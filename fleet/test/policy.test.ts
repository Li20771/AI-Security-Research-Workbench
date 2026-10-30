import { test } from "node:test";
import assert from "node:assert/strict";
import { FleetPolicyError } from "../src/errors.ts";
import { makeHarness } from "./helpers.ts";

test("a binding that was not issued by the trusted host is rejected", async () => {
  const h = makeHarness();
  const response = h.api.submit(
    {
      contract_version: "1.0.0",
      workflow_id: "research",
      task_id: "analysis_a",
      input: { brief: "synthetic" }
    },
    { role: "researcher", workspace_id: "ws_a" }
  );
  assert.equal(response.ok, false);
  assert.equal(response.error?.code, "untrusted-binding");
  const rejected = h.ledger.readAll().find((event) => event.type === "request.rejected");
  assert.ok(rejected);
  assert.equal(rejected.run_id, null);
  assert.equal(rejected.role, null);
  assert.equal(h.ledger.verify().ok, true);
});

test("request-level identity fields are rejected before a run is created", async () => {
  const h = makeHarness();
  const binding = await h.issueBinding("researcher");
  const response = h.api.submit(
    {
      contract_version: "1.0.0",
      workflow_id: "research",
      task_id: "analysis_a",
      input: { brief: "synthetic" },
      role: "lab_runner"
    },
    binding
  );
  assert.equal(response.ok, false);
  assert.equal(response.error?.code, "identity-in-request");
  assert.equal(h.adapter.openCalls, 0);
});

test("disabled workflows and disabled roles fail closed", async () => {
  const h = makeHarness();
  const labValidation = await h.submitAs("lab_runner", "lab_validation", "suite_run");
  assert.equal(labValidation.response.ok, false);
  assert.equal(labValidation.response.error?.code, "workflow-disabled");

  const labRole = await h.submitAs("lab_runner", "security_audit", "validation");
  assert.equal(labRole.response.ok, false);
  assert.equal(labRole.response.error?.code, "role-disabled");
  assert.equal(h.adapter.openCalls, 0);
});

test("unknown task and role-not-allowed are rejected", async () => {
  const h = makeHarness();
  const unknownTask = await h.submitAs("researcher", "research", "no_such_task");
  assert.equal(unknownTask.response.ok, false);
  assert.equal(unknownTask.response.error?.code, "task-unknown");

  const wrongRole = await h.submitAs("researcher", "research", "challenge");
  assert.equal(wrongRole.response.ok, false);
  assert.equal(wrongRole.response.error?.code, "role-not-allowed");
});

test("worker runs require a memory pack and enforce deadline/budget caps", async () => {
  const h = makeHarness();
  const noPack = await h.submitAs("researcher", "research", "analysis_a", {
    memory_pack: null
  });
  assert.equal(noPack.response.ok, false);
  assert.equal(noPack.response.error?.code, "memory-pack-required");

  const deadline = await h.submitAs("researcher", "research", "analysis_a", {
    deadline_ms: 999999
  });
  assert.equal(deadline.response.ok, false);
  assert.equal(deadline.response.error?.code, "deadline-exceeds-preset");

  const budget = await h.submitAs("researcher", "research", "analysis_a", {
    budget: { max_tokens: 999999, max_cost_usd: 0 }
  });
  assert.equal(budget.response.ok, false);
  assert.equal(budget.response.error?.code, "budget-exceeds-preset");
});

test("dependency runs require a completed parent in the same workflow instance", async () => {
  const h = makeHarness();
  const missing = await h.submitAs("challenger", "research", "challenge");
  assert.equal(missing.response.ok, false);
  assert.equal(missing.response.error?.code, "dependency-not-satisfied");

  const analysis = await h.submitAs("researcher", "research", "analysis_a");
  const analysisRunId = analysis.response.data?.run_id;
  assert.ok(typeof analysisRunId === "string");
  const analysisRun = await h.controller.waitForRun(analysisRunId, 3000);
  assert.equal(analysisRun.status, "completed");

  const challenge = await h.submitAs("challenger", "research", "challenge", {
    workflow_instance_id: analysis.binding.workflow_instance_id,
    parent_run_id: analysisRunId
  });
  assert.equal(challenge.response.ok, true);
  const challengeRunId = challenge.response.data?.run_id;
  assert.ok(typeof challengeRunId === "string");
  const challengeRun = await h.controller.waitForRun(challengeRunId, 3000);
  assert.equal(challengeRun.status, "completed");
  assert.equal(challengeRun.parent_run_id, analysisRunId);
});

