"""The two gates an invocation passes before anything runs.

Contract §9 and §12.3.

```text
gate 1   AI-06's own boundary check     this module, runs first
gate 2   AI-04 Guard                    the authorization, runs second
```

**Gate 1 is not a substitute for gate 2, and gate 2 is not a substitute for gate
1.** A request must pass both. Gate 1 exists because there are requests v1
cannot express at all — a real CAN interface, for instance — and asking Guard
about a target AI-06 will never execute would produce an authorization for
something that must not happen regardless of what any policy says.

### Gate 2 does not cache, widen or reuse

One `ALLOW` authorizes one invocation, as stated in that invocation's request
(§9.1). A second invocation asks again. There is no store of decisions here and
no parameter that could introduce one.
"""

from __future__ import annotations

from typing import Any, Mapping

from plugins.guard import GuardRequest, evaluate
from plugins.guard.models import WorkspaceRef
from plugins.guard.vocabulary import GuardDecision

from plugins.context.workspace import resolve_workspace

from plugins.security_tools.adapter import Invocation
from plugins.security_tools.errors import GuardUnavailable, TargetRefused
from plugins.security_tools.request import ToolRequest
from plugins.security_tools.vocabulary import (
    V1_PERMITTED_TARGET_ENVIRONMENTS,
    V1_PERMITTED_VEHICLE_INTERFACES,
    TargetInterface,
    TargetKind,
    VehicleInterface,
)

__all__ = [
    "ask_guard",
    "check_v1_target_boundary",
    "decision_summary",
    "guard_workspace_for",
    "unattributed_summary",
]

#: The target kinds §12 governs. A request naming one of these is held to the
#: v1 boundary whatever the operation says.
_VEHICLE_TARGET_KINDS = frozenset(
    {
        TargetKind.CAN_BUS,
        TargetKind.ECU,
        TargetKind.VEHICLE,
        TargetKind.ACTUATOR,
    }
)

#: AI-04's interfaces that are physical, whatever they are called.
_PHYSICAL_INTERFACES = frozenset(
    {
        TargetInterface.CAN,
        TargetInterface.CAN_FD,
        TargetInterface.LIN,
        TargetInterface.ETHERNET,
    }
)


def check_v1_target_boundary(request: ToolRequest, spec: Any) -> None:
    """Gate 1. Refuse a target v1 cannot express, before Guard is asked (§12.3).

    Fails closed. An unsettled classification is refused rather than treated as
    simulated: AI-04 §16 blocks rather than assuming, and "the caller probably
    meant vcan0" is not a classification. Nothing here substitutes a different
    interface to make an operation succeed (§12.5).
    """
    target = request.target
    needs_vehicle = (
        getattr(spec.environment, "vehicle_interface", VehicleInterface.NONE)
        is not VehicleInterface.NONE
        or target.kind in _VEHICLE_TARGET_KINDS
    )
    if not needs_vehicle:
        return

    if target.interface in _PHYSICAL_INTERFACES:
        raise TargetRefused(
            "this request names a physical vehicle interface. AI-06 v1 reaches "
            "vcan, a simulator or an isolated harness and nothing else (§12.2); "
            "the target is refused rather than downgraded"
        )

    if target.interface not in {
        _to_target_interface(member) for member in V1_PERMITTED_VEHICLE_INTERFACES
    }:
        raise TargetRefused(
            "this request's vehicle interface is not one v1 permits (§12.1). An "
            "unsettled classification is refused, never treated as simulated"
        )

    if target.environment not in V1_PERMITTED_TARGET_ENVIRONMENTS:
        raise TargetRefused(
            "this request's target environment is not one v1 permits (§12.1). "
            "`real` and `unknown` are both refusals, and `unknown` is not read "
            "as simulated"
        )

    if target.is_real is True:
        raise TargetRefused(
            "this request declares the target real (§12.2). AI-06 refuses it "
            "rather than substituting a simulated one"
        )


def _to_target_interface(member: VehicleInterface) -> TargetInterface:
    """AI-06's `VehicleInterface` member to AI-04's `TargetInterface` member.

    The two vocabularies name the same interfaces because AI-06's is a description
    of what an operation needs and AI-04's is the request's field. The mapping is
    explicit so a new member on either side is a visible edit rather than a
    silent default.
    """
    return {
        VehicleInterface.VCAN: TargetInterface.VCAN,
        VehicleInterface.SIMULATOR: TargetInterface.SIMULATOR,
        VehicleInterface.ISOLATED_HARNESS: TargetInterface.ISOLATED_HARNESS,
    }[member]


