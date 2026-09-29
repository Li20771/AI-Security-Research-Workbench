"""Deterministic conflict resolution.

The brief's T4 and T11.

The cases are chosen to be adversarial rather than convenient. T4 uses a
historical report whose declaration is routed onto the *same subject* as live
git state through the frozen alias table, so the conflict is real and not
manufactured by a naming coincidence. T11 pits the two orderings against each
other: the frozen priority table says P1 outranks P4, and the evidence rule
says a plan does not outrank evidence. A resolution that satisfied only one of
them would pass a weaker test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.context.classification import ContextItem, ItemRef, RawItem, classify
from plugins.context.context import build_context
from plugins.context.resolution import (
    apply_resolution,
    contested_subjects,
    ordering_key,
    resolve_conflicts,
    resolve_subject,
)
from plugins.context.sources import (
    DocumentSource,
    GitCurrentStateSource,
    GitHistorySource,
)
from plugins.context.vocabulary import (
    Freshness,
    ItemKind,
    SourceKind,
    StatusValue,
)
from tests.context.conftest import (
    OTHER_SHA,
    SAMPLE_SHA,
    declaration_document,
    write_document,
)


pytestmark = pytest.mark.layer2

#: Upper-case hex, because the §7.3 value grammar records state-shaped
#: uppercase tokens. A lower-case sha in a document is prose the extractor
#: correctly declines to read, which is why this fixture is upper-case.
OLD_SHA_UPPER = "A" * 40


def item(
    *,
    subject: str,
    value: str,
    source_kind: SourceKind,
    identity: str = "src",
    revision: str = "rev",
    declared: str | None = None,
) -> ContextItem:
    return classify(
        RawItem(subject=subject, value=value, declared_state=declared),
        source_kind=source_kind,
        source_identity=identity,
        source_revision=revision,
        retrieved_at="2026-09-29T00:00:00Z",
        workspace_id="ws",
        freshness=Freshness.CURRENT,
    )


class TestT4HistoryCannotOverrideCurrent:
    """A past report describes the past. It is kept, and it does not win."""

    @pytest.fixture
    def workspace_with_a_stale_report(self, tmp_path: Path, fake_git):
        """A report declaring an old HEAD, on the same subject as live git."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/report.md",
            declaration_document(("HEAD", OLD_SHA_UPPER)),
        )
        manifest = (
            GitCurrentStateSource(fake_git),
            DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),
        )
        return build_context(root, manifest=manifest, reader=fake_git)

    def test_both_the_fact_and_the_history_survive(
        self, workspace_with_a_stale_report
    ):
        response = workspace_with_a_stale_report
        assert any(i.value == SAMPLE_SHA for i in response.facts)
        assert any(i.value == OLD_SHA_UPPER for i in response.history)

    def test_the_report_lands_on_the_same_subject_as_git(self, workspace_with_a_stale_report):
        """The alias table is what makes the conflict detectable at all (D-5)."""
        subjects = {i.subject for i in workspace_with_a_stale_report.history}
        assert "git.head" in subjects

    def test_the_current_fact_is_authoritative(self, workspace_with_a_stale_report):
        resolution = [
            r for r in workspace_with_a_stale_report.conflicts if r.subject == "git.head"
        ]
        assert len(resolution) == 1
        assert resolution[0].authoritative is not None
        assert resolution[0].authoritative.source_kind is SourceKind.GIT_CURRENT_STATE

    def test_the_history_item_is_retained_and_marked(self, workspace_with_a_stale_report):
        stale = [i for i in workspace_with_a_stale_report.history if i.subject == "git.head"]
        assert len(stale) == 1, "the losing item was deleted rather than superseded"
        assert stale[0].superseded_by is not None
        assert stale[0].superseded_by.source_kind is SourceKind.GIT_CURRENT_STATE

    def test_the_winning_item_is_not_marked_superseded(self, workspace_with_a_stale_report):
        winner = [
            i
            for i in workspace_with_a_stale_report.facts
            if i.subject == "git.head"
        ][0]
        assert winner.superseded_by is None

    def test_the_past_value_never_becomes_a_present_fact(
        self, workspace_with_a_stale_report
    ):
        for fact_item in workspace_with_a_stale_report.facts:
            assert fact_item.value != OLD_SHA_UPPER

    def test_the_historical_item_stays_out_of_facts(self, workspace_with_a_stale_report):
        for fact_item in workspace_with_a_stale_report.facts:
            assert fact_item.item_kind is ItemKind.FACT

    def test_a_git_history_commit_does_not_claim_the_head_subject(
        self, tmp_path: Path, fake_git
    ):
        from tests.context.conftest import git_log_lines

        root = tmp_path / "ws"
        root.mkdir()
        fake_git.log = git_log_lines([("c" * 40, "2026-09-29T10:00:00+00:00", "work")])
        response = build_context(
            root, manifest=(GitHistorySource(fake_git),), reader=fake_git
        )
        assert all(i.subject.startswith("git.commit.") for i in response.history)


