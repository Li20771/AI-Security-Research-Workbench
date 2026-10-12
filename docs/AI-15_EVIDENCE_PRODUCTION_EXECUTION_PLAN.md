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
        ^ RECORDED (§19 Amendment 3): STEP 0b IS NOW SATISFIED, SO THIS CLAUSE'S
        CONDITION NO LONGER HOLDS. The clause is kept because what it says about
        the CHECKS is unchanged and is the reason it exists: Layer 0 refuses a
        CHANGE and has never been a runtime barrier, and a record a writer stored
        is still stored. A writer present today would violate §17.2, not this
        clause.
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
        ^ THE CLAUSE IS KEPT IN ITS ORIGINAL WORDS AND ITS SECOND SENTENCE IS NO
        LONGER TRUE. It was written before PR #87 merged. A caller-supplied string
        is STILL what `provenance.producer` carries, and it is NO LONGER the SOLE
        basis on which the claim is accepted: §30 step 7b now requires a producer
        proof that verifies, so a well-formed token with no proof is REJECTED
        (AI-05 §7.3.3, §7.3.8). Recorded by §19 Amendment 5.
```

```text
FROZEN: THE PRODUCER FIELD IS A DECLARATION AND NOT AN AUTHENTICATION SOURCE.
        `provenance.producer` NAMES the component that is claimed to have produced
        the event. It does not establish that the claim is true, and no clause of
        this document may read it as establishing one. A declaration is what a
        proof is checked AGAINST; it is never what makes a claim trusted, and a
        record's own text must not be able to make itself credible.
FROZEN: A VALID PRODUCER PROOF VERIFICATION IS THE ADMISSIBILITY BASIS FOR THE
        PRODUCER CLAIM. The claim is admissible when, and only when, the submission
        carries a proof that verifies under the key the deployment's designated
        trust configuration holds for the token the record DECLARES — AI-05
        §7.3.1's standard, run as §30 step 7b, before any typed record exists. THIS
        IS WHAT MAKES A PRODUCER CLAIM MORE THAN WELL FORMED, and it is a SEPARATE
        question from §6.5's registry check (§4.3, §9.3). Neither substitutes for
        the other, and the declaration is not upgraded by a proof being valid for
        it: the proof is evidence about a KEY HOLDER, and §7.3.1 states the limit.
FROZEN: NO RUNTIME IDENTITY OBJECT IS INTRODUCED, BY THIS DOCUMENT OR BY THE PHASE
        THAT IMPLEMENTS THIS BOUNDARY. Authentication yields a VERDICT, not a
        value: there is no authenticated-producer handle, context, session or
        identity object to thread from a caller through a service to a writer, and
        NONE MAY BE ADDED. The producer identity a record carries is the DECLARED
        token, and what a reader may conclude from it is bounded by AI-05 §7.3.1
        and by §4.1's six-way separation. A design that needed such an object to
        carry trust forward would be a different architecture, and this boundary
        is not it: what crosses the boundary is the SUBMITTED MAPPING and the
        PROOF beside it (§9.4).
```

### 4.3 Is the producer claim enforced today?

**Yes, mechanically — against the registry. No, in any sense of authentication.**

```text
WHAT IS ENFORCED  plugins/evidence/models.py:173 check_cross_field, called from
                  `EvidenceRecord.from_mapping` at models.py:1586, i.e. INSIDE
                  `admit()`'s CONSTRUCTION step — admission.py:218, the THIRD step
                  of the pipeline, AFTER step 7's rule set and step 7b.

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

  admit(raw: object, *, producer_proof=None, clock=None) admission.py:177
  admit_to_store(raw: object, *, store, producer_proof=None,
                 clock=None) admission.py:228

  Neither takes a caller identity, a caller handle, a module, a workspace-scoped
  capability, or a credential. `raw` is a mapping. The producer is a FIELD INSIDE
  IT. Nothing in the record carries who submitted it, and nothing in the pipeline
  compares one with the other.
  ^ THE TWO SIGNATURES ARE RESTATED AT THE MERGED HEAD (§19 Amendment 5). Both
  entry points gained a THIRD keyword argument, `producer_proof`, and THAT DOES NOT
  CHANGE THIS BLOCK'S FINDING: a proof says something about the PRODUCER CLAIM and
  nothing about who is calling. The API still takes no submitter identity, still
  accepts any caller, and still compares no caller against the record (§9.2).
```

```text
FROZEN: the producer token is a NAMESPACE CLAIM, not a CREDENTIAL.
FROZEN: §6.5 REGISTRY MEMBERSHIP PROVES REGISTRATION AND NOTHING ELSE. A value
        passing `g_registered` proves that the string is the token the registry
        holds for this (kind, family). It does NOT prove that the named component
        produced the record, that the submitter is that component, or that the
        submitter is entitled to speak for it. Registry validation is a
        WELL-FORMEDNESS check; producer AUTHENTICATION is a different question.
        §30 step 7b is the step that ANSWERS it (AI-05 Amendment 5), AND PR #87
        NOW PERFORMS IT: `plugins/evidence/producer_auth.py` runs the check inside
        `admission.admit()`, before any typed record exists (§19 Amendment 3).
        ^ THE CLAUSE READ "AND NOTHING PERFORMS THAT STEP — it is contract text,
        not code (§19 Amendment 2)" UNTIL PR #87 MERGED, and it is corrected here
        rather than deleted because the rule AROUND it is the point. WHY THE RULE
        IS UNCHANGED: what `g_registered` proves is exactly what it proved before —
        registration, and nothing else. An authentication step running elsewhere
        does not make the registry check an authenticity check, and the two remain
        SEPARATE CHECKS (§9.3).
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
RECORDED (§19 Amendment 5): THE SENTENCE ABOVE IS KEPT IN ITS ORIGINAL WORDS AND IS
          NO LONGER TRUE AS WRITTEN. It was written before PR #87 merged. A module
          that can import `plugins.evidence` may still CALL `admit` with a mapping
          like the one above, and it now has to carry a producer proof that
          verifies AS WELL: a submission with no proof is REJECTED with
          AUTHENTICATION_PROOF_MISSING, and one whose proof does not verify is
          REJECTED too (AI-05 §7.3.3, §7.3.8). The step that refuses it runs before
          any typed record exists, so the well-formedness of the fields above is
          never reached on its own.
          WHAT DID NOT CHANGE IS THE PARAGRAPH'S POINT, AND IT IS NOW SHARPER: the
          API still takes no submitter identity, and an admitted record still
          proves only that a well-formed claim was made under a token whose
          producer claim was AUTHENTICATED as AI-05 §7.3.1 defines it — a KEY
          HOLDER, not a code component, and not the submitter (§4.3, §9.2).
```

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
        ^ RECORDED (§19 Amendment 3): AI15-OPEN-1 IS NO LONGER OPEN. The clause is
        left in its ORIGINAL WORDS because its FORM is the point — it is a rule
        BOUNDED BY A CONDITION, not a permanent prohibition — and because the
        conduct it governs is governed still, by §17.2, whose block on importing
        `plugins.evidence` from composition/ does not depend on this item at all.
        WHAT REFUSES A CALL SITE NOW IS §17.2 (STEP 1, and it is AI-14's), ROW 1′,
        AND STEP 2's OWN PRECONDITION — not this clause, and not §15.2 STEP 0b,
        which is satisfied.
        ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED — delivered by its OWNER,
        not by AI-15 (AI-14 Amendment 2, PR #90; recorded as discharged by AI-14
        Amendment 4, PR #96). §17.2 NO LONGER REFUSES THE IMPORT OR THE CALL. What
        still refuses a production call site is the joint-delivery requirement
        (§17.2d), row 1′ for any event but AI-06's, and the absent call site itself.
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
    WHAT THIS DOES NOT  establish producer authentication. AI-05 Amendment 4
      CLOSE             builds no authentication mechanism and claims no claim is
                        trustworthy — that was AI-05's SECOND question, and it was
                        answered and closed SEPARATELY, by AI-05 Amendments 5, 6
                        and 7 (§9.2, §19 Amendment 3).
                        ^ THIS PARAGRAPH SAID "AI15-OPEN-1 remains OPEN" UNTIL
                        §19 AMENDMENT 3. The item is now CLOSED BY ITS OWNER, and
                        NOTHING ABOUT AMENDMENT 4's SCOPE MOVES because of it:
                        Amendment 4 answered the READING question and not the
                        AUTHENTICITY one, and it is still the answer to the
                        reading question. It does not touch AI-11 §21.1's OPEN-1,
                        which asks a different question with the same owner and
                        REMAINS OPEN.
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
     THE SEMANTIC OBJECTION NOW SETTLED: AI-06's rows exist in §6.5, and AI-06
     §15.1 gives the submitter role its own words — "the caller submits it" — so
     the ownership question this path turns on is answered at the CONTRACT
     level. Settling it is not building on it: THE OBJECTION IS SETTLED, THE
     PATH IS NOT OPEN. No production caller exists (§14.3), T2 still has no
     authorized call site, and none may be created or run until AI-14's STEP 1
     (§17.2). ^ THE LAST CLAUSE CITED §15.2 STEP 0b UNTIL §19 AMENDMENT 3. STEP 0b
     IS NOW SATISFIED AND NO LONGER REFUSES ANYTHING; THE CONCLUSION IS UNCHANGED,
     and what refuses the call site now is §17.2 and §16.2's remaining rows.
     ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED — by its OWNER, not by AI-15
     (AI-14 Amendment 2, PR #90; recorded as discharged by AI-14 Amendment 4, PR
     #96). §17.2 NO LONGER REFUSES THE IMPORT OR THE CALL. What remains: the
     joint-delivery requirement (§17.2d), row 1′ for any event but AI-06's, a real
     non-test call site (STEP 2) and STEP 3.

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
        ^ RECORDED (§19 AMENDMENT 6): STEP 1 HAS SINCE BEEN MADE, BY AI-14. AI-14
        Amendment 2 (PR #90, merge a98e389b91ee10858abc67e7c66509cd12fae9dc)
        delivered the AUTHORIZATION change, and AI-14 Amendment 4 (PR #96, merge
        36d6ea92a8872dd9167412d8e39de063854b345d) records its enumerated list as
        discharged on AI-14's side. THE SENTENCE ABOVE IS KEPT AS WHAT IT WAS. AI-15
        DID NOT MAKE THIS STEP AND DOES NOT CLAIM IT. AI-15-B IS STILL NOT STARTED,
        and T2 still has no call site.
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
   caller has been written and §17.2 refuses one until AI-14's STEP 1.
   ^ THE SECOND REASON CITED §15.2 STEP 0b "while AI15-OPEN-1 is open" UNTIL §19
   AMENDMENT 3. STEP 0b IS NOW SATISFIED AND AI15-OPEN-1 IS CLOSED, so that reason
   is gone; THE ANSWER IS STILL "NOBODY", and §17.2 is what keeps it so.
   ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED — by its OWNER, not by AI-15
   (AI-14 Amendment 2, PR #90; recorded as discharged by AI-14 Amendment 4, PR
   #96). §17.2 NO LONGER REFUSES THE IMPORT OR THE CALL. THE ANSWER IS STILL
   "NOBODY", and what keeps it so now is the absent call site, the joint-delivery
   requirement (§17.2d) and row 1′ for any event but AI-06's.

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
                        ^ RECORDED (§19 Amendment 3): AI15-OPEN-1 IS CLOSED, so the
                        middle sentence's ANTECEDENT no longer holds. THE
                        CONCLUSION IS UNCHANGED AND SO IS ITS REASON: a path
                        meeting 1-10 is STILL NOT CONNECTED, because condition 11
                        is a condition on a RECORD and no record exists; and the
                        case STILL MUST NOT ARISE, because §17.2 refuses the import
                        and the call until AI-14's STEP 1, and §16.2's rows 1, 1′, 2
                        and 3 all stand. WHAT CHANGED IS WHICH CLAUSE FORBIDS IT,
                        NOT THAT IT IS FORBIDDEN.
                        ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED (AI-14
                        Amendment 2, PR #90; recorded as discharged by AI-14
                        Amendment 4, PR #96), so §17.2 no longer refuses the import
                        or the call, and row 1 is satisfied with it. THE CASE STILL
                        MUST NOT ARISE, and what forbids it is now the
                        joint-delivery requirement (§17.2d), row 1′ for any event
                        but AI-06's, and the absent call site.
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
        ^ RECORDED (§19 Amendment 3): "WHILE AI15-OPEN-1 IS OPEN" AND "WHICH §15.2
        STEP 0b FORBIDS" ARE BOTH SUPERSEDED. THE RULE IS NOT. A state that
        satisfies 1-10 still has a LIVE WRITER, it is still not CONNECTED, a better
        label is still not the remedy, and a record that was stored still stays
        stored (§6.1). What forbids the writer is now §17.2, row 1′, and STEP 2's
        own precondition.
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
STATUS TODAY: THE AUTHENTICATION GAP IS CLOSED AND THE CALLER GAP IS NOT. THREE
SEPARATE FACTS, AND THEY MUST NOT BE MERGED INTO ONE.

  the API        admit() takes no submitter identity (§4.3). ANY code that can
                 import `plugins.evidence` and call `admit` can submit a
                 producer="ai-04" claim with a well-formed DECISION — AND, SINCE
                 PR #87, THAT IS NOT SUFFICIENT. §30 step 7b runs BEFORE any typed
                 record is constructed, so the submission must also carry a
                 producer proof that authenticates under the deployment's
                 designated trust mapping; a submission with NO proof is REJECTED
                 exactly as one with a bad proof is (AI-05 §7.3). WHAT REMAINS A
                 PROPERTY OF THE API IS THE REST OF IT: it still takes no submitter
                 identity, and it still accepts any caller. AUTHENTICATING THE
                 PRODUCER TOKEN DOES NOT IDENTIFY THE SUBMITTER, and it is not
                 meant to — §4.1 keeps producer, actor and submitter apart, and §9.5
                 keeps authentication out of the authority matrix.
  the tree       at main @ 37f354c, no production module imports the package
                 outside AI-06's type-only projection, and no production caller
                 of admission exists (§3.1-§3.3). This is a RECORDED negative
                 finding about the repository AT THAT BASELINE, and it is the
                 weakest of the three: it says what HAS been written, not what CAN
                 run.
                 ^ RE-MEASURED AT main @ 9e1b4c45, AND IT STILL HOLDS. The baseline
                 finding was checked again on the tree this record is based on
                 rather than inherited from 37f354c. The measurement parses every
                 tracked `*.py` file and matches CALL EXPRESSIONS, not text, so a
                 docstring, a definition or a comment cannot be mistaken for a
                 call: 46 calls to `admit`/`admit_to_store` exist, 45 in `tests/`
                 and ONE outside it — `admit_to_store()` invoking `admit()`
                 internally, at `plugins/evidence/admission.py:288`. No wildcard
                 import, no `importlib`/`__import__` path and no string-literal
                 lookup reaches either entry point. The only importer outside the
                 package remains AI-06's type-only projection
                 (`plugins/security_tools/evidence.py:12`, which imports two TYPES
                 and calls neither), and the only non-test `EvidenceRecord(...)`
                 remains the stored-form loader (`stored.py:172`). NEITHER PR #87
                 NOR PR #88 ADDED A CALLER — and that is now a measurement at the
                 current baseline rather than an inheritance from the freeze.
  the check      a change adding such a caller TO ONE OF THE FIVE DIRECTORIES
                 THAT CARRY A RULE would fail the BUILD-TIME checks in §3.4.
                 That is a constraint on what may be MERGED. It is NOT global:
                 §3.4 names the packages that have no rule, and a caller placed
                 there would be refused by its phase's contract rather than by
                 a check.
  NOT claimed    that any of the three makes the API unreachable at RUNTIME.
                 THERE IS STILL NO RUNTIME SANDBOX — Layer 0 is a BUILD-TIME
                 repository-policy check, not a runtime barrier (§3.4) — AND THERE
                 IS NOW RUNTIME AUTHENTICATION, WHICH IS A DIFFERENT THING AND IS
                 NOT A SANDBOX. §30 step 7b runs inside admission, in the process
                 that called it; it authenticates a CLAIM, and it does not contain a
                 CALLER. Committed code that imported the package WOULD STILL RUN
                 (§3.4). What refuses it is that this repository will not merge it,
                 and §17.2, which blocks the import and the call until AI-14's
                 STEP 1. ^ THIS CLAUSE CITED §15.2 STEP 0b UNTIL §19 AMENDMENT 3.
                 STEP 0b IS SATISFIED AND NO LONGER REFUSES ANYTHING; the
                 prohibition on creating the writer is UNCHANGED and now rests on
                 §17.2 and §16.2's remaining rows.
                 ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED (AI-14 Amendment
                 2, PR #90; recorded as discharged by AI-14 Amendment 4, PR #96).
                 §17.2 NO LONGER REFUSES THE IMPORT OR THE CALL. THE PROHIBITION ON
                 CREATING THE WRITER IS UNCHANGED and now rests on the
                 joint-delivery requirement (§17.2d), row 1′ for any event but
                 AI-06's, §16.2's remaining rows, and §8.3 condition 11.

AI15-OPEN-1  PRODUCER AUTHENTICITY — how is a producer claim ESTABLISHED, as
             against merely well-formed?

        OWNER            AI-05. It owns §6.5, §6.6 and §7. The question is a
                         question about AI-05's admission contract, and neither
                         AI-15 nor any other phase may answer it for AI-05.
        STATUS           CLOSED. Closed by its OWNER, in the owner's contract,
                         under the owner's amendment rule — AI-05 Amendment 7,
                         merged by PR #88 (commit
                         9e1b4c451deed34605d021b4203fccd16dad4cd0). AI-15 RECORDS
                         the closure and did not make it (§19 Amendment 3).
        WHAT WAS MISSING  a decision about HOW a claim is established. §6.5/§6.6
                         answer "is this token the registered one for this kind
                         and family"; nothing answered "did the named component
                         submit it". AI-05 MADE THAT DECISION — see "WHAT WAS
                         MISSING NOW" below and §19 Amendment 2.
        WHAT WAS MISSING NOW  ^ THE HEADING IS KEPT AS WHAT IT WAS. Under it, this
                         block read "the decision is made; the mechanism is NOT
                         BUILT", and that was true from Amendment 6 until PR #87
                         merged. NOTHING IS MISSING NOW: the three parts §15.2
                         STEP 0b measures are all supplied.
                             MECHANISM               DEFINED — AI-05 Amendment 5
                                                     (§7.3, §30 step 7b) and
                                                     Amendment 6 (§7.3.11,
                                                     §31.3), counted ONCE,
                                                     because the configuration
                                                     freeze is PART OF defining
                                                     the mechanism, not a second
                                                     delivery beside it
                             RUNTIME IMPLEMENTATION  IMPLEMENTED — PR #87, merge
                                                     commit
                                                     d09ce69ec1c0975c6d638d7861df2f11c44ec1d1
                             ACCEPTANCE TESTS        RUN — CI run #301, 46
                                                     process-isolated cases that
                                                     RAN, 0 skipped
                         THE LAYER 0 RULES AMENDMENT 6 OBLIGED ARE NOT MERELY
                         WRITTEN DOWN. PR #87 implements them in
                         scripts/ci/layer0_policy.py, and run #301 reports
                         `Layer 0 = PASS (24 checks)` including
                         `evidence producer authentication boundary`. §19
                         Amendment 3 states all of this with its links, and it is
                         the record to read.
        WHAT AI-15 DOES NOT DO   it does not add a token, a check, a hook, a
                         signature, a key, a registry service or a "producer
                         verification" seam. §17.4 forbids all of them.
        HOW THE QUESTION WAS ANSWERED   that was AI-05's design act, and AI-15
                         states no preference among mechanisms. §9.5 fixes only
                         that whatever AI-05 chooses MUST NOT enter the authority
                         matrix. AI-05 made that act in its own contract, under
                         its own amendment rule (Amendments 5 and 6), and CLOSED
                         the item there too (Amendment 7). AI-15 records it and
                         did not produce it.
        WHAT KEEPS IT FROM MATTERING TODAY  THE GATE THIS ITEM HELD IS GONE, AND
                         WHAT REMAINS IS A FACT RATHER THAN A GATE. The finding
                         that no production caller exists HAS BEEN RE-MEASURED at
                         the current baseline and still holds (see "the tree"
                         above) — but it is NOT the only thing standing between a
                         claim and a stored record, and it MUST NOT be written as
                         though it were:
                             THE AUTHENTICATION IS NO LONGER ABSENT. A caller
                               written today would have to present a producer
                               proof that authenticates, because §30 step 7b runs
                               inside `admit()` before any typed record is
                               constructed. That is a REAL CONTROL, and it is the
                               one this item was about.
                             THE REPOSITORY GATES ARE STILL IN FRONT OF THE WRITE.
                               §17.2 refuses the import and the call until AI-14's
                               STEP 1, and §16.2 rows 1, 1′, 2 and 3 stand.
                               ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED
                               (AI-14 Amendment 2, PR #90; recorded as discharged by
                               AI-14 Amendment 4, PR #96), so §17.2 no longer
                               refuses the import or the call and row 1 is satisfied
                               with it. THE GATES STILL IN FRONT OF THE WRITE ARE
                               the joint-delivery requirement (§17.2d), ROW 1′ for
                               any event but AI-06's, and §16.2's remaining rows.
                             WHAT IS ACTUALLY ABSENT IS A CALLER — and its absence
                               is what makes the API UNREACHABLE IN PRACTICE. It is
                               a FACT ABOUT THE TREE and NOT a runtime security
                               control: nothing enforces it at runtime, and this
                               document MUST NOT present it as one.
                         §15.2 STEP 0b no longer forbids creating a caller, because
                         STEP 0b is satisfied; the prohibition is §17.2's and
                         §16.2's, and NEITHER OF THOSE IS A RUNTIME BARRIER either.
        STATUS, STATED PRECISELY  FOUR SEPARATE THINGS, AND THIS RECORD KEEPS
                         THEM APART — merging any two of them either overstates or
                         understates the position.

                             THE MECHANISM       IMPLEMENTED. `admit()` performs
                                                 §30 step 7b BEFORE any typed record
                                                 is constructed, against a designated
                                                 trust mapping read once at process
                                                 initialization; a submission with
                                                 no proof is REJECTED exactly as one
                                                 with a bad proof is. THIS IS THE PART
                                                 PR #87 CHANGED, and it is the part
                                                 this item was about.
                             THE API BOUNDARY    UNCHANGED, AND NOT A CONSEQUENCE OF
                                                 THE MECHANISM. The API still takes no
                                                 submitter identity and still accepts
                                                 any caller. AUTHENTICATING A PRODUCER
                                                 CLAIM DOES NOT IDENTIFY THE
                                                 SUBMITTER, DOES NOT AUTHORIZE THE
                                                 CALLER, AND WAS NEVER MEANT TO
                                                 (§4.1, §9.5). A caller that passes
                                                 authentication is a caller whose
                                                 CLAIM checked out — not a caller the
                                                 API approved.
                             THE PRODUCTION      NONE — RE-MEASURED at the current
                               CALLER STATE      baseline, with the method and the
                                                 counts stated under "the tree" above.
                                                 The absence is what makes the API
                                                 unreachable in practice.
                             THE GATES           §17.2, row 1′, STEP 2's precondition,
                                                 and the remaining STEP 3 and
                                                 joint-delivery requirements — ALL
                                                 still unsatisfied, NONE of them
                                                 AI-05's, and NONE moved by this
                                                 closure.

                         THE SENTENCE THIS PARAGRAPH USED TO CARRY — that the only
                         thing between a caller-supplied claim and a stored record
                         is that nobody has written the caller — WAS TRUE BEFORE
                         PR #87 AND IS NOT TRUE NOW. A caller would ALSO have to
                         authenticate, and would ALSO have to pass a gate that is
                         still closed. "No caller exists" remains a fact about the
                         tree and is still NOT a property that keeps anything safe;
                         it has simply stopped being the whole of the story.
        WHY IT IS STILL A B5 PREREQUISITE, AND WHAT THAT NOW MEANS  because the
                         first caller to be written would run — which is what B5
                         is, and writing it is still gated. WHAT GATES IT IS NO
                         LONGER THIS ITEM: STEP 0b is satisfied (§15.2, §16.2,
                         §17.2b), and the blockers that remain are STEP 1, row 1′,
                         STEP 2 and STEP 3, none of which is AI-05's to move.
                         ^ RECORDED (§19 AMENDMENT 6): OF THOSE FOUR, STEP 1 IS NOW
                         SATISFIED TOO (AI-14 Amendment 2, PR #90; recorded as
                         discharged by AI-14 Amendment 4, PR #96), and it was moved
                         by its OWNER and not by AI-05 or AI-15. THE BLOCKERS THAT
                         REMAIN ARE row 1′, a real non-test call site (STEP 2), the
                         joint-delivery mechanism and STEP 3.
                         §8.3 condition 11 carries the mechanism into the
                         CONNECTED gate, and §16.2 keeps that SEPARATE from the
                         item's closure: B5 is still BLOCKED, still NOT
                         CONNECTED, and there is still no call site and no record.
```

