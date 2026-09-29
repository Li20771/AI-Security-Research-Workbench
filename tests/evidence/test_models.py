"""The record model: identity, correlation, and strictness.

Covers T5 and T6, plus the model-level strictness that §13.8 and §30 depend on.

The two identity tests are deliberately about **digest behaviour**, not field
presence. `experiment_id` and `evidence_id` are the two fields most likely to be
"unified" with their neighbours by a well-meaning refactor, because they look
like the fields next to them. They are not: one is AI-05's own record identity
and one is operational correlation metadata, and the digests have to show it.
"""

from __future__ import annotations

import pytest

from plugins.evidence import errors as ev_errors
from plugins.evidence import EvidenceRecord, assign_digests

pytestmark = pytest.mark.layer1


class TestT5EvidenceIdIsGeneratedAndNonSemantic:
    """T5 — identity is not semantics.

    Changing `evidence_id` must leave `content_digest` untouched and change
    `record_digest`. If `evidence_id` were content-derived, two records making
    the same claim would be indistinguishable — but they are two observations,
    not one.
    """

    def test_ai_05_generates_the_id(self, record_factory):
        record = EvidenceRecord.from_mapping(record_factory(), clock=lambda: "t")
        assert record.evidence_id is not None
        assert record.evidence_id.startswith("ev-")

    def test_two_parses_of_the_same_supplied_record_get_different_ids(
        self, record_factory
    ):
        raw = record_factory()
        first = EvidenceRecord.from_mapping(raw, clock=lambda: "t")
        second = EvidenceRecord.from_mapping(raw, clock=lambda: "t")
        assert first.evidence_id != second.evidence_id

    def test_the_id_is_not_content_derived(self, record_factory, build):
        """Same content, different ids — so the id is not a function of content."""
        raw = record_factory()
        a = build(raw)
        b = build(raw)
        assert a.evidence_id != b.evidence_id
        assert a.integrity.content_digest == b.integrity.content_digest

    def test_changing_the_id_leaves_content_digest_and_changes_record_digest(
        self, record_factory, build
    ):
        raw = record_factory()
        a = build(raw, evidence_id="ev-aaaaaaaaaaaaaaaa")
        b = build(raw, evidence_id="ev-bbbbbbbbbbbbbbbb")

        assert a.integrity.content_digest == b.integrity.content_digest, (
            "evidence_id is identity, not content; it must not enter the "
            "semantic digest"
        )
        assert a.integrity.record_digest != b.integrity.record_digest, (
            "evidence_id IS a stored field, so it must be covered by the "
            "integrity digest"
        )

    def test_evidence_id_is_absent_from_the_content_projection(self, record_factory, build):
        from plugins.evidence import content_projection

        assert "evidence_id" not in content_projection(build(record_factory()))

    def test_a_caller_supplied_evidence_id_is_rejected(self, record_factory):
        raw = record_factory(evidence_id="ev-attacker-supplied")
        with pytest.raises(ev_errors.CallerSuppliedIdentity):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")


class TestT6ExperimentIdIsOperational:
    """T6 — correlation, not identity, and not content.

    Two records making the same claim under two experiment labels are **one
    claim recorded twice**, and the store must be able to say so. That is only
    expressible if `experiment_id` is outside the semantic digest.
    """

    def test_same_claim_different_experiment_gives_the_same_content_digest(
        self, record_factory, build
    ):
        a = build(record_factory(provenance=_prov(experiment_id="EXP-20260929-0001")))
        b = build(record_factory(provenance=_prov(experiment_id="EXP-20260929-0002")))

        assert a.integrity.content_digest == b.integrity.content_digest, (
            "which task a record was filed under does not change what it claims"
        )
        assert a.integrity.record_digest != b.integrity.record_digest, (
            "experiment_id IS stored, so the integrity digest must cover it"
        )

    def test_experiment_id_is_absent_from_the_content_projection(self, record_factory, build):
        from plugins.evidence import content_projection

        projection = content_projection(build(record_factory()))
        assert "experiment_id" not in projection

    def test_a_null_experiment_id_is_legal(self, record_factory, build):
        raw = record_factory(provenance=_prov(experiment_id=None))
        assert build(raw).provenance.experiment_id is None

    def test_correlation_is_not_uniqueness(self, record_factory, build):
        """Many records may share one experiment id (§8)."""
        raw = record_factory()
        a, b = build(raw), build(raw)
        assert a.provenance.experiment_id == b.provenance.experiment_id
        assert a.evidence_id != b.evidence_id


