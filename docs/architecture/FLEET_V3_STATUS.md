# DSH Agent Fleet v3.0 — 实施状态

**仓库基线：** `21fe4e71c47e7bb95c22c103d4c14bce295490b9`（GitHub `main`；PR #103 已于 2026-10-30 合入）
**工作分支：** `fix/fleet-v3-round2-hardening`（基于上述 `main`；本轮改动位于本地工作树，尚未 commit/push/merge）
**实施日期：** 2026-10-30 首轮；2026-11-01 round 2 加固
**性质：** fake-only、离线、可审查实现；不是真实 DSH/provider/SecurityLab 验收。

本文件区分 `IMPLEMENTED`、`IMPLEMENTED BUT NOT CONNECTED`、`BLOCKED`、`NOT_RUN`。
Fake test 通过不等于真实 runtime 集成通过。

## 1. 共享契约（Fleet API `1.0.0`；MemoryPack `1.1.0`）

| 文件 | 版本 | 状态 |
|---|---|---|
| `docs/contracts/FLEET_API_V1.md` | 1.0.0 | FROZEN / IMPLEMENTED |
| `docs/contracts/MEMORYPACK_V1.md` | 1.0.0 | FROZEN（历史版本，保留不复写） |
| `docs/contracts/MEMORYPACK_V1_1.md` | 1.1.0 | FROZEN / Workbench fake client IMPLEMENTED |
| `docs/contracts/SECURITYLAB_MCP_V1.md` | 1.0.0 | FROZEN / Workbench fake client IMPLEMENTED |
| `docs/contracts/RUN_LEDGER_V1.md` | 1.0.0 | FROZEN / IMPLEMENTED |
| `docs/contracts/DSH_SDK_ADAPTER_V1.md` | 1.0.0 | FROZEN / fake adapter IMPLEMENTED；真实 SDK NOT_RUN |
| `docs/contracts/*.schema.json`（14 个） | 1.0.0 / 1.1.0 | FROZEN / Ajv validated |
| `docs/contracts/examples/*`（14 个，含 7 条 RunLedger 事件） | 1.0.0 / 1.1.0 | FROZEN / Ajv validated |

