# AI-01 — DSH Baseline Checkpoint #11: Windows Sandbox Availability — Closing Record

> **Status: COMPLETE — CHECKPOINT #11 (read-only, closing the Sandbox investigation)**
> Experiment ID: `AI-01-DSH-20260928-011`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: CP1 · CP2 · CP3 · CP4 · CP5 · CP6 · CP7 · CP8 · CP9 · CP10 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. Purpose

This checkpoint **closes** the Windows Sandbox availability investigation on this host. It
consolidates the read-only evidence gathered across CP9 and CP10 with the additional queries
recorded below, so that AI-01 criterion #3 has a complete, auditable basis for its status.

It answers one question and stops:

> Does this Windows host presently offer a Windows Sandbox environment that could be used to
> execute the AI-01 clean-installation validation?

**Answer: no such environment was found.** Both known installation paths were checked and
neither is present. Criterion #3 therefore remains `BLOCKED`.

## 2. Scope and non-goals

**In scope.** Read-only review and consolidation of Sandbox availability evidence; recording
the raw results of the feature / package / capability / AppX queries; correcting the record
where an earlier inference was too strong.

**Non-goals — none of the following was performed:**

- no installation, uninstallation, or enabling of any Windows feature
- no `DISM` modification, no registry modification, no reboot
- no same-machine DSH reinstall
- no clean-install attempt
- no elevation
- no AI-02 or later-phase work
- `PROJECT_STATUS.md` was **not** updated — AI-01 does not meet its COMPLETE conditions

No finding below is a `PASS` that was not executed, and no `BLOCKED` / `NOT_RUN` / `UNKNOWN`
was upgraded.

## 3. Host context

| Property | Value |
| --- | --- |
| Edition | Windows 11 专业版 (Pro), `EditionID: Professional` |
| Version | 25H2, build **26200.9457**, x64 |
| BuildLabEx | `26100.1.amd64fre.ge_release.240331-1435` (GA release branch) |
| Machine | LENOVO `83BF` — physical, not a guest (CP9 §3.1) |
| Virtualization | functional — a hypervisor is detected and running (CP9 §4) |
| RAM | 15.73 GB total / **2.57 GB available** (CP9 §8) |

### 3.1 Evidence provenance

The feature, package, capability and AppX queries below **require elevation**. The agent
session runs **unelevated** (`is admin: False`, re-confirmed at this checkpoint), so those
queries cannot be executed by the agent and are recorded as **operator-reported from an
elevated session**.

Items C and D are newly supplied by the operator for this checkpoint. Items A and B were
recorded in CP10. Everything the agent observed directly is labelled as such.

> The distinction is maintained deliberately: nothing here is presented as an agent
> observation when it is not.

## 4. Evidence commands and observed results

### A. Windows Sandbox Optional Feature — **not registered**

```powershell
Get-WindowsOptionalFeature -Online |
  Where-Object { $_.FeatureName -match 'Sandbox|Disposable|Container' }
```

Observed — the **only** match:

```text
MSMQ-Container    Disabled
```

```powershell
dism /Online /Get-Features /Format:Table | findstr /I "Sandbox Disposable Container"
```

Observed — the **only** match:

```text
MSMQ-Container
```

**Result:** `Containers-DisposableClientVM` = **ABSENT / NOT REGISTERED**.

### B. Windows Sandbox package — **not installed**

```powershell
Get-WindowsPackage -Online |
  Where-Object { $_.PackageName -match 'Containers-DisposableClientVM|Containers-OptionalFeatures' }
```

Observed: **no output.**

**Result:** relevant installed Windows package = **ABSENT**.

### C. Windows Capability — **not observed**

```powershell
Get-WindowsCapability -Online |
  Where-Object { $_.Name -match 'Sandbox' } |
  Format-Table Name, State -AutoSize
```

Observed: **no output.**

**Result:** any Windows Sandbox matching Capability = **NOT OBSERVED**.

This is the path that would have settled whether the image can *accept* the feature — the open
question left by CP10 §13/§17. It returned nothing.

### D. `WindowsSandbox` AppX registration — **not observed**

```powershell
Get-AppxPackage -AllUsers -Name WindowsSandbox |
  Select-Object Name, Version, Status, PackageFullName
```

Observed: **no output.**

**Result:** `WindowsSandbox` AppX registration = **ABSENT / NOT OBSERVED**.

> This closes the gap CP10 recorded as `UNKNOWN`. In CP10 the all-users AppX query was
> access-denied from the agent session (CP10 §6, §11); the operator has now run it elevated and
> it returned nothing. **The Store/AppX path is therefore also not present** — it is no longer
> merely unobserved-because-unqueryable.

### E. Component-store residue — **present** (retained from CP10)

Agent-observed (read-only, unelevated), CP10 §9/§10:

