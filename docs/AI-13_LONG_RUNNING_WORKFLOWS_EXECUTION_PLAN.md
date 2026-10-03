# AI-13 — Long-running Workflows — Execution Plan

> Status: **DRAFT — FREEZE PROPOSAL** (AI-13-A, 2026-10-03)
> Phase: AI-13 — Long-running Workflows
> Sub-phase: **AI-13-A — Contract / Design Freeze**
> Base: `main` @ `2c23bab866ce20595fccfde2ff1f563ce0a07086`
> Rule: This document defines the contract. AI-13-B implements against it. Nothing in AI-13
> may deviate from a frozen contract without amending this document first (§20).

```text
THIS DOCUMENT IS NOT YET FROZEN.

The freeze act is human review followed by the merge of PR 1.
Until that merge, this is a proposal. C0 (§19) is NOT satisfied by this document's
existence — it is satisfied by its merge.

No code exists. No workflow has run. No checkpoint exists.
```

---

## 0. The one idea — read this first

```text
declared bounds
  + disposable state
  + a fresh authorization per attempt
  =  a long-running task that cannot escalate
```

Everything below is a consequence of one refusal:

```text
FROZEN: a resumed attempt inherits DECLARED STATE and nothing else — no authorization,
        no approval, no context, no tool state.
```

```text
FROZEN: durable state is not authority.
FROZEN: retry is not escalation.
FROZEN: an attempt is authorized on its own, or it does not run.
FROZEN: AI-13 v1 has no unbounded execution — every bound is DECLARED, and reaching one
        is a terminal state rather than a silent stop.
```

AI-13 exists so a task can outlive one execution without any of the mechanisms that make
long-running systems unsafe: carried-over permissions, hidden retries, silent
escalation, and state that is durable in fact and unaccountable in practice.

---

## 1. Purpose

Four phases deferred work to AI-13 **by name**. This contract picks it up:

```text
AI-08 §7.2   "AI-08 v1 has no parent-execution relationship, no retry lineage and no
             resumption lineage. A second attempt is a SECOND EXECUTION with its own
             ExecutionId — a distinct record, not a retry state. Retry, resume and
             failure classification belong to AI-13."
AI-08 §11.4  "Agent-level classification MUST NOT invent retry, cancellation, resume,
             fallback or escalation semantics."
AI-08 T32    the vocabulary TIMED_OUT / CANCELLED / RETRYING / RETRIED / FALLBACK /
             ESCALATED is FORBIDDEN in AI-08 because it belongs to AI-13.
AI-02 §5.11  "max_retries is frozen as a field but must default to 0 in AI-02. Retry
             policy is AI-13's problem."
AI-02 §9.1   "attempts | per call; retry_count is reserved for AI-13 and is 0 in AI-02".
AI-10 §5.3   "resume of a closed case is not a transition; it is AI-13's boundary and
             does not exist in v1."
```

`workflows/` already exists as an empty scaffold with its own README and this phase's
name on it. Its principle is inherited, not invented:

```text
workflows/README.md   "Generated runs and checkpoints are disposable unless promoted
                       to Evidence."
```

AI-13 defines the workflow layer **above** the existing execution seams. It is not a
second execution engine, not a scheduler, and not a place where authorization happens.

---

## 2. Normative Language

```text
FROZEN      settled by this contract. AI-13-B MUST implement it. Changing it requires
            an amendment (§20).
PROPOSED    this contract's choice, made so AI-13-B does not have to choose while
            implementing. Normative for AI-13-B, and the class most likely to be
            amended.
DEFERRED    deliberately not done, with the reason recorded.
BLOCKED     cannot be done now, and the blocker is named.
OPEN        a question this contract does NOT answer. An OPEN item MUST NOT be closed
            by an implementation decision.
```

---

## 3. Scope

### 3.1 In scope for AI-13 v1

```text
the workflow definition and its identity
the step, attempt and checkpoint model
resume integrity rules
failure classification, retry and its bounds
timeout and cancellation semantics
resource limits
the human-approval point, and what it is NOT
auditability and provenance for a workflow run
```

### 3.2 Out of scope — FROZEN

