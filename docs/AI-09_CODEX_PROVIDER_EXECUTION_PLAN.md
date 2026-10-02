# AI-09 — Codex Provider Integration — Execution Plan

> Status: **FROZEN** (AI-09-A, 2026-10-02)
> Phase: AI-09 — Domestic Models for Codex
> Sub-phase: **AI-09-A — Contract / Execution Plan / Freeze**
> Base: `main` @ `edb7dfc82ce51123482ac357fb9319dca2fa0d9a`
> Rule: This document defines the contract. AI-09-B implements against it. Nothing in AI-09
> may deviate from a frozen contract without amending this document first (§26).

---

## 0. The five responsibilities — read this first

```text
Router selects.
Agent executes.
Provider invokes.
Guard authorizes tool use.
Evidence records admitted facts.
```

These are five distinct responsibilities owned by five different phases. AI-09 exists to connect
**Agent executes** to **Provider invokes** and nothing else.

```text
FROZEN: AI-09 MUST NOT merge any two of these responsibilities.
FROZEN: AI-09 MUST NOT move one of them into another layer to make wiring easier.
```

The whole of AI-09 is one narrow seam: a Codex Agent execution may reach a real provider through
AI-02's existing normalized invocation boundary, without either layer learning about the other.

---

## 1. Normative language

```text
MUST       a requirement. AI-09-B that violates it is not conformant.
MUST NOT   a prohibition.
FROZEN     binding, and changes only by amendment (§26).
DEFERRED   declared, and deliberately not decided here.
OPEN       named as unresolved, with a stated default.
```

---

## 2. Architectural purpose and identity

### 2.1 What AI-09 is

AI-09 wires the Codex Agent's already-frozen provider seam to a real, already-registered provider,
using the provider layer that already exists.

```text
AI-09 is a Workbench CORE INTEGRATION LAYER.
AI-09 is NOT a DSH plugin.
AI-09 is NOT a new provider.
AI-09 is NOT a new invocation API.
AI-09 is NOT a Router feature.
```

### 2.2 What AI-09 is not asked to build

Every mechanism AI-09 needs already exists and is already frozen. AI-09 adds **no** transport, **no**
protocol adapter, **no** credential mechanism, **no** capability probe and **no** invocation
boundary. It adds a composition, an explicit model binding, and the tests that observe the result.

```text
FROZEN: AI-09-B MUST NOT reimplement anything AI-02 already ships.
FROZEN: AI-09-B MUST NOT add a second provider invocation API.
```

### 2.3 The roadmap requirement this contract answers

`docs/MASTER_ROADMAP.md` §AI-09, verbatim:

```text
目标：利用 Codex 的 provider abstraction 接入其他 OpenAI-compatible API。

要求：
- provider profile 独立
- secret 不入 Git
- model capability 记录
- tool calling compatibility test
- structured output compatibility test
- timeout / retry / context handling test
```

Each requirement is answered by a section of this document: provider profile independence (§5),
secrets (§13), capability records (§14), tool calling (§15), structured output (§16), timeout and
retry and context (§12, §17, §18).

---

## 3. What already exists — and what AI-09 therefore does not build

| Mechanism | Where it already lives | AI-09's relationship |
| --- | --- | --- |
| provider profile (identity, protocol, endpoint, credential ref, models) | `providers/mimo/provider.yaml` | consumed unchanged |
| model profile (limits, modality, capabilities, provenance) | `providers/mimo/models/*.yaml` | consumed unchanged |
| credential reference grammar + resolver (`env:` only) | `providers/credential.py` | consumed unchanged |
| protocol adapter (`openai_compatible_chat`) | `providers/protocol/openai_compatible_chat.py` | consumed unchanged |
| transport interface | `providers/protocol/base.py` | **injected**, not selected (§10.4) |
| the one concrete transport (live-only) | `providers/http_transport.py` | untouched; see §20.4 |
| normalized invocation (`Invoker.invoke`) | `providers/invocation.py` | **the only call path** (§8) |
| capability gate | `providers/invocation.py` `_check_capabilities` | obeyed, never bypassed (§14) |
| error taxonomy, redaction, metrics, pricing | `providers/{errors,redaction,metrics,pricing}.py` | untouched |
| opt-in live verification + probe authorisation | `providers/live_verification.py` | reused for compatibility observation (§20) |
| Agent identity, execution contract, result grammar | `agents/` | consumed unchanged (§19) |
| `CodexBackend` seam | `agents/codex/body.py` | **implemented against**, signature unchanged (§9) |
| Router | `routing/` | untouched, and not on the execution path (§7) |

```text
FROZEN: AI-09-B MUST NOT modify providers/, agents/, routing/, plugins/ or tools/.
FROZEN: AI-09-B's only production code is a new integration layer (§10).
```

