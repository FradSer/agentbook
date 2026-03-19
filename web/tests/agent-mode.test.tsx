import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentPage from "@/app/agent/page";

const { getProblemsListMock, getBalanceMock } = vi.hoisted(() => ({
  getProblemsListMock: vi.fn(),
  getBalanceMock: vi.fn(),
}));

vi.mock("@/lib/api", () => {
  class MockApiError extends Error {
    statusCode: number;

    constructor(statusCode: number, message: string) {
      super(message);
      this.statusCode = statusCode;
    }
  }

  return {
    ApiError: MockApiError,
    getProblems: getProblemsListMock,
    getBalance: getBalanceMock,
  };
});

describe("agent mode page", () => {
  beforeEach(() => {
    getProblemsListMock.mockReset();
    getBalanceMock.mockReset();
    window.localStorage.clear();
    getProblemsListMock.mockResolvedValue([]);
    getBalanceMock.mockResolvedValue({
      agent_id: "agent-1",
      token_balance: 100,
      total_earned: 0,
      total_spent: 0,
      recent_transactions: [],
    });
  });

  it("requires registration when no agent api key is stored", () => {
    render(<AgentPage />);

    expect(screen.getByText("Register your agent first")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Register Agent" })).toBeInTheDocument();
  });

  it("loads full agent features when api key is available", async () => {
    window.localStorage.setItem("agentbook_agent_api_key", "ak_agent");
    getProblemsListMock.mockResolvedValue([
      {
        problem_id: "p-1",
        description: "ModuleNotFoundError importing numpy",
        best_confidence: 0.7,
        has_canonical: true,
      },
    ]);

    render(<AgentPage />);

    await waitFor(() => {
      expect(getProblemsListMock).toHaveBeenCalledWith({ apiKey: "ak_agent" });
      expect(getBalanceMock).toHaveBeenCalledWith("ak_agent");
    });

    expect(screen.getByText("Token Balance")).toBeInTheDocument();
    expect(screen.getByText("ModuleNotFoundError importing numpy")).toBeInTheDocument();
  });
});
