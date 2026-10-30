import { deepFreeze, isPlainObject } from "../canonical-json.ts";
import type {
  Authority,
  MemoryLayer,
  MemoryType,
  ReviewState,
  RoleId,
  Visibility
} from "../contract.ts";
import { isRoleId } from "../contract.ts";
import { FleetPolicyError } from "../errors.ts";
import {
  EPISODE_ID_PATTERN,
  RUN_ID_PATTERN,
  TASK_ID_PATTERN,
  WORKSPACE_ID_PATTERN
} from "../binding.ts";
import { getWorkspace } from "../registries/workspaces.ts";
import type { Clock } from "../time.ts";
import { nowIso, SystemClock } from "../time.ts";
import type {
  MemoryPack,
  MemoryPackClient,
  MemoryPackContext,
  MemoryPackEntry
} from "./memorypack.ts";
import {
  GLOBAL_WORKSPACE_ID,
  MEMORYPACK_CONTRACT_VERSION,
  entrySha256,
  freezeMemoryPack,
  MemoryPackError,
  snapshotHashFor,
  snapshotIdFor
} from "./memorypack.ts";

export const RUN_PRIVATE_ID = "run_11111111111111111111111111111111";

interface MemorySeed {
  entry_id: string;
  path: string;
  layer: MemoryLayer;
  type: MemoryType;
  title: string;
  /** Missing means legacy `unmarked`; never inferred from type. */
  visibility?: Visibility;
  workspace_id: string;
  episode_id: string | null;
  authority: Authority;
  review_state: ReviewState;
  revision: string;
  body: string;
  run_id?: string;
}

/** v1.1.0 path rules: NFC Unicode, POSIX separators, no unsafe segments. */
function isPackPath(value: string): boolean {
  if (typeof value !== "string" || value === "" || value.length > 512) return false;
  if (/[\u0000-\u001f\u007f]/.test(value) || value.includes("\\")) return false;
  if (value.startsWith("/") || /^[A-Za-z]:/.test(value)) return false;
  const normalized = value.normalize("NFC");
  if (normalized.length > 512) return false;
  return normalized
    .split("/")
    .every((segment) => segment !== "" && segment !== "." && segment !== ".." && !segment.includes(":"));
}

const LAYER_ORDER: Readonly<Record<MemoryLayer, number>> = {
  L1: 1,
  L2: 2,
  L3: 3,
  L4: 4,
  KB: 5
};

