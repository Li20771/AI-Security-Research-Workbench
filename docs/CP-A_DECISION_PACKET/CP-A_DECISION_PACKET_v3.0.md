# CP-A_DECISION_PACKET_v3.0

> **STATUS: DRAFT — NOT APPROVED.**
> This file is a **decision request**, not a decision. Nothing in it has been
> approved, adopted, merged or agreed by any owner. It is **not a contract**, it
> has **no normative force**, and it creates **no obligation** on any phase.
> It may not be cited as authority for any change, and it must not be quoted as
> though an owner had already decided.
>
> It lives **outside** every phase's contract. No clause of AI-05, AI-06, AI-08,
> AI-14 or AI-15 is amended, restated, weakened or superseded by it.
>
> **Baseline:** `origin/main` = `34a685b5ae5885fb2a496f88af0ff422af2f5894`,
> verified by `git fetch origin --prune` on 2026-10-13; PR #99 is the last merge;
> no later commit exists.
>
> **Supersedes:** the unpublished v2.x drafts in this directory —
> `PROJECT_OWNER_DECISION.md`, `AI14_OWNER_DECISION.md`, `AI05_OWNER_DECISION.md`
> and `CP-A_STATUS.md` — which were prepared against a stale baseline and whose
> seven settled items are recorded in §2 as CLOSED HISTORY. This file does not
> re-open them.

---

## 0. What this packet is and is not

```text
DRAFT — NOT APPROVED. This is a DECISION REQUEST, not a decision.

it is        a register of the questions that remain open at the baseline named
             above, each with the facts verified against that baseline, the scope
             of what a decision must determine, and an unsigned signature box
it is not    a decision, an approval, a contract, an amendment, or authorisation
             for any code, call site, producer token, registry row, test or
             workflow change
it does not  amend any contract; every amendment recorded in §2 was made by the
             owner of the contract it amends, in that owner's contract, under
             that owner's amendment rule
it does not  edit docs/PROJECT_STATUS.md or docs/MASTER_ROADMAP.md; §3 D7
             records their conflicts and asks who may correct them
it has       no normative force, and no status in it is an owner's approval of
             any option
```

**The register is the authority for who decides what.** Where this packet's prose
and the register disagree about an owner, the register governs. No item in this
packet is the project owner's to decide unless the register says so, and no item
is any other owner's to decide because this packet documents it here.

No file in this packet exempts any gate, and nothing in it authorises an
implementation to begin.

---

## 1. Operational Freeze State (verified at 34a685b5)

```text
OPERATIONAL FREEZE STATE — verified status at the baseline named at the top of
this file, not a decision. It creates no decision, approves no option, and is
not a substitute for any contract. It grants no exemption from any gate.

CP-A                                      NOT SATISFIED
B5 (composition -> Evidence)              BLOCKED (rows 1', 2, 3, joint)
AI-15-B                                   NOT STARTED / BLOCKED
STEP 2                                    BLOCKED / NOT MADE
STEP 3                                    CANNOT RUN (no call site to name)
production call site                      NONE AUTHORISED
   (APPROVED_CALL_SITES is EMPTY at
    tests/evidence/test_producer_authentication.py:1243; the 18a exact-set
    assertion passes on the empty set)
CONNECTED claim about this edge           FORBIDDEN
AI-05 acceptance matrix                   NOT RUN (this round)
Layer 0 "PASS (24 checks)"                NOT VERIFIED (this round)
§7.3.13 two-tree connection gate          EXISTS AND IN CI (layer1) — NEW
                                          SINCE v2.x (PRs #98/#99)
AI-06 §15.8 signing boundary              FROZEN AND LIVE (PR #98) — the
                                          eight negative tests are owed by
                                          the joint change and have not run

"NOT RUN" describes a TEST OR CI RUN that was not performed this round; it is
NEVER a description of STEP 3. "CANNOT RUN" describes an ARCHITECTURAL GATE: STEP
3 cannot start because no call site exists for it to name, so there is nothing for
it to run in the first place. The two are not interchangeable.

Historical CI run #301 is a RECORD in AI-05's contract. It is NOT an execution
result of this round and MUST NOT be presented as one.
No file in this packet exempts any gate, and no status above is an owner's
approval of any option in this packet.
```

**Evidence for each state, verified line by line at the baseline.**

| State | Verified at |
|---|---|
| B5 BLOCKED on rows 1', 2, 3 and joint | `docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md:1511-1556`; `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:3043-3103` |
| AI-15-B NOT STARTED / BLOCKED | `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:4999`; `:3043` |
| production call site NONE — the scanner's exception is intra-package | `tests/evidence/callsite_identity.py:58-68`; the only executable call is `plugins/evidence/admission.py:288` |
| STEP 3 CANNOT RUN | `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:2756-2759` |
| no CONNECTED claim | `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:2760-2763`; `:3543-3545` |
| approved set EMPTY, 18a passes on it | `tests/evidence/test_producer_authentication.py:1243`, `:1278-1292` |
| §7.3.13 two-tree gate exists and runs in CI | `tests/evidence/connection_change_verification.py:1-30`, `:60-69`; `tests/evidence/test_connection_change_verification.py:29`; `.github/workflows/preflight.yml:75` |
| AI-06 §15.8 FROZEN and live; tests not written, not run | `docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1109`, `:1228-1229`; `ProducerSigner` occurs in no code module (contract text only, `:1126`, `:1553`) |
| `AI14_FORBIDDEN_IMPORTS` is empty | `scripts/ci/layer0_policy.py:3583` |

**The historical record, kept as what it was.** AI-05 Amendment 7 (d), §35.3 and
`## Status` record "46 RAN / 0 skipped" as the result of CI run #301, together
with `Layer 0 = PASS (24 checks)`
(`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:7577-7578`, `:6941`, `:6953`, `:6994`).
That is a **historical record of an execution** recorded in AI-05's contract. It
is not an execution result of this round, and this packet neither re-ran it nor
re-verified its numbers. Historical results MUST NOT be presented as current
execution.

**The AI-05 acceptance matrix is NOT RUN this round and Layer 0 is NOT VERIFIED
this round.** The packet executed no test and no CI run. Nothing in it may be
read as an execution result.

---

## 2. CLOSED HISTORY — CLOSED_BY_PHASE_AMENDMENT

Seven items carried by the unpublished v2.x drafts were settled by phase
amendments merged after those drafts were prepared. Each is recorded here once,
with the amendment that closed it, and is not a register item. The amendments
were made by the owners of the contracts they amend; this packet produced no part
of any of them.

Five phase amendments landed after the v2.x drafts were prepared, all merged by
**PR #98** (merge commit `285d5c9e836d3f5f79903d59fc29070707705d6a`, head
`a731c501ff8ae8d4a992d9191dea950385eba847`, branch
`feature/ai15-pr1-contract-acceptance`, merged 2026-10-12), except where a later
merge is named. Three of them closed the seven items below — AI-14 Amendment 5,
AI-15 Amendment 7 and AI-05 Amendment 9; AI-06 Amendment 2 and AI-08 Amendment 5
are part of the same change's contract work and are recorded here for the
evidence base:

```text
AI-05   Amendment 9   §7.3.13 exact approved call-site set            FROZEN
AI-06   Amendment 2   §15.8 production-side signing boundary          FROZEN
AI-08   Amendment 5   a submission envelope may pass through
AI-14   Amendment 5   the B5 rules the joint change needs
AI-15   Amendment 7   the superseded B5 quotation is corrected, and
                      the joint change is recorded as three-party
```

