/* Sell / POS tab: sales, basket, receipts. */
var BASKET = [];
var SALE_BUSY = false;

function posSafeRef(ref) {
  return String(ref || '').replace(/[^A-Za-z0-9_-]/g, '');
}

function setSaleBusy(busy) {
  SALE_BUSY = busy;
  const sell = $('saleBtn');
  if (sell) {
    sell.disabled = busy;
    sell.textContent = busy ? 'Saving…' : 'Sell';
  }
  const basket = $('basketBtn');
  if (basket) {
    basket.disabled = busy;
    basket.textContent = busy ? 'Saving…' : 'Complete Sale + Print';
  }
}

function productPrice(id) {
  const list = (typeof PRODUCTS !== 'undefined' && PRODUCTS) ? PRODUCTS : [];
  const p = list.find(x => String(x.id) === String(id));
  return p ? +p.price_sell : prodPrice(id);
}

function basketTotal() {
  return BASKET.reduce((sum, b) => sum + productPrice(b.product_id) * b.qty, 0);
}

async function makeSale(e) {
  e.preventDefault();
  if (SALE_BUSY || MOMO.busy) return;
  const method = $('sMethod').value;
  const qty = +$('sQty').value || 0;
  const payload = {
    product_id: $('sProd').value, qty, payment_method: method,
    served_by: $('sBy').value || ME.display_name,
    customer_name: $('sCust').value, customer_phone: $('sPhone').value,
    sale_date: $('salesDate').value,
  };
  let momoRef = '';
  const momoProvider = momoMethodProvider(method);
  const manualMomo = !!momoProvider && momoManualMode(method);
  if (manualMomo) {
    const manualError = momoManualReferenceError(momoProvider);
    if (manualError) {
      $('saleMsg').textContent = '❌ ' + manualError;
      if ($('momoManualRef')) $('momoManualRef').focus();
      return;
    }
  }
  setSaleBusy(true);
  try {
    if (momoProvider) {
      if (manualMomo) {
        payload.is_manual_entry = true;
        payload.momo_ref = momoManualReference();
      } else if (momoConfiguredFor(method)) {
        momoRef = await momoReferenceFor(productPrice($('sProd').value) * qty, $('sPhone').value, method);
        payload.momo_ref = momoRef;
      }
    }
    const r = await api('/api/sales', 'POST', payload);
    MOMO_PAID = null;
    if (manualMomo) clearMomoManualReference();
    if (momoRef) setMomoState('ok', 'Sale saved · ' + momoProviderLabel(momoProvider) + ' ' + shortRef(momoRef));
    const receiptRef = posSafeRef(r.receipt_ref);
    const momoDisplay = r.momo_ref
      ? ' · ' + momoProviderLabel(momoProvider) + ' ' + escHtml(String(r.momo_ref).slice(0, 8)) + '…'
      : '';
    $('saleMsg').innerHTML = '✓ Saved. Total UGX ' + r.total.toLocaleString() + momoDisplay +
      ' <button class="btn gold" onclick="printReceiptRef(\'' + receiptRef + '\')">Print Receipt</button>';
    loadSales(); loadDash(); loadStock(); loadCustomers();
  } catch (err) {
    const savedRef = posSafeRef(err.data && err.data.receipt_ref);
    if (err.status === 409) {
      MOMO_PAID = null;
      if (manualMomo) clearMomoManualReference();
      setMomoState('warn', err.message);
      if (savedRef) {
        $('saleMsg').innerHTML = '⚠ Already recorded on receipt <code>' + escHtml(savedRef) + '</code> — the sale was not saved again. <button class="btn gold" onclick="printReceiptRef(\'' + savedRef + '\')">Print Receipt</button>';
        loadSales();
      } else {
        $('saleMsg').textContent = '❌ ' + err.message;
      }
    } else if (momoRef) {
      const paidAmount = err.data && err.data.paid_amount != null
        ? +err.data.paid_amount
        : productPrice($('sProd').value) * qty;
      MOMO_PAID = { ref: momoRef, amount: paidAmount, provider: momoProvider };
      $('saleMsg').textContent = '⚠ ' + err.message + ' — ' + momoProviderLabel(momoProvider) + ' ' + momoRef + ' was paid. Sell again to save it without charging twice.';
    } else if (manualMomo && payload.momo_ref) {
      $('saleMsg').textContent = '⚠ ' + err.message + ' — manual ' + momoProviderLabel(momoProvider) + ' ' + payload.momo_ref + ' was not saved. Correct the sale and try again.';
    } else {
      $('saleMsg').textContent = '❌ ' + err.message;
    }
  } finally {
    setSaleBusy(false);
  }
}

