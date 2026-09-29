"""Layer 3 — the real repository, read through the real pipeline.

Contract §12.4. These tests run the extractor against this repository's actual
documents rather than against fixtures written to agree with it. That is the
point: a fixture proves the code matches the test author's understanding, while
`docs/PROJECT_STATUS.md` proves it matches a document nobody wrote for this
test.

> A fixture is not evidence about the world. These tests pin *our* extraction
> against real repository text. They establish nothing about any other
> workspace, and they cannot promote anything.

Nothing here asserts that any phase passed. `NOT_RUN` in a closeout document is
read as `NOT_RUN`; the test asserts the *reading*, never the result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.context.context import build_context
from plugins.context.vocabulary import (
    ITEM_KIND_BY_SOURCE,
    ItemKind,
    SourceKind,
    SourceReadStatus,
    StatusValue,
)
from plugins.context.validate import repository_root


pytestmark = pytest.mark.layer3

#: The subject the two real documents agree on. `docs/PROJECT_STATUS.md` is the
#: P2 capability inventory and `docs/AI-02_CLOSEOUT_2026-09-29.md` is a P4 exit
#: report, so this subject is a genuine cross-source conflict rather than a
#: constructed one.
LIVE_EXECUTION_SUBJECT = "declared.live_provider_execution"


@pytest.fixture(scope="module")
def context():
    return build_context(repository_root())


def git_output(*args: str) -> str:
    """Run git directly, so an assertion compares the plugin against git."""
    import subprocess

    return subprocess.run(
        ["git", *args],
        cwd=repository_root(),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class TestTheRepositoryReadsAsItself:
    def test_the_workspace_is_this_repository(self, context):
        assert context.workspace.repository == (
            "Li20771/AI-Security-Research-Workbench"
        )

    def test_the_live_git_state_is_present(self, context):
        """The three subjects every checkout has, attached or detached.

        `git.branch` is deliberately **not** in this set. A detached HEAD has
        no branch, and `actions/checkout` leaves one on every `pull_request`
        run, so requiring a branch here would assert a property of the
        developer's machine rather than a property of the plugin. The original
        version of this test did exactly that and failed on its first CI run;
        `test_branch_and_detached_agree` now states the real invariant.
        """
        subjects = {item.subject for item in context.facts}
        assert {"git.head", "git.working_tree", "git.detached"} <= subjects

    def test_branch_and_detached_agree(self, context):
        """A branch item exists exactly when the checkout is not detached."""
        facts = {item.subject: item.value for item in context.facts}
        detached = facts["git.detached"] == "TRUE"
        assert ("git.branch" in facts) is not detached

    def test_a_branch_item_matches_git_when_present(self, context):
        """When there is a branch, it is git's branch -- not one we invented."""
        facts = {item.subject: item.value for item in context.facts}
        if "git.branch" not in facts:
            pytest.skip("detached HEAD: there is no branch to compare")
        assert facts["git.branch"] == git_output("symbolic-ref", "--short", "-q", "HEAD")

    def test_the_head_matches_git(self, context):
        item = [i for i in context.facts if i.subject == "git.head"][0]
        assert item.value == git_output("rev-parse", "HEAD")

    def test_the_working_tree_matches_git(self, context):
        facts = {item.subject: item.value for item in context.facts}
        porcelain = git_output("status", "--porcelain")
        expected = "CLEAN" if not porcelain.strip() else "DIRTY"
        assert facts["git.working_tree"] == expected

    def test_the_documented_sources_were_read(self, context):
        read = {
            record.source_identity
            for record in context.sources
            if record.read_status is SourceReadStatus.READ
        }
        assert "docs/PROJECT_STATUS.md" in read
        assert "docs/MASTER_ROADMAP.md" in read
        assert "docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md" in read

    def test_the_ai_02_closeout_is_discovered_as_an_exit_report(self, context):
        reports = [
            record
            for record in context.sources
            if record.source_kind is SourceKind.EXIT_REPORT
        ]
        assert reports
        assert any("CLOSEOUT" in record.source_identity for record in reports)

    def test_every_read_source_carries_a_revision(self, context):
        for record in context.sources:
            if record.read_status is SourceReadStatus.READ:
                assert record.source_revision, record.source_identity


class TestTheRealDeclarationsSurvive:
    def test_live_provider_execution_is_not_run(self, context):
        """The claim AI-02 recorded, read back unchanged."""
        items = [i for i in context.items if i.subject == LIVE_EXECUTION_SUBJECT]
        assert items
        assert {i.declared_state for i in items} == {"NOT_RUN"}
        assert all(i.truth_state is StatusValue.NOT_RUN for i in items)

    def test_not_run_was_not_promoted_to_pass(self, context):
        for item in context.items:
            if item.subject == LIVE_EXECUTION_SUBJECT:
                assert item.truth_state is not StatusValue.PASS

    def test_a_lifecycle_word_in_the_real_documents_is_not_a_pass(self, context):
        """`AI-02 overall = COMPLETE` is a lifecycle word, not a truth state."""
        completes = [i for i in context.items if i.declared_state == "COMPLETE"]
        assert completes, "the real documents declare COMPLETE; the extractor missed it"
        for item in completes:
            assert item.truth_state is StatusValue.UNKNOWN

    def test_a_compound_real_declaration_is_not_decomposed(self, context):
        """`Clean-room reinstall = BLOCKED / DEFERRED` is not `BLOCKED`."""
        compounds = [
            i for i in context.items if i.declared_state == "BLOCKED / DEFERRED"
        ]
        assert compounds, "the real documents declare a compound value"
        for item in compounds:
            assert item.truth_state is StatusValue.UNKNOWN

    def test_no_item_claims_a_pass_it_did_not_read(self, context):
        """The invariant, checked against real repository text."""
        for item in context.items:
            if item.truth_state is StatusValue.PASS:
                assert item.declared_state == "PASS", item.subject

    def test_a_pass_in_the_real_documents_is_read_as_a_pass(self, context):
        """The rule is not a blanket downgrade: a literal `PASS` survives."""
        passes = [i for i in context.items if i.declared_state == "PASS"]
        assert passes, "the real documents declare PASS; the extractor missed it"
        assert all(i.truth_state is StatusValue.PASS for i in passes)


