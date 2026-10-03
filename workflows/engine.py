"""AI-13 §6, §10, §11, §12, §15 — advancing a run, one step at a time.

```text
FROZEN: AI-13 v1 runs ONE step at a time. There is no concurrency, no parallelism and
        no worker pool.
FROZEN: AI-13 v1 holds no execution open between process lifetimes. A run advances when
        something asks it to; nothing wakes up on its own.
```

### What this module is, and is not

It COMPOSES. `StepExecutor` is the seam through which a step reaches an AI-08 execution,
and AI-13 supplies the identity, the bounds and the record around it. This module starts
no process, imports no provider, calls no tool and writes no evidence — a run advances
because a caller asked it to, and stops where a bound says it stops.

### Every attempt is authorized on its own

```text
FROZEN: the previous attempt's decision grants the next attempt NOTHING.
```

AI-13 does not hold a Guard decision, and there is no field on `AttemptRecord` that
could carry one (`workflows.checkpoint` forbids the names outright, and this module
never constructs one). A resumed or retried attempt reaches its own execution, which
asks Guard for its own invocation exactly as AI-08 §12 requires.

### Two things the executor cannot do

```text
widen the request   an attempt whose reported request digest is not the digest the
                    definition declares is refused, terminal (§10.1)
reuse an execution  an attempt reporting an ExecutionId another attempt already
                    produced is refused, terminal (§6.3)
```

Both are checked on what the executor REPORTS rather than on a promise about what it
would do, because a promise is not checkable and these are.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence

from workflows.canonical import canonical_body
from workflows.checkpoint import CHECKPOINT_DIGEST_FIELD, ArtifactRef, Checkpoint
from workflows.definition import WorkflowDefinition, WorkflowStep
from workflows.errors import InvalidRecord
from workflows.instants import INSTANT_FORMAT
from workflows.policy import (
    attempt_request_digest,
    check_attempt_may_begin,
    check_may_retry,
    step_deadline_from,
)
from workflows.resume import verify_resume
from workflows.run import AttemptId, AttemptRecord, RunRecord, StepRecord, new_run_id
from workflows.vocabulary import FailureClass, StepState, WorkflowState

__all__ = [
    "ExecutionOutcome",
    "StepExecutor",
    "advance",
    "cancel",
    "checkpoint_for",
    "record_checkpoint",
    "resume_run",
    "start_run",
    "terminal_state_for",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime(INSTANT_FORMAT)


def _checkpoint_bytes(checkpoint: Checkpoint) -> int:
    """§12's byte bound, measured over §7.4's canonical body.

    The canonical form is the record's own defined byte form, so a size measured here is
    the same number the digest is computed over. Measuring a differently-encoded copy
    would let a writer's formatting decide whether a declared bound was reached.
    """
    return len(
        canonical_body(checkpoint.to_mapping(), digest_field=CHECKPOINT_DIGEST_FIELD)
    )


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """What one attempt produced. The executor reports it; AI-13 records it.

    `request_digest` is the digest of the request the attempt ACTUALLY made, and
    `execution_id` is the execution it actually produced. Both are checked against what
    the definition declares before the attempt is recorded.
    """

    execution_id: str
    succeeded: bool
    request_digest: str
    reason_code: str = ""
    failure_class: FailureClass | None = None
    artifact_refs: tuple[ArtifactRef, ...] = ()
    #: §15.2's "the decision id it rests on", as a REFERENCE. Empty when the attempt
    #: rested on no decision. AI-13-B never mints one — the execution that asked Guard
    #: already has it, and AI-13 records what it is told rather than inventing a value.
    decision_id: str = ""
    #: The size of the artifacts this attempt referenced, so §12's declared artifact
    #: bound has a counter to be enforced from. A NUMBER, never content: §7.2 and §15.2
    #: keep the bytes outside every record AI-13 writes.
    artifact_bytes: int = 0


class StepExecutor(Protocol):
    """The seam through which a step reaches an execution. AI-13 composes it."""

    def execute(
        self,
        *,
        definition: WorkflowDefinition,
        step: WorkflowStep,
        attempt_id: AttemptId,
        run: RunRecord,
        now: str,
    ) -> ExecutionOutcome: ...


#: §11, §12 name two of these explicitly — the workflow deadline is TIMED_OUT, and a
#: retry, attempt or resource bound is RESOURCE_EXHAUSTED. The rest follow from the
#: failure's own vocabulary: a cancelled execution ends a cancelled run, a refused
#: authorization ends a blocked one, and a terminal failure ends a failed one. Each is
#: a fact about the RUN that a reader can act on, which is why they are states rather
#: than one collapsed "not completed".
def terminal_state_for(failure: FailureClass) -> WorkflowState:
    if failure is FailureClass.TIMED_OUT:
        return WorkflowState.TIMED_OUT
    if failure is FailureClass.RESOURCE_EXHAUSTED:
        return WorkflowState.RESOURCE_EXHAUSTED
    if failure is FailureClass.CANCELLED:
        return WorkflowState.CANCELLED
    if failure in (FailureClass.BLOCKED_PRECONDITION, FailureClass.AUTHORIZATION_DENIED):
        return WorkflowState.BLOCKED
    if failure is FailureClass.APPROVAL_DENIED:
        return WorkflowState.BLOCKED
    return WorkflowState.FAILED


def _initial_steps(definition: WorkflowDefinition) -> tuple[StepRecord, ...]:
    return tuple(
        StepRecord(
            step_id=step.step_id,
            state=StepState.READY if index == 0 else StepState.PENDING,
        )
        for index, step in enumerate(definition.steps)
    )


def start_run(
    *,
    definition: WorkflowDefinition,
    workspace_identity: str,
    now: str | None = None,
    run_id: str | None = None,
) -> RunRecord:
    """§5, §8.3. Create a run. The deadline is computed HERE and never again."""
    definition.verify_digest()
    created = now or _utc_now()

    policy = definition.retry_policy
    record = RunRecord(
        run_id=run_id or new_run_id(),
        workflow_id=definition.workflow_id,
        revision=definition.revision,
        definition_digest=definition.definition_digest,
        workspace_identity=workspace_identity,
        state=WorkflowState.RUNNING,
        steps=_initial_steps(definition),
        created_at=created,
        updated_at=created,
        declared=definition.limits.to_body(),
        # §8.3: computed ONCE, at run creation, and persisted as an ABSOLUTE instant.
        # Resume reads it and never writes a new one, which is what makes a bound
        # survive a restart rather than restarting with it.
        workflow_deadline=definition.limits.workflow_deadline,
        retry_deadline=policy.deadline if policy else None,
        consumed_total_attempts=0,
        consumed_checkpoints=0,
        consumed_checkpoint_bytes=0,
        consumed_artifact_bytes=0,
        run_digest="",
    )
    return record.advance()


def _next_step(definition: WorkflowDefinition, run: RunRecord) -> WorkflowStep | None:
    """The first step that has not succeeded. v1 runs them in declared order."""
    for step in definition.steps:
        record = run.step(step.step_id)
        if record is None or record.state is not StepState.SUCCEEDED:
            return step
    return None


def _refuse_attempt(
    run: RunRecord, step_id: str, attempt: AttemptRecord, now: str
) -> RunRecord:
    """Record an attempt the engine REFUSED, and end the run (§10.1, §6.3).

    The attempt is COUNTED. An execution ran and produced an ExecutionId, and §15.1 makes
    the record the account of what the run did — a refusal that left the counter untouched
    would be a ledger that omits a spend. Both callers are terminal, so the count is not
    what stops anything; it is what makes the stop readable afterwards.
    """
    return run.with_step(
        step_id,
        state=StepState.FAILED,
        attempts=run.attempts_for(step_id) + (attempt,),
    ).advance(
        state=WorkflowState.FAILED,
        updated_at=now,
        consumed_total_attempts=run.consumed_total_attempts + 1,
    )


def _terminal(
    run: RunRecord, state: WorkflowState, now: str, *, bound: str | None = None
) -> RunRecord:
    """End the run. `bound` names the declared bound it reached, when one stopped it (§15.2).

    A run that ends for a reason that is not a bound — an unclassified failure, a
    cancelled run, a refused resume — passes none, because naming a bound there would
    attribute the stop to a limit the run never touched.
    """
    return run.advance(state=state, updated_at=now, reached_bound=bound)


def advance(
    *,
    definition: WorkflowDefinition,
    run: RunRecord,
    executor: StepExecutor,
    now: str | None = None,
) -> RunRecord:
    """§6, §12. Run ONE attempt at the next step, and return the successor record.

    Returns the run unchanged when it is already terminal, and a completed run when
    every step has succeeded. A failed attempt that a declared policy may retry leaves
    the run RUNNING with the step READY; the caller advances again to spend the retry,
    which is what makes each attempt separately authorized and separately recorded.
    """
    moment = now or _utc_now()

    if run.is_terminal:
        return run

    step = _next_step(definition, run)
    if step is None:
        return _terminal(run, WorkflowState.COMPLETED, moment)

    # The bound is evaluated BEFORE the attempt begins (§10.3.1), so an overrun is a
    # refusal rather than something discovered halfway through.
    decision = check_attempt_may_begin(definition, run, step.step_id, moment)
    if not decision.allowed:
        return _terminal(
            run,
            decision.terminal_state or WorkflowState.FAILED,
            moment,
            bound=decision.reason_code,
        )

    attempt_no = len(run.attempts_for(step.step_id)) + 1
    attempt_id = AttemptId(run_id=run.run_id, step_id=step.step_id, attempt_no=attempt_no)

    # §11.1, §12. Anchored at the step's FIRST attempt and persisted from there, so a
    # retry inside this step — and a resume of it — spends the same step budget rather
    # than being handed a new one. `run.step_deadline` is read, never recomputed, once
    # the step has started.
    step_deadline = run.step_deadline or step_deadline_from(definition, moment)

    outcome = executor.execute(
        definition=definition, step=step, attempt_id=attempt_id, run=run, now=moment
    )

    expected_request = attempt_request_digest(definition, step, run)
    if outcome.request_digest != expected_request:
        # §10.1. The attempt made a different request than the definition declares —
        # widened, relaxed or otherwise changed. Refused on the reported digest rather
        # than on a promise, because a promise cannot be checked.
        return _refuse_attempt(
            run,
            step.step_id,
            AttemptRecord(
                attempt_id=attempt_id,
                execution_id=outcome.execution_id,
                failure_class=FailureClass.TERMINAL_FAILURE,
                reason_code="RETRY_WIDENED_REQUEST",
                started_at=moment,
                ended_at=moment,
                succeeded=False,
                decision_id=outcome.decision_id or None,
            ),
            moment,
        )

    if outcome.execution_id and outcome.execution_id in run.execution_ids():
        # §6.3. A retry lineage is a sequence of AttemptIds, each pointing at a DISTINCT
        # ExecutionId — never one ExecutionId with a counter on it.
        return _refuse_attempt(
            run,
            step.step_id,
            AttemptRecord(
                attempt_id=attempt_id,
                execution_id=outcome.execution_id,
                failure_class=FailureClass.TERMINAL_FAILURE,
                reason_code="EXECUTION_ID_REUSED",
                started_at=moment,
                ended_at=moment,
                succeeded=False,
                decision_id=outcome.decision_id or None,
            ),
            moment,
        )

    attempt = AttemptRecord(
        attempt_id=attempt_id,
        execution_id=outcome.execution_id,
        failure_class=None if outcome.succeeded else outcome.failure_class,
        reason_code=outcome.reason_code,
        started_at=moment,
        ended_at=moment,
        succeeded=outcome.succeeded,
        artifact_refs=outcome.artifact_refs,
        decision_id=outcome.decision_id or None,
    )
    spent_artifacts = run.consumed_artifact_bytes + outcome.artifact_bytes
    record = run.with_step(
        step.step_id,
        state=StepState.SUCCEEDED if outcome.succeeded else StepState.READY,
        attempts=run.attempts_for(step.step_id) + (attempt,),
    ).advance(
        consumed_total_attempts=run.consumed_total_attempts + 1,
        consumed_artifact_bytes=spent_artifacts,
        # A step that SUCCEEDED releases its bound, so the next step is anchored on its
        # own first attempt. A step that did not keeps the one it was given, which is
        # what makes the retry spend the same budget.
        step_deadline=None if outcome.succeeded else step_deadline,
        updated_at=moment,
    )

    if spent_artifacts > definition.limits.max_artifact_bytes:
        # §12. Every other bound is evaluated BEFORE its attempt (§10.3.1) because it is
        # knowable then; the bytes an attempt references are knowable only once it has
        # run. So this one is met here — and it is still TERMINAL and NAMED rather than a
        # silent stop, and the attempt that reached it stays on the ledger.
        return _terminal(
            record,
            WorkflowState.RESOURCE_EXHAUSTED,
            moment,
            bound="ARTIFACT_BOUND_REACHED",
        )

    if outcome.succeeded:
        if _next_step(definition, record) is None:
            return _terminal(record, WorkflowState.COMPLETED, moment)
        return record

    retry = check_may_retry(definition, record, step.step_id, outcome.failure_class, moment)
    if retry.allowed:
        # The step stays READY so the NEXT advance spends the retry as its own attempt,
        # with its own AttemptId and its own execution.
        return record

    failure = outcome.failure_class
    state = (
        retry.terminal_state
        if retry.terminal_state is not None
        else (terminal_state_for(failure) if failure is not None else WorkflowState.FAILED)
    )
    return _terminal(record, state, moment)


def resume_run(
    *,
    definition: WorkflowDefinition,
    run: RunRecord,
    checkpoint: Checkpoint,
    workspace_identity: str,
    executor: StepExecutor,
    now: str | None = None,
) -> RunRecord:
    """§8. Verify every binding, then advance ONE attempt as a new attempt."""
    moment = now or _utc_now()

    check = verify_resume(
        definition=definition,
        run=run,
        checkpoint=checkpoint,
        workspace_identity=workspace_identity,
    )
    if not check.allowed:
        return _terminal(run, check.terminal_state or WorkflowState.FAILED, moment)

    # Nothing but DECLARED STATE crosses the resume boundary (§8.2). The inherited
    # state is read, and deliberately not merged into the run: the run already holds
    # it, and copying it back would be a second place for it to be wrong.
    return advance(definition=definition, run=run, executor=executor, now=moment)


def cancel(*, run: RunRecord, now: str | None = None, reason_code: str = "CANCELLED_BY_CALLER") -> RunRecord:
    """§11.2. Cancellation is terminal, and is never retried."""
    if run.is_terminal:
        return run
    return _terminal(run, WorkflowState.CANCELLED, now or _utc_now())


def checkpoint_for(
    *,
    definition: WorkflowDefinition,
    run: RunRecord,
    now: str | None = None,
) -> Checkpoint:
    """§7. A snapshot of what has completed. Disposable, immutable, and not authority.

    Refuses when the declared checkpoint bound would be exceeded, because §12 makes
    reaching a limit a terminal state rather than a silent stop.
    """
    moment = now or _utc_now()

    completed = tuple(
        record.step_id
        for record in run.steps
        if record.state is StepState.SUCCEEDED
    )
    last = completed[-1] if completed else definition.steps[0].step_id
    refs: list[ArtifactRef] = []
    for record in run.steps:
        for attempt in record.attempts:
            refs.extend(attempt.artifact_refs)

    draft = Checkpoint(
        workflow_id=definition.workflow_id,
        revision=definition.revision,
        definition_digest=definition.definition_digest,
        run_id=run.run_id,
        step_id=last,
        attempt_no=max(len(run.attempts_for(last)), 1),
        completed_steps=completed,
        created_at=moment,
        artifact_refs=tuple(refs),
        checkpoint_digest="",
    )
    checkpoint = replace(draft, checkpoint_digest=draft.computed_digest)

    if _checkpoint_bytes(checkpoint) > definition.limits.max_checkpoint_bytes:
        raise InvalidRecord(
            "the checkpoint exceeds the declared byte bound; §12 makes reaching a "
            "declared limit a terminal state rather than a silent write",
            reason_code="CHECKPOINT_BYTES_BOUND_REACHED",
        )
    if run.consumed_checkpoints + 1 > definition.limits.max_checkpoints:
        raise InvalidRecord(
            "the declared checkpoint count bound has been reached (§12)",
            reason_code="CHECKPOINT_COUNT_BOUND_REACHED",
        )
    return checkpoint


def record_checkpoint(
    *,
    run: RunRecord,
    checkpoint: Checkpoint,
    now: str | None = None,
) -> RunRecord:
    """§12, §15.1. Charge a WRITTEN checkpoint to the RUN RECORD.

    A checkpoint is disposable; the bound that limits it is not. The counter lives on the
    record so that discarding every checkpoint a run wrote cannot restore the budget to
    write more — and so that `check_attempt_may_begin` can end the run when the bound is
    reached, rather than the bound being declared, validated, and never reachable.
    """
    moment = now or _utc_now()
    return run.advance(
        consumed_checkpoints=run.consumed_checkpoints + 1,
        consumed_checkpoint_bytes=run.consumed_checkpoint_bytes + _checkpoint_bytes(checkpoint),
        updated_at=moment,
    )
