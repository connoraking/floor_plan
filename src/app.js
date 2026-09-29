import "./styles.css";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {
  clamp,
  furniturePath,
  normalizeAngle,
  pointFromPointer,
  scaleFromCalibration,
  validateFurniture,
} from "./geometry.js";
import {
  PROJECT_FORMAT,
  PROJECT_VERSION,
  base64ToBytes,
  bytesToBase64,
  parseProject,
} from "./project.js";
import {
  calculateCappedRenderScale,
  calculateContinuousFitFactor,
  calculateSpreadFitFactor,
} from "./layout.js";
import { pageRecordsForProject, removePageAt } from "./pages.js";
import { buildFlattenedPdf } from "./pdf-export.js";

GlobalWorkerOptions.workerSrc = workerUrl;

const SVG_NS = "http://www.w3.org/2000/svg";
const CSS_PDF_SCALE = 1.12;
const MAX_RENDER_PIXELS = 10_000_000;
const MAX_RENDERED_PAGE_CANVASES = 4;
const COLORS = ["#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed"];
const EXPORT_SVG_STYLES = `
  .furniture-shape { stroke: #101828; stroke-width: 1.5; vector-effect: non-scaling-stroke; }
  .furniture-label { fill: #101828; font: 800 11px sans-serif; paint-order: stroke; stroke: rgba(255,255,255,.88); stroke-width: 3px; text-anchor: middle; vector-effect: non-scaling-stroke; }
  .calibration-line { stroke: #f04438; stroke-width: 3px; stroke-dasharray: 8 5; vector-effect: non-scaling-stroke; }
  .calibration-point { fill: #fff; stroke: #f04438; stroke-width: 3px; vector-effect: non-scaling-stroke; }
  .calibration-label { fill: #b42318; font: 900 12px sans-serif; paint-order: stroke; stroke: #fff; stroke-width: 4px; text-anchor: middle; vector-effect: non-scaling-stroke; }
`;
const electronApi = window.floorPlannerApi;

const elements = Object.fromEntries(
  [
    "open-pdf",
    "open-pdf-side",
    "empty-open",
    "open-project",
    "save-project",
    "export-pdf",
    "zoom-out",
    "zoom-in",
    "zoom-fit",
    "zoom-slider",
    "zoom-value",
    "pdf-summary",
    "scale-summary",
    "calibrate",
    "add-rectangle",
    "add-l-shape",
    "document-name",
    "page-count",
    "active-page-status",
    "page-layout",
    "drop-zone",
    "page-gallery",
    "calibration-guide",
    "calibration-guide-title",
    "calibration-guide-detail",
    "cancel-calibration",
    "calibration-dialog",
    "calibration-form",
    "calibration-length",
    "calibration-unit",
    "calibration-all-pages",
    "calibration-back",
    "calibration-cancel",
    "furniture-dialog",
    "furniture-form",
    "furniture-dialog-title",
    "furniture-name",
    "furniture-width",
    "furniture-depth",
    "furniture-arm-depth",
    "furniture-return-width",
    "new-l-shape-fields",
    "furniture-shape-help",
    "furniture-cancel",
    "pdf-file-input",
    "project-file-input",
    "toast-region",
    "inspector-empty",
    "inspector-form",
    "inspector-title",
    "close-inspector",
    "edit-name",
    "edit-width",
    "edit-depth",
    "edit-arm-depth",
    "edit-return-width",
    "edit-rotation",
    "edit-locked",
    "l-shape-fields",
    "rotate-left",
    "rotate-right",
    "duplicate",
    "delete",
    "step-open",
    "step-calibrate",
    "step-furniture",
  ].map((id) => [id, document.getElementById(id)]),
);

const state = {
  pdf: null,
  pdfLoadingTask: null,
  pdfBytes: null,
  fileName: null,
  projectName: null,
  pages: [],
  items: [],
  activePage: 0,
  selectedItemId: null,
  zoom: 1,
  layout: "continuous",
  newShapeType: "rect",
  dirty: false,
  calibration: {
    active: false,
    pageIndex: null,
    start: null,
    current: null,
  },
  pendingCalibration: null,
  drag: null,
  pageObserver: null,
  visiblePageIndexes: new Set(),
};

function createSvgElement(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

function uniqueId() {
  return globalThis.crypto?.randomUUID?.() || `piece-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " is-error" : ""}`;
  toast.textContent = message;
  elements["toast-region"].append(toast);
  window.setTimeout(() => toast.remove(), 3800);
}

function safeErrorMessage(error, fallback) {
  const message = error instanceof Error ? error.message : String(error || "");
  return message && message !== "undefined" ? message : fallback;
}

function markDirty(value = true) {
  state.dirty = value;
  electronApi?.setDirty(value);
  updateDocumentTitle();
}

function updateDocumentTitle() {
  const name = state.projectName || state.fileName || "Floor Planner";
  document.title = `${state.dirty ? "• " : ""}${name} — Floor Planner`;
}

function activePage() {
  return state.pages[state.activePage] || null;
}

function selectedItem() {
  return state.items.find((item) => item.id === state.selectedItemId) || null;
}

async function choosePdf() {
  try {
    if (electronApi) {
      if (!(await confirmDiscardIfNeeded())) return;
      const result = await electronApi.openPdf();
      if (!result) return;
      await loadPdf(new Uint8Array(result.data), result.name);
    } else {
      elements["pdf-file-input"].click();
    }
  } catch (error) {
    showToast(`Could not open that PDF: ${safeErrorMessage(error, "Unknown error")}`, true);
  }
}

async function readPdfFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
    showToast("Please choose a PDF file.", true);
    return;
  }
  try {
    if (!(await confirmDiscardIfNeeded())) return;
    await loadPdf(new Uint8Array(await file.arrayBuffer()), file.name);
  } catch (error) {
    showToast(`Could not open that PDF: ${safeErrorMessage(error, "The file may be damaged.")}`, true);
  }
}

