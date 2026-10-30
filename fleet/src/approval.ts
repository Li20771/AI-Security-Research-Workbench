import type { RoleId, WorkflowId } from "./contract.ts";

export type ApprovalDecision = "approved" | "pending" | "denied";

export interface ApprovalContext {
  workflow_id: WorkflowId;
  task_id: string;
  workspace_id: string;
  role: RoleId;
}

export interface ApprovalVerifier {
  verify(approvalRef: string, context: ApprovalContext): ApprovalDecision;
  consume(approvalRef: string, runId: string): boolean;
}

export interface ApprovalGrant {
  approval_ref: string;
  workflow_id: WorkflowId;
  task_id: string;
  workspace_id: string;
  role: RoleId;
  state: "approved" | "pending";
  single_use?: boolean;
}

interface StoredGrant extends ApprovalGrant {
  consumed_by: string | null;
}

export class FakeApprovalRegistry implements ApprovalVerifier {
  #grants = new Map<string, StoredGrant>();

  register(grant: ApprovalGrant): void {
    this.#grants.set(grant.approval_ref, {
      ...grant,
      single_use: grant.single_use ?? true,
      consumed_by: null
    });
  }

  setState(approvalRef: string, state: "approved" | "pending"): boolean {
    const grant = this.#grants.get(approvalRef);
    if (grant === undefined) {
      return false;
    }
    grant.state = state;
    return true;
  }

  verify(approvalRef: string, context: ApprovalContext): ApprovalDecision {
    const grant = this.#grants.get(approvalRef);
    if (grant === undefined) {
      return "denied";
    }
    if (grant.consumed_by !== null) {
      return "denied";
    }
    if (
      grant.workflow_id !== context.workflow_id ||
      grant.task_id !== context.task_id ||
      grant.workspace_id !== context.workspace_id ||
      grant.role !== context.role
    ) {
      return "denied";
    }
    return grant.state;
  }

  consume(approvalRef: string, runId: string): boolean {
    const grant = this.#grants.get(approvalRef);
    if (grant === undefined || grant.state !== "approved" || grant.consumed_by !== null) {
      return false;
    }
    if (grant.single_use === false) {
      return true;
    }
    grant.consumed_by = runId;
    return true;
  }
}

export class DenyAllApprovalVerifier implements ApprovalVerifier {
  verify(_approvalRef: string, _context: ApprovalContext): ApprovalDecision {
    return "denied";
  }

  consume(_approvalRef: string, _runId: string): boolean {
    return false;
  }
}
