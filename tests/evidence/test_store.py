"""The filesystem Store — §19, §20 and B2 decisions D2/D3/D4/D5.

Every test here uses a temporary directory. The repository's own
`evidence/staged/` and `evidence/promoted/` are never written by the suite, and
the Store never discovers a path: it is handed a root, which is what makes that
possible.

### What these tests are about

The Store is a byte pipe, so most of what can go wrong is at the edges: a
partial file becoming visible, an existing record being replaced, a path being
assembled from an unvalidated id, or a corrupted file being returned as a valid
record. Each of those has a test rather than an assurance.
"""

from __future__ import annotations

import json

import pytest

from plugins.evidence import (
    EvidenceRecord,
    PromotedEvidenceStore,
    StagedEvidenceStore,
    StoredIntegrityFailure,
    admit_to_store,
    assign_digests,
    load_stored,
)
from plugins.evidence import errors as ev_errors
from plugins.evidence.store import SUFFIX
from tests.evidence.conftest import FIXED_CLOCK, make_observation

pytestmark = pytest.mark.layer1


def _written(**overrides) -> EvidenceRecord:
    return assign_digests(
        EvidenceRecord.from_mapping(make_observation(**overrides), clock=lambda: FIXED_CLOCK)
    )


@pytest.fixture
def staged(tmp_path):
    return StagedEvidenceStore(tmp_path / "staged")


@pytest.fixture
def promoted(tmp_path):
    return PromotedEvidenceStore(tmp_path / "promoted")


def _promote_by_hand(staged, promoted, record):
    """Put a staged record's bytes in the promoted directory the way a human does.

    There is no promotion method to call — that is the point of §20.3 — so the
    test performs the act itself: copy the file, byte for byte, to a new
    location. Nothing here is an AI-05 operation, and the invariants it must
    preserve are asserted in `TestPromotionInvariants`.
    """
    promoted.root.mkdir(parents=True, exist_ok=True)
    (promoted.root / f"{record.evidence_id}.json").write_bytes(
        (staged.root / f"{record.evidence_id}.json").read_bytes()
    )


# --------------------------------------------------------------------------
# The physical format (D2, D3)
# --------------------------------------------------------------------------


class TestThePhysicalFormat:
    """D3: UTF-8 JSON, one record per file, `<evidence_id>.json`."""

    def test_one_record_is_one_file_named_for_its_evidence_id(self, staged):
        record = _written()

        staged.write(record)

        files = list(staged.root.iterdir())
        assert [f.name for f in files] == [f"{record.evidence_id}{SUFFIX}"]

    def test_the_file_is_utf8_json_of_the_stored_mapping(self, staged):
        record = _written()

        staged.write(record)

        raw = (staged.root / f"{record.evidence_id}{SUFFIX}").read_bytes()
        assert raw.decode("utf-8")  # raises if it is not UTF-8
        assert json.loads(raw.decode("utf-8")) == record.to_stored_mapping()

    def test_no_temporary_file_survives_a_successful_write(self, staged):
        staged.write(_written())

        assert [p.name for p in staged.root.iterdir() if ".tmp-" in p.name] == []

    def test_no_temporary_file_survives_a_collision(self, staged):
        record = _written()
        staged.write(record)

        with pytest.raises(ev_errors.DuplicateEvidenceId):
            staged.write(record)

        assert [p.name for p in staged.root.iterdir() if ".tmp-" in p.name] == []

    def test_the_store_writes_under_its_root_and_nowhere_else(self, tmp_path):
        root = tmp_path / "only-here"
        store = StagedEvidenceStore(root)

        store.write(_written())

        assert root.is_dir()
        assert [p.name for p in tmp_path.iterdir()] == ["only-here"]

    def test_nothing_is_written_until_a_write_is_asked_for(self, tmp_path):
        root = tmp_path / "untouched"
        StagedEvidenceStore(root)

        assert not root.exists()


# --------------------------------------------------------------------------
# Round-trip through the filesystem (§17, D3)
# --------------------------------------------------------------------------


