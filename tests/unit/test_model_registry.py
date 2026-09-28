"""Model profile loading.

Contract §6 plus the identity rules: filename and directory are part of the
identity contract, so a profile cannot be loaded under a name it does not own.

Fixtures are built as dicts and dumped with `yaml.safe_dump` rather than
assembled by string surgery, so a test mutates exactly the key it means to.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from providers.model_profile import CapabilityName
from providers.model_registry import (
    ModelRegistryError,
    available_model_refs,
    load_all_model_profiles,
    load_model,
    load_model_profile,
    model_profile_path,
    models_dir,
)
from providers.registry import providers_root

MINIMAL_PROVIDER: dict = {
    "provider_id": "example",
    "display_name": "Example",
    "protocol": {"family": "openai_compatible_chat", "version": "v1"},
    "endpoint": {
        "base_url": "https://example.test",
        "path_template": "/chat/completions",
        "source": "declared",
        "verified_at": None,
        "evidence_ref": None,
    },
    "credential": {"ref": "env:EXAMPLE_API_KEY", "kind": "api_key", "required": True},
    "models": [],
}


def minimal_model(provider_id: str = "example", model_id: str = "example-model") -> dict:
    return {
        "model_ref": f"{provider_id}/{model_id}",
        "provider_id": provider_id,
        "model_id": model_id,
        "display_name": "Example Model",
        "family": "example",
        "version": "1.0",
        "limits": {"context_limit": None, "max_output": None},
        "modality": {"input": ["text"], "output": ["text"]},
        "capabilities": {
            name.value: {
                "declared": None,
                "verified": None,
                "status": "UNKNOWN",
                "source": None,
            }
            for name in CapabilityName
        },
        "provenance": {
            "declared_source": None,
            "declared_at": None,
            "verified_at": None,
            "evidence_ref": None,
        },
    }


def _dump(path: Path, doc: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def _repo(root: Path, provider_id: str = "example") -> Path:
    """A minimal valid provider directory, so its models are discoverable."""
    provider = copy.deepcopy(MINIMAL_PROVIDER)
    provider["provider_id"] = provider_id
    _dump(root / provider_id / "provider.yaml", provider)
    return root


def _model_path(root: Path, doc: dict, filename: str | None = None) -> Path:
    provider_id = doc["provider_id"]
    stem = filename if filename is not None else doc["model_id"]
    return root / provider_id / "models" / f"{stem}.yaml"


def _write_model(root: Path, doc: dict, filename: str | None = None) -> Path:
    return _dump(_model_path(root, doc, filename), doc)


class TestLoadingTheShippedProfiles:
    def test_all_three_load(self, model_profiles):
        assert set(model_profiles) == {
            "deepseek/deepseek-flash",
            "mimo/mimo-v2.6-pro",
            "mimo/mimo-v2.6-flash",
        }

    def test_available_model_refs_lists_exactly_three(self):
        assert len(available_model_refs()) == 3

    def test_load_model_by_identity(self):
        profile = load_model("deepseek", "deepseek-flash")
        assert profile.model_ref == "deepseek/deepseek-flash"

    def test_paths_resolve(self):
        for provider_id, model_id in (
            ("deepseek", "deepseek-flash"),
            ("mimo", "mimo-v2.6-pro"),
            ("mimo", "mimo-v2.6-flash"),
        ):
            assert model_profile_path(provider_id, model_id).is_file()
            assert models_dir(provider_id).is_dir()


class TestIdentityIsEnforcedByPath:
    def test_model_id_must_match_the_filename(self, tmp_path):
        path = _write_model(tmp_path, minimal_model(), filename="wrong-name")
        with pytest.raises(ModelRegistryError, match="filename"):
            load_model_profile(path)

    def test_provider_id_must_match_the_directory(self, tmp_path):
        doc = minimal_model()
        doc.update({"provider_id": "deepseek", "model_ref": "deepseek/example-model"})
        _repo(tmp_path, "deepseek")
        path = _write_model(tmp_path, doc)
        assert path.parent.parent.name == "deepseek"
        # Directory agrees, so this loads; the mismatch case is below.
        assert load_model_profile(path).provider_id == "deepseek"

    def test_a_profile_in_the_wrong_directory_is_rejected(self, tmp_path):
        doc = minimal_model()  # provider_id example
        _repo(tmp_path, "other")
        path = tmp_path / "other" / "models" / "example-model.yaml"
        _dump(path, doc)
        with pytest.raises(ModelRegistryError, match="does not match directory"):
            load_model_profile(path)

    def test_profiles_must_live_under_a_models_directory(self, tmp_path):
        path = _dump(tmp_path / "example" / "example-model.yaml", minimal_model())
        with pytest.raises(ModelRegistryError, match="models/"):
            load_model_profile(path)

    def test_path_rules_make_duplicate_refs_impossible(self, tmp_path):
        """A ref comes from `provider_id` + filename, so it cannot repeat.

        The registry guards against duplicates defensively, but these two rules
        are what actually guarantee uniqueness.
        """
        _repo(tmp_path)
        _write_model(tmp_path, minimal_model(model_id="alpha"))
        _write_model(tmp_path, minimal_model(model_id="beta"))

        profiles = load_all_model_profiles(tmp_path)
        assert set(profiles) == {"example/alpha", "example/beta"}
        assert len(profiles) == len(set(profiles))

    def test_a_provider_without_provider_yaml_contributes_no_models(self, tmp_path):
        _write_model(tmp_path, minimal_model())
        assert load_all_model_profiles(tmp_path) == {}

    def test_missing_file_is_reported(self, tmp_path):
        with pytest.raises(ModelRegistryError, match="not found"):
            load_model_profile(tmp_path / "example" / "models" / "absent.yaml")


class TestMalformedProfiles:
    def test_missing_field_is_rejected(self, tmp_path):
        doc = minimal_model()
        del doc["family"]
        path = _write_model(tmp_path, doc)
        with pytest.raises(ModelRegistryError, match="missing field"):
            load_model_profile(path)

    def test_unknown_field_is_rejected(self, tmp_path):
        doc = minimal_model()
        doc["mystery"] = True
        with pytest.raises(ModelRegistryError, match="unknown field"):
            load_model_profile(_write_model(tmp_path, doc))

    @pytest.mark.parametrize(
        "field,value",
        [
            ("endpoint", {"base_url": "https://example.test"}),
            ("credential", {"ref": "env:X"}),
            ("transport", {"max_retries": 0}),
            ("protocol", {"family": "openai_compatible_chat"}),
            ("enabled", True),
        ],
    )
    def test_another_layers_field_is_rejected_by_name(self, tmp_path, field, value):
        """Provider facts and runtime config do not belong in a model profile."""
        doc = minimal_model()
        doc[field] = value
        with pytest.raises(ModelRegistryError, match=field):
            load_model_profile(_write_model(tmp_path, doc))

    def test_missing_capability_is_rejected(self, tmp_path):
        doc = minimal_model()
        del doc["capabilities"]["prompt_caching"]
        with pytest.raises(ModelRegistryError, match="capabilities"):
            load_model_profile(_write_model(tmp_path, doc))

    def test_unknown_capability_is_rejected(self, tmp_path):
        doc = minimal_model()
        doc["capabilities"]["telepathy"] = {"status": "UNKNOWN"}
        with pytest.raises(ModelRegistryError, match="telepathy"):
            load_model_profile(_write_model(tmp_path, doc))

    def test_invalid_status_is_rejected(self, tmp_path):
        doc = minimal_model()
        doc["capabilities"]["tool_calling"]["status"] = "PROBABLY"
        with pytest.raises(ModelRegistryError, match="frozen states"):
            load_model_profile(_write_model(tmp_path, doc))

    def test_invalid_mode_is_rejected(self, tmp_path):
        doc = minimal_model()
        doc["capabilities"]["structured_output"]["mode"] = "json_ish"
        with pytest.raises(ModelRegistryError, match="mode"):
            load_model_profile(_write_model(tmp_path, doc))

    def test_unquoted_version_is_rejected(self, tmp_path):
        doc = minimal_model()
        doc["version"] = 1.0  # YAML float, not a string
        with pytest.raises(ModelRegistryError, match="version"):
            load_model_profile(_write_model(tmp_path, doc))

    def test_boolean_string_for_declared_is_rejected(self, tmp_path):
        doc = minimal_model()
        doc["capabilities"]["tool_calling"]["declared"] = "yes"
        with pytest.raises(ModelRegistryError, match="declared"):
            load_model_profile(_write_model(tmp_path, doc))

    def test_non_mapping_document_is_rejected(self, tmp_path):
        path = tmp_path / "example" / "models" / "example-model.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ModelRegistryError, match="mapping"):
            load_model_profile(path)

    def test_invalid_yaml_is_rejected(self, tmp_path):
        path = tmp_path / "example" / "models" / "example-model.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("model_ref: [oops\n", encoding="utf-8")
        with pytest.raises(ModelRegistryError, match="invalid YAML"):
            load_model_profile(path)


class TestProviderWithoutModels:
    def test_openai_compatible_has_no_models_directory(self):
        """The reserved provider has no profiles, so it contributes no refs."""
        assert not models_dir("openai-compatible").is_dir()
        assert not any(
            ref.startswith("openai-compatible/") for ref in available_model_refs()
        )

    def test_every_model_ref_belongs_to_a_registered_provider(self, model_profiles):
        from providers.registry import available_provider_ids

        providers = set(available_provider_ids())
        for ref, profile in model_profiles.items():
            assert profile.provider_id in providers, ref

    def test_models_live_under_the_providers_directory(self):
        assert models_dir("deepseek").parent == providers_root() / "deepseek"
