import { test } from "node:test";
import assert from "node:assert/strict";
import type { ToolName } from "../src/contract.ts";
import { FakeSecurityLabMcpClient } from "../src/mcp/securitylab-client.ts";
import type { SecurityLabContext } from "../src/mcp/securitylab-client.ts";

function context(overrides: Partial<SecurityLabContext> = {}): SecurityLabContext {
  return {
    run_id: "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    role: "researcher",
    workspace_id: "ws_a",
    episode_id: "ep_1",
    tool_profile: "researcher_ro_v1",
    ...overrides
  };
}

test("read-only tool list is role-scoped and vcan is disabled", () => {
  const client = new FakeSecurityLabMcpClient();
  const researcher = client.listTools(context());
  assert.deepEqual(
    researcher.map((tool) => tool.name).sort(),
    ["lab_catalog", "lab_get_report", "lab_get_run_result", "lab_read_file", "lab_status"]
  );
  assert.equal(researcher.some((tool) => tool.name === "securitylab_vcan"), false);

  const labRunner = client.listTools(
    context({ role: "lab_runner", tool_profile: "lab_runner_vcan_v1" })
  );
  assert.deepEqual(labRunner, [{ name: "securitylab_vcan", enabled: false }]);
});

test("allowed file reads are bounded, read-only, and scoped to the bound root", async () => {
  const client = new FakeSecurityLabMcpClient();
  const file = await client.callTool(context(), "lab_read_file", { path: "notes.txt" });
  assert.equal(file.ok, true);
  assert.equal(file.meta.executed, true);
  assert.equal(file.meta.side_effects, 0);
  assert.equal(file.meta.identity_source, "server-binding");
  assert.equal(file.data?.content, "WS_A_WORKSPACE_CANARY");

  const report = await client.callTool(context(), "lab_read_file", {
    path: "report-1.md",
    root_id: "reports"
  });
  assert.equal(report.ok, true);
  assert.match(String(report.data?.content), /Report A/);
});

test("path traversal, absolute, drive, UNC, NUL, ADS, and symlink escape are rejected", async () => {
  const client = new FakeSecurityLabMcpClient();
  const cases: Array<Record<string, unknown>> = [
    { path: "../ws_b/reports/report-b.md" },
    { path: "..\\ws_b\\reports\\report-b.md" },
    { path: "/etc/passwd" },
    { path: "C:\\Windows\\win.ini" },
    { path: "\\\\server\\share\\file" },
    { path: "notes.txt\u0000" },
    { path: "notes.txt:stream" }
  ];
  for (const args of cases) {
    const result = await client.callTool(context(), "lab_read_file", args);
    assert.equal(result.ok, false, JSON.stringify(args));
    assert.equal(result.error?.code, "path-out-of-root", JSON.stringify(args));
    assert.equal(result.meta.executed, false);
    assert.equal(result.meta.side_effects, 0);
  }
  const symlink = await client.callTool(context(), "lab_read_file", { path: "link-out" });
  assert.equal(symlink.ok, false);
  assert.equal(symlink.error?.code, "symlink-escape");
  assert.equal(symlink.meta.executed, false);
});

test("identity fields in tool arguments are rejected", async () => {
  const client = new FakeSecurityLabMcpClient();
  const result = await client.callTool(context(), "lab_read_file", {
    path: "notes.txt",
    role: "orchestrator"
  });
  assert.equal(result.ok, false);
  assert.equal(result.error?.code, "identity-in-args");
  assert.equal(result.meta.executed, false);
  assert.equal(result.meta.side_effects, 0);
});

test("unknown tools and disabled vcan never execute", async () => {
  const client = new FakeSecurityLabMcpClient();
  const unknown = await client.callTool(context(), "not_a_tool" as ToolName, {});
  assert.equal(unknown.ok, false);
  assert.equal(unknown.error?.code, "tool-not-allowed");
  assert.equal(unknown.meta.executed, false);

  const vcan = await client.callTool(
    context({ role: "lab_runner", tool_profile: "lab_runner_vcan_v1" }),
    "securitylab_vcan",
    { suite: "unit_smoke" }
  );
  assert.equal(vcan.ok, false);
  assert.equal(vcan.error?.code, "tool-disabled");
  assert.equal(vcan.meta.executed, false);
  assert.equal(vcan.meta.side_effects, 0);
});

test("outputs are redacted and truncated at the 64 KiB limit", async () => {
  const client = new FakeSecurityLabMcpClient();
  const secret = await client.callTool(context(), "lab_read_file", { path: "secret.txt" });
  assert.equal(secret.ok, true);
  assert.equal(secret.meta.redacted, true);
  assert.equal(String(secret.data?.content).includes("REDACTION_TOKEN_SENTINEL"), false);
  assert.equal(String(secret.data?.content).includes("REDACTION_PASSWORD_SENTINEL"), false);
  assert.match(String(secret.data?.content), /\[REDACTED\]/);

  const large = await client.callTool(context(), "lab_read_file", { path: "large.txt" });
  assert.equal(large.ok, true);
  assert.equal(large.data?.truncated, true);
  assert.equal(large.data?.bytes, 65536);
  assert.equal(String(large.data?.content).length, 65536);
});

test("allowed reports and run results are readable without executing anything", async () => {
  const client = new FakeSecurityLabMcpClient();
  const report = await client.callTool(context(), "lab_get_report", { report_id: "rep_a_0001" });
  assert.equal(report.ok, true);
  assert.equal(report.data?.title, "Synthetic report A");
  assert.equal(report.meta.executed, true);
  const runResult = await client.callTool(context(), "lab_get_run_result", {
    result_id: "res_a_0001"
  });
  assert.equal(runResult.ok, true);
  assert.equal(runResult.data?.status, "completed");
  assert.equal(runResult.meta.executed, true);
});

test("cross-workspace reports/results are not visible and catalog leaks no absolute root", async () => {
  const client = new FakeSecurityLabMcpClient();
  const foreignReport = await client.callTool(context(), "lab_get_report", {
    report_id: "rep_b_0001"
  });
  assert.equal(foreignReport.ok, false);
  assert.equal(foreignReport.error?.code, "not-found");
  const foreignResult = await client.callTool(context(), "lab_get_run_result", {
    result_id: "res_b_0001"
  });
  assert.equal(foreignResult.ok, false);
  assert.equal(foreignResult.error?.code, "not-found");

  const catalog = await client.callTool(context(), "lab_catalog", {});
  assert.equal(catalog.ok, true);
  const serialized = JSON.stringify(catalog.data);
  assert.equal(serialized.includes("D:\\\\lab"), false);
  assert.equal(serialized.includes("ws_b"), false);

  const status = await client.callTool(context(), "lab_status", {});
  assert.equal(status.ok, true);
  assert.equal(status.data?.execution, "disabled");
  assert.equal(status.data?.vcan, "disabled");
});
