import { canonicalJson, isPlainObject, jsonByteLength } from "./canonical-json.ts";
import type { Budget, WorkflowId } from "./contract.ts";
import { FORBIDDEN_IDENTITY_REQUEST_KEYS, isWorkflowId } from "./contract.ts";
import type { FleetErrorCode } from "./errors.ts";
import type { StatusQuery, SubmitRequest } from "./api-types.ts";
import {
  RUN_ID_PATTERN,
  TASK_ID_PATTERN,
  WFI_PATTERN
} from "./binding.ts";

export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; code: FleetErrorCode; message: string };

const SUBMIT_KEYS = new Set([
  "contract_version",
  "workflow_id",
  "task_id",
  "input",
  "parent_run_id",
  "deadline_ms",
  "budget"
]);

const STATUS_KEYS = new Set([
  "contract_version",
  "run_id",
  "workflow_instance_id",
  "task_id"
]);

const FORBIDDEN_KEYS = new Set<string>(FORBIDDEN_IDENTITY_REQUEST_KEYS);

const MAX_INPUT_BYTES = 16 * 1024;

function invalid(message: string): ValidationResult<never> {
  return { ok: false, code: "invalid-request", message };
}

function identity(message: string): ValidationResult<never> {
  return { ok: false, code: "identity-in-request", message };
}

export function validateSubmitRequest(value: unknown): ValidationResult<SubmitRequest> {
  if (!isPlainObject(value)) {
    return invalid("request must be an object");
  }
  for (const key of Object.keys(value)) {
    if (FORBIDDEN_KEYS.has(key)) {
      return identity(`request must not set identity or permission field: ${key}`);
    }
  }
  for (const key of Object.keys(value)) {
    if (!SUBMIT_KEYS.has(key)) {
      return invalid(`unknown request field: ${key}`);
    }
  }
  const contractVersion = value.contract_version;
  if (contractVersion !== "1.0.0") {
    if (typeof contractVersion === "string") {
      return {
        ok: false,
        code: "contract-version-mismatch",
        message: `unsupported contract_version: ${contractVersion}`
      };
    }
    return invalid("contract_version is required");
  }
  const workflowId = value.workflow_id;
  if (typeof workflowId !== "string" || !isWorkflowId(workflowId)) {
    return invalid("workflow_id is not a registered workflow");
  }
  const taskId = value.task_id;
  if (typeof taskId !== "string" || !TASK_ID_PATTERN.test(taskId)) {
    return invalid("task_id is invalid");
  }
  const input = value.input;
  if (!isPlainObject(input)) {
    return invalid("input must be a JSON object");
  }
  if (Object.keys(input).length > 32) {
    return invalid("input has too many top-level fields");
  }
  for (const key of Object.keys(input)) {
    if (key.length > 64) {
      return invalid("input field name is too long");
    }
  }
  try {
    canonicalJson(input);
  } catch {
    return invalid("input must be canonical JSON data");
  }
  if (jsonByteLength(input) > MAX_INPUT_BYTES) {
    return invalid("input exceeds 16 KiB");
  }

  let parentRunId: string | null = null;
  if (value.parent_run_id !== undefined && value.parent_run_id !== null) {
    if (typeof value.parent_run_id !== "string" || !RUN_ID_PATTERN.test(value.parent_run_id)) {
      return invalid("parent_run_id is invalid");
    }
    parentRunId = value.parent_run_id;
  }

  let deadlineMs: number | null = null;
  if (value.deadline_ms !== undefined && value.deadline_ms !== null) {
    const deadline = value.deadline_ms;
    if (
      typeof deadline !== "number" ||
      !Number.isInteger(deadline) ||
      deadline < 1 ||
      deadline > 86400000
    ) {
      return invalid("deadline_ms is invalid");
    }
    deadlineMs = deadline;
  }

  let budget: Budget | null = null;
  if (value.budget !== undefined && value.budget !== null) {
    if (!isPlainObject(value.budget)) {
      return invalid("budget must be an object");
    }
    for (const key of Object.keys(value.budget)) {
      if (key !== "max_tokens" && key !== "max_cost_usd") {
        return invalid(`unknown budget field: ${key}`);
      }
    }
    const maxTokens = value.budget.max_tokens;
    const maxCost = value.budget.max_cost_usd;
    if (
      typeof maxTokens !== "number" ||
      !Number.isInteger(maxTokens) ||
      maxTokens < 0 ||
      maxTokens > 1000000
    ) {
      return invalid("budget.max_tokens is invalid");
    }
    if (
      typeof maxCost !== "number" ||
      !Number.isFinite(maxCost) ||
      maxCost < 0 ||
      maxCost > 1000
    ) {
      return invalid("budget.max_cost_usd is invalid");
    }
    budget = { max_tokens: maxTokens, max_cost_usd: maxCost };
  }

  return {
    ok: true,
    value: {
      contract_version: "1.0.0",
      workflow_id: workflowId as WorkflowId,
      task_id: taskId,
      input,
      parent_run_id: parentRunId,
      deadline_ms: deadlineMs,
      budget
    }
  };
}

export function validateStatusQuery(value: unknown): ValidationResult<StatusQuery> {
  if (!isPlainObject(value)) {
    return invalid("status query must be an object");
  }
  for (const key of Object.keys(value)) {
    if (!STATUS_KEYS.has(key)) {
      return invalid(`unknown status query field: ${key}`);
    }
  }
  if (value.contract_version !== "1.0.0") {
    if (typeof value.contract_version === "string") {
      return {
        ok: false,
        code: "contract-version-mismatch",
        message: `unsupported contract_version: ${value.contract_version}`
      };
    }
    return invalid("contract_version is required");
  }
  const runId = value.run_id;
  const workflowInstanceId = value.workflow_instance_id;
  const taskId = value.task_id;
  if (runId !== undefined && workflowInstanceId !== undefined) {
    return invalid("run_id and workflow_instance_id are mutually exclusive");
  }
  if (runId !== undefined) {
    if (typeof runId !== "string" || !RUN_ID_PATTERN.test(runId)) {
      return invalid("run_id is invalid");
    }
    if (taskId !== undefined) {
      return invalid("task_id cannot be combined with run_id");
    }
    return {
      ok: true,
      value: {
        contract_version: "1.0.0",
        run_id: runId,
        workflow_instance_id: null,
        task_id: null
      }
    };
  }
  if (workflowInstanceId !== undefined) {
    if (typeof workflowInstanceId !== "string" || !WFI_PATTERN.test(workflowInstanceId)) {
      return invalid("workflow_instance_id is invalid");
    }
    if (taskId !== undefined && (typeof taskId !== "string" || !TASK_ID_PATTERN.test(taskId))) {
      return invalid("task_id is invalid");
    }
    return {
      ok: true,
      value: {
        contract_version: "1.0.0",
        run_id: null,
        workflow_instance_id: workflowInstanceId,
        task_id: typeof taskId === "string" ? taskId : null
      }
    };
  }
  return invalid("status query requires run_id or workflow_instance_id");
}

export function isRunId(value: string): boolean {
  return RUN_ID_PATTERN.test(value);
}
