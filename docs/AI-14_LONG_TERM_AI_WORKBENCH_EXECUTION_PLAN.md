# AI-14 — Long-term AI Workbench — Execution Plan

> Status: **DRAFT — FREEZE PROPOSAL** (AI-14-A, 2026-10-04)
> Phase: AI-14 — Long-term AI Workbench
> Sub-phase: **AI-14-A — Final Architecture / Long-term Workbench Freeze**
> Prerequisite: AI-13 — COMPLETE / MERGED / CLOSED, merge commit
> `98d4f57ad0bd78a54b9eb2ea44f30d2db394ee97` (PR #71)
> Base: `main` @ `98d4f57ad0bd78a54b9eb2ea44f30d2db394ee97`
> Rule: This document defines the contract. AI-14-B implements against it. Nothing in AI-14
> may deviate from a frozen contract without amending this document first (§24).

```text
THIS DOCUMENT IS NOT YET FROZEN.

The freeze act is human review followed by the merge of this PR. Until that merge this is
a proposal, and C0 (§22) is NOT satisfied by this document's existence — it is satisfied
by its merge.

AI-14-A writes NO runtime implementation and changes NO runtime behaviour. It corrects the
project's status record, inventories what the repository actually contains, and freezes the
architecture the later sub-phases implement against.
```

---

## 0. The one idea — read this first

```text
independently frozen capabilities
  + an explicit composition that adds no authority
  + one document that says which of them are CONNECTED and which are only SEAMS
  =  a workbench that can keep growing without any layer swallowing another
```

Everything below is a consequence of one refusal:

```text
FROZEN: COMPOSITION MUST NOT TRANSFER AUTHORITY. Connecting two layers MUST NOT give
        either one a power it did not already hold on its own. Every capability keeps
        the authority it was frozen with, and the composition's authority is exactly
        the union of its parts — never more.
```

```text
FROZEN: Evidence > model judgment.
FROZEN: NOT_RUN, BLOCKED, UNKNOWN and UNAVAILABLE are NOT PASS. No composition, wiring,
        aggregation, dashboard or default in AI-14 may turn one of them into a PASS, a
        grant, an availability claim or a completed phase.
FROZEN: a capability that exists but is not connected is recorded as NOT CONNECTED. AI-14
        MUST NOT describe a seam as a working path, and MUST NOT close a gap by wiring it
        silently (§5, Appendix A).
```

---

## 1. Purpose

AI-14 is the **final architecture freeze** of the Workbench: the phase in which the layers
built by AI-00 … AI-13 are composed into one explainable system, and in which the project
states — once, and on evidence — what that system is.

It is **not** a new capability. Everything AI-14 composes already exists, frozen by its own
contract:

```text
AI-00   the architecture and the repository baseline
AI-02   the model / provider layer, and the model registry
AI-03   the Context plugin
AI-04   the Guard plugin
AI-05   the Evidence / Audit plugin — INCOMPLETE (C-1 DEFERRED)
AI-06   the security research tools, the tool gateway and the adapter layer
AI-07   the Router (v1)
AI-08   the agent runtime — the execution identity a step runs under
AI-09   the Codex provider integration
AI-10   the cross-agent review layer
AI-11   the security benchmark
AI-12   model routing v2 — NOT CLOSED (AI-12-C BLOCKED)
AI-13   long-running workflows and the human approval point — COMPLETE / CLOSED
```

```text
FROZEN: AI-14 composes existing capabilities. It MUST NOT redefine one, and it MUST NOT
        become the owner of a semantics another phase froze. Where AI-14 needs a
        behaviour that no phase owns, it records an OPEN or BLOCKED item (§20) rather
        than defining the behaviour here.
```

The reason this phase exists at all is that the repository today is **a set of frozen
layers with almost no production composition**. §5 records exactly where that is true, on
evidence, because "the directory exists" is not "the architecture is connected".

---

## 2. Normative Language

```text
FROZEN      settled by this contract. AI-14-B MUST implement it. Changing it requires an
            amendment (§24).

PROPOSED    this contract's choice, made so AI-14-B does not have to choose while
            implementing. Normative for AI-14-B, and the class most likely to be amended.

RECORDED    a fact about the repository as it is. Not a requirement and not a proposal —
            it is the evidence base §4-§6 and Appendix A rest on. A RECORDED fact that
            stops being true is corrected by updating the record, never by arguing with
            it.

DEFERRED    deliberately not done, with the reason recorded.

BLOCKED     cannot be done now, and the blocker is named.

OPEN        a question this contract does NOT answer. An OPEN item MUST NOT be closed by
            an implementation decision (§24).
```

```text
FROZEN: the classification vocabulary of §5 is part of the contract:

            CONNECTED                  production code on both sides of the boundary,
                                       with a real call site outside tests
            IMPLEMENTED BUT NOT        both sides exist; the only callers/implementors
              CONNECTED                 are tests or nothing at all
            IMPLEMENTED                one side only, complete in itself
            DECLARES ONLY              named in a contract or a docstring, no code
            DEFERRED / BLOCKED         as above
            OUT OF SCOPE               refused by §23 and not planned

        A path is CONNECTED only when a NON-TEST call site exists. A Protocol with only
        test doubles behind it is IMPLEMENTED BUT NOT CONNECTED, however complete the
        types look.
```

---

## 3. Final system scope

The Workbench is these components and nothing else. Each row is the component's identity
in the final architecture, its responsibility, and the thing it does NOT own.

```text
Agent                   EXECUTION IDENTITY + EXECUTION
                        runs one attempt under an AgentId from the registry; produces
                        an AgentResult whose content is a REFERENCE
                        does NOT: authorize, select models, persist, approve, grade

Provider / Model        TRANSPORT + MODEL CAPABILITY ABSTRACTION
                        invokes a model through a declared provider profile
                        does NOT: authorize, select itself, retry or fall back silently

Context                 DECLARED CONTEXT ASSEMBLY
                        builds a scoped ContextResponse for a workspace
                        does NOT: decide permissions, persist evidence, cache as truth

Guard                   AUTHORIZATION
                        evaluates a GuardRequest and returns a GuardDecision
                        does NOT: execute, approve workflows, record evidence

Security Tools          TOOL EXECUTION
                        the single tool-invocation path and its adapter families
                        does NOT: authorize itself, widen its own scope

Router                  SELECTION
                        selects among eligible profiles from declared evidence
                        does NOT: authorize, execute, score into a ranking

Cross-Agent Review      INDEPENDENT EVALUATION / COMPARISON
                        compares declared review material, requests verification
                        does NOT: prove correctness, authorize, decide

Benchmark               MEASUREMENT
                        versioned tasks, measured results, declared oracles
                        does NOT: authorize, select, become routing input by itself

Workflow                EXECUTION LIFECYCLE / LONG-RUNNING STATE
                        definitions, attempts, checkpoints, runs, bounds
                        does NOT: authorize, approve, hold context or tool state

Human Approval          THE WORKFLOW GATE
                        opens ONE workflow step for ONE attempt number
                        does NOT: authorize Guard-bound actions, prove anything else

Evidence / Audit        DURABLE ADMITTED FACTS
                        admits and stores records under declared producers
                        does NOT: authorize, gate, or become a decision store

Workspace               ISOLATION BOUNDARY
                        the identity every other component scopes itself to
                        does NOT: own another workspace's facts
```

```text
FROZEN: the components above are the WHOLE final system scope. AI-14 v1 adds no
        thirteenth component and removes none.
FROZEN: an Agent, a provider, a Guard, a Router, a review layer, a benchmark, a workflow
        and an Evidence layer MUST each remain separately replaceable. AI-14 MUST NOT
        fuse any two of them into one object to make composition easier.
```

---

## 4. Ownership and authority boundaries

### 4.1 The authority matrix

Every cell is traceable to a clause or an API; none is a judgement about what a component
"should" be able to do. "Records" means the component produces a record of a fact — §6
says which of those records are durable and which are run data only.

```text
                    SELECTS             AUTHORIZES          RECORDS             EXECUTES
Agent               no                  no                  no                  YES — one attempt,
  (AI-08)                                                                         under an AgentId
                                                                                  from the registry
Router              YES — a model ref   no                  no                  no
  (AI-07/12)        or an agent_hint;
                    a hint, not a grant
Guard               no                  YES — one           no                  no
  (AI-04)                               invocation:
                                        ALLOW / DENY /
                                        BLOCKED / UNKNOWN
Security Tools      no                  no                  no                  YES — one tool
  (AI-06)                                                                         invocation, after
                                                                                  a Guard ALLOW
Provider / Model    no                  no                  no                  YES — one model
  (AI-02)                                                                         call, when a
                                                                                  caller asks
Workflow            no                  no                  YES — the run       YES — the run's own
  (AI-13)                                                     ledger              lifecycle
                                                              (RunRecord)
Human Approval      no                  NO — it opens a     no — the run        no
  (AI-13-C)                             WORKFLOW gate and   records the
                                        grants nothing to   reference
                                        Guard               (§15.2)
Evidence            no                  no                  YES — durable       no
  (AI-05)                                                     admitted facts
Review              no                  no                  YES — findings,     no
  (AI-10)                                                     run data only
Benchmark           no                  no                  YES — measured      YES — task oracles
  (AI-11)                                                     facts, run data     and the REFERENCE
                                                              only                executor
Workspace           no                  no                  no                  no — it is an
  (AI-00/03/06/13)                                                                isolation boundary,
                                                                                  not an actor
```

```text
FROZEN: the matrix has exactly ONE authorizing column entry — Guard. No composition in
        AI-14 may add a second, and no other component may be given a veto it does not
        have today (a veto is an authority, and it would be one the phase never froze).
FROZEN: "Records" is not "authorizes". A durable record, a finding, a measurement or a
        ledger entry never becomes a grant by being read (§4.2).
```

### 4.2 The ten rules

```text
1   ROUTER NEVER GRANTS PERMISSION
    AI-00 F-13: "Model Router is a Workbench core service and never grants permissions.
    Its planning identity is Plugin 5 / AI-07 Model Router v1. This label does not make
    Router a DSH plugin." routing/router.py:7-9 states it again: "Nothing here executes.
    … AI-07 selects; AI-02 makes a call when a caller asks it to, and the Router never
    asks." A RouterDecision carries no fallbacks and no nested decision
    (routing/decision.py:23).

2   GUARD REMAINS THE PERMISSION AUTHORITY
    plugins/guard/vocabulary.py:44-57 declares exactly four outcomes — ALLOW, DENY,
    BLOCKED, UNKNOWN. Guard's policy is a CALL PARAMETER and is never discovered
    (plugins/guard/__init__.py:23-26). One ALLOW authorizes one invocation
    (plugins/security_tools/guards.py:16-20: "does not cache, widen or reuse").

3   HUMAN APPROVAL NEVER BECOMES GUARD APPROVAL
    AI-04 models.py:294-315: "Guard issues no approvals; it only consumes their state."
    AI-13 §13.5 and PROJECT_STATUS.md both freeze that a workflow approval opens a
    WORKFLOW gate only, and Guard's own gate stays independently BLOCKED. The two
    vocabularies are different types and no value passes between them.

4   EVIDENCE NEVER BECOMES AUTHORIZATION
    An admission outcome is ACCEPTED / REJECTED / UNAVAILABLE (plugins/evidence/
    vocabulary.py:70-85) — a statement about a RECORD, not a permission. AI-05's own
    documents warn that "an ACCEPTED from admit() or admit_to_store() is not a full §30
    admission" (AI-05-B2-P3_EVIDENCE:276-277); nothing in AI-05 or AI-06 turns a stored
    record into a grant, and AI-14 introduces no such path.

5   BENCHMARK RESULT NEVER BECOMES PERMISSION
    OracleVerdict (PASS/FAIL/BLOCKED/NOT_RUN/UNKNOWN/UNAVAILABLE, benchmarks/
    vocabulary.py:84-89) is a MEASUREMENT vocabulary. Its only cross-layer use is AI-12
    policy evidence (routing/evidence.py), where a cited PASS can activate a rule that
    SELECTS a model ref — selection, not authorization. And the only evidence class
    suppliable to AI-12 is REFERENCE (routing/evidence.py:104), so no model measurement
    can justify a selection today (§20).

6   REVIEW FINDING NEVER BECOMES PERMISSION
    review/finding.py:1-13: a finding is "a structural observation, never a verdict";
    review/case.py:448: requesting verification "authorizes nothing and executes
    nothing"; ReviewFindingKind is not a permission vocabulary. Layer 0 refuses verdict
    tokens in the review layer outright (scripts/ci/layer0_policy.py:1866-1879).

7   WORKFLOW STATE NEVER BECOMES GUARD ALLOW
    A RunRecord, a Checkpoint and a WorkflowApproval are AI-13 types. Guard does not
    import them and cannot read them; the reverse direction (AI-13 → Guard) is DECLARES
    ONLY — workflows/ imports nothing outside itself (§5). No workflow state is an
    input to a GuardDecision.

8   A PREVIOUS AGENT RESULT NEVER AUTHORIZES ANOTHER AGENT
    agents/result.py carries references, never content; review/material.py requires
    explicitly supplied material; an agent_hint from the Router "stays a hint" and the
    agent layer is forbidden from importing routing/ at all (tests/agents/
    test_layer_boundaries.py:208-211). A second Agent's execution is a second execution
    with its own ExecutionId (AI-08 §7.2), not an inheritance.

9   RESUME NEVER CARRIES APPROVAL, AUTHORIZATION OR TOOL STATE
    AI-13 §8.2: InheritedState has exactly two fields — completed_steps and
    artifact_refs — and a test asserts the field set so a third cannot arrive quietly.
    A checkpoint that could carry an approval is refused by name at the checkpoint
    boundary (§7.2), and a resume re-verifies the definition, workspace and digests.

10  A PROVIDER CAPABILITY THAT IS UNKNOWN CANNOT BE PROMOTED BY WIRING
    CapabilityStatus is DECLARED / VERIFIED / NOT_VERIFIED / UNAVAILABLE / UNKNOWN
    (providers/model_profile.py:53-72); there is no AVAILABLE member. Only VERIFIED
    passes the Router rule (routing/profile.py:55) and the invocation gate
    (providers/invocation.py:621-640, BlockCode.CAPABILITY_NOT_VERIFIED). Every shipped
    model profile is UNKNOWN today, so the gated paths are effectively BLOCKED — and
    AI-14 composition MUST NOT change that. Connecting a layer is not evidence.
```

```text
FROZEN: the ten rules above are restatements of clauses other phases already froze. AI-14
        adds no eleventh and weakens none. Where a rule and its source contract differ,
        the SOURCE CONTRACT governs and this document is wrong (§24).
```

---

## 5. Execution topology

### 5.1 What is actually connected

This section is the answer to "the directory exists, therefore the architecture is
connected" — it does not hold. The classification below is produced from code: a path is
CONNECTED only when a NON-TEST call site exists (§2).

```text
PATH                                          CLASSIFICATION              EVIDENCE
Agent runtime -> Context                      CONNECTED                   agents/runtime.py:185
  build_context()                                                         build_context(...)
Agent runtime -> Guard                        CONNECTED                   agents/toolcall.py:51,
  evaluate()                                                              :169-174
Agent runtime -> Security Tools               CONNECTED                   agents/toolcall.py:169
  invoke()                                                                invoke(...)
  (the ONLY non-test invoke caller)
Security Tools -> Guard                        CONNECTED                   plugins/security_tools/
  ask_guard() -> evaluator(...)                                           guards.py:201
Security Tools -> Context isolation            CONNECTED                   plugins/security_tools/
  contained_path() -> is_inside()                                         paths.py:18,45-67
Review -> Agent predicates                    CONNECTED (read-only)       review/independence.py:88,
  structural_independence(), resolve_agent()                              review/material.py:120
Benchmark -> Tool registry / agent registry   CONNECTED (read-only)       benchmarks/task.py:35,749,
                                                                          benchmarks/run.py:322
Router -> provider/model TYPES                CONNECTED (types only)      routing/request.py:16-17,
  ModelProfile, ProviderProfile                                           routing/router.py:18-19
AI-12 policy -> AI-11 OracleVerdict           CONNECTED (types only)      routing/policy.py:49,
                                                                          layer0:2219 allows only
                                                                          benchmarks.vocabulary
--------------------------------------------------------------------------- SEAM -----
Agent -> Provider                             IMPLEMENTED BUT NOT         agents/codex/body.py:67
  CodexBackend Protocol                          CONNECTED                CodexBackend; the only
                                                                          structural implementor is
                                                                          integrations/codex/
                                                                          backend.py:98, built only
                                                                          in tests/integrations/
                                                                          conftest.py:196
Workflow -> Agent execution                   IMPLEMENTED BUT NOT         workflows/engine.py:238
  StepExecutor Protocol                          CONNECTED                StepExecutor — the ONLY
                                                                          implementors are test
                                                                          doubles (tests/workflows/
                                                                          conftest.py:161-362)
Workflow -> Provider invocation               DOES NOT EXIST              workflows/ imports
                                                                          nothing outside itself
Workflow -> Guard / Tools                     DOES NOT EXIST (by         layer0:2625-2640 forbids
                                                 contract)                every foreign root
Router -> model invocation                    DOES NOT EXIST              no path carries a
  RouterDecision -> Invoker                                               RouterDecision into
                                                                          Invoker.invoke
Review -> controlled verification caller      DECLARED ONLY               AI-10 §11.1/§11.2 names it;
  VerificationRequest -> invoke()                                         review/ and tests/review/
                                                                          never call invoke()
Any producer -> Evidence                      IMPLEMENTED BUT NOT         no non-test caller of
  admit() / admit_to_store()                     CONNECTED                admission.py:150,181
AI-06 -> AI-05 projection                     IMPLEMENTED BUT NOT         plugins/security_tools/
  tool_call_for(), execution_payload_for()       CONNECTED                evidence.py:19,40
```

```text
RECORDED: at this revision the Workbench has ONE connected production spine —
          Agent runtime -> Context, Guard, Security Tools (with Guard inside the tool
          path) — plus read-only predicate use of the Agent layer by Review and of the
          tool/agent registries by Benchmark. Everything else in the table is a seam, a
          declaration or an unconnected implementation.
FROZEN:   AI-14-B MUST NOT describe a SEAM as a working path. Any user-facing statement
          about the system MUST carry the classification above.
```

### 5.2 The composed path, once AI-14-B connects it

The topology AI-14 freezes is the following; every edge obeys §4's rules, and every edge
that is not CONNECTED today is an AI-14-B work item (§22 C9), not an assumption.

```text
Human / Caller
      |
      v
task intake ............ the caller's own act; no phase owns a "task" type (§6)
      |
      v
Context (AI-03) ........ build_context() -> ContextResponse, workspace-scoped
      |
      v
Router (AI-07/12) ...... evaluate() -> RouterDecision  [SELECTS ONLY]
      |
      v
Agent execution (AI-08)  run_execution() under an AgentId, one ExecutionId
      |
      +--> Security Tools (AI-06) --> Guard (AI-04) --> adapter --> ToolResult
      |         invoke() is the ONE tool path; Guard's ALLOW is per invocation
      |
      +--> Provider / Model (AI-02 / AI-09) ...... the model call itself
      |
      v
AgentResult ............ content is a REFERENCE, never inline content
      |
      v
Workflow (AI-13) ....... the run that a long task lives in; RunRecord is the ledger
      |
      +--> Human Approval (AI-13-C) when the definition declares a wait
      |         designated ingress + Ed25519 provenance + exact attempt scope
      |
      v
Result / references
      |
      +--> Evidence / Audit (AI-05) where a producer token exists (§20)
      +--> Review (AI-10) / Benchmark (AI-11) where EXPLICITLY requested
```

```text
FROZEN: an arrow above is a CALL DIRECTION, not an authority transfer. In particular:
            the arrow into Guard means "asked", never "authorized"
            the arrow into Workflow does not let workflow state authorize anything
            the arrow into Evidence is an ADMISSION REQUEST; the phase that owns the
              producer token decides, and today no token exists for any of these
              writers (§20)
FROZEN: no arrow may be shortcut. A tool invocation without Guard, an Agent execution
        that reads another Agent's result as authority, a Human Approval presented as a
        Guard decision, and an Evidence record treated as a permission are each refused
        by §4.2 and MUST be refused in code by AI-14-B.
FROZEN: the Router is NOT on the Agent's tool path and MUST NOT be placed there. It sits
        before agent execution (selection), and the tool path goes through Guard.
```

### 5.3 What "composition" means here

```text
FROZEN: AI-14-B composes by CALLING existing entry points — build_context(), evaluate()
        (Router), run_execution(), invoke(), evaluate() (Guard), admit()/admit_to_store(),
        the AI-13 engine API, the AI-10 case API, the AI-11 campaign entry point. It MUST
        NOT re-implement a layer's decision, and MUST NOT introduce a second entry point
        for a layer that already has one.
FROZEN: where a layer has no public entry point for what composition needs (the
        controlled verification caller of §5.1, for example), AI-14-B implements the
        CALLER as an explicit component and records it as such — it does not extend the
        layer it is calling.
```

---

## 6. Data and trust flow

### 6.1 Source, owner, persistence, trust

```text
TYPE                        SOURCE                 OWNER      PERSISTENCE        TRUST
Task                        human / caller         — (no      none               untrusted input
                                                   phase
                                                   type)
ContextResponse             plugins.context        AI-03      none (cache is     derived; freshness
                            .build_context()                  disposable,        declared per item
                                                              never truth)
RouterRequest               caller                 AI-07      none               caller-declared
RouterDecision              routing.evaluate()     AI-07/12   none by itself     a SELECTION; no
                                                              (audit record;     authority
                                                              caller keeps it)
AgentExecutionRequest       caller of AI-08        AI-08      none               an execution
                                                                                 request; grants
                                                                                 nothing
AgentResult                 agents.runtime         AI-08      none (content is   run data; content
                                                              a REFERENCE)       stays outside
ToolRequest                 AI-06 invoke() caller  AI-06      none               a request; Guard
                                                                                 decides it
GuardDecision               plugins.guard          AI-04      none (Decision-    AUTHORITATIVE for
                            .evaluate()                       Record returned;   THAT invocation
                                                              evidence_ref is
                                                              a reference)
RunRecord                   AI-13 engine           AI-13      caller's store     the run's state;
                                                              (persistence       origin is the
                                                              boundary)          persistence
                                                                                 boundary (§17)
Checkpoint                  AI-13 engine           AI-13      caller's store     DISPOSABLE;
                                                              (disposable)       authority for
                                                                                 nothing
WorkflowApproval            designated ingress     AI-13-C    NOT stored — the   verified
                            (Ed25519, external)               run keeps a        provenance; opens
                                                              reference only     ONE workflow gate
EvidenceRecord              a §6.5 admitted        AI-05      staged ->          a durable admitted
                            producer                          promoted store     FACT; never a grant
ReviewMaterial              explicitly supplied    AI-10      none               declared material;
                            by a caller                                          compared, not
                                                                                 trusted
ReviewFinding               review.compare()       AI-10      none (run data)    a structural
                                                                                 observation
BenchmarkRun                benchmarks.runner      AI-11      none (results/     measured facts;
                                                              is gitignored      no authority
                                                              and disposable)
```

### 6.2 Reuse, crossing, and authority

```text
TYPE                        REUSABLE?                      CROSSES WORKSPACE?   AUTHORIZES?
Task                        n/a — input                    only by the caller   no
ContextResponse             per build; cache is keyed by   NO — workspace-      no
                            workspace + source identity    scoped; one
                            (cache never truth)            workspace's items
                                                           never enter another
RouterRequest               per call                       caller-declared      no
RouterDecision              audit only; never reused as    no                   no
                            authority for a later attempt
AgentExecutionRequest       never reused; one ExecutionId  no                   no
                            per execution
AgentResult                 a REFERENCE may be repeated;   no (reference is     no
                            its content is never assumed   workspace-scoped)
ToolRequest                 per invocation                 no                   no
GuardDecision               ONE invocation; no cache, no   no                   YES — that one
                            widen, no reuse (guards.py)                         invocation only
RunRecord                   the run's own lineage          run is bound to      no
                                                           ONE workspace
                                                           identity (§5)
Checkpoint                  disposable; may be discarded   no                   no
WorkflowApproval            NO inheritance — the six       no                   opens ONE step's
                            fields bind one attempt                             ONE attempt
EvidenceRecord              read-only once promoted;       workspace-scoped     no
                            staged may be discarded        (AI-05 §18.1)
ReviewMaterial              per case                       caller's declaration no
ReviewFinding               per comparison                 no                   no
BenchmarkRun                per run                        corpus is global,    no
                                                           results are per-run
```

```text
FROZEN: the following MUST NOT cross a workspace boundary in AI-14: ContextResponse
        items, AgentResult content, ToolRequest targets, GuardDecision, RunRecord,
        Checkpoint, EvidenceRecord, ReviewMaterial. Each of those is already scoped by
        its own phase (AI-03 cache key, AI-06 contained_path, AI-05 §18.1 workspace
        agreement, AI-13 workspace identity); AI-14 composes them WITHOUT adding a
        cross-workspace path (§15).
FROZEN: the following MUST NOT authorize anything, anywhere in the composition:
        Task, ContextResponse, RouterDecision, AgentResult, RunRecord, Checkpoint,
        WorkflowApproval (outside its one workflow step and attempt), EvidenceRecord,
        ReviewFinding, BenchmarkRun. Only a GuardDecision authorizes, and only the
        invocation it names.
FROZEN: raw model output, tool output, prompts, completions, credentials and repository
        content MUST NOT enter a RunRecord, a Checkpoint or an EvidenceRecord. They stay
        outside as referenced artifacts (AI-13 §7.2, AI-05 §5.2, AI-11 §18.2).
```

---

## 7. Agent architecture

```text
identity            an AgentId from the registry — agents/vocabulary.py resolve_agent()
                    / ROLE_BY_AGENT. Two exist: DSH (primary) and Codex (independent
                    second). AgentRole is a DECLARED ROLE, never a security
                    authorization.
execution identity  one execution = one ExecutionId (agents/request.py
                    new_execution_id); AttemptId is AI-13's identity for an attempt and
                    points at a distinct ExecutionId (AI-08 §7.2)
context             execution-owned: the runtime builds its own context
                    (agents/runtime.py:185) and hands the workspace identity to the
                    tool gateway (agents/runtime.py:203-214)
result              AgentResult content is a REFERENCE (agents/result.py
                    RESULT_REFERENCE_GRAMMAR); content stays outside every record
independence        structural, not a verdict: eight declared conditions I1..I8
                    (agents/independence.py) answer "were these executions independent",
                    never "is this answer correct"
reach               agents/ imports plugins.context, plugins.guard and
                    plugins.security_tools ONLY. It reaches no provider, no routing, no
                    tools/, no evidence, no workflows (tests/agents/
                    test_layer_boundaries.py).
```

```text
FROZEN: AI-14 adds NO third Agent identity and NO new AgentRole. A future Agent is an
        EXTENSION POINT (§21) that requires an AI-08 amendment; it MUST NOT arrive as a
        configuration value, a registry default or an "experimental" body.
FROZEN: Agent identity is NOT permission. A role, an AgentId or an agent_hint grants
        nothing; only a GuardDecision authorizes an invocation.
FROZEN: an Agent execution MUST NOT read another Agent's result as authority. A second
        execution is a second execution (§4.2 rule 8).
FROZEN: independent review is NOT proof of correctness, and structural independence is
        NOT a correctness claim (§15).
```

```text
RECORDED: the AI-08 execution's coupling to a provider is a SEAM. agents/codex/body.py
          declares CodexBackend; the only structural implementor is
          integrations/codex/backend.py MimoCodexBackend, and it is constructed only in
          tests. Connecting it is an AI-14-B work item (§5), not an existing path.
```

---

## 8. Provider and model architecture

```text
provider identity   providers/profile.py ProviderProfile + registry.py, loaded from
                    config/providers/; profiles are DATA
model identity      providers/model_profile.py ModelProfile; providers/model_registry.py
                    loads them; ModelRef is provider_id/model_id
capability status   CapabilityStatus = DECLARED / VERIFIED / NOT_VERIFIED / UNAVAILABLE
                    / UNKNOWN — five members, and there is NO `AVAILABLE` member. Only
                    VERIFIED passes the Router rule (routing/profile.py:55) and the
                    invocation gate (providers/invocation.py:621-640)
enablement          declared per provider config; a disabled provider is not a candidate
credentials         CredentialRef + resolve(); no secret value is ever written into a
                    profile, a record or a log (providers/redaction.py)
invocation          providers/invocation.py InvocationRequest / InvocationResult /
                    Invoker.invoke — the ONE model-call boundary; GATED_CAPABILITIES
                    refuse a call whose capability is not VERIFIED
fallback            NONE. providers/invocation.py:38: "No retry, no fallback, no model
                    selection." AI-12's fallback/escalation declarations are DATA that
                    nothing executes (§9)
integration         integrations/codex/ binds one provider+model to the Codex agent and
                    consults neither the Router, the environment, the task text nor the
                    AgentId (integrations/codex/binding.py:16-18)
```

```text
FROZEN: UNKNOWN MUST NOT become AVAILABLE. Every shipped model profile is UNKNOWN today,
        and every "streaming / reasoning / prompt caching / endpoint" claim is
        DECLARED-and-unverified. Wiring a provider into a path does NOT verify a
        capability; only a contracted live verification does, and it is NOT_RUN (§20).
FROZEN: a Router decision does NOT authorize a model call. The invocation gate answers
        to the capability status, and the caller decides to call.
FROZEN: adding a provider or a model is a DATA change (a profile in the registry), never
        a code change in a calling layer.
FROZEN: no provider-specific business logic may appear in the workflow layer or in the
        agent layer. Provider differences live in profiles and adapters (§23).
```

---

## 9. Router architecture

```text
entry point         routing/router.py evaluate() -> RouterDecision — a PURE function
                    over (RouterRequest, RuleSet, profiles, enabled providers)
vocabulary          RoutingOutcome = SELECTED / NO_ELIGIBLE_MODEL / MODEL_UNAVAILABLE /
                    INVALID_REQUEST / INVALID_RULES / ROUTER_ERROR
rules               routing/rules.py: the only selection fields are select_model_ref and
                    select_agent; an empty rule set yields NO_ELIGIBLE_MODEL
eligibility         routing/profile.py: only CapabilityStatus.VERIFIED is available
policy (AI-12)      routing/policy.py + policy_eval.py: Policy, PolicyRule, falsifier,
                    discrimination control, rollback, and fallback/escalation as
                    DECLARATIONS; resolve_policy() returns an auditable resolution
evidence (AI-12)    routing/evidence.py: SUPPLIABLE_EVIDENCE_CLASSES = (REFERENCE,) —
                    a caller may cite AI-11 REFERENCE evidence and no model-execution
                    record at all
```

```text
FROZEN: the Router NEVER grants permission and never executes. routing/router.py:7-9:
        "Nothing here executes. No provider call, no transport, no socket, no
        subprocess. AI-07 selects; AI-02 makes a call when a caller asks it to, and the
        Router never asks."
FROZEN: the Router is a Workbench CORE service (AI-00 F-13). Its planning label
        "Plugin 5" MUST NOT be read as "make it a DSH plugin"; §17 states the boundary.
FROZEN: a RouterDecision is an audit record and a selection. It carries no fallbacks and
        no nested decision, and it MUST NOT be reused as authority for a later attempt.
FROZEN: AI-12's §6 model-comparative prerequisite stays BLOCKED. AI-14 MUST NOT activate
        a model-comparative rule, fabricate per-model measurements, or turn the REFERENCE
        campaign into model evidence (§20, §23).
FROZEN: an agent_hint stays a hint. The agent layer is forbidden from importing routing
        at all, so the hint cannot become a selection made by the layer it selects for.
```

```text
RECORDED: Router -> model invocation DOES NOT EXIST. No path carries a RouterDecision
          into Invoker.invoke; the only non-test importers of routing/ are Layer 0
          itself and tests. Router is IMPLEMENTED BUT NOT CONNECTED (§5).
```

---

## 10. Context architecture

```text
entry point         plugins/context/context.py build_context(root, *, manifest, reader,
                    cache, clock) -> ContextResponse
shape               ContextResponse: workspace, facts / history / plans, sources,
                    freshness, status, conflicts, retrieved_at
scope               one workspace. assert_same_workspace() RAISES rather than filtering,
                    so a foreign item cannot be quietly dropped or quietly kept
cache               keyed by workspace_id + source_kind + source_identity +
                    source_revision; a cache is NEVER the only source of truth (AI-00
                    F-11) and is disposable
reach               consumed by agents/runtime.py:185 (the only production caller),
                    plugins/guard (context in a GuardRequest, predicate resolution),
                    plugins/evidence (vocabulary), plugins/security_tools (containment
                    via is_inside) and integrations/codex
```

```text
FROZEN: a ContextResponse is DERIVED DATA. It is never truth, never authorization and
        never durable evidence. Freshness is declared per item and MUST NOT be
        flattened into a boolean by a composing layer.
FROZEN: Context items MUST NOT cross a workspace boundary. AI-14 composes context per
        workspace and MUST NOT add an aggregation path (§16).
FROZEN: the Context plugin performs no git write and reaches no provider; Layer 0
        executes its reader to prove the read-only set (layer0 check 13).
```

---

## 11. Tool and Guard architecture

```text
tool entry point    plugins/security_tools/dispatch.py invoke(request, *, registry,
                    evaluator, policy, runner) -> ToolResult — the ONE tool path
pipeline            registry lookup -> operation spec -> argument validation ->
                    gate 1 check_v1_target_boundary -> root resolution -> gate 2
                    ask_guard -> adapter execute -> ToolResult
refusals            a refusal is a ToolResult, never an exception: DENY -> NOT_RUN,
                    BLOCKED -> BLOCKED, UNKNOWN -> UNKNOWN
guard entry point   plugins/guard/evaluator.py evaluate(request, policy) -> DecisionRecord.
                    It NEVER raises: a malformed request becomes a decision record
vocabulary          GuardDecision = ALLOW / DENY / BLOCKED / UNKNOWN ("Exactly four");
                    CheckResult = SATISFIED / REJECTED / UNAVAILABLE / INDETERMINATE
approval input      Guard consumes an ApprovalStatus (VERIFIED/MISSING/INVALID/UNKNOWN)
                    as INPUT; it issues no approval and has no approval outcome. With no
                    verified approval the approval-gated path is BLOCKED /
                    APPROVAL_NOT_VERIFIED — the intended fail-closed state
containment         plugins/security_tools/paths.py resolves and refuses escapes by
                    RESOLUTION (plugins.context.workspace.is_inside), not by string
                    inspection
adapters            eight families under tools/ (git, github, tests, terminal, mcp,
                    vehicle_network, firmware, reverse_engineering), composed by
                    tools/__init__.py default_registry()
```

```text
FROZEN: one ALLOW authorizes ONE invocation. No cache, no widening, no reuse — the
        tool path asks again for every call and a refusal is recorded with the decision
        it came from.
FROZEN: the tool path MUST NOT be entered without Guard. A "direct" adapter call, a
        cached decision or a caller-supplied ALLOW is a bypass and MUST be refused by
        AI-14-B's composition.
FROZEN: vehicle and system boundaries stay as frozen: real CAN, real ECU, real vehicle
        and system-change/remote-change actions remain BLOCKED with no approval source
        (AI-04 §8.2, AI-00 §7). AI-14 adds no exception path.
FROZEN: Research tool ADAPTERS are separate from the Security Tools plugin (AI-00 F-14);
        the plugin is the invocation boundary and the adapters are its leaves.
```

```text
RECORDED: the AI-06 -> AI-05 projection (tool_call_for, execution_payload_for) is
          IMPLEMENTED BUT NOT CONNECTED: nothing in production admits a tool-call
          record to Evidence (§14, §20).
```

---

## 12. Workflow architecture

AI-13 is **COMPLETE / CLOSED** — merge commit
`98d4f57ad0bd78a54b9eb2ea44f30d2db394ee97` (PR #71). AI-14 **composes** it and
redefines nothing.

```text
entry points        workflows/engine.py: start_run, begin_attempt, complete_attempt,
                    advance, resume_run; resolve_approval, reenter_approval;
                    workflows/run.py: record_approval
state               RunRecord is the LEDGER and the authority for bounds; Checkpoint is
                    a disposable snapshot with authority for nothing (§15.1)
attempts            one attempt = one AI-08 execution; AttemptId = (run_id, step_id,
                    attempt_no); ExecutionIds are never reused
bounds              every bound is DECLARED; reaching one is a named terminal state;
                    the NARROWER bound governs; time spent waiting for an approval
                    consumes the run's budget
workspace           a run records the workspace identity it started under; a mismatch is
                    WORKSPACE_CHANGED and is terminal — there is no re-derivation in v1
execution seam      workflows/engine.py:238 StepExecutor Protocol — the ONLY way AI-13
                    reaches an execution, and today the only implementors are test
                    doubles (§5)
reach               workflows/ imports NOTHING outside itself (plus `cryptography` for
                    Ed25519 verification). It reaches no agent, provider, tool, guard,
                    router, review, benchmark or evidence module — enforced by Layer 0
```

```text
FROZEN: AI-13's contract, its six-field scope preimage, its Amendments 1-4 and its
        approval semantics are UNCHANGED by AI-14. This phase composes the engine; it
        does not amend §13, does not add a workflow state, does not add a FailureClass
        and does not touch the digest form.
FROZEN: the RunRecord trust boundary is as AI-13 stated it (Round 4 ruling): the engine
        trusts the record its persistence boundary supplies as the run's state, validates
        record-local invariants and every predecessor -> successor transition it
        performs, and does NOT authenticate the origin of an externally supplied record.
        AI-14 MUST NOT introduce a record-level trust root, a signing authority, a
        shared secret or a hidden marker to change that (§21 extension point).
FROZEN: connecting the StepExecutor seam to a real execution is an AI-14-B work item.
        The implementation MUST be a caller-supplied executor that performs an AI-08
        execution; it MUST NOT move execution into workflows/ and MUST NOT let the
        workflow layer reach an agent, a provider or a tool by import.
```

---

## 13. Human approval architecture

AI-13-C is **COMPLETE / MERGED** (PR #71). The approval point is frozen and AI-14 only
composes it.

```text
what it opens       ONE workflow step, for ONE attempt number. Nothing else. A workflow
                    approval is not a Guard approval, not an AI-04 ApprovalRef and not
                    an Evidence record (AI-13 §13.5)
ingress             the deployment's designated anchor, read from ONE place
                    (WORKBENCH_APPROVAL_TRUST_ANCHOR, workflows/ingress.py); no key
                    parameter, no caller-selected trust root
provenance          Ed25519, verified against THAT anchor inside
                    Provenance.__post_init__, which refuses a signature under any other
                    key; the value also binds its fields to the artifact it verified
scope               exactly six fields (workflow_id, revision, definition_digest, run_id,
                    step_id, attempt_no) and nothing else
non-inheritance     an approval for attempt N does not authorize N+1; the admission gate
                    refuses an attempt whose number no accepted approval covers
```

```text
FROZEN: AI-14 MUST NOT add a second trust-anchor reader, a second Ed25519 verification
        site, a signing key, a shared secret, a public trust-root parameter or a new
        approval mint path. The three bypasses closed in review rounds 2-3 stay closed
        and the Round 4 ruling stands.
FROZEN: a human approval MUST NOT be presented to Guard, to Evidence, to a review case
        or to a benchmark as an authorization. Guard's own approval-gated path remains
        independently BLOCKED because no Guard approval source exists (AI-04 §8.2).
FROZEN: with no designated anchor configured, every approval step is BLOCKED. AI-14 MUST
        NOT provide a default anchor, a test anchor or a development bypass.
```

---

## 14. Evidence and audit architecture

```text
entry points        plugins/evidence/admission.py admit(raw, *, clock=) -> AdmissionResult
                    and admit_to_store(raw, *, store, clock=) -> AdmissionResult
outcomes            AdmissionOutcome = ACCEPTED / REJECTED / UNAVAILABLE
kinds               EvidenceKind = OBSERVATION / DECISION / EXECUTION, with a typed
                    payload per kind and cross-field rules (§6.6)
producers           the §6.5 ADMITTED_EVENTS registry; ProducerType = AGENT / SERVICE /
                    UNKNOWN, and every v1 row requires `service`
digests             content_digest + record_digest over §7.4's canonical form; stored
                    form round-trips and is integrity-checked on read
store               plugins/evidence/store.py: STAGED (write, atomic, never overwrites)
                    and PROMOTED (no `write` method at all — "the absence is the
                    enforcement"); a promoted record is read-only and is never deleted
                    by AI-05
workspace           §18.1 workspace agreement is checked before admission
```

```text
RECORDED: nothing in production calls admit() or admit_to_store(). The whole layer is
          IMPLEMENTED BUT NOT CONNECTED: AI-08 states "v1 writes no EvidenceRecord at
          all", AI-10 writes none, AI-11 writes none, AI-13 registers no producer, and
          AI-06's projection helpers have no caller (§5, Appendix A).
RECORDED: C-1 — the PUBLISHED ADMISSION RULE SET — is DEFERRED. §30 step 7 (Class 3 and
          Class 4 fields checked against the published rules) is unimplemented,
          plugins/evidence/rules.py does not exist, T22a/T22b/T22c are unrunnable, T20c
          is skipped, and §32's C6 gate is NOT closed. An ACCEPTED from admit() or
          admit_to_store() is therefore NOT a full §30 admission.
```

```text
FROZEN: AI-14 MUST NOT read "stored" as "fully admitted", and MUST NOT describe an
        admitted record as having passed §30 step 7 while C-1 is DEFERRED.
FROZEN: AI-14 creates NO producer token, and MUST NOT register a producer for any phase.
        The §6.5 registry is AI-05's, and adding a row to it is an AI-05 amendment —
        which the owner phase must make BEFORE AI-14 depends on it (§20).
FROZEN: an EvidenceRecord is a durable FACT. It is never an authorization, never a
        permission and never a score (§4.2 rules 4-6).
FROZEN: raw tool output, model output, prompts, completions, credentials, secrets and
        repository content MUST NOT be admitted. A record carries references; the bytes
        stay outside (AI-05 §5.2, AI-13 §7.2, AI-11 §18.2).
FROZEN: durable recording of any of AI-08's, AI-10's, AI-11's or AI-13's run facts is
        DEFERRED until an AI-05 amendment admits that phase's producer. Until then those
        facts are RUN DATA, and no document may call them durable evidence.
```

---

## 15. Review and benchmark architecture

```text
review entry point  review/case.py create_case / supply_materials / record_comparison /
                    observe_independence / request_verification / observe_verification /
                    record_decision / close
review shape        a ReviewCase holds IDENTIFIERS only; findings, observations and
                    decisions are separate returned values, so a case cannot accumulate
                    content and cannot become a store
review vocabulary   ReviewFindingKind and HumanDecisionKind are observation vocabularies,
                    not verdicts; a finding is "a structural observation, never a
                    verdict"; Layer 0 refuses verdict tokens in review/ outright
review reach        review/ imports agents.independence, agents.result,
                    agents.vocabulary and ONE enum from plugins.security_tools. It
                    reaches no provider, routing, tools/, guard, evidence or workflows
benchmark entry     benchmarks/runner.py execute_task; benchmarks/campaign.py campaign()
                    (the REFERENCE-executor campaign) and determinism_control()
benchmark shape     versioned corpus under benchmarks/tasks/; oracles are declared,
                    executed and aggregated into OracleVerdict
benchmark reach     benchmarks/ imports plugins.security_tools.ToolRegistry, tools
                    .default_registry and agents.vocabulary.resolve_agent — read-only
```

```text
FROZEN: the four things are four things. Benchmark MEASURES, Review EVALUATES, Evidence
        RECORDS durable facts, Workflow EXECUTES a lifecycle. AI-14 MUST NOT fuse them
        into one pipeline object, one store or one vocabulary.
FROZEN: a REFERENCE campaign is TASK evidence, never model-performance evidence.
        AI-11 §20.4: "`reference` is a DECLARED DETERMINISTIC EXECUTOR. It is NOT A
        MODEL… a run whose agent_id is `reference` MUST NOT be presented as a model
        measurement."
FROZEN: a review finding is NOT a correctness proof and NOT an authorization. The
        controlled verification caller of AI-10 §11.1 is DECLARED ONLY today; AI-14-B may
        implement that caller, and doing so MUST call plugins.security_tools.invoke() so
        the invocation passes through Guard — review/ MUST NOT compose a ToolRequest,
        import Guard, or hold an evaluator.
FROZEN: neither a review case nor a benchmark run is persisted in v1. AI-14 introduces
        no store for either; durable review evidence stays DEFERRED to AI-05 (§20).
FROZEN: a benchmark result MUST NOT become a permission, and MUST NOT be aggregated
        across models into a ranking. AI-11's non-goals forbid cross-model aggregates
        and AI-12 §6 is BLOCKED (§20).
```

---

## 16. Workspace isolation

```text
identity            plugins/context WorkspaceIdentity (resolve_workspace); a run records
                    the workspace identity it started under (AI-13 §5); Guard carries a
                    workspace in every request; the tool path resolves containment
                    against a declared root
enforcement         AI-03 assert_same_workspace (raises, never filters); AI-05 §18.1
                    workspace agreement; AI-06 contained_path (resolution, not string
                    inspection); AI-13 WORKSPACE_CHANGED (exact identity, no
                    re-derivation in v1)
registry            workspaces/ contains a README and workspaces.example.yaml only —
                    a declared example, no discovery mechanism and no code
```

```text
FROZEN: cross-workspace aggregation DOES NOT HAPPEN by default. AI-14 composes per
        workspace; a cross-workspace view would require an explicit, separately frozen
        mechanism, and none exists (this is AI-00 §17's open question, kept OPEN).
FROZEN: SecurityLab is an independent workspace and an independent research system
        (AI-00 F-02 / F-17). The Workbench does not own SecurityLab's facts, does not
        read its internal state and does not become its scheduler. Any integration is a
        controlled interface on SecurityLab's terms (§23).
FROZEN: no component may widen its workspace scope to make composition simpler — not a
        context build, not a Guard policy, not a tool root, not a workflow run.
```

---

## 17. Plugin / core boundary

```text
plugins/            the DSH/plugin-facing layers. Four runtime plugin layers exist:
                    context (AI-03), guard (AI-04), evidence (AI-05), security_tools
                    (AI-06)
core services       agents (AI-08 execution), routing (AI-07/12 selection), review
                    (AI-10 evaluation), workflows (AI-13 lifecycle), providers (AI-02
                    model layer), tools (AI-06's adapter layer), integrations (AI-09
                    composition)
```

```text
FROZEN: the Router is a Workbench CORE service, not a plugin. AI-00 F-13: "Its planning
        identity is Plugin 5 / AI-07 Model Router v1. This label does not make Router a
        DSH plugin." The word "Plugin" in a historical roadmap label MUST NOT move a core
        service under plugins/.
FROZEN: the boundary is enforced per layer by Layer 0 (22 checks). A new module in this
        repository MUST declare exactly one pytest layer marker, and a new top-level
        package MUST arrive with its own Layer 0 check — a package without one is
        unchecked, and an unchecked package is not composable.
FROZEN: plugins/ MUST NOT import a core service. The direction is: a core service may
        call a plugin's public entry point; a plugin never reaches up into a core
        service. Where a plugin needs a decision (Guard's policy, a tool registry), it
        takes it as a PARAMETER, as it does today.
```

---

## 18. Persistence and lifecycle

```text
durable             Evidence staged/promoted records (the filesystem store, root is a
                    parameter; the Python surface is explicitly provisional, AI-05 D11);
                    the caller's RunRecord store (AI-13 owns no store — the CALLER's
                    persistence boundary holds the run); the benchmark corpus under
                    benchmarks/tasks/ (task INPUT, not results)
disposable          Context cache; AI-13 checkpoints; benchmark results (benchmarks/
                    results/ is gitignored and disposable by default); the in-memory
                    values of review cases, findings, decisions, Guard records and
                    Router decisions
nothing             AI-13 holds no store, starts no daemon and holds no execution open
                    between process lifetimes; no phase in this repository runs a
                    background process
```

```text
FROZEN: AI-14 introduces NO new durable store, NO daemon and NO cross-process execution.
        A run advances when something asks it to advance, and the only thing that
        survives a process is what a phase already declared durable.
FROZEN: AI-14 introduces NO record-level trust mechanism for RunRecord (§12). A durable
        store's integrity is the persistence boundary's responsibility; the Workbench
        states that boundary rather than pretending to authenticate it.
FROZEN: a checkpoint is disposable and carries authority for NOTHING. A resume inherits
        declared state only (AI-13 §8.2). No composition may enforce a bound from a
        checkpoint or read an approval out of one.
```

---

## 19. Integration rules

```text
ONE ENTRY POINT     every layer is reached through the entry point it already froze:
                    build_context(), routing.evaluate(), agents.runtime.run_execution(),
                    plugins.security_tools.invoke(), plugins.guard.evaluate(),
                    plugins.evidence.admit()/admit_to_store(), the AI-13 engine API, the
                    AI-10 case API, the AI-11 campaign entry point. AI-14-B MUST NOT
                    create a second way in.

CALL, DO NOT        composition calls a layer; it never re-implements that layer's
  RE-IMPLEMENT      decision, never re-derives a digest, never re-checks a bound that
                    the owning phase checks, and never "optimises" a validation away.

FAIL CLOSED         every failure path ends in NOT_RUN, BLOCKED or UNKNOWN — never a
                    default-allow. Guard returns a decision record instead of raising;
                    the tool path refuses instead of raising; an unroutable request
                    selects nothing; an unverified capability is refused.

NO NEW AUTHORITY    composition adds no grant (§4.2). No layer's output becomes another
                    layer's permission.

NO NEW TRUST ROOT   no new key, secret, anchor, verifier or record signature arrives
                    (§12, §13, §18).

NO SILENT WIRING    a seam that becomes a path is an explicit, reviewed change: it
                    updates §5, and it carries tests that show the seam's boundary still
                    holds after it is connected.
```

```text
FROZEN: every AI-14-B work item MUST name the entry point it calls and the authority the
        call does NOT transfer. A work item that cannot name both is not ready.
FROZEN: a new top-level package or a new test module MUST be accompanied by its Layer 0
        check and its layer marker in the same change (§17).
```

---

## 20. Deferred, blocked and dependency decisions

### 20.1 The decision table

| Item | Current status | AI-14 dependency | Decision |
|---|---|---|---|
| AI-05 C-1 — the published admission rule set | **DEFERRED** | none for composition; blocks any claim of a full §30 admission | **DEFER** (owner: AI-05) |
| AI-12-C — the campaign over policies | **BLOCKED / NOT STARTED** | none for composition; blocks any model-comparative selection | **DEFER** (owner: AI-12) |
| live provider verification | **NOT_RUN** | none — every gated capability is UNKNOWN, so paths fail closed | **DEFER** (owner: AI-02) |
| model-comparative evidence | **BLOCKED** | none for composition; blocks AI-12 §6 and any model-quality claim | **DEFER** (owner: AI-11 + AI-12 + AI-05) |
| durable review evidence | **DEFERRED** | none — review stays run data | **DEFER** (owner: AI-05) |
| clean-room DSH reproducibility | **DEFERRED** | none | **OUT OF SCOPE / FUTURE** (AI-01 reclassified it) |

### 20.2 Why each decision, and what it blocks

```text
AI-05 C-1 — DEFER
    Basis   AI-05-B2_DECISIONS D1: "C-1 = DEFERRED (contract §35.1); T22a/T22b/T22c =
            DEFERRED; §30 step 7 = NOT IMPLEMENTABLE in B2", and "B2 MUST NOT invent,
            guess or import an admission rule set."
    Why not BLOCK   nothing on the composition path needs Class 3/Class 4 rule checking.
            Admission steps 1-6 and 8-14 are implemented, so a record can be validated
            and stored today.
    Why not INCLUDE AI-14 has no authority to publish another phase's rule set. Closing
            C-1 is an AI-05 amendment plus §30 step 7, made by AI-05 under AI-05's rule
            (§24: AI-14 must not amend another phase).
    BLOCKS  any statement that an admitted record passed a FULL §30 admission, and any
            claim that the Evidence layer is complete.
    If AI-14-B wants a durable record it MUST first ask AI-05 to admit a producer —
            that sub-goal is BLOCKED, not deferred.
```

```text
AI-12-C and model-comparative evidence — DEFER (BLOCKED where required)
    Basis   AI-12 §6: "BLOCKED: a MODEL-comparative policy"; "§6 remains BLOCKED until
            per-model measurements exist under a separate contract defining their
            producer, attribution and measurement method." AI-12-B_EVIDENCE: "AI-12-B is
            COMPLETE and MERGED. That is not AI-12 being CLOSED."
    Why not INCLUDE   the prerequisite is per-model measurement, and AI-11's campaign
            measured TASKS through executor_kind = REFERENCE with agent_id null and no
            provider call — it contains no per-model success, cost or latency
            (PROJECT_STATUS: "No model has been measured").
    Why not BLOCK the whole phase   AI-14 composes SELECTION, and the Router works over
            the evidence classes it is allowed to read (REFERENCE only,
            routing/evidence.py:104). A model-comparative rule is not needed to compose.
    BLOCKS  any routing decision that claims one model was selected because it performed
            better. AI-14-B MUST NOT fabricate measurements, MUST NOT enable a dormant
            model-comparative rule, and MUST NOT present the REFERENCE campaign as model
            evidence.
```

```text
live provider verification — DEFER
    Basis   preflight.yml: "Layer 4 = NOT_RUN … NOT_RUN != PASS. This run promotes no
            capability"; the live workflow is workflow_dispatch-only and no credential
            has ever been supplied.
    Why not BLOCK   the invocation gate refuses an unverified capability, so composition
            is fail-closed without it.
    BLOCKS  every statement that a model capability is VERIFIED or available. Every
            shipped capability stays UNKNOWN (§8).
```

```text
durable review evidence — DEFER
    Basis   AI-10 §13.2/§13.4 and AI-10_EVIDENCE: "durable review evidence … requires an
            AI-05 amendment. The v1 §6.5 admitted-producer registry admits no AI-10
            token, and AI-10 writes NO EvidenceRecord under any token."
    Why not INCLUDE   the producer registry is AI-05's, and AI-14 cannot add a row.
    BLOCKS  any statement that a review finding or a human decision is durable. In v1
            they are run data, and documents MUST say so.
```

```text
clean-room DSH reproducibility — OUT OF SCOPE / FUTURE
    Basis   AI-01: "reclassified as deferred deployment / reproducibility validation; it
            is not an AI-01 exit blocker. It is not a PASS."
    Decision   AI-14 does not adopt it. It is a deployment-validation activity, not
            architecture, and adopting it here would silently reopen a closed phase's
            exit.
```

### 20.3 The rule that keeps this honest

```text
FROZEN: "it can be implemented first and filled in later" is NOT "it is not a
        dependency". For every item above, the DEFER applies to the PHASE DELIVERABLE,
        and the item stays a BLOCK for any AI-14-B work item that would need it:
            a durable record of a run fact      -> BLOCKED until AI-05 admits a producer
            a model-comparative selection       -> BLOCKED until §6's prerequisite
            a VERIFIED capability claim         -> BLOCKED until live verification runs
            a durable review finding/decision   -> BLOCKED until AI-05 admits a producer
            a full §30 admission claim          -> BLOCKED until C-1 is published
            a cross-machine reproducibility     -> OUT OF SCOPE, not planned here
FROZEN: AI-14-B's scope (§22 C9) MUST NOT contain a work item that depends on a BLOCKED
        item unless that item's owner has first made the amendment it requires. A
        composition that "temporarily" papers over one is the defect this rule forbids.
```

---

## 21. Extension points

Each of these is a place the architecture is DESIGNED to grow. None is built in v1, and
none may arrive as a default, a helper or a configuration flag.

```text
EXTENSION POINT                     OWNER       WHAT IT WOULD REQUIRE
a third Agent identity              AI-08       an AI-08 amendment (registry + role).
                                                AI-14 creates none (§7).
a new provider or model             AI-02       a profile in the registry — a DATA
                                                change, no code change anywhere else
a new tool adapter family           AI-06       an adapter + registry entry under
                                                tools/, with the same Guard path
a new Evidence producer             AI-05       an AI-05 amendment to the §6.5 registry
a new review verification kind      AI-10       an AI-10 amendment; the invocation still
                                                goes through AI-06's single path
a new benchmark task family         AI-11       corpus data + a declared oracle
model-comparative routing           AI-12       §6's prerequisite: per-model measurement
                                                under a separate contract
multi-workspace discovery           AI-00/AI-03 AI-00 §17 keeps this OPEN; a frozen
                                                mechanism would be needed first
record-level trust for RunRecord    AI-13       NOT in v1 (Round 4 ruling). It would
                                                need a record trust root — a signing
                                                authority or a shared secret — which the
                                                phase deliberately does not have
cross-workspace aggregation         AI-00/AI-03 an explicit mechanism and a contract;
                                                never a side effect of composition
```

```text
FROZEN: an extension point is a PLACE, not a promise. AI-14-B MUST NOT implement one
        "because it will be needed later", and MUST NOT leave a flag, a stub or a
        TODO-shaped code path that quietly enables one.
```

---

## 22. Definition of Done

```text
C0   this contract FROZEN by the merge of the AI-14-A PR (not by its existence)
C1   status record corrected: PROJECT_STATUS.md and MASTER_ROADMAP.md agree with the
     real `main` history for every closed phase (AI-14-A delivers this)
C2   architecture inventory recorded on code evidence, with the §5 classification, and
     with every DECLARES-ONLY / NOT-CONNECTED item named (§5, Appendix A)
C3   authority matrix frozen: every cell traceable to a contract clause or an API (§4)
C4   execution topology frozen, distinguishing CONNECTED paths from SEAMS (§5)
C5   data and trust flow frozen for every type in §6, including what may NOT cross a
     boundary
C6   dependency decisions made and argued for AI-05 C-1 and AI-12-C (§20)
C7   extension points named, and every "later maybe" refused a home in v1 (§21)
C8   non-goals frozen (§23)
C9   AI-14-B scope stated as a work list derived from C2-C7, with no item that requires
     redefining another phase
```

```text
FROZEN: AI-14-A satisfies C0 only on merge. C1-C9 are satisfied by THIS document's
        contents; AI-14-B is the sub-phase that implements the composition C9 lists.
```

---

## 23. Non-goals — FROZEN

```text
no distributed scheduler                 no cross-machine coordination
no cloud orchestration                   no hosted control plane
no arbitrary DAG engine                  steps stay an ordered declared sequence
no autonomous policy learning            no policy that rewrites itself
no model self-selection without          AI-12's prerequisite stands; a model still
  evidence                                 cannot pick itself into service
no hidden retry                          no retry a caller did not ask for
no hidden fallback                       AI-12's fallback stays DATA
no hidden escalation                     no privilege path that opens itself
no shared Guard cache                    one ALLOW authorizes one invocation
no cross-Agent result authority          one Agent's result grants nothing to another
no Evidence-as-permission                a record is never a grant
no Workflow-as-permission                workflow state is never a Guard ALLOW
no SecurityLab coupling                  SecurityLab keeps its own facts (§16)
no new daemon unless separately          v1 holds nothing open between processes
  justified
no provider-specific business logic      the workflow layer never learns a vendor
  in the workflow layer
```

```text
FROZEN: each line above corresponds to a clause another phase already froze. AI-14
        restates them so that a composition cannot quietly reintroduce one; it does not
        re-open any of them.
FROZEN: a capability that "may be needed later" goes to §21 as an EXTENSION POINT. It
        MUST NOT be smuggled into v1 as a default, a helper or a "temporary" path.
```

---

## 24. Amendment procedure

```text
FROZEN: AI-14-B MUST NOT deviate from this document without amending it first.

An amendment is REQUIRED for any change to:

    the component list or a component's responsibility (§3)
    the authority matrix, or any of §4's ten rules
    the execution topology's CONNECTED/SEAM classification of a path (§5)
    a data type's source, owner, persistence, trust level or propagation rule (§6)
    the plugin / core boundary (§17)
    a dependency decision recorded in §20
    the non-goals (§23)
    which sub-phase owns which semantics

An amendment records: what changed, why, its security and authority impact, and the
date. It is committed BEFORE the code that depends on it, and it is logged in §25.
```

```text
FROZEN: AI-14 owns this document. It does NOT own AI-00 … AI-13. An amendment to one of
        those is made by that phase under that phase's own amendment rule, BEFORE AI-14
        depends on it — AI-14 MUST NOT amend another phase's contract from here.
FROZEN: this document MUST NOT modify a frozen clause of any earlier phase, and MUST NOT
        restate one in weaker words. Where AI-14 restates an earlier rule, the earlier
        contract remains the authority and a conflict is resolved in ITS favour.
```

---

## 25. Amendment Log

```text
(none — this document has not been amended)
```

---

## Appendix A — Architecture inventory (evidence)

Classification per §2/§5. Evidence is a file and, where useful, a line. This is the
inventory §22 C2 requires; it is a RECORDED fact about the repository at
`main @ 98d4f57ad0bd78a54b9eb2ea44f30d2db394ee97`, not a design intent.

```text
LAYER / ITEM                              CLASSIFICATION                 EVIDENCE
context  build_context()                  CONNECTED                      plugins/context/context.py:271;
                                                                         agents/runtime.py:185
context  workspace containment            CONNECTED                      plugins/security_tools/
  (is_inside / canonical_root)                                           paths.py:18,45-67
context  cache (never truth)              IMPLEMENTED                    plugins/context/cache.py
guard    evaluate()                       CONNECTED                      plugins/guard/evaluator.py:620;
                                                                         agents/toolcall.py:172
guard    approval vocabulary              DECLARES ONLY (input state)    guard/models.py:294-315;
                                                                         evaluator.py:192-221
guard    four-member decision vocabulary  IMPLEMENTED                    guard/vocabulary.py:44-71
tools    invoke() — the single path       CONNECTED                      security_tools/dispatch.py:64;
                                                                         agents/toolcall.py:169
tools    eight adapter families           IMPLEMENTED                    tools/__init__.py:43-57
tools    -> Evidence projection           IMPLEMENTED BUT NOT CONNECTED  security_tools/evidence.py:19,40
agents   identity / runtime / results     IMPLEMENTED                    agents/vocabulary.py:123;
                                                                         runtime.py:142,250; result.py
agents   structural independence (I1-I8)  IMPLEMENTED                    agents/independence.py
agents   -> provider (CodexBackend)       IMPLEMENTED BUT NOT CONNECTED  agents/codex/body.py:67;
                                                                         integrations/codex/
                                                                         backend.py:98 (tests only)
providers profiles / registry / validate  IMPLEMENTED                    providers/model_profile.py:381;
                                                                         providers/model_registry.py
providers invocation boundary             IMPLEMENTED (no production     providers/invocation.py:722
                                             caller)                     (callers: live_verification,
                                                                         integrations/codex/tests)
providers live verification               NOT_RUN (path implemented)     providers/live_verification.py;
                                                                         .github/.../preflight.yml:67
providers capability VERIFIED             BLOCKED (all UNKNOWN)          providers/model_profile.py:53-72
routing  evaluate() (AI-07 v1)            IMPLEMENTED BUT NOT CONNECTED  routing/router.py:48
routing  policy core (AI-12)              IMPLEMENTED BUT NOT CONNECTED  routing/policy.py:502;
                                                                         routing/policy_eval.py:244
routing  fallback / escalation            DECLARES ONLY (data)           routing/policy.py:281-334
routing  model-comparative rule           BLOCKED                        AI-12 plan §6;
                                                                         routing/evidence.py:104
review   case / finding / decision API    IMPLEMENTED (run data)         review/case.py:122;
                                                                         review/finding.py:35
review   controlled verification caller   DECLARED ONLY                  AI-10 plan §11.1-§11.2;
                                                                         review/verification.py:15-25
review   durable evidence                 DEFERRED (AI-05 amendment)     AI-10_EVIDENCE:353-365
bench    corpus / oracles / REFERENCE     IMPLEMENTED                    benchmarks/task.py:46;
           campaign                                                      benchmarks/oracle.py:49;
                                                                         benchmarks/campaign.py:168
bench    model-measurement campaign       BLOCKED / DEFERRED             AI-11 plan §20.3-§20.4
bench    durable results                  NOT IMPLEMENTED (disposable)   .gitignore:39-40
workflows engine / ledger / policy        IMPLEMENTED                    workflows/engine.py; run.py
workflows approval point                  IMPLEMENTED + WIRED            workflows/approval.py;
                                                                         workflows/ingress.py
workflows -> agent execution              IMPLEMENTED BUT NOT CONNECTED  workflows/engine.py:238
  (StepExecutor)                                                         (test doubles only)
workflows -> provider / tool / guard      DOES NOT EXIST (by contract)   layer0_policy.py:2625-2640
evidence admission (§30 1-6, 8-14)        IMPLEMENTED BUT NOT CONNECTED  plugins/evidence/admission.py:150,181
evidence store (staged / promoted)        IMPLEMENTED BUT NOT CONNECTED  plugins/evidence/store.py:261-331
evidence §30 step 7 (C-1)                 DEFERRED                       AI-05-B2_DECISIONS:31-44
evidence producers (AI-08/10/11/13)       DECLARES ONLY / DEFERRED       AI-05 §6.5 registry
integrations/codex backend                IMPLEMENTED BUT NOT CONNECTED  integrations/codex/backend.py:98
workspaces registry / discovery           DECLARES ONLY                  workspaces/README.md +
                                                                         workspaces.example.yaml
```

```text
FROZEN: this appendix is the evidence base for §5. AI-14-B MUST update it when a
        classification changes — connecting a seam is a change to this table, and the
        table is part of the contract (§24).
```
