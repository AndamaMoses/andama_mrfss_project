/* Read-only Revenue tab: price book, snapshot, invoice/payment ledger, renewals.
   Every call is a GET. Activation, invoicing, and payment recording stay on the
   operator CLI, so this module deliberately has no write path. */

var REV_CURRENCY = 'UGX';
var REV_METHODS = {
  cash: 'Cash',
  bank: 'Bank',
  mtn_momo: 'MTN MoMo',
  airtel_money: 'Airtel Money',
  other: 'Other',
};

function revAmount(value, currency) {
  var n = Math.round(Number(value) || 0);
  return n.toLocaleString() + ' ' + (currency || REV_CURRENCY);
}

function revMessage(tbody, cols, text) {
  var el = $(tbody);
  if (el) el.innerHTML = '<tr><td colspan="' + cols + '">' + escHtml(text) + '</td></tr>';
}

function revMethodLabel(method) {
  return REV_METHODS[method] || method;
}

function loadRevenue() {
  if (!ME || ME.role !== 'admin') return Promise.resolve();
  return Promise.allSettled([
    loadRevenueSnapshot(),
    loadRevenueBook(),
    loadRevenueInvoices(),
    loadRevenuePayments(),
    loadRevenueRenewals(),
  ]);
}

async function loadRevenueSnapshot() {
  try {
    var d = await api('/api/subscription/report');
    REV_CURRENCY = d.currency || REV_CURRENCY;
    $('revAsOf').textContent = d.as_of ? 'as of ' + d.as_of : 'snapshot';
    $('revMrr').textContent = revAmount(d.mrr, d.currency);
    $('revOutstanding').textContent = revAmount(d.outstanding_balance, d.currency);
    $('revCollected').textContent = revAmount(d.payments_collected, d.currency);
    $('revInvoiced').textContent = revAmount(d.total_invoiced, d.currency);
    $('revSetupInvoiced').textContent = revAmount(d.setup_invoiced, d.currency);
    $('revMonthlyInvoiced').textContent = revAmount(d.monthly_invoiced, d.currency);
    $('revInvoiceCount').textContent = String(d.invoice_count || 0);
    $('revRenewalCount').textContent = String(d.renewal_due_count || 0);
    $('revNote').textContent = 'Read-only snapshot of this installation. Plan changes, invoices, and ' +
      'payments are recorded by your operator, never from this screen.';

    var methods = d.payments_by_method || {};
    var keys = Object.keys(methods);
    $('revMethods').innerHTML = keys.length
      ? keys.map(function (k) {
        return '<span class="plan-chip">' + escHtml(revMethodLabel(k)) + ' · ' +
          revAmount(methods[k], d.currency) + '</span>';
      }).join('')
      : '<span class="plan-chip">Nothing collected yet</span>';
  } catch (e) {
    $('revAsOf').textContent = 'unavailable';
    $('revNote').textContent = 'Revenue report unavailable: ' + e.message;
    ['revMrr', 'revOutstanding', 'revCollected', 'revInvoiced', 'revSetupInvoiced',
      'revMonthlyInvoiced', 'revInvoiceCount', 'revRenewalCount'].forEach(function (id) {
        $(id).textContent = '—';
      });
    $('revMethods').innerHTML = '';
  }
}

async function loadRevenueBook() {
  try {
    var d = await api('/api/subscription/pricebook');
    $('revBookVersion').textContent = d.version || 'price book';
    $('revBookRows').innerHTML = (d.offers || []).map(function (o) {
      var rules = (o.roles || []).join(' / ');
      if ((o.requires || []).length) {
        rules += ' · requires ' + o.requires.map(function (r) { return r.label; }).join(', ');
      }
      var description = o.description
        ? '<br><span style="font-size:12px;color:var(--muted)">' + escHtml(o.description) + '</span>'
        : '';
      return '<tr><td><b>' + escHtml(o.label) + '</b>' + description + '</td>' +
        '<td>' + revAmount(o.setup, d.currency) + '</td>' +
        '<td>' + revAmount(o.monthly, d.currency) + '</td>' +
        '<td style="font-size:12px">' + escHtml(rules) + '</td></tr>';
    }).join('') || '<tr><td colspan="4">No offers</td></tr>';
    $('revBookRules').textContent = 'Setup discounts are capped at ' +
      revAmount(d.setup_discount_cap, d.currency) + '. Monthly fees are never discounted.';
  } catch (e) {
    $('revBookVersion').textContent = 'unavailable';
    revMessage('revBookRows', 4, 'Price book unavailable: ' + e.message);
    $('revBookRules').textContent = '';
  }
}

