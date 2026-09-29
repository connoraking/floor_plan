import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(),
}));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "pdf.worker.mjs" }));

describe("application startup", () => {
  beforeAll(async () => {
    const html = await readFile(resolve(process.cwd(), "src/index.html"), "utf8");
    document.documentElement.innerHTML = html;
    await import("../src/app.js");
  });

  it("binds the main controls without a startup error", () => {
    expect(window.__floorPlannerTest.getState()).toMatchObject({ pageCount: 0, zoom: 1 });
    expect(document.getElementById("open-pdf").disabled).toBe(false);
    expect(document.getElementById("zoom-slider").disabled).toBe(true);
  });
});