class TestFilesystemRoundTrip:
    """The contract's round-trip, through real bytes on a real filesystem."""

    def test_a_record_reads_back_equal(self, staged):
        record = _written()

        staged.write(record)

        assert staged.read(record.evidence_id) == record

    def test_both_digests_are_unchanged_by_storage(self, staged):
        record = _written()
        staged.write(record)

        back = staged.read(record.evidence_id)

        assert back.integrity.content_digest == record.integrity.content_digest
        assert back.integrity.record_digest == record.integrity.record_digest

    def test_the_store_does_not_recompute_or_alter_a_digest(self, staged):
        """D3: the Store neither calculates a digest nor rewrites one."""
        record = _written()
        staged.write(record)

        on_disk = json.loads(
            (staged.root / f"{record.evidence_id}{SUFFIX}").read_text(encoding="utf-8")
        )

        assert on_disk["integrity"]["content_digest"] == record.integrity.content_digest
        assert on_disk["integrity"]["record_digest"] == record.integrity.record_digest

    def test_the_stored_bytes_are_exactly_the_stored_mapping(self, staged):
        """Nothing is added, reordered or normalised on the way to disk."""
        record = _written()
        staged.write(record)

        on_disk = json.loads(
            (staged.root / f"{record.evidence_id}{SUFFIX}").read_text(encoding="utf-8")
        )

        assert on_disk == json.loads(json.dumps(record.to_stored_mapping()))
        assert load_stored(on_disk).integrity.record_digest == record.integrity.record_digest

    def test_a_fresh_store_instance_reads_the_same_record(self, tmp_path):
        """D1/D3: a written record survives the process that wrote it.

        A new `EvidenceStore` over the same root has no shared state with the
        one that wrote — this is the closest a test gets to a restart without
        spawning a process.
        """
        root = tmp_path / "staged"
        record = _written()
        StagedEvidenceStore(root).write(record)

        recovered = StagedEvidenceStore(root).read(record.evidence_id)

        assert recovered == record


# --------------------------------------------------------------------------
# No overwrite (§30 step 14 at the filesystem boundary, D8)
# --------------------------------------------------------------------------


class TestNoOverwrite:
    """An existing record is never silently replaced."""

    def test_a_second_write_of_the_same_id_is_refused(self, staged):
        record = _written()
        staged.write(record)

        with pytest.raises(ev_errors.DuplicateEvidenceId):
            staged.write(record)

    def test_the_existing_bytes_are_untouched_by_a_refused_write(self, staged):
        record = _written()
        staged.write(record)
        path = staged.root / f"{record.evidence_id}{SUFFIX}"
        before = path.read_bytes()

        other = assign_digests(
            EvidenceRecord.from_mapping(
                make_observation(payload={
                    "family": "SOURCE_READ",
                    "subject": "a-different-claim",
                    "observed": "different",
                    "read_status": "READ",
                    "binding": {
                        "source_kind": "git_current_state",
                        "source_identity": "git",
                        "source_revision": "a" * 39 + "1",
                    },
                }),
                evidence_id=record.evidence_id,
                clock=lambda: FIXED_CLOCK,
            )
        )
        with pytest.raises(ev_errors.DuplicateEvidenceId):
            staged.write(other)

        assert path.read_bytes() == before
        assert staged.read(record.evidence_id) == record

    def test_contains_reports_an_existing_record(self, staged):
        record = _written()

        assert staged.contains(record.evidence_id) is False
        staged.write(record)
        assert staged.contains(record.evidence_id) is True


# --------------------------------------------------------------------------
# Reading what is not there, or not readable
# --------------------------------------------------------------------------


