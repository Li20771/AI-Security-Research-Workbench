"""AI-13-C — the approval point: §13's boundary, and the gate Amendment 4 added.

Two things are being proven here, and they are different:

```text
§13.2, §13.3   identity — an approval answers ONE scope, and only the designated
               ingress can produce one
§13.1.2        admission — an attempt at a gated step does not begin without one
```

The second is why most of these tests are boundary tests rather than happy paths. Before
Amendment 4 an approval was a RECORD the engine consulted when convenient; T26 and T28
are the tests that fail if it ever becomes one again.
"""

from __future__ import annotations

import pytest

from workflows.approval import ApprovalScope
from workflows.definition import WorkflowDefinition
from workflows.engine import (
    advance,
    begin_attempt,
    reenter_approval,
    resolve_approval,
    start_run,
)
from workflows.errors import InvalidRecord
from workflows.ingress import ApprovalRefused
from workflows.vocabulary import StepState, WorkflowState

from tests.workflows.conftest import (
    T0,
    T1,
    T2,
    AlwaysFailsExecutor,
    RecordingExecutor,
    SigningAuthority,
    a_gated_definition,
    a_retry_policy,
    a_waiting_run,
    limits,
)

pytestmark = pytest.mark.layer2


def _an_attempt(run, step_id: str, attempt_no: int, execution_id: str):
    """An attempt a caller built by hand, for a transition the engine never performs."""
    from workflows.run import AttemptId, AttemptRecord
    from workflows.vocabulary import FailureClass

    return AttemptRecord(
        attempt_id=AttemptId(run_id=run.run_id, step_id=step_id, attempt_no=attempt_no),
        execution_id=execution_id,
        failure_class=FailureClass.TERMINAL_FAILURE,
        reason_code="REFUSED",
        started_at=T2,
        ended_at=T2,
        succeeded=False,
    )


def _scope_for(run, definition, attempt_no: int) -> ApprovalScope:
    """The scope of the step the approval point GATES, for one attempt number."""
    gated = definition.gated_step("gate")
    assert gated is not None
    return ApprovalScope(
        workflow_id=run.workflow_id,
        revision=run.revision,
        definition_digest=run.definition_digest,
        run_id=run.run_id,
        step_id=gated.step_id,
        attempt_no=attempt_no,
    )


def _approved_for_attempt_one(ingress: SigningAuthority, definition: WorkflowDefinition):
    """A run whose gated step holds an accepted approval for attempt 1."""
    run = a_waiting_run(definition)
    scope = _scope_for(run, definition, 1)
    return resolve_approval(
        definition=definition, run=run, artifact=ingress.sign(scope), now=T1
    )


def _failed_once(ingress: SigningAuthority):
    """The state CASE A starts from: attempt 1 approved, run, and failed retryably.

    It DECLARES a retry policy, because without one a retryable failure has no retry and
    §10.3 ends the run — which is the right behaviour and the wrong starting point for a
    test about what happens when a retry is available.
    """
    definition = a_gated_definition(retry_policy=a_retry_policy(max_attempts=3))
    run = _approved_for_attempt_one(ingress, definition)
    executor = AlwaysFailsExecutor()
    run = advance(definition=definition, run=run, executor=executor, now=T2)
    assert len(executor.calls) == 1
    assert run.step("work").state is StepState.READY
    return definition, run


# ---------------------------------------------------------------------------
# §13.1.1 — arriving at the point
# ---------------------------------------------------------------------------


