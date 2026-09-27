# Project Status
> Baseline: 2026-09-26

## Current stage
**AI-00 — Requirements / Architecture Freeze**

## Start Here

This file is the single entry point for deciding what to do next.

### Current work item

Finish AI-00 exit prerequisites. Do not start implementation of later phases from memory or from the directory tree.

AI-01 execution plan is frozen at [docs/AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md). It becomes active only after AI-00 exits.

1. Produce and freeze the AI-01 DSH baseline execution plan.
2. Independently verify GitHub `main` branch protection and required checks.
3. After both are complete, close AI-00 and start AI-01.

### Session start sequence

```text
PROJECT_STATUS.md
    -> MASTER_ROADMAP.md (current phase)
    -> current phase requirements / design
    -> git branch / SHA / working tree
    -> task branch
    -> implementation
    -> verification + evidence
    -> PR / approval
    -> merge checkpoint
    -> update PROJECT_STATUS.md
```

### Do not start yet

- AI-02 DeepSeek + MiMo Model Layer
- AI-03 Context Plugin implementation
- AI-04 Guard implementation
- AI-05 Evidence implementation
- AI-06 Security Tools implementation
- AI-07 Router implementation


## Completed

### Repository foundation
- Independent Workbench repository
- Core directory skeleton
- README and roadmap
- Git/security boundary
- Example configuration separated from secrets
- Basic CI preflight
- PR template
- Bootstrap guidance

### Architecture alignment
- AI-00 to AI-14 numbering confirmed against the original Workbench plan; no renumbering was needed.
- Router is explicitly a Workbench core service.
- Terminal and MCP have first-class Tool entry points.
- Long-running workflows have a dedicated layer.
- Evidence lifecycle and retention semantics are documented.
- Project Status is separate from the Roadmap.
- SecurityLab remains an independent workspace.

## Not yet completed
- DSH baseline installation and behavior verification
- Exact supported DSH/Codex versions
- Provider connectivity tests
- Executable Context plugin
- Executable Guard plugin
- Executable Evidence/Audit plugin
- Research tool adapters
- Model Router implementation
- Codex integration
- Benchmark dataset
- Cross-Agent Review implementation
- Long-running workflow implementation

## AI-00 remaining exit items
1. Freeze the AI-01 DSH baseline execution plan.
2. Independently verify GitHub `main` branch protection and required checks through an available authoritative interface.

## Status semantics
`PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN`

Do not turn missing environment, skipped execution, or blocked actions into PASS.