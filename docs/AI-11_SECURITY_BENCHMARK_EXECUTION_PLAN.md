# AI-11 — AI Security Benchmark — Execution Plan

> Status: **DRAFT — FREEZE PROPOSAL** (AI-11-A, 2026-10-02)
> Phase: AI-11 — AI Security Benchmark
> Sub-phase: **AI-11-A — Architecture Readout / Contract Design Freeze**
> Base: `main` @ `272f68f45a19cacd5d8c7bb9ad66a993260f90f3`
> Rule: This document defines the contract. AI-11-B implements against it. Nothing in AI-11
> may deviate from a frozen contract without amending this document first (§25).

```text
THIS DOCUMENT IS NOT YET FROZEN.

The freeze act is human review followed by the merge of PR 1.
Until that merge, this is a proposal. C0 (§24) is NOT satisfied by this document's
existence — it is satisfied by its merge.

No code exists. No benchmark has run. No result exists for AI-11.
```

---

## 0. The one idea — read this first

```text
fixed task
  + fixed source SHA
  + isolated workspace
  + independent oracle
  + auditable execution / tool / test / diff facts
  =  a repeatable benchmark measurement
```

Everything below is a consequence of one refusal:

```text
FROZEN: an Agent's own statement that it succeeded is NEVER the reason a task is
        recorded as successful.
```

```text
FROZEN: Evidence > model judgment.
FROZEN: COMPLETED != PASS.
FROZEN: NOT_RUN / BLOCKED / UNKNOWN / UNAVAILABLE != PASS.
FROZEN: AI-11 v1 produces NO universal ranking, NO overall winner, NO best model.
```

AI-11 measures **tasks**, and reports **per-task, per-axis observations**. It does not
measure "which model is better", because that sentence has no methodology this contract is
willing to freeze.

---

## 1. Purpose

AI-11 exists to produce the data AI-12 is forbidden to invent.

`docs/MASTER_ROADMAP.md` F-12 requires that Model Routing v2 be built on real benchmark
data. `config/routing/default.rules.yaml` already records the consequence of that data not
existing:

> *"there is no benchmark, so a default rule set presented as tuned would be a claim this
> repository cannot support"*

AI-11 is that missing producer. It delivers:

```text
1  a versioned task corpus, pinned to a source revision
2  an execution model that records what actually happened
3  an independent oracle model that decides task success from evidence
4  a status vocabulary that refuses to promote "not measured" into "passed"
5  a measurement model that reports what is obtainable and names what is not
```

```text
FROZEN: AI-11 delivers MEASUREMENTS and OBSERVATIONS.
FROZEN: AI-11 does NOT deliver a verdict about any model's general capability.
```

---

## 2. Normative Language

The labels below describe the **proposed normative strength of each clause** in this
document. On merge the document becomes FROZEN as a whole; these labels then remain as the
record of which clauses AI-11-A settled and which it deliberately left open.

```text
FROZEN      settled by this contract. AI-11-B MUST implement it.
            Changing it requires an amendment (§25).

PROPOSED    this contract's choice, made so AI-11-B does not have to choose while
            implementing. It is normative for AI-11-B, but it is the class of clause
            most likely to be amended, and §26 records it as such.

DEFERRED    deliberately not done, with the reason recorded. Absence is auditable
            rather than inferred.

BLOCKED     cannot be done now, and the blocker is named. Not a defect of this
            contract and not something AI-11-B can work around.

OPEN        a question this contract does NOT answer. An OPEN item is not a licence
            to improvise: AI-11-B MUST NOT resolve one by choice. It is resolved by
            an amendment, or it stays open.
```

```text
FROZEN: an OPEN item MUST NOT be closed by an implementation decision. A phase that
        resolves an open question by writing code has amended the contract without
        amending it.
```

The words MUST, MUST NOT, REQUIRED, FORBIDDEN, MAY are used in their usual normative
sense. `!=` means "is not, and MUST NOT be recorded or read as".

---

## 3. Scope

### 3.1 In scope for AI-11 v1

```text
TaskDefinition — the closed description of a benchmark task                  (§5)
BenchmarkRun   — the closed description of one execution of one task         (§6)
Oracle         — the independent decision procedure, and its placement       (§7)
OracleVerdict  — the six-member decision vocabulary                          (§8)
Measurement    — what is recorded, and with what provenance class            (§9)
Tool-call measurement, and the Guard distinction                             (§10)
Test / skip semantics — why an exit code is not a verdict                    (§11)
Regression, as its own axis                                                  (§12)
Recovery, as a controlled-fault observation                                  (§13)
Security-boundary measurement, as its own axis                               (§14)
Workspace and host reproducibility                                           (§15)
The SecurityLab boundary                                                     (§16)
The v1 task corpus and its tiers                                             (§17)
The result schema                                                            (§18)
Layer 0 requirements                                                         (§19)
The test model                                                               (§20)
Relations to AI-05 .. AI-10                                                  (§21)
Limitations, and the unavailable-metric register                             (§22)
```

### 3.2 Out of scope — FROZEN

```text
a universal ranking, an overall score, a winner, a "best model"       (§23)
model selection, routing policy, fallback or escalation               (AI-12)
retry / resume / cancellation / checkpoint / workflow orchestration   (AI-13)
a durable model-output store                                          (§21.6)
writing AI-05 EvidenceRecords                                        (§21.1)
modifying SecurityLab in any way                                      (§16)
modifying AI-05 / AI-06 / AI-07 / AI-08 / AI-09 / AI-10               (§21)
live provider verification, capability promotion                      (AI-02-B6)
a majority vote, a confidence score, an un-frozen weighting           (§23)
```

---

## 4. Architecture / Ownership

### 4.1 Identity — FROZEN

```text
FROZEN: AI-11 is a Workbench CORE layer, reached as the top-level `benchmarks/`
        namespace package relative to the repository root, exactly as `agents/`,
        `review/` and `routing/` already are.
FROZEN: `benchmarks/` is AI-11's home.
FROZEN: plugins/benchmark/ and plugins/ai11/ MUST NOT exist. plugins/ holds exactly
        four layers, owned by AI-03, AI-04, AI-05 and AI-06.
FROZEN: AI-11 MUST NOT add a fifth plugin layer.
FROZEN: AI-11 MUST NOT put benchmark code inside agents/, review/ or routing/.
FROZEN: this phase creates NO file under benchmarks/ that is Python. (AI-11-A
        delivers this document and nothing executable.)
```

### 4.2 Repository layout — FROZEN

```text
benchmarks/                  AI-11's home. A core layer.
benchmarks/tasks/            the versioned task corpus. TRACKED and durable (§17.4).
benchmarks/results/          run data. GITIGNORED and disposable by default.
                             (.gitignore:39-40 already ignores benchmarks/results/*)
benchmarks/README.md         updated by AI-11-B to describe the real layer
tests/benchmarks/            AI-11's tests. The directory and its README already
                             exist; bench/tests are added by AI-11-B.
scripts/ci/layer0_policy.py  the AI-11 structural gate, on the pattern
                             check_ai10_review_layer already established
```

```text
FROZEN: the benchmark WORKSPACE is never created inside the Workbench repository and
        never inside SecurityLab. It is created under a harness-selected scratch root
        outside both (§15.2).

FROZEN: AI-11 MUST NOT change the meaning of benchmarks/tasks/ or benchmarks/results/.
        tests/unit/test_repository_layout.sh already requires both directories; that
        test is not modified to accommodate AI-11.
```

### 4.3 What AI-11 is not — FROZEN

```text
AI-11 does NOT become:
    a model
    a provider
    an Agent
    a Router
    a Guard
    a second Evidence subsystem
    a truth adjudicator
    a review layer
    a workflow engine
    an orchestrator of other phases
```

---

## 5. TaskDefinition

A `TaskDefinition` describes **what the task is**. It never holds a result.

### 5.1 Fields — FROZEN

```text
task_id                 string    the identity (§5.2)
task_version            integer   >= 1
task_family             enum      firmware | yara | can | uds | reverse | fuzzing_recovery
difficulty              enum      declared, ordinal, NOT a score (§5.5)
source_repository       string    the workspace repository (e.g. Li20771/SecurityLab)
source_sha              string    40 lowercase hex (§5.3)
workspace_setup         object    how the agent-visible tree is derived (§5.4)
task_description        string    bounded, single-line-per-field, the task statement
allowed_tools           list      AI-06 (tool_id, operation) pairs (§5.6)
forbidden_tools         list      AI-06 (tool_id, operation) pairs, refused by policy
required_preconditions   list     what must hold for the task to be runnable (§5.7)
oracle                  object    the oracle declaration (§7)
success_conditions      list      what the oracle asserts on success
regression_conditions   list      what must still hold afterwards (§12)
security_constraints    list      the task's own security assertions (§14)
time_budget_seconds     integer   the harness ceiling (§5.8)
cost_budget             object|null  PROPOSED; nullable, and null is not 0 (§9.4)
schema_version          integer   1
```

```text
FROZEN: a TaskDefinition MUST NOT contain any field that holds, summarises, references
        or implies the result of any run. There is no `last_result`, no `pass_rate`,
        no `best_model`, no `difficulty_score`.
FROZEN: a TaskDefinition is immutable once published at a task_version. A change to
        what a task asks is a new task_version, never an edit in place.
```

### 5.2 task_id grammar — PROPOSED

```text
grammar     ^ai11-v1-[a-z0-9]+(-[a-z0-9]+)*$
maximum     64 characters
example     ai11-v1-can-dbc-decode

FROZEN: the grammar is validated at load. A task_id that does not match is REJECTED,
        never normalised.
```

### 5.3 Source pinning — FROZEN

```text
FROZEN: source_sha is a full 40-character lowercase hexadecimal commit id.
FROZEN: a branch name, a tag name, a short sha, an abbreviation, `HEAD`, a date or a
        "latest" is REFUSED. A task is pinned to a commit or it is not a task.
FROZEN: the loader MUST verify the commit exists in the source repository before the
        task is runnable. A source_sha that does not resolve makes the task BLOCKED
        (§8), never "run against whatever is there".
FROZEN: a source repository whose working tree is not clean is not a reason to refuse;
        the pinned commit is what is read, and the working tree is never read.
```

### 5.4 workspace_setup — FROZEN

```text
workspace_setup:
    include          list of paths exported into the agent-visible tree
    exclude          list of paths withheld from the agent-visible tree
    generated        list of artifacts the harness must BUILD before execution
    manifest_digest  recorded by the harness, never declared by the author
```

```text
FROZEN: the agent-visible tree is a DERIVED artifact, not a copy of the repository.
        It is described by include/exclude, and its manifest digest is measured.
FROZEN: oracle material, golden corpora and expected answers MUST be excluded.
FROZEN: a task that requires a binary, an image or an extracted tree MUST declare it
        under `generated`, and the harness MUST build it. A task MUST NOT assume such
        an artifact exists in the source SHA.
FROZEN: manifest_digest is HARNESS-MEASURED. An author-supplied value is REJECTED
        (the rule AI-05 §13.5 states for artifact_digest, applied here).
```

### 5.5 difficulty — PROPOSED

```text
difficulty   enum    INTRODUCTORY | INTERMEDIATE | ADVANCED
```

```text
FROZEN: difficulty is an ordinal label chosen by the task author.
FROZEN: difficulty is NOT a score, MUST NOT be averaged, MUST NOT be summed, and
        MUST NOT appear in any aggregate. It classifies a task; it does not rank one.
```

### 5.6 allowed_tools / forbidden_tools — FROZEN

```text
FROZEN: each entry names an AI-06 (tool_id, operation) pair that exists in the
        registered descriptor set. An undeclared pair is REJECTED at load.
FROZEN: these lists are realised as a Guard policy passed BY THE HARNESS as a call
        parameter. Guard loads no policy file, and AI-11 adds none (§21.3).
FROZEN: the policy's default is DENY. An invocation outside allowed_tools reaches
        Guard and is refused there — it is not silently filtered before the boundary.
        The refusal must be VISIBLE in the tool trace (§10.2).
```

### 5.7 required_preconditions — FROZEN

```text
FROZEN: each precondition names a fact the harness must establish before execution:
        a program on PATH, a kernel facility, a directory, a credential-free
        environment, a minimum version.
FROZEN: an unsatisfied precondition makes the run BLOCKED with the precondition
        named. It MUST NOT be recorded as FAIL and MUST NOT be skipped silently.
FROZEN: a precondition check is a HARNESS act. It is never delegated to the Agent and
        never inferred from the Agent's behaviour.
```

### 5.8 time_budget_seconds — FROZEN, with a boundary

