import { describe, expect, it } from "vitest";
import {
  distance,
  furniturePath,
  normalizeAngle,
  resizeFurnitureFromHandle,
  scaleFromCalibration,
  toInches,
  validateFurniture,
} from "../src/geometry.js";

describe("measurement conversion", () => {
  it("converts common units to inches", () => {
    expect(toInches(2, "ft")).toBe(24);
    expect(toInches(2.54, "cm")).toBeCloseTo(1);
    expect(toInches(1, "m")).toBeCloseTo(39.3700787);
  });

  it("calculates scale from two clicks and a real length", () => {
    const result = scaleFromCalibration({ x: 10, y: 20 }, { x: 130, y: 20 }, 10, "ft");
    expect(result).toBe(1);
  });

  it("rejects invalid or tiny calibration measurements", () => {
    expect(() => toInches(0, "ft")).toThrow(/greater than zero/);
    expect(() => scaleFromCalibration({ x: 0, y: 0 }, { x: 1, y: 0 }, 10, "ft")).toThrow(/too close/);
  });

  it("measures diagonal distances", () => {
    expect(distance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5);
  });
});

describe("furniture geometry", () => {
  it("builds rectangle and L-shaped paths in drawing coordinates", () => {
    const rectangle = furniturePath({ type: "rect", width: 10, depth: 5 }, 2);
    expect(rectangle).toBe("M -10 -5 H 10 V 5 H -10 Z");

    const sectional = furniturePath(
      { type: "l", width: 100, depth: 80, armDepth: 30, returnWidth: 35 },
      1,
    );
    expect(sectional).toContain("H 50");
    expect(sectional).toContain("V -10");
    expect(sectional).toContain("H -15");
    expect(sectional).toContain("V 40");
  });

  it("validates L-shape thickness against its outside dimensions", () => {
    expect(() => validateFurniture({
      type: "l",
      name: "Sectional",
      width: 80,
      depth: 40,
      armDepth: 40,
      returnWidth: 20,
    })).toThrow(/Arm depth/);
  });

  it("normalizes rotation", () => {
    expect(normalizeAngle(-15)).toBe(345);
    expect(normalizeAngle(375)).toBe(15);
  });

  it("resizes from the visible edge while keeping the opposite edge fixed", () => {
    const result = resizeFurnitureFromHandle(
      { type: "rect", width: 48, depth: 30, x: 100, y: 100, rotation: 0 },
      20,
      0,
      "width",
      2,
    );
    expect(result).toEqual({ width: 58, depth: 30, x: 110, y: 100 });
  });

  it("resizes rotated and L-shaped furniture in local coordinates", () => {
    const rotated = resizeFurnitureFromHandle(
      { type: "rect", width: 48, depth: 30, x: 100, y: 100, rotation: 90 },
      0,
      20,
      "width",
      2,
    );
    expect(rotated.width).toBe(58);
    expect(rotated.x).toBeCloseTo(100);
    expect(rotated.y).toBeCloseTo(110);

    const clamped = resizeFurnitureFromHandle(
      { type: "l", width: 60, depth: 50, returnWidth: 24, armDepth: 20, x: 100, y: 100, rotation: 0 },
      -500,
      -500,
      "both",
      2,
    );
    expect(clamped.width).toBe(24.25);
    expect(clamped.depth).toBe(20.25);
  });
});
