import { useEffect, useMemo, useRef, useState } from 'react';
import Modal from '../../components/Modal.jsx';
import ConfirmDialog from '../../components/ConfirmDialog.jsx';
import Loader from '../../components/Loader.jsx';
import { apiPost, apiGet, apiPut, buildQuery, createEndpoints, getEndpoints, updateEndpoints, deleteEndpoints, toggleEndpoints, apiPatch } from '../../api/endpoints.js';
import { showToast } from '../../utils/toast.js';
import SearchableSelect from '../../components/SearchableSelect.jsx';

const INITIAL_ROWS = [];

export default function State() {
  const [rows, setRows] = useState(INITIAL_ROWS);
  const [query, setQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('active'); // 'active' | 'inactive'
  const [loading, setLoading] = useState(false);

  // Modal state (create/update)
  const [form, setForm] = useState({ name: '' });
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [countriesData, setCountriesData] = useState([]);
  const countries = useMemo(() => countriesData.map(c => c.name), [countriesData]);
  // Deletion state
  const [pendingDelete, setPendingDelete] = useState(null);
  // Restore state
  const [pendingRestore, setPendingRestore] = useState(null);
  const stateModalId = 'stateModal';
  const confirmDeleteId = 'confirmDelete';
  const confirmRestoreId = 'confirmRestore';

  const showModal = (id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const modal = window.bootstrap?.Modal.getInstance(el) || new window.bootstrap.Modal(el);
    modal.show();
  };

  useEffect(() => {
    (async () => {
      try {
        const resp = await apiGet(getEndpoints.countriesList);
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) {
          showToast(resp?.message || 'Failed to fetch countries', 'error');
          return;
        }
        const list = Array.isArray(resp?.result) ? resp.result : [];
        setCountriesData(list);
      } catch (e) {
        showToast(e?.message || 'Failed to fetch countries', 'error');
      }
    })();
  }, []);

  const handleRestore = (row) => {
    setPendingRestore(row);
    showModal(confirmRestoreId);
  };

  const doRestore = async () => {
    if (!pendingRestore) return;
    try {
      setLoading(true);
      // Restore by setting is_active: true
      const resp = await apiPatch(deleteEndpoints.stateDelete, {
        id: pendingRestore.id,
        is_active: true,
      });
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to restore state', 'error');
        return;
      }
      showToast(resp?.message || 'State restored', 'success');
      await fetchStates(filterStatus);
    } catch (e) {
      showToast(e?.message || 'Failed to restore state', 'error');
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

  const fetchStates = async (status = filterStatus) => {
    try {
      setLoading(true);
      // Backend expects is_active as a query param using GET
      const resp = await apiGet(
        `${getEndpoints.statesList}${buildQuery({ is_active: status === 'active', sort_by: 'id' })}`
      );
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to fetch states', 'error');
        return;
      }
      const list = Array.isArray(resp?.result) ? resp.result : [];
      setRows(list.map((c) => ({
        id: c.id ?? c.state_id ?? c.country_id,
        state_id: c.state_id ?? c.id,
        name: c.name,
        country_id: c.country_id,
        country: c.country || { name: '', country_id: c.country_id },
        is_active: (c.is_active ?? c.isActive ?? true) === true,
      })));
    } catch (e) {
      showToast(e?.message || 'Failed to fetch states', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Run only once on mount (guard against StrictMode double-invoke)
  const hasFetchedRef = useRef(false);
  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;
    fetchStates('active');
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => !q || `${r.name} ${r.country_id} ${r.country?.name || ''}`.toLowerCase().includes(q));
  }, [rows, query]);

  const openAdd = () => {
    setEditingId(null);
    setForm({ name: '' });
    showModal(stateModalId);
  };

  const openEdit = (row) => {
    setEditingId(row.id);
    setForm({ name: row.name || '', country: row.country?.name || '' });
    showModal(stateModalId);
  };

  const onSave = async () => {
    if (!form.name?.trim()) return;
    try {
      setSaving(true);
      const selected = countriesData.find(c => c.name === form.country);
      const selectedCountryId = selected?.country_id ?? selected?.id;
      if (!editingId && !selectedCountryId) {
        showToast('Please select a country for the state', 'error');
        return;
      }
      if (editingId !== null) {
        // Update
        const resp = await apiPut(updateEndpoints.stateUpdate, {
          state_id: rows.find(r => r.id === editingId)?.state_id ?? editingId,
          name: form.name.trim(),
          ...(selectedCountryId ? { country_id: selectedCountryId } : {}),
        });
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) {
          showToast(resp?.message || 'Failed to update state', 'error');
          return;
        }
        showToast(resp?.message || 'State updated', 'success');
        await fetchStates();
      } else {
        // Create
        const resp = await apiPost(createEndpoints.stateCreate, { name: form.name.trim(), country_id: selectedCountryId });
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) {
          showToast(resp?.message || 'Failed to create state', 'error');
          return;
        }
        showToast(resp?.message || 'State created', 'success');
        await fetchStates();
      }
      setForm({ name: '' });
      hideModal(stateModalId);
    } catch (err) {
      showToast(err?.message || (editingId ? 'Failed to update state' : 'Failed to create state'), 'error');
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
      const resp = await apiPatch(deleteEndpoints.stateDelete, payload);
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || 'Failed to delete state', 'error');
        return;
      }
      showToast(resp?.message || 'State deleted', 'success');
      await fetchStates(filterStatus);
    } catch (e) {
      showToast(e?.message || 'Failed to delete state', 'error');
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
          <h2 className="mb-1">States</h2>
          <p className="text-muted small mb-0">Manage states</p>
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
            onChange={(e) => { const v = e.target.value; setFilterStatus(v); fetchStates(v); }}
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
            Add State
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
                <th>Country</th>
                <th className="text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id}>
                  <td className="fw-semibold">{r.state_id}</td>
                  <td>{r.name}</td>
                  <td>{r.country.name}</td>
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
                  <td colSpan={4} className="text-center text-muted py-5">No results</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Update State Modal */}
      <Modal
        id={stateModalId}
        title={editingId ? 'Edit State' : 'Add State'}
        headerGradient
        onClose={() => { setForm({ name: '' }); setEditingId(null); }}
        footer={(
          <>
            <button type="button" className="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" className="btn btn-gradient" onClick={onSave} disabled={!form.name || !form.country || saving}>{saving ? 'Saving…' : 'Save'}</button>
          </>
        )}
      >
        <div className="mb-3">
          <label className="form-label">Name</label>
          <input className="form-control" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="State name" />
          <SearchableSelect
          label="Country"
          value={form.country}
          onChange={(v) => {
            setForm({ name: form.name, country: v, state: '' });
          }}
          options={countries}
          placeholder="Select country"
        />
      </div>
      </Modal>

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        id={confirmDeleteId}
        title="Delete State"
        message={pendingDelete ? (
          <>
            Are you sure you want to delete <strong>{pendingDelete.name}</strong>?
          </>
        ) : 'Are you sure you want to delete this state?'}
        confirmText="Delete"
        onConfirm={doDelete}
        variant="danger"
      />

      {/* Confirm Restore Dialog */}
      <ConfirmDialog
        id={confirmRestoreId}
        title="Restore State"
        message={pendingRestore ? (
          <>
            Are you sure you want to restore <strong>{pendingRestore.name}</strong>?
          </>
        ) : 'Are you sure you want to restore this state?'}
        confirmText="Restore"
        onConfirm={doRestore}
        variant="success"
      />

      {/* Loader Overlay */}
      <Loader visible={loading} text="Please wait..." />
    </section>
  );
}

