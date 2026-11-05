/* Shared DOM + HTTP helpers. Loaded first. */
function $(id) {
  return document.getElementById(id);
}

async function api(u, m, b) {
  const r = await fetch(u, {
    method: m || 'GET',
    headers: b ? { 'Content-Type': 'application/json' } : {},
    body: b ? JSON.stringify(b) : undefined,
  });
  if (r.status === 401) {
    location.href = '/login';
    throw new Error('Please log in');
  }
  const j = await r.json().catch(() => ({}));
  if (r.status === 403 && j.error === 'app not entitled') {
    if (typeof openUpgrade === 'function') openUpgrade(j.app);
    const err = new Error(j.message || 'This app is not included in your plan');
    err.appNotEntitled = true;
    err.status = r.status;
    err.data = j;
    throw err;
  }
  if (!r.ok) {
    const err = new Error(j.error || j.message || 'Error');
    // Keep the response body and status so callers can recover from an
    // ambiguous MoMo outcome (the route still returns a pollable reference).
    err.status = r.status;
    err.data = j;
    throw err;
  }
  return j;
}

async function logout() {
  try { await fetch('/api/logout', { method: 'POST' }); } catch (e) { }
  location.href = '/login';
}

async function switchUser() {
  try { await fetch('/api/logout', { method: 'POST' }); } catch (e) { }
  location.href = '/login';
}
