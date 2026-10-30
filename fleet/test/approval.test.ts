import { test } from "node:test";
import assert from "node:assert/strict";
import { DenyAllApprovalVerifier, FakeApprovalRegistry } from "../src/approval.ts";
import { assertTransition, canTransition } from "../src/state-machine.ts";
import { FleetPolicyError } from "../src/errors.ts";

const context = {
  workflow_id: "security_audit" as const,
  task_id: "validation",
  workspace_id: "ws_a",
  role: "lab_runner" as const
};

test("approval grants are exact-scope, single-use, and fail closed", () => {
  const registry = new FakeApprovalRegistry();
  registry.register({
    approval_ref: "apr_test_0001",
    workflow_id: "security_audit",
    task_id: "validation",
    workspace_id: "ws_a",
    role: "lab_runner",
    state: "approved"
  });
  assert.equal(registry.verify("apr_test_0001", context), "approved");
  assert.equal(registry.verify("apr_test_0001", { ...context, workspace_id: "ws_b" }), "denied");
  assert.equal(registry.consume("apr_test_0001", "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), true);
  assert.equal(registry.verify("apr_test_0001", context), "denied");
  assert.equal(registry.consume("apr_test_0001", "run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"), false);
});

test("pending approval can be promoted to approved by the host", () => {
  const registry = new FakeApprovalRegistry();
  registry.register({
    approval_ref: "apr_test_0002",
    workflow_id: "security_audit",
    task_id: "validation",
    workspace_id: "ws_a",
    role: "lab_runner",
    state: "pending"
  });
  assert.equal(registry.verify("apr_test_0002", context), "pending");
  assert.equal(registry.consume("apr_test_0002", "run_cccccccccccccccccccccccccccccccc"), false);
  assert.equal(registry.setState("apr_test_0002", "approved"), true);
  assert.equal(registry.verify("apr_test_0002", context), "approved");
});

test("deny-all verifier and the waiting_approval state machine are fail closed", () => {
  const deny = new DenyAllApprovalVerifier();
  assert.equal(deny.verify("apr_test_0003", context), "denied");
  assert.equal(deny.consume("apr_test_0003", "run_dddddddddddddddddddddddddddddddd"), false);
  assert.equal(canTransition("validated", "waiting_approval"), true);
  assert.equal(canTransition("waiting_approval", "queued"), true);
  assert.equal(canTransition("completed", "running"), false);
  assert.throws(
    () => assertTransition("completed", "running"),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "internal-error"
  );
});
