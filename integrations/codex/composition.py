"""The composition root for the Codex integration.

This module exists to keep one thing in exactly one place: the credential-bearing
`InvocationContext`.

```text
composition root
    |
    +--> InvocationContext   provider registry + model registry
    |                        + injected Transport
    |                        + credential environment
    |
    +--> Invoker(context)
    |
    v
MimoCodexBackend             receives the Invoker, and nothing credential-bearing
    |
    v
existing Invoker.invoke()
```

Contract §13: *the credential is resolved by the provider layer at invocation
time, and the integration layer never sees it, holds it, or passes it.* A backend
that accepted the environment mapping and forwarded it would be holding it, so
the mapping stops here and the backend receives only the boundary that already
owns it.

This is also where the `Transport` is injected, which is what keeps
`providers/http_transport.py` unreachable from the rest of the layer: the caller
supplies a transport, this function wires it, and no other module names one.

Nothing here reads an environment variable. The mapping is a parameter, supplied
by whoever owns the process environment — the composition root is a wiring point,
not a reader.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from providers.config import ProviderConfig
from providers.invocation import InvocationContext, Invoker
from providers.model_profile import ModelProfile
from providers.profile import ProviderProfile
from providers.protocol import Transport
from providers.transport import TransportSettings

from integrations.codex.backend import CODEX_INVOCATION_TIMEOUT_MS, MimoCodexBackend

__all__ = ["build_mimo_codex_backend"]


def build_mimo_codex_backend(
    *,
    model_ref: str,
    config: ProviderConfig,
    providers: Mapping[str, ProviderProfile],
    models: Mapping[str, ModelProfile],
    transport: Transport,
    transport_settings: TransportSettings,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], float] | None = None,
    timeout_ms: int = CODEX_INVOCATION_TIMEOUT_MS,
) -> MimoCodexBackend:
    """Assemble the invocation boundary, then hand the backend only that.

    `environ` is the credential environment the provider layer's resolver reads
    from. It is kept on this side of the boundary: the returned backend has no
    reference to it and no parameter through which it could be given one.
    """
    context = InvocationContext(
        providers=providers,
        models=models,
        transport=transport,
        # One provider, one ceiling. The invocation deadline is folded into it by
        # `effective_transport_settings`, so a request can tighten the budget but
        # never widen it.
        transport_settings_for=lambda _provider_id: transport_settings,
        environ=environ,
    )
    kwargs: dict[str, Any] = {} if clock is None else {"clock": clock}
    invoker = Invoker(context, **kwargs)

    return MimoCodexBackend(
        model_ref=model_ref,
        config=config,
        providers=providers,
        models=models,
        invoker=invoker,
        timeout_ms=timeout_ms,
    )
