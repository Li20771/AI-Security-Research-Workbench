import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { sha256OfJson } from "../src/canonical-json.ts";
import {
  compareCodePoints,
  snapshotHashFor,
  snapshotIdFor
} from "../src/memory/memorypack.ts";
import type { MemoryPack, MemoryPackEntry } from "../src/memory/memorypack.ts";

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
const SCHEMA_ID = "urn:dsh-memory:contract:memorypack:1.2.0";
const FIXTURE = join(
  process.cwd(),
  "test",
  "fixtures",
  "memorypack.v1.2.dsh-memory.json"
);

const LAYER_ORDER: Readonly<Record<string, number>> = {
  L1: 1,
  L2: 2,
  L3: 3,
  L4: 4,
  KB: 5
};

function makeAjv(): AjvLike {
  const ajv = new Ajv2020({
    allErrors: true,
    strict: true,
    strictRequired: false,
    allowUnionTypes: true
  });
  addFormats(ajv);
  for (const file of ["memorypack.v1.2.schema.json"]) {
    const schema = JSON.parse(readFileSync(join(CONTRACTS, file), "utf8")) as Record<
      string,
      unknown
    >;
    ajv.addSchema(schema, schema.$id as string);
  }
  return ajv;
}

function readFixture(): MemoryPack {
  return JSON.parse(readFileSync(FIXTURE, "utf8")) as MemoryPack;
}

function expectedHash(pack: MemoryPack): string {
  return snapshotHashFor(pack.scope, pack.role, pack.entries);
}

test("the dsh-memory synthetic producer pack satisfies Workbench v1.2 schema and semantics", () => {
  const ajv = makeAjv();
  const validate = ajv.getSchema(SCHEMA_ID);
  assert.ok(validate, "memorypack v1.2 schema is registered");
  const pack = readFixture();
  const ok = validate(pack);
  assert.equal(
    ok,
    true,
    ajv.errorsText(validate.errors, { separator: "\n" })
  );

  assert.equal(pack.contract_version, "1.2.0");
  assert.equal(pack.source.vault, "dsh-memory");
  assert.equal(pack.source.contract_version, "1.2.0");
  assert.equal(pack.read_only, true);
  assert.equal(pack.policy.authorized_before_retrieval, true);
  assert.ok(pack.entries.length > 0 && pack.entries.length <= 100);

  // The snapshot identity is recomputed with Workbench's canonical JSON and
  // deterministic code-point ordering, so this fails if either repo drifts.
  const recomputed = expectedHash(pack);
  assert.equal(pack.snapshot_hash, recomputed);
  assert.equal(pack.snapshot_id, snapshotIdFor(recomputed));

  for (const entry of pack.entries) {
    assert.equal(entry.review_state, "approved");
    assert.equal(entry.sha256, sha256OfJson({
      path: entry.path,
      revision: entry.revision,
      body: entry.body
    }));
    assert.equal(entry.path, entry.path.normalize("NFC"), "paths are NFC");
    assert.ok(!entry.path.includes("\\"), "paths use POSIX separators");
    assert.ok(!entry.path.startsWith("/"), "paths are relative");
    assert.ok(entry.path.split("/").every((segment) => segment !== "" && segment !== "." && segment !== ".."));
    assert.ok(entry.path.split("/").every((segment) => !segment.includes(":")));
  }

  // Entries are emitted in deterministic layer-then-code-point path order.
  for (let index = 1; index < pack.entries.length; index += 1) {
    const previous = pack.entries[index - 1] as MemoryPackEntry;
    const current = pack.entries[index] as MemoryPackEntry;
    const layerOrder =
      (LAYER_ORDER[previous.layer] as number) - (LAYER_ORDER[current.layer] as number);
    if (layerOrder === 0) {
      assert.ok(
        compareCodePoints(previous.path, current.path) < 0,
        `${previous.path} must sort before ${current.path}`
      );
    } else {
      assert.ok(layerOrder < 0, "entries must be layer ordered");
    }
  }

  assert.equal(
    pack.policy.cross_workspace,
    pack.entries.some(
      (entry) =>
        entry.visibility === "user-global" &&
        entry.workspace_id !== pack.scope.workspace_id
    ),
    "cross_workspace must be recomputable from entries"
  );
  assert.ok(
    pack.entries.some((entry) => entry.workspace_id === "global"),
    "the unscoped explicit user-global note uses the global sentinel"
  );
  assert.ok(
    !JSON.stringify(pack).includes("WS_B_FOREIGN_CANARY"),
    "foreign workspace canary must not appear in the Workbench-visible pack"
  );
});

test("Workbench rejects a dsh-memory pack whose content no longer matches its snapshot", () => {
  const pack = readFixture();
  const tampered = structuredClone(pack);
  const target = tampered.entries[0];
  assert.ok(target);
  target.body = `${target.body} tampered`;
  const recomputed = expectedHash(tampered);
  assert.notEqual(recomputed, tampered.snapshot_hash);

  const ajv = makeAjv();
  const validate = ajv.getSchema(SCHEMA_ID);
  assert.ok(validate);
  const wrongVersion = structuredClone(pack);
  (wrongVersion as unknown as Record<string, unknown>).contract_version = "1.3.0";
  assert.equal(validate(wrongVersion), false, "unsupported contract versions are rejected");

  // The previous contract version must not be silently accepted either.
  const previous = structuredClone(pack);
  (previous as unknown as Record<string, unknown>).contract_version = "1.1.0";
  (previous.source as Record<string, unknown>).contract_version = "1.1.0";
  assert.equal(validate(previous), false, "a v1.1.0 pack is rejected by the v1.2.0 schema");
});
