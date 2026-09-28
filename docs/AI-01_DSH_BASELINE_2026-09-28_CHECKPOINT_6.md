# AI-01 — DSH Baseline Checkpoint #6: Current-Build GUI Plugin Evidence

> **Status: COMPLETE — CHECKPOINT #6**
> Experiment ID: `AI-01-DSH-20260928-006`
> Date: 2026-09-28
> Phase: AI-01 — DSH Baseline
> Predecessors: CP1 · CP2 · CP3 · CP4 · CP5 (all merged)
> Plan of record: [AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md)

## 1. Purpose

CP5 recorded criterion #8 (`Required plugin/tool behavior verified`) as `BLOCKED`, and named
one of its unblock conditions as:

> *"a human opens the DSH GUI 插件 panel and reports the loaded plugin list — token-free, GUI,
> on the same basis as the CP2 verification"*

**That condition has now been met.** This checkpoint records the resulting observation,
re-classifies criterion #8, and updates the AI-01 blocker summary.

This checkpoint **only records an observation**. It does not widen it (§4).

> **Revision 2 note.** The operator subsequently confirmed the page identity and observed the
> per-entry enablement states. This revision therefore:
> (a) replaces the earlier, over-conservative "plugin-related panel / capability entries"
> wording with the confirmed identity — the page is explicitly **插件列表** (Plugin List),
> §3.2; and (b) adds the observed **enabled/disabled states**, §3.3.
> The scope exclusions are unchanged, and §4.1's caution about entry #2 is **strengthened**,
> because that entry is now observed as enabled.

## 2. Baseline

