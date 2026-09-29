const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const fs = require("node:fs/promises");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const isDevelopment = !app.isPackaged && Boolean(process.env.VITE_DEV_SERVER_URL);
const isSmokeTest = !app.isPackaged && Boolean(process.env.FLOOR_PLANNER_SMOKE_TEST);
const dirtyRenderers = new Set();

if (isSmokeTest && process.platform === "linux") {
  app.commandLine.appendSwitch("disable-gpu");
  app.commandLine.appendSwitch("disable-dev-shm-usage");
  app.commandLine.appendSwitch("no-sandbox");
}

async function runSmokeTest(window) {
  try {
    console.log("FLOOR_PLANNER_SMOKE_STAGE renderer-loaded");
    const fixturePath = path.resolve(process.env.FLOOR_PLANNER_SMOKE_TEST);
    const screenshotPath = path.resolve(
      process.env.FLOOR_PLANNER_SMOKE_SCREENSHOT || path.join(process.cwd(), "tmp", "electron-smoke.png"),
    );
    const encodedPdf = (await fs.readFile(fixturePath)).toString("base64");
    const result = await window.webContents.executeJavaScript(`
      (async () => {
        const bytes = Uint8Array.from(atob(${JSON.stringify(encodedPdf)}), (character) => character.charCodeAt(0));
        await window.__floorPlannerTest.loadPdfBytes(bytes, "five-page-floor-plan.pdf");

        const continuousGallery = document.getElementById("page-gallery");
        const continuousCards = [...document.querySelectorAll(".page-card")];
        const firstSurfaceBounds = continuousCards[0].querySelector(".pdf-surface").getBoundingClientRect();
        const firstCardBounds = continuousCards[0].getBoundingClientRect();
        const secondCardBounds = continuousCards[1].getBoundingClientRect();
        const continuousPageIsFullHeight = firstSurfaceBounds.height > firstSurfaceBounds.width;
        const continuousRowsDoNotOverlap = secondCardBounds.top > firstCardBounds.bottom + 15;
        const continuousPageFillsWidth = firstSurfaceBounds.width >= continuousGallery.clientWidth - 80;

        const layout = document.getElementById("page-layout");
        layout.value = "spread";
        layout.dispatchEvent(new Event("change", { bubbles: true }));

        window.confirm = () => true;
        document.querySelectorAll(".page-remove")[2].click();

        const zoomSlider = document.getElementById("zoom-slider");
        zoomSlider.value = "140";
        zoomSlider.dispatchEvent(new Event("input", { bubbles: true }));
        const zoomAfterSlider = window.__floorPlannerTest.getState().zoom;
        document.getElementById("zoom-fit").click();

        document.getElementById("calibrate").click();
        const svg = document.querySelector('.page-overlay[data-page-index="0"]');
        const bounds = svg.getBoundingClientRect();
        const clickAt = (fractionX, fractionY, pointerId) => svg.dispatchEvent(new PointerEvent("pointerdown", {
          bubbles: true,
          clientX: bounds.left + bounds.width * fractionX,
          clientY: bounds.top + bounds.height * fractionY,
          pointerId,
          button: 0,
        }));
        clickAt(0.22, 0.88, 11);
        clickAt(0.78, 0.88, 12);
        document.getElementById("calibration-length").value = "20";
        document.getElementById("calibration-unit").value = "ft";
        document.getElementById("calibration-all-pages").checked = true;
        document.getElementById("calibration-form").requestSubmit();

        document.getElementById("add-rectangle").click();
        document.getElementById("furniture-name").value = "Test sofa";
        document.getElementById("furniture-width").value = "84";
        document.getElementById("furniture-depth").value = "36";
        document.getElementById("furniture-form").requestSubmit();

        const resizeHandlesBefore = document.querySelectorAll(".resize-handle").length;
        const widthHandle = document.querySelector('.resize-handle[data-resize-axis="width"]');
        const widthHandleBounds = widthHandle.getBoundingClientRect();
        const resizeStartX = (widthHandleBounds.left + widthHandleBounds.right) / 2;
        const resizeStartY = (widthHandleBounds.top + widthHandleBounds.bottom) / 2;
        widthHandle.dispatchEvent(new PointerEvent("pointerdown", {
          bubbles: true,
          clientX: resizeStartX,
          clientY: resizeStartY,
          pointerId: 21,
          button: 0,
        }));
        svg.dispatchEvent(new PointerEvent("pointermove", {
          bubbles: true,
          clientX: resizeStartX + 40,
          clientY: resizeStartY,
          pointerId: 21,
          button: 0,
        }));
        svg.dispatchEvent(new PointerEvent("pointerup", {
          bubbles: true,
          clientX: resizeStartX + 40,
          clientY: resizeStartY,
          pointerId: 21,
          button: 0,
        }));
        const resizedFurnitureWidth = window.__floorPlannerTest.getState().items[0].width;

        zoomSlider.value = "200";
        zoomSlider.dispatchEvent(new Event("input", { bubbles: true }));
        const calibrationPointScreenSize = document.querySelector(".calibration-point").getBoundingClientRect().width;
        document.getElementById("zoom-fit").click();

        const mainLayoutColumns = getComputedStyle(document.querySelector(".main-layout")).gridTemplateColumns.split(" ").length;
        const inspectorPosition = getComputedStyle(document.getElementById("inspector")).position;
        const galleryBounds = continuousGallery.getBoundingClientRect();
        const inspectorBounds = document.getElementById("inspector").getBoundingClientRect();
        const galleryStaysLeftOfInspector = galleryBounds.right <= inspectorBounds.left + 1;
        const scrollbarGutter = getComputedStyle(continuousGallery).scrollbarGutter;

        const exportedPdf = await window.__floorPlannerTest.createExportPdfBytes();
        const state = window.__floorPlannerTest.getState();
        const gallery = document.getElementById("page-gallery");
        return {
          ...state,
          continuousPageIsFullHeight,
          continuousRowsDoNotOverlap,
          continuousPageFillsWidth,
          exportedPdfPrefix: String.fromCharCode(...exportedPdf.slice(0, 5)),
          exportedPdfSize: exportedPdf.length,
          resizeHandlesBefore,
          resizedFurnitureWidth,
          calibrationPointScreenSize,
          mainLayoutColumns,
          inspectorPosition,
          galleryStaysLeftOfInspector,
          scrollbarGutter,
          zoomAfterSlider,
          visiblePageCards: [...document.querySelectorAll(".page-card")].filter((node) => !node.hidden).length,
          openButtonColor: getComputedStyle(document.getElementById("open-pdf")).backgroundColor,
          calibrateButtonColor: getComputedStyle(document.getElementById("calibrate")).backgroundColor,
          calibrateDialogClosed: !document.getElementById("calibration-dialog").open,
          furnitureDialogClosed: !document.getElementById("furniture-dialog").open,
          spreadFits: gallery.scrollWidth <= gallery.clientWidth + 2,
        };
      })()
    `, true);
    console.log("FLOOR_PLANNER_SMOKE_STAGE interactions-complete");

    const failures = [];
    if (result.pageCount !== 4 || result.visiblePageCards !== 4) failures.push("five-page PDF load or page removal failed");
    if (!result.continuousPageIsFullHeight || !result.continuousRowsDoNotOverlap || !result.continuousPageFillsWidth) {
      failures.push("continuous pages were cropped instead of filling the scrollable width");
    }
    if (result.pdfPageNumbers.join(",") !== "1,2,4,5") failures.push("the wrong PDF page was removed");
    if (result.calibratedPages !== 4) failures.push("calibration was not applied to all remaining pages");
    if (result.itemCount !== 1) failures.push("furniture could not be added");
    if (result.resizeHandlesBefore !== 3 || result.resizedFurnitureWidth <= 84) failures.push("direct furniture resize handles did not work");
    if (result.calibrationPointScreenSize > 12) failures.push("calibration points grew too large when zoomed");
    if (result.mainLayoutColumns !== 3 || result.inspectorPosition === "absolute" || !result.galleryStaysLeftOfInspector) {
      failures.push("the furniture inspector overlays the PDF workspace");
    }
    if (!result.scrollbarGutter.includes("stable")) failures.push("the PDF scrollbar does not reserve its own gutter");
    if (result.exportedPdfPrefix !== "%PDF-" || result.exportedPdfSize < 1000) failures.push("furnished PDF export failed");
    if (result.layout !== "spread") failures.push("two-page layout did not activate");
    if (result.zoomAfterSlider !== 1.4) failures.push("zoom slider did not set an exact zoom level");
    if (!result.spreadFits) failures.push("two-page layout requires horizontal scrolling");
    if (!result.calibrateDialogClosed || !result.furnitureDialogClosed) failures.push("a workflow dialog did not close");
    if (result.openButtonColor === "rgba(0, 0, 0, 0)" || result.calibrateButtonColor === "rgba(0, 0, 0, 0)") {
      failures.push("primary action colors are not visible");
    }

    await fs.mkdir(path.dirname(screenshotPath), { recursive: true });
    const image = await window.webContents.capturePage();
    console.log("FLOOR_PLANNER_SMOKE_STAGE screenshot-captured");
    await fs.writeFile(screenshotPath, image.toPNG());
    console.log(`FLOOR_PLANNER_SMOKE_RESULT ${JSON.stringify({ ...result, screenshotPath, failures })}`);
    app.exit(failures.length ? 1 : 0);
  } catch (error) {
    console.error("FLOOR_PLANNER_SMOKE_ERROR", error);
    app.exit(1);
  }
}

