"""AI-08 §9 — structural independence, and what it does not prove.

```text
I1  identity separation            distinct registered AgentIds
I2  execution separation           distinct opaque ExecutionIds, neither derived
I3  input separation               neither Agent's result is the other's input
I4  context separation             each execution owns its own ContextResponse
I5  tool authorization separation  fresh GuardRequest + GuardDecision per call
I6  result separation              two results, neither carrying the other
I7  failure separation             neither outcome derives from the other's
I8  provenance separation          each result names its own agent and execution
```

### What this proves, and what it must never be read as

```text
CAN establish    two registered identities, two execution instances, separate
                 inputs, separate contexts, separate Guard decision sets,
                 separate results, separate provenance

CANNOT establish that two models are cognitively independent; that neither was
                 influenced by similar training data; that either conclusion is
                 correct; that two agreeing results make a fact true
```

```text
FROZEN: structural independence MUST NOT be written, recorded or read as truth
        verification, as a PASS, as a verdict, or as a correctness claim (§9.2).
FROZEN: AgentRole.INDEPENDENT_SECOND is NOT a finding. The role alone never
        satisfies I1-I8; independence is a property of an execution PAIR and of
        nothing else (§5.2.1).
FROZEN: agreement between two Agents is NOT verification. AI-00 §13 forbids
        "两边一致所以一定正确" and "模型置信度最高所以通过" by name.
```

### I3 is structural as well as checked

`AgentExecutionRequest` has no field that can hold an `AgentResult` — that is
asserted directly against the dataclass in the test matrix, so I3's first line of
defence is the request shape rather than a runtime check that could be skipped.
The predicate below is the second line: it refuses a pair whose declared
descriptors name the other execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from plugins.context import ContextResponse

from agents.request import AgentExecutionRequest
from agents.result import AgentResult
from agents.vocabulary import AgentId

__all__ = [
    "I1_IDENTITY",
    "I2_EXECUTION",
    "I3_INPUT",
    "I4_CONTEXT",
    "I5_TOOL_AUTHORIZATION",
    "I6_RESULT",
    "I7_FAILURE",
    "I8_PROVENANCE",
    "INDEPENDENCE_CONDITIONS",
    "ExecutionRecord",
    "IndependenceFinding",
    "structural_independence",
]

I1_IDENTITY = "I1_IDENTITY_SEPARATION"
I2_EXECUTION = "I2_EXECUTION_SEPARATION"
I3_INPUT = "I3_INPUT_SEPARATION"
I4_CONTEXT = "I4_CONTEXT_SEPARATION"
I5_TOOL_AUTHORIZATION = "I5_TOOL_AUTHORIZATION_SEPARATION"
I6_RESULT = "I6_RESULT_SEPARATION"
I7_FAILURE = "I7_FAILURE_SEPARATION"
I8_PROVENANCE = "I8_PROVENANCE_SEPARATION"

#: Stable labels, in contract order.
INDEPENDENCE_CONDITIONS: tuple[str, ...] = (
    I1_IDENTITY,
    I2_EXECUTION,
    I3_INPUT,
    I4_CONTEXT,
    I5_TOOL_AUTHORIZATION,
    I6_RESULT,
    I7_FAILURE,
    I8_PROVENANCE,
)


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """Everything one execution produced, kept together.

    A record is the unit the predicate ranges over: a request with no result is
    not a completed execution, and a result with no context cannot be checked
    for I4. Holding them together is what makes "which context did *this*
    execution establish" answerable rather than assumed.

    `context` is `None` for a `BLOCKED` execution whose body never started —
    there is no context to hold, because establishing one is exactly what did
    not happen (§11.1). A record is not a claim that an execution ran; it is a
    claim about what it produced, and a blocked execution produces a result and
    no context.
    """

    request: AgentExecutionRequest
    result: AgentResult
    context: ContextResponse | None = None


@dataclass(frozen=True, slots=True)
class IndependenceFinding:
    """The outcome of the I1-I8 predicate. **A finding, never a verdict.**

    It says which structural conditions hold between two executions. It says
    nothing about whether either result is right, and nothing about whether the
    task succeeded — `satisfied` reaching all eight is not a `PASS` and must
    never be recorded as one (§9.2).
    """

    satisfied: tuple[str, ...]
    violated: tuple[str, ...]

    @property
    def independent(self) -> bool:
        """Whether all eight structural conditions hold.

        A true value means *these two executions are structurally separate*.
        It does **not** mean the two Agents agreed, and it does not mean either
        is correct.
        """
        return not self.violated

    def to_mapping(self) -> dict[str, Any]:
        return {
            "independent": self.independent,
            "conditions": list(INDEPENDENCE_CONDITIONS),
            "satisfied": list(self.satisfied),
            "violated": list(self.violated),
        }


def _descriptor_texts(request: AgentExecutionRequest) -> Iterable[str]:
    """Every caller-supplied descriptor on a request, as text.

    Used by I3 and I7: a cross-reference between two executions has to be
    written down somewhere, and these are the only places a request can write
    anything down.
    """
    yield request.task
    yield request.input_digest
    if request.context_descriptor is not None:
        yield request.context_descriptor


def _mentions(values: Iterable[str], needle: str) -> bool:
    return bool(needle) and any(needle in value for value in values)


def _result_texts(result: AgentResult) -> Iterable[str]:
    yield result.result
    yield result.reason_code
    if result.blocking is not None:
        yield result.blocking


def _duplicate_decision_ids(records: tuple[ExecutionRecord, ...]) -> tuple[str, ...]:
    """Guard decision ids reused across the pair.

    An **empty** `decision_id` is not a reuse. AI-06 leaves it empty for an
    invocation that never reached Guard at all — an unknown tool, a bad
    argument, a v1 target refusal — and saying "no evaluation decided this" is
    more honest than inventing an identifier. Two such invocations sharing the
    empty string are two invocations that were both refused before evaluation,
    not one decision used twice.
    """
    seen: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        for decision_id in record.result.tool_call_ids():
            if not decision_id:
                continue
            if decision_id in seen and decision_id not in duplicates:
                duplicates.append(decision_id)
            seen.add(decision_id)
    return tuple(duplicates)


def structural_independence(
    left: ExecutionRecord, right: ExecutionRecord
) -> IndependenceFinding:
    """The I1-I8 predicate over one execution pair (§9.1).

    Symmetric: `structural_independence(a, b)` and `(b, a)` agree, because every
    condition is stated as a relation between the two rather than as a property
    of one of them.
    """
    satisfied: list[str] = []
    violated: list[str] = []

    def check(condition: str, holds: bool) -> None:
        (satisfied if holds else violated).append(condition)

    left_agent = str(left.request.agent_id)
    right_agent = str(right.request.agent_id)
    left_execution = left.result.execution_id
    right_execution = right.result.execution_id

    # I1 — distinct registered identities.
    #
    # Membership is tested against the members' VALUES, not against `set(AgentId)`.
    # `AgentResult.agent_id` is a plain string, and `Enum.__hash__` hashes the
    # member NAME, so `"dsh" in set(AgentId)` is False even though
    # `AgentId.DSH == "dsh"`. Testing the wrong one made every pair unsatisfiable
    # on I1 — a finding no execution could clear, which is the kind of defect
    # that reads as a passing check until a pair is actually compared.
    registered_agent_ids = {member.value for member in AgentId}
    check(
        I1_IDENTITY,
        left_agent != right_agent
        and left_agent in registered_agent_ids
        and right_agent in registered_agent_ids,
    )

    # I2 — distinct opaque execution ids, neither derived from the other and
    # neither encoding its own Agent (which would make the id a second identity
    # claim, and an id that names its agent is not opaque — §7.2).
    check(
        I2_EXECUTION,
        bool(left_execution)
        and bool(right_execution)
        and left_execution != right_execution
        and left_execution not in right_execution
        and right_execution not in left_execution
        and left_agent not in left_execution
        and right_agent not in right_execution,
    )

    # I3 — neither result is the other's input. The key v1 boundary.
    check(
        I3_INPUT,
        not _mentions(_descriptor_texts(left.request), right_execution)
        and not _mentions(_descriptor_texts(left.request), right.result.result)
        and not _mentions(_descriptor_texts(right.request), left_execution)
        and not _mentions(_descriptor_texts(right.request), left.result.result),
    )

    # I4 — each execution owns its own ContextResponse, and each result's
    # workspace is the one its own execution read. An execution that never
    # established one cannot satisfy this: "each owns its own" is false when
    # there is nothing to own.
    check(
        I4_CONTEXT,
        left.context is not None
        and right.context is not None
        and left.context is not right.context
        and left.context.workspace.workspace_id == left.result.workspace_id
        and right.context.workspace.workspace_id == right.result.workspace_id,
    )

    # I5 — no Guard decision is reused across the pair. NOT about digests:
    # §9.1.1 forbids requiring `request_digest` uniqueness, and two identical
    # requests legitimately produce equal digests.
    check(I5_TOOL_AUTHORIZATION, not _duplicate_decision_ids((left, right)))

    # I6 — two results, neither carrying the other.
    check(
        I6_RESULT,
        left.result is not right.result
        and left_execution not in _result_texts(right.result)
        and right_execution not in _result_texts(left.result),
    )

    # I7 — neither outcome derives from the other's. A converted outcome would
    # have to name the execution it was converted from.
    check(
        I7_FAILURE,
        not _mentions(_result_texts(left.result), right_execution)
        and not _mentions(_result_texts(right.result), left_execution),
    )

    # I8 — each result names its own Agent and its own execution.
    check(
        I8_PROVENANCE,
        left.result.agent_id == left_agent
        and right.result.agent_id == right_agent
        and bool(left.result.execution_id)
        and bool(right.result.execution_id),
    )

    return IndependenceFinding(satisfied=tuple(satisfied), violated=tuple(violated))
