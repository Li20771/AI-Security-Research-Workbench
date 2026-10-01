"""The stored form — §17's round-trip, verified rather than assumed.

```text
write   EvidenceRecord.to_stored_mapping()   pure shape; nothing to verify yet
read    load_stored(mapping)                 shape, then every rule, then digests
check   verify_stored_integrity(record)      recompute both digests and compare
```

### The two entry points are deliberately not one

```text
caller input parser   EvidenceRecord.from_mapping   §30 step 10 still applies
stored-form loader    load_stored                   reads what AI-05 wrote
```

They are separate functions with separate key sets, not one function with a
flag. A flag would put both boundaries behind one boolean, and a caller that
reached the wrong branch would be a configuration mistake rather than a type
error. §14.6.1's R1 is unchanged by anything here: `from_mapping` still refuses
a supplied `evidence_id`, `recorded_at`, `content_digest`, `record_digest` or
`value_digest`, and nothing in this module relaxes it.

Passing a stored mapping to the caller parser is refused, and it is refused by
the rule that names the problem: the stored form carries
`provenance.recorded_at`, which §15.2 marks as AI-05's to stamp.

### Why the loader re-runs every rule

The stored bytes are not trusted. `load_stored` reaches the same B1 validators
the caller path uses — shape, `schema_version`, required fields, the closed
vocabularies, the §14.9 grammars, the §6.5 registry, the §6.6 cross-field rules
— and adds the two conditions that live outside `from_mapping`: the §18.1
workspace agreement rule and §17's digest recomputation.

**None of those rules is restated here.** This module composes; it does not
re-implement. The only new validation in the package for this is
`ContextRef.from_stored_mapping`, which exists because the stored form has no
raw `value` to compute a digest from, not because a rule was relaxed.

### What a failure does

Nothing is repaired, nothing is rewritten, and no corrected record is returned.
A stored digest that does not match its content is a `StoredIntegrityFailure`,
and the caller gets an exception rather than a record that has been quietly
brought back into agreement with itself.

### No I/O

This module imports no serializer and no filesystem module. `to_stored_mapping`
returns a plain mapping of `str`/`int`/`bool`/`None`/`list`/`dict`; turning that
into bytes for `evidence/staged/` is the Store's job, and the Store does not
exist yet (B2 decision D2/D3).
"""

from __future__ import annotations

from plugins.evidence.admission import check_workspace_agreement
from plugins.evidence.digests import content_digest, record_digest
from plugins.evidence.errors import StoredIntegrityFailure, UnsupportedVocabulary

# `_closed_keys`, `_mapping` and `_required` are models.py's shared internals —
# the block it labels as such. Importing them is how the loader applies the
# same structural rules without a second copy of them.
from plugins.evidence.models import (
    PAYLOAD_BY_KIND,
    SUPPORTED_SCHEMA_VERSION,
    Artifacts,
    EvidenceRecord,
    Identity,
    Integrity,
    Provenance,
    References,
    _closed_keys,  # noqa: PLC2701 - shared internals, same package
    _mapping,
    _required,
    check_cross_field,
    observation_payload,
)
from plugins.evidence.vocabulary import EvidenceKind

__all__ = [
    "load_stored",
    "verify_stored_integrity",
]

#: §5's envelope, which is the stored form. There is no top-level `evidence_id`,
#: `content_digest` or `record_digest`: they live in `identity` and `integrity`,
#: where §5 puts them.
_STORED_TOP_KEYS = frozenset(
    {
        "schema_version",
        "identity",
        "payload",
        "provenance",
        "references",
        "artifacts",
        "integrity",
    }
)


def verify_stored_integrity(record: EvidenceRecord) -> None:
    """Recompute both digests and compare them with the stored ones (§16, §17).

    The stored values are the thing being checked, never the thing being
    trusted. `content_digest` is recomputed over the record's canonical
    semantic projection and checked first, because it is the narrower claim:
    if the semantic content moved, that is the more precise finding, and
    `record_digest` would fail for the same reason without saying so.

    Raises `StoredIntegrityFailure` on any disagreement. It never writes a
    digest back and never returns a repaired record — §22.3's rule that the
    failure belongs in the return value, applied to reading rather than writing.
    """
    stored_content = record.integrity.content_digest
    stored_record = record.integrity.record_digest

    if stored_content is None or stored_record is None:
        raise StoredIntegrityFailure(
            "the record carries no stored digests, so there is nothing to verify "
            "it against. Only a record AI-05 has written has both (§30 step 12); "
            "an unassigned record is not a stored record"
        )

    if content_digest(record) != stored_content:
        raise StoredIntegrityFailure(
            "content_digest does not match the record's canonical semantic "
            "projection (§16). The claim these bytes carry is not the claim the "
            "stored digest describes. Nothing is repaired and no digest is "
            "rewritten"
        )

    if record_digest(record) != stored_record:
        raise StoredIntegrityFailure(
            "record_digest does not match the stored record (§17). A stored field "
            "was altered after the record was written. Nothing is repaired and no "
            "digest is rewritten"
        )


def load_stored(mapping: object) -> EvidenceRecord:
    """Rebuild a written EvidenceRecord from its stored form (§5, §17).

    Runs, in order:

    ```text
    the §5 envelope and its closed key set
    schema_version
    identity, payload, provenance, references, artifacts, integrity
        — through B1's parsers, with the stored-form ContextRef and
          Provenance/provenance readers where the two forms differ
    check_cross_field            §6.6, from B1
    check_workspace_agreement    §18.1, from the admission boundary
    verify_stored_integrity      §17, this module
    ```

    Raises an `EvidenceError` subclass on any failure: `RecordMalformed` and its
    children for a malformed stored form, `StoredIntegrityFailure` for a stored
    record whose digests do not describe it. A caller that wants the §22.1
    outcome instead of the exception can map it, as `admission.admit` does for
    the caller path.
    """
    data = _mapping(mapping, "record")
    _closed_keys(data, _STORED_TOP_KEYS, "record")

    version = data.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedVocabulary(
            f"record.schema_version {version!r} is not supported; this "
            f"contract defines {SUPPORTED_SCHEMA_VERSION}"
        )

    identity = Identity.from_stored_mapping(
        _required(data, "identity", "record"), "identity"
    )

    payload_raw = _required(data, "payload", "record")
    if identity.kind is EvidenceKind.OBSERVATION:
        _family, payload = observation_payload(payload_raw, "payload")
    else:
        payload = PAYLOAD_BY_KIND[identity.kind].from_mapping(payload_raw, "payload")

    record = EvidenceRecord(
        identity=identity,
        provenance=Provenance.from_stored_mapping(
            _required(data, "provenance", "record"), "provenance"
        ),
        payload=payload,
        schema_version=version,
        references=References.from_stored_mapping(data.get("references"), "references"),
        # Artifacts carry no generated field, so the two forms are identical and
        # the caller parser is the stored parser.
        artifacts=Artifacts.from_mapping(data.get("artifacts"), "artifacts"),
        integrity=Integrity.from_stored_mapping(
            _required(data, "integrity", "record"), "integrity"
        ),
    )

    check_cross_field(record)
    check_workspace_agreement(record)
    verify_stored_integrity(record)
    return record
