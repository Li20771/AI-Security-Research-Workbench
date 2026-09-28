"""Provider identity and model references.

Contract §5.1, §5.5, §5.7. AI-02 is scoped to exactly two providers, and the
reserved OpenAI-compatible slot is not one of them.
"""

from __future__ import annotations

import pytest

from providers.registry import (
    available_provider_ids,
    load_all_providers,
    load_provider,
    provider_profile_path,
    providers_root,
)


pytestmark = pytest.mark.layer1

EXPECTED_PROVIDERS = {
    "deepseek": {
        "display_name": "DeepSeek",
        "models": ("deepseek/deepseek-flash",),
        "credential_ref": "env:DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
    },
    "mimo": {
        "display_name": "MiMo",
        "models": ("mimo/mimo-v2.6-pro", "mimo/mimo-v2.6-flash"),
        "credential_ref": "env:MIMO_API_KEY",
        "base_url": "https://api.xiaomimimo.com/v1",
    },
}


class TestScope:
    def test_exactly_two_providers_are_registered(self):
        assert available_provider_ids() == ["deepseek", "mimo"]

    def test_registered_providers_match_the_frozen_scope(self):
        assert set(load_all_providers()) == set(EXPECTED_PROVIDERS)

    def test_reserved_provider_is_not_registered(self):
        """`providers/openai-compatible/` has no profile: AI-09 owns it."""
        assert "openai-compatible" not in available_provider_ids()
        assert not provider_profile_path("openai-compatible").is_file()

    def test_reserved_directory_still_exists(self):
        """Untouched, but still present as the reserved extension point."""
        assert (providers_root() / "openai-compatible").is_dir()


class TestIdentity:
    @pytest.mark.parametrize("provider_id", sorted(EXPECTED_PROVIDERS))
    def test_profile_identity_matches_declaration(self, all_profiles, provider_id):
        expected = EXPECTED_PROVIDERS[provider_id]
        profile = all_profiles[provider_id]
        assert profile.provider_id == provider_id
        assert profile.display_name == expected["display_name"]
        assert profile.model_refs == expected["models"]
        assert profile.endpoint.base_url == expected["base_url"]
        assert profile.credential.ref == expected["credential_ref"]

    def test_providers_are_distinct(self, all_profiles):
        deepseek = all_profiles["deepseek"]
        mimo = all_profiles["mimo"]
        assert deepseek.provider_id != mimo.provider_id
        assert deepseek.display_name != mimo.display_name
        assert deepseek.endpoint.base_url != mimo.endpoint.base_url
        assert deepseek.credential.ref != mimo.credential.ref
        assert set(deepseek.model_refs).isdisjoint(mimo.model_refs)

    def test_shared_protocol_family_but_separate_profiles(self, all_profiles):
        """D-2: one adapter, two profiles. Attribution depends on it."""
        families = {p.protocol.family for p in all_profiles.values()}
        assert families == {"openai_compatible_chat"}
        assert len({p.provider_id for p in all_profiles.values()}) == 2

    def test_provider_id_matches_its_directory(self):
        for provider_id in available_provider_ids():
            path = provider_profile_path(provider_id)
            assert path.parent.name == provider_id
            assert load_provider(provider_id).provider_id == provider_id


class TestModelReferences:
    @pytest.mark.parametrize(
        "provider_id,expected",
        [(pid, sorted(cfg["models"])) for pid, cfg in EXPECTED_PROVIDERS.items()],
    )
    def test_model_refs_use_provider_slash_model(self, all_profiles, provider_id, expected):
        assert sorted(all_profiles[provider_id].model_refs) == expected

    def test_every_model_ref_names_its_own_provider(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            for model_ref in profile.models:
                assert model_ref.provider_id == provider_id

    def test_mimo_exposes_both_reference_models(self, mimo_profile):
        assert "mimo/mimo-v2.6-pro" in mimo_profile.model_refs
        assert "mimo/mimo-v2.6-flash" in mimo_profile.model_refs

    def test_display_names_are_not_used_as_model_ids(self, all_profiles):
        """A display name is never sent to a provider (§6.3)."""
        model_ids = {
            ref.model_id for p in all_profiles.values() for ref in p.models
        }
        assert "DeepSeek-V4.1-Flash" not in model_ids
        assert "MiMo-V2.6-Pro" not in model_ids
        assert "MiMo-V2.6-Flash" not in model_ids

    def test_no_model_is_marked_as_a_default(self, all_profiles):
        """The model list carries no ordering semantics (§5.7, D-13)."""
        for provider_id, profile in all_profiles.items():
            for attr in ("default_model", "default", "primary"):
                assert not hasattr(profile, attr), f"{provider_id}.{attr}"
