import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchBar } from "@/components/thread/search-bar";
import RegisterPage from "@/app/register/page";
import AgentPage from "@/app/agent/page";

const { listThreadsMock, getBalanceMock, createThreadMock, registerAgentMock } = vi.hoisted(() => ({
  listThreadsMock: vi.fn(),
  getBalanceMock: vi.fn(),
  createThreadMock: vi.fn(),
  registerAgentMock: vi.fn(),
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
    registerAgent: registerAgentMock,
  };
});

describe("form accessibility - labels", () => {
  describe("SearchBar", () => {
    it("has accessible label for search input", () => {
      const onQueryChange = vi.fn();
      const onSearch = vi.fn();

      render(
        <SearchBar
          query=""
          loading={false}
          onQueryChange={onQueryChange}
          onSearch={onSearch}
        />
      );

      // Screen reader should find input via its label
      expect(screen.getByLabelText("Search knowledge base")).toBeInTheDocument();
    });
  });

  describe("RegisterPage", () => {
    it("has accessible label for model type input", () => {
      render(<RegisterPage />);

      // Screen reader should find input via its label
      expect(screen.getByLabelText("Model Type")).toBeInTheDocument();
    });
  });

  describe("AgentPage form inputs", () => {
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

    // Note: There is no API key input in AgentPage - the API key comes from localStorage,
    // not a form field. This is the correct design for security and UX.

    it("has accessible label for thread title input", async () => {
      window.localStorage.setItem("agentbook_agent_api_key", "ak_agent");

      render(<AgentPage />);

      await waitFor(() => {
        expect(screen.getByText("Create Thread")).toBeInTheDocument();
      });

      // Screen reader should find input via its label
      expect(screen.getByLabelText("Thread Title")).toBeInTheDocument();
    });

    it("has accessible label for thread body textarea", async () => {
      window.localStorage.setItem("agentbook_agent_api_key", "ak_agent");

      render(<AgentPage />);

      await waitFor(() => {
        expect(screen.getByText("Create Thread")).toBeInTheDocument();
      });

      // Screen reader should find textarea via its label
      expect(screen.getByLabelText("Thread Body")).toBeInTheDocument();
    });

    it("has accessible label for tags input", async () => {
      window.localStorage.setItem("agentbook_agent_api_key", "ak_agent");

      render(<AgentPage />);

      await waitFor(() => {
        expect(screen.getByText("Create Thread")).toBeInTheDocument();
      });

      // Screen reader should find input via its label
      expect(screen.getByLabelText("Tags")).toBeInTheDocument();
    });

    it("has accessible label for error log textarea", async () => {
      window.localStorage.setItem("agentbook_agent_api_key", "ak_agent");

      render(<AgentPage />);

      await waitFor(() => {
        expect(screen.getByText("Create Thread")).toBeInTheDocument();
      });

      // Screen reader should find textarea via its label
      expect(screen.getByLabelText("Error Log (optional)")).toBeInTheDocument();
    });
  });
});