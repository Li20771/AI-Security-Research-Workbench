import {
  compactObject,
  isPlainObject,
  jsonByteLength,
  sha256OfJson
} from "./canonical-json.ts";
import type {
  Budget,
  CleanupState,
  RoleId,
  RunLedgerEventType,
  RunStatus,
  TerminalStatus,
  WorkflowId
} from "./contract.ts";
import { CONTRACT_VERSION, isTerminalStatus, isWorkflowId } from "./contract.ts";
import type {
  CancelResponse,
  ResultResponse,
  RunSummary,
  StatusQuery,
  StatusResponse,
  SubmitRequest,
  SubmitResponse
} from "./api-types.ts";
import type { ApprovalContext, ApprovalVerifier } from "./approval.ts";
import { DenyAllApprovalVerifier } from "./approval.ts";
import type { TrustedBinding } from "./binding.ts";
import {
  MEMORY_PACK_ID_PATTERN,
  RUN_ID_PATTERN,
  SHA256_PATTERN,
  TASK_ID_PATTERN,
  TrustedBindingIssuer
} from "./binding.ts";
import type { ErrorDetails, FleetErrorCode } from "./errors.ts";
import {
  FleetPolicyError,
  fleetError,
  safeErrorMessage
} from "./errors.ts";
import type { IdGenerator } from "./ids.ts";
import { UuidIdGenerator, resultRefFor } from "./ids.ts";
import type { RunLedger, RunLedgerEvent } from "./ledger.ts";
import { validateSubmitRequest, validateStatusQuery } from "./request-validation.ts";
import type { RolePreset } from "./registries/roles.ts";
import { getPresetByIdVersion, getRolePreset } from "./registries/roles.ts";
import type { WorkflowTask } from "./registries/workflows.ts";
import { getTask, getWorkflow } from "./registries/workflows.ts";
import { getWorkspace } from "./registries/workspaces.ts";
import { validatePluginManifest } from "./registries/plugins.ts";
import type { ResultStore, StoredResult } from "./result-store.ts";
import { assertTransition } from "./state-machine.ts";
import type { Clock } from "./time.ts";
import { nowIso, SystemClock } from "./time.ts";
import type {
  DshCancelResult,
  DshCloseResult,
  DshRuntimeAdapter,
  DshSessionHandle,
  DshSessionRequest
} from "./adapters/dsh-adapter.ts";
import { DshAdapterError, DshCancelledError } from "./adapters/dsh-adapter.ts";
import { WorkspaceLifecycleHooks } from "./adapters/lifecycle-hooks.ts";
import type { WorkerResultEnvelope } from "./worker-result.ts";
import {
  artifactsForEnvelope,
  createWorkerResultEnvelope
} from "./worker-result.ts";

export interface FleetControllerDeps {
  bindingIssuer: TrustedBindingIssuer;
  ledger: RunLedger;
  adapter: DshRuntimeAdapter;
  resultStore: ResultStore;
  approvalVerifier?: ApprovalVerifier;
  clock?: Clock;
  idGenerator?: IdGenerator;
  workspaceRoots?: Readonly<Record<string, string>>;
}

export interface RunRecord {
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
  tool_profile: string;
  memory_pack_snapshot_id: string | null;
  memory_pack_snapshot_hash: string | null;
  approval_ref: string | null;
  base_sha: string | null;
  deadline_ms: number;
  budget: Budget;
  input_sha256: string;
  status: RunStatus;
  session_id: string | null;
  result_ref: string | null;
  result_sha256: string | null;
  cleanup_state: CleanupState | null;
  reason_code: string | null;
  reason: string | null;
  created_at: string;
  updated_at: string;
  worker: boolean;
  adapter_id: string;
}

interface ActiveRun {
  run: RunRecord;
  request: SubmitRequest;
  preset: RolePreset;
  task: WorkflowTask;
  binding: TrustedBinding;
  handle: DshSessionHandle | null;
  timer: ReturnType<typeof setTimeout> | null;
  settled: boolean;
  cancelRequested: boolean;
  timedOut: boolean;
  slotReserved: boolean;
  waiters: Set<(run: RunRecord) => void>;
}

interface PendingApprovalRun {
  request: SubmitRequest;
  preset: RolePreset;
  task: WorkflowTask;
  binding: TrustedBinding;
}

interface CleanupOutcome {
  state: CleanupState;
  detail: string | null;
}

export interface ReconcileReport {
  reconciled: number;
  run_ids: string[];
}

export interface ApprovalGrantResult {
  ok: boolean;
  code?: FleetErrorCode;
  message?: string;
  status?: "queued";
}

const TERMINAL_EVENT: Readonly<Record<TerminalStatus, RunLedgerEventType>> = {
  completed: "run.completed",
  failed: "run.failed",
  blocked: "run.blocked",
  timed_out: "run.timed_out",
  cancelled: "run.cancelled"
};

const DEFAULT_WORKSPACE_ROOTS: Readonly<Record<string, string>> = {
  ws_a: "D:\\lab\\ws_a",
  ws_b: "D:\\lab\\ws_b",
  ws_disabled: "D:\\lab\\ws_disabled"
};

function minBudget(left: Budget, right: Budget): Budget {
  return {
    max_tokens: Math.min(left.max_tokens, right.max_tokens),
    max_cost_usd: Math.min(left.max_cost_usd, right.max_cost_usd)
  };
}

function terminalEventFor(status: TerminalStatus): RunLedgerEventType {
  return TERMINAL_EVENT[status];
}

function currentRunStatus(run: RunRecord): RunStatus {
  return run.status;
}

export class FleetController {
  #issuer: TrustedBindingIssuer;
  #ledger: RunLedger;
  #adapter: DshRuntimeAdapter;
  #resultStore: ResultStore;
  #approval: ApprovalVerifier;
  #clock: Clock;
  #ids: IdGenerator;
  #roots: Readonly<Record<string, string>>;
  #hooks: WorkspaceLifecycleHooks;
  #runs = new Map<string, RunRecord>();
  #active = new Map<string, ActiveRun>();
  #pendingApproval = new Map<string, PendingApprovalRun>();
  #concurrency = new Map<string, number>();
  #waiters = new Map<string, Set<(run: RunRecord) => void>>();

