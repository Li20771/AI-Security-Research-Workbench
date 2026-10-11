"""AI-14-B / B6 — the authority boundaries, verified end to end.

§4.2's rules are restatements of clauses other phases froze. A composition is
exactly where they can be lost quietly — each layer is correct alone and the
wiring gives one of them a power it never had — so each rule below is checked
across the CONNECTED path rather than inside one layer.
"""

from __future__ import annotations

import pathlib

import pytest

from agents.body import BodyOutcome
from agents.request import AgentExecutionRequest
from agents.vocabulary import AgentId
from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools.vocabulary import ToolOutcome
from providers.model_profile import CapabilityName, CapabilityStatus
from tools import default_registry

from composition.executor import AgentStepExecutor
from agents.body import OfflineBody

from composition.provider import ExecutionBinding, offline_body_factory
from composition.root import run_task

from tests.composition.conftest import (
    ALL_PROVIDERS,
    A_MODEL_REF,
    PROFILES,
    a_router_request,
    a_rule_set,
    a_workspace,
)

pytestmark = pytest.mark.layer2


class _ToolCallingBody:
    """A body that makes exactly one declared tool call, through the gateway.

    It reaches the tool path the only way a body can: `tools.invoke`, which asks
    Guard. It does not touch the registry and does not decide anything.
    """

    agent_id = AgentId.DSH

    def __init__(self, invocation) -> None:  # noqa: ANN001
        self._invocation = invocation

    def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
        self.reference = tools.invoke(self._invocation)
        return BodyOutcome(result_ref="sha256:" + "cd" * 32)


def _run(tmp_path, body_factory=None, **overrides):
    root, _ = a_workspace(tmp_path / "ws")
    arguments = {
        "workspace_root": str(root),
        "task": "wf-demo/v1/s1",
        "input_digest": "0" * 64,
        "router_request": a_router_request(),
        "rule_set": a_rule_set(),
        "profiles": PROFILES,
        "enabled_providers": ALL_PROVIDERS,
        "body_factory": body_factory if body_factory is not None else offline_body_factory(),
        "default_agent": AgentId.DSH,
        "registry": default_registry(),
        "policy": None,
        "clock": lambda: "2026-10-04T00:00:00Z",
    }
    arguments.update(overrides)
    return run_task(**arguments), root


def test_the_router_does_not_authorize_the_tool_call_it_selected_for(tmp_path) -> None:
    """SECURITY BOUNDARY. §4.2 rule 1.

    The Router SELECTED, the execution ran — and the tool invocation the execution
    made was still decided by GUARD, which refused it. The selection authorized
    nothing: a decision that granted permission would have made this call
    COMPLETED.
    """
    from tests.composition.test_controlled_verification import _an_entry

    entry = _an_entry("t-a")
    from agents.toolcall import ToolInvocation

    body = _ToolCallingBody(
        ToolInvocation(
            tool_id=entry.tool_id,
            tool_version=entry.tool_version,
            adapter_family=entry.adapter_family,
            operation=entry.operation,
            permission_level=entry.permission_level,
            target=entry.target,
            timeout_seconds=entry.timeout_seconds,
        )
    )
    def a_factory(*, model_ref, agent_id):
        return ExecutionBinding(body=body, model_ref=None)

    outcome, _ = _run(tmp_path, body_factory=a_factory)

    assert outcome.decision.outcome.value == "SELECTED"
    call = outcome.result.tool_calls[0]
    assert call.outcome is ToolOutcome.BLOCKED
    assert call.outcome is not ToolOutcome.COMPLETED
    # The refusal is attributable to a real Guard evaluation.
    assert call.guard_decision is GuardDecision.BLOCKED
    assert call.guard_decision_id.startswith("grd-")


