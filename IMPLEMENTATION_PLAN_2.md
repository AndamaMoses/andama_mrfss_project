# Implementation Plan 2 — Packaging, Entitlements & App Launcher

**Project:** andama_mrfss_project (Onzima Charles Drug Shop + Tender Copilot)
**Date:** 2026-10-21
**Status:** Phases 0–5 complete; Phase 6 pilot in progress (started 2026-10-21,
ends 2026-11-04)
**Companion document:** `modularization/IMPLEMENTATION_PLAN.md` (internal modularization, complete)

---

## 1. Executive summary

The backend is now a modular monolith: 14 domain packages, a Flask application
factory, one SQLite database, one migration stream, and a 154-test suite. The
next commercial step is not a plugin runtime. It is a **packaging layer**:

- a static **app registry** describing what the product can do;
- **installation-level entitlements** deciding what this customer owns;
- a **server-side gate** that enforces those entitlements;
- an **Odoo-style launcher** that makes the product feel like a suite;
- **two bundles and one add-on** that are easy to sell and support.

One codebase, one deployable, one database, one migration stream. Apps are
packages in the product catalog, not installable code modules.

Target: 20 pharmacy customers in 12 months, sales-assisted onboarding, manual
activation. Estimated effort: **9–12 developer days**, or roughly three
full-time weeks including pilot hardening.

---

## 2. Decisions locked

| Decision | Choice |
|---|---|
| Customer target | 20 pharmacies in 12 months |
| Sales motion | Sales-assisted; no self-service app store |
| Architecture | Packaged modular monolith — **not** a plugin runtime |
| Deployment | One codebase, one process, one SQLite database per installation |
| Bundles | 2 bundles + 1 add-on + Tender Copilot standalone |
| Activation | Operator-run CLI; read-only plan panel for the customer |
| Tender Copilot | Separate brand and go-to-market, shared codebase and auth |
| Branding | Keep plum/gold; borrow Odoo's layout grammar, not assets |
| Device priority | Desktop-first at the counter; responsive for the owner |
| First screens | POS, Inventory, Dashboard |
| Expiry policy | Soft warning in v1; no hard lockout |
| User permissions | Unchanged; entitlements are installation-wide, roles still control users |

### Non-goals for this plan

- Module loader, dependency resolver, or marketplace
- Per-module database migrations or version skew
- Self-service purchases, billing integration, or license server
- Multi-tenancy rewrite or microservices
- Full visual redesign; only the launcher, navigation gating, and plan panel
- Third-party developer SDK

These are deliberate. Revisit only when the triggers in Section 15 are met.

---

## 3. Commercial catalog

Draft pricing for validation with the first five buyers. Do not discount the
monthly fee; discount setup if a deal needs movement.

| Offer | Apps included | Setup | Monthly | Buyer |
|---|---|---:|---:|---|
| **Core** | POS, Inventory (batches/expiry), Purchases/Invoices, Customers, Dashboard | UGX 400,000 | UGX 120,000 | Single-counter shop |
| **Pro** | Core + Patients/Refills, Finance (credit, reconciliation, expenses, profit), Staff activity | UGX 600,000 | UGX 180,000 | Established shop with staff and credit |
| **Growth add-on** | Stock Alerts, SMS/WhatsApp reminders and log (requires Pro) | UGX 200,000 | +UGX 50,000 | Pro customers |
| **Tender Copilot** | Tender page, analysis, methodology (standalone brand) | UGX 300,000 | UGX 150,000 | Consultancies |

**Illustrative mix at 20 customers:** 11 Core + 9 Pro + 5 Growth add-ons ≈
**UGX 3.2M MRR**, plus ~UGX 10.8M in setup fees. At ~3,800 UGX/USD this is
roughly USD 840/month — a founder-led business, not a platform business.

**Positioning:** *Odoo-grade polish, pharmacy-grade focus, WhatsApp-native
workflows.* Never position on price against Odoo; position on time-to-value and
stock-loss prevention.

---

## 4. Architecture

### 4.1 Principles

1. **Entitlements gate access; they do not install code.** All apps ship in the
   binary.
2. **One migration stream.** Schema changes are global and additive.
3. **Fail open on an empty entitlement table.** An upgrade must never lock a
   shop out of its data.
4. **Deny server-side, hide client-side.** Hidden buttons are not security.
5. **Configuration, not forks.** No customer-specific branches.
6. **Keep the existing stack.** No new Python or JavaScript dependencies.

### 4.2 App registry

Static metadata in `drugshop/apps/registry.py`.