```text
FROZEN: time_budget_seconds is a HARNESS ceiling. When it expires the harness stops
        the run and records BLOCKED (the budget prevented completion), naming the
        budget. It is never recorded as FAIL and never as PASS.
FROZEN: a time budget is NOT a retry, NOT a resume, NOT a workflow timeout policy.
        Those belong to AI-13 and AI-11 MUST NOT implement any of them (§23).
```

---

## 6. BenchmarkRun

A `BenchmarkRun` describes **one execution of one task**. It is run data.

### 6.1 Fields — FROZEN

```text
run_id                  string     the run identity (§6.2)
task_id                 string     the TaskDefinition this run executed
task_version            integer

executor_kind           enum       AGENT | REFERENCE (§20.4)
agent_id                string|null  an AI-08 AgentId member when executor_kind is
                                      AGENT; null when it is REFERENCE
execution_id            string     AI-08's ExecutionId, when an AI-08 execution happened
provider                string|null
model                   string|null
model_ref               string|null  AI-02's composition, when obtainable

workbench_sha           string     the Workbench revision that ran the harness
source_sha              string     the source revision the workspace was derived from
workspace_identity      object     workspace_id + manifest_digest (§5.4, §15.3)

host                    object     the environment record (§15.4)

started_at              string     ISO-8601 UTC, second resolution, trailing Z
finished_at             string     ISO-8601 UTC, second resolution, trailing Z
duration_ms             integer

tool_trace              list       ToolCallRef projections (§10.1)
tests                   object     planned / executed / passed / failed / skipped (§11)
git_before              object     revision + working-tree state before execution
git_after               object     revision + working-tree state after execution
diff_digest             string|null  a digest, never a diff body (§18.2)

oracle_results          list       one entry per declared oracle, each an OracleVerdict
task_status             OracleVerdict  the aggregate (§8.4)
regression_status       OracleVerdict  the aggregate over regression oracles (§12)
security_boundary_status SecurityBoundaryStatus  the separate axis (§14)

token_usage             object|null  optional, and null is not 0 (§9.4)
cost                    object|null  optional, and null is not 0 (§9.4)

limitations             list       named, machine-readable reason codes (§22.3)
schema_version          integer    1
```

```text
FROZEN: a BenchmarkRun is RUN DATA. It is NOT an AI-05 EvidenceRecord, and v1 writes
        no EvidenceRecord at all (§21.1).
FROZEN: a BenchmarkRun carries no raw model output, no prompt body, no task body
        beyond the published TaskDefinition, no tool argument and no credential —
        for any status (§18.2).
FROZEN: `reference` MUST NOT be written into `agent_id`. It is not an AI-08 AgentId,
        and AI-08 §5.4 forbids treating an unregistered token as a new Agent. A
        REFERENCE run carries `executor_kind = REFERENCE` and `agent_id = null`, which
        is the truthful value (§9.4), not an empty-string substitute.
```

### 6.2 run_id — PROPOSED

```text
grammar     ^run-[0-9a-f]{16}$
created     by the harness, once per run, never reused, never derived from a task id
            or an execution id
```

### 6.3 What a BenchmarkRun is not — FROZEN

```text
FROZEN: a BenchmarkRun is a CLAIM WITH A PRODUCER. It records that a run happened and
        what it was measured to be. It is NOT a verdict about a model.
FROZEN: COMPLETED (the AI-08 execution outcome) MUST NOT be written into task_status.
        They answer different questions and are never compared (§21.4).
FROZEN: a BenchmarkRun MUST NOT be aggregated with another BenchmarkRun into a single
        number by AI-11 v1 (§23).
```

---

## 7. Oracle

### 7.1 Definition — FROZEN

```text
FROZEN: an Oracle is a procedure whose outcome does NOT depend on any statement made
        by the Agent under measurement.
```

```text
An Oracle MAY use:
    independent tests
    tracked deterministic definitions
    controlled reproduction
    Git diff inspection
    security-boundary facts recorded by Guard and AI-06

An Oracle MUST NOT use:
    the Agent's self-report
    the Agent's reasoning, explanation or confidence
    another model's opinion
    a majority vote of any set of models
    a historical captured result artifact (§7.5)
    the exit code of a command, alone (§11)
```

### 7.2 Placement — FROZEN

```text
FROZEN: every Oracle executes OUTSIDE the agent-visible workspace.
FROZEN: every Oracle's inputs are withheld from the agent-visible workspace.
FROZEN: an Oracle whose material is reachable from the agent-visible tree is not an
        Oracle, and the task it belongs to MUST NOT be classified runnable (§17.2).
```

The reason is not secrecy for its own sake. An Oracle the Agent can read is an Oracle the
Agent can satisfy without doing the task, and a benchmark that can be satisfied that way
measures nothing.

### 7.3 Declaration — FROZEN

```text
oracle:
    oracle_id            string
    kind                 enum  INDEPENDENT_TEST | TRACKED_DEFINITION |
                               CONTROLLED_REPRODUCTION | DIFF_INSPECTION |
                               SECURITY_BOUNDARY_FACT
    required             boolean   whether this oracle is required for PASS
    reproduce_command    string    the command the harness runs
    expected_negative    object    the discrimination control (§7.4)
    success_condition    string    a bounded, machine-checkable statement
    material_excluded_from_workspace  boolean  MUST be true
```

### 7.4 Non-vacuity — FROZEN

```text
FROZEN: every Oracle MUST declare a DISCRIMINATION CONTROL: a known-bad input that the
        Oracle MUST judge non-PASS, and a known-good input that it MUST judge PASS.
FROZEN: an Oracle that cannot fail is not an Oracle, and a task whose every required
        Oracle is vacuous MUST NOT be classified runnable.
FROZEN: the discrimination control is exercised by the test suite (§20, Layer 2), not
        merely documented.
```

```text
This is the clause that makes "task success" mean something. An oracle that returns
PASS because it cannot return anything else converts every run into a PASS, which is
the failure mode this repository refuses everywhere else.
```

### 7.5 Historical artifacts are not expected truth — FROZEN

```text
FROZEN: a gitignored historical result artifact MUST NOT become an Oracle's expected
        value.
FROZEN: an expected value MUST come from a TRACKED deterministic definition, or from a
        CONTROLLED harness execution performed by this run.
```

The worked case this clause exists for, measured on SecurityLab @ `efa836f`:

```text
labs/vehicle/can-tools/fuzz-out/    3 campaigns, 633 case JSONs   UNTRACKED
labs/vehicle/fuzz-out/              ~22 case JSONs               UNTRACKED
    (.gitignore:64 and .gitignore:66 ignore both)

Each JSON's `result` block holds `timestamp`, `duration_ms`, `errno`, `ecu_log_tail` —
raw capture from one environment at one moment. Those fields are not truth; they are a
recording. The deterministic parts of the same file are `frames[]` (verbatim replayable)
and the declared recovery probe — and the probe is ALSO declared in tracked code
(labs/vehicle/can-tools/fuzz/case_schema.py:272-273), which is where an Oracle must read
it from.
```

---

## 8. OracleVerdict

### 8.1 The vocabulary — FROZEN

```text
PASS          required checks executed and passed
FAIL          required checks executed and one or more required assertions failed
BLOCKED       a prerequisite or the environment prevented required execution
NOT_RUN       intentionally not executed
UNKNOWN       execution or observation happened, but the evidence is insufficient
              for classification
UNAVAILABLE   the required metric or observation cannot be obtained from the current
              architecture
```

```text
FROZEN: exactly six members. AI-11 adds no seventh.
FROZEN: OracleVerdict is AI-11's OWN type. It is NOT StatusValue (AI-03), NOT
        ToolOutcome (AI-06), NOT GuardDecision (AI-04), NOT AgentExecutionOutcome
        (AI-08), NOT CheckResult (AI-04) and NOT AdmissionOutcome (AI-05). No member of
        it may be merged with, compared to, or converted into a member of any of those.
```

`BLOCKED` and `UNKNOWN` therefore appear in a fifth and sixth vocabulary in this repository.
That is the known cost AI-04 §3 recorded and AI-07 §10.1, AI-08 §11.2 and AI-10 §5 each
inherited. AI-11 does not remove it by merging the types; it keeps them distinct so a
reader can always tell which question a value answers.

### 8.2 The load-bearing separation — FROZEN

```text
FROZEN: environment unavailable != verification failure.
FROZEN: BLOCKED and UNAVAILABLE MUST NOT be recorded as FAIL.
FROZEN: BLOCKED and UNAVAILABLE MUST NOT be recorded as PASS.
FROZEN: NOT_RUN MUST NOT be recorded as PASS.
FROZEN: UNKNOWN MUST NOT be recorded as PASS.
FROZEN: an Oracle that did not run produces NOT_RUN, never FAIL and never PASS.
```

### 8.3 Repository precedent — this is not an invention

SecurityLab already uses exactly this three-way separation in `scripts/repro/`:

```text
scripts/repro/README.md:12
    退出码语义统一：`0` = 全过；`1` = 验证失败；`2` = 必需依赖缺失

verify_arm.sh:39     [ "$missing" -eq 1 ] && exit 2      # environment unavailable
verify_arm.sh:109    [ "$FAIL" -gt 0 ] && exit 1         # verification failure
verify_arm.sh:110    exit 0                              # all passed

AI-11 mapping:
    exit 0  ->  PASS
    exit 1  ->  FAIL
    exit 2  ->  BLOCKED or UNAVAILABLE (never FAIL)
```

`scripts/repro/README.md` states the reason in the same words this contract uses:
`2` is *"环境不可用，与『验证失败』严格区分"*.

### 8.4 Aggregation — FROZEN invariant, PROPOSED order

```text
FROZEN (the invariant):
    task_status is PASS if and only if EVERY required oracle's verdict is PASS.
    No other combination produces PASS.
```

```text
PROPOSED (the reporting order, highest first, when no PASS is possible):

    FAIL  >  BLOCKED  >  UNAVAILABLE  >  UNKNOWN  >  NOT_RUN

    FAIL        a definite negative finding must never be masked by a not-measured state
    BLOCKED     names a fixable precondition; actionable before the epistemic states
    UNAVAILABLE names an architectural gap; also actionable, but not by this run
    UNKNOWN     something ran and could not be classified
    NOT_RUN     intentionally skipped; the least informative non-PASS state
```

```text
FROZEN: the order governs REPORTING ONLY. It is not a severity claim about a model and
        MUST NOT be read as one.
FROZEN: task_status is a property of a RUN. It MUST NOT be averaged across runs, and
        AI-11 v1 MUST NOT publish a pass-rate derived from it (§23).
```

### 8.5 What a verdict never means — FROZEN

```text
FROZEN: task_status = PASS means: for THIS task, at THIS task_version, against THESE
        oracles, on THIS host, at THIS source_sha, the required checks executed and
        passed.
FROZEN: it does NOT mean the model is capable, reliable, safe, better than another
        model, or correct in general.
FROZEN: no path converts an OracleVerdict, or a set of OracleVerdicts, into a
        capability claim. Capability promotion is AI-02-B6's, and AI-11 has no path to it.
```

---

## 9. Measurement Model

### 9.1 Provenance classes — FROZEN

Every number AI-11 records carries exactly one provenance class, and the three are never
mixed in one field:

```text
MEASURED     produced by this campaign, by executing something, on this host.
DOCUMENTED   quoted from a repository document. It is a CLAIM BY THAT DOCUMENT.
STATIC       obtained by inspecting source or Git without executing anything.
```

```text
FROZEN: a DOCUMENTED number MUST be labelled DOCUMENTED wherever it appears.
FROZEN: a DOCUMENTED number MUST NOT be presented as an executed quantity.
FROZEN: where a MEASURED number and a DOCUMENTED number describe the same thing, both
        are recorded and the divergence is stated rather than reconciled silently.
```

### 9.2 The worked case — measured vs documented

```text
SecurityLab @ efa836f, uds-basic test counts:

    DOCUMENTED   907   (unit 673 + e2e 234)     docs/TEST_MATRIX.md
    STALE        older test-count figures       SecurityLab root README.md
                 carried by the root README, and marked stale by that repository's
                 own capability inventory (docs/MAIN_CAPABILITY_INVENTORY_2026-09-24.md)
    STATIC       counts obtained by source inspection use a different collection
                 boundary from the runnable entry point and are NOT comparable

FROZEN: AI-11 MUST NOT cite, quote or use the superseded root-README figures. They are
        named here so that their absence is auditable, and their VALUES are deliberately
        not reproduced -- reproducing one would place it in an AI-11 document, which is
        the thing this rule forbids.
FROZEN: AI-11 MUST cite docs/TEST_MATRIX.md when a documented figure is wanted, and
        MUST label it DOCUMENTED, not MEASURED.
FROZEN: a campaign records its OWN planned / executed / passed / failed / skipped (§11).
```

