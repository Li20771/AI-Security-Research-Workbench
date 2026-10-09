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
    producer_type:   agent | service | unknown   # NOT human (§7.1)
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

**Amendment 1 added a payload-support column.** Before it, this table assigned a
kind to eight events while §11 provided no payload for two of them, so the table
asserted a recordability the contract could not deliver. The kind assignments are
unchanged; the payload column now states what v1 can actually write.

| Event | kind | producer (writes) | actor (described) | v1 payload support |
| --- | --- | --- | --- | --- |
| AI-02 provider probe | `OBSERVATION` | AI-02 | service | ADMITTED |
| AI-02 capability observation | `OBSERVATION` | AI-02 | service | ADMITTED |
| AI-03 context read | `OBSERVATION` | AI-03 | service | ADMITTED |
| AI-04 Guard decision | `DECISION` | AI-04 | service | ADMITTED |
| AI-06 tool execution | `EXECUTION` | AI-06 | agent | ADMITTED |
| AI-06 test result | `EXECUTION` | AI-06 | service | ADMITTED |
| AI-07 routing decision | `DECISION` | AI-07 | service | **DEFERRED — outcome vocabulary NOT FROZEN** |
| **human approval** | **`DECISION`** | the Workbench component recording it | **human** | **DEFERRED — outcome vocabulary NOT FROZEN** |

### 6.3 Why a human approval is a DECISION

A recorded human approval is about **the human's decision**. The approval artifact
— a signed record, a ticket, a message — is evidence *of* that decision and is
carried as an artifact reference, not as the record's kind.

```text
recorded act = the human decided        -> kind = DECISION, actor.type = human
```

A record whose entire claim is "an artifact exists at location L" is a strictly
weaker `OBSERVATION` of an artifact, with `actor.type = service`. These are
different records and the kind field distinguishes them.

**This section states the conceptual classification, not a v1 representation.**
Amendment 2 makes that separation explicit, because §6.5 defers the human-approval
event and §6.6 rejects a non-service `DECISION` actor. The record described above
is therefore classified here and is **not representable in v1**:

```text
conceptual classification   human approval = DECISION + actor.type = human
v1 admitted event           NONE — the event is DEFERRED (§6.5, producer NONE)
a v1 record carrying it     DECISION + actor.type = human  ->  REJECTED (§6.6)
```

The classification is not withdrawn, and §6.5 already says as much: what is
deferred is the **outcome vocabulary** and the admitted representation, never the
kind. When a future amendment makes the event representable it is a `DECISION`,
never an `OBSERVATION`.

The approval artifact — a signed record, a ticket, a message — may still exist
outside AI-05, and an admitted record may reference it as an artifact. What v1
cannot carry is a record whose claim **is** the human's decision. The artifact is
evidence *of* the approval held elsewhere, not an AI-05 record *of* it, which is
the distinction this section exists to draw.

### 6.4 Kinds that must not be added

```text
CAPABILITY_OBSERVATION   the payload differs, not the act
TEST                     a test run is an EXECUTION
CONTEXT_READ             an OBSERVATION with a context payload
ROUTING                  a DECISION; and AI-07 is DEFERRED
APPROVAL                 a DECISION whose actor is human
```

### 6.5 The v1 admitted-producer registry — FROZEN (Amendment 1)

Exactly six admitted events. No seventh event exists in v1.

| # | admitted event | kind | family | producer | producer_type | actor.type |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | AI-03 context read | `OBSERVATION` | `SOURCE_READ` | `ai-03` | `service` | `service` |
| 2 | AI-02 provider probe | `OBSERVATION` | `PROVIDER_PROBE` | `ai-02` | `service` | `service` |
| 3 | AI-02 capability observation | `OBSERVATION` | `CAPABILITY_OBSERVATION` | `ai-02` | `service` | `service` |
| 4 | AI-04 Guard decision | `DECISION` | none | `ai-04` | `service` | `service` |
| 5 | AI-06 tool execution | `EXECUTION` | none | `ai-06` | `service` | `agent` |
| 6 | AI-06 test result | `EXECUTION` | none | `ai-06` | `service` | `service` |

```text
The event-to-component MAPPING is CONTRACT-REQUIRED: §6.2's producer and actor
columns already state which component writes which event, and this table
transcribes them.

The producer token SPELLINGS are IMPLEMENTATION-CHOSEN and are FROZEN by
Amendment 1. No frozen serialized producer token exists anywhere in the
repository, so the amendment freezes a set rather than leaving every producer
rule uncheckable.

The registry is keyed by admitted event and family. A token registered for one
event is not thereby valid for another.

The registry constrains v1 ADMITTED RECORDS. It is not the permanent set of
Workbench components. Adding an event, a producer or a token is an amendment.
```

**The two deferred events are not representable in v1.**

| deferred event | kind | family | producer | payload | reserved field | discriminator | reserved interface |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AI-07 routing decision | `DECISION` | none | NONE | DEFERRED | none | none | none |
| human approval | `DECISION` | none | NONE | DEFERRED | none | none | none |

Neither gains a placeholder token, a discriminator, a reserved field or an
interface reservation. §6.2's kind assignment stands: when either becomes
representable it is a `DECISION`, never an `OBSERVATION`. What is deferred is the
**outcome vocabulary**, not the classification.

### 6.6 Cross-field rejection rules — FROZEN (Amendment 1)

| rule | outcome |
| --- | --- |
| `producer` is not the token registered for this kind and family | REJECTED |
| `producer_type` is not a member of `ProducerType` (§7.1) | REJECTED |
| kind is `DECISION` and `actor.type` is not `service` | REJECTED |
| kind is `OBSERVATION` and `actor.type` is not `service` | REJECTED |
| kind is `EXECUTION` and `actor.type` is neither `agent` nor `service` | REJECTED |
| kind is `DECISION` and `decision` is not a `GuardDecision` member | REJECTED |
| kind is `OBSERVATION` and the status field is not its family's | REJECTED |
| kind is `OBSERVATION` and the binding arm is not its family's | REJECTED |
| a `payload.tool_calls[]` ordinal is duplicated | REJECTED |
| `payload.reasons[]` contains a duplicate element | REJECTED |
| `artifacts.items[]` contains a duplicate `artifact_digest` | REJECTED |

Rejected by construction from §6.5: `ai-02` used for a `DECISION`; `ai-04` used for
an `OBSERVATION`; `ai-06` used for a `DECISION`; `ai-03` used for an `EXECUTION`;
`ai-02` used for an `OBSERVATION` whose family is `SOURCE_READ`; and any token
absent from the registry.

The DECISION row is what closes the Guard producer alias: producer,
`producer_type`, `actor.type` and `decision` together are the whole of §6.2's Guard
row, and no other row may produce that combination. Without it, any service
producer carrying an `ALLOW` decision could be read as an AI-04 Guard decision, and
a human approval could be recorded in `GuardDecision`'s vocabulary.

### 6.7 The ObservationFamily vocabulary — FROZEN (Amendment 1)

`ObservationFamily` is a closed vocabulary owned by AI-05. **It is declared here,
once.** §6.5, §11 and §15.2 use it and do not restate its members; a member set
appearing anywhere else in this contract is a defect in this contract, and this
section is the authority.

```text
ObservationFamily — closed, owned by AI-05, frozen by Amendment 1

    SOURCE_READ
    PROVIDER_PROBE
    CAPABILITY_OBSERVATION
```

```text
Exactly these three members in AI-05 v1.
There is no fourth member and no implicit member.
Any value outside these three is REJECTED, never treated as an ordinary value
  (§11's unlisted-enum rule).
A fourth member requires an amendment, on the same footing as a fourth
  EvidenceKind (§6.4).
```

`family` is REQUIRED on every `OBSERVATION`, and absent from `DECISION` and
`EXECUTION`.

The `none` that appears in §6.5's `family` column on the DECISION and EXECUTION
rows is a statement that the field is not applicable to that kind. **It is not a
member of this vocabulary and is never a legal value.**

The family selects the binding arm and the status field of an `OBSERVATION`, and
the selection is never inferred from a producer name (§11).

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

### 7.1 Vocabulary and role constraint — FROZEN

**Amendment 1 gave `producer_type` its own vocabulary.** Before it, this section
described `producer_type` as a narrower use of AI-04's `ActorType`, which made the
producer role a constraint on another component's type rather than a type in its
own right. The two vocabularies are now distinct, and **`producer_type` does not use
`ActorType`**.

```text
ProducerType — closed, owned by AI-05, frozen by Amendment 1
    agent
    service
    unknown

ActorType — AI-04's, imported unchanged and NOT redefined
    human
    agent
    service
    unknown
```

```text
producer_type  MUST be a member of ProducerType
actor.type     MUST be a member of ActorType
```

**Why this is a separate type rather than a constraint.** `human` is not reachable
in the producer role: the producer is the component that **wrote** the record, so a
human producer would mean a human authoring an EvidenceRecord directly, which §7
forbids. Expressing that as "`ActorType` minus `human`" makes the producer
vocabulary a function of a type AI-05 does not own, and it left
`producer = human, producer_type = human` schema-legal while the prose forbade it.
A closed three-member type admits no such state.

FORBIDDEN:

```text
producer_type = human     REJECTED (§30)
```

PERMITTED, and the reason the constraint is narrow rather than a blanket ban on the
member:

```text
ActorType.HUMAN           the member remains in the inherited vocabulary; AI-05
                          imports the type and does not remove a member (§3)
actor.type = human        REJECTED on a v1 record (§6.6) — the human-approval event
                          is deferred, so no admitted event describes a human act
                          (§6.5)
```

Both halves are load-bearing. The producer constraint is narrow because it is a
statement about the **producer role**, not about the word `human`: the member is
untouched in the type AI-05 imported, and what refuses it in the actor role is the
v1 admission boundary rather than a vocabulary edit. Removing `human` from
`ActorType` would answer the same question by damaging a frozen type AI-05 does not
own, which is the failure this section exists to avoid.

Amendment 2 corrected this block. It previously read `actor.type = human -> ACCEPTED`,
citing §6.3, which §6.5 and §6.6 do not permit.

**A record with no producer is not a record.** Provenance is never fabricated: a
record claiming an observation that no producer made would be a false record.

### 7.2 Producer and submitter are different roles — FROZEN (Amendment 4)

> **IN FORCE — Amendment 4, merged as PR #80
> (`03d42681cb8b2110773654822655117daea44ad5`).** This section is FROZEN as
> written, and the text below is unchanged by that activation. The activation
> condition §34.3 recorded for this amendment has been met. See §34.3 for the
> record.

Two roles take part in one admitted record, and they are not the same role.

```text
producer    the Workbench component RESPONSIBLE FOR THE CONTENT of the event the
            record describes — the component that supplies the semantic content
            of that event's claim.
submitter   the caller that hands an already prepared record to an AI-05
            admission entry point: `admit()` or `admit_to_store()`.
```

`WROTE`, where §7 and §5.1's field comment use the word, is given the first of
those meanings **by this amendment**. It names the ATTRIBUTION of the event's
claim to the component that supplies its semantic content, and it is not, by
itself, a statement about which code called admission or the storage API.

```text
RECORDED — THIS IS A CHOICE AMENDMENT 4 MAKES, AND IT SAYS SO.
        The original wording did NOT distinguish the component that authors an
        event's claim from the caller that submits the record. Some of §7's own
        examples, and §6.2's row for the human-approval event, are CONSISTENT
        with the choice made here, and §7's closing rule — "a record with no
        producer is not a record" — points the same way. That is why the choice
        is defensible.
        It is NOT evidence that the contract already entailed it uniquely, and
        this amendment does not claim that it did.
        The counter-evidence is on the record: AI-08 §13.1 reads WROTE the other
        way and refused to write under `ai-06` on that basis, and AI-15 recorded
        the question as an OPEN item rather than as settled text.
```

