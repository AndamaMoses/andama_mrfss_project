# Mobile Money Integration Guide: Onzima Dawa

**Target Systems:** MTN Mobile Money & Airtel Money Uganda  
**Applicable Project:** Onzima Dawa (Pharmacy POS & Tender Copilot)  
**Primary Currency:** Ugandan Shillings (`UGX`) *(Sandbox uses `EUR`)*  
**Deployment Context:** Onzima Charles Drug Shop (Kireka) & Communion Engineering Services (Jinja), Uganda  
**Tech Stack:** Python 3.12+ / Flask 3.x, SQLite 3 (Raw Parameterized SQL), Vanilla ES6 JavaScript  

---

## Implementation phases

The guide is delivered in phases. The status column reflects this repository.

| Phase | Scope | Status |
|---|---|---|
| 0 — Foundation | Architecture, `.env`, MTN client, provisioning CLI, blueprint wiring | **Built — reviewed** |
| 1 - MTN sale guard | Durable ledger, idempotency, callback, atomic anti-replay, amount/currency verification, manual-entry policy | **Built - signed off** |
| 2 — Airtel Money | `airtel.py`, telco detection, provider-aware ledger, unified `/api/payments/*` endpoints, Airtel sale verification, provider-aware POS/manual entry | **Built - awaiting sign-off** |
| 3 — Reconciliation | Payment variance ledger, stale-prompt sweep, Airtel callbacks, close-shift snapshots | **Built - awaiting sign-off** |
| 4 — POS UI | USSD push polling and manual fallback | **Built - awaiting sign-off** |
| 5 — Verification | Tests and runbook | Built for MTN and Airtel |

Phase 0 is the foundation reviewed first. Later sections describe the target
design and call out where the current code differs.

**Phase 0 verification (2026-11-03):** `python -m pytest -q` → 311 passed;
`python -m ruff check .` → clean; `python -m flask --app run momo status --check`
→ MTN sandbox token exchange OK.

Phase 0 hardening added during the second review:

- Bearer token is cached per client and refreshed once on HTTP 401; concurrent
  POS polls share one client per configuration instead of fetching a token per
  request.
- Ugandan MSISDNs are validated and normalised to `256...`; malformed numbers
  are rejected before MTN is called.
- `UGX` (and other zero-decimal currencies) must be whole shillings; a
  fractional amount is rejected rather than silently rounded.
- MTN 4xx responses are passed through to the counter; auth/5xx failures are
  hidden as `502` so an upstream outage is not mistaken for a bad payment.
- Network, malformed-URL, and protocol failures are wrapped as `MomoError`, so
  the health endpoint and CLI fail cleanly instead of raising a traceback.

Phase 1 closes those gaps: initiated collections are written to the durable
`momo_collections` ledger before MTN is called, retries reuse an idempotency
key, the callback and status routes update the ledger, sale claims are atomic,
and verification fails closed when credentials are incomplete. Phase 2 extends
the same ledger and guard to Airtel Money and adds the unified multi-provider
API.

**Phase 1 verification (2026-11-04):** `python -m pytest -q` → 332 passed;
`python -m ruff check .` → clean. No test calls the real MTN API or moves
money; the suite clears live credentials and injects fake transports.

Second-review hardening: a replayed sale now returns the original sale id and
receipt so the counter can stop retrying after a lost response; callback-only
successes are checked against MTN's reported amount/currency before a claim;
sale verification reuses one MTN client/token instead of fetching a new token
per sale; and the POS refuses to start a second prompt while a paid-but-unsaved
or unresolved pending request exists.

**Phase 2 verification (2026-11-04):** `python -m pytest -q` → 409 passed;
`python -m ruff check .` → clean; `node --check` → clean for `momo.js`,
`pos.js`, and `core/api.js`. The suite blanks all live credentials, injects a
fake Airtel transport, and monkeypatches the route/service clients, so no test
reaches MTN or Airtel or moves money.

Phase 2 hardening:

- The ledger records the owning provider; using an MTN reference on an Airtel
  sale (or vice versa) returns `409` instead of updating the wrong rail.
- Unified collection keys are provider-prefixed so the same POS idempotency key
  cannot collide across carriers in the global unique index.
- A definitive carrier rejection is returned with `status: FAILED` even when
  the HTTP status is hidden as `502`; the POS stops immediately instead of
  polling an auth failure for two minutes.
- A previously pending Airtel/MTN request that returns `FAILED`, `REJECTED`, or
  `TIMEOUT` now releases the POS pending guard; only an unresolved request
  (cancel/timeout) keeps it for a later check.
- Airtel status amounts/currencies may be strings; a successful sale still
  requires a non-empty, positive, exact amount and a matching currency. When a
  successful status response omits amount/currency, verification falls back to
  the pre-request ledger row and still fails closed if that row is missing.