| App ID | Name | Bundle | Tabs / surface | Backend owner |
|---|---|---|---|---|
| `pos` | Point of Sale | Core | `pos` | `sales` |
| `inventory` | Inventory & Purchases | Core | `stock`, `inv`, `drugs` | `inventory` |
| `patients` | Refill Care | Pro | `pat` | `patients` |
| `finance` | Finance | Pro | `rec`, `fin` | `credit`, `finance`, `reporting.api_staff_activity` |
| `alerts` | Stock Alerts | Growth | `alerts` | `notifications` |
| `tender` | Tender Copilot | Tender | `/tender` | `tender` |
| `dashboard` | Dashboard | Always-on | `dash` | `reporting.api_dashboard` |

Always-on surfaces (not sold separately): authentication, user management,
customers, settings, backup, CSV export, Manage Data.

Each registry entry carries: `id`, `name`, `short_name`, `description`, `icon`
(existing SVG sprite id), `tabs`, `bundle`, `requires` (app IDs), `always_on`,
and display order.

**Bundle map**

| Bundle | Apps |
|---|---|
| `core` | `pos`, `inventory` |
| `pro` | `core` + `patients`, `finance` |
| `growth` | `pro` + `alerts` |
| `tender` | `tender` |
| `legacy` | all gated apps: `pos`, `inventory`, `patients`, `finance`, `alerts`, `tender` (grandfathered only; not sold) |

`alerts` requires `pro`. `tender` is standalone and may be combined with any
pharmacy bundle by activating both. `legacy` exists only to keep the existing
Onzima installation on every feature it had before packaging.

### 4.3 Entitlement data model

New additive migration: `drugshop/migrations/002_app_entitlements.sql`.
Also reflected in `drugshop/schema.sql` for fresh databases.

```sql
CREATE TABLE IF NOT EXISTS app_entitlements (
  app_id        TEXT PRIMARY KEY,
  bundle        TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL DEFAULT 'active',   -- active | revoked
  activated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  expires_at    TEXT,                              -- informational in v1
  source        TEXT NOT NULL DEFAULT 'manual',    -- manual | bootstrap | cli
  notes         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS entitlement_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  app_id      TEXT NOT NULL,
  action      TEXT NOT NULL,                       -- seed | add | remove | change
  actor       TEXT NOT NULL DEFAULT '',
  detail      TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_entitlement_events_created
  ON entitlement_events(created_at);
```

Notes:

- One row per app, per installation. No `tenant_id` in v1; one deployment serves
  one shop.
- `expires_at` is shown to the operator and customer but does **not** block
  access in v1. This avoids locking a pharmacy out during a late Mobile Money
  payment. Hard expiry can be added later behind a config flag.
- Removing an app sets `status='revoked'` and logs an event; it never deletes
  business data. Re-activation restores access to the same data.

### 4.4 Seeding and grandfathering

- `run.py` calls `ensure_entitlements(app.config["DEFAULT_BUNDLE"])` after
  `init_db()`.
- `DEFAULT_BUNDLE` defaults to `legacy` (Pro + Alerts + Tender) so the existing
  Onzima installation keeps every current feature. New installations set
  `DRUGSHOP_BUNDLE=core` at deploy time. `legacy` is not a sold bundle.
- Seeding happens only when `app_entitlements` is empty. It writes one `seed`
  event per app. An installation already seeded as Pro can be grandfathered
  with `flask --app run plan add alerts` and `flask --app run plan add tender`.
- If the table is empty at request time (e.g. a deployment script forgot to
  seed), `is_entitled()` returns `True` for all apps and logs a warning. This is
  the fail-open safety net.
- `tests/conftest.py` seeds `pro` so the existing 154 tests continue to exercise
  all routes.

### 4.5 Enforcement gate

A `before_request` hook in `drugshop/apps/guards.py`, registered after the auth
gate in `create_app()`.

**Mapping:** built once at startup from the Flask URL map.

| Blueprint | App |
|---|---|
| `sales` | `pos` |
| `inventory` | `inventory` |
| `patients` | `patients` |
| `credit` | `finance` |
| `finance` | `finance` |
| `notifications` | `alerts` |
| `tender` | `tender` |
| `reporting.api_staff_activity` | `finance` (override) |
| `reporting.*` (all other endpoints) | always-on |
| `auth`, `web`, `admin`, `customers`, `apps` | always-on |
| `static` | always-on |

- Endpoint-level overrides take precedence over blueprint defaults.
- A test iterates `app.url_map` and asserts every non-static endpoint is either
  mapped or explicitly always-on. This prevents a new route from silently
  becoming free.
- `before_request` uses `flask.g` to cache the entitlement set for the request.
- Admins are **not** bypassed. A shop that has not bought Finance cannot use
  Finance, even as admin.
- Denied API request → `403` JSON:
  `{"error":"app not entitled","app":"patients","message":"Refill Care is not included in your plan.","upgrade":{"bundle":"pro"}}`
