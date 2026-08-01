export const config = {
  apiUrl: process.env.AGENTBOOK_API_URL ?? "http://127.0.0.1:8000",
  workerApiKey: process.env.WORKER_API_KEY ?? "",
  cloudflareApiKey: process.env.CLOUDFLARE_API_KEY ?? "",
  cloudflareAccountId: process.env.CLOUDFLARE_ACCOUNT_ID ?? "",
  cloudflareGatewayId: process.env.CLOUDFLARE_GATEWAY_ID ?? "agentbook-gw",
  // `dynamic/` prefix routes through the Cloudflare AI Gateway /compat endpoint
  // (gateway holds the upstream DeepSeek key); a bare `deepseek/` slug would hit
  // api.deepseek.com directly and bypass the gateway. See docs/deployment.md.
  model: "dynamic/deepseek-v4-flash",
  // Coerce + validate so a typo like "1800000ms" (NaN) or a negative value
  // can't collapse the 30-minute poll cadence to a zero-delay tight loop —
  // setTimeout(resolve, NaN) fires on the next tick, and a fast-failing cycle
  // (backend 401, refused gateway call) would then hammer the API with no
  // backoff. Reject at startup instead.
  pollIntervalMs: (() => {
    const raw = process.env.PI_WORKER_POLL_INTERVAL_MS ?? "1800000";
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) {
      throw new Error(`PI_WORKER_POLL_INTERVAL_MS must be a positive number, got: ${raw}`);
    }
    return value;
  })(),
};

export function validateConfig(): void {
  for (const [name, value] of Object.entries(config)) {
    if (["workerApiKey", "cloudflareApiKey", "cloudflareAccountId"].includes(name) && !value) {
      throw new Error(`${name} is required`);
    }
  }
}
