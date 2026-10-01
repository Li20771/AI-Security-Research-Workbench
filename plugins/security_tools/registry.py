"""The tool registry — a description, never an authorization (contract §7.4).

```text
Registry describes.   Guard authorizes.   Adapter executes.
```

The registry answers *what tools exist, what operations they declare, what those
operations need*. It does **not** hold a policy, call Guard, issue an ALLOW, or
refuse a request that should have been Guard's to refuse. A registry that decided
authorization would be the second permission system this contract exists to
prevent.

Registration is **static** (§7.5): the v1 registry is built from a fixed,
in-repository declaration. There is no runtime discovery, no remote manifest and
no dynamic plugin loading — that boundary is AI-00 §17's open question and AI-06
does not resolve it by inventing a loader.
"""

from __future__ import annotations

from plugins.security_tools.adapter import ToolAdapter
from plugins.security_tools.descriptor import OperationSpec, ToolDescriptor
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import AdapterFamily

__all__ = ["ToolRegistry"]


class ToolRegistry:
    """A fixed map from `(tool_id, tool_version)` to a descriptor and an adapter."""

    def __init__(self, adapters: tuple[ToolAdapter, ...] = ()) -> None:
        self._adapters: dict[tuple[str, str], ToolAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    # ------------------------------------------------------------------
    # description
    # ------------------------------------------------------------------

    def register(self, adapter: ToolAdapter) -> None:
        """Add one adapter. A duplicate identity is refused, not overwritten."""
        identity = adapter.descriptor.identity
        key = (identity.tool_id, identity.tool_version)
        if key in self._adapters:
            raise ValueError(
                "two adapters declare the same tool_id and tool_version; the "
                "registry refuses the collision rather than letting the last "
                "registration win"
            )
        self._adapters[key] = adapter

    @property
    def identities(self) -> tuple[ToolIdentity, ...]:
        return tuple(
            adapter.descriptor.identity for adapter in self._adapters.values()
        )

    @property
    def families(self) -> frozenset[AdapterFamily]:
        """Which families are actually represented here.

        A description of this registry, not the frozen vocabulary — §5.3's set is
        checked against `AdapterFamily` itself, and a test does that.
        """
        return frozenset(
            adapter.descriptor.identity.adapter_family
            for adapter in self._adapters.values()
        )

    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(adapter.descriptor for adapter in self._adapters.values())

    def descriptor_for(self, identity: ToolIdentity) -> ToolDescriptor | None:
        adapter = self._adapters.get((identity.tool_id, identity.tool_version))
        return None if adapter is None else adapter.descriptor

    def adapter_for(self, identity: ToolIdentity) -> ToolAdapter | None:
        return self._adapters.get((identity.tool_id, identity.tool_version))

    def operation_for(self, identity: ToolIdentity, operation: str) -> OperationSpec | None:
        descriptor = self.descriptor_for(identity)
        return None if descriptor is None else descriptor.operation(operation)

    def capability_names(self, identity: ToolIdentity) -> tuple[str, ...]:
        descriptor = self.descriptor_for(identity)
        return () if descriptor is None else descriptor.capability_names
