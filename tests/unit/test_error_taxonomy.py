"""Error taxonomy.

Asserts against the table frozen in contract §5.10, transcribed here
independently rather than read back from the implementation, so the test
detects drift instead of restating it.
"""

from __future__ import annotations

import pytest

from providers.errors import (
    DEFAULT_RETRYABLE,
    PRECONDITION_CLASSES,
    ErrorClass,
    ErrorStage,
    ProviderError,
)


pytestmark = pytest.mark.layer1

#: Transcribed from contract §5.10. Order matches the document.
FROZEN_CLASSES: dict[str, bool] = {
    "CREDENTIAL_MISSING": False,
    "CREDENTIAL_UNSUPPORTED": False,
    "AUTHENTICATION": False,
    "RATE_LIMIT": True,
    "QUOTA_EXHAUSTED": False,
    "TIMEOUT": True,
    "TRANSPORT": True,
    "SERVER": True,
    "INVALID_REQUEST": False,
    "CONTEXT_OVERFLOW": False,
    "CONTENT_FILTER": False,
    "PROTOCOL": False,
    "CANCELLED": False,
    "UNKNOWN": False,
}

#: Transcribed from contract §5.9.
FROZEN_STAGES = {"resolve", "connect", "tls", "send", "receive", "parse", "validate"}


class TestEnumCoverage:
    def test_every_frozen_class_exists_with_the_frozen_name(self):
        assert {c.name for c in ErrorClass} == set(FROZEN_CLASSES)

    def test_every_frozen_stage_exists(self):
        assert {s.value for s in ErrorStage} == FROZEN_STAGES

    def test_retryable_defaults_match_the_frozen_table(self):
        for name, expected in FROZEN_CLASSES.items():
            assert DEFAULT_RETRYABLE[ErrorClass[name]] is expected, name

    def test_retryable_table_covers_every_class(self):
        assert set(DEFAULT_RETRYABLE) == set(ErrorClass)


class TestClassesAreNeverMerged:
    """Contract §5.10, D-6 and D-16."""

    def test_rate_limit_is_not_quota_exhausted(self):
        assert ErrorClass.RATE_LIMIT is not ErrorClass.QUOTA_EXHAUSTED
        assert ErrorClass.RATE_LIMIT != ErrorClass.QUOTA_EXHAUSTED
        # Transient and retryable vs terminal and needing a human.
        assert DEFAULT_RETRYABLE[ErrorClass.RATE_LIMIT] is True
        assert DEFAULT_RETRYABLE[ErrorClass.QUOTA_EXHAUSTED] is False

    def test_protocol_is_not_invalid_request(self):
        assert ErrorClass.PROTOCOL != ErrorClass.INVALID_REQUEST
        assert ErrorClass.PROTOCOL in ErrorClass
        assert ErrorClass.INVALID_REQUEST in ErrorClass

    def test_credential_missing_is_not_credential_unsupported(self):
        assert ErrorClass.CREDENTIAL_MISSING != ErrorClass.CREDENTIAL_UNSUPPORTED
        assert ErrorClass.CREDENTIAL_MISSING in ErrorClass
        assert ErrorClass.CREDENTIAL_UNSUPPORTED in ErrorClass

    def test_precondition_classes_are_exactly_the_two_credential_classes(self):
        assert PRECONDITION_CLASSES == {
            ErrorClass.CREDENTIAL_MISSING,
            ErrorClass.CREDENTIAL_UNSUPPORTED,
        }


class TestProviderError:
    def test_retryable_defaults_from_the_class(self):
        assert ProviderError(ErrorClass.RATE_LIMIT).retryable is True
        assert ProviderError(ErrorClass.AUTHENTICATION).retryable is False

    def test_retryable_can_be_overridden_per_call(self):
        assert ProviderError(ErrorClass.RATE_LIMIT, retryable_override=False).retryable is False

    def test_is_precondition_only_for_credential_classes(self):
        assert ProviderError(ErrorClass.CREDENTIAL_MISSING).is_precondition
        assert ProviderError(ErrorClass.CREDENTIAL_UNSUPPORTED).is_precondition
        assert not ProviderError(ErrorClass.AUTHENTICATION).is_precondition

    def test_serializes_to_the_frozen_shape(self):
        error = ProviderError(
            error_class=ErrorClass.TIMEOUT,
            stage=ErrorStage.RECEIVE,
            http_status=None,
        )
        payload = error.to_dict()
        assert set(payload) == {
            "class",
            "stage",
            "provider_code",
            "provider_message_sanitized",
            "retryable",
            "http_status",
        }
        # `class` is a Python keyword, so the attribute is renamed on output.
        # The wire shape is a contract and keeps the frozen key.
        assert payload["class"] == "TIMEOUT"
        assert payload["stage"] == "receive"
        assert payload["retryable"] is True

    def test_errors_are_immutable(self):
        error = ProviderError(ErrorClass.SERVER)
        with pytest.raises(Exception):
            error.error_class = ErrorClass.UNKNOWN  # type: ignore[misc]
