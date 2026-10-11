"""The stored form and §17's round-trip — R1 to R8.

§17 requires:

```text
serialize -> canonicalize -> hash          == record_digest
re-read   -> parse -> canonicalize -> hash == the SAME record_digest
```

and names the trap: "an implementation whose storage format does not round-trip
losslessly (a string that re-parses as a boolean, a numeric string that
re-parses as a number) will drift `record_digest` on an unmodified record".

So the round trip is exercised **through JSON text**, not from dictionary to
dictionary. A dict-to-dict test would pass an implementation that stored
`ordinal` as `"0"`, which is exactly what §17 says to watch for.

### Why `json` appears in this file and not in the package

B2 decision D3 fixes the storage encoding as UTF-8 JSON, and this file proves
the stored mapping is JSON-safe. `plugins/evidence` still imports no serializer:
the mapping it produces is plain `str`/`int`/`bool`/`None`/`list`/`dict`, and
turning that into bytes is the Store's job. The Store does not exist yet, so the
encoding lives here, where it is under test.

### The two entry points

`EvidenceRecord.from_mapping` is the caller parser. `load_stored` is the
stored-form loader. R4 exists to prove the first did not become the second.

### What the tamper tests have to get right

R5 to R7 must tamper a field with a value that is **still valid for its own
grammar**, so that the only thing that can catch it is the digest. A tamper that
also breaks a shape rule proves nothing about integrity — it would be refused by
the parser, which is the easy half. Each test asserts
`reason_code == "STORED_INTEGRITY_FAILURE"` for that reason.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from trust_harness import proof_for_record

from plugins.evidence import (
    EvidenceRecord,
    StoredIntegrityFailure,
    admit,
    assign_digests,
    content_digest,
    load_stored,
    record_digest,
    record_projection,
    verify_stored_integrity,
)
from plugins.evidence import errors as ev_errors
from tests.evidence.conftest import (
    FIXED_CLOCK,
    SHA256,
    WS_OTHER,
    make_artifact,
    make_context_ref,
    make_decision,
    make_execution,
    make_observation,
)

pytestmark = pytest.mark.layer1

#: A value distinctive enough that finding it anywhere in the stored bytes
#: would be a §12.4 violation rather than a coincidence.
RAW_VALUE = "the-raw-context-value-must-never-be-stored"


def _write(raw: dict) -> EvidenceRecord:
    """Admit a supplied record and give it its digests."""
    return assign_digests(
        EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)
    )


def _json_round_trip(record: EvidenceRecord) -> EvidenceRecord:
    """The real §17 path: mapping -> JSON text -> mapping -> loader."""
    text = json.dumps(record.to_stored_mapping(), ensure_ascii=False)
    return load_stored(json.loads(text))


def _observation(**overrides) -> EvidenceRecord:
    base = dict(
        references={"context": [make_context_ref(subject="git.head", value=RAW_VALUE)]},
        artifacts={"items": [make_artifact()]},
    )
    base.update(overrides)
    return _write(make_observation(**base))


# --------------------------------------------------------------------------
# R1 — full round-trip
# --------------------------------------------------------------------------


class TestR1FullRoundTrip:
    """R1 — a written record survives storage unchanged, digests included."""

    def test_an_observation_round_trips_through_json_text(self):
        original = _observation()

        restored = _json_round_trip(original)

        assert restored == original

    def test_all_three_kinds_round_trip(self):
        """The envelope is shared; each payload's inverse is its own."""
        for original in (
            _observation(),
            _write(make_decision()),
            _write(make_execution()),
        ):
            restored = _json_round_trip(original)
            assert restored == original, original.kind
            assert restored.payload == original.payload

    def test_both_digests_are_reproduced_exactly(self):
        original = _observation()

        restored = _json_round_trip(original)

        assert restored.integrity.content_digest == original.integrity.content_digest
        assert restored.integrity.record_digest == original.integrity.record_digest

    def test_a_second_write_is_byte_identical(self):
        """The stored form is deterministic, so a promotion copy is comparable."""
        original = _observation()

        assert original.to_stored_mapping() == original.to_stored_mapping()

    def test_re_reading_twice_gives_the_same_digests(self):
        """§17's requirement is about re-reading, not about reading once."""
        original = _observation()
        first = _json_round_trip(original)

        second = _json_round_trip(first)

        assert second.integrity.record_digest == original.integrity.record_digest

    def test_the_stored_form_is_json_safe(self):
        """No value the encoder would have to special-case."""
        stored = _observation().to_stored_mapping()

        reloaded = json.loads(json.dumps(stored, ensure_ascii=False))

        assert reloaded == stored

    def test_a_tool_call_ordinal_stays_an_integer(self):
        """§17's named trap: `"0"` re-reads as a string and would drift the digest."""
        original = _write(make_execution(payload={"tool_calls[]": [
            {"ordinal": 0, "what_ran": "git status", "status": "PASS"},
            {"ordinal": 7, "what_ran": "pytest", "status": "PASS"},
        ]}))

        restored = _json_round_trip(original)

        ordinals = [c.ordinal for c in restored.payload.tool_calls]
        assert ordinals == [0, 7]
        assert all(isinstance(o, int) for o in ordinals)

    def test_an_absent_optional_field_stays_absent(self):
        original = _write(make_observation())

        restored = _json_round_trip(original)

        assert restored.provenance.observed_at == original.provenance.observed_at
        assert restored.provenance.experiment_id == original.provenance.experiment_id


