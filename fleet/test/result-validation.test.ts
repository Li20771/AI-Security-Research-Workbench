import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { FleetPolicyError } from "../src/errors.ts";
import { FixedClock } from "../src/time.ts";
import {
  artifactsForEnvelope,
  createWorkerResultEnvelope,
  validateWorkerResultPayload
} from "../src/worker-result.ts";

const EXAMPLES = join(process.cwd(), "..", "docs", "contracts", "examples");

function researcherPayload(): Record<string, unknown> {
  return {
    summary: "Synthetic analysis.",
    claims: [],
    citations: [],
    artifacts: [],
    memory_candidates: [],
    requested_actions: [],
    limitations: ["synthetic"]
  };
}

test("the frozen challenger and verifier examples pass runtime validation", () => {
  const challenger = JSON.parse(
    readFileSync(join(EXAMPLES, "worker-result.challenger.json"), "utf8")
  ) as unknown;
  const challengerResult = validateWorkerResultPayload("challenger", challenger);
  assert.equal(challengerResult.ok, true);

  const verifier = JSON.parse(
    readFileSync(join(EXAMPLES, "worker-result.evidence-verifier.json"), "utf8")
  ) as unknown;
  const verifierResult = validateWorkerResultPayload("evidence_verifier", verifier);
  assert.equal(verifierResult.ok, true);
});

test("challenger requires findings and verifier requires at least one verdict", () => {
  const missingFindings = validateWorkerResultPayload("challenger", researcherPayload());
  assert.equal(missingFindings.ok, false);
  assert.ok(missingFindings.ok === false && missingFindings.errors.some((e) => e.includes("findings")));

  const missingVerdicts = validateWorkerResultPayload("evidence_verifier", researcherPayload());
  assert.equal(missingVerdicts.ok, false);
  assert.ok(missingVerdicts.ok === false && missingVerdicts.errors.some((e) => e.includes("verdicts")));

  const emptyVerdicts = validateWorkerResultPayload("evidence_verifier", {
    ...researcherPayload(),
    verdicts: []
  });
  assert.equal(emptyVerdicts.ok, false);
});

test("executing actions, restricted memory candidates, and traversal references are rejected", () => {
  const executing = validateWorkerResultPayload("researcher", {
    ...researcherPayload(),
    requested_actions: [{ action: "execute", target: "shell" }]
  });
  assert.equal(executing.ok, false);

  const restricted = validateWorkerResultPayload("researcher", {
    ...researcherPayload(),
    memory_candidates: [
      { candidate_id: "mc_0001", text: "secret", scope: "restricted" }
    ]
  });
  assert.equal(restricted.ok, false);

  const traversalArtifact = validateWorkerResultPayload("researcher", {
    ...researcherPayload(),
    artifacts: [{ ref: "../outside.txt", sha256: "a".repeat(64) }]
  });
  assert.equal(traversalArtifact.ok, false);

  const traversalCitation = validateWorkerResultPayload("researcher", {
    ...researcherPayload(),
    citations: [{ ref: "../outside.txt", revision: "abc", kind: "file" }]
  });
  assert.equal(traversalCitation.ok, false);
});

test("the result envelope is explicitly untrusted and not Evidence", () => {
  const envelope = createWorkerResultEnvelope(
    "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "researcher",
    researcherPayload(),
    new FixedClock()
  );
  assert.equal(envelope.contract_version, "1.0.0");
  assert.equal(envelope.schema_id, "worker-result.v1");
  assert.equal(envelope.untrusted, true);
  assert.equal(envelope.admission, "none");
  assert.equal(envelope.evidence, false);
  assert.match(envelope.payload_sha256, /^[a-f0-9]{64}$/);
  assert.deepEqual(artifactsForEnvelope(envelope), []);
});

test("invalid worker output becomes a policy error, never a completed result", () => {
  assert.throws(
    () =>
      createWorkerResultEnvelope(
        "run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "researcher",
        { summary: 123 },
        new FixedClock()
      ),
    (error: unknown) => error instanceof FleetPolicyError && error.code === "invalid-worker-result"
  );
});
