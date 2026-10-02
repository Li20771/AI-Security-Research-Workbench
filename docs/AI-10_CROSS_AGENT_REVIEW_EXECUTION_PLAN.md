# AI-10 — Cross-Agent Review — Execution Plan

> Status: **FROZEN** (AI-10-A, 2026-10-02)
> Phase: AI-10 — Cross-Agent Review
> Sub-phase: **AI-10-A — Contract / Execution Plan / Freeze**
> Base: `main` @ `2e55b5a1e0c13d559ceb08fd5ca8094410634f11`
> Rule: This document defines the contract. AI-10-B implements against it. Nothing in AI-10 may
> deviate from a frozen contract without amending this document first (§24).

---

## 0. The six responsibilities — read this first

```text
AI-07 Router        selects.
AI-08 Agent         executes, and proves structural independence.
AI-09 Integration   connects the Codex Agent to a provider.
AI-04 Guard         authorizes tool use.
AI-06 Tools         execute research tools.
AI-10 Review        compares declared review material and coordinates verification.
AI-05 Evidence      records admitted facts.
Human               makes the final decision.
```

These are distinct responsibilities owned by distinct phases. AI-10 exists to add the one that
does not exist yet: **a review layer that compares what two Agents declared, requests executable
verification, and hands the result to a human.**

```text
FROZEN: AI-10 MUST NOT merge any two of these responsibilities.
FROZEN: AI-10 MUST NOT move one of them into another layer to make review easier.
```

AI-10 is a **Workbench core service**, reached as the top-level `review/` layer — not a DSH plugin,
not an Agent, not a provider, not a Router, not a Guard, not an Evidence subsystem.

```text
AI-10 does NOT become:
    a third Agent
    a provider
    a Router
    a Guard
    a second Evidence subsystem
    a truth adjudicator
    a benchmark
    a majority-vote engine
```

### The one fact that governs this phase

```text
AI-08's AgentResult carries a reference or a digest — never content (AI-08 §10.2).
AI-09 creates no durable model-output store, and its reference locates no artifact (AI-09 §19).
Therefore, at the time of this freeze, the real analysis of either Agent CANNOT be obtained
by AI-10 automatically, and MUST NOT be invented, reconstructed or inferred from a digest.
```

AI-10-A does not close that. AI-10-A names it, freezes the only legal v1 input boundary around
it, and records what a future amendment would have to change (§13.4, §23).

---

## 1. Purpose

Cross-agent review is the "second opinion" closure AI-00 §13 requires:

```text
Task
  |
DSH analysis
  |
independent Codex analysis
  |
executable verification
  |
human decision
  |
Evidence
```

AI-10 owns the middle of that pipeline: the part that **compares** the two declared analyses,
**requests** executable verification, and **records** a human decision — without ever deciding
which analysis is right.

```text
AI-00 §13 forbids, by name:
    "谁说得更像真的"            judging by which narrative sounds more true
    "两边一致所以一定正确"       treating agreement as proof
    "模型置信度最高所以通过"      passing on a confidence threshold
```

AI-10 inherits all three prohibitions unchanged and adds the mechanism that keeps them
structural rather than aspirational: a closed observation vocabulary with no verdict member
(§9), a separate verification act (§10), and a human-supplied decision (§12).

---

## 2. Scope

### 2.1 In scope for AI-10

```text
this contract (AI-10-A)                                    AI-10-A
the review/ core layer                                      AI-10-B
ReviewCase, ReviewMaterial, ReviewClaim                     AI-10-B
ReviewFinding — the eight structural observations           AI-10-B
VerificationRequest / VerificationObservation               AI-10-B
HumanDecision — run data, human-supplied                    AI-10-B
the AI-10 Layer 0 boundary check                            AI-10-B
the offline test model                                      AI-10-B
the AI-10 evidence record and status updates                AI-10-B
```

### 2.2 Out of scope for AI-10

```text
any change to AI-02 providers/            AI-02 owns it
any change to AI-03 context               AI-03 owns it
any change to AI-04 Guard                 AI-04 owns it
any change to AI-05 Evidence              AI-05 owns it
any change to AI-06 Security Tools        AI-06 owns it
any change to AI-07 routing               AI-07 owns it
any change to AI-08 agents/               AI-08 owns it
any change to AI-09 integrations/         AI-09 owns it
automatic capture of Agent output          PREREQUISITE / BLOCKED (§13.4)
durable model-output storage               out of scope; its own contract
DSH integration                            AI-08 leaves it out; not in v1
Router integration                         AI-07 unchanged; no execution coupling
benchmark scoring                          AI-11 owns it
routing v2 fallback / escalation           AI-12 owns it
retry / resume / long-running workflows    AI-13 owns it
SecurityLab, in any form                   not reachable from this repository
live provider verification                 NOT_RUN here; no provider call
capability promotion                       never AI-10's
```

### 2.3 Non-goals, restated as the boundary

```text
AI-10 is NOT:
    a truth adjudicator
    a verdict engine
    a voting system
    a confidence or scoring system
    a ranking or selection system
    a second authorization path
    a second tool execution system
    an Evidence store
    a model-output archive
    an automatic second-opinion loop
```

---

## 3. Normative language

```text
MUST        a requirement. AI-10-B that violates it is not conformant.
MUST NOT    a prohibition.
FROZEN      binding, and changes only by amendment (§24).
DEFERRED    declared, and deliberately not decided here.
OPEN        named as unresolved, with a stated default where one exists.
```

---

## 4. What cross-agent review is

### 4.1 The discovery this contract is built on

AI-10-A's architecture discovery measured the repository and recorded five facts. Every design
decision below follows from them.

```text
D1  AgentResult carries no content. `AgentResult.result` admits exactly two shapes —
    `sha256:<64 lowercase hex>` or `ref:<opaque token>` (AI-08 §10.2, agents/result.py).
    It cannot carry raw model output, a prompt body, a task body or a tool argument.

D2  The `sha256:` reference locates nothing. AI-09 §19.2.1 freezes it as a provenance /
    content digest reference and forbids presenting it as a retrievable artifact locator.
    There is no store behind it, and a digest is not reversible.

D3  Normalized model output is transient by design. AI-09 §19.2 allows it in the backend's
    memory for the duration of `produce()` and freezes that it never reaches disk, a log, a
    phase evidence record or any durable store; `MimoCodexBackend.produce` returns only the
    digest and drops the `InvocationResult`.

D4  Structural independence is not correctness. AI-08 §9 defines I1–I8 over an execution
    pair, and §9.2 freezes that the finding is never a PASS, a verdict or a correctness claim.

D5  No review mechanism exists. There is no review layer, no review or decision record type,
    no human-decision type, and no AI-05 producer token for any of them.
```

```text
CONSEQUENCE (FROZEN): AI-10 v1 cannot read an Agent's analysis out of AI-08's or AI-09's
    artifacts. Whatever AI-10 compares must be SUPPLIED to it, explicitly, and must be
    treated as a declared claim about an execution — not as verified content.
```

### 4.2 The definition — FROZEN

```text
Cross-agent review is:
    two explicitly supplied ReviewMaterials, each attributed to a registered AgentId and an
    execution instance, compared structurally;
    plus zero or more VerificationRequests, each answered (or not) by an executable
    verification performed through AI-06's invocation path under AI-04's authorization;
    plus exactly one human decision, or an explicit closure without one.
```

```text
FROZEN: a review is over DECLARED MATERIAL and OBSERVED ACTS. It is never over truth.
FROZEN: the unit of review is the ReviewCase (§5). Exactly two sides, LEFT and RIGHT.
FROZEN: LEFT and RIGHT are POSITIONS in a comparison. They are not roles, not precedence,
        not authority, and not a ranking. "Left" does not mean primary or first.
FROZEN: in v1 the two sides MUST be attributed to two DISTINCT registered AgentIds
        (AgentId is AI-08's closed vocabulary, imported by identity). Comparing two
        executions of one AgentId is NOT cross-agent review and is out of scope.
```

### 4.3 What review is not — FROZEN

