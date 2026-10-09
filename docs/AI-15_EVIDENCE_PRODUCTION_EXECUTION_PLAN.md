# AI-15 — Evidence Production / Composition Integration — Execution Plan

> Phase: AI-15 — Evidence Production / Composition Integration
> Sub-phase: AI-15-A — architecture / contract freeze
> Baseline: `main` @ `37f354cbb3c007f2d92021fa560a443a53591372`
> Status: **FROZEN — COMPLETE / MERGED.** The freeze act was the merge of PR #78
> (`6e814a8b6d214a0203deb73b1abbf21ae50b68cc`, a true two-parent merge of
> `37f354cbb3c007f2d92021fa560a443a53591372` and
> `210a1907b453e927c1af8074a3f33ba8f51fe1b6`).
>
> It froze an ARCHITECTURE / CONTRACT. It wrote no runtime, created and registered
> no producer token, and connected no seam. **AI-15-B is NOT STARTED / BLOCKED** and
> **B5 (composition → Evidence) is BLOCKED / NOT STARTED**. An implementation that
> depends on a prerequisite amendment still MUST NOT begin: that prohibition is
> §15.2's and §16.2's, both FROZEN before this closeout, and neither is changed
> here. §15.2 names each step and its owner; §16.2 lists the live blockers. See
> §Status for the merge record.
>
> A change to this document now follows §19's amendment rule, which is unchanged by
> the merge.

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
PROPOSED  the boundary between REGISTRY MEMBERSHIP and AUTHENTICATION, and between
          AUTHENTICATION and AUTHORIZATION (§4.3, §9.5)
PROPOSED  the ORDER in which B5's blockers must be discharged, so that no
          prerequisite amendment is asked to assert an outcome that does not yet
          exist (§15.2)
RECORDED  the current-state audit: contract / implementation / call site (§3, §20)
```

### 1.3 Scope — what AI-15 does NOT own

```text
OUT OF SCOPE  AI-05's §6.5 registry, §6.6 rules, §7 producer model, §30 contract
OUT OF SCOPE  producer AUTHENTICATION — how a producer claim is established.
              AI15-OPEN-1, owned by AI-05 (§9.2). AI-15 neither resolves it nor
              builds any mechanism for it (§9.5, §17.4)
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
                 and persists. Both run step 7 (AI-05 §14.10) since Amendment 3.
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

**These are BUILD-TIME checks. They are not a runtime sandbox, and AI-15 MUST NOT
describe them as one.**

```text
WHAT LAYER 0 IS      scripts/ci/layer0_policy.py, run by CI, plus the boundary
                     tests under tests/. It reads the REPOSITORY and reports a
                     problem for a change that violates a frozen architectural
                     rule. A problem FAILS the build.
WHAT LAYER 0 IS NOT  a runtime enforcement. Nothing stops a Python module from
                     executing `from plugins.evidence import admit`. If such a
                     module were committed, it would IMPORT AND RUN. What the
                     checks do is refuse the COMMIT — the constraint is that this
                     repository will not merge the change, not that the
                     interpreter will stop the code.
```

```text
FROZEN: a statement of the form "the composition cannot reach Evidence at runtime"
        is FALSE and MUST NOT appear in this document or in any AI-15-B change.
        The verifiable statement is the one below.
FROZEN: IF A WRITER IS EVER PRESENT AND RUNS WHILE §15.2 STEP 0b IS UNSATISFIED,
        THAT IS A VIOLATION OF THE ARCHITECTURE. It is NOT a legitimate
        intermediate state, and it is NOT something these checks prevented — they
        refuse a CHANGE, and they do not stop code that is already merged from
        executing. A record such a writer stores is stored, and no later label
        undoes it (§6.1).
```

```text
RECORDED, and this is what §3.1-§3.3 measured: at main @ 37f354c there is NO
production caller of AI-05 admission that conforms to the frozen architectural
rules. Two different claims, two different strengths, and AI-15 states both
rather than merging them:
    none was WRITTEN — a negative finding about this tree; and
    a change adding one would be refused by an explicit check, WHERE A CHECK
      COVERS THE DIRECTORY THE CALLER IS ADDED TO.

```

```text
SCOPE, STATED BEFORE THE TABLE — THESE ARE PER-DIRECTORY RULES, NOT A GLOBAL
BARRIER. Five of the components carry an explicit Layer 0 rule that refuses a
`plugins.evidence` import. `plugins/security_tools/` carries NONE, and the
projection it holds is a FROZEN CLAUSE OF AI-06'S OWN CONTRACT (§15.1, §15.2)
rather than something a Layer 0 rule enforces.

    WITH an explicit rule      composition/ · agents/ · review/ · benchmarks/
                               · workflows/
    WITHOUT one — permitted   plugins/security_tools/ — AI-06's projection
                               (§14.3); the import is CONTRACT-SANCTIONED
    WITHOUT one — it IS the   plugins/evidence/ — the package itself (§14.2)
      package
    WITHOUT one — no import   every other package, today
      today
```

```text
FROZEN: AI-15 MUST NOT describe the table below as a GLOBAL DEFENCE covering
        every possible writer. It is a set of checks on the directories that
        have them, and it is complete only for those directories.
FROZEN: A WRITER PLACED IN A PACKAGE WITH NO RULE WOULD NOT BE REFUSED BY
        LAYER 0 AT ALL. Nothing in this repository would stop it structurally;
        what would refuse it is that phase's own contract — which is a rule, not
        a check — and AI-15 states that difference rather than hiding it behind
        the table.
FROZEN: the checks are not a global barrier, and the RECORDED absence of a
        caller is not runtime unreachability. Those are two separate corrections
        and neither substitutes for the other.

```text
COMPONENT            ENFORCEMENT                                  FILE:LINE
                     — five directories carry a rule; security_tools does NOT
composition/         AI14_FORBIDDEN_IMPORTS = ("plugins.evidence",)
                                                                  scripts/ci/layer0_policy.py:3241
                                                                  checked at :3351
agents/              AGENTS_FORBIDDEN_IMPORTS check, explicit
                                                                  scripts/ci/layer0_policy.py:1549
review/              AI10_ALLOWED_PLUGIN_IMPORTS is an ALLOWLIST
                     ("plugins.security_tools", "plugins.context")
                     plugins.evidence is absent from the
                     allowlist, so a change importing
                     it is REPORTED by the check            :1833
benchmarks/          explicit check, "AI-11 v1 writes no AI-05
                     EvidenceRecord (contract 21.1)"             :2465-2468
