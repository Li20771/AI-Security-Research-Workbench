"""The §30 admission pipeline through persistence, and §30 step 14 uniqueness.

`admit_to_store` composes B1, the P1 workspace rule and the P2 loader with the
Store. Nothing here re-tests a rule that B1, P1 or P2 already holds directly —
the tests are about the **composition**: the order, what reaches the store, what
does not, and what a rejection costs.

### The two uniqueness cases, and why they are not symmetric

```text
duplicate evidence_id       collision or overwrite attempt   REJECTED  (§8.2)
duplicate content_digest    two events making one claim      ACCEPTED  (§8.2)
```

§8.2 states both, and §30 step 14 names only the first. A store that keyed on
`content_digest` would satisfy the easy half of this file and silently collapse
two observations into one — so the acceptance case has its own test, and asserts
that both records are still there afterwards.
"""

from __future__ import annotations

import json

import pytest

from plugins.evidence import (
    AdmissionOutcome,
    EvidenceStore,
    EvidenceTier,
    admit,
    admit_to_store,
    assign_digests,
    EvidenceRecord,
)
from plugins.evidence import errors as ev_errors
from tests.evidence.conftest import (
    FIXED_CLOCK,
    WS,
    WS_OTHER,
    make_context_ref,
    make_observation,
)

pytestmark = pytest.mark.layer1

CLK = lambda: FIXED_CLOCK  # noqa: E731 - a pinned clock, as the other modules use


def _admit(raw, store):
    return admit_to_store(raw, store=store, clock=CLK)


@pytest.fixture
def store(tmp_path):
    return EvidenceStore(tmp_path / "staged")


# --------------------------------------------------------------------------
# The composed pipeline
# --------------------------------------------------------------------------


class TestThePipeline:
    def test_an_admissible_record_is_accepted_and_written(self, store):
        result = _admit(make_observation(), store)

        assert result.outcome is AdmissionOutcome.ACCEPTED
        assert result.record is not None
        assert store.list_ids() == (result.record.evidence_id,)

    def test_the_stored_record_is_the_admitted_record(self, store):
        result = _admit(make_observation(), store)

        assert store.read(result.record.evidence_id) == result.record

    def test_the_admitted_record_carries_both_digests(self, store):
        """§30 step 12 ran before the write, not after it."""
        result = _admit(make_observation(), store)

        assert len(result.record.integrity.content_digest) == 64
        assert len(result.record.integrity.record_digest) == 64

    def test_admit_to_store_agrees_with_admit_on_the_verdict(self, store):
        """Composition must not change the answer admission already gives."""
        raw = make_observation(references={"context": [make_context_ref()]})

        assert admit(raw, clock=CLK).outcome is _admit(raw, store).outcome

    def test_the_supplied_mapping_is_never_modified(self, store):
        import copy

        raw = make_observation(references={"context": [make_context_ref()]})
        before = copy.deepcopy(raw)

        _admit(raw, store)

        assert raw == before


# --------------------------------------------------------------------------
# A rejection stores nothing
# --------------------------------------------------------------------------


class TestARejectionStoresNothing:
    """§30: "Any failure produces REJECTED with a named reason and stores nothing"."""

    @pytest.mark.parametrize(
        "label,raw",
        [
            ("unknown top-level field", lambda: {**make_observation(), "raw_payload": 1}),
            ("unsupported schema", lambda: {**make_observation(), "schema_version": 2}),
            ("missing required field", lambda: {k: v for k, v in make_observation().items() if k != "payload"}),
            ("not a mapping", lambda: "not a record"),
            ("none", lambda: None),
            (
                "unregistered producer",
                lambda: make_observation(provenance={
                    "producer": "ai-02",
                    "producer_version": "1.0.0",
                    "producer_type": "service",
                    "actor": {"id": "ai-02", "type": "service"},
                    "workspace_id": WS,
                }),
            ),
        ],
    )
    def test_a_rejected_record_leaves_the_store_empty(self, store, label, raw):
        result = _admit(raw(), store)

        assert result.outcome is AdmissionOutcome.REJECTED, label
        assert result.record is None, label
        assert store.list_ids() == (), label

    def test_a_workspace_violation_is_not_filtered_into_a_write(self, store):
        """§18.3 survives composition: the record is refused whole."""
        raw = make_observation(references={"context": [
            make_context_ref(subject="git.head", workspace_id=WS),
            make_context_ref(subject="git.branch", workspace_id=WS_OTHER),
        ]})

        result = _admit(raw, store)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "WORKSPACE_AGREEMENT_VIOLATION"
        assert store.list_ids() == ()
        assert len(raw["references"]["context"]) == 2

    def test_the_reason_code_names_the_rule(self, store):
        result = _admit("not a record", store)

        assert result.reason_code == "RECORD_MALFORMED"