### D1 — joint-delivery mechanism

```text
ORIGINAL ITEM (v2.x)   How is a joint change delivered when neither AI-14 §22.1
                       B5 nor AI-15 §17.2d named a mechanism, and B5 still read
                       "two authors"?
SUPERSEDING AMENDMENT  AI-14 Amendment 5(c), 2026-10-12 — §22.1 B5's
                       `blocked by (iii)` now names THREE parts and THREE
                       authors, ONE change, ONE review, ONE merge, not a commit
                       count; a separately merged AI-14 part or AI-05 part does
                       not satisfy the row; the CONNECTED classification remains
                       AI-14's and moves only in the same change as the call
                       site.
CLAUSE MAPPING         docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md
                       :1521-1556 (in tree); the amendment's own record at
                       :2305-2311
EVIDENCE               PR #98, merge 285d5c9e…; the amendment is logged in AI-14
                       §25 at :2274
CORROBORATION          AI-15 Amendment 7 added the third (AI-05) row to
                       §17.2d — docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md
                       :3412-3418, with the note at :3420-3426
NO REOPENING           The mechanism is named in AI-14's contract. Its delivery
                       shape is not a question in this packet.
```

### C1 — `persist an Evidence record` vs calling `admit_to_store`

```text
ORIGINAL ITEM (v2.x)   Does AI-14 §22.1's preamble prohibition on the glue
                       "persist[ing] an Evidence record" forbid calling
                       `admit_to_store`, which §22.1 B5 requires?
SUPERSEDING AMENDMENT  AI-14 Amendment 5(a), 2026-10-12 — the §22.1 preamble
                       gains a limiting sentence: the prohibition means a
                       composition module WRITING TO A STORE ITSELF, and does NOT
                       extend to calling AI-05's admission entry point. "THIS IS
                       A READING, NOT A RELAXATION."
CLAUSE MAPPING         docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md
                       :1314-1330 (in tree); the amendment's own record at
                       :2289-2296
EVIDENCE               PR #98, merge 285d5c9e…
NO REOPENING           The reading is recorded in AI-14's contract. N1's own
                       question is a different one (see §3).
```

### C2 — §22.1 ORDER scope

```text
ORIGINAL ITEM (v2.x)   Does §22.1 ORDER's registry precondition ("B5 MUST NOT
                       START until AI-05 has amended its producer registry")
                       apply to the AI-06 path?
SUPERSEDING AMENDMENT  AI-14 Amendment 5(b), 2026-10-12 — a scope note records
                       that the sentence states the gate for a phase whose facts
                       have NO §6.5 row, and does NOT apply to the AI-06 path,
                       whose two rows already exist and whose §15.1 already names
                       a submitter. It moves nothing on AI-11 §21.1's OPEN-1 and
                       authorises no path for any phase without a §6.5 row.
CLAUSE MAPPING         docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md
                       :1355-1363 (in tree, under ORDER at :1348-1353); the
                       amendment's own record at :2298-2303
EVIDENCE               PR #98, merge 285d5c9e…
NO REOPENING           The scope note is in AI-14's contract. AI-11 §21.1's
                       OPEN-1 remains OPEN and is a different item.
```

### C3a — third-party (AI-05) row in B5

```text
ORIGINAL ITEM (v2.x)   How is AI-05, whose acceptance obligation observes the
                       connecting change, recorded in AI-14's contract?
SUPERSEDING AMENDMENT  AI-14 Amendment 5(c), 2026-10-12 — B5's `blocked by (iii)`
                       names "the AI-05 part — AI-05'S OWNER — the acceptance
                       obligations its contract imposes on the change, and the
                       CI matrix node list that runs them", with the
                       what-is-not-transferred block.
CLAUSE MAPPING         docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md
                       :1531-1534 and :1551-1556 (in tree)
EVIDENCE               PR #98, merge 285d5c9e…
NO REOPENING           NAMING THE PART TRANSFERS NOTHING: AI-05 does not classify
                       this edge and does not author or approve AI-14's clauses.
```

### C3b — §7.2 quotation sync request

```text
ORIGINAL ITEM (v2.x)   A REQUEST that AI-15's contract maintainer synchronise
                       §7.2's quotation of AI-14 §22.1 B5, which still read
                       "under the producer token that phase HOLDS".
SUPERSEDING AMENDMENT  AI-15 Amendment 7, 2026-10-12 — the superseded quotation
                       is corrected IN PLACE, with the correction recorded beside
                       it. "NO RULE CHANGES: the topology, its blockers and its
                       prerequisites are exactly as they were."
CLAUSE MAPPING         docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md
                       :1034-1042; the amendment's own record at :4853-4854
EVIDENCE               PR #98, merge 285d5c9e…
NO REOPENING           THE REQUEST'S SUBJECT NO LONGER EXISTS in the current
                       tree. AI-14's owner holds no part of AI-15's text, and
                       AI-15's text was corrected by AI-15's owner under §19.
```

### C4 — §24 "committed BEFORE the code that depends on it" vs the same-merge rule

```text
ORIGINAL ITEM (v2.x)   Read literally, §24 required the classification amendment
                       to be committed before the code, which §22.1 forbids
                       merging separately.
SUPERSEDING AMENDMENT  AI-14 Amendment 5(d), 2026-10-12 — §24 gains a
                       clarifying block separating a PREREQUISITE amendment
                       (changes a rule; committed first) from a CLASSIFICATION
                       amendment (states an outcome; in the same change as the
                       code), and records that "A PREREQUISITE AMENDMENT MUST NOT
                       ASSERT THE OUTCOME OF THE WORK IT PRECEDES."
CLAUSE MAPPING         docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md
                       :1744-1757 (in tree, under §24 at :1724); the amendment's
                       own record at :2313-2316
EVIDENCE               PR #98, merge 285d5c9e…; AI-15 §15.2 records the same
                       principle at :2789-2792
NO REOPENING           The clarification is in AI-14's contract. The same-merge
                       rule is not weakened by it.
```

### D2 — §7.3.7 writer-absence obligation disposition (sub-items D2.1-D2.8)

