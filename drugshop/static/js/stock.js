/* Stock tab: drug catalogue, products, batches, supplier invoices. */
let _allDrugs = [];
let _editingDrugId = null;

async function loadDrugCatalogue() {
  if (ME.role !== 'admin') return;
  try {
    const drugs = await api('/api/products');
    _allDrugs = drugs;
    const total = drugs.length;
    const lowCt = drugs.filter(d => d.low_stock).length;
    const totalStock = drugs.reduce((a, d) => a + d.stock_on_hand, 0);
    const totalVal = drugs.reduce((a, d) => a + (d.stock_on_hand * (d.price_buy || 0)), 0);
    if ($('drugStats')) $('drugStats').innerHTML = `
      <div class="dstat"><h4>Total Drugs</h4><div class="dv">${total}</div></div>
      <div class="dstat"><h4>Stock On Hand</h4><div class="dv">${totalStock.toLocaleString()}</div></div>
      <div class="dstat" style="border-top-color:var(--blood)"><h4>Low Stock</h4><div class="dv" style="color:var(--blood)">${lowCt}</div></div>
      <div class="dstat" style="border-top-color:var(--brass)"><h4>Stock Value (Cost)</h4><div class="dv" style="font-size:18px">${Math.round(totalVal).toLocaleString()}<small style="font-size:13px;font-weight:600"> UGX</small></div></div>
    `;
    renderDrugTable(drugs);
  } catch (e) { }
}

function renderDrugTable(drugs) {
  if ($('drugCountBadge')) $('drugCountBadge').textContent = drugs.length + ' drugs';
  if (!drugs.length) { $('drugRows').innerHTML = '<tr><td colspan="10"><div class="drug-empty">💊 No drugs in catalogue yet. Add your first drug above.</div></td></tr>'; return }
  $('drugRows').innerHTML = drugs.map((d, i) => {
    const low = d.low_stock;
    return `<tr>
      <td style="color:var(--muted);font-size:12px">${i + 1}</td>
      <td><b>${d.name}</b></td>
      <td><span class="pill-badge">${d.category || 'General'}</span></td>
      <td>${d.unit || 'tabs'}</td>
      <td>${d.reorder_level}</td>
      <td>${(d.price_buy || 0).toLocaleString()}</td>
      <td style="font-weight:800;color:#1a4d2e">${(d.price_sell || 0).toLocaleString()}</td>
      <td><b>${d.stock_on_hand}</b></td>
      <td>${low ? '<span class="low-badge" style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:11.5px;font-weight:800">⚠ LOW</span>' : '<span class="pill-badge">✓ OK</span>'}</td>
      <td><span style="display:flex;gap:6px">
        <button class="btn-edit" onclick="editDrug(${d.id})">✏️ Edit</button>
        <button class="btn-red" onclick="deleteDrug(${d.id})">🗑 Delete</button>
      </span></td>
    </tr>`;
  }).join('');
}

function filterDrugs() {
  const q = ($('drugSearch') && $('drugSearch').value || '').toLowerCase();
  renderDrugTable(q ? _allDrugs.filter(d => d.name.toLowerCase().includes(q) || ((d.category || '').toLowerCase().includes(q))) : _allDrugs);
}

async function saveDrug(e) {
  e.preventDefault();
  const body = { name: $('dName').value.trim(), category: $('dCat').value || 'General', unit: $('dUnit').value || 'tabs', reorder_level: +$('dReorder').value || 10, price_buy: +$('dBuy').value || 0, price_sell: +$('dSell').value || 0 };
  try {
    if (_editingDrugId) {
      await api('/api/products/' + _editingDrugId, 'PUT', body);
      $('drugMsg').innerHTML = '<span style="color:#2e7d4f">✓ Drug updated successfully!</span>';
      cancelDrugEdit();
    } else {
      await api('/api/products', 'POST', body);
      $('drugMsg').innerHTML = '<span style="color:#2e7d4f">✓ Drug added to catalogue!</span>';
      $('drugForm').reset();
    }
    loadDrugCatalogue(); loadProducts(); loadDash();
  } catch (err) { $('drugMsg').innerHTML = '<span style="color:var(--blood)">❌ ' + err.message + '</span>' }
}

