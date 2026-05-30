/**
 * API client for Store Intelligence backend.
 */
const BASE_URL = '/api/v1';

async function fetchJSON(url) {
  const response = await fetch(`${BASE_URL}${url}`);
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  getOccupancy: () => fetchJSON('/analytics/occupancy'),
  getSummary: () => fetchJSON('/analytics/summary'),
  getHistorical: (hours = 24) => fetchJSON(`/analytics/historical?hours=${hours}&granularity=hour`),
  getZoneTraffic: () => fetchJSON('/analytics/zones'),
  getRecentEvents: (limit = 50) => fetchJSON(`/events/recent?limit=${limit}`),
  getAnomalies: (limit = 20) => fetchJSON(`/events/anomalies?limit=${limit}`),
  getHealth: () => fetchJSON('/health'),
};
