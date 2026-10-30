import { test } from "node:test";
import assert from "node:assert/strict";
import { makeHarness } from "./helpers.ts";

async function waitUntil(predicate: () => boolean, timeoutMs: number = 1000): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error("waitUntil timeout");
    }
    await new Promise((resolve) => {
      setTimeout(resolve, 5);
    });
  }
}

test("timeout propagates to the fake runtime and records timed_out with cleanup succeeded", async () => {
  const h = makeHarness({ adapter: { mode: "hang" } });
  const submission = await h.submitAs("researcher", "research", "analysis_a", {
    deadline_ms: 30
  });
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "timed_out");
  assert.equal(run.cleanup_state, "succeeded");
  assert.equal(h.adapter.cancelCalls, 1);
  assert.equal(h.adapter.closeCalls, 1);
  assert.equal(h.adapter.activeSessionCount, 0);
  assert.equal(h.ledger.verify().ok, true);
});

test("kill/cleanup failure becomes blocked, never cancelled or timed out", async () => {
  const h = makeHarness({ adapter: { mode: "hang", cancelCleaned: false } });
  const submission = await h.submitAs("researcher", "research", "analysis_a", {
    deadline_ms: 30
  });
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "blocked");
  assert.equal(run.cleanup_state, "failed");
  assert.equal(run.reason_code, "adapter-cancel-failed");
  assert.equal(h.adapter.cancelCalls, 1);
  assert.equal(h.ledger.verify().ok, true);
});

test("explicit cancel propagates and returns cancelled when cleanup succeeds", async () => {
  const h = makeHarness({ adapter: { mode: "hang" } });
  const submission = await h.submitAs("researcher", "research", "analysis_a");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  await waitUntil(() => h.adapter.openCalls === 1 && h.adapter.activeSessionCount === 1);
  const cancelled = await h.api.cancel(runId, submission.binding);
  assert.equal(cancelled.ok, true);
  assert.equal(cancelled.data?.status, "cancelled");
  assert.equal(cancelled.data?.cleanup.state, "succeeded");
  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "cancelled");
  assert.equal(h.adapter.cancelCalls, 1);
  assert.equal(h.adapter.activeSessionCount, 0);
});

test("malformed worker output fails validation and never becomes completed", async () => {
  const h = makeHarness({ adapter: { mode: "malformed" } });
  const submission = await h.submitAs("researcher", "research", "analysis_a");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "failed");
  assert.equal(run.reason_code, "invalid-worker-result");
  const result = h.api.result(runId, submission.binding);
  assert.equal(result.ok, false);
  assert.equal(result.error?.code, "result-not-available");
});

test("adapter crash becomes a failed run and cleanup is attempted", async () => {
  const h = makeHarness({ adapter: { mode: "crash" } });
  const submission = await h.submitAs("researcher", "research", "analysis_a");
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "failed");
  assert.equal(run.reason_code, "internal-error");
  assert.equal(h.adapter.cancelCalls, 1);
  assert.equal(h.adapter.activeSessionCount, 0);
});

test("concurrent runs use distinct sessions and do not share inputs or results", async () => {
  const h = makeHarness({ adapter: { mode: "success", delayMs: 10 } });
  h.adapter.resultFactory = ({ input }) => {
    const brief =
      typeof input === "object" && input !== null && "brief" in input
        ? String((input as { brief: unknown }).brief)
        : "missing";
    return {
      summary: `echo:${brief}`,
      claims: [],
      citations: [],
      artifacts: [],
      memory_candidates: [],
      requested_actions: [],
      limitations: ["fake concurrency test"]
    };
  };
  const first = await h.submitAs("researcher", "research", "analysis_a", {
    input: { brief: "first-input" }
  });
  const second = await h.submitAs("researcher", "research", "analysis_a", {
    input: { brief: "second-input" }
  });
  const firstId = first.response.data?.run_id;
  const secondId = second.response.data?.run_id;
  assert.ok(typeof firstId === "string");
  assert.ok(typeof secondId === "string");
  const [firstRun, secondRun] = await Promise.all([
    h.controller.waitForRun(firstId, 3000),
    h.controller.waitForRun(secondId, 3000)
  ]);
  assert.equal(firstRun.status, "completed");
  assert.equal(secondRun.status, "completed");
  assert.notEqual(firstRun.session_id, secondRun.session_id);
  assert.equal(h.adapter.sessionIds.length, 2);
  assert.equal(h.adapter.maxConcurrent, 2);
  const firstResult = h.api.result(firstId, first.binding);
  const secondResult = h.api.result(secondId, second.binding);
  assert.equal(firstResult.data?.result.payload.summary, "echo:first-input");
  assert.equal(secondResult.data?.result.payload.summary, "echo:second-input");
});

test("restart reconcile blocks an orphaned run without reopening a session", async () => {
  const h = makeHarness();
  const runId = "run_22222222222222222222222222222222";
  const workflowInstanceId = "wfi_11111111111111111111111111111111";
  const baseData = {
    status: "created",
    request_id: "req_33333333333333333333333333333333",
    input_sha256: "a".repeat(64),
    workflow_id: "research",
    preset_id: "preset_researcher",
    preset_version: "1.0.0",
    workspace_id: "ws_a",
    episode_id: "ep_1",
    base_sha: null,
    memory_pack_snapshot_id: "mp_44444444444444444444444444444444",
    memory_pack_snapshot_hash: "b".repeat(64),
    tool_profile: "researcher_ro_v1",
    approval_ref: null,
    deadline_ms: 60000,
    budget: { max_tokens: 1000, max_cost_usd: 0 },
    worker: true,
    parent_run_id: null
  };
  const append = (type: Parameters<typeof h.ledger.append>[0]["type"], data: Record<string, unknown>) => {
    h.ledger.append({
      type,
      workflow_instance_id: workflowInstanceId,
      run_id: runId,
      task_id: "analysis_a",
      role: "researcher",
      data
    });
  };
  append("run.created", baseData);
  append("run.validated", { status: "validated" });
  append("run.queued", { status: "queued" });
  append("run.session_opened", { session_id: "dshsess_fake_orphan" });
  append("run.started", { status: "running", session_id: "dshsess_fake_orphan" });

  const report = h.controller.reconcile();
  assert.deepEqual(report, { reconciled: 1, run_ids: [runId] });
  assert.equal(h.adapter.openCalls, 0);
  assert.equal(h.adapter.cancelCalls, 0);
  const binding = await h.issueBinding("researcher");
  const status = h.api.status({ contract_version: "1.0.0", run_id: runId }, binding);
  assert.equal(status.ok, true);
  assert.equal(status.data?.runs[0]?.status, "blocked");
  assert.equal(status.data?.runs[0]?.reason_code, "orphaned-after-restart");
  assert.equal(status.data?.runs[0]?.cleanup_state, "unknown");
  assert.equal(h.ledger.verify().ok, true);
});
