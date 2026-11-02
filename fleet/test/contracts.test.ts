import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { verifyLedgerEvents } from "../src/ledger.ts";
import { makeHarness } from "./helpers.ts";

interface ValidateFn {
  (data: unknown): boolean;
  errors?: unknown;
}

interface AjvLike {
  addSchema(schema: object, id?: string): unknown;
  getSchema(id: string): ValidateFn | undefined;
  errorsText(errors: unknown, options?: { separator?: string }): string;
}

const require = createRequire(import.meta.url);
const Ajv2020 = require("ajv/dist/2020") as new (options?: Record<string, unknown>) => AjvLike;
const addFormats = require("ajv-formats") as (ajv: AjvLike) => void;

const CONTRACTS = join(process.cwd(), "..", "docs", "contracts");
const EXAMPLES = join(CONTRACTS, "examples");

const schemaFiles = [
  "fleet-submit-request.v1.schema.json",
  "fleet-status-query.v1.schema.json",
  "fleet-submit-response.v1.schema.json",
  "fleet-status-response.v1.schema.json",
  "fleet-result-response.v1.schema.json",
  "fleet-cancel-response.v1.schema.json",
  "worker-result.v1.schema.json",
  "run-ledger.v1.schema.json",
  "workflow-registry.v1.schema.json",
  "role-preset.v1.schema.json",
  "memorypack.v1.schema.json",
  "memorypack.v1.1.schema.json",
  "securitylab-tool-call.v1.schema.json",
  "securitylab-tool-result.v1.schema.json"
];

function makeAjv(): AjvLike {
  const ajv = new Ajv2020({
    allErrors: true,
    strict: true,
    strictRequired: false,
    allowUnionTypes: true
  });
  addFormats(ajv);
  for (const file of schemaFiles) {
    const schema = JSON.parse(readFileSync(join(CONTRACTS, file), "utf8")) as Record<string, unknown>;
    ajv.addSchema(schema, schema.$id as string);
  }
  return ajv;
}

function assertValid(ajv: AjvLike, schemaId: string, value: unknown, label: string): void {
  const validate = ajv.getSchema(schemaId);
  assert.ok(validate, `schema not found: ${schemaId}`);
  const ok = validate(value);
  assert.equal(ok, true, `${label}: ${ajv.errorsText(validate.errors, { separator: "\n" })}`);
}

