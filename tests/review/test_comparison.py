"""AI-10 §9 — the comparison: every observation, and only the observations.

Determinism is the property that lets a review be re-run: the same two materials
produce the same findings, with the same identifiers, every time.
"""

from __future__ import annotations

import pytest

from agents.vocabulary import AgentId

from review.comparison import compare
from review.material import ReviewMaterial
from review.vocabulary import ReviewFindingKind

from tests.review.conftest import claim, sha256, target

pytestmark = pytest.mark.layer2

CASE = "rc-comparison"


def material(
    material_id: str,
    agent_id: AgentId,
    claims: tuple = (),
    *,
    input_digest: str | None = None,
) -> ReviewMaterial:
    return ReviewMaterial(
        material_id=material_id,
        agent_id=agent_id,
        execution_id=f"ex-{material_id}",
        workspace_id="ws-1",
        input_digest=input_digest or sha256("a"),
        source_status="COMPLETED",
        claims=claims,
    )


def kinds(findings) -> set[str]:
    return {str(finding.kind) for finding in findings}


def of_kind(findings, kind: ReviewFindingKind):
    return next(finding for finding in findings if finding.kind is kind)


LEFT = AgentId.DSH
RIGHT = AgentId.CODEX


class TestMaterialIdentity:
    def test_equal_claim_sets_are_identical_material(self):
        left = material("m1", LEFT, (claim("c1"),))
        right = material("m2", RIGHT, (claim("c9"),))  # same content, other id
        findings = compare(left, right, review_case_id=CASE)
        # The claim set is identical AND every claim appears on both sides;
        # neither observation is confirmation of anything (§9.4).
        assert kinds(findings) == {"IDENTICAL_MATERIAL", "CLAIM_OVERLAP"}
        assert of_kind(findings, ReviewFindingKind.IDENTICAL_MATERIAL).subjects == ("m1", "m2")
        assert of_kind(findings, ReviewFindingKind.CLAIM_OVERLAP).subjects == ("m1#c1",)

    def test_a_different_claim_set_is_a_material_difference(self):
        left = material("m1", LEFT, (claim("c1"),))
        right = material("m2", RIGHT, (claim("c1", statement="something else"),))
        findings = compare(left, right, review_case_id=CASE)
        assert "MATERIAL_DIFFERENCE" in kinds(findings)
        assert "IDENTICAL_MATERIAL" not in kinds(findings)

    def test_two_silent_materials_are_structurally_identical(self):
        """Equal claim-set digests, and the claim set is empty on both sides.

        This is a statement about two DECLARED claim sets, both of which declare
        nothing. It is not confirmation of anything, and §9.4 says so.
        """
        findings = compare(material("m1", LEFT), material("m2", RIGHT), review_case_id=CASE)
        assert kinds(findings) == {"IDENTICAL_MATERIAL"}


class TestClaims:
    def test_an_overlapping_claim_is_observed_with_its_left_subject(self):
        left = material("m1", LEFT, (claim("c1"), claim("c2", statement="only left")))
        right = material("m2", RIGHT, (claim("c3"),))
        findings = compare(left, right, review_case_id=CASE)
        overlap = of_kind(findings, ReviewFindingKind.CLAIM_OVERLAP)
        assert overlap.subjects == ("m1#c1",)
        assert "CLAIM_UNIQUE_TO_LEFT" in kinds(findings)
        assert "CLAIM_UNIQUE_TO_RIGHT" not in kinds(findings)

    def test_a_claim_on_one_side_only_is_unique_to_that_side(self):
        left = material("m1", LEFT, (claim("c1", statement="left only"),))
        right = material("m2", RIGHT, (claim("c1", statement="right only"),))
        findings = compare(left, right, review_case_id=CASE)
        assert of_kind(findings, ReviewFindingKind.CLAIM_UNIQUE_TO_LEFT).subjects == ("m1#c1",)
        assert of_kind(findings, ReviewFindingKind.CLAIM_UNIQUE_TO_RIGHT).subjects == ("m2#c1",)
        assert "CLAIM_OVERLAP" not in kinds(findings)

    def test_two_materials_cannot_declare_the_same_claim_id_twice(self):
        """A malformed claim set never reaches a comparison."""
        with pytest.raises(Exception):
            material("m1", LEFT, (claim("c1"), claim("c1", statement="duplicate")))


