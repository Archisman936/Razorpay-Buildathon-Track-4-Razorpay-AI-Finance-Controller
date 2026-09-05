/**
 * Centralized API client for Razorpay AI Finance Controller.
 * All requests proxy through Vite's dev server → http://localhost:8000
 */

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData
    ? { ...options.headers }
    : { 'Content-Type': 'application/json', ...options.headers };

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ── Health ─────────────────────────────────────────── */
export const healthApi = {
  get: () => fetch('/health').then(r => r.json()),
  chatHealth: () => request('/chat/health'),
};

/* ── Dashboard ─────────────────────────────────────── */
export const dashboardApi = {
  summary: () => request('/dashboard/summary'),
};

/* ── Reconciliation ────────────────────────────────── */
export const reconciliationApi = {
  run: (sourceType, sourceId, includeMl = true, includeException = true) =>
    request('/reconciliation/run', {
      method: 'POST',
      body: JSON.stringify({
        source_type: sourceType,
        source_id: sourceId,
        include_ml: includeMl,
        include_exception: includeException,
      }),
    }),
};

/* ── Transactions ──────────────────────────────────── */
export const transactionsApi = {
  get: (sourceType, sourceId) =>
    request(`/transactions/${sourceType}/${sourceId}`),
};

/* ── Chat ──────────────────────────────────────────── */
export const chatApi = {
  message: (message, resetConversation = false) =>
    request('/chat/message', {
      method: 'POST',
      body: JSON.stringify({ message, reset_conversation: resetConversation }),
    }),
  reset: () => request('/chat/reset', { method: 'POST' }),
  health: () => request('/chat/health'),
};

/* ── Upload ────────────────────────────────────────── */
export const uploadApi = {
  sourceTypes: () => request('/upload/source-types'),
  uploadFile: (file, sourceType = 'auto_detect') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', sourceType);
    return request('/upload/file', { method: 'POST', body: formData });
  },
};