```text
ORIGINAL ITEM (v2.x)   Whether §7.3.7's obligation "the absence of a production
                       non-test writer" continued, and what replaced it.
SUPERSEDING AMENDMENT  AI-05 Amendment 9, 2026-10-12 — the obligation was
                       REPLACED by §7.3.13's EXACT APPROVED CALL-SITE SET.
                       "It is REPLACED, NOT DELETED: §34.2 forbids 'a test
                       deleted, weakened, or re-scoped to make a test pass', and
                       a connecting change that simply removed the obligation
                       would be exactly that."
CLAUSE MAPPING         docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:2355-2571 (new
                       §7.3.13, FROZEN); Amendment 9's own record at :7385
                       onwards; §7.3.7's obligation line at :1659-1665
IMPLEMENTED BY         PR #98 (merge 285d5c9e…) — the obligation-18 series in
                       tests/evidence/test_producer_authentication.py: class
                       TestObligation18ApprovedCallSiteSet at :1262, the 18a
                       exact-set assertion at :1278, obligations 18a-18u, and the
                       module-level APPROVED_CALL_SITES at :1243 (a five-field
                       identity key, currently EMPTY);
                       PR #99 (merge 34a685b5…) —
                       tests/evidence/connection_change_verification.py, the
                       two-tree baseline/candidate verification with the one-time
                       pre-connection gate, and tests/evidence/callsite_identity.py,
                       the six-field call-site identity with alias resolution and
                       fail-closed unresolvable forms. The tests that exercise
                       them carry the layer1 mark
                       (tests/evidence/test_connection_change_verification.py:29;
                       tests/evidence/test_producer_authentication.py:65) and run
                       in CI (.github/workflows/preflight.yml:75, :100-166).
WHAT NO LONGER EXISTS  The old 18a writer-absence assertion and its node ids
                       (class TestObligation18NoProductionWriter;
                       test_obligation_18a_no_production_call_site_exists) are
                       gone from the contract, the tests and the workflow. The
                       old four-field authorisation model proposed in the v2.x
                       draft is DELETED and is NOT redesigned here.
NO REOPENING           This entry records supersession ONLY. The disposition is
                       AI-05's owner's act, made in AI-05's contract under
                       AI-05 §34, and is not re-litigated in this packet.
```

**These items are CLOSED. They MUST NOT be re-opened, re-decided, or
re-litigated in this or any later packet; the amendments that closed them stand
in their owners' contracts.**

---

## 3. OPEN decision register

**All nine items below are listed. Every one is `DECISION REQUIRED`: no option in
this packet has been approved, and no recommendation, draft or audit finding
below is an owner's decision.**

| ID | Item | Authorized owner(s) | Status | Required deliverable | Gate / invariant to preserve |
|---|---|---|---|---|---|
| D3 | First target event for the composition → Evidence connection | project owner | **DECISION REQUIRED** | a signed decision naming the event, with the recommendation recorded as a recommendation only, and with the matters that remain unresolved named in it | the choice connects nothing and establishes no producer identity; no production call site is authorised by it; no CONNECTED claim may follow from it |
| D4 | Deployment trust configuration (`WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG`) | project owner | **DECISION REQUIRED** | the named responsible party, plus the mapping and its injection method | AI-05 §7.3.2's one-key-per-recognized-token rule; an absent, malformed or colliding mapping keeps every submission REJECTED — no writer may run before this resolves |
| D5 | `ai-06` private-key custody | project owner | **DECISION REQUIRED** | the named party and the generation / storage / rotation / destruction rules | AI-05 §7.3.9 makes key custody and mapping correctness trust assumptions outside the contract; a forwarder MUST NOT generate or replace a proof (AI-05 §7.3.12) |
| D6 | `AdmissionOutcome` propagation | implementing party **and** AI-14 owner — **both must sign** | **DECISION REQUIRED** | the proposed propagation interface and runtime behaviour, plus AI-14 owner's review of its effect on the composition boundary, result semantics and STEP 3 | AI-15 §7.4's `UNDETERMINED` stands until ruled; §8.3 conditions 8 and 10 hold; no authorize stage exists and none may be added; **one signature alone decides nothing and STEP 2 stays BLOCKED** |
| D7 | `PROJECT_STATUS.md` / `MASTER_ROADMAP.md` synchronisation | project owner | **DECISION REQUIRED** | the named maintainer, the authorised sources, the non-overclaim rule, and the timing (after re-verification) | must not mark STEP 2, STEP 3 or any seam complete; must not supply evidence to the joint change; AI-14's classification authority and AI-05's contract authority are untouched |
| D8 | Joint integration acceptance owner | project owner | **DECISION REQUIRED** | the named accepting party, plus the signed acknowledgement that the role excludes making AI-14's STEP 3 classification | only AI-14's owner states the STEP 3 classification, and only in the same change as the call site; the accepting party's remit excludes it |
| N1 | The AI-06 §15.8 signing-helper delivery decision | project owner (which work is undertaken); the §15.8 deferral path belongs to AI-06's owner | **DECISION REQUIRED** | a signed choice between Reading 1 and Reading 2, with the contract tension recorded either way | §15.8 as frozen says the joint change MUST ship the eight negative tests; until they exist and run, the boundary is a rule and not a demonstrated property |
| N3 | The `store.write` acceptance-assertion decision | AI-05 owner (if the assertion lands in the acceptance module); the joint review is the applying surface | **DECISION REQUIRED** | whether an assertion that production code contains no direct `StagedEvidenceStore.write` call outside the admission entry points is added, and if so which owner authors it | the constraint is a RULE, not a check; `StagedEvidenceStore.write` is public and callable; §8.3 condition 9 requires `admit_to_store`, not a bare `store.write` |
| N4 | The AI-15 §20 fourth-same-change-surface decision | AI-15 contract maintainer (the act) with the project owner (the plan) | **DECISION REQUIRED** | a signed record of how AI-15 §8.3 condition 2's second naming surface is executed in the joint delivery, and by whom | §8.3 condition 2 requires the call site named by file and line in AI-14 §5.1 AND in AI-15 §20, in the same change that connects it; AI-15's contract is amended only by AI-15's owner under §19 |

**No decision box in this packet has been signed. No owner input has been
received for any item.**

---

### D3 — First target event

**Question:** which event does the composition → Evidence connection target
first?

#### The recommendation

> **RECOMMENDATION (not a decision): adopt the AI-06 `tool execution` event
> (`kind` = EXECUTION, `producer` = `ai-06`, `actor.type` = `agent`) as the first
> target event for the composition → Evidence connection.**

This is the recommendation the v2.x draft carried, kept in substance. It is a
recommendation only: it decides nothing, and the owner may reject or modify it.

#### Facts (verified at 34a685b5)

| # | Fact | Location |
|---|---|---|
| 1 | AI-06 §15.1 FROZEN: AI-06 "does not call admission … It produces a projection, and the caller submits it through AI-05's existing entry point." | `docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1003-1005` |
| 2 | AI-06 §15.2 FROZEN: one tool invocation → one `ToolResult` → one AI-05 `ToolCall` | `docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1013-1017` |
| 3 | AI-06 §15.7: both AI-06 registry rows are real; the distinction is `actor.type` (`agent` = tool execution, `service` = test result) | `docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1097-1107` |
| 4 | AI-15 §5.2 RECORDED: §15.1 is "the ONLY frozen contract clause in the repository that names a submitter, and it names 'the caller'" | `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:796-797` |
| 5 | AI-15 §7.2 defines T2 (composition as submitter of an owner-authored record); AI-15 §7.3 FROZEN concludes T2 is the only topology consistent with the frozen contracts | `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:1030-1043`, `:1076-1079` |
| 6 | AI-15 §17.3: the AI-06 path needs no §6.5 amendment — "the AI-06 rows exist and AI-06 §15.1 names a caller" | `docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:3488-3495` |
| 7 | Registry rows exist | `plugins/evidence/models.py:143-150` |

#### What approving this does not establish — required to be recorded with the decision

