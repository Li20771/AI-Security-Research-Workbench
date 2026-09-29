# Project Status
> Baseline: 2026-09-26

## Current stage
**AI-03 — Context Plugin**

AI-00 architecture and repository baseline is complete. **AI-01 DSH Baseline is COMPLETE** — see
[AI-01 final gate status](#ai-01-final-gate-status). **AI-02 Model Layer is COMPLETE** — see
[AI-02 final gate status](#ai-02-final-gate-status) and
[AI-02_CLOSEOUT_2026-09-29.md](AI-02_CLOSEOUT_2026-09-29.md).

AI-03 is **COMPLETE** — all exit criteria C0–C8 satisfied, C8 by required CI on its own head.
Its contract, implementation, verification, and evidence are on branch
`feature/ai-03-context-plugin`, and its evidence is recorded in
[AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md](AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md).
PR **#28 is OPEN and NOT MERGED**: `main` does not yet contain AI-03. See
[AI-03 status](#ai-03-status).

The GitHub `main` branch protection requirement is **BLOCKED** by the current GitHub
Free/private-repository plan and is retained as a documented platform limitation; it is not
treated as a PASS.

## Start Here

This file is the single entry point for deciding what to do next.

### Current work item

**AI-03 — Context Plugin — merged? No. Awaiting human merge decision.**

```text
branch           = feature/ai-03-context-plugin
validated head   = 7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011  (last code commit)
PR               = #28 (OPEN, MERGEABLE, not merged)
required CI      = SUCCESS (run 36518367883 on the code head)
exit criteria    = C0-C8 all PASS
```

> CI status belongs to a commit. Writing a SHA into a file creates a commit, so
> any SHA recorded here is one commit behind the file stating it. **The current
> status is what GitHub reports on PR #28**, and nothing here is `PASS` on the
> strength of a self-referential SHA.

AI-03's implementation and verification are complete and its exit criteria are satisfied. The
remaining action is a **human merge decision** on PR #28 — the last step of AI-03-C, and
deliberately not taken by the agent that implemented the phase. After merge, this file records
the merge SHA and moves the current stage to AI-04.

Pushing was authorised and performed for this branch. No merge, no force push, and no history
rewrite was performed at any point.

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

- AI-04 Guard implementation
- AI-05 Evidence implementation
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
- AI-03 Context Plugin — **implemented, verified, and COMPLETE** on branch
  `feature/ai-03-context-plugin`; PR #28 is open and **not merged**, so `main` does not
  yet contain it (see [AI-03 status](#ai-03-status))
- Executable Guard plugin
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
AI-03-C  = COMPLETE      PR opened; merge is the remaining human decision
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
PR #28            = OPEN, MERGEABLE, NOT MERGED
CI run 36518367883 @ 7a29197 = SUCCESS
  Layer 0 — repository policy ......... success (13 checks)
  Layers 1-3 — offline model+context .. success
    layer 1 = 488 passed
    layer 2 = 764 passed
    layer 3 =  64 passed, 1 skipped
```

```text
SecurityLab    = UNCHANGED
main           = UNCHANGED (8c5df3e); AI-03 is NOT on main until PR #28 is merged
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

**`main` does not contain AI-03.** PR #28 is open and unmerged; until a human merges it, this
status describes a branch.

Recorded, not hidden:

- `docs/MASTER_ROADMAP.md` (P1) and `docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` (P3) are
  read and recorded with their revisions but contribute **no context items**, because neither
  contains a structurally declared state and the extractor does not read prose. A deliberately
  narrow grammar was chosen over one that guesses.
- The Context cache is **in-memory only**. A persistent cache needs a storage location, a
  retention rule, and a cleanup rule; shipping one without those would ship a second,
  undeclared source of truth.
- AI-03 **adds no layer 4** — the Context plugin has no network surface.

## Status semantics
`PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN`

Do not turn missing environment, skipped execution, or blocked actions into PASS.