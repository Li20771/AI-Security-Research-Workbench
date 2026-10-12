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
                                              DEFINED BY §7.3 (Amendment 5).
                                              Before Amendment 5 AI-05 did not
                                              do this and this section did not
                                              add it. §7.3 is the instrument
                                              that adds it, and THIS section
                                              still does not
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
        still do. Whether a producer claim is trustworthy was OPEN when this
        section was written, and this section does not close it. §7.3, added by
        Amendment 5, is where the standard is DEFINED — and §6.5 and §6.6 are
        UNCHANGED by that amendment.
```

### 7.3 Producer authentication — FROZEN (Amendment 5)

> **IN FORCE — Amendment 5, merged as PR #83
> (`7017bf577f654cb6dea0e8d5e50a27f334117b73`).** This section is FROZEN as
> written, and the text below is unchanged by that activation. See §34.3 for the
> record.
>
> **THIS RECORDS THE CONTRACT'S STATUS, NOT A RUNTIME ONE.** Amendment 5 DEFINES a
> standard; it does not implement it. Nothing in this repository performs `§30`
> step 7b, **no producer-authentication acceptance test has been run**, and the
> RECORDED DIVERGENCE in §34.3 stands. **AI15-OPEN-1 remains OPEN**, **AI-15 §15.2
> STEP 0b remains UNSATISFIED**, **B5 remains BLOCKED and is not CONNECTED**, and
> no production non-test Evidence writer is authorized. Being IN FORCE means the
> clause binds; it does NOT mean the mechanism exists.

§7.2 separated three checks and recorded that AI-05 performed only the first. This
section defines the second.

It is AI-05's answer to the question recorded as **AI15-OPEN-1** — how a producer
claim is ESTABLISHED, as against merely well-formed — and it is made here, in AI-05's
contract, under AI-05's amendment rule, because §6.5, §6.6 and §7 are AI-05's.

```text
FROZEN: THIS SECTION DEFINES A STANDARD. IT DOES NOT CLAIM THE STANDARD IS
        IMPLEMENTED. AI-15 §15.2 STEP 0b requires a mechanism AND its
        implementation AND tests showing it holds. This amendment supplies the
        FIRST of those three. The other two are implementation obligations that
        this amendment neither discharges nor may be reported as discharging.
FROZEN: this section does not reopen, re-argue or weaken §7.2. The submitter MAY
        differ from the producer (Reading A, Amendment 4). This section adds a
        check on the producer claim and changes nothing about who may submit.
```

#### 7.3.1 The standard, stated exactly

```text
THE STANDARD
    A producer claim is AUTHENTICATED when, and only when, all of the following
    hold for the record being submitted:

      (a) the deployment has a designated producer trust mapping (§7.3.2)
      (b) that mapping holds a public key for the producer token the record names
      (c) the submission carries a proof (§7.3.3)
      (d) the proof's signature verifies, under THAT key, over the DECODED
          `message_b64u` bytes
      (e) those decoded bytes ARE signed_input(submitted mapping) — the FULL
          COMPOSITE of §7.3.4, domain tag and version INCLUDED, and not the bare
          canonical serialization — byte for byte

    Any of (a)-(e) failing means the claim is NOT authenticated, and the record is
    REJECTED (§7.3.8). There is no partial authentication and no warning state.
```

```text
FROZEN: WHAT THIS ESTABLISHES, AND WHAT IT DOES NOT. Stated here rather than left
        to a reader, because overstating it is the failure this section exists to
        prevent:

        IT ESTABLISHES   the holder of the private key that this deployment
                         associates with producer token T signed a message that is
                         EXACTLY signed_input(THIS RECORD) — the DOMAIN TAG, the
                         SEPARATOR bytes, the PROTOCOL VERSION and the canonical
                         serialization of the COMPLETE SUBMITTED MAPPING, all four
                         of them, per §7.3.4 — and that the record being submitted
                         names T
        IT DOES NOT      prove that a particular CODE COMPONENT executed the
          ESTABLISH      operation, that the component's process is uncompromised,
                         that the claim's CONTENT is true, or that the
                         deployment's mapping is correct

        The step from "the holder of T's key signed" to "component T produced
        this" is a DEPLOYMENT ASSERTION, not a cryptographic one. This contract
        records that assertion as its trust assumption and does not present it as
        proof.
FROZEN: this is NOT a claim about the SUBMITTER. A submitter that is not the
        producer may present a producer's proof (§7.2, Reading A). Producer
        authentication and submitter identity are the second and third checks of
        §7.2 and remain different checks.
```

#### 7.3.2 The designated producer trust mapping

```text
WHAT IT IS      a DEPLOYMENT-level mapping from producer token to Ed25519 PUBLIC
                key, read from exactly ONE place, by exactly one module.
WHAT IT IS NOT  a registry. It creates no §6.5 row, admits no event, and confers
                no recognition. §6.5 remains the SOLE authority on whether a
                producer token is recognized (§6.5, §6.6, UNCHANGED by this
                amendment). A key configured for a token §6.5 does not register is
                INERT — and it is inert BY CONSTRUCTION, not by ordering: a
                successful signature for such a token establishes nothing, because
                the §6.6 registry check inside typed construction REFUSES the
                record whatever its proof said. NO VALID SIGNATURE FOR AN
                UNREGISTERED TOKEN CAN RESULT IN ACCEPTANCE.
                THAT LAST SENTENCE DESCRIBES A KEY THAT COLLIDES WITH NO RECOGNIZED
                TOKEN'S. A key that DOES collide with one is not inert at all — it
                makes the WHOLE MAPPING non-compliant and fails it closed under BOTH
                reader policies. See the group rule below, and §7.3.2's FROZEN clause
                on why the unregistered half is not optional.
```

```text
FROZEN: AUTHENTICATION MAY RUN BEFORE THE REGISTRY CHECK, AND THAT ORDER IS NOT A
        HOLE. §7.3.7 puts step 7b before construction, and the §6.5/§6.6 registry
        and cross-field checks run INSIDE construction (§30 steps 1-4, 4b, 6,
        8-11, 13). A submission naming an unregistered token can therefore REACH —
        and can PASS — authentication, and is then REFUSED by §6.6. An earlier
        revision of this section said the registry check refuses such a record
        "before authentication is consulted". THAT IS WITHDRAWN: it described an
        execution order this contract does not have, and it contradicted §7.3.7 and
        §30 step 7b.
FROZEN: THE TWO CHECKS ANSWER DIFFERENT QUESTIONS AND NEITHER SUBSTITUTES FOR THE
        OTHER, which is why the order between them carries no weight:
            authentication   did the holder of the key this deployment associates
                             with the CLAIMED token sign this submission?
            §6.5 / §6.6      does that token APPLY to this record's kind and
                             family, and is the event representable at all?
        A REGISTERED token with no configured key is REJECTED at authentication.
        A configured KEY with no registered token is REJECTED at construction.
        Neither check can be satisfied by the other, and this amendment adds no
        path on which either is skipped. A valid signature is NOT a registration,
        and it is NOT a permission.
```

```text
FROZEN: NO PUBLIC AI-05 FUNCTION MAY ACCEPT A CALLER-SELECTED PUBLIC KEY, MAPPING,
        ANCHOR OR VERIFIER AS A PARAMETER. A function that takes one has a caller
        who selects what is trusted, and a caller who selects the trust root can
        install their own and mint proofs that verify. The mapping is a DEPLOYMENT
        FACT, read from one place that is not a parameter.
FROZEN: ONE READER. Exactly one module reads the designated mapping, and the
        verification site ASKS that module which key applies rather than deciding
        for itself. A second reader is a second place the phase decides what to
        trust.
FROZEN: NO DEFAULT, NO BYPASS. There is no default mapping, no development
        mapping, no test mapping reachable from production code, no `verify=False`
        switch, and no configuration under which a proof is accepted without
        verification. A test supplies its keys through the SAME designated
        mechanism a deployment uses (§7.3.7); it does not get a second path.
FROZEN: FAIL CLOSED. A deployment with no designated mapping authenticates
        NOTHING, and every submission is REJECTED under §7.3.8. The absence of the
        mapping is not a degraded mode.
```

```text
FROZEN: ONE KEY PER RECOGNIZED PRODUCER TOKEN, AND NO SHARING WITH ANYTHING ELSE.
        Each producer token §6.5 RECOGNIZES MUST have its own private signing key.
        It MUST NOT share that key with another recognized token, AND IT MUST NOT
        SHARE IT WITH AN UNREGISTERED TOKEN EITHER. The corresponding public key is
        what the mapping holds for that token.
        THE SCOPE IS "RECOGNIZED", AND IT IS STATED HERE RATHER THAN LEFT TO BE
        INFERRED FROM A LATER CLAUSE. An earlier revision said "each producer token
        that CAN BE AUTHENTICATED", which reaches every token holding a mapping
        entry — and an unregistered token CAN hold one and CAN be authenticated
        under POLICY A. THAT FORM IS WITHDRAWN: it forbade a configuration POLICY A
        permits, and it left the exception to be reconstructed from below.
FROZEN: A SHARED PRIVATE SIGNING KEY IS NON-COMPLIANT WHEN A RECOGNIZED TOKEN IS
        ONE OF THE SHARERS, AND A DEPLOYMENT CONFIGURED THAT WAY DOES NOT SATISFY
        THIS SECTION. The reason is mechanical rather than stylistic: verification
        selects the key BY THE CLAIMED TOKEN, so two tokens holding one key are
        indistinguishable to the verifier, and either holder could sign a claim
        naming the other that verifies. That is precisely the forgery §9.2 names,
        and a shared key would leave §6.5's string comparison as the only thing
        refusing it — which §7.2 already records is not an authentication check.
        THE FORGERY NEEDS A RECOGNIZED NAME TO LAND ON, and that is why the case
        below is different rather than an oversight. Two UNREGISTERED tokens sharing
        a key cannot produce an ACCEPTED record at all, because §6.6 refuses both of
        them whatever their proofs say; there is nothing for the sharing to reach.
        POLICY A PERMITS EXACTLY THAT CONFIGURATION AND NO OTHER. An earlier
        revision said "a shared private signing key across two or more producer
        tokens IS NON-COMPLIANT" without qualification, which forbade it; THAT FORM
        IS WITHDRAWN. A deployment is NON-COMPLIANT the moment a RECOGNIZED token's
        key is shared with any other token at all.
FROZEN: NO RECOGNIZED PRODUCER TOKEN MAY SHARE ITS PUBLIC KEY WITH ANY OTHER TOKEN
        IN THE MAPPING — REGISTERED OR NOT. Two recognized tokens MUST NOT hold the
        same Ed25519 PUBLIC-KEY BYTES, and A RECOGNIZED TOKEN MUST NOT HOLD THE SAME
        BYTES AS AN UNREGISTERED ONE EITHER. This is the ENFORCEABLE HALF of the
        rule above: the contract never sees a private key, but it does see the
        public keys the mapping holds, and one public key under two tokens IS the
        shared-key defect stated in terms a reader can check.
FROZEN: WHY THE UNREGISTERED HALF IS NOT OPTIONAL, AND WHY "U's OWN RECORDS ARE
        STILL REFUSED" DOES NOT COVER IT. Suppose R is registered and U is not, and
        both map to the same key K. An injectivity rule stated over recognized
        tokens ALONE would tolerate that mapping, because only ONE recognized token
        is involved — AND IT WOULD BE WRONG. If R and U in fact share the private
        key, its holder can sign a claim naming `producer = R`. That claim verifies
        under K, R's own registered key, and §6.6 ADMITS it because R IS registered
        for that kind and family. THE RESULT IS ACCEPTED. The forgery is never made
        in U's name, so nothing about U's records being refused touches it.
FROZEN: THE RULE IS ABOUT GROUPS, NOT ABOUT PAIRS OF RECOGNIZED TOKENS. Group the
        mapping's entries BY PUBLIC KEY. A group containing AT LEAST ONE RECOGNIZED
        TOKEN makes the WHOLE MAPPING non-compliant, however many unregistered
        tokens sit beside it. Only a group consisting ENTIRELY of unregistered
        tokens may be tolerated, and only by POLICY A.
FROZEN: A MAPPING THAT BREAKS ITS READER'S POLICY FAILS CLOSED, AND NO
        AUTHENTICATION PROCEEDS UNDER IT. Validation happens IN THE DESIGNATED
        READER — §7.3.2's ONE READER — which refuses to produce a mapping that
        breaks the rule THAT POLICY enforces: under BOTH policies, a duplicate
        group containing a recognized token; and under POLICY B additionally ANY
        duplicate group at all. THE UNQUALIFIED WORD "INJECTIVITY" IS NOT THE TEST,
        and a reader MUST NOT use it as one: a mapping carrying a duplicate group
        of unregistered tokens is NOT injective as a whole, and under POLICY A that
        mapping is COMPLIANT AND MUST BE USED. A reader that tolerates a group its
        OWN policy permits HAS NOT BROKEN THIS CLAUSE, and refusing the mapping for
        it would itself be the defect.
        When the reader does refuse, the deployment has NO usable designated
        mapping, and every submission is REJECTED under §7.3.8 with
        AUTHENTICATION_KEY_UNAVAILABLE: the same outcome as a deployment with no
        mapping at all, because that is what it now has. The reader MUST NOT return
        the valid subset, MUST NOT keep the first or last entry it saw, and MUST NOT
        warn and continue — a mapping it cannot vouch for is not a mapping it may
        hand out.
FROZEN: A DUPLICATE GROUP CONSISTING ENTIRELY OF UNREGISTERED TOKENS IS HARMLESS,
        AND IT IS THE ONLY CASE THE TWO POLICIES TREAT DIFFERENTLY. Every group that
        contains a recognized token fails the mapping closed under BOTH.

        TWO READER POLICIES ARE PERMITTED FOR THAT ONE CASE, AND THE CONTRACT
        REQUIRES NEITHER. A reader MUST BE CONSISTENT: it may not refuse the mapping
        for some duplicates and tolerate others of the same kind. Which policy a
        deployment runs is a DEPLOYMENT FACT, not a choice any caller makes.

            POLICY A   NO RECOGNIZED TOKEN SHARES ITS KEY WITH ANYTHING; A DUPLICATE
                       GROUP OF UNREGISTERED TOKENS ALONE IS TOLERATED.
                       Every group containing a recognized token fails the WHOLE
                       mapping closed, exactly as under POLICY B. A group consisting
                       ONLY of unregistered tokens is tolerated and the mapping
                       stays usable. Under §7.3.7's order a signature over such a
                       token's claim MAY STILL VERIFY, because step 7b runs before
                       construction; the record is then REFUSED BY §6.6 during
                       construction, whatever the proof said.
                       HARMLESS THROUGH THE REGISTRY.

            POLICY B   FAIL CLOSED ON ANY DUPLICATE PUBLIC KEY, INCLUDING ONE THAT
                       INVOLVES ONLY UNREGISTERED TOKENS.
                       The reader refuses the mapping over ALL its entries, so the
                       deployment has NO usable mapping. The submission is REFUSED
                       with AUTHENTICATION_KEY_UNAVAILABLE, and NO signature
                       verification and NO construction occur.
                       HARMLESS THROUGH A REFUSED MAPPING.

        FROZEN: THE TWO POLICIES DIFFER IN ONE CASE AND NOWHERE ELSE. A group
        holding at least one recognized token fails the mapping closed under BOTH,
        so NO reader policy can admit a mapping on which a recognized token shares a
        key — with another recognized token, or with an unregistered one.

        FROZEN: WHAT HOLDS UNDER BOTH, AND IT IS THE WHOLE OF THE REQUIREMENT
            a mapping entry for a token §6.5 does not register GRANTS NO §6.5
              IDENTITY and creates no registry row
            a duplicate involving only unregistered tokens does NOT, BY THAT
              DUPLICATION ITSELF, bypass the registry check or cause an unregistered
              record to be accepted
            a submission naming an unregistered token MUST NOT BE ACCEPTED on EITHER
              path
            a valid signature is NOT a registration and NOT a permission
        NEITHER POLICY IS HARMLESS BECAUSE "AUTHENTICATION FAILS" AS A PROPERTY OF
        THE CLAIM. Under POLICY A the signature may well succeed; under POLICY B it
        is never attempted.

        AN EARLIER REVISION OF THIS CLAUSE SAID SUCH A COLLISION "AUTHENTICATES
        NOTHING". THAT IS WITHDRAWN: it is false under POLICY A, and it is precisely
        the confusion between authenticating a CLAIM and admitting a RECORD that
        §7.2 and §7.3.8 exist to prevent.
        A reader MAY refuse a mapping for ANY duplicate public key over ALL its
        entries — that IS POLICY B — and it is strictly stronger.
FROZEN: INJECTIVITY IS NOT RECOGNITION, AND A PUBLIC-KEY MAPPING CONFERS NOTHING.
        §6.5 remains the SOLE authority on whether a producer token is recognized;
        a key configured for an unrecognized token creates no registry entry and
        changes no authority; and an unrecognized token STAYS UNRECOGNIZED however
        well-formed and however unique its key material is. Nothing in this section
        admits an event, and nothing in it moves a row of any authority matrix.
```

#### 7.3.3 The proof, and where it lives

```text
PROOF     a value carried ALONGSIDE the submitted mapping, as a separate argument
          to the admission entry point. It is NOT a field of the EvidenceRecord.

          producer_proof
              message_b64u  string   the signed input of §7.3.4, carried as
                                    canonical UNPADDED Base64url (RFC 4648 §5:
                                    alphabet A-Z a-z 0-9 - _ , and no '=')
              signature     string   exactly 128 lowercase hexadecimal characters,
                                    a 64-byte Ed25519 signature over the DECODED
                                    bytes of message_b64u
```

```text
FROZEN: message_b64u IS A CARRIER, AND ITS DECODING IS STRICT. The signed input is
        what it DECODES to (§7.3.4), never the encoded string itself. Decoding
        MUST refuse a character outside the alphabet rather than skipping it, MUST
        refuse '=' padding, and MUST be CANONICAL: re-encoding the decoded bytes
        MUST reproduce the submitted string exactly, so a value whose final quantum
        carries non-zero unused bits is REFUSED as malformed rather than accepted
        as an alias of a valid one. Two distinct strings therefore never decode to
        the same signed input, and no raw-NUL transport ambiguity exists — the
        signed input's 0x00 separators travel inside the encoding, not beside it.
FROZEN: THE SIGNATURE IS OVER THE DECODED BYTES. Not over the encoded string, and
        not over a re-encoding of it.
FROZEN: THE PROOF IS A REQUIRED ARGUMENT OF BOTH PUBLIC ENTRY POINTS.
            admit(raw, ...)
            admit_to_store(raw, *, store, ...)
        Neither returns ACCEPTED for a submission whose producer claim is not
        authenticated (§7.3.1). `admit_to_store()` passes the proof THROUGH to
        `admit()` rather than verifying a second time, so one verification runs and
        one verdict is reached; it MUST NOT contact the store on a non-ACCEPTED
        result (§7.3.8).
FROZEN: A MISSING PROOF IS A REJECTED RESULT, NOT A TypeError. Omitting the proof,
        or passing `None` explicitly, MUST produce REJECTED with
        AUTHENTICATION_PROOF_MISSING — the outcome §7.3.8 prescribes. A required
        positional parameter would raise TypeError and leave the caller with no
        admission result at all, which is not what this contract defines. The
        default MUST NOT be a value that can authenticate: it fails closed by
        construction, and NO argument, configuration or default makes its absence
        yield ACCEPTED. There is no unauthenticated success path.
```

```text
FROZEN: THE PROOF IS NOT PART OF THE RECORD. No field is added to EvidenceRecord,
        no canonical collection changes, no digest input changes, and the stored
        form is unchanged. The record schema is NOT what this amendment touches.
FROZEN: THE PROOF ENVELOPE IS OUTSIDE THE SIGNED INPUT. `message_b64u` and
        `signature` are not fields of the mapping and are not covered by the
        signature — a signature cannot cover itself, and the envelope that CARRIES
        the signed input is not part of it. What the signature covers is defined in
        §7.3.4 and nothing else.
FROZEN: the proof is NOT stored. §20.3's promotion copies a staged record's bytes
        unchanged; a proof is not among them, and this amendment adds no stored
        field that would carry one.
```

#### 7.3.4 The signed input, exactly

This is the definition a signer and a verifier must agree on byte for byte. It is
stated as bytes and ordering rather than as an instruction to "sign the mapping",
because an instruction admits two readings and two readings are two formats.

```text
DOMAIN_TAG      the ASCII bytes  workbench.evidence.producer-proof
PROOF_VERSION   the ASCII bytes  1
SEPARATOR       a single 0x00 byte

signed_input(mapping) =
        DOMAIN_TAG
     || SEPARATOR
     || PROOF_VERSION
     || SEPARATOR
     || canonical_serialization(mapping) encoded as UTF-8

and the message a producer signs, and a verifier checks, is exactly those bytes.
```

```text
WHY THE SEPARATOR IS UNAMBIGUOUS: canonical_serialization emits JSON, and JSON
escapes every control character below U+0020 as a \uXXXX sequence. A raw 0x00 byte
therefore CANNOT appear in the serialized mapping, so the two separators are
positions and not merely conventions — no mapping content can forge one.
```

```text
FROZEN: DOMAIN SEPARATION IS EXPLICIT AND IS PART OF THE SIGNED INPUT. The tag
        states which protocol the bytes belong to, and it is covered by the
        signature rather than checked beside it.
FROZEN: WHAT THE TAG GUARANTEES, STATED PRECISELY RATHER THAN UNIVERSALLY. A prefix
        cannot make a signature unverifiable in the abstract; it fixes the one
        preimage shape THIS verifier accepts. The guarantee is therefore narrower
        than "no signature can ever be reused", and is exactly this:
            this verifier reconstructs signed_input from the submitted mapping —
              including the expected DOMAIN_TAG and PROOF_VERSION — and accepts
              only a carried message that equals it BYTE FOR BYTE
            a signature over any other byte sequence verifies only if that
              sequence IS byte-identical to this protocol's expected preimage
        Separation is therefore bought by two protocols using two DIFFERENT tags,
        and no single protocol can buy it alone. It is stated as what it is: an
        OBLIGATION ON ANY OTHER PROTOCOL that shares key material with this one to
        use its own distinct DOMAIN_TAG. The tag is 33 ASCII bytes, and its hex is
        given in §7.3.6's vectors.
FROZEN: PROOF_VERSION IS PART OF THE SIGNED INPUT AND IS NOT NEGOTIATED. A
        verifier implements the versions it implements and no others; a carried
        message built under another version does not equal the verifier's own
        reconstruction and fails §7.3.5's comparison. There is no downgrade path,
        no "try each version", and no accepted-but-unverified version.
```

```text
FROZEN: WHAT THE SIGNED INPUT CONTAINS. It is the COMPLETE SUPPLIED MAPPING — every
        top-level field §30 admits and every nested supplied field — serialized as
        one value. It therefore covers, among everything else:
            provenance.producer          the claimed token, so re-pointing a proof
                                         at another producer changes the bytes
            identity.kind                and the payload, so kind and family are
            payload.family                 covered
            provenance.workspace_id      the record's scope
            provenance.actor             attribution, as authored
        No security-relevant supplied field is outside it.
FROZEN: AI-05-GENERATED VALUES ARE ABSENT BY CONSTRUCTION. §30 step 10 already
        REJECTS a supplied `content_digest`, `record_digest` or
        `ContextRef.value_digest`, and `evidence_id` is generated at step 13. The
        signed input therefore never contains a value AI-05 will later compute,
        and it does not depend on one.
