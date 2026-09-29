"""The AI-05 record model.

Implements the contract §5 envelope, §7 producer/actor split, §9 provenance,
§11 payloads, §12's ContextRef shape and §13's artifact shape.

Two properties carry most of the weight here.

**The record is a typed envelope plus a typed payload, not a free mapping.**
Every field is declared; a field the contract does not define is refused rather
than ignored. §13.8 depends on that: a record arriving with raw content in an
undeclared field is `REJECTED`, never quietly reshaped into an artifact.

**Caller-supplied and AI-05-generated are different things.** §15.2 records for
every field whether a caller may supply it. `evidence_id`, `recorded_at`,
`content_digest`, `record_digest` and every `ContextRef.value_digest` are
AI-05's to produce, and a caller supplying one is rejected (§14.6.1, R1). This
is the rule that makes §14.6's prohibition enforceable: no component can tell a
digest of a secret from any other digest, so the protection cannot be a
detector — it is that there is no field in which a caller can substitute one.

`recorded_at` is in that list, which surprises people. §15.2 says a caller does
not supply it; it is the instant AI-05 wrote the record, so the writer stamps
it, not the submitter.

### On the payload field sets

§11 requires that "every payload field MUST be declared in this contract", and
then names the fields only in prose. The three payload types below use exactly
those names and nothing more. **The selection is an inference and is reported as
C-2**, pending ratification — see the B1 implementation report. It is not a
contract amendment and nothing here relaxes a frozen rule.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from plugins.context.context import utc_now

# The serialization primitive only, imported from AI-04 per §15. AI-04's
# semantic projections are not reused — AI-05 owns its own field classification.
from plugins.guard.digest import canonical_json, sha256_hex

from plugins.evidence.errors import (
    CallerSuppliedDigest,
    CallerSuppliedGeneratedField,
    CallerSuppliedIdentity,
    InvalidDigestShape,
    InvalidIdentifier,
    MissingRequiredField,
    NonCanonicalDigestCase,
    PayloadKindMismatch,
    ProducerRoleViolation,
    RawContentRejected,
    RecordMalformed,
    UnknownField,
    UnsupportedVocabulary,
)
from plugins.evidence.vocabulary import (
    ActorType,
    EvidenceKind,
    Freshness,
    GuardDecision,
    ItemKind,
    StatusValue,
    producer_type_is_permitted,
)

#: The only schema version this contract defines.
SUPPORTED_SCHEMA_VERSION = 1

#: The one structure the record defines, mirroring AI-04's `SUPPORTED_SCHEMA_VERSION`.
EVIDENCE_ID_PREFIX = "ev-"

#: Class 3 identifier shape. The same shape AI-02 uses for `experiment_id`, which
#: is the repository's existing answer to "an id is an identifier, not free text".
#:
#: Applied **only** where a shape is documented: `experiment_id` by AI-02 §7.4 and
#: `record_ref` by AI-05 §8.1. `actor.id`, `workspace_id`, `producer` and the
#: artifact `role` are open strings — AI-04 treats the first two as open and
#: compared literally, and constraining them here would reject ids the Workbench
#: already produces, such as `human:reviewer`.
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: The shape `evidence_id` takes, and therefore the shape a `record_ref` must
#: have if it is to denote one (§8.1).
EVIDENCE_ID_RE = re.compile(r"^ev-[0-9a-f]{16}$")

#: Class 1 structural lengths. A document revision is a SHA-256 of content; a git
#: revision is a 40-character commit SHA. Both are legitimate; nothing else is.
_SHA256_LEN = 64
_GIT_SHA_LEN = 40
_STRUCTURAL_LENGTHS = frozenset({_SHA256_LEN, _GIT_SHA_LEN})

_LOWER_HEX_RE = re.compile(r"^[0-9a-f]+$")
_UPPER_HEX_RE = re.compile(r"^[0-9A-F]+$")


# --------------------------------------------------------------------------
# Class 1: structural fields
# --------------------------------------------------------------------------


def _structural(
    value: object, field_name: str, *, lengths: frozenset[int] = _STRUCTURAL_LENGTHS
) -> str:
    """Validate a Class 1 field: lowercase hex of an exact declared length.

    §14.5.1 freezes the case policy. Uppercase is **rejected**, never
    normalized, because normalizing means substituting an accepted value and
    §14.4 forbids AI-05 from doing that at all.

    No message below echoes the supplied value. A structural field is a place a
    caller might have put something that is not a digest, and §14.8 records that
    residual; an error message is not a place to reproduce it.
    """
    if not isinstance(value, str):
        raise InvalidDigestShape(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    if len(value) not in lengths:
        expected = " or ".join(str(n) for n in sorted(lengths))
        raise InvalidDigestShape(
            f"{field_name} must be {expected} characters; got {len(value)}"
        )
    if not _LOWER_HEX_RE.match(value):
        if _UPPER_HEX_RE.match(value):
            raise NonCanonicalDigestCase(
                f"{field_name} is uppercase hexadecimal; §14.5.1 requires "
                "lowercase, and AI-05 does not normalize what it accepts"
            )
        raise InvalidDigestShape(
            f"{field_name} must be lowercase hexadecimal of the declared length; "
            f"got {len(value)} characters containing a non-hex character"
        )
    return value


def _sha256(value: object, field_name: str) -> str:
    """Validate a 64-character SHA-256 hex digest."""
    return _structural(value, field_name, lengths=frozenset({_SHA256_LEN}))


def _revision(value: object, field_name: str) -> str:
    """Validate a source revision: a 40-character commit or a 64-character digest."""
    return _structural(value, field_name)


# --------------------------------------------------------------------------
# Class 3: identifiers
# --------------------------------------------------------------------------


def _identifier(value: object, field_name: str) -> str:
    """Validate a Class 3 identifier.

    Shape only. AI-05 does not sanitize (§14.4.1): a value that is
    identifier-shaped *and* secret-shaped has already been handled upstream, and
    an unsanitized one is the upstream sanitizer's miss rather than something
    AI-05 repairs.
    """
    if not isinstance(value, str):
        raise InvalidIdentifier(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    if not IDENTIFIER_RE.match(value):
        raise InvalidIdentifier(
            f"{field_name} is not identifier-shaped: expected "
            f"{IDENTIFIER_RE.pattern}, got {len(value)} characters"
        )
    return value


#: Ceiling for every declared text field. §14.2 forbids a free-text class, so no
#: field may be unbounded — a string with no cap is a free-text field wearing
#: another name.
MAX_TEXT_LENGTH = 512


def _record_ref(value: object, field_name: str) -> str:
    """A `record_ref` must be able to denote a record, so it takes that shape."""
    if not isinstance(value, str):
        raise InvalidIdentifier(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    if not EVIDENCE_ID_RE.match(value):
        raise InvalidIdentifier(
            f"{field_name} does not denote a record: expected "
            f"{EVIDENCE_ID_RE.pattern}, got {len(value)} characters"
        )
    return value


def _text(value: object, field_name: str, *, limit: int = MAX_TEXT_LENGTH) -> str:
    """A bounded, non-empty string.

    Deliberately **not** identifier-shaped. AI-04 treats `actor.id` and
    `workspace.id` as open strings compared literally, and its own fixtures use
    ids like `human:reviewer`; constraining them here would reject values the
    Workbench already produces. Only the fields with a documented shape get one.
    """
    if not isinstance(value, str):
        raise RecordMalformed(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    if not value.strip():
        raise RecordMalformed(f"{field_name} must not be empty")
    if len(value) > limit:
        raise RecordMalformed(
            f"{field_name} exceeds {limit} characters; got {len(value)}"
        )
    return value


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name)


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecordMalformed(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RecordMalformed(f"{field_name} must be a list")
    return value


def _closed_keys(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    """Refuse a field the contract does not define (§30 step 1)."""
    unknown = set(raw) - allowed
    if unknown:
        raise UnknownField(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}. A field that is silently "
            "dropped cannot be audited (§30), and §13.8 refuses undeclared raw "
            "content rather than reshaping it"
        )


def _required(raw: Mapping[str, Any], name: str, where: str) -> Any:
    if name not in raw or raw[name] is None:
        raise MissingRequiredField(f"{where}.{name} is required")
    return raw[name]


def _enum(value: object, kind: type, field_name: str):
    try:
        return kind(value)
    except ValueError:
        allowed = ", ".join(sorted(member.value for member in kind))
        raise UnsupportedVocabulary(
            f"{field_name}: {value!r} is not one of {allowed}"
        ) from None


def value_digest_of(value: str) -> str:
    """The `value_digest` of one accepted context value (§12.1, §14.6.1).

    This is an **identity discriminator**, not a confidentiality mechanism. A
    low-entropy value is brute-forceable from its digest, and that is accepted
    here because the value is workspace document content already referenced by
    identity — no confidentiality is created or lost. A secret never reaches a
    `ContextRef`, because a secret-bearing field is rejected upstream (§14).

    Computed over the canonical JSON form of the string, so a value that could
    collide with a differently-typed serialization cannot.
    """
    return sha256_hex(canonical_json(value))


def new_evidence_id() -> str:
    """A generated, opaque record identity (§8.1).

    Follows AI-04's `decision_id` precedent: a generated runtime identifier that
    is never part of a semantic digest. It is **never content-derived**, so two
    records making the same claim have different ids — they are two observations,
    not one.
    """
    return f"{EVIDENCE_ID_PREFIX}{uuid.uuid4().hex[:16]}"


# --------------------------------------------------------------------------
# Value types
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Actor:
    """The entity whose act the record is ABOUT (§7)."""

    id: str
    type: ActorType

    @classmethod
    def from_mapping(cls, raw: object, where: str = "actor") -> "Actor":
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"id", "type"}), where)
        return cls(
            id=_text(_required(data, "id", where), f"{where}.id"),
            type=_enum(_required(data, "type", where), ActorType, f"{where}.type"),
        )

    def to_projection(self) -> dict[str, Any]:
        return {"actor.id": self.id, "actor.type": str(self.type)}


@dataclass(frozen=True, slots=True)
class ContextRef:
    """A durable reference to one AI-03 context item (§12.1).

    `value_digest` is an **identity discriminator**, not a confidentiality
    mechanism. Value participates in item identity — AI-03's Amendment 3 added it
    because two halves of a self-contradicting document shared one read and
    therefore one reference — and AI-04 sorts its item projection by it too. Two
    items from one read with different values are two items.

    The raw `value` is never stored and never rendered here (§12.4).
    """

    workspace_id: str
    source_kind: str
    source_identity: str
    source_revision: str
    subject: str
    value_digest: str
    item_kind: ItemKind
    truth_state: StatusValue
    freshness: Freshness

    #: What a caller supplies. `value` is transient input: AI-05 digests it and
    #: does not keep it. `value_digest` is AI-05's to compute (§14.6.1, R1).
    _SUPPLIED_KEYS = frozenset(
        {
            "workspace_id",
            "source_kind",
            "source_identity",
            "source_revision",
            "subject",
            "value",
            "item_kind",
            "truth_state",
            "freshness",
        }
    )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "context[]") -> "ContextRef":
        """Derive a stored ContextRef from a supplied reference and its value.

        The supplied form carries the raw `value` so AI-05 can compute
        `value_digest` from something it admitted; the stored form carries only
        the digest. §30 step 10 makes `value_digest` absent from the supplied
        record, and §12.4 keeps the raw value out of the stored one — so neither
        form carries both.
        """
        data = _mapping(raw, where)
        if "value_digest" in data:
            raise CallerSuppliedDigest(
                f"{where}.value_digest: AI-05 computes this from an accepted "
                "value (§14.6.1, R1). A caller-supplied digest is refused "
                "whatever its shape, so sha256(secret) cannot be adopted as an "
                "Evidence digest merely by looking like one"
            )
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        value = _text(_required(data, "value", where), f"{where}.value")
        return cls(
            workspace_id=_text(
                _required(data, "workspace_id", where), f"{where}.workspace_id"
            ),
            source_kind=_text(
                _required(data, "source_kind", where), f"{where}.source_kind"
            ),
            source_identity=_text(
                _required(data, "source_identity", where), f"{where}.source_identity"
            ),
            source_revision=_revision(
                _required(data, "source_revision", where), f"{where}.source_revision"
            ),
            subject=_text(_required(data, "subject", where), f"{where}.subject"),
            value_digest=value_digest_of(value),
            item_kind=_enum(
                _required(data, "item_kind", where), ItemKind, f"{where}.item_kind"
            ),
            truth_state=_enum(
                _required(data, "truth_state", where), StatusValue, f"{where}.truth_state"
            ),
            freshness=_enum(
                _required(data, "freshness", where), Freshness, f"{where}.freshness"
            ),
        )

    #: The set-semantic ordering key (§15.4). The exact frozen identity tuple.
    @property
    def canonical_key(self) -> tuple[str, ...]:
        return (
            self.workspace_id,
            self.source_kind,
            self.source_identity,
            self.source_revision,
            self.subject,
            self.value_digest,
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "source_kind": self.source_kind,
            "source_identity": self.source_identity,
            "source_revision": self.source_revision,
            "subject": self.subject,
            "value_digest": self.value_digest,
            "item_kind": str(self.item_kind),
            "truth_state": str(self.truth_state),
            "freshness": str(self.freshness),
        }


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A reference to bytes AI-05 never reads (§13).

    `artifact_digest` is the one caller-supplied digest, because the producer
    holds the bytes and AI-05 does not (§13.5). Its declared role is
    artifact-byte integrity — not the representation of a record's own content —
    which is why it is not an exception to R1 but a different field.

    `artifact_ref` is an **opaque locator**, never a path. Because it is opaque,
    relocation cannot change it, which is what lets promotion alter no field
    (§20.3).
    """

    artifact_digest: str
    external: bool
    role: str | None = None
    owner_workspace_id: str | None = None
    artifact_ref: str | None = None

    _SUPPLIED_KEYS = frozenset(
        {"artifact_digest", "role", "external", "owner_workspace_id", "artifact_ref"}
    )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "artifacts[]") -> "ArtifactRef":
        data = _mapping(raw, where)
        if "availability" in data or "artifact_state" in data:
            raise RawContentRejected(
                f"{where}: artifact availability is a query-time fact about the "
                "store, never a record field (§13.3). Recording it would require "
                "writing to the record when the artifact expires, which §19 forbids"
            )
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        external = _required(data, "external", where)
        if not isinstance(external, bool):
            raise RecordMalformed(
                f"{where}.external must be true or false; got {type(external).__name__}"
            )
        owner = _optional_text(data.get("owner_workspace_id"), f"{where}.owner_workspace_id")
        if external and owner is None:
            raise MissingRequiredField(
                f"{where}.owner_workspace_id is required when external is true (§13.6)"
            )
        role = data.get("role")
        return cls(
            artifact_digest=_sha256(
                _required(data, "artifact_digest", where), f"{where}.artifact_digest"
            ),
            external=external,
            role=None if role is None else _text(role, f"{where}.role"),
            owner_workspace_id=owner,
            artifact_ref=_optional_text(data.get("artifact_ref"), f"{where}.artifact_ref"),
        )

    @property
    def canonical_key(self) -> tuple[str, str]:
        """The set-semantic ordering key (§15.4): `(role, artifact_digest)`.

        `artifact_ref` is deliberately absent — it is a locator, not an ordering
        input, and ordering by it would make the digest depend on where the bytes
        happen to live.
        """
        return (self.role or "", self.artifact_digest)

    def to_projection(self) -> dict[str, Any]:
        return {
            "artifact_digest": self.artifact_digest,
            "role": self.role,
            "external": self.external,
            "owner_workspace_id": self.owner_workspace_id,
            "artifact_ref": self.artifact_ref,
        }


