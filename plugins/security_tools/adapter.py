"""The adapter protocol — one shape, eight families (contract §8, §4.1).

An adapter answers one question: *given an authorized invocation, what happened*.
It does not answer *may this run* — that was settled before it was called (§9.1).

### What an adapter may do, and what it may not

```text
MAY      validate input the descriptor already declared
         check the execution environment
         enforce the workspace containment rule
         enforce the vehicle boundary for its own operations
         apply a timeout
         shape the output
MAY NOT  build a second permission engine, policy engine, rule precedence
         or approval service
```

A copy of AI-04's decision model under `tools/` would be the second permission
system this contract exists to prevent (§7.4, §9 of the brief). Every adapter
here takes the Guard decision as settled and never reconsiders it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from plugins.guard.models import TargetRef

from plugins.security_tools.descriptor import OperationSpec, ToolDescriptor
from plugins.security_tools.runner import ProcessRunner
from plugins.security_tools.vocabulary import ToolOutcome

__all__ = ["AdapterOutcome", "Invocation", "ToolAdapter"]


@dataclass(frozen=True, slots=True)
class Invocation:
    """Everything an adapter is given. It has already been authorized.

    There is deliberately no policy, no approval state and no permission level
    here: an adapter that could see them could be tempted to reason about them,
    and the whole point of the boundary is that it does not.
    """

    operation: str
    spec: OperationSpec
    arguments: Mapping[str, Any]
    target: TargetRef
    timeout_seconds: int
    environment: Mapping[str, str]
    root: str | None
    runner: ProcessRunner
    workspace_id: str


@dataclass(frozen=True, slots=True)
class AdapterOutcome:
    """What an adapter reports, before dispatch projects and bounds it.

    `outcome` is the adapter's claim about the **operation** (§8.2). It is not a
    claim about the research question, and an adapter that lifted a test
    runner's own result vocabulary into this field would be doing the one thing
    §8.2 forbids.
    """

    outcome: ToolOutcome
    reason_code: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    structured: Mapping[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    started_at: str | None = None

    @classmethod
    def of(
        cls,
        outcome: ToolOutcome,
        reason_code: str,
        **rest: Any,
    ) -> "AdapterOutcome":
        return cls(outcome=outcome, reason_code=reason_code, **rest)


class ToolAdapter(Protocol):
    """One family's implementation.

    `descriptor` is a description and the registry answers questions from it.
    `execute` is called only after Guard returned ALLOW for this invocation.
    """

    @property
    def descriptor(self) -> ToolDescriptor: ...

    def execute(self, invocation: Invocation) -> AdapterOutcome: ...


# --------------------------------------------------------------------------
# the shared argv path
# --------------------------------------------------------------------------

#: Names copied from the parent so that a process can start at all.
#:
#: Deliberately two, and deliberately named. A child needs to *find* a program
#: and, on Windows, to load the system libraries; it does not need the parent's
#: API keys. `os.environ` is never passed through wholesale (§11.2), and a test
#: asserts that a parent-only variable does not reach the child.
_BASELINE_ENVIRONMENT_NAMES = ("PATH", "SYSTEMROOT", "SystemRoot", "PATHEXT", "COMSPEC", "TEMP", "TMP")

def declared_environment(invocation: Invocation) -> dict[str, str]:
    """The child environment: a named minimal baseline plus what was declared.

    This is the only function that builds an environment for a process, so
    §11.2 has one implementation and one test.
    """
    environment = {
        name: os.environ[name]
        for name in _BASELINE_ENVIRONMENT_NAMES
        if name in os.environ
    }
    environment.update(invocation.environment)
    return environment


def execute_argv(invocation: Invocation, argv: Sequence[str]) -> AdapterOutcome:
    """Run one declared argv under the execution boundary (§11), and map it.

    The only place §11.5's exit-code mapping lives. An operation declares which
    exit codes mean it COMPLETED; anything else is FAILED. The general rule
    "zero is success" is deliberately **not** used, because a search tool
    reports "no match" through its status and a test runner reports failing
    tests through one.
    """
    if not invocation.spec.environment.subprocess:
        raise ExecutionRefused(
            "this operation does not declare that it starts a process (§7.2), so "
            "AI-06 does not start one for it"
        )
    if invocation.root is None:
        raise ExecutionRefused(
            "a process is started inside a declared workspace root, and this "
            "request declared none (§10.2)"
        )

    process = invocation.runner.run(
        list(argv),
        cwd=invocation.root,
        environment=declared_environment(invocation),
        timeout_seconds=invocation.timeout_seconds,
    )

    if process.timed_out:
        return AdapterOutcome.of(
            ToolOutcome.TIMED_OUT,
            "TIMEOUT_EXPIRED",
            exit_code=None,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_ms=process.duration_ms,
        )

    if process.exit_code is None:
        # No exit code and no timeout means the process never ran: the program
        # is absent or could not be started. That is `BLOCKED`, not `FAILED` —
        # §8.2 makes BLOCKED "a precondition was unavailable, so nothing ran" —
        # and it is decided here rather than by each adapter asking the host
        # whether a program exists, which would also make an adapter untestable
        # without the program installed.
        return AdapterOutcome.of(
            ToolOutcome.BLOCKED,
            "PROGRAM_UNAVAILABLE",
            exit_code=None,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_ms=process.duration_ms,
        )

    completed = (
        process.exit_code is not None
        and process.exit_code in invocation.spec.expected_exit_codes
    )
    return AdapterOutcome.of(
        ToolOutcome.COMPLETED if completed else ToolOutcome.FAILED,
        "EXIT_CODE_EXPECTED" if completed else "EXIT_CODE_UNEXPECTED",
        exit_code=process.exit_code,
        stdout=process.stdout,
        stderr=process.stderr,
        duration_ms=process.duration_ms,
    )
