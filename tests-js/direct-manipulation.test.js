import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { beforeAll, describe, expect, it, vi } from "vitest";

const pdfPage = {
  getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale }),
  render: () => ({ promise: Promise.resolve() }),
};

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: () => ({
    promise: Promise.resolve({ numPages: 1, getPage: async () => pdfPage }),
    destroy: async () => {},
  }),
}));
vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({ default: "pdf.worker.mjs" }));

describe("direct furniture manipulation", () => {
  beforeAll(async () => {
    const html = await readFile(resolve(process.cwd(), "src/index.html"), "utf8");
    document.documentElement.innerHTML = html;
    window.requestAnimationFrame = (callback) => callback();
    window.PointerEvent = window.MouseEvent;
    window.HTMLElement.prototype.scrollIntoView = () => {};
    window.SVGElement.prototype.setPointerCapture = () => {};
    window.HTMLDialogElement.prototype.showModal = function showModal() { this.open = true; };
    window.HTMLDialogElement.prototype.close = function close() { this.open = false; };
    window.HTMLCanvasElement.prototype.getContext = () => ({ fillRect: () => {}, drawImage: () => {} });
    await import("../src/app.js");
    await window.__floorPlannerTest.loadPdfBytes(new Uint8Array([37, 80, 68, 70]), "test.pdf");

    const svg = document.querySelector(".page-overlay");
    svg.getBoundingClientRect = () => {
      const width = Number.parseFloat(svg.parentElement.style.width) || 240;
      return { left: 0, top: 0, right: width, bottom: width * 4 / 3, width, height: width * 4 / 3 };
    };

    document.getElementById("calibrate").click();
    const point = (x, pointerId) => svg.dispatchEvent(new PointerEvent("pointerdown", {
      bubbles: true,
      clientX: x,
      clientY: 250,
      pointerId,
      button: 0,
    }));
    point(40, 1);
    point(200, 2);
    document.getElementById("calibration-length").value = "10";
    document.getElementById("calibration-unit").value = "ft";
    document.getElementById("calibration-form").requestSubmit();

    document.getElementById("add-rectangle").click();
    document.getElementById("furniture-name").value = "Sofa";
    document.getElementById("furniture-width").value = "84";
    document.getElementById("furniture-depth").value = "36";
    document.getElementById("furniture-form").requestSubmit();
  });

  it("shows direct width, depth, and corner handles on selected furniture", () => {
    expect([...document.querySelectorAll(".resize-handle")].map((node) => node.dataset.resizeAxis))
      .toEqual(["width", "depth", "both"]);
    expect(document.querySelector(".resize-outline")).not.toBeNull();
  });

  it("changes the furniture dimensions by dragging a handle", () => {
    const svg = document.querySelector(".page-overlay");
    const handle = document.querySelector('.resize-handle[data-resize-axis="width"]');
    handle.dispatchEvent(new PointerEvent("pointerdown", {
      bubbles: true,
      clientX: 160,
      clientY: 160,
      pointerId: 9,
      button: 0,
    }));
    svg.dispatchEvent(new PointerEvent("pointermove", {
      bubbles: true,
      clientX: 190,
      clientY: 160,
      pointerId: 9,
      button: 0,
    }));
    svg.dispatchEvent(new PointerEvent("pointerup", {
      bubbles: true,
      clientX: 190,
      clientY: 160,
      pointerId: 9,
      button: 0,
    }));

    const item = window.__floorPlannerTest.getState().items[0];
    expect(item.width).toBeGreaterThan(84);
    expect(Number(document.getElementById("edit-width").value)).toBe(item.width);
  });

  it("keeps calibration points eight screen pixels wide as zoom changes", () => {
    const slider = document.getElementById("zoom-slider");
    slider.value = "200";
    slider.dispatchEvent(new Event("input", { bubbles: true }));

    const svg = document.querySelector(".page-overlay");
    const radiusInPageUnits = Number(document.querySelector(".calibration-point").getAttribute("r"));
    const screenDiameter = radiusInPageUnits * 2 * svg.getBoundingClientRect().width / 600;
    expect(screenDiameter).toBeCloseTo(8);
  });
});
