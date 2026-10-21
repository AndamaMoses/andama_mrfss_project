/* Credit ledger. */
async function loadCredit() {
  if (typeof isAppEntitled === 'function' && !isAppEntitled('finance')) return;
  try {
    const c = await api('/api/credit');
    $('creditSummary').innerHTML = `<div class="alert ${c.count ? 'red' : 'green'}">${c.count} unpaid credit sale(s) — total owed <b>UGX ${c.total_owed.toLocaleString()}</b></div>`;
    $('creditRows').innerHTML = c.rows.map(r => `<tr><td>${r.sale_date}</td><td>${contactCell(r.customer_name, r.customer_phone)}</td><td>${r.product_name} x${r.qty}</td><td>${r.total.toLocaleString()}</td><td>${r.paid.toLocaleString()}</td><td><b>${r.balance.toLocaleString()}</b></td><td><button class="btn ghost" onclick="payCredit(${r.id},${r.balance})">Record Payment</button></td></tr>`).join('') || '<tr><td colspan=7>Nothing owed</td></tr>';
  } catch (e) { }
}

async function payCredit(id, bal) {
  const a = prompt('Amount received (balance UGX ' + bal.toLocaleString() + ')?');
  if (!a) return;
  try {
    const r = await api('/api/credit/' + id + '/pay', 'POST', { amount: +a });
    alert('Payment recorded. Balance: UGX ' + r.balance.toLocaleString());
    loadCredit(); loadDash();
  } catch (e) { alert('❌ ' + e.message) }
}
