"""The process boundary — the only module in AI-06 that starts a process.

Contract §11. This module is deliberately small and deliberately alone: it is
the one place where the argv rule (§11.1), the declared-environment rule
(§11.2) and the required-timeout rule (§11.3) are enforced, so there is one
place to audit and one place for Layer 0 to check.

### What this module will not do

```text
it will not pass `shell=True`, and it has no parameter that could
it will not accept a command string; `argv` is a sequence of separate arguments
it will not inherit the parent environment; `environment` is passed explicitly
it will not run without a timeout; the parameter is required and must be positive
it will not leave a timed-out process running
```

The last one is a property of `subprocess.run(timeout=...)`, which terminates
the child before raising. AI-06 relies on it and tests it (§14 of the brief)
rather than assuming it.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Protocol, Sequence

from plugins.security_tools.errors import ExecutionRefused

__all__ = ["ProcessOutcome", "ProcessRunner", "SubprocessRunner"]


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    """What a process did. Facts only — no verdict (§11.5)."""

    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: int


class ProcessRunner(Protocol):
    """The seam tests replace.

    Every adapter takes a runner. The default is `SubprocessRunner`; a test
    passes a fake, and no test in this repository starts a real process.
    """

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        environment: dict[str, str],
        timeout_seconds: int,
    ) -> ProcessOutcome: ...


class SubprocessRunner:
    """The real one. `shell` is not a parameter, so it cannot be set."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        environment: dict[str, str],
        timeout_seconds: int,
    ) -> ProcessOutcome:
        arguments = list(argv)
        if not arguments:
            raise ExecutionRefused("an operation must declare at least one argv element")
        if not all(isinstance(part, str) for part in arguments):
            raise ExecutionRefused("every argv element must be a string")
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise ExecutionRefused(
                "a process is never started without a positive deadline (§11.3)"
            )

        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 - argv, and shell is not a parameter
                arguments,
                cwd=cwd,
                env=dict(environment),
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,  # stated rather than defaulted, and not parameterised
            )
        except subprocess.TimeoutExpired as expired:
            # `subprocess.run` terminates the child before raising, so the
            # process is stopped by the time this returns (§11.3).
            return ProcessOutcome(
                exit_code=None,
                stdout=_decode(expired.stdout),
                stderr=_decode(expired.stderr),
                timed_out=True,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except FileNotFoundError:
            return ProcessOutcome(
                exit_code=None,
                stdout="",
                stderr="the program was not found",
                timed_out=False,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except OSError:
            return ProcessOutcome(
                exit_code=None,
                stdout="",
                stderr="the program could not be started",
                timed_out=False,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        return ProcessOutcome(
            exit_code=completed.returncode,
            stdout=_decode(completed.stdout),
            stderr=_decode(completed.stderr),
            timed_out=False,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


def _decode(raw: bytes | str | None) -> str:
    """Bytes to text, never raising on what a tool happened to print.

    A tool's output is not obliged to be UTF-8, and a decode error must not
    become an exception in the middle of recording what happened.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return raw.decode("utf-8", errors="replace")
