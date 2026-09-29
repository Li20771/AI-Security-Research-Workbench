"""Source adapters and the default manifest.

Implements AI-03 contract §7. This is A2 of the phase plan: reading one
workspace's declared context sources and reporting, per source, what was read
and at which revision.

Two design points carry most of the weight.

**A failed read is a recorded outcome, not an exception.** `MISSING`,
`UNREADABLE`, `REFUSED` and `BLOCKED` are values a source returns. A build that
raised on a missing document would tell its caller nothing about which source
was absent, and the caller would have no way to record the gap.

**Containment is checked before the read, not after.** Every source path is
resolved against the workspace root and refused if it escapes, so a manifest
entry cannot reach another workspace even if it names one. This is what makes
workspace isolation structural rather than conventional (§6.3, §3.6).

### What is cached, and what deliberately is not

`probe_revision` returns the cheap identity of what a read *would* return, and
it is what the cache keys on. Three cases:

    git_history        HEAD sha           cached -- a log read is the expensive one
    documents          content digest     cached -- the digest is what makes it sound
    git_current_state  ** not cached **   no cheap probe is correct

The live-state source is deliberately uncached (D-14). Its payload includes the
working tree, which changes without HEAD changing, so every cheap probe for it
-- HEAD, `rev-parse`, mtime -- would serve a `CLEAN` tree after the tree became
`DIRTY`. A cache that is wrong about the working tree is worse than no cache,
and "the cache is never a source of truth" is only true if the probe that
confirms a hit is actually sound.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from plugins.context.classification import RawItem
from plugins.context.declarations import extract_declarations
from plugins.context.errors import ContainmentError, ManifestError
from plugins.context.vocabulary import SourceKind, SourceReadStatus, WorkingTreeState
from plugins.context.workspace import (
    GitReader,
    SubprocessGitReader,
    WorkspaceIdentity,
    is_inside,
)

#: The default manifest's document bindings (contract §7.2), reviewed like code
#: (D-1). Which documents constitute a workspace's context is a reviewed
#: decision: a source that silently appears or disappears changes what the
#: agent believes about its own project.
MASTER_ROADMAP_PATH = "docs/MASTER_ROADMAP.md"
CAPABILITY_INVENTORY_PATH = "docs/PROJECT_STATUS.md"
DESIGN_FREEZE_PATH = "docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md"
EXIT_REPORT_GLOB = "docs/*_CLOSEOUT_*.md"

#: How many historical commits `git_history` reads (Q-1). Bounded and declared,
#: because an unbounded `git log` on a large repository is a latency bug that
#: looks like a feature.
HISTORY_COMMIT_LIMIT = 20

#: Field separator for the log format. A control character, so a commit subject
#: cannot collide with it.
_LOG_SEPARATOR = "\x1f"


@dataclass(frozen=True, slots=True)
class SourceRead:
    """What one source produced (contract §7.1).

    Attributes:
        status: the §5.7 read outcome. `READ` is the only status that may carry
            a payload; every other status carries an empty one.
        source_revision: the revision read, or `None` when none was
            established. `None` means the read cannot be cached, because a
            cache key needs a revision to confirm against.
        payload: the claims read, or empty when nothing was read.
        note: why a non-`READ` status occurred. Recorded, never inferred.
    """

    status: SourceReadStatus
    source_revision: str | None
    payload: tuple[RawItem, ...]
    note: str | None = None

    def __post_init__(self) -> None:
        if self.status is not SourceReadStatus.READ and self.payload:
            raise ManifestError(
                f"a {self.status} read must not carry a payload; a source that "
                "was not read is never reported as read with content (§5.7)"
            )

    @classmethod
    def unread(cls, status: SourceReadStatus, note: str) -> "SourceRead":
        return cls(status=status, source_revision=None, payload=(), note=note)


class SourceAdapter(Protocol):
    """One context source (contract §7.1)."""

    kind: SourceKind

    def identity(self) -> str:
        """Stable identity of the thing read, within the workspace."""
        ...

    def probe_revision(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        """The cheap revision identity used to key the cache, or `None`.

        `None` means "this source cannot be soundly cached" and is a deliberate
        answer, not a missing implementation.
        """
        ...

    def revision_now(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        """The revision this source would be read at right now.

        Used only for the §10 end-of-build freshness comparison, which is a
        **different question** from `probe_revision`. A freshness probe may be
        weaker than a cache probe, because a mismatch only downgrades freshness
        — the fail-safe direction — whereas a wrong cache key serves a stale
        payload as current. A source may therefore be uncacheable and still
        report a definite freshness.
        """
        ...

    def read(self, workspace: WorkspaceIdentity, root: Path) -> SourceRead:
        ...


class _Base:
    """Shared plumbing. Not a `SourceAdapter`; it declares no `kind`."""

    def __init__(self, kind: SourceKind, identity: str) -> None:
        if not identity:
            raise ManifestError("a source identity must not be empty")
        self.kind = kind
        self._identity = identity

    def identity(self) -> str:
        return self._identity

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{type(self).__name__}({self.kind}, {self._identity!r})"


# --------------------------------------------------------------------------
# git sources
# --------------------------------------------------------------------------


class GitCurrentStateSource(_Base):
    """P0 -- the live state of the workspace repository (contract §7.4).

    Never cached (D-14): its payload includes the working tree, and no cheap
    probe captures the working tree.
    """

    def __init__(self, reader: GitReader) -> None:
        super().__init__(SourceKind.GIT_CURRENT_STATE, "git")
        self._reader = reader

    def probe_revision(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        return None

    def revision_now(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        # HEAD, because HEAD is what `read` records as the revision. The working
        # tree is not revision-tracked and no cheap probe captures it; that is
        # exactly why this source is never cached (D-14), so a second build
        # always re-reads the tree rather than trusting a probe about it.
        head = self._reader.run(root, ("rev-parse", "HEAD"))
        return head.text if head.ok and head.text else None

    def read(self, workspace: WorkspaceIdentity, root: Path) -> SourceRead:
        head = self._reader.run(root, ("rev-parse", "HEAD"))
        if not head.ok or not head.text:
            return SourceRead.unread(
                SourceReadStatus.BLOCKED,
                f"HEAD could not be read: {(head.stderr or 'not a git repository').strip()}",
            )
        commit = head.text

        symbolic = self._reader.run(root, ("symbolic-ref", "--short", "-q", "HEAD"))
        branch = symbolic.text if symbolic.ok and symbolic.text else None

        status = self._reader.run(root, ("status", "--porcelain"))
        if not status.ok:
            # Unreadable is not clean (§6.1). The item says UNKNOWN.
            tree = WorkingTreeState.UNKNOWN
            changed: int | None = None
        else:
            lines = [line for line in status.stdout.splitlines() if line.strip()]
            tree = WorkingTreeState.CLEAN if not lines else WorkingTreeState.DIRTY
            changed = len(lines)

        items = [
            RawItem(subject="git.head", value=commit),
            RawItem(subject="git.detached", value="TRUE" if branch is None else "FALSE"),
            RawItem(subject="git.working_tree", value=str(tree)),
        ]
        if branch is not None:
            items.append(RawItem(subject="git.branch", value=branch))
        if workspace.repository is not None:
            items.append(RawItem(subject="git.repository", value=workspace.repository))
        if changed is not None:
            items.append(RawItem(subject="git.changed_files", value=str(changed)))

        return SourceRead(
            status=SourceReadStatus.READ,
            source_revision=commit,
            payload=tuple(items),
            note=None,
        )


class GitHistorySource(_Base):
    """P5 -- commits that have already happened (contract §7.4).

    Cacheable: `git log` from HEAD is a function of HEAD, and HEAD is the
    probe. A history read is also the expensive one, which is where a cache
    earns its keep.
    """

    def __init__(self, reader: GitReader, limit: int = HISTORY_COMMIT_LIMIT) -> None:
        super().__init__(SourceKind.GIT_HISTORY, "git:history")
        if limit <= 0:
            raise ManifestError(f"history limit must be > 0; got {limit}")
        self._reader = reader
        self._limit = limit

    @property
    def limit(self) -> int:
        return self._limit

    def _head(self, root: Path) -> str | None:
        result = self._reader.run(root, ("rev-parse", "HEAD"))
        return result.text if result.ok and result.text else None

    def probe_revision(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        return self._head(root)

    def revision_now(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        return self._head(root)

    def read(self, workspace: WorkspaceIdentity, root: Path) -> SourceRead:
        revision = self._head(root)
        if revision is None:
            return SourceRead.unread(
                SourceReadStatus.BLOCKED, "HEAD could not be read; history unavailable"
            )

        fmt = _LOG_SEPARATOR.join(("%H", "%cI", "%s"))
        result = self._reader.run(
            root, ("log", f"--max-count={self._limit}", f"--format={fmt}")
        )
        if not result.ok:
            return SourceRead.unread(
                SourceReadStatus.BLOCKED,
                f"git log failed: {(result.stderr or 'unknown error').strip()}",
            )

        items: list[RawItem] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(_LOG_SEPARATOR)
            if len(parts) != 3:
                # A line that does not match the requested format is skipped
                # rather than guessed at.
                continue
            sha, committed_at, subject = parts
            items.append(
                RawItem(subject=f"git.commit.{sha}", value=f"{committed_at} {subject}")
            )

        return SourceRead(
            status=SourceReadStatus.READ,
            source_revision=revision,
            payload=tuple(items),
            note=f"most recent {self._limit} commits",
        )


# --------------------------------------------------------------------------
# document sources
# --------------------------------------------------------------------------


class DocumentSource(_Base):
    """A document read through the §7.3 declared-state extraction.

    Its revision is the SHA-256 of the content read (D-3), not the workspace
    commit. The digest answers the question the cache actually asks -- *is this
    the same document?* -- whereas the commit would make an uncommitted edit
    invisible and an unrelated commit invalidate every document at once.
    """

    def __init__(self, kind: SourceKind, relative_path: str) -> None:
        super().__init__(kind, relative_path.replace("\\", "/"))
        self._relative_path = self._identity

    @property
    def relative_path(self) -> str:
        return self._relative_path

    def _resolve(self, root: Path) -> tuple[Path | None, SourceRead | None]:
        """Resolve the path, or return the refusal that replaces it (§6.3)."""
        try:
            candidate = root / self._relative_path
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            return None, SourceRead.unread(
                SourceReadStatus.REFUSED, f"path could not be composed: {exc}"
            )
        if not is_inside(root, candidate):
            return None, SourceRead.unread(
                SourceReadStatus.REFUSED,
                f"{self._relative_path!r} resolves outside the workspace root; "
                "a context source never reaches another workspace",
            )
        return candidate, None

    def probe_revision(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        return self.revision_now(workspace, root)

    def revision_now(self, workspace: WorkspaceIdentity, root: Path) -> str | None:
        path, refusal = self._resolve(root)
        if refusal is not None or path is None:
            return None
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None

    def read(self, workspace: WorkspaceIdentity, root: Path) -> SourceRead:
        path, refusal = self._resolve(root)
        if refusal is not None or path is None:
            return refusal if refusal is not None else SourceRead.unread(
                SourceReadStatus.REFUSED, "path could not be resolved"
            )

        if not path.exists():
            return SourceRead.unread(
                SourceReadStatus.MISSING, f"{self._relative_path} does not exist"
            )
        if not path.is_file():
            return SourceRead.unread(
                SourceReadStatus.UNREADABLE, f"{self._relative_path} is not a file"
            )

        try:
            raw = path.read_bytes()
        except OSError as exc:
            return SourceRead.unread(
                SourceReadStatus.UNREADABLE, f"{self._relative_path}: {exc}"
            )

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            return SourceRead.unread(
                SourceReadStatus.UNREADABLE, f"{self._relative_path} is not UTF-8: {exc}"
            )

        declarations = extract_declarations(text)
        payload = tuple(
            RawItem(
                subject=declaration.subject,
                value=declaration.declared_state,
                declared_state=declaration.declared_state,
            )
            for declaration in declarations
        )

        return SourceRead(
            status=SourceReadStatus.READ,
            source_revision=hashlib.sha256(raw).hexdigest(),
            payload=payload,
            note=f"{len(payload)} declared state(s)",
        )


# --------------------------------------------------------------------------
# the default manifest
# --------------------------------------------------------------------------


def build_manifest(root: Path, reader: GitReader) -> tuple[SourceAdapter, ...]:
    """The default source manifest (contract §7.2), expanded against `root`.

    The exit-report row is a glob, expanded here into one adapter per matched
    file so that every report keeps its own identity and revision. When the
    glob matches nothing, one adapter is still returned, so the row is visibly
    accounted for as `MISSING` rather than silently absent: P4 having no
    members is a fact about the workspace, and a source list that quietly
    omitted it would hide that.

    The priority table is **not** configurable. A manifest chooses which
    documents to read; it cannot reorder §5.3.
    """
    sources: list[SourceAdapter] = [
        GitCurrentStateSource(reader),
        DocumentSource(SourceKind.MASTER_ROADMAP, MASTER_ROADMAP_PATH),
        DocumentSource(SourceKind.CAPABILITY_INVENTORY, CAPABILITY_INVENTORY_PATH),
        DocumentSource(SourceKind.DESIGN_FREEZE, DESIGN_FREEZE_PATH),
    ]

    matched = sorted(
        path
        for path in root.glob(EXIT_REPORT_GLOB)
        if path.is_file() and is_inside(root, path)
    )
    if matched:
        for path in matched:
            sources.append(
                DocumentSource(
                    SourceKind.EXIT_REPORT, path.relative_to(root).as_posix()
                )
            )
    else:
        sources.append(DocumentSource(SourceKind.EXIT_REPORT, EXIT_REPORT_GLOB))

    sources.append(GitHistorySource(reader))
    return tuple(sources)


def manifest_identities(sources: Sequence[SourceAdapter]) -> tuple[tuple[str, str], ...]:
    """`(source_kind, identity)` pairs, sorted. Used to report a manifest."""
    return tuple(sorted((str(source.kind), source.identity()) for source in sources))


__all__ = [
    "CAPABILITY_INVENTORY_PATH",
    "DESIGN_FREEZE_PATH",
    "EXIT_REPORT_GLOB",
    "HISTORY_COMMIT_LIMIT",
    "MASTER_ROADMAP_PATH",
    "DocumentSource",
    "GitCurrentStateSource",
    "GitHistorySource",
    "SourceAdapter",
    "SourceRead",
    "build_manifest",
    "manifest_identities",
]
