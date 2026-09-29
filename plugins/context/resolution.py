"""Deterministic conflict resolution.

Implements AI-03 contract §11. Two items conflict when they share a `subject`
and come from different sources; resolution picks one authoritative item and
**retains every loser**, marked with the winner's reference.

Nothing is ever deleted by conflict resolution. Deleting the loser would
destroy exactly the disagreement that makes the context auditable, and it would
make the plugin's output depend on which source happened to be read first.

### The ordering

```text
1. epistemic class   FACT  <  HISTORY  <  PLAN     (§16 of the brief: evidence wins)
2. source priority   P0 < P1 < ... < P5            (§5.3, frozen)
3. source identity   ascending                     (determinism)
4. source revision   ascending                     (determinism)
5. value             ascending                     (determinism)
```

Steps 1 and 2 are the interesting ones, and they are two axes rather than one
because the AI-03 brief's §6 and §16 would otherwise contradict each other
(D-8). §6 freezes a single source priority in which the Master Roadmap (P1)
outranks exit reports (P4); §16 requires that evidence state wins and that a
plan stays a plan. Applied as one ordering, those two would let the roadmap
override an exit report about the same subject. They are therefore applied in
sequence: the frozen priority orders sources **within** an epistemic class, and
the epistemic class decides **across** them.

Step 5 exists because a single document can declare two different values for
one subject. That disagreement is real, so both items are kept and the
tiebreak keeps the winner stable across runs rather than dependent on file
order.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass

from plugins.context.classification import ContextItem, ItemRef
from plugins.context.vocabulary import (
    ITEM_KIND_RANK,
    StatusValue,
)


@dataclass(frozen=True, slots=True)
class SubjectResolution:
    """The recorded outcome for one contested subject (contract §11.4).

    Attributes:
        subject: the subject every listed item is about.
        authoritative: the winning item's reference, by the §11.2 ordering.
        evidenced: the highest-ranked item that carries a recognised §5.4
            truth state, or `None` when no item for this subject does. This is
            the field that makes "evidence wins over plan" observable: a PLAN
            item can be authoritative without ever being evidenced.
        superseded: every other item's reference, in ordering order.
    """

    subject: str
    authoritative: ItemRef | None
    evidenced: ItemRef | None
    superseded: tuple[ItemRef, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "authoritative": (
                self.authoritative.render() if self.authoritative is not None else None
            ),
            "evidenced": (
                self.evidenced.render() if self.evidenced is not None else None
            ),
            "superseded": [ref.render() for ref in self.superseded],
        }


def ordering_key(item: ContextItem) -> tuple[object, ...]:
    """The §11.2 ordering key. Total, so resolution never depends on input order."""
    return (
        ITEM_KIND_RANK[item.item_kind],
        item.priority,
        item.source_identity,
        item.source_revision or "",
        item.value,
    )


def sort_items(items: tuple[ContextItem, ...]) -> tuple[ContextItem, ...]:
    """Deterministic item order: by subject, then by the §11.2 ordering."""
    return tuple(sorted(items, key=lambda item: (item.subject, ordering_key(item))))


def resolve_subject(items: tuple[ContextItem, ...]) -> SubjectResolution:
    """Resolve one subject's items. `items` must be non-empty and share a subject."""
    if not items:
        raise ValueError("a resolution needs at least one item")
    subject = items[0].subject
    if any(item.subject != subject for item in items):
        raise ValueError("a resolution describes exactly one subject")

    ordered = sorted(items, key=ordering_key)
    evidenced = [item for item in ordered if item.truth_state is not StatusValue.UNKNOWN]

    return SubjectResolution(
        subject=subject,
        authoritative=ordered[0].ref,
        evidenced=evidenced[0].ref if evidenced else None,
        superseded=tuple(item.ref for item in ordered[1:]),
    )


def contested_subjects(
    items: tuple[ContextItem, ...],
) -> dict[str, tuple[ContextItem, ...]]:
    """Subjects claimed by more than one item, keyed by subject."""
    grouped: dict[str, list[ContextItem]] = defaultdict(list)
    for item in items:
        grouped[item.subject].append(item)
    return {subject: tuple(group) for subject, group in grouped.items() if len(group) > 1}


def resolve_conflicts(
    items: tuple[ContextItem, ...],
) -> tuple[SubjectResolution, ...]:
    """Every contested subject, resolved and ordered by subject."""
    contested = contested_subjects(items)
    return tuple(
        resolve_subject(contested[subject]) for subject in sorted(contested)
    )


def apply_resolution(items: tuple[ContextItem, ...]) -> tuple[ContextItem, ...]:
    """Mark every losing item with the winner's reference (§11.1).

    A winning item keeps `superseded_by: None`. The function is idempotent, so
    a caller that applied it once and a caller that applied it twice get the
    same items.
    """
    contested = contested_subjects(items)
    winners: dict[str, ItemRef] = {
        subject: resolve_subject(group).authoritative  # type: ignore[assignment]
        for subject, group in contested.items()
    }

    resolved: list[ContextItem] = []
    for item in items:
        winner = winners.get(item.subject)
        if winner is None or winner == item.ref:
            resolved.append(dataclasses.replace(item, superseded_by=None))
        else:
            resolved.append(dataclasses.replace(item, superseded_by=winner))
    return tuple(resolved)


__all__ = [
    "SubjectResolution",
    "apply_resolution",
    "contested_subjects",
    "ordering_key",
    "resolve_conflicts",
    "resolve_subject",
    "sort_items",
]
