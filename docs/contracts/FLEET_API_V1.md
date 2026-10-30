# Fleet Public API v1

**契约 ID：** `dsh-fleet.fleet-api`
**版本：** `1.0.0`
**状态：** `FROZEN`（2026-10-30）
**实现状态：** `IMPLEMENTED`（fake-only）；真实 DSH SDK/runtime 为 `NOT_RUN`。
**消费者：** DSH Main、Workbench Fleet 宿主、三个仓库的 contract tests。

本文件定义 DSH Main 能调用的**全部** Fleet 操作。不存在通用 `run_agent`、任意命令、
任意路径、自由角色或任意工具执行 API。

## 1. 身份与可信绑定

### 1.1 身份对象

| 对象 | 含义 | 绑定方 |
|---|---|---|
| `workflow_instance_id` | 一次工作流实例，聚合同一流程的多个 task run | host |
| `task_id` | 工作流内固定任务 | workflow registry |
| `run_id` | 一次 worker 执行；重试必须生成新 id | Fleet |
| `parent_run_id` | 依赖或重试来源；首次为 `null` | host / Fleet |
| `role` | `orchestrator` / `researcher` / `vehicle_analyst` / `challenger` / `evidence_verifier` / `lab_runner` | role registry |
| `preset_id` + `preset_version` | 不可在 run 中静默变化的 Agent preset | preset registry |
| `workspace_id` / `episode_id` | 获准访问的项目与阶段范围 | host + workspace registry |
| `tool_profile` | 允许的 MCP server/tool 集合 | preset registry |
| `memory_pack` | 只读 MemoryPack snapshot 引用 | dsh-memory |
| `approval_ref` | 高影响操作审批引用；不得跨 run/目标泛化 | approval verifier |
| `session_id` | DSH runtime session；不是 workflow/run 身份 | runtime adapter |

### 1.2 TrustedBinding

`binding` 是 host 侧签发、Fleet 内部验证的不可伪造对象，**不是**请求体字段：

```json
{
  "binding_id": "bind_0123456789abcdef0123456789abcdef",
  "issued_at": "2026-10-30T00:00:00.000Z",
  "workflow_instance_id": "wfi_0123456789abcdef0123456789abcdef",
  "workspace_id": "ws_a",
  "episode_id": "ep_1",
  "role": "researcher",
  "preset_id": "preset_researcher",
  "preset_version": "1.0.0",
  "tool_profile": "researcher_ro_v1",
  "memory_pack": {
    "snapshot_id": "mp_0123456789abcdef0123456789abcdef",
    "snapshot_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "workspace_id": "ws_a",
    "episode_id": "ep_1"
  },
  "approval_ref": null,
  "base_sha": null,
  "max_budget": { "max_tokens": 4000, "max_cost_usd": 0.10 },
  "max_timeout_ms": 120000
}
```

规则：

- `binding_id` 由 host 签发，Fleet 用**进程内不可伪造的签发注册表**（opaque identity registry）
  验证；普通 JSON 对象、深拷贝、重新序列化后的对象都不是可信绑定。
- 绑定字段只能由 host 设置；请求参数、prompt、MCP 参数都不能覆盖。
- `preset_id/preset_version` 必须与 `role` 的 enabled preset 完全一致。
- `tool_profile` 必须等于该 preset 的 `tool_profile`。
- `workspace_id` 必须已登记且 enabled；`episode_id` 缺失时为 `null`。
- worker 角色（`researcher`、`vehicle_analyst`、`challenger`、`evidence_verifier`、
  `lab_runner`）在 v1 必须携带非空 `memory_pack`；缺失时 `fleet.submit` 返回
  `memory-pack-required`，不创建 run。
- `memory_pack.workspace_id` 必须等于绑定 workspace；`snapshot_id`/`snapshot_hash`
  格式合法。跨 workspace pack 一律拒绝。
- `base_sha` 为 40 或 64 位十六进制，或 `null`。
- `max_budget` / `max_timeout_ms` 是绑定上限；请求只能进一步缩小，不能扩大。
- `binding` 不写入 RunLedger 原文；ledger 只记录其安全元数据字段。

