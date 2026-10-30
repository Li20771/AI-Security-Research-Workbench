import { deepFreeze } from "../canonical-json.ts";
import type { Budget, PluginRef, RoleId } from "../contract.ts";
import { pluginRef } from "./plugins.ts";

export type WorkspaceVisibility = "bound-workspace" | "none";
export type DataScope = "read-only" | "none";

export interface RolePreset {
  preset_id: string;
  preset_version: string;
  role: RoleId;
  enabled: boolean;
  worker: boolean;
  dsh_profile: string;
  plugin_manifest: readonly PluginRef[];
  mcp_server: string | null;
  tool_profile: string | null;
  allowed_tools: readonly string[];
  input_schema_id: string;
  output_schema_id: string;
  workspace_visibility: WorkspaceVisibility;
  data_scope: DataScope;
  max_timeout_ms: number;
  default_timeout_ms: number;
  max_concurrent: number;
  max_output_bytes: number;
  max_budget: Budget;
  env_allowlist: readonly string[];
  requires_approval: boolean;
}

const CORE_PLUGINS: readonly PluginRef[] = [
  pluginRef("fleet.core"),
  pluginRef("fleet.output-schema"),
  pluginRef("fleet.ledger")
];

const READ_ONLY_PLUGINS: readonly PluginRef[] = [
  ...CORE_PLUGINS,
  pluginRef("fleet.memorypack-readonly"),
  pluginRef("fleet.securitylab-ro")
];

const LAB_RUNNER_PLUGINS: readonly PluginRef[] = [
  ...CORE_PLUGINS,
  pluginRef("fleet.memorypack-readonly"),
  pluginRef("fleet.securitylab-vcan", false)
];

const READ_ONLY_TOOLS: readonly string[] = [
  "lab_catalog",
  "lab_status",
  "lab_read_file",
  "lab_get_report",
  "lab_get_run_result"
];

const CHALLENGER_TOOLS: readonly string[] = [
  "lab_catalog",
  "lab_status",
  "lab_read_file",
  "lab_get_report"
];

