"""The frozen AI-03 vocabulary.

Contract §5, transcribed and asserted. These tests exist so that reordering the
priority table, adding a truth state, or changing a kind mapping is a failure
rather than a silent behaviour change.

The most important tests here are the ones that pin what the vocabulary
**cannot** express. `COMPLETE` and `IMPLEMENTED` have no enum member, so no code
path can produce them as a state; the absence is the guarantee, and these tests
are what stop the absence from being quietly filled in later.
"""

from __future__ import annotations

import dataclasses

import pytest

from plugins.context.vocabulary import (
    FRESHNESS_SEVERITY,
    ITEM_KIND_BY_SOURCE,
    ITEM_KIND_RANK,
    SOURCE_PRIORITY,
    SOURCE_PRIORITY_ORDER,
    ContextStatus,
    Freshness,
    ItemKind,
    SourceKind,
    SourcePriority,
    SourceReadStatus,
    StatusValue,
    WorkingTreeState,
    item_kind_for,
    most_severe_freshness,
    truth_state_for_declaration,
)


pytestmark = pytest.mark.layer1

#: Transcribed from contract §5.3. Order is the priority: index 0 is P0.
FROZEN_PRIORITY: tuple[str, ...] = (
    "git_current_state",
    "master_roadmap",
    "capability_inventory",
    "design_freeze",
    "exit_report",
    "git_history",
)

#: Transcribed from contract §5.4.
FROZEN_TRUTH_STATES: tuple[str, ...] = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN")

#: Transcribed from contract §5.1.
FROZEN_ITEM_KINDS: tuple[str, ...] = ("FACT", "HISTORY", "PLAN")

#: Transcribed from contract §8.1.
FROZEN_KIND_BY_SOURCE: dict[str, str] = {
    "git_current_state": "FACT",
    "git_history": "HISTORY",
    "exit_report": "HISTORY",
    "master_roadmap": "PLAN",
    "design_freeze": "PLAN",
    "capability_inventory": "PLAN",
}


class TestSourcePriorityIsFrozen:
    def test_order_matches_the_contract(self):
        assert tuple(str(kind) for kind in SOURCE_PRIORITY_ORDER) == FROZEN_PRIORITY

    def test_rank_equals_index(self):
        for rank, kind in enumerate(SOURCE_PRIORITY_ORDER):
            assert int(SOURCE_PRIORITY[kind]) == rank, kind

    def test_enum_member_names_match_the_ranks(self):
        for rank, kind in enumerate(SOURCE_PRIORITY_ORDER):
            assert SourcePriority(rank).name == kind.name

    def test_git_current_state_outranks_everything_below_it(self):
        highest = SOURCE_PRIORITY[SourceKind.GIT_CURRENT_STATE]
        for kind in SOURCE_PRIORITY_ORDER[1:]:
            assert highest < SOURCE_PRIORITY[kind], kind

    def test_history_outranks_nothing_above_it(self):
        assert SOURCE_PRIORITY[SourceKind.GIT_HISTORY] == max(
            SOURCE_PRIORITY[kind] for kind in SOURCE_PRIORITY_ORDER
        )

    def test_cache_ranks_below_every_source_kind(self):
        """P6 exists in the table and is never an item's rank (§9.2)."""
        assert SourcePriority.CACHE > max(
            SOURCE_PRIORITY[kind] for kind in SOURCE_PRIORITY_ORDER
        )
        assert "CACHE" not in {kind.name for kind in SourceKind}

    def test_every_source_kind_has_a_priority(self):
        assert set(SOURCE_PRIORITY) == set(SourceKind)

    def test_priorities_are_unique(self):
        ranks = list(SOURCE_PRIORITY.values())
        assert len(ranks) == len(set(ranks))


