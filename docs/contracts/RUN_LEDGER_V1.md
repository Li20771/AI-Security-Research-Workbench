# RunLedger v1

**契约 ID：** `dsh-fleet.run-ledger`
**版本：** `1.0.0`
**状态：** `FROZEN`（2026-10-30）
**实现状态：** `IMPLEMENTED`（in-memory + append-only JSONL；fake-only tests）。
**消费者：** Fleet controller、授权 reviewer、主 DSH 状态查询。

RunLedger 是 **Fleet operational state**，不是知识库，也不是 Evidence。它记录
workflow/worker/session/tool 生命周期、终态和运行产物**引用**，不记录 prompt、
credential、完整环境、完整模型内部过程或未授权原始材料。

## 1. 事件信封

每个事件是一行 JSON（JSONL），字段固定：

```json
{
  "contract_version": "1.0.0",
  "seq": 1,
  "event_id": "evt_0123456789abcdef0123456789abcdef",
  "at": "2026-10-30T00:00:00.000Z",
  "type": "run.created",
  "workflow_instance_id": "wfi_0123456789abcdef0123456789abcdef",
  "run_id": "run_0123456789abcdef0123456789abcdef",
  "task_id": "analysis_a",
  "role": "researcher",
  "data": { },
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

| 字段 | 规则 |
|---|---|
| `seq` | 从 1 开始严格递增；不得跳号/重复 |
| `event_id` | `evt_` + 8..96 个 `[A-Za-z0-9_-]`；唯一 |
| `at` | RFC3339 UTC 时间 |
| `type` | 固定枚举，见 §2 |
| `workflow_instance_id` | run 事件必填；不可信绑定被拒的 `request.rejected` 可为 `null` |
| `run_id` | run 事件必填；拒绝事件为 `null` |
| `task_id` / `role` | 已验证时填写；未验证时为 `null` |
| `prev_hash` | 前一条的 `hash`；genesis 为 64 个 `0` |
| `hash` | 本条事件 canonical JSON 的 SHA-256，见 §4 |

## 2. 事件类型

| type | 用途 |
|---|---|
| `run.created` | run 创建；记录绑定安全元数据、input hash、deadline/budget |
| `run.validated` | 入口策略校验通过 |
| `run.queued` | 进入排队/并发槽 |
| `run.waiting_approval` | 等待审批；未打开 session |
| `run.approved` | 审批通过（host-internal 操作，不是 Fleet 公共 API） |
| `run.session_opened` | DSH session 已打开；记录 `session_id` |
| `run.started` | worker 开始执行 |
| `run.completed` | 终态 completed；记录 result ref/hash/artifact refs |
| `run.failed` | 终态 failed；记录 reason_code/reason |
| `run.blocked` | 终态 blocked；策略/清理/未知状态 |
| `run.timed_out` | 终态 timed_out；cleanup 成功 |
| `run.cancelled` | 终态 cancelled；cleanup 成功或 not_needed |
| `run.cleanup` | runtime cleanup 结果：`not_needed|succeeded|failed|unknown` |
| `run.reconciled` | 重启后识别 orphan run；随后写 `run.blocked` |
| `request.rejected` | submit 被拒绝；不创建 run |

## 3. `data` 允许字段

`data` 是严格对象，`additionalProperties: false`。允许的键：

| 键 | 类型 | 说明 |
|---|---|---|
| `status` | run status | 终态/状态快照 |
| `reason_code` | `[a-z][a-z0-9-]{1,63}` | 机器可读原因 |
| `reason` | string ≤ 2048 | 人类可读原因；不得含秘密/prompt |
| `request_id` | `req_…` | submit 请求 ID |
| `input_sha256` | 64 hex | 任务输入 canonical hash；不存输入原文 |
| `workflow_id` | workflow enum | 固定 workflow |
| `parent_run_id` | `run_…`/null | 依赖或重试来源 |
| `session_id` | `dshsess_…` ≤ 128 | DSH runtime session |
| `preset_id` / `preset_version` | string | preset 身份 |
| `workspace_id` / `episode_id` | string/null | 绑定范围 |
| `base_sha` | 40/64 hex/null | 代码基线 |
| `memory_pack_snapshot_id` / `_hash` | string | MemoryPack 引用 |
| `tool_profile` | string | 工具 profile |
| `approval_ref` | string/null | 审批引用 |
| `deadline_ms` | integer | 有效 deadline |
| `budget` | `{max_tokens,max_cost_usd}` | 有效预算 |
| `result_ref` | string | 结果引用 |
| `result_sha256` | 64 hex | 结果 hash |
| `artifact_refs` | `[{ref,sha256}]` ≤ 100 | 产物引用 |
| `cleanup_state` | `not_needed|succeeded|failed|unknown` | 清理状态 |
| `cleanup_detail` | string ≤ 1024 | 清理说明 |
| `worker` | boolean | `single` 为 false |
| `parent_task_id` | string | 依赖/重试 parent task |
| `reconciled_from_seq` | integer | orphan 识别来源 |
| `adapter` | string ≤ 128 | runtime adapter ID |
| `duration_ms` | integer | 执行时长 |
| `output_bytes` | integer | 输出大小 |

**禁止键**（递归扫描；出现即 `ledger-unsafe-field`，拒绝 append）：

`prompt`、`prompts`、`input`、`messages`、`message`、`env`、`environment`、
`env_values`、`credential`、`credentials`、`token`、`access_token`、
`refresh_token`、`secret`、`password`、`api_key`、`apikey`、`authorization`、
`cookie`、`chain_of_thought`、`reasoning`、`raw_output`、`worker_output`、
`result_payload`、`body`。

另外：

- 字符串值 ≤ 2048 字符；`artifact_refs` 等数组 ≤ 100 项。
- 单事件 canonical JSON ≤ 16 KiB。
- 不写 credential/token/key 值、完整环境、未授权原始材料、完整模型内部过程。
- 不写 worker result payload 本身，只写 `result_ref` + `result_sha256`。

## 4. 哈希链

- canonical JSON：对象键按字典序递归排序；数组保序；拒绝 `undefined`/非有限数。
- `hash = SHA-256(canonicalJson(event without hash))`；`prev_hash` 参与计算。
- genesis：`prev_hash = "0" × 64`。
- `seq` 必须从 1 连续递增；`prev_hash` 必须等于上一条 `hash`。
- 读取/启动时验证整条链；任何格式、seq、prev_hash、hash 或字段安全校验失败 ->
  `ledger-integrity`，拒绝继续 append（fail closed），不自动修复/截断。
- `readAll()` 返回不可变副本；没有 update/delete/truncate API。

## 5. 存储与恢复

- `JsonlRunLedger` 以 append 模式写 UTF-8 JSONL；每行一个事件。
- 进程重启后从文件重建 `seq`/`hash` 链；无法验证 -> 拒绝启动 ledger。
- `run.reconciled`：对最后一个状态非终态的 run，记录
  `reason_code = "orphaned-after-restart"`、`cleanup_state = "unknown"`，
  然后写 `run.blocked` 终态；**不**复用未知 session，不尝试猜测成功。
- 结果内容不在 ledger 中；结果引用指向 result store。result store 不可用时
  `fleet.result` 返回 `result-not-available`，不伪造结果。

## 6. 与其它数据边界

| 数据 | 用途 | 写入者 | 消费者 |
|---|---|---|---|
| RunLedger | workflow/worker/session/tool 生命周期、终态、结果引用 | Fleet | 主 DSH、授权 reviewer |
| dsh-memory | 可复用项目知识、工作流、接力上下文 | 主 DSH/Curator 审核后写 | workers 只读 MemoryPack |
| Evidence | 经 producer/provenance/scope/admission 的 durable facts | 授权 producer | Verifier/人 |

- RunLedger 事件、worker 输出、Fleet 答复都不是 Evidence。
- 旧 Workbench AI-15-B/B5 仍为 `BLOCKED`；本 Fleet 不绕过 producer/admission gate。

## 7. 示例

- `examples/run-ledger.events.jsonl`（含有效 hash 链的 3 条事件）

## 8. 版本与同步

- 当前版本 `1.0.0`；与 `FLEET_API_V1.md` 同一版本。
- 任何事件/字段/禁令变化必须同步 schema、controller、测试与 `brief/contracts/`。
