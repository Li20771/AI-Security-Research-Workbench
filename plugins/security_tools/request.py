"""The tool request — what is being asked for (contract §6).

A `ToolRequest` is not, and MUST NOT contain, a free-form command line (§5.1).
It names a declared operation and supplies arguments to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from plugins.guard.models import Actor, ApprovalRef, TargetRef

from plugins.security_tools.errors import (
    PermissionLevelMissing,
    TimeoutMissing,
    ToolRequestMalformed,
)
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import PermissionLevel

__all__ = ["ToolRequest", "ToolWorkspace"]

_TOP_KEYS = frozenset(
    {
        "schema_version",
        "workspace",
        "tool",
        "operation",
        "arguments",
        "actor",
        "permission_level",
        "target",
        "execution",
        "approval",
    }
)

_IDENT_ALLOWED = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


@dataclass(frozen=True, slots=True)
class ToolWorkspace:
    """The workspace an invocation belongs to (contract §6.1, §10).

    `root` is **declared**. It is never discovered: no upward search, no sibling
    scan, no registry lookup, no inference from the current working directory
    (§10.2). When it is absent, an operation that needs a filesystem is refused
    rather than defaulting to anything.
    """

    workspace_id: str
    root: str | None = None

    @classmethod
    def from_mapping(cls, raw: object, where: str = "workspace") -> "ToolWorkspace":
        if not isinstance(raw, Mapping):
            raise ToolRequestMalformed(f"{where} must be an object")
        unknown = set(raw) - {"workspace_id", "root"}
        if unknown:
            raise ToolRequestMalformed(
                f"{where} has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, unknown)))}"
            )
        workspace_id = raw.get("workspace_id")
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ToolRequestMalformed(f"{where}.workspace_id must be non-empty")
        root = raw.get("root")
        if root is not None and not isinstance(root, str):
            raise ToolRequestMalformed(f"{where}.root must be a string or null")
        return cls(workspace_id=workspace_id, root=root)


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """§6.1. The complete invocation, minus the policy and minus the tool.

    `permission_level` is **REQUIRED and supplied** (§6.2). There is no
    constructor path that derives it, and `from_mapping` refuses a request that
    omits it rather than defaulting to anything.
    """

    workspace: ToolWorkspace
    tool: ToolIdentity
    operation: str
    actor: Actor
    permission_level: PermissionLevel
    target: TargetRef
    timeout_seconds: int
    arguments: Mapping[str, Any] = None  # type: ignore[assignment]
    environment: Mapping[str, str] = None  # type: ignore[assignment]
    approval: ApprovalRef | None = None
    schema_version: int = 1

    @classmethod
    def from_mapping(cls, raw: object) -> "ToolRequest":
        """Parse a supplied request, refusing anything §6.1 does not define."""
        if not isinstance(raw, Mapping):
            raise ToolRequestMalformed("request must be an object")

        unknown = set(raw) - _TOP_KEYS
        if unknown:
            raise ToolRequestMalformed(
                f"unknown request field(s): {', '.join(sorted(map(str, unknown)))}. "
                "§6.1 fixes the request shape; a field AI-06 does not define is "
                "refused rather than ignored, so a credential or a command string "
                "cannot ride along unremarked"
            )

        version = raw.get("schema_version")
        if version != 1:
            raise ToolRequestMalformed(
                f"schema_version {version!r} is not supported; this contract defines 1"
            )

        # §6.2. Checked before anything else about the request, because a
        # request without a level is not one to repair — it is one to refuse.
        if "permission_level" not in raw or raw["permission_level"] is None:
            raise PermissionLevelMissing(
                "request.permission_level is REQUIRED (§6.2). AI-06 never infers "
                "the level from an operation name, a tool_id or a target: "
                "privilege is supplied by the caller or the request is refused"
            )
        try:
            level = PermissionLevel(raw["permission_level"])
        except ValueError:
            raise ToolRequestMalformed(
                "request.permission_level is not one of AI-04's six levels"
            ) from None

        execution = raw.get("execution")
        if not isinstance(execution, Mapping):
            raise ToolRequestMalformed("request.execution must be an object")
        unknown_execution = set(execution) - {"timeout_seconds", "environment"}
        if unknown_execution:
            raise ToolRequestMalformed(
                "request.execution has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, unknown_execution)))}"
            )
        # §11.3. There is no default and no "no timeout".
        timeout = execution.get("timeout_seconds")
        if timeout is None:
            raise TimeoutMissing(
                "request.execution.timeout_seconds is REQUIRED (§11.3). There is "
                "no default and no unbounded execution: a tool that hangs is a "
                "tool that has taken the session with it"
            )
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise ToolRequestMalformed(
                "request.execution.timeout_seconds must be a positive integer"
            )

        environment = execution.get("environment", {})
        if not isinstance(environment, Mapping):
            raise ToolRequestMalformed("request.execution.environment must be an object")
        for key, value in environment.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ToolRequestMalformed(
                    "request.execution.environment must map strings to strings"
                )

        operation = raw.get("operation")
        if not isinstance(operation, str) or not operation:
            raise ToolRequestMalformed("request.operation must be a non-empty string")
        if len(operation) > 64 or not set(operation) <= _IDENT_ALLOWED:
            raise ToolRequestMalformed(
                "request.operation must be a bounded machine token"
            )

        arguments = raw.get("arguments", {})
        if not isinstance(arguments, Mapping):
            raise ToolRequestMalformed("request.arguments must be an object")

        actor_raw = raw.get("actor")
        target_raw = raw.get("target")
        if not isinstance(actor_raw, Mapping):
            raise ToolRequestMalformed("request.actor must be an object")
        if not isinstance(target_raw, Mapping):
            raise ToolRequestMalformed("request.target must be an object")

        approval_raw = raw.get("approval")
        approval = (
            None
            if approval_raw is None
            else ApprovalRef.from_mapping(_as_mapping(approval_raw, "approval"))
        )

        return cls(
            workspace=ToolWorkspace.from_mapping(raw.get("workspace")),
            tool=ToolIdentity.from_mapping(raw.get("tool")),
            operation=operation,
            actor=Actor.from_mapping(_as_mapping(actor_raw, "actor")),
            permission_level=level,
            target=TargetRef.from_mapping(_as_mapping(target_raw, "target")),
            timeout_seconds=timeout,
            arguments=dict(arguments),
            environment=dict(environment),
            approval=approval,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workspace": {
                "workspace_id": self.workspace.workspace_id,
                "root": self.workspace.root,
            },
            "tool": self.tool.to_mapping(),
            "operation": self.operation,
            "arguments": dict(self.arguments),
            "actor": self.actor.to_dict(),
            "permission_level": str(self.permission_level),
            "target": self.target.to_dict(),
            "execution": {
                "timeout_seconds": self.timeout_seconds,
                "environment": dict(self.environment),
            },
            "approval": None if self.approval is None else self.approval.to_dict(),
        }


def _as_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolRequestMalformed(f"request.{where} must be an object")
    return value
