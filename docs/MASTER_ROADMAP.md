# AI Security Research Workbench Master Roadmap

> Status baseline: 2026-09-26  
> Project: `Li20771/AI-Security-Research-Workbench`

## 0. Why this project exists

SecurityLab 已经具备独立的研究、测试和工程闭环，但 Agent 能力、模型能力、审计能力、工具编排能力如果继续直接堆进 SecurityLab，会让两个项目逐渐互相绑定。

因此建立独立的 AI Workbench：

- Workbench 负责 **怎么让 Agent 工作**。
- SecurityLab 负责 **研究什么、如何验证研究结果**。

Workbench 应能把同一套 Agent 能力复用于其他安全研究 workspace。

---

# 1. Target Architecture

```text
                         Human
                  architecture / approval
                            |
             +--------------+--------------+
             |                             |
       DSH Main Agent               Codex Second Agent
             |                             |
      model/provider layer          model/provider layer
             |                             |
        +----+----+                   +----+----+
        |         |                   |         |
     DeepSeek    MiMo            OpenAI API   Domestic APIs
        |         |
        +----+----+
             |
     Context / Guard / Evidence
             |
       Research Tool Layer
             |
      Git / GitHub / MCP /
 CAN / ISO-TP / UDS / QEMU / GDB /
      Ghidra / AFL++ / YARA / ...
             |
          Workspace
             |
        SecurityLab
```

## 1.1 Architecture alignment decisions

### Routing boundary

Model Router is a Workbench core service, not a DSH plugin. Router selects eligible Agent/provider/model profiles but never grants permissions. Guard remains authoritative.

### Tool boundary

The first-class tool adapter families are Git, GitHub, Terminal, MCP, Tests, Vehicle Network, Firmware, and Reverse Engineering. The Security Tools plugin composes these adapters.

### Workflow boundary

Long-running execution has a dedicated `workflows/` layer with definitions, checkpoints, runs, and policies. Generated run data is disposable unless promoted to durable Evidence.

### Evidence boundary

Evidence is split into raw run output, normalized durable records, benchmark results, and audit/review records. Key normalized Evidence is durable; large raw logs may be artifact-only.

## 2. Governance model

权限分层：

```text
read
  -> analyze
  -> test
  -> modify
  -> system-change
  -> remote-change
```

默认规则：

- read/analyze 可以低摩擦执行。
- test 必须记录测试对象与范围。
- modify 必须有 Git branch 边界。
- system-change 必须显式批准。
- remote-change 必须显式批准。
- main 不作为 Agent 的默认工作分支。
- 不允许把“模型觉得安全”当成通过条件。

---

# 3. Roadmap

## AI-00 — Requirements / Architecture Freeze

目标：冻结整个 Workbench 的边界与长期架构。

交付：

- 项目定位
- Agent 角色
- Provider / Model 抽象
- Plugin 边界
- Tool 权限模型
- Security Guard 原则
- Evidence / Audit 数据结构
- Workspace / Context 模型
- Git 安全约束
- 长期演进路线

状态：**当前阶段**

---

## AI-01 — DSH Baseline

目标：让 DSH 成为主 Agent 平台的可重复基线。

范围：

- 安装/启动方式记录
- 工作区绑定
- 配置持久化
- 基础插件机制确认
- 基础 Agent 行为回归
- 稳定能力与实验能力分层
- 回滚点与基线记录

出口条件：

- 能从干净环境复现 DSH 基线。
- 能确认 Agent、工具、插件的实际行为。
- 有可回退配置。

---

## AI-02 — DeepSeek + MiMo Model Layer

目标：建立与 Agent 平台解耦的模型层。

规划：

- DeepSeek V4.1
- MiMo-V2.6
- provider/model 双层抽象
- 统一模型能力描述
- 上下文与工具调用能力记录
- 成本/延迟/稳定性指标采集

原则：

