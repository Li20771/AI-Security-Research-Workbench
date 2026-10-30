import path from "node:path";
import { isPlainObject } from "../canonical-json.ts";
import type { RoleId, ToolName } from "../contract.ts";
import { isRoleId, isToolName, TOOL_NAMES } from "../contract.ts";
import { EPISODE_ID_PATTERN, RUN_ID_PATTERN, WORKSPACE_ID_PATTERN } from "../binding.ts";
import { getRolePreset } from "../registries/roles.ts";
import { getWorkspace } from "../registries/workspaces.ts";
import { checkContainment, sanitizeRelativePath } from "../path-safety.ts";

export type SecurityLabErrorCode =
  | "tool-not-allowed"
  | "tool-disabled"
  | "identity-in-args"
  | "invalid-args"
  | "path-out-of-root"
  | "symlink-escape"
  | "cross-workspace-denied"
  | "not-found"
  | "output-limit"
  | "redaction-failed"
  | "internal-error";

export interface SecurityLabContext {
  run_id: string;
  role: RoleId;
  workspace_id: string;
  episode_id: string | null;
  tool_profile: string;
}

export interface SecurityLabToolDescriptor {
  name: ToolName;
  enabled: boolean;
}

export interface SecurityLabResult {
  contract_version: "1.0.0";
  server: "securitylab_ro" | "securitylab_vcan";
  tool: ToolName;
  ok: boolean;
  data: Record<string, unknown> | null;
  error: { code: SecurityLabErrorCode; message: string } | null;
  meta: {
    identity_source: "server-binding";
    executed: boolean;
    side_effects: 0;
    redacted: boolean;
    output_limit: number;
    bytes: number;
  };
}

export interface SecurityLabMcpClient {
  listTools(context: SecurityLabContext): readonly SecurityLabToolDescriptor[];
  callTool(
    context: SecurityLabContext,
    tool: ToolName,
    args: Record<string, unknown>
  ): Promise<SecurityLabResult>;
}

const OUTPUT_LIMIT = 65536;
const IDENTITY_ARG_KEYS = new Set([
  "role",
  "workspace_id",
  "episode_id",
  "run_id",
  "session_id",
  "tool_profile",
  "approval_ref",
  "command",
  "shell",
  "python",
  "script",
  "url",
  "target",
  "host",
  "sudo",
  "git",
  "env",
  "environment"
]);

interface FakeFile {
  content: string;
  symlink?: string;
}

type RootKind = "workspace" | "reports" | "artifacts";

interface FakeWorkspace {
  root: string;
  files: Record<RootKind, Map<string, FakeFile>>;
  reports: Map<string, { title: string; content: string }>;
  results: Map<string, { status: string; summary: string }>;
}

function makeWorkspace(root: string): FakeWorkspace {
  return {
    root,
    files: {
      workspace: new Map(),
      reports: new Map(),
      artifacts: new Map()
    },
    reports: new Map(),
    results: new Map()
  };
}

function seedWorkspaces(): Map<string, FakeWorkspace> {
  const wsA = makeWorkspace("D:\\lab\\ws_a");
  wsA.files.workspace.set("notes.txt", { content: "WS_A_WORKSPACE_CANARY" });
  wsA.files.workspace.set("secret.txt", {
    content: "token=REDACTION_TOKEN_SENTINEL\npassword=REDACTION_PASSWORD_SENTINEL\nnormal line"
  });
  wsA.files.workspace.set("large.txt", { content: "x".repeat(70000) });
  wsA.files.workspace.set("link-out", {
    content: "should never be returned",
    symlink: "../ws_b/reports/report-b.md"
  });
  wsA.files.reports.set("report-1.md", {
    content: "Report A: synthetic fixture; no real target data."
  });
  wsA.files.artifacts.set("run-1/out.txt", { content: "artifact-a" });
  wsA.reports.set("rep_a_0001", {
    title: "Synthetic report A",
    content: "Synthetic report A body."
  });
  wsA.results.set("res_a_0001", {
    status: "completed",
    summary: "Synthetic run result A."
  });

  const wsB = makeWorkspace("D:\\lab\\ws_b");
  wsB.files.workspace.set("notes.txt", { content: "WS_B_WORKSPACE_CANARY" });
  wsB.files.reports.set("report-b.md", { content: "WS_B_CANARY" });
  wsB.files.artifacts.set("run-b/out.txt", { content: "artifact-b" });
  wsB.reports.set("rep_b_0001", {
    title: "Synthetic report B",
    content: "Synthetic report B body."
  });
  wsB.results.set("res_b_0001", {
    status: "completed",
    summary: "Synthetic run result B."
  });

  return new Map([
    ["ws_a", wsA],
    ["ws_b", wsB]
  ]);
}

