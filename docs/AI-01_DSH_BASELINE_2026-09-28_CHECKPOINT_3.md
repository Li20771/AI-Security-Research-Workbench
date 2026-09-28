# AI-01 — DSH Baseline Checkpoint #3

> **Status: COMPLETE — CHECKPOINT #3**
> Experiment ID: `AI-01-DSH-20260928-003`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: [Checkpoint #1](AI-01_DSH_BASELINE_2026-09-28.md), [Checkpoint #2](AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_2.md) (both merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

**This document does not mark AI-01 complete.** Checkpoints #1 and #2 are preserved unchanged;
this file is additive. `PROJECT_STATUS.md`, `MASTER_ROADMAP.md` and
`AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` are intentionally unchanged.

## 1. Nature and scope of this checkpoint

This checkpoint addresses exactly one AI-01 exit criterion, recorded as
`BLOCKED — install observed, not re-run` in Checkpoint #1:

> **Clean installation/start procedure documented**

The single question asked here was:

> Do we hold sufficient, **pinnable** installation material and documented steps for
> DSH `0.1.7-rc.2` to be reconstructed later from a clean environment?

**Method: read-only observation only.** No install, no uninstall, no download, no DSH
configuration change, no DSH process action. Every value below was read from the local
filesystem or registry; every hash was computed locally.

### 1.1 What this checkpoint does NOT establish

Stated up front because the classification in §6 depends on it:

- **A clean installation was not performed.** Nothing here demonstrates that a clean
  reinstall works, and no such claim is made.
- **Finding an installer is not the same as verifying reinstallability.** It establishes
  that installation material exists and can support a precise reinstall plan — nothing more.
- **The artifact set is not a controlled archive.** Both artifacts live in updater cache
  directories managed by `electron-updater` (§4).
- **Offline reconstruction was not tested.** Whether a clean first run requires network
  access to fetch profile bundles was not determined.
- **Artifact B has no integrity anchor** (§5.3).

## 2. Git baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp3` |
| Base SHA | `d2e397ad52fb5783f657a0630cb73b7f909762a3` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree at branch creation | clean |

## 3. Artifact A — DSH Harness shell installer `0.1.7-rc.2`

Two local copies of the **same** artifact exist; both were hashed and both are byte-identical.

### 3.1 Primary (version-named) copy

| Field | Value |
| --- | --- |
| Path | `C:\Users\20771\AppData\Local\@deepseek-aidsh-desktop-updater\pending\deepseek-harness-0.1.7-rc.2-win-x64.exe` |
| Size | `288245480` bytes |
| mtime | `2026-09-26 21:37:24` |
| SHA-256 | `0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86` |
| FileVersion | `0.1.7-rc.2` |
| ProductVersion | `0.1.7-rc.2` |
| ProductName | `DeepSeek Harness` |
| FileDescription | `Electron desktop shell for a bundled dsh runtime and external plugins` |
| Authenticode | **Valid** |

### 3.2 Working-copy duplicate

| Field | Value |
| --- | --- |
| Path | `C:\Users\20771\AppData\Local\@deepseek-aidsh-desktop-updater\installer.exe` |
| Size | `288245480` bytes |
| mtime | `2026-09-26 21:37:24` |
| SHA-256 | `0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86` |
| FileVersion / ProductVersion | `0.1.7-rc.2` / `0.1.7-rc.2` |
| ProductName | `DeepSeek Harness` |
| Authenticode | **Valid** |

Both SHA-256 values are identical, so these are the same binary under two names.

### 3.3 Publisher hash record

`C:\Users\20771\AppData\Local\@deepseek-aidsh-desktop-updater\pending\update-info.json`:

```json
{"fileName":"deepseek-harness-0.1.7-rc.2-win-x64.exe","sha512":"AY7f45dYO7BFrfgaLmzXNWP0pavlxkSbsehPo/WF6PXcFdDK3fF1oHUPs/4f2bzROgQvm6wSgawZ/g7UzbPRmw==","isAdminRightsRequired":false}
```

This record is what the updater wrote when it downloaded the artifact. It supplies:

- a **filename pinned to the exact version** (`0.1.7-rc.2`)
- a **SHA-512** to verify against
- `isAdminRightsRequired: false` — direct evidence for the per-user install classification (§4)

## 4. Artifact B — DSH Desktop plugin installer `2.0.5`

| Field | Value |
| --- | --- |
| Path | `C:\Users\20771\AppData\Local\dsh-plugin-desktop-updater\installer.exe` |
| Size | `134358451` bytes |
| mtime | `2026-09-15 11:02:11` |
| SHA-256 | `5BE1EBC44C6940EEE8C5DDBFAC52E048B07D5DD4B49B0642059C12E5A1E725A4` |
| FileVersion | `2.0.5` |
| ProductVersion | `2.0.5` |
| ProductName | `DSH Desktop` |
| FileDescription | `DSH Desktop: an Electron shell composed as a DeepSeek Harness Cordis plugin` |
| Authenticode | **NotSigned** |

No `update-info.json` (or equivalent publisher hash record) is present alongside this artifact.

### 4.1 Search for other artifacts

A bounded recursive search (`Depth 3`) of `%LOCALAPPDATA%`, `%USERPROFILE%\Downloads`,
`%USERPROFILE%\Desktop` and `%TEMP%` found **no other DSH installer artifacts**. Nothing is
archived outside the updater cache directories, and `Downloads` holds no DSH installer.

## 5. Integrity evidence

### 5.1 Artifact A — publisher hash record matches local recomputation

SHA-512 computed locally over the artifact and base64-encoded, compared against the recorded
value from `update-info.json`:

```text
computed sha512 (base64) : AY7f45dYO7BFrfgaLmzXNWP0pavlxkSbsehPo/WF6PXcFdDK3fF1oHUPs/4f2bzROgQvm6wSgawZ/g7UzbPRmw==
recorded sha512 (base64) : AY7f45dYO7BFrfgaLmzXNWP0pavlxkSbsehPo/WF6PXcFdDK3fF1oHUPs/4f2bzROgQvm6wSgawZ/g7UzbPRmw==
MATCH : True
```

### 5.2 Artifact A — Authenticode

```text
Status        : Valid
StatusMessage : Signature verified.
Subject       : CN="Hangzhou DeepSeek Artificial Intelligence Co., Ltd.",
                O="Hangzhou DeepSeek Artificial Intelligence Co., Ltd.",
                L=Hangzhou, S=Zhejiang, C=CN, ... SERIALNUMBER=91330105MACPN4X08Y,
                OID.2.5.4.15=Private Organization
Issuer        : CN=GlobalSign GCC R45 EV CodeSigning CA 2020, O=GlobalSign nv-sa, C=BE
NotAfter      : 2027-09-01 16:49:44
Thumbprint    : 84032578657219876E273E0D1BD303CFE1B82E6F
Timestamped   : yes (DigiCert SHA256 RSA4096 Timestamp Responder 2026 1)
```

Artifact A therefore carries **two independent integrity anchors**: a matching publisher
SHA-512 record, and a valid EV code signature from the stated publisher.

### 5.3 Artifact B — no integrity anchor established

Artifact B is **NotSigned** and has **no verified publisher hash anchor**.

> **Artifact B has neither a signature anchor nor a verified publisher hash anchor.
> Its provenance integrity is therefore NOT established.**

Its SHA-256 in §4 is a self-consistency measurement only — it lets a future check detect
change, but it does not attest that the binary is the genuine publisher artifact.

### 5.4 Installed binaries

| Binary | Authenticode |
| --- | --- |
| `DeepSeek Harness.exe` | **Valid** |
| `Uninstall DeepSeek Harness.exe` | **Valid** |

Both are signed by the same publisher, consistent with the current installation having come
from the signed Artifact A.

## 6. Installation method — observed facts

All values in this section were **directly observed**. Nothing here was inferred.

| Item | Observed value |
| --- | --- |
| Install scope | **per-user** |
| Admin rights | **not required** — `update-info.json` → `isAdminRightsRequired: false` |
| Uninstall string | `"C:\Users\20771\AppData\Local\Programs\DeepSeek Harness\Uninstall DeepSeek Harness.exe" /currentuser` (the `/currentuser` flag is direct evidence of per-user scope) |
| Install root | `C:\Users\20771\AppData\Local\Programs\DeepSeek Harness` |
| Uninstall registry entry | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\` → `DisplayName: DeepSeek Harness 0.1.7-rc.2`, `DisplayVersion: 0.1.7-rc.2`, `InstallLocation: C:\Users\20771\AppData\Local\Programs\DeepSeek Harness` |
| Shortcut target (Start Menu) | `...\Programs\DeepSeek Harness\DeepSeek Harness.exe`, arguments: **empty** |
| Shortcut target (Desktop) | same target, arguments: **empty** |
| Update channel | `nightly` |
| Update feed | `https://download.deepseek.com/dsh-desk/feeds/win-x64/` |
| Update provider | `generic` |
| Updater cache dir name | `@deepseek-aidsh-desktop-updater` |
| Expected publisher (`app-update.yml`) | `CN=Hangzhou DeepSeek Artificial Intelligence Co., Ltd., O=..., C=CN` |
| Uninstaller FileVersion | `0.1.7-rc.2` |

### 6.1 Installer implementation type — observational judgement only

> The current install layout is **consistent with an NSIS-style installer** (per-user
> `Programs` install root, a `Uninstall <Product>.exe` alongside the application, and
> `/currentuser` in the uninstall string; and it is **not** a Squirrel layout, since no
> `Update.exe` exists in the install root).
>
> **This checkpoint did not independently prove the installer implementation type.** The
> NSIS attribution is an observation-based judgement, not an established fact, and must not
> be upgraded without direct evidence from the installer itself.

## 7. Classification

Per the AI-01 status semantics `PASS` / `FAIL` / `BLOCKED` / `NOT_RUN` / `UNKNOWN`.

```text
Install artifact available             PASS
Exact-version artifact identified      PASS
Exact-version reinstall reproducible   BLOCKED
Clean installation actually executed   NOT_RUN
Startup procedure                      PASS
Overall installation criterion         BLOCKED
```

### 7.1 Basis for each classification

| Item | Basis |
| --- | --- |
| Install artifact available — **PASS** | Artifact A exists locally and is version-pinned (§3) |
| Exact-version artifact identified — **PASS** | `0.1.7-rc.2` confirmed by filename, internal VersionInfo, registry `DisplayVersion`, uninstaller FileVersion, and the publisher hash record — six independent fields agree (§3, §6) |
| Exact-version reinstall reproducible — **BLOCKED** | see §7.2 |
| Clean installation actually executed — **NOT_RUN** | deliberately not performed; a clean reinstall is a separate future checkpoint |
| Startup procedure — **PASS** | verified by execution in Checkpoint #1 §5.1/§5.5 (shortcut target with no arguments, relaunch from shortcut); re-observed here in §6 |
| Overall installation criterion — **BLOCKED** | the AI-01 criterion is "clean installation/start procedure documented"; startup is verified, but the clean-install half remains blocked |

`BLOCKED` rather than `UNKNOWN` because the blockers are **identified and specific**, not
merely unclear.

### 7.2 Why "exact-version reinstall reproducible" is BLOCKED

At minimum, all five of the following:

1. **The artifacts sit in updater cache, not a controlled long-term archive.**
   Both live under `electron-updater`-managed directories (`@deepseek-aidsh-desktop-updater`,
   `dsh-plugin-desktop-updater`). A future update cycle may overwrite or evict them.
   *Available now* is not *durably available*.
2. **The `nightly` channel does not guarantee the same build remains downloadable.**
   A nightly feed is not a stable release channel. Whether `0.1.7-rc.2` can still be fetched
   from upstream was **not tested** — no download was performed.
3. **Artifact B has no independent integrity anchor** (§5.3). A reinstall requiring the
   plugin cannot currently be verified for authenticity.
4. **Whether a clean first run requires network access is unverified.** Whether the profile
   bundles (`@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-web-app`,
   `@deepseek-ai/dsh-experimental-agent-team-profile`) ship inside the installer or are
   fetched on first run was **not determined** in this checkpoint. This directly affects
   whether an offline clean reconstruction is possible.
5. **No clean reinstall has been executed.**

> Finding the installer is not the same as having verified that a reinstall works. This
> checkpoint establishes only that usable installation material exists and that a precise
> reinstall plan can be built on top of it. Converting `BLOCKED` → `PASS` requires an actual
> clean-environment rehearsal, which is out of scope here.

## 8. Current DSH state — unchanged

| Item | Value |
| --- | --- |
| Process count | 5 |
| Start time | `2026-09-28 10:32:20` (unchanged since the Checkpoint #1 restart) |
| PIDs | `24404, 29052, 29320, 38716, 43500` |
| Loopback | `127.0.0.1:19387` listening (pid 29052) |

**This checkpoint did not uninstall, reinstall, reconfigure, restart or otherwise touch DSH.**
DSH remains the same running instance, with the same PIDs and start time as at the end of
Checkpoint #1.

## 9. SecurityLab — unchanged

```text
branch : main
HEAD   : efa836ff9225f6226ca8a76615f3f45c31110d58
git status --short -> (empty)

SecurityLab modified files = 0
```

## 10. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `bash -n scripts/bootstrap/preflight.sh` | PASS |
| `bash -n tests/unit/test_repository_layout.sh` | PASS |
| CI required-files check | PASS |
| CI secret-file check | PASS — none present |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_3.md` |

No credential material was read at any point; `~/.dsh/.credentials.yaml` was not opened.
No session token was obtained or used. No network configuration was changed and no git
remote was modified.

## 11. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `d2e397ad52fb5783f657a0630cb73b7f909762a3` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard d2e397ad52fb5783f657a0630cb73b7f909762a3` |
| Side effects on DSH | **None** — no DSH state was modified |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 12. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-003` |
| Checkpoint | #3 |
| Branch | `baseline/ai-01-dsh-20260928-cp3` |
| Base SHA | `d2e397ad52fb5783f657a0630cb73b7f909762a3` |
| DSH version | `0.1.7-rc.2` |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| **AI-01** | **IN PROGRESS** |
| **Checkpoint #3** | **COMPLETE** |
| **Overall installation criterion** | **BLOCKED** |

Not implemented in this checkpoint (per AI-01 §7 and the stated boundary): Context plugin,
Guard plugin, Evidence plugin, Security Tools plugin, Model Router, DeepSeek/MiMo provider
integration, Codex integration, and any AI-02+ work.
