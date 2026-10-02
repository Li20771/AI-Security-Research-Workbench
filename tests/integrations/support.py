"""Shared constants and builders for the AI-09 integration tests.

Separate from `conftest.py` on purpose: pytest loads a `conftest` through its own
import machinery, so importing constants *from* one can yield a second module
instance that merely happens to hold equal values. A plain module has one.
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

#: Markers that must never reach a provider request. Each is distinctive enough
#: that a substring search over the built request is a meaningful assertion.
SENTINEL_CONTEXT = "SECRET_CONTEXT_SENTINEL"
SENTINEL_WORKSPACE = "WORKSPACE_SENTINEL"
SENTINEL_EXECUTION = "EXECUTION_SENTINEL"
SENTINEL_SOURCE = "SOURCE_RECORD_SENTINEL"

MIMO_MODEL_REFS = ("mimo/mimo-v2.6-pro", "mimo/mimo-v2.6-flash")
DEEPSEEK_MODEL_REF = "deepseek/deepseek-flash"


def write_provider_config(
    tmp_path: pathlib.Path, providers: dict[str, Any], *, name: str = "providers"
):
    """Write a runtime provider config and load it the way production would.

    Written to a temp file and passed through `load_provider_config`, so the
    enablement a test relies on is real parsed config rather than a hand-built
    object that could disagree with the schema.
    """
    from providers.config import load_provider_config

    path = tmp_path / f"{name}.yaml"
    path.write_text(
        yaml.safe_dump({"version": 1, "providers": providers}), encoding="utf-8"
    )
    return load_provider_config(path)


def mimo_entry(
    *, enabled: bool, models: tuple[str, ...] = MIMO_MODEL_REFS, **extra: Any
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "enabled": enabled,
        "models": list(models),
        "transport": {
            "timeout_connect_ms": 10_000,
            "timeout_total_ms": 120_000,
            "max_retries": 0,
            "verify_tls": True,
        },
    }
    entry.update(extra)
    return entry