```text
FROZEN: AI-13 v1 defines no distributed workflow engine, no cross-machine scheduler and
        no cloud orchestration.
FROZEN: AI-13 v1 defines no arbitrary DAG scheduler. A workflow is an ordered sequence
        of declared steps; a DAG engine needs a requirement this repository does not
        have, and a scheduler nobody asked for is the shape §16 forbids.
FROZEN: AI-13 v1 starts no background daemon and holds no execution open between
        process lifetimes. A run advances when something asks it to advance.
FROZEN: AI-13 v1 implements no provider, no Agent body, no tool and no transport. It
        composes the existing seams (§17).
FROZEN: AI-13 v1 writes no AI-05 EvidenceRecord (§13.5) and registers no producer.
FROZEN: AI-13 v1 executes no AI-12 policy, performs no model fallback, and selects no
        model (§10.4).
```

---

## 4. What AI-13 owns, and what it must not touch

```text
AI-04 Guard        permission authority. AI-13 asks it, per Guard-bound invocation,
                   exactly as AI-08 does. AI-13 does not evaluate policy, does not
                   issue approvals, does not cache or carry an ALLOW, and does not
                   widen anything Guard decided.
AI-05 Evidence     durable record ownership. AI-13 writes none, registers no producer
                   token, and does not reshape workflow state into a record.
AI-06 tools        the single tool-invocation path. AI-13 invokes nothing directly.
AI-07 Router       an independent decision per caller-submitted RouterRequest. AI-13
                   submits requests; it never reuses, stores or infers a decision.
AI-08 execution    the execution seam. An attempt IS an AI-08 execution (§6.3).
AI-09 providers    provider integration. AI-13 does not reach a provider.
AI-10 review       review and human-decision material. AI-13's approval point is a
                   different thing with a different subject (§13.6).
AI-11 benchmark    measurement. AI-13 changes no corpus, no oracle and no material.
AI-12 policy       declaration. AI-13 executes none of it (§10.4).
SecurityLab        an independent research project. Never modified.
```

```text
FROZEN: AI-13 owns WORKFLOW EXECUTION STATE — what a run has done, what it may do next,
        and within which declared bounds. It owns no authority, no record and no
        decision that another phase already owns.
```

---

## 5. Workflow identity — FROZEN

```text
WorkflowDefinition   a TRACKED artifact under workflows/definitions/, reviewed and
                     versioned in Git. Never generated, never fetched, never
                     discovered at runtime.
WorkflowId           stable across revisions.
Revision             a string, recorded on every run.
DefinitionDigest     a digest over the definition's canonical bytes.
WorkflowRunId        opaque, unique, never reused, and NEVER derived from another
                     run's id.
```

```text
FROZEN: a run binds to (workflow_id, revision, definition_digest) at creation, and
        those three are recorded on the run and on every checkpoint it writes.
FROZEN: a run MUST NOT resume under a different revision OR a different
        definition_digest. There is no migration, no rebase and no "close enough": a
        definition that changed may have changed what a completed step MEANT, and a
        resumed run whose earlier steps were interpreted by different rules is a run
        whose record cannot be read.
FROZEN: a revision mismatch is a TERMINAL state for the run, named
        `DEFINITION_CHANGED`, not a refusal that may be retried into agreement.
```

```text
FROZEN: a run records the WORKSPACE IDENTITY it started under, and resume requires the
        same workspace identity. The repository already treats a workspace identity as
        part of what a measurement means (AI-08 records it; AI-11 binds a manifest
        digest into a run); a workflow that resumed into a different tree would be
        continuing work in a place the earlier steps never saw.
FROZEN: where a run declares that its workspace is re-derived, the re-derivation is
        recorded with its own digest, and a mismatch is `WORKSPACE_CHANGED`.
```

---

## 6. The step and attempt model — FROZEN

### 6.1 Steps

```text
FROZEN: a workflow is an ORDERED SEQUENCE of declared steps. Order is part of the
        definition, not a runtime discovery.
FROZEN: a StepId is stable within a definition, and a step's identity is (workflow_id,
        revision, step_id).
FROZEN: a step declares what it does by naming an EXISTING seam — an Agent execution,
        a tool invocation through AI-06's path, or a declared wait on an approval. A
        step that names nothing AI-13 may call is not a step this contract admits.
```

### 6.2 What a step is not

```text
FROZEN: a step is not an authorization. A step that needs a Guard-bound invocation asks
        Guard for that invocation (§17.2), and a step's success is not a permission.
FROZEN: a step is not a place to hold state between attempts. That is the checkpoint's
        job, and the checkpoint carries declared state only (§7).
```

### 6.3 Attempts

```text
FROZEN: one attempt at one step IS one AI-08 execution, with its OWN ExecutionId,
        produced by AI-08's frozen entry point. AI-08 §7.2 states this and AI-13
        inherits it rather than restating a rival: "a second attempt is a SECOND
        EXECUTION with its own ExecutionId — a distinct record, not a retry state."
```

