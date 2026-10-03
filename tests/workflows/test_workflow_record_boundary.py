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
from workflows.engine import advance, begin_attempt, checkpoint_for, record_checkpoint, start_run
from workflows.errors import InvalidRecord
from workflows.run import RUN_DIGEST_FIELD, RunRecord
from workflows.vocabulary import WorkflowState

from tests.workflows.conftest import (
    T0,
    T1,
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


# ---------------------------------------------------------------------------
# What a successor may not erase
# ---------------------------------------------------------------------------


def test_a_successor_cannot_delete_a_recorded_attempt() -> None:
    """§15.2. A spent attempt cannot be unspent."""
    _, run = _failed_once()
    assert len(run.attempts_for("s1")) == 1

    with pytest.raises(InvalidRecord):
        run.with_step("s1", attempts=())


def test_a_successor_cannot_renumber_a_recorded_attempt() -> None:
    """§6.3. An attempt number is never reused or renumbered."""
    _, run = _failed_once()
    recorded = run.attempts_for("s1")[0]
    renumbered = dataclasses.replace(
        recorded, attempt_id=dataclasses.replace(recorded.attempt_id, attempt_no=7)
    )

    with pytest.raises(InvalidRecord):
        run.with_step("s1", attempts=(renumbered,))


def test_a_successor_cannot_rewrite_a_recorded_attempt() -> None:
    """§15.2. The ledger records what an attempt WAS, not what it would be convenient
    for it to have been."""
    _, run = _failed_once()
    recorded = run.attempts_for("s1")[0]
    rewritten = dataclasses.replace(recorded, reason_code="NEVER_HAPPENED")

    with pytest.raises(InvalidRecord):
        run.with_step("s1", attempts=(rewritten,))


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
