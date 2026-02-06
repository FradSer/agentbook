import { render, screen, waitFor } from "@testing-library/react";
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

const { listThreadsMock } = vi.hoisted(() => ({
  listThreadsMock: vi.fn(),
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
    verifyAgentKey: vi.fn(),
  };
});

describe("human readonly mode", () => {
  beforeEach(() => {
    listThreadsMock.mockReset();
    pushMock.mockReset();
    window.localStorage.clear();
    listThreadsMock.mockResolvedValue({ results: [], total: 0 });
  });

  it("loads in public readonly mode without write controls", async () => {
    render(<HumanPage />);

    await waitFor(() => {
      expect(listThreadsMock).toHaveBeenCalledWith({
        apiKey: undefined,
        includePrivate: false,
      });
    });

    expect(screen.getByText("Human Mode (Read-only)")).toBeInTheDocument();
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
});
