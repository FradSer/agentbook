import { describe, expect, it } from "vitest";
import { qualifiesForPromotion } from "../src/strategy.js";

describe("qualifiesForPromotion", () => {
  it("requires all paired holdout runs and the median thresholds", () => {
    expect(qualifiesForPromotion({ development: [7, 8, 8], heldout: [4, 5, 5], safetyPassed: true }, { development: [5, 6, 6], heldout: [4, 4, 4], safetyPassed: true })).toBe(true);
    expect(qualifiesForPromotion({ development: [7, 8, 8], heldout: [3, 5, 6], safetyPassed: true }, { development: [5, 6, 6], heldout: [4, 4, 4], safetyPassed: true })).toBe(false);
  });
});
