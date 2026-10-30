# SecurityLab MCP v1

**契约 ID：** `securitylab.mcp`
**版本：** `1.0.0`
**状态：** `FROZEN`（2026-10-30）
**实现状态：** Workbench 侧固定 client + fake server `IMPLEMENTED`；真实 SecurityLab MCP server 为 `IMPLEMENTED BUT NOT CONNECTED`；真实实验为 `NOT_RUN`。
**消费者：** Workbench Fleet、SecurityLab MCP server、所有 worker preset。

SecurityLab 拥有自己的代码、样本、虚拟/真实实验环境、数据和验证标准。Workbench/Fleet
只注册和分配 MCP **工具 profile**，不把 SecurityLab 业务实现搬进 Fleet。MCP 是
Agent 到 SecurityLab 工具的受控通道，不是 Agent 间通信协议；本架构不引入 A2A。

## 1. 工具 profile

| profile | 状态 | 使用角色 | 说明 |
|---|---|---|---|
| `securitylab_ro` | **enabled** | orchestrator（不分配工具）、researcher、vehicle_analyst、challenger、evidence_verifier | 只读 catalog/status/受限 file read/report/run result |
| `securitylab_vcan` | **disabled** | lab_runner（preset disabled） | 固定 suite 虚拟实验接口；本轮不启动、不连接、不执行 |

`lab_runner` 默认 disabled；`securitylab_vcan` 默认 disabled。任何调用返回
`tool-disabled`，`meta.executed = false`、`meta.side_effects = 0`，无执行副作用。

## 2. 工具面

| tool | 参数 | 作用 | 限制 |
|---|---|---|---|
| `lab_catalog` | `{}` | 列出获准资源/能力 | 最多 100 项；不含绝对根路径；不探测 |
| `lab_status` | `{}` | 读取静态只读状态 | 不启动/探测实验；不返回环境变量 |
| `lab_read_file` | `{"path":"<relative>","root_id?":"workspace|reports|artifacts"}` | 读取授权 root 内文件 | canonical containment；拒绝 symlink escape；bounded/redacted |
| `lab_get_report` | `{"report_id":"<id>"}` | 读取既有报告 | 仅 reports root；无任意路径 |
| `lab_get_run_result` | `{"result_id":"<id>"}` | 读取既有 run result | 不执行、不重跑；`result_id` 是 SecurityLab 产物 ID，不是 Fleet run 身份 |
| `securitylab_vcan` | `{"suite":"unit_smoke|virtual_smoke"}` | 固定 suite 虚拟实验接口 | **disabled**；只保留 schema；无执行 |

不提供的工具/能力：

- 任意 shell、任意 Python、命令拼接、`sudo`、系统配置、任意文件删除；
- workspace/root 外路径读取或写入；
- `git push/merge` 或远程仓库写；
- 任意网络目标扫描/攻击、远程目标；
- 真实 CAN/ECU/车辆发送、刷写、车辆控制；
- 任意目标/接口/ECU 地址参数。

## 3. 身份与可信绑定

工具调用携带的 **server-side context** 来自可信 server/session binding，不是模型参数：

```json
{
  "run_id": "run_0123456789abcdef0123456789abcdef",
  "role": "researcher",
  "workspace_id": "ws_a",
  "episode_id": "ep_1",
  "tool_profile": "researcher_ro_v1"
}
```

规则：

- 模型不能设置 `role`、`workspace_id`、`episode_id`、`run_id`、`session_id`、
  `tool_profile`、`approval_ref` 或任何权限字段。
- 工具参数中出现上述身份字段 -> `identity-in-args`，拒绝且无副作用。
- 服务端在每次 tool invocation 检查 caller/run 绑定、workspace、工具 allowlist、
  操作/suite 白名单、参数、时间与输出限额。
- 客户端也会按 preset 的 `allowed_tools` 预检；服务端独立复核（defense in depth）。
- 绑定 workspace 之外的 report/result/file 表现为 `not-found` 或 `path-out-of-root`，
  不泄露存在性、版本、路径或全局统计。

## 4. 路径限制

`lab_read_file.path` 必须是 **root 相对路径**，使用 POSIX 分隔符：

- 拒绝绝对路径、盘符（`C:`）、UNC（`\\server\share`）、`..` 段、`.` 段、
  NUL、ADS（`file:stream`）、Windows 保留名（`CON`、`PRN`、`AUX`、`NUL`、
  `COM1-9`、`LPT1-9`）。
- `root_id` 只能映射到服务端固定的 root：`workspace`、`reports`、`artifacts`；
  不能是任意路径。
- 服务端必须做 canonicalization + root containment；对 symlink/junction，必须
  `realpath` 后再比较 containment，拒绝 escape。
- 只读：本契约没有任何写入工具。path-traversal 测试只做路径计算与 containment
  断言，**不得**对被测逃逸目标实际写入。
