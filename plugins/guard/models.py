"""Guard request and decision structures.

Implements AI-04 contract §4 (request), §18 (result) and §19 (provenance).

Requests arrive as **data** -- JSON or YAML a caller supplied -- so normalization
is where an unlisted value in a closed vocabulary is caught. §4.2 requires that
an unlisted value is never silently treated as an ordinary one, and §11.6 makes
it unsupported. Normalization is therefore strict and happens once, at the
boundary, rather than being re-checked throughout evaluation.

The request carries **no policy** (§9.1). A policy is a call parameter, not
caller-supplied data: were it a request field, a caller could vary it per call
and Guard would be selecting policy in effect if not in name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from plugins.context.context import ContextResponse
from plugins.guard.errors import RequestMalformed, RequestUnscoped
from plugins.guard.vocabulary import (
    ActorType,
    ApprovalStatus,
    CapabilityStatus,
    CheckResult,
    GuardDecision,
    PermissionLevel,
    TargetEnvironment,
    TargetInterface,
    TargetKind,
    TargetSensitivity,
    WorkingTreeState,
)

#: The only request schema this contract defines (§4).
SUPPORTED_SCHEMA_VERSION = 1

#: Permitted top-level request keys (§4). Anything else is rejected rather than
#: ignored, the same way AI-02's provider registry rejects unknown profile
#: fields: a field that is silently dropped cannot be audited, and §4 says a
#: credential value, prompt body or raw sensitive payload must not *enter* the
#: request. Ignoring such a field would leave it in the caller's payload with
#: nothing recording that Guard declined to use it.
_REQUEST_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "actor",
        "workspace",
        "action",
        "capability",
        "target",
        "context",
        "capability_state",
        "approval",
    }
)


def _enum(value: Any, kind: type, field_name: str):
    """Coerce to a closed vocabulary, refusing anything unlisted (§4.2).

    A missing value is `None` and stays `None`: "not supplied" and "supplied as
    something unrecognised" are different facts, and only the second is a
    malformed request.
    """
    if value is None:
        return None
    try:
        return kind(value)
    except ValueError:
        allowed = ", ".join(sorted(member.value for member in kind))
        raise RequestMalformed(
            f"{field_name}: {value!r} is not one of {allowed}"
        ) from None


def _require_enum(value: Any, kind: type, field_name: str):
    coerced = _enum(value, kind, field_name)
    if coerced is None:
        raise RequestMalformed(f"{field_name} is required")
    return coerced


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RequestMalformed(f"{field_name} must be an object")
    return value


def _text(
    value: Any,
    field_name: str,
    *,
    required: bool = False,
    allow_blank: bool = False,
) -> str | None:
    """Coerce to text.

    `allow_blank` exists for `workspace.workspace_id` alone: a present but blank
    scope is *unscoped*, which §15.1 treats separately from *malformed*, and the
    two carry different reason codes because they need different fixes.
    """
    if value is None:
        if required:
            raise RequestMalformed(f"{field_name} is required")
        return None
    if not isinstance(value, str):
        raise RequestMalformed(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    if required and not allow_blank and not value.strip():
        raise RequestMalformed(f"{field_name} must not be empty")
    return value


def _boolean(value: Any, field_name: str, *, default: bool | None = None):
    if value is None:
        return default
    if not isinstance(value, bool):
        raise RequestMalformed(
            f"{field_name} must be true or false; got {type(value).__name__}"
        )
    return value


@dataclass(frozen=True, slots=True)
class Actor:
    id: str
    type: ActorType

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Actor":
        return cls(
            id=_text(raw.get("id"), "actor.id", required=True),  # type: ignore[arg-type]
            type=_require_enum(raw.get("type"), ActorType, "actor.type"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": str(self.type)}


@dataclass(frozen=True, slots=True)
class WorkspaceRef:
    """The request's workspace scope (contract §4, §5).

    A deliberate **subset** of AI-03's `WorkspaceIdentity` (§4.3): `workspace_root`
    and `changed_files` are omitted because a host path carries no authorization
    meaning and leaks machine layout into a digest, and a file count would let a
    rule authorize on a number that changes for unrelated reasons.
    """

    workspace_id: str
    repository: str | None
    branch: str | None
    commit: str | None
    detached: bool
    working_tree: WorkingTreeState

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "WorkspaceRef":
        return cls(
            workspace_id=_text(
                raw.get("workspace_id"),
                "workspace.workspace_id",
                required=True,
                allow_blank=True,
            ),  # type: ignore[arg-type]
            repository=_text(raw.get("repository"), "workspace.repository"),
            branch=_text(raw.get("branch"), "workspace.branch"),
            commit=_text(raw.get("commit"), "workspace.commit"),
            detached=_boolean(raw.get("detached"), "workspace.detached", default=False),  # type: ignore[arg-type]
            working_tree=_require_enum(
                raw.get("working_tree"), WorkingTreeState, "workspace.working_tree"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "repository": self.repository,
            "branch": self.branch,
            "commit": self.commit,
            "detached": self.detached,
            "working_tree": str(self.working_tree),
        }


@dataclass(frozen=True, slots=True)
class ActionRef:
    """Contract §4.1. `permission_level` is first-class and never inferred."""

    id: str
    permission_level: PermissionLevel

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ActionRef":
        return cls(
            id=_text(raw.get("id"), "action.id", required=True),  # type: ignore[arg-type]
            permission_level=_require_enum(
                raw.get("permission_level"),
                PermissionLevel,
                "action.permission_level",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "permission_level": str(self.permission_level)}


@dataclass(frozen=True, slots=True)
class CapabilityRef:
    id: str | None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CapabilityRef":
        return cls(id=_text(raw.get("id"), "capability.id"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id}


@dataclass(frozen=True, slots=True)
class TargetRef:
    """Contract §4, §16. Every field is closed or explicitly nullable."""

    kind: TargetKind
    identifier: str | None = None
    environment: TargetEnvironment | None = None
    interface: TargetInterface | None = None
    is_real: bool | None = None
    sensitivity: TargetSensitivity | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TargetRef":
        return cls(
            kind=_require_enum(raw.get("kind"), TargetKind, "target.kind"),
            identifier=_text(raw.get("identifier"), "target.identifier"),
            environment=_enum(
                raw.get("environment"), TargetEnvironment, "target.environment"
            ),
            interface=_enum(raw.get("interface"), TargetInterface, "target.interface"),
            is_real=_boolean(raw.get("is_real"), "target.is_real"),
            sensitivity=_enum(
                raw.get("sensitivity"), TargetSensitivity, "target.sensitivity"
            ),
        )

    @property
    def has_real_environment(self) -> bool:
        """Whether §16's real-world distinction is settled, and how.

        Returns `True` only when the target is *positively* known to be real.
        An unsettled classification returns `False` and is handled separately by
        the §16 gate, which `BLOCKED`s rather than assuming simulated.
        """
        return self.environment is TargetEnvironment.REAL or self.is_real is True

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "identifier": self.identifier,
            "environment": str(self.environment) if self.environment else None,
            "interface": str(self.interface) if self.interface else None,
            "is_real": self.is_real,
            "sensitivity": str(self.sensitivity) if self.sensitivity else None,
        }


@dataclass(frozen=True, slots=True)
class CapabilityRecord:
    """One normalized capability state, consumed from AI-02 (contract §7)."""

    capability_id: str
    status: CapabilityStatus

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CapabilityRecord":
        return cls(
            capability_id=_text(
                raw.get("capability_id"), "capability_state.records[].capability_id",
                required=True,
            ),  # type: ignore[arg-type]
            status=_require_enum(
                raw.get("status"), CapabilityStatus, "capability_state.records[].status"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"capability_id": self.capability_id, "status": str(self.status)}


@dataclass(frozen=True, slots=True)
class ApprovalRef:
    """Contract §8. Guard issues no approvals; it only consumes their state."""

    status: ApprovalStatus
    scope_digest: str | None = None
    reference: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ApprovalRef":
        return cls(
            status=_require_enum(raw.get("status"), ApprovalStatus, "approval.status"),
            scope_digest=_text(raw.get("scope_digest"), "approval.scope_digest"),
            reference=_text(raw.get("reference"), "approval.reference"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "scope_digest": self.scope_digest,
            "reference": self.reference,
        }


@dataclass(frozen=True, slots=True)
class GuardRequest:
    """Contract §4. The complete authorization input, minus the policy (§9.1)."""

    actor: Actor
    workspace: WorkspaceRef
    action: ActionRef
    capability: CapabilityRef
    target: TargetRef
    approval: ApprovalRef
    capability_state: tuple[CapabilityRecord, ...] = ()
    context: ContextResponse | None = None
    schema_version: int = SUPPORTED_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "GuardRequest":
        """Normalize caller data, refusing anything the contract does not define.

        Strict by design (§4.2): an unlisted value is unsupported, and an
        unsupported input must not reach evaluation as an ordinary one.
        """
        if not isinstance(raw, Mapping):
            raise RequestMalformed("request must be an object")

        unknown = set(raw) - _REQUEST_KEYS
        if unknown:
            raise RequestMalformed(
                f"unknown request field(s): {', '.join(sorted(map(str, unknown)))}. "
                "§4 fixes the request shape; a field Guard does not define is "
                "refused rather than ignored, so a credential, prompt body or "
                "raw payload cannot ride along unremarked"
            )

        version = raw.get("schema_version")
        if version != SUPPORTED_SCHEMA_VERSION:
            raise RequestMalformed(
                f"schema_version {version!r} is not supported; "
                f"this contract defines {SUPPORTED_SCHEMA_VERSION}"
            )

        records_raw = _mapping(raw.get("capability_state", {}), "capability_state")
        records = records_raw.get("records", [])
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise RequestMalformed("capability_state.records must be a list")

        context_raw = raw.get("context")
        context: ContextResponse | None = None
        if context_raw is not None:
            context_mapping = _mapping(context_raw, "context")
            response = context_mapping.get("response")
            if response is None:
                context = None
            elif isinstance(response, ContextResponse):
                context = response
            else:
                # A ContextResponse is AI-03's object, not a shape Guard
                # redefines (§28.2). A caller passing a dict passes the wrong
                # thing, and inventing a parser for it would be a second
                # definition of AI-03's type.
                raise RequestMalformed(
                    "context.response must be an AI-03 ContextResponse instance, "
                    "not raw data; Guard consumes that type rather than "
                    "reimplementing it"
                )

        request = cls(
            actor=Actor.from_mapping(_mapping(raw.get("actor"), "actor")),
            workspace=WorkspaceRef.from_mapping(
                _mapping(raw.get("workspace"), "workspace")
            ),
            action=ActionRef.from_mapping(_mapping(raw.get("action"), "action")),
            capability=CapabilityRef.from_mapping(
                _mapping(raw.get("capability", {}), "capability")
            ),
            target=TargetRef.from_mapping(_mapping(raw.get("target"), "target")),
            approval=ApprovalRef.from_mapping(
                _mapping(raw.get("approval"), "approval")
            ),
            capability_state=tuple(
                CapabilityRecord.from_mapping(
                    _mapping(entry, "capability_state.records[]")
                )
                for entry in records
            ),
            context=context,
            schema_version=version,
        )

        # §15.1: an unscoped request is an absolute deny. Checked here because a
        # request with no workspace cannot be scoped to one, and every later
        # step assumes a scope exists.
        if not request.workspace.workspace_id.strip():
            raise RequestUnscoped("request carries no workspace scope")

        return request

    @property
    def capability_ids(self) -> frozenset[str]:
        return frozenset(record.capability_id for record in self.capability_state)

    def record_for(self, capability_id: str | None) -> CapabilityRecord | None:
        if capability_id is None:
            return None
        for record in self.capability_state:
            if record.capability_id == capability_id:
                return record
        return None

    @property
    def duplicate_capability_ids(self) -> tuple[str, ...]:
        """Capability ids recorded more than once.

        Not a §9.2 invariant (that governs `rule_id`), but the shape is the same
        hazard: two records for one id make `capability.status` ambiguous, and
        picking one silently would be exactly the "keep the first occurrence"
        resolution §9.2 forbids for rules.
        """
        seen: set[str] = set()
        duplicates: list[str] = []
        for record in self.capability_state:
            if record.capability_id in seen and record.capability_id not in duplicates:
                duplicates.append(record.capability_id)
            seen.add(record.capability_id)
        return tuple(duplicates)


@dataclass(frozen=True, slots=True)
class CheckRecord:
    """One evaluated predicate, as recorded on the decision (§18).

    `result` is a `CheckResult`, never a `GuardDecision` (§18.2).
    """

    check_id: str
    result: CheckResult
    source: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "result": str(self.result),
            "source": self.source,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class Provenance:
    """Contract §19: everything needed to answer "why was this decided?"."""

    policy_id: str | None = None
    policy_revision: str | None = None
    policy_digest: str | None = None
    rule_id: str | None = None
    context_refs: tuple[str, ...] = ()
    approval_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_revision": self.policy_revision,
            "policy_digest": self.policy_digest,
            "rule_id": self.rule_id,
            "context_refs": list(self.context_refs),
            "approval_reference": self.approval_reference,
        }


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """Contract §18. The machine-consumable result.

    Carries **no** `deterministic` field (§18.1): determinism is a contract
    guarantee verified by re-evaluation, not a value a record reports about
    itself. A field that can hold one value carries no information.

    Carries no raw context, prompt, credential or tool output (§18.3) -- only
    references.
    """

    decision: GuardDecision
    reason_code: str
    reasons: tuple[str, ...]
    workspace_id: str
    actor: Actor
    action: ActionRef
    capability: str | None
    target: TargetRef
    provenance: Provenance
    checks: tuple[CheckRecord, ...]
    request_digest: str
    evaluation_digest: str
    decision_id: str
    evaluated_at: str
    evidence_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SUPPORTED_SCHEMA_VERSION,
            "decision_id": self.decision_id,
            "evaluated_at": self.evaluated_at,
            "decision": str(self.decision),
            "reason_code": self.reason_code,
            "reasons": list(self.reasons),
            "workspace_id": self.workspace_id,
            "actor": self.actor.to_dict(),
            "action": self.action.to_dict(),
            "capability": self.capability,
            "target": self.target.to_dict(),
            "policy": {
                "policy_id": self.provenance.policy_id,
                "revision": self.provenance.policy_revision,
                "digest": self.provenance.policy_digest,
            },
            "rule_id": self.provenance.rule_id,
            "checks": [check.to_dict() for check in self.checks],
            "context_refs": list(self.provenance.context_refs),
            "approval_reference": self.provenance.approval_reference,
            "request_digest": self.request_digest,
            "evaluation_digest": self.evaluation_digest,
            "evidence_ref": self.evidence_ref,
        }


__all__ = [
    "SUPPORTED_SCHEMA_VERSION",
    "Actor",
    "ActionRef",
    "ApprovalRef",
    "CapabilityRecord",
    "CapabilityRef",
    "CheckRecord",
    "DecisionRecord",
    "GuardRequest",
    "Provenance",
    "TargetRef",
    "WorkspaceRef",
]