## 2. 公共 API 面

对 DSH Main 只暴露四个固定操作：

```text
fleet.submit(request, binding) -> SubmitResponse
fleet.status(query, binding)   -> StatusResponse
fleet.result(run_id, binding)  -> ResultResponse
fleet.cancel(run_id, binding)  -> CancelResponse
```

响应统一信封（各操作有独立 JSON Schema）：

```json
{
  "contract_version": "1.0.0",
  "ok": true,
  "operation": "submit",
  "data": { },
  "error": null
}
```

- `ok: true` 时必须有 `data`，`error` 为 `null` 或缺省。
- `ok: false` 时必须有 `error`，`data` 可省略；拒绝不产生 run。
- 所有字符串字段不得包含 NUL；错误信息不得包含 credential、token、完整环境或 prompt。

## 3. `fleet.submit`

### 3.1 请求

```json
{
  "contract_version": "1.0.0",
  "workflow_id": "research",
  "task_id": "analysis_a",
  "input": { "brief": "…", "scenario": "…" },
  "parent_run_id": null,
  "deadline_ms": 60000,
  "budget": { "max_tokens": 1000, "max_cost_usd": 0.0 }
}
```

| 字段 | 必填 | 规则 |
|---|---|---|
| `contract_version` | 是 | const `1.0.0` |
| `workflow_id` | 是 | 固定枚举，见 §7 |
| `task_id` | 是 | 该 workflow 内固定 task |
| `input` | 是 | JSON object；canonical JSON ≤ 16 KiB；内容不可信，不写入 ledger |
| `parent_run_id` | 否 | `run_…` 或 `null`；用于依赖或重试，见 §3.4 |
| `deadline_ms` | 否 | 1..86400000；不得超过 preset/绑定上限 |
| `budget` | 否 | `{max_tokens, max_cost_usd}`；不得超过 preset/绑定上限 |

**禁止出现在请求顶层的字段**（出现即 `identity-in-request`，拒绝且不创建 run）：
`workflow_instance_id`、`role`、`workspace_id`、`episode_id`、`preset_id`、
`preset_version`、`tool_profile`、`approval_ref`、`memory_pack`、
`memory_pack_snapshot_id`、`env`、`environment`、`command`、`path`、`session_id`、
`run_id`、`allowed_tools`、`tools`、`mcp_server`、`model`、`provider`、`shell`、
`python`、`credentials`、`token`。

`input` 内部可以包含任意任务文本；它始终是不可信内容，Fleet 不会把其中的
`role`/`workspace_id` 等键解释为身份。

### 3.2 验证顺序（任何一步失败都 fail closed）

1. 验证 `binding` 是可信签发对象；否则 `untrusted-binding`。
2. 验证请求 schema、禁止字段、JSON 大小；否则 `invalid-request` / `identity-in-request`。
3. 验证 workflow 存在且 enabled；否则 `unknown-workflow` / `workflow-disabled`。
4. 验证 task 存在；否则 `unknown-task`。
5. 验证绑定 role 在 task 的 `allowed_roles` 中；`lab_runner` 在 v1 为 disabled，
   因此 `security_audit.validation` 与 `lab_validation.suite_run` 在 role 检查处被拒绝。
6. 验证 role/preset 登记、版本匹配、preset enabled、插件 manifest 全部登记且 enabled；
   否则 `unknown-role` / `role-disabled` / `preset-mismatch` / `preset-disabled` /
   `plugin-unregistered` / `plugin-disabled`。
7. 验证 workspace 登记且 enabled、该 role 在 workspace 允许范围内；否则
   `workspace-unknown` / `workspace-disabled` / `workspace-role-denied`。
8. worker 角色验证 MemoryPack 存在且 workspace 匹配；否则 `memory-pack-required` /
   `memory-scope-mismatch`。
9. 验证 approval（仅 `requires_approval` 的 task/preset）；否则
   `approval-required` / `approval-denied`；verified `pending` 进入 `waiting_approval`。
10. 验证并发上限；否则 `concurrency-limit`。
11. 验证 deadline/budget 不超过 preset 与绑定上限；否则
    `deadline-exceeds-preset` / `budget-exceeds-preset`。
