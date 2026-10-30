import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

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

const root = process.cwd();
const contractsDir = join(root, "..", "docs", "contracts");
const examplesDir = join(contractsDir, "examples");

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

const ajv = new Ajv2020({
  allErrors: true,
  strict: true,
  strictRequired: false,
  allowUnionTypes: true
});
addFormats(ajv);

for (const file of schemaFiles) {
  const schema = JSON.parse(readFileSync(join(contractsDir, file), "utf8")) as Record<string, unknown>;
  ajv.addSchema(schema, schema.$id as string);
  if (schema.$id !== undefined) {
    console.log(`schema  ${file}  ${String(schema.$id)}`);
  }
}

type Case = { schema: string; example: string };
const cases: Case[] = [
  { schema: "urn:dsh-fleet:contract:fleet-submit-request:1.0.0", example: "fleet-submit.research.request.json" },
  { schema: "urn:dsh-fleet:contract:fleet-submit-response:1.0.0", example: "fleet-submit.response.json" },
  { schema: "urn:dsh-fleet:contract:fleet-status-response:1.0.0", example: "fleet-status.response.json" },
  { schema: "urn:dsh-fleet:contract:fleet-result-response:1.0.0", example: "fleet-result.response.json" },
  { schema: "urn:dsh-fleet:contract:fleet-cancel-response:1.0.0", example: "fleet-cancel.response.json" },
  { schema: "urn:dsh-fleet:contract:worker-result:1.0.0", example: "worker-result.challenger.json" },
  { schema: "urn:dsh-fleet:contract:worker-result:1.0.0", example: "worker-result.evidence-verifier.json" },
  { schema: "urn:dsh-fleet:contract:workflow-registry:1.0.0", example: "workflow.registry.json" },
  { schema: "urn:dsh-fleet:contract:role-preset:1.0.0", example: "role-preset.registry.json" },
  { schema: "urn:dsh-memory:contract:memorypack:1.0.0", example: "memorypack.example.json" },
  { schema: "urn:dsh-memory:contract:memorypack:1.1.0", example: "memorypack.v1.1.example.json" },
  { schema: "urn:securitylab:contract:tool-call:1.0.0", example: "securitylab-tool-call.example.json" },
  { schema: "urn:securitylab:contract:tool-result:1.0.0", example: "securitylab-tool-result.example.json" }
];

let failures = 0;
for (const c of cases) {
  const data = JSON.parse(readFileSync(join(examplesDir, c.example), "utf8")) as unknown;
  const validate = ajv.getSchema(c.schema);
  if (validate === undefined) {
    failures += 1;
    console.error(`FAIL no schema ${c.schema}`);
    continue;
  }
  if (validate(data)) {
    console.log(`PASS  ${c.example}`);
  } else {
    failures += 1;
    console.error(`FAIL  ${c.example}`);
    console.error(ajv.errorsText(validate.errors, { separator: "\n" }));
  }
}

const ledgerExample = join(examplesDir, "run-ledger.events.jsonl");
if (existsSync(ledgerExample)) {
  const events = readFileSync(ledgerExample, "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as unknown);
  const validate = ajv.getSchema("urn:dsh-fleet:contract:run-ledger:1.0.0");
  if (validate === undefined) {
    failures += 1;
    console.error("FAIL no run-ledger schema");
  } else {
    for (const [index, event] of events.entries()) {
      if (!validate(event)) {
        failures += 1;
        console.error(`FAIL  run-ledger.events.jsonl line ${index + 1}`);
        console.error(ajv.errorsText(validate.errors, { separator: "\n" }));
      }
    }
    console.log(`PASS  run-ledger.events.jsonl (${events.length} events)`);
  }
}

if (failures > 0) {
  console.error(`contract check failed: ${failures}`);
  process.exitCode = 1;
} else {
  console.log("contract check: PASS");
}
