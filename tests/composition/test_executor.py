"""AI-14-B / B3 — Workflow `StepExecutor` -> real Agent execution.

The engine keeps the attempt, the bounds, the transitions and the approval gate;
this executor only delegates. These tests are about the boundary between the two:
what the executor refuses, and what the engine still owns afterwards.
"""

from __future__ import annotations

import pytest

from agents.body import BodyOutcome, OfflineBody
from agents.codex.body import CodexBody
from agents.toolcall import ToolInvocation
from agents.vocabulary import AgentId
from plugins.guard.models import TargetRef
from plugins.guard.vocabulary import PermissionLevel, TargetKind
from plugins.security_tools.vocabulary import AdapterFamily

from workflows.definition import StepKind, WorkflowStep
from workflows.engine import advance, begin_attempt, start_run
from workflows.vocabulary import FailureClass, StepState, WorkflowState

from composition.errors import ExecutionRefused, WorkspaceRefused
from composition.executor import AgentStepExecutor

from tests.workflows.conftest import T0, T2, limits, make_definition, a_step

from tests.composition.conftest import a_workspace

pytestmark = pytest.mark.layer2


class _RaisingBody:
    """A body that starts and fails. AI-08 reports FAILED, and no class."""

    agent_id = AgentId.DSH

    def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
        raise RuntimeError("the body started and did not reach a result")


def _a_run(tmp_path, **overrides):
    """A run created under the identity its workspace really resolves to."""
    root, workspace_id = a_workspace(tmp_path / "ws")
    definition = make_definition(**overrides)
    run = start_run(definition=definition, workspace_identity=workspace_id, now=T0)
    return definition, run, root, workspace_id


def _an_executor(root, body=None, **overrides):
    arguments = {
        "body": body if body is not None else OfflineBody(agent_id=AgentId.DSH),
        "agent_id": AgentId.DSH,
        "workspace_root": str(root),
        # AI-08 reports the execution's own timing, and AI-13 records what it is
        # told. The workflow tests use synthetic instants, so the execution is
        # given the same clock the engine was — otherwise a real wall-clock
        # execution reports times a day after the run's own deadlines and the
        # engine correctly reads that as an overrun.
        "clock": lambda: T2,
    }
    arguments.update(overrides)
    return AgentStepExecutor(**arguments)


