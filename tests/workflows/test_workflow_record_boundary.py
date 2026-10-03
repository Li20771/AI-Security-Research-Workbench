"""AI-13-B — §5, §6.3, §8.3, §12, §15: the boundaries a record may not cross.

Two ways a record can quietly disagree with something it is supposed to be bound by:

```text
successor   a later record contradicting the history of the one before it
binding     a run read through a definition it was never created under
```

**A digest catches neither.** It proves a record is internally consistent, and both of
these records are perfectly consistent: `run.advance(consumed_total_attempts=0)` hashes
beautifully, and a checkpoint built from an amended definition is a well-formed
checkpoint. The digest answers "is this record what it says it is", never "is this
record entitled to say it".

So both rules are enforced where the transition happens, and both are tested by making
the transition DIRECTLY. "The engine is the only caller" is not a boundary — it is a
convention, and the tests below are written as the caller who never agreed to it.
"""

from __future__ import annotations

import dataclasses

import pytest

from workflows.canonical import digest_of
from workflows.definition import WorkflowDefinition
from workflows.engine import (
    advance,
    begin_attempt,
    checkpoint_for,
    complete_attempt,
    record_checkpoint,
    start_run,
)
from workflows.errors import InvalidRecord
from workflows.run import RUN_DIGEST_FIELD, AttemptId, AttemptRecord, RunRecord, StepRecord
from workflows.vocabulary import FailureClass, StepState, WorkflowState

from tests.workflows.conftest import (
    T0,
    T1,
    T2,
    AlwaysFailsExecutor,
    RecordingExecutor,
    a_retry_policy,
    a_step,
    limits,
    make_definition,
)

pytestmark = pytest.mark.layer2


def _failed_once() -> tuple[WorkflowDefinition, RunRecord]:
    """A run with one recorded attempt, a live step bound, and a run-wide retry bound."""
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    executor = AlwaysFailsExecutor(duration_seconds=1)
    run = start_run(definition=definition, workspace_identity="ws-1", now=T0)
    return definition, advance(definition=definition, run=run, executor=executor, now=T0)


# ---------------------------------------------------------------------------
# What a successor may not move
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("workflow_deadline", "2030-01-01T00:00:00Z"),
        ("retry_deadline", "2030-01-01T00:00:00Z"),
        ("workspace_identity", "ws-2"),
        ("definition_digest", "f" * 64),
        ("revision", "v9"),
        ("workflow_id", "wf-other"),
        ("run_id", "run-someone-else"),
    ],
)
def test_a_successor_cannot_move_a_fact_fixed_at_creation(
    field_name: str, value: str
) -> None:
    """§5, §8.3, §15.1. A deadline a later record could extend is not a bound.

    The same for the workspace the earlier steps ran in: §5 makes a difference there
    terminal rather than reconcilable, and a successor free to rewrite it would make
    that check a formality.
    """
    _, run = _failed_once()
    with pytest.raises(InvalidRecord):
        run.advance(**{field_name: value})


def test_a_successor_cannot_rewrite_the_declared_bounds() -> None:
    """§15.1, §15.2. The record carries the bounds the run was given, and is the
    authority a bound is enforced from — so a successor free to rewrite them would make
    every limit in the phase advisory."""
    _, run = _failed_once()
    with pytest.raises(InvalidRecord):
        run.advance(declared={**run.declared, "attempts_total": 10_000})


@pytest.mark.parametrize(
    "field_name",
    [
        "consumed_total_attempts",
        "consumed_checkpoints",
        "consumed_checkpoint_bytes",
        "consumed_artifact_bytes",
    ],
)
def test_a_successor_cannot_lower_a_counter(field_name: str) -> None:
    """§12, §15.1. A counter a bound is enforced from may only ever go up."""
    _, run = _failed_once()
    with pytest.raises(InvalidRecord):
        run.advance(**{field_name: getattr(run, field_name) - 1})


