import { deepFreeze, isPlainObject } from "./canonical-json.ts";
import type { Budget, RoleId } from "./contract.ts";
import { isRoleId } from "./contract.ts";
import type { FleetErrorCode } from "./errors.ts";
import { FleetPolicyError } from "./errors.ts";
import type { IdGenerator } from "./ids.ts";
import { UuidIdGenerator } from "./ids.ts";
import { getPresetByIdVersion } from "./registries/roles.ts";
import { getWorkspace } from "./registries/workspaces.ts";
import type { Clock } from "./time.ts";
import { nowIso, SystemClock } from "./time.ts";

export const WFI_PATTERN = /^wfi_[A-Za-z0-9_-]{8,96}$/;
export const RUN_ID_PATTERN = /^run_[A-Za-z0-9_-]{8,96}$/;
export const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,96}$/;
export const EVENT_ID_PATTERN = /^evt_[A-Za-z0-9_-]{8,96}$/;
export const BINDING_ID_PATTERN = /^bind_[A-Za-z0-9_-]{8,96}$/;
export const MEMORY_PACK_ID_PATTERN = /^mp_[a-f0-9]{32}$/;
export const SHA256_PATTERN = /^[a-f0-9]{64}$/;
export const APPROVAL_REF_PATTERN = /^apr_[A-Za-z0-9_-]{4,128}$/;
export const BASE_SHA_PATTERN = /^([a-f0-9]{40}|[a-f0-9]{64})$/;
export const WORKSPACE_ID_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/;
export const EPISODE_ID_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/;
export const PRESET_ID_PATTERN = /^preset_[a-z][a-z0-9_]{2,63}$/;
export const PRESET_VERSION_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+$/;
export const TASK_ID_PATTERN = /^[a-z][a-z0-9_]{1,63}$/;

export interface MemoryPackRef {
  snapshot_id: string;
  snapshot_hash: string;
  workspace_id: string;
  episode_id: string | null;
}

export interface TrustedBindingInput {
  workflow_instance_id: string;
  workspace_id: string;
  episode_id?: string | null;
  role: RoleId;
  preset_id: string;
  preset_version: string;
  tool_profile: string;
  memory_pack?: MemoryPackRef | null;
  approval_ref?: string | null;
  base_sha?: string | null;
  max_budget?: Budget;
  max_timeout_ms?: number;
}

export interface TrustedBinding {
  readonly binding_id: string;
  readonly issued_at: string;
  readonly workflow_instance_id: string;
  readonly workspace_id: string;
  readonly episode_id: string | null;
  readonly role: RoleId;
  readonly preset_id: string;
  readonly preset_version: string;
  readonly tool_profile: string;
  readonly memory_pack: MemoryPackRef | null;
  readonly approval_ref: string | null;
  readonly base_sha: string | null;
  readonly max_budget: Budget;
  readonly max_timeout_ms: number;
}

export interface BindingIssuerOptions {
  idGenerator?: IdGenerator;
  clock?: Clock;
}

function fail(code: FleetErrorCode, message: string): never {
  throw new FleetPolicyError(code, message);
}

function validateMemoryPackRef(
  value: unknown,
  workspaceId: string,
  episodeId: string | null
): MemoryPackRef {
  if (!isPlainObject(value)) {
    fail("memory-scope-mismatch", "memory_pack must be an object");
  }
  const snapshotId = value.snapshot_id;
  const snapshotHash = value.snapshot_hash;
  const packWorkspace = value.workspace_id;
  const packEpisode = value.episode_id;
  if (typeof snapshotId !== "string" || !MEMORY_PACK_ID_PATTERN.test(snapshotId)) {
    fail("memory-scope-mismatch", "memory_pack.snapshot_id is invalid");
  }
  if (typeof snapshotHash !== "string" || !SHA256_PATTERN.test(snapshotHash)) {
    fail("memory-scope-mismatch", "memory_pack.snapshot_hash is invalid");
  }
  if (typeof packWorkspace !== "string" || packWorkspace !== workspaceId) {
    fail("memory-scope-mismatch", "memory_pack workspace does not match the binding");
  }
  if (
    packEpisode !== null &&
    packEpisode !== undefined &&
    (typeof packEpisode !== "string" || !EPISODE_ID_PATTERN.test(packEpisode))
  ) {
    fail("memory-scope-mismatch", "memory_pack.episode_id is invalid");
  }
  if (
    episodeId !== null &&
    typeof packEpisode === "string" &&
    packEpisode !== episodeId
  ) {
    fail("memory-scope-mismatch", "memory_pack episode does not match the binding");
  }
  return {
    snapshot_id: snapshotId,
    snapshot_hash: snapshotHash,
    workspace_id: packWorkspace,
    episode_id: typeof packEpisode === "string" ? packEpisode : null
  };
}

