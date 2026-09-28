"""Layer 3 fixture loading, with provenance enforced.

Contract §12.4: fixtures are labelled `synthetic` or `scrubbed`, and *a fixture
of unknown provenance is not usable as a regression baseline*. That rule is
enforced here rather than documented and hoped for:

- every fixture on disk must be declared in the manifest
- every declared fixture must exist
- the provenance must be one of the two frozen values
- the note must explain where the payload came from

A payload nobody can characterise is indistinguishable from one somebody made
up, so it is refused rather than silently trusted.

Every loader takes an optional `root` so the rules can be exercised against a
throwaway tree rather than only asserted about the shipped one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

FIXTURES_ROOT = Path(__file__).resolve().parent
MANIFEST_NAME = "manifest.yaml"
MANIFEST_VERSION = 1


class FixtureError(ValueError):
    """A fixture or its manifest entry is missing, malformed, or unlabelled."""


class Provenance(StrEnum):
    """The two permitted provenances (§12.4).

    `unknown` is deliberately absent: it is not a value, it is the failure the
    loader raises.
    """

    SYNTHETIC = "synthetic"
    SCRUBBED = "scrubbed"


@dataclass(frozen=True, slots=True)
class Fixture:
    """One declared, provenance-labelled response payload."""

    path: str
    provider_id: str
    provenance: Provenance
    note: str
    payload: Any

    @property
    def name(self) -> str:
        """The file stem, for display. Two providers may share one."""
        return Path(self.path).stem

    @property
    def key(self) -> str:
        """The unique lookup key: the path without its extension.

        Provider-qualified, because `deepseek/chat_stop` and `mimo/chat_stop`
        are different fixtures that happen to describe the same scenario.
        """
        return Path(self.path).with_suffix("").as_posix()

    @property
    def is_synthetic(self) -> bool:
        return self.provenance is Provenance.SYNTHETIC


def _manifest_path(root: Path) -> Path:
    return root / MANIFEST_NAME


def _read_manifest(root: Path) -> dict[str, Any]:
    manifest_path = _manifest_path(root)
    if not manifest_path.is_file():
        raise FixtureError(f"fixture manifest not found: {manifest_path}")
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FixtureError(f"{manifest_path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise FixtureError(f"{manifest_path}: expected a mapping")
    if raw.get("version") != MANIFEST_VERSION:
        raise FixtureError(
            f"{manifest_path}: unsupported version {raw.get('version')!r}; "
            f"expected {MANIFEST_VERSION}"
        )
    entries = raw.get("fixtures")
    if not isinstance(entries, list):
        raise FixtureError(f"{manifest_path}: 'fixtures' must be a list")
    return raw


def declared_paths(root: Path | None = None) -> tuple[str, ...]:
    """Every fixture path the manifest declares."""
    base = FIXTURES_ROOT if root is None else root
    return tuple(str(entry["path"]) for entry in _read_manifest(base)["fixtures"])


def paths_on_disk(root: Path | None = None) -> tuple[str, ...]:
    """Every fixture payload present, as a manifest-relative path."""
    base = FIXTURES_ROOT if root is None else root
    return tuple(
        sorted(
            str(path.relative_to(base)).replace("\\", "/")
            for path in base.rglob("*.json")
        )
    )


def load_fixtures(root: Path | None = None) -> dict[str, Fixture]:
    """Load every declared fixture, refusing anything unlabelled.

    Returns fixtures keyed by name (`chat_stop`, `error_401`, ...), which is
    unique across the provider directories by construction -- a collision is
    reported rather than silently overwriting.
    """
    base = FIXTURES_ROOT if root is None else root
    manifest = _read_manifest(base)
    manifest_path = _manifest_path(base)
    fixtures: dict[str, Fixture] = {}

    for entry in manifest["fixtures"]:
        if not isinstance(entry, dict):
            raise FixtureError(f"{manifest_path}: each fixture must be a mapping")

        for field in ("path", "provider_id", "provenance", "note"):
            if not entry.get(field):
                raise FixtureError(
                    f"{manifest_path}: fixture entry {entry.get('path')!r} is "
                    f"missing a non-empty {field!r}; a fixture without a "
                    "declared provenance is not a usable regression baseline"
                )

        relative = str(entry["path"])
        try:
            provenance = Provenance(entry["provenance"])
        except ValueError as exc:
            raise FixtureError(
                f"{manifest_path}: {relative} declares provenance "
                f"{entry['provenance']!r}, which is not one of "
                f"{[p.value for p in Provenance]}"
            ) from exc

        payload_path = base / relative
        if not payload_path.is_file():
            raise FixtureError(
                f"{manifest_path}: {relative} is declared but not present"
            )

        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FixtureError(f"{relative}: invalid JSON: {exc}") from exc

        fixture = Fixture(
            path=relative,
            provider_id=str(entry["provider_id"]),
            provenance=provenance,
            note=str(entry["note"]),
            payload=payload,
        )
        if fixture.key in fixtures:
            raise FixtureError(
                f"{relative}: fixture key {fixture.key!r} collides with "
                f"{fixtures[fixture.key].path!r}"
            )
        fixtures[fixture.key] = fixture

    undeclared = sorted(set(paths_on_disk(base)) - set(declared_paths(base)))
    if undeclared:
        raise FixtureError(
            f"{manifest_path}: fixture(s) present but undeclared: "
            f"{', '.join(undeclared)}. An undeclared fixture has no provenance, "
            "and a fixture of unknown provenance is not usable (§12.4)"
        )

    return fixtures


def fixture_names_by_provider(root: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Fixture names grouped by the provider they describe."""
    grouped: dict[str, list[str]] = {}
    for fixture in load_fixtures(root).values():
        grouped.setdefault(fixture.provider_id, []).append(fixture.name)
    return {pid: tuple(sorted(names)) for pid, names in sorted(grouped.items())}


__all__ = [
    "FIXTURES_ROOT",
    "MANIFEST_NAME",
    "MANIFEST_VERSION",
    "Fixture",
    "FixtureError",
    "Provenance",
    "declared_paths",
    "fixture_names_by_provider",
    "load_fixtures",
    "paths_on_disk",
]
