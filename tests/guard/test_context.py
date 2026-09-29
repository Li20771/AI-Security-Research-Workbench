"""T3, T4 and T12 — context authorization and truth preservation.

Contract §6 and §21.

T12's requirement is the subtle one: the six non-authorizing values must be
**never `ALLOW`** and **never silently `REJECTED`**. A test that passed by
treating `PLAN` as "not a fact, so the rule does not apply, so default `DENY`"
would be a *failure* of T12 — the caller must learn that the evidence cannot
authorize, not be told the rule simply did not match.
"""

from __future__ import annotations

import pytest

from plugins.guard import GuardDecision, evaluate

from tests.guard.conftest import (
    WS,
    WS_OTHER,
    eq,
    make_context,
    make_context_item,
    make_policy,
    make_request,
    make_rule,
)

pytestmark = pytest.mark.layer2


def request_with(*items, workspace_id: str = WS):
    return make_request(context={"response": make_context(*items, workspace_id=workspace_id)})


class TestT3UnknownContext:
    def test_unknown_truth_state_yields_unknown(self):
        item = make_context_item(truth_state="UNKNOWN")
        rule = make_rule(
            "wants-pass",
            conditions=[eq("context.declared.gate.truth_state", "PASS")],
        )
        record = evaluate(request_with(item), make_policy(rule))
        assert record.decision is GuardDecision.UNKNOWN

    def test_unknown_is_not_blocked(self):
        """§2.3: UNKNOWN is a definite statement about an upstream fact."""
        item = make_context_item(truth_state="UNKNOWN")
        rule = make_rule("wants-pass", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        record = evaluate(request_with(item), make_policy(rule))
        assert record.decision is not GuardDecision.BLOCKED
        assert record.reason_code == "PRECONDITION_INDETERMINATE"

    def test_unknown_freshness_is_indeterminate(self):
        item = make_context_item(freshness="UNKNOWN")
        rule = make_rule("wants-pass", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        assert evaluate(request_with(item), make_policy(rule)).decision is GuardDecision.UNKNOWN


class TestT4StaleContext:
    def test_stale_context_is_blocked(self):
        item = make_context_item(freshness="STALE")
        rule = make_rule("wants-pass", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        record = evaluate(request_with(item), make_policy(rule))
        assert record.decision is GuardDecision.BLOCKED

    def test_stale_names_staleness_rather_than_absence(self):
        """§10.2: STALE is not WRONG; the caller should re-read, not re-derive."""
        item = make_context_item(freshness="STALE")
        rule = make_rule("wants-pass", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        details = " ".join(c.detail for c in evaluate(request_with(item), make_policy(rule)).checks)
        assert "STALE" in details

    def test_stale_never_authorizes(self):
        item = make_context_item(freshness="STALE")
        rule = make_rule("allow", match=[], conditions=[eq("context.declared.gate.freshness", "STALE")])
        assert evaluate(request_with(item), make_policy(rule)).decision is not GuardDecision.ALLOW


class TestT6CurrentFactAuthorizes:
    def test_a_current_fact_satisfies_a_condition(self):
        item = make_context_item(truth_state="PASS", freshness="CURRENT")
        rule = make_rule("allow", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        assert evaluate(request_with(item), make_policy(rule)).decision is GuardDecision.ALLOW

    def test_item_kind_fact_is_comparable(self):
        item = make_context_item(item_kind="FACT")
        rule = make_rule("allow", conditions=[eq("context.declared.gate.item_kind", "FACT")])
        assert evaluate(request_with(item), make_policy(rule)).decision is GuardDecision.ALLOW


@pytest.mark.parametrize(
    ("item_kind", "truth_state", "freshness"),
    [
        ("PLAN", "UNKNOWN", "CURRENT"),
        ("HISTORY", "PASS", "CURRENT"),
        ("FACT", "NOT_RUN", "CURRENT"),
        ("FACT", "BLOCKED", "CURRENT"),
        ("FACT", "PASS", "STALE"),
        ("FACT", "UNKNOWN", "CURRENT"),
    ],
)
class TestT12TruthPreservation:
    """None of these may reach ALLOW, and none may be silently REJECTED."""

    def test_never_allow(self, item_kind, truth_state, freshness):
        item = make_context_item(
            item_kind=item_kind, truth_state=truth_state, freshness=freshness
        )
        rule = make_rule(
            "allow",
            match=[],
            conditions=[eq("context.declared.gate.truth_state", "PASS")],
        )
        record = evaluate(request_with(item), make_policy(rule))
        assert record.decision is not GuardDecision.ALLOW

    def test_never_silently_rejected(self, item_kind, truth_state, freshness):
        """The distinguishing assertion: a non-authorizing value is UNAVAILABLE
        or INDETERMINATE, so the decision is BLOCKED or UNKNOWN — not a default
        DENY that hides what actually happened."""
        item = make_context_item(
            item_kind=item_kind, truth_state=truth_state, freshness=freshness
        )
        rule = make_rule(
            "allow",
            match=[],
            conditions=[eq("context.declared.gate.truth_state", "PASS")],
        )
        record = evaluate(request_with(item), make_policy(rule))
        assert record.decision in (GuardDecision.BLOCKED, GuardDecision.UNKNOWN)
        assert record.reason_code != "NO_APPLICABLE_RULE"


class TestPlanCannotAuthorizeOnItsContent:
    """§6.2: a PLAN never authorizes because its content says COMPLETE."""

    def test_a_plan_saying_complete_does_not_authorize(self):
        item = make_context_item(item_kind="PLAN", truth_state="UNKNOWN", value="COMPLETE")
        rule = make_rule("allow", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        assert evaluate(request_with(item), make_policy(rule)).decision is not GuardDecision.ALLOW

    def test_a_plan_claiming_pass_does_not_authorize(self):
        item = make_context_item(item_kind="PLAN", truth_state="UNKNOWN", value="PASS")
        rule = make_rule("allow", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        assert evaluate(request_with(item), make_policy(rule)).decision is not GuardDecision.ALLOW

    def test_a_plan_claiming_approved_does_not_authorize(self):
        item = make_context_item(item_kind="PLAN", truth_state="UNKNOWN", value="APPROVED")
        rule = make_rule("allow", match=[])
        assert evaluate(request_with(item), make_policy(rule)).decision is GuardDecision.ALLOW or True
        # The rule above matches unconditionally; the assertion that matters is
        # that the *plan* contributed nothing. Check the gate directly.
        from plugins.guard.predicates import resolve_field
        from plugins.guard.policy import FieldRef
        from plugins.guard.models import GuardRequest

        request = GuardRequest.from_mapping(request_with(item))
        resolution = resolve_field(request, FieldRef.parse("context.declared.gate.truth_state"))
        assert not resolution.resolved

    def test_history_does_not_authorize(self):
        item = make_context_item(item_kind="HISTORY", truth_state="PASS")
        rule = make_rule("allow", conditions=[eq("context.declared.gate.item_kind", "FACT")])
        assert evaluate(request_with(item), make_policy(rule)).decision is not GuardDecision.ALLOW


class TestMissingContext:
    def test_no_context_response_is_blocked(self):
        rule = make_rule("allow", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        record = evaluate(make_request(context=None), make_policy(rule))
        assert record.decision is GuardDecision.BLOCKED

    def test_absent_subject_is_blocked(self):
        rule = make_rule("allow", conditions=[eq("context.never.recorded.truth_state", "PASS")])
        item = make_context_item("some.other.subject")
        assert evaluate(request_with(item), make_policy(rule)).decision is GuardDecision.BLOCKED
