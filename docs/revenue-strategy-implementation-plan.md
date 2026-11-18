# Revenue Strategy — Phased Implementation Plan

**Status:** Phase 5 approved 2026-11-18; first-customer rollout pending  
**Date:** 2026-11-05  
**Companion:** [`revenue-strategy.md`](revenue-strategy.md)  
**Proposed branch:** `feature/revenue-ops`  
**Target:** first paying customer on the new revenue flow, with Onzima left untouched on Legacy during the pilot

> This plan turns the revenue strategy into small, reviewable build slices. Each
> phase must pass its own tests and review gate before the next phase starts.
> The current build has entitlements but **no pricing, subscription ledger,
> invoicing, renewal tracking, or billing UI**; this plan adds those without
> turning the product into a self-service SaaS platform.

---

## 1. How to use this plan

1. Read the phase goal, scope, and exit criteria before writing code.
2. Build only that phase on the branch; do not pull later phases forward.
3. Run the targeted tests first, then the full regression suite.
4. Record the manual test evidence and review notes.
5. Fix P0/P1 defects before the gate. P2/P3 defects go to the next phase.
6. Do not start the next phase until the current gate is signed off.
7. Keep the live Onzima database out of the build loop until the rollout phase.

### Review / test / fix loop

| Step | What happens | Evidence |
|---|---|---|
| 1. Review | Confirm scope, data model, CLI/API shape, and UI copy | Signed phase checklist |
| 2. Build | Small commits, one concern per commit | Branch history |
| 3. Test | Targeted tests, full suite, lint, JS syntax, migration checks | Command output |
| 4. Manual run | Run the phase scenario on a scratch database or staging install | Screenshots / notes |
| 5. Review gate | Founder reviews the demo and accepts or rejects | Gate sign-off |
| 6. Fix window | 0.5 day reserved for P0/P1 fixes | Updated test evidence |

### Environments

- **Scratch database** — temporary SQLite DB built by the test fixtures.
- **Staging install** — a copy of the real database under `instance/staging-*`.
- **Live install** — Onzima only; do not use it for feature testing.
- **No real carrier calls** in tests. No test may move money.

---

## 2. Scope

### In scope

- A versioned price book and quote calculator.
- A per-installation subscription record.
- Operator-only activation that updates entitlements and records commercial terms.
- Manual invoice and payment recording (no gateway).
- Renewal dates, status, and a due-renewal queue.
- A read-only customer view of plan, renewal, balance, and invoices.
- Per-install reporting and a read-only portfolio rollup script.
- Onboarding, rollback, and monthly-close documentation updates.

### Out of scope for this plan

- Self-service checkout, card payments, or automated billing.
- A licence server, hard lockout, or automatic suspension.
- Multi-tenancy or a central SaaS control plane.
- A full accounting, tax, or payroll system.
- Revenue share or commission on pharmacy customer payments.
- A CRM or sales-pipeline database inside the product.

These can be revisited only when the triggers in
[`packaging-plan.md`](packaging-plan.md) §13 are met.

---

## 3. Architecture decisions to confirm

These are recommendations for Phase 0 review.

| Decision | Recommendation | Why |
|---|---|---|
| Where billing data lives | In the installation's SQLite database | Fits one-shop-per-deployment; no multi-tenancy rewrite |
| Source of truth for access | Existing `app_entitlements` | The gate already works and is tested |
| Source of truth for commercial terms | New `billing_subscriptions` table | Keeps access and money separate |
| Who can write billing data | Operator CLI only | No new operator role; customer UI stays read-only |
| Price storage | Versioned code price book | Reviewable, testable, no per-install drift |
| Quote history | Snapshot price-book version on activation | Quote totals can be audited later |
| Invoice/payment processing | Manual records | No gateway in v1; the shop's MoMo credentials are not ours |
| Portfolio reporting | Read-only script over database files | One report without centralising tenant data |
| Legacy customer | `grandfathered` subscription, monthly 0 | Keeps Onzima out of MRR but visible in reports |
| Hard expiry | Deferred | Preserve the current soft-expiry safety choice |

### Critical boundary

The MTN MoMo and Airtel Money clients in this repository collect **the shop's
customer payments into the shop's merchant account**. They must not be reused to
charge the shop for its Onzima Dawa subscription unless a separate merchant
account and explicit commercial decision exist. Subscription collection in this
plan is manual.

---

## 4. Phase overview

| Phase | Outcome | Effort | Gate |
|---|---|---:|---|
| **0** | Decisions frozen; baseline green; branch ready | 0.5–1 day | Signed decision record |
| **1** | Price book and quote CLI work | 1–2 days | Quote review against strategy |
| **2** | Subscription record and activation work | 2–3 days | Staging activation passes |
| **3** | Invoices, payments, and renewals work | 2–3 days | Full billing cycle in staging |
| **4** | Read-only plan/subscription UI and API | 2–3 days | UI matrix passes |
| **5** | Reporting, rollup, and first paid rollout | 1–2 days | First paid customer + close |
| **6** | Optional automation | Deferred | Triggers met |

**Rough total:** 9–14 developer days, excluding commercial selling time and
the 0.5-day fix window per phase.

---

## 5. Phase 0 — Decisions and baseline

### Goal

Freeze the commercial rules that the build depends on, create a safe branch, and
prove the current suite is green before touching code.

### Tasks

1. Review [`revenue-strategy.md`](revenue-strategy.md) and approve the draft
   price card.
2. Decide the items in Appendix A:
   - Core, Pro, Growth add-on, Tender, and combined quote rules.
   - Setup-discount policy and approval limit.
   - Invoice numbering and due-date policy.
   - Subscription payment methods and currency.
   - Whether invoice amounts are tax-inclusive.
3. Confirm the pilot rule: no bundle announcement, price sheet, or live plan
   change for Onzima before the observation window ends on 2026-11-09.
4. Create `feature/revenue-ops` from the current branch.
5. Run the baseline:
   - `python -m pytest -q`
   - `python -m ruff check .`
   - `node --check` on every JavaScript file
   - smoke script against a staging install
6. Back up the live database and record the SHA256.
7. Create the phase checklist in Appendix D.

### Deliverables

- Completed decision record (Appendix A).
- Baseline command output and backup hash.
- Branch name and first commit.

### Review gate

- [x] Prices and discount policy signed off.
- [x] Invoice/payment scope signed off.
- [x] Baseline suite green.
- [x] Backup verified with `PRAGMA integrity_check = ok`.
- [x] No live plan or feature change made.

