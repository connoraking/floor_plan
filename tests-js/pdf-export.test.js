import { PDFDocument } from "pdf-lib";
import { describe, expect, it } from "vitest";
import { buildFlattenedPdf } from "../src/pdf-export.js";

const ONE_PIXEL_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+X7xLAAAAAElFTkSuQmCC";

describe("shareable PDF export", () => {
  it("creates a real multi-page PDF with the requested page sizes", async () => {
    const progress = [];
    const bytes = await buildFlattenedPdf([
      { width: 612, height: 792, png: ONE_PIXEL_PNG },
      { width: 792, height: 612, getPng: async () => ONE_PIXEL_PNG },
    ], { title: "Test furnished plan", onProgress: (current, total) => progress.push([current, total]) });
    const pdf = await PDFDocument.load(bytes);

    expect(new TextDecoder().decode(bytes.slice(0, 5))).toBe("%PDF-");
    expect(pdf.getPageCount()).toBe(2);
    expect(pdf.getPage(0).getSize()).toEqual({ width: 612, height: 792 });
    expect(pdf.getPage(1).getSize()).toEqual({ width: 792, height: 612 });
    expect(progress).toEqual([[1, 2], [2, 2]]);
  });

  it("rejects an export without pages", async () => {
    await expect(buildFlattenedPdf([])).rejects.toThrow(/no pages/i);
  });
});
