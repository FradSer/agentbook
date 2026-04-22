import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

const { fetchRadarMock, fetchMetricsMock, getProblemsListMock } = vi.hoisted(
  () => ({
    fetchRadarMock: vi.fn(),
    fetchMetricsMock: vi.fn(),
    getProblemsListMock: vi.fn(),
  }),
);

vi.mock("@/lib/api", () => ({
  fetchRadar: fetchRadarMock,
  fetchMetrics: fetchMetricsMock,
  getProblems: getProblemsListMock,
  ApiError: class ApiError extends Error {
    readonly statusCode: number;
    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
    }
  },
}));

const emptyRadar = { trending: [], new_unsolved: [], degrading: [] };
const emptyMetrics = {
  resolution_rate: { value: 0, trend: null, target: 0.8 },
  median_ttr_seconds: { value: 0, trend: null, target: 300 },
  avg_solution_confidence: { value: 0, trend: null, target: 0.75 },
  knowledge_coverage: { value: 0, trend: null },
  knowledge_freshness: { value: 0, trend: null, target: 0.6 },
  solutions_needing_synthesis: 0,
  stale_solutions: 0,
};

describe("HomePage — Memory Radar & Metrics tabs", () => {
  beforeEach(() => {
    fetchRadarMock.mockReset();
    fetchMetricsMock.mockReset();
    getProblemsListMock.mockReset();
    fetchRadarMock.mockResolvedValue(emptyRadar);
    fetchMetricsMock.mockResolvedValue(emptyMetrics);
    getProblemsListMock.mockResolvedValue([]);
  });

  it("given home page load when initial data resolves then both primary tabs are visible", async () => {
    render(<HomePage />);
    await waitFor(() => expect(fetchRadarMock).toHaveBeenCalled());
    expect(
      screen.getByRole("tab", { name: "Memory Radar" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Quality Metrics" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tabpanel")).toBeInTheDocument();
  });

  it("shows trending section with activity badge when trending data exists", async () => {
    fetchRadarMock.mockResolvedValue({
      trending: [
        {
          problem_id: "abc",
          description: "pgvector not installed",
          agent_count: 5,
          solution_count: 2,
          resolution_rate: 0.8,
          last_24h_resolve_calls: 10,
        },
      ],
      new_unsolved: [],
      degrading: [],
    });
    render(<HomePage />);
    await waitFor(() => expect(fetchRadarMock).toHaveBeenCalled());

    const radarTab = screen.getByText("Memory Radar");
    await userEvent.click(radarTab);

    await waitFor(() =>
      expect(screen.getByText("Trending")).toBeInTheDocument(),
    );
    expect(screen.getByText("10 in 24h")).toBeInTheDocument();
  });

  it("given metrics data when switching tabs then metric cards are rendered", async () => {
    fetchMetricsMock.mockResolvedValue({
      ...emptyMetrics,
      resolution_rate: { value: 0.78, trend: "+0.03", target: 0.8 },
    });
    render(<HomePage />);

    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());

    const metricsTab = screen.getByText("Quality Metrics");
    await userEvent.click(metricsTab);

    await waitFor(() =>
      expect(screen.getByText("Resolution Rate")).toBeInTheDocument(),
    );
  });
});
