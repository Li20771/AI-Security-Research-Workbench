"""The frozen AI-03 context vocabulary.

Implements AI-03 contract §5, frozen in
`docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md`. Every table here is transcribed
from that document and asserted against it by the layer-1 tests, so reordering
a priority or adding a state is a test failure rather than a silent behaviour
change.

Three rules dominate this module.

**Kinds are assigned, never promoted.** FACT, HISTORY and PLAN describe what an
item asserts about time. There is no function here -- or anywhere in this
package -- that converts one into another. `PLAN -> IMPLEMENTED`,
`PLAN -> COMPLETE` and `PLAN -> PASS` are not forbidden by a check; they are
unrepresentable, because `IMPLEMENTED` and `COMPLETE` are not members of any
enum in this module.

**Declared is not true.** `truth_state_for_declaration` is the only bridge from
what a source wrote to the §5.4 truth model, and it is a literal membership
test: the token must *be* one of the five. Everything else -- `COMPLETE`,
`NOT STARTED`, `DEFERRED`, `BLOCKED / DEFERRED` -- keeps its text in
`declared_state` and has truth state `UNKNOWN`. A compound declaration is never
decomposed into its parts, because choosing one would be inference.

**Absent is not false.** A source that declared nothing is `UNKNOWN`, never a
default value.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Mapping


class ItemKind(StrEnum):
    """What an item asserts about time (contract §5.1). Frozen.

    The three are not interchangeable, and nothing converts between them:

        FACT      something about the present state of this workspace
        HISTORY   something that has already happened
        PLAN      something intended, frozen, or declared but not executed
    """

    FACT = "FACT"
    HISTORY = "HISTORY"
    PLAN = "PLAN"


class SourceKind(StrEnum):
    """The six context sources (contract §5.2). Exactly six.

    A seventh is a contract amendment, not a configuration change.
    """

    GIT_CURRENT_STATE = "git_current_state"
    MASTER_ROADMAP = "master_roadmap"
    CAPABILITY_INVENTORY = "capability_inventory"
    DESIGN_FREEZE = "design_freeze"
    EXIT_REPORT = "exit_report"
    GIT_HISTORY = "git_history"


class SourcePriority(IntEnum):
    """Frozen source priority (contract §5.3). Lower rank = higher precedence.

    Transcribed from AI-00 §11. `CACHE` is a member because the priority table
    has seven rows, but it is **not** a source kind: a cache entry is never an
    item's source (§9.2), so no item ever carries this rank.
    """

    GIT_CURRENT_STATE = 0
    MASTER_ROADMAP = 1
    CAPABILITY_INVENTORY = 2
    DESIGN_FREEZE = 3
    EXIT_REPORT = 4
    GIT_HISTORY = 5
    CACHE = 6


#: The frozen priority table, in precedence order. The tuple's index *is* the
#: rank, so this is both the mapping and its own proof of ordering.
SOURCE_PRIORITY_ORDER: tuple[SourceKind, ...] = (
    SourceKind.GIT_CURRENT_STATE,
    SourceKind.MASTER_ROADMAP,
    SourceKind.CAPABILITY_INVENTORY,
    SourceKind.DESIGN_FREEZE,
    SourceKind.EXIT_REPORT,
    SourceKind.GIT_HISTORY,
)

SOURCE_PRIORITY: Mapping[SourceKind, SourcePriority] = {
    SourceKind.GIT_CURRENT_STATE: SourcePriority.GIT_CURRENT_STATE,
    SourceKind.MASTER_ROADMAP: SourcePriority.MASTER_ROADMAP,
    SourceKind.CAPABILITY_INVENTORY: SourcePriority.CAPABILITY_INVENTORY,
    SourceKind.DESIGN_FREEZE: SourcePriority.DESIGN_FREEZE,
    SourceKind.EXIT_REPORT: SourcePriority.EXIT_REPORT,
    SourceKind.GIT_HISTORY: SourcePriority.GIT_HISTORY,
}


class StatusValue(StrEnum):
    """The frozen truth model (contract §5.4), from AI-00 §10. Exactly five.

    `COMPLETE`, `NOT STARTED`, `DEFERRED`, `UNCHANGED` and every other
    lifecycle word are **not** truth states. They survive verbatim in
    `declared_state` and their truth state is `UNKNOWN` -- never `PASS`.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"


