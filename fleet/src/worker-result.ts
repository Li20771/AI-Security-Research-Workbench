import { deepFreeze, isPlainObject, sha256OfJson } from "./canonical-json.ts";
import type {
  RequestedAction,
  RoleId,
  Severity,
  Verdict,
  Visibility
} from "./contract.ts";
import {
  REQUESTED_ACTIONS,
  SEVERITIES,
  VERDICTS,
  VISIBILITIES
} from "./contract.ts";
import { FleetPolicyError } from "./errors.ts";
import { isSafeReference } from "./path-safety.ts";
import type { Clock } from "./time.ts";
import { nowIso } from "./time.ts";

export interface Citation {
  ref: string;
  revision: string;
  kind: "memory" | "file" | "report" | "artifact";
}

export interface Claim {
  claim_id: string;
  text: string;
  citations: Citation[];
}

export interface ArtifactRef {
  ref: string;
  sha256: string;
}

export interface MemoryCandidate {
  candidate_id: string;
  text: string;
  scope: Visibility;
  rationale?: string;
}

export interface RequestedActionRef {
  action: RequestedAction;
  target: string;
}

export interface Finding {
  finding_id: string;
  target: string;
  severity: Severity;
  rationale: string;
  citations: Citation[];
}

export interface VerdictResult {
  claim_id: string;
  verdict: Verdict;
  evidence_refs: string[];
  rationale: string;
}

export interface WorkerResultPayload {
  summary: string;
  claims: Claim[];
  citations: Citation[];
  artifacts: ArtifactRef[];
  memory_candidates: MemoryCandidate[];
  requested_actions: RequestedActionRef[];
  limitations: string[];
  findings?: Finding[];
  verdicts?: VerdictResult[];
}

export interface WorkerResultEnvelope {
  contract_version: "1.0.0";
  schema_id: "worker-result.v1";
  run_id: string;
  role: RoleId;
  received_at: string;
  untrusted: true;
  admission: "none";
  evidence: false;
  payload_sha256: string;
  payload: WorkerResultPayload;
}

export type WorkerResultValidation =
  | { ok: true; payload: WorkerResultPayload }
  | { ok: false; errors: string[] };

const TOP_LEVEL_KEYS = new Set([
  "summary",
  "claims",
  "citations",
  "artifacts",
  "memory_candidates",
  "requested_actions",
  "limitations",
  "findings",
  "verdicts"
]);

const CLAIM_ID = /^clm_[A-Za-z0-9_-]{4,64}$/;
const FINDING_ID = /^fnd_[A-Za-z0-9_-]{4,64}$/;
const CANDIDATE_ID = /^mc_[A-Za-z0-9_-]{4,64}$/;

function pushError(errors: string[], message: string): void {
  if (errors.length < 50) {
    errors.push(message);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return isPlainObject(value);
}

function checkKeys(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
  path: string,
  errors: string[]
): void {
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      pushError(errors, `${path}.${key} is not allowed`);
    }
  }
}

function requireRecord(
  value: unknown,
  path: string,
  errors: string[]
): Record<string, unknown> | null {
  if (!isRecord(value)) {
    pushError(errors, `${path} must be an object`);
    return null;
  }
  return value;
}

function requireString(
  value: unknown,
  path: string,
  errors: string[],
  min: number,
  max: number
): string | null {
  if (typeof value !== "string" || value.length < min || value.length > max) {
    pushError(errors, `${path} must be a string of length ${min}..${max}`);
    return null;
  }
  return value;
}

function requireArray(
  value: unknown,
  path: string,
  errors: string[],
  maxItems: number,
  minItems: number = 0
): unknown[] | null {
  if (!Array.isArray(value) || value.length < minItems || value.length > maxItems) {
    pushError(errors, `${path} must be an array of length ${minItems}..${maxItems}`);
    return null;
  }
  return value;
}

function requireRef(value: unknown, path: string, errors: string[]): string | null {
  const ref = requireString(value, path, errors, 1, 512);
  if (ref === null) {
    return null;
  }
  if (!isSafeReference(ref)) {
    pushError(errors, `${path} must be a relative reference without traversal`);
    return null;
  }
  return ref;
}

