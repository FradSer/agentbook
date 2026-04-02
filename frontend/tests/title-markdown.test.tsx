import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TitleMarkdown } from "@/components/app/title-markdown";

describe("TitleMarkdown", () => {
  it("renders inline code with IBM Plex mono stack (font-mono)", () => {
    const { container } = render(
      <TitleMarkdown content="Error: `ModuleNotFoundError` in venv" />,
    );
    const code = container.querySelector("code");
    expect(code).toBeTruthy();
    expect(code?.className).toMatch(/font-mono/);
  });

  it("insideLink uses span instead of anchor for links", () => {
    const { container } = render(
      <TitleMarkdown content="[docs](https://example.com)" insideLink />,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(
      container.querySelector("span[title='https://example.com']"),
    ).toBeTruthy();
  });
});
