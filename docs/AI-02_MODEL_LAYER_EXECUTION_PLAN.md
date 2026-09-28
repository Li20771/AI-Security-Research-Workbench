# AI-02 — Model Layer Execution Plan

> Status: **FROZEN** (AI-02-A, 2026-09-28)
> Phase: AI-02 — DeepSeek + MiMo Model Layer
> Sub-phase: **AI-02-A — Contract / Execution Plan / Freeze**
> Prerequisite: AI-01 DSH Baseline (COMPLETE) + AI-00 architecture freeze
> Base branch: `main`
> Base SHA: `a804fc9d89a68d2a0d6fbc0fdbb28d864a22b17a`
> Rule: This document defines the contract. AI-02-B implements against it. Nothing in AI-02 may
> deviate from a frozen contract without amending this document first.

---

## 1. Status

| Item | Value |
| --- | --- |
| Phase | AI-02 — DeepSeek + MiMo Model Layer |
| Sub-phase | AI-02-A — Contract / Execution Plan / Freeze |
| Status | **COMPLETE — contract frozen** |
| Production code changed | **0** |
| Frozen on | 2026-09-28 |
| Freeze branch | `feature/ai-02-model-layer-contract` |

**What this sub-phase delivers:** a written, reviewable contract for the Workbench model layer —
provider boundary, model profile boundary, invocation boundary, capability truth model, metrics
model, secret boundary, live-test boundary, and the phased plan for AI-02-B.

**What this sub-phase explicitly does not deliver:** any implementation. No API client, no model
SDK, no live call, no router, no guard, no plugin, no DSH/Codex integration, no SecurityLab
change.

### 1.1 Freeze semantics

```text
Frozen   = the shape and the rules below are binding for AI-02-B
Deferred = the value or the mechanism is declared but NOT verified by the Workbench
```

A frozen contract is a constraint on implementation. It is **not** a claim that any provider,
model, endpoint, or capability listed here has been tested. Every provider-derived fact in this
document is recorded as `DECLARED` under §8 and is promoted only by recorded execution evidence
in AI-02-B6.

> Frozen contracts and verified facts are different things. This document freezes the former and
> deliberately does not assert the latter.

---

## 2. Base SHA

Recorded at AI-02-A start, read from the repository — not assumed:

```text
branch            = main
HEAD              = a804fc9d89a68d2a0d6fbc0fdbb28d864a22b17a
origin/main       = a804fc9d89a68d2a0d6fbc0fdbb28d864a22b17a
working tree      = clean
remote            = https://github.com/Li20771/AI-Security-Research-Workbench.git
```

HEAD and `origin/main` agree; the base is the merged AI-01 closeout commit
(`docs(ai-01): redefine AI-01 exit criteria and close out the phase (#19)`).

AI-02-A work branch: `feature/ai-02-model-layer-contract`, created from this exact SHA.

### 2.1 Repository baseline observed at AI-02-A

Read directly from the working tree. Nothing below is inferred from directory names.

| Path | Actual content |
| --- | --- |
| `providers/README.md` | Index only; lists `deepseek/`, `mimo/`, `openai-compatible/` |
| `providers/deepseek/` | `README.md` only — "Reserved for the providers/deepseek layer" |
| `providers/mimo/` | `README.md` only — "Reserved for the providers/mimo layer" |
| `providers/openai-compatible/` | `README.md` only — "Reserved for the … layer" |
| `config/providers/` | `README.md` + `providers.example.yaml` (3 provider entries, all `enabled: false`) |
| `tests/unit/` | `README.md` + `test_repository_layout.sh` (layout assertions only) |
| `tests/integration/` | `README.md` only |
| `tests/guard/`, `tests/benchmarks/` | `README.md` only |

**There is no model-layer implementation in the repository.** Every `providers/*` directory is an
empty reserved slot. AI-02 starts from a documentation skeleton, and this plan is the first
AI-02 artifact.

Existing config shape (`config/providers/providers.example.yaml`) — recorded for the gap analysis
in §16.1:

```yaml
providers:
  deepseek:
    enabled: false
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-flash
  mimo:
    enabled: false
    api_key_env: MIMO_API_KEY
    model: ""
  openai-compatible:
    enabled: false
    base_url_env: OPENAI_COMPATIBLE_BASE_URL
    api_key_env: OPENAI_COMPATIBLE_API_KEY
    model: ""
```

---

## 3. Scope

AI-02 builds a **model layer decoupled from the Agent platform**.

Roadmap target (MASTER_ROADMAP §AI-02):

- DeepSeek and MiMo integration
- Provider / Model two-level abstraction
- Unified model capability description
- Context and tool-calling capability recording
- Cost / latency / stability metric collection

This document scopes **all of AI-02**, and freezes the contract that AI-02-B implements.

### 3.1 Architectural position

```text
Agent
  |
  v
Provider          endpoint / authentication / protocol / transport
  |
  v
Model             model id / capability metadata / limits / capabilities
```

`Provider` owns transport and protocol. `Model` owns identity and capability. The split is
binding: a capability question is never answered by a provider profile, and an endpoint question
is never answered by a model profile.

### 3.2 Provider scope — exactly two providers

AI-02 freezes **two** provider profiles:

- `deepseek`
- `mimo`

### 3.3 Model scope

Only the models listed in §6.4. No model may be recorded as a permanent default. No model is
"the" Workbench model.

### 3.4 Deliverables

- A frozen contract (this document) — AI-02-A
- Provider profiles + protocol adapter — AI-02-B1
- Model profiles with truth-model capability status — AI-02-B2
- Decoupled invocation request/result normalization — AI-02-B3
- Metrics collection with usage/null accounting — AI-02-B4
- Offline test suite wired into CI — AI-02-B5
- Opt-in live connectivity verification producing evidence — AI-02-B6
- Evidence record + status update — AI-02-C

### 3.5 Explicitly out of AI-02 scope

AI-02 does **not**:

- implement Model Router, routing rules, task classification, model selection, or fallback
  policy — Router is AI-07 and remains a separate Workbench core service (F-13)
- implement Guard, Context, or Evidence plugins — AI-03/AI-04/AI-05
- integrate DSH or Codex — AI-08
- modify SecurityLab, its research code, or its evidence
- change the permission model, the vehicle boundary, or the Git boundary
- run the AI-11 benchmark
- implement retry, resume, or long-running workflow semantics — AI-13

### 3.6 Router boundary — explicitly excluded

```text
Model Layer
    |
    v
Model Router      <- NOT in AI-02. NOT implemented. NOT designed here.
```

AI-02's obligation to the future Router is exactly this: **produce correct, honest provider and
model metadata**, so that AI-07 can route on real data instead of guesses.

AI-02 must not contain: a routing engine, a default-model choice, a task classifier, a fallback
policy, an escalation policy, or any change to `config/routing/`.

Router selects eligible profiles. It never grants permission (F-13, ADR 0003).

### 3.7 Generic OpenAI-compatible provider — explicitly excluded

`providers/openai-compatible/` and the `openai-compatible` entry in
`config/providers/providers.example.yaml` already exist in the repository. **They are not part of
AI-02.** They remain a reserved extension point for AI-09 and later phases.

The existence of a shared protocol must not be read as a licence to implement a third provider.
See §5.6 for why DeepSeek and MiMo still get separate provider profiles despite sharing a
protocol family.

---

## 4. Non-goals

Beyond §3.5, AI-02 explicitly does not:

- write a real API client or add a model SDK dependency in AI-02-A
- access any external model API in AI-02-A
- add a live connectivity test in AI-02-A
- store, echo, log, or fixture any real credential
- treat provider documentation or vendor benchmarks as Workbench evidence
- claim any capability as verified before AI-02-B6 records execution evidence
- treat a model's marketing benchmark as a selection criterion (MASTER_ROADMAP §AI-02:
  selection data comes from the Workbench's own task benchmark, AI-11)
- convert `BLOCKED` / `NOT_RUN` / `UNKNOWN` into `PASS`
- modify `main`, rewrite history, or force-push

---

## 5. Provider contract

A provider is described by two things that must not be conflated:

| Concept | Nature | Location |
| --- | --- | --- |
| **Provider profile** | static, reviewable descriptor | `providers/<provider_id>/` |
| **Provider adapter** | behavioural implementation for a protocol family | `providers/<provider_id>/` + shared protocol layer |