- Manual entry cannot consume an unconfirmed `API` or `LEGACY` row, even when
  `MOMO_VERIFY_SALES` / `AIRTEL_VERIFY_SALES` is off; the rollout path may
  consume its own pending automated request, but not a reference entered by
  hand.
- Amount-mismatch responses include `paid_amount` and `paid_currency` so the
  POS can correct the sale to what the customer actually paid instead of
  sending a second prompt.
- Verify switches accept string booleans (`0`/`false`/`no`/`off`), and migration
  005 is safe to retry after an interrupted table rebuild.
- Live Airtel sandbox token/collection checks remain blocked until
  `AIRTEL_CLIENT_ID` and `AIRTEL_CLIENT_SECRET` are issued. Offline client,
  route, and sale-guard tests pass with a fake transport.

**Phase 3 verification (2026-11-05):** `python -m pytest -q` → 440 passed;
`python -m ruff check .` → clean; `node --check` → clean for `finance.js`,
`momo.js`, `pos.js`, and `core/api.js`. The suite uses fake carriers only.

Phase 3 adds:

- `payment_reconciliations`, a per-provider/day snapshot of expected, consumed,
  pending, unknown, orphaned, and variance amounts. Migration 006 covers
  existing databases; `schema.sql` covers fresh ones.
- A bounded stale-payment sweep that re-queries only old `PENDING`/`UNKNOWN`
  rows with no sale, prioritizes configured providers, skips unconfigured
  providers, supports `dry_run`, and records `RECONCILE` / `RECONCILE_ERROR`
  events.
- `POST /api/payments/airtel/callback`, authenticated with
  `AIRTEL_CALLBACK_SECRET`. It **never trusts the callback body**: it re-queries
  Airtel's status endpoint before updating the ledger.
- `daily-summary`, `close-shift`, `sweep`, and `payments` finance endpoints;
  `/api/reconciliation/calculate` now includes the live `payments` view. The
  reconciliation POSTs validate `YYYY-MM-DD` dates and reject non-object JSON
  with `400` instead of a server error.
- `flask --app run momo reconcile` for an operator/cron stale-payment sweep.
- The reconciliation tab shows confirmed, pending, unresolved, orphaned, and
  variance totals, per-provider breakdowns, the actual unresolved/orphaned
  references, a “Check Pending” action, and a “Close Shift & Snapshot” action.

**Phase 4 verification (2026-11-06):** `python -m pytest -q` → 499 passed;
`python -m ruff check .` → clean; `node --check` → clean for `momo.js`,
`pos.js`, `finance.js`, `core/api.js`, `core/format.js`, and `core/apps.js`.
The rendered `/staff` inline script also passes `node --check`. The suite uses
fake carriers only and never moves money.

Phase 4 hardening (second review, money safety):

- `MOMO_PAID` now stores the provider, amount, and normalised customer phone.
  It is cleared only when the saved sale response carries that exact
  reference. A cash sale, a manual sale on another reference, or a sale for a
  different customer no longer erases a paid-but-unsaved guard and allows a
  second prompt.
- A successful sale also clears a matching `MOMO_PENDING` guard. A manual sale
  that consumes the pending reference therefore releases the guard instead of
  leaving the POS permanently blocked.
- The payment panel exposes explicit guard controls: “Check pending request”
  polls/reuses the pending reference, “Forget pending” releases an unresolved
  prompt with a warning, and “Forget paid reference” releases a paid guard only
  after a confirmation that explains the double-charge risk.
- Both guards are persisted in `sessionStorage` for the tab, so an accidental
  reload does not forget a paid-but-unsaved reference. The guard controls remain
  available to resolve a stale entry.
- The basket is snapshotted before an automated prompt, and the Clear action is
  locked during checkout. A basket change during approval can no longer make the
  saved sale differ from the amount the customer approved.
- `/api/payments/health` and `/api/momo/health` expose `verify_sales`. The POS
  and staff pages require a manual reference only when the server will verify
  it, so the documented monitored-rollout path is usable without weakening the
  default verified path.
- POS-generated `external_id` values include a random suffix, so two terminals
  creating a request in the same millisecond cannot collide and reuse each
  other’s payment reference.
- A `SALE_BUSY` lock covers both single-item and basket checkout. The Sell and
  Complete buttons disable while a request is in flight, so a double-click
  cannot submit two sales. Basket add/remove actions are ignored during the
  request, so the basket cannot change underneath an in-progress checkout.
- Manual MTN/Airtel references are required client-side when the server's
  `verify_sales` flag is on. The POS and staff pages read that flag from the
  health endpoint; the staff page focuses the reference input when it is
  missing.
- The staff checkout is serialized with a `BUSY` guard and surfaces a `409`
  duplicate reference as the existing receipt instead of retrying the sale.
- Pending-prompt reuse compares normalised phone digits, so `077...`, `+256...`,
  and `00256...` are treated as the same number and a formatting difference
  does not trigger a second prompt.
