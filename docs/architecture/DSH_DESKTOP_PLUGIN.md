# DSH Desktop Fleet Plugin（C 阶段接入）

**状态：** `IMPLEMENTED`（插件 + host 已在真实 DSH SDK session 验证；已安装到
`desktop` profile，等待 DSH Desktop 重启后做 UI 验收）  
**日期：** 2026-11-02  
**性质：** 部署 glue；Fleet 包本身不依赖 DSH Desktop，也不把 provider/router 带回来。

## 1. 结构

```text
DSH Desktop (desktop profile)
  └─ dsh-fleet plugin (lib/index.js)
       ├─ fleet_submit / fleet_status / fleet_result / fleet_cancel
       └─ stdio JSON-RPC
            ▼
       fleet-host.ts (独立 Node 进程)
         ├─ TrustedBindingIssuer（host 签发，模型不能设置身份）
         ├─ FleetController + RunLedger + InMemoryResultStore
         ├─ RealDshAdapter → 官方 dsh-sdk-client → 独立 DSH worker sessions
         ├─ dsh-memory stdio service（只读 MemoryPack）
         └─ SecurityLab MCP per-run binding/patch
```

插件只是传输层。身份、workspace、episode、role、preset、tool profile、MemoryPack
和 approval 都由 host 侧签发；四个工具的参数里出现这些字段会被拒绝。

## 2. 工具

| 工具 | 参数 | 说明 |
|---|---|---|
| `fleet_submit` | `workflow_id`, `task_id`, `input`, optional `parent_run_id`/`deadline_ms`/`budget` | 创建 run；host 按 task registry 选择 enabled worker role |
| `fleet_status` | `run_id` 或 `workflow_instance_id` + optional `task_id` | 查询同一 workspace 的 run |
| `fleet_result` | `run_id` | 读取 completed 且 schema/role 校验通过的 result |
| `fleet_cancel` | `run_id` | 取消 queued/waiting/running；cleanup 失败会 blocked |

`input` 是 untrusted JSON；不能改变 role/scope/tool/memory/provider。

## 3. 当前部署配置

- workspace：`ws_a` → `E:\DSH-jiagou\_repos\03-securitylab`
- episode：`ep_1`
- provider/model：`tokenrhythm / deepseek-flash`（受信部署配置）
- MemoryPack：独立 dsh-memory stdio service；当前使用 synthetic vault
  `E:\DSH-jiagou\_c-runtime\vault-plugin`
- SecurityLab MCP：真实只读 stdio server，per-run binding
- DSH worker runtime：官方 `0.2.1-rc.2`；每 run 独立临时 `DSH_HOME`
- ResultStore：`InMemoryResultStore`；DSH Desktop/host 重启后不保留结果

## 4. 安装位置

已安装到：

```text
C:\Users\20771\.dsh\profiles\desktop\node_modules\dsh-fleet\
```

`profiles/desktop/package.json` 已加入：

- `dependencies.dsh-fleet = "0.1.0"`
- `dsh.profile.bundles` 末尾 `dsh-fleet`

安装前备份：

```text
profiles/desktop/package.json.bak-dsh-fleet-<timestamp>
```

**重启 DSH Desktop** 后插件才会加载。若 Desktop 启动失败，恢复备份的
`package.json` 并删除 `node_modules/dsh-fleet` 即可回退。

## 5. 已验证

在真实 DSH SDK session 中加载同一插件（file-URL patch），模型调用
`fleet_submit`，host 返回：

```json
{"contract_version":"1.0.0","ok":true,"operation":"submit",
 "data":{"status":"completed"}}
```

host 另行通过真实 SecurityLab MCP、独立 dsh-memory service 和 tokenrhythm route
完成了 research 三角色 smoke。Desktop UI 内的工具调用尚未由本会话验收，需重启后
在聊天里确认四个工具出现。

## 6. 限制

- 固定单一 workspace `ws_a`；不跟随 DSH Desktop 当前会话切换 workspace。
- 当前 synthetic vault；真实用户 vault 未接入。
- InMemoryResultStore；重启丢结果；无 durable replay。
- 没有 host/session 级审批 UI；approval 仍为 host 内部配置。
- 真实 vcan/CAN/ECU/车辆/设备实验仍 `NOT_RUN`。
- 宿主进程路径位于本机 temp/部署目录；迁移到其他机器需重新生成配置。
