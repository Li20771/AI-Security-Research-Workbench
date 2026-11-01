import { realpath } from "node:fs/promises";
import path from "node:path";
import { isPlainObject } from "../canonical-json.ts";
import { checkContainment, detectPathStyle } from "../path-safety.ts";
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

function normalizeRoot(value: string): string | null {
  const style = detectPathStyle(value);
  const pathModule = style === "win32" ? path.win32 : path.posix;
  if (!pathModule.isAbsolute(value)) {
    return null;
  }
  const resolved = pathModule.resolve(value);
  return style === "win32" ? resolved.toLowerCase() : resolved;
}

export type Canonicalizer = (value: string) => Promise<string>;

const defaultCanonicalizer: Canonicalizer = (value) => realpath(value);

/**
 * Trusted workspace-root registry used by the DSH working-directory hook.
 *
 * `roots` must come from the trusted host/workspace registry, never from a
 * request or model output. An unknown workspace, a missing root entry, a root
 * mismatch, a lexically escaping directory, a non-existent root/directory or a
 * symlink/junction escaping the canonical root all fail closed.
 */
export class WorkspaceLifecycleHooks implements DshLifecycleHooks {
  #roots: Readonly<Record<string, string>>;
  #canonicalize: Canonicalizer;

  constructor(
    roots: Readonly<Record<string, string>>,
    canonicalize: Canonicalizer = defaultCanonicalizer
  ) {
    this.#roots = { ...roots };
    this.#canonicalize = canonicalize;
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
    if (!Object.hasOwn(this.#roots, workspaceId)) {
      return fail("workspace-root-unknown");
    }
    const expectedRoot = this.#roots[workspaceId];
    if (typeof expectedRoot !== "string" || expectedRoot.trim() === "") {
      return fail("workspace-root-unknown");
    }
    const normalizedExpected = normalizeRoot(expectedRoot);
    const normalizedEvent = normalizeRoot(workspaceRoot);
    if (normalizedExpected === null || normalizedEvent === null) {
      return fail("workspace-root-invalid");
    }
    if (normalizedExpected !== normalizedEvent) {
      return fail("workspace-root-mismatch");
    }
    const lexical = checkContainment(expectedRoot, workingDirectory);
    if (!lexical.contained) {
      return fail("wd-out-of-root", lexical.reason ?? "outside-root");
    }

    // Lexical containment is not enough: a working directory below a symlink or
    // junction can resolve outside the trusted root. The runtime event may only
    // use a directory that really exists; an unavailable root/directory fails
    // closed rather than silently degrading to a lexical-only check.
    let canonicalRoot: string;
    let canonicalWorkingDirectory: string;
    try {
      canonicalRoot = await this.#canonicalize(expectedRoot);
      canonicalWorkingDirectory = await this.#canonicalize(workingDirectory);
    } catch {
      return fail("wd-root-unavailable");
    }
    const canonical = checkContainment(canonicalRoot, canonicalWorkingDirectory);
    if (!canonical.contained) {
      return fail("wd-symlink-escape", canonical.reason ?? "outside-canonical-root");
    }
    return { ok: true };
  }
}
