"""Codex — the independent second Agent's execution shape, and the AI-09 seam.

```text
codex -> AgentRole.INDEPENDENT_SECOND      (§5.2, fixed registration)
```

The role is an **architectural name**. It is not an independence finding: the
role alone never satisfies I1-I8, and independence is a property of an execution
pair and of nothing else (§5.2.1).

### The provider seam, and who fills it

```text
Codex Agent
    |
    v
CodexBody            <- AI-08 owns this
    |
    v
CodexBackend         <- the interface AI-08-B defines and does NOT implement
    |
    v
provider / model     <- AI-09 wires a real one
```

AI-08-B defines the shape and stops. It does **not** implement an
OpenAI-compatible client, a domestic provider, a model profile, a credential
path, a tool-calling compatibility matrix or a network call — all of that is
AI-09's (§15), and a real backend plugged in here would be that work done twice
and untested.

### The v1 backend is offline and performs no inference

`OfflineCodexBackend` is a deterministic stub. It reaches no network, reads no
credential and spawns no process, and it produces a **provenance reference**, not
a task result. It exists so the execution contract has something real to run
against.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar, Protocol, Sequence

from plugins.context import ContextResponse

from agents.body import BodyOutcome, REASON_COMPLETED
from agents.request import AgentExecutionRequest
from agents.toolcall import ToolGateway, ToolInvocation
from agents.vocabulary import AgentId

__all__ = [
    "CODEX_AGENT_ID",
    "CodexBackend",
    "CodexBody",
    "OfflineCodexBackend",
]


#: The one AgentId this body serves. A constant rather than a constructor
#: argument, for the same reason DSH's is: attribution must not be rewritable
#: by the caller.
CODEX_AGENT_ID = AgentId.CODEX


class CodexBackend(Protocol):
    """The provider seam. **AI-09 implements this; AI-08-B does not.**

    A backend turns a declared task and an already-resolved context into a
    reference to its output. It is handed no credential and no tool gateway:
    credentials are resolved by the provider layer at AI-09's boundary, and tool
    invocations belong to the execution, not to the model that asked for one.

    ```text
    FROZEN: AI-08-B MUST NOT implement a real backend (§15).
    FROZEN: a backend MUST NOT reach the network in AI-08. The offline backend is
            the only one v1 ships, and it makes no call.
    FROZEN: a backend returns a REFERENCE, never raw model output (§10).
    ```
    """

    @property
    def backend_id(self) -> str: ...

    def produce(
        self,
        *,
        agent_id: AgentId,
        request: AgentExecutionRequest,
        context: ContextResponse,
    ) -> str:
        """Return a reference to this backend's output. Never the output."""
        ...


@dataclass(frozen=True, slots=True)
class OfflineCodexBackend:
    """The v1 stub. Deterministic, offline, and **not a model**.

    It performs no inference and makes no claim about the task. Its reference is
    a digest over the declared inputs, so it is reproducible, and it says only
    what a provenance reference can say: which execution produced it and over
    what.
    """

    backend_id: str = "codex-offline-v1"

    def produce(
        self,
        *,
        agent_id: AgentId,
        request: AgentExecutionRequest,
        context: ContextResponse,
    ) -> str:
        payload = "\x00".join(
            (
                str(agent_id),
                self.backend_id,
                request.task,
                request.input_digest,
                context.workspace.workspace_id,
                context.workspace.commit or "",
                str(context.status),
            )
        )
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class CodexBody:
    """The independent second Agent's body.

    It delegates output production to a `CodexBackend`, and it owns the
    execution's tool calls. Those are two different questions: a backend answers
    "what did this model produce", and the execution answers "what did this
    execution run, and under which authorization".
    """

    backend: CodexBackend = field(default_factory=OfflineCodexBackend)
    plan: Sequence[ToolInvocation] = field(default_factory=tuple)

    agent_id: ClassVar[AgentId] = CODEX_AGENT_ID

    def run(
        self,
        *,
        request: AgentExecutionRequest,
        context: ContextResponse,
        tools: ToolGateway,
    ) -> BodyOutcome:
        if AgentId(request.agent_id) is not CODEX_AGENT_ID:
            raise ValueError(
                "CodexBody was given a request for a different Agent; a body "
                "serves one identity, and the attribution must not be "
                "rewritable by the caller (§5.1)"
            )

        # Every declared invocation goes to Guard, one fresh evaluation each.
        # A refusal is recorded and the body continues: §11.2 makes a refused
        # tool call a TOOL-level event, and the execution's own outcome is
        # decided by what the execution did.
        for invocation in self.plan:
            tools.invoke(invocation)

        return BodyOutcome(
            result_ref=self.backend.produce(
                agent_id=CODEX_AGENT_ID, request=request, context=context
            ),
            reason_code=REASON_COMPLETED,
        )
