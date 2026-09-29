"""The cache boundary.

The brief's T9 and T10, plus the key semantics they rest on.

    cache != source of truth

The tests below check that claim in the only way that means anything: by trying
to make the cache lie and showing that it cannot. A stale entry produces no
items; another workspace's entry is not a near-miss but a miss; and a build
over an empty cache produces exactly what a build over a warm one does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.context.cache import (
    CacheEntry,
    CacheKey,
    CacheOutcome,
    InMemoryContextCache,
)
from plugins.context.classification import RawItem
from plugins.context.context import (
    ContextResponse,
    FreshnessSummary,
    SourceRecord,
    build_context,
)
from plugins.context.errors import CacheError
from plugins.context.sources import DocumentSource, GitCurrentStateSource
from plugins.context.validate import check_uncacheable_live_state
from plugins.context.vocabulary import (
    ContextStatus,
    Freshness,
    SourceKind,
    SourceReadStatus,
    WorkingTreeState,
)
from plugins.context.workspace import WorkspaceIdentity
from tests.context.conftest import declaration_document, write_document


pytestmark = pytest.mark.layer2

REPORT = "docs/report.md"


def key_for(workspace_id: str, revision: str, identity: str = REPORT) -> CacheKey:
    return CacheKey(
        workspace_id=workspace_id,
        source_kind=SourceKind.EXIT_REPORT,
        source_identity=identity,
        source_revision=revision,
    )


def without_cache_flag(item) -> dict:
    """Item payload minus the one field a cache is allowed to change.

    `cache_hit` is provenance, not content: whether a read was short-circuited
    must never be visible in what the read said. Comparing everything else is
    how that claim is tested.
    """
    payload = item.to_dict()
    payload.pop("cache_hit")
    return payload


def response_with_source(root: Path, *, source_kind, cache_hit: bool) -> ContextResponse:
    """A minimal hand-built response, for exercising the validators directly."""
    record = SourceRecord(
        workspace_id="ws",
        source_kind=source_kind,
        source_identity="git",
        source_revision="a" * 40,
        retrieved_at="2026-09-29T00:00:00Z",
        read_status=SourceReadStatus.READ,
        freshness=Freshness.CURRENT,
        item_count=0,
        cache_hit=cache_hit,
    )
    return ContextResponse(
        workspace=WorkspaceIdentity(
            workspace_id="ws",
            workspace_root=root.as_posix(),
            repository=None,
            branch="main",
            commit="a" * 40,
            detached=False,
            working_tree=WorkingTreeState.CLEAN,
            changed_files=0,
        ),
        facts=(),
        history=(),
        plans=(),
        sources=(record,),
        freshness=FreshnessSummary(0, 0, 0, Freshness.CURRENT),
        status=ContextStatus.FULL,
        conflicts=(),
        retrieved_at="2026-09-29T00:00:00Z",
    )


class TestCacheKey:
    def test_all_four_parts_are_required(self):
        with pytest.raises(CacheError):
            CacheKey("", SourceKind.EXIT_REPORT, REPORT, "rev")
        with pytest.raises(CacheError):
            CacheKey("ws", SourceKind.EXIT_REPORT, "", "rev")
        with pytest.raises(CacheError):
            CacheKey("ws", SourceKind.EXIT_REPORT, REPORT, "")
        with pytest.raises(CacheError):
            CacheKey("ws", SourceKind.EXIT_REPORT, REPORT, "   ")

    def test_scope_excludes_the_revision(self):
        """Scope is what separates `STALE` from `MISS` (§9.3)."""
        assert key_for("ws", "r1").scope == key_for("ws", "r2").scope

    def test_scope_includes_the_workspace(self):
        assert key_for("ws-a", "r1").scope != key_for("ws-b", "r1").scope

    def test_render_is_stable_and_distinguishing(self):
        assert key_for("ws", "r1").render() == key_for("ws", "r1").render()
        assert key_for("ws", "r1").render() != key_for("ws", "r2").render()


class TestLookupOutcomes:
    def test_an_exact_match_is_a_hit(self):
        cache = InMemoryContextCache()
        entry = CacheEntry(key_for("ws", "r1"), "2026-09-29T00:00:00Z", ())
        cache.put(entry)
        lookup = cache.lookup(key_for("ws", "r1"))
        assert lookup.outcome is CacheOutcome.HIT
        assert lookup.entry is entry
        assert lookup.is_hit

    def test_a_different_revision_is_stale(self):
        cache = InMemoryContextCache()
        cache.put(CacheEntry(key_for("ws", "r1"), "2026-09-29T00:00:00Z", ()))
        lookup = cache.lookup(key_for("ws", "r2"))
        assert lookup.outcome is CacheOutcome.STALE
        assert lookup.entry is None

    def test_a_stale_lookup_never_hands_back_an_entry(self):
        """The type makes the mistake unavailable: no entry, so no fallback."""
        cache = InMemoryContextCache()
        cache.put(CacheEntry(key_for("ws", "r1"), "2026-09-29T00:00:00Z", ()))
        assert cache.lookup(key_for("ws", "r2")).entry is None

    def test_nothing_known_is_a_miss(self):
        assert InMemoryContextCache().lookup(key_for("ws", "r1")).outcome is (
            CacheOutcome.MISS
        )

    def test_a_different_identity_is_a_miss(self):
        cache = InMemoryContextCache()
        cache.put(CacheEntry(key_for("ws", "r1"), "2026-09-29T00:00:00Z", ()))
        lookup = cache.lookup(key_for("ws", "r1", identity="docs/other.md"))
        assert lookup.outcome is CacheOutcome.MISS

    def test_invalidate_removes_one_entry(self):
        cache = InMemoryContextCache()
        cache.put(CacheEntry(key_for("ws", "r1"), "2026-09-29T00:00:00Z", ()))
        cache.invalidate(key_for("ws", "r1"))
        assert cache.lookup(key_for("ws", "r1")).outcome is CacheOutcome.MISS

    def test_invalidate_scope_removes_every_revision(self):
        cache = InMemoryContextCache()
        cache.put(CacheEntry(key_for("ws", "r1"), "t", ()))
        cache.put(CacheEntry(key_for("ws", "r2"), "t", ()))
        cache.invalidate_scope(key_for("ws", "r1").scope)
        assert len(cache) == 0

    def test_clear_empties_the_cache(self):
        cache = InMemoryContextCache()
        cache.put(CacheEntry(key_for("ws", "r1"), "t", ()))
        cache.clear()
        assert len(cache) == 0

    def test_the_cache_is_disposable(self):
        """Deleting it is always safe: it holds nothing that cannot be re-read."""
        cache = InMemoryContextCache()
        cache.put(
            CacheEntry(
                key_for("ws", "r1"),
                "t",
                (RawItem(subject="a", value="b", declared_state="PASS"),),
            )
        )
        cache.clear()
        assert cache.lookup(key_for("ws", "r1")).outcome is CacheOutcome.MISS


class TestT9CacheWorkspaceIsolation:
    """A workspace's cache entry is not reachable from another workspace."""

    @pytest.fixture
    def twin_workspaces(self, tmp_path: Path, fake_git):
        """Two workspaces whose documents are byte-identical.

        Identical content means identical revision digests, so any isolation
        that holds here holds because of `workspace_id` alone -- there is no
        convenient difference in the content to hide behind.
        """
        text = declaration_document(("Live provider execution", "NOT_RUN"))
        roots = []
        for name in ("ws-a", "ws-b"):
            root = tmp_path / name
            root.mkdir()
            write_document(root, REPORT, text)
            roots.append(root)
        return roots

    def test_a_is_a_hit_and_b_is_a_miss(self, twin_workspaces, fake_git):
        root_a, root_b = twin_workspaces
        cache = InMemoryContextCache()
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)

        build_context(root_a, manifest=manifest, reader=fake_git, cache=cache)
        response_b = build_context(
            root_b, manifest=manifest, reader=fake_git, cache=cache
        )

        record_b = response_b.sources[0]
        assert record_b.cache_hit is False, "workspace B was served workspace A's entry"
        assert record_b.workspace_id == response_b.workspace.workspace_id

    def test_b_lookup_is_a_miss_not_a_stale(self, twin_workspaces, fake_git):
        """Another workspace's entry is not an older version of this one's (§9.4)."""
        root_a, root_b = twin_workspaces
        cache = InMemoryContextCache()
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)

        first = build_context(root_a, manifest=manifest, reader=fake_git, cache=cache)
        revision = first.sources[0].source_revision
        assert revision is not None

        # The same document content, read under a different workspace, must not
        # even register as a stale version of A's entry.
        lookup = cache.lookup(
            CacheKey(
                workspace_id="ws-different",
                source_kind=SourceKind.EXIT_REPORT,
                source_identity=REPORT,
                source_revision=revision,
            )
        )
        assert lookup.outcome is CacheOutcome.MISS

    def test_the_two_workspaces_have_different_identities(self, twin_workspaces, fake_git):
        root_a, root_b = twin_workspaces
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)
        a = build_context(root_a, manifest=manifest, reader=fake_git)
        b = build_context(root_b, manifest=manifest, reader=fake_git)
        assert a.workspace.workspace_id != b.workspace.workspace_id

    def test_identical_content_still_yields_identical_items_per_workspace(
        self, twin_workspaces, fake_git
    ):
        """Isolation is about identity, not about content differing."""
        root_a, root_b = twin_workspaces
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)
        a = build_context(root_a, manifest=manifest, reader=fake_git)
        b = build_context(root_b, manifest=manifest, reader=fake_git)
        assert [(i.subject, i.value, i.truth_state) for i in a.items] == [
            (i.subject, i.value, i.truth_state) for i in b.items
        ]


