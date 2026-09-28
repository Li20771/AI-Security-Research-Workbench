# AI-01 — DSH Baseline Checkpoint #5: Final Exit Review

> **Status: COMPLETE — CHECKPOINT #5 (exit review)**
> Experiment ID: `AI-01-DSH-20260928-005`
> Date: 2026-09-28
> Phase under review: **AI-01 — DSH Baseline**
> Predecessors: CP1 · CP2 · CP3 · CP4 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. What this checkpoint is

A **phase exit review**. It answers exactly one question:

> What is the true status of each AI-01 exit criterion today?

It is **not** implementation, **not** blocker resolution, **not** a DSH change, and **not** a
bridge into AI-02. No new capability was probed; this is an audit of evidence already recorded
in CP1–CP4 against the frozen plan.

**Standards were not lowered to close the phase.** Three criteria remain unmet and are
recorded `BLOCKED`; one is `NOT_RUN` by rule. Consequently `PROJECT_STATUS.md` is
**deliberately unchanged** (§7).

## 2. Baseline at review time

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp5` |
| Base SHA | `c4e92fce8adf9046aca27f3ca532153c16f11f80` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree | clean |
| DSH version | `0.1.7-rc.2` |
| DSH state | 5 processes, `24404, 29052, 29320, 38716, 43500`, started `2026-09-28 10:32:20`; `127.0.0.1:19387` |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| Merged AI-01 work | CP1 `042f4fd` · CP2 `d2e397a` · CP3 `df18e54` · CP4 `c4e92fc` |

## 3. Exit checklist — per `AI-01_DSH_BASELINE_EXECUTION_PLAN.md` §6

Statuses are restricted to `PASS` / `FAIL` / `BLOCKED` / `NOT_RUN` / `UNKNOWN`. No new status
is invented.

| # | Exit criterion (verbatim from §6) | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Exact tested DSH version recorded | **PASS** | CP1 §2 — three version layers; re-confirmed CP3 §3, CP4 §3 |
| 2 | Runtime dependency versions recorded | **PASS** | CP1 §3 — OS, Git, Python (×2), Node (×2), npm, Docker, bundled Node/pnpm |
| 3 | Clean installation/start procedure documented | **BLOCKED** | CP3 §7.2 — see §4 |
| 4 | Startup/restart behavior verified | **PASS** | CP1 §5.1, §5.4, §5.5 — start, graceful exit, restart, persistence |
| 5 | Known-good configuration recorded without secrets | **PASS** | CP1 §6 — profile, bundles, patch layer; credentials located but not read |
| 6 | Controlled workspace binding verified | **PASS** | CP1 §7.1/§7.2 A/B — registry binding + observed read |
| 7 | Required baseline Agent behavior verified | **PASS** | CP2 §4 — response, git inspection, workspace read, context retrieval |
| 8 | Required plugin/tool behavior verified | **BLOCKED** | CP4 §4.4, §5.2 — see §5 |
| 9 | Permission boundaries verified | **BLOCKED** | CP4 §6.1–§6.3 — see §6 |
| 10 | Evidence record completed | **PASS** | CP1–CP5, each with Experiment ID, evidence, statuses |
| 11 | Reproducible rollback point recorded | **PASS** | Rollback ref recorded in CP1 §10, CP3 §11, CP4 §10, and §9 below |
| 12 | Known limitations classified | **PASS** | CP1 §9.2 (8), CP3 §7.2, CP4 §9 (11–16) |
| 13 | PR reviewed and merged | **PASS** (CP1–CP4) | PRs #8, #9, #10, #11 all reviewed and merged |
| 14 | PROJECT_STATUS.md updated | **NOT_RUN** | Deliberately withheld — §7 |

Summary: **10 PASS · 0 FAIL · 3 BLOCKED · 1 NOT_RUN · 0 UNKNOWN** (14 criteria).

No criterion is marked `FAIL`: nothing was executed and found not to work at the criterion
level. The unmet criteria are unmet because the required evidence **cannot be obtained
within the current safety boundary** — which is `BLOCKED`, not `FAIL`.

## 4. Criterion 3 — Clean installation/start procedure

### 4.1 What is established

| Fact | Source |
| --- | --- |
| Artifact A exists: `deepseek-harness-0.1.7-rc.2-win-x64.exe`, 288 245 480 bytes | CP3 §3 |
| Artifact A SHA-256 `0CF065DC…3CEB86`; publisher SHA-512 record **matches** local recomputation | CP3 §5.1 |
| Artifact A Authenticode **Valid** (EV, Hangzhou DeepSeek AI Co., Ltd., timestamped) | CP3 §5.2 |
| Install method observed: per-user, no admin, install root, `HKCU` uninstall entry, shortcut targets | CP3 §6 |
| Startup method verified by execution | CP1 §5.1, §5.5 |
| `/api/plugins`-adjacent runtime surface reachable | CP4 §6.1 |

### 4.2 What is NOT established

| Missing | Consequence |
| --- | --- |
| Artifact B (DSH Desktop plugin `2.0.5`) has **no integrity anchor** — `NotSigned`, no publisher hash | the artifact set cannot be fully authenticated |
| Both artifacts live in **`electron-updater` cache directories**, not a controlled archive | *available now* ≠ *durably available* |
| The feed is a **`nightly` channel**; upstream re-fetch was not tested | the exact build may not be re-obtainable |
| Whether a clean first run requires **network access** (profile bundles) was not determined | offline reconstruction is unproven |
| **No clean installation has ever been executed** | no recorded install commands exist |
| **No disposable / clean Windows environment** is available or permitted | the rehearsal cannot be staged |

### 4.3 Judgment

> **`BLOCKED` — the criterion is NOT met, and is not recorded as `PASS`.**

The plan requires more than a description of an install. §2.2 states: *"Establish a clean,
repeatable procedure for: installation, dependency setup, startup, shutdown, restart after
environment reboot, configuration persistence. **Every command used for the baseline must be
recorded.**"* §2.1 adds: *"Do not document a version as supported until it has been tested."*
The roadmap's own exit condition for AI-01 is *"能从干净环境复现 DSH 基线"* — reproducible
**from a clean environment**.

None of those is satisfied by observing an installer that is already present. What exists is
a **well-evidenced artifact plus an observed install method** — which is exactly what CP3
recorded as *"usable installation material exists and a precise reinstall plan can be built
on it."* That is strictly less than a verified clean installation, and it is not upgraded here.

### 4.4 Unblock condition

All four steps are required; the criterion moves to `PASS` only after step 3 has actually run:

```text
1. Provide a disposable / clean Windows environment
   that does NOT affect the current DSH installation.