test("retry uses a new run id and preserves the failed original", async () => {
  const h = makeHarness({ adapter: { mode: "start-failure" } });
  const first = await h.submitAs("researcher", "research", "analysis_a");
  const firstRunId = first.response.data?.run_id;
  assert.ok(typeof firstRunId === "string");
  const failed = await h.controller.waitForRun(firstRunId, 3000);
  assert.equal(failed.status, "failed");

  h.adapter.mode = "success";
  const retry = await h.submitAs("researcher", "research", "analysis_a", {
    workflow_instance_id: first.binding.workflow_instance_id,
    parent_run_id: firstRunId
  });
  assert.equal(retry.response.ok, true);
  const retryRunId = retry.response.data?.run_id;
  assert.ok(typeof retryRunId === "string");
  assert.notEqual(retryRunId, firstRunId);
  const retried = await h.controller.waitForRun(retryRunId, 3000);
  assert.equal(retried.status, "completed");
  assert.equal(h.controller.status({ contract_version: "1.0.0", run_id: firstRunId }, first.binding).data?.runs[0]?.status, "failed");
});

test("cross-workspace status and result are not visible", async () => {
  const h = makeHarness();
  const foreign = await h.submitAs("researcher", "research", "analysis_a", {
    workspace_id: "ws_b",
    episode_id: "ep_b"
  });
  const foreignRunId = foreign.response.data?.run_id;
  assert.ok(typeof foreignRunId === "string");
  await h.controller.waitForRun(foreignRunId, 3000);

  const localBinding = await h.issueBinding("researcher");
  const status = h.api.status({ contract_version: "1.0.0", run_id: foreignRunId }, localBinding);
  assert.equal(status.ok, false);
  assert.equal(status.error?.code, "run-not-found");
  const result = h.api.result(foreignRunId, localBinding);
  assert.equal(result.ok, false);
  assert.equal(result.error?.code, "run-not-found");
  const instanceStatus = h.api.status(
    { contract_version: "1.0.0", workflow_instance_id: foreign.binding.workflow_instance_id },
    localBinding
  );
  assert.equal(instanceStatus.ok, false);
  assert.equal(instanceStatus.error?.code, "run-not-found");
});

test("a terminal run cannot be cancelled", async () => {
  const h = makeHarness();
  const submission = await h.submitAs("researcher", "research", "analysis_a");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  await h.controller.waitForRun(runId, 3000);
  const response = await h.api.cancel(runId, submission.binding);
  assert.equal(response.ok, false);
  assert.equal(response.error?.code, "run-not-cancellable");
});

test("preset concurrency limit rejects a third active run", async () => {
  const h = makeHarness({ adapter: { mode: "hang" } });
  const first = await h.submitAs("researcher", "research", "analysis_a");
  const second = await h.submitAs("researcher", "research", "analysis_a");
  const third = await h.submitAs("researcher", "research", "analysis_a");
  assert.equal(first.response.ok, true);
  assert.equal(second.response.ok, true);
  assert.equal(third.response.ok, false);
  assert.equal(third.response.error?.code, "concurrency-limit");

  const firstId = first.response.data?.run_id;
  const secondId = second.response.data?.run_id;
  assert.ok(typeof firstId === "string");
  assert.ok(typeof secondId === "string");
  const cancelledFirst = await h.api.cancel(firstId, first.binding);
  const cancelledSecond = await h.api.cancel(secondId, second.binding);
  assert.equal(cancelledFirst.ok, true);
  assert.equal(cancelledSecond.ok, true);
  assert.equal(cancelledFirst.data?.status, "cancelled");
  assert.equal(cancelledSecond.data?.status, "cancelled");
});

test("binding issuer rejects workspace, preset, and memory scope mismatches", async () => {
  const h = makeHarness();
  assert.throws(
    () =>
      h.issuer.issue({
        workflow_instance_id: "wfi_00000000000000000000000000000001",
        workspace_id: "ws_disabled",
        episode_id: "ep_1",
        role: "researcher",
        preset_id: "preset_researcher",
        preset_version: "1.0.0",
        tool_profile: "researcher_ro_v1"
      }),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "workspace-disabled"
  );
  assert.throws(
    () =>
      h.issuer.issue({
        workflow_instance_id: "wfi_00000000000000000000000000000002",
        workspace_id: "ws_a",
        episode_id: "ep_1",
        role: "researcher",
        preset_id: "preset_challenger",
        preset_version: "1.0.0",
        tool_profile: "challenger_ro_v1"
      }),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "preset-mismatch"
  );
  const foreignPack = await h.memory.createPackRef("ws_b", "ep_b", "researcher");
  assert.throws(
    () =>
      h.issuer.issue({
        workflow_instance_id: "wfi_00000000000000000000000000000003",
        workspace_id: "ws_a",
        episode_id: "ep_1",
        role: "researcher",
        preset_id: "preset_researcher",
        preset_version: "1.0.0",
        tool_profile: "researcher_ro_v1",
        memory_pack: foreignPack
      }),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "memory-scope-mismatch"
  );
});