```text
1. NO PRODUCTION CALLER EXISTS. `controlled_verification`
   (composition/verification.py:167) is called only from
   tests/composition/test_controlled_verification.py:65. Choosing a target event
   is not evidence that any production end-to-end path exists.

2. NO PRODUCER IDENTITY IS ESTABLISHED BY THE CHOICE. AI-05 §7.3.1: the
   mechanism establishes A KEY HOLDER, and "The step from 'the holder of T's key
   signed' to 'component T produced this' is a DEPLOYMENT ASSERTION, not a
   cryptographic one" (docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:729-732).

3. THE MATTERS THAT REMAIN UNRESOLVED ARE NOW: D4, D5, D6, N1 (with its
   conditional N1-C), N3 and N4. The v2.x draft's U1 (the persist /
   admit_to_store boundary) is RESOLVED by AI-14 Amendment 5(a) and U4's D1 and
   D2 are RESOLVED by AI-14 Amendment 5(c), AI-05 Amendment 9 and PRs #98/#99
   (see §2). U1 and U4 MUST NOT be listed as unresolved.

4. NO SEAM BECOMES CONNECTED. B5 remains BLOCKED; AI-15-B remains NOT STARTED;
   STEP 2 must not begin.
```

#### Decision scope

A decision must determine the first target event and record, with it, items 1-4
above. Options may include the recommended AI-06 `tool execution` event, another
event whose §6.5 row already exists, or a decision to defer; each carries its own
consequences, and none is chosen here.

```text
D3 — FIRST TARGET EVENT
  decision        [ ] ACCEPT AS RECOMMENDED
                  [ ] REJECT
                  [ ] NEEDS MODIFICATION: __________________________________

  Recorded with the decision (required):
    acknowledged   [ ] no production caller exists today
    acknowledged   [ ] the choice does not establish producer identity
    acknowledged   [ ] D4, D5, D6, N1 (and N1-C), N3 and N4 remain unresolved
    acknowledged   [ ] no seam becomes CONNECTED

  decider   ______________________________
  date      ______________________________
  reason    ______________________________________________________________
  contract(s) this decision applies to: __________________________________
```

**Until this block is signed, D3 = DECISION REQUIRED.**

---

### D4 — Deployment trust configuration

**Question:** who owns the actual configuration and deployment of
`WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG`?

#### Facts (verified at 34a685b5)

- The variable is read **once**, at module import, by the one reader:
  `plugins/evidence/producer_auth.py:70` (`_ENV_NAME`) and `:251-253`
  (module-level `_SUPPLIED_VALUE` / `_STATE`). There is deliberately no function
  that reads it (`:245-249`).
- Outside the reader the name occurs once more in code:
  `tests/evidence/trust_harness.py:75` (`ENV_NAME`).
- `.env.example` does **not** list the variable.
- An absent, malformed or colliding mapping is the same state: every submission
  is REJECTED with `AUTHENTICATION_KEY_UNAVAILABLE` for the process lifetime
  (`plugins/evidence/producer_auth.py:409-416`; AI-05 §7.3.2 at
  `docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:804` — ONE KEY PER RECOGNIZED PRODUCER
  TOKEN — and §7.3.8 at `:1680`).
- AI-05 §7.3.9: revocation "DOES NOT REACH BACKWARDS"
  (`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:1784`), so neither a missing nor a
  wrong mapping is detectable after a record is stored.

**Why it must be resolved before the first persisted record:** with no usable
mapping, a connected writer admits nothing; with a wrong mapping, it admits under
a key the deployment did not intend.

**Must be resolved before the first persisted record: YES.**
**May be prepared in parallel during CP-A: YES** (configuration only; creates no
writer).

#### Decision scope

A decision must determine the responsible party, the mapping and its injection
method. No option is recommended here.

```text
D4 — TRUST CONFIGURATION OWNER
  responsible party  ______________________________
  mapping source     ______________________________________________
  injection method   ______________________________________________
  decider   ______________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________
```

**Until this block is signed, D4 = DECISION REQUIRED.**

---

### D5 — `ai-06` private-key custody

**Question:** who generates, holds, rotates and destroys the private key whose
public half the deployment maps to producer token `ai-06`?

#### Facts (verified at 34a685b5)

- AI-05 §7.3.9 records key custody — generation, storage, backup, rotation,
  destruction — and the correctness of the mapping as **trust assumptions
  outside the contract** (`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:1805-1808`).
- AI-05 §7.3.12 FROZEN: "A FORWARDER MUST NOT GENERATE A PROOF" — minting one
  requires the producer's private key, and §7.3.11 puts public key material only
  in the deployment's configuration
  (`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:2307-2312`).
- AI-05 §7.3.2 FROZEN: ONE KEY PER RECOGNIZED PRODUCER TOKEN, and no sharing
  with anything else (`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:804`).
- AI-06 §15.8 FROZEN: THE PRIVATE KEY IS NEVER IN THIS REPOSITORY; key
  generation, storage, backup, rotation and destruction are the deployment's and
  are outside that contract (`docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1130-1133`).

**Why it must be resolved before the first persisted record:** a record admitted
under `ai-06` asserts that the holder of `ai-06`'s key signed it. If no party
holds that key, no record can be admitted; if the wrong party holds it, the
record's producer claim is a deployment error indistinguishable, in the record,
from a correct one.

**Must be resolved before the first persisted record: YES.**
**May be prepared in parallel during CP-A: YES** (key lifecycle operations do not
touch the admission path).

#### Decision scope

A decision must determine the responsible party and the generation / storage /
rotation / destruction rules. No option is recommended here.

```text
D5 — KEY CUSTODY OWNER
  responsible party  ______________________________
  generation         ______________________________________________
  storage            ______________________________________________
  rotation           ______________________________________________
  destruction        ______________________________________________
  decider   ______________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________
```

**Until this block is signed, D5 = DECISION REQUIRED.**

---

### D6 — `AdmissionOutcome` propagation

**This item carries TWO signature records — "D6 — implementing party" and
"D6 — AI-14 side". They are separate records and BOTH must sign the same option.
A signature by one party alone decides nothing, and STEP 2 stays BLOCKED on a
partial signature.**

#### The open contract state, preserved

```text
AI-15 §7.4  (docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:1155-1156)
    Q  who exposes the admission result to the caller?
    A  UNDETERMINED. §11 fixes what MUST be observable; it does not fix the
       plumbing.
```

**This section does not resolve that. `UNDETERMINED` stands until the
responsible contract parties rule, and adding this section is not a ruling.**

#### Facts (verified at 34a685b5)

```text
AI-15 §8.3 condition 8  (:1213-1217)
    the AdmissionOutcome is PROPAGATED to the caller AS A VALUE — never as an
    exception, never swallowed, never re-read as a success; and in the other
    direction, no API misuse is recast AS an outcome: a programming error stays
    an exception and MUST NOT be reported as REJECTED or UNAVAILABLE

AI-15 §8.3 condition 10  (:1220-1222)
    the authority matrix is unchanged, and the change names what it did NOT
    prove: that an ACCEPTED is not an authorization, and that a stored record is
    not a grant

AI-15 §9.5   (:1712-1755)  authentication is not authorization, in either
                           direction
AI-15 §10.4  (:1868; the FROZEN clause at :1888-1898)
                           NO authorize stage exists in this pipeline, and none
                           may be added; the earlier "authorize evidence
                           production" model is WITHDRAWN and MUST NOT be
                           reintroduced
```

#### Who decides, and how

| Party | Responsibility in D6 |
|---|---|
| **implementing party** | proposes the concrete propagation interface and the runtime behaviour: what the caller receives, in what shape, at which boundary, and what happens on each of `ACCEPTED` / `REJECTED` / `UNAVAILABLE` |
| **AI-14 owner** | reviews the proposal for its effect on the composition boundary, on result semantics, and on AI-14's own STEP 3 classification responsibility |

