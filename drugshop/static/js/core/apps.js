/* Entitlement-aware launcher, navigation, plan panel, and upgrade prompt.
   Loaded after core/ui.js and before boot.js. When /api/apps is unavailable we
   fail open: every app stays visible and boot.js falls back to loadAll(). */
var APPS_DATA = null;
var APP_BY_ID = {};
var TAB_APPS = {};
var UPGRADE_RETURN_FOCUS = null;

var BUNDLE_NAMES = {
  core: 'Core',
  pro: 'Pro',
  growth: 'Growth',
  tender: 'Tender Copilot',
  legacy: 'Legacy',
};

var PHARMACY_APP_IDS = ['pos', 'inventory', 'patients', 'finance', 'alerts'];

function escHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function bundleLabel(bundleId) {
  return BUNDLE_NAMES[bundleId] || (bundleId ? String(bundleId) : '');
}

function appById(appId) {
  return APP_BY_ID[appId] || null;
}

/* Tender Copilot is sold separately. Keep it out of pharmacy launchers, and
   keep the pharmacy suite out of Tender-only launchers, so neither demo shows
   the other product as a locked cross-sell tile. */
function launcherApps(data) {
  var apps = (data && data.apps) || [];
  var hasPharmacy = apps.some(function (app) {
    return app.entitled && PHARMACY_APP_IDS.indexOf(app.id) !== -1;
  });
  var hasTender = apps.some(function (app) {
    return app.entitled && app.id === 'tender';
  });

  if (hasTender && !hasPharmacy) {
    return apps.filter(function (app) {
      return app.always_on || app.id === 'tender';
    });
  }
  if (!hasTender) {
    return apps.filter(function (app) { return app.id !== 'tender'; });
  }
  return apps;
}

function isAppEntitled(appId) {
  if (!APPS_DATA) return true;
  var app = APP_BY_ID[appId];
  return app ? app.entitled === true : true;
}

function tabAppId(tabId) {
  return TAB_APPS[tabId] || '';
}

function canOpenTab(tabId) {
  if (!APPS_DATA) return true;
  var appId = tabAppId(tabId);
  return !appId || isAppEntitled(appId);
}

function setGatedHidden(el, hide) {
  if (!el) return;
  el.classList.toggle('app-hidden', !!hide);
  if (hide) el.setAttribute('hidden', 'hidden');
  else el.removeAttribute('hidden');
}

function sectionHasVisibleItem(title) {
  var wanted = (title.dataset.sectionApps || '')
    .split(',')
    .map(function (x) { return x.trim(); })
    .filter(Boolean);
  if (!wanted.length) return true;
  if (wanted.some(isAppEntitled)) return true;

  /* A section can also contain always-available items (for example Manage
     Data). Keep its heading when one of those is still visible. */
  var el = title.nextElementSibling;
  while (el && !el.classList.contains('snav-section-title')) {
    if (el.matches('button, a') && !el.classList.contains('app-hidden')) {
      var appId = el.dataset.app;
      if (!appId || isAppEntitled(appId)) return true;
    }
    el = el.nextElementSibling;
  }
  return false;
}

function applyApps(data) {
  APPS_DATA = data || { apps: [], plan: {}, support: {} };
  APP_BY_ID = {};
  TAB_APPS = {};

  (APPS_DATA.apps || []).forEach(function (app) {
    APP_BY_ID[app.id] = app;
    (app.tabs || []).forEach(function (tabId) {
      TAB_APPS[tabId] = app.id;
    });
  });

  document.querySelectorAll('[data-app]').forEach(function (el) {
    var app = APP_BY_ID[el.dataset.app];
    setGatedHidden(el, !!app && !app.entitled);
  });

  document.querySelectorAll('.snav-section-title[data-section-apps]').forEach(function (title) {
    setGatedHidden(title, !sectionHasVisibleItem(title));
  });

  var active = document.querySelector('.tab.active');
  if (active && !canOpenTab(active.id.replace(/^tab-/, ''))) {
    switchTab('dash');
  }

  renderLauncher(APPS_DATA);
  renderPlanPanel(APPS_DATA);
}

