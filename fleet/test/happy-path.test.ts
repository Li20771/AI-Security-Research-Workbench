import { test } from "node:test";
import assert from "node:assert/strict";
import { makeHarness } from "./helpers.ts";

test("research worker completes, returns untrusted result, and leaves prompt content out of the ledger", async () => {
  const h = makeHarness();
  const submission = await h.submitAs("researcher", "research", "analysis_a", {
    input: { brief: "SYNTHETIC_PROMPT_SENTINEL", scenario: "synthetic" }
  });
  assert.equal(submission.response.ok, true);
  assert.equal(submission.response.data?.status, "queued");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");

  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "completed");
  assert.equal(h.adapter.openCalls, 1);
  assert.equal(h.adapter.cancelCalls, 0);
  assert.equal(h.adapter.closeCalls, 1);
  assert.equal(h.adapter.activeSessionCount, 0);

  const status = h.api.status({ contract_version: "1.0.0", run_id: runId }, submission.binding);
  assert.equal(status.ok, true);
  assert.equal(status.data?.runs[0]?.status, "completed");
  assert.equal(status.data?.runs[0]?.result_ref, `result://${runId}`);

  const result = h.api.result(runId, submission.binding);
  assert.equal(result.ok, true);
  assert.equal(result.data?.untrusted, true);
  assert.equal(result.data?.admission, "none");
  assert.equal(result.data?.evidence, false);
  assert.equal(result.data?.result.payload.summary.length > 0, true);
  assert.equal(result.data?.result_sha256.length, 64);

  const ledger = h.ledger.readAll();
  assert.equal(h.ledger.verify().ok, true);
  const serialized = JSON.stringify(ledger);
  assert.equal(serialized.includes("SYNTHETIC_PROMPT_SENTINEL"), false);
  assert.equal(serialized.includes("synthetic fixture"), false);
  const created = ledger.find((event) => event.type === "run.created");
  assert.ok(created);
  assert.equal(typeof created.data.input_sha256, "string");
  assert.equal(created.data.input_sha256, (created.data.input_sha256 as string));
});

test("single workflow completes without opening a DSH session and has no worker result", async () => {
  const h = makeHarness();
  const submission = await h.submitAs("orchestrator", "single", "main");
  assert.equal(submission.response.ok, true);
  assert.equal(submission.response.data?.status, "completed");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  assert.equal(h.adapter.openCalls, 0);

  const status = h.api.status({ contract_version: "1.0.0", run_id: runId }, submission.binding);
  assert.equal(status.ok, true);
  assert.equal(status.data?.runs[0]?.status, "completed");
  assert.equal(status.data?.runs[0]?.cleanup_state, "not_needed");

  const result = h.api.result(runId, submission.binding);
  assert.equal(result.ok, false);
  assert.equal(result.error?.code, "result-not-available");
  assert.equal(h.ledger.verify().ok, true);
});

test("workflow instance status is scoped and returns all runs for the caller", async () => {
  const h = makeHarness();
  const first = await h.submitAs("researcher", "research", "analysis_a");
  const runId = first.response.data?.run_id;
  assert.ok(typeof runId === "string");
  await h.controller.waitForRun(runId, 3000);

  const query = {
    contract_version: "1.0.0",
    workflow_instance_id: first.binding.workflow_instance_id
  };
  const status = h.api.status(query, first.binding);
  assert.equal(status.ok, true);
  assert.equal(status.data?.runs.length, 1);
  assert.equal(status.data?.runs[0]?.run_id, runId);
});
