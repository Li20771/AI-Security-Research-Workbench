# DSH Desktop：SecurityLab MCP + dsh-memory + AgentTeams 角色分工

**日期：** 2026-11-02  
**状态：** 已写入 `profiles/desktop/cordis.patch.yml`；`dsh-memory` 已作为
`link:D:/dsh-memory/plugin` 依赖安装并加入 bundles。运行中的 DSH Desktop 已热加载并
启动 4 个 SecurityLab MCP server。AgentTeams profile、tool policies 与 dsh-memory
工具需在重启/新聊天后验收。  
**性质：** 部署配置，不是 Fleet 控制面；AgentTeams 的 tool policy 是工具可见性策略，
不是 OS sandbox 或授权边界。

## 1. SecurityLab MCP

四个只读 server，每个使用各自的 role binding；server 端独立执行 role allowlist、路径、
路径 containment、输出上限和脱敏：

| serverName | role | tool profile | 工具面 |
|---|---|---|---|
| `securitylab_researcher` | researcher | `researcher_ro_v1` | 5 个只读工具 |
| `securitylab_vehicle_analyst` | vehicle_analyst | `vehicle_analyst_ro_v1` | 5 个只读工具 |
| `securitylab_challenger` | challenger | `challenger_ro_v1` | 4 个只读工具（无 run-result） |
| `securitylab_evidence_verifier` | evidence_verifier | `evidence_verifier_ro_v1` | 5 个只读工具 |

配置与 binding：

```text
C:\Users\20771\.dsh\securitylab-mcp\
  server.json
  bindings\researcher.json
  bindings\vehicle_analyst.json
  bindings\challenger.json
  bindings\evidence_verifier.json
```

MCP client 配置在 `profiles/desktop/cordis.patch.yml` 的 insert 行中；server 仍由
SecurityLab 仓库的 `securitylab_mcp` 拥有。`failOnStartupError: false`，避免一个
MCP server 失败阻断 DSH Desktop 启动；工具缺失时应检查 Python/config/binding。

## 2. dsh-memory 插件

- 以本地 `link:` 依赖安装，不在 `node_modules` 里放手工副本：

  ```json
  "dependencies": { "dsh-memory": "link:D:/dsh-memory/plugin" }
  ```

  同时加入 `dsh.profile.bundles`。这样 DSH 的 plugin manager 执行 pnpm
  install 时会把 `dsh-memory` 当作已声明依赖保留；手工复制的
  `node_modules/dsh-memory` 会被 pnpm 移到 `node_modules/.ignored/` 并
  在下次安装时删除。
- `cordis.patch.yml` 用 `- id: dsh-memory` 覆盖 bundle 插入的同一行，配置：
  `vaultRoot: D:\dsh-memory\kb`。
- 已在真实 DSH SDK session 验证插件加载，注册
  `memory_search`/`memory_write`/`memory_revise`/`memory_review`/
  `memory_forget`/`memory_harvest`/`memory_purge`/`memory_workflow`/
  `memory_stats`/`memory_diagnose` 等工具。
- 读/写权限仍由 dsh-memory 插件自身控制；AgentTeams 成员没有 Fleet 的
  MemoryPack 边界，不能把普通成员输出自动写成长期记忆。

## 3. AgentTeams 角色分工

AgentTeams 配置追加在 `profiles/desktop/cordis.patch.yml`：

- profile id：`security-research`
- `taskPlanning: seed`，任务 DAG：

| task | member | role | 依赖 |
|---|---|---|---|
| `analysis_a` | researcher | researcher | — |
| `analysis_b` | vehicle_analyst | vehicle_analyst | — |
| `challenge` | challenger | challenger | `analysis_a` |
| `verify` | evidence_verifier | evidence_verifier | `challenge` |

- 四个成员分别选择 `tool_policy`：`researcher`、`vehicle_analyst`、`challenger`、
  `evidence_verifier`。
- 每个 policy：
  - 保留本角色的 MCP server 工具；
  - deny 其他三个 SecurityLab server 的全部工具；
  - deny `pwsh`、`write`、`edit`、`web_search`、`web_fetch`（保持 worker 只读；
    Windows 上 `bash` 本来 disabled，故不声明）；
  - deny `memory_write`/`memory_revise`/`memory_review`/`memory_forget`/
    `memory_purge`/`memory_harvest`/`memory_workflow`（worker 不能写共享记忆）。
- `orchestrator` 是 captain，不是 member；`lab_runner` 不加入 profile（当前 disabled）。

## 4. 使用

```text
/agent-teams --profile security-research 检查当前 SecurityLab workspace 的只读安全状态
```

或自然语言：

```text
用 AgentTeams 的 security-research profile 完成只读安全研究，按 researcher、
vehicle_analyst、challenger、evidence_verifier 分工。
```

AgentTeams 会先给出 staged plan；在 Team 面板审查 roster/DAG 后再 **Approve & Run**。

## 5. 验证与限制

已验证：

- `cordis.patch.yml` YAML 可解析；
- 4 个真实 SecurityLab MCP server 已由运行中的 DSH Desktop 启动；
- challenger binding 的 `tools/list` 返回 4 个工具，无 `lab_get_run_result`；
- dsh-memory 插件已在真实 DSH SDK session 加载并注册 10 个 memory_* 工具；
  本机 profile 已声明 `link:D:/dsh-memory/plugin` 并完成 pnpm install；
- AgentTeams 配置已用插件自身的 `Config` schema 校验通过，profile/成员/任务/策略
  均被接受；
- policy 中去除的全局工具名已与 DSH runtime 包核对存在：`pwsh`、`write`、
  `edit`、`web_search`、`web_fetch`；未知的 owner deny 名称会使成员 spawn
  直接失败（AgentTeams 不会静默放宽 owner 策略）。

限制：

- AgentTeams tool policy 不是授权边界；真正权限由每个 SecurityLab MCP server 的
  role binding 在服务端执行。
- 成员仍可使用 read/grep 等全局只读工具；policy 只 deny 了明确的写/shell/web、
  共享记忆写入与其他角色的 MCP server。
- **captain（orchestrator）仍能看到四个 MCP server 的工具**；profile 级 MCP
  server 无法只对成员注册。角色隔离对 member 生效，对 captain 不是强制边界。
- 固定 workspace 为 SecurityLab 仓库；不跟随 DSH 当前 workspace。
- `lab_runner`/vcan、真实 CAN/ECU/车辆/设备仍 disabled/NOT_RUN。
- 角色输出是普通 Agent 文本，不是 Fleet worker-result，也不是 Evidence；不要把
  challenger/verifier 文本自动当作已验证事实。

## 6. 回退

- 配置备份：`profiles/desktop/cordis.patch.yml.bak-securitylab-20261102-194530`
  与 `cordis.patch.yml.bak-dsh-memory-<timestamp>`；package.json 备份
  `package.json.bak-dsh-memory-<timestamp>`。
- 恢复 `cordis.patch.yml` 与 `package.json`（删除 `dsh-memory` 依赖和 bundle 项），
  再执行一次 pnpm install 即可撤销本轮 SecurityLab MCP / AgentTeams profile /
  dsh-memory 配置。`D:\dsh-memory\plugin` 源目录不受影响。
