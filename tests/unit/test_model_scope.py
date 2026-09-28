"""The frozen AI-02 model scope.

Contract §6.4: three models, and nothing else. §6.5: unknown limits stay null.
§6.6: v1 modality is text. D-13: no model is a default.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from providers.model_profile import CapabilityStatus
from providers.model_registry import available_model_refs
from providers.validate import AI02_SCOPE_MODELS, main, validate_all

#: Transcribed from contract §6.4. `display_name` and `model_id` are recorded
#: as a pair, independently -- the second is not derived from the first.
FROZEN_IDENTITY: dict[str, dict[str, str]] = {
    "deepseek/deepseek-flash": {
        "provider_id": "deepseek",
        "model_id": "deepseek-flash",
        "display_name": "DeepSeek-V4.1-Flash",
        "family": "deepseek",
        "version": "4.1",
    },
    "mimo/mimo-v2.6-pro": {
        "provider_id": "mimo",
        "model_id": "mimo-v2.6-pro",
        "display_name": "MiMo-V2.6-Pro",
        "family": "mimo",
        "version": "2.6",
    },
    "mimo/mimo-v2.6-flash": {
        "provider_id": "mimo",
        "model_id": "mimo-v2.6-flash",
        "display_name": "MiMo-V2.6-Flash",
        "family": "mimo",
        "version": "2.6",
    },
}

EXPECTED_REFS = set(FROZEN_IDENTITY)


class TestScopeIsExactlyThree:
    def test_scope_constant_matches_the_frozen_table(self):
        assert AI02_SCOPE_MODELS == EXPECTED_REFS

    def test_exactly_three_model_profiles_exist(self, model_profiles):
        assert len(model_profiles) == 3

    def test_the_registered_refs_are_exactly_the_frozen_scope(self, model_profiles):
        assert set(model_profiles) == EXPECTED_REFS

    def test_available_model_refs_matches(self):
        assert set(available_model_refs()) == EXPECTED_REFS

    def test_no_fourth_model_is_present(self, model_profiles):
        assert not (set(model_profiles) - EXPECTED_REFS)


@pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
class TestFrozenIdentity:
    def test_identity_fields_match_the_contract(self, model_profiles, ref):
        profile = model_profiles[ref]
        expected = FROZEN_IDENTITY[ref]
        for field, value in expected.items():
            assert getattr(profile, field) == value, f"{ref}.{field}"

    def test_model_ref_is_provider_slash_model_id(self, model_profiles, ref):
        profile = model_profiles[ref]
        assert profile.model_ref == f"{profile.provider_id}/{profile.model_id}"

    def test_model_id_differs_from_display_name(self, model_profiles, ref):
        """Two independent records that happen to correspond (§6.3)."""
        profile = model_profiles[ref]
        assert profile.model_id != profile.display_name

    def test_model_id_is_recorded_verbatim(self, model_profiles, ref):
        """Case matters: the API id is sent as written."""
        profile = model_profiles[ref]
        assert profile.model_id == FROZEN_IDENTITY[ref]["model_id"]
        assert profile.model_id == profile.model_id.strip()
        assert profile.model_id == profile.model_id.lower()


class TestLimitsStayUnknown:
    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_context_limit_is_none(self, model_profiles, ref):
        assert model_profiles[ref].limits.context_limit is None

    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_max_output_is_none(self, model_profiles, ref):
        assert model_profiles[ref].limits.max_output is None

    def test_no_limit_is_zero(self, model_profiles):
        """Zero is a measurement. Nobody measured anything."""
        for ref, profile in model_profiles.items():
            assert profile.limits.context_limit != 0, ref
            assert profile.limits.max_output != 0, ref

    def test_all_limits_are_unknown(self, model_profiles):
        for ref, profile in model_profiles.items():
            assert profile.limits.are_unknown, ref


class TestModalityIsV1:
    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_input_is_text(self, model_profiles, ref):
        assert model_profiles[ref].modality.input == ("text",)

    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_output_is_text(self, model_profiles, ref):
        assert model_profiles[ref].modality.output == ("text",)

    def test_no_extra_modality_is_declared(self, model_profiles):
        for ref, profile in model_profiles.items():
            assert profile.modality.to_dict() == {
                "input": ["text"],
                "output": ["text"],
            }, ref


class TestProvenanceIsEmpty:
    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_declared_source_is_none(self, model_profiles, ref):
        assert model_profiles[ref].provenance.declared_source is None

    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_verified_at_is_none(self, model_profiles, ref):
        assert model_profiles[ref].provenance.verified_at is None

    @pytest.mark.parametrize("ref", sorted(FROZEN_IDENTITY))
    def test_evidence_ref_is_none(self, model_profiles, ref):
        assert model_profiles[ref].provenance.evidence_ref is None

    def test_no_verification_is_recorded(self, model_profiles):
        for ref, profile in model_profiles.items():
            assert not profile.provenance.has_verification, ref

    def test_no_capability_is_verified(self, model_profiles):
        for ref, profile in model_profiles.items():
            assert not profile.has_verified_capability, ref
            for name, entry in profile.capabilities.items():
                assert entry.status is CapabilityStatus.UNKNOWN, f"{ref}:{name.value}"


class TestNoDefaultModel:
    """D-13: no default, preferred, primary, or ranking semantics."""

    @pytest.mark.parametrize(
        "forbidden", ["default", "primary", "preferred", "priority", "weight", "rank"]
    )
    def test_model_profile_has_no_ranking_field(self, forbidden):
        assert forbidden not in {f.name for f in dataclasses.fields(
            __import__("providers.model_profile", fromlist=["ModelProfile"]).ModelProfile
        )}

    def test_model_refs_carry_no_ordering_semantics(self):
        """Sorted for determinism only. Nothing may read order as preference."""
        refs = available_model_refs()
        assert refs == sorted(refs)
        assert len(refs) == len(set(refs))

    def test_provider_model_lists_have_no_default_marker(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            payload = profile.to_dict()
            assert "default_model" not in payload, provider_id
            assert "preferred" not in payload, provider_id

    def test_no_model_is_marked_default_in_any_profile(self, model_profiles):
        for ref, profile in model_profiles.items():
            payload: dict[str, Any] = profile.to_dict()
            for forbidden in ("default", "preferred", "primary", "priority"):
                assert forbidden not in payload, f"{ref}.{forbidden}"


class TestValidationCoversModels:
    def test_full_validation_passes(self):
        assert validate_all() == []

    def test_cli_reports_three_models(self, capsys):
        assert main([]) == 0
        out = capsys.readouterr().out
        assert "models: 3" in out
        for ref in EXPECTED_REFS:
            assert ref in out
