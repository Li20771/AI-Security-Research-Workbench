export const FLEET_ERROR_CODES = [
  "invalid-request",
  "identity-in-request",
  "untrusted-binding",
  "contract-version-mismatch",
  "workflow-unknown",
  "workflow-disabled",
  "task-unknown",
  "role-unknown",
  "role-disabled",
  "role-not-allowed",
  "preset-mismatch",
  "preset-disabled",
  "plugin-unregistered",
  "plugin-disabled",
  "workspace-unknown",
  "workspace-disabled",
  "workspace-role-denied",
  "memory-pack-required",
  "memory-scope-mismatch",
  "approval-required",
  "approval-denied",
  "approval-pending",
  "concurrency-limit",
  "deadline-exceeds-preset",
  "budget-exceeds-preset",
  "parent-not-found",
  "parent-not-terminal",
  "dependency-not-satisfied",
  "invalid-parent-run",
  "run-not-found",
  "run-not-cancellable",
  "result-not-ready",
  "result-not-available",
  "adapter-start-failed",
  "adapter-timeout",
  "adapter-cancel-failed",
  "invalid-worker-result",
  "cleanup-failed",
  "session-init-blocked",
  "ledger-integrity",
  "internal-error"
] as const;

export type FleetErrorCode = (typeof FLEET_ERROR_CODES)[number];

export type ErrorDetailValue = string | number | boolean | null;
export type ErrorDetails = Record<string, ErrorDetailValue>;

export interface FleetErrorShape {
  code: FleetErrorCode;
  message: string;
  details?: ErrorDetails;
}

export class FleetPolicyError extends Error {
  code: FleetErrorCode;
  details: ErrorDetails | undefined;

  constructor(code: FleetErrorCode, message: string, details?: ErrorDetails) {
    super(message);
    this.name = "FleetPolicyError";
    this.code = code;
    this.details = details;
  }
}

export function fleetError(
  code: FleetErrorCode,
  message: string,
  details?: ErrorDetails
): FleetErrorShape {
  const error: FleetErrorShape = { code, message };
  if (details !== undefined) {
    error.details = details;
  }
  return error;
}

export function asFleetPolicyError(error: unknown): FleetPolicyError | null {
  if (error instanceof FleetPolicyError) {
    return error;
  }
  return null;
}

export function safeErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.length > 0) {
    return error.message.slice(0, 512);
  }
  return "unexpected error";
}
