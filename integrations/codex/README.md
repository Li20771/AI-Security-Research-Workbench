# integrations/codex

AI-09's single composition boundary: it wires AI-08's frozen `CodexBackend` seam
to the `mimo` provider through AI-02's frozen normalized invocation boundary.

Contract: [`docs/AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md`](../../docs/AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md)

## Why this directory exists

Two layers must not know about each other:

```text
agents/      AI-08's provider-neutral Agent layer. Its own boundary tests assert that
             no module here names Invoker, ModelProfile, base_url or endpoint.
providers/   AI-02's model layer. It knows nothing about Agents or executions.
```

Composing them needs a third place to live. That is `integrations/`, a Workbench
core layer reached as a namespace package — no `__init__.py`, exactly as
`routing/` and `agents/` are.

The dependency runs one way:

```text
integrations/  ->  agents/      ALLOWED
integrations/  ->  providers/   ALLOWED, through an explicit allowlist
integrations/  ->  plugins.context              ALLOWED
integrations/  ->  routing, tools, plugins.evidence, os, socket, urllib,
                   requests, httpx, HttpTransport   FORBIDDEN

agents/     -/->  integrations/   FORBIDDEN
providers/  -/->  integrations/   FORBIDDEN
```

`scripts/ci/layer0_policy.py`'s `check_ai09_integration_layer()` enforces all of
it, and `tests/integrations/test_boundaries.py` proves the gate is not vacuous.

## What is here

```text
binding.py     model binding and runtime enablement (§5.3, §6, §11)
backend.py     MimoCodexBackend — the concrete CodexBackend (§8, §12, §17, §19)
composition.py the composition root: builds the credential-bearing InvocationContext
               and the Invoker, then hands the backend only that
reference.py   the sha256 provenance digest and its canonical inputs (§19.2.1)
errors.py      the integration-layer error taxonomy
```

## The execution path

```text
CodexBody
    |
    v
MimoCodexBackend.produce(agent_id=, request=, context=)      AI-08's signature, verbatim
    |
    v
InvocationRequest
    |
    v
providers.invocation.Invoker.invoke                          the ONLY path to a provider
    |
    v
capability gate -> credential resolution -> protocol adapter -> injected Transport
```

## What it will not do

```text
no default model          a caller binds one of the two supported refs explicitly
no fallback               binding `flash` never yields `pro`
no inference              the model is never derived from AgentId, task text or config
no context egress         only `request.task` becomes the user message
no credential access      the provider layer resolves it; `os` is not even imported
no transport selection    the Transport is injected by the composition root
no retry                  max_retries = 0, attempts == 1
no artifact store         the reference is a digest, and it locates nothing
no capability promotion   every shipped capability stays UNKNOWN
```

## Construction: two sides of one boundary

`composition.py` is the composition root. It assembles the credential-bearing
`InvocationContext` and the `Invoker` over it, and hands the backend only that:

```python
# composition.py — the only place a credential source is assembled
context = InvocationContext(
    providers=..., models=...,
    transport=transport,            # INJECTED by the caller
    transport_settings_for=...,
    environ=environ,                # the credential environment, stays here
)
backend = MimoCodexBackend(
    model_ref="mimo/mimo-v2.6-pro", # explicit, validated, immutable
    config=provider_config,         # runtime enablement authority
    providers=..., models=...,      # AI-02's registries, for binding validation
    invoker=Invoker(context),
)
```

The backend's constructor has **no** `environ`, `transport` or
`transport_settings` parameter, and its source names `environ` nowhere.
`check_ai09_integration_layer()` asserts that: only `composition.py` may bind an
environment mapping, and every other module in the layer is refused if it does.

Holding the mapping *is* holding the credential — even if no key is ever read —
so the boundary is drawn at the module that assembles the provider-side context,
not at the call that reads a variable.

A provider that runtime config does not explicitly enable is refused at
construction, and the backend is not built. **Profile existence is not runtime
enablement.**

## Live

Nothing in this package contacts a provider. The default path injects the shared
fake transport, and `providers/http_transport.py` is referenced nowhere under
`integrations/`. A live observation, if one is ever wanted, goes through AI-02's
existing `LiveVerifier` / `ProbeAuthorisation` path and promotes nothing on its
own.
