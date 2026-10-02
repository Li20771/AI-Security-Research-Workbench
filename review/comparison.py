"""AI-10 §9 — the comparison: deterministic structural observations.

The comparison answers exactly one question:

```text
what structurally differs, what overlaps, what needs verification, what is unresolved
```

It never answers "which side is right". There is no confidence calculation, no
heuristic, no score, no ranking and no winner — and none of those could be added
here without a contract amendment, because the finding vocabulary is closed at
the eight members of §9.2 and the projections this module emits are the ones the
digests cover.

### Determinism

Same inputs, same output. The derivation reads no clock, uses no randomness and
depends on no global state; the findings are ordered by kind and then by
subjects, and each identifier is derived from what the finding observes.

### What each result does not mean

```text
IDENTICAL_MATERIAL            is NOT confirmation
MATERIAL_DIFFERENCE           is NOT disagreement
CLAIM_OVERLAP                 is NOT agreement
CLAIM_UNIQUE_TO_LEFT/RIGHT    is NOT "that side is correct"
EVIDENCE_REFERENCE_DIFFERENCE is NOT "one side's references are wrong"
VERIFICATION_REQUIRED         is NOT "the claim is false"
UNRESOLVED                    is NOT a pass, and NOT a failure
```
"""

from __future__ import annotations

from typing import Iterable

from review.claim import ReviewClaim, claim_content_digest, claim_statement_digest
from review.finding import ReviewFinding, make_finding
from review.material import ReviewMaterial
from review.vocabulary import ReviewFindingKind

__all__ = ["compare"]


def _subjects_for(
    material: ReviewMaterial, claims: Iterable[ReviewClaim]
) -> tuple[str, ...]:
    return tuple(f"{material.material_id}#{claim.claim_id}" for claim in claims)


def compare(
    left: ReviewMaterial | None,
    right: ReviewMaterial | None,
    *,
    review_case_id: str,
    observed_subjects: frozenset[str] = frozenset(),
) -> tuple[ReviewFinding, ...]:
    """The structural comparison of one case's two sides (§9.2).

    `observed_subjects` is the set of `"<material_id>#<claim_id>"` subjects that
    already have a `VerificationObservation`. It exists so that
    VERIFICATION_REQUIRED means what §9.2 says — a declared target with no
    observation yet — rather than "a target exists".

    Either side may be `None`, which is the honest input when a material was not
    supplied; the comparison then cannot be completed and returns UNRESOLVED
    alone. The case API refuses to record a comparison unless both sides are
    supplied, so a case never reaches this arm.
    """
    if left is None or right is None:
        return (make_finding(review_case_id, ReviewFindingKind.UNRESOLVED),)

    findings: list[ReviewFinding] = []

    both_materials = (left.material_id, right.material_id)

    if left.claims_digest == right.claims_digest:
        findings.append(
            make_finding(review_case_id, ReviewFindingKind.IDENTICAL_MATERIAL, both_materials)
        )
    else:
        findings.append(
            make_finding(review_case_id, ReviewFindingKind.MATERIAL_DIFFERENCE, both_materials)
        )

    left_by_digest = {claim_content_digest(claim): claim for claim in left.claims}
    right_by_digest = {claim_content_digest(claim): claim for claim in right.claims}

    overlap = sorted(set(left_by_digest) & set(right_by_digest))
    unique_left = sorted(set(left_by_digest) - set(right_by_digest))
    unique_right = sorted(set(right_by_digest) - set(left_by_digest))

    if overlap:
        findings.append(
            make_finding(
                review_case_id,
                ReviewFindingKind.CLAIM_OVERLAP,
                _subjects_for(left, (left_by_digest[digest] for digest in overlap)),
            )
        )
    if unique_left:
        findings.append(
            make_finding(
                review_case_id,
                ReviewFindingKind.CLAIM_UNIQUE_TO_LEFT,
                _subjects_for(left, (left_by_digest[digest] for digest in unique_left)),
            )
        )
    if unique_right:
        findings.append(
            make_finding(
                review_case_id,
                ReviewFindingKind.CLAIM_UNIQUE_TO_RIGHT,
                _subjects_for(right, (right_by_digest[digest] for digest in unique_right)),
            )
        )

    # A structural identity in the statement does not imply the declared
    # references agree, so the two are observed separately.
    #
    # RECORDED FINDING: this one observation is evaluated over STATEMENT
    # identity (`claim_statement_digest`), not over the §9.3 content digest.
    # Evaluated over the content digest — which covers `evidence_refs` — the
    # rule could never fire, because two claims whose references differ do not
    # share one. `review/claim.py` records the inconsistency in full; the
    # contract is not changed here.
    left_by_statement: dict[str, list[ReviewClaim]] = {}
    for member in left.claims:
        left_by_statement.setdefault(claim_statement_digest(member), []).append(member)
    right_by_statement: dict[str, list[ReviewClaim]] = {}
    for member in right.claims:
        right_by_statement.setdefault(claim_statement_digest(member), []).append(member)

    differing: list[str] = []
    for digest in sorted(set(left_by_statement) & set(right_by_statement)):
        left_group = left_by_statement[digest]
        right_group = right_by_statement[digest]
        left_refs = {ref for member in left_group for ref in member.evidence_refs}
        right_refs = {ref for member in right_group for ref in member.evidence_refs}
        if left_refs != right_refs:
            differing.extend(
                f"{left.material_id}#{member.claim_id}" for member in left_group
            )
            differing.extend(
                f"{right.material_id}#{member.claim_id}" for member in right_group
            )
    if differing:
        findings.append(
            make_finding(
                review_case_id,
                ReviewFindingKind.EVIDENCE_REFERENCE_DIFFERENCE,
                tuple(differing),
            )
        )

    required: list[str] = []
    for material in (left, right):
        for claim in material.claims:
            if not claim.verification_targets:
                continue
            subject = f"{material.material_id}#{claim.claim_id}"
            if subject not in observed_subjects:
                required.append(subject)
    if required:
        findings.append(
            make_finding(review_case_id, ReviewFindingKind.VERIFICATION_REQUIRED, tuple(required))
        )

    return tuple(sorted(findings, key=lambda finding: (finding.kind.value, finding.subjects)))
