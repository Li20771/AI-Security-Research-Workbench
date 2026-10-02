"""AI-10 §9 — the comparison: deterministic structural observations.

The comparison answers exactly one question:

```text
what structurally differs, what overlaps, what needs verification, what is unresolved
```

It never answers "which side is right". There is no confidence calculation, no
heuristic, no score, no ranking and no winner — and none of those could be added
here without a contract amendment, because the finding vocabulary is closed at
the eight members of §9.2.

### Two claim identities, and which observation uses which (§9.3.1)

```text
content identity    statement + evidence_refs + targets
                    -> CLAIM_OVERLAP, CLAIM_UNIQUE_TO_LEFT, CLAIM_UNIQUE_TO_RIGHT,
                       and the claim-set comparison behind claims_digest
statement identity  statement + targets, and NOT evidence_refs
                    -> EVIDENCE_REFERENCE_DIFFERENCE alone
```

### What the comparison does not receive

It receives the two materials and nothing else. It has **no** parameter that
could carry a verification observation, because §5.3 places the comparison
before any verification is requested: at COMPARISON_RECORDED no observation can
exist, so §9.2's VERIFICATION_REQUIRED fires for every claim that declares a
target. Suppressing it would require a caller to assert an observation that the
lifecycle says has not happened, and no caller may do that.

### Determinism

Same inputs, same output. The derivation reads no clock, uses no randomness and
depends on no global state; findings are ordered by kind and then by subjects,
every identifier is derived from what the finding observes, and a material may
lawfully declare two claims with the same content and different `claim_id`s —
so claims are grouped into lists and none is overwritten.

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


def _group_by_content_digest(
    claims: tuple[ReviewClaim, ...],
) -> dict[str, list[ReviewClaim]]:
    """Claims by content identity, as LISTS.

    §7.4 rejects a duplicate `claim_id`; it does not reject two claims that share
    content under different ids. A `digest -> ReviewClaim` map would silently
    drop one of them, and a silently shortened subject set is a false record of
    what was observed.
    """
    grouped: dict[str, list[ReviewClaim]] = {}
    for claim in claims:
        grouped.setdefault(claim_content_digest(claim), []).append(claim)
    return grouped


def _subjects(material: ReviewMaterial, claims: Iterable[ReviewClaim]) -> list[str]:
    return [f"{material.material_id}#{claim.claim_id}" for claim in claims]


def compare(
    left: ReviewMaterial | None,
    right: ReviewMaterial | None,
    *,
    review_case_id: str,
) -> tuple[ReviewFinding, ...]:
    """The structural comparison of one case's two sides (§9.2).

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

    left_by_digest = _group_by_content_digest(left.claims)
    right_by_digest = _group_by_content_digest(right.claims)

    overlap = sorted(set(left_by_digest) & set(right_by_digest))
    unique_left = sorted(set(left_by_digest) - set(right_by_digest))
    unique_right = sorted(set(right_by_digest) - set(left_by_digest))

    if overlap:
        # An overlap is a fact about BOTH sides, so every claim carrying the
        # digest on either side is named. Two claims on one side with the same
        # content are two claims, and both appear.
        subjects: list[str] = []
        for digest in overlap:
            subjects.extend(_subjects(left, left_by_digest[digest]))
            subjects.extend(_subjects(right, right_by_digest[digest]))
        findings.append(
            make_finding(review_case_id, ReviewFindingKind.CLAIM_OVERLAP, tuple(subjects))
        )
    if unique_left:
        findings.append(
            make_finding(
                review_case_id,
                ReviewFindingKind.CLAIM_UNIQUE_TO_LEFT,
                tuple(
                    subject
                    for digest in unique_left
                    for subject in _subjects(left, left_by_digest[digest])
                ),
            )
        )
    if unique_right:
        findings.append(
            make_finding(
                review_case_id,
                ReviewFindingKind.CLAIM_UNIQUE_TO_RIGHT,
                tuple(
                    subject
                    for digest in unique_right
                    for subject in _subjects(right, right_by_digest[digest])
                ),
            )
        )

    # §9.3.1: statement identity, not content identity. Both sides' declared
    # references are compared for a statement declared on both sides, and every
    # claim carrying that statement is named.
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
            differing.extend(_subjects(left, left_group))
            differing.extend(_subjects(right, right_group))
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
            if claim.verification_targets:
                required.append(f"{material.material_id}#{claim.claim_id}")
    if required:
        findings.append(
            make_finding(review_case_id, ReviewFindingKind.VERIFICATION_REQUIRED, tuple(required))
        )

    return tuple(sorted(findings, key=lambda finding: (finding.kind.value, finding.subjects)))
