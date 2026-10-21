/* Startup: wire navigation/sidebar, initialize dates, load data. Keep last. */
document.querySelectorAll('.snav button').forEach(b => {
  b.onclick = () => switchTab(b.dataset.tab);
});

window.addEventListener('resize', syncSidebarState);
syncSidebarState();

window.addEventListener('keydown', e => {
  if (e.key === 'Escape') toggleMobileSidebar(false);
});

setInterval(() => { $('clock').textContent = new Date().toLocaleString() }, 1000);
if ($('salesDate')) $('salesDate').value = today();
if ($('rDate')) $('rDate').value = today();
if ($('expMonth')) $('expMonth').value = today().slice(0, 7);

async function checkMe() {
  const m = await api('/api/me');
  if (m && m.username) {
    ME = m;
    applyPersona();
  } else {
    location.href = '/login';
  }
}

async function loadAll() {
  loadDash(); loadProducts(); loadSales(); loadStock(); loadInvoices();
  calcRec(); loadRec(); loadPatients(); loadAlerts(); loadSettings();
  loadSmsLog(); loadCredit(); loadExpenses(); loadProfit(); loadTeam();
  loadManage(); loadCustomers(); loadDrugCatalogue();
}

checkMe().then(() => { if (ME.username) loadAll() });
