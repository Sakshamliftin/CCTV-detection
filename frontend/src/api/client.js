/**
 * API client for Store Intelligence backend.
 */
const BASE_URL = '/api/v1';

async function fetchJSON(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${BASE_URL}${url}`, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

export const api = {
  getOccupancy: (storeId) => fetchJSON(`/stores/${storeId}/occupancy`),
  getSummary: (storeId) => fetchJSON(`/stores/${storeId}/summary`),
  getHistorical: (storeId, hours = 24) => fetchJSON(`/stores/${storeId}/historical?hours=${hours}&granularity=hour`),
  getZoneTraffic: (storeId) => fetchJSON(`/stores/${storeId}/zones`),
  getRecentEvents: (limit = 50) => fetchJSON(`/events/recent?limit=${limit}`),
  getAnomalies: (storeId, limit = 20) => fetchJSON(`/stores/${storeId}/anomalies?limit=${limit}`),
  getHealth: () => fetchJSON('/health'),
  
  // Stores API
  getStores: () => fetchJSON('/stores'),
  getStoreDetail: (storeId) => fetchJSON(`/stores/${storeId}`),
  processStore: (storeId) => fetch(`${BASE_URL}/stores/${storeId}/process`, { method: 'POST' }).then(r => r.json()),
  uploadStore: (formData) => fetch(`${BASE_URL}/stores/upload`, { method: 'POST', body: formData }).then(r => r.json()),
  uploadPOS: (storeId, formData) => fetch(`${BASE_URL}/stores/${storeId}/pos`, { method: 'POST', body: formData }).then(r => r.json()),
  updateZones: (storeId, zones) => fetch(`${BASE_URL}/stores/${storeId}/zones`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(zones)
  }).then(r => r.json()),
};
