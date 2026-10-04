"""AI-14-B / B6 — the composition root.

One task, the connected path, and one result. These tests are about what the root
returns and what it refuses to do on the way.
"""

from __future__ import annotations

import pytest

from agents.result import AgentExecutionOutcome
from agents.vocabulary import AgentId
from tools import default_registry

from composition.errors import SelectionRefused
from agents.body import OfflineBody

from composition.root import run_task

from tests.composition.conftest import (
    ALL_PROVIDERS,
    A_MODEL_REF,
    PROFILES,
    a_router_request,
    a_rule_set,
    a_workspace,
    an_empty_rule_set,
)

pytestmark = pytest.mark.layer2


class _CountingBody:
    """An offline body that records whether it was entered at all."""

    agent_id = AgentId.DSH

    def __init__(self) -> None:
        self.runs = 0
        self._inner = None

    def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
        from agents.body import BodyOutcome

        self.runs += 1
        return BodyOutcome(result_ref="sha256:" + "ab" * 32)


def _run(tmp_path, *, body=None, rule_set=None, **overrides):
    root, _ = a_workspace(tmp_path / "ws")
    arguments = {
        "workspace_root": str(root),
        "task": "wf-demo/v1/s1",
        "input_digest": "0" * 64,
        "router_request": a_router_request(),
        "rule_set": a_rule_set(),
        "profiles": PROFILES,
        "enabled_providers": ALL_PROVIDERS,
        "body": body if body is not None else OfflineBody(agent_id=AgentId.DSH),
        "default_agent": AgentId.DSH,
        "registry": default_registry(),
        "policy": None,
        "clock": lambda: "2026-10-04T00:00:00Z",
    }
    arguments.update(overrides)
    if rule_set is not None:
        arguments["rule_set"] = rule_set
    return run_task(**arguments)


def test_a_task_runs_through_the_connected_path(tmp_path) -> None:
    """The control: Context, Router, execution and a result, in one call.

    The Context is the execution's OWN — AI-08 establishes one per execution
    (§8.1) — and the workspace id it resolved is what comes back.
    """
    outcome = _run(tmp_path)

    assert outcome.model_ref == A_MODEL_REF
    assert str(outcome.request.agent_id) == AgentId.DSH.value
    assert outcome.result.outcome is AgentExecutionOutcome.COMPLETED
    assert outcome.workspace_id != ""
    assert outcome.execution_id.startswith("ex-")


def test_the_result_is_a_reference_and_not_content(tmp_path) -> None:
    """§10. A result names what the execution terminated with."""
    outcome = _run(tmp_path)

    assert outcome.result.result.startswith("sha256:")
    assert outcome.result.tool_calls == ()


def test_a_non_selecting_router_outcome_stops_before_any_execution(tmp_path) -> None:
    """§22.1 B1. No selection means no execution — not an execution with a default.

    The body counts its own entries, so this asserts the stronger fact: the
    execution was never entered.
    """
    body = _CountingBody()

    with pytest.raises(SelectionRefused):
        _run(tmp_path, body=body, rule_set=an_empty_rule_set())

    assert body.runs == 0


def test_the_decision_travels_with_the_run(tmp_path) -> None:
    """A reader can answer "why this model" from what the root returns."""
    outcome = _run(tmp_path)

    assert outcome.decision.outcome.value == "SELECTED"
    assert outcome.decision.reason_code == "RULE_MATCHED"
    assert outcome.decision.to_mapping()["selected"] == A_MODEL_REF