const SEEDS: readonly MemorySeed[] = deepFreeze([
  {
    entry_id: "mem_a_episode_0001",
    path: "workspaces/ws_a/memory/episode-note.md",
    layer: "L4",
    type: "episode",
    title: "ws_a episode note",
    visibility: "episode-shared",
    workspace_id: "ws_a",
    episode_id: "ep_1",
    authority: "agent-observed",
    review_state: "approved",
    revision: "aaaaaaaaaaaa",
    body: "WS_A_CANARY"
  },
  {
    entry_id: "mem_a_shared_0001",
    path: "workspaces/ws_a/memory/shared-note.md",
    layer: "L3",
    type: "memory",
    title: "ws_a shared note",
    visibility: "workspace-shared",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "curator",
    review_state: "approved",
    revision: "bbbbbbbbbbbb",
    body: "WS_A_SHARED_CANARY"
  },
  {
    entry_id: "mem_global_0001",
    path: "global/user-global-note.md",
    layer: "L1",
    type: "knowledge",
    title: "user-global note",
    visibility: "user-global",
    workspace_id: GLOBAL_WORKSPACE_ID,
    episode_id: null,
    authority: "human-approved",
    review_state: "approved",
    revision: "cccccccccccc",
    body: "GLOBAL_CANARY"
  },
  {
    entry_id: "mem_a_unicode_0001",
    path: "workspaces/ws_a/memory/结论.md",
    layer: "L4",
    type: "episode",
    title: "ws_a unicode note",
    visibility: "episode-shared",
    workspace_id: "ws_a",
    episode_id: "ep_1",
    authority: "agent-observed",
    review_state: "approved",
    revision: "666666666666",
    body: "UNICODE_PATH_CANARY"
  },
  {
    entry_id: "mem_a_unmarked_0001",
    path: "workspaces/ws_a/memory/unmarked.md",
    layer: "L4",
    type: "memory",
    title: "legacy unmarked note",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "agent-observed",
    review_state: "approved",
    revision: "888888888888",
    body: "UNMARKED_CANARY"
  },
  {
    entry_id: "mem_a_bad_path_0001",
    path: "../escape.md",
    layer: "L4",
    type: "memory",
    title: "invalid path note",
    visibility: "workspace-shared",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "agent-observed",
    review_state: "approved",
    revision: "777777777777",
    body: "BAD_PATH_CANARY"
  },
  {
    entry_id: "mem_b_foreign_0001",
    path: "workspaces/ws_b/memory/foreign-note.md",
    layer: "L4",
    type: "memory",
    title: "ws_b foreign note",
    visibility: "workspace-shared",
    workspace_id: "ws_b",
    episode_id: "ep_b",
    authority: "agent-observed",
    review_state: "approved",
    revision: "dddddddddddd",
    body: "WS_B_CANARY"
  },
  {
    entry_id: "mem_a_restricted_0001",
    path: "workspaces/ws_a/memory/restricted.md",
    layer: "L4",
    type: "memory",
    title: "restricted note",
    visibility: "workspace-shared",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "curator",
    review_state: "restricted",
    revision: "eeeeeeeeeeee",
    body: "RESTRICTED_CANARY"
  },
  {
    entry_id: "mem_a_pending_0001",
    path: "workspaces/ws_a/memory/pending.md",
    layer: "L4",
    type: "memory",
    title: "pending note",
    visibility: "workspace-shared",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "agent-observed",
    review_state: "pending",
    revision: "ffffffffffff",
    body: "PENDING_CANARY"
  },
  {
    entry_id: "mem_a_rejected_0001",
    path: "workspaces/ws_a/memory/rejected.md",
    layer: "L4",
    type: "memory",
    title: "rejected note",
    visibility: "workspace-shared",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "agent-observed",
    review_state: "rejected",
    revision: "111111111111",
    body: "REJECTED_CANARY"
  },
  {
    entry_id: "mem_a_superseded_0001",
    path: "workspaces/ws_a/memory/superseded.md",
    layer: "L4",
    type: "memory",
    title: "superseded note",
    visibility: "workspace-shared",
    workspace_id: "ws_a",
    episode_id: null,
    authority: "curator",
    review_state: "superseded",
    revision: "222222222222",
    body: "SUPERSEDED_CANARY"
  },
  {
    entry_id: "mem_a_run_private_0001",
    path: "workspaces/ws_a/memory/run-private.md",
    layer: "L4",
    type: "episode",
    title: "run-private note",
    visibility: "run-private",
    workspace_id: "ws_a",
    episode_id: "ep_1",
    authority: "agent-observed",
    review_state: "approved",
    revision: "333333333333",
    body: "RUN_PRIVATE_CANARY",
    run_id: RUN_PRIVATE_ID
  },
  {
    entry_id: "mem_a_other_episode_0001",
    path: "workspaces/ws_a/memory/other-episode.md",
    layer: "L4",
    type: "episode",
    title: "other episode note",
    visibility: "episode-shared",
    workspace_id: "ws_a",
    episode_id: "ep_2",
    authority: "agent-observed",
    review_state: "approved",
    revision: "444444444444",
    body: "OTHER_EPISODE_CANARY"
  }
]);

function inSlice(seed: MemorySeed, context: MemoryPackContext): boolean {
  if (seed.visibility === "user-global") return true;
  if (seed.workspace_id !== context.workspace_id) return false;
  if (seed.visibility === "episode-shared") {
    return seed.episode_id !== null && seed.episode_id === context.episode_id;
  }
  if (seed.visibility === "run-private") {
    return seed.run_id !== undefined && seed.run_id === context.run_id;
  }
  // workspace-shared and unmarked records belong to the workspace slice.
  return true;
}

function includeAllowed(seed: MemorySeed, context: MemoryPackContext): boolean {
  const visibility = seed.visibility;
  if (visibility === undefined) return false;
  if (visibility === "user-global") return true;
  if (seed.workspace_id !== context.workspace_id) return false;
  if (visibility === "episode-shared") {
    return seed.episode_id !== null && seed.episode_id === context.episode_id;
  }
  if (visibility === "run-private") {
    return seed.run_id !== undefined && seed.run_id === context.run_id;
  }
  return true;
}

function toEntry(seed: MemorySeed): MemoryPackEntry {
  const path = seed.path.normalize("NFC");
  return {
    entry_id: seed.entry_id,
    path,
    layer: seed.layer,
    type: seed.type,
    title: seed.title,
    visibility: seed.visibility as Visibility,
    workspace_id: seed.workspace_id,
    episode_id: seed.episode_id,
    authority: seed.authority,
    review_state: "approved" as const,
    revision: seed.revision,
    body: seed.body,
    sources: [],
    sha256: entrySha256({ path, revision: seed.revision, body: seed.body })
  };
}

