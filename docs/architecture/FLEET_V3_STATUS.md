# DSH Agent Fleet v3.0 — 实施状态

**仓库审计基线：** `1d3c5252bf554ef299aa744ba9d8dcfa9fd6cd19`（GitHub `main`，2026-11-02）
**审计修正：** 按《DSH_AGENT_FLEET_V3_UNIFIED_ARCHITECTURE.md》v3.0 回退未授权的 MemoryPack v1.2.0 与 AI-15 OPEN-1 signing 代码；改动位于本地工作树，尚未 commit/push/merge
**实施日期：** 2026-10-30 首轮；2026-11-01 round 2 加固；2026-11-02 架构基线对齐
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
| `docs/contracts/DSH_SDK_ADAPTER_V1.md` | 1.1.0 | FROZEN / fake adapter + RealDshAdapter IMPLEMENTED；限定环境 C smoke PASS |
| `docs/contracts/*.schema.json`（14 个） | 1.0.0 / 1.1.0 | FROZEN / Ajv validated |
| `docs/contracts/examples/*`（14 个，含 7 条 RunLedger 事件） | 1.0.0 / 1.1.0 | FROZEN / Ajv validated |

一致副本：`D:\claude-work\DSH-Fleet-v3\brief\contracts\`。版本不一致时消费方必须拒绝。
MemoryPack 1.1.0 只允许显式 `user-global` 跨 workspace；无显式 visibility 的旧记录
不进入 worker pack，只能由 Curator 通过只读迁移清单确认后迁移；路径为 NFC Unicode。

**2026-11-02 架构对齐：** GitHub `main` 曾把 MemoryPack 提升到 `1.2.0`；v3.0 架构文档
规定当前契约为 `1.1.0`，且任何共享字段/版本变更必须先获用户批准。该未经批准的
`1.2.0` 文件、schema、example、fixture 与消费代码已在本轮工作树回退；本仓库当前
工作树只保留 `1.0.0`（历史）与 `1.1.0`（当前）。

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
| 真实 official DSH SDK adapter/API 静态对照 | `IMPLEMENTED` | `docs/architecture/DSH_SDK_STATIC_COMPARISON.md`；官方 `0.2.1-rc.2` 源码/包已确认 |
| 真实 DSH SDK port + `RealDshAdapter`（fake SDK tests） | `IMPLEMENTED` | `fleet/src/adapters/dsh-sdk-port.ts`, `real-dsh-adapter.ts`, `test/real-dsh-adapter.test.ts` |
| 真实 DSH session/prompt/cancel/cleanup（C runtime smoke） | `PASS`（限定环境，见 §10） | 官方 SDK `0.2.1-rc.2` + 受信部署 tokenrhythm route；真实 dsh-memory producer/MCP 已接入 C smoke；独立 service/IPC 仍未连接 |
| 真实 dsh-memory producer（in-process） | `IMPLEMENTED`（C smoke） | 部署 client 导入真实 dsh-memory MemoryPack producer；只读 entries 经 Fleet 校验后进入 session；独立 service/IPC 仍 `NOT_RUN` |
| 真实 SecurityLab MCP server（C smoke） | `IMPLEMENTED` | 部署侧 DSH MCP client 启动真实只读 stdio server；per-run binding/patch；analysis_a 调用 `mcp__securitylab_ro__lab_status` |
| Workbench 旧 provider/model 调用面 | `NOT_RUN`（**调用面已移除**） | live runner、`http_transport.py`、live workflow、`tests/live/` 已删除；Layer 0 强制不得回归 |
| DSH SDK runtime model call（C smoke） | `PASS`（受信部署 route） | 不属 Fleet 职责；由 DSH runtime 调用，route 由受信部署配置提供；见 §10 |
| SecurityLab/vcan/CAN/ECU/车辆/设备实验 | `NOT_RUN` | `lab_runner` / `securitylab_vcan` disabled |
| AI-15 Evidence writer / B5 | `BLOCKED / UNCHANGED` | Fleet 不写 Evidence，不绕过 producer/admission |
| 旧 Python 全量测试套件 | `NOT_RUN` | 本轮只运行新增 Fleet 离线 tests；旧测试保留 |

## 3. 测试矩阵（本地，离线）

运行时：Node `v22.23.4`；TypeScript `5.9.3`；Ajv `8.20.0`。

```text
TypeScript typecheck                         PASS  0 errors
Fleet fake tests (node:test)                 PASS  99 passed / 0 failed / 0 skipped
Contract schema/examples check               PASS  14 schemas / 13 JSON examples / 7 ledger events（14 个示例文件）
Cross-repo MemoryPack v1.1 fixture           PASS  2 passed（dsh-memory producer 产物由 Workbench schema/hash 校验）
Linux CI: Workbench fleet workflow           PASS  typecheck + fake tests + contracts
Linux CI: dsh-memory memory workflow         PASS  offline tests（含 symlink/path cases）
Linux CI: SecurityLab CI                     PASS  fast QA（ruff + mypy + offline tests）
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
- MemoryPack delivery fail closed：无 client、snapshot/hash、contract version、workspace
  或 run scope 不匹配时，worker session 不启动且 run failed。
