# AI-01 — DSH Baseline Checkpoint #10: Windows Sandbox Registration Investigation

> **Status: COMPLETE — CHECKPOINT #10 (read-only)**
> Experiment ID: `AI-01-DSH-20260928-010`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: CP1 · CP2 · CP3 · CP4 · CP5 · CP6 · CP7 · CP8 · CP9 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. Objective

Answer one question about this Windows image:

> Is `Containers-DisposableClientVM` (Windows Sandbox) **merely not enabled**, or is it
> **not registered at all**?

This checkpoint is **read-only**. Nothing was enabled, installed, repaired, uninstalled, or
modified. No `Enable-WindowsOptionalFeature`, no `DISM /Add-Package`, no `/RestoreHealth`, no
SFC, no Windows Update change, no Store operation, no VM, no clean install.

**CP10 supersedes CP9's Sandbox-enableability inference.** See §9 — CP9 itself is not modified.

## 2. Baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp10` |
| Base SHA | `09956d902016434496fa5a4d002064bfabae6eec` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree | clean |
| Investigation run | `2026-09-28 19:36–19:40` (local) |

> **Base SHA note.** The task named `7a49c21…` but instructed not to assume it. `origin/main`
> had advanced — **CP9 was merged as `09956d9`** — so this checkpoint is based on `09956d9`,
> the actual current main.

## 3. Method, and one access limitation that shapes everything below

**This session runs unelevated:** `user LILIKE\20771`, `is admin: False`.

Every administrative query therefore **fails for me**, and I recorded the exact failures
rather than paraphrasing them:

| Query | My result (unelevated) |
| --- | --- |
| `Get-WindowsOptionalFeature -Online` | `ERROR: The requested operation requires elevation.` |
| `dism /Online /Get-FeatureInfo /FeatureName:Containers-DisposableClientVM` | `Error: 740` — *"Elevated permissions are required to run DISM."* — **exit code 740** |
| `Get-WindowsPackage -Online` | `ERROR: The requested operation requires elevation.` |
| `Get-AppxPackage -AllUsers` | `ERROR: Access is denied.` |
| `Get-ChildItem "$env:ProgramFiles\WindowsApps"` | `ERROR: Access to the path … is denied.` |

**Consequence for evidence quality.** Feature-registration results come from the **operator's
elevated session** and are recorded here as **operator-reported**. Everything in §11 is **my
own direct read-only observation** and is the new evidence this checkpoint contributes. The
distinction is maintained throughout; nothing is presented as my observation when it is not.

## 4. Windows version and build

| Property | Value |
| --- | --- |
| Caption | Microsoft Windows 11 专业版 (Pro) |
| EditionID | `Professional` |
| DisplayVersion | `25H2` |
| CurrentBuild / UBR | `26200` / `9457` → **26200.9457** |
| Version | `10.0.26200` |
| Architecture | x64 |
| InstallationType | `Client` |
| **BuildLabEx** | `26100.1.amd64fre.ge_release.240331-1435` |

`ge_release` is the **General Availability release** branch — observed from the OS itself.

> **No channel inference is made.** This checkpoint does not classify the host as
> Insider / Canary / Preview. The `ge_release` string is recorded as read; no conclusion about
> update channel is drawn from anything else.

## 5. Feature registration — `Containers-DisposableClientVM`

### 5.1 Operator-reported, elevated

```powershell
Get-WindowsOptionalFeature -Online |
  Where-Object { $_.FeatureName -match 'Sandbox|Disposable|Container' }
```

returned **only**:

```text
MSMQ-Container    Disabled
```

```powershell
dism /Online /Get-Features /Format:Table | findstr /I "Sandbox Disposable Container"
```

returned **only** `MSMQ-Container`.

```powershell
Get-WindowsPackage -Online |
  Where-Object { $_.PackageName -match 'Containers-DisposableClientVM|Containers-OptionalFeatures' }
```