class TestEvidenceReferences:
    def test_the_same_statement_with_different_references_is_observed(self):
        """Both sides say the same thing and cite different references.

        §9.3's content digest covers `evidence_refs`, so these two claims are
        not "the same claim" for overlap purposes; this observation is the one
        that fires, over statement identity. `review/claim.py` records why.
        """
        left = material("m1", LEFT, (claim("c1", evidence_refs=(sha256("a"),)),))
        right = material("m2", RIGHT, (claim("c1", evidence_refs=(sha256("b"),)),))
        findings = compare(left, right, review_case_id=CASE)
        difference = of_kind(findings, ReviewFindingKind.EVIDENCE_REFERENCE_DIFFERENCE)
        assert difference.subjects == ("m1#c1", "m2#c1")
        assert "CLAIM_OVERLAP" not in kinds(findings)

    def test_equal_references_produce_no_difference_observation(self):
        left = material("m1", LEFT, (claim("c1", evidence_refs=(sha256("a"),)),))
        right = material("m2", RIGHT, (claim("c1", evidence_refs=(sha256("a"),)),))
        findings = compare(left, right, review_case_id=CASE)
        assert "EVIDENCE_REFERENCE_DIFFERENCE" not in kinds(findings)
        assert "CLAIM_OVERLAP" in kinds(findings)

    def test_one_side_citing_nothing_is_a_reference_difference(self):
        left = material("m1", LEFT, (claim("c1", evidence_refs=(sha256("a"),)),))
        right = material("m2", RIGHT, (claim("c1"),))
        findings = compare(left, right, review_case_id=CASE)
        assert "EVIDENCE_REFERENCE_DIFFERENCE" in kinds(findings)


class TestVerificationRequired:
    def test_a_declared_target_with_no_observation_is_observed(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)),))
        right = material("m2", RIGHT, (claim("c1", verification_targets=(target(),)),))
        findings = compare(left, right, review_case_id=CASE)
        required = of_kind(findings, ReviewFindingKind.VERIFICATION_REQUIRED)
        assert required.subjects == ("m1#c1", "m2#c1")

    def test_an_observed_subject_is_no_longer_required(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)),))
        right = material("m2", RIGHT, (claim("c1", verification_targets=(target(),)),))
        findings = compare(
            left,
            right,
            review_case_id=CASE,
            observed_subjects=frozenset({"m1#c1", "m2#c1"}),
        )
        assert "VERIFICATION_REQUIRED" not in kinds(findings)

    def test_a_claim_without_a_target_requires_nothing(self):
        findings = compare(
            material("m1", LEFT, (claim("c1"),)),
            material("m2", RIGHT, (claim("c1"),)),
            review_case_id=CASE,
        )
        assert "VERIFICATION_REQUIRED" not in kinds(findings)


class TestUnresolved:
    def test_a_missing_side_cannot_be_compared(self):
        findings = compare(None, material("m2", RIGHT, (claim(),)), review_case_id=CASE)
        assert kinds(findings) == {"UNRESOLVED"}

    def test_unresolved_is_not_a_failure_and_not_a_pass(self):
        findings = compare(None, None, review_case_id=CASE)
        assert len(findings) == 1
        mapping = findings[0].to_mapping()
        assert mapping["kind"] == "UNRESOLVED"
        assert mapping["subjects"] == []


class TestDeterminism:
    def test_the_same_inputs_produce_the_same_findings(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)), claim("c2")))
        right = material("m2", RIGHT, (claim("c1"),))
        first = compare(left, right, review_case_id=CASE)
        second = compare(left, right, review_case_id=CASE)
        assert [finding.to_mapping() for finding in first] == [
            finding.to_mapping() for finding in second
        ]

    def test_findings_are_ordered_deterministically(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)),))
        right = material("m2", RIGHT, (claim("c1"),))
        findings = compare(left, right, review_case_id=CASE)
        keys = [(finding.kind.value, finding.subjects) for finding in findings]
        assert keys == sorted(keys)
