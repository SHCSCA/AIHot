type PaginationBarProps = {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
};

export function PaginationBar({ page, totalPages, onPageChange, disabled = false }: PaginationBarProps) {
  if (totalPages <= 1) return null;
  const pages = visiblePages(page, totalPages);
  return (
    <nav className="pagination-bar" aria-label="分页">
      <button onClick={() => onPageChange(page - 1)} disabled={disabled || page <= 1}>
        上一页
      </button>
      {pages.map((item, index) =>
        item === "gap" ? (
          <span key={`gap-${index}`}>...</span>
        ) : (
          <button
            key={item}
            className={item === page ? "active" : ""}
            onClick={() => onPageChange(item)}
            disabled={disabled || item === page}
          >
            {item}
          </button>
        )
      )}
      <button onClick={() => onPageChange(page + 1)} disabled={disabled || page >= totalPages}>
        下一页
      </button>
    </nav>
  );
}

function visiblePages(page: number, totalPages: number): Array<number | "gap"> {
  if (totalPages <= 6) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const result: Array<number | "gap"> = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);
  if (start > 2) result.push("gap");
  for (let current = start; current <= end; current += 1) {
    result.push(current);
  }
  if (end < totalPages - 1) result.push("gap");
  result.push(totalPages);
  return result;
}
