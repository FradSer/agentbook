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
  pollIntervalMs: Number(process.env.PI_WORKER_POLL_INTERVAL_MS ?? 1_800_000),
};

export function validateConfig(): void {
  for (const [name, value] of Object.entries(config)) {
    if (["workerApiKey", "cloudflareApiKey", "cloudflareAccountId"].includes(name) && !value) {
      throw new Error(`${name} is required`);
    }
  }
}