```text
FROZEN: a submitter MAY differ from the producer named on the record. That
        relationship is not a defect in the record, and §6.2's mapping, §6.5's
        registry and §6.6's rejection rules are each written to be satisfied
        either way.
FROZEN: a submitter differing from the producer does NOT make the producer
        claim true, and does NOT make it false. Whether a claim is trustworthy
        is a DIFFERENT question, and this section does not answer it.
FROZEN: calling `admit()` or `admit_to_store()` does NOT by itself confer the
        PRODUCER role on the caller. Submitting is not producing. The producer
        named on a record is the component §7 defines, whether or not that
        component performed the call.
FROZEN: THREE DIFFERENT CHECKS, AND §6.5 IS ONLY THE FIRST OF THEM.

            registry and cross-field        whether this producer token APPLIES
              validation                      to this record's kind and family,
                                              plus the §6.6 type constraints.
                                              This IS a real constraint: a token
                                              registered for one event is not
                                              valid for another (§6.5), and a
                                              mismatched producer_type or
                                              actor.type is REJECTED (§6.6)
            producer                        whether the claim actually came
              AUTHENTICATION                  from the component it names.
                                              AI-05 v1 does NOT do this, and
                                              this section does not add it
            submitter IDENTITY              who called the admission entry
                                              point. The API does not establish
                                              it: `admit()` and
                                              `admit_to_store()` take no
                                              submitter identity
        §6.5 CONSTRAINS THE FIRST. It neither implies, proves nor substitutes for
        the second or the third, and the three MUST NOT be conflated. A caller
        that reports a registered token has reported a token that APPLIES to
        that kind and family, and nothing more.
FROZEN: no clause of this contract may be read as declaring a producer claim
        AUTHENTICATED. AI-05 v1 admits a record whose producer token is the one
        §6.5 registers for its kind and family. It does not certify who supplied
        the record, and it makes no claim that it did.
```

§7's three worked examples are read under this section, and none of them changes:

```text
"A human approves"    producer = the component that RECORDED it (§7). Under this
                      section that component is the one responsible for the
                      claim about the human's decision: it authored the record
                      of that decision. It is the producer whether or not some
                      other caller hands the record in. §6.2's row states the
                      same role in the same words — "the Workbench component
                      recording it" — and the event remains DEFERRED with
                      producer NONE (§6.5).
"Guard decides"       producer = AI-04, because AI-04 supplies the claim.
"A probe observes"    producer = AI-02, for the same reason.
```

```text
FROZEN: this section adds no field, no vocabulary member, no registry row, no
        token and no admission outcome. It adds NORMATIVE TEXT and nothing
        else: a recorded clarification of what this contract means, chosen
        deliberately by Amendment 4.
FROZEN: it is NOT a claim that the existing implementation already has producer
        authentication, and NOT a claim that §6.5 and §6.6 already enforced this
        reading. They enforce token applicability, kind and family, and the
        field type constraints — which they enforced before this section and
        still do. Whether a producer claim is trustworthy remains OPEN, and
        this section does not close it.
```

---

## 8. Identity Model

FROZEN. Six fields, six **different** jobs. Conflating any two is a defect.

```text
role                 field             property
identity             evidence_id       unique per record; opaque; AI-05-generated
correlation          experiment_id     groups records; NOT unique; OPERATIONAL (§8.4)
semantic equivalence content_digest    equal <=> same normalized claim
record integrity     record_digest     detects alteration of the stored record
artifact integrity   artifact_digest   detects alteration of the artifact bytes
artifact location    artifact_ref      opaque locator
```

### 8.1 evidence_id

```text
AI-05-GENERATED at admission
opaque, "ev-" followed by exactly 16 lowercase hex characters   (Amendment 1)
NEVER content-derived
NEVER caller-supplied
NEVER in content_digest
in record_digest
grammar G-EVIDENCE-ID (§14.9)
```

**Amendment 1 fixed the width.** Before it this section said `ev-<hex>` and gave no
length, so `record_ref` validation had nothing to validate against. The width is
**AI-05's own representation choice**, not an AI-04 contract requirement: AI-04's
contract fixes no width, and its implementation uses `uuid4().hex[:16]` for
`decision_id`, which is the only precedent and is an implementation one.

Generation follows AI-04's `decision_id` precedent: a generated runtime identifier
that is never part of a semantic digest. Because **AI-05 assigns it**, a
caller-supplied value in this field is `REJECTED` (§30), and a collision is
`REJECTED` defensively.

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

### 8.4 experiment_id is OPERATIONAL — FROZEN

```text
experiment_id is correlation metadata.
It is NOT identity.
It is NOT part of the semantic claim.
It is EXCLUDED from content_digest.
It IS included in record_digest.
```

The acid test from §15.1 — *would two records differing only in this field be
evidence of different facts?* — answers **no**. Which human task a record was filed
under does not change what the record claims about the world.

Repository precedent, decisive: AI-02 §7.4 defines `experiment_id` inside
`RequestMetadata` and describes that type as *"Workbench bookkeeping, not prompt
content. It never carries secrets or prompt bodies."* AI-02 §9.4 repeats it: the
metadata is never acted on and no field of it may drive behaviour. AI-00 §9 places
`experiment_id` in the Experiment Record as a label — `EXP-YYYYMMDD-XXXX` — not as a
semantic component.

FROZEN consequences:

```text
same normalized claim, different experiment_id
    ->  SAME content_digest
    ->  DIFFERENT record_digest
```

Both records are `ACCEPTED`. They are one claim recorded twice under two task
labels, and the store MUST be able to say so. Including `experiment_id` in
`content_digest` would destroy exactly that statement.

> **This CORRECTS the freeze revision.** §15.2 previously listed `experiment_id` as
> included in `content_digest`, which contradicted §8's "correlation only". The
> exclusion is now frozen and §15.2, §15.5, §16, T7 and T29 are aligned to it.

---

## 9. Provenance

FROZEN. Provenance answers "who, where, when" for every record.

```text
producer          which component wrote the record
producer_version  its version
producer_type     agent | service | unknown        (§7.1 — human is not a valid role here)
actor             the entity whose act is described
workspace_id      the scope of the whole record          REQUIRED, non-empty
experiment_id     correlation label                      optional
observed_at       when the claimed act happened          per kind (§10)
recorded_at       when the record was written            operational
```

**Semantic vs operational classification lives in exactly one place: the §15.2
authoritative field table.** This section names the fields and their mandatory-ness;
it does not restate their digest membership, so the two cannot drift apart.

```text
producer            SEMANTIC      (§15.2.2)
producer_version    OPERATIONAL   (§15.2.2)
producer_type       SEMANTIC
experiment_id       OPERATIONAL   (§8.4)
recorded_at         OPERATIONAL
observed_at         per kind      (§10.2)
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

**Syntax, which is a separate question from the classification above
(Amendment 1).** The table decides *which* timestamps are semantic. It says nothing
about their form, and the two must not be conflated:

```text
observed_at and recorded_at, when a value is present, MUST be ISO-8601 UTC with a
trailing Z at second resolution.   grammar G-TIMESTAMP (§14.9)
```

The rule applies to those two fields and to no others. It is REPOSITORY-DERIVED:
`plugins/context/context.py` `utc_now()` emits exactly this form, and AI-02's
`live_verification` uses second resolution.

Null, per kind, and not a matter of syntax:

```text
OBSERVATION   observed_at REQUIRED and non-null
EXECUTION     observed_at REQUIRED and non-null
DECISION      observed_at OPTIONAL; the projection emits null, never omits the key
recorded_at   REQUIRED and non-null for every kind; AI-05 stamps it
```

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

**Amendment 1 declared the fields.** Before it, this section named the fields in
prose and satisfied none of its own three requirements: no field was declared, no
class was assigned, and no field carried a semantic or operational mark. §15.2 now
carries the complete leaf table, with every field's class, grammar, role, digest
membership and origin.

```text
OBSERVATION
    subject          string             REQUIRED   Class 3
    family           ObservationFamily  REQUIRED   Class 2
    binding          WorkspaceBinding or ProviderBinding
                                        REQUIRED   arm selected by family
    observed         string             REQUIRED   Class 4
    plus, per family:
        SOURCE_READ              read_status       SourceReadStatus   REQUIRED
        PROVIDER_PROBE           run_status        LiveRunStatus      REQUIRED
        CAPABILITY_OBSERVATION   outcome           ProbeOutcome       REQUIRED
                                 candidate_status  CapabilityStatus  REQUIRED

DECISION
    decision         GuardDecision      REQUIRED   Class 2
    reason_code      string             REQUIRED   Class 3
    reasons          string[]           OPTIONAL   Class 4, SET
    input_digest     string             REQUIRED   Class 1, 64 lowercase hex

EXECUTION
    tool_calls                       ToolCall[]  OPTIONAL   ORDER by ordinal
        ordinal                      int         REQUIRED   Class n/a
        what_ran                     string      REQUIRED   Class 4
        status                       StatusValue REQUIRED   Class 2
        result_classification        DEFERRED — MUST BE ABSENT IN V1
```

A status field belonging to a family other than the record's own is REJECTED. The
binding arm is selected by `family` and is never inferred from a producer name.

```text
WorkspaceBinding                       ProviderBinding
    source_kind      SourceKind  REQ       model_ref      string  REQ
    source_identity  string      REQ       endpoint_host  string? optional
    source_revision  string      REQ       capability     CapabilityName? optional
```

**DECISION admits one arm in v1.** Routing decisions and human approvals are
classified as `DECISION` by §6.2 and their payload outcome vocabularies are NOT
FROZEN, so neither arm is representable in v1. See §6.5.

Rules:

```text
the payload has NO free-form map field
every field is declared; an undeclared field is REJECTED (§30)
every string field belongs to a declared class (§14.2) and a declared grammar (§14.9)
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

**The conditional source revision rule — FROZEN (Amendment 1).**

One rule, applied identically to both paths that carry a source revision:

```text
payload.binding.source_revision
references.context[].source_revision
```

| `source_kind` | required revision |
| --- | --- |
| `GIT_CURRENT_STATE` | exactly 40 lowercase hexadecimal characters |
| `GIT_HISTORY` | exactly 40 lowercase hexadecimal characters |
| `MASTER_ROADMAP` | exactly 64 lowercase hexadecimal characters |
| `CAPABILITY_INVENTORY` | exactly 64 lowercase hexadecimal characters |
| `DESIGN_FREEZE` | exactly 64 lowercase hexadecimal characters |
| `EXIT_REPORT` | exactly 64 lowercase hexadecimal characters |
| any other value | REJECTED, because `SourceKind` is closed and those are its only six members |

```text
This is a CONTRACT-LEVEL CONDITIONAL GRAMMAR RULE, not a runtime inference and not
something a producer may determine. grammar G-REVISION (§14.9).

The same source_kind and revision pair MUST produce the same accept or reject
result on both paths.

REPOSITORY-DERIVED: AI-03 §7.1 states that a git source's revision is the commit SHA
the read describes and a document source's revision is the SHA-256 digest of the
file content read. plugins/context/sources.py implements both.
```

`source_kind` MUST use AI-03's `SourceKind`, `item_kind` MUST use AI-03's `ItemKind`,
`truth_state` MUST use AI-03's `StatusValue`, and `freshness` MUST use AI-03's
`Freshness`. No arbitrary string is accepted in any of the four.

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
role               DEFERRED     MUST BE ABSENT IN V1   (Amendment 1)
external           SEMANTIC     included in both
owner_workspace_id SEMANTIC     included in both
artifact_ref       OPERATIONAL  EXCLUDED from content_digest, included in record_digest
availability       RUNTIME      NOT an Evidence field at all
```

**`role` is deferred (Amendment 1).** It was declared here as a closed vocabulary
with no members enumerated anywhere, so the requirement could not be satisfied and
the field could not be validated. It is now a closed vocabulary whose members are
**not yet frozen**, and `role` MUST BE ABSENT in v1: a record carrying it is
REJECTED. Reintroducing it requires a further amendment that freezes its members.
No closed vocabulary for `role` is created by Amendment 1.

**`artifact_ref` is an opaque identifier, never a path.** The id-to-location mapping
is a store-side concern. Because it is opaque, relocation cannot change it, and
promotion alters no field (§20.3). Its grammar is `G-LOCATOR` (§14.9): bounded,
single-line, and otherwise uninterpreted. AI-05 never resolves it and never parses
it, and this contract does not enforce "never a path" lexically — that sentence
describes AI-05's behaviour.

### 13.2 Collection rules — FROZEN

```text
ordering    SET-semantic, canonical order = artifact_digest      (Amendment 1)
uniqueness  artifact_digest unique within a record
            a second entry with the same digest is a DUPLICATE -> REJECT
ordering MUST NOT use artifact_ref   — it is a locator, not an ordering input
```

**Amendment 1 narrowed the key.** It was `(role, artifact_digest)`. `role` MUST BE
ABSENT in v1, so the pair degenerates to `artifact_digest` alone. No key is added
and none is removed; the degenerate case is stated so that it is not mistaken for a
silent simplification.

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

### 13.7 The one-directional relationship — FROZEN

```text
RAW BYTES
    |
    |  the PRODUCER owns storage
    v