- Denied page request (`/tender`) → redirect to `/?upgrade=tender`.
- A denial is logged at INFO level with the endpoint and app; it is not written
  to `entitlement_events` (that table is for commercial changes, not access
  attempts).

### 4.6 Plan administration

Writes are operator-only via Flask CLI. The customer sees a read-only plan
panel. This is intentional: at 20 customers, self-service activation is a
revenue leak and a support risk.

Commands (exact names may adjust during implementation):

```text
flask --app run plan show
flask --app run plan set pro --expires 2027-10-21 --actor "Andama"
flask --app run plan set core --actor "Andama"
flask --app run plan add alerts --actor "Andama"
flask --app run plan remove alerts --actor "Andama"
flask --app run plan set tender --actor "Andama"
```

- `plan set` replaces the bundle entitlement set, adds missing apps, revokes
  removed apps, and logs one event per change.
- `plan add` validates `requires` (e.g. `alerts` demands the Pro apps).
- Unknown bundle/app → non-zero exit with a clear message.
- Output prints the active bundle, apps, expiry, and support contact.
- The CLI requires an initialized database; it does not call `init_db()`.

**Read-only panel:** a "Plan & Apps" card in the existing Manage Data tab shows
bundle, included apps, expiry, and a WhatsApp support link. No toggles.

### 4.7 `/api/apps` payload

Authenticated; always-on; used by the launcher, navigation, and plan panel.

```json
{
  "plan": {
    "bundle": "pro",
    "label": "Pro",
    "status": "active",
    "expires_at": null
  },
  "apps": [
    {
      "id": "pos",
      "name": "Point of Sale",
      "description": "Sell, print receipts, close the day",
      "icon": "i-pos",
      "tabs": ["pos"],
      "bundle": "core",
      "entitled": true,
      "always_on": false
    },
    {
      "id": "tender",
      "name": "Tender Copilot",
      "description": "Analyse PPDA/UNRA tenders",
      "icon": "i-hat",
      "tabs": [],
      "bundle": "tender",
      "entitled": false,
      "always_on": false
    }
  ],
  "support": {
    "whatsapp": "+256...",
    "message": "Upgrade your plan"
  }
}
```

- `tabs` tells the frontend which tabs belong to the app.
- The payload never includes entitlement internals, notes, or event history.
- `support.whatsapp` comes from `SUPPORT_WHATSAPP` config; blank hides the CTA.

### 4.8 Frontend behavior

New file: `drugshop/static/js/core/apps.js`, loaded before `boot.js`.

**Launcher**

- New `#tab-apps` section with an app grid: icon, name, one-line description,
  lock badge for unentitled apps.
- Styling uses existing plum/gold tokens; white tile cards, 16px radius, 56px
  icon, responsive 2/3/4/6-column grid.
- Reuse the existing SVG sprite (`i-dash`, `i-pos`, `i-stock`, `i-heart`,
  `i-coins`, `i-bell`, `i-hat`, plus a new `i-apps` and `i-lock`).
- Entitled tile click → first tab in `tabs`; Tender tile → `/tender`.
- Unentitled tile click → upgrade modal with the support link.
- Dashboard remains the default landing tab in v1. "Apps" is the first sidebar
  entry. Revisit landing behavior after the pilot.

**Navigation gating**

- Add `data-app="pos"` / `"inventory"` / `"patients"` / `"finance"` /
  `"alerts"` / `"tender"` to sidebar buttons and links.
- Add `data-section-apps="pos,inventory"` to section titles so empty sections
  disappear.
- `applyApps()` hides unentitled elements, renders the launcher, and redirects
  to Dashboard if the active tab was hidden.
- `switchTab()` refuses to open a tab whose app is not entitled and opens the
  upgrade modal instead. This covers stray `onclick` calls and deep links.
- Show Dashboard's "Refills Due" panel only when `patients` is entitled; the
  Expiry Watchdog remains Core.

**Loader gating**

`loadAll()` must not call endpoints the installation cannot access. Otherwise
every login produces a burst of 403s.

| Group | Loaders |
|---|---|
| Always | `loadDash`, `loadTeam`, `loadManage`, `loadCustomers`, `loadSettings` |
| `pos` | `loadSales` |
| `inventory` | `loadProducts`, `loadStock`, `loadInvoices`, `loadDrugCatalogue` |
| `patients` | `loadPatients` |
| `finance` | `loadCredit`, `loadExpenses`, `loadProfit`, `calcRec`, `loadRec` |
| `alerts` | `loadAlerts`, `loadSmsLog` |

- If `/api/apps` fails, fall back to the current `loadAll()` behavior and leave
  navigation visible. The server still enforces. This avoids a blank UI.
- `core/api.js` recognises `403 {"error":"app not entitled"}` and opens the
  upgrade modal instead of a generic error toast.

