# AI-01 — DSH Baseline Execution Plan

> Status: **FROZEN**
> Phase: AI-01 — DSH Baseline
> Prerequisite: AI-00 architecture / repository baseline
> Rule: AI-01 is the current active phase. Do not begin AI-02+ implementation before AI-01 exit.

## 1. Purpose

Establish a reproducible, evidence-backed DSH baseline for the Workbench.

AI-01 answers:

- What exact DSH build/version is being used?
- How is it installed and started?
- What configuration is required?
- How is a Workbench workspace attached?
- Which plugin/tool capabilities actually work?
- What is the reproducible rollback point?
- Which behaviors are confirmed, unsupported, or unknown?

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

Establish a clean, repeatable procedure for:

- installation
- dependency setup
- startup
- shutdown
- restart after environment reboot
- configuration persistence

Every command used for the baseline must be recorded.

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

## 6. Exit criteria

AI-01 exits only when all applicable items below are satisfied:

- [ ] Exact tested DSH version recorded
- [ ] Runtime dependency versions recorded
- [ ] Clean installation/start procedure documented
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
