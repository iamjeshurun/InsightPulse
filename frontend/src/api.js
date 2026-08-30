const BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export const api = {
  health: () => request('/health'),
  summary: () => request('/api/v1/analytics/summary'),
  analyses: (product = '') => request(`/api/v1/analyses?limit=500${product ? `&product=${encodeURIComponent(product)}` : ''}`),
  analyze: (record) => request('/api/v1/analyze', { method: 'POST', body: JSON.stringify(record) }),
  batch: (records) => request('/api/v1/analyze/batch', { method: 'POST', body: JSON.stringify({ records }) }),
  feedback: (value) => request('/api/v1/feedback', { method: 'POST', body: JSON.stringify(value) }),
}