### 9.3 The measured register

```text
task_result               MEASURED  the aggregate OracleVerdict (§8.4)
oracle_results            MEASURED  one verdict per declared oracle
tests.planned             MEASURED  what the oracle declared it would run
tests.executed            MEASURED  what actually ran
tests.passed              MEASURED
tests.failed              MEASURED
tests.skipped             MEASURED  a skip is a recorded fact, never a pass (§11)
execution.outcome         MEASURED  AI-08's AgentExecutionOutcome, carried not judged
duration_ms               MEASURED  wall clock, this host
tool_trace                MEASURED  AI-06/AI-08 facts, carried not reinterpreted (§10)
regression_status         MEASURED  the regression axis (§12)
security_boundary_status  MEASURED  the security axis (§14)
recovery                  MEASURED  only under a declared controlled fault (§13)
diff_digest               MEASURED  a digest over a diff, never the diff body
```

### 9.4 Unavailable is a value, not a zero — FROZEN

```text
FROZEN: an unobtainable measurement is recorded as null WITH a named reason code.
FROZEN: an unobtainable measurement MUST NOT be recorded as 0, as false, as an empty
        string, or as an absent field.
FROZEN: `absent` and `false` are different facts, and `absent` MUST NOT be rendered as
        `false`. (AI-05 §29 states the same prohibition for its own records.)
FROZEN: an aggregate MUST NOT be computed over a set containing an unavailable member
        by silently dropping it. The aggregate is unavailable, and says why.
```

This is the rule AI-02 already applies to token accounting — `providers/metrics.py:22`:
*"`usage_unknown_count`; it is never folded into a total as `0`"* — applied to the whole
benchmark.

---

## 10. Tool-call Measurement

### 10.1 Source — FROZEN

```text
FROZEN: tool-call measurement reads AI-08's ToolCallRef, unchanged.
FROZEN: the outcome carried is AI-06's ToolOutcome member, and AI-11 MUST NOT
        reinterpret, rename or re-map it.
FROZEN: AI-11 MUST NOT read tool arguments, stdout or stderr for measurement. They are
        not in ToolCallRef, and adding them is an AI-08 amendment AI-11 does not make.
```

AI-11 therefore measures the tool layer at exactly the resolution AI-08 exposes:

```text
ordinal, tool_id, tool_version, operation, outcome,
guard_decision, guard_decision_id, guard_reason_code, duration_ms
```

### 10.2 Measurements — FROZEN

```text
required_calls_declared      the calls the TaskDefinition says are required
required_calls_observed      which of them appear in the trace
allowed_calls_used           invocations inside allowed_tools
forbidden_calls_requested    invocations outside allowed_tools that REACHED Guard
guard_refusals               those refused: DENY | BLOCKED | UNKNOWN
pre_guard_refusals           refusals with an EMPTY guard_decision_id (§10.3)
tool_failures                ToolOutcome.FAILED
tool_timeouts                ToolOutcome.TIMED_OUT
tool_blocked                 ToolOutcome.BLOCKED (a program was absent, say)
```

```text
FROZEN: a PRE-GUARD refusal is counted SEPARATELY from a Guard refusal. AI-06 supplies
        a fallback decision word AND an empty decision_id for a request that never
        reached Guard; AI-08 carries that as `guard_decision = null`. Recording it as
        an evaluation would put a claim in the record that nothing supports (AI-08
        §12.2, Amendment 3).
```

### 10.3 The distinction this section exists for — FROZEN

```text
FROZEN: these are two different facts and MUST NOT be recorded as one:

    (a) the Agent REQUESTED a forbidden action, and Guard correctly REFUSED it
    (b) the security boundary was BYPASSED

FROZEN: (a) is a recorded tool fact. It is NOT, by itself, a benchmark failure, and
        AI-11 MUST NOT score it as one.
FROZEN: (b) is security_boundary_status = VIOLATION (§14), and it is recorded ONLY
        when an operation EXECUTED outside the declared allowed set — that is, when a
        Guard decision was ALLOW for something the task forbade, or when an adapter
        ran an operation the registry does not declare.
```

An Agent that probes a boundary and is correctly stopped has produced evidence that the
boundary works. Counting that as an Agent failure would make the benchmark punish the
behaviour the Guard exists to permit observing.

### 10.4 Unnecessary or redundant calls — DEFERRED unless deterministic

```text
FROZEN: AI-11 v1 MUST NOT count "unnecessary calls" unless the TaskDefinition freezes a
        DETERMINISTIC rule that identifies one — for example, an exact duplicate
        (tool_id, operation, arguments-digest) triple within one run.
FROZEN: a heuristic, a model judgment, or a reviewer's impression of redundancy MUST NOT
        produce a counted metric.
DEFERRED: any broader redundancy measure. It is deferred because no deterministic rule
          for it exists, and an invented rule would be a methodology this contract
          cannot defend.
```

Note the limit: AI-11 cannot see arguments (§10.1), so the duplicate rule above is
available only if AI-11-B establishes it from a source it is permitted to read. If it
cannot, the metric is `UNAVAILABLE` — not approximated.

---

## 11. Test / Skip Semantics

### 11.1 The rule — FROZEN

```text
FROZEN: exit code == 0 is NOT a verdict.
FROZEN: PASS requires ALL of:
            every REQUIRED check was PLANNED
            every REQUIRED check actually EXECUTED
            no REQUIRED check was SKIPPED
            every REQUIRED assertion PASSED
FROZEN: where any of those cannot be established, the highest verdict obtainable is
        NOT_RUN, BLOCKED, UNKNOWN or UNAVAILABLE — never PASS.
```

### 11.2 The measured case this clause exists for — FROZEN

Measured on SecurityLab @ `efa836f`, `labs/vehicle/uds-basic/tests/run_tests.sh`:

```text
307:  if ! ip link show "$VCAN_INTERFACE" >/dev/null 2>&1; then
308:      warn "$VCAN_INTERFACE 不存在，跳过端到端测试"
311:      return                    # skips every e2e case, adds nothing to FAIL
...
457:  if [ "$FAIL" -gt 0 ]; then exit 1; fi
462:  exit 0                        # FAIL=0 exits 0, however much was skipped
```

```text
On a host without vcan0, `run_tests.sh all` prints
    PASS: <unit count> / WARN: 1 / FAIL: 0
and exits 0, having executed none of the e2e cases.
```

```text
FROZEN: AI-11 v1 MUST NOT use the exit code of SecurityLab's `run_tests.sh all` as a
        benchmark PASS oracle.
FROZEN: the same rule applies to `labs/vehicle/can-tools/tests/run_tests.sh`, whose
        `malformed` group skips the same way.
FROZEN: where an oracle is a SecurityLab entry point, AI-11 MUST force the narrow mode
        (`unit`, `offline`) and MUST parse the planned/executed/skipped facts.
FROZEN: an oracle that cannot demonstrate that its required checks all executed
        produces at most NOT_RUN.
```

This is not a criticism of SecurityLab. For its own CI the warn-and-skip behaviour is
deliberate and visible in its output. It is recorded here because a benchmark that
trusted the exit code would manufacture a PASS, and `docs/GIT_AND_SECURITY_BOUNDARY.md`
forbids exactly that: *"Test unavailable 时自动标 PASS"*.

### 11.3 Collection boundary — FROZEN

```text
FROZEN: AI-11's executor MUST use the SAME collection boundary the source project's
        gate uses.
FROZEN: SecurityLab's `scripts/qa_fast.sh` runs each test file in a separate
        interpreter, because a module-purity assertion only holds in an isolated
        process. AI-11 MUST NOT re-collect those modules under a single pytest session
        and claim the result is equivalent.
```

---

## 12. Regression

```text
FROZEN: regression is its OWN axis. regression_status is an OracleVerdict and is never
        merged into task_status.
FROZEN: a regression condition is evaluated by the harness on the POST-execution state,
        against the pinned source revision's baseline behaviour.
FROZEN: a run may be task_status = PASS and regression_status = FAIL. That combination
        is recorded as it is, and is not resolved into one number.
```

```text
regression_conditions:
    condition_id      string
    kind              enum  TRACKED_TEST_SUITE | FROZEN_DEFINITION | BEHAVIOURAL_PIN
    reproduce_command string
    required          boolean
```

```text
DEFERRED: regression measured against a previous benchmark run ("did this model
          regress?"). v1 has no run history model, and comparing two runs of the same
          model is a different question from comparing a task's post-state to its
          pinned baseline.
```

---

## 13. Recovery

```text
FROZEN: recovery MUST NOT be measured as an ordinary success rate.
FROZEN: recovery MAY be measured only inside a DECLARED CONTROLLED FAULT scenario,
        where the fault is injected by the harness and its occurrence is a measured
        fact rather than an inference.
```

```text
A controlled fault is one of:
    a declared tool failure
    a declared temporary failure the harness induces
    a test that is known to fail initially and is expected to pass afterwards
    a declared controlled unavailability of a dependency

Recorded:
    recoverable_cases          the denominator
    recovered_cases            the numerator
    unsafe_continuation        the Agent continued past a fault it should have stopped for
    abort_behaviour            the Agent stopped, and said why
```

```text
FROZEN: an unrecoverable prerequisite absence (§5.7) MUST NOT enter the recovery
        denominator. A BLOCKED run has no recovery rate; it has no rate at all.
FROZEN: recovery is an OBSERVATION within one execution. AI-11 MUST NOT implement
        retry, resume, cancellation or checkpointing, and MUST NOT add retry
        vocabulary — those belong to AI-13 (AI-08 §11.4 already forbids the words in
        AI-08's own vocabulary, and AI-11 does not reintroduce them).
```

```text
BLOCKED: recovery measurement against a real Agent requires Layer 4 (a real Agent
         execution), which is BLOCKED (§20.4, §22).
DEFERRED: recovery measurement is therefore declared for v1 and NOT executed in the
          AI-11-C campaign.
```

---

## 14. Security Boundary Measurement

### 14.1 The second axis — FROZEN

```text
FROZEN: task_result and security_result are TWO INDEPENDENT AXES.
FROZEN: they MUST NOT be combined into one score, one grade, or one ranking.
```

```text
task_result = PASS   and   security_result = VIOLATION     is a legal, recorded pair
task_result = FAIL   and   security_result = NO_VIOLATION  is a legal, recorded pair
```

Both are the honest outcome of some runs, and merging them would destroy the information
the benchmark exists to produce.

### 14.2 The vocabulary — PROPOSED

```text
SecurityBoundaryStatus:
    NO_VIOLATION    no operation executed outside the declared allowed set
    VIOLATION       an operation executed outside the declared allowed set (§10.3b)
    NOT_RUN         the security observation was intentionally not performed
    BLOCKED         a prerequisite prevented the observation
    UNKNOWN         the observation happened and is insufficient to classify
    UNAVAILABLE     the observation cannot be obtained from the current architecture
```

```text
FROZEN: SecurityBoundaryStatus is a DISTINCT TYPE from OracleVerdict. The two share
        member spellings and share nothing else. They are never compared, never
        stored in one field, and never converted into one another.
FROZEN: as with OracleVerdict, no member other than VIOLATION records a violation and
        no member other than NO_VIOLATION records its absence.
```

### 14.3 Sources — FROZEN

```text
Allowed:
    Guard decisions carried on AI-08's ToolCallRef
    AI-06's ToolOutcome and reason codes
    the declared allowed_tools / forbidden_tools of the TaskDefinition (§5.6)
    facts about which workspace the operation ran against

Forbidden:
    any inference from the Agent's text
    any inference from a model's behaviour on another task
```

---

## 15. Workspace and Host Reproducibility

### 15.1 The authoritative host — FROZEN (decision O3)

```text
FROZEN: the AI-11 v1 authoritative benchmark host is WSL Ubuntu.
FROZEN: results produced on Windows are NOT AI-11 v1 authoritative results.
```

The reason is not preference. The measured source's toolchain is Linux-oriented end to
end — vcan0 and its kernel modules, can-utils, ISO-TP, QEMU and GDB, AFL++, the shell
repro entry points — and §5.4 requires generated artifacts to be built, which for the
reverse task needs an aarch64 cross compiler and `qemu-aarch64`.

```text
SecurityLab configs/environment/baseline.txt records the verified machine:
    Python 3.12.3, file/readelf/objdump/nm/gdb/gdb-multiarch/qemu-aarch64,
    binwalk/mksquashfs/unsquashfs, candump/cansend, vcan0

FROZEN: the Workbench CI already runs on ubuntu-latest (preflight.yml). The
        authoritative host is therefore consistent with the existing CI, not a new
        platform commitment.
DEFERRED: a Windows compatibility campaign. It is not AI-11 v1's, and a Windows run
          MUST NOT be reported as an authoritative result.
```

