"""Workspace resolution — identity and current git state.

Implements AI-03 contract §6 and §7.4. This is A1 of the phase plan: the one
place that answers *which workspace is this, and what is its current state*.

Three properties matter more than the code that provides them.

**Read-only, structurally.** `SubprocessGitReader` refuses any command outside
the frozen set of §7.4 before a process is started. The refusal is not a
convention the callers respect; it is a check inside the only code path that
can spawn `git`. AI-03 contains no git write command, and this is where that is
enforced rather than promised.

**No discovery.** The resolver reads the root it is given. It does not read a
workspace registry, does not walk to a parent directory to find a repository,
and does not look at siblings. A root that is not itself a repository yields
`working_tree: UNKNOWN` with `branch`/`commit` of `None` — it does not trigger
a search upward, and it does not become the first workspace of a set.

**Unknown is not clean.** A working tree that could not be read is `UNKNOWN`.
Reporting it as `CLEAN` would be the most damaging possible default: the whole
point of reading it is to find out whether it is clean.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from plugins.context.errors import GitCommandRefused, WorkspaceError
from plugins.context.vocabulary import WorkingTreeState

#: The frozen read-only git command set (contract §7.4). Anything else is
#: refused before a subprocess exists.
READ_ONLY_GIT_COMMANDS: frozenset[str] = frozenset(
    {"rev-parse", "symbolic-ref", "status", "log", "remote"}
)

#: Subcommands whose read-or-write nature depends on their **first argument**,
#: and the arguments that keep them read-only.
#:
#: `git remote get-url origin` reads; `git remote add origin ...` rewrites
#: `.git/config`. Checking only the subcommand would permit the second, so the
#: guard has to look one token further. This was found by the Layer 0 check
#: refusing to accept a check it could not fail (§12.1).
READ_ONLY_GIT_ARGUMENTS: Mapping[str, frozenset[str]] = {
    "remote": frozenset({"get-url", "show", "-v", "--verbose"}),
}

#: Wall-clock ceiling for one git read. A hung git must not hang a context
#: build: a timeout is a `BLOCKED`/`UNKNOWN` read, which the caller records.
GIT_TIMEOUT_SECONDS = 20


@dataclass(frozen=True, slots=True)
class GitResult:
    """The outcome of one git invocation. Never raises for a non-zero exit."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        return self.stdout.strip()


class GitReader(Protocol):
    """The git access seam.

    A protocol rather than a concrete class so the resolver can be exercised
    without a repository, and so the read-only guard is a property of the
    production implementation rather than of the tests.
    """

    def run(self, root: Path, args: Sequence[str]) -> GitResult: ...


class SubprocessGitReader:
    """The only code in AI-03 that can spawn `git`. Read-only by construction."""

    def run(self, root: Path, args: Sequence[str]) -> GitResult:
        if not args:
            raise GitCommandRefused("empty git command")
        command = args[0]
        if command.startswith("-"):
            raise GitCommandRefused(
                f"git invoked with the option {command!r} where a command was "
                "expected; global options are supplied by this reader, not by "
                "callers, so a caller cannot smuggle one past the read-only set"
            )
        if command not in READ_ONLY_GIT_COMMANDS:
            raise GitCommandRefused(
                f"git {command!r} is not in the frozen read-only set "
                f"{sorted(READ_ONLY_GIT_COMMANDS)}; AI-03 performs no git write "
                "(contract §7.4)"
            )

        allowed_arguments = READ_ONLY_GIT_ARGUMENTS.get(command)
        if allowed_arguments is not None:
            argument = args[1] if len(args) > 1 else ""
            if argument not in allowed_arguments:
                raise GitCommandRefused(
                    f"git {command} {argument!r} is not read-only; "
                    f"git {command} permits only {sorted(allowed_arguments)} "
                    "(contract §7.4)"
                )

        # `--no-optional-locks` keeps `git status` from refreshing the index:
        # a context read must not modify the repository it is reading. The
        # environment flags do the same job for any nested invocation and stop
        # a credential prompt from blocking the build.
        environ = dict(os.environ)
        environ["GIT_OPTIONAL_LOCKS"] = "0"
        environ["GIT_TERMINAL_PROMPT"] = "0"

        try:
            completed = subprocess.run(
                ["git", "--no-pager", "--no-optional-locks", "-C", str(root), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT_SECONDS,
                env=environ,
            )
        except FileNotFoundError:
            # Recorded, not raised: a missing git is a BLOCKED read (§5.7), not
            # a defect in the workspace.
            return GitResult(returncode=127, stdout="", stderr="git not found")
        except subprocess.TimeoutExpired:
            return GitResult(returncode=124, stdout="", stderr="git timed out")

        return GitResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


#: Every GitHub remote spelling git itself accepts:
#: `https://github.com/O/N(.git)`, `ssh://git@github.com/O/N(.git)`, and the
#: scp-like `git@github.com:O/N(.git)`. The last one is the form `git remote
#: get-url` returns for an SSH clone, which is the common case on a developer
#: machine, so missing it would leave most real workspaces with a raw URL.
_GITHUB_URL = re.compile(
    r"^(?:(?:https?://|ssh://git@)github\.com/|git@github\.com:)"
    r"(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$"
)


def normalise_repository(url: str | None) -> str | None:
    """`owner/name` for a GitHub remote, else the URL unchanged, else `None`."""
    if url is None:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    match = _GITHUB_URL.match(candidate)
    if match is not None:
        return match.group("slug")
    return candidate


def workspace_id_for(root: Path, repository: str | None) -> str:
    """Deterministic workspace identity (contract §6.2).

    Inputs are the canonical root and the repository identity and nothing else,
    so the id is stable across runs and across machines that see the same
    workspace. Two different roots -- or one root under two repositories --
    have two different ids, which is what makes workspace isolation checkable
    rather than merely intended.
    """
    digest = hashlib.sha256()
    digest.update(root.as_posix().encode("utf-8"))
    digest.update(b"\x00")
    digest.update((repository or "").encode("utf-8"))
    return "ws-" + digest.hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class WorkspaceIdentity:
    """Which workspace this is, and what state it is in (contract §6.1)."""

    workspace_id: str
    workspace_root: str
    repository: str | None
    branch: str | None
    commit: str | None
    detached: bool
    working_tree: WorkingTreeState
    changed_files: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "workspace_root": self.workspace_root,
            "repository": self.repository,
            "branch": self.branch,
            "commit": self.commit,
            "detached": self.detached,
            "working_tree": str(self.working_tree),
            "changed_files": self.changed_files,
        }