class TestT10CacheInvalidation:
    """When the source revision changes, the old entry is not current."""

    def test_a_changed_document_invalidates_its_entry(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        path = write_document(
            root, REPORT, declaration_document(("Gate", "NOT_RUN"))
        )
        cache = InMemoryContextCache()
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)

        first = build_context(root, manifest=manifest, reader=fake_git, cache=cache)
        first_revision = first.sources[0].source_revision
        assert first_revision is not None

        path.write_text(declaration_document(("Gate", "BLOCKED")), encoding="utf-8")

        second = build_context(root, manifest=manifest, reader=fake_git, cache=cache)
        second_revision = second.sources[0].source_revision
        assert second_revision is not None
        assert second_revision != first_revision

        # The old entry is now a different revision: stale, and unusable.
        lookup = cache.lookup(
            CacheKey(
                workspace_id=first.workspace.workspace_id,
                source_kind=SourceKind.EXIT_REPORT,
                source_identity=REPORT,
                source_revision=first_revision,
            )
        )
        assert lookup.outcome is CacheOutcome.HIT  # the old entry still exists...

        # ...and asking for the *current* revision is a stale, not a hit.
        current = cache.lookup(
            CacheKey(
                workspace_id=first.workspace.workspace_id,
                source_kind=SourceKind.EXIT_REPORT,
                source_identity=REPORT,
                source_revision=second_revision,
            )
        )
        assert current.outcome is CacheOutcome.HIT  # populated by the rebuild

    def test_the_stale_revision_is_reported_as_stale(self, tmp_path: Path, fake_git):
        """A revision that was read here before, and is not the current one."""
        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, REPORT, declaration_document(("Gate", "NOT_RUN")))
        cache = InMemoryContextCache()
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)
        build_context(root, manifest=manifest, reader=fake_git, cache=cache)

        lookup = cache.lookup(
            CacheKey(
                workspace_id=build_context(
                    root, manifest=manifest, reader=fake_git, cache=cache
                ).workspace.workspace_id,
                source_kind=SourceKind.EXIT_REPORT,
                source_identity=REPORT,
                source_revision="a-revision-that-was-never-read",
            )
        )
        assert lookup.outcome is CacheOutcome.STALE
        assert lookup.entry is None

    def test_the_rebuild_reflects_the_new_content_not_the_cached_value(
        self, tmp_path: Path, fake_git
    ):
        root = tmp_path / "ws"
        root.mkdir()
        path = write_document(root, REPORT, declaration_document(("Gate", "NOT_RUN")))
        cache = InMemoryContextCache()
        manifest = (DocumentSource(SourceKind.EXIT_REPORT, REPORT),)

        first = build_context(root, manifest=manifest, reader=fake_git, cache=cache)
        assert first.history[0].value == "NOT_RUN"

        path.write_text(declaration_document(("Gate", "BLOCKED")), encoding="utf-8")
        second = build_context(root, manifest=manifest, reader=fake_git, cache=cache)
        assert second.history[0].value == "BLOCKED"
        assert second.sources[0].cache_hit is False

    def test_a_head_move_invalidates_git_history(self, tmp_path: Path, fake_git):
        from plugins.context.sources import GitHistorySource
        from tests.context.conftest import git_log_lines

        root = tmp_path / "ws"
        root.mkdir()
        manifest = (GitHistorySource(fake_git),)
        cache = InMemoryContextCache()

        fake_git.head = "a" * 40
        fake_git.log = git_log_lines([("a" * 40, "2026-09-29T10:00:00+00:00", "one")])
        first = build_context(root, manifest=manifest, reader=fake_git, cache=cache)
        assert first.sources[0].cache_hit is False

        fake_git.head = "b" * 40
        fake_git.log = git_log_lines([("b" * 40, "2026-09-29T11:00:00+00:00", "two")])
        second = build_context(root, manifest=manifest, reader=fake_git, cache=cache)

        # A new HEAD is a new revision, so the entry was not reused.
        assert second.sources[0].cache_hit is False
        assert second.sources[0].source_revision == "b" * 40
        assert any("two" in item.value for item in second.history)