async function loadSales() {
  const rows = await api('/api/sales?date=' + $('salesDate').value);
  $('salesRows').innerHTML = rows.map(s => {
    const ref = posSafeRef(s.receipt_ref);
    return `<tr><td>${escHtml(s.id)}</td><td><code>${escHtml(s.receipt_ref || '—')}</code></td><td>${escHtml(s.product_name)}</td><td>${escHtml(s.qty)}</td><td>${(+s.total || 0).toLocaleString()}</td><td>${escHtml(s.payment_method)}</td><td>${contactCell(s.customer_name, s.customer_phone)}</td><td>${escHtml(s.served_by || '—')}</td><td><button class="btn ghost" onclick="printReceiptRef('${ref}')">Print</button></td></tr>`;
  }).join('') || '<tr><td colspan=9>No sales</td></tr>';
}

function prodName(id) {
  const o = document.querySelector('#sProd option[value="' + id + '"]');
  return o ? o.textContent.split(' (')[0] : ('#' + id);
}

function prodPrice(id) {
  const o = document.querySelector('#sProd option[value="' + id + '"]');
  const m = o ? o.textContent.match(/UGX ([\d,]+)/) : null;
  return m ? +m[1].replace(/,/g, '') : 0;
}

function addToBasket() {
  const id = $('sProd').value, q = +$('sQty').value || 1;
  const ex = BASKET.find(x => x.product_id === id);
  if (ex) ex.qty += q; else BASKET.push({ product_id: id, qty: q });
  renderBasket();
}

function renderBasket() {
  $('basketRows').innerHTML = BASKET.length ? BASKET.map((b, i) => `<tr><td>${escHtml(prodName(b.product_id))}</td><td>${escHtml(b.qty)}</td><td>${(productPrice(b.product_id) * b.qty).toLocaleString()}</td><td><button class="btn ghost" onclick="BASKET.splice(${i},1);renderBasket()">✕</button></td></tr>`).join('') : '<tr><td colspan="4">Empty — add items with + Basket</td></tr>';
}

function clearBasket() {
  BASKET = [];
  renderBasket();
}

async function completeBasket() {
  if (!BASKET.length) { alert('Basket is empty'); return }
  if (SALE_BUSY || MOMO.busy) return;
  const method = $('bMethod').value;
  const total = basketTotal();
  const payload = {
    items: BASKET, payment_method: method,
    served_by: $('bBy').value || $('sBy').value || ME.display_name,
    customer_name: $('bCustomer').value, customer_phone: $('bPhone').value,
    sale_date: $('salesDate').value,
  };
  let momoRef = '';
  const momoProvider = momoMethodProvider(method);
  const manualMomo = !!momoProvider && momoManualMode(method);
  if (manualMomo) {
    const manualError = momoManualReferenceError(momoProvider);
    if (manualError) {
      alert('❌ ' + manualError);
      if ($('momoManualRef')) $('momoManualRef').focus();
      return;
    }
  }
  setSaleBusy(true);
  try {
    if (momoProvider) {
      if (manualMomo) {
        payload.is_manual_entry = true;
        payload.momo_ref = momoManualReference();
      } else if (momoConfiguredFor(method)) {
        momoRef = await momoReferenceFor(total, $('bPhone').value, method);
        payload.momo_ref = momoRef;
      }
    }
    const r = await api('/api/sales/cart', 'POST', payload);
    MOMO_PAID = null;
    if (manualMomo) clearMomoManualReference();
    if (momoRef) setMomoState('ok', 'Sale saved · ' + momoProviderLabel(momoProvider) + ' ' + shortRef(momoRef));
    clearBasket(); loadSales(); loadDash(); loadStock(); loadCredit(); loadCustomers();
    try {
      await printReceiptRef(r.receipt_ref);
    } catch (printErr) {
      alert('The sale was saved, but the receipt could not be printed: ' + printErr.message);
    }
  } catch (e) {
    const savedRef = posSafeRef(e.data && e.data.receipt_ref);
    if (e.status === 409) {
      MOMO_PAID = null;
      if (manualMomo) clearMomoManualReference();
      setMomoState('warn', e.message);
      if (savedRef) {
        alert('⚠ This payment is already recorded on receipt ' + savedRef + '. The basket was not saved again.');
        try { await printReceiptRef(savedRef); } catch (printErr) { /* receipt is optional here */ }
      } else {
        alert('❌ ' + e.message);
      }
    } else if (momoRef) {
      const paidAmount = e.data && e.data.paid_amount != null
        ? +e.data.paid_amount
        : total;
      MOMO_PAID = { ref: momoRef, amount: paidAmount, provider: momoProvider };
      alert('⚠ ' + e.message + '\n\n' + momoProviderLabel(momoProvider) + ' ' + momoRef + ' was paid. Complete the sale again to save it without charging twice.');
    } else if (manualMomo && payload.momo_ref) {
      alert('⚠ ' + e.message + '\n\nManual ' + momoProviderLabel(momoProvider) + ' ' + payload.momo_ref + ' was not saved. Correct the sale and try again.');
    } else {
      alert('❌ ' + e.message);
    }
  } finally {
    setSaleBusy(false);
  }
}

