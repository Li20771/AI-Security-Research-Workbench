import { deepFreeze, sha256OfJson } from "../canonical-json.ts";
import type {
  Authority,
  MemoryLayer,
  MemoryType,
  RoleId,
  Visibility
} from "../contract.ts";

/** MemoryPack is versioned independently from the Fleet API contract. */
export const MEMORYPACK_CONTRACT_VERSION = "1.2.0" as const;

/** Reserved owner for an explicit user-global entry without an origin scope. */
export const GLOBAL_WORKSPACE_ID = "global" as const;

export type MemoryPackErrorCode =
  | "memory-context-untrusted"
  | "memory-scope-missing"
  | "memory-scope-invalid"
  | "memory-workspace-denied"
  | "memory-episode-denied"
  | "memory-role-denied"
  | "memory-snapshot-mismatch"
  | "memory-contract-version"
  | "memory-internal-error";

export class MemoryPackError extends Error {
  code: MemoryPackErrorCode;

  constructor(code: MemoryPackErrorCode, message: string) {
    super(message);
    this.name = "MemoryPackError";
    this.code = code;
  }
}

export interface MemoryPackContext {
  workspace_id: string;
  episode_id: string | null;
  role: RoleId;
  run_id: string;
  task_id: string;
  purpose: string;
  max_entries: number;
}

export interface MemoryPackSource {
  ref: string;
  revision?: string;
  kind?: "memory" | "file" | "report" | "artifact";
}

export interface MemoryPackEntry {
  entry_id: string;
  path: string;
  layer: MemoryLayer;
  type: MemoryType;
  title: string;
  visibility: Visibility;
  workspace_id: string;
  episode_id: string | null;
  authority: Authority;
  review_state: "approved";
  revision: string;
  body: string;
  sources: MemoryPackSource[];
  sha256: string;
}

export interface MemoryPack {
  contract_version: typeof MEMORYPACK_CONTRACT_VERSION;
  snapshot_id: string;
  snapshot_hash: string;
  generated_at: string;
  read_only: true;
  scope: {
    workspace_id: string;
    episode_id: string | null;
  };
  role: RoleId;
  run_id: string;
  entries: MemoryPackEntry[];
  excluded: {
    pending: number;
    rejected: number;
    superseded: number;
    restricted: number;
    unmarked: number;
    path_invalid: number;
    entry_invalid: number;
    /**
     * Authorized records whose layer could not be resolved (missing/unknown
     * `type` and no valid explicit `layer`). They never enter `entries` and are
     * never relabelled as `KB`.
     */
    unspecified_layer: number;
  };
  source: {
    vault: "dsh-memory";
    contract_version: typeof MEMORYPACK_CONTRACT_VERSION;
  };
  policy: {
    authorized_before_retrieval: true;
    cross_workspace: boolean;
  };
}

export interface MemoryPackClient {
  getPack(context: MemoryPackContext): Promise<MemoryPack>;
}

/**
 * Locale-independent Unicode code-point comparison.
 *
 * `localeCompare` depends on the host locale/ICU data and must never decide
 * MemoryPack ordering or the snapshot hash. Comparing code points is stable
 * across processes, platforms and locales; a proper prefix sorts first.
 */
export function compareCodePoints(left: string, right: string): number {
  const leftPoints = Array.from(left, (char) => char.codePointAt(0) as number);
  const rightPoints = Array.from(right, (char) => char.codePointAt(0) as number);
  const shared = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < shared; index += 1) {
    const leftPoint = leftPoints[index] as number;
    const rightPoint = rightPoints[index] as number;
    if (leftPoint !== rightPoint) {
      return leftPoint < rightPoint ? -1 : 1;
    }
  }
  return leftPoints.length - rightPoints.length;
}

export function snapshotHashFor(
  scope: { workspace_id: string; episode_id: string | null },
  role: RoleId,
  entries: readonly MemoryPackEntry[]
): string {
  const sorted = [...entries].sort((left, right) => {
    const pathOrder = compareCodePoints(left.path, right.path);
    if (pathOrder !== 0) {
      return pathOrder;
    }
    return compareCodePoints(left.revision, right.revision);
  });
  return sha256OfJson({
    contract_version: MEMORYPACK_CONTRACT_VERSION,
    scope,
    role,
    entries: sorted
  });
}

export function snapshotIdFor(hash: string): string {
  return `mp_${hash.slice(0, 32)}`;
}

export function entrySha256(entry: Pick<MemoryPackEntry, "path" | "revision" | "body">): string {
  return sha256OfJson({
    path: entry.path,
    revision: entry.revision,
    body: entry.body
  });
}

export function freezeMemoryPack(pack: MemoryPack): MemoryPack {
  return deepFreeze(pack);
}
