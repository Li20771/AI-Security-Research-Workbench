"""Rule ordering: structural specificity, linearized.

Implements AI-04 contract §12 and §12.2.2, as amended by Amendment 9.

**This module must not contain a comparator.** §12.0 is explicit: steps 4 and 5
are one *procedure*, not a `sort` with a comparison function. The reason is not
style. Structural specificity `⊏` is a **partial** order — two rules may be
incomparable — and the composite

    if the specificity relation decides, use it
    otherwise, use rule_id ascending

is **not transitive**. An implementation using it can be walked into a cycle and
produces different orders for the same rules depending on input order.

The counterexample that forced Amendment 9, three rules in one bucket:

    X = match { a: eq 1, b: eq 2 }     rule_id r3
    Y = match { a: eq 1 }              rule_id r1
    Z = match { b: eq 3 }              rule_id r2

    X ⊏ Y      comparable
    Y ∥ Z      incomparable
    Z ∥ X      incomparable

The composite gives `X ≺ Y` (specificity), `Y ≺ Z` (r1 < r2), `Z ≺ X` (r2 < r3)
— a cycle. Under the linearization below the order is uniquely `Z, X, Y` for
every permutation of the input.

`rule_id` is still used, but as a **local** choice among rules that are
*simultaneously available* — those with no remaining specificity predecessor —
rather than as a global lexical fallback. That distinction is what restores
transitivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from plugins.guard.errors import OrderingCycle
from plugins.guard.policy import Predicate, Rule

#: The four constraint forms of §12.2, after normalisation.
#:
#: `eq v` is normalised to `in {v}` because §12.2 declares them equivalent, and
#: the normalised form makes every per-field comparison a set comparison.
ABSENT = "absent"  # no constraint on this field
EXISTS = "exists"  # any present, non-null value
IN = "in"  # a finite value set


@dataclass(frozen=True, slots=True)
class Constraint:
    """One field's constraint within a rule's `match`."""

    kind: str
    values: frozenset[object] = frozenset()

    @staticmethod
    def absent() -> "Constraint":
        return Constraint(kind=ABSENT)

    @staticmethod
    def exists() -> "Constraint":
        return Constraint(kind=EXISTS)

    @staticmethod
    def in_(values: Iterable[object]) -> "Constraint":
        return Constraint(kind=IN, values=frozenset(values))


def _intersect(left: Constraint, right: Constraint) -> Constraint:
    """The effective constraint when two predicates constrain one field.

    A rule's `match` is a conjunction, so a field constrained twice is
    constrained by the *intersection*. Taking the union, or the last predicate
    seen, would make specificity depend on predicate order — the very thing
    §20.3 rules out by declaring `match` set-semantic.
    """
    if left.kind == ABSENT:
        return right
    if right.kind == ABSENT:
        return left
    if left.kind == EXISTS:
        return right
    if right.kind == EXISTS:
        return left
    return Constraint.in_(left.values & right.values)


def constraints_for(predicates: Sequence[Predicate]) -> Mapping[str, Constraint]:
    """The per-field constraint map of a `match` (§12.2).

    Order-independent: conjunction is commutative and `_intersect` is too, so
    permuting the predicates yields the same map.
    """
    result: dict[str, Constraint] = {}
    for predicate in predicates:
        field = predicate.field.text
        if predicate.op == "exists":
            addition = Constraint.exists()
        else:
            addition = Constraint.in_(predicate.values)
        current = result.get(field)
        result[field] = addition if current is None else _intersect(current, addition)
    return result


def at_least_as_specific(a: Constraint, b: Constraint) -> bool:
    """`A_f ⊑ B_f` — "A is at least as specific as B at this field" (§12.2).

    Transcibed from the contract's per-field table. `absent` is the *bottom*:
    a rule that does not constrain a field is the least specific there, so
    `X ⊑ absent` holds for every X and `absent ⊑ X` holds only for `absent`.
    """
    if b.kind == ABSENT:
        return True
    if a.kind == ABSENT:
        return False
    if a.kind == EXISTS:
        return b.kind == EXISTS
    if b.kind == EXISTS:
        return True
    return a.values <= b.values


def strictly_more_specific(
    a: Mapping[str, Constraint], b: Mapping[str, Constraint]
) -> bool:
    """Rule A is strictly more specific than rule B (§12.2).

    `A_f ⊑ B_f` for **every** field, and strictly for **at least one**. Fields
    absent from both maps are unconstrained in both and contribute nothing.
    """
    fields = set(a) | set(b)
    if not all(
        at_least_as_specific(a.get(f, Constraint.absent()), b.get(f, Constraint.absent()))
        for f in fields
    ):
        return False
    return any(
        not at_least_as_specific(
            b.get(f, Constraint.absent()), a.get(f, Constraint.absent())
        )
        for f in fields
    )


def _precedes(a: Rule, b: Rule) -> bool:
    """`A -> B`: A must be evaluated before B (§12.2.2)."""
    return strictly_more_specific(constraints_for(a.match), constraints_for(b.match))


def linearize_bucket(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """Deterministic Kahn-style emission within one `(priority, effect)` bucket.

    Transcribed from §12.2.2:

        remaining = every rule in the bucket
        while remaining is not empty:
            available = rules in remaining with no remaining specificity predecessor
            choose the available rule with the lexicographically smallest rule_id
            emit it; remove it from remaining

    `available` is the set of rules nothing remaining must precede — the
    currently *most specific* remaining rules. The contract uses "available"
    rather than "maximal" or "minimal" because those two words are read in
    opposite directions by different conventions, and the direction is
    load-bearing.

    Raises `OrderingCycle` if `available` ever empties. That should be
    unreachable — `⊏` is a partial order, hence acyclic — but the alternative to
    detecting it is an infinite loop, and an infinite loop in an authorization
    path is worse than a refusal.
    """
    remaining = list(rules)
    emitted: list[Rule] = []

    # Precompute the relation once; it is the expensive part and the rule set
    # does not change during emission.
    precedes: dict[str, set[str]] = {rule.rule_id: set() for rule in remaining}
    for outer in remaining:
        for inner in remaining:
            if outer is inner:
                continue
            if _precedes(outer, inner):
                precedes[inner.rule_id].add(outer.rule_id)

    while remaining:
        remaining_ids = {rule.rule_id for rule in remaining}
        available = [
            rule
            for rule in remaining
            if not (precedes[rule.rule_id] & remaining_ids)
        ]
        if not available:
            raise OrderingCycle(
                "no rule is available; the specificity relation contains a "
                f"cycle among {sorted(remaining_ids)}"
            )
        chosen = min(available, key=lambda rule: rule.rule_id)
        emitted.append(chosen)
        remaining.remove(chosen)

    return tuple(emitted)


def order_rules(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """The full §12 order: bucket by priority and effect, then linearize each.

    Steps 1-3 are ordinary keys and are applied by bucketing:

        1. immutable safety invariants   evaluated before any of this (§15.1)
        2. lower numeric priority value  bucket key, ascending
        3. DENY before ALLOW             bucket key at equal priority

    Steps 4-5 are the linearization, applied **within** a bucket — §12.2.2 says
    ordering happens "at equal priority and equal effect", so specificity is
    never compared across buckets.

    The result is a function of the rule set alone. Policy file order is not
    read anywhere in this module.
    """
    buckets: dict[tuple[int, int], list[Rule]] = {}
    for rule in rules:
        buckets.setdefault(rule.sort_bucket, []).append(rule)

    ordered: list[Rule] = []
    for bucket_key in sorted(buckets):
        ordered.extend(linearize_bucket(buckets[bucket_key]))
    return tuple(ordered)


def is_total_order(ordered: Sequence[Rule]) -> bool:
    """Sanity check used by tests: every declared relation is respected.

    Not used by evaluation — a check that ran on every request would be paying
    for a property the procedure guarantees by construction. It exists so the
    guarantee can be asserted directly rather than only observed through
    behaviour.
    """
    position = {rule.rule_id: index for index, rule in enumerate(ordered)}
    for outer in ordered:
        for inner in ordered:
            if outer is inner:
                continue
            if _precedes(outer, inner) and position[outer.rule_id] > position[inner.rule_id]:
                return False
    return True


__all__ = [
    "ABSENT",
    "EXISTS",
    "IN",
    "Constraint",
    "at_least_as_specific",
    "constraints_for",
    "is_total_order",
    "linearize_bucket",
    "order_rules",
    "strictly_more_specific",
]