2. First copy the verified artifact out of the volatile updater cache into a
   controlled archive, then use it:
       pending\deepseek-harness-0.1.7-rc.2-win-x64.exe
       size 288245480
       sha256 0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86
   (Artifact B, the 2.0.5 plugin installer, still needs an integrity anchor
    before the plugin half of the baseline can be called reproducible.)

3. Perform the clean install -> start -> workspace / basic validation,
   recording every command and its actual result.

4. Confirm / deny the network dependency at first run (§4.2).
```

This checkpoint **did not** create a VM, Windows Sandbox, or user account, and did not modify
system configuration — creating any of those is outside AI-01's boundary.

## 5. Criterion 8 — Required plugin/tool behavior verified

The plan §2.5 requires, per capability, *actual* evidence: `Agent starts`, `Workspace access`,
`Git inspection`, `Tool invocation`, `Plugin loading`, `Permission boundary`, `Context
loading`, `Recovery`.

| Required capability | Status | Evidence |
| --- | --- | --- |
| Agent starts | **PASS** | CP2 §4.1 (operator GUI) |
| Workspace access | **PASS** | CP2 §4.3 |
| Git inspection | **PASS** | CP2 §4.2 |
| Tool invocation | **PASS** | CP2 §4.2/§4.3 — real command and file-read results, cross-checked outside DSH |
| Context loading | **PASS** | CP2 §4.4 (scoped: DSH-native, not a Workbench Context plugin) |
| Recovery | **PASS** | CP1 §5.4/§5.5 |
| **Plugin loading** | **NOT VERIFIED for the current build** | CP4 §4.4 |

### 5.1 Judgment

> **`BLOCKED` — the criterion is not met. Tool behaviour is verified; plugin behaviour is not.**

The criterion is a single line covering both. Tool behaviour has genuine execution evidence
(CP2, human-executed). Plugin behaviour does not: the only runtime plugin evidence on this
machine is **stale** (CP4 §4.2/§4.3 — `2026-09-15`, describing `0.1.2-rc.1`), and the
current build **writes no plugin telemetry at all** (CP4 §4.4). CP4 records current-build
plugin attribution as `UNKNOWN` precisely because the available signals prove the app is
running but do not attribute the surface to a loaded plugin.

Per CP4 §4/§5.2, the available routes to plugin evidence are all closed under the current
boundary: `/api/plugins` is token-gated (`401`), the CLI is `NOT_RUN` because invoking it
risks printing a session token, and no current-run telemetry is produced.

**No Context / Guard / Evidence / Security Tools plugin was implemented to fill this gap**,
and none should be: those are AI-03–AI-06. Implementing them would not produce evidence about
*DSH's* plugin loading either.

### 5.2 Unblock condition

Any **one** of:

```text
(a) A human opens the DSH GUI 插件 (Plugins) panel and reports the loaded plugin
    list — token-free, GUI, on the same basis as the CP2 verification; or

