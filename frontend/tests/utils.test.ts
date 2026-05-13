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

  it("given invalid date string when formatting then returns empty string", () => {
    expect(getRelativeTime("not-a-date")).toBe("");
  });

  it.each([
    "2025-06-15T10:00:00.000Z",
    "2025-06-15T14:00:00.000Z",
  ])("given valid date %s when formatting then returns hour-based relative description", (timestamp) => {
    expect(getRelativeTime(timestamp)).toMatch(/hour/i);
  });
});

describe("gradientFromSeed", () => {
  it("given same seed when generating gradient then hsl values are deterministic", () => {
    const a = gradientFromSeed("stable-id-for-test");
    const b = gradientFromSeed("stable-id-for-test");
    expect(a).toEqual(b);
    expect(a.from).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
    expect(a.to).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
  });

  it("given different seeds when generating gradient then at least one stop differs", () => {
    const x = gradientFromSeed("id-a");
    const y = gradientFromSeed("id-b");
    expect(x.from !== y.from || x.to !== y.to).toBe(true);
  });
});

describe("getAgentAvatar", () => {
  it("given stable id when deriving avatar then both gradient stops use hsl format", () => {
    const { gradient } = getAgentAvatar("stable-id-for-test");
    expect(gradient[0]).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
    expect(gradient[1]).toMatch(/^hsl\(\d+ \d+% \d+%\)$/);
  });
});
