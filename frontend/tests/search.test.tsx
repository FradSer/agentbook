/**
 * Tests for /search public page (public unified memory layer entry point).
 * Covers: empty state, results render, SearchBox submit, no write actions.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchBox } from "@/components/app/search-box";
import { SearchResultsList } from "@/components/app/search-results-list";
import type { SearchResult } from "@/lib/types";

const { searchProblemsMock, routerPushMock } = vi.hoisted(() => ({
  searchProblemsMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock, replace: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    searchProblems: searchProblemsMock,
  };
});

const sampleResults: SearchResult[] = [
  {
    problem_id: "p-hydration",
    description_preview: "Next.js hydration mismatch on dynamic boundary",
    tags: ["nextjs", "react", "hydration"],
    similarity_score: 0.91,
    best_solution: {
      solution_id: "sol-1",
      content_preview:
        "Move the dynamic value into useEffect so the SSR markup matches.",
      confidence: 0.86,
    },
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    problem_id: "p-pgvector",
    description_preview: "pgvector extension not installed on Railway",
    tags: ["postgres", "pgvector"],
    similarity_score: 0.74,
    best_solution: null,
    created_at: new Date(Date.now() - 172800000).toISOString(),
  },
];

describe("SearchResultsList", () => {
  it("shows the prompt empty state when query is empty", () => {
    render(<SearchResultsList results={[]} query="" />);
    expect(
      screen.getByText(/type an error message or stack trace/i),
    ).toBeInTheDocument();
  });

  it("shows no-results state with MCP contribute hint when query has no matches", () => {
    render(<SearchResultsList results={[]} query="hydration" />);
    expect(screen.getByText(/no problems match/i)).toBeInTheDocument();
    const setupLink = screen.getByRole("link", { name: /client setup/i });
    expect(setupLink).toHaveAttribute(
      "href",
      "https://github.com/FradSer/agentbook/blob/main/docs/mcp-setup.md",
    );
    expect(setupLink).toHaveAttribute("target", "_blank");
    expect(setupLink).toHaveAttribute("rel", "noreferrer");
  });

  it("renders one card per result with confidence and tags", () => {
    render(<SearchResultsList results={sampleResults} query="hydration" />);
    expect(
      screen.getByText(/Next\.js hydration mismatch/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/pgvector extension not installed/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/86% · high/i)).toBeInTheDocument();
    expect(screen.getByText(/no solution yet/i)).toBeInTheDocument();
    expect(screen.getByText("nextjs")).toBeInTheDocument();
    expect(screen.getByText("pgvector")).toBeInTheDocument();
  });

  it("links each result card to its problem detail page", () => {
    render(<SearchResultsList results={sampleResults} query="hydration" />);
    const links = screen
      .getAllByRole("link")
      .filter((el) => el.getAttribute("href")?.startsWith("/problems/"));
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/problems/p-hydration");
    expect(links[1]).toHaveAttribute("href", "/problems/p-pgvector");
  });
});

describe("SearchBox", () => {
  beforeEach(() => {
    routerPushMock.mockReset();
  });

  it("pushes /search with encoded query on submit", async () => {
    const user = userEvent.setup();
    render(<SearchBox initialQuery="" />);
    const input = screen.getByRole("searchbox");
    await user.type(input, "hydration error");
    await user.click(screen.getByRole("button", { name: /search/i }));
    expect(routerPushMock).toHaveBeenCalledWith("/search?q=hydration%20error");
  });

  it("does not push on empty submit", async () => {
    const user = userEvent.setup();
    render(<SearchBox initialQuery="   " />);
    await user.click(screen.getByRole("button", { name: /search/i }));
    expect(routerPushMock).not.toHaveBeenCalled();
  });

  it("renders without write-action buttons (public read-only)", () => {
    render(<SearchBox initialQuery="" />);
    const writeButtons = screen.queryAllByRole("button", {
      name: /submit|create|post/i,
    });
    expect(writeButtons).toHaveLength(0);
  });
});

describe("/search page (server component)", () => {
  beforeEach(() => {
    searchProblemsMock.mockReset();
  });

  it("renders empty state when no query is provided", async () => {
    const { default: SearchPage } = await import("@/app/search/page");
    const ui = await SearchPage({ searchParams: Promise.resolve({}) });
    render(ui);
    expect(
      screen.getByRole("heading", { name: /search the agentbook/i, level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/type an error message or stack trace/i),
    ).toBeInTheDocument();
    expect(searchProblemsMock).not.toHaveBeenCalled();
  });

  it("calls searchProblems and renders results when query is present", async () => {
    searchProblemsMock.mockResolvedValueOnce({
      results: sampleResults,
      total: sampleResults.length,
    });
    const { default: SearchPage } = await import("@/app/search/page");
    const ui = await SearchPage({
      searchParams: Promise.resolve({ q: "hydration" }),
    });
    render(ui);
    expect(searchProblemsMock).toHaveBeenCalledWith("hydration");
    expect(
      screen.getByText(/Next\.js hydration mismatch/i),
    ).toBeInTheDocument();
  });

  it("renders error panel if searchProblems throws", async () => {
    searchProblemsMock.mockRejectedValueOnce(new Error("Connection failed"));
    const { default: SearchPage } = await import("@/app/search/page");
    const ui = await SearchPage({
      searchParams: Promise.resolve({ q: "hydration" }),
    });
    render(ui);
    expect(screen.getByText(/Connection failed/i)).toBeInTheDocument();
  });

  it("never renders write-action buttons", async () => {
    searchProblemsMock.mockResolvedValueOnce({
      results: sampleResults,
      total: sampleResults.length,
    });
    const { default: SearchPage } = await import("@/app/search/page");
    const ui = await SearchPage({
      searchParams: Promise.resolve({ q: "hydration" }),
    });
    render(ui);
    const writeButtons = screen.queryAllByRole("button", {
      name: /submit|create|post|contribute|report/i,
    });
    expect(writeButtons).toHaveLength(0);
  });
});
