"""The invocation pipeline (contract §9.1).

```text
Agent -> ToolRequest
      -> AI-06 validation            §6.1, §7.3
      -> AI-06 v1 target boundary    §12.3    gate 1
      -> AI-04 Guard                 §9.1     gate 2
      -> adapter                     §11
      -> ToolResult                  §8
      -> AI-05 projection            §15
```

Every step that can refuse refuses **before** the next one runs, so a malformed
invocation never reaches the evaluator and an unauthorized one never reaches a
process.
"""

from __future__ import annotations

from typing import Any

from plugins.guard.vocabulary import GuardDecision

from plugins.security_tools.adapter import AdapterOutcome, Invocation
from plugins.security_tools.descriptor import OperationSpec, ToolDescriptor
from plugins.security_tools.errors import (
    ArgumentInvalid,
    ExecutionRefused,
    GuardUnavailable,
    PathEscapesWorkspace,
    TargetRefused,
    ToolError,
    UnknownOperation,
    UnknownTool,
)
from plugins.security_tools.guards import (
    ask_guard,
    check_v1_target_boundary,
    decision_summary,
    guard_workspace_for,
)
from plugins.security_tools.paths import resolve_root
from plugins.security_tools.redaction import project
from plugins.security_tools.registry import ToolRegistry
from plugins.security_tools.request import ToolRequest
from plugins.security_tools.result import BOUNDED_OUTPUT_CHARS, ToolResult
from plugins.security_tools.runner import ProcessRunner, SubprocessRunner
from plugins.security_tools.vocabulary import FilesystemAccess, ToolOutcome

__all__ = ["invoke"]

#: How a Guard decision becomes a `ToolOutcome` when it is not an ALLOW (§9.2).
#:
#: `DENY`, `BLOCKED` and `UNKNOWN` are all refusals to execute. There is no
#: ordering among them that permits execution, and no path converts one into an
#: ALLOW — AI-04 §21's closing assertion, applied here unchanged.
_REFUSAL_OUTCOMES: dict[GuardDecision, ToolOutcome] = {
    GuardDecision.DENY: ToolOutcome.NOT_RUN,
    GuardDecision.BLOCKED: ToolOutcome.BLOCKED,
    GuardDecision.UNKNOWN: ToolOutcome.UNKNOWN,
}


def invoke(
    request: ToolRequest,
    *,
    registry: ToolRegistry,
    evaluator: Any,
    policy: Any,
    runner: ProcessRunner | None = None,
) -> ToolResult:
    """Run one invocation, or refuse it. Never both, and never silently."""
    descriptor = registry.descriptor_for(request.tool)
    if descriptor is None:
        return _refusal(request, ToolOutcome.UNKNOWN, "UNKNOWN_TOOL")

    spec = descriptor.operation(request.operation)
    if spec is None:
        return _refusal(request, ToolOutcome.UNKNOWN, "UNKNOWN_OPERATION")

    # §7.3, before Guard: a schema AI-06 cannot enforce is not a schema.
    try:
        arguments = spec.validate_arguments(request.arguments)
    except ToolError as exc:
        return _refusal(request, ToolOutcome.UNKNOWN, exc.reason_code)

    # Gate 1 (§12.3). Runs before Guard so that a request v1 cannot express is
    # never put to a policy in the first place.
    try:
        check_v1_target_boundary(request, spec)
    except TargetRefused as exc:
        return _refusal(request, ToolOutcome.BLOCKED, exc.reason_code)

    root = request.workspace.root
    try:
        if spec.environment.filesystem is not FilesystemAccess.NONE or root is not None:
            root = str(resolve_root(root))
    except ToolError as exc:
        return _refusal(request, ToolOutcome.BLOCKED, exc.reason_code)

    # Gate 2 (§9.1). One decision authorizes one invocation, as stated in this
    # request. There is no store of decisions and no parameter that could add one.
    workspace = guard_workspace_for(request)
    try:
        decision = ask_guard(
            request, workspace=workspace, evaluator=evaluator, policy=policy
        )
    except GuardUnavailable as exc:
        return _refusal(request, ToolOutcome.BLOCKED, exc.reason_code)

    if decision is not GuardDecision.ALLOW:
        return _refusal(
            request, _REFUSAL_OUTCOMES[decision], f"GUARD_{decision.value}", decision=decision
        )

    adapter = registry.adapter_for(request.tool)
    if adapter is None:  # pragma: no cover - registry lookup already succeeded
        return _refusal(request, ToolOutcome.UNKNOWN, "UNKNOWN_TOOL")

    invocation = Invocation(
        operation=request.operation,
        spec=spec,
        arguments=arguments,
        target=request.target,
        timeout_seconds=request.timeout_seconds,
        environment=dict(request.environment),
        root=root,
        runner=runner if runner is not None else SubprocessRunner(),
        workspace_id=request.workspace.workspace_id,
    )

    try:
        outcome = adapter.execute(invocation)
    except PathEscapesWorkspace as exc:
        return _refusal(request, ToolOutcome.BLOCKED, exc.reason_code, decision=decision)
    except (TargetRefused, ExecutionRefused) as exc:
        return _refusal(request, ToolOutcome.BLOCKED, exc.reason_code, decision=decision)
    except ToolError as exc:
        return _refusal(request, ToolOutcome.UNKNOWN, exc.reason_code, decision=decision)

    return _assembled(request, descriptor, outcome, decision)


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------