artifact storage                 (outside AI-05)
    |
    |  the PRODUCER supplies ref + digest
    v
AI-05 EvidenceRecord
    |
    +--> artifact_ref
    +--> artifact_digest
    +--> external / owner_workspace_id
    (role is DEFERRED and MUST BE ABSENT in v1 — §13.1, Amendment 1)
```

**NOT:**

```text
RAW BYTES
    |
    v
AI-05
    |
    +--> sanitize        FORBIDDEN
    +--> store           FORBIDDEN
    +--> digest          FORBIDDEN
```

```text
AI-05 does not own the raw artifact lifecycle.
```

### 13.8 AI-05 never converts content into an artifact — FROZEN

```text
raw content supplied to AI-05
    -> AI-05 turns it into an artifact          FORBIDDEN
```

Such a conversion would be an implicit transformation: AI-05 would decide that
supplied content is an artifact, choose to retain it, and compute its digest. That
violates three already-frozen rules at once — AI-05 never sanitizes (§14.4.1), never
substitutes a value (§30.1), and never changes the recorded fact (§19).

The correct sequence is a **producer** action, not an admission behaviour:

```text
1. the caller holds the raw bytes
2. the CALLER stores them outside AI-05 and computes their digest
3. the caller submits a record carrying artifact_digest and artifact_ref
4. AI-05 admits the REFERENCE (§13.1, §13.2). It never sees the bytes.
```

A record that arrives carrying raw content in a field the contract does not define is
`REJECTED` (§30) — it is not quietly reshaped into an artifact reference. Rejecting
is loud; reshaping is silent, and a caller that believed it had submitted an artifact
would never learn otherwise.

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

Every string field belongs to exactly one declared class. **Amendment 1 restated
Class 3 and Class 4**; the other three are unchanged.

```text
Class 1  structural
    A digest or a revision. Lowercase hexadecimal, exact length.

Class 2  vocabulary
    A member of a named closed enum.

Class 3  structured machine token
    A bounded string whose interpretation is defined by a field-specific grammar
    (§14.9). AI-05 shape-validates it. AI-05 never normalizes it and never
    substitutes it; a non-conforming value is REJECTED.
    Class 3 does NOT imply that every field in it is semantically an identifier.

Class 4  bounded producer-normalized text
    A single line, length-capped, newline-flattened by the PRODUCER, and subject
    to the published admission rule set. AI-05 validates and rejects a malformed
    admission value. AI-05 performs no substitution and no sanitization.

Class 5  free text
    FORBIDDEN. Does not exist in the schema.
```

A caller holding an arbitrary string **has no field to put it in.**

**AI-05 MUST NOT perform sanitization on any class.** It checks a value's shape
against the declared grammar and admits or rejects it. AI-05 never rewrites an
accepted value, in Class 3, Class 4 or anywhere else.

**Class 3 is not a claim about secret provenance.** AI-05 does not assert that any
Class 3 field passed through `providers/redaction.py`, and does not depend on that
being true. Where an upstream contract requires pre-sanitization, that contract owns
the responsibility and this one does not restate it.

**Class 4's division of responsibility.** The producer normalizes and flattens
newlines before submission. AI-05 **rejects** a value containing CR or LF rather
than flattening it, because flattening would be the silent substitution §14.4.1
forbids.

**The published admission rule set is C-1, and Amendment 3 PUBLISHES it (§14.10).**
Every Class 3 and Class 4 field is now rule-checked at admission, in addition to
being structurally bounded. Before Amendment 3 this paragraph said the rule set
"remains DEFERRED, so every Class 4 field is structurally bounded and not
rule-checked"; that sentence is superseded, and the rule set it deferred is
normatively defined in §14.10.

### 14.9 The grammar table — FROZEN

**Amendment 1 added this section.** Each name is defined exactly once and is used by
the §15.2 leaf table. No alias exists.

| grammar | definition | origin |
| --- | --- | --- |
| `G-EVIDENCE-ID` | the pattern `^ev-[0-9a-f]{16}$` | IMPLEMENTATION-CHOSEN |
| `G-DIGEST` | exactly 64 lowercase hexadecimal characters | REPOSITORY-DERIVED |
| `G-IDENT` | the pattern `^[A-Za-z0-9._-]{1,64}$` | IMPLEMENTATION-CHOSEN |
| `G-SUBJECT` | non-empty, single-line, at most 256 characters, otherwise uninterpreted | IMPLEMENTATION-CHOSEN |
| `G-OPAQUE-ID` | non-empty, single-line, at most 512 characters, no CR, no LF, otherwise uninterpreted | IMPLEMENTATION-CHOSEN |
| `G-HOST` | non-empty, single-line, lowercase, containing none of the characters at-sign, colon, slash or whitespace, at most 253 characters | IMPLEMENTATION-CHOSEN |
| `G-MODELREF` | `PROVIDER_ID_RE` followed by exactly one slash followed by `MODEL_ID_RE` | REPOSITORY-DERIVED |
| `G-REVISION` | conditional on `source_kind` as stated in §12.1 | REPOSITORY-DERIVED |
| `G-TIMESTAMP` | ISO-8601 UTC with a trailing `Z`, at second resolution | REPOSITORY-DERIVED |
| `G-LOCATOR` | non-empty when present, single-line, at most 512 characters, no CR, no LF, otherwise uninterpreted by AI-05 | IMPLEMENTATION-CHOSEN |
| `G-TEXT` | single-line bounded producer-normalized text, at most 512 characters, no CR, no LF. The producer performs normalization and newline flattening. AI-05 validates and rejects malformed input and performs no substitution and no sanitization | shape IMPLEMENTATION-CHOSEN; admission rule-set obligation CONTRACT-REQUIRED and **PUBLISHED by Amendment 3 (§14.10)** |
| `G-REGISTERED` | the token admitted by §6.5 for the current kind and family | registry requirement CONTRACT-REQUIRED, token spelling IMPLEMENTATION-CHOSEN |
| `G-ORDINAL` | an integer greater than or equal to 0, unique within `payload.tool_calls[]`, not required to be contiguous | IMPLEMENTATION-CHOSEN |

### 14.10 The published admission rule set — FROZEN (Amendment 3)

**This section PUBLISHES the rule set that §30 step 7, §14.2 and the `G-TEXT` row
above refer to as C-1.** Before Amendment 3 the contract named it and deferred it;
the companion records (`AI-05-B2_DECISIONS_2026-10-01.md` D1, the B1 evidence, the
project status) recorded the same. It is now defined here, and this section is the
normative source.

```text
FROZEN: AI-05 owns the published admission rule set. It is exactly the six rules
        below; a seventh is an amendment (§34.1), never a configuration change.

FROZEN: the patterns are a FROZEN SNAPSHOT of the six credential-detection patterns
        the repository's upstream sanitizer applies to provider-bound text. They are
        TRANSCRIBED, never imported: an edit to that sanitizer MUST NOT change what
        AI-05 admits, and changing this rule set requires a further amendment. The
        snapshot was taken at main 7e7d83b74e2903f2b83e95cf35d0115d4038df90.

FROZEN: DETECTION ONLY. A rule answers "does this value match". No rule carries a
        replacement, AI-05 holds none, and AI-05 never substitutes, redacts,
        sanitizes or normalizes a value (§14.4.1). The substitution half stays
        upstream.

FROZEN: no exact-secret list and no secret registry. AI-05 holds no caller secret
        and reads no credential store. Exact-VALUE substitution is an upstream
        capture/sanitization operation and is not representable in this contract.

FROZEN: no rule-set version field, on a record or anywhere else. The rule set is
        versioned by AMENDMENT. A version field would invite an admission decision
        to depend on which revision wrote the record.

FROZEN: NOTHING HERE IS RETROACTIVE. These rules are checked at NEW admission only.
        A record already written stays readable; no re-admission, no stored-form
        load and no future amendment applies a later rule set to it (§17, §20).
```

```text
rule id   pattern                                                    catches
C1-R01    (?i)\bauthorization\b\s*[:=]\s*\S+                          Authorization header
C1-R02    (?i)\b(api[_-]?key|apikey|access[_-]?token|                  key=value credential
          refresh[_-]?token|auth[_-]?token|bearer|token|              parameters
          secret|password|passwd|pwd)\b\s*[:=]\s*["']?([^\s"',;}\]]+)
C1-R03    \bsk-[A-Za-z0-9_\-]{8,}                                       vendor "sk-" token
C1-R04    \b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}                     GitHub token prefix
C1-R05    \bxox[baprs]-[A-Za-z0-9\-]{10,}                              Slack token prefix
C1-R06    \b[A-Za-z0-9_\-]{32,}\b                                     long opaque token

FROZEN: the rule ids, their order and their patterns are the published contract.
        A rule is matched with `search` semantics wherever it applies, and the
        FIRST matching rule in the order above is the one reported.
```

```text
WHERE THE RULES APPLY — every CALLER-SUPPLIED Class 3 and Class 4 field, plus one
admission-only input, and nothing else. Paths are §15.2's; the scan reads the
supplied mapping, where the provenance leaves appear under `provenance.`:

Class 3 (§15.2 class 3)          producer, producer_version, workspace_id,
                                 experiment_id, observed_at, payload.subject,
                                 payload.binding.source_identity,
                                 payload.binding.model_ref,
                                 payload.binding.endpoint_host, payload.reason_code,
                                 references.context[].workspace_id,
                                 references.context[].source_identity,
                                 references.context[].subject,
                                 references.decisions[].record_ref,
                                 references.supersedes[].record_ref,
                                 artifacts.items[].owner_workspace_id,
                                 artifacts.items[].artifact_ref
Class 4 (§15.2 class 4)          actor.id, payload.observed, payload.reasons[],
                                 payload.tool_calls[].what_ran,
                                 references.supersedes[].correction_reason

ADMISSION-ONLY, and NOT a        references.context[].value
  §15.2 leaf

Class 1                          NEVER scanned. A digest or a revision is lowercase
                                 hex of an exact length, and rule C1-R06 would match
                                 every one of them: a 40-character commit SHA and a
                                 64-character SHA-256 are both 32+ character runs.
                                 Applying the rules to a structural field would
                                 reject every legitimate record (T20a, T20b).
Class 2                          validated against its closed enum and not scanned.
```

```text
FROZEN: the classes above are §15.2's own `class` column, quoted rather than assigned
        here. §15.2 is the single source of truth for a field's class, and a
        classification stated anywhere else — this section included — is a defect in
        this document. `producer` is class 3 with grammar G-REGISTERED because §15.2
        says so; the implementation additionally applies a G-TEXT shape bound to it,
        and that does not move it.

FROZEN: `references.context[].value` is an ADMISSION-ONLY SUPPLIED INPUT, and it is
        the one scanned path with no §15.2 row. It exists only in the supplied form:
        `ContextRef.from_mapping` derives `value_digest` from it (§12.1), and the raw
        value is NEVER persisted and never rendered (§12.4). It is therefore not a
        stored leaf, and it MUST NOT be added to §15.2, to the stored form or to the
        implementation's field table. It is G-TEXT-shaped, and step 7 reads it BEFORE
        that derivation — which is both what R2 requires and why step 7 runs where it
        does. A reader must not have to derive this boundary; it is stated here.

FROZEN: Class 3 and Class 4 are both scanned, so a field's class never decides
        WHETHER it is checked — only Class 1 and Class 2 are exempt, and §15.2's
        `origin` column decides the rest: a field AI-05 GENERATES (`evidence_id`,
        `recorded_at`) is not a caller-supplied value and is not scanned.
```

```text
FROZEN: a value matching any published rule is REJECTED
        (reason ADMISSION_RULE_VIOLATION). It is never sanitized, never truncated,
        never replaced and never repaired, and no digest is computed over it (§14.6
        R2) — which is why step 7 reads the SUPPLIED values before the record is
        constructed, since construction derives references.context[].value_digest
        from the supplied value (§12.1).

FROZEN: this rule set is a DETECTOR, not a completeness claim. §14.1's limit stands
        unchanged: a secret that matches no rule passes, and §14.8 keeps the
        residual stated rather than closed.

CONSEQUENCE, declared: a legitimate 64-character lowercase hex value in a Class 4
        field matches C1-R06 and is REJECTED (T20c). That is deliberate
        over-rejection in the safe direction; a kind needing to carry such a value
        MUST declare the field Class 1. It MUST NOT be "fixed" by widening a rule.
