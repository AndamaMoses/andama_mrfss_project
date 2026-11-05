# First-Run Gaps — Implementation Plan

Status: **implemented — see §7 for results**
Branch: `feature/packaging`
Baseline: `234 passed` (`python -m pytest -q`, 2026-10-30)

This plan turns the first-time-client walkthrough findings into small, verifiable
stages. It deliberately fixes **trust and plan-boundary defects first**, before
adding new workflows. Every stage must keep the full suite green and must add a
regression test for the behavior it changes.

---

## 1. Verified defect register

Each item below was reproduced against a scratch SQLite database seeded with the
public Core demo (`DEMO_SEED=1`, `DRUGSHOP_BUNDLE=core`) — not inferred only from
reading code.

| # | Defect | Evidence | Severity | Stage |
|---|--------|----------|----------|-------|
| 1 | Dashboard "sales count" counts line items, not receipts | 2-line basket + 1 single sale reported `count = 9`; demo day has 3 receipts but 6 line items | High | 1 |
| 2 | Today's Sales table hides receipt number and served-by | `pos.js` renders `s.id` but not `s.receipt_ref` / `s.served_by` | High | 1 |
| 3 | Single-item CREDIT sale accepts no customer name | `POST /api/sales` with `payment_method=CREDIT` and no name returned `201`; cart path returns `400` | High | 1 |
| 4 | 31–60 day expiries are counted but never listed | `expiry_counts.warning_60` is returned; no UI list uses it | Medium | 1 |
| 5 | Core dashboard leaks Pro data | `/api/dashboard` on Core returns `refill.due_count = 2` and `credit_owed_total = 1300` | High | 2 |
| 6 | Patient CSV export is always available | `GET /api/export/patients` on Core returned `200` | High | 2 |
| 7 | Core accepts CREDIT sales | `/api/sales` and `/api/sales/cart` accept `CREDIT`; only `/api/credit` is Finance-gated | High | 2 |
| 8 | Staff page breaks on Core | `/staff` calls `/api/reminders` unconditionally (403 on Core) and still shows a refill card | High | 2 |
| 9 | Staff page offers CREDIT on Core | `staff.html` always renders `CREDIT (owe)` | Medium | 2 |
| 10 | Anonymous visitors get the pharmacy SPA shell at `/` | `GET /` returned `200` with `index.html`; JS redirects only after boot | Medium | 3 |
| 11 | Branch is not editable in Shop Settings | API allow-list already includes `shop_branch`; the form/JS omit it | Medium | 3 |
| 12 | Demo sale is CREDIT even on Core | `demo.py` seeds a CREDIT sale directly, bypassing the entitlement boundary | Medium | 3 |
| 13 | No write-off / stock adjustment workflow | Only purchases and sales change stock; damaged/expired stock has no path | High (ops) | 4 |
| 14 | Supplier invoice posting uses `prompt()` with product IDs | `stock.js` asks for raw IDs instead of a form | Medium (ops) | 4 |
| 15 | No offline POS / service worker | No service worker or queue; a dropped connection stops sales | High (ops) | Backlog |
| 16 | Backups are manual only | `/api/backup` is a download button; no schedule or retention | High (ops) | Backlog |
| 17 | No generic audit log | Only `login_events`, staff sales, entitlement events | Medium | Backlog |
| 18 | No returns / partial refunds | Only admin void of a whole sale | High (product) | Backlog |
| 19 | No VAT/tax fields | Receipts and sales have no tax line | Medium (product) | Backlog |

**Ruled out during verification:** the dashboard expiry watchdog already
receives `expiry_critical` as a list (`expired + critical_30`), so it was not a
defect. Only the missing 31–60 day list was real.

Out of scope for this pass (documented, not silently dropped): barcode scanning,
held sales, OCR of supplier invoices, multiple branches, offline sync, scheduled
backups, generic audit log, returns/refunds, VAT. These need product decisions
and, in several cases, schema migrations.

---

## 2. Stage 1 — Sales data trust

**Goal:** what the dashboard and Today's Sales table say must match what the shop
actually rang up.

Changes:
1. `drugshop/sales/service.py` — `sales_summary()` counts **distinct receipts**
   (`receipt_ref`, falling back to the row id for legacy blank refs) and keeps
   `line_count` for the Z-report.
2. `drugshop/static/js/pos.js` — Today's Sales rows show receipt number and
   served-by; update the empty-state `colspan`.
3. `drugshop/templates/index.html` — add the two column headers.
4. `drugshop/sales/routes.py` — single-item `CREDIT` requires a customer name,
   matching the cart path.
5. `drugshop/reporting/routes.py` — add `expiry_warning` (31–60 days) as a list
   alongside the existing `expiry_critical` list.
6. `drugshop/static/js/dashboard.js` — render critical + warning batches.

Tests:
- Two-line basket + one single sale → `sales_today.count == 2`, `line_count == 3`.
- Single-item CREDIT without a name → `400`; with a name → `201`.
- Dashboard `expiry_critical` contains the ≤30d batch and `expiry_warning`
  contains the 31–60d batch.
- Existing demo test updated: today's receipt count is `3`, not `6`.

