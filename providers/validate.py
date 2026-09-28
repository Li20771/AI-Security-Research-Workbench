"""Offline provider / model / config validation.

Entry point for the CI validation step:

    python -m providers.validate

Checks provider profiles (AI-02-B1), model profiles (AI-02-B2), the provider
<-> model reference graph, and the checked-in example runtime config, all
against the frozen AI-02 contract.

Performs no network I/O and requires no credential -- it must pass in an
environment with no API keys set. Live connectivity verification is AI-02-B6
and is deliberately **not** part of this: a validation that could reach a
provider would stop being a validation and start being a test.

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
from providers.model_profile import (
    CapabilityName,
    CapabilityStatus,
    ModelProfile,
    ModelProfileError,
)
from providers.model_registry import (
    ModelRegistryError,
    available_model_refs,
    load_all_model_profiles,
)
from providers.profile import ProfileError, ProviderProfile
from providers.protocol import UnsupportedProtocolFamily, adapter_for
from providers.registry import (
    RegistryError,
    available_provider_ids,
    load_provider,
    providers_root,
)
from providers.transport import AI02_MAX_RETRIES

#: Providers AI-02 is scoped to freeze (contract §3.2, §5.5).
AI02_SCOPE_PROVIDERS: frozenset[str] = frozenset({"deepseek", "mimo"})

#: The complete AI-02 model scope (contract §6.4). Exactly three, and nothing
#: else -- adding a fourth is a contract amendment, not a config change.
AI02_SCOPE_MODELS: frozenset[str] = frozenset(
    {
        "deepseek/deepseek-flash",
        "mimo/mimo-v2.6-pro",
        "mimo/mimo-v2.6-flash",
    }
)

#: v1 modality (contract §6.6). Additional modalities require a declaration
#: this phase has no source for.
V1_MODALITY: tuple[str, ...] = ("text",)

#: Reserved extension point. Must exist in config, stay disabled, and have no
#: implementation (contract §3.7; task §17 of AI-02-B1).
RESERVED_PROVIDERS: frozenset[str] = frozenset({"openai-compatible"})


def validate_provider_profile(profile: ProviderProfile) -> list[str]:
    """Check one provider profile against AI-02 policy."""
    problems: list[str] = []
    pid = profile.provider_id

    if not profile.models:
        problems.append(
            f"{pid}: no models exposed; a provider that cannot enumerate its "
            "models exposes an empty list rather than a guess"
        )

    if "transport" in profile.to_dict():
        problems.append(
            f"{pid}: profile carries transport settings; they are runtime "
            "config, not profile data (§5.11)"
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


def validate_model_profile(profile: ModelProfile) -> list[str]:
    """Check one model profile against AI-02 policy.

    Structural rules are enforced by the types themselves. What is checked
    here is the *phase* policy: what AI-02-B2 is and is not allowed to assert
    before AI-02-B6 has observed anything.
    """
    problems: list[str] = []
    ref = profile.model_ref

    if profile.model_ref not in AI02_SCOPE_MODELS:
        problems.append(
            f"{ref}: outside the AI-02 model scope; the scope is exactly "
            f"{sorted(AI02_SCOPE_MODELS)}"
        )

    # Nothing may be VERIFIED: only AI-02-B6 may promote a capability, and
    # only from a dated observation (§8.3, §14).
    for name, entry in profile.capabilities.items():
        if entry.status is CapabilityStatus.VERIFIED:
            problems.append(
                f"{ref}: {name.value} is VERIFIED, but no verification phase has "
                "run; only AI-02-B6 may promote a capability (§8.3)"
            )

    # A capability that was never checked must not claim a source either.
    for name, entry in profile.capabilities.items():
        if entry.status is CapabilityStatus.UNKNOWN and entry.source is not None:
            problems.append(f"{ref}: {name.value} is UNKNOWN but carries a source")

    if not profile.limits.are_unknown:
        problems.append(
            f"{ref}: limits are declared ({profile.limits.to_dict()}), but no "
            "observation exists; an unmeasured limit must be null, never a "
            "guess (§6.5)"
        )

    if profile.modality.input != V1_MODALITY or profile.modality.output != V1_MODALITY:
        problems.append(
            f"{ref}: modality is {profile.modality.to_dict()}; v1 requires "
            f"input/output of {list(V1_MODALITY)} (§6.6)"
        )

    if profile.provenance.verified_at is not None or profile.provenance.evidence_ref is not None:
        problems.append(
            f"{ref}: provenance records a verification, but AI-02-B2 performs "
            "none; verified_at and evidence_ref must be null until AI-02-B6 (§10)"
        )

    return problems


def validate_model_provider_references(
    providers: dict[str, ProviderProfile],
    models: dict[str, ModelProfile],
) -> list[str]:
    """Check the provider <-> model reference graph both ways.

    Every model a provider exposes must resolve to a model profile, and every
    model profile must belong to a registered provider. A dangling reference in
    either direction means one layer is describing something the other does not
    have.
    """
    problems: list[str] = []

    for provider_id, profile in providers.items():
        for ref in profile.model_refs:
            if ref not in models:
                problems.append(
                    f"{provider_id}: exposes {ref!r}, which has no model profile "
                    "under providers/<provider_id>/models/"
                )

    for ref, model in models.items():
        if model.provider_id not in providers:
            problems.append(
                f"{ref}: model profile names provider {model.provider_id!r}, "
                "which is not a registered provider"
            )

    return problems


def validate_model_scope(models: dict[str, ModelProfile]) -> list[str]:
    """Check the model set is exactly the frozen scope (contract §6.4)."""
    problems: list[str] = []
    found = set(models)

    for missing in sorted(AI02_SCOPE_MODELS - found):
        problems.append(f"model scope: expected model {missing!r} is missing")
    for extra in sorted(found - AI02_SCOPE_MODELS):
        problems.append(
            f"model scope: {extra!r} is outside the AI-02 model scope; the scope "
            f"is exactly {sorted(AI02_SCOPE_MODELS)}"
        )

    return problems


def validate_example_config(path: Path | None = None) -> list[str]:
    """Check the checked-in example config."""
    problems: list[str] = []
    target = example_config_path() if path is None else path

    try:
        config = load_provider_config(target)
    except ProviderConfigError as exc:
        return [f"example config: {exc}"]

    for provider_id in AI02_SCOPE_PROVIDERS:
        if provider_id not in config.providers:
            problems.append(f"example config: missing provider {provider_id!r}")
            continue

        # Transport settings are runtime config (§5.11), so this is where
        # their policy is enforced.
        transport = config.transport_for(provider_id)
        if config.providers[provider_id].transport is None:
            problems.append(
                f"example config: provider {provider_id!r} declares no transport "
                "settings; timeouts must be explicit (§5.11)"
            )
        if transport.max_retries != AI02_MAX_RETRIES:
            problems.append(
                f"example config: {provider_id} max_retries is "
                f"{transport.max_retries}; AI-02 requires {AI02_MAX_RETRIES} "
                "(D-12, no retry loop)"
            )
        if not transport.verify_tls:
            problems.append(
                f"example config: {provider_id} disables verify_tls; disabling "
                "TLS verification is a security-relevant change requiring "
                "explicit human approval (§5.11)"
            )

    for provider_id in RESERVED_PROVIDERS:
        entry = config.providers.get(provider_id)
        if entry is None:
            problems.append(
                f"example config: reserved provider {provider_id!r} is missing; "
                "it must remain present and disabled"
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

    # --- provider layer -------------------------------------------------
    provider_ids = available_provider_ids(base)
    if not provider_ids:
        problems.append(f"no provider profiles found under {base}")

    providers: dict[str, ProviderProfile] = {}
    for provider_id in provider_ids:
        try:
            profile = load_provider(provider_id, base)
        except (RegistryError, ProfileError) as exc:
            problems.append(f"{provider_id}: {exc}")
            continue
        providers[provider_id] = profile
        problems.extend(validate_provider_profile(profile))

    # --- model layer ----------------------------------------------------
    try:
        models = load_all_model_profiles(base)
    except (ModelRegistryError, ModelProfileError) as exc:
        problems.append(f"model profiles: {exc}")
        models = {}

    for ref, model in models.items():
        problems.extend(validate_model_profile(model))

    problems.extend(validate_model_scope(models))

    # --- reference graph -------------------------------------------------
    problems.extend(validate_model_provider_references(providers, models))

    # --- runtime config --------------------------------------------------
    problems.extend(validate_example_config())

    return problems


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problems = validate_all()

    if problems:
        print("provider/config/model validation: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    providers = ", ".join(available_provider_ids())
    refs = available_model_refs()
    print(f"provider/config/model validation: PASS")
    print(f"  providers: {providers}")
    print(f"  models: {len(refs)}")
    for ref in refs:
        print(f"    - {ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