Frozen rule (§16, D-1): **provider identity and protocol facts are reviewable repository data,
not runtime-editable config.** Runtime config selects, overrides, and enables — it does not
redefine capability.

### 5.1 Provider identity

A provider declares a stable identity:

```yaml
provider_id: deepseek          # stable, lowercase, no version, no spaces
display_name: DeepSeek
```

Rules:

- `provider_id` is the identity used in config keys, model refs, metrics, and evidence.
- `provider_id` is **not** the vendor's marketing name and is not derived from the model name.
- `provider_id` does not change when the vendor renames a product.
- A provider rename is an explicit, reviewed change — never a silent alias.
- `display_name` is human-facing only and is never used as a key.

### 5.2 Endpoint declaration

```yaml
endpoint:
  base_url: https://api.deepseek.com
  path_template: /chat/completions
  source: declared              # declared | verified
  verified_at: null
  evidence_ref: null
```

Rules:

- `base_url` and `path_template` are recorded **separately**. Composition is
  `base_url` + `path_template`.
- **No shared URL prefix may be assumed.** The two in-scope providers declare different base URL
  shapes (§5.5). A generic `/v1` prefix must never be hardcoded.
- An endpoint is `declared` until AI-02-B6 observes it. A declared endpoint is never treated as
  reachable, correct, or current.
- Endpoint overrides may come from runtime config; when an override is active, the effective
  endpoint must record `source: override` and the profile default must remain unchanged.
- The credential is never part of the URL.

### 5.3 Credential reference

Config and profiles carry a **reference**, never a value:

```yaml
credential:
  ref: env:DEEPSEEK_API_KEY
  kind: api_key
  required: true
```

Reference grammar (frozen for v1):

```text
env:<VAR_NAME>        v1 — read from the process environment. The only supported scheme.
file:<path>           reserved
keyring:<id>          reserved
vault:<path>          reserved
<literal value>       FORBIDDEN
```

Three distinct outcomes. They are **never merged** (§5.10):

```text
env:<VAR_NAME> unset / empty / whitespace   ->  CREDENTIAL_MISSING      (runtime precondition)
file: / keyring: / vault: / unknown scheme  ->  CREDENTIAL_UNSUPPORTED  (runtime precondition)
<literal value>                             ->  configuration rejection (never reaches runtime)
```

Rules:

- Only `env:` is implemented in AI-02. A reserved or unrecognised scheme fails closed with
  `CREDENTIAL_UNSUPPORTED` — it never falls back to a literal, to an empty value, or to treating
  the reference string as a variable name.
- **An unsupported scheme is not a missing credential.** `file:/etc/key` is a well-formed
  reference to a mechanism AI-02 does not implement; it is not an unset variable. The two are
  separately classed (§5.10) so that an unimplemented mechanism is never reported as a
  configuration gap, and a genuine configuration gap is never reported as an unimplemented
  mechanism. Their remedies differ: one needs a credential provisioned, the other needs a
  supported reference written.
- Resolution happens **at invocation time**, not at import time, and never at config-load time
  in a way that writes the value anywhere.
- The resolved value lives only in the request's transport header. It is never returned, logged,
  serialized, put in a metric, or written to Evidence.
- **Missing and empty are the same failure.** An unset variable and a variable set to `""` or
  whitespace both resolve to `CREDENTIAL_MISSING`.
- A **literal value** in a `ref` field is rejected by configuration/schema validation (§10.3). It
  is never resolved, never sent, and never treated as a credential — it is a defect, not a runtime
  error class.
- `CREDENTIAL_MISSING` and `CREDENTIAL_UNSUPPORTED` are **precondition failures raised before any
  network attempt.** Neither is an authentication error discovered by the provider, and neither
  may ever be sent as an empty `Authorization` header.
- `required: false` is permitted only for providers that genuinely need no credential; it does not
  authorise sending an empty one.

### 5.4 Protocol declaration

```yaml
protocol:
  family: openai_compatible_chat
  version: v1
```

Streaming support is a model capability (§6.7), and provenance is recorded where defined by the
endpoint/capability schemas; neither is a Protocol field here.

Rules:

- `protocol.family` names the **wire protocol family**, not the vendor. Both in-scope providers
  declare `openai_compatible_chat`.
- The protocol family determines the adapter. The provider profile determines endpoint,
  credential, and protocol. **Runtime config supplies transport settings** (§5.11): transport is
  not profile data, and a profile carrying it is rejected on load.
- `protocol.version` is the protocol revision the adapter targets, not the provider's API version
  string.
- "OpenAI-compatible" is a **declaration of intent, not a guarantee.** Compatibility is partial
  in practice; anything not observed is `DECLARED`, per §8.
- Where a provider deviates from the family, the deviation is recorded as an explicit
  provider-level exception rather than silently absorbed into the shared adapter.

### 5.5 In-scope provider profiles

Declared values below are recorded as `DECLARED` (§8). None is verified.

#### `deepseek`

```yaml
provider_id: deepseek
display_name: DeepSeek
protocol: { family: openai_compatible_chat, version: v1 }
endpoint:
  base_url: https://api.deepseek.com
  source: declared
credential: { ref: "env:DEEPSEEK_API_KEY", kind: api_key, required: true }
```

Reference models (§6.4): `DeepSeek-V4.1-Flash` → API model id `deepseek-flash`.

#### `mimo`

```yaml
provider_id: mimo
display_name: MiMo
protocol: { family: openai_compatible_chat, version: v1 }
endpoint:
  base_url: https://api.xiaomimimo.com/v1
  source: declared
credential: { ref: "env:MIMO_API_KEY", kind: api_key, required: true }
```

Reference models (§6.4): `MiMo-V2.6-Pro` → `mimo-v2.6-pro`, `MiMo-V2.6-Flash` → `mimo-v2.6-flash`.

> **Endpoint shapes differ deliberately.** `deepseek` declares a base URL without a version
> segment; `mimo` declares one with `/v1`. This is exactly why §5.2 forbids assuming a shared
> prefix. Endpoint correctness for both is `DECLARED` and is verified only in AI-02-B6.

### 5.6 Shared protocol does not mean shared provider profile

Frozen decision (§16, D-2): **`deepseek` and `mimo` are separate provider profiles even though
they share a protocol family**, and neither is implemented via the reserved
`openai-compatible` provider.

Reasons:

- they have different endpoints, different credentials, and independent availability
- their compatibility gaps will differ, and each gap must be attributable to a named provider
- metrics and evidence must attribute a request to a real provider, not to a generic bucket
- routing (AI-07) and benchmarking (AI-11) need per-provider attribution to be meaningful

Sharing the **adapter** is correct and expected. Sharing the **profile** would destroy
attribution.

### 5.7 Supported-model exposure

A provider exposes the models it can serve as an explicit list of **model references**, never as
a single default:

```yaml
models:
  - deepseek/deepseek-flash
```

Rules:

- The provider profile lists references; the model profile (§6) owns the facts.
- A provider must not invent a model id that has no model profile.
- The list carries no ordering semantics. Position in the list never means "preferred" or
  "default".
- **A single model must never be recorded as the permanent default.**
- A provider profile that cannot enumerate its models exposes an empty list, not a guess.

### 5.8 Normalized response

The provider adapter returns a **normalized envelope**, never a raw HTTP response:

```yaml
provider_response:
  provider_id: deepseek
  model_id: deepseek-flash
  text: null
  tool_calls: []
  structured_output: null
  reasoning: null
  usage: { ... }
  finish_state: STOP
  provider_request_id: null
  raw_response_ref: null
  error: null
```

Rules:

- The envelope shape is **identical across providers**. Consumers of the model layer never see a
  provider-specific payload.
- `raw_response_ref` is an **artifact pointer**, not inlined content. Normalized output is
  durable; raw payload is disposable (F-15, ADR 0004).
- Reasoning/thinking content, when a provider returns it, goes to `reasoning` and **must never be
  concatenated into `text`.** The answer and the model's reasoning are different artifacts with
  different evidentiary weight.
- Absent fields are `null` or `[]`. Absence is never represented by a fabricated zero-length
  string, a zero count, or a default object.

### 5.9 Transport error reporting

Every failure produces a typed error, never a bare exception and never a silent fallback:

```yaml
error:
  class: TIMEOUT
  provider_code: null
  provider_message_sanitized: "connect deadline exceeded"
  retryable: true
  stage: connect          # resolve | connect | tls | send | receive | parse | validate
  http_status: null
```

Rules:

- `class` comes from the frozen taxonomy in §5.10.
- `stage` records **where** it failed, which distinguishes a network fault from a provider fault.
- `provider_message_sanitized` has passed through the redaction step in §10.3.
- `retryable` is a **hint for a later phase only.** AI-02 implements no retry loop (§5.11).
- An unclassified failure is `UNKNOWN` — never `SUCCESS`, and never an exception that escapes as
  an untyped crash.

### 5.10 Error classification taxonomy (frozen)

| Class | Trigger | Default `retryable` |
| --- | --- | --- |
| `CREDENTIAL_MISSING` | credential env var unset, empty, or whitespace — raised **before** any request | no |
| `CREDENTIAL_UNSUPPORTED` | credential ref uses an unsupported scheme (`file:`, `keyring:`, `vault:`, unknown) — raised **before** any request | no |
| `AUTHENTICATION` | credential rejected by provider (401/403) | no |
| `RATE_LIMIT` | transient throttle (429) | yes |
| `QUOTA_EXHAUSTED` | balance/quota exhausted (402, hard quota) | no |
| `TIMEOUT` | connect or total deadline exceeded | yes |
| `TRANSPORT` | DNS / TCP / TLS / socket failure; no HTTP response obtained | yes |
| `SERVER` | provider-side failure (5xx) | yes |
| `INVALID_REQUEST` | provider rejected the request as malformed (400/422) | no |
| `CONTEXT_OVERFLOW` | request exceeds the model's context window | no |
| `CONTENT_FILTER` | provider refused on policy grounds | no |
| `PROTOCOL` | response unparseable, or shape violates the declared contract | no |
| `CANCELLED` | caller aborted | no |
| `UNKNOWN` | not classifiable | no |

The eight error distinctions required by AI-02-A are answered as follows:

| Required distinction | Answer |
| --- | --- |
| authentication | `AUTHENTICATION` (provider rejected the credential) vs `CREDENTIAL_MISSING` (no credential to send) vs `CREDENTIAL_UNSUPPORTED` (reference mechanism not implemented) |
| timeout | `TIMEOUT`, with `stage` recording connect vs read vs total |
| rate-limit | `RATE_LIMIT` (transient) vs `QUOTA_EXHAUSTED` (terminal) |
| protocol | `PROTOCOL` (response violated the contract) vs `INVALID_REQUEST` (we sent a bad request) |

Rules:

- **`RATE_LIMIT` and `QUOTA_EXHAUSTED` are never merged.** One is transient and retryable, the
  other is terminal and needs a human. Conflating them produces retry storms against a dead
  account.
- **`PROTOCOL` and `INVALID_REQUEST` are never merged.** One means the provider broke our
  contract; the other means we broke theirs.
- **`CREDENTIAL_MISSING` and `CREDENTIAL_UNSUPPORTED` are never merged.** One means the runtime
  environment did not supply a credential; the other means the reference asked for a mechanism
  AI-02 does not implement. They have different remedies — provisioning a credential versus
  writing a supported reference — so merging them sends an operator to fix the wrong thing.
- **A literal credential value is not an error class.** It is rejected by configuration/schema
  validation (§10.3), never resolved, and never sent, so it never reaches this taxonomy.
- A failure is never downgraded into a partial success. Partial output produced before a
  `TIMEOUT` is recorded as partial and the call's status is the error.
- Provider error bodies are **sanitized before they are stored**, because providers echo request
  material — including credentials — into error text.

### 5.11 Transport settings

```yaml
transport:
  timeout_connect_ms: 10000
  timeout_total_ms: 120000
  max_retries: 0
  verify_tls: true
```

Rules:

- **A timeout is always explicit.** There is no unbounded or default-infinite request.
- `timeout_total_ms` is a hard deadline covering the whole call, including retries.
- `max_retries` is frozen as a field but **must default to `0` in AI-02.** Retry policy is AI-13's
  problem; adding retries here would silently multiply live-test cost and mask flakiness.
- `verify_tls: true` is the default and disabling it is a security-relevant change requiring
  explicit human approval.
- Transport settings are runtime config, not profile data.

### 5.12 Provider contract checklist

Every item AI-02-A was required to answer:

| # | Question | Answered in |
| --- | --- | --- |
| 1 | how a provider declares identity | §5.1 |
| 2 | how a provider provides its endpoint | §5.2, §5.5 |
| 3 | how a provider reads a credential reference | §5.3 |
| 4 | how a provider declares protocol | §5.4 |
| 5 | how a provider exposes supported models | §5.7 |
| 6 | how a provider returns a normalized response | §5.8 |
| 7 | how a provider reports transport errors | §5.9 |
| 8 | how auth / timeout / rate-limit / protocol errors are distinguished | §5.10 |

---

## 6. Model profile contract

A model profile describes **one model available from one provider**. It is keyed by the model
reference `provider_id/model_id`.

### 6.1 Shape

```yaml
model_ref: deepseek/deepseek-flash
provider_id: deepseek
model_id: deepseek-flash
display_name: DeepSeek-V4.1-Flash
family: deepseek
version: "4.1"

limits:
  context_limit: null
  max_output: null

modality:
  input: [text]
  output: [text]

capabilities:
  tool_calling:      { declared: null, verified: null, status: UNKNOWN, source: null }
  structured_output: { declared: null, verified: null, status: UNKNOWN, source: null }
  streaming:         { declared: null, verified: null, status: UNKNOWN, source: null }
  reasoning:         { declared: null, verified: null, status: UNKNOWN, source: null }
  prompt_caching:    { declared: null, verified: null, status: UNKNOWN, source: null }

provenance:
  declared_source: null
  declared_at: null
  verified_at: null
  evidence_ref: null
```

### 6.2 Required fields

Per AI-02-A §5.2, every profile carries: provider, model id, display name, family/version,
context limit, max output, modality, tool calling, structured output, streaming,
reasoning/thinking capability, capability source, and capability verification status.

### 6.3 Identity rules

- **`model_id` is the API model id** and is the only string ever sent to the provider.
- **`display_name` is never sent to the provider.** Display names are human-facing metadata.
- **A display name must never be converted into a model id by string manipulation** — no
  lowercasing, no hyphenating, no stripping. The two strings are independent records that happen
  to correspond.
- `model_id` is passed **verbatim**, case-sensitively. `deepseek-flash` and `DeepSeek-Flash` are
  different strings and only the recorded one is correct.
- `family` and `version` are **descriptive grouping fields with no behavioural meaning.**
  Capability must never be inferred from family, version, or name. `-Pro` in a display name is
  not evidence of a capability.
- `model_id` is recorded exactly as the provider documents it, and its correctness is `DECLARED`
  until AI-02-B6 confirms it — an unverified id is a documented risk, not a verified fact.

### 6.4 In-scope models

| Provider | Reference (display) name | API model id | Status |
| --- | --- | --- | --- |
| `deepseek` | `DeepSeek-V4.1-Flash` | `deepseek-flash` | DECLARED |
| `mimo` | `MiMo-V2.6-Pro` | `mimo-v2.6-pro` | DECLARED |
| `mimo` | `MiMo-V2.6-Flash` | `mimo-v2.6-flash` | DECLARED |

Rules:

- This table is the **complete** AI-02 model scope. Nothing else is in scope.
- **None of these is a default model.** There is no "the Workbench model".
- The reference name is the vendor's; the model id is the API's. They are recorded as a pair, not
  as a derivation.
- Whether `deepseek-flash` and the `mimo-v2.6-*` ids are exactly correct is **`DECLARED` and
  unverified** at freeze time. AI-02-B6 is where that is settled.

### 6.5 Limits — nullability rule

```text
context_limit / max_output:  null  =>  unknown. NEVER a guess.
```

- An unknown limit is `null`, never a plausible-looking number and never a vendor maximum copied
  from a different model.
- A wrong context limit is materially worse than an unknown one: it silently truncates real work.
- A limit is `DECLARED` when it comes from provider documentation, and `VERIFIED` only when the
  Workbench observed the boundary.
- Consumption code must handle `null` limits by **refusing to assume a budget** — not by
  substituting a default. Where a limit is required and unknown, the operation is `BLOCKED`, not
  optimistically attempted.

