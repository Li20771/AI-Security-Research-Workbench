"""AI-06 — Security Research Tools Plugin.

One way to run a research tool, and one way to describe what happened.

```text
Tool is a capability.       It does not decide whether it may run.
Guard is the authorization. It decides; it never executes.
Evidence is the record.     It records; it adjudicates nothing.
```

```text
Agent -> ToolRequest -> AI-04 Guard -> adapter -> ToolResult -> AI-05 projection
                            ^                          ^
                     the authorization          the execution fact
```

AI-06 is the only layer that executes anything, and the reason it exists is so
that execution happens in one auditable place rather than in whatever code
happened to need a subprocess.

### What this package is, and the five things it is not

```text
IT IS      the Tool API: identity, request, result, descriptor, registry, the
           adapter protocol, the two gates, and the Evidence projection.
IT IS NOT  a permission system        permission_level is supplied by the caller
                                      and is never inferred (§6.2); Guard decides
IT IS NOT  an evidence store          AI-06 projects; AI-05 records (§15.1)
IT IS NOT  a shell                    an operation executes argv, and `shell` is
                                      not a parameter anywhere (§11.1)
IT IS NOT  a policy engine            the policy is a parameter handed in, as
                                      AI-04 requires of every caller (§9.4)
IT IS NOT  a discovery mechanism      the registry is static and the workspace
                                      root is declared (§7.5, §10.2)
```

### The two gates

```text
gate 1   AI-06's v1 target boundary    refuses what v1 cannot express at all
gate 2   AI-04 Guard                   authorizes, or does not
```

Both must pass. One `ALLOW` authorizes one invocation; nothing here caches it.

### Where the adapters are

`plugins/security_tools` is the plugin. The eight adapter families live under
`tools/`, because AI-00 F-14 freezes that split: *"Research tool adapters are
separate from the Security Tools plugin."* This package never imports `tools.*`,
so there is no cycle; `tools/__init__.py` builds the default registry.

Contract: `docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md`.
"""

from __future__ import annotations

from plugins.security_tools.adapter import AdapterOutcome, Invocation, ToolAdapter
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
from plugins.security_tools.dispatch import invoke
from plugins.security_tools.errors import (
    ArgumentInvalid,
    ExecutionRefused,
    GuardUnavailable,
    PathEscapesWorkspace,
    PermissionLevelMissing,
    TargetRefused,
    TimeoutMissing,
    ToolError,
    ToolRequestMalformed,
    UnknownOperation,
    UnknownTool,
    WorkspaceUnresolvable,
)
from plugins.security_tools.evidence import execution_payload_for, tool_call_for
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.paths import contained_path, resolve_root
from plugins.security_tools.redaction import MASK, project, redact_text
from plugins.security_tools.registry import ToolRegistry
from plugins.security_tools.request import ToolRequest, ToolWorkspace
from plugins.security_tools.result import BOUNDED_OUTPUT_CHARS, ToolResult
from plugins.security_tools.runner import ProcessOutcome, ProcessRunner, SubprocessRunner
from plugins.security_tools.vocabulary import (
    ADMITTED_FAMILIES,
    OUTCOME_TO_STATUS,
    V1_PERMITTED_TARGET_ENVIRONMENTS,
    V1_PERMITTED_VEHICLE_INTERFACES,
    AdapterFamily,
    FilesystemAccess,
    ToolOutcome,
    VehicleInterface,
    status_for,
)

__all__ = [
    "ADMITTED_FAMILIES",
    "BOUNDED_OUTPUT_CHARS",
    "MASK",
    "OUTCOME_TO_STATUS",
    "V1_PERMITTED_TARGET_ENVIRONMENTS",
    "V1_PERMITTED_VEHICLE_INTERFACES",
    "AdapterFamily",
    "AdapterOutcome",
    "ArgumentInvalid",
    "ArgumentSpec",
    "EnvironmentRequirement",
    "ExecutionRefused",
    "FilesystemAccess",
    "GuardUnavailable",
    "Invocation",
    "OperationSpec",
    "PathEscapesWorkspace",
    "PermissionLevelMissing",
    "ProcessOutcome",
    "ProcessRunner",
    "SubprocessRunner",
    "TargetRefused",
    "TimeoutMissing",
    "ToolAdapter",
    "ToolDescriptor",
    "ToolError",
    "ToolIdentity",
    "ToolOutcome",
    "ToolRegistry",
    "ToolRequest",
    "ToolRequestMalformed",
    "ToolResult",
    "ToolWorkspace",
    "UnknownOperation",
    "UnknownTool",
    "VehicleInterface",
    "WorkspaceUnresolvable",
    "contained_path",
    "execution_payload_for",
    "invoke",
    "project",
    "redact_text",
    "resolve_root",
    "status_for",
    "tool_call_for",
]