12. 验证 parent run（依赖/重试语义）；否则 `parent-not-found` / `parent-not-terminal` /
    `dependency-not-satisfied` / `invalid-parent-run`。
13. 生成新 `run_id`，写 append-only ledger，创建 run。

拒绝时写 `request.rejected` ledger 事件（`run_id: null`），但不创建 run。
不可信绑定被拒绝时，不记录 role/workspace 等未验证字段。

### 3.3 响应

```json
{
  "contract_version": "1.0.0",
  "ok": true,
  "operation": "submit",
  "data": {
    "workflow_instance_id": "wfi_0123456789abcdef0123456789abcdef",
    "run_id": "run_0123456789abcdef0123456789abcdef",
    "status": "queued",
    "accepted_at": "2026-10-30T00:00:00.000Z"
  }
}
```

- worker 提交成功后返回 `queued`（执行异步开始）。
- `single` 直接返回 `completed`，不创建 session、不启动 worker。
- 有效但 pending 的 approval 返回 `waiting_approval`；v1 冻结 registry 中
  所有 `requires_approval` task 都属于 disabled `lab_runner`，因此该路径
  在本轮不可达，但状态与实现保留给未来单独授权的 registry 版本。

### 3.4 parent run、依赖与重试

- task 的 `depends_on` 非空时，必须提供 `parent_run_id`。parent 必须同一
  `workflow_instance_id`、同一 workspace；parent 属于 `depends_on` 时还必须
  `completed`，否则 `dependency-not-satisfied`。parent 与当前 task 相同且处于终态时
  视为重试（见下一条），不要求属于 `depends_on`。
- parent 与当前 task 相同表示重试：parent 必须处于终态且 role 相同；重试生成
  **新 `run_id`**，原始 run 记录与 ledger 事件保留，不覆盖。parent 非终态 ->
  `parent-not-terminal`；role 不同 -> `invalid-parent-run`。
- parent 既不是依赖 task、也不是同 task 重试 -> `invalid-parent-run`。
- parent 不存在或不在绑定 workspace -> `parent-not-found`（不泄露其他 workspace 的存在性）。

## 4. `fleet.status`

查询必须是以下之一：

```json
{ "contract_version": "1.0.0", "run_id": "run_…" }
```

```json
{
  "contract_version": "1.0.0",
  "workflow_instance_id": "wfi_…",
  "task_id": "analysis_a"
}
```

- 不接受空查询或无界列表；至少一个选择器。
- 绑定 workspace 之外、或绑定 role 无权查看的 run 一律返回 `run-not-found`，
  不泄露存在性、状态、时间或结果引用。
- `orchestrator` 可查看同一 workspace 内的所有 run；worker 角色只能查看同 role 的 run。
- 响应中的 `runs[]` 只包含安全元数据，不含 prompt、input、credential、完整模型过程。

`RunSummary` 字段：

```json
{
  "run_id": "run_…",
  "workflow_instance_id": "wfi_…",
  "workflow_id": "research",
  "task_id": "analysis_a",
  "parent_run_id": null,
  "role": "researcher",
  "preset_id": "preset_researcher",
  "preset_version": "1.0.0",
  "workspace_id": "ws_a",
  "episode_id": "ep_1",
  "status": "completed",
  "created_at": "2026-10-30T00:00:00.000Z",
  "updated_at": "2026-10-30T00:01:00.000Z",
  "session_id": "dshsess_…",
  "result_ref": "result://run_…",
  "result_sha256": "…",
  "cleanup_state": "succeeded",
  "reason_code": null,
  "reason": null
}
```

## 5. `fleet.result`

- 只能读取终态 `completed` 的 run。
- 非终态 -> `result-not-ready`；终态非 `completed` -> `result-not-available`。
- `single` 没有 worker result，返回 `result-not-available`。
- 结果 JSON 必须已通过 `worker-result.v1` 与 role-specific 校验；否则该 run 不会
  进入 `completed`（见 §8）。
- 返回信封中的 `untrusted: true`、`admission: "none"`、`evidence: false` 是常量：
  worker 输出不是 Evidence，也不能自动进入共享记忆。

