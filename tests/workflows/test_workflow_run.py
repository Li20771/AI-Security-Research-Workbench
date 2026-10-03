"""AI-13-B — T1, T11, T12, T13, T14, T15, T17, T25: running, and what stops it.

Every bound here is exercised at a DECLARED instant rather than by waiting, because
§10.3.1 makes a bound something evaluated before an attempt begins. A test that slept
would be testing the clock.
"""

from __future__ import annotations

import pytest

from workflows.definition import WorkflowDefinition
from workflows.engine import (
    advance,
    cancel,
    checkpoint_for,
    start_run,
    terminal_state_for,
)
from workflows.errors import InvalidDefinition
from workflows.vocabulary import NEVER_RETRIED, FailureClass, StepState, WorkflowState

from tests.workflows.conftest import (
    a_step,
    FAR_SECONDS,
    STEP_TIMEOUT_SECONDS,
    T0,
    T1,
    T2,
    AlwaysFailsExecutor,
    FailOnceExecutor,
    ReusingExecutor,
    RecordingExecutor,
    WideningExecutor,
    a_retry_policy,
    definition_body,
    limits,
    make_definition,
)

pytestmark = pytest.mark.layer2


def _run(definition: WorkflowDefinition, **kwargs):  # noqa: ANN202
    return start_run(definition=definition, workspace_identity="ws-1", now=T0, **kwargs)


# ---------------------------------------------------------------------------
# The happy path — the control the refusals below would otherwise pass vacuously
# ---------------------------------------------------------------------------


def test_a_run_advances_one_step_at_a_time_and_completes() -> None:
    """§12. One step per advance; nothing runs ahead."""
    definition = make_definition()
    executor = RecordingExecutor()
    run = _run(definition)

    run = advance(definition=definition, run=run, executor=executor, now=T1)
    assert run.state is WorkflowState.RUNNING
    assert len(executor.calls) == 1, "one advance is one attempt, not a loop"
    assert run.step("s1").state is StepState.SUCCEEDED
    assert run.step("s2").state is StepState.PENDING

    run = advance(definition=definition, run=run, executor=executor, now=T2)
    assert run.state is WorkflowState.COMPLETED
    assert run.consumed_total_attempts == 2


def test_a_terminal_run_does_not_advance() -> None:
    definition = make_definition()
    executor = RecordingExecutor()
    run = _run(definition)
    run = advance(definition=definition, run=run, executor=executor, now=T1)
    run = advance(definition=definition, run=run, executor=executor, now=T2)
    assert run.state is WorkflowState.COMPLETED

    again = advance(definition=definition, run=run, executor=executor, now="2026-10-03T11:00:00Z")
    assert again == run
    assert len(executor.calls) == 2


# ---------------------------------------------------------------------------
# T1, T13 — every attempt is its own execution, and inherits nothing
# ---------------------------------------------------------------------------


def test_T13_every_attempt_produces_its_own_execution() -> None:
    """§6.3. A retry lineage is a sequence of AttemptIds at DISTINCT ExecutionIds."""
    definition = make_definition(
        limits=limits(attempts_per_step=3),
        retry_policy=a_retry_policy(max_attempts=3),
    )
    executor = FailOnceExecutor()
    run = _run(definition)

    run = advance(definition=definition, run=run, executor=executor, now=T1)
    run = advance(definition=definition, run=run, executor=executor, now=T2)

    attempts = run.attempts_for("s1")
    assert [a.attempt_id.attempt_no for a in attempts] == [1, 2]
    assert len({a.execution_id for a in attempts}) == 2, "one ExecutionId with a counter"
    assert run.step("s1").state is StepState.SUCCEEDED


def test_T13b_a_reused_execution_id_is_refused() -> None:
    """§6.3. Refused on what the executor REPORTED, not on a promise about it."""
    definition = make_definition(
        steps=[a_step("s1"),
               a_step("s2")]
    )
    executor = ReusingExecutor()
    run = _run(definition)
    run = advance(definition=definition, run=run, executor=executor, now=T1)
    run = advance(definition=definition, run=run, executor=executor, now=T2)

    assert run.state is WorkflowState.FAILED
    assert run.attempts_for("s2")[-1].reason_code == "EXECUTION_ID_REUSED"


