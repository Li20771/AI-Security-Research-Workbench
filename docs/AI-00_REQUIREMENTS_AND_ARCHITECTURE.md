# AI-00 — Requirements & Architecture Freeze

> Status: **IN PROGRESS**
> Date baseline: **2026-09-26**

## 1. Problem Statement

当前我们需要的不是“再找一个更强的模型”，而是一套可以长期使用的 AI Agent 工作环境。

这个环境需要同时解决：

- 多 Agent
- 多模型
- 多 Provider
- 安全工具调用
- 项目上下文持久化
- Git 安全
- 研究证据
- 可恢复工作流
- 模型/Agent benchmark

因此 Workbench 被定义为一个独立系统。

---

## 2. Non-goals

AI-00 不做：

- DSH 核心 fork
- SecurityLab 协议代码修改
- 自动接入真实车辆
- 自动接管真实 ECU
- 自动修改主机系统
- 自动推断或储存 secrets
- 建立“一个模型解决全部任务”的固定架构
- 直接实现 AI-14 全部能力

---

## 3. Agents

### 3.1 DSH

定位：**Primary Agent**

职责：

- 主工作流
- 任务分解
- 工具调用
- Provider / Model 路由
- workspace context
- 常规研究执行

DSH 不是永久绑定到单一模型。

---

### 3.2 Codex

定位：**Independent Second Agent**

职责：

- 第二实现路径
- 独立代码审查
- 第二意见
- 交叉验证

Codex 不作为 DSH 的“一个子模型”。

---

## 4. Model / Provider abstraction

必须区分：

```text
Agent
  |
Provider
  |
Model
```

例如：

```text
DSH
  -> DeepSeek provider -> deepseek-flash
  -> MiMo provider     -> MiMo model

Codex
  -> OpenAI provider
  -> domestic OpenAI-compatible provider
```

Provider 负责：

- endpoint
- authentication
- protocol compatibility
- transport settings

Model 负责：

- model id
- capability metadata
- context/output limits
- tool calling capability
- structured output capability

Secret 只存在于运行时环境或安全凭证系统，不进入 Git。

---

## 5. Plugin architecture

采用 **plugin-first**。

第一批逻辑插件：

### Context Plugin

负责：

- Git state
- project docs
- roadmap
- inventories
- design freeze
- exit reports
- task context

### Guard Plugin

负责：

- permission checks
- branch checks
- vehicle-network safety
- system-change approval
- secret protection
- fail-closed behavior

### Evidence Plugin

负责：

- Experiment ID
- Agent
- Provider / Model
- SHA
- branch
- tools
- tests
- results
- diff
- approval
- final status

### Research Tools Plugin

负责：

- Git/GitHub
- test
- vcan
- CAN/ISO-TP/UDS
- replay/capture
- QEMU
- GDB
- Ghidra
- AFL++
- YARA
- firmware tooling

---

## 6. Permission Model

权限必须单向升级：

```text
read
  < analyze
  < test
  < modify
  < system-change
  < remote-change
```

### read

读取文件、Git 状态、文档、公开数据。

### analyze

静态分析、代码审查、结构分析。

### test

执行限定测试与仿真操作。

### modify

修改工作分支中的文件。

### system-change

修改系统、服务、内核相关配置。

必须显式批准。

### remote-change

push、merge、部署、远程执行等。

必须显式批准。

---

## 7. Vehicle Security Boundary

默认环境：

```text
Agent
  |
Safety Guard
  |
vcan0 / simulator
```

默认禁止：

- real CAN interface
- real vehicle
- real ECU
- unknown external CAN gateway
- uncontrolled ECU flashing
- physical actuation

任何例外都不能通过“提示词约定”实现，而必须由可执行 Guard 控制。

---

## 8. Git Safety Boundary

默认：

```text
main
  |
  +-- feature / experiment branch
       |
       +-- Agent changes
       +-- tests
       +-- evidence
```

规则：

- Agent 默认不能直接修改 main。
- 不允许无批准的 history rewrite。
- 修改前记录 base SHA。
- 修改后记录 diff。
- merge 是人类决策点，或进入明确批准的自动化策略。
- 所有实验必须能够定位到 branch + commit。

---

## 9. Evidence Model

每个研究任务生成一个 Experiment Record。

最小模型：