**Plan panel**

Read-only card in Manage Data: current bundle, list of included apps, expiry,
and "Talk to us" WhatsApp link. Admin-only, matching the rest of Manage Data.

---

## 5. Route ownership matrix

| Route(s) | App | Notes |
|---|---|---|
| `/api/sales*`, `/api/receipts/*` | `pos` | Core |
| `/api/products*`, `/api/batches*`, `/api/expiry`, `/api/invoices*`, `/uploads/*` | `inventory` | Core |
| `/api/patients*`, `/api/reminders` | `patients` | Pro |
| `/api/credit*` | `finance` | Pro |
| `/api/reconciliation*`, `/api/expenses*`, `/api/profit` | `finance` | Pro |
| `/api/staff-activity` | `finance` | Pro; explicit override |
| `/api/alerts/*` | `alerts` | Growth add-on |
| `/tender`, `/api/tender/*` | `tender` | Standalone |
| `/api/customers` | always-on | Needed by POS and credit |
| `/api/dashboard`, `/api/my-sales`, `/api/backup`, `/api/export/*` | always-on | Data access and trust |
| `/api/login`, `/api/logout`, `/api/me`, `/api/personas`, `/api/users*`, `/api/change-password` | always-on | Auth and user management |
| `/api/settings`, `/api/seed` | always-on | Admin-only at route level |
| `/`, `/login`, `/staff` | always-on | Pages |

---

## 6. Implementation phases

Each phase ends with the full test suite, `ruff check .`, and the smoke script
green. Commit per phase.

### Phase 0 — Baseline and safety (0.5 day)

1. **Commit the current modularization work.** `git status` is dirty: `app.py`
   deleted, templates moved, `drugshop/` and tests untracked. Do not build on
   top of an uncommitted tree.
2. Tag `pre-packaging`.
3. Create branch `feature/packaging`.
4. Back up the live database (use `/api/backup` or copy the resolved DB path).
5. Confirm baseline: `pytest -q`, `ruff check .`, `scripts/smoke.ps1`.

**Acceptance:** clean tree, tag exists, backup verified, baseline green.

### Phase 1 — Registry, schema, seeding, CLI (2.5–3 days)

**New files**

- `drugshop/apps/__init__.py`
- `drugshop/apps/registry.py`
- `drugshop/apps/service.py`
- `drugshop/apps/cli.py`
- `drugshop/migrations/002_app_entitlements.sql`
- `tests/test_apps.py`
- `tests/test_entitlements.py`

**Changed files**

- `drugshop/schema.sql` (append the two tables)
- `drugshop/__init__.py` (register CLI)
- `run.py` (call `ensure_entitlements`)
- `config.py` (`DEFAULT_BUNDLE`, `SUPPORT_WHATSAPP`)
- `tests/conftest.py` (seed `pro`)

**Tasks**

1. Define `APPS`, `BUNDLES`, `BLUEPRINT_APPS`, `ENDPOINT_OVERRIDES`, and
   `ALWAYS_ON` in the registry.
2. Implement `bundle_apps`, `entitled_app_ids`, `is_entitled`, `current_plan`,
   `set_bundle`, `add_app`, `remove_app`, `ensure_entitlements`, `log_event`.
3. Write the migration and mirror it in `schema.sql`.
4. Add CLI commands and register them in `create_app()`.
5. Seed `pro` in the test fixture; add tests for bundle maps, dependencies,
   seeding, add/remove, event log, and unknown input.
6. No route gating yet, so existing behavior is unchanged.

**Acceptance:** fresh DB seeds Pro; existing DB upgrades cleanly; CLI works;
154 existing tests still pass.

### Phase 2 — Enforcement and API (1–1.5 days)

**New files**

- `drugshop/apps/guards.py`
- `drugshop/apps/routes.py`
- `tests/test_app_gate.py`
- `tests/test_apps_api.py`

**Changed files**

- `drugshop/__init__.py` (register blueprint and gate after auth gate)

**Tasks**

1. Build the endpoint→app map from `app.url_map` plus overrides.
2. Register `before_request`; cache entitlements in `flask.g`.
3. Return the standard 403 JSON for APIs and redirect for pages.
4. Add `GET /api/apps`.
5. Add the route-coverage test: every non-static endpoint is mapped or
   explicitly always-on.
6. Test admin-denied, anonymous, entitled, unentitled, empty-table fail-open,
   and page redirect.

**Acceptance:** Core cannot reach Pro endpoints; Pro reaches everything current;
always-on routes unaffected; `/api/apps` matches the registry.

### Phase 3 — Launcher, navigation, loaders (2.5–3.5 days)

**New files**

- `drugshop/static/js/core/apps.js`

**Changed files**