def _an_invocation(*, timeout_seconds: int) -> ToolInvocation:
    return ToolInvocation(
        tool_id="git",
        tool_version="1.0.0",
        adapter_family=AdapterFamily.GIT,
        operation="status",
        permission_level=PermissionLevel.READ,
        target=TargetRef(kind=TargetKind.REPOSITORY, identifier="repo"),
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# The production executor is real
# ---------------------------------------------------------------------------


def test_a_workflow_step_runs_through_the_production_executor(tmp_path) -> None:
    """The control: a real definition advances with a non-test executor.

    Before this, `StepExecutor` had test doubles and no production implementor —
    the seam §5.1 records as IMPLEMENTED BUT NOT CONNECTED. This is that seam,
    connected, and the execution's own ExecutionId reaching the ledger is what
    says so.
    """
    definition, run, root, _ = _a_run(tmp_path)
    executor = _an_executor(root)

    after = advance(definition=definition, run=run, executor=executor, now=T2)

    attempts = after.attempts_for("s1")
    assert len(attempts) == 1
    assert attempts[0].succeeded is True
    assert attempts[0].execution_id.startswith("ex-")
    assert after.step("s1").state is StepState.SUCCEEDED


def test_the_executor_lives_outside_the_workflow_package(tmp_path) -> None:
    """§5.1: the implementation is the composition's, not `workflows/`'s.

    `workflows/` imports nothing outside itself, and it must not learn which
    Agent ran: the engine sees an `ExecutionOutcome` and nothing else.
    """
    definition, run, root, _ = _a_run(tmp_path)
    executor = _an_executor(root)

    assert type(executor).__module__.startswith("composition")
    assert not type(executor).__module__.startswith("tests")


def test_the_recorded_timing_is_the_executions(tmp_path) -> None:
    """§15.2. The attempt records what the EXECUTION reported."""
    definition, run, root, _ = _a_run(tmp_path)
    after = advance(
        definition=definition, run=run, executor=_an_executor(root), now=T2
    )

    attempt = after.attempts_for("s1")[0]
    assert attempt.started_at is not None
    assert attempt.ended_at >= attempt.started_at


# ---------------------------------------------------------------------------
# What the executor refuses
# ---------------------------------------------------------------------------


def test_a_workspace_that_is_not_the_runs_is_refused(tmp_path) -> None:
    """§5. A run executes in the workspace it was created under.

    The run below was created under a different identity, so delegating it would
    execute the attempt somewhere the run never named. There is no re-derivation
    in v1 and the executor does not invent one.
    """
    root, _ = a_workspace(tmp_path / "ws")
    definition = make_definition()
    run = start_run(definition=definition, workspace_identity="ws-somewhere-else", now=T0)

    with pytest.raises(WorkspaceRefused):
        advance(definition=definition, run=run, executor=_an_executor(root), now=T2)


def test_a_step_that_is_not_an_execution_is_refused(tmp_path) -> None:
    """A wait is not an execution (§6.1)."""
    definition, run, root, _ = _a_run(tmp_path)
    executor = _an_executor(root)
    approval_step = WorkflowStep(
        step_id="gate", kind=StepKind.APPROVAL, approval_seconds=60
    )

    with pytest.raises(ExecutionRefused):
        executor.execute(
            definition=definition,
            step=approval_step,
            attempt_id=None,  # type: ignore[arg-type]
            run=run,
            now=T2,
            timeout_seconds=30,
        )


def test_a_body_serving_another_agent_is_refused(tmp_path) -> None:
    """Attribution must not be rewritable by the composition (§5.1)."""
    root, _ = a_workspace(tmp_path / "ws")

    with pytest.raises(ExecutionRefused):
        AgentStepExecutor(
            body=CodexBody(),
            agent_id=AgentId.DSH,
            workspace_root=str(root),
        )


def test_a_plan_exceeding_the_composed_bound_is_refused(tmp_path) -> None:
    """§10.3.1, §11.1. The narrower bound governs.

    The engine composed a 30-second outer bound for this step; the body's plan
    asks for 600. An executor that ran it would be running something other than
    the attempt that was admitted.
    """
    definition, run, root, _ = _a_run(tmp_path)
    body = OfflineBody(agent_id=AgentId.DSH, plan=(_an_invocation(timeout_seconds=600),))

    with pytest.raises(ExecutionRefused) as refused:
        advance(
            definition=definition,
            run=run,
            executor=_an_executor(root, body=body),
            now=T2,
        )

    assert "narrower bound governs" in str(refused.value)


# ---------------------------------------------------------------------------
# What the engine still owns afterwards
# ---------------------------------------------------------------------------


def test_a_failed_execution_is_unclassified_and_is_never_retried(tmp_path) -> None:
    """§9.1. AI-08 does not classify retryability, and the composition invents none.

    A body that FAILED arrives as `failure_class=None` — UNCLASSIFIED — and §9.1
    says an unclassified failure stops and is never retried. Inventing
    RETRYABLE_FAILURE here would be this layer deciding retryability, which §9
    makes an EXECUTION fact.

    The run declares a retry policy that WOULD retry a RETRYABLE_FAILURE, so the
    assertion below is about the classification and not about a missing policy.
    """
    definition, run, root, _ = _a_run(
        tmp_path,
        limits=limits(attempts_per_step=5, attempts_total=10),
        retry_policy={
            "policy_id": "p",
            "applies_to": ["RETRYABLE_FAILURE"],
            "max_attempts": 3,
            "retry_seconds": 3600,
        },
    )

    after = advance(
        definition=definition, run=run, executor=_an_executor(root, body=_RaisingBody()), now=T2
    )

    attempt = after.attempts_for("s1")[0]
    assert attempt.succeeded is False
    assert attempt.failure_class is None
    assert FailureClass.RETRYABLE_FAILURE not in {attempt.failure_class}
    assert after.is_terminal is True
    assert after.state is WorkflowState.FAILED


def test_the_engine_still_owns_admission(tmp_path) -> None:
    """The executor is reached only through `begin_attempt`'s decision.

    A refused admission never calls the executor at all: the plan comes back
    unadmitted and nothing was delegated.
    """
    root, workspace_id = a_workspace(tmp_path / "ws")
    # The run's deadline has already passed, so the bound refuses the attempt
    # before the executor could be reached.
    definition = make_definition(limits=limits(workflow_seconds=1))
    run = start_run(definition=definition, workspace_identity=workspace_id, now=T0)

    plan = begin_attempt(definition=definition, run=run, now="2026-10-03T10:00:10Z")

    assert plan.admitted is False
    assert plan.refusal != ""