async function loadRevenueInvoices() {
  try {
    var rows = await api('/api/subscription/invoices');
    $('revInvoiceRows').innerHTML = rows.map(function (i) {
      var period = i.period_start && i.period_end
        ? ' <span style="font-size:11px;color:var(--muted)">' + escHtml(i.period_start) +
          ' → ' + escHtml(i.period_end) + '</span>'
        : '';
      return '<tr><td><b>' + escHtml(i.invoice_no) + '</b>' + period + '</td>' +
        '<td>' + escHtml(i.kind) + '</td>' +
        '<td>' + escHtml(i.issue_date || '—') + '</td>' +
        '<td>' + escHtml(i.due_date || '—') + '</td>' +
        '<td>' + revAmount(i.amount, i.currency) + '</td>' +
        '<td>' + revAmount(i.paid, i.currency) + '</td>' +
        '<td><b>' + revAmount(i.balance, i.currency) + '</b></td>' +
        '<td>' + escHtml(i.status) + '</td></tr>';
    }).join('') || '<tr><td colspan="8">No invoices yet</td></tr>';
  } catch (e) {
    revMessage('revInvoiceRows', 8, 'Invoices unavailable: ' + e.message);
  }
}

async function loadRevenuePayments() {
  try {
    var rows = await api('/api/subscription/payments');
    $('revPaymentRows').innerHTML = rows.map(function (p) {
      return '<tr><td>' + escHtml(p.paid_on || '—') + '</td>' +
        '<td>' + escHtml(p.invoice_no) + '</td>' +
        '<td>' + escHtml(p.invoice_kind) + '</td>' +
        '<td>' + escHtml(revMethodLabel(p.method)) + '</td>' +
        '<td><b>' + revAmount(p.amount, p.currency) + '</b></td>' +
        '<td>' + escHtml(p.reference || '—') + '</td>' +
        '<td>' + escHtml(p.received_by || '—') + '</td></tr>';
    }).join('') || '<tr><td colspan="7">No payments recorded yet</td></tr>';
  } catch (e) {
    revMessage('revPaymentRows', 7, 'Payments unavailable: ' + e.message);
  }
}

async function loadRevenueRenewals() {
  var input = $('revDays');
  var days = input ? Math.max(0, Math.min(3650, parseInt(input.value, 10) || 14)) : 14;
  if (input) input.value = String(days);
  try {
    var rows = await api('/api/subscription/renewals?days=' + encodeURIComponent(days));
    $('revRenewalRows').innerHTML = rows.map(function (r) {
      var when = r.days_until < 0
        ? Math.abs(r.days_until) + ' day(s) overdue'
        : 'in ' + r.days_until + ' day(s)';
      return '<tr><td><b>' + escHtml(r.customer_name || '—') + '</b></td>' +
        '<td>' + escHtml(r.bundle) + '</td>' +
        '<td>' + escHtml(r.current_period_end || '—') + '</td>' +
        '<td>' + escHtml(when) + '</td>' +
        '<td>' + revAmount(r.monthly_fee, r.currency) + '</td>' +
        '<td>' + escHtml(r.status) + '</td></tr>';
    }).join('') || '<tr><td colspan="6">Nothing due in the next ' + days + ' day(s)</td></tr>';
  } catch (e) {
    revMessage('revRenewalRows', 6, 'Renewals unavailable: ' + e.message);
  }
}