**Sign-off:** Product owner, 2026-11-05. Baseline: 445 tests passed, Ruff clean,
17 JS files parsed. Backup: `instance/backups/drugshop-pre-revenue-ops-20261105-101640.db`
(SHA256 `646288bd062b135023af88987c6a8e08f2898c75db568fed4a890f466388c94d`,
integrity `ok`). The pending `006_payment_reconciliation.sql` migration was
rehearsed on a backup copy, then applied live; plan remained Legacy and all
existing business row counts were unchanged.

**Re-verification (2026-11-09):** 507 tests passed (445 Phase 0 baseline plus
62 added since), Ruff clean, all 17 JS files parsed. `scripts/smoke.ps1` passed
against a scratch copy of `instance/staging-core/drugshop.db` (Core plan). The
backup SHA256 and `PRAGMA integrity_check` still match, and the live database
remains on Legacy with `006_payment_reconciliation.sql` applied and no billing
tables.

### Rollback

None for the revenue build; docs and branch only. The independent additive
`006_payment_reconciliation.sql` migration can be left in place and does not
change the plan.

---

## 6. Phase 1 — Price book and quote engine

### Goal

Create one testable source of truth for prices and a quote command that the
founder can use in a sales conversation in under five minutes.

### Build

- New package: `drugshop/billing/`
  - `catalog.py` — price book, version, quote rules, pure functions.
  - `cli.py` — `flask --app run revenue ...` commands.
  - `__init__.py` — package docstring and exports.
- Register the CLI in the application factory.
- Tests:
  - `tests/test_billing_catalog.py`
  - `tests/test_billing_cli.py`

### Quote rules

- Base offers: `core`, `pro`, `tender`.
- Growth is an add-on that requires Pro.
- Tender can be standalone or added to Core/Pro/Growth.
- Growth quote = Pro + Growth add-on.
- Combined quote = base pharmacy bundle + Tender.
- Combined defaults to the sum of lines until a packaged discount is approved.
- Legacy cannot be quoted.
- Monthly fees cannot be discounted.
- Setup discount cannot be negative, exceed the setup total, or exceed the
  approved 100,000 UGX v1 cap.
- Unknown bundles, missing dependencies, and zero/negative amounts fail clearly.
- Every quote returns a `price_book_version`.

### Commands

```bash
flask --app run revenue pricebook
flask --app run revenue quote core
flask --app run revenue quote pro
flask --app run revenue quote pro --add growth
flask --app run revenue quote pro --add tender
flask --app run revenue quote tender
flask --app run revenue quote pro --setup-discount 100000 --json
```

### Manual verification

Produce and review six quotes:

| Scenario | Expected setup | Expected monthly |
|---|---:|---:|
| Core | 400,000 | 120,000 |
| Pro | 600,000 | 180,000 |
| Growth (Pro + add-on) | 800,000 | 230,000 |
| Tender standalone | 300,000 | 150,000 |
| Pro + Tender | 900,000 | 330,000 |
| Pro with 100,000 setup discount | 500,000 | 180,000 |

Also verify that `legacy` is refused with a clear message, and that a discount
above the approved 100,000 UGX cap is refused.

**Review evidence (2026-11-09):** all six quotes match the table. `legacy` and
discounts above 100,000 UGX exit non-zero with clear messages. The 55 targeted
billing tests and the 509-test full suite pass; Ruff is clean; the quote group
runs without importing the database layer. No schema, migration, or entitlement
files changed in Phase 1.

### Tests

- Exact totals for each scenario.
- Growth without Pro is rejected.
- Tender standalone and combined both work.
- Setup discount boundary (100,000 cap and setup subtotal) and monthly-discount
  rejection.
- JSON output is stable and includes line items and version.
- CLI exits non-zero with a clear message on invalid input.
- No database connection is required.

### Review gate

- [x] Founder agrees the six quotes.
- [x] The quote output is readable in a live sales call.
- [x] Price-book version is visible.
- [x] No schema or entitlement change was made.

**Sign-off:** Product owner, 2026-11-09.

### Rollback

Remove the new package and CLI registration. No data migration.

---

## 7. Phase 2 — Subscription ledger and activation

### Goal

Record the commercial agreement for the installation and make activation a
single, auditable operator action.

### Build

- Migration `007_billing_subscriptions.sql` (006 is already used by
  `006_payment_reconciliation.sql`):
  - `billing_subscriptions`
  - `billing_events`
- Mirror the tables in `drugshop/schema.sql` for fresh databases.
- New service: `drugshop/billing/service.py`.
- Extend `drugshop/billing/cli.py` with activation and status commands.
- Tests:
  - `tests/test_billing_migrations.py`
  - `tests/test_billing_service.py`
  - `tests/test_billing_cli.py`

### Data model summary

Full proposed schema is in Appendix B.

`billing_subscriptions` stores:

- customer and contact details;
- bundle;
- status (`pending`, `active`, `past_due`, `cancelled`, `expired`, `grandfathered`);
- currency;
- setup fee and monthly fee;
- start date and current period dates;
- price-book version;
- notes and timestamps.

`billing_events` records every commercial action with actor, detail, and time.

### Activation flow

1. Validate bundle, dates, fees, currency, and operator input.
2. Write a `pending` subscription row and a `billing_events` entry.
3. Call the existing entitlement service to set the bundle.
4. Mark the subscription `active`.
5. Return the plan, subscription status, and next renewal date.

If step 3 fails, the subscription stays `pending` and the operator can retry.
The entitlement change is not rolled back silently; the error tells the operator
what state the install is in. Both services must be idempotent.

### Commands

```bash
flask --app run revenue activate pro \
  --customer "Example Pharmacy" \
  --contact "+256..." \
  --start 2026-11-05 \
  --period-end 2027-11-05 \
  --actor "Andama" \
  --notes "signed Pro, one year"

flask --app run revenue show
flask --app run revenue renew --period-end 2027-11-05 --actor "Andama"
flask --app run revenue status active --actor "Andama"
flask --app run revenue status past_due --notes "November invoice unpaid"
```

Default fees come from the price book. Any manual override requires
`--override-reason` and is written to `billing_events`.

Legacy activation requires `--grandfathered`, sets monthly to 0, and is excluded
from MRR.

### Tests

