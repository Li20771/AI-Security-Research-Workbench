"""Workspace isolation.

The brief's T1 and T12.

T12 is the one that needs care about what it claims. "SecurityLab must not be
mixed into the Workbench context" does **not** mean the string `SecurityLab` is
forbidden — this repository's own `docs/PROJECT_STATUS.md` contains the line
`SecurityLab = UNCHANGED`, and that line is *this* workspace's content, read
from *this* workspace's file. Suppressing it would be censoring the workspace's
own record. What isolation actually forbids is:

* reading a source outside the workspace root,
* carrying another workspace's identity,
* discovering a sibling workspace at all,
* and consulting a registry that names other workspaces.

Those four are what these tests check, structurally.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from plugins.context.context import build_context
from plugins.context.sources import (
    DocumentSource,
    GitCurrentStateSource,
    build_manifest,
)
from plugins.context.vocabulary import SourceKind, SourceReadStatus
from plugins.context.workspace import is_inside, resolve_workspace
from tests.context.conftest import declaration_document, write_document


pytestmark = pytest.mark.layer2

#: A string that appears only inside the sibling workspace. If it turns up in
#: the workbench's context, something read across the boundary.
SIBLING_MARKER = "SIBLING-WORKSPACE-ONLY-MARKER"


@pytest.fixture
def sibling_pair(tmp_path: Path, fake_git):
    """A workbench workspace and a sibling research workspace beside it.

    The sibling is laid out the way SecurityLab is: a separate directory with
    its own documents, containing material the workbench has no business
    reading.
    """
    workbench = tmp_path / "AI-Security-Research-Workbench"
    workbench.mkdir()
    write_document(
        workbench,
        "docs/PROJECT_STATUS.md",
        declaration_document(("SecurityLab", "UNCHANGED")),
    )

    sibling = tmp_path / "SecurityLab"
    sibling.mkdir()
    write_document(
        sibling,
        "docs/status.md",
        declaration_document(("UDS-Research", SIBLING_MARKER)),
    )
    write_document(sibling, "docs/roadmap.md", f"# {SIBLING_MARKER}\n")

    return workbench, sibling


class TestT1WorkspaceIsolation:
    def test_two_workspaces_have_two_identities(self, tmp_path: Path, fake_git):
        roots = []
        for name in ("a", "b"):
            root = tmp_path / name
            root.mkdir()
            roots.append(root)
        ids = {
            resolve_workspace(root, reader=FakeReaderFor(root, fake_git)).workspace_id
            for root in roots
        }
        assert len(ids) == 2

    def test_a_context_carries_exactly_one_workspace(self, workspace_a, workspace_b, fake_git):
        manifest = (DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),)
        first = build_context(workspace_a, manifest=manifest, reader=fake_git)
        second = build_context(workspace_b, manifest=manifest, reader=fake_git)

        for response in (first, second):
            identities = {response.workspace.workspace_id}
            identities |= {item.workspace_id for item in response.items}
            identities |= {record.workspace_id for record in response.sources}
            assert len(identities) == 1

    def test_a_is_not_polluted_by_b(self, workspace_a, workspace_b, fake_git):
        manifest = (DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),)
        response = build_context(workspace_a, manifest=manifest, reader=fake_git)
        values = {item.value for item in response.items}
        assert "DIRTY" not in values, "workspace A received workspace B's declaration"
        assert "CLEAN" in values

    def test_b_is_not_polluted_by_a(self, workspace_a, workspace_b, fake_git):
        manifest = (DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),)
        response = build_context(workspace_b, manifest=manifest, reader=fake_git)
        values = {item.value for item in response.items}
        assert "CLEAN" not in values, "workspace B received workspace A's declaration"
        assert "DIRTY" in values

    def test_a_source_escaping_the_root_is_refused(self, workspace_a, workspace_b, fake_git):
        """A relative path that climbs out is refused before it is opened."""
        escaping = DocumentSource(
            SourceKind.EXIT_REPORT, "../workspace-b/docs/status.md"
        )
        response = build_context(
            workspace_a, manifest=(escaping,), reader=fake_git
        )
        assert response.sources[0].read_status is SourceReadStatus.REFUSED
        assert response.items == ()

    def test_an_absolute_path_is_refused(self, workspace_a, workspace_b, fake_git):
        absolute = DocumentSource(
            SourceKind.EXIT_REPORT, (workspace_b / "docs/status.md").as_posix()
        )
        response = build_context(workspace_a, manifest=(absolute,), reader=fake_git)
        assert response.sources[0].read_status is SourceReadStatus.REFUSED

    def test_a_linked_path_out_of_the_root_is_refused(
        self, workspace_a, workspace_b, fake_git
    ):
        """Containment is checked after resolution, so a link does not defeat it.

        A Unix symlink needs a privilege Windows does not grant by default, so
        this falls back to a directory junction, which needs none. The property
        under test -- a path that *resolves* outside the root is refused -- is
        the same for both.
        """
        link = workspace_a / "escape"
        if not _make_directory_link(link, workspace_b):
            pytest.skip("no link type is available in this environment")

        source = DocumentSource(SourceKind.EXIT_REPORT, "escape/docs/status.md")
        response = build_context(workspace_a, manifest=(source,), reader=fake_git)
        assert response.sources[0].read_status is SourceReadStatus.REFUSED
        assert response.items == ()

    def test_a_linked_path_is_outside_the_root(self, workspace_a, workspace_b):
        link = workspace_a / "escape"
        if not _make_directory_link(link, workspace_b):
            pytest.skip("no link type is available in this environment")
        assert not is_inside(workspace_a, link / "docs/status.md")

    def test_a_refused_source_does_not_abort_the_build(self, workspace_a, fake_git):
        """A refusal is recorded and degrades to PARTIAL, not to an exception."""
        from plugins.context.vocabulary import ContextStatus

        response = build_context(
            workspace_a,
            manifest=(
                DocumentSource(SourceKind.EXIT_REPORT, "../elsewhere.md"),
                DocumentSource(SourceKind.CAPABILITY_INVENTORY, "docs/status.md"),
            ),
            reader=fake_git,
        )
        assert response.status is ContextStatus.PARTIAL
        assert response.items

    def test_containment_helper_rejects_an_outside_path(self, workspace_a, workspace_b):
        assert is_inside(workspace_a, workspace_a / "docs/status.md")
        assert not is_inside(workspace_a, workspace_b / "docs/status.md")
        assert not is_inside(workspace_a, workspace_a / ".." / "workspace-b")

    def test_the_manifest_never_names_a_path_outside_the_root(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        for source in build_manifest(root, fake_git):
            if isinstance(source, DocumentSource):
                assert is_inside(root, root / source.relative_path), source.identity()


class TestT12SiblingWorkspaceIsolation:
    def test_a_sibling_workspace_never_reaches_the_context(self, sibling_pair, fake_git):
        workbench, _sibling = sibling_pair
        response = build_context(workbench, reader=fake_git)
        assert SIBLING_MARKER not in json.dumps(response.to_dict())

    def test_no_item_originates_outside_the_root(self, sibling_pair, fake_git):
        workbench, _sibling = sibling_pair
        response = build_context(workbench, reader=fake_git)
        for record in response.sources:
            if "/" in record.source_identity:
                assert is_inside(
                    workbench, workbench / record.source_identity
                ), record.source_identity

    def test_the_sibling_is_never_named_as_a_source(self, sibling_pair, fake_git):
        workbench, sibling = sibling_pair
        response = build_context(workbench, reader=fake_git)
        for record in response.sources:
            assert "SecurityLab" not in record.source_identity
            assert sibling.name not in record.source_identity

    def test_the_resolver_does_not_discover_the_sibling(self, sibling_pair, fake_git):
        """No git call is made against a directory other than the root."""
        workbench, sibling = sibling_pair
        fake_git.calls.clear()
        resolve_workspace(workbench, reader=fake_git)
        for root, _args in fake_git.calls:
            assert root == workbench, f"the resolver read {root}"
            assert root != sibling

    def test_the_workspace_registry_is_not_consulted(self, sibling_pair, fake_git):
        """`workspaces/workspaces.example.yaml` names a `securitylab` entry.

        Reading it would import a declaration about another workspace into this
        one's context. It is not in the manifest, and the build does not go
        looking for it.
        """
        workbench, _sibling = sibling_pair
        response = build_context(workbench, reader=fake_git)
        identities = {record.source_identity for record in response.sources}
        assert "workspaces/workspaces.example.yaml" not in identities

    def test_the_workbench_may_record_its_own_statement_about_a_sibling(
        self, sibling_pair, fake_git
    ):
        """The line `SecurityLab = UNCHANGED` is this workspace's own record.

        Isolation is about *sources*, not about vocabulary. Refusing to report
        a workspace's own statement would be censoring its record, not
        protecting it.
        """
        workbench, _sibling = sibling_pair
        response = build_context(workbench, reader=fake_git)
        subjects = {item.subject for item in response.items}
        assert "declared.securitylab" in subjects
        item = [i for i in response.items if i.subject == "declared.securitylab"][0]
        assert item.declared_state == "UNCHANGED"
        # ...and it is recorded as this workspace's declaration, read from this
        # workspace's file.
        assert item.workspace_id == response.workspace.workspace_id

    def test_two_adjacent_workspaces_keep_separate_identities(self, sibling_pair, fake_git):
        workbench, sibling = sibling_pair
        first = resolve_workspace(workbench, reader=fake_git)
        second = resolve_workspace(sibling, reader=fake_git)
        assert first.workspace_id != second.workspace_id
        assert first.workspace_root != second.workspace_root


class TestNoUpwardRepositorySearch:
    """Contract §6.4: a directory inside a repository is not that repository."""

    def test_a_directory_inside_a_repository_borrows_nothing(self, tmp_path: Path, fake_git):
        root = tmp_path / "repo"
        inner = root / "sub" / "dir"
        inner.mkdir(parents=True)
        fake_git.own_repository = False

        identity = resolve_workspace(inner, reader=fake_git)
        assert identity.commit is None
        assert identity.branch is None
        assert identity.repository is None
        assert identity.working_tree.value == "UNKNOWN"

    def test_unknown_is_not_clean(self, tmp_path: Path, fake_git):
        from plugins.context.vocabulary import WorkingTreeState

        root = tmp_path / "plain"
        root.mkdir()
        identity = resolve_workspace(
            root, reader=NotARepositoryReader()
        )
        assert identity.working_tree is WorkingTreeState.UNKNOWN
        assert identity.working_tree is not WorkingTreeState.CLEAN

    def test_the_inner_directory_has_its_own_identity(self, tmp_path: Path, fake_git):
        outer = tmp_path / "repo"
        inner = outer / "sub"
        inner.mkdir(parents=True)
        fake_git.own_repository = False
        assert (
            resolve_workspace(outer, reader=fake_git).workspace_id
            != resolve_workspace(inner, reader=fake_git).workspace_id
        )


class TestGitSourceIsReadOnly:
    def test_a_write_command_is_refused_before_a_process_exists(self):
        from plugins.context.errors import GitCommandRefused
        from plugins.context.workspace import SubprocessGitReader

        reader = SubprocessGitReader()
        for forbidden in ("commit", "push", "add", "checkout", "reset", "merge", "clean"):
            with pytest.raises(GitCommandRefused):
                reader.run(Path("."), (forbidden,))

    def test_a_global_option_cannot_be_smuggled_past_the_guard(self):
        from plugins.context.errors import GitCommandRefused
        from plugins.context.workspace import SubprocessGitReader

        with pytest.raises(GitCommandRefused):
            SubprocessGitReader().run(Path("."), ("-c", "x=y", "commit"))

    def test_an_empty_command_is_refused(self):
        from plugins.context.errors import GitCommandRefused
        from plugins.context.workspace import SubprocessGitReader

        with pytest.raises(GitCommandRefused):
            SubprocessGitReader().run(Path("."), ())

    def test_the_read_set_is_exactly_the_frozen_one(self):
        from plugins.context.workspace import READ_ONLY_GIT_COMMANDS

        assert READ_ONLY_GIT_COMMANDS == {
            "rev-parse",
            "symbolic-ref",
            "status",
            "log",
            "remote",
        }

    @pytest.mark.parametrize(
        "invocation",
        [
            ("remote", "add", "origin", "https://example.invalid/x.git"),
            ("remote", "remove", "origin"),
            ("remote", "set-url", "origin", "https://example.invalid/y.git"),
            ("remote", "prune"),
            ("remote", "update"),
            ("remote",),
        ],
    )
    def test_a_write_shaped_remote_is_refused(self, invocation):
        """`git remote` is read-only in one shape and a write in another.

        `git remote get-url` reads; `git remote add` rewrites `.git/config`.
        A guard that checked only the subcommand would permit the second, which
        is a defect the Layer 0 check found by refusing to accept a check it
        could not fail.
        """
        from plugins.context.errors import GitCommandRefused
        from plugins.context.workspace import SubprocessGitReader

        with pytest.raises(GitCommandRefused):
            SubprocessGitReader().run(Path("."), invocation)

    @pytest.mark.parametrize(
        "invocation",
        [
            ("remote", "get-url", "origin"),
            ("remote", "show"),
            ("remote", "-v"),
        ],
    )
    def test_the_read_only_remote_shapes_are_permitted(self, invocation):
        """The other direction: a guard that refused everything is not a guard."""
        from plugins.context.errors import GitCommandRefused
        from plugins.context.workspace import SubprocessGitReader

        try:
            SubprocessGitReader().run(Path("."), invocation)
        except GitCommandRefused as exc:  # pragma: no cover - the failure path
            pytest.fail(f"{invocation} is read-only but was refused: {exc}")
        except Exception:
            # Permitted, and it failed against `.` for a reason that is not the
            # guard's business.
            pass


class TestThePackageContainsNoGitWrite:
    """The Layer 0 scan as a test, so it fails in the suite as well as in CI."""

    def test_no_write_subcommand_appears_in_the_package(self):
        package = Path(__file__).resolve().parents[2] / "plugins" / "context"
        forbidden = (
            "git commit",
            "git push",
            "git add ",
            "git checkout",
            "git reset",
            "git restore",
            "git clean",
            "git merge",
            "git rebase",
            "git tag",
            "git stash",
            "git fetch",
            "git pull",
        )
        for path in sorted(package.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for needle in forbidden:
                assert needle not in text, f"{path.name} contains {needle!r}"


def _make_directory_link(link: Path, target: Path) -> bool:
    """Create a directory link at `link` pointing at `target`.

    Tries a symlink first and falls back to a Windows junction, which requires
    no elevation. Returns `False` when neither is available, so the caller can
    report the case as unexecuted rather than as passed.
    """
    if link.exists() or link.is_symlink():
        return True
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass

    if os.name != "nt":
        return False
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and link.exists()


class FakeReaderFor:
    """A reader that defers to a shared fake but reports `root` as its toplevel."""

    def __init__(self, root: Path, shared) -> None:
        self._root = Path(root)
        self._shared = shared

    def run(self, root, args):
        from tests.context.conftest import ok

        if tuple(args) == ("rev-parse", "--show-toplevel"):
            return ok(str(root))
        return self._shared.run(root, args)


class NotARepositoryReader:
    """A reader for which nothing resolves: every command fails."""

    def run(self, root, args):
        from tests.context.conftest import failed

        return failed("not a git repository")