class TestUnreadableRecords:
    """Every way a read can fail, and each one fails as its own thing."""

    def test_a_missing_record_is_not_found(self, staged):
        with pytest.raises(ev_errors.RecordNotFound):
            staged.read("ev-" + "a" * 16)

    def test_a_missing_record_is_not_found_on_the_promoted_tier(self, promoted):
        with pytest.raises(ev_errors.RecordNotFound):
            promoted.read("ev-" + "a" * 16)

    def test_bytes_that_are_not_utf8_are_refused(self, staged):
        evidence_id = "ev-" + "a" * 16
        staged.root.mkdir(parents=True)
        (staged.root / f"{evidence_id}{SUFFIX}").write_bytes(b"\xff\xfe\x00not utf8")

        with pytest.raises(ev_errors.StoredBytesUnreadable):
            staged.read(evidence_id)

    def test_bytes_that_are_not_json_are_refused(self, staged):
        evidence_id = "ev-" + "a" * 16
        staged.root.mkdir(parents=True)
        (staged.root / f"{evidence_id}{SUFFIX}").write_text("{not json", encoding="utf-8")

        with pytest.raises(ev_errors.StoredBytesUnreadable):
            staged.read(evidence_id)

    def test_valid_json_that_is_not_a_record_is_refused(self, staged):
        evidence_id = "ev-" + "a" * 16
        staged.root.mkdir(parents=True)
        (staged.root / f"{evidence_id}{SUFFIX}").write_text('{"hello": 1}', encoding="utf-8")

        with pytest.raises(ev_errors.EvidenceError):
            staged.read(evidence_id)

    def test_a_tampered_record_is_refused_rather_than_returned(self, staged):
        record = _written()
        staged.write(record)
        path = staged.root / f"{record.evidence_id}{SUFFIX}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["provenance"]["producer_version"] = "9.9.9"
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(StoredIntegrityFailure):
            staged.read(record.evidence_id)

    def test_a_tampered_record_is_not_repaired(self, staged):
        """The refusal leaves the file exactly as it was."""
        record = _written()
        staged.write(record)
        path = staged.root / f"{record.evidence_id}{SUFFIX}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["provenance"]["producer_version"] = "9.9.9"
        tampered = json.dumps(payload)
        path.write_text(tampered, encoding="utf-8")

        with pytest.raises(StoredIntegrityFailure):
            staged.read(record.evidence_id)

        assert path.read_text(encoding="utf-8") == tampered


# --------------------------------------------------------------------------
# The id is validated before it becomes a path
# --------------------------------------------------------------------------


class TestTheIdCannotEscapeTheRoot:
    """`G-EVIDENCE-ID` is the reason a traversal is impossible, not a check."""

    @pytest.mark.parametrize(
        "bad_id",
        [
            "../../etc/passwd",
            "..",
            "../outside",
            "/etc/passwd",
            "C:/Windows/System32/config",
            "ev-" + "a" * 15,
            "ev-" + "A" * 16,
            "ev-" + "g" * 16,
            "ev-../../x",
            "",
            None,
            7,
        ],
    )
    def test_a_malformed_id_is_refused_by_every_entry_point(self, staged, bad_id):
        with pytest.raises(ev_errors.EvidenceError):
            staged.read(bad_id)
        with pytest.raises(ev_errors.EvidenceError):
            staged.contains(bad_id)
        with pytest.raises(ev_errors.EvidenceError):
            staged.discard(bad_id)

    @pytest.mark.parametrize("bad_id", ["../../outside", "../outside", "/outside"])
    def test_a_traversal_attempt_creates_no_path_anywhere(self, tmp_path, bad_id):
        """The id is refused before a path is formed, so nothing is touched.

        `write` cannot be reached with a malformed id at all — the model will
        not build a record carrying one — so the traversal surface is the three
        methods that take an id straight from the caller.
        """
        root = tmp_path / "root"
        store = StagedEvidenceStore(root)

        for call in (store.read, store.contains, store.discard):
            with pytest.raises(ev_errors.EvidenceError):
                call(bad_id)

        assert not root.exists()
        assert not (tmp_path / "outside").exists()
        assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# Listing (provisional surface — D11)
# --------------------------------------------------------------------------


class TestListing:
    def test_listing_is_empty_before_anything_is_written(self, staged):
        assert staged.list_ids() == ()

    def test_listing_returns_written_ids_in_order(self, staged):
        records = [
            assign_digests(
                EvidenceRecord.from_mapping(
                    make_observation(), evidence_id="ev-" + c * 16,
                    clock=lambda: FIXED_CLOCK,
                )
            )
            for c in "cab"
        ]
        for record in records:
            staged.write(record)

        assert staged.list_ids() == ("ev-" + "a" * 16, "ev-" + "b" * 16, "ev-" + "c" * 16)

    def test_a_file_that_is_not_a_record_is_not_listed(self, staged):
        record = _written()
        staged.write(record)
        (staged.root / "notes.txt").write_text("not a record", encoding="utf-8")
        stray = staged.root / f"ev-{'a' * 16}.json.tmp-1-abc"
        stray.write_text("x", encoding="utf-8")

        assert staged.list_ids() == (record.evidence_id,)
        assert stray.exists()


# --------------------------------------------------------------------------
# Discard (§19.2, §20.2, D5)
# --------------------------------------------------------------------------


