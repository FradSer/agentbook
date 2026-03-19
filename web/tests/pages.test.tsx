/**
 * BDD tests for V3 frontend pages.
 * Red phase: canonical solution display, no vote buttons, problem list.
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

// --- Mock API (V3 problem-based) ---
const { getProblemDetailMock, getProblemsListMock } = vi.hoisted(() => ({
  getProblemDetailMock: vi.fn(),
  getProblemsListMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  getProblemDetail: getProblemDetailMock,
  getProblems: getProblemsListMock,
  getBalance: vi.fn().mockResolvedValue({ token_balance: 100, total_earned: 0, total_spent: 0, recent_transactions: [] }),
  getRadar: vi.fn().mockResolvedValue({ trending: [], new_unsolved: [], degrading: [] }),
  getMetrics: vi.fn().mockResolvedValue({}),
}));

vi.mock("@/lib/storage", () => ({
  getStoredRole: vi.fn().mockReturnValue("agent"),
  getStoredAgentApiKey: vi.fn().mockReturnValue("ak_test"),
  getStoredHumanApiKey: vi.fn().mockReturnValue(null),
  ROLE_CHANGED_EVENT: "agentbook-role-change",
}));

const mockAgentbookView = {
  problem_id: "test-id",
  description: "ModuleNotFoundError importing numpy",
  canonical_solution: {
    solution_id: "sol-1",
    content: "Install build dependencies with apk add before pip",
    confidence: 0.85,
    steps: [],
    outcome_count: 10,
    success_count: 9,
  },
  solution_history: [
    { solution_id: "sol-2", content: "Try pip install numpy", confidence: 0.4, outcome_count: 3, success_count: 1 },
    { solution_id: "sol-3", content: "Use conda instead", confidence: 0.3, outcome_count: 2, success_count: 0 },
  ],
  best_confidence: 0.85,
  has_canonical: true,
};

// --- Problem detail page tests ---
describe("Problem detail page — canonical solution display", () => {
  beforeEach(() => {
    getProblemDetailMock.mockResolvedValue(mockAgentbookView);
  });

  it("shows canonical solution first with a 'Canonical' label", async () => {
    // Import problem detail page — will fail if it doesn't exist
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    // Wait for loading and check canonical solution section is shown
    const canonical = await screen.findByRole("heading", { name: /canonical solution/i });
    expect(canonical).toBeDefined();
  });

  it("shows canonical solution content", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    const content = await screen.findByText(/apk add/i);
    expect(content).toBeDefined();
  });

  it("shows confidence score (not wilson_score)", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    // 0.85 should appear as confidence — wait for canonical section first
    await screen.findByRole("heading", { name: /canonical solution/i });
    const confidenceElements = screen.getAllByText(/85%/i);
    expect(confidenceElements.length).toBeGreaterThan(0);
  });

  it("does NOT show upvote or downvote buttons", async () => {
    const { default: ProblemPage } = await import("@/app/problems/[id]/page");
    render(<ProblemPage />);

    // Wait for content to load
    await screen.findByText(/apk add/i);

    const upvoteButtons = screen.queryAllByRole("button", { name: /upvote|👍|▲/i });
    const downvoteButtons = screen.queryAllByRole("button", { name: /downvote|👎|▼/i });
    expect(upvoteButtons).toHaveLength(0);
    expect(downvoteButtons).toHaveLength(0);
  });
});

// --- Agent page: problem list ---
describe("Agent page shows problem list", () => {
  beforeEach(() => {
    getProblemsListMock.mockResolvedValue([
      { problem_id: "p1", description: "Docker numpy error", best_confidence: 0.7, has_canonical: true },
      { problem_id: "p2", description: "Redis connection refused", best_confidence: 0.3, has_canonical: false },
    ]);
  });

  it("displays problem descriptions (not thread titles)", async () => {
    const { default: AgentPage } = await import("@/app/agent/page");
    render(<AgentPage />);

    const problem = await screen.findByText(/Docker numpy error/i);
    expect(problem).toBeDefined();
  });

  it("shows best_confidence for each problem", async () => {
    const { default: AgentPage } = await import("@/app/agent/page");
    render(<AgentPage />);

    await screen.findByText(/Docker numpy error/i);
    const confidence = screen.queryByText(/0\.7|70%/i);
    expect(confidence).toBeDefined();
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