- `drugshop/templates/index.html` (launcher section, `data-app` attributes,
  plan panel, styles, script include; admin settings/team/backup moved into
  Manage Data so they remain reachable without the Alerts add-on)
- `drugshop/static/js/core/ui.js` (tab guard, titles)
- `drugshop/static/js/boot.js` (load `/api/apps`, gated loaders)
- `drugshop/static/js/core/api.js` (entitlement 403 handling)
- `drugshop/static/js/dashboard.js` (hide Refills Due and Credit Owed KPIs)
- `drugshop/static/js/manage.js` (load only entitled Manage Data panels)
- `drugshop/static/js/credit.js`, `team.js`, `settings.js` (guard secondary
  loader calls so another tab cannot trigger a predictable 403)
- `tests/test_pages.py` (apps module and launcher/plan markup checks)

**Tasks**

1. Build the launcher grid and responsive styles in the existing visual language.
2. Add `data-app` and `data-section-apps` attributes to navigation.
3. Implement `applyApps`, `renderLauncher`, `openUpgrade`, `switchTab` guard.
4. Replace the unconditional `loadAll()` with grouped loaders.
5. Add the read-only plan card in Manage Data.
6. Verify keyboard focus, contrast, and 44px touch targets.
7. Manual matrix: Pro, Core, Growth, Tender, admin, staff.

**Acceptance:** no 403s in the console for a normal Pro session; Core hides
Patients/Finance/Alerts and blocks their endpoints; launcher renders correctly
at 1280px, 900px, and 390px.

### Phase 4 — Tender packaging (1 day)

1. Hide the Tender sidebar link unless `tender` is entitled.
2. Direct `/tender` for an unentitled installation → upgrade page/redirect.
3. Add Tender brand header and standalone copy; keep the existing tool.
4. Document optional separate domain mapping; do not split the codebase.
5. Test pharmacy-only, Tender-only, and combined entitlements.

**Acceptance:** no cross-sell leakage into pharmacy demos; Tender works
standalone with the same auth.

### Phase 5 — Hardening, docs, dry run (1.5–2 days)

1. Full suite and `ruff`.
2. Extend `scripts/smoke.ps1`: `/api/apps`, Core denial, Pro access, Tender
   redirect.
3. Write onboarding/rollback runbooks (Sections 8–9) into the repo or appendix.
4. Dry run on a **copy** of the real database:
   - migrate, seed the target bundle (Pro for acceptance; Legacy for Onzima),
     compare row counts;
   - downgrade to Core, verify data still present;
   - re-upgrade, verify access returns;
   - restore from backup as a rehearsal.
5. Check `index.html` size and avoid a redesign; keep the diff focused.

**Acceptance:** dry run clean, smoke green, rollback rehearsed.

### Phase 6 — Pilot (0.5–1 day + two weeks observation)

1. Deploy to Onzima with **Legacy** (grandfathered: Pro + Alerts + Tender).
2. Verify all current features and the plan panel.
3. Create a staging/demo Core installation and rehearse a downgrade/upgrade.
4. Run a 15-minute owner walkthrough; capture questions.
5. Track activation time, 403 denials, support tickets, and one upgrade
   conversation. Entitlement denials are logged at warning level and summarized
   by `scripts/pilot_metrics.py`.

The executable checklist is [`docs/pilot-runbook.md`](docs/pilot-runbook.md);
results go in [`docs/pilot-tracker.md`](docs/pilot-tracker.md).

**Acceptance:** two weeks with no regressions; one upgrade demo completed.

---

## 7. Test plan

| Layer | Coverage |
|---|---|
| Registry unit | Bundle membership, dependency validation, unknown IDs |
| Service unit | Seed-once, add/remove, revoke without data loss, event log |
| Gate integration | Entitled 200, unentitled 403, admin denied, empty table fail-open, page redirect |
| Route coverage | Every endpoint mapped or explicitly always-on |
| API | `/api/apps` shape and flags for Core, Pro, Growth, Tender |
| Migration | Fresh DB, legacy DB, idempotent re-run |
| CLI | Set/add/remove, expiry, actor, invalid input, audit events |
| Regression | All existing tests with Pro seeded (212 at Phase 5) |
| Manual UI | Pro, Core, Growth, Tender; desktop/tablet/phone; keyboard |
| Smoke | Login, `/api/apps`, Core denial, Pro access, Tender redirect, backup, pages |

Commands:

```powershell
python -m pytest -q
python -m ruff check .
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1
```

---

## 8. Rollout sequence

1. Announce nothing until this has run quietly for two weeks.
2. Back up the database and verify the backup opens.
3. Deploy code; `init_db()` runs the additive migration.
4. `ensure_entitlements("legacy")` seeds Onzima with every app (Pro + Alerts +
   Tender); verify `/api/apps`.
