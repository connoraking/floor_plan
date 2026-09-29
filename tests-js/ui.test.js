import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { JSDOM } from "jsdom";
import { describe, expect, it } from "vitest";

describe("visible desktop controls", () => {
  it("keeps the main actions labeled, high-contrast, and keyboard reachable", async () => {
    const html = await readFile(resolve(process.cwd(), "src/index.html"), "utf8");
    const css = await readFile(resolve(process.cwd(), "src/styles.css"), "utf8");
    const dom = new JSDOM(html);
    const document = dom.window.document;

    const openPdf = document.getElementById("open-pdf");
    const calibrate = document.getElementById("calibrate");
    expect(openPdf.textContent).toMatch(/Open PDF/);
    expect(openPdf.classList.contains("button-primary")).toBe(true);
    expect(calibrate.textContent).toMatch(/Calibrate this page/);
    expect(calibrate.classList.contains("button-accent")).toBe(true);
    expect(openPdf.getAttribute("tabindex")).not.toBe("-1");
    expect(calibrate.getAttribute("tabindex")).not.toBe("-1");

    expect(css).toMatch(/\.button-primary\s*\{[^}]*color:\s*var\(--white\)[^}]*background:\s*var\(--blue-600\)/s);
    expect(css).toMatch(/\.button-accent\s*\{[^}]*color:\s*#2d1600[^}]*background:\s*#fdb022/s);
    expect(css).toMatch(/--focus:\s*#175cd3/);
    expect(css).toMatch(/:focus-visible\s*\{[^}]*outline:\s*3px solid var\(--focus\)[^}]*box-shadow:/s);
    expect(document.getElementById("calibration-dialog").getAttribute("aria-labelledby")).toBe("calibration-dialog-title");
    expect(document.getElementById("calibration-cancel").textContent).toMatch(/Cancel/);
    expect(document.getElementById("calibration-all-pages").checked).toBe(false);
    expect(document.getElementById("zoom-slider").getAttribute("min")).toBe("40");
    expect(document.getElementById("zoom-slider").getAttribute("max")).toBe("250");
    expect(document.getElementById("zoom-fit").textContent).toMatch(/Fit page/);
  });

  it("offers both continuous and two-page layouts", async () => {
    const html = await readFile(resolve(process.cwd(), "src/index.html"), "utf8");
    const css = await readFile(resolve(process.cwd(), "src/styles.css"), "utf8");
    const document = new JSDOM(html).window.document;
    const options = [...document.querySelectorAll("#page-layout option")].map((option) => option.value);
    expect(options).toEqual(["continuous", "spread"]);
    expect(document.getElementById("page-gallery")).not.toBeNull();
    expect(document.getElementById("page-gallery").hasAttribute("aria-live")).toBe(false);
    expect(css).toMatch(/grid-template-columns:\s*repeat\(2, max-content\)/);
    expect(css).toMatch(/justify-content:\s*safe center/);
  });
});