- Fresh database migration creates both tables.
- Existing database migration is additive and idempotent.
- Activation creates subscription + entitlements that agree.
- Re-running the same activation is a no-op.
- A failed entitlement step leaves `pending`, not `active`.
- Legacy without `--grandfathered` is refused.
- Legacy with `--grandfathered` stores monthly 0.
- Status transitions are validated.
- Renewal extends the period and writes an event.
- CLI returns helpful errors for unknown bundle/app, bad dates, and negative fees.
- `billing_events` contains actor and reason for every change.

### Manual verification

On a staging Core install:

1. Activate Pro.
2. Confirm `flask --app run plan show` and `/api/apps` both report Pro.
3. Confirm the subscription row, dates, fees, and event log.
4. Restart the app; confirm the plan and subscription persist.
5. Restore the staging backup and confirm the pre-activation state returns.

### Review gate

- [x] Activation is reproducible from a fresh database in under 15 minutes.
- [x] Entitlements and subscription agree after activation.
- [x] Failure path leaves an obvious, recoverable `pending` state.
- [x] Legacy remains untouched on the live installation.
- [x] Migration dry run on a copy passes with business row counts unchanged.

**Implementation evidence (2026-11-09):** migration 007 applies cleanly to
fresh, legacy, and staging databases; the full suite is **556 passed** (73
targeted billing/migration tests), Ruff is clean. On a scratch copy of
`instance/staging-core/drugshop.db` (Core, migrations 001–002), migration 007
was applied and Pro was activated at the price-book fees (600,000 setup /
180,000 monthly, 2026-11-09 → 2027-11-09). `revenue show` reported `[OK]`,
`plan show` and `GET /api/apps` both reported Pro with expiry 2027-11-09, and
the event log recorded the actor, terms, and reason. A renewal to 2028-11-09
and past_due → active status changes also logged and reconciled. Every command
ran in a fresh process, proving persistence; restoring the pre-activation
backup returned the install to Core with no subscription. A fresh database
initialized from 001–007 activated Pro successfully. `scripts/dry_run_packaging.py`
on a copy of the live database applied 007, preserved all 19 existing business
table row counts, and left the source hash unchanged during the dry run. The
live root database stayed on Legacy/migration 006 with no billing tables during
verification. A later `python run.py` startup (2026-11-09 03:37:58) applied
migration 007 additively: the plan remains Legacy, both billing tables are
empty, and all business and plan rows still match the verified post-pilot
backup (only live `login_events` audit rows differ). The zero-byte
`instance/drugshop.db` artifact was removed, and the test fixture now passes its
temporary database into `create_app()` so a missing instance file can never
fall back to the live database.

**Sign-off:** Approved 2026-11-12; the product owner authorized moving to
Phase 3.

### Rollback

The migration is additive. Disable the new CLI, restore the pre-phase backup if
needed, or leave the tables unused. Do not drop business tables to roll back.

---

## 8. Phase 3 — Invoices, payments, and renewals

### Goal

Give the operator a simple, auditable record of what was billed, what was
collected, and what is due next — without pretending to be an accounting system.

### Build

- Migration `008_billing_invoices.sql`:
  - `billing_invoices`
  - `billing_payments`
- Extend `drugshop/billing/service.py`.
- Extend the `revenue` CLI:
  - `invoice setup`
  - `invoice monthly`
  - `invoice list`
  - `invoice show`
  - `invoice void`
  - `payment record`
  - `renewals`
- Tests:
  - `tests/test_billing_invoices.py`
  - `tests/test_billing_payments.py`
  - `tests/test_billing_renewals.py`

### Rules

- Invoice kinds: `setup`, `monthly`, `addon`, `other`.
- Invoice statuses: `draft`, `unpaid`, `partial`, `paid`, `void`.
- Payment methods are labels only: `cash`, `bank`, `mtn_momo`, `airtel_money`, `other`.
- Setup invoice defaults to the agreed setup fee.
- Monthly invoice defaults to the agreed monthly fee for the period.
- Partial payments are allowed; overpayment is rejected.
- A voided invoice cannot accept new payments.
- Invoice numbers are `INV-YYYYMM-####`, unique and sequential per issue month.
- At most one non-void setup invoice exists per installation; it must be voided
  before another is issued.
- Monthly invoice periods may not overlap a non-void monthly invoice.
- Voiding keeps the row for audit and reports a zero balance. An invoice with
  recorded payments cannot be voided; money already received must be handled by
  the operator first.
- Invoice numbering and payment balance checks run inside `BEGIN IMMEDIATE`, so
  two operator runs cannot reuse a number or pay the same balance twice.
- Renewal queue defaults to 14 days before `current_period_end`.
- No gateway call is made when recording a payment.

### Commands

```bash
flask --app run revenue invoice setup --due 2026-11-12
flask --app run revenue invoice monthly \
  --period-start 2026-11-05 --period-end 2026-12-05 --due 2026-11-05
flask --app run revenue invoice list
flask --app run revenue invoice show INV-202611-0001
flask --app run revenue invoice void INV-202611-0002 --reason "wrong period"
flask --app run revenue payment record INV-202611-0001 \
  --amount 600000 --method bank --reference "FT-..." --received-by "Andama"
flask --app run revenue renewals --days 14
```

### Tests

- Setup and monthly invoice totals match the subscription.
- Invoice numbering is unique and sequential.
- Partial payment moves the invoice to `partial`.
- Full payment moves it to `paid`.
- Overpayment is rejected with the remaining balance.
- A void invoice rejects payment.
- A second setup invoice is refused until the first is voided.
- An overlapping monthly invoice is refused; adjacent periods are accepted.
- An invoice with recorded payments cannot be voided.
- Concurrent payment attempts cannot overpay or duplicate a payment.
- SQLite enforces the setup/monthly money guards with partial unique indexes.
- Negative or zero amounts are rejected.
- Renewal window includes dates inside the window and excludes later dates.
- CLI output is clear and machine-readable with `--json`.
- No network client is invoked.

### Manual verification

Run one complete cycle on staging:

1. Create the setup invoice.
2. Record a partial payment; confirm balance.
3. Record the remainder; confirm `paid`.
4. Create the first monthly invoice.
5. Run `renewals --days 14`; confirm the due list.
6. Renew and confirm the next period.
7. Export/inspect the rows and reconcile to the quote.

### Review gate

- [x] One setup and one monthly invoice reconcile exactly to Phase 1 quotes.
- [x] Partial and full payment states are correct.
- [x] Renewal queue is correct around the 14-day boundary.
- [x] No payment gateway or carrier call was made.
- [x] The operator can explain the balance from the CLI alone.
- [x] A wrong invoice can be voided and reissued without hand-editing SQLite.
- [x] Concurrent payment attempts cannot overpay or duplicate a payment.

