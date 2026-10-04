"""AI-14-B / B1+B2 — the SELECTED model drives the body that executes.

The gap this module exists for:

```text
BEFORE   Router selects X, and the caller had already supplied body Y
         -> "the Router selected X" and "the execution was built for X" were two
            independent facts, and nothing connected them
AFTER    Router selects X -> body_factory(model_ref=X, ...) -> the binding is
         built FOR X -> run_execution
```

`WorkbenchRun.model_ref` alone cannot prove this: it is the RouterDecision's own
attribute and says only that a selection happened. These tests assert on
`binding_model_ref` — what the body was BUILT for — and on the argument the
factory actually received.
"""

from __future__ import annotations

import pytest

from agents.vocabulary import AgentId
from providers.invocation import InvocationRequest, InvocationStatus, Message, MessageRole

from composition.errors import ProviderRefused, SelectionRefused
from composition.provider import (
    ExecutionBinding,
    codex_body_factory,
    offline_body_factory,
)
from composition.root import run_task

from tests.composition.conftest import (
    ALL_PROVIDERS,
    A_MODEL_REF,
    PROFILES,
    PROVIDERS,
    a_provider_config,
    a_router_request,
    a_rule_set,
    a_workspace,
    an_empty_rule_set,
)

from tests.composition.test_provider import _RecordingTransport, _an_invoker

pytestmark = pytest.mark.layer2

#: The other model ref inside AI-09's scope — used to prove the binding follows
#: the SELECTION rather than a default.
THE_OTHER_REF = "mimo/mimo-v2.6-pro"


def _a_factory(*, enabled=("mimo",), invoker=None):
    return codex_body_factory(
        config=a_provider_config(enabled=enabled),
        providers=PROVIDERS,
        models=PROFILES,
        invoker=invoker if invoker is not None else _an_invoker(_RecordingTransport()),
    )


