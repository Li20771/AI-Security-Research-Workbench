"""Canonicalization and the authoritative field table.

Implements contract §15 — and §15.2 in particular, which is **the single source
of truth for digest behaviour**. The table is data here, not prose: both
projections are built by walking it, so a field cannot acquire a second
classification somewhere else without a test noticing.

The serialization primitive is imported from AI-04's `plugins.guard.digest`,
because §15 says AI-04's §20.2 rules are imported rather than restated. What is
**not** imported is AI-04's projection: `request_projection` and
`evaluation_projection` answer AI-04's questions about AI-04's fields. AI-05
owns its own classification.

### What canonicalization is not allowed to do

It represents an already-valid record deterministically. It does not make an
invalid record valid. Specifically it never:

    strips arbitrary fields           lowercases arbitrary fields
    redacts                           normalizes secrets
    repairs malformed values          drops unknown fields

An uppercase SHA-256 is **rejected**, not quietly lowered — normalizing would
mean substituting an accepted value, which §14.4 forbids. Canonicalization runs
after validation and never instead of it.

### Two orders, deliberately different (§15.4)

Set-semantic collections are sorted by their frozen identity tuple before
hashing, so a digest cannot depend on the order a caller happened to write a
list in. Order-semantic collections keep their meaning but are still sorted —
by their **explicit ordinal**, never by array position. Array position is an
input the caller controls; sorting by it is the defect AI-04-B §E.1 recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

# The serialization primitive only. AI-04's semantic projections are not reused.
from plugins.guard.digest import canonical_json, sha256_hex

from plugins.evidence.models import EvidenceRecord
from plugins.evidence.vocabulary import EvidenceKind

__all__ = [
    "CONTENT_EXCLUDED_PATHS",
    "FIELD_TABLE",
    "DigestRole",
    "FieldRow",
    "Inclusion",
    "canonical_json",
    "content_projection",
    "observed_at_is_semantic",
    "record_projection",
    "sha256_hex",
]


class DigestRole(StrEnum):
    """What job a field does (§15.2)."""

    SEMANTIC = "semantic"
    OPERATIONAL = "operational"
    IDENTITY = "identity"
    LOCATOR = "locator"
    INTEGRITY = "integrity"
    RUNTIME = "runtime"
    NOT_CONTENT = "not_content"


class Inclusion(StrEnum):
    """Whether a field enters a given digest (§15.2)."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    PER_KIND = "per_kind"
    #: It *is* the digest, so it is not its own input.
    IS_THE_DIGEST = "is_the_digest"
    #: Not a field of the record at all.
    NOT_A_FIELD = "not_a_field"


@dataclass(frozen=True, slots=True)
class FieldRow:
    """One row of the §15.2 authoritative table."""

    path: str
    role: DigestRole
    content: Inclusion
    record: Inclusion
    caller_supplied: bool
    ai05_generated: bool


