"""AI-06 MCP adapter. Contract §13.5. **The boundary, and no operation.**

`tools/mcp/README.md` already states the rule this adapter implements:

> *"MCP connectivity is a capability only. Guard determines whether a server,
> resource, or action is eligible in the current context."*

### What v1 does not build

```text
MCP server discovery        a marketplace              a credential manager
unbounded dynamic tool loading   any network operation
```

The point of the boundary is that a later phase has somewhere to stand, and that
AI-06-B can test the adapter protocol against a shape that is not git. It is not
a platform, and building the platform here would be scope the contract declines.

Like `github`, this family declares no operation, because §16 forbids a
network-capable operation in v1. The adapter is real, registered and held to the
uniform protocol — what it does not have is something to reach.
"""

from __future__ import annotations

from plugins.security_tools.adapter import AdapterOutcome, Invocation
from plugins.security_tools.descriptor import ToolDescriptor
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import AdapterFamily, ToolOutcome

__all__ = ["Adapter", "OPERATION_NAMES", "TOOL_ID", "TOOL_VERSION"]

TOOL_ID = "mcp"
TOOL_VERSION = "1.0.0"

#: Empty, and that is the v1 decision (§13.5, §16).
OPERATIONS: tuple = ()

OPERATION_NAMES = ()


class Adapter:
    """The MCP family, with no operation to invoke."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.MCP),
            summary=(
                "MCP adapter boundary. v1 declares no operation: reaching a "
                "server would need the network, and no v1 operation may (§16)"
            ),
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        # Unreachable: dispatch refuses with UNKNOWN_OPERATION first.
        return AdapterOutcome.of(ToolOutcome.UNKNOWN, "NO_OPERATION_DECLARED")