Both parties sign below. **A signature by one party alone does not decide D6.**

#### Disagreement handling

```text
If the implementing party and AI-14's owner do not both sign the same option,
D6 REMAINS DECISION REQUIRED and STEP 2 REMAINS BLOCKED. A partially signed D6
decides nothing.

ESCALATION (recorded, not exercised): the disagreement MAY be referred to the
project owner for a decision on WHICH WORK IS UNDERTAKEN — for example, to
re-scope or defer the propagation question. The project owner's handling of that
escalation MUST NOT make AI-14's STEP 3 classification on AI-14's behalf: AI-14
§24 keeps that act with AI-14's owner
(docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md:1761-1763; AI-15 §15.2
STEP 3 at :2760-2763).
```

#### Decision scope

A decision must determine the propagation interface and the runtime behaviour
for each of the three outcomes, and record AI-14 owner's review of its effect on
the composition boundary, result semantics and STEP 3. Options may be named
neutrally — accept as proposed, reject, or modify — and none is recommended here.

```text
D6 — ADMISSIONOUTCOME PROPAGATION — implementing party signature
  technical decision   [ ] ACCEPT the proposed interface and runtime behaviour
                       [ ] REJECT the proposal (state why): __________________
                       [ ] NEEDS MODIFICATION: ________________________________

  name/role  ______________________________  date ______________
  reason     ______________________________________________________
  contract(s) this decision applies to: ____________________________
  [ ] confirms the proposal keeps AI-15 §8.3 conditions 8 and 10, and adds no
      authorize stage (§10.4)
```

```text
D6 — ADMISSIONOUTCOME PROPAGATION — AI-14 side signature
  technical decision   [ ] ACCEPT the same option the implementing party signed
                       [ ] REJECT (state why): ________________________________
                       [ ] NEEDS MODIFICATION: ________________________________

  name/role  ______________________________  date ______________
  reason     ______________________________________________________
  contract(s) this decision applies to: ____________________________
  [ ] confirms this review does NOT constitute AI-14's STEP 3 classification,
      which remains AI-14's act alone, in the same change as the call site
```

```text
[ ] this section does not decide D6
[ ] AI-15 §7.4's UNDETERMINED status is preserved
[ ] no production call site is authorised by this section
[ ] D6's signature does not authorise STEP 2 to begin while D3, D4, D5 or N1
    remain undecided
```

**Until BOTH blocks carry the same signed option, D6 = DECISION REQUIRED.**

---

### D7 — `PROJECT_STATUS.md` / `MASTER_ROADMAP.md` synchronisation

#### D7.1 The regenerated conflict inventory at 34a685b5

The two status documents disagree with the contracts they describe. The inventory
below was regenerated against the baseline named at the top of this file; it does
not carry the v2.x counts. Recorded, not resolved.

```text
1. AI-15 AMENDMENT COUNT.
   docs/PROJECT_STATUS.md:15 ("AI-15's contract has since been AMENDED FOUR
   TIMES") and :2126 ("FROZEN @ PR #78; AMENDED FOUR TIMES");
   docs/MASTER_ROADMAP.md:1020 and :1310 (the same "AMENDED FOUR TIMES").
   AGAINST: AI-15 §19 (:3680) records SEVEN TIMES, naming Amendments 1-7.

2. AI-15 INTERNAL divergence (new). AI-15's own `## Status` (:5045) still reads
   "amended SIX TIMES", and its enumeration ends at Amendment 6 (:5064-5070),
   with no Amendment 7 line anywhere in the block (:4990-5113). AI-15 §19
   (:3680) records SEVEN, and Amendment 7's "WHAT THIS AMENDMENT CHANGES"
   (:4858) claims "`## Status` the amendment count and the Amendment 7 line"
   were updated. This is a record-vs-reality divergence inside AI-15's contract
   left by PR #98; its correction is AI-15's owner's act under §19.

   A SECOND INSTANCE OF THE SAME CLASS, VERIFIED. AI-15's text still describes
   the joint change as two-author in three places, although AI-15 Amendment 7
   recorded it as three-party: §17.2d's heading (:3398, "THE CHANGE HAS TWO
   PARTS AND TWO AUTHORS") above the three-row table Amendment 7 added
   (:3400-3418, with the third-row note at :3420-3426); §15.2's STEP 3 owner
   line (:2750, "the two parts merge as one change with two authors", restating
   STEP 2's joint-change rule — STEP 2's own block carries the same two-owner
   shape at :2720-2730); and §16.2's `joint` blocker row (:3098-3103, "a change
   with two authors"). Its correction is likewise AI-15's owner's act under §19.

3. AI-14 AMENDMENT COUNT.
   docs/PROJECT_STATUS.md:222 and :1961 ("FROZEN @ PR #72; AMENDED THREE TIMES
   ON `main`"); docs/MASTER_ROADMAP.md:933 (the same) and :1309 ("contract
   FROZEN + AMENDED THREE TIMES ON `main`").
   AGAINST: AI-14's header (:3-5) records AMENDED FIVE TIMES.

4. STEP 1 DISCHARGE WORDING.
   docs/PROJECT_STATUS.md:21 and :27-31 and :88 and :705 still state "AI-14 STEP
   1 IS NOT FULLY DISCHARGED" and "AI-14'S OWN CONTRACT HAS NOT BEEN UPDATED BY
   AI-14"; docs/MASTER_ROADMAP.md:961-962 ("AI-14's OWN CONTRACT still carries
   the older OPEN record — AI-14 has not updated it") and :1089-1093 (the same
   in Chinese).
   AGAINST: AI-14 Amendment 4 (:2193-2270) records STEP 1's enumerated checklist
   as DISCHARGED and records the stale row as CORRECTED, and AI-15 §19 Amendment
   6 (:4670 onwards) records the same discharge.

VERIFIED: every line number above was read in the current tree.
```

**Three conflicts carried by the v2.x draft are RESOLVED in the current tree and
MUST NOT be re-listed:**

```text
the §22.1 ORDER vs B5 tension          resolved by AI-14 Amendment 5(b) — the
                                       scope note is in the tree at
                                       docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md:1355-1363
the test:1302 stale failure message    resolved by PR #98 — the class and 18a
                                       were renamed and rewritten, and no
                                       "while AI15-OPEN-1 is open" message
                                       remains in tests/evidence/
the §7.2 HOLDS quotation               resolved by AI-15 Amendment 7 — the
                                       correction is in the tree at
                                       docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:1034-1042
```

**Nothing in this packet edits either document.**

#### D7.2 The questions to be decided

```text
1. AUTHORISATION   Is the synchronisation approved at all — to be performed only
                   AFTER the authoritative contract states, merge commits and PR
                   states have been re-verified?
2. OWNERSHIP       Who maintains PROJECT_STATUS.md and MASTER_ROADMAP.md?
3. SOURCES         Which verified sources may an update cite? (candidate set:
                   the phase contracts themselves, the merge commits recorded in
                   each amendment, and PR state as returned by the forge — not
                   another status document)
4. NON-OVERCLAIM   How is an update prevented from marking STEP 2 or STEP 3, or
                   any seam, as complete? (candidate rule: a status document may
                   record only what a contract records, and MUST NOT introduce a
                   classification the owning contract has not made)
