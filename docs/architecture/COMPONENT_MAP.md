# Component Map

```text
                              Human
                    architecture / approval
                              |
                    +---------+---------+
                    |   Workbench Core |
                    |                 |
                    |   Model Router  |
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
             +----------------+----------------+
             |                |               |
          Context           Guard          Evidence
             |                |               |
             +----------------+---------------+
                              |
                 Security Tools Plugin
                              |
                    Tool Adapter Layer
                              |
        +---------+---------+--------+----------+
        |         |         |        |          |
       Git      GitHub    Terminal   MCP   Security/RE Tooling
                              |
                         Workspace
                              |
                         SecurityLab
```

## Responsibilities

- **Workbench Core / Model Router**: selects eligible Agent / Provider / Model profiles and records routing decisions. It never grants permissions.
- **Agents**: execution roles; DSH is Primary Agent, Codex is Independent Second Agent.
- **Providers / Models**: transport and model capability abstraction.
- **Plugins**: four runtime plugin layers — Context, Guard, Evidence, Security Tools.
- **Tool adapters**: concrete execution interfaces used under Guard control.
- **Evidence**: durable normalized research records; raw run output may remain disposable.
- **Benchmarks**: versioned task cases and measured results; later consumed by Router v2.
- **Workflows**: bounded, resumable long-running execution.
- **Workspaces**: external research projects such as SecurityLab.

> **Plugin 5 / AI-07** is the planning identity of Model Router. Its architectural classification remains Workbench core service, not a DSH plugin.