  constructor(deps: FleetControllerDeps) {
    this.#issuer = deps.bindingIssuer;
    this.#ledger = deps.ledger;
    this.#adapter = deps.adapter;
    this.#resultStore = deps.resultStore;
    this.#approval = deps.approvalVerifier ?? new DenyAllApprovalVerifier();
    this.#clock = deps.clock ?? new SystemClock();
    this.#ids = deps.idGenerator ?? new UuidIdGenerator();
    this.#roots = deps.workspaceRoots ?? DEFAULT_WORKSPACE_ROOTS;
    this.#hooks = new WorkspaceLifecycleHooks(this.#roots);
  }

  submit(request: unknown, binding: unknown): SubmitResponse {
    const requestId = this.#ids.requestId();
    if (!this.#issuer.verify(binding)) {
      this.#recordRejection(null, request, requestId, "untrusted-binding");
      return this.#submitError(
        "untrusted-binding",
        "binding was not issued by the trusted host"
      );
    }

    let inputSha256: string | undefined;
    try {
      const validated = validateSubmitRequest(request);
      if (!validated.ok) {
        this.#recordRejection(binding, request, requestId, validated.code);
        return this.#submitError(validated.code, validated.message);
      }
      const req = validated.value;
      inputSha256 = sha256OfJson(req.input);

      const workflow = getWorkflow(req.workflow_id);
      if (workflow === undefined) {
        return this.#reject(binding, request, requestId, inputSha256, "workflow-unknown", "workflow is not registered");
      }
      if (!workflow.enabled) {
        return this.#reject(binding, request, requestId, inputSha256, "workflow-disabled", "workflow is disabled");
      }
      const task = getTask(workflow, req.task_id);
      if (task === undefined) {
        return this.#reject(binding, request, requestId, inputSha256, "task-unknown", "task is not registered in this workflow");
      }
      if (!task.allowed_roles.includes(binding.role)) {
        return this.#reject(binding, request, requestId, inputSha256, "role-not-allowed", "role is not allowed for this task");
      }
      const preset = getRolePreset(binding.role);
      if (preset === undefined) {
        return this.#reject(binding, request, requestId, inputSha256, "role-unknown", "role is not registered");
      }
      if (!preset.enabled) {
        return this.#reject(binding, request, requestId, inputSha256, "role-disabled", "role is disabled");
      }
      const boundPreset = getPresetByIdVersion(binding.preset_id, binding.preset_version);
      if (
        boundPreset === undefined ||
        boundPreset.role !== binding.role ||
        boundPreset.preset_id !== preset.preset_id ||
        boundPreset.preset_version !== preset.preset_version
      ) {
        return this.#reject(binding, request, requestId, inputSha256, "preset-mismatch", "binding preset does not match the role");
      }
      if (binding.tool_profile !== preset.tool_profile) {
        return this.#reject(binding, request, requestId, inputSha256, "preset-mismatch", "binding tool profile does not match the preset");
      }
      const pluginValidation = validatePluginManifest(preset.plugin_manifest);
      if (!pluginValidation.ok) {
        return this.#reject(
          binding,
          request,
          requestId,
          inputSha256,
          pluginValidation.code ?? "plugin-unregistered",
          pluginValidation.message ?? "plugin manifest is invalid"
        );
      }
      const workspace = getWorkspace(binding.workspace_id);
      if (workspace === undefined) {
        return this.#reject(binding, request, requestId, inputSha256, "workspace-unknown", "workspace is not registered");
      }
      if (!workspace.enabled) {
        return this.#reject(binding, request, requestId, inputSha256, "workspace-disabled", "workspace is disabled");
      }
      if (!workspace.allowed_roles.includes(binding.role)) {
        return this.#reject(binding, request, requestId, inputSha256, "workspace-role-denied", "role is not allowed in this workspace");
      }
      if (preset.worker) {
        if (binding.memory_pack === null) {
          return this.#reject(binding, request, requestId, inputSha256, "memory-pack-required", "worker runs require a read-only memory pack");
        }
        if (!this.#memoryPackMatchesBinding(binding)) {
          return this.#reject(binding, request, requestId, inputSha256, "memory-scope-mismatch", "memory pack does not match the binding scope");
        }
      }

      const requiresApproval = task.requires_approval || preset.requires_approval;
      let approvalDecision: "approved" | "pending" | "denied" = "approved";
      const approvalContext: ApprovalContext = {
        workflow_id: workflow.workflow_id,
        task_id: task.task_id,
        workspace_id: binding.workspace_id,
        role: binding.role
      };
      if (requiresApproval) {
        if (binding.approval_ref === null) {
          return this.#reject(binding, request, requestId, inputSha256, "approval-required", "this task requires an approval reference");
        }
        approvalDecision = this.#approval.verify(binding.approval_ref, approvalContext);
        if (approvalDecision === "denied") {
          return this.#reject(binding, request, requestId, inputSha256, "approval-denied", "approval was denied or does not match this task");
        }
      }

      const deadlineMs =
        req.deadline_ms ??
        Math.min(preset.default_timeout_ms, binding.max_timeout_ms);
      if (
        deadlineMs > preset.max_timeout_ms ||
        deadlineMs > binding.max_timeout_ms ||
        deadlineMs < 1
      ) {
        return this.#reject(binding, request, requestId, inputSha256, "deadline-exceeds-preset", "deadline exceeds the preset or binding limit");
      }
      const budget =
        req.budget ?? minBudget(preset.max_budget, binding.max_budget);
      if (
        budget.max_tokens > preset.max_budget.max_tokens ||
        budget.max_cost_usd > preset.max_budget.max_cost_usd ||
        budget.max_tokens > binding.max_budget.max_tokens ||
        budget.max_cost_usd > binding.max_budget.max_cost_usd
      ) {
        return this.#reject(binding, request, requestId, inputSha256, "budget-exceeds-preset", "budget exceeds the preset or binding limit");
      }

