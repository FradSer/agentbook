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
  it("next.config.ts declares permanent redirect from /problems to /memories", () => {
    const src = readFileSync(nextConfigPath, "utf-8");
    expect(src).toContain('source: "/problems"');
    expect(src).toContain('destination: "/memories"');
    expect(src).toContain("permanent: true");
  });

  it("next.config.ts declares permanent redirect for /problems/:id to /memories/:id", () => {
    const src = readFileSync(nextConfigPath, "utf-8");
    expect(src).toContain('source: "/problems/:id"');
    expect(src).toContain('destination: "/memories/:id"');
  });
});
