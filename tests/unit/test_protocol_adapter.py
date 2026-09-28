"""Protocol adapter behaviour, driven by a fake transport.

Every path is exercised through `FakeTransport`. No test opens a connection:
AI-02-B1 ships no network transport, so none can be reached.
"""

from __future__ import annotations

import pytest

from providers.errors import ErrorClass, ErrorStage
from providers.protocol import (
    FinishState,
    ProviderCall,
    UnsupportedProtocolFamily,
    adapter_for,
    registered_families,
)
from providers.protocol.base import TransportFailureKind, TransportResult

FAMILY = "openai_compatible_chat"


def _call(profile, body: str, credential: str = "placeholder-credential"):
    adapter = adapter_for(profile.protocol.family)
    request = adapter.build_request(
        profile, profile.models[0], credential=credential, body=body
    )
    return ProviderCall(profile=profile, model_ref=profile.models[0], request=request)


class TestAdapterRegistry:
    def test_only_the_shared_family_is_registered(self):
        assert registered_families() == (FAMILY,)

    def test_both_providers_use_the_same_adapter(self, all_profiles):
        """D-2: shared adapter, separate profiles."""
        adapters = {
            id(adapter_for(p.protocol.family)) for p in all_profiles.values()
        }
        assert len(adapters) == 1

    def test_unknown_family_raises_rather_than_falling_back(self):
        with pytest.raises(UnsupportedProtocolFamily):
            adapter_for("not_a_real_family")


class TestSuccessPath:
    def test_successful_call_returns_an_envelope_with_attribution(
        self, deepseek_profile, fake_transport_factory, body
    ):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.success()
        )
        assert response.ok
        assert response.error is None
        assert response.provider_id == "deepseek"
        assert response.model_id == "deepseek-flash"

    def test_envelope_carries_no_content_in_b1(
        self, deepseek_profile, fake_transport_factory, body
    ):
        """Field mapping is AI-02-B3. B1 validates shape and attributes only."""
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.success()
        )
        assert response.text is None
        assert response.usage is None
        assert response.finish_state is FinishState.UNKNOWN

    def test_request_is_recorded_by_the_transport(
        self, deepseek_profile, fake_transport_factory, body
    ):
        transport = fake_transport_factory.success()
        adapter_for(FAMILY).send(_call(deepseek_profile, body), transport)
        assert len(transport.requests) == 1
        assert transport.requests[0].url == deepseek_profile.endpoint.effective_url

    def test_both_providers_reach_their_own_endpoint(
        self, all_profiles, fake_transport_factory, body
    ):
        adapter = adapter_for(FAMILY)
        for provider_id, profile in all_profiles.items():
            transport = fake_transport_factory.success()
            adapter.send(_call(profile, body), transport)
            assert transport.requests[0].url == profile.endpoint.effective_url, provider_id


class TestTransportFailurePath:
    def test_timeout_is_classified_as_timeout(
        self, deepseek_profile, fake_transport_factory, body
    ):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.timeout()
        )
        assert not response.ok
        assert response.error.error_class is ErrorClass.TIMEOUT
        assert response.error.stage is ErrorStage.RECEIVE
        assert response.finish_state is FinishState.ERROR

    def test_connection_failure_is_classified_as_transport(
        self, deepseek_profile, fake_transport_factory, body
    ):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.transport_error()
        )
        assert response.error.error_class is ErrorClass.TRANSPORT
        assert response.error.stage is ErrorStage.CONNECT

    @pytest.mark.parametrize(
        "kind", list(TransportFailureKind)
    )
    def test_every_failure_kind_maps_to_a_class(
        self, deepseek_profile, fake_transport_factory, body, kind
    ):
        adapter = adapter_for(FAMILY)
        result = TransportResult.failed(kind, ErrorStage.RECEIVE, "boom")
        response = adapter.send(_call(deepseek_profile, body), fake_transport_factory(result))
        assert response.error is not None
        assert response.error.error_class in ErrorClass


