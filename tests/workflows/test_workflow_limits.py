"""AI-13-B — T17, T23, T24: every DECLARED bound must have something that reaches it.

§12 declares six limits and refuses a workflow that omits any of them:

```text
maximum workflow runtime          maximum attempts per step
maximum step runtime              maximum total attempts for the run
maximum checkpoint count or       maximum artifact bytes referenced by a run
  total checkpoint bytes per run
```

```text
FROZEN: these are DECLARED, not defaulted. A workflow that declares no limit is refused
        at validation; "no limit" and "a limit nobody wrote down" are the same thing at
        run time, and only one of them is honest.
FROZEN: reaching any limit is a TERMINAL state with its own name (`RESOURCE_EXHAUSTED`),
        and never a silent stop.
```

### The property these tests exist for

A declared bound that NOTHING can reach satisfies every test that only checks a
definition is REFUSED for omitting it. Validation would pass, the counters would sit at
zero, and "maximum artifact bytes" would be a number in a tracked file that no run ever
touched — which is what the second clause above calls a silent stop arriving by a
different route.

So each test here drives a counter to its bound and requires the RUN to end, by name.
The last test in the module states the property directly rather than one bound at a time.
"""

from __future__ import annotations

import pytest

from workflows.definition import WorkflowDefinition
from workflows.engine import (
    advance,
    checkpoint_for,
    record_checkpoint,
    resume_run,
    start_run,
)
from workflows.errors import InvalidDefinition
from workflows.policy import check_attempt_may_begin
from workflows.vocabulary import StepState, WorkflowState

from tests.workflows.conftest import (
    FAR_SECONDS,
    STEP_TIMEOUT_SECONDS,
    T0,
    T1,
    T2,
    AlwaysFailsExecutor,
    RecordingExecutor,
    a_retry_policy,
    definition_body,
    limits,
    make_definition,
)

pytestmark = pytest.mark.layer2


def _started(definition: WorkflowDefinition, **kwargs):  # noqa: ANN202
    return start_run(definition=definition, workspace_identity="ws-1", now=T0, **kwargs)


# ---------------------------------------------------------------------------
# T17 — the checkpoint bounds, which nothing reached before
# ---------------------------------------------------------------------------


def test_T17_a_reached_checkpoint_count_bound_ends_the_run() -> None:
    """§12. The count is a counter on the RECORD, so writing snapshots spends it."""
    definition = make_definition(limits=limits(max_checkpoints=1))
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T1)
    assert run.state is WorkflowState.RUNNING

    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
    assert run.consumed_checkpoints == 1, "writing a checkpoint did not spend the budget"

    after = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T2)
    assert after.state is WorkflowState.RESOURCE_EXHAUSTED
    assert after.reached_bound == "CHECKPOINT_COUNT_BOUND_REACHED"


def test_T17b_a_reached_checkpoint_byte_bound_ends_the_run() -> None:
    """§12's other half: "count OR total checkpoint bytes". Bytes accumulate on the
    record, so a run can exceed the total without any single checkpoint being too big."""
    definition = make_definition(
        limits=limits(max_checkpoints=100, max_checkpoint_bytes=1200)
    )
    run = _started(definition)
    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    assert run.consumed_checkpoint_bytes == 0

    reached = None
    previous = run
    for _ in range(200):
        previous = run
        run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
        if run.state is WorkflowState.RESOURCE_EXHAUSTED:
            reached = run
            break
    assert previous.state is WorkflowState.RUNNING, (
        "the run was already terminal before the write that reached the bound, so this "
        "test cannot tell which write did it"
    )

    # §12. The WRITE that reaches the bound ends the run — not the next `advance`, which
    # would leave a record that is over its declared bound and still says RUNNING.
    assert reached is not None, "the byte bound was never reached, so it bounds nothing"
    assert reached.reached_bound == "CHECKPOINT_BYTES_BOUND_REACHED"


def test_T24c_discarding_checkpoints_does_not_restore_the_checkpoint_budget() -> None:
    """§15.1, for the checkpoint bound specifically.

    Two snapshots are written and then not kept — no reference survives. The record is
    unchanged, so the budget is still spent. A bound read from "the checkpoints I still
    have" would read zero here and let the run write forever.
    """
    definition = make_definition(limits=limits(max_checkpoints=2))
    run = _started(definition)

    for _ in range(2):
        snapshot = checkpoint_for(definition=definition, run=run, now=T1)
        run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
    del snapshot

    assert run.consumed_checkpoints == 2
    after = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T2)
    assert after.state is WorkflowState.RESOURCE_EXHAUSTED
    assert after.reached_bound == "CHECKPOINT_COUNT_BOUND_REACHED"


