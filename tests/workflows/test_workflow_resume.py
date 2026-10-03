"""AI-13-B — T9, T23, T24: what a resume verifies, and what it must not reset.

§8.3 is the clause these exist for:

```text
FROZEN: a bound MUST SURVIVE RESUME. A resumed run inherits the budget already
        consumed, and no resume, restart or wait grants a new one.
```

Without it the contract would say both that nothing is held open between process
lifetimes and that a run has a maximum runtime — and a duration that restarted on
resume would let a one-hour bound run for a week.
"""

from __future__ import annotations

import dataclasses

import pytest

from workflows.definition import WorkflowDefinition
from workflows.engine import advance, checkpoint_for, resume_run, start_run
from workflows.errors import InvalidCheckpoint
from workflows.resume import INHERITED_FIELDS
from workflows.vocabulary import WorkflowState

from tests.workflows.conftest import (
    a_retry_policy,
    a_step,
    FAR_SECONDS,
    T0,
    T1,
    T2,
    AlwaysFailsExecutor,
    RecordingExecutor,
    definition_body,
    limits,
    make_definition,
)

pytestmark = pytest.mark.layer2

LATER = "2026-10-03T12:00:00Z"


def _started(definition: WorkflowDefinition, **kwargs):  # noqa: ANN202
    return start_run(definition=definition, workspace_identity="ws-1", now=T0, **kwargs)


def _valid_checkpoint(**overrides):  # noqa: ANN202
    """A checkpoint whose digest VERIFIES, with `overrides` applied first.

    `dataclasses.replace` would leave the digest stale and the integrity check would
    stop the resume before the binding under test was reached — the test would then
    pass for a reason it did not name.
    """
    from workflows.canonical import digest_of
    from workflows.checkpoint import CHECKPOINT_DIGEST_FIELD, Checkpoint

    body = {
        "workflow_id": "wf-demo",
        "revision": "v1",
        "definition_digest": "d" * 64,
        "run_id": "run-1",
        "step_id": "s1",
        "attempt_no": 1,
        "completed_steps": ["s1"],
        "artifact_refs": [],
        "created_at": T1,
    }
    body.update(overrides)
    body[CHECKPOINT_DIGEST_FIELD] = digest_of(
        {**body, CHECKPOINT_DIGEST_FIELD: ""}, digest_field=CHECKPOINT_DIGEST_FIELD
    )
    return Checkpoint.from_mapping(body)


def _advanced_once(definition: WorkflowDefinition, *, now=T1, **kwargs):  # noqa: ANN001, ANN202
    run = _started(definition, **kwargs)
    return advance(definition=definition, run=run, executor=RecordingExecutor(), now=now)


# ---------------------------------------------------------------------------
# T23 — the bound survives
# ---------------------------------------------------------------------------


def test_T23_the_workflow_deadline_is_not_recomputed_on_resume() -> None:
    """§8.3. It is computed ONCE, at run creation, and persisted as an ABSOLUTE instant."""
    definition = make_definition(
        limits=limits(workflow_seconds=1800, step_seconds=600)
    )
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    assert run.workflow_deadline == "2026-10-03T10:30:00Z"

    resumed = resume_run(
        definition=definition,
        run=run,
        checkpoint=checkpoint,
        workspace_identity="ws-1",
        executor=RecordingExecutor(),
        now=LATER,
    )
    # LATER is past the deadline, and the resumed run does not get a new one.
    assert resumed.state is WorkflowState.TIMED_OUT
    assert resumed.workflow_deadline == "2026-10-03T10:30:00Z"


def test_T23b_a_run_whose_deadline_has_passed_does_not_resume() -> None:
    """§8.3: "A run whose stored deadline has passed does not resume — it is TIMED_OUT." """
    definition = make_definition(
        limits=limits(workflow_seconds=1800, step_seconds=600)
    )
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    executor = RecordingExecutor()
    resumed = resume_run(
        definition=definition, run=run, checkpoint=checkpoint,
        workspace_identity="ws-1", executor=executor, now=LATER,
    )
    assert len(executor.calls) == 0, "an attempt began after the stored deadline"
    assert resumed.state is WorkflowState.TIMED_OUT


