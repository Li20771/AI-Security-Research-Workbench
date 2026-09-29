# Project Status
> Baseline: 2026-09-26

## Current stage
**AI-03 — Context Plugin**

AI-00 architecture and repository baseline is complete. **AI-01 DSH Baseline is COMPLETE** — see
[AI-01 final gate status](#ai-01-final-gate-status). **AI-02 Model Layer is COMPLETE** — see
[AI-02 final gate status](#ai-02-final-gate-status) and
[AI-02_CLOSEOUT_2026-09-29.md](AI-02_CLOSEOUT_2026-09-29.md).

AI-03 is the current stage but **NOT STARTED**: no AI-03 implementation has begun.

The GitHub `main` branch protection requirement is **BLOCKED** by the current GitHub
Free/private-repository plan and is retained as a documented platform limitation; it is not
treated as a PASS.

## Start Here

This file is the single entry point for deciding what to do next.

### Current work item

**AI-03 — Context Plugin**

AI-03 has **not started**. When it begins, it builds on the completed AI-02 merge commit
`75f7f661f5a0a3c4b2725c8fdeca161efc02c80b`.

The closed AI-01 execution plan remains at
[docs/AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)
(frozen; amended 2026-09-28 — exit criteria redefined, see its §6.1 and §9).

The frozen AI-02 contract remains at
[docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md](AI-02_MODEL_LAYER_EXECUTION_PLAN.md)
(frozen at AI-02-A; amended four times, see its §17.1 amendment log).

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

- AI-03 Context Plugin implementation — **current stage, not started**
- AI-04 Guard implementation
- AI-05 Evidence implementation
- AI-06 Security Tools implementation
- AI-07 Router implementation

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
- Executable Context plugin
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

## Status semantics
`PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN`

Do not turn missing environment, skipped execution, or blocked actions into PASS.