function redact(content: string): { content: string; redacted: boolean } {
  const pattern = /((?:token|api_key|apikey|password|secret|authorization|cookie)\s*[:=]\s*)([^\s,;]+)/gi;
  let redacted = false;
  const output = content.replace(pattern, (_match, prefix: string) => {
    redacted = true;
    return `${prefix}[REDACTED]`;
  });
  return { content: output, redacted };
}

function truncateUtf8(content: string, limit: number): { content: string; bytes: number; truncated: boolean } {
  const fullBytes = Buffer.byteLength(content, "utf8");
  if (fullBytes <= limit) {
    return { content, bytes: fullBytes, truncated: false };
  }
  let end = content.length;
  while (end > 0 && Buffer.byteLength(content.slice(0, end), "utf8") > limit) {
    end -= 1;
  }
  const sliced = content.slice(0, end);
  return {
    content: sliced,
    bytes: Buffer.byteLength(sliced, "utf8"),
    truncated: true
  };
}

function resultOk(
  tool: ToolName,
  server: "securitylab_ro" | "securitylab_vcan",
  data: Record<string, unknown>,
  redacted: boolean,
  bytes: number,
  executed: boolean
): SecurityLabResult {
  return {
    contract_version: "1.0.0",
    server,
    tool,
    ok: true,
    data,
    error: null,
    meta: {
      identity_source: "server-binding",
      executed,
      side_effects: 0,
      redacted,
      output_limit: OUTPUT_LIMIT,
      bytes
    }
  };
}

function resultFail(
  tool: ToolName,
  server: "securitylab_ro" | "securitylab_vcan",
  code: SecurityLabErrorCode,
  message: string
): SecurityLabResult {
  return {
    contract_version: "1.0.0",
    server,
    tool,
    ok: false,
    data: null,
    error: { code, message },
    meta: {
      identity_source: "server-binding",
      executed: false,
      side_effects: 0,
      redacted: false,
      output_limit: OUTPUT_LIMIT,
      bytes: 0
    }
  };
}

function serverFor(tool: ToolName): "securitylab_ro" | "securitylab_vcan" {
  return tool === "securitylab_vcan" ? "securitylab_vcan" : "securitylab_ro";
}

function validateContext(context: SecurityLabContext): string | null {
  if (!isPlainObject(context)) {
    return "context must be an object";
  }
  const record = context as unknown as Record<string, unknown>;
  if (
    typeof record.run_id !== "string" ||
    !RUN_ID_PATTERN.test(record.run_id) ||
    typeof record.role !== "string" ||
    !isRoleId(record.role) ||
    typeof record.workspace_id !== "string" ||
    !WORKSPACE_ID_PATTERN.test(record.workspace_id) ||
    typeof record.tool_profile !== "string"
  ) {
    return "server binding is invalid";
  }
  if (
    record.episode_id !== null &&
    (typeof record.episode_id !== "string" || !EPISODE_ID_PATTERN.test(record.episode_id))
  ) {
    return "server binding episode is invalid";
  }
  const workspace = getWorkspace(record.workspace_id);
  if (workspace === undefined || !workspace.enabled) {
    return "workspace is not registered or is disabled";
  }
  return null;
}

