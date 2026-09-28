# Providers

Model provider adapters and capability descriptions.

## Boundary

```text
Agent
  |
Provider          endpoint / authentication / protocol / transport   <- this directory
  |
Model             model id / capability metadata / limits            <- AI-02-B2
```

A provider profile owns transport and protocol. It does not own model
capability: that is a model profile's job, and it arrives in AI-02-B2.

## Layout

```text
providers/
  errors.py            typed error taxonomy          (contract §5.9, §5.10)
  redaction.py         credential redaction          (contract §10.3)
  credential.py        reference grammar + resolver  (contract §5.3)
  transport.py         transport settings            (contract §5.11)
  profile.py           profile types                 (contract §5.1 - §5.7)
  registry.py          profile loading
  config.py            runtime config loading
  validate.py          offline validation entry point
  protocol/
    base.py                      adapter interface, envelope, transport interface
    openai_compatible_chat.py    shared adapter for both in-scope providers
  deepseek/provider.yaml         declared profile
  mimo/provider.yaml             declared profile
  openai-compatible/             RESERVED — not implemented, see below
```

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

## Rules

- **No credentials.** Profiles and config carry `credential.ref` in the frozen
  grammar (`env:<VAR_NAME>`), never a value. A literal in a ref field is
  rejected at validation.
- **No network.** AI-02 ships no HTTP transport. `Transport` is an interface;
  the test suite supplies a fake, and no shipped code path can open a
  provider connection.
- **No `/v1` inference.** `effective_url = base_url + path_template`, exactly.
  No prefix is injected.
- **No retries.** `max_retries` is 0 and AI-02 implements no retry loop.
- **No default model.** The model list has no ordering semantics.

Validate offline, with no API key present:

```bash
python -m providers.validate
python -m pytest
```