```

---


Evidence for the REPOSITORY-DERIVED labels:

```text
G-DIGEST
    §20.2 of the AI-04 contract fixes the digest representation as lowercase
    hexadecimal. plugins/guard/digest.py sha256_hex emits exactly 64 characters.

G-MODELREF
    providers/profile.py line 27 defines PROVIDER_ID_RE
    providers/model_profile.py line 41 defines MODEL_ID_RE
    providers/profile.py ModelRef.parse requires exactly one slash
    The composition is AI-02's. AI-05 does not redefine model identity. A
    model_ref that AI-02 accepts, AI-05 MUST NOT reject.

G-REVISION
    AI-03 §7.1: a git source's revision is the commit SHA the read describes; a
    document source's revision is the SHA-256 digest of the file content read.

G-TIMESTAMP
    plugins/context/context.py utc_now emits isoformat at second resolution with
    the offset replaced by Z.
```

Two notes, recorded rather than left implicit:

```text
G-HOST
    The exclusion of userinfo, port and uppercase follows from AI-02's own
    endpoint_host behaviour. AI-02 states no lexical grammar, so the character
    set and the length bound are AI-05's choice. AI-02's endpoint host semantics
    are not redefined.

G-OPAQUE-ID and G-LOCATOR
    These two define identical shapes today. They are named separately because
    their semantic roles differ, an identity versus a locator. They are not
    claimed to differ today.
```

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
admission            AI-05 — structural, plus the published rule set
modification         AI-05 NEVER alters a value. Evidence is not the layer that
                     rewrites a fact.
```

AI-05 **may** reject content that violates the published admission rule set. It does
**not** sanitize, redact, or substitute.

### 14.4.1 Two operations over one rule set — FROZEN

The repository's sanitizer performs two operations over the same patterns. AI-05
performs **only the first**.

```text
operation                     owner          AI-05
detection   "does this value    both           YES — at admission, over
             match a rule?"                    Class 3 and Class 4
substitution "what should this   UPSTREAM       NO — never, on any class
             value become?"

reuse of the rule set  !=  AI-05 owns the sanitization operation.
```

AI-05 reuses the published **rule definitions**. It does not call, wrap, or
reimplement the substitution half of the sanitizer, and an admitted value is never
rewritten. Where `providers/redaction.py` is reused in this contract, it is reused
**by the upstream capture layer**, not by AI-05.

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
Class 1 (structural)   shape-validated (exact length, LOWERCASE hex charset).
                       NEVER scanned. A value failing the shape check is REJECTED,
                       never replaced.
Class 2 (vocabulary)   validated against the enum. A value outside it is REJECTED.
Class 3 (identifier)   validated as an identifier. The value arrives PRE-SANITIZED
                       from upstream — because an id can be identifier-shaped and
                       secret-shaped at once, which AI-02 already states and already
                       handles both ways. AI-05 checks the shape; it does not
                       sanitize (§14.4.1).
Class 4 (bounded)      the full rule set, plus length cap and newline flattening.
```

### 14.5.1 Case policy for structural fields — FROZEN

**Uppercase hexadecimal in a Class 1 field is `REJECTED` as non-canonical.**

Option A (accept and normalize to lowercase) is **FORBIDDEN**, because normalizing
means *substituting an accepted value* — which §14.4 forbids AI-05 from doing at all.
The two rules cannot both hold, and the no-substitution rule is the more fundamental
one: it is what keeps Evidence from being the layer that rewrites a fact.

```text
lowercase hex, exact length    ACCEPTED
uppercase hex                  REJECTED  (non-canonical; AI-05 will not rewrite it)
wrong length                   REJECTED
non-hex character              REJECTED
```

This matches AI-04 §20.2, which already fixes the digest representation as
**lowercase hexadecimal**, and matches what git and every digest function in this
repository emit. A producer holding an uppercase digest normalizes it **upstream**;
AI-05 does not.

**Consequence, stated so it is not a surprise:** a legitimate 64-hex value appearing
in a Class 4 bounded source field matches rule 6 and is therefore `REJECTED`. If a
record kind needs to carry such a value, that field MUST be declared Class 1. This is
deliberate over-rejection in the safe direction, not an oversight.

### 14.6 Secret-derived digests — FORBIDDEN, stated enforceably

The prohibition is real, but "sha256(secret) is forbidden anywhere" is not
enforceable, because no component can tell a digest of a secret from a digest of
anything else. It is therefore restated as three checkable rules plus the reason.

```text
FORBIDDEN — enforceable:

R1  AI-05 MUST NOT use a caller-supplied value as content_digest, record_digest or
    ContextRef.value_digest. AI-05 generates those three itself (see §14.6.1).
    A caller-supplied value in those fields is REJECTED.

R2  AI-05 MUST NOT compute a digest over a value it did not admit. A value is
    admitted only after its class rules pass (§30). AI-05 therefore never digests
    rule-tripping content, because such content is rejected before hashing.

R3  No field of an EvidenceRecord has a declared semantic role of "secret" or
    "credential". There is no field a secret-derived digest belongs in.
```

```text
The reason, recorded so the rules are not mistaken for arbitrary:

a digest of a low-entropy secret is recoverable by
    1. low-entropy enumeration   a PIN or short token falls to brute force
    2. dictionary recovery       a password from a known corpus falls to a wordlist
    3. confirmation oracle       a stored digest CONFIRMS a candidate the attacker
                                 already holds
    4. cross-record correlation  an unsalted digest links the same secret across two
                                 otherwise unrelated records

Salt or HMAC would defeat 1–3 but destroys content-equivalence — the only reason to
digest at all — and requires key management inside an evidence store, which is a
responsibility AI-05 must not take on.
```

The digest is taken over the **accepted** value. An upstream-sanitized value's digest
is a constant, which is correct: it distinguishes *sanitized* from *empty* from
*absent*.

### 14.6.1 Which digests AI-05 generates, and which it accepts — FROZEN

This is the distinction that resolves the contradiction. **Digest-shaped is not the
same as trustworthy.**

```text
field                     origin              AI-05 role
content_digest            AI-05-GENERATED     computes it from canonical admitted content
record_digest             AI-05-GENERATED     computes it over the stored record
ContextRef.value_digest   AI-05-GENERATED     computes it from an ADMITTED value
artifact_digest           CALLER-SUPPLIED     validates shape; CANNOT verify against
                                              bytes it never reads (§13.5)

A caller-supplied value in an AI-05-generated digest field   REJECTED
```

`artifact_digest` is the single exception, and it is not an exception to R1 — it is a
different field with a different declared role: **artifact-byte integrity**, not the
representation of a record's own content. It is supplied by the producer that holds
the bytes, and §14.7 governs it.

Therefore:

```text
AI-05 cannot be made to ADOPT a caller's sha256(secret) as an Evidence digest,
  because there is no field that accepts a caller-supplied digest for AI-05's own
  content, and the three fields AI-05 generates are generated from admitted content.
```

### 14.7 The artifact case, distinguished

`artifact_digest` is a digest of bytes that may contain a credential. That is
**materially different** from `sha256(secret)`: attacking it requires guessing the
whole artifact rather than a low-entropy preimage, and the bytes are outside AI-05's
boundary (§13.4). It is accepted, and AI-05 makes no claim about the artifact's
contents.

### 14.8 The residual case, stated rather than hidden

A secret that is itself exactly 64 lowercase hexadecimal characters is
indistinguishable **by shape** from a digest. The mitigation is provenance, not
shape — and the provenance differs between the two kinds of Class 1 field:

```text
content_digest, record_digest, ContextRef.value_digest
    AI-05-GENERATED from admitted canonical content.
    A caller cannot supply them (R1). The residual does not apply.

artifact_digest
    CALLER-SUPPLIED. AI-05 validates its shape and CANNOT verify it (§13.5).
    If a producer supplies a digest of a low-entropy secret here, AI-05 accepts it
    and cannot detect it.
```

The second case is a **residual AI-05 does not close**, and this contract says so
rather than implying otherwise. §14.7 governs why it is accepted: the field's
declared role is artifact-byte integrity, AI-05 makes no claim about artifact
contents, and the bytes are outside its boundary. Closing it would require AI-05 to
read bytes it must not read — trading a stated, bounded limit for a boundary
violation.

That limit MUST be stated and tested (T20c, T22d, T22e).

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

### 15.2 The authoritative field table — FROZEN

**This table is the single source of truth for digest behaviour.** Any other
statement in this document that disagrees with it is a defect in this document.
An implementation MUST NOT classify a field by any other means.

**Amendment 1 replaces the container-level table with a leaf table.** The previous
table classified `payload` and the collection containers as single rows, which could
not express a nested exclusion: `artifact_ref`'s exclusion from `content_digest`
lived in imperative code rather than in this table. Every leaf is now a row, and the
containers carry collection order only (§15.4).

Column meanings:

```text
path                    the complete dotted path of the leaf within the record
type                    the declared type
class                   the §14.2 field class, n/a for a field that is not a
                        string field, or DEFERRED
grammar                 the §14.9 grammar name, n/a, or MUST BE ABSENT IN V1
semantic/operational    the field role
content_digest          yes, no, per-kind, or is
record_digest           yes, no, or is
origin                  C for caller-supplied, A for AI-05-generated
```

| path | type | class | grammar | semantic/operational | content_digest | record_digest | origin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `evidence_id` | string | 3 | `G-EVIDENCE-ID` | identity | no | yes | A |
| `schema_version` | int | n/a | n/a | semantic | yes | yes | C |
| `kind` | enum `EvidenceKind` | 2 | n/a | semantic | yes | yes | C |
| `producer` | string | 3 | `G-REGISTERED` | semantic | yes | yes | C |
| `producer_version` | string | 3 | `G-IDENT` | operational | no | yes | C |
| `producer_type` | enum `ProducerType` | 2 | n/a | semantic | yes | yes | C |
| `actor.id` | string | 4 | `G-TEXT` | semantic | yes | yes | C |
| `actor.type` | enum `ActorType` | 2 | n/a | semantic | yes | yes | C |
| `workspace_id` | string | 3 | `G-IDENT` | semantic | yes | yes | C |
| `experiment_id` | string or null | 3 | `G-IDENT` | operational | no | yes | C |
| `observed_at` | string or null | 3 | `G-TIMESTAMP` | per-kind | per-kind | yes | C |
| `recorded_at` | string | 3 | `G-TIMESTAMP` | operational | no | yes | A |
| `payload.subject` | string | 3 | `G-SUBJECT` | semantic | yes | yes | C |
| `payload.family` | enum `ObservationFamily` | 2 | n/a | semantic | yes | yes | C |
| `payload.binding.source_kind` | enum `SourceKind` | 2 | n/a | semantic | yes | yes | C |
| `payload.binding.source_identity` | string | 3 | `G-OPAQUE-ID` | semantic | yes | yes | C |
| `payload.binding.source_revision` | string | 1 | `G-REVISION` | semantic | yes | yes | C |
| `payload.binding.model_ref` | string | 3 | `G-MODELREF` | semantic | yes | yes | C |
| `payload.binding.endpoint_host` | string or null | 3 | `G-HOST` | semantic | yes | yes | C |
| `payload.binding.capability` | enum `CapabilityName` or null | 2 | n/a | semantic | yes | yes | C |
| `payload.read_status` | enum `SourceReadStatus` | 2 | n/a | semantic | yes | yes | C |
| `payload.run_status` | enum `LiveRunStatus` | 2 | n/a | semantic | yes | yes | C |
| `payload.outcome` | enum `ProbeOutcome` | 2 | n/a | semantic | yes | yes | C |
| `payload.candidate_status` | enum `CapabilityStatus` | 2 | n/a | semantic | yes | yes | C |
| `payload.observed` | string | 4 | `G-TEXT` | semantic | yes | yes | C |
| `payload.decision` | enum `GuardDecision` | 2 | n/a | semantic | yes | yes | C |
| `payload.reason_code` | string | 3 | `G-IDENT` | semantic | yes | yes | C |
| `payload.reasons[]` | string | 4 | `G-TEXT` | semantic | yes | yes | C |
| `payload.input_digest` | string | 1 | `G-DIGEST` | semantic | yes | yes | C |
| `payload.tool_calls[].ordinal` | int | n/a | `G-ORDINAL` | semantic | yes | yes | C |
| `payload.tool_calls[].what_ran` | string | 4 | `G-TEXT` | semantic | yes | yes | C |
| `payload.tool_calls[].status` | enum `StatusValue` | 2 | n/a | semantic | yes | yes | C |
| `payload.tool_calls[].result_classification` | DEFERRED | DEFERRED | MUST BE ABSENT IN V1 | not present in v1 | not present in v1 | not present in v1 | not present in v1 |
| `references.context[].workspace_id` | string | 3 | `G-IDENT` | semantic | yes | yes | C |
| `references.context[].source_kind` | enum `SourceKind` | 2 | n/a | semantic | yes | yes | C |
| `references.context[].source_identity` | string | 3 | `G-OPAQUE-ID` | semantic | yes | yes | C |
| `references.context[].source_revision` | string | 1 | `G-REVISION` | semantic | yes | yes | C |
| `references.context[].subject` | string | 3 | `G-SUBJECT` | semantic | yes | yes | C |
| `references.context[].value_digest` | string | 1 | `G-DIGEST` | semantic | yes | yes | A |
| `references.context[].item_kind` | enum `ItemKind` | 2 | n/a | semantic | yes | yes | C |
| `references.context[].truth_state` | enum `StatusValue` | 2 | n/a | semantic | yes | yes | C |
| `references.context[].freshness` | enum `Freshness` | 2 | n/a | semantic | yes | yes | C |
| `references.decisions[].record_ref` | string | 3 | `G-EVIDENCE-ID` | semantic | yes | yes | C |
| `references.supersedes[].record_ref` | string | 3 | `G-EVIDENCE-ID` | semantic | yes | yes | C |
| `references.supersedes[].correction_reason` | string | 4 | `G-TEXT` | semantic | yes | yes | C |
| `artifacts.items[].artifact_digest` | string | 1 | `G-DIGEST` | semantic | yes | yes | C |
| `artifacts.items[].role` | DEFERRED | DEFERRED | MUST BE ABSENT IN V1 | not present in v1 | not present in v1 | not present in v1 | not present in v1 |
| `artifacts.items[].external` | bool | n/a | n/a | semantic | yes | yes | C |
| `artifacts.items[].owner_workspace_id` | string or null | 3 | `G-IDENT` | semantic | yes | yes | C |
| `artifacts.items[].artifact_ref` | string or null | 3 | `G-LOCATOR` | locator | no | yes | C |
| `content_digest` | string | 1 | `G-DIGEST` | integrity | is | yes | A |
| `record_digest` | string | 1 | `G-DIGEST` | integrity | no | is | A |

Two rows are deferred and MUST BE ABSENT IN V1:
`payload.tool_calls[].result_classification` and `artifacts.items[].role`.

```text
storage tier MUST NOT be in content_digest.
storage tier MUST NOT be in record_digest either — it is a property of where the
  bytes are, not of the bytes.