def test_T1_a_resumed_attempt_inherits_no_authorization() -> None:
    """§8.2. The structure a resume hands over cannot hold an authorization."""
    from workflows.resume import INHERITED_FIELDS, InheritedState

    assert set(INHERITED_FIELDS) == {"completed_steps", "artifact_refs"}
    assert {field.name for field in __import__("dataclasses").fields(InheritedState)} == set(
        INHERITED_FIELDS
    ), "a third field is how an authorization would arrive, and §8.2 forbids one"


def test_T1b_a_checkpoint_cannot_carry_a_guard_decision_or_an_approval() -> None:
    """The two names a resumed attempt would most likely be handed."""
    from workflows.checkpoint import Checkpoint
    from workflows.errors import InvalidCheckpoint

    for forbidden in ("guard_decision", "approval", "authorization"):
        with pytest.raises(InvalidCheckpoint):
            Checkpoint.from_mapping(
                {
                    "workflow_id": "w", "revision": "v1", "definition_digest": "d",
                    "run_id": "r", "step_id": "s", "attempt_no": 1,
                    "completed_steps": [], "created_at": T0,
                    forbidden: "anything", "checkpoint_digest": "x",
                }
            )


# ---------------------------------------------------------------------------
# T11 — retry does not widen the request
# ---------------------------------------------------------------------------


def test_T11_an_attempt_that_widens_its_request_is_refused() -> None:
    """§10.1. retry is not escalation, widening or relaxation."""
    definition = make_definition()
    run = advance(
        definition=definition, run=_run(definition), executor=WideningExecutor(), now=T1
    )

    assert run.state is WorkflowState.FAILED
    assert run.attempts_for("s1")[-1].reason_code == "RETRY_WIDENED_REQUEST"


def test_T11b_a_faithful_attempt_is_not_refused() -> None:
    """The control: the same engine accepts the request the definition declares."""
    definition = make_definition()
    run = advance(
        definition=definition, run=_run(definition), executor=RecordingExecutor(), now=T1
    )
    assert run.state is WorkflowState.RUNNING
    assert run.step("s1").state is StepState.SUCCEEDED


# ---------------------------------------------------------------------------
# T14, T15 — the failure vocabulary, and what is never retried
# ---------------------------------------------------------------------------


def test_T14_an_unclassified_failure_stops_and_is_never_retried() -> None:
    """§9.1. No class assigned, the execution stops, and no retry is permitted."""
    definition = make_definition(
        retry_policy={
            "policy_id": "p",
            "applies_to": [str(c) for c in FailureClass],
            "max_attempts": 5,
            "retry_seconds": FAR_SECONDS,
        }
    )
    executor = AlwaysFailsExecutor(failure=None)
    run = advance(definition=definition, run=_run(definition), executor=executor, now=T1)

    assert run.state is WorkflowState.FAILED
    assert len(executor.calls) == 1, "an unclassified failure was retried"
    attempt = run.attempts_for("s1")[-1]
    assert attempt.failure_class is None, "a class was assigned to an unclassified failure"
    assert attempt.unclassified


def test_T14b_no_UNKNOWN_member_exists_in_the_vocabulary() -> None:
    """§9.1. The mutation this refuses is "make 'we could not classify this' a class"."""
    assert "UNKNOWN" not in {member.value for member in FailureClass}
    assert len(FailureClass) == 9


@pytest.mark.parametrize("failure", sorted(NEVER_RETRIED, key=str))
def test_T15_a_never_retried_class_is_not_retried(failure: FailureClass) -> None:
    """§9.2, whatever a policy says — including one that covers every class."""
    definition = make_definition(
        retry_policy={
            "policy_id": "p",
            "applies_to": [str(c) for c in FailureClass],
            "max_attempts": 5,
            "retry_seconds": FAR_SECONDS,
        }
    )
    executor = AlwaysFailsExecutor(failure=failure)
    run = advance(definition=definition, run=_run(definition), executor=executor, now=T1)

    assert len(executor.calls) == 1, f"{failure} was retried"
    assert run.is_terminal


