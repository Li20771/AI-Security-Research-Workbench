# AI-01 — DSH Baseline Checkpoint #2

> **Status: PARTIAL — CHECKPOINT #2**
> Experiment ID: `AI-01-DSH-20260928-002`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessor: [AI-01_DSH_BASELINE_2026-09-28.md](AI-01_DSH_BASELINE_2026-09-28.md) (Checkpoint #1, merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

**This document does not mark AI-01 complete.** Checkpoint #1 is preserved unchanged; this file
is additive. `PROJECT_STATUS.md` and `MASTER_ROADMAP.md` are intentionally unchanged.

## 1. Git baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp2` |
| Base SHA | `042f4fd615469896fdb36d268a09167ccd06c060` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree at branch creation | clean |

Checkpoint #1 was merged into `main` as `042f4fd docs(ai-01): DSH baseline checkpoint #1`.

## 2. Evidence provenance — read this before the results

**The four verifications in §4 were executed by the human operator in the DSH GUI, not by the agent.**

This is not a formality; it determines what the evidence can support:

- In Checkpoint #1 these four items were classified `BLOCKED` after a documented assessment
  showed DSH exposes no agent-invocable surface (no CLI; loopback requires a session token;
  GUI automation is an uncontrolled interface). See Checkpoint #1 §8.1.
- That assessment **still holds**. Nothing in this checkpoint changes the invocation surface.
- The results below are therefore **operator-executed and operator-reported**. The agent did
  **not** independently reproduce or verify them, and could not have.
- They are recorded as legitimate evidence under this project's human-in-the-loop model
  (the same basis on which the GUI-performed Quit was recorded in Checkpoint #1 §5.4).
- They are recorded **verbatim as reported**. No result was inferred, adjusted, or upgraded.

Any future automation of these four items would need a permitted invocation path that does
not currently exist.

## 3. Environment at Checkpoint #2

| Item | Value |
| --- | --- |
| DSH shell (FileVersion) | `0.1.7-rc.2` — **unchanged** since Checkpoint #1 |
| DSH ProductVersion | `0.1.7.0` |
| DSH processes | 5, running since `2026-09-28 10:32:20` (the Checkpoint #1 restart; no relaunch since) |
| Loopback endpoint | `127.0.0.1:19387` listening (loopback only) |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |

**Version stability check:** DSH is on the `nightly` update channel, which Checkpoint #1
flagged as a baseline-stability risk (limitation #2). At this checkpoint the installed build
is **still `0.1.7-rc.2`** — no background auto-update occurred between Checkpoint #1 and the
manual verification. The nightly risk remains open, but it did not materialise today.

## 4. Manual verification results

All four were run in a **new session** in the SecurityLab workspace of DSH Desktop.
Raw input and raw result are reproduced as reported; status is the operator's classification,
reviewed against the stated expectation.

### 4.1 Agent normal response

```text
INPUT  : 请用一句话说明你当前所在的 workspace。

RESULT : 我当前所在的 workspace 是 D:\SecurityLab（即 SecurityLab
         个人网络安全与车联网安全研究项目根目录）。

STATUS : PASS
```

The agent returned a coherent natural-language answer and correctly identified the bound
workspace path. This confirms the agent starts and completes a turn.

### 4.2 Git inspection

```text
INPUT  : 请执行 git rev-parse HEAD，并只返回命令的实际输出。

RESULT : efa836ff9225f6226ca8a76615f3f45c31110d58

STATUS : PASS
```

The returned SHA **exactly matches** the independently recorded SecurityLab HEAD (§3, §5).
This is a real command result, not a plausible-looking fabrication — the value was
cross-checked against the repository state measured outside DSH.

### 4.3 Workspace read

```text
INPUT  : 请读取 README.md，并概括它的第一段。

RESULT : Agent successfully read SecurityLab README.md and returned the
         first paragraph:

             个人网络安全与车联网安全研究环境。

         It also returned the subsequent project-positioning content.

STATUS : PASS
```

The first paragraph matches `SecurityLab/README.md` as independently read outside DSH,
confirming a genuine file read rather than a generated approximation.

### 4.4 Context loading

```text
INPUT  : 这个项目有哪些研究方向？

RESULT : Agent extracted the research directions from the SecurityLab project
         content, citing README / AGENTS.md and the project directory.

         Directions returned:
           - 网络安全
           - 二进制逆向
           - 固件分析
           - ARM / AArch64
           - Linux / Embedded Linux
           - CAN / SocketCAN
           - ISO-TP
           - UDS
           - 车联网安全
           - 漏洞研究
           - 安全实验自动化

STATUS : PASS
```

> **Scope caveat — what this does and does not prove.**
> This demonstrates that the **DSH agent can retrieve project context from the currently
> bound SecurityLab workspace** (reading repository content and summarising it).
>
> It does **not** demonstrate that a Workbench Context Plugin exists, is implemented, or is
> loaded. No Context plugin has been implemented — Context is a later AI phase and is
> explicitly outside AI-01 scope. Nothing in this result should be read as that plugin being
> present.

## 5. SecurityLab integrity

Read-only discipline was maintained throughout. Independent check outside DSH:

```text
BEFORE manual verification :  branch main, HEAD efa836ff9225f6226ca8a76615f3f45c31110d58
                              git status --short -> 0 lines

AFTER manual verification  :  branch main, HEAD efa836ff9225f6226ca8a76615f3f45c31110d58
                              git status --short -> 0 lines (empty)
```

```text
SecurityLab modified files = 0
```

SecurityLab HEAD is unchanged and matches the value the agent reported in §4.2.
**Note:** the "before" and "after" checks were performed by the agent outside DSH; the
verification session itself ran in the GUI, and its read-only character is evidenced by the
clean post-run status rather than by instrumentation of the session.

## 6. Capability classification (consolidated)

Delta column compares against Checkpoint #1.

| # | Capability | Status | Δ vs CP1 | Evidence |
| --- | --- | --- | --- | --- |
| 1 | DSH installed & version identified | **PASS** | = | §3 |
| 2 | DSH process running | **PASS** | = | §3 |
| 3 | Startup method identified | **PASS** | = | CP1 §5.1 |
| 4 | Local service reachable | **PASS** | = | §3 |
| 5 | Shutdown via window-close | **PASS** | = | CP1 §5.4 |
| 6 | Graceful process termination | **PASS** | = | CP1 §5.4 |
| 7 | Restart / recovery | **PASS** | = | CP1 §5.5 |
| 8 | **Agent starts / normal response** | **PASS** | ▲ BLOCKED → PASS | §4.1 |
| 9 | **Git inspection via agent** | **PASS** | ▲ BLOCKED → PASS | §4.2 |
| 10 | **Workspace read via agent** | **PASS** | ▲ BLOCKED → PASS | §4.3 |
| 11 | **Context retrieval via agent** | **PASS** | ▲ BLOCKED → PASS | §4.4 |
| 12 | Configuration baseline captured | **PASS** | = | CP1 §6 |
| 13 | Plugin loading mechanism identified | **PASS** (config-level) | = | CP1 §6.2 |
| 14 | SecurityLab workspace binding | **PASS** | = | CP1 §7.1 |
| 15 | Controlled read observation | **PASS** | = | CP1 §7.2 B |
| 16 | **SecurityLab integrity** | **PASS** | = | §5 |
| 17 | Read-only enforcement | **FAIL / NOT_IMPLEMENTED** | = | CP1 §7.2 C |
| 18 | OS reboot recovery | **NOT_RUN** | = | never exercised |
| 19 | Clean reinstall | **NOT_RUN** | = | CP1 §4 |
| 20 | Plugin runtime behaviour | **NOT_RUN** | = | needs plugin-level probing |
| 21 | Permission boundary (allowed + blocked) | **NOT_RUN** | = | Guard is AI-04, out of scope |

Items 8–11 moved from `BLOCKED` to `PASS` **solely** because operator-executed evidence now
exists. They were not upgraded on the basis that they "should work".

`Read-only enforcement` remains **FAIL / NOT_IMPLEMENTED** and is unchanged by these results:
the four verifications show the agent *did not* write, which is an observation, not a control
(see Checkpoint #1 §7.2 for the A/B/C distinction). Until Guard exists (AI-04), write
protection rests on human and process discipline.

## 7. Known limitations

Inherited from Checkpoint #1 (§9.2) and still open:

1. **DSH Desktop is GUI-only** — no CLI, no headless mode. The four items in §4 can only be
   executed by a human in the GUI; they cannot be automated or re-run by CI.
2. **Nightly update channel** — the baseline can move under us. Stable today (§3), not guaranteed.
3. **Three-layer versioning** — shell `0.1.7-rc.2` / desktop plugin `2.0.5` / Electron `44.0.0`.
4. **Read-only workspace access unenforced** — the FAIL above.
5. **Python interpreter ambiguity** — `3.14.4` (PowerShell) vs `3.14.5` (Bash/MSYS2).
6. **System Node != DSH Node** — system `v20.12.0`, DSH-bundled `24.18.1`.
7. **No durable startup log** — startup evidence must come from process/port observation.
8. **Window-close is not Quit** — clicking `X` hides to tray.

New in this checkpoint:

9. **Manual results are not reproducible by the agent.** Items 8–11 are one-shot,
   human-executed observations. They cannot be re-verified by any automated means available
   today, so they are evidence of *a* successful run, not of a continuously verified
   capability. Re-validation requires a human each time.
10. **Context scope.** §4.4 shows DSH-native context retrieval, not a Workbench Context
    Plugin. Do not conflate the two.

## 8. AI-01 exit criteria status

| Exit criterion | Status |
| --- | --- |
| Exact tested DSH version recorded | PASS |
| Runtime dependency versions recorded | PASS |
| Clean installation/start procedure documented | BLOCKED — install observed, not re-run |
| Startup/restart behaviour verified | PASS |
| Known-good configuration recorded without secrets | PASS |
| Controlled workspace binding verified | PASS |
| Required baseline Agent behavior verified | PASS (operator-executed, §4) |
| Required plugin/tool behavior verified | **NOT_RUN** — still open |
| Permission boundaries verified | **NOT_RUN** — Guard is AI-04 |
| Evidence record completed | PARTIAL — CP1 + CP2 |
| Reproducible rollback point recorded | PASS (§9) |
| Known limitations classified | PASS (§7) |
| PR reviewed and merged | PENDING |
| PROJECT_STATUS.md updated | **NOT DONE — intentionally** |

**AI-01 remains IN PROGRESS.** The four agent-behaviour items passing does not satisfy
"plugin/tool behavior" or "permission boundaries", both of which are still `NOT_RUN`.

## 9. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `042f4fd615469896fdb36d268a09167ccd06c060` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard 042f4fd615469896fdb36d268a09167ccd06c060` |
| Side effects on DSH | **None** — no DSH configuration was written |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 10. Validation

| Command | Result |
| --- | --- |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `bash -n` on both scripts | PASS |
| CI required-files check | PASS |
| CI secret-file check | PASS — none present |
| `git diff --check` | PASS |

## 11. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-002` |
| Checkpoint | #2 |
| Branch | `baseline/ai-01-dsh-20260928-cp2` |
| Base SHA | `042f4fd615469896fdb36d268a09167ccd06c060` |
| DSH version | `0.1.7-rc.2` |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| AI-01 status | **IN PROGRESS — not complete** |
| Final status | **PARTIAL** — 16 PASS, 1 FAIL, 0 BLOCKED, 4 NOT_RUN, 0 UNKNOWN (of 21) |

**Not implemented in this checkpoint** (per AI-01 §7 and the stated boundary): Context plugin,
Guard plugin, Evidence plugin, Security Tools plugin, Model Router, DeepSeek/MiMo provider
integration, Codex integration, and any AI-02+ work.