class TestT11SourcePriorityIsDeterministic:
    """Same class, different priority: the frozen table decides."""

    def test_the_roadmap_outranks_the_inventory_within_plan(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root, "docs/roadmap.md", declaration_document(("Phase", "PLANNED"))
        )
        write_document(
            root, "docs/status.md", declaration_document(("Phase", "DEFERRED"))
        )
        manifest = (
            DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),
            DocumentSource(SourceKind.MASTER_ROADMAP, "docs/roadmap.md"),
        )
        response = build_context(root, manifest=manifest, reader=fake_git)

        resolution = [r for r in response.conflicts if r.subject == "declared.phase"]
        assert len(resolution) == 1
        assert resolution[0].authoritative.source_kind is SourceKind.MASTER_ROADMAP

    def test_the_winner_does_not_depend_on_manifest_order(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, "docs/roadmap.md", declaration_document(("Phase", "PLANNED")))
        write_document(root, "docs/status.md", declaration_document(("Phase", "DEFERRED")))
        roadmap = DocumentSource(SourceKind.MASTER_ROADMAP, "docs/roadmap.md")
        inventory = DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md")

        forwards = build_context(
            root, manifest=(roadmap, inventory), reader=fake_git
        )
        backwards = build_context(
            root, manifest=(inventory, roadmap), reader=fake_git
        )

        def winner(response):
            return [
                r.authoritative.source_kind
                for r in response.conflicts
                if r.subject == "declared.phase"
            ][0]

        assert winner(forwards) is winner(backwards) is SourceKind.MASTER_ROADMAP

    def test_evidence_beats_a_higher_priority_plan(self, tmp_path: Path, fake_git):
        """D-8: the §6 table ranks sources, not kinds.

        The inventory is P2 and the exit report is P4, so the frozen priority
        table prefers the inventory. The evidence rule overrides it, because a
        plan is not evidence however highly its source ranks.
        """
        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, "docs/status.md", declaration_document(("Gate", "PLANNED")))
        write_document(root, "docs/report.md", declaration_document(("Gate", "PASS")))
        inventory = DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md")
        report = DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md")

        response = build_context(
            root, manifest=(inventory, report), reader=fake_git
        )
        resolution = [r for r in response.conflicts if r.subject == "declared.gate"][0]
        assert resolution.authoritative.source_kind is SourceKind.EXIT_REPORT
        assert resolution.evidenced.source_kind is SourceKind.EXIT_REPORT

    def test_a_live_fact_beats_a_higher_priority_plan(self, tmp_path: Path, fake_git):
        """The same rule against P0: a roadmap cannot contradict the repository."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, "docs/roadmap.md", declaration_document(("HEAD", OLD_SHA_UPPER)))
        response = build_context(
            root,
            manifest=(
                GitCurrentStateSource(fake_git),
                DocumentSource(SourceKind.MASTER_ROADMAP, "docs/roadmap.md"),
            ),
            reader=fake_git,
        )
        resolution = [r for r in response.conflicts if r.subject == "git.head"][0]
        assert resolution.authoritative.source_kind is SourceKind.GIT_CURRENT_STATE

    def test_resolution_is_stable_across_repeated_builds(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, "docs/roadmap.md", declaration_document(("Phase", "PLANNED")))
        write_document(root, "docs/status.md", declaration_document(("Phase", "DEFERRED")))
        manifest = (
            DocumentSource(SourceKind.MASTER_ROADMAP, "docs/roadmap.md"),
            DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),
        )
        first = build_context(root, manifest=manifest, reader=fake_git)
        second = build_context(root, manifest=manifest, reader=fake_git)
        assert [r.to_dict() for r in first.conflicts] == [
            r.to_dict() for r in second.conflicts
        ]


class TestOrderingIsTotal:
    def test_kind_rank_precedes_priority(self):
        fact = item(
            subject="s", value="1", source_kind=SourceKind.GIT_CURRENT_STATE
        )
        plan = item(subject="s", value="2", source_kind=SourceKind.MASTER_ROADMAP)
        assert ordering_key(fact) < ordering_key(plan)

    def test_priority_breaks_ties_within_a_kind(self):
        roadmap = item(subject="s", value="1", source_kind=SourceKind.MASTER_ROADMAP)
        inventory = item(
            subject="s", value="1", source_kind=SourceKind.CAPABILITY_INVENTORY
        )
        assert ordering_key(roadmap) < ordering_key(inventory)

    def test_identity_breaks_ties_within_a_source_kind(self):
        early = item(
            subject="s", value="1", source_kind=SourceKind.EXIT_REPORT, identity="a.md"
        )
        late = item(
            subject="s", value="1", source_kind=SourceKind.EXIT_REPORT, identity="b.md"
        )
        assert ordering_key(early) < ordering_key(late)

    def test_value_breaks_a_self_contradiction(self):
        """One document declaring two values must still resolve the same way twice.

        Amendment 2: steps 1-4 are **not** total. Two items from one read of one
        file share subject, class, priority, identity and revision, so only
        `value` separates them.
        """
        first = item(subject="s", value="AAA", source_kind=SourceKind.EXIT_REPORT)
        second = item(subject="s", value="BBB", source_kind=SourceKind.EXIT_REPORT)

        # Same everything except the value -- the case §11.2 originally denied.
        assert first.source_identity == second.source_identity
        assert first.source_revision == second.source_revision
        assert ordering_key(first) != ordering_key(second)

        once = resolve_subject((first, second))
        twice = resolve_subject((second, first))
        assert once.authoritative == twice.authoritative

    def test_a_real_self_contradicting_document_resolves_deterministically(
        self, tmp_path: Path, fake_git
    ):
        """The same case through the real extraction path (§7.3 keeps both)."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/report.md",
            declaration_document(("Gate", "PASS"), ("Gate", "FAIL")),
        )
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),)

        first = build_context(root, manifest=manifest, reader=fake_git)
        second = build_context(root, manifest=manifest, reader=fake_git)

        # Both declarations survive: a contradiction is not a duplicate.
        assert len(first.history) == 2
        assert {i.value for i in first.history} == {"PASS", "FAIL"}

        assert [c.to_dict() for c in first.conflicts] == [
            c.to_dict() for c in second.conflicts
        ]

    def test_the_losing_half_of_a_contradiction_is_retained(
        self, tmp_path: Path, fake_git
    ):
        """The contradiction stays visible; resolution does not hide it."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(
            root,
            "docs/report.md",
            declaration_document(("Gate", "PASS"), ("Gate", "FAIL")),
        )
        response = build_context(
            root,
            manifest=(DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md"),),
            reader=fake_git,
        )
        superseded = [i for i in response.history if i.superseded_by is not None]
        assert len(superseded) == 1
        assert superseded[0].value in {"PASS", "FAIL"}

    def test_ordering_does_not_depend_on_input_order(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.EXIT_REPORT, identity="b"),
            item(subject="s", value="2", source_kind=SourceKind.GIT_CURRENT_STATE),
            item(subject="s", value="3", source_kind=SourceKind.MASTER_ROADMAP),
        )
        forwards = resolve_subject(items).authoritative
        backwards = resolve_subject(tuple(reversed(items))).authoritative
        assert forwards == backwards


class TestResolutionRecord:
    def test_an_uncontested_subject_is_not_a_conflict(self):
        single = item(subject="s", value="1", source_kind=SourceKind.EXIT_REPORT)
        assert contested_subjects((single,)) == {}
        assert resolve_conflicts((single,)) == ()

    def test_a_contested_subject_is_reported(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.EXIT_REPORT),
            item(subject="s", value="2", source_kind=SourceKind.MASTER_ROADMAP),
        )
        assert list(contested_subjects(items)) == ["s"]
        assert len(resolve_conflicts(items)) == 1

    def test_evidenced_is_none_when_nothing_declares_a_state(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.EXIT_REPORT),
            item(subject="s", value="2", source_kind=SourceKind.MASTER_ROADMAP),
        )
        assert resolve_subject(items).evidenced is None

    def test_evidenced_names_the_highest_ranked_state(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.MASTER_ROADMAP),
            item(
                subject="s",
                value="2",
                source_kind=SourceKind.EXIT_REPORT,
                declared="NOT_RUN",
            ),
        )
        resolution = resolve_subject(items)
        assert resolution.evidenced is not None
        assert resolution.evidenced.source_kind is SourceKind.EXIT_REPORT

    def test_every_loser_is_listed(self):
        items = tuple(
            item(subject="s", value=str(n), source_kind=SourceKind.EXIT_REPORT, identity=f"{n}.md")
            for n in range(3)
        )
        assert len(resolve_subject(items).superseded) == 2

    def test_a_resolution_refuses_a_mixed_subject(self):
        items = (
            item(subject="a", value="1", source_kind=SourceKind.EXIT_REPORT),
            item(subject="b", value="2", source_kind=SourceKind.EXIT_REPORT),
        )
        with pytest.raises(ValueError):
            resolve_subject(items)

    def test_a_resolution_refuses_an_empty_subject(self):
        with pytest.raises(ValueError):
            resolve_subject(())


class TestApplyResolution:
    def test_it_marks_only_the_losers(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.GIT_CURRENT_STATE),
            item(subject="s", value="2", source_kind=SourceKind.MASTER_ROADMAP),
        )
        marked = apply_resolution(items)
        winner = [i for i in marked if i.source_kind is SourceKind.GIT_CURRENT_STATE][0]
        loser = [i for i in marked if i.source_kind is SourceKind.MASTER_ROADMAP][0]
        assert winner.superseded_by is None
        assert loser.superseded_by == winner.ref

    def test_no_item_is_removed(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.GIT_CURRENT_STATE),
            item(subject="s", value="2", source_kind=SourceKind.MASTER_ROADMAP),
        )
        assert len(apply_resolution(items)) == len(items)

    def test_it_is_idempotent(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.GIT_CURRENT_STATE),
            item(subject="s", value="2", source_kind=SourceKind.MASTER_ROADMAP),
        )
        once = apply_resolution(items)
        assert [i.superseded_by for i in apply_resolution(once)] == [
            i.superseded_by for i in once
        ]

    def test_an_uncontested_item_keeps_a_clear_field(self):
        single = item(subject="s", value="1", source_kind=SourceKind.EXIT_REPORT)
        assert apply_resolution((single,))[0].superseded_by is None

    def test_a_reference_renders_readably(self):
        reference = ItemRef(SourceKind.EXIT_REPORT, "docs/report.md", "abc", "NOT_RUN")
        assert reference.render() == "exit_report:docs/report.md@abc = NOT_RUN"

    def test_a_reference_distinguishes_two_items_from_one_read(self):
        """Amendment 3: a ref names an item, not a read.

        Both halves of a self-contradicting document come from one read, so a
        ref without `value` made them equal — and conflict resolution, which
        compares refs, then marked neither as superseded.
        """
        pass_item = item(subject="s", value="PASS", source_kind=SourceKind.EXIT_REPORT)
        fail_item = item(subject="s", value="FAIL", source_kind=SourceKind.EXIT_REPORT)
        # One read: same kind, same identity, same revision.
        assert pass_item.source_kind == fail_item.source_kind
        assert pass_item.source_identity == fail_item.source_identity
        assert pass_item.source_revision == fail_item.source_revision
        # Two items, so two refs.
        assert pass_item.ref != fail_item.ref


class TestUnknownIsNotResolvedAway:
    def test_an_unknown_never_becomes_the_evidenced_item(self):
        items = (
            item(subject="s", value="1", source_kind=SourceKind.GIT_CURRENT_STATE),
            item(
                subject="s",
                value="2",
                source_kind=SourceKind.EXIT_REPORT,
                declared="COMPLETE",
            ),
        )
        resolution = resolve_subject(items)
        # The exit report declares nothing in the truth model, so it is not
        # evidence for this subject -- even though it is a HISTORY item.
        assert resolution.evidenced is None or (
            resolution.evidenced.source_kind is not SourceKind.EXIT_REPORT
        )

    def test_an_unknown_truth_state_is_never_replaced_by_inference(self):
        declared_unknown = item(
            subject="s",
            value="1",
            source_kind=SourceKind.EXIT_REPORT,
            declared="UNKNOWN",
        )
        assert declared_unknown.truth_state is StatusValue.UNKNOWN
        assert declared_unknown.declared_state == "UNKNOWN"