---

## 4. Scope

### 4.1 In scope for AI-09

```text
the AI-09 contract (this document)                     AI-09-A
a single Codex integration / composition layer          AI-09-B
a concrete CodexBackend bound to one explicit model_ref AI-09-B
the offline compatibility tests for that binding        AI-09-B
the tool-calling and structured-output compatibility observation, reusing AI-02's machinery
the AI-09 Layer 0 boundary check                        AI-09-B
the AI-09 evidence record and status updates            AI-09-B
```

### 4.2 Out of scope for AI-09

```text
any provider-side change                       AI-02 owns providers/
any Agent identity or execution change         AI-08 owns agents/
any routing change or routing integration      AI-07 owns routing/
tool authorization or execution                AI-04 + AI-06 own it
Evidence admission or storage                  AI-05 owns it
Context resolution                             AI-03 owns it
retry, resume, cancellation, long-running      AI-13 owns it
cross-agent comparison, second opinion         AI-10 owns it
benchmark scoring                              AI-11 owns it
routing v2 fallback / escalation               AI-12 owns it
SecurityLab, in any form                       not reachable from this repository
```

---

## 5. Target provider

### 5.1 Concrete provider: `mimo`

```text
FROZEN: AI-09 v1 integrates exactly one provider identity: `mimo`.
FROZEN: AI-09 v1 uses the already-registered profile `providers/mimo/provider.yaml`.
FROZEN: AI-09 v1 creates NO third provider identity.
```

The profile is consumed exactly as it stands today:

```text
provider_id     mimo
display_name    MiMo
protocol        openai_compatible_chat / v1
endpoint        base_url https://api.xiaomimimo.com/v1 + path_template /chat/completions
credential.ref  env:MIMO_API_KEY
models          mimo/mimo-v2.6-pro, mimo/mimo-v2.6-flash
status          every fact DECLARED; nothing VERIFIED
```

### 5.2 `providers/openai-compatible/` stays reserved

```text
FROZEN: `providers/openai-compatible/` remains a RESERVED, DISABLED, UNIMPLEMENTED
        extension point. AI-09 v1 does not implement it.
FROZEN: the runtime config entry `openai-compatible` keeps `reserved: true` and
        `enabled: false`.
FROZEN: AI-09-B MUST NOT create `providers/openai-compatible/provider.yaml`.
```

The reasons are recorded here so a later reader does not have to reconstruct them:

1. AI-02 already froze `deepseek` and `mimo` as the two real providers, and the generic
   `openai-compatible` slot as a placeholder (`providers/registry.py`, `providers/validate.py`
   `RESERVED_PROVIDERS`).
2. The concrete domestic-model target of this phase already has a real, independent `mimo`
   profile. Nothing is missing.
3. Creating a third provider identity merely to occupy a reserved directory would add an
   identity with no independent profile review behind it, and would blur the attribution rule
   that a shared protocol family is not a shared provider.
4. AI-02's live allowlist and validation both assume two providers. Enabling a third is a
   boundary change with no requirement driving it.

---

## 6. Target models

```text
FROZEN: AI-09 v1 supports exactly two model refs:
            mimo/mimo-v2.6-pro
            mimo/mimo-v2.6-flash
FROZEN: a concrete backend instance binds exactly ONE of them, explicitly (§11).
FROZEN: there is no default model.
```

```text
FROZEN: AI-09 MUST NOT derive a model from an AgentId.
FROZEN: AI-09 MUST NOT derive a model from a display_name.
FROZEN: AI-09 MUST NOT derive a model from a free-form string, a prefix match or a
        "closest available" search.
FROZEN: AI-09 MUST NOT fall back from one model ref to the other.
FROZEN: AI-09 MUST NOT let a caller widen the supported set at runtime.
```

The model list has no ordering semantics and none may be introduced (AI-02 D-13: *no model is a
default model*). `mimo-v2.6-pro` is not "the good one" and `mimo-v2.6-flash` is not "the fallback";
they are two identities, and which one an execution used is an explicit, recorded choice.

---

## 7. Protocol

```text
FROZEN: AI-09 reuses the existing `openai_compatible_chat` protocol family.
FROZEN: AI-09 MUST NOT add a second HTTP, chat or completion protocol.
FROZEN: AI-09 MUST NOT add a second protocol adapter or a second adapter registry.
```

The adapter is selected by the provider profile's declared family through the existing
`adapter_for(profile.protocol.family)` path. AI-09 never names an adapter.

---

## 8. Invocation path

### 8.1 The one path

```text
CodexBody
    |
    v
CodexBackend                     (AI-08's seam; signature unchanged)
    |
    v
AI-09 integration backend        (new; binds a model_ref; builds a request)
    |
    v
InvocationRequest  ->  Invoker.invoke(...)     (providers.invocation — the ONLY invocation API)
    |
    v
existing provider / profile / credential / protocol / transport path
```

