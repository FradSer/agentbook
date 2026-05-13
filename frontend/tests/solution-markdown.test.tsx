import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SolutionMarkdown } from "@/components/app/solution-markdown";

describe("SolutionMarkdown", () => {
  it("given fenced code markdown when rendered then code block is present and raw fence is hidden", () => {
    const md = [
      "Install certifi:",
      "",
      "```bash",
      "pip install --upgrade certifi",
      "```",
    ].join("\n");

    render(<SolutionMarkdown content={md} />);

    expect(screen.queryByText("```bash")).not.toBeInTheDocument();
    expect(
      screen.getByText("pip install --upgrade certifi"),
    ).toBeInTheDocument();
    expect(document.querySelector("pre code")).toBeTruthy();
  });

  it("given inline code markdown when rendered then code element exists", () => {
    render(<SolutionMarkdown content="Use `verify=True` here." />);
    expect(document.querySelector("code")).toBeTruthy();
  });

  it.each([
    { level: 2, name: "Top" },
    { level: 3, name: "Section" },
  ])("given heading markdown when rendered then heading level $level/$name is mapped", ({
    level,
    name,
  }) => {
    const md = ["# Top", "", "## Section"].join("\n");
    render(<SolutionMarkdown content={md} />);
    expect(screen.getByRole("heading", { level, name })).toBeInTheDocument();
  });
});
