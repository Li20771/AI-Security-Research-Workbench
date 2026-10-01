"""The thirteen frozen grammars.

Implements AI-05 contract §14.9. Before Amendment 1 the implementation validated
with ad-hoc helpers scattered through `models.py` — a bare length, a bare
character class, a bare "is it a string" — and the contract's grammar names had
no counterpart in code. A field's rule could therefore only be discovered by
reading the call site that happened to apply it.

**This is not a grammar engine.** It is thirteen named functions, one per frozen
grammar, plus the conditional rule for `G-REVISION`. There is no parser, no rule
registry, no plugin point, and no way to add a fourteenth grammar without an
amendment to the contract. Each function does one thing: it returns the value,
or it raises.

**Every function raises; none repairs.** No function lowercases, trims, flattens
or substitutes. §14.4.1 makes AI-05 the layer that never rewrites an accepted
value, so an uppercase digest is REJECTED rather than normalized, and a
multi-line value is REJECTED rather than flattened.

The origin labels are the contract's, and two of them matter for the reader:

    REPOSITORY-DERIVED    the rule comes from an existing AI-02/AI-03 artefact
    IMPLEMENTATION-CHOSEN the contract requires a bound and AI-05 picks it
"""

from __future__ import annotations

import re

from providers.profile import PROVIDER_ID_RE, ModelRef, ProfileError

# `_MODEL_ID_RE` is module-private in AI-02. It is imported rather than copied
# because the alternative is a second definition of AI-02's model-id grammar,
# which is the divergence §3 forbids: two definitions in one repository means
# two places to update and one of them forgotten. The contract names this
# grammar REPOSITORY-DERIVED for exactly this reason, and a copy would be the
# narrower pattern Amendment 1 corrected.
from providers.model_profile import _MODEL_ID_RE

from plugins.evidence.errors import (
    FieldClassViolation,
    InvalidDigestShape,
    InvalidIdentifier,
    NonCanonicalDigestCase,
    ProducerNotRegistered,
    RecordMalformed,
)
from plugins.context.vocabulary import SourceKind

# --------------------------------------------------------------------------
# Shared character classes
# --------------------------------------------------------------------------

_LOWER_HEX = re.compile(r"^[0-9a-f]+$")
_UPPER_HEX = re.compile(r"^[0-9A-F]+$")

#: G-EVIDENCE-ID (§8.1, §14.9). IMPLEMENTATION-CHOSEN width.
_EVIDENCE_ID = re.compile(r"^ev-[0-9a-f]{16}$")

#: G-IDENT (§14.9). IMPLEMENTATION-CHOSEN.
_IDENT = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: G-TIMESTAMP (§10.3, §14.9). REPOSITORY-DERIVED: AI-03's `utc_now()` emits
#: exactly this form, and AI-02's `live_verification` uses second resolution.
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_GIT_SHA_LEN = 40
_SHA256_LEN = 64


def _reject(value: object, field_name: str, expectation: str) -> None:
    """One rejection shape, so no message can leak the supplied value.

    A structural field is a place a caller might have put something that is not
    a digest at all (§14.8), so no message interpolates the value. It names the
    field, the expectation, and at most a length or a character class.
    """
    raise FieldClassViolation(
        f"{field_name}: {expectation}; got {_describe(value)}"
    )


def _describe(value: object) -> str:
    if isinstance(value, str):
        return f"{len(value)} characters"
    return type(value).__name__