```text
FROZEN: `providers.invocation.Invoker.invoke` is the only way AI-09 reaches a provider.
FROZEN: AI-09 MUST NOT construct a TransportRequest, an HTTP request, a URL or a header itself.
FROZEN: AI-09 MUST NOT call the protocol adapter directly.
FROZEN: AI-09 MUST NOT open a socket, spawn a process, or import an HTTP client.
```

### 8.2 The Router is not on this path

```text
FROZEN: the AI-09 execution path contains no Router step.
FROZEN: AI-09 MUST NOT import `routing`.
FROZEN: AI-09 MUST NOT consult a rule set, a RouterDecision, or `agent_hint`.
```

---

## 9. Router boundary (AI-07 is unchanged)

```text
FROZEN: `RouterRequest` is unchanged.
FROZEN: `RouterDecision` is unchanged.
FROZEN: `RoutingOutcome` is unchanged.
FROZEN: `routing/` MUST NOT import provider execution, and MUST NOT gain an execution step.
FROZEN: the Router MUST NOT execute a provider call.
FROZEN: `RouterDecision.selected` remains a routing OUTPUT. It is not an instruction to
        execute anything.
FROZEN: `agent_hint` remains a HINT. It is not resolved, and it does not select a model.
FROZEN: AI-09 v1 MUST NOT feed `RouterDecision.selected` into a CodexBackend, automatically
        or otherwise.
```

### 9.1 Recorded architecture gap (not fixed here)

```text
Today `RouterDecision.selected` has NO execution consumer. `routing.router.evaluate` is called
only by the Layer 0 policy check and by tests; no production path acts on a decision. Likewise
`routing.router.py` performs no provider call by design.
```

```text
RECORDED GAP: Router -> Provider execution coupling does not exist.
STATUS:       NOT FIXED BY AI-09. This is an architecture gap, not an AI-09 deliverable.
FROZEN:       AI-09 MUST NOT close this gap by wiring routing into the execution path.
```

Connecting routing to execution is a separate decision with its own contract, because it changes
who chooses a model — and model choice is currently an explicit, auditable act by a caller.

---

## 10. Backend physical boundary

### 10.1 Location

```text
FROZEN: AI-09-B creates ONE new top-level integration layer:

            integrations/
                codex/            <- AI-09 v1's single composition boundary

FROZEN: `integrations/` is a Workbench CORE layer, reached as a namespace package.
FROZEN: `integrations/__init__.py` MUST NOT exist, exactly as `routing/__init__.py` and
        `agents/__init__.py` must not exist.
FROZEN: `integrations/` is NOT a plugin and MUST NOT be created under `plugins/`.
```

### 10.2 Why here, and not somewhere else

Both neighbouring homes are closed by frozen contracts, not by preference:

```text
agents/codex/        CLOSED by AI-08. AI-08's own boundary tests assert that no module
                     under agents/ names Invoker, InvocationRequest, ModelProfile,
                     CapabilityName, CredentialRef, base_url or endpoint, that no
                     identifier contains "transport", and that no module reads
                     environ/getenv/SecretValue. Putting a real backend here would
                     require deleting AI-08's frozen boundary tests.

providers/           CLOSED by AI-02. providers/ is the provider/model layer. It knows
                     nothing about Agents, executions or AgentResult, and giving it
                     Agent runtime orchestration would invert the dependency the layer
                     split exists to create.
```

A composition of two layers that must not know about each other needs a third place to live. That
is `integrations/`.

### 10.3 Dependency direction — frozen

```text
integrations/  ->  agents/            ALLOWED   (AgentBody, CodexBackend, AgentExecutionRequest,
                                                 AgentId, ContextResponse via plugins.context)
integrations/  ->  providers/         ALLOWED   (Invoker, InvocationContext, InvocationRequest,
                                                 InvocationResult, Transport, ModelRef)
integrations/  ->  plugins/context    ALLOWED   (ContextResponse, read-only)
integrations/  ->  plugins/evidence   FORBIDDEN (AI-08 writes no EvidenceRecord; AI-09 does not
                                                 change that — §19.4)
integrations/  ->  routing/           FORBIDDEN (§9)
integrations/  ->  tools/             FORBIDDEN (tool execution is AI-08 + AI-06 + AI-04)
integrations/  ->  plugins/http_transport, socket, http, urllib, requests, httpx, aiohttp,
                   ftplib, smtplib, telnetlib, ssl, asyncio, multiprocessing, subprocess,
                   shutil            FORBIDDEN

agents/     -/->  integrations/       FORBIDDEN  (one-way)
providers/  -/->  integrations/       FORBIDDEN  (one-way)
routing/    -/->  integrations/       FORBIDDEN  (one-way)
```

