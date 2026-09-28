"""Model profile schema and validation.

Contract §6.1 - §6.8. Structural rules live on the types, so a malformed
profile cannot be constructed at all rather than being caught later.
"""

from __future__ import annotations

import dataclasses

import pytest

from providers.model_profile import (
    Capabilities,
    CapabilityEntry,
    CapabilityName,
    CapabilityStatus,
    Limits,
    ModelProfile,
    ModelProfileError,
    Modality,
    Provenance,
    StructuredOutputMode,
)


pytestmark = pytest.mark.layer1


def make_profile(**overrides) -> ModelProfile:
    """A minimal valid profile, with fields overridable per test."""
    base = {
        "model_ref": "deepseek/deepseek-flash",
        "provider_id": "deepseek",
        "model_id": "deepseek-flash",
        "display_name": "DeepSeek-V4.1-Flash",
        "family": "deepseek",
        "version": "4.1",
    }
    base.update(overrides)
    return ModelProfile(**base)


class TestIdentity:
    def test_minimal_profile_constructs(self):
        profile = make_profile()
        assert profile.model_ref == "deepseek/deepseek-flash"
        assert profile.provider_id == "deepseek"
        assert profile.model_id == "deepseek-flash"

    def test_model_ref_must_equal_provider_and_model_id(self):
        with pytest.raises(ModelProfileError, match="model_ref"):
            make_profile(model_ref="mimo/deepseek-flash")

    def test_provider_id_must_be_a_valid_provider_id(self):
        for bad in ("DeepSeek", "-x", "", "has space"):
            with pytest.raises(ModelProfileError):
                make_profile(provider_id=bad, model_ref=f"{bad}/deepseek-flash")

    @pytest.mark.parametrize("bad", ["", "   ", "has space", "/slash", "-leading"])
    def test_model_id_must_be_a_valid_identifier(self, bad):
        with pytest.raises(ModelProfileError, match="model_id"):
            make_profile(model_id=bad, model_ref=f"deepseek/{bad}")

    @pytest.mark.parametrize("field", ["display_name", "family"])
    def test_text_fields_must_not_be_empty(self, field):
        with pytest.raises(ModelProfileError, match=field):
            make_profile(**{field: "   "})

    def test_version_must_be_a_string(self):
        """`version: 4.1` in YAML parses as a float; that must fail loudly."""
        with pytest.raises(ModelProfileError, match="version"):
            make_profile(version=4.1)

    def test_version_must_not_be_empty(self):
        with pytest.raises(ModelProfileError, match="version"):
            make_profile(version="  ")

    def test_model_id_is_independent_of_display_name(self):
        """The two are separate records, not a derivation (§6.3).

        This constructs a pair that no string transform would relate, which
        proves the schema does not validate one against the other.
        """
        profile = make_profile(
            display_name="Totally Unrelated Name",
            model_id="some-other-id",
            model_ref="deepseek/some-other-id",
        )
        assert profile.display_name != profile.model_id
        assert profile.model_id == "some-other-id"


class TestLimits:
    def test_defaults_are_unknown(self):
        limits = Limits()
        assert limits.context_limit is None
        assert limits.max_output is None
        assert limits.are_unknown

    def test_positive_values_are_representable(self):
        limits = Limits(context_limit=128_000, max_output=8_192)
        assert limits.context_limit == 128_000
        assert not limits.are_unknown

    @pytest.mark.parametrize("bad", [0, -1, -128_000])
    def test_non_positive_values_are_rejected(self, bad):
        """An unknown limit is null; a non-positive one is not a limit at all."""
        with pytest.raises(ModelProfileError, match="context_limit"):
            Limits(context_limit=bad)

    @pytest.mark.parametrize("bad", [True, False, "128000", 1.5])
    def test_non_integer_values_are_rejected(self, bad):
        with pytest.raises(ModelProfileError, match="context_limit"):
            Limits(context_limit=bad)

    def test_max_output_is_validated_too(self):
        with pytest.raises(ModelProfileError, match="max_output"):
            Limits(max_output=-5)


