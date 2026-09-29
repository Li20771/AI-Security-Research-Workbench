"""FACT / HISTORY / PLAN separation, and state preservation.

The brief's T3, T5, T6, T7 and T8, exercised through the whole pipeline rather
than against the classifier alone: a guarantee that holds only at the unit
level is a guarantee that a caller can lose.

Every test here drives a real `build_context` over a throwaway workspace, so
what is asserted is what a consumer would actually receive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.context.context import build_context
from plugins.context.sources import (
    DocumentSource,
    GitCurrentStateSource,
    GitHistorySource,
)
from plugins.context.vocabulary import (
    ITEM_KIND_BY_SOURCE,
    ItemKind,
    SourceKind,
    StatusValue,
)
from tests.context.conftest import (
    OTHER_SHA,
    SAMPLE_SHA,
    declaration_document,
    document_manifest,
    git_log_lines,
    write_document,
)


pytestmark = pytest.mark.layer2

PLAN_SOURCE_KINDS = frozenset(
    kind for kind, item_kind in ITEM_KIND_BY_SOURCE.items() if item_kind is ItemKind.PLAN
)


def full_manifest(root: Path, reader) -> tuple:
    """One source of every kind, over a throwaway workspace."""
    write_document(
        root,
        "docs/roadmap.md",
        declaration_document(("AI-04", "NOT_STARTED")),
    )
    write_document(
        root,
        "docs/report.md",
        declaration_document(("Live provider execution", "NOT_RUN")),
    )
    return (
        GitCurrentStateSource(reader),
        DocumentSource(SourceKind.MASTER_ROADMAP, "docs/roadmap.md"),
        DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),
        GitHistorySource(reader),
    )


@pytest.fixture
def three_kind_context(tmp_path: Path, fake_git):
    root = tmp_path / "ws"
    root.mkdir()
    fake_git.log = git_log_lines([("a" * 40, "2026-09-29T10:00:00+00:00", "earlier work")])
    return build_context(root, manifest=full_manifest(root, fake_git), reader=fake_git)


class TestT3FactHistoryPlanSeparation:
    def test_all_three_kinds_are_present(self, three_kind_context):
        assert three_kind_context.facts
        assert three_kind_context.history
        assert three_kind_context.plans

    def test_facts_holds_only_fact_items(self, three_kind_context):
        for item in three_kind_context.facts:
            assert item.item_kind is ItemKind.FACT, item.subject

    def test_history_holds_only_history_items(self, three_kind_context):
        for item in three_kind_context.history:
            assert item.item_kind is ItemKind.HISTORY, item.subject

    def test_plans_holds_only_plan_items(self, three_kind_context):
        for item in three_kind_context.plans:
            assert item.item_kind is ItemKind.PLAN, item.subject

    def test_every_item_kind_matches_its_source(self, three_kind_context):
        for item in three_kind_context.items:
            assert item.item_kind is ITEM_KIND_BY_SOURCE[item.source_kind], item.subject

    def test_the_three_lists_partition_the_items(self, three_kind_context):
        total = len(three_kind_context.facts) + len(three_kind_context.history)
        total += len(three_kind_context.plans)
        assert total == len(three_kind_context.items)

    def test_no_item_appears_twice(self, three_kind_context):
        keys = [
            (item.subject, item.source_kind, item.source_revision)
            for item in three_kind_context.items
        ]
        assert len(keys) == len(set(keys))

    def test_git_state_is_a_fact_and_git_history_is_history(self, three_kind_context):
        for item in three_kind_context.facts:
            assert item.source_kind is SourceKind.GIT_CURRENT_STATE
        assert any(
            item.source_kind is SourceKind.GIT_HISTORY
            for item in three_kind_context.history
        )

    def test_kind_of_an_item_is_immutable(self, three_kind_context):
        item = three_kind_context.facts[0]
        with pytest.raises((AttributeError, TypeError)):
            item.item_kind = ItemKind.PLAN  # type: ignore[misc]


class TestT5PlanCannotBecomeFact:
    def test_a_planned_phase_stays_a_plan(self, three_kind_context):
        planned = [i for i in three_kind_context.plans if i.subject == "declared.ai_04"]
        assert len(planned) == 1
        assert planned[0].declared_state == "NOT_STARTED"

    def test_a_planned_phase_never_reaches_facts(self, three_kind_context):
        subjects = {item.subject for item in three_kind_context.facts}
        assert "declared.ai_04" not in subjects

    def test_no_plan_source_contributes_to_facts(self, three_kind_context):
        for item in three_kind_context.facts:
            assert item.source_kind not in PLAN_SOURCE_KINDS, item.subject

    def test_a_planned_phase_is_not_a_pass(self, three_kind_context):
        planned = [i for i in three_kind_context.plans if i.subject == "declared.ai_04"]
        assert planned[0].truth_state is not StatusValue.PASS
        assert planned[0].truth_state is StatusValue.UNKNOWN

    def test_no_lifecycle_word_becomes_a_truth_state(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/roadmap.md",
            declaration_document(
                ("AI-04", "NOT_STARTED"),
                ("AI-05", "PLANNED"),
                ("AI-06", "DEFERRED"),
                ("AI-07", "DEFERRED"),
            ),
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.MASTER_ROADMAP, "docs/roadmap.md"),),
            reader=fake_git,
        )
        assert response.plans
        for item in response.plans:
            assert item.truth_state is StatusValue.UNKNOWN, item.subject
            assert item.declared_state is not None

    def test_a_plan_source_cannot_outrank_evidence_for_facts(
        self, three_kind_context
    ):
        """Whatever the ranking does, `facts` is built from a partition, not a filter."""
        for item in three_kind_context.facts:
            assert item.item_kind is ItemKind.FACT


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        ("UNKNOWN", StatusValue.UNKNOWN),
        ("NOT_RUN", StatusValue.NOT_RUN),
        ("BLOCKED", StatusValue.BLOCKED),
        ("PASS", StatusValue.PASS),
        ("FAIL", StatusValue.FAIL),
    ],
)
class TestT6T7T8StatePreservation:
    """A declared state survives the pipeline unchanged, in both axes."""

    def test_declared_state_is_preserved_verbatim(
        self, tmp_path: Path, fake_git, declared, expected
    ):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root, "docs/report.md", declaration_document(("Gate", declared))
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),),
            reader=fake_git,
        )
        item = response.history[0]
        assert item.declared_state == declared
        assert item.truth_state is expected

    def test_a_lowercase_spelling_is_not_upgraded(
        self, tmp_path: Path, fake_git, declared, expected
    ):
        """A near-miss is not the state, at any stage of the pipeline."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root, "docs/report.md", declaration_document(("Gate", declared.lower()))
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),),
            reader=fake_git,
        )
        for item in response.items:
            assert item.truth_state is StatusValue.UNKNOWN, item.subject