- POS and staff receipt/sale HTML escape carrier references, customer names and
  phones, product names, shop fields, and receipt fields. Receipt references are
  restricted to a safe character set before being embedded in `onclick`
  handlers.
- The shared `escHtml` helper now lives in `core/format.js`, where `contactCell`
  also escapes the customer name and phone it renders.

## 1. Architecture & Design Principles

```text
[Cashier POS Interface]
          │
          ├── MTN_MOMO (automated) ──► POST /api/payments/collect {provider: MTN}
          │                                (legacy: POST /api/momo/collect)
          ├── AIRTEL_MOMO (automated) ─► POST /api/payments/collect {provider: AIRTEL}
          │
          ▼
 [momo_collections: PENDING, provider=MTN|AIRTEL]
          │
          ├── MTN: USSD push ──► GET /api/momo/collect/<ref>
          │                     POST /api/momo/callback
          └── Airtel: USSD push ─► GET /api/payments/status/AIRTEL/<ref>
                                   POST /api/payments/airtel/callback
                                   (re-queries status; body is not trusted)
          │
          ▼
 POST /api/sales[/cart] (payment_method, momo_ref)
          │
          ▼
   [_momo_guard]
   ├── canonical reference + duplicate check
   ├── provider match (MTN reference on an Airtel sale -> 409)
   ├── gateway verify (automated, fail-closed)
   └── amount and currency match
          │
          ▼
 [Atomic SQLite transaction]
   ├── allocate FEFO batches
   ├── deduct batch inventory
   ├── conditional ledger claim -> CONSUMED
   └── record sale lines + link sale_id
          │
          ▼
 [Return JSON & print receipt]
```

### Core Tenets
1. **Zero External Dependencies:** Built using Python's standard library `urllib.request` to prevent third-party package drift and keep deployment lightweight.
2. **Replay & Underpayment Guards:** Strict server-side verification before SQLite commits any stock deduction.
3. **Resilient Cashier Fallback:** Never halt counter sales during telco network degradation; attendants can toggle from automated USSD push to manual till code entry at any time.
4. **End-of-Shift Accounting:** Automated aggregation of expected MTN/Airtel sales against counted statements in the `reconciliations` ledger, with per-provider payment snapshots in `payment_reconciliations` and a bounded stale-prompt sweep before closing.

---

## 2. Environment Configuration (`.env`)

`config.py` loads `.env` at startup; real environment variables always win.
Copy `.env.example` to `.env` and fill in the values. Inline comments are **not**
supported by the loader, so put comments on their own lines.

```ini
# MTN Mobile Money Open API
MOMO_TARGET_ENVIRONMENT=sandbox
# 'sandbox' or a country environment such as 'mtnuganda'
MOMO_BASE_URL=
# Blank uses the sandbox host, or the production host for the environment.
MOMO_SUBSCRIPTION_KEY=
MOMO_API_USER=
# Auto-provisioned with: flask --app run momo provision --save
MOMO_API_KEY=
# Auto-provisioned with the same command.
MOMO_CURRENCY=
# Blank = EUR on sandbox (MTN's only sandbox currency), UGX in production.
MOMO_TIMEOUT=20
MOMO_VERIFY_SALES=1
# Public HTTPS endpoint, including ?token=<secret>:
#   MOMO_CALLBACK_URL=https://shop.example/api/momo/callback?token=...
MOMO_CALLBACK_URL=
# Shared secret for /api/momo/callback. Blank disables the route.
MOMO_CALLBACK_SECRET=

# Airtel Money OpenAPI Uganda
AIRTEL_BASE_URL=https://openapiuat.airtel.africa
AIRTEL_CLIENT_ID=
AIRTEL_CLIENT_SECRET=
AIRTEL_CURRENCY=UGX
AIRTEL_COUNTRY=UG
AIRTEL_TIMEOUT=20
AIRTEL_VERIFY_SALES=1
# Public HTTPS callback endpoint, including ?token=<secret>:
#   AIRTEL_CALLBACK_URL=https://shop.example/api/payments/airtel/callback?token=...
AIRTEL_CALLBACK_URL=
# Shared secret for /api/payments/airtel/callback. Blank disables the route.
AIRTEL_CALLBACK_SECRET=
```

## 3. Directory Layout

Current tree. The unified `/api/payments/*` routes dispatch to MTN or Airtel;
the original `/api/momo/*` endpoints remain for MTN compatibility.

