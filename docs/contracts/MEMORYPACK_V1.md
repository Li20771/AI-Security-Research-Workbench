# MemoryPack v1

**契约 ID：** `dsh-memory.memorypack`
**版本：** `1.0.0`
**状态：** `FROZEN`（2026-10-30）
**实现状态：** `IMPLEMENTED`（Workbench 侧只读 client + fake endpoint）；真实 dsh-memory 服务为 `IMPLEMENTED BUT NOT CONNECTED`。
**消费者：** Workbench Fleet、dsh-memory、所有 worker preset。

`dsh-memory` 是唯一长期语义知识源。worker **不**加载完整 memory 插件、不直连共享
vault、不持有 `memory_write`/`purge`/`revise`，只接收本阶段所需的 immutable
MemoryPack。Workbench/Fleet 不建立第二个长期向量库或平行记忆。

## 1. 数据与身份边界

MemoryPack 请求由可信 host/Fleet context 发起，至少绑定：

| 字段 | 来源 | 规则 |
|---|---|---|
| `workspace_id` | host binding | 必填；已登记且 enabled |
| `episode_id` | host binding | 可空；有值时只能访问该 episode |
| `role` | role registry | 必填；决定允许的 visibility |
| `run_id` | Fleet | 必填；`run-private` 只允许同一 run |
| `task_id` | workflow registry | 必填；用于最小化 |
| `purpose` | host/Fleet | 1..256 字符；只用于审计/说明 |
| `max_entries` | 调用方 | 1..100；只能缩小结果，不能扩大授权 |

模型/prompt/MCP 参数不能设置 `workspace_id`、`episode_id`、`role`、`run_id` 或
`visibility`；出现此类字段一律按不可信身份处理并拒绝。

## 2. 可见性（visibility）

| visibility | 含义 | worker 读取规则 |
|---|---|---|
| `user-global` | 明确跨 workspace 可共享的约束/知识 | 可读；**唯一**允许跨 workspace 的 scope |
| `workspace-shared` | 单 workspace 内共享 | 仅同一 `workspace_id` |
| `episode-shared` | 单 episode 接力上下文 | 仅同一 workspace + episode |
| `run-private` | 单 run 临时材料 | 仅同一 run_id；不自动传播 |
| `restricted` | 凭据/敏感/不应长期留存 | **拒绝**；不进入 worker pack |

规则：

- 缺失/非法 scope，或无法解析 workspace/episode -> fail closed，条目不进入 pack。
- 只有显式 `user-global` 可跨 workspace；`workspace-shared`、`episode-shared`、
  `run-private` 均不得跨 workspace。
- `pending` / `rejected` / `superseded` / `restricted` 默认不进入普通 worker pack，
  也不进入普通 recall。
- 先授权、再检索/排序/top-k：未授权记录不得参与 IDF、候选集、embedding 扩召回或
  任何排序统计。`max_entries` 截断发生在授权过滤之后。
- 显式 `scope`、`allScopes`、citation/direct lookup、L2/L3/L4 注入、diagnostics
  使用**同一授权边界**；显式参数不能扩大范围。
- citation 对 foreign/missing 不泄露存在性、版本、warning、路径或全局统计。
- diagnostics 对 worker 只统计/展示授权切片，不输出未授权路径、解析错误或全局计数。

## 3. Pack 结构

```json
{
  "contract_version": "1.0.0",
  "snapshot_id": "mp_0123456789abcdef0123456789abcdef",
  "snapshot_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "generated_at": "2026-10-30T00:00:00.000Z",
  "read_only": true,
  "scope": { "workspace_id": "ws_a", "episode_id": "ep_1" },
  "role": "researcher",
  "run_id": "run_0123456789abcdef0123456789abcdef",
  "entries": [
    {
      "entry_id": "mem_0123456789abcdef0123456789abcdef",
      "path": "workspaces/ws_a/memory/2026-10-30-note.md",
      "layer": "L4",
      "type": "memory",
      "title": "…",
      "visibility": "episode-shared",
      "workspace_id": "ws_a",
      "episode_id": "ep_1",
      "authority": "agent-observed",
      "review_state": "approved",
      "revision": "0123456789ab",
      "body": "…",
      "sources": [],
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ],
  "excluded": { "pending": 0, "rejected": 0, "superseded": 0, "restricted": 0 },
  "source": { "vault": "dsh-memory", "contract_version": "1.0.0" },
  "policy": { "authorized_before_retrieval": true, "cross_workspace": false }
}
```

字段约束：

