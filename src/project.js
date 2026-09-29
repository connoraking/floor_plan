export const PROJECT_FORMAT = "easy-floor-planner";
export const PROJECT_VERSION = 2;

export function bytesToBase64(bytes) {
  if (!(bytes instanceof Uint8Array)) throw new Error("PDF data is missing.");
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

export function base64ToBytes(value) {
  if (typeof value !== "string" || !value) throw new Error("Project PDF data is missing.");
  let binary;
  try {
    binary = atob(value);
  } catch {
    throw new Error("Project PDF data is damaged.");
  }
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

export function parseProject(contents) {
  let project;
  try {
    project = JSON.parse(contents);
  } catch {
    throw new Error("This project file is not valid JSON.");
  }
  if (project?.format !== PROJECT_FORMAT || project?.version !== PROJECT_VERSION) {
    throw new Error("This is not a Floor Planner 2 project file.");
  }
  if (!Array.isArray(project.pages) || !Array.isArray(project.items) || !project.pdfBase64) {
    throw new Error("This Floor Planner project is incomplete.");
  }
  return project;
}
