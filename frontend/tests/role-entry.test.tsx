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
    getProblemsListMock.mockResolvedValue([]);
  });

  it("shows problems list heading", async () => {
    render(<HomePage />);

    await waitFor(() =>
      expect(screen.getByText("Problem Definitions")).toBeInTheDocument(),
    );
  });
});
