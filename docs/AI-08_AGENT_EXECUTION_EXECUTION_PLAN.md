# AI-08 — Codex Second Agent Execution Plan

> Status: **FROZEN** (AI-08-A, 2026-10-01)
> Phase: AI-08 — Codex Second Agent
> Sub-phase: **AI-08-A — Contract / Execution Plan / Freeze**
> Prerequisite: AI-00 … AI-07 (all COMPLETE and merged)
> Base branch: `main`
> Base SHA: `a7c4a1e2536536940d96431883dadb592f7c151a`
> Rule: This document defines the contract. AI-08-B implements against it. Nothing in AI-08 may
> deviate from a frozen contract without amending this document first (§18).

---

## 1. Purpose

AI-08 makes Codex a **second Agent** with its own identity, its own execution instance, its own
result and its own provenance — not a DSH subprocess, not a DSH internal model switch, not a
provider and not a model profile.

```text
Task
  |
  v
AI-07 Router            selects an eligible model profile, and may carry an agent hint
  |                     it does not execute an Agent and proves nothing
  v
AI-08 Agent layer       resolves Agent identity, runs one execution, owns AgentResult
  |
  v
AI-04 Guard             authorizes each tool invocation        <- unchanged authority
  |
  v
AI-06 Tools             execute the capability
  |
  v
AI-05 Evidence          records admitted facts                 <- AI-08 writes none in v1 (§13)
```

**Router selects. Guard authorizes. Evidence records. AI-08 executes and attributes.**

### 1.1 Architectural identity — FROZEN

```text
AI-08 is a Workbench CORE AGENT LAYER at agents/.
AI-08 is NOT a DSH plugin.
AI-08 is NOT a provider.
AI-08 is NOT a model profile.
AI-08 is NOT a DSH child process.
AI-08 is NOT a DSH internal model switch.
```

```text
DSH   = primary Agent
Codex = independent second Agent

DSH ≠ Codex
```

`agents/` exists in this repository today as a name reservation and nothing else: two placeholder
READMEs, no Python. AI-08-A changes no part of that. AI-08-B is the phase that puts code there.

### 1.2 What AI-08-A delivers

```text
docs/AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md   this document
docs/PROJECT_STATUS.md                         AI-08-A status only
docs/MASTER_ROADMAP.md                         AI-08 status only
tests/routing/test_router.py                   two AI-07 absence assertions, maintained (§17)
```

### 1.3 What AI-08-A does NOT deliver

```text
no Agent runtime              no agents/**/*.py
no AgentResult implementation no execution, no resolver, no predicate
no Codex provider             no OpenAI-compatible integration, no model profile
no network                    no live call, no credential, no transport
no subprocess execution
no Evidence implementation    no AI-05 change of any kind
no Guard implementation       no AI-04 change of any kind
no Context implementation     no AI-03 change of any kind
no AI-07 change               the AI-07 contract blob is not touched
```

---

## 2. Normative Language

```text
MUST       a requirement. AI-08-B that violates it is not conformant.
MUST NOT   a prohibition.
FROZEN     binding, and changes only by amendment (§18).
DEFERRED   declared, and deliberately not decided here.
OPEN       named as unresolved, with a stated default.
OWNER      which phase owns a vocabulary or a boundary.
```

---

## 3. What already exists, and what this contract does with it

AI-08 is not written on a blank page. Everything here is a **transcription or a reconciliation**,
never a contradiction.

```text
docs/adr/0002-agent-boundary.md      "DSH is the Primary Agent. Codex is an Independent
                                      Second Agent." — and the two keep separate
                                      execution paths and evidence records      (§1.1, §9)
docs/architecture/COMPONENT_MAP.md   DSH Main Agent and Codex Second Agent as siblings,
                                      both above the Provider / Model layer    (§1.1, §15)
docs/MASTER_ROADMAP.md AI-08         the four requirements: independent context,
                                      independent result, independent tool
                                      permission record, no shared unverified
                                      model judgement                          (§1, §8, §9, §12)
docs/AI-00_…ARCHITECTURE.md §3.1     DSH: primary Agent, not bound to one model      (§6)
docs/AI-00_…ARCHITECTURE.md §3.2     Codex: second implementation path, independent
                                      code review, second opinion, cross-validation,
                                      and "not a sub-model of DSH"               (§1.1)
docs/AI-00_…ARCHITECTURE.md §13      Agent A + Agent B + executable verification +
                                      human decision = evidence-backed result;
                                      agreement is explicitly NOT verification (§8.2)
docs/GIT_AND_SECURITY_BOUNDARY.md    Agent text never maps to PASS automatically;
                                      fail-closed on Guard error               (§8.2, §12)
agents/README.md                     "dsh/: primary Agent" · "codex/: independent
                                      second Agent"                             (§5, §17)
config/dsh/config.example.yaml       role: primary                    documentation only (§5.3)
config/codex/config.example.yaml     role: independent_second_agent   documentation only (§5.3)

AI-04  ActorType                     human | agent | service | unknown — imported, not
                                     redefined; AI-08 adds no member to it      (§5.3)
AI-04  Actor                         {id, type} — carried and digest-bound, never
                                     consulted during evaluation               (§12)
AI-04  PermissionLevel               read | analyze | test | modify |
                                     system-change | remote-change             (§12)
AI-06  §8.2 / AI-05 §26              "A tool's own claim of success is a claim with a
                                     producer. AI-05 records the claim and its
                                     producer. It adjudicates nothing."        (§8.2, §13)
AI-05  §6.5 ADMITTED_EVENTS          six rows, producers ai-03/ai-02/ai-04/ai-06;
                                     every row registers producer_type service  (§13)
AI-05  ProducerType                  agent | service | unknown — AGENT is a valid member
                                     and is inadmissible for every v1 event     (§13)
AI-07  §11 second opinion            "a hint is a hint"; AI-07 MUST NOT execute or
                                     validate the independent Agent, and MUST NOT
                                     claim any independence property about it   (§6)
routing/decision.py                  RouterDecision.agent_hint: str | None       (§6)
```

**Two facts govern this phase and are stated where a reader will find them.**

```text
Every capability on every shipped model profile is UNKNOWN, and no provider call has
ever been made in this repository. AI-08 v1 therefore cannot execute anything through
the provider layer — and it does not try to (§15). That is the honest state.

AI-08 v1 has NO provider binding. It defines the Agent execution contract that AI-09
will wire to a real Codex backend. A contract with no backend is not a defect; it is
the boundary this phase was asked to freeze.
```

---

## 4. Scope

### 4.1 In scope

```text
the Agent identity model: AgentId, AgentRole, and the registration table
the identity boundary: how a hint becomes a resolved identity, and how it does not
the execution contract: AgentExecutionRequest, ExecutionId, the execution instance
the Context isolation rule
the independence definition I1–I8, and what it cannot prove
AgentResult, and the rule that it is not a verdict
AgentExecutionOutcome, three members, AI-08's own
the Guard boundary: unchanged, one fresh decision per tool invocation
the Evidence boundary: what AI-08 may and may not write, and why v1 writes nothing
the cross-agent result sharing prohibition
the Codex provider boundary, deferred whole to AI-09
the repository layout, the amendment rule, the test matrix and the exit gates
```

### 4.2 Out of scope

```text
Agent execution implementation        AI-08-B
any provider or model integration     AI-09 owns it
cross-agent comparison                AI-10 owns it
the second-opinion closure            AI-10 owns it
human decision recording              AI-10, with AI-05's existing types
benchmark comparison                  AI-11 owns it
routing v2 fallback / escalation      AI-12 owns it
retry, timeout, cancellation,
  checkpoint, resume, failure
  classification                      AI-13 owns it
Guard, or any part of authorization   AI-04 owns it and is not modified
Context, or any part of AI-03         AI-03 owns it and is not modified
Evidence, or any part of AI-05        AI-05 owns it and is not modified
the AI-07 Router                      AI-07 owns it and is not modified
DSH integration                       not in v1
```

### 4.3 Non-goals, restated as the boundary

```text
AI-08 is NOT:
    a provider
    a model profile
    a routing engine
    an authorization engine
    a second Guard
    a truth adjudicator
    an Evidence store
    a verification mechanism
    a majority-vote mechanism
    a fallback-until-success engine
    a benchmark
```

---

## 5. Agent identity

### 5.1 AgentId — FROZEN

```text
OWNER: AI-08
```

A closed vocabulary. **v1 has exactly two members.**

```python
class AgentId(StrEnum):
    DSH = "dsh"
    CODEX = "codex"
```

```text
FROZEN: a free-form string is NEVER a trusted Agent identity.
FROZEN: adding a member is a code change and a contract amendment (§18).
        It MUST NOT arise from filesystem discovery, environment inspection,
        configuration reading, network lookup or any other runtime mechanism.
FROZEN: AgentId is not inferred from a model name, a provider id, a display name
        or a process name. None of those is an Agent identity.
```

