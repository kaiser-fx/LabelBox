/**
 * LabelBox REST API Client
 * Wraps all backend endpoints with automatic JWT management.
 */
const API = (() => {
  const BASE = '';  // Same-origin — served by FastAPI

  // ── Token management ─────────────────────────────────────────────────
  function getToken()  { return localStorage.getItem('labelbox_token'); }
  function setToken(t) { localStorage.setItem('labelbox_token', t); }
  function clearToken() { localStorage.removeItem('labelbox_token'); }
  function isLoggedIn() { return !!getToken(); }

  function authHeaders() {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function request(method, path, { body, isForm } = {}) {
    const headers = { ...authHeaders() };
    const opts = { method, headers };

    if (body && !isForm) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    } else if (body && isForm) {
      opts.body = body; // FormData — browser sets Content-Type automatically
    }

    const res = await fetch(`${BASE}${path}`, opts);

    if (res.status === 401) {
      clearToken();
      throw new Error('Session expired. Please log in again.');
    }

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        detail = err.detail || JSON.stringify(err);
      } catch { /* ignore parse error */ }
      throw new Error(detail);
    }

    return res.json();
  }

  // ── Auth ──────────────────────────────────────────────────────────────
  async function login(email, password) {
    const data = await request('POST', '/auth/login', {
      body: { email, password },
    });
    setToken(data.access_token);
    return data;
  }

  async function getMe() {
    return request('GET', '/auth/me');
  }

  function logout() {
    clearToken();
  }

  // ── Sessions ──────────────────────────────────────────────────────────
  async function createSession(storeName, location) {
    return request('POST', '/sessions', {
      body: { store_name: storeName, location: location || null },
    });
  }

  async function listSessions() {
    return request('GET', '/sessions');
  }

  async function getSession(sessionId) {
    return request('GET', `/sessions/${sessionId}`);
  }

  async function getSessionReport(sessionId) {
    return request('GET', `/sessions/${sessionId}/report`);
  }

  async function downloadSessionReportPdf(sessionId) {
    const response = await fetch(`${BASE}/sessions/${sessionId}/report/pdf`, {
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Could not export the session PDF.');
    return response.blob();
  }

  // ── Scans ─────────────────────────────────────────────────────────────
  async function submitScan(sessionId, imageBlob, capturedAt = null) {
    const formData = new FormData();
    formData.append('file', imageBlob, 'label.jpg');
    if (capturedAt) formData.append('captured_at', capturedAt);
    return request('POST', `/sessions/${sessionId}/scans`, {
      body: formData,
      isForm: true,
    });
  }

  async function getScan(scanId) {
    return request('GET', `/scans/${scanId}`);
  }

  async function listSessionScans(sessionId) {
    return request('GET', `/sessions/${sessionId}/scans`);
  }

  return {
    getToken, setToken, clearToken, isLoggedIn, login, getMe, logout,
    createSession, listSessions, getSession, getSessionReport, downloadSessionReportPdf,
    submitScan, getScan, listSessionScans,
  };
})();