- MCP delivery fail closed：未配置 server、args 缺少 `{binding}` 时拒绝启动；per-run
  binding 包含 run/role/workspace/episode/tool_profile。
- SecurityLab 真实角色矩阵（`test_service.py::test_role_tool_surface_and_denials`）：
  六个角色的工具面、`tool-not-allowed`、traversal、`identity-in-args`、
  challenger 无 run-result、`lab_runner` vcan `tool-disabled` 且 `side_effects=0`。
- MemoryPack 确定性：Unicode code point 排序、`snapshot_hash` 与输入顺序无关、
  locale 无关；hardcoded hash 锁定顺序规则。
- 跨仓库 fake acceptance：`test/cross-repo-memorypack.test.ts` 校验 dsh-memory
  producer 生成的 synthetic pack（schema、NFC、entry sha256、snapshot hash、
  `excluded`、`policy.cross_workspace`），并验证篡改/未知版本会被拒绝。
- 跨仓库端到端 fake run：`test/cross-repo-e2e.test.ts` 用 dsh-memory v1.1 pack
  作为 binding、在 worker 中调用 SecurityLab fake MCP 只读工具，验证身份/scope、
  工具执行、untrusted result、RunLedger 与跨 workspace canary 不泄露。
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
深拷贝不可伪造。`memory_pack.workspace_id` 必须等于 binding workspace，
`memory_pack.episode_id` 必须与 binding `episode_id` 完全一致（`null` 与具体 episode
不是同一 scope；workspace-wide pack 不得满足 episode-bound worker run）。

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

旧 `agents/`、`providers/` 不参与新 Fleet 路径；`routing/` 与 `composition/` 已于 2026-11-02 删除；
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

- 本轮审计基线为 GitHub `main` `1d3c525…`（已包含 PR #103、round-2 PR #104 及其后
  的文档/契约提交）；本轮的架构对齐修正位于本地工作树，未 commit/push/merge，未修改远端。
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

## 8. 架构基线对齐（2026-11-02）

| 偏差 | 处置 | 架构依据 |
|---|---|---|
| MemoryPack 契约被提升到 `1.2.0`，新增 `excluded.unspecified_layer`，Workbench 与 dsh-memory 同步消费 | 在本轮工作树回退到 `1.1.0`；删除 v1.2 合同/schema/example/fixture 与消费代码；跨仓库 fixture 恢复为 v1.1.0 并保持与 dsh-memory producer byte-identical | §2.4 当前 MemoryPack 契约 `1.1.0`；§14.2 共享字段变更须先获用户确认并版本化 |
| 合入 AI-15 OPEN-1 phase 3A `plugins/security_tools/signing.py`、错误类型与测试（dormant，无调用点） | 在本轮工作树回退该提交；保留既有 AI-15 legacy 文档/代码，不新增 Evidence writer 能力 | §12.1 / §16：AI-15 Evidence writer/B5 为 `BLOCKED/UNCHANGED`；§13.1 旧 AI 路径仅作 legacy/reference |
| MemoryPack binding 只比较 workspace；episode-bound run 可接受 `episode_id: null` 的 workspace-wide pack，scope 被放宽 | 改为 `memory_pack.episode_id` 与 binding `episode_id` 完全一致；新增双向 mismatch 测试 | §3.3 `pack workspace` 必须相同、`episode` 不可不一致；§5.3.1 step 7 |

回退后的离线验证：

```text
TypeScript typecheck                         PASS
Fleet fake tests (node:test)                 PASS  99 passed / 0 failed / 0 skipped
Contract schema/examples check               PASS  14 schemas / 13 JSON examples / 7 ledger events
Cross-repo MemoryPack v1.1 fixture           PASS  2 passed（fixture 与 dsh-memory 产物 byte-identical）
Cross-repo end-to-end fake run               PASS  1 passed（dsh-memory pack + SecurityLab fake MCP + Fleet）
```

