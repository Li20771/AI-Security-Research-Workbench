"""Provider profile loading.

A provider profile is repository data under `providers/<provider_id>/`,
reviewed like code (D-1). This module reads it and enforces the shape; it does
not reach the network and does not resolve credentials.

A directory without a `provider.yaml` is not a registered provider. That is
how `providers/openai-compatible/` stays a reserved extension point for AI-09
rather than becoming a third implemented provider.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from providers.credential import CredentialConfigError
from providers.profile import (
    CredentialSpec,
    Endpoint,
    ModelRef,
    ProfileError,
    Protocol,
    ProviderProfile,
)
from providers.transport import TransportConfigError, TransportSettings

PROFILE_FILENAME = "provider.yaml"

_PROFILE_KEYS = frozenset(
    {
        "provider_id",
        "display_name",
        "protocol",
        "endpoint",
        "credential",
        "models",
        "transport",
    }
)


class RegistryError(ValueError):
    """A provider profile could not be loaded or is malformed."""


def providers_root() -> Path:
    """The `providers/` directory."""
    return Path(__file__).resolve().parent


def provider_profile_path(provider_id: str, root: Path | None = None) -> Path:
    base = providers_root() if root is None else root
    return base / provider_id / PROFILE_FILENAME


def available_provider_ids(root: Path | None = None) -> list[str]:
    """Provider ids that have a `provider.yaml`. Sorted, so order is stable."""
    base = providers_root() if root is None else root
    if not base.is_dir():
        return []
    return sorted(
        entry.name
        for entry in base.iterdir()
        if entry.is_dir()
        and not entry.name.startswith((".", "_"))
        and (entry / PROFILE_FILENAME).is_file()
    )


def load_provider_profile(path: Path) -> ProviderProfile:
    """Load and validate one provider profile from a YAML file."""
    if not path.is_file():
        raise RegistryError(f"provider profile not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RegistryError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, Mapping):
        raise RegistryError(
            f"{path}: expected a mapping, got {type(raw).__name__}"
        )

    unknown = set(raw) - _PROFILE_KEYS
    if unknown:
        raise RegistryError(
            f"{path}: unknown field(s): {', '.join(sorted(unknown))}"
        )

    missing = _PROFILE_KEYS - set(raw)
    if missing:
        raise RegistryError(
            f"{path}: missing field(s): {', '.join(sorted(missing))}"
        )

    profile = _build_profile(raw, origin=str(path))

    # The directory name is part of the identity contract: config keys and
    # model refs both address providers by id.
    if path.parent.name != profile.provider_id:
        raise RegistryError(
            f"{path}: provider_id {profile.provider_id!r} does not match "
            f"directory {path.parent.name!r}"
        )

    return profile


def _build_profile(raw: Mapping[str, Any], *, origin: str) -> ProviderProfile:
    try:
        protocol_raw = raw["protocol"]
        if not isinstance(protocol_raw, Mapping):
            raise RegistryError(f"{origin}: protocol must be a mapping")
        protocol = Protocol(
            family=str(protocol_raw.get("family", "")),
            version=str(protocol_raw.get("version", "")),
        )

        endpoint_raw = raw["endpoint"]
        if not isinstance(endpoint_raw, Mapping):
            raise RegistryError(f"{origin}: endpoint must be a mapping")
        endpoint = Endpoint(
            base_url=str(endpoint_raw.get("base_url", "")),
            path_template=str(endpoint_raw.get("path_template", "")),
            source=str(endpoint_raw.get("source", "declared")),
            verified_at=endpoint_raw.get("verified_at"),
            evidence_ref=endpoint_raw.get("evidence_ref"),
        )

        credential_raw = raw["credential"]
        if not isinstance(credential_raw, Mapping):
            raise RegistryError(f"{origin}: credential must be a mapping")
        credential = CredentialSpec(
            ref=credential_raw.get("ref"),
            kind=str(credential_raw.get("kind", "api_key")),
            required=credential_raw.get("required", True),
        )

        models_raw = raw["models"]
        if not isinstance(models_raw, list):
            raise RegistryError(f"{origin}: models must be a list")
        models = tuple(ModelRef.parse(entry) for entry in models_raw)

        transport = TransportSettings.from_mapping(raw["transport"])
    except (CredentialConfigError, TransportConfigError, ProfileError) as exc:
        raise RegistryError(f"{origin}: {exc}") from exc

    return ProviderProfile(
        provider_id=str(raw["provider_id"]),
        display_name=str(raw["display_name"]),
        protocol=protocol,
        endpoint=endpoint,
        credential=credential,
        models=models,
        transport=transport,
    )


def load_provider(provider_id: str, root: Path | None = None) -> ProviderProfile:
    return load_provider_profile(provider_profile_path(provider_id, root))


def load_all_providers(root: Path | None = None) -> dict[str, ProviderProfile]:
    """Load every registered provider profile, keyed by provider id."""
    base = providers_root() if root is None else root
    return {
        provider_id: load_provider(provider_id, base)
        for provider_id in available_provider_ids(base)
    }


__all__ = [
    "PROFILE_FILENAME",
    "RegistryError",
    "available_provider_ids",
    "load_all_providers",
    "load_provider",
    "load_provider_profile",
    "provider_profile_path",
    "providers_root",
]
