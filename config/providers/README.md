# providers (runtime config)

Runtime configuration for the Workbench provider layer.

## Layer boundary

```text
providers/<id>/provider.yaml    reviewable identity and protocol facts
config/providers/*.yaml         runtime selection, enablement, overrides
```

This directory selects and enables. It does not define identity or protocol —
that is `providers/`' job, reviewed like code. Runtime config never redefines
capability.

## Files

- `providers.example.yaml` — the reference shape. Copy to `providers.yaml` to
  use. `providers.yaml` carries local overrides and is never committed with a
  credential value.

## Rules

- **References, not values.** Credentials appear as `credential.ref` in the
  frozen grammar `env:<VAR_NAME>`. Any other scheme is reserved and
  unimplemented. A bare credential value here is a configuration defect: it is
  rejected at validation, never resolved, and never sent.
- **Fail-closed.** A provider without an explicit `enabled: true` is disabled,
  and everything ships disabled because nothing has been verified.
- **Reserved entries stay disabled.** `openai-compatible` is an AI-09
  extension point. It must keep `reserved: true` and `enabled: false`.
- **No secrets.** `.env` remains gitignored; the preflight CI check that no
  `.env`, `*.pem`, or `*.key` file is present still applies.

## Validation

```bash
python -m providers.validate
```

Validates both registered profiles and this example against the frozen AI-02
contract. It performs no network I/O and requires no API key.