class TestTruthStatesAreFrozen:
    def test_exactly_five_states(self):
        assert tuple(str(state) for state in StatusValue) == FROZEN_TRUTH_STATES

    @pytest.mark.parametrize(
        "lifecycle_word",
        [
            "COMPLETE",
            "NOT_STARTED",
            "NOT STARTED",
            "DEFERRED",
            "UNCHANGED",
            "IMPLEMENTED",
            "PLANNED",
            "DONE",
            "OK",
        ],
    )
    def test_a_lifecycle_word_is_not_a_truth_state(self, lifecycle_word):
        """§5.4: these are words, not states, and never become `PASS`."""
        assert truth_state_for_declaration(lifecycle_word) is StatusValue.UNKNOWN

    @pytest.mark.parametrize("state", FROZEN_TRUTH_STATES)
    def test_a_literal_state_survives(self, state):
        assert truth_state_for_declaration(state) is StatusValue(state)

    @pytest.mark.parametrize("state", FROZEN_TRUTH_STATES)
    def test_surrounding_whitespace_is_the_only_transformation(self, state):
        assert truth_state_for_declaration(f"  {state}  ") is StatusValue(state)

    @pytest.mark.parametrize(
        "token", ["pass", "Pass", "not_run", "not run", "NOT RUN", "Blocked"]
    )
    def test_case_and_spacing_are_not_normalised(self, token):
        """A near-miss is not the state; normalising it would be inference."""
        assert truth_state_for_declaration(token) is StatusValue.UNKNOWN

    def test_a_compound_declaration_is_not_decomposed(self):
        """D-6: `BLOCKED / DEFERRED` is not `BLOCKED`."""
        assert truth_state_for_declaration("BLOCKED / DEFERRED") is StatusValue.UNKNOWN

    def test_an_absent_declaration_is_unknown(self):
        assert truth_state_for_declaration(None) is StatusValue.UNKNOWN

    def test_an_empty_declaration_is_unknown(self):
        assert truth_state_for_declaration("") is StatusValue.UNKNOWN

    def test_pass_is_reachable_only_from_the_literal_token(self):
        """The §5.4 guarantee, stated as a property over a corpus."""
        corpus = [
            None,
            "",
            " ",
            "PASS",
            "PASSED",
            "pass",
            "COMPLETE",
            "SUCCESS",
            "OK",
            "VERIFIED",
            "TRUE",
            "NOT_RUN",
            "BLOCKED",
            "FAIL",
            "UNKNOWN",
            "PASS / COMPLETE",
        ]
        promoted = [
            token
            for token in corpus
            if truth_state_for_declaration(token) is StatusValue.PASS
            and (token is None or token.strip() != "PASS")
        ]
        assert promoted == []


class TestItemKindsAreFrozen:
    def test_exactly_three_kinds(self):
        assert tuple(str(kind) for kind in ItemKind) == FROZEN_ITEM_KINDS

    def test_kind_by_source_matches_the_contract(self):
        actual = {str(kind): str(value) for kind, value in ITEM_KIND_BY_SOURCE.items()}
        assert actual == FROZEN_KIND_BY_SOURCE

    def test_every_source_kind_has_a_kind(self):
        assert set(ITEM_KIND_BY_SOURCE) == set(SourceKind)

    def test_the_kind_helper_is_the_table(self):
        for kind in SourceKind:
            assert item_kind_for(kind) is ITEM_KIND_BY_SOURCE[kind]

    def test_load_bearing_indirection_is_frozen(self):
        """The three findings that must not be reclassified."""
        assert item_kind_for(SourceKind.GIT_CURRENT_STATE) is ItemKind.FACT
        assert item_kind_for(SourceKind.GIT_HISTORY) is ItemKind.HISTORY
        assert item_kind_for(SourceKind.MASTER_ROADMAP) is ItemKind.PLAN

    def test_ambiguous_sources_default_to_plan(self):
        """D-2: the fail-safe direction for a declarative document."""
        for kind in (
            SourceKind.MASTER_ROADMAP,
            SourceKind.CAPABILITY_INVENTORY,
            SourceKind.DESIGN_FREEZE,
        ):
            assert item_kind_for(kind) is ItemKind.PLAN, kind

    def test_evidence_rank_beats_plan_rank(self):
        """§11.2: the epistemic class orders before source priority."""
        assert ITEM_KIND_RANK[ItemKind.FACT] < ITEM_KIND_RANK[ItemKind.HISTORY]
        assert ITEM_KIND_RANK[ItemKind.HISTORY] < ITEM_KIND_RANK[ItemKind.PLAN]

    def test_the_highest_priority_plan_still_ranks_behind_history(self):
        """D-8, stated directly: P1 roadmap loses to P4 exit report on a subject."""
        roadmap = ITEM_KIND_RANK[item_kind_for(SourceKind.MASTER_ROADMAP)]
        exit_report = ITEM_KIND_RANK[item_kind_for(SourceKind.EXIT_REPORT)]
        assert exit_report < roadmap