def test_arriving_at_an_approval_point_waits_without_running_anything(monkeypatch) -> None:
    """§13.1.2. The wait changes two states and nothing else."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()

    run = a_waiting_run(definition)

    assert run.state is WorkflowState.AWAITING_APPROVAL
    assert run.step("gate").state is StepState.AWAITING_APPROVAL
    assert run.step("work").state is StepState.READY, "the gated step was touched"
    assert run.attempts_for("work") == (), "the wait created an attempt"
    assert run.consumed_total_attempts == 0
    assert run.approvals == ()


def test_a_deployment_with_no_designated_anchor_blocks_the_step(monkeypatch) -> None:
    """§13.3. With no ingress every approval step is BLOCKED — fail-closed, now rather
    than after a deadline nothing could meet."""
    monkeypatch.delenv("WORKBENCH_APPROVAL_TRUST_ANCHOR", raising=False)
    definition = a_gated_definition()

    run = a_waiting_run(definition)

    assert run.state is WorkflowState.BLOCKED
    assert run.step("gate").state is StepState.BLOCKED


# ---------------------------------------------------------------------------
# §13.2 — the scope, and what it binds
# ---------------------------------------------------------------------------


def test_the_scope_preimage_is_exactly_the_six_fields() -> None:
    """§13.2. "exactly these six fields and nothing else"."""
    from workflows.approval import SCOPE_FIELDS

    assert SCOPE_FIELDS == (
        "workflow_id",
        "revision",
        "definition_digest",
        "run_id",
        "step_id",
        "attempt_no",
    )


@pytest.mark.parametrize(
    ("field", "other"),
    [
        ("workflow_id", "wf-other"),
        ("revision", "v9"),
        ("definition_digest", "f" * 64),
        ("run_id", "run-someone-else"),
        ("step_id", "another-step"),
        ("attempt_no", 2),
    ],
)
def test_changing_any_one_of_the_six_changes_the_digest(field: str, other: object) -> None:
    """T3. "changing ANY ONE of the six produces a different scope_digest"."""
    base = ApprovalScope(
        workflow_id="wf", revision="v1", definition_digest="d" * 64,
        run_id="run-1", step_id="work", attempt_no=1,
    )
    changed = ApprovalScope(**{**base.to_body(), field: other})  # type: ignore[arg-type]

    assert changed.digest != base.digest, field


def test_the_scope_is_not_inherited_across_attempts(monkeypatch) -> None:
    """T2, mechanically. Same run, same step, same revision, same digest — FOUR of the
    six, and four is not six."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)

    assert run.approval_covers("work", 1)
    assert not run.approval_covers("work", 2)

    first = _scope_for(run, definition, 1)
    second = _scope_for(run, definition, 2)
    assert first.digest != second.digest


# ---------------------------------------------------------------------------
# §13.3 — the ingress, and what a forgery is
# ---------------------------------------------------------------------------


def test_an_approval_from_the_designated_ingress_is_accepted(monkeypatch) -> None:
    """The control. Without it every refusal below would prove nothing."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)

    accepted = resolve_approval(
        definition=definition,
        run=run,
        artifact=ingress.sign(_scope_for(run, definition, 1)),
        now=T1,
    )

    assert accepted.state is WorkflowState.RUNNING
    assert accepted.step("gate").state is StepState.SUCCEEDED
    assert accepted.step("work").state is StepState.READY, "acceptance touched the gated step"
    assert accepted.attempts_for("work") == (), "acceptance created an attempt"
    assert accepted.consumed_total_attempts == 0
    assert len(accepted.approvals) == 1


def test_T4_a_forged_human_approval_is_refused(monkeypatch) -> None:
    """T4. §13.3. A record that declares `actor_kind = HUMAN`, carries a well-formed
    timestamp and an exact scope digest — and was signed by SOMEONE ELSE.

    Both halves of §13.3.1 are required, and this is the half that matters: the fields
    are perfect, and perfect fields prove a string rather than a human.
    """
    designated = SigningAuthority()
    designated.install(monkeypatch)
    forger = SigningAuthority()

    definition = a_gated_definition()
    run = a_waiting_run(definition)
    forged = forger.sign(_scope_for(run, definition, 1))

    assert forged.actor_kind.value == "HUMAN"
    with pytest.raises(ApprovalRefused):
        resolve_approval(definition=definition, run=run, artifact=forged, now=T1)

    assert run.approvals == (), "a forgery reached the ledger"


@pytest.mark.parametrize("actor_kind", ["AGENT", "MODEL", "SERVICE"])
def test_T4b_an_agent_a_model_or_a_service_cannot_approve(monkeypatch, actor_kind: str) -> None:
    """T4's other half. §13.3.1: those checks are NECESSARY and this is one of them —
    the signature verifies, and the actor is still not a human."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)

    artifact = ingress.sign(_scope_for(run, definition, 1), actor_kind=actor_kind)
    with pytest.raises(ApprovalRefused):
        resolve_approval(definition=definition, run=run, artifact=artifact, now=T1)