def test_T15b_a_retryable_class_with_no_policy_is_not_retried() -> None:
    """§10.3. A workflow that declares no retry policy has no retries."""
    definition = make_definition(retry_policy=None)
    executor = AlwaysFailsExecutor()
    run = advance(definition=definition, run=_run(definition), executor=executor, now=T1)

    assert len(executor.calls) == 1
    assert run.state is WorkflowState.FAILED


def test_T15c_a_retryable_class_a_policy_does_not_cover_is_not_retried() -> None:
    definition = make_definition(
        retry_policy={
            "policy_id": "p",
            "applies_to": ["DEPENDENCY_FAILED"],
            "max_attempts": 3,
            "retry_seconds": FAR_SECONDS,
        }
    )
    executor = AlwaysFailsExecutor(failure=FailureClass.RETRYABLE_FAILURE)
    run = advance(definition=definition, run=_run(definition), executor=executor, now=T1)

    assert len(executor.calls) == 1


def test_T15d_a_class_a_policy_covers_IS_retried() -> None:
    """The control. Without it every refusal above passes vacuously."""
    definition = make_definition(
        retry_policy={
            "policy_id": "p",
            "applies_to": ["RETRYABLE_FAILURE"],
            "max_attempts": 3,
            "retry_seconds": FAR_SECONDS,
        }
    )
    executor = FailOnceExecutor()
    run = _run(definition)
    run = advance(definition=definition, run=run, executor=executor, now=T1)
    assert run.state is WorkflowState.RUNNING and len(executor.calls) == 1

    run = advance(definition=definition, run=run, executor=executor, now=T2)
    assert len(executor.calls) == 2
    assert run.step("s1").state is StepState.SUCCEEDED


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (FailureClass.TIMED_OUT, WorkflowState.TIMED_OUT),
        (FailureClass.RESOURCE_EXHAUSTED, WorkflowState.RESOURCE_EXHAUSTED),
        (FailureClass.CANCELLED, WorkflowState.CANCELLED),
        (FailureClass.BLOCKED_PRECONDITION, WorkflowState.BLOCKED),
        (FailureClass.AUTHORIZATION_DENIED, WorkflowState.BLOCKED),
        (FailureClass.APPROVAL_DENIED, WorkflowState.BLOCKED),
        (FailureClass.DEPENDENCY_FAILED, WorkflowState.FAILED),
    ],
)
def test_T17_a_failure_class_maps_to_its_own_terminal_state(
    failure: FailureClass, expected: WorkflowState
) -> None:
    """§11, §12 name two of these; the rest follow from the failure's own vocabulary."""
    assert terminal_state_for(failure) is expected


# ---------------------------------------------------------------------------
# T12, T25 — bounds, evaluated BEFORE an attempt begins
# ---------------------------------------------------------------------------


def test_T12_the_attempt_bound_stops_a_run_whose_policy_would_retry() -> None:
    """§10.3.1. The narrower bound governs — here, attempts_per_step."""
    definition = make_definition(
        limits=limits(attempts_per_step=2, attempts_total=99),
        retry_policy=a_retry_policy(max_attempts=99),
    )
    executor = AlwaysFailsExecutor()
    run = _run(definition)

    run = advance(definition=definition, run=run, executor=executor, now=T1)
    run = advance(definition=definition, run=run, executor=executor, now=T2)
    assert len(executor.calls) == 2, "the wider policy bound governed"
    assert run.state is WorkflowState.RESOURCE_EXHAUSTED
    assert len(run.attempts_for("s1")) == 2


