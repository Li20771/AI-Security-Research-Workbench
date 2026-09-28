"""Offline provider/config validation.

Entry point for the CI `provider/config validation` step:

    python -m providers.validate

Checks every registered provider profile and the checked-in example config
against the frozen AI-02 contract. Performs no network I/O and requires no
credential -- it must pass in an environment with no API keys set.

Exit code 0 = all checks passed; 1 = at least one problem, printed to stderr.
"""

from __future__ import annotations

import sys
from pathlib import Path

from providers.config import (
    ProviderConfigError,
    example_config_path,
    load_provider_config,
)
from providers.profile import ProfileError, ProviderProfile
from providers.protocol import UnsupportedProtocolFamily, adapter_for
from providers.registry import (
    RegistryError,
    available_provider_ids,
    load_provider,
    providers_root,
)
from providers.transport import AI02_MAX_RETRIES, TransportConfigError

#: Providers AI-02 is scoped to freeze (contract §3.2, §5.5).
AI02_SCOPE_PROVIDERS: frozenset[str] = frozenset({"deepseek", "mimo"})

#: Reserved extension point. Must exist in config, stay disabled, and have no
#: implementation (contract §3.7; task §17).
RESERVED_PROVIDERS: frozenset[str] = frozenset({"openai-compatible"})


def validate_provider_profile(profile: ProviderProfile) -> list[str]:
    """Check one profile against AI-02 policy. Returns problem descriptions."""
    problems: list[str] = []
    pid = profile.provider_id

    if not profile.models:
        problems.append(
            f"{pid}: no models exposed; a provider that cannot enumerate its "
            "models exposes an empty list rather than a guess"
        )

    if profile.transport.max_retries != AI02_MAX_RETRIES:
        problems.append(
            f"{pid}: max_retries is {profile.transport.max_retries}; AI-02 "
            f"requires {AI02_MAX_RETRIES} (D-12, no retry loop)"
        )

    if not profile.transport.verify_tls:
        problems.append(
            f"{pid}: verify_tls is disabled; disabling TLS verification is a "
            "security-relevant change requiring explicit human approval (§5.11)"
        )

    if profile.endpoint.source != "declared":
        problems.append(
            f"{pid}: endpoint.source is {profile.endpoint.source!r}; AI-02-B1 "
            "records declared endpoints only, and only AI-02-B6 may promote "
            "one to verified (§5.2, §8.3)"
        )

    if profile.endpoint.verified_at is not None:
        problems.append(
            f"{pid}: endpoint.verified_at is set, but no verification phase "
            "has run; nothing in AI-02-B1 is VERIFIED"
        )

    if not profile.credential.parsed.is_supported:
        problems.append(
            f"{pid}: credential scheme {profile.credential.parsed.scheme!r} is "
            "not implemented; AI-02-B1 supports env: only (§5.3)"
        )

    try:
        adapter_for(profile.protocol.family)
    except UnsupportedProtocolFamily as exc:
        problems.append(f"{pid}: {exc}")

    return problems


def validate_example_config(path: Path | None = None) -> list[str]:
    """Check the checked-in example config. Returns problem descriptions."""
    problems: list[str] = []
    target = example_config_path() if path is None else path

    try:
        config = load_provider_config(target)
    except ProviderConfigError as exc:
        return [f"example config: {exc}"]

    for provider_id in AI02_SCOPE_PROVIDERS:
        if provider_id not in config.providers:
            problems.append(f"example config: missing provider {provider_id!r}")

    for provider_id in RESERVED_PROVIDERS:
        entry = config.providers.get(provider_id)
        if entry is None:
            problems.append(
                f"example config: reserved provider {provider_id!r} is missing; "
                "it must remain present and disabled (task §17)"
            )
            continue
        if not entry.reserved:
            problems.append(
                f"example config: provider {provider_id!r} must be marked reserved"
            )
        if entry.enabled:
            problems.append(
                f"example config: reserved provider {provider_id!r} must stay "
                "disabled; AI-09 has not been implemented"
            )

    for provider_id, entry in config.providers.items():
        if entry.reserved:
            continue
        if provider_id in available_provider_ids():
            continue
        problems.append(
            f"example config: provider {provider_id!r} has no profile under "
            "providers/; config selects providers, it does not define them"
        )

    return problems


def validate_all(root: Path | None = None) -> list[str]:
    """Run every offline validation. Returns an empty list when all pass."""
    problems: list[str] = []
    base = providers_root() if root is None else root

    provider_ids = available_provider_ids(base)
    if not provider_ids:
        problems.append(f"no provider profiles found under {base}")

    for provider_id in provider_ids:
        try:
            profile = load_provider(provider_id, base)
        except (RegistryError, ProfileError, TransportConfigError) as exc:
            problems.append(f"{provider_id}: {exc}")
            continue
        problems.extend(validate_provider_profile(profile))

    problems.extend(validate_example_config())
    return problems


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problems = validate_all()

    if problems:
        print("provider/config validation: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    ids = ", ".join(available_provider_ids())
    print(f"provider/config validation: PASS (providers: {ids})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