# --------------------------------------------------------------------------
# Case A — duplicate evidence_id
# --------------------------------------------------------------------------


class TestDuplicateEvidenceIdIsRejected:
    """§8.2, §30 step 14. A collision is refused and nothing is replaced."""

    @staticmethod
    def _pin_identity(monkeypatch, evidence_id: str) -> None:
        """Force the generated id, so a collision is constructible.

        `new_evidence_id` is a `uuid4`-backed generator, so a collision cannot
        happen by chance and cannot be demanded from the outside. This patches
        the generator rather than adding an `evidence_id` argument to the
        pipeline: an argument would be a caller-supplied identity, which §8.1
        forbids, and a test does not get to widen the contract.
        """
        monkeypatch.setattr(
            "plugins.evidence.models.new_evidence_id", lambda: evidence_id
        )

    def test_a_collision_is_rejected(self, store, monkeypatch):
        self._pin_identity(monkeypatch, "ev-" + "d" * 16)

        first = _admit(make_observation(), store)
        second = _admit(
            make_observation(payload={
                "family": "SOURCE_READ",
                "subject": "a-second-claim",
                "observed": "second",
                "read_status": "READ",
                "binding": {
                    "source_kind": "git_current_state",
                    "source_identity": "git",
                    "source_revision": "a" * 39 + "1",
                },
            }),
            store,
        )

        assert first.outcome is AdmissionOutcome.ACCEPTED
        assert second.outcome is AdmissionOutcome.REJECTED
        assert second.reason_code == "DUPLICATE_EVIDENCE_ID"
        assert second.record is None

    def test_the_existing_record_is_not_overwritten(self, store, monkeypatch):
        self._pin_identity(monkeypatch, "ev-" + "d" * 16)

        first = _admit(make_observation(), store)
        path = store.root / f"{first.record.evidence_id}.json"
        before = path.read_bytes()

        _admit(
            make_observation(payload={
                "family": "SOURCE_READ",
                "subject": "a-second-claim",
                "observed": "second",
                "read_status": "READ",
                "binding": {
                    "source_kind": "git_current_state",
                    "source_identity": "git",
                    "source_revision": "a" * 39 + "1",
                },
            }),
            store,
        )

        assert path.read_bytes() == before
        assert store.read(first.record.evidence_id) == first.record

    def test_only_one_file_exists_after_a_collision(self, store, monkeypatch):
        self._pin_identity(monkeypatch, "ev-" + "d" * 16)

        _admit(make_observation(), store)
        _admit(make_observation(), store)

        assert store.list_ids() == ("ev-" + "d" * 16,)

    def test_the_store_refuses_a_direct_write_of_a_duplicate(self, store):
        """The detection is the Store's; the rule is admission's (D8)."""
        record = assign_digests(
            EvidenceRecord.from_mapping(
                make_observation(), evidence_id="ev-" + "e" * 16, clock=CLK
            )
        )
        store.write(record)

        with pytest.raises(ev_errors.DuplicateEvidenceId):
            store.write(record)


# --------------------------------------------------------------------------
# Case B — duplicate content_digest
# --------------------------------------------------------------------------