async function loadPdf(bytes, fileName, restoredProject = null) {
  cancelCalibration();
  setLoading(true, "Opening PDF…");
  let loadingTask = null;
  try {
    const retainedBytes = bytes.slice();
    loadingTask = getDocument({ data: bytes.slice() });
    const pdf = await loadingTask.promise;
    const records = pageRecordsForProject(pdf.numPages, restoredProject ? restoredProject.pages : null);
    const newPages = [];
    for (let index = 0; index < records.length; index += 1) {
      const { pdfPageNumber, savedPage: restoredPage } = records[index];
      const pdfPage = await pdf.getPage(pdfPageNumber);
      const viewport = pdfPage.getViewport({ scale: 1 });
      newPages.push({
        index,
        pdfPageNumber,
        pdfPage,
        width: viewport.width,
        height: viewport.height,
        pointsPerInch: Number(restoredPage?.pointsPerInch) || null,
        scaleLabel: restoredPage?.scaleLabel || null,
        calibration: restoredPage?.calibration || null,
        card: null,
        surface: null,
        canvas: null,
        svg: null,
        renderPromise: null,
        rendered: false,
      });
    }

    let newItems = [];
    if (restoredProject?.items) {
      newItems = restoredProject.items
        .filter((item) => Number.isInteger(item.pageIndex) && item.pageIndex >= 0 && item.pageIndex < newPages.length)
        .map((item) => ({
          id: item.id || uniqueId(),
          type: item.type === "l" ? "l" : "rect",
          name: String(item.name || "Furniture"),
          pageIndex: item.pageIndex,
          x: Number.isFinite(Number(item.x)) ? Number(item.x) : newPages[item.pageIndex].width / 2,
          y: Number.isFinite(Number(item.y)) ? Number(item.y) : newPages[item.pageIndex].height / 2,
          width: Number(item.width) || 36,
          depth: Number(item.depth) || 36,
          armDepth: Number(item.armDepth) || 18,
          returnWidth: Number(item.returnWidth) || 18,
          rotation: normalizeAngle(item.rotation),
          color: COLORS.includes(item.color) ? item.color : COLORS[0],
          locked: Boolean(item.locked),
        }));
    }

    if (state.pdfLoadingTask) await state.pdfLoadingTask.destroy();
    state.pdf = pdf;
    state.pdfLoadingTask = loadingTask;
    state.pdfBytes = retainedBytes;
    state.fileName = fileName || "floor-plan.pdf";
    state.projectName = restoredProject?.projectName || null;
    state.pages = newPages;
    state.items = newItems;
    state.activePage = 0;
    state.selectedItemId = null;

    buildPageGallery();
    updateSurfaceSizes();
    await ensurePageRendered(0);
    updateUi();
    await new Promise((resolve) => window.requestAnimationFrame(resolve));
    fitActivePage(false);
    markDirty(false);
    showToast(`Opened ${pdf.numPages} page${pdf.numPages === 1 ? "" : "s"}.`);
  } catch (error) {
    if (loadingTask && state.pdfLoadingTask !== loadingTask) await loadingTask.destroy().catch(() => {});
    if (state.pdfLoadingTask === loadingTask) {
      await loadingTask.destroy().catch(() => {});
      state.pdf = null;
      state.pdfLoadingTask = null;
      state.pdfBytes = null;
      state.pages = [];
      state.items = [];
    }
    throw error;
  } finally {
    setLoading(false);
    updateUi();
  }
}

function setLoading(loading, message = "Loading…") {
  for (const button of [elements["open-pdf"], elements["open-pdf-side"], elements["empty-open"]]) {
    button.disabled = loading;
  }
  if (loading) {
    elements["document-name"].textContent = message;
  }
}

function buildPageGallery() {
  const gallery = elements["page-gallery"];
  state.pageObserver?.disconnect();
  state.pageObserver = null;
  state.visiblePageIndexes.clear();
  gallery.replaceChildren();
  for (const page of state.pages) {
    const card = document.createElement("article");
    card.className = "page-card";
    card.dataset.pageIndex = page.index;
    card.tabIndex = 0;
    card.setAttribute("aria-label", `PDF page ${page.pdfPageNumber}`);

    const header = document.createElement("header");
    header.className = "page-header";
    const pageInfo = document.createElement("div");
    pageInfo.className = "page-info";
    const pageName = document.createElement("strong");
    pageName.textContent = `PDF page ${page.pdfPageNumber}`;
    const scaleStatus = document.createElement("span");
    scaleStatus.className = "page-scale-status";
    scaleStatus.dataset.role = "scale-status";
    pageInfo.append(pageName, scaleStatus);
    const pageCalibrate = document.createElement("button");
    pageCalibrate.className = "button button-accent button-small page-calibrate";
    pageCalibrate.type = "button";
    pageCalibrate.textContent = "Calibrate";
    pageCalibrate.setAttribute("aria-label", `Calibrate PDF page ${page.pdfPageNumber}`);
    pageCalibrate.addEventListener("click", (event) => {
      event.stopPropagation();
      setActivePage(page.index);
      startCalibration();
    });
    const removeButton = document.createElement("button");
    removeButton.className = "button button-danger button-small page-remove";
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.disabled = state.pages.length <= 1;
    removeButton.title = removeButton.disabled ? "A floor plan must keep at least one page" : `Remove PDF page ${page.pdfPageNumber}`;
    removeButton.setAttribute("aria-label", `Remove PDF page ${page.pdfPageNumber}`);
    removeButton.addEventListener("click", (event) => {
      event.stopPropagation();
      removePage(page.index);
    });
    const pageActions = document.createElement("div");
    pageActions.className = "page-actions";
    pageActions.append(pageCalibrate, removeButton);
    header.append(pageInfo, pageActions);

    const surface = document.createElement("div");
    surface.className = "pdf-surface";
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    const svg = createSvgElement("svg", {
      class: "page-overlay",
      viewBox: `0 0 ${page.width} ${page.height}`,
      "aria-label": `Furniture overlay for PDF page ${page.pdfPageNumber}`,
    });
    svg.dataset.pageIndex = page.index;
    surface.append(canvas, svg);
    card.append(header, surface);
    gallery.append(card);

    page.card = card;
    page.surface = surface;
    page.canvas = canvas;
    page.svg = svg;

    card.addEventListener("pointerdown", () => setActivePage(page.index));
    card.addEventListener("keydown", (event) => {
      if (event.target !== card || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      setActivePage(page.index);
    });
    svg.addEventListener("pointerdown", handleOverlayPointerDown);
    svg.addEventListener("pointermove", handleOverlayPointerMove);
    svg.addEventListener("pointerup", handleOverlayPointerUp);
    svg.addEventListener("pointercancel", handleOverlayPointerUp);
    renderOverlay(page.index);
  }
  observePageVisibility();
}

function observePageVisibility() {
  if (!("IntersectionObserver" in window)) {
    for (const page of state.pages) ensurePageRendered(page.index);
    return;
  }
  state.pageObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const pageIndex = Number(entry.target.dataset.pageIndex);
      if (entry.isIntersecting) {
        state.visiblePageIndexes.add(pageIndex);
        ensurePageRendered(pageIndex);
      } else {
        state.visiblePageIndexes.delete(pageIndex);
      }
    }
  }, { root: elements["page-gallery"], rootMargin: "350px 0px" });
  for (const page of state.pages) state.pageObserver.observe(page.card);
}