def canonical_root(root: Path | str) -> Path:
    """The absolute, symlink-resolved workspace root (contract §6.3)."""
    path = Path(root)
    if not path.exists():
        raise WorkspaceError(f"workspace root does not exist: {path}")
    if not path.is_dir():
        raise WorkspaceError(f"workspace root is not a directory: {path}")
    return path.resolve()


def _same_path(left: Path, right: Path) -> bool:
    """Compare two paths for identity, tolerating platform spelling.

    Windows paths are case-insensitive and `git` may report a drive letter or
    separator style that differs from `Path.resolve()`, so a raw string compare
    would report "not the same directory" for the same directory.
    """
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
        os.path.normpath(str(right))
    )


def _is_own_repository(root: Path, reader: GitReader) -> bool:
    """Whether `root` is itself a repository root, not a directory inside one.

    `git -C <dir>` searches *upward* for a repository. Left unchecked, that
    search is workspace discovery by another name: resolving `repo/tools/git`
    would report `repo`'s branch and commit under `repo/tools/git`'s workspace
    id, producing an identity that refers to two different things at once
    (contract §6.4).
    """
    toplevel = reader.run(root, ("rev-parse", "--show-toplevel"))
    if not toplevel.ok or not toplevel.text:
        return False
    try:
        reported = Path(toplevel.text).resolve()
    except OSError:  # pragma: no cover - defensive
        return False
    return _same_path(reported, root)


def _unresolved(canonical: Path) -> WorkspaceIdentity:
    """The identity of a directory that is not its own repository.

    Every field that could carry a borrowed value is `None` or `UNKNOWN`. No
    field is inherited from an enclosing repository.
    """
    return WorkspaceIdentity(
        workspace_id=workspace_id_for(canonical, None),
        workspace_root=canonical.as_posix(),
        repository=None,
        branch=None,
        commit=None,
        detached=False,
        working_tree=WorkingTreeState.UNKNOWN,
        changed_files=None,
    )


def _read_working_tree(
    root: Path, reader: GitReader
) -> tuple[WorkingTreeState, int | None]:
    result = reader.run(root, ("status", "--porcelain"))
    if not result.ok:
        # Unreadable is not clean (§6.1).
        return WorkingTreeState.UNKNOWN, None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return WorkingTreeState.CLEAN, 0
    return WorkingTreeState.DIRTY, len(lines)


def resolve_workspace(
    root: Path | str,
    *,
    reader: GitReader | None = None,
) -> WorkspaceIdentity:
    """Resolve one workspace's identity and current git state.

    Reads only `root`. A root that is not **its own** repository root -- inside
    a repository rather than at its top, or outside any repository -- produces
    an identity with `working_tree: UNKNOWN` and `branch`/`commit` of `None`
    rather than an exception or a borrowed value. "This directory is not a
    repository of its own" is an answer, and the caller needs to record it.
    """
    canonical = canonical_root(root)
    git = SubprocessGitReader() if reader is None else reader

    if not _is_own_repository(canonical, git):
        return _unresolved(canonical)

    remote = git.run(canonical, ("remote", "get-url", "origin"))
    repository = normalise_repository(remote.text) if remote.ok else None

    head = git.run(canonical, ("rev-parse", "HEAD"))
    commit = head.text if head.ok and head.text else None

    # `symbolic-ref -q` exits non-zero on a detached HEAD, which is the
    # detached signal itself rather than a failure to report.
    symbolic = git.run(canonical, ("symbolic-ref", "--short", "-q", "HEAD"))
    if symbolic.ok and symbolic.text:
        branch: str | None = symbolic.text
        detached = False
    else:
        branch = None
        detached = commit is not None

    working_tree, changed = _read_working_tree(canonical, git)

    return WorkspaceIdentity(
        workspace_id=workspace_id_for(canonical, repository),
        workspace_root=canonical.as_posix(),
        repository=repository,
        branch=branch,
        commit=commit,
        detached=detached,
        working_tree=working_tree,
        changed_files=changed,
    )


def is_inside(root: Path, candidate: Path) -> bool:
    """Whether `candidate`, once resolved, is inside `root` (contract §6.3).

    Resolution is what makes this a containment check rather than a string
    comparison: a symlink pointing out of the workspace resolves outside it and
    is refused with it.
    """
    try:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve()
    except OSError:  # pragma: no cover - resolve() rarely raises on Windows
        return False
    return resolved_candidate == resolved_root or resolved_root in resolved_candidate.parents


__all__ = [
    "GIT_TIMEOUT_SECONDS",
    "READ_ONLY_GIT_COMMANDS",
    "GitReader",
    "GitResult",
    "SubprocessGitReader",
    "WorkspaceIdentity",
    "canonical_root",
    "is_inside",
    "normalise_repository",
    "resolve_workspace",
    "workspace_id_for",
]
