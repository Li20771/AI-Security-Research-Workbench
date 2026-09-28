"""Invocation failure paths.

Contract §5.9, §5.10, §14, §15. Failures come back as typed results rather
than exceptions, and the taxonomy separations B1 froze still hold through the
invocation layer.
"""

from __future__ import annotations

import pytest

from providers.errors import ErrorClass, ErrorStage
from providers.invocation import (
    BlockCode,
    InvocationRequest,
    InvocationStatus,
    Message,
    MessageRole,
)
from providers.protocol import FinishState, TransportFailureKind, TransportResult


def _request(**overrides) -> InvocationRequest:
    base = {
        "model_ref": "deepseek/deepseek-flash",
        "messages": (Message(MessageRole.USER, "ping"),),
        "timeout_ms": 120_000,
    }
    base.update(overrides)
    return InvocationRequest(**base)


class TestCredentialPreconditions:
    def test_missing_credential_blocks_before_transport(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        result = invoker_factory(transport, environ={}).invoke(_request())

        assert result.status is InvocationStatus.BLOCKED
        assert result.error.error_class is ErrorClass.CREDENTIAL_MISSING
        assert result.error.stage is ErrorStage.RESOLVE
        assert result.error.is_precondition
        # A precondition reached no provider, so there is no finish reason.
        assert result.finish_state is FinishState.UNKNOWN
        assert result.blocked is None
        assert transport.requests == []

    def test_a_credential_precondition_uses_the_taxonomy_not_blocked(
        self, invoker_factory, fake_transport_factory
    ):
        """Credential classes are frozen taxonomy members, so `error` carries them."""
        result = invoker_factory(fake_transport_factory.success(), environ={}).invoke(
            _request()
        )
        assert result.error is not None
        assert result.blocked is None

    def test_unsupported_credential_scheme_blocks(
        self, invoker_factory, fake_transport_factory, all_profiles, model_profiles
    ):
        import dataclasses

        from providers.invocation import InvocationContext, Invoker
        from providers.profile import CredentialSpec
        from providers.transport import TransportSettings

        provider = dataclasses.replace(
            all_profiles["deepseek"],
            credential=CredentialSpec(ref="vault:secret/deepseek"),
        )
        transport = fake_transport_factory.success()
        invoker = Invoker(
            InvocationContext(
                providers={**all_profiles, "deepseek": provider},
                models=model_profiles,
                transport=transport,
                transport_settings_for=lambda _pid: TransportSettings(),
                environ={},
            )
        )

        result = invoker.invoke(_request())

        assert result.status is InvocationStatus.BLOCKED
        assert result.error.error_class is ErrorClass.CREDENTIAL_UNSUPPORTED
        assert result.finish_state is FinishState.UNKNOWN
        assert result.blocked is None
        assert transport.requests == []

    def test_missing_and_unsupported_stay_distinct(
        self, invoker_factory, fake_transport_factory
    ):
        result = invoker_factory(fake_transport_factory.success(), environ={}).invoke(
            _request()
        )
        assert result.error.error_class is not ErrorClass.CREDENTIAL_UNSUPPORTED

    def test_a_literal_credential_ref_is_a_config_defect_not_a_class(
        self, all_profiles, model_profiles, fake_transport_factory
    ):
        """§10.3: a literal is rejected, and is not MISSING or UNSUPPORTED.

        `CredentialSpec` refuses to hold a literal, so the only way this state
        can arise is a hand-edited or stale profile that bypassed the loader.
        The test reproduces that with a stand-in `credential` rather than
        mutating frozen fixtures.
        """
        import dataclasses
        from types import SimpleNamespace

        from providers.invocation import InvocationContext, Invoker
        from providers.transport import TransportSettings

        provider = dataclasses.replace(
            all_profiles["deepseek"],
            credential=SimpleNamespace(ref="sk-literal-value", kind="api_key"),
        )
        transport = fake_transport_factory.success()
        invoker = Invoker(
            InvocationContext(
                providers={**all_profiles, "deepseek": provider},
                models=model_profiles,
                transport=transport,
                transport_settings_for=lambda _pid: TransportSettings(),
                environ={},
            )
        )

        result = invoker.invoke(_request())

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.code is BlockCode.CREDENTIAL_CONFIG_DEFECT
        # Not an ErrorClass: a malformed reference is not a credential that is
        # missing or unsupported.
        assert result.error is None
        assert transport.requests == []
        assert "sk-literal-value" not in str(result.to_dict())


class TestLookupFailures:
    def test_unknown_model_blocks_before_transport(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        result = invoker_factory(transport).invoke(
            _request(model_ref="deepseek/not-a-real-model")
        )

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.code is BlockCode.UNKNOWN_MODEL
        assert transport.requests == []

    def test_unknown_provider_blocks_before_transport(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        result = invoker_factory(transport).invoke(
            _request(model_ref="openai-compatible/gpt")
        )

        assert result.status is InvocationStatus.BLOCKED
        assert result.blocked.code is BlockCode.UNKNOWN_PROVIDER
        assert transport.requests == []

    def test_no_other_model_is_substituted(
        self, invoker_factory, fake_transport_factory
    ):
        """No fallback: an unknown model is refused, never replaced."""
        transport = fake_transport_factory.success()
        result = invoker_factory(transport).invoke(
            _request(model_ref="deepseek/not-a-real-model")
        )

        assert result.model_id == "not-a-real-model"
        assert result.model_ref == "deepseek/not-a-real-model"
        assert transport.requests == []


class TestTransportFailures:
    def test_timeout(self, invoker_factory, fake_transport_factory):
        result = invoker_factory(fake_transport_factory.timeout()).invoke(_request())
        assert result.status is InvocationStatus.ERROR
        # A provider-layer failure DOES have a finish reason, unlike a refusal.
        assert result.finish_state is FinishState.ERROR
        assert result.error.error_class is ErrorClass.TIMEOUT
        assert not result.ok

    def test_a_provider_failure_is_not_blocked(
        self, invoker_factory, fake_transport_factory
    ):
        result = invoker_factory(fake_transport_factory.timeout()).invoke(_request())
        assert result.status is not InvocationStatus.BLOCKED
        assert result.blocked is None

    def test_transport_failure(self, invoker_factory, fake_transport_factory):
        result = invoker_factory(fake_transport_factory.transport_error()).invoke(_request())
        assert result.error.error_class is ErrorClass.TRANSPORT

    def test_cancelled(self, invoker_factory, fake_transport_factory):
        transport = fake_transport_factory(
            TransportResult.failed(
                TransportFailureKind.CANCELLED, ErrorStage.RECEIVE, "aborted"
            )
        )
        result = invoker_factory(transport).invoke(_request())
        assert result.error.error_class is ErrorClass.CANCELLED

    def test_a_failed_call_has_no_usage(self, invoker_factory, fake_transport_factory):
        result = invoker_factory(fake_transport_factory.timeout()).invoke(_request())
        assert result.usage is None


class TestHttpFailures:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (401, ErrorClass.AUTHENTICATION),
            (403, ErrorClass.AUTHENTICATION),
            (402, ErrorClass.QUOTA_EXHAUSTED),
            (429, ErrorClass.RATE_LIMIT),
            (400, ErrorClass.INVALID_REQUEST),
            (422, ErrorClass.INVALID_REQUEST),
            (413, ErrorClass.CONTEXT_OVERFLOW),
            (500, ErrorClass.SERVER),
            (503, ErrorClass.SERVER),
            (418, ErrorClass.UNKNOWN),
        ],
    )
    def test_http_status_classes_survive_normalization(
        self, status, expected, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.http_error(status)
        result = invoker_factory(transport).invoke(_request())

        assert result.status is InvocationStatus.ERROR
        assert result.error.error_class is expected
        assert result.error.http_status == status

    def test_rate_limit_and_quota_exhausted_stay_distinct(
        self, invoker_factory, fake_transport_factory
    ):
        throttled = invoker_factory(fake_transport_factory.http_error(429)).invoke(
            _request()
        )
        exhausted = invoker_factory(fake_transport_factory.http_error(402)).invoke(
            _request()
        )

        assert throttled.error.error_class is not exhausted.error.error_class
        assert throttled.error.retryable is True
        assert exhausted.error.retryable is False

    def test_context_overflow_is_refined_from_the_message(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.http_error(
            400, "maximum context length is 65536 tokens"
        )
        result = invoker_factory(transport).invoke(_request())
        assert result.error.error_class is ErrorClass.CONTEXT_OVERFLOW

    def test_content_filter_from_the_message(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.http_error(
            400, "your request was flagged by our content policy"
        )
        result = invoker_factory(transport).invoke(_request())
        assert result.error.error_class is ErrorClass.CONTENT_FILTER

    def test_protocol_error_from_a_malformed_body(
        self, invoker_factory, fake_transport_factory
    ):
        result = invoker_factory(fake_transport_factory.protocol_error()).invoke(_request())
        assert result.error.error_class is ErrorClass.PROTOCOL
        assert result.error.stage is ErrorStage.PARSE

    def test_protocol_and_invalid_request_stay_distinct(
        self, invoker_factory, fake_transport_factory
    ):
        ours = invoker_factory(fake_transport_factory.http_error(400)).invoke(_request())
        theirs = invoker_factory(fake_transport_factory.protocol_error()).invoke(_request())

        assert ours.error.error_class is ErrorClass.INVALID_REQUEST
        assert theirs.error.error_class is ErrorClass.PROTOCOL


class TestFailuresAreNeverSuccess:
    def test_status_is_the_only_success_signal(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        transport = fake_transport_factory.success(completion_payload())
        result = invoker_factory(transport).invoke(_request())
        assert result.ok

    def test_partial_text_on_an_error_is_not_success(
        self, invoker_factory, fake_transport_factory
    ):
        """A non-empty text on an ERROR result is partial output (§7.2, §14)."""
        result = invoker_factory(fake_transport_factory.timeout()).invoke(_request())
        assert not result.ok
        assert result.status is InvocationStatus.ERROR
        assert result.status is not InvocationStatus.SUCCESS

    def test_a_blocked_result_is_not_success(
        self, invoker_factory, fake_transport_factory
    ):
        result = invoker_factory(fake_transport_factory.success(), environ={}).invoke(
            _request()
        )
        assert not result.ok
        assert result.status is not InvocationStatus.SUCCESS

    def test_every_failure_carries_a_class_or_a_block_reason(
        self, invoker_factory, fake_transport_factory
    ):
        transports = [
            fake_transport_factory.timeout(),
            fake_transport_factory.transport_error(),
            fake_transport_factory.auth_error(),
            fake_transport_factory.protocol_error(),
            fake_transport_factory.http_error(500),
        ]
        for transport in transports:
            result = invoker_factory(transport).invoke(_request())
            assert not result.ok
            assert result.error is not None or result.blocked is not None


class TestErrorSanitization:
    def test_a_credential_in_an_error_body_is_redacted(
        self, invoker_factory, fake_transport_factory
    ):
        from tests.conftest import PLACEHOLDER_CREDENTIAL

        transport = fake_transport_factory.http_error(
            401, f"invalid key {PLACEHOLDER_CREDENTIAL}"
        )
        result = invoker_factory(transport).invoke(_request())

        assert PLACEHOLDER_CREDENTIAL not in repr(result.to_dict())
        assert PLACEHOLDER_CREDENTIAL not in (result.error.provider_message_sanitized or "")

    def test_an_error_result_does_not_leak_the_credential_in_its_repr(
        self, invoker_factory, fake_transport_factory
    ):
        from tests.conftest import PLACEHOLDER_CREDENTIAL

        result = invoker_factory(fake_transport_factory.timeout()).invoke(_request())
        assert PLACEHOLDER_CREDENTIAL not in repr(result)
        assert PLACEHOLDER_CREDENTIAL not in str(result.to_dict())


class TestNoRetry:
    def test_a_failure_is_not_retried(self, invoker_factory, fake_transport_factory):
        transport = fake_transport_factory.http_error(429)
        result = invoker_factory(transport).invoke(_request())

        assert result.attempts == 1
        assert len(transport.requests) == 1

    def test_no_backoff_or_second_attempt(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.timeout()
        invoker_factory(transport).invoke(_request())
        assert len(transport.requests) == 1
