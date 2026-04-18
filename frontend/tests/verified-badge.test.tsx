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
  it("renders with aria-label 'sandbox verified'", () => {
    const { getByLabelText } = render(<VerifiedPill />);
    expect(getByLabelText("sandbox verified")).toBeTruthy();
  });

  it("displays the label text 'Verified'", () => {
    const { getByText } = render(<VerifiedPill />);
    expect(getByText(/verified/i)).toBeTruthy();
  });
});

describe("DualScore", () => {
  it("renders global score always", () => {
    const { getByText } = render(
      <DualScore global={0.71} perEnvironment={null} />,
    );
    expect(getByText("0.71")).toBeTruthy();
    expect(getByText(/global/i)).toBeTruthy();
  });

  it("renders top per-environment score with its key", () => {
    const { getByText } = render(
      <DualScore
        global={0.71}
        perEnvironment={{ "os=ubuntu-22": 0.82, "os=alpine-3": 0.55 }}
      />,
    );
    expect(getByText("0.71")).toBeTruthy();
    expect(getByText("0.82")).toBeTruthy();
    expect(getByText("os=ubuntu-22")).toBeTruthy();
  });

  it("omits per-env block when empty", () => {
    const { queryByText } = render(
      <DualScore global={0.5} perEnvironment={{}} />,
    );
    expect(queryByText("os=")).toBeNull();
  });
});