### 6.6 Modality

`modality` is a set, not a scalar: a model may accept one modality and emit another.

- v1 requires `input: [text]` and `output: [text]`.
- Additional modalities are recorded only when declared, and follow the truth model.
- A request whose modality is not in the model's **declared** input set is refused before the
  request is sent.

### 6.7 Capability entries

Each capability uses the truth-model object frozen in §8. Capability-specific rules:

**`tool_calling`** — records that the *mechanism* works: tools are accepted, calls are returned,
and calls map into the normalized result. It does **not** claim the model chooses tools correctly;
tool-call correctness is measured by AI-11, not asserted by AI-02.

**`structured_output`** — is more than a boolean. The declared support level matters:

| Mode | Meaning | Consumer rule |
| --- | --- | --- |
| `json_schema` | a supplied schema is enforced by the provider | output may be treated as schema-conforming |
| `json_object` | JSON is guaranteed, schema is **not** | output must be validated by the caller |
| `none` | no structured-output guarantee | — |

> **`json_object` is not schema enforcement.** A profile that declares `json_object` must never be
> consumed as though it guaranteed a schema. Treating the two as equivalent is exactly the kind of
> false-confidence failure the Workbench exists to prevent.

**`streaming`** — records whether a streamed response is delivered and mapped into the normalized
envelope. A model that streams but whose stream cannot be normalized is not `VERIFIED`.

**`reasoning`** — records whether the model exposes reasoning/thinking content separately. When
present it is surfaced in the `reasoning` field, never merged into `text` (§5.8). Where a provider
exposes a reasoning *control*, its default state is recorded — an implicitly-enabled thinking mode
changes latency, token cost, and output shape, and must not be discovered by surprise in
benchmark results.

**`prompt_caching`** — records whether the provider reports cache reads/writes. It exists because
§9 requires cache tokens to be recordable when reported, and explicitly absent when not.

### 6.8 Capability source and verification status

Every capability carries `source` (where the claim came from) and `status` (§8). A capability with
no claim and no observation is `UNKNOWN` with `source: null` — never a defaulted `false`.

```text
declared: null, status: UNKNOWN   =>  nobody knows. Not "false".
declared: false, status: UNAVAILABLE => someone positive-observed that it does not work.
```

`UNKNOWN` and `UNAVAILABLE` are not interchangeable, and neither is `false`.

---

## 7. Invocation contract

A single provider-decoupled call model. Defined here; **not implemented in AI-02-A.**

### 7.1 Request

```yaml
invocation_request:
  request_id: wb-<ulid>            # Workbench-generated correlation id
  model_ref: deepseek/deepseek-flash
  messages:
    - role: system | user | assistant | tool
      content: <text>
  tools: []                        # optional, provider-agnostic schema
  structured_output:               # optional
    mode: json_schema | json_object | none
    schema: {}                     # required when mode = json_schema
  generation:                      # optional
    temperature: null
    max_output: null
    stop: []
  stream: false
  timeout_ms: 120000               # required
  metadata:                        # request metadata — see §7.3
    experiment_id: null
    task_id: null
    task_class: null
    agent: dsh
    purpose: connectivity_check
```

Rules:

- `model_ref` is the only way to name a model. A bare model id is not accepted, because it loses
  provider attribution.
- `timeout_ms` is required. There is no unbounded call.
- The request contains **no credential**. Credentials are resolved by the provider adapter at send
  time, from the reference in the provider profile.
- `tools` and `structured_output` are optional and independent; support for each is gated by the
  model profile's capability status.
- A request that requires an unverified capability is **refused before sending** rather than
  attempted optimistically. `status: NOT_VERIFIED` does not authorise a live attempt outside
  AI-02-B6.
- `stream: true` where streaming is not `VERIFIED` is refused rather than silently downgraded to
  `false` — a silent downgrade hides a broken capability.

### 7.2 Result

```yaml
invocation_result:
  request_id: wb-<ulid>
  provider_id: deepseek
  model_id: deepseek-flash
  model_ref: deepseek/deepseek-flash
  status: SUCCESS | ERROR | BLOCKED
  text: null
  tool_calls: []
  structured_output: null
  reasoning: null
  usage: { ... }                   # §9.2
  finish_state: STOP | LENGTH | TOOL_CALLS | CONTENT_FILTER | ERROR | UNKNOWN
  latency: { total_ms: null, ttfb_ms: null }
  error: null                      # §5.9 shape — provider-layer failures only
  attempts: 1
  raw_response_ref: null
  blocked: null                    # invocation-layer refusal; see below
    # code: CAPABILITY_NOT_VERIFIED | UNKNOWN_PROVIDER
    #     | UNKNOWN_MODEL | CREDENTIAL_CONFIG_DEFECT
    # detail: <text>
    # required_capability: null    # set when code = CAPABILITY_NOT_VERIFIED
    # actual_status: null          # the capability status actually recorded
```

Rules:

- `status` is the **only** success signal. A non-empty `text` on an `ERROR` result is partial
  output, not a success.
- `provider_id` + `model_id` + `model_ref` are always recorded, so every result is attributable
  without consulting external state.
- `model_id` echoes the **effective** model id the provider was asked for — if an alias or
  redirect occurred, it is recorded rather than hidden.
- `BLOCKED` means the invocation was refused **before any provider activity**. Nothing was sent,
  so no provider finish reason exists and a `BLOCKED` result always carries
  `finish_state: UNKNOWN`. `finish_state: ERROR` means a *provider* signalled failure (§7.3) and
  is therefore never used for a refusal.
- A `BLOCKED` result carries its reason in exactly one of two places:
  - **Invocation-layer refusal** — `blocked` is populated and `error` is `null`. The `code`
    names the policy decision. These have no provider taxonomy class because no provider was
    contacted.
  - **Credential precondition** — `error` carries `CREDENTIAL_MISSING` or
    `CREDENTIAL_UNSUPPORTED` (§5.3), which are frozen provider taxonomy classes, and `blocked`
    is `null`.
- **No provider `ErrorClass` is introduced for an invocation-layer refusal.** The provider
  taxonomy describes provider-layer outcomes (D-6, D-16); reusing a class for a pre-flight
  policy decision would blur that boundary and imply a provider interaction that never
  happened. The two representations stay separate on purpose.

### 7.3 Finish state

| State | Meaning | Consumer rule |
| --- | --- | --- |
| `STOP` | model finished naturally | complete |
| `LENGTH` | output hit a length limit and is **truncated** | must be treated as incomplete |
| `TOOL_CALLS` | model requested tool calls | not an error; not a final answer |
| `CONTENT_FILTER` | provider stopped on policy grounds | not a successful answer |
| `ERROR` | provider signalled failure | failure |
| `UNKNOWN` | provider returned an unrecognised state | must not be treated as `STOP` |

> **`LENGTH` is a truncation warning, not a success.** A truncated answer that gets consumed as
> complete is a false result — the exact failure mode the Workbench truth model exists to prevent.
> `UNKNOWN` similarly must never default to `STOP`.

### 7.4 Request metadata

`metadata` exists so metrics and evidence can attribute a call without parsing prompts.

- `experiment_id` links the call to an Evidence record (AI-05).
- `task_class` is recorded for **later** routing analysis by AI-07 — recording it does not
  implement routing.
- `agent` names the calling Agent; it never implies a permission.
- Metadata never contains secrets, prompt bodies, or credential material.
- AI-02 **records** metadata. It does not act on it. No field here may drive model selection.

---

## 8. Capability model (truth model)

### 8.1 The five states (frozen)

```text
DECLARED
VERIFIED
NOT_VERIFIED
UNAVAILABLE
UNKNOWN
```

| State | Meaning | Evidence required |
| --- | --- | --- |
| `DECLARED` | an external source claims it (provider docs, model card, vendor material) | a citation; **no Workbench execution** |
| `VERIFIED` | the Workbench observed it working | recorded execution evidence |
| `NOT_VERIFIED` | verification was attempted and was inconclusive, blocked, or insufficient | a record of the attempted check |
| `UNAVAILABLE` | the Workbench observed it absent, rejected, or unsupported | a record of the negative observation |
| `UNKNOWN` | no claim and no observation exists | — |

Relationship to the repository truth model (AI-04 / CONTRIBUTING):