async function ensurePageRendered(pageIndex) {
  const page = state.pages[pageIndex];
  if (!page || page.rendered) return;
  if (page.renderPromise) return page.renderPromise;
  page.renderPromise = renderPdfPage(page)
    .then(() => {
      page.rendered = true;
      page.surface?.classList.add("is-rendered");
      evictDistantPageCanvases(page.index);
    })
    .catch((error) => {
      if (error?.name !== "RenderingCancelledException") {
        showToast(`Could not display PDF page ${page.pdfPageNumber}: ${safeErrorMessage(error, "Unknown error")}`, true);
      }
    })
    .finally(() => {
      page.renderPromise = null;
    });
  return page.renderPromise;
}

async function renderPdfPage(page) {
  const baseViewport = page.pdfPage.getViewport({ scale: 1 });
  const renderScale = calculateCappedRenderScale(
    baseViewport.width,
    baseViewport.height,
    CSS_PDF_SCALE * Math.min(window.devicePixelRatio || 1, 2),
    MAX_RENDER_PIXELS,
  );
  const viewport = page.pdfPage.getViewport({ scale: renderScale });
  page.canvas.width = Math.floor(viewport.width);
  page.canvas.height = Math.floor(viewport.height);
  const context = page.canvas.getContext("2d", { alpha: false });
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, page.canvas.width, page.canvas.height);
  await page.pdfPage.render({ canvasContext: context, viewport }).promise;
}

function evictDistantPageCanvases(referenceIndex) {
  const rendered = () => state.pages.filter((page) => page.rendered);
  while (rendered().length > MAX_RENDERED_PAGE_CANVASES) {
    const candidate = rendered()
      .filter((page) => page.index !== referenceIndex && page.index !== state.activePage && !state.visiblePageIndexes.has(page.index))
      .sort((first, second) => Math.abs(second.index - referenceIndex) - Math.abs(first.index - referenceIndex))[0];
    if (!candidate) return;
    candidate.canvas.width = 1;
    candidate.canvas.height = 1;
    candidate.rendered = false;
    candidate.surface?.classList.remove("is-rendered");
  }
}

function updateSurfaceSizes() {
  for (const page of state.pages) {
    const layoutFactor = state.layout === "spread"
      ? spreadFitFactor()
      : calculateContinuousFitFactor(elements["page-gallery"].clientWidth, page.width, CSS_PDF_SCALE);
    const width = page.width * CSS_PDF_SCALE * state.zoom * layoutFactor;
    page.surface.style.width = `${width}px`;
    page.surface.style.height = `${(width * page.height) / page.width}px`;
  }
  const zoomPercent = Math.round(state.zoom * 100);
  elements["zoom-value"].textContent = `${zoomPercent}%`;
  elements["zoom-slider"].value = String(zoomPercent);
}

function spreadFitFactor() {
  return calculateSpreadFitFactor(
    elements["page-gallery"].clientWidth,
    state.pages.map((page) => page.width),
    CSS_PDF_SCALE,
  );
}

function setActivePage(index) {
  if (!state.pages[index]) return;
  ensurePageRendered(index);
  if (state.activePage === index) return;
  if (state.calibration.active) cancelCalibration();
  state.activePage = index;
  if (selectedItem()?.pageIndex !== index) state.selectedItemId = null;
  updateUi();
}

function removePage(index) {
  const page = state.pages[index];
  if (!page) return;
  if (state.pages.length <= 1) {
    showToast("A floor plan must keep at least one page.", true);
    return;
  }
  const furnitureCount = state.items.filter((item) => item.pageIndex === index).length;
  const furnitureWarning = furnitureCount
    ? ` This will also remove ${furnitureCount} furniture piece${furnitureCount === 1 ? "" : "s"} from that page.`
    : "";
  if (!window.confirm(`Remove PDF page ${page.pdfPageNumber} from this project?${furnitureWarning}`)) return;

  if (state.calibration.active || state.pendingCalibration) cancelCalibration();
  const previousActivePage = state.activePage;
  const result = removePageAt(state.pages, state.items, index);
  state.pages = result.pages;
  state.items = result.items;
  state.selectedItemId = state.items.some((item) => item.id === state.selectedItemId) ? state.selectedItemId : null;
  state.activePage = previousActivePage === index
    ? Math.min(index, state.pages.length - 1)
    : previousActivePage > index
      ? previousActivePage - 1
      : previousActivePage;
  buildPageGallery();
  updateSurfaceSizes();
  ensurePageRendered(state.activePage);
  markDirty();
  updateUi();
  state.pages[state.activePage]?.card?.scrollIntoView({ block: "center" });
  showToast(`PDF page ${page.pdfPageNumber} removed from this project.`);
}