def test_the_checkpoint_count_bound_is_terminal_AT_the_write_that_reaches_it() -> None:
    """§12. "reaching any limit is a TERMINAL state" — at the WRITE, not at whatever
    asks the run to advance next.

    Waiting leaves a record that is at its declared bound and still says RUNNING, which
    is a state §12 does not define and a reader would have to interpret.
    """
    definition = make_definition(limits=limits(max_checkpoints=3))
    run = _started(definition)
    snapshot = checkpoint_for(definition=definition, run=run, now=T1)

    for expected in (1, 2):
        run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
        assert run.consumed_checkpoints == expected
        assert run.state is WorkflowState.RUNNING, (
            f"the run went terminal at {expected} of its declared three checkpoints"
        )

    run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
    assert run.consumed_checkpoints == 3
    assert run.state is WorkflowState.RESOURCE_EXHAUSTED
    assert run.reached_bound == "CHECKPOINT_COUNT_BOUND_REACHED"


def test_the_artifact_bound_is_terminal_AT_the_declared_maximum() -> None:
    """§12. A bound of "maximum N" that only bit at N plus one would be a bound of N
    plus one, and the three other counters are checked at `>=`."""
    definition = make_definition(limits=limits(max_artifact_bytes=1000))
    executor = RecordingExecutor(artifact_bytes=1000)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T1)

    assert run.consumed_artifact_bytes == 1000
    assert run.state is WorkflowState.RESOURCE_EXHAUSTED
    assert run.reached_bound == "ARTIFACT_BOUND_REACHED"


# ---------------------------------------------------------------------------
# T17 — the artifact bound, which nothing checked before
# ---------------------------------------------------------------------------


def test_T17c_a_reached_artifact_bound_ends_the_run() -> None:
    """§12. Bytes an attempt references are knowable only once it has run, so this bound
    is met after the attempt — and is still TERMINAL and NAMED rather than a silent stop."""
    definition = make_definition(limits=limits(max_artifact_bytes=1000))
    executor = RecordingExecutor(artifact_bytes=1001)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T1)

    assert run.state is WorkflowState.RESOURCE_EXHAUSTED
    assert run.reached_bound == "ARTIFACT_BOUND_REACHED"
    assert run.consumed_artifact_bytes == 1001
    assert len(run.attempts_for("s1")) == 1, "the attempt that reached the bound was dropped"


def test_T17d_an_attempt_under_the_artifact_bound_is_recorded_and_continues() -> None:
    """The control: the same path accepts an attempt that stays UNDER the bound.

    Under, and not merely at it: §12 makes reaching a limit terminal, so the run that
    spends exactly the declared maximum has reached it.
    """
    definition = make_definition(limits=limits(max_artifact_bytes=1000))
    executor = RecordingExecutor(artifact_bytes=999)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T1)

    assert run.state is WorkflowState.RUNNING
    assert run.reached_bound is None
    assert run.consumed_artifact_bytes == 999


def test_T24d_the_artifact_bound_is_enforced_from_the_record_across_a_resume() -> None:
    """§8.3, §15.1. The spend is on the record, so a resume inherits it."""
    definition = make_definition(limits=limits(max_artifact_bytes=1500))
    run = _started(definition)
    run = advance(
        definition=definition,
        run=run,
        executor=RecordingExecutor(artifact_bytes=1000),
        now=T1,
    )
    assert run.consumed_artifact_bytes == 1000

    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    resumed = resume_run(
        definition=definition,
        run=run,
        checkpoint=snapshot,
        workspace_identity="ws-1",
        executor=RecordingExecutor(artifact_bytes=1000),
        now=T2,
    )

    assert resumed.state is WorkflowState.RESOURCE_EXHAUSTED, (
        "the resumed run was handed a fresh artifact budget"
    )
    assert resumed.consumed_artifact_bytes == 2000
    assert resumed.reached_bound == "ARTIFACT_BOUND_REACHED"


# ---------------------------------------------------------------------------
# T17, T23 — the STEP runtime bound
# ---------------------------------------------------------------------------


def test_T17e_a_reached_step_deadline_ends_the_run() -> None:
    """§11.1. The step's declared runtime is an absolute instant, and it governs."""
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T0)
    assert run.state is WorkflowState.RUNNING
    assert run.step_deadline == "2026-10-03T10:00:30Z"

    after = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now="2026-10-03T10:00:30Z")
    assert after.state is WorkflowState.TIMED_OUT, (
        "the step's declared runtime was reached and the run continued"
    )
    assert after.reached_bound == "STEP_DEADLINE_REACHED"