# --------------------------------------------------------------------------
# R2 — ContextRef
# --------------------------------------------------------------------------


class TestR2ContextRefRoundTrip:
    """R2 — `value_digest` survives; the raw `value` never does."""

    def test_the_value_digest_is_restored(self):
        original = _observation()
        expected = original.references.context[0].value_digest

        restored = _json_round_trip(original)

        assert restored.references.context[0].value_digest == expected

    def test_the_stored_bytes_carry_no_raw_value(self):
        original = _observation()
        text = json.dumps(original.to_stored_mapping(), ensure_ascii=False)

        assert RAW_VALUE not in text, "the raw context value reached the stored form"

    def test_the_stored_form_has_no_value_key(self):
        stored = _observation().to_stored_mapping()

        assert "value" not in stored["references"]["context"][0]
        assert "value_digest" in stored["references"]["context"][0]

    def test_all_nine_fields_are_present(self):
        stored = _observation().to_stored_mapping()["references"]["context"][0]

        assert set(stored) == {
            "workspace_id",
            "source_kind",
            "source_identity",
            "source_revision",
            "subject",
            "value_digest",
            "item_kind",
            "truth_state",
            "freshness",
        }

    def test_a_stored_context_ref_carrying_a_raw_value_is_refused(self):
        """§12.4 forbids persisting one; reading it back is not a repair path."""
        stored = _observation().to_stored_mapping()
        stored["references"]["context"][0]["value"] = RAW_VALUE

        with pytest.raises(ev_errors.UnknownField):
            load_stored(stored)


# --------------------------------------------------------------------------
# R3 — recorded_at
# --------------------------------------------------------------------------


class TestR3RecordedAtRoundTrip:
    """R3 — the stamped timestamp survives, and is re-validated on the way in."""

    def test_recorded_at_is_restored(self):
        original = _observation()

        restored = _json_round_trip(original)

        assert restored.provenance.recorded_at == original.provenance.recorded_at
        assert restored.provenance.recorded_at == FIXED_CLOCK

    def test_a_malformed_stored_recorded_at_is_refused(self):
        stored = _observation().to_stored_mapping()
        stored["provenance"]["recorded_at"] = "2026-09-30 00:00:00"

        with pytest.raises(ev_errors.FieldClassViolation):
            load_stored(stored)

    def test_a_stored_form_missing_recorded_at_is_refused(self):
        stored = _observation().to_stored_mapping()
        del stored["provenance"]["recorded_at"]

        with pytest.raises(ev_errors.MissingRequiredField):
            load_stored(stored)