```json
{
  "contract_version": "1.0.0",
  "ok": true,
  "operation": "result",
  "data": {
    "run_id": "run_…",
    "status": "completed",
    "result_ref": "result://run_…",
    "result_sha256": "…",
    "untrusted": true,
    "admission": "none",
    "evidence": false,
    "result": {
      "contract_version": "1.0.0",
      "schema_id": "worker-result.v1",
      "run_id": "run_…",
      "role": "researcher",
      "received_at": "2026-10-30T00:01:00.000Z",
      "untrusted": true,
      "admission": "none",
      "evidence": false,
      "payload_sha256": "…",
      "payload": { }
    },
    "artifacts": []
  }
}
```

## 6. `fleet.cancel`

- 可取消状态：`queued`、`waiting_approval`、`running`。
- 终态 run -> `run-not-cancellable`，状态不变。
- `waiting_approval` / 尚未打开 session 的 `queued`：无需 runtime，直接
  `cancelled`，`cleanup.state = "not_needed"`。
- `running`：必须传播到对应 session/process，并检查关闭结果。
  - cleanup 成功 -> `cancelled`，`cleanup.state = "succeeded"`。
  - cleanup 失败/无法确认 -> **`blocked`**，`cleanup.state = "failed" | "unknown"`；
    不得伪装为 `cancelled`，不得复用该 session。
- 取消与 timeout 竞争时只允许一个终态；后到者不得覆盖。
- 响应：

```json
{
  "contract_version": "1.0.0",
  "ok": true,
  "operation": "cancel",
  "data": {
    "run_id": "run_…",
    "status": "cancelled",
    "cleanup": { "state": "succeeded", "detail": null }
  }
}
```

## 7. 状态机

```text
created -> validated -> queued -> running
   |          |             |        |-> completed
   |          |             |        |-> failed
   |          |             |        |-> blocked
   |          |             |        |-> timed_out
   |          |             |        |-> cancelled
   |          |             |-> cancelled | blocked
   |          |-> waiting_approval -> queued | running | cancelled | blocked
   |          |-> completed（仅 single）
   |          |-> cancelled | blocked
   |-> cancelled | blocked
```

- 终态：`completed` / `failed` / `blocked` / `timed_out` / `cancelled`。
- 任何终止都必须伴随 `run.cleanup`（如果打开过 session）与终态 ledger 事件。
- `completed` 但 session close 失败 -> `blocked`（`cleanup-failed`），结果不暴露。
- timeout 但 cleanup 失败 -> `blocked`，`cleanup_state = "failed"`。
- 重试永远是新 `run_id`；终态记录不修改。

## 8. Workflow / task registry（v1 冻结）

| workflow | 状态 | task | allowed roles | 依赖 | 审批 | worker |
|---|---|---|---|---|---|---|
| `single` | enabled | `main` | `orchestrator` | — | 否 | 否 |
| `research` | enabled | `analysis_a` | `researcher` | — | 否 | 是 |
| `research` | enabled | `analysis_b` | `vehicle_analyst` | — | 否 | 是 |
| `research` | enabled | `challenge` | `challenger` | `analysis_a` | 否 | 是 |
| `research` | enabled | `verify` | `evidence_verifier` | `challenge` | 否 | 是 |
| `design_review` | enabled | `design` | `vehicle_analyst` | — | 否 | 是 |
| `design_review` | enabled | `challenge` | `challenger` | `design` | 否 | 是 |
| `design_review` | enabled | `verify` | `evidence_verifier` | `challenge` | 否 | 是 |
| `security_audit` | enabled | `analysis` | `researcher`, `vehicle_analyst` | — | 否 | 是 |
| `security_audit` | enabled | `challenge` | `challenger` | `analysis` | 否 | 是 |
| `security_audit` | enabled | `validation` | `lab_runner` | `analysis` | 是 | 是（disabled role） |
| `security_audit` | enabled | `verify` | `evidence_verifier` | `challenge` | 否 | 是 |
| `lab_validation` | **disabled** | `suite_run` | `lab_runner` | — | 是 | 是（disabled workflow） |