def _string(value: object, field_name: str, expectation: str) -> str:
    if not isinstance(value, str):
        raise FieldClassViolation(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    return value


def _single_line(value: str, field_name: str, expectation: str) -> None:
    if "\n" in value or "\r" in value:
        _reject(value, field_name, expectation)


# --------------------------------------------------------------------------
# G-EVIDENCE-ID
# --------------------------------------------------------------------------


def g_evidence_id(value: object, field_name: str) -> str:
    """`^ev-[0-9a-f]{16}$`. AI-05's own identity representation (§8.1)."""
    text = _string(value, field_name, "must be ev- followed by 16 lowercase hex")
    if not _EVIDENCE_ID.match(text):
        raise InvalidIdentifier(
            f"{field_name} must be ev- followed by 16 lowercase hexadecimal "
            f"characters; got {len(text)} characters"
        )
    return text


# --------------------------------------------------------------------------
# G-DIGEST
# --------------------------------------------------------------------------


def g_digest(value: object, field_name: str) -> str:
    """Exactly 64 lowercase hexadecimal characters. REPOSITORY-DERIVED (§20.2)."""
    return _hex_of_length(value, field_name, _SHA256_LEN)


# --------------------------------------------------------------------------
# G-IDENT
# --------------------------------------------------------------------------


def g_ident(value: object, field_name: str) -> str:
    """`^[A-Za-z0-9._-]{1,64}$`. IMPLEMENTATION-CHOSEN."""
    text = _string(value, field_name, "must be an identifier")
    if not _IDENT.match(text):
        raise InvalidIdentifier(
            f"{field_name} must match {_IDENT.pattern}; got {len(text)} characters"
        )
    return text


# --------------------------------------------------------------------------
# G-SUBJECT
# --------------------------------------------------------------------------


def g_subject(value: object, field_name: str) -> str:
    """Non-empty, single-line, at most 256 characters, otherwise uninterpreted.

    The bound admits AI-03's longest subject with margin. AI-03 derives a
    subject as `declared.` plus a normalised declaration key of up to 80
    characters (`plugins/context/declarations.py`), so a legal AI-03 subject can
    reach 89. An identifier grammar would have rejected the longer ones, which
    it did before Amendment 1.
    """
    text = _string(value, field_name, "must be a subject")
    if not text.strip():
        _reject(value, field_name, "must not be empty")
    _single_line(text, field_name, "must be a single line")
    if len(text) > 256:
        _reject(value, field_name, "must be at most 256 characters")
    return text


# --------------------------------------------------------------------------
# G-OPAQUE-ID
# --------------------------------------------------------------------------


def g_opaque_id(value: object, field_name: str) -> str:
    """Non-empty, single-line, at most 512 characters, otherwise uninterpreted.

    A path-shaped value is legal: AI-03's `source_identity` is the bare token
    `git` for one source and `docs/MASTER_ROADMAP.md` for another, and the
    contract freezes only "stable identity of the thing read".
    """
    text = _string(value, field_name, "must be an opaque identity")
    if not text.strip():
        _reject(value, field_name, "must not be empty")
    _single_line(text, field_name, "must be a single line")
    if len(text) > 512:
        _reject(value, field_name, "must be at most 512 characters")
    return text


# --------------------------------------------------------------------------
# G-HOST
# --------------------------------------------------------------------------


def g_host(value: object, field_name: str) -> str:
    """Non-empty, single-line, lowercase, no at-sign, colon, slash or whitespace.

    The exclusions are REPOSITORY-DERIVED: AI-02's `endpoint_host()` drops any
    userinfo segment, drops the port and lowercases the host, so a value still
    containing those characters is not an endpoint host. AI-02 states no lexical
    grammar, so the character set and the 253 bound are IMPLEMENTATION-CHOSEN.
    """
    text = _string(value, field_name, "must be a hostname")
    if not text:
        _reject(value, field_name, "must not be empty")
    _single_line(text, field_name, "must be a single line")
    if len(text) > 253:
        _reject(value, field_name, "must be at most 253 characters")
    if text != text.lower():
        _reject(value, field_name, "must be lowercase")
    forbidden = [c for c in "@:/" if c in text]
    if forbidden or any(c.isspace() for c in text):
        _reject(value, field_name, "must not contain userinfo, port, path or whitespace")
    return text


# --------------------------------------------------------------------------
# G-MODELREF
# --------------------------------------------------------------------------


def g_modelref(value: object, field_name: str) -> str:
    """`PROVIDER_ID_RE` + exactly one slash + `_MODEL_ID_RE`. REPOSITORY-DERIVED.

    Composed from AI-02's own parts rather than restated. A `model_ref` that
    AI-02 accepts, AI-05 MUST NOT reject — including one whose model id contains
    a colon, which AI-02's `_MODEL_ID_RE` permits and a narrower pattern would
    have refused.
    """
    text = _string(value, field_name, "must be a provider/model reference")
    try:
        parsed = ModelRef.parse(text)
    except ProfileError as exc:
        raise FieldClassViolation(f"{field_name}: {exc}") from None

    if not PROVIDER_ID_RE.match(parsed.provider_id):
        raise FieldClassViolation(
            f"{field_name} has a provider part that is not a valid provider id"
        )
    if not _MODEL_ID_RE.match(parsed.model_id):
        raise FieldClassViolation(
            f"{field_name} has a model part that is not a valid model id"
        )
    return str(parsed)


# --------------------------------------------------------------------------
# G-REVISION
# --------------------------------------------------------------------------

#: The conditional revision rule (§12.1), as a frozen mapping.
_GIT_REVISION_KINDS: frozenset[SourceKind] = frozenset(
    {SourceKind.GIT_CURRENT_STATE, SourceKind.GIT_HISTORY}
)
_DOCUMENT_REVISION_KINDS: frozenset[SourceKind] = frozenset(
    {
        SourceKind.MASTER_ROADMAP,
        SourceKind.CAPABILITY_INVENTORY,
        SourceKind.DESIGN_FREEZE,
        SourceKind.EXIT_REPORT,
    }
)


def revision_length_for(source_kind: SourceKind) -> int:
    """The required revision width for a source kind (§12.1).

    Raises for anything outside AI-03's closed `SourceKind`, because the rule is
    total over exactly six members and a seventh is a contract amendment.
    """
    if source_kind in _GIT_REVISION_KINDS:
        return _GIT_SHA_LEN
    if source_kind in _DOCUMENT_REVISION_KINDS:
        return _SHA256_LEN
    raise RecordMalformed(
        f"source_kind {source_kind!r} has no frozen revision width; SourceKind is "
        "closed and those are its only six members (§12.1)"
    )


def g_revision(value: object, source_kind: SourceKind, field_name: str) -> str:
    """The conditional revision grammar (§12.1). REPOSITORY-DERIVED.

    Takes the sibling `source_kind` as an argument because the contract makes the
    rule conditional and the implementation MUST NOT infer it. Both the
    `ContextRef` path and the binding path call this same function, which is what
    makes their behaviour identical by construction rather than by agreement.
    """
    required = revision_length_for(source_kind)
    return _hex_of_length(value, field_name, required)


# --------------------------------------------------------------------------
# G-TIMESTAMP
# --------------------------------------------------------------------------


def g_timestamp(value: object, field_name: str) -> str:
    """ISO-8601 UTC with a trailing `Z`, at second resolution (§10.3).

    REPOSITORY-DERIVED. Syntax only: whether a timestamp is SEMANTIC is §10.2's
    question and is decided by the field's kind, not by this grammar.
    """
    text = _string(value, field_name, "must be an ISO-8601 UTC timestamp")
    if not _TIMESTAMP.match(text):
        raise FieldClassViolation(
            f"{field_name} must be ISO-8601 UTC with a trailing Z at second "
            "resolution, as in 2026-09-30T00:00:00Z"
        )
    return text


# --------------------------------------------------------------------------
# G-LOCATOR
# --------------------------------------------------------------------------


def g_locator(value: object, field_name: str) -> str:
    """Non-empty, single-line, at most 512 characters, otherwise uninterpreted.

    AI-05 never resolves or parses the value. §13.1's "opaque identifier, never a
    path" describes that behaviour and is NOT lexically enforced here: a path is
    not refused by shape, because the contract states no such rule and inventing
    one would be the unevidenced exclusion Amendment 1 removed.
    """
    text = _string(value, field_name, "must be an opaque locator")
    if not text.strip():
        _reject(value, field_name, "must not be empty")
    _single_line(text, field_name, "must be a single line")
    if len(text) > 512:
        _reject(value, field_name, "must be at most 512 characters")
    return text


# --------------------------------------------------------------------------
# G-TEXT
# --------------------------------------------------------------------------


def g_text(value: object, field_name: str) -> str:
    """Single-line bounded producer-normalized text, at most 512 characters.

    The producer flattens newlines before submission. AI-05 validates and
    REJECTS a multi-line value rather than flattening it, because flattening
    would be the silent substitution §14.4.1 forbids.
    """
    text = _string(value, field_name, "must be bounded text")
    if not text.strip():
        _reject(value, field_name, "must not be empty")
    _single_line(text, field_name, "must be a single line")
    if len(text) > 512:
        _reject(value, field_name, "must be at most 512 characters")
    return text


# --------------------------------------------------------------------------
# G-REGISTERED
# --------------------------------------------------------------------------


def g_registered(value: object, allowed: frozenset[str], field_name: str) -> str:
    """The token admitted by the §6.5 registry for the current kind and family.

    Takes the allowed set as an argument rather than looking it up, so the
    grammar stays a validator and the registry stays in `models.py`. The registry
    requirement is CONTRACT-REQUIRED; the token spellings are
    IMPLEMENTATION-CHOSEN and frozen by Amendment 1.
    """
    text = _string(value, field_name, "must be a registered producer token")
    if text not in allowed:
        raise ProducerNotRegistered(
            f"{field_name}: {text!r} is not the token registered for this kind and "
            f"family (§6.5); expected one of {sorted(allowed)}"
        )
    return text


# --------------------------------------------------------------------------
# G-ORDINAL
# --------------------------------------------------------------------------


def g_ordinal(value: object, field_name: str) -> int:
    """A non-negative integer, unique within its collection, not contiguous.

    Uniqueness is a collection property and is checked by the collection. This
    function validates the value's own shape.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecordMalformed(
            f"{field_name} must be an integer; got {type(value).__name__}"
        )
    if value < 0:
        raise RecordMalformed(f"{field_name} must not be negative")
    return value


# --------------------------------------------------------------------------
# shared internals
# --------------------------------------------------------------------------


def _hex_of_length(value: object, field_name: str, length: int) -> str:
    """Lowercase hex of an exact length, with case refused rather than fixed.

    Every failure here is an `InvalidDigestShape`, including a non-string, so a
    caller catching the structural-class error catches all of them.
    """
    if not isinstance(value, str):
        raise InvalidDigestShape(
            f"{field_name} must be a string of {length} lowercase hex characters; "
            f"got {type(value).__name__}"
        )
    text = value
    if len(text) != length:
        raise InvalidDigestShape(
            f"{field_name} must be exactly {length} characters; got {len(text)}"
        )
    if not _LOWER_HEX.match(text):
        if _UPPER_HEX.match(text):
            raise NonCanonicalDigestCase(
                f"{field_name} is uppercase hexadecimal; §14.5.1 requires lowercase, "
                "and AI-05 does not normalize what it accepts"
            )
        raise InvalidDigestShape(
            f"{field_name} must be lowercase hexadecimal of length {length}; "
            f"got {len(text)} characters containing a non-hex character"
        )
    return text


GRAMMAR_NAMES: tuple[str, ...] = (
    "G-EVIDENCE-ID",
    "G-DIGEST",
    "G-IDENT",
    "G-SUBJECT",
    "G-OPAQUE-ID",
    "G-HOST",
    "G-MODELREF",
    "G-REVISION",
    "G-TIMESTAMP",
    "G-LOCATOR",
    "G-TEXT",
    "G-REGISTERED",
    "G-ORDINAL",
)

__all__ = [
    "GRAMMAR_NAMES",
    "g_digest",
    "g_evidence_id",
    "g_host",
    "g_ident",
    "g_locator",
    "g_modelref",
    "g_opaque_id",
    "g_ordinal",
    "g_registered",
    "g_revision",
    "g_subject",
    "g_text",
    "g_timestamp",
    "revision_length_for",
]