returned **no match**.

### 5.2 My own attempt (unelevated, for the record)

```text
Get-WindowsOptionalFeature -Online   -> ERROR: The requested operation requires elevation.
dism /Online /Get-FeatureInfo ...    -> Error: 740, exit code 740
```

### 5.3 Finding

> **`Containers-DisposableClientVM` does not appear in the optional-feature list of this
> image.** It is not a registered-but-disabled feature; it is **not registered**.

**This directly contradicts the assumption that it is "merely disabled".**

## 6. AppX / Store registration

| Query | Result |
| --- | --- |
| `Get-AppxPackage` \| `Name -match 'Sandbox'` (current user) | **no match** |
| `Get-AppxPackage -AllUsers` | **Access is denied** (needs elevation) |
| `Get-AppxPackage -AllUsers -PackageTypeFilter Main,Bundle` | not obtainable (same denial) |

> **AppX / Store-version Sandbox registration = `UNKNOWN`.** The current-user query found
> nothing, but the all-users query — the one that would settle whether a 24H2+ Store-delivered
> Sandbox is registered — could not be run from this session. **No inference is drawn from
> its absence.**

## 7. WindowsApps and System32

| Path | Result |
| --- | --- |
| `C:\Program Files\WindowsApps` \| `Name -match 'Sandbox'` | **Access denied** → `UNKNOWN` |
| `%WINDIR%\System32` \| `*Sandbox*` | **no match** |
| `%WINDIR%\System32` \| `*WindowsSandbox*` | **0 matches** |

`WindowsSandbox.exe` and `WindowsSandboxClient.exe` are **absent**.

## 8. Start Menu / shell registration

```powershell
Get-StartApps | Where-Object { $_.Name -match 'Sandbox|沙盒' }
```

**no match** — no Sandbox entry is registered in the shell.

Consistent with §7: with no binaries present, no shell entry can exist.

## 9. Package residue vs installed package — the distinction this checkpoint exists to enforce

These are **four different things** and are recorded separately:

| # | Claim | Result | Evidence |
| --- | --- | --- | --- |
| 1 | **component-store file present** | **PRESENT** | 20 files matching `Containers-DisposableClientVM*` in `C:\Windows\servicing\Packages`, including `.mum`/`.cat` up to build `26100.9278`; plus 16 matching `Microsoft-Windows-Containers-OptionalFeatures*` |
| 2 | **installed package present** | **ABSENT** | operator's `Get-WindowsPackage -Online` → no match |
| 3 | **registered optional feature present** | **ABSENT** | operator's `Get-WindowsOptionalFeature` / `dism /Get-Features` → only `MSMQ-Container` |
| 4 | **AppX package present** | **UNKNOWN** | `-AllUsers` and `WindowsApps` both access-denied from this session |

> ```text
> C:\Windows\servicing\Packages\...Containers-DisposableClientVM*.mum present
>         ≠
> the optional feature is registered
>         ≠
> the feature is enabled
>         ≠
> Sandbox is runnable
> ```
>
> The `.mum` files are **servicing-store payload/residue that ships with the OS image**. On
> this image they are accompanied by **no feature registration whatsoever**. CP9 treated their
> presence as evidence of enableability; §10 shows why that inference does not hold.

## 10. New evidence — CBS package state, empirically calibrated

This is the checkpoint's own read-only contribution, and it corroborates the operator's
elevated findings from a different direction.

### 10.1 The calibration

CBS stores a `CurrentState` value per package under
`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages`.
To interpret it, the value was compared against a feature whose state is **already known on
this machine**: `VirtualMachinePlatform` is **enabled** (`vmcompute` and `HvHost` are running,
per CP9 §4.2).

```text
VirtualMachinePlatform — KNOWN ENABLED
  Version          Kind      CurrentState
  10.0.26100.1     Feature   112
  10.0.26100.1742  Feature    64
  10.0.26100.7309  Feature   112
  10.0.26100.9168  Feature    80
  10.0.26100.9444  Feature    80
  10.0.26100.9445  Feature    80
  10.0.26100.9457  Feature   112      <- current build
```