def test_a_successor_cannot_restore_the_attempt_budget() -> None:
    """The literal case this boundary exists for.

    One attempt has been spent. `consumed_total_attempts=0` is a record whose digest
    verifies and which says the run has spent nothing — a budget reset that no signature
    and no digest can distinguish from an honest record.
    """
    _, run = _failed_once()
    assert run.consumed_total_attempts == 1

    with pytest.raises(InvalidRecord):
        run.advance(consumed_total_attempts=0)
    assert run.consumed_total_attempts == 1, "the predecessor was mutated"


def _attempt(
    run: RunRecord,
    step_id: str,
    attempt_no: int,
    *,
    execution_id: str,
    succeeded: bool = False,
) -> AttemptRecord:
    """An attempt a caller built by hand, for a transition the engine never performs."""
    return AttemptRecord(
        attempt_id=AttemptId(run_id=run.run_id, step_id=step_id, attempt_no=attempt_no),
        execution_id=execution_id,
        failure_class=None if succeeded else FailureClass.TERMINAL_FAILURE,
        reason_code="" if succeeded else "REFUSED",
        started_at=T1,
        ended_at=T1,
        succeeded=succeeded,
    )


def _with_step(run: RunRecord, step_id: str, **changes: object):
    """The steps tuple with ONE step record replaced.

    Written out rather than reached for, because there is no longer a `with_step` on
    the record: a step-level change that is not part of a legal transition has no
    convenience path, and a caller who wants one has to build the transition by hand —
    which is exactly the caller these tests are written as.
    """
    return tuple(
        dataclasses.replace(record, **changes) if record.step_id == step_id else record
        for record in run.steps
    )


# ---------------------------------------------------------------------------
# What a successor may not erase
# ---------------------------------------------------------------------------


def test_a_successor_cannot_delete_a_recorded_attempt() -> None:
    """§15.2. A spent attempt cannot be unspent."""
    _, run = _failed_once()
    assert len(run.attempts_for("s1")) == 1

    with pytest.raises(InvalidRecord):
        run.advance(steps=_with_step(run, "s1", attempts=()))


def test_a_successor_cannot_renumber_a_recorded_attempt() -> None:
    """§6.3. An attempt number is never reused or renumbered."""
    _, run = _failed_once()
    recorded = run.attempts_for("s1")[0]
    renumbered = dataclasses.replace(
        recorded, attempt_id=dataclasses.replace(recorded.attempt_id, attempt_no=7)
    )

    with pytest.raises(InvalidRecord):
        run.advance(steps=_with_step(run, "s1", attempts=(renumbered,)))


def test_a_successor_cannot_rewrite_a_recorded_attempt() -> None:
    """§15.2. The ledger records what an attempt WAS, not what it would be convenient
    for it to have been."""
    _, run = _failed_once()
    recorded = run.attempts_for("s1")[0]
    rewritten = dataclasses.replace(recorded, reason_code="NEVER_HAPPENED")

    with pytest.raises(InvalidRecord):
        run.advance(steps=_with_step(run, "s1", attempts=(rewritten,)))


def test_a_successor_cannot_drop_a_step() -> None:
    """§6.1. A step the run declared does not leave its own record."""
    _, run = _failed_once()
    with pytest.raises(InvalidRecord):
        run.advance(steps=run.steps[:1])


# ---------------------------------------------------------------------------
# The two live fields, and the transitions the engine actually needs
# ---------------------------------------------------------------------------


def test_a_successor_cannot_replace_the_step_deadline() -> None:
    """§8.3. It is anchored once. Replacing it hands the same step a second budget."""
    _, run = _failed_once()
    assert run.step_deadline is not None

    with pytest.raises(InvalidRecord):
        run.advance(step_deadline="2030-01-01T00:00:00Z")


def test_a_successor_cannot_release_the_step_deadline_early() -> None:
    """The escape the rule exists for: clear the bound while the step is unfinished, and
    the next attempt anchors a fresh one."""
    _, run = _failed_once()
    with pytest.raises(InvalidRecord):
        run.advance(step_deadline=None)


