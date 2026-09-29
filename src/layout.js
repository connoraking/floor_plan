export function calculateSpreadFitFactor(galleryWidth, pageWidths, cssPdfScale = 1.12) {
  if (!pageWidths.length) return 1;
  const widestPage = Math.max(...pageWidths);
  // 60px gallery padding + 22px column gap + 12px from both page-card borders.
  const availableWidth = Math.max(240, galleryWidth - 94);
  const factor = availableWidth / (widestPage * cssPdfScale * 2);
  return Math.max(0.2, factor);
}

export function calculateContinuousFitFactor(galleryWidth, pageWidth, cssPdfScale = 1.12) {
  const availableWidth = Math.max(240, galleryWidth - 72);
  return availableWidth / (pageWidth * cssPdfScale);
}

export function calculateCappedRenderScale(width, height, desiredScale, maxPixels = 10_000_000) {
  const requestedPixels = width * height * desiredScale * desiredScale;
  if (requestedPixels <= maxPixels) return desiredScale;
  return desiredScale * Math.sqrt(maxPixels / requestedPixels);
}
