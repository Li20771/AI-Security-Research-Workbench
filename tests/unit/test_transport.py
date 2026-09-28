"""Transport settings.

Contract §5.11 / D-12: a timeout is always explicit, there is no unbounded or
default-infinite request, and `max_retries` defaults to 0 because AI-02
implements no retry loop.
"""

from __future__ import annotations

import math

import pytest

from providers.transport import (
    AI02_MAX_RETRIES,
    DEFAULT_TIMEOUT_CONNECT_MS,
    DEFAULT_TIMEOUT_TOTAL_MS,
    TransportConfigError,
    TransportSettings,
)


class TestDefaults:
    def test_frozen_defaults(self):
        settings = TransportSettings()
        assert settings.timeout_connect_ms == 10_000
        assert settings.timeout_total_ms == 120_000
        assert settings.max_retries == 0
        assert settings.verify_tls is True

    def test_module_constants_match_the_defaults(self):
        assert DEFAULT_TIMEOUT_CONNECT_MS == 10_000
        assert DEFAULT_TIMEOUT_TOTAL_MS == 120_000
        assert AI02_MAX_RETRIES == 0

    def test_profiles_use_the_frozen_defaults(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            transport = profile.transport
            assert transport.max_retries == 0, provider_id
            assert transport.verify_tls is True, provider_id
            assert transport.timeout_connect_ms == 10_000, provider_id
            assert transport.timeout_total_ms == 120_000, provider_id


class TestTimeoutRejection:
    @pytest.mark.parametrize("value", [0, -1, -10_000])
    def test_non_positive_timeouts_are_rejected(self, value):
        """A non-positive timeout is not an unbounded timeout; it is invalid."""
        with pytest.raises(TransportConfigError):
            TransportSettings(timeout_connect_ms=value)

    @pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
    def test_non_finite_timeouts_are_rejected(self, value):
        with pytest.raises(TransportConfigError):
            TransportSettings(timeout_total_ms=value)

    @pytest.mark.parametrize("value", [None, "10000", True, False, [10_000], {}])
    def test_non_numeric_timeouts_are_rejected(self, value):
        with pytest.raises(TransportConfigError):
            TransportSettings(timeout_connect_ms=value)

    def test_total_shorter_than_connect_is_rejected(self):
        with pytest.raises(TransportConfigError):
            TransportSettings(timeout_connect_ms=30_000, timeout_total_ms=10_000)

    def test_total_equal_to_connect_is_allowed(self):
        settings = TransportSettings(timeout_connect_ms=5_000, timeout_total_ms=5_000)
        assert settings.timeout_total_ms == settings.timeout_connect_ms


class TestRetryRejection:
    @pytest.mark.parametrize("value", [-1, -5])
    def test_negative_max_retries_is_rejected(self, value):
        with pytest.raises(TransportConfigError):
            TransportSettings(max_retries=value)

    def test_zero_max_retries_is_the_default_and_is_allowed(self):
        assert TransportSettings(max_retries=0).max_retries == 0

    @pytest.mark.parametrize("value", [True, False, "3", 1.5, None])
    def test_non_integer_max_retries_is_rejected(self, value):
        with pytest.raises(TransportConfigError):
            TransportSettings(max_retries=value)

    def test_positive_max_retries_is_representable_but_inert(self):
        """The field is frozen for AI-13, but AI-02 runs no retry loop."""
        settings = TransportSettings(max_retries=3)
        assert settings.retries_are_inert is True

    def test_default_reports_retries_as_not_inert(self):
        assert TransportSettings().retries_are_inert is False


class TestTlsVerification:
    def test_verify_tls_defaults_true(self):
        assert TransportSettings().verify_tls is True

    @pytest.mark.parametrize("value", ["true", 1, 0, None])
    def test_verify_tls_must_be_a_bool(self, value):
        with pytest.raises(TransportConfigError):
            TransportSettings(verify_tls=value)

    def test_disabling_is_representable_but_flagged_by_validation(self):
        """Permitted only with explicit human approval (§5.11); the phase's
        validator reports it, and the shipped profiles never disable it."""
        assert TransportSettings(verify_tls=False).verify_tls is False


class TestFromMapping:
    def test_none_yields_defaults(self):
        assert TransportSettings.from_mapping(None) == TransportSettings()

    def test_partial_mapping_fills_defaults(self):
        settings = TransportSettings.from_mapping({"max_retries": 0})
        assert settings.timeout_total_ms == DEFAULT_TIMEOUT_TOTAL_MS

    def test_unknown_keys_are_rejected(self):
        with pytest.raises(TransportConfigError):
            TransportSettings.from_mapping({"timeout_ms": 1000})

    def test_non_mapping_is_rejected(self):
        with pytest.raises(TransportConfigError):
            TransportSettings.from_mapping([1, 2, 3])


class TestSerialization:
    def test_round_trips_through_mapping(self):
        original = TransportSettings(timeout_connect_ms=1_000, timeout_total_ms=2_000)
        assert TransportSettings.from_mapping(original.to_dict()) == original
