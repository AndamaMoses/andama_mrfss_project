/* Dashboard tab. */
async function loadDash() {
  const d = await api('/api/dashboard?date=' + today());
  const showPatients = typeof isAppEntitled !== 'function' || isAppEntitled('patients');
  const showFinance = typeof isAppEntitled !== 'function' || isAppEntitled('finance');
  const refillCard = showPatients ? `<div class="card ${d.refill.due_count ? 'warn' : ''}"><h3>Refills Due</h3><div class="v">${d.refill.due_count}</div><small>chronic patients</small></div>` : '';
  const creditCard = showFinance ? `<div class="card ${d.credit_owed_total > 0 ? 'danger' : ''}"><h3>Credit Owed</h3><div class="v">${Math.round(d.credit_owed_total || 0).toLocaleString()}</div><small>UGX outstanding</small></div>` : '';
  $('kpis').innerHTML = `
<div class="card gold"><h3>Sales Today</h3><div class="v">${d.sales_today.total.toLocaleString()}</div><small>UGX · ${d.sales_today.count} sales</small></div>
<div class="card"><h3>Cash / MTN / Airtel</h3><div style="font-weight:800;color:var(--pine-900)">${d.sales_today.by_method.CASH.toLocaleString()} / ${d.sales_today.by_method.MTN_MOMO.toLocaleString()} / ${d.sales_today.by_method.AIRTEL_MOMO.toLocaleString()}</div><small>UGX split</small></div>
<div class="card ${d.low_stock_count ? 'danger' : ''}"><h3>Low Stock</h3><div class="v">${d.low_stock_count}</div><small>items at reorder</small></div>
<div class="card ${d.expiry_counts.expired || d.expiry_counts.critical_30 ? 'danger' : 'warn'}"><h3>Expired / ≤30d</h3><div class="v">${(d.expiry_counts.expired || 0) + (d.expiry_counts.critical_30 || 0)}</div><small>≤60d: ${d.expiry_counts.warning_60 || 0}</small></div>
<div class="card"><h3>Stock Value</h3><div class="v">${Math.round(d.stock_value).toLocaleString()}</div><small>UGX at cost</small></div>
${refillCard}
${creditCard}`;
  $('watch').innerHTML = d.expiry_critical.length ? d.expiry_critical.map(b => `<div class="alert ${b.days_to_expiry < 0 ? 'red' : 'amber'}"><b>${b.product_name}</b> batch ${b.batch_no || ''} — ${b.qty_remaining} left, expires ${b.expiry_date} (${b.days_to_expiry} days)</div>`).join('') : '<div class="alert green">No critical expiries. Good job!</div>';
  $('dashRefill').innerHTML = d.refill.due.length ? d.refill.due.map(p => `<div>• <b>${p.name}</b> (${p.phone}) — ${p.drug_name || ''} due ${p.next_due} <a class="btn wa" style="padding:2px 8px;text-decoration:none" target="_blank" href="${p.whatsapp_link}">WhatsApp</a></div>`).join('') : '<div class="alert green">No refills due today.</div>';
  try {
    const expN = (d.expiry_counts?.expired || 0) + (d.expiry_counts?.critical_30 || 0);
    const bExp = $('badgeStockExpiry'); if (bExp) { bExp.textContent = expN; bExp.style.display = expN > 0 ? '' : 'none' }
    const refN = d.refill?.due_count || 0;
    const bRef = $('badgeRefillCare'); if (bRef) { bRef.textContent = refN; bRef.style.display = refN > 0 ? '' : 'none' }
    const lowN = d.low_stock_count || 0;
    const bAlert = $('badgeStockAlerts'); if (bAlert) { bAlert.textContent = lowN; bAlert.style.display = lowN > 0 ? '' : 'none' }
    const bCred = $('badgeCreditOwed'); if (bCred) { bCred.style.display = (d.credit_owed_total > 0) ? '' : 'none' }
  } catch (e) { console.warn('badge update err', e) }
}
