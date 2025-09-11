// Centralized API configuration: base URL and endpoint paths
// Set VITE_API_BASE_URL in your .env to override the default
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://192.168.1.25:9000/api';

// Resource paths (no trailing slashes)
export const endpoints = {
  cities: '/cities',
  states: '/states',
  countries: '/countries',
  places: '/places',
  restaurants: '/restaurant',
  foods: '/foods',
  hotels: '/hotels',
  itineraries: '/itineraries',
};

// Create endpoints
export const createEndpoints = {
  cityCreate: '/city/create',
  stateCreate: '/state/create',
  countryCreate: '/country/create',
  placeCreate: '/places/create',
  restaurantCreate: '/restaurant/create',
};

// Read endpoints
export const getEndpoints = {
  countriesList: '/country/get_all_countries',
  statesList: '/state/get_all_states',
  citiesList: '/city/get_all_cities',
  placesList: '/places/get_all_places',
  restaurantsList: '/restaurant/get_all_restaurants',
};

// Update endpoints
export const updateEndpoints = {
  countryUpdate: '/country/update_country',
  stateUpdate: '/state/update_state',
  cityUpdate: '/city/update_city',
  placeUpdate: '/places/update_place',
  restaurantUpdate: '/restaurant/update_restaurant',
};

// Delete endpoints (some backends use POST for deletes)
export const deleteEndpoints = {
  countryDelete: '/country/delete_country',
  stateDelete: '/state/delete_state',
  cityDelete: '/city/delete_city',
  placeDelete: '/places/delete_place',
  restaurantDelete: '/restaurant/delete_restaurant',
};

// Toggle/Status endpoints
export const toggleEndpoints = {
  countryToggleStatus: '/country/toggle_status',
};

// Utility: build a query string from an object
export function buildQuery(params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && `${v}` !== '');
  return entries.length ? `?${new URLSearchParams(entries).toString()}` : '';
}

// Utility: compose a full URL for a given endpoint key and optional path suffix
// Example: apiUrl('cities') => `${API_BASE_URL}/cities`
//          apiUrl('cities', '/123') => `${API_BASE_URL}/cities/123`
export function apiUrl(key, suffix = '') {
  const base = endpoints[key];
  if (!base) throw new Error(`Unknown endpoint key: ${key}`);
  return `${API_BASE_URL}${base}${suffix}`;
}

// Helper: GET JSON from an absolute or relative path
export async function apiGet(path) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const res = await fetch(url, { method: 'GET' });
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json())?.message || message; } catch (_) { try { message = await res.text(); } catch (_) {} }
    throw new Error(message || `Request failed with ${res.status}`);
  }
  try { return await res.json(); } catch (_) { return null; }
}

// Helper: POST JSON to an absolute or relative path
export async function apiPost(path, data) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data ?? {}),
  });
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json())?.message || message; } catch (_) { try { message = await res.text(); } catch (_) {} }
    throw new Error(message || `Request failed with ${res.status}`);
  }
  try { return await res.json(); } catch (_) { return null; }
}

// Helper: PATCH JSON to an absolute or relative path
export async function apiPatch(path, data) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data ?? {}),
  });
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json())?.message || message; } catch (_) { try { message = await res.text(); } catch (_) {} }
    throw new Error(message || `Request failed with ${res.status}`);
  }
  try { return await res.json(); } catch (_) { return null; }
}

// Helper: PUT JSON to an absolute or relative path
export async function apiPut(path, data) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data ?? {}),
  });
  if (!res.ok) {
    let message = res.statusText;
    try { message = (await res.json())?.message || message; } catch (_) { try { message = await res.text(); } catch (_) {} }
    throw new Error(message || `Request failed with ${res.status}`);
  }
  try { return await res.json(); } catch (_) { return null; }
}

// Example usage (in your components/services):
// import { apiUrl, buildQuery, apiPost, apiGet, createEndpoints, getEndpoints } from '../api/endpoints';
// const res = await fetch(apiUrl('cities') + buildQuery({ page: 1, q: 'mumbai' }));
// const createdCity = await apiPost(createEndpoints.cityCreate, { name: 'New City' });
// const countries = await apiGet(getEndpoints.countriesList);
