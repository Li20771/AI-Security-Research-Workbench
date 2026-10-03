# AI-13 — Long-running Workflows — Execution Plan

> Status: **FROZEN** (AI-13-A, 2026-10-03 — frozen by the merge of PR #69)
> Phase: AI-13 — Long-running Workflows
> Sub-phase: **AI-13-A — Contract / Design Freeze**
> Base: `main` @ `2c23bab866ce20595fccfde2ff1f563ce0a07086`
> Rule: This document defines the contract. AI-13-B implements against it. Nothing in AI-13
> may deviate from a frozen contract without amending this document first (§20).

```text
THIS DOCUMENT IS FROZEN.

The freeze act was human review followed by the merge of PR #69 into `main`, at merge
commit `1e0a7fd`. C0 (§19) is satisfied by that merge — as the block here said it would
be — and not by this document's existence.

This block is a STATUS record and nothing more. It changes no clause of §0–§21: those
are as merged, and a change to any of them is an amendment (§20), never a status edit.

At the freeze no workflow code existed, no workflow had run and no checkpoint existed.
AI-13-B implements the workflow core against this document (§18).
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
FROZEN: a run records the WORKSPACE IDENTITY it started under, and resume requires an
        EXACT match. The repository already treats a workspace identity as part of what
        a measurement means (AI-08 records it; AI-11 binds a manifest digest into a
        run); a workflow that resumed into a different tree would be continuing work in
        a place the earlier steps never saw.
FROZEN: v1 has NO re-derivation. A workspace identity that differs in any way is
        `WORKSPACE_CHANGED` and the run is terminal. There is no "re-derived and
        therefore equivalent" path, because defining what would make two workspaces
        equivalent is a mechanism with no requirement behind it yet — and a v1 that
        invented one would be a rule nobody asked for and nobody could check.
```

```text
DEFERRED: workspace re-derivation, as an artifact with its own digest, authority and
          validation. It becomes a contract question the first time a run genuinely
          needs to continue in a re-derived tree, and not before.
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

```text
AMENDMENT 1 (2026-10-04) — the approval point GATES a step; it is not one.

FROZEN: an APPROVAL step is a declared WAIT on an approval. It is NOT an execution-seam
        step: it reaches no seam, runs nothing, and produces nothing.
FROZEN: an APPROVAL step therefore has no AttemptId and no ExecutionId of its own, and
        creates no attempt however long it waits.
FROZEN: an APPROVAL step gates the NEXT declared execution-seam step in workflow order.
        A definition whose APPROVAL step has no subsequent execution-seam step is
        REFUSED: an approval that authorizes nothing is not an approval this contract
        admits, and a wait with nothing behind it is the unbounded state §16 forbids.
FROZEN: "execution-seam step" means a step naming an Agent execution or a tool
        invocation through AI-06's path. An APPROVAL step is not one.
FROZEN: the target is the NEXT one in DECLARED order and nothing else. There is no
        selector, no name, no index and no second mechanism for choosing which step an
        approval point gates — a target a definition could point anywhere would be a
        target an approval could be moved between.
```

```text
WHY THIS IS AN AMENDMENT, and not a clarification of wording already here:

    §6.1 made an APPROVAL step a declared wait.
    §6.3 made one attempt at one step an AI-08 EXECUTION.
    §13.1 bound an approval to (…, step_id, attempt_no).

    A wait produces no execution, so by §6.3 it has no attempt — and by §13.1 an approval
    can therefore not name it. The three clauses could not hold together, and nothing in
    the document said which step an approval belongs to when the wait is its own step.
    That is the ambiguity this amendment resolves.
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
AMENDMENT 1 (2026-10-04) — which steps have attempts, and whose attempt an approval names.

FROZEN: attempts exist ONLY for execution-seam steps (§6.1). An APPROVAL step's work is
        a wait, a wait is not an execution, and it therefore creates no attempt.
FROZEN: the attempt a workflow approval authorizes belongs to the EXECUTION-SEAM step
        that approval point GATES (§6.1). It is never an attempt of the wait itself,
        which has none for an approval to name.
```

```text
UNCHANGED BY THAT AMENDMENT, and stated so that nothing here reads as a licence:

    AI-08 execution identity     an attempt is still one AI-08 execution, and AI-13
                                 still mints, reuses and interprets no ExecutionId
    AttemptId                    still (run_id, step_id, attempt_no)
    ExecutionId uniqueness       still one execution per attempt, never one execution
                                 with a counter on it (§6.3, T13)
    a fresh execution per attempt  still the rule, for every attempt that exists
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

### 7.4 The canonical form — ONE definition, for every digest AI-13 computes

An earlier revision said a checkpoint "carries a digest of its own bytes". That is
circular: the digest field is part of the bytes it would cover, so no value satisfies it.
The preimage is frozen here, and **every digest in this contract uses this section** —
the checkpoint digest (§7.1), the approval scope digest (§13.2), the run record digest
(§15) and the definition digest (§5) alike. One definition, so two of them cannot drift
apart.

```text
PREIMAGE   the UTF-8 bytes of the canonical JSON object formed from the record's
           fields EXCLUDING the record's own digest field.

CANONICAL JSON
    object keys sorted ascending by Unicode code point
    no whitespace between tokens, no trailing newline
    strings UTF-8, minimal JSON escaping (quote, backslash, control characters)
    integers only — no floats, no exponent notation
    a field whose value is null is OMITTED from the body
    an empty list or empty object is PRESENT, as [] or {}

DIGEST     SHA-256 over the PREIMAGE, lowercase hexadecimal

EXCLUDED   the digest field itself, and NOTHING else. Each record names that field in
           its own schema; a record with two digest-shaped fields is invalid.
```

```text
FROZEN: null and absent are the SAME in the canonical body, and an empty list is NOT
        absent. The distinction is frozen because the alternative — a digest that turns
        on whether a writer emitted `null` or omitted a key — makes two byte-different
        records canonicalise equal, or two equivalent records canonicalise differently,
        and a reader cannot tell which happened.
FROZEN: integers only. A float in a digest-covered field is REFUSED at validation: two
        implementations that disagree about `1.0` versus `1` produce two digests for one
        fact, and the disagreement is invisible until it matters.
FROZEN: the algorithm is SHA-256 and the encoding lowercase hexadecimal. A record whose
        digest is not exactly that is invalid, not merely unverifiable.
```

```text
T10, MECHANICALLY
    take a valid checkpoint
    modify ONE byte of any covered field
    recompute -> a different digest
    verify   -> mismatch -> CHECKPOINT_CORRUPT, and the run is terminal
```

```text
FROZEN: changing this section changes every digest in the phase. It is an amendment
        (§20), never an implementation choice, and AI-13-B MUST NOT pick its own
        ordering, encoding or algorithm.
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
            workspace identity matches EXACTLY (§5)
            the checkpoint's own digest is intact (§7.4)
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

### 8.3 A BOUND MUST SURVIVE RESUME

This contract says both that nothing is held open between process lifetimes (§12) and
that a run has a maximum runtime (§11, §12). Together those would be escapable: an
attempt runs, the process exits, the run resumes, and a duration that restarted would
let a run with a one-hour bound run for a week.

```text
FROZEN: a bound MUST SURVIVE RESUME. A resumed run inherits the budget already
        consumed, and no resume, restart or wait grants a new one.
```

The model is a **persisted absolute deadline**, not a duration:

```text
FROZEN: the workflow deadline is computed ONCE, at run creation, and persisted as an
        ABSOLUTE instant. It is never recomputed, never moved and never re-derived from
        a duration.
FROZEN: resume reads the stored deadline and computes what REMAINS from the current
        time. It never writes a new deadline. A run whose stored deadline has passed
        does not resume — it is TIMED_OUT.
FROZEN: the retry time bound is ABSOLUTE for the run, shared by every retry of every
        step, not granted fresh per attempt. An attempt that would BEGIN after the retry
        deadline MUST NOT begin; reaching it is RESOURCE_EXHAUSTED.
FROZEN: the attempt bound is a PERSISTED COUNTER on the run record (§15), not a counter
        reconstructed from checkpoints. Discarding a checkpoint MUST NOT reduce the
        number of attempts a run has already spent.
```

```text
TIMESTAMPS, FROZEN
    format       ISO-8601, UTC, trailing `Z`, second resolution
    a bound is reached when the current time is >= the deadline
```

```text
FROZEN: a bound that must survive a resume MUST NOT be persisted as a MONOTONIC reading.
        A monotonic clock is meaningful only within the process that read it, so a
        stored one says nothing after a restart — it would look like a very large
        remaining budget. A monotonic reading MAY be used inside one attempt as an
        implementation detail, and MUST NOT be persisted as if it were a deadline.
```

```text
FROZEN: PROCESS RESTART, CHECKPOINT RESUME, and TIME SPENT AWAITING AN APPROVAL all
        consume the run's deadline. None of them pauses it. An approval that could pause
        the clock would be a way to run forever by asking a human slowly; the approval
        has its own deadline (§13.4) and the run's keeps running.
```

```text
FROZEN: reaching the workflow deadline is TIMED_OUT. Reaching the retry time bound or
        the attempt bound is RESOURCE_EXHAUSTED. Neither is retried, and neither is a
        silent stop (§12).
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
FROZEN: where a failure matches none of the nine, it is UNCLASSIFIED: NO FailureClass
        is assigned, the execution STOPS, and no retry is permitted. The run record says
        the failure was unclassified rather than naming a class it does not have.
```

```text
FROZEN: FailureClass is exactly the nine members above. It has NO `UNKNOWN` member, and
        adding one is an amendment (§20).
```

```text
FROZEN: "unclassified" is AI-13's own fact about its own classification. It is NOT
        `StatusValue.UNKNOWN`, NOT `GuardDecision.UNKNOWN`, NOT `OracleVerdict.UNKNOWN`
        and NOT AI-05's admission `UNKNOWN`. None of those vocabularies gains a member,
        none is passed into AI-13's, and an unclassified failure is not a value that
        could be compared with one of them.
```

```text
WHY NO MEMBER. A tenth member would make "we could not classify this" a CLASS — a value
that sits in the same field as the nine and that a policy could be written against. It
is not a kind of failure; it is the absence of a classification, and the only honest
action on an absence is to stop. The mutation control is exact: make an unclassified
failure assignable, and T14 must fail.
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

### 10.3.1 Effective bounds — the precedence, frozen

Several bounds can apply to one decision at once. Which one governs MUST NOT be left to
an implementation, because two implementations that differ would disagree about whether
a run may take another attempt — and the disagreement would be invisible until a run
went too far.

```text
FROZEN: where more than one declared bound applies, the NARROWER one governs. Never the
        wider, and never a value an implementation chose.

effective attempts for a step
    = min( attempts declared for that step,
           total attempts remaining for the run,
           the retry policy's attempts bound, where that policy covers this failure )

effective deadline
    = min( workflow deadline,
           retry policy deadline, where that policy covers this failure,
           step deadline )

effective step deadline
    = min( step deadline, the workflow deadline's REMAINING time )
```

```text
FROZEN: the absence of a bound is not "unlimited". A definition that omits one does not
        validate (§12) — so there is no case in which one bound's silence widens
        another.
FROZEN: a bound is evaluated BEFORE an attempt begins. An attempt that would begin at or
        after any effective deadline MUST NOT begin, and one that would exceed any
        effective attempt bound MUST NOT begin. Bounds are not discovered by overrunning
        them.
FROZEN: a step deadline that is not narrower than its workflow's remaining time is not a
        step deadline — it is a number that never governs.
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
FROZEN: every counter a limit is enforced from lives on the RUN RECORD (§15), never on a
        checkpoint. That is what makes a limit survive a resume (§8.3) and what makes it
        unescapable by discarding one.
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

```text
SCOPE PREIMAGE, FROZEN — exactly these six fields and nothing else:

    scope_digest = SHA-256 ( §7.4's canonical form )
        over the canonical JSON object of
            workflow_id
            revision
            definition_digest
            run_id
            step_id
            attempt_no
```

```text
FROZEN: nothing else enters the scope preimage — not the approver, not the timestamp,
        not the artifact reference, and NOT the artifact's bytes. The first three are
        properties of the APPROVAL while the digest is a property of the SCOPE, and an
        approver or a time in the preimage would give one scope as many digests as it
        had approvers. The artifact is excluded because its bytes are the one thing this
        contract deliberately keeps out of the record (§7.2); a scope that turned on
        them could not be computed from the record alone.
FROZEN: changing ANY ONE of the six produces a different scope_digest, and an approval
        whose scope_digest does not match the scope under evaluation is REFUSED. That is
        what makes non-inheritance mechanical rather than a matter of careful reading.
```

```text
AMENDMENT 1 (2026-10-04) — WHICH step and attempt the six name.

FROZEN: a workflow approval is for the execution-seam step GATED by the approval point
        (§6.1), and NOT for the approval wait step itself.

    scope.step_id      the StepId of the GATED execution-seam step
    scope.attempt_no   the next legal attempt number for that gated step, as it stood
                       when the ApprovalRequest was created

FROZEN: the preimage above is UNCHANGED. It remains exactly those six fields, and this
        amendment adds no seventh. `step_id` and `attempt_no` were two of the six all
        along; what was underspecified was WHICH step and attempt they name, not how many
        fields there are.

FROZEN: still excluded, now and always — ApprovalPointId, an AttemptId object, an
        ExecutionId, workspace_identity, the approver, the timestamp, the artifact
        reference and the artifact's bytes.
```

### 13.1.1 The ApprovalRequest

```text
FROZEN: an ApprovalRequest is created when the run REACHES the APPROVAL step, and it
        names the scope of the gated execution-seam step:

            workflow_id · revision · definition_digest · run_id ·
            gated step_id · next legal attempt_no for that gated step

FROZEN: an ApprovalRequest carries NO authority. Holding one is permission for nothing,
        and it is not an approval.
FROZEN: it is NOT durable and MUST NOT be persisted as authority: §15.2 records the
        approvals a run ACCEPTED, and a request nobody answered is a fact about a wait
        rather than about what the run did.
FROZEN: it MUST NOT enter a checkpoint (§7.2), MUST NOT produce an attempt, and MUST NOT
        produce an ExecutionId.
```

### 13.1.2 Acceptance, and what the wait becomes

```text
AWAITING_APPROVAL
        |
        |  a valid approval for the EXACT target scope
        v
approval step  ->  SUCCEEDED
run            ->  RUNNING
gated step     ->  READY, untouched
        |
        v
begin_attempt()
        |
        v
exactly the attempt_no the approval named
```

```text
FROZEN: the APPROVAL step becomes SUCCEEDED, and its SUCCEEDED requires NO attempt —
        a wait is not an execution, and §6.3 gives attempts only to execution-seam
        steps. This is the one step-state transition in this contract that no attempt
        produces, and it is named rather than implied.
FROZEN: the gated step is left READY and untouched by the acceptance. The approval
        authorizes an attempt; it does not run one, and it does not itself change
        anything about the step it gates.
FROZEN: the attempt that follows MUST be exactly the attempt_no the approval named. An
        attempt at a different number is not the authorized one, and §6.3's "never
        reused, never renumbered" makes that a fact about the number rather than a
        promise about the engine.
FROZEN: acceptance does NOT touch the gated step's deadline, the run's deadline, or any
        counter. It moves the run out of a wait it was already paying for.
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

```text
AMENDMENT 1 (2026-10-04) — non-inheritance, stated as arithmetic.

FROZEN: `attempt_no` is one of the six, so an approval for one attempt of the GATED step
        cannot authorize another. A retry, or a resume that re-executes an interrupted
        step as a new attempt, moves that step's next legal attempt number on — the
        scope changes, and the old approval's digest no longer matches the scope under
        evaluation.

FROZEN: SAME RUN, SAME STEP, SAME REVISION and SAME DEFINITION DIGEST are FOUR of the
        six fields. Four is not six. An implementation that matched on those four would
        be matching on a different thing than this contract defines, and the digest is
        what makes that visible rather than a matter of careful reading.

    approval(scope attempt_no = 1)   authorizes only attempt_no = 1
    retry | resume                   produces attempt_no = 2
    the same approval                REFUSED, because the scope it names no longer exists
```

### 13.3 Only a designated ingress can produce an approval

An earlier revision said self-approval was "structurally impossible" and then listed
only what a record may SAY: `actor.type = human`, not the executing Agent, not a
service principal. Every one of those is a FIELD. A caller that writes them satisfies
all three, and a check that reads them proves a string, not a human — the same defect
AI-12-B's review found when a caller labelled its own record `MODEL_EXECUTION` and
manufactured the prerequisite.

```text
FROZEN: a caller-authored record that declares `actor.type = human` is NOT proof of a
        human approval. The declaration is a LABEL, and AI-13-C MUST NOT accept a label
        as the thing it labels.
FROZEN: a valid workflow approval MUST originate from the EXPLICITLY DESIGNATED HUMAN
        APPROVAL INGRESS — the one authority this phase permits to produce approvals.
FROZEN: that ingress MUST be EXTERNAL to Agent, model and service execution. No Agent
        body, no tool, no provider call, no workflow step and no run may reach it,
        invoke it, or stand in for it.
FROZEN: an approval is accepted only after AI-13-C has MACHINE-VERIFIED that it came
        from that ingress. The verification is over PROVENANCE, never over the fields a
        record carries.
FROZEN: a typed or mapping record whose only claim to humanity is `actor.type = human`
        MUST be REFUSED, however well-formed the rest of it is.
FROZEN: AI-13-C MUST NOT provide a constructor, a factory, a default or any other path
        by which an Agent, a model or a service can manufacture an approval, or the
        provenance that would make one acceptable.
```

```text
NOT FROZEN HERE — AI-13-C's to implement:
    the ingress MECHANISM. A local operator console, an artifact signed outside the
    process, a human-driven command — which one, and how provenance is proved, is C's.
FROZEN HERE — and C MUST NOT amend without §20:
    that such an authority EXISTS, that it is DESIGNATED, that it is EXTERNAL to
    execution, and that a caller cannot be it.
```

```text
FROZEN: until AI-13-C designates an ingress and its provenance check, NO approval is
        valid, and every approval step is therefore BLOCKED. That is the fail-closed
        shape AI-04 already has — "AI-04 v1 implements no approval issuance, so with no
        verified source every gated action is permanently BLOCKED. That is the intended
        fail-closed state, not a defect" — and AI-13 adopts it rather than inventing a
        weaker one of its own.
```

### 13.3.1 Self-approval, restated on that boundary

```text
FROZEN: the approver is a HUMAN actor. An Agent MUST NOT approve and a model MUST NOT
        approve — not through a tool, not through a body, not by emitting a record that
        looks like one.
FROZEN: the approver MUST NOT be the actor whose step is being approved. An approval
        whose actor is the executing Agent, the run's own identity, or any service
        principal is REFUSED.
FROZEN: those checks are NECESSARY AND NOT SUFFICIENT. They reject a record that names
        the wrong actor; §13.3 rejects a record that names the right one without coming
        from the authority entitled to name it. A record must pass BOTH, and passing the
        field checks alone is worth nothing.
FROZEN: an Agent, a model or a service is not an approval SOURCE. A caller-supplied
        human label is not sufficient. The designated ingress is the ONLY accepted
        source, and "self-approval is impossible" is a claim about that boundary — not
        about a field.
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
FROZEN: the trusted ingress (§13.3) is a WORKFLOW-level authority and NOT the approval
        source AI-04 leaves open. D-12 puts approval issuance/verification outside
        Guard and §25.2 Q-3 leaves `approval.scope_digest` to "a later phase"; a
        designated ingress for one phase's own gate does not answer AI-04's question,
        and AI-13 MUST NOT present it as though it did.
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

## 15. The run record, and its boundary with the checkpoint — FROZEN

### 15.1 Two artifacts, two jobs

```text
RunRecord    the workflow execution LEDGER: the account of what a run has done.
             Authority for BOUNDS, because a bound is a fact about the whole run.

Checkpoint   a disposable RESUME SNAPSHOT: what is needed to continue.
             Authority for nothing. It may be discarded at any time.
```

```text
FROZEN: the separation is load-bearing. A bound enforced from a checkpoint would be
        escapable by discarding one: spend three attempts, delete the checkpoint, resume,
        and a "maximum three attempts" rule has spent none. Every counter a bound is
        enforced from lives on the RUN RECORD.
FROZEN: discarding a checkpoint MUST NOT lose, and MUST NOT alter: the attempt count,
        the elapsed or remaining runtime budget, the terminal state, the approvals
        recorded, the resource consumption, or the run's lineage.
FROZEN: the run record of a NON-TERMINAL run MUST NOT be discarded. Once a run is
        terminal its record MAY be discarded like any other disposable state — but
        discarding it discards the run's auditability, so it is a declared operator act
        and it is not something a resume or a checkpoint operation may do.
```

### 15.2 The minimum a RunRecord carries

```text
run identity
    run_id · workflow_id · revision · definition_digest
    the workspace identity the run started under

step and attempt ledger, ORDERED
    every step and its StepState
    every attempt, with
        AttemptId            (run_id, step_id, attempt_no)
        the ExecutionId it produced          — a REFERENCE, never content
        the FailureClass it ended with, or an explicit "unclassified" (§9.1)
        when it began and when it ended

failure and authorization provenance, as REFERENCES
    for each non-succeeding attempt: the reason code and the decision id it rests on
    every approval: its scope_digest and its artifact reference

bounds
    every bound the run DECLARED
    every bound's CONSUMED counter and its ABSOLUTE deadline (§8.3)
    which bound the run reached, if it reached one

state
    a terminal state, or an explicit statement that the run is not terminal
```

```text
FROZEN: an attempt's classification records the EVIDENCE it rests on as a REFERENCE —
        an execution id, a reason code, a decision id — never as content.
FROZEN: no raw tool output, model output, prompt, completion, provider body, credential,
        secret or repository file content appears in a run record or a checkpoint. This
        is AI-05 §5.2's rule and AI-11 §18.2's rule; AI-13 inherits it rather than
        restating a weaker one.
FROZEN: a run record MUST be sufficient for a reader to answer "what did this run do,
        under which definition, within which bounds, and who authorized it" WITHOUT
        asking the component that ran it.
FROZEN: the run record is NOT an AI-05 EvidenceRecord, MUST NOT be written as one, and
        MUST NOT be reshaped into one. AI-13 registers no producer (§16).
FROZEN: where a run record carries its own digest, it uses §7.4's canonical form with
        the digest field excluded — the same rule as every other digest here, so a
        second self-digest ambiguity cannot appear in the artifact a reader trusts most.
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

## 18. Delivery — and who owns which semantics

```text
AI-13-A   contract / design freeze   this document, merged
AI-13-B   the workflow core          definition · identity · step · attempt · checkpoint
                                     · resume · failure classification · retry · timeout
                                     · cancellation · limits · run record
AI-13-C   the approval point         the DESIGNATED HUMAN APPROVAL INGRESS and its
                                     provenance check · the workflow approval record ·
                                     validation · scope digest · deadline ·
                                     non-inheritance · self-approval refusal · denied
                                     semantics
```

```text
FROZEN: AI-13-B implements NO approval semantics. The approval RECORD, the ingress it
        must come from, its scope digest, its non-inheritance, its deadline and its
        refusal rules are AI-13-C's, and they are frozen in §13 so that C implements
        against a settled contract rather than deciding them while coding.
FROZEN: C's exit INCLUDES designating the ingress and implementing its provenance
        check. Until both exist, every approval is invalid and every approval step is
        BLOCKED (§13.3) — so a C that implemented the record without the ingress would
        have implemented a gate that accepts anything, which is worse than none.
FROZEN: therefore AI-13-B REFUSES a definition that declares an approval step, with a
        named reason (`APPROVAL_STEP_NOT_IMPLEMENTED`). A workflow that needs a human
        approval does not run until AI-13-C exists. Half an approval point — a step that
        waits for something nothing can produce — would be worse than none, and a
        workflow that parked forever on a gate no implementation opens is exactly the
        unbounded state §16 forbids.
FROZEN: AI-13-B's exit does NOT include any approval assertion, and AI-13-B MUST NOT
        claim that approval semantics are proven. §21 assigns those tests to C.
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
C2   step / attempt / checkpoint model frozen (§6, §7), including §7.4's canonical
     form and the checkpoint digest preimage — one definition, shared by every digest
     in the phase
C3   resume integrity rules frozen — what is verified, what is inherited, what MUST NOT
     be, and that a BOUND SURVIVES RESUME (§8)
C4   retry and failure semantics frozen — the nine classes with NO UNKNOWN member,
     retryability as an execution fact, the four things retry is not, the never-retried
     list, and the effective-bound precedence (§9, §10)
C5   timeout and cancellation semantics frozen (§11)
C6   resource limits frozen — declared, bounded, terminal when reached (§12)
C7   human approval boundary frozen — the TRUSTED INGRESS and the rule that a caller
     assertion is not an approval, plus binding, the scope preimage, non-inheritance,
     no self-approval, no Evidence record and no Guard approval (§13). FROZEN HERE, and
     IMPLEMENTED BY AI-13-C: freezing the boundary is this contract's exit, and it is
     NOT a claim that any approval mechanism or ingress exists
C8   Guard / Router / Evidence ownership frozen, with the ownership table (§4, §17),
     and the B/C split that keeps an exit criterion from claiming a proof whose
     mechanism does not exist (§18)
C9   security non-goals frozen (§16)
C10  auditability and provenance requirements frozen, with the RunRecord / Checkpoint
     boundary and the rule that a bound is enforced from the record, not the
     checkpoint (§15)
C11  required tests and mutation controls identified and assigned to the sub-phase that
     owns them — named in §21, NOT implemented here
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
the canonical form or the digest preimage (§7.4) — this changes EVERY digest here
resume integrity, or the rule that a bound survives resume (§8)
failure classification or retryability (§9)
the retry boundary, its bounds, or the effective-bound precedence (§10)
timeout or cancellation semantics (§11)
the resource limits or the rule that they are declared (§12)
the human-approval boundary, including the trusted ingress and the scope preimage (§13)
AI-13's vocabulary, or the absence of an UNKNOWN FailureClass member (§14, §9.1)
the run record's contents, or the RunRecord / Checkpoint boundary (§15)
which sub-phase owns which semantics (§18)
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

## 21. What must be proven — identified here, implemented there

Grouped by the sub-phase that OWNS the semantics, so an exit criterion cannot claim a
proof whose mechanism does not exist yet (§18).

### 21.1 AI-13-B — the workflow core

```text
T1   a resumed attempt inherits no authorization: a checkpoint carrying a Guard
     decision, or an attempt reading one back, MUST fail
T7   a revision mismatch is DEFINITION_CHANGED and is not retried into agreement
T8   a definition digest mismatch is refused even when the revision string matches
T9   a workspace identity mismatch is WORKSPACE_CHANGED — and there is no
     re-derivation path that would accept it (§5)
T10  a checkpoint whose digest does not verify is CHECKPOINT_CORRUPT, and §7.4's
     preimage is what it is verified against
T11  a retry that would widen the request is refused
T12  a retry that would exceed an effective bound is refused (§10.3.1)
T13  an attempt that needs routing submits a new request and reuses no decision
T14  an unclassified failure assigns NO FailureClass, stops, and is never retried
T15  AUTHORIZATION_DENIED and CANCELLED are never retried
T16  a workflow that declares no limit is refused at validation
T17  reaching a declared bound produces RESOURCE_EXHAUSTED or TIMED_OUT, not a
     silent stop
T18  no AI-13 run record or checkpoint contains raw tool output, model output, a
     credential or repository content
T19  AI-13 writes no AI-05 record and registers no producer
T20  AI-13 reads no AI-12 policy and executes no fallback
T21  AI-13 does not reopen a closed ReviewCase; a resumed run is not a review
     transition (AI-10 §5.3)
T22  a definition declaring an approval step is REFUSED by B, named
     APPROVAL_STEP_NOT_IMPLEMENTED (§18)
T23  a run's deadline and attempt counters survive resume: exit the process, resume,
     and the remaining budget is what was left, not a fresh one (§8.3)
T24  the run record, not the checkpoint, is what a bound is enforced from: discarding
     every checkpoint MUST NOT reduce the attempts a run has spent (§15.1)
T25  an attempt that would begin at or after an effective deadline does not begin
```

### 21.2 AI-13-C — the approval point

```text
T2   an approval bound to attempt 1 does not authorize attempt 2
T3   an approval whose scope digest differs in ANY of the six bound fields is refused,
     and §13.2's preimage is what it is compared against
T4   a FORGED human approval is refused: a caller-authored record that carries
     `actor.type = human`, a valid scope_digest and a well-formed timestamp, but
     without provenance from the designated approval ingress, MUST be rejected —
     AND a record whose actor is the executing Agent, a model or a service is rejected
     too. Both halves are required; the field half alone proves a string, not a human
T5   a denied approval is terminal and produces no automatic re-request
T6   an approval that misses its deadline is APPROVAL_DENIED, not a pending state
```

### 21.3 Mutation controls — required of both

```text
FROZEN: each test MUST fail when the guard it names is REMOVED, not merely pass while
        the guard exists. The review of AI-12-B found three defects that a
        coverage-shaped suite had passed, and AI-13 does not repeat that: the controls
        below are the ones that must be shown to fail.
```

```text
checkpoint digest preimage     change one byte of a covered field, or move the digest
                               field into the preimage — T10 must fail
approval scope digest preimage add the approver or a timestamp to the preimage, or
                               change one of the six — T3 must fail
trusted approval ingress       remove the ingress-provenance check and let a
                               caller-authored record be accepted on its fields —
                               T4 must fail. A control that only changes
                               `actor.type` proves the enum check, not the boundary,
                               and is NOT an acceptable control for this rule
approval source is not an actor let an Agent, a model or a service reach the ingress,
                               or expose a constructor that mints an approval or its
                               provenance — T4 must fail
persisted runtime budget       recompute the deadline on resume instead of reading it,
                               or persist a monotonic reading — T23 must fail
resumed retry budget           reset the attempt counter on resume — T23/T24 must fail
RunRecord / Checkpoint split   enforce a bound from a checkpoint instead of the run
                               record — T24 must fail
B/C ownership boundary         let B accept an approval step — T22 must fail
unclassified failure stops     give an unclassified failure a class, or a retry —
                               T14 must fail
effective bound precedence     let the WIDER of two bounds govern — T12/T25 must fail
```

```text
FROZEN: AI-13-B MUST add a Layer 0 boundary for workflows/. The top-level workflows/
        directory is unchecked today — the only `workflows` Layer 0 knows about is
        .github/workflows — so a workflow module could reach a provider, write an
        Evidence record or start a process with nothing to stop it. AI-13-C extends it
        for the approval point.
```

---

## 22. Amendment Log

```text
AMENDMENT 1 — 2026-10-04 — the approval point gates a step; it is not one.

CHANGED CLAUSES
    §6.1   an APPROVAL step is a declared WAIT, is not an execution-seam step, has no
           AttemptId and no ExecutionId of its own, and gates the NEXT declared
           execution-seam step in workflow order
    §6.3   attempts exist only for execution-seam steps; a wait creates none; the attempt
           an approval authorizes belongs to the gated execution-seam step
    §13.1  scope.step_id names the GATED execution-seam step, and scope.attempt_no the
           next legal attempt number for it at the moment the ApprovalRequest is created
    §13.1.1  NEW — the ApprovalRequest: when it is created, what it names, and that it
           carries no authority, is not durable, and produces no attempt or ExecutionId
    §13.1.2  NEW — acceptance: the wait becomes SUCCEEDED with NO attempt, the gated step
           stays READY and untouched, and the attempt that follows is exactly the one the
           approval named
    §13.2  non-inheritance restated as arithmetic over the six fields

WHY THE FROZEN WORDING WAS INSUFFICIENT
    §6.1 made an APPROVAL step a declared wait.
    §6.3 made one attempt at one step an AI-08 execution.
    §13.1 bound an approval to (…, step_id, attempt_no).

    A wait produces no execution, so by §6.3 it has no attempt — and by §13.1 an approval
    could therefore not name it. The three clauses could not hold together, and the
    document did not say which step an approval belongs to when the wait is a step of
    its own. Both remaining readings were untenable: naming the wait step contradicts
    §6.3, and making the wait step also execute contradicts §6.1's "names an EXISTING
    seam — one of three".

SECURITY IMPACT
    The ambiguity decided what a human actually approved. A scope naming the wait step
    would have described a step that runs nothing, while the thing that ran would have
    been authorized by a digest over the wrong subject — the failure mode §13.2 exists to
    prevent, arrived at by underspecification rather than by a weak check.
    This amendment makes the subject unambiguous and keeps the six-field preimage
    EXACTLY as it was, so every digest already frozen keeps its meaning.

AUTHORITY IMPACT
    None transferred. The approval still opens a WORKFLOW gate and nothing else; Guard
    remains the authorization authority (§13.5), the ingress remains external and
    machine-verified (§13.3), and no approval becomes an ApprovalRef, an EvidenceRecord
    or an AI-10 decision.

THIS AMENDMENT DOES NOT CHANGE
    the six-field scope preimage          approval non-inheritance
    Guard authority                       Evidence ownership
    AI-08 execution identity              the failure vocabulary
    the checkpoint boundary               the trusted-ingress boundary

    No field is added to the scope. No vocabulary member is added anywhere. An
    ApprovalPointId is still refused: the scope IS the identity.
```

---

## Status

```text
AI-13-A  = FROZEN / MERGED           this document (PR #69 @ 1e0a7fd)
AI-13-B  = IMPLEMENTED               the workflow core — this revision of the document
AI-13-C  = IN PROGRESS               the approval point — Amendment 1 is committed,
                                     the implementation is not
AI-13    = NOT COMPLETE

AI-12    = NOT CLOSED                §6 model-comparative prerequisite BLOCKED
AI-12-C  = BLOCKED / NOT STARTED
AI-05    = INCOMPLETE                C-1 DEFERRED; AI-13 does not resolve it
```
