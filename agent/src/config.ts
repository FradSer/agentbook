export interface WorkerConfig {
  apiUrl: string;
  workerApiKey: string;
  cloudflareApiKey: string;
  cloudflareAccountId: string;
  cloudflareGatewayId: string;
  model: string;
  pollIntervalMs: number;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): WorkerConfig {
  const rawInterval = env.PI_WORKER_POLL_INTERVAL_MS ?? "1800000";
  const pollIntervalMs = Number(rawInterval);
  if (!Number.isFinite(pollIntervalMs) || pollIntervalMs <= 0) {
    throw new Error(
      `PI_WORKER_POLL_INTERVAL_MS must be a positive number, got: ${rawInterval}`,
    );
  }

  return {
    apiUrl: env.AGENTBOOK_API_URL ?? "",
    workerApiKey: env.WORKER_API_KEY ?? "",
    cloudflareApiKey: env.CLOUDFLARE_API_KEY ?? "",
    cloudflareAccountId: env.CLOUDFLARE_ACCOUNT_ID ?? "",
    cloudflareGatewayId: env.CLOUDFLARE_GATEWAY_ID ?? "agentbook-gw",
    // Workers AI is the no-provider-balance default for the worker. Operators
    // can override MODEL_ID with a Gateway compat slug (for example a funded
    // dynamic/ route) without changing the deployment artifact.
    model: env.MODEL_ID ?? "workers-ai/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    // Coerce + validate so a typo like "1800000ms" (NaN) or a negative value
    // can't collapse the 30-minute poll cadence to a zero-delay tight loop —
    // setTimeout(resolve, NaN) fires on the next tick, and a fast-failing cycle
    // (backend 401, refused gateway call) would then hammer the API with no
    // backoff. Reject at startup instead.
    pollIntervalMs,
  };
}

export const config = loadConfig();

export function validateConfig(
  candidate: WorkerConfig = config,
  isRailway = Boolean(process.env.RAILWAY_ENVIRONMENT),
): void {
  if (!candidate.apiUrl) throw new Error("apiUrl is required");
  const host = new URL(candidate.apiUrl).hostname;
  if (
    isRailway &&
    (host === "localhost" || host === "127.0.0.1" || host === "::1")
  ) {
    throw new Error("apiUrl must not use a loopback host");
  }
  for (const [name, value] of Object.entries(candidate)) {
    if (
      ["workerApiKey", "cloudflareApiKey", "cloudflareAccountId"].includes(
        name,
      ) &&
      !value
    ) {
      throw new Error(`${name} is required`);
    }
  }
}