```text
agreement       is NOT truth
agreement       is NOT a PASS
agreement       is NOT VERIFIED
disagreement    is NOT a failure
independence    is NOT correctness
material difference is NOT disagreement
a finding       is NOT a verdict
a human decision is NOT a model decision
a human decision is NOT a truth claim
COMPLETED       is NOT PASS
```

### 4.4 The questions this contract answers

```text
What exactly is reviewed?          the two supplied ReviewMaterials and their claims (§6, §7)
Who is allowed to supply it?       a controlled caller, by explicit submission; never
                                   automatic capture (§6.3)
Who may read it?                   the review layer and the human decision step; never an
                                   Agent execution input, a provider, a store or a log (§15)
How long does it live?             run-scoped; until the case closes or the process ends (§6.5)
What is persisted?                 nothing, by AI-10, in v1 (§6.5, §13)
What is never persisted?           material content, statements, tool output, raw provider
                                   output, credentials (§15)
How is provenance represented?     declared attribution fields plus a declared source status;
                                   declared is NOT verified (§6.4)
What does comparison mean?         the eight structural observations of §9
What does comparison NOT mean?     agreement, disagreement, truth, correctness, verification (§9.4)
How is verification invoked?       VerificationRequest -> controlled verification caller ->
                                   AI-06 -> AI-04 Guard -> adapter (§10, §11)
Who authorizes verification?       AI-04, through AI-06; permission is supplied by the
                                   controlled caller, never inferred by AI-10 (§11)
Who makes the final decision?      a human, explicitly recorded (§12)
How can a review remain unresolved? UNRESOLVED / NOT_RUN / BLOCKED closure states, with no
                                   forced verification and no forced decision (§14)
```

---

## 5. ReviewCase

### 5.1 Shape

```yaml
ReviewCase:
  review_case_id:     "rc-<opaque>"     # AI-10-generated, opaque
  workspace_id:       <AI-03 workspace identity>
  left_material_id:   <material_id | null>    # null until supplied
  right_material_id:  <material_id | null>
  state:              ReviewCaseState
  schema_version:     1
```

```text
FROZEN: a ReviewCase is a VALUE. Advancing its state produces a new value; it never mutates
        the previous one. A case records what was supplied, observed and decided — in order.
FROZEN: `review_case_id` is opaque. It encodes no Agent, no task, no workspace content and no
        outcome. The `rc-` prefix is a label, not a namespace that carries meaning (the
        ExecutionId rule, AI-08 §7.2, applied here).
FROZEN: one case has exactly two sides, LEFT and RIGHT, and each side holds exactly one
        supplied ReviewMaterial.
FROZEN: a case is scoped to ONE workspace. Materials whose workspace_id disagrees with the
        case's workspace_id are REFUSED rather than accepted and re-scoped.
```

### 5.2 ReviewCaseState — FROZEN, closed

```text
CREATED                  the case exists; no material has been supplied
MATERIALS_SUPPLIED       both sides hold a supplied ReviewMaterial
INDEPENDENCE_OBSERVED    AI-08's I1-I8 predicate ran over the two executions and its
                         finding was recorded verbatim (§8)
COMPARISON_RECORDED      the structural comparison produced its ReviewFindings (§9)
VERIFICATION_REQUESTED   at least one VerificationRequest was issued
VERIFICATION_OBSERVED    at least one VerificationObservation was recorded
HUMAN_DECISION_RECORDED  a HumanDecision was supplied by a human caller
CLOSED                   the case is finished; terminal

UNRESOLVED               terminal closure without a determination
BLOCKED                  terminal closure: a case-level precondition prevented the review
                         from proceeding
NOT_RUN                  terminal closure: the review was intentionally not executed
```

```text
FROZEN: exactly these eleven members. A twelfth is an amendment.
FROZEN: BLOCKED here is a REVIEW-CASE state. It is NOT GuardDecision.BLOCKED,
        NOT ToolOutcome.BLOCKED and NOT AgentExecutionOutcome.BLOCKED. The words collide
        across four closed vocabularies; the types MUST NOT be merged, compared or
        converted (the known cost AI-04 §3, AI-07 §10.1 and AI-08 §11.2 each record).
FROZEN: UNRESOLVED as a case state and UNRESOLVED as a ReviewFinding kind (§9) are two
        different questions answered by two different types. They MUST NOT be conflated.
FROZEN: no state in this vocabulary means PASS, VERIFIED or CORRECT, and none may be
        recorded as one.
```

### 5.3 Legal transitions — FROZEN

```text
CREATED                  -> MATERIALS_SUPPLIED
MATERIALS_SUPPLIED       -> INDEPENDENCE_OBSERVED        (only when §8's conditions hold)
MATERIALS_SUPPLIED       -> COMPARISON_RECORDED
INDEPENDENCE_OBSERVED    -> COMPARISON_RECORDED
COMPARISON_RECORDED      -> VERIFICATION_REQUESTED       (optional)
VERIFICATION_REQUESTED   -> VERIFICATION_OBSERVED        (when an observation is reported)
COMPARISON_RECORDED      -> HUMAN_DECISION_RECORDED
VERIFICATION_OBSERVED    -> HUMAN_DECISION_RECORDED
HUMAN_DECISION_RECORDED  -> CLOSED                       (only for ACCEPTED / REJECTED, §12)
any non-terminal state   -> UNRESOLVED | BLOCKED | NOT_RUN   (explicit closure only)
```

```text
FROZEN: transitions are MONOTONIC. No transition moves a case to an earlier state.
FROZEN: every transition is an EXPLICIT act of a caller. None is automatic, none is
        time-based, and none is inferred from another record's arrival.
FROZEN: verification is OPTIONAL. A case MAY reach COMPARISON_RECORDED and be closed
        UNRESOLVED, or decided by a human, without any VerificationRequest ever existing.
FROZEN: a case MAY NOT be forced to produce a decision, a finding, or a verification.
FROZEN: resume of a closed case is not a transition; it is AI-13's boundary and does not
        exist in v1.
```

---

## 6. ReviewMaterial

### 6.1 What it is — FROZEN

```text
ReviewMaterial is an explicitly submitted review input: a declared analysis, attributed by
its submitter to one Agent execution, carrying a bounded set of declared claims.
```

```text
IT IS      caller-supplied material, run-scoped
IT IS NOT  a field of AgentResult
IT IS NOT  an AI-05 EvidenceRecord
IT IS NOT  a model-output database, cache or archive
IT IS NOT  a shared mutable result pool
IT IS NOT  an input to any Agent execution (§8.3)
IT IS NOT  a verdict, a score or a ranking
```

```text
FROZEN: AI-10 accepts explicitly supplied ReviewMaterial. Nothing more.
FROZEN: AI-10 MUST NOT attempt to reconstruct material from AgentResult.result, from a
        `sha256:` digest, from a `ref:` token, from an InvocationResult, or from a provider.
FROZEN: a digest is not content, and treating one as content is a category error this
        contract names so that no implementation makes it.
```

### 6.2 Shape — FROZEN

```yaml
ReviewMaterial:
  material_id:       "<opaque>"        # submitter-supplied, unique within the case
  agent_id:          AgentId           # AI-08's closed vocabulary, imported by identity
  execution_id:      "<opaque>"        # the execution this material is attributed to
  workspace_id:      <AI-03 workspace identity>
  input_digest:      "<bounded single-line text, max 128>"
  source_status:     AgentExecutionOutcome   # AI-08's, imported by identity — DECLARED
  claims:            [ ReviewClaim, ... ]    # SET-semantic, bounded
  claims_digest:     "sha256:<64 lowercase hex>"   # over the claims only
  material_digest:   "sha256:<64 lowercase hex>"   # over the whole semantic projection
  schema_version:    1
```

