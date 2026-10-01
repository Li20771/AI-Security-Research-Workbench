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
an ExecutionId                      §7.2
an AgentId                          §5.1
a workspace identity                §8
a declared input descriptor         §7.3
a ContextResponse for this execution §8
zero or more tool invocations       §12
one terminal AgentResult            §10
```

```text
FROZEN: an execution produces EXACTLY ONE terminal AgentResult.
        There is no partial result, no intermediate result and no second one.
FROZEN: zero tool invocations is a valid execution. An execution that answered
        from context alone is complete, not incomplete.
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

The minimum an execution needs. It carries **no** credential, **no** tool argument and **no** Guard
decision.

```text
agent_id            an AgentId (§5.1)
workspace           a workspace identity, the same scope AI-03 and AI-04 use
task                a task descriptor or task reference
context             the ContextResponse for this execution (§8)
input               a declared input descriptor: a digest, or a reference to
                    bytes AI-08 does not itself store
```

```text
FROZEN: every field above is REQUIRED. An execution with no declared input is not
        an execution this contract produces.
FROZEN: the request carries no api_key, no token, no credential, no secret, no
        header and no authorization value. A field nobody defined is a field a
        credential can ride in on — the rule AI-04 §4 and AI-07 §5.3 already state
        for their own boundaries.
FROZEN: an unknown field is REFUSED, not ignored.
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

What is isolated, and what is not:

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
    each execution has its own ContextResponse (§8), and neither execution's
    context object is the other's.

I5  Tool authorization separation
    every tool invocation carries a FRESH GuardRequest and a FRESH GuardDecision.
    No GuardDecision, and no request_digest, is reused across executions.

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
result              an output reference or a digest — not the raw output
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
COMPLETED   the Agent execution produced a result.
FAILED      the execution started and did not produce a valid terminal result.
BLOCKED     a required execution, authorization or environment condition
            prevented execution, so nothing ran.
```

```text
FROZEN: COMPLETED ≠ PASS
FROZEN: COMPLETED ≠ VERIFIED
FROZEN: COMPLETED ≠ CORRECT
FROZEN: COMPLETED ≠ task success

COMPLETED means one thing: an Agent execution reached a terminal result.
It is a claim about the EXECUTION, never a claim about the research question.
```

`BLOCKED` appears in `GuardDecision`, in `StatusValue` and in `ToolOutcome` as well. That is the
same known cost AI-07 §10.1 recorded; AI-08 does not remove it by merging the types, and it does
not rename its own member to avoid the collision.

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

```text
OPEN: whether a per-Agent permission CEILING is enforced caller-side and recorded,
      or deferred to AI-09 / AI-10. Default recorded: NOT enforced in v1, and NOT
      claimed. A caller-side ceiling would be a convention in the request AI-08
      builds, not a Guard feature, and it MUST NOT be described as one.
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

### 13.4 Deferred elsewhere — unchanged

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
| T13 | context is per-execution | §8 | two executions, two ContextResponses, same workspace |
| T14 | context is not shared | §8 | neither execution holds the other's context object |
| T15 | I1 identity separation | §9.1 | distinct agent ids, both registered |
| T16 | I2 execution separation | §9.1 | distinct execution ids, neither derived |
| T17 | I3 input separation | §9.1 | neither result is the other's input, both directions |
| T18 | I4 context separation | §9.1 | distinct context per execution |
| T19 | I5 authorization separation | §9.1 | fresh request and fresh decision per invocation |
| T20 | I6 result separation | §9.1 | two results, neither carrying the other |
| T21 | I7 failure separation | §9.1 | FAILED/BLOCKED never becomes the other's COMPLETED |
| T22 | I8 provenance separation | §9.1 | each result names its own agent and execution |
| T23 | independence is not a verdict | §9.2 | the predicate returns a finding, never PASS/VERIFIED |
| T24 | the result is not a verdict | §10 | AgentResult carries no PASS, no VERIFIED, no success |
| T25 | the outcome vocabulary is three | §11 | exactly COMPLETED, FAILED, BLOCKED |
| T26 | no AI-13 vocabulary leaked | §11 | no TIMED_OUT/CANCELLED/RETRYING/FALLBACK/ESCALATED |
| T27 | Guard is unchanged | §12 | no actor-keyed policy field; no second evaluator |
| T28 | no ceiling is claimed | §12.1 | no document or code claims an Agent-specific permission |
| T29 | no Evidence is written | §13.1 | AI-08 writes no EvidenceRecord under any token |
| T30 | no cross-agent injection | §14 | neither result reaches the other's input |
| T31 | no network, no subprocess | §15 | agents/ imports no HTTP client and spawns nothing |
| T32 | no provider binding | §15 | no model profile, no provider id, no endpoint |
| T33 | Layer 0 gate | §17 | the AI-08 gate exists and passes (AI-08-B) |
| T34 | the boundary holds | §17.1 | agents/ is a core layer and not a plugin package |

---

## 20. Exit Gates

AI-08 is complete only when every gate below passes.

| # | Gate | Condition |
| --- | --- | --- |
| C0 | Contract frozen | this document is frozen and its amendment log is open |
| C1 | Agent identity frozen | AgentId and AgentRole are closed, and the registration is total |
| C2 | Identity boundary verified | a hint never becomes an identity without `resolve_agent` |
| C3 | Execution contract verified | one request, one ExecutionId, one terminal result |
| C4 | Context isolation verified | same workspace, per-execution ContextResponse |
| C5 | Independence verified | I1–I8 all hold, and each has a direct assertion |
| C6 | Non-provability stated | no artifact claims independence is verification |
| C7 | Result boundary verified | AgentResult carries no verdict, no raw output, no credential |
| C8 | Outcome vocabulary verified | exactly three members; no AI-12/AI-13 vocabulary |
| C9 | Guard boundary verified | no Guard change, fresh decision per invocation, no ceiling claimed |
| C10 | Evidence boundary verified | no AI-08 EvidenceRecord written; no AI-05 change |
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
Context acquisition: one ContextResponse per execution, same workspace
AgentResult, and AgentExecutionOutcome
the independence predicate over I1–I8
the Guard call path: one fresh request and one fresh decision per tool invocation
the Layer 0 AI-08 gate
tests/agents/, layer 1, covering T1–T34
```

