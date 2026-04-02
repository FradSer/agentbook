import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SolutionMarkdown } from "@/components/app/solution-markdown";

describe("SolutionMarkdown", () => {
  it("renders fenced code as pre and code, not raw backticks", () => {
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

  it("renders inline code with code element", () => {
    render(<SolutionMarkdown content="Use `verify=True` here." />);
    expect(document.querySelector("code")).toBeTruthy();
  });

  it("maps markdown headings to h2/h3 so outline stays consistent under page h1", () => {
    const md = ["# Top", "", "## Section"].join("\n");
    render(<SolutionMarkdown content={md} />);
    expect(
      screen.getByRole("heading", { level: 2, name: "Top" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Section" }),
    ).toBeInTheDocument();
  });
});
