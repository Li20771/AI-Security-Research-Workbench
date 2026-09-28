# AI-01 — DSH Baseline Checkpoint #1

> **Status: PARTIAL — CHECKPOINT #1 of N**
> Experiment ID: `AI-01-DSH-20260928-001`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

**This document does not mark AI-01 complete.** It records the first verified checkpoint.
`docs/PROJECT_STATUS.md` is intentionally unchanged. See [§9 AI-01 exit criteria status](#9-ai-01-exit-criteria-status).

## 1. Git baseline

| Item | Value |
| --- | --- |
| Working branch | `baseline/ai-01-dsh-20260928` |
| Base SHA | `f7883681ab7219314f6a4ad2fb6abd2b45595e4d` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree at start | clean |
| Old branch `baseline/ai-01-dsh-20260927` | Left **untouched** at `f788368` — not rebased, not overwritten |

The previous AI-01 branch was already based on current `main`, not on the stale `0b25a61`.
A **new** task branch was created from the true base rather than reusing or rewriting history.

```text
git fetch origin --prune
git rev-parse origin/main                                  # f7883681ab7219314f6a4ad2fb6abd2b45595e4d
git checkout -b baseline/ai-01-dsh-20260928 f7883681ab7219314f6a4ad2fb6abd2b45595e4d
```

## 2. DSH version — measured, not assumed

DSH Desktop is **not** a single version number. Three distinct versions were measured:

| Layer | Version | Evidence source |
| --- | --- | --- |
| DSH shell (Electron app) | `0.1.7-rc.2` (FileVersion) / `0.1.7.0` (ProductVersion) | `(Get-Item <exe>).VersionInfo` |
| `dsh-plugin-desktop` | `2.0.5` | `logs/dsh-2026-09-15.log` banner |
| Electron runtime | `44.0.0` | `resources/version` |
| Bundled Node | `24.18.1` | `resources/runtime/versions.json` |
| Bundled pnpm | `11.7.0` | `resources/runtime/versions.json` |

Executable:

```text
C:\Users\20771\AppData\Local\Programs\DeepSeek Harness\DeepSeek Harness.exe
```

The pre-supplied fact `DSH Desktop = 0.1.7-rc.2` is confirmed for the shell. The
`dsh-plugin-desktop 2.0.5` layer was not previously recorded and is added here.

## 3. Environment versions — measured

| Component | Measured | Notes |
| --- | --- | --- |
| OS | Microsoft Windows 11 专业版, Version 10.0.26200, Build 26200 | matches supplied `10.0.26200.0` |
| Git | `2.55.0.windows.2` | matches supplied |
| Python (Windows-native) | `3.14.4` | `C:\Users\20771\AppData\Local\Python\pythoncore-3.14-64\python.exe` — matches supplied |
| Python (MSYS2, Bash PATH) | `3.14.5` | `C:/msys64/mingw64/bin/python.exe` — **shadows the above inside the Bash tool** |
| Node.js (system) | `v20.12.0` | matches supplied |
| npm | `10.5.0` | matches supplied |
| Docker | `29.7.2`, build `a7dcaa6` | matches supplied |
| Node.js (DSH-bundled) | `24.18.1` | **differs from system Node** — DSH does not use the system runtime |

### 3.1 Version discrepancy found

The supplied fact `Python = 3.14.4` is correct **only for the Windows-native interpreter**.
Inside the Bash tool, `PATH` resolves `python` to MSYS2's `3.14.5` first:

```text
$ which -a python          # /c/msys64/mingw64/bin/python  ← resolved first
$ python --version         # Python 3.14.5  (MINGW GCC 16.1.0)
$ powershell -c "python --version"   # Python 3.14.4  ← Windows-native
```

**Consequence:** any automation run from Bash may execute a different interpreter than
one run from PowerShell. Baseline commands must record the shell they were run in.

## 4. Installation method

| Item | Finding |
| --- | --- |
| Install root | `%LOCALAPPDATA%\Programs\DeepSeek Harness\` (per-user, no admin) |
| Installer | `Uninstall DeepSeek Harness.exe` present → standard per-user Windows installer |
| Update channel | `nightly` |
| Update feed | `https://download.deepseek.com/dsh-desk/feeds/win-x64/` |
| Publisher | `CN=Hangzhou DeepSeek Artificial Intelligence Co., Ltd., O=Hangzhou DeepSeek Artificial Intelligence Co., Ltd., C=CN` |
| Application package | `resources/app.asar` (~117 MB), with `app.asar.unpacked/` for native deps (`node-pty`, `fontkit`, `@img`, …) |

Install method was **observed from artifacts**, not re-run. Re-installation was not performed
and is therefore `NOT_RUN` (see [§8](#8-capability-classification)).

## 5. Startup and shutdown

### 5.1 Startup method — verified

Two shortcuts exist, both targeting the executable **directly with no arguments**:

```text
Start Menu : %APPDATA%\Microsoft\Windows\Start Menu\Programs\DeepSeek Harness.lnk
Desktop    : %USERPROFILE%\Desktop\DeepSeek Harness.lnk
TargetPath : C:\Users\20771\AppData\Local\Programs\DeepSeek Harness\DeepSeek Harness.exe
Arguments  : (none)
WorkingDir : C:\Users\20771\AppData\Local\Programs\DeepSeek Harness
```

**There is no `dsh` CLI on `PATH`**, and no headless entry point reachable from a shell.
`~/.dsh/profiles/desktop/node_modules/` is empty. The `app.asar.unpacked/dsh/` directory
is unpacked native dependencies, not a CLI. DSH Desktop is **GUI-only** from a shell's perspective.

### 5.2 Running state — verified

```text
5 processes, all started 2026-09-26 22:09:31
PIDs: 7176, 21184, 29244, 36116, 37124
```

Window state at checkpoint start:

| Property | Value |
| --- | --- |
| Window class | `Chrome_WidgetWin_1` |
| Title | `DeepSeek Harness` |
| Visible | **False** — resident in system tray (`Electron_NotifyIconHostWindow` present) |

### 5.3 Local service — verified

DSH serves a loopback HTTP endpoint:

```text
PID 7176 listening on 127.0.0.1:19387
```

```text
$ curl -s -i http://127.0.0.1:19387/
HTTP/1.1 401 Unauthorized
dsh web authentication required; reopen the URL printed by dsh web.
```

This is **consistent with** the configured `networkExposure: loopback` and is a
**positive security property**: the local endpoint is not unauthenticated.

### 5.4 Shutdown behaviour — verified

`WM_CLOSE` (the standard window-close gesture) was sent to the main window **twice**:
once while the window was hidden, and once while it was visible and foregrounded.

```text
Run 1 — window hidden before close
  Pre  : 5 processes, window visible = False
  Post : 5 processes, window visible = False   (no observable change)

Run 2 — window visible and foregrounded before close
  Pre  : 5 processes, window visible = True
  Post : 5 processes, window visible = False   ← window hidden to tray
```

**Finding: closing the DSH window hides it to the system tray; it does NOT terminate DSH.**
All 5 processes remain alive with unchanged PIDs. This is the correct, expected behaviour for
a tray-resident application, and it definitively establishes that **window-close is not the
exit path**.

The application's genuine exit path is the in-app `应用 → 退出` menu or the tray icon's
right-click Quit — both GUI-only actions with no shell-reachable equivalent
(see §8.1 for the avenues ruled out).

**Graceful termination — verified (operator-performed).**
Since no shell path exists, the Quit was performed by the human operator via the GUI
(agent actions are attributed because they are part of the evidence). Result:

```text
Before Quit : 5 processes (PIDs 7176, 21184, 29244, 36116, 37124), port 19387 LISTENING
After  Quit : 0 processes,                                    port 19387 NOT listening
```

A first operator attempt that clicked the window's `X` did **not** terminate DSH —
independently confirming §5.4 that window-close only hides to tray. The second attempt,
using the real Quit entry point, exited cleanly with no orphaned processes.

### 5.5 Restart and configuration persistence — verified

Relaunched using the documented startup method (the Start Menu shortcut):

```text
$ Start-Process "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\DeepSeek Harness.lnk"

process count : 5
new PIDs      : 24404, 29052, 29320, 38716, 43500
start time    : 2026-09-28 10:32:20–21  (all fresh)
port 19387    : LISTENING again (pid 29052)
loopback probe: HTTP 401  (service up, auth still enforced)
```

**Persistence: PASS.** `~/.dsh/storages/workspace.json` was byte-identical after restart —
the SecurityLab binding, its `createdAt`/`updatedAt` timestamps, and session
`session-bfd8b6a9-8c56-47e0-8138-06c878afd1e8` all survived unchanged.

> **New finding — DSH writes no durable startup log.**
> After the restart, `%APPDATA%\DSH Desktop\logs\` and `lifecycle-events\startup.jsonl`
> were **still** dated 2026-09-15. A full stop/start cycle on 2026-09-28 appended nothing.
> This double-confirms limitation #7 (§9.2): DSH 0.1.7-rc.2 does not persist startup
> lifecycle events to these paths under this configuration.
> **Consequence: startup evidence for future checkpoints must come from process and
> port observation, not from DSH's own log files.**

**Termination and restart WERE completed in Checkpoint #1.** See §5.4 (graceful termination),
§5.5 (restart and configuration persistence), and capability entries #6 and #7 in §8.
Force-kill (`Stop-Process`) was deliberately **not** used at any point: it tests neither
graceful shutdown nor restart recovery, and would have misrepresented the result. All
termination evidence above comes from the application's own Quit path, not from a forced kill.

## 6. Configuration baseline (no secrets)

### 6.1 Configuration locations

| Path | Role |
| --- | --- |
| `~/.dsh/` | DSH config home (profiles, sessions, storages) |
| `%APPDATA%\DSH Desktop\` | Electron `userData` (logs, lifecycle-events, caches) |
| `%LOCALAPPDATA%\Programs\DeepSeek Harness\resources\` | Application bundle + bundled runtime |

### 6.2 Active profile — `desktop`

`~/.dsh/profiles/desktop/package.json`:

```json
{
  "name": "dsh-profile-desktop",
  "private": true,
  "dependencies": {},
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-web-app",
        "@deepseek-ai/dsh-experimental-agent-team-profile"
      ],
      "patchReload": "live"
    }
  }
}
```

**Plugin loading mechanism: Cordis profile composition.** `cordis.yml` is an empty root
entry list; the tree is composed as layered patches — bundle layer(s) → `cordis.patch.yml`
→ `--patch` overlays. `patchReload: live` means the patch layer hot-reloads.

`~/.dsh/profiles/desktop/cordis.patch.yml` — operator patch layer (UI configuration only,
no provider config, no secrets):

```yaml
- id: ui-settings-general
  name: "@deepseek-ai/dsh-client-ui-settings-general"
  config: { welcomeNoticeVersion: 2026-08-13.1 }
