# AI-12 — Model Routing v2 — Execution Plan

> Status: **DRAFT — FREEZE PROPOSAL** (AI-12-A, 2026-10-03)
> Phase: AI-12 — Model Routing v2
> Sub-phase: **AI-12-A — Contract / Design Freeze**
> Prerequisite: AI-11 — COMPLETE / MERGED / CLOSED (`6bbe526b5bedeb29fb138f8979f0a4cb6df1b3ce`)
> Base: `main` @ `6bbe526b5bedeb29fb138f8979f0a4cb6df1b3ce`
> Rule: This document defines the contract. AI-12-B implements against it. Nothing in AI-12
> may deviate from a frozen contract without amending this document first (§13).

```text
THIS DOCUMENT IS NOT YET FROZEN.

The freeze act is human review followed by the merge of PR 1.
Until that merge, this is a proposal. C0 (§12) is NOT satisfied by this document's
existence — it is satisfied by its merge.

No code exists. No routing decision has been made. No model has been measured.
```

---

## 0. The one idea — read this first

```text
measured task facts
  + a declared policy over those facts
  + the evidence each decision cites
  =  an auditable routing decision
```

Everything below is a consequence of one refusal:

```text
FROZEN: a routing decision MUST NOT cite a measurement that does not exist.
```

```text
FROZEN: Evidence > preference.
FROZEN: BLOCKED, NOT_RUN, UNKNOWN and UNAVAILABLE are NOT PASS, and MUST NOT be
        weighted, scored, aggregated or reasoned about as if they were.
FROZEN: an unmeasured dimension stays UNKNOWN. AI-12 v1 MUST NOT invent a value for it
        in order to produce a complete-looking policy.
FROZEN: AI-12 v1 produces NO universal ranking, NO overall winner, NO best model.
```

---

## 1. Purpose

AI-12 exists to **use** the data AI-11 produced, without redefining it.

`docs/MASTER_ROADMAP.md` requires that routing v2 be built on real benchmark data —
*"AI-12 必须建立在 AI-11 的真实数据上"*. AI-11 has now produced that data: a six-task
corpus measured through independent oracles, a reference-executor campaign, and a
determinism control. AI-12 turns those measurements into routing policy.

AI-12 is **not** a second benchmark and **not** a scoring layer on top of AI-11. It reads
AI-11's records as they are, and the first thing this contract freezes is what "as they
are" forbids.

---

## 2. Normative Language

```text
FROZEN      settled by this contract. AI-12-B MUST implement it.
            Changing it requires an amendment (§13).

PROPOSED    this contract's choice, made so AI-12-B does not have to choose while
            implementing. Normative for AI-12-B, and the class most likely to be
            amended.

DEFERRED    deliberately not done, with the reason recorded.

BLOCKED     cannot be done now, and the blocker is named.

OPEN        a question this contract does NOT answer. An OPEN item MUST NOT be closed
            by an implementation decision (§13).
```

---

## 3. Scope

### 3.1 In scope for AI-12 v1

```text
the consumption contract over AI-11 records
the shape of a routing decision: inputs, outputs, evidence binding
task-to-model policy, fallback policy and escalation policy as DECLARED artifacts
explainability, auditability and reversibility requirements
```

### 3.2 Out of scope — FROZEN

```text
FROZEN: AI-12 v1 does not re-run, re-judge, re-derive or re-score any AI-11 measurement.
FROZEN: AI-12 v1 does not call a provider and does not execute a model. It routes
        against records that exist; producing new records is a later, separately
        contracted act.
FROZEN: AI-12 v1 does not modify AI-11, AI-07, AI-04 or any other phase's contract,
        code or material.
FROZEN: AI-12 v1 does not produce a composite score across tasks or across axes.
FROZEN: AI-12 v1 does not remove a task from the corpus, for any reason, including
        that the task is BLOCKED.
FROZEN: AI-12 v1 does not execute a fallback, retry a model, hold runtime decision
        state, or perform any long-running recovery. Its fallback and escalation are
        declared data (§5.2).
```

---

## 4. What AI-12 consumes — AI-11's measured facts, supplied and read-only

