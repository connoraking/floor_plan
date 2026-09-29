import { describe, expect, it } from "vitest";
import {
  PROJECT_FORMAT,
  PROJECT_VERSION,
  base64ToBytes,
  bytesToBase64,
  parseProject,
} from "../src/project.js";

describe("portable project files", () => {
  it("round-trips binary PDF data without changing a byte", () => {
    const source = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0, 1, 127, 128, 255]);
    expect(base64ToBytes(bytesToBase64(source))).toEqual(source);
  });

  it("accepts the current project structure", () => {
    const project = {
      format: PROJECT_FORMAT,
      version: PROJECT_VERSION,
      pdfBase64: bytesToBase64(new Uint8Array([1, 2, 3])),
      pages: [{ pointsPerInch: 1.5 }],
      items: [],
    };
    expect(parseProject(JSON.stringify(project))).toEqual(project);
  });

  it("rejects corrupt, old, and incomplete projects with useful errors", () => {
    expect(() => parseProject("not json")).toThrow(/not valid JSON/);
    expect(() => parseProject(JSON.stringify({ format: PROJECT_FORMAT, version: 1 }))).toThrow(/not a Floor Planner 2/);
    expect(() => parseProject(JSON.stringify({ format: PROJECT_FORMAT, version: PROJECT_VERSION }))).toThrow(/incomplete/);
    expect(() => base64ToBytes("%%%")) .toThrow(/damaged/);
  });
});
