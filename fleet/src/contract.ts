export const CONTRACT_VERSION = "1.0.0" as const;

export const ROLE_IDS = [
  "orchestrator",
  "researcher",
  "vehicle_analyst",
  "challenger",
  "evidence_verifier",
  "lab_runner"
] as const;
export type RoleId = (typeof ROLE_IDS)[number];

export const WORKFLOW_IDS = [
  "single",
  "research",
  "design_review",
  "lab_validation",
  "security_audit"
] as const;
export type WorkflowId = (typeof WORKFLOW_IDS)[number];

export const RUN_STATUSES = [
  "created",
  "validated",
  "queued",
  "running",
  "waiting_approval",
  "completed",
  "failed",
  "blocked",
  "timed_out",
  "cancelled"
] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export const TERMINAL_STATUSES = [
  "completed",
  "failed",
  "blocked",
  "timed_out",
  "cancelled"
] as const;
export type TerminalStatus = (typeof TERMINAL_STATUSES)[number];

export const CLEANUP_STATES = ["not_needed", "succeeded", "failed", "unknown"] as const;
export type CleanupState = (typeof CLEANUP_STATES)[number];

export const VISIBILITIES = [
  "user-global",
  "workspace-shared",
  "episode-shared",
  "run-private"
] as const;
export type Visibility = (typeof VISIBILITIES)[number];

export const REVIEW_STATES = ["approved", "pending", "rejected", "superseded", "restricted"] as const;
export type ReviewState = (typeof REVIEW_STATES)[number];

export const MEMORY_LAYERS = ["L1", "L2", "L3", "L4", "KB"] as const;
export type MemoryLayer = (typeof MEMORY_LAYERS)[number];

export const MEMORY_TYPES = ["memory", "knowledge", "episode", "map", "reference"] as const;
export type MemoryType = (typeof MEMORY_TYPES)[number];

export const AUTHORITIES = ["human-approved", "curator", "agent-observed", "source-document"] as const;
export type Authority = (typeof AUTHORITIES)[number];

export const VERDICTS = ["confirmed", "rejected", "unresolved"] as const;
export type Verdict = (typeof VERDICTS)[number];

export const SEVERITIES = ["low", "medium", "high", "critical"] as const;
export type Severity = (typeof SEVERITIES)[number];

export const REQUESTED_ACTIONS = [
  "request_review",
  "request_approval",
  "propose_memory_candidate",
  "flag_evidence_gap",
  "request_additional_context"
] as const;
export type RequestedAction = (typeof REQUESTED_ACTIONS)[number];

export const TOOL_NAMES = [
  "lab_catalog",
  "lab_status",
  "lab_read_file",
  "lab_get_report",
  "lab_get_run_result",
  "securitylab_vcan"
] as const;
export type ToolName = (typeof TOOL_NAMES)[number];

export const MCP_PROFILES = ["securitylab_ro", "securitylab_vcan"] as const;
export type McpProfile = (typeof MCP_PROFILES)[number];

export const RUN_LEDGER_EVENT_TYPES = [
  "run.created",
  "run.validated",
  "run.queued",
  "run.waiting_approval",
  "run.approved",
  "run.session_opened",
  "run.started",
  "run.completed",
  "run.failed",
  "run.blocked",
  "run.timed_out",
  "run.cancelled",
  "run.cleanup",
  "run.reconciled",
  "request.rejected"
] as const;
export type RunLedgerEventType = (typeof RUN_LEDGER_EVENT_TYPES)[number];

export interface Budget {
  max_tokens: number;
  max_cost_usd: number;
}

export interface PluginRef {
  plugin_id: string;
  version: string;
  enabled: boolean;
}

