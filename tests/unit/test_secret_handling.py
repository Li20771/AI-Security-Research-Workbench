"""Secret boundary.

Contract §10. A credential value must not reach logs, reprs, exception
messages, serialized results, or Evidence. Every value used here is a
synthetic placeholder; no test reads a real credential.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from providers.credential import CredentialRef, SecretValue, resolve_ref
from providers.errors import ErrorClass, ProviderError
from providers.protocol import adapter_for
from providers.redaction import REDACTED, redact


pytestmark = pytest.mark.layer2

PLACEHOLDER = "sk-test-placeholder-not-a-real-key-000000"
ENV_NAME = "WORKBENCH_TEST_CREDENTIAL"


@pytest.fixture
def secret() -> SecretValue:
    return SecretValue(PLACEHOLDER)


class TestSecretValue:
    def test_repr_does_not_leak(self, secret):
        assert PLACEHOLDER not in repr(secret)
        assert REDACTED in repr(secret) or "***" in repr(secret)

    def test_str_does_not_leak(self, secret):
        assert PLACEHOLDER not in str(secret)
        assert str(secret) == "***"

    def test_fstring_does_not_leak(self, secret):
        assert PLACEHOLDER not in f"{secret}"

    def test_reveal_returns_the_value(self, secret):
        assert secret.reveal() == PLACEHOLDER

    def test_dataclass_repr_does_not_leak(self, secret):
        """A SecretValue inside a dataclass must not leak via the dataclass."""

        @dataclass(frozen=True)
        class Holder:
            label: str
            credential: SecretValue

        holder = Holder(label="deepseek", credential=secret)
        assert PLACEHOLDER not in repr(holder)
        assert PLACEHOLDER not in str(holder)

    def test_matches_compares_values(self, secret):
        assert secret.matches(SecretValue(PLACEHOLDER))
        assert not secret.matches(SecretValue("different"))

    def test_empty_value_is_rejected(self):
        with pytest.raises(Exception):
            SecretValue("")

    def test_truthiness_is_true(self, secret):
        assert bool(secret) is True


class TestRedaction:
    @pytest.mark.parametrize(
        "text",
        [
            f"invalid key {PLACEHOLDER}",
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345",
            "api_key=abcdefghijklmnopqrstuvwxyz012345",
            "token: abcdefghijklmnopqrstuvwxyz012345",
            "password=abcdefghijklmnopqrstuvwxyz012345",
            "ghp_abcdefghijklmnopqrstuvwxyz012345",
        ],
    )
    def test_credential_shaped_text_is_redacted(self, text):
        result = redact(text)
        assert "abcdefghijklmnopqrstuvwxyz012345" not in result
        assert REDACTED in result

    def test_exact_value_is_redacted_even_without_a_recognisable_shape(self, secret):
        text = f"provider rejected credential {PLACEHOLDER} for model x"
        result = redact(text, extra_secrets=[secret.reveal()])
        assert PLACEHOLDER not in result

    def test_none_passes_through(self):
        assert redact(None) is None

    def test_ordinary_prose_is_preserved(self):
        text = "connect deadline exceeded after 10000 ms"
        assert redact(text) == text


class TestTransportRequestRedaction:
    """Transport settings come from runtime config, not the profile (§5.11)."""

    def _request(self, profile, transport_settings, body: str):
        adapter = adapter_for(profile.protocol.family)
        return adapter.build_request(
            profile,
            profile.models[0],
            credential=PLACEHOLDER,
            body=body,
            transport_settings=transport_settings,
        )

    def test_repr_does_not_leak_the_credential(
        self, deepseek_profile, runtime_transport
    ):
        request = self._request(
            deepseek_profile, runtime_transport, json.dumps({"model": "deepseek-flash"})
        )
        assert PLACEHOLDER not in repr(request)
        assert PLACEHOLDER not in str(request)

    def test_redacted_headers_mask_the_authorization_header(
        self, deepseek_profile, runtime_transport
    ):
        request = self._request(deepseek_profile, runtime_transport, "{}")
        headers = request.redacted_headers()
        assert headers["Authorization"] == REDACTED
        # The header name survives, so the request is still diagnosable.
        assert "Authorization" in headers

    def test_body_is_not_rendered(self, deepseek_profile, runtime_transport):
        request = self._request(
            deepseek_profile, runtime_transport, '{"secret":"sensitive"}'
        )
        assert "sensitive" not in repr(request)

    def test_credential_never_appears_in_the_url(
        self, deepseek_profile, runtime_transport
    ):
        request = self._request(deepseek_profile, runtime_transport, "{}")
        assert PLACEHOLDER not in request.url
        assert "@" not in request.url

    def test_runtime_transport_reaches_the_request(
        self, deepseek_profile, runtime_transport
    ):
        """The settings the caller supplies are the ones that get applied."""
        from providers.transport import TransportSettings

        settings = TransportSettings(timeout_connect_ms=1_234, timeout_total_ms=5_678)
        request = self._request(deepseek_profile, settings, "{}")
        assert request.timeout_connect_ms == 1_234
        assert request.timeout_total_ms == 5_678


class TestProviderErrorSanitization:
    def test_error_message_is_sanitized_on_output(self):
        error = ProviderError(
            error_class=ErrorClass.AUTHENTICATION,
            provider_message_sanitized=redact(f"bad key {PLACEHOLDER}"),
            http_status=401,
        )
        payload = error.to_dict()
        assert PLACEHOLDER not in json.dumps(payload)
        assert PLACEHOLDER not in repr(error)

    def test_transport_failure_message_is_sanitized_at_capture(self):
        from providers.protocol import TransportFailureKind, TransportResult
        from providers.errors import ErrorStage

        result = TransportResult.failed(
            TransportFailureKind.TRANSPORT,
            ErrorStage.CONNECT,
            f"connection refused while sending {PLACEHOLDER}",
        )
        assert PLACEHOLDER not in (result.message or "")


class TestNoCredentialRequired:
    def test_profiles_load_with_credentials_unset(self, monkeypatch):
        """CI has no API keys. Loading must not require one."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("MIMO_API_KEY", raising=False)

        from providers.registry import load_provider

        assert load_provider("deepseek").credential.parsed.is_supported
        assert load_provider("mimo").credential.parsed.is_supported

    def test_resolution_reports_missing_without_raising_a_leak(self, monkeypatch):
        monkeypatch.delenv(ENV_NAME, raising=False)
        from providers.credential import CredentialError

        with pytest.raises(CredentialError) as excinfo:
            resolve_ref(f"env:{ENV_NAME}")
        assert excinfo.value.error_class is ErrorClass.CREDENTIAL_MISSING
        assert ENV_NAME in str(excinfo.value)

    def test_resolved_value_does_not_appear_in_any_serialized_result(
        self, deepseek_profile, monkeypatch
    ):
        monkeypatch.setenv(ENV_NAME, PLACEHOLDER)
        secret = resolve_ref(f"env:{ENV_NAME}")
        assert secret.reveal() == PLACEHOLDER
        assert PLACEHOLDER not in json.dumps({"credential": str(secret)})
        assert PLACEHOLDER not in repr(CredentialRef.parse(f"env:{ENV_NAME}"))
