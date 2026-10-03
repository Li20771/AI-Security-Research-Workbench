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
                    +---------+---------+
                    |   Workbench Core |
                    |                 |
                    |  Model Router   |
                    +---------|-------+
                              |
                 +------------+------------+
                 |                         |
          DSH Main Agent             Codex Second Agent
                 |                         |
                 +------------+------------+
                              |
                    Provider / Model Layer
                              |
                 +------------+------------+
                 |                         |
          DeepSeek / MiMo        OpenAI-compatible
                              |
                 Context / Guard / Evidence
                              |
                    Research Tool Adapters
                              |
                    Git / GitHub / MCP /
             CAN / ISO-TP / UDS / QEMU / GDB /
                 Ghidra / AFL++ / YARA / ...
                              |
                         Workspace
                              |
                         SecurityLab
```

**Planning identity:** Plugin 5 / AI-07 — Model Router v1. Architectural classification: Workbench core service, not a DSH plugin.

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

状态：**已完成**

---

## AI-01 — DSH Baseline

目标：建立经过实际验证、证据支持的 DSH 主 Agent 基线。

范围：

- 安装/启动方式记录
- 工作区绑定
- 配置持久化
- 基础插件机制确认
- 基础 Agent 行为回归
- 稳定能力与实验能力分层
- 回滚点与基线记录

出口条件：

- 能确认 Agent、工具、插件的实际行为。
- 有可回退配置。
- 安装 / 启动过程已记录（documented）。

**不在出口条件内：**

- 在另一台干净 Windows 环境中重装同一 DSH 版本并证明完全复现。
  该项属于未来的部署 / 可复现性验证，**不是 AI-01 的 gate**。

说明：

- AI-01 validates the current DSH baseline, not universal cross-machine support.
- DSH is an external moving dependency and may require re-baselining after significant updates.
- Clean-room reinstall / cross-machine deployment is a future operational validation item,
  not an AI-01 gate.

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

状态：**COMPLETE** — 契约、实现、验证与证据均已完成（[执行计划](AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md)、
[证据](AI-03_CONTEXT_PLUGIN_EVIDENCE_2026-09-29.md)）。出口条件 C0–C8 全部 `PASS`，
其中 C8（required CI/tests PASS）由 validated head `7a29197` 上的 required CI run
`36518367883` = SUCCESS 满足。PR **#28 已由人工 merge**，merge commit
`548bc041b31cc0fc9d01af55c527378ba2c42c48`；AI-03 已在 `main` 上。

约束：

- Context 只呈现来源声明的状态，不判断"实际上应该是什么"
- `PLAN` 不得升级为 `FACT`；`PLAN → COMPLETE` / `PLAN → PASS` 在本阶段不可表示
- cache 不是事实源；revision 不匹配的 cache 条目不产生任何 item
- Context 严格 workspace-scoped，不实现跨 workspace 聚合，不读取 SecurityLab
- 不使用模型推理判定 Fact / History / Plan / PASS / COMPLETE

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

状态：**COMPLETE** — 合同冻结（[执行计划](AI-04_GUARD_EXECUTION_PLAN.md)，9 次 amendment）、
实现合并（[证据](AI-04-B_EVIDENCE_2026-09-29.md)）、review 完成、CI green，阶段已关闭。

```text
merge SHA = 254823f74aa742a3f98d04f7d184b39c33369d98   (PR #32)
AI-04-A   = COMPLETE / MERGED    contract frozen, 9 amendments
AI-04-B   = COMPLETE / MERGED    plugins/guard, 295 tests
AI-04-C   = COMPLETE             closeout
C0-C10    = all PASS
```

实现要点：

- `Guard.evaluate(request, policy)` 返回 `DecisionRecord`；policy 是调用参数，Guard 不做
  discovery / storage / selection
- 决策词表固定为 `ALLOW | DENY | BLOCKED | UNKNOWN`；`CheckResult` 是独立类型
- §12.2.2 的 specificity 排序是 deterministic topological linearization，不是 comparator
- 绝对安全边界在 policy 之前执行：secret-material 与 cross-workspace 都是 `DENY`，
  先于 policy 缺失 / 解析 / 校验
- 无 approval source，因此 `system-change` / `remote-change` / 真实 CAN/ECU/vehicle
  恒为 `BLOCKED`（D-12）

---

## AI-05 — Evidence / Audit Plugin

**Status: INCOMPLETE.** B1 (the offline logical core) is complete and merged, and so is the whole
of B2. AI-05 is not closed, and the reason is C-1 rather than anything B2 left undone.
This section keeps the original design as written — B1 and B2 completing do not change what AI-05
is for, and they do not change any later stage's dependency on it.

```text
AI-05-A     = COMPLETE / MERGED   contract frozen (docs/AI-05_EVIDENCE_EXECUTION_PLAN.md)
AI-05-B1    = COMPLETE / MERGED   offline logical core
AI-05-B2-P1 = COMPLETE / MERGED   §18.1 workspace agreement, T12/T13
AI-05-B2-P2 = COMPLETE / MERGED   §17 stored-form round-trip
AI-05-B2-P3 = COMPLETE / MERGED   admission pipeline, filesystem Store,
                                  uniqueness, staged discard,
                                  §31 Layer 0 evidence check
AI-05-B2    = COMPLETE            its frozen scope is implemented and merged
AI-05       = INCOMPLETE          C-1 is DEFERRED

B1 merge SHA = 0403fcd83b740f0603af7204e77f6e6905a84cf0   (PR #34)
B1 evidence  = docs/AI-05-B1_EVIDENCE_2026-10-01.md
P1 merge SHA = 844df7beb3ada381c71c945991c551403595885a   (PR #41)
P2 merge SHA = b8692c181f646386430dccd419595ca88e0cc4db   (PR #42)
P2 evidence  = docs/AI-05-B2-P2_EVIDENCE_2026-10-01.md
P3 merge SHA = 67515ff96dbd95ee5a8f73923d5eadc3f097501a   (PR #44)
P3 evidence  = docs/AI-05-B2-P3_EVIDENCE_2026-10-01.md
B2 decisions = docs/AI-05-B2_DECISIONS_2026-10-01.md
```

B1 built the record model, the §15.2 field table, the two digests, the grammars, the §6.5
registry and the §6.6 cross-field rules, and nothing else: no storage, no admission pipeline, no
Store. Everything below that depends on Evidence being *recorded and persisted* — audit trails,
benchmark consumption, reproducibility of a completed task — is therefore still ahead, and B1
alone does not satisfy it.

B2 added the §18.1 workspace agreement boundary (P1), the §17 stored-form round-trip (P2), and the
admission pipeline and filesystem Store (P3). A record can now be admitted and persisted under
`evidence/staged/`, read back and verified, and discarded as a whole.

Promotion stays a human act and has no AI-05 operation: the two tiers are two types, and the
promoted one has no `write`, so an admitted record cannot be routed into the durable tier by any
call. The promoted tier is read-only and is never deleted by AI-05.

What is still ahead: C-1 leaves §30 step 7 unimplemented and T22a/T22b/T22c unrunnable, so §32's
C6 gate is not closed. ContextRef derivation from AI-03 is not wired. And four items the B2
decision record left undefined — the retrieval return shape, the `superseded_by` query shape, the
promotion API and discard cleanup granularity — remain undefined rather than settled by the
Store's provisional surface.

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

**Status: COMPLETE / MERGED.** Merged to `main` as `3b1917ab` (PR #47). The Tool API, the eight adapter families, the four
boundaries (Guard, workspace, execution, vehicle), the Evidence projection and the AI-06
Layer 0 check are implemented and measured; see
[AI-06_EVIDENCE_2026-10-01.md](AI-06_EVIDENCE_2026-10-01.md) and the AI-06 section of
[PROJECT_STATUS.md](PROJECT_STATUS.md).

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

**Status: COMPLETE / MERGED.** The contract is
[AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md](AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md), frozen at
AI-08-A and merged as `2117cdf4` (PR #51). AI-08-B implemented the runtime against it and was
merged as `edb7dfc82ce51123482ac357fb9319dca2fa0d9a` (PR #52).

```text
AI-08-A     = COMPLETE / MERGED    contract frozen          (PR #51, 2117cdf4)
AI-08-B     = COMPLETE / MERGED    agent runtime            (PR #52, edb7dfc8)
AI-08       = CLOSED
contract    = blob a01e03f5306299a0a4442648eeb8fdcfce6bd8dd
                     after Amendment 4
previous    = 739ec29f37bfb8654f19ca088d6af57ffdd09e69
                     after Amendment 3
earlier     = 7fa9effde597c71f127c4e14dc31641a5ffe7589
                     after Amendment 2; the blob AI-08-A merged
amendments  = 4                    Amendment 1 (review corrections)
                                   Amendment 2 (terminal-result invariant)
                                   Amendment 3 (Guard-bound invocation boundary)
                                   Amendment 4 (required CI configuration in scope)
```

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

冻结要点（AI-08-A）：

- `AgentId` 是封闭词表，v1 只有 `dsh` / `codex`；自由字符串永远不是可信身份
- `AgentRole`（`PRIMARY` / `INDEPENDENT_SECOND`）是 AI-08 自己的角色词汇，
  与 AI-04 的 `ActorType` 是三个不同的问题，不得互相混淆
- 身份来自注册表，不来自发现（不读目录、不读环境变量、不读配置）
- Router 的 `agent_hint` 仍然只是 hint；`resolve_agent` 是候选变成身份的唯一入口
- 一次 execution = 一个 `ExecutionId` + 一个 terminal `AgentResult`
- `AgentExecutionRequest` **不携带** `ContextResponse`；由 execution runtime 为该次执行
  建立唯一一份、归该 execution 所有的 `ContextResponse`
- Context 隔离：同一 workspace + 每个 execution 独立的、execution-owned `ContextResponse`
- 独立性 I1–I8，其中 I3（result 不得成为另一个 Agent 的 input）是 v1 的关键边界
- 独立性只证明 provenance 独立，**不证明**结论正确；一致不等于验证
- `AgentRole.INDEPENDENT_SECOND` 只是架构角色，**不是** independence finding；
  角色本身永远不满足 I1–I8
- I5 是「每次 tool 调用都新建 GuardRequest / GuardDecision」，**不是** `request_digest` 全局唯一
- `AgentExecutionOutcome` 只有 `COMPLETED` / `FAILED` / `BLOCKED`；`COMPLETED != PASS`
- `BLOCKED` 是 execution 级的（execution **body** 未启动）；tool 被 Guard BLOCK 不会把
  整个 Agent execution 改写成 BLOCKED
- 「one ExecutionId → one terminal AgentResult」对 **三种 outcome 全部成立**：
  FAILED / BLOCKED 仍然各产生恰好一个 AgentResult；body 未启动 ≠ 没有 AgentResult
- `AgentResult.result` 恒存在；FAILED / BLOCKED 时指向 terminal failure/block metadata，
  而不是一个并不存在的 task result

```text
DEFERRED  AI-08 producer token for Evidence   an AI-05 amendment is required first
DEFERRED  a per-Agent permission ceiling      OUT OF SCOPE. AI-08 v1 does not enforce
                                              or claim one, and AI-08-B MUST NOT infer
                                              one from AgentId, AgentRole or ActorType.
```

AI-08-B 实现要点：

- `agents/` 是 core Agent layer（namespace package），不是 plugin layer
- 一次 execution：一个 `AgentExecutionRequest` → 一个 `ExecutionId` → 一个 terminal `AgentResult`；
  COMPLETED / FAILED / BLOCKED 三者皆然
- Context 由 runtime 建立、归该 execution 所有；request 只携带 descriptor，绝不携带 `ContextResponse`
- AI-08 不直接调用 Guard：它把 `actor = AgentId` 的 `ToolRequest` 交给 AI-06，
  由 AI-06 为每次 **Guard-bound** invocation 新建 `GuardRequest` / `GuardDecision`；
  不复用、不缓存
- AI-06 会在 Guard 之前拒绝某些请求（unknown tool / operation / 参数 / v1 target /
  workspace）。这类 **pre-Guard refusal 没有 GuardDecision**，不得伪造；
  `decision_id` 为空表示「没有发生评价」，**不等于** UNKNOWN，也**不等于** BLOCKED
- `AgentExecutionRequest` 构造时即经 `resolve_agent` 解析身份；
  `AgentResult.agent_id` 是真正的 `AgentId`，未注册字符串无法构造
- `AgentResult.result` 只接受 `sha256:<64 hex>` 或 `ref:<token>` 两种形状：
  这是**结构性形状保证**，不是内容扫描器（完整答案属于 AI-05 的 C-1）
- AI-08 不写任何 EvidenceRecord，也不 import `plugins.evidence`（Layer 0 会拦）
- v1 的 body 不做推理、不联网、不绑模型；它产出的是 provenance reference，不是 task result
- `COMPLETED != PASS`；`AgentRole.INDEPENDENT_SECOND` 不是 independence finding

**AI-08 v1 has no provider binding** — every capability on every shipped model profile is
`UNKNOWN` and no provider call has ever been made in this repository. Real Codex provider and model
wiring is AI-09's. **AI-08 v1 writes no AI-05 EvidenceRecord**: the only producer token admissible
for an EXECUTION record is `ai-06`, and an AI-08 record written under that token would be a false
producer claim.

---

## AI-09 — Domestic Models for Codex

**Status: COMPLETE / MERGED / CLOSED.** The contract is
[AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md](AI-09_CODEX_PROVIDER_EXECUTION_PLAN.md), frozen at
AI-09-A and unchanged by the implementation. The Codex integration layer was merged by PR #54.
No provider call has been made by this phase, no capability is VERIFIED, and connectivity is NOT
VERIFIED — the merge closed the implementation, not the provider question.

```text
AI-09-A     = CONTRACT FROZEN      (2026-10-02)
AI-09-B     = COMPLETE / MERGED    PR #54
AI-09       = CLOSED

merge       = b8b815b181e69f7651efdde97dd9473a3e619c7f
                     true two-parent merge; not squashed, not rebased
                     parent 1 = 4614a2ccb1a90ccf9c9e81bbe2bca87d44a47ae1
                     parent 2 = 3b83d245ac19dfeff4dc101188131e74330130c8
merged at   = 2026-10-02T06:57:50Z
contract    = blob e9728b184740074e5c8f718db6b45f859c3802bf
                     unchanged by AI-09-B
provider    = mimo — the existing profile; NO third provider identity
models      = mimo/mimo-v2.6-pro, mimo/mimo-v2.6-flash
backend     = integrations/codex/   a namespace package
reserved    = providers/openai-compatible/ stays RESERVED / DISABLED / UNIMPLEMENTED
evidence    = docs/AI-09_EVIDENCE_2026-10-02.md
live        = NOT_RUN    capability = UNKNOWN    connectivity = NOT VERIFIED
```

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

**Status: COMPLETE / MERGED / CLOSED.** The contract is
[AI-10_CROSS_AGENT_REVIEW_EXECUTION_PLAN.md](AI-10_CROSS_AGENT_REVIEW_EXECUTION_PLAN.md),
frozen at AI-10-A (PR #56, `3613896d`) and amended twice. The implementation was merged by
PR #60. Evidence: [AI-10_EVIDENCE_2026-10-02.md](AI-10_EVIDENCE_2026-10-02.md).

```text
AI-10-A     = COMPLETE / MERGED    contract frozen          (PR #56, 3613896d)
Amendment 1 = APPLIED / MERGED     §9.3.1 statement identity (PR #58, fbf1e1b0)
Amendment 2 = APPLIED / MERGED     §5.4 independence_status  (PR #59, 32126416)
AI-10-B     = COMPLETE / MERGED    the review core          (PR #60, d22fe25c)
AI-10       = CLOSED

merge       = d22fe25c5fe94ae697083fd9fbdfaf3976785703   (PR #60, true two-parent merge)
contract blob = fc6f709611fcf7a8fcf6845097bf130920445fdc
home        = review/ — a Workbench CORE service, not a plugin
live        = NOT_RUN     no provider call has been made
```

Frozen boundaries this phase introduced:

```text
review/ is a CORE service; it is not a plugin, an Agent, a Router, a Guard, a
  provider or a second Evidence subsystem
EXTERNAL REVIEW MATERIAL INGRESS — v1 accepts only explicitly supplied material;
  declared provenance is never verified provenance, and a digest is never read as
  content
the comparison produces exactly eight structural observations and never a verdict,
  a ranking, a winner or a score
verification is a REQUEST: the controlled caller invokes AI-06, under AI-04; AI-10
  holds no authorization authority and composes no ToolRequest
a human decision is human-supplied run data, never model-generated, never
  pre-filled, and never a recommendation
AI-10 writes NO EvidenceRecord in v1, under no producer token
```

Major unresolved dependencies, recorded and left standing:

```text
BLOCKED / PREREQUISITE   automatic acquisition of real Agent analysis material
                         (AI-08 §10.2, AI-09 §19) — needs an AI-09 amendment and/or
                         a separately reviewed DSH seam
DEFERRED                 durable review evidence and a durable HumanDecision —
                         both require an AI-05 amendment
NOT_RUN                  live provider verification, live Agent execution
```

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

### Status: COMPLETE / MERGED / CLOSED

```text
AI-11-A     = COMPLETE / MERGED / FROZEN   contract frozen        (PR #62, c1118551)
AI-11-B     = COMPLETE / MERGED            the benchmark core     (PR #63, ce880282)
AI-11-C     = COMPLETE / MERGED            the measured campaign  (PR #65, 6bbe526b)
AI-11       = CLOSED
contract blob = 6f7548a1c05b31093371f536e9a080434cddbcb0
              docs/AI-11_SECURITY_BENCHMARK_EXECUTION_PLAN.md (after Amendment 1, §27)
SecurityLab = efa836ff9225f6226ca8a76615f3f45c31110d58   read-only throughout
evidence    = docs/AI-11_EVIDENCE_2026-10-03.md
```

实际成果：

```text
benchmark core                benchmarks/ — contract型 oracle、BLOCKED/FAIL/PASS 分离
six-task corpus               六个 tracked task，每个带独立 oracle 与 negative control
reference executor campaign   python3 -m benchmarks.campaign，六任务全覆盖
independent oracle            每个 task 的真实独立观测（非 truth 回读）
campaign determinism check    同任务两次运行，11 个语义字段全部一致
A.6 controlled reproduction   固定 seed 重放 pinned generator，30 case
```

实际限制 —— 不得省略：

```text
A.6 production = BLOCKED
    PRECONDITION_UNMET:environment:vcan0-exclusive
    vcan0 存在 != vcan0 独占；当前合同不承认任何可审计的独占机制
Layer 4 = BLOCKED / DEFERRED
    无 provider 调用，故无 live 验证可做
kernel oracle truth 是 host-contingent（见 evidence §7）
    FINAL-REVIEW OBSERVATION / FUTURE DESIGN DEBT，未修，未改合同
```

明确的边界：

```text
AI-11 does not produce:
    universal ranking
    winner
    best model
    composite score

六任务中五个 PASS、一个 BLOCKED。把六项合成一个分数，等于把五次测量和一个环境边界相加。
```

AI-11 交付的是**测量事实**，不是模型结论。AI-12 才开始把这些事实用于路由决策；
AI-12 必须读取 AI-11 的 measurements，不得重新解释 BLOCKED / NOT_RUN / UNKNOWN /
UNAVAILABLE，也不得因某个 task 当前 BLOCKED 而将其删除。

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

### Status: AI-12-A COMPLETE / MERGED · AI-12-B COMPLETE / MERGED · AI-12 NOT CLOSED

```text
AI-12-A  = COMPLETE / MERGED   contract frozen   (PR #66, 60c630d8)
contract blob = b6e3cc8bd3a54b61e88c1f45c080bfd44965a462
AI-12-B  = COMPLETE / MERGED   the policy core   (PR #67, fa892eb1)
AI-12    = NOT CLOSED
AI-12-C  = BLOCKED / NOT STARTED
evidence = docs/AI-12-B_EVIDENCE_2026-10-03.md
```

已实现（offline verified）：

```text
policy artifact + validator        版本、rule identity、全序、condition、
                                   selection、reason_code、evidence binding、
                                   falsifier、discrimination control、
                                   fallback / escalation 声明、rollback、dormant
supplied evidence input            run_id 为身份，task_id / source_sha 不足以定位；
                                   重复 run_id 被拒；verdict 使用 AI-11 的封闭词表
resolution + audit                 fired rules、cited evidence、每一条 supplied
                                   record 的去向；verify_resolution 可外部重算
Layer 0 boundary                   policy core 只可 import benchmarks.vocabulary；
                                   无 score/weight/ranking、无 fallback/retry 执行路径
```

仍 BLOCKED —— 不得当作已完成：

```text
model-comparative prerequisite (§6)
    AI-11 的 campaign 是 executor_kind = REFERENCE，不含 per-model history / cost /
    latency；实现 infrastructure 不产生这些测量
    -> 任何 policy 只能 DORMANT，不能选择模型
live provider call / model measurement = NOT_RUN
AI-12-C = BLOCKED / NOT STARTED
```

边界：

```text
AI-12 只声明 policy，不做 runtime fallback / retry / escalation
AI-12 不产生 score / weight / ranking / aggregate / composite
AI-12 不修改 AI-07 / AI-11 / AI-05
把六任务合成一个分数仍然是禁止的
```

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

### Status: AI-13-A DRAFT / FREEZE PROPOSAL · AI-13 NOT COMPLETE

```text
contract = docs/AI-13_LONG_RUNNING_WORKFLOWS_EXECUTION_PLAN.md
AI-13-A  = DRAFT / FREEZE PROPOSAL   contract / design freeze   (PR open, not merged)
AI-13-B  = NOT STARTED               the workflow core
AI-13-C  = NOT STARTED               the approval point
AI-13    = NOT COMPLETE
AI-13 home = workflows/  (definitions · checkpoints · runs · policies)
```

本轮（AI-13-A）只冻结契约，不实现。契约承接了四个阶段**点名**交给 AI-13 的遗留项：

```text
AI-08 §7.2   无 parent-execution、无 retry lineage、无 resumption lineage；
             第二次尝试是**另一条 execution**，有自己的 ExecutionId
AI-08 §11.4  Agent 层不得发明 retry / cancellation / resume / fallback / escalation
AI-08 T32    TIMED_OUT / CANCELLED / RETRYING / RETRIED / FALLBACK / ESCALATED
             这些词被禁止于 AI-08，因为属于 AI-13
AI-02 §5.11  max_retries 默认 0；retry policy 是 AI-13 的事
AI-02 §9.1   retry_count 保留给 AI-13，AI-02 里恒为 0
AI-10 §5.3   "resume of a closed case ... is AI-13's boundary and does not exist in v1"
```

已冻结的核心边界：

```text
resume 只继承 DECLARED STATE；不继承 authorization / approval / context / tool state
每一次 attempt 独立授权；上一次 decision 不给下一次任何授权
retry ≠ 提权 ≠ 扩大候选集 ≠ 放宽能力 ≠ 自动模型 fallback
每个 bound 都是 DECLARED；达到 bound 是具名 terminal state，不是静默停止
checkpoint 是 disposable workflow state，不是 AI-05 Evidence，且不得当成 Evidence
human approval 只开 workflow 的门；Guard 的门仍然独立 BLOCKED（AI-04 §8 / D-12 / Q-3）
AI-13 v1 无 DAG scheduler、无后台 daemon、无并发、无跨进程保持
```

review 后补齐的、必须机械可验的语义：

```text
canonical digest（§7.4）  单一 preimage 定义：canonical JSON、键排序、UTF-8、
                          null 视为缺省、整数、SHA-256；digest 字段自身排除。
                          checkpoint / approval scope / run record / definition 共用
checkpoint digest         自指定义已消除；T10 可机械验证 tamper -> CHECKPOINT_CORRUPT
approval scope digest     冻结为恰好六个字段的 canonical 序列化；任一字段变化 -> 拒绝
BOUND SURVIVES RESUME      持久化 ABSOLUTE deadline，不是重算的 duration；
                          跨 process 不得重置；approval 等待、restart 均计入
RunRecord vs Checkpoint    ledger 与 snapshot 分离；bound 由 RunRecord 强制，
                          丢弃 checkpoint 不得减少已消耗的 attempts / budget
effective bound            多 bound 并存取 min；先判后跑，不允许跑到超限才发现
workspace re-derivation    v1 无此机制：exact identity 或 WORKSPACE_CHANGED
FailureClass               九个成员，无 UNKNOWN 成员；无法归类 = 不赋类 + 停止 + 不 retry
B/C 分工                   B = workflow core（拒绝 approval step）；C = approval point
trusted approval ingress   caller 自述 actor.type = human 不等于 human approval；
                           approval 必须来自 C 指派的、位于 Agent/model/service 执行
                           之外的 ingress，且 provenance 可被机械验证；在此 ingress
                           存在之前，任何 approval 都无效、approval step 一律 BLOCKED
```

仍 BLOCKED / 未解决，不得借 AI-13 绕过：

```text
AI-12 §6 model-comparative prerequisite = BLOCKED（AI-13 不执行 AI-12 policy）
AI-12-C = BLOCKED / NOT STARTED
AI-05 = INCOMPLETE（C-1 DEFERRED；AI-13 不注册 producer、不写 Evidence、不解决 C-1）
```

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

AI-00 platform limitation: GitHub `main` branch protection is BLOCKED under the current GitHub Free/private-repository plan. This does not block AI-01; it remains an explicit external limitation.
    
## 2.1 Standard phase execution and completion path

Every AI phase follows the same path. The current phase and current work item are recorded in `docs/PROJECT_STATUS.md`.

```text
START
  -> read PROJECT_STATUS
  -> read current MASTER_ROADMAP phase
  -> read phase requirements / design
  -> verify branch + base SHA + working tree
  -> create task branch + task/experiment ID
  -> IMPLEMENT
  -> VERIFY
  -> record Evidence
  -> review scope + diff
  -> PR / approval gate
  -> MERGE checkpoint
  -> update PROJECT_STATUS
  -> next phase
```

A phase is not complete merely because code exists. Its exit requires:

- declared scope completed
- required validation executed
- evidence recorded
- known blockers explicitly classified
- exit criteria satisfied
- status updated before the next phase begins

### Phase start rule

At the beginning of every work session, do not choose work from memory or from the directory tree. Use `docs/PROJECT_STATUS.md` as the single current-work entry point, then follow the phase dependency and exit criteria in this roadmap.



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
| AI-00 | **COMPLETE** |
| AI-01 | **COMPLETE** |
| AI-02 | **COMPLETE** — closed 2026-09-29, see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-03 | **COMPLETE** — C0–C8 PASS; merged as `548bc041` (PR #28); see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-04 | **COMPLETE** — merged as `254823f7` (PR #32); see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-05 | **B1 COMPLETE** (PR #34); **B2 COMPLETE** — P1 `844df7be` (PR #41), P2 `b8692c18` (PR #42) and P3 `67515ff9` (PR #44) merged; **AI-05 INCOMPLETE** — C-1 DEFERRED, §30 step 7 unimplemented; see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-06 | **COMPLETE** — merged as `3b1917ab` (PR #47); see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-07 | **COMPLETE** — contract `963c181c` (PR #48), implementation `e57541f9` (PR #49) merged; see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-08 | **COMPLETE** — merged as `edb7dfc82ce51123482ac357fb9319dca2fa0d9a` (PR #52); see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-09 | **COMPLETE** — merged as `b8b815b181e69f7651efdde97dd9473a3e619c7f` (PR #54); see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-10 | **COMPLETE** — contract `3613896d` (PR #56), Amendments 1 and 2 (`fbf1e1b0` PR #58, `32126416` PR #59), implementation `d22fe25c5fe94ae697083fd9fbdfaf3976785703` (PR #60) merged; see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| AI-11 | **COMPLETE / CLOSED** — contract `6f7548a1` (PR #62 + Amendment 1), benchmark core `ce880282` (PR #63), measured campaign `6bbe526b5bedeb29fb138f8979f0a4cb6df1b3ce` (PR #65); five tasks PASS, A.6 BLOCKED by `PRECONDITION_UNMET:environment:vcan0-exclusive`; see [AI-11_EVIDENCE_2026-10-03.md](AI-11_EVIDENCE_2026-10-03.md) |
| AI-12 | **AI-12-A COMPLETE / MERGED** (`60c630d8`), **AI-12-B COMPLETE / MERGED** (`fa892eb1`, PR #67) — the policy core; **AI-12-C BLOCKED / NOT STARTED**, **AI-12 NOT CLOSED**, model-comparative prerequisite BLOCKED; see [AI-12-B_EVIDENCE_2026-10-03.md](AI-12-B_EVIDENCE_2026-10-03.md) |
| AI-13 | **AI-13-A DRAFT / FREEZE PROPOSAL** — contract/design freeze, PR open, not merged; **AI-13 NOT COMPLETE**, AI-13-B/C not started; see [AI-13_LONG_RUNNING_WORKFLOWS_EXECUTION_PLAN.md](AI-13_LONG_RUNNING_WORKFLOWS_EXECUTION_PLAN.md) |
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

