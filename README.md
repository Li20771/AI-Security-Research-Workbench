# AI Security Research Workbench

DSH Agent Fleet v3.0 的 **控制面**：一个中心化、可审计、权限 fail-closed 的
Orchestrator–Worker 编排层，供 DSH 主 Harness 使用。

本项目与 `SecurityLab`、`dsh-memory` 分离维护，三者职责互不重叠：

- `AI-Security-Research-Workbench`：Fleet 控制面 —— workflow/task/role/preset registry、
  TrustedBinding 与授权、调度、运行生命周期、RunLedger、worker 结果校验，
  以及面向 dsh-memory 与 SecurityLab MCP 的只读 client。
- `SecurityLab`：UDS/CAN/Gateway、固件、测试、实验场景与安全研究本体，并**自己拥有**
  受限只读 MCP server。
- `dsh-memory`：唯一长期语义知识源，向 worker 产出只读 MemoryPack。
- Workbench 可以连接多个研究项目，SecurityLab 只是第一个 workspace，不被 Workbench
  的代码结构绑定。

## 核心定位

Workbench **不是**模型 runtime，**不是**第二套 LLM Agent，**不是** DSH 的 fork。
它不实现 prompt/model loop、provider/router 或原生 subagent 机制；它决定"运行哪一个
固定 role preset、在什么 scope、配什么工具、怎样记录与结束"。

用户只与 DSH Main 对话；DSH Main 通过固定 Fleet API 请求工作流；Fleet 验证身份、角色、
scope、工具与预算，再通过 DSH SDK adapter 管理独立 worker session。

```text
用户
 │ 目标、范围、澄清、审批、最终决定
 ▼
DSH Desktop / DSH Main Agent               用户对话与主推理的唯一 Harness
 │ 仅调用固定 Fleet API；不自授工具权限
 ▼
Workbench：DSH Agent Fleet                 控制面 / workflow 与 worker 生命周期
 ├─ 固定 workflow / task / role / preset registry
 ├─ TrustedBinding、授权检查、approval、budget/timeout/concurrency
 ├─ Fleet API：submit / status / result / cancel
 ├─ DSH Runtime Adapter（当前只有 interface + fake adapter）
 ├─ MemoryPack Client（当前 fake client）
 ├─ SecurityLab MCP Client（当前 fake server/client tests）
 ├─ RunLedger + ResultStore
 └─ worker-result schema 与 role-specific validator
      │                       │
      │ DSH SDK adapter        │ 每角色专用 MCP profile
      ▼                       ▼
角色化、独立 DSH Workers        SecurityLab MCP Server（由 SecurityLab 仓库拥有）
                               ├─ securitylab_ro：只读 catalog/status/file/report/result
                               └─ securitylab_vcan：固定虚拟 suite 接口，当前 disabled
      ▲
      │ 只读 MemoryPack v1.1.0（带 workspace/episode/role/run scope）
      │
`dsh-memory`：唯一长期语义知识源
 ├─ 既有 L1–L4 与 KB 分类
 ├─ visibility/scope 授权先于检索、排序、top-k、citation、diagnostics
 ├─ 主 DSH/Curator 受控写入
 └─ worker 输出仅能形成 pending memory candidate

独立 Evidence 系统：authorized producer → provenance/scope/admission → durable Evidence
Fleet、MemoryPack、worker result 和 RunLedger 都不能绕过或替代 Evidence。
```

### 三种数据绝不混用

| 数据对象 | 用途 | 写入者 | 能否当作 Evidence |
|---|---|---|---|
| RunLedger | Fleet 的 operational state、状态转换、cleanup、结果引用 | Fleet | **不能** |
| Memory / MemoryPack | 经 Curator 控制的可复用知识；pack 是只读 snapshot | 主 DSH/Curator；worker 只读 | **不能** |
| Evidence | 经授权 producer、provenance、scope、admission 验证的 durable facts | 登记且授权的 Evidence producer | 通过 admission 后才可以 |

## 当前实现状态

实现位于 [`fleet/`](fleet/README.md)。每个契约**独立版本化**，版本号互不蕴含：

| 契约 | 版本 |
|---|---|
| Fleet API | `1.0.0` |
| MemoryPack | `1.1.0` |
| SecurityLab MCP | `1.0.0` |
| RunLedger | `1.0.0` |
| DSH runtime adapter | `1.0.0` |
| worker-result | `1.0.0` |

消费方收到不支持的版本必须拒绝，不得"尽力兼容"。共享接口契约位于
[`docs/contracts/`](docs/contracts/README.md)，实施矩阵见
[`docs/architecture/FLEET_V3_STATUS.md`](docs/architecture/FLEET_V3_STATUS.md)。

| 能力 | 状态 |
|---|---|
| 四个固定 Fleet API（submit/status/result/cancel）、registry、state machine、RunLedger | `IMPLEMENTED`（fake-only） |
| DSH runtime adapter | `IMPLEMENTED`（interface + fake）；真实 SDK `NOT_RUN` |
| dsh-memory 连接 | Workbench 侧只读 client `IMPLEMENTED BUT NOT CONNECTED` |
| SecurityLab MCP 连接 | Workbench 侧 client + fake server `IMPLEMENTED BUT NOT CONNECTED` |
| provider/model 调用 | `NOT_RUN` |
| SecurityLab/vcan/CAN/ECU/车辆/设备实验 | `NOT_RUN` |
| AI-15 Evidence writer / B5 | `BLOCKED` / `UNCHANGED` |