class TestModality:
    def test_default_is_text_to_text(self):
        modality = Modality()
        assert modality.input == ("text",)
        assert modality.output == ("text",)

    def test_input_and_output_are_separate_sets(self):
        modality = Modality(input=("text", "image"), output=("text",))
        assert modality.input != modality.output

    @pytest.mark.parametrize("field", ["input", "output"])
    def test_empty_is_rejected(self, field):
        with pytest.raises(ModelProfileError, match=f"modality.{field}"):
            Modality(**{field: ()})

    def test_duplicates_are_rejected(self):
        with pytest.raises(ModelProfileError, match="repeat"):
            Modality(input=("text", "text"))

    @pytest.mark.parametrize("bad", ["Text", "text ", "", "TEXT", "has space", "with-dash"])
    def test_values_must_be_lowercase_identifiers(self, bad):
        with pytest.raises(ModelProfileError, match="modality.input"):
            Modality(input=(bad,))


class TestCapabilitiesShape:
    def test_defaults_are_the_five_frozen_capabilities(self):
        assert {name.value for name in CapabilityName} == {
            "tool_calling",
            "structured_output",
            "streaming",
            "reasoning",
            "prompt_caching",
        }

    def test_every_capability_defaults_to_unknown(self):
        capabilities = Capabilities()
        for name, entry in capabilities.items():
            assert entry.status is CapabilityStatus.UNKNOWN, name

    def test_a_missing_capability_cannot_be_expressed(self):
        """Named fields: omission is a TypeError, not a silent KeyError."""
        with pytest.raises(TypeError):
            Capabilities(nonexistent_capability=CapabilityEntry())

    def test_mode_is_only_valid_on_structured_output(self):
        with pytest.raises(ModelProfileError, match="mode"):
            Capabilities(
                streaming=CapabilityEntry(mode=StructuredOutputMode.JSON_OBJECT)
            )

    def test_structured_output_may_carry_a_mode(self):
        capabilities = Capabilities(
            structured_output=CapabilityEntry(mode=StructuredOutputMode.JSON_OBJECT)
        )
        assert capabilities.structured_output.mode is StructuredOutputMode.JSON_OBJECT

    def test_mode_rejects_an_unknown_level(self):
        with pytest.raises(ModelProfileError, match="mode"):
            CapabilityEntry(mode="json_ish")


class TestProfileFieldBoundaries:
    """A model profile must not carry another layer's fields (§3 of the task)."""

    @pytest.mark.parametrize(
        "forbidden",
        ["endpoint", "credential", "transport", "enabled", "protocol", "capabilities_raw"],
    )
    def test_forbidden_fields_are_absent(self, forbidden):
        assert forbidden not in {f.name for f in dataclasses.fields(ModelProfile)}

    def test_forbidden_fields_cannot_be_attached(self, deepseek_flash):
        """`frozen` + `slots` make reattachment impossible, not merely frowned on."""
        with pytest.raises((AttributeError, TypeError)):
            deepseek_flash.endpoint = "https://example.test"  # type: ignore[misc]
        assert not hasattr(deepseek_flash, "endpoint")

    def test_serialized_profile_carries_only_model_layer_fields(self, deepseek_flash):
        assert set(deepseek_flash.to_dict()) == {
            "model_ref",
            "provider_id",
            "model_id",
            "display_name",
            "family",
            "version",
            "limits",
            "modality",
            "capabilities",
            "provenance",
        }


class TestProvenance:
    def test_defaults_are_empty(self):
        provenance = Provenance()
        assert provenance.declared_source is None
        assert provenance.declared_at is None
        assert provenance.verified_at is None
        assert provenance.evidence_ref is None
        assert not provenance.has_declaration
        assert not provenance.has_verification

    def test_non_string_values_are_rejected(self):
        with pytest.raises(ModelProfileError, match="declared_source"):
            Provenance(declared_source=123)


class TestImmutability:
    def test_declared_fields_raise_frozen_instance_error(self):
        profile = make_profile()
        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.model_id = "other"  # type: ignore[misc]
        assert profile.model_id == "deepseek-flash"