Acceptance: dashboard "N sales" equals receipts, the table identifies each
receipt and cashier, and the expiry panel lists every critical batch.

---

## 3. Stage 2 — Plan and entitlement boundaries

**Goal:** a Core install must never expose, compute, or accept Pro/Finance data,
and the staff view must not 403 against its own plan.

Changes:
1. `drugshop/reporting/routes.py`
   - `api_dashboard()` returns empty refill/credit blocks unless the app is
     entitled. Shape stays stable so the UI does not need null checks.
   - `api_export()` rejects `patients` with `403` when `patients` is not
     entitled; `sales` and `stock` stay available to Core.
2. `drugshop/sales/routes.py` — both sale endpoints reject `CREDIT` with `403`
   and the standard upgrade payload when `finance` is not entitled.
3. `drugshop/web/routes.py` — render `staff.html` with `show_patients` and
   `show_finance` flags.
4. `drugshop/templates/staff.html` — hide the refill card, Care tab, and
   `/api/reminders` call when Patients is absent; hide CREDIT when Finance is
   absent.
5. `drugshop/demo.py` — seed the demo CREDIT row as CASH on plans without
   Finance, so the demo never contains data its own UI forbids.

Tests:
- Core dashboard has `refill.due_count == 0`, `credit_owed_total == 0`.
- Core `GET /api/export/patients` → `403`; `sales`/`stock` → `200`.
- Core `POST /api/sales` and `/api/sales/cart` with CREDIT → `403`.
- Pro still allows all of the above (regression guard).
- `/staff` on Core does not contain `/api/reminders` or `CREDIT (owe)`.

Acceptance: a Core browser session produces no expected 403s, and the server —
not just the UI — enforces the plan.

---

## 4. Stage 3 — First-run and demo polish

**Goal:** a first-time visitor lands on a sign-in page, sees demo data clearly
labelled, and can set the branch shown on receipts.

Changes:
1. `drugshop/web/routes.py` — `/` and `/staff` redirect anonymous visitors to
   `/login` before any workspace shell is served.
2. `config.py` + `drugshop/web/routes.py` — expose `DEMO_MODE` when `DEMO_SEED`
   is enabled; render `index.html` with a visible "Demo data — synthetic
   records" banner.
3. `drugshop/static/js/settings.js` + `index.html` — add the branch field to
   Shop Settings (the API already persists it).
4. Update `tests/test_pages.py` to fetch `/` as a signed-in user.

Tests:
- Anonymous `GET /` and `GET /staff` → `302` to `/login`; signed-in → `200`.
- Demo-mode app renders the banner; normal app does not.
- Saving `shop_branch` changes the value returned by `/api/settings` and used on
  receipts.

Acceptance: no unauthenticated SPA flash, demo data is unmistakably synthetic,
and the branch on a receipt is editable.

---

## 5. Stage 4 — Operations quick wins

**Goal:** cover the two highest-friction stock operations. This is the one stage
that needs a schema change, so it ships its own numbered migration.

Changes:
1. Add migration `003_stock_adjustments.sql` (and mirror it in `schema.sql`),
   an admin stock adjustment/write-off endpoint, and a form in the Inventory
   tab. Reasons: `DAMAGED`, `EXPIRED`, `COUNT_CORRECTION`, `OTHER`. Writes a
   negative movement tied to a batch and never goes below zero.
2. Replace the `prompt()`-based supplier invoice posting with a proper form
   (product select, qty, expiry, batch no). Keep the existing endpoint
   contract.
3. Document the offline/backup/returns work as the next milestone in this file
   rather than pretending it is fixed.

Tests:
- Write-off reduces the batch quantity and records the reason; over-writing off
  is rejected.
- Invoice form posts the same payload the old prompt path did.

Acceptance: an expired strip can be removed from stock with an audit trail, and
an invoice can be posted without memorising product IDs.

---

## 6. Execution rules

- Run `python -m pytest -q` after each stage; run `ruff check .` on changed
  Python files.
- Add tests **before** or with the fix, never after a silent behavior change.
- Keep the public Core demo working at every commit.
- Do not delete or rewrite existing business data; entitlement changes only
  revoke access.
- If a stage reveals a schema change, stop and split it into its own migration
  plan rather than folding it in. Stage 4's write-off is the exception and
  ships as `003_stock_adjustments.sql` with a mirrored `schema.sql` table.

---

## 7. Results

| Stage | Outcome | Regression coverage |
|-------|---------|---------------------|
| 1 | Receipt-based sales count, receipt/served-by columns, CREDIT name check, 31–60 day expiry list | `test_sales.py`, `test_reporting.py`, `test_demo.py` |
| 2 | Core dashboard/export/sales boundaries and plan-aware staff view | `test_plan_boundaries.py` |
| 3 | Anonymous `/` and `/staff` redirect, demo banner, editable branch | `test_pages.py`, `test_config.py` |
| 4 | Stock write-off with audit row, invoice posting form | `test_inventory.py`, `test_migrations.py` |

Remaining backlog (unchanged): offline POS, scheduled backups, generic audit
log, returns/partial refunds, VAT, barcode scanning, held sales, OCR, multiple
branches. These are product decisions plus larger migrations, not quick wins.

