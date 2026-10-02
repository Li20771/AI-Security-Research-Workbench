"""AI-08 contract T14, T15, T18 — context isolation.

§7.3 the request carries no ContextResponse
§8.1 the runtime establishes exactly one, and the execution owns it
§8.2 what is isolated, and what is shared
§9.1 I4 context separation
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from plugins.guard import PermissionLevel, TargetKind, TargetRef
from plugins.security_tools import AdapterFamily

from agents.body import OfflineBody
from agents.request import AgentExecutionRequest
from agents.runtime import run_execution
from agents.toolcall import ToolGateway, ToolInvocation
from agents.vocabulary import AgentId

from tests.agents.conftest import (
    ECHO_TOOL_ID,
    ECHO_TOOL_VERSION,
    allow_policy,
    make_request,
)

pytestmark = pytest.mark.layer1

RUNTIME_SOURCE = pathlib.Path("agents/runtime.py")


def _plan() -> tuple[ToolInvocation, ...]:
    return (
        ToolInvocation(
            tool_id=ECHO_TOOL_ID,
            tool_version=ECHO_TOOL_VERSION,
            adapter_family=AdapterFamily.TERMINAL,
            operation="echo",
            permission_level=PermissionLevel.READ,
            target=TargetRef(kind=TargetKind.REPOSITORY),
            timeout_seconds=5,
        ),
    )


class TestTheRuntimeEstablishesTheContext:
    """T14 — §8.1."""

    def test_an_execution_owns_a_context_it_established(self, workspace_root):
        record = run_execution(
            make_request(workspace_root), body=OfflineBody(agent_id=AgentId.DSH)
        )
        assert record.context is not None
        assert record.context.workspace.workspace_id == record.result.workspace_id

    def test_two_executions_hold_two_different_context_objects(self, workspace_root):
        """Same workspace, two responses — the whole point of §8.2."""
        request = make_request(workspace_root)
        first = run_execution(request, body=OfflineBody(agent_id=AgentId.DSH))
        second = run_execution(request, body=OfflineBody(agent_id=AgentId.DSH))

        assert first.context is not second.context
        assert (
            first.context.workspace.workspace_id
            == second.context.workspace.workspace_id
        )

    def test_the_context_is_frozen(self, workspace_root):
        """A shared *mutable* context is what §8.2 forbids; frozen is why it cannot be."""
        record = run_execution(
            make_request(workspace_root), body=OfflineBody(agent_id=AgentId.DSH)
        )
        assert type(record.context).__dataclass_params__.frozen
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.context.status = "FULL"  # type: ignore[misc]

    def test_a_blocked_execution_owns_no_context(self, workspace_root):
        """A body that never started established nothing (§11.1)."""
        request = make_request(workspace_root)
        record = run_execution(
            AgentExecutionRequest(
                agent_id=request.agent_id,
                workspace_root=request.workspace_root + "-absent",
                task=request.task,
                input_digest=request.input_digest,
            ),
            body=OfflineBody(agent_id=AgentId.DSH),
        )
        assert record.context is None
        assert record.result.workspace_id == ""


class TestTheRequestCarriesNoContext:
    """T14 — §7.3."""

    def test_the_request_has_no_context_response_field(self):
        fields = {f.name for f in dataclasses.fields(AgentExecutionRequest)}
        assert fields == {
            "agent_id",
            "workspace_root",
            "task",
            "input_digest",
            "context_descriptor",
            "schema_version",
        }
        annotations = {name: str(hint) for name, hint in AgentExecutionRequest.__annotations__.items()}
        assert "ContextResponse" not in "".join(annotations.values())

    def test_a_context_response_is_refused_in_its_place(self, workspace_root):
        from plugins.context import build_context

        with pytest.raises(ValueError):
            AgentExecutionRequest.from_mapping(
                {
                    "schema_version": 1,
                    "agent_id": "dsh",
                    "workspace": {"root": workspace_root},
                    "task": "t",
                    "input": "x",
                    "context": build_context(workspace_root),
                }
            )


class TestNoSharedExecutionState:
    """T15 — §8.2."""

    def test_two_executions_do_not_share_tool_state(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        policy = allow_policy(workspace_id_of(workspace_root))
        request = make_request(workspace_root)

        first = run_execution(
            request,
            body=OfflineBody(agent_id=AgentId.DSH, plan=_plan()),
            registry=echo_registry,
            policy=policy,
        )
        second = run_execution(
            request,
            body=OfflineBody(agent_id=AgentId.DSH, plan=_plan()),
            registry=echo_registry,
            policy=policy,
        )

        assert len(first.result.tool_calls) == 1
        assert len(second.result.tool_calls) == 1
        # Two invocations, two decisions, and neither execution holds the
        # other's. The ordinal restarts, which is what "per execution" means.
        assert first.result.tool_calls[0].ordinal == 0
        assert second.result.tool_calls[0].ordinal == 0
        assert (
            first.result.tool_calls[0].guard_decision_id
            != second.result.tool_calls[0].guard_decision_id
        )

    def test_a_gateway_belongs_to_one_execution(self, workspace_root):
        first = ToolGateway(
            agent_id=AgentId.DSH, workspace_id="ws-a", workspace_root=workspace_root
        )
        second = ToolGateway(
            agent_id=AgentId.DSH, workspace_id="ws-a", workspace_root=workspace_root
        )
        assert first is not second
        assert first.calls == () and second.calls == ()

    def test_results_are_not_shared_between_executions(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """Two executions, two results, two invocation tuples — element by element.

        Compared with `is not` on the elements rather than on the tuples: an
        empty tuple is interned, so `() is ()` is `True` and a tuple-identity
        assertion would pass vacuously for a body with no plan. A plan makes the
        claim falsifiable.
        """
        policy = allow_policy(workspace_id_of(workspace_root))
        request = make_request(workspace_root)

        first = run_execution(
            request,
            body=OfflineBody(agent_id=AgentId.DSH, plan=_plan()),
            registry=echo_registry,
            policy=policy,
        )
        second = run_execution(
            request,
            body=OfflineBody(agent_id=AgentId.DSH, plan=_plan()),
            registry=echo_registry,
            policy=policy,
        )

        assert first.result is not second.result
        assert first.result.tool_calls[0] is not second.result.tool_calls[0]
        assert (
            first.result.tool_calls[0].guard_decision_id
            != second.result.tool_calls[0].guard_decision_id
        )


class TestNoSharedCacheIsIntroduced:
    """T15 — §8.2. The runtime must not hand two executions one cache."""

    def test_build_context_is_called_once_without_a_cache(self):
        tree = ast.parse(RUNTIME_SOURCE.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "build_context"
        ]
        assert len(calls) == 1
        # Only `clock` is passed. No `cache=`, so AI-03 mints a fresh in-memory
        # cache per execution — the default that makes two executions two
        # caches rather than one shared one.
        assert {kw.arg for kw in calls[0].keywords} == {"clock"}

    def test_the_runtime_never_names_a_cache_type(self):
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")
        assert "InMemoryContextCache" not in source
        assert "cache=" not in source
