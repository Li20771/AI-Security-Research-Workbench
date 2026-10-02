"""AI-10 §7 — the claim: bounds, set semantics and the fields it must not have.

The claim is declared analysis material. These tests hold the two halves of
that apart: what a claim may SAY (a bounded statement, declared references,
declared check targets) and what it may never say (a confidence, a rank, a
recommendation).
"""

from __future__ import annotations

import dataclasses

import pytest

from review.claim import ReviewClaim, VerificationTarget, claim_content_digest
from review.errors import (
    InvalidClaim,
    InvalidIdentifier,
    InvalidReference,
    InvalidTarget,
)
from review.vocabulary import (
    FORBIDDEN_CLAIM_FIELDS,
    MAX_EVIDENCE_REFS_PER_CLAIM,
    MAX_STATEMENT_CHARS,
    MAX_TARGET_DESCRIPTION_CHARS,
    MAX_VERIFICATION_TARGETS_PER_CLAIM,
)

from tests.review.conftest import claim, sha256, target

pytestmark = pytest.mark.layer1


class TestClaimShape:
    def test_a_minimal_claim_is_valid(self):
        built = claim()
        assert built.claim_id == "c1"
        assert built.evidence_refs == ()
        assert built.verification_targets == ()

    def test_claim_id_is_bounded_and_opaque(self):
        for bad in ("", "has space", "a" * 65, None, 7):
            with pytest.raises(InvalidIdentifier):
                ReviewClaim(claim_id=bad, statement="a statement")

    def test_statement_is_required_and_bounded(self):
        with pytest.raises(InvalidClaim):
            ReviewClaim(claim_id="c1", statement="")
        with pytest.raises(InvalidClaim):
            ReviewClaim(claim_id="c1", statement="x" * (MAX_STATEMENT_CHARS + 1))
        assert ReviewClaim(
            claim_id="c1", statement="x" * MAX_STATEMENT_CHARS
        ).statement

    def test_statement_must_be_text(self):
        with pytest.raises(InvalidClaim):
            ReviewClaim(claim_id="c1", statement=42)

    def test_schema_version_is_closed(self):
        with pytest.raises(InvalidClaim):
            ReviewClaim(claim_id="c1", statement="a statement", schema_version=2)

    def test_there_is_no_field_for_a_verdict(self):
        fields = {field.name for field in dataclasses.fields(ReviewClaim)}
        assert fields == {
            "schema_version",
            "claim_id",
            "statement",
            "evidence_refs",
            "verification_targets",
        }


class TestEvidenceReferences:
    def test_a_declared_reference_is_accepted(self):
        built = claim(evidence_refs=(sha256("a"), "ref:some-artifact-token"))
        assert len(built.evidence_refs) == 2

    def test_raw_content_is_not_a_reference(self):
        for bad in ("the parser rejects trailing bytes", "AWS_SECRET=abc", "", "sha256:xyz"):
            with pytest.raises(InvalidReference):
                claim(evidence_refs=(bad,))

    def test_references_are_bounded(self):
        with pytest.raises(InvalidClaim):
            claim(
                evidence_refs=tuple(
                    "sha256:" + f"{index:064x}"
                    for index in range(MAX_EVIDENCE_REFS_PER_CLAIM + 1)
                )
            )

    def test_order_does_not_change_the_reference_set(self):
        first = claim(evidence_refs=(sha256("a"), sha256("b")))
        second = claim(evidence_refs=(sha256("b"), sha256("a")))
        assert first.evidence_refs == second.evidence_refs
        assert claim_content_digest(first) == claim_content_digest(second)


