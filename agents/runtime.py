"""AI-08 §7, §8, §11 — the execution controller.

```text
one AgentExecutionRequest
        ->
one new opaque ExecutionId
        ->
zero or more tool invocations
        ->
one terminal AgentResult

and the last line holds for COMPLETED, FAILED and BLOCKED alike (§7.1.1).
```

### The controller produces the result, not the body

```text
FROZEN: the execution CONTROLLER / RUNTIME produces the terminal AgentResult.
        It does so whether or not the Agent execution BODY ran.
FROZEN: Agent execution body did not start  !=  no AgentResult exists.
```

That is what makes `BLOCKED` expressible: the body never starts, and the record
of why still exists because the controller writes it.

### Context is established here, and owned here — §8.1

```text
FROZEN: the execution runtime establishes exactly one ContextResponse for the
        execution, from the execution's own workspace and task.
FROZEN: the AgentExecutionRequest does NOT carry a ContextResponse, and
        supplying one is REFUSED rather than ignored.
```

The response is a local value, handed to one body, and referenced by one result.
Two executions hold two different objects even when they read the same
read-only facts, because §8.2 isolates the resolved response and the cache
instance, not the workspace.

### What v1 does not classify, and why — §11.1

`§11.1` closes the execution-level precondition list for v1. Two of its members
can fire here:

```text
a workspace that cannot be used          WORKSPACE_UNAVAILABLE
a ContextResponse that cannot be         CONTEXT_UNAVAILABLE
  established
```

Two cannot, and are not faked:

```text
an Agent that does not resolve           fires at the IDENTITY boundary
                                         (agents.vocabulary.resolve_agent) and
                                         at request construction, before an
                                         execution exists at all
a missing or unreadable declared input   the declared input is a digest or a
                                         reference to bytes AI-08 explicitly
                                         does not store (§7.3); there is
                                         nothing here to read and therefore
                                         nothing to find missing
```

```text
FROZEN: no authorization member is in this list. AI-08 v1 has no execution-level
        authorization — Guard authorizes tool INVOCATIONS, not executions
        (§12.1.1) — and a refused tool call is a TOOL-level event that never
        rewrites the execution outcome (§11.2).
```
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from plugins.context import build_context
from plugins.security_tools import ToolRegistry

from agents.body import AgentBody
from agents.independence import ExecutionRecord
from agents.request import AgentExecutionRequest, new_execution_id
from agents.result import AgentExecutionOutcome, AgentResult
from agents.toolcall import ToolGateway

__all__ = [
    "execute",
    "run_execution",
]

Clock = Callable[[], str]

#: Stable labels. Never prose, and never a sentence a reader has to parse.
#: `EXECUTION_COMPLETED` lives with the bodies (`agents.body`), because a
#: completed execution's reason is the body's to report.
REASON_BODY_FAILED = "BODY_FAILED"
REASON_WORKSPACE_UNAVAILABLE = "WORKSPACE_UNAVAILABLE"
REASON_CONTEXT_UNAVAILABLE = "CONTEXT_UNAVAILABLE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _terminal_result(
    *,
    request: AgentExecutionRequest,
    execution_id: str,
    workspace_id: str,
    outcome: AgentExecutionOutcome,
    result: str,
    reason_code: str,
    started_at: str,
    started_monotonic: float,
    tools: ToolGateway | None = None,
    blocking: str | None = None,
) -> AgentResult:
    """Build the one terminal result. Every return path in `execute` goes here.

    Having a single constructor is what makes §7.1.1 structural rather than
    aspirational: there is no branch that returns early without a result,
    because there is nowhere else to return from.
    """
    return AgentResult(
        agent_id=str(request.agent_id),
        execution_id=execution_id,
        workspace_id=workspace_id,
        input_digest=request.input_digest,
        outcome=outcome,
        result=result,
        tool_calls=() if tools is None else tools.calls,
        started_at=started_at,
        duration_ms=max(0, int((time.monotonic() - started_monotonic) * 1000)),
        reason_code=reason_code,
        blocking=blocking,
    )


def execute(
    request: AgentExecutionRequest,
    *,
    body: AgentBody,
    registry: ToolRegistry | None = None,
    policy: Any = None,
    clock: Clock | None = None,
) -> AgentResult:
    """Run one execution and return its one terminal `AgentResult`.

    The order is the contract's, and it is load-bearing:

```text
1  the workspace precondition      a body that never started is BLOCKED
2  establish the execution's own ContextResponse
3  run the body                    an exception is FAILED, never a silent success
4  one terminal AgentResult        for every path above, without exception
```
    """
    started_at = (clock or _utc_now)()
    started_monotonic = time.monotonic()
    execution_id = new_execution_id()

    root = Path(request.workspace_root)
    if not root.is_dir():
        # §11.1: an execution-level precondition. The body never starts, and
        # the controller still produces the terminal result describing it.
        return _terminal_result(
            request=request,
            execution_id=execution_id,
            workspace_id="",
            outcome=AgentExecutionOutcome.BLOCKED,
            result=f"agent-block:{execution_id}",
            reason_code=REASON_WORKSPACE_UNAVAILABLE,
            blocking=(
                "the declared workspace root is not a usable directory, so the "
                "execution body was never started (§11.1)"
            ),
            started_at=started_at,
            started_monotonic=started_monotonic,
        )

    try:
        context = build_context(root, clock=(clock or _utc_now))
    except Exception as exc:  # noqa: BLE001 - any failure to establish is a block
        return _terminal_result(
            request=request,
            execution_id=execution_id,
            workspace_id="",
            outcome=AgentExecutionOutcome.BLOCKED,
            result=f"agent-block:{execution_id}",
            reason_code=REASON_CONTEXT_UNAVAILABLE,
            blocking=(
                "the execution's ContextResponse could not be established, so "
                "the execution body was never started (§8.1, §11.1): "
                f"{type(exc).__name__}"
            ),
            started_at=started_at,
            started_monotonic=started_monotonic,
        )

    workspace_id = context.workspace.workspace_id

    # One gateway per execution. §8.2 forbids two executions sharing tool state,
    # and a per-execution object is the cheapest way to make sharing impossible
    # rather than merely discouraged.
    tools = ToolGateway(
        agent_id=request.agent_id,
        workspace_id=workspace_id,
        workspace_root=request.workspace_root,
        registry=registry,
        policy=policy,
    )

    try:
        outcome = body.run(request=request, context=context, tools=tools)
    except Exception as exc:  # noqa: BLE001 - a body that failed is FAILED
        # §11.1: the body STARTED. An execution that started is never BLOCKED,
        # whatever went wrong inside it.
        return _terminal_result(
            request=request,
            execution_id=execution_id,
            workspace_id=workspace_id,
            outcome=AgentExecutionOutcome.FAILED,
            result=f"agent-failure:{execution_id}",
            reason_code=REASON_BODY_FAILED,
            blocking=(
                "the execution body started and did not reach a valid task "
                f"result (§11.1): {type(exc).__name__}"
            ),
            tools=tools,
            started_at=started_at,
            started_monotonic=started_monotonic,
        )

    return _terminal_result(
        request=request,
        execution_id=execution_id,
        workspace_id=workspace_id,
        outcome=AgentExecutionOutcome.COMPLETED,
        result=outcome.result_ref,
        reason_code=outcome.reason_code,
        tools=tools,
        started_at=started_at,
        started_monotonic=started_monotonic,
    )


def run_execution(
    request: AgentExecutionRequest,
    *,
    body: AgentBody,
    registry: ToolRegistry | None = None,
    policy: Any = None,
    clock: Clock | None = None,
) -> ExecutionRecord:
    """Run one execution and return the **record** the predicate ranges over.

    `execute` answers "what did this execution terminate with". This answers the
    larger question an independence check needs: the request, the result, and
    the `ContextResponse` the execution established for itself.

    ```text
    §9.1 I4 asks which context an execution owns, and §8.1 says the runtime
    establishes it — so the runtime is the only place that can answer. Returning
    the result alone would leave I4 unprovable from the outside, and an
    unprovable condition is one that gets asserted by assumption instead.
    ```

    The context is captured from the body's own arguments rather than rebuilt:
    rebuilding would produce a *second* `ContextResponse` and quietly break the
    property this function exists to let a caller check.
    """
    captured: list[Any] = []

    class _Capturing:
        __slots__ = ()

        def run(self, *, request, context, tools):  # noqa: ANN001, ANN202
            captured.append(context)
            return body.run(request=request, context=context, tools=tools)

    result = execute(
        request,
        body=_Capturing(),
        registry=registry,
        policy=policy,
        clock=clock,
    )
    return ExecutionRecord(
        request=request,
        result=result,
        context=captured[0] if captured else None,
    )
