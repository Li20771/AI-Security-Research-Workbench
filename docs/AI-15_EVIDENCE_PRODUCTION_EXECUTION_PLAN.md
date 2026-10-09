# AI-15 — Evidence Production / Composition Integration — Execution Plan

> Phase: AI-15 — Evidence Production / Composition Integration
> Sub-phase: AI-15-A — architecture / contract freeze
> Baseline: `main` @ `37f354cbb3c007f2d92021fa560a443a53591372`
> Status: **DRAFT / FREEZE PROPOSAL.** No runtime is implemented by this document,
> and none may be until this document is merged **and** the amendment
> prerequisites in §15 have landed.

---

## 0. The one idea — read this first

```text
An EvidenceRecord is written by a PRODUCER.
A producer is a NAMED, REGISTERED role — not a credential.

Today the registry has four names and six rows (AI-02, AI-03, AI-04, AI-06).
Three of those four phases CANNOT write a record, because their own contracts forbid it.
No fourth writer exists.

So before "composition -> Evidence" can be designed, one question has to be
answered that no contract answers today:

    when a component other than the named one submits the record,
    who is the producer?

AI-15-A does not answer it. It measures it, names the owners, and stops.
```

```text
FROZEN: AI-15-A is a documentation act. It implements nothing, adds no producer
        token, amends no earlier phase's contract, and connects no seam.
FROZEN: no clause below may be implemented while the item it depends on is OPEN
        or BLOCKED (§16). An implementation that "temporarily" bridges one is the
        defect this document exists to prevent.
```

---

## 1. Status / Scope

### 1.1 Why this phase exists

AI-14 left exactly one work item undone:

```text
docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md §22.1
    B5  composition -> Evidence                BLOCKED   NOT STARTED
```

and it left it undone for two reasons it stated together:

```text
docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md:1520-1530
    "AI-05 C-1 is still DEFERRED, no producer token exists, and `composition/`
     MUST NOT import `plugins.evidence` — the layer 0 check refuses it structurally"
```

The first half of that sentence has since lapsed: **C-1 was closed on 2026-10-04 by
AI-05 Amendment 3** (`docs/AI-05-C1_EVIDENCE_2026-10-04.md`; PR #75 @
`390faeefc1145838eb14f3f2d29319be6f38c901`). §30 step 7 is implemented and
`plugins/evidence/rules.py` exists.

The second half has not lapsed, and it is the larger one.

**AI-15 exists because "C-1 is closed" does not mean "B5 is unblocked", and no
document currently says what B5 would actually require.**

### 1.2 Scope — what AI-15 owns

```text
PROPOSED  the producer-ownership question, asked precisely and handed to its owners
PROPOSED  the CONNECTED definition for the composition -> Evidence edge (§8)
PROPOSED  the admission boundary AI-15-B would call, and what it must not do (§10)
PROPOSED  failure semantics for a production-side admission (§11)
PROPOSED  the workspace obligations a production writer inherits (§12)
PROPOSED  the authority rules, restated so a writer cannot acquire one (§13)
RECORDED  the current-state audit: contract / implementation / call site (§3, §20)
```

### 1.3 Scope — what AI-15 does NOT own

```text
OUT OF SCOPE  AI-05's §6.5 registry, §6.6 rules, §7 producer model, §30 contract
OUT OF SCOPE  AI-11 §21.1's OPEN-1 tension and its reconciliation
OUT OF SCOPE  AI-14's CONNECTED/SEAM classification of any edge other than B5
OUT OF SCOPE  any phase's own writer (§14, §15 — those are owner amendments)
OUT OF SCOPE  AI-12-C, the model-comparative prerequisite, live provider verification
OUT OF SCOPE  a record-level trust root, a signer, a registry service, a daemon
OUT OF SCOPE  cross-workspace aggregation, in any form
```

```text
FROZEN: AI-15 MUST NOT modify a frozen clause of AI-00 .. AI-14. Where this
        document and an earlier contract differ, the earlier contract governs and
        THIS DOCUMENT IS WRONG.
FROZEN: AI-15 creates no producer token, adds no row to AI-05's §6.5 registry,
        and declares no second Evidence vocabulary.
```

### 1.4 What this document is not

It is **not** a design for a new Evidence system. AI-05 owns Evidence. It is **not**
a plan to make the composition a producer. AI-14 §3 lists twelve components and the
composition is not one of them.

It is one thing: **the boundary conditions under which an existing, frozen Evidence
contract may acquire its first production writer — or an honest statement that it
may not yet.**

---

## 2. Evidence baseline and terminology

### 2.1 The four questions, kept apart

Every clause in this document is one of four kinds, and they are not
interchangeable. This is the discipline AI-15-A exists to enforce.

```text
CONTRACT        what a frozen document says
IMPLEMENTATION  what code exists
CALL SITE       who actually invokes it, outside tests
EVIDENCE        what has been observed and can be re-checked
```

```text
FROZEN: a claim of the form "composition -> Evidence exists" requires all four.
        "The contract permits it" is not "it exists". "A test calls it" is not
        "a production caller calls it". "The types line up" is not "it is wired".
FROZEN: where only some of the four hold, the document MUST state which, using
        §2.2's classification. A path MUST NOT be described as connected on a
        subset.
```

### 2.2 Classification vocabulary

**Inherited unchanged from AI-14 §2**, because a second vocabulary for the same
question would be the divergence this repository refuses everywhere else.

```text
CONNECTED                  production code on both sides of the boundary, with a
                           real call site outside tests
IMPLEMENTED BUT NOT        both sides exist; the only callers/implementors are
  CONNECTED                tests, or there are none at all
IMPLEMENTED                one side only, complete in itself
DECLARES ONLY              named in a contract or a docstring, no code
DEFERRED / BLOCKED         as §2.3 below
OUT OF SCOPE               refused by §1.3 and not planned
```

### 2.3 Status vocabulary

**Inherited unchanged from AI-14 §2.** These are four different things and MUST NOT
be used interchangeably.

```text
FROZEN      settled by this contract. AI-15-B MUST implement it. Changing it
            requires an amendment (§19).
PROPOSED    this contract's choice, made so AI-15-B does not have to choose while
            implementing. Normative for AI-15-B, and the class most likely to be
            amended.
RECORDED    a fact about the repository as it is. Not a requirement and not a
            proposal. A RECORDED fact that stops being true is corrected by
            updating the record, never by arguing with it.
OPEN        a question this contract does NOT answer. An OPEN item MUST NOT be
            closed by an implementation decision.
BLOCKED     cannot be done now, and the blocker is named.
DEFERRED    deliberately not done, with the reason recorded.
OUT OF SCOPE refused and not planned.
```

```text
FROZEN: OPEN != "a TODO for AI-15-B". An OPEN item has an OWNER, and the owner is
        not AI-15 unless this document says so.
FROZEN: BLOCKED != DEFERRED. A blocked item has a named blocker that could be
        removed by someone; a deferred item is a decision not to do it.
```

### 2.4 The Evidence terms this document uses, defined once

```text
admission        the §30 pipeline. plugins/evidence/admission.py:176 admit()
                 runs steps 1-13; :210 admit_to_store() additionally runs step 14
                 and persists. Both run step 7 (§14.10) since Amendment 3.
producer         §7: "the component that WROTE the EvidenceRecord. Always a
                 Workbench component. Never a human."
actor            §7: "the entity whose act the record is ABOUT."
producer token   the string in provenance.producer. §6.5 registers it, and
                 §6.6 refuses one that is not registered for this kind and family.
admitted event   one row of §6.5. Six rows in v1, from four tokens.
tier             §20. STAGED receives records and may be discarded; PROMOTED is
                 durable, read-only, and has no write at all.
promotion        §20.3: a HUMAN copies the bytes. It creates no new record, no new
                 evidence_id, and mutates nothing.
```

```text
FROZEN: this document defines no Evidence term of its own. Every one above is
        AI-05's, quoted or paraphrased, and AI-05 §34.1 governs a change to any.
```

---

## 3. Current-state evidence audit

Everything in this section is **RECORDED** and re-checkable at the stated
`path:line` on `main` @ `37f354c`.

### 3.1 Non-test imports of `plugins.evidence`

Search: every `*.py` under `plugins/`, `composition/`, `agents/`, `workflows/`,
`benchmarks/`, `review/`, `routing/`, `integrations/`, `providers/`, `tools/`,
`workspaces/`, `scripts/`, `config/`.

```text
RESULT
    plugins/evidence/*.py      the package's own eleven files (AI-05)
    plugins/security_tools/evidence.py:12
                               `from plugins.evidence import ExecutionPayload, ToolCall`

    that is the WHOLE non-test import surface of the package.
```

```text
RECORDED: `plugins/security_tools/evidence.py:12` imports two AI-05 PAYLOAD TYPES
          and nothing else. It does not import `admit`, `admit_to_store`,
          `EvidenceRecord`, the Store, or the registry.
RECORDED: the two functions it defines — `tool_call_for` (evidence.py:19) and
          `execution_payload_for` (evidence.py:40) — have NO production caller.
          Their only callers are `tests/security_tools/test_evidence_and_families.py`.
          They are re-exported at `plugins/security_tools/__init__.py:80`.
```

**Classification: IMPLEMENTED BUT NOT CONNECTED** — which is exactly what AI-14 §5.1
and Appendix A already record for the AI-06 -> AI-05 projection row.

### 3.2 Calls to the Evidence entry points

```text
NON-TEST
    plugins/evidence/admission.py:265   admit()          <- admit_to_store() calling it

    that is the ONLY non-test call of either entry point in the repository.

TEST ONLY
    tests/evidence/test_admission_pipeline.py:51,88
    tests/evidence/test_admission_rules.py:56,541
    tests/evidence/test_digests.py:123,148
    tests/evidence/test_store.py:495,499
    tests/evidence/test_stored_form.py:318,325
    tests/evidence/test_workspace_agreement.py:75
```

```text
RECORDED: there is no non-test caller of `admit()` outside the package.
RECORDED: there is no non-test caller of `admit_to_store()` at all — including
          inside the package. Its only callers are five test modules.
```

**Classification: IMPLEMENTED BUT NOT CONNECTED.**

### 3.3 `EvidenceRecord` construction

```text
NON-TEST
    plugins/evidence/stored.py:172      load_stored() rebuilding a record from the
                                        STORED FORM

TEST
    (none)
```

```text
RECORDED: exactly one non-test site constructs an `EvidenceRecord`, and it is the
          LOADER. It reads bytes that are already on disk and re-instantiates the
          record; it is not a write path and it is not reached from admission.
RECORDED: `admit()` does not construct one at a line of its own — construction
          happens inside `EvidenceRecord.from_mapping` (plugins/evidence/models.py,
          called at admission.py:200).

CONCLUSION: there is NO production construction of a record FOR WRITING, anywhere.
```