The vocabulary does not collide with any existing one:

```text
plugins.guard.vocabulary.ActorType      human | agent | service | unknown
plugins.evidence.vocabulary.ProducerType agent | service | unknown
providers.model_profile.CapabilityName  a model capability, not an actor
routing.vocabulary.RoutingOutcome       a routing result, not an actor
```

`AgentId` is AI-08's own and is **not merged with any of them**. `BLOCKED` and `UNKNOWN` already
appear in more than one vocabulary in this repository; that is a known cost recorded by AI-04 §3,
and AI-08 does not remove it by merging types.

### 5.2 AgentRole — FROZEN

```text
OWNER: AI-08
```

```python
class AgentRole(StrEnum):
    PRIMARY = "PRIMARY"
    INDEPENDENT_SECOND = "INDEPENDENT_SECOND"
```

§19 Q-2 asked whether `AgentRole` is needed. **It is kept**, for one reason: without it, "which
Agent is primary" exists nowhere in code, and the independence predicate (§9) would compare two
identifiers without knowing which one is the primary and which is the second. The concept already
exists as prose in `agents/README.md` and as an unread example-config field; this section moves it
into one place that code can read.

```text
FROZEN: AgentRole is AI-08's own and MUST NOT restate HUMAN / AGENT / SERVICE.
        It carries no permission, no capability and no authorization.
FROZEN: the v1 registration is total and fixed:

            dsh   -> PRIMARY
            codex -> INDEPENDENT_SECOND

FROZEN: a role is a property of the REGISTRATION, not of an execution instance.
        An execution carries an AgentId; it does not carry a role, because a
        stored role could disagree with the registry and become a second source
        of truth.
```

### 5.2.1 A role is not an independence finding — FROZEN

`INDEPENDENT_SECOND` is an architectural name. It is the word `codex` would have been registered
under even if nothing in this repository ever executed a second Agent. Stating the limit explicitly,
because the name invites exactly one misreading:

```text
FROZEN: AgentRole.INDEPENDENT_SECOND is an ARCHITECTURAL ROLE.
FROZEN: it is NOT an independence finding.
FROZEN: the role ALONE MUST NOT satisfy I1-I8 (§9.1).
FROZEN: the role MUST NOT be recorded, cited or counted as proof of structural
        independence.
FROZEN: a tool, a report or a test MUST NOT conclude "these two executions are
        independent" from the registration table.
```

```text
Structural independence exists ONLY when the I1-I8 execution-pair predicate holds
over two actual executions. It is a property of an EXECUTION PAIR (§9.1), never a
property of an Agent, and never a property of a registration row.
```

```text
The vocabulary is unchanged by this clarification. No member is added, removed or
renamed; this subsection states what the existing member does not mean.
```

### 5.3 Three questions, three fields — FROZEN

The most likely way to get this phase wrong is to collapse these into one another. They are not
interchangeable.

```text
ActorType     WHAT KIND of actor is this        AI-04 owns it
              ActorType.AGENT means: this is an agent actor.
              It does not say which agent.

AgentId       WHICH registered Agent            AI-08 owns it
              dsh | codex.
              It does not say what the agent is for.

AgentRole     WHAT ROLE does it carry           AI-08 owns it
              PRIMARY | INDEPENDENT_SECOND.
              It does not restate the actor kind and it grants nothing.
```

```text
FROZEN: AI-08 MUST NOT add a member to ActorType.
FROZEN: AI-08 MUST NOT create a second actor-type vocabulary.
FROZEN: AI-08 MUST NOT encode a role inside ActorType, AgentId or any string.
FROZEN: AgentRole MUST NOT be read as an authorization input by anything.
        Guard does not consult it and cannot consult it (§12).
```

### 5.4 Registration, not discovery — FROZEN

```text
FROZEN: Agent identity resolution is a pure function over the frozen AgentId
        vocabulary and the frozen registration table.

FORBIDDEN:
    reading a directory to decide which Agents exist
    reading an environment variable to decide which Agents exist
    reading config/ to decide which Agents exist
    treating an unregistered token as a new Agent
    a "default agent" that applies when the token is unrecognised
```

`config/dsh/config.example.yaml` and `config/codex/config.example.yaml` remain what they are today:
**documentation**. No code reads them, they are not a schema — Layer 0 asserts that example configs
carry no credential values, and `tests/unit/test_repository_layout.sh` requires the files to exist.
They MUST NOT become an identity source.

---

## 6. Router → Agent boundary

### 6.1 agent_hint is not identity — FROZEN (transcribed from AI-07 §11)

```text
FROZEN: RouterDecision.agent_hint is a HINT.
FROZEN: a hint is a CANDIDATE string, never a resolved identity.
FROZEN: `agent_hint == "codex"` MUST NOT be read as "Codex has executed",
        "Codex exists", "Codex is available" or "Codex is independent".
FROZEN: a RouterDecision carries NO execution result, NO AgentResult and
        NO independence finding.
FROZEN: AI-08 MUST NOT change routing/, the RouterRequest or the RouterDecision.
```

AI-07 already froze all of this (`docs/AI-07_MODEL_ROUTER_EXECUTION_PLAN.md` §11). AI-08 transcribes
it and adds nothing. The Router's own rule stands: *AI-07 is not the producer of an independence
claim.*

### 6.2 The identity boundary — FROZEN

AI-08 provides exactly one way for a candidate string to become a trusted identity:

```text
resolve_agent(candidate) -> AgentId
    a registered AgentId member  -> returned, resolved
    anything else                -> REFUSED
```

```text
FROZEN: resolve_agent is the ONLY boundary at which a candidate becomes an AgentId.
FROZEN: an agent_hint MUST pass through this boundary before any part of AI-08
        acts on it.
FROZEN: resolve_agent performs no discovery (§5.4). It is a closed membership
        test plus the frozen registration table.
FROZEN: resolve_agent refuses rather than guessing. There is no "probably dsh"
        branch and no default agent.
```

`require_independence` remains a **requirement only**. AI-08 does not read it, does not act on it,
and MUST NOT record that it was satisfied. AI-10 owns whatever closes it.

### 6.3 Router does not execute — FROZEN

```text
FROZEN: AI-08 MUST NOT be reachable from routing/.
        routing/ imports plugins.guard.vocabulary and nothing else
        (Layer 0 enforces this at full-module-path granularity).
FROZEN: the Agent layer MUST NOT be imported, constructed or called by the Router.
FROZEN: AI-08 MUST NOT add an execution path to the Router.
```

---

## 7. Execution

### 7.1 What one execution is — FROZEN

```text
One Agent execution is the complete execution instance that begins when an
AgentExecutionRequest is accepted and ends when exactly one terminal AgentResult
has been produced for it.
```

It MUST have all of:

```text
an ExecutionId                          §7.2
an AgentId                              §5.1
a workspace identity                    §7.3
a declared input descriptor             §7.3
exactly one ContextResponse             ESTABLISHED BY THE RUNTIME, not carried
                                        in the request — §8
zero or more tool invocations           §12
one terminal AgentResult                §10
```

```text
FROZEN: an execution produces EXACTLY ONE terminal AgentResult.
        There is no partial result, no intermediate result and no second one.
FROZEN: zero tool invocations is a valid execution. An execution that answered
        from context alone is complete, not incomplete.
FROZEN: the ContextResponse is an OWNED OUTPUT of the execution, produced by the
        execution runtime. It is NOT an input supplied through the request (§7.3).
        "The request carries context" and "the execution establishes context" are
        two competing semantics and only the second one holds here.
```

### 7.1.1 One terminal result, for every outcome — FROZEN

`one terminal AgentResult` holds for **all three** `AgentExecutionOutcome` members, without
exception. This is stated separately because it is the one place where a reader could reasonably —
and wrongly — conclude that a failed or blocked execution has no result.

```text
FROZEN: COMPLETED, FAILED and BLOCKED each terminate in EXACTLY ONE
        AgentResult. The count is one in all three cases.
FROZEN: there is no outcome for which no AgentResult exists.
```

```text
Agent execution body did not start
    ≠
no AgentResult exists
```

```text
FROZEN: the execution CONTROLLER / RUNTIME produces the terminal AgentResult.
        It does so whether or not the Agent execution BODY ran.
FROZEN: for BLOCKED the body never started, and the controller still produces
        the terminal AgentResult describing the blocking condition.
FROZEN: for FAILED the body started and did not produce a valid task result, and
        the controller still produces the terminal AgentResult describing the
        failure.
FROZEN: a terminal AgentResult is therefore NOT evidence that the Agent body ran.
        It is evidence that the execution reached a terminal outcome, which is a
        different claim (§8.2 of AI-00's rule, one layer over).
```

```text
The invariant, for every execution:

    one AgentExecutionRequest
        ->
    one ExecutionId
        ->
    one terminal AgentResult

It holds identically for COMPLETED, FAILED and BLOCKED.
```

