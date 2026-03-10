import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

const { listThreadsMock } = vi.hoisted(() => ({
  listThreadsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {},
  listThreads: listThreadsMock,
}));

describe("home page", () => {
  beforeEach(() => {
    listThreadsMock.mockReset();
    window.localStorage.clear();
    listThreadsMock.mockResolvedValue({ results: [], total: 0 });
  });

  it("shows questions list", () => {
    render(<HomePage />);

    expect(screen.getByText("All Questions")).toBeInTheDocument();
  });

  it("shows filters", () => {
    render(<HomePage />);

    expect(screen.getByText("Newest")).toBeInTheDocument();
    expect(screen.getByText("Unanswered")).toBeInTheDocument();
    expect(screen.getByText("Answered")).toBeInTheDocument();
  });
});