```text
FROZEN: the integration layer depends on both sides; neither side depends on it.
FROZEN: the transport is INJECTED into the integration layer. AI-09 MUST NOT select one.
```

### 10.4 New Layer 0 boundary required

```text
REQUIRED (AI-09-B): a new `check_ai09_integration_layer()` in `scripts/ci/layer0_policy.py`,
asserting §10.3 structurally and the frozen non-goals of §21.
```

This follows the existing precedent: each phase that adds a core layer adds its own Layer 0 check
(AI-05, AI-06, AI-07 and AI-08 each did). `scripts/ci/layer0_policy.py` is shared CI
infrastructure.

```text
RECORDED GAP: AI-02's live-transport confinement guard ranges over the roots
              ("providers", "tests", "scripts") and therefore does NOT cover a new
              top-level package. AI-09-B's own Layer 0 check closes this for
              `integrations/` by forbidding `http_transport` there.
DO NOT:       AI-09-B MUST NOT modify AI-02's guard in `tests/unit/test_live_verification.py`
              to widen its roots. That file is an AI-02-owned artifact. Widening it is a
              separate, reviewed decision.
```

---

## 11. Model binding

```text
FROZEN: a concrete backend instance binds its `model_ref` explicitly at construction.
```

Conceptually, and only conceptually — this contract does not specify the implementation:

```text
backend(model_ref="mimo/mimo-v2.6-pro")
```

```text
FROZEN: the binding is validated at construction, not at call time:
        the ref parses, and it is one of §6's two supported refs.
FROZEN: constructing a backend with an unsupported, unregistered or malformed ref is an error.
FROZEN: the binding is immutable for the instance's lifetime.
FROZEN: `model_ref` is not a parameter of `produce` and MUST NOT become one — AI-08's
        signature is frozen (§10 does not reopen it).
FROZEN: the backend MUST NOT read a model from configuration, environment, the task text,
        the context, the AgentId, or a routing decision.
```

The binding is deliberately the *only* thing that decides which model answers. A caller that wants
the other model constructs the other backend. Nothing infers, substitutes or upgrades.

---

## 12. Context egress policy

This is the security centre of AI-09.

### 12.1 The risk being closed

`CodexBackend.produce` receives a `ContextResponse`. That type carries `facts`, `history`, `plans`,
`sources`, freshness, conflicts and workspace identity, and it has a `to_dict()`. Serialising it
and putting it in a prompt is one line of code, is the obvious thing to do, and would be an
**implicit bulk egress of workspace-scoped state to an external provider**.

```text
FROZEN: AI-09 v1 MUST NOT send the full ContextResponse, its `to_dict()`, or any
        wholesale serialisation of it, to a provider.
FROZEN: AI-09 v1 MUST NOT send any context ITEM (fact, history entry, plan, source record),
        in whole or in part, to a provider.
FROZEN: AI-09 v1 MUST NOT send freshness, conflicts, subject resolutions, or item metadata
        to a provider.
```

### 12.2 What the provider request may contain

```text
FROZEN: the outbound request body contains exactly:
            - the bound model's API model id
            - the declared task text from `AgentExecutionRequest.task`, as message content
            - protocol-required fields
        and nothing else.
FROZEN: `AgentExecutionRequest.task` is the caller's declared task. It is the only
        caller-supplied text that may leave the process.
FROZEN: `RequestMetadata` is LOCAL attribution. It is never sent (AI-02 §7.4).
```

### 12.3 What context may be used for

```text
FROZEN: `ContextResponse` may be used LOCALLY, and only for:
            - workspace-identity alignment (§12.4)
            - local attribution inputs to the produced reference digest (§19)
FROZEN: context metadata MUST NOT reach the request body, headers, URL or metadata payload.
```

### 12.4 Workspace alignment

```text
FROZEN: before producing a reference, the integration layer MUST verify that the context's
        workspace is the execution's workspace — the same canonical workspace root as
        `AgentExecutionRequest.workspace_root`.
FROZEN: a mismatch is a REFUSAL. The backend raises; it does not warn, repair or proceed.
FROZEN: AI-09 MUST NOT reimplement path canonicalisation. AI-03 already provides it.
```

### 12.5 Future context projection

```text
DEFERRED: sending any context to a model requires an explicit, bounded PROJECTION CONTRACT:
          a named subset, a declared purpose, a size bound, and its own review.
FROZEN: AI-09 v1 ships no projection, and therefore sends no context.
FROZEN: AI-09 MUST NOT modify AI-03, and MUST NOT introduce a second Context plugin.
```

---

## 13. Credential policy

