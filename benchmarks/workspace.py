"""AI-11 §5.3, §5.4, §15.2, §15.3, §16 — workspace preparation, and the read-only rule.

```text
FROZEN: the source repository is opened STRICTLY READ-ONLY and is never written to.
FROZEN: the workspace is created under a harness-selected scratch root OUTSIDE both the
        Workbench repository and the source repository.
FROZEN: the agent-visible tree is the derived worktree FILTERED by workspace_setup
        (§15.3). It is not the repository.
```

### The lifecycle, and why the filter is not optional

```text
    SecurityLab @ pinned source_sha
        |
        v
    scratch clone --no-hardlinks          reads the source; writes to nothing
        |
        v
    detached source worktree              the SETUP and BUILD source
        |
        v
    harness setup / build generated       artifacts land in scratch/setup
        |
        v
    construct the FILTERED tree           only declared material is copied
        |
        v
    verify exclusions                     every withheld path must be ABSENT
        |
        v
    manifest_digest(agent-visible tree)   measured over the FILTERED tree
        |
        v
    DerivedWorkspace
```

The order is the contract's and it is load-bearing. **Filter first, verify second,
manifest third.** A digest taken over the full source worktree measures a tree the Agent
never sees, and a verification that runs before the filter checks a tree that is about to
be replaced.

### Why the source worktree is not the workspace

The full SecurityLab tree holds `control/`-adjacent material, whole test suites, and — for
the reverse task — the `.c` source of the binary the Agent is asked to analyse. Handing it
to the Agent is not a leak of one answer; it is the absence of a task.

The setup tree exists for the opposite reason: a build needs the sources it builds FROM
(`labs/reverse/arm64/hello_arm64.c`, `labs/firmware/synthetic-ecu/build_fw.sh`), and those
sources must not reach the workspace that the same build's output is placed in.

### Scratch layout

```text
<scratch_root>/<run_id>/
    source.git/    the scratch clone
    source/        the detached worktree at source_sha — the build source
    setup/         build-only area: intermediate and generated artifacts
    workspace/     the FINAL agent-visible tree
```
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from benchmarks.errors import WorkspaceDerivationError
from benchmarks.paths import (
    has_glob,
    resolve_within,
    validate_exclude_pattern,
)

__all__ = [
    "GENERATED_BUILDERS",
    "TASK_MATERIAL_PREFIX",
    "Builder",
    "DerivedWorkspace",
    "GitResult",
    "GitRunner",
    "ScratchGit",
    "SourceTree",
    "derive_source_tree",
    "export_path",
    "manifest_digest",
    "prepare_workspace",
    "resolve_source_sha",
    "validate_source_root",
    "verify_exclusions",
]

#: Wall-clock ceiling for one git operation. A hung git must not hang a benchmark run.
GIT_TIMEOUT_SECONDS = 300

#: §5.4. An `include` entry under this prefix comes from the benchmark task's own
#: directory in the Workbench corpus, not from the source repository. Everything else
#: comes from the source tree.
#:
#: The convention exists because a task ships two kinds of material: the pinned source
#: it is about, and the material the task itself carries (`task/frame.txt`). Without a
#: rule, "where does this path come from" would be answered by trying both, and a path
#: that exists in both places would resolve by accident.
TASK_MATERIAL_PREFIX = "task/"


# ---------------------------------------------------------------------------
# git, and the source tree
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GitResult:
    """What one git invocation did. Never raises for a non-zero exit."""

    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class GitRunner(Protocol):
    """The git seam, so derivation can be exercised without a repository."""

    def run(self, argv: Sequence[str], *, cwd: str | None = None) -> GitResult: ...


class ScratchGit:
    """The only code in AI-11 that spawns git.

    `shell=False`, stated rather than defaulted — the same property AI-06's runner
    states for itself, for the same reason: an argv cannot become shell syntax.
    """

    def run(self, argv: Sequence[str], *, cwd: str | None = None) -> GitResult:
        completed = subprocess.run(  # noqa: S603 - argv, no shell, no user input
            ["git", *argv],
            cwd=cwd,
            capture_output=True,
            text=True,
            # A child that emits a byte outside UTF-8 kills the reader THREAD, and the
            # exception never reaches the caller: `subprocess.run` returns normally and
            # the output is silently truncated. `errors="replace"` keeps the text and
            # keeps the failure visible instead of losing it in a dead thread.
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
        return GitResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def resolve_source_sha(source_root: str | Path, source_sha: str, *, git: GitRunner) -> bool:
    """§5.3. Whether the pinned commit exists in the source repository.

    This is a PRECONDITION, not a shape check. A source_sha that does not resolve makes
    the task `BLOCKED`; it never falls back to the working tree, and the working tree is
    never read.

    `^{commit}` is what makes it an existence check rather than a name check: it asks
    for the commit object, so a tag that happens to be spelled like a sha, or a tree
    object, does not satisfy it.
    """
    result = git.run(
        ["rev-parse", "--verify", "--quiet", f"{source_sha}^{{commit}}"],
        cwd=str(source_root),
    )
    return result.ok and result.stdout.strip().startswith(source_sha)


@dataclass(frozen=True, slots=True)
class SourceTree:
    """The pinned source, checked out in scratch. **The build source, not the workspace.**

    It is handed to builders and to nothing else. An executor never sees it.
    """

    root: Path
    source_sha: str
    scratch: Path
    derivation: str

    @property
    def setup_dir(self) -> Path:
        """The build area. Outside both the source tree and the agent-visible tree."""
        return self.scratch / "setup"

    @property
    def workspace_dir(self) -> Path:
        """Where the filtered, agent-visible tree will be constructed."""
        return self.scratch / "workspace"


def validate_source_root(source_root: str | Path) -> Path:
    """Refuse a source root that cannot be read, BEFORE anything is attempted.

    ```text
    FROZEN: an invalid source MUST NOT produce a successful campaign.
    ```

    Without this, an unusable path reaches `subprocess` as a `cwd` and raises
    `NotADirectoryError`, which is neither a `BenchmarkError` nor a `CampaignError` and
    therefore escapes the runner's and the campaign's handlers as a bare traceback. The
    process still exits non-zero — so it was never a fake success — but a refusal a
    caller cannot catch and a reader cannot classify is not the honest answer this
    repository gives anywhere else.

    A path that a SHELL converted (`/d/SecurityLab` reaching Python as `D:/SecurityLab`
    from Git Bash) is a normal directory by the time it arrives, and passes here.
    """
    root = Path(source_root)
    if not root.exists():
        raise WorkspaceDerivationError(
            f"the source root {str(source_root)!r} does not exist on this host. On "
            "Windows a POSIX-style path such as /d/SecurityLab is converted by the "
            "shell that launches Python; a path that reaches Python unconverted "
            r"resolves to \d\SecurityLab and is not the repository"
        )
    if not root.is_dir():
        raise WorkspaceDerivationError(f"the source root {str(source_root)!r} is not a directory")
    return root


def derive_source_tree(
    *,
    source_root: str | Path,
    source_sha: str,
    scratch_root: str | Path,
    run_id: str,
    git: GitRunner | None = None,
) -> SourceTree:
    """§15.2. Check the pinned commit out into scratch, without writing to the source.

    The source is read by `git clone` and by nothing else. Every subsequent write lands
    in the scratch root.
    """
    runner = git if git is not None else ScratchGit()
    scratch = Path(scratch_root) / run_id
    clone = scratch / "source.git"
    source = scratch / "source"

    if scratch.exists():
        # A run id is never reused (§6.2), so a directory that already exists is a
        # caller error rather than a resumable state. It is removed rather than merged
        # into, because merging into it would mix two runs' material.
        shutil.rmtree(scratch)
    (scratch / "setup").mkdir(parents=True, exist_ok=True)

    clone_result = runner.run(
        ["clone", "--no-hardlinks", "--quiet", str(source_root), str(clone)]
    )
    if not clone_result.ok:
        raise WorkspaceDerivationError(
            f"could not clone the source read-only: {clone_result.stderr.strip()[:200]}"
        )

    worktree_result = runner.run(
        ["worktree", "add", "--detach", "--quiet", str(source), source_sha],
        cwd=str(clone),
    )
    if not worktree_result.ok:
        raise WorkspaceDerivationError(
            f"could not create a detached worktree at {source_sha}: "
            f"{worktree_result.stderr.strip()[:200]}. The pinned commit must exist in "
            "the source; a sha that does not resolve is a precondition failure (§5.3)"
        )

    return SourceTree(
        root=source,
        source_sha=source_sha,
        scratch=scratch,
        derivation="clone-no-hardlinks+worktree-detach",
    )


# ---------------------------------------------------------------------------
# generated artifacts (§5.4)
# ---------------------------------------------------------------------------


class Builder(Protocol):
    """Builds one declared `generated` artifact from the pinned source.

    It receives the SOURCE tree and the SETUP area, and returns the artifact it built.
    It is never handed the agent-visible tree: a builder that could write there could
    also leave its intermediate material there.
    """

    def __call__(self, source_root: Path, setup_dir: Path) -> Path: ...


def _run_build(argv: Sequence[str], *, cwd: Path, requires: str) -> None:
    """Run one build command, mapping a missing program to a named refusal."""
    try:
        completed = subprocess.run(  # noqa: S603 - argv, no shell, no pinned input
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise WorkspaceDerivationError(
            f"the generated artifact needs {requires}, which is not on this host "
            f"(§5.7: an unmet precondition is BLOCKED, not FAIL)"
        ) from exc
    if completed.returncode != 0:
        raise WorkspaceDerivationError(
            f"{argv[0]} failed while building a generated artifact: "
            f"{(completed.stderr or completed.stdout).strip()[:200]}"
        )


def _build_reverse_binary(source_root: Path, setup_dir: Path) -> Path:
    """§A.5. Compile `labs/reverse/arm64/hello_arm64.c` for AArch64.

    The binary is NOT in the tracked source SHA — `.gitignore:40` ignores
    `labs/reverse/**/hello_arm64` — so it is built here, and the `.c` it is built from
    is withheld from the agent-visible tree by the task's `exclude`.
    """
    source = source_root / "labs/reverse/arm64/hello_arm64.c"
    if not source.is_file():
        raise WorkspaceDerivationError(
            f"{source} is absent from the pinned source; the reverse task declares a "
            "generated artifact whose source does not exist at this revision"
        )
    output = setup_dir / "hello_arm64"
    _run_build(
        ["aarch64-linux-gnu-gcc", "-static", "-o", str(output), str(source)],
        cwd=setup_dir,
        requires="aarch64-linux-gnu-gcc",
    )
    return output


def _build_firmware_image(source_root: Path, setup_dir: Path) -> Path:
    """§A.4. Build the v1 SquashFS image with the source's own `build_fw.sh`.

    `build_fw.sh` calls `mksquashfs` without a reproducible-time flag, so the image
    digest is NOT stable across runs. The contract therefore forbids freezing it as
    truth; it is recorded, and the oracle derives its expected values from the image it
    actually has.
    """
    script = source_root / "labs/firmware/synthetic-ecu/build_fw.sh"
    if not script.is_file():
        raise WorkspaceDerivationError(
            f"{script} is absent from the pinned source; the firmware task declares a "
            "generated artifact whose builder does not exist at this revision"
        )
    _run_build(["bash", str(script), "v1"], cwd=setup_dir, requires="bash + mksquashfs")
    produced = source_root / "labs/firmware/synthetic-ecu/build/syn-ecu-v1.squashfs"
    if not produced.is_file():
        raise WorkspaceDerivationError(
            f"build_fw.sh completed and produced no image at {produced}; a declared "
            "generated artifact that nothing produces is refused rather than skipped"
        )
    output = setup_dir / "syn-ecu-v1.squashfs"
    shutil.copyfile(produced, output)
    return output


#: Builders, keyed by `<task_id>:<declared artifact path>`.
#:
#: A declared generated artifact with no entry here is a REFUSAL, not a silent skip.
#: §5.4 requires the harness to build it, and "nothing built it and the run continued"
#: is how a task quietly stops measuring what it claims to.
GENERATED_BUILDERS: Mapping[str, Builder] = {
    "ai11-v1-reverse-arm64-triage:work/hello_arm64": _build_reverse_binary,
    "ai11-v1-firmware-syn-ecu-inventory:image/syn-ecu-v1.squashfs": _build_firmware_image,
}


# ---------------------------------------------------------------------------
# manifest and exclusions
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_digest(root: str | Path) -> str:
    """§5.4, §15.3. A digest over the tree's contents and modes.

    Deterministic by construction: paths are sorted, and the digest covers the relative
    path, the executable bit and the content hash. It deliberately excludes mtimes and
    ownership, because those change when a tree is copied and the digest is supposed to
    answer "is this the same tree", not "was it copied the same way".

    Symlinks are recorded as their target rather than followed, so a link that points
    outside the tree cannot pull foreign bytes into the measurement.
    """
    base = Path(root)
    if not base.is_dir():
        raise WorkspaceDerivationError(f"{base} is not a directory")

    entries: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(base).as_posix()
            if path.is_symlink():
                entries.append(f"{rel}\0link\0{os.readlink(path)}")
            else:
                executable = "x" if path.stat().st_mode & stat.S_IXUSR else "-"
                entries.append(f"{rel}\0{executable}\0{_sha256_file(path)}")

    payload = "\n".join(entries).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_exclusions(root: str | Path, exclude: Sequence[str]) -> None:
    """§15.3. Assert every withheld path is ABSENT.

    Raises rather than warning. A run that proceeds with oracle material reachable from
    the agent-visible tree has produced a measurement that means nothing, and it has
    already spent whatever it cost to produce it.
    """
    base = Path(root).resolve()
    present: list[str] = []
    for raw in exclude:
        pattern = validate_exclude_pattern(raw, where="exclude entry")
        matches = list(base.glob(pattern)) if has_glob(pattern) else []
        if not matches:
            # Resolved, so a literal entry that leaves the tree is refused here rather
            # than compared as a string. `..` is already refused by the validator; this
            # catches a symlinked intermediate directory.
            candidate = resolve_within(base, pattern, where="exclude entry")
            if candidate.exists():
                matches = [candidate]
        present.extend(
            str(match.relative_to(base)) if match.is_relative_to(base) else str(match)
            for match in matches
        )

    if present:
        raise WorkspaceDerivationError(
            f"the agent-visible tree still holds path(s) the definition withheld: "
            f"{sorted(present)}. §15.3 requires every excluded path to be ABSENT before "
            "execution begins"
        )


# ---------------------------------------------------------------------------
# constructing the filtered tree
# ---------------------------------------------------------------------------


def _copy_file(source: Path, destination: Path) -> None:
    """Copy one file as an independent file.

    `copy2` preserves the mode — which the manifest digest covers — and never
    hardlinks, so the workspace cannot share an inode with the source. A hardlink would
    make the workspace a second name for a source file: a write through it would be a
    write to SecurityLab, which §16 forbids.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def export_path(source: Path, workspace: Path, relative: str) -> list[str]:
    """Copy one declared path (file or directory) into the agent-visible tree.

    Symlinks are REFUSED rather than followed or reproduced. A symlink in an exported
    tree is a path out of the workspace, and following one during export would pull
    content the task never declared into the tree the Agent reads. The corpus contains
    none, so a refusal costs nothing and closes the case.
    """
    if source.is_symlink():
        raise WorkspaceDerivationError(
            f"{relative} is a symlink. An exported tree must not contain one: it is a "
            "path out of the workspace, and following it would copy material the task "
            "never declared (contract §15.3)"
        )

    if source.is_file():
        _copy_file(source, resolve_within(workspace, relative, where=f"export {relative!r}"))
        return [relative]

    if not source.is_dir():
        raise WorkspaceDerivationError(f"{relative} is neither a file nor a directory")

    exported: list[str] = []
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames.sort()
        for name in sorted(filenames):
            child = Path(dirpath) / name
            child_rel = child.relative_to(source).as_posix()
            export_path(
                child,
                resolve_within(workspace, relative, where=f"export {relative!r}"),
                child_rel,
            )
            exported.append(f"{relative}/{child_rel}")
    return exported


