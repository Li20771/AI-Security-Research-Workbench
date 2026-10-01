"""Canonicalization and the authoritative leaf table.

Implements contract §15 — and §15.2 in particular, which is **the single source
of truth for digest behaviour**. The table is data here, not prose: both
projections are built by walking it, so a field cannot acquire a second
classification somewhere else without a test noticing.

**Amendment 1 made the table leaf-based.** Before it, five rows described
*containers* (`payload`, `references.context[]`, `artifacts.items[]` and two
more) and everything inside them was classified by that single row. That could
not express a nested exclusion, so `artifact_ref`'s exclusion from
`content_digest` lived in an imperative `pop` inside this module — a rule the
table could be walked to and never discover. Every leaf is now a row, and this
module contains no hidden field removal at all.

The serialization primitive is imported from AI-04's `plugins.guard.digest`,
because §15 imports AI-04's §20.2 rules rather than restating them. What is
**not** imported is AI-04's projection: `request_projection` and
`evaluation_projection` answer AI-04's questions about AI-04's fields.

### What canonicalization is not allowed to do

It represents an already-valid record deterministically. It never strips, lowercases,
redacts, normalizes, repairs or drops. An uppercase SHA-256 is **rejected** upstream
rather than lowered here — canonicalization runs after validation and never instead
of it.

### Two orders, deliberately different (§15.4)

Set-semantic collections are sorted by their frozen identity tuple before hashing,
so a digest cannot depend on the order a caller happened to write a list in.
Order-semantic collections keep their meaning but are still sorted — by their
**explicit ordinal**, never by array position.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

# The serialization primitive only. AI-04's semantic projections are not reused.
from plugins.guard.digest import canonical_json, sha256_hex

from plugins.evidence.errors import RecordMalformed
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
    "resolver_paths",
    "sha256_hex",
]


class DigestRole(StrEnum):
    """What job a field does (§15.2)."""

    SEMANTIC = "semantic"
    OPERATIONAL = "operational"
    IDENTITY = "identity"
    LOCATOR = "locator"
    INTEGRITY = "integrity"
    NOT_CONTENT = "not_content"


class Inclusion(StrEnum):
    """Whether a leaf enters a given digest (§15.2)."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    PER_KIND = "per_kind"
    #: It *is* the digest, so it is not its own input.
    IS_THE_DIGEST = "is_the_digest"


@dataclass(frozen=True, slots=True)
class FieldRow:
    """One leaf of the §15.2 authoritative table."""

    path: str
    role: DigestRole
    content: Inclusion
    record: Inclusion