```

### 15.2.1 The two questions this table must answer

```text
same claim, different producer_version
    ->  SAME content_digest          (producer_version is OPERATIONAL)
        DIFFERENT record_digest
    reason: a version is a property of the instrument, not of the claim. A producer
            upgrade that changes normalization changes `payload`, which IS semantic,
            so the difference surfaces where it belongs instead of being
            double-counted. Including the version would make every upgrade break
            content-equivalence with all history.

same claim, different experiment_id
    ->  SAME content_digest          (experiment_id is OPERATIONAL, §8.4)
        DIFFERENT record_digest
    reason: which task a record was filed under does not change what it claims.
```

### 15.2.2 Why `producer_version` is OPERATIONAL — FROZEN

`producer` and `producer_version` are classified differently, by the same acid test
used everywhere in this contract: *would two records differing only in this field be
evidence of different facts?*

```text
producer          which component observed. A DIFFERENT observer makes DIFFERENT
                  evidence — AI-02 §8.3: "Provider documentation is not Workbench
                  evidence." Provenance is load-bearing.  SEMANTIC.
producer_version  which build of that same observer. Same observer, same claim.
                  OPERATIONAL.
```

`producer_type` is retained as SEMANTIC even though it is derivable from `producer`,
so that the semantic projection is self-describing without a lookup table. That
redundancy is deliberate and is the only one in the table.

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
declared here. **Amendment 1 merged this table into §15.2**, so a collection's order
and its leaves are declared in one document; this section restates the order column
for reference and adds the duplicate rule.

| collection | order | canonical key | duplicates |
| --- | --- | --- | --- |
| `references.context[]` | SET | `(workspace_id, source_kind, source_identity, source_revision, subject, value_digest)` | REJECTED |
| `references.decisions[]` | SET | `record_ref` | REJECTED |
| `references.supersedes[]` | SET | `record_ref` | REJECTED |
| `artifacts.items[]` | SET | `artifact_digest` | REJECTED |
| `payload.reasons[]` | SET | element value ascending | REJECTED |
| `payload.tool_calls[]` | ORDER | explicit `ordinal`; array position is never semantic | REJECTED on a duplicate ordinal |

```text
Amendment 1 changes three rows and adds one.

artifacts.items[]        key was (role, artifact_digest). `role` MUST BE ABSENT in
                         v1 (§13.1), so the key is artifact_digest alone.
payload.reasons[]        was not declared here at all, so its ordering was an
                         implementation choice that moved content_digest.
payload.tool_calls[]     formerly written `payload tool_calls[]`.
payload tests[]/results[]  REMOVED. No leaf schema for it existed anywhere in this
                         contract, and no §6.2 event produces it.
```

An undeclared collection is a contract violation, not an implementation choice. AI-04
paid for an undeclared collection twice — Amendment 9(b) and AI-04-B §E.1 — and both
times the symptom was a digest that moved when nothing semantic did.

### 15.5 The canonical cases — FROZEN

```text
C1   same semantics, different YAML key order      SAME content_digest
C2   same semantics, different set order           SAME content_digest
C3   same semantics, different artifact locator    content_digest SAME (excluded)
                                                   record_digest  DIFFERENT
C4   same semantics, different recorded_at         content_digest SAME
                                                   record_digest  DIFFERENT
C5   same semantics, different evidence_id         content_digest SAME
                                                   record_digest  DIFFERENT
C6   same event, different observed_at             OBSERVATION/EXECUTION: DIFFERENT
                                                   DECISION:              SAME
C7   same artifact bytes, different artifact_ref   identical to C3
C8   same Context identity, different value_digest content_digest DIFFERENT
                                                   (value participates in identity, §12.2)
C9   same claim, different experiment_id           content_digest SAME  (§8.4)
                                                   record_digest  DIFFERENT
C10  same claim, different producer_version        content_digest SAME  (§15.2.2)
                                                   record_digest  DIFFERENT
C11  same claim, different producer                 content_digest DIFFERENT
                                                    (provenance is semantic)
```

---

## 16. content_digest

FROZEN.

```text
purpose     semantic equivalence
covers      exactly the rows marked `yes` in the §15.2 table
excludes    evidence_id, recorded_at, experiment_id, producer_version,
            artifact_ref, artifact availability, storage tier
generated   by AI-05 from admitted canonical content. NEVER caller-supplied (R1).
property    INVARIANT across promotion and relocation
job         deduplication; "do these two records make the same claim?"
```

**§15.2 is authoritative.** The list above is a summary; if it ever disagrees with
the table, the table is correct and this paragraph is the defect.

```text
same content_digest  does NOT imply same evidence_id   (§8.1)
```

---

## 17. record_digest

FROZEN.

```text
purpose     integrity of the stored record
covers      every persisted field — exactly the rows marked `yes` in §15.2, which
            is every stored field including evidence_id, recorded_at,
            experiment_id, producer_version and artifact_ref
excludes    record_digest itself — a digest MUST NOT be its own input
generated   by AI-05. NEVER caller-supplied (R1).
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
producer_type = human         REJECTED      role constraint, not a vocabulary
                                            member (§7.1)
undeclared raw-content field  REJECTED      a raw payload, raw log, raw provider
                                            body or raw tool output is not reshaped
                                            into an artifact; the producer stores
                                            the bytes and submits a reference
                                            (§13.8)
workspace mismatch            REJECTED      §18
workspace missing             REJECTED      required field
workspace unresolvable        REJECTED      §18.2
secret detected in a Class 3
  or Class 4 field by the
  published rules             REJECTED      never stored; never redacted in place
                                            by AI-05 — an unsanitized identifier is
                                            the upstream sanitizer's miss, not
                                            something AI-05 repairs (§14.2)
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

**Amendment 1 made the reference unambiguous.** A `record_ref` ALWAYS denotes an
AI-05 `evidence_id`, in both `references.decisions[]` and `references.supersedes[]`,
and takes the grammar `G-EVIDENCE-ID` (§14.9). An AI-04 guard decision id is NEVER an
AI-05 `record_ref`: an AI-04 decision is recorded as an AI-05 `DECISION` record and
is referenced by **that** record's id. Accepting a raw decision id would make
`record_ref` denote two namespaces at once, which is the homonym this section exists
to close.

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

**Amendment 1 restated this boundary.** This section previously said a routing
decision *can* become a `DECISION` record, while §11 provided no routing arm and no
routing vocabulary exists in the repository. Two sections cannot both be true, so
the statement is now made as a taxonomy fact plus a payload-support fact:

```text
kind classification    DECISION            (§6.2, unchanged)
payload support        DEFERRED
outcome vocabulary     NOT FROZEN
producer token         NONE registered     (§6.5)
reserved field         none
reserved discriminator none
interface reservation  forbidden (below)
```

The kind is decided; the outcome vocabulary is not. **No routing decision is
representable in v1**, and this is a declared deferral rather than a silent
impossibility.

AI-05 MUST NOT:

```text
route
select a model
reserve a Router-shaped interface field
```

AI-07 is **DEFERRED**. AI-05 does not stub it, does not reserve an interface for it,
and reserves no routing field, discriminator or arm.

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
 4b. role          producer_type is NOT human (§7.1). Membership in the inherited
                   ActorType vocabulary is necessary but not sufficient — the role
                   constraint is applied on top of it
 5. workspace      workspace_id is present, non-empty, and agrees everywhere (§18)
 6. classes        every string field is validated against its declared class (§14.2)
 7. rule set       every supplied Class 3 and Class 4 field is checked against the
                   published rule set (§14.10, C1-R01..C1-R06)
                   -> a match is REJECTED as ADMISSION_RULE_VIOLATION
                   -> DETECTION ONLY. AI-05 never substitutes (§14.4.1)
                   -> read from the SUPPLIED values, before step 1 constructs the
                      record: construction derives references.context[].value_digest
                      from the supplied value, and R2 forbids hashing a value that
                      was not admitted. A record violating both a shape rule and a
                      published rule therefore reports the rule; both are REJECTED
                      and nothing is stored
 8. references     references are well-formed and their identity is complete (§12)
 9. artifacts      artifact entries satisfy §13.1/§13.2
10. digest origin  content_digest, record_digest and every ContextRef.value_digest
                   are ABSENT from the supplied record. AI-05 generates them (§14.6.1)
                   -> a caller-supplied value in those fields is REJECTED (R1)
11. digest shape   every supplied Class 1 field (artifact_digest) is
                   lowercase hex of the exact declared length (§14.5.1)
                   -> uppercase is REJECTED, never normalized
12. integrity      AI-05 computes content_digest and record_digest over the accepted
                   canonical content
13. assignment     AI-05 generates evidence_id (§8.1)
14. uniqueness     the generated evidence_id is not already present
```

Any failure produces `REJECTED` with a named reason and **stores nothing**.

```text
unknown top-level field        REJECTED   — a field that is silently dropped cannot
                                            be audited (AI-04 §4.2 precedent)
unsupported schema_version     REJECTED
caller-supplied digest for an
  AI-05-generated field        REJECTED   (R1, §14.6.1)
uppercase hex in Class 1       REJECTED   (§14.5.1)
unsanitized identifier in
  Class 3                      REJECTED   (§14.2)
producer_type = human          REJECTED   (§7.1) — the producer is the component
                                           that WROTE the record, and a human does
                                           not author an EvidenceRecord directly
an undeclared raw-content
  field of any kind            REJECTED   — including a raw payload, raw log, raw
                                           provider body or raw tool output. AI-05
                                           never converts supplied content into an
                                           artifact (§13.4, §13.7)