class TestCompoundAndLifecycleDeclarations:
    def test_a_compound_value_is_preserved_whole(self, tmp_path: Path, fake_git):
        """D-6, at the pipeline level: `BLOCKED / DEFERRED` is not `BLOCKED`."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/status.md",
            declaration_document(("Clean-room reinstall", "BLOCKED / DEFERRED")),
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),),
            reader=fake_git,
        )
        item = response.plans[0]
        assert item.declared_state == "BLOCKED / DEFERRED"
        assert item.truth_state is StatusValue.UNKNOWN

    def test_a_lifecycle_word_is_preserved_and_not_laundered(
        self, tmp_path: Path, fake_git
    ):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/status.md",
            declaration_document(
                ("AI-02 overall", "COMPLETE"),
                ("SecurityLab", "UNCHANGED"),
            ),
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),),
            reader=fake_git,
        )
        for item in response.plans:
            assert item.truth_state is StatusValue.UNKNOWN, item.subject

    def test_no_item_is_pass_without_a_literal_pass_declaration(
        self, tmp_path: Path, fake_git
    ):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/status.md",
            declaration_document(
                ("AI-02 overall", "COMPLETE"),
                ("Offline CI", "PASS"),
                ("Clean-room reinstall", "BLOCKED / DEFERRED"),
            ),
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),),
            reader=fake_git,
        )
        for item in response.items:
            if item.truth_state is StatusValue.PASS:
                assert item.declared_state == "PASS", item.subject


class TestItemsCarryProvenance:
    def test_every_item_names_its_workspace_source_and_revision(
        self, three_kind_context
    ):
        for item in three_kind_context.items:
            assert item.workspace_id == three_kind_context.workspace.workspace_id
            assert item.source_identity
            assert item.source_kind in SourceKind
            assert item.retrieved_at.endswith("Z")

    def test_a_git_item_carries_no_declared_state(self, three_kind_context):
        for item in three_kind_context.facts:
            assert item.declared_state is None
            assert item.truth_state is StatusValue.UNKNOWN

    def test_a_document_item_carries_the_revision_it_was_read_at(
        self, three_kind_context
    ):
        for item in three_kind_context.plans:
            assert item.source_revision is not None
            assert len(item.source_revision) == 64  # sha-256 hex digest

    def test_raw_items_reject_a_non_string_value(self):
        from plugins.context.classification import RawItem
        from plugins.context.errors import ContextError

        with pytest.raises(ContextError):
            RawItem(subject="a", value=1)  # type: ignore[arg-type]

    def test_raw_items_reject_an_empty_subject(self):
        from plugins.context.classification import RawItem
        from plugins.context.errors import ContextError

        with pytest.raises(ContextError):
            RawItem(subject="", value="x")


class TestContextStatus:
    def test_every_source_read_is_full(self, three_kind_context):
        from plugins.context.vocabulary import ContextStatus

        assert three_kind_context.status is ContextStatus.FULL

    def test_a_missing_source_makes_the_build_partial(self, tmp_path: Path, fake_git):
        from plugins.context.vocabulary import ContextStatus

        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, "docs/report.md", declaration_document(("A", "PASS")))
        response = build_context(
            root,
            manifest=(
                DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),
                DocumentSource(SourceKind.MASTER_ROADMAP, "docs/absent.md"),
            ),
            reader=fake_git,
        )
        assert response.status is ContextStatus.PARTIAL

    def test_nothing_read_is_unknown_not_empty_success(self, tmp_path: Path, fake_git):
        from plugins.context.vocabulary import ContextStatus

        root = tmp_path / "ws"
        root.mkdir()
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.MASTER_ROADMAP, "docs/absent.md"),),
            reader=fake_git,
        )
        assert response.status is ContextStatus.UNKNOWN
        assert response.items == ()
