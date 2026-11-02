"""AI-06's refusal vocabulary.

Contract §17. Each refusal carries a stable `reason_code` — never prose-as-code —
and **never an interpolated value**. AI-05's error doctrine records why: an error
message is a place a value escapes to a log, and a tool argument is a place a
credential can be. A message here names the field, the rule, and at most a shape
fact.

**These are not AI-04's errors and not AI-05's.** A guard refusal is already a
`GuardDecision` and travels as a `ToolResult` outcome (§9.2); it is not an
exception. What is here is AI-06 refusing its own input before Guard is asked.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base class for every AI-06 refusal.

    `reason_code` is a stable, machine-readable label. It is not a message and
    it never contains a supplied value.
    """

    reason_code: str = "TOOL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --------------------------------------------------------------------------
# The request (§6.1) — refused before Guard is asked
# --------------------------------------------------------------------------


class ToolRequestMalformed(ToolError):
    """The request does not match §6.1.

    A field the contract does not define is refused rather than ignored, so a
    credential or a command string cannot ride along unremarked.
    """

    reason_code = "TOOL_REQUEST_MALFORMED"


class PermissionLevelMissing(ToolRequestMalformed):
    """`permission_level` is absent (contract §6.2).

    Distinct from a malformed request because the caller's repair is specific:
    supply the level, and do not let anyone guess it from a name.
    """

    reason_code = "PERMISSION_LEVEL_MISSING"


class TimeoutMissing(ToolRequestMalformed):
    """`execution.timeout_seconds` is absent (contract §11.3).

    There is no default and no "no timeout". A tool that hangs is a tool that
    has taken the session with it.
    """

    reason_code = "TIMEOUT_MISSING"


# --------------------------------------------------------------------------
# The registry (§7) — a declared capability that is absent
# --------------------------------------------------------------------------


class UnknownTool(ToolError):
    """No adapter is registered for this `tool_id` and `tool_version`."""

    reason_code = "UNKNOWN_TOOL"


class UnknownOperation(ToolError):
    """The tool declares no such operation."""

    reason_code = "UNKNOWN_OPERATION"


class ArgumentInvalid(ToolError):
    """An argument fails the operation's declared schema (contract §7.3).

    An argument the schema does not define is refused. A schema AI-06 cannot
    enforce is not a schema.
    """

    reason_code = "ARGUMENT_INVALID"


# --------------------------------------------------------------------------
# The workspace (§10)
# --------------------------------------------------------------------------


class WorkspaceUnresolvable(ToolError):
    """The declared root is absent, is not a directory, or cannot be reached."""

    reason_code = "WORKSPACE_UNRESOLVABLE"


class PathEscapesWorkspace(ToolError):
    """A path resolves outside the declared root (contract §10.3).

    Detected by resolution, not by string inspection: a symlink pointing out of
    the workspace resolves outside it and is refused with it.
    """

    reason_code = "PATH_ESCAPES_WORKSPACE"


# --------------------------------------------------------------------------
# The vehicle boundary (§12)
# --------------------------------------------------------------------------


class TargetRefused(ToolError):
    """The target is outside the v1 boundary (contract §12.3).

    This is AI-06's own gate, and it runs *before* Guard is asked. It is not a
    substitute for AI-04's gate: a request must pass both.
    """

    reason_code = "TARGET_REFUSED"


# --------------------------------------------------------------------------
# The execution boundary (§11)
# --------------------------------------------------------------------------


class ExecutionRefused(ToolError):
    """The operation cannot be executed within §11's boundary.

    Reached when an adapter would have to do something the boundary forbids —
    run outside its declared argv shape, inherit an environment it may not, or
    start a process the contract does not allow it to start.
    """

    reason_code = "EXECUTION_REFUSED"


class GuardUnavailable(ToolError):
    """No usable authorization could be obtained (contract §9.1, §9.2).

    Fail closed: an evaluator that raised is not an evaluator that allowed.
    This never becomes an execution.
    """

    reason_code = "GUARD_UNAVAILABLE"


__all__ = [
    "ArgumentInvalid",
    "ExecutionRefused",
    "GuardUnavailable",
    "PathEscapesWorkspace",
    "PermissionLevelMissing",
    "TargetRefused",
    "TimeoutMissing",
    "ToolError",
    "ToolRequestMalformed",
    "UnknownOperation",
    "UnknownTool",
    "WorkspaceUnresolvable",
]
