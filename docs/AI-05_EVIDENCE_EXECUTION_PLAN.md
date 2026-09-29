# AI-05 — Evidence / Audit Plugin

> **Status: FROZEN — AI-05-A.** This document is the contract. AI-05-B implements
> against it. Nothing here is a claim that AI-05 has been implemented.
>
> **Frozen** = the shape and the rules below are binding for AI-05-B.
> **Deferred** = the value or the mechanism is declared but NOT decided by AI-05-A.
>
> A frozen contract is a constraint on implementation. It is **not** a claim that
> any Evidence record exists, that any record has been admitted, or that any
> component has been authorized by one.
>
> > Frozen contracts and verified facts are different things. This document freezes
> > the former and deliberately does not assert the latter.

---

## 1. Purpose

AI-05 makes an Agent task reviewable after the chat window is gone.

```text
AI-04 decides.  AI-05 records.
```

The plugin provides one durable capability: a **normalized, immutable,
workspace-scoped record** of what an identified actor did or observed, written by
an identified producer, carrying provenance, semantic content, references,
artifacts, and integrity digests — so that a later reader can reconstruct what
happened without trusting a transcript.

**AI-05 is authoritative for nothing.** It records. It does not decide, authorize,
promote, execute, aggregate or adjudicate.

> **Evidence records what happened.**
> **Evidence does not make something true.**

### 1.1 What this sub-phase delivers

The frozen contract only. AI-05-A delivers:

```text
docs/AI-05_EVIDENCE_EXECUTION_PLAN.md   this document
```

**What this sub-phase explicitly does not deliver:** any implementation, any
`plugins/evidence/` production code, any schema file, any storage backend, any test.

### 1.2 Authority boundaries, stated once

```text
Guard decides.        It does not record.
AI-05 records.        It does not decide.

Router selects.       It never grants permissions.   (F-13)
Guard decides whether a selected action may proceed. It never selects.
```

Guard consumes AI-03 Context and AI-02 capability state as **inputs**. AI-05
records what was consumed. Neither collects the other's data, and neither
authorizes on the other's behalf.

---

## 2. Scope

### 2.1 In scope for AI-05

```text
the EvidenceRecord envelope
the three evidence kinds and their payload contracts
producer / actor identity
the identity model: evidence_id, experiment_id, digests
the provenance contract
time semantics, per field and per kind
the ContextRef durable reference
the artifact reference and its boundary
the secret admission boundary
canonicalization and the two digests
workspace isolation
lifecycle: write-once, append-only, supersession
durability tiers: staged and promoted
admission outcomes and failure semantics
the test matrix and the exit gates
```

### 2.2 Explicitly out of AI-05 scope

```text
AI-02 capability promotion            not implemented, not owned (note the boundary in §23)
AI-03 context collection              not implemented
AI-04 authorization                   not implemented
AI-06 tool execution                  not implemented
AI-07 model routing                   DEFERRED; not implemented, not stubbed
AI-11 benchmark / ranking / scoring   not implemented
raw log archive                       not owned; artifacts are referenced, never ingested
secret scanning engine                not implemented (§14)
storage backend selection             NOT decided by this document (§20.4)
SecurityLab integration               not implemented
```

### 2.3 Non-goals

AI-05 is **not**:

```text
a secret scanner
a tool executor
a Guard
an authorization engine
an AI-02 capability promotion engine
a context store
a router
a benchmark ranking engine
a raw-log archive
```

A component that recorded evidence *and* decided what it meant would be a
different component wearing this one's name.

---

## 3. Normative Language

```text
MUST        a binding requirement. A violation is a contract violation.
MUST NOT    a binding prohibition. A violation is a contract violation.
FROZEN      the rule is binding for AI-05-B and changes only by amendment (§34).
DEFERRED    declared, deliberately not decided here.
FORBIDDEN   a state that a test MUST fail on.
```

Three vocabularies are inherited unchanged and MUST NOT be merged or restated:

```text
item_kind      FACT | HISTORY | PLAN                               (AI-03)
truth_state    PASS | FAIL | BLOCKED | NOT_RUN | UNKNOWN            (AI-03, from AI-00 §10)
GuardDecision  ALLOW | DENY | BLOCKED | UNKNOWN                     (AI-04)
CheckResult    SATISFIED | REJECTED | UNAVAILABLE | INDETERMINATE   (AI-04)
```

**Nothing frozen elsewhere is restated.** AI-03's `ItemKind`, `StatusValue`,
`Freshness`, `WorkingTreeState` and `ContextItem`, and AI-04's `DecisionRecord`
and `GuardDecision`, are **imported** wherever they are used. Redefining one is a
defect, not a convenience: two definitions in one repository means two places to
update and one of them gets forgotten.

---

## 4. Evidence Definition

FROZEN:

> **Evidence is a normalized, immutable, workspace-scoped record of an identified
> act or observation made by a named actor, written by a named producer, with
> provenance, semantic content, references, artifacts, and integrity digests.**

```text
Evidence records what happened or what was decided.
Evidence does not adjudicate truth.
Evidence does not grant authorization.
Evidence does not promote capability state.
```

FORBIDDEN phrasings, in this document and in any consumer:

```text
"Evidence exists, therefore it is true"
"Evidence exists, therefore it is verified"
"Evidence exists, therefore the action is authorized"
```

### 4.1 The producing acts

An Evidence record is produced by exactly one of three acts:

```text
OBSERVATION   something was observed
DECISION      something was decided
EXECUTION     something was run
```

"Observed or decided" is insufficient on its own: an execution is a third act and
is not reducible to either. A test run is not an observation *of* a test; it is a
run whose result is then observed.

---

## 5. EvidenceRecord Envelope

FROZEN. An EvidenceRecord is a **common envelope plus a typed payload** — not a
generic observation schema.

```text
EvidenceRecord
├── identity      evidence_id, kind, schema_version
├── provenance    producer, actor, workspace, experiment, times
├── payload       kind-specific, closed, declared
├── references    ContextRef[], decisions, supersedes
├── artifacts     artifact references
└── integrity     content_digest, record_digest
```

```yaml
EvidenceRecord:
  schema_version: 1

  identity:
    evidence_id:     string        # generated, opaque, "ev-<hex>"; in record_digest only
    kind:            OBSERVATION | DECISION | EXECUTION
    # no free-form identity map

  provenance:
    producer:        string        # the component that WROTE this record
    producer_version: string
    producer_type:   human | agent | service | unknown
    actor:                         # the entity whose act is described
      id:            string
      type:          human | agent | service | unknown
    workspace_id:    string        # REQUIRED, non-empty; the scope of the whole record
    experiment_id:   string | null # CORRELATION only; never identity
    observed_at:     string | null # SEMANTIC where the kind's claim is time-bound (§10)
    recorded_at:     string        # OPERATIONAL; excluded from content_digest

  payload:                         # kind-specific; see §11

  references:
    context:         ContextRef[]  # SET-semantic (§12, §15.4)
    decisions:       RecordRef[]   # SET-semantic
    supersedes:      SupersedeRef[]# SET-semantic (§21)

  artifacts:
    items:           ArtifactRef[] # SET-semantic (§13)

  integrity:
    content_digest:  string        # §16
    record_digest:   string        # §17
```

### 5.1 Why an envelope plus a typed payload

Three reasons, each grounded in this repository:

```text
1. Identity, provenance, integrity and canonicalization rules are IDENTICAL across
   kinds. Implementing them once prevents the divergence noted in AI-04 §28.2.
2. A generic schema expresses per-kind requirements as optionality, and optionality
   cannot be enforced. evidence/schema/experiment.schema.yaml is the repository's own
   experiment with a generic monolith: it is loaded by nothing and validated by
   nothing, and its only reference is a presence assertion in a shell test.
3. A typed payload is what lets this contract say "required for this kind" — the
   only form of requirement a validator can enforce. AI-04 §4.2's strictness is
   possible only because the request shape is fixed.
```

### 5.2 What must not appear

No raw context payload, secret, prompt, credential, tool output, provider response
body, diff, or repository file content belongs in a record. Context appears only as
references; artifacts appear only as references and digests.

---

## 6. Evidence Kinds

FROZEN. Exactly three. **A fourth kind is a contract amendment, not a configuration
change** (AI-03 §5.2 precedent).