```text
FROZEN: `agent_id` MUST resolve through AI-08's `resolve_agent`. An unregistered token is
        REFUSED. A free string is never an identity (AI-08 §5.1, applied here).
FROZEN: `source_status` is DECLARED BY THE SUBMITTER. It records the terminal outcome the
        submitter declares for the referenced execution. It is NOT verified by AI-10, and it
        is never a statement about the material's quality.
FROZEN: `claims_digest` and `material_digest` are AI-10-GENERATED. A caller-supplied digest
        is REFUSED, for the reason AI-05 §14.6.1 gives for its own generated fields.
FROZEN: `material_id` is an audit identifier, supplied once, unique within its case. It is
        not an identity claim about an Agent and never substitutes for `execution_id`.
```

Bounded constants, frozen for v1:

```text
MAX_CLAIMS_PER_MATERIAL            32
MAX_STATEMENT_CHARS                1024
MAX_EVIDENCE_REFS_PER_CLAIM        32
MAX_VERIFICATION_TARGETS_PER_CLAIM 8
MAX_TARGET_DESCRIPTION_CHARS       256
MAX_INPUT_DIGEST_CHARS             128
```

```text
FROZEN: these are security bounds, not formatting preferences. Changing one is an amendment.
FROZEN: there is no unbounded field on ReviewMaterial. A field nobody bounded is a field
        through which a transcript, a log or a secret reaches the review layer.
```

### 6.3 Ingress — EXTERNAL REVIEW MATERIAL INGRESS — FROZEN

```text
FROZEN: v1's only input boundary is EXTERNAL REVIEW MATERIAL INGRESS.

    the material is SUPPLIED to AI-10 by a controlled caller, explicitly, as an act;
    AI-10 does not acquire it, fetch it, discover it, subscribe to it or derive it.
```

```text
MUST NOT be described, documented or recorded as:
    automatic Agent output capture
    automatic DSH output acquisition
    automatic Codex output acquisition
    an output pipeline, a tap, a hook or a subscription
```

```text
FROZEN: automatic acquisition of an Agent's real analysis material does not exist in v1.
        It is a PREREQUISITE / BLOCKED item (§13.4). No part of AI-10 may pretend otherwise,
        and no test may fabricate a captured output to make the path look complete.
```

### 6.4 Declared provenance is not verified provenance — FROZEN

```text
The submitter declares: agent_id, execution_id, workspace_id, input_digest, source_status.
AI-10 records the declaration and checks only what it can check.
```

```text
CAN be checked, when the caller also supplies the two ExecutionRecords (§8):
    the declared execution_id matches a supplied ExecutionRecord's result.execution_id
    the declared agent_id matches that record's request.agent_id
    the declared workspace_id matches that record's result.workspace_id
    the declared input_digest matches that record's request.input_digest
    the declared source_status matches that record's result.outcome

CANNOT be checked, ever, in v1:
    that the material's CONTENT came from that execution.
        The execution's terminal artifact is a reference or a digest. There is no content to
        compare the material against, and AI-10 MUST NOT claim there is.
```

```text
FROZEN: a mismatch between a declared field and a supplied ExecutionRecord is a REFUSAL,
        not a warning (the AI-09 §12.4 alignment rule, applied here).
FROZEN: when no ExecutionRecord is supplied, the declaration stands UNCHECKED, and the case
        MUST record that state. Unchecked is not verified, and it is not a defect to be
        repaired by assumption.
```

### 6.5 Lifetime and persistence — FROZEN

```text
LIVES       in memory, for the review session: from submission until the case is closed or
            the process ends
PERSISTED   nothing. AI-10 v1 has no durable store: no file, no archive, no database, no
            cache, no log line carrying material content
SURVIVES    nothing but the digests, and even the digests are not written by AI-10 in v1
```

```text
FROZEN: no durable store. No file archive. No database. No AgentResult injection.
        No automatic cross-agent mutation.
FROZEN: material does not survive the process, and nothing may be built that expects it to.
```

### 6.6 What ReviewMaterial is not — restated for the reader who skims

```text
ReviewMaterial  !=  AgentResult
ReviewMaterial  !=  EvidenceRecord
ReviewMaterial  !=  model output
ReviewMaterial  !=  a fact
ReviewMaterial  !=  Agent B's input
```

---

## 7. ReviewClaim

### 7.1 Shape — FROZEN

```yaml
ReviewClaim:
  claim_id:              "<opaque>"     # submitter-supplied, unique within its material
  statement:             "<bounded text, max 1024>"
  evidence_refs:         [ "<sha256:<64hex> | ref:<token>>", ... ]   # SET-semantic
  verification_targets:  [ VerificationTarget, ... ]                 # SET-semantic
  schema_version:        1

VerificationTarget:
  target_id:       "<opaque>"           # unique within its claim
  description:     "<bounded single-line text, max 256>"
  schema_version:  1
```

### 7.2 What a claim is — FROZEN

```text
A ReviewClaim is DECLARED ANALYSIS MATERIAL. It is a statement its submitter stands behind,
plus references the submitter declares, plus checks the submitter declares could be run.
```

```text
statement            !=  truth
evidence_refs        !=  verification
verification_targets !=  verified facts
```

```text
FROZEN: `statement` is bounded text. It is NOT a transcript, NOT a provider response, NOT a
        tool log, and nothing enforces that beyond the bound — AI-10 is not a content
        classifier, and §15 says plainly where the guarantee stops.
FROZEN: `evidence_refs` entries use AI-08's reference grammar, imported by identity:
        `sha256:<64 lowercase hex>` or `ref:<token>`. An evidence_ref is a DECLARED
        reference. AI-10 does not dereference it in v1, does not assert that the referenced
        thing exists, and does not treat it as evidence or as admission.
FROZEN: a `verification_target` is a DECLARED description of something that could be
        checked. It is AI-10's own descriptor type. It is NOT AI-04's TargetRef or
        TargetKind, NOT AI-06's operation, and it MUST NOT be converted into one by AI-10.
```

### 7.3 Fields that MUST NOT exist — FROZEN

```text
FORBIDDEN on ReviewClaim or anywhere in review/:
    confidence
    correctness
    probability
    winner
    score
    rank
    weight
    priority
    recommended_*
```

```text
FROZEN: each of these turns the review layer into a system that adjudicates. A review layer
        that can produce a winner has become the thing AI-00 §13 forbids.
```

### 7.4 Set semantics — FROZEN

```text
FROZEN: `claims` is a SET. Duplicate `claim_id` within one material is REJECTED.
FROZEN: `evidence_refs` is a SET. A duplicate element is REJECTED rather than deduplicated
        silently (the AI-05 §15.4 rule, applied here).
FROZEN: `verification_targets` is a SET keyed by `target_id`. A duplicate target_id is
        REJECTED.
FROZEN: array position is not semantic. Every projection that feeds a digest emits elements
        in a deterministic order (claims by claim_id; refs and targets sorted).
```

---

## 8. Independence relation

### 8.1 AI-08's I1–I8 are reused, not restated — FROZEN

```text
I1  identity separation            distinct registered AgentIds
I2  execution separation           distinct opaque ExecutionIds, neither derived
I3  input separation               neither Agent's result is the other's input
I4  context separation             each execution owns its own ContextResponse
I5  tool authorization separation  fresh GuardRequest + GuardDecision per Guard-bound call
I6  result separation              two results, neither carrying the other
I7  failure separation             no conversion of one outcome into the other's success
I8  provenance separation          each result names its own agent and execution
```

```text
FROZEN: AI-10 imports AI-08's `structural_independence` and its `IndependenceFinding`
        READ-ONLY. AI-10 does not modify agents/, does not extend the predicate, does not
        add a condition, and does not define a second independence vocabulary.
FROZEN: the finding is recorded VERBATIM: satisfied / violated condition labels, and nothing
        else. AI-10 MUST NOT add a correctness field, an agreement field or a verdict to it.
FROZEN: I1-I8 = structural independence. It is NOT correctness, NOT agreement, NOT
        verification, and NOT a review finding.
```

### 8.2 When independence may be observed — FROZEN

```text
`structural_independence` ranges over two ExecutionRecords (request + result + context).
ReviewMaterial supplies attribution fields, not ExecutionRecords.
```

