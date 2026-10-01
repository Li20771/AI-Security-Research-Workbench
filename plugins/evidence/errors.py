"""The AI-05 error hierarchy.

Two things this module deliberately does **not** do.

**It does not represent `AdmissionOutcome` as an exception.** A decision that a
record is `REJECTED` is a result, not a crash: §22.1 defines three outcomes, and
an exception type is not one of them. `AdmissionOutcome` lives in `vocabulary`.
These exceptions are the *reason* a rejection happened, and B2's admission
pipeline is what converts one into an outcome.

**It does not echo the offending value.** Every message names the field, the
expectation, and at most a shape fact — a length, a character class. Nothing
here interpolates a supplied string into an error message, because an error
message is a place a value escapes to a log, and a structural field is a place a
caller might have put something that is not a digest at all (§14.8's residual).

Each error carries a `reason_code` so a caller can branch on the *kind* of
rejection without parsing prose, mirroring AI-04's reason codes.
"""

from __future__ import annotations


class EvidenceError(Exception):
    """Base class for every AI-05 error.

    `reason_code` is a stable, machine-readable label. It is not a message and
    it never contains a supplied value.
    """

    reason_code: str = "EVIDENCE_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --------------------------------------------------------------------------
# Structure (§5, §30 steps 1-3)
# --------------------------------------------------------------------------


class RecordMalformed(EvidenceError):
    """The record does not match the declared envelope or its kind's payload."""

    reason_code = "RECORD_MALFORMED"


class UnknownField(RecordMalformed):
    """A field the contract does not define (§30).

    Not ignored. AI-04 §4.2's precedent: a field that is silently dropped cannot
    be audited, and §13.8 relies on this — a record arriving with raw content in
    an undeclared field is `REJECTED` rather than quietly reshaped.
    """

    reason_code = "UNKNOWN_FIELD"


class MissingRequiredField(RecordMalformed):
    """A field required for this kind is absent or null (§30 step 3)."""

    reason_code = "MISSING_REQUIRED_FIELD"


class PayloadKindMismatch(RecordMalformed):
    """The payload is not the one this kind declares (§11)."""

    reason_code = "PAYLOAD_KIND_MISMATCH"


class RawContentRejected(RecordMalformed):
    """An undeclared raw-content field (§13.8).

    AI-05 never converts supplied content into an artifact. The producer stores
    the bytes; AI-05 admits a reference.
    """

    reason_code = "RAW_CONTENT_REJECTED"


# --------------------------------------------------------------------------
# Vocabulary and role (§6, §7.1, §30 step 4)
# --------------------------------------------------------------------------


class UnsupportedVocabulary(EvidenceError):
    """A value outside a closed vocabulary (§30 step 4)."""

    reason_code = "UNSUPPORTED_VOCABULARY"


class ProducerRoleViolation(UnsupportedVocabulary):
    """`producer_type = human` (§7.1).

    A distinct code from a plain unlisted value, because `human` **is** a member
    of the inherited `ActorType` vocabulary — it is simply not a valid producer
    role. The caller needs to be told which of the two problems they have.
    """

    reason_code = "PRODUCER_ROLE_VIOLATION"


# --------------------------------------------------------------------------
# Field classes (§14.2, §14.5.1, §30 steps 6-7)
# --------------------------------------------------------------------------


class FieldClassViolation(EvidenceError):
    """A value does not satisfy its declared field class (§14.2)."""

    reason_code = "FIELD_CLASS_VIOLATION"


class InvalidIdentifier(FieldClassViolation):
    """A Class 3 identifier is not identifier-shaped (§14.2)."""

    reason_code = "INVALID_IDENTIFIER"


class InvalidDigestShape(FieldClassViolation):
    """A Class 1 structural field is not lowercase hex of the declared length.

    Covers wrong length and wrong charset alike (§14.5.1).
    """

    reason_code = "INVALID_DIGEST_SHAPE"


class NonCanonicalDigestCase(InvalidDigestShape):
    """Uppercase hexadecimal in a Class 1 field (§14.5.1).

    Uppercase is `REJECTED`, never normalized. Normalizing would mean
    substituting an accepted value, which §14.4 forbids AI-05 from doing at all
    — and the no-substitution rule is the more fundamental one, because it is
    what keeps Evidence from being the layer that rewrites a fact.
    """

    reason_code = "NON_CANONICAL_DIGEST_CASE"


