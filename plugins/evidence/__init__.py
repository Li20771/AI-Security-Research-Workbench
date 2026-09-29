"""AI-05 — Evidence / Audit Plugin.

AI-05 is the Workbench's durable record layer. It records what happened; it does
not decide what it means.

```text
Guard decides.  AI-05 records.

Evidence records what happened.
Evidence does not adjudicate truth.
Evidence does not grant authorization.
Evidence does not promote capability state.
```

This package is **AI-05-B1, the logical core**. It is offline, pure, and has no
storage:

```text
IMPLEMENTED HERE (B1)
    the record model and its typed payloads
    the authoritative digest field table (§15.2)
    canonicalization and collection ordering
    content_digest, record_digest, value_digest

NOT IMPLEMENTED (later phases)
    admission pipeline (B2)            ContextRef derivation from AI-03 (B2)
    artifact rule enforcement (B2)     the published admission rule set (C-1)
    lifecycle and the Store protocol (B3)
    any storage backend (B4)           any file I/O, at all
```

Usage:

```python
from plugins.evidence import EvidenceRecord, assign_digests

record = EvidenceRecord.from_mapping(supplied)   # strict; refuses unknown fields
record = assign_digests(record)                  # fills content_digest/record_digest
record.integrity.content_digest
```

**Boundaries this package must keep.** It imports no network client, spawns no
subprocess, executes no tool, routes nothing, authorizes nothing, promotes no
capability, performs no file I/O, and ingests no artifact bytes. Frozen types
from AI-02, AI-03 and AI-04 are **imported, not restated** (§3): a second
definition in one repository means two places to update and one of them
forgotten.

Contract: `docs/AI-05_EVIDENCE_EXECUTION_PLAN.md`.
"""

from __future__ import annotations

from plugins.evidence.canonical import (
    CONTENT_EXCLUDED_PATHS,
    FIELD_TABLE,
    DigestRole,
    FieldRow,
    Inclusion,
    canonical_json,
    content_projection,
    observed_at_is_semantic,
    record_projection,
    resolver_paths,
    sha256_hex,
)
from plugins.evidence.digests import (
    assign_digests,
    content_digest,
    record_digest,
)
from plugins.evidence.errors import (
    CallerSuppliedDigest,
    CallerSuppliedGeneratedField,
    CallerSuppliedIdentity,
    EvidenceError,
    FieldClassViolation,
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
from plugins.evidence.models import (
    EVIDENCE_ID_PREFIX,
    IDENTIFIER_RE,
    PAYLOAD_BY_KIND,
    SUPPORTED_SCHEMA_VERSION,
    Actor,
    ArtifactRef,
    Artifacts,
    ContextRef,
    DecisionPayload,
    EvidenceRecord,
    ExecutionPayload,
    Identity,
    Integrity,
    ObservationPayload,
    Provenance,
    RecordRef,
    References,
    SupersedeRef,
    ToolCall,
    new_evidence_id,
    value_digest_of,
)
from plugins.evidence.vocabulary import (
    AI05_GENERATED_DIGEST_FIELDS,
    CALLER_SUPPLIED_DIGEST_FIELDS,
    PERMITTED_ACTOR_TYPES,
    PERMITTED_PRODUCER_TYPES,
    ActorType,
    AdmissionOutcome,
    DigestOrigin,
    EvidenceKind,
    FieldClass,
    Freshness,
    GuardDecision,
    ItemKind,
    StatusValue,
    actor_type_is_permitted,
    producer_type_is_permitted,
)

__all__ = [
    "AI05_GENERATED_DIGEST_FIELDS",
    "CALLER_SUPPLIED_DIGEST_FIELDS",
    "CONTENT_EXCLUDED_PATHS",
    "EVIDENCE_ID_PREFIX",
    "FIELD_TABLE",
    "IDENTIFIER_RE",
    "PAYLOAD_BY_KIND",
    "PERMITTED_ACTOR_TYPES",
    "PERMITTED_PRODUCER_TYPES",
    "SUPPORTED_SCHEMA_VERSION",
    "Actor",
    "ActorType",
    "AdmissionOutcome",
    "ArtifactRef",
    "Artifacts",
    "CallerSuppliedDigest",
    "CallerSuppliedGeneratedField",
    "CallerSuppliedIdentity",
    "ContextRef",
    "DecisionPayload",
    "DigestOrigin",
    "DigestRole",
    "EvidenceError",
    "EvidenceKind",
    "EvidenceRecord",
    "ExecutionPayload",
    "FieldClass",
    "FieldClassViolation",
    "FieldRow",
    "Freshness",
    "GuardDecision",
    "Identity",
    "Inclusion",
    "Integrity",
    "InvalidDigestShape",
    "InvalidIdentifier",
    "ItemKind",
    "MissingRequiredField",
    "NonCanonicalDigestCase",
    "ObservationPayload",
    "PayloadKindMismatch",
    "ProducerRoleViolation",
    "Provenance",
    "RawContentRejected",
    "RecordMalformed",
    "RecordRef",
    "References",
    "StatusValue",
    "SupersedeRef",
    "ToolCall",
    "UnknownField",
    "UnsupportedVocabulary",
    "actor_type_is_permitted",
    "assign_digests",
    "canonical_json",
    "content_digest",
    "content_projection",
    "new_evidence_id",
    "observed_at_is_semantic",
    "producer_type_is_permitted",
    "record_digest",
    "record_projection",
    "resolver_paths",
    "sha256_hex",
    "value_digest_of",
]
