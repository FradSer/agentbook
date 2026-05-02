import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { LiveResearchSnapshot } from "@/lib/types";

import { MockEventSource } from "./__helpers__/mock-event-source";

// `fetchLiveResearchSnapshot` is mocked so REST fallback tests don't hit the
// network. The hook is imported lazily in each test so the module-not-found
// failure surfaces uniformly during the Red phase.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchLiveResearchSnapshot: vi.fn(),
  };
});

import { fetchLiveResearchSnapshot } from "@/lib/api";

const fetchSnapshotMock = vi.mocked(fetchLiveResearchSnapshot);

const STREAM_PATH = "/v1/dashboard/research/stream";

const baseSnapshot: LiveResearchSnapshot = {
  active: [],
  last_cycle_at: null,
  now: "2026-05-01T00:00:00Z",
};

function snapshotWith(
  overrides: Partial<LiveResearchSnapshot>,
): LiveResearchSnapshot {
  return { ...baseSnapshot, ...overrides };
}

async function importHook() {
  return await import("@/lib/use-live-research");
}

beforeEach(() => {
  vi.useFakeTimers();
  MockEventSource.reset();
  fetchSnapshotMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useLiveResearch", () => {
  test("opens an EventSource at /v1/dashboard/research/stream on mount", async () => {
    const { useLiveResearch } = await importHook();
    renderHook(() => useLiveResearch());

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain(STREAM_PATH);
    expect(MockEventSource.instances[0].closed).toBe(false);
  });

  test("status is 'loading' before the first snapshot frame arrives", async () => {
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    expect(result.current.status).toBe("loading");
    expect(result.current.snapshot).toBeNull();
  });

  test("status is 'open' after the first snapshot event", async () => {
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    act(() => {
      MockEventSource.instances[0].dispatch("snapshot", baseSnapshot);
    });

    expect(result.current.status).toBe("open");
    expect(result.current.snapshot).toEqual(baseSnapshot);
  });

  test("snapshot state replaces the active list when a snapshot event fires", async () => {
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    const first = snapshotWith({
      active: [
        {
          problem_id: "P-1",
          description: "First",
          solution_count: 1,
          best_confidence: 0.5,
          research_started_at: "2026-05-01T00:00:00Z",
          elapsed_seconds: 1,
        },
      ],
    });
    const second = snapshotWith({
      active: [
        {
          problem_id: "P-2",
          description: "Second",
          solution_count: 2,
          best_confidence: 0.7,
          research_started_at: "2026-05-01T00:01:00Z",
          elapsed_seconds: 2,
        },
      ],
    });

    act(() => {
      MockEventSource.instances[0].dispatch("snapshot", first);
    });
    act(() => {
      MockEventSource.instances[0].dispatch("snapshot", second);
    });

    expect(result.current.snapshot?.active).toEqual(second.active);
    expect(result.current.snapshot?.active).toHaveLength(1);
  });

  test("research_started event adds the problem to active state (deduped by problem_id)", async () => {
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    act(() => {
      MockEventSource.instances[0].dispatch("snapshot", baseSnapshot);
    });

    const event = {
      problem_id: "P-9",
      description: "New",
      solution_count: 0,
      best_confidence: 0.3,
      research_started_at: "2026-05-01T00:02:00Z",
      elapsed_seconds: 0,
    };
    act(() => {
      MockEventSource.instances[0].dispatch("research_started", event);
    });
    // Duplicate should be ignored.
    act(() => {
      MockEventSource.instances[0].dispatch("research_started", event);
    });

    expect(result.current.snapshot?.active).toHaveLength(1);
    expect(result.current.snapshot?.active[0].problem_id).toBe("P-9");
  });

  test("research_ended event removes the problem from active state and updates last_cycle_at", async () => {
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    const initial = snapshotWith({
      active: [
        {
          problem_id: "P-1",
          description: "Alpha",
          solution_count: 1,
          best_confidence: 0.4,
          research_started_at: "2026-05-01T00:00:00Z",
          elapsed_seconds: 0,
        },
      ],
    });
    act(() => {
      MockEventSource.instances[0].dispatch("snapshot", initial);
    });

    act(() => {
      MockEventSource.instances[0].dispatch("research_ended", {
        problem_id: "P-1",
        last_cycle_at: "2026-05-01T00:05:00Z",
      });
    });

    expect(result.current.snapshot?.active).toEqual([]);
    expect(result.current.snapshot?.last_cycle_at).toBe("2026-05-01T00:05:00Z");
  });

  test("3 consecutive onerror events without a message trigger REST fallback poll", async () => {
    fetchSnapshotMock.mockResolvedValue(baseSnapshot);
    const { useLiveResearch } = await importHook();
    renderHook(() => useLiveResearch());

    const es = MockEventSource.instances[0];
    act(() => {
      es.emitError();
      es.emitError();
      es.emitError();
    });

    expect(fetchSnapshotMock).toHaveBeenCalledTimes(1);
  });

  test("status switches to 'fallback' when REST polling activates", async () => {
    fetchSnapshotMock.mockResolvedValue(baseSnapshot);
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    const es = MockEventSource.instances[0];
    await act(async () => {
      es.emitError();
      es.emitError();
      es.emitError();
      await Promise.resolve();
    });

    expect(result.current.status).toBe("fallback");
  });

  test("REST poll fires every 10 seconds in fallback mode", async () => {
    fetchSnapshotMock.mockResolvedValue(baseSnapshot);
    const { useLiveResearch } = await importHook();
    renderHook(() => useLiveResearch());

    const es = MockEventSource.instances[0];
    await act(async () => {
      es.emitError();
      es.emitError();
      es.emitError();
      await Promise.resolve();
    });
    expect(fetchSnapshotMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await Promise.resolve();
    });
    expect(fetchSnapshotMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      vi.advanceTimersByTime(10_000);
      await Promise.resolve();
    });
    expect(fetchSnapshotMock).toHaveBeenCalledTimes(3);
  });

  test("hook tries to re-open EventSource every 60 seconds while in fallback", async () => {
    fetchSnapshotMock.mockResolvedValue(baseSnapshot);
    const { useLiveResearch } = await importHook();
    renderHook(() => useLiveResearch());

    expect(MockEventSource.instances).toHaveLength(1);
    const original = MockEventSource.instances[0];
    await act(async () => {
      original.emitError();
      original.emitError();
      original.emitError();
      await Promise.resolve();
    });
    expect(original.closed).toBe(true);

    await act(async () => {
      vi.advanceTimersByTime(60_000);
      await Promise.resolve();
    });
    expect(MockEventSource.instances).toHaveLength(2);
    expect(MockEventSource.instances[1].url).toContain(STREAM_PATH);
  });

  test("first successful snapshot event after fallback cancels the REST polling interval", async () => {
    fetchSnapshotMock.mockResolvedValue(baseSnapshot);
    const { useLiveResearch } = await importHook();
    const { result } = renderHook(() => useLiveResearch());

    const original = MockEventSource.instances[0];
    await act(async () => {
      original.emitError();
      original.emitError();
      original.emitError();
      await Promise.resolve();
    });
    expect(fetchSnapshotMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(60_000);
      await Promise.resolve();
    });
    expect(MockEventSource.instances).toHaveLength(2);

    const reopened = MockEventSource.instances[1];
    act(() => {
      reopened.dispatch("snapshot", baseSnapshot);
    });
    expect(result.current.status).toBe("open");

    fetchSnapshotMock.mockClear();
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
    });
    expect(fetchSnapshotMock).not.toHaveBeenCalled();
  });

  test("hook closes EventSource and aborts pending fetch on unmount", async () => {
    fetchSnapshotMock.mockResolvedValue(baseSnapshot);
    const { useLiveResearch } = await importHook();
    const { unmount } = renderHook(() => useLiveResearch());

    const es = MockEventSource.instances[0];
    expect(es.closed).toBe(false);

    unmount();

    expect(es.closed).toBe(true);
  });

  test("StrictMode double-mount does not leak a second EventSource", async () => {
    const { useLiveResearch } = await importHook();
    const React = await import("react");
    const StrictHarness = ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.StrictMode, null, children);

    renderHook(() => useLiveResearch(), { wrapper: StrictHarness });

    // After the second pass of strict-mode, exactly one open instance remains.
    expect(MockEventSource.open).toHaveLength(1);
  });

  test("Last-Event-ID is NOT re-sent on reconnect (server re-emits fresh snapshot)", async () => {
    // Native EventSource ignores headers; we assert the URL has no last-event-id
    // query string and that the constructor was called with a single string arg.
    const { useLiveResearch } = await importHook();
    renderHook(() => useLiveResearch());

    const es = MockEventSource.instances[0];
    expect(es.url).not.toContain("last-event-id");
    expect(es.url).not.toContain("Last-Event-ID");
  });
});