**Implementation evidence (2026-11-12, re-reviewed):** migration 008 applies
cleanly to fresh, Phase 2, and legacy databases; the full suite is **602
passed** (56 targeted billing/migration tests), Ruff is clean.

The re-review hardened the money paths:

- Invoice numbering and the payment balance check now run inside
  `BEGIN IMMEDIATE`, so two operator processes cannot reuse a number or pay the
  same balance twice. A two-thread test proves only one of two concurrent
  600,000 UGX payments lands on a 600,000 UGX invoice.
- `billing_invoices` carries partial unique indexes: at most one non-void setup
  invoice per installation, and at most one non-void monthly invoice per
  period. The service supplies friendly errors first; SQLite enforces them as
  the backstop.
- Monthly invoices may not overlap a non-void monthly invoice; adjacent periods
  remain valid.
- `invoice show` prints the payment ledger so the balance is explainable from
  the CLI, and `invoice void` records the operator and reason while keeping the
  row for audit. A void invoice reports a zero balance. An invoice with
  recorded payments cannot be voided.
- Invoice lookups accept lower-case input and `get_db()` waits briefly on a
  writer lock instead of failing instantly when the shop app is open.

Setup and monthly invoice amounts are asserted equal to the Pro quote
(600,000 + 180,000 UGX), and a separate test proves a founder-approved setup
discount is billed at the agreed 500,000 UGX rather than the 600,000 UGX list
price. The manual cycle on a throwaway database created setup invoice
`INV-202611-0001` for 600,000 UGX, recorded a 300,000 UGX partial payment
(balance 300,000), completed it (paid, balance 0), showed the two payments from
the CLI, created monthly invoice `INV-202611-0002` for 180,000 UGX with period
2026-11-05..2026-12-05, voided a wrong December invoice and reissued it, returned
the subscription in `revenue renewals --days 14 --as-of 2026-11-21`, renewed to
2027-01-05, and confirmed invoice list, subscription, and entitlements
reconciled. The dry run on a copy of the live database applied only
`008_billing_invoices.sql`, preserved all 21 existing table row counts, passed
the Core/Legacy access matrices and restore rehearsal, and left the source hash
unchanged. At Phase 3 sign-off the live root database remained on migration 007
with both Phase 2 billing tables empty; migration 008 applied additively on
2026-11-18.

**Sign-off:** Approved 2026-11-16; the product owner authorized moving to
Phase 4.

### Rollback

Additive tables; disable the commands and restore the phase backup if needed.
No business data is deleted.

---

## 9. Phase 4 — Read-only subscription UI and API

### Goal

Show the customer their plan, renewal date, balance, and invoices without giving
them a way to change commercial terms.

### Build

- New `drugshop/billing/routes.py` blueprint.
- Register it as always-on in the entitlement map so Core and Tender installs can
  still see their own plan.
- `GET /api/subscription` — any signed-in user; limited fields.
- `GET /api/subscription/invoices` — admin only.
- `GET /api/subscription/invoices/<invoice_no>` — admin only.
- Extend the **Plan & Apps** card in `index.html`:
  - plan name and status;
  - start and renewal date;
  - monthly fee and currency;
  - outstanding balance;
  - admin-only invoice list;
  - support/upgrade link.
- Extend `drugshop/static/js/core/apps.js` and `manage.js`.
- Add styles consistent with the current design system.
- Set `SUPPORT_WHATSAPP` for the pilot and staging demos.
- Tests:
  - `tests/test_billing_api.py`
  - `tests/test_billing_ui.py`

### API shape

```json
{
  "plan": {
    "bundle": "pro",
    "label": "Pro",
    "status": "active",
    "started_on": "2026-11-05",
    "current_period_end": "2027-11-05",
    "monthly_fee": 180000,
    "currency": "UGX"
  },
  "balance": 0,
  "renewal_due": false,
  "support": {"whatsapp": "..."}
}
```

Invoices are returned separately to admins, with amount, status, due date,
payments, and balance. Internal notes, price-book internals, and margins are
never returned.

### Tests

- Login required for all new endpoints.
- Any signed-in user can read the limited subscription summary.
- Only admins can read invoices.
- Invoice detail is scoped to the install; no enumeration of other customers.
- Hidden fields are not present in the payload.
- UI markup and JS references exist.
- Text is escaped before insertion into the DOM.
- Status labels render correctly for active, past_due, expired, and grandfathered.
- Core, Pro, Growth, Tender, combined, and Legacy plans render without errors.

### Manual verification matrix

| Plan | Launcher | Plan card | Invoices | Upgrade CTA |
|---|---|---|---|---|
| Core | Core apps only | Core, renewal, balance | Admin only | Visible |
| Pro | Pro apps | Pro, renewal, balance | Admin only | Visible |
| Growth | Pro + alerts | Growth, renewal, balance | Admin only | Visible |
| Tender | Tender only | Tender, renewal, balance | Admin only | Visible |
| Combined | Pro + Tender | Combined, renewal, balance | Admin only | Visible |
| Legacy | All apps | Grandfathered, no MRR | Admin only | Hidden or neutral |

Check desktop and 390px mobile widths, keyboard focus, and zero unexpected 403s.

### Review gate

- [x] Customer can see what they own and when it renews.
- [x] There is no edit, upgrade, or payment button that changes data.
- [x] Admin invoice view is read-only.
- [x] Upgrade CTA opens the configured support link.
- [x] No console errors on any plan. (Static parse and the automated plan
  matrix pass; the product owner accepted the gate on 2026-11-18.)

**Implementation evidence (2026-11-16):** Phase 4 adds the always-on
`billing` blueprint with `GET /api/subscription`, an admin-only invoice list,
and an admin-only invoice detail. The full suite is **625 passed** (35 targeted
Phase 4 tests), Ruff is clean, and `node --check` passes for `core/apps.js` and
`manage.js`. A throwaway-database smoke run returned the Legacy grandfathered
fallback, a Pro summary of 180,000 UGX/month with a 680,000 UGX balance, the
two-invoice ledger, a lower-case invoice lookup, and staff summary `200` /
invoices `403`. Anonymous calls return `401`; an unknown invoice returns `404`;
reads fail open before the billing migration. Automated checks cover
Core/Pro/Growth/Tender/Legacy, balance and `renewal_due`, void-zero balances,
escaped invoice rows, and the absence of notes, row ids, setup fees,
price-book internals, and contact details from the payloads. The Plan & Apps
card contains no form, input, button, or write callback. At Phase 4 sign-off the
live root database was on migration 007 with `billing_subscriptions` empty and
`billing_invoices` absent. A normal `python run.py` startup on 2026-11-18 applied
the additive 008 migration; `instance/drugshop.db` was not recreated.
`SUPPORT_WHATSAPP` was blank at Phase 4 sign-off; the pilot number was supplied
on 2026-11-18 and is configured through the environment only (`.env` locally,
the Render dashboard in production), never committed.