class Freshness(StrEnum):
    """How current an item's revision is (contract §5.5, §10)."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


#: Severity order for the §10.3 summary. Higher = more severe, so the overall
#: value is the maximum and a response holding one unestablished item never
#: reports itself as wholly current.
FRESHNESS_SEVERITY: Mapping[Freshness, int] = {
    Freshness.CURRENT: 0,
    Freshness.STALE: 1,
    Freshness.UNKNOWN: 2,
}


class SourceReadStatus(StrEnum):
    """The outcome of reading a source (contract §5.7).

    A different question from what the source declared. A source that was not
    read is never reported as read with an empty payload: `MISSING` is not an
    empty document, and it is not a `PASS`.
    """

    READ = "READ"
    MISSING = "MISSING"
    UNREADABLE = "UNREADABLE"
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"


class ContextStatus(StrEnum):
    """Whether the build could read what it declared (contract §5.8).

    Deliberately **not** `COMPLETE`. This enum answers a question about the
    build ("did every declared source get read?"), and `COMPLETE` is a
    lifecycle word that AI-02's closeout names as the thing a plan must never be
    promoted to. Two different questions sharing one word is how a plan's
    `COMPLETE` ends up in a build's status field. `FULL` cannot be confused for
    either.
    """

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class WorkingTreeState(StrEnum):
    """Working tree state (contract §6.1).

    `UNKNOWN` is never `CLEAN`: an unreadable working tree is not a clean one.
    """

    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    UNKNOWN = "UNKNOWN"


#: Kind by source class (contract §8.1). Reviewed policy, not inference.
#:
#: Where a class is genuinely ambiguous the entry is `PLAN`, the fail-safe
#: direction (D-2, §8.2): classifying a plan as a plan costs nothing, while
#: classifying a plan or a history as a fact presents something that is not
#: current as current.
ITEM_KIND_BY_SOURCE: Mapping[SourceKind, ItemKind] = {
    SourceKind.GIT_CURRENT_STATE: ItemKind.FACT,
    SourceKind.GIT_HISTORY: ItemKind.HISTORY,
    SourceKind.EXIT_REPORT: ItemKind.HISTORY,
    SourceKind.MASTER_ROADMAP: ItemKind.PLAN,
    SourceKind.DESIGN_FREEZE: ItemKind.PLAN,
    SourceKind.CAPABILITY_INVENTORY: ItemKind.PLAN,
}


#: Conflict-resolution class rank (contract §11.2, D-8). Applied *before*
#: source priority, because a plan is not evidence and must not outrank an
#: execution record however the priority table ranks their sources.
ITEM_KIND_RANK: Mapping[ItemKind, int] = {
    ItemKind.FACT: 0,
    ItemKind.HISTORY: 1,
    ItemKind.PLAN: 2,
}


def truth_state_for_declaration(declared: str | None) -> StatusValue:
    """Translate a declared token into the frozen truth model (§5.6).

    The **only** conversion in the package, and it is a literal membership
    test. The token must be one of the five §5.4 values after stripping
    surrounding whitespace; anything else is `UNKNOWN`, with the original text
    preserved on the item's `declared_state`.

    There is deliberately no mapping table. A table would be a list of
    judgement calls -- is `COMPLETE` close enough to `PASS`? is `BLOCKED /
    DEFERRED` mostly `BLOCKED`? -- and every one of them answers "yes" to
    laundering a claim into evidence. The absence of the table is the
    guarantee.
    """
    if declared is None:
        return StatusValue.UNKNOWN
    try:
        return StatusValue(declared.strip())
    except ValueError:
        return StatusValue.UNKNOWN


def source_priority(kind: SourceKind) -> SourcePriority:
    return SOURCE_PRIORITY[kind]


def item_kind_for(kind: SourceKind) -> ItemKind:
    return ITEM_KIND_BY_SOURCE[kind]


def most_severe_freshness(values: object) -> Freshness:
    """The §10.3 summary value: the most severe freshness present.

    An empty collection has no items to be stale, so it is `CURRENT`.
    """
    freshest = Freshness.CURRENT
    for value in values:  # type: ignore[union-attr]
        if FRESHNESS_SEVERITY[value] > FRESHNESS_SEVERITY[freshest]:
            freshest = value
    return freshest


__all__ = [
    "ContextStatus",
    "FRESHNESS_SEVERITY",
    "Freshness",
    "ITEM_KIND_BY_SOURCE",
    "ITEM_KIND_RANK",
    "ItemKind",
    "SOURCE_PRIORITY",
    "SOURCE_PRIORITY_ORDER",
    "SourceKind",
    "SourcePriority",
    "SourceReadStatus",
    "StatusValue",
    "WorkingTreeState",
    "item_kind_for",
    "most_severe_freshness",
    "source_priority",
    "truth_state_for_declaration",
]
