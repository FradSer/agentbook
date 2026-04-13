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

  it("shows public memory layer hero", async () => {
    render(<HomePage />);

    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          name: /one memory every agent can read/i,
          level: 1,
        }),
      ).toBeInTheDocument(),
    );
  });
});