export const CONTRACT_SCHEMA_IDS = {
  submitRequest: "urn:dsh-fleet:contract:fleet-submit-request:1.0.0",
  statusQuery: "urn:dsh-fleet:contract:fleet-status-query:1.0.0",
  submitResponse: "urn:dsh-fleet:contract:fleet-submit-response:1.0.0",
  statusResponse: "urn:dsh-fleet:contract:fleet-status-response:1.0.0",
  resultResponse: "urn:dsh-fleet:contract:fleet-result-response:1.0.0",
  cancelResponse: "urn:dsh-fleet:contract:fleet-cancel-response:1.0.0",
  workerResult: "urn:dsh-fleet:contract:worker-result:1.0.0",
  runLedger: "urn:dsh-fleet:contract:run-ledger:1.0.0",
  workflowRegistry: "urn:dsh-fleet:contract:workflow-registry:1.0.0",
  rolePreset: "urn:dsh-fleet:contract:role-preset:1.0.0",
  memoryPack: "urn:dsh-memory:contract:memorypack:1.0.0",
  securityLabCall: "urn:securitylab:contract:tool-call:1.0.0",
  securityLabResult: "urn:securitylab:contract:tool-result:1.0.0"
} as const;

export const FORBIDDEN_IDENTITY_REQUEST_KEYS = [
  "workflow_instance_id",
  "role",
  "workspace_id",
  "episode_id",
  "preset_id",
  "preset_version",
  "tool_profile",
  "approval_ref",
  "memory_pack",
  "memory_pack_snapshot_id",
  "env",
  "environment",
  "command",
  "path",
  "session_id",
  "run_id",
  "allowed_tools",
  "tools",
  "mcp_server",
  "model",
  "provider",
  "shell",
  "python",
  "credentials",
  "token"
] as const;

export const FORBIDDEN_LEDGER_KEYS = [
  "prompt",
  "prompts",
  "input",
  "messages",
  "message",
  "env",
  "environment",
  "env_values",
  "credential",
  "credentials",
  "token",
  "access_token",
  "refresh_token",
  "secret",
  "password",
  "api_key",
  "apikey",
  "authorization",
  "cookie",
  "chain_of_thought",
  "reasoning",
  "raw_output",
  "worker_output",
  "result_payload",
  "body"
] as const;

export const ALLOWED_LEDGER_DATA_KEYS = [
  "status",
  "reason_code",
  "reason",
  "request_id",
  "input_sha256",
  "workflow_id",
  "parent_run_id",
  "session_id",
  "preset_id",
  "preset_version",
  "workspace_id",
  "episode_id",
  "base_sha",
  "memory_pack_snapshot_id",
  "memory_pack_snapshot_hash",
  "tool_profile",
  "approval_ref",
  "deadline_ms",
  "budget",
  "result_ref",
  "result_sha256",
  "artifact_refs",
  "cleanup_state",
  "cleanup_detail",
  "worker",
  "parent_task_id",
  "reconciled_from_seq",
  "adapter",
  "duration_ms",
  "output_bytes"
] as const;

export function isRoleId(value: string): value is RoleId {
  return (ROLE_IDS as readonly string[]).includes(value);
}

export function isWorkflowId(value: string): value is WorkflowId {
  return (WORKFLOW_IDS as readonly string[]).includes(value);
}

export function isRunStatus(value: string): value is RunStatus {
  return (RUN_STATUSES as readonly string[]).includes(value);
}

export function isTerminalStatus(value: string): value is TerminalStatus {
  return (TERMINAL_STATUSES as readonly string[]).includes(value);
}

export function isCleanupState(value: string): value is CleanupState {
  return (CLEANUP_STATES as readonly string[]).includes(value);
}

export function isVisibility(value: string): value is Visibility {
  return (VISIBILITIES as readonly string[]).includes(value);
}

export function isMemoryLayer(value: string): value is MemoryLayer {
  return (MEMORY_LAYERS as readonly string[]).includes(value);
}

export function isMemoryType(value: string): value is MemoryType {
  return (MEMORY_TYPES as readonly string[]).includes(value);
}

export function isAuthority(value: string): value is Authority {
  return (AUTHORITIES as readonly string[]).includes(value);
}

export function isRequestedAction(value: string): value is RequestedAction {
  return (REQUESTED_ACTIONS as readonly string[]).includes(value);
}

export function isToolName(value: string): value is ToolName {
  return (TOOL_NAMES as readonly string[]).includes(value);
}

export function isMcpProfile(value: string): value is McpProfile {
  return (MCP_PROFILES as readonly string[]).includes(value);
}

export function isRunLedgerEventType(value: string): value is RunLedgerEventType {
  return (RUN_LEDGER_EVENT_TYPES as readonly string[]).includes(value);
}
