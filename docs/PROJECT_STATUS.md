# Project Status
> Baseline: 2026-09-26

## Current stage
**AI-05 — Evidence / Audit Plugin**

AI-00 architecture and repository baseline is complete. **AI-01 DSH Baseline is COMPLETE** — see
[AI-01 final gate status](#ai-01-final-gate-status). **AI-02 Model Layer is COMPLETE** — see
[AI-02 final gate status](#ai-02-final-gate-status) and
[AI-02_CLOSEOUT_2026-09-29.md](AI-02_CLOSEOUT_2026-09-29.md).

AI-03 is **COMPLETE and MERGED** — all exit criteria C0–C8 satisfied, C8 by required CI on its
own head, and merged to `main` as `548bc041b31cc0fc9d01af55c527378ba2c42c48` (PR #28). Its
contract, implementation, verification, and evidence are recorded in
[AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md](AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md) and
[AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md](AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md).
See [AI-03 status](#ai-03-status).

AI-04 is **COMPLETE and MERGED** — merged to `main` as
`254823f74aa742a3f98d04f7d184b39c33369d98` (PR #32). See [AI-04 status](#ai-04-status).

**AI-05-B1 is COMPLETE and MERGED** — merged to `main` as
`0403fcd83b740f0603af7204e77f6e6905a84cf0` (PR #34). B1 is the **offline logical core only**;
AI-05 as a whole is **INCOMPLETE** and B2 has not started. See [AI-05 status](#ai-05-status).

The GitHub `main` branch protection requirement is **BLOCKED** by the current GitHub
Free/private-repository plan and is retained as a documented platform limitation; it is not
treated as a PASS.

## Start Here

This file is the single entry point for deciding what to do next.

### Current work item

**AI-05-B2 — Evidence admission, Store and lifecycle — NOT STARTED.**

```text
AI-05 contract    = frozen, docs/AI-05_EVIDENCE_EXECUTION_PLAN.md
AI-05 contract blob = a1df976deea70daea754d89574c47165140d00d0
AI-05-A           = COMPLETE / MERGED   contract frozen, 1 amendment
AI-05-B1          = COMPLETE / MERGED   offline logical core
AI-05-B1 merge    = 0403fcd83b740f0603af7204e77f6e6905a84cf0  (PR #34, merged)
AI-05-B2          = NOT STARTED
AI-05 overall     = INCOMPLETE
```

AI-04 is closed. AI-05-A is closed: the contract was frozen and then amended once (Amendment 1),
which replaced the container-level §15.2 table with a leaf table, declared the §6.5
admitted-producer registry, added the §14.9 grammar table and declared the `ObservationFamily`
vocabulary.

AI-05-B1 is closed and merged. It built the record model, the §15.2 leaf field table, the two
digests, the §14.9 named grammars, the §6.5 registry and the §6.6 cross-field rules — and
nothing else. It added **no storage, no admission pipeline and no Store**. Full evidence is in
[AI-05-B1_EVIDENCE_2026-10-01.md](AI-05-B1_EVIDENCE_2026-10-01.md).

> **AI-05-B2 has not been started.** No branch, no admission rule set, no `rules.py`, no Store
> protocol, no storage backend, no lifecycle. B2's design is a separate work stage and is
> deliberately not specified here.

The merged AI-03, AI-04 and AI-05-B1 branches (`feature/ai-03-context-plugin`,
`feature/ai-04-guard-implementation`, `feature/ai-05-b1-logical-core`) may be deleted.

No force push and no history rewrite was performed at any point in AI-03, AI-04 or AI-05-B1.
Each merge was a human decision taken at the GitHub checkpoint, not by the agent that implemented
the phase.

The closed AI-01 execution plan remains at
[docs/AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)
(frozen; amended 2026-09-28 — exit criteria redefined, see its §6.1 and §9).

The frozen AI-02 contract remains at
[docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md](AI-02_MODEL_LAYER_EXECUTION_PLAN.md)
(frozen at AI-02-A; amended four times, see its §17.1 amendment log).

The AI-03 contract is at
[docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md](AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md)
(frozen at AI-03-A; amended three times, see its §17.1 amendment log).

### Session start sequence

```text
PROJECT_STATUS.md
    -> MASTER_ROADMAP.md (current phase)
    -> the current phase's execution plan
    -> verify branch / SHA / working tree
    -> create a task/experiment ID
    -> execution
    -> verification + evidence
    -> PR / approval
    -> merge checkpoint
    -> update PROJECT_STATUS.md
```

### Not yet started

- AI-05-B2 Evidence admission, Store and lifecycle
- AI-06 Security Tools implementation
- AI-07 Router implementation — **DEFERRED**, and untouched by AI-03

## Completed

### Repository foundation
- Independent Workbench repository
- Core directory skeleton
- README and roadmap
- Git/security boundary
- Example configuration separated from secrets
- Basic CI preflight
- PR template
- Bootstrap guidance

### Architecture alignment
- AI-00 to AI-14 numbering confirmed against the original Workbench plan; no renumbering was needed.
- Router is explicitly a Workbench core service.
- Terminal and MCP have first-class Tool entry points.
- Long-running workflows have a dedicated layer.
- Evidence lifecycle and retention semantics are documented.
- Project Status is separate from the Roadmap.
- SecurityLab remains an independent workspace.

## Not yet completed
- Exact supported DSH/Codex versions
- Provider connectivity tests — live verification is **NOT_RUN** (AI-02-B6 built
  the opt-in path; no provider call has been made)
- Executable Evidence/Audit plugin
- Research tool adapters
- Model Router implementation
- Codex integration
- Benchmark dataset
- Cross-Agent Review implementation
- Long-running workflow implementation

## AI-00 final gate status

- Architecture / repository baseline: **PASS**
- AI-01 execution plan: **PASS / FROZEN**
- GitHub `main` branch protection: **BLOCKED** — current GitHub Free/private-repository plan does not enforce repository rulesets.

This platform limitation is documented and is not converted to PASS.

## AI-01 final gate status

**AI-01 — DSH Baseline: COMPLETE** — closed 2026-09-28. Exit criteria were redefined in the
amended [execution plan](AI-01_DSH_BASELINE_EXECUTION_PLAN.md) §6.1 and §9.

Verified and recorded (evidence: checkpoints CP1–CP11):

- current DSH baseline verified against the running installation
- exact DSH version (`0.1.7-rc.2`), install artifact identity, startup method and runtime
  behaviour documented
- known-good configuration recorded without secrets
- controlled workspace binding verified (SecurityLab, external)
- required baseline Agent behaviour verified
- plugin/tool capability recorded
- permission boundary recorded — DSH-native network-exposure boundary, with executed allowed
  and blocked cases
- restart / recovery / configuration persistence verified
- rollback point recorded
- known limitations classified

Outstanding, deferred:

- **Clean-room cross-machine reinstall: BLOCKED / DEFERRED.** No clean, disposable Windows
  environment exists on this host, established by direct investigation (CP7, CP9, CP10, CP11).
  Reclassified as future **deployment / reproducibility validation**; it is **not** an AI-01
  exit blocker. It is **not** a `PASS`.

```text
AI-01 overall        = COMPLETE
Clean-room reinstall = BLOCKED / DEFERRED
Criterion #8         = PASS
Criterion #9         = PASS
```

> **This does not claim universal Windows compatibility.** It does **not** claim that DSH
> installation is reproducible across environments, and does **not** claim that all future DSH
> builds are supported. DSH is an external, continuously updated platform; a material upgrade
> requires a new baseline checkpoint (execution plan §9).

## AI-02 final gate status

**AI-02 — DeepSeek + MiMo Model Layer: COMPLETE** — closed 2026-09-29. Full evidence in
[AI-02_CLOSEOUT_2026-09-29.md](AI-02_CLOSEOUT_2026-09-29.md).

```text
AI-02 overall = COMPLETE

AI-02-A  = PASS / COMPLETE   contract / execution plan / freeze
AI-02-B1 = PASS / COMPLETE   provider skeleton
AI-02-B2 = PASS / COMPLETE   model profiles
AI-02-B3 = PASS / COMPLETE   normalized invocation
AI-02-B4 = PASS / COMPLETE   metrics
AI-02-B5 = PASS / COMPLETE   offline tests / CI layers 0-3
AI-02-B6 = PASS / COMPLETE   opt-in live connectivity verification
AI-02-C  = COMPLETE          closeout / evidence

Final merge SHA = 75f7f661f5a0a3c4b2725c8fdeca161efc02c80b
                  (PR #26; parents c90b8251 + 5524b53a)

Offline CI      = PASS
                  956 passed, 5 deselected
                  Layer 0 = PASS (12 checks)
                  layer 1 = 382, layer 2 = 539, layer 3 = 35

Live provider execution = NOT_RUN
Real provider API calls = 0

SecurityLab        = UNCHANGED
Router             = UNIMPLEMENTED / UNCHANGED
openai-compatible  = RESERVED / UNIMPLEMENTED
```

Verified and recorded:

- provider and model profile schemas, with the capability truth model frozen
- exactly three model profiles and two provider profiles, registry-validated
- a provider-decoupled invocation boundary, with a capability gate that refuses
  before any provider activity
- metrics with unknown-usage accounting, and pricing as dated metadata with no
  hardcoded price
- offline test layers 0–3 wired into CI, Layer 4 excluded by construction
- an opt-in live verification path that is off by default and cannot run without
  a human starting it

Outstanding, deferred — **not** AI-02 failures:

- **Live connectivity remains `NOT_RUN`.** No credential was supplied and no
  provider call was made. §14.3 permits recording `NOT_RUN`; it is not a `PASS`.
- **`streaming`, `reasoning`, and `prompt_caching` remain `UNKNOWN`.** No safe,
  bounded, repeatable probe exists for them in this phase.
- **Endpoints and API model ids remain `DECLARED`.** Unverified until a dated
  observation exists.

> **No capability in this repository is `VERIFIED`.** Every capability on every
> model profile is `UNKNOWN`. B6 can produce a *candidate* status for human
> review; it cannot modify a profile, and it did not.

## AI-03 status

**AI-03 — Context Plugin: COMPLETE.** All exit criteria satisfied; C8 by required CI on the
validated head. Full evidence in
[AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md](AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md).

```text
AI-03-A  = COMPLETE      contract / execution plan / freeze
AI-03-B1 = COMPLETE      workspace resolver
AI-03-B2 = COMPLETE      source adapters
AI-03-B3 = COMPLETE      semantic classification
AI-03-B4 = COMPLETE      cache boundary
AI-03-B5 = COMPLETE      integration and offline tests
AI-03-C  = COMPLETE      PR #28 opened, CI green, merged by a human
AI-03    = COMPLETE

C0 contract implemented              = PASS
C1 workspace isolation verified      = PASS
C2 current git state verified        = PASS
C3 fact/history/plan separation      = PASS
C4 source priority conflict tests    = PASS
C5 UNKNOWN/NOT_RUN/BLOCKED preserved = PASS
C6 cache boundary and invalidation   = PASS
C7 evidence artifact complete        = PASS
C8 required CI/tests PASS            = PASS
```

Base SHA `8c5df3e085e15e39f901e83f53f0e04f693cfb84`; branch
`feature/ai-03-context-plugin`; validated head
`7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011`.

Local verification (offline, no credential, no network):

```text
Layer 0 = PASS (13 checks; was 12)
provider/config/model validation = PASS
context validation = PASS
1317 passed, 5 deselected
  layer 1 = 488, layer 2 = 764, layer 3 = 65
  baseline was 956 passed, 5 deselected — +361 tests, 0 regressions
```

Required CI, on the validated head — this is what satisfies C8:

```text
PR #28                        = MERGED by a human, 2026-09-29T03:58:20Z
merge commit                  = 548bc041b31cc0fc9d01af55c527378ba2c42c48
CI run 36518367883 @ 7a29197  = SUCCESS   (validated the code head)
CI run 36519252935 @ a5376e2  = SUCCESS   (validated the final doc head)
  Layer 0 — repository policy ......... success (13 checks)
  Layers 1-3 — offline model+context .. success
    layer 1 = 488 passed
    layer 2 = 764 passed
    layer 3 =  64 passed, 1 skipped
```

```text
SecurityLab    = UNCHANGED
main           = 548bc041; AI-03 IS on main
Router (AI-07) = DEFERRED / UNIMPLEMENTED
```

**Historical note, retained deliberately.** Before the branch was pushed, C8 was recorded as
`NOT_RUN`, because no CI had ever run for it. That was the correct state then and is no longer
the current one. The first CI run (36517922651, head `0bffb60`) then **failed** on a genuine
defect in an AI-03 test — it assumed an attached HEAD, which `actions/checkout` does not provide
on a `pull_request` run. C8 was `BLOCKED`/`FAIL` for that head. The test was corrected, and C8 is
`PASS` only for `7a29197`, the head this status refers to.

**One assertion is `NOT_RUN` in CI, not `PASS`:** `test_a_branch_item_matches_git_when_present`
skips under a detached HEAD. The attached-branch behaviour is covered deterministically by
`tests/integration/test_context_git_state.py` against throwaway repositories, which does run in
CI, so this leaves no gap — but it is recorded as skipped, not upgraded.

**`main` now contains AI-03.** PR #28 was merged by a human as `548bc041`. Everything above
describes the merged content, not a branch.

Recorded, not hidden:

- `docs/MASTER_ROADMAP.md` (P1) and `docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` (P3) are
  read and recorded with their revisions but contribute **no context items**, because neither
  contains a structurally declared state and the extractor does not read prose. A deliberately
  narrow grammar was chosen over one that guesses.
- The Context cache is **in-memory only**. A persistent cache needs a storage location, a
  retention rule, and a cleanup rule; shipping one without those would ship a second,
  undeclared source of truth.
- AI-03 **adds no layer 4** — the Context plugin has no network surface.

## AI-04 status

**AI-04 — Security Guard Plugin: COMPLETE.** Full evidence in
[AI-04-B_EVIDENCE_2026-09-29.md](AI-04-B_EVIDENCE_2026-09-29.md).

```text
AI-04-A = COMPLETE / MERGED   contract frozen, 9 amendments
AI-04-B = COMPLETE / MERGED   implementation, tests, evidence
AI-04-C = COMPLETE            closeout
AI-04   = COMPLETE

merge SHA = 254823f74aa742a3f98d04f7d184b39c33369d98   (PR #32)
base      = 8b1af38754681955615f7b1a228fb90c1215615c
```

`AI-04-C10 required CI = PASS` on the merged head and on this closeout commit.

### What was built

```text
plugins/guard/    9 modules, 3244 lines
tests/guard/      9 modules, 295 tests
```

`Guard.evaluate(request, policy)` returns a `DecisionRecord` carrying
`ALLOW | DENY | BLOCKED | UNKNOWN`, a reason code, per-check results, provenance
and two semantic digests. Guard decides; it does not execute, collect, persist,
route, approve or scan.

Covered by the phase's T1–T15 test matrix and C0–C10 exit gates.

### Verified

```text
Guard tests      = 295 passed
whole repository = 1612 passed, 5 deselected   (baseline 1317; +295, 0 regressions)
Layer 0          = PASS (13 checks)
security checks  = clean — no eval, exec, compile, subprocess, network,
                   routing or tools import in plugins/guard
contract conformance = all 15 vocabularies match the frozen contract;
                   AI-02 and AI-03 frozen types imported by identity, not restated
```

### Amendments and review fixes

The contract was amended **9 times before implementation**, closing four blocking
findings: an `UNKNOWN`-semantics contradiction, a rule ordering that claimed to be
total but was not, an absent condition grammar, and undefined digest
canonicalization.

Two post-implementation review fixes, both CI-verified on their own heads:

```text
Fix #1  §15.1 absolute deny ran after policy; secret-material requests with a
        missing or invalid policy reported BLOCKED instead of DENY
Fix #2  §15.1 cross-workspace authorization was not a boundary; foreign context
        was filtered and evaluation continued, so an unconditional ALLOW
        succeeded on a request spanning two workspaces
```

Both were the same mistake in different places: a boundary check placed after
the thing it was supposed to precede.

### Recorded, not hidden

- **No approval source exists**, so `system-change`, `remote-change` and real
  CAN/ECU/vehicle are permanently `BLOCKED` (§8.2, D-12). Intended fail-closed
  behaviour, verified by test — not a defect.
- **Guard performs no policy discovery.** Where a policy comes from remains Q-1;
  `evaluate` takes it as a parameter.
- **`evidence_ref` is always `null`** until AI-05 exists. AI-05 is not a
  prerequisite for AI-04.

```text
SecurityLab    = UNCHANGED
AI-02 / AI-03  = UNCHANGED
Router (AI-07) = DEFERRED / UNIMPLEMENTED
main           = contains AI-04
```

## AI-05 status

**AI-05 — Evidence / Audit Plugin: INCOMPLETE.** B1 is complete and merged; B2 has not started.
Full evidence in [AI-05-B1_EVIDENCE_2026-10-01.md](AI-05-B1_EVIDENCE_2026-10-01.md).

```text
AI-05-A  = COMPLETE / MERGED   contract frozen, 1 amendment
AI-05-B1 = COMPLETE / MERGED   offline logical core
AI-05-B2 = NOT STARTED         admission, Store, lifecycle
AI-05    = INCOMPLETE          not closed

B1 merge SHA    = 0403fcd83b740f0603af7204e77f6e6905a84cf0   (PR #34)
B1 merged head  = de63631ad88b42ad8a4bc1dbbc3997b25ab93d53
audited code head = 39ddd27761ff7b3a08fd6311ec5e27a9326c7d82
contract blob   = a1df976deea70daea754d89574c47165140d00d0
                  docs/AI-05_EVIDENCE_EXECUTION_PLAN.md
```

The contract reached `main` through PR #35 (Amendment 1). It was **not modified by B1**: its blob
hash is identical before and after the merge, which is the check that makes that statement
verifiable rather than asserted.

### What B1 built

```text
plugins/evidence/   7 modules, 3018 lines
tests/evidence/     5 modules, 1751 lines
```

The record model with typed per-family payloads, the §15.2 leaf field table held as data (52
rows), `content_digest` and `record_digest` plus `value_digest`, the §14.9 named grammars, the
§6.5 six-event producer registry, and the §6.6 cross-field rules.

### Verified

```text
evidence tests   = 159 passed, 1 skipped
whole repository = 1771 passed, 1 skipped, 5 deselected
Layer 0          = PASS (13 checks)
T35 boundary     = clean — no network client, no subprocess, no eval/exec/compile,
                   no routing/tools import, no secret logging
storage boundary = clean — no file I/O, no serializer, no JSON/YAML/SQLite,
                   no filesystem access anywhere in the package
contract         = unmodified; blob identical before and after the merge
```

The one skip is `T20c`, deferred against `C-1`: the contract does not name the published
admission rule set. It is reported as a skip rather than faked.

### Recorded, not hidden

- **C11 is a limitation of the contract's test model, not of the implementation.** §15.5's
  canonical case C11 requires two records differing only in `producer`, and §6.5 registers
  exactly one producer token per admitted event, so no admitted pair exists to compare. C11 is
  not deleted, not weakened, and not satisfied by a manufactured record. Closing it would require
  a contract amendment, which B1 deliberately did not make.
- **Four gaps were closed in the implementation before they were closed by a test.** G5, G9, G12
  and G16 were proven indirectly at first; a later test-only commit added seven tests so that all
  sixteen now have a direct assertion. Recorded because a gap closed without a test is closed by
  argument.
- **AI-05 persists nothing.** B1 is a pure logical core with no Store, so no `EvidenceRecord` is
  written anywhere. AI-04's `evidence_ref` is therefore still always `null`, exactly as AI-04
  records: B1 gives it something to point at in principle, but nothing yet to point at in fact.
  That null state is an unchanged fact about AI-04, not unfinished work in B1.

```text
SecurityLab           = UNCHANGED
AI-02 / AI-03 / AI-04 = UNCHANGED
Router (AI-07)        = DEFERRED / UNIMPLEMENTED
main                  = contains AI-05-B1
```

## Status semantics
`PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN`

Do not turn missing environment, skipped execution, or blocked actions into PASS.