"""AI-06 reverse-engineering adapter. Contract §13.8.

```text
FROZEN: v1 covers identity, declared capabilities, argument schemas, the
        execution boundary and a uniform result. It does not reimplement YARA,
        AFL++, or Ghidra, and it does not embed one.
```

### Ghidra is declared and NOT_RUN

The roadmap lists Ghidra, and this family is where it belongs. v1 does **not**
take it on: a Ghidra integration is a JVM headless-analyzer concern with its own
installation model, and claiming it here would mean either an embedded JVM or a
`PASS` with nothing behind it. The family is declared, the operation is not, and
the Evidence record says `NOT_RUN` rather than dressing the gap as coverage.

### A fuzzing run is bounded

`afl_fuzz` takes a duration and runs under the request's timeout like any other
operation. A fuzzer with no bound is a fuzzer that has taken the session with it
(§11.3), and `AI-13` forbids unbounded background execution for the Workbench as
a whole.
"""

from __future__ import annotations

import shutil

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

TOOL_ID = "reverse_engineering"
TOOL_VERSION = "1.0.0"

_SUBPROCESS = EnvironmentRequirement(
    filesystem=FilesystemAccess.READ, subprocess=True
)

OPERATIONS: tuple[OperationSpec, ...] = (
    OperationSpec(
        name="yara_scan",
        permission_level_floor=PermissionLevel.TEST,
        summary="scan bytes against a declared rule file",
        arguments=(
            ArgumentSpec("rules", "string", maximum_length=512),
            ArgumentSpec("target", "string", maximum_length=512),
        ),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.FILESYSTEM,),
        # YARA reports a match through its exit status, so a non-zero exit is
        # not a failed operation. This is the case §11.5 exists for: the general
        # "zero is success" rule would report a match as a failure.
        expected_exit_codes=frozenset({0, 1}),
    ),
    OperationSpec(
        name="afl_fuzz",
        permission_level_floor=PermissionLevel.TEST,
        summary="a bounded fuzzing run against a declared target",
        arguments=(
            ArgumentSpec("target", "string", maximum_length=512),
            ArgumentSpec("duration_seconds", "integer", required=False),
        ),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.FILESYSTEM,),
        expected_exit_codes=frozenset({0}),
    ),
)

OPERATION_NAMES = tuple(spec.name for spec in OPERATIONS)

_PROGRAMS = {"yara_scan": "yara", "afl_fuzz": "afl-fuzz"}


class Adapter:
    """Drives declared reverse-engineering programs; contains none of them."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(
                TOOL_ID, TOOL_VERSION, AdapterFamily.REVERSE_ENGINEERING
            ),
            summary="run declared RE tooling inside the workspace root",
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        program = _PROGRAMS[invocation.operation]
        if shutil.which(program) is None:
            return AdapterOutcome.of(
                ToolOutcome.NOT_RUN,
                "PROGRAM_NOT_PRESENT",
                stderr="the declared program is not present on this host",
            )

        root = resolve_root(invocation.root)
        arguments = invocation.arguments

        if invocation.operation == "yara_scan":
            rules = contained_path(root, arguments["rules"])
            target = contained_path(root, arguments["target"])
            return execute_argv(invocation, [program, str(rules), str(target)])

        target = contained_path(root, arguments["target"])
        duration = arguments.get("duration_seconds")
        argv = [program, "-i", str(target)]
        if duration is not None:
            argv.extend(["-V", str(duration)])
        return execute_argv(invocation, argv)
