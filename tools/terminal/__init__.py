"""AI-06 terminal adapter. Contract §13.4.

```text
Terminal != unrestricted shell
```

`run` executes **one declared program** with **validated arguments**. There is no
command string, no pipeline, no redirect, no subshell, and no environment
assignment prefix. Anything a shell would interpret arrives as an ordinary
argument, because there is no shell to interpret it (§11.1).

The program is not a free-form argument either: it must appear in
`_DECLARED_PROGRAMS`, so "run anything" is not a thing this adapter can be asked
to do. Adding a program is an edit to a closed set in reviewed code, not a request
field.

This adapter is not how the other seven families do their work. An operation that
belongs to `git`, `tests`, `vehicle_network` or any other family MUST NOT be
routed through here to avoid declaring it (§13.4).
"""

from __future__ import annotations

from plugins.security_tools.adapter import AdapterOutcome, Invocation, execute_argv
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
from plugins.security_tools.errors import ExecutionRefused
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import (
    AdapterFamily,
    FilesystemAccess,
    PermissionLevel,
    TargetKind,
    ToolOutcome,
)

__all__ = ["Adapter", "DECLARED_PROGRAMS", "OPERATION_NAMES", "TOOL_ID", "TOOL_VERSION"]

TOOL_ID = "terminal"
TOOL_VERSION = "1.0.0"

#: The programs this adapter may run. A closed set, deliberately small.
DECLARED_PROGRAMS: frozenset[str] = frozenset(
    {"echo", "printf", "uname", "pwd", "true", "false"}
)

OPERATIONS: tuple[OperationSpec, ...] = (
    OperationSpec(
        name="run",
        permission_level_floor=PermissionLevel.TEST,
        summary="run one declared program with validated arguments",
        arguments=(
            ArgumentSpec("program", "string", maximum_length=64),
            ArgumentSpec("args", "string_list", required=False),
        ),
        environment=EnvironmentRequirement(
            filesystem=FilesystemAccess.READ, subprocess=True
        ),
        target_kinds=(TargetKind.FILESYSTEM, TargetKind.SYSTEM),
        expected_exit_codes=frozenset({0}),
    ),
)

OPERATION_NAMES = tuple(spec.name for spec in OPERATIONS)


class Adapter:
    """Declared programs, argv only."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.TERMINAL),
            summary="run a declared program inside the workspace, argv only",
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        program = invocation.arguments["program"]
        if program not in DECLARED_PROGRAMS:
            raise ExecutionRefused(
                "this adapter runs declared programs only. A program that is not "
                "in the reviewed set is refused here rather than passed to a "
                "process, because 'run anything' is what a shell is and this "
                "adapter is not a shell (§13.4)"
            )
        argv = [program, *invocation.arguments.get("args", [])]
        return execute_argv(invocation, argv)