function createWindow() {
  const window = new BrowserWindow({
    width: isSmokeTest ? 1100 : 1500,
    height: 940,
    minWidth: 1050,
    minHeight: 700,
    backgroundColor: "#101828",
    title: "Floor Planner",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: !isSmokeTest,
    },
  });
  const rendererId = window.webContents.id;

  if (!isSmokeTest) window.once("ready-to-show", () => window.show());
  if (isSmokeTest) {
    window.webContents.on("console-message", (_event, details) => {
      console.log(`FLOOR_PLANNER_RENDERER ${details.level} ${details.message}`);
    });
    window.webContents.on("did-fail-load", (_event, code, description) => {
      console.error(`FLOOR_PLANNER_LOAD_FAILED ${code} ${description}`);
    });
    window.webContents.once("did-finish-load", () => runSmokeTest(window));
  }
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) shell.openExternal(url);
    return { action: "deny" };
  });
  window.webContents.on("will-navigate", (event, url) => {
    if (!isTrustedRendererUrl(url)) event.preventDefault();
  });
  window.on("close", (event) => {
    if (!dirtyRenderers.has(rendererId)) return;
    const choice = dialog.showMessageBoxSync(window, {
      type: "warning",
      title: "Unsaved floor plan",
      message: "You have changes that have not been saved.",
      detail: "Keep working so you can save, or close and discard those changes.",
      buttons: ["Keep working", "Discard changes"],
      defaultId: 0,
      cancelId: 0,
      noLink: true,
    });
    if (choice === 0) event.preventDefault();
    else dirtyRenderers.delete(rendererId);
  });
  window.on("closed", () => dirtyRenderers.delete(rendererId));

  if (isDevelopment) {
    window.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    window.loadFile(path.join(__dirname, "..", "dist-web", "index.html"));
  }
}

