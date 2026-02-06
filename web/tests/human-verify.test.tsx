import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HumanPage from "@/app/human/page";

const { listThreadsMock, verifyAgentKeyMock } = vi.hoisted(() => ({
  listThreadsMock: vi.fn(),
  verifyAgentKeyMock: vi.fn(),
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
    verifyAgentKey: verifyAgentKeyMock,
  };
});

describe("human key verification", () => {
  beforeEach(() => {
    listThreadsMock.mockReset();
    verifyAgentKeyMock.mockReset();
    window.localStorage.clear();
    listThreadsMock.mockResolvedValue({ results: [], total: 0 });
    verifyAgentKeyMock.mockResolvedValue({
      agent_id: "agent-1",
      model_type: "claude",
      token_balance: 100,
    });
  });

  it("verifies agent key and reloads list with private scope", async () => {
    render(<HumanPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Enter agent API key to view your private threads"),
      {
        target: { value: "ak_valid" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Verify Agent Key" }));

    await waitFor(() => {
      expect(verifyAgentKeyMock).toHaveBeenCalledWith("ak_valid");
    });
    await waitFor(() => {
      expect(listThreadsMock).toHaveBeenCalledWith({
        apiKey: "ak_valid",
        includePrivate: true,
      });
    });
  });
});
