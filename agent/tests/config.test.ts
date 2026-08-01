import { describe, expect, it } from "vitest";
import { config, loadConfig, validateConfig } from "../src/config.js";

describe("config", () => {
  it("parses a positive PI_WORKER_POLL_INTERVAL_MS", () => {
    // The default or a set positive value must be a finite positive number so
    // setTimeout(resolve, pollIntervalMs) does not collapse to a zero-delay
    // tight loop on a fast-failing cycle.
    expect(Number.isFinite(config.pollIntervalMs)).toBe(true);
    expect(config.pollIntervalMs).toBeGreaterThan(0);
  });

  it("resolves the dynamic gateway model id", () => {
    expect(config.model).toBe("dynamic/deepseek-v4-flash");
  });

  it("requires a backend API URL and rejects loopback on Railway", () => {
    expect(() =>
      validateConfig(
        loadConfig({
          WORKER_API_KEY: "worker-key",
          CLOUDFLARE_API_KEY: "gateway-key",
          CLOUDFLARE_ACCOUNT_ID: "account-id",
        }),
      ),
    ).toThrow("apiUrl is required");

    expect(() =>
      validateConfig(
        loadConfig({
          AGENTBOOK_API_URL: "http://127.0.0.1:8000",
          WORKER_API_KEY: "worker-key",
          CLOUDFLARE_API_KEY: "gateway-key",
          CLOUDFLARE_ACCOUNT_ID: "account-id",
        }),
        true,
      ),
    ).toThrow("must not use a loopback host");
  });
});