async function printReceiptRef(ref) {
  if (!ref) return;
  const r = await api('/api/receipts/' + encodeURIComponent(ref));
  const lines = (r.lines || []).map(l => `<tr><td>${escHtml(l.product_name)} x${escHtml(l.qty)}</td><td style="text-align:right">${(+l.total || 0).toLocaleString()}</td></tr>`).join('');
  const customer = r.customer_name
    ? '<p>Customer: ' + escHtml(r.customer_name) + (r.customer_phone ? ' · ' + escHtml(r.customer_phone) : '') + '</p>'
    : '';
  $('receiptBox').innerHTML = `<h3>${escHtml(r.shop_name)}</h3><p>${escHtml(r.shop_branch)} · ${escHtml(r.shop_phone)}</p><p>Receipt ${escHtml(r.receipt_no)} · ${escHtml(r.sale_date)}</p>${customer}<hr><table>${lines}</table><hr><p>${escHtml(r.payment_method)} · Served by: ${escHtml(r.served_by || '-')}</p>${r.momo_ref ? '<p>MoMo ref: ' + escHtml(r.momo_ref) + '</p>' : ''}<p><b>Total: UGX ${(+r.total || 0).toLocaleString()}</b></p><p>${escHtml(r.footer)}</p>`;
  window.print();
}

async function printDayReport() {
  const d = await api('/api/sales/day-report?date=' + $('salesDate').value);
  const rows = (d.rows || []).map(x => `<div>${escHtml(x.product_name)} x${escHtml(x.qty)} — ${(+x.total || 0).toLocaleString()} (${escHtml(x.payment_method)})</div>`).join('');
  $('receiptBox').innerHTML = `<h3>${escHtml(d.shop_name)} — Z-REPORT</h3><p>${escHtml(d.date)}</p><hr>` + rows + `<hr><p><b>Total: UGX ${(+d.summary.total || 0).toLocaleString()} (${escHtml(d.summary.count)} sales)</b></p><p>Cash ${(+d.summary.by_method.CASH || 0).toLocaleString()} · MTN ${(+d.summary.by_method.MTN_MOMO || 0).toLocaleString()} · Airtel ${(+d.summary.by_method.AIRTEL_MOMO || 0).toLocaleString()}</p>`;
  window.print();
}

async function voidSale(id) {
  if (!confirm('Void sale #' + id + '? Stock goes back on shelf.')) return;
  try {
    await fetch('/api/sales/' + id, { method: 'DELETE' }).then(async r => { if (!r.ok) throw new Error((await r.json()).error) });
    loadSales(); loadStock(); loadDash(); loadCredit(); loadManage();
  } catch (e) { alert('❌ ' + e.message) }
}