| Item | Value |
| --- | --- |
| Branch | `baseline/ai-01-dsh-20260928-cp6` |
| Base SHA | `61cd31de7a6306a82e08cda7aca21c35b42caff9` |
| Base = `origin/main` | Yes (`git rev-list --left-right --count origin/main...HEAD` → `0 0`) |
| Working tree | clean |
| DSH version | **`0.1.7-rc.2`** (FileVersion) / `0.1.7.0` (ProductVersion) |
| DSH run | 5 processes, started `2026-09-28 10:32:20` |
| Loopback | `127.0.0.1:19387` |
| SecurityLab HEAD | `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| Observation reported | `2026-09-28 11:56` (local); enablement states confirmed in revision 2 |
| Observation performed in | the DSH run started `2026-09-28 10:32:20` — i.e. **the current build** |

## 3. The observation

### 3.1 Evidence classification

```text
Evidence class :  Human GUI observation
Run scope      :  current-run   (the DSH instance started 2026-09-28 10:32:20)
UI surface     :  DSH GUI → 插件列表   (the Plugin List page)
```

This is **not** `stale-artifact`, **not** `inferred`, and **not** `config-level`. It is a
human operator's direct reading of a live panel in the running application, reported into
this checkpoint.

It is **not agent-executable evidence.** No agent-invocable surface was used — consistent
with CP4 §5.2, where such a surface was shown to be unreachable, and with the standing
prohibition on the session token.

### 3.2 Panel / UI scope

The operator opened the DSH GUI page whose title is explicitly **插件列表** — the **Plugin
List**.

This is a **confirmed identification**, and it is a correction to how an earlier revision of
this checkpoint described it. It is explicitly **not** a general settings page and **not** a
general experimental-features list. The entries, their descriptions, and their
enabled/disabled state were read off that page.

**What was observed is a UI surface.** The scope of this evidence is exactly that: the Plugin
List page presented these entries and these toggle states. Nothing about how the page is
produced, populated, or backed was observed.

### 3.3 The seven observed entries (verbatim)

Recorded exactly as observed, including the one entry for which the operator reported no
description. **No description has been supplied or invented for it.** Enabled/disabled state
is recorded as displayed.

| # | Entry | Description as displayed | Enabled |
| --- | --- | --- | --- |
| 1 | 智能体团队实验性 | 启用团队协作、团队工具、成员列表和共享任务看板。 | **已开** |
| 2 | 自动授权审查实验性 | 提供自动审查权限模式，由模型在每次工具调用前判断是否授权。 | **已开** |
| 3 | 语音输入实验性 | 在本机使用 SenseVoice 转写录音；首次使用需安装依赖。 | **未开** |
| 4 | 终端 | 限制每条命令最多能跑多久、最多输出多少内容。 | **已开** |
| 5 | Agent 循环 | 控制 Agent 派发工具调用的方式。 | **已开** |
| 6 | 子智能体 | 设置子智能体的递归层级、数量和模型。 | **已开** |
| 7 | 网页搜索 | *(no description reported — recorded as observed, not filled in)* | **已开，但需要设置搜索提供方** |

Four entries carry an `实验性` (experimental) marker; three do not. That distinction is part
of what was displayed and is recorded as such; no meaning is assigned to it here.

### 3.4 Two entries requiring explicit care

#### 3.4.1 Entry 7 — 网页搜索

```text
enabled    = yes
functional = NOT_RUN / not established
dependency = search provider configuration required
```

The page states that a **search provider must be configured**. No provider was configured,
no search was executed, and no result was observed.

> **Entry 7 is NOT recorded as "web search works".** "Enabled" here means only that the
> toggle reads as on in the Plugin List. Functional behaviour is `NOT_RUN` and is not
> established by this observation.

#### 3.4.2 Entry 3 — 语音输入

```text
enabled = no
```

This entry appears in the Plugin List but is **not enabled**.

> **Its presence in the Plugin List must not be read as it being enabled or active.** The
> page also notes that first use requires installing dependencies; that step was not taken.

## 4. Scope limits — what this checkpoint does NOT establish

Per the evidence rule for this checkpoint, the observation is **not** extended to:

- ❌ internal **package names** for any entry
- ❌ specific **plugin IDs** for any entry
- ❌ any **implementation code location** (no file, module or bundle was inspected)
- ❌ whether any entry is provided by a particular **bundle** or by the base profile
- ❌ whether any entry's functionality **executes successfully** — no entry was run
- ❌ **plugin API execution** success for any entry
- ❌ the **plugin loading mechanism** — CP4 §4.1/§4.2 already characterized that separately
  from configuration and stale artifacts; this checkpoint adds nothing to it
- ❌ whether these entries are **plugins** in the sense the profile bundle list uses
  (CP4 §4.1) — the page is a UI surface, and its entries are recorded as displayed

> **This checkpoint establishes exactly this:** the currently running DSH GUI shows a page
> titled **插件列表** (Plugin List) that **presents these seven entries**, with the
> descriptions displayed and the **enablement states** recorded in §3.3. Nothing further is
> claimed. In particular, "enabled" is a **toggle state**, not evidence that the feature
> works or that anything was executed.

### 4.1 A specific caution about entry #2

Entry 2 (自动授权审查实验性 — "automatic authorization review", described as providing an
automatic review permission mode where the model judges whether to authorize before each tool
call) is **permission-adjacent**, and it is now additionally observed as **已开 (enabled)**.

**It still does not change criterion #9, and must not be used to. An enabled toggle is not
enforcement evidence.** Reasons:

- the observed **已开 is a toggle state** on a settings-like page. It shows the feature is
  switched on — *not* that any permission decision has been made, applied, or enforced;
- **no permission decision was exercised, allowed, or denied through it.** No tool call was
  routed through this mode and no allowed/blocked case was produced;
- the entry is marked **实验性** (experimental);
- criterion #9 requires *"allowed + blocked cases"* as **executed** evidence. A toggle state
  is not an executed case — this is exactly the inference CP5 §6.2 warns against, and the
  newly observed "已开" makes that warning *more* important, not less.

Recording this explicitly so that a later reader cannot mistake an enabled toggle for verified
enforcement. Criterion #9 stays exactly as CP5 left it (§6).

## 5. Criterion #8 — `Required plugin/tool behavior verified`

### 5.1 Status change

```text
CP5:  BLOCKED
CP6:  PASS
```

### 5.2 Basis — both halves now have evidence

| Half | Evidence | Status |
| --- | --- | --- |
| **Tool** side | CP2 §4 — response, `git rev-parse HEAD`, `README.md` read, context retrieval (human-executed; SHA and README paragraph cross-checked outside DSH) | **PASS** |
| **Plugin** side | §3 above — current-run human GUI observation of the **插件列表** page: entries, descriptions, and enablement states | **PASS** |

CP5's stated unblock condition was specifically *"a human opens the DSH GUI plugin panel and
reports the loaded plugin list."* Three things are now confirmed:

1. the page is explicitly the **插件列表** (Plugin List), not a generic settings or
   experimental-features page;
2. the plugin entries are **directly observable** in the current running instance;
3. their **enabled/disabled state** is directly observable.

That is the condition CP5 asked for, so the criterion is no longer `BLOCKED`. The tool half
continues to rest on CP2's human-executed evidence.

### 5.3 Mandatory scope qualifier

> **This PASS establishes current-build plugin-list presence and observed enablement state.
> It does not establish execution success or package/source-level identity.**

The criterion asks whether *required plugin/tool behaviour is verified*. It is satisfied at
the level of: *the current build's Plugin List presents these entries with the observed
enablement states, and the agent-level tool behaviours were verified in CP2.* It is **not**
satisfied at the level of naming packages, identifying plugin IDs, locating implementation,
or demonstrating that any plugin's functionality executes — none of which was attempted or is
claimed. No plugin was run; no plugin API was called.

## 6. Criteria #3 and #9 — unchanged

Both remain `BLOCKED`. This checkpoint neither adds evidence to them nor removes any.

### 6.1 Criterion #3 — Clean installation/start procedure

```text
Status: BLOCKED  (unchanged from CP3 §7.2 and CP5 §4)
```

No clean installation was performed, no disposable environment was created, and no
installation artifact was re-obtained. Nothing in §3 bears on installation. The unblock
condition in CP5 §4.4 stands verbatim.

### 6.2 Criterion #9 — Permission boundaries

```text
Status: BLOCKED  (unchanged from CP4 §6 and CP5 §6)
```

| Element | Status |
| --- | --- |
| DSH-native network boundary — blocked cases | **PASS** (CP4 §6.1) |
| DSH-native network boundary — allowed case | **NOT_RUN** |
| Filesystem / workspace enforcement | **UNKNOWN** |
| Filesystem blocked-case | **NOT_RUN** |
| Workbench Guard | **NOT_IMPLEMENTED** (a Workbench statement — *not* a DSH `FAIL`) |

A GUI observation of a plugin panel is not a permission probe. The unblock conditions in
CP5 §6.2 stand verbatim. See §4.1 for why entry #2 in particular must not be read into this
criterion.

## 7. Updated AI-01 blocker summary

| # | Exit criterion | CP5 | CP6 |
| --- | --- | --- | --- |
| 1 | Exact tested DSH version recorded | PASS | PASS |
| 2 | Runtime dependency versions recorded | PASS | PASS |
| 3 | Clean installation/start procedure documented | BLOCKED | **BLOCKED** |
| 4 | Startup/restart behavior verified | PASS | PASS |
| 5 | Known-good configuration recorded without secrets | PASS | PASS |
| 6 | Controlled workspace binding verified | PASS | PASS |
| 7 | Required baseline Agent behavior verified | PASS | PASS |
| 8 | Required plugin/tool behavior verified | BLOCKED | **PASS** ▲ |
| 9 | Permission boundaries verified | BLOCKED | **BLOCKED** |
| 10 | Evidence record completed | PASS | PASS |
| 11 | Reproducible rollback point recorded | PASS | PASS |
| 12 | Known limitations classified | PASS | PASS |
| 13 | PR reviewed and merged | PASS (CP1–CP4) | PASS (CP1–CP5) |
| 14 | PROJECT_STATUS.md updated | NOT_RUN | **NOT_RUN** (withheld) |

```text
CP6 tally: 11 PASS · 0 FAIL · 2 BLOCKED · 1 NOT_RUN · 0 UNKNOWN   (14 criteria)
```

Blockers reduced from **3 → 2**.

## 8. Final AI-01 judgment

```text
AI-01 = BLOCKED
```

**Not COMPLETE:** criteria #3 and #9 remain unmet.

**Not IN PROGRESS:** the two remaining blockers both depend on an external environment or
authorization outside the current safety boundary (CP5 §8.2). No work completable inside the
boundary remains for either.

**No change is made to `PROJECT_STATUS.md`.** The AI-01 completion state may be updated only
on `COMPLETE`, and the judgment is `BLOCKED`.

### 8.1 Remaining blockers and unblock conditions

```text
#3  Clean installation/start procedure    BLOCKED

    1. Provide a disposable / clean Windows environment that does NOT affect
       the current DSH installation.
    2. Copy the verified artifact out of the volatile updater cache into a
       controlled archive, then use it:
         deepseek-harness-0.1.7-rc.2-win-x64.exe
         size 288245480
         sha256 0CF065DC2FC56456448620230581A9072477F0B2562BBC4E1709CDAEDD3CEB86
       (Artifact B, the 2.0.5 plugin installer, still lacks an integrity anchor.)
    3. Actually perform clean install -> start -> workspace/basic validation,
       recording every command and its real result.
    4. Confirm / deny the first-run network dependency.


