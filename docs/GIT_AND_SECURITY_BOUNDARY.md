# Git & Security Boundary

## Purpose

本文件是 Workbench 的最低安全边界。

## Branch policy

Agent 默认只能在实验/功能分支工作：

```text
main
  -> feature/*
  -> experiment/*
  -> audit/*
  -> chore/*
```

变更前：

1. 读取当前 branch。
2. 读取当前 SHA。
3. 检查 working tree。
4. 生成任务/实验 ID。

变更后：

1. 检查 diff。
2. 执行对应测试。
3. 记录结果。
4. 记录最终 SHA。

## Protected actions

以下动作默认需要明确的人类批准：

- 修改 main
- merge / rebase / history rewrite
- force push
- sudo
- systemd/system configuration
- kernel/bind-mount/network configuration
- credential changes
- real CAN / ECU / vehicle access
- destructive filesystem operations
- uncontrolled remote execution

## SecurityLab boundary

Workbench 可以通过受控工具访问 SecurityLab，但不得把 Workbench 的权限模型当成 SecurityLab 本身的安全边界。

SecurityLab 的研究代码与测试结果仍由 SecurityLab 自己负责。

## Fail-closed

任何 Guard 判断结果：

- ALLOW -> 可以继续
- DENY -> 阻断
- UNKNOWN -> 默认阻断
- ERROR -> 默认阻断

尤其禁止：

- Guard 异常时自动放行
- Tool unavailable 时自动跳过限制
- Test unavailable 时自动标 PASS

## Secrets

禁止：

- API keys
- private keys
- access tokens
- passwords
- cookies
- SSH credentials

进入 Git tracked files。

允许使用环境变量、系统凭证或专用 secret manager 注入运行时配置。

## Vehicle network

默认只允许：

- vcan
- simulator
- isolated test harness

真实接口属于高影响权限，需要单独授权。

## Status semantics

只有具备执行证据的成功测试才能标记：

```text
PASS
```

其他情况必须保留：

```text
FAIL
BLOCKED
NOT_RUN
UNKNOWN
```
