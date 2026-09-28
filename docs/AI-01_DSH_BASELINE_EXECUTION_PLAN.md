# AI-01 — DSH Baseline Execution Plan

> Status: **FROZEN** (amended 2026-09-28 — exit criteria redefined, see §6.1 and §9)
> Phase: AI-01 — DSH Baseline
> Prerequisite: AI-00 architecture / repository baseline
> Rule: AI-01 is the current active phase. Do not begin AI-02+ implementation before AI-01 exit.

## 1. Purpose

Establish an **actually verified, evidence-backed DSH baseline** for the Workbench.

AI-01 records the DSH baseline that was tested, on the host where it was tested, with
execution evidence behind each claim. It is a record of verified present state — not a
portability guarantee and not a support commitment.

AI-01 answers:

- What exact DSH build/version was tested?
- How is it installed and started on the verified host?
- What configuration is required?
- How is a Workbench workspace attached?
- Which plugin/tool capabilities actually work?
- What is the reproducible rollback point?
- Which behaviors are confirmed, unsupported, or unknown?

### 1.1 Scope boundary — what AI-01 does and does not claim

AI-01 validates the **current DSH baseline**, not universal cross-machine support.

- **In scope:** exact tested DSH version, installation method and startup on the verified host,
  configuration, workspace binding, plugin/tool capability, permission boundary, recovery,
  evidence, and rollback point.
- **Not an AI-01 exit requirement:** reinstalling the same DSH version on a *different* clean
  Windows machine and demonstrating full reproduction. That is **deployment / reproducibility
  work**, deferred — see §6.1 and §9.
- AI-01 does **not** claim that DSH is reproducible across arbitrary Windows environments, and
  does **not** claim that the Workbench runs on any Windows host.

No model integration, routing implementation, plugin implementation, or SecurityLab production change belongs in AI-01.

## 2. Scope

### 2.1 Runtime baseline

Record the exact tested versions and environment for:

- DSH
- OS / distribution
- Python
- Node / npm, when required by DSH
- Docker, when required
- Git
- other runtime dependencies actually used by DSH

Do not document a version as supported until it has been tested.

### 2.2 Installation and startup

Record the installation and startup procedure **as actually observed and executed on the
verified host**:

- installation
- dependency setup
- startup
- shutdown
- restart after environment reboot
- configuration persistence

Every command used for the baseline must be recorded.

**Documenting this procedure is required. Proving that it reproduces on a different clean
machine is not part of AI-01** — see §6.1. The recorded procedure is evidence about the tested
host and the tested version, not a portability claim.

### 2.3 Configuration baseline

Freeze the minimum known-good configuration:

- primary Agent role
- workspace mode
- permission defaults
- plugin loading mechanism
- tool availability
- provider configuration shape without committing secrets

Secrets remain runtime-only.

### 2.4 Workspace baseline

Verify a controlled workspace can be attached.

First target:

- SecurityLab as an external workspace
- read-only / controlled access by default
- no hard-coded SecurityLab implementation inside DSH

### 2.5 Capability baseline

Verify actual behavior, not documentation claims.

| Capability | Required evidence |
| --- | --- |
| Agent starts | startup log / health evidence |
| Workspace access | successful controlled read |
| Git inspection | actual command/result |
| Tool invocation | actual tool call/result |
| Plugin loading | actual plugin behavior |
| Permission boundary | allowed + blocked cases |
| Context loading | actual context retrieval |
| Recovery | stop/restart and recovery evidence |

Each item is classified as PASS, FAIL, BLOCKED, NOT_RUN, or UNKNOWN.

## 3. Baseline security boundary

AI-01 remains inside the existing Workbench security boundary:

- main branch is not a default Agent work branch
- no force push or history rewrite
- no secrets in Git
- no real CAN / ECU / vehicle access
- no uncontrolled remote execution
- no destructive system changes
- Guard remains authoritative for permission decisions

## 4. Execution sequence

