/* Mobile-money request-to-pay for the Sell/POS counter (MTN and Airtel).
   A sale is recorded only after the customer approves the prompt and the
   server re-checks the reference. Uncheck the request box to record a payment
   that was already made directly to the till. */

var MOMO = {
  providers: {
    MTN: { configured: false, environment: '', currency: 'UGX', verify_sales: true },
    AIRTEL: { configured: false, environment: '', currency: 'UGX', verify_sales: true },
  },
  configured: false,
  environment: '',
  currency: 'UGX',
  busy: false,
  cancel: false,
  manualProvider: '',
};
var MOMO_PAID = null;    // { ref, amount, phone, provider } — paid but not saved yet
var MOMO_PENDING = null; // { ref, amount, phone, key, provider } — awaiting approval
var MOMO_GUARD_KEY = 'onzima.momo.guard.v1';

function momoPhoneKey(phone) {
  let digits = String(phone || '').replace(/\D/g, '');
  if (digits.indexOf('00') === 0) digits = digits.slice(2);
  if (digits.indexOf('2560') === 0) digits = '256' + digits.slice(4);
  if (/^0\d{9}$/.test(digits)) digits = '256' + digits.slice(1);
  if (/^7\d{8}$/.test(digits)) digits = '256' + digits;
  return digits;
}

function momoRefKey(ref) {
  let key = String(ref || '').trim().toUpperCase();
  if (key.length > 1 && key.charAt(0) === '{' && key.charAt(key.length - 1) === '}') {
    key = key.slice(1, -1);
  }
  // UUIDs may be typed with or without braces/hyphens; compare the same form.
  const compact = key.replace(/-/g, '');
  if (/^[0-9A-F]{32}$/.test(compact)) return compact;
  return key;
}

function momoGuardMatches(guard, provider, amount, phone) {
  if (!guard) return false;
  if (guard.provider !== provider) return false;
  if (Math.abs(Number(guard.amount) - Number(amount)) >= 0.01) return false;
  const guardPhone = momoPhoneKey(guard.phone);
  const salePhone = momoPhoneKey(phone);
  return guardPhone !== '' && salePhone !== '' && guardPhone === salePhone;
}

/* Persist the guards for this tab. A reload must not forget a customer who
   has already paid, otherwise the next attempt could send a second prompt. */
function momoPersistGuards() {
  try {
    if (!MOMO_PAID && !MOMO_PENDING) {
      sessionStorage.removeItem(MOMO_GUARD_KEY);
    } else {
      sessionStorage.setItem(MOMO_GUARD_KEY, JSON.stringify({
        paid: MOMO_PAID,
        pending: MOMO_PENDING,
      }));
    }
  } catch (e) { /* storage can be unavailable in private mode */ }
}

