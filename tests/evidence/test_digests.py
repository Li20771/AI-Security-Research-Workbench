"""Structural fields and digest origin.

Covers T20a, T20b, T20c (deferred), T21a, T21b, T21c and T22e.

### Why the structural-field tests matter more than they look

`providers/redaction.py` rule 6 is `\\b[A-Za-z0-9_\\-]{32,}\\b`. It matches a
40-character git SHA and a 64-character SHA-256, so applying it to AI-05's
structural fields would replace every digest and every source revision with
`[REDACTED]` — destroying the record while appearing to sanitize it
successfully. B1 implements **no** pattern redaction, and these tests are what
keep it that way: they would fail the moment someone reused the sanitizer here.

### On T20c

T20c asserts that a legitimate 64-hex value in a Class 4 bounded-source field is
`REJECTED`, because rule 6 fires on it. That behaviour belongs to the published
admission rule set, which is the subject of **C-1** — the contract gap recorded
in the B1 preflight and explicitly deferred. B1 has no bounded-source rule set,
so T20c is deferred with it rather than faked.
"""

from __future__ import annotations

import pytest

from plugins.evidence import errors as ev_errors
from plugins.evidence import (
    EvidenceRecord,
    assign_digests,
    content_digest,
    record_digest,
    value_digest_of,
)

pytestmark = pytest.mark.layer1

GIT_SHA = "a" * 39 + "1"
SHA256 = "b" * 64


class TestT20aValidGitSha:
    """T20a — a 40-character commit SHA is accepted, unredacted and unchanged."""

    def test_a_git_sha_in_a_source_revision_is_accepted(self, record_factory, build):
        record = build(
            record_factory(references={"context": [_context(revision=GIT_SHA)]})
        )
        assert len(GIT_SHA) == 40
        assert record.references.context[0].source_revision == GIT_SHA

    def test_a_git_sha_is_not_redacted(self, record_factory, build):
        """The rule-6 hazard, asserted directly."""
        record = build(
            record_factory(references={"context": [_context(revision=GIT_SHA)]})
        )
        assert "[REDACTED]" not in record.references.context[0].source_revision
        assert record.references.context[0].source_revision == GIT_SHA

    def test_a_git_sha_survives_into_the_digest_input(self, record_factory, build):
        from plugins.evidence import content_projection

        record = build(
            record_factory(references={"context": [_context(revision=GIT_SHA)]})
        )
        assert GIT_SHA in str(content_projection(record))

    def test_the_revision_is_unchanged_by_digesting(self, record_factory, build):
        before = _parse(record_factory(references={"context": [_context(revision=GIT_SHA)]}))
        after = assign_digests(before)
        assert (
            before.references.context[0].source_revision
            == after.references.context[0].source_revision
            == GIT_SHA
        )


class TestT20bValidSha256:
    """T20b — a 64-character SHA-256 is accepted, unredacted and unchanged."""

    def test_a_sha256_artifact_digest_is_accepted(self, record_factory, build):
        record = build(record_factory(artifacts={"items": [_artifact(SHA256)]}))
        assert record.artifacts.items[0].artifact_digest == SHA256

    def test_a_sha256_is_not_redacted(self, record_factory, build):
        record = build(record_factory(artifacts={"items": [_artifact(SHA256)]}))
        assert record.artifacts.items[0].artifact_digest == SHA256
        assert "[REDACTED]" not in record.artifacts.items[0].artifact_digest

    def test_a_sha256_is_accepted_as_a_document_revision(self, record_factory, build):
        """Documents use a content digest as the revision, git uses a commit."""
        record = build(
            record_factory(references={"context": [_context(revision=SHA256)]})
        )
        assert record.references.context[0].source_revision == SHA256

    def test_the_ai_05_generated_digests_are_64_character_hex(self, record_factory, build):
        record = build(record_factory())
        assert len(record.integrity.content_digest) == 64
        assert len(record.integrity.record_digest) == 64

    def test_no_redaction_machinery_exists_in_the_package(self):
        """B1 must not have imported the sanitizer's pattern rules.

        A structural check, because the hazard is a future edit rather than a
        present bug: if `redact` were reachable from `plugins.evidence`, the
        redaction of digests would become one careless call away.
        """
        import plugins.evidence as package

        source_modules = [
            package.models,
            package.canonical,
            package.digests,
            package.vocabulary,
            package.errors,
        ]
        for module in source_modules:
            assert not hasattr(module, "redact"), module.__name__
            assert not hasattr(module, "REDACTED"), module.__name__


class TestT20cBoundedSourceRuleSetDeferred:
    """T20c — deferred to C-1.

    The contract says a legitimate 64-hex value in a Class 4 bounded-source field
    is `REJECTED`, because the published rule set fires on it. B1 implements no
    rule set, so asserting that here would either fail or require inventing the
    rules C-1 is about. Recorded as an explicit deferral rather than a silent
    gap.
    """

    @pytest.mark.skip(
        reason="C-1: requires the published admission rule set, deferred out of B1"
    )
    def test_a_64_hex_value_in_a_bounded_source_field_is_rejected(self):
        raise AssertionError("unreachable until C-1 is ratified")


