# AI Security Research Workbench

面向个人安全研究与车联网安全工程的 AI Agent 工作台。

本项目与 `SecurityLab` 分离维护：

- `AI-Security-Research-Workbench`：负责 Agent、模型、插件、路由、审计、基准与工作流。
- `SecurityLab`：负责 UDS/CAN/Gateway、固件、测试、实验场景与安全研究本体。
- Workbench 可以连接多个研究项目，SecurityLab 只是第一个 workspace，不被 Workbench 的代码结构绑定。

## 核心定位

Workbench 不是一个单一模型，也不是 DSH 的 fork。

目标架构：

```text
                    Human
              架构 / 批准 / 决策
                       |
          +------------+------------+
          |                         |
      DSH Main Agent          Codex Second Agent
          |                         |
     Model Router               Provider Layer
          |                         |
   +------+------+          +------+------+
   |             |          |             |
DeepSeek      MiMo       OpenAI-compatible providers
   |             |
   +------+------+ 
          |
       Tools / MCP
          |
   +------+------+----------------------+
   |             |                      |
 Git/GitHub   Security Tools      Workspace Context
   |             |                      |
   +-------------+----------------------+
                       |
                   SecurityLab
```

## 设计原则

1. **人负责最终决策**：Agent 可以分析、验证、提出修改，但高影响操作必须经过明确授权。
2. **Evidence > Model Confidence**：模型自信不是证据；测试、日志、diff、Git 状态和复现实验才是证据。
3. **Plugin-first**：优先使用 DSH 的插件/扩展能力，不直接 fork 核心。
4. **项目与 Agent 解耦**：Workbench 服务多个 workspace，不把 SecurityLab 逻辑硬编码进 Agent。
5. **安全边界默认拒绝**：真实车辆、真实 ECU、真实 CAN 总线、敏感系统修改与秘密信息访问默认禁止。
6. **可恢复、可审计**：每次研究任务都能回答“谁、用什么模型、基于哪个 SHA、做了什么、改了什么、测了什么、结果是什么”。
7. **先冻结、后实现**：先完成 AI-00 需求与架构冻结，再逐阶段实现。

## Roadmap

详见 [docs/MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md)。

## 当前阶段

**AI-00 — Requirements / Architecture Freeze**

当前只冻结范围、边界、数据结构和演进路线；暂不把后续阶段的实现混入 AI-00。

## 文档

- [Master Roadmap](docs/MASTER_ROADMAP.md)
- [AI-00 Requirements & Architecture](docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md)
- [Git & Security Boundary](docs/GIT_AND_SECURITY_BOUNDARY.md)

## 与 SecurityLab 的关系

Workbench 通过 workspace/context/tool 适配层访问 SecurityLab。

不要把以下内容反向塞入 Workbench：

- SecurityLab 的 UDS/CAN/Gateway 业务实现
- SecurityLab 的协议测试实现
- SecurityLab 的固件样本与实验数据
- SecurityLab 自己的工程退出标准

这些仍由 SecurityLab 自己维护。