```text
FROZEN: the INDEPENDENCE_OBSERVED state is reachable ONLY when the caller supplies BOTH
        ExecutionRecords and every declared attribution field agrees with them (§6.4).
FROZEN: when the records are not supplied, or do not agree, the case MUST NOT record an
        independence observation, MUST NOT fabricate an IndependenceFinding, and MUST NOT
        describe the case as independent or non-independent.
FROZEN: "independence was not observed" is NOT a violation and NOT a negative finding.
        It is the absence of an observation, and it is recorded as such.
FROZEN: even a fully satisfied finding says nothing about the two materials' provenance or
        quality. The finding is about the two EXECUTIONS, not about the material.
```

### 8.3 Cross-agent isolation — FROZEN

```text
ReviewMaterial from Agent A  MUST NOT become Agent B's execution input.
ReviewMaterial from Agent B  MUST NOT become Agent A's execution input.
```

```text
FROZEN: AI-10 MUST NOT modify `AgentExecutionRequest`, MUST NOT add a field to it, and MUST
        NOT route review material through an Agent execution.
FROZEN: AI-10's review mode is a review-case construct. It is NOT an Agent execution and it
        MUST NOT be recorded as one.
FROZEN: AI-08 §9.1.1 records that a future mode in which one Agent's result IS an input to
        another is a DIFFERENT execution mode, MUST NOT be described as blind independent
        execution, and MUST NOT be recorded as satisfying I3. That future mode is NOT this
        contract, is NOT v1, and requires its own contract and an AI-08 boundary review.
```

---

## 9. ReviewFinding

### 9.1 Shape — FROZEN

```yaml
ReviewFinding:
  finding_id:      "<opaque>"
  review_case_id:  "<review_case_id>"
  kind:            ReviewFindingKind
  subjects:        [ "<material_id>#<claim_id>" | "<material_id>", ... ]   # SET-semantic
  schema_version:  1
```

```text
FROZEN: a finding is an OBSERVATION over supplied material. It is NOT a verdict.
FROZEN: `subjects` labels what the observation is about. A subject is a label, not evidence,
        not proof, and not a reference to a fact.
FROZEN: findings are a SET. The same (kind, subjects) pair MUST NOT be recorded twice.
```

### 9.2 ReviewFindingKind — FROZEN, closed, exactly eight

```text
IDENTICAL_MATERIAL            the two materials' `claims_digest` are equal
MATERIAL_DIFFERENCE           the two materials' `claims_digest` differ
CLAIM_OVERLAP                 a claim content digest appears on BOTH sides
CLAIM_UNIQUE_TO_LEFT          a claim content digest appears on the LEFT side only
CLAIM_UNIQUE_TO_RIGHT         a claim content digest appears on the RIGHT side only
EVIDENCE_REFERENCE_DIFFERENCE for a claim STATEMENT declared on both sides, the two sides'
                              `evidence_refs` sets are not equal (§9.3.1)
VERIFICATION_REQUIRED         a claim on either side declares at least one
                              verification_target and has no VerificationObservation yet
UNRESOLVED                    the comparison could not be completed
```

```text
FROZEN: exactly these eight. A ninth is an amendment.
FROZEN: IDENTICAL_MATERIAL and MATERIAL_DIFFERENCE are mutually exclusive: exactly one of
        the two is recorded for a completed comparison.
```

### 9.3 Claim identity, for comparison — FROZEN

```text
FROZEN: two claims are "the same claim" for OVERLAP AND UNIQUENESS when their CLAIM CONTENT
        DIGESTS are equal. The claim content digest covers:
            schema_version, statement, sorted(evidence_refs), sorted(verification_targets)
        It EXCLUDES `claim_id`, because `claim_id` is a submitter-chosen identifier and not
        content (the AI-08 §9.1.1 rule that a digest is not an identity, applied in reverse:
        an identifier is not content).
FROZEN: structural identity of a declared claim is NOT agreement, NOT truth, and NOT
        correctness.
```

### 9.3.1 Two identities, and which rule uses which — FROZEN (Amendment 1)

```text
claim content digest        schema_version, statement, sorted(evidence_refs),
                            sorted(verification_targets)
                            excludes claim_id
    used by                 CLAIM_OVERLAP
                            CLAIM_UNIQUE_TO_LEFT
                            CLAIM_UNIQUE_TO_RIGHT
                            the claim-set comparison behind `claims_digest`, and therefore
                            IDENTICAL_MATERIAL and MATERIAL_DIFFERENCE

claim statement digest      schema_version, statement, sorted(verification_targets)
                            excludes claim_id AND evidence_refs
    used by                 EVIDENCE_REFERENCE_DIFFERENCE alone
```

```text
FROZEN: a claim's STATEMENT IDENTITY is what it says — the statement and the checks it
        declares — and not what it cites. Two claims that say the same thing and cite
        different references are statement-equivalent and content-different, and that is
        exactly the fact EVIDENCE_REFERENCE_DIFFERENCE exists to observe.
FROZEN: EVIDENCE_REFERENCE_DIFFERENCE compares the two sides' `evidence_refs` sets for a
        statement declared on both sides. Equal sets produce no observation; unequal sets
        produce one, naming every claim that carries the statement on either side.
FROZEN: the two identities are the only two. A third would be an amendment.
```

```text
RECORDED (Amendment 1): as originally frozen, §9.3 defined one identity — the content
        digest, which covers `evidence_refs` — and §9.2 asked
        EVIDENCE_REFERENCE_DIFFERENCE to fire for a content digest present on both sides
        whose `evidence_refs` differ. Those two cannot both hold: claims whose references
        differ do not share a content digest, and claims that share one have equal
        references by construction. The member was unreachable. Amendment 1 records the
        problem and fixes it here rather than leaving an implementation to choose.
```

### 9.4 What each finding does NOT mean — FROZEN

```text
MATERIAL_DIFFERENCE          is NOT disagreement
CLAIM_OVERLAP                is NOT agreement
CLAIM_UNIQUE_TO_LEFT         is NOT "left is correct"
CLAIM_UNIQUE_TO_RIGHT        is NOT "right is correct"
EVIDENCE_REFERENCE_DIFFERENCE is NOT "one side's evidence is wrong or incomplete"
VERIFICATION_REQUIRED        is NOT "the claim is false"
IDENTICAL_MATERIAL           is NOT confirmation
UNRESOLVED                   is NOT a PASS, and NOT a failure
```

### 9.5 Forbidden vocabulary — FROZEN

```text
FORBIDDEN as a finding kind, a state, a field or a reason code anywhere in review/:
    PASS
    FAIL
    CORRECT
    INCORRECT
    VERIFIED
    WINNER
    BEST_AGENT
    HIGHER_CONFIDENCE
```

```text
FROZEN: AI-10 derives findings. AI-10 MUST NOT derive any other kind, MUST NOT rank
        findings, and MUST NOT convert a finding into a decision.
```

---

## 10. VerificationRequest and VerificationObservation

### 10.1 Why these are two types — FROZEN

```text
ASKING for a verification and OBSERVING one are different acts with different producers.
Merging them would record "a check was requested" and "a check ran" as the same fact, which
is the conflation AI-08 §12.2 refuses for authorization and AI-06 §8 refuses for execution.
```

### 10.2 VerificationRequest — FROZEN

```yaml
VerificationRequest:
  verification_id:  "<opaque>"
  review_case_id:   "<review_case_id>"
  subject:          "<material_id>#<claim_id>"
  targets:          [ VerificationTarget, ... ]   # the declared targets this request asks about
  requested_at:     "<timestamp>"
  schema_version:   1
```

```text
FROZEN: a VerificationRequest carries NO permission level, NO actor, NO tool id, NO
        operation, NO command and NO credential.
FROZEN: AI-10 MUST NOT infer a permission level from a claim, from an AgentId, from a
        ReviewFinding, from a source_status or from anything else. It has none to give.
FROZEN: a VerificationRequest is a REQUEST. It authorizes nothing and executes nothing.
```

### 10.3 VerificationObservation — FROZEN

