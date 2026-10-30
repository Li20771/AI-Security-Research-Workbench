# DSH Agent Fleet v3.0 — Workbench Fleet core

**状态：** fake-only 可审查实现；真实 DSH SDK/runtime、provider/model、SecurityLab/vcan 均为 `NOT_RUN`。
**契约版本：** Fleet API `1.0.0`；MemoryPack `1.1.0`（见 `docs/contracts/` 与 `brief/contracts/` 镜像）。
**目标运行时：** Node.js 22+；本机验证使用 Node `v22.23.4`。

本目录是新 **Fleet / 编排 / 权限基础**，不是重新实现一套 LLM Agent。DSH Main 只通过
四个固定操作调度；worker 由未来的官方 DSH runtime adapter 执行；Fleet 负责可信绑定、
固定 workflow/role/preset、append-only RunLedger、只读 MemoryPack 与 SecurityLab MCP
工具 profile。

## 1. 目录

```text
fleet/
  src/
    fleet-controller.ts     Fleet 状态机、submit/status/result/cancel、cancel/timeout/reconcile
    fleet-api.ts            只暴露四个固定操作的 DSH Main API
    binding.ts              可信 host binding 签发/验证（opaque WeakSet）
    request-validation.ts   请求/查询 fail-closed 校验
    ledger.ts               append-only RunLedger（内存 + JSONL，哈希链）
    worker-result.ts        不可信 worker 输出 schema/role 校验
    path-safety.ts          canonicalization/containment 纯计算
    env.ts                  仅 allowlist 变量名；不读 process.env
    registries/             workflow / role-preset / plugin / workspace 固定 registry
    adapters/               DSH runtime adapter 接口、fake adapter、hook 分离
    memory/                 只读 MemoryPack client + fake endpoint
    mcp/                    SecurityLab MCP client + fake server
  test/                     离线 fake tests（node:test）
  scripts/                  contract check / ledger example generator
```

## 2. 已实现（`IMPLEMENTED`）

- `fleet.submit/status/result/cancel` 固定 API；无 `run_agent`、任意命令/路径/角色入口。
- 固定 `single` / `research` / `design_review` / `security_audit` / `lab_validation`
  workflow registry；`lab_validation` disabled。
- 固定 `orchestrator` / `researcher` / `vehicle_analyst` / `challenger` /
  `evidence_verifier` / `lab_runner` preset；`lab_runner` disabled。
- 可信 binding：workspace/episode/role/preset/tool profile/MemoryPack/approval/deadline/budget；
  请求不能覆盖；普通 JSON 对象不能伪造。
- append-only RunLedger：seq、prev_hash、SHA-256 链、JSONL 持久化、损坏 fail closed、
  prompt/credential/env/完整模型过程字段禁令。
- 状态机与终态：created/validated/queued/running/waiting_approval/completed/failed/
  blocked/timed_out/cancelled；重试新 run id；timeout/cancel 清理失败 -> blocked。
- fake DSH adapter：成功、启动失败、timeout、cancel、malformed output、crash、
  并发隔离、kill/close failure、restart orphan。
- 只读 MemoryPack fake client：user-global/workspace-shared/episode-shared/run-private/
  restricted；先授权后 top-k；pending/rejected/superseded/restricted 不进入 pack。
- SecurityLab MCP fake client：`securitylab_ro`、`lab_catalog/status/read_file/get_report/
  get_run_result`；路径 containment、输出上限/脱敏；`securitylab_vcan` disabled。
- 两个独立 DSH lifecycle hook：`session.promptBeforeInitialize` 与
  `session.wd.beforeInitialize`，分别测试，不合并语义。
- 静态边界：Fleet 源码不读 `process.env`、不 spawn、不联网、不 import 旧
  agents/providers/routing/composition/Evidence writer。

## 3. 已实现但未连接（`IMPLEMENTED BUT NOT CONNECTED`）

- 官方 DSH SDK runtime adapter：只有接口与 fake adapter；未安装/未调用官方 SDK。
- dsh-memory：只有 Workbench 侧只读 client 与 fake endpoint；未连接真实 vault。
- SecurityLab MCP：只有 Workbench 侧 client 与 fake server；未连接真实 server。
- 结果存储：`InMemoryResultStore`；没有 durable production result store。

## 4. 阻塞/未运行（`BLOCKED` / `NOT_RUN`）

- 官方 DSH SDK 静态/API 结构检查：工作区未发现 SDK 源码/包 -> `BLOCKED`。
- 真实 DSH session/handshake/initialize/prompt/event/cancel：`NOT_RUN`。
- 真实 provider/model 调用：`NOT_RUN`。
- SecurityLab/vcan/CAN/ECU/车辆/设备实验：`NOT_RUN`。
- Windows/WSL/Linux/macOS 兼容性矩阵：`NOT_RUN`。
- 旧 Python 测试套件未在本轮全部运行；旧模块测试保留。

## 5. 本地命令（离线）

使用仓库外的 Node 22：

```powershell
$node = 'D:\claude-work\DSH-Fleet-v3\.tools\node22\node-v22.23.4-win-x64\node.exe'
$npm  = 'D:\claude-work\DSH-Fleet-v3\.tools\node22\node-v22.23.4-win-x64\npm.cmd'
Set-Location 'D:\claude-work\DSH-Fleet-v3\01-workbench\fleet'
& $npm install --offline --no-audit --no-fund --ignore-scripts
& $node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit
& $node --experimental-strip-types --test "test/*.test.ts"
& $node --experimental-strip-types scripts/check-contracts.ts
```

或使用 npm scripts：`npm run typecheck`、`npm test`、`npm run contracts:check`。

## 6. 安全边界（实现约束）

- `lab_runner` 与 `securitylab_vcan` 默认 disabled；无实验/设备执行。
- 不读取/复制 credential/token/key 文件或环境值；env 只传 allowlist 名称。
- path-traversal 测试只做 canonicalization/containment 计算与断言，不写入被测逃逸目标。
- worker 输出是不可信数据：不是 Evidence，不能自动写共享记忆或改权限。
- AI-15 Evidence writer / B5 仍为 `BLOCKED`；本 Fleet 不绕过 producer/admission gate。
- RunLedger 不是知识库/Evidence；MemoryPack 只读；Evidence 独立。
- 不 push/merge；本目录是本地可审查 diff。
