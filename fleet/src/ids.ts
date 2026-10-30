import { randomUUID } from "node:crypto";

export interface IdGenerator {
  runId(): string;
  workflowInstanceId(): string;
  requestId(): string;
  eventId(): string;
  bindingId(): string;
}

export class UuidIdGenerator implements IdGenerator {
  #make(prefix: string): string {
    return `${prefix}_${randomUUID().replaceAll("-", "")}`;
  }

  runId(): string {
    return this.#make("run");
  }

  workflowInstanceId(): string {
    return this.#make("wfi");
  }

  requestId(): string {
    return this.#make("req");
  }

  eventId(): string {
    return this.#make("evt");
  }

  bindingId(): string {
    return this.#make("bind");
  }
}

export class DeterministicIdGenerator implements IdGenerator {
  #counter = 0;

  #next(prefix: string): string {
    this.#counter += 1;
    return `${prefix}_${String(this.#counter).padStart(32, "0")}`;
  }

  runId(): string {
    return this.#next("run");
  }

  workflowInstanceId(): string {
    return this.#next("wfi");
  }

  requestId(): string {
    return this.#next("req");
  }

  eventId(): string {
    return this.#next("evt");
  }

  bindingId(): string {
    return this.#next("bind");
  }
}

export function resultRefFor(runId: string): string {
  return `result://${runId}`;
}
