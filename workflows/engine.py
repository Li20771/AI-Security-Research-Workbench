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
from workflows.instants import INSTANT_FORMAT, is_instant, parse_instant, plus_seconds
from workflows.policy import (
    attempt_request_digest,
    check_attempt_may_begin,
    check_may_retry,
    effective_deadline,
    effective_timeout_seconds,
    step_deadline_from,
)
from workflows.resume import verify_resume
from workflows.run import AttemptId, AttemptRecord, RunRecord, StepRecord, new_run_id
from workflows.vocabulary import FailureClass, StepState, WorkflowState

__all__ = [
    "AttemptPlan",
    "ExecutionOutcome",
    "StepExecutor",
    "advance",
    "begin_attempt",
    "cancel",
    "checkpoint_for",
    "complete_attempt",
    "record_checkpoint",
    "resume_run",
    "start_run",
    "terminal_state_for",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime(INSTANT_FORMAT)


def _require_the_runs_own_definition(
    definition: WorkflowDefinition, run: RunRecord
) -> None:
    """§5, §8.1. Refuse a definition that is not the one this RUN was created under.

    A run binds to (workflow_id, revision, definition_digest) at creation, and §8.1
    makes a mismatch terminal for a resume. The same mismatch matters anywhere a
    definition is used to act ON a run: an old run read through a newer definition
    produces artifacts that look right and belong to another revision — a checkpoint
    stamped with a digest the run never ran under, or a bound taken from a policy the
    run was never given.

    It is also what makes the two authorities the SAME. §15.1 puts every bound on the
    run record; the definition carries its own copy of the declared limits. Checking the
    digest proves they hold the same numbers, so a bound read from either is the bound
    this run declared.

    The message names the FIELD and not the value: a definition is tracked content, and
    an error message is a place a value escapes to a log.
    """
    if definition.workflow_id != run.workflow_id:
        raise InvalidRecord(
            "the definition is not the one this run was created under: workflow_id "
            "differs (§5)"
        )
    if definition.revision != run.revision:
        raise InvalidRecord(
            "the definition is not the one this run was created under: revision "
            "differs (§5)"
        )
    if definition.definition_digest != run.definition_digest:
        # Checked separately from the revision string on purpose: a revision is a label
        # its author chose, and the digest is the bytes. Two definitions can share a
        # revision and differ, and only the digest catches that.
        raise InvalidRecord(
            "the definition is not the one this run was created under: "
            "definition_digest differs, so its declared bounds are not this run's (§5)"
        )


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

    ### The timing is the EXECUTION's, not AI-13's

    `started_at` and `ended_at` are REQUIRED, and the engine records what it is given.
    It used to write `started_at = ended_at = <the instant the attempt was dispatched>`,
    which recorded every attempt as instantaneous — a ledger that cannot show an
    attempt consuming its bound, and one that would have made "did this attempt exceed
    its step deadline?" unanswerable by construction. An execution that runs for a
    minute and is recorded as taking none is a record that says the bound was never
    reached.

    ### What AI-13 does NOT verify here

    `artifact_bytes` is a figure the executor REPORTS. AI-13 holds no artifact store and
    reads no artifact, so it has nothing to measure the number against: an executor that
    reported zero for artifacts it referenced would be believed. This is the trust
    boundary of the execution seam, not an independent proof, and it is stated here so
    that no reader mistakes the counter for a measurement. `execution_id` and
    `request_digest` cross-checked against something; this one cannot be.
    """

    execution_id: str
    succeeded: bool
    request_digest: str
    started_at: str
    ended_at: str
    reason_code: str = ""
    failure_class: FailureClass | None = None
    artifact_refs: tuple[ArtifactRef, ...] = ()
    #: §15.2's "the decision id it rests on", as a REFERENCE. Empty when the attempt
    #: rested on no decision. AI-13-B never mints one — the execution that asked Guard
    #: already has it, and AI-13 records what it is told rather than inventing a value.
    decision_id: str = ""
    #: The size of the artifacts this attempt referenced, so §12's declared artifact
    #: bound has a counter to be enforced from. A NUMBER, never content: §7.2 and §15.2
    #: keep the bytes outside every record AI-13 writes. See the trust note above.
    artifact_bytes: int = 0
    #: §11.2. WHO cancelled an in-flight attempt and WHY, when the execution reports
    #: `CANCELLED`. AI-13 v1 "cancels between attempts, never inside one", so a
    #: cancellation the engine learns about from an outcome is the attempt owner's act —
    #: and the owner is the only thing that can name it. Required with `CANCELLED` and
    #: refused without it, so a cancelled run cannot reach the record unable to say why.
    cancelled_by: str = ""
    cancelled_reason: str = ""

    def __post_init__(self) -> None:
        if not is_instant(self.started_at) or not is_instant(self.ended_at):
            raise InvalidRecord(
                "an execution outcome reports when it began and ended, as §8.3 "
                "instants; AI-13 records the execution's own timing rather than "
                "assuming one"
            )
        if parse_instant(self.ended_at) < parse_instant(self.started_at):
            raise InvalidRecord("an execution outcome ended before it began")

        # §11.2. The same invariant the RunRecord enforces, one layer out: a CANCELLED
        # outcome names who and why, and an outcome that is not CANCELLED carries
        # neither. Checked here so the engine cannot be handed a cancellation it would
        # have to invent a provenance for.
        cancelling = self.failure_class is FailureClass.CANCELLED
        named = bool(self.cancelled_by) and bool(self.cancelled_reason)
        if cancelling and not named:
            raise InvalidRecord(
                "an execution reported CANCELLED without naming who cancelled it and "
                "why; §11.2 records both, and AI-13 does not mint a provenance for a "
                "cancellation it did not perform"
            )
        if named and not cancelling:
            raise InvalidRecord(
                "an execution reported cancellation provenance for an outcome that is "
                "not CANCELLED; §11.2 records WHO and WHY on a cancellation"
            )


class StepExecutor(Protocol):
    """The seam through which a step reaches an execution. AI-13 composes it.

    `timeout_seconds` is the COMPOSED outer bound from `effective_timeout_seconds`: the
    step's declared per-invocation timeout, narrowed by whatever the step, the workflow
    and the retry budget have left. It is the value the execution must be given, and it
    is passed here rather than left for the executor to derive, because a bound an
    executor computes for itself is a bound an executor can widen.

    The executor forwards it to the AI-08 execution, which forwards it to AI-06's
    per-invocation `timeout_seconds` (AI-06 §, "a timeout is always explicit"). AI-13
    does not reach into that path and does not implement a second one.
    """

    def execute(
        self,
        *,
        definition: WorkflowDefinition,
        step: WorkflowStep,
        attempt_id: AttemptId,
        run: RunRecord,
        now: str,
        timeout_seconds: int,
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
        # §8.3: computed ONCE, HERE, from the runtimes the definition declares, and
        # persisted as ABSOLUTE instants. Resume reads them and never writes new ones,
        # which is what makes a bound survive a restart rather than restarting with it.
        #
        # The definition carries a RUNTIME and the record carries the ABSOLUTE. That
        # split is the contract's: a bound is a fact about a run, and a tracked
        # definition reviewed in Git cannot know when a run began.
        workflow_deadline=plus_seconds(created, definition.limits.workflow_seconds),
        retry_deadline=(
            plus_seconds(created, policy.retry_seconds) if policy is not None else None
        ),
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

    The attempt was already COUNTED, in `begin_attempt`, before the execution was
    entered — so this does not count it again. §15.1 makes the record the account of what
    the run did, and a run that begins an attempt has spent it whether or not the attempt
    comes back to be described.
    """
    return run.with_step(
        step_id,
        state=StepState.FAILED,
        attempts=run.attempts_for(step_id) + (attempt,),
    ).advance(
        state=WorkflowState.FAILED,
        updated_at=now,
        inflight_attempt_no=None,
    )


def _deadline_reached(run: RunRecord, step_deadline: str) -> str:
    """§15.2. WHICH declared deadline an attempt ran into.

    The narrowest is named, and a tie goes to the most specific — a step deadline that
    coincides with its workflow's is still the step's bound being reached, and a reader
    asking what stopped this run wants the innermost limit that did.
    """
    candidates = [(step_deadline, "STEP_DEADLINE_REACHED")]
    if run.retry_deadline is not None:
        candidates.append((run.retry_deadline, "RETRY_DEADLINE_REACHED"))
    candidates.append((run.workflow_deadline, "WORKFLOW_DEADLINE_REACHED"))
    return min(candidates, key=lambda candidate: parse_instant(candidate[0]))[1]


def _terminal(
    run: RunRecord,
    state: WorkflowState,
    now: str,
    *,
    bound: str | None = None,
    cancelled_by: str | None = None,
    cancelled_reason: str | None = None,
) -> RunRecord:
    """End the run. `bound` names the declared bound it reached, when one stopped it (§15.2).

    A run that ends for a reason that is not a bound — an unclassified failure, a
    cancelled run, a refused resume — passes none, because naming a bound there would
    attribute the stop to a limit the run never touched.

    `cancelled_by` and `cancelled_reason` are passed only for a CANCELLED run, and
    `RunRecord.__post_init__` refuses the record if they are missing — so a cancellation
    that cannot name WHO and WHY does not become a terminal state at all.
    """
    return run.advance(
        state=state,
        updated_at=now,
        reached_bound=bound,
        inflight_attempt_no=None,
        cancelled_by=cancelled_by,
        cancelled_reason=cancelled_reason,
    )


@dataclass(frozen=True, slots=True)
class AttemptPlan:
    """What an attempt begins from, decided BEFORE the execution is entered.

    ```text
    Definition = tracked policy data
    RunRecord  = runtime authority
    ```

    §8.3 requires the step deadline to be anchored once and persisted, and a value
    persisted AFTER an execution returns is a value that a process dying mid-attempt
    never wrote — so the next resume derives a fresh full step budget, which is the
    escape the clause exists to close. The two phases are therefore separate functions,
    and this is the handover between them:

    ```text
    plan = begin_attempt(definition=..., run=..., now=...)
    persist(plan.run)                 <- the caller's persistence boundary
    if plan.admitted:
        result = complete_attempt(definition=..., plan=plan, executor=...)
    ```

    `run` is the successor record in BOTH cases. When `admitted` is False a bound or a
    terminal state refused the attempt, and `run` is the terminal successor. When it is
    True, `run` already carries every fact that must outlive a process ending during the
    execution:

    ```text
    step_deadline          anchored once, at the step's first attempt
    inflight_attempt_no    the attempt number this attempt is using
    consumed_total_attempts  the attempt, counted because the run began it
    workflow_deadline · retry_deadline   untouched, and already persisted
    ```
    """

    run: RunRecord
    admitted: bool
    step: WorkflowStep | None = None
    attempt_id: AttemptId | None = None
    timeout_seconds: int = 0
    deadline: str = ""
    refusal: str = ""
    #: The instant the attempt was admitted at. Phase two uses it, so one attempt reads
    #: the clock once and its two halves cannot disagree about when it happened.
    moment: str = ""


def begin_attempt(
    *,
    definition: WorkflowDefinition,
    run: RunRecord,
    now: str | None = None,
) -> AttemptPlan:
    """§6, §8.3, §10.3.1, §11.1, §12. Phase ONE — everything true BEFORE execution.

    It returns the record rather than writing it, because AI-13-B holds no store: the
    CALLER owns the persistence boundary, and this is the state it must write before the
    execution starts. `advance` calls this and completes it in one go for callers that
    do not need to survive a crash; the bounds behave identically either way, and the
    only difference is whether the caller wrote the record down in time.
    """
    moment = now or _utc_now()

    # §5, §8.1. Checked FIRST, before the terminal short-circuit: a foreign definition
    # must not be able to act on this run at all, not even to be told it is finished.
    _require_the_runs_own_definition(definition, run)

    if run.is_terminal:
        return AttemptPlan(
            run=run, admitted=False, refusal=f"RUN_ALREADY_TERMINAL:{run.state}", moment=moment
        )

    step = _next_step(definition, run)
    if step is None:
        return AttemptPlan(
            run=_terminal(run, WorkflowState.COMPLETED, moment),
            admitted=False,
            refusal="ALL_STEPS_SUCCEEDED",
            moment=moment,
        )

    # The bound is evaluated BEFORE the attempt begins (§10.3.1), so an overrun is a
    # refusal rather than something discovered halfway through.
    decision = check_attempt_may_begin(definition, run, step.step_id, moment)
    if not decision.allowed:
        return AttemptPlan(
            run=_terminal(
                run,
                decision.terminal_state or WorkflowState.FAILED,
                moment,
                bound=decision.reason_code,
            ),
            admitted=False,
            refusal=decision.reason_code,
            moment=moment,
        )

    # §6.3. The number is derived from what the run has BEGUN, not from what it has
    # finished, so an attempt whose process died still holds its number and a resume
    # cannot hand the same one out twice.
    attempt_no = max(len(run.attempts_for(step.step_id)), run.inflight_attempt_no or 0) + 1
    attempt_id = AttemptId(run_id=run.run_id, step_id=step.step_id, attempt_no=attempt_no)

    # §11.1, §12. Anchored at the step's FIRST attempt and persisted from there, so a
    # retry inside this step — and a resume of it — spends the same step budget rather
    # than being handed a new one. `run.step_deadline` is read, never recomputed, once
    # the step has started.
    step_deadline = run.step_deadline or step_deadline_from(run, moment)

    prepared = run.advance(
        step_deadline=step_deadline,
        inflight_attempt_no=attempt_no,
        # §15.1. The attempt is spent the moment it BEGINS. A run that started an
        # execution has spent it whether or not the execution returns to be described,
        # and a counter that only moved on the way back would let a crash loop spend
        # without limit — which is what "no resume grants a new budget" forbids.
        consumed_total_attempts=run.consumed_total_attempts + 1,
        updated_at=moment,
    )

    # §11.1. The bound the execution must be GIVEN, composed from the step's declared
    # per-invocation timeout and what the outer bounds have left. It is handed down
    # rather than left for the executor to derive, because a bound an executor computes
    # for itself is a bound an executor can widen.
    return AttemptPlan(
        run=prepared,
        admitted=True,
        step=step,
        attempt_id=attempt_id,
        timeout_seconds=effective_timeout_seconds(prepared, step, moment),
        deadline=effective_deadline(prepared, step.step_id, moment),
        moment=moment,
    )


def complete_attempt(
    *,
    definition: WorkflowDefinition,
    plan: AttemptPlan,
    executor: StepExecutor,
) -> RunRecord:
    """§6, §10, §11, §12, §15. Phase TWO — enter the execution and record what came back.

    It takes the PLAN rather than the original run, so the state the execution is handed
    is the state the caller was told to persist: the anchored step deadline, the counted
    attempt, and the composed timeout all come from one place.
    """
    if not plan.admitted:
        return plan.run

    # Checked rather than asserted. `AttemptPlan` is a public record a caller can build
    # by hand, and a plan claiming `admitted` without the state that admission implies
    # is a refusal this module issues rather than an interpreter feature an optimised
    # run removes.
    step = plan.step
    attempt_id = plan.attempt_id
    run = plan.run
    if step is None or attempt_id is None or run.step_deadline is None:
        raise InvalidRecord(
            "an attempt plan is marked admitted but carries no step, no attempt "
            "identity or no anchored step deadline; only `begin_attempt` produces an "
            "admitted plan, and it sets all three"
        )
    moment = plan.moment
    step_deadline = run.step_deadline
    outer_deadline = plan.deadline

    outcome = executor.execute(
        definition=definition,
        step=step,
        attempt_id=attempt_id,
        run=run,
        now=moment,
        timeout_seconds=plan.timeout_seconds,
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
                started_at=outcome.started_at,
                ended_at=outcome.ended_at,
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
                started_at=outcome.started_at,
                ended_at=outcome.ended_at,
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
        # The EXECUTION's own timing, recorded rather than assumed (§15.2).
        started_at=outcome.started_at,
        ended_at=outcome.ended_at,
        succeeded=outcome.succeeded,
        artifact_refs=outcome.artifact_refs,
        decision_id=outcome.decision_id or None,
    )
    spent_artifacts = run.consumed_artifact_bytes + outcome.artifact_bytes
    # ONE successor, not two chained ones. A step reaching its outcome and its bound
    # being released are the same fact, and splitting them would publish an intermediate
    # record that never existed — a step already SUCCEEDED while its deadline was still
    # anchored — and would make the release unverifiable against its predecessor.
    record = run.advance(
        steps=tuple(
            replace(
                other,
                state=StepState.SUCCEEDED if outcome.succeeded else StepState.READY,
                attempts=other.attempts + (attempt,),
            )
            if other.step_id == step.step_id
            else other
            for other in run.steps
        ),
        # The attempt was counted in `begin_attempt`; this records what it DID.
        consumed_artifact_bytes=spent_artifacts,
        # A step that SUCCEEDED releases its bound, so the next step is anchored on its
        # own first attempt. A step that did not keeps the one it was given, which is
        # what makes the retry spend the same budget.
        step_deadline=None if outcome.succeeded else step_deadline,
        inflight_attempt_no=None,
        updated_at=moment,
    )

    if parse_instant(outcome.ended_at) >= parse_instant(outer_deadline):
        # §11.1. The attempt ran TO or PAST the bound it was given, and that is
        # TIMED_OUT — "did not finish in time" — rather than FAILED, because the two are
        # different facts and a reader acts on them differently.
        #
        # This question is answerable only because the record carries the EXECUTION's
        # timing. While the engine wrote the dispatch instant for both ends, every
        # attempt was recorded as instantaneous and no attempt could ever have been
        # found to exceed anything.
        #
        # `>=` and not `>`: §8.3 freezes "a bound is reached when the current time is >=
        # the deadline", and a bound reached at its final instant is reached.
        return _terminal(
            record,
            WorkflowState.TIMED_OUT,
            moment,
            bound=_deadline_reached(run, step_deadline),
        )

    if spent_artifacts >= run.declared_limit("max_artifact_bytes"):
        # §12. Every other bound is evaluated BEFORE its attempt (§10.3.1) because it is
        # knowable then; the bytes an attempt references are knowable only once it has
        # run. So this one is met here — and it is still TERMINAL and NAMED rather than a
        # silent stop, and the attempt that reached it stays on the ledger.
        #
        # `>=` and not `>`: §12 says REACHING a limit is terminal, and the other three
        # counters are checked at `>=`. A bound that only bit one byte past its declared
        # value would be a limit of "maximum plus one".
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
    if state is WorkflowState.CANCELLED:
        # §11.2. A cancelled run records WHO cancelled and WHY, and the only thing that
        # knows is the execution that observed the cancellation: AI-13 v1 "cancels
        # between attempts, never inside one", so an in-flight cancellation is the
        # attempt owner's act and reaches the record as the owner declared it. AI-13
        # invents nothing here — it carries a reference it was given.
        return _terminal(
            record,
            state,
            moment,
            cancelled_by=outcome.cancelled_by,
            cancelled_reason=outcome.cancelled_reason,
        )
    return _terminal(record, state, moment)


def advance(
    *,
    definition: WorkflowDefinition,
    run: RunRecord,
    executor: StepExecutor,
    now: str | None = None,
) -> RunRecord:
    """§6, §12. Run ONE attempt at the next step, in one call.

    This is `begin_attempt` then `complete_attempt`, and it is a CONVENIENCE. It does not
    hand the pre-execution record to a persistence boundary, so a process ending while
    the execution runs leaves whatever the caller last wrote — which, for a caller using
    this function, is the record from BEFORE the attempt.

    Nothing about the bounds depends on which shape is used: `begin_attempt` anchors the
    step deadline, counts the attempt and fixes the attempt number either way. The
    difference is only whether the caller wrote the record down in time, so a caller
    that must survive a crash uses the two phases directly and persists `plan.run`
    between them.
    """
    plan = begin_attempt(definition=definition, run=run, now=now)
    if not plan.admitted:
        return plan.run
    return complete_attempt(definition=definition, plan=plan, executor=executor)


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


def cancel(
    *,
    run: RunRecord,
    cancelled_by: str,
    reason: str,
    now: str | None = None,
) -> RunRecord:
    """§11.2. Cancellation is terminal, RECORDED, and never retried.

    ```text
    FROZEN: cancellation is not a failure of the work, and a run cancelled by a human
            MUST NOT be recorded as one. AI-13 records WHO cancelled and WHY as a
            declared reference, and does not adjudicate whether the reason was good.
    ```

    Both are REQUIRED and both are REFERENCES: an identifier for the actor and for the
    reason, never prose. A run that stopped with nobody named and nothing recorded is a
    record that cannot answer why it stopped, which is the whole of what §11.2 asks the
    record to be able to do.

    Neither is judged. AI-13 does not decide whether the reason was good, whether the
    actor was entitled, or whether the cancellation should have happened — `_reference`
    checks the FORM of what was declared and nothing else.
    """
    if run.is_terminal:
        return run
    return run.advance(
        state=WorkflowState.CANCELLED,
        updated_at=now or _utc_now(),
        cancelled_by=cancelled_by,
        cancelled_reason=reason,
    )


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

    # §5, §8.1. Before anything is built: the definition must be the run's own, so a
    # checkpoint cannot be stamped with a digest this run never ran under.
    _require_the_runs_own_definition(definition, run)

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

    # §15.1, §15.2. The bound comes from the RUN RECORD — the authority for this run's
    # declared limits — and not from the definition's copy of them. `definition` is a
    # tracked artifact that can be amended between two reads of the same run; the record
    # is what the run was given, and reading it here is what stops a modified definition
    # from changing a budget the run already has.
    if _checkpoint_bytes(checkpoint) > run.declared_limit("max_checkpoint_bytes"):
        raise InvalidRecord(
            "the checkpoint exceeds the declared byte bound; §12 makes reaching a "
            "declared limit a terminal state rather than a silent write",
            reason_code="CHECKPOINT_BYTES_BOUND_REACHED",
        )
    if run.consumed_checkpoints + 1 > run.declared_limit("max_checkpoints"):
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

    §12 makes REACHING a limit terminal, so the write that reaches one ends the run
    HERE rather than at whatever asks it to advance next. Waiting would leave a record
    that is over its declared bound and still says RUNNING, which is a state §12 does
    not define. The count is named before the bytes, matching the order
    `check_attempt_may_begin` checks them, so the name a reader sees does not depend on
    which function happened to notice the same fact.
    """
    moment = now or _utc_now()
    spent_count = run.consumed_checkpoints + 1
    spent_bytes = run.consumed_checkpoint_bytes + _checkpoint_bytes(checkpoint)

    successor = run.advance(
        consumed_checkpoints=spent_count,
        consumed_checkpoint_bytes=spent_bytes,
        updated_at=moment,
    )

    if spent_count >= run.declared_limit("max_checkpoints"):
        return _terminal(
            successor,
            WorkflowState.RESOURCE_EXHAUSTED,
            moment,
            bound="CHECKPOINT_COUNT_BOUND_REACHED",
        )
    if spent_bytes >= run.declared_limit("max_checkpoint_bytes"):
        return _terminal(
            successor,
            WorkflowState.RESOURCE_EXHAUSTED,
            moment,
            bound="CHECKPOINT_BYTES_BOUND_REACHED",
        )
    return successor