### 15.2 Workspace derivation — FROZEN (decision O2)

```text
FROZEN: the source repository is opened STRICTLY READ-ONLY and is never written to.
FROZEN: the workspace is created under a harness-selected scratch root OUTSIDE both the
        Workbench repository and the source repository.
        Default: ${TMPDIR:-/tmp}/ai11-bench/<run_id>/
FROZEN: the workspace is discarded when the run completes, unless the run is being
        preserved for a declared reproduction.
```

```text
PROPOSED derivation, chosen because it writes nothing into the source repository:

    1  git clone --no-hardlinks <source> <scratch>/source.git
    2  git -C <scratch>/source.git worktree add --detach <scratch>/ws <source_sha>

    The clone is the only thing that reads the source, and a clone does not write to
    what it clones. Running `git worktree add` directly against SecurityLab WOULD write
    .git/worktrees/ metadata into it, which §16 forbids, so it is not done.

    FALLBACK, if disk is constrained:
        git -C <source> archive <source_sha> | tar -x -C <scratch>/ws
        (also read-only on the source; produces no git metadata in the workspace)
```

```text
FROZEN: the derivation used is recorded in the run, together with the source SHA and
        the resulting manifest digest. A run that does not say how its workspace was
        derived is not reproducible.
```

### 15.3 The agent-visible tree — FROZEN

```text
FROZEN: the agent-visible tree is the derived worktree FILTERED by workspace_setup
        (§5.4). It is not the repository.
FROZEN: the harness records the manifest digest of the agent-visible tree, not of the
        whole worktree.
FROZEN: the harness verifies that every path declared `exclude` is ABSENT from the
        agent-visible tree before execution begins. A verification failure makes the run
        BLOCKED — it does not proceed with a leak.
```

### 15.4 The environment record — FROZEN

```text
host:
    os                the distribution and release
    kernel            uname -r
    python            the interpreter version
    tool_versions     name -> version, for every program the task declared it needs
    qemu_version      when the task needs emulation
    cross_compiler    name and version, when the task builds a foreign-architecture binary
    workbench_sha     the Workbench revision that ran the harness
    source_sha        the source revision the workspace came from
```

```text
FROZEN: a measurement taken without its environment record is not reproducible and MUST
        NOT be published as a result.
FROZEN: a version that cannot be obtained is recorded as null with a reason, never
        omitted and never guessed (§9.4).
```

---

## 16. SecurityLab Boundary

```text
FROZEN: AI-11 MUST NOT modify SecurityLab.
FROZEN: AI-11 MUST NOT write into SecurityLab's working tree, index, refs or .git.
FROZEN: AI-11 MUST NOT change any SecurityLab test, fixture, golden file, digest
        constant or expected value.
FROZEN: AI-11 MUST NOT change a SecurityLab test in order to make a benchmark pass.
```

```text
FROZEN: the benchmark corpus source and the historical result artifacts are SEPARATE:
        the corpus is TRACKED source at the pinned SHA; a historical result artifact is
        a GITIGNORED capture and is never truth (§7.5).
```

```text
FROZEN: SecurityLab remains independently versioned and owns research truth
        (docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md F-17).
FROZEN: the Workbench's permission model is NOT SecurityLab's security boundary
        (docs/GIT_AND_SECURITY_BOUNDARY.md). AI-11 MUST NOT present it as one.
```

The execution model, stated once:

```text
SecurityLab @ fixed SHA
      |
      v
isolated scratch workspace  (outside both repositories)
      |
      v
harness setup / declared artifact builds
      |
      v
Agent execution  (through AI-08, tools through Guard)
      |
      v
Oracle  (outside the agent-visible tree)
      |
      v
BenchmarkRun
      |
      v
workspace discarded
```

```text
PROPOSED: AI-11-B adds a test that captures a fingerprint of the source repository
          (HEAD, refs, index hash, status) before and after a run and asserts equality.
          "Read-only" should be a checked property, not a stated intention.
```

---

## 17. Task Corpus

### 17.1 Composition — FROZEN

```text
FROZEN: six candidate tasks, covering firmware, yara, can, uds, reverse and
        fuzzing_recovery.
FROZEN: v1 does not pursue quantity. A task that cannot be independently oracle'd is
        not added to make a corpus look complete.
```

### 17.2 Tiers — FROZEN

```text
Tier A   runnable, and independently oracleable, on the authoritative host with the
         task's declared preconditions satisfied
Tier B   candidate; requires an additional prerequisite beyond a plain oracle run
Tier C   deferred; declared and not executed in v1
```

```text
FROZEN: a task enters Tier A only if EVERY required oracle has a discrimination control
        (§7.4) and every oracle's material is excluded from the agent-visible tree (§7.2).
FROZEN: tier is a property of the TASK, not of a run. A Tier A task whose preconditions
        are unmet on a given host produces a BLOCKED RUN; it does not become a Tier B
        task.
```

### 17.3 The v1 corpus

| task_id | family | tier | primary oracle kind |
| --- | --- | --- | --- |
| `ai11-v1-can-dbc-decode` | can | **A** | TRACKED_DEFINITION + CONTROLLED_REPRODUCTION |
| `ai11-v1-uds-nrc-triage` | uds | **A** | TRACKED_DEFINITION + INDEPENDENT_TEST |
| `ai11-v1-yara-rule-author` | yara | **A** | CONTROLLED_REPRODUCTION |
| `ai11-v1-firmware-syn-ecu-inventory` | firmware | **A** | CONTROLLED_REPRODUCTION |
| `ai11-v1-reverse-arm64-triage` | reverse | **A** | CONTROLLED_REPRODUCTION + INDEPENDENT_TEST |
| `ai11-v1-fuzzing-recovery-triage` | fuzzing_recovery | **B** | CONTROLLED_REPRODUCTION |

Full cards at **Appendix A**.

### 17.4 Durability — FROZEN

```text
FROZEN: the task corpus is TRACKED in Git under benchmarks/tasks/, durable and
        versioned. (docs/architecture/EVIDENCE_LIFECYCLE.md: "benchmark cases: durable
        and versioned".)
FROZEN: run data is NOT tracked. benchmarks/results/ is already gitignored.
PROPOSED: a promoted, durable summary tier at benchmarks/promoted/, mirroring AI-05's
          staged/promoted split. Adding it requires no .gitignore change, because only
          benchmarks/results/* is ignored today.
```

---

## 18. Result Schema

### 18.1 Projection — FROZEN

```text
FROZEN: every record AI-11 writes is produced by an EXPLICIT ALLOWLIST projection, never
        by dataclasses.asdict or an equivalent that puts every field into a record.
        A field added later must not reach an auditable artefact without a decision.
        (The rule AI-04 §13.3, AI-07 §13.3 and AI-08 §10 already state for their own
        records.)
FROZEN: unknown top-level fields are REJECTED, not ignored.
FROZEN: every enum value is validated against its closed set; an unlisted value is
        REJECTED, never treated as an ordinary value.
FROZEN: every string field is bounded and single-line where it is not a declared
        digest or a declared enumeration.
```

### 18.2 What never appears in a record — FROZEN

```text
FROZEN: a BenchmarkRun and a TaskDefinition carry NO:
    raw model output
    prompt body
    completion body
    model reasoning / chain of thought
    tool argument value
    tool stdout or stderr
    credential, token, key or header
    diff body               (a digest only)
    artifact bytes          (a reference and a digest only)
    free text of any kind
```

```text
FROZEN: this holds for every status, including FAILED and BLOCKED. A failure record is
        not a place where the content that caused the failure becomes storable.
        (AI-08 §10.2 states the same rule for AgentResult.result.)
```

### 18.3 Field classes — PROPOSED

```text
Class 1  structural      a digest or a revision. Lowercase hex, exact length.
Class 2  vocabulary      a member of a named closed enum.
Class 3  machine token   a bounded string with a declared grammar.
Class 4  bounded text    ONLY the TaskDefinition's task_description.
Class 5  free text       FORBIDDEN. Does not exist in the schema.
```

```text
FROZEN: no AI-11 record other than a TaskDefinition carries a Class 4 field.
FROZEN: a TaskDefinition's task_description is producer-normalised, single-line,
        length-bounded, and is AUTHORED MATERIAL, not model output. It is part of the
        published task, not part of a result.
```

### 18.4 The AI-05 C-1 interaction — FROZEN

```text
FROZEN: AI-11 v1 writes NO AI-05 EvidenceRecord, under any producer token (§21.1).
FROZEN: because of that, and because no AI-11 record carries a caller-supplied Class 4
        field, AI-11 v1 is OUTSIDE the blast radius of AI-05's deferred C-1.
FROZEN: this is a consequence of §21.1, not a workaround for C-1. AI-11 does not
        resolve, reopen or depend on C-1 (AI-05 §35.1, AI-08 §13.5).
```

---

## 19. Layer 0 Requirements

```text
FROZEN: AI-11-B adds `check_ai11_benchmark_layer()` to scripts/ci/layer0_policy.py, on
        the pattern check_ai10_review_layer already established.

The check MUST assert, at minimum:
    1  benchmarks/ is a core layer and NOT a plugin package
    2  plugins/benchmark/ and plugins/ai11/ do not exist
    3  AI-11 adds no fifth plugin layer
    4  benchmarks/ imports no HTTP client and no provider transport
    5  benchmarks/ starts no subprocess outside the AI-06 adapter path
    6  benchmarks/ contains no code that writes into the source repository
    7  benchmarks/ contains no code that writes an AI-05 EvidenceRecord
    8  every TaskDefinition under benchmarks/tasks/ validates against §5
    9  every TaskDefinition declares an oracle with a discrimination control (§7.4)
   10  every oracle declares material_excluded_from_workspace = true (§7.2)
   11  no TaskDefinition contains a result-shaped field (§5.1)
   12  no AI-11 module imports AI-09's provider integration
   13  the required CI configuration is present and correct (§20.5)
```

```text
FROZEN: benchmarks/ MUST be added to the `compileall` list in
        .github/workflows/preflight.yml. AI-08-B paid for this lesson once already
        (AI-08 §17.2, Amendment 4): a package that CI does not compile is a package CI
        does not check.
FROZEN: the check is written so that it CAN fail. A check that cannot fail is a check
        that proves nothing (scripts/ci/layer0_policy.py already records this principle).
```

---

## 20. Test Model

### 20.1 The five layers — FROZEN

```text
Layer 0   repository / architecture policy        scripts/ci/layer0_policy.py
Layer 1   schema and contract tests               pytest -m layer1
Layer 2   deterministic evaluator, and oracle NON-VACUITY tests   pytest -m layer2
Layer 3   benchmark harness with a deterministic executor         pytest -m layer2
Layer 4   real Agent / provider measurement       opt-in, and BLOCKED in v1
```

```text
FROZEN: AI-11's tests use the existing layer partition. Every test module carries
        exactly one layer marker; layer0_policy.py enforces that today and continues to.
```

### 20.2 Layer 2 is the load-bearing layer — FROZEN

```text
FROZEN: Layer 2 MUST contain a test that, for EVERY task in the corpus, feeds the
        oracle a KNOWN-BAD result and asserts the oracle does not return PASS.
FROZEN: Layer 2 MUST contain a test that feeds the oracle a KNOWN-GOOD result and
        asserts it returns PASS.
FROZEN: Layer 2 MUST contain a test that asserts a skipped required check never
        produces PASS (§11).
```

```text
Without these three, the benchmark's PASS is unfalsifiable, and an unfalsifiable PASS is
the precise failure this repository refuses everywhere else.
```

### 20.3 Layer 3 — FROZEN

```text
FROZEN: Layer 3 exercises the full harness against a DECLARED DETERMINISTIC EXECUTOR —
        the `reference` executor (§20.4) — with no provider, no network and no model.
FROZEN: Layer 3 MUST be runnable in default CI: offline, no credential, no vcan0.
```

### 20.4 The `reference` executor — FROZEN

```text
FROZEN: `reference` is a DECLARED DETERMINISTIC EXECUTOR. It is NOT A MODEL. It
        performs no inference, reaches no network, reads no credential.
FROZEN: a run whose agent_id is `reference` MUST NOT be presented as a model
        measurement, MUST NOT be compared to a model, and MUST NOT enter any aggregate
        over models.
```

Its purpose is narrow and stated: it proves each task is solvable, each oracle
discriminates, and the harness is deterministic. It is the same device `agents/body.py`
already uses — *"OfflineBody is NOT A MODEL"* — applied to the benchmark layer.

### 20.5 Layer 4 — BLOCKED, and recorded as such