function validateArgs(
  tool: ToolName,
  args: Record<string, unknown>
): { ok: true } | { ok: false; code: SecurityLabErrorCode; message: string } {
  if (!isPlainObject(args)) {
    return { ok: false, code: "invalid-args", message: "arguments must be an object" };
  }
  for (const key of Object.keys(args)) {
    if (IDENTITY_ARG_KEYS.has(key)) {
      return {
        ok: false,
        code: "identity-in-args",
        message: `identity or permission field is not allowed in arguments: ${key}`
      };
    }
  }
  const keys = Object.keys(args);
  if (tool === "lab_catalog" || tool === "lab_status") {
    if (keys.length !== 0) {
      return { ok: false, code: "invalid-args", message: `${tool} takes no arguments` };
    }
    return { ok: true };
  }
  if (tool === "lab_read_file") {
    for (const key of keys) {
      if (key !== "path" && key !== "root_id") {
        return { ok: false, code: "invalid-args", message: `unknown argument: ${key}` };
      }
    }
    if (typeof args.path !== "string") {
      return { ok: false, code: "invalid-args", message: "path is required" };
    }
    if (
      args.root_id !== undefined &&
      args.root_id !== "workspace" &&
      args.root_id !== "reports" &&
      args.root_id !== "artifacts"
    ) {
      return { ok: false, code: "invalid-args", message: "root_id is invalid" };
    }
    return { ok: true };
  }
  if (tool === "lab_get_report") {
    if (keys.length !== 1 || typeof args.report_id !== "string" || !/^rep_[A-Za-z0-9_-]{4,64}$/.test(args.report_id)) {
      return { ok: false, code: "invalid-args", message: "report_id is invalid" };
    }
    return { ok: true };
  }
  if (tool === "lab_get_run_result") {
    if (keys.length !== 1 || typeof args.result_id !== "string" || !/^res_[A-Za-z0-9_-]{4,64}$/.test(args.result_id)) {
      return { ok: false, code: "invalid-args", message: "result_id is invalid" };
    }
    return { ok: true };
  }
  if (tool === "securitylab_vcan") {
    if (keys.length !== 1 || args.suite !== "unit_smoke" && args.suite !== "virtual_smoke") {
      return { ok: false, code: "invalid-args", message: "suite is invalid" };
    }
    return { ok: true };
  }
  return { ok: false, code: "tool-not-allowed", message: "unknown tool" };
}

export class FakeSecurityLabMcpClient implements SecurityLabMcpClient {
  #workspaces: Map<string, FakeWorkspace>;

  constructor(workspaces?: Map<string, FakeWorkspace>) {
    this.#workspaces = workspaces ?? seedWorkspaces();
  }

  listTools(context: SecurityLabContext): readonly SecurityLabToolDescriptor[] {
    if (validateContext(context) !== null || !isRoleId(context.role)) {
      return [];
    }
    const preset = getRolePreset(context.role);
    if (preset === undefined || preset.tool_profile !== context.tool_profile) {
      return [];
    }
    return preset.allowed_tools
      .filter((tool): tool is ToolName => isToolName(tool))
      .map((tool) => ({
        name: tool,
        enabled: tool !== "securitylab_vcan"
      }));
  }