function renderOverlay(pageIndex) {
  const page = state.pages[pageIndex];
  if (!page?.svg) return;
  const svg = page.svg;
  svg.replaceChildren();

  if (page.calibration?.start && page.calibration?.end) {
    appendCalibrationMarker(svg, page.calibration.start, page.calibration.end, page.calibration.label || page.scaleLabel || "Scale");
  }

  for (const item of state.items.filter((entry) => entry.pageIndex === pageIndex)) {
    if (!page.pointsPerInch) continue;
    const group = createSvgElement("g", {
      class: `furniture${item.id === state.selectedItemId ? " is-selected" : ""}${item.locked ? " is-locked" : ""}`,
      transform: `translate(${item.x} ${item.y}) rotate(${item.rotation})`,
      "data-item-id": item.id,
      tabindex: "0",
      role: "button",
      "aria-pressed": item.id === state.selectedItemId ? "true" : "false",
      "aria-label": `${item.name}, ${item.width} by ${item.depth} inches`,
    });
    const path = createSvgElement("path", {
      class: "furniture-shape",
      d: furniturePath(item, page.pointsPerInch),
      fill: item.color,
      "fill-opacity": "0.46",
    });
    const nameLabel = createSvgElement("text", { class: "furniture-label", y: "-3" });
    nameLabel.textContent = item.name;
    const sizeLabel = createSvgElement("text", { class: "furniture-label", y: "11" });
    sizeLabel.textContent = `${formatInches(item.width)} × ${formatInches(item.depth)}`;
    group.append(path, nameLabel, sizeLabel);
    group.addEventListener("focus", () => selectItemFromKeyboard(item.id));
    group.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      selectItemFromKeyboard(item.id);
    });
    svg.append(group);
  }

  if (state.calibration.pageIndex === pageIndex && state.calibration.start && state.calibration.current) {
    appendCalibrationMarker(svg, state.calibration.start, state.calibration.current, "Click second point", true);
  } else if (state.pendingCalibration?.pageIndex === pageIndex) {
    appendCalibrationMarker(
      svg,
      state.pendingCalibration.start,
      state.pendingCalibration.end,
      "Selected distance",
      true,
    );
  }
}

function selectItemFromKeyboard(id) {
  state.selectedItemId = id;
  for (const group of document.querySelectorAll(".furniture")) {
    const selected = group.dataset.itemId === id;
    group.classList.toggle("is-selected", selected);
    group.setAttribute("aria-pressed", selected ? "true" : "false");
  }
  updateInspector();
}

function appendCalibrationMarker(svg, start, end, label, temporary = false) {
  const line = createSvgElement("line", {
    class: `calibration-line${temporary ? " is-temporary" : ""}`,
    x1: start.x,
    y1: start.y,
    x2: end.x,
    y2: end.y,
  });
  const radius = 5;
  const first = createSvgElement("circle", {
    class: "calibration-point",
    cx: start.x,
    cy: start.y,
    r: radius,
  });
  const second = createSvgElement("circle", {
    class: "calibration-point",
    cx: end.x,
    cy: end.y,
    r: radius,
  });
  const text = createSvgElement("text", {
    class: "calibration-label",
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2 - 9,
  });
  text.textContent = label;
  svg.append(line, first, second, text);
}

function formatInches(value) {
  const rounded = Math.round(Number(value) * 4) / 4;
  return `${rounded}\u2033`;
}

function handleOverlayPointerDown(event) {
  const svg = event.currentTarget;
  const pageIndex = Number(svg.dataset.pageIndex);
  setActivePage(pageIndex);
  const page = state.pages[pageIndex];

  if (state.calibration.active && state.calibration.pageIndex === pageIndex) {
    event.preventDefault();
    const point = pointFromPointer(event, svg, page);
    if (!state.calibration.start) {
      state.calibration.start = point;
      state.calibration.current = point;
      elements["calibration-guide-title"].textContent = "Now click the second endpoint";
      elements["calibration-guide-detail"].textContent = "Move across the known dimension and click its other end.";
      renderOverlay(pageIndex);
    } else {
      try {
        scaleFromCalibration(state.calibration.start, point, 1, "in");
        state.pendingCalibration = { pageIndex, start: state.calibration.start, end: point };
        state.calibration = { active: false, pageIndex: null, start: null, current: null };
        elements["calibration-guide"].hidden = true;
        updateCalibrationCursors();
        renderOverlay(pageIndex);
        elements["calibration-dialog"].showModal();
        window.setTimeout(() => elements["calibration-length"].select(), 20);
      } catch (error) {
        showToast(safeErrorMessage(error, "Choose two points farther apart."), true);
      }
    }
    return;
  }

  const group = event.target.closest?.(".furniture");
  if (!group) {
    selectItem(null);
    return;
  }

  const item = state.items.find((entry) => entry.id === group.dataset.itemId);
  if (!item) return;
  selectItem(item.id);
  if (item.locked) {
    showToast("This piece is locked. Unlock it in the right panel to move it.");
    return;
  }
  event.preventDefault();
  const point = pointFromPointer(event, svg, page);
  state.drag = { itemId: item.id, pageIndex, pointerId: event.pointerId, start: point, x: item.x, y: item.y };
  svg.setPointerCapture(event.pointerId);
}

function handleOverlayPointerMove(event) {
  const svg = event.currentTarget;
  const pageIndex = Number(svg.dataset.pageIndex);
  const page = state.pages[pageIndex];
  if (state.calibration.active && state.calibration.pageIndex === pageIndex && state.calibration.start) {
    state.calibration.current = pointFromPointer(event, svg, page);
    renderOverlay(pageIndex);
    return;
  }
  if (!state.drag || state.drag.pageIndex !== pageIndex || state.drag.pointerId !== event.pointerId) return;
  const item = state.items.find((entry) => entry.id === state.drag.itemId);
  if (!item) return;
  const point = pointFromPointer(event, svg, page);
  item.x = clamp(state.drag.x + point.x - state.drag.start.x, 0, page.width);
  item.y = clamp(state.drag.y + point.y - state.drag.start.y, 0, page.height);
  renderOverlay(pageIndex);
}

function handleOverlayPointerUp(event) {
  if (!state.drag || state.drag.pointerId !== event.pointerId) return;
  const pageIndex = state.drag.pageIndex;
  state.drag = null;
  markDirty();
  renderOverlay(pageIndex);
}

function startCalibration() {
  const page = activePage();
  if (!page) {
    showToast("Open a PDF first.", true);
    return;
  }
  if (elements["calibration-dialog"].open) elements["calibration-dialog"].close();
  state.pendingCalibration = null;
  state.calibration = { active: true, pageIndex: page.index, start: null, current: null };
  elements["calibration-guide"].hidden = false;
  elements["calibration-guide-title"].textContent = "Click the first endpoint";
  elements["calibration-guide-detail"].textContent = "Choose one end of a printed measurement line on this page.";
  page.card.scrollIntoView({ behavior: "smooth", block: "center" });
  updateCalibrationCursors();
  updateUi();
}