function validateCitation(
  value: unknown,
  path: string,
  errors: string[]
): Citation | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["ref", "revision", "kind"]), path, errors);
  const ref = requireRef(record.ref, `${path}.ref`, errors);
  const revision = requireString(record.revision, `${path}.revision`, errors, 1, 128);
  const kind = record.kind;
  if (kind !== "memory" && kind !== "file" && kind !== "report" && kind !== "artifact") {
    pushError(errors, `${path}.kind is invalid`);
  }
  if (ref === null || revision === null) {
    return null;
  }
  return { ref, revision, kind: kind as Citation["kind"] };
}

function validateClaim(value: unknown, path: string, errors: string[]): Claim | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["claim_id", "text", "citations"]), path, errors);
  const claimId = record.claim_id;
  if (typeof claimId !== "string" || !CLAIM_ID.test(claimId)) {
    pushError(errors, `${path}.claim_id is invalid`);
  }
  const text = requireString(record.text, `${path}.text`, errors, 1, 4000);
  const citationsRaw = requireArray(record.citations, `${path}.citations`, errors, 50);
  const citations: Citation[] = [];
  if (citationsRaw !== null) {
    for (const [index, item] of citationsRaw.entries()) {
      const citation = validateCitation(item, `${path}.citations[${index}]`, errors);
      if (citation !== null) {
        citations.push(citation);
      }
    }
  }
  if (typeof claimId !== "string" || !CLAIM_ID.test(claimId) || text === null) {
    return null;
  }
  return { claim_id: claimId, text, citations };
}

function validateArtifact(value: unknown, path: string, errors: string[]): ArtifactRef | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["ref", "sha256"]), path, errors);
  const ref = requireRef(record.ref, `${path}.ref`, errors);
  const sha256 = record.sha256;
  if (typeof sha256 !== "string" || !/^[a-f0-9]{64}$/.test(sha256)) {
    pushError(errors, `${path}.sha256 must be 64 lowercase hex characters`);
  }
  if (ref === null || typeof sha256 !== "string") {
    return null;
  }
  return { ref, sha256 };
}

function validateMemoryCandidate(
  value: unknown,
  path: string,
  errors: string[]
): MemoryCandidate | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["candidate_id", "text", "scope", "rationale"]), path, errors);
  const candidateId = record.candidate_id;
  if (typeof candidateId !== "string" || !CANDIDATE_ID.test(candidateId)) {
    pushError(errors, `${path}.candidate_id is invalid`);
  }
  const text = requireString(record.text, `${path}.text`, errors, 1, 2000);
  const scope = record.scope;
  if (typeof scope !== "string" || !(VISIBILITIES as readonly string[]).includes(scope)) {
    pushError(errors, `${path}.scope must be user-global, workspace-shared, episode-shared, or run-private`);
  }
  let rationale: string | undefined;
  if (record.rationale !== undefined) {
    const validated = requireString(record.rationale, `${path}.rationale`, errors, 1, 1000);
    if (validated !== null) {
      rationale = validated;
    }
  }
  if (
    typeof candidateId !== "string" ||
    !CANDIDATE_ID.test(candidateId) ||
    text === null ||
    typeof scope !== "string" ||
    !(VISIBILITIES as readonly string[]).includes(scope)
  ) {
    return null;
  }
  const candidate: MemoryCandidate = {
    candidate_id: candidateId,
    text,
    scope: scope as Visibility
  };
  if (rationale !== undefined) {
    candidate.rationale = rationale;
  }
  return candidate;
}

function validateRequestedAction(
  value: unknown,
  path: string,
  errors: string[]
): RequestedActionRef | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["action", "target"]), path, errors);
  const action = record.action;
  if (typeof action !== "string" || !(REQUESTED_ACTIONS as readonly string[]).includes(action)) {
    pushError(errors, `${path}.action is not an allowed non-executing action`);
  }
  const target = requireString(record.target, `${path}.target`, errors, 1, 256);
  if (
    typeof action !== "string" ||
    !(REQUESTED_ACTIONS as readonly string[]).includes(action) ||
    target === null
  ) {
    return null;
  }
  return { action: action as RequestedAction, target };
}

