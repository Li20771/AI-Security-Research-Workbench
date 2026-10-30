import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync
} from "node:fs";
import { dirname } from "node:path";
import {
  canonicalJson,
  deepFreeze,
  isPlainObject,
  jsonByteLength,
  sha256OfJson
} from "./canonical-json.ts";
import type {
  RoleId,
  RunLedgerEventType
} from "./contract.ts";
import {
  ALLOWED_LEDGER_DATA_KEYS,
  FORBIDDEN_LEDGER_KEYS,
  isRoleId,
  isRunLedgerEventType
} from "./contract.ts";
import { FleetPolicyError } from "./errors.ts";
import type { IdGenerator } from "./ids.ts";
import { UuidIdGenerator } from "./ids.ts";
import type { Clock } from "./time.ts";
import { nowIso, SystemClock } from "./time.ts";
import { EVENT_ID_PATTERN, RUN_ID_PATTERN, TASK_ID_PATTERN, WFI_PATTERN } from "./binding.ts";

export const GENESIS_HASH = "0".repeat(64);
const MAX_EVENT_BYTES = 16 * 1024;
const MAX_STRING_LENGTH = 2048;
const MAX_ARRAY_ITEMS = 100;
const MAX_DEPTH = 4;

const ALLOWED_DATA_KEYS = new Set<string>(ALLOWED_LEDGER_DATA_KEYS);
const FORBIDDEN_KEYS = new Set<string>(FORBIDDEN_LEDGER_KEYS);
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const REASON_CODE_PATTERN = /^[a-z][a-z0-9-]{1,63}$/;
const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,96}$/;
const SESSION_ID_PATTERN = /^dshsess_[A-Za-z0-9_-]{8,120}$/;
const PRESET_ID_PATTERN = /^preset_[a-z][a-z0-9_]{2,63}$/;
const PRESET_VERSION_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+$/;
const WORKSPACE_ID_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/;
const EPISODE_ID_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/;
const BASE_SHA_PATTERN = /^([a-f0-9]{40}|[a-f0-9]{64})$/;
const MEMORY_PACK_ID_PATTERN = /^mp_[a-f0-9]{32}$/;
const RESULT_REF_PATTERN = /^result:\/\/run_[A-Za-z0-9_-]{8,96}$/;

export interface RunLedgerEvent {
  contract_version: "1.0.0";
  seq: number;
  event_id: string;
  at: string;
  type: RunLedgerEventType;
  workflow_instance_id: string | null;
  run_id: string | null;
  task_id: string | null;
  role: RoleId | null;
  data: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface RunLedgerAppendInput {
  type: RunLedgerEventType;
  workflow_instance_id: string | null;
  run_id: string | null;
  task_id: string | null;
  role: RoleId | null;
  data: Record<string, unknown>;
}

export interface LedgerVerifyResult {
  ok: boolean;
  checked: number;
  error?: string;
  at_seq?: number;
}

export interface RunLedger {
  append(input: RunLedgerAppendInput): RunLedgerEvent;
  readAll(): readonly RunLedgerEvent[];
  verify(): LedgerVerifyResult;
}

function unsafe(message: string, field: string): never {
  throw new FleetPolicyError("ledger-integrity", message, { field });
}

function scanLedgerValue(value: unknown, path: string, depth: number): void {
  if (depth > MAX_DEPTH) {
    unsafe("ledger data is nested too deeply", path);
  }
  if (value === null || typeof value === "boolean") {
    return;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      unsafe("ledger data contains a non-finite number", path);
    }
    return;
  }
  if (typeof value === "string") {
    if (value.length > MAX_STRING_LENGTH) {
      unsafe("ledger string is too long", path);
    }
    if (value.includes("\u0000")) {
      unsafe("ledger string contains NUL", path);
    }
    return;
  }
  if (Array.isArray(value)) {
    if (value.length > MAX_ARRAY_ITEMS) {
      unsafe("ledger array is too long", path);
    }
    for (const [index, item] of value.entries()) {
      scanLedgerValue(item, `${path}[${index}]`, depth + 1);
    }
    return;
  }
  if (isPlainObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(key)) {
        unsafe(`ledger data contains a forbidden field: ${key}`, `${path}.${key}`);
      }
      if (key.length > 64) {
        unsafe("ledger field name is too long", `${path}.${key}`);
      }
      scanLedgerValue(item, `${path}.${key}`, depth + 1);
    }
    return;
  }
  unsafe("ledger data contains an unsupported value", path);
}

