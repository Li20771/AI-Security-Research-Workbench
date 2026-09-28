# AI-01 — DSH Baseline Checkpoint #9: Clean-Environment Capability Check

> **Status: COMPLETE — CHECKPOINT #9 (read-only capability survey)**
> Experiment ID: `AI-01-DSH-20260928-009`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: CP1 · CP2 · CP3 · CP4 · CP5 · CP6 · CP7 · CP8 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. Objective

Answer one question only:

> **Can an isolated Windows environment be obtained for AI-01 criterion #3?**

**Nothing was installed, enabled, or modified.** This checkpoint is a read-only survey of what
this machine can and cannot provide. It does **not** perform a clean install, does not enable
any Windows feature, does not create a VM, and does not attempt elevation.

## 2. Baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp9` |
| Base SHA | `7a49c211cde00f3493ab5020eb371451ddcf15de` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree | clean |
| Survey run | `2026-09-28 19:30–19:32` (local) |
| Elevation | **none** — `user LILIKE\20771`, `is admin: False` |

## 3. Windows

| Property | Value |
| --- | --- |
| Caption | Microsoft Windows 11 专业版 (**Pro**) |
| EditionID | `Professional` |
| DisplayVersion | `25H2` |
| Build | `26200` (UBR 9457) |
| Version | `10.0.26200` |
| Architecture | 64-bit (AMD64) |

> **Note on `ProductName`.** The registry value `HKLM\...\CurrentVersion\ProductName` reads
> `Windows 10 Pro`. This is a known Windows artefact — that value is not updated by an in-place
> upgrade to Windows 11. The authoritative fields (`EditionID: Professional`,
> `BuildNumber: 26200`, `DisplayVersion: 25H2`) and the OS caption all identify **Windows 11
> Pro**. Recorded so it is not mistaken for a Windows 10 machine later.

### 3.1 Physical, not virtual

| Property | Value |
| --- | --- |
| Manufacturer / Model | `LENOVO` / `83BF` |
| BIOS vendor | `LENOVO` |
| CPU | 12th Gen Intel Core i7-12700H |

This is a **physical machine**, not a guest. That matters: a guest would have made the
"clean environment" question trivial, and it does not.

## 4. Virtualization

| Observation | Value |
| --- | --- |
| `Win32_ComputerSystem.HypervisorPresent` | **True** |
| `VirtualizationFirmwareEnabled` (WMI) | `False` |
| `VMMonitorModeExtensions` (WMI) | `False` |
| `SecondLevelAddressTranslationExtensions` (WMI) | `False` |
| `systeminfo` Hyper-V requirements | **"A hypervisor has been detected. Features required for Hyper-V will not be displayed."** |

### 4.1 Reading these together — the `False` values are a masking artefact

The three `False` values must **not** be read as "virtualization is unavailable". When a
hypervisor is already running, Windows masks the CPU's virtualization flags from the
operating system, so these WMI properties report `False`. `systeminfo` states this explicitly.

**A hypervisor is running on this machine right now.** That is itself evidence that CPU
virtualization is enabled in firmware and functional — it is the precondition for the
services observed below (they are the WSL2 / VirtualMachinePlatform stack on Intel, which
requires VT-x).

**Conclusion: virtualization capability = functional.** Not "theoretically available" — it is
observably active.

### 4.2 Virtualization services

| Service | StartType | Status | Meaning |
| --- | --- | --- | --- |
| `vmcompute` (Host Compute Service) | Manual | **Running** | VirtualMachinePlatform present |
| `HvHost` (HV Host Service) | Manual | **Running** | hypervisor host present |
| `vmms` (VM Management) | — | **NOT PRESENT** | **full Hyper-V role NOT enabled** |
| `vmicvss` | Manual | Stopped | — |
| `WslService` | Automatic | **Running** | WSL2 in use |
| `docker` | — | **NOT PRESENT** | Docker engine service not registered |

`vmcompute` + `HvHost` running, `vmms` absent: this is the signature of
**VirtualMachinePlatform enabled (for WSL2) without the full Hyper-V role**.

### 4.3 Binaries

| Binary | State |
| --- | --- |
| `vmcompute.exe` | PRESENT |
| `vmms.exe` | absent |
| `WindowsSandbox.exe` | **absent** |
| `WindowsSandboxClient.exe` | absent |
| `VBoxManage.exe` | absent |
| `vmrun.exe` | absent |

### 4.4 Feature payloads staged in the component store

| Feature | Staged packages found |
| --- | --- |
| `Containers-DisposableClientVM` (Windows Sandbox) | **present** — e.g. `Containers-DisposableClientVM-merged-Package~31bf3856ad364e35~amd64~~10.0.26100.8972.mum` |
| `VirtualMachinePlatform` | 38 packages |
| `Microsoft-Hyper-V` | 136 packages |

