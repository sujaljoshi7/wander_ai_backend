import { useMemo, useRef, useState } from 'react';

/**
 * SearchableSelect - simple searchable dropdown using Bootstrap styles.
 * Props:
 * - label?: string
 * - value: string
 * - onChange: (value: string) => void
 * - options: string[]
 * - placeholder?: string
 * - disabled?: boolean
 */
export default function SearchableSelect({ label, value, onChange, options, placeholder = 'Select...', disabled = false }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const btnRef = useRef(null);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return options;
    return options.filter((o) => o.toLowerCase().includes(term));
  }, [q, options]);

  return (
    <div className="mb-3">
      {label && <label className="form-label">{label}</label>}
      <div className="dropdown w-100">
        <button
          className="btn btn-light w-100 text-start d-flex justify-content-between align-items-center"
          type="button"
          disabled={disabled}
          data-bs-toggle="dropdown"
          aria-expanded={open}
          ref={btnRef}
          onClick={() => setOpen(!open)}
        >
          <span className="text-truncate">{value || placeholder}</span>
          <span className="ms-2">▾</span>
        </button>
        <div className="dropdown-menu p-2" style={{ width: '100%' }}>
          <input
            className="form-control mb-2"
            placeholder="Search..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            autoFocus
            onClick={(e) => e.stopPropagation()}
          />
          <div className="list-select" style={{ maxHeight: 220, overflowY: 'auto' }}>
            {filtered.length === 0 && (
              <div className="text-muted small px-2 py-1">No results</div>
            )}
            {filtered.map((opt, idx) => (
              <button
                key={opt}
                type="button"
                className={`dropdown-item py-2 ${opt === value ? 'active' : ''}`}
                onClick={() => {
                  onChange(opt);
                  setOpen(false);
                  setQ('');
                  btnRef.current?.click();
                }}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
