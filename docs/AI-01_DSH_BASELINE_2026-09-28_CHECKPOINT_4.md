# AI-01 — DSH Baseline Checkpoint #4

> **Status: COMPLETE — CHECKPOINT #4**
> Experiment ID: `AI-01-DSH-20260928-004`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: [CP1](AI-01_DSH_BASELINE_2026-09-28.md) · [CP2](AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_2.md) · [CP3](AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_3.md) (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

**This document does not mark AI-01 complete.** Predecessors are preserved unchanged; this
file is additive. `PROJECT_STATUS.md` and `MASTER_ROADMAP.md` are intentionally unchanged.

## 1. Objective

Characterize DSH's **native** capability and security boundary — what DSH actually has today,
what it does not have, and what cannot be safely verified:

- **A.** Plugin behaviour — how DSH loads/registers plugins, and what runtime evidence exists
- **B.** Tool behaviour — which tools have direct execution evidence
- **C.** Permission boundary — whether DSH natively enforces anything verifiable
- **D.** Boundary integrity — SecurityLab / Workbench / remote-state invariants

This checkpoint implements **nothing**. It is characterization only.

## 2. Method and evidence standard

Read-only observation plus safe, non-destructive probes. No install, no uninstall, no
download, no DSH configuration change, no DSH process action, no credential access, no
session token, no GUI automation, no writes to SecurityLab.

Every `PASS` below has direct execution evidence. Evidence is labelled:

| Label | Meaning |
| --- | --- |
| **current-run** | produced by the instance now running (started `2026-09-28 10:32:20`) |
| **stale-artifact** | produced by DSH on `2026-09-15` and describing a different build — see §3 |
| **config-level** | read from configuration/structure, not observed executing |
| **carried-CP2** | human-executed in Checkpoint #2, not reproduced here |

> **A note on stale artifacts.** Most of DSH's own runtime telemetry on this machine is dated
> `2026-09-15` and describes `dshVersion 0.1.2-rc.1` on the `stable` channel, installed at
> `C:\Users\20771\DSHdesktop\DSH Desktop\`. The current install is `0.1.7-rc.2` on `nightly`
> at `%LOCALAPPDATA%\Programs\DeepSeek Harness\`. Neither the `2026-09-26` nor the
> `2026-09-28` startup wrote new lifecycle telemetry (§4.4). Stale artifacts are therefore
> used **only** as evidence of DSH's *mechanism*, never as evidence of the *current build's*
> behaviour. This distinction is applied throughout.

## 3. Environment

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp4` |
| Base SHA | `df18e54f0d7b52567c8995c26abe8974f82344da` |
| HEAD at start | `df18e54f0d7b52567c8995c26abe8974f82344da` (= `origin/main`, `0 0`) |
| Working tree at start | clean |
| DSH version | `0.1.7-rc.2` (FileVersion), `0.1.7.0` (ProductVersion) |
| DSH Desktop plugin | `2.0.5` |
| Electron runtime | `44.0.0` |
| Bundled Node / pnpm | `24.18.1` / `11.7.0` |
| DSH processes | 5 — `24404, 29052, 29320, 38716, 43500`, started `2026-09-28 10:32:20` |
| DSH listening endpoint | `127.0.0.1:19387` (loopback only) |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |

## 4. A — Plugin behaviour

### 4.1 Plugin loading mechanism (config-level + stale runtime evidence)

DSH composes a **Cordis profile**. `~/.dsh/profiles/desktop/package.json` declares three
bundles; `cordis.yml` is an empty root entry list and the tree is composed as layered patches:

```json
{ "name": "dsh-profile-desktop", "private": true, "dependencies": {},
  "dsh": { "profile": {
    "bundles": ["@deepseek-ai/dsh-base",
                "@deepseek-ai/dsh-web-app",
                "@deepseek-ai/dsh-experimental-agent-team-profile"],
    "patchReload": "live" } } }
```

Layering order (documented in `cordis.yml` itself): bundle layers → `cordis.patch.yml` →
`--patch` overlays. The operator patch layer contains **five UI entries only**
(`ui-settings-general`, `ui-theme`, `ui-chat`, `ui-settings`, `ui-settings-account`) — no
provider, permission or tool configuration.

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| Read active profile selection | a named active profile | `profile-selection/state.json` → `{"version":2,"active":"desktop"}` | **PASS** (config-level) |
| Read profile identity | a stable profile hash | `profileHash 165bfa9a95eac2d903fd4958f27f83aaa7c31e19ebede52d3f920fcb95ca7ed3` | **PASS** (config-level) |
| Determine plugin discovery source | a market/registry source | `desktop-market/state.json` → `{"version":1,"requested":"community-market"}`; `profile-preferences` → `"market":"community-market"` | **PASS** (config-level) |
| Enumerate declared plugin bundles | bundle list | 3 bundles (§4.1) | **PASS** (config-level) |

### 4.2 Runtime evidence of the plugin lifecycle (stale-artifact)

`lifecycle-events/startup.jsonl` records DSH's own startup pipeline. Parsed in full:

```text
startup.run.started
  stage electron-ready        -> completed
  stage shell-environment     -> completed
  stage runtime-bootstrap     -> completed
  stage profile-selection     -> completed
  stage profile-composition   -> completed   (79116 ms)
  stage runtime-bootstrap     -> completed
  stage host-boot             -> completed
  stage renderer-startup      -> started
      renderer.boot.started
      renderer.boot.completed   {"rendererStatus":"healthy"}
  stage renderer-startup      -> completed
  stage health-commit         -> completed
startup.run.completed         {"finalStage":"health-commit","rendererStatus":"healthy"}
```

**This is DSH's plugin/profile composition pipeline observed executing**: profile-selection →
profile-composition → runtime-bootstrap → host-boot. It is direct runtime evidence of the
loading mechanism — **but from `2026-09-15`, describing `0.1.2-rc.1`.**

### 4.3 Plugin runtime actually loaded (stale-artifact)

`logs/dsh-2026-09-15.log` contains DSH's own banner lines:

```text
--- dsh-plugin-desktop DSH Desktop 2.0.5 win32 node v24.18.1 run 1789441511064 ---
--- dsh-plugin-desktop DSH Desktop 2.0.5 win32 node v24.18.1 run 1789455212493 ---
```

This is runtime evidence that `dsh-plugin-desktop 2.0.5` loaded and ran. **Stale-artifact.**

A **health snapshot** was also committed (`health-snapshots/…/slot-1/manifest.json`) with
`"reason":"healthy-startup"`, recording `appVersion 2.0.5`, `desktopPackageName
dsh-plugin-desktop`, and SHA-256 for `package.json`, `pnpm-workspace.yaml`,
`cordis.patch.yml`, `home/settings.yaml` — DSH's own integrity mechanism for the profile.
**Stale-artifact.**

### 4.4 Current-run plugin runtime evidence — and a gap

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| New lifecycle telemetry written by the `09-26` or `09-28` startups | new entries | **none** — `logs/` and `lifecycle-events/` still dated `2026-09-15` | **FAIL** (no current-run telemetry is produced) |
| Plugin runtime active in the current run | working plugin-provided surface | loopback `127.0.0.1:19387` serving; UI rendered; a full agent turn completed (CP2, human-executed) | **PASS** (indirect, current-run) |

The runtime is demonstrably live, but **DSH 0.1.7-rc.2 writes no current-run plugin telemetry
to these paths.** Plugin-runtime evidence for the current build is therefore indirect only.

### 4.5 Generated host/runtime command shims — present but STALE

DSH generates command shims for its tool environment. Both generations exist and both are
**broken**, because they bake in absolute paths to an install root that no longer exists:

`host-commands/desktop/generations/<hash>/bin/dsh.cmd`:

```bat
set "ELECTRON_RUN_AS_NODE=1"
set "DSH_DESKTOP_DEFAULT_PROFILE=desktop"
set "DSH_HOME=C:\Users\20771\.dsh"
"C:\Users\20771\DSHdesktop\DSH Desktop\DSH Desktop.exe" --expose-internals
  "C:\Users\20771\DSHdesktop\DSH Desktop\resources\app.asar\lib\desktop-cli.js" %*
```

`runtime-commands/generations/<hash>/bin/pnpm.cmd` and `private/node-bin/node.cmd` reference
the same dead root, and additionally pin `npm_config_target=43.3.0` (Electron **43.3.0**)
against the current Electron **44.0.0**.

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| Generated shims are usable | shim paths exist | `C:\Users\20771\DSHdesktop` → **does not exist** | **FAIL** (stale, non-functional) |
| `dsh` resolvable from host PATH | resolvable | `where dsh` → not found | **FAIL** (not on PATH) |

### 4.6 What is NOT plugin evidence

`plugins/context`, `plugins/guard`, `plugins/evidence`, `plugins/security-tools` in this
repository contain **exactly one file each — a placeholder `README.md`** reading
"Reserved for the … layer of the AI Security Research Workbench."

> **These directories are scaffolding. They are not plugin implementations, they are not
> loaded by DSH, and their existence must not be read as any Workbench capability having
> been implemented.** The four Workbench plugin layers remain unimplemented (AI-03 … AI-06).

### 4.7 Plugin section summary

| Question | Answer |
| --- | --- |
| How does DSH load/register plugins? | Cordis profile composition: bundles → `cordis.patch.yml` → overlays, `patchReload: live`; market source `community-market` |
| Is plugin loading observed at runtime? | **Yes — but only via `2026-09-15` stale artifacts** describing `0.1.2-rc.1` |
| Is a plugin loaded in the current run? | **Yes, indirectly** (UI renders, agent completes turns) — no direct telemetry |
| Can individual plugin capabilities be enumerated? | **UNKNOWN** — bundle internals (`app.asar`) were not inspected |
| Are the Workbench plugin layers implemented? | **No** — placeholder READMEs only |

## 5. B — Tool behaviour

### 5.1 Agent-invoked tools (carried-CP2, human-executed)

These are the only tool behaviours with agent-level execution evidence, and they were
performed by the human operator in the GUI, not by any agent-invocable surface:

| Test | Evidence | Status |
| --- | --- | --- |
| Workspace read | read `README.md`, returned its real first paragraph | **PASS** (carried-CP2) |
| Git inspection | `git rev-parse HEAD` → `efa836ff9225f6226ca8a76615f3f45c31110d58` (matches) | **PASS** (carried-CP2) |
| Context retrieval | retrieved project directions from README / AGENTS.md | **PASS** (carried-CP2) |

Not re-executed here; carried forward as recorded in Checkpoint #2 §4.

### 5.2 Independent tool invocation mechanism

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| Does DSH have a CLI? | a CLI entry point | **Yes, structurally**: `resources/app.asar/lib/desktop-cli.js`, invoked by the generated `dsh.cmd` with `ELECTRON_RUN_AS_NODE=1`, `DSH_HOME`, `DSH_DESKTOP_DEFAULT_PROFILE` | **PASS** (structural) |
| Is that CLI reachable today? | invocable | **No** — not on PATH; the only generated shim points at a nonexistent install root (§4.5) | **FAIL** |
| Is the CLI functional if invoked directly? | — | **NOT_RUN** — see below | **NOT_RUN** |
| Is there a terminal/shell tool? | shim evidence | shims for bundled `node`/`pnpm` are generated (`clear-env.cjs`, `node.cmd`, `pnpm.cmd`) → a shell tool environment exists structurally | **PASS** (structural) |
| Does that shell tool work in the current run? | — | **UNKNOWN** — the generated shims are stale (§4.5); no current-run shell invocation was observed | **UNKNOWN** |

> **Why the CLI was deliberately not exercised.**
> The CLI is the component that performs DSH web authentication — its documented subcommand
> `dsh web` prints the session URL *containing the session token* (that string is what the
> `401` body refers to: "reopen the URL printed by `dsh web`"). Exercising the CLI therefore
> risks printing or minting a session token, which this checkpoint explicitly forbids.
> The prohibition was respected by **not invoking it**, rather than by invoking it carefully.
> A future checkpoint may exercise a specific, provably token-free subcommand under explicit
> authorization.

### 5.3 Tool section summary

| Question | Answer |
| --- | --- |
| Which tool behaviours have direct execution evidence? | Workspace read, Git inspection, context retrieval — **all human-executed in CP2**; no agent-invocable execution path exists |
| Does an independent tool invocation mechanism exist? | Structurally yes (`desktop-cli.js` + generated shims); **functionally unreachable** today |
| Is there a shell/terminal capability? | Structurally yes (shim generation); current-run functionality **UNKNOWN** |

## 6. C — Permission boundary

Per the checkpoint rule, this is split into four **separate** questions. "No Guard plugin"
is **not** automatically a DSH permission failure.

### 6.1 Does a DSH-native boundary exist?

| Test | Command | Expected | Actual | Status |
| --- | --- | --- | --- | --- |
| Unauthenticated loopback access | `curl http://127.0.0.1:19387/` | denied | `HTTP 401` | **PASS** (blocked as expected) |
| Unauthenticated API paths | `curl` on `/api/health`, `/api/plugins`, `/api/workspace`, `/api/sessions` | denied | `HTTP 401` on **all five** paths | **PASS** (blocked as expected) |
| Boundary response body | `curl http://127.0.0.1:19387/` | an auth challenge | `dsh web authentication required; reopen the URL printed by dsh web.` | **PASS** |
| Off-loopback reachability | `curl http://172.24.208.1:19387/` | unreachable | connection failed (`000`) | **PASS** (blocked as expected) |
| Listening scope | `Get-NetTCPConnection -State Listen` filtered to DSH PIDs | loopback only | `127.0.0.1:19387` — **no non-loopback binding** | **PASS** |

> **A native boundary IS present and IS enforced — for network exposure.** Five executed
> denied-cases, consistent across paths, plus proof that the endpoint does not bind off
> loopback. This is the one DSH-native enforcement mechanism verified in this checkpoint.

### 6.2 Does the current configuration actually enforce anything else?

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| Permission/guard/policy configuration present in the active profile | some policy config | **none** — `cordis.yml`, `cordis.patch.yml`, `package.json`, `pnpm-workspace.yaml` contain no permission/guard/sandbox/allow/deny/policy keys | **FAIL** (no such configuration exists) |
| Permission configuration present in DSH settings | some policy config | **none** in `settings.yaml` / `settings.yaml.imported` | **FAIL** (no such configuration exists) |
| Filesystem / workspace permission enforcement | observable enforcement | **none observed** | **UNKNOWN** |

> The only configured security-relevant setting is `networkExposure: loopback` — which §6.1
> confirms is genuinely enforced. **No filesystem, workspace, tool or command permission
> layer is configured at all.** The absence of a *configuration* is not proof of the absence
> of a *mechanism*; the mechanism could exist without configuration. Hence **UNKNOWN**, not
> FAIL, for filesystem enforcement.

### 6.3 Is a blocked-case actually verified?

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| Blocked-case: unauthenticated network access | denied | denied (401 ×5) | **PASS** (executed) |
| Blocked-case: off-host network access | denied | denied (unreachable) | **PASS** (executed) |
| Blocked-case: filesystem / workspace write denial | denied | **not attempted** | **NOT_RUN** |

> **Why the filesystem blocked-case is `NOT_RUN` and not a fabricated result.**
> Constructing it requires a disposable scratch workspace, which requires **registering a new
> workspace in DSH configuration** — explicitly forbidden here. Attempting it against
> SecurityLab is forbidden. There is no safe way to build this case in this checkpoint, so it
> is recorded `NOT_RUN` rather than invented as `PASS` or `FAIL`.

### 6.4 Is the Workbench Guard implemented?

| Test | Expected | Actual | Status |
| --- | --- | --- | --- |
| Guard implementation exists | plugin code | `plugins/guard/` contains **one placeholder README** | **NOT_IMPLEMENTED** |

This is a statement about the **Workbench**, not about DSH, and is recorded separately so it
cannot be confused with a DSH permission failure.

### 6.5 Permission boundary summary

| Question | Answer |
| --- | --- |
| DSH native boundary exists? | **Yes — for network exposure only**, verified by executed denied-cases |
| Current config enforced? | Only `networkExposure: loopback`; **no** permission/guard/policy configuration exists anywhere |
| Blocked-case verified? | **Yes for network** (5 × 401 + off-loopback unreachable); **NOT_RUN** for filesystem |
| Workbench Guard implemented? | **No** — placeholder README only |

## 7. D — Boundary integrity

| Invariant | Verification | Result |
| --- | --- | --- |
| SecurityLab working tree unchanged | `git status --short` → empty (0 files) | **PASS** |
| SecurityLab HEAD unchanged | `efa836ff9225f6226ca8a76615f3f45c31110d58` = expected | **PASS** |
| SecurityLab reflog shows no new entries | last entry `efa836f HEAD@{0}: merge …: Fast-forward` (pre-existing) | **PASS** |
| Workbench `main` unchanged | `main` untouched; work done on `baseline/ai-01-dsh-20260928-cp4` | **PASS** |
| No remote write | no `push --force`, no remote change; remote URL unchanged | **PASS** |
| No destructive operation | no delete, no uninstall, no reinstall, no force-kill | **PASS** |
| No credential access | `~/.dsh/.credentials.yaml` **not opened** | **PASS** |
| No session token obtained | CLI not invoked (§5.2); no token printed, copied or used | **PASS** |
| No DSH configuration change | profile/settings files not written | **PASS** |
| No persisted config change | no git config, proxy or network setting written | **PASS** |

## 8. Consolidated status

| # | Item | Status |
| --- | --- | --- |
| 1 | Plugin loading mechanism identified (Cordis profile + market) | **PASS** (config-level) |
| 2 | Plugin composition pipeline observed executing | **PASS** (stale-artifact) |
| 3 | `dsh-plugin-desktop` loaded and ran | **PASS** (stale-artifact) |
| 4 | Plugin runtime active in the current run | **PASS** (indirect, current-run) |
| 5 | Current-run plugin telemetry produced | **FAIL** — none written |
| 6 | Individual plugin capabilities enumerable | **UNKNOWN** |
| 7 | Generated host/runtime shims usable | **FAIL** — stale, dead paths |
| 8 | Workspace read via agent | **PASS** (carried-CP2, human-executed) |
| 9 | Git inspection via agent | **PASS** (carried-CP2, human-executed) |
| 10 | Context retrieval via agent | **PASS** (carried-CP2, human-executed) |
| 11 | Independent tool invocation mechanism exists (structural) | **PASS** |
| 12 | Independent tool invocation mechanism reachable | **FAIL** — not on PATH, shim broken |
| 13 | CLI functionally exercised | **NOT_RUN** — token-adjacent, forbidden |
| 14 | Shell/terminal tool functional in current run | **UNKNOWN** |
| 15 | DSH-native network boundary enforced | **PASS** — executed denied-cases |
| 16 | Other permission configuration present | **FAIL** — none exists |
| 17 | Filesystem/workspace enforcement | **UNKNOWN** |
| 18 | Filesystem blocked-case verified | **NOT_RUN** — no safe construction |
| 19 | Workbench Guard implemented | **NOT_IMPLEMENTED** (Workbench, not DSH) |
| 20 | SecurityLab / Workbench / remote invariants | **PASS** — all ten (§7) |

Tally: **11 PASS, 4 FAIL, 0 BLOCKED, 2 NOT_RUN, 3 UNKNOWN** (20 items).

A `FAIL` here means "executed, and the observed behaviour is not what the baseline needs" —
e.g. shims that are stale, or the absence of any permission configuration. It does not mean
DSH is broken; §4.4/§4.5/§6.2 explain each.

## 9. Known limitations

Inherited from Checkpoint #1 §9.2 and still open: GUI-only operation; nightly channel;
three-layer versioning; read-only workspace access unenforced; Python interpreter ambiguity;
system Node vs bundled Node; no durable startup log; window-close is not Quit.

New in this checkpoint:

11. **DSH's own telemetry is stale and describes a different build.** Every lifecycle artifact
    on this machine is from `2026-09-15` and describes `0.1.2-rc.1` / `stable` at a since-moved
    install root. **Any future checkpoint must not treat these files as current-run evidence.**
12. **Generated command shims carry absolute install paths and go stale on reinstall/move.**
    `dsh`, `node` and `pnpm` shims all point at `C:\Users\20771\DSHdesktop\…`, which does not
    exist. This is a concrete, reproducible instability in DSH's tool environment.
13. **The CLI cannot be validated without touching the token surface.** Any functional test
    of `desktop-cli.js` is currently blocked by the standing token prohibition.
14. **The filesystem permission boundary cannot be tested safely** without registering a
    disposable workspace, which requires a DSH configuration change.
15. **No permission/guard/policy configuration exists in DSH.** Whatever enforcement DSH may
    have internally, none of it is configured. Nothing here should be read as a Workbench
    Guard being present or as DSH having a permissions layer ready to use.

## 10. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `df18e54f0d7b52567c8995c26abe8974f82344da` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard df18e54f0d7b52567c8995c26abe8974f82344da` |
| Side effects on DSH | **None** — no DSH state written |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 11. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git rev-parse HEAD` | recorded in §12 |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_4.md` |

## 12. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-004` |
| Checkpoint | #4 |
| Branch | `baseline/ai-01-dsh-20260928-cp4` |
| Base SHA | `df18e54f0d7b52567c8995c26abe8974f82344da` |
| DSH version | `0.1.7-rc.2` |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| **AI-01** | **IN PROGRESS — not complete** |
| **Checkpoint #4** | **COMPLETE** |
| **Checkpoint #4 overall status** | **PARTIAL** — 11 PASS, 4 FAIL, 0 BLOCKED, 2 NOT_RUN, 3 UNKNOWN |

Not implemented in this checkpoint (per AI-01 §7 and the stated boundary): Context plugin,
Guard plugin, Evidence plugin, Security Tools plugin, Model Router, DeepSeek/MiMo provider
integration, Codex integration, Benchmark, workflows, and any AI-02+ work.
