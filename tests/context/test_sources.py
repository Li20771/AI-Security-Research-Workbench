"""Source adapters and the default manifest.

Contract §7. The five required fields, the five read outcomes, and the
containment rule that makes workspace isolation structural.

The read outcomes matter more than they look. `MISSING` and `READ with nothing`
are the same shape to a careless consumer, and only one of them is a fact about
the workspace; these tests keep them distinct.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.context.errors import ManifestError
from plugins.context.sources import (
    CAPABILITY_INVENTORY_PATH,
    DESIGN_FREEZE_PATH,
    EXIT_REPORT_GLOB,
    HISTORY_COMMIT_LIMIT,
    MASTER_ROADMAP_PATH,
    DocumentSource,
    GitCurrentStateSource,
    GitHistorySource,
    SourceRead,
    build_manifest,
    manifest_identities,
)
from plugins.context.vocabulary import SourceKind, SourceReadStatus
from plugins.context.workspace import resolve_workspace
from tests.context.conftest import (
    SAMPLE_SHA,
    declaration_document,
    git_log_lines,
    write_document,
)


pytestmark = pytest.mark.layer2


@pytest.fixture
def workspace(tmp_path: Path, fake_git):
    root = tmp_path / "ws"
    root.mkdir()
    return resolve_workspace(root, reader=fake_git), root


class TestSourceReadContract:
    def test_a_read_carries_a_payload(self):
        read = SourceRead(
            status=SourceReadStatus.READ,
            source_revision="rev",
            payload=(),
            note=None,
        )
        assert read.status is SourceReadStatus.READ

    @pytest.mark.parametrize(
        "status",
        [
            SourceReadStatus.MISSING,
            SourceReadStatus.UNREADABLE,
            SourceReadStatus.REFUSED,
            SourceReadStatus.BLOCKED,
        ],
    )
    def test_an_unread_source_cannot_carry_a_payload(self, status):
        """The type refuses to represent "not read, but here are the contents"."""
        from plugins.context.classification import RawItem

        with pytest.raises(ManifestError):
            SourceRead(
                status=status,
                source_revision=None,
                payload=(RawItem(subject="s", value="v"),),
            )

    def test_the_five_fields_are_all_present(self, workspace):
        _, root = workspace
        write_document(root, "docs/report.md", declaration_document(("A", "PASS")))
        read = DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md").read(
            workspace[0], root
        )
        assert read.status is SourceReadStatus.READ
        assert read.source_revision is not None
        assert read.payload
        assert read.note is not None


class TestDocumentSource:
    def test_the_revision_is_the_content_digest(self, workspace):
        identity, root = workspace
        path = write_document(root, "docs/report.md", declaration_document(("A", "PASS")))
        source = DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md")

        first = source.read(identity, root).source_revision
        path.write_text(declaration_document(("A", "FAIL")), encoding="utf-8")
        second = source.read(identity, root).source_revision
        assert first != second

    def test_the_revision_is_stable_when_the_content_is(self, workspace):
        identity, root = workspace
        write_document(root, "docs/report.md", declaration_document(("A", "PASS")))
        source = DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md")
        assert source.read(identity, root).source_revision == (
            source.read(identity, root).source_revision
        )

    def test_a_missing_document_is_missing_not_empty(self, workspace):
        identity, root = workspace
        read = DocumentSource(SourceKind.MASTER_ROADMAP, "docs/absent.md").read(
            identity, root
        )
        assert read.status is SourceReadStatus.MISSING
        assert read.payload == ()
        assert read.source_revision is None

    def test_a_directory_is_unreadable(self, workspace):
        identity, root = workspace
        (root / "docs" / "a-directory.md").mkdir(parents=True)
        read = DocumentSource(SourceKind.MASTER_ROADMAP, "docs/a-directory.md").read(
            identity, root
        )
        assert read.status is SourceReadStatus.UNREADABLE

    def test_a_non_utf8_document_is_unreadable(self, workspace):
        identity, root = workspace
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "binary.md").write_bytes(b"\xff\xfe\x00\x01")
        read = DocumentSource(SourceKind.MASTER_ROADMAP, "docs/binary.md").read(
            identity, root
        )
        assert read.status is SourceReadStatus.UNREADABLE

    def test_a_document_with_no_declarations_is_read_with_no_items(self, workspace):
        """Read and empty is not the same as missing, and both are recorded."""
        identity, root = workspace
        write_document(root, "docs/prose.md", "# Just prose\n\nNo declarations.\n")
        read = DocumentSource(SourceKind.MASTER_ROADMAP, "docs/prose.md").read(
            identity, root
        )
        assert read.status is SourceReadStatus.READ
        assert read.payload == ()
        assert read.source_revision is not None

    def test_a_path_outside_the_root_is_refused(self, workspace, tmp_path):
        identity, root = workspace
        other = tmp_path / "other"
        other.mkdir()
        read = DocumentSource(SourceKind.EXIT_REPORT, "../other/x.md").read(identity, root)
        assert read.status is SourceReadStatus.REFUSED

    def test_the_identity_is_a_posix_relative_path(self):
        source = DocumentSource(SourceKind.EXIT_REPORT, "docs\\report.md")
        assert source.identity() == "docs/report.md"

    def test_declarations_become_raw_items(self, workspace):
        identity, root = workspace
        write_document(
            root,
            "docs/report.md",
            declaration_document(("Live provider execution", "NOT_RUN")),
        )
        read = DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md").read(
            identity, root
        )
        assert len(read.payload) == 1
        assert read.payload[0].subject == "declared.live_provider_execution"
        assert read.payload[0].declared_state == "NOT_RUN"


class TestGitCurrentStateSource:
    def test_it_reads_the_live_state(self, workspace, fake_git):
        identity, root = workspace
        read = GitCurrentStateSource(fake_git).read(identity, root)
        subjects = {item.subject: item.value for item in read.payload}
        assert subjects["git.head"] == SAMPLE_SHA
        assert subjects["git.branch"] == "main"
        assert subjects["git.working_tree"] == "CLEAN"
        assert subjects["git.detached"] == "FALSE"

    def test_a_failed_head_read_is_blocked(self, workspace, fake_git):
        identity, root = workspace
        fake_git.head = None
        read = GitCurrentStateSource(fake_git).read(identity, root)
        assert read.status is SourceReadStatus.BLOCKED
        assert read.payload == ()

    def test_a_dirty_tree_is_reported(self, workspace, fake_git):
        identity, root = workspace
        fake_git.porcelain = "?? a\n?? b\n"
        read = GitCurrentStateSource(fake_git).read(identity, root)
        values = {item.subject: item.value for item in read.payload}
        assert values["git.working_tree"] == "DIRTY"
        assert values["git.changed_files"] == "2"

    def test_an_unreadable_tree_says_unknown(self, workspace, fake_git):
        identity, root = workspace
        from tests.context.conftest import failed

        fake_git.set(root, ("status", "--porcelain"), failed())
        read = GitCurrentStateSource(fake_git).read(identity, root)
        values = {item.subject: item.value for item in read.payload}
        assert values["git.working_tree"] == "UNKNOWN"
        assert "git.changed_files" not in values

    def test_a_detached_head_emits_no_branch_item(self, workspace, fake_git):
        identity, root = workspace
        fake_git.branch = None
        read = GitCurrentStateSource(fake_git).read(identity, root)
        subjects = {item.subject for item in read.payload}
        assert "git.branch" not in subjects
        assert "git.detached" in subjects

    def test_the_revision_is_the_head_commit(self, workspace, fake_git):
        identity, root = workspace
        assert GitCurrentStateSource(fake_git).read(identity, root).source_revision == (
            SAMPLE_SHA
        )


class TestGitHistorySource:
    def test_it_emits_one_item_per_commit(self, workspace, fake_git):
        identity, root = workspace
        fake_git.log = git_log_lines(
            [
                ("a" * 40, "2026-09-29T10:00:00+00:00", "first"),
                ("b" * 40, "2026-09-29T11:00:00+00:00", "second"),
            ]
        )
        read = GitHistorySource(fake_git).read(identity, root)
        assert [item.subject for item in read.payload] == [
            f"git.commit.{'a' * 40}",
            f"git.commit.{'b' * 40}",
        ]

    def test_the_subject_and_date_are_kept(self, workspace, fake_git):
        identity, root = workspace
        fake_git.log = git_log_lines([("a" * 40, "2026-09-29T10:00:00+00:00", "fix a bug")])
        assert GitHistorySource(fake_git).read(identity, root).payload[0].value == (
            "2026-09-29T10:00:00+00:00 fix a bug"
        )

    def test_a_malformed_log_line_is_skipped_not_guessed(self, workspace, fake_git):
        identity, root = workspace
        fake_git.log = "not\ta\tvalid\trow\n" + git_log_lines(
            [("a" * 40, "2026-09-29T10:00:00+00:00", "real")]
        )
        read = GitHistorySource(fake_git).read(identity, root)
        assert len(read.payload) == 1

    def test_an_unreadable_head_is_blocked(self, workspace, fake_git):
        identity, root = workspace
        fake_git.head = None
        read = GitHistorySource(fake_git).read(identity, root)
        assert read.status is SourceReadStatus.BLOCKED

    def test_a_failed_log_is_blocked(self, workspace, fake_git):
        from tests.context.conftest import failed

        identity, root = workspace
        fake_git.set(root, ("log", f"--max-count={HISTORY_COMMIT_LIMIT}", "--format=%H\x1f%cI\x1f%s"), failed())
        read = GitHistorySource(fake_git).read(identity, root)
        assert read.status is SourceReadStatus.BLOCKED

    def test_the_limit_is_bounded_and_requested(self, workspace, fake_git):
        identity, root = workspace
        GitHistorySource(fake_git, limit=5).read(identity, root)
        assert any("--max-count=5" in arg for _, args in fake_git.calls for arg in args)

    def test_a_non_positive_limit_is_rejected(self, fake_git):
        with pytest.raises(ManifestError):
            GitHistorySource(fake_git, limit=0)

    def test_an_empty_history_is_read_with_no_items(self, workspace, fake_git):
        identity, root = workspace
        fake_git.log = ""
        read = GitHistorySource(fake_git).read(identity, root)
        assert read.status is SourceReadStatus.READ
        assert read.payload == ()

    def test_it_is_cacheable_and_the_live_state_is_not(self, workspace, fake_git):
        """D-14, stated as a property of the two git sources."""
        identity, root = workspace
        assert GitHistorySource(fake_git).probe_revision(identity, root) == SAMPLE_SHA
        assert GitCurrentStateSource(fake_git).probe_revision(identity, root) is None


class TestDefaultManifest:
    def test_every_source_kind_is_represented(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        kinds = [source.kind for source in build_manifest(root, fake_git)]
        assert kinds == [
            SourceKind.GIT_CURRENT_STATE,
            SourceKind.MASTER_ROADMAP,
            SourceKind.CAPABILITY_INVENTORY,
            SourceKind.DESIGN_FREEZE,
            SourceKind.EXIT_REPORT,  # the placeholder row; see below
            SourceKind.GIT_HISTORY,
        ]

    def test_the_manifest_covers_every_frozen_source_kind(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        assert {source.kind for source in build_manifest(root, fake_git)} == set(SourceKind)

    def test_the_document_bindings_are_the_contract_ones(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        identities = {source.identity() for source in build_manifest(root, fake_git)}
        assert MASTER_ROADMAP_PATH in identities
        assert CAPABILITY_INVENTORY_PATH in identities
        assert DESIGN_FREEZE_PATH in identities

    def test_each_exit_report_becomes_its_own_source(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, "docs/AI-01_CLOSEOUT_x.md", "")
        write_document(root, "docs/AI-02_CLOSEOUT_y.md", "")
        identities = [s.identity() for s in build_manifest(root, fake_git)]
        assert "docs/AI-01_CLOSEOUT_x.md" in identities
        assert "docs/AI-02_CLOSEOUT_y.md" in identities

    def test_no_exit_report_still_yields_a_source(self, tmp_path: Path, fake_git):
        """P4 having no members is a fact about the workspace, not an absence."""
        root = tmp_path / "ws"
        root.mkdir()
        reports = [
            s for s in build_manifest(root, fake_git) if s.kind is SourceKind.EXIT_REPORT
        ]
        assert len(reports) == 1
        assert reports[0].identity() == EXIT_REPORT_GLOB

    def test_the_empty_glob_source_reads_missing(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        identity = resolve_workspace(root, reader=fake_git)
        reports = [
            s for s in build_manifest(root, fake_git) if s.kind is SourceKind.EXIT_REPORT
        ]
        assert reports[0].read(identity, root).status is SourceReadStatus.MISSING

    def test_the_manifest_priorities_follow_the_frozen_table(self, tmp_path: Path, fake_git):
        from plugins.context.vocabulary import SOURCE_PRIORITY

        root = tmp_path / "ws"
        root.mkdir()
        ranks = [int(SOURCE_PRIORITY[s.kind]) for s in build_manifest(root, fake_git)]
        assert ranks == sorted(ranks)

    def test_manifest_identities_are_sorted_and_distinct(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        pairs = manifest_identities(build_manifest(root, fake_git))
        assert pairs == tuple(sorted(pairs))
        assert len(pairs) == len(set(pairs))
        assert len(pairs) == len(set(SourceKind))


class TestAdapterIdentityRules:
    def test_an_empty_identity_is_rejected(self):
        with pytest.raises(ManifestError):
            DocumentSource(SourceKind.EXIT_REPORT, "")

    def test_a_repr_names_the_kind_and_identity(self):
        source = DocumentSource(SourceKind.EXIT_REPORT, "docs/report.md")
        assert "exit_report" in repr(source)
        assert "docs/report.md" in repr(source)