```text
AttemptId            AI-13's own identity for an attempt: (run_id, step_id, attempt_no).
attempt_no           starts at 1 and increases by exactly 1 per attempt at that step.
                     Never reused, never renumbered, never derived from an ExecutionId.
attempt.execution_id the ExecutionId the attempt produced. AI-13 records the REFERENCE;
                     it does not mint, reuse or interpret an ExecutionId.
```

```text
FROZEN: an attempt's identity and its execution's identity are different facts and both
        are recorded. A retry lineage is a sequence of AttemptIds, each pointing at a
        distinct ExecutionId — never one ExecutionId with a counter on it.
```

---

## 7. Checkpoints — FROZEN

### 7.1 What a checkpoint is

```text
FROZEN: a checkpoint is a durable-in-principle, DISPOSABLE record of what a run has
        completed and what it may do next. It is workflow execution state.
FROZEN: a checkpoint is IMMUTABLE. Resume appends a new checkpoint; it never edits one.
FROZEN: a checkpoint names (workflow_id, revision, definition_digest, run_id, step_id,
        attempt_no) and carries a digest of its own bytes. A checkpoint that cannot name
        all of those is not usable and MUST be refused rather than guessed at.
```

### 7.2 What a checkpoint MUST NOT contain

```text
FROZEN: no secret, credential, token or key.
FROZEN: no tool output, no model output, no prompt body, no completion body, no raw
        provider body, no repository file content, no diff body.
FROZEN: no authorization state — no GuardDecision, no ALLOW, no approval status, no
        decision id carried forward as if it still held (§8.2).
FROZEN: no AI-05 EvidenceRecord, and no field shaped like one.
```

```text
FROZEN: anything large or raw is stored OUTSIDE the checkpoint and referenced from it by
        reference and digest. workflows/runs/README.md already says this; AI-13 makes it
        a rule rather than advice.
```

### 7.3 Durability, and the relationship to AI-05

```text
FROZEN: a checkpoint's default is DISPOSABLE. Discarding checkpoints for a finished or
        abandoned run is normal and MUST be possible.
FROZEN: a checkpoint is NOT an AI-05 EvidenceRecord, MUST NOT be written as one, and
        MUST NOT be reshaped into one. AI-05 admits six events from six named producers;
        a workflow event is not among them, and AI-05 §22.2 REJECTS raw tool output
        outright — a checkpoint is not a way around a rule AI-05 owns.
FROZEN: promotion of workflow state into durable evidence is NOT an AI-13 operation. It
        would need an AI-05 amendment admitting a producer token, and AI-13 does not
        make one (§16).
```

---

## 8. Resume integrity — FROZEN

### 8.1 What resume requires

```text
FROZEN: resume requires ALL of, verified before an attempt is created:
            workflow_id and revision match
            definition_digest matches
            workspace identity matches, or a declared re-derivation matches
            the checkpoint's own digest is intact
FROZEN: any mismatch is a terminal state for the run, named for the mismatch
        (`DEFINITION_CHANGED`, `WORKSPACE_CHANGED`, `CHECKPOINT_CORRUPT`). None is
        retryable and none is repaired by choosing the closer of two values.
```

### 8.2 What resume inherits, and what it must not

```text
FROZEN: resume re-executes the interrupted step as a NEW attempt. A step is not resumed
        halfway: its declared state is "completed" or it runs again.
FROZEN: a new attempt inherits DECLARED STATE ONLY — which steps completed, their
        declared outcomes, and artifact references.
```

```text
FROZEN: a new attempt MUST NOT inherit, and the checkpoint MUST NOT carry:
            a Guard decision, an ALLOW, or any authorization
            an approval, or a scope an earlier approval covered
            a context payload or a context decision
            a tool gateway, tool state or a tool result
            a model selection, a candidate set or a RouterDecision
            a capability status or any relaxation of a requirement
```

```text
FROZEN: every Guard-bound invocation in a resumed attempt carries a FRESH GuardRequest
        and receives a FRESH GuardDecision. AI-08 §12 states the rule this inherits:
        "one ALLOW authorizes one Guard-bound invocation. A second invocation asks
        again. There is no decision store, and AI-08 MUST NOT create one." A checkpoint
        is not a decision store, and AI-13 MUST NOT create one either.
```

---

## 9. Failure classification — FROZEN

```text
FROZEN: AI-13 owns workflow failure CLASSIFICATION. This is the thing AI-08 §11.4
        refused to invent and named AI-13 as its owner.
```