function validateBudget(value: unknown, presetBudget: Budget): Budget {
  if (!isPlainObject(value)) {
    fail("invalid-request", "max_budget must be an object");
  }
  const maxTokens = value.max_tokens;
  const maxCost = value.max_cost_usd;
  if (
    typeof maxTokens !== "number" ||
    !Number.isFinite(maxTokens) ||
    !Number.isInteger(maxTokens) ||
    maxTokens < 0
  ) {
    fail("invalid-request", "max_budget.max_tokens is invalid");
  }
  if (typeof maxCost !== "number" || !Number.isFinite(maxCost) || maxCost < 0) {
    fail("invalid-request", "max_budget.max_cost_usd is invalid");
  }
  if (maxTokens > presetBudget.max_tokens || maxCost > presetBudget.max_cost_usd) {
    fail("budget-exceeds-preset", "binding budget exceeds the preset limit");
  }
  return { max_tokens: maxTokens, max_cost_usd: maxCost };
}

export class TrustedBindingIssuer {
  #issued = new WeakSet<object>();
  #ids: IdGenerator;
  #clock: Clock;

  constructor(options: BindingIssuerOptions = {}) {
    this.#ids = options.idGenerator ?? new UuidIdGenerator();
    this.#clock = options.clock ?? new SystemClock();
  }

  issue(input: TrustedBindingInput): TrustedBinding {
    if (!isPlainObject(input)) {
      fail("untrusted-binding", "binding input must be an object");
    }
    if (typeof input.workflow_instance_id !== "string" || !WFI_PATTERN.test(input.workflow_instance_id)) {
      fail("invalid-request", "workflow_instance_id is invalid");
    }
    if (typeof input.workspace_id !== "string" || !WORKSPACE_ID_PATTERN.test(input.workspace_id)) {
      fail("workspace-unknown", "workspace_id is invalid");
    }
    const workspace = getWorkspace(input.workspace_id);
    if (workspace === undefined) {
      fail("workspace-unknown", "workspace is not registered");
    }
    if (!workspace.enabled) {
      fail("workspace-disabled", "workspace is disabled");
    }
    if (!isRoleId(input.role)) {
      fail("role-unknown", "role is not registered");
    }
    const role = input.role;
    if (!workspace.allowed_roles.includes(role)) {
      fail("workspace-role-denied", "role is not allowed in this workspace");
    }
    if (typeof input.preset_id !== "string" || !PRESET_ID_PATTERN.test(input.preset_id)) {
      fail("preset-mismatch", "preset_id is invalid");
    }
    if (
      typeof input.preset_version !== "string" ||
      !PRESET_VERSION_PATTERN.test(input.preset_version)
    ) {
      fail("preset-mismatch", "preset_version is invalid");
    }
    const preset = getPresetByIdVersion(input.preset_id, input.preset_version);
    if (preset === undefined || preset.role !== role) {
      fail("preset-mismatch", "preset does not match the role");
    }
    if (typeof input.tool_profile !== "string" || input.tool_profile !== preset.tool_profile) {
      fail("preset-mismatch", "tool_profile does not match the preset");
    }
    const episodeId = input.episode_id ?? null;
    if (episodeId !== null && (typeof episodeId !== "string" || !EPISODE_ID_PATTERN.test(episodeId))) {
      fail("invalid-request", "episode_id is invalid");
    }
    const memoryPack =
      input.memory_pack === undefined || input.memory_pack === null
        ? null
        : validateMemoryPackRef(input.memory_pack, input.workspace_id, episodeId);
    const approvalRef = input.approval_ref ?? null;
    if (approvalRef !== null && (typeof approvalRef !== "string" || !APPROVAL_REF_PATTERN.test(approvalRef))) {
      fail("invalid-request", "approval_ref is invalid");
    }
    const baseSha = input.base_sha ?? null;
    if (baseSha !== null && (typeof baseSha !== "string" || !BASE_SHA_PATTERN.test(baseSha))) {
      fail("invalid-request", "base_sha is invalid");
    }
    const maxBudget = validateBudget(input.max_budget ?? preset.max_budget, preset.max_budget);
    const maxTimeout = input.max_timeout_ms ?? preset.max_timeout_ms;
    if (
      typeof maxTimeout !== "number" ||
      !Number.isInteger(maxTimeout) ||
      maxTimeout < 1 ||
      maxTimeout > preset.max_timeout_ms
    ) {
      fail("deadline-exceeds-preset", "max_timeout_ms is invalid or exceeds the preset limit");
    }

    const binding = deepFreeze<TrustedBinding>({
      binding_id: this.#ids.bindingId(),
      issued_at: nowIso(this.#clock),
      workflow_instance_id: input.workflow_instance_id,
      workspace_id: input.workspace_id,
      episode_id: episodeId,
      role,
      preset_id: input.preset_id,
      preset_version: input.preset_version,
      tool_profile: input.tool_profile,
      memory_pack: memoryPack,
      approval_ref: approvalRef,
      base_sha: baseSha,
      max_budget: maxBudget,
      max_timeout_ms: maxTimeout
    });
    this.#issued.add(binding);
    return binding;
  }

  verify(value: unknown): value is TrustedBinding {
    return (
      value !== null &&
      typeof value === "object" &&
      this.#issued.has(value as object)
    );
  }

  assertTrusted(value: unknown): TrustedBinding {
    if (!this.verify(value)) {
      throw new FleetPolicyError("untrusted-binding", "binding was not issued by the trusted host");
    }
    return value;
  }
}