workflows/           AI13_FORBIDDEN_IMPORT_ROOTS includes
                     "plugins"  (comment: "guard (AI-04),
                     evidence (AI-05), security_tools (AI-06)")   :2630
plugins/security_tools/  NO LAYER 0 RULE. Its import of two
                     AI-05 payload types is permitted by
                     AI-06 §15.1/§15.2 — a CONTRACT
                     clause, not a check. A change adding
                     an admission CALLER here would be
                     refused by AI-06's contract and by
                     review, NOT by layer0                    (none)
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
RECORDED: the COMPOSITION block — and only that one, since it is the only block
          with such a proof — is proven NON-VACUOUS at
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
        All three are owned by AI-14, not by AI-15 (§15.2).
FROZEN: and the check that would refuse the import is a REPOSITORY check on the
        committed change. It protects the ARCHITECTURE, not the process: while it
        stands, a merged change cannot introduce the edge, and that is the whole
        of what it guarantees.
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
5  EVENT KIND            EvidenceKind = OBSERVATION | DECISION | EXECUTION
                         (AI-05 §6). Describes THE ACT, and is what selects the
                         payload (AI-05 §11).
6  EVENT FAMILY          ObservationFamily = SOURCE_READ | PROVIDER_PROBE |
                         CAPABILITY_OBSERVATION (AI-05 §6.7). REQUIRED on an
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
FROZEN: TODAY'S PIPELINE ACCEPTS THE CLAIM ON EXACTLY THE FIRST OF THOSE BASES.
        A caller-supplied string is the sole basis of `provenance.producer`, and
        §4.3 records what is and is not checked. This list states the RULE; §4.3
        states the GAP between the rule and the implementation, and neither is a
        substitute for the other.
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
FROZEN: §6.5 REGISTRY MEMBERSHIP PROVES REGISTRATION AND NOTHING ELSE. A value
        passing `g_registered` proves that the string is the token the registry
        holds for this (kind, family). It does NOT prove that the named component
        produced the record, that the submitter is that component, or that the
        submitter is entitled to speak for it. Registry validation is a
        WELL-FORMEDNESS check; producer AUTHENTICATION is a different question,
        and no step of §30 answers it.
FROZEN: A NON-TEST CALL SITE IS NOT PRODUCER PROVENANCE. Wiring a caller to
        `admit_to_store` establishes that records can be WRITTEN. It establishes
        nothing about WHO wrote them. §8.3 carries this as its own condition,
        because a reader could otherwise take "the seam is connected" for "the
        provenance is sound" — an inference this document refuses.
FROZEN: AI-15-A does NOT fix this. §1.3 puts a new trust MECHANISM out of scope,
        and §9.5 keeps the trust question apart from the authority question.
        Recorded as AI15-OPEN-1 in §9.2 and §16, with the consequence stated
        rather than hidden.
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
RECORDED: whether this matters today is answered by §3, and the answer has THREE
          parts that MUST NOT be merged:
              BASELINE       at main @ 37f354c there is NO production Evidence
                             admission caller (§3.1-§3.3). A negative finding
                             about this tree: it says what has been WRITTEN, not
                             what can RUN.
              WITH A RULE    a change adding such a caller TO ONE OF THE FIVE
                             DIRECTORIES THAT CARRY A LAYER 0 RULE would be
                             refused by the corresponding build-time check,
                             which rejects the commit (§3.4).
              WITHOUT ONE    a caller placed in a directory with NO rule — the
                             clearest case is `plugins/security_tools/` (§3.4,
                             §14.3) — would NOT be refused by a build-time check,
                             because there is none to refuse it. What governs it
                             is the owning phase's CONTRACT, and A CONTRACT RULE
                             IS NOT A BUILD-TIME CHECK. AI-15 MUST NOT describe
                             one as the other.
          None of the three is a runtime barrier. A committed module that
          imported `plugins.evidence` would RUN (§3.4), and nothing in this
          repository stops it at runtime. The gap is LATENT — no caller exists —
          not IMPOSSIBLE, and stating it as latent is the point.
FROZEN: while AI15-OPEN-1 is OPEN, NO production, non-test call site that can
        execute admission and persist an EvidenceRecord may be created, merged
        or run — IN ANY DIRECTORY, whether or not a Layer 0 rule covers it
        (§15.2 STEP 0b, §17.2b). That rule does not depend on a check existing,
        which is exactly why it is stated as a rule.
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
AI-05 §7's worked example binds `producer` to the OWNING COMPONENT OF THE ACT.
§13.1 of AI-08 draws the strict conclusion from it:
    "`producer` names the component that WROTE the record, and that claim would be
     false [if AI-08 wrote under ai-06]."
```

**The analysis below is the AI-15-A freeze-time record, and it is kept as what it
was.** It states the question as it stood when this contract was frozen. The
question has since been answered by the phase that owns it — see the disposition
block after the reading list (§19, Amendment 1).

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
    Consistent with:  AI-05 §7's literal wording, and AI-08 §13.1's reasoning
                      applied
                      to a courier.
    Consequence:      AI-06 §15.1 is unimplementable without an AI-05 amendment.
```

```text
AI15-OPEN-2  Which reading of AI-05 §7's "WROTE" governs `producer` when the
             submitter is not the named component?

        OWNER            AI-05 — it owns §7, §6.5 and §6.6, and it answered
        STATUS           CLOSED / ANSWERED BY AI-05 AMENDMENT 4 (§19, Amendment 1)
        THE ANSWER       READING A. AI-05 Amendment 4 has chosen, and is IN FORCE
                         as of its merge (PR #80, 03d42681cb8b2110773654822655117daea44ad5)
        ANSWERED BY      AI-05 itself, in AI-05's own contract. AI-15 did NOT
                         choose this, did not implement it and did not test it
                         into existence. AI-15 records the answer and updates its
                         own dependency state.
        WHY IT MATTERED   READING A makes the AI-06 -> AI-05 projection the one
                         seam that could be connected WITHOUT a §6.5 amendment.
                         READING B would have made it need one. The chosen
                         reading is the one that leaves the seam reachable; it
                         does NOT connect it, and does not make the record
                         admissible that was not admissible before.
```

```text
RECORDED — THE DISPOSITION, AND ITS LIMITS.

    AI-05 Amendment 4 defines `producer` as the component RESPONSIBLE FOR THE
    CONTENT of the event the record describes, and `submitter` as the caller that
    hands a prepared record to `admit()` or `admit_to_store()`. It states that
    calling either entry point does NOT by itself confer the producer role, and
    that registry validation, producer authentication and submitter identity are
    THREE DIFFERENT CHECKS that must not be conflated.

    WHAT THIS CLOSES    AI15-OPEN-2, and only it: the semantic relation between
                        the producer named on a record and the caller that
                        submits it.
    WHAT THIS DOES NOT  establish producer authentication. AI15-OPEN-1 remains
      CLOSE             OPEN, and AI-05 Amendment 4 records the same: it builds
                        no authentication mechanism and claims no claim is
                        trustworthy. It does not touch AI-11 §21.1's OPEN-1,
                        which asks a different question with the same owner.
```

```text
FROZEN: AI-15 MUST NOT resolve an OPEN item by implementing an answer to it.
FROZEN: AI-15 MUST NOT "test" an OPEN item by writing the record either way. A test
        asserting an outcome would settle by convention what a contract has not
        settled.
RECORDED: AI15-OPEN-2 was closed the way this rule requires and not by breaking it.
        It was answered by AI-05, in AI-05's contract, under AI-05's amendment
        rule. AI-15 wrote no implementation and added no test asserting an
        outcome; it recorded the answer (§19, Amendment 1).
```

---

## 6. Evidence production boundary

### 6.1 What promotion from run data to EvidenceRecord requires

```text
FROZEN: run data does NOT become Evidence by being produced, by being correct, by
        being observed, or by a model judging it true. It becomes Evidence by
        passing §30 admission under an ADMITTED producer, and by nothing else.
FROZEN: "PASSING §30 ADMISSION UNDER AN ADMITTED PRODUCER" IS A STATEMENT ABOUT
        THE RECORD, NOT ABOUT THE SUBMITTER. §30's fourteen steps include no step
        that establishes who submitted the record (§4.3). So a durable admission
        means exactly this: the record is well formed, its producer token is the
        one the registry holds for this kind and family, its workspace agrees, and
        it is now stored. It does NOT mean the named component wrote it.
FROZEN: DURABILITY DOES NOT UPGRADE THE CLAIM. A staged record and a promoted one
        carry the same bytes and the same digests (§20.3), so promotion adds
        EXISTENCE, not AUTHENTICITY. A reader MUST NOT treat "it is durable" as
        stronger evidence of its producer than "it was admitted" was — promotion
        is a human copy, not a verification step.
FROZEN: THE AUTHENTICITY CONDITION IS AI15-OPEN-1, AND IT IS AI-05'S TO DEFINE.
        Until AI-05 has defined it AND it has been implemented AND tests show it
        holds, no document, no caller and no result may describe an admitted
        record as PROVEN to have been produced by the component its token names.
        §8.3 carries this as its own CONNECTED condition.
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
FROZEN: SecretValue MUST NOT cross the boundary, and the AI-05 §14.10 rule set is
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
     IT INHERITED AI15-OPEN-2 (§5.3): whether a submitting composition authors a
     false producer claim by the standard AI-08 §13.1 applied to itself. AI-05
     Amendment 4 answered that with READING A — a submitter MAY differ from the
     producer and does not thereby make a false claim — so this objection is
     SETTLED, and it was settled by the owner, not by AI-15 (§19 Amendment 1).
     THE ONE UNBLOCKED PATH: AI-06's rows exist and AI-06 §15.1 names a caller.
     WHAT IS NOT UNBLOCKED: the path itself. T2 still has no authorized call
     site, and STEP 0b still forbids one (§17.2b).

T3 — COMPOSITION AS A NEW PRODUCER
     REJECTED by §7.1. OUT OF SCOPE, permanently.
```

### 7.3 What AI-15-A concludes about the topology

```text
FROZEN: the ONLY topology consistent with the frozen contracts is T2, and only
        under READING A, and only for an event whose registry row already exists,
        and only after §15.2's ordered steps are satisfied: AI-14 authorizes the
        edge (STEP 1), a call site exists (STEP 2), and AI-14 records the
        classification with it (STEP 3).
FROZEN: T2 IS LEGAL ONLY UNDER READING A — AND THAT CONDITION IS NOW MET. AI-05
        Amendment 4 chose READING A and is IN FORCE (§5.3, §19 Amendment 1).
        Had it chosen READING B there would be no legal forwarder and T2 would
        not be available at all, leaving T1 as the only shape with its five
        amendments AI-15 does not own. That branch did not occur.
FROZEN: READING A BEING SETTLED IS NOT T2 BEING CONNECTED, AND NOT T2 BEING
        AUTHORIZED. T2 remains a topology this document considers legal; it has
        no call site (STEP 2), no AI-14 authorization (STEP 1) and no
        classification (STEP 3). Nothing here may be read as a connection.
FROZEN: T1 is not forbidden by AI-15 — it is the topology each phase's own
        contract would have to choose if it wanted its own writer — but AI-15 owns
        none of the amendments it needs and MUST NOT assume it.
FROZEN: T3 is refused.
FROZEN: AI-15-B MUST NOT begin T2's implementation. STEP 1 is a PREREQUISITE, not
        a parallel workstream, and STEP 3 may not run before STEP 0b (§15.2).
        STEP 0a is satisfied and STEP 1's semantic precondition is therefore met;
        STEP 1 itself has NOT been made, and it is AI-14's to make.
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
A  NOBODY, AND THE QUESTION THAT SAT BEHIND IT IS NOW ANSWERED. Whether a caller
   other than the producing component may submit a record is settled by AI-05
   Amendment 4 — READING A, so it may (§5.3, §19 Amendment 1). That names no
   submitter: the answer is still "nobody" today (§3.2), because no production
   caller has been written and §15.2 STEP 0b forbids writing one while AI15-OPEN-1
   is open.

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
    a non-test call site on its own — it proves records can be written, not who
      wrote them (§4.3), and before §15.2 STEP 0b such a call site MUST
      NOT EXIST AT ALL (§17.2b)
    a record the registry ACCEPTED — §6.5 membership is a well-formedness check,
      not an authentication (§4.3, §9.2)
    a record that was ADMITTED and then PROMOTED — durability adds existence, not
      authenticity (§6.1)
```

### 8.3 The B5 CONNECTED definition — PROPOSED

B5 is CONNECTED when **all twelve** hold, and each is checkable from the
repository.

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
    exception, never swallowed, never re-read as a success (§11) — and, in the
    other direction, no API misuse is recast AS an outcome: a programming error
    stays an exception and MUST NOT be reported as REJECTED or UNAVAILABLE
    (§11.2)
 9  exactly one record is written per production event, into the STAGED tier, and
    §30 step 14 is run (`admit_to_store`, not a bare `store.write`)
10  the authority matrix is unchanged, and the change names what it did NOT prove:
    that an ACCEPTED is not an authorization, and that a stored record is not a
    grant (§13)
11  THE PRODUCER CLAIM ON THE RECORD IS AUTHENTICATED TO WHATEVER STANDARD AI-05
    HAS DEFINED under AI15-OPEN-1 (§9.2), that standard is implemented, and tests
    show it holds. Registry membership is not this condition (§4.3). While
    WHILE AI15-OPEN-1 IS OPEN, CONDITION 11 IS UNSATISFIED — AND THE CONSEQUENCE
    IS NOT ONLY THAT THE SEAM MAY NOT BE CALLED CONNECTED. §15.2 STEP 0b gates
    the WRITE, so no production call site that can execute admission may exist
    either (§17.2b). Condition 11 is a condition on the RECORD, and it is
    discharged BEFORE the record exists, not after it.
12  the change states, where a reader will meet it, WHAT AN ACCEPTED DOES NOT
    ESTABLISH: that a record was admitted is evidence of a well-formed CLAIM made
    under a registered token, not proof of the fact the claim describes. The
    connection of a writer is the moment this is easiest to lose, so the change
    that connects one carries the sentence.
```

```text
PROPOSED: this list is AI-15-A's, and it is the class most likely to be amended.
FROZEN: items 1, 2, 5, 8, 10 and 11 are NOT negotiable:
           1, 2      restate AI-14 §2's CONNECTED definition
           5         restates AI-05 §6.5/§6.6
           8         restates §22.1's outcome rule, both directions
           10, 11    restate AI-14 §4.2 rule 4 and §4.3's registry/authentication
                     split. Item 11 is the one a wiring change is most likely to
                     assume away, which is why it is stated as a condition rather
                     than as a caveat.
FROZEN: items 3, 4, 6, 7, 9 and 12 are AI-15-A's framing of what those
        restatements require of a call site. They may be amended (§19). Items 1,
        2, 5, 8, 10 and 11 may not be removed; they may only be restated more
        precisely.
```

### 8.4 The intermediate states, so a partial result is not over-reported

```text
SEAM                    nothing on one side.
IMPLEMENTED BUT NOT     both sides exist; only tests, or nothing, call it.
  CONNECTED
CONNECTED               §8.3's twelve conditions hold, INCLUDING condition 11.
                        A path meeting conditions 1-10 while AI15-OPEN-1 is OPEN is
                        NOT CONNECTED — and it is not a reportable state either:
                        §15.2 STEP 0b forbids the writer from existing, so this
                        case MUST NOT ARISE. If it does arise, it is a violation
                        of this document, not a fourth classification.
```

```text
FROZEN: AI-15-B MUST NOT report an intermediate state as CONNECTED, and MUST NOT
        report a state that satisfies items 1-10 but fails 11 or 12. Items 10-12
        are the ones a "successful" implementation is most likely to skip: 10
        keeps the Evidence layer from becoming an authority, 11 keeps it from
        asserting a producer it cannot vouch for, and 12 keeps a reader from
        taking an admitted claim for a proven fact.
FROZEN: and item 11 is not a labelling rule. A state that satisfies 1-10 while
        AI15-OPEN-1 is OPEN has a LIVE WRITER — which §15.2 STEP 0b forbids — so
        the remedy is not a better label. It is that the writer does not exist.
        The classification describes a seam; STEP 0b constrains a RECORD, and a
        record that was stored stays stored (§6.1).
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
        daemon, NO credential path and NO authentication API. None exists in the
        repository for this purpose and AI-15 does not invent one.
FROZEN: AUTHENTICATION IS NOT AUTHORIZATION, AND THIS DOCUMENT MUST NOT BE READ
        AS SAYING SO IN EITHER DIRECTION. A mechanism that ESTABLISHES who
        submitted a record is a TRUST mechanism, not a permission. §9.5 states
        the rule and AI-14 §4.1's matrix is unchanged by it.
FROZEN: whether AI-05's eventual answer to AI15-OPEN-1 involves a new trust root
        is AI-05's determination, made under AI-05's amendment rule and approved
        by AI-05's owner. AI-15 neither presupposes one nor forbids one. What
        AI-15 fixes is narrower and stated in §17.4: AI-15 does not BUILD one.
```

### 9.2 Threat 1 — component A writes a record claiming to be component B

```text
STATUS TODAY: THE GAP IS OPEN, AND NO CALLER EXISTS. THREE SEPARATE FACTS, AND
THEY MUST NOT BE MERGED INTO ONE.

  the API        admit() takes no submitter identity (§4.3). ANY code that can
                 import `plugins.evidence` and call `admit` can submit
                 producer="ai-04" with a well-formed DECISION. This is a property
                 of the API, and it does not depend on what is in the tree today.
  the tree       at main @ 37f354c, no production module imports the package
                 outside AI-06's type-only projection, and no production caller
                 of admission exists (§3.1-§3.3). This is a RECORDED negative
                 finding about the repository, and it is the weakest of the three:
                 it says what HAS been written, not what CAN run.
  the check      a change adding such a caller TO ONE OF THE FIVE DIRECTORIES
                 THAT CARRY A RULE would fail the BUILD-TIME checks in §3.4.
                 That is a constraint on what may be MERGED. It is NOT global:
                 §3.4 names the packages that have no rule, and a caller placed
                 there would be refused by its phase's contract rather than by
                 a check.
  NOT claimed    that any of the three makes the API unreachable at RUNTIME.
                 There is no runtime sandbox and no runtime authentication here.
                 Committed code that imported the package WOULD RUN (§3.4); the
                 constraint is that this repository will not merge it, and
                 §15.2 STEP 0b says it must not be created in the first place.

AI15-OPEN-1  PRODUCER AUTHENTICITY — how is a producer claim ESTABLISHED, as
             against merely well-formed?

        OWNER            AI-05. It owns §6.5, §6.6 and §7. The question is a
                         question about AI-05's admission contract, and neither
                         AI-15 nor any other phase may answer it for AI-05.
        STATUS           OPEN. Not a TODO for AI-15-B.
        WHAT IS MISSING  a decision about HOW a claim is established. §6.5/§6.6
                         answer "is this token the registered one for this kind
                         and family"; nothing answers "did the named component
                         submit it".
        WHAT AI-15 DOES NOT DO   it does not add a token, a check, a hook, a
                         signature, a key, a registry service or a "producer
                         verification" seam. §17.4 forbids all of them.
        HOW THE QUESTION IS ANSWERED   that is AI-05's design act, and AI-15
                         states no preference among mechanisms. §9.5 fixes only
                         that whatever AI-05 chooses MUST NOT enter the authority
                         matrix.
        WHAT KEEPS IT FROM MATTERING TODAY  the RECORDED finding in §3.1-§3.3 — no
                         production caller exists at this baseline — together
                         with §15.2 STEP 0b, which forbids creating one while
                         this item is OPEN. Neither is a runtime barrier.
        STATUS, STATED PRECISELY  AI15-OPEN-1 is UNSOLVED, NOT UNREACHABLE. The
                         API accepts a caller-supplied producer claim today, and
                         the only thing between that and a stored record is that
                         nobody has written the caller. "No caller exists" is a
                         fact about the tree; it is not a property that keeps the
                         claim safe.
        WHY IT IS STILL A B5 PREREQUISITE  because the first caller to be written
                         would run — which is what B5 is. §15.2 STEP 0b gates that
                         write, and §8.3 condition 11 carries it into the
                         CONNECTED gate.
```

```text
AI15-OPEN-1 IS NOT AI-11 §21.1's OPEN-1. They share an owner and nothing else.

    AI-11 §21.1 OPEN-1   WHICH PRODUCERS EXIST
                         no §6.5 row exists for AI-08 / AI-10 / AI-11 / AI-13, so
                         no record from those phases can be admitted at all.
                         Resolving it means ADMITTING A TOKEN.  (§15.3)

    AI15-OPEN-1          WHETHER A PRODUCER CLAIM IS TRUSTWORTHY
                         the rows that DO exist accept a caller-supplied string.
                         Resolving it means DECIDING HOW A CLAIM IS ESTABLISHED.
                         (§4.3, §8.3 condition 11)

    ADMITTING A TOKEN DOES NOT RESOLVE AI15-OPEN-1. A newly admitted `ai-11` row
    would accept a caller-supplied "ai-11" for exactly the reason the `ai-06` row
    accepts a caller-supplied "ai-06": `g_registered` compares the string to the
    registry and compares nothing else (models.py:193).

    RESOLVING AI15-OPEN-1 DOES NOT RESOLVE AI-11 §21.1 OPEN-1. A claim established
    to whatever standard AI-05 sets is still REFUSED by `g_registered` when the
    phase has no row for that kind and family.

    The two are therefore independent, neither blocks the other's resolution, and
    closing one MUST NOT be reported as progress on the other.

FROZEN: AI-15 MUST NOT close, weaken, rename or claim to have resolved AI-11
        §21.1's OPEN-1. §15.1 keeps the questions apart; §16 keeps BOTH open.
```

### 9.3 Threat 2 — a caller fills in any producer token it likes

```text
STATUS TODAY: THE FIELD IS CALLER-SUPPLIED AND IS CHECKED ONLY FOR REGISTRATION.

  `provenance.producer` is a Class 3, G-REGISTERED leaf in §15.2's field table
  (plugins/evidence/canonical.py:104), validated by g_text at
  plugins/evidence/models.py:1211 and by the registry at models.py:193.
  It is caller-supplied, and AI-05 §14.10's C1-R06 opaque-token rule scans it.

RECORDED: a value "looking right" is EXACTLY the condition that makes it pass.
          `ai-04` passes because it IS the registered token for a DECISION, not
          because anything verified who wrote it.
```

```text
FROZEN: AI-15-A states this rather than glossing it, because a later reader could
        otherwise take §6.5/§6.6's mechanical checks for an authenticity check.
        They are a REGISTRY check. §4.3 draws the line, §9.2 names the owner and
        the condition, and §9.5 keeps the question out of the authority matrix.
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
RECORDED: the precondition this clause used to carry is satisfied. It required
        AI15-OPEN-2 to be answered first, because §9.4 presumes the forwarder is not
        the producer; AI-05 Amendment 4 answered it with READING A, under which a
        forwarder that is not the producer is exactly what is contemplated (§5.3).
        Under READING B there would have been no legal forwarder and this clause
        would have been inert. The clause is therefore LIVE as written: its
        immutability rules are unchanged, and satisfying the precondition does not
        authorize a forwarder to exist (§15.2 STEP 0b, §17.2b).
```

### 9.5 Authentication is not authorization

```text
FROZEN: an identity-authentication or provenance-verification mechanism is NOT a
        permission mechanism, and the two MUST NOT be conflated IN EITHER
        DIRECTION:
            "it authenticates"          MUST NOT be read as "it authorizes"
            "it is not authorization"   MUST NOT be read as "authentication
                                         mechanisms are forbidden"
```

```text
FROZEN: THE SECOND DIRECTION IS THE ONE THIS CLAUSE EXISTS FOR. AI-15 does not
        hold that a trust mechanism would be an authority, and MUST NOT be read as
        refusing AI15-OPEN-1's resolution on the ground that it would grant one.
        Whether a specific mechanism AI-05 might propose would constitute a new
        authority is decided by AI-14 §4.1's matrix and by AI-05's own amendment.
        Not by this document.
FROZEN: the mechanism's DESIGN is AI-05's to propose and AI-05's owner to approve.
        AI-15 states no preference among signatures, keys, registry services,
        capability handles or any other shape, and MUST NOT be cited for or
        against one.
```

```text
FROZEN: REGARDLESS OF HOW AI15-OPEN-1 IS RESOLVED, AND WHATEVER SHAPE THE
        MECHANISM TAKES:
            AI-14 §4.1's authority matrix MUST NOT change
            no new authorizing subject may appear
            Guard MUST remain the only component with an AUTHORIZES entry
            an AUTHENTICATED producer MUST NOT thereby hold a permission
            an AUTHENTICATED record MUST NOT thereby become a grant
            an authentication failure MUST NOT be reported as a Guard DENY, and a
              Guard ALLOW MUST NOT be reported as an authentication
```

```text
FROZEN: a resolution that changed the matrix would be an AI-14 amendment and an
        AI-04 question, not an AI-05 one, and AI-15 MUST NOT propose it. If AI-05's
        chosen mechanism appeared to require one, that is a cross-phase dependency
        to be raised with the owners — not something AI-15-B resolves by wiring.
FROZEN: §13 states the same rule from the authority side, and the two sections are
        one rule. Where they appear to differ, §13's matrix is the authority.
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
        steps 1-13 entirely, and `StagedEvidenceStore.write` (store.py:270) IS
        CALLABLE — so this is a rule, not a build-time check, and nothing in the
        repository refuses it. It is stated as a rule and the reviewer is told it
        is one.
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
FROZEN: AI-15 NORMALIZES NO EXCEPTION INTO AN OUTCOME, AND NORMALIZES NO OUTCOME
        INTO AN EXCEPTION. The two channels are different and stay different:
            a normal admission result arrives as an AdmissionResult VALUE
            an API misuse stays a raised exception (§11.2)
FROZEN: `admit` catches `EvidenceError` only (admission.py:203). Every other
        exception propagates, and AI-15-B MUST let it. Wrapping it — in an
        AdmissionResult, in a REJECTED, in an UNAVAILABLE, in a new reason_code —
        would put a caller's programming error into the same channel as a record's
        verdict, and a log could no longer tell them apart.
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
    one of them).

    FROZEN: AI-15-B MUST NOT wrap it in an AdmissionResult, MUST NOT map it to
            REJECTED or UNAVAILABLE, and MUST NOT mint a reason_code for it. It is
            outside the outcome vocabulary, and putting it inside would make "the
            record was refused" and "the caller passed the wrong store"
            indistinguishable to whoever reads the failure later.
    FROZEN: the same rule governs every other non-EvidenceError exception. It
            propagates, and it MUST keep propagating.
    FROZEN: this is NOT a gap to be closed by AI-15. `admit_to_store`'s TypeError
            is the API telling a caller it used the wrong tier; the fix is the
            caller's, and no outcome value makes a misused store into a verdict.
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