class TestT8OperationalFieldsAreIndividuallyExcludedFromTheContentDigest:
    """T8 — each operational field is asserted **separately**.

    A single combined assertion would pass while three of the four fields were
    wrong. Each of `recorded_at`, `experiment_id`, `producer_version` and
    `artifact_ref` gets its own claim.
    """

    def test_recorded_at(self, record_factory):
        a = _digests(record_factory(), clock="2026-09-29T00:00:00Z")
        b = _digests(record_factory(), clock="2026-09-30T00:00:00Z")
        assert a["content"] == b["content"]
        assert a["record"] != b["record"]

    def test_experiment_id(self, record_factory):
        a = _digests(record_factory(provenance=_prov(experiment_id="EXP-A")))
        b = _digests(record_factory(provenance=_prov(experiment_id="EXP-B")))
        assert a["content"] == b["content"]
        assert a["record"] != b["record"]

    def test_producer_version(self, record_factory):
        a = _digests(record_factory(provenance=_prov(producer_version="1.0.0")))
        b = _digests(record_factory(provenance=_prov(producer_version="2.0.0")))
        assert a["content"] == b["content"], (
            "a version is a property of the instrument, not of the claim"
        )
        assert a["record"] != b["record"]

    def test_artifact_ref(self, record_factory):
        a = _digests(
            record_factory(artifacts={"items": [_artifact(artifact_ref="art-a")]})
        )
        b = _digests(
            record_factory(artifacts={"items": [_artifact(artifact_ref="art-b")]})
        )
        assert a["content"] == b["content"], (
            "content_digest is location-independent: where the bytes live is not "
            "part of what the record claims (§15.3)"
        )
        assert a["record"] != b["record"], (
            "record_digest exists precisely so that repointing a locator is "
            "detectable rather than invisible"
        )

    def test_producer_is_semantic_unlike_producer_version(self, record_factory):
        """The contrast that a name-similarity refactor would destroy."""
        a = _digests(record_factory(provenance=_prov(producer="ai-02")))
        b = _digests(record_factory(provenance=_prov(producer="ai-03")))
        assert a["content"] != b["content"], (
            "a different observer makes different evidence — AI-02 §8.3: "
            "'Provider documentation is not Workbench evidence'"
        )


class TestT22dCallerSuppliedGeneratedFields:
    """T22d — a caller may not supply a field AI-05 generates (§14.6.1, R1).

    Paired with T22e in `test_digests.py`, which proves the rejection is about
    *origin* and not about digests being refused generally.
    """

    def test_a_supplied_content_digest_is_rejected(self, record_factory):
        raw = record_factory(content_digest="b" * 64)
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")

    def test_a_supplied_record_digest_is_rejected(self, record_factory):
        raw = record_factory(record_digest="b" * 64)
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")

    def test_a_supplied_value_digest_is_rejected(self, record_factory):
        ref = _context_ref()
        ref["value_digest"] = "b" * 64
        raw = record_factory(references={"context": [ref]})
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")

    def test_a_secret_derived_digest_cannot_be_adopted_by_looking_valid(
        self, record_factory
    ):
        """The residual §14.8 names cannot be closed by a detector.

        No component can tell a digest of a secret from any other digest, so the
        protection is not pattern matching — it is that there is no field in
        which a caller can substitute one. The value below is a *shaped* digest
        and is refused for its origin, not its appearance.
        """
        import hashlib

        shaped = hashlib.sha256(b"hunter2").hexdigest()
        assert len(shaped) == 64 and shaped == shaped.lower()

        raw = record_factory(content_digest=shaped)
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")

    def test_a_caller_supplied_recorded_at_is_rejected(self, record_factory):
        prov = _prov()
        prov["recorded_at"] = "2020-01-01T00:00:00Z"
        with pytest.raises(ev_errors.CallerSuppliedGeneratedField):
            EvidenceRecord.from_mapping(
                record_factory(provenance=prov), clock=lambda: "t"
            )