```

### 30.1 AI-05 never rewrites

```text
No step of admission modifies a supplied value. The only values AI-05 originates are
the three digests it generates (§14.6.1) and evidence_id (§8.1). Everything else is
either admitted as supplied or rejected.
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
| T4b | producer role constraint | role, not vocabulary | `producer_type = human` | `REJECTED` | `human` is in the inherited vocabulary but is not a valid producer role (§7.1); membership is necessary, not sufficient |
| T4c | actor admission boundary | role, not vocabulary | `actor.type = human` on a DECISION | `REJECTED` | `ActorType.HUMAN` remains a valid inherited vocabulary member, but the human-approval event is not an admitted v1 event, so §6.6 rejects a `DECISION` carrying `actor.type = human`. Amendment 2 corrected this row: it previously read `ACCEPTED` |
| T5 | `evidence_id` identity | identity ≠ semantics | two records, same content, different ids | both accepted; ids differ; ids absent from `content_digest` | two runs are two events |
| T6 | `experiment_id` correlation | correlation ≠ identity | many records, one `experiment_id` | all accepted, none unique | grouping never becomes identity |
| T7 | `content_digest` determinism | canonicalization | same semantic input, separate processes | identical digest | an unenforced digest is not a digest |
| T8 | operational fields | digest classification | vary `recorded_at`, `experiment_id`, `producer_version`, `artifact_ref` in turn | `content_digest` unchanged, `record_digest` changed — for each | an operational field that reaches `content_digest` is an undeclared semantic input |
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
| T20c | structural provenance | structural class | a legitimate 64-hex value in a Class 4 bounded field | `REJECTED` — rule 6 fires; asserted as the DECLARED consequence | 64 hex is only safe where provenance is constrained; over-rejection is the safe direction |
| T21a | malformed digest length | structural class | wrong-length digest | `REJECTED` | shape failure is never a redaction candidate |
| T21b | malformed digest charset | structural class | non-hex in a digest field | `REJECTED` | as T21a |
| T21c | digest case policy | structural class | uppercase hex in a Class 1 field | `REJECTED` as non-canonical; NOT normalized | AI-05 never substitutes a value, so it cannot normalize one |
| T22a | known test secret | secret boundary | a known test secret in a Class 4 field | `REJECTED` | published rules are enforced at admission |
| T22b | secret-shaped token | secret boundary | a secret-shaped token in a Class 4 field | `REJECTED` | as T22a |
| T22c | identifier pre-sanitization | secret boundary | an UNSANITIZED secret-shaped token in a Class 3 field | `REJECTED`; the pre-sanitized form is `ACCEPTED` | AI-05 checks shape, it never sanitizes (§14.2, §14.4.1) |
| T22d | caller-supplied digest | digest origin | a caller supplies a value for `content_digest`, `record_digest` or `ContextRef.value_digest` | `REJECTED` (R1) | digests of AI-05's own content are AI-05's to compute; `sha256(secret)` cannot be adopted as an Evidence digest |
| T22e | AI-05-generated digest | digest origin | AI-05 computes a digest from accepted canonical content | `ACCEPTED` | positive control: digest-shaped is not the same as caller-controlled |
| T23 | raw payload rejection | payload boundary | an undeclared raw-content field — raw payload, raw log, raw provider body, raw tool output | `REJECTED`; nothing stored | raw payload cannot cross the normalized Evidence boundary, and AI-05 never converts supplied content into an artifact (§13.8) |
| T24 | artifact reference contract | artifact boundary | the VALID alternative path: a producer stores the bytes outside AI-05 and submits `artifact_digest` + `artifact_ref` + `external` + `owner_workspace_id` | `ACCEPTED`; digest required; `artifact_ref` opaque; availability absent | T23 and T24 are two halves of one boundary: the reference crosses, the bytes never do (§13.7) |
| T25 | immutable write | lifecycle | any later operation on an admitted record | bytes unchanged | an audit trail that can be edited is not one |
| T26 | correction via `supersedes` | lifecycle | a correcting record | new record accepted; old record byte-identical | corrections are additions, never edits |
| T27 | `superseded_by` derived | lifecycle | query the set | derivable; not a stored field on any record | a stored back-pointer is a mutation |
| T28 | duplicate `evidence_id` | identity | the same id twice | `REJECTED` | collision or overwrite attempt |
| T29 | duplicate content | identity | same claim under two `experiment_id` values | same `content_digest`, different `record_digest`, both `ACCEPTED` | correlation is not identity; a claim recorded under two tasks is still one claim |
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
T22a-e are five distinct boundaries, not five spellings of one. T22a and T22b are
  detection at admission; T22c is the pre-sanitization requirement; T22d is digest
  ORIGIN; T22e is the positive control that proves T22d rejects for the right
  reason. T22e MUST exist — without it, T22d is satisfied by a system that rejects
  every digest.
T20c and T21c assert DELIBERATE REJECTIONS that a reader may expect to be
  acceptances. They MUST NOT be "fixed" by widening the rule. Widening them changes
  a frozen boundary (§34.1).
T20c and T22a-c are ENFORCEABLE as of Amendment 3, which publishes the admission
  rule set they assert against (§14.10). T20c was carried as a static skip while C-1
  was deferred; it is an assertion now, and it asserts the SAME expectation it always
  stated. T22a, T22b and T22c are the three detection rows of §14.10: a known test
  secret in a Class 4 field, a secret-shaped token in a Class 4 field, and an
  unsanitized secret-shaped token in a Class 3 field. T22d and T22e are unaffected —
  they are digest-ORIGIN rows and never depended on the rule set.
T4b and T4c are a pair, and Amendment 2 restates what the pair proves. The earlier
  wording described T4c as an acceptance and justified it by the recorded human
  approval of §6.3, which §6.5 and §6.6 do not permit in v1; it is replaced here.
T4b proves that `producer_type = human` is rejected even though `human` IS a member
  of the inherited ActorType vocabulary.
T4c proves the complementary boundary from the other side: `ActorType.HUMAN` remains
  a valid vocabulary member, while a DECISION record carrying `actor.type = human`
  is nevertheless rejected in v1, because the human-approval event is deferred from
  the §6.5 admitted registry.
Therefore the restriction is not implemented by deleting `human` from the inherited
  vocabulary; it is enforced at the v1 role/admission boundary. A system that
  satisfied T4b by removing `human` from the vocabulary would still pass T4c's
  vocabulary assertion but would fail T4c's record assertion for the wrong reason,
  which is what keeps the two rows from collapsing into one another.
T23 and T24 are a pair. T23 alone is satisfied by a system that rejects every
  artifact reference. T24 is the control that proves the legitimate path — bytes
  stored by the producer, reference submitted to AI-05 — still works.
T24 COMPATIBILITY EDIT, recorded by Amendment 1. T24's test identity, purpose,
  acceptance assertion and security property remain unchanged. Its fixture field
  list is updated only to remove the now-forbidden v1 `role` field, which
  Amendment 1 makes MUST BE ABSENT in v1 (§13.1). Leaving `role` in the fixture
  would have left this matrix asserting an input the contract now rejects. This is
  a consistency edit and not a change of test meaning; the whole of T24's text is
  NOT unchanged, and this note is what records the difference.
T31 MUST observe state before and after. Asserting an absence rhetorically proves
  nothing.
T33a-d are four separate routes to the same forbidden outcome. One test would cover
  one route and imply the other three.
T8 covers four fields, not one, and each MUST be asserted separately: an operational
  field that leaks into content_digest is an undeclared semantic input.
```

### 31.2 Tests added by Amendment 1

Amendment 1 adds the assertions its declarations require. None of T1 to T35 is
removed, merged, renumbered or weakened.

```text
T42b   kind is DECISION and actor.type is human                REJECTED
T42c   kind is DECISION and actor.type is agent or unknown     REJECTED
T42d   kind is DECISION and producer is not ai-04              REJECTED
T42e   a legitimate AI-04 Guard decision                       ACCEPTED
T42f   a routing decision is not representable in v1           REJECTED
T43    every collection in §15.4 has leaves in §15.2, and no collection leaf
       belongs to an undeclared collection
T44    artifact_ref accepts a bounded single-line opaque value and rejects a
       multi-line or over-long one; AI-05 never resolves or parses it
T45    actor.id accepts a multi-character value and rejects a multi-line one
T46    artifacts.items[].role present in v1                    REJECTED
T47    payload.reasons[] is permutation invariant; a duplicate  REJECTED
T48    a legal AI-02 model_ref containing a colon              ACCEPTED
       a model_ref with no slash or two slashes                REJECTED
T49    a 40-character revision with a document source_kind     REJECTED
       a 64-character revision with a git source_kind          REJECTED
T50    a source_kind outside AI-03 SourceKind                  REJECTED
T51    a malformed timestamp                                   REJECTED
       observed_at null on DECISION                            ACCEPTED
       observed_at null on OBSERVATION or EXECUTION            REJECTED
T52    a binding arm that does not match the family            REJECTED
T53    every §15.2 leaf is reachable, and every digest projection reference is
       represented by a field-table row, asserted per digest
T56    an AI-03-valid subject greater than 64 characters and at most the
       G-SUBJECT bound                                         ACCEPTED
T57    both source_revision paths produce identical outcomes for identical
       source_kind and revision input pairs
```

#### T54 — all six admitted events accepted with their registered producer

Six cases, one per row of §6.5. Each supplies a payload its kind or family
admits, and the case is satisfied only when the record is accepted with the
token spelled exactly as §6.5 spells it.

```text
case                                                              expected
ai-03 with OBSERVATION, family SOURCE_READ,
    producer_type service, actor.type service                     ACCEPTED
ai-02 with OBSERVATION, family PROVIDER_PROBE,
    producer_type service, actor.type service                     ACCEPTED
ai-02 with OBSERVATION, family CAPABILITY_OBSERVATION,
    producer_type service, actor.type service                     ACCEPTED
ai-04 with DECISION,
    producer_type service, actor.type service                     ACCEPTED
ai-06 with EXECUTION,
    producer_type service, actor.type agent                       ACCEPTED
ai-06 with EXECUTION,
    producer_type service, actor.type service                     ACCEPTED
```

#### T55 — incompatible producer and event combinations rejected

```text
case                                                expected
ai-02 used with DECISION                            REJECTED
ai-04 used with OBSERVATION                         REJECTED
ai-06 used with DECISION                            REJECTED
ai-03 used with EXECUTION                           REJECTED
ai-02 used with OBSERVATION and family SOURCE_READ  REJECTED
a token absent from the registry                    REJECTED
```

T54 and T55 are a pair. T54 alone is satisfied by a registry that admits
everything; T55 alone is satisfied by one that admits nothing.

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
  Proved     every record names who wrote it, whose act it describes, and when, and
             that the two roles are distinct
  Evidence   T1, T3, T4b, T4c; the §9.1 required-field list; the §7.1 role constraint
  Forbidden  a record with no producer or no actor; producer_type = human;
             actor and producer conflated; an absent observed_at where the kind's
             claim is time-bound; a fabricated provenance field; a host path or
             artifact availability in a record

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
  Proved     the §14.3 invariants hold, and the limit §14.8 does not close is stated
  Evidence   T20a–c, T21a–c, T22a–e; the published rule set (§14.10, published by
             Amendment 3 — before it, this gate cited a rule set the contract named
             and deferred); the §14.6.1 digest-origin table
  Forbidden  a secret in a Class 3 or Class 4 field; a caller-supplied value in an
             AI-05-generated digest field (R1); AI-05 computing a digest over a value
             it did not admit (R2); any field whose declared role is a secret or
             credential (R3); a blanket application of rule 6 to structural fields;
             stored error text; AI-05 performing sanitization or substitution; a
             claim of detector completeness
  Not forbidden, and stated as such
             artifact_digest supplied by a producer whose artifact bytes may contain a
             credential — accepted, bounded, and recorded as an unclosed residual in
             §14.8 rather than implied away

C7 — Artifact boundary
  Proved     references and digests only; no byte ingestion; availability not a field;
             raw content is rejected rather than reshaped into an artifact
  Evidence   T23 (raw content REJECTED) and T24 (the legitimate reference path);
             §13.7's one-directional diagram
  Forbidden  claiming AI-05 verifies artifact bytes; AI-05 converting supplied raw
             content into an artifact reference; AI-05 sanitizing, storing or
             digesting artifact bytes; artifact availability stored as a record
             field; a missing artifact treated as record corruption; an unmarked
             external artifact

C8 — Immutable / append-only
  Proved     an admitted record's bytes never change; corrections are new records
  Evidence   T25, T26, T27
  Forbidden  a stored superseded_by; a revision counter on one identity; revocation
             by mutation; deletion of a promoted record; promotion changing content
             rather than location only

C9 — Digest determinism + integrity
  Proved     equal semantics -> equal content_digest; altered bytes -> different
             record_digest; storage round-trips; EVERY field classified exactly as
             the §15.2 table says
  Evidence   T7–T11; T8 asserts each operational field separately; the §15.5 canonical
             cases C1–C11, including C9 (experiment_id), C10 (producer_version) and
             C11 (producer)
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

#### Amendment 1 — AI-05-B1 implementation readiness (2026-09-30)

Found while implementing AI-05-B1 against main
`53c0cce1a375b7084e1ab63ef52691068e1285f1`, the head at which this contract's file
had blob `b1f97b5437737c106aacd3a8635386686ae5e719`. The amendment was authored on a
docs-only branch with the B1 implementation head
`f1644de005d61d718b72382fe03a8104734e9716` left untouched.

```text
(a) §11 declared no payload field, class or semantic/operational mark while
    requiring all three. It named the fields in prose and satisfied none of its own
    requirements. All three payloads are now declared leaf by leaf in §15.2.