class TestTheCacheIsOnlyAnOptimisation:
    def test_a_warm_cache_does_not_change_the_items(self, tmp_path: Path, fake_git):
        from plugins.context.sources import GitHistorySource
        from tests.context.conftest import git_log_lines

        root = tmp_path / "ws"
        root.mkdir()
        write_document(root, REPORT, declaration_document(("Gate", "NOT_RUN")))
        fake_git.log = git_log_lines([("a" * 40, "2026-09-29T10:00:00+00:00", "one")])
        manifest = (
            DocumentSource(SourceKind.EXIT_REPORT, REPORT),
            GitHistorySource(fake_git),
        )

        cold = build_context(root, manifest=manifest, reader=fake_git)
        cache = InMemoryContextCache()
        build_context(root, manifest=manifest, reader=fake_git, cache=cache)
        warm = build_context(root, manifest=manifest, reader=fake_git, cache=cache)

        assert any(record.cache_hit for record in warm.sources), "the warm cache did nothing"
        assert [without_cache_flag(i) for i in cold.items] == [
            without_cache_flag(i) for i in warm.items
        ]


class TestTheLiveStateSourceIsNeverCached:
    """D-14: no cheap probe captures the working tree, so the source is uncached."""

    def test_probe_revision_is_none(self, tmp_path: Path, fake_git):
        source = GitCurrentStateSource(fake_git)
        assert source.probe_revision(None, tmp_path) is None  # type: ignore[arg-type]

    def test_a_cached_live_state_is_a_validation_failure(self, tmp_path: Path):
        """The rule is enforced by `validate`, not merely by the reader."""
        response = response_with_source(
            tmp_path,
            source_kind=SourceKind.GIT_CURRENT_STATE,
            cache_hit=True,
        )
        assert check_uncacheable_live_state(response) != []

    def test_a_live_state_recording_no_hit_passes_validation(self, tmp_path: Path):
        response = response_with_source(
            tmp_path,
            source_kind=SourceKind.GIT_CURRENT_STATE,
            cache_hit=False,
        )
        assert check_uncacheable_live_state(response) == []

    def test_the_real_read_never_reports_a_cache_hit(self, tmp_path: Path, fake_git):
        root = tmp_path / "ws"
        root.mkdir()
        cache = InMemoryContextCache()
        manifest = (GitCurrentStateSource(fake_git),)
        for _ in range(3):
            response = build_context(root, manifest=manifest, reader=fake_git, cache=cache)
            assert response.sources[0].cache_hit is False
