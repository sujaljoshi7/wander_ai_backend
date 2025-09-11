import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import SearchableSelect from '../components/SearchableSelect.jsx';
import { apiGet, apiPost, apiPut, buildQuery, getEndpoints, createEndpoints, updateEndpoints } from '../api/endpoints.js';
import { showToast } from '../utils/toast.js';

const defaultOpenHours = {
  mon: [["00:00", "23:59"]],
  tue: [["00:00", "23:59"]],
  wed: [["00:00", "23:59"]],
  thu: [["00:00", "23:59"]],
  fri: [["00:00", "23:59"]],
  sat: [["00:00", "23:59"]],
  sun: [["00:00", "23:59"]],
};

const days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

function toSlots(openHours) {
  const result = {};
  for (const d of days) {
    const ranges = openHours?.[d] || [];
    result[d] = ranges.map(([start, end]) => ({ start, end })).slice(0, 2);
    if (result[d].length === 0) result[d] = [{ start: "", end: "" }];
  }
  return result;
}

const initialForm = {
  name: '',
  city: '',
  state: '',
  country: '',
  city_id: '',
  state_id: '',
  country_id: '',
  lat: '',
  lng: '',
  type: '',
  tags: '',
  suitable_for: '',
  famous_for: '',
  description: '',
  avg_visit_mins: '',
  entry_fee_adult: '',
  entry_fee_child: '',
  entry_fee_senior: '',
  avg_cost_amount: '',
  currency: 'INR',
  wheelchair_accessible: false,
  parking_available: false,
  public_transport: true,
  openHours: toSlots(defaultOpenHours),
  closedDays: { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false },
  best_months: '',
  best_time_of_day_to_visit: '',
  rating: '',
  notes: '',
};

