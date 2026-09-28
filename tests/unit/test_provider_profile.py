"""Provider profile schema and registry loading.

Contract §5.1 - §5.7, D-1. A profile is reviewable repository data; the loader
enforces its shape and refuses anything it cannot represent.
"""

from __future__ import annotations

import textwrap
from dataclasses import FrozenInstanceError, fields

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
    """
).lstrip("\n")

#: A profile body carrying transport settings. These belong to runtime config
#: (§5.11), so a profile with them must be rejected rather than loaded.
PROFILE_WITH_TRANSPORT = (
    MINIMAL_PROFILE.format(provider_id="example", display_name="Example")
    + "\ntransport:\n  timeout_connect_ms: 10000\n  timeout_total_ms: 120000\n"
)


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
        assert profile.display_name == "Example"
        assert profile.model_refs == ("example/example-model",)

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


class TestTransportIsNotProfileData:
    """§5.11: transport settings are runtime config, not profile data.

    The layering is enforced structurally, not by convention: the profile type
    has no such field, the field is declared with slots, and the loader rejects
    any profile that carries one.
    """

    def test_provider_profile_has_no_transport_field(self):
        assert "transport" not in {f.name for f in fields(ProviderProfile)}

    def test_provider_profile_has_no_transport_attribute(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            assert not hasattr(profile, "transport"), provider_id

    def test_transport_cannot_be_reattached_to_a_profile(self, deepseek_profile):
        """The layering guarantee is structural: the attribute cannot exist.

        CPython raises `TypeError` rather than `AttributeError` for an
        undeclared attribute on a `frozen=True, slots=True` dataclass: the
        generated `__setattr__` compares against the pre-slots class object.
        The assignment is still refused, which is the property that matters,
        so this asserts the effect rather than the exception type.

        Declared fields still raise `FrozenInstanceError` normally.
        """
        with pytest.raises((AttributeError, TypeError)):
            deepseek_profile.transport = None  # type: ignore[misc]
        assert not hasattr(deepseek_profile, "transport")

    def test_declared_fields_still_raise_frozen_instance_error(self, deepseek_profile):
        with pytest.raises(FrozenInstanceError):
            deepseek_profile.provider_id = "hacked"  # type: ignore[misc]
        assert deepseek_profile.provider_id == "deepseek"

    def test_serialized_profile_carries_no_transport(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            assert "transport" not in profile.to_dict(), provider_id

    def test_a_profile_carrying_transport_is_rejected(self, tmp_path):
        path = _write(tmp_path / "example" / "provider.yaml", PROFILE_WITH_TRANSPORT)
        with pytest.raises(RegistryError, match="runtime config"):
            load_provider_profile(path)

    def test_rejection_message_points_at_the_right_layer(self, tmp_path):
        path = _write(tmp_path / "example" / "provider.yaml", PROFILE_WITH_TRANSPORT)
        with pytest.raises(RegistryError) as excinfo:
            load_provider_profile(path)
        message = str(excinfo.value)
        assert "transport" in message
        assert "config/providers" in message

    def test_shipped_profiles_contain_no_transport_block(self):
        for provider_id in ("deepseek", "mimo"):
            text = provider_profile_path(provider_id).read_text(encoding="utf-8")
            assert "\ntransport:" not in text, provider_id

    def test_transport_loads_from_runtime_config_instead(self, example_config):
        """The same settings are available where they belong."""
        for provider_id in ("deepseek", "mimo"):
            transport = example_config.transport_for(provider_id)
            assert transport.max_retries == 0, provider_id
            assert transport.verify_tls is True, provider_id


class TestProtocolSchema:
    """§5.4 reconciliation: `Protocol` carries `family` and `version` only.

    §5.4's illustrative YAML block also shows `streaming: sse` and
    `source: declared`, but **no rule in §5.4 defines either field**. Both have
    authoritative definitions elsewhere, and neither is a provider fact:

    - `streaming` is defined in §6.7 as a *model capability* under the truth
      model -- object-shaped (`declared` / `verified` / `status` / `source`)
      and AI-02-B2 scope. A scalar `protocol.streaming` would be a second,
      differently-shaped field with the same name, and would assert a
      capability claim that §8.3 forbids asserting without evidence.
    - `source` is defined for endpoints in §5.2 and for capabilities in §6.8.
      §5.4 gives it no meaning.

    Adding them to B1 would invent semantics the contract does not define, so
    they are excluded. These assertions freeze that determination: if either
    is ever added, it is a deliberate contract amendment, not a drift.
    """

    def test_protocol_carries_only_family_and_version(self):
        assert {f.name for f in fields(Protocol)} == {"family", "version"}

    def test_protocol_has_no_streaming_or_source_attributes(self):
        protocol = Protocol("openai_compatible_chat", "v1")
        assert not hasattr(protocol, "streaming")
        assert not hasattr(protocol, "source")

    def test_protocol_serializes_family_and_version_only(self):
        assert set(Protocol("openai_compatible_chat", "v1").to_dict()) == {
            "family",
            "version",
        }

    def test_shipped_profiles_declare_family_and_version_only(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            assert set(profile.protocol.to_dict()) == {"family", "version"}, provider_id

    def test_shipped_profile_yaml_declares_no_streaming(self):
        """`streaming` is a capability (§6.7), not a provider protocol fact."""
        for provider_id in ("deepseek", "mimo"):
            text = provider_profile_path(provider_id).read_text(encoding="utf-8")
            assert "streaming:" not in text, provider_id

    def test_protocol_fields_must_not_be_empty(self):
        with pytest.raises(ProfileError):
            Protocol("", "v1")
        with pytest.raises(ProfileError):
            Protocol("openai_compatible_chat", "")


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
