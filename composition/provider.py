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

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from providers.config import ProviderConfig
from providers.model_profile import ModelProfile
from providers.profile import ProviderProfile

from agents.body import AgentBody, OfflineBody
from agents.codex.body import CodexBody, OfflineCodexBackend
from agents.toolcall import ToolInvocation
from agents.vocabulary import AgentId

from integrations.codex.backend import CODEX_INVOCATION_TIMEOUT_MS, MimoCodexBackend

from composition.errors import ProviderRefused

__all__ = [
    "BodyFactory",
    "ExecutionBinding",
    "codex_body",
    "codex_body_factory",
    "enabled_provider_ids",
    "offline_body_factory",
    "offline_codex_body",
]


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    """What a body factory built, and which model it was built FOR.

    ```text
    model_ref is a string   the body was built for that model, and for a
                            provider-backed body the value comes from AI-09's
                            VALIDATED binding — the ref the backend will invoke
    model_ref is None       the body invokes no model at all (the offline path)
    ```

    This is the value the composition checks against the Router's selection, and
    it is the only thing that can: `RouterDecision.selected` says what was
    SELECTED, and this says what was BUILT. A composition that reported the first
    as if it were the second would be asserting a connection it never made.
    """

    body: AgentBody
    model_ref: str | None = None


#: What `run_task` calls AFTER the Router has selected. It is handed the selected
#: model ref and the Agent identity the execution request carries, and it returns
#: the body to run plus the model that body was built for.
BodyFactory = Callable[..., ExecutionBinding]


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


def _provider_backend(
    *,
    model_ref: object,
    config: ProviderConfig,
    providers: Mapping[str, ProviderProfile],
    models: Mapping[str, ModelProfile],
    invoker: Any,
    timeout_ms: int,
) -> MimoCodexBackend:
    """AI-09's backend over one validated, runtime-enabled binding.

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
        return MimoCodexBackend(
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
        raise ProviderRefused(f"the Codex provider binding was refused: {exc}") from exc


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
    """Build the Codex body over one validated, runtime-enabled binding."""
    backend = _provider_backend(
        model_ref=model_ref,
        config=config,
        providers=providers,
        models=models,
        invoker=invoker,
        timeout_ms=timeout_ms,
    )
    return CodexBody(backend=backend, plan=tuple(plan))


# ---------------------------------------------------------------------------
# Body factories: what `run_task` calls AFTER the Router has selected (§22.1 B1+B2)
# ---------------------------------------------------------------------------


def codex_body_factory(
    *,
    config: ProviderConfig,
    providers: Mapping[str, ProviderProfile],
    models: Mapping[str, ModelProfile],
    invoker: Any,
    plan: Sequence[ToolInvocation] = (),
    timeout_ms: int = CODEX_INVOCATION_TIMEOUT_MS,
) -> BodyFactory:
    """A factory that binds THE SELECTED model, after the selection happens.

    ```text
    RouterRequest -> evaluate() -> RouterDecision(selected = X)
                                        |
                                        v   X is passed HERE, as an argument
                              codex_body_factory's build()
                                        |
                                        v
                              MimoCodexBackend(model_ref = X, ...)   AI-09 validates X
                                        |
                                        v
                              ExecutionBinding(model_ref = the BOUND ref)
    ```

    The composition never holds a pre-built provider body: the body does not exist
    until a selection exists, and the model it is built for is the one that was
    selected. A ref the Router did not select can only reach this factory by a
    caller passing it, and the composition refuses a binding that names a
    different model than the selection did (§22.1 B1+B2).

    The invoker is still the caller's: this factory constructs none, reads no
    credential and opens no client — building one is what this phase does not do
    (§22.1 B2).
    """

    def build(*, model_ref: str, agent_id: AgentId) -> ExecutionBinding:
        if agent_id is not AgentId.CODEX:
            raise ProviderRefused(
                f"the provider-backed body serves {AgentId.CODEX.value!r} and the "
                f"Router selected an execution for {agent_id.value!r}; a provider "
                "binding is not a body for an Agent it does not serve (§7)"
            )
        backend = _provider_backend(
            model_ref=model_ref,
            config=config,
            providers=providers,
            models=models,
            invoker=invoker,
            timeout_ms=timeout_ms,
        )
        return ExecutionBinding(
            body=CodexBody(backend=backend, plan=tuple(plan)),
            # From AI-09's VALIDATED binding, not from the argument: this is what
            # the backend will actually invoke.
            model_ref=backend.binding.model_ref,
        )

    return build


def offline_body_factory() -> BodyFactory:
    """The offline factory. It invokes NO model, and says so.

    ```text
    FROZEN: an offline body is an execution with no provider. It is NOT a model
            invocation, and a composed run using it MUST NOT be described as
            having executed the model the Router selected.
    ```

    It still runs AFTER the selection, and still receives the selected ref — the
    Agent it builds a body for is the Agent the selection's request names. What it
    reports back is `model_ref=None`: the honest answer for a body that reaches no
    provider.
    """

    def build(*, model_ref: str, agent_id: AgentId) -> ExecutionBinding:
        if agent_id is AgentId.CODEX:
            return ExecutionBinding(
                body=CodexBody(backend=OfflineCodexBackend()), model_ref=None
            )
        if agent_id is AgentId.DSH:
            return ExecutionBinding(
                body=OfflineBody(agent_id=AgentId.DSH), model_ref=None
            )
        raise ProviderRefused(
            f"no offline body serves {agent_id!r}; the AgentId vocabulary is closed "
            "at two and this factory builds a body for the one the selection named"
        )

    return build
