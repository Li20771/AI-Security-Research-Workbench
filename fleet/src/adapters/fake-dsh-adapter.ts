import { randomUUID } from "node:crypto";
import { deepFreeze } from "../canonical-json.ts";
import type { RoleId } from "../contract.ts";
import type {
  DshCancelResult,
  DshCloseResult,
  DshHealth,
  DshRunRequest,
  DshRuntimeAdapter,
  DshSessionHandle,
  DshSessionRequest,
  PromptBeforeInitializeEvent,
  WdBeforeInitializeEvent
} from "./dsh-adapter.ts";
import {
  DshAdapterError,
  DshCancelledError,
  PROMPT_HOOK_NAME,
  WD_HOOK_NAME
} from "./dsh-adapter.ts";

export type FakeDshMode = "success" | "start-failure" | "hang" | "malformed" | "crash";

export interface FakeResultContext {
  handle: DshSessionHandle;
  request: DshSessionRequest;
  input: unknown;
}

export type FakeResultFactory = (context: FakeResultContext) => unknown;

export interface FakeDshAdapterOptions {
  adapterId?: string;
  mode?: FakeDshMode;
  cancelCleaned?: boolean;
  closeClosed?: boolean;
  delayMs?: number;
  resultFactory?: FakeResultFactory;
}

interface FakeHookCall {
  hook: typeof PROMPT_HOOK_NAME | typeof WD_HOOK_NAME;
  ok: boolean;
  code: string | null;
}

interface FakeSessionState {
  handle: DshSessionHandle;
  request: DshSessionRequest;
  input: unknown;
  closed: boolean;
  cancelRequested: boolean;
  rejectRun: ((error: Error) => void) | null;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function defaultResult(role: RoleId): unknown {
  const payload: Record<string, unknown> = {
    summary: "Fake DSH adapter output; no real runtime, model, or target was contacted.",
    claims: [],
    citations: [],
    artifacts: [],
    memory_candidates: [],
    requested_actions: [],
    limitations: ["Fake adapter only; real DSH runtime is NOT_RUN."]
  };
  if (role === "challenger") {
    payload.findings = [];
  }
  if (role === "evidence_verifier") {
    payload.verdicts = [
      {
        claim_id: "clm_0001",
        verdict: "unresolved",
        evidence_refs: [],
        rationale: "No real evidence was available in the fake runtime."
      }
    ];
  }
  return payload;
}

export class FakeDshAdapter implements DshRuntimeAdapter {
  adapter_id: string;
  mode: FakeDshMode;
  cancelCleaned: boolean;
  closeClosed: boolean;
  delayMs: number;
  resultFactory: FakeResultFactory | null;

  #sessions = new Map<string, FakeSessionState>();
  #counter = 0;
  #openCalls = 0;
  #cancelCalls = 0;
  #closeCalls = 0;
  #maxConcurrent = 0;
  #hookCalls: FakeHookCall[] = [];

  constructor(options: FakeDshAdapterOptions = {}) {
    this.adapter_id = options.adapterId ?? "fake-dsh-adapter-v1";
    this.mode = options.mode ?? "success";
    this.cancelCleaned = options.cancelCleaned ?? true;
    this.closeClosed = options.closeClosed ?? true;
    this.delayMs = options.delayMs ?? 0;
    this.resultFactory = options.resultFactory ?? null;
  }

  async openSession(request: DshSessionRequest): Promise<DshSessionHandle> {
    this.#openCalls += 1;
    if (this.mode === "start-failure") {
      throw new DshAdapterError("adapter-start-failed", "fake start failure");
    }
    if (request.lifecycle_hooks === undefined) {
      throw new DshAdapterError("session-init-blocked", "lifecycle hooks are missing");
    }

    const promptEvent: PromptBeforeInitializeEvent = {
      kind: PROMPT_HOOK_NAME,
      run_id: request.run_id,
      role: request.role,
      preset_id: request.preset_id,
      preset_version: request.preset_version,
      prompt_template_id: "worker-task-v1"
    };
    const promptResult = await request.lifecycle_hooks.promptBeforeInitialize(promptEvent);
    this.#hookCalls.push({
      hook: PROMPT_HOOK_NAME,
      ok: promptResult.ok,
      code: promptResult.code ?? null
    });