```text
drugshop/
├── payments/
│   ├── __init__.py
│   ├── momo.py          # MTN Collections client (stdlib urllib)
│   ├── airtel.py        # Airtel OAuth2 collection/status client
│   ├── providers.py     # provider constants, method mapping, telco detection
│   ├── ledger.py        # provider-aware collections + atomic anti-replay claim
│   ├── errors.py        # shared PaymentError
│   ├── service.py       # fail-closed verification + fetch_status()
│   ├── reconciliation.py # stale sweep, payment summary, close-shift snapshots
│   ├── routes.py        # /api/momo/* compatibility + /api/payments/* unified
│   ├── cli.py           # flask momo status|provision|collect|request|reconcile
│   └── __init__.py
├── migrations/
│   ├── 004_momo_ledger.sql      # ledger tables + legacy momo_ref backfill
│   ├── 005_momo_provider.sql    # provider column rebuild/backfill
│   └── 006_payment_reconciliation.sql # per-provider/day variance snapshots
├── sales/
│   └── routes.py        # POS checkout with _momo_guard + ledger claim
├── finance/
│   └── routes.py        # Z-report + daily-summary/close-shift/sweep/payments
└── static/js/
    ├── momo.js          # provider-aware prompt polling, pending reuse, fallback
    ├── finance.js       # reconciliation totals + pending check
    └── pos.js           # payment form wiring for MTN and Airtel
```

## 4. Code Implementation

### 4.1 MTN MoMo Client (`drugshop/payments/momo.py`)
The shipped client is standard-library only and takes an injectable transport,
so tests never touch the network. Public API:

```python
from drugshop.payments.momo import MomoClient, MomoSettings, provision

settings = MomoSettings.from_mapping(app.config)  # or MomoSettings.from_env()
client = MomoClient(settings)                     # transport=... in tests

client.access_token()                             # cached bearer token
client.request_to_pay(amount=5000, phone="0772123456",
                      external_id="SALE-12")      # -> {reference_id, amount, ...}
client.request_status("11111111-1111-4111-8111-111111111111")
                                                  # -> {"status": "SUCCESSFUL", ...}
client.account_balance()
provision(settings)                               # -> (api_user, api_key)
```

Implementation notes:

- `MOMO_TIMEOUT` is parsed defensively; blank or invalid values fall back to 20s.
- Amounts must be finite and positive; an empty `externalId` falls back to the
  reference id, because MTN rejects an empty value.
- MSISDNs are normalized to `256...` by `normalize_msisdn()`; wrong-length
  numbers and the common `2560...` handset form are rejected/repaired before
  any network call.
- `UGX` and other zero-decimal currencies are sent as whole numbers. A
  fractional UGX total is an error, not something to round.
- `MomoError` wraps HTTP, network, protocol, and malformed-URL failures with
  `status` and `payload`. Routes pass MTN 4xx through and hide auth/5xx as 502.
- Bearer tokens are cached per client, refreshed once on a 401, and guarded by
  a lock so concurrent polls do not stampede MTN's token endpoint.
- Currency defaults to `EUR` on sandbox and `UGX` in production.

The full source is in [`drugshop/payments/momo.py`](../drugshop/payments/momo.py).

### 4.2 Airtel Money Client (`drugshop/payments/airtel.py`)

The shipped client mirrors the MTN client: standard library only, an injectable
transport for offline tests, and a cached OAuth2 bearer token refreshed once on
HTTP 401.

```python
from drugshop.payments.airtel import AirtelClient, AirtelSettings

settings = AirtelSettings.from_mapping(app.config)  # or .from_env()
client = AirtelClient(settings)                     # transport=... in tests

client.access_token()                               # cached client-credentials token
client.request_to_pay(
    amount=5000,
    phone="0701234567",
    external_id="POS-42",
    reference_id="22222222-2222-4222-8222-222222222222",
)                                                   # -> PENDING + reference_id
client.request_status("22222222-2222-4222-8222-222222222222")
                                                    # -> normalized SUCCESSFUL/...
```

Implementation notes:

- OAuth2 token: `POST /auth/oauth2/token` with `client_id`,
  `client_secret`, and `grant_type=client_credentials`.
- Collection: `POST /merchant/v1/payments/` with `reference`,
  `subscriber{country,currency,msisdn}`, and
  `transaction{amount,country,currency,id}`.
- Status: `GET /standard/v1/payments/{transaction_id}`.
- Airtel MSISDNs are national digits without the country code or leading zero
  (`0701234567` → `701234567`). This is deliberately different from MTN's
  `256...` form.
- `UGX` amounts are sent as whole numbers; a fractional UGX amount is rejected.
- Status codes normalize to the ledger vocabulary: `TS` → `SUCCESSFUL`;
  `TF`/`TIN` → `FAILED`; `TIP` → `PENDING`; `TA` → `UNKNOWN`; `TE` → `TIMEOUT`.
- Status amounts/currencies may be strings; the service converts them and still
  requires a non-empty, positive, exact amount with a matching currency.
- Airtel's status response may omit amount/currency. Verification then falls
  back to the amount/currency recorded in the ledger *before* the collection was
  requested, and the sale must still match exactly. With no ledger row the
  check stays fail-closed (`502`).
- A business failure in a `200` response is raised as `AirtelError` with an
  HTTP-like status; routes map it like an HTTP failure.
