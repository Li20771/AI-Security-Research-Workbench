"""T13 — the fail-closed matrix, one case per §21 row.

The assertion that matters is negative and is stated explicitly at the end of
this module: **none of these cases may produce `ALLOW`.**

A case is one row of §21. The two rows Amendment 7 added — an unevaluable
`match` — are here too, because a rule dropped for being hard to evaluate is the
fall-through §14 exists to prevent, one step earlier.
"""

from __future__ import annotations

import pytest

from plugins.guard import CheckResult, GuardDecision, evaluate

from tests.guard.conftest import (
    WS_OTHER,
    eq,
    make_context,
    make_context_item,
    make_policy,
    make_request,
    make_rule,
)

pytestmark = pytest.mark.layer2

PERMISSIVE = make_policy(make_rule("allow-all", priority=0))


def case(name: str, request, policy):
    return pytest.param(request, policy, id=name)


def _ctx(*items):
    return make_request(context={"response": make_context(*items)})


#: One entry per §21 row. `request`, `policy`, expected decision.
MATRIX = [
    case("missing_policy", make_request(), None),
    case("invalid_policy", make_request(), {"version": 99}),
    case("duplicate_rule_id", make_request(),
         make_policy(make_rule("d"), make_rule("d", priority=1))),
    case("policy_digest_mismatch", make_request(),
         make_policy(make_rule("allow"), digest="0" * 64)),
    case("policy_workspace_mismatch", make_request(),
         make_policy(make_rule("allow"), workspace_id=WS_OTHER)),
    case("unknown_workspace", make_request(
        workspace={**make_request()["workspace"], "workspace_id": ""}), PERMISSIVE),
    case("malformed_request", {"schema_version": 7}, PERMISSIVE),
    case("unsupported_field", make_request(),
         make_policy(make_rule("r", match=[{"field": "nope.field", "op": "eq", "value": "x"}]))),
    case("unsupported_predicate", make_request(),
         make_policy(make_rule("r", match=[{"field": "action.id", "op": "regex", "value": ".*"}]))),
    case("closed_vocabulary_unknown_value", make_request(),
         make_policy(make_rule("r", match=[eq("target.kind", "spaceship")]))),
    case("missing_context", make_request(context=None),
         make_policy(make_rule("r", conditions=[eq("context.g.truth_state", "PASS")]))),
    case("context_unknown", _ctx(make_context_item(truth_state="UNKNOWN")),
         make_policy(make_rule("r", conditions=[eq("context.declared.gate.truth_state", "PASS")]))),
    case("context_stale", _ctx(make_context_item(freshness="STALE")),
         make_policy(make_rule("r", conditions=[eq("context.declared.gate.truth_state", "PASS")]))),
    case("required_fact_absent_plan_present", _ctx(make_context_item(item_kind="PLAN")),
         make_policy(make_rule("r", conditions=[eq("context.declared.gate.item_kind", "FACT")]))),
    case("required_fact_absent_history_present", _ctx(make_context_item(item_kind="HISTORY")),
         make_policy(make_rule("r", conditions=[eq("context.declared.gate.item_kind", "FACT")]))),
    case("required_fact_absent_entirely", make_request(context=None),
         make_policy(make_rule("r", conditions=[eq("context.declared.gate.item_kind", "FACT")]))),
    case("missing_capability", make_request(capability={"id": "cap-1"}),
         make_policy(make_rule("r", conditions=[eq("capability.status", "VERIFIED")]))),
    case("capability_unknown", make_request(
        capability={"id": "c"},
        capability_state={"records": [{"capability_id": "c", "status": "UNKNOWN"}]}),
        make_policy(make_rule("r", conditions=[eq("capability.status", "VERIFIED")]))),
    case("capability_declared", make_request(
        capability={"id": "c"},
        capability_state={"records": [{"capability_id": "c", "status": "DECLARED"}]}),
        make_policy(make_rule("r", conditions=[eq("capability.status", "VERIFIED")]))),
    case("capability_not_verified", make_request(
        capability={"id": "c"},
        capability_state={"records": [{"capability_id": "c", "status": "NOT_VERIFIED"}]}),
        make_policy(make_rule("r", conditions=[eq("capability.status", "VERIFIED")]))),
    case("capability_unavailable", make_request(
        capability={"id": "c"},
        capability_state={"records": [{"capability_id": "c", "status": "UNAVAILABLE"}]}),
        make_policy(make_rule("r", conditions=[eq("capability.status", "VERIFIED")]))),
    case("missing_approval", make_request(approval={"status": "MISSING"}),
         make_policy(make_rule("r", conditions=[eq("approval.status", "VERIFIED")]))),
    case("approval_invalid", make_request(approval={"status": "INVALID"}),
         make_policy(make_rule("r", conditions=[eq("approval.status", "VERIFIED")]))),
    case("approval_unknown", make_request(approval={"status": "UNKNOWN"}),
         make_policy(make_rule("r", conditions=[eq("approval.status", "VERIFIED")]))),
    case("no_matching_rule", make_request(),
         make_policy(make_rule("r", match=[eq("action.id", "other")]))),
    case("explicit_deny", make_request(), make_policy(make_rule("r", effect="DENY"))),
]

