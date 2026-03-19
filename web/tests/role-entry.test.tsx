import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

const { getProblemsListMock } = vi.hoisted(() => ({
  getProblemsListMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  getProblems: getProblemsListMock,
}));

describe("home page", () => {
  beforeEach(() => {
    getProblemsListMock.mockReset();
    window.localStorage.clear();
    getProblemsListMock.mockResolvedValue([]);
  });

  it("shows problems list heading", async () => {
    render(<HomePage />);

    await waitFor(() =>
      expect(screen.getByText("Agentbooks")).toBeInTheDocument()
    );
  });

  it("shows Register as Agent button when no role stored", async () => {
    render(<HomePage />);

    await waitFor(() =>
      expect(screen.getByText("Register as Agent")).toBeInTheDocument()
    );
  });
});
