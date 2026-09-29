"""T2 and T10 — the policy input boundary, validation, and digests.

Contract §9.1 (`Guard.evaluate(request, policy)`), §9.2 (validation invariants)
and §20.2–§20.3 (canonicalization).

T10's shape changed in Amendment 9. It previously asserted a policy whose
`revision` differs from "the one the request was evaluated against" — a
comparison against a field this contract does not define and never did. It now
covers the boundary that exists.
"""

from __future__ import annotations

import pytest

from plugins.guard import GuardDecision, Policy, PolicyInvalid, evaluate, policy_digest
from plugins.guard.ordering import order_rules

from tests.guard.conftest import eq, make_policy, make_request, make_rule


pytestmark = pytest.mark.layer2


class TestT2MissingPolicy:
    def test_no_policy_is_blocked(self):
        record = evaluate(make_request(), None)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_MISSING"

    def test_no_policy_leaves_policy_provenance_null(self):
        record = evaluate(make_request(), None)
        assert record.provenance.policy_id is None
        assert record.provenance.policy_revision is None
        assert record.provenance.policy_digest is None
        assert record.provenance.rule_id is None

    def test_missing_policy_is_not_deny(self):
        """§13: BLOCKED describes an unavailable evaluation; DENY is a decision."""
        assert evaluate(make_request(), None).decision is not GuardDecision.DENY


class TestT10aValidPolicy:
    def test_a_valid_policy_is_evaluated(self):
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        assert record.decision is GuardDecision.ALLOW
        assert record.provenance.policy_id == "policy-1"
        assert record.provenance.policy_revision == "rev-1"

    def test_a_matching_declared_digest_is_accepted(self):
        policy = Policy.from_mapping(make_policy(make_rule("allow")))
        declared = policy_digest(policy)
        raw = make_policy(make_rule("allow"), digest=declared)
        record = evaluate(make_request(), raw)
        assert record.decision is GuardDecision.ALLOW


class TestT10bDigestMismatch:
    def test_a_wrong_declared_digest_is_blocked(self):
        raw = make_policy(make_rule("allow"), digest="0" * 64)
        record = evaluate(make_request(), raw)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_DIGEST_MISMATCH"

    def test_the_mismatch_records_both_digests(self):
        raw = make_policy(make_rule("allow"), digest="0" * 64)
        joined = " ".join(evaluate(make_request(), raw).reasons)
        assert "0" * 64 in joined

    def test_a_mismatch_is_not_recomputed_and_tolerated(self):
        raw = make_policy(make_rule("allow"), digest="0" * 64)
        assert evaluate(make_request(), raw).decision is not GuardDecision.ALLOW


class TestT10cInvalidPolicy:
    @pytest.mark.parametrize(
        "bad",
        [
            {"version": 99, "policy_id": "p", "revision": "r", "workspace_id": "ws-1", "rules": []},
            {"version": 1, "policy_id": "", "revision": "r", "workspace_id": "ws-1", "rules": []},
            {"version": 1, "policy_id": "p", "revision": "r", "workspace_id": "ws-1", "rules": {}},
        ],
    )
    def test_a_malformed_policy_is_blocked(self, bad):
        assert evaluate(make_request(), bad).decision is GuardDecision.BLOCKED

    def test_an_unlisted_effect_is_rejected(self):
        rule = make_rule("r", effect="BLOCKED")
        with pytest.raises(PolicyInvalid):
            Policy.from_mapping(make_policy(rule))

    def test_an_unlisted_predicate_is_rejected(self):
        rule = make_rule("r", match=[{"field": "action.id", "op": "matches", "value": ".*"}])
        with pytest.raises(PolicyInvalid):
            Policy.from_mapping(make_policy(rule))

    def test_an_unsupported_field_is_rejected(self):
        rule = make_rule("r", match=[eq("request.secret", "x")])
        with pytest.raises(PolicyInvalid):
            Policy.from_mapping(make_policy(rule))

    def test_a_literal_outside_its_domain_is_rejected(self):
        rule = make_rule("r", match=[eq("target.kind", "not_a_kind")])
        with pytest.raises(PolicyInvalid):
            Policy.from_mapping(make_policy(rule))


class TestT10fDuplicateRuleId:
    def test_a_duplicate_rule_id_is_blocked(self):
        policy = make_policy(make_rule("same"), make_rule("same", priority=1))
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_DUPLICATE_RULE_ID"

    def test_a_duplicate_is_never_resolved_by_keeping_one(self):
        """§9.2 names the four forbidden resolutions; none may produce a decision."""
        policy = make_policy(make_rule("same"), make_rule("same", priority=1))
        record = evaluate(make_request(), policy)
        assert record.provenance.rule_id is None

    def test_the_duplicate_id_is_named(self):
        policy = make_policy(make_rule("same"), make_rule("same", priority=1))
        assert "same" in " ".join(evaluate(make_request(), policy).reasons)

    def test_three_way_duplicate_is_still_blocked(self):
        policy = make_policy(*(make_rule("same", priority=i) for i in range(3)))
        assert evaluate(make_request(), policy).decision is GuardDecision.BLOCKED


class TestT10gRulePermutation:
    """§20.1: policy rule order is not a semantic input."""

    @staticmethod
    def _rules():
        return [
            make_rule("a-generic", priority=5, match=[eq("action.id", "read-file")]),
            make_rule(
                "b-specific",
                priority=5,
                match=[eq("action.id", "read-file"), eq("target.kind", "repository")],
            ),
            make_rule("c-deny-elsewhere", priority=5, effect="DENY",
                      match=[eq("action.id", "other")]),
        ]

    def test_permuting_rules_leaves_the_policy_digest_unchanged(self):
        import itertools

        digests = {
            policy_digest(Policy.from_mapping(make_policy(*perm)))
            for perm in itertools.permutations(self._rules())
        }
        assert len(digests) == 1, f"policy.digest depends on file order: {digests}"

    def test_permuting_rules_leaves_decision_and_digest_unchanged(self):
        import itertools

        outcomes = set()
        for perm in itertools.permutations(self._rules()):
            record = evaluate(make_request(), make_policy(*perm))
            outcomes.add((str(record.decision), record.provenance.rule_id,
                          record.evaluation_digest))
        assert len(outcomes) == 1, f"file order changed the outcome: {outcomes}"

    def test_the_evaluation_trace_is_not_the_digest_order(self):
        """§20.3, D-18: the two orders are different and must not be conflated."""
        policy = Policy.from_mapping(make_policy(*self._rules()))
        digest_order = [r.rule_id for r in sorted(policy.rules, key=lambda r: r.rule_id)]
        walk_order = [r.rule_id for r in order_rules(policy.rules)]
        assert digest_order != walk_order, (
            "the fixture must distinguish the two orders for this test to mean "
            "anything"
        )
