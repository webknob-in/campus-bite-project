// Pagination: previous/next controls with a "Page X of Y" indicator (Requirement 27.5).
// Feed it the fields of a Paginated_Response:
//   <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
// It is rendered even when there is a single page so every list page shows the current page.
export default function Pagination({ page, pageSize, total, onPageChange }) {
  const currentPage = Number.isFinite(page) && page >= 1 ? Math.floor(page) : 1;
  const itemCount = Number.isFinite(total) && total > 0 ? total : 0;
  const totalPages = pageSize > 0 ? Math.max(1, Math.ceil(itemCount / pageSize)) : 1;

  const hasPrevious = currentPage > 1;
  const hasNext = currentPage < totalPages;

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={!hasPrevious}
        // If the page is past the last page (an empty page), step back to the last real page.
        onClick={() => onPageChange(Math.min(currentPage - 1, totalPages))}
      >
        Previous
      </button>
      <span className="pagination-status" aria-live="polite" aria-atomic="true">
        Page {currentPage} of {totalPages}
      </span>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={!hasNext}
        onClick={() => onPageChange(currentPage + 1)}
      >
        Next
      </button>
    </nav>
  );
}
