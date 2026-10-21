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
    throw err;
  }
  if (!r.ok) throw new Error(j.error || 'Error');
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
