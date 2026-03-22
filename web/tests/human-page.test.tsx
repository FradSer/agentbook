import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HumanPage from "@/app/human/page";

const { fetchRadarMock, fetchMetricsMock, getProblemsListMock } = vi.hoisted(() => ({
  fetchRadarMock: vi.fn(),
  fetchMetricsMock: vi.fn(),
  getProblemsListMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  fetchRadar: fetchRadarMock,
  fetchMetrics: fetchMetricsMock,
  getProblems: getProblemsListMock,
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

describe("HumanPage — Problem Radar", () => {
  beforeEach(() => {
    fetchRadarMock.mockReset();
    fetchMetricsMock.mockReset();
    getProblemsListMock.mockReset();
    fetchRadarMock.mockResolvedValue(emptyRadar);
    fetchMetricsMock.mockResolvedValue(emptyMetrics);
    getProblemsListMock.mockResolvedValue([]);
  });

  it("renders Problem Radar and Quality Metrics tabs", async () => {
    render(<HumanPage />);
    await waitFor(() => expect(fetchRadarMock).toHaveBeenCalled());
    expect(screen.getByRole("heading", { level: 1, name: /human dashboard/i })).toBeInTheDocument();
    expect(screen.getByText("Problem Radar")).toBeInTheDocument();
    expect(screen.getByText("Quality Metrics")).toBeInTheDocument();
    expect(document.getElementById("human-panel-problems")).toHaveAttribute("role", "tabpanel");
  });

  it("shows TRENDING badge when trending data exists", async () => {
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
    render(<HumanPage />);
    await waitFor(() => expect(fetchRadarMock).toHaveBeenCalled());

    // Navigate to Problem Radar tab
    const radarTab = screen.getByText("Problem Radar");
    await userEvent.click(radarTab);

    await waitFor(() => expect(screen.getByText("TRENDING")).toBeInTheDocument());
  });

  it("shows empty state when all sections are empty", async () => {
    render(<HumanPage />);
    // Default tab is "problems" and empty list shows "No problems yet."
    await waitFor(() =>
      expect(screen.getByRole("tabpanel", { name: "Problems" })).toHaveTextContent("No problems yet.")
    );
  });

  it("switches to metrics tab and shows metric cards", async () => {
    fetchMetricsMock.mockResolvedValue({
      ...emptyMetrics,
      resolution_rate: { value: 0.78, trend: "+0.03", target: 0.8 },
    });
    render(<HumanPage />);

    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());

    const metricsTab = screen.getByText("Quality Metrics");
    await userEvent.click(metricsTab);

    await waitFor(() =>
      expect(screen.getByText("Resolution Rate")).toBeInTheDocument()
    );
  });
});