5. AUTHORITY       How are AI-14's classification authority and AI-05's contract
                   maintenance authority preserved through the update?
6. TIMING          When does it run, and does it run as its own change with its
                   own review rather than folded into the joint STEP 2 + STEP 3
                   change?
```

**Recommendation (not a decision):** schedule the synchronisation **after** the
authoritative contract states are re-verified, and perform it as its own change
with its own review. Do not fold it into the joint STEP 2 + STEP 3 change, where
it could supply "evidence" the joint change has not earned.

#### D7.3 Decision record

```text
D7 — STATUS-DOCUMENT SYNCHRONIZATION
  [ ] ACCEPT — synchronise after re-verification, under the rules recorded above
  [ ] REJECT — leave the two documents as they are (reason): ______________
  [ ] NEEDS MODIFICATION: ________________________________________________

  main maintainer (named by this decision)  ______________________________
  sources authorised for the update         ______________________________
  non-overclaim rule adopted                ________________________________
  decider   ______________________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________

[ ] the two status documents are UNCHANGED by this packet
[ ] the conflicts listed in D7.1 are PRESERVED, not eliminated
[ ] D7 remains DECISION REQUIRED until responsibility, content and timing are
    approved
```

**Until this block is signed, D7 = DECISION REQUIRED.**

---

### D8 — Joint integration acceptance owner

**Question:** who performs the final joint integration acceptance for the
three-party change, and on what terms?

#### Recommendation

> **RECOMMENDATION (not a decision): AI-14's owner chairs the acceptance. Each of
> the three parties signs for its own part. The acceptance role explicitly does
> NOT include making AI-14's STEP 3 classification on AI-14's behalf.**

#### Facts (verified at 34a685b5)

```text
1. Only AI-14's owner states the STEP 3 classification, and only in the same
   change as the call site:
       AI-15 §15.2 STEP 3 (:2760-2763) — "STEP 3 IS THE ONLY STEP THAT MAY USE
       THE WORD CONNECTED ABOUT THIS EDGE, AND IT IS THE ONLY STEP THAT MAY
       WRITE IT DOWN."
       AI-15 §17.2d (:3440-3444) — AI-14's owner must personally make or
       formally submit and approve its contract, Layer 0 constant, test
       assertions and classification parts.
       AI-14 §24 (:1761-1763) — AI-14 does not own AI-00…AI-13, and MUST NOT
       amend another phase's contract.

2. Naming the third party transfers nothing:
       AI-15 §17.2d (:3420-3426) — "NAMING IT TRANSFERS NOTHING: AI-05 does not
       classify this edge, does not author AI-14's clauses, and does not approve
       them."
       AI-14 §22.1 B5 (:1551-1556) — the CONNECTED classification of this edge
       remains AI-14's; naming AI-05 as a co-deliverer gives AI-05 no part of it.

3. A classification merged separately from the call site does not satisfy
   AI-14 §22.1 (AI-15 §17.2d, :3460-3465).

4. The three-party shape itself is CLOSED HISTORY (§2, D1 and C3a); what remains
   open here is only WHO ACCEPTS and ON WHAT TERMS.
```

**Must be resolved before the first persisted record: YES** (the accepting party
must be named before the change merges).
**May be prepared in parallel during CP-A: YES** (naming the party).

#### Decision scope

A decision must name the accepting party and record the acknowledgement that the
role excludes making AI-14's STEP 3 classification. Options may be named
neutrally; the recommendation above is a recommendation only.

```text
D8 — JOINT INTEGRATION ACCEPTANCE
  accepting party    ______________________________
  acknowledged       [ ] the acceptance role does NOT include making
                         AI-14's STEP 3 classification on AI-14's behalf
  acknowledged       [ ] AI-05 signs its own contract/CI-compatibility part
  acknowledged       [ ] the implementing party signs its runtime part
  decider   ______________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________