(b) Explicit authorization to invoke a specific, provably token-free
    desktop-cli.js subcommand; or

(c) A DSH build that emits current-run plugin telemetry.
```

## 6. Criterion 9 — Permission boundaries verified

The plan §2.5 requires for `Permission boundary`: **"allowed + blocked cases"**.

| Element | Status | Evidence |
| --- | --- | --- |
| DSH-native **network** boundary — blocked cases | **PASS** | CP4 §6.1 — `401` on 5 paths; off-loopback unreachable; loopback-only binding |
| DSH-native **network** boundary — **allowed** case | **NOT RUN** | requires a session token — forbidden |
| Filesystem / workspace enforcement | **UNKNOWN** | CP4 §6.2 — no such configuration exists; mechanism presence unproven |
| Filesystem blocked-case | **NOT_RUN** | CP4 §6.3 — no safe construction without a DSH config change |
| Workbench Guard | **NOT_IMPLEMENTED** | CP4 §6.4 — placeholder README only |

### 6.1 Judgment

> **`BLOCKED` — the criterion is not met.** The required evidence is *"allowed + blocked
> cases"*. Blocked cases exist (five, executed). An **allowed** case does not exist, because
> demonstrating one requires the session token, which is forbidden.

The distinction the checkpoint demanded is preserved explicitly and must not be collapsed:

```text
DSH-native network exposure boundary   ->  PASS (blocked cases, executed)
Workbench Guard                        ->  NOT_IMPLEMENTED (a Workbench statement)
```

> **"Guard is not implemented" is NOT recorded anywhere as a DSH `FAIL`.** Guard is AI-04 and
> is out of AI-01 scope (plan §7). Its absence says nothing about DSH's native boundary, which
> CP4 verified positively. The two are separate rows precisely so they cannot be conflated.

### 6.2 Unblock condition

Either:

```text
(a) Explicit authorization for a token-free demonstration of the ALLOWED path
    (i.e. an authorized way to show an authenticated request succeeding), or

(b) Explicit authorization to register a disposable scratch workspace in DSH,
    enabling a filesystem blocked-case (write denial) that does not touch
    SecurityLab, system directories, credentials, or remote resources.