```text
VERIFIED     ~ PASS       executed, evidenced, positive
UNAVAILABLE  ~ FAIL       executed, evidenced, negative
NOT_VERIFIED ~ BLOCKED    attempted, no conclusive evidence
DECLARED     ~ (none)     documented only — no Workbench execution
UNKNOWN      ~ UNKNOWN    nothing known
```

### 8.2 Two axes, not one

A capability records **what was claimed** and **what was observed** separately:

```yaml
tool_calling:
  declared: true
  verified: false
  status: NOT_VERIFIED
  source: provider_docs
```

`declared` and `verified` answer different questions and are never collapsed into one boolean.

### 8.3 Rules

- **`DECLARED` never auto-promotes to `VERIFIED`.** Only recorded execution evidence promotes it.
- **Provider documentation is not Workbench evidence.** Marketing material and vendor benchmarks
  are `DECLARED` at best, and are never a selection criterion (MASTER_ROADMAP §AI-02).
- **`UNKNOWN` is not `false`, and `UNKNOWN` is not `UNAVAILABLE`.** No claim plus no observation is
  `UNKNOWN`; `false` is an assertion that requires evidence.
- **Absence of a declaration is not evidence of absence.**
- **A fixture is not evidence of provider behaviour** (§12.3). Only an actual observed response is.
- Every promotion to `VERIFIED` records `verified_at`, the model id, and an `evidence_ref`.
- A `VERIFIED` capability is valid **only for the model id, endpoint, and date it was observed
  against.** Providers change models in place; a stale verification is not a permanent guarantee
  and must be re-established when the model id or endpoint changes materially.

---

## 9. Metrics model

AI-02 must support the collection below. **Collecting a metric does not implement a policy on
it** — routing on these numbers is AI-07/AI-12.

### 9.1 Required metrics

| Metric | Notes |
| --- | --- |
| `request_count` | attempted calls |
| `success_count` | `status = SUCCESS` |
| `failure_count` | `status = ERROR` |
| `blocked_count` | `status = BLOCKED` — e.g. credential missing or unsupported. **Not a failure** |
| `timeout_count` | the `TIMEOUT` subset of failures, counted separately |
| `latency` | raw `total_ms` samples plus aggregates; aggregates never replace samples |
| `input_tokens` | provider-reported |
| `output_tokens` | provider-reported |
| `cache_read_tokens` | only where the provider reports them |
| `cache_write_tokens` | only where the provider reports them |
| `estimated_cost` | **only** when a pricing record applies (§9.3) |
| `error_class` | distribution over the §5.10 taxonomy |
| `attempts` | per call; `retry_count` is reserved for AI-13 and is `0` in AI-02 |
| `usage_unknown_count` | calls whose usage was not reported |

### 9.2 Usage and the zero-vs-unknown rule

```yaml
usage:
  input_tokens: null
  output_tokens: null
  total_tokens: null
  cache_read_tokens: null
  cache_write_tokens: null
  usage_status: REPORTED | ESTIMATED | UNKNOWN
```

> **A missing token count is `null` with `usage_status: UNKNOWN`, never `0`.** Zero is a
> measurement; unknown is the absence of one. Reporting unmeasured usage as `0` silently
> under-reports cost and corrupts every downstream aggregate.

Rules:

- `usage_status: UNKNOWN` propagates: an aggregate containing any unknown usage is itself labeled
  as partially unknown, and every total reports `usage_unknown_count` alongside it.
- `ESTIMATED` (a locally tokenized approximation) is never presented as `REPORTED`. AI-02 does not
  implement estimation; the state is reserved so it cannot be faked later.
- `blocked_count` is tracked separately so that an unconfigured environment does not look like a
  failing provider.

### 9.3 Pricing

Pricing is **updatable metadata, never core logic.**

```yaml
pricing:
  provider_id: deepseek
  model_id: deepseek-flash
  currency: USD
  unit: per_1m_tokens
  effective_from: 2026-09-28
  input_per_1m: null
  output_per_1m: null
  cache_read_per_1m: null
  cache_write_per_1m: null
  source: null
```

Rules:

- **No price is ever hardcoded in core logic.** Cost is *derived* at read time from a pricing
  record; token counts are the durable metric, cost is a projection.
- Pricing records are **versioned and date-stamped**. Prices change; a cost figure without its
  pricing record's date is not reproducible.
- **No applicable pricing record ⇒ `estimated_cost: null` with `pricing_status: UNKNOWN`** — never
  `0`, and never a fallback to another model's price.
- Estimated cost is `null` whenever `usage_status: UNKNOWN`, because the inputs are unknown.
- `source` records where the price came from. An unsourced price is not a verified price.
- AI-02 records the pricing *shape and lookup rule*. Populating real prices is deferred, and no
  price is asserted in this document.

### 9.4 Attribution

Every metric sample carries `provider_id`, `model_id`, `model_ref`, `status`, `error_class`, and
the `experiment_id`/`task_class` metadata from §7.4. Metrics that cannot be attributed to a real
provider and model are not collected — this is what makes AI-11's benchmark data trustworthy.

---

## 10. Secret boundary

### 10.1 Prohibited locations

Credentials must never enter:

- Git-tracked files, including profile files and example config
- `.env.example` or any other example/template file
- test fixtures or recorded response fixtures
- Evidence records
- ordinary logs, error messages, stack traces, or metric values
- the invocation request/result objects
- chat, prompts, or model input

### 10.2 Permitted locations

Runtime resolution only, via the reference grammar in §5.3 — process environment in v1. A future
secret manager is a reserved scheme, not an implicit permission.

### 10.3 Enforcement inside the contract

- Config and profiles carry `credential.ref` — a **reference**. A literal value in a ref field is
  rejected by configuration/schema validation, never resolved, and never sent. It is a defect, not
  a convenience — and not an error class either.
- The provider adapter logs the credential's **presence, never its value** (`present` / `missing`).
- Redaction applies to outbound error text, because providers echo request material into error
  bodies: `Authorization` headers, `api_key`/`token`/`secret`/`password` parameter patterns, and
  key-shaped strings are stripped before storage.
- `provider_message_sanitized` is sanitized **at capture time**, not at display time — anything
  stored unsanitized is already a leak.
- Evidence records store `provider_id` / `model_id` / endpoint host, never credential material
  (ADR 0004).
- `.env` remains gitignored, and the preflight CI check that no `.env`, `*.pem`, or `*.key` file is
  present continues to apply.

### 10.4 Test fixture rule

Fixtures must contain **obviously synthetic placeholder values** (e.g. `test-key-not-a-real-key`)
and must be non-functional if ever used. The test suite must additionally assert that **no test
requires a real credential** to pass.

### 10.5 Fail-closed rule

```text
credential env var unset/empty/whitespace  ->  BLOCKED (CREDENTIAL_MISSING), before any network attempt
credential ref scheme unsupported          ->  BLOCKED (CREDENTIAL_UNSUPPORTED), before any network attempt
credential ref is a literal value          ->  configuration rejected, never sent
credential present and scheme supported    ->  attempt
anything else                              ->  BLOCKED
```

A missing credential is never resolved by trying anyway, an unsupported scheme is never resolved by
guessing at the reference, and an authentication failure is never retried as though it were
transient.

---

## 11. Live-test boundary

### 11.1 CI rules

CI **must not**:

- access the real DeepSeek API
- access the real MiMo API
- require an API key to be present
- mark any live check as `PASS`

In CI, every live check is `NOT_RUN`. That is the **expected** CI outcome, and CI passes with live
checks `NOT_RUN`. Live-check status is never part of the CI gate.

### 11.2 Live-test status vocabulary

```text
PASS      executed, observed success, evidence recorded
FAIL      executed, observed failure, evidence recorded
BLOCKED   could not execute (no credential, opt-in off, endpoint unreachable)
NOT_RUN   intentionally not executed — the CI default
UNKNOWN   executed but inconclusive
```

> **`NOT_RUN != PASS`.** A live check that did not run has produced no evidence and supports no
> capability claim. Neither does `BLOCKED`. This is the same rule as AI-04's status semantics, and
> it applies with particular force here: the entire purpose of AI-02-B6 is to convert `DECLARED`
> into `VERIFIED`, and that conversion is void if a skipped run reports success.

### 11.3 Opt-in requirements

A live test runs only when **all** hold:

1. an explicit opt-in flag is set (e.g. `WORKBENCH_LIVE_TESTS=1`)
2. the specific provider's credential resolves (not merely "is mentioned")
3. the provider is in an explicit live-test allowlist

Absent any one of these, the test records `BLOCKED` with a machine-readable reason
(`opt_in_absent`, `credential_missing`, `credential_unsupported`, `provider_not_allowlisted`), or
`NOT_RUN` in CI.

### 11.4 Live-test safety rules

- Single-shot, bounded, and low-cost: a minimal fixed prompt with a small `max_output`.
- **No repository content is sent.** No file, diff, doc, or credential-adjacent string leaves the
  host. A connectivity check sends a fixed literal.
- No tool execution, no file access, no network target beyond the provider endpoint.
- `timeout_total_ms` set explicitly and conservatively.
- `max_retries: 0`, so a failure is observed rather than retried into ambiguity.
- Costs are bounded and recorded.
- Live tests are **never** invoked from the default CI workflow, and never from a hook that a
  normal test run triggers.

### 11.5 Live-test evidence

Each live run records: provider, model id, endpoint host, timestamp, status, latency, finish
state, `usage_status`, and `error_class` on failure. It records **no credential**, and no raw
request or response body unless it has passed §10.3 redaction.

### 11.6 What a live test proves

A live test proves capability **for that model id, that endpoint, and that date.** It says nothing
about other models, other endpoints, or future dates. Provider model ids change under stable
public names, so a verification is a dated observation, not a permanent property of the name.

---

## 12. Testing strategy

Five layers, ordered by what they are allowed to assume.

### 12.1 Layer 0 — repository policy (offline, exists)

Already in CI: required files, repository layout, absence of secret files, shell syntax. AI-02-B5
extends this with: example configs contain no credential **values**; `.env` is not tracked; no
live test is reachable from the default workflow.

### 12.2 Layer 1 — contract and schema (offline)

- model profiles validate against the profile schema
- provider profiles validate against the provider schema
- every `model_ref` resolves to an existing profile
- `model_id` is non-empty and free of whitespace/control characters
- **every credential entry is a reference** — a literal value is a hard failure
- capability status values are within the §8.1 set

### 12.3 Layer 2 — unit tests with a fake transport (offline, no network)

A stub transport returning canned provider-shaped payloads. Asserts normalization:

- `usage` absent ⇒ `null` + `UNKNOWN`, **never `0`**
- `finish_state: LENGTH` is propagated and not treated as complete
- error classification for 401 / 403 / 402 / 429 / 5xx / 400 / malformed body / connect timeout /
  read timeout / TLS failure
- `RATE_LIMIT` and `QUOTA_EXHAUSTED` stay distinct
- `PROTOCOL` and `INVALID_REQUEST` stay distinct
- tool calls map into `tool_calls`, not into `text`
- reasoning content maps to `reasoning` and **never** into `text`
- `json_object` mode is not reported as schema-enforced
- credential redaction removes key-shaped strings from error text
- empty/unset/whitespace credential ⇒ `CREDENTIAL_MISSING` **with no request sent**
- unsupported ref scheme (`file:`, `keyring:`, `vault:`, unknown) ⇒ `CREDENTIAL_UNSUPPORTED`
  **with no request sent**, and never reported as `CREDENTIAL_MISSING`
- a literal credential value ⇒ rejected by schema validation, **with no request sent**
- `timeout_ms` is enforced; partial output on timeout is marked partial
- no result is ever produced with `status: SUCCESS` and a non-null `error`

> **A fixture is not evidence of provider behaviour.** Layer 3 fixtures are hand-written synthetic
> payloads or scrubbed captures. They pin *our* normalization logic. They never establish what a
> provider does, and they can never promote a capability to `VERIFIED`.

### 12.4 Layer 3 — offline contract fixtures (offline)

Recorded per-provider response fixtures, checked in, synthetic or scrubbed, containing no real
credential. They pin normalization behaviour across refactors. Each fixture is labeled with its
provenance (`synthetic` or `scrubbed`); a fixture of unknown provenance is not usable as a
regression baseline.

### 12.5 Layer 4 — opt-in live connectivity verification (AI-02-B6)

Gated per §11. Produces dated evidence and is the **only** layer permitted to promote a capability
from `DECLARED` to `VERIFIED`.

### 12.6 Layer rules

- CI runs layers 0–3. **Never layer 4.**
- Layers 1–3 require no credential, no network, and no provider access.
- Layer 4's absence is `NOT_RUN`, and `NOT_RUN` is a legitimate, expected CI state — not a failure
  to be papered over, and not a `PASS`.

---

## 13. Implementation phases

```text
AI-02-A    Contract / Freeze                        <- this document. COMPLETE.
AI-02-B1   Provider skeleton
AI-02-B2   Model profiles
AI-02-B3   Normalized invocation
AI-02-B4   Metrics
AI-02-B5   Offline tests
AI-02-B6   Opt-in live connectivity verification
AI-02-C    Closeout / Evidence
```

### AI-02-B1 — Provider skeleton

Deliver: provider profile schema; the `deepseek` and `mimo` profiles of §5.5; credential-reference
resolution per §5.3; the §5.10 error taxonomy as a typed enumeration; the protocol adapter
interface; transport settings shape.
Constraint: **no live network call.** Exercised only through the fake transport.
Also required: revise `config/providers/providers.example.yaml` per §16.1.
Exit: profiles validate; refs resolve to refs; a missing credential yields `CREDENTIAL_MISSING`
and an unsupported ref scheme yields `CREDENTIAL_UNSUPPORTED`, each before any transport activity;
a literal credential value is rejected by schema validation and never sent.

### AI-02-B2 — Model profiles

Deliver: model profile schema; the three §6.4 profiles; every capability initialized to `UNKNOWN`
with `declared: null` except where an actual declared source exists.
Constraint: **no capability may be initialized to `VERIFIED`,** and no limit may be invented.
Exit: profiles validate; the nullability rule holds; no profile asserts an unverified capability.

### AI-02-B3 — Normalized invocation

Deliver: `invocation_request` / `invocation_result` per §7; provider→normalized mapping; the
`LENGTH` / `TOOL_CALLS` / `UNKNOWN` finish-state rules; reasoning separation.
Constraint: no router, no model selection, no fallback.
Exit: layer-2 tests pass; a request for an unverified capability is refused before sending.

### AI-02-B4 — Metrics

Deliver: the §9.1 counters; usage with the zero-vs-unknown rule; latency samples; the pricing
lookup shape.
Constraint: **no hardcoded price**; no cost computed without a pricing record.
Exit: unknown usage survives aggregation as unknown; `estimated_cost` is `null` without pricing.

### AI-02-B5 — Offline tests

Deliver: layers 0–3 wired into CI; fixtures labeled by provenance.

### AI-02-B6 — Opt-in live connectivity verification

Deliver: gated live checks per §11 producing dated evidence.
Exit: each capability is `VERIFIED` (with evidence) or remains `DECLARED` / `NOT_VERIFIED` /
`UNAVAILABLE` / `UNKNOWN` with a recorded reason. **No silent promotion, no `NOT_RUN` reported as
`PASS`.**

### AI-02-C — Closeout / Evidence

Deliver: AI-02 Evidence record; `PROJECT_STATUS.md` and `MASTER_ROADMAP.md` updated; PR reviewed
and merged; contract amendments (if any) folded back into this document.

---

## 14. Exit criteria

### 14.1 AI-02-A exit criteria

- [x] Current real base SHA recorded (§2)
- [x] Current working tree state recorded (§2)
- [x] AI-02 scope frozen (§3)
- [x] DeepSeek provider boundary frozen (§5.5)
- [x] MiMo provider boundary frozen (§5.5)
- [x] Provider contract frozen (§5)
- [x] Model profile contract frozen (§6)
- [x] Capability schema frozen (§8)
- [x] Invocation contract frozen (§7)
- [x] Metrics contract frozen (§9)
- [x] Secret handling boundary frozen (§10)
- [x] Live-test boundary frozen (§11)
- [x] Router explicitly excluded (§3.6)
- [x] OpenAI-compatible generic provider explicitly excluded (§3.7)
- [x] Execution plan committed
- [x] Contains no production implementation
- [x] Contains no real API key
- [x] Contains no real API call
- [x] Relevant CI passes

### 14.2 AI-02-B entry criteria

