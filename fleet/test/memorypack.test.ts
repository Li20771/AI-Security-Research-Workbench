import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeMemoryPackClient, RUN_PRIVATE_ID } from "../src/memory/fake-memorypack-client.ts";
import {
  MEMORYPACK_CONTRACT_VERSION,
  MemoryPackError,
  compareCodePoints,
  snapshotHashFor
} from "../src/memory/memorypack.ts";
import type { MemoryPackContext, MemoryPackEntry } from "../src/memory/memorypack.ts";
import { sha256OfJson } from "../src/canonical-json.ts";
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
  // Locks locale-independent code-point ordering and canonical JSON hashing.
  assert.equal(
    first.snapshot_hash,
    "1cc74ad9a67b090eb398d501e32f278bf7f4f001765dd693aa299e17f1401994"
  );
  assert.equal(first.snapshot_id, "mp_1cc74ad9a67b090eb398d501e32f278b");
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

test("memorypack ordering uses locale-independent Unicode code points", () => {
  // These pairs distinguish code-point order from both UTF-16 code-unit order
  // and host-locale collation.
  assert.ok(compareCodePoints("z.md", "Ä.md") < 0, "U+007A < U+00C4");
  assert.ok(compareCodePoints("Ä.md", "é.md") < 0, "U+00C4 < U+00E9");
  assert.ok(compareCodePoints("é.md", "😀.md") < 0, "U+00E9 < U+1F600");
  assert.ok("a😀.md" < "a\uE000.md", "UTF-16 code units order the surrogate first");
  assert.ok(
    compareCodePoints("a😀.md", "a\uE000.md") > 0,
    "code-point order places U+1F600 after U+E000"
  );
  assert.ok(compareCodePoints("a", "ab") < 0, "a proper prefix sorts first");
  assert.equal(compareCodePoints("same", "same"), 0);
});

test("snapshot hash is independent of entry input order and is code-point ordered", () => {
  const first = {
    entry_id: "mem_b",
    path: "workspaces/ws_a/memory/é.md",
    revision: "000000000002"
  } as MemoryPackEntry;
  const second = {
    entry_id: "mem_a",
    path: "workspaces/ws_a/memory/z.md",
    revision: "000000000001"
  } as MemoryPackEntry;
  const scope = { workspace_id: "ws_a", episode_id: "ep_1" };
  const forward = snapshotHashFor(scope, "researcher", [first, second]);
  const reverse = snapshotHashFor(scope, "researcher", [second, first]);
  assert.equal(forward, reverse);
  const changed = snapshotHashFor(scope, "researcher", [
    { ...first, revision: "000000000003" },
    second
  ]);
  assert.notEqual(changed, forward);

  // A surrogate-pair path and a private-use path differ under UTF-16 but the
  // contract orders by code point. Rebuild the expected canonical hash by hand
  // in that order so a future comparator regression is visible here too.
  const astral = {
    entry_id: "mem_astral",
    path: "a/😀.md",
    revision: "000000000004"
  } as MemoryPackEntry;
  const privateUse = {
    entry_id: "mem_private",
    path: "a/\uE000.md",
    revision: "000000000005"
  } as MemoryPackEntry;
  const codePointHash = snapshotHashFor(scope, "researcher", [astral, privateUse]);
  assert.equal(
    codePointHash,
    sha256OfJson({
      contract_version: MEMORYPACK_CONTRACT_VERSION,
      scope,
      role: "researcher",
      entries: [privateUse, astral]
    })
  );
});

test("createPackRef produces a stable read-only snapshot reference for bindings", async () => {
  const client = new FakeMemoryPackClient(new FixedClock());
  const first = await client.createPackRef("ws_a", "ep_1", "researcher");
  const second = await client.createPackRef("ws_a", "ep_1", "researcher");
  assert.deepEqual(first, second);
  assert.match(first.snapshot_id, /^mp_[a-f0-9]{32}$/);
  assert.match(first.snapshot_hash, /^[a-f0-9]{64}$/);
});
