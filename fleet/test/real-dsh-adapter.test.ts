import { test, after } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type {
  DshSdkFactory,
  DshSdkHarness,
  DshSdkHarnessOptions,
  DshSdkRunOptions,
  DshSdkRunResult,
  DshSdkSession
} from "../src/adapters/dsh-sdk-port.ts";
import {
  RealDshAdapter,
  type RealDshAdapterConfig
} from "../src/adapters/real-dsh-adapter.ts";
import type { DshRunRequest, DshSessionRequest } from "../src/adapters/dsh-adapter.ts";

const ROOT = mkdtempSync(join(tmpdir(), "dsh-real-adapter-"));
after(() => {
  rmSync(ROOT, { recursive: true, force: true });
});

class FakeSession implements DshSdkSession {
  #harness: FakeHarness;

  constructor(harness: FakeHarness) {
    this.#harness = harness;
  }

  async run(input: string, options?: DshSdkRunOptions): Promise<DshSdkRunResult> {
    this.#harness.prompts.push(input);
    return {
      sessionId: options?.sessionId ?? this.#harness.sessionId,
      finalResponse: this.#harness.finalResponse
    };
  }
}

class FakeHarness implements DshSdkHarness {
  options: DshSdkHarnessOptions | null = null;
  sessionId = "dshsess_fake";
  finalResponse = JSON.stringify({
    summary: "fake SDK worker result",
    claims: [],
    citations: [],
    artifacts: [],
    memory_candidates: [],
    requested_actions: [],
    limitations: []
  });
  prompts: string[] = [];
  started = false;
  closed = false;

  async start(): Promise<void> {
    this.started = true;
  }

  session(id?: string): DshSdkSession {
    if (id !== undefined) this.sessionId = id;
    return new FakeSession(this);
  }

  async close(): Promise<void> {
    this.closed = true;
  }
}

class FakeFactory implements DshSdkFactory {
  created: FakeHarness[] = [];

  create(options: DshSdkHarnessOptions): FakeHarness {
    const harness = new FakeHarness();
    harness.options = options;
    this.created.push(harness);
    return harness;
  }
}

function request(overrides: Partial<DshSessionRequest> = {}): DshSessionRequest {
  return {
    run_id: "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    role: "researcher",
    preset_id: "preset_researcher",
    preset_version: "1.0.0",
    dsh_profile: "dsh-researcher-v1",
    plugin_manifest: [],
    tool_profile: "researcher_ro_v1",
    mcp_server: null,
    workspace_id: "ws_a",
    episode_id: "ep_1",
    workspace_root: ROOT,
    working_directory: ROOT,
    memory_pack: {
      snapshot_id: `mp_${"a".repeat(32)}`,
      snapshot_hash: "b".repeat(64),
      workspace_id: "ws_a",
      episode_id: "ep_1"
    },
    env_allowlist: ["LANG"],
    lifecycle_hooks: {
      promptBeforeInitialize: async () => ({ ok: true }),
      wdBeforeInitialize: async () => ({ ok: true })
    },
    ...overrides
  };
}

function runRequest(input: Record<string, unknown>): DshRunRequest {
  return {
    input_sha256: "c".repeat(64),
    input,
    deadline_ms: 30000,
    budget: { max_tokens: 256, max_cost_usd: 0 }
  };
}

function config(
  factory: DshSdkFactory,
  overrides: Partial<RealDshAdapterConfig> = {}
): RealDshAdapterConfig {
  return {
    factory,
    provider: "unimodel",
    model: "deepseek-v4-flash",
    dshBin: "C:\\dsh\\dsh.cmd",
    profile: "sdk",
    dshHomeRoot: join(ROOT, "homes"),
    envValues: { LANG: "C", UNIMODEL_API_KEY: "synthetic-key" },
    envNames: ["LANG", "UNIMODEL_API_KEY"],
    requiredEnvNames: ["UNIMODEL_API_KEY"],
    workerInstruction: "Return only the worker-result JSON object.",
    contextBuilder: () => "MEMORY_CONTEXT_SENTINEL",
    ...overrides
  };
}

test("real adapter starts an isolated harness with trusted route and explicit env", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(config(factory));
  const handle = await adapter.openSession(request());
  assert.match(handle.session_id, /^dshsess_[A-Za-z0-9_-]{8,120}$/);
  assert.equal(factory.created.length, 1);
  const harness = factory.created[0]!;
  assert.deepEqual(harness.options?.env, {
    LANG: "C",
    UNIMODEL_API_KEY: "synthetic-key"
  });
  assert.equal(harness.options?.provider, "unimodel");
  assert.equal(harness.options?.model, "deepseek-v4-flash");
  assert.equal(harness.options?.profile, "sdk");
  assert.equal(harness.options?.cwd, ROOT);
  assert.ok(harness.options?.dshHome.startsWith(join(ROOT, "homes")));
  assert.equal(existsSync(harness.options?.dshHome as string), true);
  assert.equal((await adapter.health(handle)).state, "ready");
  await adapter.closeSession(handle);
});

test("real adapter parses strict JSON and rejects non-JSON to the Fleet validator", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(config(factory));
  const handle = await adapter.openSession(request());
  const parsed = await adapter.runSession(handle, runRequest({ brief: "hello" }));
  assert.ok(parsed && typeof parsed === "object");
  assert.equal((parsed as { summary: string }).summary, "fake SDK worker result");
  const prompt = factory.created[0]!.prompts[0] as string;
  assert.match(prompt, /MEMORY_CONTEXT_SENTINEL/);
  assert.match(prompt, /Worker role: researcher/);
  assert.match(prompt, /untrusted JSON data/);
  assert.match(prompt, /"brief":"hello"/);

  factory.created[0]!.finalResponse = "not JSON";
  assert.equal(await adapter.runSession(handle, runRequest({ brief: "again" })), "not JSON");
  await adapter.closeSession(handle);
});

