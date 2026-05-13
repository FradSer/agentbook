/**
 * BDD scenarios covered:
 *   - /memories shows verified badge (aria-label="sandbox verified")
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VerifiedPill } from "../app/memories/_components/verified-pill";

describe("VerifiedPill", () => {
  it("given a rendered pill when queried then it is accessible and labeled", () => {
    const { getByLabelText, getByText } = render(<VerifiedPill />);
    expect(getByLabelText("sandbox verified")).toBeTruthy();
    expect(getByText(/verified/i)).toBeTruthy();
  });
});