  async callTool(
    context: SecurityLabContext,
    tool: ToolName,
    args: Record<string, unknown>
  ): Promise<SecurityLabResult> {
    const server = serverFor(tool);
    if (!isToolName(tool)) {
      return resultFail("lab_catalog", server, "tool-not-allowed", "unknown tool");
    }
    const contextError = validateContext(context);
    if (contextError !== null) {
      return resultFail(tool, server, "invalid-args", contextError);
    }
    const preset = getRolePreset(context.role);
    if (preset === undefined || preset.tool_profile !== context.tool_profile) {
      return resultFail(tool, server, "tool-not-allowed", "tool profile does not match the role");
    }
    if (!preset.allowed_tools.includes(tool)) {
      return resultFail(tool, server, "tool-not-allowed", "tool is not allowed for this role");
    }
    if (preset.mcp_server === "securitylab_vcan" || tool === "securitylab_vcan") {
      return resultFail(tool, server, "tool-disabled", "securitylab_vcan is disabled");
    }
    const argsValidation = validateArgs(tool, args);
    if (!argsValidation.ok) {
      return resultFail(tool, server, argsValidation.code, argsValidation.message);
    }
    const workspace = this.#workspaces.get(context.workspace_id);
    if (workspace === undefined) {
      return resultFail(tool, server, "not-found", "workspace is not available");
    }

    if (tool === "lab_status") {
      return resultOk(
        tool,
        server,
        { status: "ready", execution: "disabled", vcan: "disabled" },
        false,
        Buffer.byteLength(JSON.stringify({ status: "ready", execution: "disabled", vcan: "disabled" }), "utf8"),
        true
      );
    }

    if (tool === "lab_catalog") {
      const resources: Array<{ id: string; kind: string; title: string }> = [];
      for (const [id, report] of workspace.reports) {
        resources.push({ id, kind: "report", title: report.title });
      }
      for (const [id, result] of workspace.results) {
        resources.push({ id, kind: "run_result", title: `Run result (${result.status})` });
      }
      resources.push({ id: "workspace", kind: "file_root", title: "Workspace files" });
      resources.push({ id: "reports", kind: "file_root", title: "Reports" });
      resources.push({ id: "artifacts", kind: "file_root", title: "Artifacts" });
      const bounded = resources.slice(0, 100);
      const payload = { resources: bounded };
      return resultOk(
        tool,
        server,
        payload,
        false,
        Buffer.byteLength(JSON.stringify(payload), "utf8"),
        true
      );
    }

    if (tool === "lab_read_file") {
      const pathInput = args.path;
      const sanitized = sanitizeRelativePath(pathInput);
      if (!sanitized.ok || sanitized.path === null) {
        return resultFail(tool, server, "path-out-of-root", sanitized.reason ?? "invalid path");
      }
      const rootKind = (args.root_id ?? "workspace") as RootKind;
      const files = workspace.files[rootKind];
      if (files === undefined) {
        return resultFail(tool, server, "invalid-args", "root_id is invalid");
      }
      const rootPath =
        rootKind === "workspace" ? workspace.root : path.win32.join(workspace.root, rootKind);
      const containment = checkContainment(rootPath, sanitized.path);
      if (!containment.contained) {
        return resultFail(tool, server, "path-out-of-root", containment.reason ?? "outside root");
      }
      const file = files.get(sanitized.path);
      if (file === undefined) {
        return resultFail(tool, server, "not-found", "file is not available");
      }
      if (file.symlink !== undefined) {
        const symlinkContainment = checkContainment(rootPath, file.symlink);
        if (!symlinkContainment.contained) {
          return resultFail(tool, server, "symlink-escape", "symlink escapes the bound root");
        }
      }
      const redacted = redact(file.content);
      const truncated = truncateUtf8(redacted.content, OUTPUT_LIMIT);
      return resultOk(
        tool,
        server,
        { content: truncated.content, bytes: truncated.bytes, truncated: truncated.truncated },
        redacted.redacted,
        truncated.bytes,
        true
      );
    }

    if (tool === "lab_get_report") {
      const reportId = args.report_id as string;
      const report = workspace.reports.get(reportId);
      if (report === undefined) {
        return resultFail(tool, server, "not-found", "report is not available");
      }
      const redacted = redact(report.content);
      const truncated = truncateUtf8(redacted.content, OUTPUT_LIMIT);
      return resultOk(
        tool,
        server,
        { report_id: reportId, title: report.title, content: truncated.content, bytes: truncated.bytes, truncated: truncated.truncated },
        redacted.redacted,
        truncated.bytes,
        true
      );
    }

    if (tool === "lab_get_run_result") {
      const resultId = args.result_id as string;
      const runResult = workspace.results.get(resultId);
      if (runResult === undefined) {
        return resultFail(tool, server, "not-found", "run result is not available");
      }
      return resultOk(
        tool,
        server,
        { result_id: resultId, status: runResult.status, summary: runResult.summary },
        false,
        Buffer.byteLength(JSON.stringify(runResult), "utf8"),
        true
      );
    }

    return resultFail(tool, server, "tool-not-allowed", "tool is not implemented");
  }
}

export const ALL_SECURITYLAB_TOOLS: readonly ToolName[] = TOOL_NAMES;