# --------------------------------------------------------------------------
# Digest origin (§14.6.1, R1)
# --------------------------------------------------------------------------


class CallerSuppliedGeneratedField(EvidenceError):
    """A caller supplied a value for a field AI-05 generates (§14.6.1).

    This is R1, and it is the rule that makes the §14.6 prohibition enforceable.
    No component can tell a digest of a secret from any other digest, so the
    protection cannot be a detector — it is that AI-05's own digests are
    computed from admitted content and there is no field a caller can use to
    substitute one.
    """

    reason_code = "CALLER_SUPPLIED_GENERATED_FIELD"


class CallerSuppliedDigest(CallerSuppliedGeneratedField):
    """A caller supplied `content_digest`, `record_digest` or `value_digest`."""

    reason_code = "CALLER_SUPPLIED_DIGEST"


class CallerSuppliedIdentity(CallerSuppliedGeneratedField):
    """A caller supplied `evidence_id` (§8.1)."""

    reason_code = "CALLER_SUPPLIED_IDENTITY"


# --------------------------------------------------------------------------
# Cross-field rules (§6.6) — added by Amendment 1 conformance
# --------------------------------------------------------------------------


class CrossFieldViolation(RecordMalformed):
    """A field is well-formed on its own but contradicts another field (§6.6).

    A distinct family from a shape or vocabulary failure, because the caller's
    repair is different: nothing about the offending value is wrong, and what
    must change is the combination.
    """

    reason_code = "CROSS_FIELD_VIOLATION"


class ProducerNotRegistered(CrossFieldViolation):
    """The producer token is not registered for this kind and family (§6.5)."""

    reason_code = "PRODUCER_NOT_REGISTERED"


class ProducerTypeNotAdmitted(CrossFieldViolation):
    """`producer_type` is a valid `ProducerType` member but not the one this
    event registers (§6.5, §6.6).

    Distinct from `ProducerRoleViolation`, which is the vocabulary-level refusal
    of `human`. Here the value is a legal member of the vocabulary and is still
    not admissible, because all six registry rows register `service`.
    """

    reason_code = "PRODUCER_TYPE_NOT_ADMITTED"


class ActorTypeNotAdmitted(CrossFieldViolation):
    """`actor.type` is not one of the values this kind admits (§6.6)."""

    reason_code = "ACTOR_TYPE_NOT_ADMITTED"


class FamilyStatusMismatch(CrossFieldViolation):
    """The status field present is not the one this family declares (§11)."""

    reason_code = "FAMILY_STATUS_MISMATCH"


class BindingArmMismatch(CrossFieldViolation):
    """The binding arm present is not the one this family selects (§11)."""

    reason_code = "BINDING_ARM_MISMATCH"


# --------------------------------------------------------------------------
# Workspace isolation (§18) — added by AI-05-B2
# --------------------------------------------------------------------------


class WorkspaceAgreementViolation(EvidenceError):
    """Two workspace-scoped fields of one record name different workspaces (§18.1).

    **Why this is not a `CrossFieldViolation`.** That family is the §6.6 rule
    set — a frozen, enumerable list of producer/actor/kind combinations. §18 is a
    separate frozen section, and §22.2 gives "workspace mismatch" its own row
    rather than folding it into the cross-field rows. Subclassing
    `CrossFieldViolation` would place a §18 rule inside the §6.6 family and make
    an `except CrossFieldViolation` handler claim a rule it does not hold.

    **Why it is not a `RecordMalformed`.** §22.2 lists "malformed record" and
    "workspace mismatch" as different conditions. Nothing about either value is
    malformed; what fails is their agreement, and the caller's repair is to
    change the scope, not the shape.

    Subclasses `EvidenceError` directly for the same reason `UnsupportedVocabulary`
    and `FieldClassViolation` do: the reason a record was rejected has to be
    branchable without parsing prose, and a family a caller cannot name is a
    family a caller cannot handle.
    """

    reason_code = "WORKSPACE_AGREEMENT_VIOLATION"


# --------------------------------------------------------------------------
# Stored form (§17) — added by AI-05-B2 P2
# --------------------------------------------------------------------------