def test_T23e_the_step_deadline_is_anchored_once_and_survives_a_resume() -> None:
    """§8.3. A per-attempt `now + step_seconds` would hand the resume a whole new step
    budget — so a step bounded at one minute could be resumed into an unbounded one."""
    definition = make_definition(
        limits=limits(step_seconds=60, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T1)
    anchored = run.step_deadline
    assert anchored == "2026-10-03T10:01:10Z"

    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    resumed = resume_run(
        definition=definition,
        run=run,
        checkpoint=snapshot,
        workspace_identity="ws-1",
        executor=AlwaysFailsExecutor(),
        now="2026-10-03T10:00:40Z",
    )

    assert resumed.step_deadline == anchored, (
        "the resumed run was handed a new step deadline instead of inheriting the "
        "remaining step budget (§8.3)"
    )

    after = advance(
        definition=definition,
        run=resumed,
        executor=AlwaysFailsExecutor(),
        now="2026-10-03T10:01:10Z",
    )
    assert after.state is WorkflowState.TIMED_OUT


# ---------------------------------------------------------------------------
# §15.2 — the record names the bound, and the decision the attempt rested on
# ---------------------------------------------------------------------------


def test_T17f_a_run_that_reached_no_bound_names_none() -> None:
    """§15.2. `reached_bound` is a fact, not a summary: a run stopped by an unclassified
    failure must not be attributed to a limit it never touched."""
    from workflows.vocabulary import FailureClass

    definition = make_definition()
    run = advance(
        definition=definition,
        run=_started(definition),
        executor=AlwaysFailsExecutor(failure=None),
        now=T1,
    )
    assert run.state is WorkflowState.FAILED
    assert run.reached_bound is None


def test_the_decision_a_failed_attempt_rested_on_is_recorded_as_a_reference() -> None:
    """§15.2. "the reason code and the decision id it rests on" — as a REFERENCE."""
    definition = make_definition()
    run = advance(
        definition=definition,
        run=_started(definition),
        executor=RecordingExecutor(outcomes=[False], decision_id="dec-1"),
        now=T1,
    )
    attempt = run.attempts_for("s1")[-1]
    assert attempt.decision_id == "dec-1"
    assert attempt.reason_code == "TRANSIENT"


def test_the_checkpoint_REFUSES_the_decision_id_the_record_carries() -> None:
    """§15.1, mechanically. The ledger is required to name the decision (§15.2); the
    disposable snapshot a resumed attempt reads is forbidden to (§7.2). One name, two
    records, opposite rules — which is the separation doing work rather than tidying."""
    from workflows.checkpoint import Checkpoint
    from workflows.errors import InvalidCheckpoint

    with pytest.raises(InvalidCheckpoint) as raised:
        Checkpoint.from_mapping(
            {
                "workflow_id": "w", "revision": "v1", "definition_digest": "d",
                "run_id": "r", "step_id": "s", "attempt_no": 1,
                "completed_steps": [], "created_at": T0,
                "decision_id": "dec-1", "checkpoint_digest": "x",
            }
        )
    assert raised.value.reason_code == "CHECKPOINT_CARRIES_FORBIDDEN_STATE"


def test_an_attempt_that_rested_on_nothing_carries_no_decision() -> None:
    """The control. A record that invented a decision id would be asserting an
    authorization nobody gave, which is the defect §13.3 exists to refuse."""
    definition = make_definition()
    run = advance(
        definition=definition, run=_started(definition), executor=RecordingExecutor(), now=T1
    )
    assert run.attempts_for("s1")[-1].decision_id is None


# ---------------------------------------------------------------------------
# The artifact byte counter, and the trust boundary it actually has
# ---------------------------------------------------------------------------


def test_artifact_bytes_are_REPORTED_by_the_execution_not_measured_by_ai13() -> None:
    """§12's artifact bound, and the limit of what AI-13 can claim about it.

    AI-13 holds no artifact store and reads no artifact, so `artifact_bytes` is a figure
    the EXECUTION reports and AI-13 has nothing to check it against. This test pins that
    fact rather than leaving it implied: an executor that reports zero bytes for
    artifacts it did reference is believed, so the counter is a bound on what the
    execution DECLARES, not an independent measurement of what it produced.

    Stating it here is deliberate. A reader who assumed the number was verified would
    overrate the bound, and the person who needs to know is whoever is deciding whether
    to trust a workflow run's resource accounting — not whoever is attacking it.

    Verifying it would need an artifact store or a reader AI-13 does not have and this
    contract does not give it, so the honest move is to name the boundary rather than
    to pretend the counter crosses it.
    """
    from workflows.checkpoint import ArtifactRef

    declared = (ArtifactRef(reference="artifact://run/output", digest="a" * 64),)
    definition = make_definition(limits=limits(max_artifact_bytes=1))
    executor = RecordingExecutor(artifact_bytes=0, artifact_refs=declared)

    run = advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    assert run.state is WorkflowState.RUNNING, (
        "the run stopped for a reason this test does not describe"
    )
    assert run.consumed_artifact_bytes == 0, "what the execution declared is what is counted"
    assert run.attempts_for("s1")[-1].artifact_refs == declared, (
        "the references are recorded; only their SIZE is taken on the execution's word"
    )


def test_the_artifact_counter_is_a_number_and_never_content() -> None:
    """§7.2, §15.2. What crosses the seam is a size and a reference — never the bytes.

    This is the half of the rule AI-13 does enforce, and it is the half that matters for
    every record AI-13 writes: whatever the execution reports, the ledger holds no
    artifact content for a checkpoint or a reader to leak.
    """
    from workflows.checkpoint import ArtifactRef

    declared = (ArtifactRef(reference="artifact://run/output", digest="b" * 64),)
    definition = make_definition()
    executor = RecordingExecutor(artifact_bytes=4096, artifact_refs=declared)

    run = advance(definition=definition, run=_started(definition), executor=executor, now=T0)
    carried = run.attempts_for("s1")[-1].artifact_refs[0]

    assert set(carried.to_body()) == {"reference", "digest"}
    assert run.consumed_artifact_bytes == 4096


# ---------------------------------------------------------------------------
# §11.1 — the outer bound reaches the EXECUTION, and composes with the inner one
# ---------------------------------------------------------------------------


def test_the_effective_timeout_is_handed_to_the_execution() -> None:
    """§11.1. The composed outer bound REACHES the execution.

    A bound the engine computes and then drops is a bound nobody is given, and a bound
    nobody is given is a bound nobody honours. Here the step has five seconds of its
    declared runtime left, the run has eight, and the step declared thirty — so five
    governs and five is what the execution is told.
    """
    definition = make_definition(limits=limits(workflow_seconds=8, step_seconds=5))
    executor = RecordingExecutor()
    advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    assert executor.calls[0]["timeout_seconds"] == 5


def test_the_workflow_deadline_remains_the_outer_bound() -> None:
    """§10.3.1. "effective step deadline = min(step deadline, the workflow deadline's
    REMAINING time)".

    The step declared ten minutes and has them; the WORKFLOW has five seconds left. The
    workflow is the narrower bound, so the workflow is what the execution is given — an
    outer bound that a wider inner one could override would not be an outer bound.
    """
    definition = make_definition(limits=limits(workflow_seconds=5, step_seconds=600))
    executor = RecordingExecutor()
    advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    assert executor.calls[0]["timeout_seconds"] == 5


def test_the_step_bound_survives_a_retry() -> None:
    """§8.3 by way of §12. A retry spends the budget the STEP was given.

    The step deadline is anchored at the step's first attempt and persisted from there,
    so a retry inside that step inherits what is left rather than being handed a fresh
    step runtime — the same rule that keeps the workflow and retry budgets from
    restarting, applied to the bound in between them.
    """
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    executor = AlwaysFailsExecutor(duration_seconds=5)
    run = _started(definition)

    run = advance(definition=definition, run=run, executor=executor, now=T0)
    anchored = run.step_deadline
    assert anchored == "2026-10-03T10:00:30Z"

    run = advance(
        definition=definition,
        run=run,
        executor=executor,
        now="2026-10-03T10:00:20Z",
    )
    assert run.step_deadline == anchored, "the retry was handed a fresh step budget"
    assert len(run.attempts_for("s1")) == 2, "the retry did not happen"


def test_the_outer_bound_never_widens_the_inner_timeout() -> None:
    """§11.1. "It does not remove the inner one, and it does not make an inner one
    optional."

    With both outer bounds far away, the step's DECLARED per-invocation timeout is what
    the execution is given. The composition can only ever narrow: an outer bound that is
    wider must not become the value handed down, because that would replace AI-06's
    inner timeout with a longer one.
    """
    definition = make_definition(
        limits=limits(workflow_seconds=FAR_SECONDS, step_seconds=FAR_SECONDS)
    )
    executor = RecordingExecutor()
    advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    assert executor.calls[0]["timeout_seconds"] == STEP_TIMEOUT_SECONDS


def test_a_step_declaring_no_inner_timeout_is_refused() -> None:
    """§11.1. The outer bound does not make the inner one optional, so a step that
    declared only an outer one is not a step this contract admits."""
    with pytest.raises(InvalidDefinition):
        WorkflowDefinition.from_mapping(
            definition_body(steps=[{"step_id": "s1", "kind": "AGENT_EXECUTION"}])
        )


def test_the_recorded_timing_is_the_executions_not_the_dispatch_instant() -> None:
    """§15.2. An attempt that took forty-five seconds is recorded as taking forty-five.

    The engine used to write the dispatch instant for BOTH ends, which recorded every
    attempt as instantaneous — a ledger that could not show an attempt consuming its
    bound, and that made "did this attempt exceed its deadline?" unanswerable by
    construction.
    """
    definition = make_definition(
        limits=limits(workflow_seconds=FAR_SECONDS, step_seconds=600)
    )
    executor = RecordingExecutor(duration_seconds=45)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    attempt = run.attempts_for("s1")[-1]
    assert attempt.started_at == T0
    assert attempt.ended_at == "2026-10-03T10:00:45Z"


def test_an_attempt_that_overruns_its_effective_deadline_is_TIMED_OUT() -> None:
    """§11.1. The bound governs AFTER the attempt as well as before it.

    §11.1 makes exceeding a deadline TIMED_OUT rather than FAILED, "because 'did not
    finish in time' and 'finished wrongly' are different facts and a reader acts on them
    differently".
    """
    definition = make_definition(
        limits=limits(workflow_seconds=FAR_SECONDS, step_seconds=30)
    )
    executor = RecordingExecutor(duration_seconds=30)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    assert run.state is WorkflowState.TIMED_OUT
    assert run.reached_bound == "STEP_DEADLINE_REACHED"
    assert len(run.attempts_for("s1")) == 1, "the attempt that overran was dropped"


def test_an_attempt_that_stays_inside_its_bound_is_not_TIMED_OUT() -> None:
    """The control. Without it the check above would pass on a run that always timed out."""
    definition = make_definition(
        limits=limits(workflow_seconds=FAR_SECONDS, step_seconds=30)
    )
    executor = RecordingExecutor(duration_seconds=29)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T0)

    assert run.state is WorkflowState.RUNNING
    assert run.reached_bound is None


