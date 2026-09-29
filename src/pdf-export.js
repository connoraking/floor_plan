import { PDFDocument } from "pdf-lib";

export async function buildFlattenedPdf(pageImages, options = {}) {
  if (!Array.isArray(pageImages) || !pageImages.length) {
    throw new Error("There are no pages to export.");
  }
  const pdf = await PDFDocument.create();
  pdf.setTitle(options.title || "Furnished floor plan");
  pdf.setCreator("Floor Planner");
  pdf.setProducer("Floor Planner");

  for (let index = 0; index < pageImages.length; index += 1) {
    const definition = pageImages[index];
    const width = Number(definition.width);
    const height = Number(definition.height);
    if (!(width > 0) || !(height > 0)) throw new Error("A PDF page has an invalid size.");
    const pngSource = typeof definition.getPng === "function"
      ? await definition.getPng()
      : definition.png;
    if (!pngSource) throw new Error("A PDF page image is missing.");

    const embeddedImage = await pdf.embedPng(pngSource);
    const outputPage = pdf.addPage([width, height]);
    outputPage.drawImage(embeddedImage, { x: 0, y: 0, width, height });
    options.onProgress?.(index + 1, pageImages.length);
  }

  return pdf.save({ useObjectStreams: true });
}