      if (preset.worker && this.#activeCount(preset.preset_id) >= preset.max_concurrent) {
        return this.#reject(binding, request, requestId, inputSha256, "concurrency-limit", "preset concurrency limit is full");
      }

      const parent = this.#validateParent(req, task, binding);
      if (parent.ok === false) {
        return this.#reject(binding, request, requestId, inputSha256, parent.code, parent.message);
      }

      const runId = this.#ids.runId();
      if (requiresApproval && approvalDecision === "approved" && binding.approval_ref !== null) {
        if (!this.#approval.consume(binding.approval_ref, runId)) {
          return this.#reject(binding, request, requestId, inputSha256, "approval-denied", "approval could not be consumed");
        }
      }

      const now = nowIso(this.#clock);
      const run: RunRecord = {
        run_id: runId,
        workflow_instance_id: binding.workflow_instance_id,
        workflow_id: workflow.workflow_id,
        task_id: task.task_id,
        parent_run_id: req.parent_run_id,
        role: binding.role,
        preset_id: preset.preset_id,
        preset_version: preset.preset_version,
        workspace_id: binding.workspace_id,
        episode_id: binding.episode_id,
        tool_profile: binding.tool_profile,
        memory_pack_snapshot_id: binding.memory_pack?.snapshot_id ?? null,
        memory_pack_snapshot_hash: binding.memory_pack?.snapshot_hash ?? null,
        approval_ref: binding.approval_ref,
        base_sha: binding.base_sha,
        deadline_ms: deadlineMs,
        budget,
        input_sha256: inputSha256,
        status: "created",
        session_id: null,
        result_ref: null,
        result_sha256: null,
        cleanup_state: null,
        reason_code: null,
        reason: null,
        created_at: now,
        updated_at: now,
        worker: task.worker && preset.worker,
        adapter_id: this.#adapter.adapter_id
      };

      this.#runs.set(runId, run);
      this.#appendRunEvent(run, "run.created", {
        status: "created",
        request_id: requestId,
        input_sha256: inputSha256,
        workflow_id: run.workflow_id,
        preset_id: run.preset_id,
        preset_version: run.preset_version,
        workspace_id: run.workspace_id,
        episode_id: run.episode_id,
        base_sha: run.base_sha,
        memory_pack_snapshot_id: run.memory_pack_snapshot_id,
        memory_pack_snapshot_hash: run.memory_pack_snapshot_hash,
        tool_profile: run.tool_profile,
        approval_ref: run.approval_ref,
        deadline_ms: run.deadline_ms,
        budget: run.budget,
        worker: run.worker,
        parent_run_id: run.parent_run_id,
        adapter: run.adapter_id
      });
      this.#transition(run, "validated");
      this.#appendRunEvent(run, "run.validated", { status: "validated" });

      if (!run.worker) {
        this.#finalizeRunRecord(
          run,
          "completed",
          null,
          null,
          { state: "not_needed", detail: null }
        );
        return this.#submitSuccess(run, "completed");
      }

      if (requiresApproval && approvalDecision === "pending") {
        this.#transition(run, "waiting_approval");
        this.#appendRunEvent(run, "run.waiting_approval", {
          status: "waiting_approval",
          approval_ref: run.approval_ref
        });
        this.#pendingApproval.set(runId, { request: req, preset, task, binding });
        return this.#submitSuccess(run, "waiting_approval");
      }

      this.#transition(run, "queued");
      this.#appendRunEvent(run, "run.queued", { status: "queued" });
      this.#startWorker(run, req, preset, task, binding);
      return this.#submitSuccess(run, "queued");
    } catch (error) {
      if (error instanceof FleetPolicyError) {
        return this.#reject(binding, request, requestId, inputSha256, error.code, error.message, error.details);
      }
      return this.#reject(
        binding,
        request,
        requestId,
        inputSha256,
        "internal-error",
        safeErrorMessage(error)
      );
    }
  }

  status(query: unknown, binding: unknown): StatusResponse {
    if (!this.#issuer.verify(binding)) {
      return this.#statusError("untrusted-binding", "binding was not issued by the trusted host");
    }
    const validated = validateStatusQuery(query);
    if (!validated.ok) {
      return this.#statusError(validated.code, validated.message);
    }
    const q = validated.value;
    if (q.run_id !== null) {
      const run = this.#runs.get(q.run_id);
      if (run === undefined || !this.#canAccess(binding, run)) {
        return this.#statusError("run-not-found", "run is not available to this caller");
      }
      return {
        contract_version: CONTRACT_VERSION,
        ok: true,
        operation: "status",
        data: { runs: [this.#summary(run)] }
      };
    }
    const workflowInstanceId = q.workflow_instance_id as string;
    const runs: RunRecord[] = [];
    for (const run of this.#runs.values()) {
      if (run.workflow_instance_id !== workflowInstanceId) {
        continue;
      }
      if (!this.#canAccess(binding, run)) {
        continue;
      }
      if (q.task_id !== null && run.task_id !== q.task_id) {
        continue;
      }
      runs.push(run);
    }
    if (runs.length === 0) {
      return this.#statusError("run-not-found", "workflow instance is not available to this caller");
    }
    return {
      contract_version: CONTRACT_VERSION,
      ok: true,
      operation: "status",
      data: { runs: runs.slice(0, 100).map((run) => this.#summary(run)) }
    };
  }

  result(runId: unknown, binding: unknown): ResultResponse {
    if (!this.#issuer.verify(binding)) {
      return this.#resultError("untrusted-binding", "binding was not issued by the trusted host");
    }
    if (typeof runId !== "string" || !RUN_ID_PATTERN.test(runId)) {
      return this.#resultError("invalid-request", "run_id is invalid");
    }
    const run = this.#runs.get(runId);
    if (run === undefined || !this.#canAccess(binding, run)) {
      return this.#resultError("run-not-found", "run is not available to this caller");
    }
    if (!isTerminalStatus(run.status)) {
      return this.#resultError("result-not-ready", "run is not terminal");
    }
    if (run.status !== "completed" || run.result_ref === null || run.result_sha256 === null) {
      return this.#resultError("result-not-available", "run has no completed worker result");
    }
    const stored = this.#resultStore.get(run.result_ref);
    if (stored === undefined) {
      return this.#resultError("result-not-available", "result store does not contain this result");
    }
    return {
      contract_version: CONTRACT_VERSION,
      ok: true,
      operation: "result",
      data: {
        run_id: run.run_id,
        status: "completed",
        result_ref: run.result_ref,
        result_sha256: run.result_sha256,
        untrusted: true,
        admission: "none",
        evidence: false,
        result: stored.envelope,
        artifacts: artifactsForEnvelope(stored.envelope)
      }
    };
  }

  async cancel(runId: unknown, binding: unknown): Promise<CancelResponse> {
    if (!this.#issuer.verify(binding)) {
      return this.#cancelError("untrusted-binding", "binding was not issued by the trusted host");
    }
    if (typeof runId !== "string" || !RUN_ID_PATTERN.test(runId)) {
      return this.#cancelError("invalid-request", "run_id is invalid");
    }
    const run = this.#runs.get(runId);
    if (run === undefined || !this.#canAccess(binding, run)) {
      return this.#cancelError("run-not-found", "run is not available to this caller");
    }
    if (isTerminalStatus(run.status)) {
      return this.#cancelError("run-not-cancellable", "run is already terminal");
    }
    const active = this.#active.get(runId);
    if (active !== undefined) {
      active.cancelRequested = true;
      const cleanup = await this.#cleanup(active, "operator-cancel");
      const status: "cancelled" | "blocked" =
        cleanup.state === "succeeded" || cleanup.state === "not_needed" ? "cancelled" : "blocked";
      await this.#finalize(
        active,
        status,
        status === "cancelled" ? "cancelled-by-request" : "adapter-cancel-failed",
        status === "cancelled" ? "cancelled by request" : "runtime cleanup failed during cancel",
        undefined,
        cleanup
      );
      this.#pendingApproval.delete(runId);
      const finalStatus = currentRunStatus(run);
      if (finalStatus !== "cancelled" && finalStatus !== "blocked") {
        return this.#cancelError("run-not-cancellable", "run reached a different terminal state before cancellation completed");
      }
      return {
        contract_version: CONTRACT_VERSION,
        ok: true,
        operation: "cancel",
        data: {
          run_id: runId,
          status: finalStatus,
          cleanup: { state: cleanup.state, detail: cleanup.detail }
        }
      };
    }
    if (
      run.status === "queued" ||
      run.status === "waiting_approval" ||
      run.status === "created" ||
      run.status === "validated"
    ) {
      const cleanup: CleanupOutcome = { state: "not_needed", detail: null };
      this.#pendingApproval.delete(runId);
      this.#finalizeRunRecord(
        run,
        "cancelled",
        "cancelled-before-start",
        "cancelled before runtime start",
        cleanup
      );
      const finalStatus = currentRunStatus(run);
      if (finalStatus !== "cancelled") {
        return this.#cancelError("run-not-cancellable", "run reached a different terminal state before cancellation completed");
      }
      return {
        contract_version: CONTRACT_VERSION,
        ok: true,
        operation: "cancel",
        data: {
          run_id: runId,
          status: "cancelled",
          cleanup: { state: cleanup.state, detail: cleanup.detail }
        }
      };
    }
    const cleanup: CleanupOutcome = { state: "unknown", detail: "runtime state is unknown" };
    this.#finalizeRunRecord(
      run,
      "blocked",
      "adapter-cancel-failed",
      "run was not active and runtime state could not be confirmed",
      cleanup
    );
    const finalStatus = currentRunStatus(run);
    if (finalStatus !== "blocked") {
      return this.#cancelError("run-not-cancellable", "run reached a different terminal state before cancellation completed");
    }
    return {
      contract_version: CONTRACT_VERSION,
      ok: true,
      operation: "cancel",
      data: {
        run_id: runId,
        status: "blocked",
        cleanup: { state: cleanup.state, detail: cleanup.detail }
      }
    };
  }

  async grantApproval(runId: string, approvalRef: string): Promise<ApprovalGrantResult> {
    const run = this.#runs.get(runId);
    if (run === undefined) {
      return { ok: false, code: "run-not-found", message: "run is not registered" };
    }
    if (run.status !== "waiting_approval") {
      return { ok: false, code: "run-not-cancellable", message: "run is not waiting for approval" };
    }
    if (run.approval_ref !== approvalRef) {
      return { ok: false, code: "approval-denied", message: "approval reference does not match the run" };
    }
    const pending = this.#pendingApproval.get(runId);
    if (pending === undefined) {
      return { ok: false, code: "internal-error", message: "pending approval context is missing" };
    }
    const context: ApprovalContext = {
      workflow_id: run.workflow_id,
      task_id: run.task_id,
      workspace_id: run.workspace_id,
      role: run.role
    };
    const decision = this.#approval.verify(approvalRef, context);
    if (decision !== "approved") {
      return { ok: false, code: "approval-denied", message: "approval is not approved" };
    }
    if (!this.#approval.consume(approvalRef, runId)) {
      return { ok: false, code: "approval-denied", message: "approval could not be consumed" };
    }
    if (this.#activeCount(pending.preset.preset_id) >= pending.preset.max_concurrent) {
      return { ok: false, code: "concurrency-limit", message: "preset concurrency limit is full" };
    }
    this.#pendingApproval.delete(runId);
    this.#transition(run, "queued");
    this.#appendRunEvent(run, "run.approved", {
      status: "queued",
      approval_ref: approvalRef
    });
    this.#appendRunEvent(run, "run.queued", { status: "queued" });
    this.#startWorker(run, pending.request, pending.preset, pending.task, pending.binding);
    return { ok: true, status: "queued" };
  }

  reconcile(): ReconcileReport {
    const verification = this.#ledger.verify();
    if (!verification.ok) {
      throw new FleetPolicyError("ledger-integrity", verification.error ?? "ledger is invalid", {
        at_seq: verification.at_seq ?? 0
      });
    }
    const events = this.#ledger.readAll();
    const created = new Map<string, RunLedgerEvent>();
    const lastStatus = new Map<string, RunLedgerEvent>();
    const sessionIds = new Map<string, string>();
    for (const event of events) {
      if (event.run_id === null) {
        continue;
      }
      if (event.type === "run.created" && !created.has(event.run_id)) {
        created.set(event.run_id, event);
      }
      if (event.type === "run.session_opened" && typeof event.data.session_id === "string") {
        sessionIds.set(event.run_id, event.data.session_id);
      }
      if (
        event.type === "run.created" ||
        event.type === "run.validated" ||
        event.type === "run.queued" ||
        event.type === "run.waiting_approval" ||
        event.type === "run.approved" ||
        event.type === "run.session_opened" ||
        event.type === "run.started" ||
        event.type === "run.completed" ||
        event.type === "run.failed" ||
        event.type === "run.blocked" ||
        event.type === "run.timed_out" ||
        event.type === "run.cancelled"
      ) {
        lastStatus.set(event.run_id, event);
      }
    }

    const reconciled: string[] = [];
    for (const [runId, last] of lastStatus) {
      const existing = this.#runs.get(runId);
      if (existing !== undefined && isTerminalStatus(existing.status)) {
        continue;
      }
      if (this.#active.has(runId)) {
        continue;
      }
      if (
        last.type === "run.completed" ||
        last.type === "run.failed" ||
        last.type === "run.blocked" ||
        last.type === "run.timed_out" ||
        last.type === "run.cancelled"
      ) {
        continue;
      }
      const createdEvent = created.get(runId);
      if (createdEvent === undefined) {
        continue;
      }
      const run = this.#reconstructRun(createdEvent, last, sessionIds.get(runId) ?? null);
      if (run === null) {
        continue;
      }
      this.#runs.set(runId, run);
      this.#appendRunEvent(run, "run.reconciled", {
        reason_code: "orphaned-after-restart",
        reconciled_from_seq: last.seq,
        cleanup_state: "unknown"
      });
      this.#finalizeRunRecord(
        run,
        "blocked",
        "orphaned-after-restart",
        "run was non-terminal at restart; runtime state is unknown",
        { state: "unknown", detail: "runtime state could not be confirmed after restart" }
      );
      reconciled.push(runId);
    }
    return { reconciled: reconciled.length, run_ids: reconciled };
  }

  waitForRun(runId: string, timeoutMs: number = 5000): Promise<RunRecord> {
    const run = this.#runs.get(runId);
    if (run === undefined) {
      return Promise.reject(new Error("run-not-found"));
    }
    if (isTerminalStatus(run.status)) {
      return Promise.resolve(run);
    }
    return new Promise<RunRecord>((resolve, reject) => {
      const waiter = (terminalRun: RunRecord): void => {
        clearTimeout(timer);
        resolve(terminalRun);
      };
      const timer = setTimeout(() => {
        const set = this.#waiters.get(runId);
        set?.delete(waiter);
        reject(new Error("wait-timeout"));
      }, timeoutMs);
      let set = this.#waiters.get(runId);
      if (set === undefined) {
        set = new Set();
        this.#waiters.set(runId, set);
      }
      set.add(waiter);
    });
  }

  async drain(timeoutMs: number = 5000): Promise<void> {
    const ids = [...this.#active.keys()];
    await Promise.all(ids.map((runId) => this.waitForRun(runId, timeoutMs)));
  }

  #validateParent(
    request: SubmitRequest,
    task: WorkflowTask,
    binding: TrustedBinding
  ):
    | { ok: true; parent: RunRecord | null }
    | { ok: false; code: FleetErrorCode; message: string } {
    if (request.parent_run_id === null) {
      if (task.depends_on.length > 0) {
        return {
          ok: false,
          code: "dependency-not-satisfied",
          message: "task dependencies require a parent run"
        };
      }
      return { ok: true, parent: null };
    }
    const parent = this.#runs.get(request.parent_run_id);
    if (parent === undefined || parent.workspace_id !== binding.workspace_id) {
      return { ok: false, code: "parent-not-found", message: "parent run is not available" };
    }
    if (parent.workflow_instance_id !== binding.workflow_instance_id) {
      return { ok: false, code: "invalid-parent-run", message: "parent run belongs to another workflow instance" };
    }
    if (!isTerminalStatus(parent.status)) {
      return { ok: false, code: "parent-not-terminal", message: "parent run is not terminal" };
    }
    if (task.depends_on.includes(parent.task_id)) {
      if (parent.status !== "completed") {
        return {
          ok: false,
          code: "dependency-not-satisfied",
          message: "dependency parent did not complete"
        };
      }
      return { ok: true, parent };
    }
    if (parent.task_id === task.task_id) {
      if (parent.role !== binding.role) {
        return { ok: false, code: "invalid-parent-run", message: "retry parent belongs to another role" };
      }
      return { ok: true, parent };
    }
    return { ok: false, code: "invalid-parent-run", message: "parent run is not a dependency or retry source" };
  }

  #memoryPackMatchesBinding(binding: TrustedBinding): boolean {
    const pack = binding.memory_pack;
    if (pack === null) {
      return false;
    }
    if (!MEMORY_PACK_ID_PATTERN.test(pack.snapshot_id)) {
      return false;
    }
    if (!SHA256_PATTERN.test(pack.snapshot_hash)) {
      return false;
    }
    if (pack.workspace_id !== binding.workspace_id) {
      return false;
    }
    if (
      binding.episode_id !== null &&
      pack.episode_id !== null &&
      pack.episode_id !== binding.episode_id
    ) {
      return false;
    }
    return true;
  }

  #startWorker(
    run: RunRecord,
    request: SubmitRequest,
    preset: RolePreset,
    task: WorkflowTask,
    binding: TrustedBinding
  ): void {
    const active: ActiveRun = {
      run,
      request,
      preset,
      task,
      binding,
      handle: null,
      timer: null,
      settled: false,
      cancelRequested: false,
      timedOut: false,
      slotReserved: false,
      waiters: new Set()
    };
    this.#active.set(run.run_id, active);
    this.#reserveSlot(preset.preset_id);
    active.slotReserved = true;
    void this.#execute(active);
  }

  async #execute(active: ActiveRun): Promise<void> {
    const { run, preset, binding, request } = active;
    try {
      this.#transition(run, "running");
      const workspaceRoot = this.#roots[run.workspace_id] ?? `workspace://${run.workspace_id}`;
      const sessionRequest: DshSessionRequest = {
        run_id: run.run_id,
        role: run.role,
        preset_id: run.preset_id,
        preset_version: run.preset_version,
        dsh_profile: preset.dsh_profile,
        plugin_manifest: preset.plugin_manifest,
        tool_profile: preset.tool_profile,
        mcp_server: preset.mcp_server,
        workspace_id: run.workspace_id,
        episode_id: run.episode_id,
        workspace_root: workspaceRoot,
        working_directory: workspaceRoot,
        memory_pack: binding.memory_pack,
        env_allowlist: preset.env_allowlist,
        lifecycle_hooks: this.#hooks
      };
      const handle = await this.#adapter.openSession(sessionRequest);
      if (active.settled) {
        await this.#bestEffortClose(handle);
        return;
      }
      active.handle = handle;
      run.session_id = handle.session_id;
      this.#appendRunEvent(run, "run.session_opened", { session_id: handle.session_id });
      this.#appendRunEvent(run, "run.started", {
        status: "running",
        session_id: handle.session_id
      });
      active.timer = setTimeout(() => {
        void this.#handleTimeout(active);
      }, run.deadline_ms);

      const output = await this.#adapter.runSession(handle, {
        input_sha256: run.input_sha256,
        input: request.input,
        deadline_ms: run.deadline_ms,
        budget: run.budget
      });
      if (active.settled) {
        return;
      }
      const envelope = createWorkerResultEnvelope(run.run_id, run.role, output, this.#clock);
      if (active.settled) {
        return;
      }
      const cleanup = await this.#closeCompleted(active);
      if (active.settled) {
        return;
      }
      if (cleanup.state !== "succeeded") {
        await this.#finalize(
          active,
          "blocked",
          "cleanup-failed",
          "runtime cleanup failed after completion",
          undefined,
          cleanup
        );
        return;
      }
      const stored = this.#resultStore.put(envelope);
      await this.#finalize(active, "completed", null, null, stored, cleanup);
    } catch (error) {
      if (active.settled) {
        return;
      }
      // The timeout/cancel handler owns cleanup and the terminal transition.
      // A DshCancelledError here is the expected consequence of that handler
      // rejecting the pending runSession promise; do not clean up twice.
      if (active.cancelRequested || active.timedOut) {
        return;
      }
      const policy = error instanceof FleetPolicyError ? error : null;
      if (policy !== null && policy.code === "invalid-worker-result") {
        const cleanup = await this.#cleanup(active, "invalid-worker-result");
        await this.#finalize(
          active,
          cleanup.state === "succeeded" || cleanup.state === "not_needed" ? "failed" : "blocked",
          "invalid-worker-result",
          "worker output failed schema or role validation",
          undefined,
          cleanup
        );
        return;
      }
      if (error instanceof DshCancelledError) {
        const cleanup = await this.#cleanup(active, "cancelled");
        const status: TerminalStatus =
          active.timedOut
            ? cleanup.state === "succeeded" || cleanup.state === "not_needed"
              ? "timed_out"
              : "blocked"
            : cleanup.state === "succeeded" || cleanup.state === "not_needed"
              ? "cancelled"
              : "blocked";
        await this.#finalize(
          active,
          status,
          status === "timed_out" ? "adapter-timeout" : status === "cancelled" ? "cancelled-by-request" : "adapter-cancel-failed",
          status === "timed_out" ? "worker deadline exceeded" : "worker was cancelled",
          undefined,
          cleanup
        );
        return;
      }
      const hadHandle = active.handle !== null;
      const cleanup = await this.#cleanup(active, "failure");
      const adapterError = error instanceof DshAdapterError ? error : null;
      const code: FleetErrorCode =
        adapterError?.code === "session-init-blocked"
          ? "session-init-blocked"
          : !hadHandle
            ? "adapter-start-failed"
            : "internal-error";
      await this.#finalize(
        active,
        cleanup.state === "succeeded" || cleanup.state === "not_needed" ? "failed" : "blocked",
        code,
        safeErrorMessage(error),
        undefined,
        cleanup
      );
    }
  }

  async #handleTimeout(active: ActiveRun): Promise<void> {
    if (active.settled) {
      return;
    }
    active.timedOut = true;
    const cleanup = await this.#cleanup(active, "timeout");
    if (active.settled) {
      return;
    }
    const status: TerminalStatus =
      cleanup.state === "succeeded" || cleanup.state === "not_needed" ? "timed_out" : "blocked";
    await this.#finalize(
      active,
      status,
      status === "timed_out" ? "adapter-timeout" : "adapter-cancel-failed",
      status === "timed_out" ? "worker deadline exceeded" : "timeout cleanup failed",
      undefined,
      cleanup
    );
  }

  async #cleanup(active: ActiveRun, reason: string): Promise<CleanupOutcome> {
    const handle = active.handle;
    if (handle === null) {
      return { state: "not_needed", detail: null };
    }
    let cancelOk: boolean | null = null;
    let cancelDetail: string | null = null;
    try {
      const cancel: DshCancelResult = await this.#adapter.cancelSession(handle, reason);
      cancelOk = cancel.cleaned;
      cancelDetail = cancel.detail ?? null;
    } catch {
      cancelOk = null;
      cancelDetail = "cancel-error";
    }
    let closeOk: boolean | null = null;
    let closeDetail: string | null = null;
    try {
      const close: DshCloseResult = await this.#adapter.closeSession(handle);
      closeOk = close.closed;
      closeDetail = close.detail ?? null;
    } catch {
      closeOk = null;
      closeDetail = "close-error";
    }
    active.handle = null;
    if (closeOk === false || cancelOk === false) {
      return { state: "failed", detail: closeDetail ?? cancelDetail };
    }
    if (cancelOk === true && closeOk === true) {
      return { state: "succeeded", detail: null };
    }
    return { state: "unknown", detail: closeDetail ?? cancelDetail };
  }

  async #closeCompleted(active: ActiveRun): Promise<CleanupOutcome> {
    const handle = active.handle;
    if (handle === null) {
      return { state: "not_needed", detail: null };
    }
    try {
      const close: DshCloseResult = await this.#adapter.closeSession(handle);
      active.handle = null;
      if (close.closed) {
        return { state: "succeeded", detail: null };
      }
      return { state: "failed", detail: close.detail ?? "close returned false" };
    } catch {
      active.handle = null;
      return { state: "unknown", detail: "close-error" };
    }
  }

  async #bestEffortClose(handle: DshSessionHandle): Promise<void> {
    try {
      await this.#adapter.closeSession(handle);
    } catch {
      // Terminal state was already recorded; this is best-effort cleanup only.
    }
  }

  async #finalize(
    active: ActiveRun,
    status: TerminalStatus,
    reasonCode: string | null,
    reason: string | null,
    stored: StoredResult | undefined,
    cleanup: CleanupOutcome
  ): Promise<void> {
    if (active.settled) {
      return;
    }
    active.settled = true;
    if (active.timer !== null) {
      clearTimeout(active.timer);
      active.timer = null;
    }
    this.#releaseSlot(active);
    this.#active.delete(active.run.run_id);
    this.#finalizeRunRecord(active.run, status, reasonCode, reason, cleanup, stored);
  }

  #finalizeRunRecord(
    run: RunRecord,
    status: TerminalStatus,
    reasonCode: string | null,
    reason: string | null,
    cleanup: CleanupOutcome,
    stored?: StoredResult
  ): void {
    if (isTerminalStatus(run.status)) {
      return;
    }
    assertTransition(run.status, status);
    const now = nowIso(this.#clock);
    const durationMs = Math.max(0, Date.parse(now) - Date.parse(run.created_at));
    run.status = status;
    run.updated_at = now;
    run.cleanup_state = cleanup.state;
    run.reason_code = reasonCode;
    run.reason = reason;
    if (stored !== undefined) {
      run.result_ref = stored.result_ref;
      run.result_sha256 = stored.result_sha256;
    }
    this.#appendRunEvent(run, "run.cleanup", {
      cleanup_state: cleanup.state,
      cleanup_detail: cleanup.detail ?? undefined
    });
    const data: Record<string, unknown> = {
      status,
      cleanup_state: cleanup.state,
      duration_ms: durationMs,
      worker: run.worker
    };
    if (reasonCode !== null) {
      data.reason_code = reasonCode;
    }
    if (reason !== null) {
      data.reason = reason;
    }
    if (stored !== undefined) {
      data.result_ref = stored.result_ref;
      data.result_sha256 = stored.result_sha256;
      data.artifact_refs = artifactsForEnvelope(stored.envelope);
      data.output_bytes = jsonByteLength(stored.envelope.payload);
    }
    this.#appendRunEvent(run, terminalEventFor(status), data);
    this.#resolveWaiters(run);
  }

  #appendRunEvent(
    run: RunRecord,
    type: RunLedgerEventType,
    data: Record<string, unknown>
  ): void {
    this.#ledger.append({
      type,
      workflow_instance_id: run.workflow_instance_id,
      run_id: run.run_id,
      task_id: run.task_id,
      role: run.role,
      data: compactObject(data)
    });
  }

  #transition(run: RunRecord, next: RunStatus): void {
    assertTransition(run.status, next);
    run.status = next;
    run.updated_at = nowIso(this.#clock);
  }

  #recordRejection(
    binding: TrustedBinding | null,
    request: unknown,
    requestId: string,
    code: FleetErrorCode,
    inputSha256?: string
  ): void {
    let taskId: string | null = null;
    if (isPlainObject(request) && typeof request.task_id === "string" && TASK_ID_PATTERN.test(request.task_id)) {
      taskId = request.task_id;
    }
    try {
      this.#ledger.append({
        type: "request.rejected",
        workflow_instance_id: binding?.workflow_instance_id ?? null,
        run_id: null,
        task_id: taskId,
        role: binding?.role ?? null,
        data: compactObject({
          request_id: requestId,
          reason_code: code,
          input_sha256: inputSha256
        })
      });
    } catch {
      // The policy refusal remains the response; ledger integrity is checked elsewhere.
    }
  }

  #reject(
    binding: TrustedBinding,
    request: unknown,
    requestId: string,
    inputSha256: string | undefined,
    code: FleetErrorCode,
    message: string,
    details?: ErrorDetails
  ): SubmitResponse {
    this.#recordRejection(binding, request, requestId, code, inputSha256);
    return this.#submitError(code, message, details);
  }

  #submitError(
    code: FleetErrorCode,
    message: string,
    details?: ErrorDetails
  ): SubmitResponse {
    return {
      contract_version: CONTRACT_VERSION,
      ok: false,
      operation: "submit",
      error: fleetError(code, message.slice(0, 512), details)
    };
  }

  #statusError(code: FleetErrorCode, message: string): StatusResponse {
    return {
      contract_version: CONTRACT_VERSION,
      ok: false,
      operation: "status",
      error: fleetError(code, message.slice(0, 512))
    };
  }

  #resultError(code: FleetErrorCode, message: string): ResultResponse {
    return {
      contract_version: CONTRACT_VERSION,
      ok: false,
      operation: "result",
      error: fleetError(code, message.slice(0, 512))
    };
  }

  #cancelError(code: FleetErrorCode, message: string): CancelResponse {
    return {
      contract_version: CONTRACT_VERSION,
      ok: false,
      operation: "cancel",
      error: fleetError(code, message.slice(0, 512))
    };
  }

  #submitSuccess(
    run: RunRecord,
    status: "queued" | "waiting_approval" | "completed"
  ): SubmitResponse {
    return {
      contract_version: CONTRACT_VERSION,
      ok: true,
      operation: "submit",
      data: {
        workflow_instance_id: run.workflow_instance_id,
        run_id: run.run_id,
        status,
        accepted_at: run.created_at
      }
    };
  }

  #summary(run: RunRecord): RunSummary {
    return {
      run_id: run.run_id,
      workflow_instance_id: run.workflow_instance_id,
      workflow_id: run.workflow_id,
      task_id: run.task_id,
      parent_run_id: run.parent_run_id,
      role: run.role,
      preset_id: run.preset_id,
      preset_version: run.preset_version,
      workspace_id: run.workspace_id,
      episode_id: run.episode_id,
      status: run.status,
      created_at: run.created_at,
      updated_at: run.updated_at,
      session_id: run.session_id,
      result_ref: run.result_ref,
      result_sha256: run.result_sha256,
      cleanup_state: run.cleanup_state,
      reason_code: run.reason_code,
      reason: run.reason
    };
  }

  #canAccess(binding: TrustedBinding, run: RunRecord): boolean {
    if (binding.workspace_id !== run.workspace_id) {
      return false;
    }
    if (binding.episode_id !== null && binding.episode_id !== run.episode_id) {
      return false;
    }
    if (binding.role === "orchestrator") {
      return true;
    }
    return binding.role === run.role;
  }

  #activeCount(presetId: string): number {
    return this.#concurrency.get(presetId) ?? 0;
  }

  #reserveSlot(presetId: string): void {
    this.#concurrency.set(presetId, this.#activeCount(presetId) + 1);
  }

  #releaseSlot(active: ActiveRun): void {
    if (!active.slotReserved) {
      return;
    }
    active.slotReserved = false;
    const current = this.#activeCount(active.preset.preset_id);
    this.#concurrency.set(active.preset.preset_id, Math.max(0, current - 1));
  }

  #resolveWaiters(run: RunRecord): void {
    const set = this.#waiters.get(run.run_id);
    if (set === undefined) {
      return;
    }
    this.#waiters.delete(run.run_id);
    for (const waiter of set) {
      waiter(run);
    }
  }

  #reconstructRun(
    created: RunLedgerEvent,
    last: RunLedgerEvent,
    sessionId: string | null
  ): RunRecord | null {
    if (
      created.role === null ||
      created.task_id === null ||
      created.workflow_instance_id === null ||
      created.run_id === null
    ) {
      return null;
    }
    const data = created.data;
    const workflowId = data.workflow_id;
    if (typeof workflowId !== "string" || !isWorkflowId(workflowId)) {
      return null;
    }
    const presetId = data.preset_id;
    const presetVersion = data.preset_version;
    const workspaceId = data.workspace_id;
    const toolProfile = data.tool_profile;
    const inputSha256 = data.input_sha256;
    if (
      typeof presetId !== "string" ||
      typeof presetVersion !== "string" ||
      typeof workspaceId !== "string" ||
      typeof toolProfile !== "string" ||
      typeof inputSha256 !== "string"
    ) {
      return null;
    }
    const budgetRaw = data.budget;
    const budget: Budget =
      isPlainObject(budgetRaw) &&
      typeof budgetRaw.max_tokens === "number" &&
      typeof budgetRaw.max_cost_usd === "number"
        ? {
            max_tokens: budgetRaw.max_tokens,
            max_cost_usd: budgetRaw.max_cost_usd
          }
        : { max_tokens: 0, max_cost_usd: 0 };
    const status = this.#statusFromEvent(last);
    if (status === null) {
      return null;
    }
    return {
      run_id: created.run_id,
      workflow_instance_id: created.workflow_instance_id,
      workflow_id: workflowId as WorkflowId,
      task_id: created.task_id,
      parent_run_id:
        typeof data.parent_run_id === "string" ? data.parent_run_id : null,
      role: created.role,
      preset_id: presetId,
      preset_version: presetVersion,
      workspace_id: workspaceId,
      episode_id:
        typeof data.episode_id === "string" ? data.episode_id : null,
      tool_profile: toolProfile,
      memory_pack_snapshot_id:
        typeof data.memory_pack_snapshot_id === "string"
          ? data.memory_pack_snapshot_id
          : null,
      memory_pack_snapshot_hash:
        typeof data.memory_pack_snapshot_hash === "string"
          ? data.memory_pack_snapshot_hash
          : null,
      approval_ref:
        typeof data.approval_ref === "string" ? data.approval_ref : null,
      base_sha: typeof data.base_sha === "string" ? data.base_sha : null,
      deadline_ms:
        typeof data.deadline_ms === "number" ? data.deadline_ms : 1,
      budget,
      input_sha256: inputSha256,
      status,
      session_id: sessionId,
      result_ref: null,
      result_sha256: null,
      cleanup_state: null,
      reason_code: null,
      reason: null,
      created_at: created.at,
      updated_at: last.at,
      worker: data.worker === true,
      adapter_id: typeof data.adapter === "string" ? data.adapter : "unknown"
    };
  }

  #statusFromEvent(event: RunLedgerEvent): RunStatus | null {
    switch (event.type) {
      case "run.created":
        return "created";
      case "run.validated":
        return "validated";
      case "run.queued":
      case "run.approved":
        return "queued";
      case "run.waiting_approval":
        return "waiting_approval";
      case "run.session_opened":
      case "run.started":
        return "running";
      default:
        return null;
    }
  }
}