export function assertLedgerDataSafe(data: Record<string, unknown>): void {
  if (!isPlainObject(data)) {
    unsafe("ledger data must be an object", "data");
  }
  for (const key of Object.keys(data)) {
    if (!ALLOWED_DATA_KEYS.has(key)) {
      unsafe(`ledger data field is not allowed: ${key}`, `data.${key}`);
    }
  }
  scanLedgerValue(data, "data", 0);
  if (jsonByteLength(data) > MAX_EVENT_BYTES) {
    unsafe("ledger data exceeds 16 KiB", "data");
  }
}

function isoDate(value: unknown): value is string {
  return (
    typeof value === "string" &&
    !Number.isNaN(Date.parse(value)) &&
    new Date(value).toISOString() === value
  );
}

export function validateLedgerEventShape(value: unknown): string[] {
  const errors: string[] = [];
  if (!isPlainObject(value)) {
    return ["event must be an object"];
  }
  const allowed = new Set([
    "contract_version",
    "seq",
    "event_id",
    "at",
    "type",
    "workflow_instance_id",
    "run_id",
    "task_id",
    "role",
    "data",
    "prev_hash",
    "hash"
  ]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      errors.push(`event field is not allowed: ${key}`);
    }
  }
  if (value.contract_version !== "1.0.0") {
    errors.push("contract_version must be 1.0.0");
  }
  if (typeof value.seq !== "number" || !Number.isInteger(value.seq) || value.seq < 1) {
    errors.push("seq must be a positive integer");
  }
  if (typeof value.event_id !== "string" || !EVENT_ID_PATTERN.test(value.event_id)) {
    errors.push("event_id is invalid");
  }
  if (!isoDate(value.at)) {
    errors.push("at must be an ISO timestamp");
  }
  if (typeof value.type !== "string" || !isRunLedgerEventType(value.type)) {
    errors.push("type is invalid");
  }
  if (
    value.workflow_instance_id !== null &&
    (typeof value.workflow_instance_id !== "string" ||
      !WFI_PATTERN.test(value.workflow_instance_id))
  ) {
    errors.push("workflow_instance_id is invalid");
  }
  if (
    value.run_id !== null &&
    (typeof value.run_id !== "string" || !RUN_ID_PATTERN.test(value.run_id))
  ) {
    errors.push("run_id is invalid");
  }
  if (
    value.task_id !== null &&
    (typeof value.task_id !== "string" || !TASK_ID_PATTERN.test(value.task_id))
  ) {
    errors.push("task_id is invalid");
  }
  if (value.role !== null && (typeof value.role !== "string" || !isRoleId(value.role))) {
    errors.push("role is invalid");
  }
  if (!isPlainObject(value.data)) {
    errors.push("data must be an object");
  } else {
    try {
      assertLedgerDataSafe(value.data);
    } catch (error) {
      errors.push(error instanceof Error ? error.message : "data is unsafe");
    }
  }
  if (typeof value.prev_hash !== "string" || !SHA256_PATTERN.test(value.prev_hash)) {
    errors.push("prev_hash is invalid");
  }
  if (typeof value.hash !== "string" || !SHA256_PATTERN.test(value.hash)) {
    errors.push("hash is invalid");
  }
  if (value.type === "request.rejected") {
    if (value.run_id !== null) {
      errors.push("request.rejected must not carry a run_id");
    }
  } else if (typeof value.type === "string" && isRunLedgerEventType(value.type)) {
    if (value.run_id === null) {
      errors.push("run events require run_id");
    }
    if (value.workflow_instance_id === null) {
      errors.push("run events require workflow_instance_id");
    }
    if (value.task_id === null) {
      errors.push("run events require task_id");
    }
    if (value.role === null) {
      errors.push("run events require role");
    }
  }
  return errors;
}

function eventHash(event: Omit<RunLedgerEvent, "hash">): string {
  return sha256OfJson(event);
}

export function verifyLedgerEvents(events: readonly RunLedgerEvent[]): LedgerVerifyResult {
  let prevHash = GENESIS_HASH;
  const seenIds = new Set<string>();
  for (const [index, event] of events.entries()) {
    const errors = validateLedgerEventShape(event);
    if (errors.length > 0) {
      return {
        ok: false,
        checked: index,
        error: errors.join("; "),
        at_seq: event.seq
      };
    }
    if (event.seq !== index + 1) {
      return {
        ok: false,
        checked: index,
        error: `expected seq ${index + 1}, got ${event.seq}`,
        at_seq: event.seq
      };
    }
    if (seenIds.has(event.event_id)) {
      return {
        ok: false,
        checked: index,
        error: `duplicate event_id: ${event.event_id}`,
        at_seq: event.seq
      };
    }
    seenIds.add(event.event_id);
    if (event.prev_hash !== prevHash) {
      return {
        ok: false,
        checked: index,
        error: `prev_hash mismatch at seq ${event.seq}`,
        at_seq: event.seq
      };
    }
    const { hash: _hash, ...withoutHash } = event;
    const computed = eventHash(withoutHash);
    if (event.hash !== computed) {
      return {
        ok: false,
        checked: index,
        error: `hash mismatch at seq ${event.seq}`,
        at_seq: event.seq
      };
    }
    prevHash = event.hash;
  }
  return { ok: true, checked: events.length };
}

