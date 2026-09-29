export function calculateSpreadFitFactor(galleryWidth, pageWidths, cssPdfScale = 1.12) {
  if (!pageWidths.length) return 1;
  const widestPage = Math.max(...pageWidths);
  // 60px gallery padding + 22px column gap + 12px from both page-card borders.
  const availableWidth = Math.max(240, galleryWidth - 94);
  const factor = availableWidth / (widestPage * cssPdfScale * 2);
  return Math.min(1, Math.max(0.2, factor));
}