function cancelCalibration() {
  const pageIndex = state.calibration.pageIndex ?? state.pendingCalibration?.pageIndex;
  state.calibration = { active: false, pageIndex: null, start: null, current: null };
  state.pendingCalibration = null;
  elements["calibration-guide"].hidden = true;
  if (elements["calibration-dialog"].open) elements["calibration-dialog"].close();
  updateCalibrationCursors();
  if (pageIndex != null) renderOverlay(pageIndex);
  updateUi();
}

function updateCalibrationCursors() {
  for (const page of state.pages) {
    page.svg?.classList.toggle(
      "is-calibrating",
      state.calibration.active && state.calibration.pageIndex === page.index,
    );
  }
}

function applyCalibration(event) {
  event.preventDefault();
  const pending = state.pendingCalibration;
  if (!pending) return;
  try {
    const length = Number(elements["calibration-length"].value);
    const unit = elements["calibration-unit"].value;
    const pointsPerInch = scaleFromCalibration(pending.start, pending.end, length, unit);
    const unitName = { ft: "ft", in: "in", cm: "cm", m: "m" }[unit];
    const label = `${length} ${unitName}`;
    const targetIndexes = elements["calibration-all-pages"].checked
      ? state.pages.map((page) => page.index)
      : [pending.pageIndex];
    for (const index of targetIndexes) {
      const page = state.pages[index];
      page.pointsPerInch = pointsPerInch;
      page.scaleLabel = index === pending.pageIndex ? label : `${label} (copied)`;
      page.calibration = index === pending.pageIndex ? { start: pending.start, end: pending.end, label } : null;
      renderOverlay(index);
    }
    state.pendingCalibration = null;
    elements["calibration-dialog"].close();
    markDirty();
    updateUi();
    const calibratedPage = state.pages[pending.pageIndex];
    showToast(elements["calibration-all-pages"].checked ? "Scale set for every page." : `Scale set for PDF page ${calibratedPage.pdfPageNumber}.`);
  } catch (error) {
    showToast(safeErrorMessage(error, "Enter a valid measurement."), true);
  }
}

function reopenCalibration() {
  const index = state.pendingCalibration?.pageIndex ?? state.activePage;
  state.pendingCalibration = null;
  elements["calibration-dialog"].close();
  state.activePage = index;
  startCalibration();
}

function openFurnitureDialog(type, preset = null) {
  const page = activePage();
  if (!page) {
    showToast("Open a PDF first.", true);
    return;
  }
  if (!page.pointsPerInch) {
    showToast("Set the page scale first so the furniture has the right size.");
    startCalibration();
    return;
  }
  const presets = {
    sofa: { name: "Sofa", width: 84, depth: 36 },
    queen: { name: "Queen bed", width: 60, depth: 80 },
    table: { name: "Dining table", width: 72, depth: 40 },
  };
  const values = presets[preset] || (type === "l"
    ? { name: "L-shaped couch", width: 108, depth: 84, armDepth: 36, returnWidth: 36 }
    : { name: "Furniture", width: 48, depth: 30 });
  state.newShapeType = type;
  elements["furniture-dialog-title"].textContent = type === "l" ? "Add an L-shape" : "Add a rectangle";
  elements["new-l-shape-fields"].hidden = type !== "l";
  elements["furniture-shape-help"].textContent = type === "l"
    ? "Overall width and depth set the outside size. Arm depth and return width set the two thicknesses of the L."
    : "A regular rectangle, good for beds, tables, rugs, and sofas.";
  elements["furniture-name"].value = values.name;
  elements["furniture-width"].value = values.width;
  elements["furniture-depth"].value = values.depth;
  elements["furniture-arm-depth"].value = values.armDepth || 18;
  elements["furniture-return-width"].value = values.returnWidth || 18;
  elements["furniture-dialog"].showModal();
  window.setTimeout(() => elements["furniture-name"].select(), 20);
}

function addFurniture(event) {
  event.preventDefault();
  const page = activePage();
  if (!page?.pointsPerInch) return;
  try {
    const item = validateFurniture({
      id: uniqueId(),
      type: state.newShapeType,
      name: elements["furniture-name"].value.trim(),
      pageIndex: page.index,
      x: page.width / 2,
      y: page.height / 2,
      width: elements["furniture-width"].value,
      depth: elements["furniture-depth"].value,
      armDepth: elements["furniture-arm-depth"].value,
      returnWidth: elements["furniture-return-width"].value,
      rotation: 0,
      color: COLORS[state.items.length % COLORS.length],
      locked: false,
    });
    state.items.push(item);
    state.selectedItemId = item.id;
    elements["furniture-dialog"].close();
    markDirty();
    renderOverlay(page.index);
    updateUi();
    showToast(`${item.name} added. Drag it into place.`);
  } catch (error) {
    showToast(safeErrorMessage(error, "Check the furniture dimensions."), true);
  }
}

function selectItem(id) {
  const oldItem = selectedItem();
  state.selectedItemId = id;
  const item = selectedItem();
  if (oldItem) renderOverlay(oldItem.pageIndex);
  if (item && (!oldItem || oldItem.pageIndex !== item.pageIndex)) renderOverlay(item.pageIndex);
  updateInspector();
}

function updateInspector() {
  const item = selectedItem();
  elements["inspector-empty"].hidden = Boolean(item);
  elements["inspector-form"].hidden = !item;
  document.getElementById("inspector").classList.toggle("is-open", Boolean(item));
  if (!item) return;
  elements["inspector-title"].textContent = item.name;
  elements["edit-name"].value = item.name;
  elements["edit-width"].value = item.width;
  elements["edit-depth"].value = item.depth;
  elements["edit-arm-depth"].value = item.armDepth;
  elements["edit-return-width"].value = item.returnWidth;
  elements["edit-rotation"].value = item.rotation;
  elements["edit-locked"].checked = item.locked;
  elements["l-shape-fields"].hidden = item.type !== "l";
  for (const swatch of document.querySelectorAll(".color-swatch")) {
    const selected = swatch.dataset.color === item.color;
    swatch.classList.toggle("is-selected", selected);
    swatch.setAttribute("aria-pressed", selected ? "true" : "false");
  }
}

