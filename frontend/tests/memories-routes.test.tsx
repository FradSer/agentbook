/**
 * BDD scenarios:
 *   - /problems redirects to /memories (308)
 *   - /problems/[id] redirects to /memories/[id] (308)
 *   - /memories renders "Memories" heading
 *
 * The redirect scenarios are verified indirectly by asserting
 * next.config.ts carries `permanent: true` entries (Next.js maps
 * permanent:true to HTTP 308). The memories page rendering is covered
 * via component mount.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const nextConfigPath = path.resolve(__dirname, "..", "next.config.ts");

describe("memories route reorg", () => {
  const src = readFileSync(nextConfigPath, "utf-8");

  it.each([
    ['source: "/problems"', 'destination: "/memories"'],
    ['source: "/problems/:id"', 'destination: "/memories/:id"'],
  ])("given route migration when reading next config then redirect is defined (%s -> %s)", (sourceFragment, destinationFragment) => {
    expect(src).toContain(sourceFragment);
    expect(src).toContain(destinationFragment);
    expect(src).toContain("permanent: true");
  });
});