- Phase 3 adds the Airtel callback route. Airtel may still deliver only a
  polling result, so the POS continues to poll the status endpoint; callbacks
  and the stale sweep are additional confirmation paths.

The full source is in [`drugshop/payments/airtel.py`](../drugshop/payments/airtel.py).


### 4.3 Unified Service Layer (`drugshop/payments/service.py`)

The shipped verifier is provider-aware:

```python
verify_reference(reference, amount, provider="MTN", currency=None)
```

It canonicalises the reference, selects the MTN or Airtel settings/client, and
fails closed when the provider's verify switch is on but its credentials are
incomplete (`MOMO_VERIFY_SALES` / `AIRTEL_VERIFY_SALES`, both default on). A
successful check must report `SUCCESSFUL`, a non-empty positive amount that
matches the basket exactly, and a currency matching the configured environment.
The result is written to the ledger before the sale claim.

Provider detection lives in `drugshop/payments/providers.py`:

- `provider` is `MTN` or `AIRTEL`; `payment_method` is `MTN_MOMO` or
  `AIRTEL_MOMO`.
- Ugandan MTN prefixes: `077`, `078`, `076`, `039`.
- Ugandan Airtel prefixes: `070`, `074`, `075`, `020`.
- `detect_telco(phone)` returns `MTN_MOMO`, `AIRTEL_MOMO`, or `UNKNOWN`;
  `detect_provider(phone)` returns `MTN`, `AIRTEL`, or `UNKNOWN`.
- An unknown prefix is never guessed. The caller must select the carrier
  explicitly.

Client caches are keyed by provider and the credential/URL fields, so a POS
polling loop reuses one bearer token instead of fetching a new token per request.

`fetch_status(reference, provider)` is the read-only companion to
`verify_reference()`. It requires provider credentials but deliberately ignores
`MOMO_VERIFY_SALES` / `AIRTEL_VERIFY_SALES`, because a callback or reconciliation
sweep must be able to check a payment even when sale verification is disabled.
It never applies a sale claim and never moves money.


### 4.4 Payment API Endpoints (`drugshop/payments/routes.py`)

MTN compatibility endpoints remain:

- `GET /api/momo/health` — credential summary; `?check=1` forces a token
  exchange.
- `POST /api/momo/collect` — creates a `PENDING` ledger row *before* calling
  MTN, reuses an `idempotency_key`/`external_id`, and returns a pollable
  reference even when the MTN outcome is ambiguous.
- `GET /api/momo/collect/<reference_id>` — rejects non-UUID references and
  updates the ledger from MTN's status response.
- `POST /api/momo/callback` — public but authenticated with
  `MOMO_CALLBACK_SECRET`; it only updates an existing ledger row.