function updateSelectedFromInspector() {
  const item = selectedItem();
  if (!item) return;
  const original = { ...item };
  try {
    const changed = validateFurniture({
      ...item,
      name: elements["edit-name"].value.trim(),
      width: elements["edit-width"].value,
      depth: elements["edit-depth"].value,
      armDepth: elements["edit-arm-depth"].value,
      returnWidth: elements["edit-return-width"].value,
    });
    Object.assign(item, changed, {
      rotation: normalizeAngle(elements["edit-rotation"].value),
      locked: elements["edit-locked"].checked,
    });
    markDirty();
    renderOverlay(item.pageIndex);
    updateInspector();
  } catch (error) {
    Object.assign(item, original);
    showToast(safeErrorMessage(error, "Check the dimensions."), true);
    updateInspector();
  }
}

function rotateSelected(amount) {
  const item = selectedItem();
  if (!item) return;
  item.rotation = normalizeAngle(item.rotation + amount);
  markDirty();
  renderOverlay(item.pageIndex);
  updateInspector();
}

function setSelectedColor(color) {
  const item = selectedItem();
  if (!item || !COLORS.includes(color)) return;
  item.color = color;
  markDirty();
  renderOverlay(item.pageIndex);
  updateInspector();
}

function duplicateSelected() {
  const item = selectedItem();
  if (!item) return;
  const page = state.pages[item.pageIndex];
  const duplicate = {
    ...item,
    id: uniqueId(),
    name: `${item.name} copy`,
    x: clamp(item.x + 12, 0, page.width),
    y: clamp(item.y + 12, 0, page.height),
    locked: false,
  };
  state.items.push(duplicate);
  state.selectedItemId = duplicate.id;
  markDirty();
  renderOverlay(item.pageIndex);
  updateInspector();
}

function deleteSelected() {
  const item = selectedItem();
  if (!item) return;
  state.items = state.items.filter((entry) => entry.id !== item.id);
  state.selectedItemId = null;
  markDirty();
  renderOverlay(item.pageIndex);
  updateInspector();
  showToast(`${item.name} removed.`);
}

function updateUi() {
  const hasPdf = Boolean(state.pdf);
  const page = activePage();
  const calibrated = Boolean(page?.pointsPerInch);
  const visiblePageCount = state.pages.length;
  const originalPageCount = state.pdf?.numPages || 0;
  const pageCountText = visiblePageCount === originalPageCount
    ? `${visiblePageCount} page${visiblePageCount === 1 ? "" : "s"}`
    : `${visiblePageCount} of ${originalPageCount} pages`;
  elements["drop-zone"].hidden = hasPdf;
  elements["page-gallery"].hidden = !hasPdf;
  elements["document-name"].textContent = state.fileName || "No floor plan open";
  elements["page-count"].textContent = hasPdf ? pageCountText : "";
  elements["pdf-summary"].textContent = hasPdf
    ? `${pageCountText} ready`
    : "No PDF open";
  elements["calibrate"].disabled = !hasPdf;
  elements["calibrate"].textContent = state.calibration.active
    ? "Cancel calibration"
    : page
      ? `Calibrate PDF page ${page.pdfPageNumber}`
      : "Calibrate this page";
  elements["calibrate"].setAttribute("aria-pressed", state.calibration.active ? "true" : "false");
  elements["active-page-status"].textContent = page ? `PDF page ${page.pdfPageNumber} selected.` : "";
  elements["scale-summary"].textContent = !hasPdf
    ? "Open a PDF first"
    : calibrated
      ? `PDF page ${page.pdfPageNumber} ready · ${page.scaleLabel || "scale set"}`
      : `PDF page ${page.pdfPageNumber} needs a scale`;
  for (const id of ["add-rectangle", "add-l-shape"]) elements[id].disabled = !hasPdf;
  for (const preset of document.querySelectorAll(".preset")) preset.disabled = !hasPdf;
  elements["save-project"].disabled = !hasPdf;
  elements["export-pdf"].disabled = !hasPdf;
  for (const id of ["zoom-out", "zoom-in", "zoom-fit", "zoom-slider"]) elements[id].disabled = !hasPdf;

  elements["step-open"].classList.toggle("is-complete", hasPdf);
  elements["step-open"].classList.toggle("is-current", !hasPdf);
  elements["step-calibrate"].classList.toggle("is-complete", calibrated);
  elements["step-calibrate"].classList.toggle("is-current", hasPdf && !calibrated);
  elements["step-furniture"].classList.toggle("is-current", calibrated);

  for (const entry of state.pages) {
    entry.card?.classList.toggle("is-active", entry.index === state.activePage);
    entry.card?.setAttribute("aria-current", entry.index === state.activePage ? "page" : "false");
    const status = entry.card?.querySelector('[data-role="scale-status"]');
    if (status) {
      status.textContent = entry.pointsPerInch ? "Scale set" : "Scale needed";
      status.classList.toggle("is-set", Boolean(entry.pointsPerInch));
    }
  }
  updateInspector();
  updateDocumentTitle();
}

function projectPayload() {
  return {
    format: PROJECT_FORMAT,
    version: PROJECT_VERSION,
    projectName: state.projectName,
    pdfName: state.fileName,
    pdfBase64: bytesToBase64(state.pdfBytes),
    pages: state.pages.map((page) => ({
      pdfPageNumber: page.pdfPageNumber,
      pointsPerInch: page.pointsPerInch,
      scaleLabel: page.scaleLabel,
      calibration: page.calibration,
    })),
    items: state.items.map(({ id, type, name, pageIndex, x, y, width, depth, armDepth, returnWidth, rotation, color, locked }) => ({
      id,
      type,
      name,
      pageIndex,
      x,
      y,
      width,
      depth,
      armDepth,
      returnWidth,
      rotation,
      color,
      locked,
    })),
  };
}