function validateFinding(value: unknown, path: string, errors: string[]): Finding | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["finding_id", "target", "severity", "rationale", "citations"]), path, errors);
  const findingId = record.finding_id;
  if (typeof findingId !== "string" || !FINDING_ID.test(findingId)) {
    pushError(errors, `${path}.finding_id is invalid`);
  }
  const target = requireString(record.target, `${path}.target`, errors, 1, 256);
  const severity = record.severity;
  if (typeof severity !== "string" || !(SEVERITIES as readonly string[]).includes(severity)) {
    pushError(errors, `${path}.severity is invalid`);
  }
  const rationale = requireString(record.rationale, `${path}.rationale`, errors, 1, 2000);
  const citationsRaw = requireArray(record.citations, `${path}.citations`, errors, 50);
  const citations: Citation[] = [];
  if (citationsRaw !== null) {
    for (const [index, item] of citationsRaw.entries()) {
      const citation = validateCitation(item, `${path}.citations[${index}]`, errors);
      if (citation !== null) {
        citations.push(citation);
      }
    }
  }
  if (
    typeof findingId !== "string" ||
    !FINDING_ID.test(findingId) ||
    target === null ||
    typeof severity !== "string" ||
    !(SEVERITIES as readonly string[]).includes(severity) ||
    rationale === null
  ) {
    return null;
  }
  return {
    finding_id: findingId,
    target,
    severity: severity as Severity,
    rationale,
    citations
  };
}

function validateVerdict(value: unknown, path: string, errors: string[]): VerdictResult | null {
  const record = requireRecord(value, path, errors);
  if (record === null) {
    return null;
  }
  checkKeys(record, new Set(["claim_id", "verdict", "evidence_refs", "rationale"]), path, errors);
  const claimId = record.claim_id;
  if (typeof claimId !== "string" || !CLAIM_ID.test(claimId)) {
    pushError(errors, `${path}.claim_id is invalid`);
  }
  const verdict = record.verdict;
  if (typeof verdict !== "string" || !(VERDICTS as readonly string[]).includes(verdict)) {
    pushError(errors, `${path}.verdict is invalid`);
  }
  const evidenceRefsRaw = requireArray(record.evidence_refs, `${path}.evidence_refs`, errors, 50);
  const evidenceRefs: string[] = [];
  if (evidenceRefsRaw !== null) {
    for (const [index, item] of evidenceRefsRaw.entries()) {
      const ref = requireRef(item, `${path}.evidence_refs[${index}]`, errors);
      if (ref !== null) {
        evidenceRefs.push(ref);
      }
    }
  }
  const rationale = requireString(record.rationale, `${path}.rationale`, errors, 1, 2000);
  if (
    typeof claimId !== "string" ||
    !CLAIM_ID.test(claimId) ||
    typeof verdict !== "string" ||
    !(VERDICTS as readonly string[]).includes(verdict) ||
    rationale === null
  ) {
    return null;
  }
  return {
    claim_id: claimId,
    verdict: verdict as Verdict,
    evidence_refs: evidenceRefs,
    rationale
  };
}

