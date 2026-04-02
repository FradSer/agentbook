import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAgentAvatar, getRelativeTime, gradientFromSeed } from "@/lib/utils";

describe("getRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-06-15T12:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns empty string for invalid date", () => {
    expect(getRelativeTime("not-a-date")).toBe("");
  });

  it("describes a past time in hours", () => {
    const past = "2025-06-15T10:00:00.000Z";
    expect(getRelativeTime(past)).toMatch(/hour/i);
  });

  it("describes a future time", () => {
    const future = "2025-06-15T14:00:00.000Z";
    expect(getRelativeTime(future)).toMatch(/hour/i);
  });
});

describe("gradientFromSeed", () => {
  it("returns deterministic hsl() stops for the same seed", () => {
    const a = gradientFromSeed("stable-id-for-test");
    const b = gradientFromSeed("stable-id-for-test");
    expect(a).toEqual(b);
    expect(a.from).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
    expect(a.to).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
  });

  it("usually differs for different seeds", () => {
    const x = gradientFromSeed("id-a");
    const y = gradientFromSeed("id-b");
    expect(x.from !== y.from || x.to !== y.to).toBe(true);
  });
});

describe("getAgentAvatar", () => {
  it("returns hsl gradient stops derived from id", () => {
    const { gradient } = getAgentAvatar("stable-id-for-test");
    expect(gradient[0]).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
    expect(gradient[1]).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
  });
});
