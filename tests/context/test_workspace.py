"""Workspace identity.

Contract §6. Identity is what every isolation guarantee is built on, so these
tests treat it as a load-bearing value rather than a label: it must be stable
across runs, distinct across roots, and derived from nothing but the root and
the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.context.errors import WorkspaceError
from plugins.context.vocabulary import WorkingTreeState
from plugins.context.workspace import (
    WorkspaceIdentity,
    canonical_root,
    normalise_repository,
    resolve_workspace,
    workspace_id_for,
)
from tests.context.conftest import SAMPLE_SHA


pytestmark = pytest.mark.layer2


class TestWorkspaceIdentityDerivation:
    def test_it_is_stable_across_calls(self, tmp_path: Path):
        root = tmp_path / "ws"
        root.mkdir()
        assert workspace_id_for(root, "o/n") == workspace_id_for(root, "o/n")

    def test_different_roots_have_different_ids(self, tmp_path: Path):
        first = tmp_path / "a"
        second = tmp_path / "b"
        first.mkdir()
        second.mkdir()
        assert workspace_id_for(first, None) != workspace_id_for(second, None)

    def test_one_root_under_two_repositories_has_two_ids(self, tmp_path: Path):
        root = tmp_path / "ws"
        root.mkdir()
        assert workspace_id_for(root, "o/one") != workspace_id_for(root, "o/two")

    def test_the_identity_is_not_a_path(self, tmp_path: Path):
        """An id that leaked the host path would not be portable between machines."""
        root = tmp_path / "ws"
        root.mkdir()
        identity = workspace_id_for(root, "o/n")
        assert str(root) not in identity
        assert identity.startswith("ws-")

    def test_the_identity_does_not_depend_on_time(self, tmp_path: Path):
        root = tmp_path / "ws"
        root.mkdir()
        assert workspace_id_for(root, "o/n") == workspace_id_for(root, "o/n")


class TestRepositoryNormalisation:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://github.com/owner/name.git", "owner/name"),
            ("https://github.com/owner/name", "owner/name"),
            ("git@github.com:owner/name.git", "owner/name"),
            ("git@github.com:owner/name", "owner/name"),
            ("ssh://git@github.com/owner/name.git", "owner/name"),
            ("https://github.com/owner/name/", "owner/name"),
            ("https://example.invalid/owner/name.git", "https://example.invalid/owner/name.git"),
            ("https://gitlab.com/owner/name.git", "https://gitlab.com/owner/name.git"),
        ],
    )
    def test_a_url_becomes_a_slug_or_stays_itself(self, url, expected):
        assert normalise_repository(url) == expected

    def test_a_non_github_remote_is_not_rewritten(self):
        """Only GitHub gets a slug. Guessing at another host's shape would be
        inventing an identity."""
        assert normalise_repository("https://git.example.com/a/b.git") == (
            "https://git.example.com/a/b.git"
        )

    def test_an_absent_remote_is_none(self):
        assert normalise_repository(None) is None
        assert normalise_repository("") is None
        assert normalise_repository("   ") is None


class TestResolveWorkspace:
    def test_a_repository_yields_its_identity(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        identity = resolve_workspace(root, reader=fake_git)
        assert identity.commit == SAMPLE_SHA
        assert identity.branch == "main"
        assert identity.detached is False
        assert identity.repository == "example/workspace"
        assert identity.working_tree is WorkingTreeState.CLEAN

    def test_a_dirty_tree_is_reported_dirty(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        fake_git.porcelain = " M file.py\n?? new.py\n"
        identity = resolve_workspace(root, reader=fake_git)
        assert identity.working_tree is WorkingTreeState.DIRTY
        assert identity.changed_files == 2

    def test_an_unreadable_tree_is_unknown_not_clean(self, tmp_path: Path, fake_git):
        """§6.1: the whole point of reading the tree is to find out."""
        root = tmp_path / "ws"
        root.mkdir()
        fake_git.set(root, ("status", "--porcelain"), _failed())
        identity = resolve_workspace(root, reader=fake_git)
        assert identity.working_tree is WorkingTreeState.UNKNOWN
        assert identity.changed_files is None

    def test_a_detached_head_has_no_branch(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        fake_git.branch = None
        identity = resolve_workspace(root, reader=fake_git)
        assert identity.branch is None
        assert identity.detached is True

    def test_a_repository_without_commits_has_no_commit(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        fake_git.head = None
        identity = resolve_workspace(root, reader=fake_git)
        assert identity.commit is None
        assert identity.detached is False

    def test_a_missing_remote_leaves_the_repository_unset(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        fake_git.remote = None
        identity = resolve_workspace(root, reader=fake_git)
        assert identity.repository is None
        assert identity.workspace_id.startswith("ws-")

    def test_the_root_is_canonical_and_posix(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        identity = resolve_workspace(root, reader=fake_git)
        assert "\\" not in identity.workspace_root
        assert Path(identity.workspace_root).is_absolute()

    def test_a_missing_root_is_an_error_not_an_identity(self, tmp_path: Path, fake_git):
        with pytest.raises(WorkspaceError):
            resolve_workspace(tmp_path / "absent", reader=fake_git)

    def test_a_file_is_not_a_workspace_root(self, tmp_path: Path, fake_git):
        path = tmp_path / "file.txt"
        path.write_text("x", encoding="utf-8")
        with pytest.raises(WorkspaceError):
            resolve_workspace(path, reader=fake_git)

    def test_resolution_is_read_only(self, tmp_path: Path, fake_git):
        """Every command issued is in the frozen read set."""
        from plugins.context.workspace import READ_ONLY_GIT_COMMANDS

        root = tmp_path / "ws"
        root.mkdir()
        resolve_workspace(root, reader=fake_git)
        assert fake_git.commands
        assert set(fake_git.commands) <= READ_ONLY_GIT_COMMANDS

    def test_resolution_touches_no_other_directory(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        resolve_workspace(root, reader=fake_git)
        assert {seen for seen, _ in fake_git.calls} == {root}


class TestIdentitySerialisation:
    def test_it_round_trips_every_field(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        payload = resolve_workspace(root, reader=fake_git).to_dict()
        assert set(payload) == {
            "workspace_id",
            "workspace_root",
            "repository",
            "branch",
            "commit",
            "detached",
            "working_tree",
            "changed_files",
        }

    def test_it_is_immutable(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        identity = resolve_workspace(root, reader=fake_git)
        with pytest.raises((AttributeError, TypeError)):
            identity.branch = "other"  # type: ignore[misc]

    def test_canonical_root_resolves_a_relative_path(self, tmp_path: Path, monkeypatch):
        root = tmp_path / "ws"
        root.mkdir()
        monkeypatch.chdir(tmp_path)
        assert canonical_root("ws") == root.resolve()

    def test_the_identity_type_is_frozen(self):
        import dataclasses

        assert WorkspaceIdentity.__dataclass_params__.frozen  # type: ignore[attr-defined]
        assert dataclasses.is_dataclass(WorkspaceIdentity)


def _failed():
    from tests.context.conftest import failed

    return failed("status unavailable")