5. Run smoke and the manual Legacy checklist.
6. Show the owner the Plan & Apps panel; explain nothing has been taken away.
7. Two weeks later, demo a Core staging install; use it in new-customer sales.
8. Sell the first Growth add-on or Tender engagement.

**Rollback**

- Code: checkout `pre-packaging` and restart. The migration is additive, so old
  code ignores the new tables.
- Data: restore the verified backup if any migration issue appears.
- Access: `flask --app run plan set legacy` restores Onzima's apps instantly;
  use `plan set pro` for a Pro customer.
- No destructive statements in `002_app_entitlements.sql`.

---

## 9. Onboarding runbook (per customer)

1. Confirm payment and chosen bundle; record expiry date.
2. Back up the existing database **and uploads**.
3. Deploy the current release; confirm `python run.py` boots.
4. Set the initial bundle: `DRUGSHOP_BUNDLE=core` for new installs, or
   `flask --app run plan set <bundle>`.
5. Log in as admin; verify `/api/apps` and the launcher.
6. Run the smoke checklist.
7. Verify one real workflow end-to-end (e.g. a cash sale and a stock check).
8. Show the owner the Plan & Apps card and support WhatsApp link.
9. Record activation time and support contact in the customer sheet.
10. Schedule a 30-day check-in and a renewal reminder 14 days before expiry.

The executable version is [`docs/onboarding-runbook.md`](docs/onboarding-runbook.md).
Rollback steps are in [`docs/rollback-runbook.md`](docs/rollback-runbook.md).

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Starting on an uncommitted tree | High | Lost work, messy diff | Phase 0 commits/tags first |
| Existing customer loses access | Medium | Trust damage | Seed Legacy for Onzima, fail-open empty table, dry run, CLI restore |
| Hidden UI but open API | Medium | Revenue leak, data exposure | Central endpoint map + coverage test |
| Frontend calls unentitled endpoints | High | Console noise, broken panels | Grouped loaders + 403 handling |
| New route accidentally free | Medium | Revenue leak | Route-coverage test fails CI |
| Scope creep into plugin runtime | High | Weeks lost | Non-goals in writing; review gate |
| Per-customer forks | Medium | Maintenance blow-up | Config only; feature flags, no branches |
| Expiry lockout drama | Low | Shop cannot sell | Soft expiry in v1 |
| SQLite migration issue | Low | Data loss | Additive SQL, backup, dry run, rollback |
| Tender brand confuses pharmacy buyers | Medium | Weaker demos | Separate link, separate script, never bundled by default |
| Pricing too low for 20-customer economics | Medium | Unsustainable support | Test 180k Pro; discount setup, not monthly |

---

## 11. Effort estimate

| Phase | Effort |
|---|---:|
| 0 — Baseline and safety | 0.5 day |
| 1 — Registry, schema, seed, CLI | 2.5–3 days |
| 2 — Enforcement and API | 1–1.5 days |
| 3 — Launcher, navigation, loaders | 2.5–3.5 days |
| 4 — Tender packaging | 1 day |
| 5 — Hardening, docs, dry run | 1.5–2 days |
| 6 — Pilot | 0.5–1 day + observation |
| **Total** | **9–12 developer days** |

Calendar: about three full-time weeks, or four to six weeks part-time. No new
infrastructure cost. Optional icon design: UGX 300k–800k if not done in-house.

---

## 12. Definition of done

- [x] Current modularization work committed and tagged `pre-packaging`.
- [x] `002_app_entitlements.sql` applied; fresh and legacy DBs verified.
- [x] Onzima Legacy plan (Pro + Alerts + Tender) rehearsed on a DB copy; every
  current feature still works. Live seed happens on the deployment boot.
- [x] `GET /api/apps` returns the correct plan and app flags.
- [x] Every non-static endpoint is mapped or explicitly always-on.
- [x] Core blocks Patients/Finance/Alerts at the API and in the UI.
- [x] Admin is not exempt from entitlement checks.
- [x] Launcher renders in brand colors, responsive, keyboard accessible.
- [x] No 403s during a normal Pro session; no 500s on downgrade.
- [x] Plan panel is read-only and shows bundle, apps, expiry, support link.
- [x] Tender hidden and blocked when unentitled; works standalone when entitled.
- [x] CLI set/add/remove tested; audit events written.
- [x] `pytest -q` green (212 tests after packaging).
- [x] `ruff check .` clean.
- [x] Smoke script includes packaging checks and passes.
- [x] Onboarding and rollback runbooks exist.
- [x] Dry run on a copy of the real DB completed and backup restored.
- [ ] Two-week pilot with Onzima shows no regressions.

---

## 13. Out of scope and future triggers

Not now:

- Plugin loader, marketplace, third-party SDK
- Per-module migrations, module version skew
- Self-service purchases, automated billing, license server
- Multi-tenant SaaS rewrite
- Full UI redesign beyond launcher/navigation
- AI invoice OCR, expiry prediction, MoMo reconciliation (separate roadmap)

Revisit true modular runtime only when at least three of these are true:

1. 50+ customers across 3+ verticals.
2. Resellers or third-party developers want to build on the platform.
3. Customers demand per-module procurement or independent upgrades.
4. A dedicated platform engineer is on the team.
5. On-prem installations need offline module changes without a full release.

---

## 14. Open decisions before Phase 4

1. Final bundle prices — validate 120k/180k against the playbook's 80–150k.
2. Tender Copilot brand name and domain. Brand retained as **Tender Copilot**;
   optional separate-domain mapping is documented in
   `docs/tender-standalone.md` (same codebase, no split).
3. Tender landing: separate page now, or after three paying consultancies.
4. Launcher landing default — Dashboard for staff, Apps for admins, or both?
5. Hard expiry policy after the first renewal cycle; keep soft in v1.
6. Whether Growth includes future AI features at the same price or becomes a
   separate AI add-on.

---

## 15. Execution log

| Phase | Status | Verification | Notes |
|---|---|---|---|
| 0 — Baseline | DONE | 154 tests, ruff clean, smoke 9/9 | Commit `3b085a9`; tag `pre-packaging`; branch `feature/packaging`; DB backup `instance/backups/drugshop-pre-packaging-20261021-161243.db` (SHA256 verified) |
| 1 — Registry, schema, seed, CLI | DONE | 181 tests, ruff clean, smoke 9/9 | `drugshop/apps/` (registry, service, CLI), migration `002_app_entitlements.sql`, Pro seeded on boot, CLI dry-run on a copy of the live DB with business counts unchanged. Route gating intentionally starts in Phase 2. |
| 2 — Enforcement and API | DONE | 200 tests, ruff clean, smoke 9/9 | `drugshop/apps/guards.py` (endpoint map + `before_request` gate), `drugshop/apps/routes.py` (`GET /api/apps`), full route-coverage test, admin-denied/empty-table/page-redirect checks. Tender and Alerts tests now explicitly grant those standalone/add-on apps. |
| 2a — Onzima grandfathering | DONE | 203 tests, ruff clean, smoke 9/9 | Added non-sellable `legacy` bundle (Pro + Alerts + Tender); `DEFAULT_BUNDLE` now seeds `legacy`. Existing already-seeded Pro installs can add the two apps with `plan add`. New deployments set `DRUGSHOP_BUNDLE=core`. |
| 3 — Launcher, navigation, loaders | DONE | 204 tests, ruff clean, smoke 9/9; headless Chrome matrix for Legacy, Pro, Growth, Core, Tender, and Core staff | Added Apps launcher, locked tiles, upgrade modal, nav/tab gating, read-only plan card, grouped loaders, and `/api/apps` fail-open fallback. Admin Shop Settings, Backup, Team, and Shift Activity moved to Manage Data so Pro/Core retain them; Shift Activity stays finance-gated. Core hides Patients/Finance/Alerts and credit options; no console errors or expected API 403s in the browser matrix. |
| 4 — Tender packaging | DONE | 212 tests, ruff clean, smoke 9/9, headless Chrome checks for Core and Tender | Tender now renders plan-aware: Tender-only installs get the standalone brand, shared-auth sign-in/sign-out, and no Onzima link or copy; combined installs keep the suite backlink. The launcher stops cross-selling Tender into pharmacy demos and stops showing pharmacy upsells in Tender-only plans. Added `docs/tender-standalone.md` (optional separate-domain mapping, shared cookie domain), `SESSION_COOKIE_DOMAIN`, and pharmacy-only/Tender-only/combined tests. |
| 5 — Hardening, docs, dry run | DONE | 212 tests, ruff clean, smoke green for Core, Pro, and Tender; dry-run `PASS` for legacy and pro | Live DB is the legacy root `drugshop.db` (110,592 bytes, SHA256 `E2AEED56CF6C7ACF1D8F5C2E4838A4DACEDFF75230859638324CEB7B3A14542C`), byte-identical to the verified `instance/backups/drugshop-pre-packaging-20261021-161243.db`; backup `PRAGMA integrity_check = ok`. Added `scripts/dry_run_packaging.py` and `docs/onboarding-runbook.md` / `docs/rollback-runbook.md`; extended `scripts/smoke.ps1` with plan-aware `/api/apps`, POS/Patients, Tender redirect, and `-Username` / `SMOKE_PASSWORD`. Dry run applied `002_app_entitlements.sql`, preserved all 15 business table row counts, passed Legacy/Pro -> Core -> re-upgrade access matrix, restored the verified backup, and confirmed the live DB hash unchanged. `index.html` is 86,250 bytes / 3,061 lines; no redesign. |
| 6 — Pilot | IN PROGRESS (Day 0 done; ends 2026-11-04) | 212 tests, ruff clean; live Legacy smoke 15/15; staging Core/Pro/Core smoke 15/15; business row counts unchanged | Corrected Phase 6 from Pro to **Legacy**. Deployed live at 2026-10-21 19:24:13 after a verified pre-pilot backup (`instance/backups/drugshop-pre-pilot-20261021-192335.db`, SHA256 `E2AEED56...A14542C`): migration `002` applied, six Legacy entitlements, users/products/sales/patients counts unchanged. Changed entitlement denials from INFO to WARNING so default logs capture them; `scripts/pilot_metrics.py` reports activation, logins, counts, and 403s without writing the DB. Added `/api/backup` to smoke. Created `instance/staging-core` and rehearsed Core -> Pro -> Core with smoke green and zero row loss. Owner walkthrough, upgrade demo, and the 14-day observation remain pending. |