### 11.4 Failure propagation is not authorization

```text
FROZEN: A CALLER MAY ACT ON AN ADMISSION OUTCOME. Treating a REJECTED or an
        UNAVAILABLE as the failure of the CALLER'S OWN operation — returning a
        non-success result, stopping, or declining to run a later step that
        depended on the record existing — is ERROR PROPAGATION. It is not the
        exercise of an authority, and AI-15 does not forbid it.
FROZEN: this document does NOT require a caller to continue, to swallow the
        outcome, or to report success. §11.3 forbids converting a failure INTO a
        success; it does not forbid a caller from treating a failure AS a
        failure.
FROZEN: AI-15 DECIDES NO PHASE'S FAILURE POLICY. Whether a workflow abandons a
        run, whether a benchmark records a task as not-run, whether an agent
        execution returns a non-success outcome, whether a review case closes,
        and whether a composition returns a partial result are each that phase's
        own contract, frozen elsewhere. AI-15 neither restates nor amends any of
        them (§1.3).
```

```text
FROZEN: WHAT AI-15 DOES FIX IS THE BOUNDARY, AND IT HAS FOUR EDGES:
            the outcome is OBSERVABLE to the caller, as a value (§11.1)
            it is NEVER DISGUISED AS SUCCESS — an unpersisted record MUST NOT be
              reported as durable Evidence, and a REJECTED or UNAVAILABLE MUST
              NOT be rendered as an ACCEPTED, a pass or a completed step
            it is NEVER RE-READ AS A PERMISSION (§13, below)
            an API misuse is NOT an outcome and MUST NOT be dressed as one (§11.2)
        Inside those four edges the caller's policy is the caller's.
FROZEN: AND THE PROPAGATION GRANTS NOTHING IN EITHER DIRECTION. No failure path
        produces a Guard ALLOW, a permission, a capability promotion, a
        model-selection decision or a workflow approval; and neither does any
        SUCCESS path (§13.1). A caller stopping because a write failed is not
        Evidence withholding a permission, and a caller continuing because a
        write succeeded is not Evidence granting one. The two directions are the
        same rule.
FROZEN: concluding that "the caller may not fail the operation" would itself be
        an authority claim — it would let Evidence dictate another phase's control
        flow. AI-15 makes no such claim, and an earlier revision of this document
        made one; it is WITHDRAWN.
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
        AI-14 §4.2 rule 5; AI-11 §8.5, AI-11 §23.
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
FROZEN: §9.5 states the same boundary from the TRUST side, and the two are one
        rule: an authenticated producer gains no permission, and no mechanism that
        establishes who wrote a record may appear in §13.1's matrix. Where this
        section and §9.5 appear to differ, THIS section's matrix is the authority.
FROZEN: §11.4 states the same boundary from the FAILURE side, and it runs in both
        directions: a REJECTED or an UNAVAILABLE is not a permission withheld, and
        an ACCEPTED is not a permission granted. A caller that stops on a failed
        write has stopped; it has not been authorized to stop, and it has not been
        denied anything by Evidence.
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
AI15-OPEN-3  whether `DecisionRecord.evidence_ref` should ever carry an AI-05 id.
        OWNER: AI-04. Not AI-15, and not AI-15-B.
```

