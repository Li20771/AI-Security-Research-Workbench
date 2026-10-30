import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { canonicalJson } from "../src/canonical-json.ts";
import { DeterministicIdGenerator } from "../src/ids.ts";
import { InMemoryRunLedger } from "../src/ledger.ts";
import { FixedClock } from "../src/time.ts";

const runId = "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const workflowInstanceId = "wfi_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
const requestId = "req_cccccccccccccccccccccccccccccccc";
const sessionId = "dshsess_fake_example_0001";
const ledger = new InMemoryRunLedger({
  idGenerator: new DeterministicIdGenerator(),
  clock: new FixedClock("2026-10-30T00:00:00.000Z")
});

const append = (type: Parameters<typeof ledger.append>[0]["type"], data: Record<string, unknown>) => {
  ledger.append({
    type,
    workflow_instance_id: workflowInstanceId,
    run_id: runId,
    task_id: "analysis_a",
    role: "researcher",
    data
  });
};

append("run.created", {
  status: "created",
  request_id: requestId,
  input_sha256: "d".repeat(64),
  workflow_id: "research",
  parent_run_id: null,
  preset_id: "preset_researcher",
  preset_version: "1.0.0",
  workspace_id: "ws_a",
  episode_id: "ep_1",
  base_sha: null,
  memory_pack_snapshot_id: "mp_44444444444444444444444444444444",
  memory_pack_snapshot_hash: "e".repeat(64),
  tool_profile: "researcher_ro_v1",
  approval_ref: null,
  deadline_ms: 60000,
  budget: { max_tokens: 1000, max_cost_usd: 0 },
  worker: true
});
append("run.validated", { status: "validated" });
append("run.queued", { status: "queued" });
append("run.session_opened", { session_id: sessionId });
append("run.started", { status: "running", session_id: sessionId });
append("run.cleanup", { cleanup_state: "succeeded" });
append("run.completed", {
  status: "completed",
  cleanup_state: "succeeded",
  duration_ms: 1000,
  worker: true,
  result_ref: `result://${runId}`,
  result_sha256: "f".repeat(64),
  artifact_refs: [
    {
      ref: `artifacts/${runId}/summary.json`,
      sha256: "a".repeat(64)
    }
  ],
  output_bytes: 128
});

const out = ledger
  .readAll()
  .map((event) => canonicalJson(event))
  .join("\n");
const target = join(process.cwd(), "..", "docs", "contracts", "examples", "run-ledger.events.jsonl");
writeFileSync(target, `${out}\n`, "utf8");
console.log(`wrote ${ledger.readAll().length} ledger events to ${target}`);
console.log(`ledger verify: ${ledger.verify().ok ? "PASS" : "FAIL"}`);
