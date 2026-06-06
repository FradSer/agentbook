import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { LiveResearchSnapshot } from "@/lib/types";

vi.mock("@/lib/use-live-research", () => ({
  useLiveResearch: vi.fn(),
}));

import { useLiveResearch } from "@/lib/use-live-research";

const useLiveResearchMock = vi.mocked(useLiveResearch);

async function importBanner() {
  return await import("@/components/app/live-research-banner");
}

const NOW_ISO = "2026-05-01T00:00:00Z";
const NOW_MS = new Date(NOW_ISO).getTime();

function startedSecondsAgo(seconds: number): string {
  return new Date(NOW_MS - seconds * 1000).toISOString();
}

function activeSnapshot(
  count = 1,
  override: Partial<LiveResearchSnapshot> = {},
): LiveResearchSnapshot {
  return {
    active: Array.from({ length: count }, (_, i) => ({
      problem_id: `P-${count - i}`,
      description: `Problem ${count - i} long description that may overflow the inline ribbon when truncated`,
      solution_count: 4 - i,
      best_confidence: 0.72 - i * 0.05,
      research_started_at: startedSecondsAgo(15 + i * 30),
      elapsed_seconds: 15 + i * 30,
    })),
    last_cycle_at: "2026-04-30T23:57:00Z",
    now: NOW_ISO,
    ...override,
  };
}

