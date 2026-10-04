"""AI-14-B / B6 — the composition root (§22.1, §5.2).

```text
Context  ->  Router (SELECTS)  ->  Agent execution  ->  Provider / model boundary
                                          |
                                          +--> Security Tools -> Guard -> ToolResult
                                          |
                                          v
                                    AgentResult (a REFERENCE)
```

### What a composition root is

It is the caller that §5.1 records as missing: the thing that calls the frozen
layers in the frozen order and returns what they produced. It is **not** a
component (§3 lists twelve and this is not a thirteenth), it is **not** an
authority (§4's matrix is unchanged by it), and it holds **no** decision of its
own.

```text
FROZEN: the root CALLS existing entry points. It creates no second way into a
        layer, no store, no daemon, no scheduler and no test-only bypass.
FROZEN: the root adds no authority. It cannot choose a permission, produce a
        Guard ALLOW, persist an Evidence record, mint a workflow approval or read
        a RouterDecision as authorization.
FROZEN: nothing here retries, falls back or escalates. A refusal from any layer
        is returned as that layer's own refusal.
FROZEN: Review and Benchmark are reached only when a caller asks for them. This
        root does not invoke either, and neither is on the task path.
```

### What the caller still owns

The workspace root, the task descriptor, the routing rules and registry, the
enabled-provider set, the agent body (offline or provider-backed, §8) and the
tool registry and Guard policy. The root assembles them; it does not decide any
of them, and it reads no credential and opens no network client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from providers.model_profile import ModelProfile

from agents.body import AgentBody
from agents.request import AgentExecutionRequest
from agents.result import AgentResult
from agents.runtime import run_execution

from routing.decision import RouterDecision
from routing.request import RouterRequest
from routing.rules import RuleSet

from composition.selection import select

__all__ = ["WorkbenchRun", "run_task"]


@dataclass(frozen=True, slots=True)
class WorkbenchRun:
    """One composed task, as references.

    The decision is kept because it is the audit record of WHY this model and this
    Agent, and the request is kept because it is what the execution was given.
    Neither is authority, and the result is a REFERENCE — never inline content.
    """

    decision: RouterDecision
    request: AgentExecutionRequest
    result: AgentResult
    workspace_id: str

    @property
    def model_ref(self) -> str:
        return str(self.decision.selected)

    @property
    def execution_id(self) -> str:
        return self.result.execution_id


def run_task(
    *,
    workspace_root: str,
    task: str,
    input_digest: str,
    router_request: RouterRequest,
    rule_set: RuleSet,
    profiles: Mapping[str, ModelProfile],
    enabled_providers: frozenset[str],
    body: AgentBody,
    default_agent: object,
    context_descriptor: str | None = None,
    registry: Any = None,
    policy: Any = None,
    clock: Callable[[], str] | None = None,
) -> WorkbenchRun:
    """Run one task through the connected path and return what it produced.

    The order is the contract's:

    ```text
    1  the Router SELECTS                     a non-selecting outcome is a STOP
    2  the selection becomes a request        through the registry, never around it
    3  the execution runs                     AI-08 establishes and owns its context
    4  the execution's tool calls             go through Guard inside the tool path
    5  one terminal result                     a reference, never content
    ```

    `run_execution` is AI-08's own entry point: the Context this execution uses is
    the one AI-08 establishes for it (§8.1), which is why the root does not build
    one itself. A second ContextResponse would be a second context, and the
    execution's own is the one that belongs to it.
    """
    selection = select(
        router_request,
        rule_set=rule_set,
        profiles=profiles,
        enabled_providers=enabled_providers,
        workspace_root=workspace_root,
        task=task,
        input_digest=input_digest,
        default_agent=default_agent,
        context_descriptor=context_descriptor,
        clock=clock,
    )

    record = run_execution(
        selection.request,
        body=body,
        registry=registry,
        policy=policy,
        clock=clock,
    )

    return WorkbenchRun(
        decision=selection.decision,
        request=selection.request,
        result=record.result,
        workspace_id=(
            "" if record.context is None else record.context.workspace.workspace_id
        ),
    )