---

## Appendix A — File map

```text
drugshop/apps/
├── __init__.py          # package docstring, exports
├── registry.py          # APPS, BUNDLES, BLUEPRINT_APPS, overrides
├── service.py           # entitlements, seeding, plan changes, events
├── guards.py            # endpoint map + before_request gate
├── routes.py            # GET /api/apps
└── cli.py               # flask plan ... commands

drugshop/migrations/002_app_entitlements.sql
drugshop/static/js/core/apps.js
drugshop/templates/index.html          # launcher, data-app, plan panel
drugshop/static/js/core/ui.js          # tab guard
drugshop/static/js/boot.js             # apps bootstrap + grouped loaders
drugshop/static/js/core/api.js         # 403 handling
drugshop/__init__.py                   # register blueprint, gate, CLI
drugshop/schema.sql                    # new tables
docs/tender-standalone.md              # separate-domain mapping, demo hygiene
docs/onboarding-runbook.md             # backup, activation, smoke, handover
docs/rollback-runbook.md               # access/code/data rollback
docs/pilot-runbook.md                  # Onzima deployment + 14-day observation
docs/pilot-tracker.md                  # pilot baseline, metrics, exit decision
run.py                                 # ensure_entitlements
config.py                              # DEFAULT_BUNDLE, SUPPORT_WHATSAPP
tests/conftest.py                      # seed Pro
tests/test_apps.py                     # registry
tests/test_entitlements.py             # service + CLI
tests/test_app_gate.py                 # enforcement
tests/test_apps_api.py                 # payload
scripts/smoke.ps1                      # plan-aware packaging checks
scripts/dry_run_packaging.py           # migration/plan/restore rehearsal
scripts/pilot_metrics.py               # read-only pilot metrics + 403 scan
```

## Appendix B — Smoke checklist additions

| Check | Expected |
|---|---|
| `GET /api/apps` as admin | 200, plan + apps |
| `GET /api/patients` on Pro | 200 |
| `GET /api/patients` after Core downgrade | 403 `app not entitled` |
| `GET /api/employees` (nonexistent) | 404, not 403 |
| `GET /api/backup` on Core | 200 (always-on) |
| `GET /tender` on Core | redirect to upgrade |
| `GET /tender` on Tender | 200 |
| `POST /api/login` with wrong password | 401 |
| Launcher HTML contains `appsGrid` | yes |
| Plan panel shows bundle | yes |

## Appendix C — Grandfathering note

Onzima Charles Drug Shop is the reference installation. It must be seeded as
**Legacy** (Pro + Alerts + Tender) on the first boot after deployment, so no
current feature disappears. The non-sellable bundle is recorded in
`entitlement_events` with the default-bundle bootstrap event.
Do not announce bundles to Onzima until the pilot has run for two weeks. If a
renewal discussion happens sooner, the answer is: "Your current features are
unchanged."

## Appendix D — Why not per-module migrations

The current runner applies numbered, global SQL files in one transaction per
file. Per-module migrations would require a dependency graph, module version
tracking, partial upgrade states, and a rollback story for each module. At 20
customers and one deployable, this is pure cost. Entitlements change rows, not
schema. The global runner stays.

## Appendix E — Success metrics for the pilot

| Metric | Target |
|---|---|
| Activation time per customer | < 15 minutes |
| Unentitled 403s during normal Pro use | 0 |
| Downgrade/upgrade data loss | 0 rows |
| Support hours per customer per month | ≤ 2 |
| Upgrade demo → paid conversion | ≥ 1 in the first quarter |
| Time to quote a bundle | < 5 minutes |

Record the actuals in [`docs/pilot-tracker.md`](docs/pilot-tracker.md).