```text
FROZEN: this introduces no fourth outcome and no non-terminal outcome (§11).
FROZEN: "the controller produced a result" MUST NOT be read as "the Agent
        completed the task" (§11.3).
```

### 7.2 ExecutionId — FROZEN

```text
OWNER: the AI-08 execution runtime
```

```text
FROZEN: a new ExecutionId is created for every execution.
FROZEN: an ExecutionId is never reused, never recycled and never derived from
        another execution's id.
FROZEN: an ExecutionId is opaque. It encodes no agent, no workspace, no task,
        no timestamp and no outcome. Nothing may be parsed out of one.
FROZEN: a DSH execution and a Codex execution MUST NOT share an ExecutionId.
FROZEN: a shared task reference MUST NOT be used AS an ExecutionId, and an
        ExecutionId MUST NOT be used as a task reference.
```

```text
task / work-item identity   ≠   execution identity
```

If two executions belong to one upper-level task, that relationship is carried by a **separate**
task reference. §19 Q-3 asked who owns `ExecutionId`; the answer frozen here is the AI-08 execution
runtime, and it owns the task reference too, as a distinct field.

```text
FROZEN: AI-08 v1 has no parent-execution relationship, no retry lineage and no
        resumption lineage. A second attempt is a SECOND EXECUTION with its own
        ExecutionId — a distinct record, not a retry state. Retry, resume and
        failure classification belong to AI-13 (§16).
```

### 7.3 AgentExecutionRequest — FROZEN

The minimum an execution needs. It carries **no** credential, **no** tool argument, **no** Guard
decision and **no** `ContextResponse`.

```text
agent_id            an AgentId (§5.1)
workspace           a workspace identity, the same scope AI-03 and AI-04 use
task                a task descriptor or task reference
input               a declared input descriptor: a digest, or a reference to
                    bytes AI-08 does not itself store
```

```text
FROZEN: every field above is REQUIRED. An execution with no declared input is not
        an execution this contract produces.
FROZEN: the request does NOT carry a ContextResponse. The execution runtime
        ESTABLISHES one ContextResponse for the execution, from the execution's
        own workspace and task (§8). AI-03's ContextResponse is an owned output
        of an execution, and it is never a shared request input.
FROZEN: the request carries no api_key, no token, no credential, no secret, no
        header and no authorization value. A field nobody defined is a field a
        credential can ride in on — the rule AI-04 §4 and AI-07 §5.3 already state
        for their own boundaries.
FROZEN: an unknown field is REFUSED, not ignored.
```

If a caller needs to express **where** context should come from, it MAY pass a context
**descriptor or reference** — a workspace-scoped source reference, never a `ContextResponse` object
and never another execution's resolved context. A descriptor says what to read; it does not carry
what was read.

```text
ALLOWED      a context descriptor / reference: where the execution should read from
FORBIDDEN    a ContextResponse in the request
FORBIDDEN    another execution's ContextResponse, by object or by reference
FORBIDDEN    a context cache shared between two executions
```

```text
DEFERRED: the AI-03 ContextRef derivation needed to make such a descriptor
          first-class. AI-03 is not modified and G-14 remains deferred (§13.5).
          Until it exists, the descriptor is a workspace-scoped reference and
          nothing more.
```

### 7.4 Runtime input is not durable Evidence — FROZEN

This distinction is load-bearing and is stated here because getting it wrong in either direction
breaks something that is already frozen.

```text
RUNTIME INPUT
    MAY contain real task content. An Agent asked to review a diff must receive
    the diff. That is execution, and it is not a contract violation.

DURABLE EVIDENCE
    MUST contain only what the record contract admits: descriptors, digests,
    references and provenance — never raw prompt bodies, never task bodies,
    never tool arguments, never credentials.
```

```text
FROZEN: AI-05's rule that an EvidenceRecord stores no raw content is a rule about
        DURABLE RECORDS. It is NOT a rule that an Agent may not be given a task.
FROZEN: AI-08 MUST NOT carry real task content into a durable AgentResult (§10)
        or into any durable record.
FROZEN: credentials, secrets and tool arguments MUST NOT appear in a durable
        AgentResult or in any durable record, at any depth.
```

---

## 8. Context isolation — FROZEN

v1 uses the composition the Discovery found already available:

```text
same workspace
    +
independent ContextResponse per Agent execution
```

### 8.1 Who establishes the context — FROZEN

```text
FROZEN: the EXECUTION RUNTIME establishes exactly one ContextResponse for the
        execution, from the execution's own workspace and task.
FROZEN: each execution therefore OWNS its ContextResponse. It is an output of
        the execution, not an input to it.
FROZEN: the AgentExecutionRequest does NOT carry a ContextResponse (§7.3). There
        is no field for one, and supplying one is REFUSED rather than ignored.
```

```text
FORBIDDEN:
    passing a ContextResponse in AgentExecutionRequest
    handing one execution's ContextResponse to another execution, by object or
      by reference
    sharing one context cache instance between two executions
    a "shared context" the two Agents both read as their context object
PERMITTED:
    two executions reading the same read-only workspace facts, because each
      established its OWN ContextResponse over them (§8.2)
```

### 8.2 What is isolated, and what is not — FROZEN

```text
FROZEN: both Agents MAY target the same workspace_id, and MAY read the same
        read-only facts from it.
FROZEN: every execution establishes its OWN ContextResponse. One execution's
        ContextResponse is never handed to another execution as its context.
FROZEN: two executions MUST NOT share mutable execution state.
FROZEN: two executions MUST NOT share an AgentResult (§10).
FROZEN: two executions MUST NOT share a Guard decision (§12).
FROZEN: two executions MUST NOT share Agent-specific result state.
```

```text
ISOLATED      the resolved ContextResponse; the cache instance; result state;
              tool state; Guard decisions; execution identity
SHARED        workspace_id; read-only source facts, which are read-only precisely
              so that sharing them is not a coupling
OUT OF SCOPE  prompt / message state. It does not exist anywhere in this
              repository at any layer, and AI-08 MUST NOT invent it here.
```

```text
FROZEN: AI-08 MUST NOT modify AI-03 and MUST NOT require a change to it.
DEFERRED: Context snapshot registry, ContextRef derivation from AI-03, and
          cross-agent context comparison. All three are AI-03 / AI-05 deferred
          capabilities and remain deferred (§16).
```

---

## 9. Independence

### 9.1 The definition — FROZEN

An **execution pair** `(E_dsh, E_codex)` is **structurally independent** only when all eight
conditions hold. Each is a check over recorded artifacts, and none requires a live execution.

```text
I1  Identity separation
    E_dsh.agent_id != E_codex.agent_id
    AND both are members of the closed AgentId vocabulary (§5.1).

I2  Execution separation
    E_dsh.execution_id != E_codex.execution_id
    AND neither id is derived from the other (§7.2).

I3  Input separation
    Codex's execution input MUST NOT contain a DSH AgentResult.
    DSH's execution input MUST NOT contain a Codex AgentResult.

        Result(D) ──X──> Input(C)
        Result(C) ──X──> Input(D)

    This is the KEY boundary of AI-08 v1. v1 is BLIND independent execution.

I4  Context separation
    each execution ESTABLISHES and OWNS its own ContextResponse (§8.1), and
    neither execution's context object is the other's. Neither execution's
    context was supplied through its request.

I5  Tool authorization separation
    every tool invocation creates a FRESH GuardRequest and a FRESH GuardDecision.
    No GuardDecision object is reused across executions.
    No authorization result is reused across executions.

I6  Result separation
    each execution produces its own AgentResult, and neither carries the other's.

I7  Failure separation
    one Agent's FAILED or BLOCKED MUST NOT be converted into the other Agent's
    COMPLETED. No path converts one execution's non-success into another
    execution's success.

I8  Provenance separation
    every AgentResult names its own agent_id and execution_id, and can be traced
    back to its own execution.
```

### 9.1.1 request_digest is not an identity — FROZEN

I5 is about **fresh authorization objects**, not about digest uniqueness. Stating the difference
explicitly, because the two are easy to conflate:

```text
FROZEN: request_digest is a digest OF THE GUARD REQUEST. It is a property of the
        request that was evaluated.
FROZEN: request_digest does NOT define execution identity, and it does NOT define
        Agent identity.
FROZEN: request_digest is NOT required to be globally unique, and is NOT required
        to differ between two executions.
```

```text
Two executions MAY produce the same request_digest. That is not a violation of
I5 and MUST NOT be treated as one — the requests would simply have been
identical, which is a legitimate thing for two independent executions of the
same task to produce.

I5 is satisfied by fresh OBJECTS and a fresh DECISION each time, not by distinct
digest VALUES.
```

```text
FORBIDDEN: adding a nonce, a random field, a counter, a timestamp or any other
           make-work value to a GuardRequest so that its digest differs.
FORBIDDEN: changing AI-04's digest projection so that digests cannot collide.
FORBIDDEN: a test that asserts request_digest uniqueness across executions.
```

