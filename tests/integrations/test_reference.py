"""The reference digest (contract §19.2.1).

Layer 1: pure functions over AI-02's normalized result types. No transport.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from providers.invocation import (
    InvocationResult,
    InvocationStatus,
    ToolCall,
    Usage,
    UsageStatus,
)
from providers.protocol import FinishState

from integrations.codex.errors import CodexInvocationError
from integrations.codex.reference import (
    REFERENCE_RE,
    canonical_json,
    reference_for,
    select_digest_input,
)

pytestmark = pytest.mark.layer1


def _result(**overrides) -> InvocationResult:
    base = {
        "request_id": "wb-test",
        "provider_id": "mimo",
        "model_id": "mimo-v2.6-pro",
        "model_ref": "mimo/mimo-v2.6-pro",
        "status": InvocationStatus.SUCCESS,
        "text": "hello",
        "finish_state": FinishState.STOP,
        "usage": Usage(usage_status=UsageStatus.UNKNOWN),
    }
    base.update(overrides)
    return InvocationResult(**base)


class TestCanonicalJson:
    def test_keys_are_sorted(self):
        assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_separators_carry_no_whitespace(self):
        assert canonical_json({"a": [1, 2]}) == '{"a":[1,2]}'

    def test_non_ascii_is_emitted_verbatim(self):
        assert canonical_json({"k": "é"}) == '{"k":"é"}'
        assert canonical_json({"k": "é"}).encode("utf-8") == b'{"k":"\xc3\xa9"}'

    def test_nesting_is_canonical_at_every_level(self):
        assert canonical_json({"z": {"b": 1, "a": 2}}) == '{"z":{"a":2,"b":1}}'

    def test_input_formatting_does_not_change_the_canonical_value(self):
        """Whitespace and key order in a source document are not part of the value."""
        pretty = json.loads('{\n  "b": 1,\n  "a": 2\n}')
        compact = json.loads('{"a":2,"b":1}')
        assert canonical_json(pretty) == canonical_json(compact)


class TestTheDigestInput:
    def test_plain_text_uses_the_normalized_text_bytes(self):
        form, data = select_digest_input(_result(text="hello"))
        assert form == "text"
        assert data == b"hello"

    def test_unicode_text_is_utf8(self):
        _, data = select_digest_input(_result(text="héllo"))
        assert data == "héllo".encode("utf-8")

    def test_structured_output_uses_canonical_json(self):
        form, data = select_digest_input(_result(text=None, structured_output={"b": 1, "a": 2}))
        assert form == "structured_output"
        assert data == b'{"a":2,"b":1}'

    def test_a_tool_call_response_uses_the_normalized_envelope(self):
        call = ToolCall(name="probe", arguments='{"value":"ok"}', id="call-1")
        form, data = select_digest_input(_result(text=None, tool_calls=(call,)))
        assert form == "tool_calls"
        assert json.loads(data) == {
            "tool_calls": [
                {"arguments": '{"value":"ok"}', "id": "call-1", "name": "probe"}
            ]
        }

    def test_tool_calls_take_precedence_over_text(self):
        """The calls are the part a consumer must act on, so they are the digest input."""
        call = ToolCall(name="probe", arguments="{}", id="call-1")
        form, _ = select_digest_input(_result(text="also some text", tool_calls=(call,)))
        assert form == "tool_calls"

    def test_an_empty_success_digests_the_empty_string(self):
        form, data = select_digest_input(_result(text=None))
        assert form == "text"
        assert data == b""


class TestTheReference:
    def test_the_form_is_the_frozen_one(self):
        reference = reference_for(_result())
        assert REFERENCE_RE.match(reference)
        assert reference == reference.lower()

    def test_it_is_a_sha256_of_the_selected_input(self):
        _, data = select_digest_input(_result(text="hello"))
        assert reference_for(_result(text="hello")) == (
            "sha256:" + hashlib.sha256(data).hexdigest()
        )

    def test_the_same_text_yields_the_same_reference(self):
        assert reference_for(_result(text="same")) == reference_for(_result(text="same"))

    def test_different_text_yields_a_different_reference(self):
        assert reference_for(_result(text="a")) != reference_for(_result(text="b"))

    def test_usage_and_latency_do_not_enter_the_digest(self):
        """The digest is over content, not over bookkeeping."""
        first = _result(usage=Usage(input_tokens=1, output_tokens=2))
        second = _result(usage=None)
        assert reference_for(first) == reference_for(second)

    def test_the_provider_envelope_does_not_enter_the_digest(self):
        """Two results that normalize alike agree, whatever the request ids were."""
        assert reference_for(_result(request_id="wb-1")) == reference_for(
            _result(request_id="wb-2")
        )

    def test_no_credential_or_context_value_is_hashed(self):
        """Nothing but the normalized content is an input, so nothing else can be."""
        _, data = select_digest_input(_result(text="hello"))
        assert b"MIMO_API_KEY" not in data
        assert b"sk-" not in data


class TestFailuresProduceNoReference:
    def test_an_error_result_is_refused(self):
        result = _result(status=InvocationStatus.ERROR, text=None)
        with pytest.raises(CodexInvocationError):
            reference_for(result)

    def test_a_blocked_result_is_refused(self):
        result = _result(status=InvocationStatus.BLOCKED, text=None)
        with pytest.raises(CodexInvocationError):
            reference_for(result)

    @pytest.mark.parametrize("status", [InvocationStatus.ERROR, InvocationStatus.BLOCKED])
    def test_no_digest_is_fabricated_on_failure(self, status):
        result = _result(status=status, text="partial output that is not an answer")
        with pytest.raises(CodexInvocationError) as excinfo:
            reference_for(result)
        assert not REFERENCE_RE.match(str(excinfo.value))

    def test_a_truncated_success_is_refused(self):
        result = _result(finish_state=FinishState.LENGTH)
        with pytest.raises(CodexInvocationError, match="truncated"):
            reference_for(result)

    def test_a_content_filtered_result_is_already_an_error(self):
        """AI-02 maps a policy stop onto ERROR, so it never reaches the digest."""
        result = _result(status=InvocationStatus.ERROR, finish_state=FinishState.CONTENT_FILTER)
        with pytest.raises(CodexInvocationError):
            reference_for(result)

    def test_the_refusal_carries_the_typed_result(self):
        result = _result(status=InvocationStatus.BLOCKED, text=None)
        with pytest.raises(CodexInvocationError) as excinfo:
            reference_for(result)
        assert excinfo.value.result is result
