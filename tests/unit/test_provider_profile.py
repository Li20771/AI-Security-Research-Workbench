"""Provider profile schema and registry loading.

Contract §5.1 - §5.7, D-1. A profile is reviewable repository data; the loader
enforces its shape and refuses anything it cannot represent.
"""

from __future__ import annotations

import textwrap

import pytest

from providers.credential import CredentialConfigError
from providers.profile import (
    CredentialSpec,
    Endpoint,
    ModelRef,
    ProfileError,
    Protocol,
    ProviderProfile,
)
from providers.registry import (
    RegistryError,
    load_provider_profile,
    provider_profile_path,
)
from providers.transport import TransportSettings


def _write(path, body: str):
    """Write a profile body verbatim.

    No dedent here: callers append fields at column 0, and dedenting the
    combined text would leave the template indented while the appended lines
    were not, which is invalid YAML at document root.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


#: Dedented once, at definition. `str.format` fills the two placeholders.
MINIMAL_PROFILE = textwrap.dedent(
    """
    provider_id: {provider_id}
    display_name: {display_name}
    protocol:
      family: openai_compatible_chat
      version: v1
    endpoint:
      base_url: https://example.test
      path_template: /chat/completions
      source: declared
      verified_at: null
      evidence_ref: null
    credential:
      ref: env:EXAMPLE_API_KEY
      kind: api_key
      required: true
    models:
      - {provider_id}/example-model
    transport:
      timeout_connect_ms: 10000
      timeout_total_ms: 120000
      max_retries: 0
      verify_tls: true
    """
).lstrip("\n")


class TestProviderIdValidation:
    @pytest.mark.parametrize(
        "value", ["deepseek", "mimo", "openai_compatible", "openai-compatible", "a1"]
    )
    def test_valid_identifiers(self, value):
        ProviderProfile(
            provider_id=value,
            display_name="X",
            protocol=Protocol("openai_compatible_chat", "v1"),
            endpoint=Endpoint("https://example.test", "/chat"),
            credential=CredentialSpec("env:EXAMPLE_API_KEY"),
        )

    @pytest.mark.parametrize(
        "value", ["DeepSeek", "DEEPSEEK", "-leading", "trailing-", "dou--ble", "has space", "", "1leading"]
    )
    def test_invalid_identifiers_are_rejected(self, value):
        with pytest.raises(ProfileError):
            ProviderProfile(
                provider_id=value,
                display_name="X",
                protocol=Protocol("openai_compatible_chat", "v1"),
                endpoint=Endpoint("https://example.test", "/chat"),
                credential=CredentialSpec("env:EXAMPLE_API_KEY"),
            )

    def test_display_name_must_not_be_empty(self):
        with pytest.raises(ProfileError):
            ProviderProfile(
                provider_id="example",
                display_name="   ",
                protocol=Protocol("openai_compatible_chat", "v1"),
                endpoint=Endpoint("https://example.test", "/chat"),
                credential=CredentialSpec("env:EXAMPLE_API_KEY"),
            )


class TestModelRef:
    @pytest.mark.parametrize(
        "raw", ["deepseek/deepseek-flash", "mimo/mimo-v2.6-pro", "a/b"]
    )
    def test_valid_refs(self, raw):
        assert str(ModelRef.parse(raw)) == raw

    @pytest.mark.parametrize(
        "raw", ["", "no-separator", "a/b/c", "/model", "provider/", "a /b", "a/ b", 42, None]
    )
    def test_invalid_refs_are_rejected(self, raw):
        with pytest.raises(ProfileError):
            ModelRef.parse(raw)

    def test_ref_must_match_its_profile_provider(self):
        with pytest.raises(ProfileError):
            ProviderProfile(
                provider_id="deepseek",
                display_name="DeepSeek",
                protocol=Protocol("openai_compatible_chat", "v1"),
                endpoint=Endpoint("https://example.test", "/chat"),
                credential=CredentialSpec("env:EXAMPLE_API_KEY"),
                models=(ModelRef.parse("mimo/mimo-v2.6-pro"),),
            )


class TestCredentialSpec:
    def test_literal_value_cannot_be_constructed(self):
        """The type cannot represent a credential value at all (§10.3)."""
        with pytest.raises(CredentialConfigError):
            CredentialSpec("sk-literal-credential-value")

    def test_reserved_scheme_is_representable(self):
        spec = CredentialSpec("file:/etc/key")
        assert not spec.parsed.is_supported

    def test_required_must_be_a_bool(self):
        with pytest.raises(ProfileError):
            CredentialSpec("env:EXAMPLE_API_KEY", required="yes")


class TestRegistryLoading:
    def test_loads_a_minimal_profile(self, tmp_path):
        path = _write(
            tmp_path / "example" / "provider.yaml",
            MINIMAL_PROFILE.format(provider_id="example", display_name="Example"),
        )
        profile = load_provider_profile(path)
        assert profile.provider_id == "example"
        assert profile.transport == TransportSettings()

    def test_missing_file_is_reported(self, tmp_path):
        with pytest.raises(RegistryError):
            load_provider_profile(tmp_path / "absent" / "provider.yaml")

    def test_unknown_field_is_rejected(self, tmp_path):
        body = MINIMAL_PROFILE.format(
            provider_id="example", display_name="Example"
        ) + "\ncapabilities:\n  tool_calling: true\n"
        path = _write(tmp_path / "example" / "provider.yaml", body)
        with pytest.raises(RegistryError, match="unknown field"):
            load_provider_profile(path)

    def test_missing_field_is_rejected(self, tmp_path):
        path = _write(
            tmp_path / "example" / "provider.yaml",
            "provider_id: example\ndisplay_name: Example\n",
        )
        with pytest.raises(RegistryError, match="missing field"):
            load_provider_profile(path)

    def test_directory_must_match_provider_id(self, tmp_path):
        path = _write(
            tmp_path / "wrong-name" / "provider.yaml",
            MINIMAL_PROFILE.format(provider_id="example", display_name="Example"),
        )
        with pytest.raises(RegistryError, match="does not match"):
            load_provider_profile(path)

    def test_invalid_yaml_is_reported(self, tmp_path):
        path = _write(tmp_path / "example" / "provider.yaml", "provider_id: [unclosed\n")
        with pytest.raises(RegistryError):
            load_provider_profile(path)

    def test_non_mapping_document_is_rejected(self, tmp_path):
        path = _write(tmp_path / "example" / "provider.yaml", "- just\n- a\n- list\n")
        with pytest.raises(RegistryError):
            load_provider_profile(path)

    def test_literal_credential_in_a_profile_is_rejected(self, tmp_path):
        body = MINIMAL_PROFILE.format(
            provider_id="example", display_name="Example"
        ).replace("env:EXAMPLE_API_KEY", "sk-a-real-looking-key")
        path = _write(tmp_path / "example" / "provider.yaml", body)
        with pytest.raises(RegistryError):
            load_provider_profile(path)


class TestB1ScopeDiscipline:
    def test_profiles_carry_no_capability_metadata(self, all_profiles):
        """Capability metadata is AI-02-B2's deliverable, not B1's."""
        for provider_id, profile in all_profiles.items():
            payload = profile.to_dict()
            for forbidden in (
                "capabilities",
                "tool_calling",
                "structured_output",
                "streaming",
                "reasoning",
                "modality",
                "context_limit",
                "max_output",
            ):
                assert forbidden not in payload, f"{provider_id}.{forbidden}"
            assert not hasattr(profile, "capabilities")

    def test_profiles_declare_no_verification(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            assert profile.endpoint.source == "declared", provider_id
            assert profile.endpoint.verified_at is None, provider_id
            assert profile.endpoint.evidence_ref is None, provider_id

    def test_credential_is_a_reference_not_a_value(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            assert profile.credential.ref.startswith("env:"), provider_id
            assert profile.credential.parsed.is_supported, provider_id

    def test_shipped_profile_paths_resolve(self):
        for provider_id in ("deepseek", "mimo"):
            assert provider_profile_path(provider_id).is_file()
