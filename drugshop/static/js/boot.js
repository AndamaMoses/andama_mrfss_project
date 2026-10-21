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

/* Fallback used only when /api/apps cannot be read. It keeps the old
   fail-open behaviour: navigation stays visible and every loader runs. */
async function loadAll() {
  loadDash(); loadProducts(); loadSales(); loadStock(); loadInvoices();
  calcRec(); loadRec(); loadPatients(); loadAlerts(); loadSettings();
  loadSmsLog(); loadCredit(); loadExpenses(); loadProfit(); loadTeam();
  loadManage(); loadCustomers(); loadDrugCatalogue();
}

/* Load only the endpoint groups this installation is entitled to. This is
   what keeps a normal Core/Pro session free of expected 403s. */
function loadEntitledData() {
  loadDash();

  if (isAppEntitled('pos')) loadSales();

  if (isAppEntitled('inventory')) {
    loadProducts(); loadStock(); loadInvoices(); loadDrugCatalogue();
  }

  if (isAppEntitled('patients')) loadPatients();

  if (isAppEntitled('finance')) {
    calcRec(); loadRec(); loadCredit(); loadExpenses(); loadProfit(); loadCustomers();
  }

  if (isAppEntitled('alerts')) loadAlerts();

  if (ME.role === 'admin') {
    loadSettings(); loadTeam();
  }

  if (isAppEntitled('pos') || isAppEntitled('inventory') || isAppEntitled('patients')) {
    loadManage();
  }
}

async function loadWorkspace() {
  let data;
  try {
    data = await api('/api/apps');
  } catch (e) {
    console.warn('App catalog unavailable; falling back to full loading', e);
    loadAll();
    return;
  }

  try {
    applyApps(data);
  } catch (e) {
    console.error('Could not apply app catalog; keeping navigation visible', e);
    resetAppsGating();
    loadAll();
    return;
  }

  handleUpgradeParam();
  loadEntitledData();
}

checkMe().then(() => { if (ME.username) loadWorkspace() });
