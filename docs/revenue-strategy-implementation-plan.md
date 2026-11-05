# Revenue Strategy — Phased Implementation Plan

**Status:** Phase 0 approved 2026-11-05; Phase 1 not started  
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
- Setup discount cannot be negative or exceed the setup total.
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

Also verify that `legacy` is refused with a clear message.

### Tests

- Exact totals for each scenario.
- Growth without Pro is rejected.
- Tender standalone and combined both work.
- Setup discount boundary and monthly-discount rejection.
- JSON output is stable and includes line items and version.
- CLI exits non-zero with a clear message on invalid input.
- No database connection is required.

### Review gate

- [ ] Founder agrees the six quotes.
- [ ] The quote output is readable in a live sales call.
- [ ] Price-book version is visible.
- [ ] No schema or entitlement change was made.

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

- [ ] Activation is reproducible from a fresh database in under 15 minutes.
- [ ] Entitlements and subscription agree after activation.
- [ ] Failure path leaves an obvious, recoverable `pending` state.
- [ ] Legacy remains untouched on the live installation.
- [ ] Migration dry run on a copy passes with business row counts unchanged.

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
- Invoice numbers are unique and sequential per installation.
- Renewal queue defaults to 14 days before `current_period_end`.
- No gateway call is made when recording a payment.

### Commands

```bash
flask --app run revenue invoice setup --due 2026-11-12
flask --app run revenue invoice monthly \
  --period-start 2026-11-05 --period-end 2026-12-05 --due 2026-11-05
flask --app run revenue invoice list
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

- [ ] One setup and one monthly invoice reconcile exactly to Phase 1 quotes.
- [ ] Partial and full payment states are correct.
- [ ] Renewal queue is correct around the 14-day boundary.
- [ ] No payment gateway or carrier call was made.
- [ ] The operator can explain the balance from the CLI alone.

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

- [ ] Customer can see what they own and when it renews.
- [ ] There is no edit, upgrade, or payment button that changes data.
- [ ] Admin invoice view is read-only.
- [ ] Upgrade CTA opens the configured support link.
- [ ] No console errors on any plan.

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
  - grandfathered and excluded rows.
- `scripts/revenue_rollup.py`:
  - accepts one or more database paths or a directory;
  - opens databases read-only;
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

- [ ] First paid customer is active, invoiced, and visible in the report.
- [ ] Report totals reconcile to the manual calculation.
- [ ] Onzima's live plan is unchanged unless deliberately grandfathered.
- [ ] Onboarding and rollback runbooks match the shipped commands.
- [ ] No regressions, no unexpected 403s, no data loss.

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
flask --app run revenue show
flask --app run revenue activate <bundle> [options]
flask --app run revenue renew --period-end YYYY-MM-DD
flask --app run revenue status <status> [--notes ...]
flask --app run revenue invoice setup [--due YYYY-MM-DD]
flask --app run revenue invoice monthly --period-start ... --period-end ... [--due ...]
flask --app run revenue invoice list [--json]
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
| 0 — Decisions and baseline | **Approved** | 2026-11-05 | 2026-11-05 | 445 tests passed; dry-run fix; backup verified; live 006 applied; plan unchanged; branch `feature/revenue-ops` |
| 1 — Price book and quote engine | Not started | | | |
| 2 — Subscription ledger and activation | Not started | | | |
| 3 — Invoices, payments, renewals | Not started | | | |
| 4 — Read-only subscription UI/API | Not started | | | |
| 5 — Reporting and first paid rollout | Not started | | | |
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
