# Fleet v3.0 旧模块处置表

**基线：** `fcbc266f899823db4dbe6f3d521c33fee9d08f1e`
**状态：** 说明性文档；不代表旧模块已删除、迁移或已接入新 Fleet。
**原则：** 不把旧 AI-00–AI-15 的“完成”状态当作 v3.0 已实现；不盲目删除可复用测试/历史证据；
新 Fleet 路径与旧模块显式隔离。

## 1. 处置

| 旧路径 | 处置 | 新架构下的定位 | 本轮动作 |
|---|---|---|---|
| `agents/` | `REFERENCE / LEGACY` | 旧 Agent execution/runtime；新 worker 由 DSH runtime 执行 | 不导入；保留源码与测试；新 Fleet 不把它当作已实现 |
| `providers/` | `DEFER / REFERENCE` | DSH profile/model selection 决定 worker model | 不导入；不复制 provider/router；不调用任何 provider |
| `routing/` | `DEFER / REFERENCE` | 旧 Router v1/v2；新 Fleet 不做模型路由 | 不导入；保留测试/证据；不声称与 Fleet 连接 |
| `composition/` | `ARCHIVE / REFERENCE` | 旧 Workbench 内部层 glue；由 Fleet controller + DSH plugin/API 入口取代 | 不导入；B5 仍 `BLOCKED`；不构造 live Invoker |
| `plugins/guard/` | `REFERENCE` | 旧 Guard 策略语义可参考；新执行边界是 Fleet run policy + MCP server policy | 不导入；避免 Fleet/Guard/MCP 多重互相矛盾的授权器 |
| `plugins/context/` | `REFERENCE` | 旧只读 context；新 MemoryPack/workspace snapshot 是独立边界 | 不导入；不把 context 当长期记忆 |
| `plugins/security_tools/` + `tools/` | `REFERENCE` | 旧通用分发/占位工具；SecurityLab 工具由 MCP server 拥有 | 不导入；不搬 SecurityLab 业务实现进 Fleet |
| `workflows/` | `REFERENCE` | 旧 workflow/approval 状态机经验；Fleet 拥有 run 状态 | 不导入；避免双重 run 状态所有者 |
| `plugins/evidence/` | `UNCHANGED` | durable Evidence/admission gate；AI-15-B/B5 未连接 | 不修改、不绕过；Fleet 不写 Evidence |
| `review/` | `UNCHANGED` | 旧 cross-agent review；新 Verifier 是 worker role | 不修改；不把 review 结果自动当 Evidence |
| `benchmarks/` | `UNCHANGED` | 旧 benchmark；本轮不运行 | 不修改；不声称模型测量 |
| `workspaces/` | `UNCHANGED / REFERENCE` | 旧示例 workspace 配置；新 Fleet 使用独立 workspace registry | 不修改；新 registry 在 `fleet/src/registries/workspaces.ts` |
| `integrations/codex/` | `SEPARATE ASSET` | 外部 Codex reviewer；不是 DSH worker，不是 `AgentId.CODEX` 已接入 | 不导入；不赋予 SecurityLab/Memory/Evidence 权限 |
| `docs/AI-00…AI-15` | `HISTORICAL` | 旧架构历史与证据；v3.0 目标规范是新文档 | 不静默覆盖；新状态见 `FLEET_V3_STATUS.md` |
| `tests/` | `RETAINED` | 旧模块测试与历史证据 | 不删除；本轮只新增 `fleet/test/` 离线 fake tests |
| `.github/` | `UNCHANGED` | 旧 CI；本轮未改 | 不在本轮改 CI |

## 2. 隔离如何被强制

`fleet/test/static-boundary.test.ts` 对 `fleet/src/**/*.ts` 做静态检查：

- 不出现 `process.env` / `process.exit` / `child_process` / 网络 client；
- 不 import `agents/`、`providers/`、`routing/`、`composition/`；
- 不引用 `plugins/evidence`、`EvidenceRecord`、`admit(`、`evidence_store`；
- 文件系统写入只允许出现在 `ledger.ts`（append-only RunLedger）；
- 两个 DSH lifecycle hook 名称保持独立。

`fleet/test/registry.test.ts` 验证 `lab_runner` preset 与 `fleet.securitylab-vcan` plugin
均为 disabled。

## 3. 未做的事

- 没有删除旧模块、旧测试或旧文档。
- 没有把旧模块改写成 Python/TypeScript 双实现。
- 没有在旧目录逐文件加 deprecation banner；本文件是统一处置记录，旧模块保持可审查历史。
- 没有把旧 `agents/`、旧 `providers/` 或旧 `composition/` 当作新 Fleet 已连接。
- 没有把旧 AI-15 Evidence writer/B5 接入新 Fleet。
