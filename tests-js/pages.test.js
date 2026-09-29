import { describe, expect, it } from "vitest";
import { pageRecordsForProject, removePageAt } from "../src/pages.js";

describe("PDF page management", () => {
  it("keeps every page in PDFs longer than two pages", () => {
    expect(pageRecordsForProject(5).map((record) => record.pdfPageNumber)).toEqual([1, 2, 3, 4, 5]);
  });

  it("restores only saved source pages after a page was removed", () => {
    const savedPages = [1, 2, 4, 5].map((pdfPageNumber) => ({ pdfPageNumber }));
    expect(pageRecordsForProject(5, savedPages).map((record) => record.pdfPageNumber)).toEqual([1, 2, 4, 5]);
  });

  it("removes the requested page, its furniture, and reindexes later furniture", () => {
    const pages = [1, 2, 3, 4, 5].map((pdfPageNumber, index) => ({ index, pdfPageNumber }));
    const items = [
      { id: "first", pageIndex: 0 },
      { id: "removed", pageIndex: 2 },
      { id: "last", pageIndex: 4 },
    ];
    const result = removePageAt(pages, items, 2);

    expect(result.pages.map((page) => page.pdfPageNumber)).toEqual([1, 2, 4, 5]);
    expect(result.pages.map((page) => page.index)).toEqual([0, 1, 2, 3]);
    expect(result.items).toEqual([
      { id: "first", pageIndex: 0 },
      { id: "last", pageIndex: 3 },
    ]);
  });

  it("does not allow the final remaining page to be removed", () => {
    expect(() => removePageAt([{ index: 0, pdfPageNumber: 1 }], [], 0)).toThrow(/at least one page/);
  });
});