```yaml
VerificationObservation:
  verification_id:    "<verification_id>"     # the request this observes
  review_case_id:     "<review_case_id>"
  subject:            "<material_id>#<claim_id>"
  outcome:            ToolOutcome             # AI-06's, imported by identity
  reason_code:        "<AI-06's reason code>"
  tool_id:            "<AI-06's spelling>"
  tool_version:       "<AI-06's spelling>"
  operation:          "<AI-06's spelling>"
  guard_decision_id:  "<id | empty>"
  guard_reason_code:  "<code | empty>"
  duration_ms:        <int | null>
  observed_at:        "<timestamp>"
  schema_version:     1
```

```text
FROZEN: an observation is a PROJECTION of an AI-06 execution. It carries no stdout, no
        stderr, no arguments, no environment and no target detail beyond AI-06's own
        spelling. AI-06's `ToolResult` remains the execution fact and is not absorbed
        (the AI-08 §10 rule that a result references other results rather than absorbing them).
FROZEN: at most one observation per request.
FROZEN: an empty `guard_decision_id` means NO EVALUATION HAPPENED — AI-06 refused the
        request before the Guard boundary. It MUST NOT be recorded as BLOCKED, as UNKNOWN,
        or as an authorization decision (AI-08 Amendment 3, §12.2).
FROZEN: an observation is an execution fact about a check. `ToolOutcome.COMPLETED` is NOT
        "the claim is true", NOT "the claim is verified", and NOT a PASS.
```

### 10.4 Status of an unanswered request — FROZEN

```text
FROZEN: a VerificationRequest with no observation is a legitimate terminal fact. The case
        MAY close with it outstanding, and the outstanding request MUST be visible rather
        than silently dropped.
FROZEN: a refused, blocked or failed verification NEVER converts into a satisfied one, and
        never converts into a finding about the claim.
```

---

## 11. AI-06 / Guard boundary

### 11.1 The path — FROZEN

```text
Review
    |
    v
VerificationRequest
    |
    v
controlled verification caller        <- composes the ToolRequest: actor, permission_level,
    |                                    target, timeout. AI-10 composes none of these.
    v
AI-06 Security Tools  (public invocation API)
    |
    v
AI-04 Guard           (one fresh evaluation)
    |
    v
tool adapter
    |
    v
ToolResult            -> reported back as a VerificationObservation
```

### 11.2 Why the invocation is performed by the controlled caller — FROZEN

```text
AI-06's public invocation API requires an `evaluator` (AI-04's `evaluate`) and a policy.
AI-10 MUST NOT import AI-04 in any form (§16). It therefore cannot supply the evaluator, and
it cannot be the caller of record for an authorization.
```

```text
FROZEN: AI-10 issues VerificationRequests. The controlled verification caller performs the
        invocation and reports the observation. AI-10 records the observation; it does not
        produce it, and it MUST NOT fabricate one.
FROZEN: AI-10 does not hold authorization authority, does not select a policy, and does not
        evaluate one.
```

### 11.3 Prohibitions — FROZEN

```text
AI-10 MUST NOT:
    import tools/ or call any tools.* adapter directly
    import plugins.guard, call Guard.evaluate(), or alias it
    invent, synthesize or reconstruct a GuardDecision
    reuse, cache, widen or pre-authorize any GuardDecision
    build a second ToolRequest path, a second registry or a second dispatch
    execute a subprocess of its own
    announce a verification that did not run
```

### 11.4 The invariant the caller must keep — FROZEN

```text
one verification invocation
    -> one ToolRequest
    -> one fresh GuardRequest
    -> one fresh GuardDecision   (when the Guard boundary is reached)
    -> one ToolResult
```

```text
FROZEN: one ALLOW authorizes one invocation. A second verification asks again. Nothing is
        cached, reused or widened (AI-06 §9.1, AI-08 §12).
FROZEN: a request AI-06 refuses before Guard has NO GuardDecision, and that absence is
        recorded truthfully as an empty decision id.
FROZEN: AI-10 verifies through AI-06's single executable path or it does not verify at all.
```

---

## 12. HumanDecision

### 12.1 Shape — FROZEN

```yaml
HumanDecision:
  decision_id:      "<opaque>"
  review_case_id:   "<review_case_id>"
  actor_id:         "<bounded identifier of a human>"
  decision:         HumanDecisionKind
  rationale:        "<bounded text, max 512>"
  recorded_at:      "<timestamp>"
  schema_version:   1
```

### 12.2 HumanDecisionKind — FROZEN, closed, exactly three

```text
ACCEPTED    the human accepted the review case's material as a basis for the human's own
            next act. NOT a truth verdict, NOT a PASS, NOT VERIFIED, NOT a correctness claim.
REJECTED    the human rejected it. NOT a statement that any claim is false.
DEFERRED    the human declined to accept or reject now. The case remains OPEN;
            a DEFERRED decision does not advance the case to CLOSED.
```

```text
FROZEN: exactly these three members. A fourth is an amendment.
FROZEN: none of them means PASS, VERIFIED, CORRECT or "the winner".
```

### 12.3 What a HumanDecision must be — FROZEN

```text
MUST be supplied by a human caller, explicitly.
MUST be recorded as an act, with its rationale and its time.
MUST be attributable to a human actor identifier.
```

```text
MUST NOT be:
    model-generated
    generated or pre-filled by AI-10
    derived from a ReviewFinding
    derived from a majority vote
    derived from a confidence threshold
    auto-selected, defaulted or recommended
```

```text
FROZEN: there is no `recommended_*` field, no default decision, and no path in review/ that
        produces a decision value without a human supplying it.
FROZEN: `actor_id` is a bounded identifier DECLARED by the caller. It is NOT an AgentId,
        NOT a model identity, and NOT authenticated in v1. There is no human identity
        registry in this repository, and v1 does not invent one.
FROZEN: `rationale` is bounded and is not a transcript.
```

### 12.4 Storage status — FROZEN

```text
HumanDecision = run data in v1.
AI-05 durable recording of a human decision = DEFERRED (§13).
```

---

## 13. Evidence boundary

### 13.1 Ownership — FROZEN

```text
ReviewMaterial       AI-10   review input
ReviewFinding        AI-10   comparison observation
ReviewCase           AI-10   review lifecycle value
VerificationRequest  AI-10   a request for a verification act
HumanDecision        AI-10   a human's decision act
VerificationObservation AI-10  a projection of an AI-06 execution
ToolResult           AI-06   the execution fact
IndependenceFinding  AI-08   structural independence over an execution pair
AgentResult          AI-08   one execution's terminal run result
EvidenceRecord       AI-05   the durable admitted record
```

```text
FROZEN: AI-10 creates no second EvidenceStore, no second record schema, no second admission
        pipeline and no second producer vocabulary.
```

### 13.2 AI-10 writes no EvidenceRecord in v1 — FROZEN

```text
FROZEN: AI-10 MUST NOT write an AI-05 EvidenceRecord, under any producer token.
FROZEN: AI-10 MUST NOT write under "ai-04" or "ai-06". Those tokens name the component that
        WROTE the record; AI-10 is not AI-04 and is not AI-06, and writing under either would
        be a false producer claim — the class of claim this repository refuses everywhere
        (AI-08 §13.1, AI-09 §19.3.1).
FROZEN: AI-10 MUST NOT invent a producer token. The §6.5 registry admits exactly six events
        today, none of them AI-10's, and adding one is an AI-05 amendment made by AI-05.
```

### 13.3 What may become durable today — FROZEN

```text
The verification half of a review can already be recorded durably ONLY when an admissible
producer actually performs the act — for example an AI-06 tool execution, recorded by AI-06
under AI-06's token. That record is AI-06's, describes AI-06's act, and is not a review
record. AI-10 must not be described as its producer.
```

```text
FROZEN: AI-10 review result != AI-05 EvidenceRecord.
FROZEN: no document produced by AI-10 may read an ACCEPTED from admit() or admit_to_store()
        as a full §30 admission. AI-05 C-1 remains DEFERRED, so §30 step 7 is unimplemented.
```

### 13.4 Future dependencies — FROZEN as recorded, not resolved here

