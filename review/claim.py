"""AI-10 §7 — the claim: declared analysis material.

A claim is a statement its submitter stands behind, the references the submitter
declares, and the checks the submitter declares could be run.

```text
statement            !=  truth
evidence_refs        !=  verification
verification_targets !=  verified facts
```

### What a claim cannot say

There is no `confidence`, no `correctness`, no `probability`, no `winner`, no
`score`, no `rank`, no `weight`, no `priority` and no `recommended_*`. Those
fields are refused by name in `from_mapping` rather than merely omitted, because
a schema that could express a verdict would eventually be asked to produce one,
and a review layer that can produce a winner has become the thing AI-00 §13
forbids.

### Set semantics

`evidence_refs` and `verification_targets` are sets. A duplicate is REJECTED
rather than deduplicated silently — deduplication would be the silent
substitution AI-05 §14.4.1 forbids, and a set that preserves multiplicity is not
a set. Both are stored in a deterministic order so that a projection, and
therefore a digest, does not depend on the caller's array order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from review.digest import digest_of
from review.errors import InvalidClaim, InvalidTarget
from review.validation import (
    bounded_text,
    closed_keys,
    identifier,
    mapping,
    reference,
    refused_keys,
    sequence,
    single_line,
)
from review.vocabulary import (
    FORBIDDEN_CLAIM_FIELDS,
    MAX_EVIDENCE_REFS_PER_CLAIM,
    MAX_STATEMENT_CHARS,
    MAX_TARGET_DESCRIPTION_CHARS,
    MAX_VERIFICATION_TARGETS_PER_CLAIM,
)

__all__ = [
    "ReviewClaim",
    "VerificationTarget",
    "claim_content_digest",
    "claim_statement_digest",
]

_TARGET_KEYS = frozenset({"schema_version", "target_id", "description"})
_CLAIM_KEYS = frozenset(
    {"schema_version", "claim_id", "statement", "evidence_refs", "verification_targets"}
)


@dataclass(frozen=True, slots=True)
class VerificationTarget:
    """§7.1. A DECLARED description of something that could be checked.

    It is AI-10's own descriptor type. It is not AI-04's `TargetRef`, not
    AI-06's operation, and AI-10 never converts one into the other: the mapping
    from a declared target to a concrete tool request belongs to the controlled
    verification caller (§11.2).
    """

    target_id: str
    description: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "target_id", identifier(self.target_id, "target.target_id")
        )
        object.__setattr__(
            self,
            "description",
            single_line(
                self.description,
                "target.description",
                maximum=MAX_TARGET_DESCRIPTION_CHARS,
                error=InvalidTarget,
            ),
        )
        if self.schema_version != 1:
            raise InvalidTarget(
                f"target.schema_version {self.schema_version!r} is not supported; "
                "this contract defines 1"
            )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "target") -> "VerificationTarget":
        data = mapping(raw, where)
        closed_keys(data, _TARGET_KEYS, where, error=InvalidTarget)
        if data.get("schema_version") != 1:
            raise InvalidTarget(
                f"{where}.schema_version {data.get('schema_version')!r} is not "
                "supported; this contract defines 1"
            )
        return cls(
            target_id=data.get("target_id"),
            description=data.get("description"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "target_id": self.target_id,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class ReviewClaim:
    """§7.1. One declared claim inside a submitted material."""

    claim_id: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    verification_targets: tuple[VerificationTarget, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", identifier(self.claim_id, "claim.claim_id"))
        object.__setattr__(
            self,
            "statement",
            bounded_text(
                self.statement,
                "claim.statement",
                maximum=MAX_STATEMENT_CHARS,
                error=InvalidClaim,
            ),
        )
        if self.schema_version != 1:
            raise InvalidClaim(
                f"claim.schema_version {self.schema_version!r} is not supported; "
                "this contract defines 1"
            )

        refs = tuple(self.evidence_refs)
        if len(refs) > MAX_EVIDENCE_REFS_PER_CLAIM:
            raise InvalidClaim(
                f"claim.evidence_refs must hold at most {MAX_EVIDENCE_REFS_PER_CLAIM} "
                f"references; got {len(refs)}"
            )
        for ref in refs:
            reference(ref, "claim.evidence_refs[]")
        if len(set(refs)) != len(refs):
            raise InvalidClaim(
                "claim.evidence_refs is SET-semantic and a duplicate element is "
                "refused; deduplicating would be a silent substitution"
            )
        object.__setattr__(self, "evidence_refs", tuple(sorted(refs)))

        targets = tuple(self.verification_targets)
        if len(targets) > MAX_VERIFICATION_TARGETS_PER_CLAIM:
            raise InvalidClaim(
                f"claim.verification_targets must hold at most "
                f"{MAX_VERIFICATION_TARGETS_PER_CLAIM} targets; got {len(targets)}"
            )
        for target in targets:
            if not isinstance(target, VerificationTarget):
                raise InvalidClaim(
                    "claim.verification_targets entries must be VerificationTarget; "
                    f"got {type(target).__name__}"
                )
        target_ids = [target.target_id for target in targets]
        if len(set(target_ids)) != len(target_ids):
            raise InvalidClaim(
                "claim.verification_targets is keyed by target_id and a duplicate "
                "target_id is refused"
            )
        object.__setattr__(
            self,
            "verification_targets",
            tuple(sorted(targets, key=lambda target: target.target_id)),
        )

    # -- raw boundary ------------------------------------------------------

    @classmethod
    def from_mapping(cls, raw: object) -> "ReviewClaim":
        data = mapping(raw, "claim")
        refused_keys(
            data,
            FORBIDDEN_CLAIM_FIELDS,
            "claim",
            "A claim is declared analysis material. A confidence, a rank, a score "
            "or a recommendation is a verdict, and AI-10 does not produce verdicts "
            "(§7.3).",
            error=InvalidClaim,
        )
        closed_keys(data, _CLAIM_KEYS, "claim", error=InvalidClaim)
        if data.get("schema_version") != 1:
            raise InvalidClaim(
                f"claim.schema_version {data.get('schema_version')!r} is not "
                "supported; this contract defines 1"
            )
        targets = tuple(
            VerificationTarget.from_mapping(entry, "claim.verification_targets[]")
            for entry in sequence(
                data.get("verification_targets", []),
                "claim.verification_targets",
                error=InvalidClaim,
            )
        )
        return cls(
            claim_id=data.get("claim_id"),
            statement=data.get("statement"),
            evidence_refs=sequence(
                data.get("evidence_refs", []), "claim.evidence_refs", error=InvalidClaim
            ),
            verification_targets=targets,
        )

    # -- projections -------------------------------------------------------

    def to_mapping(self) -> dict[str, Any]:
        """The claim's own allowlist. Emitted in a deterministic order."""
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "statement": self.statement,
            "evidence_refs": list(self.evidence_refs),
            "verification_targets": [
                target.to_mapping() for target in self.verification_targets
            ],
        }

    def content_projection(self) -> dict[str, Any]:
        """What the claim CONTENT digest covers (§9.3).

        `claim_id` is excluded. It is a submitter-chosen identifier, not content,
        and two submitters who declare the same claim must be comparable.
        """
        return {
            "schema_version": self.schema_version,
            "statement": self.statement,
            "evidence_refs": list(self.evidence_refs),
            "verification_targets": [
                target.to_mapping() for target in self.verification_targets
            ],
        }