AI-04 owns `request_digest` and its projection. AI-08 does not change it, does not constrain it,
and does not depend on its uniqueness for anything.

```text
FROZEN: I3 is a v1 boundary and MUST NOT be relaxed within AI-08.
FROZEN: AI-10 MAY later build cross-agent review, in which one Agent's result IS
        an input to another. When it does, that is a DIFFERENT execution mode and
        MUST NOT be described as blind independent execution, and MUST NOT be
        recorded as satisfying I3.
```

### 9.2 What independence canNOT prove — FROZEN

```text
AI-08 CAN establish:
    two registered identities
    two execution instances
    separate inputs
    separate contexts
    separate Guard decision sets
    separate results
    separate provenance

AI-08 CANNOT establish, and MUST NOT claim:
    that two models are cognitively independent
    that two Agents were not influenced by similar training data
    that Codex's conclusion is correct
    that two agreeing results make a fact true
```

```text
FROZEN: structural independence MUST NOT be written, recorded or read as truth
        verification, as a PASS, as a verdict, or as a correctness claim.
FROZEN: agreement between two Agents is NOT verification. AI-00 §13 forbids
        "两边一致所以一定正确" and "模型置信度最高所以通过" by name, and AI-08
        inherits both prohibitions unchanged.
FROZEN: the independence result MUST NOT be promoted to a fact by any later
        stage that has not itself executed a verification.
```

---

## 10. AgentResult

```text
OWNER: AI-08
```

```text
FROZEN: AI-08 defines ONE AgentResult type. It is the only agent-level result in
        the repository and MUST NOT be duplicated by a second agent-result type.
FROZEN: AgentResult MUST NOT restate, wrap or re-interpret:
            providers.invocation.InvocationResult      AI-02
            plugins.security_tools.vocabulary.ToolOutcome  AI-06
            routing.vocabulary.RoutingOutcome          AI-07
            plugins.context.vocabulary.StatusValue     AI-03
            plugins.guard.vocabulary.GuardDecision     AI-04
        Each of those keeps its own owner and its own meaning. An
        InvocationResult is NOT an AgentResult. A ToolOutcome is NOT an
        AgentResult. A completed tool call is NOT a completed execution.
FROZEN: AgentResult references those results; it does not absorb them.
```

Required content:

```text
agent_id            an AgentId (§5.1)
execution_id        the ExecutionId this result terminates (§7.2)
workspace           the workspace identity the execution ran in
input               the declared input digest or reference from the request (§7.3)
outcome             a terminal AgentExecutionOutcome (§11)
result              a terminal result reference or digest.
                    When a task result/output exists, it refers to that.
                    For FAILED and BLOCKED it MAY refer to the terminal
                    failure/block result metadata instead of a task result.
                    It is ALWAYS present, and it is never the raw output (§10.2).
tool_results        references to tool invocations, zero or more
timing              start and duration metadata
blocking            for BLOCKED, the condition that prevented execution; for
                    FAILED, the failure reason code
```

```text
FROZEN: AgentResult MUST NOT carry raw model output, a raw prompt body, a raw
        task body, tool arguments or any credential. It carries a reference or
        a digest, and the bytes live outside the durable record (§7.4).
FROZEN: AgentResult is a CLAIM WITH A PRODUCER. It records that an execution
        happened and what it ended as. It is not a verdict about the task.
FROZEN: AgentResult MUST NOT be readable as PASS, as VERIFIED, or as success.
```

### 10.1 Attribution, and what "producer" means here — FROZEN

`AgentResult` is attributed by **two fields and no others**:

```text
agent_id        WHICH Agent's execution this result describes
execution_id    WHICH execution this result terminates
```

```text
FROZEN: in AI-08 v1 an AgentResult is RUNTIME / RUN DATA. It is NOT a durable
        EvidenceRecord (§13.1), and it therefore has NO AI-05 producer field.
FROZEN: AI-08 MUST NOT add a producer vocabulary to AgentResult, and MUST NOT
        invent a second one anywhere.
```

When — and only when — a future AI-05 amendment makes an AI-08 execution admissible as durable
Evidence, the two roles separate exactly as AI-05 §7 already defines them:

```text
producer    the AI-08 COMPONENT that WRITES the EvidenceRecord
actor       the AGENT whose execution is DESCRIBED

producer != actor
```

```text
FROZEN: producer and actor are different questions and MUST NOT be conflated.
FROZEN: an AgentId is an ACTOR value. It is never a producer token.
FROZEN: AI-08 MUST NOT write an EvidenceRecord under a producer token that did
        not write it (§13.1), and MUST NOT reuse "ai-06".
```

```text
DEFERRED: the AI-08 producer token itself. Until AI-05 admits one, §13.1 stands
          and no AI-08 EvidenceRecord exists to attribute.
```

### 10.2 `result` is required, and it is not always a task result — FROZEN

The field name invites one wrong reading: that a `FAILED` or `BLOCKED` result either has no
`result` at all or must carry a successful one. Neither is true.

```text
FROZEN: `result` is present on EVERY terminal AgentResult, for all three
        outcomes. There is no outcome for which it is absent.
FROZEN: `result` names WHAT THE EXECUTION TERMINATED WITH — a task result for
        COMPLETED, and the terminal failure or block metadata for FAILED and
        BLOCKED.
FROZEN: a FAILED or BLOCKED AgentResult is NOT required to carry a task result,
        and MUST NOT be read as implying one exists.
FROZEN: `blocking` carries the reason for FAILED and BLOCKED. `result` and
        `blocking` are not alternatives: a FAILED or BLOCKED result carries both.
```

```text
COMPLETED   result -> the task result, by reference or digest
FAILED      result -> the terminal failure metadata, by reference or digest
BLOCKED     result -> the terminal block metadata, by reference or digest
```

```text
FROZEN: `result` MUST NOT carry raw model output, a raw prompt body, a raw task
        body, tool arguments or any credential — for ANY outcome, not only for
        COMPLETED. A failure record is not a place where the raw content that
        caused the failure becomes storable.
```

---

## 11. Agent execution outcome — FROZEN

```text
OWNER: AI-08
```

An AI-08-owned closed vocabulary. **Exactly three members.**

```python
class AgentExecutionOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
```

```text
COMPLETED   the execution reached a terminal AgentResult representing a
            completed Agent execution.

FAILED      the Agent execution STARTED but failed to produce a valid task
            result. The execution runtime STILL produces exactly one terminal
            AgentResult describing the failure.

BLOCKED     an EXECUTION-LEVEL precondition prevented the Agent execution from
            STARTING. The execution controller STILL produces exactly one
            terminal AgentResult describing the blocking condition.
```

```text
FROZEN: the "exactly one terminal AgentResult" invariant (§7.1.1) holds for
        COMPLETED, FAILED and BLOCKED alike. FAILED and BLOCKED describe what
        the EXECUTION BODY did or did not do — they do NOT mean that no
        AgentResult exists.
FROZEN: Agent execution body did not start  ≠  no AgentResult exists.
```

```text
The vocabulary is unchanged by this amendment. No member is added, removed or
renamed; this block states what the existing three members do and do not imply.
```

### 11.1 BLOCKED is execution-level — FROZEN

The distinction between "never started" and "started and did not finish" is the whole reason
`FAILED` and `BLOCKED` are separate members, and it is stated explicitly because the two are the
easiest pair in this contract to collapse.

```text
FROZEN: BLOCKED means the Agent execution BODY did not start. A body that never
        began cannot have "partially run" and cannot have "run but failed".
FROZEN: FAILED means the Agent execution BODY did start. A body that started is
        never BLOCKED.
FROZEN: an execution-level precondition is something that prevents the execution
        BODY from beginning at all — an Agent that does not resolve, a workspace
        that cannot be used, a missing or unreadable declared input, or a
        ContextResponse that cannot be established.
```

```text
FROZEN: BLOCKED does NOT mean "no AgentResult". The CONTROLLER still produces
        exactly one terminal AgentResult, carrying BLOCKED and the blocking
        condition (§7.1.1, §10.2).
FROZEN: BLOCKED describes the EXECUTION BODY, never the record. The record
        exists in all three outcomes.
```

```text
FROZEN: AI-08 v1 has no execution-level authorization, so no authorization
        refusal is an execution-level precondition. Guard authorizes tool
        INVOCATIONS, not executions (§12), and a refused invocation is a
        TOOL-level event (§11.2). This list is closed for v1: it contains no
        authorization member, and AI-08-B MUST NOT add one.
```

### 11.2 Tool-level BLOCKED is not execution-level BLOCKED — FROZEN

```text
ToolOutcome.BLOCKED   ≠   AgentExecutionOutcome.BLOCKED
```

