/**
 * BDD scenarios covered:
 *   - /memories shows verified badge (aria-label="sandbox verified")
 *   - /memories shows dual score (global + best per-environment)
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DualScore } from "../app/memories/_components/dual-score";
import { VerifiedPill } from "../app/memories/_components/verified-pill";

describe("VerifiedPill", () => {
  it("given a rendered pill when queried then it is accessible and labeled", () => {
    const { getByLabelText, getByText } = render(<VerifiedPill />);
    expect(getByLabelText("sandbox verified")).toBeTruthy();
    expect(getByText(/verified/i)).toBeTruthy();
  });
});

describe("DualScore", () => {
  it("given per-environment scores when rendered then top score and key are shown", () => {
    const { getByText } = render(
      <DualScore
        global={0.71}
        perEnvironment={{ "os=ubuntu-22": 0.82, "os=alpine-3": 0.55 }}
      />,
    );
    expect(getByText("0.71")).toBeTruthy();
    expect(getByText(/global/i)).toBeTruthy();
    expect(getByText("0.82")).toBeTruthy();
    expect(getByText("os=ubuntu-22")).toBeTruthy();
  });

  it.each([
    { perEnvironment: null, hasPerEnvironment: false },
    { perEnvironment: {}, hasPerEnvironment: false },
  ])("given perEnvironment=%j when rendered then optional per-env block is omitted", ({
    perEnvironment,
    hasPerEnvironment,
  }) => {
    const { queryByText } = render(
      <DualScore global={0.5} perEnvironment={perEnvironment} />,
    );
    expect(Boolean(queryByText("os="))).toBe(hasPerEnvironment);
  });
});
