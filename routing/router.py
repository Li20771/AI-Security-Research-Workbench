"""The evaluation. Contract §7, §9, §10.

```text
evaluate(request, rule_set, registry) -> exactly ONE RouterDecision
```

**Nothing here executes.** No provider call, no transport, no socket, no
subprocess (§14). AI-07 selects; AI-02 makes a call when a caller asks it to, and
the Router never asks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from providers.model_profile import ModelProfile
from providers.profile import ModelRef, ProfileError

from routing.decision import RouterDecision
from routing.errors import InvalidRequest, InvalidRules
from routing.profile import capability_is_available, modality_satisfies
from routing.request import RouterRequest
from routing.rules import Rule, RuleSet
from routing.vocabulary import RoutingOutcome

__all__ = ["evaluate", "evaluate_mapping"]

#: Reasons a candidate is not eligible. Stable labels, never prose.
REASON_SELECTED = "RULE_MATCHED"
REASON_NO_RULE = "NO_MATCHING_RULE"
REASON_NO_CANDIDATES = "NO_ELIGIBLE_CANDIDATE"
REASON_MODEL_UNAVAILABLE = "MODEL_NOT_RESOLVABLE"
REASON_PROVIDER_DISABLED = "PROVIDER_DISABLED"
REASON_CAPABILITY_NOT_VERIFIED = "CAPABILITY_NOT_VERIFIED"
REASON_MODALITY_UNSUPPORTED = "MODALITY_UNSUPPORTED"


def _new_decision_id() -> str:
    return f"rt-{uuid.uuid4().hex[:16]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluate(
    request: RouterRequest,
    rule_set: RuleSet,
    *,
    profiles: Mapping[str, ModelProfile],
    enabled_providers: frozenset[str] | None = None,
    clock: Callable[[], str] | None = None,
    decision_id_factory: Callable[[], str] | None = None,
) -> RouterDecision:
    """One evaluation. Contract §7, §9, §10.

    `profiles` is AI-02's registry, keyed by `model_ref` — `load_all_model_profiles`
    returns exactly that. `enabled_providers` is AI-02's `ProviderConfig`, and a
    provider that is not enabled is not a candidate (§6.4).

    **Enablement fails closed.** An omitted `enabled_providers` means *no provider
    is enabled*, not *do not check*: AI-02 ships every provider `enabled: false`,
    and AI-07 reads that through `ProviderConfig` rather than deciding it. Reading
    an absent config as permission would be the one fail-open path in this module,
    and it was — an earlier revision treated `None` as "skip the check", so a
    disabled provider could be selected by simply not passing a config.

    `clock` and `decision_id_factory` are injectable so that the semantic content
    of a decision can be compared across two evaluations. They affect only the two
    audit identifiers, never the outcome.
    """
    now = (clock or _utc_now)()
    new_id = (decision_id_factory or _new_decision_id)()

    def decision(
        outcome: RoutingOutcome,
        reason_code: str,
        *,
        rule: Rule | None = None,
        selected: str | None = None,
    ) -> RouterDecision:
        return RouterDecision(
            decision_id=new_id,
            decided_at=now,
            outcome=outcome,
            reason_code=reason_code,
            rules_revision=rule_set.revision,
            requested=request.to_mapping(),
            matched_rule=None if rule is None else rule.rule_id,
            candidates=request.ordered_candidates,
            selected=selected,
            agent_hint=None if rule is None else rule.select_agent,
        )

    # §6.4: a latency-class constraint names a vocabulary AI-02 does not have.
    # Refused rather than ignored, and never guessed at.
    if request.max_latency_class is not None:
        raise InvalidRequest(
            "constraints.max_latency_class: AI-02 exposes no latency-class "
            "vocabulary, so this constraint cannot be evaluated (§6.4). It is "
            "refused rather than silently ignored, and AI-07 does not invent "
            "fast/medium/slow"
        )

    # §7.5: the candidate sequence is derived, never the caller's order.
    candidates = request.ordered_candidates

    # §7.6: no matching rule is NO_ELIGIBLE_MODEL, never an implicit default.
    rule = rule_set.first_match(request)
    if rule is None:
        return decision(RoutingOutcome.NO_ELIGIBLE_MODEL, REASON_NO_RULE)

    # §7.7: a rule may select an agent hint without naming a model.
    if rule.select_model_ref is None:
        return decision(
            RoutingOutcome.NO_ELIGIBLE_MODEL, REASON_NO_CANDIDATES, rule=rule
        )

    selected_ref = rule.select_model_ref

    # §7.7: a model the request did not name is not a candidate, and the Router
    # does not substitute one to make the request succeed.
    if selected_ref not in candidates:
        return decision(
            RoutingOutcome.MODEL_UNAVAILABLE, REASON_MODEL_UNAVAILABLE, rule=rule
        )

    profile = profiles.get(selected_ref)
    if profile is None:
        return decision(
            RoutingOutcome.MODEL_UNAVAILABLE, REASON_MODEL_UNAVAILABLE, rule=rule
        )

    # Fail closed: absent enablement is no enablement. There is deliberately no
    # `is not None` guard here, because that guard was the defect.
    enabled = frozenset() if enabled_providers is None else frozenset(enabled_providers)
    if profile.provider_id not in enabled:
        return decision(
            RoutingOutcome.MODEL_UNAVAILABLE, REASON_PROVIDER_DISABLED, rule=rule
        )

    # §6.2. Only VERIFIED satisfies. UNKNOWN, DECLARED, NOT_VERIFIED and
    # UNAVAILABLE all refuse, and there is no "probably" branch.
    if request.requested_capability is not None:
        try:
            requested = request.requested_capability
            available = capability_is_available(profile, requested)
        except ValueError:
            return decision(
                RoutingOutcome.NO_ELIGIBLE_MODEL,
                REASON_CAPABILITY_NOT_VERIFIED,
                rule=rule,
            )
        if not available:
            return decision(
                RoutingOutcome.NO_ELIGIBLE_MODEL,
                REASON_CAPABILITY_NOT_VERIFIED,
                rule=rule,
            )

    # §6.3. A modality requirement matches on AI-02's `modality`, because AI-02
    # defines no multimodal capability.
    if request.modality is not None and not modality_satisfies(profile, request.modality):
        return decision(
            RoutingOutcome.NO_ELIGIBLE_MODEL, REASON_MODALITY_UNSUPPORTED, rule=rule
        )

    return decision(
        RoutingOutcome.SELECTED, REASON_SELECTED, rule=rule, selected=selected_ref
    )


def evaluate_mapping(
    raw_request: object,
    raw_rule_set: object,
    *,
    profiles: Mapping[str, ModelProfile],
    enabled_providers: frozenset[str] | None = None,
    clock: Callable[[], str] | None = None,
    decision_id_factory: Callable[[], str] | None = None,
) -> RouterDecision:
    """The raw boundary: both the request and the rule set may be supplied as mappings.

    **This is where `INVALID_REQUEST` and `INVALID_RULES` become outcomes.** Both
    are frozen `RoutingOutcome` members (§10.1, §12.4), and an exception escaping
    the Router-facing API is not one of them — the exception is the mechanism, the
    outcome is the contract, exactly as AI-06 §17 puts it for a refusal.

    `RuleSet.from_mapping` and `RouterRequest.from_mapping` remain the validators
    and still raise. They are not the Router boundary, and this is.

    An invalid rule set produces `INVALID_RULES` with **no selection and no partial
    application**: validation completes before any rule is evaluated, so there is
    no state in which some rules were applied and others were not.
    """
    now = (clock or _utc_now)()
    new_id = (decision_id_factory or _new_decision_id)()

    try:
        rule_set = (
            raw_rule_set
            if isinstance(raw_rule_set, RuleSet)
            else RuleSet.from_mapping(raw_rule_set)
        )
    except InvalidRules as exc:
        return RouterDecision(
            decision_id=new_id,
            decided_at=now,
            outcome=RoutingOutcome.INVALID_RULES,
            reason_code=exc.reason_code,
            rules_revision="",
        )

    try:
        request = RouterRequest.from_mapping(raw_request)
    except InvalidRequest as exc:
        return RouterDecision(
            decision_id=new_id,
            decided_at=now,
            outcome=RoutingOutcome.INVALID_REQUEST,
            reason_code=exc.reason_code,
            rules_revision=rule_set.revision,
        )

    return evaluate(
        request,
        rule_set,
        profiles=profiles,
        enabled_providers=enabled_providers,
        clock=lambda: now,
        decision_id_factory=lambda: new_id,
    )
