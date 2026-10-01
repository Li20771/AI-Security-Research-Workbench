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

This package carries **AI-05-B1, the logical core**, plus the first AI-05-B2
increment, the §18.1 workspace agreement boundary. It is offline, pure, and has
no storage:

```text
IMPLEMENTED HERE
    the record model and its three typed payloads
    the §6.5 admitted-producer registry and the §6.6 cross-field rules
    the thirteen frozen grammars (§14.9)
    the leaf-accurate field table and the two digests
    the §18.1 workspace agreement rule and the §22.1 outcome mapping
    the §17 stored form: to_stored_mapping, load_stored and its verification

NOT IMPLEMENTED
    the published admission rule set (C-1), which §30 step 7 needs
    §30 step 14 uniqueness                 ContextRef derivation from AI-03
    lifecycle and the Store protocol       any storage backend
    any byte encoding — the Store does that, and there is no Store yet
```

Usage:

```python
from plugins.evidence import EvidenceRecord, assign_digests

record = EvidenceRecord.from_mapping(supplied)   # strict; refuses unknown fields
record = assign_digests(record)                  # fills content_digest/record_digest
record.integrity.content_digest
```

**Vocabulary membership and admission are two checks.** `agent` is a valid
`ProducerType` member and is still REJECTED for every v1 admitted event, because
all six §6.5 registry rows register `service`.

**Boundaries this package must keep.** It imports no network client, spawns no
subprocess, executes no tool, routes nothing, authorizes nothing, promotes no
capability, performs no file I/O, and ingests no artifact bytes. Frozen types
from AI-02, AI-03 and AI-04 are **imported, not restated** (§3).

Contract: `docs/AI-05_EVIDENCE_EXECUTION_PLAN.md`.
B2 staging decisions: `docs/AI-05-B2_DECISIONS_2026-10-01.md`.
"""

from __future__ import annotations

from plugins.evidence.admission import (
    AdmissionResult,
    admit,
    check_workspace_agreement,
)
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
    ActorTypeNotAdmitted,
    BindingArmMismatch,
    CallerSuppliedDigest,
    CallerSuppliedGeneratedField,
    CallerSuppliedIdentity,
    CrossFieldViolation,
    DuplicateElement,
    DuplicateOrdinal,
    EvidenceError,
    FamilyStatusMismatch,
    FieldClassViolation,
    InvalidDigestShape,
    InvalidIdentifier,
    MissingRequiredField,
    NonCanonicalDigestCase,
    PayloadKindMismatch,
    ProducerNotRegistered,
    ProducerRoleViolation,
    ProducerTypeNotAdmitted,
    RawContentRejected,
    RecordMalformed,
    StoredIntegrityFailure,
    UnknownField,
    UnsupportedVocabulary,
    WorkspaceAgreementViolation,
)
from plugins.evidence.grammar import (
    GRAMMAR_NAMES,
    g_digest,
    g_evidence_id,
    g_host,
    g_ident,
    g_locator,
    g_modelref,
    g_opaque_id,
    g_ordinal,
    g_registered,
    g_revision,
    g_subject,
    g_text,
    g_timestamp,
    revision_length_for,
)
from plugins.evidence.models import (
    ADMITTED_EVENTS,
    EVIDENCE_ID_PREFIX,
    MAX_TEXT_LENGTH,
    OBSERVATION_BY_FAMILY,
    PAYLOAD_BY_KIND,
    SUPPORTED_SCHEMA_VERSION,
    Actor,
    AdmittedEvent,
    ArtifactRef,
    Artifacts,
    CapabilityObservation,
    ContextRef,
    DecisionPayload,
    EvidenceRecord,
    ExecutionPayload,
    Identity,
    Integrity,
    ProviderBinding,
    ProviderProbeObservation,
    Provenance,
    RecordRef,
    References,
    SourceReadObservation,
    SupersedeRef,
    ToolCall,
    WorkspaceBinding,
    admitted_events_for,
    check_cross_field,
    new_evidence_id,
    observation_payload,
    value_digest_of,
)
from plugins.evidence.stored import (
    load_stored,
    verify_stored_integrity,
)
from plugins.evidence.vocabulary import (
    AI05_GENERATED_DIGEST_FIELDS,
    CALLER_SUPPLIED_DIGEST_FIELDS,
    PERMITTED_ACTOR_TYPES,
    ActorType,
    AdmissionOutcome,
    DigestOrigin,
    EvidenceKind,
    FieldClass,
    Freshness,
    GuardDecision,
    ItemKind,
    ObservationFamily,
    ProducerType,
    StatusValue,
    actor_type_is_permitted,
    producer_type_is_permitted,
)

__all__ = [
    "ADMITTED_EVENTS",
    "AI05_GENERATED_DIGEST_FIELDS",
    "CALLER_SUPPLIED_DIGEST_FIELDS",
    "CONTENT_EXCLUDED_PATHS",
    "EVIDENCE_ID_PREFIX",
    "FIELD_TABLE",
    "GRAMMAR_NAMES",
    "MAX_TEXT_LENGTH",
    "OBSERVATION_BY_FAMILY",
    "PAYLOAD_BY_KIND",
    "PERMITTED_ACTOR_TYPES",
    "SUPPORTED_SCHEMA_VERSION",
    "Actor",
    "ActorType",
    "ActorTypeNotAdmitted",
    "AdmissionOutcome",
    "AdmissionResult",
    "AdmittedEvent",
    "ArtifactRef",
    "Artifacts",
    "BindingArmMismatch",
    "CallerSuppliedDigest",
    "CallerSuppliedGeneratedField",
    "CallerSuppliedIdentity",
    "CapabilityObservation",
    "ContextRef",
    "CrossFieldViolation",
    "DecisionPayload",
    "DigestOrigin",
    "DigestRole",
    "DuplicateElement",
    "DuplicateOrdinal",
    "EvidenceError",
    "EvidenceKind",
    "EvidenceRecord",
    "ExecutionPayload",
    "FamilyStatusMismatch",
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
    "ObservationFamily",
    "PayloadKindMismatch",
    "ProducerNotRegistered",
    "ProducerRoleViolation",
    "ProducerType",
    "ProducerTypeNotAdmitted",
    "Provenance",
    "ProviderBinding",
    "ProviderProbeObservation",
    "RawContentRejected",
    "RecordMalformed",
    "RecordRef",
    "References",
    "SourceReadObservation",
    "StatusValue",
    "StoredIntegrityFailure",
    "SupersedeRef",
    "ToolCall",
    "UnknownField",
    "UnsupportedVocabulary",
    "WorkspaceAgreementViolation",
    "WorkspaceBinding",
    "actor_type_is_permitted",
    "admit",
    "admitted_events_for",
    "assign_digests",
    "canonical_json",
    "check_cross_field",
    "check_workspace_agreement",
    "content_digest",
    "content_projection",
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
    "load_stored",
    "new_evidence_id",
    "observation_payload",
    "observed_at_is_semantic",
    "producer_type_is_permitted",
    "record_digest",
    "record_projection",
    "resolver_paths",
    "revision_length_for",
    "sha256_hex",
    "value_digest_of",
    "verify_stored_integrity",
]