def _resolve_include(
    relative: str, *, source_root: Path, task_material_root: Path | None
) -> Path:
    """Where one `include` entry comes from (§5.4).

    `task/`-prefixed entries come from the benchmark task's own directory — the corpus
    directory `benchmarks/tasks/<task_id>/` — and everything else comes from the pinned
    source tree. The rule is positional and total, so a path that exists in both places
    cannot resolve by accident.

    The prefix is KEPT, not stripped: the entry `task/frame.txt` lands at
    `.../benchmarks/tasks/<task_id>/task/frame.txt` and is exported to the workspace as
    `task/frame.txt`. The path the task declares is the path the Agent sees, which is
    what makes a task description that names `task/frame.txt` correct.
    """
    if relative.startswith(TASK_MATERIAL_PREFIX):
        if task_material_root is None:
            raise WorkspaceDerivationError(
                f"include entry {relative!r} is task material and no task material root "
                "was supplied"
            )
        return resolve_within(
            task_material_root, relative, where=f"include entry {relative!r}"
        )
    return resolve_within(source_root, relative, where=f"include entry {relative!r}")


@dataclass(frozen=True, slots=True)
class DerivedWorkspace:
    """The agent-visible tree, and the facts that make it reproducible.

    `root` IS the agent-visible tree. It is not the source worktree, and the manifest
    digest is measured over the filtered tree that the Agent actually reads.
    """

    root: Path
    source_sha: str
    derivation: str
    manifest_digest: str
    exported: tuple[str, ...] = ()
    generated: tuple[str, ...] = ()
    withheld: tuple[str, ...] = field(default_factory=tuple)

    def identity(self) -> Mapping[str, str]:
        """§6.1's `workspace_identity`: the workspace id and the measured manifest."""
        return {
            "workspace_id": f"ai11-{self.source_sha[:12]}",
            "manifest_digest": self.manifest_digest,
            "derivation": self.derivation,
        }