```

Until then, the criterion stays `BLOCKED` and the filesystem boundary stays `UNKNOWN`. It is
**not** recorded `FAIL`: no probe failed — the probes were never safely constructible.

## 7. Criterion 14 — PROJECT_STATUS.md updated

`PROJECT_STATUS.md` is **deliberately unchanged**. The instruction governing this checkpoint
permits updating the AI-01 completion state *only* when the phase judgment is `COMPLETE`.
The judgment is not `COMPLETE` (§8), so the file was not touched.

Status `NOT_RUN` — intentionally withheld, not failed. This criterion is contingent on the
phase reaching `COMPLETE` and cannot be satisfied before then.

## 8. Final phase judgment

```text
AI-01 = BLOCKED
```

### 8.1 Why not COMPLETE

Three applicable exit criteria are unmet (§3, #3 / #8 / #9), and one is `NOT_RUN` by rule
(#14). "All applicable exit criteria satisfied" is false.

### 8.2 Why BLOCKED rather than IN PROGRESS

The distinguishing test is whether **real work remains that is completable inside the current
safety boundary**. It is not:

| Unmet criterion | What blocks it | Inside the boundary? |
| --- | --- | --- |
| #3 Clean installation | needs a disposable/clean Windows environment; creating one is forbidden | **No** |
| #8 Plugin behavior | needs a token-free enumeration path or a human GUI action; telemetry absent | **No** |
| #9 Permission boundaries | needs the token (allowed case) or a DSH config change (filesystem case) | **No** |

Every remaining item depends on an **external environment or action outside the current
boundary** — a disposable environment, an authorization, or a human GUI observation. None can
be advanced by further work under the present constraints. That is the definition of
`BLOCKED`.

### 8.3 Why not a lowered standard

The phase is one step from complete on paper, which is precisely when standards slip. It was
not permitted to. Specifically, this review **rejected** three softenings that were available:

1. treating the CP3 artifact evidence as satisfying "clean installation";
2. treating the CP4 network blocked-cases as satisfying "allowed + blocked";
3. letting the CP2 human-verified tool results cover the plugin half of criterion #8.

Each would have produced a green checklist and a false exit. None was taken.

## 9. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `c4e92fce8adf9046aca27f3ca532153c16f11f80` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard c4e92fce8adf9046aca27f3ca532153c16f11f80` |
| Side effects on DSH | **None** — no DSH state modified |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 10. Boundary integrity

| Invariant | Result |
| --- | --- |
| SecurityLab working tree unchanged | **PASS** — `git status --short` empty (0 files) |
| SecurityLab HEAD unchanged | **PASS** — `efa836ff9225f6226ca8a76615f3f45c31110d58` = expected |
| SecurityLab reflog shows no new entries | **PASS** — last entry pre-existing |
| Workbench `main` unmodified | **PASS** — review performed on a branch |
| `PROJECT_STATUS.md` unmodified | **PASS** — deliberately not touched (§7) |
| No DSH modification | **PASS** — no install, uninstall, download, config change or process action |
| No VM / Sandbox / user account / system config created | **PASS** |
| No credential or token access | **PASS** — `~/.dsh/.credentials.yaml` not opened |
| No plugin / Guard / tool adapter implemented | **PASS** |
| No AI-02+ work started | **PASS** |

## 11. Known limitations (consolidated)

Inherited: GUI-only operation; nightly channel; three-layer versioning; read-only workspace
access unenforced; Python `3.14.4`/`3.14.5` shell ambiguity; system Node vs bundled Node; no
durable startup log; window-close is not Quit; DSH telemetry is stale and describes a
different build; generated command shims bake in absolute install paths and go stale; the CLI
cannot be validated without touching the token surface; the filesystem permission boundary
cannot be tested safely; no permission/guard/policy configuration exists in DSH;
plugin-runtime attribution for the current build is unverified.

Added at review:

17. **AI-01 cannot be closed within the current safety boundary.** Three exit criteria require
    an external environment, an authorization, or a human GUI observation. This is a boundary
    property, not a defect in the baseline work.
18. **The baseline is pinned to a moving target.** `0.1.7-rc.2` is a `nightly` build. Every
    statement in CP1–CP5 is true of that build at that time and must be re-verified if DSH
    auto-updates.

## 12. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | recorded in §13 |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_5.md` |

## 13. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-005` |
| Checkpoint | #5 — Final Exit Review |
| Branch | `baseline/ai-01-dsh-20260928-cp5` |
| Base SHA | `c4e92fce8adf9046aca27f3ca532153c16f11f80` |
| Exit checklist | **10 PASS · 0 FAIL · 3 BLOCKED · 1 NOT_RUN · 0 UNKNOWN** |
| **AI-01 final judgment** | **BLOCKED** |
| `PROJECT_STATUS.md` | **unchanged** (permitted only on `COMPLETE`) |
| AI-02 | **NOT STARTED** — must not begin until AI-01 exits |
| Checkpoint #5 | **COMPLETE** |

The AI-01 baseline itself is in good shape: DSH `0.1.7-rc.2` is installed, running,
configured, workspace-bound and behaviourally characterized, with an evidence record and a
rollback point. What is missing is **verification that cannot be performed from inside the
current boundary** — not baseline work left undone.
