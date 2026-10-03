"""AI-13 §10.3.1, §11, §12 — bounds, and what may begin.

```text
FROZEN: where more than one declared bound applies, the NARROWER one governs. Never the
        wider, and never a value an implementation chose.
```

### The import that is deliberately absent

`workflows.policy` does NOT import `workflows.checkpoint`, and the absence is the
structural form of §15.1's rule. Every bound here is computed from the DEFINITION and
the RUN RECORD:

```text
FROZEN: the run record, not the checkpoint, is what a bound is enforced from:
        discarding every checkpoint MUST NOT reduce the attempts a run has spent.
```

A module that could read a checkpoint could enforce a bound from one, and "could" is
how the escapable version gets written. A test asserts this module's imports, so the
rule cannot be undone by an edit nobody noticed.

### Bounds are evaluated BEFORE an attempt begins

```text
FROZEN: a bound is evaluated BEFORE an attempt begins. An attempt that would begin at or
        after any effective deadline MUST NOT begin, and one that would exceed any
        effective attempt bound MUST NOT begin. Bounds are not discovered by overrunning
        them.
```

Every function here takes `now` as an argument. Nothing reads a clock, so a caller can
prove what happens at a boundary instant rather than waiting for one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from workflows.canonical import digest_of
from workflows.definition import WorkflowDefinition, WorkflowStep
from workflows.instants import parse_instant, plus_seconds
from workflows.run import RunRecord
from workflows.vocabulary import NEVER_RETRIED, FailureClass, WorkflowState

__all__ = [
    "BoundDecision",
    "attempt_request_digest",
    "check_attempt_may_begin",
    "check_may_retry",
    "effective_attempt_bound",
    "effective_deadline",
    "effective_timeout_seconds",
    "parse_instant",
    "seconds_remaining",
    "step_deadline_from",
]


def seconds_remaining(deadline: str, now: str) -> int:
    """How much of `deadline` is left at `now`. Negative once it has passed."""
    return int((parse_instant(deadline) - parse_instant(now)).total_seconds())


def _earliest(instants: list[str]) -> str:
    """The narrowest of several absolute bounds — the one that governs (§10.3.1)."""
    return min(instants, key=parse_instant)


@dataclass(frozen=True, slots=True)
class BoundDecision:
    """Whether an attempt may begin, and if not, what the run becomes.

    `terminal_state` is set only when the refusal is a bound the run has REACHED.
    A refusal that is merely "not yet" — there is still budget, but this attempt would
    overrun it — is terminal too, because §12 makes reaching a limit a terminal state
    rather than a silent stop.
    """

    allowed: bool
    reason_code: str = ""
    terminal_state: WorkflowState | None = None
    detail: str = ""


def effective_attempt_bound(
    definition: WorkflowDefinition,
    run: RunRecord,
    step_id: str,
    failure: FailureClass | None = None,
) -> int:
    """§10.3.1. The narrowest of every attempts bound that applies to this step.

    ```text
    effective attempts for a step
        = min( attempts declared for that step,
               total attempts remaining for the run,
               the retry policy's attempts bound, where that policy covers this failure )
    ```

    The policy's bound is conditional in the contract — "where that policy covers this
    failure" — so `failure` decides whether it is a candidate at all. `None` means the
    question is being asked before a failure exists (may an attempt begin at all?), and
    the policy bound is included: it is a declared ceiling on this step either way.
    """
    # §15.1, §15.2. Read from the RUN RECORD, which is the authority for this run's
    # declared bounds. `definition` is a tracked artifact that can be amended between
    # two reads of the same run; the record is what the run was given.
    candidates = [run.declared_limit("attempts_per_step")]

    remaining_total = run.declared_limit("attempts_total") - run.consumed_total_attempts
    # A run with no budget left has an effective bound of zero, which refuses the next
    # attempt. Clamping at 1 here would silently restore one attempt's worth of budget.
    candidates.append(max(remaining_total, 0))

    policy = definition.retry_policy
    if policy is not None and (failure is None or policy.covers(failure)):
        candidates.append(policy.max_attempts)

    return min(candidates)


def step_deadline_from(run: RunRecord, now: str) -> str:
    """§11.1, §12. The absolute instant a step's declared runtime ends at.

    Called ONCE, when the step's first attempt begins, and then persisted on the run
    record. It is deliberately not called per attempt: `now + step_seconds` recomputed on
    every retry — and on every resume — would restart the bound each time, which is the
    escape §8.3 forbids. A step bounded at one hour would get a fresh hour every time the
    run was picked back up.
    """
    return plus_seconds(now, run.declared_limit("step_seconds"))


def effective_deadline(run: RunRecord, step_id: str, now: str) -> str:
    """§10.3.1. The narrowest deadline an attempt at this step must finish inside.

    ```text
    effective step deadline = min( step deadline, the workflow deadline's REMAINING time )
    effective deadline      = min( workflow deadline, retry deadline, effective step deadline )
    ```

    The step's deadline is READ from the record when the step has started, and derived
    from `now` only when it has not — because before a step starts there is no step bound
    to read, and the instant the first attempt would begin is the only honest anchor.
    """
    step_deadline = run.step_deadline or step_deadline_from(run, now)

    candidates = [_earliest([step_deadline, run.workflow_deadline])]
    if run.retry_deadline is not None:
        candidates.append(run.retry_deadline)
    candidates.append(run.workflow_deadline)
    return _earliest(candidates)


def effective_timeout_seconds(run: RunRecord, step: WorkflowStep, now: str) -> int:
    """§11.1. The timeout an attempt at this step must be GIVEN, composed.

    ```text
    effective timeout
        = min( the step's declared per-invocation timeout,   <- the INNER bound
               the step deadline's remaining time,           \
               the workflow deadline's remaining time,        |  AI-13's OUTER bounds
               the retry deadline's remaining time )         /
    ```

    The inner timeout is the BASE of the minimum and never one of its casualties.
    §11.1 makes AI-13's deadline an OUTER bound that "COMPOSES WITH, and never replaces,
    the per-invocation `timeout_seconds` AI-06 already requires ... it does not remove
    the inner one, and it does not make an inner one optional." So this can only ever
    narrow what the step declared, and the engine hands the result to the execution
    rather than substituting a bound of its own.

    A result of zero or less means no time remains. `check_attempt_may_begin` refuses
    such an attempt before it begins, so a caller that has already asked that question
    receives at least one second here.
    """
    step_deadline = run.step_deadline or step_deadline_from(run, now)
    candidates = [
        step.timeout_seconds,
        seconds_remaining(step_deadline, now),
        seconds_remaining(run.workflow_deadline, now),
    ]
    if run.retry_deadline is not None:
        candidates.append(seconds_remaining(run.retry_deadline, now))
    return min(candidates)


def check_attempt_may_begin(
    definition: WorkflowDefinition,
    run: RunRecord,
    step_id: str,
    now: str,
    failure: FailureClass | None = None,
) -> BoundDecision:
    """§10.3.1, §12. Evaluated BEFORE the attempt, never discovered by overrunning it."""
    if run.is_terminal:
        return BoundDecision(
            allowed=False,
            reason_code=f"RUN_ALREADY_TERMINAL:{run.state}",
            terminal_state=run.state,
            detail="a terminal run does not advance",
        )

    remaining_workflow = seconds_remaining(run.workflow_deadline, now)
    if remaining_workflow <= 0:
        # §8.3: the workflow deadline is absolute and a wait for an approval, a restart
        # and a resume all consume it. Reaching it is TIMED_OUT.
        return BoundDecision(
            allowed=False,
            reason_code="WORKFLOW_DEADLINE_REACHED",
            terminal_state=WorkflowState.TIMED_OUT,
            detail="the workflow deadline has passed",
        )

    if run.retry_deadline is not None and seconds_remaining(run.retry_deadline, now) <= 0:
        return BoundDecision(
            allowed=False,
            reason_code="RETRY_DEADLINE_REACHED",
            terminal_state=WorkflowState.RESOURCE_EXHAUSTED,
            detail="the run-wide retry deadline has passed",
        )

    if run.step_deadline is not None and seconds_remaining(run.step_deadline, now) <= 0:
        # §11.1: exceeding a deadline is TIMED_OUT, because "did not finish in time" and
        # "finished wrongly" are different facts and a reader acts on them differently.
        # The value comes from the RECORD, so a retry spends the same step budget the
        # first attempt was given rather than a fresh one.
        return BoundDecision(
            allowed=False,
            reason_code="STEP_DEADLINE_REACHED",
            terminal_state=WorkflowState.TIMED_OUT,
            detail="the step's declared runtime has been reached",
        )

    spent = len(run.attempts_for(step_id))
    bound = effective_attempt_bound(definition, run, step_id, failure)
    if spent >= bound:
        return BoundDecision(
            allowed=False,
            reason_code="ATTEMPT_BOUND_REACHED",
            terminal_state=WorkflowState.RESOURCE_EXHAUSTED,
            detail=f"{spent} of {bound} permitted attempts at this step have been spent",
        )

    # §12's three resource bounds, all enforced from counters on the RUN RECORD. Each is
    # checked before the attempt because a bound discovered by overrunning it is not a
    # bound — and each was declared, so none may be left with nothing that reaches it.
    if run.consumed_checkpoints >= run.declared_limit("max_checkpoints"):
        return BoundDecision(
            allowed=False,
            reason_code="CHECKPOINT_COUNT_BOUND_REACHED",
            terminal_state=WorkflowState.RESOURCE_EXHAUSTED,
            detail="the declared checkpoint count bound has been reached",
        )

    if run.consumed_checkpoint_bytes >= run.declared_limit("max_checkpoint_bytes"):
        return BoundDecision(
            allowed=False,
            reason_code="CHECKPOINT_BYTES_BOUND_REACHED",
            terminal_state=WorkflowState.RESOURCE_EXHAUSTED,
            detail="the declared total checkpoint byte bound has been reached",
        )

    if run.consumed_artifact_bytes >= run.declared_limit("max_artifact_bytes"):
        return BoundDecision(
            allowed=False,
            reason_code="ARTIFACT_BOUND_REACHED",
            terminal_state=WorkflowState.RESOURCE_EXHAUSTED,
            detail="the declared artifact byte bound has been reached",
        )

    return BoundDecision(allowed=True)


def check_may_retry(
    definition: WorkflowDefinition,
    run: RunRecord,
    step_id: str,
    failure: FailureClass | None,
    now: str,
) -> BoundDecision:
    """§9.2, §10. Retryability is an execution-policy fact, never a reinterpretation.

    The order matters. An UNCLASSIFIED failure stops before any policy is consulted, so
    a policy cannot be written that retries a failure nobody could name.
    """
    if failure is None:
        # §9.1. No class assigned, the execution stops, and no retry is permitted. This
        # is the first check because a policy must not be able to reach past it.
        return BoundDecision(
            allowed=False,
            reason_code="UNCLASSIFIED_FAILURE_STOPS",
            terminal_state=WorkflowState.FAILED,
            detail="the failure matched none of the nine classes, so none was assigned",
        )

    if failure in NEVER_RETRIED:
        return BoundDecision(
            allowed=False,
            reason_code=f"NEVER_RETRIED:{failure}",
            terminal_state=None,
            detail="§9.2 lists this failure as never retried",
        )

    policy = definition.retry_policy
    if policy is None:
        return BoundDecision(
            allowed=False,
            reason_code="NO_RETRY_POLICY",
            terminal_state=None,
            detail="the workflow declares no retry policy, so it has no retries",
        )

    if not policy.covers(failure):
        return BoundDecision(
            allowed=False,
            reason_code=f"POLICY_DOES_NOT_COVER:{failure}",
            terminal_state=None,
            detail="the declared policy does not apply to this failure class",
        )

    return check_attempt_may_begin(definition, run, step_id, now, failure)


def attempt_request_digest(
    definition: WorkflowDefinition, step: WorkflowStep, run: RunRecord
) -> str:
    """The request an attempt at this step MUST make — and the digest of it.

    §10.1: "an attempt's request is the request its definition declares. A retry MUST NOT
    change an actor, a permission level, a target, a capability requirement, a modality,
    an independence requirement, or any other declared constraint." An executor that
    reports a different request has widened it, and the engine refuses the attempt on
    the strength of this digest rather than on a promise that it would not.
    """
    from workflows.canonical import digest_of

    body: Mapping[str, Any] = {
        "workflow_id": definition.workflow_id,
        "revision": definition.revision,
        "definition_digest": definition.definition_digest,
        "step_id": step.step_id,
        "kind": str(step.kind),
        "workspace_identity": run.workspace_identity,
    }
    return digest_of({**body, "request_digest": ""}, digest_field="request_digest")