```text
Containers-DisposableClientVM — UNDER INVESTIGATION
  Version          Kind      CurrentState
  10.0.26100.1     Merged     64
  10.0.26100.1591  Feature    64
  10.0.26100.1742  Feature    64
  10.0.26100.8972  Merged     64
  10.0.26100.9168  Feature    64
  10.0.26100.9278  Merged     64
  10.0.26100.9445  Feature    64
  10.0.26100.9457  Feature    64      <- current build
```

### 10.2 The comparison that matters — same build version

| Feature | Package version | State |
| --- | --- | --- |
| VirtualMachinePlatform (**enabled**) | `10.0.26100.9457` | **112** |
| Containers-DisposableClientVM | `10.0.26100.9457` | **64** |

At the **identical package version**, the enabled feature's package reads `112`; the Sandbox
package reads `64`. **Every** Sandbox package — including the current-build one — reads `64`,
while the enabled feature reaches `112`.

### 10.3 How to read this, and how not to

This is an **empirical contrast observed on this machine**, not a citation of the CBS state
enumeration. The defensible statement is:

> On this host, an enabled feature has at least one package at `CurrentState 112`, including
> its current-build package. The Sandbox feature has **no** package at `112`; all of its
> packages, including the current-build one, read `64`.

That is consistent with **staged residue** rather than an installed feature, and it is
independent of the elevated feature query — yet agrees with it.

### 10.4 Registration asymmetry

`VirtualMachinePlatform` — a **registered** feature — has explicit *Disabled-FOD* wrapper
packages:

```text
HyperV-OptionalFeature-VirtualMachinePlatform-Client-Disabled-FOD-Package-Wrapper~…~10.0.26100.1742
HyperV-OptionalFeature-VirtualMachinePlatform-Client-Disabled-FOD-Package-Wrapper~…~10.0.26100.9168
```

For `Containers-DisposableClientVM`, a search for any `DisposableClientVM.*Disabled-FOD`
package returned **NONE**.

A registered feature that is turned off leaves a *Disabled-FOD* wrapper. Sandbox leaves none —
further evidence that it is **not registered as a feature on this image**.

## 11. Verdict per item

Using only the permitted vocabulary:

| Item | Verdict |
| --- | --- |
| component-store `.mum` residue | **PRESENT** |
| installed package | **ABSENT** |
| registered optional feature | **ABSENT** |
| feature enabled | **ABSENT** |
| Sandbox AppX package (current user) | **ABSENT** |
| Sandbox AppX package (all users) | **UNKNOWN** — query denied |
| `WindowsApps` Sandbox package | **UNKNOWN** — access denied |
| System32 Sandbox binaries | **ABSENT** |
| Start Menu entry | **ABSENT** |
| Sandbox runnable | **UNKNOWN** |

> **Scope of the `UNKNOWN` on runnability.** The legacy Optional Feature / System32 execution
> path is unavailable on this image, but the complete Store-delivered Sandbox application
> cannot be classified as runnable or non-runnable because the all-users AppX and WindowsApps
> queries were access-denied.
>
> The evidence model is therefore split, and the split is what matters here:
>
> ```text
> legacy Optional Feature path   Containers-DisposableClientVM  = ABSENT
>                                System32 legacy binaries       = ABSENT
> Store / AppX path              AppX all-users                 = UNKNOWN
>                                WindowsApps                    = UNKNOWN
>                                ---------------------------------------------
>                                complete Sandbox runnable      = UNKNOWN
> ```
>
> The `ABSENT` results establish that the **legacy path** is unavailable. They do **not**
> establish that no Sandbox can run on this machine, because the Store-delivered route was
> never observed — it was **access-denied**, which is not the same as absent.

