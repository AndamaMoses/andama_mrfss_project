/* Stock alerts + SMS log. */
window._lowStockAlerts = [];
window._managerPhone = '';

async function loadAlerts() {
  const a = await api('/api/alerts/low-stock');
  window._lowStockAlerts = a.items || [];
  window._managerPhone = a.manager_phone || '';
  if (!a.count) {
    $('alertList').innerHTML = '<div class="alert green">No low-stock items</div>';
    loadSmsLog();
    return;
  }
  $('alertList').innerHTML = a.items.map((it, idx) => {
    const enc = encodeURIComponent(it.sms_text || '');
    return '<div class="alert red"><b>' + it.name + '</b> — ' + it.stock_on_hand + ' left (reorder ' + it.reorder_level + '), suggest order ' + it.suggested_order + '<br><span class="flex" style="margin-top:6px"><button class="btn" onclick="sendAlertSms(' + idx + ')">SMS to Manager</button> <a class="btn wa" style="text-decoration:none" href="sms:?body=' + enc + '">Phone SMS App</a> <a class="btn wa" style="text-decoration:none" target="_blank" href="https://wa.me/?text=' + enc + '">WhatsApp</a></span></div>';
  }).join('');
  loadSmsLog();
}

function sendAlertSms(idx) {
  const it = (window._lowStockAlerts || [])[idx];
  if (!it) return;
  sendSms(window._managerPhone || '', it.sms_text || '');
}

async function sendSms(to, msg) {
  const dest = to || prompt('Manager phone (e.g. 077...)');
  if (!dest) return;
  const r = await api('/api/alerts/send-sms', 'POST', { to: dest, message: msg, channel: 'SMS' });
  alert('SMS status: ' + r.status + '\n' + (r.detail || ''));
  loadSmsLog();
}

async function loadSmsLog() {
  try {
    const rows = await api('/api/alerts/log');
    $('smsRows').innerHTML = rows.map(r => `<tr><td>${r.created_at}</td><td>${r.to_phone}</td><td>${r.channel}</td><td>${r.status}</td><td>${(r.message || '').slice(0, 80)}</td></tr>`).join('');
  } catch (e) { }
}