**Sign-off:** Approved 2026-11-18; the product owner authorized moving to
Phase 5.

### Rollback

Remove the blueprint, template additions, and JS calls. Billing tables remain
idle; no data is lost.

---

## 10. Phase 5 — Reporting, rollup, and first paid rollout

### Goal

Close the loop: produce a monthly revenue view, rehearse on a database copy,
then onboard the first paying customer without disturbing Onzima.

### Build

- `flask --app run revenue report --format json|csv`:
  - MRR, setup collected, payments collected, outstanding balance;
  - plan mix;
  - renewals due;
  - grandfathered and excluded rows;
  - the `as_of` date used for the renewal window.
- Reporting opens the installation database read-only, in one snapshot.
- `scripts/revenue_rollup.py`:
  - accepts one or more database paths or a directory;
  - opens databases read-only, in one snapshot each;
  - rejects a portfolio that mixes currencies;
  - emits CSV/JSON;
  - never writes to a customer database;
  - tests with two synthetic databases.
- Update:
  - [`onboarding-runbook.md`](onboarding-runbook.md) — subscription activation,
    invoice, payment, renewal.
  - [`rollback-runbook.md`](rollback-runbook.md) — billing rollback and restore.
  - [`revenue-strategy.md`](revenue-strategy.md) — link this plan and record
    approved prices.
- Add a monthly-close checklist and renewal-reminder checklist.

### Rollout sequence

1. **Database copy:** apply migrations, activate a synthetic customer, run the
   full cycle, compare row counts before/after.
2. **Staging:** run Core → Pro → Growth → Tender activation and report.
3. **Onzima:** do not change the plan. If desired, create a grandfathered
   subscription with monthly 0 only after the pilot exits.
4. **First paying customer:** quote → setup invoice → payment → activate →
   handover → 30-day check-in.
5. **Review:** founder checks the report against the invoice, quote, and plan.

### Tests

- Full suite: `python -m pytest -q`.
- Lint: `python -m ruff check .`.
- JS syntax: every file passes `node --check`.
- Smoke matrix: Core, Pro, Growth, Tender, Legacy, combined.
- Migration dry run on a real database copy; business row counts unchanged.
- Rollup totals equal the sum of the individual installation reports.
- Rollup refuses to write or mutate a source database.
- Backup and restore rehearsal passes.

### Review gate

- [x] First paid customer is active, invoiced, and visible in the report.
- [x] Report totals reconcile to the manual calculation.
- [x] Onzima's live plan is unchanged unless deliberately grandfathered.
- [x] Onboarding and rollback runbooks match the shipped commands.
- [x] No regressions, no unexpected 403s, no data loss.

**Implementation evidence (2026-11-18):** Phase 5 adds
`flask --app run revenue report --format text|json|csv` with MRR, setup and
monthly invoiced amounts, setup and total collections, outstanding balance,
plan mix, renewal queue, grandfathered/excluded rows, and the `as_of` date used
for the renewal window. The report opens the installation database with
`mode=ro`, `PRAGMA query_only`, and one read transaction, so reporting cannot
write and cannot mix committed states. The report and the read-only
`scripts/revenue_rollup.py` share `drugshop/billing/report.py`; the rollup opens
every source the same way, hashes each file before and after the read, rejects a
mixed-currency portfolio, and emits per-installation CSV or an aggregated JSON
portfolio. The onboarding and rollback runbooks now use the billing CLI, and
new monthly-close and renewal-reminder checklists cover the operating cadence.
`scripts/README.md` documents the rollup.

Verification: full suite **647 passed** (21 targeted Phase 5 revenue tests plus
the live-database guard), Ruff is
clean, and every file under `drugshop/static/js/` passes `node --check`. The
report CLI was hash-checked on a copy of the live database: the source was
byte-identical after the run. The manual rehearsal copied the live database
read-only, applied only migration 008, preserved all 21 existing business table
counts, and produced a Pro report with 180,000 UGX MRR and a 680,000 UGX balance
after a 100,000 UGX partial payment. The plan matrix reconciled: Core
120,000/400,000, Pro 180,000/600,000, Growth 230,000/800,000, Tender
150,000/300,000, Legacy grandfathered at 0, and a combined Pro + Tender install
with a 330,000 UGX agreed monthly fee. A six-installation rollup reported MRR
1,010,000, exactly the sum of the individual reports.
`scripts/dry_run_packaging.py` applied only `008_billing_invoices.sql`, preserved
21 business table counts, passed the Core/Legacy access matrices and restore
rehearsal, and left the source hash unchanged. The live root database is now on
migration 008, applied by a normal `python run.py` startup during this review.
The owner's 10:41 login updated `last_login_at`, and live counts remain users 2,
products 8, batches 7, sales 12, patients 3, and tender_docs 11 with
`PRAGMA integrity_check` returning `ok`, matching the pilot progression. It has
six Legacy entitlement rows and zero billing subscriptions, invoices, and
payments; no business rows were lost, and `instance/drugshop.db` was not
recreated.

Re-review note: the report is a cumulative snapshot, not a period filter. The
monthly-close checklist now states that monthly movement is the current report
minus the previous close. The service already refuses to void a paid or partly
paid invoice, so collected totals cannot diverge through a voided paid invoice.
A local-only known risk remains: CSV cells containing formula prefixes from
operator-entered customer names could execute in a spreadsheet; treat operator
CSV output as trusted internal data or open it with formula evaluation disabled.

