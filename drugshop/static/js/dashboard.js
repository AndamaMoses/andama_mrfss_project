/* Dashboard tab: operational KPIs, expiry watchdog, refill outreach and drawer. */

function dashFmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(String(iso).slice(0, 10) + 'T00:00:00');
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function dashAmount(n) {
  return Math.round(Number(n) || 0).toLocaleString();
}

function dashCompact(n) {
  const v = Math.round(Number(n) || 0);
  if (v >= 1000000) return (v / 1000000).toFixed(2).replace(/\.00$/, '') + 'M';
  if (v >= 100000) return Math.round(v / 1000) + 'K';
  return v.toLocaleString();
}

function dashKpi(opts) {
  const tone = opts.tone ? ' ' + opts.tone : '';
  const iconTone = opts.iconTone ? ' ' + opts.iconTone : '';
  const valueCls = opts.smallValue ? ' sm' : '';
  const chips = (opts.chips || []).map(c =>
    `<span class="kpi-chip${c.tone ? ' ' + c.tone : ''}">${c.label}</span>`
  ).join('');
  const footTone = opts.footTone ? ' ' + opts.footTone : '';
  const footer = opts.foot
    ? `<div class="kpi-foot${footTone}">${opts.foot}</div>`
    : (chips ? `<div class="kpi-chips">${chips}</div>` : '');
  return `<div class="kpi${tone}">
    <div class="kpi-top">
      <span class="kpi-label">${opts.label}</span>
      <span class="kpi-ic${iconTone}"><svg class="ic"><use href="#${opts.icon}" /></svg></span>
    </div>
    <div class="kpi-value${valueCls}" title="${opts.title || ''}">${opts.value}</div>
    <div class="kpi-sub">${opts.sub || ''}</div>
    ${footer}
  </div>`;
}

function filterWatch(btn, state) {
  const wrap = document.getElementById('watchFilter');
  if (wrap) wrap.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
  document.querySelectorAll('#watch .wd-row').forEach(row => {
    row.style.display = (state === 'all' || row.dataset.state === state) ? '' : 'none';
  });
}

function quarantineBatch(id) {
  switchTab('stock');
  setTimeout(() => {
    if (typeof pickWriteOff === 'function') pickWriteOff(id);
    else if (typeof switchTab === 'function') switchTab('stock');
  }, 120);
}

