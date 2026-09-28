# Providers

Model provider adapters and capability descriptions.

## Boundary

```text
Agent
  |
Provider          endpoint / authentication / protocol     <- this directory
  |
Model             model id / capability metadata / limits  <- AI-02-B2
```

A provider profile owns identity, endpoint, protocol, and the credential
reference. It does **not** own transport settings and does **not** own model
capability. Capability is a model profile's job (AI-02-B2).

## Layer split

```text
providers/<id>/provider.yaml    identity, protocol, endpoint,
                                credential.ref, models
config/providers/*.yaml         enabled, runtime overrides, transport
```

**Transport settings are runtime config, not profile data (§5.11).** Timeouts,
retries, and TLS verification live in `config/providers/*.yaml` and are passed
to the adapter explicitly as `transport_settings`.

The split is enforced structurally rather than by convention:

- `ProviderProfile` has no `transport` field, so the adapter cannot read one
- the loader **rejects** a provider profile that carries a `transport:` block
- `build_request()` requires `transport_settings`, so the runtime input cannot
  be skipped

## Layout

```text
providers/
  errors.py            typed error taxonomy          (contract §5.9, §5.10)
  redaction.py         credential redaction          (contract §10.3)
  credential.py        reference grammar + resolver  (contract §5.3)
  transport.py         transport settings TYPE       (runtime config, §5.11)
  profile.py           profile types                 (contract §5.1 - §5.7)
  registry.py          profile loading
  config.py            runtime config loading
  validate.py          offline validation entry point
  protocol/
    base.py                      adapter interface, envelope, transport interface
    openai_compatible_chat.py    shared adapter for both in-scope providers
  model_profile.py     model profile types           (contract §6, §8)
  model_registry.py    model profile loading
  invocation.py        normalized invocation         (contract §7, §5.8)
  deepseek/provider.yaml         declared provider profile
  deepseek/models/*.yaml         declared model profiles
  mimo/provider.yaml             declared provider profile
  mimo/models/*.yaml             declared model profiles
  openai-compatible/             RESERVED — not implemented, see below
```

## Model profiles

Model profiles live beside the provider that exposes them, at
`providers/<provider_id>/models/<model_id>.yaml`. They are reviewable data,
not runtime config, and the filename and directory are part of the identity
contract: a profile whose `model_id` disagrees with its filename, or whose
`provider_id` disagrees with its directory, is rejected on load.

| Model ref | display name | limits | capabilities |
| --- | --- | --- | --- |
| `deepseek/deepseek-flash` | `DeepSeek-V4.1-Flash` | unknown | UNKNOWN |
| `mimo/mimo-v2.6-pro` | `MiMo-V2.6-Pro` | unknown | UNKNOWN |
| `mimo/mimo-v2.6-flash` | `MiMo-V2.6-Flash` | unknown | UNKNOWN |

Three models, and that is the whole AI-02 scope. None is a default.

### The truth model, and why the profiles assert nothing

Every capability carries **two axes**: `declared` (what an external source
claims) and `verified` (what the Workbench observed), plus a `status` from the
five frozen states. They are never collapsed into one boolean.

```
DECLARED      an external source claims it; no Workbench execution
VERIFIED      the Workbench observed it working, with evidence
NOT_VERIFIED  verification was attempted and was inconclusive
UNAVAILABLE   the Workbench observed it absent or rejected
UNKNOWN       no claim and no observation
```

**No shipped capability is anything but `UNKNOWN`**, and every limit is
`null`. This is not an unfinished profile — it is the honest record. Nobody
has checked, so nothing is claimed:

- `UNKNOWN` is not `false`. Unknown means unknown.
- `declared: null` does not mean "unsupported"; it means nobody said.
- A guessed context limit is worse than an absent one: it silently truncates
  real work.
- Capability is never inferred from a name. `Pro`, `Flash`, `V4.1` are not
  evidence of anything.
- Only AI-02-B6 may promote a capability, and only from a dated observation.

A profile declaring `VERIFIED` must carry `verified_at` and `evidence_ref`;
the schema rejects the claim without them. `structured_output` additionally
records a `mode`, because `json_object` guarantees JSON but **not** schema
conformance, and the two must never be consumed alike.

## Providers in scope

| Provider | Profile | Models |
| --- | --- | --- |
| `deepseek` | [`deepseek/provider.yaml`](deepseek/provider.yaml) | `deepseek/deepseek-flash` |
| `mimo` | [`mimo/provider.yaml`](mimo/provider.yaml) | `mimo/mimo-v2.6-pro`, `mimo/mimo-v2.6-flash` |

Both declare the `openai_compatible_chat` protocol family and therefore share
one adapter. They keep **separate profiles**, because endpoints, credentials,
availability, and compatibility gaps all differ and metrics must attribute a
request to a real provider.

Everything in these profiles is `DECLARED`, not `VERIFIED`. Only AI-02-B6 may
promote a capability, and only from a dated observation.

## `openai-compatible/` is reserved

The directory is a placeholder for **AI-09**. It has no profile, no adapter,
and no implementation, and the config entry that references it is marked
`reserved: true` and must stay disabled. Sharing a protocol family with
DeepSeek and MiMo does not make this a third implemented provider.

## Invocation

`Invoker.invoke(request)` is the normalized boundary. A caller builds an
`InvocationRequest` and reads an `InvocationResult`; it never sees a
provider's JSON, and attribution (`provider_id` / `model_id` / `model_ref`)
travels on the result rather than being inferred from a payload.

```text
InvocationRequest  ->  model resolution  ->  capability gate
                   ->  credential resolution  ->  protocol adapter
                   ->  transport  ->  InvocationResult
```

**The capability gate refuses before any provider activity.** Tools,
structured output, and `stream: true` each require their capability to be
`VERIFIED`; `UNKNOWN`, `NOT_VERIFIED`, `DECLARED` and `UNAVAILABLE` all refuse,
and a blocked call performs zero transport calls. `stream: true` is never
silently downgraded to `false`.

Since every shipped capability is `UNKNOWN`, only plain text calls can reach a
transport today.

`status` is the only success signal. `LENGTH` on a successful call means the
answer is **truncated**, not complete; `UNKNOWN` never collapses to `STOP`;
and a tool call is neither an error nor a final answer.

A pre-flight refusal carries a `BlockReason`, not a provider `ErrorClass`:
no provider was contacted, so no provider-layer class applies. Reusing one
would blur a policy decision with something a provider did.

## Rules

- **No credentials.** Profiles and config carry `credential.ref` in the frozen
  grammar (`env:<VAR_NAME>`), never a value. A literal in a ref field is
  rejected at validation.
- **No network.** AI-02 ships no HTTP transport. `Transport` is an interface;
  the test suite supplies a fake, and no shipped code path can open a
  provider connection.
- **No `/v1` inference.** `effective_url = base_url + path_template`, exactly.
  No prefix is injected.
- **No transport in profiles.** Transport settings are runtime config (§5.11);
  a profile carrying them is rejected on load.
- **No retries.** `max_retries` is 0 and AI-02 implements no retry loop.
- **No default model.** The model list has no ordering semantics.

Validate offline, with no API key present:

```bash
python -m providers.validate
python -m pytest
```
