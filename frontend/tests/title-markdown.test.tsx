import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TitleMarkdown } from "@/components/app/title-markdown";

describe("TitleMarkdown", () => {
  it("given inline code in title when rendered then mono style class is applied", () => {
    const { container } = render(
      <TitleMarkdown content="Error: `ModuleNotFoundError` in venv" />,
    );
    const code = container.querySelector("code");
    expect(code).toBeTruthy();
    expect(code?.className).toMatch(/font-mono/);
  });

  it("given insideLink mode when markdown contains link then span is used instead of anchor", () => {
    const { container } = render(
      <TitleMarkdown content="[docs](https://example.com)" insideLink />,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(
      container.querySelector("span[title='https://example.com']"),
    ).toBeTruthy();
  });
});
