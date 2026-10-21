/* Staff/team management. */
async function addUser(e) {
  e.preventDefault();
  try {
    await api('/api/users', 'POST', { username: $('nuName').value, password: $('nuPass').value, display_name: $('nuDisp').value || $('nuName').value, role: $('nuRole').value });
    $('userMsg').textContent = 'Staff added ✓';
    e.target.reset();
    loadTeam();
  } catch (e) { $('userMsg').textContent = '❌ ' + e.message }
}

async function loadTeam() {
  try {
    const rows = await api('/api/users');
    $('teamRows').innerHTML = rows.map(r => `<tr><td><b>${r.display_name || r.username}</b></td><td>${r.username}</td><td><span class="rolebadge ${r.role}">${ROLE_LABEL[r.role] || r.role}</span></td><td>${r.phone || '—'}</td><td>${r.username !== ME.username ? `<button class="btn ghost" onclick="delUser(${r.id},'${r.username}')">Remove</button>` : '<small style="color:var(--muted)">you</small>'}</td></tr>`).join('');
  } catch (e) { }
  loadActivity();
}

async function loadActivity() {
  if (typeof isAppEntitled === 'function' && !isAppEntitled('finance')) return;
  try {
    const a = await api('/api/staff-activity?date=' + $('salesDate').value);
    $('shiftBox').innerHTML = a.sales_by_staff.length ? '<table><thead><tr><th>Staff</th><th>Sales</th><th>Revenue UGX</th></tr></thead><tbody>' + a.sales_by_staff.map(s => `<tr><td>${s.staff}</td><td>${s.sales}</td><td>${Math.round(s.revenue).toLocaleString()}</td></tr>`).join('') + '</tbody></table>' : '<div class="alert green">No sales recorded yet today.</div>';
    $('loginRows').innerHTML = a.recent_logins.map(l => `<tr><td>${l.name} <small style="color:var(--muted)">(${l.username})</small></td><td>${l.login_at}</td><td>${l.ip || '—'}</td></tr>`).join('') || '<tr><td colspan=3>No sign-ins yet</td></tr>';
  } catch (e) { }
}

async function delUser(id, name) {
  if (!confirm('Remove staff account "' + name + '"?')) return;
  try {
    await api('/api/users/' + id, 'DELETE');
    loadTeam();
  } catch (e) { alert('❌ ' + e.message) }
}