test("all frozen examples validate against their schemas", () => {
  const ajv = makeAjv();
  const cases: Array<[string, string]> = [
    ["urn:dsh-fleet:contract:fleet-submit-request:1.0.0", "fleet-submit.research.request.json"],
    ["urn:dsh-fleet:contract:fleet-submit-response:1.0.0", "fleet-submit.response.json"],
    ["urn:dsh-fleet:contract:fleet-status-response:1.0.0", "fleet-status.response.json"],
    ["urn:dsh-fleet:contract:fleet-result-response:1.0.0", "fleet-result.response.json"],
    ["urn:dsh-fleet:contract:fleet-cancel-response:1.0.0", "fleet-cancel.response.json"],
    ["urn:dsh-fleet:contract:worker-result:1.0.0", "worker-result.challenger.json"],
    ["urn:dsh-fleet:contract:worker-result:1.0.0", "worker-result.evidence-verifier.json"],
    ["urn:dsh-fleet:contract:workflow-registry:1.0.0", "workflow.registry.json"],
    ["urn:dsh-fleet:contract:role-preset:1.0.0", "role-preset.registry.json"],
    ["urn:dsh-memory:contract:memorypack:1.0.0", "memorypack.example.json"],
    ["urn:dsh-memory:contract:memorypack:1.1.0", "memorypack.v1.1.example.json"],
    ["urn:securitylab:contract:tool-call:1.0.0", "securitylab-tool-call.example.json"],
    ["urn:securitylab:contract:tool-result:1.0.0", "securitylab-tool-result.example.json"]
  ];
  for (const [schemaId, example] of cases) {
    const value = JSON.parse(readFileSync(join(EXAMPLES, example), "utf8")) as unknown;
    assertValid(ajv, schemaId, value, example);
  }

  const ledgerEvents = readFileSync(join(EXAMPLES, "run-ledger.events.jsonl"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as unknown);
  for (const event of ledgerEvents) {
    assertValid(ajv, "urn:dsh-fleet:contract:run-ledger:1.0.0", event, "run-ledger example");
  }
  assert.equal(verifyLedgerEvents(ledgerEvents as never).ok, true);
});

test("MemoryPack v1.1 accepts NFC Unicode paths and rejects traversal/unsafe paths", () => {
  const ajv = makeAjv();
  const schema = "urn:dsh-memory:contract:memorypack:1.1.0";
  const base = JSON.parse(
    readFileSync(join(EXAMPLES, "memorypack.v1.1.example.json"), "utf8")
  ) as Record<string, unknown>;
  const withPath = (path: string): Record<string, unknown> => {
    const copy = structuredClone(base);
    const entries = copy.entries as Array<Record<string, unknown>>;
    entries[0]!.path = path;
    return copy;
  };
  assertValid(ajv, schema, withPath("workspaces/ws_a/memory/结论.md"), "Unicode path");
  assertValid(ajv, schema, withPath("workspaces/ws_a/memory/café.md"), "NFC path");
  for (const bad of ["../escape.md", "a/../b.md", "/abs.md", "C:/x.md", "a//b.md", "a/./b.md", "a\\b.md", "a:b.md"]) {
    const validate = ajv.getSchema(schema);
    assert.ok(validate);
    assert.equal(validate(withPath(bad)), false, `path must be rejected: ${JSON.stringify(bad)}`);
  }
});

test("invalid requests and queries are rejected by the frozen schemas", () => {
  const ajv = makeAjv();
  const submit = ajv.getSchema("urn:dsh-fleet:contract:fleet-submit-request:1.0.0");
  assert.ok(submit);
  assert.equal(
    submit({
      contract_version: "1.0.0",
      workflow_id: "research",
      task_id: "analysis_a",
      input: {},
      role: "researcher"
    }),
    false
  );
  const query = ajv.getSchema("urn:dsh-fleet:contract:fleet-status-query:1.0.0");
  assert.ok(query);
  assert.equal(query({ contract_version: "1.0.0" }), false);
  assert.equal(
    query({ contract_version: "1.0.0", run_id: "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", task_id: "analysis_a" }),
    false
  );
});

test("live Fleet responses and ledger events validate against the frozen schemas", async () => {
  const ajv = makeAjv();
  const h = makeHarness();

  const single = await h.submitAs("orchestrator", "single", "main");
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:fleet-submit-response:1.0.0",
    single.response,
    "single submit response"
  );
  const singleRunId = single.response.data?.run_id as string;
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:fleet-status-response:1.0.0",
    h.api.status({ contract_version: "1.0.0", run_id: singleRunId }, single.binding),
    "single status response"
  );

  const worker = await h.submitAs("researcher", "research", "analysis_a");
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:fleet-submit-response:1.0.0",
    worker.response,
    "worker submit response"
  );
  const workerRunId = worker.response.data?.run_id as string;
  await h.controller.waitForRun(workerRunId, 3000);
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:fleet-status-response:1.0.0",
    h.api.status({ contract_version: "1.0.0", run_id: workerRunId }, worker.binding),
    "worker status response"
  );
  const result = h.api.result(workerRunId, worker.binding);
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:fleet-result-response:1.0.0",
    result,
    "worker result response"
  );
  assert.ok(result.data);
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:worker-result:1.0.0",
    result.data.result.payload,
    "worker result payload"
  );

  const rejected = h.api.submit(
    {
      contract_version: "1.0.0",
      workflow_id: "research",
      task_id: "analysis_a",
      input: {}
    },
    {}
  );
  assertValid(
    ajv,
    "urn:dsh-fleet:contract:fleet-submit-response:1.0.0",
    rejected,
    "rejected submit response"
  );

  const ledgerSchema = "urn:dsh-fleet:contract:run-ledger:1.0.0";
  for (const event of h.ledger.readAll()) {
    assertValid(ajv, ledgerSchema, event, `ledger event ${event.seq}`);
  }
  assert.equal(h.ledger.verify().ok, true);
});
