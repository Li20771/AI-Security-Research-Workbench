"""T7 — rule ordering.

Contract §12, §12.2.2, and the Amendment 9 counterexample.

T7g is the load-bearing sub-case. Sub-cases 7a–7f all use rule sets whose
specificity relation happens to be a chain, or has only one incomparable pair,
and the composite comparator the contract forbids orders those consistently —
which is exactly why the defect survived the earlier review. 7g is the minimal
shape where it cycles.
"""

from __future__ import annotations

import itertools

import pytest

from plugins.guard.ordering import (
    constraints_for,
    is_total_order,
    linearize_bucket,
    order_rules,
    strictly_more_specific,
)
from plugins.guard.policy import Rule
from plugins.guard.vocabulary import RuleEffect

from tests.guard.conftest import eq, make_rule


pytestmark = pytest.mark.layer2


def rule(rule_id: str, **match_fields) -> Rule:
    match = [eq(field, value) for field, value in match_fields.items()]
    return Rule.from_mapping(make_rule(rule_id, match=match), 0)


def rule_effect(rule_id: str, effect: str, **match_fields) -> Rule:
    match = [eq(field, value) for field, value in match_fields.items()]
    return Rule.from_mapping(make_rule(rule_id, effect=effect, match=match), 0)


class TestSpecificityRelation:
    """§12.2's per-field relation, transcribed."""

    def test_a_rule_with_more_constraints_is_more_specific(self):
        general = rule("g", **{"action.id": "a"})
        specific = Rule.from_mapping(
            make_rule("s", match=[eq("action.id", "a"), eq("target.kind", "repository")]), 0
        )
        assert strictly_more_specific(
            constraints_for(specific.match), constraints_for(general.match)
        )

    def test_eq_is_at_least_as_specific_as_a_containing_in(self):
        narrow = Rule.from_mapping(make_rule("n", match=[eq("action.id", "a")]), 0)
        wide = Rule.from_mapping(
            make_rule("w", match=[{"field": "action.id", "op": "in", "value": ["a", "b"]}]), 0
        )
        assert strictly_more_specific(
            constraints_for(narrow.match), constraints_for(wide.match)
        )
        assert not strictly_more_specific(
            constraints_for(wide.match), constraints_for(narrow.match)
        )

    def test_exists_is_less_specific_than_eq(self):
        exists_rule = Rule.from_mapping(
            make_rule("e", match=[{"field": "action.id", "op": "exists"}]), 0
        )
        eq_rule = Rule.from_mapping(make_rule("q", match=[eq("action.id", "a")]), 0)
        assert strictly_more_specific(
            constraints_for(eq_rule.match), constraints_for(exists_rule.match)
        )

    def test_identical_matches_are_not_strictly_ordered(self):
        a = rule("a", **{"action.id": "x"})
        b = rule("b", **{"action.id": "x"})
        assert not strictly_more_specific(
            constraints_for(a.match), constraints_for(b.match)
        )


class TestT7aSamePriorityDenyBeforeAllow:
    def test_deny_wins_over_allow_at_equal_priority(self):
        deny = rule_effect("r-deny", "DENY")
        allow = rule_effect("r-allow", "ALLOW")
        ordered = order_rules([allow, deny])
        assert [r.rule_id for r in ordered] == ["r-deny", "r-allow"]

    def test_deny_first_regardless_of_rule_id(self):
        deny = rule_effect("z-deny", "DENY")
        allow = rule_effect("a-allow", "ALLOW")
        assert [r.rule_id for r in order_rules([allow, deny])] == ["z-deny", "a-allow"]


class TestT7bDifferentPriority:
    def test_lower_numeric_priority_wins(self):
        low = Rule.from_mapping(make_rule("low", priority=0), 0)
        high = Rule.from_mapping(make_rule("high", priority=10), 0)
        assert [r.rule_id for r in order_rules([high, low])] == ["low", "high"]

    def test_priority_outranks_effect(self):
        """A high-priority ALLOW precedes a low-priority DENY."""
        allow0 = Rule.from_mapping(make_rule("allow", priority=0, effect="ALLOW"), 0)
        deny9 = Rule.from_mapping(make_rule("deny", priority=9, effect="DENY"), 0)
        assert [r.rule_id for r in order_rules([deny9, allow0])] == ["allow", "deny"]


class TestT7cSpecificBeforeGeneric:
    def test_the_more_specific_rule_is_emitted_first(self):
        generic = Rule.from_mapping(make_rule("generic", match=[eq("action.id", "a")]), 0)
        specific = Rule.from_mapping(
            make_rule("specific", match=[eq("action.id", "a"), eq("target.kind", "repository")]),
            0,
        )
        ordered = order_rules([generic, specific])
        assert [r.rule_id for r in ordered] == ["specific", "generic"]


class TestT7dIncomparableRules:
    def test_incomparable_rules_are_ordered_by_rule_id(self):
        a = Rule.from_mapping(make_rule("r-a", match=[eq("action.id", "x")]), 0)
        b = Rule.from_mapping(make_rule("r-b", match=[eq("target.kind", "repository")]), 0)
        ordered = order_rules([b, a])
        assert [r.rule_id for r in ordered] == ["r-a", "r-b"]

    def test_incomparable_rules_are_not_forced_into_a_relation(self):
        a = constraints_for(rule("a", **{"action.id": "x"}).match)
        b = constraints_for(rule("b", **{"target.kind": "repository"}).match)
        assert not strictly_more_specific(a, b)
        assert not strictly_more_specific(b, a)