def test_the_runs_own_identity_cannot_be_the_approver(monkeypatch) -> None:
    """§13.3.1. "an approval whose actor is the run's own identity ... is REFUSED"."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)

    artifact = ingress.sign(_scope_for(run, definition, 1), actor_reference=run.run_id)
    with pytest.raises(ApprovalRefused):
        resolve_approval(definition=definition, run=run, artifact=artifact, now=T1)


def test_an_approval_for_another_scope_is_refused(monkeypatch) -> None:
    """§13.2. A digest that does not match is a DIFFERENT scope, not a near miss."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)

    elsewhere = ApprovalScope(
        workflow_id=run.workflow_id, revision=run.revision,
        definition_digest=run.definition_digest, run_id=run.run_id,
        step_id="work", attempt_no=7,
    )
    with pytest.raises(ApprovalRefused):
        resolve_approval(
            definition=definition, run=run, artifact=ingress.sign(elsewhere), now=T1
        )


def test_a_tampered_artifact_is_refused(monkeypatch) -> None:
    """The signature covers every field, so changing one byte stops it verifying."""
    import dataclasses

    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)

    good = ingress.sign(_scope_for(run, definition, 1))
    tampered = dataclasses.replace(good, actor_reference="someone-else")

    with pytest.raises(ApprovalRefused):
        resolve_approval(definition=definition, run=run, artifact=tampered, now=T1)


# ---------------------------------------------------------------------------
# §13.4 — denial and the deadline
# ---------------------------------------------------------------------------


def test_T5_a_denied_approval_is_terminal_and_is_not_re_asked(monkeypatch) -> None:
    """§13.4. "Re-asking a human who has answered is pressure, not process." """
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)

    denied = resolve_approval(
        definition=definition,
        run=run,
        artifact=ingress.sign(_scope_for(run, definition, 1), decision="DENIED"),
        now=T1,
    )

    assert denied.is_terminal
    assert denied.state is WorkflowState.BLOCKED
    assert denied.step("gate").state is StepState.BLOCKED
    assert denied.approvals == (), "a denial was recorded as an approval"

    with pytest.raises(InvalidRecord):
        reenter_approval(definition=definition, run=denied, now=T2)


def test_T6_an_approval_that_misses_its_deadline_is_denied(monkeypatch) -> None:
    """§13.4. "not a silent wait. There is no open-ended pending state." """
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    run = a_waiting_run(definition)
    assert run.approval_deadline is not None

    after = advance(
        definition=definition,
        run=run,
        executor=RecordingExecutor(),
        now=run.approval_deadline,
    )

    assert after.is_terminal
    assert after.state is WorkflowState.BLOCKED
    assert after.approvals == ()


def test_waiting_consumes_the_runs_own_deadline(monkeypatch) -> None:
    """§8.3. "TIME SPENT AWAITING AN APPROVAL ... consume[s] the run's deadline." """
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition(
        limits=limits(workflow_seconds=5, step_seconds=600)
    )
    run = a_waiting_run(definition)
    assert run.workflow_deadline == "2026-10-03T10:00:05Z"

    after = advance(
        definition=definition,
        run=run,
        executor=RecordingExecutor(),
        now="2026-10-03T10:00:05Z",
    )

    assert after.state is WorkflowState.TIMED_OUT
    assert after.workflow_deadline == run.workflow_deadline, "the deadline moved"


# ---------------------------------------------------------------------------
# T26 — THE ADMISSION GATE (Amendment 4)
# ---------------------------------------------------------------------------


def test_T26_a_gated_attempt_without_a_covering_approval_is_not_admitted(monkeypatch) -> None:
    """T26. SECURITY BOUNDARY. §13.1.2.

    Attempt 1 is approved and fails retryably. Attempt 2 has NO approval covering it, so
    it MUST NOT begin — and the refusal must be a PRECONDITION rather than a failure:
    nothing reserved, nothing counted, no execution, no ExecutionId, and NOT a terminal
    state, because §9's nine classes classify what went wrong and nothing did.
    """
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)

    assert not run.approval_covers("work", 2)

    idle = RecordingExecutor()
    after = advance(definition=definition, run=run, executor=idle, now=T2)

    assert len(idle.calls) == 0, "an attempt began with no approval covering its number"
    assert after == run, "the refusal altered the record"
    assert after.consumed_total_attempts == 1, "an attempt was counted"
    assert after.inflight_attempt_no is None, "an attempt was reserved"
    assert after.attempts_for("work") == run.attempts_for("work"), "an attempt was recorded"
    assert after.is_terminal is False, "the refusal was hidden behind a terminal state"
    assert after.state is WorkflowState.RUNNING


