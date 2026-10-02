"""AI-11 §5.3, §5.4, §15, §16 — workspace preparation. Layer 2.

The tests that matter here are the INTEGRATION ones (`test_I*`). An earlier revision of
this module tested `verify_exclusions()` in isolation and never exercised the path that
builds the agent-visible tree — so the filter could be absent entirely and every test
still passed. These tests drive the whole lifecycle against a real git repository and
assert on what the Agent would actually be able to read.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from benchmarks.errors import WorkspaceDerivationError
from benchmarks.task import TaskDefinition
from benchmarks.workspace import (
    GENERATED_BUILDERS,
    GitResult,
    derive_source_tree,
    manifest_digest,
    prepare_workspace,
    resolve_source_sha,
    verify_exclusions,
)
from tests.benchmarks.conftest import SOURCE_SHA, valid_task_mapping

pytestmark = pytest.mark.layer2


# ---------------------------------------------------------------------------
# the live fixture repository
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _make_source_repo(tmp_path: Path) -> tuple[Path, str]:
    """A miniature SecurityLab: real files in a real git repository.

    It carries the four shapes the preparation path must distinguish: a source that
    must be withheld (the `.c`), source material that must be exported, a directory
    that must never be exported (`control/`), and an undeclared file that must not be
    exported either.
    """
    repo = tmp_path / "SecurityLab"
    (repo / "labs/reverse/arm64").mkdir(parents=True)
    (repo / "labs/yara-basic/rules").mkdir(parents=True)
    (repo / "labs/yara-basic/samples").mkdir(parents=True)
    (repo / "labs/vehicle/can-basic").mkdir(parents=True)
    (repo / "control").mkdir(parents=True)

    (repo / "labs/reverse/arm64/hello_arm64.c").write_text(
        '#include <stdio.h>\nint main(void){printf("ARM64 result = 42\\n");return 0;}\n',
        encoding="utf-8",
    )
    (repo / "labs/yara-basic/rules/demo.yar").write_text("rule demo { condition: true }\n",
                                                         encoding="utf-8")
    (repo / "labs/yara-basic/samples/sample_hit.txt").write_text("SYNMALWARE_C2_BEACON\n",
                                                                 encoding="utf-8")
    (repo / "labs/yara-basic/samples/sample_clean.txt").write_text("benign\n", encoding="utf-8")
    (repo / "labs/vehicle/can-basic/demo.dbc").write_text('BO_ 291 EngineData: 8 ECU_TEST\n',
                                                          encoding="utf-8")
    # Must never reach the workspace, and is not declared anywhere as excluded:
    # it is simply not included, and "not included" has to mean "not present".
    (repo / "UNDECLARED_SECRET.md").write_text("must not be exported\n", encoding="utf-8")
    (repo / "control/truth.json").write_text('{"answer": 42}\n', encoding="utf-8")

    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.email", "ai11@example.invalid")
    _git(repo, "config", "user.name", "AI-11 fixture")
    # A Windows checkout with autocrlf would rewrite the .c on checkout and change the
    # bytes the manifest sees; the fixture is byte-exact on purpose.
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _repo_fingerprint(repo: Path) -> dict[str, str]:
    """Everything about the source repository that must not change."""
    index = repo / ".git" / "index"
    return {
        "head": _git(repo, "rev-parse", "HEAD"),
        "refs": _git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        "status": _git(repo, "status", "--porcelain"),
        "ls_files": _git(repo, "ls-files", "-s"),
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest() if index.is_file() else "",
        "worktrees_dir": str((repo / ".git" / "worktrees").exists()),
    }


def _task_material(tmp_path: Path, task_id: str = "ai11-v1-test-fixture") -> Path:
    root = tmp_path / "corpus" / task_id
    (root / "task").mkdir(parents=True)
    (root / "task" / "frame.txt").write_text("123#1122334455667788\n", encoding="utf-8")
    (root / "control").mkdir(parents=True, exist_ok=True)
    (root / "control" / "truth.json").write_text('{"t": 1}\n', encoding="utf-8")
    return root


def _task(**overrides: object) -> TaskDefinition:
    return TaskDefinition.from_mapping(valid_task_mapping(**overrides))


def _fake_reverse_builder(source_root: Path, setup_dir: Path) -> Path:
    """Stands in for the AArch64 cross compiler, which CI does not have."""
    source = source_root / "labs/reverse/arm64/hello_arm64.c"
    assert source.is_file(), "the builder must read the .c from the SOURCE tree"
    output = setup_dir / "hello_arm64"
    output.write_bytes(b"\x7fELF fake aarch64 binary\n")
    os.chmod(output, 0o755)
    return output


# ===========================================================================
# I — integration: the lifecycle a task actually runs
# ===========================================================================


def test_I1_only_declared_include_material_reaches_the_workspace(tmp_path: Path) -> None:
    """An undeclared file in the source tree must NOT be in the workspace.

    This is the assertion an isolated `verify_exclusions()` test cannot make: it is
    about everything the filter left OUT, not about a path someone remembered to list.
    """
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc"],
            "exclude": ["control"],
            "generated": [],
        }
    )
    workspace = prepare_workspace(
        task=task, source_tree=tree, task_material_root=_task_material(tmp_path)
    )

    assert (workspace.root / "labs/vehicle/can-basic/demo.dbc").is_file()
    assert not (workspace.root / "UNDECLARED_SECRET.md").exists()
    assert not (workspace.root / "labs/reverse").exists()
    assert not (workspace.root / "labs/yara-basic").exists()


def test_I2_the_whole_source_tree_is_never_the_workspace(tmp_path: Path) -> None:
    """The source worktree exists, and it is a DIFFERENT directory."""
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc"],
            "exclude": ["control"],
            "generated": [],
        }
    )
    workspace = prepare_workspace(
        task=task, source_tree=tree, task_material_root=_task_material(tmp_path)
    )

    assert workspace.root != tree.root
    assert workspace.root == tree.workspace_dir
    assert (tree.root / "UNDECLARED_SECRET.md").is_file(), "the source tree keeps everything"
    assert not (workspace.root / "UNDECLARED_SECRET.md").exists()


def test_I3_control_is_never_present(tmp_path: Path) -> None:
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc", "task/frame.txt"],
            "exclude": ["control"],
            "generated": [],
        }
    )
    workspace = prepare_workspace(
        task=task, source_tree=tree, task_material_root=_task_material(tmp_path)
    )
    assert not (workspace.root / "control").exists()
    assert not list(workspace.root.rglob("truth.json"))
    assert not list(workspace.root.rglob("known_good.json"))
    assert not list(workspace.root.rglob("known_bad.json"))


def test_I4_task_material_reaches_the_workspace(tmp_path: Path) -> None:
    """`task/`-prefixed includes come from the corpus, not from the source."""
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    material = _task_material(tmp_path)
    task = _task(
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc", "task/frame.txt"],
            "exclude": ["control"],
            "generated": [],
        }
    )
    workspace = prepare_workspace(task=task, source_tree=tree, task_material_root=material)
    frame = workspace.root / "task/frame.txt"
    assert frame.is_file()
    assert frame.read_text(encoding="utf-8") == "123#1122334455667788\n"


def test_I5_the_reverse_task_withholds_its_source_and_gains_its_binary(
    tmp_path: Path,
) -> None:
    """§A.5, end to end. The `.c` is absent; the compiled binary is present."""
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task_id = "ai11-v1-reverse-arm64-triage"
    task = _task(
        task_id=task_id,
        workspace_setup={
            "include": ["task/frame.txt"],
            "exclude": ["control", "labs/reverse/arm64/hello_arm64.c"],
            "generated": ["work/hello_arm64"],
        },
    )
    workspace = prepare_workspace(
        task=task,
        source_tree=tree,
        task_material_root=_task_material(tmp_path),
        builders={f"{task_id}:work/hello_arm64": _fake_reverse_builder},
    )

    assert (workspace.root / "work/hello_arm64").is_file()
    assert not (workspace.root / "labs/reverse/arm64/hello_arm64.c").exists()
    assert not list(workspace.root.rglob("hello_arm64.c"))
    # And the source tree still has it, which is why the exclude had to be declared.
    assert (tree.root / "labs/reverse/arm64/hello_arm64.c").is_file()


def test_I6_a_builder_is_required_and_is_not_assumed_from_the_source(tmp_path: Path) -> None:
    """§5.4. A declared generated artifact with no builder is REFUSED.

    The failure mode this prevents is a run that silently proceeds because the artifact
    happened to be lying around at the pinned revision.
    """
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        task_id="ai11-v1-reverse-arm64-triage",
        workspace_setup={
            "include": ["task/frame.txt"],
            "exclude": ["control"],
            "generated": ["work/hello_arm64"],
        },
    )
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        prepare_workspace(
            task=task,
            source_tree=tree,
            task_material_root=_task_material(tmp_path),
            builders={},
        )
    assert "no builder is registered" in str(excinfo.value)


def test_I7_the_builder_runs_in_setup_and_not_in_the_workspace(tmp_path: Path) -> None:
    """Generated artifacts are built in `scratch/setup`, then copied in."""
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    seen: dict[str, Path] = {}

    def spy(source_root: Path, setup_dir: Path) -> Path:
        seen["source"] = source_root
        seen["setup"] = setup_dir
        out = setup_dir / "hello_arm64"
        out.write_bytes(b"fake\n")
        return out

    task_id = "ai11-v1-reverse-arm64-triage"
    task = _task(
        task_id=task_id,
        workspace_setup={"include": ["task/frame.txt"], "exclude": ["control"],
                         "generated": ["work/hello_arm64"]},
    )
    prepare_workspace(
        task=task, source_tree=tree, task_material_root=_task_material(tmp_path),
        builders={f"{task_id}:work/hello_arm64": spy},
    )

    assert seen["source"] == tree.root, "the builder reads from the SOURCE tree"
    assert seen["setup"] == tree.setup_dir
    assert tree.setup_dir != tree.workspace_dir
    assert (tree.setup_dir / "hello_arm64").is_file(), "the build lands in setup"


def test_I8_a_leaked_excluded_path_blocks_before_execution(tmp_path: Path) -> None:
    """A real leak, produced through the real path, must FAIL — not be reported.

    The leak is manufactured by making `control/` part of an INCLUDE, so the export
    genuinely places it in the workspace and the verification genuinely finds it. A test
    that called `verify_exclusions()` on a hand-built directory would prove only that
    the helper works, which is not the property under test.
    """
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    material = _task_material(tmp_path)
    task = _task(
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc", "control/truth.json"],
            "exclude": ["control"],
            "generated": [],
        }
    )
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        prepare_workspace(task=task, source_tree=tree, task_material_root=material)
    assert "withheld" in str(excinfo.value)
    assert "control" in str(excinfo.value)


def test_I9_a_missing_include_is_refused_not_skipped(tmp_path: Path) -> None:
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        workspace_setup={"include": ["labs/does/not/exist.txt"], "exclude": [], "generated": []}
    )
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        prepare_workspace(task=task, source_tree=tree, task_material_root=_task_material(tmp_path))
    assert "does not exist" in str(excinfo.value)


def test_I10_the_manifest_is_of_the_filtered_tree(tmp_path: Path) -> None:
    """Two different filters over one source produce two different digests.

    A digest taken over the source worktree would be identical for both, which is how
    the bug this test exists for would look from the outside.
    """
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    material = _task_material(tmp_path)

    narrow = prepare_workspace(
        task=_task(workspace_setup={"include": ["labs/vehicle/can-basic/demo.dbc"],
                                    "exclude": ["control"], "generated": []}),
        source_tree=tree, task_material_root=material,
    )
    narrow_digest = narrow.manifest_digest

    # Re-derive, because a run id is never reused and prepare_workspace clears the
    # workspace directory before constructing it.
    tree2 = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s2", run_id="run-fedcba9876543210"
    )
    wide = prepare_workspace(
        task=_task(workspace_setup={"include": ["labs/yara-basic/rules",
                                                "labs/vehicle/can-basic/demo.dbc"],
                                    "exclude": ["control"], "generated": []}),
        source_tree=tree2, task_material_root=material,
    )

    assert narrow_digest != wide.manifest_digest
    assert narrow.manifest_digest == manifest_digest(narrow.root)
    assert narrow.manifest_digest != manifest_digest(tree.root), (
        "the digest must not be the source worktree's"
    )


def test_I11_the_manifest_is_deterministic_across_derivations(tmp_path: Path) -> None:
    repo, sha = _make_source_repo(tmp_path)
    material = _task_material(tmp_path)
    setup = {"include": ["labs/vehicle/can-basic/demo.dbc"], "exclude": ["control"],
             "generated": []}

    digests = []
    for index, run_id in enumerate(("run-0123456789abcdef", "run-fedcba9876543210")):
        tree = derive_source_tree(
            source_root=repo, source_sha=sha, scratch_root=tmp_path / f"s{index}", run_id=run_id
        )
        digests.append(
            prepare_workspace(task=_task(workspace_setup=setup), source_tree=tree,
                              task_material_root=material).manifest_digest
        )
    assert digests[0] == digests[1]


# ===========================================================================
# S — source safety
# ===========================================================================


def test_S1_the_workspace_shares_no_inode_with_the_source(tmp_path: Path) -> None:
    """No hardlinks: a write through the workspace must not reach SecurityLab."""
    repo, sha = _make_source_repo(tmp_path)
    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        workspace_setup={"include": ["labs/vehicle/can-basic/demo.dbc"],
                         "exclude": ["control"], "generated": []}
    )
    workspace = prepare_workspace(
        task=task, source_tree=tree, task_material_root=_task_material(tmp_path)
    )

    exported = workspace.root / "labs/vehicle/can-basic/demo.dbc"
    original = tree.root / "labs/vehicle/can-basic/demo.dbc"
    assert exported.stat().st_ino != original.stat().st_ino
    if hasattr(os, "stat") and os.name != "nt":
        assert exported.stat().st_nlink == 1

    # The behavioural form of the same assertion.
    exported.write_text("mutated\n", encoding="utf-8")
    assert original.read_text(encoding="utf-8") == "BO_ 291 EngineData: 8 ECU_TEST\n"


def test_S2_the_source_repository_is_byte_identical_after_setup(tmp_path: Path) -> None:
    """§16. HEAD, refs, index and status are unchanged, and no worktree metadata appears.

    `git worktree add` against the source would create `.git/worktrees/`. That is the
    single measured fact the clone-first design exists around, and this is where it is
    checked rather than described.
    """
    repo, sha = _make_source_repo(tmp_path)
    before = _repo_fingerprint(repo)

    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task_id = "ai11-v1-reverse-arm64-triage"
    prepare_workspace(
        task=_task(
            task_id=task_id,
            workspace_setup={"include": ["task/frame.txt"],
                             "exclude": ["control", "labs/reverse/arm64/hello_arm64.c"],
                             "generated": ["work/hello_arm64"]},
        ),
        source_tree=tree,
        task_material_root=_task_material(tmp_path),
        builders={f"{task_id}:work/hello_arm64": _fake_reverse_builder},
    )

    after = _repo_fingerprint(repo)
    assert before == after
    assert before["worktrees_dir"] == "False", (
        "the source repository gained .git/worktrees; the worktree was created against "
        "the source instead of against the scratch clone"
    )


def test_S3_a_symlink_is_refused_rather_than_followed(tmp_path: Path) -> None:
    """A symlink in the exported set is a path out of the workspace."""
    repo, sha = _make_source_repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("material the task never declared\n", encoding="utf-8")
    link = repo / "labs/vehicle/can-basic/link.dbc"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows without privilege
        pytest.skip("this host cannot create a symlink")

    tree = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=tmp_path / "s", run_id="run-0123456789abcdef"
    )
    task = _task(
        workspace_setup={"include": ["labs/vehicle/can-basic/link.dbc"],
                         "exclude": ["control"], "generated": []}
    )
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        prepare_workspace(task=task, source_tree=tree, task_material_root=_task_material(tmp_path))
    assert "symlink" in str(excinfo.value)


def test_S4_an_unresolvable_sha_blocks_rather_than_falling_back(tmp_path: Path) -> None:
    """§5.3. There is no fallback to the working tree."""
    repo, _ = _make_source_repo(tmp_path)
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        derive_source_tree(
            source_root=repo, source_sha="0" * 40, scratch_root=tmp_path / "s",
            run_id="run-0123456789abcdef",
        )
    assert "precondition failure" in str(excinfo.value)


# ===========================================================================
# U — unit-level, still worth keeping
# ===========================================================================


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
            (Path(args[-1]) / ".git").mkdir(parents=True, exist_ok=True)
            return GitResult(returncode=0)
        if args[0] == "worktree":
            if not self.worktree_ok:
                return GitResult(returncode=128, stderr="invalid reference")
            worktree = Path(args[-2])
            worktree.mkdir(parents=True, exist_ok=True)
            (worktree / "README.md").write_text("derived\n", encoding="utf-8")
            return GitResult(returncode=0)
        return GitResult(returncode=0)


def test_U1_a_resolvable_sha_is_found(tmp_path: Path) -> None:
    git = FakeGit()
    assert resolve_source_sha(tmp_path, SOURCE_SHA, git=git)
    args, _ = git.calls[0]
    assert args[:3] == ["rev-parse", "--verify", "--quiet"]
    assert args[3] == f"{SOURCE_SHA}^{{commit}}"


def test_U2_an_unresolvable_sha_is_not_found(tmp_path: Path) -> None:
    assert not resolve_source_sha(tmp_path, "0" * 40, git=FakeGit(rev_parse_ok=False))


def test_U3_every_command_runs_in_scratch_or_nowhere(tmp_path: Path) -> None:
    source = tmp_path / "SecurityLab"
    source.mkdir()
    scratch = tmp_path / "scratch"
    git = FakeGit()
    derive_source_tree(
        source_root=source, source_sha=SOURCE_SHA, scratch_root=scratch,
        run_id="run-0123456789abcdef", git=git,
    )
    for argv, cwd in git.calls:
        assert cwd is None or cwd.startswith(str(scratch)), (
            f"{argv} ran with cwd={cwd}, outside the scratch root"
        )
        assert not (cwd or "").startswith(str(source))

    clone_calls = [argv for argv, _ in git.calls if argv[0] == "clone"]
    assert len(clone_calls) == 1
    assert "--no-hardlinks" in clone_calls[0]

    worktree_calls = [(argv, cwd) for argv, cwd in git.calls if argv[0] == "worktree"]
    assert len(worktree_calls) == 1
    argv, cwd = worktree_calls[0]
    assert cwd is not None and cwd.endswith("source.git")
    assert "--detach" in argv
    assert SOURCE_SHA in argv


def test_U4_a_failed_clone_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "SecurityLab"
    source.mkdir()
    with pytest.raises(WorkspaceDerivationError):
        derive_source_tree(
            source_root=source, source_sha=SOURCE_SHA, scratch_root=tmp_path / "s",
            run_id="run-0123456789abcdef", git=FakeGit(clone_ok=False),
        )


def test_U5_manifest_digest_is_deterministic_and_content_sensitive(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("two\n", encoding="utf-8")
    before = manifest_digest(tmp_path)
    assert before == manifest_digest(tmp_path)
    os.utime(tmp_path / "a.txt", (0, 0))
    assert manifest_digest(tmp_path) == before, "mtime is not part of the tree"
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    assert manifest_digest(tmp_path) != before


def test_U6_manifest_digest_refuses_a_missing_root(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceDerivationError):
        manifest_digest(tmp_path / "nope")


def test_U7_an_excluded_glob_is_refused(tmp_path: Path) -> None:
    (tmp_path / "labs").mkdir()
    (tmp_path / "labs" / "hello_arm64.c").write_text("int main(){}", encoding="utf-8")
    with pytest.raises(WorkspaceDerivationError):
        verify_exclusions(tmp_path, ["labs/*.c"])


def test_U8_the_run_id_is_not_reused(tmp_path: Path) -> None:
    """§6.2. A scratch dir that already exists is cleared, not merged into."""
    repo, sha = _make_source_repo(tmp_path)
    scratch = tmp_path / "s"
    first = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=scratch, run_id="run-0123456789abcdef"
    )
    (first.root / "STALE").write_text("from the previous run", encoding="utf-8")
    second = derive_source_tree(
        source_root=repo, source_sha=sha, scratch_root=scratch, run_id="run-0123456789abcdef"
    )
    assert not (second.root / "STALE").exists()


# ===========================================================================
# R — the shipped corpus's workspace declarations
# ===========================================================================


CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"


def test_R1_every_corpus_task_declares_a_workspace_it_could_build() -> None:
    """Structural sanity over the shipped corpus, offline."""
    from benchmarks.task import load_corpus

    for task in load_corpus(CORPUS_ROOT):
        assert task.workspace_setup.include, f"{task.task_id} includes nothing"
        assert "control" in task.workspace_setup.exclude, f"{task.task_id} does not exclude control"
        for relative in task.workspace_setup.include:
            from_source = not relative.startswith("task/")
            if from_source:
                assert (CORPUS_ROOT / task.task_id / "control").exists()
        for relative in task.workspace_setup.generated:
            assert relative in (
                "work/hello_arm64",
                "image/syn-ecu-v1.squashfs",
            ) or f"{task.task_id}:{relative}" in GENERATED_BUILDERS, (
                f"{task.task_id} declares generated {relative!r} with no registered builder"
            )


def test_R2_the_generated_artifacts_that_need_builders_have_them() -> None:
    from benchmarks.task import load_corpus

    for task in load_corpus(CORPUS_ROOT):
        for relative in task.workspace_setup.generated:
            key = f"{task.task_id}:{relative}"
            assert key in GENERATED_BUILDERS, f"{key} has no builder"


def test_R3_the_yara_held_out_corpus_exists_and_is_independent() -> None:
    """The A.3 gap is CLOSED, and closed with genuinely independent material.

    An earlier revision declared four held-out names and shipped no material for them,
    so A.3's held-out judgement could not execute. The corpus now carries the files.

    The second half is the part that matters: the negatives must be DECOYS, not blank
    files. Each carries exactly one ECU indicator, so a rule matching a single weak
    string false-positives and is caught. And none of the four is a rename of a visible
    SecurityLab sample — a held-out sample that is a copy of a visible one measures
    nothing.
    """
    import json

    task_dir = CORPUS_ROOT / "ai11-v1-yara-rule-author"
    truth = json.loads((task_dir / "control" / "truth.json").read_text("utf-8"))
    samples = truth["samples"]
    assert sorted(samples) == [
        "holdout_negative_benign", "holdout_negative_clean",
        "holdout_positive_beacon", "holdout_positive_ecu",
    ]

    contents = {}
    for key, spec in samples.items():
        path = task_dir / "control" / spec["file"]
        assert path.is_file(), f"{key} declares {spec['file']} and it does not exist"
        contents[key] = path.read_text("utf-8")

    # Not renames of the visible samples.
    visible = {
        "beacon": "SYNMALWARE_C2_BEACON callback=60 user=admin",
        "clean": "nothing malicious here, just benign text",
    }
    for key, text in contents.items():
        for name, marker in visible.items():
            assert marker not in text, (
                f"{key} contains verbatim content from the visible {name} sample; "
                "held-out material must be independent, not a rename"
            )

    # The negatives are decoys: exactly one ECU indicator each, so "2 of them" holds.
    ecu_indicators = ("AFL", "SYN-ECU", "UDS 0x10/0x11/0x22/0x27")
    for key in ("holdout_negative_benign", "holdout_negative_clean"):
        hits = sum(1 for indicator in ecu_indicators if indicator in contents[key])
        assert hits == 1, (
            f"{key} carries {hits} ECU indicators; a negative must carry exactly one so "
            "that a rule matching a single weak string is caught"
        )
        assert "SYNMALWARE_C2_BEACON" not in contents[key]
        assert "syn-c2.invalid" not in contents[key]

    # The positives carry enough to match.
    assert "SYNMALWARE_C2_BEACON" in contents["holdout_positive_beacon"]
    assert sum(1 for i in ecu_indicators if i in contents["holdout_positive_ecu"]) >= 2