function validateContext(context: MemoryPackContext): void {
  if (!isPlainObject(context)) {
    throw new MemoryPackError("memory-context-untrusted", "memory pack context must be an object");
  }
  const record = context as unknown as Record<string, unknown>;
  const workspaceId = record.workspace_id;
  const role = record.role;
  const runId = record.run_id;
  const taskId = record.task_id;
  if (
    typeof workspaceId !== "string" ||
    !WORKSPACE_ID_PATTERN.test(workspaceId) ||
    typeof role !== "string" ||
    !isRoleId(role) ||
    typeof runId !== "string" ||
    !RUN_ID_PATTERN.test(runId) ||
    typeof taskId !== "string" ||
    !TASK_ID_PATTERN.test(taskId)
  ) {
    throw new MemoryPackError("memory-scope-missing", "memory pack context is incomplete");
  }
  if (
    record.episode_id !== null &&
    (typeof record.episode_id !== "string" || !EPISODE_ID_PATTERN.test(record.episode_id))
  ) {
    throw new MemoryPackError("memory-scope-invalid", "episode_id is invalid");
  }
  if (typeof record.purpose !== "string" || record.purpose.length < 1 || record.purpose.length > 256) {
    throw new MemoryPackError("memory-scope-invalid", "purpose is invalid");
  }
  if (
    typeof record.max_entries !== "number" ||
    !Number.isInteger(record.max_entries) ||
    record.max_entries < 1 ||
    record.max_entries > 100
  ) {
    throw new MemoryPackError("memory-scope-invalid", "max_entries must be 1..100");
  }
  const workspace = getWorkspace(workspaceId);
  if (workspace === undefined || !workspace.enabled) {
    throw new MemoryPackError("memory-workspace-denied", "workspace is not registered or is disabled");
  }
  if (!workspace.allowed_roles.includes(role as RoleId)) {
    throw new MemoryPackError("memory-role-denied", "role is not allowed in this workspace");
  }
}

export class FakeMemoryPackClient implements MemoryPackClient {
  #clock: Clock;

  constructor(clock: Clock = new SystemClock()) {
    this.#clock = clock;
  }

  async getPack(context: MemoryPackContext): Promise<MemoryPack> {
    validateContext(context);
    const included: MemoryPackEntry[] = [];
    const excluded = {
      pending: 0,
      rejected: 0,
      superseded: 0,
      restricted: 0,
      unmarked: 0,
      path_invalid: 0,
      entry_invalid: 0
    };
    for (const seed of SEEDS) {
      if (!inSlice(seed, context)) {
        continue;
      }
      if (seed.review_state === "pending") {
        excluded.pending += 1;
        continue;
      }
      if (seed.review_state === "rejected") {
        excluded.rejected += 1;
        continue;
      }
      if (seed.review_state === "superseded") {
        excluded.superseded += 1;
        continue;
      }
      if (seed.review_state === "restricted") {
        excluded.restricted += 1;
        continue;
      }
      if (!includeAllowed(seed, context)) {
        excluded.unmarked += 1;
        continue;
      }
      if (!isPackPath(seed.path)) {
        excluded.path_invalid += 1;
        continue;
      }
      if (seed.body.length > 65536) {
        excluded.entry_invalid += 1;
        continue;
      }
      included.push(toEntry(seed));
    }
    included.sort((left, right) => {
      const layerDiff = LAYER_ORDER[left.layer] - LAYER_ORDER[right.layer];
      if (layerDiff !== 0) {
        return layerDiff;
      }
      return left.path.localeCompare(right.path);
    });
    const selected = included.slice(0, context.max_entries);
    const scope = {
      workspace_id: context.workspace_id,
      episode_id: context.episode_id
    };
    const snapshotHash = snapshotHashFor(scope, context.role, selected);
    const pack: MemoryPack = {
      contract_version: MEMORYPACK_CONTRACT_VERSION,
      snapshot_id: snapshotIdFor(snapshotHash),
      snapshot_hash: snapshotHash,
      generated_at: nowIso(this.#clock),
      read_only: true,
      scope,
      role: context.role,
      run_id: context.run_id,
      entries: selected,
      excluded,
      source: { vault: "dsh-memory", contract_version: MEMORYPACK_CONTRACT_VERSION },
      policy: {
        authorized_before_retrieval: true,
        cross_workspace: selected.some(
          (entry) => entry.visibility === "user-global" && entry.workspace_id !== context.workspace_id
        )
      }
    };
    return freezeMemoryPack(pack);
  }

  async createPackRef(
    workspaceId: string,
    episodeId: string | null,
    role: RoleId
  ): Promise<{ snapshot_id: string; snapshot_hash: string; workspace_id: string; episode_id: string | null }> {
    if (!isRoleId(role)) {
      throw new MemoryPackError("memory-scope-invalid", "role is invalid");
    }
    const context: MemoryPackContext = {
      workspace_id: workspaceId,
      episode_id: episodeId,
      role,
      run_id: "run_00000000000000000000000000000000",
      task_id: "main",
      purpose: "phase-snapshot-ref",
      max_entries: 100
    };
    const pack = await this.getPack(context);
    return {
      snapshot_id: pack.snapshot_id,
      snapshot_hash: pack.snapshot_hash,
      workspace_id: workspaceId,
      episode_id: episodeId
    };
  }
}

export function assertMemoryPackContractVersion(pack: MemoryPack): void {
  if (
    pack.contract_version !== MEMORYPACK_CONTRACT_VERSION ||
    pack.source.contract_version !== MEMORYPACK_CONTRACT_VERSION
  ) {
    throw new FleetPolicyError("internal-error", "memory pack contract version mismatch");
  }
}