def test_T12b_the_total_attempt_bound_governs_across_steps() -> None:
    """§10.3.1: total attempts remaining is one of the bounds that can govern."""
    definition = make_definition(
        limits=limits(attempts_per_step=5, attempts_total=1),
        retry_policy=a_retry_policy(max_attempts=5),
    )
    executor = RecordingExecutor()
    run = _run(definition)
    run = advance(definition=definition, run=run, executor=executor, now=T1)
    assert run.consumed_total_attempts == 1

    run = advance(definition=definition, run=run, executor=executor, now=T2)
    assert len(executor.calls) == 1, "a second attempt ran with no total budget left"
    assert run.state is WorkflowState.RESOURCE_EXHAUSTED


def test_T25_an_attempt_at_or_after_the_workflow_deadline_does_not_begin() -> None:
    """§8.3, §10.3.1. Evaluated BEFORE the attempt, not discovered by overrunning it."""
    definition = make_definition(
        limits=limits(workflow_seconds=31, step_seconds=60)
    )
    executor = RecordingExecutor()
    run = _run(definition)

    run = advance(definition=definition, run=run, executor=executor, now="2026-10-03T10:00:31Z")
    assert len(executor.calls) == 0, "an attempt began at or after the deadline"
    assert run.state is WorkflowState.TIMED_OUT


def test_T25b_the_boundary_instant_itself_does_not_begin() -> None:
    """§8.3: a bound is reached when the current time is >= the deadline."""
    definition = make_definition(
        limits=limits(workflow_seconds=30, step_seconds=60)
    )
    executor = RecordingExecutor()
    run = advance(
        definition=definition, run=_run(definition), executor=executor,
        now="2026-10-03T10:00:30Z",
    )
    assert len(executor.calls) == 0
    assert run.state is WorkflowState.TIMED_OUT


def test_T25c_an_attempt_inside_the_deadline_does_begin() -> None:
    """The control for the two above."""
    definition = make_definition(
        limits=limits(workflow_seconds=30, step_seconds=60)
    )
    executor = RecordingExecutor()
    run = advance(
        definition=definition, run=_run(definition), executor=executor,
        now="2026-10-03T10:00:29Z",
    )
    assert len(executor.calls) == 1
    assert run.state is WorkflowState.RUNNING


# ---------------------------------------------------------------------------
# §11.2 — cancellation
# ---------------------------------------------------------------------------


def test_cancellation_is_terminal_and_is_not_retried() -> None:
    definition = make_definition(retry_policy=a_retry_policy(max_attempts=3))
    run = cancel(
        run=_run(definition), cancelled_by="operator-li", reason="SUPERSEDED", now=T1
    )
    assert run.state is WorkflowState.CANCELLED

    executor = RecordingExecutor()
    after = advance(definition=definition, run=run, executor=executor, now=T2)
    assert after == run
    assert len(executor.calls) == 0


def test_cancellation_records_who_and_why_as_references() -> None:
    """§11.2. A cancelled run can answer WHO cancelled it and WHY."""
    definition = make_definition()
    run = cancel(
        run=_run(definition),
        cancelled_by="operator-li",
        reason="OPERATOR_REQUEST",
        now=T1,
    )
    assert run.state is WorkflowState.CANCELLED
    assert run.cancelled_by == "operator-li"
    assert run.cancelled_reason == "OPERATOR_REQUEST"


def test_cancellation_provenance_survives_serialization() -> None:
    """§11.2, §15.2. Both are on the RECORD, so both survive a reload — a provenance
    that only existed in the object that cancelled would be a provenance a reader of the
    ledger could not find."""
    from workflows.run import RunRecord

    definition = make_definition()
    run = cancel(
        run=_run(definition), cancelled_by="operator-li", reason="SUPERSEDED", now=T1
    )

    restored = RunRecord.from_mapping(run.to_mapping())
    assert restored.cancelled_by == "operator-li"
    assert restored.cancelled_reason == "SUPERSEDED"
    assert restored.verify_digest() is None