class TestT7eCompleteTie:
    def test_a_complete_tie_orders_by_rule_id_both_ways(self):
        a = Rule.from_mapping(make_rule("aaa"), 0)
        b = Rule.from_mapping(make_rule("bbb"), 0)
        assert [r.rule_id for r in order_rules([a, b])] == ["aaa", "bbb"]
        assert [r.rule_id for r in order_rules([b, a])] == ["aaa", "bbb"]


class TestT7fPolicyFileOrderIsIrrelevant:
    def test_every_permutation_of_a_mixed_policy_gives_one_order(self):
        rules = [
            Rule.from_mapping(make_rule("a-generic", priority=5, match=[eq("action.id", "z")]), 0),
            Rule.from_mapping(
                make_rule(
                    "b-specific",
                    priority=5,
                    match=[eq("action.id", "z"), eq("target.kind", "repository")],
                ),
                0,
            ),
            Rule.from_mapping(make_rule("c-deny", priority=5, effect="DENY"), 0),
            Rule.from_mapping(make_rule("d-high-priority", priority=0), 0),
        ]
        orders = {
            tuple(r.rule_id for r in order_rules(list(perm)))
            for perm in itertools.permutations(rules)
        }
        assert len(orders) == 1, f"file order changed the ordering: {orders}"

    def test_the_single_order_preserves_every_declared_relation(self):
        rules = [
            Rule.from_mapping(make_rule("g", match=[eq("action.id", "z")]), 0),
            Rule.from_mapping(
                make_rule("s", match=[eq("action.id", "z"), eq("target.kind", "repository")]),
                0,
            ),
        ]
        ordered = order_rules(rules)
        assert is_total_order(ordered)


class TestT7gAmendment9Counterexample:
    """The minimal shape where a composite comparator cycles.

    X is strictly more specific than Y; Y and Z are incomparable; Z and X are
    incomparable. The composite gives X ≺ Y (specificity), Y ≺ Z (r1 < r2),
    Z ≺ X (r2 < r3) — a cycle, and three distinct orders across six
    permutations. The linearization gives one.
    """

    @staticmethod
    def bucket() -> list[Rule]:
        """The contract's abstract `a`/`b` fields, on real vocabulary values.

        X constrains two fields, Y one of them, Z a different one — which is
        the whole shape: two rules each more specific than a third at different
        fields, and incomparable to each other.
        """
        x = Rule.from_mapping(
            make_rule("r3", match=[eq("action.id", "1"), eq("target.kind", "repository")]),
            0,
        )
        y = Rule.from_mapping(make_rule("r1", match=[eq("action.id", "1")]), 0)
        z = Rule.from_mapping(make_rule("r2", match=[eq("target.kind", "service")]), 0)
        return [x, y, z]

    def test_the_declared_relation_is_the_counterexample_shape(self):
        x, y, z = self.bucket()
        cx, cy, cz = (constraints_for(r.match) for r in (x, y, z))

        assert strictly_more_specific(cx, cy), "X ⊏ Y"
        assert not strictly_more_specific(cy, cz), "Y ∥ Z"
        assert not strictly_more_specific(cz, cy), "Y ∥ Z"
        assert not strictly_more_specific(cz, cx), "Z ∥ X"
        assert not strictly_more_specific(cx, cz), "Z ∥ X"

    def test_every_input_permutation_emits_the_same_order(self):
        orders = {
            tuple(r.rule_id for r in linearize_bucket(list(perm)))
            for perm in itertools.permutations(self.bucket())
        }
        assert len(orders) == 1, f"the linearization is not permutation-invariant: {orders}"

    def test_the_documented_order_is_z_x_y(self):
        """§12.2.3 works the counterexample out to Z, X, Y."""
        assert [r.rule_id for r in linearize_bucket(self.bucket())] == ["r2", "r3", "r1"]

    def test_specificity_is_preserved_in_every_permutation(self):
        """X ⊏ Y implies X is emitted before Y — the property a comparator loses."""
        for perm in itertools.permutations(self.bucket()):
            order = [r.rule_id for r in linearize_bucket(list(perm))]
            assert order.index("r3") < order.index("r1"), perm

    def test_no_cycle_is_reported(self):
        from plugins.guard.errors import OrderingCycle

        for perm in itertools.permutations(self.bucket()):
            try:
                linearize_bucket(list(perm))
            except OrderingCycle:  # pragma: no cover - the failure path
                pytest.fail("the linearization reported a cycle on an acyclic relation")


class TestRunawayGuard:
    def test_an_empty_available_set_is_reported_not_looped(self, monkeypatch):
        """`available` emptying should be unreachable; it must not hang if it happens."""
        import plugins.guard.ordering as ordering
        from plugins.guard.errors import OrderingCycle

        rules = [Rule.from_mapping(make_rule("a"), 0), Rule.from_mapping(make_rule("b"), 0)]
        monkeypatch.setattr(ordering, "_precedes", lambda a, b: True)
        with pytest.raises(OrderingCycle):
            ordering.linearize_bucket(rules)