- 旧 AI-00–AI-15 文档与 `agents/`、`providers/`、`routing/`、`composition/` 是历史/参考资产，
  不代表新 Fleet 已实现，也不得被新 Fleet import 或调用；处置表见
  [`FLEET_V3_MODULE_DISPOSITION.md`](docs/architecture/FLEET_V3_MODULE_DISPOSITION.md)。
- `lab_runner` 与 `securitylab_vcan` 默认 disabled。
- fake/offline 测试通过**不等于**真实 DSH、MCP、provider、模型或实验环境通过。

## 设计原则

1. **权限不是提示词**：请求体里没有身份/权限字段；身份由 host/Fleet TrustedBinding 签发，
   服务端每次调用独立复核。
2. **人负责最终决策**：worker 可以分析、验证、提出修改，但高影响操作必须经过明确授权。
3. **Evidence > Model Confidence**：模型自信不是证据；测试、日志、diff、Git 状态和
   复现实验才是证据。worker 输出恒为 `untrusted`，`admission: none`、`evidence: false`。
4. **三种数据分离**：RunLedger（运行状态）、MemoryPack（只读知识快照）、Evidence
   （经 admission 的 durable facts）绝不互相替代。
5. **authorization first**：先授权过滤，再查找/排序/计数/截断；显式 scope、`allScopes`
   不能扩大权限。
6. **项目与 Agent 解耦**：Workbench 服务多个 workspace，不把 SecurityLab 逻辑硬编码进 Fleet。
7. **安全边界默认拒绝**：真实车辆、真实 ECU、真实 CAN 总线、敏感系统修改与秘密信息访问
   默认禁止；`lab_runner` / `securitylab_vcan` 保持 disabled。
8. **可审计**：每次运行都能回答"谁、哪个 role/preset、基于哪个 base SHA、用了哪个
   memory snapshot、做了什么、怎样结束、cleanup 是否确认"。
9. **版本化契约先行**：任何 shared field/visibility/error code 变化，先提契约变更再实现；
   消费方遇到未知版本一律拒绝，不做"尽力兼容"。

## Roadmap

新架构的实施顺序与阶段完成标准见
[docs/architecture/FLEET_V3_STATUS.md](docs/architecture/FLEET_V3_STATUS.md)。
旧 [docs/MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md) 属 AI-00–AI-15 历史阶段，不描述 v3.0 路径。

## 当前阶段

旧 AI-00–AI-15 阶段文档保留为历史记录，不再代表当前目标架构。当前 v3.0 Fleet
实施状态、测试矩阵与 `BLOCKED` / `NOT_RUN` 项见
[docs/architecture/FLEET_V3_STATUS.md](docs/architecture/FLEET_V3_STATUS.md)。

按架构手册的完成标准，本仓库目前最多证明**单仓库离线核心**与**跨仓库 fake-first 集成**；
真实 runtime 接入（真实 SDK、真实 session/cancel/cleanup、真实 provider、真实
SecurityLab/vcan/设备）仍需用户单独授权与独立测试计划，不得由 fake 通过推导。

## 文档

- [Master Roadmap](docs/MASTER_ROADMAP.md)
- [AI-00 Requirements & Architecture](docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md)
- [Git & Security Boundary](docs/GIT_AND_SECURITY_BOUNDARY.md)
- [Project Status](docs/PROJECT_STATUS.md)
- [Evidence Lifecycle](docs/architecture/EVIDENCE_LIFECYCLE.md)

## 与 SecurityLab、dsh-memory 的关系

Fleet 与相邻服务之间只有**版本化契约**，没有共享代码：

- **SecurityLab**：SecurityLab 仓库自己拥有受限 MCP server（`securitylab_ro` enabled、
  `securitylab_vcan` disabled）。Fleet 只注册与分配 MCP **工具 profile**，并通过
  MCP client 调用；服务端在每次调用时独立复核 role/workspace/path/output，
  client 侧 allowlist 不是唯一控制。MCP 是 Agent→工具的数据调用协议，不是
  agent-to-agent 通信；本架构不引入 A2A。
- **dsh-memory**：唯一长期共享知识源。Fleet 只持只读 `MemoryPackClient`，接口没有
  `write/update/delete/purge/revise`；worker 只能通过 `memory_candidates` 提出
  pending 提议，由主 DSH/Curator 审核后才可写回。

不要把以下内容反向塞入 Workbench：

- SecurityLab 的 UDS/CAN/Gateway 业务实现、协议测试、固件样本与实验数据
- dsh-memory 的 vault、索引/检索实现或第二套长期记忆存储
- 任何 Evidence producer/admission 逻辑（Fleet 不写 Evidence，也不绕过 gate）

这些分别由 SecurityLab 与 dsh-memory 自己维护。
