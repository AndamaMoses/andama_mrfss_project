/* Shared display formatters. */
var ROLE_LABEL = { admin: 'Shop Owner', attendant: 'Sales Agent' };

function today() {
  return new Date().toISOString().slice(0, 10);
}

function initials(n) {
  return (n || '?').trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function badge(s) {
  const m = { 'EXPIRED': 'b-expired', 'CRITICAL_30': 'b-critical', 'WARNING_60': 'b-warning', 'OK': 'b-ok' };
  return `<span class="badge ${m[s] || 'b-ok'}">${s.replace('_', ' ')}</span>`;
}

function waNum(p) {
  let d = String(p || '').replace(/\D/g, '');
  if (/^0\d{9}$/.test(d)) d = '256' + d.slice(1);
  return d;
}

function contactCell(name, phone) {
  if (!name && !phone) return '—';
  const d = waNum(phone);
  let s = `<b>${name || ''}</b>` + (phone ? `<br><small>${phone}</small>` : '');
  if (d) s += `<br><span class="flex"><a href="tel:+${d}" style="font-size:12px">Call</a><a target="_blank" href="https://wa.me/${d}" style="font-size:12px">WhatsApp</a></span>`;
  return s;
}