### 4.1 The record — an explicitly supplied, immutable input

```text
FROZEN: AI-12 consumes explicitly supplied immutable AI-11 `BenchmarkRun` records and,
        when used, an explicitly supplied campaign report / manifest.
FROZEN: every consumed `BenchmarkRun` is identified by its exact `run_id` and a
        recorded digest of the supplied record.
FROZEN: AI-12 MUST NOT assume `benchmarks/results/` contains durable historical
        campaign data.
FROZEN: AI-12 MUST NOT reconstruct a `BenchmarkRun` from `docs/AI-11_EVIDENCE_*.md`,
        task definitions, truth files, or raw campaign output.
FROZEN: if the required machine-readable AI-11 record is absent, the input dimension is
        UNKNOWN / unavailable to AI-12. AI-12 MUST NOT regenerate it by re-running or
        re-judging AI-11.
FROZEN: a campaign report is an input only when its exact supplied instance and
        provenance are identifiable. AI-12 MUST NOT silently substitute a different
        campaign report.
```

AI-11's run data is **disposable by design**. A `BenchmarkRun` is produced into a
scratch root, and the campaign report of §3 of the AI-11 evidence is command output —
neither is durable tracked corpus. Supplying them is therefore an explicit act, and the
supplied instance is what AI-12 reasons over.

```text
FROZEN: this contract does not make AI-11's result directory durable, and does not ask
        AI-11 to change where it writes. AI-12's input is a supplied artifact, not a
        location.
```

For each task, the fields AI-12 may reason over once such a record is supplied:

```text
run_id · task_id · task_version · source_sha · workbench_sha
task_status              PASS / FAIL / BLOCKED / NOT_RUN / UNKNOWN / UNAVAILABLE
regression_status        the same six-member vocabulary, on its own axis (§12 of AI-11)
tests                    planned / executed / passed / failed / skipped
oracle_results           per-oracle verdict, reason_code, counts, limitations
limitations              the parameterised reason codes a run carries
workspace_identity       the manifest digest the measurement was taken in
security_boundary_status its own axis
```

### 4.2 REFERENCE evidence is not model evidence

```text
FROZEN: a `BenchmarkRun` with `executor_kind = REFERENCE` is evidence about the
        benchmark task, the oracle and the reference execution path.
FROZEN: a REFERENCE verdict MUST NOT be interpreted as evidence of a model's
        capability, model success rate, model reliability, model cost or model latency.
FROZEN: AI-12 MUST NOT select a particular model because an AI-11 REFERENCE run
        received PASS.
FROZEN: AI-12 MUST NOT convert a REFERENCE task PASS into a model-performance claim.
FROZEN: model-specific routing evidence requires an execution record whose producer
        identifies the model / provider execution, under a contract that defines how
        that measurement is produced and attributed.
```

A REFERENCE run says *this task is solvable and this oracle says so*. It says nothing
about any model, because no model was involved: `agent_id` is null, `provider` is null,
`token_usage` and `cost` are null, and `tool_trace` is empty on every record.

```text
FROZEN: "the task PASSed" and "a model performs well on the task" are different
        sentences, and AI-12 MUST NOT write the second from the first.
```

### 4.3 The four non-PASS verdicts are not promotable

```text
FROZEN: BLOCKED, NOT_RUN, UNKNOWN and UNAVAILABLE MUST NOT be read, weighted, summed,
        ranked or reasoned about as success — not by a policy, not by a weight, not by
        an "effective score", and not by treating a missing measurement as a neutral
        value.
FROZEN: a dimension with no measurement is UNKNOWN. UNKNOWN MUST be represented as
        UNKNOWN in the policy artifact, and MUST NOT be given a default, an average, a
        prior or a placeholder that a reader could consume as a value.
```

```text
FROZEN: the ONLY path from a record to a routing weight is a recorded verdict. A policy
        that cites a task MUST cite the verdict it was derived from.
```

### 4.4 A BLOCKED task is not a task to delete