function isTrustedRendererUrl(url) {
  if (isDevelopment) {
    try {
      return new URL(url).origin === new URL(process.env.VITE_DEV_SERVER_URL).origin;
    } catch {
      return false;
    }
  }
  const expected = pathToFileURL(path.join(__dirname, "..", "dist-web", "index.html")).href;
  return url === expected || url.startsWith(`${expected}#`) || url.startsWith(`${expected}?`);
}

function requireTrustedSender(event) {
  const url = event.senderFrame?.url || event.sender.getURL();
  if (!isTrustedRendererUrl(url)) throw new Error("Blocked IPC request from an untrusted page.");
}

function arrayBufferFromBuffer(buffer) {
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
}

ipcMain.handle("file:open-pdf", async (event) => {
  requireTrustedSender(event);
  const result = await dialog.showOpenDialog({
    title: "Choose a floor plan PDF",
    properties: ["openFile"],
    filters: [{ name: "PDF floor plans", extensions: ["pdf"] }],
  });
  if (result.canceled || !result.filePaths[0]) return null;
  const filePath = result.filePaths[0];
  const data = await fs.readFile(filePath);
  return { name: path.basename(filePath), data: arrayBufferFromBuffer(data) };
});

ipcMain.handle("file:open-project", async (event) => {
  requireTrustedSender(event);
  const result = await dialog.showOpenDialog({
    title: "Open a Floor Planner project",
    properties: ["openFile"],
    filters: [{ name: "Floor Planner project", extensions: ["floorplan"] }],
  });
  if (result.canceled || !result.filePaths[0]) return null;
  return fs.readFile(result.filePaths[0], "utf8");
});

ipcMain.handle("file:save-project", async (event, { suggestedName, contents }) => {
  requireTrustedSender(event);
  if (typeof contents !== "string") throw new TypeError("Project contents must be text.");
  const result = await dialog.showSaveDialog({
    title: "Save Floor Planner project",
    defaultPath: suggestedName || "My floor plan.floorplan",
    filters: [{ name: "Floor Planner project", extensions: ["floorplan"] }],
  });
  if (result.canceled || !result.filePath) return null;
  await fs.writeFile(result.filePath, contents, "utf8");
  return result.filePath;
});

ipcMain.handle("file:export-pdf", async (event, { suggestedName, data }) => {
  requireTrustedSender(event);
  let pdfBuffer;
  if (data instanceof ArrayBuffer) pdfBuffer = Buffer.from(data);
  else if (ArrayBuffer.isView(data)) pdfBuffer = Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  else throw new TypeError("Export data must be PDF bytes.");
  if (pdfBuffer.subarray(0, 5).toString("ascii") !== "%PDF-") throw new TypeError("Export data is not a PDF.");
  const result = await dialog.showSaveDialog({
    title: "Export furnished floor plan",
    defaultPath: suggestedName || "furnished-floor-plan.pdf",
    filters: [{ name: "PDF document", extensions: ["pdf"] }],
  });
  if (result.canceled || !result.filePath) return null;
  await fs.writeFile(result.filePath, pdfBuffer);
  return result.filePath;
});

ipcMain.handle("app:confirm-discard", async (event) => {
  requireTrustedSender(event);
  const window = BrowserWindow.getFocusedWindow();
  const options = {
    type: "warning",
    title: "Unsaved floor plan",
    message: "Open another file and discard your unsaved changes?",
    buttons: ["Keep working", "Discard changes"],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  };
  const result = window
    ? await dialog.showMessageBox(window, options)
    : await dialog.showMessageBox(options);
  return result.response === 1;
});

ipcMain.on("app:set-dirty", (event, dirty) => {
  try {
    requireTrustedSender(event);
    if (dirty) dirtyRenderers.add(event.sender.id);
    else dirtyRenderers.delete(event.sender.id);
  } catch {
    // Ignore messages from unexpected frames.
  }
});

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
