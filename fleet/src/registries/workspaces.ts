import { deepFreeze } from "../canonical-json.ts";
import type { RoleId } from "../contract.ts";

export interface WorkspaceDefinition {
  workspace_id: string;
  enabled: boolean;
  allowed_roles: readonly RoleId[];
  root_ref: string;
}

const ALL_ROLES: readonly RoleId[] = [
  "orchestrator",
  "researcher",
  "vehicle_analyst",
  "challenger",
  "evidence_verifier",
  "lab_runner"
];

export const WORKSPACE_REGISTRY: readonly WorkspaceDefinition[] = deepFreeze([
  {
    workspace_id: "ws_a",
    enabled: true,
    allowed_roles: ALL_ROLES,
    root_ref: "workspace://ws_a"
  },
  {
    workspace_id: "ws_b",
    enabled: true,
    allowed_roles: ALL_ROLES,
    root_ref: "workspace://ws_b"
  },
  {
    workspace_id: "ws_disabled",
    enabled: false,
    allowed_roles: ALL_ROLES,
    root_ref: "workspace://ws_disabled"
  }
]);

const BY_ID = new Map<string, WorkspaceDefinition>(
  WORKSPACE_REGISTRY.map((workspace) => [workspace.workspace_id, workspace])
);

export function getWorkspace(workspaceId: string): WorkspaceDefinition | undefined {
  return BY_ID.get(workspaceId);
}

export function isWorkspaceEnabled(workspaceId: string): boolean {
  return BY_ID.get(workspaceId)?.enabled === true;
}
