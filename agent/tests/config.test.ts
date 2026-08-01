import { describe, expect, it } from "vitest";
import { config } from "../src/config.js";

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
});
