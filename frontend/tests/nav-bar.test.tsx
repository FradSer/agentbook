import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const { searchProblemsMock } = vi.hoisted(() => ({
  searchProblemsMock: vi.fn(),
}));

beforeAll(() => {
  // cmdk (used by SearchDialog) depends on browser APIs that jsdom does
  // not provide. No-op stubs keep the dialog from crashing on mount.
  if (typeof globalThis.ResizeObserver === "undefined") {
    class StubResizeObserver {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    }
    (
      globalThis as unknown as { ResizeObserver: typeof ResizeObserver }
    ).ResizeObserver = StubResizeObserver as unknown as typeof ResizeObserver;
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    searchProblems: searchProblemsMock,
  };
});

import { NavBar } from "@/components/app/nav-bar";

beforeEach(() => {
  searchProblemsMock.mockReset();
  searchProblemsMock.mockResolvedValue({ results: [], total: 0 });
});

describe("NavBar", () => {
  it("renders the brand link pointing to the home route", () => {
    render(<NavBar />);
    const homeLink = screen.getByRole("link", { name: /agentbook/i });
    expect(homeLink).toHaveAttribute("href", "/");
  });

  it("opens the search dialog when the search button is clicked", async () => {
    const user = userEvent.setup();
    render(<NavBar />);
    await user.click(screen.getByRole("button", { name: /open search/i }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("opens the search dialog on Cmd/Ctrl+K", async () => {
    render(<NavBar />);
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });

  it("does not hijack the slash key while the user is typing in an input", () => {
    render(
      <>
        <input data-testid="text-input" />
        <NavBar />
      </>,
    );

    const input = screen.getByTestId("text-input");
    input.focus();
    fireEvent.keyDown(input, { key: "/" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
