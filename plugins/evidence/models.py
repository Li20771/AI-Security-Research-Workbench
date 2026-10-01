"""The AI-05 record model.

Implements the contract §5 envelope, §6.5 registry, §6.6 cross-field rules, §7
producer/actor split, §9 provenance, §11 payloads, §12 ContextRef and §13
artifacts.

Three properties carry most of the weight here.

**The record is a typed envelope plus a typed payload, not a free mapping.**
Every field is declared; a field the contract does not define is refused rather
than ignored. §13.8 depends on that: a record arriving with raw content in an
undeclared field is `REJECTED`, never quietly reshaped.

**Caller-supplied and AI-05-generated are different things.** §15.2 records for
every field whether a caller may supply it. `evidence_id`, `recorded_at`,
`content_digest`, `record_digest` and every `ContextRef.value_digest` are
AI-05's to produce, and a caller supplying one is rejected (§14.6.1, R1). This
is what makes §14.6's prohibition enforceable: no component can tell a digest of
a secret from any other digest, so the protection is not a detector — it is that
there is no field in which a caller can substitute one.

**Vocabulary membership and admission are two checks, not one.** `agent` is a
valid `ProducerType` member and is still REJECTED for every v1 admitted event,
because all six registry rows (§6.5) register `service`. `ProducerType` answers
the vocabulary question; the registry answers the admission question.

Every grammar in `grammar.py` is named after the contract's name for it, so a
field's rule can be found without reading the call site that applies it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from plugins.context.context import utc_now
from plugins.context.vocabulary import (
    Freshness,
    ItemKind,
    SourceKind,
    SourceReadStatus,
    StatusValue,
)
from plugins.guard.digest import canonical_json, sha256_hex
from plugins.guard.vocabulary import ActorType, GuardDecision
from providers.live_verification import LiveRunStatus, ProbeOutcome
from providers.model_profile import CapabilityName, CapabilityStatus

from plugins.evidence.errors import (
    ActorTypeNotAdmitted,
    CallerSuppliedDigest,
    CallerSuppliedGeneratedField,
    CallerSuppliedIdentity,
    CrossFieldViolation,
    DuplicateElement,
    DuplicateOrdinal,
    FamilyStatusMismatch,
    MissingRequiredField,
    PayloadKindMismatch,
    ProducerNotRegistered,
    ProducerRoleViolation,
    ProducerTypeNotAdmitted,
    RawContentRejected,
    RecordMalformed,
    UnknownField,
    UnsupportedVocabulary,
)
from plugins.evidence.grammar import (
    g_digest,
    g_evidence_id,
    g_host,
    g_ident,
    g_locator,
    g_modelref,
    g_opaque_id,
    g_ordinal,
    g_registered,
    g_revision,
    g_subject,
    g_text,
    g_timestamp,
)
from plugins.evidence.vocabulary import (
    EvidenceKind,
    ObservationFamily,
    ProducerType,
    producer_type_is_permitted,
)

#: The only schema version this contract defines.
SUPPORTED_SCHEMA_VERSION = 1

#: The prefix `evidence_id` carries (§8.1).
EVIDENCE_ID_PREFIX = "ev-"

#: Ceiling for a Class 4 text field. IMPLEMENTATION-CHOSEN: §14.2 forbids a
#: free-text class, so a string with no cap would be one under another name.
MAX_TEXT_LENGTH = 512


# --------------------------------------------------------------------------
# §6.5 — the v1 admitted-producer registry
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdmittedEvent:
    """One row of the §6.5 registry."""

    event: str
    kind: EvidenceKind
    family: ObservationFamily | None
    producer: str
    producer_type: ProducerType
    actor_type: ActorType


#: §6.5, transcribed. Exactly six rows, frozen by Amendment 1.
#:
#: The event-to-component mapping is CONTRACT-REQUIRED and is transcribed from
#: §6.2. The producer TOKENS are IMPLEMENTATION-CHOSEN and frozen by the
#: amendment, because no serialized producer token exists anywhere in the
#: repository.
ADMITTED_EVENTS: tuple[AdmittedEvent, ...] = (
    AdmittedEvent(
        "AI-03 context read", EvidenceKind.OBSERVATION,
        ObservationFamily.SOURCE_READ, "ai-03", ProducerType.SERVICE, ActorType.SERVICE,
    ),
    AdmittedEvent(
        "AI-02 provider probe", EvidenceKind.OBSERVATION,
        ObservationFamily.PROVIDER_PROBE, "ai-02", ProducerType.SERVICE, ActorType.SERVICE,
    ),
    AdmittedEvent(
        "AI-02 capability observation", EvidenceKind.OBSERVATION,
        ObservationFamily.CAPABILITY_OBSERVATION, "ai-02", ProducerType.SERVICE,
        ActorType.SERVICE,
    ),
    AdmittedEvent(
        "AI-04 Guard decision", EvidenceKind.DECISION,
        None, "ai-04", ProducerType.SERVICE, ActorType.SERVICE,
    ),
    AdmittedEvent(
        "AI-06 tool execution", EvidenceKind.EXECUTION,
        None, "ai-06", ProducerType.SERVICE, ActorType.AGENT,
    ),
    AdmittedEvent(
        "AI-06 test result", EvidenceKind.EXECUTION,
        None, "ai-06", ProducerType.SERVICE, ActorType.SERVICE,
    ),
)


def admitted_events_for(
    kind: EvidenceKind, family: ObservationFamily | None
) -> tuple[AdmittedEvent, ...]:
    """The registry rows an admitted record of this kind and family may match.

    An empty result means the event is NOT REPRESENTABLE in v1: that is the case
    for every `DECISION` other than AI-04's Guard decision, which is how the
    deferred routing and human-approval arms are refused rather than reserved.
    """
    return tuple(
        row for row in ADMITTED_EVENTS if row.kind is kind and row.family is family
    )


# --------------------------------------------------------------------------
# §6.6 — cross-field rules
# --------------------------------------------------------------------------


def check_cross_field(record: "EvidenceRecord") -> None:
    """Every §6.6 rejection rule, applied to a parsed record.

    Runs after parsing because each rule relates two fields, and a rule that
    related a field to a value that failed to parse would report the wrong
    problem. Failing closed here leaves the record unbuilt, so a rejected
    combination is never stored.
    """
    kind = record.identity.kind
    family = getattr(record.payload, "family", None)
    provenance = record.provenance

    candidates = admitted_events_for(kind, family)
    if not candidates:
        raise CrossFieldViolation(
            f"no admitted event has kind {kind}"
            + (f" and family {family}" if family is not None else "")
            + "; the event is not representable in v1 (§6.5)"
        )

    g_registered(
        provenance.producer,
        frozenset(row.producer for row in candidates),
        "provenance.producer",
    )
    if provenance.producer_type not in {row.producer_type for row in candidates}:
        raise ProducerTypeNotAdmitted(
            f"producer_type {provenance.producer_type} is a valid ProducerType member "
            f"but is not admitted for {candidates[0].event}; every v1 admitted event "
            "registers service (§6.5)"
        )
    if provenance.actor.type not in {row.actor_type for row in candidates}:
        raise ActorTypeNotAdmitted(
            f"actor.type {provenance.actor.type} is not admitted for kind {kind}; "
            f"expected one of {sorted(str(r.actor_type) for r in candidates)} (§6.6)"
        )


# --------------------------------------------------------------------------
# Value types
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Actor:
    """The entity whose act the record is ABOUT (§7)."""

    id: str
    type: ActorType

    @classmethod
    def from_mapping(cls, raw: object, where: str = "actor") -> "Actor":
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"id", "type"}), where)
        return cls(
            id=g_text(_required(data, "id", where), f"{where}.id"),
            type=_enum(_required(data, "type", where), ActorType, f"{where}.type"),
        )

    def to_projection(self) -> dict[str, Any]:
        return {"actor.id": self.id, "actor.type": str(self.type)}

    def to_mapping(self) -> dict[str, Any]:
        return {"id": self.id, "type": str(self.type)}


@dataclass(frozen=True, slots=True)
class WorkspaceBinding:
    """What an observation of a workspace source is bound to (§11).

    AI-03-shaped: the source kind, its stable identity, and the revision read.
    `source_revision` is validated against the sibling `source_kind` by the
    conditional rule, and by the same function the `ContextRef` path uses, so
    the two cannot drift apart.
    """

    source_kind: SourceKind
    source_identity: str
    source_revision: str

    _KEYS = frozenset({"source_kind", "source_identity", "source_revision"})

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "WorkspaceBinding":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        source_kind = _enum(
            _required(data, "source_kind", where), SourceKind, f"{where}.source_kind"
        )
        return cls(
            source_kind=source_kind,
            source_identity=g_opaque_id(
                _required(data, "source_identity", where), f"{where}.source_identity"
            ),
            source_revision=g_revision(
                _required(data, "source_revision", where),
                source_kind,
                f"{where}.source_revision",
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
        }

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
        }


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    """What an observation of an external service is bound to (§11).

    AI-02-shaped. `model_ref` is the composition AI-02 itself parses, so a
    reference AI-02 accepts is never refused here. `provider_id` and `model_id`
    are deliberately absent: `model_ref` carries both and AI-02 can split it,
    and three fields for one fact is three fields that can disagree.
    """

    model_ref: str
    endpoint_host: str | None = None
    capability: CapabilityName | None = None

    _KEYS = frozenset({"model_ref", "endpoint_host", "capability"})

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "ProviderBinding":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        endpoint = data.get("endpoint_host")
        capability = data.get("capability")
        return cls(
            model_ref=g_modelref(_required(data, "model_ref", where), f"{where}.model_ref"),
            endpoint_host=(
                None
                if endpoint is None
                else g_host(endpoint, f"{where}.endpoint_host")
            ),
            capability=(
                None
                if capability is None
                else _enum(capability, CapabilityName, f"{where}.capability")
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref,
            "endpoint_host": self.endpoint_host,
            "capability": None if self.capability is None else str(self.capability),
        }

    def to_mapping(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref,
            "endpoint_host": self.endpoint_host,
            "capability": None if self.capability is None else str(self.capability),
        }


@dataclass(frozen=True, slots=True)
class ContextRef:
    """A durable reference to one AI-03 context item (§12.1).

    Exactly nine fields. `source_kind` is AI-03's `SourceKind` and not an
    arbitrary string: before Amendment 1 it was validated as free text, which
    let a value outside the frozen vocabulary into `content_digest`.

    `value_digest` is an **identity discriminator**, not a confidentiality
    mechanism. Value participates in item identity — AI-03's Amendment 3 added it
    because two halves of a self-contradicting document shared one read and
    therefore one reference. The raw `value` is never stored and never rendered.
    """

    workspace_id: str
    source_kind: SourceKind
    source_identity: str
    source_revision: str
    subject: str
    value_digest: str
    item_kind: ItemKind
    truth_state: StatusValue
    freshness: Freshness

    _SUPPLIED_KEYS = frozenset(
        {
            "workspace_id",
            "source_kind",
            "source_identity",
            "source_revision",
            "subject",
            "value",
            "item_kind",
            "truth_state",
            "freshness",
        }
    )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "context[]") -> "ContextRef":
        """Derive a stored ContextRef from a supplied reference and its value.

        The supplied form carries the raw `value` so AI-05 can compute
        `value_digest` from something it admitted; the stored form carries only
        the digest. §30 step 10 makes `value_digest` absent from the supplied
        record, and §12.4 keeps the raw value out of the stored one.
        """
        data = _mapping(raw, where)
        if "value_digest" in data:
            raise CallerSuppliedDigest(
                f"{where}.value_digest: AI-05 computes this from an accepted "
                "value (§14.6.1, R1). A caller-supplied digest is refused whatever "
                "its shape, so sha256(secret) cannot be adopted as an Evidence "
                "digest merely by looking like one"
            )
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        value = g_text(_required(data, "value", where), f"{where}.value")
        source_kind = _enum(
            _required(data, "source_kind", where), SourceKind, f"{where}.source_kind"
        )
        return cls(
            workspace_id=g_ident(
                _required(data, "workspace_id", where), f"{where}.workspace_id"
            ),
            source_kind=source_kind,
            source_identity=g_opaque_id(
                _required(data, "source_identity", where), f"{where}.source_identity"
            ),
            source_revision=g_revision(
                _required(data, "source_revision", where),
                source_kind,
                f"{where}.source_revision",
            ),
            subject=g_subject(_required(data, "subject", where), f"{where}.subject"),
            value_digest=value_digest_of(value),
            item_kind=_enum(
                _required(data, "item_kind", where), ItemKind, f"{where}.item_kind"
            ),
            truth_state=_enum(
                _required(data, "truth_state", where), StatusValue, f"{where}.truth_state"
            ),
            freshness=_enum(
                _required(data, "freshness", where), Freshness, f"{where}.freshness"
            ),
        )

    @property
    def canonical_key(self) -> tuple[str, ...]:
        """The set-semantic ordering key (§15.4). The exact frozen identity tuple."""
        return (
            self.workspace_id,
            str(self.source_kind),
            self.source_identity,
            self.source_revision,
            self.subject,
            self.value_digest,
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
            "subject": self.subject,
            "value_digest": self.value_digest,
            "item_kind": str(self.item_kind),
            "truth_state": str(self.truth_state),
            "freshness": str(self.freshness),
        }

    #: The stored form's keys. `value_digest` replaces the supplied `value`;
    #: there is no key for the raw value, because §12.4 forbids persisting one.
    _STORED_KEYS = frozenset(
        {
            "workspace_id",
            "source_kind",
            "source_identity",
            "source_revision",
            "subject",
            "value_digest",
            "item_kind",
            "truth_state",
            "freshness",
        }
    )

    def to_mapping(self) -> dict[str, Any]:
        """The stored form (§12.1): nine fields, `value_digest`, no raw `value`."""
        return {
            "workspace_id": self.workspace_id,
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
            "subject": self.subject,
            "value_digest": self.value_digest,
            "item_kind": str(self.item_kind),
            "truth_state": str(self.truth_state),
            "freshness": str(self.freshness),
        }

    @classmethod
    def from_stored_mapping(cls, raw: object, where: str = "references.context[]") -> "ContextRef":
        """Rebuild a written ContextRef from the digest it already carries (§17).

        This is the **stored path**, and it is not the caller path. The supplied
        form carries the raw `value` and no digest, because AI-05 computes the
        digest from something it admitted; the stored form carries the digest
        and no value, because §12.4 forbids persisting one and there is nothing
        left to recompute it from.

        `from_mapping` above still refuses a caller-supplied `value_digest`
        outright. Nothing here relaxes that: the two entry points are separate
        methods with separate key sets, and no argument turns one into the
        other.

        The digest is validated for shape (`g_digest`) and by nothing else —
        it cannot be recomputed, because the value it was computed from is not
        stored. That is exactly why the digest is also inside `record_digest`:
        a substituted `value_digest` is caught by round-trip verification, not
        by this parser.
        """
        data = _mapping(raw, where)
        if "value" in data:
            raise UnknownField(
                f"{where}.value: the stored form carries no raw value (§12.4). A "
                "raw value MUST NOT be persisted in a ContextRef, so its presence "
                "here is refused rather than read or discarded"
            )
        _closed_keys(data, cls._STORED_KEYS, where)
        source_kind = _enum(
            _required(data, "source_kind", where), SourceKind, f"{where}.source_kind"
        )
        return cls(
            workspace_id=g_ident(
                _required(data, "workspace_id", where), f"{where}.workspace_id"
            ),
            source_kind=source_kind,
            source_identity=g_opaque_id(
                _required(data, "source_identity", where), f"{where}.source_identity"
            ),
            source_revision=g_revision(
                _required(data, "source_revision", where),
                source_kind,
                f"{where}.source_revision",
            ),
            subject=g_subject(_required(data, "subject", where), f"{where}.subject"),
            value_digest=g_digest(
                _required(data, "value_digest", where), f"{where}.value_digest"
            ),
            item_kind=_enum(
                _required(data, "item_kind", where), ItemKind, f"{where}.item_kind"
            ),
            truth_state=_enum(
                _required(data, "truth_state", where), StatusValue, f"{where}.truth_state"
            ),
            freshness=_enum(
                _required(data, "freshness", where), Freshness, f"{where}.freshness"
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A reference to bytes AI-05 never reads (§13).

    `artifact_digest` is the one caller-supplied digest, because the producer
    holds the bytes and AI-05 does not (§13.5). Its declared role is
    artifact-byte integrity, not the representation of a record's own content.

    **`role` does not exist here.** §13.1 requires it ABSENT in v1, so a supplied
    `role` is REJECTED rather than stripped — stripping would be the silent
    substitution §14.4.1 forbids and would leave the caller believing a value had
    been kept.
    """

    artifact_digest: str
    external: bool
    owner_workspace_id: str | None = None
    artifact_ref: str | None = None

    _SUPPLIED_KEYS = frozenset(
        {"artifact_digest", "external", "owner_workspace_id", "artifact_ref"}
    )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "artifacts[]") -> "ArtifactRef":
        data = _mapping(raw, where)
        if "role" in data:
            raise UnknownField(
                f"{where}.role: §13.1 requires `artifact.items[].role` to be ABSENT "
                "in v1. It is a closed vocabulary whose members are not yet frozen, "
                "so the field is refused rather than stripped or ignored; "
                "reintroducing it requires an amendment that freezes its members"
            )
        if "availability" in data or "artifact_state" in data:
            raise RawContentRejected(
                f"{where}: artifact availability is a query-time fact about the "
                "store, never a record field (§13.3). Recording it would require "
                "writing to the record when the artifact expires, which §19 forbids"
            )
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        external = _required(data, "external", where)
        if not isinstance(external, bool):
            raise RecordMalformed(
                f"{where}.external must be true or false; got {type(external).__name__}"
            )
        owner = data.get("owner_workspace_id")
        owner_id = None if owner is None else g_ident(owner, f"{where}.owner_workspace_id")
        if external and owner_id is None:
            raise MissingRequiredField(
                f"{where}.owner_workspace_id is required when external is true (§13.6)"
            )
        ref = data.get("artifact_ref")
        return cls(
            artifact_digest=g_digest(
                _required(data, "artifact_digest", where), f"{where}.artifact_digest"
            ),
            external=external,
            owner_workspace_id=owner_id,
            artifact_ref=None if ref is None else g_locator(ref, f"{where}.artifact_ref"),
        )

    @property
    def canonical_key(self) -> tuple[str]:
        """The set-semantic ordering key (§13.2): `artifact_digest` alone.

        `role` is absent in v1, so the key the contract writes as
        `(role, artifact_digest)` degenerates to this. `artifact_ref` is
        deliberately absent: it is a locator, and ordering by it would make the
        digest depend on where the bytes happen to live.
        """
        return (self.artifact_digest,)

    def to_projection(self) -> dict[str, Any]:
        return {
            "artifact_digest": self.artifact_digest,
            "external": self.external,
            "owner_workspace_id": self.owner_workspace_id,
            "artifact_ref": self.artifact_ref,
        }

    def to_mapping(self) -> dict[str, Any]:
        """The stored form is the supplied form: nothing here is generated."""
        return {
            "artifact_digest": self.artifact_digest,
            "external": self.external,
            "owner_workspace_id": self.owner_workspace_id,
            "artifact_ref": self.artifact_ref,
        }