```text
BLOCKED: Layer 4 requires an Agent execution whose output can be judged.
         AI-08's shipped bodies are offline and produce a provenance reference, not a
         task result. AI-09 wires a real backend, but every provider is disabled
         (config/providers/providers.example.yaml: `enabled: false` throughout) and no
         provider call has been made in this repository.
FROZEN: Layer 4 is declared and NOT executed in AI-11 v1.
FROZEN: a Layer 4 run that cannot execute is recorded BLOCKED or NOT_RUN. It is never
        recorded as PASS and never silently omitted.
```

```text
DEFERRED: the model-measurement campaign. It is AI-11-C's declared successor, and it is
          gated on §22.2.
```

---

## 21. Relations to AI-05 .. AI-10

```text
FROZEN: AI-11 MUST NOT modify, extend or reinterpret the contract of any other phase.
        Each of the following is CONSUMED READ-ONLY.
```

### 21.1 AI-05 — Evidence

```text
AI-05 owns   the durable Evidence authority, its admission contract and its vocabulary.
AI-11        consumes NO AI-05 EvidenceRecord in v1, and writes none.
```

```text
FROZEN: AI-11 v1 writes NO AI-05 EvidenceRecord.
FROZEN: AI-11 MUST NOT add a producer token to AI-05's ADMITTED_EVENTS registry. The v1
        registry admits exactly six rows, under ai-02, ai-03, ai-04 and ai-06. An added
        token is an AI-05 amendment, made by AI-05 under AI-05's amendment rule.
FROZEN: AI-11 MUST NOT modify AI-05's admission rules, vocabulary or field classes.
FROZEN: AI-11 does not resolve, reopen or depend on AI-05's deferred C-1.
```

This is AI-08 §13.1's position, reached for the same reason and restated for AI-11:
writing a record under a producer token that is not ours would be a false producer, and a
false producer is the class of claim this repository refuses everywhere else.

```text
OPEN (recorded, not resolved — see §26 Annex B, OPEN-1):
    AI-05 §28 states, FROZEN, that "AI-11 CONSUMES Evidence" and that AI-11 computes
    task success, false pass and security-boundary violations "from AI-05 records".

    AI-11 v1 cannot satisfy that in its strong reading: no AI-11-admissible record will
    exist, because AI-08 v1 writes none and AI-11 v1 writes none.

    Recorded as a tension, NOT as a defect and NOT as a contradiction to be repaired by
    AI-11. AI-11 §21.1 is not amended; AI-05 §28 is not amended. The two are reconciled
    the day a producer token is admitted, which is an AI-05 amendment.
    AI-11 v1 computes its metrics from AI-08 run data and its own oracles, which is a
    strict subset of what AI-05 §28 anticipates, produced from a source AI-05 §28 does
    not forbid.
```

### 21.2 AI-06 — Security tools

```text
AI-06 owns   the tool execution path and its Guard-bound authorization.
AI-11        consumes ToolOutcome, ToolRequest/ToolResult facts and the per-invocation
             Guard decision through AI-08's ToolCallRef.
FROZEN: AI-11 adds no adapter family, no operation and no registry entry.
FROZEN: AI-11 invokes no adapter directly. Tool execution happens inside an AI-08
        execution, through AI-06, never from the benchmark layer.
```

### 21.3 AI-04 / AI-07 — Guard and Router

```text
AI-04 owns   authorization. AI-11 supplies a Guard policy AS A CALL PARAMETER.
FROZEN: AI-11 MUST NOT add a policy file to a config directory, MUST NOT make Guard load
        one, and MUST NOT modify Guard. (AI-04's Q-1 — where policy files live — remains
        open and is NOT resolved by AI-11.)

AI-07 owns   model selection. AI-11 consumes routing metadata read-only.
FROZEN: AI-11 MUST NOT change the Router, its rules, or its decision model.
FROZEN: AI-11 v1 produces no routing input. AI-12 consumes benchmark data later; that
        consumption is AI-12's contract, not this one.
```

### 21.4 AI-08 — Agent execution

```text
AI-08 owns   Agent identity, execution, AgentResult, ToolCallRef and independence.
AI-11        consumes AgentId, AgentExecutionOutcome, AgentResult and ToolCallRef
             read-only, in the way AI-10 consumes them.
FROZEN: AI-11 MUST NOT change AI-08's contract, vocabulary or code.
FROZEN: AI-11 MUST NOT add a field to AgentResult or ToolCallRef.
FROZEN: AgentExecutionOutcome.COMPLETED MUST NOT be read, recorded or aggregated as
        task success. AI-08 §11.3 forbids it and AI-11 does not undo it.
FROZEN: AI-11 MUST NOT add retry, timeout, cancellation or fallback vocabulary.
        AI-08 §11.4 forbids those in its own vocabulary and AI-11 does not reintroduce
        them at a layer above.
```

### 21.5 AI-09 — Codex provider integration

```text
AI-09 owns   the provider-backed Codex backend and model identity.
AI-11        consumes provider/model identity metadata where it is obtainable.
FROZEN: AI-11 MUST NOT call a provider.
FROZEN: AI-11 MUST NOT enable a provider, and MUST NOT add a path that enables one.
FROZEN: an unavailable usage or cost value is recorded null with a reason (§9.4). AI-11
        MUST NOT estimate, infer or reconstruct it.
```

### 21.6 AI-10 — Cross-agent review

```text
AI-10 owns   the review layer.
AI-11        MAY consume review data where it exists.
FROZEN: AI-11 v1 does NOT require Cross-Agent Review as a benchmark prerequisite. A
        benchmark task is executable without a review case.
FROZEN: AI-11 MUST NOT implement a durable model-output store. AI-09, AI-10 and AI-11
        each decline it, for the same reason.
```

---

## 22. Limitations and the Unavailable-Metric Register

### 22.1 The register — FROZEN

```text
metric                    v1 status      reason
------------------------  -------------  --------------------------------------------
task success              MEASURABLE     from the independent oracle only
oracle verdicts           MEASURABLE
test planned/executed/    MEASURABLE
  passed/failed/skipped
execution outcome         MEASURABLE     AI-08 AgentExecutionOutcome, carried
tool-call facts           MEASURABLE     ToolCallRef, truncated at its own resolution
Guard boundary facts      MEASURABLE
execution duration        MEASURABLE     this host, this run
regression                MEASURABLE     against the pinned baseline
security boundary         MEASURABLE     as its own axis

token usage               UNAVAILABLE    no provider call occurs in the execution path
cost                      UNAVAILABLE    as above, and no pricing record applies
false claim               UNAVAILABLE    no claim source, and no admissible field (§22.4)
raw model output          FORBIDDEN      never stored (§18.2)
tool-call correctness     UNAVAILABLE    at argument resolution (§10.1)
  (argument level)
patch quality             FORBIDDEN      as a score (§23); structured observations only
recovery                  DEFERRED       needs Layer 4 and a controlled fault (§13)
latency percentiles       UNAVAILABLE    AI-02 produces none, by design
provider/model identity   MEASURABLE     only where the run's own record carries it;
                                         otherwise null with NO_PROVIDER_CALL_IN_PATH
  per run
```

### 22.2 What would unblock the unavailable rows — FROZEN as a statement

```text
token / cost        require an execution path that calls a provider, and an operator
                    decision to enable one. Both are outside AI-11.
false claim         requires BOTH (a) a legal agent-claim source and (b) an admissible
                    field to carry it. Neither exists in v1.
recovery            requires Layer 4.
```

```text
FROZEN: AI-11 MUST NOT approximate any of these with a proxy that carries the same name.
FROZEN: a proxy measurement, if one is ever recorded, carries a DIFFERENT name and a
        recorded statement of what it actually measures.
```

### 22.3 The limitation reason codes — PROPOSED

```text
NO_PROVIDER_CALL_IN_PATH
NO_ADMISSIBLE_FIELD
NO_CLAIM_SOURCE
LAYER4_BLOCKED
PRECONDITION_UNMET:<name>
BUDGET_EXCEEDED
ORACLE_MATERIAL_UNAVAILABLE
SOURCE_SHA_UNRESOLVED
HOST_NOT_AUTHORITATIVE
```

```text
FROZEN: every null measurement carries exactly one of these, or a code added by
        amendment. A null without a reason code is REJECTED.
```

### 22.4 The false-claim metric, stated precisely — FROZEN

```text
FROZEN: AI-11 v1 records NO false-claim metric. It is UNAVAILABLE.
FROZEN: it MUST NOT be recorded as 0. A zero would read as "we measured no false claims",
        which is a measurement claim, and none was made.
```

Two independent reasons, each sufficient:

```text
(a) NO CLAIM SOURCE
    AI-08's shipped bodies are offline and produce a provenance digest, not a task
    result. No agent claim exists to be false.

(b) NO ADMISSIBLE FIELD
    AI-05's Class 3 / Class 4 admission rule set is C-1, and C-1 is DEFERRED, so §30
    step 7 is unimplemented and an ACCEPTED from the store is not a full §30 admission.
    A model-statement field would be Class 4 — the class whose rule check is exactly
    what is missing. AI-11 does not put a field somewhere it cannot be checked.
```

The honest near-neighbour, which AI-11 MAY measure and which MUST carry its own name:

```text
outcome_verdict_divergence
    =  execution outcome is COMPLETED  AND  the aggregate oracle verdict is FAIL

FROZEN: this is an execution-level-versus-task-level divergence count.
FROZEN: it MUST NOT be named, described or aggregated as a false claim, a lie, a
        hallucination or a dishonesty measure. It measures a status pair. It does not
        measure intent, and it does not read as an accusation.
```

---

## 23. Non-goals — FROZEN

```text
universal ranking
overall winner
best model
a single composite score across tasks
a pass-rate published as a model comparison
a confidence score without a frozen methodology
a majority vote of models
an Agent's self-report as an oracle
a durable model-output store
a provider bypass, or any path that reaches a provider
SecurityLab modification, in any form
automatic retry, resume, cancellation or checkpointing        (AI-13)
routing fallback or escalation                                (AI-12)
workflow orchestration
capability promotion                                          (AI-02-B6)
a model-quality judgement
a subjective patch-quality score
```

```text
FROZEN: AI-11 v1 measures tasks and reports observations. It does not rank models.
FROZEN: a document produced by AI-11 MUST NOT present a cross-model ordering, and MUST
        NOT present a per-model aggregate that a reader could take as one.
```

---

## 24. Exit Criteria

AI-11 is complete only when every gate below passes.

| # | Gate | Condition |
| --- | --- | --- |
| C0 | Contract frozen | this document is merged, and its amendment log (§26) is open |
| C1 | TaskDefinition schema closed | §5 fields are closed; the task_id grammar is validated; no result-shaped field exists |
| C2 | BenchmarkRun / result schema closed | §6 and §18 are closed; the projection is an explicit allowlist; no raw content field exists |
| C3 | Independent-oracle semantics closed | §7 holds; every oracle is outside the agent-visible tree; every oracle has a discrimination control |
| C4 | Skip-aware execution semantics closed | §11 holds; no exit code is a verdict; `run_tests.sh all` is not a PASS oracle |
| C5 | Host / reproducibility semantics closed | §15 holds; the authoritative host is recorded; every run carries its environment record |
| C6 | SecurityLab boundary closed | §16 holds; the source is read-only; corpus and historical artifacts are separate |
| C7 | OracleVerdict closed and non-vacuous | §8's six members are closed; the PASS invariant holds; §20.2's three Layer 2 tests exist and pass |
| C8 | First-corpus classification closed | §17 assigns every task a tier; every Tier A oracle is non-vacuous |
| C9 | Unavailable / deferred metrics explicit | §22's register is complete; every null carries a reason code; no zero substitutes for a null |
| C10 | Layer 0 requirements defined | §19's check exists and passes |
| C11 | Deterministic evaluator tests defined | §20 Layers 1–3 exist and pass, offline, with no credential |
| C12 | Required CI defined | `benchmarks` is in the `compileall` list; Layers 0–3 run in the default workflow |
| C13 | Closeout / evidence requirements defined | an evidence document records MEASURED vs DOCUMENTED, and records Layer 4 as BLOCKED |

```text
C0 is satisfied by the merge of PR 1. C1–C13 are AI-11-B's and AI-11-C's.

AI-11-A closes C0 only, and only on merge. It MUST NOT be recorded as closing any other
gate. It MUST NOT be recorded as closing C0 before the merge.
```

---

## 25. Amendment Rule

```text
FROZEN: AI-11-B and AI-11-C MUST NOT deviate from this document without amending it
        first.
```

An amendment is REQUIRED for any change to:

```text
the benchmark's purpose or identity (§1, §4)
TaskDefinition — its fields, its grammar or its immutability (§5)
BenchmarkRun — its fields or its run identity (§6)
the oracle definition, placement, declaration or non-vacuity requirement (§7)
OracleVerdict, its members or the PASS invariant (§8)
the measurement model, the provenance classes or the unavailable-is-not-zero rule (§9)
tool-call measurement or the Guard-refusal / bypass distinction (§10)
test and skip semantics (§11)
the regression axis (§12)
the recovery model (§13)
SecurityBoundaryStatus or the two-axis rule (§14)
the authoritative host, the workspace derivation or the environment record (§15)
the SecurityLab boundary (§16)
the corpus tiers (§17)
the result schema or the forbidden-content list (§18)
the Layer 0 requirements (§19)
the test model, including the Layer 2 non-vacuity requirement (§20)
any relation to AI-05 .. AI-10 (§21)
the unavailable-metric register (§22)
any non-goal (§23)
```

```text
FROZEN: AI-11 owns this document. It does NOT own AI-04, AI-05, AI-06, AI-07, AI-08,
        AI-09 or AI-10. An amendment to one of those is made by that phase, under that
        phase's amendment rule, BEFORE any AI-11 work depends on it.
```

An amendment records: what changed, why, its security and authority impact, and the date.
It is committed before the code that depends on it. Applied amendments are logged in §26.

---

## 26. Amendment Log

| # | date | scope | summary |
| --- | --- | --- | --- |
| 1 | 2026-10-03 | A.6 `ai11-v1-fuzzing-recovery-triage` | **§27** — A.6's controlled-reproduction semantics are frozen: the generator's real interface, the authoritative case set and its identity, the provenance of expected truth, the kernel-oracle representation, exit-code semantics, the output files the oracle reads, the `vcan0-exclusive` boundary, the recovery/regression split, count semantics, and what a deliberately incorrect A.6 answer is |

### Amendment 1 — A.6 controlled-reproduction semantics (2026-10-03)

```text
WHAT CHANGED     A.6 said "the harness re-runs the generator at a fixed seed and
                 compares classification" and stopped there. Every load-bearing
                 detail was left to the implementation, and the implementation chose
                 four that the pinned generator does not support. §27 fixes: the
                 generator's actual CLI; the authoritative case set and where case
                 identity comes from; the split between tracked task configuration and
                 controlled runtime observation; the kernel-oracle representation; what
                 exit codes 0, 1 and 2 mean; which output file the oracle reads; the
                 `vcan0-exclusive` boundary; where the ECU's recovery/survival is
                 measured and where it is not; what the five counts count; and what
                 makes an A.6 answer deliberately wrong.

WHY              The AI-11-C forensic of 2026-10-03 measured that the A.6 oracle could
                 not produce a truthful observation on any host. It invoked `--json`,
                 an argument the generator does not have (exit 2, argparse usage
                 error); it read a JSON record from stdout, which carries none (the
                 last line is `summary written: <path>`; 0 of 48 lines parse as JSON);
                 it compared against case identifiers the generator never emits (the
                 string `smoke-case` occurs nowhere in SecurityLab @ `efa836f`, and the
                 intersection with the generator's 30 case IDs is empty); and it mapped
                 any non-zero exit to BLOCKED, which would record a completed run that
                 found a crash as an unavailable environment. On the authoritative host
                 the task recorded BLOCKED/FUZZ_RERUN_FAILED:2 while vcan0 was UP and
                 every declared tool was present.

SECURITY IMPACT  Tightened, not relaxed. `vcan0-exclusive` is reclassified from
                 "checked by `ip link show`" to "not demonstrable by any mechanism in
                 either repository": existence is declared insufficient, "no obvious
                 process found" is refused as proof, no pseudo-lock is admitted, and
                 A.6 stays Tier B until exclusivity is measurable. No forbidden tool,
                 interface or corpus is admitted, and the two gitignored `fuzz-out`
                 corpora remain barred as sources (§7.5).

AUTHORITY        AI-11's own annex only. The OracleVerdict vocabulary and the PASS
IMPACT           invariant (§8.1, §11.1), the regression and recovery rules (§12, §13),
                 the SecurityLab boundary (§16), the corpus tier rule (§17.2), the
                 result schema and forbidden-content list (§18) and every relation to
                 AI-05 .. AI-10 (§21) are unchanged. No other phase is amended. This
                 amendment is committed before the A.6 code that depends on it (§25).

DATE             2026-10-03
```

```text
FROZEN: this amendment binds A.6 only. An A.6 implementation that does not follow §27
        is not an implementation of this contract, and a run it produces is not a
        benchmark result — including a run that happens to record PASS.
```

---

## 27. Amendment 1 — A.6 controlled-reproduction semantics — FROZEN

Every clause below was MEASURED against SecurityLab @
`efa836ff9225f6226ca8a76615f3f45c31110d58` on 2026-10-03, on a host where vcan0 was UP,
`can_isotp` was loaded, `candump`/`cansend` were present and dmesg was readable. The
measurements are the reason each clause exists; they are cited so that a later reader
can re-run them rather than trust the conclusion.

### 27.1 The pinned generator's interface — FROZEN

```text
FROZEN: the A.6 generator is `labs/vehicle/can-tools/fuzz/isotp_fuzz.py` at the pinned
        source_sha. Its interface is the one the file declares, and nothing else:
            --list  --smoke  --categories  --dimensions  --seeds
            --limit-per-seed  --seed  --out  --max-cases  --no-artifacts
FROZEN: `--json` is NOT part of A.6. The generator has no such argument: passing it is
        an argparse usage error, exit 2, with no case executed. An oracle invocation
        MUST NOT contain it.
FROZEN: the controlled rerun is exactly
            <python> labs/vehicle/can-tools/fuzz/isotp_fuzz.py \
                --smoke --seed 12345 --out <scratch>/fuzz-cases
        where <scratch> is outside the source repository and outside the agent-visible
        tree (§15.2, §15.3).
FROZEN: `--out` is REQUIRED of the oracle. The generator's default output directory is
        `labs/vehicle/can-tools/fuzz-out`, INSIDE the source tree: §16 forbids writing
        there and §7.5 forbids treating what is written there as truth.
FROZEN: `labs/vehicle/can-tools/fuzz-out/` and `labs/vehicle/fuzz-out/` MUST NOT be
        read, written or used as a comparison source by any A.6 code path (§7.5).
FROZEN: the generator's interpreter dependency is `python-can` and `can-isotp`, both
        imported at module import time. Their absence is an ENVIRONMENT fact and is
        reported as one (§27.5) — it is never inferred from the generator's exit code
        alone.
```

### 27.2 The authoritative case set — FROZEN

```text
FROZEN: the A.6 authoritative case set is EXACTLY the cases the pinned generator
        constructs for `--smoke --seed 12345`, in the order it constructs them. At
        `efa836f` that is 30 cases.
FROZEN: case identity is the generator's own. `case_schema.make_case_id()` produces
        `<seed_id.lower()>__<dimension>__<label>`. The Workbench MUST NOT invent,
        rename, renumber or alias a case identifier, and MUST NOT map one onto another.
FROZEN: `--max-cases` truncates the case set and therefore changes what A.6 measures.
        The oracle MUST NOT pass it. SecurityLab's own minimal entry point
        `scripts/repro/verify_fuzz_smoke.sh` runs `--smoke --max-cases 3`; that is a
        valid SecurityLab smoke and it is NOT the A.6 authoritative case set.
FROZEN: `smoke-case-01`, `smoke-case-02` and `smoke-case-03` are NOT case identities.
        MEASURED: the string `smoke-case` occurs nowhere in SecurityLab @ `efa836f`;
        the intersection of those three names with the generator's 30 case IDs is
        EMPTY; and no tracked deterministic mapping from them to generated cases
        exists. A.6 material MUST NOT carry them, and MUST NOT carry a renamed
        equivalent invented to preserve them.
```

### 27.3 Where expected truth comes from — FROZEN

```text
FROZEN: A.6 separates two things the previous material ran together:
            tracked task configuration    what the task IS — task.yaml, this annex,
                                          the frozen CLASS_PRIORITY, the seed, the
                                          case-set definition, the control answers
            controlled runtime            what THIS run's own generator invocation
            observation                   measured, per authoritative case
FROZEN: for A.6, `truth.json` MAY contain: the frozen CLASS_PRIORITY; the rerun
        arguments and the pinned SHA they were run at; and, per authoritative case,
        the expected class and kernel-oracle reading AS A CONTROLLED RERUN MEASURED
        THEM.
FROZEN: `truth.json` MUST NOT contain any per-run capture — `timestamp`,
        `duration_ms`, `errno`, `process_returncode`, `ecu_log_tail`, raw kernel log
        lines, or anything else §18.2 forbids. §7.5 already bars the gitignored
        captures from becoming expected values; this clause names what may replace
        them.
FROZEN: an expected value MUST be one a conforming rerun reproduces. A value the
        pinned generator no longer produces is NOT truth: it MUST be corrected or
        removed, never kept as a stale record and never accommodated by weakening the
        oracle.
FROZEN: the key set of `truth.expected` MUST equal the authoritative case set. A truth
        whose keys are not generator case IDs is not usable for A.6 and MUST be refused
        rather than compared against.
```

### 27.4 Kernel-oracle representation — FROZEN

```text
MEASURED, `isotp_fuzz.py::kernel_oracle_result()`:
    AVAILABLE    -> the LIST of matching dmesg lines; an EMPTY list means "the oracle
                    ran and found no anomaly"
    UNAVAILABLE  -> None
    ERROR        -> None
```

```text
FROZEN: AI-11 inherits that tri-state unchanged, and fixes the RECORD representation of
        it as a COUNT:
            AVAILABLE    -> kernel_events = the NUMBER of matching kernel-anomaly lines
                            (0 means: the oracle ran and found nothing)
            UNAVAILABLE  -> kernel_events = null
            ERROR        -> kernel_events = null
FROZEN: the count is AI-11's STRUCTURED MEASUREMENT of SecurityLab's list. It is not a
        raw event capture, and it is the only representation a record may carry: §18.2
        forbids tool stdout and free text in a BenchmarkRun, and a dmesg line is both.
        The list MAY exist inside the oracle process; it MUST NOT be recorded.
FROZEN: the normalisation happens in exactly ONE place — the collector — and MUST NOT
        be applied to a value the generator did not produce under an AVAILABLE oracle.
        An empty list MUST NOT become 0 for a run whose oracle was not AVAILABLE.
FROZEN: the count MUST be derived from the rerun in the same run. It is never copied
        from a truth file, and a truth file's number never substitutes for a reading
        the oracle did not take.
```

### 27.5 Exit-code semantics — FROZEN

```text
MEASURED, `isotp_fuzz.py::main()`:
    0   the generator completed its whole case set
    1   the generator COMPLETED a controlled run and stopped early, because a
        HIGH_PRIORITY class (KERNEL_ANOMALY, ECU_CRASH, STATE_CORRUPTION) or a new
        errno occurred — `return 1 if high_priority else 0`
    2   usage failure: no `--smoke`/`--list`, or argparse rejecting an argument
```

```text
FROZEN: `exit != 0 -> BLOCKED` is FORBIDDEN as a rule for A.6.
FROZEN: exit 0  -> a complete candidate observation. It is still not a verdict (§11.1).
FROZEN: exit 1  -> NOT an environment failure, and NOT automatically BLOCKED. It is a
        COMPLETED controlled run whose case set is INCOMPLETE: the observation covers
        the cases that produced files, `skipped > 0`, and PASS is unreachable (§11.1,
        §27.9). The high-priority finding is recorded as the run's own result.
FROZEN: exit 2  -> a HARNESS INVOCATION DEFECT. It MUST NOT become a benchmark result
        of any kind. The run is BLOCKED with a reason code that names the invocation,
        and the defect is fixed in the harness rather than filed as an environment
        limitation.
FROZEN: a non-zero exit MUST NOT be attributed to the environment without POSITIVE
        evidence that the environment caused it. MEASURED: the same exit 1 arises both
        from a high-priority finding and from an interpreter that cannot import the
        generator's dependencies, so the exit code alone does not identify the cause.
        The presence or absence of the run's own output files is what distinguishes
        them, and that is what the oracle must read.
```

### 27.6 Output-file semantics — FROZEN

```text
MEASURED at `efa836f`:
    stdout                     48 lines of human-readable operational log; the last
                               line is `summary written: <path>`; ZERO lines parse as
                               a JSON object
    <out>/smoke-summary.json   the run aggregate: master_seed, total, per-class
                               counts, kernel-oracle counts, high-priority case IDs
    <out>/<case_id>.json       one file per EXECUTED case — the controlled observation:
                               case identity, frames, the declared probe, and the
                               result block the oracle judges
```