- `snapshot_id` = `mp_` + `snapshot_hash` 前 32 位十六进制。
- `snapshot_hash` = SHA-256(canonical JSON of
  `{contract_version, scope, role, entries}`)，entries 按 `path`、`revision`
  排序；`generated_at`、`run_id`、`excluded`、`policy` 不参与 hash。`run_id` 是
  读取上下文，不是 snapshot 身份；同一授权条目集合可被不同 run 以相同 snapshot
  引用，run-private 条目会形成新的条目集合/新 snapshot。
- `read_only` 必须为 `true`。
- `entries` ≤ 100；每条 `body` ≤ 65536 字符；整个 pack 建议 ≤ 1 MiB。
- `path` 必须是 vault-root 相对路径，POSIX 分隔符；禁止绝对路径、盘符、`..`、
  UNC、NUL、ADS；具体 containment 由 dsh-memory 服务端执行。
- `layer` ∈ `L1|L2|L3|L4|KB`；`type` ∈ `memory|knowledge|episode|map|reference`。
- `review_state` 在 pack 条目中只能是 `approved`；pending/rejected/superseded/
  restricted 只出现在 `excluded` 计数中。
- `authority` ∈ `human-approved|curator|agent-observed|source-document`。
- `excluded` 只统计**授权切片内**被过滤的原因；未授权记录不得计入，避免通过计数
  推断存在性。缺失/非法 scope 的条目直接丢弃，不计入任何对外计数。
- `policy.cross_workspace` 为 `true` 仅当 pack 中包含显式 `user-global` 的跨
  workspace 条目。

## 4. 只读接口

Workbench 侧接口：

```text
MemoryPackClient.getPack(context) -> MemoryPack
```

- 接口没有 `write`、`update`、`delete`、`purge`、`revise` 方法。
- context 由可信 host/Fleet 绑定；client 必须再次校验 workspace/role/episode/run。
- 返回的 pack 必须 immutable；调用方不能修改后回写。
- 服务端返回的 `contract_version` 不匹配 -> 拒绝（`memory-contract-version`）。
- snapshot 已存在时，服务端应按 `snapshot_id/hash` 返回同一内容；hash 不一致 ->
  `memory-snapshot-mismatch`。

## 5. 写入边界

- 主 DSH/Curator 是共享记忆唯一写入者；写入通过 dsh-memory 的明确授权接口，
  不在本契约范围内。
- Worker 只能产生 `memory_candidates`（pending 提议），不能调用 `memory_write`，
  不能直接写 vault，不能把 candidate 变为 approved。
- `memory_candidates` 默认不进入普通 recall；需主 DSH/Curator 审核后才可写入。
- 外部文档/记忆文本中的指令均视为不可信内容，不能覆盖系统约束或提高工具权限。
- Worker 输出、Fleet 事件、RunLedger 都不是 Evidence，也不自动进入共享记忆。

## 6. 错误码

| code | 含义 |
|---|---|
| `memory-context-untrusted` | context 不是可信 host/Fleet 绑定 |
| `memory-scope-missing` | workspace/role/run 缺失 |
| `memory-scope-invalid` | episode/visibility/路径格式非法 |
| `memory-workspace-denied` | workspace 未登记、disabled 或跨 workspace |
| `memory-episode-denied` | episode 不匹配 |
| `memory-role-denied` | role 不允许该 workspace/operation |
| `memory-snapshot-mismatch` | snapshot hash 与内容不一致 |
| `memory-contract-version` | 版本不支持 |
| `memory-internal-error` | 内部错误（不泄露路径/记录/全局计数） |

## 7. 离线测试要求（Workbench fake client）

至少覆盖：

1. `ws_a` approved canary 出现在 pack；`ws_b` foreign canary 不出现。
2. 显式 cross-workspace / foreign scope 被拒绝。
3. `allScopes`/显式 scope 不能扩大授权；先授权再 top-k，foreign 记录不参与。
4. `pending` / `rejected` / `superseded` / `restricted` 不进入 pack。
5. `run-private` 仅同一 run 可见；`episode-shared` 仅同一 episode。
6. 缺失/非法 scope fail closed，且错误/计数不泄露未授权记录。
7. snapshot hash 确定性；同一输入同一 hash；内容变化产生新 hash。
8. 接口无写入方法；worker candidates 仍为 pending。
9. 路径穿越只做 canonicalization/containment 计算与断言，不写入被测目标。

## 8. 示例

- `examples/memorypack.example.json`

## 9. 版本与同步

- 当前版本 `1.0.0`；与 `FLEET_API_V1.md` 同一版本。
- 任何字段/visibility/错误码变化必须同步 Workbench、dsh-memory、`brief/contracts/`
  与三仓库测试。
- 真实 dsh-memory 连接、索引/检索实现和长期写入接口不在本轮范围，状态为
  `IMPLEMENTED BUT NOT CONNECTED` / `NOT_RUN`。