def _refusal(
    request: ToolRequest,
    outcome: ToolOutcome,
    reason_code: str,
    decision: GuardDecision | None = None,
) -> ToolResult:
    """A refusal is a `ToolResult`, not an exception (§17, §9.2).

    The exception is the mechanism; the result is the contract. A caller that
    wants to know why an invocation did not run reads `reason_code`, and one
    that wants to know what authorized the attempt reads `guard`.
    """
    return ToolResult(
        tool_id=request.tool.tool_id,
        tool_version=request.tool.tool_version,
        operation=request.operation,
        outcome=outcome,
        reason_code=reason_code,
        workspace_id=request.workspace.workspace_id,
        guard={
            "decision": str(decision if decision is not None else GuardDecision.BLOCKED),
            "reason_code": reason_code,
            "decision_id": "",
        },
        target=request.target.to_dict(),
    )


def _assembled(
    request: ToolRequest,
    descriptor: ToolDescriptor,
    outcome: AdapterOutcome,
    decision: GuardDecision,
) -> ToolResult:
    """Project the adapter's report into the result this contract promises."""
    stdout, stderr, structured, redacted = project(
        outcome.stdout, outcome.stderr, outcome.structured
    )
    stdout, cut_out = _bound(stdout)
    stderr, cut_err = _bound(stderr)

    return ToolResult(
        tool_id=descriptor.identity.tool_id,
        tool_version=descriptor.identity.tool_version,
        operation=request.operation,
        outcome=outcome.outcome,
        reason_code=outcome.reason_code,
        workspace_id=request.workspace.workspace_id,
        guard={
            "decision": str(decision),
            "reason_code": "",
            "decision_id": "",
        },
        target=request.target.to_dict(),
        started_at=outcome.started_at,
        duration_ms=outcome.duration_ms,
        exit_code=outcome.exit_code,
        stdout=stdout,
        stderr=stderr,
        truncated=cut_out or cut_err,
        redacted=redacted,
        structured=structured,
    )


def _bound(text: str) -> tuple[str, bool]:
    """§15.5. Truncation is marked, never silent."""
    if len(text) <= BOUNDED_OUTPUT_CHARS:
        return text, False
    return text[:BOUNDED_OUTPUT_CHARS], True


def operation_needs_subprocess(spec: OperationSpec) -> bool:
    """Whether this operation may start a process. A description, not a grant."""
    return bool(spec.environment.subprocess)