The unified provider-aware endpoints are:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/payments/health` | Both carriers' credential/environment summary; `?check=1` forces a token exchange per configured provider |
| `POST` | `/api/payments/detect` | Returns `provider` (`MTN`/`AIRTEL`/`UNKNOWN`) and `payment_method` (`MTN_MOMO`/`AIRTEL_MOMO`/`UNKNOWN`) for a Ugandan phone |
| `POST` | `/api/payments/collect` | Dispatches MTN or Airtel; `provider` may be `AUTO`/`DETECT` or omitted to use prefix detection |
| `GET` | `/api/payments/status/<provider>/<reference_id>` | Polls the selected carrier and updates the provider-aware ledger |
| `POST` | `/api/payments/airtel/callback` | Public Airtel callback; authenticates with `AIRTEL_CALLBACK_SECRET` and re-queries status before updating the ledger |

Collection behaviour:

- A missing/invalid amount or phone returns `400`; an unknown carrier returns
  `400` with `provider: UNKNOWN`; an unconfigured carrier returns `503`.
- A retried idempotency key or `external_id` returns the original reference
  (`202`, `reused: true`) instead of sending a second prompt.
- A definitive carrier rejection is `FAILED`; a network/5xx outcome is
  `UNKNOWN` and keeps the reference pollable.
- A reference owned by the other carrier returns `409` from both collection
  retries and status polling.
- Airtel collection references are always UUIDs, matching the ledger's
  canonical reference format.
- Both callbacks live on the always-on `payments_callback` blueprint and are in
  `OPEN_API`, because neither carrier can send a session cookie.
- The Airtel callback accepts the secret as `?token=`, `X-Callback-Token`, or
  `Authorization: Bearer`. It requires a UUID `transaction.id` that already
  exists in the ledger, rejects an MTN reference with `409`, and records what
  the callback *claimed* in the audit event without applying it. The status
  endpoint's answer is the only input to `apply_status()`.
- A callback for an unknown reference returns `404` and never creates a ledger
  row. A blank `AIRTEL_CALLBACK_SECRET` disables the route (`404`); a wrong
  secret returns `403`.


### 4.5 POS Sale Guard & FEFO Allocation (`drugshop/sales/routes.py`)

The shipped guard applies equally to `MTN_MOMO` and `AIRTEL_MOMO`:

- rejects a `momo_ref` on non-mobile-money methods;
- treats `is_manual_entry` as explicit: a manual payment must still supply a
  reference when that provider's verification is enabled, but is not sent to
  the gateway;
- rejects manual use of a `PENDING`/`UNKNOWN` API payment so a counter entry
  cannot consume a prompt the customer has not approved;
- rejects a reference owned by the other carrier with `409`;
- verifies automated references (fail-closed) and checks the amount and
  currency against the provider's configuration;
- performs the atomic ledger claim *inside* the sale transaction, before the
  sale row is inserted, so a stock or validation failure rolls the claim back;
- returns `409` for a reference already consumed by another sale, including the
  original `sale_id`/`receipt_ref`. Voiding a sale restores stock but leaves
  the ledger row `CONSUMED` and records a `SALE_VOIDED` audit event.

The guard passes `provider` to the ledger claim, so an Airtel manual reference
is stored as `provider=AIRTEL`, while legacy/pre-Phase-2 references remain
`MTN`. Manual Airtel references use `AIRTEL_CURRENCY` (default `UGX`), not the
MTN sandbox default.


### 4.6 End-of-Day Reconciliation Ledger (`drugshop/finance/routes.py`)

> **Status:** built in Phase 3. The original
> `GET /api/reconciliation/calculate` and `GET|POST /api/reconciliation`
> endpoints remain compatible; `calculate` now also returns a live `payments`
> summary.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/reconciliation/calculate?date=YYYY-MM-DD` | Expected sales by method, saved cash reconciliation, and live payment summary |
| `GET` | `/api/reconciliation/daily-summary?date=YYYY-MM-DD` | `summary` with expected cash/MTN/Airtel/credit and receipt count, plus `existing_reconciliation` and `payments` |
| `GET` | `/api/reconciliation/payments?date=YYYY-MM-DD` | Live payment variance (`live`) plus any saved close-shift snapshots (`saved`) |
| `POST` | `/api/reconciliation/close-shift` | Upserts counted balances with status `CLOSED`, returns per-channel variances, and snapshots payment variance |
| `POST` | `/api/reconciliation/sweep` | Bounded stale-prompt sweep; accepts `provider`, `older_than_minutes`, `limit`, and `dry_run` |
| `GET\|POST` | `/api/reconciliation` | Existing history/upsert endpoint; POST now validates the date |

Close-shift body:

```json
{
  "date": "2026-11-04",
  "counted_cash": 120000,
  "counted_mtn": 85000,
  "counted_airtel": 45000,
  "notes": "Evening shift closed cleanly."
}
```

It returns `status: CLOSED`, `difference`, `variances` (`cash`, `mtn`,
`airtel`), and the live `payments` snapshot. A non-numeric or non-finite counted
amount returns `400`; missing counted values default to `0`, matching the
original runbook contract. A malformed date returns `400` instead of creating a
separate ledger day; the same strict `YYYY-MM-DD` check applies to
`calculate`, `daily-summary`, `payments`, and the legacy POST.

`drugshop/payments/reconciliation.py` owns the variance logic:

- **expected** is the sum of sales for that provider's payment method on the
  selected day.
- **consumed** is the sum of ledger rows whose `sale_receipt_ref` matches a
  receipt from that day.
- **variance** is `consumed - expected`.
- **successful** is the amount the carrier actually confirmed. A `CONSUMED`
  row claimed while still pending (verification-off rollout) or claimed from a
  manual reference is not counted, because no carrier status confirmed it.
- **orphaned** is a confirmed payment with no live sale: either a `SUCCESSFUL`
  row with no receipt, or a `CONSUMED` row whose receipt no longer exists
  because the sale was voided. A void never frees the ledger row, so this keeps
  the customer's money visible instead of letting it vanish from both expected
  and consumed.
- **unresolved** is a `PENDING`/`UNKNOWN` ledger row with no sale. These are
  reported regardless of creation date so an old prompt cannot be forgotten.
- The flow totals (`successful`, `pending`, `unknown`, `failed`) are scoped to
  ledger rows created on the selected day; `expected`/`consumed` follow the
  sale date and `orphaned`/`unresolved` are all-time attention lists.
- A provider is `BALANCED` only when the variance is effectively zero and there
  are no orphaned or unresolved rows; otherwise it is `ATTENTION`.

The live summary lists at most 100 unresolved and 100 orphaned rows and sets
`unresolved_truncated` / `orphaned_truncated`; the per-provider counts and
amounts remain complete.

`payment_reconciliations` stores one row per provider and day with expected,
consumed, successful, pending, unknown, orphaned, unresolved, variance, status,
and a JSON `snapshot`. Migration 006 adds the table/index to an existing
database; `schema.sql` creates it on a fresh one.

