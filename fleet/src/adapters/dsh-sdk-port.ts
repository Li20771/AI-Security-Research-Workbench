/**
 * Narrow port over the official `@deepseek-ai/dsh-sdk-client` surface.
 *
 * The Fleet adapter deliberately depends on this port rather than importing
 * the official package directly. A deployment supplies a factory that wraps
 * `DeepSeekHarness`/`HarnessClient`; fake tests supply an in-memory harness.
 * This keeps the Fleet package installable without the SDK and makes the
 * official SDK's evolving API a deployment concern, not a Fleet contract.
 */

export interface DshSdkNotification {
  method: string;
  params: Record<string, unknown>;
}

export interface DshSdkRunOptions {
  sessionId?: string;
  onNotification?: (notification: DshSdkNotification) => void;
}

export interface DshSdkRunResult {
  sessionId: string;
  finalResponse: string;
}

export interface DshSdkSession {
  run(input: string, options?: DshSdkRunOptions): Promise<DshSdkRunResult>;
}

export interface DshSdkHarness {
  start(): Promise<void>;
  session(id?: string): DshSdkSession;
  close(): Promise<void>;
  getWorkingDirectory?(sessionId: string): Promise<string>;
  setWorkingDirectory?(sessionId: string, path: string): Promise<string>;
}

export interface DshSdkHarnessOptions {
  dshBin: string;
  profile: string;
  patches?: readonly string[];
  dshHome: string;
  cwd: string;
  env: Record<string, string>;
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  initializeTimeoutMs?: number;
}

export interface DshSdkFactory {
  create(options: DshSdkHarnessOptions): DshSdkHarness;
}
