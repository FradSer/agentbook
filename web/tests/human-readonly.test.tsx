import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HumanPage from "@/app/human/page";
import { NavBar } from "@/components/app/nav-bar";

const { pushMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
  }),
}));

const { fetchRadarMock, fetchMetricsMock } = vi.hoisted(() => ({
  fetchRadarMock: vi.fn(),
  fetchMetricsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  fetchRadar: fetchRadarMock,
  fetchMetrics: fetchMetricsMock,
}));

describe("human readonly mode", () => {
  beforeEach(() => {
    fetchRadarMock.mockReset();
    fetchMetricsMock.mockReset();
    pushMock.mockReset();
    window.localStorage.clear();
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
    render(<HumanPage />);

    await waitFor(() => {
      expect(fetchRadarMock).toHaveBeenCalled();
    });

    expect(screen.getByText("Problem Radar")).toBeInTheDocument();
    expect(screen.queryByText("Create Thread")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
    expect(screen.queryByText("Add Comment")).not.toBeInTheDocument();
  });

  it("hides search in navbar for human role", async () => {
    window.localStorage.setItem("agentbook_role", "human");

    render(<NavBar />);

    await waitFor(() => {
      expect(screen.getByText("Switch to Agent")).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "Search" })).not.toBeInTheDocument();
  });

  it("syncs navbar role when role changes in current tab", async () => {
    window.localStorage.setItem("agentbook_role", "human");

    render(<NavBar />);

    await waitFor(() => {
      expect(screen.getByText("Switch to Agent")).toBeInTheDocument();
    });

    act(() => {
      window.localStorage.setItem("agentbook_role", "agent");
      window.dispatchEvent(new Event("agentbook-role-change"));
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Search" })).toBeInTheDocument();
    });
    expect(screen.getByText("Switch to Human")).toBeInTheDocument();
  });
});
