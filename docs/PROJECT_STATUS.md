# Project Status
> Baseline: 2026-09-26

## Current stage
**AI-10 — Cross-Agent Review — COMPLETE / MERGED / CLOSED.**
AI-09 — Codex Provider Integration is **COMPLETE / MERGED / CLOSED** as
`b8b815b181e69f7651efdde97dd9473a3e619c7f` (PR #54). AI-08 — Codex Second Agent is
**COMPLETE and MERGED** as `edb7dfc82ce51123482ac357fb9319dca2fa0d9a` (PR #52).
AI-07 — Model Router v1 is **COMPLETE / CLOSED**. The next work item is
**AI-11 — AI Security Benchmark**, which is **NOT STARTED**.

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
`0403fcd83b740f0603af7204e77f6e6905a84cf0` (PR #34). B1 is the **offline logical core only**.

**AI-05-B2-P1 is COMPLETE and MERGED** — merged to `main` as
`844df7beb3ada381c71c945991c551403595885a` (PR #41). P1 added the §18.1 workspace agreement
boundary and T12/T13.

**AI-05-B2-P2 is COMPLETE and MERGED** — merged to `main` as
`b8692c181f646386430dccd419595ca88e0cc4db` (PR #42). P2 added the §17 stored-form round-trip.

**AI-05-B2-P3 is COMPLETE and MERGED** — merged to `main` as
`67515ff96dbd95ee5a8f73923d5eadc3f097501a` (PR #44). P3 added the admission pipeline, the
filesystem Store, uniqueness, staged discard and the §31 Layer 0 evidence check.

**AI-06 — Security Research Tools Plugin is COMPLETE and MERGED** — merged to `main` as
`3b1917ab596931ec89de8c17a02266b5902557a5` (PR #47). The Tool API, eight adapter families, the Guard,
workspace, execution, vehicle and secret boundaries, the Evidence projection and the AI-06
Layer 0 check are all in this PR. Full evidence in
[AI-06_EVIDENCE_2026-10-01.md](AI-06_EVIDENCE_2026-10-01.md).

**AI-07 — Model Router v1 is COMPLETE and MERGED** — AI-07-A (contract, PR #48) merged as
`963c181ce2c41aed8f5e400193ad3aeda03d6bb0`, and AI-07-B (implementation, PR #49) merged as
`e57541f90d693472c695143af0bc79215d462fab`. The phase is **CLOSED**. Its contract blob was not
modified by AI-07-B. Full evidence in
[AI-07_EVIDENCE_2026-10-01.md](AI-07_EVIDENCE_2026-10-01.md). See [AI-07 status](#ai-07-status).

**AI-05-B2 is COMPLETE**: every stage of its frozen scope has been implemented and merged. **AI-05
as a whole remains INCOMPLETE**, because C-1 is still DEFERRED — §30 step 7 is unimplemented,
T22a/T22b/T22c remain unrunnable, and §32's C6 gate is therefore not closed. See
[AI-05 status](#ai-05-status).

The GitHub `main` branch protection requirement is **BLOCKED** by the current GitHub
Free/private-repository plan and is retained as a documented platform limitation; it is not
treated as a PASS.

## Start Here

This file is the single entry point for deciding what to do next.

### Current work item

**AI-10 — Cross-Agent Review — COMPLETE / CLOSED.**

**AI-11 — AI Security Benchmark — NEXT; NOT STARTED.** No contract, no implementation and
no result exists for it.

```text
AI-10-A     = COMPLETE / MERGED    contract frozen           (PR #56, 3613896d)
Amendment 1 = APPLIED / MERGED     §9.3.1 statement identity (PR #58, fbf1e1b0)
Amendment 2 = APPLIED / MERGED     §5.4 independence_status  (PR #59, 32126416)
AI-10-B     = COMPLETE / MERGED    the review core           (PR #60, d22fe25c)
AI-10       = CLOSED

merge       = d22fe25c5fe94ae697083fd9fbdfaf3976785703   (PR #60, true two-parent merge)
base        = main @ 32126416aa719ff204a5a690f868ff98122f1e22
branch      = feature/ai-10-review-core-correction   (merged; retained)
contract    = docs/AI-10_CROSS_AGENT_REVIEW_EXECUTION_PLAN.md
contract blob = fc6f709611fcf7a8fcf6845097bf130920445fdc
                     UNCHANGED by AI-10-B
evidence    = docs/AI-10_EVIDENCE_2026-10-02.md

home        = review/ — a Workbench CORE service, not a plugin
ingress     = EXTERNAL REVIEW MATERIAL INGRESS — explicitly supplied material only
independence= AI-08's I1-I8 consumed read-only; `independence_status` is a second,
              orthogonal axis (NOT_APPLICABLE / UNCHECKED / OBSERVED)
verification= a request only; the controlled caller invokes AI-06, under AI-04
evidence    = AI-10 writes NO EvidenceRecord in v1, under no producer token
decision    = human-supplied run data; never model-generated, never pre-filled

live        = NOT_RUN     no provider call has been made
automatic acquisition of real Agent analysis material = BLOCKED / PREREQUISITE
durable review evidence / durable HumanDecision       = DEFERRED to an AI-05 amendment
```

**AI-10 is closed as of the PR #60 merge.** The merge closed the implementation and its
offline verification; it did not close the blocker above, and it produced no live run.

**Retained record — AI-09: COMPLETE / MERGED / CLOSED.**

```text
AI-09-A     = CONTRACT FROZEN      (2026-10-02)
AI-09-B     = COMPLETE / MERGED    PR #54
AI-09       = CLOSED

merge       = b8b815b181e69f7651efdde97dd9473a3e619c7f   (PR #54, true two-parent merge)
base        = main @ 4614a2ccb1a90ccf9c9e81bbe2bca87d44a47ae1
branch      = feature/ai-09-codex-integration   (merged; retained)
contract    = docs/AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md
contract blob = e9728b184740074e5c8f718db6b45f859c3802bf
                     UNCHANGED by AI-09-B
evidence    = docs/AI-09_EVIDENCE_2026-10-02.md

provider    = mimo — the existing profile; NO third provider identity
models      = mimo/mimo-v2.6-pro, mimo/mimo-v2.6-flash   (no default, no fallback)
backend     = integrations/codex/   a namespace package
reserved    = providers/openai-compatible/ stays RESERVED / DISABLED / UNIMPLEMENTED

live        = NOT_RUN     no provider call has been made by this phase
capability  = UNKNOWN     every capability, every shipped model profile
connectivity= NOT VERIFIED
```

**AI-09-A closed contract gate C0; AI-09-B closed C1–C12.** The phase is complete as of the
PR #54 merge. No provider call has been made by this phase, no capability is VERIFIED, and
connectivity is NOT VERIFIED — the merge closed the implementation, not the provider question.

**Retained record — AI-08: COMPLETE / MERGED.**

```text
AI-08-A merge SHA  = 2117cdf49940bb97f5f18a6447fbc2f0137b31e7   (PR #51)
AI-08-B merge SHA  = edb7dfc82ce51123482ac357fb9319dca2fa0d9a   (PR #52)
contract           = docs/AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md
contract blob      = a01e03f5306299a0a4442648eeb8fdcfce6bd8dd   UNCHANGED by AI-09-A
amendments         = 4   Amendment 1 (review corrections, §22)
                         Amendment 2 (terminal-result invariant, §22)
                         Amendment 3 (Guard-bound tool invocation boundary, §22)
                         Amendment 4 (required CI configuration in scope, §22)
```

Two facts govern this phase and are recorded where a reader will find them rather than inferred:

```text
AI-08 v1 has NO provider binding. Every capability on every shipped model profile is
UNKNOWN and no provider call has ever been made in this repository, so AI-08 v1 cannot
execute anything through the provider layer and does not try to. Real Codex provider and
model wiring is AI-09's.

AI-08 v1 writes NO AI-05 EvidenceRecord. The only producer token admissible for an
EXECUTION record is "ai-06", and AI-08 is not AI-06; writing under that token would be a
false producer claim. The AI-08 producer token is DEFERRED pending an AI-05 amendment,
and AI-08-B MUST NOT write Evidence in the meantime.
```

**Retained record — AI-07: COMPLETE / MERGED / CLOSED.**

```text
AI-07-A merge       = 963c181ce2c41aed8f5e400193ad3aeda03d6bb0   (PR #48, merged)
AI-07-B merge       = e57541f90d693472c695143af0bc79215d462fab   (PR #49, merged)
AI-07-B head        = 679c927f6b4c82369c4e26b790dd31a8ac324598
                      the merge tree equals this tree — no content change
AI-07 contract      = frozen, docs/AI-07_MODEL_ROUTER_EXECUTION_PLAN.md
AI-07 contract blob = 2f8dcba8f9c2ca36e3d917fc6b69c3a5cb7f36fe
                      unchanged by AI-07-B, and unchanged by AI-08-A
AI-07 evidence      = docs/AI-07_EVIDENCE_2026-10-01.md
```

**Retained record — AI-05-B2: COMPLETE / MERGED.** All three stages are merged. AI-05 itself is
**not** closed: C-1 remains DEFERRED.

```text
AI-05 contract      = frozen, docs/AI-05_EVIDENCE_EXECUTION_PLAN.md
AI-05 contract blob = dd062148938f902109b49a496bb6051c3331a349
                      current, after Amendment 2
B2 Decision Record  = docs/AI-05-B2_DECISIONS_2026-10-01.md
B2 decision blob    = e6249c856d23afba5b97143bec60be06168a4a48

AI-05-A             = COMPLETE / MERGED   contract frozen, 2 amendments
AI-05-B1            = COMPLETE / MERGED   offline logical core
AI-05-B1 merge      = 0403fcd83b740f0603af7204e77f6e6905a84cf0  (PR #34, merged)

AI-05-B2-P1         = COMPLETE / MERGED   §18.1 workspace agreement, T12/T13
AI-05-B2-P1 merge   = 844df7beb3ada381c71c945991c551403595885a  (PR #41, merged)

AI-05-B2-P2         = COMPLETE / MERGED   §17 stored-form round-trip
AI-05-B2-P2 merge   = b8692c181f646386430dccd419595ca88e0cc4db  (PR #42, merged)

AI-05-B2-P3         = COMPLETE / MERGED   admission pipeline, filesystem Store,
                                          uniqueness, staged discard,
                                          §31 Layer 0 evidence check
AI-05-B2-P3 merge   = 67515ff96dbd95ee5a8f73923d5eadc3f097501a  (PR #44, merged)

AI-05-B2            = COMPLETE            its frozen scope is implemented and
                                          merged; C-1 was never part of it
AI-05 overall       = INCOMPLETE          C-1 is DEFERRED, so §30 step 7 is
                                          unimplemented and §32 C6 is not closed

B1 verification-time contract blob
                    = a1df976deea70daea754d89574c47165140d00d0
```

AI-04 is closed. AI-05-A is closed: the contract was frozen and then **amended twice**.

**Amendment 1** established the B1 implementation-ready schema — the leaf-level §15.2 digest table
in place of the container table, the §6.5 admitted-producer registry, the §14.9 grammar table, and
the `ObservationFamily` vocabulary.

**Amendment 2** reconciled the human-approval v1 representability wording. A human approval remains
conceptually a `DECISION` with `actor.type = human`, but the event is deferred and is not
representable in v1, so the T4c matrix row now expects `REJECTED`, consistent with §6.5 and §6.6.

The current contract blob is `dd062148938f902109b49a496bb6051c3331a349`. The blob that B1 was
built, verified and merged **against** is `a1df976deea70daea754d89574c47165140d00d0`; Amendment 2
came afterwards. B1's own evidence records the earlier value, and that is the correct historical
fact rather than a stale pointer.

AI-05-B1 is closed and merged. It built the record model, the §15.2 leaf field table, the two
digests, the §14.9 named grammars, the §6.5 registry and the §6.6 cross-field rules — and
nothing else. It added **no storage, no admission pipeline and no Store**. Full evidence is in
[AI-05-B1_EVIDENCE_2026-10-01.md](AI-05-B1_EVIDENCE_2026-10-01.md).

> **AI-05-B2 is complete and merged.** P1 (workspace agreement), P2 (stored-form round-trip) and
> P3 (admission pipeline, filesystem Store, uniqueness, staged discard, §31 Layer 0 check) are all
> on `main`. There is still no `rules.py`, and that is not an omission: C-1 remains DEFERRED, so
> §30 step 7 is unimplemented and no document should read an `ACCEPTED` from `admit()` or
> `admit_to_store()` as a full §30 admission.

The merged AI-03, AI-04, AI-05-B1 and both merged AI-05-B2 branches
(`feature/ai-03-context-plugin`, `feature/ai-04-guard-implementation`,
`feature/ai-05-b1-logical-core`, `feature/ai-05-b2-admission-store-lifecycle`,
`feature/ai-05-b2-stored-form-loader`) may be deleted.

The two AI-07 branches (`feature/ai-07-router-contract`, `feature/ai-07-router-v1`) may also be
deleted. Both are contained in `main`: `feature/ai-07-router-v1` at
`679c927f6b4c82369c4e26b790dd31a8ac324598` has no commit that `main` does not already contain,
and no file differs between that head and `main`. Their deletion is a plain branch delete, not a
force delete, and nothing in AI-07 depends on them surviving.

No force push and no history rewrite was performed at any point in AI-03, AI-04, AI-05-B1 or
AI-05-B2.
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

```text
AI-11   AI Security Benchmark                 NEXT      NOT STARTED
AI-12   routing v2 fallback / escalation      queued    NOT STARTED
AI-13   retry / timeout / cancellation /
        checkpoint / resume /
        failure classification                queued    NOT STARTED
```

- **AI-11 — AI Security Benchmark — NEXT, NOT STARTED.** No contract, no implementation,
  no test and no result exists for it. It consumes per-Agent result data; it is not started
  by AI-10's closeout, and nothing in AI-10 depends on it.

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
- Codex integration
- Benchmark dataset
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

**AI-05 — Evidence / Audit Plugin: INCOMPLETE.** B1 and the whole of B2 are complete and merged.
AI-05 is not closed, and the reason is C-1 rather than anything B2 left undone.
Full evidence in [AI-05-B1_EVIDENCE_2026-10-01.md](AI-05-B1_EVIDENCE_2026-10-01.md),
[AI-05-B2-P2_EVIDENCE_2026-10-01.md](AI-05-B2-P2_EVIDENCE_2026-10-01.md) and
[AI-05-B2-P3_EVIDENCE_2026-10-01.md](AI-05-B2-P3_EVIDENCE_2026-10-01.md).

```text
AI-05-A     = COMPLETE / MERGED   contract frozen, 2 amendments
AI-05-B1    = COMPLETE / MERGED   offline logical core
AI-05-B2-P1 = COMPLETE / MERGED   §18.1 workspace agreement, T12/T13
AI-05-B2-P2 = COMPLETE / MERGED   §17 stored-form round-trip
AI-05-B2-P3 = COMPLETE / MERGED   admission pipeline, filesystem Store,
                                  uniqueness, staged discard,
                                  §31 Layer 0 evidence check
AI-05-B2    = COMPLETE            its frozen scope is implemented and merged
AI-05       = INCOMPLETE          C-1 is DEFERRED, so §30 step 7 is
                                  unimplemented and §32 C6 is not closed

B1 merge SHA    = 0403fcd83b740f0603af7204e77f6e6905a84cf0   (PR #34)
B1 merged head  = de63631ad88b42ad8a4bc1dbbc3997b25ab93d53
audited code head = 39ddd27761ff7b3a08fd6311ec5e27a9326c7d82

P1 merge SHA    = 844df7beb3ada381c71c945991c551403595885a   (PR #41)
P1 head         = 2474ddbea6fc71054f79b30ada6db3efec292557

P2 merge SHA    = b8692c181f646386430dccd419595ca88e0cc4db   (PR #42)
P2 head         = a403a792420bfd33904d98e9ad78d66d72ecf2ec
P2 base         = 844df7beb3ada381c71c945991c551403595885a

P3 branch       = feature/ai-05-b2-p3-admission-store-lifecycle
P3 base         = bf0790ac0ba1de2b79d4835c70b8a50fb12502c8
P3 head         = 6b3f3a0909b7f0542d9581afa4fb3689ea2ac968
P3 merge SHA    = 67515ff96dbd95ee5a8f73923d5eadc3f097501a   (PR #44)
P3 evidence     = docs/AI-05-B2-P3_EVIDENCE_2026-10-01.md

contract blob   = dd062148938f902109b49a496bb6051c3331a349
                  docs/AI-05_EVIDENCE_EXECUTION_PLAN.md
                  current, after Amendment 2
B2 decision blob = e6249c856d23afba5b97143bec60be06168a4a48
                  docs/AI-05-B2_DECISIONS_2026-10-01.md

B1 verification-time contract blob
                = a1df976deea70daea754d89574c47165140d00d0
                  the blob B1 was built, verified and merged against
```

### What B2 has delivered

```text
P1   §18.1 workspace agreement — the one admission condition B1 did not hold.
     references.context[].workspace_id must agree with provenance.workspace_id,
     and artifacts.items[].owner_workspace_id must agree unless the artifact is
     explicitly external (§18.1's exemption). T12 and T13, with T13 proven
     against a deliberately constructed two-workspace input so that a filtering
     implementation would be distinguishable from a rejecting one.
     4 files, +569 / -5.  No Store, no uniqueness, no lifecycle.

P2   §17 stored-form round-trip: to_stored_mapping, load_stored and
     verify_stored_integrity. A written record is re-read losslessly, its
     generated fields are restored on the stored path only, and both digests are
     recomputed and compared with the stored values. 5 files, +1376 / -47.
     No Store, no filesystem persistence, no uniqueness, no lifecycle.

P3   the admission pipeline, the filesystem Store, uniqueness, staged discard
     and §31's Layer 0 structural check — merged as 67515ff9 (PR #44).
     admit_to_store() runs §30 steps 1-6 and 8-14 and persists. The Store
     writes UTF-8 JSON, one record per file, atomically and without overwrite;
     it computes no digest and canonicalizes nothing. Duplicate evidence_id is
     REJECTED with the existing record untouched; duplicate content_digest is
     ACCEPTED, and both records are stored. discard is staged-only.
     The two tiers are two types: StagedEvidenceStore writes, and
     PromotedEvidenceStore has no write at all, so admission cannot be aimed at
     the durable tier and there is no programmatic promotion path.
     Layer 0 is now 14 checks.
```

`AI-05-B2 = COMPLETE` means exactly this: **the frozen implementation scope of B2 is
implemented and merged.** It does not mean §30 is complete. C-1 was never part of B2's declared
scope, and its absence is a residual of the AI-05 contract rather than something B2 quietly left
undone — or something this closeout may quietly implement.

### What B2 has not delivered

```text
nothing from its own frozen scope. B2's declared work is complete and merged.

D11  four items remain undefined and were deliberately not frozen: the
     retrieval return shape, the superseded_by query shape, the promotion API,
     and discard cleanup granularity. The Store's Python surface is documented
     as provisional rather than as contract.

C-1  remains DEFERRED. The published admission rule set is not published, so
     §30 step 7 is unimplemented and T22a / T22b / T22c remain unrunnable. An
     ACCEPTED from admit() or admit_to_store is therefore not a full §30
     admission, and no document should read it as one.
```

The contract reached `main` through PR #35 (Amendment 1) and was amended a second time by PR #38
(Amendment 2), which reconciled the human-approval v1 representability wording. Neither amendment
was made by B1, and B1 was **not** modified by either: its blob hash is identical before and after
the B1 merge, which is the check that makes that statement verifiable rather than asserted.

The distinction between the two blob values is deliberate. `a1df976` is the contract B1's evidence
was produced against and stays recorded as such there; `dd06214` is what `main` carries now.

Amendment 2 changed what the contract **says** rather than what it **requires**. §6.5 already
registered no producer for the human-approval event and §6.6 already rejected a non-service
`DECISION` actor, so nothing admitted a human-actor record; four passages elsewhere said otherwise
and now agree. That is why B1's evidence suite is unchanged and still green — the implementation
was already on the correct side of the boundary the contract had drawn.

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

## AI-06 status

**AI-06 — Security Research Tools Plugin: COMPLETE / MERGED.**
Frozen contract `docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md`.

```text
AI-06-A merged contract      1cff20f7969c61c2870e8ed13c86cf7d784644ea
effective contract, after
  Amendment 1                4b05155c9bd7ed2d7e25f7e23a0471de82a880f8
```

The two are not interchangeable: `1cff20f7` is what AI-06-A merged, and
`4b05155c` is what AI-06-B implements against.

```text
AI-06-A     = COMPLETE / MERGED   contract frozen (PR #46)
AI-06-B     = COMPLETE / MERGED   implementation (PR #47), one review fix in
                                  the same PR (Guard attribution, section O
                                  of the evidence record)
AI-06       = COMPLETE

merge SHA   = 3b1917ab596931ec89de8c17a02266b5902557a5   (PR #47)
evidence    = docs/AI-06_EVIDENCE_2026-10-01.md
```

Measured on the branch head:

```text
tests/security_tools          160 passed, 1 skipped
whole repository             2113 passed, 2 skipped, 5 deselected
Layer 0                      PASS (15 checks)
```

```text
NOT_RUN   GitHub and MCP operations  — boundary declared, no operation (§13.2, §13.5, §16)
NOT_RUN   Ghidra                     — declared by the roadmap, not taken on in v1
NOT_RUN   the T17 symlink case       — this host refuses symlink creation (WinError 1314)
BLOCKED   real CAN / ECU / vehicle   — refused by §12.2, by design and asserted

Router (AI-07) = DEFERRED / UNIMPLEMENTED — untouched, no interface reserved
SecurityLab    = UNCHANGED
```

## AI-07 status

**AI-07 — Plugin 5: Model Router v1: COMPLETE / MERGED / CLOSED.**

```text
AI-07-A  = COMPLETE / MERGED   contract frozen        (PR #48)
AI-07-B  = COMPLETE / MERGED   implementation         (PR #49)
AI-07    = COMPLETE / CLOSED

merge SHA (A)  = 963c181ce2c41aed8f5e400193ad3aeda03d6bb0
merge SHA (B)  = e57541f90d693472c695143af0bc79215d462fab
PR #49 head    = 679c927f6b4c82369c4e26b790dd31a8ac324598
                 the merge tree equals this tree — the merge changed no content

contract = docs/AI-07_MODEL_ROUTER_EXECUTION_PLAN.md
blob     = 2f8dcba8f9c2ca36e3d917fc6b69c3a5cb7f36fe   (after Amendment 1)
amendments = 1
         identical at 963c181, 679c927 and e57541f — AI-07-B did not modify it

evidence = docs/AI-07_EVIDENCE_2026-10-01.md
```

Measured on `main` at `e57541f`:

```text
tests/routing                 134 passed
tests/security_tools           16 passed   (the T46/T47 file)
whole repository              2271 passed, 2 skipped, 5 deselected
Layer 0                       PASS (16 checks)
compileall / providers.validate / git diff --check     clean
```

Required CI ran on the merge commit `e57541f` itself (run 36880374948, push event):
**Layer 0 — repository policy** and **Layers 1-3 — offline model and context layers** both
`success`. C11 is closed by that run; a local run would not have closed it.

The router is implemented in `routing/`. Every capability on every shipped profile is
`UNKNOWN`, so a request requiring one yields `NO_ELIGIBLE_MODEL`. That is the v1 design, and
T9 is the synthetic control proving the rule is not a blanket refusal.

```text
DEFERRED  tuned rule set              AI-00 F-12: Router v2's, on benchmark data
DEFERRED  independent Agent identity  AI-08 owns identity, execution and independence semantics
DEFERRED  policy discovery            Q-1, AI-04's existing deferred item
DEFERRED  cost-class routing          AI-02 defines no cost-class vocabulary
DEFERRED  latency class               AI-02 exposes no latency class
UNKNOWN   every capability on every shipped profile
NOT_RUN   Ghidra, GitHub/MCP operations, the T17 symlink case   (AI-06, unchanged)
BLOCKED   real CAN / ECU / vehicle    AI-04 §8.2 / D-12, by design and asserted
```

Closing AI-07 does not convert any line above into a PASS.

Amendment 1 reconciled four internal inconsistencies before implementation began: `sensitivity`
had an eligibility effect with no AI-02 source field; `max_cost_class` named a vocabulary AI-02
does not define; `fallback` was described as a boundary with no v1 trigger; and
`require_independence` needed an explicit non-claim. Security and authority impact: none.

One fact governs v1 and is worth stating where a reader will find it: **every capability on every
shipped model profile is `UNKNOWN`**, so a request that requires a capability has no eligible
candidate and the outcome is `NO_ELIGIBLE_MODEL`. That is the honest state, not a defect.

## AI-08 status

**AI-08 — Codex Second Agent: COMPLETE / MERGED.** Contract frozen at AI-08-A, implemented by
AI-08-B, merged as `edb7dfc82ce51123482ac357fb9319dca2fa0d9a` (PR #52).

```text
AI-08-A     = COMPLETE / MERGED    contract frozen   (PR #51, 2117cdf4)
AI-08-B     = COMPLETE / MERGED    agent runtime     (PR #52, edb7dfc8)
AI-08       = CLOSED

base        = main @ a7c4a1e2536536940d96431883dadb592f7c151a
contract    = docs/AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md
contract blob = a01e03f5306299a0a4442648eeb8fdcfce6bd8dd   UNCHANGED by AI-09-A
amendments  = 4   Amendment 1 (review corrections)
                  Amendment 2 (terminal-result invariant)
                  Amendment 3 (Guard-bound tool invocation boundary)
                  Amendment 4 (required CI configuration in scope)
```

AI-08 makes Codex a second Agent with its own identity, its own execution instance, its own result
and its own provenance — not a DSH subprocess, not a DSH internal model switch, not a provider and
not a model profile. **AI-08-A freezes the contract and implements nothing.**

```text
FROZEN at AI-08-A
    the core-agent-layer identity, and that AI-08 is not a plugin, a provider,
      a model profile or a DSH child process
    AgentId — closed, exactly dsh | codex; a free string is never an identity
    AgentRole — closed, PRIMARY | INDEPENDENT_SECOND; the registration is fixed
    the three distinct questions: ActorType / AgentId / AgentRole
    that identity is registered, never discovered
    the Router boundary: a hint stays a hint; resolve_agent is the only way a
      candidate becomes an identity
    the execution contract: one request, one ExecutionId, one terminal result
    that the invariant holds for ALL THREE outcomes: FAILED and BLOCKED still
      terminate in exactly one AgentResult, and "the body did not start" is not
      "no AgentResult exists"
    that AgentResult.result is always present, and for FAILED/BLOCKED refers to
      terminal failure/block metadata rather than a task result
    that the AgentExecutionRequest carries NO ContextResponse, and that the
      runtime establishes one execution-owned ContextResponse per execution
    that runtime input may carry task content and durable records may not
    Context isolation: same workspace, per-execution ContextResponse
    the independence definition I1-I8, with I3 (result-is-not-input) as the key
      v1 boundary
    that I5 is fresh GuardRequest + fresh GuardDecision, NOT request_digest
      uniqueness; request_digest is not an identity
    what independence cannot prove, and that it is never a verdict
    that AgentRole.INDEPENDENT_SECOND is an architectural role and NOT an
      independence finding; the role alone never satisfies I1-I8
    AgentResult — attributed by agent_id + execution_id, a claim with a
      producer, never a PASS, and carrying no producer field in v1
    AgentExecutionOutcome — COMPLETED | FAILED | BLOCKED, three members;
      BLOCKED is execution-level, and a Guard-refused tool call never rewrites
      the execution outcome
    the Guard boundary: unchanged, fresh decision per invocation, and no
      Agent-specific permission policy claimed or inferred
    the Evidence boundary: AI-08 writes no EvidenceRecord in v1; execution-level
      permission records satisfy the roadmap requirement without one
    the cross-agent result sharing prohibition
    the Codex provider boundary, deferred whole to AI-09
    the repository layout, and the two AI-07 test assertions maintained
```

Measured on the AI-08-A branch:

```text
tests/routing                 134 passed
whole repository             2271 passed, 2 skipped, 5 deselected
Layer 0                       PASS (16 checks)
```

```text
DEFERRED  the AI-08 producer token for Evidence   an AI-05 amendment is required
                                                  before it exists (§13.2)
DEFERRED  a per-Agent permission ceiling          OUT OF SCOPE. AI-08 v1 does not
                                                  enforce or claim one, and AI-08-B
                                                  MUST NOT infer one from AgentId,
                                                  AgentRole or ActorType (§12.1.1)
DEFERRED  AI-09  real Codex provider / model integration
DEFERRED  AI-10  cross-agent review / second-opinion closure
DEFERRED  AI-11  benchmark comparison
DEFERRED  AI-12  routing v2 fallback / escalation
DEFERRED  AI-13  retry / timeout / cancellation / checkpoint / resume /
                 failure classification
UNCHANGED AI-05 C-1, AI-05 D11, AI-03 G-14
```

**AI-08-A closes contract gate C0 and nothing else.** C1–C17 belong to AI-08-B, and no part of
AI-08 is a `PASS`.

Two facts are recorded here so that neither is inferred later:

```text
AI-08 v1 has NO provider binding. Every capability on every shipped model profile is
UNKNOWN and no provider call has ever been made in this repository. AI-08 v1 therefore
cannot execute anything through the provider layer, and does not try to. That is the
honest state, not a defect; real wiring is AI-09's.

AI-08 v1 writes NO AI-05 EvidenceRecord. `admitted_events_for(EXECUTION, None)` returns
exactly one row, "AI-06 tool execution", whose producer token is "ai-06", and
`g_registered` admits no other. An AI-08 record written under "ai-06" would be a false
producer claim, which this repository refuses everywhere else. AI-08-B MUST NOT write
Evidence; the token is DEFERRED pending an AI-05 amendment.
```

### AI-08-B — Agent runtime / execution layer

**COMPLETE / MERGED.** Merged as `edb7dfc82ce51123482ac357fb9319dca2fa0d9a` (PR #52). The AI-08-A
contract was not modified by the implementation.

```text
AI-08-B branch  = feature/ai-08-agent-runtime
AI-08-B base    = 2117cdf49940bb97f5f18a6447fbc2f0137b31e7   (the AI-08-A merge)
AI-08-B merge   = edb7dfc82ce51123482ac357fb9319dca2fa0d9a   (PR #52)
AI-08           = CLOSED
```

The paragraph below is retained as the **historical record of what the branch contained at the
time it was written**. It is not the current state.

What exists now, under `agents/`:

```text
vocabulary.py    AgentId (dsh | codex), AgentRole (PRIMARY | INDEPENDENT_SECOND),
                 the frozen registration, resolve_agent
request.py       AgentExecutionRequest, and the opaque ExecutionId
result.py        AgentResult, AgentExecutionOutcome, ToolCallRef
toolcall.py      the tool path: one fresh GuardRequest and GuardDecision per invocation
body.py          AgentBody, and v1's offline deterministic body
runtime.py       execute() and run_execution() — the controller
independence.py  the I1-I8 predicate
dsh/body.py      the primary Agent's execution shape
codex/body.py    the second Agent's shape, and the AI-09 CodexBackend seam
```

```text
one AgentExecutionRequest -> one ExecutionId -> one terminal AgentResult
    for COMPLETED, FAILED and BLOCKED alike

Context      established by the runtime, one per execution, owned by it.
             The request carries a descriptor and never a ContextResponse.
Guard        AI-08 does not call Guard. AI-06 builds a fresh GuardRequest per
             invocation from the ToolRequest AI-08 supplies, whose actor is the
             AgentId. No decision is cached or reused.
Evidence     no EvidenceRecord is written. AI-08 does not import plugins.evidence,
             and its Layer 0 gate fails the build if it starts to.
Router       no import in either direction.
Provider     none. No network, no subprocess, no model binding, no credential.
```

Measured on the branch:

```text
tests/agents                 212 passed
whole repository            2483 passed, 2 skipped, 5 deselected
Layer 0                     PASS (17 checks)   the AI-08 gate is check #17
compileall                  clean
providers.validate          PASS
```

### AI-08-A Amendment 3 — Guard-bound tool invocation boundary

Found by AI-08-B's implementation review, and the first amendment resolving a
contradiction between AI-08's frozen text and **another phase's** frozen
architecture.

```text
§12 / §9.1 I5 / §13.4 quantified over EVERY tool invocation:
    a fresh GuardRequest and a fresh GuardDecision

AI-06 refuses on five paths BEFORE `ask_guard`
(dispatch.py:75 unknown tool, :79 unknown operation, :85 invalid arguments,
 :92 v1 target boundary, :99 workspace resolution; `ask_guard` is at :109).
No GuardRequest is built and no DecisionRecord exists. AI-06's own
`unattributed_summary` documents it: `decision_id` "stays empty precisely
because no evaluation produced one".

The universal could not be met. Closing it would have required duplicating
AI-06's gates in AI-08, fabricating a GuardDecision, or changing AI-06 — all
three forbidden.
```

```text
RESOLVED — GUARD-BOUND SEMANTICS. New §12.2 and §9.1.2 define:

  Guard-bound invocation   passed AI-06's pre-Guard gates and reached the Guard
                           authorization boundary. Carries a fresh GuardRequest
                           and a fresh GuardDecision.
  Pre-Guard refusal        refused before that boundary. Has NO GuardDecision,
                           and none may be fabricated.

An empty `guard_decision_id` now means exactly one thing: no evaluation
happened. It is NOT UNKNOWN and NOT BLOCKED.

Synchronised: §9.1 I5, §12, §12.2 (new), §9.1.2 (new), §13.4, §20 C9,
§21, test matrix T20 and new T44.
```

### AI-08-A Amendment 4 — required CI configuration is part of phase scope

A scope-statement correction. C17 listed the phase's diff as living inside
`agents/`, `tests/agents/`, docs, tests and the Layer 0 gate, but AI-08-B also
changed `.github/workflows/preflight.yml` so that CI syntax-checks the new
`agents/` code — `tests` was compiled and `agents` was not.

```text
.github/workflows/preflight.yml   REQUIRED CI VALIDATION INFRASTRUCTURE
NOT                               AI-08 application or runtime logic
```

New §17.2 names it with a narrow exception: a CI change is in scope only when
STRICTLY NECESSARY to validate AI-08-owned code in the required CI path, and
only when it adds or adjusts validation for `agents/` or `tests/agents/`, does
not weaken a security gate, does not enable network/provider/live execution,
does not change permissions or protected paths, and does not alter another
phase's contract or implementation. `.github/` is not an AI-08 free-edit area
and §17.2 says so. No implementation changed.

Two implementation fixes landed with Amendment 3:

```text
identity boundary   AgentExecutionRequest.__post_init__ resolves through
                    `resolve_agent`, and AgentResult.agent_id is a real AgentId.
                    Before this, `agent_id="not-registered"` constructed happily:
                    a BLOCKED result was attributed to no registered Agent, and
                    a ValueError escaped execute() on the normal path.
raw-content shape   AgentResult.result admits exactly two shapes —
                    `sha256:<64 lowercase hex>` or `ref:<opaque token>` — so
                    obvious raw-content forms cannot be stored at all. This is a
                    STRUCTURAL SHAPE guarantee, not a content classifier; the
                    full answer is AI-05's deferred C-1 and §10.2 says so.
```

```text
required CI on this branch   run 36892373480 — Layer 0 pass, Layers 1-3 pass
DEFERRED  AI-09  real Codex provider / model integration
DEFERRED  AI-10  cross-agent review / second-opinion closure
DEFERRED  AI-11  benchmark comparison
DEFERRED  AI-12  routing v2 fallback / escalation
DEFERRED  AI-13  retry / timeout / cancellation / checkpoint / resume /
                 failure classification
DEFERRED  the AI-08 producer token for Evidence   an AI-05 amendment is required
DEFERRED  a per-Agent permission ceiling          OUT OF SCOPE, and not inferred
UNCHANGED AI-05 C-1, AI-05 D11, AI-03 G-14
```

**AI-08-B is not a `PASS`.** It is implemented and locally verified; C1–C17 close only
when the phase's own evidence record and required CI do, and AI-08-A closed C0 alone.

Two facts a reader should not have to infer:

```text
The v1 bodies perform no inference. Every capability on every shipped model profile
is UNKNOWN and no provider call has ever been made in this repository, so the bodies
cannot call a model and do not pretend to. They produce a PROVENANCE REFERENCE, not a
task result. §10.2's "task result" arm is AI-09's.

AgentResult is run data. It is not an AI-05 EvidenceRecord, and no admission pipeline
runs when an execution does.
```

---

## AI-09 status

**AI-09 — Codex Provider Integration: COMPLETE / MERGED / CLOSED.**

AI-09 wires Codex's already-frozen `CodexBackend` seam to a real, already-registered provider
(`mimo`) through AI-02's already-frozen normalized invocation boundary. It is a composition, not
a new provider layer.

```text
AI-09-A     = CONTRACT FROZEN      (2026-10-02)
AI-09-B     = COMPLETE / MERGED    PR #54
AI-09       = CLOSED

merge       = b8b815b181e69f7651efdde97dd9473a3e619c7f
                     true two-parent merge; not squashed, not rebased
                     parent 1 = 4614a2ccb1a90ccf9c9e81bbe2bca87d44a47ae1
                     parent 2 = 3b83d245ac19dfeff4dc101188131e74330130c8
merged at   = 2026-10-02T06:57:50Z
base        = main @ 4614a2ccb1a90ccf9c9e81bbe2bca87d44a47ae1
branch      = feature/ai-09-codex-integration   (merged; retained)
contract    = docs/AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md
contract blob = e9728b184740074e5c8f718db6b45f859c3802bf
                     UNCHANGED by AI-09-B
evidence    = docs/AI-09_EVIDENCE_2026-10-02.md

local post-merge verification
            compileall            PASS
            Layer 0               PASS (18 checks)
            pytest -m "not layer4"
                                  2622 passed, 2 skipped, 5 deselected, 0 failed
            live provider call    NOT RUN
```

### What AI-09-B built

```text
integrations/codex/     binding.py, backend.py, reference.py, errors.py, README.md
                        a new core namespace layer; no __init__.py
tests/integrations/     122 tests, layers 1 and 2, all offline
Layer 0                 check_ai09_integration_layer(), 18 checks total
verification            Layer 0 PASS; providers.validate PASS; plugins.context.validate PASS;
                        pytest collected 2612 / 5 deselected / 2607 selected,
                        2605 passed, 2 skipped, 0 failed
```

### What AI-09-B does not claim

```text
live provider call      NOT_RUN — none has been made by this phase
Mimo connectivity       NOT VERIFIED
capability              UNKNOWN on every capability of every shipped model profile
offline fixtures        prove normalization and serialization only; they are not
                        provider evidence and they promote nothing
```

### Recorded during AI-09-B

```text
AI-02's live-transport confinement guard scans providers/, tests/ and scripts/ by
substring, so any file under those roots that NAMES the live transport trips it,
including prose. AI-02's guard was NOT modified: the AI-09 files avoid naming it, and
the property is asserted by the Layer 0 allowlist, which excludes by omission. The cost
is recorded in the evidence document.

`integrations/` remains outside AI-02's guard roots, exactly as AI-09 contract §10.4
recorded; AI-09's own Layer 0 check closes it.
```

### What AI-09-A froze

```text
provider        mimo — the existing profile; NO third provider identity
reserved        providers/openai-compatible/ stays RESERVED / DISABLED / UNIMPLEMENTED
models          mimo/mimo-v2.6-pro, mimo/mimo-v2.6-flash — no default, no fallback,
                no derivation from AgentId, display_name or free-form string
enablement      runtime `providers.mimo.enabled == true` is REQUIRED, checked at construction
                from AI-02's ProviderConfig; profile existence != runtime enablement; a
                reserved provider is never enabled; the example config is a template.
                Enablement is ADDED, not substituted — it never replaces or relaxes
                Invoker's provider/model/capability checks, and `CodexBackend -> direct
                HttpTransport` is forbidden
protocol        openai_compatible_chat — no second protocol, no second adapter
invocation      providers.invocation.Invoker is the ONLY path; no second invocation API
backend         integrations/codex/ — a new core namespace layer; AI-09-B creates it
router          AI-07 unchanged; no execution coupling; `selected` is not auto-injected;
                `agent_hint` stays a hint
context         NO context egress, in TWO governed layers. Layer A (content) admits exactly
                one thing: `request.task` as one provider user message. Layer B admits the
                protocol's own structural control fields (`model`, messages envelope,
                `tools`, `response_format`, `stream`, generation controls, fixed headers).
                Neither layer admits workbench execution or context state
credential      env: only, via the existing resolver; no new scheme, no literal, ever
capability      UNKNOWN != AVAILABLE; no promotion, no bypass, no new probe. Three test
                layers (adapter / offline normalization / live observation) never merge, and
                an offline tool-call test goes at the adapter boundary — it never fabricates
                a VERIFIED model to get through the gate
tool calling    compatibility only (schema in, normalized call out); the probe never executes
                the returned call, triggers no AI-06 invocation, and has no continuation
                loop; NO model-driven tool loop
structured      json_object at minimum; `response_format` is a Layer B protocol field,
                never context; never equated with json_schema
timeout         always bounded; request deadline tightens, never widens
retry           max_retries = 0; attempts == 1; retry stays AI-13's
output          AgentResult unchanged; no raw output; NO durable model-output store.
                The reference is one form — `sha256:<64 lowercase hex>` over a canonical
                digest input (UTF-8; ensure_ascii=false; sort_keys=true;
                separators=(",", ":")) — and it locates no artifact
evidence        "AI-09 evidence record" means a `docs/AI-09_*` phase record, NOT an AI-05
                `plugins/evidence` EvidenceRecord; plugins/evidence/** is not modified
```

### Contract self-review

```text
touches the AI-08 frozen contract?     NO   AI-08 contract blob unchanged
touches the AI-07 frozen contract?     NO   AI-07 contract blob unchanged
touches the AI-02 frozen contract?     NO   AI-02 contract unchanged
changes Router semantics?              NO   §9 restates the boundary, alters nothing
changes the Context plugin?            NO   §12.5 forbids modifying AI-03
changes the credential grammar?        NO   §13 freezes env: only
changes the provider identity count?   NO   §5.2 forbids a third identity
openai-compatible reserved/disabled?   YES  §5.2 requires it stay reserved and disabled
creates a third provider?              NO   §5.2 forbids it explicitly
connects the Router?                   NO   §9 forbids it explicitly
sends context wholesale?               NO   §12.2 permits only `request.task`
turns UNKNOWN into AVAILABLE?          NO   §14 forbids it explicitly
adds retry?                            NO   §18 freezes max_retries = 0
adds a second invocation path?         NO   §8 names Invoker as the only path
adds a credential scheme?              NO   §13 freezes env: only
pulls tool execution into AI-09?       NO   §15.2 puts it out of scope
changes implementation code?           NO   no implementation path is touched
needs a new Layer 0 boundary?          YES  §10.4 requires check_ai09_integration_layer()
                                            in AI-09-B
```

### Recorded, not fixed

```text
RECORDED GAP   Router -> Provider execution coupling does not exist. `RouterDecision.selected`
               has no execution consumer. AI-09 does not close this gap; wiring routing into
               execution is a separate decision with its own contract (§9.1).

RECORDED GAP   AI-02's live-transport confinement guard ranges over the roots
               ("providers", "tests", "scripts") and therefore does not cover a new top-level
               package. AI-09-B closes this for `integrations/` through its own Layer 0 check.
               AI-02's guard is NOT modified (§10.4).

RECORDED LIM.  AI-08's three-member `AgentExecutionOutcome` is frozen. A failed invocation
               maps onto `FAILED`, so a provider ERROR and a pre-flight BLOCKED are not
               distinguished in `AgentResult`. The distinction survives on the
               `InvocationResult` (§19.4).
```

### What AI-09-A did not do

```text
no backend implemented
no `integrations/` directory created
no provider call made
no live test run
no AI-02, AI-03, AI-04, AI-05, AI-06, AI-07 or AI-08 contract or code modified
no credential read or printed
```

---

## AI-10 status

**AI-10 — Cross-Agent Review: COMPLETE / MERGED / CLOSED.**

```text
AI-10-A     = COMPLETE / MERGED    contract frozen          (PR #56, 3613896d)
Amendment 1 = APPLIED / MERGED     §9.3.1 statement identity (PR #58, fbf1e1b0)
Amendment 2 = APPLIED / MERGED     §5.4 independence_status  (PR #59, 32126416)
AI-10-B     = COMPLETE / MERGED    the review core          (PR #60, d22fe25c)
AI-10       = CLOSED

merge       = d22fe25c5fe94ae697083fd9fbdfaf3976785703
                     true two-parent merge; not squashed, not rebased
                     parent 1 = 32126416aa719ff204a5a690f868ff98122f1e22
                     parent 2 = 2468f85ebe15a8196a0b06e39a9900323d3fa356
base        = main @ 32126416aa719ff204a5a690f868ff98122f1e22
branch      = feature/ai-10-review-core-correction   (merged; retained)
contract    = docs/AI-10_CROSS_AGENT_REVIEW_EXECUTION_PLAN.md
contract blob = fc6f709611fcf7a8fcf6845097bf130920445fdc
                     UNCHANGED by AI-10-B
evidence    = docs/AI-10_EVIDENCE_2026-10-02.md
```

### What AI-10-B built

```text
review/                    a Workbench CORE layer — a namespace package, no __init__.py
                           12 modules: vocabulary, errors, digest, validation, claim,
                           material, finding, comparison, case, independence,
                           verification, decision
tests/review/              10 modules + conftest
Layer 0                    check_ai10_review_layer(), 19 checks in total
CI                         compileall now covers review/
```

```text
measured on the merged head
    tests/review            327 passed
    whole repository        2949 passed, 2 skipped, 5 deselected, 0 failed
                            (two consecutive runs)
    Layer 0                 PASS (19 checks)
    compileall              PASS
    providers.validate      PASS
    plugins.context.validate PASS
    required CI             run 36989026416 — Layer 0 SUCCESS, Layers 1-3 SUCCESS
                            run 37000268681 on the merge commit — SUCCESS
```

### What AI-10 does not claim

```text
live provider call        NOT_RUN — none has been made by this phase
live Agent execution      NOT_RUN
durable review evidence   AI-10 writes NO EvidenceRecord, under no producer token
durable HumanDecision     run data only
```

### Recorded, not resolved

```text
BLOCKED / PREREQUISITE
    automatic acquisition of real Agent analysis material. AI-08's AgentResult
    carries a reference or a digest and never content; AI-09 creates no durable
    model-output store and its reference locates no artifact. AI-10 v1 therefore
    accepts only explicitly supplied ReviewMaterial. Closing this needs an AI-09
    amendment and/or a separately reviewed DSH seam — neither was made.

DEFERRED
    durable review evidence, and a durable HumanDecision. Both require an AI-05
    amendment: the v1 §6.5 admitted-producer registry admits no AI-10 token, and
    AI-10 borrows none.

RECORDED — an AI-03 test, not AI-10's
    tests/context/test_cache.py::test_a_warm_cache_does_not_change_the_items is
    timing-sensitive: it compares item payloads across two build_context calls and
    `retrieved_at` is second-resolution and not stripped. Observed once in an
    earlier full-suite run, clean in 12/12 isolated runs and in later full runs.
    Recorded as RECORDED / PRE-EXISTING / OUT OF SCOPE. Not fixed here.

RECORDED — PR #57
    feature/ai-10-review-core remains OPEN / NOT MERGED / NOT MODIFIED / NOT
    REBASED / NOT FORCE-PUSHED. Its implementation content was carried onto the
    amended main as 00e8b02 on the correction branch that PR #60 merged, so the
    old branch is superseded. Closing it is a human housekeeping decision.
```