```text
AI15-OPEN-1 IS NOT AI-11 §21.1's OPEN-1. They share an owner and nothing else.

    AI-11 §21.1 OPEN-1   WHICH PRODUCERS EXIST
                         no §6.5 row exists for AI-08 / AI-10 / AI-11 / AI-13, so
                         no record from those phases can be admitted at all.
                         Resolving it means ADMITTING A TOKEN.  (§15.3)

    AI15-OPEN-1          WHETHER A PRODUCER CLAIM IS TRUSTWORTHY
                         the rows that DO exist accept a caller-supplied string.
                         AI-05 has DECIDED how a claim is established (Amendments
                         5 and 6); resolving the item now means IMPLEMENTING that
                         decision and TESTING it, not choosing it. (§4.3, §8.3
                         condition 11)

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
STATUS TODAY: THE FIELD IS STILL CALLER-SUPPLIED, AND REGISTRATION IS STILL THE
ONLY THING §6.5/§6.6 CHECK ABOUT IT — WHICH IS WHY A SEPARATE STEP EXISTS.

  `provenance.producer` is a Class 3, G-REGISTERED leaf in §15.2's field table
  (plugins/evidence/canonical.py:104), validated by g_text at
  plugins/evidence/models.py:1211 and by the registry at models.py:193.
  It is caller-supplied, and AI-05 §14.10's C1-R06 opaque-token rule scans it.

THREE THINGS THAT MUST NOT BE COLLAPSED, AND THE ORDER THEY RUN IN:

  1  THE CLAIM. `provenance.producer` remains a SUBMITTED string. §6.5/§6.6
     check REGISTRATION — whether the token is the registered one for that kind
     and family, and whether it is applicable. That comparison is a
     WELL-FORMEDNESS check and is NOT authentication.
  2  THE AUTHENTICATION. A SEPARATE mechanism, §30 step 7b, requires a producer
     PROOF; it verifies the signature under the key the deployment's designated
     trust configuration holds for the claimed token; and it requires the signed
     input to be the canonical serialization of THIS submitted mapping. It runs
     BEFORE construction, and none of its six reason codes is a registry code
     (§7.3.8).
  3  THE CONSEQUENCE. A value that passes the REGISTRY check does NOT by itself
     mean the whole admission succeeds. Registration is NECESSARY AND NOT
     SUFFICIENT: `ai-04` still has to authenticate, and it does so only if the
     submission carries a proof that verifies under `ai-04`'s designated key over
     this exact mapping.

RECORDED: a value "looking right" is EXACTLY the condition that makes it pass
          REGISTRATION. `ai-04` passes the registry because it IS the registered
          token for a DECISION — not because anything verified who wrote it.
          ^ THAT SENTENCE WAS THE WHOLE STORY UNTIL PR #87 AND IS NOW ONE HALF OF
          IT: registration still says nothing about authorship, and what says
          something about it is the separate step in 2 above. THE DISTINCTION THE
          PARAGRAPH EXISTS TO DRAW IS UNCHANGED AND IS NOW SHARPER — registry
          membership and producer authentication are SEPARATE CHECKS, and the
          second does not replace the first: §6.5 is still the sole authority on
          which tokens are RECOGNIZED, so an authenticated claim naming an
          unregistered token is still REFUSED, during construction (§7.3.2,
          §7.3.7).
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
FROZEN: THE PRODUCER PROOF CROSSES THE SAME BOUNDARY, AND THE LIST ABOVE IS NOT THE
        INSTRUMENT FOR IT. The proof is NOT a record field (AI-05 §7.3.3), so it is
        not one of the five items above. It is carried BESIDE the submitted mapping,
        as an argument to the admission entry point, and the forwarder that submits
        is the party that presents it. AI-05 §7.3.12 states the permission and its
        limits from the producing contract's side; this clause states the
        INVARIANT that makes the permission safe.
FROZEN: THE PROOF BYTES MUST BE PRESERVED. A forwarder that carries a producer
        proof MUST carry it UNCHANGED — `message_b64u` and `signature` alike, byte
        for byte — and MUST NOT re-encode, re-order, pad, trim, normalise, rewrap or
        rewrite any part of it. A re-encoding that would decode to the same bytes is
        STILL a change to the envelope and is refused as one: AI-05 §7.3.3 requires
        decoding to be strict AND canonical, so a value that is not reproduced
        exactly by re-encoding is malformed rather than an alias of a valid one.
FROZEN: DROPPING THE PROOF IS `AUTHENTICATION_PROOF_MISSING`, AND THAT IS THE ONLY
        THING IT CAN BE. An absent argument, or an explicit `None`, is REJECTED —
        not a TypeError, and not a weaker admission (AI-05 §7.3.3, §7.3.8). A
        forwarder therefore CANNOT lose a claim into an unauthenticated acceptance:
        the only outcome a dropped proof can produce is a refusal.
FROZEN: MODIFYING THE PROOF IS A VERIFICATION FAILURE, NAMED BY THE STEP THAT CATCHES
        IT. A changed message fails V4 (AUTHENTICATION_SIGNATURE_INVALID) or, if the
        signature was recomputed, V5 (AUTHENTICATION_INPUT_MISMATCH); a changed
        envelope fails V1 (AUTHENTICATION_PROOF_MALFORMED) (AI-05 §7.3.5).
FROZEN: SUBSTITUTING A PROOF CANNOT BE MADE TO VERIFY, AND THE REASON IS STRUCTURAL
        RATHER THAN POLICY. The carried bytes must equal the verifier's own
        reconstruction of THIS submitted mapping, so a proof minted for any other
        record fails V5; and the key is selected BY THE TOKEN THE RECORD DECLARES,
        so another producer's proof fails V4 under this token's key (AI-05 §7.3.5
        V3-V5). A substitute does not become acceptable by being well formed.
FROZEN: NO SILENT ACCEPTANCE EXISTS ON ANY OF THESE PATHS. There is no parameter, no
        configuration and no forwarding shape under which a lost, altered or
        substituted proof yields an ACCEPTED, and a forwarder MUST NOT report one as
        evidence that the claim was authenticated.
FROZEN: A FORWARDER MUST NOT MINT, RE-MINT OR REPAIR A PROOF. Minting requires the
        producer's private signing key, and the deployment's designated
        configuration carries PUBLIC key material only (AI-05 §7.3.2, §7.3.11); key
        custody is §7.3.9's trust assumption and is outside this contract. A
        forwarder that holds no key can transmit a proof and cannot manufacture
        one — and a forwarder that DID hold one would be the forgery AI-05 §9.2
        names, not a convenience.
FROZEN: THE COMPOSITION'S OWN CONDUCT IS AI-05 §7.3.12's AND AI-14 §22.1 B5's. The
        composition MAY transport an owning phase's proof as OPAQUE material, and
        MUST NOT generate, replace, mutate or claim ownership of one. §17.4 forbids
        AI-15 from adding a trust root, a signer or a key, and this clause adds
        none: it constrains what a caller does with material it did not produce.
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
admit(raw: object, *, producer_proof=None, clock=None) -> AdmissionResult
                                                                admission.py:177
     step 7   check_admission_rules(raw)                        admission.py:216
     step 7b  authenticate(raw, producer_proof)                 admission.py:217
                -> §7.3's check on the producer claim, and it runs BEFORE any
                   typed record exists (plugins/evidence/producer_auth.py:394)
     steps 1-4, 4b, 6, 8-13
              EvidenceRecord.from_mapping(raw, clock=clock)     admission.py:218
                -> which calls check_cross_field at models.py:1586 (§6.5/§6.6)
     step 5   check_workspace_agreement(record)                 admission.py:219
     step 12  assign_digests(record)                            admission.py:220
     stores NOTHING.

admit_to_store(raw: object, *, store, producer_proof=None, clock=None)
                                                                admission.py:228
     admit(raw, producer_proof=producer_proof, clock=clock)     admission.py:288
     step 14  store.contains(record.evidence_id)                admission.py:294
              store.write(record)                               admission.py:299
```

