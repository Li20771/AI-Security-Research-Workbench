import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const SRC = join(process.cwd(), "src");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(path));
    } else if (entry.isFile() && entry.name.endsWith(".ts")) {
      out.push(path);
    }
  }
  return out;
}

const files = walk(SRC);

test("Fleet source never reads ambient environment, spawns processes, or opens network clients", () => {
  const forbidden = [
    "process.env",
    "process.exit",
    "child_process",
    "node:net",
    "node:http",
    "node:https",
    "WebSocket",
    "fetch(",
    "eval(",
    "new Function",
    "require("
  ];
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    for (const token of forbidden) {
      assert.equal(
        text.includes(token),
        false,
        `${relative(process.cwd(), file)} contains forbidden token: ${token}`
      );
    }
  }
});

test("Fleet source does not import legacy agents/providers/routing/composition or Evidence writers", () => {
  const legacy = [
    "../agents",
    "../providers",
    "../routing",
    "../composition",
    "plugins/evidence",
    "evidence/",
    "EvidenceRecord",
    "admit(",
    "evidence_store"
  ];
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    for (const token of legacy) {
      assert.equal(
        text.includes(token),
        false,
        `${relative(process.cwd(), file)} references legacy/Evidence token: ${token}`
      );
    }
  }
});

test("filesystem writes are confined to the append-only ledger implementation", () => {
  const writeTokens = ["appendFileSync", "writeFileSync", "createWriteStream", "rmSync", "unlinkSync"];
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    const rel = relative(SRC, file);
    for (const token of writeTokens) {
      if (text.includes(token)) {
        assert.equal(rel, "ledger.ts", `${rel} performs filesystem write token: ${token}`);
      }
    }
  }
});

test("the two DSH lifecycle hooks remain distinct names in source", () => {
  const adapter = readFileSync(join(SRC, "adapters", "dsh-adapter.ts"), "utf8");
  const hooks = readFileSync(join(SRC, "adapters", "lifecycle-hooks.ts"), "utf8");
  assert.ok(adapter.includes('"session.promptBeforeInitialize"'));
  assert.ok(adapter.includes('"session.wd.beforeInitialize"'));
  assert.ok(hooks.includes("promptBeforeInitialize"));
  assert.ok(hooks.includes("wdBeforeInitialize"));
  assert.notEqual(
    adapter.indexOf('"session.promptBeforeInitialize"'),
    adapter.indexOf('"session.wd.beforeInitialize"')
  );
});