```text
OBSERVATION   something was observed
DECISION      something was decided
EXECUTION     something was run
```

### 6.1 The rule that assigns a kind

FROZEN:

> **kind describes the ACT THE RECORD IS ABOUT** — not how the Workbench happened
> to observe it.

Tie-breaker, for an act the table below does not cover:

> kind describes the act that **changed or asserted something about the world**,
> not the transport that carried the news of it.

### 6.2 The assignment table

| Event | kind | producer (writes) | actor (described) |
| --- | --- | --- | --- |
| AI-02 provider probe | `OBSERVATION` | AI-02 | service |
| AI-02 capability observation | `OBSERVATION` | AI-02 | service |
| AI-03 context read | `OBSERVATION` | AI-03 | service |
| AI-04 Guard decision | `DECISION` | AI-04 | service |
| AI-06 tool execution | `EXECUTION` | AI-06 | agent |
| AI-06 test result | `EXECUTION` | AI-06 | service |
| AI-07 routing decision | `DECISION` | AI-07 | service |
| **human approval** | **`DECISION`** | the Workbench component recording it | **human** |

### 6.3 Why a human approval is a DECISION

A recorded human approval is about **the human's decision**. The approval artifact
— a signed record, a ticket, a message — is evidence *of* that decision and is
carried as an artifact reference, not as the record's kind.

```text
recorded act = the human decided        -> kind = DECISION, actor.type = human
```

A record whose entire claim is "an artifact exists at location L" is a strictly
weaker `OBSERVATION` of an artifact, with `actor.type = service`. Both records may
exist. They are different records and the kind field distinguishes them.

### 6.4 Kinds that must not be added

```text
CAPABILITY_OBSERVATION   the payload differs, not the act
TEST                     a test run is an EXECUTION
CONTEXT_READ             an OBSERVATION with a context payload
ROUTING                  a DECISION; and AI-07 is DEFERRED
APPROVAL                 a DECISION whose actor is human
```

---

## 7. Producer / Actor Model

FROZEN. Two distinct fields, both mandatory, never conflated.

```text
producer    the component that WROTE the EvidenceRecord.
            Always a Workbench component. Never a human.

actor       the entity whose act the record is ABOUT.
            human | agent | service | unknown
```

```text
A human approves.
  actor    = the human            (the act described)
  producer = the Workbench component that recorded it   (the act of writing)

Guard decides.
  actor    = service
  producer = AI-04

A probe observes.
  actor    = service
  producer = AI-02
```

`producer_type` and `actor.type` use the closed vocabulary
`human | agent | service | unknown`, inherited from AI-04's `ActorType` — imported,
not restated.

**A record with no producer is not a record.** Provenance is never fabricated: a
record claiming an observation that no producer made would be a false record.

---

## 8. Identity Model

FROZEN. Six fields, six **different** jobs. Conflating any two is a defect.

```text
role                 field             property
identity             evidence_id       unique per record; opaque; non-semantic
correlation          experiment_id     groups records; NOT unique; caller-supplied
semantic equivalence content_digest    equal <=> same normalized claim
record integrity     record_digest     detects alteration of the stored record
artifact integrity   artifact_digest   detects alteration of the artifact bytes
artifact location    artifact_ref      opaque locator
```

### 8.1 evidence_id

```text
generated, opaque, "ev-<hex>"
NEVER content-derived
NEVER in content_digest
in record_digest
```

Consequences, stated explicitly because they are counter-intuitive:

```text
same content          MAY have different evidence_id
same content_digest   does NOT imply same evidence_id
```

