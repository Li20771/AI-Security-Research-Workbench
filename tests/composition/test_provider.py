"""AI-14-B / B2 — Agent -> Provider / model invocation.

Three things are being proven, and they are different:

```text
the offline path works        a composed execution runs with no provider at all
the binding gate holds        a provider that is not runtime-enabled is refused
wiring is not verification    an UNKNOWN capability is still refused AFTER the
                              seam is connected, and no network is touched
```
"""

from __future__ import annotations

import pytest

from agents.body import OfflineBody
from agents.request import AgentExecutionRequest
from agents.result import AgentExecutionOutcome
from agents.runtime import execute
from agents.vocabulary import AgentId

from integrations.codex.backend import MimoCodexBackend
from providers.invocation import (
    InvocationContext,
    InvocationRequest,
    InvocationStatus,
    Invoker,
    Message,
    MessageRole,
)
from providers.protocol.base import Transport, TransportRequest, TransportResult
from providers.transport import TransportSettings

from composition.errors import ProviderRefused
from composition.provider import codex_body, enabled_provider_ids, offline_codex_body

from tests.composition.conftest import (
    ALL_PROVIDERS,
    A_MODEL_REF,
    PROFILES,
    PROVIDERS,
    a_provider_config,
    a_workspace,
)

pytestmark = pytest.mark.layer2


class _RecordingTransport(Transport):
    """A transport that records being asked to send and never sends.

    It exists so a test can assert on the STRONGER fact: not that a call failed,
    but that no call was attempted at all.
    """

    def __init__(self) -> None:
        self.requests: list[TransportRequest] = []

    def send(self, request: TransportRequest) -> TransportResult:
        self.requests.append(request)
        return TransportResult(
            failure=None, http_status=200, payload={"choices": []}
        )


def _an_invoker(transport: Transport) -> Invoker:
    """An Invoker built the way an external composition root would build one."""
    return Invoker(
        InvocationContext(
            providers=PROVIDERS,
            models=PROFILES,
            transport=transport,
            transport_settings_for=lambda provider_id: TransportSettings(),
            environ={},
        )
    )


def _a_request(tmp_path) -> AgentExecutionRequest:
    root, _ = a_workspace(tmp_path / "ws")
    return AgentExecutionRequest(
        agent_id=AgentId.CODEX,
        workspace_root=str(root),
        task="wf/task",
        input_digest="0" * 64,
    )


# ---------------------------------------------------------------------------
# The offline path
# ---------------------------------------------------------------------------


def test_the_offline_body_runs_with_no_provider_and_no_credential(tmp_path) -> None:
    """The control for everything below: the seam is usable with nothing wired."""
    result = execute(_a_request(tmp_path), body=offline_codex_body())

    assert result.outcome is AgentExecutionOutcome.COMPLETED
    assert result.result.startswith("sha256:")
    assert str(result.agent_id) == AgentId.CODEX.value


def test_enabled_provider_ids_reads_runtime_config(tmp_path) -> None:
    """Enablement comes from CONFIG, never from a profile on disk."""
    assert enabled_provider_ids(a_provider_config()) == frozenset()
    assert enabled_provider_ids(a_provider_config(enabled=("mimo",))) == frozenset(
        {"mimo"}
    )
    # A reserved extension point is never enabled. AI-02 refuses a config that
    # tries to enable one, so the only reachable state is reserved-and-disabled —
    # and the composition reports no enabled provider for it.
    assert enabled_provider_ids(a_provider_config(reserved=("mimo",))) == frozenset()


# ---------------------------------------------------------------------------
# The binding gate
# ---------------------------------------------------------------------------


def test_a_disabled_provider_is_refused(tmp_path) -> None:
    """AI-09: profile existence is not runtime enablement."""
    with pytest.raises(ProviderRefused) as refused:
        codex_body(
            model_ref=A_MODEL_REF,
            config=a_provider_config(enabled=()),
            providers=PROVIDERS,
            models=PROFILES,
            invoker=_an_invoker(_RecordingTransport()),
        )

    assert "not enabled" in str(refused.value)


def test_a_reserved_provider_is_refused(tmp_path) -> None:
    """A reserved provider is an extension point, never invoked.

    AI-02 refuses a config that both reserves and enables a provider, so the
    reachable case is a reserved, un-enabled entry — and AI-09's own reserved
    branch fires on it before the enablement check does.
    """
    with pytest.raises(ProviderRefused) as refused:
        codex_body(
            model_ref=A_MODEL_REF,
            config=a_provider_config(reserved=("mimo",)),
            providers=PROVIDERS,
            models=PROFILES,
            invoker=_an_invoker(_RecordingTransport()),
        )

    assert "reserved" in str(refused.value)