```text
FROZEN: a tool invocation that Guard BLOCKs does NOT automatically rewrite the
        whole Agent execution as execution-level BLOCKED.
FROZEN: a tool-level refusal is recorded AT THE TOOL LEVEL, in the tool
        invocation's own result, where AI-06 already records it correctly.
FROZEN: the Agent execution's own outcome is then determined by what the
        execution actually did — it started, so it is COMPLETED or FAILED, not
        BLOCKED.
FROZEN: no path converts one tool invocation's refusal into an execution-level
        BLOCKED, and no path converts it into a COMPLETED that hides it.
```

```text
An execution whose only tool call was refused by Guard still started and still
ran. It terminated in exactly one AgentResult saying so (§7.1.1). That is the
honest record, and it is what makes the two vocabularies worth keeping apart.
```

```text
FROZEN: a tool refusal means the execution BODY started, so the outcome is
        COMPLETED or FAILED — never BLOCKED, and never "no AgentResult". The
        refused invocation is visible in the AgentResult's tool_results, where
        AI-06's own ToolOutcome records it.
```

```text
FROZEN: Agent-level classification MUST NOT invent retry, cancellation, resume,
        fallback or escalation semantics. A refused tool call does not become a
        retryable state here. Those belong to AI-13 (§11.4).
```

### 11.3 What COMPLETED does not mean — FROZEN

```text
FROZEN: COMPLETED ≠ PASS
FROZEN: COMPLETED ≠ VERIFIED
FROZEN: COMPLETED ≠ CORRECT
FROZEN: COMPLETED ≠ task success

COMPLETED means one thing: an Agent execution reached a terminal result
representing a completed Agent execution.
It is a claim about the EXECUTION, never a claim about the research question.
```

```text
FROZEN: this applies to the RECORD as well as the outcome. That the controller
        produced a terminal AgentResult MUST NOT be read as "the Agent completed
        the task", and MUST NOT be read as a verdict on the task.
```

```text
The same limit applies to FAILED and BLOCKED from the other side: a FAILED or
BLOCKED record is a claim that the EXECUTION did not complete, never a claim
that the task is impossible or that the research question is answered.
```

`BLOCKED` appears in `GuardDecision`, in `StatusValue` and in `ToolOutcome` as well. That is the
same known cost AI-07 §10.1 recorded; AI-08 does not remove it by merging the types, and it does
not rename its own member to avoid the collision. §11.2 is how the collision is kept from becoming
a conflation.

### 11.4 No AI-12 / AI-13 vocabulary — FROZEN

v1 adds **no** member beyond these three:

```text
FORBIDDEN in AI-08 v1:  TIMED_OUT  CANCELLED  RETRYING  RETRIED  FALLBACK  ESCALATED
```

They belong to AI-13 (workflow) and AI-12 (routing v2). Adding one here would give one concept two
owners and would describe a mechanism this phase does not have.

---

## 12. Guard boundary — FROZEN

```text
FROZEN: AI-08 MUST NOT modify AI-04 and MUST NOT add a surface to Guard.
FROZEN: AI-08 MUST NOT cache, widen, reuse or pre-authorize any Guard decision.
FROZEN: AI-08 MUST NOT evaluate a policy itself, and MUST NOT wrap, extend,
        reimplement or shadow Guard.evaluate(request, policy).
```

Every Agent tool call MUST carry:

```text
ActorType.AGENT
Actor.id = the AgentId of the executing Agent
a FRESH GuardRequest
a FRESH GuardDecision
```

The existing rule applies unchanged: **one ALLOW authorizes one invocation.** A second invocation
asks again. There is no decision store, and AI-08 MUST NOT create one.

### 12.1 No agent-specific permission policy — FROZEN

The Discovery established this against the real code, and the conclusion is binding:

```text
Guard does not consult actor identity during evaluation.
Guard has no ActorType -> PermissionLevel mapping.
A Guard policy CANNOT match on actor: the closed field-ref set contains
action.permission_level and no actor field at all.
permission_level is supplied by the CALLER on the action, never inferred.
```

```text
FROZEN: AI-08 v1 does NOT provide, and MUST NOT claim, an Agent-specific
        permission policy or a per-Agent permission ceiling.
FORBIDDEN CLAIMS:
    "Codex automatically has a read-only ceiling"
    "DSH automatically has modify permission"
    "Guard distinguishes the two Agents for authorization"
```

What AI-08 **may** do, and what it is worth:

```text
ALLOWED   record that a tool call was made by dsh, and another by codex
ALLOWED   let the two Guard decisions differ, because their actor.id differs and
          actor.id is in the request_digest projection
NOT CLAIMED   that the difference is an authorization difference
```

#### 12.1.1 The per-Agent permission ceiling — DEFERRED / OUT OF SCOPE

This was recorded as `OPEN` at the AI-08-A freeze. **Amendment 1 closes it**, because an `OPEN`
that a later implementation phase could resolve on its own is an opening for AI-08-B to invent an
authorization design while implementing.

```text
FROZEN: AI-08 v1 does not ENFORCE a per-Agent permission ceiling.
FROZEN: AI-08 v1 does not CLAIM a per-Agent permission ceiling.
FROZEN: the ceiling is OUT OF SCOPE for AI-08, not a decision left to AI-08-B.

FROZEN: any future Agent-specific permission ceiling requires an explicit
        authorization design and a contract amendment first.
FROZEN: AI-08-B MUST NOT infer a ceiling from AgentId, from AgentRole, or from
        ActorType. None of the three is an authorization input.
FROZEN: no caller-side, convention-based, or "by construction" ceiling may be
        introduced in AI-08-B and described as an Agent-specific permission.
```

```text
An observable side-effect of §12 is NOT a policy. That two Guard decisions differ
because their actor.id differs is an attribution fact, and §12.1 already forbids
reading it as an authorization difference. Amendment 1 extends the same
prohibition to any per-Agent ceiling built on top of it.
```

---

## 13. Evidence boundary — FROZEN

### 13.1 AI-08 writes no EvidenceRecord in v1 — FROZEN

The brief for this phase proposed recording an AI-08 execution with `producer_type = service`,
`actor.type = agent` and `actor.id = dsh|codex`, and described that as already permitted by AI-05.
**The actor half is permitted. The producer half is not, and this contract does not pretend
otherwise.**

Measured against the frozen AI-05 contract:

```text
plugins/evidence/models.py:193-197
    g_registered(provenance.producer,
                 frozenset(row.producer for row in candidates), ...)

admitted_events_for(EvidenceKind.EXECUTION, None)   returns exactly ONE row:
    "AI-06 tool execution"   producer "ai-06"   producer_type service   actor_type agent
```

```text
FROZEN: the ONLY producer token admissible for an EXECUTION record in v1 is "ai-06".
FROZEN: AI-08 MUST NOT write an EvidenceRecord under the "ai-06" token.
        AI-08 is not AI-06. `producer` names the component that WROTE the record,
        and that claim would be false. A false producer is exactly the class of
        claim this repository refuses everywhere else.
FROZEN: AI-08 v1 therefore writes NO AI-05 EvidenceRecord of any kind.
        Its AgentResult is run data, and run data is disposable by design
        (docs/architecture/EVIDENCE_LIFECYCLE.md).
```

### 13.2 What is frozen for the day it is admissible

```text
FROZEN: when an AI-08 execution is recorded as Evidence, the shape is:
            producer_type = service
            actor.type    = agent
            actor.id      = the AgentId of the described execution (dsh | codex)
FROZEN: `producer` names the AI-08 execution component that WRITES the record.
        `actor`  names the Agent whose execution is DESCRIBED.
        These are different questions, and AI-05 §7 already separates them.
FROZEN: AI-08 MUST NOT modify AI-05's producer vocabulary, admission rules or
        ADMITTED_EVENTS registry. An added token is an AI-05 amendment, made by
        AI-05, under AI-05's amendment rule.
DEFERRED: the AI-08 producer token itself. Until AI-05 admits one, §13.1 stands.
```

### 13.3 AI-08 is not an adjudicator — FROZEN

```text
FROZEN: AI-08 MUST NOT create an Evidence truth layer, a verification layer, an
        adjudication layer or a promotion path of its own.
FROZEN: an AgentResult is a claim with producer/actor provenance. It is NOT a
        PASS, NOT VERIFIED, and NOT a truth verdict.
FROZEN: no path converts an AgentResult, or two AgentResults, into a PASS.
```

### 13.4 "Independent tool permission records" — what AI-08 actually provides

The roadmap requires *"独立工具权限记录"* — independent tool permission records. That requirement is
**satisfied in AI-08 v1**, and it is satisfied without any durable record and without touching
AI-05:

```text
SUPPLIED BY   a fresh GuardRequest and a fresh GuardDecision for EVERY tool
              invocation, per execution (§12, I5)
NOT REQUIRED  a durable AI-05 EvidenceRecord
```

