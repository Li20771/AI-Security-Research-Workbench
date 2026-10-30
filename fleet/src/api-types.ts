import type {
  Budget,
  CleanupState,
  RoleId,
  RunStatus,
  WorkflowId
} from "./contract.ts";
import type { FleetErrorShape } from "./errors.ts";
import type { WorkerResultEnvelope } from "./worker-result.ts";

export interface SubmitData {
  workflow_instance_id: string;
  run_id: string | null;
  status: "queued" | "waiting_approval" | "completed";
  accepted_at: string;
}

export interface RunSummary {
  run_id: string;
  workflow_instance_id: string;
  workflow_id: WorkflowId;
  task_id: string;
  parent_run_id: string | null;
  role: RoleId;
  preset_id: string;
  preset_version: string;
  workspace_id: string;
  episode_id: string | null;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  session_id: string | null;
  result_ref: string | null;
  result_sha256: string | null;
  cleanup_state: CleanupState | null;
  reason_code: string | null;
  reason: string | null;
}

export interface StatusData {
  runs: RunSummary[];
}

export interface ResultData {
  run_id: string;
  status: "completed";
  result_ref: string;
  result_sha256: string;
  untrusted: true;
  admission: "none";
  evidence: false;
  result: WorkerResultEnvelope;
  artifacts: Array<{ ref: string; sha256: string }>;
}

export interface CancelData {
  run_id: string;
  status: "cancelled" | "blocked";
  cleanup: {
    state: CleanupState;
    detail: string | null;
  };
}

export interface FleetResponseBase {
  contract_version: "1.0.0";
  ok: boolean;
  error?: FleetErrorShape | null;
}

export interface SubmitResponse extends FleetResponseBase {
  operation: "submit";
  data?: SubmitData;
}

export interface StatusResponse extends FleetResponseBase {
  operation: "status";
  data?: StatusData;
}

export interface ResultResponse extends FleetResponseBase {
  operation: "result";
  data?: ResultData;
}

export interface CancelResponse extends FleetResponseBase {
  operation: "cancel";
  data?: CancelData;
}

export type FleetResponse = SubmitResponse | StatusResponse | ResultResponse | CancelResponse;

export interface SubmitRequest {
  contract_version: "1.0.0";
  workflow_id: WorkflowId;
  task_id: string;
  input: Record<string, unknown>;
  parent_run_id: string | null;
  deadline_ms: number | null;
  budget: Budget | null;
}

export interface StatusQuery {
  contract_version: "1.0.0";
  run_id: string | null;
  workflow_instance_id: string | null;
  task_id: string | null;
}
