"""Model binding and runtime enablement (contract §5.3, §6, §11).

A concrete backend binds exactly one model ref, explicitly, at construction. The
binding is validated here — never at call time, and never from anything else.

Two rules this module exists to enforce:

**Profile existence is not runtime enablement.** A `providers/mimo/provider.yaml`
on disk means the provider is *registered*. It does not mean an operator enabled
it. Only runtime config says that, and a provider without an explicit
`enabled: true` is disabled.

**A reserved provider is never enabled and never invoked.** It is an extension
point with no implementation behind it.

Nothing here consults the Router, the environment, the task text or the AgentId.
Which model answers is a decision a caller made by constructing a backend, and
this module only checks that the decision is one the repository permits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from providers.config import ProviderConfig
from providers.model_profile import ModelProfile
from providers.profile import ModelRef, ProfileError, ProviderProfile

from integrations.codex.errors import CodexBindingError

__all__ = [
    "CODEX_PROVIDER_ID",
    "SUPPORTED_MODEL_REFS",
    "CodexBinding",
    "bind_codex_model",
]

#: AI-09 v1 serves exactly one provider identity (contract §5.1). No third
#: provider is created, and `providers/openai-compatible/` stays reserved.
CODEX_PROVIDER_ID = "mimo"

#: The complete AI-09 v1 model scope (contract §6). Two refs, no ordering, and
#: no default. `pro` is not "the good one" and `flash` is not "the fallback".
SUPPORTED_MODEL_REFS: tuple[str, ...] = (
    "mimo/mimo-v2.6-pro",
    "mimo/mimo-v2.6-flash",
)


@dataclass(frozen=True, slots=True)
class CodexBinding:
    """A validated, immutable provider+model binding.

    Construction succeeds only when every precondition in `bind_codex_model`
    holds, so the existence of this object is itself the enablement evidence.
    """

    provider_id: str
    model_ref: str
    model_id: str

    def describe(self) -> str:
        return f"{self.provider_id}/{self.model_id}"


def _permitted_refs(
    profile: ProviderProfile, config: ProviderConfig, entry_models: tuple[ModelRef, ...]
) -> frozenset[str]:
    """The model refs this runtime-enabled provider permits.

    The provider profile declares what the provider exposes. The runtime config
    entry may **narrow** that set; it may not widen it. An entry that lists no
    models narrows nothing, so the profile's declaration stands.

    Narrowing is the only direction config is allowed to move: config selects and
    constrains, it never redefines what a provider is (AI-02 D-1).
    """
    declared = frozenset(profile.model_refs)
    if not entry_models:
        return declared
    return declared & frozenset(str(ref) for ref in entry_models)


def bind_codex_model(
    model_ref: object,
    *,
    config: ProviderConfig,
    providers: Mapping[str, ProviderProfile],
    models: Mapping[str, ModelProfile],
) -> CodexBinding:
    """Validate one explicit binding, or refuse.

    Every check is a refusal with its own reason, because "the backend would not
    build" is not actionable and "runtime config does not enable mimo" is.
    """
    try:
        parsed = ModelRef.parse(model_ref)
    except ProfileError as exc:
        raise CodexBindingError(f"model_ref is malformed: {exc}") from exc

    # A bare model id, a display name or a free-form string never reaches this
    # point: ModelRef.parse rejects anything that is not `<provider>/<model>`.
    if parsed.provider_id != CODEX_PROVIDER_ID:
        raise CodexBindingError(
            f"AI-09 v1 serves provider {CODEX_PROVIDER_ID!r}; "
            f"model_ref {parsed!s} names {parsed.provider_id!r}"
        )

    if str(parsed) not in SUPPORTED_MODEL_REFS:
        raise CodexBindingError(
            f"{parsed!s} is not a supported AI-09 model ref; the scope is "
            f"exactly {list(SUPPORTED_MODEL_REFS)}"
        )

    profile = providers.get(CODEX_PROVIDER_ID)
    if profile is None:
        raise CodexBindingError(
            f"provider {CODEX_PROVIDER_ID!r} has no profile under providers/; "
            "a provider that is not registered cannot be bound"
        )

    entry = config.providers.get(CODEX_PROVIDER_ID)
    if entry is None:
        # The profile exists and the provider is registered. Neither is
        # enablement, and this is the branch where that distinction bites.
        raise CodexBindingError(
            f"provider {CODEX_PROVIDER_ID!r} has no runtime config entry; "
            "profile existence is not runtime enablement"
        )

    if entry.reserved:
        raise CodexBindingError(
            f"provider {CODEX_PROVIDER_ID!r} is a reserved extension point; a "
            "reserved provider is never enabled and never invoked"
        )

    if not entry.enabled:
        raise CodexBindingError(
            f"provider {CODEX_PROVIDER_ID!r} is not enabled by runtime config; "
            "a provider without an explicit `enabled: true` is disabled"
        )

    if str(parsed) not in _permitted_refs(profile, config, entry.models):
        raise CodexBindingError(
            f"{parsed!s} is not permitted by runtime-enabled provider "
            f"{CODEX_PROVIDER_ID!r}"
        )

    if str(parsed) not in models:
        raise CodexBindingError(
            f"{parsed!s} has no model profile; a binding names a model the "
            "registry can resolve"
        )

    return CodexBinding(
        provider_id=CODEX_PROVIDER_ID,
        model_ref=str(parsed),
        model_id=parsed.model_id,
    )
