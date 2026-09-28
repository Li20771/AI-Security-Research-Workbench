"""Model profile loading.

Model profiles are reviewable repository data at
`providers/<provider_id>/models/<model_id>.yaml`, alongside the provider
profile that exposes them. They are deliberately **not** runtime config: a
capability claim needs review, and `config/providers/` is where selection and
overrides live.

Filename and directory are part of the identity contract. A profile whose
`model_id` disagrees with its filename, or whose `provider_id` disagrees with
its directory, is rejected rather than loaded under a name it does not own.

No network access, no credential resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

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
from providers.profile import ProfileError
from providers.registry import available_provider_ids, providers_root

MODELS_DIRNAME = "models"
MODEL_PROFILE_SUFFIX = ".yaml"

_PROFILE_KEYS = frozenset(
    {
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
)

#: Profile fields that belong to another layer. Reported by name so the fix is
#: obvious, rather than as a generic unknown-field error.
_PROVIDER_ONLY_FIELDS = frozenset(
    {"endpoint", "credential", "transport", "protocol", "models"}
)
_RUNTIME_ONLY_FIELDS = frozenset({"enabled", "reserved", "reserved_for"})

_CAPABILITY_KEYS = frozenset({"declared", "verified", "status", "source", "mode"})


class ModelRegistryError(ValueError):
    """A model profile could not be loaded or is malformed."""


def models_dir(provider_id: str, root: Path | None = None) -> Path:
    base = providers_root() if root is None else root
    return base / provider_id / MODELS_DIRNAME


def model_profile_path(
    provider_id: str, model_id: str, root: Path | None = None
) -> Path:
    return models_dir(provider_id, root) / f"{model_id}{MODEL_PROFILE_SUFFIX}"


def available_model_refs(root: Path | None = None) -> list[str]:
    """Every registered model ref, sorted so the order is stable.

    Ordering here is for deterministic output only. It carries no selection
    semantics: there is no default, preferred, or primary model (§6.4, D-13).
    """
    base = providers_root() if root is None else root
    refs: list[str] = []
    for provider_id in available_provider_ids(base):
        directory = models_dir(provider_id, base)
        if not directory.is_dir():
            continue
        for entry in sorted(directory.glob(f"*{MODEL_PROFILE_SUFFIX}")):
            refs.append(f"{provider_id}/{entry.stem}")
    return sorted(refs)


def load_model_profile(path: Path) -> ModelProfile:
    """Load and validate one model profile from a YAML file."""
    if not path.is_file():
        raise ModelRegistryError(f"model profile not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ModelRegistryError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, Mapping):
        raise ModelRegistryError(
            f"{path}: expected a mapping, got {type(raw).__name__}"
        )

    unknown = set(raw) - _PROFILE_KEYS
    if unknown:
        misplaced = sorted(unknown & (_PROVIDER_ONLY_FIELDS | _RUNTIME_ONLY_FIELDS))
        if misplaced:
            raise ModelRegistryError(
                f"{path}: field(s) {', '.join(misplaced)} do not belong in a model "
                "profile; provider facts live in the provider profile and "
                "enablement/overrides live in config/providers/*.yaml"
            )
        raise ModelRegistryError(
            f"{path}: unknown field(s): {', '.join(sorted(unknown))}"
        )

    missing = _PROFILE_KEYS - set(raw)
    if missing:
        raise ModelRegistryError(
            f"{path}: missing field(s): {', '.join(sorted(missing))}"
        )

    profile = _build_profile(raw, origin=str(path))

    # Filename and directory are part of the identity contract.
    if path.stem != profile.model_id:
        raise ModelRegistryError(
            f"{path}: model_id {profile.model_id!r} does not match filename "
            f"{path.stem!r}"
        )
    if path.parent.name != MODELS_DIRNAME:
        raise ModelRegistryError(
            f"{path}: model profiles must live under a '{MODELS_DIRNAME}/' directory"
        )
    if path.parent.parent.name != profile.provider_id:
        raise ModelRegistryError(
            f"{path}: provider_id {profile.provider_id!r} does not match directory "
            f"{path.parent.parent.name!r}"
        )

    return profile


def _build_capability(name: str, raw: Any, origin: str) -> CapabilityEntry:
    if not isinstance(raw, Mapping):
        raise ModelRegistryError(f"{origin}: capability {name} must be a mapping")

    unknown = set(raw) - _CAPABILITY_KEYS
    if unknown:
        raise ModelRegistryError(
            f"{origin}: capability {name} has unknown field(s): "
            f"{', '.join(sorted(unknown))}"
        )

    status_raw = raw.get("status")
    try:
        status = CapabilityStatus(status_raw)
    except ValueError as exc:
        raise ModelRegistryError(
            f"{origin}: capability {name} status {status_raw!r} is not one of the "
            f"frozen states {[s.value for s in CapabilityStatus]}"
        ) from exc

    mode_raw = raw.get("mode")
    mode = None
    if mode_raw is not None:
        try:
            mode = StructuredOutputMode(mode_raw)
        except ValueError as exc:
            raise ModelRegistryError(
                f"{origin}: capability {name} mode {mode_raw!r} is not one of "
                f"{[m.value for m in StructuredOutputMode]}"
            ) from exc

    return CapabilityEntry(
        status=status,
        declared=raw.get("declared"),
        verified=raw.get("verified"),
        source=raw.get("source"),
        mode=mode,
    )


def _build_profile(raw: Mapping[str, Any], *, origin: str) -> ModelProfile:
    try:
        limits_raw = raw["limits"]
        if not isinstance(limits_raw, Mapping):
            raise ModelRegistryError(f"{origin}: limits must be a mapping")
        limits = Limits(
            context_limit=limits_raw.get("context_limit"),
            max_output=limits_raw.get("max_output"),
        )

        modality_raw = raw["modality"]
        if not isinstance(modality_raw, Mapping):
            raise ModelRegistryError(f"{origin}: modality must be a mapping")
        modality = Modality(
            input=_modality_tuple(modality_raw.get("input"), "input", origin),
            output=_modality_tuple(modality_raw.get("output"), "output", origin),
        )

        capabilities_raw = raw["capabilities"]
        if not isinstance(capabilities_raw, Mapping):
            raise ModelRegistryError(f"{origin}: capabilities must be a mapping")

        declared_names = {str(k) for k in capabilities_raw}
        expected_names = {name.value for name in CapabilityName}
        if declared_names != expected_names:
            missing = sorted(expected_names - declared_names)
            extra = sorted(declared_names - expected_names)
            detail = []
            if missing:
                detail.append(f"missing {', '.join(missing)}")
            if extra:
                detail.append(f"unknown {', '.join(extra)}")
            raise ModelRegistryError(
                f"{origin}: capabilities must declare exactly the five frozen "
                f"capabilities ({'; '.join(detail)})"
            )

        capabilities = Capabilities(
            **{
                name.value: _build_capability(name.value, capabilities_raw[name.value], origin)
                for name in CapabilityName
            }
        )

        provenance_raw = raw["provenance"]
        if not isinstance(provenance_raw, Mapping):
            raise ModelRegistryError(f"{origin}: provenance must be a mapping")
        provenance = Provenance(
            declared_source=provenance_raw.get("declared_source"),
            declared_at=provenance_raw.get("declared_at"),
            verified_at=provenance_raw.get("verified_at"),
            evidence_ref=provenance_raw.get("evidence_ref"),
        )

        # Constructed inside the try: the profile's own cross-field rules
        # (model_ref consistency, version type, VERIFIED provenance) raise
        # ModelProfileError, which callers should see as a registry error
        # carrying the file it came from.
        profile = ModelProfile(
            model_ref=str(raw["model_ref"]),
            provider_id=str(raw["provider_id"]),
            model_id=str(raw["model_id"]),
            display_name=str(raw["display_name"]),
            family=str(raw["family"]),
            version=raw["version"],
            limits=limits,
            modality=modality,
            capabilities=capabilities,
            provenance=provenance,
        )
    except (ModelProfileError, ProfileError) as exc:
        raise ModelRegistryError(f"{origin}: {exc}") from exc

    return profile


def _modality_tuple(raw: Any, name: str, origin: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ModelRegistryError(
            f"{origin}: modality.{name} must be a list, got {type(raw).__name__}"
        )
    return tuple(str(entry) for entry in raw)


def load_model(
    provider_id: str, model_id: str, root: Path | None = None
) -> ModelProfile:
    return load_model_profile(model_profile_path(provider_id, model_id, root))


def load_all_model_profiles(root: Path | None = None) -> dict[str, ModelProfile]:
    """Load every registered model profile, keyed by model ref."""
    base = providers_root() if root is None else root
    profiles: dict[str, ModelProfile] = {}

    for provider_id in available_provider_ids(base):
        directory = models_dir(provider_id, base)
        if not directory.is_dir():
            continue
        for entry in sorted(directory.glob(f"*{MODEL_PROFILE_SUFFIX}")):
            profile = load_model_profile(entry)
            if profile.model_ref in profiles:
                raise ModelRegistryError(
                    f"{entry}: duplicate model_ref {profile.model_ref!r}"
                )
            profiles[profile.model_ref] = profile

    return profiles


def load_provider_models(
    provider_id: str, root: Path | None = None
) -> dict[str, ModelProfile]:
    """Model profiles belonging to one provider, keyed by model ref."""
    base = providers_root() if root is None else root
    return {
        ref: profile
        for ref, profile in load_all_model_profiles(base).items()
        if profile.provider_id == provider_id
    }


__all__ = [
    "MODEL_PROFILE_SUFFIX",
    "MODELS_DIRNAME",
    "ModelRegistryError",
    "available_model_refs",
    "load_all_model_profiles",
    "load_model",
    "load_model_profile",
    "load_provider_models",
    "model_profile_path",
    "models_dir",
]