AI-13's own vocabulary, closed:

```text
TERMINAL_FAILURE      the work failed and no declared policy permits another attempt
RETRYABLE_FAILURE     the work failed and a DECLARED policy permits another attempt
BLOCKED_PRECONDITION  a precondition prevented the step from starting at all
TIMED_OUT             a declared deadline expired
CANCELLED             a declared cancellation took effect
APPROVAL_DENIED       a human declined, or no approval arrived before its deadline
AUTHORIZATION_DENIED  Guard refused
RESOURCE_EXHAUSTED    a declared resource bound was reached
DEPENDENCY_FAILED     a declared dependency was absent or unreachable
```

```text
FROZEN: this vocabulary is AI-13's OWN TYPE. `BLOCKED_PRECONDITION` is not
        `GuardDecision.BLOCKED`, not `AgentExecutionOutcome.BLOCKED` and not
        `StatusValue.BLOCKED`; the repository already pays for one word in several
        vocabularies and does not merge the types to save the cost.
```

### 9.1 Retryability is an execution fact, not a reinterpretation

```text
FROZEN: retryability is a property of WORKFLOW EXECUTION POLICY over a classified
        failure. It is never a reinterpretation of an AI-05 verdict, an AI-11 verdict,
        a Guard decision or an Agent outcome.
FROZEN: a non-PASS verdict — BLOCKED, NOT_RUN, UNKNOWN, UNAVAILABLE — MUST NOT be
        converted into a retryable state, a success, or a failure by AI-13. Those words
        mean what their owning phase says they mean.
FROZEN: where a failure's class is not one this contract names, the classification is
        UNKNOWN and the ONLY permitted action is to stop. An unclassified failure MUST
        NOT be retried.
```

### 9.2 What is never retried — FROZEN

```text
FROZEN: AUTHORIZATION_DENIED is never retried automatically. A denial is an answer.
        Asking again without a change in the request is an attempt to have a boundary
        reconsider, and AI-13 does not build one.
FROZEN: APPROVAL_DENIED is never retried automatically (§13.4).
FROZEN: CANCELLED is never retried. Cancellation is a decision, not an accident.
FROZEN: a definition, workspace or checkpoint mismatch is never retried (§8.1).
FROZEN: RESOURCE_EXHAUSTED is never retried at the same bound. A retry that would exceed
        the declared bound is FORBIDDEN; the bound is what makes the run bounded.
```

---

## 10. Retry — FROZEN

### 10.1 The four things retry is not

```text
FROZEN: retry is NOT permission escalation.
FROZEN: retry is NOT candidate-set widening.
FROZEN: retry is NOT capability relaxation.
FROZEN: retry is NOT an automatic model fallback.
```

```text
FROZEN: an attempt's request is the request its definition declares. A retry MUST NOT
        change an actor, a permission level, a target, a capability requirement, a
        modality, an independence requirement, or any other declared constraint. A
        retry that would need a wider request is not a retry; it is a different task,
        and it needs its own definition and its own authorization.
```

### 10.2 Every attempt is authorized on its own

```text
FROZEN: the previous attempt's decision grants the next attempt NOTHING. There is no
        inheritance of authorization across attempts, and no object exists that could
        carry one (§8.2).
FROZEN: an attempt that needs routing submits a NEW RouterRequest, which AI-07 evaluates
        INDEPENDENTLY. AI-13 does not reuse, store or infer a RouterDecision, and does
        not treat a previous selection as a default.
```

### 10.3 Bounds

```text
FROZEN: a retry policy is DECLARED, tracked data under workflows/policies/. It names
        the failure classes it applies to and its own bounds.
FROZEN: a workflow that declares no retry policy has no retries. There is no default
        that retries, and no default that retries forever.
FROZEN: a retry policy MUST declare a maximum attempts bound AND a time bound. A policy
        with only one of the two is refused at validation: AI-02 already freezes the
        precedent that "timeout_total_ms is a hard deadline covering the whole call,
        including retries", and a bound that can be escaped by retrying slowly is not a
        bound.
FROZEN: a workflow therefore has a MAXIMUM total attempts figure, derived from its
        declared policy, and no execution path may exceed it.
```

### 10.4 AI-13 does not execute AI-12