@dataclass(frozen=True, slots=True)
class RecordRef:
    """A link to a durable record (§25). SET-semantic, ordered by `record_ref`."""

    record_ref: str

    @classmethod
    def from_mapping(cls, raw: object, where: str = "decisions[]") -> "RecordRef":
        if isinstance(raw, str):
            return cls(record_ref=_record_ref(raw, where))
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"record_ref"}), where)
        return cls(
            record_ref=_record_ref(
                _required(data, "record_ref", where), f"{where}.record_ref"
            )
        )

    @property
    def canonical_key(self) -> tuple[str]:
        return (self.record_ref,)

    def to_projection(self) -> dict[str, Any]:
        return {"record_ref": self.record_ref}


@dataclass(frozen=True, slots=True)
class SupersedeRef:
    """A forward reference to a record this one corrects (§21.1).

    Forward only, on the NEW record. The superseded record is never touched, so
    `superseded_by` is derived by query and never stored (§21.2).

    `correction_reason` carries no declared field class in the contract — §14.2
    forbids a free-text class and does not assign this field to another. It is
    length-capped here, and the gap is reported as C-2 rather than settled
    silently.
    """

    record_ref: str
    correction_reason: str

    #: A declared cap, because an unbounded string is not a bounded field.
    MAX_REASON_LENGTH = 512

    _SUPPLIED_KEYS = frozenset({"record_ref", "correction_reason"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "supersedes[]") -> "SupersedeRef":
        data = _mapping(raw, where)
        _closed_keys(data, cls._SUPPLIED_KEYS, where)
        reason = _text(
            _required(data, "correction_reason", where), f"{where}.correction_reason"
        )
        if len(reason) > cls.MAX_REASON_LENGTH:
            raise RecordMalformed(
                f"{where}.correction_reason exceeds {cls.MAX_REASON_LENGTH} "
                f"characters; got {len(reason)}"
            )
        return cls(
            record_ref=_record_ref(
                _required(data, "record_ref", where), f"{where}.record_ref"
            ),
            correction_reason=reason,
        )

    @property
    def canonical_key(self) -> tuple[str]:
        return (self.record_ref,)

    def to_projection(self) -> dict[str, Any]:
        return {
            "record_ref": self.record_ref,
            "correction_reason": self.correction_reason,
        }


# --------------------------------------------------------------------------
# Payloads (§11)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObservationPayload:
    """What an OBSERVATION asserts (§11). Fields are SEMANTIC."""

    subject: str
    observed: str
    outcome: StatusValue | None = None

    _KEYS = frozenset({"subject", "observed", "outcome"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "ObservationPayload":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        outcome = data.get("outcome")
        return cls(
            subject=_text(_required(data, "subject", where), f"{where}.subject"),
            observed=_text(_required(data, "observed", where), f"{where}.observed"),
            outcome=(
                None
                if outcome is None
                else _enum(outcome, StatusValue, f"{where}.outcome")
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "observed": self.observed,
            "outcome": None if self.outcome is None else str(self.outcome),
        }


@dataclass(frozen=True, slots=True)
class DecisionPayload:
    """What a DECISION asserts (§11). Fields are SEMANTIC."""

    decision: GuardDecision
    reason_code: str
    reasons: tuple[str, ...] = ()

    _KEYS = frozenset({"decision", "reason_code", "reasons"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "DecisionPayload":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        reasons_raw = data.get("reasons", [])
        return cls(
            decision=_enum(
                _required(data, "decision", where), GuardDecision, f"{where}.decision"
            ),
            reason_code=_text(
                _required(data, "reason_code", where), f"{where}.reason_code"
            ),
            reasons=tuple(
                _text(entry, f"{where}.reasons[]")
                for entry in _sequence(reasons_raw, f"{where}.reasons")
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "decision": str(self.decision),
            "reason_code": self.reason_code,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One step in an EXECUTION's sequence (§11.1).

    `ordinal` is the semantic ordering. **Array position is not.** Serializing
    in array order would make the digest depend on how the caller happened to
    write the list — the defect AI-04-B §E.1 recorded — so the collection is
    sorted by this value before hashing, and the array is free to be rewritten.
    """

    ordinal: int
    name: str
    status: StatusValue

    _KEYS = frozenset({"ordinal", "name", "status"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "tool_calls[]") -> "ToolCall":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        ordinal = _required(data, "ordinal", where)
        if isinstance(ordinal, bool) or not isinstance(ordinal, int):
            raise RecordMalformed(
                f"{where}.ordinal must be an integer; got {type(ordinal).__name__}"
            )
        if ordinal < 0:
            raise RecordMalformed(f"{where}.ordinal must not be negative")
        return cls(
            ordinal=ordinal,
            name=_text(_required(data, "name", where), f"{where}.name"),
            status=_enum(
                _required(data, "status", where), StatusValue, f"{where}.status"
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "name": self.name,
            "status": str(self.status),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPayload:
    """What an EXECUTION asserts (§11). ORDER-semantic by explicit ordinal."""

    tool_calls: tuple[ToolCall, ...] = ()

    _KEYS = frozenset({"tool_calls"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "payload") -> "ExecutionPayload":
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls(
            tool_calls=tuple(
                ToolCall.from_mapping(entry, f"{where}.tool_calls[]")
                for entry in _sequence(data.get("tool_calls", []), f"{where}.tool_calls")
            )
        )

    def to_projection(self) -> dict[str, Any]:
        return {"tool_calls": [call.to_projection() for call in self.tool_calls]}


PAYLOAD_BY_KIND: Mapping[EvidenceKind, type] = {
    EvidenceKind.OBSERVATION: ObservationPayload,
    EvidenceKind.DECISION: DecisionPayload,
    EvidenceKind.EXECUTION: ExecutionPayload,
}


# --------------------------------------------------------------------------
# Envelope sections
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Identity:
    """`identity` (§5). `evidence_id` is AI-05-generated and never caller-supplied."""

    kind: EvidenceKind
    evidence_id: str | None = None

    def to_projection(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, "kind": str(self.kind)}


@dataclass(frozen=True, slots=True)
class Provenance:
    """`provenance` (§7, §9).

    `producer` is the component that WROTE the record; `actor` is the entity
    whose act it describes. Different questions, different fields, never
    conflated — which is why `kind` can be DECISION while `actor.type` is human.
    """

    producer: str
    producer_version: str
    producer_type: ActorType
    actor: Actor
    workspace_id: str
    recorded_at: str
    experiment_id: str | None = None
    observed_at: str | None = None

    _SUPPLIED_KEYS = frozenset(
        {
            "producer",
            "producer_version",
            "producer_type",
            "actor",
            "workspace_id",
            "experiment_id",
            "observed_at",
        }
    )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "provenance") -> "Provenance":
        data = _mapping(raw, where)
        if "recorded_at" in data:
            raise CallerSuppliedGeneratedField(
                f"{where}.recorded_at: AI-05 stamps this when it writes the "
                "record (§15.2); it is not caller-supplied"
            )
        _closed_keys(data, cls._SUPPLIED_KEYS, where)

        producer_type_raw = _required(data, "producer_type", where)
        try:
            producer_type = ActorType(producer_type_raw)
        except ValueError:
            raise UnsupportedVocabulary(
                f"{where}.producer_type: {producer_type_raw!r} is not one of "
                f"{', '.join(sorted(m.value for m in ActorType))}"
            ) from None
        if not producer_type_is_permitted(producer_type):
            raise ProducerRoleViolation(
                f"{where}.producer_type: {producer_type} is a member of the "
                "inherited ActorType vocabulary but is not a valid producer role "
                "(§7.1). The producer is the component that wrote the record; a "
                "human does not author an EvidenceRecord directly"
            )

        experiment_id = data.get("experiment_id")
        return cls(
            producer=_text(_required(data, "producer", where), f"{where}.producer"),
            producer_version=_text(
                _required(data, "producer_version", where), f"{where}.producer_version"
            ),
            producer_type=producer_type,
            actor=Actor.from_mapping(_required(data, "actor", where), f"{where}.actor"),
            workspace_id=_text(
                _required(data, "workspace_id", where), f"{where}.workspace_id"
            ),
            recorded_at="",
            experiment_id=(
                None
                if experiment_id is None
                else _identifier(experiment_id, f"{where}.experiment_id")
            ),
            observed_at=_optional_text(data.get("observed_at"), f"{where}.observed_at"),
        )


@dataclass(frozen=True, slots=True)
class References:
    """`references` (§5, §12, §21). All three collections are SET-semantic."""

    context: tuple[ContextRef, ...] = ()
    decisions: tuple[RecordRef, ...] = ()
    supersedes: tuple[SupersedeRef, ...] = ()

    _KEYS = frozenset({"context", "decisions", "supersedes"})

    @classmethod
    def from_mapping(cls, raw: object, where: str = "references") -> "References":
        if raw is None:
            return cls()
        data = _mapping(raw, where)
        _closed_keys(data, cls._KEYS, where)
        return cls(
            context=tuple(
                ContextRef.from_mapping(entry, f"{where}.context[]")
                for entry in _sequence(data.get("context", []), f"{where}.context")
            ),
            decisions=tuple(
                RecordRef.from_mapping(entry, f"{where}.decisions[]")
                for entry in _sequence(data.get("decisions", []), f"{where}.decisions")
            ),
            supersedes=tuple(
                SupersedeRef.from_mapping(entry, f"{where}.supersedes[]")
                for entry in _sequence(data.get("supersedes", []), f"{where}.supersedes")
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "context": [item.to_projection() for item in self.context],
            "decisions": [item.to_projection() for item in self.decisions],
            "supersedes": [item.to_projection() for item in self.supersedes],
        }


@dataclass(frozen=True, slots=True)
class Artifacts:
    """`artifacts` (§13). SET-semantic."""

    items: tuple[ArtifactRef, ...] = ()

    @classmethod
    def from_mapping(cls, raw: object, where: str = "artifacts") -> "Artifacts":
        if raw is None:
            return cls()
        data = _mapping(raw, where)
        _closed_keys(data, frozenset({"items"}), where)
        return cls(
            items=tuple(
                ArtifactRef.from_mapping(entry, f"{where}.items[]")
                for entry in _sequence(data.get("items", []), f"{where}.items")
            )
        )

    def to_projection(self) -> dict[str, Any]:
        return {"items": [item.to_projection() for item in self.items]}


@dataclass(frozen=True, slots=True)
class Integrity:
    """`integrity` (§16, §17). Both digests are AI-05-generated (R1)."""

    content_digest: str | None = None
    record_digest: str | None = None

    def to_projection(self) -> dict[str, Any]:
        return {
            "content_digest": self.content_digest,
            "record_digest": self.record_digest,
        }


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


_EVIDENCE_ID_KEYS = frozenset({"evidence_id", "record_digest", "content_digest"})

_TOP_KEYS = frozenset(
    {
        "schema_version",
        "evidence_id",
        "record_digest",
        "content_digest",
        "identity",
        "kind",
        "payload",
        "provenance",
        "references",
        "artifacts",
        "integrity",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """The AI-05 record (§5). Envelope plus a typed payload.

    Constructed through `from_mapping`, which is where the strictness lives: a
    field the contract does not define is refused, a caller-supplied generated
    field is refused, and the payload must be the one this kind declares.
    """

    identity: Identity
    provenance: Provenance
    payload: Any
    schema_version: int = SUPPORTED_SCHEMA_VERSION
    references: References = field(default_factory=References)
    artifacts: Artifacts = field(default_factory=Artifacts)
    integrity: Integrity = field(default_factory=Integrity)

    @property
    def kind(self) -> EvidenceKind:
        return self.identity.kind

    @property
    def evidence_id(self) -> str | None:
        return self.identity.evidence_id

    @classmethod
    def from_mapping(
        cls,
        raw: object,
        *,
        evidence_id: str | None = None,
        clock=None,
    ) -> "EvidenceRecord":
        """Parse a supplied record, stamping the fields AI-05 generates.

        The supplied form carries **no** `evidence_id`, `recorded_at`,
        `content_digest`, `record_digest` or `value_digest`. Supplying one is
        refused rather than ignored, because accepting it would let a caller
        substitute a digest for content AI-05 never admitted (§14.6.1, R1).
        """
        data = _mapping(raw, "record")

        for name in sorted(_EVIDENCE_ID_KEYS & set(data)):
            error = (
                CallerSuppliedIdentity
                if name == "evidence_id"
                else CallerSuppliedDigest
            )
            raise error(
                f"record.{name}: AI-05 generates this (§14.6.1, §8.1). Digest-shaped "
                "is not the same as trustworthy — a caller-supplied value is refused "
                "whatever its shape"
            )
        if "recorded_at" in _mapping(data.get("provenance", {}) or {}, "provenance"):
            raise CallerSuppliedGeneratedField(
                "provenance.recorded_at: AI-05 stamps this when it writes the record"
            )

        _closed_keys(data, _TOP_KEYS, "record")

        version = data.get("schema_version")
        if version != SUPPORTED_SCHEMA_VERSION:
            raise UnsupportedVocabulary(
                f"record.schema_version {version!r} is not supported; this "
                f"contract defines {SUPPORTED_SCHEMA_VERSION}"
            )

        kind = _enum(_required(data, "kind", "record"), EvidenceKind, "record.kind")

        payload_raw = _required(data, "payload", "record")
        payload_type = PAYLOAD_BY_KIND[kind]
        payload = payload_type.from_mapping(payload_raw, "payload")

        provenance = Provenance.from_mapping(
            _required(data, "provenance", "record"), "provenance"
        )
        # `recorded_at` is AI-05's to stamp, so it is set here rather than parsed.
        provenance = replace(provenance, recorded_at=(clock or utc_now)())

        return cls(
            identity=Identity(
                kind=kind, evidence_id=evidence_id or new_evidence_id()
            ),
            provenance=provenance,
            payload=payload,
            schema_version=version,
            references=References.from_mapping(data.get("references"), "references"),
            artifacts=Artifacts.from_mapping(data.get("artifacts"), "artifacts"),
            integrity=Integrity(),
        )

    def with_integrity(self, integrity: Integrity) -> "EvidenceRecord":
        """Return a copy carrying computed digests. Never mutates in place."""
        return replace(self, integrity=integrity)

    def assert_kind_matches_payload(self) -> None:
        """The payload must be the one this kind declares (§11)."""
        expected = PAYLOAD_BY_KIND[self.identity.kind]
        if not isinstance(self.payload, expected):
            raise PayloadKindMismatch(
                f"kind {self.identity.kind} requires a {expected.__name__}; got "
                f"{type(self.payload).__name__}"
            )


__all__ = [
    "EVIDENCE_ID_PREFIX",
    "IDENTIFIER_RE",
    "PAYLOAD_BY_KIND",
    "SUPPORTED_SCHEMA_VERSION",
    "Actor",
    "ArtifactRef",
    "Artifacts",
    "ContextRef",
    "DecisionPayload",
    "EvidenceRecord",
    "ExecutionPayload",
    "Identity",
    "Integrity",
    "ObservationPayload",
    "Provenance",
    "RecordRef",
    "References",
    "SupersedeRef",
    "ToolCall",
    "new_evidence_id",
    "value_digest_of",
]