---

## 14. Cross-phase dependency audit

Legend: **contract** = what is frozen · **code** = what exists · **call site** = a
non-test caller · **evidence** = re-checkable observation.

### 14.1 Summary table

| phase | contract says | code exists | non-test call site | evidence proves CONNECTED | AI-15 depends on an amendment? |
| --- | --- | --- | --- | --- | --- |
| AI-05 | owns Evidence; §6.5 6 rows/4 tokens | yes, complete | **no external caller** | **no** | no — but §9.2 AI15-OPEN-1 is AI-05's |
| AI-06 | §15.1 projects, caller submits | `evidence.py` | **no** | **no** | **NO — §5.3 AI15-OPEN-2 was ANSWERED (READING A) by AI-05 Amendment 4; no §6.5 amendment is needed for this path** |
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
           none outstanding for the semantic question. §5.3's AI15-OPEN-2 was
           answered by AI-05 Amendment 4 (READING A) and is CLOSED (§16.1).
           §9.2's AI15-OPEN-1 remains OPEN: AI-05 still owes a producer
           authentication standard, implemented and tested, and §15.2 STEP 0b
           gates the WRITE on it. Neither is scheduled by AI-15.
```

### 14.3 AI-06

```text
contract   §15.1 FROZEN: AI-06 does not call admission; it projects, and "the
           caller submits it". §15.2 FROZEN: one invocation -> one ToolResult ->
           one ToolCall. AI-06 §15.7: both AI-06 §6.5 rows are real.
code       plugins/security_tools/evidence.py — implemented, 2 functions.
call site  NONE. `tool_call_for` and `execution_payload_for` are called only by
           tests/security_tools/test_evidence_and_families.py.
           NO LAYER 0 RULE COVERS THIS PACKAGE (§3.4). Its import of two AI-05
           payload types is permitted by AI-06 §15.1/§15.2, and a change adding
           an admission caller here would be refused by AI-06's contract and by
           review — NOT by a build-time check.
evidence   AI-14 §5.1 classifies the AI-06 -> AI-05 row IMPLEMENTED BUT NOT
           CONNECTED, and Appendix A repeats it.
AI-15 dependency
           NO AI-05 AMENDMENT, now that the reading is settled. AI-05 Amendment 4
           chose READING A (§5.3), under which AI-06's seam needs a CALLER and no
           §6.5 amendment: its rows already exist and AI-06 §15.1 already names a
           caller. Had it chosen READING B, this path would have needed one.
           FROZEN: this changes nothing about whether the caller EXISTS. The
           canonical gap is unchanged — `tool_call_for` and
           `execution_payload_for` still have no production caller, and §2.2
           keeps that an IMPLEMENTED BUT NOT CONNECTED row, not a CONNECTED one.
           AI-15 does not implement the caller, and §17 governs whoever does.
```

### 14.4 AI-08

```text
contract   §13.1 FROZEN: "AI-08 v1 therefore writes NO AI-05 EvidenceRecord of any
           kind." §13.2 FROZEN: the shape for the day it is admissible
           (producer_type service, actor.type agent, actor.id the AgentId), and the
           token itself DEFERRED. §13.3 FROZEN: no adjudication layer of its own.
code       agents/result.py — AgentResult is run data with NO producer field
           (agents/result.py:210-214, "is no AI-05 producer field here (§10.1)").
call site  NONE at main; a change adding one would fail layer0 :1549 (a
           build-time check, not a runtime block — §3.4).
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
           AI-11 §8.5: what a verdict never means. AI-11 §23: non-goals.
code       benchmarks/ imports no plugins.evidence — enforced at layer0 :2465.
call site  NONE.
evidence   the model-measurement campaign is BLOCKED (AI-11 Layer 4, AI-12 §6).
AI-15 dependency
           none directly. §21.1's OPEN-1 is §15.3's subject and its owner is AI-05.
```

### 14.7 AI-13

```text
contract   AI-13 §16 FROZEN: writes none and registers no producer. AI-13 §13.5:
           an approval
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
call site  NONE at main; a change adding one would fail layer0 :3241 and the
           AST test at tests/composition/test_composition_boundaries.py:151
           (build-time checks, not a runtime block — §3.4).
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

### 15.1 The four questions, kept apart

```text
1  AI-15's own contract       this document. Frozen by its merge (§19).
2  the AI-05 producer-token   WHICH PRODUCERS EXIST. Whether a token may be
     amendment                 admitted, for whom, and on what evidence. This is
                               AI-11 §21.1's OPEN-1. Owned by AI-05.
3  producer AUTHENTICITY      WHETHER A PRODUCER CLAIM IS TRUSTWORTHY, for the
                               rows that already exist. This is AI15-OPEN-1 (§9.2).
                               Owned by AI-05.
4  the AI-11 reconciliation   whether AI-05 §28's "AI-11 CONSUMES Evidence" is
                               satisfied. Owned by AI-05, recorded by AI-11.
```

```text
FROZEN: these are FOUR different things and AI-15 MUST NOT merge them.
FROZEN: items 2 and 3 are independent in both directions, and §9.2 works the
        argument: admitting a token does not make a claim trustworthy, and making
        a claim trustworthy does not admit a token. Closing either MUST NOT be
        reported as progress on the other.
FROZEN: item 4 is reconciled only when item 2 lands. It is NOT reconciled by
        item 3, and NOT by "AI-15-B is done" — that inference is the one this
        clause exists to forbid.
```

### 15.2 AI-14 amendment — the ordering, and why the naive order is circular

```text
THE CIRCULARITY, STATED FIRST

    A plan that says all three of these at once is NOT EXECUTABLE:

        (A)  AI-15-B MUST NOT START until an AI-14 amendment lands
        (B)  that amendment must record B5 as CONNECTED
        (C)  CONNECTED requires a real non-test call site (§8.3 condition 1)

    (A)+(B) require a call site BEFORE the work that creates it. (C) forbids
    recording CONNECTED without one. The three cannot all hold.

    An earlier revision of this document contained exactly that plan. It is
    WITHDRAWN, and the order below replaces it.
```

```text
THE RESOLUTION — SPLIT THE AMENDMENT BY WHAT IT CHANGES

    AI-14 makes TWO different kinds of statement about this edge, and they are
    separable:

        the RULE that forbids the edge      §13's identifier refusal;
                                            scripts/ci/layer0_policy.py:3241;
                                            the two composition assertions
        the CLASSIFICATION of the edge      §5.1; §22.1 B5; Appendix A

    Removing the RULE comes first and does NOT record CONNECTED. Recording
    CONNECTED comes last and comes WITH the call site. Nothing in between claims a
    connection that does not exist yet.
```

