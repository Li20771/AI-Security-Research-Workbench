import { test } from "node:test";
import assert from "node:assert/strict";
import { makeHarness } from "./helpers.ts";
import { FakeMemoryPackClient } from "../src/memory/fake-memorypack-client.ts";
import { FixedClock } from "../src/time.ts";
import type {
  MemoryPack,
  MemoryPackClient,
  MemoryPackContext
} from "../src/memory/memorypack.ts";

async function runWorker(h: ReturnType<typeof makeHarness>) {
  const submission = await h.submitAs("researcher", "research", "analysis_a");
  assert.equal(submission.response.ok, true);
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");
  return h.controller.waitForRun(runId, 2000);
}

function badClient(
  transform: (pack: MemoryPack) => MemoryPack
): MemoryPackClient {
  const base = new FakeMemoryPackClient(new FixedClock());
  return {
    async getPack(context: MemoryPackContext): Promise<MemoryPack> {
      return transform(await base.getPack(context));
    }
  };
}

test("worker run fails closed when no MemoryPack client is configured", async () => {
  const h = makeHarness({ memoryPackClient: null });
  const run = await runWorker(h);
  assert.equal(run.status, "failed");
  assert.equal(run.reason_code, "memory-pack-required");
  assert.equal(h.adapter.openCalls, 0, "no worker session may start without a pack");
});

test("worker run rejects a pack whose snapshot hash does not match the binding", async () => {
  const h = makeHarness({
    memoryPackClient: badClient((pack) => ({
      ...pack,
      snapshot_hash: "0".repeat(64)
    }))
  });
  const run = await runWorker(h);
  assert.equal(run.status, "failed");
  assert.equal(run.reason_code, "memory-scope-mismatch");
  assert.equal(h.adapter.openCalls, 0);
});

test("worker run rejects an unsupported MemoryPack contract version", async () => {
  const h = makeHarness({
    memoryPackClient: badClient(
      (pack) =>
        ({
          ...pack,
          contract_version: "2.0.0",
          source: { ...pack.source, contract_version: "2.0.0" }
        }) as unknown as MemoryPack
    )
  });
  const run = await runWorker(h);
  assert.equal(run.status, "failed");
  assert.equal(run.reason_code, "memory-scope-mismatch");
  assert.equal(h.adapter.openCalls, 0);
});

test("worker run rejects a pack with a different workspace or run scope", async () => {
  const wrongWorkspace = makeHarness({
    memoryPackClient: badClient((pack) => ({
      ...pack,
      scope: { ...pack.scope, workspace_id: "ws_b" }
    }))
  });
  const workspaceRun = await runWorker(wrongWorkspace);
  assert.equal(workspaceRun.status, "failed");
  assert.equal(workspaceRun.reason_code, "memory-scope-mismatch");
  assert.equal(wrongWorkspace.adapter.openCalls, 0);

  const wrongRun = makeHarness({
    memoryPackClient: badClient((pack) => ({
      ...pack,
      run_id: "run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }))
  });
  const runRun = await runWorker(wrongRun);
  assert.equal(runRun.status, "failed");
  assert.equal(runRun.reason_code, "memory-scope-mismatch");
  assert.equal(wrongRun.adapter.openCalls, 0);
});