**Rollout rehearsal (2026-11-18):** the full operator cycle was run end to end on
a byte-for-byte copy of the live database
(`instance/rehearsal/rehearsal-first-customer.db`), with `DRUGSHOP_DB` pointed at
the copy for every command. Sequence: `revenue pricebook` →
`revenue quote pro` → `revenue activate pro` (customer, contact, period
2026-11-18..2026-12-17) → `revenue invoice setup` → `revenue payment record`
(bank, 600,000) → `revenue invoice monthly` → `revenue payment record`
(mtn_momo, 180,000) → `revenue invoice monthly` for the next period → deliberately
wrong invoice voided and reissued → `revenue renew --period-end 2027-01-17` →
`revenue renewals --days 14 --as-of 2027-01-05` → `revenue report` (text and JSON)
→ `scripts/revenue_rollup.py`.

Results: the report showed MRR 180,000 UGX, setup invoiced 600,000, monthly
invoiced 360,000 (the voided invoice excluded), total invoiced 960,000, payments
collected 780,000, outstanding 180,000, 4 invoices (2 paid, 1 unpaid, 1 void),
and no renewals due at the current date. The rollup over the rehearsal directory
matched the single-installation report line for line. Renewals listed the
subscription as `due in 12 days` at as-of 2027-01-05, confirming the 14-day
window and the `--as-of` override. The service refused a payment against the
voided invoice (`invoice ... is void and cannot accept payments`) and refused an
overpayment (`remaining balance is 180,000 UGX`), so the close checklist's manual
failure modes are enforced by code, not convention. The source copy's hash
changed as expected; the live database hash stayed
`eb0d5e5e9f1ea04e9e1725ec733509162946eba5b49d49e05435f49d348aef28` with
`integrity_check` `ok`, zero subscriptions, and zero invoices. The read-only
portfolio rollup over the repository root reported one grandfathered Legacy
installation, MRR 0, and no invoices, also leaving the live hash unchanged.

**First paid customer (2026-11-18):** Andama Moses was activated on Pro on his
own installation, not in the pilot ledger:
`instance/customers/andama-moses.db` with uploads at
`instance/customers/andama-moses-uploads/`. The installation was created fresh
with `DRUGSHOP_BUNDLE=core`, migrated to 008, and seeded; `revenue activate pro`
then granted `pos`, `inventory`, `patients`, and `finance`. Setup 600,000 was
invoiced and collected by MTN MoMo with **no transaction reference**, because the
payer could not produce one; the payment note records that rather than inventing
an identifier that could never reconcile. The first monthly invoice for
2026-11-18..2026-12-17 was issued at 180,000 and remains unpaid. Bootstrap
accounts were corrected on the fresh installation (the `admin` display name set
to the owner and the seeded `grace` row removed); the default bootstrap password
still needs `reset-password` before handover. `ensure_admin()` seeding the pilot
staff names into every new installation is recorded as a known gap with no CLI
for the display name.

Report: MRR 180,000, total invoiced 780,000, payments collected 600,000,
outstanding 180,000, two invoices (one paid, one unpaid). The read-only
portfolio rollup over `instance/customers` returned one installation, one paying,
the same 180,000 MRR and 180,000 outstanding, and a renewal `due in 7 days` at
as-of 2026-12-10. The pilot database hash remained
`eb0d5e5e9f1ea04e9e1725ec733509162946eba5b49d49e05435f49d348aef28`.

**Incident during onboarding:** the first attempt wrote the Pro subscription to
the **pilot** database (`drugshop.db`), which revoked the `tender` and `alerts`
entitlements that installation still uses. The verified pre-change backup
(`instance/backups/drugshop-pre-onboarding-20261118-140834.db`, hash-identical to
the live file) was restored immediately; the pilot is back on `legacy` with all
six apps active, zero billing rows, `integrity_check` `ok`, and unchanged
business counts (users 2, products 8, batches 7, sales 12, patients 3,
tender_docs 11). The customer was then onboarded on a separate installation as
above. `revenue activate` intentionally revokes entitlements the target bundle
does not include, so it is destructive on a Legacy pilot; the onboarding runbook
now requires checking the database path and current plan before any commercial
write and states the flat `instance/customers/<slug>.db` portfolio layout that
the rollup expects.

**Open item:** reconcile the first monthly close to the report and record the
founder review. Until then the Phase 5 rollout gate is not fully closed.

`SUPPORT_WHATSAPP` was configured on 2026-11-18. The environment value flows
through `config.py` into `/api/subscription` and `/api/apps`, and the Plan & Apps
card plus the upgrade modal build `https://wa.me/<number>` links from it. The
number itself is environment-only (`.env` locally, Render dashboard in
production); only the blank placeholder is committed.

**Sign-off:** Implementation approved 2026-11-18 and committed on
`feature/revenue-ops`. The first-customer rollout gate, first monthly close,
and founder report review remain open.

### Rollback

Revert the release and restore the verified backup. The billing tables are
additive, so older code can ignore them. Re-run `plan set` only if access itself
must be restored.

---

## 11. Phase 6 — Deferred automation

Do **not** build these in this plan:

- self-service checkout;
- automated card or mobile-money subscription collection;
- a licence server or hard lockout;
- dunning emails or automatic suspension;
- a central multi-tenant operator console;
- accounting-system integration;
- per-user or usage-based billing.

Revisit only when at least one is true:

1. More than 20 paying installations make per-install reporting too slow.
2. Customers ask to buy or renew without operator contact.
3. Manual invoicing produces recurring errors.
4. A second operator needs a portfolio view.
5. The business has a separate merchant account and a clear mandate to collect
   subscriptions online.

---

## 12. Test and review workflow

### Test layers

| Layer | What it proves | Command |
|---|---|---|
| Unit | Quote math, rules, service transitions | `python -m pytest tests/test_billing_*.py -q` |
| Migration | Fresh and existing databases upgrade safely | `python -m pytest tests/test_migrations.py tests/test_billing_migrations.py -q` |
| API | Auth, shape, admin-only invoices, no leakage | `python -m pytest tests/test_billing_api.py -q` |
| CLI | Happy paths and clear failures | `python -m pytest tests/test_billing_cli.py -q` |
| UI | Markup, plan matrix, escaping | `python -m pytest tests/test_billing_ui.py -q` |
| Regression | Nothing existing broke | `python -m pytest -q` |
| Lint | Style and static issues | `python -m ruff check .` |
| JS syntax | Frontend files parse | `node --check` each file |
| Smoke | Login, plan, gates, pages, backup | `scripts/smoke.ps1` on staging |

### Bug triage

| Severity | Definition | Action |
|---|---|---|
| **P0** | Data loss, money error, live lockout, security issue | Stop; fix before any gate |
| **P1** | Wrong totals, activation mismatch, broken gate | Fix before the phase gate |
| **P2** | UI defect, confusing message, missing edge case | Fix in the next phase or before rollout |
| **P3** | Cosmetic or wording issue | Backlog |