```text
1. Read PROJECT_STATUS.md
2. Confirm AI-01 is the current phase
3. Read this plan and AI-00 architecture constraints
4. Record branch + base SHA + working tree
5. Create AI-01 task/experiment ID
6. Capture environment/version inventory
7. Install or confirm DSH baseline
8. Capture exact configuration
9. Start DSH
10. Verify core Agent behavior
11. Verify workspace behavior
12. Verify plugin/tool behavior
13. Verify permission boundaries
14. Verify restart/recovery
15. Record Evidence
16. Freeze reproducible baseline
17. Review diff and evidence
18. Open PR
19. Merge checkpoint
20. Update PROJECT_STATUS.md
```

## 5. Evidence requirements

The AI-01 baseline record must contain at minimum:

- Experiment ID
- DSH version
- environment versions
- installation method
- startup method
- configuration reference
- workspace reference
- branch
- base SHA
- validation commands
- validation results
- known limitations
- rollback point
- final status

No claim of support is valid without corresponding execution evidence.

### 5.1 What this evidence does and does not mean

- **Installer identity is version-specific evidence.** The recorded artifact identity
  (filename, size, hash, signature) applies to the tested build only.
- **This is not a universal support claim.** Nothing in this plan asserts that the Workbench —
  or DSH itself — works on arbitrary Windows environments.
- **Future DSH upgrades require a new baseline verification.** DSH is an external, continuously
  updated platform; once it changes materially, the recorded baseline no longer describes it.
  See §9.

## 6. Exit criteria

AI-01 exits only when all applicable items below are satisfied:

- [ ] Exact tested DSH version recorded
- [ ] Runtime dependency versions recorded
- [ ] Clean installation/start procedure **documented**
- [ ] Startup/restart behavior verified
- [ ] Known-good configuration recorded without secrets
- [ ] Controlled workspace binding verified
- [ ] Required baseline Agent behavior verified
- [ ] Required plugin/tool behavior verified
- [ ] Permission boundaries verified
- [ ] Evidence record completed
- [ ] Reproducible rollback point recorded
- [ ] Known limitations classified
- [ ] PR reviewed and merged
- [ ] PROJECT_STATUS.md updated

### 6.1 Clean installation — what is required, and what is not

```text
Documented installation/start procedure                    = REQUIRED for AI-01 exit
Clean-room reinstallation on ANOTHER machine, with full
reproduction demonstrated                                  = NOT REQUIRED FOR AI-01 EXIT
```

An earlier reading of this phase implied that AI-01 required demonstrating baseline
reproduction **from a clean environment on a different machine**. That requirement is
**removed** from the exit criteria and reclassified as deferred **deployment / reproducibility
validation**.

The reason is environmental, not a relaxation of evidence standards: this host provides no
clean, disposable Windows environment, established by direct investigation (CP7, CP9, CP10,
CP11). That finding remains `BLOCKED` — it is simply no longer a gate on AI-01.

> The deferred item **must not** be recorded as `PASS`, and no claim of cross-machine
> reproducibility may be derived from it.

## 7. Explicit non-goals

AI-01 does not:

- implement DeepSeek or MiMo integration
- implement Context / Guard / Evidence plugins
- implement Security Tools adapters
- implement Model Router
- implement Codex integration
- implement Benchmark
- implement long-running workflows
- modify SecurityLab production code

## 8. Definition of ready for AI-02

AI-02 may start only after AI-01 is marked complete in PROJECT_STATUS.md and its exit criteria are satisfied.

The AI-02 starting point must be the merged AI-01 baseline commit.

## 9. Baseline maintenance model

- **DSH is an external, moving dependency.** It updates on its own schedule and is not
  version-pinned by the Workbench.
- **The Workbench does not guarantee indefinite support for every future DSH build.** The
  baseline describes a tested build; it is not a promise about builds that do not exist yet.
- **When DSH is upgraded materially, run a new DSH baseline checkpoint.** A new checkpoint
  produces a new baseline record; it never retroactively alters an earlier one.
- **Previous evidence remains historical evidence.** Earlier checkpoints stay valid for the
  build and host they describe, and are not rewritten.
- **Clean-room installation is deferred, not cancelled.** It can be taken up later as
  deployment / reproducibility work when a suitable environment exists.

```text
AI-01 records a verified baseline, not a permanent DSH version support commitment.
```
