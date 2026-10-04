"""AI-14-B / B4 — the controlled verification caller (AI-10 §11.1, §22.1).

```text
review.verification.VerificationRequest
        |
        v
the CONTROLLED VERIFICATION CALLER          <- this module, and nowhere else
        |
        v
plugins.security_tools.dispatch.invoke()    <- AI-06's ONE tool path
        |
        v
AI-04 Guard  ->  adapter  ->  ToolResult
        |
        v
review.verification.VerificationObservation
```

### Why the caller lives here and not in `review/`

AI-10 §11.1 froze the seam and stopped: *"AI-10 issues VerificationRequests. The
controlled verification caller performs the invocation and reports the
observation."* `review/` holds no evaluator, composes no `ToolRequest` and
imports no Guard — and it stays that way. This module is the other side, and it
lives outside both layers so that neither has to grow one.

### The mapping is DECLARED, never inferred

A `VerificationTarget` is a description ("this claim could be checked by
observing X"). It is NOT an operation, NOT a tool id and NOT a target ref — AI-10
refuses to convert one into the other, and the conversion belongs to the caller.
So the caller supplies a `ToolPlanEntry` per target, and this module refuses to
guess the rest:

```text
a target with no declared entry          REFUSED — no inference, no default tool
a plan entry for a target not asked for  REFUSED — the request bounds the work
a duplicate entry for one target         REFUSED — one target, one invocation
a permission level, actor or tool id     never derived from a name or a family
  in the request                           (AI-06 §6.2: privilege is SUPPLIED)
```

### What the caller does NOT get

```text
FROZEN: every invocation goes through `invoke()`, which asks Guard per call. The
        caller holds an evaluator only to hand it to that path; it never
        evaluates, never caches an ALLOW and never reuses one.
FROZEN: a refusal is REPORTED, not repaired. A non-ALLOW Guard decision arrives
        as a `ToolOutcome` (NOT_RUN / BLOCKED / UNKNOWN) and is carried into the
        observation unchanged — the caller does not retry, escalate or pick a
        different tool.
FROZEN: an observation is not a verdict (AI-10 §5). Nothing here produces PASS,
        FAIL or any judgement about the claim under review.
```

### A note on the actor

`Actor` is required by AI-06 and this module never invents one: the caller
declares it, exactly as it declares the permission level. A verification
invocation attributed to an identity nobody named would be a record whose actor
was decided by the composition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from plugins.context import utc_now
from plugins.guard.models import Actor, TargetRef
from plugins.guard.vocabulary import PermissionLevel
from plugins.security_tools import invoke
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.registry import ToolRegistry
from plugins.security_tools.request import ToolRequest, ToolWorkspace
from plugins.security_tools.result import ToolResult
from plugins.security_tools.vocabulary import AdapterFamily

from review.verification import VerificationObservation, VerificationRequest

from composition.errors import VerificationRefused

__all__ = ["ToolPlanEntry", "controlled_verification"]


@dataclass(frozen=True, slots=True)
class ToolPlanEntry:
    """One DECLARED mapping: this target, checked by this operation.

    Everything AI-06 requires of a request that is not the workspace and not the
    actor is here, declared by the caller: the tool identity, the operation, the
    permission level, the target ref and the per-invocation timeout.
    """

    target_id: str
    tool_id: str
    tool_version: str
    adapter_family: AdapterFamily
    operation: str
    permission_level: PermissionLevel
    target: TargetRef
    timeout_seconds: int
    arguments: Mapping[str, Any] = field(default_factory=dict)


def _validated_plan(
    request: VerificationRequest, plan: Sequence[ToolPlanEntry]
) -> tuple[ToolPlanEntry, ...]:
    """The plan, checked against the request — and in the request's own order."""
    declared: dict[str, ToolPlanEntry] = {}
    for entry in plan:
        if not isinstance(entry, ToolPlanEntry):
            raise VerificationRefused(
                "every plan entry must be a ToolPlanEntry; the mapping from a "
                "declared target to a tool request is the caller's to state"
            )
        if entry.target_id in declared:
            raise VerificationRefused(
                f"target {entry.target_id!r} is declared twice; one target is one "
                "invocation, and a second entry would silently replace the first"
            )
        declared[entry.target_id] = entry

    asked = {target.target_id for target in request.targets}
    unplanned = sorted(asked - set(declared))
    if unplanned:
        raise VerificationRefused(
            f"no tool request is declared for target(s) {', '.join(unplanned)}; the "
            "caller does not infer an operation from a description, and a "
            "verification that quietly skipped a target would report less than it "
            "was asked for"
        )
    unasked = sorted(set(declared) - asked)
    if unasked:
        raise VerificationRefused(
            f"the plan names target(s) {', '.join(unasked)} that this request did "
            "not ask for; a verification request bounds the work it authorises to "
            "be requested"
        )

    # The request's own order (targets are key-sorted by AI-10), so two runs of the
    # same request invoke in the same sequence.
    return tuple(declared[target.target_id] for target in request.targets)


def _observation(
    request: VerificationRequest, result: ToolResult, observed_at: str
) -> VerificationObservation:
    """Map one `ToolResult` onto AI-10's observation, changing nothing."""
    return VerificationObservation(
        verification_id=request.verification_id,
        review_case_id=request.review_case_id,
        subject=request.subject,
        outcome=result.outcome,
        reason_code=result.reason_code,
        tool_id=result.tool_id,
        tool_version=result.tool_version,
        operation=result.operation,
        guard_decision_id=str(result.guard.get("decision_id", "")),
        guard_reason_code=str(result.guard.get("reason_code", "")),
        duration_ms=result.duration_ms,
        observed_at=observed_at,
    )


def controlled_verification(
    request: VerificationRequest,
    *,
    plan: Sequence[ToolPlanEntry],
    workspace: ToolWorkspace,
    actor: Actor,
    registry: ToolRegistry,
    evaluator: Any,
    policy: Any,
    runner: Any = None,
    clock: Callable[[], str] | None = None,
) -> tuple[VerificationObservation, ...]:
    """Perform the invocations one verification request asks for, and report them.

    One target, one `invoke()` call, one fresh Guard evaluation. The sequence is
    the request's; the mapping is the plan's; the authorization is Guard's and
    nobody else's.
    """
    entries = _validated_plan(request, plan)
    now = (clock or utc_now)()

    observations: list[VerificationObservation] = []
    for entry in entries:
        tool_request = ToolRequest(
            workspace=workspace,
            tool=ToolIdentity(
                tool_id=entry.tool_id,
                tool_version=entry.tool_version,
                adapter_family=entry.adapter_family,
            ),
            operation=entry.operation,
            actor=actor,
            permission_level=entry.permission_level,
            target=entry.target,
            timeout_seconds=entry.timeout_seconds,
            arguments=dict(entry.arguments),
        )
        # One call, one fresh GuardRequest, one fresh GuardDecision — inside the
        # tool path, for every invocation, with no cache on this side either.
        result = invoke(
            tool_request,
            registry=registry,
            evaluator=evaluator,
            policy=policy,
            runner=runner,
        )
        observations.append(_observation(request, result, now))

    return tuple(observations)
