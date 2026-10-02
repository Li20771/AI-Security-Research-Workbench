"""AI-10 §9 — the finding vocabulary: eight observations, and no verdict.

The closed vocabulary is the mechanism that keeps the review layer from
adjudicating: there is no member a verdict could be spelled with.
"""

from __future__ import annotations

import dataclasses

import pytest

from review.errors import InvalidFinding, ReviewError
from review.finding import ReviewFinding, finding_id_for, make_finding
from review.vocabulary import ReviewFindingKind

pytestmark = pytest.mark.layer1

THE_EIGHT = {
    "IDENTICAL_MATERIAL",
    "MATERIAL_DIFFERENCE",
    "CLAIM_OVERLAP",
    "CLAIM_UNIQUE_TO_LEFT",
    "CLAIM_UNIQUE_TO_RIGHT",
    "EVIDENCE_REFERENCE_DIFFERENCE",
    "VERIFICATION_REQUIRED",
    "UNRESOLVED",
}


class TestTheVocabulary:
    def test_it_is_exactly_the_frozen_eight(self):
        assert {member.value for member in ReviewFindingKind} == THE_EIGHT

    def test_no_member_is_a_verdict(self):
        for forbidden in (
            "PASS",
            "FAIL",
            "CORRECT",
            "VERIFIED",
            "WINNER",
            "BEST_AGENT",
            "HIGHER_CONFIDENCE",
            "SCORE",
            "RANK",
        ):
            assert forbidden not in {member.name for member in ReviewFindingKind}

    def test_a_kind_outside_the_vocabulary_is_refused(self):
        with pytest.raises(InvalidFinding):
            ReviewFinding(
                finding_id="rf-1",
                review_case_id="rc-1",
                kind="LEFT_IS_RIGHT",
            )


class TestShape:
    def test_a_finding_carries_only_its_observation(self):
        fields = {field.name for field in dataclasses.fields(ReviewFinding)}
        assert fields == {"schema_version", "finding_id", "review_case_id", "kind", "subjects"}

    def test_subjects_accept_a_material_and_a_claim(self):
        built = make_finding("rc-1", ReviewFindingKind.CLAIM_OVERLAP, ("m1#c1", "m2#c1"))
        assert built.subjects == ("m1#c1", "m2#c1")
        whole = make_finding("rc-1", ReviewFindingKind.MATERIAL_DIFFERENCE, ("m1", "m2"))
        assert whole.subjects == ("m1", "m2")

    def test_a_free_form_subject_is_refused(self):
        with pytest.raises(ReviewError):
            make_finding(
                "rc-1",
                ReviewFindingKind.MATERIAL_DIFFERENCE,
                ("a statement, not a label",),
            )

    def test_duplicate_subjects_are_refused(self):
        with pytest.raises(InvalidFinding):
            ReviewFinding(
                finding_id="rf-1",
                review_case_id="rc-1",
                kind=ReviewFindingKind.CLAIM_OVERLAP,
                subjects=("m1#c1", "m1#c1"),
            )

    def test_subjects_are_stored_in_a_deterministic_order(self):
        built = ReviewFinding(
            finding_id="rf-1",
            review_case_id="rc-1",
            kind=ReviewFindingKind.CLAIM_OVERLAP,
            subjects=("m2#c9", "m1#c1"),
        )
        assert built.subjects == ("m1#c1", "m2#c9")


class TestFindingIdentity:
    def test_the_identifier_is_derived_not_random(self):
        first = make_finding("rc-1", ReviewFindingKind.CLAIM_OVERLAP, ("m1#c1",))
        second = make_finding("rc-1", ReviewFindingKind.CLAIM_OVERLAP, ("m1#c1",))
        assert first.finding_id == second.finding_id

    def test_a_different_observation_gets_a_different_identifier(self):
        first = make_finding("rc-1", ReviewFindingKind.CLAIM_OVERLAP, ("m1#c1",))
        second = make_finding("rc-1", ReviewFindingKind.CLAIM_UNIQUE_TO_LEFT, ("m1#c1",))
        assert first.finding_id != second.finding_id

    def test_the_identifier_is_opaque(self):
        value = finding_id_for("rc-1", ReviewFindingKind.UNRESOLVED, ())
        assert value.startswith("rf-")
        assert "rc-1" not in value


class TestProjection:
    def test_to_mapping_is_an_allowlist(self):
        built = make_finding("rc-1", ReviewFindingKind.VERIFICATION_REQUIRED, ("m1#c1",))
        assert set(built.to_mapping()) == {
            "schema_version",
            "finding_id",
            "review_case_id",
            "kind",
            "subjects",
        }

    def test_the_mapping_spells_no_verdict(self):
        for member in ReviewFindingKind:
            mapping = make_finding("rc-1", member, ("m1",)).to_mapping()
            rendered = " ".join(str(value) for value in mapping.values())
            for forbidden in ("PASS", "VERIFIED", "CORRECT", "WINNER", "BEST_AGENT"):
                assert forbidden not in rendered