### Phase gate checklist

Copy this into each phase review:

- [ ] Scope matches this plan; no unapproved extras.
- [ ] Targeted tests pass.
- [ ] Full suite passes.
- [ ] Ruff is clean.
- [ ] Every changed JS file passes `node --check`.
- [ ] Migration tested on fresh and existing databases.
- [ ] Business row counts unchanged.
- [ ] Manual scenario recorded.
- [ ] Rollback rehearsed or explicitly deemed unnecessary.
- [ ] Docs updated.
- [ ] Reviewer sign-off and date.

---

## 13. Definition of done for v1

- [ ] Price book v1 is approved and versioned.
- [ ] Quote CLI produces the six approved quotes.
- [ ] Activation writes subscription and entitlements that agree.
- [ ] Setup and monthly invoices can be recorded and reconciled.
- [ ] Partial and full payments are correct; overpayment is blocked.
- [ ] Renewal queue works at the 14-day boundary.
- [ ] Customer plan card is read-only and correct on every plan.
- [ ] Admin invoice view is read-only and scoped.
- [ ] Portfolio rollup reconciles to individual installs.
- [ ] First paying customer is activated and invoiced.
- [ ] Onzima remains on Legacy unless deliberately grandfathered.
- [ ] Full suite, ruff, JS syntax, and smoke matrix are green.
- [ ] Onboarding, rollback, and monthly-close docs are updated.
- [ ] No P0/P1 defects remain open.

---

## 14. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Billing data stored per installation is fragmented | Slow portfolio view | Read-only rollup script; revisit central console at 20+ customers |
| Operator CLI is forgotten or misused | Wrong plan or wrong invoice | Defaults from price book; overrides require a reason; audit events |
| Subscription and entitlements drift | Customer pays for the wrong access | Activation writes both; a reconciliation test compares them |
| Soft expiry allows unpaid use | Revenue leakage | Renewal queue, 14-day reminder, manual `past_due`; revisit hard expiry later |
| Manual invoicing errors | Disputed balances | Invoice snapshots, payment ledger, reconciliation gate |
| Customer sees internal notes | Trust/security issue | Never store margins or internal notes in the install DB |
| Reusing shop MoMo credentials for subscription charges | Wrong merchant account, compliance risk | Explicitly out of scope; manual collection only |
| Price changes create inconsistent quotes | Margin and trust loss | Versioned price book; activation snapshots the version |
| Scope expands into a full SaaS platform | Delay and risk | Non-goals list; Phase 6 deferred |

---

## 15. Open decisions

| # | Decision | Needed by | Recommendation |
|---:|---|---|---|
| 1 | Final Core/Pro prices | Phase 1 gate | Use 400k/120k and 600k/180k as v1 draft |
| 2 | Growth price and whether future AI is included | Phase 1 gate | 200k setup + 50k/month; no AI promise |
| 3 | Tender standalone price | Phase 1 gate | 300k setup + 150k/month |
| 4 | Combined Pro + Tender price | Phase 1 gate | Sum of lines until a package is approved |
| 5 | Setup-discount limit | Phase 0 | Founder approval; never discount monthly |
| 6 | Invoice due date | Phase 3 | Setup due before activation; monthly in advance |
| 7 | Tax treatment | Phase 3 | Decide before the first invoice; v1 stores a total only |
| 8 | Subscription payment methods | Phase 3 | Cash, bank, MTN, Airtel, other — recorded manually |
| 9 | Hard expiry | After first renewal | Keep soft in v1 |
| 10 | Central console | After 20 customers | Rollup script only for now |

---

## Appendix A — Phase 0 decision record

Fill this in and sign before Phase 1.

| Item | Decision |
|---|---|
| Core setup / monthly | **400,000 / 120,000 UGX** |
| Pro setup / monthly | **600,000 / 180,000 UGX** |
| Growth add-on setup / monthly | **200,000 / 50,000 UGX**; requires Pro |
| Tender setup / monthly | **300,000 / 150,000 UGX** |
| Combined quote rule | Sum of lines; Pro + Tender = **900,000 setup / 330,000 monthly** |
| Setup-discount policy | Founder approval per deal; cap **100,000 UGX** in v1; never discount monthly |
| Monthly-discount policy | No discount |
| Currency | UGX |
| Tax treatment | Totals are **tax-inclusive** in v1; no separate tax line until VAT/accounting advice |
| Invoice numbering | `INV-YYYYMM-####` |
| Invoice due policy | Setup due before activation; monthly due in advance at period start; 14-day renewal queue |
| Subscription payment methods | Cash, bank transfer, MTN MoMo, Airtel Money, other; recorded manually |
| Billing data location | Installation database |
| Billing write access | Operator CLI only; customer UI read-only |
| Legacy treatment | Grandfathered, monthly 0, excluded from MRR |
| Pilot announcement rule | No bundles/price sheet or live plan change before 2026-11-09 |

Approved by: Product owner (digital sign-off in session)  Date: 2026-11-05

---

## Appendix B — Proposed data model

The final SQL belongs in numbered migrations and `drugshop/schema.sql`. This is
the shape to review in Phase 0/2.

### `billing_subscriptions`