def test_a_successor_cannot_move_the_inflight_attempt_number_backwards() -> None:
    """§6.3. Reserving a number is fine; handing out an earlier one is not."""
    definition, run = _failed_once()
    planned = begin_attempt(definition=definition, run=run, now=T1)
    assert planned.run.inflight_attempt_no == 2

    with pytest.raises(InvalidRecord):
        planned.run.advance(inflight_attempt_no=1)


def test_a_successor_cannot_leave_a_terminal_state() -> None:
    """§14. A terminal state has no transition out of it."""
    definition, run = _failed_once()
    cancelled = run.advance(
        state=WorkflowState.CANCELLED,
        cancelled_by="operator-li",
        cancelled_reason="SUPERSEDED",
    )

    with pytest.raises(InvalidRecord):
        cancelled.advance(state=WorkflowState.RUNNING)


def test_the_engines_own_transitions_are_not_refused() -> None:
    """The control. A guard that refused everything would pass every test above.

    Three transitions the engine performs and the boundary must permit: reserving an
    attempt number, releasing the step bound when the step succeeds, and recording the
    attempt that did it.
    """
    definition, run = _failed_once()

    reserved = begin_attempt(definition=definition, run=run, now=T1)
    assert reserved.run.inflight_attempt_no == 2

    after = advance(
        definition=definition, run=run, executor=RecordingExecutor(), now=T1
    )
    assert after.step_deadline is None, "the step succeeded and kept its bound"
    assert after.consumed_total_attempts == 2
    assert len(after.attempts_for("s1")) == 2


def test_the_engines_crash_resume_transition_is_not_refused() -> None:
    """The control for the one transition that is not "keep or clear".

    An attempt begins, its process ends, and the run is picked back up. The in-flight
    number moves from the abandoned attempt to a NEW one — never back to the old.
    """
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    start = start_run(definition=definition, workspace_identity="ws-1", now=T0)
    interrupted = begin_attempt(definition=definition, run=start, now=T0)
    assert interrupted.run.inflight_attempt_no == 1

    resumed = begin_attempt(definition=definition, run=interrupted.run, now=T1)
    assert resumed.run.inflight_attempt_no == 2, "the interrupted number was reused"


# ---------------------------------------------------------------------------
# §5 — a run is only ever read through its OWN definition
# ---------------------------------------------------------------------------


def test_checkpoint_for_refuses_a_workflow_id_mismatch() -> None:
    _, run = _failed_once()
    other = make_definition(workflow_id="wf-other")

    with pytest.raises(InvalidRecord):
        checkpoint_for(definition=other, run=run, now=T1)


def test_checkpoint_for_refuses_a_revision_mismatch() -> None:
    _, run = _failed_once()
    other = make_definition(revision="v2")

    with pytest.raises(InvalidRecord):
        checkpoint_for(definition=other, run=run, now=T1)


def test_checkpoint_for_refuses_a_definition_digest_mismatch() -> None:
    """§5. Two definitions can share a revision and differ, and only the digest catches
    it — so the digest is checked separately from the revision string."""
    definition, run = _failed_once()
    other = make_definition(steps=[a_step("s1")])
    assert other.revision == definition.revision
    assert other.definition_digest != definition.definition_digest

    with pytest.raises(InvalidRecord):
        checkpoint_for(definition=other, run=run, now=T1)


def test_an_old_run_under_a_new_definition_is_refused_by_advance_too() -> None:
    """The same binding at the execution boundary. A foreign definition must not drive
    an attempt either — it would carry a different policy and different bounds."""
    definition, run = _failed_once()
    other = make_definition(retry_policy=a_retry_policy(max_attempts=99))

    with pytest.raises(InvalidRecord):
        advance(definition=other, run=run, executor=RecordingExecutor(), now=T1)


def test_a_definition_that_IS_the_runs_own_is_accepted() -> None:
    """The control. Without it the three refusals above could be a path that never works."""
    definition, run = _failed_once()
    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    assert snapshot.definition_digest == run.definition_digest


# ---------------------------------------------------------------------------
# §15.1, §15.2 — the RUN's declared bounds are the authority, not the definition's
# ---------------------------------------------------------------------------


