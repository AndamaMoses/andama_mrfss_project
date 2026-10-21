/* Customers tab. */
async function loadCustomers() {
  try {
    const q = ($('custQ') && $('custQ').value) || '';
    const rows = await api('/api/customers?q=' + encodeURIComponent(q));
    $('custRows').innerHTML = rows.map(c => `<tr><td><b>${c.name || '(no name)'}</b></td><td>${c.phone || '—'}${c.wa_link ? `<br><span class="flex"><a href="tel:+${c.wa_link.replace('https://wa.me/', '')}" style="font-size:12px">Call</a><a target="_blank" href="${c.wa_link}" style="font-size:12px">WhatsApp</a></span>` : ''}</td><td>${c.visits}</td><td>${Math.round(c.total_spent).toLocaleString()}</td><td><b>${Math.round(c.owed).toLocaleString()}</b></td></tr>`).join('') || '<tr><td colspan=5>No customers yet — names & phones are captured at POS.</td></tr>';
  } catch (e) { }
}

async function addCustomer(e) {
  e.preventDefault();
  await api('/api/customers', 'POST', { name: $('ncName').value, phone: $('ncPhone').value, notes: $('ncNotes').value });
  e.target.reset();
  loadCustomers();
}