```text
RECORDED (§19 Amendment 5): THIS BLOCK WAS MEASURED BEFORE PR #87 MERGED AND IS
        RESTATED HERE AT THE MERGED HEAD. Three things changed and all three are
        visible above: both entry points take a third keyword argument,
        `producer_proof`; the pipeline has a step between step 7 and construction;
        and the line numbers moved, because the implementation around them grew.
        NOTHING ELSE MOVED — `admit()` still stores nothing, `admit_to_store()`
        still runs step 14 and then the store, and the relative order of every step
        that existed before is unchanged.
FROZEN: `producer_proof` IS REQUIRED IN AI-05 §7.3.3's SENSE. Its default is `None`
        and an argument that is absent or explicitly `None` is REJECTED with
        AUTHENTICATION_PROOF_MISSING rather than raising TypeError: a caller that
        omits the proof receives an ADMISSION RESULT and not an exception
        (admission.py:197-201, AI-05 §7.3.3).
FROZEN: `admit_to_store()` PASSES THE PROOF THROUGH TO `admit()` RATHER THAN
        VERIFYING A SECOND TIME. One verification runs and one verdict is reached;
        a non-ACCEPTED result returns before the store is touched, so an
        authentication failure never contacts storage (admission.py:239-242,
        AI-05 §7.3.3, §7.3.8).
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
FROZEN: a production caller MUST PRESENT the producer proof for the record it
        submits, at the entry point, as the argument AI-05 §7.3.3 defines. The proof
        is NOT a record field, and it is the ADMISSIBILITY BASIS of the producer
        claim (§4.2): a caller with no proof for the claim it is submitting has
        nothing admissible to submit, and the outcome is REJECTED with
        AUTHENTICATION_PROOF_MISSING rather than a weaker admission.
FROZEN: a production caller MUST NOT fabricate, substitute or repair a proof, and
        MUST NOT hold, request, accept or be handed a producer's private signing
        key. A caller that is not the producing component TRANSPORTS the producing
        component's proof AS OPAQUE MATERIAL and changes nothing in it: it does not
        read it, it does not re-encode it, it does not mint a second one, and it does
        not decide what is trusted (§9.4, AI-05 §7.3.12, AI-14 §22.1 B5).
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

### 10.4 The AI-15-B freeze matrix — the write pipeline (Amendment 5)

```text
THE PIPELINE, AND IT HAS NO AUTHORIZATION STAGE IN IT:

    submit request
      |
    producer proof authentication        §30 step 7b, run by `admit()`
      |                                  (admission.py:217)
    evidence admissibility validation     §30 step 7's published rule set over
      |                                  the SUPPLIED values, and then the shape,
      |                                  required-field, class, vocabulary and
      |                                  §6.5/§6.6 checks (§30 steps 1-4, 4b, 6)
    EvidenceRecord construction          §30 steps 1-4, 4b, 6, 8-11 and 13
      |                                  (admission.py:218)
    persist                              §30 step 14, then the store
                                         (`admit_to_store`; admission.py:294-299)
```

```text
FROZEN: NO AUTHORIZE STAGE EXISTS IN THIS PIPELINE, AND NONE MAY BE ADDED. An earlier
        model of this boundary — recorded in a review checklist rather than in this
        contract — placed an "authorize evidence production" step between
        authentication and construction. THAT MODEL IS WITHDRAWN AND MUST NOT BE
        REINTRODUCED. Evidence authorizes nothing: §13.1's matrix has exactly one
        authorizing column entry and it is Guard, admission is not authorization
        (§13.2), and an authenticated producer claim is not a permission (AI-05
        §7.3.8). A step that granted, checked or consumed a permission here would be
        an authority transfer arriving as wiring, which §13.3 forbids AI-15-B from
        making — and it would require the authority-matrix change §9.5 and §13.3
        keep out of this phase's reach.
FROZEN: AUTHENTICATION PRECEDES CONSTRUCTION, AND CONSTRUCTION PRECEDES PERSISTENCE.
        The first ordering is what this pipeline exists to fix: no typed record, and
        therefore no Evidence digest, may be derived from a claim that is not
        authenticated (AI-05 §7.3.7). "Construct first, authenticate later" is
        FORBIDDEN, and it is not reachable through either entry point — step 7b runs
        before `EvidenceRecord.from_mapping` is called at all, not after it.
FROZEN: WHERE THE ADMISSIBILITY CHECKS ACTUALLY RUN, STATED SO THE DRAWING ABOVE IS
        NOT MISTAKEN FOR A SECOND CONTRACT THAT REORDERS §30. The middle stage is
        drawn as one row because it is ONE QUESTION — is this evidence admissible —
        and that question is answered in TWO PLACES, neither of which this matrix
        moves:
            §30 step 7's published rule set runs BEFORE authentication, and
              `check_admission_rules` is written for exactly that position
              (admission.py:216; AI-05 §7.3.7 records why R2 forces it first)
            the shape, required-field, closed-key, vocabulary and §6.5/§6.6
              registry checks run INSIDE construction, at §30 steps 1-4, 4b and 6
              (admission.py:218; models.py:1586)
        AI-15 DOES NOT REORDER EITHER, and no clause of this document may be read as
        placing the registry check before authentication. AI-05 §7.3.2 records why
        the order between those two checks carries no weight: they answer different
        questions, and neither substitutes for the other. A submission naming an
        unregistered token can PASS authentication and is then REFUSED by §6.6 —
        that is the frozen behaviour, not a hole.
