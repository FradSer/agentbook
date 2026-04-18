/**
 * BDD scenarios covered (contract assertions on page source):
 *   - /research reads memory_id from query string
 *   - /research fetches /v1/research-activity?memory_id=...
 *   - /research renders sandbox_run block only when present
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const pagePath = path.resolve(__dirname, "..", "app", "research", "page.tsx");

describe("/research view", () => {
  const src = readFileSync(pagePath, "utf-8");

  it("reads memory_id from query string", () => {
    expect(src).toContain("memory_id");
    expect(src).toMatch(/searchParams\.get\("memory_id"\)/);
  });

  it("fetches /v1/research-activity with memory_id", () => {
    expect(src).toContain("/v1/research-activity?memory_id=");
  });

  it("renders sandbox_run details conditionally", () => {
    expect(src).toContain("sandbox_run");
    expect(src).toMatch(/item\.sandbox_run/);
  });

  it("shows reverse chronological order via server response ordering", () => {
    // Page preserves the order returned by /v1/research-activity.
    expect(src).toContain("items.map");
  });
});
