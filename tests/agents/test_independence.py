"""AI-08 contract T16-Tags: T16-T19, T22-T25 — structural independence.

§9.1  the eight conditions
§9.2  what independence cannot prove
§5.2.1 a role is not a finding

The predicate is exercised two ways. Conditions that hold are checked against
executions that really ran; conditions that must be *violable* are checked
against synthetic records, because a predicate that cannot be made to fail is
not a predicate.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from plugins.context import build_context
from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools import ToolOutcome

from agents.body import OfflineBody
from agents.independence import (
    I1_IDENTITY,
    I2_EXECUTION,
    I3_INPUT,
    I4_CONTEXT,
    I5_TOOL_AUTHORIZATION,
    I6_RESULT,
    I7_FAILURE,
    I8_PROVENANCE,
    INDEPENDENCE_CONDITIONS,
    ExecutionRecord,
    structural_independence,
)
from agents.request import AgentExecutionRequest
from agents.result import AgentExecutionOutcome, AgentResult, ToolCallRef
from agents.runtime import run_execution
from agents.vocabulary import AgentId, UnknownAgent

from tests.agents.conftest import make_request

pytestmark = pytest.mark.layer1

INDEPENDENCE_SOURCE = pathlib.Path("agents/independence.py")


def _call(ordinal: int, decision_id: str) -> ToolCallRef:
    return ToolCallRef(
        ordinal=ordinal,
        tool_id="echo",
        tool_version="1.0",
        operation="echo",
        outcome=ToolOutcome.COMPLETED,
        guard_decision=GuardDecision.ALLOW,
        guard_decision_id=decision_id,
        guard_reason_code="AI08_TEST_ALLOW",
    )


#: A legal v1 result reference (§10.2). `AgentResult` refuses anything else, so
#: a synthetic record has to carry a real-shaped reference like any other.
DIGEST = "sha256:" + "a" * 64


def _result(
    *,
    agent_id: str,
    execution_id: str,
    workspace_id: str = "ws-1",
    outcome: AgentExecutionOutcome = AgentExecutionOutcome.COMPLETED,
    result: str = DIGEST,
    tool_calls: tuple[ToolCallRef, ...] = (),
    blocking: str | None = None,
) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        execution_id=execution_id,
        workspace_id=workspace_id,
        input_digest="sha256:in",
        outcome=outcome,
        result=result,
        tool_calls=tool_calls,
        blocking=blocking,
    )


def _record(
    *,
    agent_id: str,
    execution_id: str,
    workspace_root: str,
    task: str = "t",
    input_digest: str = "sha256:in",
    context_descriptor: str | None = None,
    context=None,
    result: AgentResult | None = None,
) -> ExecutionRecord:
    request = AgentExecutionRequest(
        agent_id=AgentId(agent_id),
        workspace_root=workspace_root,
        task=task,
        input_digest=input_digest,
        context_descriptor=context_descriptor,
    )
    return ExecutionRecord(
        request=request,
        result=result
        if result is not None
        else _result(agent_id=agent_id, execution_id=execution_id),
        context=context if context is not None else build_context(workspace_root),
    )


class TestTheEightConditionsAreAllReported:
    """§9.1 — the predicate is total over the eight."""

    def test_the_condition_set_is_exactly_eight(self):
        assert len(INDEPENDENCE_CONDITIONS) == 8
        assert set(INDEPENDENCE_CONDITIONS) == {
            I1_IDENTITY,
            I2_EXECUTION,
            I3_INPUT,
            I4_CONTEXT,
            I5_TOOL_AUTHORIZATION,
            I6_RESULT,
            I7_FAILURE,
            I8_PROVENANCE,
        }

    def test_a_finding_reports_every_condition_exactly_once(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root)
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        finding = structural_independence(left, right)

        assert set(finding.satisfied) | set(finding.violated) == set(INDEPENDENCE_CONDITIONS)
        assert not set(finding.satisfied) & set(finding.violated)

    def test_the_predicate_is_symmetric(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root)
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        assert (
            structural_independence(left, right).to_mapping()
            == structural_independence(right, left).to_mapping()
        )


class TestI1IdentitySeparation:
    """T16 — §9.1 I1."""

    def test_two_registered_agents_separate(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root)
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        assert I1_IDENTITY in structural_independence(left, right).satisfied

    def test_one_agent_twice_does_not(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root)
        right = _record(agent_id="dsh", execution_id="ex-b", workspace_root=workspace_root)
        assert I1_IDENTITY in structural_independence(left, right).violated

    def test_an_unregistered_identity_cannot_be_built_at_all(self, workspace_root):
        """Amendment-review fix: the forged record is no longer constructible.

        This test used to build one with `dataclasses.replace(result,
        agent_id="gpt")` and assert I1 caught it. That is no longer possible —
        which is the stronger outcome: the predicate cannot be handed a
        non-registered identity to catch, because `AgentResult` refuses to exist
        with one.
        """
        with pytest.raises(UnknownAgent):
            dataclasses.replace(
                _result(agent_id="dsh", execution_id="ex-a"), agent_id="gpt"
            )
        with pytest.raises(UnknownAgent):
            _result(agent_id="gpt", execution_id="ex-a")


class TestI2ExecutionSeparation:
    """T17 — §9.1 I2."""

    def test_two_executions_separate(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root)
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        assert I2_EXECUTION in structural_independence(left, right).satisfied

    def test_a_shared_execution_id_does_not(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-same", workspace_root=workspace_root)
        right = _record(agent_id="codex", execution_id="ex-same", workspace_root=workspace_root)
        assert I2_EXECUTION in structural_independence(left, right).violated

    def test_an_id_that_encodes_its_agent_is_not_opaque(self, workspace_root):
        """§7.2: an ExecutionId encodes no agent, so one that does fails I2."""
        left = _record(agent_id="dsh", execution_id="ex-dsh-1", workspace_root=workspace_root)
        right = _record(agent_id="codex", execution_id="ex-codex-2", workspace_root=workspace_root)
        assert I2_EXECUTION in structural_independence(left, right).violated

    def test_real_execution_ids_are_opaque(self, workspace_root):
        left = run_execution(
            make_request(workspace_root, agent_id=AgentId.DSH),
            body=OfflineBody(agent_id=AgentId.DSH),
        )
        right = run_execution(
            make_request(workspace_root, agent_id=AgentId.CODEX),
            body=OfflineBody(agent_id=AgentId.CODEX),
        )
        assert I2_EXECUTION in structural_independence(left, right).satisfied


class TestI3AResultIsNeverAnInput:
    """T18 — §9.1 I3. The key v1 boundary."""

    def test_the_request_type_has_no_field_that_can_hold_a_result(self):
        """The first line of defence is the shape, not a runtime check."""
        fields = {f.name for f in dataclasses.fields(AgentExecutionRequest)}
        assert not {name for name in fields if "result" in name}
        annotations = "".join(
            str(hint) for hint in AgentExecutionRequest.__annotations__.values()
        )
        assert "AgentResult" not in annotations

    def test_no_agents_api_accepts_two_results(self):
        """Every public callable takes at most one result, or none."""
        import inspect

        import agents.independence as independence_mod
        import agents.runtime as runtime_mod

        for module in (runtime_mod, independence_mod):
            for name, obj in vars(module).items():
                if name.startswith("_") or not callable(obj):
                    continue
                if getattr(obj, "__module__", "") != module.__name__:
                    continue
                try:
                    signature = inspect.signature(obj)
                except (TypeError, ValueError):  # pragma: no cover
                    continue
                for parameter in signature.parameters:
                    if parameter in ("other", "right"):
                        # `structural_independence(left, right)` is the ONE
                        # place two records meet, and it returns a finding — it
                        # does not feed one into the other.
                        assert name == "structural_independence", name

    def test_a_descriptor_naming_the_other_execution_violates_i3(self, workspace_root):
        left = _record(agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root)
        right = _record(
            agent_id="codex",
            execution_id="ex-b",
            workspace_root=workspace_root,
            input_digest="ex-a",  # the other execution's id, as an input
        )
        assert I3_INPUT in structural_independence(left, right).violated

    def test_two_real_executions_separate_on_i3(self, workspace_root):
        left = run_execution(
            make_request(workspace_root, agent_id=AgentId.DSH),
            body=OfflineBody(agent_id=AgentId.DSH),
        )
        right = run_execution(
            make_request(workspace_root, agent_id=AgentId.CODEX),
            body=OfflineBody(agent_id=AgentId.CODEX),
        )
        assert I3_INPUT in structural_independence(left, right).satisfied


class TestI4ContextSeparation:
    """T19 — §9.1 I4."""

    def test_two_executions_own_two_contexts(self, workspace_root):
        left = run_execution(
            make_request(workspace_root, agent_id=AgentId.DSH),
            body=OfflineBody(agent_id=AgentId.DSH),
        )
        right = run_execution(
            make_request(workspace_root, agent_id=AgentId.CODEX),
            body=OfflineBody(agent_id=AgentId.CODEX),
        )
        assert I4_CONTEXT in structural_independence(left, right).satisfied

    def test_a_shared_context_object_violates_i4(self, workspace_root):
        context = build_context(workspace_root)
        left = _record(
            agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root, context=context
        )
        right = _record(
            agent_id="codex", execution_id="ex-b", workspace_root=workspace_root, context=context
        )
        assert I4_CONTEXT in structural_independence(left, right).violated

    def test_an_execution_without_a_context_violates_i4(self, workspace_root):
        left = _record(
            agent_id="dsh",
            execution_id="ex-a",
            workspace_root=workspace_root,
            context=build_context(workspace_root),
        )
        right = ExecutionRecord(
            request=left.request,
            result=_result(agent_id="codex", execution_id="ex-b"),
            context=None,
        )
        assert I4_CONTEXT in structural_independence(left, right).violated


class TestI5ToolAuthorizationSeparation:
    """T22 — §9.1 I5, §9.1.1."""

    def test_distinct_decisions_separate(self, workspace_root):
        left = _record(
            agent_id="dsh",
            execution_id="ex-a",
            workspace_root=workspace_root,
            result=_result(
                agent_id="dsh", execution_id="ex-a", tool_calls=(_call(0, "grd-1"),)
            ),
        )
        right = _record(
            agent_id="codex",
            execution_id="ex-b",
            workspace_root=workspace_root,
            result=_result(
                agent_id="codex", execution_id="ex-b", tool_calls=(_call(0, "grd-2"),)
            ),
        )
        assert I5_TOOL_AUTHORIZATION in structural_independence(left, right).satisfied

    def test_a_reused_decision_violates_i5(self, workspace_root):
        left = _record(
            agent_id="dsh",
            execution_id="ex-a",
            workspace_root=workspace_root,
            result=_result(
                agent_id="dsh", execution_id="ex-a", tool_calls=(_call(0, "grd-same"),)
            ),
        )
        right = _record(
            agent_id="codex",
            execution_id="ex-b",
            workspace_root=workspace_root,
            result=_result(
                agent_id="codex", execution_id="ex-b", tool_calls=(_call(0, "grd-same"),)
            ),
        )
        assert I5_TOOL_AUTHORIZATION in structural_independence(left, right).violated

    def test_two_refusals_that_never_reached_guard_are_not_a_reuse(self, workspace_root):
        """An empty decision id means no evaluation happened, not a shared one."""
        left = _record(
            agent_id="dsh",
            execution_id="ex-a",
            workspace_root=workspace_root,
            result=_result(
                agent_id="dsh", execution_id="ex-a", tool_calls=(_call(0, ""), _call(1, ""))
            ),
        )
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        assert I5_TOOL_AUTHORIZATION in structural_independence(left, right).satisfied


class TestI6AndI7Separation:
    """T22 — §9.1 I6, I7."""

    def test_one_result_object_shared_violates_i6(self, workspace_root):
        shared = _result(agent_id="dsh", execution_id="ex-a")
        left = _record(
            agent_id="dsh", execution_id="ex-a", workspace_root=workspace_root, result=shared
        )
        right = _record(
            agent_id="codex", execution_id="ex-b", workspace_root=workspace_root, result=shared
        )
        finding = structural_independence(left, right)
        assert I6_RESULT in finding.violated
        assert I8_PROVENANCE in finding.violated

    def test_a_result_naming_the_other_execution_violates_i7(self, workspace_root):
        left = _record(
            agent_id="dsh",
            execution_id="ex-a",
            workspace_root=workspace_root,
            result=_result(
                agent_id="dsh",
                execution_id="ex-a",
                outcome=AgentExecutionOutcome.COMPLETED,
                result="ref:converted-from-ex-b",
            ),
        )
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        assert I7_FAILURE in structural_independence(left, right).violated

    def test_a_failed_execution_does_not_upgrade_its_partner(self, workspace_root):
        """Behavioural I7: each outcome is its own, whatever the other ended as.

        One execution fails and the other completes. The failing one's outcome
        does not become the other's, and the completing one is not evidence that
        the failure did not happen.
        """
        left = run_execution(
            make_request(workspace_root, agent_id=AgentId.DSH),
            body=_ExplodingBody(),
        )
        right = run_execution(
            make_request(workspace_root, agent_id=AgentId.CODEX),
            body=OfflineBody(agent_id=AgentId.CODEX),
        )

        assert left.result.outcome is AgentExecutionOutcome.FAILED
        assert right.result.outcome is AgentExecutionOutcome.COMPLETED
        assert right.result.execution_id not in left.result.result
        assert left.result.execution_id not in right.result.result
        assert I6_RESULT in structural_independence(left, right).satisfied
        assert I7_FAILURE in structural_independence(left, right).satisfied


class _ExplodingBody:
    """A body that starts and fails, for the behavioural I7 case."""

    def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
        raise RuntimeError("the body started and did not finish")


class TestI8ProvenanceSeparation:
    """T22 — §9.1 I8."""

    def test_a_result_attributed_to_the_wrong_agent_violates_i8(self, workspace_root):
        left = _record(
            agent_id="dsh",
            execution_id="ex-a",
            workspace_root=workspace_root,
            result=_result(agent_id="codex", execution_id="ex-a"),
        )
        right = _record(agent_id="codex", execution_id="ex-b", workspace_root=workspace_root)
        assert I8_PROVENANCE in structural_independence(left, right).violated

    def test_real_results_carry_their_own_attribution(self, workspace_root):
        for agent in (AgentId.DSH, AgentId.CODEX):
            record = run_execution(
                make_request(workspace_root, agent_id=agent),
                body=OfflineBody(agent_id=agent),
            )
            assert record.result.agent_id == str(agent)
            assert record.result.execution_id


class TestIndependenceIsNotAVerdict:
    """T23, T25 — §9.2."""

    @pytest.mark.parametrize("forbidden", ["PASS", "VERIFIED", "CORRECT", "SUCCESS"])
    def test_the_module_never_speaks_a_verdict(self, forbidden):
        names = {
            node.id
            for node in ast.walk(ast.parse(INDEPENDENCE_SOURCE.read_text(encoding="utf-8")))
            if isinstance(node, ast.Name)
        }
        names |= {
            node.value.id
            for node in ast.walk(ast.parse(INDEPENDENCE_SOURCE.read_text(encoding="utf-8")))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        }
        assert forbidden not in names
        assert forbidden not in INDEPENDENCE_SOURCE.read_text(encoding="utf-8").split('"""')[0]

    def test_the_finding_exposes_no_verdict_property(self):
        fields = {f.name for f in dataclasses.fields(type(_finding()))}
        assert fields == {"satisfied", "violated"}

    def test_independent_is_not_named_like_a_verdict(self):
        finding = _finding()
        assert hasattr(finding, "independent")
        for forbidden in ("passed", "verified", "correct", "succeeded"):
            assert not hasattr(finding, forbidden)


def _finding():
    left = ExecutionRecord(
        request=AgentExecutionRequest(
            agent_id=AgentId.DSH, workspace_root=".", task="t", input_digest="i"
        ),
        result=_result(agent_id="dsh", execution_id="ex-a"),
        context=None,
    )
    right = ExecutionRecord(
        request=AgentExecutionRequest(
            agent_id=AgentId.CODEX, workspace_root=".", task="t", input_digest="i"
        ),
        result=_result(agent_id="codex", execution_id="ex-b"),
        context=None,
    )
    return structural_independence(left, right)