class TestHttpErrorPath:
    def test_auth_error_is_classified(self, deepseek_profile, fake_transport_factory, body):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.auth_error()
        )
        assert response.error.error_class is ErrorClass.AUTHENTICATION
        assert response.error.http_status == 401

    def test_protocol_violation_is_classified_as_protocol(
        self, deepseek_profile, fake_transport_factory, body
    ):
        """A 200 whose body is not an object means the provider broke the contract."""
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.protocol_error()
        )
        assert response.error.error_class is ErrorClass.PROTOCOL
        assert response.error.stage is ErrorStage.PARSE

    @pytest.mark.parametrize(
        "status,expected",
        [
            (401, ErrorClass.AUTHENTICATION),
            (403, ErrorClass.AUTHENTICATION),
            (402, ErrorClass.QUOTA_EXHAUSTED),
            (404, ErrorClass.INVALID_REQUEST),
            (408, ErrorClass.TIMEOUT),
            (409, ErrorClass.INVALID_REQUEST),
            (413, ErrorClass.CONTEXT_OVERFLOW),
            (422, ErrorClass.INVALID_REQUEST),
            (429, ErrorClass.RATE_LIMIT),
            (500, ErrorClass.SERVER),
            (502, ErrorClass.SERVER),
            (503, ErrorClass.SERVER),
            (418, ErrorClass.UNKNOWN),
        ],
    )
    def test_status_classification(
        self, deepseek_profile, fake_transport_factory, body, status, expected
    ):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.http_error(status)
        )
        assert response.error.error_class is expected

    def test_rate_limit_and_quota_exhausted_stay_distinct(
        self, deepseek_profile, fake_transport_factory, body
    ):
        adapter = adapter_for(FAMILY)
        throttled = adapter.send(
            _call(deepseek_profile, body), fake_transport_factory.http_error(429)
        )
        exhausted = adapter.send(
            _call(deepseek_profile, body), fake_transport_factory.http_error(402)
        )
        assert throttled.error.error_class is ErrorClass.RATE_LIMIT
        assert exhausted.error.error_class is ErrorClass.QUOTA_EXHAUSTED
        assert throttled.error.error_class is not exhausted.error.error_class
        assert throttled.error.retryable is True
        assert exhausted.error.retryable is False

    def test_protocol_and_invalid_request_stay_distinct(
        self, deepseek_profile, fake_transport_factory, body
    ):
        adapter = adapter_for(FAMILY)
        ours = adapter.send(
            _call(deepseek_profile, body), fake_transport_factory.http_error(400)
        )
        theirs = adapter.send(
            _call(deepseek_profile, body), fake_transport_factory.protocol_error()
        )
        assert ours.error.error_class is ErrorClass.INVALID_REQUEST
        assert theirs.error.error_class is ErrorClass.PROTOCOL

    @pytest.mark.parametrize(
        "status,message,expected",
        [
            (400, "maximum context length is 65536 tokens", ErrorClass.CONTEXT_OVERFLOW),
            (400, "This model's maximum context length is 8192", ErrorClass.CONTEXT_OVERFLOW),
            (400, "prompt is too long", ErrorClass.CONTEXT_OVERFLOW),
            (413, "too many tokens in request", ErrorClass.CONTEXT_OVERFLOW),
            (400, "your request was flagged by our content policy", ErrorClass.CONTENT_FILTER),
            (400, "moderation flagged this input", ErrorClass.CONTENT_FILTER),
        ],
    )
    def test_message_refinement(
        self, deepseek_profile, fake_transport_factory, body, status, message, expected
    ):
        transport = fake_transport_factory.http_error(status, message)
        response = adapter_for(FAMILY).send(_call(deepseek_profile, body), transport)
        assert response.error.error_class is expected

    def test_refinement_does_not_override_a_clear_status(
        self, deepseek_profile, fake_transport_factory, body
    ):
        """A 429 mentioning tokens is still a rate limit, not an overflow."""
        transport = fake_transport_factory.http_error(429, "token rate limit exceeded")
        response = adapter_for(FAMILY).send(_call(deepseek_profile, body), transport)
        assert response.error.error_class is ErrorClass.RATE_LIMIT


class TestFailureNeverBecomesSuccess:
    def test_error_response_carries_no_text(
        self, deepseek_profile, fake_transport_factory, body
    ):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.auth_error()
        )
        assert response.text is None
        assert not response.ok

    def test_send_never_raises(self, deepseek_profile, fake_transport_factory, body):
        """Failures are returned on the envelope, never raised (§5.9)."""
        adapter = adapter_for(FAMILY)
        for transport in (
            fake_transport_factory.timeout(),
            fake_transport_factory.transport_error(),
            fake_transport_factory.auth_error(),
            fake_transport_factory.protocol_error(),
            fake_transport_factory.http_error(500),
        ):
            response = adapter.send(_call(deepseek_profile, body), transport)
            assert response.error is not None

    def test_error_envelope_serializes_without_content(
        self, deepseek_profile, fake_transport_factory, body
    ):
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, body), fake_transport_factory.timeout()
        )
        payload = response.to_dict()
        assert payload["error"] is not None
        assert payload["text"] is None
        assert payload["finish_state"] == "ERROR"
