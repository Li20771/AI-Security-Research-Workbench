# DSH SDK Runtime Adapter v1

**契约 ID：** `dsh-fleet.dsh-adapter`
**版本：** `1.0.0`
**状态：** `FROZEN`（2026-10-30）
**实现状态：** 接口 + fake adapter `IMPLEMENTED`；真实 DSH SDK/runtime `NOT_RUN`。
**消费者：** Workbench Fleet controller、未来的 DSH SDK adapter 实现。

本契约定义 Fleet 与 DSH runtime 之间的**窄接口**。Fleet 不复制 DSH 的模型循环、
prompt loop 或原生 subagent 机制；每个 worker 是由 DSH runtime 执行的独立角色化
Agent preset。

## 1. 本轮静态检查结论

- 工作区内**未发现**官方 DSH SDK 源码/包（未发现 `real-runtime.mjs`、SDK package
  或 `@deepseek-harness/*` 已安装依赖）。
- 因此对官方 SDK 的静态/API 结构检查为 **`BLOCKED`**（输入缺失），真实 SDK
  session/handshake/initialize/prompt/event/cancel probe 为 **`NOT_RUN`**。
- 本文件中的接口是 Fleet 侧稳定边界，不是对官方 SDK 具体方法签名的声明；
  接入真实 SDK 时必须重新做静态 API 对照并单独授权。
- 禁止在本轮建立真实 SDK session、启动真实 DSH、发送 prompt、读取 event stream
  或做真实 cancel probe。

## 2. 适配器接口

```ts
interface DshRuntimeAdapter {
  readonly adapter_id: string;

  openSession(request: DshSessionRequest): Promise<DshSessionHandle>;
  runSession(handle: DshSessionHandle, run: DshRunRequest): Promise<unknown>;
  cancelSession(handle: DshSessionHandle, reason: string): Promise<DshCancelResult>;
  closeSession(handle: DshSessionHandle): Promise<DshCloseResult>;
  health(handle?: DshSessionHandle): Promise<DshHealth>;
}
```

- `openSession` 必须创建**新的** session；一个 run 一个 session，不并发复用。
- `runSession` 返回 worker 原始输出（`unknown`），Fleet 负责按 `worker-result.v1`
  校验；adapter 不得把输出直接标记为完成/Evidence。
- `cancelSession` 必须传播到对应 DSH worker process/session，并返回是否清理成功。
- `closeSession` 必须确认 runtime 关闭；失败/未知不得伪装成功。
- `health` 用于判断 session 生命周期；未知状态 fail closed。
- adapter 不得读取/复制主 DSH credential 文件或完整环境；只接收 preset 的
  env allowlist **变量名**，值由受信 host 显式提供。

### 2.1 `DshSessionRequest`

```json
{
  "run_id": "run_…",
  "role": "researcher",
  "preset_id": "preset_researcher",
  "preset_version": "1.0.0",
  "dsh_profile": "dsh-researcher-v1",
  "plugin_manifest": [{ "plugin_id": "fleet.core", "version": "1.0.0" }],
  "tool_profile": "researcher_ro_v1",
  "mcp_server": "securitylab_ro",
  "workspace_id": "ws_a",
  "episode_id": "ep_1",
  "workspace_root": "D:\\lab\\ws_a",
  "working_directory": "D:\\lab\\ws_a",
  "memory_pack": { "snapshot_id": "mp_…", "snapshot_hash": "…" },
  "env_allowlist": ["LANG", "LC_ALL", "TZ"],
  "lifecycle_hooks": { }
}
```

- 所有字段来自已验证的 preset/binding；调用方不能通过 request body 覆盖。
- `env_allowlist` 只含变量名，不含值；Fleet 不读取 `process.env`。
- `plugin_manifest` 必须与 preset 的登记 manifest 一致；未登记/disabled 插件在
  Fleet 入口已被拒绝。
- `memory_pack` 是只读引用；adapter 不得写入 dsh-memory。

### 2.2 结果

```ts
interface DshCancelResult {
  cleaned: boolean;
  detail?: string;
}

interface DshCloseResult {
  closed: boolean;
  detail?: string;
}

interface DshHealth {
  state: "ready" | "closed" | "unknown";
  session_id?: string;
}
```

- `cleaned: false` / `closed: false` -> Fleet 将 run 记为 `blocked`
  （`cleanup_state` 为 `failed` 或 `unknown`），不记为 `cancelled`/`timed_out`。
- 任何错误不得包含 credential、token、完整环境或 prompt。

## 3. 两个独立 lifecycle hook

必须严格区分：

| hook | 参考（handoff） | 语义 | 禁止 |
|---|---|---|---|
| `session.promptBeforeInitialize` | `real-runtime.mjs:183–195` | prompt/session 初始化相关处理 | 不得当作工作目录安全检查 |
| `session.wd.beforeInitialize` | `real-runtime.mjs:226–244` | working-directory 初始化相关处理 | 不得合并 prompt 语义 |

Fleet 侧接口：

```ts
interface DshLifecycleHooks {
  promptBeforeInitialize(event: PromptBeforeInitializeEvent): Promise<HookResult>;
  wdBeforeInitialize(event: WdBeforeInitializeEvent): Promise<HookResult>;
}
```

- 两个事件类型不同，payload 不同，调用点不同，测试分别覆盖。
- `promptBeforeInitialize` 的 payload **不含** `path`/`working_directory`；如果调用
  方把路径塞进 prompt hook，返回 `prompt-hook-misused-for-path`。
- `wdBeforeInitialize` 的 payload 含 `workspace_root` + `working_directory`；
  必须做 canonicalization + containment；越界返回 `wd-out-of-root`。
- 不得用 prompt hook 代替工作目录安全检查，也不得用 wd hook 处理 prompt 内容。
- 两个 hook 都必须调用；任一失败 -> session 初始化失败（`session-init-blocked`），
  不启动 worker。

## 4. Fake adapter 测试矩阵（必须离线）

| 场景 | 期望 |
|---|---|
| 正常完成 | 新 session；有效 result；completed；cleanup succeeded |
| 启动失败 | failed（`adapter-start-failed`）；无 session/无结果 |
| timeout | 传播 cancel；cleanup 成功 -> timed_out；失败 -> blocked |
| 显式 cancel | 传播 cancel；cleanup 成功 -> cancelled；失败 -> blocked |
| malformed event/output | failed（`invalid-worker-result`），不进入 completed |
| 并发隔离 | 每个 run 独立 session_id；不共享状态/输入/结果 |
| kill/close failure | blocked + cleanup failed/unknown；不复用 session |
| 重启 orphan | 新 controller 通过 ledger 识别非终态 run -> blocked；不重开 session |
| hook 分离 | prompt/wd 两个 hook 分别调用；wd 拒绝路径逃逸；prompt 不处理路径 |
| env allowlist | 只传允许名；不含 secret/完整环境；不读取 process.env |

## 5. 非声明

- 本契约不声明真实 DSH SDK 的包名、版本、方法签名、事件格式或平台兼容性。
- 本契约不授权建立真实 session、连接真实 DSH、调用 provider/model 或读取凭据。
- fake adapter 通过不等于真实 runtime 集成通过；真实结果保持 `NOT_RUN`。
- Windows Desktop / WSL / Linux/macOS 不互相推定兼容；首个受支持平台需显式
  写入测试矩阵并单独验证。

## 6. 版本与同步

- 当前版本 `1.0.0`；与 `FLEET_API_V1.md` 同一版本。
- 接入真实 SDK 前必须新增 adapter 实现、静态 API 对照记录、独立授权和测试矩阵；
  不得只改本文件就声称已连接。
