import { test } from "node:test";
import assert from "node:assert/strict";
import { appendFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FleetPolicyError } from "../src/errors.ts";
import { InMemoryRunLedger, JsonlRunLedger, verifyLedgerEvents } from "../src/ledger.ts";
import { DeterministicIdGenerator } from "../src/ids.ts";
import { FixedClock } from "../src/time.ts";

function newLedger(): InMemoryRunLedger {
  return new InMemoryRunLedger({
    idGenerator: new DeterministicIdGenerator(),
    clock: new FixedClock()
  });
}

const runId = "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const wfiId = "wfi_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

test("ledger events form a verified hash chain and are frozen", () => {
  const ledger = newLedger();
  const created = ledger.append({
    type: "run.created",
    workflow_instance_id: wfiId,
    run_id: runId,
    task_id: "analysis_a",
    role: "researcher",
    data: {
      status: "created",
      request_id: "req_cccccccccccccccccccccccccccccccc",
      input_sha256: "d".repeat(64),
      workflow_id: "research",
      preset_id: "preset_researcher",
      preset_version: "1.0.0",
      workspace_id: "ws_a",
      episode_id: "ep_1",
      base_sha: null,
      memory_pack_snapshot_id: null,
      memory_pack_snapshot_hash: null,
      tool_profile: "researcher_ro_v1",
      approval_ref: null,
      deadline_ms: 60000,
      budget: { max_tokens: 1000, max_cost_usd: 0 },
      worker: true,
      parent_run_id: null
    }
  });
  const started = ledger.append({
    type: "run.started",
    workflow_instance_id: wfiId,
    run_id: runId,
    task_id: "analysis_a",
    role: "researcher",
    data: { status: "running", session_id: "dshsess_fake_0001" }
  });
  assert.equal(created.seq, 1);
  assert.equal(created.prev_hash, "0".repeat(64));
  assert.equal(started.seq, 2);
  assert.equal(started.prev_hash, created.hash);
  assert.equal(Object.isFrozen(created), true);
  assert.equal(ledger.verify().ok, true);
});

test("tampering breaks verification without mutating the ledger", () => {
  const ledger = newLedger();
  ledger.append({
    type: "run.created",
    workflow_instance_id: wfiId,
    run_id: runId,
    task_id: "analysis_a",
    role: "researcher",
    data: { status: "created", reason: "original" }
  });
  const copy = JSON.parse(JSON.stringify(ledger.readAll())) as Array<{
    data: Record<string, unknown>;
  }>;
  copy[0]!.data.reason = "tampered";
  const result = verifyLedgerEvents(copy as never);
  assert.equal(result.ok, false);
  assert.match(result.error ?? "", /hash mismatch/);
  assert.equal(ledger.verify().ok, true);
});

test("forbidden and unknown ledger fields are rejected before append", () => {
  const ledger = newLedger();
  assert.throws(
    () =>
      ledger.append({
        type: "run.created",
        workflow_instance_id: wfiId,
        run_id: runId,
        task_id: "analysis_a",
        role: "researcher",
        data: { prompt: "must not enter the ledger" }
      }),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "ledger-integrity"
  );
  assert.throws(
    () =>
      ledger.append({
        type: "run.created",
        workflow_instance_id: wfiId,
        run_id: runId,
        task_id: "analysis_a",
        role: "researcher",
        data: { unknown_field: "x" }
      }),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "ledger-integrity"
  );
  assert.equal(ledger.readAll().length, 0);
});

test("JSONL ledger reloads, verifies, and appends without rewriting prior events", () => {
  const dir = mkdtempSync(join(tmpdir(), "dsh-fleet-ledger-"));
  try {
    const path = join(dir, "run-ledger.jsonl");
    const ids = new DeterministicIdGenerator();
    const first = new JsonlRunLedger({
      filePath: path,
      idGenerator: ids,
      clock: new FixedClock()
    });
    first.append({
      type: "run.created",
      workflow_instance_id: wfiId,
      run_id: runId,
      task_id: "analysis_a",
      role: "researcher",
      data: { status: "created" }
    });
    const reloaded = new JsonlRunLedger({
      filePath: path,
      idGenerator: ids,
      clock: new FixedClock()
    });
    assert.equal(reloaded.readAll().length, 1);
    assert.equal(reloaded.verify().ok, true);
    const second = reloaded.append({
      type: "run.validated",
      workflow_instance_id: wfiId,
      run_id: runId,
      task_id: "analysis_a",
      role: "researcher",
      data: { status: "validated" }
    });
    assert.equal(second.seq, 2);
    assert.equal(reloaded.verify().ok, true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a corrupted JSONL ledger fails closed on load", () => {
  const dir = mkdtempSync(join(tmpdir(), "dsh-fleet-ledger-"));
  try {
    const path = join(dir, "run-ledger.jsonl");
    appendFileSync(path, "{not-json}\n", "utf8");
    assert.throws(
      () => new JsonlRunLedger({ filePath: path }),
      (error: unknown) => error instanceof FleetPolicyError && error.code === "ledger-integrity"
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