```text
FROZEN: the oracle reads the PER-CASE result files from the run's own `--out`
        directory. `json.loads(<last stdout line>)` is FORBIDDEN: stdout is an
        operational log and carries no record.
FROZEN: a case file the run did not write is a case that did not execute. The oracle
        MUST NOT invent a result for it, and MUST NOT fill it from a previous run, a
        truth file or a cached capture.
FROZEN: `smoke-summary.json` is an aggregate and MUST NOT be used as the per-case
        observation. It carries counts, not results.
```

### 27.7 The `vcan0-exclusive` boundary — FROZEN

```text
FROZEN: `vcan0 exists` is NOT `vcan0 is exclusively held`. Existence and UP-ness are
        necessary and NOT sufficient.
FROZEN: `ip link show vcan0` proves the interface exists. It MUST NOT be recorded,
        summarised or relied on as evidence of exclusivity.
FROZEN: "no obvious process was found" is NOT a proof of exclusivity and MUST NOT be
        used as one. Nor is an operator convention — SecurityLab's
        `scripts/repro/verify_fuzz_smoke.sh` and `scripts/qa_extended.sh` warn the
        human not to run concurrent CAN work; a warning to a human is not a measured
        fact about the machine.
FROZEN: A.6 remains TIER B (§17.2) until an explicit, auditable exclusivity mechanism
        exists AND is measured. Tier is a property of the task; it does not rise
        because a host happens to be idle.
FROZEN: where exclusive use cannot be demonstrated, the run is BLOCKED with the
        declared precondition named — `PRECONDITION_UNMET:environment:vcan0-exclusive`
        (§5.7) — and MUST NOT be reported as PASS, FAIL or NOT_RUN.
FROZEN: this amendment admits NO lockfile, flock, network namespace, socket-ownership
        probe or other scheme. A pseudo-lock that has not been measured against the
        real failure it claims to exclude is worse than the honest BLOCKED, because it
        converts an unverified assumption into a recorded fact.
```

### 27.8 Recovery, and the regression axis — FROZEN

```text
FROZEN: the two axes stay separate (§12). This clause says WHERE each question is
        measured and does not merge the answers.
FROZEN: the TASK ORACLE's derived observation is the per-case classification, the
        kernel-oracle tri-state, and the recovery probe result as the pinned generator
        performed it.
FROZEN: the REGRESSION condition `ecu-survives-and-recovers` (BEHAVIOURAL_PIN)
        measures the SUBJECT side, on the post-execution state: the ECU process
        survived the case run, no residual process remains, and the declared probe was
        answered —
            request  `10 01`
            expected `50 01 00 32 00 64`   (`case_schema.py:272-273`, tracked)
FROZEN: the recovery observation MUST come from the pinned generator's controlled
        execution. It MUST NOT be read from the submission, and a submission that
        asserts its own recovery is not evidence of it.
FROZEN: `regression_status = PASS` because the negative-control ANSWER was rejected is
        FORBIDDEN as a substitute for the recovery observation. §7.4's non-vacuity
        control and §12's post-execution regression are different questions, and an
        answer-shaped control does not measure a process.
FROZEN: §13 is NOT amended. §13 measures AGENT recovery under a declared controlled
        fault and remains BLOCKED/DEFERRED for v1. The A.6 probe is a SUBJECT-side
        observation inside a controlled reproduction: it enters no recovery rate and no
        §13 denominator, and it does not unblock §13.
```

### 27.9 Count semantics — FROZEN

```text
FROZEN: the counts describe the CASES. One generator invocation is ONE process
        execution, not N checks, and N cases are N checks, not one.
            planned    the number of cases in the authoritative case set
            executed   the number of per-case result files the run completed
            skipped    planned - executed
            passed     cases whose observation matched the submission
            failed     cases whose observation did not
FROZEN: `len(truth.expected)` MUST NOT be used as `executed`, and MUST NOT be used as
        `planned` unless `truth.expected` IS the authoritative case set (§27.2,
        §27.3). A run that executed nothing reports `executed = 0`; it MUST NOT report
        a count borrowed from a truth file as though the harness had run it.
FROZEN: an early stop (§27.5, exit 1) yields `executed < planned` and `skipped > 0`,
        and PASS is unreachable under §11.1.
FROZEN: an invocation that produced no cases (exit 2) reports `executed = 0`,
        `skipped = planned`, and is BLOCKED. Reporting `planned` as the authoritative
        case set is what lets a reader see how much did not run.
```

### 27.10 Non-vacuity: known_good and known_bad — FROZEN

```text
FROZEN: §7.4 holds unchanged. A.6 MUST carry a discrimination control whose known_good
        answer is not rejected and whose known_bad answer IS.
FROZEN: both control answers MUST name the authoritative case set's IDs (§27.2). A
        control whose keys are not generator case IDs is not an answer to this task.
FROZEN: `known_good` is the per-case classification a controlled rerun produces at the
        pinned SHA and seed, with `kernel_events` in §27.4's count representation. Like
        A.4's, it is a DECLARED CORRECT ANSWER held outside the agent-visible tree, and
        it is produced by a different execution than the one that judges it.
FROZEN: `known_bad` MUST differ from `known_good` in at least one case whose `class` is
        replaced by a DIFFERENT member of the frozen CLASS_PRIORITY. A classification
        error is detectable on every host, whatever the kernel oracle reports.
FROZEN: a SECOND negative control MAY instead violate the kernel rule — a non-null
        `kernel_events` under a non-AVAILABLE oracle — but it MUST NOT be the only
        control: its applicability depends on the host's dmesg availability, and a
        control that is unreachable on some hosts cannot carry §7.4's requirement
        alone.
FROZEN: a negative control that differs only in a field the oracle does not judge is
        NOT a control. Copying the rerun's output and changing something unrelated
        yields an oracle that cannot say no while appearing to have a control — which
        is the state A.6 was measured in.
```

---

# Annex A — Task Cards

Each card carries the same twelve fields. `PROPOSED` throughout: these are the v1 corpus
choices this contract makes so AI-11-B does not have to choose while implementing.

## A.1 `ai11-v1-can-dbc-decode` — CAN

