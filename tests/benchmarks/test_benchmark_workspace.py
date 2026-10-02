"""AI-11 §5.3, §15, §16 — workspace derivation and the read-only rule.

Layer 2: a fake git seam, no repository touched, nothing spawned.

The test that matters most here is `test_T8`: the source repository must never be the
working directory of a command that writes. §16 forbids AI-11 from writing into
SecurityLab, and the reason `git worktree add` is not used against the source is a
single measured fact — it writes `.git/worktrees/` into the repository it runs against.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from benchmarks.errors import WorkspaceDerivationError
from benchmarks.workspace import (
    GitResult,
    derive_workspace,
    manifest_digest,
    resolve_source_sha,
    verify_exclusions,
)

pytestmark = pytest.mark.layer2

SOURCE_SHA = "efa836ff9225f6226ca8a76615f3f45c31110d58"


class FakeGit:
    """Records every argv, and the cwd it was invoked in. Starts nothing."""

    def __init__(self, *, rev_parse_ok: bool = True, clone_ok: bool = True,
                 worktree_ok: bool = True) -> None:
        self.rev_parse_ok = rev_parse_ok
        self.clone_ok = clone_ok
        self.worktree_ok = worktree_ok
        self.calls: list[tuple[list[str], str | None]] = []

    def run(self, argv, *, cwd=None):  # noqa: ANN001, ANN201
        args = list(argv)
        self.calls.append((args, str(cwd) if cwd is not None else None))

        if args[0] == "rev-parse":
            if not self.rev_parse_ok:
                return GitResult(returncode=1, stderr="unknown revision")
            return GitResult(returncode=0, stdout=f"{SOURCE_SHA}\n")
        if args[0] == "clone":
            if not self.clone_ok:
                return GitResult(returncode=128, stderr="clone refused")
            destination = Path(args[-1])
            (destination / ".git").mkdir(parents=True, exist_ok=True)
            return GitResult(returncode=0)
        if args[0] == "worktree":
            if not self.worktree_ok:
                return GitResult(returncode=128, stderr="invalid reference")
            worktree = Path(args[-2])
            worktree.mkdir(parents=True, exist_ok=True)
            (worktree / "README.md").write_text("derived\n", encoding="utf-8")
            return GitResult(returncode=0)
        return GitResult(returncode=0)


# ---------------------------------------------------------------------------
# T1 — source sha resolution (§5.3)
# ---------------------------------------------------------------------------


def test_T1_a_resolvable_sha_is_found(tmp_path: Path) -> None:
    git = FakeGit()
    assert resolve_source_sha(tmp_path, SOURCE_SHA, git=git)
    args, _ = git.calls[0]
    assert args[:3] == ["rev-parse", "--verify", "--quiet"]
    # `^{commit}` is what makes it an existence check rather than a name check: a tag
    # spelled like a sha, or a tree object, does not satisfy it.
    assert args[3] == f"{SOURCE_SHA}^{{commit}}"


def test_T2_an_unresolvable_sha_is_not_found(tmp_path: Path) -> None:
    assert not resolve_source_sha(tmp_path, "0" * 40, git=FakeGit(rev_parse_ok=False))


# ---------------------------------------------------------------------------
# T3 — manifest digest (§5.4, §15.3)
# ---------------------------------------------------------------------------


def test_T3_manifest_digest_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("two\n", encoding="utf-8")
    assert manifest_digest(tmp_path) == manifest_digest(tmp_path)


def test_T4_manifest_digest_changes_with_content(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    before = manifest_digest(tmp_path)
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    assert manifest_digest(tmp_path) != before


@pytest.mark.skipif(
    os.name == "nt",
    reason=(
        "Windows has no executable bit: os.chmod only toggles the read-only flag and "
        "st_mode reports no S_IXUSR, so the property cannot be exercised here. The "
        "authoritative benchmark host is WSL Ubuntu (§15.1), where it is measurable"
    ),
)
def test_T5_manifest_digest_changes_with_the_executable_bit(tmp_path: Path) -> None:
    path = tmp_path / "run.sh"
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    before = manifest_digest(tmp_path)
    os.chmod(path, 0o755)
    assert manifest_digest(tmp_path) != before


def test_T6_manifest_digest_ignores_mtime(tmp_path: Path) -> None:
    """It answers "is this the same tree", not "was it copied the same way"."""
    path = tmp_path / "a.txt"
    path.write_text("one\n", encoding="utf-8")
    before = manifest_digest(tmp_path)
    os.utime(path, (0, 0))
    assert manifest_digest(tmp_path) == before


def test_T7_manifest_digest_refuses_a_missing_root(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceDerivationError):
        manifest_digest(tmp_path / "nope")


# ---------------------------------------------------------------------------
# T8 — the source is never written to (§16)
# ---------------------------------------------------------------------------


def test_T8_derivation_never_runs_a_writing_command_in_the_source(tmp_path: Path) -> None:
    """Every command runs either with no cwd or inside the scratch clone.

    `git worktree add` against the SOURCE would write `.git/worktrees/` metadata into
    it. That is the single measured fact this design exists around, and it is asserted
    rather than described.
    """
    source = tmp_path / "SecurityLab"
    source.mkdir()
    scratch = tmp_path / "scratch"

    git = FakeGit()
    derive_workspace(
        source_root=source,
        source_sha=SOURCE_SHA,
        scratch_root=scratch,
        run_id="run-0123456789abcdef",
        git=git,
    )

    source_str = str(source)
    for argv, cwd in git.calls:
        assert cwd is None or cwd.startswith(str(scratch)), (
            f"{argv} ran with cwd={cwd}, which is neither unset nor inside the scratch "
            "root; a command run against the source could write to it"
        )
        assert not (cwd or "").startswith(source_str)

    # And the one command that reads the source is a clone, which does not write to
    # what it clones.
    clone_calls = [argv for argv, _ in git.calls if argv[0] == "clone"]
    assert len(clone_calls) == 1
    assert "--no-hardlinks" in clone_calls[0], (
        "without --no-hardlinks the scratch clone shares inodes with the source, and a "
        "later gc in the scratch clone is a write to the source's objects"
    )


def test_T9_the_worktree_is_created_inside_the_clone(tmp_path: Path) -> None:
    source = tmp_path / "SecurityLab"
    source.mkdir()
    scratch = tmp_path / "scratch"
    git = FakeGit()
    derived = derive_workspace(
        source_root=source, source_sha=SOURCE_SHA, scratch_root=scratch,
        run_id="run-0123456789abcdef", git=git,
    )

    worktree_calls = [(argv, cwd) for argv, cwd in git.calls if argv[0] == "worktree"]
    assert len(worktree_calls) == 1
    argv, cwd = worktree_calls[0]
    assert cwd is not None and cwd.endswith("source.git")
    assert "--detach" in argv
    assert SOURCE_SHA in argv
    assert derived.derivation == "clone-no-hardlinks+worktree-detach"
    assert derived.manifest_digest


def test_T10_a_failed_clone_is_refused_rather_than_worked_around(tmp_path: Path) -> None:
    source = tmp_path / "SecurityLab"
    source.mkdir()
    with pytest.raises(WorkspaceDerivationError):
        derive_workspace(
            source_root=source, source_sha=SOURCE_SHA, scratch_root=tmp_path / "s",
            run_id="run-0123456789abcdef", git=FakeGit(clone_ok=False),
        )


def test_T11_an_unresolvable_sha_blocks_rather_than_falling_back(tmp_path: Path) -> None:
    """§5.3. There is no fallback to the working tree, and no "use what is there"."""
    source = tmp_path / "SecurityLab"
    source.mkdir()
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        derive_workspace(
            source_root=source, source_sha=SOURCE_SHA, scratch_root=tmp_path / "s",
            run_id="run-0123456789abcdef", git=FakeGit(worktree_ok=False),
        )
    assert "precondition failure" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T12 — exclusions are verified before execution (§15.3)
# ---------------------------------------------------------------------------


def test_T12_a_present_excluded_path_is_refused(tmp_path: Path) -> None:
    (tmp_path / "control").mkdir()
    (tmp_path / "control" / "truth.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        verify_exclusions(tmp_path, ["control"])
    assert "control" in str(excinfo.value)


def test_T13_an_excluded_glob_is_refused(tmp_path: Path) -> None:
    (tmp_path / "labs").mkdir()
    (tmp_path / "labs" / "hello_arm64.c").write_text("int main(){}", encoding="utf-8")
    with pytest.raises(WorkspaceDerivationError):
        verify_exclusions(tmp_path, ["labs/*.c"])


def test_T14_a_clean_tree_passes(tmp_path: Path) -> None:
    (tmp_path / "task").mkdir()
    (tmp_path / "task" / "input.txt").write_text("x", encoding="utf-8")
    verify_exclusions(tmp_path, ["control", "labs/reverse/**/*.c"])


def test_T15_the_run_id_is_not_reused(tmp_path: Path) -> None:
    """§6.2. A run id is created per run and never reused, so a scratch dir that
    already exists is a caller error rather than resumable state."""
    source = tmp_path / "SecurityLab"
    source.mkdir()
    scratch = tmp_path / "scratch"
    git = FakeGit()
    first = derive_workspace(
        source_root=source, source_sha=SOURCE_SHA, scratch_root=scratch,
        run_id="run-0123456789abcdef", git=git,
    )
    marker = first.root / "STALE"
    marker.write_text("from the previous run", encoding="utf-8")
    second = derive_workspace(
        source_root=source, source_sha=SOURCE_SHA, scratch_root=scratch,
        run_id="run-0123456789abcdef", git=git,
    )
    assert not (second.root / "STALE").exists()
