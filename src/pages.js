export function pageRecordsForProject(pdfPageCount, savedPages = null) {
  if (!Number.isInteger(pdfPageCount) || pdfPageCount < 1) {
    throw new Error("The PDF does not contain any pages.");
  }

  const records = savedPages == null
    ? Array.from({ length: pdfPageCount }, (_, index) => ({ pdfPageNumber: index + 1, savedPage: null }))
    : savedPages.map((savedPage, index) => ({
      pdfPageNumber: savedPage?.pdfPageNumber ?? index + 1,
      savedPage,
    }));

  if (!records.length) throw new Error("This project does not contain any visible PDF pages.");

  const usedPageNumbers = new Set();
  for (const record of records) {
    const pageNumber = Number(record.pdfPageNumber);
    if (!Number.isInteger(pageNumber) || pageNumber < 1 || pageNumber > pdfPageCount) {
      throw new Error("This project refers to a PDF page that no longer exists.");
    }
    if (usedPageNumbers.has(pageNumber)) {
      throw new Error("This project contains the same PDF page more than once.");
    }
    record.pdfPageNumber = pageNumber;
    usedPageNumbers.add(pageNumber);
  }
  return records;
}

export function removePageAt(pages, items, pageIndex) {
  if (!Number.isInteger(pageIndex) || !pages[pageIndex]) throw new Error("That page could not be found.");
  if (pages.length <= 1) throw new Error("A floor plan must keep at least one page.");

  const remainingPages = pages
    .filter((_, index) => index !== pageIndex)
    .map((page, index) => ({
      ...page,
      index,
      card: null,
      surface: null,
      canvas: null,
      svg: null,
      renderPromise: null,
      rendered: false,
    }));
  const remainingItems = items
    .filter((item) => item.pageIndex !== pageIndex)
    .map((item) => ({
      ...item,
      pageIndex: item.pageIndex > pageIndex ? item.pageIndex - 1 : item.pageIndex,
    }));

  return { pages: remainingPages, items: remainingItems };
}
