"""Structural fields, digest origin, and the conditional revision rule.

Covers T20a, T20b, T20c, T21a, T21b, T21c, T22d, T22e, T49 and T57.

### Why the structural-field tests matter more than they look

`providers/redaction.py` rule 6 is `\\b[A-Za-z0-9_\\-]{32,}\\b`. It matches a
40-character git SHA and a 64-character SHA-256, so applying it to AI-05's
structural fields would replace every digest and every source revision with
`[REDACTED]` — destroying the record while appearing to sanitize it
successfully. B1 implements **no** pattern redaction, and these tests are what
keep it that way.

### On T20c

T20c asserts that a legitimate 64-hex value in a Class 4 field is `REJECTED`
because rule 6 fires on it. That belongs to the published admission rule set,
which **C-1** was — and which AI-05 Amendment 3 published (§14.10). T20c was
carried here as a static skip while the set did not exist; it is a real assertion
now, with the expectation it always stated, and it is asserted through `admit()`
because admission is where step 7 runs.
"""

from __future__ import annotations

import pytest

from trust_harness import proof_for_record

from plugins.evidence import errors as ev_errors
from plugins.evidence import (
    EvidenceRecord,
    assign_digests,
    content_digest,
    record_digest,
    value_digest_of,
)
from tests.evidence.conftest import (
    FIXED_CLOCK,
    GIT_SHA,
    SHA256,
    make_artifact,
    make_context_ref,
    make_observation,
)

pytestmark = pytest.mark.layer1

DOCUMENT_KIND = "exit_report"


def _parse(raw):
    return EvidenceRecord.from_mapping(raw, clock=lambda: "2026-09-30T00:00:00Z")


class TestT20aValidGitSha:
    """T20a — a 40-character commit SHA is accepted, unredacted and unchanged."""

    def test_a_git_sha_in_a_source_revision_is_accepted(self, record_factory, build):
        record = build(record_factory(references={
            "context": [make_context_ref(source_revision=GIT_SHA)]}))
        assert record.references.context[0].source_revision == GIT_SHA

    def test_a_git_sha_is_not_redacted(self, record_factory, build):
        record = build(record_factory(references={
            "context": [make_context_ref(source_revision=GIT_SHA)]}))
        assert record.references.context[0].source_revision == GIT_SHA
        assert "[REDACTED]" not in record.references.context[0].source_revision

    def test_a_git_sha_survives_into_the_digest_input(self, record_factory, build):
        from plugins.evidence import content_projection

        record = build(record_factory(references={
            "context": [make_context_ref(source_revision=GIT_SHA)]}))
        assert GIT_SHA in str(content_projection(record))


class TestT20bValidSha256:
    """T20b — a 64-character SHA-256 is accepted, unredacted and unchanged."""

    def test_a_sha256_artifact_digest_is_accepted(self, record_factory, build):
        record = build(record_factory(artifacts={"items": [make_artifact()]}))
        assert record.artifacts.items[0].artifact_digest == SHA256

    def test_a_sha256_is_not_redacted(self, record_factory, build):
        record = build(record_factory(artifacts={"items": [make_artifact()]}))
        assert record.artifacts.items[0].artifact_digest == SHA256
        assert "[REDACTED]" not in record.artifacts.items[0].artifact_digest

    def test_a_sha256_is_accepted_as_a_document_revision(self, record_factory, build):
        """Documents use a content digest as the revision, git uses a commit."""
        record = build(record_factory(references={"context": [
            make_context_ref(source_kind=DOCUMENT_KIND, source_revision=SHA256)]}))
        assert record.references.context[0].source_revision == SHA256

    def test_the_ai_05_generated_digests_are_64_character_hex(self, record_factory, build):
        record = build(record_factory())
        assert len(record.integrity.content_digest) == 64
        assert len(record.integrity.record_digest) == 64

    def test_no_redaction_machinery_exists_in_the_package(self):
        """A structural check, because the hazard is a future edit."""
        import plugins.evidence as package

        for module in (package.models, package.canonical, package.digests,
                       package.vocabulary, package.errors, package.grammar):
            assert not hasattr(module, "redact"), module.__name__
            assert not hasattr(module, "REDACTED"), module.__name__


