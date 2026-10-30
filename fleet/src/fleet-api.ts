import type {
  CancelResponse,
  ResultResponse,
  StatusResponse,
  SubmitResponse
} from "./api-types.ts";
import type { FleetController } from "./fleet-controller.ts";

/**
 * The fixed DSH Main-facing surface. It exposes exactly four operations and
 * deliberately does not expose host-internal methods such as grantApproval or
 * reconcile.
 */
export class FleetApi {
  #controller: FleetController;

  constructor(controller: FleetController) {
    this.#controller = controller;
  }

  submit(request: unknown, binding: unknown): SubmitResponse {
    return this.#controller.submit(request, binding);
  }

  status(query: unknown, binding: unknown): StatusResponse {
    return this.#controller.status(query, binding);
  }

  result(runId: unknown, binding: unknown): ResultResponse {
    return this.#controller.result(runId, binding);
  }

  cancel(runId: unknown, binding: unknown): Promise<CancelResponse> {
    return this.#controller.cancel(runId, binding);
  }
}