def _run_declaring(definition: WorkflowDefinition, **declared_overrides: int) -> RunRecord:
    """A run record whose DECLARED bounds differ from the definition it names.

    Built through the PARSE path, which is how such a record arrives in practice: a run
    read back from storage. The digest is recomputed, so the record is internally
    consistent — which is exactly the point. A digest cannot tell you that a record is
    declaring the wrong bounds, only that it is declaring them consistently.
    """
    run = start_run(definition=definition, workspace_identity="ws-1", now=T0)
    mapping = run.to_mapping()
    mapping["declared"] = {**mapping["declared"], **declared_overrides}
    mapping[RUN_DIGEST_FIELD] = digest_of(
        {**mapping, RUN_DIGEST_FIELD: ""}, digest_field=RUN_DIGEST_FIELD
    )
    return RunRecord.from_mapping(mapping)


def test_checkpoint_for_uses_the_RUN_declared_checkpoint_count_bound() -> None:
    """§15.1. The definition permits eight; the RUN declared one, and the run governs."""
    definition = make_definition(limits=limits(max_checkpoints=8))
    run = _run_declaring(definition, max_checkpoints=1)

    charged = record_checkpoint(
        run=run,
        checkpoint=checkpoint_for(definition=definition, run=run, now=T1),
        now=T1,
    )

    assert charged.state is WorkflowState.RESOURCE_EXHAUSTED, (
        "the definition's bound governed instead of the run's"
    )
    assert charged.reached_bound == "CHECKPOINT_COUNT_BOUND_REACHED"


def test_checkpoint_for_uses_the_RUN_declared_checkpoint_byte_bound() -> None:
    """The same for bytes: the definition allows 64 KiB, the run allows one byte."""
    definition = make_definition(
        limits=limits(max_checkpoints=100, max_checkpoint_bytes=65536)
    )
    run = _run_declaring(definition, max_checkpoint_bytes=1)

    with pytest.raises(InvalidRecord) as raised:
        checkpoint_for(definition=definition, run=run, now=T1)

    assert raised.value.reason_code == "CHECKPOINT_BYTES_BOUND_REACHED"


def test_a_run_record_with_no_declared_bounds_is_refused() -> None:
    """§15.2. A bound that is not a number bounds nothing, and reading one is how a
    limit would silently become unlimited."""
    definition, run = _failed_once()
    stripped = dataclasses.replace(run, declared={})

    with pytest.raises(InvalidRecord):
        checkpoint_for(definition=definition, run=stripped, now=T1)


# ---------------------------------------------------------------------------
# §14 — the workflow state is not a field a caller may set
# ---------------------------------------------------------------------------


def test_a_successor_cannot_declare_a_run_completed() -> None:
    """§14. COMPLETED is what a run IS when every declared step has succeeded.

    A caller asserting it about a run whose steps have not run is not describing the
    run; it is describing what it would like the record to say.
    """
    _, run = _failed_once()
    assert run.state is WorkflowState.RUNNING
    assert run.step("s2").state is not StepState.SUCCEEDED

    with pytest.raises(InvalidRecord):
        run.advance(state=WorkflowState.COMPLETED)


def test_a_successor_cannot_move_the_run_to_another_non_terminal_state() -> None:
    """§14. A run becomes terminal or stays where it is."""
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(state=WorkflowState.CREATED)


def test_a_successor_cannot_succeed_a_step_with_no_attempt_behind_it() -> None:
    """§15.2. A step's state is what its ATTEMPTS did.

    A SUCCEEDED step with no new attempt is a claim nothing in the record supports —
    and it is also how the step deadline would be released without anything running.
    """
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(steps=_with_step(run, "s1", state=StepState.SUCCEEDED))


def test_a_successor_cannot_move_a_step_the_run_is_not_on() -> None:
    """§6.1. Steps run in their declared order, so a later step cannot finish first."""
    _, run = _failed_once()
    assert run.step("s1").state is StepState.READY

    with pytest.raises(InvalidRecord):
        run.advance(steps=_with_step(run, "s2", state=StepState.SUCCEEDED))