```text
THE ORDER — each step names its owner, its precondition and its output

  STEP 0a  AI-05 answers AI15-OPEN-2 (§5.3): which reading of AI-05 §7's "WROTE"
           governs
           when the submitter is not the named component.
           OWNER         AI-05.
           PRECONDITION  none.
           OUTPUT        a reading, or an explicit refusal to choose.
           STATUS        ANSWERED. AI-05 Amendment 4 chose READING A and is IN
                         FORCE as of its merge (PR #80,
                         03d42681cb8b2110773654822655117daea44ad5). The output
                         above was delivered by the OWNER, in the owner's
                         contract, under the owner's amendment rule. AI-15 records
                         it; AI-15 did not produce it (§19, Amendment 1).
           GATES         STEP 1 — AND THIS GATE IS NOW SATISFIED. §7.3's T2 is legal
                         under the chosen reading; under
                         READING B there would have been no legal forwarder and
                         STEP 1 would have had nothing to authorize. SATISFYING
                         THE GATE IS NOT STEP 1: no AI-14 authorization has been
                         made, and this document does not make one.

  STEP 0b  AI-05 answers AI15-OPEN-1 (§9.2, §9.5): how a producer claim is
           ESTABLISHED to AI-05 §7's standard for "the component that WROTE".
           OWNER         AI-05.
           PRECONDITION  none. May run in parallel with STEP 1, and with the
                         non-writing preparation §17.2c allows.
           OUTPUT        a mechanism, PLUS its implementation and tests — not a
                         prose decision alone, because §8.3 condition 11 requires
                         that the standard be implemented and shown to hold.
           GATES         STEP 2 AND STEP 3. BOTH.
           FROZEN: STEP 0b GATES THE WRITE, NOT ONLY THE LABEL. No production,
                   non-test call site that can actually execute §30 admission and
                   persist an EvidenceRecord may be created, merged or run before
                   STEP 0b is complete. A writer that runs is a writer that can
                   store a producer claim nobody established, and whether the
                   resulting seam is later LABELLED CONNECTED does not un-store
                   the record.
           FROZEN: AN EARLIER REVISION OF THIS DOCUMENT GATED STEP 3 ONLY. That
                   permitted a live writer to admit and persist records while
                   §8.3 condition 11 was unsatisfied, on the reasoning that the
                   seam would simply not be called CONNECTED. It is WITHDRAWN:
                   the classification is a statement about the seam, and Step 0b
                   is a condition on the RECORD.
           FROZEN: what MAY proceed before STEP 0b is §17.2c's list, and every
                   item on it MUST be unable to execute admission.

  STEP 1   AI-14 amendment #1 — AUTHORIZATION. It changes the RULES, not the
           classification.
               §22.1 B5's "blocked by" clause
               §13's `producer_token` identifier refusal, where it reaches the
                 SUBMITTING caller rather than the composition
               §5.1's "by rule" annotation on the composition -> Evidence row
               §25's amendment log
           and, in the same change:
               scripts/ci/layer0_policy.py:3241   AI14_FORBIDDEN_IMPORTS
               tests/composition/test_composition_boundaries.py:151-176
               tests/composition/test_composition_boundaries.py:178-191
           OWNER         AI-14.
           PRECONDITION  STEP 0a — SATISFIED by AI-05 Amendment 4 (§5.3). No AI-14
                         amendment has been made; a met precondition is what
                         UNBLOCKS beginning one, and AI-14's owner begins it,
                         not AI-15 (§19, Amendment 1).
           FROZEN: THIS AMENDMENT MUST NOT RECORD B5 AS CONNECTED. There is no
                   call site yet, §8.3 condition 1 is unsatisfied, and recording
                   CONNECTED here would reproduce the (A)+(B)+(C) contradiction
                   in a new place.
           FROZEN: after STEP 1, B5's classification remains NOT CONNECTED. AI-14
                   §2 already has a member that expresses this without a new one:
                   the row stays IMPLEMENTED BUT NOT CONNECTED and loses its
                   "by rule" annotation. IF AI-14's owner judges that its
                   vocabulary CANNOT express "authorized but not yet connected",
                   that judgement is AI-14's to make and to amend for under AI-14
                   §24. AI-15 MUST NOT invent a classification member, and B5
                   stays BLOCKED until AI-14 resolves it.

  STEP 2   the IMPLEMENTATION. A real, non-test call site is created, meeting
           §8.3's conditions. This is the first step at which a production writer
           may EXIST, let alone run.
           OWNER         the implementing party, for its own runtime/composition
                         part. Per §7.3 that is the composition submitting an
                         OWNER-AUTHORED record, so the owner phase authors the
                         claim and the composition submits it.
           PRECONDITION  STEP 0a AND STEP 0b AND STEP 1. All three. STEP 0a is
                         satisfied; STEP 0b and STEP 1 are NOT.
           FROZEN: AI-15-B is ONE possible implementer of this step and is NOT
                   the only one. §17.5 fixes what the implementer may and may not
                   do, whoever it turns out to be.
           FROZEN: STEP 2 AND STEP 3 ARE DELIVERED AS ONE CHANGE, IN ONE REVIEW,
                   MERGED ONCE. AI-14 §22.1 requires the classification update to
                   happen in the SAME change that connects the seam. WHAT §22.1
                   DOES NOT DO IS PRESCRIBE A COMMIT COUNT, and AI-15 MUST NOT
                   claim that it does: the requirement here is about the MERGE
                   and the REVIEW, not about how either author arranges their
                   commits on the way there.
           FROZEN: WHAT IS FORBIDDEN IS SPLITTING THE MERGE. A runtime call site
                   merged while the classification is absent — with the
                   classification promised as a follow-up, deferred to a later
                   PR, or carried by a stacked PR merged separately — does NOT
                   satisfy §22.1, however many or few commits each half contains
                   and however close together the merges land. The seam would be
                   connected in the tree while the contract still says it does
                   not exist, and that is the state §22.1 exists to prevent.
           FROZEN: "THE SAME CHANGE" DOES NOT MEAN "ONE AUTHOR". The change has
                   two parts with two owners:
                       the runtime/composition part   the implementing party
                       the AI-14 part                 AI-14's owner — §5.1,
                                                      §22.1 B5, Appendix A,
                                                      §25, layer0 :3241, and
                                                      the two composition
                                                      assertions in tests/
                   AI-15-B MUST NOT author the AI-14 part. The AI-14 owner MUST
                   personally make it, or formally submit and approve it, under
                   AI-14 §24 and that phase's own process.
           FROZEN: IF THE REPOSITORY'S WORKFLOW CANNOT DELIVER A JOINT CHANGE OF
                   THAT SHAPE — one in which AI-14's owner authors or formally
                   approves AI-14's own parts while the implementer authors the
                   runtime part, merged as ONE change — THEN B5 AND AI-15-B STAY
                   BLOCKED. The missing decision is AI-14's: HOW IS AN AI-14
                   AMENDMENT DELIVERED ALONGSIDE ANOTHER PARTY'S RUNTIME CHANGE,
                   WITH AI-14 RETAINING OWNERSHIP? AI-15 MUST NOT invent one, MUST
                   NOT author AI-14's parts to work around it, and MUST NOT treat
                   a separately merged AI-14 part as satisfying AI-14 §22.1 —
                   whatever it was promised as, and however close together the
                   merges land. §16.2 carries this as a live blocker with its owner.

  STEP 3   AI-14 amendment #2 — CLASSIFICATION, in the SAME change as STEP 2's
           call site.
               §5.1        -> CONNECTED, naming the call site by file and line
               Appendix A  -> CONNECTED, naming the call site
               §22.1 B5's item status
               §25's amendment log
           OWNER         AI-14, for the AI-14 parts. See STEP 2's joint-change
                         rule: the two parts merge as one change with two authors.
           PRECONDITION  STEP 0a AND STEP 0b AND STEP 1 AND STEP 2. All four,
                         with STEP 2's call site in the SAME merged change.
                         STEP 0a is satisfied; the other three are NOT.
           FROZEN: STEP 3 IS THE ONLY STEP THAT MAY USE THE WORD CONNECTED ABOUT
                   THIS EDGE, AND IT IS THE ONLY STEP THAT MAY WRITE IT DOWN.
                   §5.1, Appendix A, §22.1 B5 and §25 move together, in the same
                   change as the call site, and none of them moves earlier.
           FROZEN: CONNECTED IS RECORDED ONLY WHEN EVERY §8.3 CONDITION HOLDS —
                   condition 11 included, which STEP 0b supplies. A caveated
                   CONNECTED is a CONNECTED claim, and §8.4 forbids it.
           FROZEN: if STEP 3 cannot be delivered in the SAME CHANGE as STEP 2 by
                   an owner-approved mechanism, STEP 2 MUST NOT RUN EITHER. That
                   is §16.2's joint-delivery blocker, and it is a decision AI-14's
                   owner makes, not a sequencing problem an implementer solves.
                   "Same change" means the same review and the same merge, not a
                   commit count (§17.2d).
```

```text
FROZEN: AI-14 retains ownership of its own topology, its Layer 0 boundary, its
        CONNECTED/SEAM classification and its amendment procedure. AI-15 owns
        neither STEP 1 nor STEP 3.
FROZEN: AI-15-B MUST NOT modify
        docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md. Authoring STEP 1 or
        STEP 3 is AI-14's act. AI-15-B may at most prepare a PROPOSAL for AI-14's
        owner, which that owner makes or declines under AI-14 §24. An AI-15-B
        change that carries an AI-14 amendment is a bypass of the owner rule and
        MUST NOT be merged.
FROZEN: AI-15-B MUST NOT reach the call site by narrowing layer0 :3241 itself, by
        deleting or weakening the two composition assertions, or by adding a
        test-only path. STEP 1 is the only route to a production call site, and it
        is AI-14's.
FROZEN: A PREREQUISITE AMENDMENT MUST NOT ASSERT THE OUTCOME OF THE WORK IT
        PRECEDES. That is the general form of (A)+(B)+(C), and it governs every
        amendment in this order: STEP 1 authorizes, STEP 3 classifies, and only
        STEP 3 may use the word CONNECTED about this edge.
```

```text
IF THE ORDER CANNOT BE SATISFIED

    B5 and AI-15-B stay BLOCKED, and this document NAMES the missing owner
    decision rather than inventing a rule. The order fails in exactly three ways:

        STEP 0b produces no decision            missing owner decision: AI-05
                                                (STEP 0a was answered)
        AI-14 declines STEP 1, or judges its    missing owner decision: AI-14
          vocabulary cannot express
          "authorized but not yet connected"
        no party accepts STEP 2                 missing owner decision: AI-14's,
                                                since designating it is AI-14's
                                                under STEP 1

    In any of those:
        B5        = BLOCKED
        AI-15-B   = NOT STARTED
    and AI-15 MUST NOT close the gap by amending an earlier contract, by adding a
    producer token, by narrowing another phase's Layer 0 boundary, or by recording
    CONNECTED ahead of the evidence. §16.2 carries these as live blockers.
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
        admits. It does NOT by itself unblock B5, because §15.2's ordered steps
        and §3.4's structural blocks are independent of it.
```

```text
AI-05'S SECOND, SEPARATE DEPENDENCY — PRODUCER AUTHENTICITY

    §15.1 item 2 (the token amendment) and item 3 (authenticity) are different
    questions with the same owner. B5 needs BOTH, and they are NOT substitutes:

        the token amendment        WHICH PRODUCERS EXIST
                                   gates records from phases with no §6.5 row
                                   (§14.3-§14.8), and reconciles AI-11 §21.1's
                                   OPEN-1
        AI15-OPEN-1                WHETHER A PRODUCER CLAIM IS TRUSTWORTHY
                                   gates §8.3 condition 11 — and through it the
                                   WRITE (§15.2 STEP 0b) — for EVERY record,
                                   including the four phases that already have
                                   a row

    RECORDED, and it is the reason they are not substitutes: the four phases that
    ALREADY hold a row currently satisfy `g_registered` on a caller-supplied
    string. Admitting a fifth token adds a fifth row that behaves the same way.
    The token amendment therefore cannot, by construction, satisfy condition 11.

    FROZEN: AI-15 MUST NOT present the token amendment as the whole of AI-05's
            dependency, and MUST NOT present AI15-OPEN-1 as a restatement of it.
    FROZEN: neither AI-05 item is owned, requested or scheduled here. ONE of the
            two is now ANSWERED: AI-05 Amendment 4 chose READING A, which closes
            §15.2's STEP 0a (§5.3, §19 Amendment 1). The second — producer
            AUTHENTICATION — remains §15.2's STEP 0b and remains OPEN; §16.2
            carries it, and only it, as an AI-05 blocker.
```

