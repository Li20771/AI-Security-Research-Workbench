"""Tool identity — what a tool IS (contract §5).

Three things are kept apart and never collapsed into one:

```text
tool identity      what the tool IS             this module
tool invocation    what is being asked for      request.py
tool result        what happened                result.py
```

A shell string is none of these. `ToolIdentity` says *which tool, which version,
which family* and nothing about what it is being asked to do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from plugins.security_tools.errors import ToolRequestMalformed
from plugins.security_tools.vocabulary import AdapterFamily

__all__ = ["ToolIdentity"]

#: `G-IDENT`'s shape, reused rather than restated: a stable identifier is a
#: bounded machine token, and AI-05 already paid for the grammar.
_IDENT_ALLOWED = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def _ident(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ToolRequestMalformed(f"{field} must be a non-empty string")
    if len(value) > 64:
        raise ToolRequestMalformed(f"{field} must be at most 64 characters")
    if not set(value) <= _IDENT_ALLOWED:
        raise ToolRequestMalformed(
            f"{field} must contain only letters, digits, dot, underscore or hyphen"
        )
    return value


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """§5.2. `tool_id` is stable across versions; `adapter_family` is closed.

    **This is never an authorization input** (§5.2, §6.2). Neither the id nor the
    family nor the version may be consulted to decide a `permission_level`; that
    would be deciding privilege from a name, which is the defect F-09 exists to
    prevent.
    """

    tool_id: str
    tool_version: str
    adapter_family: AdapterFamily

    @classmethod
    def from_mapping(cls, raw: object, where: str = "tool") -> "ToolIdentity":
        if not isinstance(raw, Mapping):
            raise ToolRequestMalformed(f"{where} must be an object")
        unknown = set(raw) - {"tool_id", "tool_version", "adapter_family"}
        if unknown:
            raise ToolRequestMalformed(
                f"{where} has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, unknown)))}"
            )
        family = raw.get("adapter_family")
        try:
            parsed = AdapterFamily(family)
        except ValueError:
            raise ToolRequestMalformed(
                f"{where}.adapter_family is not one of the eight families (§5.3)"
            ) from None
        return cls(
            tool_id=_ident(raw.get("tool_id"), f"{where}.tool_id"),
            tool_version=_ident(raw.get("tool_version"), f"{where}.tool_version"),
            adapter_family=parsed,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "adapter_family": str(self.adapter_family),
        }

    def __str__(self) -> str:
        return f"{self.tool_id}@{self.tool_version}"