```yaml
experiment_id: EXP-YYYYMMDD-XXXX
agent: dsh
provider: <provider>
model: <model>
workspace: <workspace>
base_sha: <sha>
branch: <branch>
approval: <approval-id-or-none>

tools:
  - name: <tool>
    action: <action>
    result: <summary>

changes:
  files: []
  diff_summary: ""

tests:
  - command: <command>
    status: PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN
    evidence: <reference>

final_status: PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN
timestamp: <timestamp>
```

---

## 10. Truth Model

Workbench 内部必须区分：

| State | Meaning |
| --- | --- |
| PASS | 已执行且有支持证据 |
| FAIL | 已执行且失败 |
| BLOCKED | 所需动作/环境受限 |
| NOT_RUN | 有意未执行 |
| UNKNOWN | 证据不足 |

任何 Agent 文本中的“应该成功”都不能自动映射到 PASS。

---

## 11. Context Persistence

聊天窗口不是事实源。

优先级：

```text
Git repository state
>
master roadmap
>
capability inventory
>
design freeze
>
exit reports
>
Git history / current diff
>
disposable AI cache
```

AI cache 必须：

- 可删除
- 可重建
- 不能成为唯一事实源

---

## 12. Routing Principles

### v1

采用规则路由：

- simple/high-frequency -> fast model
- complex repo/security -> stronger model
- multimodal -> multimodal model
- independent review -> second Agent

每次路由都应可记录。

### v2

只有在 benchmark 建立后，才引入：

- success history
- failure patterns
- cost
- latency
- task-specific routing

---

## 13. Cross-Agent Review

必须遵守：

```text
Agent A
  +
Agent B
  +
Executable verification
  +
Human decision
  =
Evidence-backed result
```

不采用：

- “谁说得更像真的”
- “两边一致所以一定正确”
- “模型置信度最高所以通过”

---

## 14. Benchmark

Benchmark 不比较“谁更聪明”，而比较任务数据：

- success
- correctness
- regression
- security violations
- false pass
- tool-call correctness
- cost
- latency
- recovery

结果用于 Routing v2。

---

## 15. Repository status

AI-00 remains IN PROGRESS. Repository foundation and architecture alignment are complete; AI-01 DSH baseline execution and GitHub main protection verification remain open.

## 16. Architecture Freeze Decisions

当前冻结：

### F-01

Workbench 是独立 GitHub repository。

### F-02

SecurityLab 是独立 workspace，不是 Workbench 的子目录。

### F-03

DSH 是 Primary Agent。

### F-04

Codex 是 Independent Second Agent。

### F-05

DeepSeek 与 MiMo 属于可替换 Model/Provider 层。

### F-06

插件采用 plugin-first，不 fork DSH 核心。

### F-07

Guard、Evidence、Context 是 Workbench 的核心基础能力。

### F-08

Vehicle security experimentation 默认只允许仿真/vcan 边界。

### F-09

main/system-change/remote-change 不属于默认 Agent 权限。

### F-10

Evidence 优先于模型置信度。

### F-11

AI cache 不能成为唯一事实源。

### F-12

Model routing v2 必须建立在真实 benchmark 数据上。

### F-13

Model Router is a Workbench core service and never grants permissions.

### F-14

Research tool adapters are separate from the Security Tools plugin.

### F-15

Key normalized Evidence is durable; raw logs and AI caches may be disposable.

### F-16

Long-running workflows are a separate bounded Workbench layer.

### F-17

SecurityLab remains independently versioned and owns research truth.

---

## 17. Open Questions

以下问题允许在 AI-01 之后实现时继续细化，不阻塞 AI-00：

- DSH 当前具体插件 API 的最终适配方式
- Codex provider profile 的最终配置格式
- Evidence 存储采用 JSON/YAML/SQLite 的最终实现
- Tool schema 的具体版本
- benchmark 数据集的最终目录结构
- 多 workspace 发现机制
- 凭证管理方案

这些是实现决策，不应反向改变本阶段已冻结的安全边界。

---

## 18. AI-00 Exit Criteria

AI-00 只有在以下全部明确后才能退出：

- [x] 独立 repository
- [x] Agent boundary
- [x] Model/Provider boundary
- [x] Plugin boundary
- [x] Permission model
- [x] Vehicle security boundary
- [x] Git safety boundary
- [x] Evidence model
- [x] Context hierarchy
- [x] Roadmap
- [x] 将上述冻结内容转化为实际 repository policy/config
- [ ] AI-01 DSH baseline execution plan
- [ ] GitHub main branch protection independently verified