```text
THE POINT AI-15-A EXISTS TO MAKE

    "wait for the producer-token amendment" is NOT a sufficient plan for B5.

    A phase that wants a durable record needs THREE things, and the token is one:
        (i)   a §6.5 row                    AI-05 amendment
                                            (= AI-11 §21.1 OPEN-1)
        (ii)  its own contract permitting it to write
                                            THAT phase's amendment
              (AI-08 §13.1, AI-10 §13.2, AI-11 §21.1, AI-13 §16 each FROZEN the
               opposite today)
        (iii) its Layer 0 boundary narrowed
                                            layer0 :1549 / :1833 / :2465 / :2630
    and B5 additionally needs:
        (iv)  AI-14 §5.1 / §22.1 B5 / Appendix A     §15.2 STEP 1 and STEP 3
        (v)   layer0 :3241 narrowed                  §15.2 STEP 1
        (vi)  two assertions in tests/composition/   §15.2 STEP 1
        (vii) AI15-OPEN-2 answered, or no forwarder  §15.2 STEP 0a
              exists at all                          — SATISFIED,
                                                     ANSWERED AS READING A
        (viii) AI15-OPEN-1 answered, implemented     §15.2 STEP 0b
              AND tested                                  §8.3 condition 11

    Eight changes, four owners. AI-15 owns none of them, and (viii) is the one an
    implementation is most likely to assume away — a working call site does not
    make the producer claim behind it true.
    ONE OF THE EIGHT IS NOW DISCHARGED, and it is (vii): AI-05 Amendment 4
    answered AI15-OPEN-2. The list is kept at eight rather than renumbered, so
    the record of what the freeze found stays legible; the satisfied item is
    marked in place. The other seven stand.
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
AI15-OPEN-1  PRODUCER AUTHENTICITY — how is a producer claim ESTABLISHED, as
        against merely well-formed? (§4.3, §9.2, §9.5)
        OWNER   AI-05
        STATUS  OPEN. Not a TODO for AI-15-B.
        GATES   §15.2 STEP 2 AND STEP 3, and through them §8.3 condition 11.
                While it is OPEN, no production call site that can execute
                admission and persist a record may be created, merged or run
                (§17.2b), and B5 cannot satisfy the CONNECTED gate however many
                call sites exist.
        NOTE    UNSOLVED, NOT UNREACHABLE. The API accepts a caller-supplied
                producer claim today and nothing in the runtime prevents a call
                (§3.4). What holds it back is that no production caller exists at
                this baseline (a RECORDED negative finding, §3.1-§3.3) and that
                §15.2 STEP 0b forbids writing one. That is why it is a
                PREREQUISITE for B5's completion rather than a follow-up.
        NOT     AI-11 §21.1's OPEN-1. That one is WHICH PRODUCERS EXIST; this one
                is WHETHER A PRODUCER CLAIM IS TRUSTWORTHY. §9.2 works the
                independence argument in both directions, and §16.2 keeps both as
                separate blockers.

AI15-OPEN-2  which reading of AI-05 §7's "WROTE" governs when the submitter is not the
        named component?
        OWNER   AI-05
        STATUS  CLOSED / ANSWERED BY AI-05 AMENDMENT 4 — READING A (§5.3, §19
                Amendment 1). AI-05 made the decision, in its own contract,
                under its own amendment rule, and it is IN FORCE as of the merge
                of PR #80 (03d42681cb8b2110773654822655117daea44ad5).
        CLOSED  the AI-05 owner. NOT by AI-15, and NOT by an implementation
          BY    decision: AI-15 wrote no code and added no test asserting an
                outcome, which is what the clause below requires.
        FORMERLY the AI-06 path, and therefore the ONLY topology that could connect
          BLOCKED without a §6.5 amendment (§7.2 T2). That is no longer blocked;
                the seam still has no caller (§14.3), and having a legal
                topology is not having a connection.

AI15-OPEN-3  whether DecisionRecord.evidence_ref should ever carry an AI-05 id.
        OWNER   AI-04
        STATUS  OPEN. §13.4.

AI15-OPEN-4  a workflow-driven step's routing input.
        OWNER   AI-13 / AI-14
        STATUS  OPEN, recorded by AI-14 §22.1 B3 as "RECORDED, NOT RESOLVED".
        RELATIONSHIP TO AI-15  NONE. Listed so a reader does not attribute it here.
```

```text
FROZEN: AI15-OPEN-1, AI15-OPEN-3 and AI15-OPEN-4 MUST NOT be closed by an AI-15-B
        implementation decision (AI-14 §2: "An OPEN item MUST NOT be closed by an
        implementation decision").
RECORDED: AI15-OPEN-2 left this list the only way an OPEN item may leave it — its
        OWNER closed it, in the owner's contract, under the owner's amendment
        rule. The rule is unchanged and is not weakened by that: it names the
        three that remain, and a fourth could not be closed the way AI15-OPEN-2
        was unless a phase that owns the question made the decision.
FROZEN: AI15-OPEN-1 gates §15.2's STEP 0b directly, so an implementation that
        "resolves" it by choosing while building is the exact failure this clause
        names. AI15-OPEN-2's gate at STEP 0a is satisfied and no longer carries
        this exposure (§5.3).
```

### 16.2 BLOCKED

```text
B5 — composition -> Evidence
    BLOCKED. Six of the seven blockers below are live. ONE IS SATISFIED: row 0a,
    answered by AI-05 Amendment 4 (§5.3, §19 Amendment 1). Satisfying a blocker
    is NOT satisfying the item — B5 stays BLOCKED, and no seam is CONNECTED.

    order  blocker                                       owner                 gates
    -----  --------------------------------------------  --------------------  --------------
    0a     AI15-OPEN-2 answered — which reading of       AI-05                 STEP 1
           AI-05 §7's "WROTE" governs (§5.3)                                — SATISFIED.
                                                                               READING A.
                                                                               STEP 1 IS NOW
                                                                               UNBLOCKED, NOT
                                                                               MADE
    0b     AI15-OPEN-1 answered, implemented and         AI-05                 STEP 2 AND STEP 3
           tested — how a producer claim is                                    — GATES THE WRITE,
           established (§9.2)                                                  not only the label,
                                                                               and §8.3 cond. 11
    1      AI-14 amendment #1 (authorization) +          AI-14                 STEP 2
           layer0 :3241 + the two composition
           assertions (§15.2)
    1'     the §6.5 row and the own-contract clause      AI-05 + the phase     STEP 2, for any event
           for each phase whose facts are admitted                             but AI-06's
    2      a real non-test call site, §8.3 cond. 1       —                     STEP 3
    3      AI-14 amendment #2 (classification), in       AI-14                 CONNECTED
           the SAME change as the call site
    joint  an AI-14-OWNER-APPROVED delivery              AI-14                 STEP 2 AND STEP 3
           mechanism for a change with two authors:                            together, in
           AI-14's owner owns its CONTRACT, LAYER 0,                           ONE review and
           TESTS and CLASSIFICATION; the implementer                           ONE merge —
           owns the runtime part. ONE review, ONE                             NOT a commit
           merge (§15.2 STEP 2, §17.2d)                                     count
    FROZEN: 0b is INDEPENDENT of 1 and 1'. A call site that works and a token that
            is registered together satisfy no part of 0b (§15.3).
    FROZEN: 0b GATES STEP 2, SO IT GATES THE WRITE. Before it is complete, no
            production call site that can execute admission may exist (§15.2,
            §17.2b). Reporting the seam as NOT CONNECTED does not satisfy 0b: a
            live writer stores, and what it stored stays stored (§6.1).
    FROZEN: the classification step (3) MUST NOT run before 0b. A prerequisite
            amendment may not assert the outcome of the work it precedes (§15.2).
    FROZEN: the joint-delivery row is the blocker an implementer is most tempted
            to route around. Authoring AI-14's contract parts to avoid it is
            §15.2's owner-rule bypass and MUST NOT be merged.
    FROZEN: SATISFYING 0a MOVED NOTHING TO AI-15. STEP 1 is AI-14's to make and is
            not made; STEP 0b is AI-05's and is not answered. This document records
            that one owner answered one question, and it authorizes nothing.
    AI-15-B  MUST NOT START. §7.3, §17.

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
FORBIDDEN TO AI-15 — permanently, by this document (§1.3, §9.5):
    a record-level trust root, a signer, a signature, a key
    an authentication API, a provenance-verification seam, a producer check
    a producer-registry service, a daemon, a scheduler
    a new credential path or a new central authority
    NOTE: this list forbids AI-15 from BUILDING these. It does NOT declare that
    they may never exist, and it does NOT classify them as authorities. Whether
    AI-05's answer to AI15-OPEN-1 takes one of these shapes is AI-05's decision,
    subject only to §9.5's rule that it MUST NOT change AI-14 §4.1's matrix.
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

Nothing here is authorized until this document is merged AND §15.2's ordered
steps have reached the point each clause names. "§15.2 has landed" is not a
single event: STEP 1 authorizes and STEP 3 classifies, and no clause below may be
read as authorized by the wrong one.

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
        §15.2's steps are satisfied in order (§16.2), and the absence tests are
        what make a future connection a VISIBLE change rather than a silent one.
```

### 17.2 Blocked until §15.2 STEP 1

```text
BLOCKED (§15.2 STEP 1 — AI-14 owns all of it):
    any import of `plugins.evidence` from composition/
    narrowing layer0 :3241
    amending tests/composition/test_composition_boundaries.py:151, :178
    restating AI-14 §5.1 / §22.1 B5 / Appendix A
FROZEN: AI-15-B MUST NOT do any of these itself, and MUST NOT reach the same
        effect by another route — a second entry point for the evidence package,
        a helper that imports it on the composition's behalf, a test-only path, or
        a re-export that moves the import out of `composition/` while keeping the
        call. STEP 1 is the only route, and it is AI-14's act.

### 17.2b Blocked until §15.2 STEP 0b — this gate covers the WRITE

```text
BLOCKED until AI-05 has answered, implemented AND TESTED AI15-OPEN-1:
    ANY PRODUCTION CALL SITE that can actually execute `admit_to_store` against a
      real store, or that can otherwise cause an EvidenceRecord to be persisted.
      This is the substantive half of the gate, and it comes FIRST.
    wiring a production caller to `admit` or `admit_to_store`
    a composition-side helper, adapter, default or factory that reaches either
      entry point when the composition runs
    any production path on which a record is admitted and stored
AND, consequently, ALSO BLOCKED:
    any claim that B5 is CONNECTED  (§8.3 condition 11)
    any claim that an admitted record is PROVEN to come from the component its
      token names  (§6.1)
    any "provisional", "interim" or caveated CONNECTED — a caveated CONNECTED
      is a CONNECTED claim (§8.4)
```

```text
FROZEN: AN EARLIER REVISION OF THIS DOCUMENT SAID STEP 0b GATES ONLY THE
        CLASSIFICATION, AND THAT "a call site may exist, work and be tested while
        AI15-OPEN-1 is OPEN". THAT IS WITHDRAWN, and it was the defect this section
        now closes: a call site that works is a call site that STORES, and a seam
        reported as "not CONNECTED" does not un-store the record. The gate is on
        the WRITE because the condition is on the RECORD.
FROZEN: the ordering consequence is the whole point — STEP 0b is not a
        documentation prerequisite for a label. It is the precondition for the
        first record this architecture would ever durably keep.
```

### 17.2c What MAY proceed before §15.2 STEP 0b

```text
PERMITTED, and it is a real list rather than a courtesy — none of it can write:
    design drafts and interface sketches, in a document or a docstring
    interface analysis: what the call would look like, what it would need, what
      it would have to be handed
    offline scaffolding that CANNOT execute admission — type stubs, Protocol
      declarations with no implementor, an unused dataclass for a candidate shape
    test preparation: fixtures, builders and assertions written against a TEST
      double, in `tests/`, where AI-14 §2 already classifies them as not a seam
    read-only inspection of AI-05's existing surface
```

```text
FROZEN: THE DISTINGUISHING TEST IS CAPABILITY, NOT INTENT, PLACEMENT OR NAMING.
        Something is on the permitted list only if, AS COMMITTED, no configuration,
        no call and no parameterisation of it can cause `admit` or `admit_to_store`
        to run against a real store.
FROZEN: these do NOT qualify, whatever they are called:
    a helper in a production package that imports `plugins.evidence`, even if no
      caller exists yet — it is one call away, and the call is the thing gated
    an adapter or factory that returns a store, or that would accept one
    an example, a demo, or a default value that reaches admission
    a test-only path inside a production module
    "it is behind a flag" — a flag is a configuration, and configuration is not a
      gate (§15.2 STEP 0b is)
FROZEN: a permitted item MUST NOT be described as B5 progress, as a connected
        seam, or as STEP 2 started. §17.1's rule governs it too.
```

### 17.2d The joint STEP 2 + STEP 3 change, and who authors which part

```text
AI-14 §22.1 requires Appendix A's classification to be updated in the SAME change
that connects a seam. §15.2 STEP 2 requires the same. §15.2 also forbids
AI-15-B from authoring AI-14's contract parts. Both rules hold, and the
resulting shape is stated here so no implementer has to guess.
```

```text
THE CHANGE HAS TWO PARTS AND TWO AUTHORS

    part                      author                     content
    ------------------------  -------------------------  -----------------------
    runtime / composition     the implementing party     the call site, the
                                                         wiring, its own tests
    the AI-14 part            AI-14'S OWNER              its CONTRACT (§5.1,
                                                         §22.1 B5, Appendix A,
                                                         §25), its LAYER 0
                                                         constant (layer0 :3241),
                                                         its TEST assertions (the
                                                         two in tests/composition/)
                                                         and the resulting
                                                         classification

