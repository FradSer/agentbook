import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchBar } from "@/components/thread/search-bar";
import RegisterPage from "@/app/register/page";

const { listThreadsMock, getBalanceMock, createThreadMock, registerAgentMock, createProblemMock } = vi.hoisted(() => ({
  listThreadsMock: vi.fn(),
  getBalanceMock: vi.fn(),
  createThreadMock: vi.fn(),
  registerAgentMock: vi.fn(),
  createProblemMock: vi.fn(),
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
    createProblem: createProblemMock,
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
});
