import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import SearchableSelect from '../../components/SearchableSelect.jsx';
import { apiGet, apiPost, apiPut, buildQuery, getEndpoints, createEndpoints, updateEndpoints } from '../../api/endpoints.js';
import { showToast } from '../../utils/toast.js';

const initialForm = {
  name: '',
  description: '',
  city: '',
  city_id: '',
  lat: '',
  lng: '',
  cuisine_text: '',
  price_range: '',
  must_try_dishes_text: '',
  tags_text: '',
  food_type: '',
  notes: '',
};

// (no extra helpers required)

export default function RestaurantCreate() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const [form, setForm] = useState(initialForm);
  const routeId = params?.id;
  const isEditing = !!routeId || !!location.state?.restaurant;
  const [citiesData, setCitiesData] = useState([]);

  const cities = useMemo(() => citiesData.map(c => c.name), [citiesData]);
  const foodTypeOptions = useMemo(() => ['Veg', 'Non Veg'], []);

  const onChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((s) => ({ ...s, [name]: type === 'checkbox' ? checked : value }));
  };

  const prefillFromRestaurant = (r) => {
    try {
      setForm((s) => ({
        ...s,
        name: r.name || '',
        description: r.description || '',
        city: r.city?.name || r.city || '',
        city_id: r.city_id || r.city?.city_id || s.city_id,
        lat: r.lat ?? r.latitude ?? '',
        lng: r.lng ?? r.longitude ?? '',
        cuisine_text: Array.isArray(r.cuisine) ? r.cuisine.join(', ') : (r.cuisine || ''),
        price_range: r.price_range || '',
        must_try_dishes_text: Array.isArray(r.must_try_dishes) ? r.must_try_dishes.join(', ') : (r.must_try_dishes || ''),
        tags_text: Array.isArray(r.tags) ? r.tags.join(', ') : (r.tags || ''),
        food_type: r.food_type || '',
        notes: r.notes || r.note || '',
      }));
    } catch (_) {
      // no-op
    }
  };

  useEffect(() => {
    const r = location.state?.restaurant;
    if (r) {
      prefillFromRestaurant(r);
      return;
    }
    if (routeId) {
      (async () => {
        try {
          const resp = await apiGet(`${getEndpoints.restaurantsList}${buildQuery({ id: routeId, page: 1, page_size: 1 })}`);
          const ok = resp?.is_success ?? resp?.isSuccess ?? false;
          if (!ok) return;
          const list = Array.isArray(resp?.result) ? resp.result : [];
          if (list.length) prefillFromRestaurant(list[0]);
        } catch (_) {}
      })();
    }
  }, [location.state, routeId]);

  // Fetch all cities once for selection
  useEffect(() => {
    (async () => {
      try {
        const resp = await apiGet(getEndpoints.citiesList);
        const ok = resp?.is_success ?? resp?.isSuccess ?? false;
        if (!ok) return;
        const list = Array.isArray(resp?.result) ? resp.result : [];
        setCitiesData(list);
      } catch (_) {}
    })();
  }, []);

  const parseArray = (text) =>
    text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

  const buildPayload = () => {
    return {
      name: form.name,
      description: form.description,
      city: form.city,
      city_id: form.city_id || (citiesData.find(c => c.name === form.city)?.city_id ?? undefined),
      lat: Number(form.lat || 0),
      lng: Number(form.lng || 0),
      cuisine: parseArray(form.cuisine_text),
      price_range: form.price_range,
      must_try_dishes: parseArray(form.must_try_dishes_text),
      food_type: form.food_type,
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
        const restaurant = location.state?.restaurant || {};
        const id = restaurant.id ?? restaurant.restaurant_id ?? form.restaurant_id ?? routeId ?? undefined;
        resp = await apiPut(updateEndpoints.restaurantUpdate, { id, ...payload });
      } else {
        resp = await apiPost(createEndpoints.restaurantCreate, payload);
      }
      const ok = resp?.is_success ?? resp?.isSuccess ?? false;
      if (!ok) {
        showToast(resp?.message || (isEditing ? 'Failed to update restaurant' : 'Failed to create restaurant'), 'error');
        return;
      }
      showToast(resp?.message || (isEditing ? 'Restaurant updated successfully' : 'Restaurant created successfully'), 'success');
      if (isEditing) {
        navigate('/restaurant');
      } else {
        // Reset form and preview after successful save
        setForm(initialForm);
        setOutput('');
      }
    } catch (err) {
      showToast(err?.message || (isEditing ? 'Failed to update restaurant' : 'Failed to create restaurant'), 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="container-fluid py-3">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h2 className="mb-1">{isEditing ? 'Update Restaurant' : 'Add Restaurant'}</h2>
          <p className="text-muted small mb-0">{isEditing ? 'Update the details and save changes' : 'Fill the details to add a new restaurant'}</p>
        </div>
        {/* <div className="d-flex gap-2">
          <button type="submit" form="restaurant-form" className="btn btn-gradient" disabled={saving}>{saving ? 'Saving…' : (isEditing ? 'Update' : 'Save')}</button>
        </div> */}
      </div>

      <form id="restaurant-form" onSubmit={onSubmit} className="row g-3">
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
                  <SearchableSelect
                    label="Food Type"
                    value={form.food_type}
                    onChange={(v) => setForm(s => ({ ...s, food_type: v }))}
                    options={foodTypeOptions}
                    placeholder="Select food type"
                  />
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
                <div className="col-md-6">
                  <SearchableSelect
                    label="City"
                    value={form.city}
                    onChange={(v) => setForm(s => {
                      const sel = citiesData.find(ct => ct.name === v);
                      const ctid = sel?.city_id ?? sel?.id ?? '';
                      return { ...s, city: v, city_id: ctid };
                    })}
                    options={cities}
                    placeholder="Select city"
                  />
                </div>
                <div className="col-md-3">
                  <label className="form-label">Lat</label>
                  <input type="number" step="any" className="form-control" name="lat" value={form.lat} onChange={onChange} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">Lng</label>
                  <input type="number" step="any" className="form-control" name="lng" value={form.lng} onChange={onChange} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Food Details */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Food Details</div>
            <div className="card-body row g-3">
              <div className="col-md-4">
                <label className="form-label">Cuisine (comma separated)</label>
                <input className="form-control" name="cuisine_text" value={form.cuisine_text} onChange={onChange} placeholder="Indian, Chinese, Continental" />
              </div>
              <div className="col-md-4">
                <label className="form-label">Must Try Dishes</label>
                <input className="form-control" name="must_try_dishes_text" value={form.must_try_dishes_text} onChange={onChange} placeholder="Momos, Dosa, Vada Pav" />
              </div>
              <div className="col-md-4">
                <label className="form-label">Price Range</label>
                <input className="form-control" name="price_range" value={form.price_range} onChange={onChange} placeholder="e.g. 200-500" />
              </div>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="col-12">
          <div className="card">
            <div className="card-header fw-semibold">Notes</div>
            <div className="card-body row g-3">
              <div className="col-md-12">
                <label className="form-label">Notes</label>
                <textarea className="form-control" rows={3} name="notes" value={form.notes} onChange={onChange} />
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
          form="restaurant-form"
          className="btn btn-gradient"
          disabled={saving || !form.city_id || !form.name}
          title={!form.city_id ? 'Select city' : ''}
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
