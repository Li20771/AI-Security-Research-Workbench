"""The tool result — what happened (contract §8).

A `ToolResult` is an execution fact. It is not an authorization, not a research
verdict, and not an Evidence record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from plugins.security_tools.vocabulary import (
    GuardDecision,
    StatusValue,
    ToolOutcome,
    status_for,
)

__all__ = ["BOUNDED_OUTPUT_CHARS", "ToolResult"]

#: How much of a stream a `ToolResult` carries (contract §8.1, §15.5).
#:
#: Deliberately **not** AI-05's `MAX_TEXT_LENGTH`. A ToolResult is not a record:
#: the Evidence projection carries neither `stdout` nor `stderr` at all (§15.2),
#: so this bound is about a result being bounded, not about fitting one into a
#: record leaf. Anything longer is truncated and `truncated` is set — a
#: truncated result is honest about being truncated, a silently shortened one is
#: a false record of what the tool said.
BOUNDED_OUTPUT_CHARS = 8192


@dataclass(frozen=True, slots=True)
class ToolResult:
    """§8.1. Attributed to a tool, a version, an operation, a workspace and an
    authorization — a result that cannot be attributed to all five is not a
    result this contract produces (§8.3).
    """

    tool_id: str
    tool_version: str
    operation: str
    outcome: ToolOutcome
    reason_code: str
    workspace_id: str
    guard: Mapping[str, str]
    target: Mapping[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    redacted: bool = False
    structured: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    @property
    def status(self) -> StatusValue:
        """The value this result projects to in Evidence (§15.3).

        One-way. Nothing converts a `StatusValue` back into a `ToolOutcome`, and
        the contract forbids adding a path that does.

        A `PASS` here means **this operation completed**. It does not mean the
        test suite passed, the research question was answered, a capability is
        VERIFIED, or that a Guard decision allows future work (§15.4).
        """
        return status_for(self.outcome)

    @property
    def guard_decision(self) -> GuardDecision:
        return GuardDecision(self.guard["decision"])

    @property
    def what_ran(self) -> str:
        """The Evidence `ToolCall.what_ran` value (§15.2).

        `<tool_id>/<operation>` and nothing else: no arguments, no output, no
        environment. AI-05 §26 forbids storing raw tool output inside a record,
        and an argument set is a second place for a credential to reach one.
        """
        return f"{self.tool_id}/{self.operation}"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "operation": self.operation,
            "outcome": str(self.outcome),
            "reason_code": self.reason_code,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "redacted": self.redacted,
            "structured": dict(self.structured),
            "guard": dict(self.guard),
            "target": dict(self.target),
            "workspace_id": self.workspace_id,
        }