```text
FROZEN: AI-09 reuses `CredentialRef`, `SecretValue` and `resolve()` unchanged.
FROZEN: AI-09 v1 uses the only supported scheme: `env:`.
FROZEN: AI-09 MUST NOT add a credential scheme.
FROZEN: AI-09 MUST NOT modify AI-02's credential grammar.
```

Forbidden, without exception:

```text
a credential literal in Git, in any file, including tests and documentation
an API key in a provider profile
an API key in a runtime config file
an API key in `InvocationRequest`
an API key in `AgentExecutionRequest`
an API key in `AgentResult`
an API key in a log line, an error message, a reference, or a digest input
```

```text
FROZEN: the credential is resolved by the provider layer at invocation time, from the
        profile's `credential.ref`. The integration layer never sees it, holds it, or
        passes it.
FROZEN: a missing or unsupported credential is a pre-flight refusal produced by the
        existing path, not an error the integration layer invents.
```

---

## 14. Capability truth boundary

### 14.1 The rule

```text
FROZEN: `UNKNOWN` is NOT `AVAILABLE`.
FROZEN: every shipped capability on both supported models is `UNKNOWN`, and AI-09 does not
        change that.
FROZEN: AI-09 MUST NOT promote a capability.
FROZEN: AI-09 MUST NOT write `VERIFIED` into a model profile.
FROZEN: AI-09 MUST NOT bypass, weaken, special-case or reimplement the capability gate.
FROZEN: a synthetic fixture MUST NOT move a capability out of `UNKNOWN`.
FROZEN: a passing test is not a capability claim.
```

### 14.2 What this means in practice

The ordinary Codex invocation is a **plain-text** call. It requires no gated capability, so it is
not refused — and it proves nothing about tool calling, structured output, streaming, reasoning or
prompt caching.

A call that requests a gated capability is refused by `providers/invocation.py`'s gate before any
transport activity, because no capability is `VERIFIED`. That refusal is correct behaviour and
AI-09 must not work around it.

### 14.3 Three things that must never be conflated