def test_T26b_an_approval_for_another_step_does_not_admit_this_one(monkeypatch) -> None:
    """The gate asks about THIS step and THIS number, not about approvals in general."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)

    # An approval that exists, for a scope this attempt is not in.
    assert len(run.approvals) == 1
    assert run.approvals[0].step_id == "work"
    assert run.approvals[0].attempt_no == 1
    assert not run.approval_covers("work", 2)


# ---------------------------------------------------------------------------
# T27 — CASE A: retryable failure, explicit retry
# ---------------------------------------------------------------------------


def test_T27_a_retryable_failure_reaches_a_fresh_approval_for_the_next_attempt(monkeypatch) -> None:
    """T27. CASE A of Amendment 4, end to end."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)

    retried = reenter_approval(definition=definition, run=run, now=T2)
    assert retried.state is WorkflowState.AWAITING_APPROVAL
    assert retried.step("gate").state is StepState.AWAITING_APPROVAL
    assert retried.approvals == run.approvals, "the re-entry reused or dropped an approval"
    assert retried.consumed_total_attempts == run.consumed_total_attempts

    scope_two = _scope_for(retried, definition, 2)
    approved = resolve_approval(
        definition=definition, run=retried, artifact=ingress.sign(scope_two), now=T2
    )
    assert approved.state is WorkflowState.RUNNING
    assert approved.step("gate").state is StepState.SUCCEEDED

    executor = RecordingExecutor()
    after = advance(definition=definition, run=approved, executor=executor, now=T2)

    assert len(executor.calls) == 1
    assert executor.calls[0]["attempt_id"].attempt_no == 2
    assert after.attempts_for("work")[-1].attempt_id.attempt_no == 2


# ---------------------------------------------------------------------------
# T28 — CASE B: crash / process death
# ---------------------------------------------------------------------------


def test_T28_resume_with_only_the_previous_approval_cannot_start_the_next_attempt(
    monkeypatch,
) -> None:
    """T28. SECURITY BOUNDARY. §13.2, §13.1.3 CASE 2.

    Attempt 1 is reserved and then the process ends before any result is recorded. On
    resume the next legal number is 2, approval #1 covers 1, and the gated step therefore
    MUST NOT begin — crash recovery is a way back through the approval point, not around
    it.
    """
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    accepted = _approved_for_attempt_one(ingress, definition)

    plan = begin_attempt(definition=definition, run=accepted, now=T2)
    persisted = plan.run
    assert plan.admitted
    assert persisted.inflight_attempt_no == 1
    assert persisted.consumed_total_attempts == 1
    assert persisted.attempts_for("work") == (), "the interrupted attempt was recorded"

    # What survived is exactly what a resume would read.
    assert persisted.approval_covers("work", 1)
    assert not persisted.approval_covers("work", 2)

    idle = RecordingExecutor()
    after = advance(definition=definition, run=persisted, executor=idle, now=T2)

    assert len(idle.calls) == 0, "resume began an attempt the old approval cannot cover"
    assert after == persisted
    assert after.is_terminal is False


