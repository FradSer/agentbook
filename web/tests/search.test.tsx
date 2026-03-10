import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchBar } from "@/components/thread/search-bar";

const { searchThreadsMock } = vi.hoisted(() => ({
  searchThreadsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  searchThreads: searchThreadsMock,
}));

describe("search functionality", () => {
  beforeEach(() => {
    searchThreadsMock.mockReset();
  });

  it("renders search input", () => {
    render(
      <SearchBar
        query=""
        loading={false}
        onQueryChange={vi.fn()}
        onSearch={vi.fn()}
      />
    );

    const searchInput = screen.getByLabelText("Search knowledge base");
    expect(searchInput).toBeInTheDocument();
  });

  it("updates query when user types", () => {
    const onQueryChange = vi.fn();
    render(
      <SearchBar
        query=""
        loading={false}
        onQueryChange={onQueryChange}
        onSearch={vi.fn()}
      />
    );

    const searchInput = screen.getByLabelText("Search knowledge base");
    fireEvent.change(searchInput, { target: { value: "test query" } });

    expect(onQueryChange).toHaveBeenCalledWith("test query");
  });

  it("submits search when form is submitted", async () => {
    const onSearch = vi.fn();
    searchThreadsMock.mockResolvedValue({
      results: [],
      total: 0,
    });

    render(
      <SearchBar
        query="python error"
        loading={false}
        onQueryChange={vi.fn()}
        onSearch={onSearch}
      />
    );

    const searchButton = screen.getByRole("button", { name: "Search" });
    fireEvent.click(searchButton);

    await waitFor(() => {
      expect(onSearch).toHaveBeenCalled();
    });
  });

  it("disables search button when query is empty", () => {
    render(
      <SearchBar
        query=""
        loading={false}
        onQueryChange={vi.fn()}
        onSearch={vi.fn()}
      />
    );

    const searchButton = screen.getByRole("button", { name: "Search" });
    expect(searchButton).toBeDisabled();
  });

  it("disables search button when loading", () => {
    render(
      <SearchBar
        query="test query"
        loading={true}
        onQueryChange={vi.fn()}
        onSearch={vi.fn()}
      />
    );

    const searchButton = screen.getByRole("button", { name: "Searching..." });
    expect(searchButton).toBeDisabled();
  });
});