# ---------------------------------------------------------------------------
# §8.3 — the deadline is released by ITS step succeeding, and nothing else
# ---------------------------------------------------------------------------


def test_the_step_deadline_is_released_only_by_its_step_SUCCEEDING() -> None:
    """The rule that a set-difference approximation gets wrong.

    "Some step succeeded" would be satisfied by step two finishing while step one's
    bound is released. Here the CURRENT step moves, an attempt behind it is recorded,
    and the transition is otherwise well formed — and it is still refused, because the
    step did not SUCCEED.
    """
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    assert reserved.inflight_attempt_no == 2

    refusing = _attempt(reserved, "s1", 2, execution_id="exec-refused")
    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved,
                "s1",
                state=StepState.FAILED,
                attempts=reserved.attempts_for("s1") + (refusing,),
            ),
            step_deadline=None,
            inflight_attempt_no=None,
        )


def test_the_step_deadline_cannot_be_released_by_another_step_succeeding() -> None:
    """The same escape by the other route: succeed a DIFFERENT step."""
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    succeeded = _attempt(reserved, "s2", 1, execution_id="exec-s2", succeeded=True)

    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved,
                "s2",
                state=StepState.SUCCEEDED,
                attempts=reserved.attempts_for("s2") + (succeeded,),
            ),
            step_deadline=None,
            inflight_attempt_no=None,
        )


# ---------------------------------------------------------------------------
# §6.1 — the step sequence is the definition's
# ---------------------------------------------------------------------------


def test_a_successor_cannot_add_a_step() -> None:
    """A record free to add a step describes a different workflow than the run bound
    to, and §5 binds the run to the definition's step sequence."""
    _, run = _failed_once()
    extra = StepRecord(step_id="s9", state=StepState.PENDING)

    with pytest.raises(InvalidRecord):
        run.advance(steps=run.steps + (extra,))


def test_a_successor_cannot_reorder_steps() -> None:
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(steps=tuple(reversed(run.steps)))


# ---------------------------------------------------------------------------
# §6.3 — attempt numbering
# ---------------------------------------------------------------------------


def test_a_successor_cannot_skip_an_attempt_number() -> None:
    """§6.3. The count increases by exactly one per attempt."""
    _, run = _failed_once()
    assert run.next_attempt_no() == 2

    with pytest.raises(InvalidRecord):
        run.advance(
            inflight_attempt_no=99,
            consumed_total_attempts=run.consumed_total_attempts + 1,
        )


def test_an_attempt_number_is_not_reused_after_a_lineage_that_starts_late() -> None:
    """§6.3, and the reason the in-flight number is persisted at all.

    A run whose first attempt died before it could be written has a lineage beginning at
    2. The next number has to come from the last RECORDED attempt, not from how many
    records there are — one record would otherwise hand out 2 a second time.
    """
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    start = start_run(definition=definition, workspace_identity="ws-1", now=T0)
    interrupted = begin_attempt(definition=definition, run=start, now=T0)
    resumed = begin_attempt(definition=definition, run=interrupted.run, now=T1)
    assert resumed.attempt_id.attempt_no == 2

    # Phase two of the resumed attempt, NOT `advance` — which would begin ANOTHER
    # attempt and move the number on again before anything was recorded.
    after = complete_attempt(
        definition=definition, plan=resumed, executor=AlwaysFailsExecutor()
    )
    assert [a.attempt_id.attempt_no for a in after.attempts_for("s1")] == [2]

    nxt = begin_attempt(
        definition=definition, run=after, now="2026-10-03T10:00:20Z"
    )
    assert nxt.attempt_id.attempt_no == 3, "attempt 2 was handed out twice"


def test_a_successor_cannot_record_an_attempt_the_run_never_reserved() -> None:
    """The rule that ties the lineage to the counter: an attempt may only be RECORDED
    if it was RESERVED, and its number is the reserved one."""
    _, run = _failed_once()
    assert run.inflight_attempt_no is None
    unreserved = _attempt(run, "s1", 2, execution_id="exec-unreserved")

    with pytest.raises(InvalidRecord):
        run.advance(
            steps=_with_step(
                run, "s1", attempts=run.attempts_for("s1") + (unreserved,)
            ),
            inflight_attempt_no=None,
        )


