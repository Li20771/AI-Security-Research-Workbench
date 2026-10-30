import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeMemoryPackClient, RUN_PRIVATE_ID } from "../src/memory/fake-memorypack-client.ts";
import { MemoryPackError } from "../src/memory/memorypack.ts";
import type { MemoryPackContext } from "../src/memory/memorypack.ts";
import { FixedClock } from "../src/time.ts";

function context(overrides: Partial<MemoryPackContext> = {}): MemoryPackContext {
  return {
    workspace_id: "ws_a",
    episode_id: "ep_1",
    role: "researcher",
    run_id: RUN_PRIVATE_ID,
    task_id: "analysis_a",
    purpose: "offline test",
    max_entries: 100,
    ...overrides
  };
}

test("ws_a pack includes approved scoped memory and excludes foreign/pending/restricted records", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const pack = await client.getPack(context());
  const bodies = pack.entries.map((entry) => entry.body);
  assert.equal(pack.contract_version, "1.1.0");
  assert.equal(pack.read_only, true);
  assert.equal(pack.scope.workspace_id, "ws_a");
  assert.ok(bodies.includes("WS_A_CANARY"));
  assert.ok(bodies.includes("WS_A_SHARED_CANARY"));
  assert.ok(bodies.includes("GLOBAL_CANARY"));
  assert.ok(bodies.includes("RUN_PRIVATE_CANARY"));
  assert.ok(bodies.includes("UNICODE_PATH_CANARY"), "NFC Unicode path must enter the pack");
  const unicode = pack.entries.find((entry) => entry.body === "UNICODE_PATH_CANARY");
  assert.ok(unicode);
  assert.equal(unicode.path, "workspaces/ws_a/memory/结论.md");
  assert.equal(unicode.path, unicode.path.normalize("NFC"));
  assert.equal(bodies.includes("WS_B_CANARY"), false);
  assert.equal(bodies.includes("PENDING_CANARY"), false);
  assert.equal(bodies.includes("REJECTED_CANARY"), false);
  assert.equal(bodies.includes("SUPERSEDED_CANARY"), false);
  assert.equal(bodies.includes("RESTRICTED_CANARY"), false);
  assert.equal(bodies.includes("OTHER_EPISODE_CANARY"), false);
  assert.equal(bodies.includes("UNMARKED_CANARY"), false);
  assert.equal(bodies.includes("BAD_PATH_CANARY"), false);
  assert.equal(pack.excluded.pending, 1);
  assert.equal(pack.excluded.rejected, 1);
  assert.equal(pack.excluded.superseded, 1);
  assert.equal(pack.excluded.restricted, 1);
  assert.equal(pack.excluded.unmarked, 1);
  assert.equal(pack.excluded.path_invalid, 1);
  assert.equal(pack.excluded.entry_invalid, 0);
  // The explicit user-global seed has no origin scope and must use `global`,
  // not the requester's workspace id; that makes cross_workspace true.
  const global = pack.entries.find((entry) => entry.body === "GLOBAL_CANARY");
  assert.ok(global);
  assert.equal(global.workspace_id, "global");
  assert.equal(pack.policy.cross_workspace, true);
  assert.equal(pack.policy.authorized_before_retrieval, true);
  assert.match(pack.snapshot_id, /^mp_[a-f0-9]{32}$/);
  assert.match(pack.snapshot_hash, /^[a-f0-9]{64}$/);
  assert.equal(
    pack.policy.cross_workspace,
    pack.entries.some(
      (entry) => entry.visibility === "user-global" && entry.workspace_id !== pack.scope.workspace_id
    ),
    "cross_workspace must match the actual entries"
  );
});

test("snapshot hashes are deterministic for the same authorized entry set", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const first = await client.getPack(context());
  const second = await client.getPack(context());
  assert.equal(first.snapshot_hash, second.snapshot_hash);
  assert.equal(first.snapshot_id, second.snapshot_id);
});

test("unmarked legacy records never cross workspaces", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const wsA = await client.getPack(context());
  const wsB = await client.getPack(
    context({ workspace_id: "ws_b", episode_id: "ep_b", run_id: "run_ffffffffffffffffffffffffffffffff" })
  );
  assert.equal(wsA.entries.some((entry) => entry.body === "UNMARKED_CANARY"), false);
  assert.equal(wsB.entries.some((entry) => entry.body === "UNMARKED_CANARY"), false);
  assert.equal(wsA.excluded.unmarked, 1);
  assert.equal(wsB.excluded.unmarked, 0, "another workspace's unmarked record is not counted");
});

test("ws_b sees its own records plus explicit user-global, but never ws_a canaries", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const pack = await client.getPack(
    context({ workspace_id: "ws_b", episode_id: "ep_b", run_id: "run_ffffffffffffffffffffffffffffffff" })
  );
  const bodies = pack.entries.map((entry) => entry.body);
  assert.ok(bodies.includes("WS_B_CANARY"));
  assert.ok(bodies.includes("GLOBAL_CANARY"));
  assert.equal(bodies.includes("WS_A_CANARY"), false);
  assert.equal(bodies.includes("WS_A_SHARED_CANARY"), false);
  assert.equal(pack.policy.cross_workspace, true);
});

test("run-private and episode-shared scopes are enforced", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const otherRun = await client.getPack(
    context({ run_id: "run_ffffffffffffffffffffffffffffffff" })
  );
  assert.equal(otherRun.entries.some((entry) => entry.body === "RUN_PRIVATE_CANARY"), false);

  const otherEpisode = await client.getPack(context({ episode_id: "ep_2" }));
  const bodies = otherEpisode.entries.map((entry) => entry.body);
  assert.equal(bodies.includes("WS_A_CANARY"), false);
  assert.ok(bodies.includes("OTHER_EPISODE_CANARY"));
});

test("top-k happens after authorization and cannot promote foreign records", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const pack = await client.getPack(context({ max_entries: 1 }));
  assert.equal(pack.entries.length, 1);
  assert.equal(pack.entries[0]?.body, "GLOBAL_CANARY");
  assert.equal(pack.entries.some((entry) => entry.body === "WS_B_CANARY"), false);
  assert.deepEqual(pack.excluded, {
    pending: 1,
    rejected: 1,
    superseded: 1,
    restricted: 1,
    unmarked: 1,
    path_invalid: 1,
    entry_invalid: 0
  });
});

test("missing/invalid context fails closed and the interface has no write method", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  await assert.rejects(
    () => client.getPack(context({ workspace_id: "ws_disabled" })),
    (error: unknown) => error instanceof MemoryPackError && error.code === "memory-workspace-denied"
  );
  await assert.rejects(
    () => client.getPack(context({ max_entries: 0 })),
    (error: unknown) => error instanceof MemoryPackError && error.code === "memory-scope-invalid"
  );
  const record = client as unknown as Record<string, unknown>;
  assert.equal(record.write, undefined);
  assert.equal(record.update, undefined);
  assert.equal(record.delete, undefined);
});

test("createPackRef produces a stable read-only snapshot reference for bindings", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const first = await client.createPackRef("ws_a", "ep_1", "researcher");
  const second = await client.createPackRef("ws_a", "ep_1", "researcher");
  assert.deepEqual(first, second);
  assert.match(first.snapshot_id, /^mp_[a-f0-9]{32}$/);
  assert.match(first.snapshot_hash, /^[a-f0-9]{64}$/);
});
