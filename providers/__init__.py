"""Provider / Model layer.

Implements the frozen AI-02 contract in
`docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md`:

    Agent
      |
    Provider     identity / protocol / endpoint / credential   <- AI-02-B1
      |
    Model        identity / limits / modality / capabilities   <- AI-02-B2

    Runtime config supplies transport settings (contract §5.11), which is why
    `transport.py` is a settings type rather than a field on a profile.

Implemented so far:

- **AI-02-B1** — provider profile schema, the `deepseek` and `mimo` provider
  profiles, credential reference resolution, the typed error taxonomy, the
  protocol adapter interface, and the transport settings shape.
- **AI-02-B2** — model profile schema, the three in-scope model profiles,
  model registry/loading, and provider <-> model reference validation.

Not implemented, by contract: normalized invocation (AI-02-B3), metrics
(AI-02-B4), live connectivity verification (AI-02-B6), Model Router (AI-07),
and the generic `openai_compatible_chat` *provider* at
`providers/openai-compatible/`, which stays a reserved extension point for
AI-09.

No capability in this package is VERIFIED. Every shipped capability is
UNKNOWN and every limit is null, because nothing has been observed yet. Only
AI-02-B6 may promote a capability, and only from a dated observation.

This package performs no network I/O. `Transport` is an interface with no
concrete implementation here; the test suite supplies a fake.
"""

from __future__ import annotations

__all__ = [
    "credential",
    "errors",
    "profile",
    "protocol",
    "redaction",
    "registry",
    "transport",
]