FROZEN: THIS MATRIX ADDS NO STEP, NO CALL AND NO ORDERING BEYOND WHAT §10.1 RECORDS.
        §10.1 remains the file:line record of what runs; this section names the
        SHAPE AI-15-B must preserve when it wires a caller to it. It changes no
        clause of §10.1-§10.3, and it does not make any of them callable: §17.2,
        row 1′ and STEP 2's precondition still refuse the writer, and §17.4 still
        forbids AI-15 to add a producer check of its own.
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
| AI-14 | §22.1 B5 BLOCKED; §5.1 not connected | `composition/` | **no** | **no** | **YES — §15.2. STEP 1's part is MADE (AI-14 Amendment 2, PR #90; recorded as discharged by AI-14 Amendment 4, PR #96); STEP 3's CLASSIFICATION still merges WITH the call site** |

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
           NONE OUTSTANDING. Both AI-05 questions AI-15 recorded are now answered
           AND closed by their owner: §5.3's AI15-OPEN-2 by AI-05 Amendment 4
           (READING A), and §9.2's AI15-OPEN-1 by AI-05 Amendment 7. NEITHER
           CLOSURE WAS AI-15'S ACT, and neither is recorded as one (§16.1).
           THE PRODUCER-AUTHENTICATION RECORD, IN ONE PLACE. AI-05 Amendment 5
           (PR #83, merge 7017bf577f654cb6dea0e8d5e50a27f334117b73) DEFINES the
           standard; AI-05 Amendment 6 (PR #85, merge
           cee1f8c9ae07837e0ebae0be3f8ab2e0113e6973) FREEZES its designated trust
           configuration, its encoding, its ONE READER, its lifecycle and the
           static enforcement it requires; and PR #87 (merge
           d09ce69ec1c0975c6d638d7861df2f11c44ec1d1) IMPLEMENTS it. The first two
           are DOCUMENTATION and together supply ONE of §15.2 STEP 0b's three
           parts — the mechanism — because the configuration freeze is part of
           defining it. THE THIRD SUPPLIES THE OTHER TWO: the runtime
           implementation, INCLUDING the Layer 0 rules Amendment 6 obliged (which
           belong to the implementing change rather than being a third deliverable
           beside it), and the §7.3.7 acceptance tests. CI run #301 executed them
           on the merged head: 46 process-isolated cases RAN, 0 skipped, and
           `Layer 0 = PASS (24 checks)`.
           AI-05 Amendment 7 (PR #88, merge
           9e1b4c451deed34605d021b4203fccd16dad4cd0) is where the OWNER recorded
           all of that and CLOSED AI15-OPEN-1, in AI-05's contract, under AI-05's
           amendment rule. THAT IS THE UPSTREAM AUTHORITY FOR THE CLOSURE; §19
           Amendment 3 syncs this document to it.
           AI-11 §21.1's OPEN-1 IS A DIFFERENT ITEM AND IS NOT MOVED BY ANY OF
           THEM: it asks WHICH PRODUCERS EXIST, no amendment named above admits a
           token, and the §6.5 registry still holds six rows over four tokens.
           AI-05 remains INCOMPLETE — §35.1's deferrals are open and the registry
           is unchanged — and nothing here says otherwise.
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
           ^ RECORDED (§19 AMENDMENT 6): A CHANGE ADDING ONE NO LONGER FAILS
           layer0. AI14_FORBIDDEN_IMPORTS is EMPTY as of AI-14 Amendment 2
           (PR #90), which AUTHORIZED the import; what still fails is the AST
           assertion in tests/composition/test_composition_boundaries.py, which
           checks the CALL rather than the import. Amending that assertion is part
           of AI-14's OWN part of the connecting change (§15.2 STEP 3, §17.2d).
evidence   AI-14-B merged as adf6db2476b7e3de33a585954610e9ab568b498c (PR #73).
AI-15 dependency
           YES. §15.2. Connecting B5 requires an AI-14 amendment; §24 lists
           "the execution topology's CONNECTED/SEAM classification of a path" as
           amendment-requiring, and §22.1 requires Appendix A to be updated in the
           same change.
           ^ RECORDED (§19 AMENDMENT 6): STEP 1'S AI-14 AMENDMENT HAS BEEN MADE —
           AI-14 Amendment 2 (PR #90, merge
           a98e389b91ee10858abc67e7c66509cd12fae9dc), recorded as discharged by
           AI-14 Amendment 4 (PR #96, merge
           36d6ea92a8872dd9167412d8e39de063854b345d). WHAT REMAINS ON AI-14'S SIDE
           IS STEP 3: its CLASSIFICATION part, merged WITH the call site in ONE
           change (§17.2d).
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
                         ^ RECORDED (§19 AMENDMENT 6): THE AUTHORIZATION HAS SINCE
                         BEEN MADE, BY AI-14'S OWNER — AI-14 Amendment 2 (PR #90,
                         merge a98e389b91ee10858abc67e7c66509cd12fae9dc), recorded
                         as discharged by AI-14 Amendment 4 (PR #96, merge
                         36d6ea92a8872dd9167412d8e39de063854b345d). AI-15 DID NOT
                         MAKE IT, does not restate it, and produces no part of it.

  STEP 0b  AI-05 answers AI15-OPEN-1 (§9.2, §9.5): how a producer claim is
           ESTABLISHED to AI-05 §7's standard for "the component that WROTE".
           OWNER         AI-05.
           PRECONDITION  none. May run in parallel with STEP 1, and with the
                         non-writing preparation §17.2c allows.
           OUTPUT        a mechanism, PLUS its implementation and tests — not a
                         prose decision alone, because §8.3 condition 11 requires
                         that the standard be implemented and shown to hold.
           STATUS        SATISFIED — ALL THREE PARTS SUPPLIED, EACH BY ITS OWN KIND
                         OF ACT.
                         THE MECHANISM is DEFINED: AI-05 Amendment 5 defines the
                         standard (§7.3, §30 step 7b) and AI-05 Amendment 6 freezes
                         its designated trust configuration, its encoding, its ONE
                         READER, its lifecycle and the static enforcement it
                         requires. THE TWO COUNT ONCE, because the configuration
                         freeze is PART OF the mechanism's definition and NOT a
                         second delivery standing beside it; the owner delivered
                         both in the owner's contract.
                         THE RUNTIME IMPLEMENTATION is IMPLEMENTED: PR #87, merge
                         commit d09ce69ec1c0975c6d638d7861df2f11c44ec1d1. IT IS NOT
                         MERELY WRITTEN — §31.3's four static rules are ENFORCED by
                         scripts/ci/layer0_policy.py, and run #301 returned
                         `Layer 0 = PASS (24 checks)` including
                         `evidence producer authentication boundary`. The Layer 0
                         rules Amendment 6 obliged belong to THIS part, being
                         obligations on the implementing change rather than a
                         deliverable of their own.
                         THE ACCEPTANCE TESTS are RUN: CI run #301, on the merged
                         head, 46 process-isolated cases that RAN and 0 that were
                         skipped, across §7.3.2's eight trust configurations. §31.3
                         requires a report to carry the number that RAN rather than
                         the run's status, and 46 is that number.
                         THE OWNER CLOSED AI15-OPEN-1 ON THIS EVIDENCE, in AI-05's
                         contract, under AI-05's amendment rule — AI-05 Amendment
                         7, merged by PR #88 (commit
                         9e1b4c451deed34605d021b4203fccd16dad4cd0). §19 Amendment 3
                         records that and syncs this document to it. AI-15 DID NOT
                         MAKE THE DECISION AND DOES NOT RESTATE IT.
           GATES         STEP 2 AND STEP 3. BOTH. ^ THE GATE THIS STEP HELD IS
                         DISCHARGED BY ITS SATISFACTION, AND THAT IS THE WHOLE OF
                         WHAT MOVED. STEP 2 and STEP 3 remain gated by STEP 1, by
                         row 1′, by the call site itself and by the joint-delivery
                         mechanism — none of which is AI-05's to move, all of which
                         remain unsatisfied, and none of which this step's
                         satisfaction touches (§16.2, §17.2).
                         ^ RECORDED (§19 AMENDMENT 6): OF THOSE FOUR, STEP 1 IS NOW
                         SATISFIED (AI-14 Amendment 2, PR #90; recorded as
                         discharged by AI-14 Amendment 4, PR #96) — and it was
                         moved by AI-14, not by AI-05 and not by AI-15. STEP 2 AND
                         STEP 3 REMAIN GATED BY row 1′, by the call site itself and
                         by the joint-delivery mechanism.
           FROZEN: STEP 0b GATES THE WRITE, NOT ONLY THE LABEL. No production,
                   non-test call site that can actually execute §30 admission and
                   persist an EvidenceRecord may be created, merged or run before
                   STEP 0b is complete. A writer that runs is a writer that can
                   store a producer claim nobody established, and whether the
                   resulting seam is later LABELLED CONNECTED does not un-store
                   the record.
                   ^ RECORDED (§19 Amendment 3): THIS CLAUSE'S CONDITION IS NOW
                   MET, AND THE CLAUSE IS NOT THEREBY REPEALED. It stated a
                   precondition on the write, not a permanent prohibition, and the
                   precondition is satisfied. IT IS ALSO NOT THE ONLY THING
                   STANDING IN FRONT OF A WRITER, and no reader may take its
                   discharge as permission: §17.2 still blocks the import, the
                   call and every route to them until AI-14's STEP 1, §16.2's rows
                   1, 1′, 2 and 3 still stand, and §15.2 STEP 2's own precondition
                   requires STEP 0a AND STEP 0b AND STEP 1 together. WHAT CHANGED
                   IS WHICH OF THOSE IS UNSATISFIED.
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
               §5.1's "by rule" annotation on the composition -> Evidence row
               §25's amendment log
               ^ AN EARLIER REVISION OF THIS LIST ALSO NAMED "§13's `producer_token`
                 identifier refusal, where it reaches the SUBMITTING caller rather
                 than the composition". THAT ITEM IS WITHDRAWN — it is an INVALID
                 CROSS-CONTRACT REFERENCE that names a rule AI-14 §13 does not
                 contain — and §19 AMENDMENT 4 records it as a NO-OP. IT IS NOT PART
                 OF STEP 1'S WORK LIST, and withdrawing it changes NO rule: the
                 composition-only identifier prohibition and §22.1 B5's `NEVER`
                 clause both continue to stand exactly as they are.
           and, in the same change:
               scripts/ci/layer0_policy.py:3241   AI14_FORBIDDEN_IMPORTS
               tests/composition/test_composition_boundaries.py:151-176
               tests/composition/test_composition_boundaries.py:178-191
           OWNER         AI-14.
           PRECONDITION  STEP 0a — SATISFIED by AI-05 Amendment 4 (§5.3). No AI-14
                         amendment has been made; a met precondition is what
                         UNBLOCKS beginning one, and AI-14's owner begins it,
                         not AI-15 (§19, Amendment 1).
                         ^ RECORDED (§19 AMENDMENT 6): THE STEP HAS SINCE BEEN MADE,
                         BY ITS OWNER. AI-14 Amendment 2 (PR #90, merge
                         a98e389b91ee10858abc67e7c66509cd12fae9dc) delivered the
                         AUTHORIZATION change this step names, and AI-14 Amendment
                         4 (PR #96, merge
                         36d6ea92a8872dd9167412d8e39de063854b345d) records its
                         enumerated list as DISCHARGED ON AI-14'S SIDE. THE
                         SENTENCE ABOVE IS KEPT AS WHAT IT WAS. AI-15 DID NOT MAKE
                         THIS STEP, DOES NOT CLAIM IT, AND DOES NOT DECLARE IT ON
                         AI-14'S BEHALF: AI-14's owner made it, in AI-14's contract,
                         under AI-14's amendment rule.
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
           PRECONDITION  STEP 0a AND STEP 0b AND STEP 1. All three.
                         ^ RECORDED (§19 AMENDMENT 6): ALL THREE ARE NOW SATISFIED.
                         STEP 1 was made by AI-14's owner — AI-14 Amendment 2,
                         recorded as discharged by AI-14 Amendment 4 (PR #96) — and
                         AI-15 produced no part of it. STEP 2 IS STILL NOT MADE:
                         no production, non-test call site exists.
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
                         ^ RECORDED (§19 AMENDMENT 6): STEP 0a, STEP 0b AND STEP 1
                         are satisfied — STEP 1 by AI-14's owner, AI-14 Amendment 2,
                         recorded as discharged by AI-14 Amendment 4 (PR #96).
                         STEP 2 IS STILL NOT MADE, and this step cannot run before
                         it: there is no call site for the classification to name,
                         and a separately merged AI-14 part does not satisfy §22.1
                         (§17.2d).
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
    decision rather than inventing a rule. The order failed in THREE ways when this
    block was written, and it fails in TWO of them now:

        STEP 0b produces no decision            RESOLVED — §19 Amendment 3.
                                                This is no longer a way the order
                                                fails: AI-05 answered, implemented
                                                and tested the question, and
                                                CLOSED AI15-OPEN-1 in its own
                                                contract. THE ROW IS KEPT IN PLACE
                                                rather than deleted, so the record
                                                of what the freeze found stays
                                                legible. No owner decision is
                                                missing here any more.
        AI-14 declines STEP 1, or judges its    missing owner decision: AI-14
          vocabulary cannot express
          "authorized but not yet connected"
        no party accepts STEP 2                 missing owner decision: AI-14's,
                                                since designating it is AI-14's
                                                under STEP 1

    In either of the two that remain:
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
    FROZEN: neither AI-05 item is owned, requested or scheduled here. BOTH ARE NOW
            ANSWERED AND CLOSED BY THEIR OWNER: AI-05 Amendment 4 chose READING A,
            which closes §15.2's STEP 0a (§5.3, §19 Amendment 1); and AI-05
            Amendment 7 answered, implemented and tested producer authentication,
            which closes AI15-OPEN-1 and satisfies §15.2's STEP 0b (§9.2, §19
            Amendment 3). AI-15 RECORDED BOTH AND PRODUCED NEITHER.
            WHAT §16.2 STILL CARRIES ON AI-05'S SIDE IS A DIFFERENT ITEM: row 1′ —
            the §6.5 row and the own-contract clause for each phase whose facts
            would be admitted. That question was never this one, it is not moved by
            either closure, and §9.2's independence argument is what keeps the two
            apart.
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
                                                     — SATISFIED. ANSWERED,
                                                     IMPLEMENTED AND TESTED
                                                     (§19 Amendment 3)

    Eight changes, four owners. AI-15 owns none of them, and (viii) is the one an
    implementation is most likely to assume away — a working call site does not
    make the producer claim behind it true. IT IS NOW DISCHARGED, AND THE REASON IT
    WAS WORTH STATING IS UNCHANGED: it was discharged by ANSWERING, IMPLEMENTING
    AND TESTING the standard, not by assuming it away.
    TWO OF THE EIGHT ARE NOW DISCHARGED. (vii) was the first — AI-05 Amendment 4
    answered AI15-OPEN-2 — and (viii) is the second — AI-05 Amendment 7 answered,
    implemented and tested AI15-OPEN-1. The list is kept at eight rather than
    renumbered, so the record of what the freeze found stays legible; each
    satisfied item is marked in place, and each is marked ONLY for what it
    actually discharges. THE OTHER SIX STAND.
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
        STATUS  CLOSED. Closed by its OWNER, in the owner's contract, under the
                owner's amendment rule — AI-05 Amendment 7, merged by PR #88
                (9e1b4c451deed34605d021b4203fccd16dad4cd0). AI-15 RECORDS the
                closure and did not make it (§19 Amendment 3).
        CLOSED  the AI-05 owner. NOT by AI-15, and NOT by an implementation
          BY    decision: AI-15 wrote no code and added no test asserting an
                outcome, which is what the FROZEN clause below requires.
        EVIDENCE the closure rests on — implementation PR #87 (merge
                d09ce69ec1c0975c6d638d7861df2f11c44ec1d1) and CI run #301, in which
                46 process-isolated cases RAN and 0 were skipped, with
                `Layer 0 = PASS (24 checks)`. §19 Amendment 3 carries the links.
        GATES   NONE ANY MORE. It gated §15.2 STEP 2 AND STEP 3 and, through them,
                §8.3 condition 11; it no longer gates them, because STEP 0b is
                satisfied. WHAT STILL GATES THE WRITE IS STEP 1, row 1′, STEP 2 and
                STEP 3, and §17.2 rather than §17.2b is now where the import and the
                call are refused.
                ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS SATISFIED TOO — by its
                OWNER, not by AI-15 (AI-14 Amendment 2, PR #90; recorded as
                discharged by AI-14 Amendment 4, PR #96) — so §17.2 NO LONGER
                REFUSES THE IMPORT OR THE CALL. WHAT STILL GATES THE WRITE IS
                row 1′, a real non-test call site (STEP 2), the joint-delivery
                mechanism and STEP 3. B5 STILL CANNOT SATISFY THE CONNECTED GATE,
                because there is still no call site and no record — but the reason
                is no longer this item.
        NOTE    SOLVED, AND THE API IS STILL NOT SAFE ON ITS OWN (§9.2). The API
                accepts any caller; what changed is that `admit()` now
                authenticates the producer claim BEFORE any typed record exists, so
                a caller that appeared would have to present an authenticated claim
                to store anything. "No caller exists" remains a RECORDED finding
                about the tree (§3.1-§3.3) and still not a runtime barrier.
        RECORDED  the three parts §15.2 STEP 0b measures — MECHANISM DEFINED
                (Amendments 5 and 6, counted once), RUNTIME IMPLEMENTATION
                IMPLEMENTED (PR #87, §31.3's Layer 0 enforcement included), and
                ACCEPTANCE TESTS RUN (run #301). THE ITEM WAS CLOSED ON THAT
                EVIDENCE AND NOT BEFORE IT.
        NOT     AI-11 §21.1's OPEN-1. That one is WHICH PRODUCERS EXIST; this one
                is WHETHER A PRODUCER CLAIM IS TRUSTWORTHY. §9.2 works the
                independence argument in both directions. CLOSING THIS ONE MOVES
                THE OTHER NOWHERE: no §6.5 row was added, and §16.2 still carries
                row 1′ as a live blocker with AI-05 as one of its owners.

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
FROZEN: AI15-OPEN-3 and AI15-OPEN-4 MUST NOT be closed by an AI-15-B
        implementation decision (AI-14 §2: "An OPEN item MUST NOT be closed by an
        implementation decision").
        ^ THIS CLAUSE NAMED THREE ITEMS UNTIL §19 AMENDMENT 3 AND NAMES TWO NOW.
        AI15-OPEN-1 left the list the same way AI15-OPEN-2 did and by the same
        route: ITS OWNER closed it, in the owner's contract, under the owner's
        amendment rule. THE RULE IS UNCHANGED AND IS NOT WEAKENED BY THAT — it
        still forbids closing an open item by an implementation decision, and
        neither departure was one.
RECORDED: AI15-OPEN-2 left this list the only way an OPEN item may leave it — its
        OWNER closed it, in the owner's contract, under the owner's amendment
        rule. The rule is unchanged and is not weakened by that: it names the
        three that remain, and a fourth could not be closed the way AI15-OPEN-2
        was unless a phase that owns the question made the decision.
        ^ THIS PARAGRAPH WAS WRITTEN WHEN THREE REMAINED AND IS KEPT AS WHAT IT
        WAS. AI15-OPEN-1 has since left the list the SAME way, by AI-05 Amendment
        7 — and the sentence "a fourth could not be closed the way AI15-OPEN-2 was
        unless a phase that owns the question made the decision" is precisely what
        governed it: AI-05 owns the question, and AI-05 made the decision. TWO
        REMAIN.
FROZEN: AI15-OPEN-1 gated §15.2's STEP 0b directly, so an implementation that
        "resolved" it by choosing while building would have been the exact failure
        this clause names. IT WAS NOT RESOLVED THAT WAY, and §19 Amendment 3
        records the shape of the closure: the OWNER answered the question in the
        owner's contract BEFORE any implementation existed (Amendment 5), and the
        implementation then implemented THAT standard rather than choosing one.
        AI15-OPEN-2's gate at STEP 0a is satisfied and no longer carries this
        exposure (§5.3).
```

### 16.2 BLOCKED

```text
B5 — composition -> Evidence
    BLOCKED. Four of the seven blockers below are live. THREE ARE SATISFIED: row
    0a, answered by AI-05 Amendment 4 (§5.3, §19 Amendment 1); row 0b, answered,
    implemented and tested by AI-05 and CLOSED BY ITS OWNER in AI-05's contract by
    Amendment 7 (§9.2, §19 Amendment 3); and row 1, DELIVERED BY ITS OWNER — AI-14
    Amendment 2 (PR #90, merge
    a98e389b91ee10858abc67e7c66509cd12fae9dc), recorded as discharged by AI-14
    Amendment 4 (PR #96, merge
    36d6ea92a8872dd9167412d8e39de063854b345d) (§19 Amendment 6). SATISFYING A
    BLOCKER IS NOT SATISFYING THE ITEM — B5 stays BLOCKED, and no seam is
    CONNECTED.

    order  blocker                                       owner                 gates
    -----  --------------------------------------------  --------------------  --------------
    0a     AI15-OPEN-2 answered — which reading of       AI-05                 STEP 1
           AI-05 §7's "WROTE" governs (§5.3)                                — SATISFIED.
                                                                               READING A.
                                                                               STEP 1 IS NOW
                                                                               UNBLOCKED, NOT
                                                                               MADE
    0b     AI15-OPEN-1 answered, implemented and         AI-05                 STEP 2 AND STEP 3
           tested — how a producer claim is                                 — SATISFIED.
           established (§9.2)                                                  ANSWERED,
                                                                               IMPLEMENTED
                                                                               (PR #87) AND
                                                                               TESTED (run #301:
                                                                               46 RAN / 0
                                                                               SKIPPED); CLOSED
                                                                               BY ITS OWNER
                                                                               (§19 Amendment 3).
                                                                               STEP 2 AND STEP 3
                                                                               REMAIN BLOCKED BY
                                                                               1, 1′, 2 AND joint
    1      AI-14 amendment #1 (authorization) +          AI-14                 STEP 2
           layer0 :3241 + the two composition                                 — SATISFIED.
           assertions (§15.2)                                                  DELIVERED BY ITS
                                                                               OWNER (AI-14
                                                                               Amendment 2,
                                                                               PR #90) AND
                                                                               RECORDED AS
                                                                               DISCHARGED
                                                                               (AI-14 Amendment
                                                                               4, PR #96, §19
                                                                               Amendment 6).
                                                                               STEP 2 REMAINS
                                                                               BLOCKED BY 1′,
                                                                               2 AND joint
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
    FROZEN: 0b IS INDEPENDENT of 1 and 1'. A call site that works and a token that
            is registered together satisfy no part of 0b (§15.3) — WHICH IS WHY
            SATISFYING 0b MOVED NOTHING ON 1 OR 1′, AND WHY SATISFYING 1 OR 1′
            WOULD MOVE NOTHING ON 0b. The independence runs in both directions and
            is unchanged by 0b's satisfaction.
    FROZEN: 0b GATES STEP 2, SO IT GATES THE WRITE. Before it is complete, no
            production call site that can execute admission may exist (§15.2,
            §17.2b). Reporting the seam as NOT CONNECTED does not satisfy 0b: a
            live writer stores, and what it stored stays stored (§6.1).
            ^ RECORDED (§19 Amendment 3): 0b IS NOW COMPLETE, so THIS GATE IS
            DISCHARGED. It was never the only gate on the write, and discharging
            it moves nothing on 1, 1′, 2, 3 or joint — all of which still stand,
            and §17.2 still refuses the import and the call.
    FROZEN: the classification step (3) MUST NOT run before 0b. A prerequisite
            amendment may not assert the outcome of the work it precedes (§15.2).
            ^ UNCHANGED, AND NOW SATISFIABLE IN THAT ORDER: 0b is complete, so
            STEP 1 may precede STEP 3 without STEP 3 asserting anything it does
            not yet have. STEP 1 has not been made (§15.2).
            ^ RECORDED (§19 AMENDMENT 6): STEP 1 HAS SINCE BEEN MADE, BY AI-14 —
            AI-14 Amendment 2 (PR #90), recorded as discharged by AI-14 Amendment 4
            (PR #96). THE ORDER THIS CLAUSE FIXES WAS KEPT: STEP 1 came before
            STEP 3, and STEP 3 still has nothing to assert — no call site exists.
    FROZEN: the joint-delivery row is the blocker an implementer is most tempted
            to route around. Authoring AI-14's contract parts to avoid it is
            §15.2's owner-rule bypass and MUST NOT be merged.
    FROZEN: SATISFYING 0a MOVED NOTHING TO AI-15. STEP 1 is AI-14's to make and is
            not made; STEP 0b is AI-05's and is not answered. This document records
            that one owner answered one question, and it authorizes nothing.
            ^ KEPT AS WHAT IT WAS. Its LAST clause is superseded by §19 Amendment 3
            and the rest of it is not: 0b HAS since been answered, implemented and
            tested by its owner, and THAT moves nothing to AI-15 either — STEP 1 is
            still AI-14's to make and is still not made. A SECOND owner answered a
            SECOND question, and the sentence "this document records that an owner
            answered a question, and it authorizes nothing" is now true of two rows
            instead of one.
            ^ RECORDED (§19 AMENDMENT 6): AND A THIRD OWNER HAS NOW ANSWERED A THIRD
            ONE. STEP 1 IS MADE — by AI-14's owner, AI-14 Amendment 2 (PR #90),
            recorded as discharged by AI-14 Amendment 4 (PR #96) — and, like the
            two before it, THAT MOVES NOTHING TO AI-15 except the STATUS this
            amendment records. AI-15 DID NOT MAKE STEP 1 and does not own its
            completion. WHAT REMAINS ON THIS ROW'S SIDE: row 1′, a real non-test
            call site (STEP 2), the joint-delivery mechanism and STEP 3.
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
```

```text
RECORDED (§19 AMENDMENT 6) — THE PREMISE THIS SECTION RESTS ON IS SATISFIED, AND
THIS SECTION'S TEXT IS UNCHANGED.

    ^ THIS BLOCK ALSO CLOSES THE CODE BLOCK ABOVE, WHICH HAD NO CLOSING FENCE: the
    `### 17.2b` heading and its first block were being rendered INSIDE §17.2's
    block. The fence is restoration, not a change to this section's text. Three
    other sites in this document have the same defect and are NOT fixed here — they
    are named in §19 Amendment 6 so they are not discovered later.

    STEP 1 HAS BEEN MADE, BY ITS OWNER. AI-14 Amendment 2 (PR #90, merge
    a98e389b91ee10858abc67e7c66509cd12fae9dc) delivered the AUTHORIZATION change,
    and AI-14 Amendment 4 (PR #96, merge
    36d6ea92a8872dd9167412d8e39de063854b345d) records its enumerated list as
    discharged on AI-14's side. ALL FOUR ITEMS ABOVE ARE THEREFORE DELIVERED:
    `composition/` MAY import `plugins.evidence`; `AI14_FORBIDDEN_IMPORTS` is EMPTY;
    the composition assertion now CHECKS THE CALL instead of refusing the import
    (its current site is tests/composition/test_composition_boundaries.py:411, not
    the pre-Amendment-2 line numbers above); and AI-14 §5.1, §22.1 B5 and Appendix A
    were restated by that same amendment.

    WHAT THIS DOES NOT DO. It permits nothing by itself and it moves nothing. B5 IS
    STILL BLOCKED, NO SEAM IS CONNECTED, AND AI-15-B IS STILL NOT STARTED.
    `AI14_FORBIDDEN_IDENTIFIERS` — the `producer_token` entry INCLUDED —
    `AI14_FORBIDDEN_CALLABLES`, the forbidden stdlib roots, the foreign-root rule and
    the one-way rule ALL STAND, and the ownership rule this section exists to protect
    is UNCHANGED: AI-15-B MUST NOT author AI-14's contract, Layer 0, test or
    classification parts, and MUST NOT reach the same effect by another route
    (§17.2d, §15.2 STEP 2's FROZEN rules).

    WHAT REFUSES A PRODUCTION CALL SITE NOW, stated so this section is not read as a
    refusal it no longer is: the JOINT-DELIVERY requirement (§17.2d — STEP 2 and
    STEP 3 merge as ONE change, and no owner-approved mechanism is named); ROW 1′ for
    any event but AI-06's; and AI-14's own composition assertion, which the
    connecting change must amend as part of AI-14's part.
```

### 17.2b The §15.2 STEP 0b gate — it covered the WRITE, and it is now discharged

```text
BLOCKED until AI-05 has answered, implemented AND TESTED AI15-OPEN-1 — AND THAT
CONDITION IS NOW MET (§15.2, §16.2 row 0b, §19 Amendment 3):
    ANY PRODUCTION CALL SITE that can actually execute `admit_to_store` against a
      real store, or that can otherwise cause an EvidenceRecord to be persisted.
      This is the substantive half of the gate, and it came FIRST.
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
RECORDED (§19 Amendment 3) — WHAT THIS GATE DID, AND WHAT ITS DISCHARGE DOES AND
DOES NOT DO. THE GATE IS DISCHARGED: AI-05 answered the question (Amendments 5 and
6), implemented it (PR #87) and tested it (run #301, 46 RAN / 0 skipped), and
CLOSED the item in its own contract (Amendment 7). AI-15 did none of that and
records it only.

    WHAT ITS DISCHARGE DOES NOT DO, AND THIS IS THE WHOLE OF THE CAVEAT:

        IT DOES NOT PERMIT A PRODUCTION CALL SITE, BECAUSE THIS WAS NEVER THE
        ONLY THING REFUSING ONE. §17.2 refuses the import and the call until
        AI-14's STEP 1; §16.2's rows 1, 1′, 2 and 3 all stand; and §15.2 STEP 2
        requires STEP 0a AND STEP 0b AND STEP 1 together, of which STEP 1 is still
        missing.
        ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS NO LONGER MISSING — it was made by
        AI-14's owner (AI-14 Amendment 2, PR #90; recorded as discharged by AI-14
        Amendment 4, PR #96), and §15.2 STEP 2's precondition is satisfied with it.
        THIS CAVEAT IS NOT THEREBY REPEALED: it still does not permit a production
        call site, and what refuses one now is the JOINT-DELIVERY requirement
        (§17.2d), ROW 1′ for any event but AI-06's, and §16.2's remaining rows.
        B5 IS STILL BLOCKED AND AI-15-B IS STILL NOT STARTED.

        IT DOES NOT MOVE THE B5 CLASSIFICATION. The three claims listed above
        remain blocked, and the reason is now the ABSENCE of a call site and of a
        record rather than the state of AI15-OPEN-1.

        IT DOES NOT SATISFY §8.3 CONDITION 11 FOR A RECORD. Condition 11 is a
        condition ON the record, and no record exists. What is now true is that the
        MECHANISM condition 11 names — the standard is defined, implemented, and
        shown by tests to hold — EXISTS. §8.3 is UNCHANGED by this amendment, and
        condition 11 is left in its original words.

        IT DOES NOT AUTHORIZE AI-15-B TO START. AI-15-B remains NOT STARTED and
        BLOCKED (§16.2, §17.5).
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
    THE WRITE ITSELF, until §15.2 STEP 1 is made and STEP 2 is delivered with
    STEP 3 in ONE change (§17.2, §16.2). This is the clause that survives every
    other amendment, and it is the one the earlier revision of this document missed
    TWICE OVER: a registered token and a working call site together still do not
    establish who wrote the record (§4.3); and for as long as that is true, THE
    WRITER MUST NOT RUN.
    ^ RECORDED (§19 Amendment 3): "UNTIL §15.2 STEP 0b LANDS" WAS ONE OF THIS
    CLAUSE'S CONDITIONS AND IS NO LONGER ONE OF THEM — 0b HAS LANDED. The clause
    is otherwise unchanged, and it never rested on 0b alone: STEP 1 is still not
    made, STEP 2 has not been delivered, and the joint-delivery mechanism is still
    unnamed. WHAT MOVED IS REAL BUT NARROW. "A registered token and a working call
    site together do not establish who wrote the record" is now a statement about
    what the API does NOT do on a caller's behalf, rather than about a mechanism
    that does not exist: §30 step 7b exists and runs (§19 Amendment 3). THE WRITER
    ^ RECORDED (§19 AMENDMENT 6): STEP 1 IS NOW MADE — by AI-14's owner, AI-14
    Amendment 2 (PR #90), recorded as discharged by AI-14 Amendment 4 (PR #96) —
    SO ONE OF THIS CLAUSE'S TWO REMAINING CONDITIONS IS SATISFIED. The clause is
    otherwise unchanged, and what still refuses the write is STEP 2 — not
    delivered — TOGETHER WITH STEP 3 in ONE change, and the unnamed joint-delivery
    mechanism. B5 IS STILL BLOCKED, NO SEAM IS CONNECTED, AND AI-15-B IS STILL NOT
    STARTED. THE WRITER
    STILL MUST NOT RUN.
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
    ^ RECORDED (§19 Amendment 3): THREE CRITERIA IN THIS LIST NAME "while
    AI15-OPEN-1 is OPEN" — two above and the STEP 0b / §17.2b one — AND AI15-OPEN-1
    IS CLOSED, so those antecedents no longer hold. THE CRITERIA ARE NOT THEREBY
    DISCHARGED, and none of them is deleted. Each still names a way this document
    would have failed: a CONNECTED claim still needs a call site named by
    file:line; a production call site that can persist a record is still
    forbidden, now by §17.2 and §16.2's remaining rows; and a state satisfying
    conditions 1-10 is still not CONNECTED. WHAT CHANGED IS THE NAME OF THE
    CONDITION THAT REFUSES THEM, NOT THAT THEY ARE REFUSED.
```

---

## 19. Amendment and normative language

```text
FROZEN. This document was frozen by the merge of PR #78, and it has been amended
SIX TIMES since — Amendment 1, Amendment 2, Amendment 3, Amendment 4, Amendment 5 and
Amendment 6, below. The line this block replaced read "PROPOSED (this document's class
until the merge that freezes it)", which was true while the freeze was a proposal and
false once it merged. It is corrected here rather than left to contradict the amendment
log beside it. The count was "TWICE" until Amendment 3, "THREE TIMES" until Amendment 4,
"FOUR TIMES" until Amendment 5 and "FIVE TIMES" until Amendment 6, and each increment of
it has been made in the same change that appended the amendment it counts.
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
    §7.2     the T2 topology note's inherited objection is recorded as SETTLED by
              AI-05 Amendment 4: a submitter MAY differ from the producer, so a
              submitting composition does not thereby author a false producer
              claim. The reading is AI-05's decision and is upstream of this
              document. The note states in the same place what that is NOT — no
              authorization, no production call site, no connection — so §7.2 and
              §7.3 read consistently rather than one unblocking what the other
              still forbids
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
    SECURITY  this amendment's own SECURITY IMPACT block is written to separate
      IMPACT  three things the first draft ran together — what it does NOT add
              (no authentication, no trust root, no new admission check), what
              it DOES (records a choice AI-05 already made), and what FOLLOWS
              WITHOUT BEING AUTHORIZED (STEP 1 becomes startable; nothing is
              authorized). The rewording changes no obligation and no boundary;
              it narrows a claim that was broader than the change

    NOTHING ELSE IN THIS DOCUMENT CHANGED. No clause of §6, §8, §9.5, §10-§13 or
    §17.1-§17.2d is touched, and no row of §20 moves.
```

```text
SECURITY IMPACT

    NO NEW SECURITY CONTROL, AND NO AUTHENTICATION — stated precisely, because
    the broader claim "nothing security-relevant changed" would be false.

    WHAT THIS AMENDMENT DOES NOT ADD
        no authentication mechanism, no trust root, no signature, no key, no
        credential path and no new admission check
        no claim that a record, a producer claim or a submitter is trusted
        no change to what AI-05 admits or rejects, and no runtime behaviour at
          all — this amendment is documentation
        AI-05 Amendment 4 says the same in its own words: registry validation,
          producer authentication and submitter identity are three different
          checks, and it performs only the first

    WHAT IT DOES
        it RECORDS a semantic choice AI-05 had already made and put IN FORCE
        (Amendment 4, PR #80), and it closes AI15-OPEN-2 in AI-15's inventory

    WHAT FOLLOWS, AND WHAT IS NOT THEREBY AUTHORIZED
        STEP 1 now has its semantic precondition met, so AI-14 may BEGIN its
          amendment. A met precondition is not an authorization: no AI-14
          amendment has been made, and this document makes none
        AI15-OPEN-1 REMAINS OPEN. No producer authentication exists, and §15.2
          STEP 0b still forbids creating or running any production call site
          that can execute admission and persist a record
        AI-11 §21.1's OPEN-1, AI15-OPEN-3 and AI15-OPEN-4 all remain OPEN

    SO: this amendment adds no security control and grants no authority. It is
    equally true that two things DID move — AI15-OPEN-2 is closed, and STEP 1
    became startable. Neither is a control, a permission, or a change in what
    the system will accept.
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

#### Amendment 2 — AI-05 Amendments 5 and 6 are recorded, and the OPEN-1 reason is corrected
(2026-10-11)

```text
IN FORCE on the merge of the change that carries it. The merge IS the approval, and
the text below is the final text.
```

```text
WHAT WAS FOUND

    This contract described AI15-OPEN-1 AS THOUGH THE STANDARD WERE STILL UNDECIDED.
    §9.2 asked "how is a producer claim ESTABLISHED" and recorded that the answer was
    MISSING; §14.2 said "AI-05 still owes a producer authentication standard,
    implemented and tested". Both were true when they were written and NEITHER IS TRUE
    NOW: AI-05 has defined the standard and frozen its configuration, in its own
    contract, under its own amendment rule.

    The correction is a RECORD of AI-05's acts, not a new AI-15 rule. Nothing here
    resolves AI15-OPEN-1, and nothing here is progress on it.

    It is also the SAME KIND of correction Amendment 1 made for AI15-OPEN-2, and it is
    made the same way: AI-15 records what the owner did, in the owner's contract, and
    claims no part of it.
```

```text
THE TWO UPSTREAM AI-05 AMENDMENTS, AND THEIR MERGE EVIDENCE

    AI-05 Amendment 5   DEFINES the producer-authentication standard.
                        merged as   7017bf577f654cb6dea0e8d5e50a27f334117b73
                                    (PR #83, a true two-parent merge)
                        what it adds to AI-05   §7.3 (the standard: a designated
                                    deployment mapping, a proof, Ed25519
                                    verification over a byte-exact signed input, the
                                    AI-05-CJ-1 canonical profile, six reason codes,
                                    fail-closed semantics) and §30 step 7b.

    AI-05 Amendment 6   FREEZES the trust configuration and its lifecycle.
                        merged as   cee1f8c9ae07837e0ebae0be3f8ab2e0113e6973
                                    (PR #85)
                        what it adds to AI-05   §7.3.11 (the ONE source
                                    WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG, its
                                    strict JSON shape, its key encoding, its ONE
                                    READER plugins/evidence/producer_auth.py, the
                                    process-lifetime lifecycle, the startup-order
                                    requirement, and the failure code) and §31.3
                                    (the Layer 0 exception, the four static
                                    enforcement rules, the test-harness boundary and
                                    the trust-boundary qualification).

    EVIDENCE BASE   docs/AI-05_EVIDENCE_EXECUTION_PLAN.md, blob
                    b89c811e9ee8da2f576b938378501c0578151dd1 at the merge commit
                    above. Both amendments are recorded in that contract's own
                    §34.3 amendment log, as Amendments 5 and 6.

    BOTH ARE DOCUMENTATION CHANGES. Neither ships a runtime control, implements §30
    step 7b, adds a test, or changes Layer 0. AI-05's own record says so.
```

```text
WHAT CHANGED IN THIS DOCUMENT

    §9.2      "WHAT IS MISSING — a decision about HOW a claim is established" is
              replaced. The decision HAS BEEN MADE, and the clause now states what is
              actually missing: the implementation, the Layer 0 enforcement and the
              §7.3.7 acceptance tests. It also states, in the clause, the THREE
              THINGS THAT MUST NOT BE COLLAPSED — the standard is DEFINED, the
              control is NOT IMPLEMENTED, and no test has DEMONSTRATED that it holds.
              "HOW THE QUESTION IS ANSWERED" is put in the past tense and records
              that AI-05 made the act; the independence argument from AI-11 §21.1's
              OPEN-1 immediately below it is UNCHANGED.
    §14.2     "AI-05 still owes a producer authentication standard, implemented and
              tested" is replaced. The reason AI15-OPEN-1 remains OPEN is no longer
              that the standard is undefined; what AI-05 owes is the RUNTIME. Both
              upstream merges are named with their SHAs, and the row states that
              AI-11 §21.1's OPEN-1 is not moved by either amendment.
    §16.1     the AI15-OPEN-1 inventory row gains a RECORDED line naming the two
              amendments and restating that the item stays OPEN. NO FIELD OF THE ROW
              MOVES: OWNER, STATUS, GATES and NOT are as they were, and the row's
              separation from AI-11 §21.1's OPEN-1 is untouched.
    §4.3      the FROZEN clause "no step of §30 answers it" is corrected to "§30
              step 7b IS the step that answers it, and NOTHING PERFORMS THAT STEP".
              THE RULE IS UNCHANGED AND IS NOT WEAKENED — registry membership is
              still a well-formedness check and is still not producer authentication.
              What is corrected is the FACT: §30 now contains such a step (Amendment
              5) and no code executes it. Leaving the clause as written would have
              asserted that §30 has no step 7b, in a document that describes step 7b.
    §15.2     STEP 0b gains a STATUS line. NO REQUIREMENT MOVES: OWNER,
              PRECONDITION, OUTPUT and GATES are as they were, and OUTPUT still
              demands a mechanism AND its implementation AND its tests. The STATUS
              line records that ONE OF THE THREE is supplied and the step is
              therefore UNSATISFIED.
    §16.2     row 0b's description is unchanged. The status block in §17/Status is
              corrected: "STEP 0b has no answer" becomes "STEP 0b is UNSATISFIED —
              the MECHANISM is DEFINED and the IMPLEMENTATION and TESTS are NOT".
    §19 head  the preamble now says the document has been amended TWICE and names
              both amendments.

    NOTHING ELSE IN THIS DOCUMENT CHANGED. No clause of §6, §8, §10-§13, §17.1-§17.2d
    or §20 moves, no row of §16.2 moves, no ownership changes, and §19's amendment
    rule is not restated in weaker words.
```

```text
WHY THE CORRECTION, AND WHAT IT IS FOR

    A reader arriving at §9.2 or §14.2 was told the standard did not exist. That
    reader would draw one of two wrong conclusions: that AI-05 had done nothing, or —
    worse — that because the gap was "undefined", closing it was somebody's design
    work still to be scheduled. Both are wrong now. THE STANDARD EXISTS AND IS
    FROZEN; THE CODE DOES NOT. A contract that leaves the first half unsaid makes the
    second half look like an omission rather than the whole of the remaining work.

    THIS MATTERS MOST FOR §15.2 STEP 0b, WHICH IS WHERE A READER CHECKS WHETHER THE
    WRITE MAY PROCEED. STEP 0b requires a mechanism AND its implementation AND tests
    showing it holds. ONLY THE FIRST OF THOSE THREE IS SUPPLIED: the mechanism is
    DEFINED, and the trust configuration Amendment 6 froze is PART OF that definition
    rather than a second delivery beside it. THE RUNTIME IMPLEMENTATION IS NOT
    IMPLEMENTED AND THE ACCEPTANCE TESTS ARE NOT_RUN, so the step is UNSATISFIED — and
    it would stay unsatisfied if both amendments were ten times longer, because
    neither is code.
```

```text
SECURITY IMPACT

    NONE, AND THE POINT IS THAT DEFINING A CONTROL IS NOT DEPLOYING ONE.

    WHAT THIS AMENDMENT DOES
        it RECORDS two AI-05 amendments and corrects the description of what AI-05
          still owes
        it keeps §15.2 STEP 0b's three parts apart — a MECHANISM that is DEFINED,
          a RUNTIME IMPLEMENTATION that is NOT IMPLEMENTED, and ACCEPTANCE TESTS
          that are NOT_RUN — and records that Amendments 5 and 6 supply the FIRST
          of them ONCE, the configuration freeze being part of the definition

    WHAT IT DOES NOT ADD
        no authentication, no check, no key, no configuration, no Layer 0 rule and no
          runtime behaviour of any kind — this amendment is documentation, and so are
          the two it records
        no claim that a producer claim is authenticated, or that any record's
          producer has been established
        NO ATTACK IS DEFEATED BY IT. §30 step 7b is performed by nothing today, and
          §7.3's standard binds a code path no caller reaches.
        no change to what AI-05 admits or rejects
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves any responsibility into AI-15. Guard
    remains the only component with an AUTHORIZES entry. An authenticated producer
    claim is not an approval, a permission, a capability or a Guard result. No
    producer token is admitted, no §6.5 row is added, and no ownership changes.
```

```text
STATUSES UNCHANGED — EVERY ONE OF THEM

    AI15-OPEN-1             OPEN, and the OWNER is unchanged: AI-05. WHAT MOVED IS
                            THE REASON, NOT THE STATUS. Neither amendment closes it.
    AI-15 §15.2 STEP 0b     UNSATISFIED. It requires THREE things: a mechanism, its
                            implementation, and tests showing it holds. ONE IS
                            SUPPLIED — the mechanism is DEFINED, and Amendment 6's
                            configuration freeze is PART OF that definition, not a
                            delivery beside it. THE RUNTIME IMPLEMENTATION IS NOT
                            IMPLEMENTED and the ACCEPTANCE TESTS ARE NOT_RUN.
    §8.3 condition 11       UNSATISFIED. It is discharged by §7.3.7's tests, and
                            none has been run.
    AI15-OPEN-2             CLOSED under AI-05 Amendment 4 (READING A), under the
                            owner's act, exactly as Amendment 1 recorded. NOT
                            reopened, re-argued or restated in weaker words.
    AI15-OPEN-3             OPEN (AI-04). Untouched.
    AI15-OPEN-4             OPEN (AI-13 / AI-14). Untouched.
    AI-11 §21.1's OPEN-1    OPEN, INDEPENDENT, AND UNRESOLVED. It asks WHICH
                            PRODUCERS EXIST. A DEFINED STANDARD DOES NOT ADMIT A
                            TOKEN, A FROZEN CONFIGURATION DOES NOT ADMIT A TOKEN,
                            AND AN AUTHENTICATION IMPLEMENTATION WOULD NOT ADMIT
                            ONE EITHER. §9.2's independence argument holds in both
                            directions and is unchanged.
    row 1′                  UNSATISFIED and SEPARATE, for the same reason. §16.2's
                            FROZEN clause that 0b is independent of 1 and 1′ is
                            untouched.
    production writer       NONE, and NOT AUTHORIZED. §17.2b's prohibition is not
                            lifted by a definition, by a frozen configuration, or by
                            both together.
    B5                      BLOCKED, and NOT CONNECTED. No classification moves.
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not close AI15-OPEN-1, and no clause here may be cited to suggest it did
    it does not satisfy §15.2 STEP 0b, §8.3 condition 11, or any part of either
    it does not treat a DOCUMENTATION change as an IMPLEMENTATION
    it does not close, weaken, rename or claim progress on AI-11 §21.1's OPEN-1
    it does not close AI15-OPEN-3 or AI15-OPEN-4
    it does not mark B5 CONNECTED or authorize a production Evidence writer
    it does not modify AI-05, AI-11, AI-13 or AI-14's contract, or any other phase's
    it does not make AI-14's STEP 1 or STEP 3
    it does not run any §7.3.7 acceptance test, and claims no result from one
    it does not turn any NOT_RUN, BLOCKED or UNKNOWN into PASS
    it does not assert that CI success on a documentation PR is evidence about
      producer authentication — it is evidence about documentation, and nothing else
```

---

#### Amendment 3 — AI-05 producer authentication is implemented, tested, and closed by its owner
(2026-10-11)

```text
IN FORCE on the merge of the change that carries it. There is no awaiting-review
marker on this amendment: the merge IS the approval, and the text below is the
final text.
```

```text
WHAT WAS FOUND

    THIS CONTRACT DESCRIBED AI15-OPEN-1 AS UNIMPLEMENTED, AND THAT STOPPED BEING
    TRUE. Amendment 2 corrected the REASON the item was open — the standard had
    been defined — and recorded, correctly for its date, that the runtime
    implementation and the acceptance tests did not exist. THEY EXIST NOW. AI-05
    implemented the mechanism (PR #87), CI executed its acceptance tests
    (run #301), and AI-05's owner recorded the result and CLOSED the item in
    AI-05's own contract (PR #88, AI-05 Amendment 7).

    A READER ARRIVING AT §9.2, §14.2, §15.2, §16.1, §16.2 OR THE STATUS BLOCK
    WOULD HAVE BEEN TOLD THE CONTROL WAS NOT BUILT, AND WOULD HAVE CONCLUDED THAT
    THE WRITE WAS STILL GATED BY §15.2 STEP 0b. IT IS NOT. The gate is discharged,
    and the blockers that remain are different ones with different owners.
```

```text
WHO DECIDED WHAT — THE OWNERSHIP IS THE POINT, AND IT IS STATED FIRST

    THE DECISION IS AI-05'S. AI15-OPEN-1 is AI-05's item (§9.2, §16.1): it asks
    how a producer claim is ESTABLISHED to AI-05 §7's standard, which is a question
    about AI-05's admission contract, and §9.2 records that neither AI-15 nor any
    other phase may answer it for AI-05.

    THE CLOSURE HAPPENED IN AI-05'S CONTRACT, MADE BY AI-05 AMENDMENT 7, under
    AI-05's amendment rule (§34 of that document). AI-15 DID NOT RESOLVE IT, DID
    NOT CONTRIBUTE TO RESOLVING IT, AND DID NOT APPROVE IT. This amendment is a
    RECORD of an owner's act, in the same shape as Amendments 1 and 2, and it takes
    no part of the act for AI-15.

    THE ROUTE IS THE ONE §16.1 NAMES FOR AN OPEN ITEM TO LEAVE THE LIST: its OWNER
    closed it, in the owner's contract, under the owner's amendment rule. That is
    how AI15-OPEN-2 left, and it is how AI15-OPEN-1 left. NO ITEM HAS LEFT THIS
    LIST BY AN IMPLEMENTATION DECISION, and the FROZEN clause in §16.1 forbidding
    that is unchanged.

    THE UPSTREAM AUTHORITY FOR THE CLOSURE IS PR #88, merge commit
    9e1b4c451deed34605d021b4203fccd16dad4cd0 — a true two-parent merge of
    d09ce69ec1c0975c6d638d7861df2f11c44ec1d1 and
    a10157a460419387178c70bd0413ea52526750c6. THAT COMMIT, AND NOT THIS ONE, IS
    WHERE AI15-OPEN-1 WAS CLOSED, and a reader who wants the closure itself must
    read AI-05's §34.3 Amendment 7, not this record.

    THIS AMENDMENT SYNCS AI-15'S OWN STATUS TO THAT FACT. It changes no AI-05
    clause, no AI-05 decision, and no AI-05 status; AI-05's contract remains the
    authority for all four.
```

```text
§15.2 STEP 0b — THE THREE PARTS, STATED SEPARATELY, EACH ON ITS OWN EVIDENCE

    §15.2 requires "a mechanism, PLUS its implementation and tests". THE THREE ARE
    COUNTED HERE AS THREE, because collapsing them is the error this document has
    warned about at every stage — and because two of the three arrived by different
    kinds of act, in different repositories-of-record, at different times.

    requirement              status        what supplies it
    -----------------------  ------------  --------------------------------------
    MECHANISM                DEFINED       AI-05 Amendment 5 (§7.3, §30 step 7b)
                                           DEFINES the standard; AI-05 Amendment 6
                                           (§7.3.11, §31.3) FREEZES its designated
                                           trust configuration, its encoding, its
                                           ONE READER, its lifecycle and the
                                           static enforcement it requires.
                                           THE TWO COUNT ONCE — the configuration
                                           freeze is PART OF the definition, not a
                                           second delivery beside it — and both
                                           are DOCUMENTATION changes.

    RUNTIME IMPLEMENTATION   IMPLEMENTED   PR #87, merge commit
                                           d09ce69ec1c0975c6d638d7861df2f11c44ec1d1.
                                           §30 step 7b is performed by
                                           plugins/evidence/producer_auth.py,
                                           called from `admission.admit()` BEFORE
                                           any typed record exists; §7.3.11's
                                           startup edge is in
                                           plugins/evidence/__init__.py.

    ACCEPTANCE TESTS         RUN           CI run #301, on the merged head:
                                           https://github.com/Li20771/AI-Security-Research-Workbench/actions/runs/38146118977
                                           46 process-isolated cases that RAN, 0
                                           skipped, across §7.3.2's eight trust
                                           configurations.

    LAYER 0 IS NOT A FOURTH PART AND IS NOT A DOCUMENTATION CLAIM. Amendment 6
    obliged §31.3's FOUR STATIC RULES, and those obligations belong to the
    RUNTIME IMPLEMENTATION — they are obligations on the change that implements the
    mechanism, not a deliverable of their own. PR #87 IMPLEMENTS THEM
    (`check_evidence_producer_authentication()` in scripts/ci/layer0_policy.py), and
    run #301 reports `Layer 0 = PASS (24 checks)` including
    `evidence producer authentication boundary`. THE RULES ARE ENFORCED, NOT MERELY
    STATED, and that is checked by a passing CI job rather than asserted here.

    THE NUMBER, AND NOT THE RUN'S STATUS. §31.3 froze the rule that a report must
    carry the number of process-isolated cases that RAN rather than the number that
    passed or the run's status, because that suite exits 0 both when its cases pass
    and when a case was skipped. THE NUMBER IS 46 RAN AND 0 SKIPPED, counted from
    the run's own job log, and it is stated instead of "the step was green". The
    run's `success` is recorded BESIDE it as the weaker evidence it is.
```

```text
AI-11 §21.1's OPEN-1 — INDEPENDENT, AND MOVED NOWHERE BY THIS

    AI-11 §21.1's OPEN-1 asks WHICH PRODUCERS EXIST: no §6.5 row exists for AI-08 /
    AI-10 / AI-11 / AI-13, so no record from those phases can be admitted at all.
    AI15-OPEN-1 asked WHETHER A PRODUCER CLAIM IS TRUSTWORTHY. §9.2 works the
    independence argument in both directions and it is UNCHANGED by this amendment.

    AUTHENTICATING A CLAIM DOES NOT ADMIT A TOKEN. No §6.5 row was added by
    PR #87, PR #88 or this change; the registry still holds EXACTLY SIX ROWS OVER
    FOUR TOKENS, and `plugins/evidence/models.py` is untouched by PR #87 at all.
    ADMITTING A TOKEN WOULD NOT HAVE SATISFIED CONDITION 11 EITHER, for the reason
    §15.3 records: a newly admitted row would accept a caller-supplied string for
    exactly the reason the existing rows do.

    AI-11 §21.1's OPEN-1 REMAINS OPEN. Row 1′ REMAINS UNSATISFIED. Closing
    AI15-OPEN-1 moved neither, and this amendment MUST NOT be cited as progress on
    either.
```

```text
§8.3 IS UNCHANGED, AND CONDITION 11 IS LEFT IN ITS ORIGINAL WORDS

    THE TWELVE CONDITIONS REMAIN THIS DOCUMENT'S FROZEN CONNECTED DEFINITION, and
    this amendment rewords none of them. Condition 11 states what it stated: the
    producer claim on the record must be authenticated to whatever standard AI-05
    defined, that standard must be implemented, and tests must show it holds.

    WHAT IS NOW TRUE, STATED WITH THE PRECISION THE CONDITION REQUIRES. The
    MECHANISM condition 11 names EXISTS: the standard is defined, implemented and
    shown by tests to hold. The CONDITION ITSELF is a condition ON A RECORD, and
    NO RECORD EXISTS — so it is UNVERIFIED rather than satisfied, and this document
    does not record it as satisfied.

    B5 IS STILL BLOCKED AND NOT CONNECTED. Twelve conditions include a real
    non-test call site, a named call site in AI-14 §5.1 and in §20, and a stored
    record in the staged tier (§8.3 conditions 1, 2, 3 and 9). NONE EXISTS. Nothing
    in this amendment may be read as moving the classification, and the sentence
    "all twelve hold" remains FALSE of this repository.
```

```text
SECURITY IMPACT

    NONE, AND THE POINT IS THAT THIS AMENDMENT ADDS NO CONTROL — IT RECORDS ONE
    THAT ALREADY MERGED.

    WHAT THIS AMENDMENT DOES
        it RECORDS that an owner closed AI15-OPEN-1, and names the upstream commit
          where that happened
        it syncs the status records that had gone stale: §9.2, §14.2, §15.2, §16.1,
          §16.2, §17.2b, §17.3, §19's preamble and `## Status`
        it keeps §15.2 STEP 0b's three parts APART — a MECHANISM that is DEFINED,
          a RUNTIME IMPLEMENTATION that is IMPLEMENTED, and ACCEPTANCE TESTS that
          are RUN — and records the case count rather than a run status
        it keeps §8.3's twelve conditions, and condition 11 in particular, exactly
          as frozen

    WHAT IT DOES NOT ADD
        no producer token, no §6.5 row, no registry change
        no call site, no writer, no seam, and no composition-side helper
        no permission, no capability, no authority-matrix row, no Guard result
        no change to any CONNECTED definition, and no new classification member
        no test, and no claim about a test this project did not run

    WHAT IT DOES NOT LIFT
        §17.2's block on importing `plugins.evidence` from composition/ until
        AI-14's STEP 1
        row 1′ — the §6.5 row and the own-contract clause for each phase whose
        facts would be admitted
        STEP 2's and STEP 3's preconditions, and the joint-delivery mechanism
        §13's authority rules, which are AI-14's and are untouched
```

```text
CONTRACT IMPACT

    ADDED        this amendment record
    AMENDED      §9.2 — AI15-OPEN-1's STATUS, its "what is missing now" block, and
                 the two closing paragraphs
                 §14.2 — AI-05's dependency record
                 §15.2 — STEP 0b's STATUS and GATES; STEP 2's and STEP 3's
                 PRECONDITION lines; the "if the order cannot be satisfied" table;
                 and a RECORDED note under the WRITE-gate clause
                 §15.3 — the AI-05 dependency paragraph and the eight-change list
                 §16.1 — AI15-OPEN-1's inventory row, and the FROZEN/RECORDED
                 clauses beneath the inventory
                 §16.2 — B5's blocker summary, row 0b, and three FROZEN clauses
                 §17.2b — the heading, and a RECORDED block stating exactly what
                 the gate's discharge does and does not do
                 §17.3 — the "STILL BLOCKED" clause and a RECORDED note
                 §19's preamble — the amendment count
                 `## Status`
    UNCHANGED    §8.3 — all twelve CONNECTED conditions, condition 11 included
                 §15.2's OWNER, PRECONDITION and OUTPUT for STEP 0b and for every
                 other step; the FROZEN clauses that fix the ORDER; §17.2; §17.2c;
                 §17.2d; §17.4; §17.5; §18; §20
    NO CHANGE TO the CONNECTED definition, the failure semantics, the workspace
                 rules, the authority restatements, the AI-15-B boundary, or the
                 class of any clause in this document
    NO CHANGE TO any other contract. AI-05, AI-11 and AI-14 are read-only here,
                 and AI-05 is the authority for the closure this amendment records.
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not close AI15-OPEN-1 — the OWNER did, in the owner's contract, and
      this amendment only records it
    it does not close AI-11 §21.1's OPEN-1, and it adds no §6.5 row
    it does not close AI15-OPEN-3 (AI-04) or AI15-OPEN-4 (AI-13 / AI-14)
    it does not satisfy row 1′, make AI-14's STEP 1, or pre-empt it
    it does not make STEP 2 or STEP 3, and it names no joint-delivery mechanism
    it does not mark B5 CONNECTED, or claim that all twelve §8.3 conditions hold
    it does not remove, weaken or reword condition 11, or any other condition
    it does not authorize a production Evidence writer to be created, merged or run
    it does not start AI-15-B, and it does not move AI-15-B out of NOT STARTED
    it does not claim AI-05 is complete: §35.1's deferrals are open and the
      registry is unchanged
    it does not turn any NOT_RUN, BLOCKED or UNKNOWN into PASS
    it does not run any test. The 46 cases it records were run by CI on PR #87's
      merged head; the runs reported here are cited to the runs that produced them
    it does not treat CI success on THIS documentation PR as evidence about
      producer authentication — it is evidence about documentation, and nothing else
    it does not alter any file outside this document, PROJECT_STATUS.md and
      MASTER_ROADMAP.md
```

---

#### Amendment 4 — an invalid AI-14 cross-contract reference is withdrawn from STEP 1
(2026-10-12)

```text
IN FORCE on the merge of the change that carries it. There is no awaiting-review
marker on this amendment: the merge IS the approval, and the text below is the
final text.
```

```text
WHAT WAS FOUND

    §15.2's STEP 1 listed, among the clauses that step changes, this one:

        "§13's `producer_token` identifier refusal, where it reaches the
         SUBMITTING caller rather than the composition"

    IT IS AN INVALID CROSS-CONTRACT REFERENCE. It names a rule in AI-14 §13 that
    AI-14 §13 DOES NOT CONTAIN, and it attributes to the existing `producer_token`
    restriction a SUBMITTING-CALLER behaviour that restriction DOES NOT HAVE.

    THE EVIDENCE, each item re-checkable:

        AI-14 §13 is "Human approval architecture". It contains NO producer-token
          rule of any kind. A case-folded search for "token" across §13 returns
          NOTHING, and "identifier" occurs in §13 nowhere either.
        `scripts/ci/layer0_policy.py`'s `AI14_FORBIDDEN_IDENTIFIERS` does contain
          `"producer_token"` — and it is a rule about `composition/*.py`, scoped to
          that directory. It has no caller-facing arm.
        `tests/composition/test_composition_boundaries.py`'s authority-vocabulary
          test scans the same directory for the same identifiers. Same scope.
        AI-14 §22.1 B5 carries its own, INDEPENDENT `NEVER` clause forbidding the
          composition to mint, select, borrow or alter a producer token or claim.
        AI-05 Amendment 4 chose READING A, which keeps producer and submitter
          APART. Authenticating a producer claim is not authenticating a submitter
          and is not an authorization.

    SO THERE IS NO REFUSAL "REACHING THE SUBMITTING CALLER" FOR STEP 1 TO NARROW.
```

```text
THE OWNER'S DECISION — OPTION A, AND IT IS MADE

    THE AI-15 OWNER HAS CHOSEN OPTION A: THE CLAUSE IS WITHDRAWN FROM STEP 1'S
    EFFECTIVE WORK LIST AND RECORDED AS A NO-OP.

    THIS IS A DECISION, NOT A NEW OPEN QUESTION. It is NOT recorded as an
    unresolved item, it is NOT reassigned, and it does NOT become a new blocker.
    §15.2's STEP 1 work list has been corrected in place, with the withdrawn clause
    shown as withdrawn rather than silently deleted.

    WHY IT IS A NO-OP RATHER THAN WORK:
        the item named a rule that does not exist, so there is nothing to change
        the rules that DO exist are scoped to `composition/` and were never in
          STEP 1's path
        NO RULE MODIFICATION IS REQUIRED, AND NONE IS MADE
        NO SUBMITTER-SIDE REFUSAL RULE IS ADDED, and none is proposed
```

```text
WHAT CONTINUES TO STAND, UNCHANGED

    `AI14_FORBIDDEN_IDENTIFIERS`' `producer_token` entry  UNCHANGED, still enforced
      over `composition/`
    the composition authority-vocabulary test              UNCHANGED, same scope
    AI-14 §22.1 B5's `NEVER` clause                        UNCHANGED — the
      composition still MUST NOT mint, select, choose, borrow or alter a producer
      token, a producer claim or a producer proof
    AI-05's READING A, and producer ≠ submitter            UNCHANGED
    §15.2 STEP 1's OTHER clauses and its enforcement list  UNCHANGED
    §16.1's other OPEN items, their owners and their status UNCHANGED

    NOTHING IN THIS AMENDMENT RELAXES A RULE. It removes a REQUIREMENT that named
    a rule which does not exist; it does not remove, weaken or reword any rule that
    does.
```

```text
TWO FACTS THAT MUST NOT BE MERGED, AND THEY ARE STATED SEPARATELY

    1  AI-15'S DECISION HAS BEEN MADE. The clause is withdrawn as a valid STEP 1
       delivery requirement. That is recorded HERE, in AI-15's own contract, by
       AI-15's owner, under AI-15's amendment rule (§19).

    2  AI-14'S OWN CONTRACT HAS NOT BEEN UPDATED BY AI-14. AI-14's document still
       carries its older OPEN / UNDECIDED status record for this reference, because
       correcting it is AI-14'S ACT, on AI-14's contract, under AI-14 §24.
       AI-15 DOES NOT MODIFY IT, DOES NOT SPEAK FOR AI-14, AND DOES NOT DECLARE
       AI-14 STEP 1 COMPLETE ON AI-14'S BEHALF.
       UNTIL AI-14'S OWNER ACTS, THE AUTHORITATIVE CONTRACT STATUS REMAINS
       CONSERVATIVE: **AI-14 STEP 1 = NOT FULLY DISCHARGED.**
       ^ RECORDED (§19 AMENDMENT 6): THE OWNER HAS NOW ACTED. AI-14 Amendment 4
       (PR #96, merge 36d6ea92a8872dd9167412d8e39de063854b345d, 2026-10-12)
       corrected the stale record this paragraph named and records STEP 1's
       enumerated list as DISCHARGED ON AI-14'S SIDE. THE TWO SENTENCES ABOVE ARE
       KEPT AS WHAT THEY WERE — they state the position on 2026-10-12 BEFORE that
       merge, and they were true of it. The record to read now is §19 Amendment 6.

    THE TWO ARE NOT THE SAME STATEMENT, AND A READER MUST NOT TAKE THE FIRST FOR
    THE SECOND. AI-15 has disposed of the item IT raised; whether that disposes of
    AI-14's status record is AI-14's to say.
```

```text
SECURITY IMPACT

    NONE. This amendment changes no runtime code, no runtime behaviour, no control
    and no check. It adds no attack surface, introduces no trust root, and alters
    no trust boundary. It REMOVES A REQUIREMENT — and the requirement it removes is
    one that named a rule which does not exist, so nothing that was enforced stops
    being enforced.
    NO NEW SUBMITTER-SIDE REFUSAL RULE IS ADDED. NO PRODUCER TOKEN IS ADDED. NO
    §6.5 REGISTRY ROW IS ADDED. NO PRODUCTION EVIDENCE CALL SITE IS CREATED.
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, moves a responsibility, introduces an
    authorizing subject, or changes AI-14 §4.1's authority matrix. Guard remains
    the only component with an AUTHORIZES entry. An authenticated producer claim is
    still not an approval, not a permission, not a capability and not a Guard
    result. Producer authentication is still not submitter identity.
```

```text
CONTRACT IMPACT

    ADDED        this amendment record
    AMENDED      §15.2 STEP 1's work list — the invalid clause is withdrawn and
                 shown as withdrawn
                 §19's preamble — the amendment count
                 `## Status` — the amendment count and the Amendment 4 line
    UNCHANGED    §8.3's twelve CONNECTED conditions, condition 11 included
                 §16.1's OPEN items, §16.2's BLOCKED rows, §17.1-§17.5, §18, §20,
                 and every other clause of §0-§20
                 the class of every clause in this document
    NO CHANGE TO any other contract. AI-14, AI-05 and AI-11 are READ-ONLY here.
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not mark AI-14 STEP 1 complete, and it does not discharge it
    it does not update AI-14's contract, which is AI-14's to update
    it does not mark B5 CONNECTED, or claim that all twelve §8.3 conditions hold
    it does not start AI-15-B, STEP 2 or STEP 3, or unblock any of them
    it does not close AI-11 §21.1's OPEN-1, row 1′, AI15-OPEN-3 or AI15-OPEN-4
    it does not resolve the joint-delivery mechanism
    it does not add, remove or weaken a producer token, a §6.5 row, a rule or a
      check, and it does not create a production Evidence writer
    it does not turn any NOT_RUN, BLOCKED or UNKNOWN into PASS
    it does not run any test. This is a documentation change, and it claims no test
      result of its own
    it does not alter any file outside this document, PROJECT_STATUS.md and
      MASTER_ROADMAP.md
```

---

#### Amendment 5 — the producer-authentication semantics AI-15-B freezes are synchronized with the implemented mechanism
(2026-10-12)

```text
IN FORCE on the merge of the change that carries it. There is no awaiting-review
marker on this amendment: the merge IS the approval, and the text below is the
final text.
```

```text
WHAT WAS FOUND

    FIVE THINGS, AND NONE OF THEM WAS A CONTRACT DISPUTE. Four were this document
    describing the boundary as it was BEFORE PR #87 merged; the fifth was a model of
    the pipeline that never matched it.

        §4.2 read "TODAY'S PIPELINE ACCEPTS THE CLAIM ON EXACTLY THE FIRST OF THOSE
        BASES. A caller-supplied string is the sole basis of `provenance.producer`".
        TRUE WHEN WRITTEN; NO LONGER TRUE. The caller-supplied string is still what
        the field carries, and it is no longer the SOLE basis: §30 step 7b now
        requires a proof that verifies.

        §4.4 read "Any module that can import `plugins.evidence` can today submit
        [...] and — if every field is otherwise well formed and the workspace agrees
        — receive `ACCEPTED`". SAME: true when written, and a submission with no
        proof is REJECTED today.

        §10.1 recorded the two entry points and the pipeline "as they are". IT
        RECORDED THEM AS THEY WERE BEFORE PR #87: neither signature carried
        `producer_proof`, no step 7b appeared in the pipeline, and the store's line
        numbers were the pre-merge ones. A reader implementing AI-15-B from §10
        would have written a caller that cannot admit anything.

        §4.3 recorded the same two signatures, and placed the registry check inside
        "`admit()`'s second step". IT IS NOW THE THIRD: step 7's rule set, then step
        7b, then construction (admission.py:218). The clause's FINDING is unchanged —
        nothing in the API establishes who submits — and the position of the check it
        describes had moved.

        THE PIPELINE ITSELF was described, outside this document, with an
        "authorize evidence production" stage between authentication and
        construction. NO SUCH STAGE EXISTS IN EVIDENCE'S PATH, and none may be
        added (§13).
```

```text
WHAT THIS AMENDMENT CHANGES, AND WHERE

    §4.2   a RECORDED correction of the withdrawn sentence, and the SEMANTICS stated
           as FROZEN clauses: the producer field is a DECLARATION and not an
           authentication source; a valid producer proof verification is the
           ADMISSIBILITY BASIS for the producer claim; and NO RUNTIME IDENTITY
           OBJECT is introduced, by this document or by any phase implementing the
           boundary.
    §4.4   a RECORDED correction of the withdrawn sentence. Its POINT is kept and
           sharpened: the API still takes no submitter identity, and an admitted
           record still establishes a KEY HOLDER that signed the claim — not a code
           component, and not the submitter.
    §4.3   two stale records corrected: the registry check's position in the pipeline
           (INSIDE construction, admission.py:218 — not "`admit()`'s second step"),
           and the two entry-point signatures, with a note that the added
           `producer_proof` argument does not change the clause's finding.
    §9.4   the PROOF PROPAGATION INVARIANT, as FROZEN clauses: the bytes are
           preserved; dropping is AUTHENTICATION_PROOF_MISSING; modification is a
           verification failure named by the step that catches it; substitution
           cannot be made to verify; there is no silent acceptance on any path; a
           forwarder may not mint, re-mint or repair a proof; and the composition's
           own conduct is left to AI-05 §7.3.12 and AI-14 §22.1 B5.
    §10.1  the entry points RESTATED at the merged head: step 7b in the pipeline,
           `producer_proof` in both signatures, the proof's through-pass to `admit()`,
           and the store's current line numbers.
    §10.2  two caller obligations added: PRESENT the proof, and do not fabricate,
           substitute, repair or hold signing material for one.
    §10.4  NEW. The AI-15-B freeze matrix — the write pipeline — with the authorize
           stage WITHDRAWN BY NAME, the ordering frozen, and the two places the
           admissibility checks actually run stated beside the drawing so it is not
           mistaken for a reordering of §30.
    §19    this record, and the amendment count.
    `## Status`  the amendment count and the Amendment 5 line.
```

```text
WHO DECIDED WHAT — THE OWNERSHIP IS THE POINT, AND IT IS STATED FIRST

    AI-15'S PART IS THIS DOCUMENT'S OWN SEMANTICS. §4.2, §4.4, §9.4, §10.1, §10.2
    and §10.4 are AI-15's clauses, and the corrections above are AI-15's act, in
    AI-15's contract, under §19. NO OTHER PHASE'S CLAUSE IS EDITED BY THIS
    AMENDMENT.

    THE CROSS-CONTRACT HALF IS AI-05'S. §9.4 and §10.2 state what a FORWARDER must
    do with a proof. What a forwarder MAY do with one is the producing contract's
    question, because it turns on the meaning of §7.3.10's word "hold". AI-05
    answered it in AI-05 §7.3.12 — AI-05 AMENDMENT 8, made by AI-05's owner in
    AI-05's contract under AI-05's amendment rule. AI-15 RECORDS it and produced
    none of it, exactly as Amendments 1, 2 and 3 recorded AI-05's acts and produced
    none of those.

    §19's ORDERING RULE IS SATISFIED. THIS ORDERING IS A CONTRACT DEPENDENCY
    REQUIREMENT, NOT A FORMALITY.

    §19 requires an amendment to AI-00 .. AI-14 to be made BEFORE AI-15 depends
    on it.

    The two parts were delivered separately and in dependency order: AI-05
    §7.3.12 merged first, as AI-05 Amendment 8, PR #94, merge commit
    6a3d6cb0abec9d776678c1b462923120db93b21d (2026-10-12).

    AI-15 Amendment 5 is authored on top of the merged AI-05 Amendment 8 state.
    Therefore this amendment does not depend on an unmerged clause. The
    referenced AI-05 ownership semantics were already present on `main` before
    this amendment was prepared.
```

```text
SECURITY IMPACT

    NONE, AND THE POINT IS THAT THIS AMENDMENT ADDS NO CONTROL. It records the shape
    of a mechanism that already merged (PR #87), and it makes three claims a reader
    can check against the code rather than against prose:

        authentication runs BEFORE construction        admission.py:217-218
        a missing proof is a REJECTED RESULT and not
          a TypeError                                  admission.py:197-201
        no production caller exists                    §3.1-§3.3, §20.1

    WHAT IS GENUINELY NEW IS ONE PROHIBITION AND ONE INVARIANT, AND BOTH ARE
    BOUNDARIES RATHER THAN CONTROLS:
        no runtime identity object may be introduced (§4.2) — a rule about a design
          this document refuses, not a runtime barrier
        a forwarder may not drop, modify, substitute or mint a proof (§9.4) — and
          this one is not merely a rule, because the verification steps that already
          exist refuse each case: PROOF_MISSING, SIGNATURE_INVALID, INPUT_MISMATCH
          or PROOF_MALFORMED (AI-05 §7.3.5, §7.3.8)

    WHAT IT DOES NOT CLAIM. It does not claim a proof makes a claim TRUE (§4.2,
    §9.2), that authentication identifies the SUBMITTER (§9.2), that an ACCEPTED is
    an authorization (§13.2), or that any part of the mechanism is new. It runs no
    test and cites no run of its own. §10.4's withdrawal of the authorize stage
    removes a CLAIM; no rule existed for it to remove.
```

```text
AUTHORITY IMPACT

    None. Nothing here grants a permission, changes AI-14 §4.1's authority matrix,
    introduces an authorizing subject, or moves a responsibility between phases.
    Guard remains the only component with an AUTHORIZES entry. An authenticated
    producer claim is still not an approval, a permission, a capability or a Guard
    result (§9.5, §13.2).
```

```text
WHAT THIS AMENDMENT DOES NOT DO

    it does not start AI-15-B, or move it out of NOT STARTED
    it does not make AI-14's STEP 1, satisfy row 1′, create a call site or a writer
    it does not mark B5 CONNECTED, or claim that any §8.3 condition now holds
    it does not add, remove or change a producer token, a §6.5 row, a reason code, an
      admission outcome or a digest input
    it does not change the failure semantics (§11), the workspace rules (§12) or the
      authority rules (§13)
    it does not authorize AI-15 to add a producer check, a provenance-verification
      seam or a trust root (§17.4, unchanged)
    it does not edit any other contract. AI-05 §7.3.12 is AI-05's own amendment,
      recorded here and produced by AI-15 in no part
    it does not turn any NOT_RUN, BLOCKED or UNKNOWN into PASS
    it does not alter any file outside this document
    it does not run any test, and it claims no test result of its own
```

---

#### Amendment 6 — AI-14 STEP 1's discharge is recorded, and this document's STEP 1 status is synced to it
(2026-10-12)

```text
IN FORCE on the merge of the change that carries it. There is no awaiting-review
marker on this amendment: the merge IS the approval, and the text below is the final
text.

AMENDMENT NUMBER  6
DATE              2026-10-12
```

```text
WHAT WAS FOUND

    THIS DOCUMENT STILL DESCRIBED AI-14'S STEP 1 AS NOT MADE, AND THAT STOPPED BEING
    TRUE ON 2026-10-11. §15.2's STEP 1 PRECONDITION read "No AI-14 amendment has
    been made"; §4.4, §7.2, §7.3, §7.4, §8.4 and §9.2, §15.2's STEP 0a and STEP 0b
    GATES and its STEP 2 and STEP 3 PRECONDITIONS, §16.1, §16.2's row 1 and its
    FROZEN notes, §17.2, §17.2b, §17.3 and `## Status` all rested on the same
    premise — that §17.2 refused the composition's import and call "until AI-14's
    STEP 1"; §14.1's summary-table row and §14.8's dependency block stated the same
    thing from the dependency side.

    AI-14'S OWN CONTRACT SETTLES WHAT HAPPENED. Its §25 Amendment 2 says, in its own
    words: "This is STEP 1 of the order AI-15 §15.2 fixes for this edge." That
    amendment MERGED — AI-14 Amendment 2, PR #90, merge
    a98e389b91ee10858abc67e7c66509cd12fae9dc (2026-10-11). AI-14's §25 Amendment 4
    (PR #96, merge 36d6ea92a8872dd9167412d8e39de063854b345d, 2026-10-12) then
    corrected its own stale row and records STEP 1's enumerated list as DISCHARGED ON
    AI-14'S SIDE.
```

```text
WHO ACTED, AND WHAT AI-15 DID NOT DO

    AI-14'S OWNER MADE STEP 1, in AI-14's contract, under AI-14's amendment rule —
    AI-14 §25 Amendments 2 and 4. AI-15 PRODUCED NO PART OF IT, DID NOT APPROVE IT,
    AND DOES NOT DECLARE IT ON AI-14'S BEHALF. This amendment RECORDS it and syncs
    this document's status to it, in the same shape as Amendments 1, 2 and 3, which
    recorded AI-05's acts and produced none of those.
    §19's ORDERING RULE IS SATISFIED: the earlier contract's amendment was made
    BEFORE AI-15 depended on it, and it landed first.
```

```text
WHAT THIS AMENDMENT CHANGES

    §15.2 STEP 1     a RECORDED note: the step has been made, by its OWNER
    §15.2 STEP 2     the PRECONDITION: all three of STEP 0a, STEP 0b and STEP 1 are
      AND STEP 3     satisfied; STEP 2 is still not made, and STEP 3 cannot run
                     before it
    §15.2 STEP 0a    RECORDED notes: the authorization has been made by AI-14, and
      AND STEP 0b    STEP 1 is satisfied with it
    §16.2            the header's count (THREE of the seven blockers satisfied),
                     row 1 marked SATISFIED with its evidence, and the two FROZEN
                     notes beneath it
    §16.1            the AI15-OPEN-1 GATES line
    §17.2            a RECORDED block — THIS SECTION'S TEXT IS UNCHANGED
    §17.2b, §17.3    RECORDED notes
    §4.4, §6.1,      RECORDED notes: §17.2 no longer refuses the import or the call
      §7.3, §7.4,
      §8.4, §9.2
    §14.1, §14.8     the AI-14 row and the dependency block, including the note that
                     a connecting change no longer fails Layer 0's import rule
    §19              this record, and the preamble's amendment count
    `## Status`      the BLOCKED block, the amendment count and the Amendment 6 line
```

```text
WHAT IT DOES NOT DO — AND THIS IS THE WHOLE OF THE LIMIT

    NO CLASSIFICATION CHANGE. B5 remains BLOCKED. §5.1's row, §22.1 B5's item status,
    Appendix A's classification and the twelve §8.3 conditions are UNTOUCHED. ROW 1′
    REMAINS UNSATISFIED for any event but AI-06's, and this amendment does not
    satisfy it.
    NO AUTHORITY CHANGE. §13's rules and AI-14 §4.1's authority matrix are unchanged;
    Guard remains the only component with an AUTHORIZES entry.
    NO CONNECTED CLAIM. No seam is connected, no edge is reported as one, and this
    amendment introduces no intermediate classification for one. §8.3 condition 11
    remains a condition ON A RECORD, and no record exists.
    AI-15-B IS STILL NOT STARTED, AND THIS AMENDMENT DOES NOT START IT. STEP 2 has
    not been delivered and STEP 3 has not begun. The joint-delivery mechanism is
    still unnamed, and §17.2d's rule that STEP 2 and STEP 3 merge as ONE change is
    unchanged.
    IT DOES NOT LIFT THE PROHIBITION ON A PRODUCTION CALL SITE. What refuses one now
    is §17.2d's joint-delivery requirement, row 1′ for any event but AI-06's, and the
    absent call site itself — not §17.2, whose premise is satisfied.
    IT TOUCHES NO OTHER FILE. AI-14's, AI-05's and AI-11's contracts, every status
    document, every runtime module and every test are UNCHANGED by it.
```

```text
ONE STRUCTURAL FIX, DISCLOSED RATHER THAN FOLDED IN

    §17.2'S CODE BLOCK HAD NO CLOSING FENCE, so the `### 17.2b` heading and its
    first block rendered INSIDE §17.2's block. This amendment closes it, because the
    RECORDED block it appends cannot be placed correctly otherwise. THAT IS A
    RESTORATION OF A FENCE AND NOT A CHANGE TO §17.2's TEXT, which is unchanged word
    for word.
    THE SAME DEFECT EXISTS AT THREE OTHER SITES AND IS NOT FIXED HERE, because
    fixing them is outside what this amendment was scoped to do. THEY ARE NAMED SO
    THEY ARE NOT DISCOVERED LATER, at `main` @ 36d6ea92: the block at §11.4's heading
    (which swallows the `### 11.4` heading), the block at §17.3's heading (which
    swallows the `### 17.3` heading), and one block in §2/§3 that swallows a fence
    opener. All three PREDATE this amendment and are present on `main`; none of them
    changes what any clause MEANS.
```

```text
SECURITY IMPACT
    NONE. No runtime code, no control, no check, no key and no trust boundary
    changes. No producer token, registry row, reason code or admission outcome is
    added, removed or changed.
AUTHORITY IMPACT
    None. Nothing here grants a permission, changes AI-14 §4.1's matrix, introduces
    an authorizing subject, or moves a responsibility between phases.
```

```text
WHAT THIS AMENDMENT DOES NOT CLAIM
    it does not claim AI-15 made, approved or may declare STEP 1
    it does not claim B5 moved, or that any seam is connected
    it does not claim STEP 1's satisfaction changes the API: the API still takes no
      submitter identity, and an authenticated producer claim is still not a
      permission
    it does not run any test, and it claims no test result of its own
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
         every blocker with its owner and the §15.2 step it gates. THREE ARE NOW
         SATISFIED — STEP 0a, answered as READING A by AI-05 Amendment 4; STEP 0b,
         answered, implemented and tested by AI-05 and closed in AI-05's contract by
         AI-05 Amendment 7 (§19 Amendment 3); and STEP 1, DELIVERED BY AI-14'S OWNER
         — AI-14 Amendment 2 (PR #90, merge
         a98e389b91ee10858abc67e7c66509cd12fae9dc), recorded as discharged by AI-14
         Amendment 4 (PR #96, merge
         36d6ea92a8872dd9167412d8e39de063854b345d) (§19 Amendment 6). THE REST
         STAND: row 1′ is unsatisfied for any event but AI-06's, there is no call
         site, the joint-delivery mechanism is unnamed, and STEP 3 cannot be
         recorded. SATISFYING A BLOCKER IS NOT SATISFYING THE ITEM, AND DEFINING A
         MECHANISM IS NOT IMPLEMENTING ONE EITHER — nor is implementing one
         connecting a seam.
         NO PRODUCTION WRITER EXISTS, and none is authorized. §15.2 STEP 0b no
         longer gates the WRITE, because it is SATISFIED, AND NEITHER DOES §17.2,
         whose STEP 1 premise is satisfied with it. What refuses the write now is
         the JOINT-DELIVERY requirement (§17.2d — STEP 2 and STEP 3 merge as ONE
         change, and no owner-approved mechanism is named), ROW 1′ for any event but
         AI-06's, and STEP 2's own precondition — which now requires a call site
         that does not exist (§17.2b, §16.2).

AMENDED: this document has been amended SIX TIMES since it was frozen.
         §19 Amendment 1 records AI-05's answer to AI15-OPEN-2.
         §19 Amendment 2 records AI-05 Amendments 5 and 6 — the producer
         authentication standard DEFINED and its trust configuration FROZEN — and
         corrected the reason AI15-OPEN-1 was THEN still OPEN.
         §19 Amendment 3 records AI-05 Amendment 7 — the standard IMPLEMENTED and
         TESTED, and AI15-OPEN-1 CLOSED BY ITS OWNER — and syncs this document's
         status records to it. THE OWNER MADE THE DECISION; AI-15 RECORDED IT.
         §19 Amendment 4 WITHDRAWS an invalid cross-contract reference from §15.2
         STEP 1's work list and records it as a NO-OP. AI-15's OWNER MADE THAT
         DECISION, in AI-15's own contract; NO RULE CHANGED and no item moved.
         §19 Amendment 5 SYNCS this document's producer-authentication semantics to
         the mechanism PR #87 implemented: §4.2, §4.3 and §4.4 corrected, §9.4's
         proof propagation invariant frozen, §10.1 restated at the merged head, §10.2's
         caller obligations extended, and §10.4 added — the AI-15-B freeze matrix,
         with the "authorize evidence production" stage WITHDRAWN BY NAME. It
         RECORDS AI-05 Amendment 8 (§7.3.12, the forwarder's transport permission)
         and produced none of it. NO STATUS ITEM MOVED: B5 stays BLOCKED, AI-15-B
         stays NOT STARTED, and no seam is CONNECTED.
         §19 Amendment 6 RECORDS AI-14 STEP 1'S DISCHARGE — delivered by AI-14's
         owner (AI-14 Amendment 2, PR #90, merge a98e389b…) and recorded as
         discharged by AI-14 Amendment 4 (PR #96, merge 36d6ea92…) — and syncs this
         document's status records to it. AI-15 PRODUCED NO PART OF IT. NO
         CLASSIFICATION MOVED: B5 stays BLOCKED, row 1′ stays unsatisfied, AI-15-B
         stays NOT STARTED, STEP 2 and STEP 3 have not begun, and no seam is
         CONNECTED.

OPEN:    AI15-OPEN-3 (AI-04) · AI15-OPEN-4 (AI-13/AI-14)
         — local ids, prefixed so they cannot be confused with AI-11 §21.1's
         OPEN-1, which is a different item (§9.2)
CLOSED:  AI15-OPEN-2 = CLOSED / ANSWERED BY AI-05 AMENDMENT 4 — READING A
         (§5.3, §16.1, §19 Amendment 1). AI-05 answered it; AI-15 recorded it.
         AI15-OPEN-1 = CLOSED BY AI-05 AMENDMENT 7 (§9.2, §16.1, §19 Amendment 3)
         — answered, implemented and tested: mechanism DEFINED, PR #87 merged as
         d09ce69ec1c0975c6d638d7861df2f11c44ec1d1, CI run #301 with 46
         process-isolated cases RAN and 0 skipped. AI-05 closed it, in AI-05's
         contract, under AI-05's amendment rule; AI-15 recorded it and did not
         make it.
         AI-11 §21.1's OPEN-1 is NOT closed by either of them, REMAINS OPEN, and
         is a DIFFERENT item: WHICH PRODUCERS EXIST. No §6.5 row was added by any
         of this.

UNCHANGED BY THIS DOCUMENT: AI-05 · AI-06 · AI-08 · AI-10 · AI-11 · AI-13 · AI-14
         contracts, implementations and boundaries — every one byte-identical.

NOT CLAIMED: that Evidence is connected. It is not. §3 records what is, and §20
         records it at file:line. Freezing this contract changed none of that:
         at the merge, and after it, `plugins.evidence` still has no production
         caller and no production writer (§3.1-§3.3).

NOT CLAIMED: that a producer claim is trustworthy once a token is registered.
         It is not. REGISTRATION IS STILL NOT AUTHENTICATION — `g_registered`
         compares a string to the registry and compares nothing else — and §8.3
         condition 11 still requires the mechanism §19 Amendment 3 records. WHAT
         HAS CHANGED IS THAT THE MECHANISM NOW EXISTS: "until AI-05 says otherwise
         and shows it" HAS HAPPENED, and §15.2 STEP 0b is satisfied. THE CONNECTED
         CLAIM AND THE WRITE ARE STILL KEPT OUT — by the ABSENCE of a call site and
         of a record, and by §17.2, rather than by this clause (§9.2).

NOT CLAIMED: that Layer 0 stops Evidence from being imported at runtime. It does
         not. It refuses a REPOSITORY CHANGE, and the absence of a caller at this
         baseline is a fact about the tree, not a runtime barrier (§3.4).

NOT CLAIMED: that Evidence admission failure must be swallowed, or that a caller
         may not treat it as the failure of its own operation. §11.4 keeps both
         claims out: the outcome stays observable, is never disguised as success
         and is never an authorization — and the caller's control flow is the
         caller's, under the caller's own contract.
```
