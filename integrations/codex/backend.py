"""The concrete Codex backend: Codex -> `mimo` through AI-02's invocation boundary.

Construction **is** the composition point. Everything this backend needs is
supplied by its caller and nothing is discovered by this module:

```text
model_ref            one of the two supported refs, explicitly
config               runtime ProviderConfig — the enablement authority
providers / models   AI-02's registries
transport            INJECTED. This layer never constructs or selects one
transport_settings   runtime config (AI-02 §5.11)
environ              injected mapping for credential resolution, or None
```

```text
FROZEN: the only path to a provider is `providers.invocation.Invoker.invoke`.
FROZEN: the outbound natural-language content is `AgentExecutionRequest.task`
        alone, as exactly one user message.
FROZEN: a failure never produces a reference.
```

The seam is AI-08's, and its signature is used verbatim::

    produce(*, agent_id, request, context) -> str

`context` is read for exactly two things — workspace alignment, which is a
refusal, and nothing else. It is never serialised, never summarised, and never
turned into prompt text. The full `ContextResponse` stays in this process.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping

from plugins.context import ContextResponse
from plugins.context.errors import WorkspaceError
from plugins.context.workspace import canonical_root

from providers.config import ProviderConfig
from providers.invocation import (
    InvocationContext,
    InvocationRequest,
    Invoker,
    Message,
    MessageRole,
    RequestMetadata,
)
from providers.model_profile import ModelProfile
from providers.profile import ProviderProfile
from providers.protocol import Transport
from providers.transport import TransportSettings

from agents.request import AgentExecutionRequest
from agents.vocabulary import AgentId

from integrations.codex.binding import CodexBinding, bind_codex_model
from integrations.codex.errors import CodexBindingError, CodexWorkspaceMismatch
from integrations.codex.reference import reference_for

__all__ = [
    "CODEX_INVOCATION_TIMEOUT_MS",
    "CODEX_PURPOSE",
    "MimoCodexBackend",
]

#: A bounded deadline, always. There is no unbounded call (contract §17), and the
#: effective deadline is the stricter of this and the runtime config ceiling.
CODEX_INVOCATION_TIMEOUT_MS = 30_000

#: Local attribution only. `RequestMetadata` is never sent to a provider
#: (AI-02 §7.4), so this names the caller's purpose without disclosing it.
CODEX_PURPOSE = "codex-provider-invocation"


def _require_positive_ms(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CodexBindingError(f"{name} must be whole milliseconds")
    if value <= 0:
        raise CodexBindingError(
            f"{name} must be > 0; a non-positive timeout is not an unbounded one"
        )
    return value


class MimoCodexBackend:
    """AI-08's `CodexBackend`, served by `mimo` through AI-02.

    Satisfies `agents.codex.body.CodexBackend` structurally: `backend_id` plus a
    `produce` of exactly the frozen shape. AI-08 is not modified to accept it,
    and this class adds no parameter to `produce`.
    """

    def __init__(
        self,
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
    ) -> None:
        # Binding first: a backend that cannot show runtime enablement is not
        # built, so no code path below can reach a provider without it.
        self._binding: CodexBinding = bind_codex_model(
            model_ref, config=config, providers=providers, models=models
        )
        self._timeout_ms = _require_positive_ms(timeout_ms, "timeout_ms")

        if not isinstance(transport, Transport):
            raise CodexBindingError(
                "transport must be an AI-02 Transport; it is injected by the "
                "composition root and never constructed here"
            )
        if not isinstance(transport_settings, TransportSettings):
            raise CodexBindingError(
                "transport_settings must be AI-02's TransportSettings"
            )

        self._context = InvocationContext(
            providers=providers,
            models=models,
            transport=transport,
            # One provider, one ceiling. The invocation deadline is folded into
            # it by `effective_transport_settings`, so a request can tighten the
            # budget but never widen it.
            transport_settings_for=lambda _provider_id: transport_settings,
            environ=environ,
        )
        kwargs: dict[str, Any] = {} if clock is None else {"clock": clock}
        self._invoker = Invoker(self._context, **kwargs)

    # -- CodexBackend -----------------------------------------------------

    @property
    def backend_id(self) -> str:
        return f"codex-{self._binding.provider_id}-{self._binding.model_id}"

    @property
    def binding(self) -> CodexBinding:
        """The validated, immutable binding this backend was built with."""
        return self._binding

    def produce(
        self,
        *,
        agent_id: AgentId,
        request: AgentExecutionRequest,
        context: ContextResponse,
    ) -> str:
        """One invocation, one reference. Never raw output.

        `COMPLETED` is not this method's to claim: `CodexBody` reports it
        unconditionally, which is why every non-success outcome raises instead of
        returning something that could be read as an answer.
        """
        self._require_aligned_workspace(request, context)

        invocation = self._build_invocation(agent_id, request)
        result = self._invoker.invoke(invocation)

        # `reference_for` refuses a non-success and a truncated success, so the
        # value returned here is always a digest of a complete, normalized
        # response — never of a raw payload, and never fabricated.
        return reference_for(result)

    # -- internals --------------------------------------------------------

    @staticmethod
    def _require_aligned_workspace(
        request: AgentExecutionRequest, context: ContextResponse
    ) -> None:
        """Refuse when the context is not the execution's own workspace (§12.4).

        A mismatch is a refusal, not a warning: a reference produced over
        misaligned inputs would attribute one workspace's work to another. AI-03
        owns path canonicalisation and this uses it rather than reimplementing
        it; `resolve_workspace` stores exactly `canonical_root(...).as_posix()`,
        so the comparison is between two AI-03 canonical forms.
        """
        try:
            execution_root = canonical_root(request.workspace_root).as_posix()
        except WorkspaceError as exc:
            raise CodexWorkspaceMismatch(
                f"the execution workspace could not be resolved: {exc}"
            ) from exc

        context_root = context.workspace.workspace_root
        if execution_root != context_root:
            raise CodexWorkspaceMismatch(
                "the context is not the execution's workspace: "
                f"execution={execution_root!r} context={context_root!r}"
            )

    def _build_invocation(
        self, agent_id: AgentId, request: AgentExecutionRequest
    ) -> InvocationRequest:
        """The whole of AI-09's provider egress (contract §12.2).

        Layer A is one user message carrying the declared task, verbatim, and
        nothing else. Layer B is the protocol's own structural fields, which the
        adapter composes from the bound model and the defaults below — no tool
        schema and no `response_format`, because this invocation requests
        neither.

        `context` is deliberately not a parameter. There is no argument through
        which a `ContextResponse` could reach the payload, which is a stronger
        guarantee than a rule saying it must not.
        """
        return InvocationRequest(
            model_ref=self._binding.model_ref,
            messages=(Message(role=MessageRole.USER, content=request.task),),
            timeout_ms=self._timeout_ms,
            metadata=RequestMetadata(agent=str(agent_id), purpose=CODEX_PURPOSE),
        )
