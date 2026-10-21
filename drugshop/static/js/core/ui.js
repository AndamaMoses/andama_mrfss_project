/* Shared UI state: persona, navigation, sidebar. */
var ME = { role: '', username: '', display_name: '' };
var TITLES = { apps: 'Apps &amp; <em>Add-ons</em>', dash: 'Dukani <em>Dashboard</em>', pos: 'Sell / <em>POS</em>', stock: 'Stock &amp; <em>Expiry</em>', inv: 'Supplier <em>Invoices</em>', rec: 'Daily <em>Reconciliation</em>', pat: 'Refill <em>Care</em>', alerts: 'Stock <em>Alerts</em>', fin: 'Credit &amp; <em>Expenses</em>', drugs: '&#128138; Drug <em>Catalogue</em>', manage: 'Owner <em>Manage Data</em>' };

function switchTab(tabId) {
  if (typeof canOpenTab === 'function' && !canOpenTab(tabId)) {
    if (typeof openUpgradeForTab === 'function') openUpgradeForTab(tabId);
    return false;
  }
  document.querySelectorAll('.snav button').forEach(x => {
    x.classList.toggle('active', x.dataset.tab === tabId);
  });
  document.querySelectorAll('.mobile-bottom-nav button[data-bottom-tab]').forEach(x => {
    x.classList.toggle('active', x.dataset.bottomTab === tabId);
  });
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const targetTab = $('tab-' + tabId);
  if (targetTab) targetTab.classList.add('active');
  $('pageTitle').innerHTML = TITLES[tabId] || '';
  toggleMobileSidebar(false);
  window.scrollTo({ top: 0, behavior: 'smooth' });
  return true;
}

function toggleMobileSidebar(force) {
  const side = document.querySelector('.side');
  const backdrop = $('sideBackdrop');
  if (!side) return;
  const shouldOpen = force !== undefined ? force : !side.classList.contains('open');
  if (shouldOpen) {
    side.classList.add('open');
    if (backdrop) backdrop.classList.add('active');
    document.body.style.overflow = 'hidden';
  } else {
    side.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
    document.body.style.overflow = '';
  }
}

function toggleDesktopSidebar() {
  const app = document.querySelector('.app');
  if (!app) return;
  if (window.innerWidth <= 900) {
    toggleMobileSidebar();
    return;
  }
  app.classList.toggle('side-collapsed');
  const isCollapsed = app.classList.contains('side-collapsed');
  localStorage.setItem('sidebar_collapsed', isCollapsed ? '1' : '0');
  const tip = isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar';
  document.querySelectorAll('.side-collapse-btn, .desk-toggle-btn').forEach(btn => btn.setAttribute('title', tip));
}

function syncSidebarState() {
  const app = document.querySelector('.app');
  if (!app) return;
  if (window.innerWidth > 900) {
    toggleMobileSidebar(false);
    if (localStorage.getItem('sidebar_collapsed') === '1') {
      app.classList.add('side-collapsed');
    } else {
      app.classList.remove('side-collapsed');
    }
  } else {
    app.classList.remove('side-collapsed');
  }
}

function applyPersona() {
  document.body.dataset.role = ME.role || '';
  $('whoName').textContent = ME.display_name || ME.username || '…';
  const ini = initials(ME.display_name || ME.username);
  $('avatar').textContent = ini;
  if ($('mobAvatar')) $('mobAvatar').textContent = ini;
  const rb = $('whoRole');
  rb.textContent = ROLE_LABEL[ME.role] || ME.role || '…';
  rb.className = 'rolebadge ' + (ME.role === 'admin' ? 'admin' : 'attendant');
}

function openProfile() {
  $('pfName').value = ME.display_name || '';
  $('pfPhone').value = ME.phone || '';
  $('pfPassNew').value = '';
  $('pfMsg').textContent = '';
  $('profileModal').classList.add('show');
}

function closeProfile() {
  $('profileModal').classList.remove('show');
}

async function saveProfile() {
  try {
    ME = Object.assign(ME, await api('/api/me', 'PUT', { display_name: $('pfName').value, phone: $('pfPhone').value }));
    if ($('pfPassNew').value) {
      await api('/api/change-password', 'POST', { old: prompt('Enter current password to confirm:'), new: $('pfPassNew').value });
      $('pfMsg').textContent = 'Profile + password saved ✓';
    } else $('pfMsg').textContent = 'Profile saved ✓';
    applyPersona();
  } catch (e) {
    $('pfMsg').textContent = '❌ ' + e.message;
  }
}