function resetAppsGating() {
  APPS_DATA = null;
  APP_BY_ID = {};
  TAB_APPS = {};
  document.querySelectorAll('[data-app], .snav-section-title[data-section-apps]').forEach(function (el) {
    setGatedHidden(el, false);
  });
}

function renderLauncher(data) {
  var grid = $('appsGrid');
  if (!grid) return;

  var apps = launcherApps(data);
  var plan = (data && data.plan) || {};
  var included = apps.filter(function (app) { return !app.always_on && app.entitled; }).length;
  var total = apps.filter(function (app) { return !app.always_on; }).length;

  if ($('launcherPlanName')) $('launcherPlanName').textContent = plan.label || 'Custom plan';
  if ($('launcherPlanMeta')) {
    $('launcherPlanMeta').textContent = included + ' of ' + total + ' add-on apps included';
  }
  if ($('launcherPlanStatus')) {
    var status = plan.status || 'active';
    $('launcherPlanStatus').textContent = status;
    $('launcherPlanStatus').className = 'plan-status' + (status === 'active' ? '' : ' inactive');
  }

  if (!apps.length) {
    grid.innerHTML = '<div class="apps-empty">No apps are available yet. Ask your account manager to finish setup.</div>';
    return;
  }

  grid.innerHTML = apps.map(function (app) {
    var locked = !app.entitled;
    var icon = /^i-[a-z0-9-]+$/.test(app.icon || '') ? app.icon : 'i-dash';
    var badge = app.always_on ? 'Always on' : bundleLabel(app.bundle);
    var label = app.name + (locked ? ' — upgrade required' : '');
    return '<button type="button" class="app-card' + (locked ? ' locked' : '') + '"' +
      ' data-launch-app="' + escHtml(app.id) + '" aria-label="' + escHtml(label) + '">' +
      '<span class="app-ic" aria-hidden="true"><svg><use href="#' + icon + '"></use></svg></span>' +
      '<span class="app-body"><b>' + escHtml(app.name) + '</b>' +
      '<small>' + escHtml(app.description) + '</small>' +
      (badge ? '<span class="app-badge">' + escHtml(badge) + '</span>' : '') +
      '</span>' +
      (locked ? '<span class="app-lock" aria-hidden="true"><svg><use href="#i-lock"></use></svg></span>' : '') +
      '</button>';
  }).join('');

  grid.querySelectorAll('[data-launch-app]').forEach(function (button) {
    button.addEventListener('click', function () {
      launchApp(button.dataset.launchApp);
    });
  });
}

function launchApp(appId) {
  var app = appById(appId);
  if (!app) return;
  if (!app.entitled) {
    openUpgrade(appId);
    return;
  }
  if (app.href) {
    location.href = app.href;
    return;
  }
  var tabId = (app.tabs || [])[0];
  if (tabId) switchTab(tabId);
}

function prettyDate(isoDate) {
  if (!isoDate) return '';
  var parts = String(isoDate).split('-');
  if (parts.length !== 3) return String(isoDate);
  var date = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
  if (isNaN(date.getTime())) return String(isoDate);
  return date.toLocaleDateString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
}

function renderPlanPanel(data) {
  if (!$('planCard')) return;

  var plan = (data && data.plan) || {};
  var support = (data && data.support) || {};
  var status = plan.status || 'active';

  if ($('planName')) $('planName').textContent = plan.label || 'Custom plan';
  if ($('planStatus')) {
    $('planStatus').textContent = status;
    $('planStatus').className = 'plan-status' + (status === 'active' ? '' : ' inactive');
  }
  if ($('planExpiry')) {
    $('planExpiry').textContent = plan.expires_at ? prettyDate(plan.expires_at) : 'No expiry set';
  }

  if ($('planApps')) {
    var included = ((data && data.apps) || []).filter(function (app) { return app.entitled; });
    $('planApps').innerHTML = included.map(function (app) {
      return '<span class="plan-chip">' + escHtml(app.name) + '</span>';
    }).join('') || '<span class="plan-chip muted-chip">No apps included</span>';
  }

  var supportLink = $('planSupport');
  if (supportLink) {
    var href = supportWhatsApp('Hi, I would like to ask about my ' + (plan.label || 'current') + ' plan.');
    supportLink.href = href || '#';
    supportLink.hidden = !href;
    supportLink.style.display = href ? '' : 'none';
  }
}

