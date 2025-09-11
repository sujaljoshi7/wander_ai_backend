import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import BootstrapPagination from '../components/Pagination.jsx';
import { apiGet, apiPatch, buildQuery, getEndpoints, deleteEndpoints } from '../api/endpoints.js';
import { showToast } from '../utils/toast.js';
import ConfirmDialog from '../components/ConfirmDialog.jsx';

export default function Place() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const navigate = useNavigate();

  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [cityFilter, setCityFilter] = useState('All');
  const [typeFilter, setTypeFilter] = useState('All');
  const [filterStatus, setFilterStatus] = useState('active');
  const [pendingDelete, setPendingDelete] = useState(null);
  const [pendingRestore, setPendingRestore] = useState(null);

  // Fetch places
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const resp = await apiGet(`${getEndpoints.placesList}${buildQuery({ is_active: filterStatus === 'active', sort_by: 'id', page, page_size: pageSize, q: query || undefined })}`);
        const ok = resp?.is_success ?? resp?.isSuccess ?? true;
        if (!ok) {
          showToast(resp?.message || 'Failed to fetch places', 'error');
          return;
        }
        const list = Array.isArray(resp?.result) ? resp.result : (Array.isArray(resp) ? resp : []);
        const mapped = list.map((p) => ({
          id: p.id ?? p.place_id ?? p.city_id ?? Math.random(),
          name: p.name ?? '',
          city: p.city ?? p.city_name ?? p.city?.name ?? '',
          type: p.type ?? p.category ?? '',
          rating: Number(p.rating ?? 0),
          raw: p,
        }));
        setData(mapped);
        const totalFromApi = resp?.pagination?.total_count ?? resp?.pagination?.total ?? resp?.total ?? undefined;
        setTotalCount(typeof totalFromApi === 'number' ? totalFromApi : mapped.length);
      } catch (e) {
        showToast(e?.message || 'Failed to fetch places', 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, [page, pageSize, query, filterStatus]);

  const cities = useMemo(() => Array.from(new Set(data.map(p => p.city))).filter(Boolean).sort(), [data]);
  const types = useMemo(() => Array.from(new Set(data.map(p => p.type))).filter(Boolean).sort(), [data]);

  const filtered = useMemo(() => {
    // Client-side filtering for city/type (applied to current page only)
    return data.filter((p) => {
      const matchesCity = cityFilter === 'All' || p.city === cityFilter;
      const matchesType = typeFilter === 'All' || p.type === typeFilter;
      return matchesCity && matchesType;
    });
  }, [data, cityFilter, typeFilter]);

  const totalPages = Math.max(1, Math.ceil((totalCount || 0) / pageSize));
  const currentPage = Math.min(page, totalPages);
  const rows = filtered; // current page rows from server

  const avgRating = useMemo(() => {
    if (filtered.length === 0) return 0;
    const sum = filtered.reduce((acc, p) => acc + p.rating, 0);
    return sum / filtered.length;
  }, [filtered]);

  const handleView = (row) => {
    const id = row?.id;
    navigate(`/place/update/${id}`, { state: { place: row.raw || row } });
  };

  const handleDelete = (row) => {
    setPendingDelete(row);
    const el = document.getElementById('confirmDeletePlace');
    if (!el) return;
    const modal = window.bootstrap?.Modal.getInstance(el) || new window.bootstrap.Modal(el);
    modal.show();
  };

  const doDelete = async () => {
    if (!pendingDelete) return;
    try {
      setLoading(true);
      const payload = { id: pendingDelete.id, is_active: false };
      const resp = await apiPatch(deleteEndpoints.placeDelete, payload);
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to delete place', 'error');
        return;
      }
      showToast(resp?.message || 'Place deleted', 'success');
      await (async () => {
        const r = await apiGet(`${getEndpoints.placesList}${buildQuery({ is_active: filterStatus === 'active', sort_by: 'id', page, page_size: pageSize, q: query || undefined })}`);
        const list = Array.isArray(r?.result) ? r.result : (Array.isArray(r) ? r : []);
        const mapped = list.map((p) => ({ id: p.id ?? p.place_id ?? p.city_id ?? Math.random(), name: p.name ?? '', city: p.city ?? p.city_name ?? p.city?.name ?? '', type: p.type ?? p.category ?? '', rating: Number(p.rating ?? 0), raw: p }));
        setData(mapped);
        const totalFromApi = r?.pagination?.total_count ?? r?.pagination?.total ?? r?.total ?? undefined;
        setTotalCount(typeof totalFromApi === 'number' ? totalFromApi : mapped.length);
      })();
    } catch (e) {
      showToast(e?.message || 'Failed to delete place', 'error');
    } finally {
      setPendingDelete(null);
      setLoading(false);
    }
  };

  const handleRestore = (row) => {
    setPendingRestore(row);
    const el = document.getElementById('confirmRestorePlace');
    if (!el) return;
    const modal = window.bootstrap?.Modal.getInstance(el) || new window.bootstrap.Modal(el);
    modal.show();
  };

  const doRestore = async () => {
    if (!pendingRestore) return;
    try {
      setLoading(true);
      const payload = { id: pendingRestore.id, is_active: true };
      const resp = await apiPatch(deleteEndpoints.placeDelete, payload);
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to restore place', 'error');
        return;
      }
      showToast(resp?.message || 'Place restored', 'success');
      await (async () => {
        const r = await apiGet(`${getEndpoints.placesList}${buildQuery({ is_active: filterStatus === 'active', sort_by: 'id', page, page_size: pageSize, q: query || undefined })}`);
        const list = Array.isArray(r?.result) ? r.result : (Array.isArray(r) ? r : []);
        const mapped = list.map((p) => ({ id: p.id ?? p.place_id ?? p.city_id ?? Math.random(), name: p.name ?? '', city: p.city ?? p.city_name ?? p.city?.name ?? '', type: p.type ?? p.category ?? '', rating: Number(p.rating ?? 0), raw: p }));
        setData(mapped);
        const totalFromApi = r?.pagination?.total_count ?? r?.pagination?.total ?? r?.total ?? undefined;
        setTotalCount(typeof totalFromApi === 'number' ? totalFromApi : mapped.length);
      })();
    } catch (e) {
      showToast(e?.message || 'Failed to restore place', 'error');
    } finally {
      setPendingRestore(null);
      setLoading(false);
    }
  };

  const goTo = (p) => setPage(Math.min(Math.max(1, p), totalPages));

  // Sliding window of up to 5 numeric pages (no first/last, no ellipses)
  const pageNumbers = useMemo(() => {
    const maxButtons = 5;
    const pages = [];
    if (totalPages <= maxButtons) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
      return pages;
    }
    let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    let endPage = startPage + maxButtons - 1;
    if (endPage > totalPages) {
      endPage = totalPages;
      startPage = endPage - maxButtons + 1;
    }
    for (let i = startPage; i <= endPage; i++) pages.push(i);
    return pages;
  }, [currentPage, totalPages]);

  return (
    <section className="container-fluid py-3">
      {/* Title and controls */}
      <div className="d-flex flex-column gap-3">
        <div className="d-flex align-items-end justify-content-between gap-3">
          <div>
            <h2 className="mb-1">Places</h2>
            <p className="text-muted small mb-0">Manage places across cities and types</p>
          </div>
          <div className="d-flex align-items-center gap-2">
            <div className="input-group" style={{ minWidth: 260 }}>
              <span className="input-group-text" id="search-addon">🔍</span>
              <input
                type="text"
                className="form-control"
                placeholder="Search name, city, type..."
                aria-label="Search"
                aria-describedby="search-addon"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setPage(1); }}
              />
            </div>
            <select
              className="form-select"
              style={{ minWidth: 160 }}
              value={filterStatus}
              onChange={(e) => { const v = e.target.value; setFilterStatus(v); setPage(1); }}
              aria-label="Filter by status"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <select
              className="form-select"
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              aria-label="Rows per page"
              style={{ width: 140 }}
            >
              <option value={5}>5 / page</option>
              <option value={10}>10 / page</option>
              <option value={20}>20 / page</option>
            </select>
            <Link to="/place/new" className="btn btn-gradient d-inline-flex align-items-center gap-2 text-nowrap">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Place
            </Link>
          </div>
        </div>

        {/* KPIs */}
        <div className="row g-3">
          <div className="col-12 col-sm-4">
            <div className="card shadow-sm">
              <div className="card-body">
                <div className="text-muted small">Total Places</div>
                <div className="h4 mb-0 fw-bold">{totalCount}</div>
              </div>
            </div>
          </div>
          <div className="col-12 col-sm-4">
            <div className="card shadow-sm">
              <div className="card-body">
                <div className="text-muted small">Average Rating</div>
                <div className="h4 mb-0 fw-bold">{avgRating.toFixed(2)}</div>
              </div>
            </div>
          </div>
          <div className="col-12 col-sm-4">
            <div className="card shadow-sm">
              <div className="card-body">
                <div className="text-muted small">Cities</div>
                <div className="h4 mb-0 fw-bold">{cities.length}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="d-flex flex-wrap align-items-center gap-2">
          <select className="form-select" value={cityFilter} onChange={(e) => { setCityFilter(e.target.value); setPage(1); }} style={{ width: 180 }}>
            <option>All</option>
            {cities.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select className="form-select" value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }} style={{ width: 180 }}>
            <option>All</option>
            {types.map((t) => <option key={t}>{t}</option>)}
          </select>
          {(cityFilter !== 'All' || typeFilter !== 'All' || query) && (
            <button className="btn btn-outline-secondary btn-sm" onClick={() => { setCityFilter('All'); setTypeFilter('All'); setQuery(''); setPage(1); }}>
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card mt-3 shadow-sm">
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Name</th>
                <th>City</th>
                <th>Type</th>
                <th>Rating</th>
                <th className="text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="fw-semibold">{row.name}</div>
                    <div className="text-muted small">ID: {row.id}</div>
                  </td>
                  <td>{row.city}</td>
                  <td>
                    <span className="badge rounded-pill text-bg-light border">{row.type}</span>
                  </td>
                  <td>
                    <div className="d-flex align-items-center gap-1">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <svg key={i} width="16" height="16" viewBox="0 0 20 20" fill={i < Math.round(row.rating) ? '#f59e0b' : 'none'} stroke="#f59e0b">
                          <path d="M10 15l-5.878 3.09L5.5 12.18.999 7.91l6.061-.88L10 1l2.94 6.03 6.061.88-4.5 4.27 1.378 5.91z"/>
                        </svg>
                      ))}
                      <span className="text-muted small">{row.rating.toFixed(1)}</span>
                    </div>
                  </td>
                  <td className="text-center">
                    <div className="d-inline-flex justify-content-center align-items-center gap-2">
                      {filterStatus === 'inactive' ? (
                        <button className="btn btn-sm btn-success" onClick={() => handleRestore(row)} title="Restore">Restore</button>
                      ) : (
                        <>
                          <button className="btn btn-sm btn-outline-primary" onClick={() => handleView(row)} title="Edit">Edit</button>
                          <button className="btn btn-sm btn-danger" onClick={() => handleDelete(row)} title="Delete">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <polyline points="3 6 5 6 21 6"></polyline>
                              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                              <path d="M10 11v6"></path>
                              <path d="M14 11v6"></path>
                              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path>
                            </svg>
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-muted py-5">No results</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="d-flex align-items-center justify-content-between mt-3 text-muted small">
        <div>
          Showing {rows.length ? (currentPage - 1) * pageSize + 1 : 0}-{(currentPage - 1) * pageSize + rows.length} of {totalCount}
        </div>
        <BootstrapPagination
          current={currentPage}
          total={totalPages}
          onChange={goTo}
          size="sm"
        />
      </div>

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        id="confirmDeletePlace"
        title="Delete Place"
        message={pendingDelete ? (
          <>
            Are you sure you want to delete <strong>{pendingDelete.name}</strong>?
          </>
        ) : 'Are you sure you want to delete this place?'}
        confirmText="Delete"
        onConfirm={doDelete}
        variant="danger"
      />

      {/* Confirm Restore Dialog */}
      <ConfirmDialog
        id="confirmRestorePlace"
        title="Restore Place"
        message={pendingRestore ? (
          <>
            Are you sure you want to restore <strong>{pendingRestore.name}</strong>?
          </>
        ) : 'Are you sure you want to restore this place?'}
        confirmText="Restore"
        onConfirm={doRestore}
        variant="success"
      />
    </section>
  );
}