# §21 also carries the row "ambiguous rule ordering -> BLOCKED". It is
# deliberately **absent** from the matrix above, because it is unreachable
# through the public path: §9.2 makes `rule_id` unique, and §12.2.2's
# linearization is total over a unique-id rule set, so no rule set can leave the
# order ambiguous. The row is defence-in-depth, and the guard that implements it
# is exercised directly in `test_ordering.py::TestRunawayGuard` rather than by a
# request that cannot arise. Recording the gap here is more useful than
# fabricating a case that would not actually be ambiguous.


class TestT13FailClosedMatrix:
    @pytest.mark.parametrize("req,pol", MATRIX)
    def test_none_of_these_produces_allow(self, req, pol):
        """The assertion that matters. Stated once, applied to every row."""
        assert evaluate(req, pol).decision is not GuardDecision.ALLOW

    @pytest.mark.parametrize("req,pol", MATRIX)
    def test_every_row_produces_a_defined_decision(self, req, pol):
        assert evaluate(req, pol).decision in set(GuardDecision)

    @pytest.mark.parametrize("req,pol", MATRIX)
    def test_every_row_carries_a_reason_code(self, req, pol):
        record = evaluate(req, pol)
        assert record.reason_code, f"{record.decision} with no reason code"

    @pytest.mark.parametrize("req,pol", MATRIX)
    def test_every_row_is_deterministic(self, req, pol):
        first, second = evaluate(req, pol), evaluate(req, pol)
        assert first.decision is second.decision
        assert first.reason_code == second.reason_code
        assert first.evaluation_digest == second.evaluation_digest


class TestT13ExpectedDecisions:
    """The specific §21 outcomes, where the row fixes one."""

    def test_missing_policy_blocks(self):
        assert evaluate(make_request(), None).decision is GuardDecision.BLOCKED

    def test_workspace_mismatch_denies(self):
        policy = make_policy(make_rule("allow"), workspace_id=WS_OTHER)
        assert evaluate(make_request(), policy).decision is GuardDecision.DENY

    def test_context_unknown_yields_unknown(self):
        rule = make_rule("r", conditions=[eq("context.declared.gate.truth_state", "PASS")])
        assert evaluate(_ctx(make_context_item(truth_state="UNKNOWN")), make_policy(rule)).decision is (
            GuardDecision.UNKNOWN
        )

    def test_capability_unknown_yields_unknown(self):
        request = make_request(
            capability={"id": "c"},
            capability_state={"records": [{"capability_id": "c", "status": "UNKNOWN"}]},
        )
        rule = make_rule("r", conditions=[eq("capability.status", "VERIFIED")])
        assert evaluate(request, make_policy(rule)).decision is GuardDecision.UNKNOWN

    def test_approval_unknown_blocks_not_unknown(self):
        """§8.1: approval is a precondition this contract owns, so UNKNOWN -> BLOCKED."""
        rule = make_rule("r", conditions=[eq("approval.status", "VERIFIED")])
        request = make_request(approval={"status": "UNKNOWN"})
        assert evaluate(request, make_policy(rule)).decision is GuardDecision.BLOCKED

    def test_unsupported_input_blocks_rather_than_rejects(self):
        """§11.6: a policy defect must not present as a clean 'rule does not apply'."""
        rule = make_rule("r", conditions=[eq("context.g.truth_state", "PASS")])
        record = evaluate(make_request(context=None), make_policy(rule))
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code != "NO_APPLICABLE_RULE"


class TestIndeterminateMatchIsRetained:
    """Amendment 7: an unevaluable `match` must not be dropped as a non-candidate."""

    def test_an_unavailable_match_stops_the_walk(self):
        specific = make_rule(
            "specific",
            priority=0,
            match=[eq("context.declared.gate.item_kind", "FACT")],
        )
        generic = make_rule("generic", priority=1)
        # No context at all, so the specific rule's match cannot be evaluated.
        record = evaluate(make_request(context=None), make_policy(specific, generic))
        assert record.decision is GuardDecision.BLOCKED

    def test_an_indeterminate_match_is_not_treated_as_a_non_match(self):
        """With a lower-priority generic ALLOW present, the specific rule must
        still be reached — the hazard §14 exists to close."""
        specific = make_rule(
            "specific",
            priority=0,
            match=[eq("context.declared.gate.truth_state", "PASS")],
        )
        generic = make_rule("generic", priority=5)
        request = _ctx(make_context_item(truth_state="UNKNOWN"))
        record = evaluate(request, make_policy(specific, generic))
        assert record.decision is GuardDecision.UNKNOWN
        assert record.provenance.rule_id == "specific"

    def test_the_trace_marks_the_indeterminate_candidate(self):
        specific = make_rule(
            "specific", priority=0, match=[eq("context.declared.gate.truth_state", "PASS")]
        )
        generic = make_rule("generic", priority=5)
        request = _ctx(make_context_item(truth_state="UNKNOWN"))
        record = evaluate(request, make_policy(specific, generic))
        assert any(c.result is CheckResult.INDETERMINATE for c in record.checks)
