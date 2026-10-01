"""AI-06 firmware adapter. Contract §13.7.

```text
FROZEN: v1 covers identity, declared capabilities, argument schemas, the
        execution boundary and a uniform result. It does not reimplement QEMU,
        GDB, or any firmware utility, and it does not embed one.
```

The adapter drives the program; it does not contain it. Whether a real run is
possible is an environment question, and where it is not, the operation reports
what actually happened rather than a hopeful success.

### An absent program is `BLOCKED`, not `FAILED`

An operation whose program is not present on the host produces
`ToolOutcome.BLOCKED` with `PROGRAM_UNAVAILABLE` — §8.2 makes BLOCKED "a
precondition was unavailable, so nothing ran", which is exactly this. It is not
`COMPLETED` and it is not `FAILED`: nothing executed, and saying so is the
honest answer.

The decision is made once, in `execute_argv`, from the process outcome — not by
each adapter asking the host whether a program exists. A host check inside an
adapter would also make the adapter untestable without the program installed,
which is how a suite ends up asserting things it never ran.
"""

from __future__ import annotations

from plugins.security_tools.adapter import AdapterOutcome, Invocation, execute_argv
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
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

TOOL_ID = "firmware"
TOOL_VERSION = "1.0.0"

_SUBPROCESS = EnvironmentRequirement(
    filesystem=FilesystemAccess.READ, subprocess=True
)

OPERATIONS: tuple[OperationSpec, ...] = (
    OperationSpec(
        name="qemu",
        permission_level_floor=PermissionLevel.TEST,
        summary="run a firmware image under emulation",
        arguments=(
            ArgumentSpec("machine", "string", maximum_length=64),
            ArgumentSpec("image", "string", maximum_length=512),
        ),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.FILESYSTEM,),
        expected_exit_codes=frozenset({0}),
    ),
    OperationSpec(
        name="gdb",
        permission_level_floor=PermissionLevel.TEST,
        summary="a bounded debug session against a declared binary",
        arguments=(
            ArgumentSpec("binary", "string", maximum_length=512),
            ArgumentSpec("commands", "string_list", required=False),
        ),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.FILESYSTEM,),
        expected_exit_codes=frozenset({0}),
    ),
    OperationSpec(
        name="firmware_unpack",
        permission_level_floor=PermissionLevel.TEST,
        summary="unpack a firmware image with a declared tool",
        arguments=(ArgumentSpec("image", "string", maximum_length=512),),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.FILESYSTEM,),
        expected_exit_codes=frozenset({0}),
    ),
)

OPERATION_NAMES = tuple(spec.name for spec in OPERATIONS)

#: Which program each operation drives. A description of the tool the operation
#: shells out to, not a bundle of it.
_PROGRAMS = {
    "qemu": "qemu-system-arm",
    "gdb": "gdb",
    "firmware_unpack": "binwalk",
}


class Adapter:
    """Drives declared firmware programs; contains none of them."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.FIRMWARE),
            summary="run declared firmware tooling inside the workspace root",
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        program = _PROGRAMS[invocation.operation]

        root = resolve_root(invocation.root)
        arguments = invocation.arguments

        if invocation.operation == "qemu":
            image = contained_path(root, arguments["image"])
            argv = [program, "-M", arguments["machine"], "-kernel", str(image)]
        elif invocation.operation == "gdb":
            binary = contained_path(root, arguments["binary"])
            argv = [program, "--batch", "--args", str(binary)]
            for command in arguments.get("commands", []):
                argv.extend(["-ex", command])
        else:
            image = contained_path(root, arguments["image"])
            argv = [program, str(image)]

        return execute_argv(invocation, argv)