def test_T23c_the_attempt_counter_is_not_rebuilt_from_a_checkpoint() -> None:
    """§8.3. It is a PERSISTED COUNTER on the run record."""
    definition = make_definition(
        limits=limits(attempts_per_step=3, attempts_total=6),
        retry_policy=a_retry_policy(max_attempts=3),
    )
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T1)
    assert run.consumed_total_attempts == 1

    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)
    resumed = resume_run(
        definition=definition, run=run, checkpoint=checkpoint,
        workspace_identity="ws-1", executor=AlwaysFailsExecutor(), now=T2,
    )

    # EXACTLY two, not "at least one". The weaker form was here first and it could not
    # detect the defect it names: a resume that rebuilt the counter from the checkpoint
    # would set it to zero, the resumed attempt would carry it to one, and `>= 1` would
    # pass. One attempt was spent before the resume and the resumed attempt is the
    # second, so the only honest value is two.
    assert resumed.consumed_total_attempts == 2, (
        "the counter was rebuilt from a checkpoint: one attempt was spent before the "
        "resume and the resumed attempt is the second"
    )
    assert len(resumed.attempts_for("s1")) == 2, "the retry did not happen"


def test_T23d_discarding_the_checkpoint_does_not_restore_budget() -> None:
    """§15.1. The bound is enforced from the RECORD, so a discarded snapshot is nothing.

    The shape of the proof: two attempts are permitted, the first has already been
    spent, and a checkpoint is taken and then not kept. If a bound could be read from
    that checkpoint the counter would look like zero — a checkpoint carries completed
    steps, never attempts — and the run would still be RUNNING after its second
    attempt. It is RESOURCE_EXHAUSTED, which is the counter on the record governing.
    """
    definition = make_definition(
        limits=limits(attempts_per_step=2, attempts_total=6),
        retry_policy=a_retry_policy(max_attempts=2),
    )
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T1)
    assert run.state is WorkflowState.RUNNING, "the first failure was not retryable"
    assert run.consumed_total_attempts == 1

    # Taken, and then simply not kept. The run record is unchanged, which is the whole
    # point: there is nothing a discard could take away.
    checkpoint_for(definition=definition, run=run, now=T1)

    executor = AlwaysFailsExecutor()
    after = advance(definition=definition, run=run, executor=executor, now=T2)

    assert len(executor.calls) == 1, "the retry did not run"
    assert after.consumed_total_attempts == 2
    assert after.state is WorkflowState.RESOURCE_EXHAUSTED, (
        "the run was still RUNNING after spending its second attempt, so the bound was "
        "read from somewhere other than the run record"
    )


# ---------------------------------------------------------------------------
# §8.3, §12 — the deadline is COMPUTED at creation and only ever READ
# ---------------------------------------------------------------------------


def test_the_workflow_deadline_is_computed_at_creation_from_the_declared_runtime() -> None:
    """§8.3. The definition declares a RUNTIME; the run record holds the ABSOLUTE.

    This is the split §12's "maximum workflow runtime" and §8.3's "persisted as an
    ABSOLUTE instant" describe together, and it is why no definition carries a date: a
    tracked artifact reviewed in Git cannot know when a run will begin, and a definition
    amended after a run started must not be able to move that run's deadline.
    """
    definition = make_definition(limits=limits(workflow_seconds=1800, step_seconds=600))
    run = _started(definition)

    assert run.created_at == T0
    assert run.workflow_deadline == "2026-10-03T10:30:00Z", "T0 plus the declared runtime"


def test_the_retry_bound_is_computed_at_creation_and_covers_the_whole_run() -> None:
    """§8.3. "The retry time bound is ABSOLUTE for the run, shared by every retry of
    every step, not granted fresh per attempt."
    """
    definition = make_definition(
        limits=limits(workflow_seconds=1800, step_seconds=600),
        retry_policy=a_retry_policy(retry_seconds=600),
    )
    run = _started(definition)

    assert run.retry_deadline == "2026-10-03T10:10:00Z", "T0 plus the declared retry runtime"