def test_one_agent_result_cannot_become_another_agents_request(tmp_path) -> None:
    """§4.2 rule 8. AI-08 refuses a result riding into a request by name.

    The composition cannot launder one execution's result into the next
    execution's input, because the shape it would have to use refuses the field.
    """
    for refused in ("result", "agent_result", "previous_result", "other_result"):
        with pytest.raises(ValueError):
            AgentExecutionRequest.from_mapping(
                {
                    "schema_version": 1,
                    "agent_id": "dsh",
                    "workspace": {"root": str(tmp_path)},
                    "task": "wf-demo/v1/s1",
                    "input": "0" * 64,
                    refused: {"result_ref": "sha256:" + "00" * 32},
                }
            )


def test_wiring_did_not_verify_a_capability(tmp_path) -> None:
    """§4.2 rule 10, §8. Every shipped capability is still UNKNOWN after a run.

    The composed path ran end to end and promoted nothing: a capability becomes
    VERIFIED by a contracted live verification, and live verification is NOT_RUN.
    """
    _run(tmp_path)

    profile = PROFILES[A_MODEL_REF]
    assert all(
        profile.capability(capability).status is not CapabilityStatus.VERIFIED
        for capability in CapabilityName
    )


def test_the_composition_reaches_no_evidence_writer() -> None:
    """B5 stays BLOCKED: no module here CALLS admission, and that is the boundary.

    THE IMPORT IS NO LONGER THE BOUNDARY. AI-14 Amendment 2 (§22.1 B5, STEP 1)
    AUTHORIZED the composition -> Evidence edge, so `plugins.evidence` is a layer
    this package may import and this test no longer refuses it. AN AUTHORIZED IMPORT
    IS PERMISSION TO WRITE A CALL, NOT A CALL.

    WHAT IS STILL CHECKED IS THE CALL — the current-state fact §5.1 and Appendix A
    depend on: no module in this package calls `admit` or `admit_to_store`, which is
    what keeps the edge IMPLEMENTED BUT NOT CONNECTED. If a call appears here, the
    edge is being connected, and §22.1 requires that change to carry the
    classification update in the SAME merged change rather than after it.

    Checked by CALL rather than by the word: the docstrings explain the rule, and a
    word scan would flag the explanation as the violation — the same distinction
    `layer0_policy` makes when it reads identifiers rather than text.
    """
    import ast

    package = pathlib.Path(__file__).resolve().parents[2] / "composition"
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = getattr(node.func, "id", None) or getattr(
                    node.func, "attr", None
                )
                assert called not in {"admit", "admit_to_store"}, path.name


def test_the_composition_adds_no_authority_vocabulary() -> None:
    """§4.2. The glue names no grant of its own.

    `ALLOW` may be READ (the tool path owns that decision) but this package never
    constructs one, and it holds no approval, trust-root or producer vocabulary at
    all.
    """
    package = pathlib.Path(__file__).resolve().parents[2] / "composition"
    forbidden = (
        "Ed25519PrivateKey",
        "ApprovalRef",
        "ApprovalStatus",
        "producer_token",
        "ADMITTED_EVENTS",
        "ALLOWED",
    )
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in text, f"{path.name} names {name}"


def test_the_composition_holds_no_workflow_state(tmp_path) -> None:
    """§4.2 rule 7. The executor returns an outcome; the engine owns the record.

    The value the executor produces has no field a run, a step or an approval
    could travel in — so a delegation cannot carry workflow state back out of
    AI-08, and cannot carry any in.
    """
    from workflows.engine import ExecutionOutcome

    fields = set(ExecutionOutcome.__dataclass_fields__)
    assert not (fields & {"run_id", "steps", "approvals", "state", "scope_digest"})

    root, _ = a_workspace(tmp_path / "ws")
    executor = AgentStepExecutor(
        body=OfflineBody(agent_id=AgentId.DSH),
        agent_id=AgentId.DSH,
        workspace_root=str(root),
        clock=lambda: "2026-10-04T00:00:00Z",
    )
    assert not hasattr(executor, "run")
    assert not hasattr(executor, "approvals")
