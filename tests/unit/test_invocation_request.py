"""Invocation request contract.

§7.1. The request is provider-neutral: it carries no credential, no endpoint,
and no transport setting, and it cannot name a model without a provider.
"""

from __future__ import annotations

import dataclasses

import pytest

from providers.invocation import (
    GenerationParameters,
    InvocationError,
    InvocationRequest,
    Message,
    MessageRole,
    RequestMetadata,
    StructuredOutputRequest,
    new_request_id,
)
from providers.model_profile import StructuredOutputMode


def _request(**overrides) -> InvocationRequest:
    base = {
        "model_ref": "deepseek/deepseek-flash",
        "messages": (Message(MessageRole.USER, "ping"),),
        "timeout_ms": 120_000,
    }
    base.update(overrides)
    return InvocationRequest(**base)


class TestModelReference:
    def test_a_qualified_ref_is_accepted(self):
        assert _request().parsed_model_ref.provider_id == "deepseek"
        assert _request().parsed_model_ref.model_id == "deepseek-flash"

    @pytest.mark.parametrize(
        "bare", ["deepseek-flash", "mimo-v2.6-pro", "deepseek", ""]
    )
    def test_a_bare_model_id_is_rejected(self, bare):
        """A bare id loses provider attribution (§7.1)."""
        with pytest.raises(Exception):
            _request(model_ref=bare)

    def test_an_unqualified_ref_cannot_be_constructed_at_all(self):
        assert "model_ref" in {f.name for f in dataclasses.fields(InvocationRequest)}


class TestRequestId:
    def test_generated_ids_are_unique_and_prefixed(self):
        ids = {new_request_id() for _ in range(200)}
        assert len(ids) == 200
        assert all(value.startswith("wb-") for value in ids)

    def test_a_supplied_request_id_is_kept_verbatim(self):
        request = _request(request_id="wb-explicit-1")
        assert request.request_id == "wb-explicit-1"

    def test_request_id_must_not_be_blank(self):
        with pytest.raises(InvocationError, match="request_id"):
            _request(request_id="   ")


class TestTimeout:
    def test_timeout_is_required(self):
        with pytest.raises(TypeError):
            InvocationRequest(
                model_ref="deepseek/deepseek-flash",
                messages=(Message(MessageRole.USER, "x"),),
            )

    @pytest.mark.parametrize("bad", [0, -1, -120_000])
    def test_non_positive_timeouts_are_rejected(self, bad):
        with pytest.raises(InvocationError, match="timeout_ms"):
            _request(timeout_ms=bad)

    @pytest.mark.parametrize("bad", [None, True, "120000", float("inf"), float("nan")])
    def test_non_finite_timeouts_are_rejected(self, bad):
        with pytest.raises(InvocationError, match="timeout_ms"):
            _request(timeout_ms=bad)

    def test_a_finite_timeout_is_accepted(self):
        assert _request(timeout_ms=1).timeout_ms == 1


class TestMessages:
    def test_messages_must_not_be_empty(self):
        with pytest.raises(InvocationError, match="messages"):
            _request(messages=())

    def test_every_frozen_role_is_representable(self):
        assert {role.value for role in MessageRole} == {
            "system",
            "user",
            "assistant",
            "tool",
        }
        for role in MessageRole:
            assert Message(role, "x").to_dict()["role"] == role.value

    def test_an_unknown_role_is_rejected(self):
        with pytest.raises(InvocationError, match="role"):
            Message("wizard", "x")  # type: ignore[arg-type]

    def test_message_content_must_be_a_string(self):
        with pytest.raises(InvocationError, match="content"):
            Message(MessageRole.USER, 42)  # type: ignore[arg-type]


class TestStream:
    @pytest.mark.parametrize("bad", ["true", 1, None])
    def test_stream_must_be_a_bool(self, bad):
        with pytest.raises(InvocationError, match="stream"):
            _request(stream=bad)

    def test_stream_defaults_to_false(self):
        assert _request().stream is False