#9  Permission boundaries                   BLOCKED

    Either:
    (a) explicit authorization for a token-free demonstration of the ALLOWED
        path; or
    (b) explicit authorization to register a disposable scratch workspace,
        enabling a filesystem blocked-case that touches no SecurityLab, system
        directory, credential or remote resource.
```

## 9. Known limitations

All limitations from CP1 §9.2, CP3 §7.2 and CP4 §9 (11–16) and CP5 §11 (17–18) remain open.

Added at this checkpoint:

19. **The plugin evidence is a direct GUI observation of the 插件列表 page, not a runtime
    trace.** It shows what the current build *presents* and what its toggles *read as*, not
    what it *loads* or *executes*. CP4 §4.4's `UNKNOWN` for package-level current-build plugin
    attribution is **not** resolved by this checkpoint — §5.3 states the exact scope.
20. **Enablement state is observed; plugin function is not exercised.** Every entry's
    enabled/disabled state was read from the page, but **no plugin was executed** and no
    plugin functionality was demonstrated. "已开" is a toggle position, not a working feature.
21. **Entry #2 is permission-adjacent and is observed as enabled — this must not be read as
    enforcement** (§4.1). An enabled toggle is not an executed allowed/blocked case. The risk
    of that misreading is high enough to record as a standing limitation.
22. **Entry 7 (网页搜索) is enabled but functionally unverified.** It reports that a search
    provider must be configured; none was configured and no search was run. `enabled = yes`,
    `functional = NOT_RUN`. It must not be cited as "web search works".
23. **Entry 3 (语音输入) is disabled.** It appears in the Plugin List but is `未开`. Its
    presence in the list is not evidence that it is enabled or active.
24. **The evidence is a single human observation.** It is not reproducible by the agent and
    was not captured as a screenshot or log; it rests on the operator's report, as CP2 did.

## 10. Boundary integrity

| Invariant | Result |
| --- | --- |
| SecurityLab tree unchanged | **PASS** — `git status --short` empty (0 files) |
| SecurityLab HEAD unchanged | **PASS** — `efa836ff9225f6226ca8a76615f3f45c31110d58` |
| Workbench `main` unmodified | **PASS** — work on a branch |
| `PROJECT_STATUS.md` unmodified | **PASS** — deliberately not touched (§8) |
| No DSH modification | **PASS** — no install/uninstall, no config change, no process action |
| No plugin installed, uninstalled, enabled or executed | **PASS** — observation only |
| No experimental feature toggled | **PASS** |
| No CLI executed | **PASS** |
| No credential or token access | **PASS** |
| No Context / Guard / Evidence / Security Tools / tool adapter / Model Router implemented | **PASS** |
| No AI-02 work started | **PASS** |

## 11. Rollback point

| Item | Value |
| --- | --- |
| Rollback ref | `61cd31de7a6306a82e08cda7aca21c35b42caff9` (`origin/main`) |
| Rollback action | `git checkout main && git reset --hard 61cd31de7a6306a82e08cda7aca21c35b42caff9` |
| Side effects on DSH | **None** — no DSH state modified |
| Side effects on SecurityLab | **None** — 0 modified files |

Documentation-only checkpoint.

## 12. Validation

| Command | Result |
| --- | --- |
| `git diff --check` | PASS — no whitespace errors |
| `bash scripts/bootstrap/preflight.sh` | PASS |
| `bash tests/unit/test_repository_layout.sh` | PASS |
| `git status` | clean except the new document |
| `git diff --stat` | 1 file added |
| `git rev-parse HEAD` | recorded in §13 |
| Diff scope | only `docs/AI-01_DSH_BASELINE_2026-09-28_CHECKPOINT_6.md` |

## 13. Final status

| Field | Value |
| --- | --- |
| Experiment ID | `AI-01-DSH-20260928-006` |
| Checkpoint | #6 |
| Branch | `baseline/ai-01-dsh-20260928-cp6` |
| Base SHA | `61cd31de7a6306a82e08cda7aca21c35b42caff9` |
| DSH version | `0.1.7-rc.2` (current build, run started `2026-09-28 10:32:20`) |
| Evidence class | `Human GUI observation` / current-run |
| UI surface | DSH GUI → **插件列表** (Plugin List) |
| Entry enablement observed | 6 enabled, 1 disabled (`语音输入实验性` = 未开) |
| Exit checklist | **11 PASS · 0 FAIL · 2 BLOCKED · 1 NOT_RUN · 0 UNKNOWN** |
| Criterion #8 | **PASS** (was BLOCKED) — scope per §5.3 |
| Criteria #3, #9 | **BLOCKED** (unchanged) |
| **AI-01 final judgment** | **BLOCKED** |
| `PROJECT_STATUS.md` | **unchanged** |
| AI-02 | **NOT STARTED** |