class TestVerificationTargets:
    def test_a_declared_target_is_accepted(self):
        built = claim(verification_targets=(target(),))
        assert built.verification_targets[0].target_id == "t1"

    def test_a_target_is_a_declaration_not_an_operation(self):
        fields = {field.name for field in dataclasses.fields(VerificationTarget)}
        assert fields == {"schema_version", "target_id", "description"}
        for forbidden in ("operation", "permission_level", "tool_id", "command", "actor"):
            assert forbidden not in fields

    def test_target_description_is_bounded_and_single_line(self):
        with pytest.raises(InvalidTarget):
            VerificationTarget(target_id="t1", description="x" * (MAX_TARGET_DESCRIPTION_CHARS + 1))
        with pytest.raises(InvalidTarget):
            VerificationTarget(target_id="t1", description="two\nlines")

    def test_targets_are_keyed_and_a_duplicate_is_refused(self):
        with pytest.raises(InvalidClaim):
            claim(verification_targets=(target("t1"), target("t1", description="other")))

    def test_targets_are_bounded(self):
        with pytest.raises(InvalidClaim):
            claim(
                verification_targets=tuple(
                    target(f"t{index}")
                    for index in range(MAX_VERIFICATION_TARGETS_PER_CLAIM + 1)
                )
            )

    def test_targets_must_be_targets(self):
        with pytest.raises(InvalidClaim):
            claim(verification_targets=("t1",))


class TestSetSemantics:
    def test_duplicate_references_are_refused_rather_than_deduplicated(self):
        with pytest.raises(InvalidClaim):
            claim(evidence_refs=(sha256("a"), sha256("a")))

    def test_duplicate_claims_are_the_materials_rule(self):
        # A claim's own identifiers are unique by construction; the material
        # enforces uniqueness across its claims (tests/review/test_material.py).
        assert claim(claim_id="c1").claim_id == "c1"


class TestForbiddenFields:
    @pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_CLAIM_FIELDS))
    def test_a_verdict_field_is_refused_by_name(self, forbidden):
        raw = {
            "schema_version": 1,
            "claim_id": "c1",
            "statement": "a statement",
            forbidden: 1,
        }
        with pytest.raises(InvalidClaim) as excinfo:
            ReviewClaim.from_mapping(raw)
        assert forbidden in str(excinfo.value)

    @pytest.mark.parametrize(
        "forbidden", ["recommended_winner", "recommended_model", "recommended_agent"]
    )
    def test_a_recommendation_field_is_refused(self, forbidden):
        raw = {
            "schema_version": 1,
            "claim_id": "c1",
            "statement": "a statement",
            forbidden: "left",
        }
        with pytest.raises(InvalidClaim):
            ReviewClaim.from_mapping(raw)

    def test_an_unknown_field_is_refused(self):
        with pytest.raises(InvalidClaim):
            ReviewClaim.from_mapping(
                {"schema_version": 1, "claim_id": "c1", "statement": "s", "extra": 1}
            )

    def test_the_refusal_names_the_field_rather_than_saying_unknown(self):
        with pytest.raises(InvalidClaim) as excinfo:
            ReviewClaim.from_mapping(
                {"schema_version": 1, "claim_id": "c1", "statement": "s", "confidence": 0.9}
            )
        assert "confidence" in str(excinfo.value)


class TestContentDigest:
    def test_claim_id_does_not_move_the_content_digest(self):
        first = claim(claim_id="c1")
        second = claim(claim_id="c2")
        assert claim_content_digest(first) == claim_content_digest(second)

    def test_statement_moves_the_content_digest(self):
        assert claim_content_digest(claim(statement="one")) != claim_content_digest(
            claim(statement="two")
        )

    def test_a_target_moves_the_content_digest(self):
        without = claim()
        with_target = claim(verification_targets=(target(),))
        assert claim_content_digest(without) != claim_content_digest(with_target)

    def test_the_digest_is_a_sha256_reference(self):
        value = claim_content_digest(claim())
        assert value.startswith("sha256:")
        assert len(value) == len("sha256:") + 64


class TestRoundTrip:
    def test_from_mapping_round_trips_to_mapping(self):
        built = claim(evidence_refs=(sha256("a"),), verification_targets=(target(),))
        assert ReviewClaim.from_mapping(built.to_mapping()) == built
