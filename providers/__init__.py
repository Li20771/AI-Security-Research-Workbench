"""Provider / Model layer.

AI-02-B1 — Provider skeleton. Implements the provider half of the frozen
AI-02 contract in `docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md`:

    Agent
      |
    Provider     endpoint / authentication / protocol / transport   <- this package
      |
    Model        identity / capability metadata / limits            <- AI-02-B2

Scope of this phase: provider profile schema, the `deepseek` and `mimo`
profiles, credential reference resolution, the typed error taxonomy, the
protocol adapter interface, and the transport settings shape.

Not in this phase, by contract: model capability profiles (AI-02-B2),
normalized invocation (AI-02-B3), metrics (AI-02-B4), live connectivity
verification (AI-02-B6), Model Router (AI-07), and the generic
`openai_compatible_chat` *provider* at `providers/openai-compatible/`, which
stays a reserved extension point for AI-09.

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