# --------------------------------------------------------------------------
# R4 — the caller boundary is still closed
# --------------------------------------------------------------------------


class TestR4CallerBoundaryRemainsClosed:
    """R4 — the stored loader did not open the caller parser (§14.6.1, R1)."""

    def test_a_caller_supplied_evidence_id_is_refused(self):
        raw = make_observation(evidence_id="ev-" + "a" * 16)

        with pytest.raises(ev_errors.CallerSuppliedIdentity):
            EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)

    def test_a_caller_supplied_recorded_at_is_refused(self):
        raw = make_observation()
        raw["provenance"] = {**raw["provenance"], "recorded_at": FIXED_CLOCK}

        with pytest.raises(ev_errors.CallerSuppliedGeneratedField):
            EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)

    def test_a_caller_supplied_content_digest_is_refused(self):
        raw = make_observation(content_digest=SHA256)

        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)

    def test_a_caller_supplied_record_digest_is_refused(self):
        raw = make_observation(record_digest=SHA256)

        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)

    def test_a_caller_supplied_value_digest_is_refused(self):
        ref = make_context_ref()
        del ref["value"]
        ref["value_digest"] = SHA256
        raw = make_observation(references={"context": [ref]})

        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)

    def test_the_whole_stored_form_is_refused_by_the_caller_parser(self):
        """A stored mapping is not a caller input, and is refused as one.

        It is refused by the rule that names the problem rather than by luck:
        the stored form carries `provenance.recorded_at`, which §15.2 makes
        AI-05's to stamp.
        """
        stored = _observation().to_stored_mapping()

        with pytest.raises(ev_errors.EvidenceError):
            EvidenceRecord.from_mapping(stored, clock=lambda: FIXED_CLOCK)

    def test_admit_still_rejects_a_stored_form(self):
        """The §22.1 outcome path is closed to it too."""
        _supplied = _observation().to_stored_mapping()
        result = admit(
            _supplied, producer_proof=proof_for_record(_supplied),
            clock=lambda: FIXED_CLOCK,
        )

        assert result.outcome.value == "REJECTED"
        assert result.record is None

    def test_admission_of_a_valid_caller_record_is_unaffected(self):
        """The control: R1 was not tightened into refusing ordinary records."""
        _supplied = make_observation()
        result = admit(
            _supplied, producer_proof=proof_for_record(_supplied),
            clock=lambda: FIXED_CLOCK,
        )

        assert result.outcome.value == "ACCEPTED"


# --------------------------------------------------------------------------
# R5 to R7 — tampering
# --------------------------------------------------------------------------


class TestR5StoredFieldTamper:
    """R5 — an operational field altered after the write is detected."""

    def test_a_changed_producer_version_is_refused(self):
        """`producer_version` is excluded from `content_digest` — §15.2.2."""
        stored = _observation().to_stored_mapping()
        stored["provenance"]["producer_version"] = "9.9.9"

        with pytest.raises(StoredIntegrityFailure) as excinfo:
            load_stored(stored)

        assert excinfo.value.reason_code == "STORED_INTEGRITY_FAILURE"

    def test_the_semantic_claim_is_untouched_by_that_tamper(self):
        """The decisive half: this is exactly why `record_digest` must exist.

        A tamper `content_digest` cannot see is the case §17 was written for.
        If the loader checked only the semantic digest, this record would load
        clean and the altered `producer_version` would never be noticed.
        """
        original = _observation()
        altered = replace(
            original,
            provenance=replace(original.provenance, producer_version="9.9.9"),
        )

        assert content_digest(altered) == original.integrity.content_digest
        assert record_digest(altered) != original.integrity.record_digest

    def test_a_changed_artifact_ref_is_refused(self):
        """`artifact_ref` is a LOCATOR, excluded from `content_digest` (§13.1)."""
        stored = _observation().to_stored_mapping()
        stored["artifacts"]["items"][0]["artifact_ref"] = "art-somewhere-else"

        with pytest.raises(StoredIntegrityFailure):
            load_stored(stored)