class TestDuplicateContentDigestIsAccepted:
    """§8.2: duplicate content is two events. `content_digest` is not a key."""

    def test_two_records_making_the_same_claim_are_both_accepted(self, store):
        raw = make_observation()

        first = _admit(raw, store)
        second = _admit(raw, store)

        assert first.outcome is AdmissionOutcome.ACCEPTED
        assert second.outcome is AdmissionOutcome.ACCEPTED

    def test_both_records_are_stored(self, store):
        raw = make_observation()

        first = _admit(raw, store)
        second = _admit(raw, store)

        assert store.list_ids() == tuple(
            sorted([first.record.evidence_id, second.record.evidence_id])
        )
        assert store.read(first.record.evidence_id) == first.record
        assert store.read(second.record.evidence_id) == second.record

    def test_the_semantic_digest_is_the_same_and_the_record_digest_is_not(self, store):
        raw = make_observation()

        first = _admit(raw, store).record
        second = _admit(raw, store).record

        assert first.integrity.content_digest == second.integrity.content_digest
        assert first.integrity.record_digest != second.integrity.record_digest
        assert first.evidence_id != second.evidence_id

    def test_the_store_has_no_index_keyed_on_content_digest(self, store):
        """A store keyed on the semantic digest would have collapsed these."""
        raw = make_observation()
        for _ in range(3):
            _admit(raw, store)

        assert len(store.list_ids()) == 3
        digests = {
            store.read(i).integrity.content_digest for i in store.list_ids()
        }
        assert len(digests) == 1, "three records, one claim, three files"


# --------------------------------------------------------------------------
# Write failure (§22.1 UNAVAILABLE, §22.3)
# --------------------------------------------------------------------------


class _FailingStore:
    """A store whose write fails for a reason other than a collision."""

    def contains(self, evidence_id: object) -> bool:
        return False

    def write(self, record: object) -> None:
        raise OSError("the disk went away")


class TestAWriteFailureIsUnavailable:
    """§22.3: INCOMPLETE CONTENT is REJECTED; WRITE FAILURE is UNAVAILABLE."""

    def test_a_write_failure_is_not_reported_as_a_rejection(self):
        result = _admit(make_observation(), _FailingStore())

        assert result.outcome is AdmissionOutcome.UNAVAILABLE
        assert result.outcome is not AdmissionOutcome.REJECTED

    def test_a_write_failure_stores_nothing_and_returns_no_record(self):
        result = _admit(make_observation(), _FailingStore())

        assert result.record is None
        assert result.reason_code == "STORAGE_FAILURE"

    def test_the_two_failures_keep_their_distinct_codes(self, store):
        rejected = _admit("not a record", store)
        unavailable = _admit(make_observation(), _FailingStore())

        assert rejected.reason_code != unavailable.reason_code
        assert rejected.outcome is not unavailable.outcome


# --------------------------------------------------------------------------
# The pipeline does not reach past what it composes
# --------------------------------------------------------------------------


class TestThePipelineComposesRatherThanReimplements:
    def test_the_admission_module_does_not_restate_a_b1_rule(self):
        """No second grammar, registry or cross-field check lives there."""
        import ast
        import pathlib

        source = pathlib.Path("plugins/evidence/admission.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")

        assert "plugins.evidence.grammar" not in imported, "a second grammar import"
        assert "plugins.evidence.canonical" not in imported, "a second projection"

    def test_the_pipeline_still_refuses_a_stored_form(self, store):
        """R1 is unchanged by the pipeline having somewhere to write."""
        stored = assign_digests(
            EvidenceRecord.from_mapping(make_observation(), clock=CLK)
        ).to_stored_mapping()

        result = _admit(stored, store)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert store.list_ids() == ()

    def test_an_accepted_result_carries_no_step_seven_claim(self, store):
        """C-1 remains DEFERRED, so step 7 has not run and nothing says it has.

        The pipeline is §30 steps 1-6 and 8-14. There is no field, flag or
        status anywhere in the result that a caller could read as "the rule set
        was checked", which is the shape the gap would take if it were papered
        over.
        """
        import dataclasses

        result = _admit(make_observation(), store)

        assert result.outcome is AdmissionOutcome.ACCEPTED
        assert {f.name for f in dataclasses.fields(result)} == {
            "outcome",
            "reason_code",
            "record",
        }
        assert not hasattr(result, "step_7")
        assert not hasattr(result, "rule_set_checked")


# --------------------------------------------------------------------------
# The tiers stay separate
# --------------------------------------------------------------------------


class TestTheTiersStaySeparate:
    def test_a_staged_write_does_not_appear_in_the_promoted_tier(self, tmp_path):
        staged = EvidenceStore(tmp_path / "staged")
        promoted = EvidenceStore(tmp_path / "promoted", tier=EvidenceTier.PROMOTED)

        result = _admit(make_observation(), staged)

        assert staged.list_ids() == (result.record.evidence_id,)
        assert promoted.list_ids() == ()
        assert promoted.contains(result.record.evidence_id) is False
