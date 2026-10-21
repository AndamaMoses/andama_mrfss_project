/* Settings + demo seeding. */
async function loadSettings() {
  try {
    const s = await api('/api/settings');
    $('setShop').value = s.shop_name || '';
    $('setPhone').value = s.shop_phone || '';
    $('setMgr').value = s.manager_phone || '';
    $('setFooter').value = s.receipt_footer || '';
  } catch (e) { }
}

async function saveSettings(e) {
  e.preventDefault();
  await api('/api/settings', 'POST', { shop_name: $('setShop').value, shop_phone: $('setPhone').value, manager_phone: $('setMgr').value, receipt_footer: $('setFooter').value });
  alert('Settings saved');
}

async function seedDemo() {
  await api('/api/seed', 'POST');
  loadAll();
}