class TestR6StoredContextDigestTamper:
    """R6 — a substituted `value_digest` does not pass quietly."""

    def test_a_changed_value_digest_is_refused(self):
        stored = _observation().to_stored_mapping()
        stored["references"]["context"][0]["value_digest"] = "d" * 64

        with pytest.raises(StoredIntegrityFailure) as excinfo:
            load_stored(stored)

        assert excinfo.value.reason_code == "STORED_INTEGRITY_FAILURE"

    def test_the_substituted_value_is_shape_valid(self):
        """Proof the refusal came from integrity, not from a shape rule.

        `"d" * 64` satisfies `G-DIGEST`, so a loader that only checked shape
        would have accepted it and returned a record whose `ContextRef` names a
        different item than the one that was read.
        """
        from plugins.evidence import g_digest

        assert g_digest("d" * 64, "value_digest") == "d" * 64

    def test_an_appended_context_ref_is_caught_by_the_digest(self):
        """Editing the set is editing the record, and `record_digest` says so."""
        stored = _observation().to_stored_mapping()
        appended = {**stored["references"]["context"][0], "subject": "git.branch"}
        stored["references"]["context"].append(appended)

        with pytest.raises(StoredIntegrityFailure) as excinfo:
            load_stored(stored)

        assert excinfo.value.reason_code == "STORED_INTEGRITY_FAILURE"


class TestR7GeneratedFieldTamper:
    """R7 — the generated fields are covered by the digest, not just validated."""

    def test_a_changed_evidence_id_is_refused(self):
        """Format-valid: `ev-` plus sixteen lowercase hex, and still caught."""
        stored = _observation().to_stored_mapping()
        stored["identity"]["evidence_id"] = "ev-" + "f" * 16

        with pytest.raises(StoredIntegrityFailure) as excinfo:
            load_stored(stored)

        assert excinfo.value.reason_code == "STORED_INTEGRITY_FAILURE"

    def test_a_changed_recorded_at_is_refused(self):
        """Format-valid timestamp; `recorded_at` is OPERATIONAL, so only
        `record_digest` covers it."""
        stored = _observation().to_stored_mapping()
        stored["provenance"]["recorded_at"] = "2026-01-01T00:00:00Z"

        with pytest.raises(StoredIntegrityFailure) as excinfo:
            load_stored(stored)

        assert excinfo.value.reason_code == "STORED_INTEGRITY_FAILURE"

    def test_a_changed_schema_version_is_refused(self):
        stored = _observation().to_stored_mapping()
        stored["schema_version"] = 2

        with pytest.raises(ev_errors.UnsupportedVocabulary):
            load_stored(stored)

    def test_an_unwritten_record_cannot_be_verified(self):
        """A record with no digests has nothing to verify against (§30 step 12)."""
        unwritten = EvidenceRecord.from_mapping(
            make_observation(), clock=lambda: FIXED_CLOCK
        )

        with pytest.raises(StoredIntegrityFailure):
            verify_stored_integrity(unwritten)

    def test_the_original_still_verifies(self):
        """The control: the tamper tests fail for the tamper, not for the loader."""
        original = _observation()

        assert verify_stored_integrity(original) is None
        assert _json_round_trip(original) == original


# --------------------------------------------------------------------------
# R8 — set and order semantics survive storage
# --------------------------------------------------------------------------