export default function PlaceCreate() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const [form, setForm] = useState(initialForm);
  const routeId = params?.id;
  const isEditing = !!routeId || !!location.state?.place;
  const [countriesData, setCountriesData] = useState([]);
  const [statesData, setStatesData] = useState([]);
  const [citiesData, setCitiesData] = useState([]);

  const countries = useMemo(() => countriesData.map(c => c.name), [countriesData]);
  const states = useMemo(() => statesData.map(s => s.name), [statesData]);
  const cities = useMemo(() => citiesData.map(c => c.name), [citiesData]);

  const currencyOptions = useMemo(
    () => [
      'INR', 'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'AUD', 'CAD', 'CHF', 'AED', 'SGD', 'NZD'
    ],
    []
  );

  const onChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((s) => ({ ...s, [name]: type === 'checkbox' ? checked : value }));
  };

  // Prefill when navigated with a place (from state) or by fetching using routeId
  const prefillFromPlace = (p) => {
    try {
      // Derive names and IDs
      const countryName = p.country?.name || p.country || p.city?.state?.country?.name || '';
      const stateName = p.state?.name || p.state || p.city?.state?.name || '';
      const cityName = p.city?.name || p.city || '';
      const country_id = p.country_id || p.country?.country_id || p.city?.state?.country_id || '';
      const state_id = p.state_id || p.state?.state_id || p.city?.state?.state_id || '';
      const city_id = p.city_id || p.city?.city_id || '';

      // Open hours conversion to slots and closedDays
      const apiOpen = p.open_hours || {};
      const computedSlots = toSlots(apiOpen);
      const computedClosed = { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false };
      for (const d of days) {
        const ranges = apiOpen?.[d] || [];
        computedClosed[d] = Array.isArray(ranges) && ranges.length === 0;
      }

      // Best time of day to visit -> text string "HH:mm-HH:mm, ..."
      const bestTimeRanges = p.best_time_of_day_to_visit || p.best_time_of_day || [];
      const bestTimeText = Array.isArray(bestTimeRanges)
        ? bestTimeRanges
            .filter((r) => Array.isArray(r) && r.length === 2)
            .map(([s, e]) => `${s}-${e}`)
            .join(', ')
        : '';

      setForm((s) => ({
        ...s,
        name: p.name || '',
        type: p.type || p.category || '',
        description: p.description || '',
        country: countryName,
        state: stateName,
        city: cityName,
        country_id: country_id || s.country_id,
        state_id: state_id || s.state_id,
        city_id: city_id || s.city_id,
        lat: p.lat ?? p.latitude ?? '',
        lng: p.lng ?? p.longitude ?? '',
        avg_visit_mins: p.avg_visit_mins ?? '',
        tags: Array.isArray(p.tags) ? p.tags.join(', ') : (p.tags || ''),
        suitable_for: Array.isArray(p.suitable_for) ? p.suitable_for.join(', ') : (p.suitable_for || ''),
        famous_for: Array.isArray(p.famous_for) ? p.famous_for.join(', ') : (p.famous_for || ''),
        entry_fee_adult: p.entry_fee?.adult ?? '',
        entry_fee_child: p.entry_fee?.child ?? '',
        entry_fee_senior: p.entry_fee?.senior ?? '',
        avg_cost_amount: (typeof p.avg_cost_per_person === 'number' ? p.avg_cost_per_person : (p.avg_cost_per_person?.amount ?? p.avg_cost_for_one?.amount)) ?? '',
        currency: p.currency || s.currency,
        wheelchair_accessible: !!p.accessibility?.wheelchair_accessible,
        parking_available: !!p.accessibility?.parking_available,
        public_transport: !!p.accessibility?.public_transport,
        openHours: computedSlots,
        closedDays: computedClosed,
        best_months: Array.isArray(p.best_months) ? p.best_months.join(', ') : (p.best_months || ''),
        best_time_of_day_to_visit: bestTimeText,
        rating: p.rating ?? '',
        notes: p.notes ?? p.note ?? '',
      }));
    } catch (_) {
      // no-op
    }
  };

  useEffect(() => {
    const p = location.state?.place;
    if (p) {
      prefillFromPlace(p);
      return;
    }
    if (routeId) {
      (async () => {
        try {
          const resp = await apiGet(`${getEndpoints.placesList}${buildQuery({ id: routeId, page: 1, page_size: 1 })}`);
          const ok = resp?.is_success ?? resp?.isSuccess ?? false;
          if (!ok) return;
          const list = Array.isArray(resp?.result) ? resp.result : [];
          if (list.length) prefillFromPlace(list[0]);
        } catch (_) {}
      })();
    }
  }, [location.state, routeId]);

  // Fetch countries once
  useEffect(() => {
    (async () => {
      try {
        const resp = await apiGet(getEndpoints.countriesList);
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) return;
        const list = Array.isArray(resp?.result) ? resp.result : [];
        setCountriesData(list);
      } catch (_) {}
    })();
  }, []);

  // Backfill country_id if name is selected and id missing when countries load
  useEffect(() => {
    if (form.country && !form.country_id && countriesData.length) {
      const sel = countriesData.find(c => c.name === form.country);
      const cid = sel?.country_id ?? sel?.id;
      if (cid) setForm(s => ({ ...s, country_id: cid }));
    }
  }, [countriesData, form.country, form.country_id]);

  // When country changes, fetch states for that country and reset state+city
  useEffect(() => {
    const selected = countriesData.find(c => c.name === form.country);
    const country_id = form.country_id || selected?.country_id || selected?.id;
    if (!country_id) {
      setStatesData([]);
      setCitiesData([]);
      return;
    }
    (async () => {
      try {
        const resp = await apiGet(`${getEndpoints.statesList}${buildQuery({ country_id, is_active: true, sort_by: 'id' })}`);
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) return;
        const list = Array.isArray(resp?.result) ? resp.result : [];
        setStatesData(list);
      } catch (_) {}
    })();
  }, [form.country, countriesData]);

  // Backfill state_id if name is selected and id missing when states load
  useEffect(() => {
    if (form.state && !form.state_id && statesData.length) {
      const sel = statesData.find(s => s.name === form.state);
      const sid = sel?.state_id ?? sel?.id;
      if (sid) setForm(s => ({ ...s, state_id: sid }));
    }
  }, [statesData, form.state, form.state_id]);

  // When state changes, fetch cities for that state and reset city
  useEffect(() => {
    const selectedState = statesData.find(s => s.name === form.state);
    const state_id = form.state_id || selectedState?.state_id || selectedState?.id;
    if (!state_id) {
      setCitiesData([]);
      return;
    }
    (async () => {
      try {
        const resp = await apiGet(`${getEndpoints.citiesList}${buildQuery({ state_id, is_active: true, sort_by: 'id' })}`);
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) return;
        const list = Array.isArray(resp?.result) ? resp.result : [];
        setCitiesData(list);
      } catch (_) {}
    })();
  }, [form.state, statesData]);

  // Backfill city_id if name is selected and id missing when cities load
  useEffect(() => {
    if (form.city && !form.city_id && citiesData.length) {
      const sel = citiesData.find(c => c.name === form.city);
      const ctid = sel?.city_id ?? sel?.id;
      if (ctid) setForm(s => ({ ...s, city_id: ctid }));
    }
  }, [citiesData, form.city, form.city_id]);

  const parseArray = (text) =>
    text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

  const parseTimeRanges = (text) =>
    text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((range) => {
        const [start, end] = range.split('-').map(t => t.trim());
        if (!start || !end) return null;
        // Simple HH:mm validation; keep as-is if not matching
        const isValid = /^\d{1,2}:\d{2}$/.test(start) && /^\d{1,2}:\d{2}$/.test(end);
        return isValid ? [start, end] : [start, end];
      })
      .filter((pair) => Array.isArray(pair) && pair.length === 2);

  const buildPayload = () => {
    const openHours = {};
    for (const d of days) {
      if (form.closedDays?.[d]) {
        openHours[d] = [];
        continue;
      }
      const slots = form.openHours[d] || [];
      const ranges = slots
        .filter(s => s.start && s.end)
        .map(s => [s.start, s.end]);
      openHours[d] = ranges.length ? ranges : [];
    }

    // Resolve IDs (prefer persisted IDs on form)
    const selCountry = countriesData.find(c => c.name === form.country);
    const selState = statesData.find(s => s.name === form.state);
    const selCity = citiesData.find(c => c.name === form.city);
    const country_id = form.country_id || selCountry?.country_id || selCountry?.id || undefined;
    const state_id = form.state_id || selState?.state_id || selState?.id || undefined;
    const city_id = form.city_id || selCity?.city_id || selCity?.id || undefined;

    const bestTimeRanges = parseTimeRanges(form.best_time_of_day_to_visit || '');

    return {
      name: form.name,
      type: form.type,
      description: form.description,
      country: form.country,
      state: form.state,
      city: form.city,
      country_id,
      state_id,
      city_id,
      lat: Number(form.lat || 0),
      lng: Number(form.lng || 0),
      avg_visit_mins: Number(form.avg_visit_mins || 0),
      tags: parseArray(form.tags),
      suitable_for: parseArray(form.suitable_for),
      famous_for: parseArray(form.famous_for),
      entry_fee: {
        adult: Number(form.entry_fee_adult || 0),
        child: Number(form.entry_fee_child || 0),
        senior: Number(form.entry_fee_senior || 0),
      },
      open_hours: openHours,
      best_months: parseArray(form.best_months),
      best_time_of_day_to_visit: bestTimeRanges,
      accessibility: {
        wheelchair_accessible: !!form.wheelchair_accessible,
        parking_available: !!form.parking_available,
        public_transport: !!form.public_transport,
      },
      avg_cost_per_person: Number(form.avg_cost_amount || 0),
      currency: form.currency || 'INR',
      rating: Number(form.rating || 0),
      notes: form.notes,
    };
  };

  const [output, setOutput] = useState('');

  const onClear = () => {
    setForm(initialForm);
    setOutput('');
  };

  const [saving, setSaving] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    const payload = buildPayload();
    setOutput(JSON.stringify(payload, null, 2));
    try {
      setSaving(true);
      let resp;
      if (isEditing) {
        const place = location.state?.place || {};
        const id = place.id ?? place.place_id ?? form.place_id ?? routeId ?? undefined;
        resp = await apiPut(updateEndpoints.placeUpdate, { id, ...payload });
      } else {
        resp = await apiPost(createEndpoints.placeCreate, payload);
      }
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || (isEditing ? 'Failed to update place' : 'Failed to create place'), 'error');
        return;
      }
      showToast(resp?.message || (isEditing ? 'Place updated successfully' : 'Place created successfully'), 'success');
      if (isEditing) {
        navigate('/place');
      } else {
        // Reset form and preview after successful save
        setForm(initialForm);
        setOutput('');
      }
    } catch (err) {
      showToast(err?.message || (isEditing ? 'Failed to update place' : 'Failed to create place'), 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="container-fluid py-3">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h2 className="mb-1">{isEditing ? 'Update Place' : 'Add Place'}</h2>
          <p className="text-muted small mb-0">{isEditing ? 'Update the details and save changes' : 'Fill the details to add a new place'}</p>
        </div>
        {/* <div className="d-flex gap-2">
          <button type="submit" form="place-form" className="btn btn-gradient" disabled={saving}>{saving ? 'Saving…' : (isEditing ? 'Update' : 'Save')}</button>
        </div> */}
      </div>

      <form id="place-form" onSubmit={onSubmit} className="row g-3">
        {/* Identity */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Identity</div>
            <div className="card-body">
              <div className="row g-3 mb-1">
                <div className="col-md-6">
                  <label className="form-label">Name</label>
                  <input className="form-control" name="name" value={form.name} onChange={onChange} required />
                </div>
                <div className="col-md-6">
                  <label className="form-label">Type</label>
                  <input className="form-control" name="type" value={form.type} onChange={onChange} placeholder="e.g., monument" />
                </div>
              </div>
              <div className="row g-3">
                <div className="col-12">
                  <label className="form-label">Description</label>
                  <textarea className="form-control" rows={3} name="description" value={form.description} onChange={onChange} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Location */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Location</div>
            <div className="card-body">
              <div className="row g-3 mb-1">
                <div className="col-md-4">
                  <SearchableSelect
                    label="Country"
                    value={form.country}
                    onChange={(v) => setForm(s => {
                      const sel = countriesData.find(c => c.name === v);
                      const cid = sel?.country_id ?? sel?.id ?? '';
                      return { ...s, country: v, country_id: cid, state: '', city: '', state_id: '', city_id: '' };
                    })}
                    options={countries}
                    placeholder="Select country"
                  />
                </div>
                <div className="col-md-4">
                  <SearchableSelect
                    label="State"
                    value={form.state}
                    onChange={(v) => setForm(s => {
                      const sel = statesData.find(st => st.name === v);
                      const sid = sel?.state_id ?? sel?.id ?? '';
                      return { ...s, state: v, state_id: sid, city: '', city_id: '' };
                    })}
                    options={states}
                    placeholder={form.country ? 'Select state' : 'Select country first'}
                    disabled={!form.country}
                  />
                </div>
                <div className="col-md-4">
                  <SearchableSelect
                    label="City"
                    value={form.city}
                    onChange={(v) => setForm(s => {
                      const sel = citiesData.find(ct => ct.name === v);
                      const ctid = sel?.city_id ?? sel?.id ?? '';
                      return { ...s, city: v, city_id: ctid };
                    })}
                    options={cities}
                    placeholder={form.state ? 'Select city' : 'Select state first'}
                    disabled={!form.state}
                  />
                </div>
              </div>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label">Lat</label>
                  <input type="number" step="any" className="form-control" name="lat" value={form.lat} onChange={onChange} />
                </div>
                <div className="col-md-4">
                  <label className="form-label">Lng</label>
                  <input type="number" step="any" className="form-control" name="lng" value={form.lng} onChange={onChange} />
                </div>
                <div className="col-md-4">
                  <label className="form-label">Avg Visit (mins)</label>
                  <input type="number" className="form-control" name="avg_visit_mins" value={form.avg_visit_mins} onChange={onChange} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Taxonomy */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Taxonomy</div>
            <div className="card-body row g-3">
              <div className="col-md-4">
                <label className="form-label">Tags (comma separated)</label>
                <input className="form-control" name="tags" value={form.tags} onChange={onChange} placeholder="historic, landmark, photography, waterfront" />
              </div>
              <div className="col-md-4">
                <label className="form-label">Suitable For</label>
                <input className="form-control" name="suitable_for" value={form.suitable_for} onChange={onChange} placeholder="couple, family, solo, group" />
              </div>
              <div className="col-md-4">
                <label className="form-label">Famous For</label>
                <input className="form-control" name="famous_for" value={form.famous_for} onChange={onChange} placeholder="architecture, history, sunset views" />
              </div>
            </div>
          </div>
        </div>

        {/* Pricing */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Pricing</div>
            <div className="card-body row g-3">
              <div className="col-md-2">
                <label className="form-label">Entry Fee (Adult)</label>
                <input type="number" className="form-control" name="entry_fee_adult" value={form.entry_fee_adult} onChange={onChange} />
              </div>
              <div className="col-md-2">
                <label className="form-label">Child</label>
                <input type="number" className="form-control" name="entry_fee_child" value={form.entry_fee_child} onChange={onChange} />
              </div>
              <div className="col-md-2">
                <label className="form-label">Senior</label>
                <input type="number" className="form-control" name="entry_fee_senior" value={form.entry_fee_senior} onChange={onChange} />
              </div>
              <div className="col-md-2">
                <SearchableSelect
                  label="Currency"
                  value={form.currency}
                  onChange={(v) => setForm(s => ({ ...s, currency: v }))}
                  options={currencyOptions}
                  placeholder="Select currency"
                />
              </div>
              <div className="col-md-2">
                <label className="form-label">Avg Cost Amount</label>
                <input className="form-control" name="avg_cost_amount" value={form.avg_cost_amount} onChange={onChange} />
              </div>
              
            </div>
          </div>
        </div>

        {/* Accessibility */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Accessibility</div>
            <div className="card-body row g-3">
              <div className="col-md-3 form-check">
                <input className="form-check-input" type="checkbox" id="wheel" name="wheelchair_accessible" checked={form.wheelchair_accessible} onChange={onChange} />
                <label className="form-check-label" htmlFor="wheel">Wheelchair Accessible</label>
              </div>
              <div className="col-md-3 form-check">
                <input className="form-check-input" type="checkbox" id="park" name="parking_available" checked={form.parking_available} onChange={onChange} />
                <label className="form-check-label" htmlFor="park">Parking Available</label>
              </div>
              <div className="col-md-3 form-check">
                <input className="form-check-input" type="checkbox" id="pt" name="public_transport" checked={form.public_transport} onChange={onChange} />
                <label className="form-check-label" htmlFor="pt">Public Transport</label>
              </div>
            </div>
          </div>
        </div>

        {/* Open Hours (structured) */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold d-flex align-items-center justify-content-between">
              <span>Open Hours</span>
              <small className="text-muted">Set up to two time ranges per day</small>
            </div>
            <div className="card-body">
              <div className="row g-3">
                {days.map((d) => (
                  <div key={d} className="col-12 col-md-6 col-xl-4">
                    <div className="border rounded p-2">
                      <div className="d-flex align-items-center justify-content-between mb-2">
                        <div className="fw-semibold text-capitalize">{d}</div>
                        <div className="form-check form-switch">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id={`closed-${d}`}
                            checked={!!form.closedDays?.[d]}
                            onChange={(e) => {
                              const checked = e.target.checked;
                              setForm((s) => {
                                const next = { ...s, closedDays: { ...(s.closedDays || {}) }, openHours: { ...s.openHours } };
                                next.closedDays[d] = checked;
                                if (checked) {
                                  next.openHours[d] = [];
                                } else {
                                  next.openHours[d] = next.openHours[d]?.length ? next.openHours[d] : [{ start: '', end: '' }];
                                }
                                return next;
                              });
                            }}
                          />
                          <label className="form-check-label ms-2" htmlFor={`closed-${d}`}>Closed</label>
                        </div>
                      </div>
                      {(form.openHours[d] || []).map((slot, idx) => (
                        <div key={idx} className="row g-2 align-items-center mb-1">
                          <div className="col-5">
                            <input
                              type="time"
                              className="form-control"
                              value={slot.start}
                              disabled={!!form.closedDays?.[d]}
                              onChange={(e) => {
                                setForm((s) => {
                                  const next = { ...s, openHours: { ...s.openHours } };
                                  const arr = [...(next.openHours[d] || [])];
                                  arr[idx] = { ...arr[idx], start: e.target.value };
                                  next.openHours[d] = arr;
                                  return next;
                                });
                              }}
                            />
                          </div>
                          <div className="col-5">
                            <input
                              type="time"
                              className="form-control"
                              value={slot.end}
                              disabled={!!form.closedDays?.[d]}
                              onChange={(e) => {
                                setForm((s) => {
                                  const next = { ...s, openHours: { ...s.openHours } };
                                  const arr = [...(next.openHours[d] || [])];
                                  arr[idx] = { ...arr[idx], end: e.target.value };
                                  next.openHours[d] = arr;
                                  return next;
                                });
                              }}
                            />
                          </div>
                          <div className="col-2 text-end">
                            { !form.closedDays?.[d] && (form.openHours[d]?.length || 0) > 1 && (
                              <button type="button" className="btn btn-sm btn-danger" onClick={() => {
                                setForm((s) => {
                                  const next = { ...s, openHours: { ...s.openHours } };
                                  const arr = [...(next.openHours[d] || [])];
                                  arr.splice(idx, 1);
                                  next.openHours[d] = arr.length ? arr : [{ start: "", end: "" }];
                                  return next;
                                });
                              }}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                              <polyline points="3 6 5 6 21 6"></polyline>
                              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                              <path d="M10 11v6"></path>
                              <path d="M14 11v6"></path>
                              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path>
                            </svg></button>
                            )}
                          </div>
                        </div>
                      ))}
                      <div className="text-end">
                        <button
                          type="button"
                          className="btn btn-sm btn-gradient"
                          onClick={() => {
                            setForm((s) => {
                              const next = { ...s, openHours: { ...s.openHours } };
                              const arr = [...(next.openHours[d] || [])];
                              if (arr.length < 2) arr.push({ start: '', end: '' });
                              next.openHours[d] = arr;
                              return next;
                            });
                          }}
                          disabled={!!form.closedDays?.[d] || (form.openHours[d]?.length || 0) >= 2}
                        >
                          Add slot
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Visiting suggestions */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Visit Suggestions</div>
            <div className="card-body row g-3">
              <div className="col-md-6">
                <label className="form-label">Best Months</label>
                <input className="form-control" name="best_months" value={form.best_months} onChange={onChange} placeholder="Nov, Dec, Jan, Feb, Mar" />
              </div>
              <div className="col-md-6">
                <label className="form-label">Best Time of Day</label>
                <input className="form-control" name="best_time_of_day_to_visit" value={form.best_time_of_day_to_visit} onChange={onChange} placeholder="17:00-19:00, 06:00-08:00" />
              </div>
              <div className="col-md-3">
                <label className="form-label">Rating</label>
                <input type="number" step="0.1" className="form-control" name="rating" value={form.rating} onChange={onChange} />
              </div>
              <div className="col-12">
                <label className="form-label">Notes</label>
                <textarea className="form-control" rows={2} name="notes" value={form.notes} onChange={onChange} />
              </div>
            </div>
          </div>
        </div>
      </form>

      {/* Bottom actions */}
      <div className="d-flex justify-content-end gap-2 mt-3">
        <button type="button" className="btn btn-secondary" onClick={onClear}>Clear</button>
        <button
          type="submit"
          form="place-form"
          className="btn btn-gradient"
          disabled={saving || !form.country_id || !form.state_id || !form.city_id}
          title={!form.country_id || !form.state_id || !form.city_id ? 'Select country, state and city' : ''}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      {output && (
        <div className="card mt-4">
          <div className="card-header d-flex align-items-center justify-content-between">
            <strong>Generated JSON</strong>
            <button
              className="btn btn-sm btn-outline-secondary"
              onClick={() => navigator.clipboard.writeText(output)}
            >
              Copy
            </button>
          </div>
          <pre className="m-0 p-3" style={{ whiteSpace: 'pre-wrap' }}>{output}</pre>
        </div>
      )}
    </section>
  );
}