```text
FROZEN: AI-12 declares fallback and escalation as POLICY DATA. It executes neither, and
        AI-13 MUST NOT become the executor AI-12 deliberately is not.
FROZEN: a workflow MUST NOT read an AI-12 policy to decide whether to retry, to choose a
        different model, or to escalate. AI-12's model-comparative prerequisite is
        BLOCKED and AI-13 does not satisfy it, does not work around it, and does not
        manufacture the measurement it needs.
```

---

## 11. Timeout and cancellation — FROZEN

### 11.1 Timeout

```text
FROZEN: every deadline is EXPLICIT and DECLARED. There is no default-infinite workflow
        and no default-infinite step. AI-02 froze the same rule for a request — "a
        timeout is always explicit. There is no unbounded or default-infinite request" —
        and AI-13 inherits it rather than restating a weaker one.
FROZEN: a workflow declares a maximum runtime; a step declares its own. A step's
        deadline that is not narrower than its workflow's is not a step deadline.
FROZEN: AI-13's step deadline COMPOSES WITH, and never replaces, the per-invocation
        `timeout_seconds` AI-06 already requires. A step deadline is an outer bound; it
        does not remove the inner one, and it does not make an inner one optional.
FROZEN: exceeding a deadline is TIMED_OUT, which is a DECLARED terminal state for the
        step. It is not FAILED, because "did not finish in time" and "finished wrongly"
        are different facts and a reader acts on them differently.
```

### 11.2 Cancellation

```text
FROZEN: cancellation is DECLARED and observed at declared points. AI-13 v1 cancels
        between attempts, never inside one: it holds no thread to interrupt and starts
        no process it would have to kill. What happens to an in-flight attempt is the
        attempt's own owner's business.
FROZEN: a cancelled run is terminal. `CANCELLED` is never retried (§9.2).
FROZEN: cancellation is not a failure of the work, and a run cancelled by a human MUST
        NOT be recorded as one. AI-13 records WHO cancelled and WHY as a declared
        reference, and does not adjudicate whether the reason was good.
```

---

## 12. Resource limits — FROZEN

Every workflow declares, in tracked policy:

```text
maximum workflow runtime
maximum step runtime
maximum attempts per step
maximum total attempts for the run
maximum checkpoint count or total checkpoint bytes per run
maximum artifact bytes referenced by a run
```

```text
FROZEN: these are DECLARED, not defaulted. A workflow that declares no limit is refused
        at validation; "no limit" and "a limit nobody wrote down" are the same thing at
        run time, and only one of them is honest.
FROZEN: reaching any limit is a TERMINAL state with its own name
        (`RESOURCE_EXHAUSTED`), and never a silent stop.
FROZEN: AI-13 v1 runs ONE step at a time. There is no concurrency, no parallelism and
        no worker pool, so there is no concurrency limit to declare. Adding one is a
        contract change (§20), not a configuration change.
FROZEN: AI-13 v1 holds no execution open between process lifetimes. A run advances when
        something asks it to; nothing wakes up on its own.
```

---

## 13. Human approval — FROZEN

### 13.1 What AI-13 defines

```text
FROZEN: AI-13 defines a WORKFLOW APPROVAL RECORD: an approval a HUMAN actor produced
        for one step of one run, recorded as workflow execution state.
FROZEN: it binds to (workflow_id, revision, definition_digest, run_id, step_id,
        attempt_no) through a scope digest. An approval that does not name all six is
        not an approval for anything and MUST be refused.
FROZEN: it records the human actor, a timestamp, the scope digest, and an artifact
        reference for whatever the human actually signed. The artifact's bytes are
        stored outside it (§7.2).
```

### 13.2 It is not inheritable

```text
FROZEN: an approval for one attempt authorizes THAT attempt. It does not carry to the
        next attempt, to the next step, or to a re-run. A retry does not inherit the
        approval that let the previous attempt start.
FROZEN: an old approval MUST NOT silently grant a new scope. A scope that differs in any
        of the six bound fields is a DIFFERENT scope, and the scope digest makes that
        mechanical rather than a matter of careful reading.
```

### 13.3 Self-approval is structurally impossible

```text
FROZEN: the approver is a HUMAN actor. An Agent MUST NOT approve, and a model MUST NOT
        approve — not through a tool, not through a body, not by emitting a record that
        looks like one.
FROZEN: the approver MUST NOT be the actor whose step is being approved. A workflow MUST
        NOT present an approval whose actor is the executing Agent, the run's own
        identity, or any service principal.
FROZEN: AI-13 v1 provides no mechanism by which an Agent, a model or a service can
        produce, synthesize or default an approval.
```

### 13.4 Rejection and deadline

