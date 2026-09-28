"""Runtime provider config and the required example revision.

Contract §16.1 lists seven ways the previous example contradicted the frozen
contract. This module asserts each is fixed, and that validation is the
mechanism that keeps it fixed.
"""

from __future__ import annotations

import textwrap

import pytest
import yaml

from providers.config import (
    CONFIG_VERSION,
    ProviderConfigError,
    example_config_path,
    load_provider_config,
)
from providers.validate import (
    AI02_SCOPE_PROVIDERS,
    RESERVED_PROVIDERS,
    main,
    validate_all,
    validate_example_config,
)


@pytest.fixture
def example_config():
    return load_provider_config(example_config_path())


@pytest.fixture
def raw_example() -> dict:
    return yaml.safe_load(example_config_path().read_text(encoding="utf-8"))


class TestExampleConfigShape:
    def test_loads_and_declares_the_frozen_version(self, example_config):
        assert example_config.version == CONFIG_VERSION

    def test_declares_both_in_scope_providers(self, example_config):
        assert AI02_SCOPE_PROVIDERS <= set(example_config.providers)

    def test_everything_is_disabled_by_default(self, example_config):
        """Nothing is verified yet, so nothing is enabled."""
        assert example_config.enabled_providers == ()

    def test_reserved_provider_is_present_disabled_and_marked(
        self, example_config
    ):
        entry = example_config.providers["openai-compatible"]
        assert entry.reserved is True
        assert entry.enabled is False
        assert entry.reserved_for == "AI-09"
        assert entry.note

    def test_config_selects_but_does_not_define_capability(self, raw_example):
        """Identity belongs to the profile, not the runtime config (D-1)."""
        for provider_id, entry in raw_example["providers"].items():
            assert "display_name" not in entry, provider_id
            assert "capabilities" not in entry, provider_id


class TestPreviousContradictionsAreFixed:
    """The seven gaps recorded in contract §16.1."""

    def test_no_scalar_model_field(self, raw_example):
        """Gap 1: a single scalar `model:` implied a default model."""
        for provider_id, entry in raw_example["providers"].items():
            assert "model" not in entry, provider_id

    def test_mimo_declares_both_models(self, example_config):
        """Gap 2: MiMo's model was an empty string."""
        models = example_config.providers["mimo"].models
        assert {str(m) for m in models} == {"mimo/mimo-v2.6-pro", "mimo/mimo-v2.6-flash"}

    def test_protocol_is_declared(self, example_config):
        """Gap 3."""
        for provider_id in AI02_SCOPE_PROVIDERS:
            protocol = example_config.providers[provider_id].protocol
            assert protocol is not None, provider_id
            assert protocol.family == "openai_compatible_chat", provider_id

    def test_endpoint_is_declared(self, example_config):
        """Gap 4."""
        for provider_id in AI02_SCOPE_PROVIDERS:
            endpoint = example_config.providers[provider_id].endpoint
            assert endpoint is not None, provider_id
            assert endpoint.source == "declared", provider_id
            assert endpoint.verified_at is None, provider_id

    def test_transport_is_declared_with_zero_retries(self, example_config):
        """Gap 5."""
        for provider_id in AI02_SCOPE_PROVIDERS:
            transport = example_config.providers[provider_id].transport
            assert transport is not None, provider_id
            assert transport.max_retries == 0, provider_id
            assert transport.verify_tls is True, provider_id

    def test_credentials_use_the_reference_grammar(self, example_config):
        """Gap 6: a bare `api_key_env:` name became `credential.ref`."""
        for provider_id in AI02_SCOPE_PROVIDERS:
            credential = example_config.providers[provider_id].credential
            assert credential is not None, provider_id
            assert credential.ref.startswith("env:"), provider_id
        for provider_id, entry in example_config.providers.items():
            assert not hasattr(entry, "api_key_env"), provider_id

    def test_reserved_provider_is_still_present(self, example_config):
        """Gap 7: it is kept, not deleted, and marked out of AI-02 scope."""
        assert RESERVED_PROVIDERS <= set(example_config.providers)


class TestConfigCredentialSafety:
    def test_no_credential_values_anywhere(self, raw_example):
        text = example_config_path().read_text(encoding="utf-8")
        for marker in ("sk-", "Bearer ", "api_key:", "secret:"):
            assert marker not in text, marker

    def test_literal_credential_in_config_is_rejected(self, tmp_path):
        path = tmp_path / "providers.yaml"
        path.write_text(
            textwrap.dedent(
                """
                version: 1
                providers:
                  deepseek:
                    enabled: false
                    credential:
                      ref: sk-a-real-looking-key
                """
            ),
            encoding="utf-8",
        )
        with pytest.raises(ProviderConfigError):
            load_provider_config(path)

    def test_reserved_provider_cannot_be_enabled(self, tmp_path):
        path = tmp_path / "providers.yaml"
        path.write_text(
            textwrap.dedent(
                """
                version: 1
                providers:
                  openai-compatible:
                    enabled: true
                    reserved: true
                """
            ),
            encoding="utf-8",
        )
        with pytest.raises(ProviderConfigError, match="reserved"):
            load_provider_config(path)


class TestConfigValidation:
    def test_example_config_has_no_problems(self):
        assert validate_example_config() == []

    def test_full_validation_passes(self):
        assert validate_all() == []

    def test_cli_exits_zero(self, capsys):
        assert main([]) == 0
        assert "PASS" in capsys.readouterr().out

    def test_unknown_config_version_is_rejected(self, tmp_path):
        path = tmp_path / "providers.yaml"
        path.write_text("version: 99\nproviders: {}\n", encoding="utf-8")
        with pytest.raises(ProviderConfigError):
            load_provider_config(path)

    def test_unknown_entry_field_is_rejected(self, tmp_path):
        path = tmp_path / "providers.yaml"
        path.write_text(
            textwrap.dedent(
                """
                version: 1
                providers:
                  deepseek:
                    enabled: false
                    mystery: true
                """
            ),
            encoding="utf-8",
        )
        with pytest.raises(ProviderConfigError, match="unknown field"):
            load_provider_config(path)
