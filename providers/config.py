"""Runtime provider configuration.

Runtime config selects, enables, and overrides. It never redefines identity or
protocol facts, which live in `providers/<id>/provider.yaml` as reviewable
repository data (D-1).

The config layer is where a literal credential value is rejected: entries carry
`credential.ref` in the frozen reference grammar, and `CredentialSpec`
validates the shape on construction, so a bare key cannot be represented.

Defaults are fail-closed. A provider without an explicit `enabled: true` is
disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from providers.credential import CredentialConfigError
from providers.profile import (
    PROVIDER_ID_RE,
    CredentialSpec,
    Endpoint,
    ModelRef,
    ProfileError,
    Protocol,
)
from providers.transport import TransportConfigError, TransportSettings

CONFIG_VERSION = 1

_ENTRY_KEYS = frozenset(
    {
        "enabled",
        "protocol",
        "endpoint",
        "credential",
        "models",
        "transport",
        "reserved",
        "reserved_for",
        "note",
    }
)


class ProviderConfigError(ValueError):
    """The runtime provider configuration is malformed."""


@dataclass(frozen=True, slots=True)
class ProviderConfigEntry:
    """One provider's runtime configuration.

    Profile-shaped fields are optional: absent means "use the profile's
    declared value". Present means an explicit override, which the contract
    requires to be recorded as `source: override` on the effective endpoint.
    """

    provider_id: str
    enabled: bool = False
    reserved: bool = False
    reserved_for: str | None = None
    note: str | None = None
    protocol: Protocol | None = None
    endpoint: Endpoint | None = None
    credential: CredentialSpec | None = None
    models: tuple[ModelRef, ...] = field(default_factory=tuple)
    transport: TransportSettings | None = None

    def __post_init__(self) -> None:
        if not PROVIDER_ID_RE.match(self.provider_id or ""):
            raise ProviderConfigError(
                f"config key {self.provider_id!r} is not a valid provider_id"
            )
        if not isinstance(self.enabled, bool):
            raise ProviderConfigError(
                f"{self.provider_id}: enabled must be a bool, "
                f"got {type(self.enabled).__name__}"
            )
        if not isinstance(self.reserved, bool):
            raise ProviderConfigError(
                f"{self.provider_id}: reserved must be a bool"
            )
        if self.reserved and self.enabled:
            raise ProviderConfigError(
                f"{self.provider_id}: a reserved extension point must not be "
                "enabled; it has no implementation"
            )


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """A parsed provider configuration document."""

    version: int
    providers: Mapping[str, ProviderConfigEntry]

    @property
    def enabled_providers(self) -> tuple[str, ...]:
        return tuple(
            sorted(pid for pid, entry in self.providers.items() if entry.enabled)
        )

    @property
    def reserved_providers(self) -> tuple[str, ...]:
        return tuple(
            sorted(pid for pid, entry in self.providers.items() if entry.reserved)
        )


def load_provider_config(path: Path) -> ProviderConfig:
    """Load and validate a runtime provider configuration file."""
    if not path.is_file():
        raise ProviderConfigError(f"provider config not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProviderConfigError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, Mapping):
        raise ProviderConfigError(
            f"{path}: expected a mapping, got {type(raw).__name__}"
        )

    unknown = set(raw) - {"version", "providers"}
    if unknown:
        raise ProviderConfigError(
            f"{path}: unknown top-level field(s): {', '.join(sorted(unknown))}"
        )

    version = raw.get("version")
    if version != CONFIG_VERSION:
        raise ProviderConfigError(
            f"{path}: unsupported version {version!r}; expected {CONFIG_VERSION}"
        )

    providers_raw = raw.get("providers")
    if not isinstance(providers_raw, Mapping):
        raise ProviderConfigError(f"{path}: 'providers' must be a mapping")

    entries: dict[str, ProviderConfigEntry] = {}
    for provider_id, entry_raw in providers_raw.items():
        entries[str(provider_id)] = _build_entry(
            str(provider_id), entry_raw, origin=str(path)
        )

    return ProviderConfig(version=version, providers=entries)


def _build_entry(
    provider_id: str, entry_raw: Any, *, origin: str
) -> ProviderConfigEntry:
    if not isinstance(entry_raw, Mapping):
        raise ProviderConfigError(
            f"{origin}: provider {provider_id!r} entry must be a mapping"
        )

    unknown = set(entry_raw) - _ENTRY_KEYS
    if unknown:
        raise ProviderConfigError(
            f"{origin}: provider {provider_id!r} has unknown field(s): "
            f"{', '.join(sorted(unknown))}"
        )

    try:
        protocol = (
            Protocol(
                family=str(entry_raw["protocol"].get("family", "")),
                version=str(entry_raw["protocol"].get("version", "")),
            )
            if isinstance(entry_raw.get("protocol"), Mapping)
            else None
        )

        endpoint_raw = entry_raw.get("endpoint")
        endpoint = (
            Endpoint(
                base_url=str(endpoint_raw.get("base_url", "")),
                path_template=str(endpoint_raw.get("path_template", "")),
                source=str(endpoint_raw.get("source", "declared")),
                verified_at=endpoint_raw.get("verified_at"),
                evidence_ref=endpoint_raw.get("evidence_ref"),
            )
            if isinstance(endpoint_raw, Mapping)
            else None
        )

        credential_raw = entry_raw.get("credential")
        credential = (
            CredentialSpec(
                ref=credential_raw.get("ref"),
                kind=str(credential_raw.get("kind", "api_key")),
                required=credential_raw.get("required", True),
            )
            if isinstance(credential_raw, Mapping)
            else None
        )

        models_raw = entry_raw.get("models", [])
        if not isinstance(models_raw, list):
            raise ProviderConfigError(
                f"{origin}: provider {provider_id!r} 'models' must be a list"
            )
        models = tuple(ModelRef.parse(entry) for entry in models_raw)

        transport = (
            TransportSettings.from_mapping(entry_raw["transport"])
            if "transport" in entry_raw
            else None
        )
    except (CredentialConfigError, ProfileError, TransportConfigError) as exc:
        raise ProviderConfigError(f"{origin}: provider {provider_id!r}: {exc}") from exc

    return ProviderConfigEntry(
        provider_id=provider_id,
        enabled=bool(entry_raw.get("enabled", False)),
        reserved=bool(entry_raw.get("reserved", False)),
        reserved_for=(
            str(entry_raw["reserved_for"])
            if entry_raw.get("reserved_for") is not None
            else None
        ),
        note=str(entry_raw["note"]) if entry_raw.get("note") is not None else None,
        protocol=protocol,
        endpoint=endpoint,
        credential=credential,
        models=models,
        transport=transport,
    )


def example_config_path() -> Path:
    """The checked-in example configuration."""
    return (
        Path(__file__).resolve().parent.parent
        / "config"
        / "providers"
        / "providers.example.yaml"
    )


__all__ = [
    "CONFIG_VERSION",
    "ProviderConfig",
    "ProviderConfigEntry",
    "ProviderConfigError",
    "example_config_path",
    "load_provider_config",
]
