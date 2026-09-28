"""Provider -> normalized result.

Contract §7.2, §7.3, §9-§13. A caller must be able to consume this result
without knowing which provider produced it or what its JSON looked like.
"""

from __future__ import annotations

import pytest

from providers.invocation import (
    InvocationRequest,
    InvocationStatus,
    Message,
    MessageRole,
    UsageStatus,
)
from providers.protocol import FinishState
from providers.transport import TransportSettings


def _request(**overrides) -> InvocationRequest:
    base = {
        "model_ref": "deepseek/deepseek-flash",
        "messages": (Message(MessageRole.USER, "ping"),),
        "timeout_ms": 120_000,
    }
    base.update(overrides)
    return InvocationRequest(**base)


def _invoke(invoker_factory, fake_transport_factory, payload, **request_overrides):
    transport = fake_transport_factory.success(payload)
    return invoker_factory(transport).invoke(_request(**request_overrides))


class TestText:
    def test_content_becomes_text(self, invoker_factory, fake_transport_factory, completion_payload):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.status is InvocationStatus.SUCCESS
        assert result.text == "hello"

    def test_absent_content_yields_none_not_empty_string(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"] = {"role": "assistant"}
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.text is None
        assert result.text != ""

    def test_null_content_yields_none(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"] = {"role": "assistant", "content": None}
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.status is InvocationStatus.SUCCESS
        assert result.text is None

    def test_no_fake_text_is_manufactured(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"] = {"role": "assistant"}
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert not result.text


class TestReasoningSeparation:
    def test_reasoning_goes_to_its_own_field(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"]["reasoning_content"] = "step by step"
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.reasoning == "step by step"
        assert result.text == "hello"

    def test_reasoning_is_never_concatenated_into_text(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"]["reasoning_content"] = "secret thinking"
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert "secret thinking" not in (result.text or "")

    def test_absent_reasoning_is_none(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.reasoning is None


class TestToolCalls:
    def test_tool_calls_are_normalized_and_flattened(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"a"}'},
                }
            ],
        }
        payload["choices"][0]["finish_reason"] = "tool_calls"

        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert len(result.tool_calls) == 1
        call = result.tool_calls[0]
        assert call.name == "read_file"
        assert call.id == "call_1"
        assert call.arguments == '{"path":"a"}'

    def test_the_provider_function_wrapper_is_not_exposed(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "tool_calls": [
                {"id": "c", "function": {"name": "f", "arguments": "{}"}}
            ],
        }
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert "function" not in result.tool_calls[0].to_dict()

    def test_tool_calls_do_not_leak_into_text(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c", "function": {"name": "danger", "arguments": "{}"}}
            ],
        }
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert "danger" not in (result.text or "")

    def test_arguments_are_not_parsed(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """Parsing would assert well-formedness the provider never confirmed."""
        payload = completion_payload()
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "tool_calls": [
                {"id": "c", "function": {"name": "f", "arguments": "{not json"}}
            ],
        }
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.tool_calls[0].arguments == "{not json"

    def test_a_malformed_tool_call_is_refused_not_dropped(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """Dropping it would lose the model's intent while reporting success."""
        payload = completion_payload()
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "tool_calls": [{"id": "c"}],  # no function
        }
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.status is InvocationStatus.ERROR
        assert result.error.error_class.value == "PROTOCOL"


class TestStructuredOutput:
    def test_structured_output_stays_none(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.structured_output is None

    def test_json_looking_text_is_not_parsed_into_structured_output(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """§12: the provider never claimed schema conformance."""
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = '{"answer": 42}'
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.text == '{"answer": 42}'
        assert result.structured_output is None


class TestFinishStates:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("stop", FinishState.STOP),
            ("length", FinishState.LENGTH),
            ("tool_calls", FinishState.TOOL_CALLS),
            ("content_filter", FinishState.CONTENT_FILTER),
            ("something_new", FinishState.UNKNOWN),
            ("function_call", FinishState.UNKNOWN),  # legacy, deliberately unmapped
            (None, FinishState.UNKNOWN),
        ],
    )
    def test_reason_mapping(
        self, raw, expected, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = raw
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.finish_state is expected

    def test_length_is_not_stop(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """A truncated answer must not read as a natural finish (§7.3)."""
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = "length"
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.finish_state is FinishState.LENGTH
        assert result.finish_state is not FinishState.STOP
        assert result.is_truncated

    def test_unknown_is_not_stop(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = "vendor_specific_thing"
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.finish_state is FinishState.UNKNOWN
        assert result.finish_state is not FinishState.STOP

    def test_tool_calls_are_not_a_final_answer(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = "tool_calls"
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "c", "function": {"name": "f", "arguments": "{}"}}],
        }
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.finish_state is FinishState.TOOL_CALLS
        assert result.tool_calls
        assert result.text is None

    def test_an_empty_text_tool_call_is_not_an_error(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = "tool_calls"
        payload["choices"][0]["message"] = {
            "role": "assistant",
            "tool_calls": [{"id": "c", "function": {"name": "f", "arguments": "{}"}}],
        }
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.status is not InvocationStatus.ERROR

    def test_content_filter_is_not_success(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = "content_filter"
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.status is not InvocationStatus.SUCCESS
        assert result.status is InvocationStatus.ERROR
        assert result.finish_state is FinishState.CONTENT_FILTER
        assert result.error.error_class.value == "CONTENT_FILTER"


class TestMalformedPayloads:
    def test_non_object_payload_is_protocol_error(
        self, invoker_factory, fake_transport_factory
    ):
        result = _invoke(invoker_factory, fake_transport_factory, "not-an-object")
        assert result.status is InvocationStatus.ERROR
        assert result.error.error_class.value == "PROTOCOL"
        assert result.error.stage.value == "parse"

    @pytest.mark.parametrize("choices", [[], None, "nope"])
    def test_missing_choices_is_protocol_error(
        self, choices, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["choices"] = choices
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.status is InvocationStatus.ERROR
        assert result.error.error_class.value == "PROTOCOL"

    def test_non_text_content_is_refused(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """v1 declares text output; a non-text shape must not become empty success."""
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = [{"type": "image_url"}]
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.status is InvocationStatus.ERROR
        assert result.error.error_class.value == "PROTOCOL"

    def test_a_malformed_payload_is_never_success(
        self, invoker_factory, fake_transport_factory
    ):
        result = _invoke(invoker_factory, fake_transport_factory, {"choices": [{}]})
        assert not result.ok


class TestUsage:
    def test_reported_counts_are_preserved(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.usage.input_tokens == 11
        assert result.usage.output_tokens == 7
        assert result.usage.total_tokens == 18
        assert result.usage.usage_status is UsageStatus.REPORTED

    def test_absent_usage_is_none_not_zero(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """Zero is a measurement; absence is not (§9.2)."""
        payload = completion_payload()
        del payload["usage"]
        result = _invoke(invoker_factory, fake_transport_factory, payload)

        assert result.usage.input_tokens is None
        assert result.usage.output_tokens is None
        assert result.usage.input_tokens != 0
        assert result.usage.usage_status is UsageStatus.UNKNOWN

    def test_a_genuine_zero_is_preserved(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        payload["usage"] = {"prompt_tokens": 0, "completion_tokens": 0}
        result = _invoke(invoker_factory, fake_transport_factory, payload)
        assert result.usage.input_tokens == 0
        assert result.usage.usage_status is UsageStatus.REPORTED

    def test_cache_tokens_are_not_guessed(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.usage.cache_read_tokens is None
        assert result.usage.cache_write_tokens is None


class TestAttribution:
    def test_attribution_is_carried_explicitly(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.provider_id == "deepseek"
        assert result.model_id == "deepseek-flash"
        assert result.model_ref == "deepseek/deepseek-flash"

    def test_model_id_is_the_api_id_not_the_display_name(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.model_id != "DeepSeek-V4.1-Flash"

    def test_mimo_is_attributed_to_mimo(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        payload = completion_payload()
        result = _invoke(
            invoker_factory,
            fake_transport_factory,
            payload,
            model_ref="mimo/mimo-v2.6-pro",
        )
        assert result.provider_id == "mimo"
        assert result.model_id == "mimo-v2.6-pro"

    def test_request_id_round_trips(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(
            invoker_factory,
            fake_transport_factory,
            completion_payload(),
            request_id="wb-round-trip",
        )
        assert result.request_id == "wb-round-trip"

    def test_provider_request_id_is_preserved(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.raw_response_ref is None

    def test_that_unused_placeholder_is_not_used_as_an_artifact(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """§17: no artifact subsystem in this phase."""
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.raw_response_ref is None


class TestLatencyAndAttempts:
    def test_latency_is_recorded(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        ticks = iter([100.0, 100.25])
        transport = fake_transport_factory.success(completion_payload())
        result = invoker_factory(transport, clock=lambda: next(ticks)).invoke(_request())

        assert result.latency.total_ms == 250

    def test_ttfb_is_not_fabricated(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        result = _invoke(invoker_factory, fake_transport_factory, completion_payload())
        assert result.latency.ttfb_ms is None

    def test_attempts_is_one(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        transport = fake_transport_factory.success(completion_payload())
        result = invoker_factory(transport).invoke(_request())

        assert result.attempts == 1
        assert len(transport.requests) == 1

    def test_no_retry_occurs_on_failure(
        self, invoker_factory, fake_transport_factory
    ):
        """AI-02 implements no retry loop (§5.11, D-12)."""
        transport = fake_transport_factory.timeout()
        result = invoker_factory(transport).invoke(_request())

        assert result.attempts == 1
        assert len(transport.requests) == 1


class TestInvocationDeadline:
    """The request deadline is an invocation-level cap, not metadata.

    Runtime config stays the operator's ceiling: a request may tighten a
    budget but never widen one, so a caller cannot raise a configured limit
    by asking for a longer call.
    """

    RUNTIME = TransportSettings(timeout_connect_ms=10_000, timeout_total_ms=120_000)

    def _sent_request(self, invoker_factory, fake_transport_factory, payload, timeout_ms):
        transport = fake_transport_factory.success(payload)
        invoker_factory(transport, settings=self.RUNTIME).invoke(
            _request(timeout_ms=timeout_ms)
        )
        return transport.requests[0]

    def test_a_shorter_request_tightens_the_total_deadline(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        request = self._sent_request(
            invoker_factory, fake_transport_factory, completion_payload(), 1_000
        )
        assert request.timeout_total_ms == 1_000
        assert request.timeout_total_ms < self.RUNTIME.timeout_total_ms

    def test_a_longer_request_cannot_raise_the_runtime_ceiling(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        request = self._sent_request(
            invoker_factory, fake_transport_factory, completion_payload(), 180_000
        )
        assert request.timeout_total_ms == self.RUNTIME.timeout_total_ms
        assert request.timeout_total_ms == 120_000

    def test_a_request_shorter_than_connect_reduces_connect_coherently(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        request = self._sent_request(
            invoker_factory, fake_transport_factory, completion_payload(), 500
        )
        assert request.timeout_connect_ms == 500
        assert request.timeout_total_ms == 500

    @pytest.mark.parametrize("timeout_ms", [1, 500, 10_000, 120_000, 180_000])
    def test_connect_never_exceeds_total(
        self, timeout_ms, invoker_factory, fake_transport_factory, completion_payload
    ):
        request = self._sent_request(
            invoker_factory, fake_transport_factory, completion_payload(), timeout_ms
        )
        assert request.timeout_connect_ms <= request.timeout_total_ms

    def test_the_deadline_is_never_looser_than_either_bound(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        for timeout_ms in (1, 500, 10_000, 120_000, 180_000):
            request = self._sent_request(
                invoker_factory, fake_transport_factory, completion_payload(), timeout_ms
            )
            assert request.timeout_total_ms <= min(timeout_ms, self.RUNTIME.timeout_total_ms)

    def test_other_transport_settings_are_preserved(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """Composition adjusts deadlines only; it does not invent settings."""
        transport = fake_transport_factory.success(completion_payload())
        runtime = TransportSettings(
            timeout_connect_ms=10_000, timeout_total_ms=120_000, max_retries=0, verify_tls=True
        )
        invoker_factory(transport, settings=runtime).invoke(_request(timeout_ms=1_000))

        request = transport.requests[0]
        assert request.verify_tls is True

    def test_a_blocked_call_sends_nothing_regardless_of_deadline(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        invoker_factory(transport, settings=self.RUNTIME).invoke(
            _request(timeout_ms=1, stream=True)
        )
        assert transport.requests == []


class TestOutboundBody:
    def test_model_field_is_the_api_model_id(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        import json

        transport = fake_transport_factory.success(completion_payload())
        invoker_factory(transport).invoke(_request())

        body = json.loads(transport.requests[0].body)
        assert body["model"] == "deepseek-flash"
        assert body["model"] != "DeepSeek-V4.1-Flash"
        assert body["model"] != "deepseek"

    def test_messages_are_forwarded(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        import json

        transport = fake_transport_factory.success(completion_payload())
        invoker_factory(transport).invoke(
            _request(messages=(Message(MessageRole.SYSTEM, "be terse"), Message(MessageRole.USER, "hi")))
        )

        body = json.loads(transport.requests[0].body)
        assert body["messages"] == [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ]

    def test_stream_is_sent_as_false_by_default(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        import json

        transport = fake_transport_factory.success(completion_payload())
        invoker_factory(transport).invoke(_request())
        assert json.loads(transport.requests[0].body)["stream"] is False

    def test_absent_generation_parameters_are_omitted(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        import json

        transport = fake_transport_factory.success(completion_payload())
        invoker_factory(transport).invoke(_request())

        body = json.loads(transport.requests[0].body)
        assert "temperature" not in body
        assert "max_tokens" not in body

    def test_credential_is_only_in_the_authorization_header(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        from tests.conftest import PLACEHOLDER_CREDENTIAL

        transport = fake_transport_factory.success(completion_payload())
        invoker_factory(transport).invoke(_request())

        request = transport.requests[0]
        assert request.headers["Authorization"].endswith(PLACEHOLDER_CREDENTIAL)
        assert PLACEHOLDER_CREDENTIAL not in request.url
        assert PLACEHOLDER_CREDENTIAL not in (request.body or "")