The sweep only re-queries stale unresolved rows and is safe to repeat:

```bash
python -m flask --app run momo reconcile --dry-run
python -m flask --app run momo reconcile --provider AIRTEL --older-than 15 --limit 50
```

It skips rows whose provider is not configured, leaves carrier errors
unresolved for the next run, and records `RECONCILE` / `RECONCILE_ERROR` events.
On an unfiltered sweep, rows from configured carriers sort ahead of rows from
unconfigured ones, so 50 old rows from a carrier without credentials cannot
starve the carrier that can actually be checked. It never creates a prompt,
consumes a reference, or moves money.

## 5. Frontend POS Controller (`drugshop/static/js/momo.js`)

The shipped module is function-based and provider-aware:

- `loadMomo()` reads `/api/payments/health` and stores the MTN and Airtel
  `configured`, `environment`, and `currency` values.
- `syncMomoUi()` shows the panel for either `MTN_MOMO` or `AIRTEL_MOMO`, updates
  the provider title/manual hint, disables the request checkbox when that
  carrier is not configured, and switches to manual-reference mode when the
  request box is unchecked.
- `momoReferenceFor(amount, phone, method)` sends
  `/api/payments/collect` with the selected provider, reuses a paid-but-unsaved
  reference only when the provider, amount, and normalised phone all match, and
  polls an existing pending request before sending another prompt. Pending
  requests are matched the same way, so a local `077...` number matches the same
  customer entered as `+256...`.
- A paid or pending guard is not released until the sale that used its
  reference is confirmed saved. `MOMO_PAID` and `MOMO_PENDING` are persisted in
  `sessionStorage`, and the panel offers “Check pending request”, “Forget
  pending”, and “Forget paid reference” controls so a stale guard cannot block
  the counter forever.
- `waitForMomo(reference, provider)` polls
  `/api/payments/status/<provider>/<reference>` every four seconds and treats
  `FAILED`, `REJECTED`, and `TIMEOUT` as terminal. A cancel or two-minute
  timeout leaves the request pending so a later attempt can check it.
- A definitive collection failure (`status: FAILED`) is not polled; an
  ambiguous network/5xx response with `status: UNKNOWN` is polled.
- `pos.js` handles both automated and manual entry for both carriers and keeps
  `MOMO_PAID` scoped to the provider, amount, and phone. It clears the guard only
  when the saved sale response carries that reference, snapshots the basket
  before an automated prompt, and locks Clear during checkout. Receipt/sale
  rendering escapes user-controlled fields.
- `staff.html` shows the manual reference field for both carriers; it never
  sends an automated prompt. Its checkout has a `BUSY` guard, requires a
  reference for mobile money only when `verify_sales` is on, and treats a `409`
  duplicate reference as the existing receipt rather than retrying the sale.
- `/api/payments/health` and `/api/momo/health` expose `verify_sales` so both
  counter pages follow the server's verification policy.


## 6. Blueprint Registration (`drugshop/__init__.py`)

The payments blueprint is registered in the application factory and is gated to
the `pos` app in `drugshop/apps/registry.py`:

```python
def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config or DevConfig)

    from drugshop.payments.cli import register_cli as register_momo_cli
    from drugshop.payments.routes import bp as payments_bp
    from drugshop.payments.routes import callback_bp as payments_callback_bp

    app.register_blueprint(payments_bp)
    app.register_blueprint(payments_callback_bp)
    # ... other blueprints ...

    # Neither carrier can send a session cookie:
    # - add /api/momo/callback and /api/payments/airtel/callback to
    #   auth.guards.OPEN_API
    # - add payments_callback to apps.registry.ALWAYS_ON_BLUEPRINTS

    register_momo_cli(app)
    return app
```

## 7. Testing & Verification Runbook

### 1. Provision carrier credentials

MTN:

```bash
python -m flask --app run momo provision --save
python -m flask --app run momo status --check
```

`status --check` performs a token exchange only; it does not move money.

Airtel: create an app with the Collection API enabled at
<https://developers.airtel.africa>, then set `AIRTEL_CLIENT_ID` and
`AIRTEL_CLIENT_SECRET` in `.env`. A safe connectivity check is the unified
health route with `?check=1`; it forces an OAuth token exchange and does not
create a collection:

```bash
curl "http://127.0.0.1:5000/api/payments/health?check=1"
```

Airtel starts on `https://openapiuat.airtel.africa`; set
`AIRTEL_BASE_URL=https://openapi.airtel.africa` for production.

### 2. Send a test collection

The payment endpoints require a signed-in session. The MTN CLI uses the same
client:

```bash
python -m flask --app run momo collect \
  --amount 5000 --phone 0772123456 --external-id TEST-MOMO-1
python -m flask --app run momo request <reference-id>
```

For the unified API, send the provider explicitly (or omit it to use prefix
detection). These routes require the POS session cookie, so add
`-b cookies.txt` after signing in:

```bash
curl -X POST http://127.0.0.1:5000/api/payments/collect \
  -H "Content-Type: application/json" \
  -d '{"amount":5000,"phone":"0701234567","provider":"AIRTEL","idempotency_key":"TEST-AIRTEL-1"}'

curl http://127.0.0.1:5000/api/payments/status/AIRTEL/<reference-id>
```

The customer must approve the prompt; a `202` response means "request
accepted", not "paid". Airtel confirmation can come from polling, the
authenticated callback, or the stale-payment sweep.

### 3. Verify the anti-replay guard

Use a real reference returned by `momo collect` or
`/api/payments/collect` (a UUID), or set `MOMO_VERIFY_SALES=0` /
`AIRTEL_VERIFY_SALES=0` while testing the guard offline. A second checkout with
the same reference must be rejected with HTTP `409` and the message
`This MoMo reference is already on another sale`. No stock is deducted on the
second attempt.

The ledger canonicalises UUID references and upper-cases manual/SMS
references, so case, braces, and whitespace cannot bypass the duplicate check.
The claim is a conditional `UPDATE` inside the sale transaction; concurrent
checkouts may both verify with the carrier, but only one can move the ledger row
to `CONSUMED`. Voiding a sale restores stock and leaves the reference consumed.
A reference recorded by MTN cannot be used on an Airtel sale (or vice versa);
that returns `409` before stock is touched.

### 3b. Verify the callbacks

Set callback secrets and register the public HTTPS URLs with each carrier:

```bash
# .env
MOMO_CALLBACK_URL=https://shop.example/api/momo/callback?token=<secret>
MOMO_CALLBACK_SECRET=<secret>
AIRTEL_CALLBACK_URL=https://shop.example/api/payments/airtel/callback?token=<secret>
AIRTEL_CALLBACK_SECRET=<secret>
```

For a local MTN check against an existing pending reference:

```bash
curl -X POST "http://127.0.0.1:5000/api/momo/callback?token=<secret>" \
  -H "Content-Type: application/json" \
  -d '{"referenceId":"<uuid>","status":"SUCCESSFUL","amount":"5000","currency":"EUR"}'
```

For Airtel, the callback body is only used to find the reference. The route
re-queries Airtel and ignores a forged status:

```bash
curl -X POST "http://127.0.0.1:5000/api/payments/airtel/callback?token=<secret>" \
  -H "Content-Type: application/json" \
  -d '{"transaction":{"id":"<uuid>","status_code":"TS"}}'
```

Both routes accept `X-Callback-Token`; the Airtel route also accepts
`Authorization: Bearer <secret>`. A blank secret disables that route (`404`); a
wrong token returns `403`; an unknown reference returns `404` and is not
created; a reference owned by the other carrier returns `409`. Polling still
works when a callback is disabled.

### 4. Verify day-end reconciliation (Z-report)

```bash
# View expected totals for a day
curl "http://127.0.0.1:5000/api/reconciliation/calculate?date=2026-11-03"

# Daily summary with the live payment variance
curl "http://127.0.0.1:5000/api/reconciliation/daily-summary?date=2026-11-03"

# Record counted cash and till balances (upserts by rec_date)
curl -X POST http://127.0.0.1:5000/api/reconciliation \
  -H "Content-Type: application/json" \
  -d '{
    "rec_date": "2026-11-03",
    "counted_cash": 120000,
    "counted_mtn": 85000,
    "counted_airtel": 45000,
    "notes": "Evening shift closed cleanly."
  }'

# Close the shift, save counted balances, and snapshot payment variance
curl -X POST http://127.0.0.1:5000/api/reconciliation/close-shift \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-11-03",
    "counted_cash": 120000,
    "counted_mtn": 85000,
    "counted_airtel": 45000,
    "notes": "Evening shift closed cleanly."
  }'

# Inspect live + saved payment variance
curl "http://127.0.0.1:5000/api/reconciliation/payments?date=2026-11-03"
```

These endpoints require a signed-in session. Before closing, check stale
prompts; the sweep only reads carrier status and never moves money:

```bash
python -m flask --app run momo reconcile --dry-run
python -m flask --app run momo reconcile --provider AIRTEL --older-than 15
```

The UI exposes the same check as **Check Pending** in the reconciliation tab.

### 5. Run the automated checks

```bash
python -m pytest -q
python -m ruff check .
node --check drugshop/static/js/momo.js
node --check drugshop/static/js/pos.js
node --check drugshop/static/js/finance.js
```

The current suite has 428 passing tests. Payment tests blank live credentials,
inject a fake transport, and monkeypatch route/service clients; no test calls
MTN or Airtel or moves money.

For a monitored rollout where the counter is the source of truth, set
`MOMO_VERIFY_SALES=0` and/or `AIRTEL_VERIFY_SALES=0`; leave both at `1` for
normal operation.