"""Context assembly — the `ContextResponse`.

Implements AI-03 contract §4.1 of the brief and §10–§11 of this plan. This is
A5, the integration step that turns per-source reads into one workspace-scoped
structure.

```text
ContextResponse
├── workspace     who this is about            (one workspace, never two)
├── facts         what is true now             (FACT items only)
├── history       what has happened            (HISTORY items only)
├── plans         what is intended             (PLAN items only)
├── sources       what was read, and at which revision
├── freshness     how current any of it is
├── status        whether the declared sources could be read
└── conflicts     every contested subject, resolved      (D-11)
```

The three item lists are separate and stay separate. A `PLAN` cannot appear in
`facts`, because `facts` is built from `ITEM_KIND_BY_SOURCE` (FACT) and nothing
else; there is no filter to get wrong, only a partition that cannot overlap.

`conflicts` is an eighth member beyond the seven the brief's conceptual model
lists. The brief separately requires deterministic conflict resolution, and a
resolution that is not recorded is not auditable (D-11). Nothing in the seven
is removed or renamed.

**Workspace consistency is asserted, not assumed.** Every item and every source
record must carry the response's `workspace_id`. Merging two workspaces would
produce a response that is wrong in a way no consumer could detect, so it
raises rather than being absorbed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from plugins.context.cache import CacheEntry, CacheKey, InMemoryContextCache
from plugins.context.classification import ContextItem, classify
from plugins.context.errors import WorkspaceMismatchError
from plugins.context.resolution import (
    SubjectResolution,
    apply_resolution,
    resolve_conflicts,
    sort_items,
)
from plugins.context.sources import SourceAdapter, SourceRead, build_manifest
from plugins.context.vocabulary import (
    ContextStatus,
    Freshness,
    ItemKind,
    SourceKind,
    SourceReadStatus,
    most_severe_freshness,
    source_priority,
)
from plugins.context.workspace import (
    GitReader,
    SubprocessGitReader,
    WorkspaceIdentity,
    canonical_root,
    resolve_workspace,
)

Clock = Callable[[], str]


def utc_now() -> str:
    """ISO-8601 UTC with a `Z` suffix. Second resolution."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True, slots=True)
class FreshnessSummary:
    """Per-value counts plus the §10.3 overall value."""

    current: int
    stale: int
    unknown: int
    overall: Freshness

    @classmethod
    def of(cls, values: Sequence[Freshness]) -> "FreshnessSummary":
        return cls(
            current=sum(1 for value in values if value is Freshness.CURRENT),
            stale=sum(1 for value in values if value is Freshness.STALE),
            unknown=sum(1 for value in values if value is Freshness.UNKNOWN),
            overall=most_severe_freshness(values),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "current": self.current,
            "stale": self.stale,
            "unknown": self.unknown,
            "overall": str(self.overall),
        }


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """What was read from one source (contract §7.1, §5.7).

    `read_status` is the point of this record: without it, a document that
    failed to read and a document that declared nothing are indistinguishable,
    and the second is a `PASS`-shaped silence (D-12).
    """

    workspace_id: str
    source_kind: SourceKind
    source_identity: str
    source_revision: str | None
    retrieved_at: str
    read_status: SourceReadStatus
    freshness: Freshness
    item_count: int
    cache_hit: bool
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
            "retrieved_at": self.retrieved_at,
            "read_status": str(self.read_status),
            "freshness": str(self.freshness),
            "item_count": self.item_count,
            "cache_hit": self.cache_hit,
            "note": self.note,
        }

    @property
    def priority(self) -> int:
        return int(source_priority(self.source_kind))


@dataclass(frozen=True, slots=True)
class ContextResponse:
    """One workspace's context (contract §4.1 of the brief)."""

    workspace: WorkspaceIdentity
    facts: tuple[ContextItem, ...]
    history: tuple[ContextItem, ...]
    plans: tuple[ContextItem, ...]
    sources: tuple[SourceRecord, ...]
    freshness: FreshnessSummary
    status: ContextStatus
    conflicts: tuple[SubjectResolution, ...]
    retrieved_at: str

    @property
    def items(self) -> tuple[ContextItem, ...]:
        """Every item, in `facts`/`history`/`plans` order."""
        return self.facts + self.history + self.plans

    def items_of_kind(self, kind: ItemKind) -> tuple[ContextItem, ...]:
        return tuple(item for item in self.items if item.item_kind is kind)

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace": self.workspace.to_dict(),
            "retrieved_at": self.retrieved_at,
            "status": str(self.status),
            "freshness": self.freshness.to_dict(),
            "facts": [item.to_dict() for item in self.facts],
            "history": [item.to_dict() for item in self.history],
            "plans": [item.to_dict() for item in self.plans],
            "sources": [record.to_dict() for record in self.sources],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }


def assert_same_workspace(
    workspace_id: str,
    items: Sequence[ContextItem],
    records: Sequence[SourceRecord],
) -> None:
    """Refuse to merge two workspaces' context (contract §6).

    Raises rather than filtering. A dropped foreign item would leave a response
    that silently omits something; a raised error names the mismatch.
    """
    for item in items:
        if item.workspace_id != workspace_id:
            raise WorkspaceMismatchError(
                f"item {item.subject!r} carries workspace {item.workspace_id!r} "
                f"but the response is for {workspace_id!r}"
            )
    for record in records:
        if record.workspace_id != workspace_id:
            raise WorkspaceMismatchError(
                f"source {record.source_identity!r} carries workspace "
                f"{record.workspace_id!r} but the response is for {workspace_id!r}"
            )