FROZEN: NO UNSIGNED ACCEPTED FIELD. §30 step 1 REJECTS a field the contract does
        not define rather than ignoring it ("a field that is silently dropped
        cannot be audited"), and every per-type parse is closed-keyed. Combined
        with the clause above, it follows that every field of an ACCEPTED record
        was inside the signed input. There is no accepted field a signature does
        not cover.
```

#### 7.3.5 Verification, as two separate operations

```text
V1  THE PROOF ENVELOPE IS VALIDATED. `message_b64u` is a string in the Base64url
    alphabet with no padding; `signature` is exactly 128 lowercase hexadecimal
    characters. A failure here is AUTHENTICATION_PROOF_MALFORMED.
V2  THE CLAIMED PRODUCER IS READ. `provenance` is read as an object and
    `provenance.producer` as a non-empty string, from the SUPPLIED mapping. This is
    a read FOR KEY SELECTION, and it is the only part of the record inspected
    before authentication. A failure here is NOT an authentication failure: it
    takes the shape reason §7.3.8 assigns it. NO KEY LOOKUP AND NO CRYPTOGRAPHY
    PROCEED WITHOUT A READABLE PRODUCER TOKEN.
V3  THE DESIGNATED MAPPING IS CONSULTED for that token (§7.3.2). No designated
    mapping at all, or no entry for the claimed token, is
    AUTHENTICATION_KEY_UNAVAILABLE.
V4  message_b64u IS DECODED STRICTLY, and the signature is checked against THAT
    key over the DECODED BYTES. A malformed or non-canonical encoding is
    AUTHENTICATION_PROOF_MALFORMED; a signature that does not verify is
    AUTHENTICATION_SIGNATURE_INVALID.
V5  THE VERIFIER RECONSTRUCTS signed_input FROM THE SUBMITTED MAPPING and requires
    exact byte equality with the decoded carried message. Bytes that differ are
    AUTHENTICATION_INPUT_MISMATCH. A submitted mapping that has NO canonical
    serialization at all under §7.3.6 is AUTHENTICATION_INPUT_UNSERIALIZABLE —
    a DIFFERENT failure from "the bytes differ", because here there are no bytes
    to compare.
```

```text
FROZEN: V4 AND V5 ARE DIFFERENT OPERATIONS AND BOTH MUST PASS. V4 proves a
        signature by a key holder; V5 proves the signed bytes are THIS submission.
        Neither implies the other, and a design that ran only one would accept
        either a proof for a different record or an unsigned submission.
FROZEN: V4 IS PERFORMED OVER BYTES THE VERIFIER HAS OBTAINED — the decoded carried
        message — and never over bytes it has not yet reconstructed. Any
        description of this mechanism that places verification before the verifier
        holds the message is wrong about the mechanism.
FROZEN: V2's READ IS A PRECONDITION, NOT A SECOND SHAPE RULE. Step 7b runs before
        typed construction, so it cannot rely on construction's checks having run.
        It therefore reads exactly two things — that `provenance` is an object and
        that `provenance.producer` is a non-empty string — and reports failure with
        the SAME reason codes construction would report for the same defect. The
        FULL shape, required-field, vocabulary and class checks remain
        construction's (§30 steps 1-4, 4b, 6), and this clause neither replaces,
        duplicates nor weakens any of them. §14.10's rule set is likewise untouched:
        `check_admission_rules` returns early for a non-mapping precisely because
        shape is not its question, and V2 does not make it one.
FROZEN: A SUBMISSION WHOSE PRODUCER TOKEN CANNOT BE READ IS REJECTED, and it is
        rejected BEFORE any key lookup, any decoding of proof material and any
        signature verification. It MUST NOT raise an unhandled exception and MUST
        NOT produce an unspecified result: an unreadable producer is an ordinary
        REJECTED outcome with an existing shape reason.
```

#### 7.3.6 The canonical serialization — AI-05-CJ-1

The signed input needs a serialization that determines bytes, not one that is merely
deterministic in practice. Naming properties is not defining a format: two
implementations can agree on "sorted keys, no whitespace, no NaN" and still disagree
about escaping or number rendering, and a proof that verifies in a test then fails in
a deployment — or, worse, verifies against bytes that are not the record.

```text
THE PROFILE IS NAMED AND VERSIONED:  AI-05-CJ-1
ITS BASIS IS A PUBLISHED STANDARD:   RFC 8785, JSON Canonicalization Scheme (JCS)

USING A PUBLISHED STANDARD, RATHER THAN THIS DOCUMENT'S OWN PROSE, IS THE POINT.
        A format specified by a document that a neighbouring phase's implementation
        can drift away from is not normative. RFC 8785 fixes key order, escaping,
        encoding and number rendering, and it is maintained outside this
        repository, so AI-05 depends on a SPECIFICATION rather than on an
        implementation happening to stay still.
```

**The compatibility evaluation, and its one result.** RFC 8785 operates on the I-JSON
data model, whose numbers are IEEE-754 doubles, so integers are bounded to
±(2^53 − 1). The Evidence input domain is **not** bounded that way: §11.1's `ordinal`
is validated by `g_ordinal`, which requires a non-negative integer and imposes **no
upper bound** (`plugins/evidence/grammar.py:380-392`). A large integer is therefore
admissible Evidence input today, and adopting RFC 8785 unchanged would reject input
the existing contract admits — a schema change this amendment has no mandate to make.

```text
FROZEN: AI-05-CJ-1's WIRE FORMAT IS RFC 8785 WITH EXACTLY ONE EXTENSION, AND NO
        OTHER. The extension is in the NUMBER DOMAIN and nowhere else:

        INTEGERS   are serialized in PLAIN DECIMAL with arbitrary precision — an
                   optional leading '-' and digits, no exponent, no leading zeros,
                   no '+', no decimal point. This SUPERSET of RFC 8785's number
                   domain is what preserves `g_ordinal`'s existing bound.
                   WHERE RFC 8785 AND AI-05-CJ-1 DIFFER ON THE WIRE, THEY DIFFER
                   HERE AND ONLY HERE, and the difference is recorded rather than
                   implied.

        EVERYTHING ELSE IS RFC 8785 VERBATIM, and is restated below so that an
        implementer needs no second document.
```

```text
FROZEN: THE INPUT ADAPTERS ARE NOT WIRE-FORMAT EXTENSIONS, AND THE DISTINCTION IS
        NOT PEDANTRY. Rule 1 below maps some PYTHON representations onto the JSON
        data model. An adapter is not an extension when the bytes it produces are
        the bytes RFC 8785 would produce for an equivalent plain value, and each
        adapter here satisfies that:

            StrEnum member    renders as its canonical STRING value — the same
                              bytes a plain `str` of that value produces. RFC 8785
                              has no notion of an enum and needs none: it receives
                              a string.
            tuple             renders as a JSON array — the same bytes a `list` of
                              the same items produces. JSON has no tuple.
            bool              dispatches BEFORE the integer rule, so True renders
                              as `true` and never as `1`. This is a DISPATCH rule
                              for a Python quirk (`isinstance(True, int)` is True),
                              not a serialization choice: JSON's booleans are
                              RFC 8785's.
            Mapping           renders as a JSON object; its key ORDER is rule 2's,
                              not the mapping's insertion order.

        NO ADAPTER MAY PRODUCE BYTES A PLAIN VALUE COULD NOT. An adapter that did
        would be an EXTENSION, and it would have to be listed with the integer
        extension above and versioned with the profile. There is none, and adding
        one is precisely the breaking change §7.3.6's version governance covers —
        so the claim "exactly one extension" is checkable rather than a slogan: an
        adapter changes WHICH PYTHON VALUE reaches the encoder, never WHAT BYTES
        the encoder emits for a value of that JSON type.
```

```text
THE COMPLETE NORMATIVE RULES — AI-05-CJ-1, version 1

 1 ACCEPTED TYPES, and their rendering
       object (Mapping)   -> a JSON object; keys are strings
       array  (list/tuple) -> a JSON array; ORDER IS PRESERVED, not sorted
       string (str)       -> a JSON string (§4 below)
       integer (int)      -> plain decimal, arbitrary precision (§7 below)
       boolean (bool)     -> true | false. A bool is NOT an integer: it MUST be
                             rendered as a boolean and MUST NOT reach the integer
                             rule, which in Python it would otherwise satisfy
       null (None)        -> null
       enum (StrEnum)     -> the member's canonical string value. RFC 8785 does
                             not know enums; rendering the member's value is this
                             profile's rule, and it matches the value the same
                             field carries once parsed.
    EVERY OTHER TYPE IS OUT OF DOMAIN and is REFUSED, never coerced: float,
    Decimal, bytes, set, frozenset, datetime, and any object without a rule above.

 2 OBJECT KEY ORDERING — RFC 8785: keys sorted by their UTF-16 CODE UNITS,
    compared as unsigned 16-bit values, shorter-first on a prefix.
    NOTE, and it is a real trap: this is NOT the same as Unicode code-point order,
    which is what a naive `sorted()` over Python strings produces. The two orders
    differ only for keys containing characters ABOVE the BMP. Every field name the
    Evidence schema admits is ASCII, so on conforming input the two orders
    coincide — the normative rule is nevertheless RFC 8785's, and an implementation
    that sorts by code point is non-conforming even where the output matches.

 3 UNICODE NORMALIZATION — NONE. RFC 8785 forbids it and so does this profile. A
    string is serialized as the code points it carries. Two strings that are
    canonically equivalent but differently composed — "é" as U+00E9 and as
    U+0065 U+0301 — are DIFFERENT strings, produce DIFFERENT bytes, and are
    different signed inputs. Signers MUST NOT normalize, and verifiers MUST NOT
    either.

 4 STRING ESCAPING — RFC 8785's minimal set, and NOTHING ELSE is escaped:
       U+0022  "   ->  \"          U+005C  \   ->  \\
       U+0008      ->  \b          U+0009      ->  \t
       U+000A      ->  \n          U+000C      ->  \f
       U+000D      ->  \r
       other U+0000..U+001F        ->  \u00xx with LOWERCASE hex digits
    EVERY other character is emitted LITERALLY, including U+007F and every
    non-ASCII character. Non-ASCII is NEVER \u-escaped: "café" is five UTF-8 bytes
    (63 61 66 c3 a9), not eleven ASCII characters. A solidus '/' is NOT escaped.
    Hex digits in \u escapes are LOWERCASE.

 5 UTF-8 ENCODING — the serialized text is encoded as UTF-8 with no BOM and no
    normalization. This is the last step and produces the bytes that are signed.

 6 SEPARATORS AND WHITESPACE — ',' between array elements and between object
    members, ':' between a key and its value, and NO whitespace anywhere outside
    string values. No trailing newline.

 7 NUMBERS — integers per the extension above. NEGATIVE ZERO, EXPONENT NOTATION,
    DECIMAL POINTS AND NON-FINITE VALUES CANNOT ARISE: the only numeric type in
    domain is `int`, so -0, 1e21, 1.0, NaN and Infinity are all OUT OF DOMAIN and
    are REFUSED by rule 1. RFC 8785's ES6 number-rendering rules are therefore
    never exercised on conforming input, and this profile does not restate them.

 8 DUPLICATE KEYS — NOT REPRESENTABLE. Both entry points take a MAPPING, and a
    Python Mapping cannot carry one key twice, so the case cannot arise at the API.
    A transport that delivers a record as JSON TEXT MUST refuse a duplicate key
    rather than keeping the last one: keeping the last is a silent choice about
    which value was signed, and this repository refuses silent choices.

 9 INVALID UNICODE — a string containing an UNPAIRED SURROGATE is OUT OF DOMAIN
    and is REFUSED. Such a string is not encodable as UTF-8, so rule 5 cannot be
    applied to it. (Noted for the record, not as a change: the EXISTING digest path
    would fail on such a value at §30 step 12 rather than refuse it at admission.
    §7.3.7 puts authentication before construction, so on the authenticated path
    this profile refuses it first, as an AUTHENTICATION_INPUT_UNSERIALIZABLE
    result rather than a thrown exception.)

10 UNKNOWN FIELDS — a serialization concern only in that they are serialized like
    any other key. They are NOT ignored: §30 step 1 REJECTS them, and §7.3.4
    records that no ACCEPTED record carries a field outside the signed input.
```

```text
FROZEN: WHAT IS UNSERIALIZABLE IS REJECTED, NOT APPROXIMATED. If the submitted
        mapping is out of domain under rules 1, 5 or 9, no canonical bytes exist,
        V5 cannot form a comparison, and the submission is REJECTED with
        AUTHENTICATION_INPUT_UNSERIALIZABLE. It MUST NOT be coerced, partially
        serialized, skipped or repaired — a coercion would mean the producer and
        the verifier signed different bytes while both believing otherwise.
FROZEN: THIS PROFILE IS NEW AND CHANGES NOTHING THAT EXISTS. §15.2's digest input,
        §14.6.1's generated digests and the stored form's serialization are
        UNCHANGED and continue to use what they used before. AI-05-CJ-1 governs the
        SIGNED INPUT and nothing else — a different function, over a different
        value, for a different purpose. Unifying the two is NOT proposed here, and
        would be a separate amendment with its own compatibility argument.
FROZEN: A CHANGE TO AI-05-CJ-1 IS A BREAKING CHANGE TO THIS PROTOCOL AND REQUIRES
        A NEW PROOF_VERSION. It is not a refactor. The version is inside the signed
        input, so a verifier that reconstructs under a changed profile produces
        different bytes, the comparison fails, and the submission is REJECTED —
        the correct and visible outcome, not a silent mis-verification. A change
        that alters the serialization of ANY field the signed input covers is such
        a change, whether or not it alters the field's meaning. Profile and version
        move together or neither moves.
```

**Normative test vectors.** These are computed values, given so that an implementation
can be checked against the profile rather than against a description of it. Byte
strings are hexadecimal; `‖` marks a concatenation boundary and is not a byte.

```text
LINE WRAPPING IN THIS BLOCK IS PRESENTATION ONLY. The hex, the Base64url and the
canonical text below are WRAPPED TO FIT THE PAGE. None of them contains a line
break; a line break is NEVER part of a signed input, of a canonical serialization,
or of an encoded value, and a reader MUST NOT treat the wrap points as bytes.
Where a length is stated, it is the length of the UNWRAPPED value. The one place
this document shows a canonical serialization on more than one line is VECTOR 1,
and that vector also gives the same text on a single line so the two can be
compared.
```

```text
THE FIXED PREFIX — the same in every vector, and what the domain/version rule costs:
    DOMAIN_TAG     776f726b62656e63682e65766964656e63652e70726f64756365722d70726f6f66
                   (33 ASCII bytes: "workbench.evidence.producer-proof")
    SEPARATOR      00
    PROOF_VERSION  31            ("1")
    SEPARATOR      00
    so every signed input begins 776f...726f6f66 00 31 00
```

```text
VECTOR 1 — ASCII, nested objects, and key ordering that is NOT the input's order

    mapping (as supplied, deliberately unsorted)
        {"schema_version":1,"kind":"OBSERVATION",
         "provenance":{"producer":"ai-03","producer_type":"service",
                       "workspace_id":"ws-1"},
         "payload":{"family":"SOURCE_READ"}}

    AI-05-CJ-1 canonical text, 158 characters, ON ONE PHYSICAL LINE, with no
    whitespace outside the string values. The line below is that line:

{"kind":"OBSERVATION","payload":{"family":"SOURCE_READ"},"provenance":{"producer":"ai-03","producer_type":"service","workspace_id":"ws-1"},"schema_version":1}

    The same text, wrapped at the same points as the rest of this block, for
    comparison — the wrap points are NOT in the value:

        {"kind":"OBSERVATION","payload":{"family":"SOURCE_READ"},"provenance":
        {"producer":"ai-03","producer_type":"service","workspace_id":"ws-1"},
        "schema_version":1}

      sha256 over its UTF-8 bytes, for cross-checking only:
        f4a1d5fcd69667991fde630a1df304c0d704926986e307a2203de6d3bb33e1ec

    SIGNED INPUT, 194 bytes
        776f726b62656e63682e65766964656e63652e70726f64756365722d70726f6f66
        0031 00
        7b226b696e64223a224f42534552564154494f4e222c227061796c6f6164223a7b
        2266616d696c79223a22534f555243455f52454144227d2c2270726f76656e616e
        6365223a7b2270726f6475636572223a2261692d3033222c2270726f6475636572
        5f74797065223a2273657276696365222c22776f726b73706163655f6964223a22
        77732d31227d2c22736368656d615f76657273696f6e223a317d

    message_b64u, 259 characters
        d29ya2JlbmNoLmV2aWRlbmNlLnByb2R1Y2VyLXByb29mADEAeyJraW5kIjoiT0JTRVJW
        QVRJT04iLCJwYXlsb2FkIjp7ImZhbWlseSI6IlNPVVJDRV9SRUFEIn0sInByb3ZlbmFu
        Y2UiOnsicHJvZHVjZXIiOiJhaS0wMyIsInByb2R1Y2VyX3R5cGUiOiJzZXJ2aWNlIiwid2
        9ya3NwYWNlX2lkIjoid3MtMSJ9LCJzY2hlbWFfdmVyc2lvbiI6MX0
      (wrapped here for the page; the value carries NO line breaks)
```

```text
VECTOR 2 — a NON-ASCII string, and the rule that matters for it

    mapping
        {"payload":{"subject":"café"},"kind":"OBSERVATION","schema_version":1}
      where "café" is c,a,f,U+00E9 (NFC — NOT normalized, see rule 3)

    AI-05-CJ-1 canonical text
        {"kind":"OBSERVATION","payload":{"subject":"café"},"schema_version":1}

    the "café" value's UTF-8 bytes, and the whole point of the vector
        63 61 66 c3 a9         <- FIVE bytes. NOT é, NOT c3 83 c2 a9
        22 63 61 66 c3 a9 22   <- as it appears inside the canonical text

    SIGNED INPUT (prefix, then the canonical bytes)
        776f726b62656e63682e65766964656e63652e70726f64756365722d70726f6f66
        0031 00
        7b226b696e64223a224f42534552564154494f4e222c227061796c6f6164223a7b
        227375626a656374223a22636166 c3a9 227d2c22736368656d615f7665727369
        6f6e223a317d

    message_b64u
        d29ya2JlbmNoLmV2aWRlbmNlLnByb2R1Y2VyLXByb29mADEAeyJraW5kIjoiT0JTRVJW
        QVRJT04iLCJwYXlsb2FkIjp7InN1YmplY3QiOiJjYWbDqSJ9LCJzY2hlbWFfdmVyc2lv
        biI6MX0
      (the fragment "YWbDqS" is where "café" is carried — 9 bytes of Base64url for
       5 bytes of UTF-8)
```

```text
VECTOR 3 — NEGATIVE CONTROL: the version is covered by the signature

    Same mapping as VECTOR 1, with PROOF_VERSION "2" instead of "1".

    MESSAGE B — the version-2 signed input, identical to VECTOR 1 EXCEPT ONE byte
        776f...726f6f66 00 32 00 7b226b696e64...317d
                            ^^
        byte offset 34, hexadecimal 32 ("2") where VECTOR 1 has 31 ("1")

    THE TWO CASES ARE DIFFERENT TESTS AND HAVE DIFFERENT EXPECTED RESULTS. §7.3.5
    runs V4 (signature over the decoded carried bytes) BEFORE V5 (compare the
    decoded carried bytes to the reconstruction), so WHICH CASE a submission falls
    into decides WHICH STEP refuses it. A vector that assigned one result to both
    would be testing the wrong stage in one of them.

    CASE A — MESSAGE B CARRIED WITH VECTOR 1's SIGNATURE (sig_A)
        V4 checks sig_A over message B's decoded bytes. It does not verify: sig_A
        was produced over message A. V5 is NEVER REACHED, and a verifier that
        reported a mismatch here would have compared before verifying.
            EXPECTED   AUTHENTICATION_SIGNATURE_INVALID

    CASE B — MESSAGE B CARRIED WITH A VALID SIGNATURE OVER MESSAGE B (sig_B),
             SUBMITTED TO A VERIFIER CONFIGURED FOR PROOF_VERSION "1"
        V4 succeeds — sig_B is valid over message B under the key the mapping
        holds for the token the record names. V5 then reconstructs the expected
        signed input from the submitted mapping. The mapping is unchanged and
        carries no version of its own, so the reconstruction uses the VERIFIER's
        version literal and begins 00 31 00, while the decoded carried message
        begins 00 32 00. They differ at offset 34.
            EXPECTED   AUTHENTICATION_INPUT_MISMATCH

    WHAT THE PAIR PROVES  the version is INSIDE the signed bytes, so a version
        cannot be changed, downgraded or upgraded without invalidating every proof
        minted under the other one (case B), AND a proof whose message was altered
        after signing is refused at the signature rather than at the comparison
        (case A). This is what §7.3.4's "PROOF_VERSION IS PART OF THE SIGNED INPUT
        AND IS NOT NEGOTIATED" requires. There is NO version negotiation, NO
        downgrade fallback and NO "try each version": a verifier implements the
        versions it implements and refuses everything else at one of these two
        steps.

VECTOR 4 — NEGATIVE CONTROL: the domain tag is covered by the signature

    Byte 0 is replaced by 78 ("x"), so the leading bytes are no longer
    "workbench.evidence.producer-proof". Same two cases, same expected results,
    by the same reasoning:

        CASE A  the altered-tag message carried with VECTOR 1's signature
                EXPECTED   AUTHENTICATION_SIGNATURE_INVALID
        CASE B  a valid signature over the altered-tag message, submitted to a
                verifier expecting the original tag
                EXPECTED   AUTHENTICATION_INPUT_MISMATCH
                (V5 reconstruction differs at offset 0)

    The pair proves for the domain tag exactly what VECTOR 3 proves for the
    version.

SIGNATURES USED, STATED BECAUSE BOTH VECTORS TURN ON THEM

    sig_A   a valid Ed25519 signature over VECTOR 1's signed input, under the test
            producer key for the token VECTOR 1 names
    sig_B   a valid Ed25519 signature over the ALTERED signed input (version-2 in
            VECTOR 3, altered-tag in VECTOR 4), under the SAME test producer key

    NO SIGNATURE VALUE IS PRINTED, and none is normative here. These vectors fix
    the BYTES a verifier compares and WHICH STEP refuses a submission; the
    signature is whatever the test key produces, and printing one would invite it
    to be copied as a fixed value when it is not. sig_A and sig_B are NAMES for
    "a valid signature over X", not constants.
```

#### 7.3.7 The order in which this runs, and the tests it obliges

```text
FROZEN: THE ORDER IS FIXED, AND IT IS STATED IN TERMS OF WHAT ACTUALLY RUNS WHERE.
        §30's NUMBERS IDENTIFY steps; they are NOT an execution order, and this
        section does not pretend otherwise. The order that runs is:

            1  §30 step 7         THE RULE SET, over the SUPPLIED values. This is
                                  the only EXISTING ADMISSION CHECK that runs
                                  BEFORE AUTHENTICATION, and `check_admission_rules`
                                  is written for exactly that position
                                  (admission.py:199).
                                  IT IS NOT THE ONLY THING THAT RUNS BEFORE
                                  CONSTRUCTION: step 7b runs there too, and so do
                                  its §7.3.5 V1 and V2 — envelope validation and
                                  the producer-token read. What is unique to step 7
                                  is that it is the one ADMISSION check already in
                                  the contract that precedes authentication
            2  §30 step 7b        PRODUCER AUTHENTICATION — this section. No
                                  implementation of it exists anywhere
            3  §30 steps 1-4, 4b, 6, 8-11
                                  TYPED CONSTRUCTION, inside
                                  `EvidenceRecord.from_mapping` (models.py): the
                                  shape, required-field, closed-key, vocabulary
                                  and class checks, the §6.5/§6.6 cross-field
                                  check, and reference and artifact parsing. It
                                  ALSO derives ContextRef.value_digest. It does
                                  NOT compute content_digest or record_digest —
                                  it builds `integrity=Integrity()`, empty
            4  §30 step 13        EVIDENCE IDENTITY, ALSO inside `from_mapping`
                                  (`new_evidence_id()`, models.py:1698) and
                                  therefore BEFORE step 12, whose number is lower.
                                  The inversion is the implementation's and is
                                  RECORDED here, not reordered
            5  §30 step 5         WORKSPACE AGREEMENT, in
                                  `check_workspace_agreement` (admission.py:201).
                                  It runs AFTER construction because it compares
                                  fields on the constructed record
            6  §30 step 12        content_digest and record_digest, in
                                  `assign_digests` (digests.py:65, called at
                                  admission.py:202). THIS is the only place the
                                  two record-level Evidence digests are computed
            7  §30 step 14        DUPLICATE CHECK, then the store
                                  (admission.py:271, :276)
```

```text
FROZEN: NO STEP APPEARS IN TWO STAGES. Steps 12 and 13 are executed by two DIFFERENT
        functions at two DIFFERENT points — 13 inside `from_mapping`, 12 inside
        `assign_digests` — and an earlier revision of this section attributed the
        range "8-13" to construction, which put step 12 in TWO places at once. THAT
        RANGE IS WITHDRAWN: construction covers 8-11 and 13, step 12 is stage 6 and
        nothing else, and no clause of this document may restore the range.
FROZEN: `ContextRef.value_digest` HAS NO §30 STEP NUMBER OF ITS OWN. §14.6.1 names
        it as AI-05-generated, and it is derived during construction, in
        `ContextRef.from_mapping` (models.py:414), from a value whose class check has
        already passed. §30 step 12 names `content_digest` and `record_digest` ONLY.
        This amendment does not renumber §30 and adds no step for it.
FROZEN: WITHIN A STAGE, THE ORDER AMONG THE STEPS THAT STAGE LISTS IS THE
        IMPLEMENTATION'S, and this section does not fix it. What it fixes is each
        step's position RELATIVE TO THE STAGES: authentication precedes
        construction, construction precedes the workspace agreement, step 13
        (identity) precedes step 12 (the two record digests), and step 12 precedes
        persistence. It does NOT fix — and MUST NOT be read as fixing — a
        statement-level order inside `from_mapping`, where the steps of stage 3 are
        interleaved by the parser rather than executed in numeric sequence.
```

```text
FROZEN: EXACTLY ONE CHECK HAS RUN WHEN AUTHENTICATION RUNS — STEP 7'S RULE SET.
        NO shape check, NO required-field check, NO class check, NO vocabulary
        check and NO §6.5/§6.6 registry check has run at that point: those are
        step 3's, and step 3 comes AFTER. No clause of this section may say or
        imply that "the class rules" have already passed when step 7b executes.
        The one thing step 7b needs from the record is the claimed producer token,
        and §7.3.5 V2 reads exactly that and nothing else.
FROZEN: THE POSITION IS FORCED BY §14.6 R2, AND THE ARGUMENT HAS TWO PARTS THAT
        MUST NOT BE MERGED:

            R2 FORCES STEP 7 FIRST. R2 forbids AI-05 computing a digest over a
              value it did not admit, and R2 defines "admitted" as "its class
              rules pass". Construction derives references.context[].value_digest
              from the supplied `value` (§12.1), so a value that has not passed the
              rule set must not reach construction.
            THIS CONTRACT ADDS STEP 7b BEFORE CONSTRUCTION. Construction is where a
              typed record comes into existence and where the first Evidence
              digest is derived. Neither may happen for a claim that has not been
              authenticated, so authentication precedes both — not because R2 says
              so, but because a record built from an unauthenticated claim should
              not be built at all.
        NOTHING HERE CLAIMS STEP 6 HAS RUN BEFORE STEP 7b. Step 6 runs INSIDE
        step 3, and within construction each field's class check precedes the
        digest derived from it: `ContextRef.from_mapping` validates `value` as text
        before deriving `value_digest` from it, so R2 holds per field as well as
        per stage.
```

```text
FROZEN: THREE OPERATIONS THAT MUST NOT BE CONFLATED, because "hashing" is used for
        all three in ordinary speech and the contract's rule is about ONE of them:

            deterministic serialization      produces the signed input. NOT a
                                             digest, and produces no Evidence
                                             field.
            Ed25519 signature verification   hashes its message internally. That is
                                             the ALGORITHM's compression, not an
                                             Evidence digest, and it produces no
                                             Evidence field. §14.6 R2 does not
                                             reach it.
            Evidence digest computation      content_digest, record_digest and
                                             ContextRef.value_digest. THIS is what
                                             R2 governs. It happens at §30 steps
                                             5 (value_digest, inside construction)
                                             and 12 (the other two) — BOTH after
                                             step 7's rule set and after
                                             authentication.
```

```text
FROZEN: WHAT IS GUARANTEED ON EVERY REJECTION PATH IN THIS SECTION:
            no Evidence digest over an unadmitted value — step 7's rule set ran
              first, and construction's per-field class checks precede the digest
              each field yields
            no persistent write — rejected input is never stored
            no store contact — the store is not touched on any non-ACCEPTED path
            no typed record and no final digest — steps 3, 5 and 12 are unreachable
              once step 7b rejects
        AND, STATED SO IT IS NOT OVER-CLAIMED: Ed25519 verification hashes its
        message. The guarantee is that no EVIDENCE digest is computed and nothing
        is persisted before authentication succeeds — NOT that no hashing occurs.
```

```text
FROZEN: THE TEST OBLIGATION THIS SECTION CREATES, for the implementation that
        follows it. Each of these is an acceptance test and each MUST exist before
        the standard may be reported as holding:
            a valid proof and an accepted producer claim
            no proof, and no designated mapping at all
            a mapping with no entry for the claimed token
            ONE PUBLIC KEY ASSIGNED TO TWO RECOGNIZED PRODUCER TOKENS, asserting
              that the designated reader REFUSES the mapping under BOTH reader
              policies, that no mapping is therefore designated, and that EVERY
              submission is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE —
              including a submission naming a token whose entry was not part of the
              collision, because the reader refuses the mapping rather than
              trimming it
            ONE PUBLIC KEY ASSIGNED TO A RECOGNIZED TOKEN AND TO AN UNREGISTERED
              ONE, asserting THE SAME outcome as the case above: BOTH policies
              REFUSE the WHOLE mapping, no mapping is designated, and every
              submission is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE. A test
              MUST NOT accept this mapping shape under POLICY A. Tolerating it would
              let the holder of the shared private key sign a claim naming the
              REGISTERED token — which verifies under that token's registered key
              and is ADMITTED by §6.6 — so the forgery lands on the registered
              token, not on the unregistered one, and refusing the unregistered
              token's own records does not touch it
            a mapping whose only duplicate public key involves tokens §6.5 does NOT
              register — AND ONLY SUCH TOKENS. §7.3.2 PERMITS TWO READER POLICIES
              for this one case, and the criterion MUST ACCEPT EITHER ONE — a test
              asserting a single outcome as the ONLY permitted one would FAIL a
              compliant deployment that chose the other:
                  POLICY A  the mapping stays usable, a signature over such a
                            token's claim MAY VERIFY, and §6.6 MUST then REFUSE the
                            record during construction
                  POLICY B  the mapping is refused over all entries, and the
                            submission MUST be REFUSED with
                            AUTHENTICATION_KEY_UNAVAILABLE, with NO signature
                            verification and NO construction
              Under BOTH policies the test MUST assert that a submission naming such
              a token is NOT ACCEPTED, that the token acquires NO §6.5 identity, and
              that the reader is CONSISTENT — refusing every duplicate of a kind or
              tolerating every duplicate of that kind, never a mixture
            EVERY fail-closed path in BOTH cases above MUST be asserted to refuse
              THE WHOLE MAPPING: no valid subset returned, no first-or-last entry
              kept, no warning-and-continue. A reader that trimmed the mapping would
              leave its surviving entries authenticating as though the collision had
              never existed
            a mapping in which EVERY entry holds DISTINCT key material — each
              recognized token distinct from every other entry, registered or not —
              asserting that the same submissions that failed above now succeed —
              the control that shows the three tests above are testing the collision
              rule and not merely the absence of a mapping
            a malformed envelope: a non-Base64url character, '=' padding, and a
              NON-CANONICAL encoding whose final quantum carries unused bits
            a signature that does not verify
            a signer using ANOTHER token's private key — the cross-producer case
            a proof replayed against a changed producer, kind, family, workspace
              or payload
            a mapping with NO canonical serialization under §7.3.6 — a value out
              of domain, and a string carrying an unpaired surrogate
            an unreadable producer token, asserting an EXISTING shape reason AND
              asserting that no key lookup occurred
            a proof omitted, and a proof passed as None, at BOTH entry points,
              each asserting REJECTED rather than TypeError
            an unknown or malformed field
            rejection without persistence and without store contact, at both
              entry points
            the EXACT APPROVED CALL-SITE SET (§7.3.13) — every production call site
              of `admit`/`admit_to_store` named INDIVIDUALLY, the BASELINE set
              being EMPTY and the CANDIDATE set EQUAL to what the connecting
              change declares. A COUNT-ONLY approval does NOT satisfy this. The
              obligation is not the mere absence of a writer: it is the presence
              of EXACTLY the authorised ones, which subsumes the absence case when
              the approved set is empty.
            the absence of any caller-selectable trust root
            no coupling from an authentication failure to a Guard outcome
            the reason-code precedence of §7.3.8 when step 7's published rule and
              authentication both fail
            AI-05-CJ-1's vectors (§7.3.6) reproduced BYTE FOR BYTE, including the
              non-ASCII vector and both negative controls
        Tests MUST use a distinct keypair per producer token and MUST go through
        the real verification path, supplied through the SAME designated
        configuration mechanism a deployment uses. A test-only bypass is
        FORBIDDEN.
        NO TEST IN THIS LIST HAS BEEN RUN. They are obligations on the
        implementation, not evidence about it.
```

#### 7.3.8 Failure semantics

```text
FROZEN: THE OUTCOME IS `REJECTED`. NO OUTCOME MEMBER IS ADDED. §22.1's three
        outcomes are unchanged, and this amendment adds none: an unauthenticated
        submission is a content violation, not a fourth kind of result.

FROZEN: SIX REASON CODES, ONE PER MANDATORY FAILURE CLASS, because a caller that
        cannot distinguish "you sent no proof" from "your key was removed" cannot
        act on either:

            AUTHENTICATION_PROOF_MISSING       no proof was supplied — the argument
                                               omitted, or passed as None
            AUTHENTICATION_PROOF_MALFORMED     the envelope is not well formed:
                                               `message_b64u` is not a string, is
                                               not in the Base64url alphabet, is
                                               padded, or is NON-CANONICAL on
                                               re-encoding; or `signature` is not
                                               exactly 128 lowercase hexadecimal
                                               characters
            AUTHENTICATION_KEY_UNAVAILABLE     no designated mapping, or no entry
                                               in it for the claimed token
            AUTHENTICATION_SIGNATURE_INVALID   the signature does not verify, under
                                               the designated key for that token,
                                               over the DECODED carried message
            AUTHENTICATION_INPUT_MISMATCH      the decoded carried message is not
                                               the signed input reconstructed from
                                               the submitted mapping
            AUTHENTICATION_INPUT_UNSERIALIZABLE
                                               the submitted mapping is OUT OF
                                               DOMAIN under §7.3.6, so no signed
                                               input exists to compare against.
                                               DISTINCT from _INPUT_MISMATCH:
                                               there bytes exist and differ; here
                                               there are no bytes at all

        These group under one authentication concern and remain DISTINCT labels.
        They are not reducible to one another and MUST NOT be collapsed into a
        single code. The last is a statement about the MAPPING, not about the
        producer token — an unreadable token is reported separately, below.
```

```text
FROZEN: AN UNREADABLE PRODUCER TOKEN IS NOT AN AUTHENTICATION FAILURE AND GETS NO
        CODE OF ITS OWN. §7.3.5 V2 must read `provenance` and `provenance.producer`
        before it can select a key, and step 7b runs before the checks that
        normally validate them. Rather than invent a parallel shape vocabulary,
        V2 reports the SAME reason the corresponding construction-time check
        reports, from codes §30 already defines:

            the supplied value is not a mapping       RECORD_MALFORMED
            `provenance` is absent or null            MISSING_REQUIRED_FIELD
            `provenance` is not an object             RECORD_MALFORMED
            `provenance.producer` is absent or null   MISSING_REQUIRED_FIELD
            `provenance.producer` is not a string,
              is empty, or is otherwise not the
              bounded text §7 requires                FIELD_CLASS_VIOLATION

        The outcome is REJECTED, and NO key lookup, NO decoding and NO signature
        verification occurs on any of these paths. This is not a second,
        disagreeing shape rule: it is a PRECONDITION READ whose failure carries the
        reason the full check would have carried, and the full check still runs at
        step 3 for every submission that gets that far.
```

```text
FROZEN: WHEN STEP 7'S RULE AND AUTHENTICATION BOTH FAIL, STEP 7's REASON IS THE ONE
        REPORTED. Step 7 runs before step 7b (§7.3.7), so a submission that trips a
        published rule AND carries a bad proof is REJECTED with the rule's
        reason_code and authentication is never reached. This is the same
        precedence §30 already records for a record violating both a shape rule and
        a published rule ("it reports the RULE"), and it is stated here because the
        precedence is observable.
FROZEN: WHAT THIS PRECEDENCE IS NOT. It is NOT a statement that "class validation"
        precedes authentication, because §30 step 6's class checks run INSIDE
        construction (step 3) and have NOT run when step 7b executes (§7.3.7). The
        only check that precedes authentication is step 7's rule set. A submission
        whose class checks would ALSO fail reaches step 7b unchecked on that axis,
        and is rejected there for whichever authentication reason applies — the
        class failure is never reached, and no clause may describe it as having
        been detected first.
FROZEN: THE STORE IS NOT CONTACTED ON ANY OF THESE PATHS. This is a property of
        the entry point rather than a promise: `admit()` takes no store at all,
        and `admit_to_store()` returns before touching one whenever the outcome is
        not ACCEPTED (§30 step 14's position).
FROZEN: AN AUTHENTICATION FAILURE IS NOT A GUARD DENY. It is not reported as one,
        not recorded as one, and not translated into one. Guard's vocabulary and
        Guard's outcomes are Guard's (§23), and this section adds no path from an
        Evidence outcome into them.
FROZEN: AUTHENTICATION IS NOT AUTHORIZATION. An authenticated producer claim is
        not a permission, not a capability, not a verification and not a
        measurement. It changes no row of any authority matrix and confers nothing
        on the producer, the submitter, the record or the deployment (§23, §24).
```

#### 7.3.9 Revocation, and the residual risks

```text
THE REVOCATION MODEL, AS IT ACTUALLY IS — stated plainly rather than implied:

    Revocation is performed by REMOVING the token's entry from the designated
    mapping and deploying the updated mapping. After that, no further claim naming
    that token can be authenticated.

    IT DOES NOT REACH BACKWARDS. This amendment provides no mechanism to
    invalidate, re-grade or re-examine a record that is already stored. A stored
    record stays readable, its digests stay valid, and no stored-form load re-runs
    admission over it (§17). A record admitted before a revocation is EXACTLY AS
    STRONG AS IT WAS WHEN ADMITTED, and no stronger.

    There is therefore NO time-bounded validity in this version, no certificate
    expiry and no revocation list. If a future requirement needs them, that is a
    further amendment and not an implication of this one.
```

```text
FROZEN: THE RESIDUAL RISKS, RECORDED SO THEY ARE NOT MISTAKEN FOR CLOSED:

    PROCESS CONTROL     an adversary who controls this process's address space can
                        control the mapping and defeat any in-process check. An
                        in-process library cannot defend its own address space,
                        and this section does not claim to survive such an
                        adversary. What it claims is that no API PATH lets a
                        caller choose the trust root.

    KEY CUSTODY         that a private key is held only by the party entitled to
                        speak for its token, and that the mapping is correct, are
                        TRUST ASSUMPTIONS. Key generation, storage, backup,
                        rotation and destruction are OUTSIDE this contract.

    KEY HOLDER, NOT     §7.3.1's limit, restated because it is the one most likely
      CODE COMPONENT    to be lost in a summary: this authenticates a key holder.
                        It does not establish which code ran.

    NOT SUBMITTER       producer authentication is not submitter identity (§7.2).
      IDENTITY
    NOT AUTHORIZATION   it is not a grant, a capability, a Guard verdict or a
                        verified measurement.
    NOT CONTENT TRUTH   it says who signed, never that the claim is true.
```

#### 7.3.10 What this section does not change

```text
FROZEN: §6.5's registry and §6.6's cross-field rules are UNCHANGED. They remain the
        recognition authority, they remain keyed by kind and family, and they
        continue to enforce exactly what they enforced before.
FROZEN: §7.2 and Amendment 4 are UNCHANGED. Reading A stands, the submitter may
        differ from the producer, and the three checks remain three.
FROZEN: §22.1's outcome vocabulary is UNCHANGED. §14.10's rule set, §14.2's field
        classes and the detection-not-sanitization rule are UNCHANGED.
FROZEN: the EvidenceRecord schema, the canonical collections, the digest inputs and
        the stored form are UNCHANGED. No field is added anywhere.
FROZEN: no producer token, registry row, Evidence kind, family, producer_type or
        admission outcome is added or removed. This section adds a CHECK and a
        PROOF CARRIER, and nothing else.
FROZEN: the mechanism defined here is AI-05's and is SEPARATE from human approval.
        AI-13's designated approval ingress (§13.3), its anchor and its Ed25519
        verification site are NOT repurposed, NOT read, and NOT widened by this
        section, and this section creates no approval path. Producer authenticity
        and human approval are different trust domains with different anchors.
FROZEN: the composition is NOT a party to this mechanism. It does not read the
        designated producer mapping, does not mint, hold or verify a proof, and
        acquires no authority, permission or capability from a producer claim
        being authenticated.
        ^ CLARIFIED BY §7.3.12 (Amendment 8): "hold" HERE MEANS CUSTODY FOR DECIDING
        WHAT IS TRUSTED — reading the mapping, selecting a key, reaching a verdict.
        TRANSPORTING a proof as opaque material is NOT that, and §7.3.12 states what
        a forwarder may and may not do with one. NO PROHIBITION IN THIS CLAUSE IS
        WEAKENED, WIDENED OR REWORDED by §7.3.12, and this clause is otherwise
        unchanged by it.
```

#### 7.3.11 The designated producer trust configuration — FROZEN (Amendment 6)

§7.3.2 fixes **what** the designated producer trust mapping is and what it may not be.
It requires the mapping to be read "from exactly ONE place, by exactly one module" and
records that a deployment with no mapping authenticates nothing. It does not name that
place or that module. **A mechanism described only by its properties is not
implementable**: an implementer must still choose a source, a format, an encoding and a
reader, and every one of those choices becomes a deployment interface that a proof is
verified against.

This section names them. It is the answer to the question §7.3.2 left open, and it
changes **no** clause of §7.3.1–§7.3.10.

```text
THE SOLE SOURCE — one environment variable, and nothing else

    WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG
```

```text
FROZEN: THIS VARIABLE IS THE ONLY PLACE THE DESIGNATED MAPPING IS READ FROM, and
        naming it is what satisfies §7.3.2's "read from exactly ONE place". There is
        no configuration file, no default path, no keyring, no network source, no
        build-time embed, no compiled-in mapping and no second environment variable.
        A deployment that supplies the mapping any other way has designated nothing,
        and §7.3.2's FAIL CLOSED clause applies.
FROZEN: THE ONE READER IS ONE MODULE, NAMED HERE:

    plugins/evidence/producer_auth.py

        It is the sole reader of WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG. It parses
        the value, validates it, holds the resulting state FOR THE LIFETIME OF THE
        PROCESS (§7.3.11's lifecycle rule), performs §7.3.5's V1-V5, and answers
        §7.3.2's "which key applies to this claimed token" for the verification site.
        A second module that reads this variable, or that decides what is trusted, is
        a second place the deployment's trust root is decided, and §7.3.2's ONE
        READER clause refuses it.
FROZEN: NO PUBLIC FUNCTION OF THIS MODULE, AND NO PUBLIC AI-05 FUNCTION ANYWHERE,
        ACCEPTS A PUBLIC KEY, A MAPPING, AN ANCHOR, A VERIFIER, A CONFIGURATION
        OBJECT OR A CONFIGURATION PATH AS A PARAMETER. §7.3.2 states the rule; this
        section records that the configuration does not create an exception to it.
        The environment is read, never handed in.
FROZEN: THE CONFIGURATION CARRIES PUBLIC KEY MATERIAL ONLY. It never carries, and
        the reader never accepts, a private signing key. The deployment holds
        verification keys and cannot mint the proofs it checks — the same boundary
        AI-13 §13.3 draws for its own anchor, drawn here independently for this one.
        A value that would place signing material in this configuration is not a
        valid configuration and MUST be refused as one (§7.3.11's validation rules).
```

```text
THE VALUE — a strict JSON object, and exactly two members

    {
      "collision_policy": "A" | "B",
      "producer_keys": { "<producer token>": "<64 lowercase hex characters>", ... }
    }

    collision_policy   REQUIRED. Exactly one of the two JSON strings "A" and "B".
                       It SELECTS between §7.3.2's POLICY A and POLICY B. It does
                       not define them, extend them, or restate them, and neither
                       policy's collision semantics are changed by this section
                       (§7.3.2, unmodified).

    producer_keys      REQUIRED. A JSON object mapping a producer-token string to
                       the Ed25519 PUBLIC key that this deployment associates with
                       that token. Each value is exactly 64 LOWERCASE hexadecimal
                       characters, decoding to 32 bytes. Uppercase hex is REFUSED,
                       never normalized — the same case policy §14.5.1 applies to a
                       Class 1 field, applied here for the same reason: a value AI-05
                       accepts is a value AI-05 must not rewrite.
```

```text
STRICT PARSING — the value is JSON, and JSON is not "close enough"

FROZEN: THE ROOT IS A JSON OBJECT AND NOTHING ELSE. An array, a string, a number,
        `true`, `false`, `null` or an empty value is NOT a configuration. A variable
        that is set but empty is not a configuration either.
FROZEN: DUPLICATE OBJECT KEYS ARE REFUSED, AT EVERY LEVEL, INCLUDING INSIDE
        `producer_keys`. `{"collision_policy":"A","collision_policy":"B"}` is a value
        that names two different policies while looking like one member, and a
        parser that keeps the last one has made a silent choice about which trust
        root the deployment holds. §7.3.6 rule 8 refuses a duplicate key on a
        transport that delivers a record as JSON text; this section applies the same
        rule to the one JSON document AI-05 reads for itself. A READING THAT KEEPS
        THE LAST KEY IS FORBIDDEN.
FROZEN: `NaN`, `Infinity` and `-Infinity` ARE NOT JSON AND ARE REFUSED. A parser
        that accepts them accepts input RFC 8259 does not define, and a value the
        grammar does not define has no meaning AI-05 may act on.
FROZEN: NO TRAILING CONTENT. The value parses as one JSON document and nothing
        follows it. Whitespace around and between tokens is insignificant and is
        permitted, because RFC 8259 permits it.
FROZEN: THE MEMBERS ARE CLOSED-KEYED AND BOTH ARE REQUIRED. An unknown member, an
        absent `collision_policy`, an absent `producer_keys`, a misspelled member
        name, or a member of the wrong JSON type is an INVALID CONFIGURATION. It is
        refused as a whole. §30 step 1 refuses an unknown field on a record because
        "a field that is silently dropped cannot be audited"; the same reasoning
        applies with more force to a trust configuration, where a dropped member is a
        trust decision nobody made.
FROZEN: A VALUE THAT IS NOT ENCODABLE AS UTF-8 IS REFUSED. §7.3.6 rule 9 refuses an
        unpaired surrogate in a signed input for the reason that rule 5 cannot be
        applied to it; this section refuses one here for the same reason.
```

```text
VALIDATION IS COMPLETE, AND PARTIAL ACCEPTANCE IS FORBIDDEN

FROZEN: THE MAPPING IS VALIDATED AS A WHOLE BEFORE ANY SUBMISSION IS AUTHENTICATED
        UNDER IT, and §7.3.2's group rule is applied to the WHOLE mapping. The reader
        MUST NOT authenticate against the entries it managed to parse, MUST NOT skip
        a malformed entry and continue, MUST NOT fall back to a default, a
        development mapping, a previously-cached mapping or a subset, and MUST NOT
        recover silently from an invalid configuration. §7.3.2's "no default
        mapping, no development mapping, no `verify=False` switch" is unchanged and
        this section adds no path around it.
FROZEN: A KEY ENTRY FOR A TOKEN §6.5 DOES NOT REGISTER IS PERMITTED, AND IS INERT.
        It creates no registry row, admits no event and confers no recognition
        (§7.3.2, §6.5). Its PRESENCE is nevertheless load-bearing, because it
        participates in the group rule below.
FROZEN: `producer_keys` MAY BE EMPTY. An empty object is a well-formed mapping that
        designates no key for any token; every submission is then REJECTED with
        AUTHENTICATION_KEY_UNAVAILABLE, which is the same outcome §7.3.2 assigns a
        deployment with no mapping at all. This is NOT the partial acceptance the
        clause above forbids: there is no entry for a partial reading to keep or drop.
FROZEN: WHICH TOKENS COUNT AS RECOGNIZED IS §6.5'S ANSWER AND NOT THIS SECTION'S.
        The reader consults the §6.5 admitted-producer registry to decide, for the
        group rule, whether a colliding group contains a recognized token. It does
        not restate the registry, does not cache a copy of it that could drift, and
        does not treat a `producer_keys` entry as evidence of recognition.
```

```text
THE COLLISION RULE IS §7.3.2'S, AND `collision_policy` ONLY SELECTS IT

FROZEN: THIS SECTION ADDS NO COLLISION SEMANTICS. §7.3.2's group rule, both reader
        policies, and the requirement that a reader be CONSISTENT are unchanged and
        are incorporated here by reference rather than restated:
            a duplicate public-key group containing AT LEAST ONE RECOGNIZED token
              makes the WHOLE MAPPING non-compliant and fails it closed under BOTH
              policies
            a duplicate group consisting ENTIRELY of unregistered tokens is the ONE
              case the two policies treat differently
FROZEN: WHAT `collision_policy` SELECTS, STATED SO A READER NEEDS NO SECOND DOCUMENT
            "A"   POLICY A — a group consisting only of unregistered tokens is
                  TOLERATED and the mapping stays usable; every group containing a
                  recognized token still fails the whole mapping closed
            "B"   POLICY B — the mapping is refused over ALL its entries on ANY
                  duplicate public key, including one that involves only
                  unregistered tokens
FROZEN: THE SELECTOR IS A DEPLOYMENT FACT AND NOT A CALLER'S CHOICE. §7.3.2 records
        that "which policy a deployment runs is a DEPLOYMENT FACT, not a choice any
        caller makes". This is where that fact is expressed, and it is expressed in
        the same place and by the same mechanism as the key material — which is the
        point: a caller cannot reach it either way.
FROZEN: WHEN THE READER REFUSES THE MAPPING, IT REFUSES IT WHOLE. No valid subset is
        returned, no first-or-last entry is kept, nothing is warned about and
        continued past (§7.3.2). The deployment then has NO usable designated
        mapping, which is what the failure rule below reports.
```

```text
FAILURE — ONE EXISTING REASON CODE, AND NO SEVENTH

FROZEN: A MISSING, MALFORMED, INCOMPLETE, UNPARSEABLE OR OTHERWISE INVALID
        CONFIGURATION IS REPORTED AS AUTHENTICATION_KEY_UNAVAILABLE, AND SO IS A
        MAPPING THE READER REFUSES. This is not a new code and MUST NOT become one:
        §7.3.8 fixes SIX codes and states that no outcome member is added, and
        §7.3.5's V3 already assigns this exact code to "no designated mapping at all,
        or no entry for the claimed token". A refused mapping is a deployment
        with no usable mapping, and this section reports it where §7.3.2 and §7.3.5
        already report that state.
FROZEN: A DEPLOYMENT MISCONFIGURATION IS NOT A DISTINCT OUTCOME, A DISTINCT
        SECURITY EVENT, OR A GUARD RESULT. It is REJECTED, it is not recorded as a
        Guard DENY, it is not translated into one, and it confers nothing on the
        producer, the submitter, the record or the deployment (§7.3.8).
FROZEN: THE EXISTING SIX CODES AND THEIR ORDER ARE UNCHANGED, AND CONFIGURATION
        FAILURE DOES NOT JUMP THE QUEUE. §7.3.5 runs V1 before V2 before V3, and this
        section does not reorder it: a submission whose proof ENVELOPE is malformed
        is reported AUTHENTICATION_PROOF_MALFORMED even when the configuration is
        also invalid, and a submission whose producer token is UNREADABLE is reported
        with an existing shape reason even when the configuration is also invalid —
        because V2 runs before V3 and performs no key lookup. Reading and validating
        the configuration does not move ahead of a check §7.3.5 places before it.
FROZEN: AN INVALID CONFIGURATION AFFECTS EVERY SUBMISSION EQUALLY. There is no
        submission, no token, no kind, no family and no caller for which an invalid
        configuration yields an ACCEPTED result or a different code.
```

```text
ONE INITIALIZATION, ONE PROCESS-LIFETIME SNAPSHOT

FROZEN: THE CONFIGURATION IS READ AND VALIDATED EXACTLY ONCE, DURING THE
        INITIALIZATION OF THE ONE READER MODULE, AND THE STATE IT PRODUCES IS THE
        SOLE AUTHORITY ON THE DEPLOYMENT'S TRUST ROOT FOR THE LIFETIME OF THAT
        PROCESS. There is NO FUNCTION that reads the variable: the read IS the
        module's own initialization, and it does not repeat. Key selection, the group
        rule and the policy the reader enforces are decided against that ONE value,
        for every admission that process ever performs.
FROZEN: THE STATE HAS EXACTLY TWO SHAPES, AND BOTH ARE FINAL.

            VALID     the mapping parsed and validated; it is used as it stands
            INVALID   the value was absent, malformed, incomplete, unparseable or
                      otherwise invalid, OR the reader refused the mapping under
                      §7.3.2's group rule

        AN INVALID STATE IS RETAINED AS INVALID. Every admission that reaches V3
        under it is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE — the same code, for
        every submission, for the rest of that process.
FROZEN: INITIALIZATION DOES NOT RAISE. An invalid configuration at startup is a STATE
        the process holds, not an exception it throws and not a failure to import. A
        reader whose import raised would leave the caller with no admission result at
        all, and would make a deployment misconfiguration appear as a programming
        error rather than as the REJECTED outcome §7.3.8 defines. The module
        initializes, records INVALID, and answers every question about "which key
        applies" with "none".
FROZEN: THE ENVIRONMENT IS A DEPLOYMENT INPUT AND NOT A CONTROL SURFACE. No
        repository code outside the trusted deployment mechanism assigns, mutates,
        unsets or otherwise writes this variable, and the reader module is not
        reloaded to re-trigger its initialization. The variable is set by whatever
        starts the process; code under this repository's control READS it and does not
        write it. §31.3 states the static obligation that enforces this.
FROZEN: A CONFIGURATION UPDATE TAKES EFFECT ONLY THROUGH A CONTROLLED PROCESS
        RESTART. That is what "deploying the updated mapping" MEANS in §7.3.9, and
        this section does not change §7.3.9's revocation model — it fixes how the
        updated mapping ARRIVES. Removing a token's entry and deploying the updated
        mapping stops that token's further claims because the RESTARTED process
        initializes from the new value; the process that has not restarted continues
        to authenticate under the mapping it started with, which is the same
        non-retroactivity §7.3.9's "IT DOES NOT REACH BACKWARDS" already provides for
        the records it admitted.
FROZEN: A LATER CHANGE TO THE VARIABLE DOES NOT RELOAD THE TRUST ROOT, AND THIS IS
        NOT A CACHE WITH A REFRESH PATH. There is no re-read, no TTL, no
        invalidation hook, no signal handler, no "reload configuration" function, and
        no path by which a second value reaches the reader.
FROZEN: `admit_to_store()` PERFORMS NO SECOND VERIFICATION AND THEREFORE CONSULTS NO
        SECOND STATE. It passes the proof through to `admit()` (§7.3.3) and one
        verdict is reached from the one process-lifetime value.
```

```text
WHEN THE READ HAPPENS, AND WHY THAT ORDER IS THE POINT

FROZEN: THE IMPLEMENTATION MUST INITIALIZE THE READER THROUGH THE EVIDENCE PACKAGE'S
        OWN INITIALIZATION PATH, BEFORE EITHER ADMISSION ENTRY POINT IS AVAILABLE.
        `plugins/evidence/__init__.py` MUST import `producer_auth`, so that importing
        the package initializes the reader; and there MUST be no lazy path, no
        first-call initialization and no admission-time read.
        THIS IS A REQUIREMENT ON THE CHANGE THAT IMPLEMENTS PRODUCER AUTHENTICATION.
        It is not a description of the repository as it stands.
FROZEN: THE GUARANTEE THAT REQUIREMENT BUYS, STATED AS WHAT IT WILL BE ONCE THAT
        CHANGE LANDS — AND NOT BEFORE: a process able to call `admit()` or
        `admit_to_store()` will necessarily have initialized the reader, because the
        only route to either entry point runs through the package that imports it.
        The ordering guarantee is then STRUCTURAL rather than a sequence someone has
        to remember to observe, which is what makes "before admission is available"
        true by construction rather than by convention.
FROZEN: THE CURRENT STATUS, RECORDED BECAUSE THE CLAUSES ABOVE ARE REQUIREMENTS AND
        NOT FACTS. `plugins/evidence/producer_auth.py` DOES NOT EXIST;
        `plugins/evidence/__init__.py` DOES NOT IMPORT IT; and NO SUCH ORDERING EXISTS
        AT RUNTIME TODAY. Amendment 6 SPECIFIES this ordering and does not establish
        that the import edge, the initialization or the guarantee is present. NOTHING
        IN THIS SECTION MAY BE READ AS A CLAIM ABOUT THE REPOSITORY AS IT STANDS, and
        §7.3.11 MUST NOT BE CITED for the proposition that the reader is initialized
        before admission is available — that proposition is an obligation on code
        that has not been written.
        THE DISTINCTION IS THE ONE THIS CONTRACT DRAWS EVERYWHERE ELSE: §7.3.7 states
        its acceptance tests as obligations and records that none has been run, and
        §34.3 records that the mechanism is DEFINED AND NOT BUILT. A CONTRACT CAN
        REQUIRE A PROPERTY, AND REQUIRING IT IS NOT HAVING IT.
FROZEN: THIS CREATES NO CALLER AND NO ENTRY POINT, AND AUTHORIZES NOTHING. The import
        edge is WITHIN the Evidence package, between a module and the package that
        owns it. No production component outside the package gains a path to
        admission, no composition module gains one, and AI-15 §17.2b's prohibition on
        a production call site is untouched. Stating an obligation on the implementing
        change grants no permission to create a production writer, a caller, or an
        authorization of any kind.
FROZEN: THE RULE DISTINGUISHES CONFIGURATION SUPPLIED WHEN A PROCESS STARTS FROM A
        VARIABLE READ AFTER ARBITRARY APPLICATION CODE HAS RUN, and it is the FIRST
        of those the contract relies on. The intended flow, once the requirement above
        is implemented, is that a deployment supplies the variable to the process
        before it starts and the process then imports the package and captures what it
        was given. WHAT BINDS IN THE MEANTIME IS THE RULE, NOT THE FLOW: NO REPOSITORY
        CODE MAY WRITE THE VARIABLE AND NO PATH MAY RE-READ IT, so that the captured
        value is the value the launcher supplied. That is an obligation §31.3 obliges
        Layer 0 to enforce on the implementing change; it is not a description of what
        the repository does today, which is nothing.
FROZEN: WHAT THAT GUARANTEE DOES NOT COVER, RECORDED RATHER THAN LEFT TO BE ASSUMED.
        Code OUTSIDE this repository — a third-party library imported before the
        Evidence package — could write the process environment before the reader
        initializes, and no static rule over this repository can see it. This is a
        RESIDUAL RISK of the same kind §7.3.9 records for process control and key
        custody: an in-process library cannot defend its own address space or the
        environment it was started in. THE TRUST BOUNDARY IS THE PROCESS ENVIRONMENT
        AS THE LAUNCHER SET IT, and this section does not claim to survive an
        adversary who can rewrite it before startup completes.
FROZEN: WHAT IS CLAIMED, AND IT IS NARROWER AND CHECKABLE — AND IT IS CLAIMED OF THE
        IMPLEMENTATION, NOT OF THE TREE. No API PATH may let a caller choose the
        trust root (§7.3.2); no module in this repository may write the variable or
        reload the reader (§31.3); the read happens once and never repeats; and the
        ordering requirement above is what will make "before admission is available"
        true by construction rather than by convention. EACH OF THOSE IS A RULE THIS
        CONTRACT IMPOSES AND A PROPERTY §31.3 OBLIGES LAYER 0 TO CHECK — none is a
        claim that the code exists. UNTIL THE IMPLEMENTING CHANGE LANDS, THE HONEST
        STATEMENT IS THE ONE §35.3 ALREADY CARRIES: AI-05 has no producer
        authentication at all, and §30 step 7b is performed by nothing.
FROZEN: THE IMMUTABILITY THIS SECTION REQUIRES OF THE CAPTURED STATE IS A RULE ON
        REPOSITORY CODE AND NOT A CLAIM OF TAMPER-PROOFNESS. The state is required to
        be held privately, never returned as a whole, never handed out as a mutable
        structure, free of any public initializer, reset or setter, and not rebound by
        any code in this repository — and §31.3 obliges Layer 0 to check exactly those
        SOURCE-TREE rules. NONE OF THAT IS A RUNTIME SANDBOX. Code able to execute
        inside the same process — arbitrary reflection, monkeypatching, a debugger, a
        hook from a library that came from outside this repository, or hostile code
        with equivalent privileges — can reach in-memory state that no source-tree
        rule protects, which §7.3.9 already records as PROCESS CONTROL and which this
        section does not contradict. WHAT IS CLAIMED IS NARROWER AND IS THE CLAIM THAT
        MATTERS HERE: REPOSITORY CODE DOES NOT DO IT, AND THE REPOSITORY WILL NOT
        MERGE CODE THAT DOES. §31.3 states the qualification in full, and the two
        clauses are one rule.
FROZEN: A DEPLOYMENT OBLIGATION IS STATED SO THE ORDERING IS ACTIONABLE, AND IT IS
        NOT A NEW COMPOSITION ENTRY POINT. The process MUST import the Evidence
        package as part of its own startup, before it begins application work. A
        deployment that deferred that import until it first needed admission would
        still be reading the SAME value — because nothing in this repository writes
        the variable — but it would have widened the residual window above, and it
        would be relying on that fact rather than on the structure. The obligation is
        recorded; it is not enforced by a caller this document invents.
```

```text
AN IMMUTABLE AUTHORITATIVE SNAPSHOT IS NOT A LAST-KNOWN-GOOD FALLBACK

FROZEN: THE TWO ARE OPPOSITES, AND THE DIFFERENCE IS THE WHOLE REASON THIS SECTION
        STATES A LIFECYCLE RATHER THAN A PROHIBITION.

            the snapshot        captured ONCE, at initialization, and authoritative
                                for the process lifetime. If it is INVALID it STAYS
                                INVALID and the deployment authenticates NOTHING. It
                                is what the process HAS, not what it would PREFER.

            last-known-good     FORBIDDEN. It would mean: the configuration is
              fallback          invalid now, so keep using the last one that
                                validated. The process would then verify against a
                                trust root the deployment has WITHDRAWN — and an
                                operator who revoked a token by removing its entry
                                would find the revocation had not taken effect, which
                                is precisely the state §7.3.9 exists to describe
                                truthfully.

FROZEN: A ONCE-ONLY CAPTURE MAKES THAT FALLBACK UNREACHABLE RATHER THAN MERELY
        FORBIDDEN. Under a PER-ATTEMPT read there IS a second read, and a second read
        is what a fallback falls back FROM: attempt 1 reads a valid mapping and caches
        it, attempt 2 reads an invalid one, and a reader that keeps serving the cached
        mapping has performed a last-known-good fallback without anyone having asked
        it to. An earlier revision of this section required "one snapshot per
        admission attempt". THAT IS WITHDRAWN AND REPLACED: it bounded each attempt
        but left the SEQUENCE of attempts unconstrained, and the sequence is where the
        fallback lives. THERE IS NO SECOND READ HERE, so there is nothing for such a
        fallback to reach. The prohibition is kept because it names the defect; the
        lifecycle is what makes the defect unrepresentable.
FROZEN: THE WITHDRAWN FORM WAS NOT WRONG ABOUT ISOLATION, AND WHAT IT CORRECTLY
        REQUIRED IS KEPT. One verification still decides key selection, the group rule
        and the enforced policy against ONE value, and no read occurs between
        selecting a key and applying the collision rule. The process-lifetime rule
        subsumes that: a value that never changes cannot change mid-verification.
```

```text
TWO SERIALIZATIONS THAT MUST NOT BE CONFUSED, AND A THIRD THAT IS NEITHER

FROZEN: THE CONFIGURATION'S JSON PARSING IS NOT AI-05-CJ-1 AND MUST NEVER BE USED AS
        IT. §7.3.6 fixes the signed input's canonicalization and states that it
        governs the SIGNED INPUT and nothing else. This section's JSON rules govern
        the CONFIGURATION DOCUMENT and nothing else. THEY ARE DIFFERENT FUNCTIONS
        OVER DIFFERENT VALUES FOR DIFFERENT PURPOSES, AND NEITHER MAY BE SUBSTITUTED
        FOR THE OTHER.
FROZEN: THE CONFIGURATION VALUE IS NEVER PART OF A SIGNED INPUT. `signed_input` is
        built from the SUBMITTED EVIDENCE MAPPING (§7.3.4). The trust configuration
        is not a field of any record, is not covered by any signature, and is not
        stored (§7.3.3). It is therefore not a value the signed-input profile has any
        opinion about.
FROZEN: WHAT FOLLOWS, AND IT IS THE FAILURE THIS CLAUSE EXISTS TO PREVENT. The
        configuration's tolerance MUST NOT LEAK INTO THE SIGNED-INPUT PATH. JSON
        permits insignificant whitespace and any member order; AI-05-CJ-1 does not
        permit whitespace inside the canonical text and fixes key order by UTF-16
        code unit. A serializer that produced the configuration's member order, or a
        pretty-printed variant of it, would produce bytes that are not the canonical
        serialization of the mapping — and a proof over those bytes is a proof over
        something the contract does not define. THE SIGNED INPUT IS PRODUCED BY THE
        AI-05-CJ-1 SERIALIZER AND BY NOTHING ELSE, INCLUDING AND ESPECIALLY NOT BY
        WHATEVER ROUTINE PARSED THE CONFIGURATION.
FROZEN: THE EXISTING DIGEST PATH IS A THIRD THING AND IS ALSO UNCHANGED. §15.2's
        digest input and the stored form continue to use what they used before
        (§7.3.6). Three serializations, three purposes, no unification.
```

```text
TRUST DOMAIN INDEPENDENCE

FROZEN: THIS CONFIGURATION AND AI-13'S APPROVAL TRUST ANCHOR ARE DIFFERENT TRUST
        DOMAINS WITH DIFFERENT SOURCES. §7.3.10 already records that AI-13's
        designated approval ingress, its anchor and its Ed25519 verification site are
        NOT repurposed, NOT read and NOT widened by §7.3. This section adds the
        converse obligation: the reader MUST NOT read AI-13's anchor variable,
        MUST NOT accept an AI-13 approval as a producer proof, and MUST NOT treat a
        producer proof as an approval. Producer authenticity and human approval are
        different questions answered by different keys, and a submission that
        satisfied one has established nothing about the other.
FROZEN: AN AUTHENTICATED PRODUCER CLAIM IS NOT AN APPROVAL, NOT A PERMISSION, NOT A
        CAPABILITY AND NOT A GUARD RESULT (§7.3.8). The configuration being valid,
        readable and internally consistent grants nothing to anyone.
```

#### 7.3.12 A forwarder and the producer proof — FROZEN (Amendment 8)

§7.3.10 records that "the composition is NOT a party to this mechanism. It does not
read the designated producer mapping, does not mint, hold or verify a proof". That
sentence was written for the mechanism's **trust** side — who may decide what is
trusted — and it does not answer the **transport** question a forwarding caller
raises. §7.2 permits a submitter that is not the producer (Reading A), so a
component that submits a record it did not author must present the proof the
authoring component minted; and the word "hold" could be read to forbid exactly
that. This section answers the transport question. It changes **no** clause of
§7.3.1–§7.3.11.

```text
THE QUESTION, AND WHY IT IS NOT ACADEMIC. §7.2 fixes that a submitter MAY differ from
the producer. AI-15 §7.3 selects T2 as the only topology consistent with the frozen
contracts, and under T2 a caller submits a record the OWNING phase authored. The
submission must carry the owning phase's proof (§7.3.3), so SOMEONE other than the
producer carries proof material to an admission entry point. WHETHER THAT IS
PERMITTED AT ALL is the question this section answers, and §7.3.10's word "hold" was
not written to answer it.
```

```text
FROZEN: A FORWARDER MAY TRANSPORT A PRODUCER PROOF AS OPAQUE MATERIAL. A caller that
        is not the producer MAY present the producing component's proof to `admit()`
        or `admit_to_store()`, and MAY carry it between the point it received it and
        the entry point, WITHOUT reading, parsing, validating or interpreting it.
        "OPAQUE" IS THE WHOLE OF THE PERMISSION: the forwarder handles bytes it did
        not produce, cannot verify on its own and could not have minted.

FROZEN: "HOLD" IN §7.3.10 MEANS CUSTODY FOR DECIDING WHAT IS TRUSTED, AND TRANSPORT
        IS NOT THAT. §7.3.10's clause refuses a component that holds, reads or
        decides the TRUST ROOT — the mapping, the key selection, the verdict. A
        forwarder does none of those: it does not read the designated mapping, it
        does not select a key, and it does not verify. The proof it carries is
        verified BY THE MECHANISM, against a mapping the forwarder never sees, using
        a key it never learns. §7.3.10 IS NOT WEAKENED BY THIS SECTION: every
        prohibition in it stands unchanged, and this section grants no permission to
        read, decide or verify anything.

FROZEN: A FORWARDER MUST NOT GENERATE A PROOF. Minting one requires the producer's
        private signing key, and §7.3.11 puts PUBLIC key material — and only public
        key material — in this deployment's configuration: the deployment holds
        verification keys and cannot mint the proofs it checks. A forwarder able to
        generate a proof for a token would be able to speak for that token, which is
        the forgery §9.2 names.

FROZEN: A FORWARDER MUST NOT REPLACE A PROOF. Substituting another proof — for the
        same token or for a different one — is refused BY THE MECHANISM rather than
        by policy: the carried bytes must equal the verifier's reconstruction of THIS
        submitted mapping (§7.3.5 V5), and the key is selected BY THE TOKEN THE
        RECORD DECLARES (§7.3.5 V3), so a proof minted for another record or another
        producer does not verify.

FROZEN: A FORWARDER MUST NOT MUTATE A PROOF. The envelope is carried byte for byte
        (§7.3.3): decoding is strict AND canonical, so a re-encoded, re-ordered,
        padded or trimmed value is REFUSED as malformed rather than accepted as an
        alias of a valid one.

FROZEN: A FORWARDER MUST NOT CLAIM OWNERSHIP OF THE CLAIM, AND MUST NOT CLAIM TO HAVE
        AUTHENTICATED IT. Transport confers nothing. It does not make the forwarder
        the producer, it does not move `provenance.producer`, `provenance.producer_type`,
        `provenance.actor` or the payload (§7.2), and it does not make the forwarder a
        party to the trust decision. §7.3.1's limit applies to whatever a reader
        concludes: a KEY HOLDER signed the claim, and that does not establish which
        code ran, nor that the claim is true, nor who submitted it.
```

```text
FROZEN: EVERY FAILURE TO PRESERVE IS A REFUSAL, AND THAT IS WHY THE PERMISSION IS
        SAFE. A forwarder that drops the proof produces AUTHENTICATION_PROOF_MISSING;
        one that alters it produces AUTHENTICATION_PROOF_MALFORMED,
        AUTHENTICATION_SIGNATURE_INVALID or AUTHENTICATION_INPUT_MISMATCH; one that
        substitutes another producer's produces AUTHENTICATION_SIGNATURE_INVALID.
        There is NO PATH on which a transport failure yields an ACCEPTED record
        (§7.3.8), so the permission this section grants cannot be converted into an
        acceptance by mishandling the material it covers.
FROZEN: TRANSPORT IS NOT A TRUST RELATIONSHIP AND GRANTS NOTHING. A forwarder
        acquires no authority, permission, capability or Guard result by carrying a
        proof (§7.3.8, §23, §24), and no clause of this section may be read as making
        the forwarder a party to the mechanism.
FROZEN: THE SUBMITTING SIDE OF THIS INVARIANT IS STATED BY THE PHASE THAT OWNS THE
        CALLER, NOT HERE. What a forwarder MUST keep immutable across the boundary,
        and what its caller obligations are, are AI-15 §9.4 and §10.2. This section
        fixes what MAY cross the boundary and under what limits; those clauses fix
        what the crossing party MUST do.
```

#### 7.3.13 The exact approved call-site set — FROZEN (Amendment 9)

```text
WHAT THIS REPLACES. §7.3.7's obligation list carried "the absence of a production
non-test writer". That obligation was true of a repository with no writer, and it
was an obligation ON THE CHANGE THAT CONNECTS the edge — a change this contract
always contemplated (§7.3.12 anticipates a forwarder). It is REPLACED, NOT
DELETED: §34.2 forbids "a test deleted, weakened, or re-scoped to make a test
pass", and a connecting change that simply removed the obligation would be exactly
that.
```

```text
THE STANDARD — EXACT CALL-SITE AUTHORISATION.

  A production call site of `admit` or `admit_to_store` is AUTHORISED only when it
  is named INDIVIDUALLY in the approved set.

  AN APPROVAL OVER THE NUMBER OF CALLS A SCOPE MAKES IS A DIFFERENT AND WEAKER
  STANDARD, and MUST NOT be recorded, reported or relied on as exact call-site
  authorisation. The two are not interchangeable, and the difference is exactly the
  substitution case below.

  AN APPROVED ENTRY CARRIES ALL OF:

      path                repository-relative POSIX path
      scope               the FULLY QUALIFIED enclosing function, including class
                          scopes and nested functions; module level is recorded as
                          "<module>" rather than left empty
      entrypoint          the CANONICAL entry-point name the call resolves to —
                          "admit" or "admit_to_store" — never an alias and never a
                          local binding name
      callee              the ORIGINAL SOURCE FORM OF THE CALLEE EXPRESSION, with
                          location attributes excluded. THIS IS NOT `entrypoint`:
                          `admit`, `submit_alias` and `adm.admit` are three
                          different forms that may all resolve to `admit`, and
                          recording the canonical name alone would collapse them
                          into ONE identity
      ast_path            the child-field/index path from the module root to the
                          Call node (for example body[3].body[1].value)
      fingerprint         a canonical digest over the call's ARGUMENTS AND CONTROL
                          CONTEXT: the argument and keyword NAMES in source order,
                          and the chain of enclosing statement kinds. THE CALLEE IS
                          NOT NORMALISED INTO IT — it is carried as `callee`
                          instead, because the two answer different questions.
                          LINENO AND COL_OFFSET ARE EXCLUDED.
      control_context     the enclosing statement kinds, where they are needed to
                          distinguish two otherwise identical calls in one scope
      proof_kwarg         the call passes `producer_proof` EXPLICITLY as a keyword
                          argument. A `**mapping` expansion does NOT satisfy this
                          and MUST FAIL — the argument is then not verifiable from
                          the source.

  THE IDENTITY IS THEREFORE STRICT ABOUT THE CALLEE. Two calls at the SAME scope,
  the SAME `ast_path` and with the SAME arguments, reaching the SAME canonical
  entry point and differing ONLY in how the callee is SPELLED, are TWO DIFFERENT
  call sites. An approval of one is NOT an approval of the other: when the callee's
  syntax form changes, the old approval MUST NOT match, and the new form MUST be
  approved again. `entrypoint` is kept as a SEPARATE field because it answers the
  different question of which entry point the call reaches, and it is what makes an
  alias recognisable at all.
```

```text
THE ASSERTION IS SET EQUALITY OVER IDENTITIES, NOT COUNT EQUALITY.
Mapping equality in both directions: OBSERVED == APPROVED.
EQUALITY OF AN EXPECTED COUNT IS NOT EVIDENCE THAT INDIVIDUAL CALL SITES WERE
APPROVED, and MUST NOT be presented as such.

WHAT IT DETECTS
    an added call, a removed call, a mis-pathed call, an unapproved call
                                            -> a key on one side only        -> FAIL
    a second call in a scope where one was approved
                                            -> a second identity             -> FAIL
    DELETE ONE CALL AND ADD ANOTHER IN THE SAME SCOPE, COUNT UNCHANGED
                                            -> a different `ast_path` and/or
                                               `fingerprint`                 -> FAIL
```

```text
BASELINE AND CANDIDATE ARE TWO DIFFERENT CHECKS AGAINST TWO DIFFERENT TREES.

    BASELINE    on `origin/main` before the connecting change: the approved set is
                EMPTY and the observed set is EMPTY. This is the replaced
                obligation's assertion, unchanged.
    CANDIDATE   on the tree that creates the call site: the observed set EQUALS the
                approved set that change declares.

NO SINGLE TREE IS REQUIRED TO SATISFY BOTH. A candidate check with an EMPTY
approved set asserts "no production call site", which is the baseline assertion —
so one implementation serves both, provided the approved set is EMPTY on the
baseline and non-empty only in the change that creates the call site.

THE BASELINE HALF IS A ONE-TIME GATE ON THE CONNECTING CHANGE, AND IT MUST BE RUN
AS ITS OWN STEP. The connecting change records, in its own report:

    the ACTUAL base SHA it was built on — the `origin/main` commit, not a branch
      name and not a remembered value
    the production call-site set observed ON THAT COMMIT, which MUST BE EMPTY
    the ACTUAL head SHA of the candidate tree
    the production call-site set observed on the CANDIDATE, compared against the
      approved set the change declares

A REPORT THAT SHOWS ONE TREE HAS NOT SHOWN TWO. Running the candidate check on a
tree whose approved set happens to be empty verifies the CANDIDATE, not the
baseline, and MUST NOT be described as having verified both.

THIS GATE DOES NOT BECOME A PERMANENT EMPTINESS REQUIREMENT. It is a one-time
condition on the change that first creates a call site, not a rule that every later
CI run must find the approved set empty — which would forbid the very connection
the obligation exists to permit. How it is implemented is the change's business: a
separate step, a one-shot job, or a recorded manual run are all acceptable, and
none of them changes the number any historical run recorded.
```

```text
THE SCANNER BOUNDARY.

  SUPPORTED — the call resolves to a canonical entry point:
      a direct call, a fully qualified call, a parent-package hop, and a LOCAL OR
      IMPORT ALIAS including an ANNOTATED binding.
      A resolved alias is counted under its CANONICAL entry-point name, NEVER under
      the local binding name.

  NOT SUPPORTED, AND NOT SILENTLY IGNORED:
      reflective acquisition         getattr(module, "admit")(...), __import__(...),
                                     importlib.import_module(...)
      partial application/wrapping   functools.partial(...), or a decorator that
                                     returns an entry point
      dispatch through a container   a list, mapping or registry lookup, then a call
      a parameter-rooted attribute chain, or any name assembled at run time

  AN UNSUPPORTED ACQUISITION IS CARRIED FORWARD ONTO THE NAME IT BINDS, AND THE
  LATER CALL IS THE FINDING. Checking only the IMMEDIATELY-INVOKED shape is NOT
  sufficient, and an implementation that stops there does not satisfy this clause.
  Each of the following obtains a callable by an unsupported form and then calls it
  through an ordinary-looking name; EVERY ONE of them MUST be reported:

      writer = getattr(evidence, "admit")      then  writer(record, ...)
      writer = partial(admit, record, ...)     then  writer()
      mod    = importlib.import_module(...)    then  mod.admit(record, ...)
      writer = REGISTRY["admit"]               then  writer(record, ...)

  A LOCAL NAME BOUND TO MORE THAN ONE ENTRY POINT IS UNRESOLVED, NOT A CHOICE. If
  one scope binds a name to both `admit` and `admit_to_store`, which one it denotes
  cannot be determined, and the call MUST be reported rather than resolved to
  either. Guessing would record an approval against a call site nobody identified.

  FAIL-CLOSED. A production form the scanner cannot RELIABLY resolve to a canonical
  entry point MUST NOT be treated as "no call site". It MUST be reported as
  UNRESOLVED, and MUST drive the check to FAIL or to a declared BLOCKED state.
  An implementation whose output is identical whether such a form is present or
  absent does not satisfy this clause.
  "THE SCANNER DOES NOT SEE IT" AND "IT CANNOT WRITE" ARE DIFFERENT STATEMENTS, and
  only the second would justify silence.

  A MODULE THE SCAN CANNOT READ OR PARSE HAS UNKNOWN CALL SITES, AND UNKNOWN IS NOT
  NONE. Every such file MUST be reported as a SCAN FAILURE — path and reason — and
  MUST drive the check to FAIL. An implementation that skips it and reports the
  call sites it happened to see does not satisfy this clause, because the result
  would be clean for a tree that was never fully read.

  NO COMPLETENESS CLAIM. Static scanning cannot prove the absence of arbitrary
  Python dynamic behaviour: `eval`, `exec`, dynamically constructed modules and
  code generated at run time are OUTSIDE what it can establish. This clause makes
  no claim of exhaustive coverage, and none may be made on its behalf.

  THE BLIND-SPOT LIST IS TRANSPARENCY, NOT ACCEPTANCE. The check carries a
  documented list of the forms it does not resolve, so a reader can see where its
  authority stops. NEITHER THE LIST'S EXISTENCE NOR ITS BEING NON-EMPTY IS AN
  ACCEPTANCE CRITERION, and neither may be cited as evidence that unresolvable
  forms are safe.

  THE POSITIVE CONTROL STAYS. A check that cannot find a call site proves nothing
  about there being none, so the control that plants one and requires it to be
  found is part of this obligation and MUST remain.
```

```text
THE FAILURE-INDEPENDENCE REQUIREMENT. EACH acceptance condition this section adds
        MUST BE ABLE TO FAIL ON ITS OWN. A check whose output cannot distinguish
        WHICH condition broke is one condition with several names, and does not
        satisfy this section.
FROZEN: §7.3.7's obligation list, as amended, is the list this section defines.
        Nothing here authorises a production caller, a connecting change or a
        CONNECTED classification: §7.3.12 states what may cross the boundary, and
        the calling phase's own contract states what its caller MUST do.
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
producer claim not            REJECTED      §30 step 7b, §7.3. One of SIX reason
  authenticated                             codes: AUTHENTICATION_PROOF_MISSING,
                                            AUTHENTICATION_PROOF_MALFORMED,
                                            AUTHENTICATION_KEY_UNAVAILABLE,
                                            AUTHENTICATION_SIGNATURE_INVALID,
                                            AUTHENTICATION_INPUT_MISMATCH,
                                            AUTHENTICATION_INPUT_UNSERIALIZABLE.
                                            No outcome member is added (§22.1), and
                                            an authentication failure is never a
                                            Guard DENY (§7.3.8). Where step 7's
                                            published rule ALSO fails, STEP 7's
                                            reason is the one reported
producer token not            REJECTED      §30 step 7b, §7.3.5 V2. Reported with an
  readable                                  EXISTING shape reason —
                                            RECORD_MALFORMED,
                                            MISSING_REQUIRED_FIELD or
                                            FIELD_CLASS_VIOLATION — and NOT with an
                                            authentication code. No key lookup and
                                            no cryptography occur
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
 7b. producer      the producer claim is AUTHENTICATED against the deployment's
     authentication designated producer trust mapping (§7.3, Amendment 5)
                   -> WHICH MAPPING THAT IS, WHERE IT COMES FROM AND WHICH MODULE
                      HOLDS IT are §7.3.11's. ONE environment variable
                      (WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG), parsed as one
                      strict JSON object, read ONCE during the initialization of
                      plugins/evidence/producer_auth.py and by nothing else. THIS STEP
                      DOES NOT READ IT: it consults the process-lifetime state that
                      initialization produced, which no later change to the variable
                      replaces and no restart-free path reloads.
                      A missing, malformed, incomplete or invalid configuration — or
                      a mapping the reader refuses under §7.3.2's group rule — leaves
                      that state INVALID, and is REJECTED with
                      AUTHENTICATION_KEY_UNAVAILABLE, which is §7.3.5 V3's existing
                      code and not a seventh one
                   -> RUNS AFTER STEP 7, AND BEFORE CONSTRUCTION. Construction is
                      steps 1-4, 4b, 6, 8-11 AND 13 — and NOT step 12, which is
                      computed later, in `assign_digests`. §30's numbers IDENTIFY
                      steps; they are not an execution order, and step 13 runs
                      before step 12. STEP 6 IS PART OF CONSTRUCTION and has NOT
                      run when this step executes (§7.3.7's stage table)
                   -> step 7 runs first because R2 forbids hashing a value that
                      was not admitted, and construction derives
                      ContextRef.value_digest from the supplied value. This step
                      runs next because no typed record, and therefore no Evidence
                      digest, may be derived from a claim that is not authenticated
                   -> REJECTED when the mapping is absent, when it holds no key for
                      the claimed token, when the proof envelope is malformed, when
                      the signature does not verify under that key, when the signed
                      input is not the canonical serialization of this mapping, or
                      when this mapping HAS no canonical serialization under
                      §7.3.6. SIX reason codes; §7.3.8
                   -> REJECTED with an EXISTING shape reason when the claimed
                      producer token cannot be read at all: no key lookup and no
                      cryptography proceed without one (§7.3.5 V2)
                   -> NOT an Evidence digest. Signature verification is not a
                      digest computation under §14.6 and produces no Evidence
                      field; §7.3.7 separates the three operations that ordinary
                      speech calls "hashing"
                   -> a submission with NO proof is REJECTED exactly as one with a
                      bad proof is. There is no unauthenticated admission path
                   -> where step 7's rule ALSO fails, STEP 7's reason is the one
                      reported, by the same precedence the step-7 note above
                      already records for a shape-vs-rule collision
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
producer claim not             REJECTED   step 7b. Absent proof, absent mapping,
  authenticated                             absent key for the claimed token, a
                                            malformed envelope, a signature that
                                            does not verify, a signed input that
                                            is not this mapping, or a mapping with
                                            no canonical serialization at all.
                                            SIX named reason codes (§7.3.8). A
                                            shared signing key across tokens is
                                            NON-COMPLIANT and cannot authenticate
                                            (§7.3.2)
producer token not             REJECTED   step 7b, §7.3.5 V2. An existing shape
  readable                                  reason — RECORD_MALFORMED,
                                            MISSING_REQUIRED_FIELD or
                                            FIELD_CLASS_VIOLATION — never an
                                            authentication code
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

### 31.3 The producer-authentication rows, and where they live (Amendment 6)

```text
FROZEN. AI-05 adds no layer 4 (§31). Every row below runs in LAYER 1 with the rest
of `tests/evidence/`, in the same offline gate, under the same "no credential, no
network" condition.

WHAT WAS AMBIGUOUS, AND IS NOT ANY MORE. Amendment 5 created §7.3.7's acceptance
obligation — twenty-two named cases plus the key-material rule — and did NOT give
them T-numbers in §31, while §31 declares itself "the test matrix" and FROZEN. A
reader could therefore conclude that §7.3.7's list sits outside the matrix, that it
is advisory, or that §31's row count is the whole of the obligation. None of those
is correct.

FROZEN: §7.3.7's ACCEPTANCE OBLIGATION IS PART OF THIS MATRIX, INCORPORATED BY
        REFERENCE. Its cases are rows of §31 in every sense that matters — same
        layer, same force, same "MUST exist before the standard may be reported as
        holding" — and a suite that omits one of them is as incomplete as a suite
        that omits T13.
FROZEN: §31's T-NUMBERING IS NOT EXTENDED BY THIS AMENDMENT. §7.3.7's cases keep
        the identifiers §7.3.7 gives them, for the same reason §7.3.6's vectors are
        referenced rather than copied: a second copy of a normative list is a second
        list that can drift, and the one in §7.3.7 sits beside the clauses it tests.
        A later amendment that wishes to number them may; until one does, §7.3.7's
        text governs and its identifiers are the ones to cite.
FROZEN: NOTHING IN §31 IS REMOVED, MERGED, RENUMBERED OR WEAKENED. T1-T35, T42-T57,
        T54 and T55 keep their rows and their meanings, and no existing row is
        re-scoped to carry an authentication assertion.
FROZEN: T35 APPLIES TO THE NEW MODULE UNCHANGED. `plugins/evidence/producer_auth.py`
        is parsed by §31's architecture-boundary row like every other module in the
        package: no network client, no `subprocess`, no `eval`/`exec`/`compile`, no
        `routing`/`tools` import, no secret logging. A cryptographic verifier that
        reached a transport, spawned a process or evaluated a string would be a
        different component wearing this one's name.
```

```text
FROZEN: LAYER 0 GAINS ONE NARROWLY SCOPED EXCEPTION, AND IT IS THE ONLY ONE.

    module            plugins/evidence/producer_auth.py — and no other module
    what it may       `os` and `json`, for the configuration and for nothing else
      import
    what it may NOT   read a file, call `open()`, walk a path, import `io`,
                      `pathlib`, `shutil`, `tempfile` or any other filesystem root,
                      or reach any configuration source other than the one variable
                      §7.3.11 names
    everything else   UNCHANGED. `store.py` remains the only module that touches a
                      filesystem, and every other restriction on `plugins/evidence`
                      stands exactly as it stood.

FROZEN: THE EXCEPTION IS TWO IMPORTS IN ONE NAMED MODULE, AND IT IS NOT A RELAXATION.
        Widening `EVIDENCE_IO_MODULES` to the package, permitting `os` in a second
        module, permitting `open()` outside `store.py`, or permitting a second
        configuration source would each break the property the exception exists to
        preserve: that exactly one module reads the trust root, and that the rest of
        the package stays pure.
FROZEN: LAYER 0 MUST ALSO ENFORCE, FOR THIS MODULE, THE FOUR RULES §7.3.2 AND
        §7.3.11 STATE IN PROSE — and stating them is not enforcing them:
            ONE READER   the designated environment variable is read in
                         `producer_auth.py` and in no other module. A second read is
                         a second place the deployment's trust root is decided,
                         whether or not it calls the accessor.
            NO MUTATION  the variable is a DEPLOYMENT INPUT and not a control
                         surface. No module writes the RUNNING process's
                         environment — no `os.environ[...] = ...`, no
                         `os.environ.setdefault`, `.pop`, `.update` or `.clear`, no
                         `os.putenv` or `os.unsetenv`, and no helper that performs
                         any of them. A value repository code can rewrite in place is
                         not a deployment fact.
                         The reader module is likewise not RELOADED to re-trigger its
                         initialization: an `importlib.reload` of it, or any other
                         route by which its module-level read runs a second time, is a
                         second read and is refused as one.
            IMMUTABLE    the captured state is not a mutable object this repository's
              STATE      code may alter. The mapping and the policy are held
                         privately, are never returned as a whole by any public
                         function, and are never handed to another module as a
                         structure it could mutate. The reader answers a PER-TOKEN
                         question — which key applies to THIS claimed token — and
                         exposes neither the mapping, the policy table nor the parsed
                         document. The state is not rebindable BY REPOSITORY CODE: no
                         assignment to, `setattr` on, or monkeypatch of it appears
                         anywhere in this repository, and there is no public
                         initializer, no reset, no setter and no "load for tests"
                         entry point.
            NO CALLER-SELECTED TRUST ROOT   no public function accepts a public key,
                         a mapping, an anchor, a verifier, a configuration object or
                         a configuration path as a parameter.
        READ AND WRITE ARE DIFFERENT FAILURES AND BOTH ARE CHECKED. A second READER
        decides a second trust root; a WRITER changes the one there is; a REPLACER
        changes what the reader holds. A deployment configuration that repository
        code can rewrite in place, or replace in memory, is not a deployment fact at
        all, and §7.3.11's process-lifetime rule would be unenforceable no matter how
        carefully the read was written.
        AI-13 §13.3 carries the first and the no-caller-selected-trust-root rules for
        its own domain, and its Layer 0 check enforces both. This amendment places the
        same obligation on the AI-05 boundary and adds the second and third, which
        AI-13's single-anchor model did not need in the same form because an anchor
        that is never re-read is neither a mapping a fallback could be built from nor
        a structure a caller could reach into; §7.3.10 keeps the two domains apart
        while the enforcement shape is the same shape.
FROZEN: WHAT THESE RULES ARE, AND WHAT THEY ARE NOT. A TRUST-BOUNDARY QUALIFICATION,
        recorded so the four rules above are not read as more than they are — and
        recorded HERE, beside them, because a qualification kept somewhere else is one
        a reader meets too late.
            WHAT THEY ARE    a set of declared SOURCE-TREE rules, enforced over the
                             files this repository contains. They establish that no
                             code IN THIS REPOSITORY reads the variable in a second
                             place, writes the running process's environment, hands
                             the mapping out, replaces the captured state, or accepts
                             a trust root as a parameter — and they DETECT those
                             patterns within their stated coverage.
            WHAT THEY ARE    a runtime sandbox, and NOT a proof of immunity. A static
              NOT            check reads SOURCE; it does not constrain what a process
                             does once it is running. Code with the ability to
                             execute inside the SAME Python process — through
                             arbitrary reflection, monkeypatching, a debugger, a hook
                             installed by a library that came from outside this
                             repository, or simply hostile code running with
                             equivalent privileges — can alter in-memory state that no
                             source-tree rule protects. §7.3.9 already records exactly
                             this as PROCESS CONTROL: "an adversary who controls this
                             process's address space can control the mapping and
                             defeat any in-process check. An in-process library cannot
                             defend its own address space, and this section does not
                             claim to survive such an adversary."
FROZEN: PYTHON MODULE STATE IS NOT INTRINSICALLY TAMPER-PROOF, AND NO CLAUSE HERE MAY
        CLAIM OTHERWISE. Attributes can be rebound, module globals can be reassigned,
        and an actor inside the process can reach past any arrangement of them.
        NOTHING IN THIS SECTION CLAIMS THAT PYTHON PREVENTS THAT, and the IMMUTABLE
        STATE rule above MUST NOT be read as such a claim: it is a rule about what
        REPOSITORY CODE MAY DO, not a property of the language. What the four rules
        establish is narrower and checkable — REPOSITORY CODE DOES NOT DO IT, AND THE
        REPOSITORY WILL NOT MERGE CODE THAT DOES.
FROZEN: THIS QUALIFICATION IS NOT PERMISSION, AND IT RELAXES NOTHING. It bounds WHAT
        STATIC ENFORCEMENT CAN DELIVER; it does not narrow a single requirement above.
        For normal repository code the requirements are ABSOLUTE: a module that writes
        the variable, replaces the captured state, hands out the mapping or accepts a
        caller-selected trust root is a FINDING and MUST NOT be merged. NO READER MAY
        CITE THIS CLAUSE to argue that such code is tolerable because an adversary
        with in-process execution could do worse — THE DEFECT AND THE LIMIT ARE
        DIFFERENT THINGS, AND THE LIMIT DOES NOT EXCUSE THE DEFECT.
FROZEN: THE NO-MUTATION RULE IS SHAPE-BASED, AND IT HAS TO BE. A name-based ban —
        "the variable's name appearing outside the reader is itself the finding" —
        would forbid the very mechanism §7.3.7's cases require, because A CHILD
        PROCESS CANNOT BE GIVEN A CONFIGURATION WITHOUT THE LAUNCHER NAMING THE
        VARIABLE. What is forbidden is WRITING THE RUNNING PROCESS'S ENVIRONMENT.
        What is permitted is HANDING A VALUE TO A PROCESS THAT HAS NOT STARTED. The
        static rule distinguishes them by the SHAPE of the use, not by the presence
        of the name, and this section states both shapes so the rule has something
        exact to check.
FROZEN: ONE TEST-HARNESS MODULE MAY NAME THE VARIABLE, AND ONLY IN THAT SHAPE.

    tests/evidence/trust_harness.py

        It is the ONLY module outside the reader in which the designated variable's
        name may appear. WITHIN it, the name may appear ONLY as a key in the
        environment mapping handed to a child-process launch — never as an
        assignment to the running process's environment, never in `os.putenv`, and
        never anywhere else in the repository.
        It supplies that environment to a SEPARATE process, which imports the real
        `plugins/evidence/producer_auth.py` and exercises the ORDINARY admission and
        verification path. It MUST NOT mutate the running test process's active
        environment to simulate a reload, and it MUST NOT inject a mapping, a key, a
        verifier or a parsed state into the reader.
        This is ONE module, ONE shape and ONE variable. It is not an exception for
        tests in general, and it is not an exception for any production module: a
        second module naming the variable, or this module naming it in another shape,
        is the NO MUTATION finding.
FROZEN: WHY THIS IS PERMITTED BY THE EXISTING ARCHITECTURE, STATED SO IT IS NOT
        MISTAKEN FOR A NEW PERMISSION. It is not new, and it does not widen anything:
            a separate interpreter is ALREADY spawned from this suite —
              `tests/evidence/test_canonical.py:119-143`,
              `test_a_separate_interpreter_reaches_the_same_value`, runs
              `subprocess.run([sys.executable, "-c", program], ...)` as "the
              cross-process half of T7"
            no Layer 0 rule constrains `tests/` on this axis. The
              `subprocess` restrictions in `scripts/ci/layer0_policy.py` are scoped
              to `plugins/evidence` (§31's five checks), to `routing/`, to
              `benchmarks/`, to `workflows/` and to `composition/`; `tests/` is
              reached only by `check_layer_markers`, which globs `test_*.py` — so a
              `trust_harness.py` support module is not a test module and needs no
              layer marker, exactly as `tests/integrations/support.py` does not
            the child's environment is supplied BEFORE the process starts, which is
              what a deployment does with the same variable; the harness adds no
              path a deployment lacks
        A SPAWN THAT FAILS ON THIS HOST IS A SKIP AND NOT A PASS. The existing
        cross-process test already records that a spawned process can fail on handle
        inheritance before any assertion runs, and reports it as a skip because that
        is a host limitation rather than a result. The producer cases inherit that
        treatment: an unrunnable child is NOT_RUN, never a passing authentication test.
FROZEN: A GREEN CI RUN IS NOT EVIDENCE THAT THE STANDARD HOLDS, AND MUST NOT BE
        REPORTED AS ANY. The suite exits 0 when its cases pass AND when a case was
        skipped, so the exit status cannot distinguish "every process-isolated case
        ran and asserted" from "the isolated cases could not execute here". A run in
        which any required process-isolated case was skipped demonstrates NOTHING
        about producer authentication, and CI SUCCESS ALONE MUST NOT BE USED TO CLAIM
        THAT AI-15 §15.2 STEP 0b IS SATISFIED OR THAT THE §7.3 STANDARD HAS BEEN
        SHOWN TO HOLD. Since §8.3 condition 11 is discharged by exactly those cases,
        a skipped case leaves condition 11 UNSATISFIED however green the run is.
        WHAT A REPORT MUST CARRY, WHEN THE TIME COMES: the number of process-isolated
        cases that RAN, not the number that passed or the run's status. A count of
        skips is a count of NOT_RUN, and NOT_RUN != PASS.
FROZEN: THE LAYER 0 RULE MUST CHECK THE SHAPE, NOT THE NAME. Two obligations, both
        static:
            the variable's name appears outside `plugins/evidence/producer_auth.py`
              ONLY in `tests/evidence/trust_harness.py`, and there only as a key in a
              child-process environment mapping
            no module anywhere assigns to, or otherwise writes, the RUNNING
              process's environment for that variable
        A rule that fired on the name alone would fail the harness; a rule that
        ignored the assignment would fail to catch a reload written as a `setenv`.
FROZEN: THIS AMENDMENT DOES NOT MAKE THAT LAYER 0 CHANGE. It is documentation, and
        `scripts/ci/layer0_policy.py` is NOT edited by it. §7.3.11's mechanism and
        the Layer 0 rules that enforce it are obligations on the change that
        IMPLEMENTS producer authentication, and until that change lands the
        implementation does not exist — so there is nothing for the widened rule to
        permit. UNTIL THEN THE EXISTING RULE STANDS AND WOULD REFUSE THE NEW MODULE,
        which is the correct and visible behaviour, not a defect to be worked around.
```

```text
HOW §7.3.7's CASES SUPPLY A CONFIGURATION WITHOUT A BYPASS

FROZEN: §7.3.7's KEY-MATERIAL RULE IS UNCHANGED AND IS NOT RELAXED BY §7.3.11's
        LIFECYCLE: tests MUST use a distinct keypair per producer token, MUST go
        through the real verification path, and MUST be supplied through the SAME
        designated configuration mechanism a deployment uses. A test-only bypass
        remains FORBIDDEN. What the lifecycle rule adds is WHEN that supply must
        happen, and it is not a new obligation so much as the same one applied
        honestly.

FROZEN: A CASE THAT NEEDS A PARTICULAR TRUST CONFIGURATION SUPPLIES IT TO A PROCESS
        THAT HAS NOT YET INITIALIZED THE READER, THROUGH THE LAUNCHER THIS SECTION
        NAMES. `tests/evidence/trust_harness.py` hands the variable to a child
        process's environment before that process starts; the child then imports the
        real reader and runs the ordinary admission and verification path.
        PROCESS-ISOLATED EXECUTION IS THEREFORE THE MECHANISM for every case whose
        expected result depends on the configuration — a valid mapping, a mapping the
        reader refuses, an unreadable value, an absent one, both collision policies,
        and each malformed shape §7.3.11 names. This is not a test-only path: it is
        EXACTLY what a deployment does, because a deployment also supplies the
        variable to a process that has not started yet. The test and the deployment
        use one mechanism; only the process boundary differs.
FROZEN: THE LAUNCHER EXCEPTION AND THE NO-MUTATION RULE ARE ONE RULE, READ TOGETHER.
        The rule above forbids WRITING THE RUNNING PROCESS'S ENVIRONMENT; this clause
        permits HANDING A VALUE TO A PROCESS THAT HAS NOT STARTED. Stated separately
        they would read as a prohibition and an exception to it; stated together they
        are one boundary, and neither is a weakening of the other. A reader who finds
        only one of them has found half a rule.

FROZEN: CHANGING THE VARIABLE AFTER INITIALIZATION IS NOT A SUPPORTED WAY TO RELOAD
        THE TRUST ROOT, AND IT MUST NOT BE USED AS ONE IN A TEST. Setting it
        mid-process changes nothing the reader will consult, so a case written that
        way asserts against a trust root the process never held: it would either fail,
        or pass for a reason unrelated to what it claims to prove. A test that mutates
        the variable and then observes an outcome has proven nothing about this
        contract, whichever way it came out.
FROZEN: THE AI-13 IN-TEST PATTERN DOES NOT CARRY OVER, AND THE DIFFERENCE IS THE
        LIFECYCLE AND NOT THE SUBJECT MATTER. AI-13's focused suite installs its
        anchor by setting an environment variable mid-test and then exercising the
        production path, because the anchor is read when the accessor is CALLED. The
        producer trust configuration is read when the reader module INITIALIZES, so
        the same shape would set a value nothing consults. §7.3.10 keeps the two trust
        domains apart regardless; this records that the two domains ALSO differ in
        when their deployment fact is captured, so a copy of the pattern is not merely
        forbidden by §7.3.10 — it would not work.

FROZEN: NO TEST MAY REACH PAST THE CONFIGURATION MECHANISM. A test MUST NOT inject a
        mapping, a key, an anchor, a verifier or a configuration object into the
        reader, MUST NOT call a private initializer with a value, and MUST NOT
        monkeypatch the reader's parsed state. Each of those is the "test-only bypass"
        §7.3.7 forbids, and the process boundary above is what makes them unnecessary
        rather than merely disallowed.
FROZEN: THE CASES THAT DO NOT DEPEND ON THE CONFIGURATION ARE UNAFFECTED. §7.3.5's
        precedence, §7.3.8's six codes, the envelope rules of V1, V2's unreadable
        token, the §30 step 7 tie-break and every reason-code assertion that turns on
        the SUBMISSION rather than on the deployment run in one process with one
        configuration, exactly as before. The lifecycle rule changes how many
        processes a suite needs, not what any case expects.

FROZEN: NO CASE NAMED IN §7.3.7 HAS BEEN RUN, AND NOTHING IN THIS SECTION IS EVIDENCE
        THAT ONE HAS. This block states how a later suite MUST supply configuration;
        it is an obligation on that suite and not a report about it.
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

#### Amendment 5 — producer authentication is defined (2026-10-10)

```text
IN FORCE — THE MERGE THIS ENTRY WAS WRITTEN FOR HAS HAPPENED.

    merged as   7017bf577f654cb6dea0e8d5e50a27f334117b73   (PR #83)
                a true two-parent merge of
                97e9e8cd37b328eff934ee4e311ca31c63ca6d6c  (main before)
                and
                737ce97caa447c835a628bbbd0b14b0d4a20888b  (the branch head)

    merged on   2026-10-11

    WHAT CHANGED       the STATUS of this amendment: authored -> IN FORCE. The
                       entry named its base main when it was written; it names its
                       merge here.
    WHAT DID NOT       any semantic text. §7.3, §30 step 7b and §22.2 are FROZEN
                       exactly as merged. No clause is reworded, added or removed
                       by this status record, and no clause of this contract is
                       edited by it. §34.1's list of amendment-requiring changes
                       is not engaged: this records an amendment's own merge, it
                       does not make a new one.
    WHAT IT DOES NOT   imply that the MECHANISM exists. §30 step 7b is still
      IMPLY            performed by nothing, and the RECORDED DIVERGENCE below
                       still stands. IN FORCE is a statement about the CONTRACT.
```

Found while answering the question AI-15 recorded as **AI15-OPEN-1**: how a producer
claim is ESTABLISHED, as against merely well-formed. §7.2 separated three checks and
recorded that AI-05 performed only the first; the second had no definition anywhere.
This amendment supplies one. It is authored on a docs-only branch based on main
`97e9e8cd37b328eff934ee4e311ca31c63ca6d6c`.

**Why this is an amendment rather than a clarification made in place.** §34.1's list
of changes requiring an amendment enumerates evidence kind, canonical collection,
digest input, workspace rule, secret boundary, authority relation, identity field and
admission outcome. This amendment changes **none** of them. §34's preamble is broader
than its list, though — a frozen contract "changes only through an explicit amendment
recorded in §34.3" — and this amendment adds a NEW STEP to §30 and a NEW CHECK to §7.
That is a change however it is described, so the instrument is an amendment, recorded
here. The fact that §30's step list and §7 are absent from §34.1's enumeration is
recorded rather than relied on, exactly as Amendment 4 recorded the same about §7.

```text
(a) NEW §7.3 defines the producer-authenticity standard: what makes a producer claim
    AUTHENTICATED, what the mechanism establishes, and — in the same place — what it
    does NOT establish. The standard is (a) a designated deployment mapping,
    (b) a key for the claimed token, (c) a proof, (d) a signature that verifies
    under THAT key over the DECODED carried message, and (e) exact byte equality
    between those decoded bytes and the COMPLETE verifier-reconstructed
    `signed_input(submitted mapping)` — the DOMAIN TAG, the SEPARATORS and the
    PROTOCOL VERSION included, and NOT the bare canonical serialization.

(b) §7.3.2 fixes the trust model: a DEPLOYMENT-LEVEL producer-token-to-public-key
    mapping, read from ONE place by ONE module, with no public AI-05 function
    accepting a caller-selected key, mapping, anchor or verifier. It establishes key
    material ONLY: §6.5 remains the sole recognition authority, and a key configured
    for an unregistered token is INERT.
    THE INERTNESS IS BY CONSTRUCTION, NOT BY ORDERING. §7.3.2 also records that
    AUTHENTICATION MAY RUN BEFORE THE §6.6 REGISTRY CHECK, because §7.3.7 puts step
    7b before construction and the registry and cross-field checks run INSIDE it: a
    submission naming an unregistered token can REACH and PASS authentication and is
    then REFUSED by §6.6. NO VALID SIGNATURE FOR AN UNREGISTERED TOKEN CAN RESULT IN
    ACCEPTANCE. The two checks answer different questions — did the key holder for
    the CLAIMED token sign this, versus does that token APPLY to this record's kind
    and family — and neither substitutes for the other. A registered token with no
    configured key is REJECTED at authentication; a configured key with no registered
    token is REJECTED at construction.
    AN EARLIER REVISION OF §7.3.2 SAID THE REGISTRY CHECK REFUSES SUCH A RECORD
    "before authentication is consulted". THAT IS WITHDRAWN: it described an
    execution order this contract does not have and contradicted §7.3.7 and §30
    step 7b. §7.3.2 records the withdrawal in place.

(c) §7.3.2 makes ONE KEY PER RECOGNIZED PRODUCER TOKEN mandatory — no recognized
    token may share its private signing key with another recognized token OR with an
    unregistered one — and records that a SHARED PRIVATE SIGNING KEY IS NON-COMPLIANT
    WHEN A RECOGNIZED TOKEN IS ONE OF THE SHARERS. Two UNREGISTERED tokens sharing a
    key are NOT that case: neither can produce an ACCEPTED record, because §6.6
    refuses both, so POLICY A permits that configuration AND ONLY IT. The earlier
    unqualified forms — "each producer token that can be authenticated MUST have its
    own private signing key" and "a shared private signing key across two or more
    producer tokens is NON-COMPLIANT" — ARE WITHDRAWN, because each forbade a
    configuration POLICY A permits and left the exception to be inferred.
    It then states the ENFORCEABLE HALF of the rule: NO RECOGNIZED PRODUCER TOKEN
    MAY SHARE ITS PUBLIC KEY WITH ANY OTHER TOKEN IN THE MAPPING, REGISTERED OR NOT.
    The contract
    never sees a private key, but it does see the public keys the mapping holds, and
    one public key under two tokens IS the shared-key defect in terms a reader can
    check. A mapping that violates THAT RULE FAILS CLOSED: the designated READER
    refuses it, the deployment therefore has NO usable mapping, and EVERY submission
    is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE. The reader MUST NOT return the
    valid subset, keep the first or last entry it saw, or warn and continue. The
    clausal subject matters: it is THE RECOGNIZED-TOKEN SHARING RULE that triggers
    this, NOT a duplicate public key as such, and NOT the unqualified word
    "injectivity" — a mapping whose only duplicate group is made up of unregistered
    tokens is COMPLIANT under POLICY A and MUST NOT be refused for it.
    THE RULE IS STATED OVER GROUPS, NOT OVER PAIRS OF RECOGNIZED TOKENS: a duplicate
    public-key group containing AT LEAST ONE RECOGNIZED TOKEN makes the WHOLE MAPPING
    non-compliant, however many unregistered tokens sit beside it. AN INJECTIVITY
    RULE OVER RECOGNIZED TOKENS ALONE WOULD BE WRONG, and closing that is what this
    item now does: if a registered R and an unregistered U share a key K, a holder
    of K's private key can sign a claim naming `producer = R`, which verifies under
    R's OWN registered key and is ADMITTED by §6.6. The forgery is never made in U's
    name, so "U's own records are still refused" does not touch it. An earlier
    revision of this item stated the rule over recognized tokens only; THAT IS
    WITHDRAWN.
    TWO READER POLICIES ARE PERMITTED, AND THEY DIFFER IN ONE CASE AND NOWHERE ELSE
    — a duplicate group consisting ENTIRELY of unregistered tokens:
        POLICY A  no recognized token shares a key with anything; a group of
                  unregistered tokens ALONE is tolerated and the mapping stays
                  usable. A signature over such a token's claim MAY VERIFY, and
                  §6.6 then REFUSES the record during construction. Harmless
                  THROUGH THE REGISTRY
        POLICY B  the reader fails closed on ANY duplicate, INCLUDING one that
                  involves only unregistered tokens, and refuses the mapping over
                  all its entries; the submission is REFUSED with
                  AUTHENTICATION_KEY_UNAVAILABLE, with no signature verification and
                  no construction. Harmless THROUGH A REFUSED MAPPING
    A group holding a recognized token fails the mapping closed under BOTH policies,
    so NO reader policy can admit a mapping on which a recognized token shares a key.
    A reader MUST BE CONSISTENT between them, and NEITHER policy is harmless because
    "authentication fails" as a property of the claim — under A the signature may
    succeed, and under B it is never attempted. What holds under BOTH is the
    INVARIANT the record must express: an unregistered token acquires NO §6.5
    identity, and a submission naming it is NEVER ACCEPTED. This is a compliance
    condition of the mechanism rather than advice, because a shared key leaves
    §6.5's string comparison as the only thing refusing a cross-producer forgery —
    and §7.2 already records that a registry check is not an authentication check.

(d) §7.3.3 and §7.3.4 define the PROOF: a `message_b64u` field carrying the signed
    input as canonical UNPADDED Base64url, and an Ed25519 `signature` over the
    DECODED bytes. The proof is carried ALONGSIDE the submitted mapping and NOT as a
    field of the EvidenceRecord, and it is required at BOTH public entry points —
    `admit()` and `admit_to_store()` — with an omitted or `None` proof producing
    REJECTED rather than a TypeError. The signed input is specified as BYTES AND
    ORDERING — a fixed domain tag, a separator, a protocol version, a separator, and
    the canonical serialization of the complete supplied mapping encoded as UTF-8 —
    rather than as an instruction to sign a mapping. Both the tag and the version
    are INSIDE the signed bytes. §7.3.4 records what a prefix does and does not
    guarantee about cross-protocol reuse, as an obligation on other protocols rather
    than as a universal claim.

(e) §7.3.5 separates VERIFICATION from BINDING as two operations that must both
    pass: the signature is checked over the bytes the verifier HAS OBTAINED (the
    carried message), and the carried message is then required to equal the
    verifier's own reconstruction. Neither operation implies the other.

(f) §7.3.6 defines AI-05-CJ-1, a COMPLETE canonical-JSON profile, rather than
    describing a serializer by its properties. Its WIRE FORMAT is RFC 8785 (JCS)
    with exactly ONE extension — arbitrary-precision plain-decimal integers, which
    is what preserves `g_ordinal`'s existing unbounded non-negative integer rule —
    and every other rule is RFC 8785 verbatim: UTF-16 code-unit key ordering,
    literal UTF-8 for non-ASCII, NO Unicode normalization, minimal escaping with
    lowercase \u hex, no whitespace outside strings, and an explicit out-of-domain
    set.
    THE INPUT ADAPTERS ARE SEPARATED FROM THAT EXTENSION AND ARE STATED NOT TO BE
    EXTENSIONS, because each produces bytes RFC 8785 would produce for an
    equivalent plain value: a StrEnum member renders as its canonical string
    (identical to a plain str of the same value), a tuple as a JSON array
    (identical to a list), and bool dispatches BEFORE the integer rule so True is
    `true` and never `1`. An adapter that produced bytes no plain value could WOULD
    be an extension, and would have to be listed with the integer one and versioned
    with the profile; there is none, which is what makes "exactly one extension"
    checkable rather than a slogan.
    It carries NORMATIVE TEST VECTORS with exact bytes, states that LINE WRAPPING in
    them is PRESENTATION ONLY and never part of a serialized value, and gives
    VECTOR 1's canonical text on a SINGLE PHYSICAL LINE as well as wrapped. The
    NEGATIVE CONTROLS ARE STATED AS TWO CASES EACH, because §7.3.5 runs V4 before
    V5: a control whose message is altered while the ORIGINAL signature is retained
    is refused at V4 with AUTHENTICATION_SIGNATURE_INVALID, and one carrying a VALID
    signature over the altered message is refused at V5 with
    AUTHENTICATION_INPUT_MISMATCH. Assigning one result to both would test the wrong
    stage in one of them.
    It records that any change is a BREAKING change requiring a new PROOF_VERSION,
    and that §15.2's digest input, §14.6.1's generated digests and the stored form
    are UNCHANGED: AI-05-CJ-1 governs the SIGNED INPUT and nothing else.

(g) NEW §30 step 7b places authentication AFTER step 7's rule set and BEFORE
    CONSTRUCTION — steps 1-4, 4b, 6, 8-11 and 13, and NOT step 12. §7.3.7 carries
    the full seven-stage table, in which EVERY §30 step appears EXACTLY ONCE. The
    position has TWO parts and they MUST NOT be merged: §14.6 R2 forces STEP 7
    first, because construction derives ContextRef.value_digest and R2 forbids
    hashing a value that was not admitted; and this contract places AUTHENTICATION
    before construction, because no typed record — and therefore no Evidence
    digest — may be derived from a claim that is not authenticated. §30's NUMBERS
    IDENTIFY STEPS AND ARE NOT AN EXECUTION ORDER: step 6 is part of construction
    and has NOT run when step 7b executes, and STEP 13 RUNS BEFORE STEP 12 because
    `from_mapping` stamps the identity while `assign_digests` computes the two
    record digests afterwards.
    STEP 7 IS THE ONLY EXISTING ADMISSION CHECK THAT RUNS BEFORE AUTHENTICATION.
    It is NOT the only thing that runs before construction: step 7b runs there too,
    and so do §7.3.5's V1 (envelope validation) and V2 (the producer-token read).
    The distinct claim step 7 carries is that it is the one ADMISSION check
    already in this contract that precedes authentication.

(h) §7.3.7 separates three operations that ordinary speech calls "hashing" —
    deterministic serialization, Ed25519's internal message compression, and
    Evidence digest computation — and records that R2 governs only the third.

(i) §7.3.8 fixes the failure semantics: the outcome stays REJECTED, NO outcome
    member is added, and SIX distinct reason codes cover every mandatory
    authentication failure. An UNREADABLE PRODUCER TOKEN gets no code of its own: it
    is reported with an existing shape reason (RECORD_MALFORMED,
    MISSING_REQUIRED_FIELD or FIELD_CLASS_VIOLATION), and no key lookup or
    cryptography runs on that path.
    Where step 7's published rule and authentication both fail, STEP 7's reason is
    reported, by the precedence §30's step-7 note already establishes for a
    shape-vs-rule collision. The precedence is NOT a statement that class validation
    precedes authentication: step 6's class checks run inside construction and have
    not run when step 7b executes.

(j) §7.3.9 records the revocation model as it actually is — removal from the
    mapping stops new claims and does NOT reach backwards — and states the residual
    risks: process control, key custody, and the limit that this authenticates a KEY
    HOLDER and not the execution identity of a code component.

(k) §22.2's condition table gains the authentication rows, so the failure appears
    where every other rejection already appears.
```

```text
WHAT THIS AMENDMENT DOES NOT DO, stated because each is a thing it could be read as
doing:

    it does NOT implement the mechanism. §7.3 DEFINES a standard; §30 step 7b
      REQUIRES it. Neither is code, and neither is a test.
    it does NOT claim the standard currently holds. THE IMPLEMENTATION DOES NOT
      PERFORM §30 STEP 7b TODAY, and this amendment does not pretend otherwise.
      That divergence is RECORDED below rather than left to be discovered.
    it does NOT close AI15-OPEN-1. AI-15 §15.2 STEP 0b requires a mechanism AND its
      implementation AND tests showing it holds; this amendment supplies the first
      of the three. Whether that closes AI-15's record of the item is AI-15's act,
      not this amendment's.
    it does NOT reopen or weaken Amendment 4. Reading A stands, the submitter MAY
      differ from the producer, and §7.2's three checks remain three.
    it does NOT touch AI-11 §21.1's OPEN-1 — WHICH PRODUCERS EXIST. Adding a key
      mapping creates no registry row and admits no event. It is a different
      question with the same owner.
    it does NOT add a producer token, registry row, Evidence kind, family,
      producer_type, admission outcome, identity field, canonical collection or
      digest input.
    it does NOT add a stored field. The proof is not stored, and the stored form is
      unchanged.
    it does NOT change the record schema. The proof is carried beside the mapping.
    it does NOT repurpose AI-13's approval ingress, its anchor or its Ed25519
      verification site. Producer authenticity and human approval are different
      trust domains (§7.3.10).
    it does NOT change any authority relation. An authenticated producer claim is
      not a permission, and no authority matrix row moves (§7.3.8).
    it does NOT authorize a production Evidence writer to be created or run.
    it does NOT make any of its acceptance tests pass. NO TEST NAMED IN §7.3.7 HAS
      BEEN RUN.
```

```text
STATUS DISCIPLINE — WHAT THIS AMENDMENT DOES AND DOES NOT MOVE. Stated as explicit
non-movements, because a reader reaching for a status line is exactly the reader most
likely to over-read it:

    AI15-OPEN-1             REMAINS OPEN. This amendment DEFINES a standard for it.
                            It does not show the standard holds. Only AI-05, by
                            implementing the mechanism and shipping the mandatory
                            tests, supplies the evidence that closes it.
    AI-15 STEP 0b           REMAINS UNSATISFIED. STEP 0b requires a mechanism AND its
                            implementation AND tests showing it holds. This amendment
                            supplies the FIRST of the three, and MUST NOT be reported
                            as having satisfied the other two.
    production writer       NOT AUTHORIZED. No production non-test caller that can
                            execute admission and persist a record is authorized to
                            be created, merged or run by this amendment, and AI-15
                            §17.2b's prohibition is NOT lifted by it.
    AI-14 STEP 1            NOT AMENDED, NOT MADE, NOT PRE-EMPTED. It is AI-14's act,
                            on AI-14's contract, under AI-14's amendment rule. This
                            amendment neither authorizes the composition -> Evidence
                            edge nor speaks for AI-14.
    B5                      REMAINS BLOCKED, AND IS NOT CLASSIFIED CONNECTED. No
                            clause here may be read as classifying it. §8.3's
                            conditions remain unsatisfied, including 11 and 12.
    AI15-OPEN-3,            REMAIN INDEPENDENT AND UNSOLVED. This amendment does not
      AI15-OPEN-4,          touch DecisionRecord.evidence_ref (AI-04's), a
      AI-11 §21.1 OPEN-1    workflow-driven step's routing input (AI-13/AI-14's), or
                            WHICH PRODUCERS EXIST (AI-05's own, and a DIFFERENT
                            question from OPEN-1: admitting a token would not
                            authenticate a claim, and authenticating a claim would
                            not admit a token).
    AI15-OPEN-2             REMAINS CLOSED under AI-05 Amendment 4 (READING A). It is
                            NOT reopened, re-argued or re-decided here, and no clause
                            of this amendment restates it in weaker words.
```

```text
RECORDED DIVERGENCE — THE CONTRACT NOW REQUIRES A STEP THE IMPLEMENTATION LACKS.

    §34.2 forbids an implementation silently diverging from this contract, and this
    amendment creates a divergence by construction: §30 step 7b is now part of the
    admission contract, and `admit()` / `admit_to_store()` do not perform it. That
    is stated here rather than left to be found.

    WHY IT IS CURRENTLY CONSEQUENCE-FREE, in three parts that MUST NOT be merged:
        NO CALLER      no production non-test caller of admission exists anywhere in
                       the repository. A step no caller reaches cannot be skipped
                       by one.
        NO WRITER      AI-15 §17.2b forbids creating a production call site that can
                       execute admission and persist a record while AI15-OPEN-1 is
                       open. That prohibition is NOT lifted by this amendment.
        CONTRACT FIRST AI-05-A is the frozen contract and AI-05-B is NOT STARTED
                       (§35.3). This project freezes the contract before the code
                       that satisfies it.

    WHAT IT MEANS UNTIL IMPLEMENTED, stated so nothing is over-reported:
        a record admitted by the CURRENT implementation has NOT had its producer
          claim authenticated, and NO document, caller or result may describe it as
          having had one
        §8.3 condition 11 of the AI-15 plan remains UNSATISFIED
        §30 step 7b MUST NOT be reported as satisfied, and this amendment MUST NOT
          be reported as having closed AI15-OPEN-1
```

```text
SECURITY IMPACT

    NO NEW RUNTIME CONTROL SHIPS WITH THIS AMENDMENT, AND NO ATTACK IS DEFEATED BY
    IT TODAY — stated precisely, because the broader claim "AI-05 now authenticates
    producers" would be false.

    WHAT THIS AMENDMENT DOES
        defines, in enforceable and testable terms, the standard a producer claim
          must meet, so that an implementation has something exact to satisfy and a
          review has something exact to check
        fixes the trust model's shape BEFORE any code exists, which is when it is
          cheapest to get right: one reader, no caller-selected trust root, no
          default, no bypass, fail closed
        requires DISTINCT key material per producer token, closing the shared-key
          forgery the design admits if that is left implicit
        gives domain separation and protocol versioning a defined byte form, so a
          signature minted for this protocol cannot be replayed into another
        records what the mechanism does NOT establish, which is the failure mode
          most likely to be summarised away

    WHAT IT DOES NOT DO
        it implements nothing, tests nothing, and changes no runtime behaviour. The
          implementation of §30 step 7b is an AI-05-B obligation
        it defeats no attack at this baseline, because no caller reaches admission
        it authenticates no key holder, because no key is configured anywhere
        it provides NO time-bounded validity and NO revocation list; revocation is
          removal from a deployment mapping and does not reach stored records
        it does not defend against an adversary who controls the process address
          space, and does not claim to

    RESIDUAL RISKS — RECORDED, NOT CLOSED
        an in-process library cannot defend its own address space; the mapping is
          only as trustworthy as the deployment that supplies it
        key custody is a trust assumption and is outside this contract
        the mechanism authenticates a KEY HOLDER, not the execution identity of a
          code component; the step from one to the other is a deployment assertion
        producer authentication is not submitter identity, not authorization, and
          not evidence that a claim's content is true
```

```text
AUTHORITY IMPACT
    None. §7.3.8 states that an authenticated producer claim is not a permission, a
    capability, a verification or a measurement, and that it changes no row of any
    authority matrix. An authentication failure is not a Guard DENY and is never
    translated into one. §23 and §24 are unchanged.

CONTRACT IMPACT
    ADDED        §7.3 (new), §30 step 7b, §22.2 rows, this amendment record
    AMENDED      §7.2's authentication row and its closing FROZEN block, to point at
                 §7.3 rather than to record the check as absent. Both edits are
                 annotations; no requirement of §7.2 changes
    UNCHANGED    §6.5, §6.6, §7.1, §11, §12, §13, §14 (all), §15, §17, §18, §20,
                 §22.1, §22.3, §22.4, §23, §24, §25, §26, §30's other steps, §34.1,
                 §34.2, §35
    NO CHANGE TO   the record schema, the canonical collections, the digest inputs,
                 the stored form, the outcome vocabulary, the registry, or any
                 authority relation
```

**AI-05 remains INCOMPLETE.** This amendment defines a standard and records that it
is not implemented. It closes nothing: not AI-11 §21.1's OPEN-1, not AI15-OPEN-1, not
AI15-OPEN-3, not AI15-OPEN-4, and not §35.1's deferrals.

---

#### Amendment 6 — the producer trust configuration is frozen (2026-10-11)

Found while performing an implementation-readiness review of §30 step 7b against this
contract. Amendment 5 defined **what** makes a producer claim authenticated and left
**where the trust root comes from** unnamed: §7.3.2 requires the designated mapping to
be read "from exactly ONE place, by exactly one module", forbids a caller-selected
trust root, and states that a deployment with no mapping authenticates nothing — but
it names neither the place nor the module, nor the mapping's format, nor the encoding
of a key within it, nor how a deployment selects between §7.3.2's two reader policies.
An implementer would have had to invent all five, and each invented answer becomes a
deployment interface that proofs are verified against. This amendment supplies them.
It is authored on a docs-only branch based on main
`f9e3b4217bbf66285e930bcff48824a028f6786d`.

**Why this is an amendment rather than a clarification made in place.** §34.1's list
of changes requiring an amendment enumerates evidence kind, canonical collection,
digest input, workspace rule, secret boundary, authority relation, identity field and
admission outcome. This amendment changes **none** of them. §34's preamble is broader
than its list, though — a frozen contract "changes only through an explicit amendment
recorded in §34.3" — and this amendment adds a NEW SECTION to §7 that a deployment's
keys are read under, adds a Layer 0 obligation to §31, and corrects the status
records in §35.3 and `## Status`. That is a change however it is described, so the
instrument is an amendment, recorded here. The fact that none of those three is in
§34.1's enumeration is recorded rather than relied on, exactly as Amendments 4 and 5
recorded the same about §7.

```text
(a) NEW §7.3.11 names the ONE place §7.3.2 left unnamed: the environment variable
    WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG, and nothing else. No configuration
    file, no default path, no keyring, no network source, no build-time embed and no
    second variable. It also names the ONE READER:
    plugins/evidence/producer_auth.py.
    Naming the two is what makes §7.3.2's "read from exactly ONE place, by exactly
    one module" checkable rather than aspirational. §7.3.2 is NOT reworded: the
    properties it fixed are unchanged, and this section supplies the name they were
    missing.

(b) THE VALUE IS A STRICT JSON OBJECT WITH EXACTLY TWO MEMBERS, both required and
    closed-keyed:
        collision_policy   the JSON string "A" or "B"
        producer_keys      an object mapping a producer-token string to its Ed25519
                           PUBLIC key, each exactly 64 LOWERCASE hexadecimal
                           characters decoding to 32 bytes
    An unknown member, an absent member, a misspelled member, a member of the wrong
    JSON type, a root that is not an object, an empty value, and a value that is not
    encodable as UTF-8 are EACH an invalid configuration, refused as a whole.
    Uppercase hex is REFUSED, never normalized, applying §14.5.1's case policy for
    the same reason it exists there: a value AI-05 accepts is a value AI-05 must not
    rewrite.
    THE PARSING IS STRICT. A DUPLICATE OBJECT KEY IS REFUSED AT EVERY LEVEL,
    INCLUDING INSIDE `producer_keys` — a reading that keeps the last one has made a
    silent choice about which trust root the deployment holds, which is the same
    defect §7.3.6 rule 8 refuses on a JSON transport. `NaN`, `Infinity` and
    `-Infinity` are NOT JSON and are refused; a parser that accepts them accepts
    input RFC 8259 does not define. Nothing may follow the document. Whitespace is
    insignificant and permitted, because RFC 8259 permits it.

(c) VALIDATION IS WHOLE-MAPPING AND PARTIAL ACCEPTANCE IS FORBIDDEN. The reader
    MUST NOT authenticate against the entries it managed to parse, skip a malformed
    entry and continue, fall back to a default, a development mapping, a cached
    mapping or a subset, or recover silently. §7.3.2's "no default mapping, no
    development mapping, no `verify=False` switch" is unchanged and this amendment
    adds no path around it.
    An entry for a token §6.5 does NOT register is PERMITTED and remains INERT
    (§7.3.2); its presence is nevertheless load-bearing, because it participates in
    the group rule. `producer_keys` MAY be empty, which designates a mapping with no
    entries and rejects every submission — the same outcome §7.3.2 assigns a
    deployment with no mapping at all. That is not partial acceptance: there is no
    entry for a partial reading to keep or drop.
    WHICH TOKENS COUNT AS RECOGNIZED IS §6.5's ANSWER. The reader consults the §6.5
    registry to decide whether a colliding group contains a recognized token. It
    does not restate the registry, cache a drifting copy of it, or treat a
    `producer_keys` entry as evidence of recognition.

(d) `collision_policy` SELECTS §7.3.2's policies AND DOES NOT DEFINE THEM. §7.3.2's
    group rule, both policies and the requirement that a reader be CONSISTENT are
    incorporated by reference and are NOT restated, reworded or extended:
        "A"   POLICY A — a group consisting only of unregistered tokens is
              tolerated; every group containing a recognized token still fails the
              whole mapping closed
        "B"   POLICY B — the mapping is refused over ALL its entries on ANY
              duplicate public key, including one involving only unregistered tokens
    Under BOTH policies a group containing at least one recognized token fails the
    mapping closed, so no selector value can admit a mapping on which a recognized
    token shares a key. §7.3.2 records that which policy a deployment runs "is a
    DEPLOYMENT FACT, not a choice any caller makes"; this is where that fact is
    expressed, in the same document and by the same mechanism as the key material,
    which is precisely why no caller can reach it.

(e) FAILURE IS ONE EXISTING REASON CODE AND NO SEVENTH IS ADDED. A missing,
    malformed, incomplete, unparseable or otherwise invalid configuration — and a
    mapping the reader refuses under the group rule — are EACH reported as
    AUTHENTICATION_KEY_UNAVAILABLE. §7.3.8 fixes SIX codes and states that no
    outcome member is added; §7.3.5's V3 already assigns this exact code to "no
    designated mapping at all, or no entry for the claimed token". A refused
    mapping IS a deployment with no usable mapping, and this amendment reports it
    where §7.3.2 and §7.3.5 already report that state.
    THE SIX CODES AND THEIR ORDER ARE UNCHANGED, AND CONFIGURATION FAILURE DOES NOT
    JUMP THE QUEUE. §7.3.5 runs V1 before V2 before V3 and this amendment does not
    reorder it: a malformed proof ENVELOPE is reported AUTHENTICATION_PROOF_MALFORMED
    even when the configuration is also invalid, and an UNREADABLE producer token is
    reported with an existing shape reason even when the configuration is also
    invalid — because V2 runs before V3 and performs no key lookup. Reading and
    validating the configuration does not move ahead of a check §7.3.5 places before
    it. An invalid configuration affects EVERY submission equally: there is no
    submission, token, kind, family or caller for which it yields ACCEPTED or a
    different code.

(f) ONE INITIALIZATION, ONE PROCESS-LIFETIME SNAPSHOT. The configuration is read and
    validated EXACTLY ONCE, during the initialization of the one reader module, and
    the state it produces is the sole authority on the deployment's trust root for
    the lifetime of that process. The state is VALID or INVALID and BOTH ARE FINAL:
    an INVALID state is retained as INVALID, and every admission reaching V3 under it
    is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE with no fallback of any kind.
    Initialization does NOT raise — an invalid configuration is a state the process
    holds, not an exception it throws and not a failure to import.
    A CONFIGURATION UPDATE TAKES EFFECT ONLY THROUGH A CONTROLLED PROCESS RESTART.
    That is what §7.3.9's "deploying the updated mapping" means; §7.3.9's revocation
    model is unchanged and this item fixes how the updated mapping ARRIVES. A later
    change to the variable does NOT reload the trust root: there is no re-read, no
    TTL, no invalidation hook, no signal handler and no reload path.
    AN IMMUTABLE AUTHORITATIVE SNAPSHOT IS NOT A LAST-KNOWN-GOOD FALLBACK, and the
    two are opposites. A fallback would keep verifying against a trust root the
    deployment had WITHDRAWN, so an operator who revoked a token by removing its
    entry would find the revocation had not taken effect.
    AN EARLIER REVISION OF THIS AMENDMENT REQUIRED "ONE SNAPSHOT PER ATTEMPT". THAT IS
    WITHDRAWN AND REPLACED. It bounded each attempt but left the SEQUENCE of attempts
    unconstrained, and the sequence is where a last-known-good fallback lives: a
    per-attempt read means a second read, a second read is what a fallback falls back
    FROM, and a reader that kept serving a mapping cached by an earlier successful
    attempt would have performed that fallback without anyone asking it to. A
    once-only capture makes the fallback UNREACHABLE rather than merely forbidden.
    What the withdrawn form correctly required is KEPT: one verification still
    decides key selection, the group rule and the enforced policy against ONE value,
    and no read occurs between selecting a key and applying the collision rule — a
    value that never changes cannot change mid-verification.
    THE ENVIRONMENT IS A DEPLOYMENT INPUT AND NOT A CONTROL SURFACE. No repository
    code outside the trusted deployment mechanism assigns, mutates, unsets or writes
    the variable, and the reader module is not reloaded to re-trigger its
    initialization. §31.3 states the static obligation that enforces this, alongside
    the one-reader and no-caller-selected-trust-root rules.

(g) TWO SERIALIZATIONS THAT MUST NOT BE CONFUSED, AND A THIRD THAT IS NEITHER.
    §7.3.6 already froze that AI-05-CJ-1 governs the SIGNED INPUT and nothing else,
    and that unifying it with §15.2's digest input is a separate amendment. This
    amendment's JSON rules govern the CONFIGURATION DOCUMENT and nothing else. Three
    serializations, three purposes, no unification — and in particular the
    configuration's tolerance MUST NOT LEAK INTO THE SIGNED-INPUT PATH: JSON permits
    insignificant whitespace and any member order, AI-05-CJ-1 permits neither, and a
    serializer that produced the configuration's member order or a pretty-printed
    variant of it would produce bytes over which a proof means nothing this contract
    defines. THE SIGNED INPUT IS PRODUCED BY THE AI-05-CJ-1 SERIALIZER AND BY NOTHING
    ELSE, INCLUDING AND ESPECIALLY NOT BY WHATEVER ROUTINE PARSED THE CONFIGURATION.
    The configuration value is never part of a signed input: `signed_input` is built
    from the submitted mapping (§7.3.4), and the configuration is not a record field,
    is not covered by any signature and is not stored (§7.3.3).

(h) TRUST-DOMAIN INDEPENDENCE IS MUTUAL. §7.3.10 already records that AI-13's
    designated approval ingress, its anchor and its Ed25519 verification site are NOT
    repurposed, NOT read and NOT widened by §7.3. §7.3.11 adds the converse: the
    reader MUST NOT read AI-13's anchor variable, MUST NOT accept an AI-13 approval
    as a producer proof, and MUST NOT treat a producer proof as an approval. The
    configuration carries PUBLIC key material only; it never carries, and the reader
    never accepts, a private signing key, so the deployment holds verification keys
    and cannot mint the proofs it checks.
    AN AUTHENTICATED PRODUCER CLAIM IS NOT AN APPROVAL, A PERMISSION, A CAPABILITY
    OR A GUARD RESULT (§7.3.8). A valid, readable, internally consistent
    configuration grants nothing to anyone.

(i) §30 step 7b CARRIES THE CROSS-REFERENCE. The step now states which mapping it
    reads, where from, by which module, and that an invalid configuration or a
    refused mapping is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE — §7.3.5 V3's
    existing code. No step is added, removed, renamed or reordered, and §7.3.7's
    seven-stage table is unchanged.

(j) NEW §31.3 RESOLVES A SCOPE AMBIGUITY IN THE TEST MATRIX. Amendment 5 created
    §7.3.7's acceptance obligation and gave it no T-numbers, while §31 declares
    itself "the test matrix" and FROZEN — so a reader could conclude that §7.3.7's
    list sits outside the matrix or is advisory. §31.3 records that §7.3.7's
    obligation IS part of the matrix, incorporated BY REFERENCE, with the same layer,
    the same force and the same "MUST exist before the standard may be reported as
    holding"; that §31's T-numbering is NOT extended by this amendment and §7.3.7's
    identifiers govern until one does; that nothing in §31 is removed, merged,
    renumbered or weakened; and that T35's architecture-boundary row applies to the
    new module unchanged.
    §31.3 ALSO DECLARES THE LAYER 0 EXCEPTION THIS MECHANISM REQUIRES, and that
    exception is TWO IMPORTS IN ONE NAMED MODULE: `os` and `json`, in
    `plugins/evidence/producer_auth.py`, for the configuration and nothing else. That
    module may not read a file, call `open()`, walk a path, import `io`, `pathlib`,
    `shutil`, `tempfile` or any other filesystem root, or reach any configuration
    source other than the one variable §7.3.11 names. `store.py` remains the only
    module that touches a filesystem and every other restriction stands. Layer 0 must
    additionally enforce the FOUR rules §31.3 lists for this module — ONE READER,
    NO MUTATION, IMMUTABLE STATE and NO CALLER-SELECTED TRUST ROOT — in the shape
    AI-13 §13.3's boundary already uses for its own domain.
    THIS AMENDMENT DOES NOT MAKE THAT LAYER 0 CHANGE. `scripts/ci/layer0_policy.py` is
    NOT edited here. The exception and the four enforcement rules are obligations on
    the change that IMPLEMENTS producer authentication; until that change lands there
    is nothing for a widened rule to permit, and the existing rule would refuse the
    new module. That refusal is the correct and visible behaviour, not a defect to be
    worked around.

(k) §35.3 AND `## Status` ARE CORRECTED, and the correction is recorded in place.
    Both carried "AI-05-B = NOT STARTED" and "plugins/evidence/ README.md placeholder
    only" in the PRESENT TENSE, which had stopped being true when B1 and B2 merged.
    They now state what is true, and keep the freeze-time values labelled as what
    they were. The correction distinguishes FOUR states that must not be collapsed:
    the record model and admission pipeline are BUILT; the producer-authentication
    mechanism is DEFINED AND NOT BUILT; a production writer / non-test caller is
    ABSENT; and no Evidence record has been stored.
    THE CORRECTION DOES NOT WEAKEN AMENDMENT 5's RECORDED DIVERGENCE, which cited
    §35.3's stale line among its grounds. That record's other two grounds are
    independent and both still hold — NO CALLER (no production non-test caller of
    admission exists anywhere) and NO WRITER (AI-15 §17.2b forbids creating one while
    AI15-OPEN-1 is open). Step 7b is unimplemented AND unreachable, and it is the
    second fact that carries the argument. Correcting a citation does not move the
    conclusion it was cited for; this is recorded rather than left to be re-derived.

(l) THE NO-MUTATION RULE WAS NAME-BASED, AND NAME-BASED IT CONTRADICTED THIS
    AMENDMENT'S OWN TEST MECHANISM. As first written it read: "The variable name
    appearing outside the reader is itself the finding, because a second module that
    can NAME it can write it." §31.3's testing clause requires the opposite: a child
    process can only be given a configuration by a launcher that NAMES THE VARIABLE.
    The contract therefore PROHIBITED AND REQUIRED THE SAME THING, which is the one
    state a frozen document must never be in.
    THE RULE IS NOW SHAPE-BASED, BECAUSE IT HAS TO BE. What is forbidden is WRITING
    THE RUNNING PROCESS'S ENVIRONMENT; what is permitted is HANDING A VALUE TO A
    PROCESS THAT HAS NOT STARTED. The static rule distinguishes them by the SHAPE of
    the use and not by the presence of the name.
    ONE NARROW HARNESS EXCEPTION IS SPECIFIED, AND IT IS NARROW IN THREE WAYS:
        one module     tests/evidence/trust_harness.py, the only place outside the
                       reader where the name may appear
        one shape      only as a key in the environment mapping handed to a
                       child-process launch — never an assignment to the running
                       process's environment and never `os.putenv`
        one variable   the designated one, and no other configuration source
    It is NOT an exception for tests in general and NOT one for any production
    module. A second module naming the variable, or this module naming it in another
    shape, is the NO MUTATION finding.
    THE EXCEPTION WAS VERIFIED AGAINST THE EXISTING ARCHITECTURE BEFORE IT WAS
    WRITTEN, because "subprocess is available in Python" is not a permission:
        a separate interpreter is ALREADY spawned from this suite —
          `tests/evidence/test_canonical.py:119-143` runs
          `subprocess.run([sys.executable, "-c", program], ...)` as the cross-process
          half of T7
        no Layer 0 rule constrains `tests/` on this axis: the `subprocess`
          restrictions in `scripts/ci/layer0_policy.py` are scoped to
          `plugins/evidence`, `routing/`, `benchmarks/`, `workflows/` and
          `composition/`, and `tests/` is reached only by `check_layer_markers`,
          which globs `test_*.py`
        so a `trust_harness.py` support module is not a test module, needs no layer
          marker, and adds no path a deployment lacks
    A FOURTH ENFORCEMENT RULE IS ADDED: IMMUTABLE STATE. §31.3 now requires that the
    captured mapping and policy are held privately, are never returned as a whole by
    any public function, are never handed to another module as a structure it could
    mutate, and are not rebound, replaced, `setattr`-ed or monkeypatched BY ANY CODE IN
    THIS REPOSITORY — with no public initializer, reset, setter or "load for tests"
    entry point. The reader answers a PER-TOKEN question and exposes neither the
    mapping, the policy nor the parsed document. This is what stops a test from passing
    by REPLACING the state it was supposed to exercise, and what stops repository code
    from replacing a trust root it is not allowed to write.
    THE RULE IS A SOURCE-TREE RULE AND NOT A CLAIM OF TAMPER-PROOFNESS. It was
    corrected to say so, and the correction is recorded in (n).
    STARTUP ORDER IS NOW STATED. §7.3.11 gained a REQUIREMENT that the implementing
    change initialize the reader through the Evidence package's own initialization
    path, and it separates CONFIGURATION SUPPLIED WHEN A PROCESS STARTS from A VARIABLE
    READ AFTER ARBITRARY APPLICATION CODE HAS RUN. It records what the guarantee does
    NOT cover — code outside this repository writing the process environment before the
    first import — as a RESIDUAL RISK on the same footing as §7.3.9's, rather than
    claiming it closed. THIS CREATES NO CALLER AND NO ENTRY POINT: the import edge is
    within the Evidence package, between a module and the package that owns it.
    THIS PARAGRAPH DESCRIBED THAT CLAUSE IN THE PRESENT TENSE, AS THOUGH THE IMPORT
    EDGE AND THE ORDERING IT BUYS ALREADY EXISTED. THEY DO NOT, AND (m) CORRECTED THE
    CLAUSE. This paragraph is kept as the record of what this item did, with the
    correction named rather than restated; THE CLAUSE ITSELF, NOT THIS SUMMARY, IS THE
    AUTHORITY for what §7.3.11 now says.

(m) §7.3.11's STARTUP-ORDER CLAUSE WAS WRITTEN IN THE PRESENT TENSE ABOUT CODE THAT
    DOES NOT EXIST, AND IS CORRECTED. The block "WHEN THE READ HAPPENS, AND WHY THAT
    ORDER IS THE POINT" said that `plugins/evidence/__init__.py` IMPORTS
    `producer_auth`, and concluded that any process able to call `admit()` HAS
    NECESSARILY ALREADY initialized the reader. NEITHER IS TRUE OF THE REPOSITORY:
    `plugins/evidence/producer_auth.py` does not exist and `plugins/evidence/__init__.py`
    does not import it. A frozen requirement was stated as a fact, which is the same
    over-claim this contract refuses everywhere else — §34.3 records the mechanism as
    DEFINED AND NOT BUILT, §7.3.7 records that no acceptance test has been run, and
    §35.3 records that §30 step 7b is performed by nothing.
    THE CLAUSE NOW SEPARATES THREE THINGS THAT WERE RUN TOGETHER:
        THE REQUIREMENT       the implementing change MUST initialize the reader
                              through the Evidence package's own initialization path,
                              before either admission entry point is available, with
                              no lazy path, no first-call initialization and no
                              admission-time read
        THE GUARANTEE         once that lands, a process able to call either entry
                              point will necessarily have initialized the reader, and
                              the ordering is structural rather than conventional
        THE CURRENT STATUS    the module does not exist, the import edge does not
                              exist, and the ordering does not exist at runtime today.
                              Amendment 6 SPECIFIES the ordering; it does not
                              establish that it is present, and §7.3.11 MUST NOT be
                              cited for the proposition that it is
    The adjacent "what is claimed" and "the contract's guarantee" clauses were
    corrected on the same footing: each now states a RULE THE CONTRACT IMPOSES and a
    property §31.3 obliges Layer 0 to check, rather than a description of what the
    repository does today — which is nothing.
    WHETHER THE IMPORT EDGE IS THE RIGHT SHAPE IS NOT REOPENED. It remains the
    requirement, for the reason §7.3.11 gives: it is an edge WITHIN the Evidence
    package, between a module and the package that owns it, so it creates no caller
    and no entry point and leaves AI-15 §17.2b untouched.
    THE TEST-HARNESS CLAUSE IS ALSO SHARPENED, AND THE CHANGE IS A NON-CLAIM RATHER
    THAN A NEW RULE. §31.3 already recorded that an unrunnable child is NOT_RUN and
    never a passing authentication test. It now also records that A GREEN CI RUN IS
    NOT EVIDENCE THAT THE STANDARD HOLDS: the suite exits 0 whether its cases passed
    or were skipped, so CI success alone MUST NOT be used to claim that AI-15 §15.2
    STEP 0b is satisfied or that the §7.3 standard has been shown to hold. Because
    §8.3 condition 11 is discharged by exactly those cases, a skipped case leaves
    condition 11 UNSATISFIED however green the run is, and a report must carry the
    number of process-isolated cases that RAN rather than the run's status.

(n) THE IMMUTABLE-STATE RULE WAS STATED AS A PROPERTY OF PYTHON. IT IS A RULE ABOUT
    THIS REPOSITORY, AND THE SCOPE IS NOW PRECISE. §31.3's IMMUTABLE STATE rule said
    the captured state is one that "no assignment to, `setattr` on, or monkeypatch of
    it SUCCEEDS", and (l) summarised it as state that "cannot be rebound, replaced,
    `setattr`-ed or monkeypatched from outside". BOTH READ AS CLAIMS ABOUT THE
    LANGUAGE, AND NEITHER IS TRUE: attributes can be rebound, module globals can be
    reassigned, and an actor inside the process can reach past any arrangement of
    them. A contract that claims otherwise would be claiming a sandbox it does not
    have.
    THE REQUIREMENT IS UNCHANGED AND IS NOW STATED AS WHAT IT IS: the state must be
    held privately, never returned as a whole, never handed out as a mutable
    structure, free of any public initializer, reset or setter, and not rebound by any
    code IN THIS REPOSITORY — and §31.3 obliges Layer 0 to CHECK THOSE SOURCE-TREE
    RULES. The enforcement is static, over the files this repository contains.
    THE QUALIFICATION IS RECORDED IN TWO PLACES, BESIDE THE RULES IT BOUNDS:
        §31.3     the four rules now carry WHAT THESE RULES ARE, AND WHAT THEY ARE
                  NOT: declared source-tree rules that DETECT the prohibited patterns
                  within their coverage, and NOT a runtime sandbox and NOT a proof of
                  immunity.
        §7.3.11   the same limitation, in the section that requires the immutability:
                  code able to execute inside the same process can reach in-memory
                  state no source-tree rule protects, and the section does not
                  contradict it.
    THIS ADDS NO ARCHITECTURE AND DESIGNS NOTHING NEW. §7.3.9 ALREADY RECORDS EXACTLY
    THIS LIMIT as PROCESS CONTROL — "an adversary who controls this process's address
    space can control the mapping and defeat any in-process check. An in-process
    library cannot defend its own address space, and this section does not claim to
    survive such an adversary." The correction ALIGNS the immutability clause with a
    residual risk the contract has carried since Amendment 5; it does not introduce
    one.
    THE QUALIFICATION IS NOT PERMISSION, AND IT RELAXES NOTHING. It bounds WHAT STATIC
    ENFORCEMENT CAN DELIVER. For normal repository code the requirements are ABSOLUTE:
    a module that writes the variable, replaces the captured state, hands out the
    mapping or accepts a caller-selected trust root is a FINDING and MUST NOT be
    merged. No reader may cite the qualification to argue that such code is tolerable
    because an adversary with in-process execution could do worse — the defect and the
    limit are different things, and the limit does not excuse the defect. §31.3 states
    this in the same clause.
    ONE RESIDUAL WAS CORRECTED WHILE INSPECTING THIS RECORD. (l)'s own summary still
    described §7.3.11's startup-order clause in the PRESENT TENSE — that
    `plugins/evidence/__init__.py` "imports the reader" and that the ordering
    "is therefore STRUCTURAL" — although (m) had already corrected the clause itself.
    The summary now states the clause as a REQUIREMENT and names (m); A SUMMARY IN
    THIS LOG DOES NOT OVERRIDE THE CLAUSE IT SUMMARISES.
```

```text
WHAT THIS AMENDMENT DOES NOT DO, stated because each is a thing it could be read as
doing:

    it does NOT implement the mechanism. It names a source, a format, an encoding, a
      reader module and a policy selector. NONE OF THEM IS CODE, and no test is added
      or run.
    it does NOT write plugins/evidence/producer_auth.py. §7.3.11 names a module that
      does not exist yet.
    it does NOT change scripts/ci/layer0_policy.py. §31.3 declares a Layer 0
      obligation for the implementing change; it does not make the change.
    it does NOT add a seventh reason code, an outcome member, a §6.5 row, a producer
      token, an Evidence kind, a family, a producer_type, an identity field, a
      canonical collection, a digest input or a stored field.
    it does NOT reword §7.3.1-§7.3.10, §30's other steps, §22.1's outcomes or §31's
      existing rows. §7.3.2's policies are SELECTED by the new selector and are not
      redefined.
    it does NOT authorize a production Evidence writer to be created, merged or run,
      and does NOT lift AI-15 §17.2b's prohibition.
    it does NOT make AI-14's STEP 1. It is AI-14's act, on AI-14's contract, under
      AI-14's amendment rule.
    it does NOT repurpose AI-13's approval ingress, anchor or verification site, and
      creates no approval path.
    it does NOT close AI15-OPEN-1. §15.2 STEP 0b requires a mechanism AND its
      implementation AND tests showing it holds. Amendment 5 supplied the standard
      and this amendment supplies the configuration — both are DEFINITION. The
      implementation and the tests remain outstanding.
    it does NOT make any §7.3.7 acceptance test pass, and NO TEST NAMED THERE HAS BEEN
      RUN.
```

```text
STATUS DISCIPLINE — WHAT THIS AMENDMENT DOES AND DOES NOT MOVE. Stated as explicit
non-movements, because a reader reaching for a status line is exactly the reader most
likely to over-read it:

    AI15-OPEN-1             REMAINS OPEN. The mechanism is now fully specified and
                            entirely unimplemented.
    AI-15 STEP 0b           REMAINS UNSATISFIED, for the same reason. A configuration
                            is not an implementation and not a test.
    production writer       NOT AUTHORIZED. Unchanged from Amendment 5.
    AI-14 STEP 1            NOT AMENDED, NOT MADE, NOT PRE-EMPTED.
    B5                      REMAINS BLOCKED and is NOT classified CONNECTED.
    AI15-OPEN-2             REMAINS CLOSED under Amendment 4 (READING A), not
                            reopened and not restated in weaker words.
    AI15-OPEN-3,            REMAIN INDEPENDENT AND UNSOLVED. This amendment does not
      AI15-OPEN-4,          touch DecisionRecord.evidence_ref (AI-04's), a
      AI-11 §21.1 OPEN-1    workflow-driven step's routing input (AI-13/AI-14's), or
                            WHICH PRODUCERS EXIST (AI-05's own).
```

```text
SECURITY IMPACT

    NO NEW RUNTIME CONTROL, AND NO ATTACK IS DEFEATED BY THIS AMENDMENT — stated
    precisely, because "the trust configuration is frozen" could be read as "AI-05
    now reads a trust configuration", which would be false. Nothing reads anything:
    the module §7.3.11 names does not exist.

    WHAT THIS AMENDMENT DOES
        it closes the last gap that made §30 step 7b unimplementable without an
          invented trust source, by fixing the source, the format, the key encoding,
          the reader module and the policy selector
        it makes the trust root UNREACHABLE FROM A CALLER by putting it in the
          environment, read by one named module, with no parameter anywhere that
          accepts a key, a mapping, an anchor, a verifier, a configuration object or
          a configuration path
        it fixes the failure direction: every configuration defect fails CLOSED, as
          one existing code, for every submission equally
        it fixes the trust root for the lifetime of a process, so a revocation
          actually takes effect when the deployment restarts and a withdrawn key is
          not silently kept in service by a fallback — and so no read can occur
          between selecting a key and applying the collision rule
        it puts the variable beyond the reach of the code that reads it: nothing in
          the repository writes the running process's environment, and the reader is
          not reloaded to re-read it
        it makes the captured state itself unreachable TO REPOSITORY CODE: held
          privately, never returned as a whole, never handed out as a structure
          another module could mutate, and not rebound by any module here — so a test
          cannot pass by REPLACING the state it was meant to exercise, and repository
          code cannot replace a trust root it may not write. THIS IS A SOURCE-TREE
          RULE AND NOT A RUNTIME SANDBOX: §31.3 and §7.3.11 both record that code able
          to execute inside the same process can reach in-memory state no static rule
          protects, which §7.3.9 already carries as PROCESS CONTROL
        it keeps the configuration's JSON tolerance out of the signed-input path,
          where it would silently change what a proof means

    WHAT IT DOES NOT ADD
        no authentication mechanism, no signature, no key, no credential path and no
          new admission check
        no claim that any record, producer claim or submitter is trusted
        no private key material anywhere: the configuration carries PUBLIC keys, and
          the deployment cannot mint what it verifies
        no change to what AI-05 admits or rejects, and no runtime behaviour at all —
          this amendment is documentation
        no new authority and no new trust domain that overlaps AI-13's
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves any responsibility into AI-05. Guard
    remains the only component with an AUTHORIZES entry. An authenticated producer
    claim is not an approval, a permission, a capability or a Guard result (§7.3.8),
    and a valid configuration grants nothing to anyone. No producer token, registry
    row or §6.5 constraint is added, removed or relaxed.
```

```text
CONTRACT IMPACT
    ADDED        §7.3.11 (new), §31.3 (new), this amendment record
    AMENDED      §30 step 7b — a cross-reference to §7.3.11 and the failure code,
                 added to the existing step; no step added, removed or reordered
                 §35.3 and `## Status` — corrected present-tense status claims, with
                 the freeze-time values kept and labelled
    UNCHANGED    §6.5, §6.6, §7.1, §7.2, §7.3.1-§7.3.10, §8-§29, §30's other steps,
                 §31's existing rows and notes, §32, §33, §34.1, §34.2, §35.1, §35.2
    NO CHANGE TO the record schema, the canonical collections, the digest inputs, the
                 stored form, the outcome vocabulary, the registry, the reason-code
                 set, or any authority relation
```

**AI-05 remains INCOMPLETE.** This amendment specifies a mechanism and does not
implement it. It closes nothing: not AI-11 §21.1's OPEN-1, not AI15-OPEN-1, not
AI15-OPEN-3, not AI15-OPEN-4, and not §35.1's deferrals. No test named in §7.3.7 has
been run, and no production Evidence writer is authorized.

---

#### Amendment 7 — producer authentication is implemented, and its owner closes AI15-OPEN-1 (2026-10-11)

Found while performing the post-merge closeout of the change that implements §30
step 7b. Amendments 5 and 6 supplied a mechanism — a standard and then its trust
configuration — and **both recorded, in their own words, that nothing performed the
step**. That change has merged. This amendment records what it delivered, the
evidence that it runs, and the owner's conclusion on the item AI-15 holds as
**AI15-OPEN-1**. It is authored on a docs-only branch based on main
`d09ce69ec1c0975c6d638d7861df2f11c44ec1d1`.

**Why this is an amendment rather than a clarification made in place.** This
amendment changes **no clause** of §7.3, §7.3.7, §7.3.11, §30 or §31. It adds no
outcome, no reason code, no registry row, no producer token, no digest input, no
stored field and no authority relation — none of §34.1's enumerated triggers is
touched. What it does is correct the contract's **current-status records**, which
§35.3 and `## Status` are, and §34's preamble requires that be done through an
explicit amendment recorded here rather than by editing a frozen clause in place.
The status of an implemented mechanism is a recorded fact, and a recorded fact that
stops being true "is corrected by updating the record, never by arguing with it"
(AI-14 §2, quoted in §35.3).

```text
(a) WHY §30 STEP 7b STOOD AT "NOT IMPLEMENTED" UNTIL THIS CHANGE MERGED

    THE STEP WAS DEFINED BY AMENDMENT 5 AND ITS CONFIGURATION WAS FROZEN BY
    AMENDMENT 6, AND BOTH ARE DOCUMENTATION CHANGES.

        Amendment 5   §7.3 and §30 step 7b — DEFINES what makes a producer claim
                      authenticated. Merged as
                      7017bf577f654cb6dea0e8d5e50a27f334117b73 (PR #83).
        Amendment 6   §7.3.11 and §31.3 — NAMES the one source, the ONE READER, the
                      process-lifetime lifecycle and the static enforcement the
                      reader requires. Merged as
                      cee1f8c9ae07837e0ebae0be3f8ab2e0113e6973 (PR #85).

    Neither wrote any code, and both said so in their own records. Amendment 6's
    log states that it "does NOT write plugins/evidence/producer_auth.py" and "does
    NOT change scripts/ci/layer0_policy.py". A contract can REQUIRE a property, and
    REQUIRING IT IS NOT HAVING IT (§7.3.11, in those words).

    SO THE STATUS COULD NOT MOVE BY DOCUMENTATION. §7.3.11 imposes FOUR obligations
    on the change that implements it, and EVERY ONE OF THEM IS A CODE ACT:

        the reader module          plugins/evidence/producer_auth.py must EXIST
        the startup edge           plugins/evidence/__init__.py must IMPORT it, so
                                   that no lazy path, first-call initialization or
                                   admission-time read can exist
        the Layer 0 enforcement    §31.3's four rules must be CHECKED by
                                   scripts/ci/layer0_policy.py, not merely stated
        the acceptance tests       §7.3.7's obligations must RUN, through the real
                                   verification path, under the SAME configuration
                                   mechanism a deployment uses

    AND THE CHANGE COULD NOT BE SPLIT INTO SMALLER ONES THAT MOVED THE STATUS
    PARTIALLY. §7.3.11 makes the read a module-INITIALIZATION act, so a reader
    without the package's import edge would not have the ordering that section
    requires; §31.3 makes Layer 0 the enforcement of §7.3.11's rules, so an
    implementation without it would be unenforced in the one place the contract
    names; and §7.3.11 makes the acceptance tests supply their configuration
    through the deployment mechanism, so tests without the launcher would be a
    bypass §31.3 forbids. Delivering step 7b meant delivering all four together,
    and UNTIL THAT LANDED THE HONEST STATUS WAS THE ONE §35.3 CARRIED: §7.3 DEFINES
    the standard, §7.3.11 fixes its configuration, and NO CODE PERFORMS IT.

    ONE FURTHER CONSTRAINT SHAPED THE CHANGE AND IS RECORDED BECAUSE IT IS EASY TO
    MISREAD AS AN OMISSION. AI-15 §17.2b forbids creating a production, non-test
    call site that can execute admission and persist a record while AI15-OPEN-1 is
    open. The implementing change therefore had to deliver step 7b WITHOUT creating
    a caller, and it did: the only call site of `admit()` in the repository is
    `admit_to_store()`'s own, and no production component reaches either.
```

```text
(b) WHAT THE CHANGE DELIVERED

    PR #87, "feat(ai05): authenticate producer claims before evidence construction",
    https://github.com/Li20771/AI-Security-Research-Workbench/pull/87

    THE IMPLEMENTATION

        plugins/evidence/producer_auth.py     NEW — §7.3.11's ONE READER.
            `_ENV_NAME` is the only occurrence of the variable's name outside the
            test launcher, and the read is a MODULE-LEVEL ACT: `_SUPPLIED_VALUE =
            os.environ.get(_ENV_NAME)` followed by `_STATE = _build_state(...)`.
            THERE IS NO FUNCTION THAT READS THE VARIABLE, which is what makes a
            second read unrepresentable rather than merely forbidden.
            The state has §7.3.11's two shapes and both are final: `_Designated`
            (frozen, slotted, keys behind a read-only mapping view) and `_Invalid`
            (a singleton). INITIALIZATION DOES NOT RAISE — an invalid configuration
            is a state the process holds, so a deployment misconfiguration arrives
            as the REJECTED outcome §7.3.8 defines rather than as an ImportError.
            Validation is whole-mapping: duplicate object keys are refused at every
            level, `NaN`/`Infinity`/`-Infinity` are refused, and every refusal path
            returns the same `_Invalid` — there is no partial acceptance.
            `authenticate()` runs §7.3.5 V1-V5 in order, and V2 reads the claimed
            producer token BEFORE V3 so that no key lookup and no cryptography
            proceed without a readable token.
            `designated_key_for()` answers a PER-TOKEN question and exposes neither
            the mapping, the policy table nor the parsed document.

        plugins/evidence/signed_input.py      NEW — §7.3.4's signed input, produced
            by the AI-05-CJ-1 serializer (§7.3.6) and by nothing else. §7.3.11
            forbids the configuration's JSON tolerance leaking into this path, and
            the two are separate functions over separate values.

        plugins/evidence/errors.py            +80 — the SIX §7.3.8 reason codes and
            no seventh: PROOF_MISSING, PROOF_MALFORMED, KEY_UNAVAILABLE,
            SIGNATURE_INVALID, INPUT_MISMATCH, INPUT_UNSERIALIZABLE. An unreadable
            producer token carries an EXISTING shape reason instead, as §7.3.5 V2
            and §7.3.8 require.

        plugins/evidence/admission.py         +29/-6 — §30 step 7b placed in the
            pipeline. `admit()` now composes, in this order:

                check_admission_rules(raw)        §30 step 7, over SUPPLIED values
                authenticate(raw, producer_proof) §30 step 7b  <- THE NEW STEP
                EvidenceRecord.from_mapping(raw)  construction: 1-4, 4b, 6, 8-11, 13
                check_workspace_agreement(record) §30 step 5's agreement half
                assign_digests(record)            §30 step 12

            AUTHENTICATION RUNS BEFORE ANY TYPED RECORD EXISTS AND BEFORE ANY
            EVIDENCE DIGEST IS DERIVED, which is exactly the position §7.3.7 fixes:
            no record, and therefore no Evidence digest, may be built from a claim
            that is not authenticated. `admit_to_store()` passes the proof THROUGH
            to `admit()` — ONE verification and one verdict, never two — and returns
            before touching the store on every non-ACCEPTED result.

        plugins/evidence/__init__.py          +14 — §7.3.11's STARTUP EDGE. The
            package imports `producer_auth`, so importing the package initializes
            the reader and any process able to call `admit()` or `admit_to_store()`
            has NECESSARILY already initialized it. The ordering guarantee is
            STRUCTURAL rather than a sequence someone must remember to observe.
            NO CALLER IS CREATED: the edge is between a module and the package that
            owns it, and AI-15 §17.2b is untouched by it.

    THE ENFORCEMENT

        scripts/ci/layer0_policy.py           +340 —
            `check_evidence_producer_authentication()`, registered in `main()` and
            reported as the Layer 0 check "evidence producer authentication
            boundary". It enforces, as §31.3 obliges:

                ONE READER              the variable's declared name is read FROM
                                        the reader module itself — so this file
                                        need not contain the literal — and is then
                                        searched repository-wide. Outside the
                                        reader it may appear ONLY in
                                        tests/evidence/trust_harness.py.
                NO MUTATION             an AST scan of the package for
                                        `os.environ[...] = ...`,
                                        `.setdefault`/`.pop`/`.update`/`.clear`,
                                        `os.putenv` and `os.unsetenv`; plus a
                                        repository-wide scan for
                                        `importlib.reload(producer_auth)` and for
                                        rebinding an attribute of `producer_auth`.
                IMMUTABLE STATE         no public function of the reader returns
                                        the captured state.
                NO CALLER-SELECTED      no public function of the reader accepts a
                  TRUST ROOT            parameter named as a key, mapping, anchor,
                                        verifier, configuration or path.
                plus the STARTUP EDGE   plugins/evidence/__init__.py must import
                                        producer_auth, or the check fails.

    THE ACCEPTANCE TESTS

        tests/evidence/test_producer_authentication.py   NEW — §7.3.7's obligations
            as an acceptance module: twenty-two obligation groups (01-22, several
            with lettered cases) plus the corrective-patch regressions. Tests use a
            DISTINCT KEYPAIR PER PRODUCER TOKEN, go through the REAL verification
            path, and are supplied through the SAME designated configuration
            mechanism a deployment uses — §7.3.7 forbids a test-only bypass and
            none is used.

        tests/evidence/trust_harness.py                  NEW — the child-process
            launcher. It is the one place outside the reader permitted to name the
            variable, and it supplies it to a SEPARATE process's environment BEFORE
            that process starts, which is what a deployment does; only the process
            boundary differs. §31.3's boundary is that it MUST NOT mutate the
            running test process's environment and MUST NOT inject a mapping, a key,
            a verifier or a parsed state into the reader.

    THE GATE

        .github/workflows/preflight.yml       +112/-1 — layer 1 now runs THROUGH the
            launcher, because the evidence tests call admission and the
            configuration must reach a process that has not started yet; and a new
            step runs the acceptance module as EIGHT separate launcher invocations,
            each its own process. Running it as one process would put one
            configuration's state behind another group's name and report a result
            for a configuration that was never in effect.
```

```text
(c) THE MERGE EVIDENCE

    PULL REQUEST   #87 — feat(ai05): authenticate producer claims before evidence
                   construction
                   head branch  feature/ai-05-producer-authentication
                   base         main
                   merged       2026-10-11T14:16:56Z
                   final head   fc6fa10fe998abd2792b0e651e210c4d6d27d2ea
                   merge commit d09ce69ec1c0975c6d638d7861df2f11c44ec1d1

    THE MERGE COMMIT IS A TRUE TWO-PARENT MERGE, and this is checked rather than
    assumed:
        parent 1  c4691153bc7cf7377dcea444e5ce37a95d8042f3   main before the merge
        parent 2  fc6fa10fe998abd2792b0e651e210c4d6d27d2ea   the pull request's head

    ACTIONS RUN #301   https://github.com/Li20771/AI-Security-Research-Workbench/actions/runs/38146118977
                   workflow     preflight
                   event        pull_request
                   head_sha     fc6fa10fe998abd2792b0e651e210c4d6d27d2ea
                                ^ THE RUN EXECUTED THE HEAD THIS RECORD NAMES. A
                                  run against any other revision would evidence
                                  nothing about this merge.
                   conclusion   success

    ITS TWO JOBS, BOTH `completed / success`:

        "Layer 0 — repository policy"                  job 114489720281
            The job log ends `Layer 0 = PASS (24 checks)`, and the checks include
            `ok  evidence producer authentication boundary`. THE FOUR RULES OF
            §31.3 ARE NOT MERELY IMPLEMENTED — THEY RUN, AND THEY PASSED.

        "Layers 1-3 — offline model and context layers"  job 114489720414
            Step "Layer 1 — producer authentication acceptance matrix
            (8 configurations)" — SUCCESS. This is the step §7.3.7's obligations
            execute in, and it is the one (d) counts.
```

```text
(d) WHAT CI RAN, AND THE COUNT §31.3 REQUIRES

    §31.3 FROZE A REPORTING RULE when it imposed this obligation, and it is the rule
    this record is written to: "WHAT A REPORT MUST CARRY, WHEN THE TIME COMES: the
    number of process-isolated cases that RAN, not the number that passed or the
    run's status. A count of skips is a count of NOT_RUN, and NOT_RUN != PASS."

    So the count comes first and the job status second.

    THE MATRIX STEP IS EIGHT LAUNCHER INVOCATIONS — eight `trust_harness.py`
    processes, each with its own pytest child and its own configuration — because
    §7.3.11 reads the configuration once per process and §31.3 makes that state
    final for the process's life. The run's own job log shows, in order:

        G1  regression                      34 cases   [100%]
        G2  absent                           2 cases   [100%]
        G3  no_entry_for_token               1 case    [100%]
        G4  collision_recognized             2 cases   [100%]
        G5  collision_mixed                  1 case    [100%]
        G6  collision_unregistered           3 cases   [100%]
        G7  collision_unregistered_b         2 cases   [100%]
        G8  distinct_control                 1 case    [100%]
        ----------------------------------------------------
        PROCESS-ISOLATED CASES THAT RAN              46
        OF WHICH SKIPPED                              0
        OF WHICH FAILED                               0

    ZERO OF THE EIGHT PROGRESS LINES CARRIES AN `s`, AN `F` OR AN `E`. That is the
    check the clause above exists to make a reader perform: a skip is visible in the
    same line as the count, and there is none. THE NUMBER THIS RECORD CARRIES IS
    THEREFORE 46 RAN AND 0 NOT_RUN — not "passed", and not "the step was green".

    THE STEP'S CONCLUSION IS `success`, THE JOB'S IS `success`, AND THE RUN'S IS
    `success`. THOSE ARE STATED AFTER THE COUNT BECAUSE THEY ARE THE WEAKER
    EVIDENCE: §31.3 records that this suite exits 0 when its cases pass AND when a
    case was skipped, so the exit status alone cannot distinguish the two.

    THE EIGHT CONFIGURATIONS COVER §7.3.7's LIST WITHOUT A GAP. Each named
    obligation has a group it runs in: 01, 09a-09d, 10, 11, 12a-12c, 13a-13b,
    14a-14c, 15a-15b, 16, 17a-17b, 18a-18b, 19, 20, 21 and 22a-22f in G1; 02a-02b in
    G2; 03 in G3; 04 and 07 in G4; 05 in G5; 06a, 06c and 07 in G6; 06b and 06c in
    G7; 08 in G8. G6 and G7 are §7.3.2's TWO POLICIES for the one case they differ
    on; both run `test_obligation_06c_reader_is_consistent`, their results are NEVER
    MERGED, and each is evidence only for its own configuration.
```

```text
(e) AI-15 §15.2 STEP 0b's THREE PARTS, COUNTED SEPARATELY

    AI-15 §15.2 states STEP 0b's OUTPUT as "a mechanism, PLUS its implementation and
    tests". THE THREE ARE STATED HERE AS THREE, because collapsing them into one
    word is the error both contracts warn against, and because a reader who reads
    one line must not be able to conclude that a definition was a delivery.

        MECHANISM                 SUPPLIED — DEFINED.
                                  AI-05 Amendment 5 (§7.3, §30 step 7b) DEFINES the
                                  standard; AI-05 Amendment 6 (§7.3.11, §31.3)
                                  FREEZES its configuration, its ONE READER, its
                                  lifecycle and the static enforcement it requires.
                                  AI-15 §15.2 already records these two as ONE
                                  part, counted ONCE, and this amendment does not
                                  re-count them.

        RUNTIME IMPLEMENTATION    SUPPLIED — IMPLEMENTED AND MERGED.
                                  PR #87, merge commit
                                  d09ce69ec1c0975c6d638d7861df2f11c44ec1d1.
                                  §30 step 7b is performed by
                                  plugins/evidence/producer_auth.py, called from
                                  `admission.admit()` BEFORE any typed record
                                  exists; §7.3.11's startup edge is in
                                  plugins/evidence/__init__.py; and §31.3's four
                                  rules are ENFORCED — not merely implemented — by
                                  `check_evidence_producer_authentication()` in
                                  scripts/ci/layer0_policy.py, which ran and passed
                                  in run #301.

        ACCEPTANCE TESTS          SUPPLIED — RUN. 46 CASES RAN, 0 SKIPPED.
                                  §7.3.7's obligations, executed in CI on the merged
                                  head, in the eight configurations (d) counts.
                                  The evidence is an EXECUTION of the real
                                  verification path under the deployment's own
                                  configuration mechanism, not a description of one.

    ALL THREE ARE NOW SUPPLIED, AND THEY ARE SUPPLIED BY THREE DIFFERENT KINDS OF
    ACT: one is a definition in this contract, one is a merge into `main`, and one
    is a counted CI execution against that merge's head. Each is cited above on its
    own evidence, and no one of them is offered as evidence for another.

    §7.3.7's OWN CLOSING LINE — "NO TEST IN THIS LIST HAS BEEN RUN" — was true when
    it was written and is FALSE NOW. IT IS KEPT WHERE IT IS, because it is
    Amendment 5's record of the position at Amendment 5's merge and §34.3 keeps
    such records as what they were. THE CORRECTED STATEMENT IS IN §35.3 AND
    `## Status`, WHICH ARE THIS CONTRACT'S CURRENT-STATUS RECORDS; §7.3.7's
    obligation LIST is untouched, and every obligation in it is now discharged by a
    case that ran.
```

```text
(f) AI15-OPEN-1 — THE OWNER'S CONCLUSION, RECORDED BY THE OWNER

    AI15-OPEN-1 is "how a producer claim is ESTABLISHED, as against merely
    well-formed" (AI-15 §9.2). ITS OWNER IS AI-05. AI-15 §16.1 records the only
    route by which an OPEN item leaves that list:

        "AI15-OPEN-2 left this list the only way an OPEN item may leave it — its
         OWNER closed it, in the owner's contract, under the owner's amendment
         rule."

    THIS IS THAT ACT, and it is made HERE, in AI-05's contract, under AI-05's
    amendment rule, rather than asserted anywhere else.

    AMENDMENT 5 ALREADY NAMED THE CLOSING EVIDENCE AND LEFT THE ACT OUTSTANDING:
    "Only AI-05, by implementing the mechanism and shipping the mandatory tests,
    supplies the evidence that closes it." Both halves now exist:

        IMPLEMENTATION   PR #87, merge commit d09ce69e…      -> (b) and (c)
        TESTS            46 process-isolated cases RAN, 0 skipped, run #301, head
                         fc6fa10f…                            -> (d)

    THE OWNER'S CONCLUSION, STATED ONCE:

        AI15-OPEN-1 IS RESOLVED. The question it names — how a producer claim is
        established to §7's standard — has been ANSWERED by the owner (Amendments 5
        and 6), IMPLEMENTED by the owner (PR #87), and SHOWN TO HOLD by tests the
        owner shipped and CI executed on the merged head (run #301). The owner
        closes it.

    WHAT THIS CONCLUSION IS NOT, AND WHAT IT DOES NOT REACH. Each of these is a
    thing the paragraph above could be misread as saying:

        IT IS NOT AI-15's RECORD. AI-15 is the custodian of the AI15-OPEN-N list,
        and it records STEP 0b as UNSATISFIED as of its Amendment 2. It will say
        otherwise only when AI-15 makes its own amendment under §19 — AI-15's act,
        on AI-15's contract, which is NOT made here. UNTIL THEN AI-15'S DOCUMENT
        SAYS WHAT IT SAYS, and a reader MUST NOT cite this record as AI-15's.

        IT IS NOT A STATEMENT ABOUT AI-11 §21.1's OPEN-1. WHICH PRODUCERS EXIST is
        a different question with the same owner (AI-15 §9.2). This change adds no
        §6.5 row and admits no event: the registry still holds EXACTLY SIX ROWS
        OVER FOUR TOKENS, and `plugins/evidence/models.py` is not touched by PR #87
        at all. Resolving either question does not resolve the other, and neither
        is presented here as resolving the other.

        IT CONNECTS NOTHING AND IT CLASSIFIES NOTHING CONNECTED. B5's remaining
        blockers, AI-14's STEP 1 and §8.3's other CONNECTED conditions are other
        owners' acts (AI-15 §16.2, §15.2). Satisfying a blocker is NOT satisfying
        the item — AI-15 §16.2 says so about row 0a in terms — and B5 remains
        BLOCKED.

        IT AUTHORIZES NO WRITER. Recording that a condition is satisfied is not
        creating the thing the condition gated. This amendment creates no call
        site, no seam, no composition edge and no production Evidence writer, and
        it does not lift AI-15 §17.2b — §17.2b is AI-15's clause, and whether its
        stated condition still obtains is AI-15's to record, not this document's.
        NO PRODUCTION COMPONENT GAINED A PATH TO ADMISSION IN THIS CHANGE: the only
        call site of `admit()` in the repository is `admit_to_store()`'s own.
```

```text
(g) WHAT THIS AMENDMENT DOES NOT DO, stated because each is a thing it could be
    read as doing:

    it does NOT change §7.3, §7.3.7, §7.3.11, §30 or §31. No clause of the standard,
      of its configuration, of the step, or of the test matrix is reworded, added to
      or weakened. The one new obligation-bearing text in this document is this
      record, and it records rather than legislates.
    it does NOT add a seventh reason code, an outcome member, a §6.5 row, a producer
      token, an Evidence kind, a family, a producer_type, an identity field, a
      canonical collection, a digest input or a stored field. The proof is still not
      stored and the stored form is unchanged.
    it does NOT authorize a production Evidence writer to be created, merged or run,
      and does NOT lift AI-15 §17.2b.
    it does NOT close AI-11 §21.1's OPEN-1, and does NOT add the §6.5 row that would.
    it does NOT close §35.1's deferrals — F-10's legacy evidence_ref rename, the
      storage-backend decision, or the record_digest physical round-trip. None is
      touched, and none becomes closable by this change.
    it does NOT close AI15-OPEN-3 or AI15-OPEN-4, which are not AI-05's.
    it does NOT mark AI-15-B complete, B5 CONNECTED, AI-14 STEP 1 made, or AI-05
      complete. It marks none of them.
    it does NOT claim the §7.3 standard makes a record PROVEN to have been produced
      by the component its token names. What it records is that the THREE conditions
      AI-15 §6.1 attaches to that description — defined, implemented, and shown to
      hold by tests — are now satisfied. §7.3.9's residual risks (process control,
      key custody, and the limit that this authenticates a KEY HOLDER and not a code
      component's execution identity) are unchanged and are not narrowed here.
    it does NOT repurpose AI-13's approval ingress, anchor or verification site, and
      creates no approval path. An authenticated producer claim remains not an
      approval, not a permission, not a capability and not a Guard result.
    it does NOT touch §32's exit gates, §33's non-goals, or any AI-00..AI-14
      contract. A later AI-15 amendment will record the upstream consequence of
      (f); it is AI-15's act and is not made, pre-empted or drafted here.
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves any responsibility into AI-05. Guard
    remains the only component with an AUTHORIZES entry. An authenticated producer
    claim is not an approval, a permission, a capability or a Guard result (§7.3.8),
    and the mechanism this record activates confers nothing on the producer, the
    submitter, the record or the deployment beyond the one thing §7.3.1 states: the
    claim is authenticated. No producer token, registry row or §6.5 constraint is
    added, removed or relaxed.
```

```text
CONTRACT IMPACT

    ADDED        this amendment record
    AMENDED      §35.3 — the current-state block now states what is true after the
                 merge, and the four-states paragraph is corrected to match; the
                 freeze-time record is kept and labelled as before
                 `## Status` — the AI-05-B line and the closing note
    UNCHANGED    §6.5, §6.6, §7.1, §7.2, §7.3 and every subsection of it including
                 §7.3.1-§7.3.11, §8-§29, §30 and every step in it including step 7b,
                 §31 and every row and note in it including §31.3, §32, §33, §34.1,
                 §34.2, §35.1, §35.2, and the Amendment 1-6 records
    KEPT AS WHAT §7.3's "IN FORCE" banner and §7.3.11's "THE CURRENT STATUS" block.
      THEY WERE  Both describe the position at the merges they belong to — Amendment
                 5's and Amendment 6's respectively — and both are left EXACTLY as
                 written. Neither is corrected in place: they are those amendments'
                 records of what was true then, and §35.3 is where this contract
                 states what is true now. A reader who finds the banner saying
                 "AI15-OPEN-1 remains OPEN" is reading a dated record, not a current
                 one, and the pointer to the current one is this block.
    NO CHANGE TO the record schema, the canonical collections, the digest inputs, the
                 stored form, the outcome vocabulary, the registry, the reason-code
                 set, the acceptance obligation list, or any authority relation
```

```text
STATUS DISCIPLINE — WHAT THIS AMENDMENT MOVES, AND WHAT IT DOES NOT. Stated as
explicit movements AND non-movements, because a reader reaching for a status line is
exactly the reader most likely to over-read it:

    MOVES

    AI15-OPEN-1             RESOLVED, AND CLOSED BY ITS OWNER. Answered (Amendments
                            5, 6), implemented (PR #87), and shown to hold by tests
                            that ran (run #301, 46 ran / 0 skipped). See (f).
    AI-15 §15.2 STEP 0b     ITS THREE PARTS ARE NOW SUPPLIED — mechanism, runtime
                            implementation, acceptance tests — stated separately in
                            (e). AI-15 owns the STATUS line that says so (§19
                            Amendment 2 wrote the current one) and this document
                            does not write it.
    §30 step 7b             IMPLEMENTED AND RUNNING. Not "defined"; not
                            "unreachable". `admit()` performs it before any typed
                            record exists.

    DOES NOT MOVE

    AI-05 as a whole        REMAINS INCOMPLETE. See the closing note below.
    AI-11 §21.1 OPEN-1      REMAINS OPEN. WHICH PRODUCERS EXIST. No registry row was
                            added, and none was authorized.
    §35.1's deferrals       REMAIN DEFERRED. F-10, the storage backend, and the
                            record_digest round-trip.
    production writer       NOT AUTHORIZED AND NOT CREATED. Unchanged from
                            Amendments 5 and 6.
    B5                      REMAINS BLOCKED and is NOT classified CONNECTED.
    AI-14 STEP 1            NOT AMENDED, NOT MADE, NOT PRE-EMPTED.
    AI15-OPEN-3,            REMAIN INDEPENDENT AND UNSOLVED. This amendment does not
      AI15-OPEN-4           touch DecisionRecord.evidence_ref (AI-04's) or a
                            workflow-driven step's routing input (AI-13/AI-14's).
```

**AI-05 remains INCOMPLETE.** This amendment records an implementation and does not
complete a phase. Producer authentication now exists, runs, and is enforced and
tested — and the registry it authenticates against still holds six rows over four
tokens, so no record from AI-08, AI-10, AI-11 or AI-13 can be admitted at all
(AI-11 §21.1 OPEN-1). §35.1's deferrals are untouched. No production writer exists,
no Evidence record has been written, and §32's exit gates are not reached. **AI-05
owns an implemented, enforced and tested producer-authentication mechanism, and it
is not a complete phase.**

---

#### Amendment 8 — a forwarder may transport a producer proof, and may do nothing else with it (2026-10-12)

Found while reconciling the AI-15-B producer-authentication freeze with §7.3. The
AI-15 contract fixes that a caller may submit a record it did not author (§7.2,
Reading A, Amendment 4; AI-15 §7.3's T2), and §7.3.3 requires that submission to
carry a producer proof — so SOMEONE other than the producer carries proof material
to an admission entry point. §7.3.10's composition clause, "does not mint, hold or
verify a proof", was written for the **trust** side of this mechanism and does not
answer whether that transport is permitted at all. This amendment answers it. It is
the AI-05 owner's act, in AI-05's contract, under AI-05's amendment rule (§34), and
it is recorded because AI-15's §9.4 and §10.2 depend on the answer.

**Why this is an amendment rather than a clarification made in place.** §34.1's list
of changes requiring an amendment enumerates evidence kind, canonical collection,
digest input, workspace rule, secret boundary, authority relation, identity field and
admission outcome. This amendment changes **none** of them. §34's preamble is broader
than its list, though — a frozen contract "changes only through an explicit amendment
recorded in §34.3" — and this amendment adds a NEW SUBSECTION to §7.3 that states
normative permissions and prohibitions. That is a change however it is described, so
the instrument is an amendment, recorded here. The fact that §7.3 is absent from
§34.1's enumeration is recorded rather than relied on, exactly as Amendments 4 and 5
recorded the same about §7 and §30.

```text
(a) NEW §7.3.12 states the transport boundary for a forwarder, and it is narrower than
    its headline:

    (i)   A FORWARDER MAY TRANSPORT A PRODUCER PROOF AS OPAQUE MATERIAL. A caller
          that is not the producer may present the producing component's proof to
          `admit()` or `admit_to_store()` and may carry it to the entry point
          without reading, parsing, validating or interpreting it.
    (ii)  "HOLD" IN §7.3.10 IS DISAMBIGUATED, AND §7.3.10 IS NOT WEAKENED. It means
          CUSTODY FOR DECIDING WHAT IS TRUSTED — reading the mapping, selecting a
          key, reaching a verdict. A forwarder does none of those, and every
          prohibition in §7.3.10 stands unchanged. §7.3.12 grants no permission to
          read, decide or verify anything.
    (iii) FOUR PROHIBITIONS, AND THEY ARE THE WHOLE OF THE RESTRICTION: a forwarder
          MUST NOT GENERATE a proof (minting needs the producer's private key, and
          §7.3.11 puts public key material only in the configuration), MUST NOT
          REPLACE one (V5 binds the bytes to the submitted mapping, V3 selects the
          key by the declared token, so a substitute does not verify), MUST NOT
          MUTATE one (§7.3.3's decoding is strict and canonical, so a re-encoding is
          refused as malformed rather than accepted as an alias), and MUST NOT CLAIM
          OWNERSHIP of the claim or claim to have authenticated it.
    (iv)  EVERY FAILURE TO PRESERVE IS A REFUSAL. Dropping the proof produces
          AUTHENTICATION_PROOF_MISSING; altering it produces PROOF_MALFORMED,
          SIGNATURE_INVALID or INPUT_MISMATCH; substituting another producer's
          produces SIGNATURE_INVALID. NO PATH converts a transport failure into an
          ACCEPTED (§7.3.8), which is why the permission is safe to grant.
    (v)   TRANSPORT GRANTS NOTHING. The forwarder acquires no authority, permission,
          capability or Guard result, and is not made a party to the mechanism.
```

```text
(b) WHAT IT DOES NOT CHANGE. §7.3.1-§7.3.11 are UNCHANGED except for a pointer note
    inside §7.3.10 that records the clarification and weakens nothing. §7.3.3's proof
    requirements, §7.3.5's five verification steps, §7.3.7's order, §7.3.8's failure
    semantics and reason codes, and §7.3.11's configuration are all untouched. No
    field, no token, no registry row, no outcome and no reason code is added.
    THE CALLER-SIDE OBLIGATIONS ARE NOT THIS CONTRACT'S. What a forwarding caller
    must DO with the proof — preserve its bytes, present it, never mint or repair one
    — is AI-15 §9.4 and §10.2, made by AI-15 under AI-15's amendment rule. This
    section fixes what MAY cross the boundary; those clauses fix what the crossing
    party MUST do.
```

```text
(c) WHY IT IS AI-05'S TO MAKE. The question turns on the meaning of a clause in
    §7.3.10, which is AI-05's text, and the permission it resolves is a permission
    against AI-05's own mechanism. AI-15 recorded the need and could not answer it:
    AI-15 §17.4 forbids AI-15 from editing this contract, and §9.5 keeps the trust
    question out of AI-15's hands. The boundary is drawn here, by the owner, before
    the dependent clause is relied on — which is what §19 of AI-15's contract
    requires of an amendment to an earlier phase.
```

```text
SECURITY IMPACT

    NARROW, AND IT IS A CLARIFICATION RATHER THAN A NEW CONTROL. It adds no runtime
    code, no key, no check and no trust root. What it does is state that a permission
    the mechanism ALREADY has by construction is a permission:

        it was never refused by any implemented check — `admit()` and
          `admit_to_store()` take a proof from whoever calls them and verify it
          against the mapping, without any notion of who is calling
        it was never exercised either: no production caller exists, so no forwarder
          has transported anything (no non-test call site; AI-15 §3)
        and it is bounded by refusals rather than by policy: each way of mishandling
          the material lands on an existing reason code (§7.3.5, §7.3.8)

    THE RESIDUAL IS THE ONE §7.3.1 ALREADY RECORDS, AND IT IS NOT WIDENED HERE. An
    authenticated claim establishes a KEY HOLDER; it does not establish which code
    ran, and it is not submitter identity. This amendment does not change that
    limit — it applies it: a forwarder that carries a proof has established nothing
    about itself, and no reader may conclude anything about it from the transport.
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves a responsibility between phases.
    Guard remains the only component with an AUTHORIZES entry. A forwarder that
    transports a proof is not thereby authorized to do anything, and an
    authenticated producer claim remains not an approval, not a permission, not a
    capability and not a Guard result (§7.3.8).
```

```text
CONTRACT IMPACT

    ADDED        §7.3.12 — the forwarder's transport boundary
                 this amendment record
    AMENDED      §7.3.10 — a pointer note recording the clarification of "hold";
                 no prohibition in it is weakened, widened or reworded
    UNCHANGED    §6.5, §6.6, §7.1, §7.2, §7.3 and every other subsection of it,
                 §8-§33, §34.1, §34.2, §35.1-§35.3, `## Status`, and the
                 Amendment 1-7 records
    NO CHANGE TO the record schema, the canonical collections, the digest inputs, the
                 stored form, the outcome vocabulary, the reason-code set, the
                 registry, the acceptance obligation list, or any authority relation
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not add, remove or change a producer token, a §6.5 registry row, an
      admission outcome, a reason code, a digest input or a stored field
    it does not authorize a production caller, a writer or a call site, and it does
      not move AI-15 §15.2's STEP 1, row 1′ or STEP 2
    it does not mark B5 CONNECTED, and it does not claim any part of AI-15 is done
    it does not weaken §7.3.10, §7.3.2's ONE READER rule, or the rule that no public
      AI-05 function accepts a caller-selected trust root
    it does not permit a forwarder to verify, to select a key, to read the
      designated mapping, or to reach a verdict
    it does not turn transport into submitter identity: the API still takes none
    it does not edit AI-15's contract or any other phase's. AI-15's §9.4 and §10.2
      are AI-15's act and are cited here, not authored
    it does not run any test, and it claims no test result of its own
```

---

#### Amendment 9 — the producer-acceptance obligation becomes an exact approved call-site set (2026-10-12)

Found while preparing the prerequisite contract and acceptance work for the
composition → Evidence edge. §7.3.7's obligation list carried **"the absence of a
production non-test writer"**, and that obligation cannot survive the change it was
written to gate: a connecting change that produced a writer would fail it, and a
connecting change that DELETED it to pass would be §34.2's forbidden case.

**Why this is an amendment rather than a clarification made in place.** §34.1's
list does not enumerate §7.3.7's obligation list or §7.3, and §34's preamble is
broader than its list: a frozen contract "changes only through an explicit
amendment recorded in §34.3". This amendment REPLACES an obligation and adds a NEW
SUBSECTION (§7.3.13) that defines a standard. That is a change however it is
described, so the instrument is an amendment — the same reasoning Amendments 4, 5
and 8 recorded about §7 and §30.

```text
(a) NEW §7.3.13 defines EXACT CALL-SITE AUTHORISATION: what an approval is over, the
    fields an approved entry carries, the failure-independence requirement, the
    scanner boundary, and the fail-closed rule for forms the scanner cannot resolve.

    IT IS AN APPROVAL OVER CALL SITES, NOT OVER COUNTS. An approval over the NUMBER
    of calls a scope makes is a DIFFERENT AND WEAKER standard, and MUST NOT be
    recorded, reported or relied on as exact call-site authorisation. The difference
    is exactly one case, and §7.3.13 names it: delete one approved call, add another
    in the same scope, leave the count unchanged.

    §7.3.7's obligation line is REPLACED by the exact approved call-site set. The
    baseline assertion (approved = empty, observed = empty) is the replaced
    obligation's meaning, preserved; the candidate assertion (observed == what the
    connecting change declares) is what the replacement adds.
```

```text
(b) THE ACCEPTANCE MODULE AND THE MATRIX. The call-site scanner this obligation
    used to carry matched a callee by NAME ONLY. It could neither name a call site
    individually nor see an aliased call, so neither half of §7.3.13 could be built
    on it. It is REPLACED by `tests/evidence/callsite_identity.py`, which:

        resolves aliases WITHIN THEIR OWN SCOPE — a local assignment in one
          function says nothing about a same-named local in another
        records a per-call identity: path, fully-qualified scope, canonical
          entry point, AST child-field/index path, canonical fingerprint (the
          subtree with location attributes excluded), enclosing statement kinds,
          and whether `producer_proof` is an EXPLICIT keyword
        reports the forms it cannot resolve as UNRESOLVED, which drive FAIL, and
          NEVER drops them
        states its blind spots, which is TRANSPARENCY and NOT an acceptance
          criterion

    THE POSITIVE CONTROL STAYS. `test_obligation_18b` is unchanged in purpose: a
    check that cannot find a call site proves nothing about there being none.

    THE FAILURE-INDEPENDENCE REQUIREMENT IS MET BY SEPARATE NODES, not by
    assertions folded into one. Six of the seven new nodes exist because a single
    node reporting "18a failed" cannot say WHICH condition broke, and a check that
    cannot distinguish them is one condition with several names. The nodes are:

        18a  the approved set is exact, over the real production tree
        18b  the positive control (unchanged in purpose)
        18c  a substitution with an UNCHANGED COUNT fails   <- the count-only case
        18d  two calls in one scope are two identities
        18e  aliases resolve to the CANONICAL entry point
        18f  an unapproved addition fails
        18g  unresolvable forms fail closed (getattr / partial / container)
        18h  `producer_proof` must be an EXPLICIT keyword; `**mapping` does not count
        18i  an unsupported ACQUISITION carried onto a name and then CALLED fails
             closed (five forms: getattr-acquired, partial-created, dynamic-import
             result, container callable, and an AMBIGUOUS local name)
        18j  a CHANGED CALLEE FORM is not the approved call site, at the same scope,
             the same AST path, the same arguments and the same canonical entry
             point
        18k  a module the scan cannot read or parse FAILS the scan

    ^ 18i, 18j AND 18k ANSWER REVIEW FINDINGS, AND EACH CLOSES A DIFFERENT HOLE.
    18i: checking only the immediately-invoked shape — `getattr(...)(...)`,
    `partial(...)()`, `container[...](...)` — sees an ordinary call to an unknown
    local and reports NOTHING. The acquisition is therefore carried FORWARD onto
    the name it binds, so the later call is the finding.
    18j: the fingerprint NORMALISED the callee into itself, which made a direct
    call and an alias call at the same AST path, with the same arguments, share one
    identity — while §7.3.13's own text claimed the fingerprint distinguished
    different call expressions. The callee is now its own identity field.
    18k: `scan_tree` skipped a file it could not parse and reported the rest as
    clean, which is a clean result for a tree that was never fully read.
```

```text
(c) THE COUNTS, AND THE HISTORICAL RECORDS THAT KEEP THEIRS.

    WHAT MOVED
        G1 matrix node ids                 34 -> 49   (+15)
        process-isolated matrix cases      46 -> 61   (+15)
        test functions in the module       45 -> 60   (+15)

    WHAT DID NOT MOVE, AND MUST NOT
        Amendment 7 (d), §35.3 and `## Status` record "46 RAN / 0 skipped" as the
        result of CI run #301. THAT IS A HISTORICAL RECORD OF AN EXECUTION, and
        §34.3 keeps such records as what they were. Rewriting those numbers would
        falsify history rather than correct it, so THEY ARE KEPT, and a pointer is
        added beside each one naming the current count.

    THE SEMANTICS OF THE RECORDED NUMBER ARE NOT WIDENED. "46 process-isolated
    cases that RAN" meant cases executed inside the isolated processes; it does not
    become a count of security requirements, and the current count is not a claim
    that anything was re-run.
```

```text
SECURITY IMPACT
    NARROW, AND THE DIRECTION IS TOWARD MORE DETECTION. The obligation is REPLACED
    BY A STRONGER ONE: "no writer exists" becomes "exactly the authorised writers
    exist", and the identity comparison catches a substitution that a count
    comparison passes. Each new node fails on its own case, so a future weakening
    of one condition cannot hide behind another's green result.
    THE BOUND IS STATED RATHER THAN OVERCLAIMED: static scanning cannot establish
    the absence of arbitrary Python dynamic behaviour, and the forms it cannot
    resolve FAIL rather than pass. Silence is never an answer.
AUTHORITY IMPACT
    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves a responsibility between phases.
    Guard remains the only component with an AUTHORIZES entry.
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not authorise a production caller, a writer or a call site. A set that
      is empty on this tree stays empty until a connecting change declares entries
      in it, and declaring them is that change's act
    it does not mark any seam CONNECTED, and it does not claim AI-15 §15.2 STEP 2
      or STEP 3 has begun
    it does not add, remove or change a producer token, a §6.5 registry row, an
      admission outcome, a reason code, a digest input or a stored field
    it does not close AI-11 §21.1's OPEN-1, which asks WHICH PRODUCERS EXIST and
      remains OPEN
    it does not resolve the storage backend. §35.1's storage-backend question and
      the record_digest round-trip obligation stay DEFERRED, and no production
      storage backend is chosen here
    it does not delete, weaken or re-scope any test. The only test it removes is
      the one whose assertion it replaces, and the replacement is strictly stronger
    it does not claim any test result of its own beyond what (b) records, and it
      does not re-run CI run #301 or restate its numbers as current
    it does not edit AI-14's, AI-15's or any other phase's contract
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

### 35.3 Not started, and not implemented — corrected by Amendments 6 and 7

```text
CORRECTED. This subsection previously read, in the PRESENT TENSE:

    AI-05-B   implementation               NOT STARTED
    plugins/evidence/                      README.md placeholder only
    any Evidence record                    none exists

TWO OF THE THREE LINES HAD STOPPED BEING TRUE. They are corrected here rather than
argued with (AI-14 §2: a recorded fact that stops being true "is corrected by
updating the record, never by arguing with it"). The third line is STILL TRUE, and
nothing in this correction claims otherwise.
```

```text
THE FREEZE-TIME RECORD, KEPT AS WHAT IT WAS
    main at freeze = b76dd681ee3f5422d87d0cae5e2a0a181353512d
    At that commit `plugins/evidence/` held a README placeholder and nothing else,
    and no Evidence record existed anywhere. That was the state this document froze,
    and the two lines above were true of it.
```

```text
WHAT IS TRUE NOW, STATED SO NO READER HAS TO RECONCILE TWO DOCUMENTS
    AI-05-B1              COMPLETE / MERGED   offline logical core
    AI-05-B2-P1           COMPLETE / MERGED   §18.1 workspace agreement
    AI-05-B2-P2           COMPLETE / MERGED   §17 stored-form round-trip
    AI-05-B2-P3           COMPLETE / MERGED   admission pipeline, filesystem Store,
                                               §31 Layer 0 evidence check
    plugins/evidence/     THIRTEEN MODULES    not a placeholder
    §30 steps 1-14        IMPLEMENTED         step 7 included, published by
                                               Amendment 3 (§14.10)
    §30 step 7b           IMPLEMENTED         performed by
                                               plugins/evidence/producer_auth.py,
                                               called from `admission.admit()`
                                               BEFORE any typed record exists
                                               (Amendment 7, PR #87)
    §7.3 acceptance tests RUN                 §7.3.7's obligations executed in CI on
                                               the merged head: 46 process-isolated
                                               cases RAN, 0 skipped (Amendment 7,
                                               run #301)
    a production writer   NONE                no non-test caller of `admit()` or
                                               `admit_to_store()` exists anywhere
    any Evidence record   none exists         `evidence/runs/` and `evidence/promoted/`
                                               hold no record, only `.gitkeep`
    AI15-OPEN-1           CLOSED BY ITS OWNER answered, implemented and shown to
                                               hold; closed in this contract under
                                               §34 (Amendment 7)
    Layer 0 enforcement   RUNNING AND PASSING §31.3's four rules are checked by
                                               `check_evidence_producer_authentication()`
                                               and passed in run #301
```

```text
FROZEN: THESE ARE FOUR DIFFERENT STATES AND MUST NOT BE COLLAPSED INTO ONE.
            the record model and the admission pipeline   BUILT
            the producer-authentication mechanism         BUILT (Amendment 7)
            a production writer / non-test caller         ABSENT
            a stored Evidence record                      NONE
        A reader who collapses them reports either more or less than is true. A
        contract that DEFINES a mechanism has not IMPLEMENTED it; and a package that
        implements every admission step except 7b is not "not started". Both errors
        are live ones — the first over-reports a control, the second hides work that
        has been done and reviewed.
        THE SECOND LINE READ "DEFINED, NOT BUILT" AND WAS TRUE UNTIL PR #87 MERGED.
        It is corrected here to BUILT, and correcting it SWAPS WHICH OF THE TWO
        ERRORS IS LIVE rather than retiring either: the mechanism is now the state
        that must not be UNDER-reported. IMPLEMENTING §30 step 7b did NOT build a
        production writer, DID NOT store a record and DID NOT admit a producer
        token, so the third and fourth lines are UNMOVED — and a reader who lets a
        built mechanism stand in for any of them has made exactly the first error
        this clause names.
FROZEN: THE CORRECTION DOES NOT WEAKEN AMENDMENT 5's RECORDED DIVERGENCE, and this
        is recorded rather than left to be re-derived. That record argued the
        divergence was consequence-free partly on the ground that "AI-05-B is NOT
        STARTED (§35.3)". Its OTHER TWO grounds are independent of that line and both
        still hold: NO CALLER — no production non-test caller of admission exists
        anywhere in the repository — and NO WRITER — AI-15 §17.2b forbids creating a
        production call site that can execute admission and persist a record while
        AI15-OPEN-1 is open. Step 7b is unimplemented AND unreachable, and it is the
        second fact that carries the argument. Correcting a citation does not move
        the conclusion it was cited for.

        ^ AMENDMENT 6's RECORD, KEPT AS WHAT IT WAS. ITS LAST SENTENCE IS NOW
        SUPERSEDED, and it is the only sentence in it that is. The divergence
        Amendment 5 recorded was that the implementation did not perform §30 step
        7b. PR #87 implements it, so THE DIVERGENCE IS CLOSED — not argued away and
        not narrowed: `admit()` performs step 7b on every submission, before any
        typed record exists.
        WHAT SURVIVES THE CLOSURE IS THE PART THAT WAS NEVER ABOUT THE DIVERGENCE.
        Amendment 5's other two grounds are unchanged, and they are still the reason
        no record is exposed to an unauthenticated claim:
            NO CALLER   still true, and deliberately so. PR #87 created no call
                        site: the only call site of `admit()` in the repository is
                        `admit_to_store()`'s own.
            NO WRITER   still true. No production call site that can execute
                        admission and persist a record exists anywhere. Whether
                        AI-15 §17.2b's prohibition continues to apply now that its
                        owner has closed AI15-OPEN-1 is AI-15's clause to read, and
                        THIS CONTRACT DOES NOT CONSTRUE IT — no writer is
                        authorized here either way.
        A CLOSED DIVERGENCE ALSO CLOSES THE DIVERGENCE'S OWN REASONING, and it is
        recorded here so that no reader re-derives a conclusion whose premise has
        gone.
```

---

## Status

```text
AI-05-A  = FROZEN          this document
AI-05-B  = PARTIAL         B1 and B2 are COMPLETE / MERGED; §30 steps 1-14 are
                           implemented, step 7b included; producer authentication
                           is ENFORCED by Layer 0 and TESTED in CI; and no
                           production caller or writer exists

main at freeze = b76dd681ee3f5422d87d0cae5e2a0a181353512d
main now       = d09ce69ec1c0975c6d638d7861df2f11c44ec1d1
                 the merge of PR #87, against which the producer-authentication
                 acceptance tests ran (Amendment 7)

AI15-OPEN-1    = CLOSED BY ITS OWNER   answered, implemented and shown to hold
                                       (Amendment 7)
```

```text
CORRECTED BY AMENDMENT 6. The line above replaced "AI-05-B = NOT STARTED" and the
line "Implementation = NOT STARTED", which were true when this document froze and
false from the moment B1 and B2 merged. The freeze-time value of `main` is kept
because it is the value this document froze at, and it is labelled as such rather
than presented as current.
```

```text
CORRECTED BY AMENDMENT 7. The AI-05-B line read "§30 step 7b is NOT implemented
and no production caller or writer exists". THE FIRST HALF OF THAT SENTENCE IS NO
LONGER TRUE and is corrected above; THE SECOND HALF STILL IS, and is kept in the
same sentence deliberately, so that the two are read together. A reader who takes
"step 7b is implemented" as "a writer exists" has read the correction backwards.

    WHY THE CORRECTION IS THIS SMALL. AI-05-B was PARTIAL before PR #87 and is
    PARTIAL after it. What changed is not the phase's status but one of the facts
    the status line enumerates — and the fact changed from NOT implemented to
    implemented, enforced and tested. A status word that had been accurate would
    have hidden the movement; a status word that overstated it would have claimed
    a phase that is not finished.

    WHAT MAKES IT LEGIBLE RATHER THAN MERELY SHORTER. The current facts are
    enumerated in §35.3, the evidence is in Amendment 7, and the freeze-time value
    of `main` is kept beside the current one so neither has to be inferred.
```

```text
AI-02 / AI-03 / AI-04  = UNCHANGED
SecurityLab            = UNCHANGED
Router (AI-07)         = DEFERRED / UNIMPLEMENTED
```

> **AI-05 is not complete.** This document freezes a contract, and the contract's
> producer-authentication mechanism is now BUILT: §7.3's standard is DEFINED
> (Amendment 5), its configuration is FROZEN (Amendment 6), and §30 step 7b is
> IMPLEMENTED, enforced by Layer 0 and tested in CI (Amendment 7, PR #87). **None
> of that completes the phase.** No production caller or writer exists, no Evidence
> record has been written, no §6.5 row has been added, and §35.1's deferrals are
> open — so no component has been authorized by any of this, there is no record
> for any of it to be said about, and `evidence/runs/` and `evidence/promoted/`
> still hold no record at all.