Nothing was marked `REGISTERED_DISABLED` — that is precisely the category CP9 implied
("not enabled, but enableable") and precisely what the evidence **does not** support.

## 12. CP9 correction — required

```text
CP9 assertion:
    "Sandbox payload already on disk -> enabling is local enable + reboot,
     no download required"

Current verification:
    NOT CONFIRMED / CONTRADICTED BY FEATURE QUERY
```

CP9 §4.4/§5 inferred enableability from the presence of `Containers-DisposableClientVM`
component-store packages. **That inference does not hold.** The packages are staged residue;
the feature is **not registered**, so there is nothing for
`Enable-WindowsOptionalFeature -FeatureName Containers-DisposableClientVM` to enable — that
command would fail with a feature-not-found error, not succeed locally.

**CP9 is not modified and its conclusion is not deleted.** CP9's finding that the *files* are
present remains true and was correctly observed; what CP10 corrects is the **inference drawn
from them**. CP9 §17 also recorded the Sandbox as `REQUIRES_ADMIN`; that classification is now
known to be **too optimistic** — the obstacle is not permission alone.

## 13. Available vs unavailable paths

| Path | Assessment |
| --- | --- |
| Enable Windows Sandbox directly | **NOT AVAILABLE** — feature not registered (§5.3); no such feature to enable |
| Add the feature via FoD / capability | **UNKNOWN** — whether this image *can* accept it requires an elevated `Get-WindowsCapability` and possibly a Windows Update / FoD source. **Not determinable from this session.** |
| Enable the full Hyper-V role | **REQUIRES_ADMIN** — 136 `Microsoft-Hyper-V` packages are staged and the role is not enabled (`vmms` absent, CP9 §4.2). Still needs a guest OS image. |
| Third-party hypervisor (VirtualBox / VMware / QEMU) | **REQUIRES_ADMIN + download** — none installed |
| WSL2 | **NOT AVAILABLE** — Linux guests only |
| Same-machine reinstall | **NOT AVAILABLE** — non-clean (CP7 §4.3) |

**Best next path:** an **elevated determination of whether `Containers-DisposableClientVM` can
be added to this image at all** (`Get-WindowsCapability -Online`, and checking whether an FoD
or Windows Update source can supply it). That is the cheapest thing still unknown, and it
decides between the two remaining options. If the image cannot accept the feature, fall back
to a **third-party hypervisor or separate hardware**. This checkpoint does **not** establish
that Sandbox is unavailable in every form — only that the **legacy Optional Feature path** is
absent; the Store-delivered route remains unobserved (§11).

## 14. Why no clean install was executed here

1. The precondition for CP9's proposed path — an enableable Sandbox feature — **does not exist
   on this image** (§5, §12).
2. Every remaining path is `REQUIRES_ADMIN`, `NOT AVAILABLE`, or `UNKNOWN` (§13).
3. This checkpoint is explicitly read-only and ran unelevated.
4. Enabling or adding a Windows feature is a **system configuration change** requiring
   explicit authorization this checkpoint does not have.

No substitute evidence was recorded in place of the install.

## 15. Criterion #3

```text
CP1 BLOCKED · CP3 BLOCKED · CP5 BLOCKED · CP6 BLOCKED · CP7 BLOCKED · CP9 BLOCKED
CP10: BLOCKED   (unchanged)
```

**Still `BLOCKED`.** The blocker is now *better understood and less optimistic*: CP9 described
it as one administrator action plus a reboot plus freed memory. CP10 shows the feature is not
registered, so **that path is not available**; the shortest remaining path is an elevated
determination of whether the feature can be added at all, and failing that a different
virtualization approach.

## 16. Integrity