- 不把“默认模型”写死成永久架构。
- 不以宣传 benchmark 作为唯一选型依据。
- 通过 Workbench 自己的任务 benchmark 得出路由数据。

---

## AI-03 — Context Plugin

目标：让 Agent 不依赖聊天记录获得项目上下文。

Context 优先级：

```text
Git repository state
    >
Master Roadmap
    >
Capability Inventory
    >
Design Freeze
    >
Exit Reports
    >
Git history / current diff
    >
Disposable AI cache
```

要求：

- 结构化提取项目状态
- 自动识别当前 branch / SHA
- 加载任务相关文档
- 区分当前事实、历史事实、设计计划
- AI cache 可删除并可重建

---

## AI-04 — Security Guard Plugin

目标：把安全约束从“提示词建议”升级为可执行约束。

第一版必须保护：

- main/master 分支
- Git history
- secrets / tokens / private keys
- sudo 与系统配置
- 真实 CAN / ECU / vehicle
- 不受控远程操作
- 破坏性文件操作

车辆网络实验边界：

- 默认只允许 vcan / 仿真链路。
- 真实 CAN、真实 ECU、真实车辆必须进入显式批准流程。

测试状态规则：

```text
PASS      = test executed + evidence available
FAIL      = executed + assertion failed
BLOCKED   = required environment/action unavailable
NOT RUN   = intentionally not executed
UNKNOWN   = insufficient evidence
```

禁止把 SKIPPED / BLOCKED 自动折算为 PASS。

---

## AI-05 — Evidence / Audit Plugin

目标：每个 Agent 任务都能形成可复核的实验记录。

核心字段：

```text
Experiment ID
Agent
Provider
Model
Workspace
Base SHA
Working Branch
User Approval
Tool Calls
Changed Files
Tests
Results
Git Diff
Final Status
Timestamp
```

审计要求：

- 记录关键工具调用
- 记录变更前后的 Git 状态
- 记录验证命令及结果
- 记录阻塞项
- 支持后续 benchmark 消费这些数据

---

## AI-06 — Security Research Tools Plugin

目标：将安全研究中高频工具抽象成统一 Tool API。

第一批：

- Git / GitHub
- test runners
- Terminal
- MCP
- vcan
- can-utils
- ISO-TP / UDS
- capture / replay
- QEMU
- GDB
- Ghidra
- AFL++
- YARA
- firmware utilities

原则：

- Tool 是能力，不是权限。
- Guard 决定 Tool 在当前上下文能否执行。
- Tool 输出必须能成为 Evidence。

---

## AI-07 — Plugin 5: Model Router v1

> Planning identity: Plugin 5. Architectural classification: Workbench core service, not a DSH plugin.

目标：建立可解释的规则路由，不追求一开始就做自主学习路由。

初版原则示例：

```text
simple / high-frequency -> fast / low-cost model
complex repo / security -> stronger model
multimodal -> multimodal-capable model
second opinion -> independent Agent
```

注意：

- 规则可配置
- 路由决策可记录
- 高影响操作不允许仅因为 Router 选择了某模型而自动放权

---

## AI-08 — Codex Second Agent

目标：把 Codex 建成独立的第二 Agent，而不是 DSH 子进程或 DSH 内部模型。

设计：

```text
DSH = primary execution / orchestration
Codex = independent reviewer / second execution path
```

要求：

- 独立上下文
- 独立结果
- 独立工具权限记录
- 不共享未验证的模型判断

---

## AI-09 — Domestic Models for Codex

目标：利用 Codex 的 provider abstraction 接入其他 OpenAI-compatible API。

要求：

- provider profile 独立
- secret 不入 Git
- model capability 记录
- tool calling compatibility test
- structured output compatibility test
- timeout / retry / context handling test

---

## AI-10 — Cross-Agent Review

目标：建立真正的“第二意见”闭环。

推荐流程：

```text
Task
  |
DSH analysis
  |
independent Codex analysis
  |
executable verification
  |
human decision
  |
Evidence
```

