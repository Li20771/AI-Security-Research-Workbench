# Project Status
> Baseline: 2026-09-26

## Current stage
**AI-01 — DSH Baseline**

AI-00 architecture and repository baseline is complete. The GitHub `main` branch protection requirement is **BLOCKED** by the current GitHub Free/private-repository plan and is retained as a documented platform limitation; it is not treated as a PASS.

## Start Here

This file is the single entry point for deciding what to do next.

### Current work item

**AI-01 — DSH Baseline**

The AI-01 execution plan is frozen at [docs/AI-01_DSH_BASELINE_EXECUTION_PLAN.md](AI-01_DSH_BASELINE_EXECUTION_PLAN.md).

### Session start sequence

```text
PROJECT_STATUS.md
    -> MASTER_ROADMAP.md (current phase)
    -> AI-01_DSH_BASELINE_EXECUTION_PLAN.md
    -> verify branch / SHA / working tree
    -> create AI-01 task/experiment ID
    -> baseline execution
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

## AI-00 final gate status

- Architecture / repository baseline: **PASS**
- AI-01 execution plan: **PASS / FROZEN**
- GitHub `main` branch protection: **BLOCKED** — current GitHub Free/private-repository plan does not enforce repository rulesets.

This platform limitation is documented and is not converted to PASS.

## Status semantics
`PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN`

Do not turn missing environment, skipped execution, or blocked actions into PASS.