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
```

---

## 4. What AI-12 consumes — AI-11's measured facts, read-only

### 4.1 The record

```text
FROZEN: AI-12 reads the AI-11 `BenchmarkRun` records under `benchmarks/`, and the
        campaign report produced by `python3 -m benchmarks.campaign`. It reads them
        read-only.
```

For each task, the fields AI-12 may reason over:

```text
task_id · task_version · source_sha · workbench_sha
task_status              PASS / FAIL / BLOCKED / NOT_RUN / UNKNOWN / UNAVAILABLE
regression_status        the same six-member vocabulary, on its own axis (§12 of AI-11)
tests                    planned / executed / passed / failed / skipped
oracle_results           per-oracle verdict, reason_code, counts, limitations
limitations              the parameterised reason codes a run carries
workspace_identity       the manifest digest the measurement was taken in
security_boundary_status its own axis
```

### 4.2 The four non-PASS verdicts are not promotable

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

### 4.3 A BLOCKED task is not a task to delete

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

### 4.4 No re-derivation

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
tool-call facts            YES, as recorded per run
test / execution counts    YES
environment facts          YES — host record, limitations, source_sha
failure patterns           YES, as reason codes
cost                       NO  — token_usage is null on every record (no provider call)
latency                    NO  — not a recorded benchmark field
per-model success history  NO  — the campaign ran executor_kind = REFERENCE
```

```text
FROZEN: the three rows marked NO are UNKNOWN inputs. AI-12 v1 MUST NOT synthesise them,
        and MUST NOT ship a policy that would read differently if they had been
        synthesised.
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

### 5.3 Evidence binding

```text
FROZEN: every emitted decision carries the evidence it cites: the task_id, the
        source_sha, the verdict, the reason code and the limitations of the run it was
        derived from.
FROZEN: a decision that cites no evidence is not a routing decision. It is a
        preference, and it MUST be represented as UNKNOWN rather than emitted as policy.
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
```

AI-07 remains the component that selects an eligible Agent / Provider / Model profile for
an execution. AI-12 changes **which policy AI-07 is given**, and nothing about who is
allowed to authorize what: Guard's authority is untouched.

---

## 10. Relations

```text
AI-07  Model Router v1 — AI-12 supplies policy; AI-07 still routes and still records why.
       AI-12 does not amend AI-07.
AI-11  AI Security Benchmark — AI-12's only measurement source. Read-only.
AI-05  Evidence — unchanged. This document is not an Evidence record and creates no
       producer token; AI-05 §28 remains OPEN.
AI-04  Guard — unchanged. AI-12 grants no authority and bypasses no check.
```

---

## 11. Delivery

```text
AI-12-A   contract / design freeze      this document, merged
AI-12-B   the policy core               implementation against the frozen contract
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
C2   no policy cites a verdict as success except PASS (§4.2)
C3   the BLOCKED task is present, recorded as BLOCKED, and unweighted (§4.3)
C4   every rule has a declared falsifier and a paired discrimination control (§7)
C5   every decision is explainable from tracked artifacts (§8)
C6   every policy declares its rollback (§8)
C7   §6's prerequisite is recorded as BLOCKED, not worked around
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
the promotability rule for non-PASS verdicts (§4.2)
the treatment of a BLOCKED task (§4.3)
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