def guard_workspace_for(request: ToolRequest) -> WorkspaceRef:
    """Build AI-04's `WorkspaceRef` from the declared root (contract §9.3).

    The git state comes from AI-03's resolver rather than from a second
    implementation: that function already answers the question, and §42 of the
    brief forbids restating it. A root that is not its own repository resolves to
    `working_tree: UNKNOWN` with no branch and no commit — which is an answer
    AI-04 already handles, not an error to repair here.
    """
    root = request.workspace.root
    if root is None:
        return WorkspaceRef(
            workspace_id=request.workspace.workspace_id,
            repository=None,
            branch=None,
            commit=None,
            detached=False,
            working_tree=_unknown_working_tree(),
        )
    identity = resolve_workspace(root)
    return WorkspaceRef(
        workspace_id=request.workspace.workspace_id,
        repository=identity.repository,
        branch=identity.branch,
        commit=identity.commit,
        detached=identity.detached,
        working_tree=identity.working_tree,
    )


def ask_guard(
    request: ToolRequest,
    *,
    workspace: WorkspaceRef,
    evaluator: Any,
    policy: Any,
) -> tuple[GuardDecision, Mapping[str, str]]:
    """Gate 2. Ask AI-04, and fail closed if it cannot answer (§9.1, §9.2).

    `evaluate` is AI-04's frozen entry point and is called as it stands. AI-06
    does not wrap, extend, shadow or reimplement it, and does not evaluate a
    policy itself.

    Returns the decision **and** the attribution that came with it, from the
    same call. §8.1 requires a result to carry "the `guard` block naming the
    decision it ran under", and §8.3 requires a result to be attributable — so
    the `reason_code` and `decision_id` are part of the answer, not decoration
    that can be dropped on the way out.

    Returning the enum alone was a defect found in review: the decision survived
    and its attribution did not, so a `ToolResult` could say ALLOW while being
    unable to name which evaluation allowed it.

    An evaluator that raises is an evaluator that did not allow. The exception
    becomes `GuardUnavailable`, and `dispatch` turns that into a refusal — never
    into an execution.
    """
    guard_request = GuardRequest(
        actor=request.actor,
        workspace=workspace,
        action=_action_for(request),
        capability=_capability_for(request),
        target=request.target,
        approval=_approval_for(request),
    )
    try:
        decision_record = evaluator(guard_request, policy)
    except Exception as exc:  # noqa: BLE001 - any failure is a refusal
        raise GuardUnavailable(
            "the evaluator did not return a decision, so nothing is authorized. "
            "An evaluator that failed is not an evaluator that allowed (§9.2)"
        ) from exc
    decision = GuardDecision(decision_record.decision)
    return decision, decision_summary(decision, decision_record)


def unattributed_summary(decision: GuardDecision, reason_code: str) -> Mapping[str, str]:
    """The `guard` block for a request that never reached AI-04.

    A refusal raised before `ask_guard` — an unknown tool, a bad argument, a v1
    target boundary — has no `DecisionRecord` to point at, and saying so is more
    honest than inventing an identifier. `decision_id` stays empty precisely
    because no evaluation produced one.
    """
    return {"decision": str(decision), "reason_code": reason_code, "decision_id": ""}


def _action_for(request: ToolRequest) -> Any:
    from plugins.guard.models import ActionRef

    return ActionRef(id=request.operation, permission_level=request.permission_level)


def _capability_for(request: ToolRequest) -> Any:
    from plugins.guard.models import CapabilityRef

    return CapabilityRef(id=None)


def _approval_for(request: ToolRequest) -> Any:
    from plugins.guard.models import ApprovalRef

    # AI-06 carries an approval through; it never issues one and never invents
    # one. With no approval source in AI-04, an approval-gated action is
    # BLOCKED, which is the intended fail-closed behaviour and not a defect for
    # AI-06 to work around.
    return ApprovalRef(status=_missing_approval_status())


def _unknown_working_tree() -> Any:
    from plugins.guard.vocabulary import WorkingTreeState

    return WorkingTreeState.UNKNOWN


def _missing_approval_status() -> Any:
    from plugins.guard.vocabulary import ApprovalStatus

    return ApprovalStatus.MISSING


def decision_summary(decision: GuardDecision, record: Any) -> Mapping[str, str]:
    """The `guard` block a `ToolResult` carries (§8.1)."""
    return {
        "decision": str(decision),
        "reason_code": str(getattr(record, "reason_code", "")),
        "decision_id": str(getattr(record, "decision_id", "")),
    }
