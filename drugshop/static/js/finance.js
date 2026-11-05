/* Reconciliation, expenses, profit. */
function recAmount(n) {
  return Math.round(Number(n) || 0).toLocaleString();
}

function recAttentionLine(r) {
  const gateway = r.mtn_status ? ' / ' + r.mtn_status : '';
  return `<div class="muted" style="font-size:13px;margin:4px 0">${r.provider} · UGX ${recAmount(r.amount)} · ${r.phone || 'no phone'} · ${r.status}${gateway} · <code>${r.reference}</code></div>`;
}

function renderRecAttention(payments) {
  const el = $('recAttention');
  if (!el) return;
  const unresolved = payments.unresolved || [];
  const orphaned = payments.orphaned || [];
  const blocks = [];
  if (unresolved.length) {
    blocks.push(`<div class="panel-title" style="margin-top:8px">Unresolved prompts (${payments.totals.unresolved_count})</div>`);
    blocks.push(unresolved.map(recAttentionLine).join(''));
    if (payments.unresolved_truncated) blocks.push('<div class="muted">Showing the first 100.</div>');
  }
  if (orphaned.length) {
    blocks.push(`<div class="panel-title" style="margin-top:8px">Orphaned payments (${payments.totals.orphaned_count})</div>`);
    blocks.push(orphaned.map(recAttentionLine).join(''));
    if (payments.orphaned_truncated) blocks.push('<div class="muted">Showing the first 100.</div>');
  }
  el.innerHTML = blocks.join('');
}

async function calcRec() {
  const d = await api('/api/reconciliation/calculate?date=' + $('rDate').value);
  $('recExp').innerHTML = `Expected → Cash: <b>${d.expected_cash.toLocaleString()}</b> · MTN: <b>${d.expected_mtn.toLocaleString()}</b> · Airtel: <b>${d.expected_airtel.toLocaleString()}</b> · Credit: ${d.expected_credit.toLocaleString()}`;
  if (d.payments) {
    const p = d.payments.totals;
    const providers = d.payments.providers || {};
    const breakdown = Object.entries(providers).map(([name, v]) =>
      `${name}: expected ${recAmount(v.expected)} · consumed ${recAmount(v.consumed)} · variance ${recAmount(v.variance)} · orphaned ${v.orphaned_count}`
    ).join('<br>');
    $('recPay').innerHTML = `MoMo ledger → Confirmed: <b>UGX ${recAmount(p.successful)}</b> · Pending: ${recAmount(p.pending)} · Unknown: ${recAmount(p.unknown)} · Unresolved: ${p.unresolved_count} (UGX ${recAmount(p.unresolved_amount)}) · Orphaned: ${p.orphaned_count} (UGX ${recAmount(p.orphaned)}) · Variance: ${recAmount(p.variance)} → <b>${p.status}</b><div class="muted" style="margin-top:6px;font-size:13px">${breakdown}</div>`;
    renderRecAttention(d.payments);
  }
  if (d.saved) $('recMsg').textContent = 'Last saved: ' + d.saved.status;
}

async function closeShift() {
  if (!confirm('Close the shift for ' + $('rDate').value + '? This saves counted balances and a payment snapshot.')) return;
  const btn = $('recCloseBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Closing…'; }
  try {
    const r = await api('/api/reconciliation/close-shift', 'POST', {
      date: $('rDate').value,
      counted_cash: +$('cCash').value,
      counted_mtn: +$('cMtn').value,
      counted_airtel: +$('cAirtel').value,
      notes: $('rNotes').value,
    });
    const v = r.variances || {};
    const diff = ['cash', 'mtn', 'airtel'].map(k => `${k} ${recAmount(v[k])}`).join(' · ');
    $('recMsg').textContent = `✓ Shift closed · ${diff} · payments ${r.payments.totals.status}`;
    await calcRec();
    await loadRec();
  } catch (err) {
    $('recMsg').textContent = '❌ ' + err.message;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Close Shift & Snapshot'; }
  }
}

async function checkPending() {
  const btn = $('recPendingBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }
  $('recMsg').textContent = 'Checking stale pending payments…';
  try {
    const r = await api('/api/reconciliation/sweep', 'POST', { older_than_minutes: 15, limit: 50 });
    const parts = [];
    if (r.updated) parts.push(r.updated + ' updated');
    if (r.unchanged) parts.push(r.unchanged + ' still pending');
    if (r.errors) parts.push(r.errors + ' could not be checked');
    if (r.skipped) parts.push(r.skipped + ' skipped');
    if (!r.checked && !r.skipped && !r.would_check) parts.push('nothing stale');
    $('recMsg').textContent = '✓ Pending check: ' + parts.join(' · ');
    await calcRec();
  } catch (err) {
    $('recMsg').textContent = '❌ ' + err.message;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Check Pending'; }
  }
}

async function saveRec(e) {
  e.preventDefault();
  try {
    const r = await api('/api/reconciliation', 'POST', { rec_date: $('rDate').value, counted_cash: +$('cCash').value, counted_mtn: +$('cMtn').value, counted_airtel: +$('cAirtel').value, notes: $('rNotes').value });
    $('recMsg').textContent = (r.status === 'BALANCED' ? '✓ BALANCED' : '⚠ ' + r.status + ' diff UGX ' + Math.round(r.difference).toLocaleString());
    loadRec(); calcRec();
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