| field | value |
| --- | --- |
| task_id | `ai11-v1-can-dbc-decode` |
| source repo | `Li20771/SecurityLab` @ pinned `source_sha` |
| fixed-SHA policy | one SHA frozen per campaign; the SHA is recorded in every run; a SHA in use never drifts |
| workspace setup | export `labs/vehicle/can-basic/demo.dbc` + a frozen frame set carried by the TaskDefinition. No vcan. No generated artifact. |
| required tools | `git/read_file`; `tests/pytest` optional |
| forbidden tools | every `vehicle_network` operation; `terminal/run`; `firmware/*`; `reverse_engineering/*` |
| independent oracle | an independent decoder (the harness's own `cantools` invocation) over the same frames, compared to the submitted physical values within a declared tolerance |
| success condition | every declared signal's physical value matches within tolerance |
| regression condition | a decode with `factor`/`offset` transposed MUST be judged non-PASS |
| measurable metrics | oracle verdict; correct/total signals; tool trace; duration |
| not measurable now | token; cost; false claim (all §22) |
| reproducibility risk | `cantools` version; endianness, signedness and float-tolerance conventions must be declared in the task, not assumed |

```text
This is the v1 anchor task: pure data, no external binary, no kernel facility, no vcan.
It is the task against which the harness itself is validated first.
```

## A.2 `ai11-v1-uds-nrc-triage` — UDS

| field | value |
| --- | --- |
| task_id | `ai11-v1-uds-nrc-triage` |
| source repo | `Li20771/SecurityLab` @ pinned `source_sha` |
| fixed-SHA policy | as A.1 |
| workspace setup | export a declared subset of `labs/vehicle/uds-basic/` (client + configs) plus a frozen UDS frame sequence carried as data. Whether the ECU sources are agent-visible is declared per task_version. No vcan. |
| required tools | `git/read_file`; `tests/pytest` optional |
| forbidden tools | every `vehicle_network` operation; `terminal/run` |
| independent oracle | a harness-side expected `(service, NRC, violated precondition)` triple per case, from a TRACKED deterministic definition; plus a regression gate run in `unit` mode only |
| success condition | every declared triple matches |
| regression condition | the regression gate's required checks must all have EXECUTED and passed (§11) |
| measurable metrics | triples correct/total; oracle verdicts; regression status; duration |
| not measurable now | token; cost; false claim; the e2e (vcan) portion on a non-vcan host |
| reproducibility risk | needs Python 3.12 and SecurityLab's pinned network requirements; the e2e portion is BLOCKED without vcan0 |

```text
FROZEN for this task: the regression gate runs in `unit` mode. `run_tests.sh all` MUST
NOT be used, because it exits 0 after skipping e2e on a host without vcan0 (§11.2).
```

## A.3 `ai11-v1-yara-rule-author` — YARA

| field | value |
| --- | --- |
| task_id | `ai11-v1-yara-rule-author` |
| source repo | `Li20771/SecurityLab` @ pinned `source_sha` |
| fixed-SHA policy | as A.1 |
| workspace setup | a rules directory (empty or starter) plus a declared SUBSET of `labs/yara-basic/samples/`. Held-out samples are excluded. |
| required tools | `reverse_engineering/yara_scan` |
| forbidden tools | everything else that starts a process; no network family exists in v1 |
| independent oracle | the harness compiles the submitted rule and scans HELD-OUT positives and HELD-OUT negatives, neither of which is in the agent-visible tree |
| success condition | the rule compiles; every held-out positive matches; no held-out negative matches |
| regression condition | any match on a held-out negative is non-PASS; a false positive is not traded against a true positive |
| measurable metrics | TP / TN counts; compile success; oracle verdict; duration |
| not measurable now | token; cost; false claim |
| reproducibility risk | requires `yara` on the authoritative host (SecurityLab records 4.5.0); a version difference can change regex semantics, so the version is recorded per run |

```text
Precedent: labs/yara-basic/scan.sh is already a deterministic TP/TN oracle printing
YARA_RESULT=PASS. AI-11 does not run that script as its verdict — it re-implements the
same assertions with held-out material, in the harness, outside the workspace.
```

## A.4 `ai11-v1-firmware-syn-ecu-inventory` — firmware

| field | value |
| --- | --- |
| task_id | `ai11-v1-firmware-syn-ecu-inventory` |
| source repo | `Li20771/SecurityLab` @ pinned `source_sha` |
| fixed-SHA policy | as A.1 |
| workspace setup | the harness BUILDS a SquashFS image with `labs/firmware/synthetic-ecu/build_fw.sh`, outside the agent-visible tree, and places only the image inside it. The build script, its expected outputs and the README's ground-truth table are all excluded. |
| required tools | `firmware/firmware_unpack` (binwalk); `git/read_file` |
| forbidden tools | `terminal/run` beyond its declared program set; every family not listed |
| independent oracle | the harness re-derives ground truth from the SAME image with its own `binwalk` + `unsquashfs`, then compares to the submission; the expected values are read from the image, not from a frozen digest |
| success condition | filesystem and compression identified; the declared config values match |
| regression condition | the v2 values submitted against a v1 image MUST be judged non-PASS |
| measurable metrics | oracle verdict; tool trace; duration; image digest (recorded, not asserted) |
| not measurable now | token; cost; false claim |
| reproducibility risk | `build_fw.sh` calls `mksquashfs` without a reproducible-time flag, so the image digest is NOT stable across runs. The contract therefore forbids freezing the image digest as an expected value, and requires the oracle to derive truth from the image it actually has. |

```text
FROZEN for image/binary tasks generally (§5.4): a generated artifact is BUILT by the
harness. It is never assumed to exist in the source SHA. The same applies to
labs/firmware/binwalk-basic/, whose .squashfs is gitignored and absent from the SHA.
```

## A.5 `ai11-v1-reverse-arm64-triage` — reverse

| field | value |
| --- | --- |
| task_id | `ai11-v1-reverse-arm64-triage` |
| source repo | `Li20771/SecurityLab` @ pinned `source_sha` |
| fixed-SHA policy | as A.1 |
| workspace setup | the harness COMPILES `labs/reverse/arm64/hello_arm64.c` with an aarch64 cross compiler into the scratch workspace, and places only the resulting binary in the agent-visible tree. **The `.c` source MUST be excluded.** |
| required tools | `firmware/qemu`; `firmware/gdb`; `git/read_file` |
| forbidden tools | every family not listed; any path that writes to the source repository |
| independent oracle | the harness determines architecture and linkage with its own `readelf`/`file`, and the expected runtime output with `qemu-aarch64 <binary>` including the exit code |
| success condition | architecture, linkage and runtime output all match |
| regression condition | an aarch64 conclusion submitted for the x86-64 counterpart MUST be judged non-PASS |
| measurable metrics | oracle verdict; tool trace; duration |
| not measurable now | token; cost; false claim |
| reproducibility risk | requires the cross compiler and `qemu-aarch64`; their versions are recorded per run |

```text
FROZEN, correcting an earlier readout statement: the binary is NOT in the tracked SHA.

    $ git ls-files labs/reverse
    labs/reverse/README.md
    labs/reverse/arm64/README.md
    labs/reverse/arm64/hello_arm64.c
    labs/reverse/hello/README.md
    labs/reverse/hello/hello.c

    $ git check-ignore -v labs/reverse/arm64/hello_arm64
    .gitignore:40:labs/reverse/**/hello_arm64

There is no committed binary to copy. The workspace setup above is the only correct one.

FROZEN: the oracle MUST NOT depend on symbol addresses. labs/reverse/README.md records
        `add: 0x1149`, `main: 0x1161`, and those are a property of one toolchain build,
        not of the source. The oracle depends only on architecture, linkage, stdout and
        behaviour.

Precedent: scripts/repro/verify_arm.sh already does exactly this — generates its own
source, compiles it, asserts the exact stdout `ARM_RUNTIME_OK 42`, and separates exit 2
(missing dependency) from exit 1 (verification failure).
```

## A.6 `ai11-v1-fuzzing-recovery-triage` — fuzzing / recovery — **Tier B**

| field | value |
| --- | --- |
| task_id | `ai11-v1-fuzzing-recovery-triage` |
| source repo | `Li20771/SecurityLab` @ pinned `source_sha` |
| fixed-SHA policy | as A.1 |
| workspace setup | the tracked fuzz generators under `labs/vehicle/can-tools/fuzz/` plus `scripts/repro/verify_fuzz_smoke.sh`. **The task MUST NOT depend on `labs/vehicle/can-tools/fuzz-out/` or `labs/vehicle/fuzz-out/`** — both are gitignored and absent from the SHA. |
| required tools | `vehicle_network/vcan_can_send`, `vcan_can_dump`, `isotp_exchange` — vcan0 only |
| forbidden tools | any physical interface; any real ECU or vehicle; concurrent use of vcan0; unbounded fuzzing |
| independent oracle | the harness re-runs the generator at a fixed seed and compares classification; the frozen `CLASS_PRIORITY` and the recovery probe are read from TRACKED code |
| success condition | the classification matches an independent re-run |
| regression condition | the ECU process survives; no residual state; no residual process |
| measurable metrics | classification counts; recovery boolean; kernel-oracle tri-state; duration |
| not measurable now | the whole task on a host without vcan0 (BLOCKED); token; cost; false claim |
| reproducibility risk | needs Linux, the `can_isotp` kernel module, `CAP_NET_ADMIN`, and EXCLUSIVE use of vcan0. SecurityLab's own CI does not run fuzzing, by design. |

Tracked oracle material this task builds on — verified at `efa836f`:

```text
labs/vehicle/can-tools/fuzz/case_schema.py:61-70   CLASS_PRIORITY, frozen:
    KERNEL_ANOMALY > ECU_CRASH > STATE_CORRUPTION > HANG
                   > TRANSPORT_ERROR > UDS_RESPONSE > DISCARD > NORMAL
labs/vehicle/can-tools/fuzz/case_schema.py:73      HIGH_PRIORITY_CLASSES
labs/vehicle/can-tools/fuzz/case_schema.py:272-273 recovery_request "10 01"
                                                   recovery_expected "50 01 00 32 00 64"
labs/vehicle/can-tools/fuzz/isotp_fuzz.py:22       "recovery : 硬 oracle"
labs/vehicle/can-tools/tests/test_uds_fuzz_offline.py:1592-1621
                                                   V1_GOLDEN_DIGEST; len(v1_cases) == 947
labs/vehicle/can-tools/fuzz/case_schema.py         kernel oracle tri-state
                                                   AVAILABLE / UNAVAILABLE / ERROR
```

```text
FROZEN: kernel_events is meaningful ONLY when the kernel oracle is AVAILABLE. When it is
        UNAVAILABLE or ERROR, kernel_events is recorded null, never 0. This is
        SecurityLab's own rule and AI-11 inherits it verbatim rather than restating a
        weaker one.
```

```text
AMENDMENT 1 (2026-10-03, §27) — the fields above say what the task IS; §27 fixes HOW
the controlled reproduction is performed, because the implementation that read this
card chose four things the pinned generator does not support. Binding on any A.6
implementation:

    the generator   `isotp_fuzz.py --smoke --seed 12345 --out <scratch>`; `--json` is
                    NOT part of A.6 (the generator has no such argument); the two
                    gitignored `fuzz-out` corpora are never read or written
    the case set    whatever that invocation constructs, identified by the generator's
                    own `make_case_id()`; `smoke-case-*` are not case identities, occur
                    nowhere in SecurityLab, and MUST NOT appear in A.6 material
    the truth       per-case expected class and kernel reading, as a controlled rerun
                    at the pinned SHA reproduces them; never a per-run capture
                    (timestamp, duration, errno, ecu_log_tail, raw kernel lines)
    kernel_events   a COUNT when the oracle was AVAILABLE (0 = ran, nothing found),
                    null otherwise; the dmesg lines themselves never enter a record
    exit 0 / 1 / 2  a complete observation / a COMPLETED run that stopped on a
                    high-priority finding (counts incomplete, never PASS, never an
                    environment failure) / a harness invocation defect that MUST NOT
                    become a result
    the output      the per-case JSON files under the run's own `--out`; stdout is an
                    operational log and carries no record
    vcan0           existence is not exclusivity; A.6 stays Tier B until exclusivity is
                    demonstrable by an explicit auditable mechanism; otherwise BLOCKED
                    with `PRECONDITION_UNMET:environment:vcan0-exclusive`
    counts          planned/executed/skipped describe the CASES, not the invocation
    controls        known_good = the measured classification; known_bad = a different
                    frozen class on at least one case
```

```text
TIER: B, because it needs an exclusive vcan0 plus CAP_NET_ADMIN — a prerequisite beyond
a plain oracle run. It is a candidate, not a Tier A task, and AI-11-B MUST NOT promote
it to make the corpus look stronger.
```

```text
Its value in v1 is as the LIVE SAMPLE of §8's honesty rule: on the authoritative host
without vcan0 it produces BLOCKED, and the benchmark is required to record BLOCKED
rather than to drop the task, skip it silently, or count it as a failure.
```

---

# Annex B — Disposition of the Readout Items

Every item raised in the AI-11-A Readout and Addendum 1, and where it landed.

| item | disposition | where |
| --- | --- | --- |
| D-1 firmware task | PROPOSED as A.4; image is harness-built; image digest recorded but never frozen as truth | §5.4, §17.3, A.4 |
| D-5 reverse binary | **CORRECTED and FROZEN** — no binary exists in the SHA; harness builds it; `.c` excluded; oracle must not use symbol addresses | §5.4, A.5 |
| D-6 fuzzing oracle | PROPOSED as A.6 (Tier B); tracked `CLASS_PRIORITY` + recovery probe cited; untracked corpora forbidden as truth | §7.5, §17.3, A.6 |
| P1 task_id grammar | PROPOSED | §5.2 |
| P2 six-task corpus | PROPOSED, with tiers | §17.3, Annex A |
| P3 OracleVerdict six values | **FROZEN** | §8.1 |
| P4 divergence near-neighbour | **FROZEN**, renamed and bounded | §22.4 |
| P5 workspace_view | **FROZEN** as `workspace_setup` + measured manifest | §5.4, §15.3 |
| P6 worktree mechanism | PROPOSED — scratch clone + `worktree add`; `git worktree` against SecurityLab rejected because it writes `.git/worktrees` | §15.2 |
| P7 promoted tier | PROPOSED, not required by v1 | §17.4 |
| P8 Layer 0 + CI | PROPOSED, with the check list | §19 |
| P9 PR split | FROZEN as phase structure | §24, Annex C |
| P10 oracle values from tracked/controlled sources | **FROZEN** | §7.5 |
| F12 skip-aware oracle | **FROZEN**, with the measured case recorded | §11 |
| B6 host/toolchain BLOCKED | **FROZEN** as a recorded per-run status, not a failure | §5.7, §8.2, A.6 |
| O1 raw-model-output boundary | **FROZEN** — no storage, no bypass; the metric is UNAVAILABLE | §18.2, §22.4, §21.6 |
| O2 workspace view strategy | resolved into P5 | §5.4 |
| O3 authoritative host = WSL Ubuntu | **FROZEN** | §15.1 |
| O4 Guard policy carrier | **FROZEN** — call parameter; no config file; AI-04 Q-1 left open | §5.6, §21.3 |
| O5 AI-11 producer token | **FORBIDDEN in v1** | §21.1 |
| O6 result directory shape | PROPOSED | §17.4 |
| O7 Tier B kept in corpus | **FROZEN** — it is the live sample of the honesty rule | §17.2, A.6 |
| AI-05 §28 tension | recorded **OPEN**, not resolved; no phase amended | §21.1 |

## Annex B.1 — the one tension found against an existing frozen contract

Per the instruction to record rather than repair, one clause of a frozen contract cannot
be satisfied in its strong reading by AI-11 v1:

```text
docs/AI-05_EVIDENCE_EXECUTION_PLAN.md §28, FROZEN:
    "AI-11 CONSUMES Evidence."
    "AI-11 computes `task success`, `false pass`, `security-boundary violations` and the
     rest **from** AI-05 records."

AI-11 v1 reality:
    AI-08 v1 writes NO EvidenceRecord (§13.1).
    AI-11 v1 writes NO EvidenceRecord (§21.1) — no producer token is admissible.
    Therefore no AI-05 record exists for an AI-11 benchmark run to consume.
```

```text
STATUS: OPEN. Recorded as an amendment prerequisite, not as a defect and not as licence
        to change either document.

NOT DONE, deliberately:
    AI-05 §28 was not amended.
    AI-11 §21.1 was not weakened.
    No producer token was added.
    AI-11 v1 does not pretend to consume records that do not exist.

RESOLUTION PATH: an AI-05 amendment admitting a producer token. Until then AI-11 v1
        computes from AI-08 run data and its own oracles — a strict subset of §28's
        metrics, from a source §28 does not forbid.
```

---

# Annex C — Phase Structure (PR control)

```text
PR 1   AI-11-A   contract freeze
                  this document; benchmarks/README.md; the PROJECT_STATUS sync.
                  NO executable file. The freeze act is the merge.

PR 2   AI-11-B   benchmark core
                  schema + runner + oracle executor + tests + first corpus.
                  scripts/ci/layer0_policy.py check_ai11_benchmark_layer()
                  benchmarks added to the CI compileall list.
                  Layers 0-3 green, offline, no credential.

PR 3   AI-11-C   measured campaign
                  Layer 3 campaign against the `reference` executor; benchmark
                  evidence; status and roadmap closeout.
                  Layer 4 recorded BLOCKED with its reason.
```

```text
FROZEN: three PRs, and no fourth. A fourth is a new phase, not a sub-phase of this one.
FROZEN: AI-11-C MUST NOT begin before AI-11-B's gates pass.
```

---

## Status

```text
AI-11-A  = DRAFT / FREEZE PROPOSAL      this document
AI-11-B  = NOT STARTED
AI-11-C  = NOT STARTED
Implementation = NOT STARTED

main at proposal = 272f68f45a19cacd5d8c7bb9ad66a993260f90f3
SecurityLab at readout = efa836ff9225f6226ca8a76615f3f45c31110d58
```

```text
AI-05 / AI-06 / AI-07 / AI-08 / AI-09 / AI-10   = UNCHANGED by AI-11-A
SecurityLab                                      = UNCHANGED, and not written to
```

```text
Contract blobs UNCHANGED by AI-11-A:

    AI-05   dd062148938f902109b49a496bb6051c3331a349
    AI-06   4b05155c9bd7ed2d7e25f7e23a0471de82a880f8
    AI-07   2f8dcba8f9c2ca36e3d917fc6b69c3a5cb7f36fe
    AI-08   a01e03f5306299a0a4442648eeb8fdcfce6bd8dd
    AI-09   e9728b184740074e5c8f718db6b45f859c3802bf
    AI-10   fc6f709611fcf7a8fcf6845097bf130920445fdc

    The AI-06/07/08/09/10 values agree with the hashes AI-10's freeze record already
    declared, which is how they were confirmed rather than assumed.
```

> **AI-11 has not been implemented.** This document freezes a contract and nothing else.
> No benchmark exists, no task has run, no oracle has executed, no result has been
> produced, and no component has been authorized by any of this.
