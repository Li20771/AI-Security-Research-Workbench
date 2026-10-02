"""AI-11 §5.3, §5.4, §15.2, §15.3, §16 — workspace derivation, and the read-only rule.

```text
FROZEN: the source repository is opened STRICTLY READ-ONLY and is never written to.
FROZEN: the workspace is created under a harness-selected scratch root OUTSIDE both the
        Workbench repository and the source repository.
```

### Why the derivation clones first

The obvious mechanism is `git -C <source> worktree add`. It is refused here, and the
reason is a single measured fact: `worktree add` writes `.git/worktrees/` metadata
**into the repository it is run against**. §16 forbids AI-11 from writing into
SecurityLab's `.git`, so that command is not available however convenient it is.

```text
    1  git clone --no-hardlinks <source> <scratch>/source.git
    2  git -C <scratch>/source.git worktree add --detach <scratch>/ws <source_sha>

    The clone is the only thing that reads the source, and a clone does not write to
    what it clones. The worktree is then created inside the scratch clone, where
    writing is not merely permitted but expected.
```

`--no-hardlinks` is not decoration: with hardlinks, the scratch clone's object store
shares inodes with the source, and a later `git gc` in the scratch clone is a write to
the source's objects. The copy costs disk and buys the guarantee.

### The agent-visible tree is a derived artifact

§5.4, §15.3: the tree the Agent sees is the derived worktree **filtered** by
`workspace_setup`, and its manifest digest is measured. `verify_exclusions` asserts that
every path the definition withheld is absent BEFORE execution begins — a run that leaked
oracle material has already destroyed its own result, and the only useful moment to
notice is before the Agent reads anything.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from benchmarks.errors import WorkspaceDerivationError

__all__ = [
    "DerivedWorkspace",
    "GitResult",
    "GitRunner",
    "ScratchGit",
    "derive_workspace",
    "manifest_digest",
    "resolve_source_sha",
    "verify_exclusions",
]

#: Wall-clock ceiling for one git operation. A hung git must not hang a benchmark run.
GIT_TIMEOUT_SECONDS = 300


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
                executable = "x" if os.access(path, os.X_OK) else "-"
                entries.append(f"{rel}\0{executable}\0{_sha256_file(path)}")

    payload = "\n".join(entries).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_exclusions(root: str | Path, exclude: Sequence[str]) -> None:
    """§15.3. Assert every withheld path is ABSENT before execution begins.

    Raises rather than warning. A run that proceeds with oracle material reachable from
    the agent-visible tree has produced a measurement that means nothing, and it has
    already spent whatever it cost to produce it.
    """
    base = Path(root)
    present: list[str] = []
    for pattern in exclude:
        # A declared path may be a glob or a literal. Both are checked; a literal that
        # exists and a glob that matches anything are both leaks.
        matches = list(base.glob(pattern)) if any(ch in pattern for ch in "*?[") else []
        if not matches and (base / pattern).exists():
            matches = [base / pattern]
        present.extend(str(match.relative_to(base)) for match in matches)

    if present:
        raise WorkspaceDerivationError(
            f"the agent-visible tree still holds path(s) the definition withheld: "
            f"{sorted(present)}. §15.3 requires every excluded path to be ABSENT before "
            "execution begins"
        )


@dataclass(frozen=True, slots=True)
class DerivedWorkspace:
    """A derived, isolated workspace and the facts that make it reproducible."""

    root: Path
    source_sha: str
    derivation: str
    manifest_digest: str

    def identity(self) -> Mapping[str, str]:
        """§6.1's `workspace_identity`: the workspace id and the measured manifest."""
        return {
            "workspace_id": f"ai11-{self.source_sha[:12]}",
            "manifest_digest": self.manifest_digest,
            "derivation": self.derivation,
        }


def derive_workspace(
    *,
    source_root: str | Path,
    source_sha: str,
    scratch_root: str | Path,
    run_id: str,
    git: GitRunner | None = None,
) -> DerivedWorkspace:
    """§15.2. Derive an isolated workspace at the pinned commit.

    The source is read by `git clone` and by nothing else. Every subsequent write lands
    in the scratch root.
    """
    runner = git if git is not None else ScratchGit()
    scratch = Path(scratch_root) / run_id
    clone = scratch / "source.git"
    worktree = scratch / "ws"

    if scratch.exists():
        # A run id is never reused (§6.2), so a directory that already exists is a
        # caller error rather than a resumable state. It is removed rather than merged
        # into, because merging into it would mix two runs' material.
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    clone_result = runner.run(
        ["clone", "--no-hardlinks", "--quiet", str(source_root), str(clone)]
    )
    if not clone_result.ok:
        raise WorkspaceDerivationError(
            f"could not clone the source read-only: {clone_result.stderr.strip()[:200]}"
        )

    worktree_result = runner.run(
        ["worktree", "add", "--detach", "--quiet", str(worktree), source_sha],
        cwd=str(clone),
    )
    if not worktree_result.ok:
        raise WorkspaceDerivationError(
            f"could not create a detached worktree at {source_sha}: "
            f"{worktree_result.stderr.strip()[:200]}. The pinned commit must exist in "
            "the source; a sha that does not resolve is a precondition failure (§5.3)"
        )

    return DerivedWorkspace(
        root=worktree,
        source_sha=source_sha,
        derivation="clone-no-hardlinks+worktree-detach",
        manifest_digest=manifest_digest(worktree),
    )
