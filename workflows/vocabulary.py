"""AI-13 §14 — AI-13's own vocabulary. Closed.

```text
FROZEN: AI-13 MUST NOT add a member to another phase's vocabulary. In particular it
        MUST NOT add to GuardDecision (ALLOW/DENY/BLOCKED/UNKNOWN), to AI-04 §18.2's
        CheckResult, to AI-05's admission vocabulary, to StatusValue, to
        AgentExecutionOutcome, or to AI-05's Evidence kinds and tiers.
```

`BLOCKED` appears in several of those and in one member below. The repository already
pays for one word in several vocabularies and does not merge the types to save the
cost — `workflows.vocabulary.WorkflowState.BLOCKED` is not
`AgentExecutionOutcome.BLOCKED` and not `GuardDecision.BLOCKED`, and no value is ever
passed between them without an explicit classification.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "FAILURE_CLASSES",
    "NEVER_RETRIED",
    "TERMINAL_STATES",
    "FailureClass",
    "StepState",
    "WorkflowState",
]


class WorkflowState(StrEnum):
    """§14. The run's own state. Closed.

    Every member is terminal or has a declared transition out of it, and none is both.
    `TERMINAL_STATES` below is the frozen partition.

    `AWAITING_APPROVAL` is a member because §14 names it, and AI-13-B NEVER sets it: a
    definition declaring an approval step is refused before a run exists (§18), so no
    run can reach it until AI-13-C implements the gate. It is defined here rather than
    left for C to add, because §20 lists AI-13's vocabulary among the things an
    amendment is required to change — a phase that had to ADD a member to this enum
    would be amending a frozen vocabulary to finish its own work.
    """

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    # The three a resume can refuse with (§8.1). They are states rather than errors
    # because each is a fact about the RUN that a reader must be able to see.
    DEFINITION_CHANGED = "DEFINITION_CHANGED"
    WORKSPACE_CHANGED = "WORKSPACE_CHANGED"
    CHECKPOINT_CORRUPT = "CHECKPOINT_CORRUPT"


class StepState(StrEnum):
    """§14. One step's state. Closed.

    `AWAITING_APPROVAL` is a member because the contract names it, and AI-13-B NEVER
    sets it: a definition declaring an approval step is refused before a run exists
    (§18), so the state is unreachable until AI-13-C implements the gate.
    """

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class FailureClass(StrEnum):
    """§9. Exactly nine, and there is no tenth.

    ```text
    FROZEN: FailureClass is exactly the nine members above. It has NO `UNKNOWN` member.
    ```

    A failure matching none of these is UNCLASSIFIED: no member is assigned, the
    execution stops, and no retry is permitted (§9.1). A tenth member would make "we
    could not classify this" a CLASS — a value sitting in the same field as the nine
    and that a policy could be written against. It is not a kind of failure; it is the
    absence of a classification, and the only honest action on an absence is to stop.
    """

    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    BLOCKED_PRECONDITION = "BLOCKED_PRECONDITION"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"


#: §14. The run states from which nothing transitions.
TERMINAL_STATES: frozenset[WorkflowState] = frozenset(
    {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.BLOCKED,
        WorkflowState.CANCELLED,
        WorkflowState.TIMED_OUT,
        WorkflowState.RESOURCE_EXHAUSTED,
        WorkflowState.DEFINITION_CHANGED,
        WorkflowState.WORKSPACE_CHANGED,
        WorkflowState.CHECKPOINT_CORRUPT,
    }
)

#: §9.2. The classes no declared policy may retry, whatever it says.
#:
#: `AUTHORIZATION_DENIED` is here because a denial is an answer: asking again without a
#: change in the request is an attempt to have a boundary reconsider, and AI-13 does
#: not build one. `APPROVAL_DENIED` is here because re-asking a human who has answered
#: is pressure, not process. `CANCELLED` is here because cancellation is a decision,
#: not an accident.
NEVER_RETRIED: frozenset[FailureClass] = frozenset(
    {
        FailureClass.AUTHORIZATION_DENIED,
        FailureClass.APPROVAL_DENIED,
        FailureClass.CANCELLED,
        FailureClass.RESOURCE_EXHAUSTED,
    }
)

#: §9. Every member, in the contract's order. A closed tuple so a caller can prove it
#: enumerated the whole vocabulary rather than the part it remembered.
FAILURE_CLASSES: tuple[FailureClass, ...] = tuple(FailureClass)
