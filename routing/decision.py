"""The RouterDecision. Contract §10, §13.3.

An auditable record of **one** evaluation. It describes descriptors only: no
prompt, no message, no tool argument, no credential, no provider payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from routing.vocabulary import RoutingOutcome

__all__ = ["RouterDecision"]


@dataclass(frozen=True, slots=True)
class RouterDecision:
    """§13.3. One evaluation, one decision.

    ```text
    FROZEN: a RouterDecision describes exactly ONE evaluation. It carries no
            `fallbacks` and no nested decision.
    ```

    A later, caller-submitted request produces another decision. The relationship
    between two decisions is external correlation metadata, not an execution or
    retry mechanism owned by AI-07 (§9).
    """

    decision_id: str
    decided_at: str
    outcome: RoutingOutcome
    reason_code: str
    rules_revision: str
    requested: Mapping[str, Any] = field(default_factory=dict)
    matched_rule: str | None = None
    candidates: tuple[str, ...] = ()
    selected: str | None = None
    agent_hint: str | None = None
    schema_version: int = 1

    @property
    def selected_nothing(self) -> bool:
        return self.selected is None

    def to_mapping(self) -> dict[str, Any]:
        """The audit record, as an **explicit allowlist**.

        `dataclasses.asdict` would put every field into the record, so a field
        added later would reach an auditable artefact without anyone deciding it
        should (§13.3, §23 of the brief).
        """
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "decided_at": self.decided_at,
            "outcome": str(self.outcome),
            "reason_code": self.reason_code,
            "requested": dict(self.requested),
            "matched_rule": self.matched_rule,
            "candidates": list(self.candidates),
            "selected": self.selected,
            "agent_hint": self.agent_hint,
            "rules_revision": self.rules_revision,
        }

    def semantic_content(self) -> dict[str, Any]:
        """The part of the decision that must be deterministic (§28 of the brief).

        `decision_id` and `decided_at` are excluded, and are not a determinism
        violation: they are new audit identifiers rather than semantics. Two
        evaluations of the same request against the same rule set and the same
        registry must agree on everything this returns.
        """
        record = self.to_mapping()
        record.pop("decision_id")
        record.pop("decided_at")
        return record
