import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  DshAdapterError,
  PROMPT_HOOK_NAME,
  WD_HOOK_NAME
} from "../src/adapters/dsh-adapter.ts";
import type {
  DshSessionRequest,
  PromptBeforeInitializeEvent,
  WdBeforeInitializeEvent
} from "../src/adapters/dsh-adapter.ts";
import { WorkspaceLifecycleHooks } from "../src/adapters/lifecycle-hooks.ts";
import { FakeDshAdapter } from "../src/adapters/fake-dsh-adapter.ts";
import { FleetController } from "../src/fleet-controller.ts";
import { getRolePreset } from "../src/registries/roles.ts";
import { makeHarness } from "./helpers.ts";

interface RootFixture {
  base: string;
  root: string;
  sub: string;
  outside: string;
}

function rootFixture(): RootFixture {
  const base = mkdtempSync(join(tmpdir(), "dsh-hooks-"));
  const root = join(base, "ws_a");
  const sub = join(root, "sub");
  const outside = join(base, "outside");
  mkdirSync(sub, { recursive: true });
  mkdirSync(outside, { recursive: true });
  return { base, root, sub, outside };
}

function promptEvent(): PromptBeforeInitializeEvent {
  return {
    kind: PROMPT_HOOK_NAME,
    run_id: "run_00000000000000000000000000000001",
    role: "researcher",
    preset_id: "preset_researcher",
    preset_version: "1.0.0",
    prompt_template_id: "worker-task-v1"
  };
}

function wdEvent(
  root: string,
  workingDirectory: string,
  workspaceId = "ws_a"
): WdBeforeInitializeEvent {
  return {
    kind: WD_HOOK_NAME,
    run_id: "run_00000000000000000000000000000001",
    workspace_id: workspaceId,
    workspace_root: root,
    working_directory: workingDirectory
  };
}

function sessionRequest(
  hooks: WorkspaceLifecycleHooks,
  roots: Readonly<Record<string, string>>,
  workingDirectory: string
): DshSessionRequest {
  const preset = getRolePreset("researcher");
  assert.ok(preset);
  return {
    run_id: "run_00000000000000000000000000000001",
    role: "researcher",
    preset_id: preset.preset_id,
    preset_version: preset.preset_version,
    dsh_profile: preset.dsh_profile,
    plugin_manifest: preset.plugin_manifest,
    tool_profile: preset.tool_profile,
    mcp_server: preset.mcp_server,
    workspace_id: "ws_a",
    episode_id: "ep_1",
    workspace_root: roots.ws_a as string,
    working_directory: workingDirectory,
    memory_pack: null,
    env_allowlist: preset.env_allowlist,
    lifecycle_hooks: hooks
  };
}

test("the two DSH lifecycle hooks are named exactly as the handoff requires", () => {
  assert.equal(PROMPT_HOOK_NAME, "session.promptBeforeInitialize");
  assert.equal(WD_HOOK_NAME, "session.wd.beforeInitialize");
  assert.notEqual(PROMPT_HOOK_NAME, WD_HOOK_NAME);
});

test("prompt hook does not perform path checks and rejects path payloads", async () => {
  const hooks = new WorkspaceLifecycleHooks({ ws_a: "/trusted/ws_a" });
  assert.deepEqual(await hooks.promptBeforeInitialize(promptEvent()), { ok: true });
  const misused = {
    ...promptEvent(),
    working_directory: "/trusted/ws_a"
  } as unknown as PromptBeforeInitializeEvent;
  const result = await hooks.promptBeforeInitialize(misused);
  assert.equal(result.ok, false);
  assert.equal(result.code, "prompt-hook-misused-for-path");
});

test("wd hook requires a root from the trusted registry and rejects path escapes", async (t) => {
  const fixture = rootFixture();
  t.after(() => rmSync(fixture.base, { recursive: true, force: true }));
  const hooks = new WorkspaceLifecycleHooks({ ws_a: fixture.root });

  assert.deepEqual(await hooks.wdBeforeInitialize(wdEvent(fixture.root, fixture.sub)), {
    ok: true
  });

  const unknown = await hooks.wdBeforeInitialize(wdEvent(fixture.root, fixture.root, "ws_other"));
  assert.equal(unknown.ok, false);
  assert.equal(unknown.code, "workspace-root-unknown");

  const mismatch = await hooks.wdBeforeInitialize(
    wdEvent(join(fixture.base, "lookalike"), fixture.root)
  );
  assert.equal(mismatch.ok, false);
  assert.equal(mismatch.code, "workspace-root-mismatch");

  const relativeRoot = await hooks.wdBeforeInitialize(
    wdEvent("relative/ws_a", fixture.root)
  );
  assert.equal(relativeRoot.ok, false);
  assert.equal(relativeRoot.code, "workspace-root-invalid");

  const escape = await hooks.wdBeforeInitialize(
    wdEvent(fixture.root, join(fixture.root, "..", "outside"))
  );
  assert.equal(escape.ok, false);
  assert.equal(escape.code, "wd-out-of-root");

  const missing = await hooks.wdBeforeInitialize(
    wdEvent(fixture.root, join(fixture.root, "missing"))
  );
  assert.equal(missing.ok, false);
  assert.equal(missing.code, "wd-root-unavailable");

  const misused = {
    ...wdEvent(fixture.root, fixture.root),
    prompt: "do not treat this as a prompt hook"
  } as unknown as WdBeforeInitializeEvent;
  const promptInWd = await hooks.wdBeforeInitialize(misused);
  assert.equal(promptInWd.ok, false);
  assert.equal(promptInWd.code, "wd-hook-misused-for-prompt");
});