function setHook(
  snapshot: LiveResearchSnapshot | null,
  status: "loading" | "open" | "fallback" | "error" = "open",
) {
  useLiveResearchMock.mockReturnValue({ snapshot, status });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW_ISO));
  useLiveResearchMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("<LiveResearchBanner/>", () => {
  test("renders active problem title, solution count, and confidence percent", async () => {
    const snap = activeSnapshot(1);
    setHook(snap);
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    expect(screen.getByText(/Problem 1/)).toBeInTheDocument();
    expect(screen.getByText(/4/)).toBeInTheDocument();
    expect(screen.getByText(/72%/)).toBeInTheDocument();
  });

  test("active link points at /memories/{problem_id}", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/memories/P-1");
  });

  test("renders 'started Xs ago' sublabel using getRelativeTime", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    expect(screen.getByText(/started/i)).toBeInTheDocument();
    expect(screen.getByText(/started .*seconds? ago/i)).toBeInTheDocument();
  });

  test("multi-problem state foregrounds the most-recent and shows '+N more in flight'", async () => {
    setHook(activeSnapshot(3));
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    // Active list is server-DESC so active[0] is the most-recently-started.
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/memories/P-3");
    expect(screen.getByText(/\+2 more in flight/)).toBeInTheDocument();
  });

  test("idle state with last_cycle_at renders 'Idle - last cycle Xm ago'", async () => {
    setHook({
      active: [],
      last_cycle_at: new Date(NOW_MS - 3 * 60 * 1000).toISOString(),
      now: NOW_ISO,
    });
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    expect(screen.getByText(/^Idle$/)).toBeInTheDocument();
    expect(screen.getByText(/Last completed run 3 minutes ago/i)).toBeInTheDocument();
    expect(screen.getByText(/Last run/i)).toBeInTheDocument();
  });

  test("idle state with last_cycle_at=null renders 'Idle - awaiting first cycle'", async () => {
    setHook({ active: [], last_cycle_at: null, now: NOW_ISO });
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    expect(
      screen.getByText(/has not completed a research cycle yet/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/awaiting first cycle/i)).toBeInTheDocument();
  });

  test("transitions between active and idle do not render a skeleton or shimmer", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { rerender, container } = render(<LiveResearchBanner />);

    setHook({ active: [], last_cycle_at: NOW_ISO, now: NOW_ISO });
    rerender(<LiveResearchBanner />);

    expect(container.querySelector(".animate-pulse")).toBeNull();
    expect(container.querySelector("[data-skeleton]")).toBeNull();
    expect(container.querySelector(".shimmer")).toBeNull();
  });

  test("uses REST snapshot for initial paint, no idle flash before first SSE frame", async () => {
    // Hook still loading, but caller passes initialSnapshot — banner must
    // render the initial active rather than the idle state.
    setHook(null, "loading");
    const initial = activeSnapshot(1);
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner initialSnapshot={initial} />);

    expect(screen.getByText(/Problem 1/)).toBeInTheDocument();
    expect(screen.queryByText(/^Idle$/)).toBeNull();
  });

  test("applies .research-active class on active container", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { container } = render(<LiveResearchBanner />);

    expect(container.querySelector(".research-active")).not.toBeNull();
  });

  test("applies .researching-dot class on the indicator", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { container } = render(<LiveResearchBanner />);

    expect(container.querySelector(".researching-dot")).not.toBeNull();
  });

  test("applies Researching badge variant via shared Badge component", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    expect(screen.getByText(/Researching/)).toBeInTheDocument();
  });

  test("does not define any new CSS custom properties", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { container } = render(<LiveResearchBanner />);

    // Inline `style` attributes containing `--something:` would indicate a new
    // CSS custom property defined in this component — disallowed.
    const inline = container.querySelectorAll("[style]");
    for (const el of Array.from(inline)) {
      const style = el.getAttribute("style") ?? "";
      expect(style.includes("--research-")).toBe(false);
    }
  });

  test("description renders with line-clamp-1 class and full text in accessible name", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { container } = render(<LiveResearchBanner />);

    expect(container.querySelector(".line-clamp-1")).not.toBeNull();
    const link = screen.getByRole("link");
    const accessibleName =
      link.getAttribute("aria-label") ?? link.textContent ?? "";
    expect(accessibleName).toContain("Problem 1 long description");
  });

  test("respects prefers-reduced-motion (asserts no inline animation override)", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { container } = render(<LiveResearchBanner />);

    // The animation rule lives in globals.css behind a media query — the
    // component must not inject inline `animation:` overrides.
    const inline = container.querySelectorAll("[style]");
    for (const el of Array.from(inline)) {
      const style = el.getAttribute("style") ?? "";
      expect(style.includes("animation")).toBe(false);
    }
  });

  test("link is keyboard-focusable with focusRing utility classes", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    const link = screen.getByRole("link");
    const cls = link.getAttribute("class") ?? "";
    expect(cls).toContain("focus-visible:ring-coral");
  });

  test("role='status' and aria-live='polite' on banner element", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    render(<LiveResearchBanner />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveAttribute("aria-atomic", "false");
  });

  test("aria-live debounce: 2 transitions within 500ms yield 1 announce", async () => {
    setHook(activeSnapshot(1));
    const { LiveResearchBanner } = await importBanner();
    const { rerender, container } = render(<LiveResearchBanner />);

    // First transition.
    setHook(activeSnapshot(2));
    rerender(<LiveResearchBanner />);
    act(() => {
      vi.advanceTimersByTime(500);
    });
    // Second transition within the 1s debounce window.
    setHook(activeSnapshot(3));
    rerender(<LiveResearchBanner />);

    // Before the debounce expires the announcement region should still hold
    // a single, stable text snapshot.
    const announcer = container.querySelector(
      '[data-testid="live-research-announcer"]',
    );
    const beforeDebounce = announcer?.textContent ?? "";

    // Once 1s elapses since the last update the announcer flushes once.
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    const afterDebounce = announcer?.textContent ?? "";
    expect(afterDebounce).not.toBe(beforeDebounce);
  });

  test("status='fallback' renders quiet '(reconnecting)' hint without destructive alert", async () => {
    setHook(activeSnapshot(1), "fallback");
    const { LiveResearchBanner } = await importBanner();
    const { container } = render(<LiveResearchBanner />);

    expect(screen.getByText(/\(reconnecting\)/)).toBeInTheDocument();
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });
});
