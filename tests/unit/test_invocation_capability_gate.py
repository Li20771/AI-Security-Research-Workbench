"""Capability gating.

Contract §6.7 and §7.1, and §5 of the AI-02-B3 task.

The load-bearing assertion is not "the call was refused" but **"no provider
activity happened"**: every blocked case must show `transport.calls == 0`.
A gate that refuses only after sending has already leaked the request.
"""

from __future__ import annotations

import dataclasses

import pytest

from providers.invocation import (
    BlockCode,
    GenerationParameters,
    InvocationContext,
    InvocationRequest,
    InvocationStatus,
    Invoker,
    Message,
    MessageRole,
    StructuredOutputRequest,
)
from providers.model_profile import (
    CapabilityEntry,
    CapabilityName,
    CapabilityStatus,
    Provenance,
    StructuredOutputMode,
)
from providers.protocol import FinishState
from providers.transport import TransportSettings


pytestmark = pytest.mark.layer2

ALL_CAPABILITIES = tuple(CapabilityName)


def _request(**overrides) -> InvocationRequest:
    base = {
        "model_ref": "deepseek/deepseek-flash",
        "messages": (Message(MessageRole.USER, "ping"),),
        "timeout_ms": 120_000,
    }
    base.update(overrides)
    return InvocationRequest(**base)


def _invoker(transport, credentials_env, model_profiles, all_profiles):
    return Invoker(
        InvocationContext(
            providers=all_profiles,
            models=model_profiles,
            transport=transport,
            transport_settings_for=lambda _pid: TransportSettings(),
            environ=credentials_env,
        )
    )


def _with_capability(base_profile, capability: CapabilityName, entry: CapabilityEntry):
    """A synthetic profile whose named capability has the given truth state.

    Used only to prove the gate's *other* side: that VERIFIED authorises and
    nothing else does. No shipped profile carries a verified capability.
    """
    capabilities = dataclasses.replace(
        base_profile.capabilities, **{capability.value: entry}
    )
    provenance = base_profile.provenance
    if entry.status is CapabilityStatus.VERIFIED:
        provenance = Provenance(
            verified_at="2026-09-28", evidence_ref="SYNTHETIC-TEST-EVIDENCE"
        )
    return dataclasses.replace(
        base_profile, capabilities=capabilities, provenance=provenance
    )


def _entry_for(status: CapabilityStatus) -> CapabilityEntry:
    """Build a well-formed entry for each non-VERIFIED state.

    Each state has its own consistency rules, so these are built lazily
    rather than in a dict literal: an eager literal would construct every
    entry and fail on the ones the current case does not use.
    """
    if status is CapabilityStatus.UNKNOWN:
        return CapabilityEntry(status=status)
    if status is CapabilityStatus.NOT_VERIFIED:
        return CapabilityEntry(
            status=status, declared=True, source="attempted, inconclusive"
        )
    if status is CapabilityStatus.DECLARED:
        return CapabilityEntry(
            status=status, declared=True, source="vendor documentation"
        )
    if status is CapabilityStatus.UNAVAILABLE:
        return CapabilityEntry(
            status=status, verified=False, source="observed rejected"
        )
    raise AssertionError(f"no non-verified entry builder for {status}")


def _invoker_with_model(
    transport, credentials_env, all_profiles, model_profiles, profile
):
    models = dict(model_profiles)
    models[profile.model_ref] = profile
    return Invoker(
        InvocationContext(
            providers=all_profiles,
            models=models,
            transport=transport,
            transport_settings_for=lambda _pid: TransportSettings(),
            environ=credentials_env,
        )
    )


class TestBaselineIsUnknown:
    """The premise of every gate: nothing shipped is verified."""

    def test_every_gated_capability_is_unknown_on_every_model(self, model_profiles):
        for ref, profile in model_profiles.items():
            for capability in ALL_CAPABILITIES:
                entry = profile.capability(capability)
                assert entry.status is CapabilityStatus.UNKNOWN, (
                    f"{ref}:{capability.value}"
                )