- id: ui-theme
  name: "@deepseek-ai/dsh-client-ui-theme"
  config: { preference: dark }
- id: ui-chat
  name: "@deepseek-ai/dsh-client-ui-chat"
  config: { transcriptView: standard, performanceUsage: detailed }
- id: ui-settings
  name: "@deepseek-ai/dsh-client-ui-settings"
  config: { enabled: true }
- id: ui-settings-account
  name: "@deepseek-ai/dsh-client-ui-settings-account"
  config:
    version: 1
    step: done
    usage: detailed
    developerTools: true
    purpose: null
    process: standard
    completion: api-key
```

### 6.3 Security-relevant settings

From `~/.dsh/settings.yaml.imported` (non-secret):

```yaml
dsh-desktop:
  mode: advanced
  openBrowser: false
  networkExposure: loopback     # local endpoint bound to loopback only
```

### 6.4 Minimal known-good configuration

The minimum configuration required to reproduce this baseline is the `desktop` profile plus
the operator patch layer above. No Workbench-specific configuration has been applied to DSH yet —
`config/dsh/config.example.yaml` in this repository is an **unwired example** (see §7.2).

### 6.5 Secret material — located, NOT read

```text
~/.dsh/.credentials.yaml   (540 bytes, present)
```

This file was **identified but deliberately not opened or copied**, per
[GIT_AND_SECURITY_BOUNDARY.md](GIT_AND_SECURITY_BOUNDARY.md). It must remain runtime-only.
No credential value appears anywhere in this document or this commit.

## 7. Workspace binding — SecurityLab

### 7.1 Binding — verified

`~/.dsh/storages/workspace.json` — exactly **one** workspace is registered:

```json
{
  "unit": { "name": "workspace", "version": 2 },
  "global": {
    "initialized": true,
    "workspaceIds": ["7401d692-ae44-419b-9ae3-570b7d2aa94a"],
    "archivedSessionIds": []
  },
  "tables": {
    "workspaces": {
      "7401d692-ae44-419b-9ae3-570b7d2aa94a": {
        "path": "D:\\SecurityLab",
        "title": "SecurityLab",
        "sessionIds": ["session-bfd8b6a9-8c56-47e0-8138-06c878afd1e8"],
        "createdAt": "2026-09-15T06:55:47.713Z",
        "updatedAt": "2026-09-26T12:51:41.268Z"
      }
    }
  }
}
```

Confirmed visually in the DSH UI: the workspace list shows **SecurityLab**, standard mode
(`标准模式`), with a session attached.

### 7.2 Independence, controlled access, and read-only enforcement

These are **three distinct claims** and they are classified separately below. Only the first
two are PASS. **Read-only enforcement is not implemented.**

| # | Claim | Result | Evidence |
| --- | --- | --- | --- |
| A | SecurityLab workspace binding | **PASS** | registered in `~/.dsh/storages/workspace.json` (§7.1); visible in the DSH UI |
| B | Controlled read observation | **PASS** | `AGENTS.md` and `README.md` read; `git status --short` returned **0** files before and after |
| C | Read-only enforcement | **FAIL / NOT_IMPLEMENTED** | see below |
| — | SecurityLab independent of Workbench | **PASS** | separate repo, remote `git@github.com:Li20771/SecurityLab.git`, path `D:\SecurityLab` |

SecurityLab state at checkpoint (read-only observation):

```text
branch : main
HEAD   : efa836ff9225f6226ca8a76615f3f45c31110d58
status : clean (0 modified files)
```

Controlled read executed: `AGENTS.md`, `README.md`. Integrity re-checked after: still 0 dirty files.

> **A and B do NOT imply C.**
>
> Claim B is an **observation about what was actually done** during this checkpoint — files
> were read and nothing was modified. It is **not** evidence that a read-only permission
> control exists or was exercised. No such control was exercised, because none exists yet.
>
> `workspaces/workspaces.example.yaml` declares `access_profile: readonly`, but that is a
> Workbench-side *example file* that **nothing consumes**. The DSH workspace registry (§7.1)
> carries **no read-only flag**, and no Guard/permission plugin exists yet (Guard is AI-04,
> explicitly out of AI-01 scope).
>
> Therefore read-only is currently a **policy intent, not an enforced control**. Until Guard
> exists, SecurityLab write-protection rests entirely on human and process discipline.
> Claim C is recorded as **FAIL / NOT_IMPLEMENTED** and must not be read as PASS.
>
> This section deliberately avoids the phrase "controlled read-only access": claims A/B
> (binding, observation) and claim C (enforcement) are separate, and only A/B pass.

## 8. Capability classification

Every item carries real execution evidence or is explicitly not claimed.

| # | Capability | Status | Evidence / reason |
| --- | --- | --- | --- |
| 1 | DSH installed & version identified | **PASS** | VersionInfo + `versions.json` + log banner (§2) |
| 2 | DSH process running | **PASS** | 5 PIDs alive, started 2026-09-26 22:09:31 (§5.2) |
| 3 | Startup method identified | **PASS** | shortcut target resolved, no args (§5.1) |
| 4 | Local service reachable | **PASS** | `127.0.0.1:19387` → HTTP 401 (§5.3) |
| 5 | Shutdown via window-close | **PASS** (behaviour characterised) | close → stays in tray, does not exit (§5.4) |
| 6 | Graceful process termination | **PASS** | operator GUI Quit → 0 processes, port closed (§5.4) |
| 7 | Restart / recovery | **PASS** | relaunched from shortcut; 5 new PIDs, port back (§5.5) |
| 8 | Restart after environment reboot | **NOT_RUN** | not exercised in this checkpoint |
| 9 | Configuration baseline captured | **PASS** | profile + bundles + patch layer (§6) |
| 10 | Plugin loading mechanism identified | **PASS** (config-level) | Cordis profile layering (§6.2) |
| 11 | Plugin runtime behaviour | **NOT_RUN** | needs an agent turn in the GUI |
| 12 | SecurityLab workspace bound | **PASS** | `workspace.json` + UI observation (§7.1) |
| 13 | Workspace controlled read | **PASS** | SecurityLab files read, integrity clean (§7.2) |
| 14 | Workspace read-only enforced | **FAIL** | not implemented; no Guard plugin (§7.2) |
| 15 | Agent answers a prompt | **NOT_RUN** | no CLI; loopback needs session token (§9.1) |
| 16 | Git inspection via DSH agent | **NOT_RUN** | same as #15 |
| 17 | Workspace read via DSH agent | **NOT_RUN** | same as #15 |
| 18 | Context loading via DSH agent | **NOT_RUN** | same as #15 |
| 19 | Permission boundary (allowed + blocked) | **NOT_RUN** | Guard is AI-04, out of scope |
| 20 | Re-installation from scratch | **NOT_RUN** | not performed; install observed from artifacts |

Status semantics per [GIT_AND_SECURITY_BOUNDARY.md](GIT_AND_SECURITY_BOUNDARY.md):
`PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN`. Nothing above is inferred from documentation;
`NOT_RUN` items were not converted to PASS.

### 8.1 Why items #15–#18 are NOT_RUN rather than FAIL

DSH Desktop exposes exactly two agent surfaces, and both are closed to this session:

1. **GUI** — the only complete surface. Driving it would require synthetic input automation.
2. **Loopback web app** (`127.0.0.1:19387`) — returns `401`; the session token is printed
   only inside the DSH UI.

Obtaining that token would mean reading `~/.dsh/.credentials.yaml` or scraping app state —
i.e. **credential access**, a protected action. GUI automation was also declined as being an
uncontrolled interface. Neither was attempted. These items are therefore honestly `NOT_RUN`,
with a manual procedure provided at [§9.1](#91-manual-verification-procedure-for-a-human-operator).

## 9. AI-01 exit criteria status

| Exit criterion | Status |
| --- | --- |
| Exact tested DSH version recorded | PASS (checkpoint-level) |
| Runtime dependency versions recorded | PASS (checkpoint-level) |
| Clean installation/start procedure documented | BLOCKED — install observed, not re-run |
| Startup/restart behaviour verified | PASS — startup, graceful exit, restart and persistence all verified (§5.1–§5.5) |
| Known-good configuration recorded without secrets | PASS |
| Controlled workspace binding verified | PASS — binding (§7.1) plus controlled read observation (§7.2 A/B). Read-only **enforcement** is a separate claim and is FAIL (§7.2 C); it is not part of this criterion. |
| Required baseline Agent behavior verified | NOT_RUN |
| Required plugin/tool behavior verified | NOT_RUN |
| Permission boundaries verified | NOT_RUN (Guard = AI-04) |
| Evidence record completed | PARTIAL — this document |
| Reproducible rollback point recorded | PASS (§10) |
| Known limitations classified | PASS (§9.2) |
| PR reviewed and merged | PENDING |
| PROJECT_STATUS.md updated | **NOT DONE — intentionally** |

**AI-01 is not complete.** This is Checkpoint #1.

### 9.1 Manual verification procedure for a human operator

Restart items #6 and #7 are now **complete** (§5.4, §5.5). The procedure below covers the
remaining `NOT_RUN` items #15–#18. Run in the DSH GUI:

```text
## Agent behaviour (use a NEW session, not a pre-existing one)
1. Open a new session in the SecurityLab workspace
2. Ask a trivial question            → expect a normal answer       (item #15)
3. Ask it to run: git rev-parse HEAD → expect efa836ff9225f6226ca8a76615f3f45c31110d58
                                                                      (item #16)
4. Ask it to read README.md          → expect SecurityLab content    (item #17)
5. Ask what the project's research directions are → expect the list
   from SecurityLab/AGENTS.md                                         (item #18)
6. After each step, re-check: cd D:\SecurityLab && git status --short → expect clean
```

Record the observed result verbatim; do not mark PASS without a visible response.

### 9.2 Known limitations

1. **DSH Desktop is GUI-only.** No CLI, no headless mode, no shell entry point. Any future
   AI-01/AI-02 automation must either bind to the authenticated loopback API or accept that
   DSH-internal behaviour is human-verified.
2. **`nightly` update channel.** The installed build is on a nightly feed, so the baseline
   is inherently unstable — `0.1.7-rc.2` may be replaced by a background auto-update. Any
   claim of "supported DSH version" must be pinned and re-verified per checkpoint.
3. **Three-layer versioning.** Shell (`0.1.7-rc.2`), desktop plugin (`2.0.5`), and app bundle
   can move independently. A single version string is insufficient to identify a baseline.
4. **Read-only workspace access is unenforced** (§7.2). Until Guard exists (AI-04), SecurityLab
   write-protection is a human/process control only.
5. **Python interpreter ambiguity** (§3.1). Bash and PowerShell resolve `python` differently.
6. **System Node ≠ DSH Node.** DSH bundles Node `24.18.1`; the system has `v20.12.0`. Workbench
   tooling must not assume the DSH runtime is the system runtime.
7. **No durable startup log.** `logs/` and `lifecycle-events/startup.jsonl` were last written
   2026-09-15 and were **not** appended to by a full stop/start cycle on 2026-09-28 (§5.5).
   DSH exposes no first-party startup log under this configuration, so startup evidence must
   come from process/port observation instead. This also means these stale files must never
   be cited as evidence of a current run.
8. **Window-close is not Quit.** Verified twice (§5.4) and again accidentally by the operator
   during this checkpoint. Anyone testing shutdown must use the tray or in-app Quit; clicking
   `X` will produce a false "still running" reading.

## 10. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `f7883681ab7219314f6a4ad2fb6abd2b45595e4d` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard f7883681ab7219314f6a4ad2fb6abd2b45595e4d` |
| Side effects on DSH | **None.** No DSH configuration was written by this checkpoint |
| SecurityLab impact | **None.** Read-only; 0 dirty files |

This checkpoint is **documentation-only**. It changes no DSH configuration, no Workbench
runtime behaviour, and no SecurityLab content. Rollback is therefore a plain revert of this
commit with no environmental cleanup required.

## 11. Validation commands and results

All commands below were executed on 2026-09-28 on branch `baseline/ai-01-dsh-20260928`.

| Command | Result |
| --- | --- |
| `bash scripts/bootstrap/preflight.sh` | **PASS** |
| `bash tests/unit/test_repository_layout.sh` | **PASS** |
| `bash -n scripts/bootstrap/preflight.sh` | **PASS** |
| `bash -n tests/unit/test_repository_layout.sh` | **PASS** |
| CI required-files check (6 files) | **PASS** |
| CI secret-file check (`.env`, `credentials.json`, `*.pem`, `*.key`) | **PASS** — none present |
| `git rev-list --left-right --count origin/main...HEAD` | `0 0` at branch creation |

CI parity note: `.github/workflows/preflight.yml` was replicated locally step-for-step.
`shellcheck` is not used by CI and was not required locally.

## 12. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-001` |
| Checkpoint | #1 |
| Branch | `baseline/ai-01-dsh-20260928` |
| Base SHA | `f7883681ab7219314f6a4ad2fb6abd2b45595e4d` |
| DSH version | `0.1.7-rc.2` shell / `2.0.5` desktop plugin / Electron `44.0.0` |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| AI-01 status | **IN PROGRESS — not complete** |
| Final status | **PARTIAL** — 11 PASS, 1 FAIL, 0 BLOCKED, 8 NOT_RUN, 0 UNKNOWN (of 20) |

**Out of scope and not implemented in this checkpoint** (per AI-01 §7 and today's boundary):
Context plugin, Guard plugin, Evidence plugin, Security Tools plugin, Model Router,
DeepSeek/MiMo provider integration, Codex integration, and any AI-02+ work.