AI-08-B MUST NOT:

```text
write an EvidenceRecord                      (§13.1)
modify AI-03, AI-04, AI-05 or AI-07          (§16)
add a provider, a model profile or a network call (§15)
add a retry, timeout or cancellation mechanism    (§11)
add cross-agent comparison or injection           (§14)
claim an Agent-specific permission ceiling        (§12.1)
```

---

## 22. Amendment log

```text
AI-08-A   FROZEN    no amendments
```

An amendment is required before any frozen rule above changes. One has not been written.

---

## 23. Freeze record

```text
AI-08-A   FROZEN    this document
base      main @ a7c4a1e2536536940d96431883dadb592f7c151a
date      2026-10-01

Frozen here:
    the core-agent-layer identity, and that AI-08 is not a plugin, a provider,
      a model profile or a DSH child process
    AgentId, a closed two-member vocabulary, and that a free string is never
      a trusted identity
    AgentRole, a closed two-member vocabulary, and the fixed registration
    the three distinct questions: ActorType / AgentId / AgentRole
    that identity is registered, never discovered
    the Router boundary: a hint stays a hint, and resolve_agent is the only
      way a candidate becomes an identity
    the execution contract: one request, one ExecutionId, one terminal result
    that runtime input may carry task content and durable records may not
    Context isolation: same workspace, per-execution ContextResponse
    the independence definition I1–I8, with I3 as the key v1 boundary
    what independence cannot prove, and that it is never a verdict
    AgentResult, and that it is a claim with a producer and not a PASS
    AgentExecutionOutcome: three members, and no AI-12/AI-13 vocabulary
    the Guard boundary: unchanged, fresh decision per invocation, and no
      Agent-specific permission policy claimed
    the Evidence boundary: AI-08 writes no EvidenceRecord in v1, and why
    the cross-agent result sharing prohibition
    the Codex provider boundary, deferred whole to AI-09
    the repository layout, and the two AI-07 test assertions maintained here

Not decided here:
    whether a per-Agent permission ceiling is enforced caller-side   OPEN,
      default recorded as not enforced and not claimed (§12.1)
    the AI-08 producer token for Evidence                             DEFERRED,
      and an AI-05 amendment is required before it exists (§13.2)
    the AI-08 Layer 0 gate implementation                             AI-08-B (§17)
    the exact module split inside agents/                             AI-08-B,
      within the layout frozen at §17
    how a second opinion is actually closed                           AI-10
    whether Codex may use a different provider family                 AI-09
```

```text
This document freezes a contract. No Agent exists, no execution has run, no Codex
backend is wired, and this document is not evidence that any of it works.
```

```text
AI-08-A  IMPLEMENTATION = NOT STARTED
```
