"""AI-10 §9 — the comparison: every observation, and only the observations.

Two properties are load-bearing:

```text
Amendment 1 / §9.3.1   the reference-difference observation is evaluated over the
                       claim STATEMENT identity, and overlap / uniqueness over the
                       CONTENT identity
§5.3                   the comparison receives the two materials and nothing else —
                       no verification observation can exist yet, so a declared
                       target always produces VERIFICATION_REQUIRED
```

Determinism is the property that lets a review be re-run: the same two materials
produce the same findings, with the same identifiers, every time.
"""

from __future__ import annotations

import inspect

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
        assert of_kind(findings, ReviewFindingKind.CLAIM_OVERLAP).subjects == ("m1#c1", "m2#c9")

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
    def test_an_overlapping_claim_names_both_sides(self):
        left = material("m1", LEFT, (claim("c1"), claim("c2", statement="only left")))
        right = material("m2", RIGHT, (claim("c3"),))
        findings = compare(left, right, review_case_id=CASE)
        overlap = of_kind(findings, ReviewFindingKind.CLAIM_OVERLAP)
        assert overlap.subjects == ("m1#c1", "m2#c3")
        assert of_kind(findings, ReviewFindingKind.CLAIM_UNIQUE_TO_LEFT).subjects == ("m1#c2",)
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


class TestDuplicateContent:
    """§7.4 rejects a duplicate `claim_id`; it does not reject duplicate content.

    Two claims on one side may lawfully share a content digest, and neither may
    be dropped from a subject set.
    """

    def test_two_claims_with_one_content_digest_are_both_named(self):
        left = material(
            "m1", LEFT, (claim("c1"), claim("c2", statement=claim().statement))
        )
        right = material("m2", RIGHT, (claim("c9"),))
        findings = compare(left, right, review_case_id=CASE)
        overlap = of_kind(findings, ReviewFindingKind.CLAIM_OVERLAP)
        assert overlap.subjects == ("m1#c1", "m1#c2", "m2#c9")
        assert "CLAIM_UNIQUE_TO_LEFT" not in kinds(findings)
        assert "CLAIM_UNIQUE_TO_RIGHT" not in kinds(findings)

    def test_one_side_varying_references_keeps_every_statement_subject(self):
        """The case a `digest -> claim` map would have silently shortened."""
        left = material(
            "m1",
            LEFT,
            (
                claim("c1", evidence_refs=(sha256("a"),)),
                claim("c2", evidence_refs=(sha256("b"),)),
            ),
        )
        right = material("m2", RIGHT, (claim("c9"),))
        findings = compare(left, right, review_case_id=CASE)
        difference = of_kind(findings, ReviewFindingKind.EVIDENCE_REFERENCE_DIFFERENCE)
        assert difference.subjects == ("m1#c1", "m1#c2", "m2#c9")

    def test_unique_subjects_keep_every_claim(self):
        left = material(
            "m1", LEFT, (claim("c1", statement="left only"), claim("c2", statement="left only"))
        )
        right = material("m2", RIGHT, (claim("c9"),))
        findings = compare(left, right, review_case_id=CASE)
        assert of_kind(findings, ReviewFindingKind.CLAIM_UNIQUE_TO_LEFT).subjects == (
            "m1#c1",
            "m1#c2",
        )


class TestEvidenceReferences:
    """§9.3.1 — the observation is evaluated over statement identity."""

    def test_the_same_statement_with_different_references_is_observed(self):
        left = material("m1", LEFT, (claim("c1", evidence_refs=(sha256("a"),)),))
        right = material("m2", RIGHT, (claim("c1", evidence_refs=(sha256("b"),)),))
        findings = compare(left, right, review_case_id=CASE)
        difference = of_kind(findings, ReviewFindingKind.EVIDENCE_REFERENCE_DIFFERENCE)
        assert difference.subjects == ("m1#c1", "m2#c1")
        # The content identity covers the references, so these two claims are not
        # the same claim for overlap purposes. Both facts are true at once.
        assert "CLAIM_OVERLAP" not in kinds(findings)

    def test_a_different_statement_produces_no_reference_difference(self):
        left = material("m1", LEFT, (claim("c1", statement="one"),))
        right = material("m2", RIGHT, (claim("c1", statement="two"),))
        findings = compare(left, right, review_case_id=CASE)
        assert "EVIDENCE_REFERENCE_DIFFERENCE" not in kinds(findings)

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

    def test_claim_ids_do_not_change_either_identity(self):
        """A submitter-chosen `claim_id` is not content, either way."""
        left = material("m1", LEFT, (claim("c1"),))
        right = material("m2", RIGHT, (claim("c9"),))
        assert "CLAIM_OVERLAP" in kinds(compare(left, right, review_case_id=CASE))
        assert "EVIDENCE_REFERENCE_DIFFERENCE" not in kinds(
            compare(left, right, review_case_id=CASE)
        )

        renamed_left = material("m1", LEFT, (claim("left-name", evidence_refs=(sha256("a"),)),))
        renamed_right = material(
            "m2", RIGHT, (claim("right-name", evidence_refs=(sha256("b"),)),)
        )
        assert "EVIDENCE_REFERENCE_DIFFERENCE" in kinds(
            compare(renamed_left, renamed_right, review_case_id=CASE)
        )


class TestVerificationRequired:
    def test_a_declared_target_is_observed(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)),))
        right = material("m2", RIGHT, (claim("c1", verification_targets=(target(),)),))
        findings = compare(left, right, review_case_id=CASE)
        required = of_kind(findings, ReviewFindingKind.VERIFICATION_REQUIRED)
        assert required.subjects == ("m1#c1", "m2#c1")

    def test_the_comparison_accepts_no_observation_state(self):
        """§5.3 puts the comparison before any verification is requested.

        There is no parameter a caller could use to assert that an observation
        already exists — a naked subject string is not an observation, and the
        comparison does not accept one.
        """
        parameters = set(inspect.signature(compare).parameters)
        assert parameters == {"left", "right", "review_case_id"}
        assert "observed_subjects" not in parameters

    def test_a_target_cannot_be_suppressed(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)),))
        right = material("m2", RIGHT, (claim("c1"),))
        findings = compare(left, right, review_case_id=CASE)
        required = of_kind(findings, ReviewFindingKind.VERIFICATION_REQUIRED)
        assert required.subjects == ("m1#c1",)

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
        left = material(
            "m1", LEFT, (claim("c1", verification_targets=(target(),)), claim("c2"))
        )
        right = material("m2", RIGHT, (claim("c1"),))
        first = compare(left, right, review_case_id=CASE)
        second = compare(left, right, review_case_id=CASE)
        assert [finding.to_mapping() for finding in first] == [
            finding.to_mapping() for finding in second
        ]

    def test_claim_order_does_not_change_the_findings(self):
        first = material("m1", LEFT, (claim("c1"), claim("c2", statement="second")))
        second = material("m1", LEFT, (claim("c2", statement="second"), claim("c1")))
        right = material("m2", RIGHT, (claim("c9"),))
        assert [f.to_mapping() for f in compare(first, right, review_case_id=CASE)] == [
            f.to_mapping() for f in compare(second, right, review_case_id=CASE)
        ]

    def test_findings_are_ordered_deterministically(self):
        left = material("m1", LEFT, (claim("c1", verification_targets=(target(),)),))
        right = material("m2", RIGHT, (claim("c1"),))
        findings = compare(left, right, review_case_id=CASE)
        keys = [(finding.kind.value, finding.subjects) for finding in findings]
        assert keys == sorted(keys)