一致副本：`D:\claude-work\DSH-Fleet-v3\brief\contracts\`。版本不一致时消费方必须拒绝。
MemoryPack 1.1.0 只允许显式 `user-global` 跨 workspace；无显式 visibility 的旧记录
不进入 worker pack，只能由 Curator 通过只读迁移清单确认后迁移；路径为 NFC Unicode。

## 2. 实现矩阵

| 能力 | 状态 | 证据/位置 |
|---|---|---|
| 四个固定 Fleet API（submit/status/result/cancel） | `IMPLEMENTED` | `fleet/src/fleet-api.ts`, `fleet-controller.ts` |
| 固定 workflow registry / state machine | `IMPLEMENTED` | `fleet/src/registries/workflows.ts`, `state-machine.ts` |
| 固定 role/preset/plugin registry | `IMPLEMENTED` | `fleet/src/registries/roles.ts`, `plugins.ts` |
| 可信 run/workspace binding | `IMPLEMENTED` | `fleet/src/binding.ts` |
| append-only RunLedger（内存 + JSONL，哈希链） | `IMPLEMENTED` | `fleet/src/ledger.ts` |
| fake DSH runtime adapter（success/fail/timeout/cancel/malformed/concurrency/restart） | `IMPLEMENTED` | `fleet/src/adapters/fake-dsh-adapter.ts` |
| `session.promptBeforeInitialize` / `session.wd.beforeInitialize` 分离 | `IMPLEMENTED` | `fleet/src/adapters/lifecycle-hooks.ts`, `test/hooks.test.ts` |
| 只读 MemoryPack client + fake endpoint | `IMPLEMENTED` | `fleet/src/memory/*`, `test/memorypack.test.ts` |
| SecurityLab MCP client + fake server | `IMPLEMENTED` | `fleet/src/mcp/securitylab-client.ts`, `test/securitylab.test.ts` |
| worker 输出 schema/role 校验 | `IMPLEMENTED` | `fleet/src/worker-result.ts` |
| path containment / env allowlist / 静态边界 | `IMPLEMENTED` | `fleet/src/path-safety.ts`, `env.ts`, `test/static-boundary.test.ts` |
| 旧模块隔离/处置记录 | `IMPLEMENTED` | `docs/architecture/FLEET_V3_MODULE_DISPOSITION.md` |
| 真实 official DSH SDK adapter/API 对照 | `BLOCKED` | 工作区未发现 SDK 源码/包；未安装依赖 |
| 真实 DSH session/runtime | `NOT_RUN` | 未建立 session，未启动 DSH |
| 真实 dsh-memory 服务 | `IMPLEMENTED BUT NOT CONNECTED` | 只有 Workbench 侧 client + fake endpoint |
| 真实 SecurityLab MCP server | `IMPLEMENTED BUT NOT CONNECTED` | 只有 Workbench 侧 client + fake server |
| provider/model 调用 | `NOT_RUN`（**调用面已移除**） | live runner、`http_transport.py`、live workflow、`tests/live/` 已删除；Layer 0 强制不得回归 |
| SecurityLab/vcan/CAN/ECU/车辆/设备实验 | `NOT_RUN` | `lab_runner` / `securitylab_vcan` disabled |
| AI-15 Evidence writer / B5 | `BLOCKED / UNCHANGED` | Fleet 不写 Evidence，不绕过 producer/admission |
| 旧 Python 全量测试套件 | `NOT_RUN` | 本轮只运行新增 Fleet 离线 tests；旧测试保留 |

## 3. 测试矩阵（本地，离线）

运行时：Node `v22.23.4`；TypeScript `5.9.3`；Ajv `8.20.0`。

```text
TypeScript typecheck                         PASS  0 errors
Fleet fake tests (node:test)                 PASS  85 passed / 0 failed / 0 skipped
Contract schema/examples check               PASS  14 schemas / 13 JSON examples / 7 ledger events（14 个示例文件）
Cross-repo MemoryPack v1.1 fixture           PASS  2 passed（dsh-memory producer 产物由 Workbench schema/hash 校验）
git diff --check                             PASS  (见交付报告)
```

准确命令：

```powershell
$node = 'D:\claude-work\DSH-Fleet-v3\.tools\node22\node-v22.23.4-win-x64\node.exe'
$npm  = 'D:\claude-work\DSH-Fleet-v3\.tools\node22\node-v22.23.4-win-x64\npm.cmd'
Set-Location 'D:\claude-work\DSH-Fleet-v3\01-workbench\fleet'
& $npm install --offline --no-audit --no-fund --ignore-scripts
& $node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit
& $node --experimental-strip-types --test "test/*.test.ts"
& $node --experimental-strip-types scripts/check-contracts.ts
```

覆盖：

- 固定 workflow/role/preset；lab_validation/lab_runner/vcan disabled；未知/越界 fail closed。
- 请求不能覆盖 role/workspace/preset/tool/approval/memory；普通对象不能伪造 binding。
- 成功、启动失败、timeout、显式 cancel、kill/close failure、malformed output、crash。
- 并发隔离（独立 session_id、不共享输入/结果）；重启 orphan -> blocked。
- run 重试新 run id；原失败记录保留；依赖 parent 校验。
- RunLedger 哈希链、篡改检测、禁止字段、JSONL 重启、损坏 fail closed。
- MemoryPack visibility/scope/top-k/pending/restricted/run-private/episode-shared。
- MemoryPack 确定性：Unicode code point 排序、`snapshot_hash` 与输入顺序无关、
  locale 无关；hardcoded hash 锁定顺序规则。
- 跨仓库 fake acceptance：`test/cross-repo-memorypack.test.ts` 校验 dsh-memory
  producer 生成的 synthetic pack（schema、NFC、entry sha256、snapshot hash、
  `excluded`、`policy.cross_workspace`），并验证篡改/未知版本会被拒绝。
- SecurityLab 路径 traversal/absolute/drive/UNC/NUL/ADS/symlink、identity args、disabled vcan、输出上限/脱敏。
- 两个 lifecycle hook 分开调用/拒绝；prompt hook 不处理路径，wd hook 不处理 prompt；
  wd hook 对未知/缺失 root、root mismatch、不存在路径、symlink/junction escape
  全部 fail closed。
- 静态检查：无 `process.env`、无 spawn/network、无旧模块/Evidence writer import。

## 4. 关键边界

### 4.1 身份

`workflow_instance_id`、`role`、`preset_version`、`workspace_id`、`episode_id`、
`tool_profile`、`memory_pack`、`approval_ref` 由 host 签发 binding；请求中的同名字段
一律 `identity-in-request`。binding 通过进程内 opaque WeakSet 验证，普通 JSON 对象/
深拷贝不可伪造。

### 4.2 数据

```text
RunLedger  = Fleet operational state；append-only；不是知识库/Evidence
MemoryPack = dsh-memory 只读 snapshot；worker 不持有 memory_write
Evidence   = producer/provenance/scope/admission gate；Fleet 不写、不绕过
```

### 4.3 DSH hook

严格区分：

- `session.promptBeforeInitialize`（handoff 参考 `real-runtime.mjs:183–195`）：
  prompt/session 初始化；**不做**工作目录路径检查。
- `session.wd.beforeInitialize`（`:226–244`）：working-directory 初始化；
  做 canonicalization + containment；**不处理** prompt 语义。

`fleet/test/hooks.test.ts` 分别覆盖两个 hook，并验证把路径塞进 prompt hook 会被拒绝；
把 prompt 塞进 wd hook 会被拒绝。wd hook 的 root 只来自 `workspaceRoots` 受信
registry（`FleetController` 不再提供内置 fallback）；未知/缺失 root、root mismatch、
不存在路径和 realpath/symlink/junction escape 均 fail closed。当前测试用 synthetic
临时目录验证，真实 DSH runtime 仍为 `NOT_RUN`。

### 4.4 旧模块

旧 `agents/`、`providers/`、`routing/`、`composition/` 不参与新 Fleet 路径；
`fleet/src` 静态检查禁止 import。详见
[FLEET_V3_MODULE_DISPOSITION.md](FLEET_V3_MODULE_DISPOSITION.md)。

## 5. 未完成 / 阻塞 / 未运行

- 官方 DSH SDK 静态/API 对照：`BLOCKED`（工作区没有 SDK 源码/包）；接入前必须重新
  对照官方 API 并单独授权。
- 真实 DSH runtime：`NOT_RUN`；没有 handshake/initialize/session prompt/event/cancel。
- 真实 dsh-memory/SecurityLab MCP 连接：`IMPLEMENTED BUT NOT CONNECTED`。
- 真实 provider/model、SecurityLab/vcan/设备实验：`NOT_RUN`。
- durable result store、sidecar/plugin host 部署形态：未实现；当前 in-memory result store。
- `waiting_approval` 状态与 host-internal `grantApproval` 已实现，但 v1 冻结 registry 中所有
  `requires_approval` task 都属于 disabled `lab_runner`，因此本轮公共 API 不可达；保留给
  未来单独授权的 registry 版本。
- 旧 Python 全量测试未运行；旧模块代码未改写/删除。

## 6. 明确声明

- GitHub `main` 已包含首轮 PR #103 的合入（基线 `21fe4e71…`）；本轮改动位于本地
  分支 `fix/fleet-v3-round2-hardening` 的工作树，未 commit/push/merge，未修改远端。
- 未运行真实 DSH SDK/runtime、provider/model 或 SecurityLab/vcan/设备实验。
- 未读取/复制 credential/token/key 文件或环境变量值；未 dump 全量环境。
- path-traversal 测试只做路径计算/containment 断言，未写入被测逃逸目标。
- 未接入 AI-15 Evidence writer/B5；未绕过 producer/admission gate。
- fake-only 测试结果不代表真实 DSH/MCP/Memory/provider 集成通过。

## 7. Round 2 加固（2026-11-01）

| 修正 | 状态 | 实现/证据 |
|---|---|---|
| cwd root trust：unknown/missing root 拒绝；root 只来自 trusted registry；realpath/symlink containment | `IMPLEMENTED`（fake/offline） | `fleet/src/adapters/lifecycle-hooks.ts`, `fleet-controller.ts`, `test/hooks.test.ts` |
| MemoryPack 确定性排序：Unicode code point；合同澄清 | `IMPLEMENTED` | `fleet/src/memory/memorypack.ts`, `test/memorypack.test.ts`, `docs/contracts/MEMORYPACK_V1_1.md` §3/§9 |
| 跨仓库 MemoryPack v1.1 fake acceptance（dsh-memory producer → Workbench schema/semantic/hash） | `IMPLEMENTED`（synthetic fixture） | `fleet/test/cross-repo-memorypack.test.ts`, `test/fixtures/` |
| 状态文档与合并基线更新 | `IMPLEMENTED` | 本文件 |

上述均为离线/synthetic 结果。真实 DSH SDK/runtime、真实 dsh-memory IPC、真实
SecurityLab MCP 进程连接、provider/model 和任何实验仍为 `NOT_RUN` 或
`IMPLEMENTED BUT NOT CONNECTED`；不得把本轮 fake acceptance 写成真实集成通过。