def test_a_cancelled_run_cannot_advance_or_retry() -> None:
    """§11.2, §9.2. Cancellation is a decision, not an accident — and CANCELLED is on
    the never-retried list, so not even a policy covering it may spend another attempt."""
    definition = make_definition(retry_policy=a_retry_policy(max_attempts=5))
    executor = AlwaysFailsExecutor()
    run = advance(definition=definition, run=_run(definition), executor=executor, now=T1)
    assert run.state is WorkflowState.RUNNING

    run = cancel(
        run=run, cancelled_by="operator-li", reason="OPERATOR_REQUEST", now=T1
    )
    after = advance(definition=definition, run=run, executor=executor, now=T2)

    assert after.state is WorkflowState.CANCELLED
    assert len(executor.calls) == 1, "a cancelled run spent another attempt"


@pytest.mark.parametrize(
    "bad",
    ["has space", "line\nbreak", "a" * 201, "", "semi;colon"],
)
def test_cancellation_refuses_free_form_provenance(bad: str) -> None:
    """§11.2 asks for a declared REFERENCE, and the difference between a reference and
    a sentence is the whole of the rule. A field that could hold a sentence is a field
    that could hold a secret, a transcript, or a judgement AI-13 is not entitled to make.
    """
    from workflows.errors import InvalidRecord

    definition = make_definition()
    with pytest.raises(InvalidRecord):
        cancel(
            run=_run(definition), cancelled_by=bad, reason="OPERATOR_REQUEST", now=T1
        )
    with pytest.raises(InvalidRecord):
        cancel(run=_run(definition), cancelled_by="operator-li", reason=bad, now=T1)


# ---------------------------------------------------------------------------
# §11.2 — the invariant at the CONSTRUCTION boundary, not only in `cancel()`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing",
    ["cancelled_by", "cancelled_reason"],
)
def test_a_CANCELLED_record_cannot_be_constructed_without_who_and_why(missing: str) -> None:
    """§11.2 at the typed-object boundary.

    `cancel()` is a convenience; a rule that lived only there would be a rule a caller
    reaches around by constructing the record directly — the same bypass AI-12-B's
    review found when a caller labelled its own record `MODEL_EXECUTION` and
    manufactured the prerequisite it was supposed to satisfy.
    """
    from dataclasses import replace

    from workflows.errors import InvalidRecord

    definition = make_definition()
    run = _run(definition)
    supplied = {"cancelled_by": "operator-li", "cancelled_reason": "SUPERSEDED"}
    del supplied[missing]

    with pytest.raises(InvalidRecord):
        replace(run, state=WorkflowState.CANCELLED, **supplied)

    # The same refusal through `advance`, which is the path the engine uses.
    with pytest.raises(InvalidRecord):
        run.advance(state=WorkflowState.CANCELLED, **supplied)


def test_a_CANCELLED_record_with_both_is_accepted_and_digests() -> None:
    """The control. Without it the refusals above could be a record that never works."""
    definition = make_definition()
    run = _run(definition)

    cancelled = run.advance(
        state=WorkflowState.CANCELLED,
        cancelled_by="operator-li",
        cancelled_reason="SUPERSEDED",
    )

    assert cancelled.state is WorkflowState.CANCELLED
    assert cancelled.verify_digest() is None


def test_a_record_that_was_not_cancelled_cannot_carry_cancellation_provenance() -> None:
    """The converse. Provenance on a run that was never cancelled is a field that means
    nothing, sitting beside records where the same names mean something."""
    from workflows.errors import InvalidRecord

    definition = make_definition()
    run = _run(definition)

    with pytest.raises(InvalidRecord):
        run.advance(cancelled_by="operator-li", cancelled_reason="SUPERSEDED")


# ---------------------------------------------------------------------------
# §8.3 — the step deadline is anchored BEFORE the execution is entered
# ---------------------------------------------------------------------------


def test_begin_attempt_anchors_the_step_deadline_before_any_execution() -> None:
    """§8.3. Phase one produces a record that already carries the bound.

    `advance` computes the deadline, enters the execution and only then writes the
    successor — so a process ending mid-attempt leaves a record with NO step deadline,
    and the next resume derives a fresh full one. Anchoring it in phase one is what
    makes the record a caller persists before executing already complete.
    """
    from workflows.engine import begin_attempt

    definition = make_definition(limits=limits(step_seconds=30))
    run = _run(definition)
    assert run.step_deadline is None

    plan = begin_attempt(definition=definition, run=run, now=T0)

    assert plan.admitted
    assert plan.run.step_deadline == "2026-10-03T10:00:30Z"
    assert plan.run.inflight_attempt_no == 1
    assert plan.run.consumed_total_attempts == 1, "the attempt was not counted at its start"
    # The other two absolutes are the ones creation fixed, untouched by phase one.
    assert plan.run.workflow_deadline == run.workflow_deadline
    assert plan.run.retry_deadline == run.retry_deadline


