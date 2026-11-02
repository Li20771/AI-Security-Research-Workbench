import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { makeHarness } from "./helpers.ts";
import { FakeSecurityLabMcpClient } from "../src/mcp/securitylab-client.ts";
import type { SecurityLabContext } from "../src/mcp/securitylab-client.ts";
import type { MemoryPack, MemoryPackContext } from "../src/memory/memorypack.ts";

const FIXTURE = join(
  process.cwd(),
  "test",
  "fixtures",
  "memorypack.v1.1.dsh-memory.json"
);

function readFixture(): MemoryPack {
  return JSON.parse(readFileSync(FIXTURE, "utf8")) as MemoryPack;
}

test("end-to-end fake run: dsh-memory pack + SecurityLab fake tool + Fleet ledger/result", async () => {
  const pack = readFixture();
  const client = new FakeSecurityLabMcpClient();
  const fixtureClient = {
    async getPack(context: MemoryPackContext): Promise<MemoryPack> {
      return {
        ...pack,
        scope: {
          workspace_id: context.workspace_id,
          episode_id: context.episode_id
        },
        role: context.role,
        run_id: context.run_id
      };
    }
  };
  const toolCalls: Array<{ tool: string; ok: boolean; executed: boolean; identity: string }> = [];

  const h = makeHarness({
    memoryPackClient: fixtureClient,
    adapter: {
      resultFactory: async ({ request }) => {
        const context: SecurityLabContext = {
          run_id: request.run_id,
          role: request.role,
          workspace_id: request.workspace_id,
          episode_id: request.episode_id,
          tool_profile: request.tool_profile ?? ""
        };
        const file = await client.callTool(context, "lab_read_file", { path: "notes.txt" });
        assert.equal(file.ok, true);
        assert.equal(file.meta.identity_source, "server-binding");
        assert.equal(file.meta.executed, true);
        assert.equal(file.meta.side_effects, 0);
        assert.equal(file.data?.content, "WS_A_WORKSPACE_CANARY");
        toolCalls.push({
          tool: "lab_read_file",
          ok: file.ok,
          executed: file.meta.executed,
          identity: file.meta.identity_source
        });

        return {
          summary: "Synthetic cross-repo run; no real DSH, MCP or lab was contacted.",
          claims: [
            {
              claim_id: "clm_0001",
              text: "Synthetic claim backed by a fake read-only file.",
              citations: [{ ref: "notes.txt", revision: "1", kind: "file" }]
            }
          ],
          citations: [{ ref: "notes.txt", revision: "1", kind: "file" }],
          artifacts: [],
          memory_candidates: [],
          requested_actions: [],
          limitations: [
            "Fake DSH adapter and fake SecurityLab MCP only; real runtime is NOT_RUN."
          ]
        };
      }
    }
  });

  const submission = await h.submitAs("researcher", "research", "analysis_a", {
    memory_pack: {
      snapshot_id: pack.snapshot_id,
      snapshot_hash: pack.snapshot_hash,
      workspace_id: pack.scope.workspace_id,
      episode_id: pack.scope.episode_id
    }
  });
  assert.equal(submission.response.ok, true);
  const runId = submission.response.data?.run_id;
  assert.ok(typeof runId === "string");

  const run = await h.controller.waitForRun(runId, 3000);
  assert.equal(run.status, "completed");
  assert.equal(toolCalls.length, 1);
  assert.deepEqual(toolCalls[0], {
    tool: "lab_read_file",
    ok: true,
    executed: true,
    identity: "server-binding"
  });
  assert.equal(h.adapter.openCalls, 1);
  assert.equal(h.adapter.closeCalls, 1);
  assert.equal(h.adapter.activeSessionCount, 0);

  const result = h.api.result(runId, submission.binding);
  assert.equal(result.ok, true);
  assert.equal(result.data?.untrusted, true);
  assert.equal(result.data?.admission, "none");
  assert.equal(result.data?.evidence, false);
  assert.equal(result.data?.result.payload.citations[0]?.ref, "notes.txt");

  const resultText = JSON.stringify(result);
  assert.equal(resultText.includes("WS_B_CANARY"), false);
  assert.equal(resultText.includes("WS_B_FOREIGN_CANARY"), false);

  const ledger = h.ledger.readAll();
  assert.equal(h.ledger.verify().ok, true);
  const created = ledger.find((event) => event.type === "run.created");
  assert.ok(created);
  assert.equal(created.data.memory_pack_snapshot_id, pack.snapshot_id);
  assert.equal(created.data.memory_pack_snapshot_hash, pack.snapshot_hash);
  assert.ok(ledger.some((event) => event.type === "run.completed"));
  const ledgerText = JSON.stringify(ledger);
  assert.equal(ledgerText.includes("Synthetic claim backed"), false);
  assert.equal(ledgerText.includes("WS_A_WORKSPACE_CANARY"), false);
});
