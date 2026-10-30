import type { RoleId, WorkflowId } from "../src/contract.ts";
import { FleetController } from "../src/fleet-controller.ts";
import { FleetApi } from "../src/fleet-api.ts";
import { TrustedBindingIssuer } from "../src/binding.ts";
import type { TrustedBinding } from "../src/binding.ts";
import { DeterministicIdGenerator } from "../src/ids.ts";
import { InMemoryRunLedger } from "../src/ledger.ts";
import { InMemoryResultStore } from "../src/result-store.ts";
import { FakeApprovalRegistry } from "../src/approval.ts";
import { FixedClock } from "../src/time.ts";
import { FakeDshAdapter } from "../src/adapters/fake-dsh-adapter.ts";
import type { FakeDshAdapterOptions } from "../src/adapters/fake-dsh-adapter.ts";
import { FakeMemoryPackClient } from "../src/memory/fake-memorypack-client.ts";
import { getRolePreset } from "../src/registries/roles.ts";
import type { MemoryPackRef } from "../src/binding.ts";

export interface HarnessOptions {
  adapter?: FakeDshAdapterOptions;
}

export interface BindingOverrides {
  workspace_id?: string;
  episode_id?: string | null;
  workflow_instance_id?: string;
  memory_pack?: MemoryPackRef | null;
  approval_ref?: string | null;
  base_sha?: string | null;
  max_timeout_ms?: number;
  max_budget?: { max_tokens: number; max_cost_usd: number };
}

export interface SubmitOptions extends BindingOverrides {
  input?: Record<string, unknown>;
  parent_run_id?: string | null;
  deadline_ms?: number;
  budget?: { max_tokens: number; max_cost_usd: number };
}

export function makeHarness(options: HarnessOptions = {}) {
  const clock = new FixedClock("2026-10-30T00:00:00.000Z");
  const ids = new DeterministicIdGenerator();
  const issuer = new TrustedBindingIssuer({ idGenerator: ids, clock });
  const ledger = new InMemoryRunLedger({ idGenerator: ids, clock });
  const adapter = new FakeDshAdapter(options.adapter);
  const resultStore = new InMemoryResultStore();
  const approval = new FakeApprovalRegistry();
  const memory = new FakeMemoryPackClient(clock);
  const controller = new FleetController({
    bindingIssuer: issuer,
    ledger,
    adapter,
    resultStore,
    approvalVerifier: approval,
    clock,
    idGenerator: ids
  });
  const api = new FleetApi(controller);

  const issueBinding = async (
    role: RoleId,
    overrides: BindingOverrides = {}
  ): Promise<TrustedBinding> => {
    const preset = getRolePreset(role);
    if (preset === undefined) {
      throw new Error(`unknown role: ${role}`);
    }
    const workspaceId = overrides.workspace_id ?? "ws_a";
    const episodeId = overrides.episode_id !== undefined ? overrides.episode_id : preset.worker ? "ep_1" : null;
    let memoryPack = overrides.memory_pack;
    if (memoryPack === undefined && preset.worker) {
      memoryPack = await memory.createPackRef(workspaceId, episodeId, role);
    }
    return issuer.issue({
      workflow_instance_id: overrides.workflow_instance_id ?? ids.workflowInstanceId(),
      workspace_id: workspaceId,
      episode_id: episodeId,
      role,
      preset_id: preset.preset_id,
      preset_version: preset.preset_version,
      tool_profile: preset.tool_profile ?? "",
      memory_pack: memoryPack ?? null,
      approval_ref: overrides.approval_ref ?? null,
      base_sha: overrides.base_sha ?? null,
      max_timeout_ms: overrides.max_timeout_ms,
      max_budget: overrides.max_budget
    });
  };

  const submitAs = async (
    role: RoleId,
    workflowId: WorkflowId,
    taskId: string,
    options: SubmitOptions = {}
  ) => {
    const binding = await issueBinding(role, options);
    const request: Record<string, unknown> = {
      contract_version: "1.0.0",
      workflow_id: workflowId,
      task_id: taskId,
      input: options.input ?? { brief: "synthetic fixture" }
    };
    if (options.parent_run_id !== undefined) {
      request.parent_run_id = options.parent_run_id;
    }
    if (options.deadline_ms !== undefined) {
      request.deadline_ms = options.deadline_ms;
    }
    if (options.budget !== undefined) {
      request.budget = options.budget;
    }
    return { binding, request, response: api.submit(request, binding) };
  };

  return {
    clock,
    ids,
    issuer,
    ledger,
    adapter,
    resultStore,
    approval,
    memory,
    controller,
    api,
    issueBinding,
    submitAs
  };
}
