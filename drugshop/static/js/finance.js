/* Reconciliation, expenses, profit. */
async function calcRec() {
  const d = await api('/api/reconciliation/calculate?date=' + $('rDate').value);
  $('recExp').innerHTML = `Expected → Cash: <b>${d.expected_cash.toLocaleString()}</b> · MTN: <b>${d.expected_mtn.toLocaleString()}</b> · Airtel: <b>${d.expected_airtel.toLocaleString()}</b> · Credit: ${d.expected_credit.toLocaleString()}`;
  if (d.saved) $('recMsg').textContent = 'Last saved: ' + d.saved.status;
}

async function saveRec(e) {
  e.preventDefault();
  try {
    const r = await api('/api/reconciliation', 'POST', { rec_date: $('rDate').value, counted_cash: +$('cCash').value, counted_mtn: +$('cMtn').value, counted_airtel: +$('cAirtel').value, notes: $('rNotes').value });
    $('recMsg').textContent = (r.status === 'BALANCED' ? '✓ BALANCED' : '⚠ ' + r.status + ' diff UGX ' + Math.round(r.difference).toLocaleString());
    loadRec();
  } catch (err) { $('recMsg').textContent = '❌ ' + err.message }
}

async function loadRec() {
  const rows = await api('/api/reconciliation');
  const admin = ME.role === 'admin';
  $('recRows').innerHTML = rows.map(r => `<tr><td>${r.rec_date}</td><td>${r.expected_cash}/${r.expected_mtn}/${r.expected_airtel}</td><td>${r.counted_cash}/${r.counted_mtn}/${r.counted_airtel}</td><td>${r.status}${admin ? ` <button class="btn ghost" style="padding:2px 8px" onclick="delRec('${r.rec_date}')">✕</button>` : ''}</td></tr>`).join('');
}

async function delRec(date) {
  if (!confirm('Delete reconciliation for ' + date + '? Day reopens.')) return;
  await fetch('/api/reconciliation/' + date, { method: 'DELETE' });
  loadRec(); calcRec();
}

async function loadExpenses() {
  const m = $('expMonth').value || today().slice(0, 7);
  const rows = await api('/api/expenses?month=' + m);
  const canDel = ME.role === 'admin';
  $('expRows').innerHTML = rows.map(r => `<tr><td>${r.exp_date}</td><td>${r.description}</td><td>${r.category}</td><td>${r.amount.toLocaleString()}</td><td>${canDel ? `<button class="btn ghost" onclick="delExpense(${r.id})">✕</button>` : ''}</td></tr>`).join('') || '<tr><td colspan=5>No expenses</td></tr>';
}

async function addExpense(e) {
  e.preventDefault();
  await api('/api/expenses', 'POST', { description: $('eDesc').value, category: $('eCat').value, amount: +$('eAmt').value, exp_date: $('eDate').value || today() });
  e.target.reset();
  loadExpenses(); loadProfit();
}

async function delExpense(id) {
  if (confirm('Delete expense?')) {
    await fetch('/api/expenses/' + id, { method: 'DELETE' });
    loadExpenses(); loadProfit();
  }
}

async function loadProfit() {
  try {
    const p = await api('/api/profit?date=' + $('salesDate').value);
    $('profitBox').innerHTML = `Revenue (cash/MoMo): <b>UGX ${p.revenue_cash_momo.toLocaleString()}</b> · Credit given: ${p.credit_given.toLocaleString()} · Stock cost: ${Math.round(p.cogs_approx).toLocaleString()} · Expenses: ${p.expenses.toLocaleString()} → <b>Profit ≈ UGX ${p.profit_approx.toLocaleString()}</b>`;
  } catch (e) { }
}
