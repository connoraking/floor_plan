import { describe, expect, it } from "vitest";
import { calculateCappedRenderScale, calculateSpreadFitFactor } from "../src/layout.js";

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

describe("multi-page rendering memory", () => {
  it("caps very large architectural pages to the configured pixel budget", () => {
    const scale = calculateCappedRenderScale(3600, 2400, 2.24, 10_000_000);
    expect(3600 * 2400 * scale * scale).toBeCloseTo(10_000_000, -1);
  });

  it("does not shrink an ordinary page unnecessarily", () => {
    expect(calculateCappedRenderScale(612, 792, 1.12, 10_000_000)).toBe(1.12);
  });
});