class TestDiscard:
    """`discard` is staged-only and all-or-nothing."""

    def test_a_staged_record_can_be_discarded(self, staged):
        record = _written()
        staged.write(record)

        staged.discard(record.evidence_id)

        assert staged.list_ids() == ()
        assert staged.contains(record.evidence_id) is False

    def test_a_discarded_record_cannot_be_read_again(self, staged):
        record = _written()
        staged.write(record)
        staged.discard(record.evidence_id)

        with pytest.raises(ev_errors.RecordNotFound):
            staged.read(record.evidence_id)

    def test_discarding_something_absent_is_not_found(self, staged):
        with pytest.raises(ev_errors.RecordNotFound):
            staged.discard("ev-" + "a" * 16)

    def test_discard_removes_the_whole_record_and_nothing_else(self, staged):
        keep = assign_digests(
            EvidenceRecord.from_mapping(
                make_observation(), evidence_id="ev-" + "b" * 16, clock=lambda: FIXED_CLOCK
            )
        )
        drop = assign_digests(
            EvidenceRecord.from_mapping(
                make_observation(), evidence_id="ev-" + "c" * 16, clock=lambda: FIXED_CLOCK
            )
        )
        staged.write(keep)
        staged.write(drop)

        staged.discard(drop.evidence_id)

        assert staged.list_ids() == (keep.evidence_id,)
        assert staged.read(keep.evidence_id) == keep

    def test_a_promoted_record_cannot_be_discarded(self, staged, promoted):
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        with pytest.raises(ev_errors.PromotedRecordNotDiscardable):
            promoted.discard(record.evidence_id)

    def test_a_refused_discard_leaves_the_promoted_record_in_place(self, staged, promoted):
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        with pytest.raises(ev_errors.PromotedRecordNotDiscardable):
            promoted.discard(record.evidence_id)

        assert promoted.read(record.evidence_id) == record

    def test_there_is_no_way_to_delete_a_promoted_record(self, promoted):
        """§19.2: the prohibition is the absence of an operation, checked."""
        for name in ("delete", "remove", "purge", "delete_record", "remove_record"):
            assert not hasattr(promoted, name), name


# --------------------------------------------------------------------------
# B — the promoted tier cannot be written, structurally
# --------------------------------------------------------------------------


class TestThePromotedTierCannotBeWritten:
    """§20.3: promotion is a human act, so AI-05 has no operation that adds one.

    The absence of a `promote()` method does not establish this on its own. A
    store that accepts a record from an ordinary program *is* a programmatic
    promotion path, whether or not a method is named for it — which is what the
    promoted tier used to be.
    """

    def test_there_is_no_write_operation_to_call(self, promoted):
        assert not hasattr(promoted, "write")

    def test_no_write_like_operation_exists_either(self, promoted):
        for name in ("write", "add", "put", "insert", "store", "save", "promote", "publish"):
            assert not hasattr(promoted, name), name

    def test_the_class_exposes_no_write_in_its_own_namespace(self):
        """Not just absent on the instance — absent from the type."""
        assert "write" not in vars(PromotedEvidenceStore)
        assert "write" not in dir(PromotedEvidenceStore)

    def test_a_promoted_store_cannot_be_handed_to_admission(self, promoted):
        """The other half: admission cannot be aimed at the durable tier."""
        with pytest.raises(TypeError):
            admit_to_store(make_observation(), store=promoted, clock=lambda: FIXED_CLOCK)

    def test_that_refusal_creates_nothing(self, promoted):
        with pytest.raises(TypeError):
            admit_to_store(make_observation(), store=promoted, clock=lambda: FIXED_CLOCK)

        assert promoted.list_ids() == ()
        assert not promoted.root.exists()

    def test_the_staged_tier_still_writes(self, staged):
        """The control: the capability was moved, not removed."""
        record = _written()

        staged.write(record)

        assert staged.read(record.evidence_id) == record


# --------------------------------------------------------------------------
# C — the promoted tier still reads, and still verifies
# --------------------------------------------------------------------------