真实 DSH SDK/runtime、真实 dsh-memory IPC、真实 SecurityLab MCP 进程连接、
provider/model 和任何实验仍为 `NOT_RUN` 或 `IMPLEMENTED BUT NOT CONNECTED`。

## 9. C 阶段：官方 DSH SDK 对照与 RealDshAdapter

详见 [DSH_SDK_STATIC_COMPARISON.md](DSH_SDK_STATIC_COMPARISON.md)。

已实现（`IMPLEMENTED`，fake SDK tests）：

- `fleet/src/adapters/dsh-sdk-port.ts`：官方 SDK 的窄 port；Fleet 不直接 import 官方包。
- `fleet/src/adapters/real-dsh-adapter.ts`：每 run 临时 `DSH_HOME`、显式 env allowlist、
  受信 deployment profile/route、strict JSON `finalResponse`、close 即 cancel、
  close/home 清理失败返回 false。
- `fleet/test/real-dsh-adapter.test.ts`：8 个 fake SDK 测试。

真实 SDK 静态对照：

- 官方 tag `dsh-v0.2.1-rc.2`、`@deepseek-ai/dsh@0.2.1-rc.2`、
  `@deepseek-ai/dsh-sdk-client@0.2.1-rc.2`。
- `initialize` 必须传 provider/model；没有轮次中 cancel；`env` 整体替换；
  `dshHome` 决定历史/凭据；`finalResponse` 是文本不是 `worker-result.v1`。
- provider/model 不属于 Fleet 选择；由受信部署配置提供，Fleet 只传递。

## 10. C runtime smoke（2026-11-02，限定环境）

**环境：** Node `v22.23.4`；官方 `@deepseek-ai/dsh@0.2.1-rc.2` 与
`@deepseek-ai/dsh-sdk-client@0.2.1-rc.2`；受信部署 route 为
`tokenrhythm / deepseek-flash`（`llm-pi-ai`，OpenAI-compatible）；`maxTokens=2048`
（512 在 challenger 上产生空 finalResponse，故使用预设上限内的 2048）。
凭据来自现有 DSH credential ref `TOKENRHYTHM_API_KEY`，只通过子进程 env 传递，
未打印、未写入 ledger。每 run 使用独立临时 `DSH_HOME`，close 后删除。
Smoke runner 是部署 glue（位于 Fleet 包外），Fleet 不依赖官方 SDK 包。

**结果：**

```text
MemoryPack producer     dsh-memory v1.1.0, synthetic vault, 2 entries
                        createPackRef == getPack snapshot (hash match)
SecurityLab MCP         real stdio server per run; analysis_a called
                        mcp__securitylab_ro__lab_status -> ready/disabled/disabled
research/analysis_a   completed  untrusted=true admission=none evidence=false
research/challenge    completed  untrusted=true admission=none evidence=false  findings=2
research/verify       completed  untrusted=true admission=none evidence=false  verdicts=1
RunLedger             21 events, hash-chain verify=true
cancel (in-flight)    cleaned=true, pending run rejected, health=closed
```

MemoryPack entries 由真实 dsh-memory producer 生成（synthetic vault，不使用真实
vault），经 Fleet controller 校验 snapshot/scope/role/run 后传入 worker；模型在
challenge/verify 输出中引用了这些 synthetic canary。SecurityLab MCP 由部署侧
`@deepseek-ai/dsh-mcp-client` 以 per-run binding/patch 启动真实只读 stdio server；
analysis_a 调用了 `mcp__securitylab_ro__lab_status` 并得到 ready/disabled/disabled。
三个角色均通过真实 SDK 子进程、真实模型调用、严格 JSON 解析和 Fleet
`worker-result` 校验；worker overlay 关闭 shell/filesystem/web/subagent/jobs。
成功 run 的 ledger 只记录 metadata/hash/ref，不记录 prompt、raw output、memory body
或 MCP 参数/结果原文。

**仍未完成的 C 项：**

- dsh-memory 独立 service/IPC 模式（当前是部署侧导入真实 producer library；
  非进程间服务；真实用户 vault 未使用）；
- MCP 的负向路径/identity/disabled-tool 真实测试与每个 role 的工具面审计
  （SecurityLab 离线 role matrix 已 PASS；真实 DSH 内逐 role 负向调用仍待补）；
- 真实 path/env/profile 负向 DSH 测试（Linux CI 已跑 Fleet fake tests、
  dsh-memory 与 SecurityLab 离线 suites）；
- 真实 provider/model 的独立费用/网络边界确认。

旧 Python 全量测试与旧 UI 审计仍为 `NOT_RUN`；不在 Fleet v3 完成标准内。