def prepare_workspace(
    *,
    task: object,
    source_tree: SourceTree,
    task_material_root: str | Path | None = None,
    builders: Mapping[str, Builder] | None = None,
) -> DerivedWorkspace:
    """§5.4, §15.3. Build the filtered, agent-visible tree.

    ```text
    filter first        only declared include material is copied
    verify second       every withheld path must be ABSENT
    manifest third      the digest is over the tree the Agent will read
    ```

    `task` is a `TaskDefinition`. It is typed loosely here only to keep this module
    importable without the task schema; its three `workspace_setup` lists are the whole
    input, and `generated` is resolved through the builder registry.
    """
    setup = task.workspace_setup  # type: ignore[attr-defined]
    task_id = task.task_id  # type: ignore[attr-defined]
    material_root = (
        Path(task_material_root) if task_material_root is not None else None
    )

    workspace = source_tree.workspace_dir
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    source_tree.setup_dir.mkdir(parents=True, exist_ok=True)

    # (1) FILTER. Only declared material is exported.
    exported: list[str] = []
    for relative in setup.include:
        origin = _resolve_include(
            relative, source_root=source_tree.root, task_material_root=material_root
        )
        if not origin.exists():
            raise WorkspaceDerivationError(
                f"include entry {relative!r} does not exist at "
                f"{origin}; a declared include that is absent is a defect in the task, "
                "not a reason to export less"
            )
        exported.extend(export_path(origin, workspace, relative))

    # (2) GENERATED. Built in the setup area, then copied in. Never assumed to exist.
    registry = GENERATED_BUILDERS if builders is None else builders
    generated: list[str] = []
    for relative in setup.generated:
        builder = registry.get(f"{task_id}:{relative}")
        if builder is None:
            raise WorkspaceDerivationError(
                f"{task_id} declares the generated artifact {relative!r} and no builder "
                "is registered for it. §5.4 requires the harness to build it; a "
                "generated artifact that nothing builds MUST NOT be assumed present in "
                "the source SHA"
            )
        built = Path(builder(source_tree.root, source_tree.setup_dir))
        if not built.exists():
            raise WorkspaceDerivationError(
                f"the builder for {task_id}:{relative} returned {built}, which does not "
                "exist; a declared generated artifact that nothing produced is refused"
            )
        destination = resolve_within(
            workspace, relative, where=f"generated artifact {relative!r}"
        )
        _copy_file(built, destination)
        generated.append(relative)

    # (3) VERIFY. Before the Agent reads anything.
    verify_exclusions(workspace, setup.exclude)

    # (4) MANIFEST. Over the filtered tree, and only now.
    return DerivedWorkspace(
        root=workspace,
        source_sha=source_tree.source_sha,
        derivation=f"{source_tree.derivation}+filtered",
        manifest_digest=manifest_digest(workspace),
        exported=tuple(sorted(exported)),
        generated=tuple(generated),
        withheld=tuple(setup.exclude),
    )
