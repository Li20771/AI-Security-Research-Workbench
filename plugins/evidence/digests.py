"""The two digests, and the third that is not one of them.

Implements contract §16 and §17.

    content_digest   semantic equivalence   "do these two records make the same claim?"
    record_digest    stored-record integrity "has this stored record been altered?"

They are **not** interchangeable, and this module exists because a single digest
cannot do both jobs — the two have opposite requirements. Content equivalence
must ignore location, or promotion would change a claim that did not change.
Integrity must cover everything stored, or repointing an `artifact_ref` at
different bytes would be invisible.

`value_digest` is a third thing with a third job: it discriminates one context
item from another (§12.2). It is not an equivalence digest and not an integrity
digest, and it is re-exported here only so callers have one import for AI-05's
digest surface.

### What AI-05 will not do

It does not accept a caller-supplied value for any of the three generated fields
(§14.6.1, R1). No component can tell a digest of a secret from any other digest,
so the protection is not a detector — it is that there is no field in which a
caller can substitute one.
"""

from __future__ import annotations

from plugins.guard.digest import canonical_json, sha256_hex

from plugins.evidence.canonical import content_projection, record_projection
from plugins.evidence.models import EvidenceRecord, Integrity, value_digest_of
from plugins.evidence.vocabulary import AI05_GENERATED_DIGEST_FIELDS

__all__ = [
    "AI05_GENERATED_DIGEST_FIELDS",
    "assign_digests",
    "canonical_json",
    "content_digest",
    "record_digest",
    "sha256_hex",
    "value_digest_of",
]


def content_digest(record: EvidenceRecord) -> str:
    """SHA-256 over the semantic projection (§16).

    Invariant across promotion and relocation. Operational fields —
    `recorded_at`, `experiment_id`, `producer_version`, `artifact_ref` — are
    absent from the projection, so changing one leaves this value untouched.
    """
    return sha256_hex(canonical_json(content_projection(record)))


def record_digest(record: EvidenceRecord) -> str:
    """SHA-256 over the stored-record projection (§17).

    Covers every stored field except `record_digest` itself. A digest MUST NOT be
    its own input.
    """
    return sha256_hex(canonical_json(record_projection(record)))


def assign_digests(record: EvidenceRecord) -> EvidenceRecord:
    """Return a copy of `record` carrying its computed digests.

    Never mutates in place: §19 makes an admitted record immutable, and a
    function that filled digests by assignment would be the first mutation in a
    pipeline that has none.

    `record_digest` is computed over the record **without** its integrity block
    and then written in, so the value does not depend on itself. `content_digest`
    is computed first and is part of the record digest, so a record's integrity
    covers which claim it carries.
    """
    record.assert_kind_matches_payload()
    content = content_digest(record)
    with_content = record.with_integrity(
        Integrity(content_digest=content, record_digest=None)
    )
    return with_content.with_integrity(
        Integrity(content_digest=content, record_digest=record_digest(with_content))
    )
