"""AI-14-B / B1 — Router selection -> Agent execution (§22.1, §5.2).

```text
RouterRequest -> routing.router.evaluate() -> RouterDecision   [SELECTS]
                                                    |
                                                    v  DATA, never a grant
                                AgentExecutionRequest -> agents.runtime
```

### What this module is, and what it is not

It is the caller-side plumbing §5.1 records as MISSING between two frozen
layers, and nothing more. It holds no decision of its own:

```text
FROZEN: the Router SELECTS. A `RouterDecision` is DATA. It is never an
        authorization, never a permission and never a Guard ALLOW (§4.2 rule 1).
FROZEN: an agent_hint is a HINT. It becomes an `AgentId` only by passing through
        `agents.vocabulary.resolve_agent`, which refuses anything not in the
        closed registry — so a hint cannot name an Agent the registry does not
        have, and cannot add one (§7).
FROZEN: an outcome that is not `SELECTED` is a STOP. `NO_ELIGIBLE_MODEL` is not a
        cue to try the next candidate, relax a constraint or reach for a default:
        AI-14 has no fallback, no retry and no escalation (§23).
```

### Why the selected model ref does not ride on the execution request

`AgentExecutionRequest` is AI-08's frozen shape and it refuses fields it does not
define. It carries no model ref, and this module MUST NOT add one — adding a
field to another phase's boundary is an amendment to THAT phase, not a
composition choice.

So the selection travels as what it is: `Selection.model_ref` is handed to the
provider binding (§8, `composition.provider`), which is the layer that turns a
model ref into an invocation. The execution request carries the execution's own
descriptors — which Agent, which workspace, which task, which input digest — and
the decision stays beside it as the audit record it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from agents.request import AgentExecutionRequest
from agents.vocabulary import AgentId, resolve_agent
from providers.model_profile import ModelProfile
from routing.decision import RouterDecision
from routing.request import RouterRequest
from routing.router import evaluate
from routing.rules import RuleSet
from routing.vocabulary import RoutingOutcome

from composition.errors import SelectionRefused

__all__ = ["Selection", "select"]


@dataclass(frozen=True, slots=True)
class Selection:
    """One evaluation and the execution request it produced.

    The two fields are deliberately separate. `decision` is the Router's own
    auditable record and is kept verbatim; `request` is what AI-08 will be given.
    Neither is derived from the other except for the Agent identity and the model
    ref, and neither carries authority over the other.
    """

    decision: RouterDecision
    request: AgentExecutionRequest

    @property
    def model_ref(self) -> str:
        """The model ref the Router selected, for the provider binding (§8).

        A `Selection` only exists for a `SELECTED` outcome, so this is never
        `None`.
        """
        return str(self.decision.selected)

    @property
    def agent_hint(self) -> str | None:
        """The hint the matched rule declared, as recorded — still only a hint."""
        return self.decision.agent_hint


def select(
    request: RouterRequest,
    *,
    rule_set: RuleSet,
    profiles: Mapping[str, ModelProfile],
    enabled_providers: frozenset[str],
    workspace_root: str,
    task: str,
    input_digest: str,
    default_agent: object,
    context_descriptor: str | None = None,
    clock: Callable[[], str] | None = None,
) -> Selection:
    """Evaluate one request and build the execution request it selects for.

    `enabled_providers` is required rather than optional: AI-07 fails closed on an
    omitted set ("no provider is enabled" is not "do not check"), and a
    composition that passed `None` by accident would be the one fail-open path
    into this call.

    `default_agent` is the identity used when the matched rule declared no hint.
    It is resolved through the registry like any other candidate, so the
    composition cannot introduce a third Agent identity by passing a string here
    (§7, §21).
    """
    decision = evaluate(
        request,
        rule_set,
        profiles=profiles,
        enabled_providers=enabled_providers,
        clock=clock,
    )

    if decision.outcome is not RoutingOutcome.SELECTED:
        raise SelectionRefused(
            "the Router did not select a model for this request "
            f"(outcome={decision.outcome}, reason={decision.reason_code}); no "
            "execution request is built and nothing is retried. A non-selecting "
            "outcome is a STOP (§22.1 B1): the composition has no fallback, no "
            "escalation and no default candidate to reach for"
        )

    # A hint becomes an identity only here, and only through the registry. An
    # unregistered hint raises `UnknownAgent` from `resolve_agent` rather than
    # being ignored or defaulted — ignoring it would silently execute under an
    # Agent the Router did not name.
    candidate: object = default_agent if decision.agent_hint is None else decision.agent_hint
    agent_id: AgentId = resolve_agent(candidate)

    execution_request = AgentExecutionRequest(
        agent_id=agent_id,
        workspace_root=workspace_root,
        task=task,
        input_digest=input_digest,
        context_descriptor=context_descriptor,
    )
    return Selection(decision=decision, request=execution_request)