class TestToolsGate:
    def test_tools_with_unknown_capability_is_blocked(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(
            _request(tools=({"type": "function", "function": {"name": "x"}},))
        )

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.code is BlockCode.CAPABILITY_NOT_VERIFIED
        assert result.blocked.required_capability is CapabilityName.TOOL_CALLING
        assert result.blocked.actual_status is CapabilityStatus.UNKNOWN
        # The hard exit criterion: nothing was sent.
        assert transport.requests == []

    def test_an_empty_tools_list_does_not_gate(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(tools=()))

        assert result.status is InvocationStatus.SUCCESS
        assert len(transport.requests) == 1


class TestStructuredOutputGate:
    @pytest.mark.parametrize(
        "mode,schema",
        [
            (StructuredOutputMode.JSON_OBJECT, None),
            (StructuredOutputMode.JSON_SCHEMA, {"type": "object"}),
        ],
    )
    def test_structured_output_with_unknown_capability_is_blocked(
        self,
        mode,
        schema,
        fake_transport_factory,
        credentials_env,
        model_profiles,
        all_profiles,
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(
            _request(structured_output=StructuredOutputRequest(mode, schema))
        )

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.required_capability is CapabilityName.STRUCTURED_OUTPUT
        assert transport.requests == []

    def test_json_object_is_not_treated_as_json_schema(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        """`json_object` is gated too: JSON mode is not schema enforcement."""
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(
            _request(
                structured_output=StructuredOutputRequest(StructuredOutputMode.JSON_OBJECT)
            )
        )

        assert result.status is InvocationStatus.BLOCKED
        assert transport.requests == []

    def test_mode_none_does_not_gate(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(
            _request(
                structured_output=StructuredOutputRequest(StructuredOutputMode.NONE)
            )
        )

        assert result.status is InvocationStatus.SUCCESS
        assert len(transport.requests) == 1


class TestStreamGate:
    def test_stream_true_with_unknown_capability_is_blocked(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(stream=True))

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.required_capability is CapabilityName.STREAMING
        assert transport.requests == []

    def test_stream_is_never_silently_downgraded(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        """A silent downgrade to `stream: false` would hide a broken capability."""
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        invoker.invoke(_request(stream=True))

        assert transport.requests == []
        assert not any(
            "stream" in str(request.body) for request in transport.requests
        )

    def test_stream_false_does_not_gate(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        assert invoker.invoke(_request(stream=False)).status is InvocationStatus.SUCCESS


class TestOnlyVerifiedAuthorises:
    @pytest.mark.parametrize(
        "status",
        [
            CapabilityStatus.UNKNOWN,
            CapabilityStatus.NOT_VERIFIED,
            CapabilityStatus.DECLARED,
            CapabilityStatus.UNAVAILABLE,
        ],
    )
    def test_non_verified_statuses_do_not_authorise(
        self,
        status,
        fake_transport_factory,
        credentials_env,
        model_profiles,
        all_profiles,
    ):
        entry = _entry_for(status)

        profile = _with_capability(
            model_profiles["deepseek/deepseek-flash"], CapabilityName.TOOL_CALLING, entry
        )
        transport = fake_transport_factory.success()
        invoker = _invoker_with_model(
            transport, credentials_env, all_profiles, model_profiles, profile
        )

        result = invoker.invoke(_request(tools=({"type": "function"},)))

        assert result.status is InvocationStatus.BLOCKED, status
        assert result.blocked.actual_status is status
        assert transport.requests == []

    def test_verified_authorises(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        """The gate's other side: VERIFIED lets the call through."""
        profile = _with_capability(
            model_profiles["deepseek/deepseek-flash"],
            CapabilityName.TOOL_CALLING,
            CapabilityEntry(status=CapabilityStatus.VERIFIED, verified=True),
        )
        transport = fake_transport_factory.success()
        invoker = _invoker_with_model(
            transport, credentials_env, all_profiles, model_profiles, profile
        )

        result = invoker.invoke(_request(tools=({"type": "function"},)))

        assert result.status is InvocationStatus.SUCCESS
        assert len(transport.requests) == 1

    def test_verified_streaming_authorises_stream(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        profile = _with_capability(
            model_profiles["deepseek/deepseek-flash"],
            CapabilityName.STREAMING,
            CapabilityEntry(status=CapabilityStatus.VERIFIED, verified=True),
        )
        transport = fake_transport_factory.success()
        invoker = _invoker_with_model(
            transport, credentials_env, all_profiles, model_profiles, profile
        )

        result = invoker.invoke(_request(stream=True))

        assert result.status is InvocationStatus.SUCCESS
        assert len(transport.requests) == 1


class TestGateOrdering:
    def test_gate_precedes_credential_resolution(
        self, fake_transport_factory, all_profiles, model_profiles
    ):
        """A gated call is refused even with no credential available.

        Ordering matters: the refusal must be about policy, not about the
        environment, so the reason a caller sees is the actionable one.
        """
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, {}, model_profiles, all_profiles)

        result = invoker.invoke(_request(stream=True))

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.code is BlockCode.CAPABILITY_NOT_VERIFIED
        assert result.error is None

    def test_a_blocked_result_carries_no_content(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(tools=({"type": "function"},)))

        assert result.text is None
        assert result.tool_calls == ()
        assert result.usage is None
        assert not result.ok

    def test_a_blocked_result_is_still_attributed(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(stream=True))

        assert result.provider_id == "deepseek"
        assert result.model_id == "deepseek-flash"
        assert result.model_ref == "deepseek/deepseek-flash"

    def test_multiple_requirements_report_the_first_gate(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(
            _request(tools=({"type": "function"},), stream=True, structured_output=None)
        )

        assert result.blocked.required_capability is CapabilityName.TOOL_CALLING
        assert transport.requests == []


class TestBlockedResultShape:
    """A refusal reached no provider, so it has no provider finish reason.

    §7.3 defines `ERROR` as "provider signalled failure". Nothing was sent, so
    writing `ERROR` here would claim an interaction that never happened.
    """

    def test_a_capability_block_has_unknown_finish_state(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(stream=True))

        assert result.status is InvocationStatus.BLOCKED
        assert result.finish_state is FinishState.UNKNOWN
        assert result.finish_state is not FinishState.ERROR

    def test_a_capability_block_carries_no_provider_error(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(tools=({"type": "function"},)))

        assert result.error is None
        assert result.blocked is not None
        assert result.blocked.code is BlockCode.CAPABILITY_NOT_VERIFIED

    @pytest.mark.parametrize(
        "code,request_kwargs,model_ref",
        [
            (BlockCode.CAPABILITY_NOT_VERIFIED, {"stream": True}, "deepseek/deepseek-flash"),
            (BlockCode.UNKNOWN_MODEL, {}, "deepseek/not-a-real-model"),
            (BlockCode.UNKNOWN_PROVIDER, {}, "openai-compatible/gpt"),
        ],
    )
    def test_every_invocation_layer_block_has_the_same_shape(
        self,
        code,
        request_kwargs,
        model_ref,
        fake_transport_factory,
        credentials_env,
        model_profiles,
        all_profiles,
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(_request(model_ref=model_ref, **request_kwargs))

        assert result.status is InvocationStatus.BLOCKED, code
        assert result.finish_state is FinishState.UNKNOWN, code
        assert result.error is None, code
        assert result.blocked is not None, code
        assert result.blocked.code is code
        assert transport.requests == [], code

    def test_a_blocked_result_is_never_a_success(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)
        assert not invoker.invoke(_request(stream=True)).ok


class TestGenerationDefaultsDoNotGate:
    def test_generation_parameters_do_not_require_a_capability(
        self, fake_transport_factory, credentials_env, model_profiles, all_profiles
    ):
        transport = fake_transport_factory.success()
        invoker = _invoker(transport, credentials_env, model_profiles, all_profiles)

        result = invoker.invoke(
            _request(generation=GenerationParameters(temperature=0.2, max_output=64))
        )

        assert result.status is InvocationStatus.SUCCESS
