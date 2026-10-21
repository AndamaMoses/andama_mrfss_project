/* Owner manage-data tab. */
async function loadManage() {
  if (ME.role !== 'admin') return;
  if (!$('mgDate').value) $('mgDate').value = today();
  const prods = await api('/api/products');
  $('mgProdRows').innerHTML = prods.map(p => `<tr><td><b>${p.name}</b> <small style="color:var(--muted)">${p.category || ''}</small></td><td>${p.stock_on_hand}</td><td>${p.price_sell}</td><td><span class="flex"><button class="btn ghost" onclick="editProduct(${p.id})">Edit</button><button class="btn ghost" onclick="delProduct(${p.id})">Delete</button></span></td></tr>`).join('');
  const batches = await api('/api/batches');
  $('mgBatchRows').innerHTML = batches.map(b => `<tr><td>${b.product_name}</td><td>${b.batch_no || '—'}</td><td>${b.qty_remaining}</td><td>${b.expiry_date}</td><td><button class="btn ghost" onclick="delBatch(${b.id})">Delete</button></td></tr>`).join('') || '<tr><td colspan=5>No batches</td></tr>';
  const sales = await api('/api/sales?date=' + $('mgDate').value);
  $('mgSaleRows').innerHTML = sales.map(s => `<tr><td>${s.id}</td><td>${s.product_name}</td><td>${s.qty}</td><td>${s.total.toLocaleString()}</td><td>${s.payment_method}</td><td>${s.served_by || '—'}</td><td><button class="btn ghost" onclick="voidSale(${s.id})">Void</button></td></tr>`).join('') || '<tr><td colspan=7>No sales that day</td></tr>';
  const pats = await api('/api/patients');
  $('mgPatRows').innerHTML = pats.map(p => `<tr><td>${p.name}</td><td>${p.phone}</td><td>${p.drug_name || '—'}</td><td><button class="btn ghost" onclick="delPatient2(${p.id})">Remove</button></td></tr>`).join('');
  const invs = await api('/api/invoices');
  $('mgInvRows').innerHTML = invs.map(r => `<tr><td>${r.id}</td><td>${r.invoice_no || '—'}</td><td>${r.supplier || '—'}</td><td>${r.status}</td><td><button class="btn ghost" onclick="delInvoice2(${r.id})">Delete</button></td></tr>`).join('') || '<tr><td colspan=5>No invoices</td></tr>';
}