**This is the key finding.** The Windows Sandbox payload is **already on disk**. Enabling the
feature would be a local enable plus a reboot — **no download required**.

## 5. Windows Sandbox

| Question | Answer |
| --- | --- |
| Does the edition support it? | **Yes** — Windows 11 Pro |
| Is it enabled? | **No** — `WindowsSandbox.exe` absent, feature query returns "requires elevation" |
| Is the payload present? | **Yes** — staged in the component store (§4.4) |
| Can it be enabled without elevation? | **No** |
| **Status** | **REQUIRES_ADMIN** |

## 6. Hyper-V

| Question | Answer |
| --- | --- |
| Is the platform present? | Partially — `vmcompute`/`HvHost` running |
| Is the full role enabled? | **No** — `vmms` absent, no `Get-VM` cmdlet |
| Can VMs be created now? | **No** |
| To enable | **REQUIRES_ADMIN** (+ reboot, + install media for a guest) |

## 7. Installed VM tooling

| Tool | State |
| --- | --- |
| VirtualBox | **NOT_INSTALLED** |
| VMware | **NOT_INSTALLED** |
| QEMU | **NOT_INSTALLED** |
| Hyper-V Manager | **NOT_INSTALLED** (`vmms` absent) |
| Docker Desktop | Installed (`Program Files\Docker`, CLI present) but **`com.docker.service` NOT PRESENT** and the daemon is not running — **NOT_AVAILABLE** |
| WSL2 | Installed — Ubuntu, docker-desktop, kali-linux, all **Linux** → **NOT_AVAILABLE** for a Windows GUI install |

Only `C:\Program Files\Docker` matched a virtualization-software search of both
`Program Files` roots. **No third-party hypervisor is installed.**

## 8. Resources

| Resource | Value | Assessment |
| --- | --- | --- |
| Total RAM | **15.73 GB** | adequate |
| **Available RAM** | **2.57 GB** | ⚠️ **insufficient for a Windows guest / Sandbox (needs ~4 GB+)** |
| Disk C: total | 200.4 GB | — |
| Disk C: free | **52.2 GB** | sufficient |

**The RAM constraint is real and independent of the permission problem.** Even after the
Sandbox feature is enabled, a Sandbox session would need meaningfully more free RAM than is
currently available. Freeing memory would be required before it could run.

## 9. Path assessment

| Path | Classification | Basis |
| --- | --- | --- |
| **Windows Sandbox** | **REQUIRES_ADMIN** | edition OK, payload staged locally, but feature not enabled and enabling needs elevation + reboot |
| **Full Hyper-V guest** | **REQUIRES_ADMIN** | role not enabled (`vmms` absent); needs elevation + reboot + install media |
| **VirtualBox / VMware / QEMU** | **NOT_INSTALLED** | absent; installing needs elevation |
| **Docker Desktop (Windows containers)** | **NOT_AVAILABLE** | service not registered, daemon down; and a headless container cannot host a GUI Electron app, so requirements 5–8 could not be exercised anyway |
| **WSL2** | **NOT_AVAILABLE** | Linux guests only — cannot validate a Windows GUI install |
| **`CodexSandboxOffline` / `CodexSandboxOnline` accounts** | **REQUIRES_ADMIN** | need elevation and their credentials (must not obtain), plus an interactive logon |
| **Same-machine reinstall** | **NOT_AVAILABLE** | non-clean: shares `~/.dsh`, `%APPDATA%\DSH Desktop` and `HKCU`; would also modify the current installation (CP7 §4.3) |
| **Cloud VM** | **NOT_AVAILABLE** | needs external account, credentials, provisioning — outside this boundary |

No path is `AVAILABLE`. Nothing was recorded as "theoretically possible".

## 10. Best available path and the minimal next action

> **Best available clean-environment path: Windows Sandbox**

It is the best option because the edition supports it, CPU virtualization is already
functional, the payload is **already on disk**, and it is genuinely disposable (state is
discarded on close). It is the shortest path to criterion #3.

**It requires an administrator. It cannot be done from this session.**

### 10.1 Minimal unlocking action (for an operator with admin rights)

```text
1. Close applications to free memory. Available RAM is currently 2.57 GB;
   a Sandbox session needs roughly 4 GB or more.

2. Enable the feature (no download required - payload is already staged):

     Enable-WindowsOptionalFeature -Online `
       -FeatureName Containers-DisposableClientVM -All

   or: Control Panel -> Turn Windows features on or off -> tick "Windows Sandbox".

3. Reboot.

4. Verify: WindowsSandbox.exe is present and a Sandbox session starts.

5. Then perform the CP7 §6.1 clean-install rehearsal inside the Sandbox:
   install -> start -> verify 0.1.7-rc.2 -> attach workspace -> minimal agent read
   -> close -> restart -> verify persistence, recording every command and result.
