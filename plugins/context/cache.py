"""The context cache — disposable, rebuildable, and never a source of truth.

Implements AI-03 contract §9. This is A4 of the phase plan.

    cache != source of truth          (AI-00 F-11)

The rule is enforced by the key rather than by a check. A hit requires all four
parts to match, revision included:

    CacheKey = workspace_id + source_kind + source_identity + source_revision

so a hit is evidence that the revision was *confirmed*, not that the value is
trusted. A cache whose key omitted the revision would serve last week's answer
with this week's confidence, and one that omitted `workspace_id` would let one
workspace answer another's question.

Three consequences follow, and each is a test:

* An entry at a superseded revision yields **no items at all**. It is not
  downgraded into an item, not used as a fallback, and not merged.
* `STALE` and `MISS` are distinguished, because they mean different things:
  `STALE` says *this was read here before and the world has moved*; `MISS` says
  *this was never read here*.
* A different workspace's entry is a `MISS`, not a `STALE`. Another workspace's
  value is not an older version of this one's.

AI-03 ships an in-memory cache only (D-10). A persistent cache needs a storage
location, a retention rule, and a cleanup rule; shipping one without those
would ship a second, undeclared source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from plugins.context.classification import RawItem
from plugins.context.errors import CacheError
from plugins.context.vocabulary import SourceKind


class CacheOutcome(StrEnum):
    """The three §9.3 lookup outcomes."""

    HIT = "HIT"
    STALE = "STALE"
    MISS = "MISS"


@dataclass(frozen=True, slots=True)
class CacheKey:
    """The frozen four-part cache key (contract §9.1).

    `source_revision` must be non-empty. A source that could not establish a
    revision cannot be cached, because there would be nothing to confirm a hit
    against -- and an unconfirmable hit is exactly the failure mode the key
    exists to prevent.
    """

    workspace_id: str
    source_kind: SourceKind
    source_identity: str
    source_revision: str

    def __post_init__(self) -> None:
        for name in ("workspace_id", "source_identity", "source_revision"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CacheError(
                    f"cache key {name} must be a non-empty string; got {value!r}. "
                    "A key part that can be absent is a key part that can be "
                    "skipped."
                )

    @property
    def scope(self) -> tuple[str, SourceKind, str]:
        """The key without its revision — used to tell STALE from MISS."""
        return (self.workspace_id, self.source_kind, self.source_identity)

    def render(self) -> str:
        return (
            f"{self.workspace_id}|{self.source_kind}|{self.source_identity}"
            f"|{self.source_revision}"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "workspace_id": self.workspace_id,
            "source_kind": str(self.source_kind),
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
        }


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """One cached read.

    Records `retrieved_at` so that a superseded entry is *reportable* rather
    than merely unusable: knowing when a stale value was read is what lets an
    operator judge whether it is worth re-reading.
    """

    key: CacheKey
    retrieved_at: str
    payload: tuple[RawItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key.to_dict(),
            "retrieved_at": self.retrieved_at,
            "payload": [item.to_dict() for item in self.payload],
        }


@dataclass(frozen=True, slots=True)
class CacheLookup:
    """The result of a lookup (§9.3).

    `entry` is populated only for a `HIT`. A `STALE` result carries no entry,
    so a caller that forgets to check the outcome still cannot use it.
    """

    outcome: CacheOutcome
    entry: CacheEntry | None = None

    @property
    def is_hit(self) -> bool:
        return self.outcome is CacheOutcome.HIT


class InMemoryContextCache:
    """A process-local cache. Deleting it costs nothing but a re-read."""

    def __init__(self, entries: Iterable[CacheEntry] = ()) -> None:
        self._entries: dict[CacheKey, CacheEntry] = {}
        for entry in entries:
            self.put(entry)

    def __len__(self) -> int:
        return len(self._entries)

    def put(self, entry: CacheEntry) -> None:
        self._entries[entry.key] = entry

    def lookup(self, key: CacheKey) -> CacheLookup:
        """Resolve one key to a `HIT`, a `STALE`, or a `MISS`."""
        entry = self._entries.get(key)
        if entry is not None:
            return CacheLookup(outcome=CacheOutcome.HIT, entry=entry)

        # Same workspace, same source, different revision: the world moved.
        # A different workspace is excluded on purpose -- another workspace's
        # value is not an older version of this one's (contract §9.4).
        for existing in self._entries:
            if existing.scope == key.scope:
                return CacheLookup(outcome=CacheOutcome.STALE, entry=None)

        return CacheLookup(outcome=CacheOutcome.MISS, entry=None)

    def invalidate(self, key: CacheKey) -> None:
        self._entries.pop(key, None)

    def invalidate_scope(self, scope: tuple[str, SourceKind, str]) -> None:
        """Drop every entry for one `(workspace, kind, identity)`."""
        for existing in [k for k in self._entries if k.scope == scope]:
            del self._entries[existing]

    def clear(self) -> None:
        self._entries.clear()

    def keys(self) -> tuple[CacheKey, ...]:
        return tuple(sorted(self._entries, key=CacheKey.render))


__all__ = [
    "CacheEntry",
    "CacheKey",
    "CacheLookup",
    "CacheOutcome",
    "InMemoryContextCache",
]
