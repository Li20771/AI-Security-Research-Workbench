"""The brief's T2 — current git state, against real git.

Every other context test runs against `FakeGitReader`, which is a table the
test author wrote. This module is the one that would still pass if
`SubprocessGitReader` were wrong about how git reports things, because it runs
real `git` against real throwaway repositories.

The distinction is the whole value of the module. A fake cannot catch a wrong
assumption about `--show-toplevel`, about `symbolic-ref` on a detached HEAD, or
about what `status --porcelain` prints for an untracked file; a real repository
catches all three.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plugins.context.context import build_context
from plugins.context.sources import GitCurrentStateSource
from plugins.context.vocabulary import WorkingTreeState
from plugins.context.workspace import SubprocessGitReader, resolve_workspace


pytestmark = pytest.mark.layer2


def git_version() -> str:
    return subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()


def porcelain(root: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class TestT2CurrentGitState:
    def test_git_is_available(self):
        """The suite depends on real git; saying so beats discovering it later."""
        assert git_version().startswith("git version")

    def test_head_matches_real_git(self, throwaway_repo: Path, head_of):
        identity = resolve_workspace(throwaway_repo)
        assert identity.commit == head_of()

    def test_the_branch_is_the_real_branch(self, throwaway_repo: Path):
        assert resolve_workspace(throwaway_repo).branch == "main"

    def test_a_freshly_committed_tree_is_clean(self, throwaway_repo: Path):
        identity = resolve_workspace(throwaway_repo)
        assert identity.working_tree is WorkingTreeState.CLEAN
        assert identity.changed_files == 0

    def test_a_new_commit_moves_the_head(self, throwaway_repo: Path, commit_in, head_of):
        before = resolve_workspace(throwaway_repo).commit
        commit_in("second")
        after = resolve_workspace(throwaway_repo).commit
        assert before != after
        assert after == head_of()

    def test_an_untracked_file_makes_the_tree_dirty(self, throwaway_repo: Path):
        (throwaway_repo / "untracked.txt").write_text("x", encoding="utf-8")
        identity = resolve_workspace(throwaway_repo)
        assert identity.working_tree is WorkingTreeState.DIRTY
        assert identity.changed_files == 1

    def test_a_modified_tracked_file_makes_the_tree_dirty(
        self, throwaway_repo: Path, commit_in
    ):
        commit_in("add a file", filename="a.txt", content="one")
        assert resolve_workspace(throwaway_repo).working_tree is WorkingTreeState.CLEAN
        (throwaway_repo / "a.txt").write_text("two", encoding="utf-8")
        assert resolve_workspace(throwaway_repo).working_tree is WorkingTreeState.DIRTY

    def test_a_new_branch_changes_the_branch(self, throwaway_repo: Path):
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feature/x"],
            cwd=throwaway_repo,
            check=True,
            capture_output=True,
        )
        assert resolve_workspace(throwaway_repo).branch == "feature/x"

    def test_a_detached_head_reports_no_branch(self, throwaway_repo: Path, head_of):
        sha = head_of()
        subprocess.run(
            ["git", "checkout", "-q", sha],
            cwd=throwaway_repo,
            check=True,
            capture_output=True,
        )
        identity = resolve_workspace(throwaway_repo)
        assert identity.branch is None
        assert identity.detached is True
        assert identity.commit == sha

    def test_the_repository_slug_comes_from_the_remote(self, throwaway_repo: Path):
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/o/n.git"],
            cwd=throwaway_repo,
            check=True,
            capture_output=True,
        )
        assert resolve_workspace(throwaway_repo).repository == "o/n"

    def test_no_remote_leaves_the_repository_unset(self, throwaway_repo: Path):
        assert resolve_workspace(throwaway_repo).repository is None

    def test_identity_is_stable_across_resolutions(self, throwaway_repo: Path):
        assert (
            resolve_workspace(throwaway_repo).workspace_id
            == resolve_workspace(throwaway_repo).workspace_id
        )


class TestNoUpwardSearchAgainstRealGit:
    """`git -C <dir>` searches upward. The resolver must not inherit the result."""

    def test_a_subdirectory_does_not_borrow_the_parent_repository(
        self, throwaway_repo: Path, head_of
    ):
        inner = throwaway_repo / "tools" / "inner"
        inner.mkdir(parents=True)

        # git itself resolves this upward, which is exactly the trap.
        assert head_of(inner) == head_of(throwaway_repo)

        identity = resolve_workspace(inner)
        assert identity.commit is None
        assert identity.branch is None
        assert identity.repository is None
        assert identity.working_tree is WorkingTreeState.UNKNOWN

    def test_the_subdirectory_is_a_different_workspace(self, throwaway_repo: Path):
        inner = throwaway_repo / "inner"
        inner.mkdir()
        assert (
            resolve_workspace(throwaway_repo).workspace_id
            != resolve_workspace(inner).workspace_id
        )

    def test_a_directory_outside_any_repository_resolves_to_unknown(self, tmp_path: Path):
        plain = tmp_path / "plain"
        plain.mkdir()
        identity = resolve_workspace(plain)
        assert identity.commit is None
        assert identity.working_tree is WorkingTreeState.UNKNOWN


class TestTheSourceReadsRealGit:
    def test_the_live_state_source_matches_the_working_tree(
        self, throwaway_repo: Path, head_of
    ):
        identity = resolve_workspace(throwaway_repo)
        read = GitCurrentStateSource(SubprocessGitReader()).read(
            identity, throwaway_repo
        )
        values = {item.subject: item.value for item in read.payload}
        assert values["git.head"] == head_of()
        assert values["git.branch"] == "main"
        assert values["git.working_tree"] == "CLEAN"

    def test_the_source_reports_a_dirty_tree_after_a_real_edit(
        self, throwaway_repo: Path
    ):
        from plugins.context.workspace import SubprocessGitReader

        (throwaway_repo / "new.txt").write_text("x", encoding="utf-8")
        identity = resolve_workspace(throwaway_repo)
        read = GitCurrentStateSource(SubprocessGitReader()).read(
            identity, throwaway_repo
        )
        values = {item.subject: item.value for item in read.payload}
        assert values["git.working_tree"] == "DIRTY"


class TestTheFullPipelineTracksRealGit:
    def test_a_build_reflects_the_current_branch(self, throwaway_repo: Path):
        response = build_context(throwaway_repo)
        branch = [i for i in response.facts if i.subject == "git.branch"][0]
        assert branch.value == "main"
        assert branch.freshness.value == "CURRENT"

    def test_a_build_reflects_a_branch_change(self, throwaway_repo: Path):
        subprocess.run(
            ["git", "checkout", "-q", "-b", "feature/y"],
            cwd=throwaway_repo,
            check=True,
            capture_output=True,
        )
        response = build_context(throwaway_repo)
        branch = [i for i in response.facts if i.subject == "git.branch"][0]
        assert branch.value == "feature/y"

    def test_a_build_reflects_a_head_move(self, throwaway_repo: Path, commit_in):
        first = build_context(throwaway_repo)
        commit_in("second")
        second = build_context(throwaway_repo)
        assert first.workspace.commit != second.workspace.commit

    def test_history_is_read_from_the_real_log(self, throwaway_repo: Path, commit_in):
        commit_in("a second commit")
        response = build_context(throwaway_repo)
        values = " ".join(i.value for i in response.history)
        assert "a second commit" in values
        assert "initial" in values

    def test_the_build_is_read_only(self, throwaway_repo: Path, head_of):
        """A context build must not modify the repository it reads."""
        before = porcelain(throwaway_repo)
        before_head = head_of()
        build_context(throwaway_repo)
        assert porcelain(throwaway_repo) == before
        assert head_of() == before_head

    def test_a_directory_outside_a_repository_still_builds(self, tmp_path: Path):
        """Not a repository is an answer, not a crash."""
        plain = tmp_path / "plain"
        plain.mkdir()
        response = build_context(plain)
        assert response.workspace.commit is None
        assert response.workspace.working_tree is WorkingTreeState.UNKNOWN
        assert response.sources
