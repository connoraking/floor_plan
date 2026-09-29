import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

describe("multi-page PDF support", () => {
  it("opens PDFs with more than two pages", async () => {
    const path = resolve(process.cwd(), "tests-js/fixtures/five-page-floor-plan.pdf");
    const bytes = new Uint8Array(await readFile(path));
    const loadingTask = getDocument({ data: bytes, disableWorker: true });
    const document = await loadingTask.promise;

    expect(document.numPages).toBe(5);
    expect((await document.getPage(5)).getViewport({ scale: 1 }).width).toBe(612);
    await loadingTask.destroy();
  });

  it("opens the two-page floor-plan fixture and exposes both pages", async () => {
    const path = resolve(process.cwd(), "tests-js/fixtures/two-page-floor-plan.pdf");
    const bytes = new Uint8Array(await readFile(path));
    const loadingTask = getDocument({ data: bytes, disableWorker: true });
    const document = await loadingTask.promise;

    expect(document.numPages).toBe(2);
    const first = await document.getPage(1);
    const second = await document.getPage(2);
    expect(first.getViewport({ scale: 1 }).width).toBe(612);
    expect(second.getViewport({ scale: 1 }).height).toBe(792);

    const replacementBytes = new Uint8Array(await readFile(path));
    const replacementTask = getDocument({ data: replacementBytes, disableWorker: true });
    const replacement = await replacementTask.promise;
    await loadingTask.destroy();
    expect(replacement.numPages).toBe(2);
    expect((await replacement.getPage(1)).getViewport({ scale: 1 }).width).toBe(612);
    await replacementTask.destroy();
  });
});
