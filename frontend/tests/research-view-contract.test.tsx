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

  it.each([
    "memory_id",
    "/v1/research-activity?memory_id=",
    "sandbox_run",
    "items.map",
  ])("given research page source when validating contract then fragment %s is present", (fragment) => {
    expect(src).toContain(fragment);
  });

  it.each([
    /searchParams\.get\("memory_id"\)/,
    /item\.sandbox_run/,
  ])("given research page source when validating behavior then expression %s matches", (pattern) => {
    expect(src).toMatch(pattern);
  });
});