def test_resume_reads_the_persisted_deadlines_and_creates_no_new_ones() -> None:
    """§8.3. "resume reads the stored deadline... It never writes a new deadline."

    Both absolutes are facts about the RUN, fixed when it began. A resume that wrote new
    ones would hand the run a fresh budget every time it was picked back up — which is
    the escape the clause exists to close, and the reason the deadline is a persisted
    instant rather than a duration re-applied on each use.
    """
    definition = make_definition(
        limits=limits(workflow_seconds=1800, step_seconds=600),
        retry_policy=a_retry_policy(retry_seconds=900),
    )
    run = _advanced_once(definition)
    assert run.retry_deadline == "2026-10-03T10:15:00Z"
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    resumed = resume_run(
        definition=definition,
        run=run,
        checkpoint=checkpoint,
        workspace_identity="ws-1",
        executor=RecordingExecutor(),
        now=T2,
    )

    assert resumed.workflow_deadline == run.workflow_deadline == "2026-10-03T10:30:00Z"
    assert resumed.retry_deadline == run.retry_deadline == "2026-10-03T10:15:00Z"


def test_resume_never_derives_a_fresh_step_deadline() -> None:
    """§8.3. The crash case, and the reason phase one exists.

    An attempt begins, the process ends before the execution returns, and the run is
    picked back up. The state that survived is the one `begin_attempt` produced — the
    record a caller was told to persist BEFORE executing — and the step bound in it is
    the ORIGINAL one, not `resume_now + step_seconds`.
    """
    from workflows.engine import begin_attempt
    from workflows.instants import plus_seconds

    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    start = _started(definition)

    interrupted = begin_attempt(definition=definition, run=start, now=T0)
    assert interrupted.run.step_deadline == "2026-10-03T10:00:30Z"

    resume_at = "2026-10-03T10:00:10Z"
    resumed = begin_attempt(definition=definition, run=interrupted.run, now=resume_at)

    assert resumed.run.step_deadline == "2026-10-03T10:00:30Z", (
        "the step deadline was re-derived from the resume instant instead of read"
    )
    assert resumed.run.step_deadline != plus_seconds(resume_at, 30), (
        "the resumed attempt was handed a whole new step budget"
    )
    # §6.3. The interrupted attempt keeps its number, so the resumed one takes the next.
    assert interrupted.attempt_id.attempt_no == 1
    assert resumed.attempt_id.attempt_no == 2, "the interrupted attempt number was reused"
    # §15.1. Both attempts were begun, so both were spent.
    assert resumed.run.consumed_total_attempts == 2


def test_a_resumed_run_hands_the_execution_the_ORIGINAL_step_bound() -> None:
    """The same property through the whole `resume_run` path."""
    from workflows.engine import begin_attempt

    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    start = _started(definition)
    interrupted = begin_attempt(definition=definition, run=start, now=T0)
    checkpoint = checkpoint_for(definition=definition, run=interrupted.run, now=T0)

    executor = RecordingExecutor()
    resume_run(
        definition=definition,
        run=interrupted.run,
        checkpoint=checkpoint,
        workspace_identity="ws-1",
        executor=executor,
        now="2026-10-03T10:00:20Z",
    )

    handed = executor.calls[0]["run"]
    assert handed.step_deadline == "2026-10-03T10:00:30Z"
    assert handed.consumed_total_attempts == 2


# ---------------------------------------------------------------------------
# T9 — the workspace binding, with no re-derivation path
# ---------------------------------------------------------------------------


def test_T9_a_changed_workspace_identity_is_WORKSPACE_CHANGED() -> None:
    """§5. v1 has NO re-derivation: a difference is terminal, not reconciled."""
    definition = make_definition()
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    executor = RecordingExecutor()
    resumed = resume_run(
        definition=definition, run=run, checkpoint=checkpoint,
        workspace_identity="ws-2", executor=executor, now=T2,
    )

    assert len(executor.calls) == 0
    assert resumed.state is WorkflowState.WORKSPACE_CHANGED


