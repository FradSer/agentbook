import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
  }),
}));

describe("role entry page", () => {
  beforeEach(() => {
    pushMock.mockReset();
    replaceMock.mockReset();
    window.localStorage.clear();
  });

  it("shows role options on first visit", () => {
    render(<HomePage />);

    expect(screen.getByText("Choose how to enter Agentbook")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue as Human" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue as Agent" })).toBeInTheDocument();
  });

  it("persists selected role and routes to target page", () => {
    render(<HomePage />);

    fireEvent.click(screen.getByRole("button", { name: "Continue as Agent" }));

    expect(window.localStorage.getItem("agentbook_role")).toBe("agent");
    expect(pushMock).toHaveBeenCalledWith("/agent");
  });

  it("redirects to stored role page automatically", async () => {
    window.localStorage.setItem("agentbook_role", "human");

    render(<HomePage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/human");
    });
  });
});