- [ ] AI-02-A merged
- [ ] `config/providers/providers.example.yaml` revised per §16.1
- [ ] Provider and model profile schemas frozen

### 14.3 AI-02 (full phase) exit criteria

Only when every item below is satisfied:

- [ ] Both provider profiles implemented and validated
- [ ] All three model profiles implemented, with no invented capability
- [ ] Invocation contract implemented and provider-decoupled
- [ ] Metrics collected with unknown-usage accounting intact
- [ ] Pricing is config/metadata; no hardcoded price in core logic
- [ ] Offline test layers 0–3 pass in CI with no credential required
- [ ] Live verification executed and evidenced, or explicitly recorded `NOT_RUN` / `BLOCKED`
- [ ] No secret in any tracked file, fixture, log, or Evidence record
- [ ] Router untouched and unimplemented
- [ ] `openai-compatible` provider untouched and unimplemented
- [ ] SecurityLab untouched
- [ ] Evidence record completed
- [ ] PR reviewed and merged, `PROJECT_STATUS.md` updated

```text
No capability claim is valid without a dated observation behind it.
```

---

## 15. Known external dependencies

| Dependency | Risk | Handling |
| --- | --- | --- |
| DeepSeek API availability and stability | live verification may be `BLOCKED` | `BLOCKED` is a valid recorded outcome (§11.2) |
| MiMo API availability and stability | same | same |
| Declared endpoint URLs | unverified; base URL shapes differ (§5.5) | `DECLARED` until AI-02-B6; no shared `/v1` assumption |
| Declared API model ids | unverified; ids change under stable product names | `DECLARED`; B6 re-verifies; verifications are dated |
| "OpenAI-compatible" claim | partial compatibility in practice | deviations recorded as provider exceptions (§5.4) |
| Provider-reported usage | may be absent or partial | `usage_status: UNKNOWN`; never `0` (§9.2) |
| Provider-reported cache tokens | provider-specific | capability-gated; `null` when unreported |
| Pricing data | changes without notice; may be unpublished | versioned metadata with `effective_from`; cost `null` without a record (§9.3) |
| Credential provisioning on the host | env vars only in v1 | missing/empty ⇒ `CREDENTIAL_MISSING`; unsupported scheme ⇒ `CREDENTIAL_UNSUPPORTED`; both fail-closed (§10.5) |
| Provider rate limits and quotas | unknown until observed | `RATE_LIMIT` vs `QUOTA_EXHAUSTED` distinguished (§5.10) |
| Provider API version drift | breaking change under a stable base URL | dated verification; re-baseline on material change |
| DSH / Codex consumption surface (AI-01 baseline, AI-08) | how the model layer is called is not yet fixed | AI-02 defines a provider-decoupled contract so this does not bind it |
| GitHub `main` branch protection | **BLOCKED** — GitHub Free/private plan (inherited from AI-00) | unchanged; not converted to `PASS` |

---

## 16. Decisions / open questions

### 16.1 Decisions made in AI-02-A

**D-1 — Provider identity and protocol facts live in `providers/<id>/`, as reviewable data.**
Runtime config (`config/providers/`) selects, enables, and overrides — it never redefines
capability. Capability facts need review; endpoints and credentials need configuration. Both
directories already exist in the repository skeleton, so this maps onto the existing layout.

**D-2 — `deepseek` and `mimo` are separate provider profiles despite a shared protocol family**
(§5.6). The adapter is shared; the profiles are not. This preserves per-provider attribution for
metrics, evidence, routing, and benchmarking.

**D-3 — `protocol.family` names the wire protocol, not the vendor.** Both in-scope providers
declare `openai_compatible_chat`.

**D-4 — Base URL and path template are separate fields, and no shared prefix is assumed** (§5.2).
The two in-scope providers declare different base URL shapes; a hardcoded `/v1` would be wrong for
at least one of them.

**D-5 — `model_id` and `display_name` are independent records** (§6.3). A model id is never
derived from a display name by string manipulation, and a display name is never sent to a
provider.

**D-6 — `RATE_LIMIT` / `QUOTA_EXHAUSTED` and `PROTOCOL` / `INVALID_REQUEST` are distinct error
classes** (§5.10). Merging them would cause retry storms against a dead account and would hide
which side broke the contract.

**D-7 — Unknown numbers are `null`, never `0`** (§6.5, §9.2). One rule serving limits, usage, and
cost, because all three fail the same way when a missing measurement is reported as zero.

**D-8 — `json_object` and `json_schema` are different support levels** (§6.7). JSON mode is not
schema enforcement and must not be consumed as though it were.

**D-9 — Reasoning content is a separate field from `text`** (§5.8). The model's thinking and its
answer are different artifacts with different evidentiary weight.

**D-10 — `finish_state: LENGTH` is a truncation warning, not a success** (§7.3).

**D-11 — Pricing is versioned, dated metadata; cost is derived, never hardcoded** (§9.3). Token
counts are the durable metric.

**D-12 — `max_retries` defaults to `0` in AI-02** (§5.11). Retry policy is AI-13's problem;
retries here would inflate live-test cost and mask flakiness.

**D-13 — No model is a default model** (§5.7, §6.4). The model list has no ordering semantics.

**D-14 — A capability is verified only for the model id, endpoint, and date observed** (§11.6).
Verification is a dated observation, not a permanent property.

**D-15 — AI-02-A changes exactly one file: this document.** The contract is frozen here; the
config revision it requires is scoped to AI-02-B1. This keeps the freeze reviewable as a single
artifact and keeps production diff at zero.

**D-16 — `CREDENTIAL_MISSING` and `CREDENTIAL_UNSUPPORTED` are distinct error classes, and a
literal credential value is neither** (§5.3, §5.10). One means the runtime environment supplied no
credential; the other means the reference names a mechanism AI-02 does not implement; a literal is
a configuration defect rejected before runtime. Merging the first two sends an operator to fix the
wrong cause — provisioning a key that was never missing, or editing a correct reference whose
scheme is simply unsupported. This decision supersedes an earlier draft of §5.10 that folded
"unsupported ref scheme" into `CREDENTIAL_MISSING`; §5.3 already required the split, so §5.10 was
the inconsistent side and is corrected.

#### Required config revision — carried by AI-02-B1

`config/providers/providers.example.yaml` currently contradicts the frozen contract and **must be
revised in AI-02-B1, before any provider code is written.** The gaps:

| # | Current state | Contradicts | Required |
| --- | --- | --- | --- |
| 1 | `model: deepseek-flash` — a single scalar model | §5.7, D-13 | a `models: []` list of model refs; never a single default |
| 2 | `mimo: model: ""` — empty, though MiMo has two models | §5.7, §6.4 | both `mimo-v2.6-pro` and `mimo-v2.6-flash` |
| 3 | no protocol declared | §5.4, D-3 | `protocol.family` / `version` per provider |
| 4 | no endpoint declared for DeepSeek or MiMo | §5.2 | declared `base_url` (+ `path_template`), `source: declared` |
| 5 | no transport settings | §5.11, D-12 | explicit timeouts; `max_retries: 0` |
| 6 | `api_key_env: NAME` — a bare variable name | §5.3 | `credential.ref: env:NAME` in the reference grammar |
| 7 | `openai-compatible` present as a peer provider | §3.7 | retained as a **reserved, disabled** future extension point, clearly marked out of AI-02 scope |

Item 7 is deliberate: the entry is not deleted, because AI-09 will need it. It is marked reserved
so that its presence cannot be read as AI-02 scope.

### 16.2 Open questions

Carried into AI-02-B. None changes a frozen boundary; each is an implementation choice.