```text
A. OFFLINE PROTOCOL COMPATIBILITY
   Our normalization logic, exercised against synthetic payloads through a fake transport.
   Proves: our code maps a declared shape correctly.
   Proves nothing about any provider.

B. LIVE PROVIDER OBSERVATION
   An opt-in, manually dispatched probe through the existing LiveVerifier /
   ProbeAuthorisation mechanism.
   Produces: a dated observation and a CANDIDATE status for a human to review.

C. MODEL-PROFILE CAPABILITY TRUTH
   What `providers/mimo/models/*.yaml` asserts.
   Changes only by a separate, reviewed change to AI-02's profiles.
```

```text
FROZEN: test result != automatic capability promotion.
FROZEN: a live positive observation produced during AI-09 does NOT license rewriting AI-02's
        capability truth contract inside this phase.
FROZEN: if AI-09 produces a live observation, it is recorded as evidence. Promoting it is a
        separate reviewed act, by the existing AI-02 mechanism, in a separate change.
```

---

## 15. Tool-calling compatibility semantics

### 15.1 What is in scope

```text
IN SCOPE (AI-09): compatibility of the provider/transport boundary with tool calling:
    - the provider accepts a standard tool schema
    - the provider returns a normalized tool call
    - that call maps correctly into `InvocationResult.tool_calls`
```

### 15.2 What is out of scope

```text
OUT OF SCOPE (AI-09): a model-driven tool loop.
    - Codex deciding, from a model's tool call, to execute a tool
    - executing that tool
    - feeding the tool result back and continuing generation
```

```text
FROZEN: AI-09-B MUST NOT convert `CodexBody` into a model-driven tool loop.
FROZEN: tool execution remains AI-08 + AI-06 + AI-04's existing boundary. `CodexBody.plan`
        stays what it is: a declared, Guard-mediated invocation list that the body executes.
FROZEN: `agents/codex/body.py` is not modified by AI-09.
```

This is the difference between "can this provider round-trip a tool call at all" (a compatibility
question, AI-09's) and "should this Agent act on one" (an execution-policy question, not AI-09's).

---

## 16. Structured-output compatibility semantics

```text
FROZEN: AI-09's structured-output compatibility test covers `json_object` at minimum.
FROZEN: `json_object` and `json_schema` are NEVER treated as equivalent.
FROZEN: AI-02's structured-output semantics are preserved: `json_object` guarantees JSON but
        NOT schema conformance, and a consumer must validate rather than trust.
FROZEN: AI-09 MUST NOT assert that `json_schema` works. AI-02 records that wrapper shape as
        unverified for both providers, and nothing in AI-09 verifies it.
FROZEN: a JSON-looking string is not evidence of schema-enforced output, and MUST NOT be
        recorded as one.
```

If a `json_schema` observation is ever wanted, it is its own probe with its own evidence, by
amendment to this document — not an extension of the `json_object` result.

---

## 17. Timeout semantics

```text
FROZEN: every AI-09 invocation is bounded. There is no unbounded call.
FROZEN: `InvocationRequest.timeout_ms` is always set, and is always > 0.
FROZEN: the effective deadline is the stricter of the request deadline and the runtime
        config ceiling, composed by AI-02's existing `effective_transport_settings`.
        A request may TIGHTEN a budget; it may never widen one.
FROZEN: AI-09 MUST NOT pass `None`, `0`, infinity or a "no timeout" sentinel.
FROZEN: AI-09 MUST NOT add a second timeout subsystem. There is one.
```

This is the "timeout / context handling test" arm of the roadmap requirement: bounded timeout
(§17), no egress of context (§12), and the refusal on workspace mismatch (§12.4).

---

## 18. Retry semantics

```text
FROZEN: AI-09 v1 uses `max_retries = 0`.
FROZEN: AI-09 MUST NOT add a retry loop, a retry budget, a backoff, or a "try the other model"
        fallback at any layer it owns.
FROZEN: compatibility and error tests MUST explicitly assert `attempts == 1`.
```

```text
DEFERRED: real retry, resume, cancellation, checkpointing and failure classification remain
          AI-13's. AI-09 MUST NOT expand into AI-13.
```

The rationale is not thrift. A retry loop hides the flakiness a compatibility test exists to
observe, multiplies live cost, and would make `attempts` a lie. AI-02's `max_retries` field is
frozen for AI-13 to consume; AI-09 leaves it inert.

---

## 19. Output and reference boundary

### 19.1 `AgentResult` is not modified

```text
FROZEN: AI-08's `AgentResult` contract is unchanged.
FROZEN: no raw model output.
FROZEN: no raw prompt.
FROZEN: no raw tool argument.
FROZEN: no credential.
FROZEN: `AgentResult.result` continues to use the existing reference grammar:
        `sha256:<64 lowercase hex>` or `ref:<opaque token>`.
```

### 19.2 What the backend may do internally

```text
ALLOWED: the backend receives the `InvocationResult` inside `produce`, including `.text`.
FROZEN: the raw text MUST NOT be placed in `AgentResult`, in any field.
FROZEN: the raw text MUST NOT be written to disk, to a log, to an evidence record, or to any
        durable store.
FROZEN: the produced reference is a DIGEST over attributable invocation facts — the bound
        provider/model ref, the request id, the invocation status and finish state, and the
        response digest — plus the local workspace attribution of §12.3.
```

### 19.3 No durable model-output store

```text
FROZEN: AI-09 v1 introduces NO durable artifact store, no model-output database, no blob
        store, no cache of responses.
FROZEN: AI-09 MUST NOT use an AI-05 EvidenceRecord as a model-output store.
FROZEN: AI-05's Evidence boundary is unchanged, and AI-09 writes no EvidenceRecord.
```

```text
FROZEN (scope statement): AI-09 v1 proves provider connectivity and normalized invocation.
        Durable, user-visible model-output materialization is OUT OF SCOPE.
```

This is stated plainly rather than left implicit so that no later reader infers a store that was
never designed. If materialization is wanted, it is its own contract with its own retention,
redaction and admission questions — the ones AI-05 already asks about everything else.

### 19.4 Failure and truncation mapping

```text
FROZEN: a non-SUCCESS `InvocationResult` MUST cause the backend to raise, so that AI-08's
        existing body-failure path produces `FAILED`.
FROZEN: the backend MUST NOT return a reference for an invocation that did not succeed.
        Doing so would report `COMPLETED` for a failed call.
```

```text
RECORDED LIMITATION: raising maps both a provider `ERROR` and a pre-flight `BLOCKED` onto
        AI-08's `FAILED`. AI-08's `AgentExecutionOutcome` is a frozen three-member enum and
        AI-09 MUST NOT amend it to add a fourth. The distinction is not lost — it survives
        intact on the `InvocationResult`, which AI-09's tests observe directly, and in the
        block reason recorded there. It is simply not carried into `AgentResult`.
```

```text
OPEN: whether a `LENGTH` (truncated) SUCCESS produces a reference.
DEFAULT (frozen for AI-09-B): it does NOT; the backend raises. With no durable artifact
        store, a truncated answer cannot be distinguished downstream from a complete one,
        and AI-08 forbids a result that reads as more than it is. Revisiting this requires
        an amendment to this document.
```

---

## 20. Test model: offline and live

### 20.1 Offline (the default, and the gate)

```text
FROZEN: AI-09's ordinary tests are offline, deterministic, and require no credential.
FROZEN: they use the existing shared `FakeTransport`. AI-09 MUST NOT add a second fake
        transport framework or a second fixture format.
FROZEN: they declare exactly one layer marker, per the existing layer model.
```

They prove: the binding, the request construction, the failure mapping, the workspace-alignment
refusal, the absence of context egress, `attempts == 1`, and that no capability moved.

### 20.2 Live (opt-in, manual, bounded)

```text
FROZEN: any live observation reuses AI-02's existing LiveVerifier / ProbeAuthorisation
        machinery. AI-09 MUST NOT copy, fork or reimplement a capability probe.
FROZEN: no live run is added to the default CI path.
FROZEN: the default CI path performs NO NETWORK access to a provider.
FROZEN: AI-09 does not widen `LIVE_PROVIDER_ALLOWLIST`.
```

`mimo` is already in the allowlist, so no widening is required for §5's target.

### 20.3 The default gate stays as it is

```text
FROZEN: `pytest.ini`'s `addopts = -m "not layer4"` is unchanged.
FROZEN: `scripts/ci/layer0_policy.py`'s workflow rules are unchanged except for the new
        AI-09 layer check of §10.4.
FROZEN: `.github/workflows/live-model-verification.yml` stays `workflow_dispatch` only,
        `contents: read`, with step-scoped secrets.
```

### 20.4 Transport injection

```text
FROZEN: the integration layer receives its `Transport` by injection from its composition root.
        It MUST NOT import `providers.http_transport`, and MUST NOT choose a transport.
FROZEN: the default (offline) path constructs no real transport, exactly as today.
```

This is what keeps §20.2 true structurally rather than by convention.

---

## 21. Non-goals — frozen

```text
AI-09 v1 does NOT:
    implement a generic `openai-compatible` provider
    create a third provider identity
    add a protocol, an adapter, or an HTTP client
    add a second invocation API
    modify `providers/`, `agents/`, `routing/`, `plugins/`, `tools/`
    modify the AI-02, AI-07 or AI-08 contracts
    connect the Router to execution, or consume `RouterDecision.selected`
    resolve `agent_hint`
    put a provider client inside `agents/codex/`
    send context, context items, or a serialised `ContextResponse` to a provider
    add a credential scheme, or read a credential itself
    promote a capability, or write `VERIFIED`
    add a capability probe
    build a model-driven tool loop, or execute a tool
    add a retry loop, a fallback, or a second timeout subsystem
    add a durable model-output store, or write an AI-05 EvidenceRecord
    widen the live provider allowlist or the live workflow's trigger
    reach SecurityLab
```

---

## 22. AI-09-B implementation checklist

```text
[ ]  1. Create `integrations/` and `integrations/codex/` as a namespace package (no __init__.py).
[ ]  2. Implement one concrete `CodexBackend` implementation, conforming to AI-08's protocol
        signature EXACTLY. Do not add, remove or rename a parameter.
[ ]  3. Bind `model_ref` explicitly at construction; validate against §6's two refs; make it
        immutable; do not expose it on `produce`.
[ ]  4. Accept an injected `Transport` (and the invocation context it implies) from the
        composition root. Do not import or select a transport.
[ ]  5. Build the `InvocationRequest` per §12.2 and §17. Send the declared task text and the
        protocol-required fields, and nothing derived from `ContextResponse`.
[ ]  6. Implement the workspace-alignment refusal of §12.4 using AI-03's existing primitive.
[ ]  7. Implement the failure mapping of §19.4: raise on non-SUCCESS; compute the reference
        digest; never materialize the text.
[ ]  8. Add `check_ai09_integration_layer()` to `scripts/ci/layer0_policy.py`, asserting §10.3.
        Add it to `main()`'s report sequence.
[ ]  9. Add offline AI-09 tests: binding validation, request shape, no-context-egress,
        workspace mismatch refusal, failure mapping, `attempts == 1`, no capability movement.
[ ] 10. Add the tool-calling and structured-output compatibility observations by REUSING
        AI-02's existing machinery (§14.3, §20.2). Do not add a probe.
[ ] 11. Verify Layer 0 passes and Layers 1-3 pass, with no credential present.
[ ] 12. Write `docs/AI-09_*_EVIDENCE_*.md`.
[ ] 13. Update `docs/PROJECT_STATUS.md` and `docs/MASTER_ROADMAP.md` status lines.
[ ] 14. Confirm the AI-09 contract blob is UNCHANGED by the implementation (or amend first).
[ ] 15. Confirm AI-02, AI-07 and AI-08 contract blobs are UNCHANGED.
```

---

## 23. Exit criteria

```text
C0   this contract is frozen and merged.                                    AI-09-A
C1   `integrations/` exists as a core namespace layer, with the AI-09 Layer 0 check.
C2   a concrete `CodexBackend` exists, binds one explicit `model_ref`, and conforms to
     AI-08's signature with no amendment to AI-08.
C3   every AI-09 invocation reaches a provider only through `Invoker.invoke`.
C4   no context, context item, or serialised `ContextResponse` crosses the provider boundary,
     asserted by test.
C5   no credential literal, no new credential scheme, and no credential read by the
     integration layer.
C6   no capability moved out of `UNKNOWN`; the capability gate is intact and unbypassed.
C7   the tool-calling and structured-output compatibility observations exist and reuse
     AI-02's machinery; `json_object` is not conflated with `json_schema`.
C8   timeout is bounded and `attempts == 1` is asserted.
C9   no durable model output exists anywhere; `AgentResult` is unchanged.
C10  Layer 0 passes, Layers 1-3 pass with no credential present, and no live call is part of
     the default gate.
C11  an AI-09 evidence record is written, and the AI-02, AI-07 and AI-08 contract blobs are
     unchanged.
C12  required CI passes on the AI-09-B head branch.
```

```text
A phase is COMPLETE only when its required CI passes on its own head and the merge checkpoint
is taken. Merged code is not a PASS by itself, and neither is a local green run.
```

---

## 24. Open questions

| # | Question | Stated default for AI-09-B |
| --- | --- | --- |
| 1 | Does a `LENGTH` (truncated) success produce a reference? | No — raise (§19.4) |
| 2 | Should AI-02's transport-confinement guard's roots be widened to include `integrations/`? | Not by AI-09-B; AI-09's own Layer 0 check covers it (§10.4) |
| 3 | Is a durable model-output store wanted at all? | Out of scope for v1 (§19.3); needs its own contract |
| 4 | Should context ever reach a model? | Not in v1; requires a bounded projection contract (§12.5) |
| 5 | Should routing ever select the model an Agent executes? | Not in v1; recorded as an architecture gap (§9.1) |
| 6 | Which of the two model refs does a given Codex execution use, and who decides? | The caller, by constructing the corresponding backend (§11). No default. |

---

## 25. What a reader must not infer

```text
Do not infer a model-output store.        There is none (§19.3).
Do not infer a retry.                     max_retries is 0 and inert (§18).
Do not infer a fallback model.            There is no default and no substitution (§6).
Do not infer a capability.                Every shipped capability is UNKNOWN (§14).
Do not infer provider behaviour.          No provider call has been made in this repository.
Do not infer that COMPLETED means PASS.   It does not; that is AI-08's rule and it stands.
Do not infer that a live run promotes.    It produces evidence for review (§14.3).
Do not infer that AI-09 chose the model.  A caller bound it explicitly (§11).
```

---

## 26. Amendment rule

```text
FROZEN: AI-09-B MUST NOT deviate from this document without amending it first.
```

An amendment is REQUIRED for any change to:

```text
the target provider (§5) or the reserved status of openai-compatible (§5.2)
the supported model refs (§6), or the introduction of any default or fallback
the invocation path (§8) or the Router boundary (§9)
the integration layer's location or dependency direction (§10)
model binding (§11)
the context egress policy (§12)
the credential policy (§13)
the capability truth boundary (§14)
tool-calling (§15) or structured-output (§16) semantics
timeout (§17) or retry (§18) semantics
the output/reference boundary (§19)
the test model (§20)
any non-goal in §21
```

An amendment records: what changed, why, its security and authority impact, and the date. It is
committed before the code that depends on it.

---

## 27. Freeze record

```text
Phase            AI-09 — Domestic Models for Codex
Sub-phase        AI-09-A — Contract / Execution Plan / Freeze
Status           FROZEN
Date             2026-10-02
Base             main @ edb7dfc82ce51123482ac357fb9319dca2fa0d9a
Contract         docs/AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md
```

```text
AI-08 contract blob   a01e03f5306299a0a4442648eeb8fdcfce6bd8dd   UNCHANGED by AI-09-A
AI-07 contract blob   2f8dcba8f9c2ca36e3d917fc6b69c3a5cb7f36fe   UNCHANGED by AI-09-A
AI-02 contract        docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md   UNCHANGED by AI-09-A
```

```text
FROZEN here   the target provider, the supported model refs, the reserved status of
              openai-compatible, the invocation path, the Router boundary, the integration
              layer's physical boundary and dependency direction, model binding, the context
              egress policy, the credential policy, the capability truth boundary,
              tool-calling and structured-output semantics, timeout and retry semantics,
              the output/reference boundary, the test model, and the non-goals
NOT DECIDED   any implementation detail of the integration backend (§22 lists what AI-09-B owes)
```

**AI-09-A freezes a contract. No backend exists, no integration layer exists, and no provider call
has been made by this phase.**
