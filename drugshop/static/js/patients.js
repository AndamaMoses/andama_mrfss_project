/* Refill care tab. */
async function addPatient(e) {
  e.preventDefault();
  await api('/api/patients', 'POST', { name: $('ptName').value, phone: $('ptPhone').value, product_id: $('ptDrug').value || null, last_refill_date: $('ptLast').value, cycle_days: +$('ptCycle').value || 30 });
  e.target.reset();
  loadPatients(); loadDash();
}

async function loadPatients() {
  const r = await api('/api/reminders');
  const card = p => `<div class="alert ${p.state === 'OVERDUE' ? 'red' : p.state === 'DUE_SOON' ? 'amber' : 'green'}"><b>${p.name}</b> ${p.phone} — ${p.drug_name || ''}<br>Last: ${p.last_refill_date} · Due: ${p.next_due} (${p.days_left}d) · <b>${p.state}</b><br><span class="flex"><a class="btn wa" style="text-decoration:none" target="_blank" href="${p.whatsapp_link}">WhatsApp Remind</a><button class="btn" onclick="refilled(${p.id})">Mark Refilled</button></span></div>`;
  $('remList').innerHTML = '<h3>Due now (' + r.due.length + ')</h3>' + (r.due.map(card).join('') || 'none') + '<h3>Upcoming (' + r.upcoming.length + ')</h3>' + (r.upcoming.map(card).join('') || 'none') + '<h3>OK (' + r.ok.length + ')</h3>' + (r.ok.map(card).join('') || 'none');
}

async function refilled(id) {
  await api('/api/patients/' + id, 'POST', {});
  loadPatients(); loadDash();
}

async function delPatient2(id) {
  if (!confirm('Remove this patient from refill care?')) return;
  try {
    await fetch('/api/patients/' + id, { method: 'DELETE' }).then(async r => { if (!r.ok) throw new Error((await r.json()).error) });
    loadPatients(); loadDash(); loadManage();
  } catch (e) { alert('❌ ' + e.message) }
}
