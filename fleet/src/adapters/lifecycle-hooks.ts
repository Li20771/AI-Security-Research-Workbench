import { isPlainObject } from "../canonical-json.ts";
import { checkContainment } from "../path-safety.ts";
import type {
  DshLifecycleHooks,
  HookResult,
  PromptBeforeInitializeEvent,
  WdBeforeInitializeEvent
} from "./dsh-adapter.ts";
import { PROMPT_HOOK_NAME, WD_HOOK_NAME } from "./dsh-adapter.ts";

function fail(code: string, detail?: string): HookResult {
  const result: HookResult = { ok: false, code };
  if (detail !== undefined) {
    result.detail = detail;
  }
  return result;
}

function hasKey(value: Record<string, unknown>, key: string): boolean {
  return Object.hasOwn(value, key);
}

export class WorkspaceLifecycleHooks implements DshLifecycleHooks {
  #roots: Readonly<Record<string, string>>;

  constructor(roots: Readonly<Record<string, string>>) {
    this.#roots = { ...roots };
  }

  async promptBeforeInitialize(event: PromptBeforeInitializeEvent): Promise<HookResult> {
    if (!isPlainObject(event)) {
      return fail("prompt-event-invalid");
    }
    const record = event as unknown as Record<string, unknown>;
    if (record.kind !== PROMPT_HOOK_NAME) {
      return fail("prompt-event-kind");
    }
    if (hasKey(record, "path") || hasKey(record, "working_directory") || hasKey(record, "workspace_root")) {
      return fail("prompt-hook-misused-for-path");
    }
    if (
      typeof record.run_id !== "string" ||
      typeof record.preset_id !== "string" ||
      typeof record.preset_version !== "string" ||
      typeof record.prompt_template_id !== "string"
    ) {
      return fail("prompt-event-invalid");
    }
    return { ok: true };
  }

  async wdBeforeInitialize(event: WdBeforeInitializeEvent): Promise<HookResult> {
    if (!isPlainObject(event)) {
      return fail("wd-event-invalid");
    }
    const record = event as unknown as Record<string, unknown>;
    if (record.kind !== WD_HOOK_NAME) {
      return fail("wd-event-kind");
    }
    if (
      hasKey(record, "prompt") ||
      hasKey(record, "prompt_template_id") ||
      hasKey(record, "messages")
    ) {
      return fail("wd-hook-misused-for-prompt");
    }
    const workspaceId = record.workspace_id;
    const workspaceRoot = record.workspace_root;
    const workingDirectory = record.working_directory;
    if (
      typeof workspaceId !== "string" ||
      typeof workspaceRoot !== "string" ||
      typeof workingDirectory !== "string"
    ) {
      return fail("wd-event-invalid");
    }
    const expectedRoot = this.#roots[workspaceId];
    if (expectedRoot !== undefined && expectedRoot !== workspaceRoot) {
      return fail("workspace-root-mismatch");
    }
    const containment = checkContainment(workspaceRoot, workingDirectory);
    if (!containment.contained) {
      return fail("wd-out-of-root", containment.reason ?? "outside-root");
    }
    return { ok: true };
  }
}