function editDrug(id) {
  const d = _allDrugs.find(x => x.id === id);
  if (!d) return;
  _editingDrugId = id;
  $('dName').value = d.name;
  $('dCat').value = d.category || 'General';
  $('dUnit').value = d.unit || 'tabs';
  $('dReorder').value = d.reorder_level;
  $('dBuy').value = d.price_buy || 0;
  $('dSell').value = d.price_sell || 0;
  $('drugBtn').textContent = '💾 Update Drug';
  $('drugCancel').style.display = '';
  $('drugFormTitle').textContent = 'Edit Drug — ' + d.name;
  $('drugMsg').textContent = '';
  switchTab('drugs');
  $('dName').focus();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function cancelDrugEdit() {
  _editingDrugId = null;
  $('drugForm').reset();
  $('drugBtn').textContent = '➕ Add Drug';
  $('drugCancel').style.display = 'none';
  $('drugFormTitle').textContent = 'Add New Drug / Medicine';
  $('drugMsg').textContent = '';
}

async function deleteDrug(id, name) {
  const d = _allDrugs.find(x => x.id === id);
  const drugName = name || (d ? d.name : 'this drug');
  if (!confirm('Delete "' + drugName + '" from the catalogue?\n\nNote: Cannot delete if stock batches or sales exist for this drug.')) return;
  try {
    await api('/api/products/' + id, 'DELETE');
    $('drugMsg').innerHTML = '<span style="color:var(--blood)">Drug removed from catalogue.</span>';
    loadDrugCatalogue(); loadProducts(); loadDash();
  } catch (e) { alert('❌ ' + e.message) }
}

async function addProduct(e) {
  e.preventDefault();
  const body = { name: $('pName').value, category: $('pCat').value, unit: $('pUnit').value, reorder_level: +$('pReorder').value, price_buy: +$('pBuy').value, price_sell: +$('pSell').value };
  try {
    if (window._editingPid) {
      await api('/api/products/' + window._editingPid, 'PUT', body);
      cancelEditProd();
    } else {
      await api('/api/products', 'POST', body);
      e.target.reset();
    }
    loadProducts(); loadStock(); loadDash(); loadManage();
  } catch (err) { alert('❌ ' + err.message) }
}

function cancelEditProd() {
  window._editingPid = null;
  $('prodBtn').textContent = 'Add';
  $('prodCancel').style.display = 'none';
  $('prodForm').reset();
}

async function editProduct(id) {
  try {
    const p = (await api('/api/products')).find(x => x.id === id);
    if (!p) return;
    window._editingPid = id;
    $('pName').value = p.name;
    $('pCat').value = p.category;
    $('pUnit').value = p.unit;
    $('pReorder').value = p.reorder_level;
    $('pBuy').value = p.price_buy;
    $('pSell').value = p.price_sell;
    $('prodBtn').textContent = 'Update Product';
    $('prodCancel').style.display = '';
    switchTab('stock');
    $('pName').focus();
  } catch (e) { alert('❌ ' + e.message) }
}

async function delProduct(id) {
  if (!confirm('Delete this product? Blocked if stock or sales exist.')) return;
  try {
    await fetch('/api/products/' + id, { method: 'DELETE' }).then(async r => { if (!r.ok) throw new Error((await r.json()).error) });
    loadProducts(); loadStock(); loadDash(); loadManage();
  } catch (e) { alert('❌ ' + e.message) }
}

async function delBatch(id) {
  if (!confirm('Delete this batch?')) return;
  try {
    await fetch('/api/batches/' + id, { method: 'DELETE' }).then(async r => { if (!r.ok) throw new Error((await r.json()).error) });
    loadStock(); loadDash(); loadManage();
  } catch (e) { alert('❌ ' + e.message) }
}

async function addBatch(e) {
  e.preventDefault();
  await api('/api/batches', 'POST', { product_id: $('bProd').value, batch_no: $('bNo').value, qty_received: +$('bQty').value, expiry_date: $('bExp').value, supplier: $('bSup').value, invoice_no: $('bInv').value });
  e.target.reset();
  loadStock(); loadDash();
}

async function loadStock() {
  const s = await api('/api/products');
  $('stockRows').innerHTML = s.map(x => `<tr><td>${x.name}</td><td>${x.stock_on_hand}</td><td>${x.reorder_level}</td><td>${x.price_sell}</td><td>${x.low_stock ? '<span class="badge b-low">LOW</span>' : '<span class="badge b-ok">OK</span>'}</td></tr>`).join('');
  const b = await api('/api/batches');
  $('batchRows').innerHTML = b.map(x => `<tr><td>${x.product_name}</td><td>${x.batch_no}</td><td>${x.qty_remaining}</td><td>${x.expiry_date}</td><td>${badge(x.status)}</td></tr>`).join('');
}

async function loadProducts() {
  const p = await api('/api/products');
  const opts = p.map(x => `<option value="${x.id}">${x.name} (${x.stock_on_hand} ${x.unit}) — UGX ${x.price_sell}</option>`).join('');
  $('sProd').innerHTML = opts;
  $('bProd').innerHTML = p.map(x => `<option value="${x.id}">${x.name}</option>`).join('');
  $('ptDrug').innerHTML = opts;
}

async function uploadInvoice(e) {
  e.preventDefault();
  const fd = new FormData();
  fd.append('invoice_no', $('iNo').value);
  fd.append('supplier', $('iSup').value);
  fd.append('inv_date', $('iDate').value || today());
  fd.append('ocr_text', $('iOcr').value);
  if ($('iPhoto').files[0]) fd.append('photo', $('iPhoto').files[0]);
  await fetch('/api/invoices', { method: 'POST', body: fd });
  e.target.reset();
  loadInvoices();
}

async function loadInvoices() {
  const rows = await api('/api/invoices');
  $('invRows').innerHTML = rows.map(r => `<tr><td>${r.id}</td><td>${r.invoice_no}</td><td>${r.supplier}</td><td>${r.image_name ? `<a target="_blank" href="/uploads/${r.image_name}">photo</a>` : ''}</td><td>${r.status}</td><td><button class="btn ghost" onclick="postInv(${r.id})">Post to Stock</button></td></tr>`).join('');
}

async function postInv(id) {
  const pid = prompt('Enter product_id to post this invoice to (see Stock tab for ids). For multi-item, use API.');
  if (!pid) return;
  const q = prompt('Qty received?');
  const exp = prompt('Expiry date YYYY-MM-DD?');
  const bn = prompt('Batch no?') || '';
  await api('/api/invoices/' + id + '/post', 'POST', { items: [{ product_id: +pid, qty_received: +q, expiry_date: exp, batch_no: bn }] });
  loadInvoices(); loadStock(); loadDash();
}

async function delInvoice2(id) {
  if (!confirm('Delete this invoice record?')) return;
  try {
    await fetch('/api/invoices/' + id, { method: 'DELETE' }).then(async r => { if (!r.ok) throw new Error((await r.json()).error) });
    loadInvoices(); loadManage();
  } catch (e) { alert('❌ ' + e.message) }
}