class TestThePromotedTierStillReads:
    def test_a_promoted_record_can_be_read(self, staged, promoted):
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        assert promoted.read(record.evidence_id) == record

    def test_a_promoted_record_is_integrity_verified_on_read(self, staged, promoted):
        """The loader runs on this tier too, so a tampered promotion is caught."""
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)
        path = promoted.root / f"{record.evidence_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["provenance"]["producer_version"] = "9.9.9"
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(StoredIntegrityFailure):
            promoted.read(record.evidence_id)

    def test_a_promoted_record_is_listed_and_contained(self, staged, promoted):
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        assert promoted.list_ids() == (record.evidence_id,)
        assert promoted.contains(record.evidence_id) is True

    def test_the_promoted_tier_still_refuses_a_traversal(self, promoted):
        with pytest.raises(ev_errors.EvidenceError):
            promoted.read("../../etc/passwd")


# --------------------------------------------------------------------------
# E — the invariants a human promotion must preserve
# --------------------------------------------------------------------------


class TestPromotionInvariants:
    """§20.3. These are the invariants, not an implementation of promotion."""

    def test_the_bytes_are_identical_after_promotion(self, staged, promoted):
        record = _written()
        staged.write(record)

        _promote_by_hand(staged, promoted, record)

        staged_bytes = (staged.root / f"{record.evidence_id}.json").read_bytes()
        promoted_bytes = (promoted.root / f"{record.evidence_id}.json").read_bytes()
        assert promoted_bytes == staged_bytes

    def test_evidence_id_content_digest_and_record_digest_are_unchanged(self, staged, promoted):
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        promoted_record = promoted.read(record.evidence_id)

        assert promoted_record.evidence_id == record.evidence_id
        assert (
            promoted_record.integrity.content_digest
            == record.integrity.content_digest
        )
        assert promoted_record.integrity.record_digest == record.integrity.record_digest

    def test_the_promoted_record_is_the_same_record(self, staged, promoted):
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        assert promoted.read(record.evidence_id) == record

    def test_promotion_creates_no_new_record(self, staged, promoted):
        record = _written()
        staged.write(record)

        _promote_by_hand(staged, promoted, record)

        assert staged.list_ids() == (record.evidence_id,)
        assert promoted.list_ids() == (record.evidence_id,)
        assert len(staged.list_ids()) + len(promoted.list_ids()) == 2

    def test_promotion_is_a_location_change_not_a_second_admission(self, staged, promoted):
        """Two files, one record: the same identity in two places."""
        record = _written()
        staged.write(record)
        _promote_by_hand(staged, promoted, record)

        first = staged.read(record.evidence_id)
        second = promoted.read(record.evidence_id)

        assert first == second
        assert first.integrity.record_digest == second.integrity.record_digest


# --------------------------------------------------------------------------
# What the Store deliberately has no operation for
# --------------------------------------------------------------------------


class TestTheStoreDoesNotDoThoseThings:
    """Each of these is a decision, so each is asserted rather than assumed."""

    def test_there_is_no_promotion_method(self, staged):
        """D9/D11: promotion is a human act and its API is undefined."""
        for name in ("promote", "promotion", "promote_record", "publish"):
            assert not hasattr(staged, name), name

    def test_there_is_no_supersession_machinery(self, staged):
        """D8: no duplicate_of, no revision, no merge, no dedup."""
        for name in ("supersede", "superseded_by", "merge", "dedupe", "deduplicate"):
            assert not hasattr(staged, name), name

    def test_the_store_module_cannot_compute_a_digest(self):
        """D3: the Store neither computes nor recomputes a digest.

        Checked against the source rather than promised. The check is on what
        the module can *do* — what it imports and what it calls — not on a
        string, because the prose in `store.py` names both digests and the
        write path **reads** `record.integrity.content_digest` to refuse an
        unwritten record. Reading a stored digest is not computing one, and an
        assertion that forbade the read would be forbidding the precondition.
        """
        import ast
        import pathlib

        source = pathlib.Path("plugins/evidence/store.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        reached_by_attribute = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        assert "plugins.evidence.digests" not in imported
        for name in (
            "content_digest",
            "record_digest",
            "assign_digests",
            "content_projection",
            "record_projection",
            "verify_stored_integrity",
        ):
            assert name not in called, f"store.py calls {name}"
            assert name not in reached_by_attribute, f"store.py calls .{name}()"

    def test_a_record_without_digests_is_not_written(self, staged):
        """An unwritten record would produce a file that cannot be read back."""
        unwritten = EvidenceRecord.from_mapping(make_observation(), clock=lambda: FIXED_CLOCK)

        with pytest.raises(ev_errors.StoredBytesUnreadable):
            staged.write(unwritten)

        assert staged.list_ids() == ()