class TestTheRealConflictIsFoundAndResolved:
    def test_the_subject_is_contested(self, context):
        contested = {conflict.subject for conflict in context.conflicts}
        assert LIVE_EXECUTION_SUBJECT in contested

    def test_the_two_sides_are_the_inventory_and_the_exit_report(self, context):
        conflict = [
            c for c in context.conflicts if c.subject == LIVE_EXECUTION_SUBJECT
        ][0]
        assert conflict.authoritative is not None
        assert conflict.authoritative.source_kind is SourceKind.EXIT_REPORT
        assert [ref.source_kind for ref in conflict.superseded] == [
            SourceKind.CAPABILITY_INVENTORY
        ]

    def test_the_plan_lost_to_the_evidence(self, context):
        """D-8, on real data: P2 is ranked above P4, and still loses.

        The capability inventory is a PLAN-class source and the closeout is a
        HISTORY-class one, so the epistemic class decides before the frozen
        priority table does.
        """
        conflict = [
            c for c in context.conflicts if c.subject == LIVE_EXECUTION_SUBJECT
        ][0]
        assert conflict.authoritative is not None
        assert conflict.authoritative.render() != conflict.superseded[0].render()

    def test_the_superseded_item_is_retained_not_deleted(self, context):
        inventory_items = [
            i
            for i in context.plans
            if i.subject == LIVE_EXECUTION_SUBJECT
            and i.source_kind is SourceKind.CAPABILITY_INVENTORY
        ]
        assert len(inventory_items) == 1
        assert inventory_items[0].superseded_by is not None

    def test_the_losing_item_keeps_its_own_declared_state(self, context):
        """Superseding changes who wins, never what the source said."""
        item = [
            i
            for i in context.plans
            if i.subject == LIVE_EXECUTION_SUBJECT
        ][0]
        assert item.declared_state == "NOT_RUN"
        assert item.truth_state is StatusValue.NOT_RUN


class TestExtractionIsReproducible:
    """Two builds over unchanged content produce identical context.

    The clock is held fixed so that `retrieved_at` is not the thing under test;
    the assertion is about extraction and classification, and a timestamp that
    legitimately differs would mask a difference that legitimately should not.
    """

    @staticmethod
    def _frozen_clock() -> str:
        return "2026-09-29T00:00:00Z"

    def test_two_builds_produce_the_same_items(self):
        first = build_context(repository_root(), clock=self._frozen_clock)
        second = build_context(repository_root(), clock=self._frozen_clock)
        assert [i.to_dict() for i in first.items] == [i.to_dict() for i in second.items]

    def test_two_builds_produce_the_same_resolutions(self):
        first = build_context(repository_root(), clock=self._frozen_clock)
        second = build_context(repository_root(), clock=self._frozen_clock)
        assert [c.to_dict() for c in first.conflicts] == [
            c.to_dict() for c in second.conflicts
        ]

    def test_two_builds_produce_the_same_source_records(self):
        first = build_context(repository_root(), clock=self._frozen_clock)
        second = build_context(repository_root(), clock=self._frozen_clock)
        assert [r.to_dict() for r in first.sources] == [
            r.to_dict() for r in second.sources
        ]

    def test_the_clock_is_the_only_thing_that_differs(self):
        """Stated directly, so the exclusion above is a recorded fact."""
        payloads = []
        for _ in range(2):
            response = build_context(repository_root())
            payloads.append(
                [
                    {k: v for k, v in item.to_dict().items() if k != "retrieved_at"}
                    for item in response.items
                ]
            )
        assert payloads[0] == payloads[1]

    def test_a_document_revision_is_its_content_digest(self, context):
        """Pinning by digest: the revision identifies the bytes that were read."""
        import hashlib

        record = [
            r for r in context.sources if r.source_identity == "docs/PROJECT_STATUS.md"
        ][0]
        digest = hashlib.sha256(
            (repository_root() / "docs/PROJECT_STATUS.md").read_bytes()
        ).hexdigest()
        assert record.source_revision == digest


class TestTheShapeHoldsOnRealData:
    def test_every_item_kind_matches_its_source(self, context):
        for item in context.items:
            assert item.item_kind is ITEM_KIND_BY_SOURCE[item.source_kind]

    def test_the_lists_are_separated(self, context):
        assert all(i.item_kind is ItemKind.FACT for i in context.facts)
        assert all(i.item_kind is ItemKind.HISTORY for i in context.history)
        assert all(i.item_kind is ItemKind.PLAN for i in context.plans)

    def test_one_workspace_throughout(self, context):
        identities = {context.workspace.workspace_id}
        identities |= {i.workspace_id for i in context.items}
        identities |= {r.workspace_id for r in context.sources}
        assert len(identities) == 1

    def test_every_source_path_is_inside_the_repository(self, context):
        root = Path(context.workspace.workspace_root)
        for record in context.sources:
            if "/" in record.source_identity:
                resolved = (root / record.source_identity).resolve()
                assert root.resolve() in resolved.parents or resolved == root.resolve()

    def test_the_validation_passes_on_the_real_repository(self):
        from plugins.context.validate import validate_all

        assert validate_all() == []
