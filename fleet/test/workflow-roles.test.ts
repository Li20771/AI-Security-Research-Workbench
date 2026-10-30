import { test } from "node:test";
import assert from "node:assert/strict";
import { makeHarness } from "./helpers.ts";

test("challenger and verifier roles receive role-specific structured result validation", async () => {
  const h = makeHarness();
  const analysis = await h.submitAs("researcher", "research", "analysis_a");
  const analysisRunId = analysis.response.data?.run_id;
  assert.ok(typeof analysisRunId === "string");
  await h.controller.waitForRun(analysisRunId, 3000);
  const workflowInstanceId = analysis.binding.workflow_instance_id;

  const challenge = await h.submitAs("challenger", "research", "challenge", {
    workflow_instance_id: workflowInstanceId,
    parent_run_id: analysisRunId
  });
  assert.equal(challenge.response.ok, true);
  const challengeRunId = challenge.response.data?.run_id;
  assert.ok(typeof challengeRunId === "string");
  const challengeRun = await h.controller.waitForRun(challengeRunId, 3000);
  assert.equal(challengeRun.status, "completed");
  const challengeResult = h.api.result(challengeRunId, challenge.binding);
  assert.equal(challengeResult.ok, true);
  assert.ok(Array.isArray(challengeResult.data?.result.payload.findings));

  const verify = await h.submitAs("evidence_verifier", "research", "verify", {
    workflow_instance_id: workflowInstanceId,
    parent_run_id: challengeRunId
  });
  assert.equal(verify.response.ok, true);
  const verifyRunId = verify.response.data?.run_id;
  assert.ok(typeof verifyRunId === "string");
  const verifyRun = await h.controller.waitForRun(verifyRunId, 3000);
  assert.equal(verifyRun.status, "completed");
  const verifyResult = h.api.result(verifyRunId, verify.binding);
  assert.equal(verifyResult.ok, true);
  assert.ok((verifyResult.data?.result.payload.verdicts?.length ?? 0) >= 1);
  assert.equal(verifyResult.data?.result.payload.verdicts?.[0]?.verdict, "unresolved");
});

test("design_review runs design -> challenge -> verify in one workflow instance", async () => {
  const h = makeHarness();
  const design = await h.submitAs("vehicle_analyst", "design_review", "design");
  const designRunId = design.response.data?.run_id;
  assert.ok(typeof designRunId === "string");
  await h.controller.waitForRun(designRunId, 3000);
  const workflowInstanceId = design.binding.workflow_instance_id;

  const challenge = await h.submitAs("challenger", "design_review", "challenge", {
    workflow_instance_id: workflowInstanceId,
    parent_run_id: designRunId
  });
  const challengeRunId = challenge.response.data?.run_id;
  assert.ok(typeof challengeRunId === "string");
  await h.controller.waitForRun(challengeRunId, 3000);

  const verify = await h.submitAs("evidence_verifier", "design_review", "verify", {
    workflow_instance_id: workflowInstanceId,
    parent_run_id: challengeRunId
  });
  assert.equal(verify.response.ok, true);
  const verifyRunId = verify.response.data?.run_id;
  assert.ok(typeof verifyRunId === "string");
  const verifyRun = await h.controller.waitForRun(verifyRunId, 3000);
  assert.equal(verifyRun.status, "completed");

  const scoped = h.api.status(
    { contract_version: "1.0.0", workflow_instance_id: workflowInstanceId },
    design.binding
  );
  assert.equal(scoped.ok, true);
  assert.equal(scoped.data?.runs.length, 1);
  assert.equal(scoped.data?.runs[0]?.role, "vehicle_analyst");

  const orchestratorBinding = await h.issueBinding("orchestrator", {
    workflow_instance_id: workflowInstanceId
  });
  const allRuns = h.api.status(
    { contract_version: "1.0.0", workflow_instance_id: workflowInstanceId },
    orchestratorBinding
  );
  assert.equal(allRuns.ok, true);
  assert.equal(allRuns.data?.runs.length, 3);
});

test("result is not ready while a run is still active", async () => {
  const h = makeHarness({ adapter: { mode: "hang" } });
  const submission = await h.submitAs("researcher", "research", "analysis_a");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  await new Promise((resolve) => setTimeout(resolve, 20));
  const result = h.api.result(runId, submission.binding);
  assert.equal(result.ok, false);
  assert.equal(result.error?.code, "result-not-ready");
  await h.api.cancel(runId, submission.binding);
});
