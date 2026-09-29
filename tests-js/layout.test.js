import { describe, expect, it } from "vitest";
import { calculateSpreadFitFactor } from "../src/layout.js";

describe("two-page layout", () => {
  it.each([900, 780, 510])("fits two Letter pages inside a %ipx gallery", (galleryWidth) => {
    const factor = calculateSpreadFitFactor(galleryWidth, [612, 612]);
    const occupiedWidth = 2 * 612 * 1.12 * factor + 94;
    expect(occupiedWidth).toBeLessThanOrEqual(galleryWidth + 0.001);
  });

  it("does not enlarge small pages beyond their natural display size", () => {
    expect(calculateSpreadFitFactor(1600, [300, 300])).toBe(1);
  });
});