- `single` 是默认；由 DSH Main 直接处理，Fleet 只记录 completed，不启动 worker。
- 未知/未登记 workflow、disabled workflow、未知 task、跳过依赖、role 不在
  `allowed_roles` 中一律拒绝。
- `lab_validation` 与 `security_audit.validation` 在 v1 不会执行任何实验。

## 9. Role / preset registry（v1 冻结）

| role | preset | 状态 | DSH profile | MCP profile | tool_profile | 允许工具 | 并发 | timeout (default/max) | 输出上限 |
|---|---|---|---|---|---|---|---|---|---|
| `orchestrator` | `preset_orchestrator` v1.0.0 | enabled | `dsh-main-v1` | — | `orchestrator_none_v1` | 无 | 1 | 30000/60000 | 0 |
| `researcher` | `preset_researcher` v1.0.0 | enabled | `dsh-researcher-v1` | `securitylab_ro` | `researcher_ro_v1` | catalog, status, read_file, get_report, get_run_result | 2 | 60000/120000 | 262144 |
| `vehicle_analyst` | `preset_vehicle_analyst` v1.0.0 | enabled | `dsh-vehicle-analyst-v1` | `securitylab_ro` | `vehicle_analyst_ro_v1` | catalog, status, read_file, get_report, get_run_result | 2 | 60000/120000 | 262144 |
| `challenger` | `preset_challenger` v1.0.0 | enabled | `dsh-challenger-v1` | `securitylab_ro` | `challenger_ro_v1` | catalog, status, read_file, get_report | 1 | 45000/90000 | 131072 |
| `evidence_verifier` | `preset_evidence_verifier` v1.0.0 | enabled | `dsh-evidence-verifier-v1` | `securitylab_ro` | `evidence_verifier_ro_v1` | catalog, status, read_file, get_report, get_run_result | 1 | 45000/90000 | 131072 |
| `lab_runner` | `preset_lab_runner` v1.0.0 | **disabled** | `dsh-lab-runner-v1` | `securitylab_vcan`（disabled） | `lab_runner_vcan_v1` | `securitylab_vcan` | 1 | 120000/300000 | 131072 |

共同约束：

- 每个 preset 固定 DSH profile、插件/扩展 manifest、MCP server/tool allowlist、
  输入/输出 schema、workspace/episode 可见范围、timeout、并发、输出和预算上限。
- plugin manifest 中的插件必须已登记且 enabled；未登记/disabled 插件 fail closed。
- `lab_runner` preset disabled，`securitylab_vcan` profile disabled；任何调用都返回
  `tool-disabled`/`role-disabled`，且无执行副作用。
- env 只传显式 allowlist 的**变量名**；Fleet 不读取 `process.env`，不复制主 DSH
  凭据文件或环境值。v1 允许名：`LANG`、`LC_ALL`、`TZ`（lab_runner 为空）。

## 10. Worker result（不可信数据）

`worker-result.v1` payload 至少包含：

```json
{
  "summary": "…",
  "claims": [],
  "citations": [],
  "artifacts": [],
  "memory_candidates": [],
  "requested_actions": [],
  "limitations": []
}
```

- `challenger` 必须提供 `findings[]`（0 条以上；每条含 `finding_id`、`target`、
  `severity`、`rationale`、`citations`）。
- `evidence_verifier` 必须提供 `verdicts[]`（至少 1 条；每条含 `claim_id`、
  `verdict` ∈ `confirmed|rejected|unresolved`、`evidence_refs`、`rationale`）。
- `requested_actions` 只允许：`request_review`、`request_approval`、
  `propose_memory_candidate`、`flag_evidence_gap`、`request_additional_context`。
  Fleet 只记录，不执行；任何执行/写操作请求都会使结果校验失败。
- `memory_candidates` 是 pending 提议；`scope` 只能是 `user-global`、
  `workspace-shared`、`episode-shared`、`run-private`，不能是 `restricted`；
  未经 Curator 审核不进入 recall。
- 结果未通过 schema 或 role-specific 校验 -> run `failed`（`invalid-worker-result`），
  不会进入 `completed`。
- 结果不是 Evidence；`admission: "none"`、`evidence: false` 是常量。