class TestT20cBoundedSourceRuleSet:
    """T20c — a legitimate 64-hex value in a Class 4 field is REJECTED.

    §14.5.1 declares this over-rejection deliberate: 64 lowercase hex characters
    are only safe where provenance is constrained, and rule C1-R06 cannot tell a
    digest from a token. It MUST NOT be "fixed" by narrowing the rule (§31.1).
    """

    def test_a_64_hex_value_in_a_bounded_source_field_is_rejected(self):
        from plugins.evidence import AdmissionOutcome, admit

        raw = make_observation()
        raw["payload"]["observed"] = SHA256

        result = admit(
            raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
        )

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "ADMISSION_RULE_VIOLATION"
        assert result.record is None

    def test_the_same_value_stays_accepted_in_a_structural_field(self):
        """The other half, and the reason this is a boundary and not a bug: T20b's
        Class 1 fields are never scanned, so the same 64-hex value is admitted
        there. T20b and T20c are one rule seen from two sides."""
        from plugins.evidence import AdmissionOutcome, admit

        raw = make_observation(
            artifacts={
                "items": [
                    {
                        "artifact_digest": SHA256,
                        "external": False,
                        "owner_workspace_id": None,
                        "artifact_ref": "art-0001",
                    }
                ]
            }
        )

        assert (
            admit(
                raw, producer_proof=proof_for_record(raw), clock=lambda: FIXED_CLOCK
            ).outcome
            is AdmissionOutcome.ACCEPTED
        )


class TestT21StructuralFieldShape:
    """T21a/b/c — wrong length, wrong charset and wrong case are all REJECTED."""

    @pytest.mark.parametrize("length", [0, 1, 39, 41, 63, 65, 128])
    def test_t21a_wrong_length_is_rejected(self, record_factory, length):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(references={"context": [
                make_context_ref(source_revision="a" * length)]}))

    def test_t21a_wrong_length_is_rejected_for_a_sha256_field(self, record_factory):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(artifacts={"items": [
                make_artifact(artifact_digest="b" * 63)]}))

    @pytest.mark.parametrize(
        "value",
        ["g" * 40, "z" * 64, "a" * 39 + "-", "a" * 39 + " ", "a" * 39 + "_"],
    )
    def test_t21b_non_hex_is_rejected(self, record_factory, value):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(references={"context": [
                make_context_ref(source_revision=value)]}))

    def test_t21c_uppercase_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.NonCanonicalDigestCase):
            _parse(record_factory(references={"context": [
                make_context_ref(source_revision="A" * 39 + "1")]}))

    def test_t21c_uppercase_is_a_shape_failure_and_not_a_redaction(self, record_factory):
        with pytest.raises(ev_errors.InvalidDigestShape) as excinfo:
            _parse(record_factory(artifacts={"items": [
                make_artifact(artifact_digest="B" * 64)]}))
        assert isinstance(excinfo.value, ev_errors.NonCanonicalDigestCase)
        assert excinfo.value.reason_code == "NON_CANONICAL_DIGEST_CASE"

    def test_t21c_uppercase_is_never_normalized(self, record_factory):
        """The decisive half: no record is produced with a lowered value."""
        raw = record_factory(references={"context": [
            make_context_ref(source_revision="A" * 39 + "1")]})
        with pytest.raises(ev_errors.NonCanonicalDigestCase):
            _parse(raw)
        assert raw["references"]["context"][0]["source_revision"] == "A" * 39 + "1"

    def test_the_lowercase_form_of_the_same_value_is_accepted(self, record_factory):
        record = _parse(record_factory(references={"context": [
            make_context_ref(source_revision="a" * 39 + "1")]}))
        assert record.references.context[0].source_revision == "a" * 39 + "1"

    def test_a_non_string_structural_field_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(artifacts={"items": [
                make_artifact(artifact_digest=12345)]}))


