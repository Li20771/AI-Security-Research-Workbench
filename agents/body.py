"""AI-08 §15 — what an Agent body is, and what v1's offline body is not.

```text
FROZEN: AI-08 v1 defines the INTERFACE SHAPE only.
FROZEN: AI-08 MUST NOT make a network call and MUST NOT import an HTTP client.
FROZEN: AI-08 v1 has no provider binding and no model binding.
```

### v1 ships an offline body, and it performs no inference

Every capability on every shipped model profile is `UNKNOWN` and no provider call
has ever been made in this repository. So the v1 bodies cannot call a model, and
they do not pretend to:

```text
OfflineBody is NOT A MODEL. It performs no inference, reaches no network, reads
no credential and spawns no process. It exists so that the execution contract
has something real to run against, and so that the runtime's outcomes are
reachable in a test.
```

AI-09 replaces Codex's body with a provider-backed one. DSH's real execution
lives in the external DSH platform (AI-01); AI-08 does not reimplement it, and
this body is the Workbench-side shape, not a second DSH.

### What `result_ref` is in v1 — read this before reading a result

```text
FROZEN (v1): the offline bodies produce a PROVENANCE REFERENCE: a digest over
        the execution's declared inputs and the context it resolved. It names
        what the execution terminated WITH, and it is not content.
FROZEN (v1): it is NOT a task result. §10.2's "task result" arm belongs to
        AI-09's provider-backed body, and a reader MUST NOT read a task result
        out of a provenance reference.
```

`COMPLETED` claims only that the execution reached a terminal result. That is a
claim about the execution, never about the task, and never about the research
question (§11.3).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, Sequence

from plugins.context import ContextResponse

from agents.request import AgentExecutionRequest
from agents.toolcall import ToolGateway, ToolInvocation
from agents.vocabulary import AgentId

__all__ = [
    "AgentBody",
    "BodyOutcome",
    "OfflineBody",
    "REASON_COMPLETED",
]

REASON_COMPLETED = "EXECUTION_COMPLETED"


@dataclass(frozen=True, slots=True)
class BodyOutcome:
    """What a body reports when it reached a terminal result.

    `result_ref` is a **reference or a digest**, never content (§10). The bytes
    live outside this record, which is what lets a result be stored or logged
    without becoming a place raw output accumulates.
    """

    result_ref: str
    reason_code: str = REASON_COMPLETED


class AgentBody(Protocol):
    """One Agent's execution shape (§15).

    A body is handed the execution's own `ContextResponse` and its own
    `ToolGateway`, and reaches the outside world through neither of them
    directly: tools go through Guard, and the context was already read for it.

    ```text
    FROZEN: a body MUST NOT be handed another execution's ContextResponse, and
            MUST NOT be handed another execution's ToolGateway (§8.2).
    FROZEN: a body's tool calls reach Guard, never the network. AI-08 v1 wires
            no provider; that is AI-09's (§15).
    FROZEN: a body MUST NOT read another Agent's result. There is no parameter
            through which one could arrive, and I3 forbids adding one (§9.1).
    ```
    """

    def run(
        self,
        *,
        request: AgentExecutionRequest,
        context: ContextResponse,
        tools: ToolGateway,
    ) -> BodyOutcome: ...


def _digest(*parts: str) -> str:
    payload = "\x00".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OfflineBody:
    """A deterministic, offline body. **Not a model.**

    It resolves to a provenance reference over the execution's declared inputs
    and the context it was handed. Two executions of the same request against
    the same workspace resolve to the same reference — which is a property of a
    deterministic function, not a claim that the work was done twice the same
    way.

    `plan` is the invocation sequence the body asks for. Each entry goes through
    `tools.invoke`, and therefore through a fresh Guard evaluation. An empty
    plan is a valid body: §7.1 makes zero tool invocations a complete execution,
    not an incomplete one.
    """

    agent_id: AgentId
    plan: Sequence[ToolInvocation] = field(default_factory=tuple)

    def run(
        self,
        *,
        request: AgentExecutionRequest,
        context: ContextResponse,
        tools: ToolGateway,
    ) -> BodyOutcome:
        if AgentId(request.agent_id) is not AgentId(self.agent_id):
            # A result is attributed by the REQUEST (§10), so a body running
            # another Agent's request would produce an execution whose declared
            # identity and actual body silently disagree. Refusing here makes
            # that unrepresentable rather than merely discouraged.
            raise ValueError(
                f"{type(self).__name__} executes as {self.agent_id} and was given "
                f"a request for {request.agent_id}; a body serves one identity, "
                "and the attribution must not be rewritable by the caller (§5.1)"
            )

        # Every declared invocation goes to Guard. A refusal is recorded and the
        # body continues: §11.2 makes a refused tool call a TOOL-level event, and
        # the execution's own outcome is decided by what the execution did.
        for invocation in self.plan:
            tools.invoke(invocation)

        reference = _digest(
            str(self.agent_id),
            request.task,
            request.input_digest,
            context.workspace.workspace_id,
            context.workspace.commit or "",
            str(context.status),
        )
        return BodyOutcome(result_ref=f"sha256:{reference}")