def test_the_state_handed_to_the_execution_already_carries_the_bound() -> None:
    """The same fact from the execution's side: there is no window in which the attempt
    is running and the step deadline exists only in a local variable."""
    definition = make_definition(limits=limits(step_seconds=30))
    executor = RecordingExecutor()
    advance(definition=definition, run=_run(definition), executor=executor, now=T0)

    handed = executor.calls[0]["run"]
    assert handed.step_deadline == "2026-10-03T10:00:30Z"
    assert handed.inflight_attempt_no == 1
    assert handed.consumed_total_attempts == 1


# ---------------------------------------------------------------------------
# §7, §15 — the run record is the ledger
# ---------------------------------------------------------------------------


def test_T24_the_run_record_carries_the_counters_a_bound_is_enforced_from() -> None:
    """§15.1. The counters live on the RECORD, and a checkpoint carries none of them."""
    definition = make_definition()
    executor = RecordingExecutor()
    run = _run(definition)
    run = advance(definition=definition, run=run, executor=executor, now=T1)

    checkpoint = checkpoint_for(definition=definition, run=run, now=T1)
    assert run.consumed_total_attempts == 1
    assert len(run.attempts_for("s1")) == 1

    # The checkpoint carries completed steps and references — not counters. A bound can
    # therefore not be read from it, which is what makes discarding one harmless.
    carried = set(checkpoint.body)
    for counter in (
        "consumed_total_attempts",
        "consumed_checkpoints",
        "consumed_artifact_bytes",
        "workflow_deadline",
    ):
        assert counter not in carried, counter


def test_the_run_record_round_trips_through_its_canonical_form() -> None:
    """§15.2. The record a reader trusts most must survive its own encoding.

    Every §15.2 field that is a REFERENCE — the decision id, the bound reached, the
    step's absolute deadline — is carried through `to_mapping` and back, and the digest
    still verifies. A field dropped on the way out is a fact the ledger reports and then
    cannot produce.
    """
    from workflows.run import RunRecord

    definition = make_definition(
        limits=limits(step_seconds=60, max_checkpoints=2),
        retry_policy=a_retry_policy(max_attempts=2),
    )
    run = _run(definition)
    run = advance(
        definition=definition,
        run=run,
        executor=RecordingExecutor(outcomes=[False], decision_id="dec-1"),
        now=T1,
    )
    assert run.attempts_for("s1")[-1].decision_id == "dec-1"

    restored = RunRecord.from_mapping(run.to_mapping())
    assert restored.to_mapping() == run.to_mapping()
    assert restored.verify_digest() is None
    assert restored.step_deadline == run.step_deadline == "2026-10-03T10:01:10Z"


def test_T24b_the_bounds_module_cannot_read_a_checkpoint() -> None:
    """§15.1, structurally. A module that COULD enforce a bound from a checkpoint is
    how the escapable version gets written, so the import is asserted absent.

    It reads the source of the module that was IMPORTED, not a path assembled from the
    working directory. The two are the same file in an ordinary run and different files
    under the mutation harness, and a rule asserted about a path rather than about the
    code in use is a rule that cannot be shown to be load-bearing.
    """
    import pathlib

    import workflows.policy as policy_module

    from tests.workflows.conftest import imported_modules

    assert policy_module.__file__ is not None
    imported = imported_modules(pathlib.Path(policy_module.__file__))

    assert "workflows.checkpoint" not in imported, (
        "workflows/policy.py imports the checkpoint module; every bound must be "
        "computed from the definition and the run record (§15.1)"
    )