function supportWhatsApp(message) {
  var raw = (APPS_DATA && APPS_DATA.support && APPS_DATA.support.whatsapp) || '';
  var digits = String(raw).replace(/\D/g, '');
  if (!digits) return '';
  return 'https://wa.me/' + digits + '?text=' + encodeURIComponent(message || '');
}

function openUpgradeForTab(tabId) {
  var appId = tabAppId(tabId);
  if (appId) openUpgrade(appId);
}

function openUpgrade(appId) {
  var modal = $('upgradeModal');
  if (!modal) return;

  if (!modal.classList.contains('show')) UPGRADE_RETURN_FOCUS = document.activeElement;

  var app = appById(appId);
  var plan = (APPS_DATA && APPS_DATA.plan) || {};
  var support = (APPS_DATA && APPS_DATA.support) || {};
  var planLabel = plan.label || 'current';

  if ($('upgradeAppName')) $('upgradeAppName').textContent = app ? app.name : 'This app';
  if ($('upgradeCopy')) {
    $('upgradeCopy').textContent = app
      ? app.name + ' is not included in your ' + planLabel + ' plan. Ask your account manager to add it.'
      : 'That feature is not included in your ' + planLabel + ' plan. Ask your account manager to add it.';
  }

  var bundle = app && app.bundle ? bundleLabel(app.bundle) : '';
  if ($('upgradeBundle')) {
    $('upgradeBundle').textContent = app && app.id === 'tender'
      ? 'Tender Copilot is a standalone add-on and can be combined with any pharmacy plan.'
      : (bundle ? 'Available with the ' + bundle + ' plan.' : '');
    $('upgradeBundle').style.display = bundle ? '' : 'none';
  }
  if ($('upgradePlan')) $('upgradePlan').textContent = planLabel;

  var wa = $('upgradeWhatsApp');
  if (wa) {
    var href = supportWhatsApp('Hi, I would like to add ' + (app ? app.name : 'an app') + ' to my ' + planLabel + ' plan.');
    wa.href = href || '#';
    wa.hidden = !href;
    wa.style.display = href ? '' : 'none';
  }
  if ($('upgradeNoSupport')) {
    $('upgradeNoSupport').style.display = (support && support.whatsapp) ? 'none' : '';
  }

  modal.classList.add('show');
  modal.setAttribute('aria-hidden', 'false');
  var close = $('upgradeClose');
  if (close) setTimeout(function () { close.focus(); }, 0);
}

function closeUpgrade() {
  var modal = $('upgradeModal');
  if (!modal || !modal.classList.contains('show')) return;
  modal.classList.remove('show');
  modal.setAttribute('aria-hidden', 'true');
  if (UPGRADE_RETURN_FOCUS && typeof UPGRADE_RETURN_FOCUS.focus === 'function') {
    UPGRADE_RETURN_FOCUS.focus();
  }
  UPGRADE_RETURN_FOCUS = null;
}

function handleUpgradeParam() {
  var params = new URLSearchParams(location.search);
  var appId = params.get('upgrade');
  if (!appId) return;

  if (!appById(appId) || !isAppEntitled(appId)) {
    openUpgrade(appId);
  }

  params.delete('upgrade');
  var query = params.toString();
  history.replaceState({}, '', location.pathname + (query ? '?' + query : '') + location.hash);
}

document.addEventListener('keydown', function (event) {
  var modal = $('upgradeModal');
  if (!modal || !modal.classList.contains('show')) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    closeUpgrade();
    return;
  }
  if (event.key !== 'Tab') return;

  var focusable = Array.prototype.filter.call(
    modal.querySelectorAll('a[href], button:not([disabled])'),
    function (el) { return el.offsetParent !== null && !el.hidden; }
  );
  if (!focusable.length) return;
  var first = focusable[0];
  var last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

document.addEventListener('DOMContentLoaded', function () {
  var modal = $('upgradeModal');
  if (!modal) return;
  modal.addEventListener('click', function (event) {
    if (event.target === modal) closeUpgrade();
  });
});