#: §15.2, transcribed leaf by leaf. 52 rows, two of them deferred and therefore
#: absent from every record — they are listed so that a reader can see the
#: contract's full shape rather than infer its absence.
FIELD_TABLE: tuple[FieldRow, ...] = (
    # ---- identity -------------------------------------------------------
    FieldRow("evidence_id", DigestRole.IDENTITY, Inclusion.EXCLUDED, Inclusion.INCLUDED),
    FieldRow("schema_version", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("kind", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    # ---- provenance -----------------------------------------------------
    FieldRow("producer", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("producer_version", DigestRole.OPERATIONAL, Inclusion.EXCLUDED, Inclusion.INCLUDED),
    FieldRow("producer_type", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("actor.id", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("actor.type", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("workspace_id", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("experiment_id", DigestRole.OPERATIONAL, Inclusion.EXCLUDED, Inclusion.INCLUDED),
    FieldRow("observed_at", DigestRole.SEMANTIC, Inclusion.PER_KIND, Inclusion.INCLUDED),
    FieldRow("recorded_at", DigestRole.OPERATIONAL, Inclusion.EXCLUDED, Inclusion.INCLUDED),
    # ---- payload: OBSERVATION -------------------------------------------
    FieldRow("payload.family", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.subject", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.binding.source_kind", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.binding.source_identity", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.binding.source_revision", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.binding.model_ref", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.binding.endpoint_host", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.binding.capability", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.read_status", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.run_status", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.outcome", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.candidate_status", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.observed", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    # ---- payload: DECISION ----------------------------------------------
    FieldRow("payload.decision", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.reason_code", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.reasons[]", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.input_digest", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    # ---- payload: EXECUTION ---------------------------------------------
    FieldRow("payload.tool_calls[].ordinal", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.tool_calls[].what_ran", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.tool_calls[].status", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("payload.tool_calls[].result_classification", DigestRole.SEMANTIC,
             Inclusion.EXCLUDED, Inclusion.EXCLUDED),
    # ---- references -----------------------------------------------------
    FieldRow("references.context[].workspace_id", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].source_kind", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].source_identity", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].source_revision", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].subject", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].value_digest", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].item_kind", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].truth_state", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.context[].freshness", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.decisions[].record_ref", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.supersedes[].record_ref", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("references.supersedes[].correction_reason", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    # ---- artifacts ------------------------------------------------------
    FieldRow("artifacts.items[].artifact_digest", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("artifacts.items[].role", DigestRole.SEMANTIC, Inclusion.EXCLUDED, Inclusion.EXCLUDED),
    FieldRow("artifacts.items[].external", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("artifacts.items[].owner_workspace_id", DigestRole.SEMANTIC, Inclusion.INCLUDED, Inclusion.INCLUDED),
    FieldRow("artifacts.items[].artifact_ref", DigestRole.LOCATOR, Inclusion.EXCLUDED, Inclusion.INCLUDED),
    # ---- integrity ------------------------------------------------------
    FieldRow("content_digest", DigestRole.INTEGRITY, Inclusion.IS_THE_DIGEST, Inclusion.INCLUDED),
    FieldRow("record_digest", DigestRole.INTEGRITY, Inclusion.EXCLUDED, Inclusion.IS_THE_DIGEST),
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


# --------------------------------------------------------------------------
# Top-level scalar leaves
# --------------------------------------------------------------------------


def _scalar(record: EvidenceRecord, leaf: str) -> Any:
    """One top-level scalar leaf, by its contract name."""
    if leaf == "evidence_id":
        return record.identity.evidence_id
    if leaf == "schema_version":
        return record.schema_version
    if leaf == "kind":
        return str(record.identity.kind)
    if leaf == "producer":
        return record.provenance.producer
    if leaf == "producer_version":
        return record.provenance.producer_version
    if leaf == "producer_type":
        return str(record.provenance.producer_type)
    if leaf == "actor.id":
        return record.provenance.actor.id
    if leaf == "actor.type":
        return str(record.provenance.actor.type)
    if leaf == "workspace_id":
        return record.provenance.workspace_id
    if leaf == "experiment_id":
        return record.provenance.experiment_id
    if leaf == "observed_at":
        return record.provenance.observed_at
    if leaf == "recorded_at":
        return record.provenance.recorded_at
    if leaf == "content_digest":
        return record.integrity.content_digest
    if leaf == "record_digest":
        return record.integrity.record_digest
    raise RecordMalformed(f"no resolver for the frozen leaf {leaf!r}")


def _scalar_paths() -> tuple[str, ...]:
    """The top-level leaves: table paths with no container prefix."""
    return tuple(
        row.path for row in FIELD_TABLE if _owner(row.path) is None
    )


# --------------------------------------------------------------------------
# Collections
# --------------------------------------------------------------------------


def _collection_items(record: EvidenceRecord, container: str) -> list[Any]:
    """The ordered items of one set-semantic collection (§15.4).

    Ordered by `canonical_key`, which each type defines as its frozen identity
    tuple. Never by array position and never by a locator.
    """
    if container == "references.context[]":
        return sorted(record.references.context, key=lambda i: i.canonical_key)
    if container == "references.decisions[]":
        return sorted(record.references.decisions, key=lambda i: i.canonical_key)
    if container == "references.supersedes[]":
        return sorted(record.references.supersedes, key=lambda i: i.canonical_key)
    if container == "artifacts.items[]":
        return sorted(record.artifacts.items, key=lambda i: i.canonical_key)
    raise RecordMalformed(f"unknown collection {container!r}")


#: The five containers. `payload` holds one item; the other four are collections.
_COLLECTIONS: tuple[str, ...] = (
    "payload",
    "references.context[]",
    "references.decisions[]",
    "references.supersedes[]",
    "artifacts.items[]",
)


def _owner(path: str) -> str | None:
    """The container a leaf belongs to, or None for a top-level leaf.

    `payload.tool_calls[].ordinal` belongs to `payload` — the tool-call
    collection is nested inside the payload rather than being a sixth container,
    because the contract declares it as `payload.tool_calls[]`.
    """
    for container in _COLLECTIONS:
        if path.startswith(container + "."):
            return container
    return None


def _leaf_within(path: str, container: str) -> str:
    """The leaf's name inside its container, e.g. `tool_calls[].ordinal`."""
    return path[len(container) + 1:]


def _include(row: FieldRow, digest: str, record: EvidenceRecord) -> bool:
    decision = row.content if digest == "content" else row.record
    if decision is Inclusion.PER_KIND:
        return observed_at_is_semantic(record.identity.kind)
    return decision is Inclusion.INCLUDED


# --------------------------------------------------------------------------
# Projections
# --------------------------------------------------------------------------


def _project(record: EvidenceRecord, *, digest: str) -> dict[str, Any]:
    """Walk the table and build the projection for one digest."""
    out: dict[str, Any] = {}

    for leaf in _scalar_paths():
        row = _TABLE_BY_PATH[leaf]
        if _include(row, digest, record):
            out[leaf] = _scalar(record, leaf)

    for container in _COLLECTIONS:
        entries: list[dict[str, Any]] = []
        if container == "payload":
            items = [record.payload]
        else:
            items = _collection_items(record, container)

        rows = {
            _leaf_within(row.path, container): row
            for row in FIELD_TABLE
            if _owner(row.path) == container
        }

        for item in items:
            projected = item.to_projection()
            entry: dict[str, Any] = {}
            for leaf, value in projected.items():
                if leaf == "tool_calls[]":
                    # A nested ORDER-semantic collection inside the payload.
                    inner = []
                    for call in value:
                        inner.append({
                            k: v
                            for k, v in call.items()
                            if _include(
                                rows[f"tool_calls[].{k}"], digest, record
                            )
                        })
                    entry["tool_calls[]"] = inner
                    continue
                row = rows.get(leaf)
                if row is None:
                    # A model field the table does not classify is a defect in
                    # this module, not a value to skip silently.
                    raise RecordMalformed(
                        f"{container}.{leaf} has no row in the §15.2 table"
                    )
                if _include(row, digest, record):
                    entry[leaf] = value
            entries.append(entry)

        if container == "payload":
            out["payload"] = entries[0]
        else:
            out[container] = entries

    return out


def resolver_paths() -> frozenset[str]:
    """Every table path this module can resolve. Used by the conformance test."""
    return frozenset(row.path for row in FIELD_TABLE)


def content_projection(record: EvidenceRecord) -> dict[str, Any]:
    """The semantic projection hashed into `content_digest` (§16).

    Invariant across promotion and relocation: it carries no `evidence_id`, no
    `recorded_at`, no `experiment_id`, no `producer_version`, no `artifact_ref`,
    and neither deferred field.
    """
    return _project(record, digest="content")


def record_projection(record: EvidenceRecord) -> dict[str, Any]:
    """The projection hashed into `record_digest` (§17).

    Covers every stored leaf except `record_digest` itself, so that repointing an
    `artifact_ref` at different bytes, or changing an operational timestamp, is
    **detectable** rather than invisible.
    """
    return _project(record, digest="record")
