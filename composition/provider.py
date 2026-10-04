"""AI-14-B / B2 — Agent -> Provider / model invocation (§22.1, §5.2).

```text
agents.runtime.run_execution(..., body=...)
        |
        v
agents.codex.body.CodexBody            <- AI-08's body, unmodified
        |
        v
CodexBackend                           <- the seam AI-08-B defined and stopped at
        |
        +--> OfflineCodexBackend       the offline path: no provider at all
        |
        +--> MimoCodexBackend          AI-09's binding, over a caller-supplied Invoker
                    |
                    v
             providers.invocation.Invoker.invoke()   <- the ONE model-call boundary
```

### What this module may and may not do

```text
MAY      build a `CodexBody` over a runtime-enabled, validated binding
MAY      build the offline body, which reaches nothing
MAY NOT  construct an `Invoker`, a `Transport`, a credential or a `CredentialRef`
MAY NOT  read a credential, an environment secret or an endpoint
MAY NOT  retry, fall back, escalate or re-select when an invocation is refused
MAY NOT  treat a constructed binding — or a wired path — as capability evidence
```

### Wiring is not verification

```text
FROZEN: a binding proves runtime ENABLEMENT and nothing else. Every shipped model
        capability is UNKNOWN, and the invocation gate refuses a call that needs a
        capability which is not VERIFIED (providers/invocation.py,
        BlockCode.CAPABILITY_NOT_VERIFIED). Connecting this seam MUST NOT change
        that, and no statement about this path may promote UNKNOWN to AVAILABLE.
FROZEN: live provider verification is NOT_RUN and is not this phase's to perform
        (§20). The composition performs no provider call, holds no credential and
        starts no network client. A deployment that wants a live call supplies an
        `Invoker` built outside this repository's composition, and the refusal it
        receives is the gate working.
```

### The invoker is a parameter, and that is the design

`MimoCodexBackend` requires AI-02's `Invoker` and refuses test doubles by type.
Building one needs a transport, and a transport is a network client — which the
composition must not create on a caller's behalf (and cannot, without a
credential it must not read). So the caller supplies it, exactly as AI-09's
docstring says an "external composition root" would.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from providers.config import ProviderConfig
from providers.model_profile import ModelProfile
from providers.profile import ProviderProfile

from agents.body import AgentBody
from agents.codex.body import CodexBody, OfflineCodexBackend
from agents.toolcall import ToolInvocation

from integrations.codex.backend import CODEX_INVOCATION_TIMEOUT_MS, MimoCodexBackend

from composition.errors import ProviderRefused

__all__ = ["codex_body", "enabled_provider_ids", "offline_codex_body"]


def enabled_provider_ids(config: ProviderConfig) -> frozenset[str]:
    """The providers runtime configuration ENABLES, for the Router's answer.

    AI-07 fails closed on an omitted set, and AI-02 ships every provider
    `enabled: false`. This is the one place the two facts are put together, so a
    caller cannot pass `None` by accident and turn "no provider is enabled" into
    "do not check".
    """
    return frozenset(
        provider_id
        for provider_id, entry in config.providers.items()
        if entry.enabled and not entry.reserved
    )


def offline_codex_body(*, plan: Sequence[ToolInvocation] = ()) -> CodexBody:
    """The offline path. No provider, no credential, no network.

    `OfflineCodexBackend` is deterministic and performs no inference. This is the
    body every offline composition and every test uses, and it is the reason the
    seam is usable without a credential at all.
    """
    return CodexBody(backend=OfflineCodexBackend(), plan=tuple(plan))


def codex_body(
    *,
    model_ref: object,
    config: ProviderConfig,
    providers: Mapping[str, ProviderProfile],
    models: Mapping[str, ModelProfile],
    invoker: Any,
    plan: Sequence[ToolInvocation] = (),
    timeout_ms: int = CODEX_INVOCATION_TIMEOUT_MS,
) -> AgentBody:
    """Build the Codex body over one validated, runtime-enabled binding.

    Every refusal below is AI-09's own and is raised BEFORE any backend exists, so
    no code path from here can reach a provider without enablement:

    ```text
    a model ref outside AI-09's scope          refused by the binding
    a provider that is not registered          refused by the binding
    no runtime config entry                    refused — profile != enablement
    a reserved provider                        refused — never enabled, never invoked
    `enabled: false`                           refused
    a model with no profile                    refused
    an invoker that is not AI-02's             refused by MimoCodexBackend
    ```

    This function does not catch any of them, and does not translate one into a
    different model or a default: a refused binding is a STOP.
    """
    try:
        backend = MimoCodexBackend(
            model_ref=model_ref,
            config=config,
            providers=providers,
            models=models,
            invoker=invoker,
            timeout_ms=timeout_ms,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised as a composition refusal
        # Named rather than swallowed: the caller gets a `ProviderRefused` whose
        # cause is AI-09's own error, so the reason ("not enabled", "not in
        # scope") survives instead of becoming "the body would not build".
        raise ProviderRefused(
            f"the Codex provider binding was refused: {exc}"
        ) from exc

    return CodexBody(backend=backend, plan=tuple(plan))
