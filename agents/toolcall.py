"""AI-08 §12, §13.4 — the tool invocation path.

```text
FROZEN: AI-08 MUST NOT modify AI-04 and MUST NOT add a surface to Guard.
FROZEN: AI-08 MUST NOT cache, widen, reuse or pre-authorize any Guard decision.
FROZEN: AI-08 MUST NOT evaluate a policy itself, and MUST NOT wrap, extend,
        reimplement or shadow Guard.evaluate(request, policy).
```

### Why this delegates to AI-06 rather than calling Guard

AI-08-A §16 records the boundary: *"AI-06 Security tools plugin — the tool
execution path AI-08 invokes (§12)"*. AI-06's `ask_guard` already builds a
**fresh `GuardRequest` per invocation** and calls AI-04's `evaluate` exactly
once, and its `dispatch.invoke` refuses to run any adapter without an `ALLOW`.
Reusing that path is what keeps this layer from becoming a second authorization
system:

```text
one invocation  ->  one ToolRequest
                ->  one fresh GuardRequest
                ->  one fresh GuardDecision
                ->  at most one adapter run
```

`evaluate` is passed to AI-06 as AI-04's frozen entry point, unmodified. AI-08
never calls it, never inspects a policy and never reconstructs a decision.

### §13.4 — what "independent tool permission records" means here

The roadmap requires *独立工具权限记录*. In AI-08 v1 that is satisfied at the
**execution level**: each Agent's tool invocations carry their own Guard
decision, made against their own request, with their own `actor.id`. It is
**not** a durable AI-05 EvidenceRecord, and AI-08 v1 must not be read as
claiming one (§13.1). That is why this module satisfies the requirement without
conflicting with AI-05 C-1.

### §12.1.1 — no permission ceiling, and none inferred

`permission_level` is supplied by the caller, on the invocation, exactly as
AI-04 requires. It is **never** derived from `AgentId`, from `AgentRole` or from
`ActorType`. AI-08 v1 has no Agent-specific permission ceiling; a ceiling read
off an identity would be an authorization design nobody approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from plugins.guard import Actor, ActorType, PermissionLevel, TargetRef, evaluate
from plugins.security_tools import (
    AdapterFamily,
    ToolIdentity,
    ToolRegistry,
    ToolRequest,
    ToolWorkspace,
    invoke,
)

from agents.result import ToolCallRef
from agents.vocabulary import AgentId

__all__ = ["ToolGateway", "ToolInvocation", "ToolUnavailable"]


class ToolUnavailable(RuntimeError):
    """The execution has no tool path configured.

    A configuration fact, not a tool outcome: AI-06's `invoke` requires a
    registry, and inventing a `ToolOutcome` for "nobody wired this" would put a
    claim about a tool into a field that answers a different question.
    """

    reason_code = "TOOL_PATH_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """What a body asks for. Authorization is not the body's to decide.

    `permission_level` is the level the caller declares for this operation. It
    is a request, not a grant: Guard decides, and a refusal is an outcome this
    layer records rather than an exception it swallows.
    """

    tool_id: str
    tool_version: str
    adapter_family: AdapterFamily
    operation: str
    permission_level: PermissionLevel
    target: TargetRef
    timeout_seconds: int
    arguments: Mapping[str, Any] = field(default_factory=dict)
    environment: Mapping[str, str] = field(default_factory=dict)


class ToolGateway:
    """One execution's tool path. Per execution, and never shared.

    §8.2 forbids two executions sharing tool state, and the simplest way to
    guarantee that is for the gateway to belong to exactly one execution. Two
    gateways hold two `calls` tuples and have no path to each other.
    """

    __slots__ = ("_agent_id", "_calls", "_policy", "_registry", "_workspace_id", "_workspace_root")

    def __init__(
        self,
        *,
        agent_id: AgentId,
        workspace_id: str,
        workspace_root: str | None,
        registry: ToolRegistry | None = None,
        policy: Any = None,
    ) -> None:
        self._agent_id = AgentId(agent_id)
        self._workspace_id = workspace_id
        self._workspace_root = workspace_root
        self._registry = registry
        self._policy = policy
        self._calls: list[ToolCallRef] = []

    @property
    def agent_id(self) -> AgentId:
        return self._agent_id

    @property
    def calls(self) -> tuple[ToolCallRef, ...]:
        """Every invocation this execution asked for, authorized or refused."""
        return tuple(self._calls)

    def invoke(self, invocation: ToolInvocation) -> ToolCallRef:
        """Ask AI-06 to run one invocation, under a fresh Guard evaluation.

        The `actor` is this execution's `AgentId`, typed `ActorType.AGENT`: the
        identity question and the kind question stay separate (§5.3), and the
        value that reaches Guard is the registered id, not a role and not a
        display name.
        """
        if self._registry is None:
            raise ToolUnavailable(
                "this execution has no tool registry, so no invocation can be "
                "put to Guard. A tool call is authorized or it does not "
                "happen; there is no third path (§12)"
            )

        request = ToolRequest(
            workspace=ToolWorkspace(
                workspace_id=self._workspace_id, root=self._workspace_root
            ),
            tool=ToolIdentity(
                tool_id=invocation.tool_id,
                tool_version=invocation.tool_version,
                adapter_family=invocation.adapter_family,
            ),
            operation=invocation.operation,
            actor=Actor(id=str(self._agent_id), type=ActorType.AGENT),
            permission_level=invocation.permission_level,
            target=invocation.target,
            timeout_seconds=invocation.timeout_seconds,
            arguments=dict(invocation.arguments),
            environment=dict(invocation.environment),
        )

        # One call, one fresh GuardRequest, one fresh GuardDecision. AI-06
        # builds the request per invocation, so there is no object here that
        # could be reused even if a caller wanted to reuse one.
        result = invoke(
            request,
            registry=self._registry,
            evaluator=evaluate,
            policy=self._policy,
        )

        guard = result.guard
        reference = ToolCallRef(
            ordinal=len(self._calls),
            tool_id=result.tool_id,
            tool_version=result.tool_version,
            operation=result.operation,
            outcome=result.outcome,
            guard_decision=result.guard_decision,
            guard_decision_id=str(guard.get("decision_id", "")),
            guard_reason_code=str(guard.get("reason_code", "")),
            duration_ms=result.duration_ms,
        )
        self._calls.append(reference)
        return reference