ORDER OF EVENTS
    STEP 1   AI-14's owner delivers the AUTHORIZATION change first — rules
             only, NEVER CONNECTED (§15.2 STEP 1)
    STEP 0a / 0b  AI-05's two answers, held before STEP 2 begins
    STEP 2+3 the runtime part and the AI-14 part merge as ONE change, with
             AI-14's owner authoring or formally approving AI-14's parts
```

```text
FROZEN: AI-15-B MUST NOT AUTHOR THE AI-14 PART. Meeting §22.1's same-change
        rule by editing AI-14's contract from an AI-15 branch is the owner-rule
        bypass §15.2 names, and MUST NOT be merged.
FROZEN: AI-14'S OWNER MUST PERSONALLY MAKE, OR FORMALLY SUBMIT AND APPROVE, its
        CONTRACT, its LAYER 0 CONSTANT, its TEST ASSERTIONS and its
        CLASSIFICATION parts — under AI-14 §24 and that phase's own process.
        Nothing in AI-15 may be read as transferring that ownership, delegating
        it, or waiving it for a joint change.
FROZEN: AI-15 DOES NOT DECIDE FOR AI-14'S OWNER — not whether the amendment is
        made, not how it is delivered, and not which of the two mechanisms below
        is used. Both are named as shapes AI-14's owner may choose; neither is
        chosen here:
            the AI-14 owner authors its parts in the SAME PR as the runtime part
            the AI-14 owner formally submits and approves its parts for that PR
              under AI-14's own process, without authoring them line by line
        A third shape — the AI-14 owner's parts merged separately — is the one
        §22.1 forbids, and is not an option.
FROZEN: THE REQUIREMENT IS ONE CHANGE, ONE REVIEW, ONE MERGE — AND IT IS NOT A
        COMMIT COUNT. AI-14 §22.1 freezes that the classification and Appendix A
        are updated in the same change that connects the seam. It does NOT say
        the parts must arrive as a single commit, and AI-15 MUST NOT attribute
        such a rule to it. How each author arranges their own commits is each
        author's business.
FROZEN: WHAT IS FORBIDDEN IS A SEPARATELY MERGED AI-14 PART. A runtime call site
        merged while the classification is absent does NOT satisfy §22.1 —
        whether the classification is promised as a follow-up, deferred to a
        later PR, or carried by a stacked PR merged separately, and however
        close together the merges land. "The classification will follow" is the
        exact case §22.1 was written to refuse.
FROZEN: IF NO OWNER-APPROVED DELIVERY MECHANISM EXISTS — one the repository's
        workflow can actually express, in which AI-14's owner authors or formally
        approves AI-14's parts while the implementer authors the runtime part,
        merged as one change — THEN B5 AND AI-15-B STAY BLOCKED. The missing
        decision is AI-14's: HOW IS AN AI-14 CONTRACT AMENDMENT DELIVERED
        ALONGSIDE ANOTHER PARTY'S RUNTIME CHANGE, WITH AI-14 RETAINING
        OWNERSHIP? §16.2 carries it as the joint-delivery blocker, and §15.2 STEP 3
        states the consequence: if the mechanism is absent, STEP 2 MUST NOT RUN
        EITHER.
FROZEN: AI-15 introduces NO new phase, NO new authority and NO new status
        vocabulary to make the joint change expressible. If the existing process
        cannot carry it, that is a blocked item with a named owner, not a reason
        to invent one.
```
```

### 17.3 Blocked until an AI-05 amendment — and only for some events

```text
BLOCKED until AI-05 admits a producer (§15.3, §15.2 STEP 1'):
    any record for a phase with NO §6.5 row — AI-08, AI-10, AI-11, AI-13, AI-14 —
      and each phase's own writer clause must also be amended, by that phase
NOT BLOCKED by a token, AND NO LONGER BLOCKED BY THE READING EITHER:
    the AI-06 rows exist and AI-06 §15.1 names a caller, so the AI-06 path needs no
      §6.5 amendment — and READING A is no longer an assumption AI-15 is proceeding
      on unilaterally: AI-05 Amendment 4 chose it (§5.3, §19 Amendment 1). Under
      READING B there would have been no legal forwarder at all.
    THIS REMOVES A CONTRACT OBSTACLE, NOT AN IMPLEMENTATION ONE. The AI-06 seam
      still has no production caller (§14.3), still needs STEP 0b before a writer
      may exist (§17.2b), and is not CONNECTED.
STILL BLOCKED even after all of the above, for EVERY phase including AI-06:
    THE WRITE ITSELF, until §15.2 STEP 0b lands (§17.2b) — and §8.3 condition 11
    with it. This is the clause that survives every other amendment, and it is
    the one the earlier revision of this document missed TWICE OVER: a
    registered token and a working call site together still do not establish who
    wrote the record (§4.3); and for as long as that is true, THE WRITER MUST NOT
    RUN.
```

### 17.4 Forbidden in AI-15, permanently

```text
FORBIDDEN:
    adding a producer token, or a row to §6.5
    editing AI-05's contract, AI-11's contract, or AI-14's contract
    editing any phase's Layer 0 boundary on that phase's behalf
    adding a trust root, a signer, a key, a registry service or a credential path
    adding an authentication API, a provenance-verification seam, a producer
      check, or any hook by which a claim would "look verified" — AI15-OPEN-1 is
      AI-05's to resolve, and AI-15 does not pre-empt it (§9.5, §15.2 STEP 0b)
    resolving AI15-OPEN-1 by implementing an answer, or re-litigating AI15-OPEN-2
      by implementing a different reading from the one AI-05 Amendment 4 chose
    implementing a writer in a phase that has not amended its own contract
    a composition producer token (§7.1)
    reimplementing any part of §30
    recasting a programming error as an admission outcome, or swallowing one
      (§11.1, §11.2)
    reading ACCEPTED as an authorization, a capability, a verification or a
      measurement
    a fallback producer, a repaired retry, or a default workspace
    cross-workspace anything
    reporting B5 as CONNECTED, or as "mostly connected", or as "provisional",
      while any of §8.3's twelve conditions is unsatisfied — in particular items
      10, 11 or 12, which a working call site does not supply
```

### 17.5 The four questions, answered for AI-15-B

```text
Q  does the composition call plugins.evidence directly, or does the owner phase?
A  §7.3: only T2 is consistent with the frozen contracts — the composition submits
   a record the OWNING phase authored — under READING A, which AI-05 Amendment 4
   chose (§5.3), and only after §15.2's STEP 1 and STEP 2. AI-15-B MUST NOT choose
   T1 or T3, and MUST NOT reach T2 by amending AI-14's contract itself (§15.2).

Q  is the composition only an orchestrator?
A  YES. AI-14 §3: it is not a component. It supplies NO fact of its own (§7.4),
   holds NO decision (root.py:20-30), and gains NO authority (§13).

Q  does the owner phase hold the producer token?
A  THE TOKEN IS NOT HELD (§4.3). It is a NAME registered for an event. What the
   owning phase owns is the CLAIM — §5.1's table maps each fact to its phase, and
   §9.4 fixes what a forwarder may not rewrite.

Q  is an admission failure a hard failure, an observable result, or a
   non-authoritative outcome?
A  IT IS A VALUE, AND IT IS OBSERVABLE, AND IT IS NON-AUTHORITATIVE — and none of
   those three means "harmless". §11.2 fixes who observes it and what is
   persisted; §10.3 and §11.3 forbid converting it into a success. AI-15-B MUST
   NOT swallow it.
A  AND AI-15-B MUST NOT REQUIRE THE CALLER TO CONTINUE EITHER. An earlier
   revision of this document said a hard failure "would give Evidence a veto, which
   is an authority AI-14 §4.1 does not grant". That OVER-INFERS and is WITHDRAWN.
   A caller may treat a REJECTED or an UNAVAILABLE as the failure of its own
   operation, return a non-success result, stop, or decline to run a dependent
   step — that is the caller's failure policy under the caller's own contract,
   and error propagation is not authorization. What AI-15 fixes is that the
   outcome stays observable, is never disguised as success and is never re-read
   as a permission (§11.4).
A  AND AI-15 DOES NOT SET ANY PHASE'S FAILURE POLICY. §11.4 keeps that out of
   scope: this document freezes the boundary, not the control flow.
A  AND THE OTHER CHANNEL IS NOT THIS ONE. A programming error — the store without
   `write`, or any other non-EvidenceError exception — is NOT an admission
   failure at all, is never an AdmissionResult, and MUST NOT be recast as one
   (§11.1, §11.2). "Admission returned a value" and "the caller misused the API"
   are two different events and stay reported as two.
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
    it states AI15-OPEN-1..4 with their owners, and keeps them distinct from
      AI-11 §21.1's OPEN-1 (§9.2, §16.1)
    it defines CONNECTED for B5 as twelve conditions (§8.3), on top of AI-14 §2's
      definition, and gives condition 11 — producer authenticity — its own owner
    it separates REGISTRY MEMBERSHIP from AUTHENTICATION everywhere they could be
      confused (§4.3, §6.1, §8.2, §9.2, §9.5)
    it separates AUTHENTICATION from AUTHORIZATION, in both directions (§9.5)
    it gives B5 an EXECUTABLE dependency order rather than a circular one (§15.2),
      and says what remains BLOCKED and whose decision is missing if that order
      cannot be satisfied
    it gates the WRITE, not only the label: §15.2 STEP 0b holds back any
      production call site that could persist a record, and §17.2b/§17.2c draw
      the line between that and preparation which cannot write
    it says which part of the joint STEP 2 + STEP 3 change each author owns, and
      keeps AI-14's owner owning its contract, Layer 0, tests and classification
      (§17.2d)
    it states that rule as ONE review and ONE merge, and does NOT present it as a
      commit-count requirement or attribute one to AI-14 (§17.2d)
    it states Layer 0's checks as BUILD-TIME repository checks, never as a
      runtime sandbox or a runtime authentication (§3.4)
    it keeps failure PROPAGATION separate from AUTHORIZATION, so neither
      "a caller must continue" nor "a caller may not fail" is imposed (§11.4)
    it names every B5 blocker with an owner and the step it gates (§16.2)
    it fixes failure semantics against AI-05's existing vocabulary, adding none (§11)
    it freezes the workspace obligations (§12)
    it restates the authority rules and forbids any transfer (§13)
    it states AI-15-B's boundary, including everything it may NOT do (§17)
    it changes NO runtime file and NO other phase's contract

AI-15-A IS NOT DONE IF
    any claim of CONNECTED appears without a non-test call site named by file:line
    any claim of CONNECTED appears while AI15-OPEN-1 is OPEN, however many call
      sites exist (§8.3 condition 11)
    registry membership is offered as producer authentication (§4.3)
    an authentication mechanism is described as an authority, or an authority as
      an authentication (§9.5)
    a prerequisite amendment is asked to record CONNECTED before the call site
      exists (§15.2)
    a programming error is presented as an admission outcome, or an outcome as an
      exception (§11)
    a production call site that can persist a record exists while AI15-OPEN-1 is
      OPEN, however the seam is labelled (§15.2 STEP 0b, §17.2b)
    a test-only path, a flag, a default or a helper is offered as satisfying
      STEP 0b, or as preparation that cannot write when it can (§17.2c)
    AI-15-B authors AI-14's contract, Layer 0, test or classification parts to
      satisfy the same-change rule, or a separately merged AI-14 part is offered
      as satisfying it (§17.2d)
    the same-change rule is stated as a COMMIT-COUNT requirement, or attributed
      to AI-14 as one — AI-14 §22.1 fixes the MERGE, not the commit count
      (§17.2d)
    Layer 0 is described as preventing an import at runtime rather than as
      refusing a repository change (§3.4)
    an admission failure is required to be swallowed, or a caller is forbidden
      from treating it as the failure of its own operation (§11.4)
    any frozen clause of AI-00 .. AI-14 is modified or restated in weaker words
    a producer token, a registry row, a new outcome, a new reason-code namespace
      or a new trust root appears
    B5's BLOCKED status is presented as a scheduling matter rather than named
      blockers with owners
    an OPEN item is closed by a decision this document makes
    AI-11 §21.1's OPEN-1 is closed, weakened or renamed, or reported as progressed
      by anything AI-15 does
```