export const ROLE_PRESETS: readonly RolePreset[] = deepFreeze([
  {
    preset_id: "preset_orchestrator",
    preset_version: "1.0.0",
    role: "orchestrator",
    enabled: true,
    worker: false,
    dsh_profile: "dsh-main-v1",
    plugin_manifest: CORE_PLUGINS,
    mcp_server: null,
    tool_profile: "orchestrator_none_v1",
    allowed_tools: [],
    input_schema_id: "fleet.submit.input.v1",
    output_schema_id: "worker-result.v1",
    workspace_visibility: "bound-workspace",
    data_scope: "none",
    max_timeout_ms: 60000,
    default_timeout_ms: 30000,
    max_concurrent: 1,
    max_output_bytes: 0,
    max_budget: { max_tokens: 0, max_cost_usd: 0 },
    env_allowlist: [],
    requires_approval: false
  },
  {
    preset_id: "preset_researcher",
    preset_version: "1.0.0",
    role: "researcher",
    enabled: true,
    worker: true,
    dsh_profile: "dsh-researcher-v1",
    plugin_manifest: READ_ONLY_PLUGINS,
    mcp_server: "securitylab_ro",
    tool_profile: "researcher_ro_v1",
    allowed_tools: READ_ONLY_TOOLS,
    input_schema_id: "fleet.submit.input.v1",
    output_schema_id: "worker-result.v1",
    workspace_visibility: "bound-workspace",
    data_scope: "read-only",
    max_timeout_ms: 120000,
    default_timeout_ms: 60000,
    max_concurrent: 2,
    max_output_bytes: 262144,
    max_budget: { max_tokens: 4000, max_cost_usd: 0.1 },
    env_allowlist: ["LANG", "LC_ALL", "TZ"],
    requires_approval: false
  },
  {
    preset_id: "preset_vehicle_analyst",
    preset_version: "1.0.0",
    role: "vehicle_analyst",
    enabled: true,
    worker: true,
    dsh_profile: "dsh-vehicle-analyst-v1",
    plugin_manifest: READ_ONLY_PLUGINS,
    mcp_server: "securitylab_ro",
    tool_profile: "vehicle_analyst_ro_v1",
    allowed_tools: READ_ONLY_TOOLS,
    input_schema_id: "fleet.submit.input.v1",
    output_schema_id: "worker-result.v1",
    workspace_visibility: "bound-workspace",
    data_scope: "read-only",
    max_timeout_ms: 120000,
    default_timeout_ms: 60000,
    max_concurrent: 2,
    max_output_bytes: 262144,
    max_budget: { max_tokens: 4000, max_cost_usd: 0.1 },
    env_allowlist: ["LANG", "LC_ALL", "TZ"],
    requires_approval: false
  },
  {
    preset_id: "preset_challenger",
    preset_version: "1.0.0",
    role: "challenger",
    enabled: true,
    worker: true,
    dsh_profile: "dsh-challenger-v1",
    plugin_manifest: READ_ONLY_PLUGINS,
    mcp_server: "securitylab_ro",
    tool_profile: "challenger_ro_v1",
    allowed_tools: CHALLENGER_TOOLS,
    input_schema_id: "fleet.submit.input.v1",
    output_schema_id: "worker-result.v1",
    workspace_visibility: "bound-workspace",
    data_scope: "read-only",
    max_timeout_ms: 90000,
    default_timeout_ms: 45000,
    max_concurrent: 1,
    max_output_bytes: 131072,
    max_budget: { max_tokens: 3000, max_cost_usd: 0.05 },
    env_allowlist: ["LANG", "LC_ALL", "TZ"],
    requires_approval: false
  },
  {
    preset_id: "preset_evidence_verifier",
    preset_version: "1.0.0",
    role: "evidence_verifier",
    enabled: true,
    worker: true,
    dsh_profile: "dsh-evidence-verifier-v1",
    plugin_manifest: READ_ONLY_PLUGINS,
    mcp_server: "securitylab_ro",
    tool_profile: "evidence_verifier_ro_v1",
    allowed_tools: READ_ONLY_TOOLS,
    input_schema_id: "fleet.submit.input.v1",
    output_schema_id: "worker-result.v1",
    workspace_visibility: "bound-workspace",
    data_scope: "read-only",
    max_timeout_ms: 90000,
    default_timeout_ms: 45000,
    max_concurrent: 1,
    max_output_bytes: 131072,
    max_budget: { max_tokens: 3000, max_cost_usd: 0.05 },
    env_allowlist: ["LANG", "LC_ALL", "TZ"],
    requires_approval: false
  },
  {
    preset_id: "preset_lab_runner",
    preset_version: "1.0.0",
    role: "lab_runner",
    enabled: false,
    worker: true,
    dsh_profile: "dsh-lab-runner-v1",
    plugin_manifest: LAB_RUNNER_PLUGINS,
    mcp_server: "securitylab_vcan",
    tool_profile: "lab_runner_vcan_v1",
    allowed_tools: ["securitylab_vcan"],
    input_schema_id: "fleet.submit.input.v1",
    output_schema_id: "worker-result.v1",
    workspace_visibility: "bound-workspace",
    data_scope: "read-only",
    max_timeout_ms: 300000,
    default_timeout_ms: 120000,
    max_concurrent: 1,
    max_output_bytes: 131072,
    max_budget: { max_tokens: 1000, max_cost_usd: 0 },
    env_allowlist: [],
    requires_approval: true
  }
]);

const BY_ROLE = new Map<RoleId, RolePreset>();
const BY_ID_VERSION = new Map<string, RolePreset>();
for (const preset of ROLE_PRESETS) {
  if (BY_ROLE.has(preset.role)) {
    throw new Error(`duplicate role preset: ${preset.role}`);
  }
  BY_ROLE.set(preset.role, preset);
  BY_ID_VERSION.set(`${preset.preset_id}@${preset.preset_version}`, preset);
}

export function getRolePreset(role: RoleId): RolePreset | undefined {
  return BY_ROLE.get(role);
}

export function getPresetByIdVersion(
  presetId: string,
  presetVersion: string
): RolePreset | undefined {
  return BY_ID_VERSION.get(`${presetId}@${presetVersion}`);
}

export function isRoleEnabled(role: RoleId): boolean {
  return BY_ROLE.get(role)?.enabled === true;
}

export function allRolePresets(): readonly RolePreset[] {
  return ROLE_PRESETS;
}
