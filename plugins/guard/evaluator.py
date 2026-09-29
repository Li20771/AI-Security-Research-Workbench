"""The Guard evaluator.

Implements AI-04 contract §12–§16 and the §14.1 walk, and exposes the frozen
entry point of §9.1:

    Guard.evaluate(request, policy)

The policy is a **parameter**, not something Guard finds. Guard verifies and
evaluates an externally supplied snapshot; it performs no discovery, storage,
selection or loading. A component that both chooses its rules and applies them
can authorize anything by choosing a permissive rule set, and no amount of
evaluation-time rigour would detect it.

Order of work, and why each step is where it is:

    1. normalize and scope          malformed -> DENY, unscoped -> DENY (§15.1)
    2. workspace agreement          mismatch -> DENY (§5)
    3. policy validation            invalid  -> BLOCKED (§9.2)
    4. ordering                     §12, by linearization (§12.2.2)
    5. the walk                     §14.1
    6. approval and target gates    before any ALLOW, never after (§14.1 step 6)
    7. assembly                     §18, §19, §20

Step 6 is a **gate, not an override**: it can turn an `ALLOW` into `BLOCKED`,
never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from plugins.guard.digest import (
    RuleTraceEntry,
    evaluation_digest,
    evaluation_projection,
    policy_digest,
    request_digest,
)
from plugins.guard.errors import (
    GuardError,
    OrderingCycle,
    PolicyDigestMismatch,
    PolicyInvalid,
    PolicyMissing,
    PolicyWorkspaceMismatch,
    RequestMalformed,
    RequestUnscoped,
)
from plugins.guard.models import (
    CheckRecord,
    DecisionRecord,
    GuardRequest,
    Provenance,
    TargetRef,
)
from plugins.guard.ordering import order_rules
from plugins.guard.policy import Policy, Rule, validate_policy
from plugins.guard.predicates import evaluate_predicates, explain_predicates
from plugins.guard.vocabulary import (
    AGGREGATE_DECISION,
    ApprovalStatus,
    CheckResult,
    GuardDecision,
    PermissionLevel,
    TargetEnvironment,
    TargetInterface,
    TargetKind,
    TargetSensitivity,
    aggregate,
)

#: Target kinds whose real-world classification §16 requires. For these, an
#: unsettled environment, interface or `is_real` is `BLOCKED` rather than
#: assumed safe — "the distinction matters" because the consequence is physical.
VEHICLE_TARGET_KINDS: frozenset[TargetKind] = frozenset(
    {
        TargetKind.CAN_BUS,
        TargetKind.ECU,
        TargetKind.VEHICLE,
        TargetKind.ACTUATOR,
    }
)

#: Permission levels §15.2 approval-gates.
APPROVAL_GATED_LEVELS: frozenset[PermissionLevel] = frozenset(
    {PermissionLevel.SYSTEM_CHANGE, PermissionLevel.REMOTE_CHANGE}
)


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """The result of a boundary check that runs before or after the walk."""

    decision: GuardDecision | None = None
    reason_code: str = ""
    reasons: tuple[str, ...] = ()

    @property
    def blocks(self) -> bool:
        return self.decision is not None


def _clean_gate() -> GateOutcome:
    return GateOutcome()


# --------------------------------------------------------------------------
# Boundaries (§15, §16)
# --------------------------------------------------------------------------


def check_absolute_deny(request: GuardRequest) -> GateOutcome:
    """§15.1 absolute deny. Checked before policy, never overridden by it."""
    target = request.target

    if (
        target.kind is TargetKind.SECRET_MATERIAL
        or target.sensitivity is TargetSensitivity.SECRET_MATERIAL
    ):
        return GateOutcome(
            decision=GuardDecision.DENY,
            reason_code="SECRET_MATERIAL_ACCESS",
            reasons=(
                "direct secret-material access is an absolute deny (§15.1); "
                "Guard never handles credential values (§17)",
            ),
        )

    if not request.workspace.workspace_id.strip():
        return GateOutcome(
            decision=GuardDecision.DENY,
            reason_code="UNSCOPED_REQUEST",
            reasons=("the request carries no workspace scope (§15.1)",),
        )

    return _clean_gate()


def check_target_classification(request: GuardRequest) -> GateOutcome:
    """§16: an unclassified target is not a safe target.

    Applies where the real/simulated distinction *matters* — a vehicle-network
    target — because the failure mode there is not a wrong report but a real
    vehicle being actuated because a field was absent and a default was
    convenient.
    """
    target = request.target
    if target.kind not in VEHICLE_TARGET_KINDS:
        return _clean_gate()

    unsettled: list[str] = []
    if target.environment is None or target.environment is TargetEnvironment.UNKNOWN:
        unsettled.append("environment")
    if target.interface is None or target.interface is TargetInterface.UNKNOWN:
        unsettled.append("interface")
    if target.is_real is None:
        unsettled.append("is_real")

    if unsettled:
        return GateOutcome(
            decision=GuardDecision.BLOCKED,
            reason_code="TARGET_CLASSIFICATION_UNKNOWN",
            reasons=(
                f"target kind {target.kind} requires a settled real/simulated "
                f"classification; {', '.join(unsettled)} is not established",
                "an unclassified target is never inferred to be simulated (§16)",
            ),
        )
    return _clean_gate()


def target_is_real(request: GuardRequest) -> bool:
    """Whether the target is *positively* known to be real."""
    target = request.target
    return (
        target.environment is TargetEnvironment.REAL or target.is_real is True
    )


def check_approval_gate(request: GuardRequest) -> GateOutcome:
    """§15.2: approval-gated actions need a verified approval, or `BLOCKED`.

    AI-04 v1 implements no approval issuance (§8.2), so with no verified source
    every gated action is permanently `BLOCKED`. That is the intended
    fail-closed state, not a defect.
    """
    gated: str | None = None
    if request.action.permission_level in APPROVAL_GATED_LEVELS:
        gated = f"permission level {request.action.permission_level}"
    elif request.target.kind in VEHICLE_TARGET_KINDS and target_is_real(request):
        gated = f"real target kind {request.target.kind}"
    elif target_is_real(request) and request.target.kind is not TargetKind.UNKNOWN:
        gated = f"real target kind {request.target.kind}"

    if gated is None:
        return _clean_gate()

    if request.approval.status is ApprovalStatus.VERIFIED:
        return _clean_gate()

    return GateOutcome(
        decision=GuardDecision.BLOCKED,
        reason_code="APPROVAL_NOT_VERIFIED",
        reasons=(
            f"{gated} is approval-gated (§15.2)",
            f"approval status is {request.approval.status}; a verified approval "
            "is required and AI-04 issues none (§8)",
        ),
    )


# --------------------------------------------------------------------------
# Workspace and policy gates (§5, §9)
# --------------------------------------------------------------------------


def check_workspace_agreement(request: GuardRequest, policy: Policy) -> GateOutcome:
    """§5. A mismatch is never merged, filtered, or repaired."""
    if policy.workspace_id != request.workspace.workspace_id:
        return GateOutcome(
            decision=GuardDecision.DENY,
            reason_code="WORKSPACE_MISMATCH",
            reasons=(
                f"policy names workspace {policy.workspace_id!r} but the request "
                f"names {request.workspace.workspace_id!r}",
                "a workspace mismatch is a determined negative (§5)",
            ),
        )
    return _clean_gate()


def check_policy(request: GuardRequest, policy: Policy) -> GateOutcome:
    """§9.2 validation and the declared-digest check.

    Runs **before** ordinary rule evaluation: an invalid policy must never reach
    the evaluator, because its rules may be unordered, ambiguous, or absent.
    """
    try:
        validate_policy(policy)
    except PolicyInvalid as exc:
        return GateOutcome(
            decision=GuardDecision.BLOCKED,
            reason_code=exc.reason_code,
            reasons=(str(exc),),
        )

    if policy.digest_is_declared:
        computed = policy_digest(policy)
        if computed != policy.digest:
            return GateOutcome(
                decision=GuardDecision.BLOCKED,
                reason_code="POLICY_DIGEST_MISMATCH",
                reasons=(
                    f"declared digest {policy.digest} does not match the "
                    f"canonical form {computed}",
                    "the snapshot being evaluated is not the one that was "
                    "reviewed, so it is refused (§9.2)",
                ),
            )
    return _clean_gate()


# --------------------------------------------------------------------------
# The walk (§14.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WalkResult:
    decision: GuardDecision
    reason_code: str
    reasons: tuple[str, ...]
    rule: Rule | None
    trace: tuple[RuleTraceEntry, ...]
    checks: tuple[CheckRecord, ...]


def walk(request: GuardRequest, ordered: Sequence[Rule]) -> WalkResult:
    """§14.1 steps 2–5.

    Candidate selection and the walk are one pass in contract order, but the
    **trace records every rule**, candidates and non-candidates alike, so a
    reader can see why a rule was skipped rather than only that it was.
    """
    trace: list[RuleTraceEntry] = []
    checks: list[CheckRecord] = []

    match_results: dict[str, CheckResult] = {}
    match_details: dict[str, tuple[str, ...]] = {}
    for rule in ordered:
        result, details = explain_predicates(request, rule.match)
        match_results[rule.rule_id] = result
        match_details[rule.rule_id] = details
        checks.append(
            CheckRecord(
                check_id=f"{rule.rule_id}.match",
                result=result,
                source="match",
                detail="; ".join(details) or f"{len(rule.match)} predicate(s)",
            )
        )

    for rule in ordered:
        match_result = match_results[rule.rule_id]

        # Step 2: match SATISFIED and indeterminate rules are candidates;
        # REJECTED rules are not (they failed at the first predicate that did
        # not apply, and their conditions are not evaluated).
        is_candidate = match_result is not CheckResult.REJECTED

        if not is_candidate:
            trace.append(
                RuleTraceEntry(
                    rule_id=rule.rule_id,
                    effect=str(rule.effect),
                    match_result=str(match_result),
                    aggregate=str(match_result),
                    candidate=False,
                    decided=False,
                )
            )
            continue

        conditions_result, condition_details = explain_predicates(
            request, rule.conditions
        )
        checks.append(
            CheckRecord(
                check_id=f"{rule.rule_id}.conditions",
                result=conditions_result,
                source="conditions",
                detail="; ".join(condition_details)
                or f"{len(rule.conditions)} predicate(s)",
            )
        )
        # The rule's aggregate combines its match with its conditions. Because
        # UNAVAILABLE and INDETERMINATE dominate the §14.2 precedence, an
        # unevaluable match keeps the candidate indeterminate however its
        # conditions resolved.
        candidate_result = aggregate((match_result, conditions_result))

        decided = False
        if candidate_result is CheckResult.SATISFIED:
            decided = True
            trace.append(
                RuleTraceEntry(
                    rule_id=rule.rule_id,
                    effect=str(rule.effect),
                    match_result=str(match_result),
                    aggregate=str(candidate_result),
                    candidate=True,
                    decided=True,
                )
            )
            return WalkResult(
                decision=GuardDecision(str(rule.effect)),
                reason_code=rule.reason_code,
                reasons=(f"rule {rule.rule_id} was satisfied",),
                rule=rule,
                trace=tuple(trace),
                checks=tuple(checks),
            )

        if candidate_result in (
            CheckResult.UNAVAILABLE,
            CheckResult.INDETERMINATE,
        ):
            # Steps 4a/4b: an indeterminate candidate stops the walk. It cannot
            # decide -- its match did not hold -- but it must not be passed over
            # either, which is the whole reason §14.0 retains it.
            trace.append(
                RuleTraceEntry(
                    rule_id=rule.rule_id,
                    effect=str(rule.effect),
                    match_result=str(match_result),
                    aggregate=str(candidate_result),
                    candidate=True,
                    decided=False,
                )
            )
            decision = AGGREGATE_DECISION[candidate_result]
            assert decision is not None  # UNAVAILABLE/INDETERMINATE always map
            return WalkResult(
                decision=decision,
                reason_code=(
                    "PRECONDITION_UNAVAILABLE"
                    if candidate_result is CheckResult.UNAVAILABLE
                    else "PRECONDITION_INDETERMINATE"
                ),
                reasons=(
                    f"rule {rule.rule_id} could not be evaluated: "
                    f"{candidate_result}",
                    "an indeterminate rule is never passed over in favour of a "
                    "lower-precedence generic allow (§14)",
                ),
                rule=rule,
                trace=tuple(trace),
                checks=tuple(checks),
            )

        # REJECTED: the candidate does not apply; continue.
        trace.append(
            RuleTraceEntry(
                rule_id=rule.rule_id,
                effect=str(rule.effect),
                match_result=str(match_result),
                aggregate=str(candidate_result),
                candidate=True,
                decided=decided,
            )
        )

    # Step 5: every candidate was reached and evaluated, and none decided.
    return WalkResult(
        decision=GuardDecision.DENY,
        reason_code="NO_APPLICABLE_RULE",
        reasons=("no applicable ALLOW rule exists; default DENY (§13)",),
        rule=None,
        trace=tuple(trace),
        checks=tuple(checks),
    )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def _now() -> str:
    from plugins.context.context import utc_now

    return utc_now()


def _decision_id() -> str:
    """A generated runtime identifier. **Never** part of a semantic digest."""
    import uuid

    return f"grd-{uuid.uuid4().hex[:16]}"


def _record(
    request: GuardRequest,
    policy: Policy | None,
    *,
    decision: GuardDecision,
    reason_code: str,
    reasons: Sequence[str],
    checks: Sequence[CheckRecord] = (),
    trace: Sequence[RuleTraceEntry] = (),
    rule_id: str | None = None,
    context_refs: Sequence[str] = (),
) -> DecisionRecord:
    policy_digest_value = policy_digest(policy) if policy is not None else ""
    request_digest_value = request_digest(request)

    projection = evaluation_projection(
        request_digest_value=request_digest_value,
        policy=policy if policy is not None else Policy(
            policy_id="", revision="", workspace_id="", rules=()
        ),
        policy_digest_value=policy_digest_value,
        trace=trace,
        context_refs=context_refs,
        decision=str(decision),
        reason_code=reason_code,
        rule_id=rule_id,
    )

    return DecisionRecord(
        decision=decision,
        reason_code=reason_code,
        reasons=tuple(reasons),
        workspace_id=request.workspace.workspace_id,
        actor=request.actor,
        action=request.action,
        capability=request.capability.id,
        target=request.target,
        provenance=Provenance(
            policy_id=policy.policy_id if policy is not None else None,
            policy_revision=policy.revision if policy is not None else None,
            policy_digest=policy_digest_value or None,
            rule_id=rule_id,
            context_refs=tuple(sorted(context_refs)),
            approval_reference=request.approval.reference,
        ),
        checks=tuple(checks),
        request_digest=request_digest_value,
        evaluation_digest=evaluation_digest(projection),
        decision_id=_decision_id(),
        evaluated_at=_now(),
    )


def _context_refs(request: GuardRequest) -> tuple[str, ...]:
    """AI-03 `ItemRef` renderings for every item consulted.

    References, never payloads: §18.3 forbids raw context in the decision record.
    """
    response = request.context
    if response is None:
        return ()
    refs: list[str] = []
    for item in (*response.facts, *response.history, *response.plans):
        if item.workspace_id != request.workspace.workspace_id:
            continue
        refs.append(item.ref.render())
    return tuple(sorted(refs))


def evaluate(
    request: GuardRequest | Mapping[str, Any],
    policy: Policy | Mapping[str, Any] | None,
) -> DecisionRecord:
    """The frozen entry point (§9.1).

    `request` and `policy` may be raw mappings or already-normalized values.
    Every failure is converted to a decision; nothing escapes as an exception,
    because a caller that received a traceback would learn nothing about what
    was wrong and an absent answer must fail closed.
    """
    # --- step 1: normalize -------------------------------------------------
    try:
        normalized_request = (
            request if isinstance(request, GuardRequest) else GuardRequest.from_mapping(request)
        )
    except RequestUnscoped as exc:
        return _unscoped_record(request, exc)
    except RequestMalformed as exc:
        return _malformed_record(request, exc)
    except GuardError as exc:  # defensive: unforeseen normalization failure
        return _malformed_record(request, exc)

    # --- step 2: policy presence and shape ---------------------------------
    if policy is None:
        return _blocked_without_policy(
            normalized_request, PolicyMissing("no policy was supplied (§9.1)")
        )
    try:
        normalized_policy = (
            policy if isinstance(policy, Policy) else Policy.from_mapping(policy)
        )
    except PolicyInvalid as exc:
        return _blocked_without_policy(normalized_request, exc)

    # --- step 3: workspace, then policy validity ---------------------------
    workspace_gate = check_workspace_agreement(normalized_request, normalized_policy)
    if workspace_gate.blocks:
        return _record(
            normalized_request,
            normalized_policy,
            decision=workspace_gate.decision,  # type: ignore[arg-type]
            reason_code=workspace_gate.reason_code,
            reasons=workspace_gate.reasons,
            context_refs=_context_refs(normalized_request),
        )

    policy_gate = check_policy(normalized_request, normalized_policy)
    if policy_gate.blocks:
        return _record(
            normalized_request,
            normalized_policy,
            decision=policy_gate.decision,  # type: ignore[arg-type]
            reason_code=policy_gate.reason_code,
            reasons=policy_gate.reasons,
            context_refs=_context_refs(normalized_request),
        )

    # --- step 4: absolute safety invariants, before any rule ---------------
    absolute = check_absolute_deny(normalized_request)
    if absolute.blocks:
        return _record(
            normalized_request,
            normalized_policy,
            decision=absolute.decision,  # type: ignore[arg-type]
            reason_code=absolute.reason_code,
            reasons=absolute.reasons,
            context_refs=_context_refs(normalized_request),
        )

    # --- step 5: ordering ---------------------------------------------------
    try:
        ordered = order_rules(normalized_policy.rules)
    except OrderingCycle as exc:
        return _record(
            normalized_request,
            normalized_policy,
            decision=GuardDecision.BLOCKED,
            reason_code=exc.reason_code,
            reasons=(str(exc),),
            context_refs=_context_refs(normalized_request),
        )

    # --- step 6: the walk ---------------------------------------------------
    result = walk(normalized_request, ordered)

    # --- step 7: gates before any ALLOW ------------------------------------
    if result.decision is GuardDecision.ALLOW:
        for gate in (
            check_target_classification(normalized_request),
            check_approval_gate(normalized_request),
        ):
            if gate.blocks:
                return _record(
                    normalized_request,
                    normalized_policy,
                    decision=gate.decision,  # type: ignore[arg-type]
                    reason_code=gate.reason_code,
                    reasons=result.reasons + gate.reasons,
                    checks=result.checks,
                    trace=result.trace,
                    rule_id=result.rule.rule_id if result.rule else None,
                    context_refs=_context_refs(normalized_request),
                )

    return _record(
        normalized_request,
        normalized_policy,
        decision=result.decision,
        reason_code=result.reason_code,
        reasons=result.reasons,
        checks=result.checks,
        trace=result.trace,
        rule_id=result.rule.rule_id if result.rule else None,
        context_refs=_context_refs(normalized_request),
    )


# --------------------------------------------------------------------------
# Failure records
#
# A decision must be produced even when the input could not be read. These build
# a record from whatever *is* readable, so the caller still learns what failed.
# --------------------------------------------------------------------------


def _blank_request() -> GuardRequest:
    from plugins.guard.models import (
        Actor,
        ActionRef,
        ApprovalRef,
        CapabilityRef,
        TargetRef,
        WorkspaceRef,
    )
    from plugins.guard.vocabulary import (
        ActorType,
        ApprovalStatus,
        PermissionLevel,
        TargetKind,
        WorkingTreeState,
    )

    return GuardRequest(
        actor=Actor(id="", type=ActorType.UNKNOWN),
        workspace=WorkspaceRef(
            workspace_id="",
            repository=None,
            branch=None,
            commit=None,
            detached=False,
            working_tree=WorkingTreeState.UNKNOWN,
        ),
        action=ActionRef(id="", permission_level=PermissionLevel.READ),
        capability=CapabilityRef(id=None),
        target=TargetRef(kind=TargetKind.UNKNOWN),
        approval=ApprovalRef(status=ApprovalStatus.MISSING),
    )


def _salvage(raw: Any) -> GuardRequest:
    """Best-effort extraction, so a failure record can name the workspace."""
    if not isinstance(raw, Mapping):
        return _blank_request()
    workspace = raw.get("workspace")
    workspace_id = (
        workspace.get("workspace_id") if isinstance(workspace, Mapping) else None
    )
    if not isinstance(workspace_id, str):
        return _blank_request()
    try:
        request = _blank_request()
        return replace(request, workspace=replace(request.workspace, workspace_id=workspace_id))
    except Exception:  # noqa: BLE001 - salvage must never raise
        return _blank_request()


def _malformed_record(raw: Any, exc: GuardError) -> DecisionRecord:
    request = _salvage(raw)
    return _record(
        request,
        None,
        decision=GuardDecision.DENY,
        reason_code=exc.reason_code,
        reasons=(
            str(exc),
            "a malformed request is an absolute deny (§15.1, §21)",
        ),
    )


def _unscoped_record(raw: Any, exc: GuardError) -> DecisionRecord:
    request = _salvage(raw)
    return _record(
        request,
        None,
        decision=GuardDecision.DENY,
        reason_code=exc.reason_code,
        reasons=(
            str(exc),
            "an unscoped authorization request is an absolute deny (§15.1)",
        ),
    )


def _blocked_without_policy(request: GuardRequest, exc: GuardError) -> DecisionRecord:
    return _record(
        request,
        None,
        decision=GuardDecision.BLOCKED,
        reason_code=exc.reason_code,
        reasons=(str(exc),),
    )


__all__ = [
    "APPROVAL_GATED_LEVELS",
    "VEHICLE_TARGET_KINDS",
    "GateOutcome",
    "WalkResult",
    "check_absolute_deny",
    "check_approval_gate",
    "check_policy",
    "check_target_classification",
    "check_workspace_agreement",
    "evaluate",
    "target_is_real",
    "walk",
]
