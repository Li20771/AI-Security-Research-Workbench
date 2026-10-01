"""AI-06 git adapter. Contract §13.1. **Read-only, and nothing else.**

```text
FROZEN: no operation in v1 performs a write to git. There is no commit, no push,
        no merge, no reset, no checkout, no branch mutation, and no history
        rewrite.
```

AI-03 already freezes a read-only git reader and asserts its refusals by executing
the guard. This adapter does not widen that. The write verbs do not exist here to
be refused — they were never declared, and a test asserts the registry contains
no operation that could write.
"""

from __future__ import annotations

from typing import Any

from plugins.security_tools.adapter import AdapterOutcome, Invocation, execute_argv
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
from plugins.security_tools.errors import PathEscapesWorkspace
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.paths import contained_path, resolve_root
from plugins.security_tools.vocabulary import (
    AdapterFamily,
    FilesystemAccess,
    PermissionLevel,
    TargetKind,
    ToolOutcome,
)

__all__ = ["Adapter", "OPERATION_NAMES", "TOOL_ID", "TOOL_VERSION"]

TOOL_ID = "git"
TOOL_VERSION = "1.0.0"

_SUBPROCESS = EnvironmentRequirement(
    filesystem=FilesystemAccess.READ, subprocess=True
)

#: Every operation reads. The floor is `read` for all six, which is a statement
#: about what git is being asked to do here and not a grant (§7.2).
OPERATIONS: tuple[OperationSpec, ...] = (
    OperationSpec(
        name="status",
        permission_level_floor=PermissionLevel.READ,
        summary="the working tree's status, porcelain",
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
    ),
    OperationSpec(
        name="current_sha",
        permission_level_floor=PermissionLevel.READ,
        summary="the commit the working tree is on",
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
    ),
    OperationSpec(
        name="current_branch",
        permission_level_floor=PermissionLevel.READ,
        summary="the branch name, or empty on a detached HEAD",
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
    ),
    OperationSpec(
        name="diff",
        permission_level_floor=PermissionLevel.READ,
        summary="the working tree diff, optionally against a revision",
        arguments=(ArgumentSpec("against", "string", required=False, maximum_length=128),),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
    ),
    OperationSpec(
        name="log",
        permission_level_floor=PermissionLevel.READ,
        summary="recent commits, one line each",
        arguments=(ArgumentSpec("limit", "integer", required=False),),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
    ),
    OperationSpec(
        name="read_file",
        permission_level_floor=PermissionLevel.READ,
        summary="one file's bytes, confined to the workspace root",
        arguments=(ArgumentSpec("path", "string", maximum_length=512),),
        environment=EnvironmentRequirement(filesystem=FilesystemAccess.READ),
        target_kinds=(TargetKind.REPOSITORY, TargetKind.FILESYSTEM),
    ),
)

OPERATION_NAMES = tuple(spec.name for spec in OPERATIONS)

#: The git verbs this adapter will ever put on an argv. A closed set, so a
#: mutation cannot be introduced by editing an argument.
_READ_ONLY_VERBS = frozenset(
    {"status", "rev-parse", "diff", "log", "show", "ls-files", "symbolic-ref"}
)


class Adapter:
    """`git`, read-only."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.GIT),
            summary="read-only git inspection inside the declared workspace root",
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        if invocation.operation == "read_file":
            return self._read_file(invocation)
        argv = self._argv(invocation)
        if argv[1] not in _READ_ONLY_VERBS:
            # Unreachable through the declarative path above; asserted anyway,
            # because a closed set that is never checked is a comment.
            raise PathEscapesWorkspace("this adapter runs read-only git verbs only")
        return execute_argv(invocation, argv)

    # ------------------------------------------------------------------

    def _argv(self, invocation: Invocation) -> list[str]:
        arguments = invocation.arguments
        if invocation.operation == "status":
            return ["git", "status", "--porcelain"]
        if invocation.operation == "current_sha":
            return ["git", "rev-parse", "HEAD"]
        if invocation.operation == "current_branch":
            return ["git", "symbolic-ref", "--short", "-q", "HEAD"]
        if invocation.operation == "diff":
            against = arguments.get("against")
            return ["git", "diff"] + ([against] if against else [])
        if invocation.operation == "log":
            limit = arguments.get("limit", 20)
            return ["git", "log", "--oneline", "-n", str(limit)]
        raise AssertionError(f"undeclared operation {invocation.operation!r}")

    def _read_file(self, invocation: Invocation) -> AdapterOutcome:
        """Read one file, resolved and confined before anything is opened.

        No subprocess: a file read is a file read, and routing it through `git`
        would be a way to reach bytes the containment rule already covers
        without a process.
        """
        root = resolve_root(invocation.root)
        path = contained_path(root, invocation.arguments["path"])
        if not path.is_file():
            return AdapterOutcome.of(ToolOutcome.FAILED, "NOT_A_FILE")
        try:
            raw = path.read_bytes()
        except OSError:
            return AdapterOutcome.of(ToolOutcome.FAILED, "UNREADABLE")
        text = raw.decode("utf-8", errors="replace")
        return AdapterOutcome.of(
            ToolOutcome.COMPLETED,
            "READ_OK",
            stdout=text,
            structured={"bytes": len(raw)},
        )