def claim_content_digest(claim: ReviewClaim) -> str:
    """§9.3. The digest two claims are compared by for overlap and uniqueness."""
    return digest_of(claim.content_projection())


def claim_statement_digest(claim: ReviewClaim) -> str:
    """The claim's STATEMENT identity: what it says, plus its declared targets.

    Excludes `evidence_refs`, and exists for exactly one rule.

    ```text
    RECORDED FINDING — a contract inconsistency, recorded rather than resolved.
        §9.3 defines the claim content digest as covering `evidence_refs`.
        §9.2 asks EVIDENCE_REFERENCE_DIFFERENCE to fire "for a claim content
        digest present on both sides" whose `evidence_refs` sets are not equal.
        Evaluated over the content digest alone the rule could never fire: two
        claims whose references differ do not share a content digest, and two
        claims that share one have equal references by construction.
        AI-10-B evaluates that ONE observation over statement identity, which is
        the only reading under which the frozen member is reachable, and does
        NOT change the contract. The overlap and uniqueness observations keep
        §9.3's definition unchanged. Resolving this properly is an AI-10
        amendment, not an implementation decision.
    """
    return digest_of(
        {
            "schema_version": claim.schema_version,
            "statement": claim.statement,
            "verification_targets": [
                target.to_mapping() for target in claim.verification_targets
            ],
        }
    )
