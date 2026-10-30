import { deepFreeze, sha256OfJson } from "./canonical-json.ts";
import type { WorkerResultEnvelope } from "./worker-result.ts";
import { resultRefFor } from "./ids.ts";

export interface StoredResult {
  result_ref: string;
  result_sha256: string;
  envelope: WorkerResultEnvelope;
}

export interface ResultStore {
  put(envelope: WorkerResultEnvelope): StoredResult;
  get(resultRef: string): StoredResult | undefined;
}

export class InMemoryResultStore implements ResultStore {
  #byRef = new Map<string, StoredResult>();

  put(envelope: WorkerResultEnvelope): StoredResult {
    const resultRef = resultRefFor(envelope.run_id);
    const stored = deepFreeze<StoredResult>({
      result_ref: resultRef,
      result_sha256: sha256OfJson(envelope),
      envelope
    });
    this.#byRef.set(resultRef, stored);
    return stored;
  }

  get(resultRef: string): StoredResult | undefined {
    return this.#byRef.get(resultRef);
  }
}
