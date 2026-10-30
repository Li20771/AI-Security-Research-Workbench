import { deepFreeze } from "./canonical-json.ts";
import type { RunStatus } from "./contract.ts";
import { FleetPolicyError } from "./errors.ts";

export const RUN_TRANSITIONS: Readonly<Record<RunStatus, readonly RunStatus[]>> = deepFreeze({
  created: ["validated", "blocked", "cancelled"],
  validated: ["queued", "waiting_approval", "completed", "blocked", "cancelled"],
  queued: ["running", "waiting_approval", "cancelled", "blocked"],
  waiting_approval: ["queued", "running", "cancelled", "blocked"],
  running: ["completed", "failed", "blocked", "timed_out", "cancelled"],
  completed: [],
  failed: [],
  blocked: [],
  timed_out: [],
  cancelled: []
});

export function canTransition(from: RunStatus, to: RunStatus): boolean {
  return RUN_TRANSITIONS[from].includes(to);
}

export function assertTransition(from: RunStatus, to: RunStatus): void {
  if (!canTransition(from, to)) {
    throw new FleetPolicyError(
      "internal-error",
      `invalid run state transition: ${from} -> ${to}`,
      { from, to }
    );
  }
}