```text
FROZEN: `ai11-v1-fuzzing-recovery-triage` is BLOCKED in the AI-11-C campaign on
        `PRECONDITION_UNMET:environment:vcan0-exclusive`. That is an environment
        boundary, not a defect and not a failure.
FROZEN: AI-12 MUST keep it in the corpus and MUST record it as BLOCKED. Removing it
        because it is BLOCKED — or because a policy reads better without it — is
        deleting a measurement to make a policy look complete, and is FORBIDDEN.
FROZEN: AI-12 MUST NOT treat a BLOCKED task as evidence for OR against any model. It
        carries no information about model behaviour, because nothing ran.
```

### 4.5 No re-derivation

```text
FROZEN: AI-12 MUST NOT recompute an oracle verdict, reinterpret a reason code, or
        re-derive a measurement from raw material. AI-11's verdict is the input, and an
        input that can be recomputed differently by the consumer is not a measurement.
FROZEN: where AI-12 needs a fact AI-11 did not record, that fact is UNKNOWN and the
        phase that owns it is named. It is NOT estimated here.
```

---

## 5. The routing decision

### 5.1 Inputs — DECLARED, and what exists today

```text
input                      exists in AI-11's campaign today?
task type / task family    YES — every corpus task declares one
task_status                YES
regression_status          YES
test / execution counts    YES
environment facts          YES — host record, limitations, source_sha
failure patterns           YES, as reason codes
tool-call facts            NO  — `tool_trace` exists on every record and is EMPTY on
                                 all six: the REFERENCE executor makes no tool calls
cost                       NO  — token_usage is null on every record (no provider call)
latency                    NO  — `duration_ms` records the HARNESS's own run duration
                                 and is excluded as operational; no model latency exists
per-model success history  NO  — the campaign ran executor_kind = REFERENCE
```

```text
FROZEN: every row marked NO is an UNKNOWN input. AI-12 v1 MUST NOT synthesise one, and
        MUST NOT ship a policy that would read differently if one had been synthesised.
FROZEN: an empty field is NOT a measured zero. `tool_trace` being present and empty means
        no tool call was made in a run where none was possible — it is not evidence that
        a model uses tools correctly, and MUST NOT be read as a success rate of 0 or 1.
```

### 5.2 Outputs

```text
task-to-model policy    for a task (or task family), which model profile is selected,
                        and the evidence that selection cites
fallback policy         what is selected when the first choice is ineligible, DECLARED
                        in advance rather than improvised at failure time
escalation policy       the declared condition under which a task moves to a different
                        model, and what happens to the result of the first attempt
```

```text
FROZEN: AI-12 fallback and escalation are DECLARATIVE POLICY DATA only.
FROZEN: AI-12 MUST NOT execute a fallback, retry a model, or create a hidden second
        routing decision.
FROZEN: AI-07 v1's frozen no-automatic-fallback boundary remains unchanged. AI-07 does
        not retry a selected model and keeps no "the previous model failed" state.
FROZEN: when a fallback is realised through AI-07, it is a new caller-submitted
        `RouterRequest` and an independently evaluated `RouterDecision`.
FROZEN: the previous decision does not grant authorization to the next decision.
FROZEN: AI-12 MUST NOT widen the original candidate set, or relax capabilities,
        modality, independence or any other `RouterRequest` constraint, during
        fallback or escalation.
FROZEN: execution, retry and long-running recovery remain outside AI-12.
```

AI-12 declares *what should happen*; it does not make it happen. The actor that submits
the next request, and the component that evaluates it, are unchanged by this contract.

### 5.3 Evidence binding — the exact run, not merely the task

```text
FROZEN: every routing decision MUST bind to the exact `BenchmarkRun` from which its
        measurement was consumed.
```

The binding therefore carries at least:

```text
run_id
task_id
source_sha
workbench_sha
verdict
reason_code
limitations
```

```text
FROZEN: `task_id` alone is not evidence identity.
FROZEN: `source_sha` alone is not evidence identity.
FROZEN: `run_id` identifies the exact measured run.
```