| Invariant | Result |
| --- | --- |
| **No** `Enable-WindowsOptionalFeature` | **PASS** |
| **No** `DISM /Enable-Feature`, `/Add-Package`, `/RestoreHealth` | **PASS** |
| **No** SFC, **no** Windows Update change, **no** Store operation | **PASS** |
| **No** system configuration changed | **PASS** |
| **No** elevation attempted | **PASS** — `is admin: False` throughout; DISM returned 740 and was not retried |
| **No** VM / user / Sandbox created | **PASS** |
| **No** clean install attempted | **PASS** |
| No credential or token access | **PASS** |
| DSH untouched | **PASS** — 5 processes, PIDs `24404, 29052, 29320, 38716, 43500`, start `2026-09-28 10:32:20` |
| SecurityLab unchanged | **PASS** — `main` @ `efa836ff9225f6226ca8a76615f3f45c31110d58`, `git status --short` empty (0 files) |
| Workbench `main` / production code unchanged | **PASS** |
| `PROJECT_STATUS.md` unchanged | **PASS** |
| CP1–CP9 unmodified | **PASS** — documentation added only |
| No Guard / plugin; no AI-02 | **PASS** |

## 17. Known limitations

Inherited from CP1 §9.2, CP3 §7.2, CP4 §9 (11–16), CP5 §11 (17–18), CP6 §9 (19–24),
CP7 §8 (25–27), CP8 §12 (28–31), CP9 §14 (32–35) — all still open. Added at this checkpoint:

36. **The agent cannot run administrative Windows queries.** Every feature/DISM/package query
    fails unelevated (error 740 / access denied). Feature-registration evidence is therefore
    **operator-reported**, and AppX/WindowsApps registration remains `UNKNOWN` until an
    elevated query supplies it.
37. **CP9's Sandbox enableability inference was wrong** and is corrected in §12. The residue
    is real; the enableability conclusion drawn from it was not.
38. **The `CurrentState` interpretation is empirical, not authoritative.** §10 derives the
    meaning of `112` vs `64` from a known-enabled feature on this host rather than from
    documented CBS semantics. It agrees with the elevated query, but it is a corroborating
    signal, not a substitute for one.
39. **Whether this image can accept `Containers-DisposableClientVM` at all is `UNKNOWN`.**
    That is now the single most valuable unknown and is the recommended next step (§13).

## 18. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `09956d902016434496fa5a4d002064bfabae6eec` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard 09956d902016434496fa5a4d002064bfabae6eec` |
| Side effects on DSH | **None** |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 19. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | the branch base `09956d902016434496fa5a4d002064bfabae6eec` at validation time, since the document was still uncommitted while these commands ran |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_10.md` |

## 20. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-010` |
| Checkpoint | #10 |
| Branch | `baseline/ai-01-dsh-20260928-cp10` |
| Base SHA | `09956d902016434496fa5a4d002064bfabae6eec` |
| Windows | 11 Pro, 26200.9457, 25H2, x64, `ge_release` |
| `Containers-DisposableClientVM` feature registration | **ABSENT** (operator-reported, elevated) |
| DISM result | **Error 740** unelevated (mine); no such feature (operator, elevated) |
| Sandbox AppX | current user **ABSENT**; all-users **UNKNOWN** |
| WindowsApps Sandbox package | **UNKNOWN** (access denied) |
| System32 Sandbox binaries | **ABSENT** |
| Start Menu entry | **ABSENT** |
| **Sandbox runnable** | **UNKNOWN** — legacy path ABSENT; Store/AppX path never observed (access-denied) |
| component-store residue | **PRESENT** |
| registered feature | **NO** |
| Best next path | elevated determination of whether the feature can be added (FoD/capability); else third-party hypervisor or separate hardware |
| CP9 correction required | **YES** — recorded in §12, CP9 itself unmodified |
| **Criterion #3** | **BLOCKED** |
| Criterion #8 / #9 | PASS (unchanged) |
| **AI-01** | **BLOCKED** — #3 remains the sole blocker |
| `PROJECT_STATUS.md` | **unchanged** |
| AI-02 | **NOT STARTED** |