class TestR8SetSemanticsSurviveStorage:
    """R8 — a reordered stored collection is the same record."""

    @staticmethod
    def _multi_context() -> EvidenceRecord:
        return _write(make_observation(references={
            "context": [
                make_context_ref(subject="git.branch", value="v-branch"),
                make_context_ref(subject="git.head", value="v-head"),
            ],
            "decisions": [{"record_ref": "ev-" + "a" * 16}],
        }))

    def test_context_permutation_does_not_move_either_digest(self):
        original = self._multi_context()
        stored = original.to_stored_mapping()

        permuted = copy.deepcopy(stored)
        permuted["references"]["context"].reverse()

        restored = load_stored(permuted)

        assert restored.integrity.content_digest == original.integrity.content_digest
        assert restored.integrity.record_digest == original.integrity.record_digest

    def test_artifacts_permutation_does_not_move_either_digest(self):
        original = _write(make_observation(artifacts={"items": [
            make_artifact(artifact_digest="b" * 64, artifact_ref="art-a"),
            make_artifact(artifact_digest="c" * 64, artifact_ref="art-b"),
        ]}))
        permuted = original.to_stored_mapping()
        permuted["artifacts"]["items"].reverse()

        restored = load_stored(permuted)

        assert restored.integrity.record_digest == original.integrity.record_digest

    def test_supersedes_permutation_does_not_move_either_digest(self):
        original = _write(make_observation(references={"supersedes": [
            {"record_ref": "ev-" + "a" * 16, "correction_reason": "first"},
            {"record_ref": "ev-" + "b" * 16, "correction_reason": "second"},
        ]}))
        permuted = original.to_stored_mapping()
        permuted["references"]["supersedes"].reverse()

        restored = load_stored(permuted)

        assert restored.integrity.record_digest == original.integrity.record_digest

    def test_the_stored_form_emits_sets_in_canonical_order(self):
        original = self._multi_context()

        subjects = [
            ref["subject"]
            for ref in original.to_stored_mapping()["references"]["context"]
        ]

        assert subjects == sorted(subjects)

    def test_a_duplicate_element_in_the_stored_form_is_still_refused(self):
        """§15.4 runs on the stored path too — it was composed, not reimplemented."""
        stored = self._multi_context().to_stored_mapping()
        stored["references"]["context"].append(
            copy.deepcopy(stored["references"]["context"][0])
        )

        with pytest.raises(ev_errors.DuplicateElement):
            load_stored(stored)

    def test_tool_calls_keep_their_ordinal_order_not_their_array_order(self):
        """§11.1: the ordinal is the order, and the array is free to be rewritten.

        The restored tuple is in array order — that is what the parser reads —
        and the *semantic* order is recovered from the ordinals. Both digests
        are unmoved, which is the claim §11.1 makes.
        """
        original = _write(make_execution(payload={"tool_calls[]": [
            {"ordinal": 2, "what_ran": "third", "status": "PASS"},
            {"ordinal": 0, "what_ran": "first", "status": "PASS"},
            {"ordinal": 1, "what_ran": "second", "status": "PASS"},
        ]}))
        reversed_stored = original.to_stored_mapping()
        reversed_stored["payload"]["tool_calls[]"].reverse()

        restored = load_stored(reversed_stored)

        by_ordinal = sorted(restored.payload.tool_calls, key=lambda c: c.ordinal)
        assert [c.what_ran for c in by_ordinal] == ["first", "second", "third"]
        assert restored.integrity.content_digest == original.integrity.content_digest
        assert restored.integrity.record_digest == original.integrity.record_digest


# --------------------------------------------------------------------------
# The stored path keeps the rules the caller path has
# --------------------------------------------------------------------------