class TestT21StructuralFieldShape:
    """T21a/b/c — wrong length, wrong charset, and wrong case are all REJECTED."""

    @pytest.mark.parametrize("length", [0, 1, 39, 41, 63, 65, 128])
    def test_t21a_wrong_length_is_rejected(self, record_factory, length):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(references={"context": [_context(revision="a" * length)]}))

    def test_t21a_wrong_length_is_rejected_for_a_sha256_field(self, record_factory):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(artifacts={"items": [_artifact("b" * 63)]}))

    @pytest.mark.parametrize(
        "value",
        [
            "g" * 40,
            "z" * 64,
            "a" * 39 + "-",
            "a" * 39 + " ",
            "a" * 39 + "_",
            "sha256:" + "a" * 32,
        ],
    )
    def test_t21b_non_hex_is_rejected(self, record_factory, value):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(references={"context": [_context(revision=value)]}))

    def test_t21c_uppercase_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.NonCanonicalDigestCase):
            _parse(
                record_factory(
                    references={"context": [_context(revision="A" * 39 + "1")]}
                )
            )

    def test_t21c_uppercase_is_a_shape_failure_and_not_a_redaction(self, record_factory):
        """The rejection is `NonCanonicalDigestCase`, which is an
        `InvalidDigestShape` — a shape failure, not a sanitization outcome."""
        with pytest.raises(ev_errors.InvalidDigestShape) as excinfo:
            _parse(record_factory(artifacts={"items": [_artifact("B" * 64)]}))
        assert isinstance(excinfo.value, ev_errors.NonCanonicalDigestCase)
        assert excinfo.value.reason_code == "NON_CANONICAL_DIGEST_CASE"

    def test_t21c_uppercase_is_never_normalized(self, record_factory):
        """The decisive half: no record is produced with a lowered value.

        If normalization happened, this would return a record whose digest is
        lowercase — and the caller would never learn their value was rewritten.
        """
        raw = record_factory(
            references={"context": [_context(revision="A" * 39 + "1")]}
        )
        with pytest.raises(ev_errors.NonCanonicalDigestCase):
            _parse(raw)
        # Nothing was produced, so nothing was rewritten.
        assert raw["references"]["context"][0]["source_revision"] == "A" * 39 + "1"

    def test_the_lowercase_form_of_the_same_value_is_accepted(self, record_factory):
        """The control: the rejection is about case, not about the value."""
        record = _parse(
            record_factory(references={"context": [_context(revision="a" * 39 + "1")]})
        )
        assert record.references.context[0].source_revision == "a" * 39 + "1"

    def test_a_non_string_structural_field_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.InvalidDigestShape):
            _parse(record_factory(artifacts={"items": [_artifact(12345)]}))


class TestT22eAi05GeneratedDigestsAreAccepted:
    """T22e — the positive control for T22d.

    Without this, T22d would be satisfied by a system that rejects every digest.
    T22e proves that AI-05 computing a digest from content it admitted is
    accepted, so T22d's rejection is about **origin** rather than about digests.
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
        record = build(
            record_factory(references={"context": [_context(value="PASS")]})
        )
        assert record.references.context[0].value_digest == value_digest_of("PASS")

    def test_two_different_values_have_different_value_digests(self):
        """§12.2 — value participates in item identity."""
        assert value_digest_of("PASS") != value_digest_of("FAIL")

    def test_the_raw_value_is_not_stored_on_the_reference(self, record_factory, build):
        """§12.4 — only the digest crosses into the record.

        The value is deliberately distinctive rather than `PASS`, because `PASS`
        is also a legitimate `truth_state` token and the assertion would be
        satisfied by coincidence rather than by the property under test.
        """
        distinctive = "A-CLAIM-THAT-APPEARS-NOWHERE-ELSE"
        record = build(
            record_factory(references={"context": [_context(value=distinctive)]})
        )
        reference = record.references.context[0]
        assert not hasattr(reference, "value"), (
            "the stored ContextRef has no value field (§12.4)"
        )
        stored = {str(getattr(reference, f)) for f in reference.__slots__}
        assert distinctive not in stored, "the raw value reached the record"

    def test_the_two_digests_answer_different_questions(self, record_factory, build):
        """§16/§17 — a single digest cannot serve both jobs."""
        a = build(record_factory())
        b = build(
            record_factory(
                provenance=_prov(recorded_at_field=None, experiment_id="EXP-OTHER")
            )
        )
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


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _parse(raw):
    return EvidenceRecord.from_mapping(raw, clock=lambda: "2026-09-29T00:00:00Z")


def _context(subject="git.head", value="PASS", revision=GIT_SHA):
    return {
        "workspace_id": "ws-1",
        "source_kind": "git_current_state",
        "source_identity": "git",
        "source_revision": revision,
        "subject": subject,
        "value": value,
        "item_kind": "FACT",
        "truth_state": "PASS",
        "freshness": "CURRENT",
    }


def _artifact(digest=SHA256):
    return {
        "artifact_digest": digest,
        "role": "raw-log",
        "external": False,
        "owner_workspace_id": None,
        "artifact_ref": "art-0001",
    }


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
    prov.update({k: v for k, v in overrides.items() if v is not None})
    return prov