(b) OBSERVATION is a typed union. §6.2 enumerates exactly three OBSERVATION-producing
    events, each carrying a different status vocabulary that is preserved verbatim:
    SourceReadStatus from AI-03; LiveRunStatus, ProbeOutcome and CapabilityStatus
    from AI-02. AI-02's own ProbeOutcome docstring records that collapsing
    INCONCLUSIVE into FAIL would turn a weak probe into a false negative. The
    `family` field, whose members are §6.2's rows, selects the arm and therefore the
    status vocabulary. The arm is never inferred from a producer name.

(c) AI-05 v1 declares an admitted-producer registry in §6.5, keyed by event and
    family, holding exactly six entries. No frozen serialized producer token exists
    anywhere in the repository, so this amendment freezes a set rather than leaving
    every producer rule uncheckable. The event-to-component mapping is
    contract-required and is transcribed from §6.2's producer and actor columns; the
    token spellings are implementation-chosen and are frozen by this amendment. The
    registry constrains v1 admitted records, not the permanent set of Workbench
    components.

(d) §6.6 adds cross-field rejection rules on producer, producer_type, actor.type and
    decision. Without them any service producer carrying an ALLOW decision could be
    read as an AI-04 Guard decision, and a human approval could be recorded in
    GuardDecision's vocabulary, which belongs to a component that did not perform
    the act.

(e) §6.2, §11 and §27 are reconciled on AI-07. A routing decision is classified as
    DECISION and its payload outcome vocabulary is not frozen, so the arm is
    deferred, no token is registered, and no routing decision is representable in
    v1. §27's prohibition on reserving a Router-shaped interface stands. The human
    approval arm is deferred on the same footing. Neither gains a placeholder token,
    a discriminator, a reserved field or an interface.

(f) §15.4 declared a `payload tests[]/results[]` collection with no leaf schema
    anywhere in this contract, so the statement that every collection is declared
    was false of the contract itself. The row is removed; no §6.2 event produces such
    a collection.

(g) §15.4 did not declare `payload.reasons[]`, so its ordering changed
    content_digest by implementation choice. Declared SET with duplicates rejected.
    AI-04 records reasons as an ordered tuple but digests it nowhere, so AI-04 never
    decides whether the order is semantic. This is an AI-05 contract semantic choice,
    not a claim about AI-04's tuple.

(h) The `role` deferral is synchronised across §13.1, §13.2 and §15.2. §13.1
    declared `role` a closed vocabulary and enumerated no members, so the field could
    not be validated. It is now a closed vocabulary whose members are not yet frozen,
    and `role` MUST BE ABSENT in v1. The ordering and uniqueness key becomes
    `artifact_digest` alone.

(i) §11 named a `result classification` with no repository vocabulary behind it. It
    is declared deferred: the concept remains in this contract, and the field MUST BE
    ABSENT in v1.

(j) The rename of §21.1's `correction_reason` to `correction_code` is withdrawn. No
    evidence establishes that it is a code. `correction_reason` is retained as
    Class 4 bounded text, single-line, semantic, in both digests, and does not
    collide with `payload.reason_code`, because different leaf paths are different
    fields.

(k) §15.2 classified containers and could not express a nested exclusion. The
    exclusion of `artifact_ref` from `content_digest` lived in imperative code rather
    than in the table. §15.2 is now a leaf table and §15.4 is merged into it, so a
    collection's order and its leaves are declared in one document.

(l) §14.2 Class 3 read "identifier" while the fields assigned to it include a
    timestamp, a hostname, a model reference, an opaque locator and a record
    reference, none of which is an identifier. Class 3 is now defined as a structured
    machine token: a bounded string whose interpretation is defined by a
    field-specific grammar. Class 4 is producer-normalized bounded text, with the
    division stated: the producer normalizes and flattens newlines, and AI-05
    validates and rejects and never substitutes.

(m) §14.9 adds the grammar table. `G-MODELREF` is the composition of `PROVIDER_ID_RE`
    and `MODEL_ID_RE`, corrected against frozen AI-02; a narrower pattern would have
    rejected a legal AI-02 model reference containing a colon.

(n) `subject` no longer uses an identifier grammar. AI-03's `subject_for_declaration`
    yields the prefix `declared.` plus a normalised key of up to 80 characters, so a
    legal AI-03 subject can reach 89 characters; an identifier cap of 64 would have
    rejected it. `G-SUBJECT` is bounded, single-line and otherwise uninterpreted, and
    both subject paths use it.

(o) `source_identity` no longer claims a path grammar. AI-03 §7.1 freezes only the
    stable identity of the thing read within the workspace, and AI-03's own values
    include the bare token `git`. `G-OPAQUE-ID` admits path-shaped values without
    asserting that they are paths.

(p) `endpoint_host` uses `G-HOST`. AI-02's endpoint host semantics are not redefined:
    the exclusions follow from `endpoint_host()`'s own behaviour. The character set
    and the length bound are implementation-chosen, because AI-02 states no lexical
    grammar.

(q) `artifact_ref`'s grammar is `G-LOCATOR`: bounded, single-line and otherwise
    uninterpreted. The statement that it is an opaque identifier and never a path
    describes AI-05's behaviour and is not lexically enforced. The amendment records
    that.

(r) `actor.id` is Class 4. AI-04 does not freeze a grammar and accepts any non-empty
    string, so AI-05's bounded single-line representation is narrower, and is
    recorded as an AI-05 contract choice rather than an AI-04-derived rule.

(s) §12.1 states the conditional revision grammar formally as `G-REVISION`. It
    applies identically to both `source_revision` paths, is a contract-level rule
    rather than a runtime inference, and follows AI-03 §7.1: 40 lowercase hexadecimal
    characters for the git kinds and 64 for the document kinds.

(t) §7.1 gives `producer_type` its own closed vocabulary, `ProducerType`, with the
    members agent, service and unknown. It does not use `ActorType`, and `ActorType`
    is not redefined.

(u) §8.1 fixes the `evidence_id` width at 16 lowercase hex characters, as AI-05's own
    representation choice rather than an AI-04 contract requirement. §23.3 states
    that a `record_ref` always denotes an AI-05 `evidence_id` and that an AI-04
    decision id is never one.

(v) §10.3 gains the `G-TIMESTAMP` syntax rule for `observed_at` and `recorded_at`,
    stated as a separate question from the semantic classification and applying to
    those two fields only.

(w) Declared as implementation-chosen, not derived from any upstream contract: the
    evidence_id width, the ordinal bound and uniqueness, the Class 3 and Class 4
    length caps including the 512 bound chosen to avoid a Class 5 free-text field,
    the `G-SUBJECT` cap of 256, the `G-TIMESTAMP` syntax rule, the `G-LOCATOR`
    character set, and the six producer tokens.

(x) T24 COMPATIBILITY EDIT, recorded here because the whole of T24's text is NOT
    unchanged. T24's test identity, purpose, acceptance assertion and security
    property remain unchanged: it is still the artifact reference contract, it is
    still the control that proves the legitimate reference path is accepted, and it
    still asserts `ACCEPTED` with the digest required and `artifact_ref` opaque. Its
    fixture field list is updated only to remove the now-forbidden v1 `role` field,
    which this amendment makes MUST BE ABSENT in v1 (§13.1). The edit exists because
    the matrix would otherwise assert an input the contract now rejects. It changes
    no test meaning and no number. §31.1 carries the same note beside the matrix.

No boundary, scope, deliverable, kind, digest classification, workspace rule or
authority relation changed. C-1 remains DEFERRED.
```

#### Amendment 2 — human-approval v1 representability reconciled (2026-10-01)

Found during contract review after AI-05-B1 merged to `main` as
`0403fcd83b740f0603af7204e77f6e6905a84cf0`. The review set §6.3's conceptual
classification beside §6.5's admitted registry and §6.6's rejection rules, and found
§31's T4c row asserting the opposite of what those two sections require.

The amendment is authored on a docs-only branch. It changes no implementation:
B1's production code and tests already reject `DECISION + actor.type = human`, which
is what §6.5 and §6.6 require. This amendment corrects the contract to match the
boundary the contract itself already drew. **B1 is not reopened, not reimplemented
and not retested.**

```text
(a) §6.3 stated the conceptual classification correctly and then concluded "Both
    records may exist", which §6.5 and §6.6 do not permit. §6.3 now separates the
    two claims explicitly: a human approval is conceptually
    DECISION + actor.type=human, and is NOT representable in v1, because the event
    is deferred from the admitted registry and §6.6 rejects a non-service DECISION
    actor. The classification is NOT withdrawn — §6.5 already records that what is
    deferred is the outcome vocabulary and not the kind.

(b) §31's T4c row expected ACCEPTED for `actor.type = human` on a DECISION about a
    human approval. That contradicted §6.6's "kind is DECISION and actor.type is not
    service -> REJECTED", and no v1 record could satisfy it, because §6.5 registers
    producer NONE for the human-approval event. T4c now expects REJECTED.
    `ActorType.HUMAN` is NOT removed from the inherited vocabulary; the restriction
    is enforced at the v1 role/admission boundary and not by deleting a vocabulary
    member.

(c) §31.1's note on the T4b/T4c pair justified T4c as an acceptance by "the recorded
    human approval of §6.3", which is the same contradiction one level up. It now
    states the pair as vocabulary-versus-admission controls: T4b proves the producer
    role rejection, and T4c proves that `ActorType.HUMAN` remains a valid vocabulary
    member while a DECISION record carrying it is nevertheless rejected in v1.

(d) §7.1 carried the same contradiction in the block that justifies `ProducerType`
    being a separate closed type: it listed `actor.type = human` as ACCEPTED with
    §6.3 as its citation, so the same false claim appeared in two sections that cite
    each other. That block was found while checking this amendment for consistency
    rather than being among the sites the review named. It now states both halves —
    the member remains in the inherited vocabulary, and an actor of `human` is
    nonetheless rejected on a v1 record — which is what the section's own argument
    needs, since its point is that the producer constraint is a rule about the
    producer role and not a vocabulary edit.
```

Sites (a) through (d) are the whole of the inconsistency. The remaining statements
about `human` in this contract were checked and are already consistent: §6.5's
deferred-event table, §6.6's rejection rows, §11's "DECISION admits one arm in v1",
the §30 admission check for `producer_type = human`, and T4b in the §31 matrix.

No change to §6.5's admitted registry. No change to §6.6's rejection rules. No
production code change, no test change, no B2 implementation. T4c's expected value is
the only assertion in the matrix this amendment changes.

#### Amendment 3 — the published admission rule set is published, not deferred (2026-10-04)

Found while closing C-1 against main
`7e7d83b74e2903f2b83e95cf35d0115d4038df90`. The contract named a "published
admission rule set" in three places — §14.2's Class 4 paragraph, the §14.9 `G-TEXT`
row, and §30 step 7 — and defined it in none. Amendment 1 introduced the name C-1
and left it deferred; the companion records (`AI-05-B2_DECISIONS_2026-10-01.md` D1,
`AI-05-B1_EVIDENCE_2026-10-01.md`, `PROJECT_STATUS.md`) recorded that §30 step 7 was
therefore unimplementable, that T20c was skipped and that T22a/T22b/T22c were
unrunnable.

```text
(a) NEW §14.10 defines the published admission rule set: exactly six rules,
    C1-R01..C1-R06, with their patterns, their order, and the fields they apply to.
    It is a FROZEN SNAPSHOT of the six detection patterns the repository's upstream
    sanitizer applies to provider-bound text — TRANSCRIBED, never imported, so an
    edit to that sanitizer cannot change what AI-05 admits. The snapshot was taken
    at main 7e7d83b74e2903f2b83e95cf35d0115d4038df90.

