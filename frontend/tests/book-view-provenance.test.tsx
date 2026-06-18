import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BookSolutionMetaBar } from "@/components/app/problem-detail/book-view";
import type { BookSolutionPayload } from "@/lib/types";

function book(overrides: Partial<BookSolutionPayload>): BookSolutionPayload {
  return {
    solution_id: "s1",
    author_id: "a1",
    content: "Cap the pool size and reuse a module-level client",
    confidence: 0.9,
    created_at: "2026-01-01T00:00:00Z",
    is_synthesized: false,
    ...overrides,
  };
}

describe("BookSolutionMetaBar provenance badge", () => {
  it("shows a Seeded badge when confidence is seed-only", () => {
    render(<BookSolutionMetaBar book={book({ provenance: "seeded" })} />);
    expect(screen.getByText("Seeded")).toBeTruthy();
  });

  it("hides the Seeded badge once an organic reporter corroborates", () => {
    render(<BookSolutionMetaBar book={book({ provenance: "organic" })} />);
    expect(screen.queryByText("Seeded")).toBeNull();
  });

  it("hides the Seeded badge when there are no outcomes", () => {
    render(<BookSolutionMetaBar book={book({ provenance: "none" })} />);
    expect(screen.queryByText("Seeded")).toBeNull();
  });
});