def _run(tmp_path, *, model_ref=A_MODEL_REF, body_factory, default_agent=AgentId.CODEX):
    root, _ = a_workspace(tmp_path / "ws")
    return run_task(
        workspace_root=str(root),
        task="wf-demo/v1/s1",
        input_digest="0" * 64,
        router_request=a_router_request(candidates=(model_ref,)),
        rule_set=a_rule_set(model_ref=model_ref),
        profiles=PROFILES,
        enabled_providers=ALL_PROVIDERS,
        body_factory=body_factory,
        default_agent=default_agent,
        clock=lambda: "2026-10-04T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# TEST 1 — the selected model reaches the binding, and the binding names it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("selected", [A_MODEL_REF, THE_OTHER_REF])
def test_the_binding_is_built_for_whatever_was_selected(selected: str) -> None:
    """The factory binds the ref it is GIVEN, not a default and not a favourite.

    Parametrised over both refs inside AI-09's scope: a factory that ignored its
    argument and always bound one of them would pass the first case and fail the
    second.
    """
    binding = _a_factory()(model_ref=selected, agent_id=AgentId.CODEX)

    assert isinstance(binding, ExecutionBinding)
    assert binding.model_ref == selected
    # The value comes from AI-09's validated binding, so it is the ref the
    # backend will actually invoke — not an echo of the argument.
    assert binding.body.backend.binding.model_ref == selected
    assert binding.body.agent_id is AgentId.CODEX


def test_run_task_hands_the_selected_model_to_the_factory(tmp_path) -> None:
    """The whole chain, asserted at the two points that could break it.

    A recording factory proves what `run_task` PASSED; the real factory proves
    what a body BUILT from that value names. Asserting only on
    `WorkbenchRun.model_ref` would prove neither.
    """
    captured: list[str] = []
    real = _a_factory()

    def a_recording_factory(*, model_ref, agent_id):
        captured.append(model_ref)
        return ExecutionBinding(body=real(model_ref=model_ref, agent_id=agent_id).body,
                                model_ref=None)

    # The offline binding above reports None (this test does not run a provider),
    # so the assertion below is about what the FACTORY was handed.
    outcome = _run(tmp_path, body_factory=a_recording_factory)
    assert captured == [A_MODEL_REF]
    assert outcome.decision.selected == A_MODEL_REF

    # And the real factory turns exactly that value into a binding for it.
    assert real(model_ref=captured[0], agent_id=AgentId.CODEX).model_ref == A_MODEL_REF


def test_the_composed_run_records_both_facts_separately(tmp_path) -> None:
    """`model_ref` is the selection; `binding_model_ref` is what was built."""
    outcome = _run(tmp_path, body_factory=offline_body_factory())

    assert outcome.model_ref == A_MODEL_REF
    # The offline body invokes no model, and says so rather than echoing the
    # selection back as if it had run it.
    assert outcome.binding_model_ref is None


# ---------------------------------------------------------------------------
# TEST 2 — a body built for another model is refused
# ---------------------------------------------------------------------------


def test_a_body_built_for_another_model_is_refused(tmp_path) -> None:
    """SECURITY BOUNDARY. §4.2 rule 1, §22.1 B1+B2.

    The Router selected one ref; the factory returned a body built for the other.
    The composition refuses rather than running it — a near miss is a different
    model, and "the execution ran something the selection did not name" is the
    exact defect this check exists for.
    """
    ran: list[str] = []

    class _ACodexBody:
        agent_id = AgentId.CODEX

        def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
            ran.append("entered")
            raise AssertionError("a body built for another model was executed")

    def a_wrong_factory(*, model_ref, agent_id):
        return ExecutionBinding(body=_ACodexBody(), model_ref=THE_OTHER_REF)

    with pytest.raises(ProviderRefused) as refused:
        _run(tmp_path, body_factory=a_wrong_factory)

    assert "did not name" in str(refused.value) or "selected" in str(refused.value)
    assert ran == [], "the refused body was executed anyway"


def test_a_factory_that_returns_a_bare_body_is_refused(tmp_path) -> None:
    """A body cannot say which model it was built for — and that is the fact."""
    from agents.body import OfflineBody, AgentBody  # noqa: F401

    def a_bare_factory(*, model_ref, agent_id):
        return OfflineBody(agent_id=AgentId.CODEX)

    with pytest.raises(ProviderRefused):
        _run(tmp_path, body_factory=a_bare_factory)


# ---------------------------------------------------------------------------
# TEST 3 — an UNKNOWN capability is still refused, and nothing is sent
# ---------------------------------------------------------------------------


def test_an_unknown_capability_is_refused_before_any_transport_request() -> None:
    """SECURITY BOUNDARY. §8, §4.2 rule 10, §22.1 B2.

    The invoker the factory holds is the invoker this test uses: a call that NEEDS
    a capability — here tool calling — is refused by AI-02's gate because every
    shipped capability is UNKNOWN, and the transport is never asked.

    Read the second half of this docstring before drawing a wider conclusion:
    AI-09's Codex invocation requests NO capability (`backend.py:225-227`: "no tool
    schema and no `response_format`, because this invocation requests neither"), so
    a composed provider-backed run is not capability-gated by that path. What
    keeps this repository honest is that NOTHING here hands the composition a live
    invoker — live verification is NOT_RUN — and the composition constructs none.
    """
    transport = _RecordingTransport()
    invoker = _an_invoker(transport)

    result = invoker.invoke(
        InvocationRequest(
            model_ref=A_MODEL_REF,
            messages=(Message(role=MessageRole.USER, content="wf-demo/v1/s1"),),
            timeout_ms=1000,
            tools=({"name": "git_status", "description": "a declared tool"},),
        )
    )

    assert result.status is InvocationStatus.BLOCKED
    assert str(result.blocked.code) == "CAPABILITY_NOT_VERIFIED"
    assert transport.requests == [], "a blocked capability reached the transport"


def test_the_factory_builds_the_binding_the_gate_would_screen() -> None:
    """The binding and the gate describe the same model.

    The ref the composed path would invoke is the ref whose capability status the
    gate reads — so "this model's capability is UNKNOWN" is a statement about the
    execution that would run, not about some other model.
    """
    from providers.model_profile import CapabilityName, CapabilityStatus

    binding = _a_factory()(model_ref=A_MODEL_REF, agent_id=AgentId.CODEX)
    profile = PROFILES[binding.model_ref]

    assert all(
        profile.capability(capability).status is not CapabilityStatus.VERIFIED
        for capability in CapabilityName
    )


# ---------------------------------------------------------------------------
# TEST 4 — no selection, no body, no execution
# ---------------------------------------------------------------------------


def test_no_selection_means_no_body_is_built_and_nothing_runs(tmp_path) -> None:
    """§22.1 B1. `NO_ELIGIBLE_MODEL` stops BEFORE construction.

    The factory records being called; it is not called. Nothing is built, nothing
    is retried and no default body is substituted.
    """
    built: list[str] = []

    def a_factory(*, model_ref, agent_id):
        built.append(model_ref)
        return offline_body_factory()(model_ref=model_ref, agent_id=agent_id)

    with pytest.raises(SelectionRefused):
        run_task(
            workspace_root=str(a_workspace(tmp_path / "ws")[0]),
            task="wf-demo/v1/s1",
            input_digest="0" * 64,
            router_request=a_router_request(candidates=(A_MODEL_REF,)),
            rule_set=an_empty_rule_set(),
            profiles=PROFILES,
            enabled_providers=ALL_PROVIDERS,
            body_factory=a_factory,
            default_agent=AgentId.CODEX,
        )

    assert built == [], "a body was built for a selection that never happened"


def test_a_disabled_provider_stops_before_any_body_is_built(tmp_path) -> None:
    """The other non-selecting outcome, and the same rule.

    The provider is not enabled, so the Router selects nothing — and the
    provider-backed factory is never reached, which is what stops "the body
    would have been built anyway" from being a path around the selection.
    """
    built: list[str] = []

    def a_recording_factory(*, model_ref, agent_id):
        built.append(model_ref)
        return _a_factory()(model_ref=model_ref, agent_id=agent_id)

    with pytest.raises(SelectionRefused):
        run_task(
            workspace_root=str(a_workspace(tmp_path / "ws")[0]),
            task="wf-demo/v1/s1",
            input_digest="0" * 64,
            router_request=a_router_request(candidates=(A_MODEL_REF,)),
            rule_set=a_rule_set(),
            profiles=PROFILES,
            enabled_providers=frozenset(),  # nothing is enabled
            body_factory=a_recording_factory,
            default_agent=AgentId.CODEX,
        )

    assert built == []
