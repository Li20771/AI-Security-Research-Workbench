"""The Evidence projection (contract §15).

**AI-06 projects; AI-05 records.** This module does not implement a store, call
admission, write a record or define an Evidence schema. It produces the
`ToolCall` AI-05 already has a type for, and the caller submits it through AI-05's
existing entry point. Reimplementing admission would duplicate AI-05's §30
pipeline and its uniqueness rule, both frozen and both tested there.
"""

from __future__ import annotations

from plugins.evidence import ExecutionPayload, ToolCall

from plugins.security_tools.result import ToolResult

__all__ = ["execution_payload_for", "tool_call_for"]


def tool_call_for(result: ToolResult, ordinal: int) -> ToolCall:
    """One invocation becomes one `ToolCall` (§15.2).

    ```yaml
    ordinal:   assigned by the caller, as AI-05 §11.1 requires
    what_ran:  "<tool_id>/<operation>"
    status:    the projected StatusValue
    ```

    `what_ran` carries the tool and the operation and **nothing else** — no
    arguments, no stdout, no stderr, no environment. AI-05 §26 forbids storing
    raw tool output inside a record, and an argument set is a second place for a
    credential to reach a durable record.
    """
    return ToolCall(
        ordinal=ordinal,
        what_ran=result.what_ran,
        status=result.status,
    )


def execution_payload_for(results: tuple[ToolResult, ...]) -> ExecutionPayload:
    """A sequence of invocations becomes one `ExecutionPayload` (§15.2).

    Ordinals are assigned here, in the order given, because AI-05 §11.1 makes
    the ordinal the semantic order and the array position not semantic at all.
    Duplicate ordinals cannot arise from this function, which is why it counts
    rather than asking the caller to.
    """
    return ExecutionPayload(
        tool_calls=tuple(
            tool_call_for(result, ordinal) for ordinal, result in enumerate(results)
        )
    )