class TestTheStoredPathKeepsTheCallerPathsRules:
    """The loader composes B1 and §18.1 rather than replacing either."""

    def test_the_grammars_still_run_on_the_stored_path(self):
        """`producer_version` is `G-IDENT`; a space in it is a shape failure."""
        stored = _observation().to_stored_mapping()
        stored["provenance"]["producer_version"] = "not an identifier"

        with pytest.raises(ev_errors.InvalidIdentifier):
            load_stored(stored)

    def test_an_uppercase_digest_in_the_stored_form_is_refused(self):
        """§14.5.1: uppercase is REJECTED, never normalized — on this path too."""
        stored = _observation().to_stored_mapping()
        stored["integrity"]["record_digest"] = stored["integrity"]["record_digest"].upper()

        with pytest.raises(ev_errors.NonCanonicalDigestCase):
            load_stored(stored)

    def test_the_registry_still_runs_on_the_stored_path(self):
        stored = _observation().to_stored_mapping()
        stored["provenance"]["producer"] = "ai-02"  # not registered for SOURCE_READ

        with pytest.raises(ev_errors.ProducerNotRegistered):
            load_stored(stored)

    def test_the_cross_field_rules_still_run_on_the_stored_path(self):
        stored = _observation().to_stored_mapping()
        stored["provenance"]["actor"] = {"id": "ai-03", "type": "agent"}

        with pytest.raises(ev_errors.ActorTypeNotAdmitted):
            load_stored(stored)

    def test_the_workspace_agreement_rule_still_runs_on_the_stored_path(self):
        """§18.1, reused from the admission boundary rather than restated."""
        stored = _observation().to_stored_mapping()
        stored["references"]["context"][0]["workspace_id"] = WS_OTHER

        with pytest.raises(ev_errors.WorkspaceAgreementViolation):
            load_stored(stored)

    def test_an_unknown_top_level_key_is_refused(self):
        stored = _observation().to_stored_mapping()
        stored["raw_payload"] = {"anything": True}

        with pytest.raises(ev_errors.UnknownField):
            load_stored(stored)

    def test_a_missing_section_is_refused(self):
        stored = _observation().to_stored_mapping()
        del stored["integrity"]

        with pytest.raises(ev_errors.MissingRequiredField):
            load_stored(stored)

    @pytest.mark.parametrize(
        "junk", [None, [], {}, "not a record", 7, True, b"bytes"]
    )
    def test_junk_fails_closed(self, junk):
        with pytest.raises(ev_errors.EvidenceError):
            load_stored(junk)


# --------------------------------------------------------------------------
# Why the projection is not the stored form
# --------------------------------------------------------------------------


class TestTheProjectionIsNotTheStoredForm:
    """The check that settled the design, kept as a test so it cannot drift.

    `record_projection` is a digest input. Reusing it as the storage format
    would couple the on-disk shape to the §15.2 digest table, so a future
    classification change would silently change the format and break the
    round-trip of records already written.
    """

    def test_the_projection_omits_record_digest(self):
        """The decisive difference: a digest MUST NOT be its own input (§17)."""
        record = _observation()

        assert "record_digest" not in record_projection(record)
        assert "record_digest" in record.to_stored_mapping()["integrity"]

    def test_the_projection_is_flat_and_the_stored_form_is_not(self):
        record = _observation()

        assert "binding.source_kind" in record_projection(record)["payload"]
        assert "binding" in record.to_stored_mapping()["payload"]

    def test_the_projection_uses_leaf_paths_for_its_containers(self):
        record = _observation()

        assert "references.context[]" in record_projection(record)
        assert "context" in record.to_stored_mapping()["references"]

    def test_the_projection_spells_reasons_with_brackets(self):
        """A key `DecisionPayload.from_mapping` does not read."""
        record = _write(make_decision())

        assert "reasons[]" in record_projection(record)["payload"]
        assert "reasons" in record.to_stored_mapping()["payload"]

    def test_the_stored_form_covers_every_field_the_projection_does(self):
        """Both are complete over the persisted fields; only one carries the digest."""
        record = _observation()

        projection_leaf_count = len(record_projection(record)["payload"])
        stored_payload = record.to_stored_mapping()["payload"]

        assert set(stored_payload) == {
            "family", "subject", "binding", "read_status", "observed"
        }
        assert projection_leaf_count == 7  # binding splits into three leaves