function momoRestoreGuards() {
  try {
    const raw = sessionStorage.getItem(MOMO_GUARD_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (saved && saved.paid && saved.paid.ref) MOMO_PAID = saved.paid;
    if (saved && saved.pending) MOMO_PENDING = saved.pending;
  } catch (e) {
    MOMO_PAID = null;
    MOMO_PENDING = null;
  }
}

function momoSetPaid(guard) {
  MOMO_PAID = guard || null;
  momoPersistGuards();
  renderMomoGuards();
}

function momoSetPending(guard) {
  MOMO_PENDING = guard || null;
  momoPersistGuards();
  renderMomoGuards();
}

/* Clear only the guard(s) that the saved sale actually used. A cash sale or a
   sale on a different reference must never erase a paid-but-unsaved guard. */
function momoClearGuardsForRef(ref) {
  const key = momoRefKey(ref);
  if (!key) return false;
  let changed = false;
  if (MOMO_PAID && momoRefKey(MOMO_PAID.ref) === key) {
    MOMO_PAID = null;
    changed = true;
  }
  if (MOMO_PENDING && momoRefKey(MOMO_PENDING.ref) === key) {
    MOMO_PENDING = null;
    changed = true;
  }
  if (changed) {
    momoPersistGuards();
    renderMomoGuards();
  }
  return changed;
}

function momoMethodProvider(method) {
  if (method === 'MTN_MOMO') return 'MTN';
  if (method === 'AIRTEL_MOMO') return 'AIRTEL';
  return '';
}

function momoProviderLabel(provider) {
  return provider === 'AIRTEL' ? 'Airtel Money' : 'MTN MoMo';
}

function momoSelectedMethod() {
  const last = MOMO.lastMethod;
  if (last && momoMethodProvider(last)) return last;
  const a = $('sMethod'), b = $('bMethod');
  if (a && momoMethodProvider(a.value)) return a.value;
  if (b && momoMethodProvider(b.value)) return b.value;
  return '';
}

function momoProviderConfig(provider) {
  return (MOMO.providers && MOMO.providers[provider]) ||
    { configured: false, environment: '', currency: 'UGX', verify_sales: true };
}

function momoConfiguredFor(method) {
  const provider = momoMethodProvider(method);
  return !!provider && !!momoProviderConfig(provider).configured;
}

async function loadMomo() {
  try {
    const h = await api('/api/payments/health');
    const list = h.providers || {};
    ['MTN', 'AIRTEL'].forEach(function (provider) {
      const cfg = list[provider] || {};
      MOMO.providers[provider] = {
        configured: !!cfg.configured,
        environment: cfg.environment || '',
        currency: cfg.currency || 'UGX',
        verify_sales: cfg.verify_sales !== false,
      };
    });
  } catch (e) {
    MOMO.providers.MTN = { configured: false, environment: '', currency: 'UGX', verify_sales: true };
    MOMO.providers.AIRTEL = { configured: false, environment: '', currency: 'UGX', verify_sales: true };
  }
  const method = momoSelectedMethod();
  const provider = momoMethodProvider(method);
  const cfg = momoProviderConfig(provider);
  MOMO.configured = !!cfg.configured;
  MOMO.environment = cfg.environment;
  MOMO.currency = cfg.currency;
  syncMomoUi();
}

function momoWanted() {
  return !!momoSelectedMethod();
}

function momoRequestEnabled(method) {
  const selected = method || momoSelectedMethod();
  const cb = $('momoRequest');
  return !!selected && momoConfiguredFor(selected) && (!cb || cb.checked);
}

function momoManualMode(method) {
  const selected = method || momoSelectedMethod();
  return !!selected && !momoRequestEnabled(selected);
}

function momoManualReference() {
  const el = $('momoManualRef');
  return el ? el.value.trim() : '';
}

function momoManualReferenceError(provider) {
  const reference = momoManualReference();
  if (reference) return '';
  // A monitored rollout may intentionally run with verification off; the
  // server accepts an empty reference in that mode, so the client must too.
  if (momoProviderConfig(provider).verify_sales === false) return '';
  return 'Enter the ' + momoProviderLabel(provider) +
    ' reference from the customer\'s SMS before saving the sale.';
}

function clearMomoManualReference() {
  const el = $('momoManualRef');
  if (el) el.value = '';
}

function syncMomoUi() {
  const box = $('momoBox');
  if (!box) return;
  const method = momoSelectedMethod();
  const provider = momoMethodProvider(method);
  const show = !!method;
  box.hidden = !show;

  // The manual reference box is shared between carriers. Never let a
  // reference typed for one carrier leak into the other carrier's sale.
  if (MOMO.manualProvider && MOMO.manualProvider !== provider) {
    clearMomoManualReference();
  }
  MOMO.manualProvider = provider;

  const title = $('momoTitle');
  if (title) title.textContent = provider ? momoProviderLabel(provider) : 'Mobile Money';

  const cfg = momoProviderConfig(provider);
  if ($('momoEnv')) {
    const env = cfg.environment === 'sandbox'
      ? 'SANDBOX'
      : (cfg.environment || '').toUpperCase();
    $('momoEnv').textContent = env ? env + ' · ' + cfg.currency : '';
  }

  const cb = $('momoRequest');
  if (cb) {
    cb.disabled = !momoConfiguredFor(method);
    if (cb.disabled) cb.checked = false;
  }
  const manualWrap = $('momoManualWrap');
  if (manualWrap) {
    const manualMode = show && !momoRequestEnabled(method);
    // A hidden manual reference must not survive into a later manual sale.
    if (!manualMode) clearMomoManualReference();
    manualWrap.hidden = !manualMode;
  }
  const manual = $('momoManualRef');
  if (manual && provider) {
    manual.placeholder = momoProviderLabel(provider) + ' reference / SMS transaction ID' +
      (cfg.verify_sales === false ? ' (optional)' : '');
  }
  const hint = $('momoManualHint');
  if (hint && provider) {
    hint.textContent = cfg.verify_sales === false
      ? 'Verification is off for this terminal. Enter the reference if the customer has it; leave it blank only for the monitored rollout.'
      : 'Enter the reference from the customer\'s ' +
        momoProviderLabel(provider) + ' SMS or receipt. It is recorded against ' +
        'this sale once and cannot be reused.';
  }

  renderMomoGuards();
  if (!show || MOMO.busy) return;
  if (!momoConfiguredFor(method)) {
    setMomoState('warn', 'Manual entry only — ' + momoProviderLabel(provider) +
      ' is not configured on this terminal. ' +
      (cfg.verify_sales === false
        ? 'A reference is optional.'
        : 'Enter the reference from the customer\'s SMS.'));
  } else if (momoRequestEnabled(method)) {
    setMomoState('idle', 'Ready — the customer approves on their phone');
  } else {
    setMomoState('warn', 'Manual record — ' +
      (cfg.verify_sales === false
        ? 'a reference is optional. '
        : 'enter the ' + momoProviderLabel(provider) +
          ' reference from the customer\'s SMS. ') +
      'No prompt will be sent.');
  }
}

function setMomoState(tone, text) {
  const wrap = $('momoState'), label = $('momoStateText');
  if (wrap) wrap.dataset.tone = tone;
  if (label) label.textContent = text;
}

function shortRef(ref) {
  return String(ref || '').slice(0, 8) + '…';
}

function momoExternalId() {
  return 'SALE-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
}

function momoGuardAmount(guard) {
  const currency = momoProviderConfig(guard.provider).currency || 'UGX';
  return currency + ' ' + Number(guard.amount || 0).toLocaleString();
}

function momoGuardSummary() {
  const parts = [];
  if (MOMO_PAID) {
    parts.push('Paid but not saved: ' + momoProviderLabel(MOMO_PAID.provider) + ' ' +
      momoGuardAmount(MOMO_PAID) + ' · ' + (MOMO_PAID.phone || 'customer phone') +
      ' · ' + shortRef(MOMO_PAID.ref) +
      '. Save that sale before starting another prompt.');
  }
  if (MOMO_PENDING) {
    parts.push('Pending request: ' + momoProviderLabel(MOMO_PENDING.provider) + ' ' +
      momoGuardAmount(MOMO_PENDING) + ' · ' + (MOMO_PENDING.phone || 'customer phone') +
      (MOMO_PENDING.ref
        ? ' · ' + shortRef(MOMO_PENDING.ref)
        : ' · reference not received') +
      '. It may still be approved on the customer phone.');
  }
  return parts.join(' ');
}

function renderMomoGuards() {
  const box = $('momoGuard');
  if (!box) return;
  const hasPaid = !!MOMO_PAID;
  const hasPending = !!MOMO_PENDING;
  box.hidden = !hasPaid && !hasPending;
  const text = $('momoGuardText');
  if (text) text.textContent = momoGuardSummary();
  const check = $('momoCheckBtn');
  if (check) {
    check.hidden = !hasPending;
    check.disabled = MOMO.busy;
  }
  const forgetPending = $('momoForgetPendingBtn');
  if (forgetPending) {
    forgetPending.hidden = !hasPending;
    forgetPending.disabled = MOMO.busy;
  }
  const forgetPaid = $('momoForgetPaidBtn');
  if (forgetPaid) {
    forgetPaid.hidden = !hasPaid;
    forgetPaid.disabled = MOMO.busy;
  }
}

/* Check a pending prompt without starting a sale. A successful check promotes
   it to the paid guard; a definitive failure releases it. */
async function checkMomoPending() {
  if (MOMO.busy || !MOMO_PENDING) return;
  let pending = MOMO_PENDING;
  MOMO.busy = true;
  MOMO.cancel = false;
  if ($('momoCancel')) $('momoCancel').hidden = false;
  renderMomoGuards();
  try {
    if (!pending.ref) {
      if (!pending.key) {
        throw new Error('This pending request has no reference or retry key; forget it only if you are sure the customer was not charged.');
      }
      setMomoState('wait', 'Recovering the pending payment request…');
      const r = await postCollect({
        amount: Math.round(pending.amount * 100) / 100,
        phone: pending.phone,
        provider: pending.provider,
        external_id: momoExternalId(),
        idempotency_key: pending.key,
        payer_message: 'Onzima Dawa',
        payee_note: 'Counter sale',
      });
      if (!r || !r.reference_id) {
        throw new Error('The carrier did not return a payment reference');
      }
      pending = {
        ref: r.reference_id,
        amount: pending.amount,
        phone: pending.phone,
        key: pending.key,
        provider: pending.provider,
      };
      momoSetPending(pending);
    }
    setMomoState('wait', 'Checking the existing payment request ' + shortRef(pending.ref));
    const status = await waitForMomo(pending.ref, pending.provider);
    if (status === 'SUCCESSFUL') {
      momoSetPending(null);
      momoSetPaid({
        ref: pending.ref,
        amount: pending.amount,
        phone: pending.phone,
        provider: pending.provider,
      });
      setMomoState('ok', 'Payment received ✓ — save the sale now');
    } else if (status === 'FAILED' || status === 'REJECTED' || status === 'TIMEOUT') {
      momoSetPending(null);
      setMomoState('error', 'Payment ' + status.toLowerCase());
    } else {
      setMomoState('warn', 'Payment is still ' + status.toLowerCase());
    }
  } catch (e) {
    const definitive = e.data &&
      (e.data.status === 'FAILED' || e.data.status === 'REJECTED' || e.data.status === 'TIMEOUT');
    if (definitive) momoSetPending(null);
    setMomoState(definitive ? 'error' : 'warn', e.message);
  } finally {
    MOMO.busy = false;
    if ($('momoCancel')) $('momoCancel').hidden = true;
    renderMomoGuards();
  }
}

function forgetMomoPending() {
  if (MOMO.busy || !MOMO_PENDING) return;
  const p = MOMO_PENDING;
  const warning = 'Forget the pending ' + momoProviderLabel(p.provider) +
    ' request for ' + momoGuardAmount(p) + ' on ' +
    (p.phone || 'the customer phone') + '?\n\n' +
    'Only do this if the customer did not receive the prompt or you have ' +
    'confirmed it cannot be approved. The request may still be approved later, ' +
    'which could charge the customer after you start a new payment.';
  if (!confirm(warning)) return;
  momoSetPending(null);
  setMomoState('warn', 'Pending request forgotten. Do not start another prompt ' +
    'for this customer until you are sure the first one will not be approved.');
}

function forgetMomoPaid() {
  if (MOMO.busy || !MOMO_PAID) return;
  const p = MOMO_PAID;
  const warning = 'Forget the paid ' + momoProviderLabel(p.provider) +
    ' reference ' + shortRef(p.ref) + ' for ' + momoGuardAmount(p) + ' on ' +
    (p.phone || 'the customer phone') + '?\n\n' +
    'Only do this if the payment is already recorded on a receipt or the ' +
    'customer was not actually charged. Forgetting it allows a new prompt and ' +
    'could charge the customer twice.';
  if (!confirm(warning)) return;
  momoSetPaid(null);
  setMomoState('warn', 'Paid reference forgotten. Check Today\'s Sales or ' +
    'reconciliation before charging this customer again.');
}

function cancelMomo() {
  if (!MOMO.busy) return;
  MOMO.cancel = true;
  setMomoState('warn', 'Cancelling — the phone prompt cannot be withdrawn. The request stays pending so the next attempt can check it.');
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/* Return a paid reference, reusing one whose sale failed to save so the
   customer is never charged twice. Also poll an existing pending request
   before sending a second prompt for the same amount and phone. */
async function momoReferenceFor(amount, phone, method) {
  const selected = method || momoSelectedMethod();
  const provider = momoMethodProvider(selected);
  const cleanPhone = String(phone || '').trim();

  if (MOMO_PAID) {
    if (momoGuardMatches(MOMO_PAID, provider, amount, cleanPhone)) {
      setMomoState('ok', 'Using paid reference ' + shortRef(MOMO_PAID.ref));
      // Keep the guard until the sale is confirmed saved. pos.js clears it
      // only when the response carries this exact reference.
      return MOMO_PAID.ref;
    }
    // Never start a second prompt while the previous payment is paid but its
    // sale has not been saved: the customer would be charged twice.
    throw new Error(
      'A ' + momoProviderLabel(MOMO_PAID.provider) + ' payment of ' +
      momoGuardAmount(MOMO_PAID) + ' on ' +
      (MOMO_PAID.phone || 'the customer phone') +
      ' is already paid but not saved. Save that sale first (or enter the ' +
      'reference manually) before starting a new payment. If the paid reference ' +
      'is already on a receipt, use "Forget paid reference" below.'
    );
  }

  if (MOMO_PENDING) {
    if (momoGuardMatches(MOMO_PENDING, provider, amount, cleanPhone)) {
      const pending = MOMO_PENDING;
      if (!pending.ref) {
        // The previous attempt lost its response before a reference arrived.
        // Retry with the same idempotency key so the server can return the
        // original request instead of creating a second prompt.
        setMomoState('wait', 'Retrying the payment request…');
        return requestMomoPayment(amount, phone, momoExternalId(), pending.key, selected);
      }
      MOMO.busy = true;
      MOMO.cancel = false;
      if ($('momoCancel')) $('momoCancel').hidden = false;
      renderMomoGuards();
      setMomoState('wait', 'Checking the existing payment request ' + shortRef(pending.ref));
      try {
        const status = await waitForMomo(pending.ref, pending.provider);
        if (status !== 'SUCCESSFUL') {
          // A definitive failure must release the guard; only an unresolved
          // request (cancel/timeout) keeps MOMO_PENDING for a later check.
          if (status === 'FAILED' || status === 'REJECTED' || status === 'TIMEOUT') {
            momoSetPending(null);
          }
          throw new Error('Payment ' + status.toLowerCase());
        }
        // The customer has paid. Promote the guard before the sale request so
        // a failed save cannot forget the reference.
        momoSetPending(null);
        momoSetPaid({
          ref: pending.ref,
          amount: pending.amount,
          phone: pending.phone,
          provider: pending.provider,
        });
        setMomoState('ok', 'Payment received ✓ — saving the sale…');
        return pending.ref;
      } catch (e) {
        setMomoState('error', e.message);
        throw e;
      } finally {
        MOMO.busy = false;
        if ($('momoCancel')) $('momoCancel').hidden = true;
        renderMomoGuards();
      }
    }
    // A pending prompt may still be approved on the customer's phone. Do not
    // send a second one for a different amount/phone until it is resolved.
    throw new Error(
      'A ' + momoProviderLabel(MOMO_PENDING.provider) + ' request for ' +
      momoGuardAmount(MOMO_PENDING) + ' on ' +
      (MOMO_PENDING.phone || 'the customer phone') +
      ' is still unresolved. Check it before starting a new payment.'
    );
  }

  // A fresh attempt gets a stable key that survives a network failure, so a
  // double-click or retry cannot create a second customer prompt.
  const key = 'POS-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
  return requestMomoPayment(amount, phone, momoExternalId(), key, selected);
}

async function postCollect(payload) {
  try {
    return await api('/api/payments/collect', 'POST', payload);
  } catch (e) {
    if (e.status) throw e;
    // A transport failure may mean the server never saw the request. Retry
    // once with the same idempotency key; the ledger makes that safe.
    return api('/api/payments/collect', 'POST', payload);
  }
}

async function requestMomoPayment(amount, phone, externalId, idempotencyKey, method) {
  const selected = method || momoSelectedMethod();
  const provider = momoMethodProvider(selected);
  const label = momoProviderLabel(provider);
  if (!momoConfiguredFor(selected)) throw new Error(label + ' is not configured on this terminal');
  if (!phone || !phone.trim()) throw new Error('Enter the customer phone number for the ' + label + ' prompt');
  if (!(amount > 0)) throw new Error('The sale total must be greater than zero');

  const cleanPhone = phone.trim();
  const payload = {
    amount: Math.round(amount * 100) / 100,
    phone: cleanPhone,
    provider: provider,
    external_id: externalId,
    idempotency_key: idempotencyKey,
    payer_message: 'Onzima Dawa',
    payee_note: 'Counter sale',
  };

  MOMO.busy = true;
  MOMO.cancel = false;
  if ($('momoCancel')) $('momoCancel').hidden = false;
  setMomoState('wait', 'Sending ' + label + ' payment request…');
  // Remember the key before the request. If the response is lost, the next
  // attempt retries this exact request instead of sending a second prompt.
  momoSetPending({ ref: '', amount, phone: cleanPhone, key: idempotencyKey, provider: provider });

  let ref = '';
  try {
    let r = null;
    try {
      r = await postCollect(payload);
    } catch (e) {
      // An ambiguous network/5xx failure still returns a reference to poll.
      // Do not throw it away: the customer may already have a prompt. A body
      // with an explicit FAILED status is definitive and must not be polled.
      const ambiguous = e.data && e.data.reference_id &&
        (e.data.status === 'UNKNOWN' || (e.status >= 500 && !e.data.status));
      const definitive = e.data &&
        (e.data.status === 'FAILED' || e.data.status === 'REJECTED' || e.data.status === 'TIMEOUT');
      if (ambiguous) {
        ref = e.data.reference_id;
        momoSetPending({ ref, amount, phone: cleanPhone, key: idempotencyKey, provider: provider });
        setMomoState('warn', 'The request outcome is unknown — checking ' + shortRef(ref));
      } else if (definitive) {
        // The carrier rejected this request; a retry with the same key would
        // only return the same failure. Release the guard for a fresh attempt.
        momoSetPending(null);
        throw e;
      } else if (!e.status || e.status >= 500) {
        // Transport/proxy failure. Keep the key so the next attempt retries
        // the same request rather than creating another one.
        throw e;
      } else {
        momoSetPending(null);
        throw e;
      }
    }

    if (!ref) {
      if (!r.reference_id) {
        momoSetPending(null);
        throw new Error(label + ' did not return a payment reference');
      }
      ref = r.reference_id;
      momoSetPending({ ref, amount, phone: cleanPhone, key: idempotencyKey, provider: provider });
    }

    const status = await waitForMomo(ref, provider);
    if (status !== 'SUCCESSFUL') {
      momoSetPending(null);
      throw new Error(label + ' payment ' + status.toLowerCase());
    }
    // Paid but not saved. Keep a paid guard carrying the phone so a later
    // cash/unrelated sale cannot erase it and trigger a second prompt.
    momoSetPending(null);
    momoSetPaid({ ref, amount, phone: cleanPhone, provider: provider });
    setMomoState('ok', 'Payment received ✓ — saving the sale…');
    return ref;
  } catch (e) {
    setMomoState('error', e.message);
    throw e;
  } finally {
    MOMO.busy = false;
    if ($('momoCancel')) $('momoCancel').hidden = true;
    renderMomoGuards();
  }
}

async function waitForMomo(ref, provider) {
  const started = Date.now();
  const timeoutMs = 120000;
  while (Date.now() - started < timeoutMs) {
    if (MOMO.cancel) {
      throw new Error('Payment request cancelled — no sale was saved. The request stays pending if the customer approves later.');
    }

    let data = {};
    try {
      data = await api(
        '/api/payments/status/' + encodeURIComponent(provider) + '/' +
        encodeURIComponent(ref)
      );
    } catch (e) {
      setMomoState('warn', 'Still checking the payment… (' + e.message + ')');
    }

    const status = String((data && data.status) || '').toUpperCase();
    if (status === 'SUCCESSFUL') return status;
    if (status === 'FAILED' || status === 'REJECTED' || status === 'TIMEOUT') return status;

    const secs = Math.round((Date.now() - started) / 1000);
    const currency = momoProviderConfig(provider).currency || 'UGX';
    setMomoState('wait', 'Waiting for approval on ' + (data.amount ? currency + ' ' + data.amount : 'the phone') + '… ' + secs + 's');
    await sleep(4000);
  }
  throw new Error('No approval after 2 minutes — the sale was not saved. The request stays pending; try again to check it.');
}

/* Keep the panel in sync with whichever payment method was last selected. */
['sMethod', 'bMethod'].forEach(function (id) {
  const el = $(id);
  if (el) el.addEventListener('change', function () {
    MOMO.lastMethod = el.value;
    syncMomoUi();
  });
});

// Restore a paid/pending guard after an accidental reload, then paint the
// guard controls. loadMomo() later refreshes the provider configuration.
momoRestoreGuards();
renderMomoGuards();
