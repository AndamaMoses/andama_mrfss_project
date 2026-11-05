/* Mobile-money request-to-pay for the Sell/POS counter (MTN and Airtel).
   A sale is recorded only after the customer approves the prompt and the
   server re-checks the reference. Uncheck the request box to record a payment
   that was already made directly to the till. */

var MOMO = {
  providers: {
    MTN: { configured: false, environment: '', currency: 'UGX' },
    AIRTEL: { configured: false, environment: '', currency: 'UGX' },
  },
  configured: false,
  environment: '',
  currency: 'UGX',
  busy: false,
  cancel: false,
  manualProvider: '',
};
var MOMO_PAID = null;    // { ref, amount, provider } — paid but not saved yet
var MOMO_PENDING = null; // { ref, amount, phone, key, provider } — awaiting approval

function momoPhoneKey(phone) {
  let digits = String(phone || '').replace(/\D/g, '');
  if (digits.indexOf('00') === 0) digits = digits.slice(2);
  if (/^0\d{9}$/.test(digits)) digits = '256' + digits.slice(1);
  return digits;
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
    { configured: false, environment: '', currency: 'UGX' };
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
      };
    });
  } catch (e) {
    MOMO.providers.MTN = { configured: false, environment: '', currency: 'UGX' };
    MOMO.providers.AIRTEL = { configured: false, environment: '', currency: 'UGX' };
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
    manual.placeholder = momoProviderLabel(provider) + ' reference / SMS transaction ID';
  }
  const hint = $('momoManualHint');
  if (hint && provider) {
    hint.textContent = 'Enter the reference from the customer\'s ' +
      momoProviderLabel(provider) + ' SMS or receipt. It is recorded against ' +
      'this sale once and cannot be reused.';
  }

  if (!show || MOMO.busy) return;
  if (!momoConfiguredFor(method)) {
    setMomoState('warn', 'Manual entry only — ' + momoProviderLabel(provider) +
      ' is not configured on this terminal. Enter the reference from the customer\'s SMS.');
  } else if (momoRequestEnabled(method)) {
    setMomoState('idle', 'Ready — the customer approves on their phone');
  } else {
    setMomoState('warn', 'Manual record — enter the ' + momoProviderLabel(provider) +
      ' reference from the customer\'s SMS. No prompt will be sent.');
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
  const phoneKey = momoPhoneKey(cleanPhone);

  if (MOMO_PAID) {
    if (MOMO_PAID.provider === provider && Math.abs(MOMO_PAID.amount - amount) < 0.01) {
      const ref = MOMO_PAID.ref;
      MOMO_PAID = null;
      setMomoState('ok', 'Using paid reference ' + shortRef(ref));
      return ref;
    }
    // Never start a second prompt while the previous payment is paid but its
    // sale has not been saved: the customer would be charged twice.
    throw new Error(
      'A ' + momoProviderLabel(MOMO_PAID.provider) + ' payment of ' +
      (momoProviderConfig(MOMO_PAID.provider).currency || 'UGX') + ' ' +
      MOMO_PAID.amount.toLocaleString() + ' is already paid but not saved. ' +
      'Save that sale first (or enter the reference manually) before starting a new payment.'
    );
  }

  if (MOMO_PENDING) {
    if (
      MOMO_PENDING.provider === provider &&
      Math.abs(MOMO_PENDING.amount - amount) < 0.01 &&
      phoneKey !== '' &&
      momoPhoneKey(MOMO_PENDING.phone) === phoneKey
    ) {
      const pending = MOMO_PENDING;
      if (!pending.ref) {
        // The previous attempt lost its response before a reference arrived.
        // Retry with the same idempotency key so the server can return the
        // original request instead of creating a second prompt.
        setMomoState('wait', 'Retrying the payment request…');
        return requestMomoPayment(amount, phone, 'SALE-' + Date.now(), pending.key, selected);
      }
      MOMO.busy = true;
      MOMO.cancel = false;
      if ($('momoCancel')) $('momoCancel').hidden = false;
      setMomoState('wait', 'Checking the existing payment request ' + shortRef(pending.ref));
      try {
        const status = await waitForMomo(pending.ref, pending.provider);
        if (status !== 'SUCCESSFUL') {
          // A definitive failure must release the guard; only an unresolved
          // request (cancel/timeout) keeps MOMO_PENDING for a later check.
          if (status === 'FAILED' || status === 'REJECTED' || status === 'TIMEOUT') {
            MOMO_PENDING = null;
          }
          throw new Error('Payment ' + status.toLowerCase());
        }
        MOMO_PENDING = null;
        setMomoState('ok', 'Payment received ✓ — saving the sale…');
        return pending.ref;
      } catch (e) {
        setMomoState('error', e.message);
        throw e;
      } finally {
        MOMO.busy = false;
        if ($('momoCancel')) $('momoCancel').hidden = true;
      }
    }
    // A pending prompt may still be approved on the customer's phone. Do not
    // send a second one for a different amount/phone until it is resolved.
    throw new Error(
      'A ' + momoProviderLabel(MOMO_PENDING.provider) + ' request for ' +
      (momoProviderConfig(MOMO_PENDING.provider).currency || 'UGX') + ' ' +
      MOMO_PENDING.amount.toLocaleString() + ' on ' +
      (MOMO_PENDING.phone || 'the customer phone') +
      ' is still unresolved. Check it before starting a new payment.'
    );
  }

  // A fresh attempt gets a stable key that survives a network failure, so a
  // double-click or retry cannot create a second customer prompt.
  const key = 'POS-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
  return requestMomoPayment(amount, phone, 'SALE-' + Date.now(), key, selected);
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
  MOMO_PENDING = { ref: '', amount, phone: cleanPhone, key: idempotencyKey, provider: provider };

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
        MOMO_PENDING = { ref, amount, phone: cleanPhone, key: idempotencyKey, provider: provider };
        setMomoState('warn', 'The request outcome is unknown — checking ' + shortRef(ref));
      } else if (definitive) {
        // The carrier rejected this request; a retry with the same key would
        // only return the same failure. Release the guard for a fresh attempt.
        MOMO_PENDING = null;
        throw e;
      } else if (!e.status || e.status >= 500) {
        // Transport/proxy failure. Keep the key so the next attempt retries
        // the same request rather than creating another one.
        throw e;
      } else {
        MOMO_PENDING = null;
        throw e;
      }
    }

    if (!ref) {
      if (!r.reference_id) {
        MOMO_PENDING = null;
        throw new Error(label + ' did not return a payment reference');
      }
      ref = r.reference_id;
      MOMO_PENDING = { ref, amount, phone: cleanPhone, key: idempotencyKey, provider: provider };
    }

    const status = await waitForMomo(ref, provider);
    if (status !== 'SUCCESSFUL') {
      MOMO_PENDING = null;
      throw new Error(label + ' payment ' + status.toLowerCase());
    }
    MOMO_PENDING = null;
    setMomoState('ok', 'Payment received ✓ — saving the sale…');
    return ref;
  } catch (e) {
    setMomoState('error', e.message);
    throw e;
  } finally {
    MOMO.busy = false;
    if ($('momoCancel')) $('momoCancel').hidden = true;
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
