/**
 * BDD scenarios covered (structural + source assertions):
 *   - /health renders sandbox pass rate
 *   - /health renders "Inflated-confidence alerts (24h): N"
 *   - /health has no write surfaces (form elements, mutation buttons)
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const pagePath = path.resolve(__dirname, "..", "app", "health", "page.tsx");

describe("/health view", () => {
  const src = readFileSync(pagePath, "utf-8");

  it("renders Sandbox pass rate label", () => {
    expect(src).toContain("Sandbox pass rate (24h)");
  });

  it("renders Inflated-confidence alerts label", () => {
    expect(src).toContain("Inflated-confidence alerts (24h)");
  });

  it("fetches /v1/health-metrics", () => {
    expect(src).toContain("/v1/health-metrics");
  });

  it("has no form elements or mutation buttons", () => {
    expect(src).not.toMatch(/<form/);
    expect(src).not.toMatch(/<button/i);
    expect(src).not.toMatch(/onSubmit/);
  });

  it("uses server component revalidate cache (matches backend 30s TTL)", () => {
    expect(src).toContain("revalidate: 30");
  });
});
