import type { Budget, PluginRef, RoleId } from "../contract.ts";
import type { MemoryPackRef } from "../binding.ts";

export const PROMPT_HOOK_NAME = "session.promptBeforeInitialize" as const;
export const WD_HOOK_NAME = "session.wd.beforeInitialize" as const;

export interface PromptBeforeInitializeEvent {
  kind: typeof PROMPT_HOOK_NAME;
  run_id: string;
  role: RoleId;
  preset_id: string;
  preset_version: string;
  prompt_template_id: string;
}

export interface WdBeforeInitializeEvent {
  kind: typeof WD_HOOK_NAME;
  run_id: string;
  workspace_id: string;
  workspace_root: string;
  working_directory: string;
}

export interface HookResult {
  ok: boolean;
  code?: string;
  detail?: string;
}

export interface DshLifecycleHooks {
  promptBeforeInitialize(event: PromptBeforeInitializeEvent): Promise<HookResult>;
  wdBeforeInitialize(event: WdBeforeInitializeEvent): Promise<HookResult>;
}

export interface DshSessionRequest {
  run_id: string;
  role: RoleId;
  preset_id: string;
  preset_version: string;
  dsh_profile: string;
  plugin_manifest: readonly PluginRef[];
  tool_profile: string | null;
  mcp_server: string | null;
  workspace_id: string;
  episode_id: string | null;
  workspace_root: string;
  working_directory: string;
  memory_pack: MemoryPackRef | null;
  env_allowlist: readonly string[];
  lifecycle_hooks: DshLifecycleHooks;
}

export interface DshSessionHandle {
  session_id: string;
  run_id: string;
  role: RoleId;
  workspace_id: string;
  opened_at: string;
}

export interface DshRunRequest {
  input_sha256: string;
  input: unknown;
  deadline_ms: number;
  budget: Budget;
}

export interface DshCancelResult {
  cleaned: boolean;
  detail?: string;
}

export interface DshCloseResult {
  closed: boolean;
  detail?: string;
}

export interface DshHealth {
  state: "ready" | "closed" | "unknown";
  session_id?: string;
}

export interface DshRuntimeAdapter {
  readonly adapter_id: string;
  openSession(request: DshSessionRequest): Promise<DshSessionHandle>;
  runSession(handle: DshSessionHandle, run: DshRunRequest): Promise<unknown>;
  cancelSession(handle: DshSessionHandle, reason: string): Promise<DshCancelResult>;
  closeSession(handle: DshSessionHandle): Promise<DshCloseResult>;
  health(handle?: DshSessionHandle): Promise<DshHealth>;
}

export class DshAdapterError extends Error {
  code: string;
  detail: string | undefined;

  constructor(code: string, detail?: string) {
    super(detail === undefined ? code : `${code}: ${detail}`);
    this.name = "DshAdapterError";
    this.code = code;
    this.detail = detail;
  }
}

export class DshCancelledError extends Error {
  constructor(reason: string) {
    super(`cancelled: ${reason}`);
    this.name = "DshCancelledError";
  }
}