```text
A.  automatic acquisition of CODEX review material
        -> likely requires an AI-09 contract amendment (its output/reference boundary, §19)
           plus a reviewed seam design. NOT AI-10's to make.

B.  automatic acquisition of / bridging to DSH review material
        -> requires a separately reviewed DSH integration seam. AI-08 v1 explicitly leaves
           DSH integration out of scope, and DSH is an external platform (AI-01).

C.  durable AI-10 decision / review evidence
        -> requires an AI-05 amendment: a producer token and an admitted event. AI-05 owns
           its registry and its amendment rule.

D.  a durable model-output store of any kind
        -> a separate contract with its own retention, redaction and admission questions
           (AI-09 §19.3 says exactly this about its own scope).
```

```text
FROZEN: AI-10-A does not modify AI-05, AI-08 or AI-09 to obtain any of A-D, and no part of
        AI-10 may assume they have been obtained.
```

---

## 14. Lifecycle

### 14.1 The frozen lifecycle

```text
CREATE
  -> MATERIALS_SUPPLIED
  -> INDEPENDENCE_OBSERVED        (optional; only when §8.2 holds)
  -> COMPARISON_RECORDED
  -> VERIFICATION_REQUESTED       (optional)
  -> VERIFICATION_OBSERVED        (optional)
  -> HUMAN_DECISION_RECORDED
  -> CLOSED
```

```text
Terminal alternatives, reachable from any non-terminal state by an explicit closure:
    UNRESOLVED
    BLOCKED
    NOT_RUN
```

### 14.2 Status discipline — FROZEN

```text
NOT_RUN   !=  PASS
BLOCKED   !=  PASS
UNKNOWN   !=  VERIFIED
UNRESOLVED != PASS, and is NOT a failure
```

```text
FROZEN: no path in review/ converts a non-success into a success, and none converts an
        absence of a result into a result (the AI-04 §21 and AI-08 §7.1.1 rules, applied here).
FROZEN: a case that ends UNRESOLVED, BLOCKED or NOT_RUN is a complete, honest outcome, not
        an incomplete review to be forced to a conclusion.
```

### 14.3 What a case may never be forced to do — FROZEN

```text
MUST NOT be forced to produce a verification.
MUST NOT be forced to produce a decision.
MUST NOT be forced to produce a finding beyond those the material supports.
MUST NOT be closed as CLOSED without an ACCEPTED or REJECTED human decision.
```

---

## 15. Security and secrecy boundary

### 15.1 Ingress rules — FROZEN

```text
FROZEN: every ReviewMaterial field is bounded (§6.2). There is no unbounded field, no blob
        field, and no free-form container.
FROZEN: ReviewMaterial MUST NOT carry a credential, a token, a key, an environment mapping,
        a raw provider response, a raw prompt, a tool argument or a command.
FROZEN: `statement`, `rationale` and `description` are bounded text fields. They admit prose,
        and prose is where a secret reaches a system that does not scan for one.
```

### 15.2 Where that guarantee stops — FROZEN

```text
FROZEN: AI-10 is NOT a content classifier. A secret typed into a bounded `statement` is not
        detected by AI-10. The AI-08 §10.2 precedent applies verbatim: a structural shape
        guarantee is not a content scanner, and saying so is more honest than implying
        otherwise. The enforceable half of this boundary is that AI-10 persists nothing and
        egresses nothing (§15.3), so material content has nowhere to go.
```

### 15.3 Egress rules — FROZEN

```text
ReviewMaterial MUST NOT reach:
    an Agent execution input           (§8.3)
    a provider or any network          (review/ has no network path at all)
    a durable store, file, archive or database
    a log line, a trace or an error message
    another review case, automatically
```

```text
FROZEN: AI-10 has no network call, no subprocess, no credential access and no filesystem
        write. A review layer that can transmit material is an exfiltration path, and v1
        does not create one.
```

### 15.4 The principles this section enforces

```text
Evidence > model judgment
execution evidence > narrative agreement
NOT_RUN   != PASS
BLOCKED   != PASS
UNKNOWN   != VERIFIED
agreement != truth
independence != correctness
material difference != disagreement
ReviewFinding != Verdict
HumanDecision != ModelDecision
AgentResult != ReviewMaterial
sha256 / ref != artifact locator
```

---

## 16. Dependency direction — FROZEN

```text
review/  ->  agents/                 ALLOWED   read-only: AgentId, resolve_agent,
                                               ExecutionRecord, AgentResult,
                                               IndependenceFinding, structural_independence
review/  ->  plugins/security_tools  ALLOWED   its public vocabulary, and its public
                                               invocation entry point where the composition
                                               root injects one. The invocation act itself
                                               belongs to the controlled verification caller
                                               (§11.2): review/ never composes a ToolRequest,
                                               never supplies an evaluator, a policy or a
                                               registry, and never imports a module below the
                                               package surface
review/  ->  plugins/context         ALLOWED   read-only, when a workspace identity is needed

review/  ->  providers/              FORBIDDEN
review/  ->  routing/                FORBIDDEN
review/  ->  plugins/guard           FORBIDDEN (in any form: import, call, alias)
review/  ->  tools/                  FORBIDDEN
review/  ->  plugins/evidence        FORBIDDEN

agents/       -/->  review/          FORBIDDEN  (one-way)
providers/    -/->  review/          FORBIDDEN  (one-way)
routing/      -/->  review/          FORBIDDEN  (one-way)
integrations/ -/->  review/          FORBIDDEN  (one-way)
```

```text
FROZEN: review/ depends on the layers it reads; none of them depends on review/.
FROZEN: the dependency runs INTO review/, never out of it.
FROZEN: if AI-10 ever needs provider data, that dependency is redesigned and reviewed —
        it is not added quietly.
```

### 16.1 Why each forbidden edge is forbidden

```text
providers/  review must not reach a provider. A review layer with a model path can generate
            or evaluate content, which is the adjudication this contract forbids.
routing/    AI-07 selects; review does not route, and the Router does not execute. Reading
            a RouterDecision would invite "the Router chose it, so it wins".
plugins/guard  Guard authorizes. Review asks; AI-06 asks Guard. A second path to Guard is a
            second authorization surface, and AI-10 has no authorization authority (§11).
tools/      adapters execute. They are reachable only through AI-06's registry and dispatch,
            under Guard. A direct import is an unguarded execution path.
plugins/evidence  AI-05 admits durable records. Review writes none (§13.2).
```

---

## 17. Repository layout — FROZEN

```text
review/                      AI-10's home. A CORE layer, reached as a namespace package
                             relative to the repository root, exactly as routing/, agents/
                             and integrations/ are.
review/**                    AI-10-B decides the module split.
tests/review/                AI-10-B.
docs/AI-10_CROSS_AGENT_REVIEW_EXECUTION_PLAN.md   this document.
```

```text
FROZEN: AI-10's home is review/.
FROZEN: review/ is a CORE layer and NOT a plugin layer.
FROZEN: review/__init__.py MUST NOT exist (the routing/, agents/ and integrations/ rule).
FROZEN: plugins/review/, agents/review/, routing/review/ and integrations/review/ MUST NOT
        exist. plugins/ holds exactly four layers, owned by AI-03, AI-04, AI-05 and AI-06.
FROZEN: AI-10-A creates none of this. AI-10-A writes this document and nothing else.
```

---

## 18. Layer 0 — FROZEN

AI-10-B MUST add `check_ai10_review_layer()` to `scripts/ci/layer0_policy.py`, following the
precedent of AI-05, AI-06, AI-07, AI-08 and AI-09. The check MUST cover:

```text
identity
    review/ exists
    review/ is a core layer: no review/__init__.py
    no plugins/review, agents/review, routing/review, integrations/review

imports
    review/ imports nothing from providers/, routing/, plugins.guard, tools/,
      plugins.evidence
    review/ imports no network client (socket, http, urllib, urllib3, requests, httpx,
      aiohttp, ftplib, smtplib, telnetlib, ssl, asyncio)
    review/ imports no process or filesystem module (subprocess, shutil, multiprocessing,
      os, pathlib, io, tempfile, sqlite3)
    review/ names no credential symbol (CredentialRef, SecretValue, environ, getenv,
      api_key, token)
    review/ binds no `evaluator`, `policy` or `registry`, composes no ToolRequest, and calls
      no function named `evaluate`
    review/ calls no forbidden builtin (eval, exec, compile, __import__)
    review/ defines no class ending in Adapter or Transport

one-way
    agents/, providers/, routing/ and integrations/ do not import review/

behavioural
    the frozen vocabularies are present and closed: ReviewCaseState has eleven members,
      ReviewFindingKind has exactly the eight members of §9.2, HumanDecisionKind has
      exactly the three members of §12.2
    no forbidden verdict token appears as an identifier or a literal in review/
      (PASS, FAIL, CORRECT, VERIFIED, WINNER, BEST_AGENT, HIGHER_CONFIDENCE)
    ReviewMaterial has no unbounded field and no forbidden field (§7.3)
    no module in review/ opens a file for writing
```

```text
FROZEN: the check MUST be non-vacuous. A check that passes because there is nothing to
        check is not a check (the AI-08 §17 rule).
FROZEN: AI-10 MUST NOT modify AI-04, AI-06, AI-07, AI-08 or AI-09 Layer 0 rules. AI-10 adds
        its own check and registers it; it changes nothing that belongs to another phase.
```

---

## 19. Test model

### 19.1 Shape

```text
OFFLINE ONLY. No network, no credential, no provider call, no live layer.
Layers 1-3, marked per pytest.ini, exactly as every other phase's tests are.
The AI-10 suite lives under tests/review/ and is added by AI-10-B.
```

### 19.2 Test matrix — FROZEN

```text
T1   material shape         a caller-supplied digest is REFUSED
T2   material shape         an unbounded field cannot be constructed
T3   material identity      an unregistered agent_id is REFUSED
T4   material ingress       construction is explicit; no capture API exists
T5   claim bounds           over-long statement / too many claims are REFUSED
T6   set semantics          duplicate claim_id, duplicate evidence_ref, duplicate
                            target_id are each REJECTED
T7   digest determinism     two conforming implementations agree on claims_digest and
                            material_digest for the same value
T8   digest scope           claim_id and material_id do not move the digest; statement,
                            refs and targets do
T9   comparison             equal claims_digest yields IDENTICAL_MATERIAL and never
                            MATERIAL_DIFFERENCE
T10  comparison             unequal claims_digest yields MATERIAL_DIFFERENCE and never
                            IDENTICAL_MATERIAL
T11  comparison             CLAIM_OVERLAP / CLAIM_UNIQUE_TO_LEFT / CLAIM_UNIQUE_TO_RIGHT
                            fire exactly on the constructed cases
T12  comparison             EVIDENCE_REFERENCE_DIFFERENCE fires only on a claim STATEMENT
                            declared on both sides whose ref sets differ (§9.3.1)
T13  finding vocabulary     no finding value outside the eight exists
T14  no verdict             no PASS / VERIFIED / CORRECT / WINNER / BEST_AGENT token is
                            producible by any review/ module
T15  independence reuse     AI-10 does not define a second independence vocabulary and does
                            not extend IndependenceFinding
T16  independence absence   a case without ExecutionRecords records no finding and no
                            negative finding
T17  independence refuse    a declared field disagreeing with a supplied ExecutionRecord is
                            REFUSED
T18  isolation              no path constructs an AgentExecutionRequest carrying material
T19  verification request   a request carries no permission level, actor, tool id, operation
                            or command
T20  verification observe   a pre-Guard refusal is recorded with an empty decision id and is
                            not recorded as BLOCKED or UNKNOWN
T21  verification path      review/ does not import tools/, plugins.guard or providers/
T22  verification honesty   no observation exists without a performed invocation; a
                            fabricated observation is not constructible
T23  human decision         a decision cannot be constructed without being supplied; no
                            default or recommended value exists
T24  human decision         DEFERRED does not close a case; CLOSED requires ACCEPTED or
                            REJECTED
T25  lifecycle              only the legal transitions of §5.3 are accepted; no backward
                            transition exists
T26  lifecycle              a case closes UNRESOLVED / BLOCKED / NOT_RUN without a decision
                            and without a forced verification
T27  secrecy                material content appears in no log, no file and no written
                            artifact (asserted, not assumed)
T28  Layer 0                check_ai10_review_layer() fails when each prohibited import is
                            injected, and passes on the real tree
```

```text
FROZEN: T28 is the meta-test — every Layer 0 assertion is proven by injecting the violation
        it claims to catch, so the gate is verified rather than trusted.
FROZEN: no test may fabricate a captured Agent output, a GuardDecision, a ToolResult or a
        provider response to make a path look complete.
```

---

## 20. Relations to the other phases

```text
AI-00   architecture freeze       consumed; §13 (cross-agent review) is the requirement
AI-01   DSH baseline              not modified; DSH remains an external platform
AI-02   provider / model layer    not reached; review/ has no provider edge (§16)
AI-03   Context plugin            read-only (workspace identity)
AI-04   Guard plugin              not modified; not imported by review/. Guard authorizes
                                  verification through AI-06 (§11)
AI-05   Evidence plugin           not modified; AI-10 writes no EvidenceRecord (§13)
AI-06   Security tools plugin     the executable verification path, through its public
                                  invocation API (§11)
AI-07   Model Router              not modified; not imported by review/. No execution
                                  coupling; agent_hint stays a hint
AI-08   agents/                   consumed read-only: AgentId, resolve_agent,
                                  ExecutionRecord, AgentResult, IndependenceFinding,
                                  structural_independence. Not modified
AI-09   integrations/             not modified; not imported. No provider call, no raw
                                  output, no artifact behind a reference
AI-11   benchmark                 consumes review data later; not in v1
AI-12   routing v2                not this contract
AI-13   long-running workflows    owns resume/retry/cancellation; review cases do not
                                  resume in v1
AI-14   long-term workbench       the multi-Agent end state
```

---

## 21. Non-goals — FROZEN

```text
AI-08 contract modification
AI-09 contract modification
AI-05 contract modification
DSH integration
provider output retention
a durable model-output store
Router integration
AI-11 benchmark
AI-12 routing fallback / escalation
AI-13 retry / resume / timeout / cancellation
SecurityLab integration, in any form
live provider verification
capability promotion
a majority vote
a confidence threshold
a ranking or a winner
automatic second-opinion loops
automatic cross-agent result injection
```

```text
FROZEN: any of these that turns out to be an implementation prerequisite is recorded as
        PREREQUISITE / BLOCKED (§13.4) and left alone. It is not implemented quietly.
```

---

## 22. What a reader must not infer

```text
Do not infer a model-output store.        There is none.
Do not infer automatic capture.           v1 ingress is explicit submission only (§6.3).
Do not infer content behind a digest.     `sha256:` locates nothing; `ref:` resolves nothing.
Do not infer that the materials are real
    Agent output.                          They are DECLARED material (§6.4).
Do not infer that independence validates
    a material.                            It is about the two executions, not the material.
Do not infer agreement from a finding.    No finding means agreement (§9.4).
Do not infer a verdict from a finding.    A finding is an observation, never a verdict.
Do not infer that verification passed.    An observation is a tool execution fact, not a
                                           truth about the claim.
Do not infer a winner from a decision.    A human decision is an act, not a truth claim.
Do not infer that COMPLETED means PASS.   It does not; that rule stands.
Do not infer that a human decision is
    durable.                               It is run data; AI-05 admission is DEFERRED.
Do not infer that AI-10 can acquire
    what AI-08 and AI-09 deliberately do
    not expose.                            That requires the amendments of §13.4.
```

---

## 23. Open questions