class TestModelStrictness:
    """§30 step 1 and §13.8 — undeclared fields are refused, never reshaped.

    These support T1-T3, which are B2's admission tests and are not claimed here;
    what is asserted now is the model-level strictness they will build on.
    """

    def test_an_unknown_top_level_field_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.UnknownField):
            EvidenceRecord.from_mapping(
                record_factory(notes="something"), clock=lambda: "t"
            )

    def test_a_raw_payload_field_is_rejected_not_reshaped(self, record_factory):
        """§13.8 — AI-05 never converts supplied content into an artifact."""
        with pytest.raises(ev_errors.UnknownField):
            EvidenceRecord.from_mapping(
                record_factory(raw_response="<200 MB of provider output>"),
                clock=lambda: "t",
            )

    def test_artifact_availability_is_rejected(self, record_factory):
        """§13.3 — availability is a query-time fact, never a record field."""
        item = _artifact()
        item["availability"] = "RETAINED"
        with pytest.raises(ev_errors.RawContentRejected):
            EvidenceRecord.from_mapping(
                record_factory(artifacts={"items": [item]}), clock=lambda: "t"
            )

    def test_a_missing_required_field_is_rejected(self, record_factory):
        raw = record_factory()
        del raw["payload"]["observed"]
        with pytest.raises(ev_errors.MissingRequiredField):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")

    def test_an_unsupported_schema_version_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.UnsupportedVocabulary):
            EvidenceRecord.from_mapping(
                record_factory(schema_version=2), clock=lambda: "t"
            )

    def test_a_payload_of_the_wrong_kind_is_rejected(self, record_factory):
        """§11 — the payload is typed per kind."""
        raw = record_factory(kind="DECISION")
        with pytest.raises(ev_errors.UnknownField):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")

    def test_an_external_artifact_requires_an_owner(self, record_factory):
        """§13.6 — an external dependency is declared, never implicit."""
        item = _artifact(external=True, owner_workspace_id=None)
        with pytest.raises(ev_errors.MissingRequiredField):
            EvidenceRecord.from_mapping(
                record_factory(artifacts={"items": [item]}), clock=lambda: "t"
            )


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _prov(**overrides):
    prov = {
        "producer": "ai-02",
        "producer_version": "1.0.0",
        "producer_type": "service",
        "actor": {"id": "provider:deepseek", "type": "service"},
        "workspace_id": "ws-1",
        "experiment_id": "EXP-20260929-0001",
        "observed_at": "2026-09-29T00:00:00Z",
    }
    prov.update(overrides)
    return prov


def _context_ref(**overrides):
    ref = {
        "workspace_id": "ws-1",
        "source_kind": "git_current_state",
        "source_identity": "git",
        "source_revision": "a" * 39 + "1",
        "subject": "git.head",
        "value": "PASS",
        "item_kind": "FACT",
        "truth_state": "PASS",
        "freshness": "CURRENT",
    }
    ref.update(overrides)
    return ref


def _artifact(**overrides):
    item = {
        "artifact_digest": "b" * 64,
        "role": "raw-log",
        "external": False,
        "owner_workspace_id": None,
        "artifact_ref": "art-0001",
    }
    item.update(overrides)
    return item


def _digests(raw, *, clock="2026-09-29T00:00:00Z"):
    record = assign_digests(EvidenceRecord.from_mapping(raw, clock=lambda: clock))
    return {
        "content": record.integrity.content_digest,
        "record": record.integrity.record_digest,
    }
