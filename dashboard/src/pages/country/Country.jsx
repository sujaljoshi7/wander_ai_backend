import { useEffect, useMemo, useRef, useState } from 'react';
import Modal from '../../components/Modal.jsx';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';
import Loader from '../../components/Loader.jsx';
import { apiPost, apiGet, buildQuery, createEndpoints, getEndpoints, updateEndpoints, deleteEndpoints, toggleEndpoints, apiPatch, apiPut } from '../../api/endpoints.js';
import { showToast } from '../../utils/toast.js';

const INITIAL_ROWS = [];

export default function Country() {
  const [rows, setRows] = useState(INITIAL_ROWS);
  const [query, setQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('active'); // 'active' | 'inactive'
  const [loading, setLoading] = useState(false);

  // Modal state (create/update)
  const [form, setForm] = useState({ name: '' });
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);

  // Deletion state
  const [pendingDelete, setPendingDelete] = useState(null);
  // Restore state
  const [pendingRestore, setPendingRestore] = useState(null);
  const countryModalId = 'countryModal';
  const confirmDeleteId = 'confirmDelete';
  const confirmRestoreId = 'confirmRestore';

  const showModal = (id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const modal = window.bootstrap?.Modal.getInstance(el) || new window.bootstrap.Modal(el);
    modal.show();
  };

  const handleRestore = (row) => {
    setPendingRestore(row);
    showModal(confirmRestoreId);
  };

  const doRestore = async () => {
    if (!pendingRestore) return;
    try {
      setLoading(true);
      // Restore by setting is_active: true
      const resp = await apiPatch(deleteEndpoints.countryDelete, {
        id: pendingRestore.id,
        is_active: true,
      });
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to restore country', 'error');
        return;
      }
      showToast(resp?.message || 'Country restored', 'success');
      await fetchCountries(filterStatus);
    } catch (e) {
      showToast(e?.message || 'Failed to restore country', 'error');
    } finally {
      setPendingRestore(null);
      setLoading(false);
    }
  };

  const hideModal = (id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const modal = window.bootstrap?.Modal.getInstance(el) || new window.bootstrap.Modal(el);
    modal.hide();
  };

  const fetchCountries = async (status = filterStatus) => {
    try {
      setLoading(true);
      // Backend expects is_active as a query param using GET
      const resp = await apiGet(
        `${getEndpoints.countriesList}${buildQuery({ is_active: status === 'active', sort_by: 'id' })}`
      );
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to fetch countries', 'error');
        return;
      }
      const list = Array.isArray(resp?.result) ? resp.result : [];
      setRows(list.map((c) => ({
        id: c.id ?? c.country_id,
        name: c.name,
        country_id: c.country_id ?? c.id,
        is_active: (c.is_active ?? c.isActive ?? true) === true,
      })));
    } catch (e) {
      showToast(e?.message || 'Failed to fetch countries', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Run only once on mount (guard against StrictMode double-invoke)
  const hasFetchedRef = useRef(false);
  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;
    fetchCountries('active');
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => !q || `${r.name} ${r.country_id}`.toLowerCase().includes(q));
  }, [rows, query]);

  const openAdd = () => {
    setEditingId(null);
    setForm({ name: '' });
    showModal(countryModalId);
  };

  const openEdit = (row) => {
    setEditingId(row.id);
    setForm({ name: row.name || '' });
    showModal(countryModalId);
  };

  const onSave = async () => {
    if (!form.name?.trim()) return;
    try {
      setSaving(true);
      if (editingId !== null) {
        // Update
        const resp = await apiPut(updateEndpoints.countryUpdate, {
          id: rows.find(r => r.id === editingId)?.id ?? editingId,
          name: form.name.trim(),
        });
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) {
          showToast(resp?.message || 'Failed to update country', 'error');
          return;
        }
        showToast(resp?.message || 'Country updated', 'success');
        await fetchCountries();
      } else {
        // Create
        const resp = await apiPost(createEndpoints.countryCreate, { name: form.name.trim() });
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) {
          showToast(resp?.message || 'Failed to create country', 'error');
          return;
        }
        showToast(resp?.message || 'Country created', 'success');
        await fetchCountries();
      }
      setForm({ name: '' });
      hideModal(countryModalId);
    } catch (err) {
      showToast(err?.message || (editingId ? 'Failed to update country' : 'Failed to create country'), 'error');
    } finally {
      setSaving(false);
      setEditingId(null);
    }
  };

  const handleDelete = (row) => {
    setPendingDelete(row);
    showModal(confirmDeleteId);
  };

  const doDelete = async () => {
    const payload = {
      id: pendingDelete.id,
      is_active: false,
    };
    if (!pendingDelete) return;
    try {
      setLoading(true);
      const resp = await apiPatch(deleteEndpoints.countryDelete, payload);
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to delete country', 'error');
        return;
      }
      showToast(resp?.message || 'Country deleted', 'success');
      await fetchCountries();
    } catch (e) {
      showToast(e?.message || 'Failed to delete country', 'error');
    } finally {
      setPendingDelete(null);
      setLoading(false);
    }
  };

  const onToggleStatus = async (row) => {
    try {
      const next = !row.is_active;
      // optimistic
      setRows((prev) => prev.map(r => r.id === row.id ? { ...r, is_active: next } : r));
      const resp = await apiPost(toggleEndpoints.countryToggleStatus, {
        id: row.id,
        is_active: next,
      });
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) throw new Error(resp?.message || 'Failed to toggle status');
      showToast(resp?.message || 'Status updated', 'success');
    } catch (e) {
      showToast(e?.message || 'Failed to toggle status', 'error');
      // revert
      setRows((prev) => prev.map(r => r.id === row.id ? { ...r, is_active: !r.is_active } : r));
    }
  };

  return (
    <section className="container-fluid py-3">
      <div className="d-flex align-items-end justify-content-between mb-3">
        <div>
          <h2 className="mb-1">Countries</h2>
          <p className="text-muted small mb-0">Manage countries</p>
        </div>
        <div className="d-flex align-items-center gap-2">
          <div className="input-group" style={{ minWidth: 260 }}>
            <span className="input-group-text">🔍</span>
            <input className="form-control" placeholder="Search state, country" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <select
            className="form-select"
            style={{ minWidth: 160 }}
            value={filterStatus}
            onChange={(e) => { const v = e.target.value; setFilterStatus(v); fetchCountries(v); }}
            aria-label="Filter by status"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <button className="btn btn-gradient d-inline-flex align-items-center gap-2 text-nowrap" onClick={openAdd}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Country
          </button>
        </div>
      </div>

      <div className="card shadow-sm">
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th className="text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id}>
                  <td className="fw-semibold">{r.country_id}</td>
                  <td>{r.name}</td>
                  <td className="text-center">
                    <div className="d-inline-flex justify-content-center align-items-center gap-2">
                      {r.is_active ? (
                        <>
                          <button className="btn btn-sm btn-outline-primary" onClick={() => openEdit(r)} title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <path d="M12 20h9"/>
                              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
                            </svg>
                          </button>
                          <button className="btn btn-sm btn-danger" onClick={() => handleDelete(r)} title="Delete">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <polyline points="3 6 5 6 21 6"></polyline>
                              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                              <path d="M10 11v6"></path>
                              <path d="M14 11v6"></path>
                              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path>
                            </svg>
                          </button>
                        </>
                      ) : (
                        <button className="btn btn-sm btn-success" onClick={() => handleRestore(r)} title="Restore">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                            <polyline points="1 4 1 10 7 10"></polyline>
                            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                          </svg>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={3} className="text-center text-muted py-5">No results</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Update Country Modal */}
      <Modal
        id={countryModalId}
        title={editingId ? 'Edit Country' : 'Add Country'}
        headerGradient
        onClose={() => { setForm({ name: '' }); setEditingId(null); }}
        footer={(
          <>
            <button type="button" className="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" className="btn btn-gradient" onClick={onSave} disabled={!form.name || saving}>{saving ? 'Saving…' : 'Save'}</button>
          </>
        )}
      >
        <div className="mb-3">
          <label className="form-label">Name</label>
          <input className="form-control" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Country name" />
      </div>
      </Modal>

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        id={confirmDeleteId}
        title="Delete Country"
        message={pendingDelete ? (
          <>
            Are you sure you want to delete <strong>{pendingDelete.name}</strong>?
          </>
        ) : 'Are you sure you want to delete this country?'}
        confirmText="Delete"
        onConfirm={doDelete}
        variant="danger"
      />

      {/* Confirm Restore Dialog */}
      <ConfirmDialog
        id={confirmRestoreId}
        title="Restore Country"
        message={pendingRestore ? (
          <>
            Are you sure you want to restore <strong>{pendingRestore.name}</strong>?
          </>
        ) : 'Are you sure you want to restore this country?'}
        confirmText="Restore"
        onConfirm={doRestore}
        variant="success"
      />

      {/* Loader Overlay */}
      <Loader visible={loading} text="Please wait..." />
    </section>
  );
}