- 20 files matching `Containers-DisposableClientVM*` in `C:\Windows\servicing\Packages`,
  including `.mum`/`.cat` up to build `26100.9278`
- 16 files matching `Microsoft-Windows-Containers-OptionalFeatures*`
- CBS `CurrentState` = **64** for every Sandbox package, including the current-build one —
  whereas the *enabled* `VirtualMachinePlatform` reaches **112** at the same package version
- no `Disabled-FOD` wrapper exists for `DisposableClientVM`, while `VirtualMachinePlatform`
  has one

**What this residue is and is not:**

```text
component-store residue
      ≠  registered feature
      ≠  enabled feature
      ≠  an installed Sandbox
      ≠  a runnable Sandbox
```

**The residue does not demonstrate that Windows Sandbox is installed**, and it must not be
read as doing so. CP9 drew an enableability inference from it; CP10 §12 corrected that
inference, and this checkpoint restates the correction.

### F. Official installation paths (already verified)

Per the verified Microsoft Learn material for the supported installation routes:

1. **Legacy path** — Windows Sandbox is installed by enabling the
   `Containers-DisposableClientVM` Optional Feature. Result A shows that feature is **not
   registered** on this image, so this route is unavailable here.
2. **Store-delivered Sandbox (Windows 11 24H2+)** — the Store delivery **still requires Windows
   Sandbox to already be installed**; it is not a from-nothing installation path. Result D shows
   no `WindowsSandbox` AppX is registered, so this route is also unavailable here.

## 5. Result summary

| Path | Evidence | Result |
| --- | --- | --- |
| Optional Feature (`Containers-DisposableClientVM`) | A | **ABSENT / NOT REGISTERED** |
| Installed Windows package | B | **ABSENT** |
| Windows Capability | C | **NOT OBSERVED** |
| `WindowsSandbox` AppX registration | D | **ABSENT / NOT OBSERVED** |
| Component-store residue | E | **PRESENT** (residue only — proves nothing about installation) |

## 6. Interpretation

**Both known installation paths were checked, and neither is present:**

- the legacy Optional Feature path does not exist on this image (A, B, C);
- the Store/AppX path is not registered either (D).

**Therefore: this host has no installed Windows Sandbox environment that could be used for the
AI-01 clean-installation validation.**

> **This checkpoint does not assert that "Sandbox runnable = ABSENT".** The precise, supported
> statement is the one above — the two *known* paths are absent, so no Sandbox environment is
> **available for this purpose** on this host. A statement about Sandbox runnability in every
> conceivable form is not made, and cannot be made from these queries.

CP10's `Sandbox runnable = UNKNOWN` remains the correct classification of that broader claim;
this checkpoint narrows what is *established* without over-extending it. Where CP10 said the
Store path was `UNKNOWN` because the query was denied, D is now an actual observation of
absence — the practical conclusion is unchanged, but its basis is now direct rather than
unavailable.

## 7. CP9 inference correction / CP10 continuity

| Checkpoint | Statement | Status |
| --- | --- | --- |
| CP9 §4.4/§5 | "payload staged → enabling is local enable + reboot, no download required" | **CORRECTED** — CP10 §12; contradicted by the feature query. Restated in §4E above. |
| CP10 §11 | "Sandbox runnable = ABSENT" | **CORRECTED** — narrowed to `UNKNOWN` (CP10 revision). Not re-broadened here. |
| CP10 §6/§11 | AppX all-users / WindowsApps = `UNKNOWN` | **SUPERSEDED IN PART** — item D now supplies the all-users AppX observation. |

Neither CP9 nor CP10 is modified. This checkpoint is additive, and the corrections are
recorded here for continuity rather than applied retroactively.

## 8. AI-01 #3 status

```text
Criterion #3  Clean installation/start procedure documented

  CP1 BLOCKED · CP3 BLOCKED · CP5 BLOCKED · CP6 BLOCKED
  CP7 BLOCKED · CP9 BLOCKED · CP10 BLOCKED · CP11 BLOCKED
```

**`BLOCKED` — not `FAIL`.**

This is not a failure of the baseline work and not a failed test. No probe returned an
unexpected result; the required environment simply **does not exist on this host**, and the
investigation has now established that across every standard path. A `FAIL` would mean an
executed attempt did not work; nothing was attempted because there was nothing to attempt it
with.

## 9. Remaining blocker

```text
No clean, disposable Windows environment is available on this host.

  legacy Optional Feature path   NOT REGISTERED   (A, B, C)
  Store / AppX path              NOT OBSERVED     (D)
  component-store residue        present, but proves nothing (E)

  -> no Sandbox environment for the clean-install validation
```

The blocker is **environmental**, not procedural. It is also independent of the earlier
finding that enabling a Windows feature would require administrator rights — the feature is
not merely switched off, it is absent.

