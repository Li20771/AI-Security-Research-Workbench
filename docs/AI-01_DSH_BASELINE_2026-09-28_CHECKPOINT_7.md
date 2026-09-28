# AI-01 — DSH Baseline Checkpoint #7: Clean Installation Attempt

> **Status: COMPLETE — CHECKPOINT #7 (criterion #3 remains BLOCKED)**
> Experiment ID: `AI-01-DSH-20260928-007`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: CP1 · CP2 · CP3 · CP4 · CP5 · CP6 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. Objective

Resolve and verify AI-01 exit criterion #3:

> **Clean installation/start procedure documented**

The goal was a real, reproducible, evidence-backed clean-install baseline, moving #3 from
`BLOCKED` to `PASS`.

**Outcome: criterion #3 remains `BLOCKED`.** No isolated Windows environment could be
established, and the checkpoint's own rule forbids substituting inference for execution:

> *"如果环境条件无法满足，不得伪造 PASS，必须记录为 BLOCKED"*

**No PASS is claimed for anything that was not executed.**

## 2. Baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp7` |
| Base SHA | `12ba7e30ebe2de0e0aad5e544771f6fc822da817` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree at branch creation | clean |
| AI-01 state | #3 BLOCKED · #8 PASS · #9 BLOCKED · **AI-01 BLOCKED** |

## 3. Requirement 1 — installer identity verified (executed)

This is the one requirement that could be executed, and it was.

```text
path      : C:\Users\20771\AppData\Local\@deepseek-aidsh-desktop-updater\pending\
            deepseek-harness-0.1.7-rc.2-win-x64.exe
size      : 288245480 bytes
mtime     : 2026-09-26 21:37:24
sha256    : 0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86
filever   : 0.1.7-rc.2
authsig   : Valid
expected  : 0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86
MATCH     : True
```

| Check | Result | Status |
| --- | --- | --- |
| Installer artifact present | yes | **PASS** |
| SHA-256 matches the expected value | `MATCH: True` | **PASS** |
| Internal FileVersion | `0.1.7-rc.2` | **PASS** |
| Authenticode signature | `Valid` | **PASS** |

The artifact is unchanged since CP3 (`2026-09-26 21:37:24`, identical hash). Installer
identity is therefore established. **Installer identity is not clean-install evidence** — it
says nothing about whether the installation works.

## 4. Clean environment — feasibility investigation (executed)

Creating a disposable Windows environment was the precondition for every other requirement.
It was investigated directly rather than assumed.

### 4.1 Findings

```text
is admin                                : False
WindowsSandbox.exe                      : ABSENT (C:\Windows\System32\WindowsSandbox.exe)
Get-WindowsOptionalFeature -Online      : fails — "The requested operation requires elevation"
Hyper-V PowerShell module (Get-VM)      : not available
VBoxManage / vmrun / qemu-system-x86_64 : not installed
docker daemon                           : not running (npipe //./pipe/dockerDesktopLinuxEngine
                                          not found); docker *service* not found
WSL distros                             : Ubuntu, docker-desktop, kali-linux — all Linux
total RAM                               : 15.7 GB
free RAM                                : 2.4 GB
```

### 4.2 Every candidate path, and why each fails

| Candidate | Blocker |
| --- | --- |
| **Windows Sandbox** | Not installed. `WindowsSandbox.exe` is absent **and** enabling the feature requires **elevation + reboot** — a system configuration change. |
| **Hyper-V VM** | No Hyper-V cmdlets; enabling requires elevation. Additionally only **2.4 GB RAM free** — a Windows guest needs ~4 GB minimum. No installation media. |
| **VirtualBox / VMware** | Not installed. Installing them requires elevation, a system change, and a Windows ISO/licence. |
| **Docker Windows container** | Daemon not running; the docker **service** does not exist. Even if started, Desktop runs the **Linux** engine, and a Windows container is headless — it cannot host a **GUI Electron** application, so requirements 5–8 (workspace, agent read, restart, persistence) could not be exercised. |
| **WSL** | Distros are Linux. They cannot validate a **Windows GUI** installation. |
| **Existing `CodexSandboxOffline` / `CodexSandboxOnline` accounts** | Using another account requires its **credentials**, which this checkpoint must not obtain, and an interactive logon session, which cannot be created here. |
| **Second install directory under the same user** | **Not clean** — see §4.3. |
| **Reinstall over the existing installation** | Explicitly forbidden: it would modify the current DSH installation. |
| **Cloud VM** | Requires network provisioning, an external account and credentials — outside this task's boundary, which forbids unrelated network activity. |

