import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RegisterPage from "@/app/register/page";

const { registerAgentMock } = vi.hoisted(() => ({
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
    registerAgent: registerAgentMock,
  };
});

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("register page", () => {
  beforeEach(() => {
    registerAgentMock.mockReset();
    window.localStorage.clear();
  });

  it("renders registration form", () => {
    render(<RegisterPage />);

    expect(screen.getByText("Register Agent")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register" })).toBeInTheDocument();
  });

  it("model type input is present", () => {
    render(<RegisterPage />);

    const modelTypeInput = screen.getByLabelText("Model Type");
    expect(modelTypeInput).toBeInTheDocument();
  });

  it("submits registration form with model type", async () => {
    registerAgentMock.mockResolvedValue({
      agent_id: "agent-1",
      api_key: "sk-agentbook-test",
      token_balance: 0,
    });

    render(<RegisterPage />);

    const modelTypeInput = screen.getByLabelText("Model Type");
    const registerButton = screen.getByRole("button", { name: "Register" });

    fireEvent.change(modelTypeInput, { target: { value: "gemini" } });
    fireEvent.click(registerButton);

    await waitFor(() => {
      expect(registerAgentMock).toHaveBeenCalledWith("gemini");
    });

    expect(screen.getByDisplayValue("sk-agentbook-test")).toBeInTheDocument();
  });

  it("displays error when registration fails", async () => {
    registerAgentMock.mockRejectedValue(new Error("Registration failed"));

    render(<RegisterPage />);

    const registerButton = screen.getByRole("button", { name: "Register" });
    fireEvent.click(registerButton);

    await waitFor(() => {
      expect(registerAgentMock).toHaveBeenCalled();
    });
  });
});