```text
FROZEN: the roadmap's "independent tool permission records" means EXECUTION-LEVEL
        AUTHORIZATION RECORDS: each Agent's tool invocations carry their own
        Guard decision, made against their own request, with their own actor.id.
FROZEN: it does NOT mean a durable AI-05 EvidenceRecord, and AI-08 v1 MUST NOT
        be read as claiming one (§13.1).
FROZEN: the independence of these records is exactly I5 — fresh objects, fresh
        decisions, no reuse. It is not digest uniqueness (§9.1.1).
```

```text
This is why AI-08 v1 can satisfy the requirement while writing no Evidence at all,
and why it therefore does not conflict with AI-05 C-1: C-1 governs DURABLE
ADMISSION (§13.5), and §13.4 produces no durable record for C-1 to govern.
```

### 13.5 Deferred elsewhere — unchanged

```text
AI-05 C-1   published admission rule set          remains DEFERRED
AI-05 D11   retrieval shape, superseded_by query,
            promotion API, discard granularity    remains DEFERRED
AI-03 G-14  ContextRef derivation from AI-03      remains DEFERRED
```

```text
FROZEN: AI-08 does not resolve, reopen or depend on any of the three.
FROZEN: no document produced by AI-08 may read an ACCEPTED from admit() or
        admit_to_store() as a full §30 admission.
```

---

## 14. Cross-agent result sharing — FROZEN

```text
FROZEN: AI-08 v1 provides NO default cross-agent result injection.

    DSH result   ──X──> Codex, automatically
    Codex result ──X──> DSH, automatically
```

```text
FORBIDDEN in AI-08 v1:
    an automatic second-opinion loop
    an automatic cross-agent comparison
    majority vote, or any vote
    automatic escalation from one Agent to the other
    a shared mutable result pool
    any path that makes Result(D) an input to Input(C) or the reverse
```

This is the operational form of I3 (§9.1) and of the roadmap requirement *"不共享未验证的模型判断"*.

```text
DEFERRED to AI-10: cross-agent review, the second-opinion closure, result comparison,
                   and the human decision step.
FROZEN: AI-10's cross-agent review is a DIFFERENT execution mode. It MUST NOT be
        recorded, described or counted as satisfying I3.
```

---

## 15. Codex provider boundary — FROZEN

```text
OWNER: AI-09
```

AI-08 v1 MUST NOT implement any of:

```text
OpenAI-compatible API integration
any domestic provider integration
a Codex model profile
a live network call
a tool-calling compatibility matrix
a structured-output provider test
```

AI-08-B defines the interface **shape** only:

```text
Codex Agent
    |
    v
Agent execution interface          AI-08 owns this contract
    |
    v
provider / model backend           AI-09 wires a real one
```

```text
FROZEN: AI-08 MUST NOT make a network call, and MUST NOT import an HTTP client.
FROZEN: AI-08 v1 has no provider binding and no model binding.
        Every capability on every shipped model profile is UNKNOWN and no provider
        call has ever been made in this repository; AI-08 does not change that.
DEFERRED: all real Codex provider and model wiring. AI-09.
```

---

## 16. Relations to the other phases

```text
AI-00   architecture freeze            consumed; adds the Agent roles and §13 (§3, §8.2)
AI-01   DSH baseline                   not modified; DSH remains an external platform
AI-02   provider / model layer         consumed by AI-09, not by AI-08 v1 (§15)
AI-03   Context plugin                 consumed unchanged; not modified (§8)
AI-04   Guard plugin                   consumed unchanged; not modified (§12)
AI-05   Evidence plugin                not modified; AI-08 writes nothing in v1 (§13)
AI-06   Security tools plugin          the tool execution path AI-08 invokes (§12)
AI-07   Model Router                   not modified; hint stays a hint (§6)
AI-09   domestic models for Codex      owns all provider/model wiring (§15)
AI-10   cross-agent review             owns comparison and the second-opinion closure (§14)
AI-11   benchmark                      consumes per-Agent results later
AI-12   routing v2                     owns fallback and escalation (§11)
AI-13   long-running workflows         owns retry, timeout, cancellation,
                                       checkpoint, resume, failure classification (§11)
AI-14   long-term workbench            the multi-Agent end state
```

---

## 17. Repository layout — FROZEN

```text
agents/                      AI-08's home. A CORE layer, reached as a namespace
                             package relative to the repository root, exactly as
                             routing/ and tests/ already are.
agents/dsh/                  role directory. AI-08-A adds no code to it.
agents/codex/                role directory. AI-08-A adds no code to it.
```

```text
FROZEN: AI-08's home is agents/.
FROZEN: plugins/agent/ and plugins/codex/ MUST NOT exist. AI-08 is a core layer
        and not a plugin layer; plugins/ holds exactly four layers, owned by
        AI-03, AI-04, AI-05 and AI-06.
FROZEN: AI-08 MUST NOT add a fifth plugin layer.
FROZEN: AI-08 MUST NOT put Agent execution inside routing/. The Router selects;
        AI-08 executes.
FROZEN: AI-08 MUST NOT add tests under tests/routing/.
```

AI-08-B's expected new locations, for the avoidance of a late discovery:

```text
agents/                      the Agent identity, execution, result and independence code
tests/agents/                AI-08's tests, all marked layer 1 (offline, no transport)
scripts/ci/layer0_policy.py  the AI-08 structural and behavioural gate, on the pattern
                             check_ai07_router_contract already established
```

**AI-08-A creates none of these.** This section records the target so that AI-08-B does not have to
choose a layout while implementing.

### 17.1 Test maintenance required by AI-08-A — FROZEN

Two AI-07 tests encode assertions that AI-08 supersedes. Both are maintained here, deliberately and
minimally. **Neither change alters an AI-07 implementation file, and the AI-07 contract blob is not
touched.**

```text
(a) tests/routing/test_router.py — TestT37Regression

    AI-07 wrote it to prove its OWN diff did not touch the earlier layers. As a
    permanent repository test it compares `main...HEAD`, which is the CURRENT
    branch's diff — so from AI-07's merge onward it constrains every later phase,
    and it would fail on the first branch that legitimately adds code under
    agents/.

    MAINTAINED: the earlier-phase boundaries are kept — providers/, plugins/ and
    tools/ remain protected. `agents/` is removed from the protected set, because
    agents/ entered AI-08 ownership at AI-08-A.
    NOT CHANGED: routing/ is NOT added to the protected set.
    NOT CHANGED: no other protection semantics.

(b) tests/routing/test_router.py — TestT29IndependenceIsARequirement

    AI-07 asserted `agents/codex/adapter.py` does not exist. That froze a PATH,
    not a boundary, and AI-08-A supersedes it.

    MAINTAINED: replaced by an assertion that AI-08's boundary still holds — the
    Agent layer is a core layer at agents/, and is not a plugin package. This is
    the same shape as AI-07's own `plugins/router/` assertion and it survives
    AI-08-B's implementation, which the absence assertion could not.
```

---

## 18. Contract amendment rule

A frozen rule changes only through an explicit amendment recorded in §22.

An amendment is REQUIRED for any new or changed:

```text
an AgentId member (§5.1)                an AgentRole member (§5.2)
the registration table (§5.4)           the AgentExecutionRequest shape (§7.3)
the ExecutionId rules (§7.2)            any independence condition I1–I8 (§9.1)
an AgentExecutionOutcome member (§11)   the AgentResult shape (§10)
the Guard boundary (§12)                the Evidence boundary (§13)
the cross-agent sharing rule (§14)      the repository layout (§17)
```

```text
FORBIDDEN:
    a hint read as an identity to make an execution possible
    an unregistered token accepted so that something has an Agent
    a second execution relabelled as a retry
    an AgentResult recorded as a PASS
    two agreeing AgentResults recorded as verification
    a Guard decision reused across invocations or across Agents
    an EvidenceRecord written under a producer token that did not write it
    an AI-08 change to AI-03, AI-04, AI-05 or AI-07
```

---

## 19. Test Matrix

Layers 1 only. **AI-08 adds no layer 4** — v1 reaches no network and starts no process (§15).

