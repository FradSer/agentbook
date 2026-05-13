import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const { pushMock, searchProblemsMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  searchProblemsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
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
import { SearchDialog } from "@/components/app/search-dialog";

function makeResult(overrides: Record<string, unknown>) {
  return {
    problem_id: "problem-1",
    description_preview: "pgvector extension missing",
    tags: ["postgres", "railway"],
    similarity_score: 0.91,
    best_solution: {
      solution_id: "solution-1",
      content_preview: "Enable pgvector before running migrations",
      confidence: 0.84,
    },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function containingText(text: string) {
  return (_content: string, element: Element | null) => {
    if (!element?.textContent?.includes(text)) {
      return false;
    }

    return Array.from(element.children).every(
      (child) => !child.textContent?.includes(text),
    );
  };
}

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });

  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  Object.defineProperty(globalThis, "ResizeObserver", {
    configurable: true,
    value: ResizeObserverMock,
  });
});

beforeEach(() => {
  pushMock.mockReset();
  searchProblemsMock.mockReset();
});

describe("Search dialog", () => {
  it("given global slash shortcut when triggered then search dialog opens with focus", async () => {
    render(<NavBar />);

    fireEvent.keyDown(document, {
      key: "/",
      metaKey: false,
      ctrlKey: false,
      altKey: false,
    });

    const input = await screen.findByPlaceholderText(/search memories/i);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(input).toHaveFocus();
  });

  it("given initial fetch failure when retrying same query then results are returned", async () => {
    const user = userEvent.setup();

    searchProblemsMock
      .mockRejectedValueOnce(new Error("backend offline"))
      .mockResolvedValueOnce({
        results: [makeResult({})],
        total: 1,
      });

    render(<SearchDialog open onOpenChange={vi.fn()} />);

    await user.type(
      screen.getByPlaceholderText(/search memories/i),
      "pgvector",
    );

    await waitFor(() => expect(searchProblemsMock).toHaveBeenCalledTimes(1));
    await screen.findByText(/Search unavailable/i);

    await user.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(searchProblemsMock).toHaveBeenCalledTimes(2));
    expect(searchProblemsMock).toHaveBeenNthCalledWith(
      2,
      "pgvector",
      expect.objectContaining({ limit: 8, signal: expect.any(AbortSignal) }),
    );
    expect(
      await screen.findByText(containingText("pgvector extension missing")),
    ).toBeInTheDocument();
  });

  it("given highlighted result when confirming keyboard selection then dialog closes and navigates", async () => {
    const user = userEvent.setup();

    searchProblemsMock.mockResolvedValue({
      results: [
        makeResult({
          description_preview: "Railway deployment failure",
          tags: ["railway", "deploy"],
          similarity_score: 0.95,
          best_solution: {
            solution_id: "solution-1",
            content_preview: "Clear the stale build cache",
            confidence: 0.81,
          },
        }),
        makeResult({
          problem_id: "problem-2",
          description_preview: "Railway postgres connection timeout",
          tags: ["railway", "postgres"],
          similarity_score: 0.75,
          best_solution: null,
        }),
      ],
      total: 2,
    });

    const onOpenChange = vi.fn();
    render(<SearchDialog open onOpenChange={onOpenChange} />);

    const input = screen.getByPlaceholderText(/search memories/i);
    await user.type(input, "Railway");

    await waitFor(() => expect(searchProblemsMock).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText(containingText("Railway deployment failure")),
    ).toBeInTheDocument();

    await user.click(input);
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(pushMock).toHaveBeenCalledWith("/memories/problem-1");
    expect(window.localStorage.getItem("agentbook:recent-queries")).toContain(
      '"Railway"',
    );
  });
});