```text
FROZEN: a decision that cites no evidence is not a routing decision. It is a
        preference, and it MUST be represented as UNKNOWN rather than emitted as policy.
FROZEN: where a campaign manifest is consumed, its digest MAY be recorded alongside the
        binding. It does not replace `run_id`: a manifest identifies a batch, and a
        decision is a claim about one run.
```

---

## 6. The prerequisite this contract does not have yet

```text
BLOCKED: a MODEL-comparative policy.
```

AI-11's campaign measured **tasks**, through `executor_kind = REFERENCE`, with
`agent_id = null` and no provider call anywhere. It therefore contains **no per-model
success history, no cost and no latency**.

```text
FROZEN: no AI-12 policy may select between models on the strength of AI-11-C's campaign.
        That campaign does not contain the measurement such a selection would need.
```

Producing those measurements is a **separately contracted act**: it needs a model
execution path, a declared provider, and an amendment or a new phase document that
freezes how a model measurement is taken and attributed. AI-12-A does not write that
contract, and AI-12-B MUST NOT improvise it.

```text
DEFERRED: the model-comparative policy, until per-model measurements exist under a
          contract that says how they are produced and attributed.
```

### 6.1 What AI-12-B may build while §6 is BLOCKED

The prerequisite blocks a **claim**, not a codebase. This is the boundary:

```text
FROZEN: until the model-comparative prerequisite is satisfied, AI-12-B MAY implement:
            policy schema
            policy validation
            evidence binding
            falsifier / discrimination validation
            rollback metadata
            dormant policy artifacts
FROZEN: until that prerequisite is satisfied, AI-12-B MUST NOT activate or ship a
        model-comparative rule that claims one model is selected because it performed
        better on AI-11.
FROZEN: a policy artifact that contains no model-comparative evidence MUST remain
        explicitly dormant / UNKNOWN if it would otherwise make a model-specific
        selection claim.
FROZEN: §6 remains BLOCKED until per-model measurements exist under a separate contract
        defining their producer, attribution and measurement method.
```

```text
FROZEN: implementing the infrastructure does NOT satisfy the prerequisite. A policy
        schema that validates cleanly is not evidence that any model outperforms
        another, and C7 stays unsatisfied until the measurements exist.
```

---

## 7. Non-vacuity

```text
FROZEN: a routing policy MUST be falsifiable. For every rule, the contract requires the
        observation that would show the rule is wrong, and a policy whose rules cannot
        be contradicted by any measurement MUST NOT be shipped.
FROZEN: a policy MUST carry a discrimination control of the same kind §7.4 of AI-11
        requires of an oracle: a declared input the policy is REQUIRED to route
        differently from another declared input, with the pair recorded.
```

```text
FROZEN: "the policy selected the model we expected" is not evidence that the policy
        works. Without a declared negative case, a policy that always answers the same
        thing passes every check written against it.
```

---

## 8. Explainable, auditable, reversible

```text
FROZEN: EXPLAINABLE — every decision names the rules that fired and the evidence each
        rule read. A decision that cannot be explained from tracked artifacts is not
        emitted.
FROZEN: AUDITABLE — a reader MUST be able to re-derive any decision from the tracked
        policy and the tracked records, without asking the component that made it.
FROZEN: REVERSIBLE — every policy declares its rollback: the previous policy, the
        condition that triggers rollback, and who decides. A policy with no declared
        rollback MUST NOT be activated.
FROZEN: no silent downgrade. A fallback is a DECLARED path with its own recorded
        reason; a decision that quietly becomes a different decision is not a fallback.
FROZEN: REVERSIBLE does not mean AI-12 reverses anything itself. The rollback is
        declared here and performed through the same caller-submitted path §5.2
        describes; AI-12 holds no runtime state and grants no authorization.
FROZEN: a declared fallback MUST NOT contradict AI-07's frozen boundary, and a policy
        that would require AI-07 to retry, to remember a previous decision, or to
        re-evaluate a request automatically MUST NOT be emitted.
```

---

## 9. Non-goals — FROZEN

```text
no universal ranking
no winner
no best-model claim
no composite score across tasks, axes or models
no aggregate a reader could take as a benchmark result
no provider call
no model execution
no change to AI-04 Guard authority
no change to AI-07's routing contract
no automatic fallback, no retry, no hidden previous-decision state
no widening of a candidate set or relaxation of a RouterRequest constraint
no execution, retry or long-running recovery
```