| # | Test | Section | Asserts |
| --- | --- | --- | --- |
| T1 | AgentId is closed | §5.1 | exactly two members; `agent`/`service`/`human` are not members |
| T2 | an unknown agent is refused | §5.1, §6.2 | `resolve_agent("gpt")` refuses; no default agent |
| T3 | the registration is total | §5.2 | dsh→PRIMARY, codex→INDEPENDENT_SECOND, both directions |
| T4 | AgentRole is not ActorType | §5.3 | no member overlap; ActorType is imported, not redefined |
| T5 | identity is not discovered | §5.4 | no filesystem, environment or config read in the resolver |
| T6 | a hint is not an identity | §6.1 | a hint string that is not an AgentId does not resolve |
| T7 | a decision carries no result | §6.1 | RouterDecision carries no AgentResult and no finding |
| T8 | the Router does not execute | §6.3 | routing/ does not import agents/ |
| T9 | execution ids are unique | §7.2 | two executions differ — the control against a constant |
| T10 | ids are not inherited | §7.2 | no parent, no retry lineage, no reuse |
| T11 | the request is closed | §7.3 | unknown field refused; no credential, no tool argument |
| T12 | runtime input ≠ durable result | §7.4 | real task content may be input; it never reaches AgentResult |
| T13 | the request carries no context | §7.3 | a `ContextResponse` in the request is REFUSED, not ignored |
| T14 | context is execution-owned | §8.1 | the runtime establishes it; two executions, two ContextResponses |
| T15 | context is not shared | §8.2 | neither execution holds the other's context object or cache |
| T16 | I1 identity separation | §9.1 | distinct agent ids, both registered |
| T17 | I2 execution separation | §9.1 | distinct execution ids, neither derived |
| T18 | I3 input separation | §9.1 | neither result is the other's input, both directions |
| T19 | I4 context separation | §9.1, §8.1 | each execution established and owns its own context |
| T20 | I5 authorization separation | §9.1 | a fresh request and a fresh decision per invocation — NOT digest uniqueness |
| T21 | request_digest is not an identity | §9.1.1 | equal digests across executions are not a violation; no nonce is added |
| T22 | I6 result separation | §9.1 | two results, neither carrying the other |
| T23 | I7 failure separation | §9.1 | FAILED/BLOCKED never becomes the other's COMPLETED |
| T24 | I8 provenance separation | §9.1 | each result names its own agent and execution |
| T25 | independence is not a verdict | §9.2 | the predicate returns a finding, never PASS/VERIFIED |
| T26 | a role is not a finding | §5.2.1 | `INDEPENDENT_SECOND` alone never satisfies I1–I8 |
| T27 | the result is not a verdict | §10 | AgentResult carries no PASS, no VERIFIED, no success |
| T28 | attribution is two fields | §10.1 | `agent_id` + `execution_id`, and no fabricated producer field |
| T29 | the outcome vocabulary is three | §11 | exactly COMPLETED, FAILED, BLOCKED — no fourth member |
| T30 | BLOCKED is execution-level | §11.1 | BLOCKED means the execution BODY never started; a body that started is never BLOCKED |
| T31 | tool BLOCKED ≠ execution BLOCKED | §11.2 | a Guard-refused tool call does not rewrite the execution outcome; the body started, so the outcome is COMPLETED or FAILED |
| T32 | no AI-13 vocabulary leaked | §11.4 | no TIMED_OUT/CANCELLED/RETRYING/FALLBACK/ESCALATED |
| T33 | Guard is unchanged | §12 | no actor-keyed policy field; no second evaluator |
| T34 | no ceiling is claimed | §12.1.1 | no Agent-specific permission is enforced, claimed or inferred |
| T35 | no Evidence is written | §13.1 | AI-08 writes no EvidenceRecord under any token |
| T36 | permission records are execution-level | §13.4 | fresh Guard decisions satisfy the roadmap requirement; no durable record |
| T37 | no cross-agent injection | §14 | neither result reaches the other's input |
| T38 | no network, no subprocess | §15 | agents/ imports no HTTP client and spawns nothing |
| T39 | no provider binding | §15 | no model profile, no provider id, no endpoint |
| T40 | Layer 0 gate | §17 | the AI-08 gate exists and passes (AI-08-B) |
| T41 | the boundary holds | §17.1 | agents/ is a core layer and not a plugin package |
| T42 | **one terminal result, every outcome** | §7.1.1, §11 | **FAILED and BLOCKED executions still terminate in exactly ONE AgentResult; neither means "no AgentResult". The body not starting ≠ the record not existing.** |
| T43 | `result` is always present | §10.2 | present for all three outcomes; a FAILED/BLOCKED `result` refers to terminal failure/block metadata, never to a task result it does not have |

---

## 20. Exit Gates

AI-08 is complete only when every gate below passes.

| # | Gate | Condition |
| --- | --- | --- |
| C0 | Contract frozen | this document is frozen and its amendment log is open |
| C1 | Agent identity frozen | AgentId and AgentRole are closed, and the registration is total |
| C2 | Identity boundary verified | a hint never becomes an identity without `resolve_agent` |
| C3 | Execution contract verified | one request, one ExecutionId, one terminal result — for **all three** outcomes, with FAILED and BLOCKED still producing exactly one AgentResult |
| C4 | Context isolation verified | same workspace; the runtime establishes an execution-owned ContextResponse, and the request carries none |
| C5 | Independence verified | I1–I8 all hold, each with a direct assertion, and no digest-uniqueness requirement is asserted |
| C6 | Non-provability stated | no artifact claims independence is verification, and no role is read as a finding |
| C7 | Result boundary verified | `result` is present for every outcome and is never a task result that does not exist; AgentResult carries no verdict, no raw output, no credential, no fabricated producer field |
| C8 | Outcome vocabulary verified | exactly three members; BLOCKED is execution-level and means the body did not start, never "no AgentResult"; a tool refusal never rewrites it; no AI-12/AI-13 vocabulary |
| C9 | Guard boundary verified | no Guard change, fresh request and fresh decision per invocation, digest uniqueness neither required nor tested, no ceiling claimed or inferred |
| C10 | Evidence boundary verified | no AI-08 EvidenceRecord written; no AI-05 change; execution-level permission records present |
| C11 | Sharing prohibition verified | no cross-agent result injection exists |
| C12 | Provider boundary verified | no network, no subprocess, no provider or model binding |
| C13 | Layer 0 PASS | the AI-08 structural and behavioural check exists and passes |
| C14 | Full offline tests PASS | layers 1–3, with the counts recorded |
| C15 | Required CI PASS | CI green on the head the phase claims |
| C16 | Evidence artifact complete | `docs/AI-08_EVIDENCE_<date>.md` |
| C17 | Scope and diff audit clean | the diff is inside `agents/`, `tests/agents/`, docs, tests and the Layer 0 gate |

```text
C0 is satisfied by AI-08-A. C1–C17 are AI-08-B's.

AI-08-A closes C0 only. It MUST NOT be recorded as closing any other gate.
```

---

## 21. AI-08-B — Implementation Execution Brief

```text
branch      feature/ai-08-agent-implementation
base        the AI-08-A merge commit
deliverable AI-08-C is NOT created. AI-08 has exactly two sub-phases.
```

AI-08-B implements:

```text
the AgentId and AgentRole vocabularies, and the frozen registration table
the identity boundary: resolve_agent, refusing everything unregistered
the execution contract: AgentExecutionRequest, ExecutionId, the execution instance
Context acquisition: the RUNTIME establishes exactly one execution-owned
  ContextResponse per execution, from that execution's workspace and task.
  The request carries none, and none is passed in (§7.3, §8.1).
AgentResult, and AgentExecutionOutcome
the independence predicate over I1–I8
the Guard call path: one fresh request and one fresh decision per tool invocation
the Layer 0 AI-08 gate
tests/agents/, layer 1, covering T1–T43
```

AI-08-B MUST NOT:

```text
write an EvidenceRecord                      (§13.1)
modify AI-03, AI-04, AI-05 or AI-07          (§16)
add a provider, a model profile or a network call (§15)
add a retry, timeout or cancellation mechanism    (§11.4)
add cross-agent comparison or injection           (§14)
enforce, claim or infer an Agent-specific
  permission ceiling from AgentId, AgentRole
  or ActorType                                    (§12.1.1)
carry a ContextResponse in AgentExecutionRequest  (§7.3)
add a nonce, counter or random field so that a
  Guard request digest becomes unique             (§9.1.1)
rewrite an execution outcome because one tool
  invocation was refused                          (§11.2)
```

---

## 22. Amendment log

```text
AI-08-A   FROZEN    no amendments
```

### Amendment 1 — AI-08-A review corrections

```text
AI-08-A Amendment 1   FROZEN    written before AI-08-B began
base                  main @ a7c4a1e2536536940d96431883dadb592f7c151a
PR                    #51, the same contract-freeze PR
```

Six corrections, all found by review of the initial freeze. **Every one is a clarification or a
relaxation. None widens AI-08's authority, adds a capability, or changes any boundary shared with
AI-03, AI-04, AI-05, AI-06 or AI-07.**

