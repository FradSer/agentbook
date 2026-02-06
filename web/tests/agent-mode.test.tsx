import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentPage from "@/app/agent/page";

const { listThreadsMock, getBalanceMock, createThreadMock } = vi.hoisted(() => ({
  listThreadsMock: vi.fn(),
  getBalanceMock: vi.fn(),
  createThreadMock: vi.fn(),
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
    listThreads: listThreadsMock,
    getBalance: getBalanceMock,
    createThread: createThreadMock,
  };
});

describe("agent mode page", () => {
  beforeEach(() => {
    listThreadsMock.mockReset();
    getBalanceMock.mockReset();
    createThreadMock.mockReset();
    window.localStorage.clear();
    listThreadsMock.mockResolvedValue({ results: [], total: 0 });
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
    expect(screen.getByRole("link", { name: "Go to Register" })).toBeInTheDocument();
  });

  it("loads full agent features when api key is available", async () => {
    window.localStorage.setItem("agentbook_agent_api_key", "ak_agent");
    listThreadsMock.mockResolvedValue({
      results: [
        {
          thread_id: "thread-1",
          title: "Thread title",
          body_preview: "preview",
          tags: ["python"],
          review_status: "approved",
          created_at: "2026-02-05T00:00:00+00:00",
        },
      ],
      total: 1,
    });

    render(<AgentPage />);

    await waitFor(() => {
      expect(listThreadsMock).toHaveBeenCalledWith({ apiKey: "ak_agent" });
      expect(getBalanceMock).toHaveBeenCalledWith("ak_agent");
    });

    expect(screen.getByText("Agent Wallet")).toBeInTheDocument();
    expect(screen.getByText("Create Thread")).toBeInTheDocument();
    expect(screen.getByText("Thread title")).toBeInTheDocument();
  });
});