def test_a_successor_cannot_record_an_attempt_from_another_run() -> None:
    """§6.3. An AttemptId is (run_id, step_id, attempt_no), and all three are this
    run's."""
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    foreign = AttemptRecord(
        attempt_id=AttemptId(run_id="run-someone-else", step_id="s1", attempt_no=2),
        execution_id="exec-foreign",
        failure_class=FailureClass.TERMINAL_FAILURE,
        reason_code="REFUSED",
        started_at=T1,
        ended_at=T1,
        succeeded=False,
    )

    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved, "s1", attempts=reserved.attempts_for("s1") + (foreign,)
            ),
            inflight_attempt_no=None,
        )


def test_a_successor_cannot_record_an_attempt_under_another_step() -> None:
    """The same for the step half of the identity."""
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    mislabelled = AttemptRecord(
        attempt_id=AttemptId(run_id=reserved.run_id, step_id="s2", attempt_no=2),
        execution_id="exec-mislabelled",
        failure_class=FailureClass.TERMINAL_FAILURE,
        reason_code="REFUSED",
        started_at=T1,
        ended_at=T1,
        succeeded=False,
    )

    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved, "s1", attempts=reserved.attempts_for("s1") + (mislabelled,)
            ),
            inflight_attempt_no=None,
        )


# ---------------------------------------------------------------------------
# §6.3, §12 — the in-flight number and the counter move together
# ---------------------------------------------------------------------------


def test_a_successor_cannot_reserve_an_attempt_without_spending_one() -> None:
    """§15.1. An attempt is counted when it BEGINS, so the two move together."""
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(inflight_attempt_no=2)


def test_a_successor_cannot_spend_an_attempt_without_reserving_one() -> None:
    """The converse, and the one that stops a run being charged for nothing."""
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(consumed_total_attempts=run.consumed_total_attempts + 1)


def test_a_successor_cannot_lower_the_checkpoint_count() -> None:
    """§12, §15.1. Discarding a checkpoint cannot restore the budget to write one —
    and neither can a successor that rewrites the counter the bound is read from."""
    definition, run = _failed_once()
    charged = record_checkpoint(
        run=run,
        checkpoint=checkpoint_for(definition=definition, run=run, now=T1),
        now=T1,
    )
    assert charged.consumed_checkpoints == 1

    with pytest.raises(InvalidRecord):
        charged.advance(consumed_checkpoints=0)


# ---------------------------------------------------------------------------
# §6.3 — one execution, one attempt
# ---------------------------------------------------------------------------


def test_a_successor_cannot_point_two_attempts_at_one_execution() -> None:
    """§6.3. "A retry lineage is a sequence of AttemptIds, each pointing at a DISTINCT
    ExecutionId — never one ExecutionId with a counter on it."

    The engine refuses a reuse when it sees one, but that is the engine choosing to
    check. This is the record's own rule, and it holds for a lineage assembled by
    anyone.
    """
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    earlier = reserved.attempts_for("s1")[0].execution_id
    duplicate = _attempt(reserved, "s1", 2, execution_id=earlier)

    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved, "s1", attempts=reserved.attempts_for("s1") + (duplicate,)
            ),
            inflight_attempt_no=None,
        )


def test_an_engine_retry_with_a_new_execution_id_is_accepted() -> None:
    """The control. A retry that produced its OWN execution is exactly what §6.3 asks
    for, and refusing it would make the rule useless rather than strict."""
    definition, run = _failed_once()

    after = advance(
        definition=definition, run=run, executor=RecordingExecutor(), now=T1
    )

    produced = [a.execution_id for r in after.steps for a in r.attempts]
    assert len(produced) == 2
    assert len(set(produced)) == 2, "the retry reused an ExecutionId"


# ---------------------------------------------------------------------------
# §9, §15.2 — an attempt's outcome and the step it moved
# ---------------------------------------------------------------------------