interface LedgerCommonOptions {
  idGenerator?: IdGenerator;
  clock?: Clock;
  initialEvents?: readonly RunLedgerEvent[];
}

function buildEvent(
  input: RunLedgerAppendInput,
  seq: number,
  prevHash: string,
  idGenerator: IdGenerator,
  clock: Clock
): RunLedgerEvent {
  assertLedgerDataSafe(input.data);
  const withoutHash: Omit<RunLedgerEvent, "hash"> = {
    contract_version: "1.0.0",
    seq,
    event_id: idGenerator.eventId(),
    at: nowIso(clock),
    type: input.type,
    workflow_instance_id: input.workflow_instance_id,
    run_id: input.run_id,
    task_id: input.task_id,
    role: input.role,
    data: input.data,
    prev_hash: prevHash
  };
  const event: RunLedgerEvent = {
    ...withoutHash,
    hash: eventHash(withoutHash)
  };
  return deepFreeze(event);
}

function loadInitialEvents(events: readonly RunLedgerEvent[]): RunLedgerEvent[] {
  const verification = verifyLedgerEvents(events);
  if (!verification.ok) {
    throw new FleetPolicyError("ledger-integrity", verification.error ?? "invalid ledger", {
      at_seq: verification.at_seq ?? 0
    });
  }
  return events.map((event) => deepFreeze(event));
}

export class InMemoryRunLedger implements RunLedger {
  #events: RunLedgerEvent[];
  #ids: IdGenerator;
  #clock: Clock;

  constructor(options: LedgerCommonOptions = {}) {
    this.#ids = options.idGenerator ?? new UuidIdGenerator();
    this.#clock = options.clock ?? new SystemClock();
    this.#events =
      options.initialEvents === undefined ? [] : loadInitialEvents(options.initialEvents);
  }

  append(input: RunLedgerAppendInput): RunLedgerEvent {
    const prevHash =
      this.#events.length === 0
        ? GENESIS_HASH
        : (this.#events[this.#events.length - 1] as RunLedgerEvent).hash;
    const event = buildEvent(input, this.#events.length + 1, prevHash, this.#ids, this.#clock);
    this.#events.push(event);
    return event;
  }

  readAll(): readonly RunLedgerEvent[] {
    return this.#events.slice();
  }

  verify(): LedgerVerifyResult {
    return verifyLedgerEvents(this.#events);
  }
}

export interface JsonlRunLedgerOptions extends LedgerCommonOptions {
  filePath: string;
}

export class JsonlRunLedger implements RunLedger {
  #filePath: string;
  #events: RunLedgerEvent[];
  #ids: IdGenerator;
  #clock: Clock;

  constructor(options: JsonlRunLedgerOptions) {
    this.#filePath = options.filePath;
    this.#ids = options.idGenerator ?? new UuidIdGenerator();
    this.#clock = options.clock ?? new SystemClock();
    const loaded: RunLedgerEvent[] = [];
    if (existsSync(this.#filePath)) {
      const text = readFileSync(this.#filePath, "utf8");
      const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
      for (const [index, line] of lines.entries()) {
        let parsed: unknown;
        try {
          parsed = JSON.parse(line) as unknown;
        } catch {
          throw new FleetPolicyError("ledger-integrity", "ledger contains invalid JSON", {
            line: index + 1
          });
        }
        loaded.push(parsed as RunLedgerEvent);
      }
    }
    this.#events = loadInitialEvents(loaded);
  }

  append(input: RunLedgerAppendInput): RunLedgerEvent {
    const prevHash =
      this.#events.length === 0
        ? GENESIS_HASH
        : (this.#events[this.#events.length - 1] as RunLedgerEvent).hash;
    const event = buildEvent(input, this.#events.length + 1, prevHash, this.#ids, this.#clock);
    mkdirSync(dirname(this.#filePath), { recursive: true });
    appendFileSync(this.#filePath, `${canonicalJson(event)}\n`, "utf8");
    this.#events.push(event);
    return event;
  }

  readAll(): readonly RunLedgerEvent[] {
    return this.#events.slice();
  }

  verify(): LedgerVerifyResult {
    return verifyLedgerEvents(this.#events);
  }

  get filePath(): string {
    return this.#filePath;
  }
}
