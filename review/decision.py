"""AI-10 §12 — the human decision: human-supplied, run-scoped.

```text
HumanDecision is an ACT, not an outcome about the world.
ACCEPTED does not mean the material is right.
REJECTED does not mean any claim is false.
DEFERRED does not close anything.
```

### What is enforced, and where the enforcement stops

Enforced here:

```text
there is no default decision, and no constructor path that omits one
a machine-origin field (model, generated, predicted, recommended, confidence,
  score, rank, votes) is REFUSED BY NAME when a decision is parsed
the actor is a bounded human identifier and is refused if it is an AgentId —
  an Agent does not decide
no module in review/ derives a decision from a finding, a material or a
  comparison; the only way one exists is that a caller supplied it
```

Not enforced, and stated plainly rather than implied: v1 does NOT authenticate
that a human typed it. There is no human identity registry in this repository —
AI-08 §5.4's rule that identity is registered, never discovered, is not being
quietly reversed here. `actor_id` is a DECLARED identifier, exactly as a
material's attribution is declared, and §12.3 says so.

### Storage status

Run data. A durable human decision requires an AI-05 amendment (§13.4 C), and
AI-10 writes no EvidenceRecord in v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.vocabulary import AgentId

from review.errors import InvalidDecision
from review.validation import (
    bounded_text,
    closed_keys,
    identifier,
    mapping,
    refused_keys,
    single_line,
)
from review.vocabulary import MAX_RATIONALE_CHARS, HumanDecisionKind

__all__ = ["HumanDecision"]

_TIMESTAMP_MAX = 64

_DECISION_KEYS = frozenset(
    {
        "schema_version",
        "decision_id",
        "review_case_id",
        "actor_id",
        "decision",
        "rationale",
        "recorded_at",
    }
)

#: Keys that would mean the decision was not a human's. Refused by name so the
#: refusal says why, rather than "unknown field".
_MACHINE_ORIGIN_KEYS = frozenset(
    {
        "model",
        "model_id",
        "agent",
        "generated",
        "generated_by",
        "auto",
        "automatic",
        "machine",
        "predicted",
        "suggested",
        "confidence",
        "score",
        "rank",
        "weight",
        "probability",
        "correctness",
        "winner",
        "best_agent",
        "recommendation",
        "recommended",
        "vote",
        "votes",
        "majority",
    }
)


@dataclass(frozen=True, slots=True)
class HumanDecision:
    """§12.1. One human's decision about one review case.

    ```text
    FROZEN (§12.3): a decision is recorded as an ACT, "with its rationale and its
    time". `recorded_at` therefore carries the same weight as `decision`: this
    type refuses an absent or empty one, and it NEVER supplies a time of its own.
    There is no clock here, no default and no automatic fill — a decision whose
    time AI-10 invented would be a decision AI-10 partly authored.

    `rationale` is bounded (§12.1) and may be empty. §12.3's phrase is not read
    here as adding a non-empty requirement the field list does not state; widening
    it is a contract question, not an implementation one.
    ```
    """

    decision_id: str
    review_case_id: str
    actor_id: str
    decision: HumanDecisionKind
    rationale: str = ""
    recorded_at: str = ""
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "decision_id",
            identifier(self.decision_id, "decision.decision_id"),
        )
        object.__setattr__(
            self,
            "review_case_id",
            identifier(self.review_case_id, "decision.review_case_id"),
        )

        actor_id = identifier(self.actor_id, "decision.actor_id")
        if actor_id in {member.value for member in AgentId}:
            raise InvalidDecision(
                f"decision.actor_id {actor_id!r} is a registered Agent identity. "
                "An Agent does not decide: the decision is a human act, and an "
                "AgentId here would be a machine-made decision wearing a human "
                "label (§12.3)"
            )
        object.__setattr__(self, "actor_id", actor_id)

        try:
            decision = HumanDecisionKind(self.decision)
        except ValueError as exc:
            raise InvalidDecision(
                f"decision.decision must be one of "
                f"{[member.value for member in HumanDecisionKind]}; got "
                f"{self.decision!r}"
            ) from exc
        object.__setattr__(self, "decision", decision)

        object.__setattr__(
            self,
            "rationale",
            bounded_text(
                self.rationale,
                "decision.rationale",
                maximum=MAX_RATIONALE_CHARS,
                error=InvalidDecision,
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "recorded_at",
            single_line(
                self.recorded_at,
                "decision.recorded_at",
                maximum=_TIMESTAMP_MAX,
                error=InvalidDecision,
            ),
        )

        if self.schema_version != 1:
            raise InvalidDecision(
                f"decision.schema_version {self.schema_version!r} is not "
                "supported; this contract defines 1"
            )

    @classmethod
    def from_mapping(cls, raw: object) -> "HumanDecision":
        data = mapping(raw, "decision")
        refused_keys(
            data,
            _MACHINE_ORIGIN_KEYS,
            "decision",
            "A human decision records a human act. A model-generated, predicted, "
            "voted or recommended value is not one, and AI-10 never derives a "
            "decision from a finding or a comparison (§12.3).",
            error=InvalidDecision,
        )
        closed_keys(data, _DECISION_KEYS, "decision", error=InvalidDecision)
        if data.get("schema_version") != 1:
            raise InvalidDecision(
                f"decision.schema_version {data.get('schema_version')!r} is not "
                "supported; this contract defines 1"
            )
        recorded_at = data.get("recorded_at")
        if recorded_at is None:
            raise InvalidDecision(
                "decision.recorded_at is required: §12.3 records a decision as an "
                "act, with its time, and AI-10 never supplies a time of its own"
            )
        return cls(
            decision_id=data.get("decision_id"),
            review_case_id=data.get("review_case_id"),
            actor_id=data.get("actor_id"),
            decision=data.get("decision"),
            rationale=data.get("rationale", ""),
            recorded_at=recorded_at,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "review_case_id": self.review_case_id,
            "actor_id": self.actor_id,
            "decision": str(self.decision),
            "rationale": self.rationale,
            "recorded_at": self.recorded_at,
        }
