/* Sell / POS tab: sales, basket, receipts. */
var BASKET = [];

async function makeSale(e) {
  e.preventDefault();
  try {
    const r = await api('/api/sales', 'POST', { product_id: $('sProd').value, qty: +$('sQty').value, payment_method: $('sMethod').value, served_by: $('sBy').value || ME.display_name, customer_name: $('sCust').value, customer_phone: $('sPhone').value, sale_date: $('salesDate').value });
    $('saleMsg').innerHTML = '✓ Saved. Total UGX ' + r.total.toLocaleString() + ' <button class="btn gold" onclick="printReceiptRef(\'' + r.receipt_ref + '\')">Print Receipt</button>';
    loadSales(); loadDash(); loadStock(); loadCustomers();
  } catch (err) { $('saleMsg').textContent = '❌ ' + err.message }
}

async function loadSales() {
  const rows = await api('/api/sales?date=' + $('salesDate').value);
  $('salesRows').innerHTML = rows.map(s => `<tr><td>${s.id}</td><td>${s.product_name}</td><td>${s.qty}</td><td>${s.total.toLocaleString()}</td><td>${s.payment_method}</td><td>${contactCell(s.customer_name, s.customer_phone)}</td><td><button class="btn ghost" onclick="printReceiptRef('${s.receipt_ref || ''}')">Print</button></td></tr>`).join('') || '<tr><td colspan=7>No sales</td></tr>';
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
  $('basketRows').innerHTML = BASKET.length ? BASKET.map((b, i) => `<tr><td>${prodName(b.product_id)}</td><td>${b.qty}</td><td>${(prodPrice(b.product_id) * b.qty).toLocaleString()}</td><td><button class="btn ghost" onclick="BASKET.splice(${i},1);renderBasket()">✕</button></td></tr>`).join('') : '<tr><td colspan="4">Empty — add items with + Basket</td></tr>';
}

function clearBasket() {
  BASKET = [];
  renderBasket();
}

async function completeBasket() {
  if (!BASKET.length) { alert('Basket is empty'); return }
  try {
    const r = await api('/api/sales/cart', 'POST', { items: BASKET, payment_method: $('bMethod').value, served_by: $('bBy').value || $('sBy').value || ME.display_name, customer_name: $('bCustomer').value, customer_phone: $('bPhone').value, sale_date: $('salesDate').value });
    clearBasket(); loadSales(); loadDash(); loadStock(); loadCredit(); loadCustomers();
    printReceiptRef(r.receipt_ref);
  } catch (e) { alert('❌ ' + e.message) }
}

async function printReceiptRef(ref) {
  if (!ref) return;
  const r = await api('/api/receipts/' + ref);
  const lines = r.lines.map(l => `<tr><td>${l.product_name} x${l.qty}</td><td style="text-align:right">${l.total.toLocaleString()}</td></tr>`).join('');
  $('receiptBox').innerHTML = `<h3>${r.shop_name}</h3><p>${r.shop_branch} · ${r.shop_phone}</p><p>Receipt ${r.receipt_no} · ${r.sale_date}</p>${r.customer_name ? '<p>Customer: ' + r.customer_name + (r.customer_phone ? ' · ' + r.customer_phone : '') + '</p>' : ''}<hr><table>${lines}</table><hr><p>${r.payment_method} · Served by: ${r.served_by || '-'}</p><p><b>Total: UGX ${r.total.toLocaleString()}</b></p><p>${r.footer}</p>`;
  window.print();
}

async function printDayReport() {
  const d = await api('/api/sales/day-report?date=' + $('salesDate').value);
  $('receiptBox').innerHTML = `<h3>${d.shop_name} — Z-REPORT</h3><p>${d.date}</p><hr>` + d.rows.map(x => `<div>${x.product_name} x${x.qty} — ${x.total.toLocaleString()} (${x.payment_method})</div>`).join('') + `<hr><p><b>Total: UGX ${d.summary.total.toLocaleString()} (${d.summary.count} sales)</b></p><p>Cash ${d.summary.by_method.CASH} · MTN ${d.summary.by_method.MTN_MOMO} · Airtel ${d.summary.by_method.AIRTEL_MOMO}</p>`;
  window.print();
}

async function voidSale(id) {
  if (!confirm('Void sale #' + id + '? Stock goes back on shelf.')) return;
  try {
    await fetch('/api/sales/' + id, { method: 'DELETE' }).then(async r => { if (!r.ok) throw new Error((await r.json()).error) });
    loadSales(); loadStock(); loadDash(); loadCredit(); loadManage();
  } catch (e) { alert('❌ ' + e.message) }
}