AI-07 remains the component that selects an eligible Agent / Provider / Model profile for
an execution, and it does so **once per caller-submitted request**, with no memory of a
previous one. AI-12 changes **which policy AI-07 is given**, and nothing about who is
allowed to authorize what: Guard's authority is untouched, and the no-automatic-fallback
boundary AI-07 froze stays exactly where it is.

```text
FROZEN: AI-12 describes policy; it does not become a runtime. A fallback AI-12 declares
        is realised by a caller submitting a new RouterRequest, not by AI-12 acting.
```

---

## 10. Relations

```text
AI-07  Model Router v1 — AI-12 supplies policy; AI-07 still routes and still records why.
       AI-07 keeps its frozen no-automatic-fallback, no-retry, no-previous-decision-state
       boundary. AI-12 does not amend AI-07, does not ask it to retry, and does not
       execute a fallback on its behalf.
AI-11  AI Security Benchmark — AI-12's only measurement source. Read-only.
AI-05  Evidence — unchanged. This document is not an Evidence record and creates no
       producer token; AI-05 §28 remains OPEN.
AI-04  Guard — unchanged. AI-12 grants no authority and bypasses no check.
```

---

## 11. Delivery

```text
AI-12-A   contract / design freeze      this document, merged
AI-12-B   the policy core               §6.1's infrastructure; the model-comparative
                                        rule stays dormant while §6 is BLOCKED
AI-12-C   the campaign over policies    optional; only if §6's prerequisite is met
```

```text
FROZEN: AI-12-A changes this document and the closeout artifacts of AI-11 it carries.
        It writes no routing code, selects no model, and calls no provider.
```

---

## 12. Exit criteria

```text
C0   this document merged
C1   every consumed input is either measured or explicitly UNKNOWN (§5.1)
C2   no policy cites a verdict as success except PASS (§4.3)
C3   the BLOCKED task is present, recorded as BLOCKED, and unweighted (§4.4)
C4   every rule has a declared falsifier and a paired discrimination control (§7)
C5   every decision is explainable from tracked artifacts (§8)
C6   every policy declares its rollback (§8)
C7   §6's prerequisite is recorded as BLOCKED, not worked around — and stays BLOCKED
     after §6.1's policy infrastructure is implemented, which does not satisfy it
C8   no non-goal of §9 is violated
```

---

## 13. Amendment Rule

```text
FROZEN: AI-12-B and AI-12-C MUST NOT deviate from this document without amending it
        first.
```

An amendment is REQUIRED for any change to:

```text
the consumption contract over AI-11 records (§4)
the separation of REFERENCE evidence from model evidence (§4.2)
the promotability rule for non-PASS verdicts (§4.3)
the treatment of a BLOCKED task (§4.4)
the routing decision's inputs, outputs or evidence binding (§5)
the prerequisite in §6
the non-vacuity requirement (§7)
the explainability, auditability or reversibility requirements (§8)
any non-goal (§9)
```

```text
FROZEN: AI-12 owns this document. It does NOT own AI-04, AI-05, AI-07, AI-08, AI-09,
        AI-10 or AI-11. An amendment to one of those is made by that phase, under that
        phase's amendment rule, BEFORE any AI-12 work depends on it.
```

An amendment records: what changed, why, its security and authority impact, and the date.
It is committed before the code that depends on it. Applied amendments are logged in §14.

---

## 14. Amendment Log

```text
(none yet — this document is a freeze proposal and no amendment has been applied)
```

---

## Status

```text
AI-12-A  = DRAFT / FREEZE PROPOSAL      this document
AI-12-B  = NOT STARTED                  the policy core
AI-12-C  = NOT STARTED                  blocked by §6
AI-11    = COMPLETE / MERGED / CLOSED   the measurement source
           merge 6bbe526b5bedeb29fb138f8979f0a4cb6df1b3ce
           contract blob 6f7548a1c05b31093371f536e9a080434cddbcb0
```
