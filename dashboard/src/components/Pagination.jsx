import { useMemo } from 'react';

/**
 * BootstrapPagination - reusable pagination component
 * Props:
 * - current: number (1-based)
 * - total: number (>= 1)
 * - onChange: (page: number) => void
 * - maxButtons?: number (default 5)
 * - size?: 'sm' | 'lg' | undefined (Bootstrap size)
 */
export default function BootstrapPagination({ current, total, onChange, maxButtons = 5, size }) {
  const pageNumbers = useMemo(() => {
    const pages = [];
    if (total <= maxButtons) {
      for (let i = 1; i <= total; i++) pages.push(i);
      return pages;
    }
    let startPage = Math.max(1, current - Math.floor(maxButtons / 2));
    let endPage = startPage + maxButtons - 1;
    if (endPage > total) {
      endPage = total;
      startPage = endPage - maxButtons + 1;
    }
    for (let i = startPage; i <= endPage; i++) pages.push(i);
    return pages;
  }, [current, total, maxButtons]);

  const sizeClass = size ? ` pagination-${size}` : '';

  return (
    <nav>
      <ul className={`pagination mb-0${sizeClass} gap-2`}>
        <li className={`page-item ${current === 1 ? 'disabled' : ''}`}>
          <button
            className="page-link"
            aria-label="Previous"
            onClick={() => onChange(Math.max(1, current - 1))}
          >
            Prev
          </button>
        </li>
        {pageNumbers.map((p) => (
          <li key={p} className={`page-item ${p === current ? 'active' : ''}`}>
            <button className="page-link" onClick={() => onChange(p)}>{p}</button>
          </li>
        ))}
        <li className={`page-item ${current === total ? 'disabled' : ''}`}>
          <button
            className="page-link"
            aria-label="Next"
            onClick={() => onChange(Math.min(total, current + 1))}
          >
            Next
          </button>
        </li>
      </ul>
    </nav>
  );
}