def test_T9b_an_identical_workspace_identity_resumes() -> None:
    """The control. Without it, a resume that always refused would pass the test above."""
    definition = make_definition()
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    executor = RecordingExecutor()
    resumed = resume_run(
        definition=definition, run=run, checkpoint=checkpoint,
        workspace_identity="ws-1", executor=executor, now=T2,
    )

    assert len(executor.calls) == 1
    assert resumed.state is WorkflowState.COMPLETED


def test_the_workspace_identity_has_no_re_derivation_field() -> None:
    """§5. There is no equivalence claim to make, so there is no place to make one."""
    definition = make_definition()
    run = _started(definition)
    carried = set(dataclasses.asdict(run)) if dataclasses.is_dataclass(run) else set()
    # The run carries ONE workspace fact. A second field is how "equivalent" would
    # arrive, and §5 defers that mechanism rather than implementing it.
    assert "workspace_identity" in {f.name for f in dataclasses.fields(run)}
    assert not {name for name in carried if "re_deriv" in name or "equivalent" in name}


# ---------------------------------------------------------------------------
# The definition binding, at the resume boundary
# ---------------------------------------------------------------------------


def test_a_changed_revision_is_DEFINITION_CHANGED() -> None:
    definition = make_definition()
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    revised = WorkflowDefinition.from_mapping(definition_body(revision="v2"))
    resumed = resume_run(
        definition=revised, run=run, checkpoint=checkpoint,
        workspace_identity="ws-1", executor=RecordingExecutor(), now=T2,
    )
    assert resumed.state is WorkflowState.DEFINITION_CHANGED


def test_a_changed_definition_digest_is_DEFINITION_CHANGED_even_at_the_same_revision() -> None:
    """§5, §8.1. Two definitions can share a revision and differ."""
    definition = make_definition()
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)

    changed = make_definition(steps=[a_step("s1")])
    assert changed.revision == definition.revision
    assert changed.definition_digest != definition.definition_digest

    resumed = resume_run(
        definition=changed, run=run, checkpoint=checkpoint,
        workspace_identity="ws-1", executor=RecordingExecutor(), now=T2,
    )
    assert resumed.state is WorkflowState.DEFINITION_CHANGED


def test_a_tampered_checkpoint_is_CHECKPOINT_CORRUPT_at_the_resume_boundary() -> None:
    definition = make_definition()
    run = _advanced_once(definition)
    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)
    tampered = dataclasses.replace(checkpoint, completed_steps=("s1", "s2"))

    resumed = resume_run(
        definition=definition, run=run, checkpoint=tampered,
        workspace_identity="ws-1", executor=RecordingExecutor(), now=T2,
    )
    assert resumed.state is WorkflowState.CHECKPOINT_CORRUPT


def test_a_checkpoint_from_another_run_is_refused() -> None:
    """Not one of §8.1's three: this is a caller handing over the wrong artifact."""
    definition = make_definition()
    run = _advanced_once(definition)
    foreign = _valid_checkpoint(run_id="run-someone-else")

    with pytest.raises(InvalidCheckpoint) as raised:
        resume_run(
            definition=definition, run=run, checkpoint=foreign,
            workspace_identity="ws-1", executor=RecordingExecutor(), now=T2,
        )
    assert raised.value.reason_code == "CHECKPOINT_FOR_ANOTHER_RUN"


def test_a_checkpoint_naming_an_unknown_step_is_refused() -> None:
    definition = make_definition()
    run = _advanced_once(definition)
    stray = _valid_checkpoint(
        run_id=run.run_id,
        definition_digest=definition.definition_digest,
        step_id="not-a-step",
        completed_steps=[],
    )

    with pytest.raises(InvalidCheckpoint) as raised:
        resume_run(
            definition=definition, run=run, checkpoint=stray,
            workspace_identity="ws-1", executor=RecordingExecutor(), now=T2,
        )
    assert raised.value.reason_code == "CHECKPOINT_NAMES_AN_UNKNOWN_STEP"


def test_INHERITED_FIELDS_is_the_frozen_two() -> None:
    """§8.2, restated where a reader looking at resume will find it."""
    assert set(INHERITED_FIELDS) == {"completed_steps", "artifact_refs"}