### 3.4 The Layer 0 structural blocks

Every component that could plausibly write a record is refused **structurally**, by
an import rule, not by convention.

```text
COMPONENT            ENFORCEMENT                                  FILE:LINE
composition/         AI14_FORBIDDEN_IMPORTS = ("plugins.evidence",)
                                                                  scripts/ci/layer0_policy.py:3241
                                                                  checked at :3351
agents/              AGENTS_FORBIDDEN_IMPORTS check, explicit
                                                                  scripts/ci/layer0_policy.py:1549
review/              AI10_ALLOWED_PLUGIN_IMPORTS is an ALLOWLIST
                     ("plugins.security_tools", "plugins.context")
                     plugins.evidence is unreachable by omission :1833
benchmarks/          explicit check, "AI-11 v1 writes no AI-05
                     EvidenceRecord (contract 21.1)"             :2465-2468
workflows/           AI13_FORBIDDEN_IMPORT_ROOTS includes
                     "plugins"  (comment: "guard (AI-04),
                     evidence (AI-05), security_tools (AI-06)")   :2630
plugins/security_tools/  NOT blocked — the projection is a
                     FROZEN AI-06 contract clause (§15.1/§15.2)    (no rule)
```

```text
RECORDED: `composition/` is also refused by a SECOND, independent check —
          tests/composition/test_composition_boundaries.py:151-176,
          `test_the_composition_reaches_no_evidence_writer`, which walks the AST
          and asserts no `plugins.evidence` import AND no call named `admit` or
          `admit_to_store`.
RECORDED: a third check asserts the composition does not even NAME the concept —
          tests/composition/test_composition_boundaries.py:178-191 forbids the
          identifiers `producer_token`, `ADMITTED_EVENTS`, `Ed25519PrivateKey`,
          `ApprovalRef`, `ApprovalStatus`, `ALLOWED` in `composition/*.py`.
RECORDED: the single block is proven NON-VACUOUS at
          tests/composition/test_composition_layer0.py:98-101,
          `test_the_check_catches_an_evidence_import`, which injects
          `from plugins.evidence import admit` and asserts the check reports it.
```

```text
FROZEN: connecting the composition -> Evidence edge requires changing, in the SAME
        change, EACH of:
            AI-14's contract §5.1 / §22.1 B5 / Appendix A  (an AI-14 amendment)
            scripts/ci/layer0_policy.py:3241               (the import constant)
            tests/composition/test_composition_boundaries.py:151, :178
        All three are owned by AI-14., not by AI-15 (§15).
```

### 3.5 The producer registry as it actually is

```text
plugins/evidence/models.py:125
    ADMITTED_EVENTS: tuple[AdmittedEvent, ...] = ( ... )

    a module-level TUPLE literal. Immutable. Six rows. Declared once.
```

| # | declared at | event | kind | family | producer | producer_type | actor.type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `models.py:126` | AI-03 context read | `OBSERVATION` | `SOURCE_READ` | `ai-03` | `service` | `service` |
| 2 | `models.py:130` | AI-02 provider probe | `OBSERVATION` | `PROVIDER_PROBE` | `ai-02` | `service` | `service` |
| 3 | `models.py:134` | AI-02 capability observation | `OBSERVATION` | `CAPABILITY_OBSERVATION` | `ai-02` | `service` | `service` |
| 4 | `models.py:139` | AI-04 Guard decision | `DECISION` | — | `ai-04` | `service` | `service` |
| 5 | `models.py:143` | AI-06 tool execution | `EXECUTION` | — | `ai-06` | `service` | `agent` |
| 6 | `models.py:147` | AI-06 test result | `EXECUTION` | — | `ai-06` | `service` | `service` |

```text
RECORDED: four distinct tokens — ai-02, ai-03, ai-04, ai-06. Six rows.
RECORDED: no token exists for any other phase. The tokens ai-05, ai-07, ai-08,
          ai-09, ai-10, ai-11, ai-12, ai-13, ai-14 and ai-15 appear NOWHERE in this
          repository as a producer token:
              non-test code: 0 occurrences for every one of the ten
              tests:         0 occurrences, except ai-07 — and that one is an
                             ABSENCE assertion (see the box below)
          (the only occurrences of "ai-06" outside the registry are
           scripts/ci/layer0_policy.py:1553, inside an AI-08 error MESSAGE string.)
RECORDED: `admitted_events_for(kind, family)` (models.py:154) is READ-ONLY. There is
          no registration function, no mutable registry, and no API that adds a row.
RECORDED: an EXISTING test already pins the producer set independently.
          tests/routing/test_router.py:760-765 — AI-07's own regression guard —
          asserts `"ai-07" not in producers` AND
          `producers == {"ai-03", "ai-02", "ai-04", "ai-06"}`.
          That is a second, test-enforced statement of the same four tokens, in a
          phase that does not own the registry, and AI-15 relies on it as
          corroboration rather than on this document's own scan alone.
```

```text
CORRECTION TO A PRIOR RECORD. AI-14 §5.1 and §22.1 B5 say "no producer token
exists". That is TRUE FOR THE PHASES B5 WOULD NEED and FALSE as a flat statement:
AI-02, AI-03, AI-04 and AI-06 each already hold an admitted row.

The precise statement is:
    four phases have a registered producer token and NO WRITER;
    every other phase has neither.

This distinction is load-bearing for §14 and is the reason AI-15-A does not accept
"wait for the producer-token amendment" as a complete answer.
```

### 3.6 The check the contributor audit ran

```text
RECORDED: the findings above were produced by an AST + text audit over the named
          roots, not by reading docstrings. Each claim in §3.1-§3.5 names a
          file:line a reviewer can open. The audit is reproducible and its
          negative results are stated as negatives, not omitted.
```

---

## 4. Producer ownership model

### 4.1 Six things that are not the same thing

AI-05's contract separates two of these and leaves four implicit. AI-15-A names all
six, because every spoofing argument in §9 turns on conflating two of them.

```text
1  COMPONENT IDENTITY    which frozen phase owns the act. AI-14 §3's twelve
                         components. A composition is NOT one of them (§3, §4).
2  PRODUCER IDENTITY     the token in provenance.producer. §6.5 registers it.
                         §7: "the component that WROTE the EvidenceRecord."
3  ACTOR IDENTITY        provenance.actor.id — the entity whose act is DESCRIBED.
                         §7, and AI-08 §13.2 already fixes its shape for a future
                         agent-execution record.
4  PRODUCER TYPE         ProducerType = agent | service | unknown.
                         AI-05 owns it (vocabulary.py). NOT an ActorType (§7.1).
5  EVENT KIND            EvidenceKind = OBSERVATION | DECISION | EXECUTION (§6).
                         Describes THE ACT, and is what selects the payload (§11).
6  EVENT FAMILY          ObservationFamily = SOURCE_READ | PROVIDER_PROBE |
                         CAPABILITY_OBSERVATION (§6.7). REQUIRED on an
                         OBSERVATION, absent from DECISION and EXECUTION.
```

```text
FROZEN: 1, 2, 3, 4, 5 and 6 are six questions. A value that answers one MUST NOT
        be read as an answer to another.
FROZEN: `actor.type` MUST NOT be read as `producer_type`, and neither MUST be read
        as an identity. `producer_type = service` distinguishes nothing: all six
        v1 rows register it (§6.5), which §6.6 makes mechanical.
FROZEN: an `AgentId` MUST NOT be read as a producer identity. AI-08 §10.1 states
        that `AgentResult` "has NO AI-05 producer field", and agents/result.py:214
        records it. An AgentId names the actor of a future EXECUTION record
        (AI-08 §13.2), never its producer.
```

### 4.2 What may not be the sole basis of a producer identity

```text
FROZEN: none of the following MAY be the sole basis on which a record's producer
        identity is accepted:
            a caller-supplied string
            a configuration value
            a Router selection, or a field derived from one
            an AgentId, or an agent_hint
            actor.type, or any other actor-side field
            a file path, a module name, or a package the caller happens to live in
            a test double, a fixture, or a Protocol implementation
FROZEN: this list is a RESTATEMENT of AI-05 §6.5/§6.6 and AI-07's and AI-08's own
        boundaries. AI-15 adds no seventh refusal and weakens none.
```

### 4.3 Is the producer claim enforced today?

**Yes, mechanically — against the registry. No, in any sense of authentication.**

```text
WHAT IS ENFORCED  plugins/evidence/models.py:173 check_cross_field, called from
                  `EvidenceRecord.from_mapping` at models.py:1586, i.e. INSIDE
                  `admit()`'s second step (admission.py:200).

  candidates = admitted_events_for(kind, family)                     models.py:154
      an empty result  -> CrossFieldViolation, "not representable in v1"

  g_registered(provenance.producer,
               frozenset(row.producer for row in candidates))        models.py:193
      a token not registered FOR THIS KIND AND FAMILY
          -> ProducerNotRegistered   (errors.py:203, "PRODUCER_NOT_REGISTERED")

  provenance.producer_type not in {row.producer_type ...}            models.py:199
          -> ProducerTypeNotAdmitted (errors.py:209)

  provenance.actor.type not in {row.actor_type ...}                  models.py:205
          -> ActorTypeNotAdmitted

  and at PARSE time, from `Provenance._validated_fields`             models.py:1198
      producer_type not a ProducerType member
          -> ProducerRoleViolation   (errors.py:93,  "PRODUCER_ROLE_VIOLATION")
```

```text
RECORDED: the token IS bound to (kind, family). `ai-04` is admissible only for a
          DECISION with no family; `ai-06` only for an EXECUTION; `ai-03` only for
          an OBSERVATION/SOURCE_READ. §6.6's rejected-by-construction list states
          the same thing from the other side, and the implementation matches it.
```

```text
RECORDED: NOTHING enforces WHO IS SUBMITTING.

  admit(raw: object, *, clock=None)                              admission.py:176
  admit_to_store(raw: object, *, store, clock=None)              admission.py:210

  Neither takes a caller identity, a caller handle, a module, a workspace-scoped
  capability, or a credential. `raw` is a mapping. The producer is a FIELD INSIDE
  IT. Nothing in the record carries who submitted it, and nothing in the pipeline
  compares one with the other.
```

```text
FROZEN: the producer token is a NAMESPACE CLAIM, not a CREDENTIAL.
FROZEN: AI-15-A does NOT fix this. Fixing it would require a trust root, and §1.3
        puts a new trust root out of scope. It is recorded as OPEN-1 in §9.2 and
        §16, with the consequence stated rather than hidden.
```

### 4.4 The consequence, stated plainly

Any module that can import `plugins.evidence` can today submit:

```python
{"kind": "DECISION", "schema_version": ...,
 "provenance": {"producer": "ai-04", "producer_type": "service", ...},
 "payload": {"decision": "ALLOW", ...}, ...}
```

and — if every field is otherwise well formed and the workspace agrees — receive
`ACCEPTED`.

```text
RECORDED: what that record then proves is that a record of that shape is
          well-formed for the AI-04 Guard-decision event. It does NOT prove that
          AI-04 produced it.
RECORDED: whether this matters today is answered by §3: nobody can reach the
          entry point anyway, because §3.4's structural blocks leave only
          plugins/evidence itself and AI-06's type-only projection.
          The gap is LATENT, not live. Stating it as latent is the point.
```

---

## 5. Producer registry / event mapping

### 5.1 Which phase owns which fact, and whether it may write it

This is the table AI-14 §22.1 B5 needs and does not have.

| fact | produced by (code) | registry row | owning phase's contract | may that phase write? |
| --- | --- | --- | --- | --- |
| provider probe | AI-02 invocation boundary | `ai-02` `OBSERVATION`/`PROVIDER_PROBE` | AI-02 | **not stated** |
| capability observation | AI-02 invocation boundary | `ai-02` `OBSERVATION`/`CAPABILITY_OBSERVATION` | AI-02 | **not stated** |
| context read | `plugins/context` `build_context` | `ai-03` `OBSERVATION`/`SOURCE_READ` | AI-03 | **not stated** |
| Guard decision | `plugins/guard/evaluator.py:579` `DecisionRecord` | `ai-04` `DECISION` | AI-04 | **not stated** |
| tool execution | `plugins/security_tools` `ToolResult` | `ai-06` `EXECUTION` actor `agent` | AI-06 §15.1 | **the CALLER submits** |
| test result | `plugins/security_tools` `ToolResult` | `ai-06` `EXECUTION` actor `service` | AI-06 §15.1 | **the CALLER submits** |
| agent execution | `agents/runtime.py` `AgentResult` | **NONE** | AI-08 §13.1 | **NO — FROZEN** |
| review finding | `review/comparison.py` | **NONE** | AI-10 §13.2 | **NO — FROZEN** |
| benchmark run | `benchmarks/run.py` `BenchmarkRun` | **NONE** | AI-11 §21.1 | **NO — FROZEN** |
| workflow run | `workflows/run.py` `RunRecord` | **NONE** | AI-13 §16 | **NO — FROZEN** |
| composed task | `composition/root.py` `WorkbenchRun` | **NONE** | AI-14 §4.2, §13 | **NO — and §3 makes it not a component** |

```text
RECORDED: the "not stated" column is not an oversight in this document. AI-02,
          AI-03 and AI-04 predate AI-14's integration question and their contracts
          do not address who submits a record under their own token. AI-15-A does
          NOT infer an answer from their silence.
```

### 5.2 The AI-06 case, which is the only one with a FROZEN submitter rule

```text
docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md §15.1 — FROZEN
    "AI-06 does not implement an evidence store, does not call admission, does not
     write a record, and does not define an Evidence schema. It produces a
     projection, and the caller submits it through AI-05's existing entry point."

§15.2 — FROZEN     one tool invocation -> one ToolResult -> one AI-05 ToolCall
docs/AI-06_...:145 "AI-06 registers no new Evidence event. AI-05 §6.5 already
                    carries both AI-06 rows."
```

```text
RECORDED: this is the ONLY frozen contract clause in the repository that names a
          submitter, and it names "the caller".
RECORDED: AI-06's registry rows exist and are not disputed by anyone.
RECORDED: `plugins/security_tools/evidence.py` implements exactly §15.2, and its
          docstring repeats the rule ("the caller submits it through AI-05's
          existing entry point").
```

### 5.3 The tension §5.2 creates, which AI-15-A does NOT resolve

```text
docs/AI-05_EVIDENCE_EXECUTION_PLAN.md §7 — FROZEN
    producer    the component that WROTE the EvidenceRecord.
    ...
    Guard decides.
      actor    = service
      producer = AI-04
```

```text
§7's worked example binds `producer` to the OWNING COMPONENT OF THE ACT.
§13.1 of AI-08 draws the strict conclusion from it:
    "`producer` names the component that WROTE the record, and that claim would be
     false [if AI-08 wrote under ai-06]."
```

So there are two readings of "wrote", and two frozen contracts point at different
ones:

```text
READING A — SUBMITTER MAY DIFFER FROM PRODUCER
    "wrote" means "authored the CLAIM". AI-06 authors the projection under §15.2;
    a caller submitting it is a courier, and the producer is AI-06.
    Consistent with:  AI-06 §15.1 ("the caller submits it")
                      §6.5/§6.6's mechanical checks (they never look at the caller)
    Not contradicted by: AI-08 §13.1 — AI-08 would be authoring a claim about
                      AI-06's act, which is what §13.1 refuses.

READING B — SUBMITTER IS THE PRODUCER
    "wrote" means "called admission / store.write". Then AI-06 §15.1's caller
    needs a registry row of its own, and no row admits "composition" or "ai-14".
    Consistent with:  §7's literal wording, and AI-08 §13.1's reasoning applied
                      to a courier.
    Consequence:      AI-06 §15.1 is unimplementable without an AI-05 amendment.
```

```text
OPEN-2  Which reading governs `producer` when the submitter is not the named
        component?

        OWNER            AI-05 (it owns §7, §6.5 and §6.6)
        AI-15 POSITION   AI-15 does NOT choose. It records that the question is
                         unanswered, that the two readings license different
                         implementations, and that AI-15-B MUST NOT start on the
                         AI-06 path until AI-05 answers.
        WHY IT MATTERS    READING A makes the AI-06 -> AI-05 projection the one
                         seam that could be connected WITHOUT a §6.5 amendment.
                         READING B makes it need one.
```

```text
FROZEN: AI-15 MUST NOT resolve OPEN-2 by implementing one reading.
FROZEN: AI-15 MUST NOT "test" OPEN-2 by writing the record either way. A test
        asserting an outcome would settle by convention what the contract has not
        settled.
```

---

## 6. Evidence production boundary

### 6.1 What promotion from run data to EvidenceRecord requires

```text
FROZEN: run data does NOT become Evidence by being produced, by being correct, by
        being observed, or by a model judging it true. It becomes Evidence by
        passing §30 admission under an ADMITTED producer, and by nothing else.
FROZEN: no component may introduce a promotion path of its own. This restates
        AI-08 §13.3 and AI-14 §4.2 rule 4, and AI-15 adds no path.
```

### 6.2 The forbidden chain, named

```text
"the model says this is a fact"
        -> EvidenceRecord
        -> permission

FORBIDDEN, at every step, and the step that makes it forbidden is the FIRST one.
A model output is not a producer, cannot hold a producer token, and is not one of
the twelve components of AI-14 §3. §10.3's rule (below) is the mechanical half.
```

### 6.3 What may and may not be a record's content

```text
FROZEN: raw tool output, raw model output, prompts, completions, credentials,
        secrets and repository content MUST NOT be admitted. A record carries
        REFERENCES; the bytes stay outside.
        SOURCES: AI-05 §5.2, §13.4, §13.8; AI-14 §14; AI-13 §7.2; AI-11 §18.2.
FROZEN: AI-05 never converts supplied content into an artifact (§13.8), and an
        undeclared raw-content field of any kind is REJECTED (§30).
FROZEN: SecretValue MUST NOT cross the boundary, and the §14.10 rule set is a
        DETECTOR, not a sanitizer — it refuses, and holds no replacement (§14.4.1).
```

### 6.4 Who produces, who authors, who submits, who admits

The four roles, kept apart, because §5.3 shows two of them are currently ambiguous.

```text
PRODUCES THE FACT    the owning component. AI-06 produces a ToolResult.
AUTHORS THE CLAIM    the component that shapes the record's content. AI-06's
                     projection (§15.2) is the shaping step.
SUBMITS              whoever calls admit()/admit_to_store(). Today: NOBODY (§3.2).
ADMITS               AI-05. It is the only thing that runs §30, and it is the only
                     thing that writes to a Store.
```

```text
FROZEN: ADMITS is AI-05's and MUST NOT be reimplemented. AI-06 §15.1 says so
        directly ("Reimplementing admission would duplicate AI-05's §30 pipeline
        and its uniqueness rule, both frozen and both tested there"), and AI-15
        inherits the rule.
FROZEN: a component that produces a fact MUST NOT thereby acquire the right to
        submit it. Production and submission are different acts and §5.1 shows
        four phases that hold one and not the other.
```

---

## 7. Composition -> Evidence topology

### 7.1 What the composition is, and what it is not

```text
docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md §3, §4
    composition/ is "the glue, not a component (§3) and not an authority (§4)".

composition/root.py:20-30
    "It is NOT a component (… twelve and this is not a thirteenth), it is NOT an
     authority (… matrix is unchanged by it), and it holds NO decision of its own."
```

```text
FROZEN: the composition is NOT a producer and MUST NOT become one. Registering an
        "ai-14" or "composition" producer token would make the glue a component,
        which contradicts AI-14 §3 — and AI-14 §24 makes "the component list or a
        component's responsibility" amendment-requiring.
FROZEN: AI-15-B MUST NOT propose, implement or imply an AI-14 producer token.
```

### 7.2 The three candidate topologies, with their blockers measured

```text
T1 — OWNER-PHASE WRITER
     each owning phase calls AI-05 itself.
     BLOCKED, per phase, by four separate things each:
         AI-08  §13.1 FROZEN "writes NO AI-05 EvidenceRecord of any kind"
                registry: no row
                layer0 :1549 refuses the import
         AI-10  §13.2 FROZEN "MUST NOT write an AI-05 EvidenceRecord, under any
                producer token"
                registry: no row
                layer0 :1833 allowlist excludes it
         AI-11  §21.1 FROZEN "writes NO AI-05 EvidenceRecord"
                registry: no row
                layer0 :2465 refuses the import
         AI-13  §16 FROZEN "writes none and registers no producer"
                registry: no row
                layer0 :2630 refuses every `plugins` root
     Cost: an AI-05 amendment AND an amendment to each phase AND a layer0
           narrowing, per phase. AI-15 owns none of them.

T2 — COMPOSITION AS SUBMITTER OF AN OWNER-AUTHORED RECORD
     the composition calls admission with a record the OWNING phase produced,
     under the token that phase holds.
     This is what AI-14 §22.1 B5 describes:
         "composition MAY call admission with a record the OWNING phase produced,
          under the producer token that phase holds"
     BLOCKED by:
         layer0 :3241  AI14_FORBIDDEN_IMPORTS — the composition may not import
                       plugins.evidence AT ALL
         test          tests/composition/test_composition_boundaries.py:151, :178
         contract      AI-14 §5.1 / Appendix A classify this row
                       "DOES NOT EXIST (by rule)"
         and, for every phase but AI-06, ALSO by T1's registry and contract rows.
     AND it inherits OPEN-2 (§5.3): whether a submitting composition authors a
     false producer claim by the standard AI-08 §13.1 applied to itself.
     THE ONE UNBLOCKED BYTE: AI-06's rows exist and AI-06 §15.1 already names a
     caller — UNDER READING A ONLY.

T3 — COMPOSITION AS A NEW PRODUCER
     REJECTED by §7.1. OUT OF SCOPE, permanently.
```

### 7.3 What AI-15-A concludes about the topology

```text
FROZEN: the ONLY topology consistent with the frozen contracts is T2, and only
        under READING A, and only for an event whose registry row already exists,
        and only after AI-14 amends §5.1 / §22.1 B5 / Appendix A and layer 0
        narrows :3241 in the same change.
FROZEN: T1 is not forbidden by AI-15 — it is the topology each phase's own
        contract would have to choose if it wanted its own writer — but AI-15 owns
        none of the five amendments it needs and MUST NOT assume it.
FROZEN: T3 is refused.
FROZEN: AI-15-B MUST NOT begin with T2's implementation. The AI-14 amendment in
        §15.2 is a PREREQUISITE, not a parallel workstream.
```

### 7.4 Who owns what, answered

```text
Q  who owns the run facts?
A  the producing component — see §5.1's table. The composition owns NONE of them:
   composition/root.py returns REFERENCES (`WorkbenchRun`, root.py:62-92) and the
   docstring at :20-30 says it holds no decision of its own.

Q  who produces raw / run data?
A  the frozen layers, at the entry points AI-14 §5.1 already names.

Q  who decides whether a fact is their own producer claim?
A  the phase that owns the fact. AI-15 does NOT assign this and §5.1 records four
   phases whose contracts have not answered it.

Q  who asks AI-05 for admission?
A  UNDETERMINED — this is the question §5.3's OPEN-2 and §7.2's three topologies
   exist to frame. Today the answer is "nobody" (§3.2).

Q  who holds an admitted producer token?
A  AI-02, AI-03, AI-04 and AI-06 have ROWS. No component holds anything, because
   a token is not a thing that is held (§4.3).

Q  who supplies workspace identity?
A  the record's `provenance.workspace_id`. Its only canonical derivation in the
   repository is plugins/context/workspace.py:174 `workspace_id_for(root,
   repository)` -> "ws-" + sha256(root \0 repository)[:16].

Q  who exposes the admission result to the caller?
A  UNDETERMINED. §11 fixes what MUST be observable; it does not fix the plumbing.
```

---

## 8. CONNECTED / SEAM definitions

### 8.1 The definition AI-14 §2 already froze

```text
FROZEN (inherited): a path is CONNECTED only when a NON-TEST call site exists. A
        Protocol with only test doubles behind it is IMPLEMENTED BUT NOT CONNECTED,
        however complete the types look.
        SOURCE: docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md §2.
FROZEN: AI-15 restates it and does not weaken it.
```

### 8.2 What specifically does NOT make B5 CONNECTED

```text
NOT SUFFICIENT, individually or together:
    `import plugins.evidence` appearing in composition/
    a helper function existing in composition/ that builds a mapping
    a test calling admit_to_store() successfully
    a Protocol with a test double behind it
    two packages being importable from each other
    the absence of an exception
    a document asserting a call site exists without naming it
```

### 8.3 The B5 CONNECTED definition — PROPOSED

B5 is CONNECTED when **all ten** hold, and each is checkable from the repository.

```text
 1  a NON-TEST module in a production package imports an AI-05 admission entry
    point and CALLS it
 2  the call site is named by file and line, in AI-14 §5.1 AND in this document's
    §20, in the same change that connects it
 3  the caller is identified, and it is the topology §7.3 selects — not a test
    helper, not a fixture, not a Protocol implementation
 4  the stored record's `payload` carries FACTS the owning phase produced, and the
    producing component is named
 5  `provenance.producer` is the token of the phase that owns the fact, and that
    token is registered in §6.5 FOR THAT KIND AND FAMILY
 6  `provenance.producer_type` is the producer_type that row registers, and
    `provenance.actor.type` the actor_type it registers
 7  `provenance.workspace_id` is the workspace the work was done in, derived from
    the same source the layers use (§12)
 8  the AdmissionOutcome is PROPAGATED to the caller as a value — never as an
    exception, never swallowed, never re-read as a success (§11)
 9  exactly one record is written per production event, into the STAGED tier, and
    §30 step 14 is run (`admit_to_store`, not a bare `store.write`)
10  the authority matrix is unchanged, and the change names what it did NOT prove:
    that an ACCEPTED is not an authorization, and that a stored record is not a
    grant (§13)
```

```text
PROPOSED: this list is AI-15-A's, and it is the class most likely to be amended.
FROZEN: items 1, 2, 5, 8 and 10 are NOT negotiable — they restate AI-14 §2,
        AI-05 §6.5/§6.6, and AI-14 §4.2 rules 4-6. Items 3, 4, 6, 7 and 9 are
        AI-15-A's framing of what those restatements require of a call site.
```

### 8.4 The intermediate states, so a partial result is not over-reported

```text
SEAM                    nothing on one side.
IMPLEMENTED BUT NOT     both sides exist; only tests, or nothing, call it.
  CONNECTED
CONNECTED               §8.3's ten conditions hold.
```

```text
FROZEN: AI-15-B MUST NOT report an intermediate state as CONNECTED, and MUST NOT
        report a state that satisfies items 1-9 but fails 10. Item 10 is the one a
        "successful" implementation is most likely to skip, and it is the one that
        keeps the Evidence layer from becoming an authority.
```

---

## 9. Provenance / trust boundary

### 9.1 What is frozen, and by whom

```text
FROZEN (AI-05 §7)      producer = the component that WROTE the record; never a human.
FROZEN (AI-05 §7.1)    producer_type is a ProducerType; `human` is REJECTED.
FROZEN (AI-05 §6.5)    the registry is keyed by admitted event and family, and "a
                       token registered for one event is not thereby valid for
                       another".
FROZEN (AI-05 §7)      "A record with no producer is not a record. Provenance is
                       never fabricated: a record claiming an observation that no
                       producer made would be a false record."
FROZEN (AI-08 §13.1)   "A false producer is exactly the class of claim this
                       repository refuses everywhere else."
```

```text
FROZEN: AI-15 restates these four and adds no fifth source of producer truth.
FROZEN: AI-15 introduces NO signer, NO signature, NO key, NO registry service, NO
        daemon, NO credential path and NO central authority. None exists in the
        repository for this purpose and AI-15 does not invent one.
```

### 9.2 Threat 1 — component A writes a record claiming to be component B

```text
STATUS TODAY: POSSIBLE IN PRINCIPLE, UNREACHABLE IN PRACTICE.

  in principle   admit() takes no submitter identity (§4.3). A module with import
                 access can submit producer="ai-04" with a well-formed DECISION.
  in practice    no module outside plugins/evidence/ and AI-06's type-only
                 projection can import the package at all (§3.1, §3.4).

OPEN-1  producer authenticity — how is a producer claim established, as against
        merely well-formed?

        OWNER            AI-05. It owns §6.5, §6.6 and §7. The question is a
                         question about AI-05's admission contract.
        BLOCKER          there is no trust root in this repository for it, and
                         AI-15 §1.3 puts creating one out of scope. A signature, a
                         key, a registry service or a capability handle would each
                         be a new authority, and AI-14 §4.1 freezes the matrix at
                         exactly one AUTHORIZES entry.
        WHAT AI-15 DOES NOT DO   it does not add a token, a check, a hook or a
                         "producer verification" seam.
        WHAT KEEPS IT FROM MATTERING TODAY  §3.4's structural blocks. Those are
                         the reason OPEN-1 is latent rather than live, and the
                         reason narrowing layer0 :3241 is not a local change.
```

### 9.3 Threat 2 — a caller fills in any producer token it likes

```text
STATUS TODAY: THE FIELD IS CALLER-SUPPLIED AND IS CHECKED ONLY FOR REGISTRATION.

  `provenance.producer` is a Class 3, G-REGISTERED leaf in §15.2's field table
  (plugins/evidence/canonical.py:104), validated by g_text at
  plugins/evidence/models.py:1211 and by the registry at models.py:193.
  It is caller-supplied, and §14.10's C1-R06 opaque-token rule scans it.

RECORDED: a value "looking right" is EXACTLY the condition that makes it pass.
          `ai-04` passes because it IS the registered token for a DECISION, not
          because anything verified who wrote it.
```

```text
FROZEN: AI-15-A states this rather than glossing it, because a later reader could
        otherwise take §6.5/§6.6's mechanical checks for an authenticity check.
        They are a REGISTRY check. §4.3 draws the line and §9.2 names the owner.
```

### 9.4 What a future writer MUST keep immutable when forwarding

```text
FROZEN: if a component ever submits a record it did not itself author, the
        following are IMMUTABLE across the forwarding boundary and MUST NOT be
        rewritten, defaulted, completed or repaired by the forwarder:
            provenance.producer           the authoring phase's token
            provenance.producer_type      that row's producer_type
            provenance.actor              that row's actor, exactly as authored
            the payload                   the authored payload, unmodified
            references[].workspace_id     the workspace each reference was read in
            the workspace_id              the workspace the fact belongs to
FROZEN: a forwarder MUST NOT substitute a default for any of these. §18.3's
        precedent is the reason: AI-04's contract said "never merged, filtered, or
        repaired" and the implementation filtered anyway, and an unconditional
        ALLOW rule then succeeded on a request spanning two workspaces. A
        repair-at-the-boundary is that defect with a different field.
FROZEN: a forwarder MUST NOT add a field. §30 step 1 rejects an unknown top-level
        field, on §4.2's precedent that "a field that is silently dropped cannot be
        audited".
```

```text
FROZEN: OPEN-2 (§5.3) must be answered BEFORE this clause can be implemented,
        because §9.4 presumes the forwarder is not the producer. Under READING B
        there is no legal forwarder at all, and this clause is inert.
```

---

## 10. Admission boundary

### 10.1 The entry points, as they are

```text
admit(raw: object, *, clock=None) -> AdmissionResult            admission.py:176
     step 7   check_admission_rules(raw)                        admission.py:199
     steps 1-4, 4b, 6, 8-13
              EvidenceRecord.from_mapping(raw, clock=clock)     admission.py:200
                -> which calls check_cross_field at models.py:1586 (§6.5/§6.6)
     step 5   check_workspace_agreement(record)                 admission.py:201
     step 12  assign_digests(record)                            admission.py:202
     stores NOTHING.

admit_to_store(raw: object, *, store, clock=None) -> AdmissionResult
                                                               admission.py:210
     admit(raw, clock=clock)                                    admission.py:265
     step 14  store.contains(record.evidence_id)                admission.py:271
              store.write(record)                               admission.py:276
```

```text
FROZEN: the recorded ORDER is §30's order except for step 7, which AI-05 §14.10
        moved before construction and recorded why (a digest must not be computed
        over a value that was not admitted — §14.6 R2). AI-15 does not reorder.
FROZEN: workspace agreement (§18.1, step 5) runs AFTER the §6.5/§6.6 producer
        checks, because those run inside `from_mapping` at admission.py:200.
        A record whose producer is unregistered is refused before its workspace is
        ever compared. Stated because §11's failure semantics depend on the order.
```

### 10.2 What a production caller would require

```text
FROZEN: a production caller MUST call `admit_to_store` and MUST NOT call
        `admit()` and then write the record itself. §30 step 14 is part of the
        admission contract, and skipping it is what AI-05 §20.3's promotion
        boundary and §8.2's uniqueness rule exist to prevent.
FROZEN: the store MUST be a StagedEvidenceStore. `admit_to_store` raises
        TypeError for anything without `write` (admission.py:256), and the
        docstring at :250 states the reason: without that refusal the function
        would itself be a programmatic promotion path.
FROZEN: the caller MUST NOT call `store.write` directly. It would bypass §30
        steps 1-13 entirely, and `StagedEvidenceStore.write` (store.py:270) is
        reachable — so this is a rule, not a structural block. It is stated as a
        rule and the reviewer is told it is one.
FROZEN: a production caller MUST NOT promote. §20.3 makes promotion a HUMAN act.
```

### 10.3 What a production caller MUST NOT do

```text
FROZEN: MUST NOT read ACCEPTED as an authorization. AI-05's own documents warn
        that an ACCEPTED is a statement about a RECORD (AI-14 §4.2 rule 4).
        NOTE: this warning predates Amendment 3 and read "is not a full §30
        admission" while C-1 was DEFERRED. C-1 is CLOSED, so a §30 admission is
        now complete — the AUTHORIZATION half is unchanged and is what matters
        here.
FROZEN: MUST NOT treat a stored record as evidence OF a capability, a permission,
        a verification or a model measurement.
FROZEN: MUST NOT retry a REJECTED admission with a repaired record. A rejection
        names a rule the record violated; repairing it changes what is being
        claimed, and a second submission is a second claim.
FROZEN: MUST NOT fall back to a different producer token when one is refused.
        §6.6 refuses by construction exactly this: "ai-02 used for a DECISION;
        ai-04 used for an OBSERVATION; ai-06 used for a DECISION; ai-03 used for
        an EXECUTION".
FROZEN: MUST NOT fall back to `admit()` when `admit_to_store` returns
        UNAVAILABLE, and MUST NOT report the run as evidenced when it did.
```

---

## 11. Failure semantics

### 11.1 AI-05's vocabulary, inherited and not re-invented

```text
AdmissionOutcome = ACCEPTED | REJECTED | UNAVAILABLE
    plugins/evidence/vocabulary.py; AI-14 §4.2 rule 4 records the three.
```

```text
FROZEN: AI-15 declares NO second outcome vocabulary. No `PARTIAL`, no `SKIPPED`,
        no `DEFERRED`, no `SOFT_FAIL`. A production caller maps AI-05's three
        outcomes and adds none.
FROZEN: AI-15 declares no second reason-code namespace. `reason_code` carries the
        EvidenceError's own (§22.1), never prose and never a supplied value.
```

### 11.2 Per-situation semantics

```text
REJECTED — the record violated a named rule; nothing was stored
    observed by     the submitting caller, as AdmissionResult(outcome=REJECTED,
                    reason_code=<the EvidenceError's reason_code>)
    persisted       NOTHING. §30: "Any failure produces REJECTED with a named
                    reason and stores nothing."
    caller sees     the outcome and the reason_code — never the offending value
                    (errors.py: an error message is a place a value escapes to a log)
    composition     surfaces it. MUST NOT retry with a repaired record (§10.3) and
                    MUST NOT try another token
    workflow        MUST NOT open a gate, close a step, or record the step as done
                    on account of it
    authority       NONE. Unchanged either way
    retry           NOT with a modified record. A second, differently-authored
                    claim is a NEW submission, not a retry

UNAVAILABLE — the record was valid and the write did not complete
    produced ONLY by  admit_to_store, and ONLY for an OSError during the write
                      (admission.py:282-284, reason_code "STORAGE_FAILURE")
    observed by     the submitting caller
    persisted       NOTHING stored; AND no record describing the failure is
                    written — "the failure belongs in the return value" (:234-235)
    caller sees     UNAVAILABLE + STORAGE_FAILURE
    composition     MUST NOT report the run as evidenced
    NOTE            this is the one outcome that is NOT the record's fault, and it
                    is therefore the one most likely to be papered over. §10.3's
                    last rule forbids it by name
    retry           a retry of the SAME record is permitted in principle — the
                    record was valid — but AI-15-B MUST NOT implement a retry
                    loop, a queue or a scheduler (§17)

DUPLICATE evidence_id
    REJECTED with DuplicateEvidenceId.reason_code (§30 step 14, admission.py:271)
    the EXISTING record is untouched. "this is a collision, not an overwrite"
    (store.py:309). A duplicate is a REJECTION, not an update

DUPLICATE content_digest
    NOT a conflict, and NOT a failure. §8.2: two records making the same claim are
    two events, they carry different evidence_ids and different record_digests, and
    BOTH are stored. AI-15-B MUST NOT add a content_digest uniqueness rule

MISSING / INVALID PRODUCER TOKEN
    REJECTED. ProducerNotRegistered (errors.py:203) for a token that is not the
    registered one for this kind and family; the kind/family itself may be
    unrepresentable, which is CrossFieldViolation instead
    NO FALLBACK. §10.3

WORKSPACE MISMATCH
    REJECTED with WorkspaceAgreementViolation (§18.1, admission.py:119-143).
    The record is rejected WHOLE — §18.3 forbids filtering.
    See §12

PRODUCER ROLE VIOLATION
    REJECTED at parse time — ProducerRoleViolation (errors.py:93) when
    producer_type is not a ProducerType member. A human producer is not
    representable (§7.1)

RUNTIME FAILURE IN THE CALLER, BEFORE ADMISSION
    nothing was submitted, nothing was stored. The caller's own phase owns the
    failure and reports it. AI-15-B MUST NOT convert a pre-admission failure into
    an UNAVAILABLE, because UNAVAILABLE has exactly one cause and widening it
    would make "the write failed" unreadable

A PROGRAMMING ERROR — store without `write`
    admission.py:256 raises TypeError. This is the ONE case where a caller sees an
    exception rather than a value, and it is deliberate: it is a misuse of the API,
    not an admission outcome (§22.1 defines three outcomes and an exception is not
    one of them)
```

### 11.3 The conversions that are forbidden

```text
exception       -> PASS                    FORBIDDEN
writer unavailable
                -> "not written" but the task reported as evidenced
                                           FORBIDDEN
producer missing -> a fallback producer    FORBIDDEN
admission REJECTED
                -> silently discarded, and success claimed
                                           FORBIDDEN
NOT_RUN / BLOCKED / UNKNOWN / UNAVAILABLE
                -> PASS                    FORBIDDEN
```

```text
FROZEN: these restate AI-14 §22.1's inherited rules and AI-05 §29's prohibition
        matrix, and AI-15 adds no sixth.
FROZEN: AI-15-B MUST NOT introduce an outcome that "succeeds with a warning".
        A warning is a PASS with less ink.
```

---

## 12. Workspace isolation

### 12.1 What is already frozen

```text
AI-05 §18.1        the agreement rule; §18.2 the outcomes; §18.3 why filtering is
                   separately named and forbidden
admission.py:106   check_workspace_agreement — the two comparisons the record can
                   express, and the five it cannot (admission.py:55-65)
AI-14 §6.2 FROZEN  EvidenceRecord "MUST NOT cross a workspace boundary in AI-14";
                   it is workspace-scoped by AI-05 §18.1
AI-14 §15          workspace isolation for the composition
```

### 12.2 The identity's single source

```text
plugins/context/workspace.py:174
    workspace_id_for(root, repository) -> "ws-" + sha256(root || \0 || repository)[:16]
    "Deterministic workspace identity (contract §6.2). Inputs are the canonical root
     and the repository identity and nothing else, so the id is stable across runs
     and across machines that see the same workspace."
```

```text
RECORDED: `EvidenceRecord.provenance.workspace_id` is a Class 3 leaf
          (canonical.py:109), scanned by the §14.10 rules, and compared against
          `references.context[].workspace_id` and
          `artifacts.items[].owner_workspace_id`.
RECORDED: `AgentResult.workspace_id` is documented as "empty exactly when the
          execution never reached a usable workspace" (agents/result.py:217).
```

```text
FROZEN: a forwarder MUST NOT derive a workspace identity of its own and MUST NOT
        substitute the caller's root for the fact's workspace. Deriving one would
        be a second source of the same identity, which is the defect AI-04 §28.2
        names.
FROZEN: `provenance.workspace_id` is REQUIRED, present and non-empty (§30 step 5).
        An AgentResult with an empty `workspace_id` therefore CANNOT produce an
        admissible record, and that is FAIL-CLOSED AND CORRECT. AI-15-B MUST NOT
        substitute a placeholder, a default, or the caller's workspace to make it
        admissible.
```

### 12.3 The three rules this phase freezes

```text
FROZEN: an EvidenceRecord remains WORKSPACE-SCOPED. AI-15 adds no scope, no
        multi-workspace record, and no scope field.
FROZEN: the composition does NOT aggregate across workspaces, and MUST NOT become
        a cross-workspace bridge. AI-14 §6.2 forbids the crossing and AI-14 §15
        forbids the aggregation; AI-15 restates both.
FROZEN: a record describing a fact in workspace A MUST NOT be submitted, admitted,
        presented or forwarded as a workspace-B record. §18.1's comparison is the
        enforcement, and §18.3 makes the outcome REJECTION, never repair.
```

```text
FROZEN: AI-15-B MUST NOT add a cross-workspace path, an aggregate view, a
        multi-workspace store, or a record-merge. Each is OUT OF SCOPE (§16).
```

---

## 13. Authority matrix / non-authority rules

### 13.1 The matrix is AI-14's and AI-15 does not touch it

```text
docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md §4.1 — FROZEN
    "the matrix has exactly ONE authorizing column entry — Guard."

                    SELECTS   AUTHORIZES   RECORDS              EXECUTES
Evidence            no        no           YES — durable        no
  (AI-05)                                   admitted facts
```

```text
FROZEN: AI-15 adds NO column, NO row, and NO entry. Guard remains the only
        authorizing component.
```

### 13.2 The rules this phase restates

```text
FROZEN: Evidence admission != authorization.                (AI-14 §4.2 rule 4)
FROZEN: An EvidenceRecord != a permission.                  (AI-14 §4.2 rule 4)
FROZEN: A producer token != an authorization. §6.5 registers a NAME; it grants
        nothing. A token is not a capability and not a credential (§4.3).
FROZEN: A producer identity != a Guard identity. §4.1's six-way split; an
        ALLOW is issued by Guard for ONE invocation and no producer field is or
        becomes an input to it.
FROZEN: the composition != an authority.                    (AI-14 §4)
FROZEN: workflow state != Evidence authority. A RunRecord, a Checkpoint and a
        WorkflowApproval are AI-13 types; none is a producer and none is a
        submission. AI-14 §4.2 rule 7 and AI-13 §13.5.
FROZEN: a benchmark result != durable truth, and != a permission.
        AI-14 §4.2 rule 5; AI-11 §8.5, §23.
FROZEN: a review finding != durable truth, and != a permission.
        AI-14 §4.2 rule 6; AI-10 §13.2.
```

### 13.3 The specific non-consequences AI-15-B MUST prove

```text
FROZEN: an ACCEPTED admission MUST NOT lead to, and MUST NOT be used to argue for:
            a Guard ALLOW
            a capability promotion (CapabilityStatus has no AVAILABLE member —
              AI-14 §4.2 rule 10)
            a model selection
            a workflow approval, or a workflow gate opening
            a review decision
            a benchmark verdict
            a second Agent's execution
            a permission of any other kind
FROZEN: AI-15-B MUST prove these remain true AFTER its change, in the same change,
        or the change is not done. An authority transfer that arrives as a
        side-effect of wiring is exactly what AI-14 §4.2 rule 4 and AI-14 §22.1's
        ten rules exist to prevent.
```

### 13.4 The residual, stated rather than hidden

```text
RECORDED: the field `evidence_ref` exists in three unrelated vocabularies and NOT
          ONE of them is an AI-05 `evidence_id`:
              plugins/guard/models.py:513        DecisionRecord.evidence_ref
              providers/model_profile.py         Provenance.evidence_ref
              review/claim.py:152                Claim.evidence_refs
          AI-05's own ids are `ev-…` (models.py:95 EVIDENCE_ID_PREFIX).
RECORDED: `DecisionRecord.evidence_ref` is NEVER populated in production —
          plugins/guard/evaluator.py:579 constructs the record and does not pass it,
          so it is `None`, and no non-test site assigns it.
```

```text
FROZEN: AI-15-B MUST NOT treat any of the three as an Evidence identity, and MUST
        NOT populate `DecisionRecord.evidence_ref` as part of this phase.
        AI-04's own contract governs that field, and AI-15 owns no AI-04 clause.
OPEN-3  whether `DecisionRecord.evidence_ref` should ever carry an AI-05 id.
        OWNER: AI-04. Not AI-15, and not AI-15-B.
```

---

## 14. Cross-phase dependency audit

Legend: **contract** = what is frozen · **code** = what exists · **call site** = a
non-test caller · **evidence** = re-checkable observation.

### 14.1 Summary table

| phase | contract says | code exists | non-test call site | evidence proves CONNECTED | AI-15 depends on an amendment? |
| --- | --- | --- | --- | --- | --- |
| AI-05 | owns Evidence; §6.5 6 rows/4 tokens | yes, complete | **no external caller** | **no** | no — but §9.2 OPEN-1 is AI-05's |
| AI-06 | §15.1 projects, caller submits | `evidence.py` | **no** | **no** | **UNDETERMINED — hinges on §5.3 OPEN-2** |
| AI-08 | §13.1 writes NO record | n/a | n/a | no | no (AI-15 does not restate AI-08's job) |
| AI-10 | §13.2 writes NO record | n/a | n/a | no | no |
| AI-11 | §21.1 writes NO record; OPEN-1 | n/a | n/a | no | **OPEN-1 is AI-05's, not AI-11's** |
| AI-13 | §16 writes none, registers no producer | n/a | n/a | no | no |
| AI-14 | §22.1 B5 BLOCKED; §5.1 not connected | `composition/` | **no** | **no** | **YES — §15.2** |

### 14.2 AI-05

```text
contract   the Evidence authority. §6.5 six rows / four tokens; §6.6 cross-field;
           §7 producer/actor; §14 secret boundary; §15.2 field table; §18.1
           workspace agreement; §30 admission; §14.10 published rule set
           (Amendment 3); §20 staged vs promoted; §34 amendment rule.
code       complete and merged. `rules.py` exists; §30 step 7 runs inside both
           entry points.
call site  NONE outside the package (§3.1, §3.2).
evidence   an ACCEPTED from either entry point IS a full §30 admission as of
           Amendment 3 — steps 1-14, no step unimplemented (PROJECT_STATUS.md:402-406).
AI-15 dependency
           none for the freeze. §9.2's OPEN-1 and §5.3's OPEN-2 are AI-05's and are
           listed in §16, not scheduled here.
```

### 14.3 AI-06

```text
contract   §15.1 FROZEN: AI-06 does not call admission; it projects, and "the
           caller submits it". §15.2 FROZEN: one invocation -> one ToolResult ->
           one ToolCall. §15.7: both AI-06 §6.5 rows are real.
code       plugins/security_tools/evidence.py — implemented, 2 functions.
call site  NONE. `tool_call_for` and `execution_payload_for` are called only by
           tests/security_tools/test_evidence_and_families.py.
evidence   AI-14 §5.1 classifies the AI-06 -> AI-05 row IMPLEMENTED BUT NOT
           CONNECTED, and Appendix A repeats it.
AI-15 dependency
           THE ONE POSSIBLE. Under READING A (§5.3), AI-06's seam needs a caller and
           no AI-05 amendment — its rows already exist and its contract already
           names a caller. Under READING B it needs one.
           AI-15 does NOT decide which, and MUST NOT implement either.
```

### 14.4 AI-08

```text
contract   §13.1 FROZEN: "AI-08 v1 therefore writes NO AI-05 EvidenceRecord of any
           kind." §13.2 FROZEN: the shape for the day it is admissible
           (producer_type service, actor.type agent, actor.id the AgentId), and the
           token itself DEFERRED. §13.3 FROZEN: no adjudication layer of its own.
code       agents/result.py — AgentResult is run data with NO producer field
           (agents/result.py:210-214, "is no AI-05 producer field here (§10.1)").
call site  NONE, and structurally refused at layer0 :1549.
evidence   tests/agents/test_layer_boundaries.py::TestNoEvidenceIsWritten asserts
           the import, the type names, and that a run produces no durable record.
AI-15 dependency
           none. AI-15 does not restate AI-08's job and does not schedule it.
```

### 14.5 AI-10

```text
contract   §13.2 FROZEN: "AI-10 MUST NOT write an AI-05 EvidenceRecord, under any
           producer token." §13.4: durable review evidence needs an AI-05
           amendment; v1 registers no AI-10 token.
code       review/ imports no plugins.evidence — enforced by an allowlist
           (layer0 :1833), and asserted at
           tests/review/test_review_boundaries.py::TestNoEvidenceIsWritten.
call site  NONE.
evidence   AI-14 §20 decision table: "durable review evidence — DEFERRED".
AI-15 dependency
           none. Unchanged by this phase.
```

### 14.6 AI-11

```text
contract   §21.1 FROZEN: "AI-11 v1 writes NO AI-05 EvidenceRecord"; "AI-11 MUST NOT
           add a producer token to AI-05's ADMITTED_EVENTS registry. … An added
           token is an AI-05 amendment, made by AI-05 under AI-05's amendment rule."
           §8.5: what a verdict never means. §23: non-goals.
code       benchmarks/ imports no plugins.evidence — enforced at layer0 :2465.
call site  NONE.
evidence   the model-measurement campaign is BLOCKED (AI-11 Layer 4, AI-12 §6).
AI-15 dependency
           none directly. §21.1's OPEN-1 is §15.3's subject and its owner is AI-05.
```

### 14.7 AI-13

```text
contract   §16 FROZEN: writes none and registers no producer. §13.5: an approval
           is not an EvidenceRecord. RunRecord (workflows/run.py) and Checkpoint
           are AI-13 types with no Evidence relationship.
code       workflows/ imports nothing outside itself — layer0 :2630 forbids every
           foreign root including `plugins`.
call site  NONE.
evidence   tests/workflows/test_workflow_boundaries.py T19 asserts it.
AI-15 dependency
           none. Unchanged by this phase.
```

### 14.8 AI-14

```text
contract   §22.1 B5 BLOCKED / NOT STARTED. §5.1 classifies the edge
           "Any producer -> Evidence" as IMPLEMENTED BUT NOT CONNECTED and
           Appendix A as "DOES NOT EXIST (by rule)". §4.2 rule 4: Evidence never
           becomes authorization. §13 FROZEN: AI-14 creates no producer token.
           §14 FROZEN: durable recording of run facts is DEFERRED until an AI-05
           amendment admits that phase's producer.
code       composition/ — 5 modules, no evidence import.
call site  NONE, refused structurally at layer0 :3241 and by the AST test at
           tests/composition/test_composition_boundaries.py:151.
evidence   AI-14-B merged as adf6db2476b7e3de33a585954610e9ab568b498c (PR #73).
AI-15 dependency
           YES. §15.2. Connecting B5 requires an AI-14 amendment; §24 lists
           "the execution topology's CONNECTED/SEAM classification of a path" as
           amendment-requiring, and §22.1 requires Appendix A to be updated in the
           same change.
```

### 14.9 A stale-record finding, reported and NOT fixed

```text
RECORDED: docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md carries AI-05 C-1 as
          DEFERRED or as an open blocker on FOURTEEN lines, all written before
          C-1 merged. `grep -n "C-1" <that file>` returns exactly:
              :76, :404, :928, :937, :1132, :1142, :1143, :1150, :1217, :1275,
              :1439, :1450, :1520, :1778
          and :930 asserts a falsifiable fact — "plugins/evidence/rules.py does not
          exist" — while plugins/evidence/rules.py exists (11,460 bytes, from
          C-1's merge on 2026-10-04).

RECORDED: `PROJECT_STATUS.md:155-157` already annotates this:
          "(C-1 itself was closed afterwards, by AI-05 Amendment 3; AI-14 recorded
           it as DEFERRED at the time, and that record is kept as what it was.)"
          So the staleness is a KNOWN, self-declared record, not a newly found
          defect.

WHY IT STILL MATTERS TO AI-15
    AI-14 §2 says a RECORDED fact that stops being true "is corrected by updating
    the record, never by arguing with it". §14 (:937) also carries a FROZEN clause
    conditioned on C-1 being DEFERRED, whose condition has since lapsed.
    When B5 is ever connected, §22.1 requires Appendix A's row for it to be
    restated in the same change — and that restatement has to reconcile these.

FOLLOW-UP / OWNER AMENDMENT REQUIRED — owner: AI-14.
AI-15 does NOT fix it, does not edit that file, and does not treat the stale text
as the current status. The current status is PROJECT_STATUS.md's and
MASTER_ROADMAP.md's, and both are current.
```

---

## 15. Amendment ownership

### 15.1 The three questions, separated

```text
AI-15's own contract       this document. Frozen by its merge. Amended by AI-15 §19.
the AI-05 producer         whether a producer token may be admitted, for whom, and
  amendment                on what evidence. Owned by AI-05.
the AI-11 reconciliation   whether AI-05 §28's "AI-11 CONSUMES Evidence" is
                           satisfied. Owned by AI-05, recorded by AI-11.
```

```text
FROZEN: these are three different things and AI-15 MUST NOT merge them. In
        particular, "AI-15-B is done" MUST NOT be offered as the reconciliation of
        AI-11 §21.1's OPEN-1.
```

### 15.2 AI-14 amendment — REQUIRED, and it is a prerequisite

```text
WHAT MUST CHANGE
    §5.1's classification of "Any producer -> Evidence"        IMPLEMENTED BUT NOT
                                                               CONNECTED -> CONNECTED
    §22.1 B5's item status and its "blocked by" clause
    Appendix A's classification of the composition -> Evidence row
    §25's amendment log
WHY
    AI-14 §24 lists "the execution topology's CONNECTED/SEAM classification of a
    path" as amendment-requiring, and §22.1 requires Appendix A to be updated in
    the SAME change that connects a seam.
ALSO IN THE SAME CHANGE
    scripts/ci/layer0_policy.py:3241    AI14_FORBIDDEN_IMPORTS
    tests/composition/test_composition_boundaries.py:151-176   the AST block
    tests/composition/test_composition_boundaries.py:178-191   the `producer_token`
                                                               name block
OWNER      AI-14.
AI-15 RELATIONSHIP  AI-15-B MUST NOT START until it lands. This is a PREREQUISITE,
                    not a parallel workstream.
```

### 15.3 AI-05 amendment — what it does and does not unblock

```text
THE ASK, as AI-11 §21.1 and Annex B.1 state it:
    "The two are reconciled the day a producer token is admitted, which is an
     AI-05 amendment."   /  "RESOLUTION PATH: an AI-05 amendment admitting a
     producer token."
OWNER      AI-05. AI-11 says so twice: "An added token is an AI-05 amendment, made
           by AI-05 under AI-05's amendment rule."
AI-11 MUST NOT BE MODIFIED to relieve this. It says so: "AI-11 §21.1 is not
amended; AI-05 §28 is not amended."
```

```text
FROZEN: AI-15 does NOT own this and MUST NOT request a specific token.
FROZEN: AI-15 MUST NOT borrow "ai-06", MUST NOT register "ai-15", and MUST NOT
        claim the composition may be a producer (§7.1).
FROZEN: the AMENDMENT, if ever made, unblocks ONLY the phases whose facts it
        admits. It does NOT by itself unblock B5, because §15.2's AI-14 amendment
        and §3.4's structural blocks are independent of it.
```

```text
THE POINT AI-15-A EXISTS TO MAKE

    "wait for the producer-token amendment" is NOT a sufficient plan for B5.

    A phase that wants a durable record needs THREE things, and the token is one:
        (i)   a §6.5 row                    AI-05 amendment
        (ii)  its own contract permitting it to write
                                            THAT phase's amendment
              (AI-08 §13.1, AI-10 §13.2, AI-11 §21.1, AI-13 §16 each FROZEN the
               opposite today)
        (iii) its Layer 0 boundary narrowed
                                            layer0 :1549 / :1833 / :2465 / :2630
    and B5 additionally needs:
        (iv)  AI-14 §5.1 / §22.1 B5 / Appendix A amended   §15.2
        (v)   layer0 :3241 narrowed                        §15.2
        (vi)  two assertions in tests/composition/ amended §15.2

    Six changes, four owners. AI-15 owns none of them.
```

### 15.4 What AI-15 owns, and it is only this

```text
FROZEN: AI-15 owns this document. It owns the CONNECTED definition (§8.3), the
        failure semantics (§11), the workspace obligations (§12) and the authority
        restatements (§13) — and only to the extent they RESTATE rather than
        change an earlier contract.
FROZEN: where AI-15 and an earlier contract differ, the earlier contract governs
        and this document is wrong (§19).
```

---

## 16. OPEN / BLOCKED / DEFERRED / OUT-OF-SCOPE inventory

### 16.1 OPEN

```text
OPEN-1  producer authenticity — how is a producer claim established, as against
        merely well-formed?
        OWNER   AI-05
        STATUS  OPEN. Not a TODO for AI-15-B.
        NOTE    the gap is LATENT today (§3.4) — no module can reach the entry
                point. It becomes live the moment any writer is connected, which is
                why it is a PREREQUISITE for B5's completion rather than a
                follow-up.

OPEN-2  which reading of AI-05 §7's "WROTE" governs when the submitter is not the
        named component?
        OWNER   AI-05
        STATUS  OPEN. §5.3 states both readings and AI-15 does not choose.
        BLOCKS  the AI-06 path, and therefore the ONLY topology that could connect
                without a §6.5 amendment (§7.2 T2).

OPEN-3  whether DecisionRecord.evidence_ref should ever carry an AI-05 id.
        OWNER   AI-04
        STATUS  OPEN. §13.4.

OPEN-4  a workflow-driven step's routing input.
        OWNER   AI-13 / AI-14
        STATUS  OPEN, recorded by AI-14 §22.1 B3 as "RECORDED, NOT RESOLVED".
        RELATIONSHIP TO AI-15  NONE. Listed so a reader does not attribute it here.
```

```text
FROZEN: OPEN-1 and OPEN-2 MUST NOT be closed by an AI-15-B implementation decision
        (AI-14 §2: "An OPEN item MUST NOT be closed by an implementation decision").
```

### 16.2 BLOCKED

```text
B5 — composition -> Evidence
    BLOCKED. Blockers, all of them live: §15.2's AI-14 amendment, layer0 :3241,
    the two composition assertions, and — for every event but AI-06's — §15.3's
    registry and per-phase contract rows.
    OWNERS   AI-14 (the amendment), AI-05 (the token, where needed), each phase
             (its own writer clause).
    AI-15-B  MUST NOT START. §7.3.

AI-12-C — the campaign over policies
    BLOCKED / NOT STARTED. Owner: AI-12. Unchanged by AI-15.

the model-comparative prerequisite
    BLOCKED. AI-12 §6: "per-model measurements under a separate contract defining
    their producer, attribution and measurement method."
    NOTE: that phrase — "their producer" — is the same question as §4.1's. AI-15
    notes the overlap and does NOT resolve it.
    Unchanged by AI-15.
```

### 16.3 DEFERRED

```text
AI-05 §35.1 — F-10 (the legacy evidence_ref rename), and the storage-backend
    record and the record_digest round-trip obligation as §35.1 states them.
    Owner: AI-05. UNCHANGED by AI-15.

durable review evidence
    AI-10 §13.4 / AI-14 §20: needs an AI-05 amendment admitting an AI-10 token.
    Owner: AI-05 (the token) + AI-10 (its own clause). UNCHANGED.

the AI-11 model-measurement campaign
    AI-11 §20/§22.2, gated on §22.2. Owner: AI-11. UNCHANGED.

the AI-07 routing DECISION event and the human-approval event
    AI-05 §6.5/§6.2: both DEFERRED, neither representable in v1, and neither gains
    a placeholder token, a discriminator, a reserved field or an interface
    reservation. UNCHANGED — and AI-15 MUST NOT add one.
```

### 16.4 OUT OF SCOPE

```text
permanently, by this document (§1.3):
    a record-level trust root, a signer, a signature, a key
    a producer-registry service, a daemon, a scheduler
    a new credential path or a new central authority
    a second Evidence contract, a second outcome vocabulary, a second registry
    a composition producer token
    cross-workspace aggregation, a multi-workspace record, a record merge
    a new Evidence kind, family, producer type or admission outcome
    reimplementing §30 anywhere
    promoting a staged record programmatically
    a retry loop, a queue, or a backfill over past run data

not this phase's, and MUST NOT be pulled in:
    AI-12-C  ·  the model-comparative prerequisite  ·  live provider verification
    AI-05 §35.1  ·  Workflow -> Router input  ·  a new Agent, provider or fallback
```

```text
FROZEN: an item moved out of §16.4 requires an amendment to THIS document (§19),
        not a work item.
```

---

## 17. AI-15-B implementation boundary

Nothing here is authorized until this document is merged AND §15.2 has landed.

### 17.1 Allowed after the freeze

```text
PERMITTED, once this document is merged:
    a Layer 0 check for AI-15, mirroring the other phases' checks, if AI-15 adds a
      top-level package or a module — AI-14 §22.1's "a new top-level package
      arrived with its own check (§17)"
    tests that assert the ABSENCE described in §3 — i.e. that no production caller
      exists — so a future connection is a visible change rather than a silent one
    tests for §11's failure semantics that use a test double and DO NOT claim a
      CONNECTED seam
```

```text
FROZEN: none of the above may be reported as B5 progress. B5 is BLOCKED until
        §15.2 lands.
```

### 17.2 Blocked until the AI-14 amendment

```text
BLOCKED (§15.2 — AI-14 owns all of it):
    any import of `plugins.evidence` from composition/
    narrowing layer0 :3241
    amending tests/composition/test_composition_boundaries.py:151, :178
    restating AI-14 §5.1 / §22.1 B5 / Appendix A
```

### 17.3 Blocked until an AI-05 amendment — and only for some events

```text
BLOCKED until AI-05 admits a producer (§15.3):
    any record for a phase with NO §6.5 row — AI-08, AI-10, AI-11, AI-13, AI-14 —
      and each phase's own writer clause must also be amended, by that phase
NOT BLOCKED by a token, but blocked by OPEN-2 (§5.3):
    the AI-06 rows exist and AI-06 §15.1 names a caller, so the AI-06 path needs no
      §6.5 amendment — under READING A. AI-15 MUST NOT proceed on that reading
      alone.
```

### 17.4 Forbidden in AI-15, permanently

```text
FORBIDDEN:
    adding a producer token, or a row to §6.5
    editing AI-05's contract, AI-11's contract, or AI-14's contract
    editing any phase's Layer 0 boundary on that phase's behalf
    adding a trust root, a signer, a key, a registry service or a credential path
    implementing a writer in a phase that has not amended its own contract
    a composition producer token (§7.1)
    reimplementing any part of §30
    reading ACCEPTED as an authorization, a capability, a verification or a
      measurement
    a fallback producer, a repaired retry, or a default workspace
    cross-workspace anything
    reporting B5 as CONNECTED, or as "mostly connected", on §8.3's items 1-9 while
      failing item 10
```

### 17.5 The four questions, answered for AI-15-B

```text
Q  does the composition call plugins.evidence directly, or does the owner phase?
A  §7.3: only T2 is consistent with the frozen contracts — the composition submits
   a record the OWNING phase authored — and only under READING A, and only after
   §15.2. AI-15-B MUST NOT choose T1 or T3.

Q  is the composition only an orchestrator?
A  YES. AI-14 §3: it is not a component. It supplies NO fact of its own (§7.4),
   holds NO decision (root.py:20-30), and gains NO authority (§13).

Q  does the owner phase hold the producer token?
A  THE TOKEN IS NOT HELD (§4.3). It is a NAME registered for an event. What the
   owning phase owns is the CLAIM — §5.1's table maps each fact to its phase, and
   §9.4 fixes what a forwarder may not rewrite.

Q  is an admission failure a hard failure, an observable result, or a
   non-authoritative outcome?
A  IT IS A VALUE, AND IT IS OBSERVABLE, AND IT IS NON-AUTHORITATIVE — all three,
   and none of them means "harmless". §11.2 fixes who observes it and what is
   persisted; §10.3 forbids converting it into a success. AI-15-B MUST NOT make it
   hard-fail the composition process (that would give Evidence a veto, which is an
   authority AI-14 §4.1 does not grant) and MUST NOT swallow it (§11.3).
```

---

## 18. Exit criteria

```text
AI-15-A IS DONE WHEN
    this document is merged to `main`
    it names, at file:line, every RECORDED fact it rests on (§3, §20)
    it separates contract / implementation / call site / evidence everywhere
      (§2.1)
    it states the producer-ownership question and assigns its owners (§4, §9, §15)
    it states OPEN-1, OPEN-2, OPEN-3 and OPEN-4 with their owners (§16)
    it defines CONNECTED for B5 (§8.3), on top of AI-14 §2's definition
    it fixes failure semantics against AI-05's existing vocabulary, adding none (§11)
    it freezes the workspace obligations (§12)
    it restates the authority rules and forbids any transfer (§13)
    it states AI-15-B's boundary, including everything it may NOT do (§17)
    it changes NO runtime file and NO other phase's contract

AI-15-A IS NOT DONE IF
    any claim of CONNECTED appears without a non-test call site named by file:line
    any frozen clause of AI-00 .. AI-14 is modified or restated in weaker words
    a producer token, a registry row, a new outcome or a new trust root appears
    B5's BLOCKED status is presented as a scheduling matter rather than named
      blockers with owners
    an OPEN item is closed by a decision this document makes
```

---

## 19. Amendment and normative language

```text
PROPOSED (this document's class until the merge that freezes it)
```

```text
FROZEN: once merged, AI-15-B MUST NOT deviate from this document without amending
        it first. An amendment is REQUIRED for any change to:
            the CONNECTED definition (§8.3)
            the provenance / immutability rules (§9.4)
            the admission boundary AI-15-B may call (§10)
            the failure semantics (§11.2) or the forbidden conversions (§11.3)
            the workspace rules (§12.3)
            the authority rules (§13)
            the AI-15-B boundary (§17)
            any item in the §16 inventory, or its owner
AN AMENDMENT RECORDS: what changed, why, its security and authority impact, and
        the date. It is committed BEFORE the code that depends on it.
FROZEN: AI-15 owns this document and NOTHING else. An amendment to AI-00 .. AI-14
        is made by that phase, under that phase's rule, BEFORE AI-15 depends on it.
FROZEN: where this document and an earlier contract differ, the EARLIER CONTRACT
        governs and this document is wrong.
```

```text
THE NORMATIVE CLASSES, USED AS AI-14 §2 DEFINES THEM
    FROZEN      settled here; AI-15-B implements it; changing it needs an amendment
    PROPOSED    this document's choice; normative for AI-15-B; most likely to be
                amended
    RECORDED    a fact about the repository as it is
    OPEN        a question this document does NOT answer
    BLOCKED     cannot be done now; the blocker is named
    DEFERRED    deliberately not done; the reason is recorded
    OUT OF SCOPE  refused and not planned

FROZEN: these seven MUST NOT be used interchangeably, and a clause MUST NOT carry
        two of them.
```

---

## 20. Appendix — the exact current call sites

Every line below is re-checkable on `main` @ `37f354c`.

### 20.1 Non-test call sites of the Evidence entry points

```text
admission.admit()
    plugins/evidence/admission.py:265      called by admit_to_store() — INTERNAL

admission.admit_to_store()
    (none)

EvidenceRecord(...)
    plugins/evidence/stored.py:172         load_stored() — the READ path

plugins.evidence import (non-test, outside the package)
    plugins/security_tools/evidence.py:12  `ExecutionPayload, ToolCall` — TYPES ONLY

tools_call_for / execution_payload_for
    plugins/security_tools/__init__.py:80  re-export
    tests/security_tools/test_evidence_and_families.py  the ONLY callers
```

### 20.2 Test-only call sites

```text
admit()          tests/evidence/test_admission_pipeline.py:88
                 tests/evidence/test_admission_rules.py:56
                 tests/evidence/test_digests.py:123,148
                 tests/evidence/test_stored_form.py:318,325
                 tests/evidence/test_workspace_agreement.py:75
admit_to_store() tests/evidence/test_admission_pipeline.py:51
                 tests/evidence/test_admission_rules.py:541
                 tests/evidence/test_store.py:495,499
```

### 20.3 The structural blocks, and their non-vacuity proofs

```text
composition/   scripts/ci/layer0_policy.py:3241  (checked :3351)
               tests/composition/test_composition_boundaries.py:151-176
               tests/composition/test_composition_boundaries.py:178-191
               proven non-vacuous: tests/composition/test_composition_layer0.py:98-101
agents/        scripts/ci/layer0_policy.py:1549
review/        scripts/ci/layer0_policy.py:1833   (allowlist)
benchmarks/    scripts/ci/layer0_policy.py:2465-2468
workflows/     scripts/ci/layer0_policy.py:2630   ("plugins" in the forbidden roots)
```

### 20.4 The registry, as declared

```text
plugins/evidence/models.py:125   ADMITTED_EVENTS: tuple[AdmittedEvent, ...]
plugins/evidence/models.py:126   "AI-03 context read"          ai-03
plugins/evidence/models.py:130   "AI-02 provider probe"        ai-02
plugins/evidence/models.py:134   "AI-02 capability observation" ai-02
plugins/evidence/models.py:139   "AI-04 Guard decision"        ai-04
plugins/evidence/models.py:143   "AI-06 tool execution"        ai-06
plugins/evidence/models.py:147   "AI-06 test result"           ai-06
plugins/evidence/models.py:154   admitted_events_for()         read-only
producer tokens ai-05/07/08/09/10/11/12/13/14/15: 0 occurrences anywhere
```

### 20.5 The admission pipeline's order

```text
admission.py:199  step 7   check_admission_rules(raw)         §14.10
admission.py:200  steps 1-4, 4b, 6, 8-13
                           EvidenceRecord.from_mapping(raw)   -> models.py:1586
                                                                 check_cross_field
                                                                 (§6.5 / §6.6)
admission.py:201  step 5   check_workspace_agreement(record)  §18.1
admission.py:202  step 12  assign_digests(record)
admission.py:271  step 14  store.contains(evidence_id)
admission.py:276           store.write(record)
```

### 20.6 The run-data types that would be candidates, and their Evidence status

```text
AgentResult      agents/result.py:210-225                 12 fields; no producer
                                                          field (§10.1)
RunRecord        workflows/run.py           24 fields; workspace_identity
BenchmarkRun     benchmarks/run.py          30 fields; workspace_identity
ReviewCase       review/case.py             7 fields; identifiers only
DecisionRecord   plugins/guard/models.py    15 fields; evidence_ref never populated
```

### 20.7 What this appendix does not claim

```text
FROZEN: this appendix is the EVIDENCE BASE for §3 and §5. It is a RECORDED
        snapshot of `main` @ 37f354c. It MUST be re-derived, not trusted, when the
        tree moves — and it MUST be updated in the same change that connects a
        seam.
FROZEN: a row that says "(none)" is a finding, not an omission. It MUST NOT be
        silently filled in by a later implementation that wants a complete-looking
        table.
```

---

## Status

```text
AI-15-A  = DRAFT / FREEZE PROPOSAL      this document
AI-15-B  = NOT STARTED                  BLOCKED (§16.2, §15.2)
```

```text
BLOCKED: B5 (composition -> Evidence) is unchanged by this document. The AI-14
         amendment (§15.2) has not been made, the Layer 0 block at :3241 stands,
         and no producer token has been added.

OPEN:    OPEN-1 (AI-05) · OPEN-2 (AI-05) · OPEN-3 (AI-04) · OPEN-4 (AI-13/AI-14)

UNCHANGED BY THIS DOCUMENT: AI-05 · AI-06 · AI-08 · AI-10 · AI-11 · AI-13 · AI-14
         contracts, implementations and boundaries — every one byte-identical.

NOT CLAIMED: that Evidence is connected. It is not. §3 records what is, and §20
         records it at file:line.
```
