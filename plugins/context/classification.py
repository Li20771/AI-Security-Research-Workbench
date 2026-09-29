"""Semantic classification — FACT / HISTORY / PLAN.

Implements AI-03 contract §8. This is A3 of the phase plan: turning what a
source *read* into what a source *claims*, with a kind attached to the claim.

The whole conversion is two steps and neither consults content meaning:

    RawItem   subject, value, an optional declared token
    classify  kind := ITEM_KIND_BY_SOURCE[source], truth := literal match on the token

There is no model here, no confidence score, and no prose analysis. Kind comes
from the source class, which is reviewed policy; truth state comes from a
literal vocabulary match. A classifier that read the text to decide what a line
"really meant" would be exactly the component the AI-03 brief forbids (its §11),
and it would also be untestable, because two runs on the same text could
disagree.

`classify` is the only producer of a `ContextItem`, and it writes `item_kind`
once. The field is frozen, and no function in this package accepts an item and
returns an item of another kind.
"""

from __future__ import annotations

from dataclasses import dataclass

from plugins.context.errors import ContextError
from plugins.context.vocabulary import (
    Freshness,
    ItemKind,
    SourceKind,
    StatusValue,
    item_kind_for,
    source_priority,
    truth_state_for_declaration,
)


@dataclass(frozen=True, slots=True)
class RawItem:
    """One claim read from a source, before any classification.

    Attributes:
        subject: what the claim is about (§8.3). Stable and comparable across
            sources, which is what makes a conflict detectable at all.
        value: the claim, as text.
        declared_state: the token the source wrote, verbatim, or `None` when
            the source declared no state. Never transformed, never inferred.
    """

    subject: str
    value: str
    declared_state: str | None = None

    def __post_init__(self) -> None:
        if not self.subject:
            raise ContextError("raw item subject must not be empty")
        if not isinstance(self.value, str):
            raise ContextError(
                f"raw item value must be a string; got {type(self.value).__name__}. "
                "A non-string value has no verbatim form to preserve."
            )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "subject": self.subject,
            "value": self.value,
            "declared_state": self.declared_state,
        }


@dataclass(frozen=True, slots=True, order=True)
class ItemRef:
    """A reference that identifies **one item**, not merely one read.

    The `value` field is load-bearing and was added by Amendment 3. Without it
    this was `(kind, identity, revision)`, which does not distinguish the two
    halves of a self-contradicting document: §7.3 keeps both `Gate = PASS` and
    `Gate = FAIL` from a single read, so both items carried the *same* ref.
    Conflict resolution compares refs to decide who lost, so it concluded that
    each item was the winner and marked neither — the loser kept
    `superseded_by: None` and the contradiction became invisible in exactly the
    case the field exists to expose.

    A ref that cannot tell two items apart is not a reference to an item.
    """

    source_kind: SourceKind
    source_identity: str
    source_revision: str
    value: str

    def render(self) -> str:
        return (
            f"{self.source_kind}:{self.source_identity}"
            f"@{self.source_revision} = {self.value}"
        )


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One classified context item (contract §15 of the AI-03 brief).

    Attributes:
        workspace_id: the workspace this was read under (§6). Never another's.
        item_kind: FACT, HISTORY or PLAN. Assigned once, never promoted.
        subject: what the item is about (§8.3).
        value: the claim, as text.
        source_kind: which §5.2 source produced it.
        source_identity: which thing within the workspace was read.
        source_revision: the revision read, or `None` when none was established.
        retrieved_at: ISO-8601 UTC timestamp of the read.
        freshness: CURRENT, STALE or UNKNOWN (§10).
        declared_state: the token the source wrote, verbatim, or `None`.
        truth_state: the §5.4 state, and only when `declared_state` is
            literally one of the five. `COMPLETE` yields `UNKNOWN`.
        cache_hit: whether the payload came from a confirmed-revision cache
            entry. Auditable, and never a source of truth (§9.2).
        superseded_by: the winning item's reference when this one lost a
            conflict, else `None`. A superseded item is retained, never
            deleted (§11.1).
    """

    workspace_id: str
    item_kind: ItemKind
    subject: str
    value: str
    source_kind: SourceKind
    source_identity: str
    source_revision: str | None
    retrieved_at: str
    freshness: Freshness
    declared_state: str | None
    truth_state: StatusValue
    cache_hit: bool
    superseded_by: ItemRef | None = None

    @property
    def priority(self) -> int:
        return int(source_priority(self.source_kind))

    @property
    def ref(self) -> ItemRef:
        """A reference that identifies this item among all others.

        Includes `value`, so the two halves of a self-contradicting document
        are distinct items rather than two names for one (Amendment 3).
        """
        return ItemRef(
            source_kind=self.source_kind,
            source_identity=self.source_identity,
            source_revision=self.source_revision or "",
            value=self.value,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "item_kind": str(self.item_kind),
            "subject": self.subject,
            "value": self.value,
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
            "retrieved_at": self.retrieved_at,
            "freshness": str(self.freshness),
            "declared_state": self.declared_state,
            "truth_state": str(self.truth_state),
            "cache_hit": self.cache_hit,
            "superseded_by": (
                self.superseded_by.render() if self.superseded_by is not None else None
            ),
        }


def classify(
    raw: RawItem,
    *,
    source_kind: SourceKind,
    source_identity: str,
    source_revision: str | None,
    retrieved_at: str,
    workspace_id: str,
    freshness: Freshness,
    cache_hit: bool = False,
) -> ContextItem:
    """Attach kind, truth state and provenance to one raw claim.

    The two conversions that happen here are the only two in the package:

        source_kind   -> item_kind    a frozen lookup (§8.1)
        declared token -> truth_state a literal vocabulary match (§5.6)

    Neither reads `value`. A claim's text cannot influence its own
    classification.
    """
    if not workspace_id:
        raise ContextError("classification requires a workspace id")
    if not source_identity:
        raise ContextError("classification requires a source identity")

    return ContextItem(
        workspace_id=workspace_id,
        item_kind=item_kind_for(source_kind),
        subject=raw.subject,
        value=raw.value,
        source_kind=source_kind,
        source_identity=source_identity,
        source_revision=source_revision,
        retrieved_at=retrieved_at,
        freshness=freshness,
        declared_state=raw.declared_state,
        truth_state=truth_state_for_declaration(raw.declared_state),
        cache_hit=cache_hit,
    )


__all__ = ["ContextItem", "ItemRef", "RawItem", "classify"]