```text
1  ContextResponse ownership                              §7.1, §7.3, §8.1, §8.2, §9 I4, §21, T13–T15, T19
   The freeze listed `context` as a REQUIRED AgentExecutionRequest field while
   also freezing that each execution establishes its OWN ContextResponse. Two
   competing semantics cannot both hold. RESOLVED: the request does not carry a
   ContextResponse; the execution runtime establishes exactly one and the
   execution owns it. A context descriptor/reference may be passed instead.

2  Guard digest uniqueness                                §9.1 I5, §9.1.1 (new), T20, T21, C5, C9
   I5 required that no `request_digest` be reused across executions. That is not
   something AI-08 can require, and asserting it would have invited a nonce or a
   Guard change to satisfy a requirement that does not exist. RESOLVED: I5 is
   about fresh OBJECTS and a fresh DECISION, not distinct digest VALUES.
   request_digest is not an identity and is not required to be unique.

3  BLOCKED semantics                                      §11.1, §11.2 (new), §11.4, T29–T32, C8
   `BLOCKED` was defined as "a condition prevented execution, so nothing ran",
   which left a Guard-refused TOOL call able to rewrite a whole Agent execution
   as BLOCKED. RESOLVED: BLOCKED is EXECUTION-LEVEL and means the execution never
   started; a tool-level refusal is recorded at the tool level and never
   rewrites the execution outcome. ToolOutcome.BLOCKED ≠
   AgentExecutionOutcome.BLOCKED.

4  Per-Agent permission ceiling                           §12.1.1 (new), T34, C9
   Recorded as OPEN at the freeze, with "default: not enforced". An OPEN that
   AI-08-B could resolve while implementing is an opening to invent an
   authorization design. RESOLVED: DEFERRED / OUT OF SCOPE. AI-08-B MUST NOT
   infer a ceiling from AgentId, AgentRole or ActorType.

5  AgentRole is not an independence finding               §5.2.1 (new), T26, C6
   `AgentRole.INDEPENDENT_SECOND` names an architectural role and could be
   misread as establishing independence. RESOLVED: the role alone never
   satisfies I1–I8 and is never proof of structural independence, which is a
   property of an execution PAIR only. The vocabulary is unchanged.

6  AgentResult producer wording                           §10.1 (new), §13.4 (new), T28, T36, C7, C10
   "a claim with a producer" in §10 and §13.3 read as though AgentResult carried
   an AI-05 producer field, which it does not: in v1 it is run data. RESOLVED:
   attribution is `agent_id` + `execution_id`, and no producer field exists.
   Where a future AI-05 amendment admits an AI-08 record, producer is the
   writing COMPONENT and actor is the described AGENT — producer != actor.
   §13.4 additionally records that the roadmap's "independent tool permission
   records" are satisfied by fresh GuardRequest + GuardDecision per invocation
   (execution-level), not by a durable EvidenceRecord — which is why AI-08 v1
   satisfies that requirement without conflicting with AI-05 C-1.
```

```text
EXPLICITLY NOT CHANGED by Amendment 1:
    any AgentId, AgentRole or AgentExecutionOutcome member
    the registration table (dsh -> PRIMARY, codex -> INDEPENDENT_SECOND)
    I1, I2, I3, I6, I7, I8
    the Guard boundary (§12): Guard is not modified, and not required to change
    the Evidence boundary (§13.1): AI-08 still writes no EvidenceRecord in v1
    the cross-agent sharing prohibition (§14)
    the Codex provider boundary (§15)
    the AI-07 contract, and any AI-03/AI-04/AI-05/AI-06 implementation
```

### Amendment 2 — the terminal-result invariant

```text
AI-08-A Amendment 2   FROZEN    written before AI-08-B began
base                  main @ a7c4a1e2536536940d96431883dadb592f7c151a
PR                    #51, the same contract-freeze PR
```

One correction. It was the only blocking contradiction left in the contract.

```text
1  The terminal-result invariant, for every outcome
   §7.1.1 (new), §10 (result field + §10.2 new), §11, §11.1, §11.2, §11.3 (new),
   §11.4 (renumbered from §11.3), T29–T31, T42, T43, C3, C7, C8

   §7.1 froze "every execution produces EXACTLY ONE terminal AgentResult",
   while §11 defined FAILED as "the execution STARTED but could not reach a
   valid terminal AgentResult". Read literally, FAILED was an outcome with no
   result — a direct contradiction of §7.1, and one that would have left
   AI-08-B to decide the invariant's scope while implementing.

   RESOLVED: the invariant holds for ALL THREE outcomes. The execution
   CONTROLLER / RUNTIME produces the terminal AgentResult, whether or not the
   Agent execution BODY ran.

       Agent execution body did not start
           ≠
       no AgentResult exists

   COMPLETED  the execution reached a terminal AgentResult representing a
              completed Agent execution
   FAILED     the body STARTED but failed to produce a valid task result; the
              runtime STILL produces exactly one terminal AgentResult
              describing the failure
   BLOCKED    an execution-level precondition prevented the body from STARTING;
              the controller STILL produces exactly one terminal AgentResult
              describing the blocking condition

   `result` is correspondingly ALWAYS present (§10.2): a task result for
   COMPLETED, and the terminal failure or block metadata for FAILED and
   BLOCKED. A FAILED or BLOCKED result is not required to carry a task result
   and MUST NOT be read as implying one exists.
```

```text
ALSO IN AMENDMENT 2, a precision fix in the same area:

   §11.1 previously listed "an authorization that refuses the execution itself"
   as an execution-level precondition. AI-08 v1 has no execution-level
   authorization — Guard authorizes tool INVOCATIONS, not executions (§12), and
   §12.1.1 states there is no Agent-specific permission policy at all. The
   precondition list is now closed and contains no authorization member, so
   AI-08-B cannot read an execution-level authorization into existence.

   §11.3 was renumbered to §11.4 to make room for the COMPLETED non-claims as
   §11.3. All references were updated.
```

```text
EXPLICITLY NOT CHANGED by Amendment 2:
    any AgentId, AgentRole or AgentExecutionOutcome member — still exactly three
    COMPLETED ≠ PASS / VERIFIED / CORRECT / task success
    ToolOutcome.BLOCKED ≠ AgentExecutionOutcome.BLOCKED
    a Guard-refused tool call still never rewrites the execution outcome
    no retry / cancel / resume / fallback / escalation — AI-13's, unchanged
    the Guard boundary, the Evidence boundary, the cross-agent sharing
      prohibition, the Codex provider boundary
    the AI-07 contract, and any AI-03/AI-04/AI-05/AI-06 implementation
```

An amendment is required before any frozen rule above changes.

---

## 23. Freeze record

```text
AI-08-A   FROZEN    this document
AI-08-A   Amendment 1 applied before AI-08-B began (§22)
AI-08-A   Amendment 2 applied before AI-08-B began (§22)
base      main @ a7c4a1e2536536940d96431883dadb592f7c151a
date      2026-10-01

Frozen here:
    the core-agent-layer identity, and that AI-08 is not a plugin, a provider,
      a model profile or a DSH child process
    AgentId, a closed two-member vocabulary, and that a free string is never
      a trusted identity
    AgentRole, a closed two-member vocabulary, and the fixed registration
    that a role is NOT an independence finding (Amendment 1)
    the three distinct questions: ActorType / AgentId / AgentRole
    that identity is registered, never discovered
    the Router boundary: a hint stays a hint, and resolve_agent is the only
      way a candidate becomes an identity
    the execution contract: one request, one ExecutionId, one terminal result —
      for ALL THREE outcomes. FAILED and BLOCKED still terminate in exactly one
      AgentResult; the body not starting does not mean the record does not exist
      (Amendment 2)
    that the request carries no ContextResponse, and that the runtime
      establishes one execution-owned ContextResponse (Amendment 1)
    that `result` is always present, and for FAILED/BLOCKED refers to terminal
      failure or block metadata rather than a task result (Amendment 2)
    that runtime input may carry task content and durable records may not
    Context isolation: same workspace, per-execution ContextResponse
    the independence definition I1–I8, with I3 as the key v1 boundary
    that I5 is fresh objects and a fresh decision, NOT digest uniqueness
      (Amendment 1)
    what independence cannot prove, and that it is never a verdict
    AgentResult, its two attribution fields, and that it is a claim with a
      producer and not a PASS
    AgentExecutionOutcome: three members; BLOCKED is execution-level and a
      tool refusal never rewrites it (Amendment 1); and each of the three still
      produces exactly one terminal AgentResult (Amendment 2)
    the Guard boundary: unchanged, fresh decision per invocation, and no
      Agent-specific permission policy claimed or inferred
    the Evidence boundary: AI-08 writes no EvidenceRecord in v1, and why
    that execution-level permission records satisfy the roadmap requirement
      without a durable record (Amendment 1)
    the cross-agent result sharing prohibition
    the Codex provider boundary, deferred whole to AI-09
    the repository layout, and the two AI-07 test assertions maintained here

Not decided here:
    the AI-08 producer token for Evidence                             DEFERRED,
      and an AI-05 amendment is required before it exists (§13.2)
    the AI-08 Layer 0 gate implementation                             AI-08-B (§17)
    the exact module split inside agents/                             AI-08-B,
      within the layout frozen at §17
    how a second opinion is actually closed                           AI-10
    whether Codex may use a different provider family                 AI-09

Closed by Amendment 1, previously OPEN:
    a per-Agent permission ceiling        DEFERRED / OUT OF SCOPE (§12.1.1).
                                          AI-08-B MUST NOT infer one.
```

```text
This document freezes a contract. No Agent exists, no execution has run, no Codex
backend is wired, and this document is not evidence that any of it works.
```

```text
AI-08-A  IMPLEMENTATION = NOT STARTED
```