test("wd hook rejects symlink/junction escapes after canonicalization", async (t) => {
  const fixture = rootFixture();
  t.after(() => rmSync(fixture.base, { recursive: true, force: true }));
  const link = join(fixture.root, "link-out");
  try {
    symlinkSync(fixture.outside, link, process.platform === "win32" ? "junction" : "dir");
  } catch {
    t.skip("symlink/junction creation is not permitted in this environment");
    return;
  }
  const hooks = new WorkspaceLifecycleHooks({ ws_a: fixture.root });
  const escaped = await hooks.wdBeforeInitialize(wdEvent(fixture.root, link));
  assert.equal(escaped.ok, false);
  assert.equal(escaped.code, "wd-symlink-escape");

  const insideLink = join(fixture.root, "link-in");
  symlinkSync(fixture.sub, insideLink, process.platform === "win32" ? "junction" : "dir");
  const inside = await hooks.wdBeforeInitialize(wdEvent(fixture.root, insideLink));
  assert.deepEqual(inside, { ok: true });
});

test("wd hook accepts the same configured root with platform case differences", async (t) => {
  if (process.platform !== "win32") {
    t.skip("case-insensitive root comparison is a Windows rule");
    return;
  }
  const fixture = rootFixture();
  t.after(() => rmSync(fixture.base, { recursive: true, force: true }));
  const hooks = new WorkspaceLifecycleHooks({ ws_a: fixture.root });
  const result = await hooks.wdBeforeInitialize(
    wdEvent(fixture.root.toLowerCase(), fixture.sub.toLowerCase())
  );
  assert.deepEqual(result, { ok: true });
});

test("the fake adapter calls both hooks separately, in order", async (t) => {
  const fixture = rootFixture();
  t.after(() => rmSync(fixture.base, { recursive: true, force: true }));
  const roots = { ws_a: fixture.root };
  const hooks = new WorkspaceLifecycleHooks(roots);
  const adapter = new FakeDshAdapter({ mode: "success" });
  const handle = await adapter.openSession(sessionRequest(hooks, roots, fixture.root));
  assert.ok(handle.session_id.startsWith("dshsess_fake_"));
  const calls = adapter.hookCalls;
  assert.equal(calls.length, 2);
  assert.equal(calls[0]?.hook, PROMPT_HOOK_NAME);
  assert.equal(calls[1]?.hook, WD_HOOK_NAME);
  assert.equal(calls[0]?.ok, true);
  assert.equal(calls[1]?.ok, true);
});

test("a wd hook rejection blocks session initialization without merging hook semantics", async (t) => {
  const fixture = rootFixture();
  t.after(() => rmSync(fixture.base, { recursive: true, force: true }));
  const roots = { ws_a: fixture.root };
  const hooks = new WorkspaceLifecycleHooks(roots);
  const adapter = new FakeDshAdapter({ mode: "success" });
  await assert.rejects(
    adapter.openSession(
      sessionRequest(hooks, roots, join(fixture.root, "..", "outside"))
    ),
    (error: unknown) =>
      error instanceof DshAdapterError && error.code === "session-init-blocked"
  );
  const calls = adapter.hookCalls;
  assert.equal(calls.length, 2);
  assert.equal(calls[0]?.hook, PROMPT_HOOK_NAME);
  assert.equal(calls[0]?.ok, true);
  assert.equal(calls[1]?.hook, WD_HOOK_NAME);
  assert.equal(calls[1]?.ok, false);
  assert.equal(calls[1]?.code, "wd-out-of-root");
  assert.equal(adapter.openCalls, 1);
  assert.equal(adapter.activeSessionCount, 0);
});

test("a worker run fails closed when the workspace has no trusted root", async () => {
  const h = makeHarness();
  const controller = new FleetController({
    bindingIssuer: h.issuer,
    ledger: h.ledger,
    adapter: h.adapter,
    resultStore: h.resultStore,
    approvalVerifier: h.approval,
    clock: h.clock,
    idGenerator: h.ids
  });
  const binding = await h.issueBinding("researcher");
  const response = controller.submit(
    {
      contract_version: "1.0.0",
      workflow_id: "research",
      task_id: "analysis_a",
      input: { brief: "synthetic" }
    },
    binding
  );
  assert.equal(response.ok, true);
  const runId = response.data?.run_id;
  assert.ok(typeof runId === "string");
  const run = await controller.waitForRun(runId, 3000);
  assert.equal(run.status, "failed");
  assert.equal(run.reason_code, "session-init-blocked");
  assert.equal(h.adapter.openCalls, 0);
  assert.equal(h.ledger.verify().ok, true);
});
