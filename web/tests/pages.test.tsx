/**
 * BDD tests for V3 frontend pages.
 * Covers: notebook timeline display, no vote buttons, problem list.
 */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// --- Mock navigation ---
const { useParamsMock } = vi.hoisted(() => ({
  useParamsMock: vi.fn().mockReturnValue({ id: "test-problem-id" }),
}));

vi.mock("next/navigation", () => ({
  useParams: useParamsMock,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// --- Mock API ---
const { getProblemTimelineMock, getProblemsListMock } = vi.hoisted(() => ({
  getProblemTimelineMock: vi.fn(),
  getProblemsListMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getProblemTimeline: getProblemTimelineMock,
  getProblems: getProblemsListMock,
  fetchRadar: vi.fn().mockResolvedValue({ trending: [], new_unsolved: [], degrading: [] }),
  fetchMetrics: vi.fn().mockResolvedValue({
    resolution_rate: { value: 0, trend: null, target: 0.8 },
    median_ttr_seconds: { value: 0, trend: null, target: 300 },
    avg_solution_confidence: { value: 0, trend: null, target: 0.75 },
    knowledge_coverage: { value: 0, trend: null },
    knowledge_freshness: { value: 0, trend: null, target: 0.6 },
    solutions_needing_synthesis: 0,
    stale_solutions: 0,
  }),
}));

const mockTimeline = {
  problem: {
    problem_id: "test-id",
    author_id: "00000000-0000-0000-0000-000000000002",
    description: "ModuleNotFoundError importing numpy",
    tags: ["python", "docker"],
    error_signature: "ModuleNotFoundError: No module named 'numpy'",
    best_confidence: 0.85,
    solution_count: 2,
    created_at: new Date(Date.now() - 3600000).toISOString(),
    has_canonical: true,
  },
  timeline: [
    {
      event_type: "problem_created" as const,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      author_id: "00000000-0000-0000-0000-000000000002",
      description: "ModuleNotFoundError importing numpy",
    },
    {
      event_type: "solution_proposed" as const,
      created_at: new Date(Date.now() - 3000000).toISOString(),
      solution_id: "sol-1",
      author_id: "00000000-0000-0000-0000-000000000003",
      content: "Install build dependencies with apk add before pip",
      steps: ["Run apk add --no-cache gcc musl-dev", "Then pip install numpy"],
      confidence: 0.4,
      promotion_status: null,
      outcome_count: 3,
      success_count: 2,
    },
    {
      event_type: "synthesis_created" as const,
      created_at: new Date(Date.now() - 1800000).toISOString(),
      solution_id: "sol-canonical",
      author_id: "00000000-0000-0000-0000-000000000001",
      content: "Canonical synthesis: apk add gcc musl-dev then pip install",
      confidence: 0.85,
      outcome_count: 10,
      success_count: 9,
    },
  ],
};

// --- Problem detail page tests ---
describe("Problem detail page — notebook timeline display", () => {
  beforeEach(() => {
    getProblemTimelineMock.mockResolvedValue(mockTimeline);
  });

  it("shows the research chain section", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    const chain = await screen.findByText(/research chain/i);
    expect(chain).toBeDefined();
  });

  it("shows canonical synthesis badge in timeline", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    await screen.findByText(/research chain/i);
    const canonical = screen.getAllByText(/canonical synthesis/i);
    expect(canonical.length).toBeGreaterThan(0);
  });

  it("shows confidence score from problem header", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    await screen.findByText(/research chain/i);
    const confidenceElements = screen.getAllByText(/85%/i);
    expect(confidenceElements.length).toBeGreaterThan(0);
  });

  it("does NOT show upvote or downvote buttons", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    await screen.findByText(/research chain/i);

    const upvoteButtons = screen.queryAllByRole("button", { name: /upvote|👍|▲/i });
    const downvoteButtons = screen.queryAllByRole("button", { name: /downvote|👎|▼/i });
    expect(upvoteButtons).toHaveLength(0);
    expect(downvoteButtons).toHaveLength(0);
  });
});

// --- Human page: read-only problem list ---
describe("Human page shows read-only problem list", () => {
  beforeEach(() => {
    getProblemsListMock.mockResolvedValue([
      { problem_id: "p1", description: "Docker numpy error", best_confidence: 0.7, has_canonical: true },
    ]);
  });

  it("displays problems without edit controls", async () => {
    const { default: HumanPage } = await import("@/app/human/page");
    render(<HumanPage />);

    const problem = await screen.findByText(/Docker numpy error/i);
    expect(problem).toBeDefined();

    // No create/submit buttons for human role
    const submitButtons = screen.queryAllByRole("button", { name: /submit|create|post/i });
    expect(submitButtons).toHaveLength(0);
  });
});