```text
FROZEN: a denied approval is TERMINAL for that step (`APPROVAL_DENIED`) and is NEVER
        re-requested automatically. Re-asking a human who has answered is pressure, not
        process; a new request requires a new human act or a new run.
FROZEN: an approval that does not arrive before its declared deadline is
        `APPROVAL_DENIED`, not a silent wait. There is no open-ended pending state.
```

### 13.5 What the approval is NOT

```text
FROZEN: it is NOT an AI-05 EvidenceRecord, and it MUST NOT be written as one. AI-05 §6.3
        classifies a human approval as DECISION with actor.type = human and states that
        it is NOT REPRESENTABLE in v1: a record carrying `DECISION + actor.type = human`
        is REJECTED (§6.6), and no producer token exists for it. AI-13 does not make one.
FROZEN: it is NOT an AI-04 `ApprovalRef`, and AI-13 MUST NOT present it to Guard as a
        VERIFIED approval. AI-04 §8 says Guard "issues no approvals; it only consumes
        their state", D-12 places "approval issuance/verification outside AI-04", and
        §25.2 Q-3 leaves the computation and binding of `approval.scope_digest` to "a
        later phase". Claiming to be that phase is an AI-04 amendment, and AI-13-A does
        not make one.
FROZEN: AI-13 MUST NOT accept a caller-supplied boolean as an approval. AI-04 §8 already
        refuses `approved = true` as evidence of a human approval, and AI-13 does not
        reintroduce it under another name.
```

```text
CONSEQUENCE, stated rather than discovered later: a workflow approval opens a WORKFLOW
gate. A Guard-gated action remains independently BLOCKED, exactly as it is today,
because the source Guard would have to verify does not exist. The two gates are
different gates, and a workflow approval does not open Guard's.
```

### 13.6 It is not AI-10's decision

```text
FROZEN: AI-10 owns a human decision about REVIEW MATERIAL. AI-13's approval is about a
        WORKFLOW STEP. They are different subjects, they are different types, and AI-13
        MUST NOT reuse AI-10's vocabulary or feed an approval into a review case.
```

---

## 14. Vocabulary — AI-13's own, and the collisions it refuses

```text
WorkflowState       CREATED RUNNING AWAITING_APPROVAL COMPLETED FAILED BLOCKED
                    CANCELLED TIMED_OUT RESOURCE_EXHAUSTED DEFINITION_CHANGED
                    WORKSPACE_CHANGED CHECKPOINT_CORRUPT
StepState           PENDING READY RUNNING AWAITING_APPROVAL SUCCEEDED FAILED BLOCKED
                    SKIPPED CANCELLED TIMED_OUT
FailureClass        §9's nine members
AttemptOutcome      the terminal classification of one attempt
Terminal?           a property, not a member: every state above is either terminal or
                    has a declared transition out of it, and no state is both
```

```text
FROZEN: AI-13 MUST NOT add a member to another phase's vocabulary. In particular it
        MUST NOT add to GuardDecision (ALLOW/DENY/BLOCKED/UNKNOWN), to AI-04 §18.2's
        CheckResult (SATISFIED/REJECTED/UNAVAILABLE/INDETERMINATE), to AI-05's admission
        vocabulary (ACCEPTED/REJECTED/UNAVAILABLE), to StatusValue
        (PASS/FAIL/BLOCKED/NOT_RUN/UNKNOWN), to AgentExecutionOutcome
        (COMPLETED/FAILED/BLOCKED), or to AI-05's Evidence kinds and tiers
        (OBSERVATION/DECISION/EXECUTION, STAGED/PROMOTED).
FROZEN: AI-13 MUST NOT use AI-05's tier and operation words — STAGED, PROMOTED,
        discard, delete, mutate, supersede — for checkpoint semantics. Checkpoints have
        their own lifecycle and reusing another phase's words would make two different
        guarantees look like one.
FROZEN: `BLOCKED` appears in AI-13's vocabularies as its own type, as it already appears
        in several. The types are never merged and no value is ever passed between them
        without an explicit classification.
```

---

## 15. Auditability and provenance — FROZEN

