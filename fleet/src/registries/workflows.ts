import { deepFreeze } from "../canonical-json.ts";
import type { RoleId, WorkflowId } from "../contract.ts";

export interface WorkflowTask {
  task_id: string;
  allowed_roles: readonly RoleId[];
  worker: boolean;
  requires_approval: boolean;
  depends_on: readonly string[];
}

export interface WorkflowDefinition {
  workflow_id: WorkflowId;
  version: string;
  enabled: boolean;
  default: boolean;
  tasks: readonly WorkflowTask[];
}

export const WORKFLOW_REGISTRY: readonly WorkflowDefinition[] = deepFreeze([
  {
    workflow_id: "single",
    version: "1.0.0",
    enabled: true,
    default: true,
    tasks: [
      {
        task_id: "main",
        allowed_roles: ["orchestrator"],
        worker: false,
        requires_approval: false,
        depends_on: []
      }
    ]
  },
  {
    workflow_id: "research",
    version: "1.0.0",
    enabled: true,
    default: false,
    tasks: [
      {
        task_id: "analysis_a",
        allowed_roles: ["researcher"],
        worker: true,
        requires_approval: false,
        depends_on: []
      },
      {
        task_id: "analysis_b",
        allowed_roles: ["vehicle_analyst"],
        worker: true,
        requires_approval: false,
        depends_on: []
      },
      {
        task_id: "challenge",
        allowed_roles: ["challenger"],
        worker: true,
        requires_approval: false,
        depends_on: ["analysis_a"]
      },
      {
        task_id: "verify",
        allowed_roles: ["evidence_verifier"],
        worker: true,
        requires_approval: false,
        depends_on: ["challenge"]
      }
    ]
  },
  {
    workflow_id: "design_review",
    version: "1.0.0",
    enabled: true,
    default: false,
    tasks: [
      {
        task_id: "design",
        allowed_roles: ["vehicle_analyst"],
        worker: true,
        requires_approval: false,
        depends_on: []
      },
      {
        task_id: "challenge",
        allowed_roles: ["challenger"],
        worker: true,
        requires_approval: false,
        depends_on: ["design"]
      },
      {
        task_id: "verify",
        allowed_roles: ["evidence_verifier"],
        worker: true,
        requires_approval: false,
        depends_on: ["challenge"]
      }
    ]
  },
  {
    workflow_id: "security_audit",
    version: "1.0.0",
    enabled: true,
    default: false,
    tasks: [
      {
        task_id: "analysis",
        allowed_roles: ["researcher", "vehicle_analyst"],
        worker: true,
        requires_approval: false,
        depends_on: []
      },
      {
        task_id: "challenge",
        allowed_roles: ["challenger"],
        worker: true,
        requires_approval: false,
        depends_on: ["analysis"]
      },
      {
        task_id: "validation",
        allowed_roles: ["lab_runner"],
        worker: true,
        requires_approval: true,
        depends_on: ["analysis"]
      },
      {
        task_id: "verify",
        allowed_roles: ["evidence_verifier"],
        worker: true,
        requires_approval: false,
        depends_on: ["challenge"]
      }
    ]
  },
  {
    workflow_id: "lab_validation",
    version: "1.0.0",
    enabled: false,
    default: false,
    tasks: [
      {
        task_id: "suite_run",
        allowed_roles: ["lab_runner"],
        worker: true,
        requires_approval: true,
        depends_on: []
      }
    ]
  }
]);

const BY_ID = new Map<WorkflowId, WorkflowDefinition>(
  WORKFLOW_REGISTRY.map((workflow) => [workflow.workflow_id, workflow])
);

export function getWorkflow(workflowId: WorkflowId): WorkflowDefinition | undefined {
  return BY_ID.get(workflowId);
}

export function getTask(
  workflow: WorkflowDefinition,
  taskId: string
): WorkflowTask | undefined {
  return workflow.tasks.find((task) => task.task_id === taskId);
}

export function taskDependencies(workflow: WorkflowDefinition, taskId: string): readonly string[] {
  return getTask(workflow, taskId)?.depends_on ?? [];
}

export interface WorkflowRegistryValidation {
  ok: boolean;
  errors: string[];
}

export function validateWorkflowRegistry(): WorkflowRegistryValidation {
  const errors: string[] = [];
  const ids = new Set<string>();
  let defaults = 0;
  for (const workflow of WORKFLOW_REGISTRY) {
    if (ids.has(workflow.workflow_id)) {
      errors.push(`duplicate workflow_id: ${workflow.workflow_id}`);
    }
    ids.add(workflow.workflow_id);
    if (workflow.default) {
      defaults += 1;
    }
    const taskIds = new Set<string>();
    for (const task of workflow.tasks) {
      if (taskIds.has(task.task_id)) {
        errors.push(`duplicate task_id in ${workflow.workflow_id}: ${task.task_id}`);
      }
      taskIds.add(task.task_id);
      for (const dependency of task.depends_on) {
        if (!workflow.tasks.some((candidate) => candidate.task_id === dependency)) {
          errors.push(
            `unknown dependency in ${workflow.workflow_id}/${task.task_id}: ${dependency}`
          );
        }
        if (dependency === task.task_id) {
          errors.push(`self dependency in ${workflow.workflow_id}/${task.task_id}`);
        }
      }
    }
  }
  if (defaults !== 1) {
    errors.push(`expected exactly one default workflow, got ${defaults}`);
  }
  return { ok: errors.length === 0, errors };
}
