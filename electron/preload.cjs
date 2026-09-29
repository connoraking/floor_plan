const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("floorPlannerApi", {
  openPdf: () => ipcRenderer.invoke("file:open-pdf"),
  openProject: () => ipcRenderer.invoke("file:open-project"),
  saveProject: (payload) => ipcRenderer.invoke("file:save-project", payload),
  exportPng: (payload) => ipcRenderer.invoke("file:export-png", payload),
  confirmDiscard: () => ipcRenderer.invoke("app:confirm-discard"),
  setDirty: (dirty) => ipcRenderer.send("app:set-dirty", Boolean(dirty)),
  platform: process.platform,
});