```text
FROZEN: a workflow run produces a RUN RECORD that names, at minimum:
            workflow_id, revision, definition_digest
            run_id
            the workspace identity the run started under
            each step, its state, and each attempt with its own AttemptId and the
            ExecutionId that attempt produced
            the failure classification of every attempt that did not succeed
            every approval, by scope digest and artifact reference
            every bound the run declared, and which one it reached if it reached one
            a terminal state, or an explicit statement that the run is not terminal
FROZEN: an attempt's classification records the EVIDENCE it rests on as a REFERENCE —
        an execution id, a reason code, a decision id — never as content.
FROZEN: no raw tool output, model output, prompt, completion, provider body, credential,
        secret or repository file content appears in a run record or a checkpoint. This
        is AI-05 §5.2's rule and AI-11 §18.2's rule; AI-13 inherits it rather than
        restating a weaker one.
FROZEN: a run record MUST be sufficient for a reader to answer "what did this run do,
        under which definition, within which bounds, and who authorized it" WITHOUT
        asking the component that ran it.
```

---

## 16. Non-goals — FROZEN

```text
no distributed workflow engine            no cross-machine scheduler
no cloud orchestration                    no arbitrary DAG scheduler
no hidden background daemon               no execution held open between processes
no infinite retry                         no unbounded or default-infinite deadline
no automatic privilege escalation         no widening a candidate set
no capability relaxation                  no automatic model fallback
no automatic approval                     no self-approval
no AI-05 producer registration            no EvidenceRecord written by AI-13
no provider implementation                no Agent body implementation
no tool implementation                    no benchmark redesign
no AI-12 policy execution                 no AI-10 review semantics
no SecurityLab modification
```

```text
FROZEN: AI-13 v1 does not promise that a workflow COMPLETES. It promises that a workflow
        is BOUNDED, that its state is auditable, and that nothing it does carries an
        authorization further than the invocation it was granted for.
```

---

## 17. Relations

```text
AI-04  Guard      AI-13 asks per Guard-bound invocation, exactly as AI-08 does, and
                  carries nothing forward. AI-13 does not amend AI-04, and its approval
                  point does not make Guard's gate passable (§13.5).
AI-05  Evidence   AI-13 writes none and registers no producer. AI-05 remains
                  INCOMPLETE — C-1 DEFERRED — and AI-13 does not resolve it.
AI-06  tools      Tool invocation stays on AI-06's single path. AI-13 composes it.
AI-07  Router     A new RouterRequest per attempt that needs routing; AI-07 evaluates
                  each independently. AI-13 does not amend AI-07.
AI-08  execution  An attempt IS an AI-08 execution with its own ExecutionId. AI-13
                  supplies the attempt identity around it and amends nothing in it. The
                  request boundary is an allowlist that refuses unknown fields, so a
                  resume token does NOT ride on AgentExecutionRequest — the attempt's
                  identity lives in AI-13's own state and is recorded as a reference.
AI-09  providers  untouched.
AI-10  review     a different human decision with a different subject (§13.6).
                  AI-10 §5.3 states that "resume of a closed case is not a transition;
                  it is AI-13's boundary and does not exist in v1". AI-13 does not
                  reopen a closed ReviewCase: a workflow run is not a review case, and
                  resuming a run must not be read as a transition of one.
AI-11  benchmark  untouched.
AI-12  routing v2 policy is DECLARED data; AI-13 executes none of it (§10.4). §6's
                  model-comparative prerequisite remains BLOCKED and AI-13 does not
                  satisfy it.
```

### 17.2 The Guard paragraph, stated once

For every Guard-bound invocation, a workflow attempt does what AI-08 already does:

```text
workflow step
    -> a FRESH request for THIS invocation
    -> Guard evaluates it, and remains authoritative
    -> an ALLOW authorizes THAT invocation and nothing else
```

```text
FROZEN: no previous decision — from this attempt, an earlier attempt, an earlier step,
        or an earlier run — implicitly authorizes the next attempt.
```

---

## 18. Delivery

```text
AI-13-A   contract / design freeze        this document, merged
AI-13-B   the workflow core               definition, run, step, attempt, checkpoint,
                                          classification, bounds
AI-13-C   the approval point              the human approval record and its gate
```

```text
FROZEN: AI-13-A changes this document and synchronizes the status documents it names.
        It writes no workflow code, runs no workflow, and creates no checkpoint.
```

---

## 19. Exit criteria