class TestNoKindPromotionExists:
    """No function converts one kind into another, so the promotion cannot happen."""

    @pytest.mark.parametrize("kind", list(ItemKind))
    def test_no_conversion_helper_is_exported(self, kind):
        import plugins.context as package

        forbidden = {
            f"promote_{kind.value.lower()}",
            f"as_{kind.value.lower()}",
            f"to_{kind.value.lower()}",
            f"upgrade_{kind.value.lower()}",
        }
        assert forbidden & set(dir(package)) == set()

    def test_no_module_defines_a_promotion_function(self):
        import plugins.context.classification as classification
        import plugins.context.resolution as resolution
        import plugins.context.vocabulary as vocabulary

        for module in (vocabulary, classification, resolution):
            names = set(dir(module))
            assert not {n for n in names if n.startswith("promote_")}, module.__name__

    def test_lifecycle_words_are_absent_from_every_state_enum(self):
        forbidden = {"COMPLETE", "IMPLEMENTED", "DONE", "PLANNED", "VERIFIED"}
        for enum in (StatusValue, ItemKind, Freshness, ContextStatus, SourceReadStatus):
            assert forbidden & {member.value for member in enum} == set(), enum


class TestFreshnessIsFrozen:
    def test_three_values(self):
        assert {str(value) for value in Freshness} == {"CURRENT", "STALE", "UNKNOWN"}

    def test_severity_is_ordered_current_stale_unknown(self):
        assert (
            FRESHNESS_SEVERITY[Freshness.CURRENT]
            < FRESHNESS_SEVERITY[Freshness.STALE]
            < FRESHNESS_SEVERITY[Freshness.UNKNOWN]
        )

    def test_summary_takes_the_most_severe(self):
        assert most_severe_freshness([Freshness.CURRENT]) is Freshness.CURRENT
        assert (
            most_severe_freshness([Freshness.CURRENT, Freshness.STALE])
            is Freshness.STALE
        )
        assert (
            most_severe_freshness([Freshness.STALE, Freshness.UNKNOWN])
            is Freshness.UNKNOWN
        )

    def test_one_unknown_makes_the_whole_summary_unknown(self):
        values = [Freshness.CURRENT] * 99 + [Freshness.UNKNOWN]
        assert most_severe_freshness(values) is Freshness.UNKNOWN

    def test_nothing_read_is_current_not_unknown(self):
        """An empty build has nothing stale; it is not thereby suspect."""
        assert most_severe_freshness([]) is Freshness.CURRENT


class TestOtherEnumsAreFrozen:
    def test_read_statuses(self):
        assert {str(v) for v in SourceReadStatus} == {
            "READ",
            "MISSING",
            "UNREADABLE",
            "REFUSED",
            "BLOCKED",
        }

    def test_context_statuses(self):
        assert {str(v) for v in ContextStatus} == {"FULL", "PARTIAL", "UNKNOWN"}

    def test_context_status_avoids_the_lifecycle_vocabulary(self):
        """Amendment 1: `COMPLETE` describes a plan's progress, not a build's.

        Two different questions sharing one word is how a plan's `COMPLETE`
        ends up in a build's status field.
        """
        assert "COMPLETE" not in {member.value for member in ContextStatus}

    def test_working_tree_states(self):
        assert {str(v) for v in WorkingTreeState} == {"CLEAN", "DIRTY", "UNKNOWN"}

    def test_unknown_is_a_working_tree_state(self):
        """§6.1: an unreadable tree is `UNKNOWN`, and `UNKNOWN` is not `CLEAN`."""
        assert WorkingTreeState.UNKNOWN in set(WorkingTreeState)
        assert WorkingTreeState.UNKNOWN is not WorkingTreeState.CLEAN


class TestFrozenTypes:
    @pytest.mark.parametrize(
        "kind_value",
        [SourceKind.GIT_CURRENT_STATE, SourceKind.MASTER_ROADMAP, SourceKind.EXIT_REPORT],
    )
    def test_source_kind_is_immutable(self, kind_value):
        with pytest.raises((AttributeError, TypeError)):
            kind_value.value = "changed"  # type: ignore[misc]

    def test_context_item_has_no_confidence_field(self):
        """§15 of the brief: `status`, not `model_confidence`."""
        from plugins.context.classification import ContextItem

        names = {field.name for field in dataclasses.fields(ContextItem)}
        for forbidden in ("confidence", "score", "weight", "rank", "probability"):
            assert forbidden not in names