async function saveProject() {
  if (!state.pdfBytes) return;
  try {
    const contents = JSON.stringify(projectPayload());
    const baseName = (state.fileName || "My floor plan").replace(/\.pdf$/i, "");
    if (electronApi) {
      const path = await electronApi.saveProject({ suggestedName: `${baseName}.floorplan`, contents });
      if (!path) return;
      state.projectName = path.split(/[\\/]/).pop();
    } else {
      downloadBlob(new Blob([contents], { type: "application/json" }), `${baseName}.floorplan`);
      state.projectName = `${baseName}.floorplan`;
    }
    markDirty(false);
    showToast("Editable project saved. Use Export PDF when you want a normal shareable document.");
  } catch (error) {
    showToast(`Could not save the project: ${safeErrorMessage(error, "Unknown error")}`, true);
  }
}

async function chooseProject() {
  try {
    if (electronApi) {
      if (!(await confirmDiscardIfNeeded())) return;
      const contents = await electronApi.openProject();
      if (!contents) return;
      await loadProject(contents);
    } else {
      elements["project-file-input"].click();
    }
  } catch (error) {
    showToast(`Could not open that project: ${safeErrorMessage(error, "Unknown error")}`, true);
  }
}

async function confirmDiscardIfNeeded() {
  if (!state.dirty) return true;
  if (electronApi) return electronApi.confirmDiscard();
  return window.confirm("Open another file and discard your unsaved changes?");
}

async function loadProject(contents) {
  const project = parseProject(contents);
  await loadPdf(base64ToBytes(project.pdfBase64), project.pdfName || "floor-plan.pdf", project);
  state.projectName = project.projectName || `${(project.pdfName || "floor-plan").replace(/\.pdf$/i, "")}.floorplan`;
  markDirty(false);
  showToast("Project opened.");
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function createPagePngDataUrl(page) {
  await ensurePageRendered(page.index);
  const output = document.createElement("canvas");
  output.width = page.canvas.width;
  output.height = page.canvas.height;
  const context = output.getContext("2d");
  context.drawImage(page.canvas, 0, 0);

  const overlay = page.svg.cloneNode(true);
  overlay.querySelectorAll(".is-selected").forEach((node) => node.classList.remove("is-selected"));
  overlay.querySelectorAll(".is-temporary").forEach((node) => node.remove());
  overlay.setAttribute("xmlns", SVG_NS);
  overlay.setAttribute("width", String(output.width));
  overlay.setAttribute("height", String(output.height));
  const embeddedStyles = createSvgElement("style");
  embeddedStyles.textContent = EXPORT_SVG_STYLES;
  overlay.prepend(embeddedStyles);
  const svgBlob = new Blob([new XMLSerializer().serializeToString(overlay)], { type: "image/svg+xml" });
  const svgUrl = URL.createObjectURL(svgBlob);
  const image = new Image();
  try {
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = reject;
      image.src = svgUrl;
    });
    context.drawImage(image, 0, 0, output.width, output.height);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
  return output.toDataURL("image/png");
}

async function createExportPdfBytes() {
  const title = (state.fileName || "Floor plan").replace(/\.pdf$/i, "");
  return buildFlattenedPdf(
    state.pages.map((page) => ({
      width: page.width,
      height: page.height,
      getPng: () => createPagePngDataUrl(page),
    })),
    {
      title: `${title} - furnished`,
      onProgress: (current, total) => {
        elements["export-pdf"].textContent = `Exporting ${current}/${total}…`;
      },
    },
  );
}

async function exportPdf() {
  if (!state.pages.length) return;
  const button = elements["export-pdf"];
  button.disabled = true;
  button.textContent = "Preparing PDF…";
  try {
    const pdfBytes = await createExportPdfBytes();
    const baseName = (state.fileName || "floor-plan").replace(/\.pdf$/i, "");
    const suggestedName = `${baseName}-furnished.pdf`;
    if (electronApi) {
      const path = await electronApi.exportPdf({ suggestedName, data: pdfBytes });
      if (!path) return;
    } else {
      downloadBlob(new Blob([pdfBytes], { type: "application/pdf" }), suggestedName);
    }
    showToast(`Exported ${state.pages.length} page${state.pages.length === 1 ? "" : "s"} with furniture as a PDF.`);
  } catch (error) {
    showToast(`Could not export the PDF: ${safeErrorMessage(error, "Unknown error")}`, true);
  } finally {
    button.textContent = "Export PDF";
    updateUi();
  }
}

function setZoom(nextZoom, anchor = null) {
  const gallery = elements["page-gallery"];
  const galleryRect = gallery.getBoundingClientRect();
  let referencePage = Number.isInteger(anchor?.pageIndex) ? state.pages[anchor.pageIndex] : null;
  if (!referencePage?.card) {
    const centerY = galleryRect.top + galleryRect.height / 2;
    referencePage = state.pages
      .filter((page) => page.card)
      .sort((first, second) => {
        const firstRect = first.card.getBoundingClientRect();
        const secondRect = second.card.getBoundingClientRect();
        return Math.abs((firstRect.top + firstRect.bottom) / 2 - centerY)
          - Math.abs((secondRect.top + secondRect.bottom) / 2 - centerY);
      })[0] || activePage();
  }
  const before = referencePage?.card?.getBoundingClientRect();
  const focusX = before
    ? clamp(anchor?.clientX ?? galleryRect.left + galleryRect.width / 2, before.left, before.right)
    : 0;
  const focusY = before
    ? clamp(anchor?.clientY ?? galleryRect.top + galleryRect.height / 2, before.top, before.bottom)
    : 0;
  const ratioX = before?.width ? (focusX - before.left) / before.width : 0.5;
  const ratioY = before?.height ? (focusY - before.top) / before.height : 0.5;

  state.zoom = clamp(Math.round(nextZoom * 20) / 20, 0.4, 2.5);
  updateSurfaceSizes();

  const after = referencePage?.card?.getBoundingClientRect();
  if (before && after) {
    gallery.scrollLeft += after.left + after.width * ratioX - focusX;
    gallery.scrollTop += after.top + after.height * ratioY - focusY;
  }
}

function fitActivePage(allowUpscale = true) {
  if (!activePage()) return;
  setZoom(1);
}