```

**Until this block is signed, D8 = DECISION REQUIRED.**

---

### N1 — The AI-06 signing-helper delivery decision

**THE QUESTION:** must the joint change deliver the AI-06-side signing boundary —
the `ProducerSigner` consumption and the eight negative tests AI-06 §15.8
requires — as part of its runtime part?

#### Facts (verified at 34a685b5)

```text
AI-06 §15.8 is FROZEN (Amendment 2, PR #98) —
docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1109 onwards:

    the signing capability is INJECTED BY THE DEPLOYMENT and is NOT BUILT in
      this repository; AI-06 declares an interface and consumes an
      implementation (:1121-1124)
    the private key is NEVER in this repository; key generation, storage,
      backup, rotation and destruction are the deployment's (:1130-1133)
    an ABSENT CAPABILITY IS REFUSED, NOT FAKED — no placeholder, no empty
      proof, no proof signed by anything else (:1134-1139)
    the signed input is the COMPLETE SUBMITTED MAPPING — AI-05 §7.3.4's signed
      input, and every semantic field the signature covers must have a defined
      source; the sources are exactly three and there is no fourth
      (:1161-1189)
    the order is CHECK, THEN SIGN (:1191-1195)
    "PR-2 — the joint change — MUST ship the negative tests that show the rules
      hold" (:1203-1206)
    the eight negative tests are enumerated at :1210-1226
    "UNTIL THOSE TESTS EXIST AND RUN, THIS BOUNDARY IS A RULE AND NOT A
      DEMONSTRATED PROPERTY, and no report may describe it as demonstrated."
      (:1228-1229)

NO TEST HAS RUN. The packet ran nothing, and no helper exists in the tree:
`ProducerSigner` occurs in AI-06's contract text only
(docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1126, :1553), in no code module,
and no test under tests/ exercises a signing boundary.
```

#### The two readings, stated neutrally

**Reading 1** — the joint change delivers the signing-boundary consumption and
the eight negative tests in its runtime part; the conditional action **N1-C**
(below) applies; the boundary becomes a demonstrated property when the tests run
in CI.

**Reading 2** — the joint change does not deliver the helper or the tests this
round; the eight-test obligation is not discharged; §15.8's boundary remains "a
rule and not a demonstrated property", and that status is recorded as an accepted
risk.

**CONTRACT TENSION THAT MUST BE RECORDED (it is a fact, not a choice).** §15.8 as
frozen says the joint change MUST ship the tests. Under Reading 2 the joint change
either ships them anyway — which is Reading 1 in effect — or AI-06's owner must
amend §15.8 to defer the obligation, an act that is AI-06's owner's under AI-06's
amendment rule and is NOT made or foreclosed by this packet.

#### Decision scope

A decision must choose between the two readings and record the contract tension
above with it. No choice is made or recommended here.

**Owner:** the project owner (which work is undertaken), with the §15.8 deferral
path belonging to AI-06's owner.

```text
N1 — AI-06 §15.8 SIGNING-HELPER DELIVERY
  decision   [ ] READING 1 — the joint change's runtime part carries the
                 signing-boundary consumption and the eight negative tests;
                 N1-C applies
             [ ] READING 2 — the joint change does not deliver them this round;
                 the obligation is not discharged and the residual status is
                 recorded as an accepted risk (state where): ______________
             [ ] NEEDS MODIFICATION: ______________________________________

  recorded with the decision (required):
    acknowledged  [ ] the contract tension between §15.8 as frozen and the
                      chosen reading is recorded above
    acknowledged  [ ] if Reading 2 is chosen, any §15.8 deferral is AI-06's
                      owner's act under AI-06's amendment rule, not this
                      packet's

  decider   ______________________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________
```

**Until this block is signed, N1 = DECISION REQUIRED.**

---

#### N1-C — CONDITIONAL ACTION (a subsection of N1, not a register item)

```text
N1-C is an ACTION attached to N1, NOT the N1 decision.
N1-C does not close N1.
N1-C is NOT a gate.
N1-C is NOT an independent register item.
If Reading 2 is chosen, N1-C does not arise, and nothing else in this packet
depends on it.
```

It exists ONLY under Reading 1. If Reading 1 is chosen: an AI-14 §24 amendment
recording, in §22.1 B5's joint-delivery description, that the joint change's
runtime part carries the AI-06 §15.8 signing-boundary delivery and its eight
negative tests.

The amendment REFERENCES §15.8. AI-14 must not restate or author AI-06's text:
"AI-14 owns this document. It does NOT own AI-00 … AI-13. An amendment to one of
those is made by that phase under that phase's own amendment rule, BEFORE AI-14
depends on it — AI-14 MUST NOT amend another phase's contract from here."
(`docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md:1761-1763`.)

**No signature box of its own** — N1-C is signed, if at all, inside N1's record
when Reading 1 is adopted.

---

### N3 — The `store.write` acceptance-assertion decision

**THE QUESTION:** must the joint change's acceptance obligations include an
assertion that production code contains no direct call of
`StagedEvidenceStore.write` (or any Evidence store `.write`) outside the
admission entry points?

#### Facts (verified at 34a685b5)

```text
`StagedEvidenceStore.write` is public and callable
    plugins/evidence/store.py:270 — it refuses only digest-less records
    (:280-285) and duplicate ids, and nothing else.

the construction recipe a composition could reach is public
    plugins/evidence/__init__.py:42-46 documents the public usage
    (`EvidenceRecord.from_mapping`, `assign_digests`), and `write` is the store
    method such a recipe would then call (plugins/evidence/store.py:270).

the combination bypasses §30's pipeline
    `admit_to_store` runs `admit` (steps 1-13, authentication included), step
    14's duplicate check and then `store.write`
    (plugins/evidence/admission.py:228-299). A direct `store.write` skips all of
    it: AI-15 §10.2 states that it "would bypass §30 steps 1-13 entirely"
    (docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:1838-1839), and step 14
    with them.

the §7.3.13 scanner watches only the admission entry points
    tests/evidence/callsite_identity.py:53 —
    CANONICAL_ENTRYPOINTS = ("admit", "admit_to_store").

no Layer 0 check covers store.write
    scripts/ci/layer0_policy.py contains no check over
    `StagedEvidenceStore.write` or a bare `store.write` call; the constraint is
    a rule, not a check.

the contract states it as a rule
    AI-15 §10.2 (:1838-1842) — "FROZEN: the caller MUST NOT call `store.write`
    directly. It would bypass §30 steps 1-13 entirely, and
    `StagedEvidenceStore.write` (store.py:270) IS CALLABLE — so this is a rule,
    not a build-time check, and nothing in the repository refuses it. It is
    stated as a rule and the reviewer is told it is one."

§8.3 condition 9 requires `admit_to_store`, not a bare `store.write`
    docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:1218-1219.
```

#### Decision scope

A decision must determine whether such an assertion is added to the AI-05
acceptance part and/or the joint review checklist for the connecting change; and
if it is added, which owner authors it (AI-05's acceptance obligations are AI-05's
part of the joint delivery). **The packet does not choose.**

**Owner:** AI-05 owner (if the assertion lands in the acceptance module), with
the joint review as the applying surface — the owner assignment is itself part of
what the signature confirms.

```text
N3 — STORE.WRITE ACCEPTANCE ASSERTION
  decision   [ ] ADD the assertion to: [ ] the AI-05 acceptance part
                                      [ ] the joint review checklist
                                      [ ] both
             [ ] DO NOT ADD it (reason, and where the existing rule is recorded
                 instead): ______________________________________________
             [ ] NEEDS MODIFICATION: ______________________________________

  if added, author of the assertion  ______________________________
  applying surface                   ______________________________
  decider   ______________________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________
```

**Until this block is signed, N3 = DECISION REQUIRED.**

---

### N4 — The AI-15 §20 fourth-same-change-surface decision

**THE QUESTION:** how is AI-15 §8.3 condition 2's second naming surface executed
in the joint delivery — the call site must be named by file and line in AI-14
§5.1 AND in AI-15's §20, in the same change that connects it — and by whom?

#### Facts (verified at 34a685b5)

```text
§8.3 condition 2 (:1201-1202)
    "the call site is named by file and line, in AI-14 §5.1 AND in this
     document's §20, in the same change that connects it"

AI-15 §20 is the second surface
    docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:4887-4909 — "Appendix —
    the exact current call sites", whose §20.1 records
    `admission.admit_to_store()` as "(none)" (:4897-4898) and whose §20.7
    (:4979-4985) records that the appendix "MUST be re-derived, not trusted,
    when the tree moves — and it MUST be updated in the same change that
    connects a seam."

the three-part joint delivery does not name AI-15's own §20 act
    AI-14 Amendment 5(c) names the runtime part, the AI-14 part and the AI-05
    part (docs/AI-14_LONG_TERM_AI_WORKBENCH_EXECUTION_PLAN.md:1521-1556);
    AI-15 Amendment 7's §17.2d third row
    (docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:3412-3418) names the same
    three. Neither names AI-15's own §20 act.

AI-15's contract is amended by AI-15's owner under §19
    docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:3676-3707 — §19's
    amendment rule, unchanged by any amendment; and §17.4 (:3521-3546) forbids
    editing another phase's contract.
```

#### Decision scope

A decision must determine whether the joint-change plan records the AI-15 §20
naming as an explicit fourth same-change act, and who coordinates it. **The
packet does not choose.**

**Owner:** AI-15 contract maintainer (the act) with the project owner (the plan).

```text
N4 — AI-15 §20 NAMING SURFACE
  decision   [ ] RECORD the §20 naming as an explicit fourth same-change act
             [ ] DO NOT (reason): __________________________________________
             [ ] NEEDS MODIFICATION: ______________________________________

  coordinating party ______________________________
  executing owner    ______________________________
  decider   ______________________________  date ______________
  reason    ______________________________________________________
  contract(s) this decision applies to: ____________________________
```

**Until this block is signed, N4 = DECISION REQUIRED.**

---

## 4. Three-party delivery matrix (work-item view)

**This section is the WORK-ITEM view; §3 is the DECISION view.** They describe
the same owners and must not be read as two different assignments. A work item is
`BLOCKED` when a decision it depends on is still `DECISION REQUIRED`; the item's
status therefore never reads as "further along" than the decision it waits on.

| Work item | Owner (same as §3) | Deliverable | Precondition | Acceptance evidence | Status |
|---|---|---|---|---|---|
| STEP 2 runtime call site | implementing party | call site + wiring + its own tests | D3, D4, D5, D6 and N1 decided; row 1′ already satisfied for the AI-06 rows | AI-15 §8.3's twelve conditions, condition 2 included | **BLOCKED** |
| STEP 3 classification | AI-14 owner | §5.1, §22.1 B5, Appendix A, §25, the Layer 0 constant, and the composition assertions in `tests/composition/` | STEP 2 in the SAME merged change | AI-15 §8.3's twelve conditions; AI-15 §15.2 STEP 3 (:2760-2763) | **BLOCKED** |
| AI-05 compatibility delivery | AI-05 owner | the acceptance obligations AI-05's contract imposes on the connecting change, and the CI matrix node list that runs them | BLOCKED on nothing that is closed — the v2.x D2 dependency is CLOSED by AI-05 Amendment 9 (§2); the acceptance part's CONTENT remains pending N3's decision (§3); what remains for AI-05's part is named in §17.2d's third row (:3412-3418) | AI-05 §34 amendment + green CI (**NOT RUN this round**) | **NOT BLOCKED ON ANY CLOSED ITEM — content pending N3** |
| Propagation interface | implementing party + AI-14 owner | the propagation interface, its runtime behaviour, and AI-14 owner's boundary review | **both** must sign D6 | AI-15 §8.3 conditions 8 and 10; §7.4's `UNDETERMINED` resolved by its owners | **DECISION REQUIRED** |
| Trust configuration and key custody | project owner | mapping and injection method; key lifecycle rules | D4, D5 decided | AI-05 §7.3.2, §7.3.9, §7.3.12 | **DECISION REQUIRED** |
| Acceptance ownership | project owner | the named accepting party and its remit | D8 decided | AI-15 §17.2d (:3420-3426, :3440-3444) | **DECISION REQUIRED** |
| Status-document synchronisation | project owner | maintainer, sources, non-overclaim rule, timing | D7 decided; contract states re-verified | the two documents' own diff | **DECISION REQUIRED** |
| row 1′ for non-AI-06 events | AI-05 + that phase | §6.5 row + that phase's own writer clause + its Layer 0 narrowing | — | — | **BLOCKED** (not this round) |
| AI15-OPEN-3 | AI-04 | — | — | — | **OPEN**, untouched |
| AI15-OPEN-4 | AI-13 / AI-14 | — | — | — | **OPEN**, untouched |
| AI-11 §21.1 OPEN-1 | AI-05 | §6.5 token | — | — | **OPEN**, untouched |

### Responsibility boundaries that must not move

```text
implementing party   writes the runtime part and its own tests; writes NO contract
AI-14 owner          writes AI-14's contract, its Layer 0 constant, its test
                     assertions and the STEP 3 classification; writes NO AI-05 text
AI-05 owner          writes AI-05's contract, its acceptance module and its CI
                     matrix node list; writes NO AI-14 classification
AI-15                authors nothing here (AI-15 §17.4:3521-3546)
```

---

## 5. CP-A v3.0 completion conditions

CP-A v3.0 is satisfied only when every row below carries a **signed** conclusion
with a decider, a date, a reason and the contract it applies to.

**One row per OPEN register item — the same nine, in the same order.**

| # | Condition (register ID) | Authorized owner(s) | Status |
|---|---|---|---|
| 1 | D3 — first target event decided | project owner | **NOT MET** |
| 2 | D4 — trust configuration ownership and mapping decided | project owner | **NOT MET** |
| 3 | D5 — `ai-06` key custody decided | project owner | **NOT MET** |
| 4 | D6 — propagation interface decided and signed by **both** parties | implementing party + AI-14 owner | **NOT MET** |
| 5 | D7 — status-document synchronisation assigned, with the regenerated inventory | project owner | **NOT MET** |
| 6 | D8 — acceptance owner named, with its remit recorded | project owner | **NOT MET** |
| 7 | N1 — the §15.8 signing-helper delivery decided (N1-C inside N1's record if Reading 1 is adopted) | project owner; the deferral path is AI-06's owner's | **NOT MET** |
| 8 | N3 — the `store.write` acceptance assertion decided | AI-05 owner (with the joint review as the applying surface) | **NOT MET** |
| 9 | N4 — the AI-15 §20 naming surface decided | AI-15 contract maintainer with the project owner | **NOT MET** |

**CP-A v3.0 = NOT SATISFIED. No decision box has been signed.**

---

## 6. States that must be preserved until CP-A v3.0 is satisfied

```text
B5 (composition -> Evidence)              BLOCKED
AI-15-B                                   NOT STARTED / BLOCKED
STEP 2                                    NOT MADE — MUST NOT BEGIN
STEP 3                                    CANNOT RUN (no call site to name)
production call site / production writer  DOES NOT EXIST, NOT AUTHORISED
any CONNECTED claim about this edge       FORBIDDEN
```

### NOT RUN / NOT VERIFIED

```text
AI-05's acceptance matrix
    NOT executed in this round. This packet ran no test and no CI run.
CI run #301 ("46 RAN / 0 skipped") and "Layer 0 = PASS (24 checks)"
    RECORDED IN AI-05's CONTRACT (docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:6941,
    :6953, :6994, :7577-7578). Not re-run, not independently verified here.
