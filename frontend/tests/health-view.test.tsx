/**
 * BDD scenarios covered (structural + source assertions):
 *   - /health renders sandbox pass rate
 *   - /health renders "Inflated-confidence alerts (24h): N"
 *   - /health surfaces flywheel usage and outcome-source classification
 *     (organic share is what the G3/G4 pilot gates read, never raw volume)
 *   - /health has no write surfaces (form elements, mutation buttons)
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const pagePath = path.resolve(__dirname, "..", "app", "health", "page.tsx");

describe("/health view", () => {
  const src = readFileSync(pagePath, "utf-8");
  const requiredFragments = [
    "Sandbox pass rate (24h)",
    "Inflated-confidence alerts (24h)",
    "fetchHealthMetrics",
    "fetchUsageDashboard",
    "Flywheel usage",
    "Outcome traffic by source",
    "Organic share (30d)",
    "organic_external",
    "author_self",
    "Author self-reports",
    "@/lib/api",
  ] as const;

  it.each(
    requiredFragments,
  )("given health page source when inspected then it contains %s", (fragment) => {
    expect(src).toContain(fragment);
  });

  it.each([
    /<form/,
    /<button/i,
    /onSubmit/,
  ])("given health page source when checking read-only contract then it excludes %s", (forbiddenToken) => {
    expect(src).not.toMatch(forbiddenToken);
  });
});
