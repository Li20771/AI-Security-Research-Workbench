# DSH SDK 静态/API 对照（C 阶段）

**对照日期：** 2026-11-02  
**官方基线：** `deepseek-ai/deepseek-harness` tag `dsh-v0.2.1-rc.2`  
**官方包：** `@deepseek-ai/dsh@0.2.1-rc.2`、`@deepseek-ai/dsh-sdk-client@0.2.1-rc.2`  
**性质：** 静态源码/API 对照 + 离线 fake SDK 验证；真实 runtime/provider 结果另行记录。

## 1. 官方 SDK 的事实

- `@deepseek-ai/dsh-sdk-client` 通过 **stdio JSON-RPC 启动 `dsh --profile sdk` 子进程**；不是进程内库。
- 高层 `DeepSeekHarness`：`start()`、`session(id?)`、`run(input, options?)`、`close()`。
- 低层 `HarnessClient`：`initialize({cwd, provider, model, ...})`、`prompt()`、`request('session/wait')`、working-directory get/set、`close()`、通知订阅。
- `initialize` **必须**传 `provider` 与 `model`。
- **没有轮次中 cancel**；放弃轮次只能关闭 runtime。
- `HarnessClientOptions.env` 是**整体替换**；省略会继承完整父进程环境。
- `HarnessClientOptions.dshHome` 指向 DSH home；不隔离会复用用户历史/凭据。
- `run()` 返回 `RunResult`，其中 `finalResponse` 是最后一条 assistant 文本，不是 Fleet 的 `worker-result.v1`。

## 2. 映射到 `DshRuntimeAdapter`

| Fleet adapter | 官方 SDK 映射 | 备注 |
|---|---|---|
| `openSession(request)` | `create harness` + `start()` + `initialize({cwd, provider, model})` | provider/model/dshBin/profile/patches/env 来自受信部署配置 |
| `runSession(handle, run)` | `harness.session(sessionId).run(prompt)` | prompt 包含 trusted context + role 指令 + untrusted task JSON |
| `cancelSession(handle)` | `harness.close()` | 无原生 cancel；close 成功才报告 `cleaned` |
| `closeSession(handle)` | `harness.close()` | close 后删除该 run 的临时 home |
| `health(handle?)` | adapter 本地状态 | SDK 无 health API |

## 3. 已实现的 C 边界

- `fleet/src/adapters/dsh-sdk-port.ts`：窄 port，Fleet 不直接 import 官方 SDK。
- `fleet/src/adapters/real-dsh-adapter.ts`：
  - 每 run 一个临时 `DSH_HOME`，close 后删除；
  - 子进程环境只由受信部署 allowlist 构造，不读 ambient environment；
  - `provider/model/dshBin/profile/patches` 只从部署配置读取，请求/模型不能覆盖；
  - `memory_pack.episode_id` 等仍由 Fleet binding 校验；adapter 只接收已校验的 session request；
  - strict JSON：只接受 `finalResponse` 为 JSON object；否则返回原文，由 Fleet 的 `worker-result` validator 拒绝；
  - cancel 走 close；close 或 home 清理失败时返回 `cleaned=false`/`closed=false`，由 Fleet 标 `blocked`。
- 部署 wrapper（`_c-runtime/official-factory.ts`）负责把 port 映射到官方 `DeepSeekHarness`。
- Worker profile overlay 关闭 shell、filesystem 写、web、subagent、jobs、workflow/PTCA 工具。

## 4. 尚未接通的 C 部分

- **MemoryPack 内容**：`DshSessionRequest` v1.1.0 已增加只读 `memory_pack_entries`；Fleet controller 从受信 MemoryPack client 读取 pack，校验 contract version、snapshot、scope、role、run 后交给 adapter。C smoke 使用真实 dsh-memory producer（synthetic vault，in-process library）；dsh-memory 的独立 service/IPC 模式和真实用户 vault 仍未连接。
- **MCP profile**：`tool_profile`/`mcp_server` 由 Fleet 逻辑字段映射到部署侧 DSH MCP patch；`RealDshAdapter` 每个 run 生成 `mcp-binding.json` 与 `mcp.patch.yml`，由 `@deepseek-ai/dsh-mcp-client` 启动真实 SecurityLab stdio server。C smoke 已调用 `mcp__securitylab_ro__lab_status`；Workbench 自带的 fake MCP client 仍只用于离线单测。
- **真实 provider/model**：C smoke 使用受信部署 route；provider/model 选择不属于 Fleet，Fleet 只传递部署配置。
- **真实 session 验收**：已在限定环境执行 initialize/prompt/cancel/cleanup；真实 path/env/profile 负向测试与 Linux CI 仍未执行。

## 5. 验证

离线：

```text
Workbench TypeScript typecheck                 PASS
Workbench Fleet fake tests                     PASS  95 passed / 0 failed / 0 skipped
RealDshAdapter fake SDK tests                  PASS  8 passed
```

真实 C runtime smoke（2026-11-02，限定环境）：

```text
官方 SDK/runtime: @deepseek-ai/dsh@0.2.1-rc.2
                  @deepseek-ai/dsh-sdk-client@0.2.1-rc.2
部署 route:       tokenrhythm / deepseek-flash（llm-pi-ai，OpenAI-compatible）
凭据:             TOKENRHYTHM_API_KEY（DSH credential store；仅子进程 env）
隔离:             per-run temp DSH_HOME，close 后删除
maxTokens:        2048（512 在 challenger 上产生空 finalResponse）
MemoryPack:       dsh-memory v1.1.0 producer, synthetic vault, 2 entries;
                  createPackRef == getPack snapshot hash
SecurityLab MCP:  real stdio server per run via @deepseek-ai/dsh-mcp-client;
                  analysis_a called mcp__securitylab_ro__lab_status
                  -> ready / execution disabled / vcan disabled
analysis_a:       completed, untrusted=true, admission=none, evidence=false
challenge:        completed, findings=1
verify:           completed, verdicts=1
RunLedger:        21 events, hash-chain verify=true
cancel:           cleaned=true, pending run rejected, health=closed
```

该结果证明真实 SDK 子进程、initialize、prompt、模型调用、严格 JSON、
真实 dsh-memory producer pack 传递、真实 SecurityLab MCP stdio 工具调用、
Fleet worker-result 校验、RunLedger 和 close/cancel cleanup 在指定环境可用；
不证明 dsh-memory 独立 service/IPC、真实用户 vault、MCP 负向路径/identity/
disabled-tool 测试、Linux/其他平台或全部负向安全测试通过。
