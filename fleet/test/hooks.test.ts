import { test } from "node:test";
import assert from "node:assert/strict";
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
import { getRolePreset } from "../src/registries/roles.ts";

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

function wdEvent(workingDirectory: string): WdBeforeInitializeEvent {
  return {
    kind: WD_HOOK_NAME,
    run_id: "run_00000000000000000000000000000001",
    workspace_id: "ws_a",
    workspace_root: "D:\\lab\\ws_a",
    working_directory: workingDirectory
  };
}

function sessionRequest(
  hooks: WorkspaceLifecycleHooks,
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
    workspace_root: "D:\\lab\\ws_a",
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
  const hooks = new WorkspaceLifecycleHooks({ ws_a: "D:\\lab\\ws_a" });
  assert.deepEqual(await hooks.promptBeforeInitialize(promptEvent()), { ok: true });
  const misused = {
    ...promptEvent(),
    working_directory: "D:\\lab\\ws_a"
  } as unknown as PromptBeforeInitializeEvent;
  const result = await hooks.promptBeforeInitialize(misused);
  assert.equal(result.ok, false);
  assert.equal(result.code, "prompt-hook-misused-for-path");
});

test("wd hook performs containment and rejects path escapes and prompt payloads", async () => {
  const hooks = new WorkspaceLifecycleHooks({ ws_a: "D:\\lab\\ws_a" });
  assert.deepEqual(await hooks.wdBeforeInitialize(wdEvent("D:\\lab\\ws_a\\sub")), { ok: true });
  const escape = await hooks.wdBeforeInitialize(wdEvent("D:\\lab\\ws_a\\..\\Windows"));
  assert.equal(escape.ok, false);
  assert.equal(escape.code, "wd-out-of-root");
  const misused = {
    ...wdEvent("D:\\lab\\ws_a"),
    prompt: "do not treat this as a prompt hook"
  } as unknown as WdBeforeInitializeEvent;
  const promptInWd = await hooks.wdBeforeInitialize(misused);
  assert.equal(promptInWd.ok, false);
  assert.equal(promptInWd.code, "wd-hook-misused-for-prompt");
});

test("the fake adapter calls both hooks separately, in order", async () => {
  const hooks = new WorkspaceLifecycleHooks({ ws_a: "D:\\lab\\ws_a" });
  const adapter = new FakeDshAdapter({ mode: "success" });
  const handle = await adapter.openSession(sessionRequest(hooks, "D:\\lab\\ws_a"));
  assert.ok(handle.session_id.startsWith("dshsess_fake_"));
  const calls = adapter.hookCalls;
  assert.equal(calls.length, 2);
  assert.equal(calls[0]?.hook, PROMPT_HOOK_NAME);
  assert.equal(calls[1]?.hook, WD_HOOK_NAME);
  assert.equal(calls[0]?.ok, true);
  assert.equal(calls[1]?.ok, true);
});

test("a wd hook rejection blocks session initialization without merging hook semantics", async () => {
  const hooks = new WorkspaceLifecycleHooks({ ws_a: "D:\\lab\\ws_a" });
  const adapter = new FakeDshAdapter({ mode: "success" });
  await assert.rejects(
    adapter.openSession(sessionRequest(hooks, "D:\\lab\\ws_a\\..\\Windows")),
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