class TestStructuredOutput:
    def test_json_schema_requires_a_schema(self):
        with pytest.raises(InvocationError, match="schema"):
            StructuredOutputRequest(StructuredOutputMode.JSON_SCHEMA)

    def test_json_object_is_valid_without_a_schema(self):
        request = StructuredOutputRequest(StructuredOutputMode.JSON_OBJECT)
        assert request.requires_capability

    def test_none_mode_requests_nothing(self):
        request = StructuredOutputRequest(StructuredOutputMode.NONE)
        assert not request.requires_capability
        assert request.to_spec() is None

    def test_none_mode_must_not_carry_a_schema(self):
        with pytest.raises(InvocationError, match="schema"):
            StructuredOutputRequest(StructuredOutputMode.NONE, schema={"type": "object"})

    def test_modes_are_not_interchangeable(self):
        schema_request = StructuredOutputRequest(
            StructuredOutputMode.JSON_SCHEMA, schema={"type": "object"}
        )
        object_request = StructuredOutputRequest(StructuredOutputMode.JSON_OBJECT)
        assert schema_request.to_spec().mode == "json_schema"
        assert object_request.to_spec().mode == "json_object"
        assert schema_request.to_spec().mode != object_request.to_spec().mode


class TestGeneration:
    def test_defaults_are_all_absent(self):
        generation = GenerationParameters()
        assert generation.temperature is None
        assert generation.max_output is None
        assert generation.stop == ()

    @pytest.mark.parametrize("bad", [-1, -0.5, float("inf"), float("nan"), True])
    def test_invalid_temperature_is_rejected(self, bad):
        with pytest.raises(InvocationError, match="temperature"):
            GenerationParameters(temperature=bad)

    @pytest.mark.parametrize("bad", [0, -1, True, 1.5])
    def test_invalid_max_output_is_rejected(self, bad):
        with pytest.raises(InvocationError, match="max_output"):
            GenerationParameters(max_output=bad)


class TestCredentialBoundary:
    """§16: a credential never appears in a request or on the request object."""

    @pytest.mark.parametrize(
        "forbidden",
        ["credential", "api_key", "apikey", "secret", "token", "authorization", "headers"],
    )
    def test_request_has_no_credential_field(self, forbidden):
        assert forbidden not in {f.name for f in dataclasses.fields(InvocationRequest)}

    def test_serialized_request_carries_no_credential(self, credentials_env):
        payload = _request().to_dict()
        rendered = repr(payload) + repr(_request())
        for value in credentials_env.values():
            assert value not in rendered
        assert "sk-" not in rendered

    def test_request_cannot_be_given_a_credential_attribute(self):
        request = _request()
        with pytest.raises((AttributeError, TypeError)):
            request.credential = "sk-nope"  # type: ignore[misc]
        assert not hasattr(request, "credential")


class TestMetadata:
    def test_metadata_is_not_part_of_the_provider_prompt(self, completion_payload):
        """Workbench metadata is internal attribution (§7.4)."""
        from providers.protocol import adapter_for

        request = _request(
            metadata=RequestMetadata(
                experiment_id="AI-02-B3-001", task_class="complex-security", agent="dsh"
            )
        )
        adapter = adapter_for("openai_compatible_chat")
        body = adapter.build_payload(
            model_id="deepseek-flash",
            messages=[message.to_dict() for message in request.messages],
        )
        rendered = repr(body)
        assert "AI-02-B3-001" not in rendered
        assert "complex-security" not in rendered

    def test_metadata_values_must_be_strings_or_null(self):
        with pytest.raises(InvocationError, match="experiment_id"):
            RequestMetadata(experiment_id=42)  # type: ignore[arg-type]


class TestRequestIsImmutable:
    def test_fields_are_frozen(self):
        request = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            request.model_ref = "mimo/mimo-v2.6-pro"  # type: ignore[misc]