| # | Question | Needed by | Default if unresolved |
| --- | --- | --- | --- |
| Q-1 | Is `env:` sufficient for v1 credential resolution, or is a config indirection needed? (AI-00 §17 lists credential management as open) | AI-02-B1 | `env:` only; other schemes reserved and fail-closed |
| Q-2 | Do both providers report token usage on every response, including streamed ones? | AI-02-B6 | `usage_status: UNKNOWN`; never `0` |
| Q-3 | Do they report cache read/write tokens, and under what field names? | AI-02-B6 | capability `UNKNOWN`; cache tokens `null` |
| Q-4 | Exact path composition per provider — does the base URL already include a version segment? | AI-02-B6 | `base_url` + `path_template` as declared; verified in B6 |
| Q-5 | Field name and shape of reasoning/thinking output per provider | AI-02-B6 | `reasoning: null`; never merged into `text` |
| Q-6 | Actual streaming support level (SSE vs other) | AI-02-B6 | `streaming` stays `DECLARED`; `stream: true` refused |
| Q-7 | Are `deepseek-flash` and `mimo-v2.6-*` the exact current API model ids? | AI-02-B6 | `DECLARED`; a wrong id surfaces as `INVALID_REQUEST` in B6 |
| Q-8 | Source of truth for pricing data (official page vs manual entry) | AI-02-B4 | `estimated_cost: null`; token counts only |
| Q-9 | Where do model profiles physically live — `providers/<id>/` or `config/providers/`? | AI-02-B2 | D-1: capability data in `providers/<id>/`, runtime overrides in `config/providers/` |
| Q-10 | Should `PROJECT_STATUS.md` be updated now or at AI-02-C? | AI-02-C | at AI-02-C (D-15 keeps this diff to one file; PROJECT_STATUS updates are the merge-checkpoint step) |
| Q-11 | What is the model layer's consumption surface for DSH (AI-08)? | AI-08 | the §7 contract is provider- and Agent-decoupled, so this does not bind AI-02 |

### 16.3 Amendment rule

Any change to a frozen boundary in this document requires an amendment to this document **first**,
with the reason recorded. Implementation must not silently diverge from the freeze, and a
divergence discovered later is corrected in the contract rather than absorbed into the code.

---

## 17. AI-02-A closeout record

```text
Phase              = AI-02-A Contract / Execution Plan / Freeze
Status             = COMPLETE
Base branch        = main
Base SHA           = a804fc9d89a68d2a0d6fbc0fdbb28d864a22b17a
Working tree       = clean at start
Work branch        = feature/ai-02-model-layer-contract
Files changed      = docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md (new)
Production code    = 0 lines changed
Provider code      = not written
Router code        = not written
Plugin code        = not written
Live API calls     = none
Secrets added      = none
```

Success for AI-02-A is **not** "implementation has started". It is that AI-02-B has a binding
implementation contract, constrained jointly by the repository's actual state (§2.1), the AI-00
architecture freeze, and the current declared model facts (§5.5, §6.4).

AI-02-A does not authorise AI-02-B. AI-02-B begins only after this document is merged and its
entry criteria (§14.2) are satisfied.

### 17.1 Amendment log

**Amendment 1 — 2026-09-28 — credential error taxonomy clarification.**

A review of this document found an internal definition conflict. §5.3 already required unsupported
credential reference schemes to fail with `CREDENTIAL_UNSUPPORTED`, while the §5.10 taxonomy table
folded "credential unset/empty, or unsupported ref scheme" into a single `CREDENTIAL_MISSING`
class. §5.3 was the correct side; §5.10 was corrected.

The frozen semantics are now unique across the document:

```text
missing / empty / whitespace  ->  CREDENTIAL_MISSING      (runtime precondition, BLOCKED)
unsupported reference scheme  ->  CREDENTIAL_UNSUPPORTED  (runtime precondition, BLOCKED)
literal credential value      ->  configuration rejection, never sent
```

Corrected in: §5.3 (reference grammar outcomes, rules), §5.10 (taxonomy table, distinction table,
rules), §9.1 (`blocked_count`), §10.3 (literal rejection), §10.5 (fail-closed block), §11.3
(opt-in reason codes), §12.3 (layer-2 assertions), §13 (AI-02-B1 exit criteria), §15 (dependency
table), §16.1 (D-16).

No boundary, scope, or deliverable changed. This is a consistency correction within AI-02-A, not a
scope change: the same correction applied uniformly, with no effect on what AI-02-B is required to
build. Documentation only — still zero production code.

**Amendment 2 — 2026-09-28 — transport ownership.**

A second internal conflict was found between §5.4 and §5.11. §5.4 rule 2 stated that "the provider
profile determines endpoint, credential, and transport", while §5.11 closes with "Transport
settings are runtime config, not profile data."

§5.11 governs. §5.4 rule 2 was the inconsistent side and is corrected:

```text
The provider profile determines endpoint, credential, and protocol.
Runtime config supplies transport settings.
```

This amendment makes the document match the AI-02-B1 implementation, which had followed §5.4
rule 2 and placed a `transport` field on the provider profile. That was corrected in the
implementation before this amendment: `ProviderProfile` no longer has the field, the loader
rejects a profile carrying one, and the adapter takes transport settings as an explicit runtime
input. The document now describes that layering rather than contradicting it.

Corrected in: §5.4 (rule 2). The §5.11 text was already correct and is unchanged.

The layer split is unchanged from what §5.11 already required:

```text
providers/<id>/provider.yaml    identity, protocol, endpoint, credential.ref, models
config/providers/*.yaml         enabled, runtime overrides, transport
```

No other frozen semantics changed — not the provider/model two-level structure, provider
identity, endpoint composition, the credential reference grammar, protocol family, model
references, the capability truth model, the error taxonomy, retry policy, live-test rules, or
the Router and AI-09 exclusions. Documentation only: zero production code, one file.

**Amendment 3 — 2026-09-28 — §5.4 illustrative YAML.**

The illustrative YAML in §5.4 was over-specified. It showed four fields:

```yaml
protocol:
  family: openai_compatible_chat
  version: v1
  streaming: sse        # removed
  source: declared      # removed
```

Neither of the two removed fields is a Protocol field, and no rule in §5.4 defined either:

- `streaming` belongs to the **model capability** layer, defined in §6.7 under the truth model —
  object-shaped (`declared` / `verified` / `status` / `source`) and AI-02-B2 scope. A scalar
  `protocol.streaming` would be a second, differently-shaped field with the same name, and would
  assert a capability claim §8.3 forbids asserting without evidence.
- `source` is provenance, recorded where the endpoint schema (§5.2) and the capability schema
  (§6.8) define it. §5.4 assigned it no meaning.

The illustrative block is therefore reduced to the two fields §5.4 actually defines:

```yaml
protocol:
  family: openai_compatible_chat
  version: v1
```

This matches the concrete in-scope provider profiles in §5.5, the `Protocol` type in the AI-02-B1
implementation, and the B1 phase specification. A one-line clarification now follows the block.

This correction only removes ambiguous illustrative fields. It creates no new field, no new
semantics, and changes nothing about the protocol family, the adapter, or any provider
declaration. §6.7 and §6.8 are unchanged and remain the sole definition of `streaming` and of
capability `source`. No boundary, scope, or implementation change: documentation only, zero
production code, one file.

**Amendment 4 — 2026-09-28 — invocation-layer block representation.**

§7.2 defined `status: BLOCKED` but never said how a *pre-flight refusal* is represented. It
stated only that `error` carries the §5.9 shape when `status != SUCCESS`, which presumes a
provider-layer failure — and a refusal has none, because no provider was contacted.

AI-02-B3 must distinguish a provider failure from a pre-flight policy refusal, so this amendment
adds an optional `blocked` field to the §7.2 result and states the rules explicitly. The
previous text is otherwise unchanged.

What the amendment settles:

1. `BLOCKED` means refused before any provider activity, so `finish_state` is **`UNKNOWN`**.
   `finish_state: ERROR` is reserved for a provider signalling failure (§7.3) and is never used
   for a refusal.
2. An invocation-layer refusal populates `blocked` and leaves `error` null. Its `code` is one of
   `CAPABILITY_NOT_VERIFIED`, `UNKNOWN_PROVIDER`, `UNKNOWN_MODEL`, `CREDENTIAL_CONFIG_DEFECT`.
3. A credential precondition populates `error` with `CREDENTIAL_MISSING` or
   `CREDENTIAL_UNSUPPORTED` — both already frozen taxonomy classes — and leaves `blocked` null.
4. **No new provider `ErrorClass` is added**, and the §5.10 taxonomy is unchanged. Reusing an
   existing class for a policy refusal would blur the boundary D-6 and D-16 draw, and would
   imply a provider interaction that never happened.

`blocked` is a field on the invocation result, not a member of the provider error taxonomy. The
two represent different layers and are deliberately not merged.

No other frozen semantics changed: not the provider/model two-level structure, provider identity,
endpoint composition, the credential reference grammar, protocol family, model references, the
capability truth model, the error taxonomy, retry policy, live-test rules, or the Router and
AI-09 exclusions.