def test_a_failed_attempt_cannot_make_its_step_SUCCEEDED() -> None:
    """§15.2. A step's state is what its ATTEMPTS did.

    This buys more than a false record. A SUCCEEDED step releases its deadline, so a
    failure disguised as a success also grants the next attempt a whole fresh step
    budget — the disguise pays for itself.
    """
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    failing = _attempt(reserved, "s1", 2, execution_id="exec-failing")

    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved,
                "s1",
                state=StepState.SUCCEEDED,
                attempts=reserved.attempts_for("s1") + (failing,),
            ),
            step_deadline=None,
            inflight_attempt_no=None,
        )


def test_a_successful_attempt_can_make_its_step_SUCCEEDED() -> None:
    """The control, and the transition the engine performs on every success."""
    definition, run = _failed_once()
    reserved = begin_attempt(definition=definition, run=run, now=T1).run
    passing = _attempt(
        reserved, "s1", 2, execution_id="exec-passing", succeeded=True
    )

    after = reserved.advance(
        steps=_with_step(
            reserved,
            "s1",
            state=StepState.SUCCEEDED,
            attempts=reserved.attempts_for("s1") + (passing,),
        ),
        step_deadline=None,
        inflight_attempt_no=None,
    )

    assert after.step("s1").state is StepState.SUCCEEDED
    assert after.step_deadline is None


def test_an_attempt_cannot_have_succeeded_and_carried_a_failure() -> None:
    """§9. An outcome and a classification are one fact, not two fields.

    §9.1's "matched none of the nine" stays `failure_class is None`; there is no tenth
    member and no UNKNOWN for a success to smuggle a class through.
    """
    with pytest.raises(InvalidRecord):
        AttemptRecord(
            attempt_id=AttemptId(run_id="run-1", step_id="s1", attempt_no=1),
            execution_id="exec-1",
            failure_class=FailureClass.TERMINAL_FAILURE,
            reason_code="REFUSED",
            started_at=T1,
            ended_at=T1,
            succeeded=True,
        )


def test_the_engines_success_and_failure_paths_still_move_their_steps() -> None:
    """The control over both halves: what the engine actually does is not refused."""
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    run = start_run(definition=definition, workspace_identity="ws-1", now=T0)

    failed = advance(
        definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T0
    )
    assert failed.step("s1").state is StepState.READY, "a retryable failure is a retry"

    succeeded = advance(
        definition=definition, run=failed, executor=RecordingExecutor(), now=T1
    )
    assert succeeded.step("s1").state is StepState.SUCCEEDED
    assert succeeded.step_deadline is None, "a succeeded step kept its bound"
    assert len(succeeded.attempts_for("s1")) == 2


# ---------------------------------------------------------------------------
# §15.2 — reached_bound is a FACT
# ---------------------------------------------------------------------------


def test_a_non_terminal_run_cannot_name_a_bound() -> None:
    """A run reaches a bound when one STOPS it, and a run still going has not been
    stopped."""
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(reached_bound="WORKFLOW_DEADLINE_REACHED")


@pytest.mark.parametrize(
    ("state", "extra"),
    [
        (WorkflowState.FAILED, {}),
        (WorkflowState.BLOCKED, {}),
        (WorkflowState.CANCELLED, {"cancelled_by": "operator-li", "cancelled_reason": "SUPERSEDED"}),
    ],
)
def test_a_run_that_reached_no_bound_cannot_name_one(
    state: WorkflowState, extra: dict[str, str]
) -> None:
    """§15.2. "which bound the run reached, IF it reached one".

    Naming one on a run that failed or was cancelled attributes the stop to a limit
    nothing touched — which is worse than saying nothing, because a reader would act on
    it.
    """
    _, run = _failed_once()

    with pytest.raises(InvalidRecord):
        run.advance(state=state, reached_bound="ATTEMPT_BOUND_REACHED", **extra)