```

**Steps 2–4 were deliberately NOT performed.** They require elevation and a system
configuration change, both outside this checkpoint's boundary.

## 11. Why no clean install was executed here

1. Every viable path is `REQUIRES_ADMIN` or `NOT_AVAILABLE` (§9). None is `AVAILABLE`.
2. This checkpoint runs **unelevated** (`is admin: False`) and did not attempt elevation.
3. Enabling a Windows feature is a **system configuration change**, which requires explicit
   human authorization this checkpoint does not have.
4. Even with the feature enabled, **available RAM (2.57 GB) is below what a guest needs**.

A clean install could therefore not be attempted, and **no substitute was recorded in its
place** (CP7 §5). Criterion #3 is unchanged.

## 12. Criterion #3 — classification

```text
Criterion #3  Clean installation/start procedure documented
  CP1 BLOCKED · CP3 BLOCKED · CP5 BLOCKED · CP6 BLOCKED · CP7 BLOCKED
  CP9: BLOCKED   (unchanged)
```

**Still `BLOCKED`.** What changed is the quality of the blocker description: it is now known
to be **one administrator action plus a reboot plus freed memory** away from being
attemptable — not an unknown.

## 13. Integrity

| Invariant | Result |
| --- | --- |
| **No** Windows feature enabled | **PASS** |
| **No** system configuration changed | **PASS** |
| **No** elevation attempted | **PASS** — `is admin: False` throughout |
| **No** software installed or removed | **PASS** |
| **No** VM / Sandbox / account created | **PASS** |
| **No** clean install attempted | **PASS** |
| DSH untouched | **PASS** — 5 processes, same PIDs `24404, 29052, 29320, 38716, 43500`, start `2026-09-28 10:32:20`, `0.1.7-rc.2` |
| SecurityLab unchanged | **PASS** — `main` @ `efa836ff9225f6226ca8a76615f3f45c31110d58`, `git status --short` empty (0 files) |
| Workbench `main` unchanged | **PASS** — `7a49c211cde00f3493ab5020eb371451ddcf15de` |
| `PROJECT_STATUS.md` unchanged | **PASS** |
| No credential or token access | **PASS** |
| No Guard / plugin implemented; no AI-02 | **PASS** |

## 14. Known limitations

Inherited from CP1 §9.2, CP3 §7.2, CP4 §9 (11–16), CP5 §11 (17–18), CP6 §9 (19–24),
CP7 §8 (25–27), CP8 §12 (28–31) — all still open. Added at this checkpoint:

32. **Enabling Windows Sandbox requires an administrator**, and the agent runs unelevated.
    The remaining distance to criterion #3 is a human action, not further investigation.
33. **Available RAM (2.57 GB) is below a Windows guest's practical minimum.** Even with
    Sandbox enabled, memory must be freed first. This was not a factor in CP7 and is newly
    identified.
34. **The Windows Sandbox payload is staged but unverified as runnable.** Staged packages mean
    no download is needed; they do not prove a Sandbox session will start on this hardware.
    That remains `UNKNOWN` until it is actually launched.
35. **`ProductName` in the registry reads "Windows 10 Pro"** on this Windows 11 machine — a
    known artefact, recorded so a future reader is not misled.

## 15. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `7a49c211cde00f3493ab5020eb371451ddcf15de` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard 7a49c211cde00f3493ab5020eb371451ddcf15de` |
| Side effects on DSH | **None** |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 16. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | the branch base `7a49c211cde00f3493ab5020eb371451ddcf15de` at validation time, since the document was still uncommitted while these commands ran |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_9.md` |

## 17. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-009` |
| Checkpoint | #9 |
| Branch | `baseline/ai-01-dsh-20260928-cp9` |
| Base SHA | `7a49c211cde00f3493ab5020eb371451ddcf15de` |
| Windows | 11 Pro, build 26200, 25H2, 64-bit, physical (Lenovo 83BF) |
| Virtualization | functional (hypervisor detected and running) |
| Windows Sandbox | **REQUIRES_ADMIN** (payload staged, not enabled) |
| Hyper-V | **REQUIRES_ADMIN** (role not enabled) |
| VM tools | **NOT_INSTALLED** (no VirtualBox / VMware / QEMU) |
| RAM | 15.73 GB total / **2.57 GB available** |
| Disk | 200.4 GB total / **52.2 GB free** |
| Best clean-environment path | **Windows Sandbox** |
| Admin required | **YES** |
| **Criterion #3** | **BLOCKED** (unchanged) |
| Criterion #8 / #9 | PASS (unchanged) |
| **AI-01** | **BLOCKED** — #3 remains the sole blocker |
| `PROJECT_STATUS.md` | **unchanged** |
| AI-02 | **NOT STARTED** |