## 10. Next prerequisite for a real clean-install run

Criterion #3 can move forward only when **all** of the following hold:

```text
1. A clean, disposable Windows environment exists that does not affect the
   current DSH installation. On this host that requires first obtaining an
   environment that does not currently exist, e.g.:
     (a) a Windows Sandbox feature that is registered and installable on this
         image  -- currently NOT REGISTERED (A, B, C); and
         note the feature payload alone is insufficient: E shows residue is not
         registration; or
     (b) a Hyper-V / VirtualBox / VMware Windows guest (>= 4 GB RAM, install
         media)   -- REQUIRES_ADMIN + install media; or
     (c) separate physical or virtual hardware.

2. Free enough memory. Available RAM is 2.57 GB; a Windows guest needs
   roughly 4 GB or more.

3. A verified installer, copied out of the volatile updater cache into a
   controlled archive:
     deepseek-harness-0.1.7-rc.2-win-x64.exe
     size 288245480
     sha256 0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86

4. An actual run, recording every command and its real result:
     install -> start -> verify 0.1.7-rc.2 -> attach a workspace ->
     minimal agent/workspace read -> close -> restart -> verify persistence
```

Until step 1 is satisfied, no further investigation on this host will change criterion #3.

## 11. Integrity

| Invariant | Result |
| --- | --- |
| No feature installed / uninstalled / enabled | **PASS** |
| No `DISM` modification, no registry modification, no reboot | **PASS** |
| No elevation attempted by the agent | **PASS** — `is admin: False` throughout |
| No same-machine DSH reinstall attempted | **PASS** |
| No clean-install attempt | **PASS** |
| DSH untouched | **PASS** — 5 processes, PIDs `24404, 29052, 29320, 38716, 43500`, start `2026-09-28 10:32:20` |
| SecurityLab unchanged | **PASS** — `main` @ `efa836ff9225f6226ca8a76615f3f45c31110d58`, `git status --short` empty (0 files) |
| Workbench `main` / production code unchanged | **PASS** — documentation only |
| `PROJECT_STATUS.md` unchanged | **PASS** — intentionally not updated; AI-01 is not COMPLETE |
| CP1–CP10 unmodified | **PASS** — additive only |
| No credential or token access | **PASS** |
| No Guard / plugin implemented; no AI-02 | **PASS** |

## 12. Known limitations

Inherited from CP1 §9.2, CP3 §7.2, CP4 §9 (11–16), CP5 §11 (17–18), CP6 §9 (19–24),
CP7 §8 (25–27), CP8 §12 (28–31), CP9 §14 (32–35), CP10 §17 (36–39) — all still open.
Added at this checkpoint:

40. **Items A–D are operator-reported, not agent-observed.** They require elevation, which the
    agent does not have. Their raw results are recorded as reported; the commands are
    reproduced so they can be re-run independently.
41. **The Sandbox investigation on this host is now closed as far as it can be.** Every
    standard path has been queried. Further probing on this machine is not expected to change
    criterion #3, and no further probing is planned.
42. **A negative query result is not proof of absence in every form.** Items C and D returned
    no output; that establishes that no matching object was registered for those query scopes,
    which is what the conclusion in §6 relies on — no stronger claim is made.

## 13. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `52520cbc87a86e016b87100fc38c2f1ad9c1ec5d` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard 52520cbc87a86e016b87100fc38c2f1ad9c1ec5d` |
| Side effects on DSH | **None** |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 14. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | the branch base `52520cbc87a86e016b87100fc38c2f1ad9c1ec5d` at validation time, since the document was still uncommitted while these commands ran |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_11.md` |

## 15. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-011` |
| Checkpoint | #11 — Sandbox investigation closing record |
| Branch | `baseline/ai-01-dsh-20260928-cp11` |
| Base SHA | `52520cbc87a86e016b87100fc38c2f1ad9c1ec5d` |
| `Containers-DisposableClientVM` Optional Feature | **ABSENT / NOT REGISTERED** |
| Windows Sandbox package | **ABSENT** |
| Windows Sandbox Capability | **NOT OBSERVED** |
| `WindowsSandbox` AppX registration | **ABSENT / NOT OBSERVED** |
| Component-store residue | **PRESENT** — proves nothing about installation |
| Installed Sandbox environment for the clean-install validation | **NONE FOUND** |
| **Criterion #3** | **BLOCKED** (not FAIL) |
| Criterion #8 | **PASS** (unchanged) |
| Criterion #9 | **PASS** (unchanged) |
| **AI-01** | **BLOCKED** — #3 remains the sole blocker |
| `PROJECT_STATUS.md` | **unchanged** |
| AI-02 | **NOT STARTED** |