def test_a_completed_run_cannot_name_a_bound() -> None:
    """A run that FINISHED reached no bound."""
    definition, run = _failed_once()
    done = advance(
        definition=definition, run=run, executor=RecordingExecutor(), now=T1
    )
    assert done.step("s1").state is StepState.SUCCEEDED
    assert done.step("s2").state is not StepState.SUCCEEDED

    reserved = begin_attempt(definition=definition, run=done, now=T2).run
    passing = _attempt(reserved, "s2", 1, execution_id="exec-s2", succeeded=True)

    with pytest.raises(InvalidRecord):
        reserved.advance(
            steps=_with_step(
                reserved,
                "s2",
                state=StepState.SUCCEEDED,
                attempts=reserved.attempts_for("s2") + (passing,),
            ),
            state=WorkflowState.COMPLETED,
            reached_bound="ATTEMPT_BOUND_REACHED",
            inflight_attempt_no=None,
        )


def test_the_engines_bound_reaching_paths_still_name_their_reason() -> None:
    """The controls. Every bound the engine can reach keeps working."""
    deadline_definition = make_definition(
        limits=limits(workflow_seconds=5, step_seconds=600)
    )
    timed_out = advance(
        definition=deadline_definition,
        run=start_run(
            definition=deadline_definition, workspace_identity="ws-1", now=T0
        ),
        executor=RecordingExecutor(),
        now="2026-10-03T10:00:05Z",
    )
    assert timed_out.state is WorkflowState.TIMED_OUT
    assert timed_out.reached_bound == "WORKFLOW_DEADLINE_REACHED"

    attempts_definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=2, attempts_total=10),
        retry_policy=a_retry_policy(max_attempts=2),
    )
    executor = AlwaysFailsExecutor()
    exhausted = start_run(
        definition=attempts_definition, workspace_identity="ws-1", now=T0
    )
    exhausted = advance(
        definition=attempts_definition, run=exhausted, executor=executor, now=T0
    )
    exhausted = advance(
        definition=attempts_definition, run=exhausted, executor=executor, now=T1
    )
    assert exhausted.state is WorkflowState.RESOURCE_EXHAUSTED
    assert exhausted.reached_bound == "ATTEMPT_BOUND_REACHED"


# ---------------------------------------------------------------------------
# §15.2 — the declared bounds are frozen, not merely un-assignable
# ---------------------------------------------------------------------------


def test_the_declared_bounds_cannot_be_edited_in_place() -> None:
    """`frozen=True` stops `run.declared = ...`. It does nothing about
    `run.declared["x"] = ...`, which edits the bound EVERY limit in the phase is
    enforced from — behind `advance`, behind `_verify_successor`, and behind the digest,
    which was computed over the values as they were.
    """
    definition, run = _failed_once()
    before = run.declared_limit("attempts_total")

    with pytest.raises(TypeError):
        run.declared["attempts_total"] = 999_999

    assert run.declared_limit("attempts_total") == before


def test_the_declared_bounds_survive_a_round_trip_still_frozen() -> None:
    """And the serialized form stays an ordinary mapping, so a record reads and writes
    as it always did."""
    definition, run = _failed_once()
    restored = RunRecord.from_mapping(run.to_mapping())

    for name in (
        "workflow_seconds",
        "step_seconds",
        "attempts_per_step",
        "attempts_total",
        "max_checkpoints",
        "max_checkpoint_bytes",
        "max_artifact_bytes",
    ):
        assert restored.declared_limit(name) == run.declared_limit(name), name

    assert isinstance(restored.to_mapping()["declared"], dict), (
        "the serialized form must stay an ordinary, serializable mapping"
    )
    with pytest.raises(TypeError):
        restored.declared["attempts_total"] = 1


def test_the_declared_bounds_are_copied_away_from_their_source() -> None:
    """A read-only VIEW over a mapping someone else still holds is a lock whose key is
    on the table: the holder mutates the original and the record changes underneath."""
    source = {"attempts_total": 4, "max_checkpoints": 8}
    definition, run = _failed_once()
    built = dataclasses.replace(run, declared=source)

    source["attempts_total"] = 999_999

    assert built.declared_limit("attempts_total") == 4, (
        "the record's bounds followed a mapping it does not own"
    )