class TestT49SourceRevisionIsConditional:
    """T49 — the revision width is decided by the sibling `source_kind` (§12.1).

    Before Amendment 1 the field accepted either width for any kind. Every one of
    AI-03's six members is exercised here, because a rule that is total over six
    values cannot be tested with two.
    """

    @pytest.mark.parametrize("kind", ["git_current_state", "git_history"])
    def test_a_git_kind_requires_forty(self, record_factory, build, kind):
        record = build(record_factory(references={"context": [
            make_context_ref(source_kind=kind, source_revision=GIT_SHA)]}))
        assert record.references.context[0].source_revision == GIT_SHA

    @pytest.mark.parametrize(
        "kind", ["master_roadmap", "capability_inventory", "design_freeze", "exit_report"]
    )
    def test_a_document_kind_requires_sixty_four(self, record_factory, build, kind):
        record = build(record_factory(references={"context": [
            make_context_ref(source_kind=kind, source_revision=SHA256)]}))
        assert record.references.context[0].source_revision == SHA256

    @pytest.mark.parametrize("kind", ["git_current_state", "git_history"])
    def test_a_git_kind_rejects_sixty_four(self, record_factory, kind):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(references={"context": [
                make_context_ref(source_kind=kind, source_revision=SHA256)]}))

    @pytest.mark.parametrize(
        "kind", ["master_roadmap", "capability_inventory", "design_freeze", "exit_report"]
    )
    def test_a_document_kind_rejects_forty(self, record_factory, kind):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(references={"context": [
                make_context_ref(source_kind=kind, source_revision=GIT_SHA)]}))

    def test_a_source_kind_outside_ai_03_is_rejected(self, record_factory):
        """T50. `SourceKind` is closed; a seventh member is an amendment."""
        with pytest.raises(ev_errors.UnsupportedVocabulary):
            _parse(record_factory(references={"context": [
                make_context_ref(source_kind="made_up_source")]}))

    def test_both_source_revision_paths_behave_identically(self, record_factory):
        """T57. Same `source_kind` and revision pair, same outcome on both paths.

        The two paths call one function, so this is identical by construction
        rather than by agreement — and the test is what holds that construction
        in place.
        """
        for kind, ok_len, bad_len in (
            ("git_current_state", GIT_SHA, SHA256),
            ("git_history", GIT_SHA, SHA256),
            ("master_roadmap", SHA256, GIT_SHA),
            ("capability_inventory", SHA256, GIT_SHA),
            ("design_freeze", SHA256, GIT_SHA),
            ("exit_report", SHA256, GIT_SHA),
        ):
            ctx_ok = make_context_ref(source_kind=kind, source_revision=ok_len)
            bind_ok = {"source_kind": kind, "source_identity": "git",
                       "source_revision": ok_len}
            ctx_bad = make_context_ref(source_kind=kind, source_revision=bad_len)
            bind_bad = {"source_kind": kind, "source_identity": "git",
                        "source_revision": bad_len}

            _parse(record_factory(references={"context": [ctx_ok]}))
            _parse(record_factory(payload={
                "family": "SOURCE_READ", "subject": "s", "observed": "o",
                "read_status": "READ", "binding": bind_ok,
            }))

            with pytest.raises(ev_errors.InvalidDigestShape):
                _parse(record_factory(references={"context": [ctx_bad]}))
            with pytest.raises(ev_errors.InvalidDigestShape):
                _parse(record_factory(payload={
                    "family": "SOURCE_READ", "subject": "s", "observed": "o",
                    "read_status": "READ", "binding": bind_bad,
                }))


class TestT22eAi05GeneratedDigestsAreAccepted:
    """T22e — the positive control for T22d.

    Without this, T22d would be satisfied by a system that rejects every digest.
    """

    def test_ai_05_computes_both_digests(self, record_factory, build):
        record = build(record_factory())
        assert record.integrity.content_digest is not None
        assert record.integrity.record_digest is not None

    def test_the_computed_digests_are_valid_lowercase_hex(self, record_factory, build):
        record = build(record_factory())
        for value in (record.integrity.content_digest, record.integrity.record_digest):
            assert len(value) == 64
            assert value == value.lower()
            assert all(c in "0123456789abcdef" for c in value)

    def test_value_digest_is_computed_from_the_admitted_value(self, record_factory, build):
        record = build(record_factory(references={
            "context": [make_context_ref(value="PASS")]}))
        assert record.references.context[0].value_digest == value_digest_of("PASS")

    def test_two_different_values_have_different_value_digests(self):
        """§12.2 — value participates in item identity."""
        assert value_digest_of("PASS") != value_digest_of("FAIL")

    def test_the_raw_value_is_not_stored_on_the_reference(self, record_factory, build):
        """§12.4 — only the digest crosses into the record."""
        distinctive = "A-CLAIM-THAT-APPEARS-NOWHERE-ELSE"
        record = build(record_factory(references={
            "context": [make_context_ref(value=distinctive)]}))
        reference = record.references.context[0]
        assert not hasattr(reference, "value")
        stored = {str(getattr(reference, f)) for f in reference.__slots__}
        assert distinctive not in stored

    def test_the_two_digests_answer_different_questions(self, record_factory, build):
        """§16/§17 — a single digest cannot serve both jobs."""
        a = build(record_factory())
        b = build(record_factory(provenance={
            **record_factory()["provenance"], "experiment_id": "EXP-OTHER"}))
        assert content_digest(a) == content_digest(b)
        assert record_digest(a) != record_digest(b)

    def test_digesting_is_not_mutating(self, record_factory):
        """§19 — `assign_digests` returns a copy; the input is untouched."""
        parsed = _parse(record_factory())
        assert parsed.integrity.content_digest is None
        digested = assign_digests(parsed)
        assert parsed.integrity.content_digest is None, "the original was mutated"
        assert digested.integrity.content_digest is not None

    def test_a_record_digest_is_never_its_own_input(self, record_factory, build):
        from plugins.evidence import record_projection

        record = build(record_factory())
        assert "record_digest" not in record_projection(record)
        assert "content_digest" in record_projection(record)
