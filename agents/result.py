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
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools.vocabulary import ToolOutcome

from agents.vocabulary import AgentId, resolve_agent

__all__ = [
    "AgentExecutionOutcome",
    "AgentResult",
    "InvalidResultReference",
    "RESULT_REFERENCE_GRAMMAR",
    "ToolCallRef",
    "is_valid_result_reference",
    "result_digest",
]

#: §10.2, v1 shape. A `result` is a terminal result **reference or digest** and
#: never raw content, so the field admits exactly two shapes and nothing else:
#:
#: ```text
#: sha256:<64 lowercase hex>        a content digest
#: ref:<opaque reference token>     a reference, token restricted to
#:                                  [A-Za-z0-9._:-], no whitespace, no CR,
#:                                  no LF, no '='
#: ```
#:
#: ### What this is, and what it is NOT
#:
#: ```text
#: IS      a structural result-shape guarantee: obvious raw-content forms —
#:         multi-line text, `KEY=value` assignments, prose, quotes, spaces —
#:         cannot be stored in AgentResult.result at all.
#: IS NOT  a universal secret-content classifier. A single-line secret that
#:         happens to match the token charset would still pass.
#: ```
#:
#: The complete answer to "is this value content-free" is a *published admission
#: rule set over bounded-source fields*, which is AI-05's deferred **C-1**.
#: AI-08 does not become a content scanner to cover a gap another phase owns;
#: it enforces the shape its own contract states and says plainly where the
#: guarantee stops.
RESULT_REFERENCE_GRAMMAR: tuple[str, ...] = (
    r"^sha256:[0-9a-f]{64}$",
    r"^ref:[A-Za-z0-9._:-]{1,480}$",
)

_RESULT_PATTERNS = tuple(re.compile(pattern) for pattern in RESULT_REFERENCE_GRAMMAR)


class InvalidResultReference(ValueError):
    """§10.2. A `result` that is not a v1 reference or digest.

    Raised at construction rather than at serialisation: a value that failed the
    shape rule must never reach an AgentResult, because the record is what a
    reader would later take at face value.
    """

    reason_code = "INVALID_RESULT_REFERENCE"


def is_valid_result_reference(value: object) -> bool:
    """Whether `value` has one of the two v1 `result` shapes."""
    if not isinstance(value, str):
        return False
    return any(pattern.match(value) is not None for pattern in _RESULT_PATTERNS)


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

    The outcome is **AI-06's own member**, imported and carried, never
    reinterpreted. `what_ran` is spelled the way AI-06 spells it, so the
    reference names the same operation AI-06 ran.

    ### `guard_decision` is `None` when Guard never ran (Amendment 3)

    ```text
    guard_decision is a GuardDecision   the invocation was GUARD-BOUND: it
                                        reached the Guard boundary and an
                                        evaluation produced this decision.
    guard_decision is None              the invocation was a PRE-GUARD REFUSAL:
                                        AI-06 refused it before the boundary, so
                                        there is no decision to carry.
    ```

    `decision_id` is empty in exactly the second case, and `was_evaluated` reads
    it.

    This is not a reinterpretation of AI-06. AI-06's `unattributed_summary`
    supplies a fallback `decision` value **and** an empty `decision_id`, and says
    of the pair that no evaluation produced one — the empty id is AI-06's own
    signal. Carrying the fallback word as a `GuardDecision` would record "no
    evaluation occurred" as "an evaluation returned BLOCKED", which are two
    different facts (§12.2).
    """

    ordinal: int
    tool_id: str
    tool_version: str
    operation: str
    outcome: ToolOutcome
    guard_decision: GuardDecision | None
    guard_decision_id: str
    guard_reason_code: str
    duration_ms: int | None = None

    @property
    def what_ran(self) -> str:
        return f"{self.tool_id}/{self.operation}"

    @property
    def was_evaluated(self) -> bool:
        """Whether Guard actually evaluated this invocation (§12.2)."""
        return bool(self.guard_decision_id)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "what_ran": self.what_ran,
            "tool_version": self.tool_version,
            "outcome": str(self.outcome),
            "guard": {
                # `None` is the truthful value for a pre-Guard refusal, and it
                # serialises as null rather than as a word that would claim an
                # evaluation happened.
                "decision": None if self.guard_decision is None else str(self.guard_decision),
                "decision_id": self.guard_decision_id,
                "reason_code": self.guard_reason_code,
                "evaluated": self.was_evaluated,
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

    agent_id: AgentId
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

    def __post_init__(self) -> None:
        """Enforce the two invariants this type is *for* (§10, §10.2).

        **Identity.** `agent_id` is declared `AgentId` and now really is one.
        It was declared `str` before, which meant a result could carry
        `'not-registered'` as its declared identity and nothing objected. It is
        resolved through the same `resolve_agent` boundary the request uses, so
        there is no second identity rule here either.

        **Result shape.** `result` must be a reference or a digest. Until this
        existed the invariant was caller convention only: a body returning
        `BodyOutcome(result_ref="AWS_SECRET=...\\nraw task body")` had the whole
        string written into a COMPLETED AgentResult verbatim. Now the record
        cannot be built from it — see `RESULT_REFERENCE_GRAMMAR` for exactly how
        far that guarantee reaches, and where it stops.
        """
        object.__setattr__(self, "agent_id", resolve_agent(self.agent_id))
        if not is_valid_result_reference(self.result):
            raise InvalidResultReference(
                f"result must be a terminal result reference or digest and is "
                f"neither (§10.2). Admitted shapes: "
                f"{' | '.join(RESULT_REFERENCE_GRAMMAR)}. Raw model output, a "
                "prompt body, a task body and tool arguments are not "
                "references, and a failure record is not a place where the raw "
                "content that caused the failure becomes storable"
            )

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
