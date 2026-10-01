"""AI-08 §10, §11 — the terminal result and the execution outcome.

**Owner: AI-08.** One agent-level result type, and it restates nothing.

```text
FROZEN: AgentResult is NOT InvocationResult   (AI-02)
        AgentResult is NOT ToolOutcome        (AI-06)
        AgentResult is NOT RoutingOutcome     (AI-07)
        AgentResult is NOT StatusValue        (AI-03)
        AgentResult is NOT GuardDecision      (AI-04)
```

It *references* those results; it does not absorb them (§10).

```text
FROZEN: AgentResult is run data. It is NOT an AI-05 EvidenceRecord, and v1
        writes no EvidenceRecord at all (§13.1).
FROZEN: AgentResult carries no raw model output, no prompt body, no task body,
        no tool argument and no credential — for ANY outcome (§10.2).
```
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools.vocabulary import ToolOutcome

__all__ = [
    "AgentExecutionOutcome",
    "AgentResult",
    "ToolCallRef",
    "result_digest",
]


class AgentExecutionOutcome(StrEnum):
    """§11. AI-08's own terminal outcome vocabulary. Closed, exactly three. FROZEN.

    ```text
    COMPLETED   the execution reached a terminal AgentResult representing a
                completed Agent execution
    FAILED      the Agent execution STARTED but failed to produce a valid task
                result; the runtime STILL produces exactly one terminal
                AgentResult describing the failure
    BLOCKED     an EXECUTION-LEVEL precondition prevented the Agent execution
                from STARTING; the controller STILL produces exactly one
                terminal AgentResult describing the blocking condition
    ```

    **All three terminate in exactly one `AgentResult` (§7.1.1).** `FAILED` and
    `BLOCKED` describe what the execution *body* did or did not do; neither
    means "no AgentResult exists".

    `BLOCKED` appears in `GuardDecision`, in `StatusValue` and in `ToolOutcome`
    too. That is the known cost AI-07 §10.1 recorded, and AI-08 does not remove
    it by merging the types. §11.2 is how the collision is kept from becoming a
    conflation: `ToolOutcome.BLOCKED` is NOT `AgentExecutionOutcome.BLOCKED`.
    """

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ToolCallRef:
    """§10. One tool invocation, as the AgentResult references it.

    The outcome and the decision are **AI-06's and AI-04's own members**,
    imported and carried, never reinterpreted. `what_ran` is spelled the way
    AI-06 spells it, so the reference names the same operation AI-06 ran.

    `guard_decision_id` is the attribution of the evaluation that decided this
    invocation. It is what makes I5 checkable: two invocations carry two
    decisions from two evaluations, and nothing is reused.
    """

    ordinal: int
    tool_id: str
    tool_version: str
    operation: str
    outcome: ToolOutcome
    guard_decision: GuardDecision
    guard_decision_id: str
    guard_reason_code: str
    duration_ms: int | None = None

    @property
    def what_ran(self) -> str:
        return f"{self.tool_id}/{self.operation}"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "what_ran": self.what_ran,
            "tool_version": self.tool_version,
            "outcome": str(self.outcome),
            "guard": {
                "decision": str(self.guard_decision),
                "decision_id": self.guard_decision_id,
                "reason_code": self.guard_reason_code,
            },
            "duration_ms": self.duration_ms,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """§10. What one execution terminated with.

    ```text
    FROZEN: exactly one AgentResult terminates one execution, for ALL THREE
            outcomes (§7.1.1).
    FROZEN: `result` is present on every outcome. For FAILED and BLOCKED it
            refers to the terminal failure or block metadata rather than to a
            task result, and it MUST NOT be read as implying a task result
            exists (§10.2).
    FROZEN: AgentResult is a CLAIM WITH A PRODUCER — it records that an
            execution happened and what it ended as. It is NOT a verdict about
            the task, NOT a PASS, NOT VERIFIED (§10, §11.3).
    FROZEN: attribution is `agent_id` + `execution_id` and nothing else. There
            is no AI-05 producer field here (§10.1).
    ```

    `workspace_id` is empty exactly when the execution never reached a usable
    workspace — which is one of the `BLOCKED` preconditions (§11.1). It is never
    a fabricated scope: an empty scope is what Guard already treats as
    unauthorized, and inventing one would be worse than the honest blank.
    """

    agent_id: str
    execution_id: str
    workspace_id: str
    input_digest: str
    outcome: AgentExecutionOutcome
    result: str
    tool_calls: tuple[ToolCallRef, ...] = ()
    started_at: str = ""
    duration_ms: int = 0
    reason_code: str = ""
    blocking: str | None = None
    schema_version: int = 1

    # -- properties --------------------------------------------------------

    @property
    def completed(self) -> bool:
        """Whether the execution reached a terminal result.

        Deliberately **not** named `passed` or `succeeded`: `COMPLETED` is not
        `PASS`, not `VERIFIED`, not `CORRECT` and not task success (§11.3), and
        a property name is where that distinction gets lost first.
        """
        return self.outcome is AgentExecutionOutcome.COMPLETED

    @property
    def digest(self) -> str:
        """The result's semantic digest (§10).

        Excludes timing: `started_at` and `duration_ms` are operational, not
        semantic, in the same split AI-05 §14.6 draws. Two runs of one
        execution's semantics agree on this value; the ids and the timing are
        what differ.
        """
        return result_digest(self)

    # -- projection --------------------------------------------------------

    def semantic_content(self) -> dict[str, Any]:
        """Everything the digest covers. An **explicit allowlist**."""
        return {
            "schema_version": self.schema_version,
            "agent_id": str(self.agent_id),
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "input_digest": self.input_digest,
            "outcome": str(self.outcome),
            "result": self.result,
            "reason_code": self.reason_code,
            "blocking": self.blocking,
            "tool_calls": [call.to_mapping() for call in self.tool_calls],
        }

    def to_mapping(self) -> dict[str, Any]:
        """The audit projection, as an **explicit allowlist**.

        `dataclasses.asdict` would put every field into a record, so a field
        added later would reach an auditable artefact without anyone deciding it
        should — the rule AI-04 §13.3 and AI-07 §13.3 already state for their own
        records. This is `semantic_content()` plus the operational fields the
        digest deliberately excludes.
        """
        record = self.semantic_content()
        record["started_at"] = self.started_at
        record["duration_ms"] = self.duration_ms
        record["digest"] = self.digest
        return record

    def tool_call_ids(self) -> tuple[str, ...]:
        """Every Guard decision id this execution ran under.

        I5's raw material: the invocations this execution authorized, each with
        the evaluation that decided it.
        """
        return tuple(call.guard_decision_id for call in self.tool_calls)


def result_digest(result: AgentResult) -> str:
    """The digest over a result's semantic content.

    A local three-line function rather than an import from AI-04's or AI-05's
    digest module: those compute digests over *their* frozen projections, and
    reaching into one for a generic hash would make AI-08 depend on a
    projection it does not own.
    """
    payload = _canonical_json(result.semantic_content())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