def test_a_model_outside_the_supported_scope_is_refused(tmp_path) -> None:
    """AI-09 v1 serves two refs; a third is not a matter of configuration."""
    with pytest.raises(ProviderRefused):
        codex_body(
            model_ref="mimo/mimo-v9-nonexistent",
            config=a_provider_config(enabled=("mimo",)),
            providers=PROVIDERS,
            models=PROFILES,
            invoker=_an_invoker(_RecordingTransport()),
        )


def test_an_invoker_the_composition_did_not_build_is_refused(tmp_path) -> None:
    """The composition hands over an Invoker; it does not accept a stand-in.

    `MimoCodexBackend` refuses anything that is not AI-02's `Invoker`, so a test
    double cannot be smuggled into the provider path — and the composition does
    not paper over that refusal with a fallback.
    """
    with pytest.raises(ProviderRefused):
        codex_body(
            model_ref=A_MODEL_REF,
            config=a_provider_config(enabled=("mimo",)),
            providers=PROVIDERS,
            models=PROFILES,
            invoker=object(),
        )


def test_an_enabled_provider_builds_a_body(tmp_path) -> None:
    """The control for the refusals above: with enablement, the body is built."""
    body = codex_body(
        model_ref=A_MODEL_REF,
        config=a_provider_config(enabled=("mimo",)),
        providers=PROVIDERS,
        models=PROFILES,
        invoker=_an_invoker(_RecordingTransport()),
    )

    assert body.agent_id is AgentId.CODEX
    assert isinstance(body.backend, MimoCodexBackend)
    assert body.backend.binding.model_ref == A_MODEL_REF


# ---------------------------------------------------------------------------
# Wiring is not verification
# ---------------------------------------------------------------------------


def test_an_unknown_capability_is_refused_after_the_seam_is_connected() -> None:
    """SECURITY BOUNDARY. §8, §22.1 B2.

    The seam is connected: a real `Invoker` exists, over the shipped registry and
    a transport. A call that NEEDS a capability — here tool calling — is refused
    by AI-02's own gate, because every shipped capability is UNKNOWN and only
    VERIFIED authorises a call.

    The transport assertion is the part that matters most: the refusal happened
    BEFORE any provider activity, so connecting the composition did not open a
    network path to a model nobody verified.
    """
    transport = _RecordingTransport()
    invoker = _an_invoker(transport)

    result = invoker.invoke(
        InvocationRequest(
            model_ref=A_MODEL_REF,
            messages=(Message(role=MessageRole.USER, content="descriptor only"),),
            timeout_ms=1000,
            tools=({"name": "git_status", "description": "a declared tool"},),
        )
    )

    assert result.status is InvocationStatus.BLOCKED
    assert str(result.blocked.code) == "CAPABILITY_NOT_VERIFIED"
    assert transport.requests == [], "a blocked capability reached the transport"


def test_the_shipped_registry_still_reports_unknown() -> None:
    """Nothing in this phase promoted a capability by wiring it.

    The profiles are the same ones AI-02 shipped: UNKNOWN. A composition that
    "verified" a capability by constructing a binding would have to change this
    value, and it cannot.
    """
    from providers.model_profile import CapabilityName, CapabilityStatus

    profile = PROFILES[A_MODEL_REF]
    for capability in CapabilityName:
        assert profile.capability(capability).status is not CapabilityStatus.VERIFIED


def test_the_composition_never_constructs_an_invoker() -> None:
    """It is handed one, or it has none — there is no third case.

    Asserted structurally as well as by construction: a module in this package
    that could build its own Invoker could also decide its own transport, and
    that decision is a credential decision this layer must not make.
    """
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[2] / "composition"
    offenders = [
        path.name
        for path in sorted(package.glob("*.py"))
        if "Invoker(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders


def test_the_offline_body_carries_no_backend_beyond_the_offline_one(tmp_path) -> None:
    """A composed offline execution names no provider and no model."""
    result = execute(_a_request(tmp_path), body=offline_codex_body())

    assert result.outcome is AgentExecutionOutcome.COMPLETED
    assert not hasattr(result, "model_ref")
    assert ALL_PROVIDERS  # the registry is non-empty, so the absence above means something