(b) §14.10 states what the rule set is NOT, because each is a thing it could have
    become: no substitution and no sanitization (DETECTION ONLY — §14.4.1 already
    put the substitution half upstream); no exact-secret list and no secret
    registry (AI-05 holds no caller secret and reads no credential store);
    no rule-set version field on a record (the set is versioned by amendment);
    and nothing retroactive (a written record stays readable; no re-admission and
    no stored-form load applies a later rule set to it).

(c) §14.2's Class 4 paragraph no longer says the rule set "remains DEFERRED, so every
    Class 4 field is structurally bounded and not rule-checked". Class 3 and Class 4
    fields are rule-checked at admission in addition to being structurally bounded,
    which is what §14.5 had already resolved and what §14.4.1 had already scoped.

(d) The §14.9 `G-TEXT` row's "DEFERRED with C-1" is superseded: the admission
    rule-set obligation is CONTRACT-REQUIRED and PUBLISHED by §14.10. The row's
    shape column is unchanged — G-TEXT is still bounded, single-line, ≤512
    characters, no CR and no LF.

(e) §30 step 7 now names the rules it checks (§14.10, C1-R01..C1-R06) and states
    that a match is REJECTED as ADMISSION_RULE_VIOLATION. It also records the one
    ordering consequence this amendment had to settle: step 7 reads the SUPPLIED
    values, before step 1 constructs the record, because construction derives
    references.context[].value_digest from the supplied value (§12.1) and §14.6 R2
    forbids computing a digest over a value that was not admitted. A record
    violating both a shape rule and a published rule therefore reports the RULE.
    Both outcomes are REJECTED and nothing is stored; no accepted value, no bound,
    no digest and no stored record is affected by which reason is reported first.

(f) §31.1 records that T20c and T22a/T22b/T22c are enforceable assertions as of this
    amendment, and that their expectations are unchanged: T20c was carried as a
    static skip while C-1 was deferred and asserts the same REJECTED it always
    stated. T22d and T22e are untouched — they are digest-origin rows.

(g) §32.1's C6 evidence list now cites §14.10 for the rule set this gate always
    required. The gate's condition text is unchanged.

(h) §14.2's own Class 3 definition is unchanged, and Class 5 remains FORBIDDEN. The
    scan set §14.10 publishes is the union of the two classes §14.5 already
    resolved; Class 1 is still NEVER scanned, which is what keeps rule C1-R06 from
    rejecting every digest and every revision in the schema (T20a, T20b).
```

No authority relation changed. No evidence kind, producer registry entry, digest
input, canonical collection, workspace rule, identity field or admission outcome
changed. No lifecycle state was added and no record becomes unreadable: the rules
apply to new admission only. §14.1's limit — a detector is not a completeness claim,
and §14.8's residual stays stated — is unchanged.

C-1 is CLOSED by this amendment. AI-05 remains INCOMPLETE until its own exit gates
say otherwise; a closed C-1 is not a claim that every Evidence seam is connected,
and §30's remaining steps are as they were.


#### Amendment 4 — producer and submitter are different roles (2026-10-09)

```text
IN FORCE — the activation condition this entry declared for itself has been met.

    THE ENTRY WAS PROPOSED WITH THIS STATUS, KEPT HERE AS THE RECORD OF WHAT
    WAS PROPOSED. It is not retracted and not rewritten; it is superseded by
    the merge it named as its own condition:

        "PROPOSED — AWAITING OWNER REVIEW. This entry states the change this
         amendment makes and why. It is NOT yet an approved record: the
         clarification it describes takes effect only when the change carrying
         this entry is merged by AI-05's owner. Until then §7.2 is a proposal,
         and no clause of this contract has changed."

    THAT MERGE HAS HAPPENED:

        merged as   03d42681cb8b2110773654822655117daea44ad5   (PR #80)
                    a true two-parent merge of
                    0bf520f4bd8d5b29d008bec2a11f6f4cfc41fcd5  (main before)
                    and
                    29ccf9a04c35e9fcb01f62f59366806f66afac41  (the branch head)

    WHAT CHANGED       the STATUS of this amendment: proposed -> in force.
    WHAT DID NOT       any semantic text. §7.2 is FROZEN exactly as merged. No
                       clause of it is reworded, added or removed by this
                       status record, and no clause below this block is
                       edited. §34.1's list of amendment-requiring changes is
                       not engaged: this records an amendment's own declared
                       activation, it does not make a new one.
```

Found during the AI-15-A audit, against main
`0bf520f4bd8d5b29d008bec2a11f6f4cfc41fcd5`. §7 defines `producer` as "the component
that WROTE the EvidenceRecord" and never says what **WROTE** means when the caller
that hands the record to admission is not that component. Two frozen clauses were
found to depend on the answer in opposite directions:

```text
§7's human-approval example   producer = "the Workbench component that recorded it"
                              — a ROLE, described by the recording relationship,
                              and §6.2's row for the same event says the same:
                              "the Workbench component recording it"
AI-08 §13.1                   reads WROTE literally enough to refuse: AI-08 "MUST
                              NOT write an EvidenceRecord under the 'ai-06' token.
                              AI-08 is not AI-06. `producer` names the component
                              that WROTE the record, and that claim would be
                              false."
```

The audit recorded the question, chose neither reading, and named it OPEN-2. This
amendment MAKES that choice rather than discovering it: `producer` names the
component responsible for the event's **claim**, not the code that called the
admission or storage API. §7's own example for the human-approval event and §6.2's
row for it are CONSISTENT with the choice, which is why it is defensible; they are
not evidence that the contract entailed it uniquely, and §7.2 records that limit.

**Why this is an amendment rather than a clarification made in place.** §34.1's
list of changes that require an amendment enumerates evidence kind, canonical
collection, digest input, workspace rule, secret boundary, authority relation,
identity field and admission outcome; **§7 is not on that list.** §34's preamble
is broader than its list, though — a frozen contract "changes only through an
explicit amendment recorded in §34.3" — and §7.2 adds a FROZEN clause to a frozen
contract, which is a change however it is described. §34.2 forbids the
alternative: a silent adjustment, or a rule relaxed to make an implementation
pass. The instrument is therefore an amendment, recorded here, and the fact that
§7 is absent from §34.1's list is recorded rather than relied on.

The amendment is authored on a docs-only branch. **It changes no implementation.**
`plugins/evidence/` is untouched: `admit()` and `admit_to_store()` take no
submitter identity today, and they still take none after it. The registry check
already compares the token against the rows its kind and family select, and
compares nothing beyond them; §7.2 states what that does and does not establish.
It changes no behaviour: the check is the same before and after. No test is
added, changed or re-scoped.

```text
(a) NEW §7.2 declares the Producer / Submitter distinction and gives WROTE its
    operative meaning.

        producer    the Workbench component RESPONSIBLE FOR THE CONTENT of the
                    event the record describes — the component that supplies the
                    semantic content of that event's claim
        submitter   the caller that hands an already prepared record to `admit()`
                    or `admit_to_store()`

    §7.2 states that WROTE names the ATTRIBUTION of the event's claim to the
    component that supplies its semantic content, and is not by itself a
    statement about which code performed the call.

(b) §7.2 records five consequences, each FROZEN:

        a submitter MAY differ from the producer named on the record, and that is
          not a defect in the record
        a submitter differing from the producer makes the claim neither true nor
          false — trustworthiness is a DIFFERENT question, and §7.2 does not
          answer it
        calling `admit()` or `admit_to_store()` does NOT by itself confer the
          producer role on the caller
        §6.5 registry and cross-field validation constrain whether the token
          APPLIES to this record's kind and family — a real constraint — and they
          neither establish the submitter's identity nor authenticate the claim.
          §7.2 separates those three checks and forbids conflating them.
        no clause may be read as declaring a producer claim AUTHENTICATED — AI-05
          admits a record whose token §6.5 registers for its kind and family, and
          does not certify who supplied it

(c) §7's three worked examples are reconciled with §7.2 and NONE of them is
    changed. "Guard decides" and "A probe observes" name the component that
    supplies the claim, which §7.2's definition already covers. "A human
    approves" names a ROLE — "the component that recorded it" — and §7.2 states
    that this component is the one responsible for the claim about the human's
    decision, whether or not some other caller hands the record in. §6.2's row
    for the same event uses the same words, and the event remains DEFERRED with
    producer NONE in §6.5. §7's closing rule — "a record with no producer is not
    a record", and provenance is never fabricated — is unchanged and is what §7.2
    is written to protect.

(d) §7.1's rule is reinforced rather than restated. §7.2 refuses to let a
    submitter's ACT confer the producer role; §7.1 already refuses to let a
    vocabulary MEMBERSHIP confer the producer role, and states why the constraint
    is a rule about the role rather than an edit to a type AI-05 does not own.
    The two are the same shape, and neither changes.

(e) §6.2's producer/event mapping, §6.5's admitted-producer registry and §6.6's
    cross-field rejection rules are UNCHANGED, and §7.2 states that they are each
    written to be satisfied whether or not the submitter is the producer. The
    mapping is keyed by event, the registry by (kind, family), and the rejection
    rules by the token, the producer_type and the actor — none of them inspects
    the caller, which is why no sentence in those three sections had to move.

(f) §5.1's field comment — `producer: string  # the component that WROTE this
    record` — is UNCHANGED, and it carries NO CROSS-REFERENCE: it does not cite
    §7, and no such citation is claimed here. §7.2 supplies the meaning of WROTE
    that the comment leaves open, which is why the comment needs no edit. The
    alternative — rewriting a one-line comment in place — would have widened
    this amendment's footprint without changing what the field means.

(g) §6.5's sentence that the event-to-component mapping states "which component
    writes which event" is UNCHANGED. Under §7.2, "writes the event" is the
    producer role: the component responsible for that event's claim. The sentence
    and §7.2 agree, and the registry's own limits — keyed by event and family, a
    token valid for one event not thereby valid for another — are as they were.
```

```text
WHAT THIS AMENDMENT DOES NOT DO, stated because each is a thing it could have
been read as doing:

    no producer token, registry row, Evidence kind, family, admission outcome or
      serialized field is added or removed
    no producer-authenticity mechanism is implemented, and authenticity is NOT
      claimed to be established. §7.2 says the opposite: registry and cross-field
      validation constrain token applicability and the field types, and neither
      authenticates a producer nor identifies a submitter
    the contracts of AI-06, AI-08, AI-11, AI-14 and AI-15 are NOT modified by
      this change, and nothing here states or implies that they are
    AI-11 §21.1's OPEN-1 — WHICH PRODUCERS EXIST — is NOT closed by this
      amendment. It is a different question with the same owner
    AI15-OPEN-1 (how a producer claim is authenticated) and AI15-OPEN-2 (the
      submitter/producer relation) are NOT auto-closed. §7.2 answers the second
      in AI-05's own voice; whether that closes AI-15's record of it is AI-15's
      act, not this amendment's
    no production Evidence writer is authorized to be created or run
    AI-08 still MUST NOT write under the `ai-06` token. §7.2 explains WHY AI-08
      §13.1's reasoning holds — AI-08 does not supply the claim about AI-06's act
      — and changes nothing about AI-08's own token or its contract permission,
      both of which remain unaddressed and DEFERRED
    AI-06's "the caller submits it" is given a consistent reading — the caller is
      the submitter, and AI-06 remains the producer of a tool-execution record —
      but AI-06's contract is NOT modified by this change
```

No authority relation changed. No evidence kind, registry entry, digest input,
canonical collection, workspace rule, identity field, admission outcome or
lifecycle state changed. No admission rule changed: §30's steps, §14.10's rule set
and §6.6's rejection rows are as they were. §7.2 adds no check and removes none:
§6.5 and §6.6 continue to enforce exactly what they enforced before. What the
amendment adds is a NORMATIVE CHOICE about what the word WROTE means, recorded
here because the original wording left it open and two readings were available.

**AI-05 remains INCOMPLETE.** This amendment closes nothing: not AI-11 §21.1's
OPEN-1, not any AI-15 open item, and not §35.1's deferrals.

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