    const wdEvent: WdBeforeInitializeEvent = {
      kind: WD_HOOK_NAME,
      run_id: request.run_id,
      workspace_id: request.workspace_id,
      workspace_root: request.workspace_root,
      working_directory: request.working_directory
    };
    const wdResult = await request.lifecycle_hooks.wdBeforeInitialize(wdEvent);
    this.#hookCalls.push({
      hook: WD_HOOK_NAME,
      ok: wdResult.ok,
      code: wdResult.code ?? null
    });

    if (!promptResult.ok || !wdResult.ok) {
      const codes = [promptResult.code, wdResult.code].filter(
        (code): code is string => typeof code === "string"
      );
      throw new DshAdapterError("session-init-blocked", codes.join(","));
    }

    this.#counter += 1;
    const sessionId = `dshsess_fake_${String(this.#counter).padStart(4, "0")}_${randomUUID()
      .replaceAll("-", "")
      .slice(0, 8)}`;
    const handle = deepFreeze<DshSessionHandle>({
      session_id: sessionId,
      run_id: request.run_id,
      role: request.role,
      workspace_id: request.workspace_id,
      opened_at: new Date().toISOString()
    });
    this.#sessions.set(sessionId, {
      handle,
      request,
      input: null,
      closed: false,
      cancelRequested: false,
      rejectRun: null
    });
    const active = this.activeSessionCount;
    if (active > this.#maxConcurrent) {
      this.#maxConcurrent = active;
    }
    return handle;
  }

  async runSession(handle: DshSessionHandle, run: DshRunRequest): Promise<unknown> {
    const state = this.#sessions.get(handle.session_id);
    if (state === undefined) {
      throw new DshAdapterError("session-not-found", "fake session is unknown");
    }
    if (state.closed) {
      throw new DshAdapterError("session-closed", "fake session is closed");
    }
    state.input = run.input;

    if (this.mode === "malformed") {
      return { summary: 123 };
    }
    if (this.mode === "crash") {
      throw new DshAdapterError("adapter-crashed", "fake worker crash");
    }
    if (this.mode === "hang") {
      return await new Promise<unknown>((_resolve, reject) => {
        if (state.cancelRequested) {
          reject(new DshCancelledError("cancelled-before-hang"));
          return;
        }
        state.rejectRun = reject;
      });
    }
    if (this.mode === "start-failure") {
      throw new DshAdapterError("adapter-start-failed", "fake start failure");
    }

    await delay(this.delayMs);
    if (state.cancelRequested || state.closed) {
      throw new DshCancelledError("session-cancelled");
    }
    if (this.resultFactory !== null) {
      return this.resultFactory({ handle, request: state.request, input: state.input });
    }
    return defaultResult(state.request.role);
  }

  async cancelSession(handle: DshSessionHandle, reason: string): Promise<DshCancelResult> {
    this.#cancelCalls += 1;
    const state = this.#sessions.get(handle.session_id);
    if (state === undefined) {
      return { cleaned: false, detail: "session-not-found" };
    }
    state.cancelRequested = true;
    const reject = state.rejectRun;
    state.rejectRun = null;
    if (reject !== null) {
      reject(new DshCancelledError(reason));
    }
    if (this.cancelCleaned) {
      return { cleaned: true };
    }
    return { cleaned: false, detail: "fake cleanup failure" };
  }

  async closeSession(handle: DshSessionHandle): Promise<DshCloseResult> {
    this.#closeCalls += 1;
    const state = this.#sessions.get(handle.session_id);
    if (state === undefined) {
      return { closed: false, detail: "session-not-found" };
    }
    state.closed = true;
    if (this.closeClosed) {
      return { closed: true };
    }
    return { closed: false, detail: "fake close failure" };
  }

  async health(handle?: DshSessionHandle): Promise<DshHealth> {
    if (handle === undefined) {
      return { state: "ready" };
    }
    const state = this.#sessions.get(handle.session_id);
    if (state === undefined) {
      return { state: "unknown" };
    }
    if (state.closed) {
      return { state: "closed", session_id: handle.session_id };
    }
    return { state: "ready", session_id: handle.session_id };
  }

  get openCalls(): number {
    return this.#openCalls;
  }

  get cancelCalls(): number {
    return this.#cancelCalls;
  }

  get closeCalls(): number {
    return this.#closeCalls;
  }

  get activeSessionCount(): number {
    let count = 0;
    for (const state of this.#sessions.values()) {
      if (!state.closed) {
        count += 1;
      }
    }
    return count;
  }

  get maxConcurrent(): number {
    return this.#maxConcurrent;
  }

  get hookCalls(): readonly FakeHookCall[] {
    return this.#hookCalls.map((call) => ({ ...call }));
  }

  get sessionIds(): readonly string[] {
    return [...this.#sessions.keys()];
  }
}
