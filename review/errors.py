"""AI-10 §6, §9, §10, §12, §14 — typed refusals.

Every refusal AI-10 makes is a typed exception with a stable `reason_code`,
because a caller that has to parse an error message to learn what happened does
not have a contract — the rule AI-04, AI-05 and AI-06 each state for their own
boundaries, applied here.

The exception is the MECHANISM; the refusal is the contract.
"""

from __future__ import annotations

__all__ = [
    "InvalidCase",
    "InvalidClaim",
    "InvalidDecision",
    "InvalidFinding",
    "InvalidIdentifier",
    "InvalidMaterial",
    "InvalidReference",
    "InvalidTarget",
    "InvalidTransition",
    "InvalidVerification",
    "ProvenanceMismatch",
    "ReviewError",
]


class ReviewError(ValueError):
    """Base class. A caller defect, never a data condition."""

    reason_code = "REVIEW_ERROR"


class InvalidIdentifier(ReviewError):
    """An identifier is empty, too long, or outside the identifier grammar."""

    reason_code = "INVALID_IDENTIFIER"


class InvalidReference(ReviewError):
    """A declared reference is not one of AI-08's two reference shapes."""

    reason_code = "INVALID_REFERENCE"


class InvalidTarget(ReviewError):
    """A verification target is malformed or unbounded."""

    reason_code = "INVALID_TARGET"


class InvalidClaim(ReviewError):
    """A claim violates the §7 schema, its bounds or its set semantics."""

    reason_code = "INVALID_CLAIM"


class InvalidMaterial(ReviewError):
    """A material violates the §6 schema, its bounds or its set semantics."""

    reason_code = "INVALID_MATERIAL"


class InvalidFinding(ReviewError):
    """A finding violates §9 — its kind, its subjects or its shape."""

    reason_code = "INVALID_FINDING"


class InvalidCase(ReviewError):
    """A case-level rule is violated — two sides, one workspace, matching ids."""

    reason_code = "INVALID_CASE"


class InvalidTransition(ReviewError):
    """A lifecycle transition is not one §5.3 permits from the current state."""

    reason_code = "INVALID_TRANSITION"


class ProvenanceMismatch(ReviewError):
    """A declared attribution field disagrees with a supplied execution record.

    §6.4: a mismatch is a REFUSAL, not a warning. The declaration would otherwise
    attribute one execution's work to another.
    """

    reason_code = "PROVENANCE_MISMATCH"


class InvalidVerification(ReviewError):
    """A verification request or observation violates §10."""

    reason_code = "INVALID_VERIFICATION"


class InvalidDecision(ReviewError):
    """A human decision violates §12 — including any attempt to make one machine-made."""

    reason_code = "INVALID_DECISION"
