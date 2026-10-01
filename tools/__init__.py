"""The eight AI-06 adapter families, and the default registry.

AI-00 **F-14** freezes the split this package exists for:

> *"Research tool adapters are separate from the Security Tools plugin."*

```text
plugins/security_tools/    the plugin: the Tool API, the registry, the boundaries
tools/<family>/            the adapters: one package per family
```

**The dependency runs one way.** An adapter imports the protocol from
`plugins.security_tools`; `plugins.security_tools` never imports `tools.*`, so
there is no cycle and the plugin stays importable on its own. This module is the
only place that knows about both halves.

### Registration is static (contract §7.5)

The default registry is built from the fixed tuple below. There is no runtime
discovery, no remote manifest and no dynamic plugin loading — that boundary is
AI-00 §17's open question, and AI-06 does not resolve it by inventing a loader.
"""

from __future__ import annotations

from plugins.security_tools.registry import ToolRegistry

from tools import (
    firmware,
    git,
    github,
    mcp,
    reverse_engineering,
    terminal,
    tests,
    vehicle_network,
)

__all__ = ["ADAPTERS", "default_registry"]

#: Every family, in the order the roadmap lists them. Each is a module exposing
#: an `Adapter` class; the registry is built from these and nothing else.
ADAPTERS = (
    git.Adapter,
    github.Adapter,
    tests.Adapter,
    terminal.Adapter,
    mcp.Adapter,
    vehicle_network.Adapter,
    firmware.Adapter,
    reverse_engineering.Adapter,
)


def default_registry() -> ToolRegistry:
    """The v1 registry: all eight families, statically declared."""
    return ToolRegistry(tuple(adapter() for adapter in ADAPTERS))
