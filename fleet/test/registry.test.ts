import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { FleetApi } from "../src/fleet-api.ts";
import { getPlugin } from "../src/registries/plugins.ts";
import { getRolePreset, ROLE_PRESETS } from "../src/registries/roles.ts";
import { getWorkflow, validateWorkflowRegistry, WORKFLOW_REGISTRY } from "../src/registries/workflows.ts";

const CONTRACTS = join(process.cwd(), "..", "docs", "contracts");

test("workflow registry is valid and lab_validation is disabled", () => {
  assert.equal(validateWorkflowRegistry().ok, true);
  const lab = getWorkflow("lab_validation");
  assert.ok(lab);
  assert.equal(lab.enabled, false);
  const single = getWorkflow("single");
  assert.ok(single);
  assert.equal(single.default, true);
  assert.deepEqual(single.tasks[0]?.allowed_roles, ["orchestrator"]);
  assert.equal(single.tasks[0]?.worker, false);
});

test("role registry keeps lab_runner disabled and challenger tools minimal", () => {
  const lab = getRolePreset("lab_runner");
  assert.ok(lab);
  assert.equal(lab.enabled, false);
  assert.equal(lab.requires_approval, true);
  assert.deepEqual(lab.allowed_tools, ["securitylab_vcan"]);
  const challenger = getRolePreset("challenger");
  assert.ok(challenger);
  assert.ok(!challenger.allowed_tools.includes("lab_get_run_result"));
  const vcan = getPlugin("fleet.securitylab-vcan");
  assert.ok(vcan);
  assert.equal(vcan.enabled, false);
});

test("the frozen role-preset example matches the code registry", () => {
  const example = JSON.parse(
    readFileSync(join(CONTRACTS, "examples", "role-preset.registry.json"), "utf8")
  ) as { contract_version: string; presets: unknown[] };
  assert.equal(example.contract_version, "1.0.0");
  assert.deepEqual(example.presets, ROLE_PRESETS);
});

test("the frozen workflow example matches the code registry", () => {
  const example = JSON.parse(
    readFileSync(join(CONTRACTS, "examples", "workflow.registry.json"), "utf8")
  ) as { contract_version: string; workflows: unknown[] };
  assert.equal(example.contract_version, "1.0.0");
  assert.deepEqual(example.workflows, WORKFLOW_REGISTRY);
});

test("FleetApi exposes exactly the four fixed operations", () => {
  const methods = Object.getOwnPropertyNames(FleetApi.prototype).sort();
  assert.deepEqual(methods, ["cancel", "constructor", "result", "status", "submit"]);
});