#: §15.2, transcribed. This tuple **is** the contract's table.
#:
#: `record` is the digest over the stored record; `content` is the semantic
#: equivalence digest. A field may be in the second and not the first
#: (`record_digest`), or the first and not the second (`evidence_id`,
#: `recorded_at`, `experiment_id`, `producer_version`, `artifact_ref`).
FIELD_TABLE: tuple[FieldRow, ...] = (
    # ---- identity -------------------------------------------------------
    FieldRow("evidence_id", DigestRole.IDENTITY, Inclusion.EXCLUDED,
             Inclusion.INCLUDED, False, True),
    FieldRow("schema_version", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("kind", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    # ---- provenance -----------------------------------------------------
    FieldRow("producer", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("producer_version", DigestRole.OPERATIONAL, Inclusion.EXCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("producer_type", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("actor.id", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("actor.type", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("workspace_id", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("experiment_id", DigestRole.OPERATIONAL, Inclusion.EXCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("observed_at", DigestRole.SEMANTIC, Inclusion.PER_KIND,
             Inclusion.INCLUDED, True, False),
    FieldRow("recorded_at", DigestRole.OPERATIONAL, Inclusion.EXCLUDED,
             Inclusion.INCLUDED, False, True),
    # ---- payload --------------------------------------------------------
    FieldRow("payload", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    # ---- references -----------------------------------------------------
    FieldRow("references.context", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("references.decisions", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    FieldRow("references.supersedes", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    # ---- artifacts ------------------------------------------------------
    FieldRow("artifacts.items", DigestRole.SEMANTIC, Inclusion.INCLUDED,
             Inclusion.INCLUDED, True, False),
    # ---- integrity ------------------------------------------------------
    FieldRow("content_digest", DigestRole.INTEGRITY, Inclusion.IS_THE_DIGEST,
             Inclusion.INCLUDED, False, True),
    FieldRow("record_digest", DigestRole.INTEGRITY, Inclusion.EXCLUDED,
             Inclusion.IS_THE_DIGEST, False, True),
    # ---- not fields of the record ---------------------------------------
    FieldRow("storage_tier", DigestRole.NOT_CONTENT, Inclusion.NOT_A_FIELD,
             Inclusion.NOT_A_FIELD, False, False),
    FieldRow("artifact_availability", DigestRole.RUNTIME, Inclusion.NOT_A_FIELD,
             Inclusion.NOT_A_FIELD, False, False),
)

_TABLE_BY_PATH: Mapping[str, FieldRow] = {row.path: row for row in FIELD_TABLE}

#: §16's exclusion list, derived from the table rather than restated.
CONTENT_EXCLUDED_PATHS: frozenset[str] = frozenset(
    row.path for row in FIELD_TABLE if row.content is Inclusion.EXCLUDED
)

#: §10.2: `observed_at` is semantic where the kind's claim is time-bound.
#: OBSERVATION is dated (AI-02 §11.6 — a result describes one model at one
#: endpoint on one day); EXECUTION is an event. DECISION is not: AI-04 T14 makes
#: re-evaluating one request one fact recorded twice, not two facts.
TIME_BOUND_KINDS: frozenset[EvidenceKind] = frozenset(
    {EvidenceKind.OBSERVATION, EvidenceKind.EXECUTION}
)


def observed_at_is_semantic(kind: EvidenceKind) -> bool:
    """Whether `observed_at` enters the content digest for this kind (§10.2)."""
    return kind in TIME_BOUND_KINDS


def _context_items(record: EvidenceRecord, digest: str) -> list[dict[str, Any]]:
    """ContextRefs, SET-semantic, sorted by the frozen identity tuple (§15.4).

    Every ContextRef field is in both digests (§15.2), so `digest` is unused.
    """
    return [
        item.to_projection()
        for item in sorted(record.references.context, key=lambda i: i.canonical_key)
    ]


def _decision_refs(record: EvidenceRecord, digest: str) -> list[dict[str, Any]]:
    """RecordRefs, SET-semantic, sorted by `record_ref` (§15.4)."""
    return [
        item.to_projection()
        for item in sorted(record.references.decisions, key=lambda i: i.canonical_key)
    ]


def _supersede_refs(record: EvidenceRecord, digest: str) -> list[dict[str, Any]]:
    """SupersedeRefs, SET-semantic, sorted by `record_ref` (§15.4)."""
    return [
        item.to_projection()
        for item in sorted(record.references.supersedes, key=lambda i: i.canonical_key)
    ]


def _artifact_items(record: EvidenceRecord, digest: str) -> list[dict[str, Any]]:
    """ArtifactRefs, SET-semantic, sorted by `(role, artifact_digest)` (§15.4).

    Never by `artifact_ref`. The locator is not an ordering input, and ordering
    by it would make the content digest depend on where the bytes live — the
    opposite of the location-independence §15.3 requires.

    **`artifact_ref` is dropped from the content projection.** §15.2 marks it
    LOCATOR / OPERATIONAL, excluded from `content_digest` and included in
    `record_digest`. It is nested inside this collection rather than being a
    top-level field, so the exclusion has to be applied here — per item — rather
    than by skipping a table row. Getting this wrong makes the content digest
    depend on where an artifact happens to live, which is exactly the property
    the two-digest model exists to provide.
    """
    items = sorted(record.artifacts.items, key=lambda i: i.canonical_key)
    projections = [item.to_projection() for item in items]
    if digest == "content":
        for projection in projections:
            projection.pop("artifact_ref", None)
    return projections


def _payload(record: EvidenceRecord, digest: str) -> dict[str, Any]:
    """The payload projection, with ORDER-semantic collections sorted by ordinal.

    Tool calls are emitted in ascending `ordinal`, **not** in array order. Array
    position is an input the caller controls; sorting by it is the defect
    AI-04-B §E.1 recorded.
    """
    projection = record.payload.to_projection()
    calls = projection.get("tool_calls")
    if isinstance(calls, list):
        projection["tool_calls"] = sorted(calls, key=lambda c: c["ordinal"])
    return projection


#: One resolver per table path. A path with no resolver, or a resolver with no
#: path, is a defect that `test_canonical.py` fails on — which is what keeps the
#: table authoritative instead of decorative.
_RESOLVERS: Mapping[str, Callable[[EvidenceRecord, str], Any]] = {
    "evidence_id": lambda r, d: r.identity.evidence_id,
    "schema_version": lambda r, d: r.schema_version,
    "kind": lambda r, d: str(r.identity.kind),
    "producer": lambda r, d: r.provenance.producer,
    "producer_version": lambda r, d: r.provenance.producer_version,
    "producer_type": lambda r, d: str(r.provenance.producer_type),
    "actor.id": lambda r, d: r.provenance.actor.id,
    "actor.type": lambda r, d: str(r.provenance.actor.type),
    "workspace_id": lambda r, d: r.provenance.workspace_id,
    "experiment_id": lambda r, d: r.provenance.experiment_id,
    "observed_at": lambda r, d: r.provenance.observed_at,
    "recorded_at": lambda r, d: r.provenance.recorded_at,
    "payload": _payload,
    "references.context": _context_items,
    "references.decisions": _decision_refs,
    "references.supersedes": _supersede_refs,
    "artifacts.items": _artifact_items,
    "content_digest": lambda r, d: r.integrity.content_digest,
    "record_digest": lambda r, d: r.integrity.record_digest,
}


def resolver_paths() -> frozenset[str]:
    """The paths that have a resolver. Used by the conformance test."""
    return frozenset(_RESOLVERS)


def _project(record: EvidenceRecord, *, digest: str) -> dict[str, Any]:
    """Walk the table and build the projection for one digest."""
    out: dict[str, Any] = {}
    for row in FIELD_TABLE:
        if row.path not in _RESOLVERS:
            continue
        decision = row.content if digest == "content" else row.record
        if decision is Inclusion.PER_KIND:
            include = (
                observed_at_is_semantic(record.identity.kind)
                if row.path == "observed_at"
                else False
            )
        else:
            include = decision is Inclusion.INCLUDED
        if include:
            out[row.path] = _RESOLVERS[row.path](record, digest)
    return out


def content_projection(record: EvidenceRecord) -> dict[str, Any]:
    """The semantic projection hashed into `content_digest` (§16).

    Invariant across promotion and relocation: it carries no `evidence_id`, no
    `recorded_at`, no `experiment_id`, no `producer_version` and no
    `artifact_ref`.
    """
    return _project(record, digest="content")


def record_projection(record: EvidenceRecord) -> dict[str, Any]:
    """The projection hashed into `record_digest` (§17).

    Covers every stored field except `record_digest` itself, so that repointing
    an `artifact_ref` at different bytes, or changing an operational timestamp,
    is **detectable** rather than invisible.
    """
    return _project(record, digest="record")