export function validateWorkerResultPayload(
  role: RoleId,
  value: unknown
): WorkerResultValidation {
  const errors: string[] = [];
  const record = requireRecord(value, "payload", errors);
  if (record === null) {
    return { ok: false, errors };
  }
  checkKeys(record, TOP_LEVEL_KEYS, "payload", errors);

  const summary = requireString(record.summary, "payload.summary", errors, 1, 4000);

  const claimsRaw = requireArray(record.claims, "payload.claims", errors, 100);
  const claims: Claim[] = [];
  if (claimsRaw !== null) {
    for (const [index, item] of claimsRaw.entries()) {
      const claim = validateClaim(item, `payload.claims[${index}]`, errors);
      if (claim !== null) {
        claims.push(claim);
      }
    }
  }

  const citationsRaw = requireArray(record.citations, "payload.citations", errors, 200);
  const citations: Citation[] = [];
  if (citationsRaw !== null) {
    for (const [index, item] of citationsRaw.entries()) {
      const citation = validateCitation(item, `payload.citations[${index}]`, errors);
      if (citation !== null) {
        citations.push(citation);
      }
    }
  }

  const artifactsRaw = requireArray(record.artifacts, "payload.artifacts", errors, 100);
  const artifacts: ArtifactRef[] = [];
  if (artifactsRaw !== null) {
    for (const [index, item] of artifactsRaw.entries()) {
      const artifact = validateArtifact(item, `payload.artifacts[${index}]`, errors);
      if (artifact !== null) {
        artifacts.push(artifact);
      }
    }
  }

  const candidatesRaw = requireArray(
    record.memory_candidates,
    "payload.memory_candidates",
    errors,
    100
  );
  const memoryCandidates: MemoryCandidate[] = [];
  if (candidatesRaw !== null) {
    for (const [index, item] of candidatesRaw.entries()) {
      const candidate = validateMemoryCandidate(
        item,
        `payload.memory_candidates[${index}]`,
        errors
      );
      if (candidate !== null) {
        memoryCandidates.push(candidate);
      }
    }
  }

  const actionsRaw = requireArray(
    record.requested_actions,
    "payload.requested_actions",
    errors,
    50
  );
  const requestedActions: RequestedActionRef[] = [];
  if (actionsRaw !== null) {
    for (const [index, item] of actionsRaw.entries()) {
      const action = validateRequestedAction(
        item,
        `payload.requested_actions[${index}]`,
        errors
      );
      if (action !== null) {
        requestedActions.push(action);
      }
    }
  }

  const limitationsRaw = requireArray(record.limitations, "payload.limitations", errors, 50);
  const limitations: string[] = [];
  if (limitationsRaw !== null) {
    for (const [index, item] of limitationsRaw.entries()) {
      const limitation = requireString(item, `payload.limitations[${index}]`, errors, 1, 1000);
      if (limitation !== null) {
        limitations.push(limitation);
      }
    }
  }

  let findings: Finding[] | undefined;
  if (record.findings !== undefined) {
    const findingsRaw = requireArray(record.findings, "payload.findings", errors, 100);
    if (findingsRaw !== null) {
      findings = [];
      for (const [index, item] of findingsRaw.entries()) {
        const finding = validateFinding(item, `payload.findings[${index}]`, errors);
        if (finding !== null) {
          findings.push(finding);
        }
      }
    }
  } else if (role === "challenger") {
    pushError(errors, "payload.findings is required for challenger");
  }

  let verdicts: VerdictResult[] | undefined;
  if (record.verdicts !== undefined) {
    const verdictsRaw = requireArray(record.verdicts, "payload.verdicts", errors, 100, 1);
    if (verdictsRaw !== null) {
      verdicts = [];
      for (const [index, item] of verdictsRaw.entries()) {
        const verdict = validateVerdict(item, `payload.verdicts[${index}]`, errors);
        if (verdict !== null) {
          verdicts.push(verdict);
        }
      }
    }
  } else if (role === "evidence_verifier") {
    pushError(errors, "payload.verdicts is required for evidence_verifier");
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  const payload: WorkerResultPayload = {
    summary: summary as string,
    claims,
    citations,
    artifacts,
    memory_candidates: memoryCandidates,
    requested_actions: requestedActions,
    limitations
  };
  if (findings !== undefined) {
    payload.findings = findings;
  }
  if (verdicts !== undefined) {
    payload.verdicts = verdicts;
  }
  return { ok: true, payload };
}

export function createWorkerResultEnvelope(
  runId: string,
  role: RoleId,
  value: unknown,
  clock: Clock
): WorkerResultEnvelope {
  const validation = validateWorkerResultPayload(role, value);
  if (!validation.ok) {
    throw new FleetPolicyError(
      "invalid-worker-result",
      "worker result failed schema or role validation",
      { errors: validation.errors.slice(0, 10).join("; ") }
    );
  }
  const payload = deepFreeze(validation.payload);
  return deepFreeze({
    contract_version: "1.0.0" as const,
    schema_id: "worker-result.v1" as const,
    run_id: runId,
    role,
    received_at: nowIso(clock),
    untrusted: true as const,
    admission: "none" as const,
    evidence: false as const,
    payload_sha256: sha256OfJson(payload),
    payload
  });
}

export function artifactsForEnvelope(
  envelope: WorkerResultEnvelope
): Array<{ ref: string; sha256: string }> {
  return envelope.payload.artifacts.map((artifact) => ({
    ref: artifact.ref,
    sha256: artifact.sha256
  }));
}