## 11. 错误码

| code | 含义 |
|---|---|
| `invalid-request` | 请求结构、类型、大小或 JSON 非法 |
| `identity-in-request` | 请求试图设置可信身份/权限字段 |
| `untrusted-binding` | binding 不是 host 签发对象 |
| `workflow-unknown` / `workflow-disabled` | workflow 未登记 / 已禁用 |
| `task-unknown` | task 不属于该 workflow |
| `role-unknown` / `role-disabled` | role 未登记 / 已禁用 |
| `role-not-allowed` | role 不在 task 的 allowed_roles |
| `preset-mismatch` / `preset-disabled` | preset 与 role 不匹配 / 已禁用 |
| `plugin-unregistered` / `plugin-disabled` | 插件未登记 / 已禁用 |
| `workspace-unknown` / `workspace-disabled` | workspace 未登记 / 已禁用 |
| `workspace-role-denied` | 该 role 不允许访问该 workspace |
| `memory-pack-required` / `memory-scope-mismatch` | worker 缺 pack / pack 跨 workspace |
| `approval-required` / `approval-denied` | 缺少 / 拒绝审批 |
| `concurrency-limit` | preset 并发上限已满 |
| `deadline-exceeds-preset` / `budget-exceeds-preset` | 超过 preset/绑定上限 |
| `parent-not-found` / `parent-not-terminal` | parent 不存在 / 未终态 |
| `dependency-not-satisfied` / `invalid-parent-run` | 依赖未满足 / parent 非法 |
| `run-not-found` | run 不存在或调用方无权查看（不泄露存在性） |
| `run-not-cancellable` | run 已终态或不可取消 |
| `result-not-ready` / `result-not-available` | 未终态 / 无可用结果 |
| `adapter-start-failed` | DSH session 打开失败 |
| `adapter-timeout` | worker 超时 |
| `adapter-cancel-failed` | 取消/清理失败（run 记为 blocked） |
| `invalid-worker-result` | worker 输出未通过 schema/role 校验 |
| `cleanup-failed` | session 关闭失败（run 记为 blocked） |
| `ledger-integrity` | ledger 链/格式/字段校验失败 |
| `internal-error` | 未分类内部错误（不得泄露秘密） |

## 12. 安全不变量

1. DSH Main 只能调用四个固定操作；没有任意执行入口。
2. 请求不能扩大 role/workspace/preset/tool/approval/memory 范围。
3. 所有未登记、disabled、缺失、版本不匹配状态都 fail closed。
4. `fleet.status/result/cancel` 按 binding 做 workspace/role 隔离；foreign run 表现为
   `run-not-found`，不泄露存在性。
5. 重试使用新 run id；失败/取消记录不覆盖。
6. timeout/cancel 必须传播到 runtime；清理失败如实记为 `blocked` + cleanup failed。
7. RunLedger 不写 prompt、credential、完整环境、完整模型内部过程或未授权原始材料。
8. worker 输出是不可信数据；不能自动改权限、写共享记忆或成为 Evidence。
9. `lab_runner`/`securitylab_vcan` 默认 disabled；本轮无真实实验。
10. 本轮不建立真实 DSH SDK session；真实 runtime 为 `NOT_RUN`。

## 13. 版本与同步

- 当前版本 `1.0.0`；与 `MEMORYPACK_V1.md`、`SECURITYLAB_MCP_V1.md`、
  `RUN_LEDGER_V1.md`、`DSH_SDK_ADAPTER_V1.md` 同一版本。
- 三个仓库必须声明同一 `contract_version`；不一致时消费方拒绝。
- 变更必须同步更新 `docs/contracts/` 与 `brief/contracts/` 的镜像及测试。

## 14. 示例

- `examples/fleet-submit.research.request.json`
- `examples/fleet-submit.response.json`
- `examples/fleet-status.response.json`
- `examples/fleet-result.response.json`
- `examples/fleet-cancel.response.json`
- `examples/worker-result.challenger.json`
- `examples/worker-result.evidence-verifier.json`
- `examples/workflow.registry.json`
- `examples/role-preset.registry.json`
