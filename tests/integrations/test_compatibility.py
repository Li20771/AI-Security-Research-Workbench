"""Tool-calling and structured-output compatibility (contract §15, §16).

Layer 1: the protocol adapter / normalization boundary, tested directly. No
transport, no `Invoker`, and no fabricated verified model.

This is the shape contract §14.4 requires. `Invoker` gates any request carrying
`tools`, `structured_output` or `stream: true`, and every shipped capability is
`UNKNOWN`, so a tool-call request cannot pass the gate. Testing the serializer
and the parser where they live is how that is observed without weakening the
gate or inventing a "verified model" to get through it.
"""

from __future__ import annotations

import json

import pytest

from providers.model_profile import CapabilityName, CapabilityStatus
from providers.profile import ModelRef, ProfileError
from providers.protocol import StructuredOutputSpec
from providers.protocol.openai_compatible_chat import OpenAICompatibleChatAdapter

pytestmark = pytest.mark.layer1

MODEL_REF = ModelRef.parse("mimo/mimo-v2.6-pro")

#: One bounded, provider-neutral schema. The probe observes whether the mechanism
#: round-trips, not whether a model chooses well.
TOOL_SCHEMA = (
    {
        "type": "function",
        "function": {
            "name": "workbench_probe",
            "description": "Records a fixed probe value.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        },
    },
)


@pytest.fixture
def adapter() -> OpenAICompatibleChatAdapter:
    return OpenAICompatibleChatAdapter()


class TestToolCallingSerialization:
    def test_a_tool_schema_is_emitted_when_the_invocation_supplies_one(self, adapter):
        payload = adapter.build_payload(
            model_id="mimo-v2.6-pro",
            messages=[{"role": "user", "content": "call it"}],
            tools=TOOL_SCHEMA,
        )
        assert payload["tools"] == list(TOOL_SCHEMA)

    def test_no_tools_key_when_the_invocation_supplies_none(self, adapter):
        payload = adapter.build_payload(
            model_id="mimo-v2.6-pro", messages=[{"role": "user", "content": "hi"}]
        )
        assert "tools" not in payload

    def test_the_schema_is_protocol_input_not_context(self, adapter):
        """A schema is a Layer B control field: a request carrying one is well-formed."""
        payload = adapter.build_payload(
            model_id="mimo-v2.6-pro",
            messages=[{"role": "user", "content": "call it"}],
            tools=TOOL_SCHEMA,
        )
        assert set(payload) <= {"model", "messages", "stream", "tools"}


class TestToolCallNormalization:
    def _payload(self, **message_overrides):
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "workbench_probe",
                        "arguments": '{"value":"ok"}',
                    },
                }
            ],
        }
        message.update(message_overrides)
        return {
            "id": "chatcmpl-1",
            "choices": [
                {"index": 0, "message": message, "finish_reason": "tool_calls"}
            ],
        }

    def test_a_tool_call_is_flattened_into_the_normalized_shape(self, adapter, mimo_profile):
        response = adapter.parse_response(mimo_profile, MODEL_REF, self._payload())
        assert response.tool_calls == (
            {"id": "call-1", "name": "workbench_probe", "arguments": '{"value":"ok"}'},
        )

    def test_arguments_stay_the_raw_string_the_provider_sent(self, adapter, mimo_profile):
        """Parsing them here would assert a well-formedness nobody confirmed."""
        payload = self._payload()
        payload["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{oops"
        response = adapter.parse_response(mimo_profile, MODEL_REF, payload)
        assert response.tool_calls[0]["arguments"] == "{oops"

    def test_tool_calls_do_not_leak_into_text(self, adapter, mimo_profile):
        response = adapter.parse_response(mimo_profile, MODEL_REF, self._payload())
        assert response.text is None

    def test_the_finish_state_is_tool_calls(self, adapter, mimo_profile):
        response = adapter.parse_response(mimo_profile, MODEL_REF, self._payload())
        assert str(response.finish_state) == "TOOL_CALLS"

    def test_a_malformed_tool_call_is_refused_not_dropped(self, adapter, mimo_profile):
        """Discarding it would lose the model's intent while still reporting success."""
        from providers.errors import ErrorClass, ProviderError

        payload = self._payload()
        del payload["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
        with pytest.raises(ProviderError) as excinfo:
            adapter.parse_response(mimo_profile, MODEL_REF, payload)
        assert excinfo.value.error_class is ErrorClass.PROTOCOL


class TestTheProbeExecutesNothing:
    def test_no_integration_module_reaches_a_tool_layer(self):
        """The compatibility path has no route to AI-06, so it cannot execute a call."""
        import ast
        import pathlib

        forbidden = ("tools", "plugins.security_tools")
        for path in sorted(pathlib.Path("integrations").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not any(
                        node.module == f or node.module.startswith(f + ".")
                        for f in forbidden
                    ), f"{path}: imports {node.module}"
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not any(
                            alias.name == f or alias.name.startswith(f + ".")
                            for f in forbidden
                        ), f"{path}: imports {alias.name}"

    def test_a_normalized_tool_call_is_data_and_nothing_more(self, adapter, mimo_profile):
        response = adapter.parse_response(mimo_profile, MODEL_REF, {
            "id": "chatcmpl-1",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "workbench_probe",
                                    "arguments": '{"value":"ok"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        })
        assert isinstance(response.tool_calls, tuple)
        assert all(isinstance(entry, dict) for entry in response.tool_calls)


class TestStructuredOutputSerialization:
    def test_json_object_requests_the_json_object_mode(self, adapter):
        payload = adapter.build_payload(
            model_id="mimo-v2.6-pro",
            messages=[{"role": "user", "content": "json please"}],
            structured_output=StructuredOutputSpec(mode="json_object"),
        )
        assert payload["response_format"] == {"type": "json_object"}

    def test_json_schema_uses_a_different_wrapper(self, adapter):
        """The two modes are never interchangeable, and never serialized alike."""
        payload = adapter.build_payload(
            model_id="mimo-v2.6-pro",
            messages=[{"role": "user", "content": "json please"}],
            structured_output=StructuredOutputSpec(
                mode="json_schema", schema={"type": "object"}
            ),
        )
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"] != {"type": "json_object"}

    def test_no_response_format_when_nothing_is_requested(self, adapter):
        payload = adapter.build_payload(
            model_id="mimo-v2.6-pro", messages=[{"role": "user", "content": "hi"}]
        )
        assert "response_format" not in payload


class TestStructuredOutputNormalization:
    def test_a_json_looking_answer_is_not_claimed_as_structured_output(
        self, adapter, mimo_profile
    ):
        """Parsing text as JSON would assert schema conformance nobody claimed."""
        payload = {
            "id": "chatcmpl-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": '{"status":"ok"}'},
                    "finish_reason": "stop",
                }
            ],
        }
        response = adapter.parse_response(mimo_profile, MODEL_REF, payload)
        assert response.structured_output is None
        assert response.text == '{"status":"ok"}'


class TestNoCapabilityIsPromoted:
    def test_both_mimo_profiles_remain_unknown(self, models):
        for ref in ("mimo/mimo-v2.6-pro", "mimo/mimo-v2.6-flash"):
            profile = models[ref]
            for name in CapabilityName:
                assert (
                    profile.capability(name).status is CapabilityStatus.UNKNOWN
                ), f"{ref}:{name}"

    def test_the_gate_refuses_tools_through_the_invoker(
        self, providers, models, credentials_env, fake_transport_factory
    ):
        """The end-to-end consequence of the above: a tool request never reaches a transport."""
        from providers.invocation import (
            InvocationContext,
            InvocationRequest,
            InvocationStatus,
            Invoker,
            Message,
            MessageRole,
        )
        from providers.transport import TransportSettings

        transport = fake_transport_factory.success()
        context = InvocationContext(
            providers=providers,
            models=models,
            transport=transport,
            transport_settings_for=lambda _pid: TransportSettings(),
            environ=credentials_env,
        )
        result = Invoker(context).invoke(
            InvocationRequest(
                model_ref="mimo/mimo-v2.6-pro",
                messages=(Message(role=MessageRole.USER, content="x"),),
                timeout_ms=1_000,
                tools=TOOL_SCHEMA,
            )
        )
        assert result.status is InvocationStatus.BLOCKED
        assert str(result.blocked.code) == "CAPABILITY_NOT_VERIFIED"
        assert transport.requests == []

    def test_the_integration_layer_cannot_write_a_profile(self):
        """No file I/O in `integrations/` at all, so no profile can be mutated.

        A capability is promoted by a reviewed edit to a profile, never as a side
        effect of a call. The strongest available guarantee of that is structural:
        the layer has no way to write anything.
        """
        import ast
        import pathlib

        for path in sorted(pathlib.Path("integrations").rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for marker in ("write_text", "write_bytes", "open("):
                assert marker not in source, f"{path}: {marker}"
            tree = ast.parse(source)
            roots = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots.add(node.module.split(".")[0])
            assert "yaml" not in roots, f"{path}: imports yaml"