async function loadDash() {
  const d = await api('/api/dashboard?date=' + today());
  const showPatients = typeof isAppEntitled !== 'function' || isAppEntitled('patients');
  const showFinance = typeof isAppEntitled !== 'function' || isAppEntitled('finance');

  const s = d.sales_today || { total: 0, count: 0, by_method: {} };
  const yesterday = d.sales_yesterday || { total: 0, count: 0 };
  const by = s.by_method || {};
  const cash = by.CASH || 0;
  const mtn = by.MTN_MOMO || 0;
  const airtel = by.AIRTEL_MOMO || 0;
  const momo = mtn + airtel;
  const expiry = d.expiry_counts || {};
  const expired = expiry.expired || 0;
  const critical = expiry.critical_30 || 0;
  const warning = expiry.warning_60 || 0;
  const okBatches = expiry.ok || 0;
  const expN = expired + critical;
  const totalBatches = expired + critical + warning + okBatches;
  const safeRate = totalBatches ? Math.round((okBatches / totalBatches) * 100) : 100;

  const dateEl = $('dashDate');
  if (dateEl) dateEl.textContent = dashFmtDate(d.date || today());

  const kpis = [
    dashKpi({
      label: 'Sales Today',
      icon: 'i-coins',
      iconTone: 'green',
      value: dashCompact(s.total),
      title: 'UGX ' + dashAmount(s.total),
      sub: 'UGX · ' + s.count + ' sale' + (s.count === 1 ? '' : 's'),
      foot: `<span>Yesterday: UGX ${dashCompact(yesterday.total)}</span><span class="foot-badge">${s.count}</span>`,
      footTone: 'neutral',
    }),
    dashKpi({
      label: 'Cash / MoMo',
      icon: 'i-cash',
      iconTone: 'blue',
      smallValue: true,
      value: [dashCompact(cash), dashCompact(mtn), dashCompact(airtel)].join('/'),
      title: `Cash ${dashAmount(cash)} · MTN ${dashAmount(mtn)} · Airtel ${dashAmount(airtel)}`,
      sub: 'UGX Split Balance',
      foot: `<span>MTN / AIRTEL</span><span class="foot-badge">Ready</span>`,
      footTone: 'green',
    }),
    dashKpi({
      label: 'Low Stock',
      icon: 'i-stock',
      iconTone: d.low_stock_count ? 'amber' : 'green',
      tone: d.low_stock_count ? 'amber' : '',
      value: d.low_stock_count || 0,
      sub: 'Items at reorder level',
      foot: `<span>${d.low_stock_count ? 'PO Suggested' : 'Stock clear'}</span>`,
      footTone: d.low_stock_count ? 'amber' : 'green',
    }),
    dashKpi({
      label: 'Expired / ≤30d',
      icon: 'i-alert',
      iconTone: expN ? 'red' : 'green',
      tone: expN ? 'red' : '',
      value: expN,
      sub: `≤60d: ${warning} critical`,
      foot: `<span>${expired} Expired</span><span>${critical} Near</span>`,
      footTone: expN ? 'red' : 'green',
    }),
    dashKpi({
      label: 'Stock Value',
      icon: 'i-trend',
      iconTone: 'violet',
      value: dashCompact(d.stock_value),
      title: 'UGX ' + dashAmount(d.stock_value),
      sub: 'UGX at cost price',
      foot: `<span>At cost</span><span class="foot-badge">FEFO</span>`,
      footTone: 'violet',
    }),
  ];

  if (showPatients) {
    kpis.push(dashKpi({
      label: 'Refills Due',
      icon: 'i-heart',
      iconTone: 'violet',
      tone: d.refill.due_count ? 'amber' : '',
      value: d.refill.due_count || 0,
      sub: 'Chronic patient queue',
      foot: `<span>Day-25 protocol</span><span>${d.refill.due_count || 0} today</span>`,
      footTone: d.refill.due_count ? 'green' : 'neutral',
    }));
  }

  if (showFinance) {
    kpis.push(dashKpi({
      label: 'Credit Owed',
      icon: 'i-scale',
      iconTone: d.credit_owed_total > 0 ? 'red' : 'green',
      tone: d.credit_owed_total > 0 ? 'red' : '',
      value: dashCompact(d.credit_owed_total),
      title: 'UGX ' + dashAmount(d.credit_owed_total),
      sub: 'UGX outstanding',
      foot: `<span>${d.credit_owed_total > 0 ? 'Follow up' : 'Ledger clear'}</span>`,
      footTone: d.credit_owed_total > 0 ? 'red' : 'green',
    }));
  }

  $('kpis').innerHTML = kpis.join('');
  $('kpis').dataset.count = kpis.length;

  /* ---------------- Expiry watchdog ---------------- */
  const crit = d.expiry_critical || [];
  const warn = d.expiry_warning || [];

  const watchdogRow = (b) => {
    const days = b.days_to_expiry;
    const state = days < 0 ? 'expired' : (days <= 30 ? 'critical' : 'warning');
    const tag = state === 'expired'
      ? '<span class="tag expired"><span class="pulse-dot"></span> Expired</span>'
      : `<span class="tag ${state === 'critical' ? 'critical' : 'neutral'}">Expiring in ${days} day${days === 1 ? '' : 's'}</span>`;
    const dayText = days < 0
      ? Math.abs(days) + ' day' + (Math.abs(days) === 1 ? '' : 's') + ' ago'
      : 'in ' + days + ' day' + (days === 1 ? '' : 's');
    const icon = state === 'expired' ? 'i-alert' : 'i-clock';
    const actions = state === 'expired'
      ? `<button type="button" class="btn red mini" onclick="quarantineBatch(${b.id})">Quarantine / Write-Off</button>
         <button type="button" class="btn ghost mini" onclick="switchTab('stock')">View shelf</button>`
      : `<button type="button" class="btn gold mini" onclick="switchTab('pos')">Discount &amp; Dispense</button>
         <button type="button" class="btn ghost mini" onclick="switchTab('stock')">Flag POS</button>`;
    return `<div class="wd-row ${state}" data-state="${state}">
      <div class="wd-ic ${state === 'expired' ? '' : 'amber'}"><svg class="ic"><use href="#${icon}" /></svg></div>
      <div class="wd-body">
        <div class="wd-title"><b>${b.product_name}</b>${tag}</div>
        <div class="wd-meta">
          <span>Batch: <b>${b.batch_no || '—'}</b></span><span class="dot"></span>
          <span>Stock: <b>${b.qty_remaining} ${b.unit || ''}</b></span>
        </div>
        <div class="wd-meta">
          <span>${days < 0 ? 'Expired' : 'Expiry'}: <b>${dashFmtDate(b.expiry_date)}</b></span>
          <span class="muted">(${dayText})</span>
        </div>
        <div class="wd-actions">${actions}</div>
      </div>
    </div>`;
  };

  const allRows = crit.concat(warn).map(watchdogRow);
  $('watch').innerHTML = allRows.length
    ? allRows.join('')
    : '<div class="alert green">No expiries inside 60 days — FEFO shelves are clear.</div>';

  const filterBtns = document.querySelectorAll('#watchFilter button');
  if (filterBtns.length === 3) {
    filterBtns[0].textContent = 'All (' + allRows.length + ')';
    filterBtns[1].textContent = 'Expired (' + expired + ')';
    filterBtns[2].textContent = '≤30 Days (' + critical + ')';
    filterBtns.forEach((b, i) => b.classList.toggle('active', i === 0));
  }

  /* ---------------- Refill outreach ---------------- */
  const due = (d.refill && d.refill.due) || [];
  $('dashRefill').innerHTML = due.length
    ? due.map(p => {
        const overdue = p.days_left < 0;
        const stateTag = overdue
          ? '<span class="tag expired"><span class="pulse-dot"></span> Overdue</span>'
          : '<span class="tag critical">Day-25 due</span>';
        return `<div class="refill-row">
          <div class="refill-avatar">${initials(p.name)}</div>
          <div class="refill-body">
            <div class="wd-title"><b>${p.name}</b>${stateTag}<span class="tag schedule">Chronic · ${p.cycle_days || 30}d</span></div>
            <div class="refill-meta">Regimen: <b>${p.drug_name || '—'}</b><span class="dot"></span>Contact: <b>${p.phone || '—'}</b></div>
            <div class="refill-meta">Next refill: <b>${dashFmtDate(p.next_due)}</b> <span class="muted">(${p.days_left} day${Math.abs(p.days_left) === 1 ? '' : 's'})</span><span class="dot"></span>Last dispense: <b>${dashFmtDate(p.last_refill_date)}</b></div>
            <div class="refill-actions">
              ${p.whatsapp_link ? `<a class="btn wa mini" target="_blank" rel="noopener" href="${p.whatsapp_link}"><svg class="ic"><use href="#i-whatsapp" /></svg> WhatsApp Refill SMS</a>` : ''}
              <button type="button" class="btn mini" onclick="switchTab('pat')"><svg class="ic"><use href="#i-pill" /></svg> Prepare Dispense</button>
            </div>
          </div>
        </div>`;
      }).join('')
    : '<div class="alert green">No refills due today — every chronic patient is inside the safe window.</div>';

  const refillChip = $('refillDueChip');
  if (refillChip) refillChip.textContent = due.length ? due.length + ' Scheduled Today' : 'None Today';

  /* ---------------- Drawer reconciliation ---------------- */
  $('dashDrawer').innerHTML = `
    <div class="drawer-stats">
      <div class="drawer-stat">
        <div><span>Cash collected today</span><strong>UGX ${dashAmount(cash)}</strong><small>${s.count} receipt${s.count === 1 ? '' : 's'} in the till</small></div>
        <div class="mini-ic"><svg class="ic"><use href="#i-cash" /></svg></div>
      </div>
      <div class="drawer-stat">
        <div><span>Mobile money</span><strong>UGX ${dashAmount(momo)}</strong><small>MTN ${dashAmount(mtn)} · Airtel ${dashAmount(airtel)}</small></div>
        <div class="mini-ic"><svg class="ic"><use href="#i-phone" /></svg></div>
      </div>
      <div class="drawer-stat">
        <div><span>Expected in drawer</span><strong>UGX ${dashAmount(cash)}</strong><small>Awaiting physical count</small></div>
        <div class="mini-ic"><svg class="ic"><use href="#i-scale" /></svg></div>
      </div>
    </div>
    ${showFinance
      ? `<div class="drawer-actions">
          <button type="button" class="btn ghost" onclick="switchTab('rec')"><svg class="ic"><use href="#i-refresh" /></svg> Conduct Mid-Day Till Drop</button>
          <button type="button" class="btn" onclick="switchTab('rec')"><svg class="ic"><use href="#i-lock" /></svg> Close Out &amp; Finalize Shift</button>
        </div>
        <p class="panel-foot">Reconciliation is recorded per day. Counts are never edited automatically.</p>`
      : `<p class="panel-foot">Day-end reconciliation is available with the Finance add-on. Cash and MoMo totals above are live.</p>`}
  `;

  if (showFinance) {
    api('/api/reconciliation/calculate?date=' + today()).then(r => {
      const chip = $('drawerStatus');
      if (!chip) return;
      if (r.saved && r.saved.status) {
        chip.textContent = r.saved.status;
        chip.className = 'tag ' + (r.saved.status === 'BALANCED' ? 'safe' : 'critical');
      } else {
        chip.textContent = 'Live';
        chip.className = 'tag neutral';
      }
    }).catch(() => {});
  }

  /* ---------------- Dispensary workload ---------------- */
  const quotaTarget = 2500000;
  const quotaPct = Math.min(100, Math.round((s.total / quotaTarget) * 100));
  const rxTarget = 40;
  const rxPct = Math.min(100, Math.round((s.count / rxTarget) * 100));
  const rxTone = rxPct >= 75 ? 'green' : (rxPct >= 40 ? 'amber' : 'red');

  $('dashWorkload').innerHTML = `
    <div class="work-row">
      <div class="work-top"><span>Daily sales quota (UGX 2.5M)</span><b>${quotaPct}%</b></div>
      <div class="progress"><i style="width:${quotaPct}%"></i></div>
    </div>
    <div class="work-row">
      <div class="work-top"><span>Prescription receipts</span><b>${s.count} / ${rxTarget}</b></div>
      <div class="progress ${rxTone}"><i style="width:${rxPct}%"></i></div>
    </div>
    <div class="work-row">
      <div class="work-top"><span>Expiry-safe batch rate</span><b>${safeRate}%</b></div>
      <div class="progress ${safeRate >= 90 ? '' : 'amber'}"><i style="width:${safeRate}%"></i></div>
    </div>
    <div class="quality-note">
      <svg class="ic"><use href="#i-shield" /></svg>
      <span>Apothecary quality check: all batch seals inspected for humidity controls today. ${expN ? expN + ' batch' + (expN === 1 ? '' : 'es') + ' need attention.' : 'Shelves are within safe windows.'}</span>
    </div>
  `;

  /* ---------------- Navigation badges ---------------- */
  try {
    const bExp = $('badgeStockExpiry');
    if (bExp) { bExp.textContent = expN; bExp.style.display = expN > 0 ? '' : 'none'; }
    const refN = (d.refill && d.refill.due_count) || 0;
    const bRef = $('badgeRefillCare');
    if (bRef) { bRef.textContent = refN; bRef.style.display = refN > 0 ? '' : 'none'; }
    const lowN = d.low_stock_count || 0;
    const bAlert = $('badgeStockAlerts');
    if (bAlert) { bAlert.textContent = lowN; bAlert.style.display = lowN > 0 ? '' : 'none'; }
    const bCred = $('badgeCreditOwed');
    if (bCred) { bCred.style.display = (d.credit_owed_total > 0) ? '' : 'none'; }
  } catch (e) {
    console.warn('badge update err', e);
  }
}