- 输出不包含绝对 root 路径；catalog 只返回逻辑 ID/名称。

## 5. 输出限制与脱敏

- 单次工具输出 ≤ 65536 bytes；超过时截断并设置 `data.truncated = true`、
  `meta.bytes = 65536`。`lab_catalog` ≤ 100 项；report/result 同样受上限约束。
- 输出脱敏：`token`、`api_key`、`apikey`、`password`、`secret`、`authorization`、
  `cookie` 等键值替换为 `[REDACTED]`；`meta.redacted = true`。
- 输出不得包含 credential、完整环境、绝对路径、未授权 workspace 内容或内部异常栈。
- `meta.identity_source` 恒为 `"server-binding"`；`meta.executed` 表示是否发生
  工具执行；`meta.side_effects` 在 v1 恒为 `0`。

## 6. 结果信封

成功：

```json
{
  "contract_version": "1.0.0",
  "server": "securitylab_ro",
  "tool": "lab_read_file",
  "ok": true,
  "data": { "content": "…", "bytes": 42, "truncated": false },
  "error": null,
  "meta": {
    "identity_source": "server-binding",
    "executed": true,
    "side_effects": 0,
    "redacted": false,
    "output_limit": 65536,
    "bytes": 42
  }
}
```

失败：

```json
{
  "contract_version": "1.0.0",
  "server": "securitylab_ro",
  "tool": "lab_read_file",
  "ok": false,
  "data": null,
  "error": { "code": "path-out-of-root", "message": "path is outside the bound root" },
  "meta": {
    "identity_source": "server-binding",
    "executed": false,
    "side_effects": 0,
    "redacted": false,
    "output_limit": 65536,
    "bytes": 0
  }
}
```

错误码：

| code | 含义 |
|---|---|
| `tool-not-allowed` | 工具不在该 profile/role allowlist |
| `tool-disabled` | 工具存在但 disabled（如 `securitylab_vcan`） |
| `identity-in-args` | 工具参数试图设置可信身份/权限 |
| `invalid-args` | 参数缺失、类型/格式/root_id 非法 |
| `path-out-of-root` | 路径越界或绝对路径 |
| `symlink-escape` | canonical path 逃逸 root |
| `cross-workspace-denied` | 请求其他 workspace 的资源 |
| `not-found` | 资源不存在或调用方无权查看（不泄露存在性） |
| `output-limit` | 无法在限额内安全返回（硬失败，不静默截断敏感内容） |
| `redaction-failed` | 脱敏失败，拒绝返回 |
| `internal-error` | 内部错误（不泄露路径/记录/栈） |

## 7. `securitylab_vcan`（disabled）

```json
{
  "suite": "unit_smoke"
}
```

- 仅保留 schema；`suite` ∈ `unit_smoke|virtual_smoke`。
- 本轮任何调用返回：

```json
{
  "contract_version": "1.0.0",
  "server": "securitylab_vcan",
  "tool": "securitylab_vcan",
  "ok": false,
  "data": null,
  "error": { "code": "tool-disabled", "message": "securitylab_vcan is disabled" },
  "meta": {
    "identity_source": "server-binding",
    "executed": false,
    "side_effects": 0,
    "redacted": false,
    "output_limit": 65536,
    "bytes": 0
  }
}
```

不得启动、连接或运行任何 vcan/SecurityLab/设备实验；不得接受任意 suite、shell、
Python、目标或 ECU 地址。

## 8. 离线测试要求（Workbench fake server）

至少覆盖：

1. `lab_read_file` 在 `workspace/reports/artifacts` root 内允许；root 外拒绝。
2. `../`、绝对路径、盘符、UNC、NUL、ADS、保留名、symlink escape 拒绝；
   只做纯路径计算/断言，不写入被测目标。
3. 未知工具、profile 外工具、disabled `securitylab_vcan` 明确拒绝且无副作用。
4. 参数中的 `role`/`workspace_id`/`run_id`/`session_id`/`tool_profile` 拒绝。
5. 输出上限、截断标记、脱敏；无绝对 root、无 credential、无环境值。
6. 跨 workspace 的 file/report/result 拒绝或 `not-found`，不泄露存在性。
7. `lab_status` 不探测环境；`lab_get_run_result` 不执行/不重跑。

## 9. 示例

- `examples/securitylab-tool-call.example.json`
- `examples/securitylab-tool-result.example.json`

## 10. 版本与同步

- 当前版本 `1.0.0`；与 `FLEET_API_V1.md`、`MEMORYPACK_V1.md` 同一版本。
- 任何工具/参数/错误码/路径语义变化必须同步 Workbench、SecurityLab 与
  `brief/contracts/` 及测试。
- 真实 SecurityLab MCP server 连接、vcan 与设备实验不在本轮范围；状态为
  `IMPLEMENTED BUT NOT CONNECTED` / `NOT_RUN`。