def test_T28b_a_resume_reaches_the_next_attempt_only_through_a_fresh_approval(
    monkeypatch,
) -> None:
    """The other half of T28: the path OUT exists, and it goes through the point."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    accepted = _approved_for_attempt_one(ingress, definition)
    persisted = begin_attempt(definition=definition, run=accepted, now=T2).run

    resumed = reenter_approval(definition=definition, run=persisted, now=T2)
    assert resumed.state is WorkflowState.AWAITING_APPROVAL

    approved = resolve_approval(
        definition=definition,
        run=resumed,
        artifact=ingress.sign(_scope_for(resumed, definition, 2)),
        now=T2,
    )
    executor = RecordingExecutor()
    after = advance(definition=definition, run=approved, executor=executor, now=T2)

    assert len(executor.calls) == 1
    assert executor.calls[0]["attempt_id"].attempt_no == 2


# ---------------------------------------------------------------------------
# T29 — an approved attempt proceeds, and the wait is not re-opened
# ---------------------------------------------------------------------------


def test_T29_an_exact_approval_permits_that_attempt_and_is_not_re_asked(monkeypatch) -> None:
    """T29. §13.1.3: a wait is never re-opened for an attempt already authorized."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)
    retried = reenter_approval(definition=definition, run=run, now=T2)
    approved = resolve_approval(
        definition=definition,
        run=retried,
        artifact=ingress.sign(_scope_for(retried, definition, 2)),
        now=T2,
    )

    assert approved.approval_covers("work", 2)
    with pytest.raises(InvalidRecord):
        reenter_approval(definition=definition, run=approved, now=T2)

    executor = RecordingExecutor()
    after = advance(definition=definition, run=approved, executor=executor, now=T2)

    assert len(executor.calls) == 1
    assert executor.calls[0]["attempt_id"].attempt_no == 2
    assert len(after.approvals) == 2, "a second approval was requested for one attempt"


# ---------------------------------------------------------------------------
# The re-entry refuses everything Amendment 4 did not license
# ---------------------------------------------------------------------------


def test_the_re_entry_refuses_a_step_that_did_not_fail(monkeypatch) -> None:
    """A caller cannot re-open the wait to skip the work it gates."""
    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition = a_gated_definition()
    accepted = _approved_for_attempt_one(ingress, definition)
    assert accepted.step("work").attempts == ()

    with pytest.raises(InvalidRecord):
        reenter_approval(definition=definition, run=accepted, now=T2)


def test_the_re_entry_refuses_an_ungated_run(monkeypatch) -> None:
    """§13.1.3 moves ONE step, the approval point that gates the failing step."""
    from tests.workflows.conftest import make_definition

    definition = make_definition()
    run = start_run(definition=definition, workspace_identity="ws-1", now=T0)
    run = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T0)

    with pytest.raises(InvalidRecord):
        reenter_approval(definition=definition, run=run, now=T2)


def test_a_successor_cannot_re_open_a_wait_for_an_already_approved_attempt(
    monkeypatch,
) -> None:
    """TRANSITION INTEGRITY. §13.1.3 at the record boundary.

    `reenter_approval` refuses with a reason, and the RECORD refuses on its own. A caller
    who assembles the same transition by hand meets the same rule — so the engine giving
    a good error message is not what makes the boundary hold, and a mutation that removes
    one of the two is still caught by the other.
    """
    import dataclasses

    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)
    retried = reenter_approval(definition=definition, run=run, now=T2)
    approved = resolve_approval(
        definition=definition,
        run=retried,
        artifact=ingress.sign(_scope_for(retried, definition, 2)),
        now=T2,
    )
    assert approved.approval_covers("work", 2)

    with pytest.raises(InvalidRecord):
        approved.advance(
            state=WorkflowState.AWAITING_APPROVAL,
            approval_deadline=T2,
            updated_at=T2,
            steps=tuple(
                dataclasses.replace(record, state=StepState.AWAITING_APPROVAL)
                if record.step_id == "gate"
                else record
                for record in approved.steps
            ),
        )
def test_a_successor_cannot_run_a_gated_attempt_behind_the_gate(monkeypatch) -> None:
    """TRANSITION INTEGRITY. §13.1.2 at the record boundary.

    `begin_attempt` checks with the definition in hand; the successor boundary checks the
    record a caller built. A caller who appends an attempt at an approved step without an
    approval for its number is refused there — `digest validation != transition
    validation`.
    """
    import dataclasses

    ingress = SigningAuthority()
    ingress.install(monkeypatch)
    definition, run = _failed_once(ingress)
    gated = run.step("work")
    assert gated is not None

    smuggled = _an_attempt(run, "work", 2, "exec-smuggled")
    steps = tuple(
        dataclasses.replace(record, attempts=record.attempts + (smuggled,))
        if record.step_id == "work"
        else record
        for record in run.steps
    )

    with pytest.raises(InvalidRecord):
        run.advance(steps=steps, inflight_attempt_no=None)