test("real adapter renders verified MemoryPack entries into the worker prompt", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(config(factory, { contextBuilder: undefined }));
  const handle = await adapter.openSession(
    request({
      memory_pack_entries: [
        {
          entry_id: "mem_a_0001",
          path: "workspaces/ws_a/memory/note.md",
          layer: "L4",
          type: "memory",
          title: "note",
          visibility: "workspace-shared",
          workspace_id: "ws_a",
          episode_id: null,
          authority: "curator",
          review_state: "approved",
          revision: "r1",
          body: "PACK_BODY_SENTINEL",
          sources: [],
          sha256: "c".repeat(64)
        }
      ]
    })
  );
  await adapter.runSession(handle, runRequest({ brief: "read pack" }));
  const prompt = factory.created[0]!.prompts[0] as string;
  assert.match(prompt, /PACK_BODY_SENTINEL/);
  assert.match(prompt, /workspaces\/ws_a\/memory\/note\.md/);
  await adapter.closeSession(handle);
});

test("real adapter writes a per-run MCP binding and patch, and fails closed when unconfigured", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(
    config(factory, {
      mcpServers: {
        securitylab_ro: {
          serverName: "securitylab_ro",
          command: "python",
          argsTemplate: ["-m", "securitylab_mcp.server", "--binding", "{binding}"],
          cwd: ROOT,
          failOnStartupError: true,
          toolCallTimeoutMs: 1000
        }
      }
    })
  );
  const handle = await adapter.openSession(request({ mcp_server: "securitylab_ro" }));
  const home = factory.created[0]!.options?.dshHome as string;
  const binding = JSON.parse(readFileSync(join(home, "mcp-binding.json"), "utf8")) as {
    run_id: string;
    role: string;
    workspace_id: string;
    episode_id: string;
    tool_profile: string;
  };
  assert.equal(binding.run_id, "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
  assert.equal(binding.role, "researcher");
  assert.equal(binding.workspace_id, "ws_a");
  assert.equal(binding.episode_id, "ep_1");
  assert.equal(binding.tool_profile, "researcher_ro_v1");
  const patch = readFileSync(join(home, "mcp.patch.yml"), "utf8");
  assert.match(patch, /securitylab-mcp/);
  assert.match(patch, /@deepseek-ai\/dsh-mcp-client/);
  assert.match(patch, /mcp-binding\.json/);
  await adapter.closeSession(handle);

  const unconfigured = new RealDshAdapter(config(new FakeFactory()));
  await assert.rejects(
    () => unconfigured.openSession(request({ mcp_server: "securitylab_ro" })),
    /mcp server is not configured/
  );
});

test("real adapter cancel closes the runtime and removes the per-run home", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(config(factory));
  const handle = await adapter.openSession(request());
  const home = factory.created[0]!.options?.dshHome as string;
  assert.equal(existsSync(home), true);
  const cleanup = await adapter.cancelSession(handle, "operator-cancel");
  assert.equal(cleanup.cleaned, true);
  assert.equal(factory.created[0]!.closed, true);
  assert.equal(existsSync(home), false);
  assert.equal((await adapter.health(handle)).state, "closed");
  await assert.rejects(() => adapter.runSession(handle, runRequest({})), /not active/);
});

test("real adapter honors the trusted profile map and rejects root escape", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(
    config(factory, {
      profileMap: {
        "dsh-challenger-v1": { profile: "sdk-challenger", patches: ["challenger.patch.yml"] }
      }
    })
  );
  const handle = await adapter.openSession(request({ dsh_profile: "dsh-challenger-v1", role: "challenger" }));
  assert.equal(factory.created[0]!.options?.profile, "sdk-challenger");
  assert.deepEqual(factory.created[0]!.options?.patches, ["challenger.patch.yml"]);
  await adapter.closeSession(handle);

  const escaping = request({ working_directory: join(ROOT, "..") });
  await assert.rejects(() => adapter.openSession(escaping), /escapes the workspace root/);
});

test("real adapter runs both lifecycle hooks and blocks on hook failure", async () => {
  const factory = new FakeFactory();
  const adapter = new RealDshAdapter(config(factory));
  const calls: string[] = [];
  const handle = await adapter.openSession(
    request({
      lifecycle_hooks: {
        promptBeforeInitialize: async () => {
          calls.push("prompt");
          return { ok: true };
        },
        wdBeforeInitialize: async () => {
          calls.push("wd");
          return { ok: true };
        }
      }
    })
  );
  assert.deepEqual(calls, ["prompt", "wd"]);
  await adapter.closeSession(handle);

  const blockedFactory = new FakeFactory();
  const blockedAdapter = new RealDshAdapter(config(blockedFactory));
  await assert.rejects(
    () =>
      blockedAdapter.openSession(
        request({
          lifecycle_hooks: {
            promptBeforeInitialize: async () => ({ ok: true }),
            wdBeforeInitialize: async () => ({ ok: false, code: "wd-out-of-root" })
          }
        })
      ),
    /session-init-blocked: wd-out-of-root/
  );
  assert.equal(blockedFactory.created.length, 0);
});

test("real adapter fails closed when a required trusted env value is missing", () => {
  const factory = new FakeFactory();
  assert.throws(
    () =>
      new RealDshAdapter(
        config(factory, {
          envValues: { LANG: "C" },
          envNames: ["LANG"],
          requiredEnvNames: ["UNIMODEL_API_KEY"]
        })
      ),
    /env value is missing/
  );
  assert.equal(factory.created.length, 0);
});