```sql
CREATE TABLE IF NOT EXISTS billing_subscriptions (
  id                    INTEGER PRIMARY KEY CHECK (id = 1),
  customer_name         TEXT NOT NULL DEFAULT '',
  contact_name          TEXT NOT NULL DEFAULT '',
  contact_phone         TEXT NOT NULL DEFAULT '',
  bundle                TEXT NOT NULL,
  status                TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN
                          ('pending','active','past_due','cancelled',
                           'expired','grandfathered')),
  currency              TEXT NOT NULL DEFAULT 'UGX',
  setup_fee             REAL NOT NULL DEFAULT 0 CHECK (setup_fee >= 0),
  monthly_fee           REAL NOT NULL DEFAULT 0 CHECK (monthly_fee >= 0),
  started_on            TEXT NOT NULL,
  current_period_start  TEXT,
  current_period_end    TEXT,
  price_book_version    TEXT NOT NULL DEFAULT '',
  notes                 TEXT NOT NULL DEFAULT '',
  created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

### `billing_events`

```sql
CREATE TABLE IF NOT EXISTS billing_events (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  subscription_id  INTEGER REFERENCES billing_subscriptions(id),
  action           TEXT NOT NULL,
  actor            TEXT NOT NULL DEFAULT '',
  detail           TEXT NOT NULL DEFAULT '',
  created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

### `billing_invoices`

```sql
CREATE TABLE IF NOT EXISTS billing_invoices (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_no    TEXT NOT NULL UNIQUE,
  kind          TEXT NOT NULL
                CHECK (kind IN ('setup','monthly','addon','other')),
  issue_date    TEXT NOT NULL,
  due_date      TEXT NOT NULL,
  period_start  TEXT,
  period_end    TEXT,
  amount        REAL NOT NULL CHECK (amount > 0),
  currency      TEXT NOT NULL DEFAULT 'UGX',
  status        TEXT NOT NULL DEFAULT 'unpaid'
                CHECK (status IN ('draft','unpaid','partial','paid','void')),
  notes         TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

### `billing_payments`

```sql
CREATE TABLE IF NOT EXISTS billing_payments (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id    INTEGER NOT NULL REFERENCES billing_invoices(id)
                ON DELETE RESTRICT,
  paid_on       TEXT NOT NULL,
  amount        REAL NOT NULL CHECK (amount > 0),
  currency      TEXT NOT NULL DEFAULT 'UGX',
  method        TEXT NOT NULL DEFAULT 'other',
  reference     TEXT NOT NULL DEFAULT '',
  received_by   TEXT NOT NULL DEFAULT '',
  notes         TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

Add indexes on subscription status, invoice status/due date, and payment invoice
id. Keep all money as `REAL` to match the current sales tables, or migrate the
new billing tables to integer minor units in Phase 0 — do not mix conventions.

---

## Appendix C — Proposed CLI and API surface

### CLI

```text
flask --app run revenue pricebook
flask --app run revenue quote <base> [--add growth|tender] [--setup-discount N] [--json]
  # setup discount N is capped at 100,000 UGX in v1
flask --app run revenue show
flask --app run revenue activate <bundle> [options]
flask --app run revenue renew --period-end YYYY-MM-DD
flask --app run revenue status <status> [--notes ...]
flask --app run revenue invoice setup [--due YYYY-MM-DD]
flask --app run revenue invoice monthly --period-start ... --period-end ... [--due ...]
flask --app run revenue invoice list [--json]
flask --app run revenue invoice show <invoice_no> [--json]
flask --app run revenue invoice void <invoice_no> [--reason ...] [--json]
flask --app run revenue payment record <invoice_no> --amount ... --method ...
flask --app run revenue renewals [--days 14] [--json]
flask --app run revenue report [--format json|csv]
```

### API

```text
GET /api/subscription                  any signed-in user, limited fields
GET /api/subscription/invoices         admin only
GET /api/subscription/invoices/<no>    admin only
```

No write endpoints in v1. Commercial writes remain operator CLI actions.

---

## Appendix D — Phase tracker

| Phase | Status | Started | Gate signed | Notes |
|---|---|---|---|---|
| 0 — Decisions and baseline | **Approved** | 2026-11-05 | 2026-11-05 | 445 tests at sign-off; re-verified 2026-11-09 (507 tests, Ruff, 17 JS, smoke); backup verified; live 006 applied; plan unchanged; branch `feature/revenue-ops` |
| 1 — Price book and quote engine | **Approved** | 2026-11-06 | 2026-11-09 | 55 targeted / 509 full tests; cap fixed; six quotes verified; no schema or entitlement change |
| 2 — Subscription ledger and activation | **Approved** | 2026-11-09 | 2026-11-12 | Migration 007 + service + CLI + tests; 73 targeted / 556 full tests; Ruff clean; staging activation/renewal/restore and fresh-DB activation verified; 007 dry run preserved 19 table counts; live stayed Legacy, then `run.py` applied 007 additively (billing empty). Owner authorized Phase 3 on 2026-11-12 |
| 3 — Invoices, payments, renewals | **Approved** | 2026-11-12 | 2026-11-16 | Migration 008 + invoice/payment/renewal service and CLI + tests; 56 targeted / 602 full tests; Ruff clean; invoice amounts reconcile to the Pro quote and to a discounted agreed fee; money paths use `BEGIN IMMEDIATE`, partial unique indexes, void/reissue, and a payment ledger view; concurrency and overlap guards tested; manual cycle verified; 008 dry run preserved 21 table counts; migration 008 applied additively on 2026-11-18 with empty billing tables. Owner authorized Phase 4 on 2026-11-16 |
| 4 — Read-only subscription UI/API | **Approved** | 2026-11-16 | 2026-11-18 | Read-only `billing` blueprint + Plan & Apps card + admin invoice ledger; 35 targeted / 625 full tests; Ruff clean; JS parses; payload filters, access matrix, Legacy grandfathered fallback, and fail-open reads verified; migration 008 applied additively on 2026-11-18 with empty billing tables; `SUPPORT_WHATSAPP` configured for the pilot on 2026-11-18. Owner authorized Phase 5 on 2026-11-18 |
| 5 - Reporting and first paid rollout | **Approved (rollout pending)** | 2026-11-18 | 2026-11-18 | Revenue report + read-only rollup + runbooks/checklists + rehearsal; 21 targeted / 647 full tests; Ruff and JS clean; report CLI hash-verified non-mutating; six-plan matrix and rollup reconcile; live-copy migration preserved 21 business table counts; restore rehearsal passed; end-to-end operator rehearsal on a live-DB copy passed (quote → activate → setup invoice → bank payment → monthly invoice → MoMo payment → void/reissue → renew → report → rollup) with live hash unchanged; first paid customer (Andama Moses, Pro) onboarded on `instance/customers/andama-moses.db` with MRR 180,000 and 180,000 outstanding, and the portfolio rollup reports 1 paying installation; pilot restored to Legacy after an accidental activation and re-verified hash-identical; first monthly close and founder review still open |
| 6 — Optional automation | Deferred | | | |

---

## Appendix E — Traceability to the revenue strategy

| Strategy goal | Build phase |
|---|---|
| Publish and test a price card | 0, 1 |
| Quote a bundle in under 5 minutes | 1 |
| Activate after payment, not self-service | 2 |
| Record setup and monthly revenue | 2, 3 |
| Track outstanding balances | 3 |
| Renew 14 days before expiry | 3, 4 |
| Show the customer what they own | 4 |
| Keep the upgrade path visible | 4 |
| Reconcile portfolio MRR | 5 |
| Protect Onzima during the pilot | 0, 2, 5 |
```
