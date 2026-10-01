"""Fixtures for the AI-06 tests.

Every test here is offline, deterministic and repeatable. No test starts a real
process, reaches a network, touches a real CAN interface, or needs a credential:
`FakeRunner` is the only process seam and a temporary directory is the only
workspace.

Two evaluators are supplied rather than one. `allow` and `refuse` are the two
answers a Guard boundary has to handle, and a suite that only ever allows would
not notice a refusal being ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import pytest

from plugins.guard.vocabulary import GuardDecision

from plugins.security_tools.runner import ProcessOutcome
from plugins.security_tools.vocabulary import AdapterFamily, PermissionLevel

# --------------------------------------------------------------------------
# the process seam
# --------------------------------------------------------------------------


@dataclass
class FakeRunner:
    """A `ProcessRunner` that starts nothing and remembers everything.

    The record of `calls` is what makes the argv rule checkable: a test asserts
    the exact list that would have been passed to a process, so a `shell=True`
    regression is visible as a shape rather than as a missing process.
    """

    exit_code: int | None = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        environment: dict[str, str],
        timeout_seconds: int,
    ) -> ProcessOutcome:
        self.calls.append(
            {
                "argv": list(argv),
                "cwd": cwd,
                "environment": dict(environment),
                "timeout_seconds": timeout_seconds,
            }
        )
        return ProcessOutcome(
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
            timed_out=self.timed_out,
            duration_ms=1,
        )


# --------------------------------------------------------------------------
# the guard seam
# --------------------------------------------------------------------------


@dataclass
class FakeDecision:
    """The part of AI-04's result `ask_guard` reads."""

    decision: GuardDecision
    reason_code: str = "TEST"
    decision_id: str = "dec-test"


class Evaluator:
    """A stand-in evaluator that records the request it was handed."""

    def __init__(self, decision: GuardDecision = GuardDecision.ALLOW) -> None:
        self.decision = decision
        self.seen: list[Any] = []

    def __call__(self, request: Any, policy: Any) -> FakeDecision:
        self.seen.append(request)
        return FakeDecision(decision=self.decision)


class RaisingEvaluator:
    """An evaluator that fails. §9.2: that is not an evaluator that allowed."""

    def __call__(self, request: Any, policy: Any) -> Any:
        raise RuntimeError("the policy engine fell over")


@pytest.fixture
def allow() -> Evaluator:
    return Evaluator(GuardDecision.ALLOW)


@pytest.fixture
def deny() -> Evaluator:
    return Evaluator(GuardDecision.DENY)


@pytest.fixture
def blocked() -> Evaluator:
    return Evaluator(GuardDecision.BLOCKED)


@pytest.fixture
def unknown() -> Evaluator:
    return Evaluator(GuardDecision.UNKNOWN)


@pytest.fixture
def exploding() -> RaisingEvaluator:
    return RaisingEvaluator()


@pytest.fixture
def policy() -> Any:
    """A policy value. AI-06 never inspects it; it is handed straight to Guard."""
    return object()


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


# --------------------------------------------------------------------------
# request builders
# --------------------------------------------------------------------------


def request_mapping(
    *,
    root: str | None = None,
    tool_id: str = "git",
    tool_version: str = "1.0.0",
    family: str = "git",
    operation: str = "status",
    arguments: dict[str, Any] | None = None,
    permission_level: str | None = "read",
    timeout_seconds: int | None = 30,
    environment: dict[str, str] | None = None,
    target: dict[str, Any] | None = None,
    workspace_id: str = "ws-test",
) -> dict[str, Any]:
    """A well-formed request, with the fields tests vary kept visible."""
    mapping: dict[str, Any] = {
        "schema_version": 1,
        "workspace": {"workspace_id": workspace_id, "root": root},
        "tool": {
            "tool_id": tool_id,
            "tool_version": tool_version,
            "adapter_family": family,
        },
        "operation": operation,
        "arguments": arguments or {},
        "actor": {"id": "dsh", "type": "agent"},
        "permission_level": permission_level,
        "target": target
        or {
            "kind": "repository",
            "identifier": "wf",
            "environment": "simulated",
            "interface": "simulator",
            "is_real": False,
            "sensitivity": "internal",
        },
        "execution": {
            "timeout_seconds": timeout_seconds,
            "environment": environment or {},
        },
    }
    if permission_level is None:
        mapping.pop("permission_level")
    if timeout_seconds is None:
        mapping["execution"] = {
            "timeout_seconds": None,
            "environment": environment or {},
        }
        mapping["execution"].pop("timeout_seconds")
    return mapping


__all__ = [
    "Evaluator",
    "FakeDecision",
    "FakeRunner",
    "RaisingEvaluator",
    "request_mapping",
]