def _freshness_for(read_revision: str | None, current_revision: str | None) -> Freshness:
    """§10.1. An unestablished revision on either side is `UNKNOWN`."""
    if read_revision is None or current_revision is None:
        return Freshness.UNKNOWN
    if read_revision == current_revision:
        return Freshness.CURRENT
    # STALE != WRONG (§10.2): it says only that nothing currently shows this to
    # still be the newest state.
    return Freshness.STALE


def _read_one(
    adapter: SourceAdapter,
    workspace: WorkspaceIdentity,
    root: Path,
    cache: InMemoryContextCache,
    retrieved_at: str,
) -> tuple[SourceRead, bool]:
    """Read one source, through the cache when the source is cacheable.

    Returns the read and whether it came from a confirmed-revision cache entry.
    """
    probe = adapter.probe_revision(workspace, root)
    if probe is None:
        # Not cacheable. `probe_revision` returning None is a deliberate answer
        # (D-14), not a missing implementation: an unsound probe would let the
        # cache serve a stale payload as current, which is the one thing the
        # cache must never do.
        return adapter.read(workspace, root), False

    key = CacheKey(
        workspace_id=workspace.workspace_id,
        source_kind=adapter.kind,
        source_identity=adapter.identity(),
        source_revision=probe,
    )
    lookup = cache.lookup(key)
    if lookup.is_hit and lookup.entry is not None:
        return (
            SourceRead(
                status=SourceReadStatus.READ,
                source_revision=probe,
                payload=lookup.entry.payload,
                note="cache hit",
            ),
            True,
        )

    read = adapter.read(workspace, root)
    if read.status is SourceReadStatus.READ and read.source_revision is not None:
        cache.put(
            CacheEntry(
                key=CacheKey(
                    workspace_id=workspace.workspace_id,
                    source_kind=adapter.kind,
                    source_identity=adapter.identity(),
                    source_revision=read.source_revision,
                ),
                retrieved_at=retrieved_at,
                payload=read.payload,
            )
        )
    return read, False


def build_context(
    root: Path | str,
    *,
    manifest: Sequence[SourceAdapter] | None = None,
    reader: GitReader | None = None,
    cache: InMemoryContextCache | None = None,
    clock: Clock | None = None,
) -> ContextResponse:
    """Build one workspace's context (contract §3.3).

    Reads only `root`. A source that cannot be read is recorded and the build
    continues: a partial context is more useful than none, provided it is
    labelled `PARTIAL` (§7.5).
    """
    canonical = canonical_root(root)
    git = SubprocessGitReader() if reader is None else reader
    workspace = resolve_workspace(canonical, reader=git)
    adapters = build_manifest(canonical, git) if manifest is None else tuple(manifest)
    store = InMemoryContextCache() if cache is None else cache
    now: Clock = utc_now if clock is None else clock
    retrieved_at = now()

    reads: list[tuple[SourceAdapter, SourceRead, bool]] = []
    for adapter in adapters:
        read, from_cache = _read_one(adapter, workspace, canonical, store, retrieved_at)
        reads.append((adapter, read, from_cache))

    # Freshness is decided against the state of the world *after* the reads, so
    # a workspace that moved mid-build reports STALE rather than CURRENT.
    items: list[ContextItem] = []
    records: list[SourceRecord] = []
    for adapter, read, from_cache in reads:
        current_revision = (
            adapter.revision_now(workspace, canonical)
            if read.status is SourceReadStatus.READ
            else None
        )
        freshness = _freshness_for(read.source_revision, current_revision)
        for raw in read.payload:
            items.append(
                classify(
                    raw,
                    source_kind=adapter.kind,
                    source_identity=adapter.identity(),
                    source_revision=read.source_revision,
                    retrieved_at=retrieved_at,
                    workspace_id=workspace.workspace_id,
                    freshness=freshness,
                    cache_hit=from_cache,
                )
            )
        records.append(
            SourceRecord(
                workspace_id=workspace.workspace_id,
                source_kind=adapter.kind,
                source_identity=adapter.identity(),
                source_revision=read.source_revision,
                retrieved_at=retrieved_at,
                read_status=read.status,
                freshness=freshness,
                item_count=len(read.payload),
                cache_hit=from_cache,
                note=read.note,
            )
        )

    resolved = apply_resolution(tuple(items))
    assert_same_workspace(workspace.workspace_id, resolved, records)

    facts = sort_items(tuple(i for i in resolved if i.item_kind is ItemKind.FACT))
    history = sort_items(tuple(i for i in resolved if i.item_kind is ItemKind.HISTORY))
    plans = sort_items(tuple(i for i in resolved if i.item_kind is ItemKind.PLAN))

    read_count = sum(1 for record in records if record.read_status is SourceReadStatus.READ)
    if read_count == len(records) and records:
        status = ContextStatus.FULL
    elif read_count == 0:
        status = ContextStatus.UNKNOWN
    else:
        status = ContextStatus.PARTIAL

    return ContextResponse(
        workspace=workspace,
        facts=facts,
        history=history,
        plans=plans,
        sources=tuple(records),
        freshness=FreshnessSummary.of(tuple(item.freshness for item in resolved)),
        status=status,
        conflicts=resolve_conflicts(resolved),
        retrieved_at=retrieved_at,
    )


__all__ = [
    "Clock",
    "ContextResponse",
    "FreshnessSummary",
    "SourceRecord",
    "assert_same_workspace",
    "build_context",
    "utc_now",
]