@dataclass(frozen=True, slots=True)
class RecordRef:
    """A link to a durable record (§23.3). SET-semantic, ordered by `record_ref`.

    A `record_ref` ALWAYS denotes an AI-05 `evidence_id`. An AI-04 guard decision
    id is never one: an AI-04 decision is recorded as an AI-05 `DECISION` record
    and referenced by that record's id.
    """

    record_ref: str

    @classmethod
    def from_mapping(cls, raw: object, where: str = "decisions[]") -> "RecordRef":
        if isinstance(raw, str):
            return cls(record_ref=g_evidence_id(raw, where))
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"record_ref"}), where)
        return cls(
            record_ref=g_evidence_id(
                _required(data, "record_ref", where), f"{where}.record_ref"
            )
        )

    @property
    def canonical_key(self) -> tuple[str]:
        return (self.record_ref,)

    def to_projection(self) -> dict[str, Any]:
        return {"record_ref": self.record_ref}

    def to_mapping(self) -> dict[str, Any]:
        return {"record_ref": self.record_ref}


@dataclass(frozen=True, slots=True)
class SupersedeRef:
    """A forward reference to a record this one corrects (§21.1).

    Forward only, on the NEW record. The superseded record is never touched, so
    `superseded_by` is derived by query and never stored (§21.2).

    `correction_reason` keeps its frozen name. An earlier draft renamed it to
    `correction_code`; that was withdrawn because nothing established it is a
    code, and different leaf paths already distinguish it from
    `payload.reason_code`.
    """

    record_ref: str
    correction_reason: str

    _SUPPLIED_KEYS = frozenset({"record_ref", "correction_reason"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "supersedes[]") -> "SupersedeRef":
        data = _mapping(raw, where)
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        return cls(
            record_ref=g_evidence_id(
                _required(data, "record_ref", where), f"{where}.record_ref"
            ),
            correction_reason=g_text(
                _required(data, "correction_reason", where),
                f"{where}.correction_reason",
            ),
        )

    @property
    def canonical_key(self) -> tuple[str]:
        return (self.record_ref,)

    def to_projection(self) -> dict[str, Any]:
        return {
            "record_ref": self.record_ref,
            "correction_reason": self.correction_reason,
        }

    def to_mapping(self) -> dict[str, Any]:
        return {
            "record_ref": self.record_ref,
            "correction_reason": self.correction_reason,
        }


# --------------------------------------------------------------------------
# Payloads (§11)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceReadObservation:
    """An OBSERVATION of a workspace source (§11, family SOURCE_READ).

    Carries `SourceReadStatus` from AI-03, whose docstring records why it must
    not be folded: "A source that was not read is never reported as read with an
    empty payload: MISSING is not an empty document, and it is not a PASS."
    """

    subject: str
    binding: WorkspaceBinding
    read_status: SourceReadStatus
    observed: str

    family = ObservationFamily.SOURCE_READ
    _KEYS = frozenset({"family", "subject", "binding", "read_status", "observed"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "SourceReadObservation":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls(
            subject=g_subject(_required(data, "subject", where), f"{where}.subject"),
            binding=WorkspaceBinding.from_mapping(
                _required(data, "binding", where), f"{where}.binding"
            ),
            read_status=_enum(
                _required(data, "read_status", where),
                SourceReadStatus,
                f"{where}.read_status",
            ),
            observed=g_text(_required(data, "observed", where), f"{where}.observed"),
        )

    def to_projection(self) -> dict[str, Any]:
        """Flat, keyed by the contract's leaf names under `payload.`."""
        return {
            "family": str(self.family),
            "subject": self.subject,
            "binding.source_kind": str(self.binding.source_kind),
            "binding.source_identity": self.binding.source_identity,
            "binding.source_revision": self.binding.source_revision,
            "read_status": str(self.read_status),
            "observed": self.observed,
        }

    def to_mapping(self) -> dict[str, Any]:
        """Nested, keyed as `from_mapping` reads it — the inverse, not the projection."""
        return {
            "family": str(self.family),
            "subject": self.subject,
            "binding": self.binding.to_mapping(),
            "read_status": str(self.read_status),
            "observed": self.observed,
        }


@dataclass(frozen=True, slots=True)
class ProviderProbeObservation:
    """An OBSERVATION of a probe run (§11, family PROVIDER_PROBE).

    Carries AI-02's `LiveRunStatus`.
    """

    subject: str
    binding: ProviderBinding
    run_status: LiveRunStatus
    observed: str

    family = ObservationFamily.PROVIDER_PROBE
    _KEYS = frozenset({"family", "subject", "binding", "run_status", "observed"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "ProviderProbeObservation":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls(
            subject=g_subject(_required(data, "subject", where), f"{where}.subject"),
            binding=ProviderBinding.from_mapping(
                _required(data, "binding", where), f"{where}.binding"
            ),
            run_status=_enum(
                _required(data, "run_status", where), LiveRunStatus, f"{where}.run_status"
            ),
            observed=g_text(_required(data, "observed", where), f"{where}.observed"),
        )

    def to_projection(self) -> dict[str, Any]:
        """Flat, keyed by the contract's leaf names under `payload.`."""
        return {
            "family": str(self.family),
            "subject": self.subject,
            "binding.model_ref": self.binding.model_ref,
            "binding.endpoint_host": self.binding.endpoint_host,
            "binding.capability": (
                None if self.binding.capability is None else str(self.binding.capability)
            ),
            "run_status": str(self.run_status),
            "observed": self.observed,
        }

    def to_mapping(self) -> dict[str, Any]:
        """Nested, keyed as `from_mapping` reads it — the inverse, not the projection."""
        return {
            "family": str(self.family),
            "subject": self.subject,
            "binding": self.binding.to_mapping(),
            "run_status": str(self.run_status),
            "observed": self.observed,
        }


@dataclass(frozen=True, slots=True)
class CapabilityObservation:
    """An OBSERVATION of what a probe found about a capability (§11).

    Carries AI-02's `ProbeOutcome` and `CapabilityStatus`. `ProbeOutcome`'s own
    docstring records why the two are not interchangeable with any other status
    vocabulary: "INCONCLUSIVE is distinct from FAIL: a model that answers a tool
    prompt in prose has not demonstrated that tool calling is broken, only that
    this prompt did not elicit it. Collapsing the two would turn a weak probe
    into a false negative."
    """

    subject: str
    binding: ProviderBinding
    outcome: ProbeOutcome
    candidate_status: CapabilityStatus
    observed: str

    family = ObservationFamily.CAPABILITY_OBSERVATION
    _KEYS = frozenset(
        {"family", "subject", "binding", "outcome", "candidate_status", "observed"}
    )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "CapabilityObservation":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        binding = ProviderBinding.from_mapping(
            _required(data, "binding", where), f"{where}.binding"
        )
        if binding.capability is None:
            raise MissingRequiredField(
                f"{where}.binding.capability is required for a "
                "CAPABILITY_OBSERVATION; a capability conclusion that does not name "
                "a capability is not a capability observation (§6.7)"
            )
        return cls(
            subject=g_subject(_required(data, "subject", where), f"{where}.subject"),
            binding=binding,
            outcome=_enum(
                _required(data, "outcome", where), ProbeOutcome, f"{where}.outcome"
            ),
            candidate_status=_enum(
                _required(data, "candidate_status", where),
                CapabilityStatus,
                f"{where}.candidate_status",
            ),
            observed=g_text(_required(data, "observed", where), f"{where}.observed"),
        )

    def to_projection(self) -> dict[str, Any]:
        """Flat, keyed by the contract's leaf names under `payload.`."""
        return {
            "family": str(self.family),
            "subject": self.subject,
            "binding.model_ref": self.binding.model_ref,
            "binding.endpoint_host": self.binding.endpoint_host,
            "binding.capability": (
                None if self.binding.capability is None else str(self.binding.capability)
            ),
            "outcome": str(self.outcome),
            "candidate_status": str(self.candidate_status),
            "observed": self.observed,
        }

    def to_mapping(self) -> dict[str, Any]:
        """Nested, keyed as `from_mapping` reads it — the inverse, not the projection."""
        return {
            "family": str(self.family),
            "subject": self.subject,
            "binding": self.binding.to_mapping(),
            "outcome": str(self.outcome),
            "candidate_status": str(self.candidate_status),
            "observed": self.observed,
        }


#: The typed union. The family selects the arm; the arm selects the status
#: vocabulary. Nothing here is inferred from a producer name.
OBSERVATION_BY_FAMILY: Mapping[ObservationFamily, type] = {
    ObservationFamily.SOURCE_READ: SourceReadObservation,
    ObservationFamily.PROVIDER_PROBE: ProviderProbeObservation,
    ObservationFamily.CAPABILITY_OBSERVATION: CapabilityObservation,
}


def observation_payload(
    raw: object, where: str = "payload"
) -> tuple[ObservationFamily, Any]:
    """Parse an OBSERVATION payload, dispatching on the explicit `family`.

    `family` is REQUIRED and is read before anything else. A payload carrying a
    status field belonging to a different family is REJECTED by the arm's closed
    key set, so a `PROVIDER_PROBE` cannot smuggle in a `read_status`.
    """
    data = _mapping(raw, where)
    if "family" not in data or data["family"] is None:
        raise MissingRequiredField(
            f"{where}.family is required on every OBSERVATION (§6.7). It selects "
            "the binding arm and the status vocabulary, and is never inferred from "
            "a producer"
        )
    family = _enum(data["family"], ObservationFamily, f"{where}.family")
    return family, OBSERVATION_BY_FAMILY[family].from_mapping(data, where)


@dataclass(frozen=True, slots=True)
class DecisionPayload:
    """What a DECISION asserts (§11). Fields are SEMANTIC.

    v1 admits the AI-04 Guard arm only. Routing decisions and human approvals are
    classified as `DECISION` by §6.2 and their outcome vocabularies are NOT
    FROZEN, so neither arm is representable — §6.5 registers no token for either
    and the cross-field rule refuses any producer that is not `ai-04`.
    """

    decision: GuardDecision
    reason_code: str
    input_digest: str
    reasons: tuple[str, ...] = ()

    _KEYS = frozenset({"decision", "reason_code", "reasons", "input_digest"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "DecisionPayload":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        raw_reasons = _sequence(data.get("reasons", []), f"{where}.reasons")
        reasons = tuple(
            g_text(entry, f"{where}.reasons[]") for entry in raw_reasons
        )
        if len(set(reasons)) != len(reasons):
            raise DuplicateElement(
                f"{where}.reasons: payload.reasons[] is SET-semantic (§15.4) and a "
                "duplicate element is REJECTED. Deduplicating would be the silent "
                "substitution §14.4.1 forbids; a set that preserves multiplicity is "
                "not a set"
            )
        return cls(
            decision=_enum(
                _required(data, "decision", where), GuardDecision, f"{where}.decision"
            ),
            reason_code=g_ident(
                _required(data, "reason_code", where), f"{where}.reason_code"
            ),
            input_digest=g_digest(
                _required(data, "input_digest", where), f"{where}.input_digest"
            ),
            reasons=reasons,
        )

    def to_projection(self) -> dict[str, Any]:
        """Emitted in ascending element order, so permutation cannot move it."""
        return {
            "decision": str(self.decision),
            "reason_code": self.reason_code,
            "input_digest": self.input_digest,
            "reasons[]": sorted(self.reasons),
        }

    def to_mapping(self) -> dict[str, Any]:
        """The key is `reasons`, which is what `from_mapping` reads.

        The projection spells it `reasons[]`; the two shapes are deliberately
        not the same object, and copying the projection here would have carried
        a key `from_mapping` does not accept.
        """
        return {
            "decision": str(self.decision),
            "reason_code": self.reason_code,
            "input_digest": self.input_digest,
            "reasons": sorted(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One step in an EXECUTION's sequence (§11.1).

    `ordinal` is the semantic ordering. **Array position is not.** Serializing in
    array order would make the digest depend on how the caller happened to write
    the list — the defect AI-04-B §E.1 recorded — so the collection is sorted by
    this value before hashing, and the array is free to be rewritten.
    """

    ordinal: int
    what_ran: str
    status: StatusValue

    _KEYS = frozenset({"ordinal", "what_ran", "status"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "tool_calls[]") -> "ToolCall":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls(
            ordinal=g_ordinal(_required(data, "ordinal", where), f"{where}.ordinal"),
            what_ran=g_text(_required(data, "what_ran", where), f"{where}.what_ran"),
            status=_enum(
                _required(data, "status", where), StatusValue, f"{where}.status"
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "what_ran": self.what_ran,
            "status": str(self.status),
        }

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "what_ran": self.what_ran,
            "status": str(self.status),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPayload:
    """What an EXECUTION asserts (§11). ORDER-semantic by explicit ordinal.

    `result_classification` does not exist here: §11 requires it ABSENT in v1.
    """

    tool_calls: tuple[ToolCall, ...] = ()

    _KEYS = frozenset({"tool_calls[]"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "ExecutionPayload":
        data = _mapping(raw, where)
        entries = _sequence(data.get("tool_calls[]", []), f"{where}.tool_calls[]")
        if "result_classification" in data or any(
            isinstance(entry, Mapping) and "result_classification" in entry
            for entry in entries
        ):
            raise UnknownField(
                f"{where}.result_classification: §11 requires it ABSENT in v1. It "
                "is a vocabulary whose members are not yet frozen, so the field is "
                "refused rather than admitted with an open value domain"
            )
        _closed_keys(data, cls._KEYS, where)
        calls = tuple(
            ToolCall.from_mapping(entry, f"{where}.tool_calls[]")
            for entry in entries
        )
        ordinals = [call.ordinal for call in calls]
        if len(set(ordinals)) != len(ordinals):
            raise DuplicateOrdinal(
                f"{where}.tool_calls: ordinal must be unique within the collection "
                "(§11.1). A duplicate leaves the ordering indeterminate and would "
                "need a tie-break comparator, which §15.4 forbids"
            )
        return cls(tool_calls=calls)

    def to_projection(self) -> dict[str, Any]:
        """Ordered by the explicit ordinal, never by array position (§11.1)."""
        return {
            "tool_calls[]": [
                call.to_projection()
                for call in sorted(self.tool_calls, key=lambda c: c.ordinal)
            ]
        }

    def to_mapping(self) -> dict[str, Any]:
        """Emitted in ordinal order, so the stored bytes are deterministic.

        `from_mapping` reads `tool_calls[]` and requires the ordinals to be
        unique, so a stored array written in any order re-reads to the same
        record — the order is the ordinal's job, not the array's (§11.1).
        """
        return {
            "tool_calls[]": [
                call.to_mapping()
                for call in sorted(self.tool_calls, key=lambda c: c.ordinal)
            ]
        }


PAYLOAD_BY_KIND: Mapping[EvidenceKind, type] = {
    EvidenceKind.DECISION: DecisionPayload,
    EvidenceKind.EXECUTION: ExecutionPayload,
}


# --------------------------------------------------------------------------
# Envelope sections
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Identity:
    """`identity` (§5). `evidence_id` is AI-05-generated and never caller-supplied."""

    kind: EvidenceKind
    evidence_id: str | None = None

    def to_projection(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, "kind": str(self.kind)}

    def to_mapping(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, "kind": str(self.kind)}

    @classmethod
    def from_stored_mapping(cls, raw: object, where: str = "identity") -> "Identity":
        """Rebuild the identity section of a written record (§5, §8.1).

        The stored path reads an `evidence_id`; the caller path never sees one.
        `EvidenceRecord.from_mapping` still raises `CallerSuppliedIdentity` for
        a supplied `evidence_id`, and this method does not change that — it is
        reached only from `stored.load_stored`.
        """
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"evidence_id", "kind"}), where)
        return cls(
            kind=_enum(_required(data, "kind", where), EvidenceKind, f"{where}.kind"),
            evidence_id=g_evidence_id(
                _required(data, "evidence_id", where), f"{where}.evidence_id"
            ),
        )


@dataclass(frozen=True, slots=True)
class Provenance:
    """`provenance` (§7, §9).

    `producer` is the component that WROTE the record; `actor` is the entity
    whose act it describes. Different questions, different fields, never
    conflated — which is why `kind` can be DECISION while `actor.type` is human.

    `producer_type` is a `ProducerType`, not an `ActorType` (Amendment 1, §7.1).
    """

    producer: str
    producer_version: str
    producer_type: ProducerType
    actor: Actor
    workspace_id: str
    recorded_at: str
    experiment_id: str | None = None
    observed_at: str | None = None

    _SUPPLIED_KEYS = frozenset(
        {
            "producer",
            "producer_version",
            "producer_type",
            "actor",
            "workspace_id",
            "experiment_id",
            "observed_at",
        }
    )

    #: The stored form adds the one field the caller form must not carry.
    _STORED_KEYS = _SUPPLIED_KEYS | {"recorded_at"}

    @classmethod
    def _validated_fields(cls, data: Mapping[str, Any], where: str) -> dict[str, Any]:
        """Every field except `recorded_at`, which the two entry points source apart.

        Shared so the caller path and the stored path cannot drift on the
        producer role constraint, the actor parse, or either timestamp's shape.
        The field list lives here once; neither entry point restates it.
        """
        raw_type = _required(data, "producer_type", where)
        if not producer_type_is_permitted(raw_type):
            raise ProducerRoleViolation(
                f"{where}.producer_type: {raw_type!r} is not a ProducerType member "
                f"(§7.1). The vocabulary is {sorted(m.value for m in ProducerType)}; "
                "`human` is an ActorType member and is not one of them, because the "
                "producer is the component that wrote the record and a human does "
                "not author an EvidenceRecord directly"
            )

        observed_at = data.get("observed_at")
        experiment_id = data.get("experiment_id")
        return dict(
            producer=g_text(_required(data, "producer", where), f"{where}.producer"),
            producer_version=g_ident(
                _required(data, "producer_version", where), f"{where}.producer_version"
            ),
            producer_type=ProducerType(raw_type),
            actor=Actor.from_mapping(_required(data, "actor", where), f"{where}.actor"),
            workspace_id=g_ident(
                _required(data, "workspace_id", where), f"{where}.workspace_id"
            ),
            experiment_id=(
                None
                if experiment_id is None
                else g_ident(experiment_id, f"{where}.experiment_id")
            ),
            observed_at=(
                None
                if observed_at is None
                else g_timestamp(observed_at, f"{where}.observed_at")
            ),
        )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "provenance") -> "Provenance":
        data = _mapping(raw, where)
        if "recorded_at" in data:
            raise CallerSuppliedGeneratedField(
                f"{where}.recorded_at: AI-05 stamps this when it writes the "
                "record (§15.2); it is not caller-supplied"
            )
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        return cls(recorded_at="", **cls._validated_fields(data, where))

    @classmethod
    def from_stored_mapping(cls, raw: object, where: str = "provenance") -> "Provenance":
        """Rebuild provenance from a written record, `recorded_at` included (§17).

        The caller path refuses `recorded_at` because AI-05 stamps it; the
        stored path requires it, because a record that has been written has
        one. The two are separate methods with separate key sets rather than
        one method with an `allow_generated_fields` switch — a switch would put
        both boundaries behind one flag, and a caller reaching the wrong branch
        would be a configuration mistake instead of a type error.
        """
        data = _mapping(raw, where)
        _closed_keys(data, cls._STORED_KEYS, where)
        return cls(
            recorded_at=g_timestamp(
                _required(data, "recorded_at", where), f"{where}.recorded_at"
            ),
            **cls._validated_fields(data, where),
        )

    def to_mapping(self) -> dict[str, Any]:
        """The stored form: every `_STORED_KEYS` field, `recorded_at` included."""
        return {
            "producer": self.producer,
            "producer_version": self.producer_version,
            "producer_type": str(self.producer_type),
            "actor": self.actor.to_mapping(),
            "workspace_id": self.workspace_id,
            "experiment_id": self.experiment_id,
            "observed_at": self.observed_at,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True, slots=True)
class References:
    """`references` (§5, §12, §21). All three collections are SET-semantic."""

    context: tuple[ContextRef, ...] = ()
    decisions: tuple[RecordRef, ...] = ()
    supersedes: tuple[SupersedeRef, ...] = ()

    _KEYS = frozenset({"context", "decisions", "supersedes"})

    @classmethod
    def _checked(
        cls,
        where: str,
        context: tuple[ContextRef, ...],
        decisions: tuple[RecordRef, ...],
        supersedes: tuple[SupersedeRef, ...],
    ) -> "References":
        """Build the section, applying §15.4's duplicate rule to all three sets.

        One place, reached by both entry points, so the caller path and the
        stored path cannot disagree about what a duplicate is.
        """
        for name, items in (
            ("context", context),
            ("decisions", decisions),
            ("supersedes", supersedes),
        ):
            keys = [item.canonical_key for item in items]
            if len(set(keys)) != len(keys):
                raise DuplicateElement(
                    f"{where}.{name} is SET-semantic (§15.4) and a duplicate element "
                    "is REJECTED. A set that preserves multiplicity is not a set"
                )
        return cls(context=context, decisions=decisions, supersedes=supersedes)

    @classmethod
    def from_mapping(cls, raw: object, where: str = "references") -> "References":
        if raw is None:
            return cls()
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls._checked(
            where,
            tuple(
                ContextRef.from_mapping(entry, f"{where}.context[]")
                for entry in _sequence(data.get("context", []), f"{where}.context")
            ),
            tuple(
                RecordRef.from_mapping(entry, f"{where}.decisions[]")
                for entry in _sequence(data.get("decisions", []), f"{where}.decisions")
            ),
            tuple(
                SupersedeRef.from_mapping(entry, f"{where}.supersedes[]")
                for entry in _sequence(data.get("supersedes", []), f"{where}.supersedes")
            ),
        )

    @classmethod
    def from_stored_mapping(cls, raw: object, where: str = "references") -> "References":
        """As `from_mapping`, with the stored ContextRef parser in place of the caller one.

        `ContextRef` is the only member of this section whose two forms differ,
        so it is the only parser that is swapped. `decisions` and `supersedes`
        carry no generated field and are read by the same code.
        """
        if raw is None:
            return cls()
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls._checked(
            where,
            tuple(
                ContextRef.from_stored_mapping(entry, f"{where}.context[]")
                for entry in _sequence(data.get("context", []), f"{where}.context")
            ),
            tuple(
                RecordRef.from_mapping(entry, f"{where}.decisions[]")
                for entry in _sequence(data.get("decisions", []), f"{where}.decisions")
            ),
            tuple(
                SupersedeRef.from_mapping(entry, f"{where}.supersedes[]")
                for entry in _sequence(data.get("supersedes", []), f"{where}.supersedes")
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "context": [item.to_projection() for item in self.context],
            "decisions": [item.to_projection() for item in self.decisions],
            "supersedes": [item.to_projection() for item in self.supersedes],
        }

    def to_mapping(self) -> dict[str, Any]:
        """Sets emitted in canonical order, so the stored bytes are deterministic.

        The order is not part of the record's meaning — §15.4 makes all three
        SET — so a stored array in any order re-reads to the same record and to
        the same digests. Emitting them sorted is a storage choice, not a claim
        that the order carries information.
        """
        return {
            "context": [
                item.to_mapping()
                for item in sorted(self.context, key=lambda i: i.canonical_key)
            ],
            "decisions": [
                item.to_mapping()
                for item in sorted(self.decisions, key=lambda i: i.canonical_key)
            ],
            "supersedes": [
                item.to_mapping()
                for item in sorted(self.supersedes, key=lambda i: i.canonical_key)
            ],
        }


@dataclass(frozen=True, slots=True)
class Artifacts:
    """`artifacts` (§13). SET-semantic, keyed by `artifact_digest`."""

    items: tuple[ArtifactRef, ...] = ()

    @classmethod
    def from_mapping(cls, raw: object, where: str = "artifacts") -> "Artifacts":
        if raw is None:
            return cls()
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"items"}), where)
        items = tuple(
            ArtifactRef.from_mapping(entry, f"{where}.items[]")
            for entry in _sequence(data.get("items", []), f"{where}.items")
        )
        keys = [item.canonical_key for item in items]
        if len(set(keys)) != len(keys):
            raise DuplicateElement(
                f"{where}.items: `artifact_digest` must be unique within a record "
                "(§13.2). A second entry with the same digest is a DUPLICATE and is "
                "REJECTED, not merged"
            )
        return cls(items=items)

    def to_projection(self) -> dict[str, Any]:
        return {"items": [item.to_projection() for item in self.items]}

    def to_mapping(self) -> dict[str, Any]:
        """Canonical order, as `References.to_mapping` — the collection is SET."""
        return {
            "items": [
                item.to_mapping()
                for item in sorted(self.items, key=lambda i: i.canonical_key)
            ]
        }


@dataclass(frozen=True, slots=True)
class Integrity:
    """`integrity` (§16, §17). Both digests are AI-05-generated (R1)."""

    content_digest: str | None = None
    record_digest: str | None = None

    def to_projection(self) -> dict[str, Any]:
        return {
            "content_digest": self.content_digest,
            "record_digest": self.record_digest,
        }

    def to_mapping(self) -> dict[str, Any]:
        return {
            "content_digest": self.content_digest,
            "record_digest": self.record_digest,
        }

    @classmethod
    def from_stored_mapping(cls, raw: object, where: str = "integrity") -> "Integrity":
        """Read the integrity section of a written record (§16, §17).

        Both digests are REQUIRED here, where the caller path has neither: a
        record that has been written carries both, and a stored record missing
        one is a malformed stored form rather than a record awaiting admission.

        Shape is validated; the **values are not trusted**. Whether they are
        the right digests for this record is decided by
        `stored.verify_stored_integrity`, which recomputes them.
        """
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"content_digest", "record_digest"}), where)
        return cls(
            content_digest=g_digest(
                _required(data, "content_digest", where), f"{where}.content_digest"
            ),
            record_digest=g_digest(
                _required(data, "record_digest", where), f"{where}.record_digest"
            ),
        )


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


#: Fields AI-05 generates. A caller supplying one is refused (R1).
_CALLER_FORBIDDEN_TOP_LEVEL = frozenset(
    {"evidence_id", "record_digest", "content_digest"}
)

_TOP_KEYS = frozenset(
    {
        "schema_version",
        "evidence_id",
        "record_digest",
        "content_digest",
        "identity",
        "kind",
        "payload",
        "provenance",
        "references",
        "artifacts",
        "integrity",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """The AI-05 record (§5). Envelope plus a typed payload.

    Constructed through `from_mapping`, which is where the strictness lives: a
    field the contract does not define is refused, a caller-supplied generated
    field is refused, the payload must be the one this kind declares, and every
    §6.6 cross-field rule is applied before the record exists.
    """

    identity: Identity
    provenance: Provenance
    payload: Any
    schema_version: int = SUPPORTED_SCHEMA_VERSION
    references: References = field(default_factory=References)
    artifacts: Artifacts = field(default_factory=Artifacts)
    integrity: Integrity = field(default_factory=Integrity)

    @property
    def kind(self) -> EvidenceKind:
        return self.identity.kind

    @property
    def evidence_id(self) -> str | None:
        return self.identity.evidence_id

    @property
    def family(self) -> ObservationFamily | None:
        return getattr(self.payload, "family", None)

    @classmethod
    def from_mapping(
        cls,
        raw: object,
        *,
        evidence_id: str | None = None,
        clock=None,
    ) -> "EvidenceRecord":
        """Parse a supplied record, stamping the fields AI-05 generates.

        The supplied form carries **no** `evidence_id`, `recorded_at`,
        `content_digest`, `record_digest` or `value_digest`. Supplying one is
        refused rather than ignored, because accepting it would let a caller
        substitute a digest for content AI-05 never admitted (§14.6.1, R1).
        """
        data = _mapping(raw, "record")

        for name in sorted(_CALLER_FORBIDDEN_TOP_LEVEL & set(data)):
            error = (
                CallerSuppliedIdentity
                if name == "evidence_id"
                else CallerSuppliedDigest
            )
            raise error(
                f"record.{name}: AI-05 generates this (§14.6.1, §8.1). Digest-shaped "
                "is not the same as trustworthy — a caller-supplied value is refused "
                "whatever its shape"
            )
        if "recorded_at" in _mapping(data.get("provenance", {}) or {}, "provenance"):
            raise CallerSuppliedGeneratedField(
                "provenance.recorded_at: AI-05 stamps this when it writes the record"
            )

        _closed_keys(data, _TOP_KEYS, "record")
        version = _schema_version(data, "record")

        kind = _enum(_required(data, "kind", "record"), EvidenceKind, "record.kind")
        payload = _parse_payload(kind, _required(data, "payload", "record"))

        provenance = Provenance.from_mapping(
            _required(data, "provenance", "record"), "provenance"
        )
        # `recorded_at` is AI-05's to stamp, so it is set here rather than parsed.
        provenance = replace(provenance, recorded_at=(clock or utc_now)())

        record = cls(
            identity=Identity(kind=kind, evidence_id=evidence_id or new_evidence_id()),
            provenance=provenance,
            payload=payload,
            schema_version=version,
            references=References.from_mapping(data.get("references"), "references"),
            artifacts=Artifacts.from_mapping(data.get("artifacts"), "artifacts"),
            integrity=Integrity(),
        )
        check_cross_field(record)
        return record

    def with_integrity(self, integrity: Integrity) -> "EvidenceRecord":
        """Return a copy carrying computed digests. Never mutates in place."""
        return replace(self, integrity=integrity)

    def assert_kind_matches_payload(self) -> None:
        """The payload must be the one this kind declares (§11)."""
        if self.identity.kind is EvidenceKind.OBSERVATION:
            expected = OBSERVATION_BY_FAMILY[ObservationFamily(self.payload.family)]
        else:
            expected = PAYLOAD_BY_KIND[self.identity.kind]
        if not isinstance(self.payload, expected):
            raise PayloadKindMismatch(
                f"kind {self.identity.kind} requires a {expected.__name__}; got "
                f"{type(self.payload).__name__}"
            )

    def to_stored_mapping(self) -> dict[str, Any]:
        """The §5 envelope, fully populated — this record's stored representation.

        **This is not `record_projection()`.** The projection is a digest input,
        and it is not a stored form for four reasons that were checked against
        the code rather than assumed from the name:

        ```text
        1  it omits `record_digest`, because a digest MUST NOT be its own input
           (§17). A stored record must carry that digest, since §17's whole point
           is that a later reader can verify the record with it.
        2  it is flat and keyed by contract leaf paths: `binding.source_kind`,
           where every payload parser reads a nested `binding`.
        3  it spells `payload.reasons[]` with brackets that `DecisionPayload`
           does not read, while `ExecutionPayload` keeps the brackets on
           `tool_calls[]` — so the projection is not the inverse of any parser.
        4  it names its containers `references.context[]`, which is a leaf path
           and not a section name.
        ```

        Reusing the projection would also make the on-disk format a by-product
        of the §15.2 digest table, so a future classification change would
        silently change the storage format and break the round-trip of every
        record already written. §20.4's D3 requires a written record to be
        readable by a future session, so the two are kept separate: §15.2
        decides what is hashed, this decides what is stored, and both are
        complete over the persisted fields.

        JSON is not imported here. This returns a plain mapping of `str`, `int`,
        `bool`, `None`, `list` and `dict`; encoding it to bytes is the Store's
        business, and the package still performs no I/O.
        """
        return {
            "schema_version": self.schema_version,
            "identity": self.identity.to_mapping(),
            "payload": self.payload.to_mapping(),
            "provenance": self.provenance.to_mapping(),
            "references": self.references.to_mapping(),
            "artifacts": self.artifacts.to_mapping(),
            "integrity": self.integrity.to_mapping(),
        }


__all__ = [
    "ADMITTED_EVENTS",
    "EVIDENCE_ID_PREFIX",
    "MAX_TEXT_LENGTH",
    "OBSERVATION_BY_FAMILY",
    "PAYLOAD_BY_KIND",
    "SUPPORTED_SCHEMA_VERSION",
    "Actor",
    "AdmittedEvent",
    "ArtifactRef",
    "Artifacts",
    "CapabilityObservation",
    "ContextRef",
    "DecisionPayload",
    "EvidenceRecord",
    "ExecutionPayload",
    "Identity",
    "Integrity",
    "ProviderBinding",
    "ProviderProbeObservation",
    "Provenance",
    "RecordRef",
    "References",
    "SourceReadObservation",
    "SupersedeRef",
    "ToolCall",
    "WorkspaceBinding",
    "admitted_events_for",
    "check_cross_field",
    "new_evidence_id",
    "observation_payload",
    "value_digest_of",
]


def value_digest_of(value: str) -> str:
    """The `value_digest` of one accepted context value (§12.1, §14.6.1).

    An **identity discriminator**, not a confidentiality mechanism. A
    low-entropy value is brute-forceable from its digest, and that is accepted
    here because the value is workspace document content already referenced by
    identity — no confidentiality is created or lost. A secret never reaches a
    `ContextRef`, because a secret-bearing field is rejected upstream (§14).

    Computed over the canonical JSON form of the string, so a value that could
    collide with a differently-typed serialization cannot.
    """
    return sha256_hex(canonical_json(value))


def new_evidence_id() -> str:
    """A generated, opaque record identity (§8.1).

    Follows AI-04's `decision_id` precedent: a generated runtime identifier that
    is never part of a semantic digest. It is **never content-derived**, so two
    records making the same claim have different ids — they are two observations,
    not one.
    """
    return f"{EVIDENCE_ID_PREFIX}{uuid.uuid4().hex[:16]}"


# --------------------------------------------------------------------------
# shared internals
# --------------------------------------------------------------------------


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecordMalformed(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RecordMalformed(f"{field_name} must be a list")
    return value


def _closed_keys(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    """Refuse a field the contract does not define (§30 step 1)."""
    unknown = set(raw) - allowed
    if unknown:
        raise UnknownField(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}. A field that is silently "
            "dropped cannot be audited (§30), and §13.8 refuses undeclared raw "
            "content rather than reshaping it"
        )


def _required(raw: Mapping[str, Any], name: str, where: str) -> Any:
    if name not in raw or raw[name] is None:
        raise MissingRequiredField(f"{where}.{name} is required")
    return raw[name]


def _enum(value: object, kind: type, field_name: str):
    try:
        return kind(value)
    except ValueError:
        allowed = ", ".join(sorted(member.value for member in kind))
        raise UnsupportedVocabulary(
            f"{field_name}: {value!r} is not one of {allowed}"
        ) from None


# --------------------------------------------------------------------------
# shared internals — the two record-level steps both entry points run
# --------------------------------------------------------------------------


def _schema_version(data: Mapping[str, Any], where: str) -> int:
    """§30 step 2: the record's `schema_version` must be the one this contract defines.

    Shared by the caller parser and the stored loader. Both refuse an
    unsupported version and both refuse it identically, because a vocabulary
    the two disagreed about would be two contracts in one package.
    """
    version = data.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedVocabulary(
            f"{where}.schema_version {version!r} is not supported; this "
            f"contract defines {SUPPORTED_SCHEMA_VERSION}"
        )
    return version


def _parse_payload(kind: EvidenceKind, raw: object, where: str = "payload"):
    """§11: dispatch a payload to the class its kind declares.

    `OBSERVATION` is a typed union whose arm the explicit `family` selects, so
    it goes through `observation_payload`; `DECISION` and `EXECUTION` have one
    payload class each. The kind is passed in rather than re-derived, so the
    caller parser and the stored loader cannot dispatch differently — the
    caller path reads `kind` from the envelope, the stored path from the
    `identity` section, and both arrive here.
    """
    if kind is EvidenceKind.OBSERVATION:
        _family, payload = observation_payload(raw, where)
        return payload
    return PAYLOAD_BY_KIND[kind].from_mapping(raw, where)
