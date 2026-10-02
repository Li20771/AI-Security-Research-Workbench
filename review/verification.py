"""AI-10 §10 — the verification request, and the observation of one.

```text
ASKING for a verification and OBSERVING one are different acts with different
producers. Merging them would record "a check was requested" and "a check ran"
as the same fact — the conflation AI-08 §12.2 refuses for authorization and
AI-06 §8 refuses for execution.
```

### What the request is not

A `VerificationRequest` carries no permission level, no actor, no tool id, no
operation and no command. AI-10 does not infer a permission level from a claim,
an AgentId or a finding — it has none to give, because the invocation is
performed by the controlled verification caller at the composition boundary:

```text
Review -> VerificationRequest -> controlled verification caller
       -> plugins.security_tools.invoke(...) -> AI-04 Guard -> adapter
       -> ToolResult -> VerificationObservation
```

The caller composes the `ToolRequest` and supplies AI-04's `evaluate` to AI-06.
AI-10 never imports `plugins.guard`, never composes a `ToolRequest`, and never
holds a policy, an evaluator or a registry.

### What the observation is not

It is a PROJECTION of an AI-06 execution, in the same shape AI-08's `ToolCallRef`
uses: what ran, what it ended as, and which evaluation decided it. It carries no
stdout, no stderr, no arguments and no environment. `ToolOutcome.COMPLETED` is a
fact about an operation — never "the claim is true".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plugins.security_tools import ToolOutcome

from review.claim import VerificationTarget
from review.errors import InvalidVerification
from review.validation import (
    claim_subject,
    closed_keys,
    identifier,
    mapping,
    refused_keys,
    sequence,
    single_line,
)
from review.vocabulary import MAX_IDENTIFIER_CHARS

__all__ = ["VerificationObservation", "VerificationRequest"]

_TIMESTAMP_MAX = 64

_REQUEST_KEYS = frozenset(
    {"schema_version", "verification_id", "review_case_id", "subject", "targets", "requested_at"}
)

#: Keys a request must never carry. An authorization belongs to the caller's
#: `ToolRequest`, and a second place to put one is a second authorization path.
_REQUEST_REFUSED = frozenset(
    {
        "permission_level",
        "actor",
        "actor_id",
        "tool_id",
        "tool_version",
        "operation",
        "command",
        "arguments",
        "environment",
        "credential",
        "policy",
        "evaluator",
        "registry",
        "timeout",
        "timeout_seconds",
        "runner",
        "adapter",
    }
)

_OBSERVATION_KEYS = frozenset(
    {
        "schema_version",
        "verification_id",
        "review_case_id",
        "subject",
        "outcome",
        "reason_code",
        "tool_id",
        "tool_version",
        "operation",
        "guard_decision_id",
        "guard_reason_code",
        "duration_ms",
        "observed_at",
    }
)

#: Keys an observation must never carry. An observation that absorbed the tool's
#: output would be a second copy of an execution fact, and the review layer is
#: not a store.
_OBSERVATION_REFUSED = frozenset(
    {
        "stdout",
        "stderr",
        "output",
        "outputs",
        "text",
        "raw",
        "raw_result",
        "tool_result",
        "arguments",
        "environment",
        "command",
    }
)


def _timestamp(value: object, where: str, *, allow_empty: bool = False) -> str:
    return single_line(
        value,
        where,
        maximum=_TIMESTAMP_MAX,
        error=InvalidVerification,
        allow_empty=allow_empty,
    )


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    """§10.2. A request. It authorizes nothing and executes nothing."""

    verification_id: str
    review_case_id: str
    subject: str
    targets: tuple[VerificationTarget, ...]
    requested_at: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "verification_id",
            identifier(self.verification_id, "request.verification_id"),
        )
        object.__setattr__(
            self,
            "review_case_id",
            identifier(self.review_case_id, "request.review_case_id"),
        )
        object.__setattr__(
            self,
            "subject",
            claim_subject(self.subject, "request.subject", error=InvalidVerification),
        )
        object.__setattr__(
            self, "requested_at", _timestamp(self.requested_at, "request.requested_at")
        )

        targets = tuple(self.targets)
        if not targets:
            raise InvalidVerification(
                "a verification request names at least one target; a request that "
                "asks for nothing is not a request"
            )
        for target in targets:
            if not isinstance(target, VerificationTarget):
                raise InvalidVerification(
                    "request.targets entries must be VerificationTarget; "
                    f"got {type(target).__name__}"
                )
        target_ids = [target.target_id for target in targets]
        if len(set(target_ids)) != len(target_ids):
            raise InvalidVerification(
                "request.targets is keyed by target_id and a duplicate is refused"
            )
        object.__setattr__(
            self,
            "targets",
            tuple(sorted(targets, key=lambda target: target.target_id)),
        )

        if self.schema_version != 1:
            raise InvalidVerification(
                f"request.schema_version {self.schema_version!r} is not supported; "
                "this contract defines 1"
            )

    @classmethod
    def from_mapping(cls, raw: object) -> "VerificationRequest":
        data = mapping(raw, "request")
        refused_keys(
            data,
            _REQUEST_REFUSED,
            "request",
            "A verification request names what could be checked and nothing "
            "more. An actor, a permission level, a tool and a command belong to "
            "the controlled verification caller, which composes the ToolRequest "
            "(§10.2, §11.2).",
            error=InvalidVerification,
        )
        closed_keys(data, _REQUEST_KEYS, "request", error=InvalidVerification)
        if data.get("schema_version") != 1:
            raise InvalidVerification(
                f"request.schema_version {data.get('schema_version')!r} is not "
                "supported; this contract defines 1"
            )
        targets = tuple(
            VerificationTarget.from_mapping(entry, "request.targets[]")
            for entry in sequence(data.get("targets", []), "request.targets", error=InvalidVerification)
        )
        return cls(
            verification_id=data.get("verification_id"),
            review_case_id=data.get("review_case_id"),
            subject=data.get("subject"),
            targets=targets,
            requested_at=data.get("requested_at"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "verification_id": self.verification_id,
            "review_case_id": self.review_case_id,
            "subject": self.subject,
            "targets": [target.to_mapping() for target in self.targets],
            "requested_at": self.requested_at,
        }


@dataclass(frozen=True, slots=True)
class VerificationObservation:
    """§10.3. What a verification invocation did, as reported back."""

    verification_id: str
    review_case_id: str
    subject: str
    outcome: ToolOutcome
    reason_code: str = ""
    tool_id: str = ""
    tool_version: str = ""
    operation: str = ""
    guard_decision_id: str = ""
    guard_reason_code: str = ""
    duration_ms: int | None = None
    observed_at: str = ""
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "verification_id",
            identifier(self.verification_id, "observation.verification_id"),
        )
        object.__setattr__(
            self,
            "review_case_id",
            identifier(self.review_case_id, "observation.review_case_id"),
        )
        object.__setattr__(
            self,
            "subject",
            claim_subject(self.subject, "observation.subject", error=InvalidVerification),
        )

        try:
            outcome = ToolOutcome(self.outcome)
        except ValueError as exc:
            raise InvalidVerification(
                "observation.outcome must be one of AI-06's ToolOutcome members; "
                f"got {self.outcome!r}"
            ) from exc
        object.__setattr__(self, "outcome", outcome)

        for name, maximum in (
            ("reason_code", MAX_IDENTIFIER_CHARS),
            ("tool_id", MAX_IDENTIFIER_CHARS),
            ("tool_version", MAX_IDENTIFIER_CHARS),
            ("operation", MAX_IDENTIFIER_CHARS),
            ("guard_reason_code", MAX_IDENTIFIER_CHARS),
        ):
            object.__setattr__(
                self,
                name,
                single_line(
                    getattr(self, name),
                    f"observation.{name}",
                    maximum=maximum,
                    error=InvalidVerification,
                    allow_empty=True,
                ),
            )

        # An empty decision id is AI-06's own signal that no evaluation happened
        # (a refusal raised before the Guard boundary). It is not a missing
        # value to be filled in, and it is not UNKNOWN or BLOCKED.
        object.__setattr__(
            self,
            "guard_decision_id",
            identifier(self.guard_decision_id, "observation.guard_decision_id")
            if self.guard_decision_id
            else "",
        )

        if self.duration_ms is not None:
            if isinstance(self.duration_ms, bool) or not isinstance(self.duration_ms, int):
                raise InvalidVerification("observation.duration_ms must be whole milliseconds")
            if self.duration_ms < 0:
                raise InvalidVerification("observation.duration_ms must be >= 0")

        object.__setattr__(
            self,
            "observed_at",
            _timestamp(self.observed_at, "observation.observed_at", allow_empty=True),
        )

        if self.schema_version != 1:
            raise InvalidVerification(
                f"observation.schema_version {self.schema_version!r} is not "
                "supported; this contract defines 1"
            )

    @property
    def evaluated(self) -> bool:
        """Whether Guard actually evaluated this invocation (§10.3).

        A false value means AI-06 refused the request before the authorization
        boundary and no decision exists. Nothing may be inferred from the
        absence beyond that.
        """
        return bool(self.guard_decision_id)

    @classmethod
    def from_mapping(cls, raw: object) -> "VerificationObservation":
        data = mapping(raw, "observation")
        refused_keys(
            data,
            _OBSERVATION_REFUSED,
            "observation",
            "An observation is a projection of an AI-06 execution and carries no "
            "tool output, no arguments and no environment. AI-06's ToolResult "
            "remains the execution fact and is not absorbed (§10.3).",
            error=InvalidVerification,
        )
        closed_keys(data, _OBSERVATION_KEYS, "observation", error=InvalidVerification)
        if data.get("schema_version") != 1:
            raise InvalidVerification(
                f"observation.schema_version {data.get('schema_version')!r} is not "
                "supported; this contract defines 1"
            )
        return cls(
            verification_id=data.get("verification_id"),
            review_case_id=data.get("review_case_id"),
            subject=data.get("subject"),
            outcome=data.get("outcome"),
            reason_code=data.get("reason_code", ""),
            tool_id=data.get("tool_id", ""),
            tool_version=data.get("tool_version", ""),
            operation=data.get("operation", ""),
            guard_decision_id=data.get("guard_decision_id", ""),
            guard_reason_code=data.get("guard_reason_code", ""),
            duration_ms=data.get("duration_ms"),
            observed_at=data.get("observed_at", ""),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "verification_id": self.verification_id,
            "review_case_id": self.review_case_id,
            "subject": self.subject,
            "outcome": str(self.outcome),
            "reason_code": self.reason_code,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "operation": self.operation,
            "guard_decision_id": self.guard_decision_id,
            "guard_reason_code": self.guard_reason_code,
            "duration_ms": self.duration_ms,
            "observed_at": self.observed_at,
        }