---

## 19. Amendment and normative language

```text
FROZEN. This document was frozen by the merge of PR #78, and it has been amended
once since — Amendment 1, below. The line this block replaced read
"PROPOSED (this document's class until the merge that freezes it)", which was
true while the freeze was a proposal and false once it merged. It is corrected
here rather than left to contradict the amendment log beside it.
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

### Amendment log

#### Amendment 1 — AI15-OPEN-2 is answered by AI-05, and this contract records it
(2026-10-09)

```text
IN FORCE on the merge of the change that carries it. There is no awaiting-review
marker on this amendment: the merge IS the approval, and the text below is the
final text.
```

```text
WHAT WAS FOUND

    AI15-OPEN-2 asked which reading of AI-05 §7's "WROTE" governs `producer` when
    the submitter is not the named component. AI-15-A recorded it as OPEN, chose
    neither reading, and froze two rules against choosing one by accident.

    The question belongs to AI-05. AI-05 answered it in its own contract:
    AMENDMENT 4, merged as PR #80
    (03d42681cb8b2110773654822655117daea44ad5), IN FORCE.

    AI-05 Amendment 4 chose READING A. `producer` is the Workbench component
    RESPONSIBLE FOR THE CONTENT of the event the record describes; `submitter`
    is the caller that hands a prepared record to `admit()` or
    `admit_to_store()`; a submitter MAY differ from the producer, and calling
    either entry point does NOT by itself confer the producer role. It further
    separates THREE checks that must not be conflated: registry and cross-field
    validation, producer AUTHENTICATION, and submitter IDENTITY.

    AI-15 DID NOT MAKE THIS DECISION. It did not implement a reading, did not
    write a record either way, and added no test asserting an outcome — which
    is exactly what §5.3's frozen rules require. AI-15 RECORDS the owner's
    answer and updates its own dependency state. The authority is AI-05's
    contract; this document is downstream of it.
```

```text
CLAUSES, DEPENDENCIES AND STATUSES THIS AMENDMENT CHANGES

    §5.3     the freeze-time reading analysis is KEPT as the historical record and
              marked as such; a disposition block is added stating the answer,
              its authority and its limits. AI15-OPEN-2's status moves from OPEN
              to CLOSED / ANSWERED BY AI-05 AMENDMENT 4
    §5.3     the two resolving rules are restated as rules about OPEN items
              generally — unchanged in substance — and a RECORDED line states that
              AI15-OPEN-2 was closed by the owner, not by breaking them
    §7.3     "T2 is legal only under READING A" gains "and that condition is now
              met", plus a new FROZEN stating that a settled reading is NOT a
              connection and NOT an authorization
    §7.4     the "UNDETERMINED" answer names the settled question and keeps the
              answer to "who submits" as "nobody"
    §9.4     the precondition "AI15-OPEN-2 must be answered before this clause can
              be implemented" becomes RECORDED and satisfied; the clause is LIVE
    §14.1    the AI-06 dependency cell: UNDETERMINED -> NO, answered as READING A
    §14.2    AI-05's dependency line: OPEN-2 closed, OPEN-1 still OPEN
    §14.3    AI-06's dependency line: no §6.5 amendment needed, and the seam still
              has no caller
    §15.2    STEP 0a gains a STATUS: ANSWERED, naming the owner, the merge and the
              fact that AI-15 did not produce the answer. STEP 1's precondition
              is marked SATISFIED. STEP 2 and STEP 3 preconditions record that
              0a is satisfied and the others are not. The failure block no longer
              lists 0a as a possible missing decision
    §15.3    the two-AI-05-items block records that one is answered; the
              eight-change list marks (vii) satisfied IN PLACE and keeps the list
              at eight rather than renumbering it
    §16.1    AI15-OPEN-2 stays in the list, marked CLOSED, with its closer named;
              the closing rules name the three that remain
    §16.2    blocker 0a is marked SATISFIED in place; the header states that six
              of seven blockers remain; a FROZEN line states that satisfying 0a
              moved nothing to AI-15
    §17.3    the AI-06 paragraph no longer says the path is blocked by the
              reading, and states that a contract obstacle is not an
              implementation one
    §17.4    the forbidden-implementations line covers re-litigating the settled
              reading
    §17.5    the topology answer names the settled reading
    §19      the stale opening class line "PROPOSED (this document's class until the
              merge that freezes it)" is corrected — it contradicted the amendment
              log it sits beside
    Status    the OPEN list drops AI15-OPEN-2; the BLOCKED block records that
              STEP 0a is satisfied and the rest is not

    NOTHING ELSE IN THIS DOCUMENT CHANGED. No clause of §6, §8, §9.5, §10-§13 or
    §17.1-§17.2d is touched, and no row of §20 moves.
```

```text
SECURITY IMPACT

    None, and the negative is the point. This amendment RECORDS a clarification
    AI-05 made about attribution. It establishes NO authentication mechanism,
    adds no trust root, no signature, no key and no credential path, and it does
    not claim that any record, producer claim or submitter is thereby trusted.
    AI-05 Amendment 4 says the same in its own words: registry validation,
    producer authentication and submitter identity are three different checks,
    and it performs only the first.
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves any responsibility into AI-15.
    Guard remains the only component with an AUTHORIZES entry. No producer token,
    registry row or §6.5 constraint is added, removed or relaxed — those are
    AI-05's, and this amendment does not touch them.
```

```text
IMPACT ON B5

    STEP 0a's semantic question is answered, so the blocker that stood in front of
    AI-14's STEP 1 is cleared and STEP 1 may now begin. It has NOT begun: STEP 1
    is AI-14's to make, and this document does not make it.

    B5 REMAINS BLOCKED. STEP 0b (producer authentication, AI-05) is unanswered;
    STEP 1, STEP 1', STEP 2, STEP 3 and the joint-delivery mechanism are
    outstanding. B5 MUST NOT be marked CONNECTED, no seam is connected by this
    amendment, and no production Evidence writer is created or authorized.

    AI-15-B remains NOT STARTED.
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not close AI15-OPEN-1 — producer authentication remains AI-05's, and
      §15.2 STEP 0b still gates the WRITE on it
    it does not close AI-11 §21.1's OPEN-1, which asks WHICH PRODUCERS EXIST — a
      different question with the same owner
    it does not close AI15-OPEN-3 (AI-04) or AI15-OPEN-4 (AI-13 / AI-14)
    it does not modify AI-05, AI-06, AI-08, AI-11 or AI-14's contract
    it does not make AI-14's amendment, or AI-05's authentication standard
    it does not authorize creating or running a production Evidence writer
    it does not turn any NOT_RUN, BLOCKED or UNKNOWN into PASS
```

---

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
AI-15-A  = COMPLETE / MERGED            contract FROZEN — DOCS ONLY
                                        PR #78 @ 6e814a8b6d214a0203deb73b1abbf21ae50b68cc
                                        true two-parent merge of 37f354c + 210a190;
                                        not squashed, not rebased
                                        (PR #78 landed seven commits: cd4b8ed, 8b852e5,
                                        7391f02, 56c1791, 952da04, c0dde97, 210a190)
AI-15-B  = NOT STARTED                  BLOCKED (§16.2, §15.2)
```

```text
RECORDED — THE MERGE, AND WHAT IT DID AND DID NOT DO. This block states FACTS about
        PR #78. It adds NO rule, and it changes no clause of this document.

            the merge of PR #78 IS the freeze act for this document
            what it froze                       an ARCHITECTURE / CONTRACT
            what it did NOT do                  connect a seam · create a producer
                                                token · register a producer · write
                                                a record · move B5 out of BLOCKED
            states unchanged by it              every one in the block below
RECORDED    the rule that follows from a frozen document is §19's, and it is
            UNCHANGED by this closeout. §19 remains the authority for what an
            amendment must contain and for which clauses require one. Nothing here
            restates it more weakly, widens it, or adds a second amendment rule
            beside it.
```

The closeout that follows records the merge and syncs the status documents. It does
not amend §0-§20, and it does not freeze a new clause.

```text
BLOCKED: B5 (composition -> Evidence) is unchanged by this document. §16.2 lists
         every blocker with its owner and the §15.2 step it gates. ONE IS NOW
         SATISFIED — STEP 0a, answered as READING A by AI-05 Amendment 4 — and
         STEP 1 may therefore begin, but it has NOT begun and it is AI-14's to
         make. The rest stand: STEP 0b has no answer, STEP 1 has not been made,
         there is no call site, the joint-delivery mechanism is unnamed, and STEP
         3 cannot be recorded. Satisfying a blocker is not satisfying the item.
         NO PRODUCTION WRITER EXISTS, and none may be created while AI15-OPEN-1 is
         OPEN: §15.2 STEP 0b gates the WRITE, not only the label (§17.2b).

AMENDED: this document has been amended ONCE since it was frozen — §19 Amendment 1,
         which records AI-05's answer to AI15-OPEN-2. That is the only amendment.

OPEN:    AI15-OPEN-1 (AI-05) · AI15-OPEN-3 (AI-04) · AI15-OPEN-4 (AI-13/AI-14)
         — local ids, prefixed so they cannot be confused with AI-11 §21.1's
         OPEN-1, which is a different item (§9.2)
CLOSED:  AI15-OPEN-2 = CLOSED / ANSWERED BY AI-05 AMENDMENT 4 — READING A
         (§5.3, §16.1, §19 Amendment 1). AI-05 answered it; AI-15 recorded it.
         AI-11 §21.1's OPEN-1 is NOT closed by that and remains OPEN.

UNCHANGED BY THIS DOCUMENT: AI-05 · AI-06 · AI-08 · AI-10 · AI-11 · AI-13 · AI-14
         contracts, implementations and boundaries — every one byte-identical.

NOT CLAIMED: that Evidence is connected. It is not. §3 records what is, and §20
         records it at file:line. Freezing this contract changed none of that:
         at the merge, and after it, `plugins.evidence` still has no production
         caller and no production writer (§3.1-§3.3).

NOT CLAIMED: that a producer claim is trustworthy once a token is registered.
         It is not, and §8.3 condition 11 keeps BOTH the CONNECTED claim and the
         WRITE out until AI-05 says otherwise and shows it (§9.2, §15.2 STEP 0b).

NOT CLAIMED: that Layer 0 stops Evidence from being imported at runtime. It does
         not. It refuses a REPOSITORY CHANGE, and the absence of a caller at this
         baseline is a fact about the tree, not a runtime barrier (§3.4).

NOT CLAIMED: that Evidence admission failure must be swallowed, or that a caller
         may not treat it as the failure of its own operation. §11.4 keeps both
         claims out: the outcome stays observable, is never disguised as success
         and is never an authorization — and the caller's control flow is the
         caller's, under the caller's own contract.
```