class StoredIntegrityFailure(EvidenceError):
    """A written record's recomputed digests disagree with the ones it carries (§17).

    **Why this is not `CallerSuppliedDigest`.** That error is about ORIGIN — a
    caller supplied a value for a field AI-05 generates. Here the origin was
    correct: AI-05 computed these digests and wrote them. What failed is that
    the content they describe is no longer the content present. The two say
    different things about the same field, and a handler that treated one as
    the other would relax the wrong boundary.

    **Why it is not a `RecordMalformed`.** §22.2 gives "malformed record" and
    "digest mismatch" separate rows. The stored form parsed correctly; the
    record is simply not the record its digest describes.

    Both digests share one code because §22.2 states one condition for both,
    and the message names which one failed.
    """

    reason_code = "STORED_INTEGRITY_FAILURE"


# --------------------------------------------------------------------------
# The Store (§19, §20, §30 step 14) — added by AI-05-B2 P3
# --------------------------------------------------------------------------


class DuplicateEvidenceId(EvidenceError):
    """A record with this `evidence_id` is already written (§8.2, §30 step 14).

    `duplicate evidence_id -> REJECTED`. It is a collision or an overwrite
    attempt, and §22.2 gives it its own row.

    **Why this is not a `CrossFieldViolation`.** Nothing about the new record
    is wrong on its own; it collides with a record that already exists. The
    caller's repair is to generate a different identity, not to change a field.
    The rule belongs to admission and the detection belongs to the Store — this
    is the error both reach for.
    """

    reason_code = "DUPLICATE_EVIDENCE_ID"


class RecordNotFound(EvidenceError):
    """No record with this `evidence_id` is stored.

    A read of an absent record is a lookup that found nothing, not a malformed
    record and not an integrity failure. §13.3 is the adjacent case and says
    the same thing about artifacts: absence is a query-time fact.
    """

    reason_code = "RECORD_NOT_FOUND"


class StoredBytesUnreadable(RecordMalformed):
    """A stored file is not UTF-8, or not JSON, so no record can be read from it.

    Subclasses `RecordMalformed` because it is a malformed stored form and a
    caller catching that family should catch this too. It carries its own code
    because the repair differs from a field-level rejection: the bytes never
    reached a parser at all.
    """

    reason_code = "STORED_BYTES_UNREADABLE"


class PromotedRecordNotDiscardable(EvidenceError):
    """`discard` was asked to remove a record from the promoted tier (§19.2, §20.2).

    ```text
    discard   remove the whole record from a NON-durable tier   ALLOWED
    delete    destroy a record whose existence WAS guaranteed   FORBIDDEN
    ```

    A promoted record's existence is guaranteed, so AI-05 has no operation that
    removes one. This error exists so that the prohibition is enforced rather
    than merely absent: a discard aimed at the promoted tier is refused by the
    code path that would otherwise have deleted the file.
    """

    reason_code = "PROMOTED_RECORD_NOT_DISCARDABLE"


# --------------------------------------------------------------------------
# Set-semantic duplicates (§15.4) — added by Amendment 1 conformance
# --------------------------------------------------------------------------


class DuplicateElement(RecordMalformed):
    """A set-semantic collection carries the same element twice (§15.4).

    REJECTED rather than deduplicated. Deduplicating would be the silent
    substitution §14.4.1 forbids, and a set that preserves multiplicity is not
    a set.
    """

    reason_code = "DUPLICATE_ELEMENT"


class DuplicateOrdinal(DuplicateElement):
    """Two `payload.tool_calls[]` entries share an ordinal (§11.1).

    The ordering must be total, or "the order" is indeterminate and would need
    a tie-break comparator — which §15.4 forbids.
    """

    reason_code = "DUPLICATE_ORDINAL"


__all__ = [
    "ActorTypeNotAdmitted",
    "BindingArmMismatch",
    "CallerSuppliedDigest",
    "CallerSuppliedGeneratedField",
    "CallerSuppliedIdentity",
    "CrossFieldViolation",
    "DuplicateElement",
    "DuplicateEvidenceId",
    "DuplicateOrdinal",
    "EvidenceError",
    "FamilyStatusMismatch",
    "FieldClassViolation",
    "InvalidDigestShape",
    "InvalidIdentifier",
    "MissingRequiredField",
    "NonCanonicalDigestCase",
    "PayloadKindMismatch",
    "ProducerNotRegistered",
    "ProducerRoleViolation",
    "ProducerTypeNotAdmitted",
    "PromotedRecordNotDiscardable",
    "RawContentRejected",
    "RecordMalformed",
    "RecordNotFound",
    "StoredBytesUnreadable",
    "StoredIntegrityFailure",
    "UnknownField",
    "UnsupportedVocabulary",
    "WorkspaceAgreementViolation",
]