# ---------------------------------------------------------------------------
# The property, once, over every bound §12 declares
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declared",
    [
        "workflow_seconds",
        "step_seconds",
        "attempts_per_step",
        "attempts_total",
        "max_checkpoints",
        "max_checkpoint_bytes",
        "max_artifact_bytes",
    ],
)
def test_every_declared_limit_is_named_where_it_is_enforced(declared: str) -> None:
    """§12. No bound is inert.

    Each of §12's limits must appear somewhere that can REACH it: the two absolute
    deadlines and the two attempt bounds in the bound check, the checkpoint bounds in the
    bound check and the write refusal, and the artifact bound in the bound check and the
    post-attempt spend. A limit that appears only in validation is a number nobody
    enforces, and this test is what stops one being added back.
    """
    import pathlib
    import re

    import workflows.engine as engine_module
    import workflows.policy as policy_module

    # Read from the modules that were IMPORTED, not from paths assembled out of the
    # working directory, so this holds for the code actually in use.
    policy_source = pathlib.Path(policy_module.__file__).read_text(encoding="utf-8")
    engine_source = pathlib.Path(engine_module.__file__).read_text(encoding="utf-8")

    # The two attempt bounds are consumed through EFFECTIVE bound arithmetic rather than
    # by name, so they are checked against the attribute they are read from.
    # §15.1, §15.2. Every one of these is read from the RUN RECORD, which is the
    # authority for the bounds a run declared. The workflow runtime is the one exception
    # in form: it is turned into an absolute at creation, and the absolute is what is
    # enforced from then on.
    attribute = {
        "workflow_seconds": "definition.limits.workflow_seconds",
        "step_seconds": 'run.declared_limit("step_seconds")',
        "attempts_per_step": 'run.declared_limit("attempts_per_step")',
        "attempts_total": 'run.declared_limit("attempts_total")',
        "max_checkpoints": 'run.declared_limit("max_checkpoints")',
        "max_checkpoint_bytes": 'run.declared_limit("max_checkpoint_bytes")',
        "max_artifact_bytes": 'run.declared_limit("max_artifact_bytes")',
    }[declared]

    assert attribute in policy_source or attribute in engine_source, (
        f"{declared} is declared and validated but nothing enforces it, which is what "
        f"§12 refuses when it says a limit nobody wrote down and no limit are the same "
        f"thing at run time"
    )
    assert re.search(rf"\b{declared}\b", policy_source + engine_source), declared
