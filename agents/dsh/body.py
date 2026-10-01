"""DSH — the primary Agent's Workbench-side execution shape.

```text
dsh -> AgentRole.PRIMARY          (§5.2, fixed registration)
```

### What this is not

**It is not DSH.** DSH is an external, GUI-only desktop platform baselined by
AI-01: no CLI on `PATH`, no headless entry point reachable from a shell, and no
startup log. AI-08 does not reimplement it, wrap it, or drive it — there is no
process here to drive.

What AI-08 owns is the Workbench-side **shape** of a DSH execution: an identity
that resolves to `PRIMARY`, a body that runs inside one execution instance, and
a result attributed to `dsh` alone.

### Why the v1 body is offline

Every capability on every shipped model profile is `UNKNOWN` and no provider call
has ever been made in this repository. The DSH body therefore cannot call a
model, and `agents.body.OfflineBody` — which performs no inference — is what v1
runs. It produces a **provenance reference**, not a task result, and
`COMPLETED` claims only that the execution reached a terminal result.

A future phase that gives DSH a model-backed body replaces the body, not the
contract: `AgentBody` is the seam, and `DSHBody` is already one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Sequence

from plugins.context import ContextResponse

from agents.body import BodyOutcome, OfflineBody
from agents.request import AgentExecutionRequest
from agents.toolcall import ToolGateway, ToolInvocation
from agents.vocabulary import AgentId

__all__ = ["DSHBody", "DSH_AGENT_ID"]


#: The one AgentId this body serves. Held as a constant rather than a
#: constructor argument so a caller cannot construct a "DSH body" that reports
#: itself as codex.
DSH_AGENT_ID = AgentId.DSH


@dataclass(frozen=True, slots=True)
class DSHBody:
    """The primary Agent's body.

    `plan` is the invocation sequence this body asks for; every entry goes
    through Guard. An empty plan is a complete execution with zero tool
    invocations (§7.1).
    """

    plan: Sequence[ToolInvocation] = field(default_factory=tuple)

    #: The identity this body executes as.
    #:
    #: A `ClassVar`, deliberately: as a dataclass field it would become a
    #: constructor parameter, and a caller could then build a "DSH body" that
    #: reports itself as codex. A body serves one identity, and that is a
    #: property of the type rather than an argument.
    agent_id: ClassVar[AgentId] = DSH_AGENT_ID

    def run(
        self,
        *,
        request: AgentExecutionRequest,
        context: ContextResponse,
        tools: ToolGateway,
    ) -> BodyOutcome:
        if AgentId(request.agent_id) is not DSH_AGENT_ID:
            # A body is bound to one Agent. Refusing here means a DSH execution
            # cannot be recorded against codex's identity by construction,
            # rather than by a later check that could be forgotten.
            raise ValueError(
                "DSHBody was given a request for a different Agent; a body "
                "serves one identity, and the attribution must not be "
                "rewritable by the caller (§5.1)"
            )
        return OfflineBody(agent_id=DSH_AGENT_ID, plan=self.plan).run(
            request=request, context=context, tools=tools
        )