```text
Q-1  the concrete submission channel for ReviewMaterial in v1 (API-level, or a bounded
     local CLI). Whatever it is, it MUST NOT create a durable store, an archive or a log
     of material content. Default: API-level, in memory.
Q-2  whether human-authored (non-Agent) material is ever representable. v1: NOT
     representable — material is attributed to a registered AgentId and an execution.
Q-3  whether a case may ever compare more than two sides, or two executions of one Agent.
     v1: NO. Both are out of scope (§4.2).
Q-4  the exact Python surface of the state machine (transition API, constructor shapes).
     AI-10-B's, within §5.3.
Q-5  the mapping from VerificationTarget to a concrete ToolRequest, and where it lives.
     It belongs to the controlled verification caller / composition boundary. AI-04 Q-1
     (policy discovery) remains open and is not resolved here.
Q-6  the retention policy of a future durable review record — an AI-05 question, if C
     (§13.4) is ever undertaken.
Q-7  whether a review case may outlive a process. AI-13 owns resume; v1 says no.
```

---

## 24. Amendment rule

```text
FROZEN: AI-10-B MUST NOT deviate from this document without amending it first.
```

An amendment is REQUIRED for any change to:

```text
the review definition (§4), or the two-side / distinct-AgentId rule
ReviewCase, its state vocabulary or its transitions (§5)
ReviewMaterial — its fields, its bounds, its ingress boundary or its lifetime (§6)
ReviewClaim — its fields or its forbidden fields (§7)
the independence relation, or the reuse of AI-08's predicate (§8)
ReviewFindingKind, the derivation rules or the forbidden vocabulary (§9)
VerificationRequest / VerificationObservation (§10)
the AI-06 / Guard boundary (§11)
HumanDecision or its vocabulary (§12)
the Evidence boundary (§13)
the security and secrecy boundary (§15)
the dependency direction (§16)
the repository layout (§17)
the Layer 0 requirements (§18)
the test model (§19)
any non-goal (§21)
```

```text
FROZEN: AI-10 owns this document. It does NOT own AI-05, AI-08 or AI-09. An amendment to
        one of those is made by that phase, under that phase's amendment rule, before any
        AI-10 work depends on it (§13.4).
```

An amendment records: what changed, why, its security and authority impact, and the date. It is
committed before the code that depends on it. Applied amendments are recorded in §26.

---

## 25. Freeze record

```text
Phase            AI-10 — Cross-Agent Review
Sub-phase        AI-10-A — Contract / Execution Plan / Freeze
Status           FROZEN
Date             2026-10-02
Base             main @ 2e55b5a1e0c13d559ceb08fd5ca8094410634f11
Contract         docs/AI-10_CROSS_AGENT_REVIEW_EXECUTION_PLAN.md
Amendments       1   Amendment 1 — the identity EVIDENCE_REFERENCE_DIFFERENCE is
                       evaluated over (§9.2, §9.3.1, §19 T12; log at §26)
```

```text
AI-08 contract blob   a01e03f5306299a0a4442648eeb8fdcfce6bd8dd   UNCHANGED by AI-10-A
AI-09 contract blob   e9728b184740074e5c8f718db6b45f859c3802bf   UNCHANGED by AI-10-A
AI-07 contract blob   2f8dcba8f9c2ca36e3d917fc6b69c3a5cb7f36fe   UNCHANGED by AI-10-A
AI-06 contract blob   4b05155c9bd7ed2d7e25f7e23a0471de82a880f8   UNCHANGED by AI-10-A
AI-05 contract blob   dd062148938f902109b49a496bb6051c3331a349   UNCHANGED by AI-10-A
AI-04 contract        docs/AI-04_GUARD_EXECUTION_PLAN.md         UNCHANGED by AI-10-A
AI-03 contract        docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md  UNCHANGED by AI-10-A
AI-02 contract        docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md   UNCHANGED by AI-10-A
```

```text
FROZEN here
    the core-service identity, and that review/ is not a plugin
    the review definition: two explicitly supplied materials, distinct AgentIds, two sides
    ReviewCase and its eleven-state lifecycle
    ReviewMaterial and EXTERNAL REVIEW MATERIAL INGRESS — the only v1 input boundary
    declared provenance, and that it is never verified provenance
    ReviewClaim, its bounds, its set semantics, and its forbidden fields
    the reuse of AI-08's I1-I8 read-only, and that independence is not correctness
    ReviewFinding — exactly eight structural observations, and what none of them means
    VerificationRequest / VerificationObservation, and the controlled-caller invocation path
    the AI-06 / Guard boundary, and that AI-10 holds no authorization authority
    HumanDecision — human-supplied, three members, never model-generated
    the Evidence boundary: AI-10 writes no EvidenceRecord in v1
    the security and secrecy boundary, and where its guarantee stops
    the dependency direction, the repository layout, the Layer 0 requirements and the
    test model

BLOCKED / PREREQUISITE here
    automatic acquisition of real Agent analysis material (§13.4 A, B)

DEFERRED here
    durable recording of a review or a human decision (an AI-05 amendment, §13.4 C)
    a durable model-output store (its own contract, §13.4 D)

OPEN here
    Q-1 .. Q-7 (§23)

NOT DECIDED here
    any implementation detail of review/ — AI-10-B's, within this contract
```

**AI-10-A freezes a contract. No `review/` layer exists, no review type exists, no verification
has been requested, and no provider call has been made by this phase.**

---

## 26. Amendment log

### Amendment 1 — 2026-10-02 — the identity EVIDENCE_REFERENCE_DIFFERENCE is evaluated over

**What changed.**

```text
§9.2   the EVIDENCE_REFERENCE_DIFFERENCE row now reads: "for a claim STATEMENT
       declared on both sides, the two sides' `evidence_refs` sets are not equal"

§9.3   the content digest is now stated as the identity for OVERLAP AND UNIQUENESS,
       rather than as the identity for comparison in general

§9.3.1 NEW. It names the two identities and which rule uses each:
           claim content digest       statement + evidence_refs + targets
                                      -> CLAIM_OVERLAP, CLAIM_UNIQUE_TO_LEFT,
                                         CLAIM_UNIQUE_TO_RIGHT, and the claim-set
                                         comparison behind IDENTICAL_MATERIAL and
                                         MATERIAL_DIFFERENCE
           claim statement digest     statement + targets, and NOT evidence_refs
                                      -> EVIDENCE_REFERENCE_DIFFERENCE alone

§19    T12 is restated against the statement identity
§25    the freeze record records this amendment
```

**Why.**

As frozen, the rule could not fire, and the reason is arithmetic rather than
editorial. §9.3 defined the claim content digest as covering `evidence_refs`; §9.2
asked EVIDENCE_REFERENCE_DIFFERENCE to fire for a claim content digest present on
both sides whose `evidence_refs` sets are not equal. Two claims whose references
differ do not share a content digest, and two claims that share one have equal
references by construction. The member was therefore unreachable — and a closed
vocabulary with an unreachable member is not the vocabulary the contract says it
is.

The contradiction was found by AI-10-B's implementation, which recorded it in
`review/claim.py`, did not change this contract, and reported it. This amendment
is the contract's own answer.

**What did NOT change.**

```text
the eight-member ReviewFindingKind vocabulary — no member added, removed or renamed
CLAIM_OVERLAP, CLAIM_UNIQUE_TO_LEFT and CLAIM_UNIQUE_TO_RIGHT keep the content digest
`claims_digest` and `material_digest` keep their inputs; a material's digest values
    are unchanged by this amendment
the four forbidden-verdict rules and every other §9.4 statement
no ranking, no winner, no confidence, no correctness, no score, no probability
the dependency direction (§16), the lifecycle (§5.3), the ingress boundary (§6.3),
    the Evidence boundary (§13) and every non-goal (§21)
```

**Security and authority impact: none.**

```text
The amendment changes WHEN one observation fires. It grants no authority, opens no
dependency, adds no field, stores nothing, and reaches no layer AI-10 could not
already reach. It makes a frozen member reachable rather than adding a capability.

It does not weaken a boundary: EVIDENCE_REFERENCE_DIFFERENCE remains an
observation about DECLARED references. It is not a statement that either side's
references are wrong, incomplete or better (§9.4), and it is not a verdict.
```

```text
Applied   2026-10-02
Owner     AI-10
Effect    the contract AI-10-B is built against. The implementation correction that
          follows replaces AI-10-B's recorded workaround with this semantics; the
          workaround was never the frozen meaning.
```
