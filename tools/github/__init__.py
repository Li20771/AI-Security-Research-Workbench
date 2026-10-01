"""AI-06 GitHub adapter. Contract §13.2. **The boundary, and no operation.**

```text
FROZEN: v1 defines the adapter boundary and no networked operation.
```

The roadmap lists GitHub as a first-class family, and this adapter declines to
open it. That is deliberate rather than unfinished.

AI-02 spent four sub-phases making live network access opt-in, allowlisted,
manual and non-default, and its evidence records that **no provider call has ever
been made**. An adapter that reached the network because "a tool exists" would
undo that in one commit. §16 forbids a network-capable operation in v1, so this
family declares none — and declaring none is the honest state, not a gap.

### What the boundary is for

The class below is a real `ToolAdapter` with a real descriptor, registered in the
default registry, held to the same protocol as the other seven families. What it
does not have is something to run. When a later phase declares a GitHub
operation, it must declare `network: true`, and a test in this repository asserts
that no operation anywhere in v1 does.
"""

from __future__ import annotations

from plugins.security_tools.adapter import AdapterOutcome, Invocation
from plugins.security_tools.descriptor import ToolDescriptor
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import AdapterFamily, ToolOutcome

__all__ = ["Adapter", "OPERATION_NAMES", "TOOL_ID", "TOOL_VERSION"]

TOOL_ID = "github"
TOOL_VERSION = "1.0.0"

#: Empty, and that is the v1 decision (§13.2).
OPERATIONS: tuple = ()

OPERATION_NAMES = ()


class Adapter:
    """The GitHub family, with no operation to invoke."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.GITHUB),
            summary=(
                "GitHub adapter boundary. v1 declares no operation: every GitHub "
                "operation would need the network, and no v1 operation may (§16)"
            ),
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        # Unreachable: the registry has no operation to look up, so dispatch
        # refuses with UNKNOWN_OPERATION before any adapter is called.
        return AdapterOutcome.of(ToolOutcome.UNKNOWN, "NO_OPERATION_DECLARED")
