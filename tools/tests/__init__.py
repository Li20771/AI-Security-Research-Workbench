"""AI-06 test-runner adapter. Contract §13.3.

```text
the runner's own output is `structured` and is NOT lifted into ToolOutcome
the runner's PASS is NOT a research verdict and NOT an Evidence PASS
```

A `pytest` run that reports *N passed* produces `ToolOutcome.COMPLETED` and
structured output saying so. Whether the research question was answered is not
this adapter's to say, and AI-00 §10 is the authority: a PASS requires *executed
and supported by evidence*, and a completed run supplies the first half only.

The `pytest` operation declares `expected_exit_codes = {0}`. A non-zero exit
means the run reported failures, so the **operation** did not succeed at what it
was asked to do — which is a claim about the operation and still not a research
verdict. The exit code itself is recorded as observed either way (§11.5).
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

TOOL_ID = "tests"
TOOL_VERSION = "1.0.0"

_SUBPROCESS = EnvironmentRequirement(
    filesystem=FilesystemAccess.READ, subprocess=True
)

OPERATIONS: tuple[OperationSpec, ...] = (
    OperationSpec(
        name="pytest",
        permission_level_floor=PermissionLevel.TEST,
        summary="run a pytest selection inside the declared workspace root",
        arguments=(
            ArgumentSpec("targets", "string_list", required=False),
            ArgumentSpec("quiet", "boolean", required=False),
        ),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
        expected_exit_codes=frozenset({0}),
    ),
    OperationSpec(
        name="shell_test",
        permission_level_floor=PermissionLevel.TEST,
        summary="run one declared test script from the workspace root",
        arguments=(ArgumentSpec("script", "string", maximum_length=512),),
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
        expected_exit_codes=frozenset({0}),
    ),
    OperationSpec(
        name="repository_validation",
        permission_level_floor=PermissionLevel.TEST,
        summary="run the repository's own validators",
        environment=_SUBPROCESS,
        target_kinds=(TargetKind.REPOSITORY,),
        expected_exit_codes=frozenset({0}),
    ),
)

OPERATION_NAMES = tuple(spec.name for spec in OPERATIONS)


class Adapter:
    """The test runner family."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.TESTS),
            summary="run declared tests inside the workspace and report facts",
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        if invocation.operation == "pytest":
            argv = ["python", "-m", "pytest"]
            if invocation.arguments.get("quiet"):
                argv.append("-q")
            argv.extend(invocation.arguments.get("targets", []))
            return execute_argv(invocation, argv)

        if invocation.operation == "shell_test":
            root = resolve_root(invocation.root)
            script = contained_path(root, invocation.arguments["script"])
            if not script.is_file():
                return AdapterOutcome.of(ToolOutcome.FAILED, "NOT_A_FILE")
            return execute_argv(invocation, ["bash", str(script)])

        if invocation.operation == "repository_validation":
            return execute_argv(
                invocation, ["python", "-m", "providers.validate"]
            )

        raise AssertionError(f"undeclared operation {invocation.operation!r}")