```text
C0   architecture baseline reviewed — C0 names the phases this contract composes, the
     seams it reuses, and the four deferrals it picks up (§1, §4, §17)
C1   workflow identity frozen — id, revision, digest, run id, workspace binding, and
     the terminal states a mismatch produces (§5)
C2   step / attempt / checkpoint model frozen (§6, §7)
C3   resume integrity rules frozen — what is verified, what is inherited, what MUST NOT
     be (§8)
C4   retry and failure semantics frozen — the nine classes, retryability as an execution
     fact, the four things retry is not, and the never-retried list (§9, §10)
C5   timeout and cancellation semantics frozen (§11)
C6   resource limits frozen — declared, bounded, terminal when reached (§12)
C7   human approval boundary frozen — binding, non-inheritance, no self-approval, no
     Evidence record, no Guard approval (§13)
C8   Guard / Router / Evidence ownership frozen, with the ownership table (§4, §17)
C9   security non-goals frozen (§16)
C10  auditability and provenance requirements frozen (§15)
C11  required tests and mutation controls identified — named in §21, NOT implemented here
C12  contract review checkpoint ready — this document is the review material
```

---

## 20. Amendment Rule

```text
FROZEN: AI-13-B and AI-13-C MUST NOT deviate from this document without amending it
        first.
```

An amendment is REQUIRED for any change to:

```text
workflow identity, the revision/digest binding, or the workspace binding (§5)
the step, attempt or checkpoint model (§6, §7)
resume integrity (§8)
failure classification or retryability (§9)
the retry boundary, its bounds, or the four things retry is not (§10)
timeout or cancellation semantics (§11)
the resource limits or the rule that they are declared (§12)
the human-approval boundary (§13)
AI-13's vocabulary (§14)
the auditability requirements (§15)
any non-goal (§16)
```

```text
FROZEN: AI-13 owns this document. It does NOT own AI-04, AI-05, AI-06, AI-07, AI-08,
        AI-09, AI-10, AI-11 or AI-12. An amendment to one of those is made by that
        phase, under that phase's amendment rule, BEFORE any AI-13 work depends on it.
```

An amendment records: what changed, why, its security and authority impact, and the date.
It is committed before the code that depends on it. Applied amendments are logged in §22.

---

## 21. What AI-13-B must prove — identified here, implemented there

```text
T1   a resumed attempt inherits no authorization: a checkpoint carrying a Guard
     decision, or an attempt reading one back, MUST fail
T2   an approval bound to attempt 1 does not authorize attempt 2
T3   an approval whose scope digest differs in ANY of the six bound fields is refused
T4   an approval whose actor is the executing Agent, a model or a service is refused
T5   a denied approval is terminal and produces no automatic re-request
T6   an approval that misses its deadline is APPROVAL_DENIED, not a pending state
T7   a revision mismatch is DEFINITION_CHANGED and is not retried into agreement
T8   a definition digest mismatch is refused even when the revision string matches
T9   a workspace identity mismatch is WORKSPACE_CHANGED
T10  a checkpoint whose own digest does not verify is CHECKPOINT_CORRUPT
T11  a retry that would widen the request is refused
T12  a retry that would exceed the declared attempt or time bound is refused
T13  an attempt that needs routing submits a new request and reuses no decision
T14  an unclassified failure stops and is never retried
T15  AUTHORIZATION_DENIED, APPROVAL_DENIED and CANCELLED are never retried
T16  a workflow that declares no limit is refused at validation
T17  reaching a declared bound produces RESOURCE_EXHAUSTED, not a silent stop
T18  no AI-13 run record or checkpoint contains raw tool output, model output, a
     credential or repository content
T19  AI-13 writes no AI-05 record and registers no producer
T20  AI-13 reads no AI-12 policy and executes no fallback
T21  AI-13 does not reopen a closed ReviewCase; a resumed run is not a review
     transition (AI-10 §5.3)
```

```text
FROZEN: each of these MUST be a test that fails when the guard it names is REMOVED, not
        merely a test that passes while the guard exists. AI-13-B's review will require
        mutation controls of the kind AI-12-B's did: take a working artifact, break the
        rule, and require the focused test to notice.
```

```text
FROZEN: AI-13-B MUST add a Layer 0 boundary for workflows/. The top-level workflows/
        directory is unchecked today — the only `workflows` Layer 0 knows about is
        .github/workflows — so a workflow module could reach a provider, write an
        Evidence record or start a process with nothing to stop it.
```

---

## 22. Amendment Log

```text
(none yet — this document is a freeze proposal and no amendment has been applied)
```

---

## Status

```text
AI-13-A  = DRAFT / FREEZE PROPOSAL   this document
AI-13-B  = NOT STARTED               the workflow core
AI-13-C  = NOT STARTED               the approval point
AI-13    = NOT COMPLETE

AI-12    = NOT CLOSED                §6 model-comparative prerequisite BLOCKED
AI-12-C  = BLOCKED / NOT STARTED
AI-05    = INCOMPLETE                C-1 DEFERRED; AI-13 does not resolve it
```