### 4.3 Why a same-machine reinstall cannot be counted as "clean"

DSH installs **per-user** and keeps its state in per-user locations. A second installation
under the same account would share all of it:

```text
C:\Users\20771\.dsh                                  EXISTS   (config home: profiles, sessions, storages)
C:\Users\20771\AppData\Roaming\DSH Desktop           EXISTS   (Electron userData: logs, market, profile state)
C:\Users\20771\AppData\Local\Programs\DeepSeek Harness EXISTS   (current install root)
```

Re-running the installer would also write the same `HKCU` uninstall key and target the same
install root — i.e. it would **modify the current installation**, which this task forbids.

> Running the installer on this machine would produce a **contaminated** result that could not
> distinguish a clean install from the existing state. Recording it as a clean installation
> would be exactly the substitution the task prohibits — *"不把文档、历史日志或旧安装结果当成
> clean-install evidence"*. It was therefore **not attempted**.

### 4.4 Conclusion

> **No isolated, rollback-able Windows environment can be established under the current
> constraints.** The blockers are environmental and concrete, not a matter of effort: no
> elevation, no Sandbox, no VM tooling, no capacity, and a per-user state directory that any
> same-machine install would share.

## 5. Requirements 2–10 — status

| # | Required verification | Status | Reason |
| --- | --- | --- | --- |
| 1 | Verify installer identity + SHA-256 | **PASS** | §3 — executed |
| 2 | Actually install in a clean/disposable environment | **NOT_RUN** | no environment (§4) |
| 3 | Actually start DSH | **NOT_RUN** | depends on #2 |
| 4 | Verify version `0.1.7-rc.2` | **NOT_RUN** | depends on #2 |
| 5 | Verify basic workspace attachment | **NOT_RUN** | depends on #2 |
| 6 | Verify minimal agent / workspace read behaviour | **NOT_RUN** | depends on #2 |
| 7 | Verify restart after close | **NOT_RUN** | depends on #2 |
| 8 | Verify config / workspace persistence | **NOT_RUN** | depends on #2 |
| 9 | Determine first-run network dependency | **NOT_RUN** | depends on #2 |
| 10 | Record all actual commands and results | **PASS** | §3, §4 record everything that was executed — and record explicitly what was not |
| 11 | Do not pass off docs / old installs as clean-install evidence | **PASS** | rule observed; no substitute evidence used |

**Every requirement from #2 onward is `NOT_RUN`.** None is `PASS`, none is inferred, and none
is filled from CP1–CP6 material about the *existing* installation.

## 6. Criterion #3 — final classification

```text
Criterion #3  Clean installation/start procedure documented
  CP1: BLOCKED   CP3: BLOCKED   CP5: BLOCKED   CP6: BLOCKED
  CP7: BLOCKED   (unchanged)
```

**The criterion is not met.** What exists is a verified installer artifact and a documented
observed install method (CP3); what does not exist is an executed clean installation. Those
are not equivalent, and CP3 §7.2 already said so.

### 6.1 Unblock conditions

All of the following, in order:

```text
1. Provide a disposable / clean Windows environment that does NOT affect the current
   DSH installation. Any one of:
     (a) Windows Sandbox enabled   — requires an administrator to enable
         Containers-DisposableClientVM and reboot; or
     (b) a Hyper-V / VirtualBox / VMware Windows guest with >= 4 GB RAM and install
         media; or
     (c) a separate physical or virtual machine.

2. Copy the verified artifact out of the volatile updater cache into a controlled
   archive first, then install from it:
       deepseek-harness-0.1.7-rc.2-win-x64.exe
       size 288245480
       sha256 0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86

3. Actually perform, in that environment:
       install -> start -> verify version 0.1.7-rc.2 -> attach a workspace ->
       minimal agent/workspace read -> close -> restart -> verify persistence

4. Record every command and its actual result, including failures.
```

> Note: step 1 requires an **administrator**. This checkpoint ran unelevated and did not
> attempt to gain elevation, enable a Windows feature, or modify system configuration.

## 7. Boundary integrity

| Invariant | Result |
| --- | --- |
| Installer **not** run | **PASS** — the artifact was hashed, never executed |
| No software installed or uninstalled | **PASS** |
| Current DSH unaffected | **PASS** — 5 processes, same PIDs `24404, 29052, 29320, 38716, 43500`, same start time `2026-09-28 10:32:20`, `0.1.7-rc.2`, `127.0.0.1:19387` |
| No administrator elevation attempted | **PASS** |
| No Windows feature enabled, no system configuration changed | **PASS** |
| No VM / Sandbox / user account created | **PASS** |
| SecurityLab unchanged | **PASS** — `main` @ `efa836ff9225f6226ca8a76615f3f45c31110d58`, `git status --short` empty (0 files) |
| Workbench `main` unchanged | **PASS** — work on a branch |
| `PROJECT_STATUS.md` unchanged | **PASS** — deliberately untouched |
| No credential or token access | **PASS** |
| No DSH configuration change | **PASS** |
| No Workbench plugin / Guard / Evidence / Router implemented | **PASS** |
| No AI-02 work started | **PASS** |

## 8. Known limitations

Inherited from CP1 §9.2, CP3 §7.2, CP4 §9 (11–16), CP5 §11 (17–18), CP6 §9 (19–24) — all
still open. Added at this checkpoint:

25. **AI-01 criterion #3 is not completable on this machine by the agent.** It requires
    elevation to create an isolated environment, and elevation is outside the standing
    boundary. This is an environment property, not a defect in the baseline work.
26. **The installer artifact still lives in a volatile `electron-updater` cache.** It has
    survived since CP3, but a future update cycle could evict it. It should be copied to a
    controlled archive before the clean-install rehearsal.
27. **Any same-machine reinstall would be contaminated by per-user state** (§4.3) — `~/.dsh`,
    `%APPDATA%\DSH Desktop`, and `HKCU`. A future attempt must not treat such a run as a
    clean installation.

## 9. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `12ba7e30ebe2de0e0aad5e544771f6fc822da817` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard 12ba7e30ebe2de0e0aad5e544771f6fc822da817` |
| Side effects on DSH | **None** — no DSH state modified, installer never run |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 10. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | the branch base `12ba7e30ebe2de0e0aad5e544771f6fc822da817` at validation time, since the document was still uncommitted while these commands ran |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_7.md` |

## 11. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-007` |
| Checkpoint | #7 |
| Branch | `baseline/ai-01-dsh-20260928-cp7` |
| Base SHA | `12ba7e30ebe2de0e0aad5e544771f6fc822da817` |
| Installer SHA-256 | `0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86` (MATCH) |
| Clean environment | **not obtainable** — §4 |
| Install / start / workspace / restart / persistence / first-run network | **NOT_RUN** |
| **Criterion #3** | **BLOCKED** (unchanged) |
| Criterion #8 | PASS (unchanged) |
| Criterion #9 | BLOCKED (unchanged) |
| **AI-01** | **BLOCKED** |
| `PROJECT_STATUS.md` | **unchanged** |
| AI-02 | **NOT STARTED** |

Criterion #3 was **not** moved to `PASS`. The honest result of this checkpoint is a verified
installer, a documented environmental blocker, and a precise list of what would have to be
true for the criterion to be met.