禁止：

- 只比较两段自然语言谁更像“正确答案”
- 用多数票替代执行验证
- 让一个 Agent 直接把另一个 Agent 的结论当成事实

---

## AI-11 — AI Security Benchmark

目标：用真实 SecurityLab 任务建立 Workbench 自己的数据。

指标方向：

- task success
- test pass rate
- false pass / false claim
- tool-call correctness
- patch quality
- regression rate
- token / cost
- latency
- recovery rate
- security-boundary violations

模型比较只输出测量结果，不输出脱离任务场景的“万能排名”。

---

## AI-12 — Model Routing v2

目标：在 benchmark 数据基础上改进路由。

输入：

- task type
- historical success
- tool use reliability
- cost
- latency
- failure patterns

输出：

- task-to-model policy
- fallback policy
- escalation policy

仍保持：

- 可解释
- 可审计
- 可回退

---

## AI-13 — Long-running Workflows

目标：支持可恢复的长任务。

能力：

- checkpoint
- resume
- timeout
- retry
- failure classification
- resource limits
- human approval points

不允许：

- 无限循环
- 无限重试
- 无限制后台执行
- 绕过 Guard 获得更高权限

---

## AI-14 — Long-term AI Workbench

最终形态：

- 多 Agent
- 多 Provider
- 多 Workspace
- 插件系统
- 可解释路由
- 安全 Guard
- Evidence / Audit
- Benchmark
- 长任务工作流

目标不是“自动化一切”，而是建立一个**可验证、可审计、可扩展的安全研究 Agent 工作台**。

---

# 4. Dependency Map

```text
AI-00
 |
 +--> AI-01
 |     |
 |     +--> AI-02
 |     +--> AI-03
 |     +--> AI-04
 |     +--> AI-05
 |     +--> AI-06
 |
 +--> AI-07 -----> AI-12
 |
 +--> AI-08 -----> AI-09
 |                  |
 |                  +--> AI-10
 |
 +--------------------> AI-11
                           |
                           +--> AI-12
                           |
                           +--> AI-13
                                 |
                                 +--> AI-14
```

说明：AI-02~06 属于基础能力区，可以在基线稳定后并行推进；AI-10 需要 AI-08/09 与验证能力；AI-12 必须建立在 AI-11 的真实数据上。

---

# 5. Workspace Boundary

Workbench 不拥有 SecurityLab 的研究事实。

```text
AI Workbench
  - Agent
  - Model
  - Provider
  - Plugin
  - Tool adapter
  - Guard
  - Evidence
  - Benchmark
  - Workflow

SecurityLab
  - UDS
  - CAN
  - Gateway
  - Firmware
  - Tests
  - Fuzzing
  - Architecture
  - Research evidence
```

二者通过受控接口连接。

---

# 6. Current Status

| Stage | Status |
| --- | --- |
| AI-00 | **IN PROGRESS** |
| AI-01 | NOT STARTED |
| AI-02 | NOT STARTED |
| AI-03 | NOT STARTED |
| AI-04 | NOT STARTED |
| AI-05 | NOT STARTED |
| AI-06 | NOT STARTED |
| AI-07 | NOT STARTED |
| AI-08 | NOT STARTED |
| AI-09 | NOT STARTED |
| AI-10 | NOT STARTED |
| AI-11 | NOT STARTED |
| AI-12 | NOT STARTED |
| AI-13 | NOT STARTED |
| AI-14 | NOT STARTED |

---

# 7. Definition of Done for the whole Workbench

最终必须同时满足：

1. Agent 能工作。
2. 模型可以替换。
3. Provider 可以替换。
4. Plugin 可以扩展。
5. Tool 能执行研究任务。
6. Guard 能阻断越权行为。
7. Evidence 能复现关键过程。
8. Benchmark 能量化表现。
9. Workspace 可以独立接入。
10. 长任务可以恢复。
11. 任何高影响动作都有明确的人类批准边界。