function handleKeyboard(event) {
  const target = event.target;
  const isTyping = target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
  const modifier = event.ctrlKey || event.metaKey;
  if (modifier && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveProject();
    return;
  }
  if (modifier && event.key.toLowerCase() === "o") {
    event.preventDefault();
    choosePdf();
    return;
  }
  if (modifier && event.key.toLowerCase() === "d" && selectedItem()) {
    event.preventDefault();
    duplicateSelected();
    return;
  }
  if (modifier && (event.key === "+" || event.key === "=")) {
    event.preventDefault();
    setZoom(state.zoom + 0.1);
    return;
  }
  if (modifier && event.key === "-") {
    event.preventDefault();
    setZoom(state.zoom - 0.1);
    return;
  }
  if (modifier && event.key === "0") {
    event.preventDefault();
    fitActivePage(true);
    return;
  }
  if (event.key === "Escape" && state.calibration.active) {
    cancelCalibration();
    return;
  }
  if (isTyping) return;
  if ((event.key === "Delete" || event.key === "Backspace") && selectedItem()) {
    event.preventDefault();
    deleteSelected();
    return;
  }
  const direction = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
  const item = selectedItem();
  if (direction && item && !item.locked) {
    event.preventDefault();
    const page = state.pages[item.pageIndex];
    const amount = page.pointsPerInch * (event.shiftKey ? 6 : 1);
    item.x = clamp(item.x + direction[0] * amount, 0, page.width);
    item.y = clamp(item.y + direction[1] * amount, 0, page.height);
    markDirty();
    renderOverlay(item.pageIndex);
  }
}

function bindEvents() {
  for (const id of ["open-pdf", "open-pdf-side", "empty-open"]) elements[id].addEventListener("click", choosePdf);
  elements["open-project"].addEventListener("click", chooseProject);
  elements["save-project"].addEventListener("click", saveProject);
  elements["export-pdf"].addEventListener("click", exportPdf);
  elements["pdf-file-input"].addEventListener("change", (event) => {
    readPdfFile(event.target.files[0]);
    event.target.value = "";
  });
  elements["project-file-input"].addEventListener("change", async (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    try {
      if (!(await confirmDiscardIfNeeded())) return;
      await loadProject(await file.text());
    } catch (error) {
      showToast(`Could not open that project: ${safeErrorMessage(error, "Invalid project file")}`, true);
    }
  });

  elements.calibrate.addEventListener("click", () => {
    if (state.calibration.active) cancelCalibration();
    else startCalibration();
  });
  elements["cancel-calibration"].addEventListener("click", cancelCalibration);
  elements["calibration-form"].addEventListener("submit", applyCalibration);
  elements["calibration-back"].addEventListener("click", reopenCalibration);
  elements["calibration-cancel"].addEventListener("click", cancelCalibration);
  elements["calibration-dialog"].addEventListener("cancel", (event) => {
    event.preventDefault();
    cancelCalibration();
  });

  elements["add-rectangle"].addEventListener("click", () => openFurnitureDialog("rect"));
  elements["add-l-shape"].addEventListener("click", () => openFurnitureDialog("l"));
  for (const preset of document.querySelectorAll(".preset")) {
    preset.addEventListener("click", () => openFurnitureDialog("rect", preset.dataset.preset));
  }
  elements["furniture-form"].addEventListener("submit", addFurniture);
  elements["furniture-cancel"].addEventListener("click", () => elements["furniture-dialog"].close());

  elements["close-inspector"].addEventListener("click", () => selectItem(null));
  for (const id of ["edit-name", "edit-width", "edit-depth", "edit-arm-depth", "edit-return-width", "edit-rotation", "edit-locked"]) {
    elements[id].addEventListener("change", updateSelectedFromInspector);
  }
  elements["rotate-left"].addEventListener("click", () => rotateSelected(-15));
  elements["rotate-right"].addEventListener("click", () => rotateSelected(15));
  elements.duplicate.addEventListener("click", duplicateSelected);
  elements.delete.addEventListener("click", deleteSelected);
  for (const swatch of document.querySelectorAll(".color-swatch")) {
    swatch.addEventListener("click", () => setSelectedColor(swatch.dataset.color));
  }

  elements["zoom-out"].addEventListener("click", () => setZoom(state.zoom - 0.1));
  elements["zoom-in"].addEventListener("click", () => setZoom(state.zoom + 0.1));
  elements["zoom-fit"].addEventListener("click", () => fitActivePage(true));
  elements["zoom-slider"].addEventListener("input", (event) => setZoom(Number(event.target.value) / 100));
  elements["page-layout"].addEventListener("change", (event) => {
    state.layout = event.target.value;
    elements["page-gallery"].classList.toggle("spread", state.layout === "spread");
    fitActivePage(false);
  });
  elements["page-gallery"].addEventListener("wheel", (event) => {
    if (!event.ctrlKey) return;
    event.preventDefault();
    const card = event.target.closest?.(".page-card");
    setZoom(state.zoom + (event.deltaY < 0 ? 0.1 : -0.1), {
      clientX: event.clientX,
      clientY: event.clientY,
      pageIndex: card ? Number(card.dataset.pageIndex) : state.activePage,
    });
  }, { passive: false });

  const dropZone = elements["drop-zone"];
  for (const type of ["dragenter", "dragover"]) {
    document.addEventListener(type, (event) => {
      event.preventDefault();
      dropZone.classList.add("is-dragover");
    });
  }
  for (const type of ["dragleave", "drop"]) {
    document.addEventListener(type, (event) => {
      event.preventDefault();
      dropZone.classList.remove("is-dragover");
    });
  }
  document.addEventListener("drop", (event) => readPdfFile(event.dataTransfer?.files?.[0]));
  document.addEventListener("keydown", handleKeyboard);
  window.addEventListener("resize", updateSurfaceSizes);
  window.addEventListener("beforeunload", (event) => {
    if (electronApi || !state.dirty) return;
    event.preventDefault();
    event.returnValue = "Unsaved changes";
  });
}

bindEvents();
updateUi();

// A small, read-only test surface used by the local browser smoke test.
window.__floorPlannerTest = {
  getState: () => ({
    pageCount: state.pages.length,
    activePage: state.activePage,
    calibratedPages: state.pages.filter((page) => page.pointsPerInch).length,
    itemCount: state.items.length,
    layout: state.layout,
    zoom: state.zoom,
    pdfPageNumbers: state.pages.map((page) => page.pdfPageNumber),
  }),
  loadPdfBytes: (bytes, name = "test.pdf") => loadPdf(new Uint8Array(bytes), name),
  createExportPdfBytes,
};
