# Evidence Lifecycle

## Goal
让 Agent 的工作结果脱离聊天记录后仍可复核、重建和用于 Benchmark。

## Layers
```text
Raw Run Output
    ->
Normalized Evidence Record
    ->
Benchmark Result
    ->
Audit / Review Record
```

## Raw Run Output
原始 stdout/stderr、tool response 和 large logs。可以是 artifact-only，不是唯一事实源。

## Normalized Evidence Record
必须包含 Experiment ID、Agent、Provider/Model、Workspace、Base SHA、Branch、Approval、Tool Calls、Changed Files、Tests、Results、Final Status、Timestamp。
这是 Workbench 的核心持久化事实。

## Retention
- normalized key Evidence: durable
- raw logs: disposable/artifact as appropriate
- AI cache: disposable and rebuildable
- benchmark cases: durable and versioned
- secrets: never stored in Evidence

## Traceability
每条 promoted Evidence 必须回溯到：
```text
Workspace + Branch + Commit SHA + Agent + Provider/Model + Tool execution
```