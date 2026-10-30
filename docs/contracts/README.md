# DSH Agent Fleet v3.0 — 共享接口契约

**契约版本：** Fleet API `1.0.0`；MemoryPack `1.1.0`
**冻结日期：** `2026-10-30`
**状态：** `FROZEN`（三仓库共享基线；Workbench / dsh-memory / SecurityLab）
**实现性质：** fake-only。真实 DSH SDK/runtime、provider/model、SecurityLab/vcan/设备实验均为 `NOT_RUN`。

本目录是 Workbench 仓库中的**正式契约**；同一份文件必须原样镜像到
`D:\claude-work\DSH-Fleet-v3\brief\contracts\`，供 dsh-memory 与 SecurityLab 会话读取。
两个位置必须逐字节一致；任何跨仓库字段、枚举、错误码或权限语义变化，必须同时更新：

1. 本目录的 Markdown；
2. 本目录的 JSON Schema / examples；
3. `brief\contracts\` 的镜像；
4. 三个仓库中消费该契约的代码与测试。

版本不一致时，消费方必须拒绝（fail closed），不得“尽力兼容”。

## 1. 文件

| 文件 | 用途 | 版本 |
|---|---|---|
| `FLEET_API_V1.md` | Fleet 公共 API、可信绑定、workflow/role/preset、状态机、结果信封、错误码 | 1.0.0 |
| `MEMORYPACK_V1.md` | dsh-memory 只读 MemoryPack（历史版本，保留不复写） | 1.0.0 |
| `MEMORYPACK_V1_1.md` | dsh-memory 只读 MemoryPack：显式 visibility、Unicode/NFC 路径、迁移清单 | 1.1.0 |
| `SECURITYLAB_MCP_V1.md` | SecurityLab MCP 只读工具面、路径限制、输出限制、disabled vcan | 1.0.0 |
| `RUN_LEDGER_V1.md` | append-only RunLedger、事件、哈希链、字段禁令 | 1.0.0 |
| `DSH_SDK_ADAPTER_V1.md` | DSH SDK runtime adapter 接口与两个独立 lifecycle hook | 1.0.0 |
| `fleet-submit-request.v1.schema.json` | `fleet.submit` 请求 | 1.0.0 |
| `fleet-status-query.v1.schema.json` | `fleet.status` 查询 | 1.0.0 |
| `fleet-submit-response.v1.schema.json` | `fleet.submit` 响应 | 1.0.0 |
| `fleet-status-response.v1.schema.json` | `fleet.status` 响应 | 1.0.0 |
| `fleet-result-response.v1.schema.json` | `fleet.result` 响应 | 1.0.0 |
| `fleet-cancel-response.v1.schema.json` | `fleet.cancel` 响应 | 1.0.0 |
| `worker-result.v1.schema.json` | worker 输出 payload（不可信数据） | 1.0.0 |
| `run-ledger.v1.schema.json` | RunLedger 单事件 | 1.0.0 |
| `workflow-registry.v1.schema.json` | 固定 workflow registry 文档 | 1.0.0 |
| `role-preset.v1.schema.json` | 固定 role/preset registry 文档 | 1.0.0 |
| `memorypack.v1.schema.json` | MemoryPack 文档（历史版本） | 1.0.0 |
| `memorypack.v1.1.schema.json` | MemoryPack 文档（当前版本） | 1.1.0 |
| `securitylab-tool-call.v1.schema.json` | SecurityLab MCP 调用 | 1.0.0 |
| `securitylab-tool-result.v1.schema.json` | SecurityLab MCP 结果 | 1.0.0 |
| `examples/` | 与上述 schema 对应的示例 | 1.0.0 / 1.1.0 |

## 2. 共同安全前提

- 身份（`workflow_instance_id`、`task_id`、`run_id`、`role`、`preset_version`、
  `workspace_id`、`episode_id`、`tool_profile`、`approval_ref`、MemoryPack snapshot）
  由可信 host 绑定，**不接受模型从 prompt、JSON 参数或 MCP 参数自报**。
- 调用参数只能缩小范围，不能扩大角色、workspace、工具、审批或记忆可见性。
- 未登记、缺失、非法、disabled、版本不匹配一律 fail closed：拒绝创建 run，
  或返回 `blocked`；不降级为更高权限，不静默回退到默认 workspace/role。
- 模型输出是不可信数据：不能修改 preset/role/workspace/tool allowlist/approval，
  不能直接写共享记忆，也不能成为 Evidence。
- RunLedger、dsh-memory、Evidence 是三个不同数据边界；worker 结果不是 Evidence。
- `lab_runner` 与 `securitylab_vcan` 默认 disabled；本轮不运行任何虚拟/真实实验。
- 真实 DSH SDK/runtime、provider/model、SecurityLab/vcan 连接均为 `NOT_RUN`。

## 3. 版本与同步规则

- Fleet API 契约版本：`1.0.0`。MemoryPack 是独立组件版本：当前 `1.1.0`
  （`MEMORYPACK_V1_1.md` / `memorypack.v1.1.schema.json`），v1.0.0 保留为历史。
  消费者不得假定所有组件版本号相同，必须按各自 `contract_version` 校验。
- 破坏性变化提升主版本；新增可选字段提升次版本；仅澄清文字提升补丁版本。
- 任何版本变化必须同步 `brief\contracts\`，并在交付报告中写明旧/新版本和影响仓库。
- 消费方读取到未知 `contract_version` 时必须拒绝，不得猜测字段语义。

## 4. 状态用语

- `IMPLEMENTED`：代码与离线 fake 测试已实现。
- `IMPLEMENTED BUT NOT CONNECTED`：接口/适配器已实现，但未连接真实 DSH/MCP/Memory 服务。
- `BLOCKED`：前置条件缺失，无法执行。
- `NOT_RUN`：本轮未执行；不得填写推测结果。
- fake 测试通过不等于真实 runtime/provider/MCP/实验通过。
