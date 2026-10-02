"""AI-10 §9 — the finding: a structural observation, never a verdict.

```text
A finding expresses:   what structurally differs
                       what overlaps
                       what requires verification
                       what remains unresolved

A finding never says:  who is correct
                       who wins
                       which Agent is better
                       which claim is true
```

`subjects` labels what the observation is about — a material id, or
`"<material_id>#<claim_id>"` for one claim. A subject is a LABEL for what was
observed. It is not evidence, not proof and not a reference to a fact.

`finding_id` is derived from the case, the kind and the subjects, so two
identical comparisons produce identical findings. A random identifier would make
the comparison non-deterministic, and determinism is the property that lets a
review be re-run and compared with itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from review.digest import digest_of
from review.errors import InvalidFinding
from review.validation import identifier, subject as subject_text
from review.vocabulary import MAX_CLAIMS_PER_MATERIAL, ReviewFindingKind

__all__ = ["ReviewFinding", "finding_id_for", "make_finding"]

#: A finding names claims, and a case has at most two materials of
#: MAX_CLAIMS_PER_MATERIAL claims each. Derived, not invented.
_MAX_SUBJECTS = MAX_CLAIMS_PER_MATERIAL * 2


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """§9.1. One structural observation about one review case."""

    finding_id: str
    review_case_id: str
    kind: ReviewFindingKind
    subjects: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "finding_id", identifier(self.finding_id, "finding.finding_id")
        )
        object.__setattr__(
            self,
            "review_case_id",
            identifier(self.review_case_id, "finding.review_case_id"),
        )
        try:
            kind = ReviewFindingKind(self.kind)
        except ValueError as exc:
            raise InvalidFinding(
                "finding.kind must be one of "
                f"{[member.value for member in ReviewFindingKind]}; got {self.kind!r}. "
                "The vocabulary is closed at eight structural observations (§9.2)"
            ) from exc
        object.__setattr__(self, "kind", kind)

        if self.schema_version != 1:
            raise InvalidFinding(
                f"finding.schema_version {self.schema_version!r} is not supported; "
                "this contract defines 1"
            )

        subjects = tuple(self.subjects)
        if len(subjects) > _MAX_SUBJECTS:
            raise InvalidFinding(
                f"finding.subjects must hold at most {_MAX_SUBJECTS} entries; "
                f"got {len(subjects)}"
            )
        for entry in subjects:
            subject_text(entry, "finding.subjects[]")
        if len(set(subjects)) != len(subjects):
            raise InvalidFinding(
                "finding.subjects is SET-semantic and a duplicate entry is refused"
            )
        object.__setattr__(self, "subjects", tuple(sorted(subjects)))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "finding_id": self.finding_id,
            "review_case_id": self.review_case_id,
            "kind": str(self.kind),
            "subjects": list(self.subjects),
        }


def finding_id_for(
    review_case_id: str, kind: ReviewFindingKind, subjects: Iterable[str]
) -> str:
    """A deterministic identifier for one observation.

    `rf-` is a label, not a namespace that carries meaning — the same rule
    AI-08 §7.2 states for an execution id.
    """
    payload = digest_of(
        {
            "review_case_id": str(review_case_id),
            "kind": str(kind),
            "subjects": sorted(subjects),
        }
    )
    return f"rf-{payload.removeprefix('sha256:')[:16]}"


def make_finding(
    review_case_id: str, kind: ReviewFindingKind, subjects: Iterable[str] = ()
) -> ReviewFinding:
    """Build a finding with its derived identifier."""
    subject_tuple = tuple(subjects)
    return ReviewFinding(
        finding_id=finding_id_for(review_case_id, kind, subject_tuple),
        review_case_id=review_case_id,
        kind=kind,
        subjects=subject_tuple,
    )


def finding_digest(finding: ReviewFinding) -> str:
    """A digest over a finding's semantic content, for tests and callers."""
    return digest_of(
        {
            "review_case_id": finding.review_case_id,
            "kind": str(finding.kind),
            "subjects": list(finding.subjects),
        }
    )