Two live probes that both returned the same result are **two runs**, not one
record. A store that cannot tell them apart cannot report how many times something
was observed. (AI-02's `run_id` docstring makes the same argument: keying on
provider alone means the second run's evidence silently overwrites the first.)

Deduplication is `content_digest`'s job, not `evidence_id`'s.

### 8.2 Duplicate handling

```text
duplicate evidence_id       REJECTED
duplicate content_digest    ACCEPTED
```

Duplicate content is two events. It MUST NOT be collapsed, and it MUST NOT be
recorded by writing a `duplicate_of` field onto either record — that would be a
mutation (§19, §21).

### 8.3 Identity is not semantic identity

```text
unique identifier    evidence_id       tells you WHICH record
semantic identity    content_digest    tells you WHETHER two records say the same thing
```

AI-03's `workspace_id` is deterministic (`ws-` + sha256 of root and repository)
because a workspace is a stable thing. **An Evidence record is an event.** Copying
the deterministic pattern from the wrong precedent would make two identical
observations indistinguishable.

---

## 9. Provenance

FROZEN. Provenance answers "who, where, when" for every record.

```text
producer          which component wrote the record
producer_version  its version
producer_type     human | agent | service | unknown
actor             the entity whose act is described
workspace_id      the scope of the whole record          REQUIRED, non-empty
experiment_id     correlation label                      optional
observed_at       when the claimed act happened          per kind (§10)
recorded_at       when the record was written            operational
```

### 9.1 Mandatory fields

```text
producer          REQUIRED
producer_type     REQUIRED
actor             REQUIRED
actor.type        REQUIRED
workspace_id      REQUIRED and non-empty
recorded_at       REQUIRED
observed_at       REQUIRED where the kind's claim is time-bound (§10.2)
```

A record missing any required provenance field is `REJECTED` (§22, §30).

### 9.2 Forbidden provenance

```text
a host filesystem path in any semantic field
   — it carries no record meaning and leaks machine layout into a digest
   (AI-04 §4.3 excluded workspace_root for exactly this reason)
a credential, credential reference value, or credential presence string
   beyond the presence classification allowed in §14
a fabricated producer or a fabricated observed_at
   — AI-02: "Nothing here is ever fabricated"
an artifact availability value
   — availability is a query-time store fact, never a record field (§13.3)
```

---

## 10. Time Semantics

FROZEN. **A timestamp is never classified by its name. It is classified by
whether it changes the meaning of what is recorded.**

### 10.1 The rule

> A timestamp is **SEMANTIC** iff the contract makes that instant part of the claim
> the record is making. It is **OPERATIONAL** iff it records when the Workbench did
> something, rather than what happened in the world.
>
> Operationally, this contract names **exactly one event time per record kind**.
> That field is `observed_at` and it is digested. Every other time is a recording
> time and is excluded, whatever its name.

**Two blanket rules are FORBIDDEN:**

```text
"all timestamps are runtime-only"     FORBIDDEN
"all timestamps are semantic"         FORBIDDEN
```

Neither is even true of the existing repository. AI-04 §20.4 excludes `evaluated_at`
and `retrieved_at` from every digest; yet `plugins/context/sources.py` places a
commit's committer date inside `RawItem.value`, and AI-04 hashes `value` — so a
timestamp is already semantic in AI-04 today, just not through a timestamp field.

### 10.2 The per-kind table — FROZEN

```text
kind          field         classification          rationale
OBSERVATION   observed_at   REQUIRED + SEMANTIC     AI-02 §11.6: a live result
                                                    describes ONE model at ONE
                                                    endpoint on ONE date and does
                                                    not generalise to a later date.
                                                    Excluding the date makes the
                                                    validity window unenforceable.
EXECUTION     observed_at   REQUIRED + SEMANTIC     a run is an event; two runs are
                                                    two runs
DECISION      observed_at   OPERATIONAL             AI-04 T14: evaluated_at changes
                                                    leave the semantic digest
                                                    unchanged. Re-evaluating one
                                                    request is one fact recorded
                                                    twice, not two facts.
```

The classification is a function of `(kind, field)`, **not of the field alone**.

### 10.3 The per-field table — FROZEN

```text
recorded_at     OPERATIONAL   excluded from content_digest, included in record_digest
observed_at     per kind      see §10.2
retrieved_at    OPERATIONAL   an upstream AI-03 read time
evaluated_at    OPERATIONAL   an upstream AI-04 evaluation time
created_at      DOES NOT EXIST — redundant with recorded_at
```

`created_at` is forbidden. Two names for one instant is how two consumers come to
disagree about which is authoritative.

When an AI-05 record's own claim **is** an upstream read — for example an
`OBSERVATION` that the workspace was in a given state at a given time — the instant
is copied into this record's `observed_at` and becomes semantic. The upstream field
keeps its operational meaning. The field **name follows the role**.

### 10.4 Worked consequences

```text
same observation + different recorded_at   ->  same content_digest, different record_digest
same event + genuinely different observed_at (OBSERVATION/EXECUTION)
                                           ->  different content_digest
same decision + different observed_at      ->  same content_digest
```

---

## 11. Payload Contract

FROZEN. The payload is **typed per kind and closed**. Every payload field MUST be
declared in this contract as either SEMANTIC or OPERATIONAL.

```text
OBSERVATION   subject, source binding, status or outcome, the observed facts
DECISION      decision, reason_code, reasons, the input it decided on
EXECUTION     what ran, its ordinal, status, result classification
```

Rules:

```text
the payload has NO free-form map field
every field is declared; an undeclared field is REJECTED (§30)
every string field belongs to a declared class (§14.2)
an unlisted enum value is REJECTED, never treated as an ordinary value (§30)
```

### 11.1 Sequences within a payload

Where a payload asserts a **sequence** — tool calls, ordered steps — the sequence is
semantic and MUST carry an explicit `ordinal`. The collection is ORDER-semantic and
is sorted by that ordinal before hashing (§15.4).

**An ORDER-semantic collection is NOT the same as "serialize in array order".**
Array position is an input the caller controls; serializing in array order would
make the digest depend on how the caller happened to write the list — the defect
AI-04-B §E.1 recorded. Sort by the ordinal, then serialize in that order.

---

## 12. ContextRef

FROZEN. The durable reference to an AI-03 context item.

**AI-03's `ItemRef.render()` MUST NOT become the durable AI-05 reference format.**
It is a display string. It is rejected for three independent reasons, any one of
which is sufficient:

```text
(a) it omits workspace_id, so a reference cannot be checked for workspace
    agreement — and §18 depends on that check
(b) it embeds unbounded document text with no length cap and no secret handling
(c) it is a display format; persisting a display format as an identity is how two
    consumers come to disagree about what the format means
```

### 12.1 The frozen shape

```yaml
ContextRef:
  workspace_id:     string   # identity / scope
  source_kind:      string   # identity — AI-03 SourceKind, imported
  source_identity:  string   # identity
  source_revision:  string   # identity — content-derived
  subject:          string   # identity
  value_digest:     string   # IDENTITY DISCRIMINATOR
  item_kind:        string   # state — FACT | HISTORY | PLAN
  truth_state:      string   # state — PASS | FAIL | BLOCKED | NOT_RUN | UNKNOWN
  freshness:        string   # state — CURRENT | STALE | UNKNOWN
```

### 12.2 Why value participates in identity

Two independent shipped implementations already require it:

```text
AI-03 classification.py Amendment 3 — ItemRef gained `value` because without it the
  two halves of a self-contradicting document (Gate = PASS and Gate = FAIL from ONE
  read) carried the SAME reference, so conflict resolution concluded each was the
  winner and marked neither.
  "A ref that cannot tell two items apart is not a reference to an item."

AI-04 digest.py — the semantic context projection sorts items by
  (subject, source_kind, source_identity, source_revision, value).
```

FROZEN:

```text
same source + same revision + same subject + DIFFERENT value
    ->  DIFFERENT item identities
```

### 12.3 What value_digest is and is not

```text
IS      an identity discriminator: two items from one read with different values
        must be distinguishable
IS NOT  a confidentiality mechanism
IS NOT  secret protection
```

A low-entropy value is brute-forceable from its digest. That is accepted here
because the value is workspace document content already referenced by identity, so
no confidentiality is created or lost. A secret never reaches a ContextRef, because
a secret-bearing field is rejected upstream (§14).

### 12.4 Prohibitions

```text
raw value MUST NOT be persisted in a ContextRef      FORBIDDEN
raw value MUST NOT be rendered into a ContextRef     FORBIDDEN
ItemRef.render() as the durable format               FORBIDDEN
```

---

## 13. ArtifactRef / Artifact Boundary

FROZEN. An artifact is referenced, never ingested.

```yaml
artifacts:
  items:
    - artifact_digest:    string        # REQUIRED
      role:               string        # optional; closed vocabulary
      external:           boolean       # REQUIRED
      owner_workspace_id: string | null # REQUIRED when external = true
      artifact_ref:       string | null # opaque locator
```

### 13.1 Field classification — FROZEN

```text
artifact_digest    SEMANTIC     included in content_digest AND record_digest
role               SEMANTIC     included in both
external           SEMANTIC     included in both
owner_workspace_id SEMANTIC     included in both
artifact_ref       OPERATIONAL  EXCLUDED from content_digest, included in record_digest
availability       RUNTIME      NOT an Evidence field at all
```

**`artifact_ref` is an opaque identifier, never a path.** The id-to-location mapping
is a store-side concern. Because it is opaque, relocation cannot change it, and
promotion alters no field (§20.3).

### 13.2 Collection rules — FROZEN

```text
ordering    SET-semantic, canonical order = (role, artifact_digest)
uniqueness  (role, artifact_digest) unique within a record
            a second entry with the same pair is a DUPLICATE -> REJECT
ordering MUST NOT use artifact_ref   — it is a locator, not an ordering input
```

### 13.3 Availability is not a field

```text
availability   a query-time fact about the store
               NEVER a record field
```

Recording `artifact_state: EXPIRED` on a record would require writing to that
record when the artifact expires — which §19 forbids. An expired artifact makes the
raw source unverifiable while the record itself remains valid and unchanged. **The
digest is what survives the artifact.**

### 13.4 The boundary — FROZEN

```text
AI-05 does not ingest artifact bytes.
AI-05 does not sanitize artifact bytes.
AI-05 does not store artifact bytes.
AI-05 does not guarantee artifact contents are secret-free.
```

```text
artifact storage owner          the PRODUCER — never AI-05
artifact trust boundary         OUTSIDE AI-05
artifact sanitization           the producer's responsibility
artifact retention              independent (ADR-0004)
AI-05's guarantee               the REFERENCE and the DIGEST, never the bytes
```

```text
"not in the normalized record"  MUST NOT be written as  "not stored anywhere"
```

A raw artifact **may** contain a credential. A consumer that follows an
`artifact_ref` is leaving the sanitized boundary, and this contract says so where a
consumer will read it.

### 13.5 The digest is producer-supplied

AI-05 does not read artifact bytes, so `artifact_digest` is supplied by the producer
and AI-05 cannot verify it against bytes it never sees. This is inherent to a
reference model, not a defect. It MUST be stated:

```text
record_digest proves the RECORD was not altered.
It says nothing about whether the artifact still matches its declared digest.
That verification requires a party that holds the bytes.
```

### 13.6 External artifacts

```text
external = true
    REQUIRES owner_workspace_id
    AI-05 NEVER resolves it
    AI-05 records locator + digest only
    it is a DECLARED EXTERNAL DEPENDENCY, not a second workspace scope (§18)
```

---

## 14. Secret Boundary

FROZEN, and deliberately stated as what can be proved.

### 14.1 What AI-05 does not claim

```text
AI-05 does NOT claim detector completeness.
AI-05 does NOT claim that no secret exists anywhere in all artifacts.
AI-05 does NOT claim "no secret can be stored" anywhere, unconditionally.
```

A guarantee nobody can test is worse than a smaller guarantee that holds.

### 14.2 The enforceable boundary — FROZEN

> **There is no free-text field class in an EvidenceRecord.**

Every string field belongs to exactly one declared class:

```text
Class 1  structural    digest / revision; hex, exact length       shape-validated
Class 2  vocabulary    closed enum                                 validated against the enum
Class 3  identifier    ^[A-Za-z0-9._-]{1,64}$ style                shape-validated
                                                                   + redacted
Class 4  bounded       content from a declared source; length cap, flattened
         source        newlines, AND the published admission rule set
Class 5  free text     FORBIDDEN — does not exist in the schema
```

A caller holding an arbitrary string **has no field to put it in.**

### 14.3 The proven invariants

```text
S1  for every rule in the published admission rule set, no accepted record contains
    a value matching that rule outside a declared structural field          PROVABLE
S2  AI-05 computes and stores no digest of a value it did not accept       PROVABLE
S3  no error text is stored — error CLASSIFICATION from a frozen taxonomy
    only, never a message, never a stack trace                             PROVABLE
S4  there is no free-text field class                                      PROVABLE (schema)
S5  AI-05 does not redact; it rejects                                      PROVABLE (no such code path)
```

### 14.4 Division of responsibility — FROZEN

```text
raw secret           handled UPSTREAM. AI-05 does not see it.
sanitization         UPSTREAM capture / sanitizer
                     (providers/redaction.py is reused, not reimplemented)
admission            AI-05 — structural, plus the published rule set
modification         AI-05 NEVER alters a value. Evidence is not the layer that
                     rewrites a fact.
```

AI-05 **may** reject content that violates the published admission rule set. It does
**not** sanitize, redact, or substitute.

### 14.5 Structural fields are not scanned

Class 1 fields MUST NOT be passed through the AI-02 pattern rule set.

```text
providers/redaction.py rule 6:  \b[A-Za-z0-9_\-]{32,}\b  ->  [REDACTED]
```

This rule **matches a 64-character SHA-256 and a 40-character git SHA** — verified
by execution against the actual pattern. Applying it to an evidence record replaces
every digest and every document revision with `[REDACTED]`: the record becomes
unverifiable while appearing successfully sanitized.

The rule is correct for the domain it was written for (provider error text, where a
long opaque run is far more likely to be a key than content). It is backwards for a
store whose content **is** hashes. Applying a rule outside its domain is the defect;
the rule is not wrong.

Resolution — FROZEN:

```text
Class 1 (structural)   shape-validated (exact length, hex charset). NEVER scanned.
                       A value failing the shape check is REJECTED, never replaced.
Class 2 (vocabulary)   validated against the enum. A value outside it is REJECTED.
Class 3 (identifier)   validated as an identifier, THEN redacted — because an id can
                       be identifier-shaped and secret-shaped at once, which AI-02
                       already states and already handles both ways.
Class 4 (bounded)      the full rule set, plus length cap and newline flattening.
```

### 14.6 Secret-derived digests — FORBIDDEN

```text
sha256(secret)   FORBIDDEN anywhere, at any layer
```

Four attacks, none requiring SHA-256 to be broken:

```text
1. low entropy         a PIN or short token is recovered by enumeration
2. dictionary recovery a password from a known corpus is recovered with a wordlist
3. confirmation oracle a stored digest CONFIRMS a candidate the attacker already holds
4. cross-record
   correlation         an unsalted digest links the same secret across two records
```

Salt or HMAC would defeat 1–3 but destroys content-equivalence — the only reason to
digest at all — and requires key management inside an evidence store, which is a
responsibility AI-05 must not take on.

The digest is taken over the **accepted** value. A redacted value's digest is a
constant, which is correct: it distinguishes *redacted* from *empty* from *absent*.

### 14.7 The artifact case, distinguished

`artifact_digest` is a digest of bytes that may contain a credential. That is
**materially different** from `sha256(secret)`: attacking it requires guessing the
whole artifact rather than a low-entropy preimage, and the bytes are outside AI-05's
boundary (§13.4). It is accepted, and AI-05 makes no claim about the artifact's
contents.

### 14.8 The residual case, stated rather than hidden

A secret that is itself exactly 64 lowercase hexadecimal characters is
indistinguishable **by shape** from a digest. The mitigation is provenance, not
shape:

```text
Class 1 fields are written only by AI-05's own digest function over canonical
content. They are NEVER caller-supplied.
```

That constraint MUST be stated and tested (T20c, T22d).

---

## 15. Canonicalization

FROZEN. Implements the AI-04 §20.2 rules, **imported, not restated**.

```text
encoding         UTF-8, no BOM
form             canonical JSON
object keys      sorted lexicographically by Unicode code point
whitespace       no insignificant whitespace
enums            canonical string form
nulls            a field in the projection whose value is not established is null,
                 never omitted; omission is not a second way to say null
absent field     a field outside the projection is not serialized at all
digest           SHA-256 over the canonical bytes, lowercase hexadecimal
bare set         REFUSED — a set has no canonical order; sort it into a list first
```

### 15.1 Two digests, two jobs

FROZEN. Conflating them is a defect.

```text
content_digest   SEMANTIC EQUIVALENCE     "do these two records make the same claim?"
record_digest    STORED-RECORD INTEGRITY  "has this stored record been altered?"
```

### 15.2 The per-field table — FROZEN

```text
field                          content_digest   record_digest
evidence_id                    excluded         included
schema_version                 included         included
kind                           included         included
producer                       included         included
producer_version               included         included
producer_type                  included         included
actor.id                       included         included
actor.type                     included         included
workspace_id                   included         included
experiment_id                  included         included
observed_at                    per kind (§10.2) included
recorded_at                    EXCLUDED         included
payload                        included         included
references.context[]           included         included
references.decisions[]         included         included
references.supersedes[]        included         included
artifacts[].artifact_digest    included         included
artifacts[].role               included         included
artifacts[].external           included         included
artifacts[].owner_workspace_id included         included
artifacts[].artifact_ref       EXCLUDED         included
availability                   not a field      not a field
content_digest                 —                included
record_digest                  excluded         excluded (never its own input)
storage tier                   excluded         EXCLUDED
```

```text
storage tier MUST NOT be in content_digest.
storage tier MUST NOT be in record_digest either — it is a property of where the
  bytes are, not of the bytes.
```

### 15.3 Why artifact_ref is excluded from content_digest

```text
content_digest claims location-independence: promotion changes location and the
  semantic claim does not change.
If artifact_ref were digested, the same artifact bytes at a different locator would
  produce a different content_digest, contradicting that property.
```

It remains in `record_digest`, so repointing a record at different bytes is
**detectable**. Under a single-digest model that alteration was invisible; this is
the hole the two-digest model closes.

### 15.4 The canonical collection table — FROZEN

**Order semantics MUST NOT be inferred at implementation time.** Every collection is
declared here.

```text
collection                    order            canonical key
payload maps                  object canonical  sorted keys
references.context[]          SET              (workspace_id, source_kind, source_identity,
                                                source_revision, subject, value_digest)
references.decisions[]        SET              record_ref
references.supersedes[]       SET              record_ref
artifacts.items[]             SET              (role, artifact_digest)
payload tool_calls[]          ORDER            explicit ordinal, then serialized in
                                                that order
payload tests[]/results[]     SET              (test_id, status)
```

An undeclared collection is a contract violation, not an implementation choice. AI-04
paid for an undeclared collection twice — Amendment 9(b) and AI-04-B §E.1 — and both
times the symptom was a digest that moved when nothing semantic did.

### 15.5 The eight canonical cases — FROZEN

```text
C1  same semantics, different YAML key order       SAME content_digest
C2  same semantics, different set order            SAME content_digest
C3  same semantics, different artifact locator     content_digest SAME (excluded)
                                                   record_digest  DIFFERENT
C4  same semantics, different recorded_at          content_digest SAME
                                                   record_digest  DIFFERENT
C5  same semantics, different evidence_id          content_digest SAME
                                                   record_digest  DIFFERENT
C6  same event, different observed_at              OBSERVATION/EXECUTION: DIFFERENT
                                                   DECISION:              SAME
C7  same artifact bytes, different artifact_ref    identical to C3
C8  same Context identity, different value_digest  content_digest DIFFERENT
                                                   (value participates in identity, §12.2)
```

---

## 16. content_digest

FROZEN.

```text
purpose     semantic equivalence
covers      kind, semantic provenance fields, payload, semantic ContextRef fields,
            artifact_digest and semantic artifact metadata, supersedes
excludes    evidence_id, recorded_at, artifact_ref, artifact availability,
            storage tier
property    INVARIANT across promotion and relocation
job         deduplication; "do these two records make the same claim?"
```

```text
same content_digest  does NOT imply same evidence_id   (§8.1)
```

---

## 17. record_digest

FROZEN.

```text
purpose     integrity of the stored record
covers      every persisted field, including evidence_id, recorded_at, artifact_ref
excludes    record_digest itself — a digest MUST NOT be its own input
property    any alteration changes it
job         verify a stored record was not modified;
            verify a promotion copy is byte-identical
```

**Round trip is a requirement:**

```text
serialize -> canonicalize -> hash          == record_digest
re-read   -> parse -> canonicalize -> hash == the SAME record_digest
```

An implementation whose storage format does not round-trip losslessly (a string
that re-parses as a boolean, a numeric string that re-parses as a number) will drift
`record_digest` on an unmodified record. This is an implementation obligation under
C9, and it is a known trap, not a discovery for AI-05-B to make.

---

## 18. Workspace Isolation

FROZEN.

```text
Every Evidence evaluation is scoped to exactly ONE workspace.

NEVER merge.
NEVER filter.
NEVER repair.
```

### 18.1 The agreement rule

```text
evidence.workspace_id        REQUIRED, non-empty
producer.workspace_id        MUST equal evidence.workspace_id
source.workspace_id          MUST equal evidence.workspace_id
context.workspace_id         MUST equal evidence.workspace_id
guard.workspace_id           MUST equal evidence.workspace_id
experiment.workspace         MUST equal evidence.workspace_id
artifact.workspace           MUST equal evidence.workspace_id, UNLESS the artifact
                             is explicitly marked external with an owner
```

### 18.2 Outcomes — FROZEN

```text
same workspace       ACCEPT
foreign workspace    REJECT
missing workspace    REJECT
unknown/unresolvable REJECT
external artifact    ACCEPT only when explicitly marked external, with
                     owner_workspace_id, and NEVER resolved by AI-05
```

### 18.3 Why filtering is separately named

AI-04's contract said *"never merged, filtered, or repaired"* for its entire frozen
life, and the implementation **filtered** anyway. Foreign context was dropped and
evaluation continued, so an unconditional `ALLOW` rule succeeded on a request
spanning two workspaces — a cross-workspace authorization reaching `ALLOW`
(AI-04-B §L, review Fix #2).

**Filtering is the default failure mode.** The prohibition MUST be asserted against
a constructible two-workspace input (T13), not merely stated. A rule with no test is
the rule AI-04 already proved insufficient.

### 18.4 External artifacts do not make a record span two workspaces

A record's **scope** is `workspace_id`. A marked external artifact is a **declared
external dependency**, carrying its owner explicitly. It is not a second scope.

```text
unmarked foreign reference   REJECT
marked external artifact     ACCEPT   (§13.6)
```

Both halves MUST be asserted (T13, T14).

---

## 19. Lifecycle

FROZEN.

```text
write-once
append-only
immutable
```

```text
an admitted EvidenceRecord is NEVER modified. Ever. In any tier.
```

### 19.1 What is not a lifecycle state

```text
validated    NOT A FIELD. A `validated` flag is a promotion field: it would have to
             be written after the record exists.
referenced   DERIVED. Computable from other records' reference fields.
revoked      NOT IN v1. A record of what happened cannot be un-happened. Withdrawing
             a claim is a NEW record about the old one, never a mutation.
```

### 19.2 Deletion

```text
durable (promoted) records   MUST NOT be deleted
staged records               may be DISCARDED   (§20.2)
```

---

## 20. Staged vs Promoted Durability

FROZEN. This section resolves the apparent conflict between "immutable" and
"discardable" by separating **two orthogonal properties**.

```text
immutability   a written record's CONTENT never changes
durability     a written record's EXISTENCE is guaranteed against loss

A staged record is immutable-but-not-durable. Nothing about that is contradictory.
```

### 20.1 The two tiers — FROZEN

```text
STAGED / workspace-local
    immutable
    workspace-local
    survives process and host restart as required by the local store
    may be DISCARDED as a whole
    NOT the permanent durable Evidence guarantee

PROMOTED
    immutable
    durable
    human-controlled promotion
    survives repository clone and a future session
    MUST NOT be deleted
```

### 20.2 discard ≠ delete ≠ mutate — FROZEN

```text
discard   remove the whole record from a NON-durable tier
          ALLOWED. All-or-nothing. Never a partial edit.
          Permitted only because the record's existence was never guaranteed.

delete    destroy a record whose existence WAS guaranteed
          FORBIDDEN. Unconditionally.

mutate    change any field of a written record
          FORBIDDEN. In both tiers.
```

### 20.3 Promotion — FROZEN

```text
promotion is a human-controlled publication
```

```text
same evidence_id      REQUIRED
same content_digest   REQUIRED
same record_digest    REQUIRED
same bytes            REQUIRED
new location only
```

Therefore:

```text
promotion does NOT create a new EvidenceRecord
promotion does NOT create a new evidence_id
promotion does NOT mutate the record
promotion does NOT change content_digest or record_digest
storage tier is NOT part of the semantic content
```

A second Evidence type for promoted records is **FORBIDDEN**: it would force either a
new `evidence_id` or a type change, and a new id breaks every reference *into* the
record — including the link that is the entire reason `record_ref` exists.

### 20.4 The durability contract — FROZEN

```text
D1  a written record survives process restart                    REQUIRED
D2  a written record survives host restart                       REQUIRED
D3  a written record is readable by a future session             REQUIRED
D4  a written record's content is verifiable by its record_digest REQUIRED
D5  a written record is never MUTATED                            REQUIRED (both tiers)
D5' a staged record may be DISCARDED                             explicit, not implied
D5''a promoted record is never deleted                           REQUIRED
D6  a record survives a repository clone    REQUIRED for PROMOTED records only
```

```text
who guarantees what:
    AI-05            D1–D5, D5', D5'' for records it accepts
    Git, for a human D6, for promoted records — not automated, never by AI-05
    For STAGED records, D6 is explicitly NOT guaranteed.
```

### 20.5 What AI-05-A does NOT freeze

```text
JSON | YAML | SQLite | filesystem       NOT DECIDED HERE
```

AI-00 §17 reserves the storage format as an implementation decision. This contract
freezes the **logical** durability contract only.

It does, however, require that location, retention and cleanup be **declared** when a
backend is chosen. AI-03 refused to ship a persistent cache without them, on the
grounds that doing so "would ship a second, undeclared source of truth" (D-10,
F-11). An evidence store is a source of truth **by construction**, so the same
requirement applies with more force.

---

## 21. Supersession / Correction

FROZEN.

### 21.1 The model

```text
correction = a NEW record naming what it supersedes
```

```yaml
references:
  supersedes:
    - record_ref:       string   # the superseded evidence_id
      correction_reason: string
```

```text
the OLD record is UNCHANGED FOREVER
```

### 21.2 Stored vs derived — FROZEN

```text
supersedes[]     EXPLICIT FIELD on the NEW record. Stored. In content_digest. SET-semantic.
superseded_by    DERIVED query result ONLY. NEVER a stored field.
```

The relationship is authored once, by the correcting record, at the moment it is
written. That is the only moment at which it is unambiguous, and the only writer
that is not mutating an existing record.

```text
A stored `superseded_by` on the old record   FORBIDDEN
A revision counter on one identity           FORBIDDEN
Revocation by mutation                       FORBIDDEN
```

A revision counter (`A.revision = 1, 2`) reinterprets one identity across time, so
`evidence_id` stops denoting a record and starts denoting a lineage — every reference
to it becomes ambiguous about which revision was meant.

### 21.3 Consequences to state

```text
A consumer reading ONE record cannot tell it was superseded.
Supersession is a property of the SET, not of a record.
A consumer that needs it MUST index.
```

This is deliberate. Storing it on the old record would trade that inconvenience for
mutability.

---

## 22. Failure Semantics

FROZEN.

### 22.1 Admission outcomes

```text
ACCEPTED      the record was admitted
REJECTED      a contract or content violation; NOTHING was stored
UNAVAILABLE   a persistence or dependency failure; NOTHING was stored
```

There is deliberately **no third `BLOCKED`**. AI-04 §18.2 introduced `CheckResult`
specifically to avoid a second `BLOCKED` ("BLOCKED is a decision, and a check is
never `BLOCKED`, it is `UNAVAILABLE`"), and AI-04 §3 records that one word in two
vocabularies is a defect AI-03 already paid for with `ContextStatus.COMPLETE`.

### 22.2 The condition table — FROZEN

```text
condition                     outcome       note
malformed record              REJECTED      shape violation
missing required field        REJECTED      required is per-kind (§11)
unsupported enum              REJECTED      never silently ordinary (§30)
workspace mismatch            REJECTED      §18
workspace missing             REJECTED      required field
workspace unresolvable        REJECTED      §18.2
secret detected in a Class 4
  field by the published rules REJECTED     never stored, never redacted in place
structural field malformed    REJECTED      never redaction, never substitution
digest mismatch               REJECTED      integrity failure
duplicate evidence_id         REJECTED      collision or overwrite attempt
duplicate content_digest      ACCEPTED      two events (§8.2)
artifact missing              NOT a failure. artifact_ref is a pointer; availability
                                            is a query-time fact (§13.3)
required source missing       REJECTED
optional source missing       ACCEPTED with an UNKNOWN value recorded
                                            (AI-03 §5.7: not read is not empty, and
                                             is not PASS)
storage failure               UNAVAILABLE   returned to the caller
```

### 22.3 The distinction that MUST be preserved

```text
INCOMPLETE CONTENT    the record was READ and is deficient.
                      -> REJECTED. Nothing is stored. The caller is told which
                         requirement failed.

WRITE FAILURE         the record was VALID and storage did not complete.
                      -> UNAVAILABLE. Nothing is stored. The caller is told the
                         write did not happen.
```

**FORBIDDEN in both cases:** storing a record that describes the failure as if it
were evidence. A record saying `status: WRITE_FAILED` is a record asserting a fact
about AI-05's own storage, written by the storage that just failed. It is
self-referential, it is unverifiable, and a consumer will read it as evidence about
the world. **The failure belongs in the return value.**

### 22.4 Why REJECTED rather than a labelled partial

AI-03's `PARTIAL` is legitimate because a context response is useful while
incomplete **and is labelled**. An evidence record is a durable claim: a partial
durable claim is one that will be misread later, after the label has been forgotten
and the record is being cited. A durable record outlives its reader's attention.

---

## 23. AI-02 Boundary

FROZEN. This is the highest-risk boundary in the phase and it is a **negative**
contract.

```text
AI-05 supplies records.
AI-02 evaluates verification predicates.
A human performs reviewed promotion.
```

Three separate actors. AI-05 is not one of the other two.

### 23.1 FORBIDDEN

```text
Evidence existence        -> capability VERIFIED        FORBIDDEN
record_ref existence      -> capability VERIFIED        FORBIDDEN
OBSERVATION record        -> capability promotion       FORBIDDEN
DECISION record           -> capability promotion       FORBIDDEN
any AI-05 record          -> any truth-state promotion  FORBIDDEN
```

### 23.2 Why

AI-02's verification anchor is not a **pointer**, it is a **predicate**.
`providers/model_profile.py` computes
`has_verification = verified_at is not None and evidence_ref is not None`, and
AI-02 §8.3 states that only recorded execution evidence promotes `DECLARED`, that
provider documentation is not Workbench evidence, and that a fixture is not evidence
of provider behaviour.

If "an AI-05 record exists" satisfied the anchor, then **write access to AI-05 would
be privilege escalation to capability promotion**. Any component able to append a
record — a future tool call, a test, a script — could promote a capability. And if
AI-05 evaluated the predicate itself, AI-05 would *be* the promotion authority, i.e.
a policy engine, which §2.3 forbids.

### 23.3 Anchor vs record_ref — FROZEN

```text
AI-02 verification anchor
    authority-bearing predicate input
    may participate in DECLARED -> VERIFIED
    evaluated by AI-02

AI-05 record_ref
    an opaque evidence_id
    a reader link
    no authorization
    no capability promotion
```

**These are never the same authority concept.** AI-05 MUST NOT introduce an
unqualified `evidence_ref`; it uses `record_ref`.

### 23.4 Existing fields — UNCHANGED

```text
providers/*.yaml + model_profile.Provenance.evidence_ref     UNCHANGED this phase
plugins/guard/models.py DecisionRecord.evidence_ref          UNCHANGED this phase
```

Both are currently provably `null` (`providers/validate.py` requires it until
AI-02-B6; AI-04 C9 records that a null `evidence_ref` is not a failure).

```text
Rename                          DEFERRED
                                a SEPARATE amendment candidate
TRIGGER CONDITION (frozen):
    the rename becomes MANDATORY before the first non-null production use of
    either legacy field.
```

---

## 24. AI-03 Boundary

FROZEN.

```text
Context is upstream input.
AI-05 records what was consulted.
```

AI-05 MUST NOT:

```text
promote truth
convert PLAN     -> FACT
convert HISTORY  -> FACT
convert UNKNOWN  -> VERIFIED
convert STALE    -> CURRENT
modify a ContextItem
modify a ContextResponse
```

```text
the Context cache is NOT an Evidence source of truth
Evidence does NOT replace Context
```

`ContextResponse` and `ContextItem` are **imported** by identity where AI-05 must
validate workspace agreement. AI-03 is not modified.

---

## 25. AI-04 Boundary

FROZEN.

```text
A DecisionRecord MAY be recorded by AI-05.
```

AI-05 MUST NOT:

```text
alter a decision outcome
authorize anything
feed Evidence back into Guard evaluation
require any AI-04 production change
```

```text
Guard decides.   Evidence records.
```

The arrow is one-directional:

```text
Guard  -> Evidence      a RECORD relationship
Evidence -> Guard       FORBIDDEN
```

`plugins/guard/models.py` `DecisionRecord.evidence_ref` is **untouched** this phase.
AI-05 refers to a stored decision by `record_ref`.

---

## 26. AI-06 Boundary

FROZEN.

AI-06 produces:

```text
tool execution
test execution
artifact production
```

which **can** produce Evidence, as `EXECUTION` or `OBSERVATION`.

AI-05:

```text
records normalized execution results
```

AI-05 MUST NOT:

```text
execute tools
run tests
interpret tool safety policy
store raw tool output inside a record
```

A tool's own claim of success is **a claim with a producer**. AI-05 records the
claim and its producer. It adjudicates nothing.

---

## 27. AI-07 Boundary

FROZEN.

A routing decision **can** become a `DECISION` record.

AI-05 MUST NOT:

```text
route
select a model
reserve a Router-shaped interface field
```

AI-07 is **DEFERRED**. AI-05 does not stub it, does not reserve an interface for it,
and its record kinds cover routing decisions without naming the Router — the generic
`producer` and `kind` fields are sufficient.

---

## 28. AI-11 Boundary

FROZEN.

```text
AI-11 CONSUMES Evidence.
```

AI-05 MUST NOT:

```text
aggregate
rank
score
benchmark
compute any metric
```

This is the boundary MASTER_ROADMAP §4 depends on: AI-11 computes
`task success`, `false pass`, `security-boundary violations` and the rest **from**
AI-05 records. AI-05 must be able to support those computations and must not perform
them.

---

## 29. Truth / Status Preservation

FROZEN. The prohibition matrix.

```text
PLAN                  -> FACT                  FORBIDDEN
HISTORY               -> FACT                  FORBIDDEN
UNKNOWN               -> VERIFIED              FORBIDDEN
UNKNOWN               -> PASS                  FORBIDDEN
NOT_RUN               -> PASS                  FORBIDDEN
BLOCKED               -> PASS                  FORBIDDEN
STALE                 -> CURRENT               FORBIDDEN
STALE                 -> WRONG                 FORBIDDEN
COMPLETE              -> PASS                  FORBIDDEN
"BLOCKED / DEFERRED"  -> BLOCKED               FORBIDDEN  (compound is never decomposed)
absent                -> false                 FORBIDDEN
cache_hit             -> any content change    FORBIDDEN

Evidence exists            -> the thing is TRUE         FORBIDDEN
Evidence exists            -> VERIFIED                 FORBIDDEN
Evidence DECISION=ALLOW    -> Guard ALLOW               FORBIDDEN
record_ref                 -> authorization             FORBIDDEN
Evidence approval ref      -> an approval exists        FORBIDDEN
```

### 29.1 No new merged status vocabulary

AI-05 MUST NOT create a new `status` field that merges `GuardDecision`,
`CheckResult`, `item_kind`, or `truth_state`.

```text
They are different types with different meanings, and are never compared, stored in
one field, or converted into one another.
```

---

## 30. Admission Contract

FROZEN. The single entry condition for storing a record.

```text
1. shape          the record matches the declared envelope and its kind's payload
                  -> a field the contract does not define is REJECTED, not ignored
2. schema_version the version is supported
3. required       every required field for that kind is present and non-null
4. vocabulary     every enum value is a member of its closed set
5. workspace      workspace_id is present, non-empty, and agrees everywhere (§18)
6. classes        every string field is validated against its declared class (§14.2)
7. rule set       Class 4 fields are checked against the published admission rules
8. references     references are well-formed and their identity is complete (§12)
9. artifacts      artifact entries satisfy §13.1/§13.2
10. integrity     supplied digests match recomputation
11. uniqueness    evidence_id is not already present
```

Any failure produces `REJECTED` with a named reason and **stores nothing**.

```text
unknown top-level field        REJECTED   — a field that is silently dropped cannot
                                            be audited (AI-04 §4.2 precedent)
unsupported schema_version     REJECTED
```

---

## 31. Test Matrix

FROZEN. Layers 1–3 only. **AI-05 adds no layer 4** — the plugin has no network
surface and no opt-in execution path, so there is nothing for a live layer to gate
(AI-03 D-9 precedent).

Layer 0 gains a structural check for `plugins/evidence`, mirroring
`check_context_plugin_performs_no_git_write`.

| # | Test | Purpose | Input | Expected | Security property |
| --- | --- | --- | --- | --- | --- |
| T1 | valid record | baseline | a well-formed record | `ACCEPTED`, round-trips | nothing is measurable without it |
| T2 | malformed record | shape enforcement | structurally invalid record | `REJECTED` | a shape violation is never absorbed |
| T3 | missing required field | per-kind requirement | record missing one required field, per kind | `REJECTED` | optionality cannot be enforced; absence cannot be a default |
| T4 | unsupported enum | closed vocabulary | an unlisted enum value | `REJECTED` | an unlisted value is never treated as ordinary |
| T5 | `evidence_id` identity | identity ≠ semantics | two records, same content, different ids | both accepted; ids differ; ids absent from `content_digest` | two runs are two events |
| T6 | `experiment_id` correlation | correlation ≠ identity | many records, one `experiment_id` | all accepted, none unique | grouping never becomes identity |
| T7 | `content_digest` determinism | canonicalization | same semantic input, separate processes | identical digest | an unenforced digest is not a digest |
| T8 | operational fields | time semantics | vary `recorded_at` | `content_digest` unchanged, `record_digest` changed | recording time is not the claim |
| T9 | semantic `observed_at` | time semantics | vary `observed_at` on OBSERVATION/EXECUTION vs DECISION | different for the former, same for the latter | the validity window is enforceable; re-evaluation is not a new fact |
| T10 | set permutation invariance | order semantics | permute `context[]`, `artifacts[]`, `supersedes[]` | same `content_digest` | an undeclared order dependence is a latent defect |
| T11 | order-semantic sequence | order semantics | reorder tool calls; then rewrite the array with the same ordinals | different digest; then same digest | array position is not semantic; the ordinal is |
| T12 | workspace isolation | scope | one workspace throughout | `ACCEPTED` | one record, one workspace |
| T13 | cross-workspace rejection | scope | a constructible two-workspace input | `REJECTED`, nothing stored, no foreign item dropped silently | filtering is the proven default failure mode |
| T14 | external artifact | scope | marked external artifact with owner | `ACCEPTED`, never resolved | an external dependency is not a second scope |
| T15 | PLAN preservation | truth | a PLAN item referenced | PLAN stays PLAN | a plan is not evidence |
| T16 | HISTORY preservation | truth | a HISTORY item referenced | HISTORY stays HISTORY | a past state is not the present one |
| T17 | UNKNOWN preservation | truth | an UNKNOWN value | UNKNOWN recorded as UNKNOWN, not defaulted | absent is not false |
| T18 | NOT_RUN preservation | truth | `NOT_RUN` | recorded as `NOT_RUN`, never as `PASS` | a check that did not run supports nothing |
| T19 | BLOCKED preservation | truth | `BLOCKED` | recorded as `BLOCKED`, never as `PASS` | blocked is not passed |
| T20a | valid 40-char git SHA | structural class | a git SHA in a revision field | NOT redacted, `ACCEPTED` | rule 6 must not destroy revisions |
| T20b | valid 64-char SHA-256 | structural class | a SHA-256 in a digest field | NOT redacted, `ACCEPTED` | rule 6 must not destroy digests |
| T20c | structural provenance | residual case | a 64-hex value in a Class 4 field | the DECLARED policy, asserted | "64 hex is safe" is only true where provenance is constrained |
| T21a | malformed digest length | structural class | wrong-length digest | `REJECTED` | shape failure is never a redaction candidate |
| T21b | malformed digest charset | structural class | non-hex in a digest field | `REJECTED` | as T21a |
| T21c | digest normalization | structural class | uppercase hex | the DECLARED policy, asserted | normalization is decided, not assumed |
| T22a | known test secret | secret boundary | a known test secret in a Class 4 field | `REJECTED` | published rules are enforced at admission |
| T22b | secret-shaped token | secret boundary | a secret-shaped token in a Class 4 field | `REJECTED` | as T22a |
| T22c | identifier path | secret boundary | a secret-shaped token in a Class 3 field | redacted per the identifier rule, then accepted | an id can be identifier-shaped and secret-shaped at once |
| T22d | secret-derived digest | secret boundary | `sha256(known secret)` in a digest field | `ACCEPTED` by shape, and asserted as a KNOWN, DOCUMENTED limit | a documented residual beats a passing test that pretends there is none |
| T23 | raw payload not normalized | payload boundary | an oversized raw payload | artifact-only; the record stays valid | normalized output is durable, raw payload is not |
| T24 | artifact reference contract | artifact boundary | an artifact entry | digest required; `artifact_ref` opaque; availability absent | AI-05 references bytes it never reads |
| T25 | immutable write | lifecycle | any later operation on an admitted record | bytes unchanged | an audit trail that can be edited is not one |
| T26 | correction via `supersedes` | lifecycle | a correcting record | new record accepted; old record byte-identical | corrections are additions, never edits |
| T27 | `superseded_by` derived | lifecycle | query the set | derivable; not a stored field on any record | a stored back-pointer is a mutation |
| T28 | duplicate `evidence_id` | identity | the same id twice | `REJECTED` | collision or overwrite attempt |
| T29 | duplicate content | identity | same `content_digest`, different ids | both `ACCEPTED` | repeated observation is not an error |
| T30 | Guard Decision recording | AI-04 boundary | a `DecisionRecord` stored | stored; NO decision outcome changes | Evidence → Guard is forbidden |
| T31 | capability promotion negative | AI-02 boundary | append a valid OBSERVATION about a real model_ref; observe AI-02 promotion state before and after | record `ACCEPTED`; `verified_at` still null; `evidence_ref` still null; `CapabilityStatus` unchanged | an absence of effect is proven only by observing before and after |
| T32 | ContextRef structure | reference integrity | a context item mapped to a ContextRef | 9 fields; `value_digest` present; raw `value` absent | a display string is not a durable identity |
| T33a | Evidence existence | truth preservation | any admitted record | no Guard `ALLOW`, no capability promotion, no truth change | existence is not truth |
| T33b | NOT_RUN evidence | truth preservation | a record whose status is `NOT_RUN` | no `PASS` anywhere | the most-repeated rule in the Workbench |
| T33c | DECISION=ALLOW evidence | truth preservation | a DECISION record with `ALLOW` | no Guard `ALLOW` results | Evidence does not authorize |
| T33d | approval reference | truth preservation | a record carrying an approval reference | no approval is deemed to exist | a caller-supplied reference is not evidence of approval (AI-04 §8) |
| T34 | regression | non-regression | the full existing suite | pass count does not decrease | a phase never trades away existing guarantees |
| T35 | architecture boundary | structural | `plugins/evidence` parsed with `ast` | no network client, no `subprocess`, no `eval`/`exec`/`compile`, no `routing`/`tools` import, no secret logging | the boundary is checked, not promised |

### 31.1 Notes on the matrix

```text
T9 and T11 are the two tests that catch the mistakes this contract's decisions exist
  to prevent. If the matrix is trimmed, keep these.
T13 MUST construct a genuinely two-workspace input. AI-04's history shows that
  asserting the prohibition without constructing the input does not catch it.
T22d documents a limit rather than passing silently. It MUST NOT be weakened into a
  passing test.
T31 MUST observe state before and after. Asserting an absence rhetorically proves
  nothing.
T33a-d are four separate routes to the same forbidden outcome. One test would cover
  one route and imply the other three.
```

---

## 32. Exit Gates

FROZEN. AI-05 is complete only when every gate below passes.

| # | Gate | Condition |
| --- | --- | --- |
| C0 | Contract frozen | this document is frozen and its amendment log is open |
| C1 | Schema shape | record shape fixed; every collection declared order- or set-semantic |
| C2 | Identity | identity, correlation, integrity and equivalence are separate fields |
| C3 | Provenance | every record names producer, actor, workspace, and its times |
| C4 | Workspace isolation | one workspace per record; never merged, filtered, or repaired |
| C5 | Truth / status preservation | no promotion path exists for any status |
| C6 | Secret-safe admission | no free-text class; published rules enforced; no secret-derived digest |
| C7 | Artifact boundary | references and digests only; no byte ingestion |
| C8 | Immutable / append-only | written records never change; corrections are new records |
| C9 | Digest determinism + integrity | `content_digest` stable; `record_digest` round-trips |
| C10 | Reference integrity | references identify items and are never silently dropped |
| C11 | Boundary preserved | AI-05 records; it does not authorize, promote, execute, route or rank |
| C12 | Regression | the pre-existing suite's pass count does not decrease |
| C13 | Required CI | CI green on the head the phase claims |

### 32.1 What is proved / required evidence / forbidden state

```text
C0 — Contract frozen
  Proved     the contract exists, is frozen, and its amendment log is open
  Evidence   this document; the amendment log (§34.3)
  Forbidden  a contract amended silently after implementation began; a test
             deleted, weakened, or re-scoped to make an implementation pass

C1 — Schema shape
  Proved     the record shape is fixed and canonicalization is fully declared
  Evidence   the §15.4 collection table with EVERY collection declared
  Forbidden  an undeclared collection; order semantics inferred at implementation time

C2 — Identity
  Proved     the six identity roles are separate fields with separate jobs
  Evidence   T5, T6, T28, T29
  Forbidden  a content-derived evidence_id; a stored duplicate_of; identity conflated
             with content-equivalence

C3 — Provenance
  Proved     every record names who wrote it, whose act it describes, and when
  Evidence   T1, T3; the §9.1 required-field list
  Forbidden  a record with no producer or no actor; an absent observed_at where the
             kind's claim is time-bound; a fabricated provenance field; a host path
             or artifact availability in a record

C4 — Workspace isolation
  Proved     one workspace per record; no merge, filter, or repair
  Evidence   T12, T13, T14; a constructed two-workspace input
  Forbidden  a foreign item filtered and the admission continuing; an unmarked
             external reference

C5 — Truth / status preservation
  Proved     no promotion path exists for any status
  Evidence   T15–T19, T33a–d; the §29 matrix
  Forbidden  PLAN->FACT; HISTORY->FACT; UNKNOWN->VERIFIED/PASS; NOT_RUN->PASS;
             BLOCKED->PASS; STALE->CURRENT; STALE->WRONG; COMPLETE->PASS;
             a compound declaration decomposed into a satisfying part

C6 — Secret-safe admission
  Proved     the §14.3 invariants hold and the limit is stated
  Evidence   T20a–c, T21a–c, T22a–d; the published rule set; the Class 1 prohibition
  Forbidden  a secret in a Class 4 field; sha256(secret) anywhere; a blanket
             application of rule 6 to structural fields; stored error text;
             an unlabelled redaction; a claim of detector completeness

C7 — Artifact boundary
  Proved     references and digests only; no byte ingestion; availability not a field
  Evidence   T23, T24
  Forbidden  claiming AI-05 verifies artifact bytes; artifact availability stored as
             a record field; a missing artifact treated as record corruption;
             an unmarked external artifact

C8 — Immutable / append-only
  Proved     an admitted record's bytes never change; corrections are new records
  Evidence   T25, T26, T27
  Forbidden  a stored superseded_by; a revision counter on one identity; revocation
             by mutation; deletion of a promoted record; promotion changing content
             rather than location only

C9 — Digest determinism + integrity
  Proved     equal semantics -> equal content_digest; altered bytes -> different
             record_digest; storage round-trips
  Evidence   T7–T11; the §15.5 canonical cases
  Forbidden  a digest varying with mapping, file, or set order; a digest INVARIANT
             across a genuine semantic difference; a record_digest that drifts on
             an unmodified record after a storage round trip

C10 — Reference integrity
  Proved     references identify items and are never silently dropped
  Evidence   T32; the §12.2 identity rule
  Forbidden  ItemRef.render() as the durable format; a reference that cannot
             distinguish two items from one read; a raw value persisted in a
             ContextRef; a reference silently filtered

C11 — Boundary preserved
  Proved     AI-05 records; it does not authorize, promote, execute, route or rank
  Evidence   T30, T31, T33a–d, T35; the structural import check
  Forbidden  Evidence->Guard authorization; Evidence->capability promotion;
             Evidence existence->any truth promotion; AI-05 evaluating an AI-02
             verification predicate; any aggregation, scoring or ranking surface

C12 — Regression
  Proved     the pre-existing suite's pass count does not decrease; AI-02/03/04
             implementations are unmodified
  Evidence   T34; the counts; a diff check
  Forbidden  a decreased pass count presented as unrelated; a count carried forward
             from another phase

C13 — Required CI
  Proved     CI is green on the head the phase claims
  Evidence   the required CI run on that commit
  Forbidden  NOT_RUN counted as complete; BLOCKED counted as complete; UNKNOWN
             counted as complete; local execution presented as CI execution
```

---

## 33. Non-Goals

FROZEN, restated as a single list because the boundary is the deliverable.

```text
AI-05 is NOT:
    a secret scanner
    a tool executor
    a Guard
    an authorization engine
    an AI-02 capability promotion engine
    a context store
    a router
    a benchmark ranking engine
    a raw-log archive
```

It also does not:

```text
sanitize or redact content            (§14.4)
ingest artifact bytes                 (§13.4)
resolve an external artifact          (§13.6)
modify any AI-02 / AI-03 / AI-04 field or type
compute a metric from its own records (§28)
decide what its records mean
```

---

## 34. Amendment Rules

### 34.1 Amendment required

A frozen contract changes **only** through an explicit amendment recorded in §34.3.

An amendment is REQUIRED for any new or changed:

```text
Evidence kind                     (§6)
canonical collection              (§15.4)
digest input                      (§15.2)
workspace rule                    (§18)
secret boundary                   (§14)
authority relation                (§23–§28)
identity field                    (§8)
admission outcome                 (§22.1)
```

### 34.2 Forbidden

```text
implementation convenience  ->  silent contract weakening     FORBIDDEN
a rule relaxed to make an implementation pass                 FORBIDDEN
a test deleted, weakened, or re-scoped to make a test pass    FORBIDDEN
```

Implementation MUST NOT silently diverge from this contract. A divergence found
during implementation is either a defect in the implementation or grounds for a
recorded amendment — never a quiet adjustment.

### 34.3 Amendment log

```text
(none — this is the freeze revision)
```

---

## 35. Open Future Work

DEFERRED. Declared so that absence is auditable rather than inferred.

### 35.1 Deferred by this freeze

```text
F-10  legacy evidence_ref rename
      DEFERRED — a separate amendment candidate
      MANDATORY before the first non-null production use of either legacy field
      (§23.4)

storage backend: JSON | YAML | SQLite | filesystem
      NOT DECIDED (§20.5); AI-00 §17 reserves it
      location, retention and cleanup MUST be declared when chosen

record_digest round-trip under the chosen physical format
      an implementation obligation under C9, flagged in §17 so it is not
      discovered in AI-05-B
```

### 35.2 Frozen by this document, for the record

```text
F-12  durability
      FROZEN as the staged / promoted tier model (§20)
      D6 applies to PROMOTED records only; staged records are explicitly
      not durable
```

### 35.3 Not started

```text
AI-05-B   implementation               NOT STARTED
plugins/evidence/                      README.md placeholder only
any Evidence record                    none exists
```

---

## Status

```text
AI-05-A  = FROZEN          this document
AI-05-B  = NOT STARTED
Implementation = NOT STARTED

main at freeze = b76dd681ee3f5422d87d0cae5e2a0a181353512d
```

```text
AI-02 / AI-03 / AI-04  = UNCHANGED
SecurityLab            = UNCHANGED
Router (AI-07)         = DEFERRED / UNIMPLEMENTED
```

> **AI-05 has not been implemented.** This document freezes a contract. No record
> exists, no store exists, and no component has been authorized by any of this.