Historical run results MUST NOT be presented as current execution.
The eight AI-06 §15.8 negative tests
    DO NOT EXIST and have not run. §15.8's boundary is a rule, not a
    demonstrated property (docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md:1228-1229).
```

### Regenerated conflict inventory — pointer

The live conflicts and their file:line evidence are in **§3 D7.1**. Three
conflicts carried by the v2.x draft are RESOLVED in the current tree and MUST NOT
be re-listed; D7.1 names them. **Nothing in this packet edits
`docs/PROJECT_STATUS.md` or `docs/MASTER_ROADMAP.md`.**

### OPEN items expressly out of scope for this round

```text
AI15-OPEN-3 (AI-04) · AI15-OPEN-4 (AI-13 / AI-14) · AI-11 §21.1's OPEN-1
AI-05 §35.1 (F-10 and the storage-backend / record-digest obligations)
AI-12-C
```

Owners and statuses as the contracts record them: AI-15 §16.1
(`docs/AI-15_EVIDENCE_PRODUCTION_EXECUTION_PLAN.md:3002-3009`), AI-11 §21.1
(`docs/AI-11_SECURITY_BENCHMARK_EXECUTION_PLAN.md:1352`, OPEN-1 at `:1373-1385`),
AI-05 §35.1 (`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md:7633-7648`), AI-12-C
(`docs/AI-12_MODEL_ROUTING_V2_EXECUTION_PLAN.md:492`, `:564`).

---

## 7. To close CP-A v3.0

1. Each owner fills the decision boxes in their item and returns them with a
   decider, a date, a reason and the contract cited. D6 requires both signatures
   on the same option; a partial signature decides nothing.
2. Each accepted draft is then made **by that owner, in that owner's contract,
   under that owner's amendment rule** — AI-14 §24 for AI-14, AI-05 §34 for
   AI-05, and each other owner's own rule for that owner's contract. **This
   packet is not that act.**
3. Only after every box is signed does the joint implementation work become
   eligible to start, and then only under the joint-delivery shape that AI-14
   Amendment 5(c) has already settled (§2, D1).

---

## 8. What this packet is not

- Not a contract or an amendment to any contract.
- Not an approval; no box is signed.
- Not authorisation for code, call sites, producer tokens, registry rows or test
  changes.
- Not an execution record: no test and no CI run was performed in preparing it.
- Not a substitute for the owners' own decision; without a signed box the item
  stays **DECISION REQUIRED**.
- It does not re-open any CLOSED HISTORY item; the amendments that closed them
  stand.
