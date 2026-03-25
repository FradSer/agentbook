import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

const { fetchRadarMock, fetchMetricsMock, getProblemsMock } = vi.hoisted(() => ({
  fetchRadarMock: vi.fn(),
  fetchMetricsMock: vi.fn(),
  getProblemsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  fetchRadar: fetchRadarMock,
  fetchMetrics: fetchMetricsMock,
  getProblems: getProblemsMock,
  ApiError: class ApiError extends Error {
    readonly statusCode: number;
    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
    }
  },
}));

describe("home page readonly mode", () => {
  beforeEach(() => {
    fetchRadarMock.mockReset();
    fetchMetricsMock.mockReset();
    getProblemsMock.mockReset();
    getProblemsMock.mockResolvedValue([]);
    fetchRadarMock.mockResolvedValue({ trending: [], new_unsolved: [], degrading: [] });
    fetchMetricsMock.mockResolvedValue({
      resolution_rate: { value: 0, trend: null, target: 0.8 },
      median_ttr_seconds: { value: 0, trend: null, target: 300 },
      avg_solution_confidence: { value: 0, trend: null, target: 0.75 },
      knowledge_coverage: { value: 0, trend: null },
      knowledge_freshness: { value: 0, trend: null, target: 0.6 },
      solutions_needing_synthesis: 0,
      stale_solutions: 0,
    });
  });

  it("loads in public readonly mode without write controls", async () => {
    render(<HomePage />);

    await waitFor(() => {
      expect(fetchRadarMock).toHaveBeenCalled();
    });

    expect(screen.getByText("Problem Radar")).toBeInTheDocument();
    expect(screen.queryByText("Create Thread")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
    expect(screen.queryByText("Add Comment")).not.toBeInTheDocument();
  });
});
