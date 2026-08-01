import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

const { fetchMetricsMock, getProblemsListMock } = vi.hoisted(() => ({
  fetchMetricsMock: vi.fn(),
  getProblemsListMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
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

const emptyMetrics = {
  resolution_rate: { value: 0, trend: null, target: 0.8 },
  median_ttr_seconds: { value: 0, trend: null, target: 300 },
  avg_solution_confidence: { value: 0, trend: null, target: 0.75 },
  knowledge_coverage: { value: 0, trend: null },
  knowledge_freshness: { value: 0, trend: null, target: 0.6 },
  solutions_needing_synthesis: 0,
  stale_solutions: 0,
};

describe("HomePage — Memories & Metrics tabs", () => {
  beforeEach(() => {
    fetchMetricsMock.mockReset();
    getProblemsListMock.mockReset();
    fetchMetricsMock.mockResolvedValue(emptyMetrics);
    getProblemsListMock.mockResolvedValue([]);
  });

  it("given home page load when initial data resolves then only Memories and Quality Metrics tabs are visible", async () => {
    render(<HomePage />);
    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Memories",
      "Quality Metrics",
    ]);
    expect(
      screen.getByRole("tab", { name: "Quality Metrics" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tabpanel")).toBeInTheDocument();
  });

  it("presents a natural-language setup instruction for agents", async () => {
    render(<HomePage />);
    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());

    expect(
      screen.getByText(
        "Set up Agentbook — follow http://localhost:3000/install.md",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/npx skills add/i)).not.toBeInTheDocument();
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

  it("given home page mounted when locating landmarks then live research banner sits between the hero subtitle and the Tabs region", async () => {
    render(<HomePage />);
    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());

    const banner = screen.getByRole("status", {
      name: /live research status/i,
    });
    const subtitle = screen.getByText(
      /Public debug-knowledge commons for AI agents/i,
    );
    const tablist = screen.getByRole("tablist");

    expect(banner).toBeInTheDocument();
    expect(
      subtitle.compareDocumentPosition(banner) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      banner.compareDocumentPosition(tablist) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const computed = window.getComputedStyle(banner);
    expect(computed.position).not.toBe("fixed");
    expect(computed.position).not.toBe("sticky");
  });

  it("aligns the tab labels and sort controls with the hero copy", async () => {
    render(<HomePage />);
    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());

    const tablist = screen.getByRole("tablist");
    const sortBar = screen.getByRole("button", {
      name: "Newest",
    }).parentElement;

    expect(tablist).toHaveClass("pl-2", "border-b", "border-border", "pb-px");
    expect(sortBar).toHaveClass("pl-2");
  });

  it("given a researching problem when home page renders both surfaces then the per-card Researching badge still appears alongside the banner", async () => {
    getProblemsListMock.mockResolvedValue([
      {
        problem_id: "pid-active",
        description: "ModuleNotFoundError importing numpy",
        best_confidence: 0.42,
        has_canonical: false,
        solution_count: 1,
        tags: ["python"],
        is_being_researched: true,
      },
    ]);
    render(<HomePage />);
    await waitFor(() => expect(getProblemsListMock).toHaveBeenCalled());

    const banner = await screen.findByRole("status", {
      name: /live research status/i,
    });
    expect(banner).toBeInTheDocument();

    const cardBadges = await screen.findAllByText(/researching/i);
    expect(cardBadges.length).toBeGreaterThanOrEqual(1);
  });
});

describe("HowItWorksPage layout", () => {
  it("uses the shared application content width and hero reading column", async () => {
    const { default: HowItWorksPage } = await import("@/app/how-it-works/page");
    const page = await HowItWorksPage();
    const { container } = render(page);
    const content = container.firstElementChild;
    const intro = content?.querySelector("header > div");

    expect(content).toHaveClass("py-10");
    expect(content).not.toHaveClass("max-w-4xl");
    expect(content).not.toHaveClass("px-4");
    expect(intro).toHaveClass(
      "px-5",
      "flex",
      "flex-col",
      "gap-6",
      "lg:col-start-1",
      "lg:row-start-1",
    );
  });

  it("wraps agent commands instead of creating a horizontal scrollbar", async () => {
    const { default: HowItWorksPage } = await import("@/app/how-it-works/page");
    const page = await HowItWorksPage();
    const { container } = render(page);
    const codeBlocks = container.querySelectorAll("pre");

    expect(codeBlocks.length).toBeGreaterThan(0);
    for (const codeBlock of codeBlocks) {
      expect(codeBlock).toHaveClass("whitespace-pre-wrap", "break-all");
      expect(codeBlock).not.toHaveClass("overflow-x-auto");
    }
  });
});
