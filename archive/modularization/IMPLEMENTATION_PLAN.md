# Modularization — Review & Implementation Plan

**Project:** andama_mrfss_project (Onzima Charles Drug Shop + Communion Engineering Tender Copilot)
**Date:** 2026-10-19
**Status:** Phases 0-8 complete; all work is uncommitted on `refactor/modularization`.

---

## 1. Executive summary

`app.py` is a single 1,356-line file holding the schema, data access, business
logic, auth, 53 route registrations, and two product areas (retail drug shop +
tender copilot). The frontend is four templates, one of which (`index.html`,
108 KB) contains roughly 60 inline JavaScript functions driving the whole app.

This document:

1. Reviews the earlier draft modularization (Section 3) — verdict: direction is
   correct, with five corrections needed.
2. Defines the target architecture (Section 4).
3. Breaks the move into 8 verifiable phases (Section 5) that keep the app
   running at every step.
4. Covers frontend, security, testing, risks, and rollback (Sections 6–10).

No behavior changes happen in Phases 0–4. Security fixes deliberately land in a
separate phase so they are reviewable in isolation.

---

## 2. Current state audit

### 2.1 Metrics

| Item | Value |
|---|---|
| `app.py` size | 1,356 lines, 53 routes, ~60 helper/route functions |
| Templates | `index.html` 108 KB (~60 inline JS functions), `login.html` 16 KB, `staff.html` 16 KB, `tender.html` 7 KB |
| Database | SQLite `drugshop.db`, 14 tables, raw sqlite3 (no ORM) |
| Migrations | Ad-hoc `migrate()` (`app.py:182`) via `ALTER TABLE` probes |
| Tests | None |
| Loose scripts | `diag.py` (password hash probe), `fix_drug_classes.py` (one-off template patch) |
| Auth | Server-side session cookie; global `before_request` gate (`app.py:33`); inline role checks per route |

### 2.2 Structural problems confirmed

| # | Problem | Evidence |
|---|---|---|
| P1 | Schema, logic, and routes co-located | `SCHEMA` string `app.py:38`, routes throughout |
| P2 | Business logic inside route handlers | `deduct_fefo` in sales routes, tender analysis in routes |
| P3 | Duplicated auth checks | `if not me or me["role"] != "admin"` repeated ~14 times |
| P4 | Hardcoded credentials backdoor | `allowed_passwords` allow-list `app.py:1086–1104`; passwords auto-reset at startup `app.py:206–229` |
| P5 | Frontend monolith | `index.html` holds all markup, CSS hooks, and JS for 12 tabs |
| P6 | Patch scripts left in root | `diag.py`, `fix_drug_classes.py` are one-off tools |
| P7 | Dev-server defaults | `debug=True`, fallback `secret_key`, DB path derived from `__file__` |

### 2.3 Existing coupling map (who calls whom)

```
db helpers (get_db/q_one/q_all/execute)
  ^ used by every route
core utils (today_str, parse_date, normalize_ug_phone, get_setting)
  ^ used by sales, patients, notifications, invoices
inventory (stock_levels, expiry_report, deduct_fefo)
  ^ used by sales, dashboard, notifications(low_stock_items), invoices
sales (sales_summary, next_receipt_ref)
  ^ used by finance (reconciliation/profit), dashboard, reports
auth (current_user)
  ^ used by most write routes
```

This is already a one-way dependency graph. The modularization formalizes it —
it does not require redesigning business logic.

---

## 3. Review of the proposed modularization

### 3.1 What holds up

| Proposal | Verdict |
|---|---|
| `create_app()` application factory | Keep — required for testability |
| Blueprints by domain | Keep — matches real route clusters |
| Service layer separate from routes | Keep — highest-value change |
| `schema.sql` extracted | Keep |
| Shared `core/` utilities | Keep |
| Frontend split eventually | Keep — but schedule after backend |

### 3.2 Corrections required

1. **Package name collision.** The draft used `app/` as the package while
   `app.py` still exists at root. Python resolves `import app` ambiguously
   (module vs package) and the existing Windows install path contains spaces
   and an emoji — import order bugs here are hard to diagnose. Use
   **`drugshop/`** as the application package; delete or shim `app.py` only at
   the final cut-over.
2. **Flask-Migrate is wrong for this stack.** Flask-Migrate wraps Alembic,
   which requires SQLAlchemy models. This codebase uses raw sqlite3. Replace
   with a lightweight versioned SQL runner: `migrations/NNN_name.sql` plus a
   `schema_migrations` table. (Adopting SQLAlchemy is a separate, larger
   decision not required for modularization.)
3. **Invoices belong to inventory, not notifications.** Invoice posting
   (`/api/invoices/<id>/post`) writes into `batches`; the notification concern
   is only the SMS text. Keep invoice routes in `inventory`, and let
   `notifications` own only SMS/WhatsApp delivery + log.
4. **Dashboard/reporting needs its own module.** `/api/dashboard` aggregates
   inventory, sales, patients, and credit. If it lives in any one domain it
   creates cross-domain imports. Add `reporting/` as an aggregation-only
   module that may depend on all services (it is a leaf — nothing imports it).
5. **`ensure_admin` behavior must change during auth extraction, not after.**
   It rewrites the admin password hash on every startup (`app.py:213, 221,
   229`). Moving it as-is would preserve a known bug. Phase 4.1 changes it to
   bootstrap-only (create if missing, never reset) and moving the credentials
   to env/config.

### 3.3 Review verdict

> The original blueprint is sound but under-specified in three areas:
> package naming, migration tooling, and cross-cutting module placement
> (dashboard, invoices, settings). With the corrections above, proceed.

---

## 4. Target architecture

### 4.1 Folder structure

```
andama_mrfss_project/
├── run.py                          # dev entry: create_app().run()
├── config.py                       # Base/Dev/Prod configs, env-driven
├── requirements.txt                # add: pytest, ruff (dev extras)
├── drugshop/                       # application package (avoids app.py clash)
│   ├── __init__.py                 # create_app(): blueprints, error handlers, gate
│   ├── db.py                       # get_db, q_one/q_all/execute, session helpers
│   ├── schema.sql                  # full CREATE TABLE set
│   ├── migrations/
│   │   ├── __init__.py             # runner: applies NNN_*.sql in order
│   │   ├── 001_initial.sql
│   │   └── 002_...                 # future changes only
│   ├── core/
│   │   ├── utils.py                # today_str, parse_date, normalize_ug_phone
│   │   └── settings.py             # SHOP_DEFAULTS, get_setting, set_setting
│   ├── auth/
│   │   ├── routes.py               # /api/login, logout, me, personas, users, change-password
│   │   ├── guards.py               # login_required, admin_required, register_gate()
│   │   └── service.py              # verify_login, create_user, change_password
│   ├── inventory/
│   │   ├── routes.py               # products, batches, expiry, invoices, uploads
│   │   └── service.py              # stock_levels, expiry_report, deduct_fefo, post_invoice
│   ├── sales/
│   │   ├── routes.py               # sales, cart, receipts, day-report
│   │   └── service.py              # checkout, checkout_cart, next_receipt_ref, sales_summary
│   ├── credit/
│   │   ├── routes.py               # /api/credit, /pay
│   │   └── service.py              # balances, record_payment
│   ├── customers/
│   │   ├── routes.py               # /api/customers
│   │   └── service.py              # upsert_customer, customer_stats
│   ├── patients/
│   │   ├── routes.py               # /api/patients, /api/reminders
│   │   └── service.py              # refill_due, refill_link
│   ├── finance/
│   │   ├── routes.py               # reconciliation, expenses, profit
│   │   └── service.py              # reconcile, profit_summary
│   ├── notifications/
│   │   ├── routes.py               # /api/alerts/*
│   │   └── service.py              # send_sms_via_gateway, low_stock_messages, wa_link
│   ├── reporting/
│   │   ├── routes.py               # /api/dashboard, my-sales, staff-activity, backup, export
│   │   └── service.py              # dashboard_payload, export_csv
│   ├── admin/
│   │   ├── routes.py               # /api/settings, /api/seed
│   │   └── service.py              # seed_demo_data
│   ├── tender/
│   │   ├── routes.py               # /tender page + /api/tender/*
│   │   └── service.py              # PPDA_REQUIREMENTS, analyze_tender_text,
│   │                               # extract_pdf_text, draft_methodology
│   ├── web/
│   │   └── routes.py               # /, /login, /staff page serving
│   ├── templates/                  # moved from ./templates
│   └── static/                     # moved from ./static
├── instance/                       # runtime data (gitignored)
│   ├── drugshop.db
│   └── uploads/
├── scripts/                        # diag.py, fix_drug_classes.py relocated
├── tests/
│   ├── conftest.py                 # app fixture, temp DB, logged-in client
│   ├── test_auth.py
│   ├── test_inventory.py
│   ├── test_sales.py
│   ├── test_patients.py
│   ├── test_finance.py
│   ├── test_tender.py
│   └── test_reporting.py
└── modularization/IMPLEMENTATION_PLAN.md   # this file
```

### 4.2 Module contracts and dependency rules

Rules (enforced by convention; optionally checked by import-linter later):

1. `core` and `db` import nothing from the feature modules.
2. Feature modules may import `core`, `db`, and named upstream services only.
3. Only `routes.py` files register Flask routes; only `drugshop/__init__.py`
   registers blueprints.
4. A service module never imports another feature's `routes.py`.
5. `reporting` is a leaf: it may import every service, nothing imports it.
6. Templates call HTTP endpoints only; no template imports server code.

Allowed dependency edges:

```
web ──────────────► (none)
core ─────────────► (none)
db ───────────────► core
auth ─────────────► db, core
inventory ────────► db, core
sales ────────────► db, core, inventory, customers
credit ───────────► db, core, sales
customers ────────► db, core
patients ─────────► db, core
notifications ────► db, core, inventory
finance ──────────► db, core, sales
admin ────────────► db, core, auth
tender ───────────► db, core
reporting ────────► all services
```

### 4.3 Route → module mapping (53 registrations)

| Target module | Routes |
|---|---|
| `web` | `/`, `/login`, `/staff` |
| `auth` | `POST /api/login`, `POST /api/logout`, `GET/PUT /api/me`, `GET /api/personas`, `GET/POST /api/users`, `DELETE /api/users/<uid>`, `POST /api/change-password` |
| `inventory` | `GET/POST /api/products`, `PUT/DELETE /api/products/<pid>`, `GET/POST /api/batches`, `DELETE /api/batches/<bid>`, `GET /api/expiry`, `GET/POST /api/invoices`, `POST /api/invoices/<iid>/post`, `DELETE /api/invoices/<iid>`, `GET /uploads/<name>` |
| `sales` | `GET/POST /api/sales`, `POST /api/sales/cart`, `DELETE /api/sales/<sid>`, `GET /api/receipts/<ref>`, `GET /api/sales/<sid>/receipt`, `GET /api/sales/day-report` |
| `credit` | `GET /api/credit`, `POST /api/credit/<sid>/pay` |
| `customers` | `GET/POST /api/customers` |
| `patients` | `GET/POST /api/patients`, `PUT/POST/DELETE /api/patients/<pid>`, `GET /api/reminders` |
| `finance` | `GET /api/reconciliation`, `GET /api/reconciliation/calculate`, `POST /api/reconciliation`, `DELETE /api/reconciliation/<rec_date>`, `GET/POST /api/expenses`, `DELETE /api/expenses/<eid>`, `GET /api/profit` |
| `notifications` | `GET /api/alerts/low-stock`, `POST /api/alerts/send-sms`, `GET /api/alerts/log` |
| `reporting` | `GET /api/dashboard`, `GET /api/my-sales`, `GET /api/staff-activity`, `GET /api/backup`, `GET /api/export/<which>` |
| `admin` | `GET/POST /api/settings`, `POST /api/seed` |
| `tender` | `GET /tender`, `POST /api/tender/analyze`, `GET /api/tender/list`, `GET /api/tender/<tid>`, `POST /api/tender/methodology` |

### 4.4 Auth gate behavior across blueprints

The current global `before_request` gate (`app.py:33`) will live in
`auth/guards.py` as `register_gate(app)`, registered once in `create_app()`.
It keeps the exact `OPEN_API = {"/api/login", "/api/logout", "/api/me",
"/api/seed", "/api/personas"}` allow-list during the migration to preserve
behavior. Per-route role checks are replaced by decorators:

```python
@login_required          # replaces `if not current_user()`
@admin_required          # replaces `if me["role"] != "admin"`
```

---

## 5. Implementation phases

Every phase ends with: tests green, app boots, smoke checklist (Appendix B)
passes on a fresh `git` branch. Phases are independent commits on
`refactor/modularization`; `main` stays releasable throughout.

### Phase 0 — Baseline & safety net (0.5 day)

**Steps**
1. Tag current state: `git tag pre-modularization`.
2. Create branch `refactor/modularization`.
3. Verify venv: `& ".venv\Scripts\python.exe" --version` (record version).
4. Add dev requirements: `pytest`, `ruff`.
5. Write `tests/conftest.py` with an app fixture pointing at a **temp copy**
   of `drugshop.db` (never the real one) and a logged-in test client.
6. Write characterization tests against today's endpoints (no code changes):
   login/logout, product CRUD, batch intake, single + cart sale (FEFO order),
   receipt fetch, credit pay + overpay rejection, refill reminders, invoice
   post, reconciliation upsert, tender text analyze.
7. Freeze a smoke script `scripts/smoke.ps1` capturing the Appendix B checks.

**Acceptance:** `pytest` passes against unmodified `app.py`; smoke script green
with the server from `python app.py`.

### Phase 1 — Config + app factory (1 day)

**New files:** `config.py`, `drugshop/__init__.py`, `run.py`
**Moved:** `SECRET_KEY`, DB path, `UPLOADS_DIR`, Africa's Talking credentials,
`debug` flag into config classes reading env vars with current values as
defaults (so behavior is byte-identical when env is unset).

**Steps**
1. `create_app(config=None)` sets `template_folder`/`static_folder` pointing
   at `drugshop/templates` / `drugshop/static` (move the folders now).
2. Keep `app.py` as a compatibility shim:
   `from drugshop import create_app; app = create_app()` — no route logic
   removed yet in this phase beyond the moved schema/helpers.
3. Keep `BASE_DIR` resolution identical so the existing `drugshop.db` is
   still found (DB stays at repo root until Phase 2 moves it to `instance/`
   with a compatibility fallback).

**Acceptance:** `python app.py` and `python run.py` both boot; all
characterization tests pass; login page renders (templates moved correctly).

### Phase 2 — Database layer + schema file (1 day)

**New files:** `drugshop/db.py`, `drugshop/schema.sql`,
`drugshop/migrations/runner.py`, `migrations/001_initial.sql`

**Steps**
1. Cut `SCHEMA` (`app.py:38`) into `schema.sql` verbatim.
2. Port `get_db`, `q_one`, `q_all`, `execute` into `db.py`. No API change.
3. Replace `migrate()` (`app.py:182`) with a runner that:
   - creates `schema_migrations(version TEXT PRIMARY KEY, applied_at)`;
   - applies `NNN_*.sql` files in order inside a transaction;
   - `001_initial.sql` reproduces schema + the additive `ALTER TABLE`s as
     idempotent statements for existing DBs.
4. Add `instance/` support: config prefers `instance/drugshop.db`, falls back
   to root DB if only that exists (migration shim), logs the chosen path.
5. Point `UPLOAD_DIR` default to `instance/uploads/` with fallback to
   existing `uploads/` when files are present.

**Acceptance:** copy of an existing `drugshop.db` upgrades cleanly; fresh DB
creates all 14 tables; `PRAGMA table_info(sales)` shows `receipt_ref`,
`customer_name`, `created_at`, `customer_phone`.

### Phase 3 — Core + auth guards (0.5 day)

**New files:** `drugshop/core/utils.py`, `drugshop/core/settings.py`,
`drugshop/auth/guards.py`

**Steps**
1. Move `today_str`, `parse_date`, `normalize_ug_phone` to `core/utils.py`.
2. Move `SHOP_DEFAULTS`, `get_setting` to `core/settings.py`; add
   `set_setting` (wraps the INSERT ... ON CONFLICT used in `/api/settings`).
3. Move the `before_request` gate into `auth/guards.py` as `register_gate(app)`;
   add `login_required` and `admin_required` decorators (not applied anywhere
   yet — applied per-module in Phase 4).

**Acceptance:** identical gate behavior proven by a test that hits a protected
endpoint without a session and expects 401, and `/api/login` open.

### Phase 4 — Module extraction (4–5 days)

Order matters (lowest risk first). **Each sub-phase is its own commit** and
ends with the full test suite + smoke run.

| Sub-phase | Blueprint | Moves from `app.py` | Watch-outs |
|---|---|---|---|
| 4.1 | `auth` | login/logout/me/personas/users/change-password, `current_user`, `ensure_admin` | Remove the password allow-list backdoor; `ensure_admin` becomes create-if-missing only (no hash reset); new users created with env-seeded credentials via `ADMIN_BOOTSTRAP_PASSWORD` (default kept for one release, then removed) |
| 4.2 | `inventory` | products, batches, expiry, invoices, uploads, `stock_levels`, `expiry_report`, `deduct_fefo` | `deduct_fefo` must stay transactional; invoice delete must still remove the file on disk |
| 4.3 | `sales` | sales, cart, receipts, day-report, `next_receipt_ref`, `sales_summary` | Cart total math and receipt ref sequence must not change |
| 4.4 | `patients` | patients CRUD, `/api/reminders`, `refill_due` | Keep `cycle_days` default 30 and Day-25 remind logic byte-identical |
| 4.5 | `customers` | `/api/customers`, `upsert_customer` | Phone digit normalization must stay identical |
| 4.6 | `credit` | `/api/credit`, pay endpoint | Overpayment guard (`paid + amt > total + 0.005`) preserved |
| 4.7 | `finance` | reconciliation, expenses, profit | `ON CONFLICT(rec_date)` upsert preserved |
| 4.8 | `notifications` | alerts, `send_sms_via_gateway`, `low_stock_items` | Simulated vs sent status codes (201/502) preserved |
| 4.9 | `reporting` | dashboard, my-sales, staff-activity, backup, export | Dashboard aggregation counts must match current numbers |
| 4.10 | `admin` | settings, seed | Seed guard ("already seeded") preserved |
| 4.11 | `tender` | tender page + 4 API routes + 3 service functions | `pypdf` extraction limits (80 pages / 60k chars) preserved |

**Blueprints registration** in `create_app()`:

```python
from drugshop.web.routes import bp as web_bp
from drugshop.auth.routes import bp as auth_bp
# ... one import per module
app.register_blueprint(web_bp)
app.register_blueprint(auth_bp, url_prefix="")
# tender gets its own url_prefix only if desired; current paths stay /api/tender/*
```

**Per sub-phase acceptance:** the service functions are callable without a
Flask request context where the current code allows it; route functions are
≤ ~15 lines (route → validate → call service → respond).

### Phase 5 — Cut-over (0.5 day)

1. Delete `app.py`.
2. `run.py` becomes the single entry point; update README run instructions.
3. Move `diag.py` and `fix_drug_classes.py` to `scripts/`.
4. Confirm no import cycles: `python -X importtime -c "import drugshop" 2>&1`
   should not error; optionally add `import-linter` contract from Section 4.2.

**Acceptance:** fresh clone + `pip install -r requirements.txt` +
`python run.py` works; full test suite passes.

### Phase 6 — Security hardening (1 day, separate PR/commit series)

1. **Remove the credential backdoor** (`app.py:1086–1104` in the old code) —
   plain `check_password_hash` only.
2. **Stop resetting passwords at startup** in `ensure_admin`; expose
   `flask --app run bootstrap-admin` or a `scripts/create_admin.py` instead.
3. `secret_key` required in prod config; fail fast when missing.
4. `debug` default False; opt-in via `FLASK_DEBUG=1`.
5. Session cookie flags: `SESSION_COOKIE_HTTPONLY=True`,
   `SESSION_COOKIE_SAMESITE="Lax"`; document HTTPS-only deployment.
6. Optional: rate-limit `/api/login`; add CSRF tokens if a browser-only
   single-origin assumption is dropped.

**Acceptance:** logging in with `password`/`admin` no longer works; restarting
the server does not resurrect default passwords; tests updated accordingly.

### Phase 7 — Frontend modularization (2–3 days, independent of 4–6)

1. Extract the `api()` helper and shared formatters from `index.html` into
   `static/js/core/api.js`, `static/js/core/format.js`.
2. Split per-tab logic into `static/js/` modules:
   `dashboard.js`, `pos.js`, `stock.js`, `patients.js`, `finance.js`,
   `credit.js`, `customers.js`, `team.js`, `settings.js`, `alerts.js`.
3. Keep `templates/index.html` as markup + `<script src>` includes; no
   framework introduction (plain JS stays plain JS).
4. Repeat for `staff.html` (smaller) if time allows; `tender.html` is
   self-contained already.

**Acceptance:** every tab exercised manually; zero inline `<script>` blocks
larger than ~50 lines remain in `index.html`.

### Phase 8 — Tests, lint, CI (1 day, starts in Phase 0, completed here)

1. Per-module tests mirroring `tests/` layout in Section 4.1.
2. `ruff check .` clean (config in `pyproject.toml` or `ruff.toml`).
3. Optional GitHub Actions: install, `ruff`, `pytest` on push.

**Acceptance:** `pytest -q` green; `ruff` exit 0.

**Status:** complete. See execution log #37.

---

## 6. Frontend modularization notes (detail)

The biggest single file in the repo is `templates/index.html` (108 KB). It
mixes CSS, HTML templates for 12 tabs, and ~60 JS functions. Recommended load
order (plain script tags, no bundler needed):

```html
<script src="/static/js/core/api.js"></script>
<script src="/static/js/core/format.js"></script>
<script src="/static/js/dashboard.js"></script>
<script src="/static/js/pos.js"></script>
<!-- ... -->
<script src="/static/js/boot.js"></script>   <!-- last: wires events, calls checkMe() -->
```

Rules:
- One global namespace object (`window.APP`) instead of free functions, or
  keep free functions but guarantee unique names (current code relies on bare
  globals in `onclick=` attributes — keep that working by preserving names).
- `boot.js` owns startup so load order of feature files is flexible.
- Move inline `onclick=` handlers to `addEventListener` only where cheap;
  otherwise leave them (they reference globals and must keep working).

---

## 7. Testing & verification strategy

| Layer | Tool | Coverage |
|---|---|---|
| HTTP characterization | pytest + Flask test client | Every endpoint in Appendix B, pre- and post-refactor |
| Service units | pytest | `deduct_fefo` FEFO order, `refill_due` states, `analyze_tender_text` scoring, `profit_summary` math |
| DB migration | pytest | Fresh DB create; old DB upgrade from a checked-in fixture copy |
| Smoke | `scripts/smoke.ps1` | Boot server, hit `/api/me` (401), login, `/api/dashboard` (200) |
| Manual | Chrome checklist | All 12 tabs on `/`, `/staff`, `/login`, `/tender` |

Standard commands (run from repo root, PowerShell):

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
& ".venv\Scripts\python.exe" run.py
Invoke-WebRequest http://127.0.0.1:5000/api/me -UseBasicParsing   # expect 401 JSON
```

Note: a dev server from the earlier preview may still be running; stop it
before starting a new one (`Get-Process python* | Where-Object Path -like '*\.venv\*' | Stop-Process`).

---

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Session invalidation on refactor (cookie secret/config change) | Medium | Users logged out | Keep same `SECRET_KEY` default during migration; only change in Phase 6 |
| Import cycle auth ↔ other modules | Medium | Boot failure | Guards import only `db`/`core`; routes import guards, never the reverse |
| `send_from_directory` template path breaks | Medium | Pages 404 | Explicit `template_folder`/`static_folder` in factory; test each page |
| FEFO transaction regression during extraction | Medium | Stock corruption | Characterization tests on cart + single sale before/after; keep `deduct_fefo` signature |
| SQLite concurrency errors introduced by pooling changes | Low | 500s under load | Do not add pooling in this project; keep per-request connect |
| DB moved to `instance/` loses data | Low | Data loss | Copy, never move; fallback logic; backup before Phase 2 (`/api/backup`) |
| Tender PDF extraction breaks on file re-save path | Low | 400s | Keep `UPLOAD_DIR` fallback resolution; test with a real PDF |
| Frontend globals collide after splitting | Medium | Broken buttons | Load-order doc + smoke test of every `onclick` target name |

Rollback: every phase is a single commit on `refactor/modularization`;
`git revert <sha>` returns to the previous working state. `app.py` exists
unchanged until Phase 5, so worst case is `git checkout main`.

---

## 9. Effort estimate

| Phase | Effort |
|---|---|
| 0 — Baseline & tests | 0.5 day |
| 1 — Config + factory | 1 day |
| 2 — DB layer + migrations | 1 day |
| 3 — Core + guards | 0.5 day |
| 4 — Module extraction (11 sub-phases) | 4–5 days |
| 5 — Cut-over | 0.5 day |
| 6 — Security hardening | 1 day |
| 7 — Frontend split | 2–3 days |
| 8 — Tests/lint/CI completion | 1 day |
| **Total** | **11.5–13.5 days** (backend-only: ~8.5–9.5) |

Suggested cutting order if time-boxed: Phases 0–4 (backend only) deliver 80%
of the maintainability win. Phase 6 (security) is strongly recommended
immediately after. Phase 7 can run as a parallel workstream.

---

## 10. Definition of done

- [ ] No file in the repo exceeds ~400 lines of Python.
- [ ] `drugshop/` package contains one folder per domain; dependency rules
      from Section 4.2 hold (verified by review or import-linter).
- [ ] `python run.py` boots the app; all 53 routes respond exactly as before.
- [ ] `pytest -q` passes; characterization tests predate the refactor.
- [ ] `ruff check .` clean.
- [ ] Credential backdoor removed; no default passwords reset at startup.
- [ ] `instance/` holds DB + uploads; existing data migrated and verified.
- [ ] README updated with the new run/test instructions.
- [ ] `modularization/IMPLEMENTATION_PLAN.md` (this file) marked complete.

---

## Appendix A — Helper inventory → destination

| Current (app.py) | Destination |
|---|---|
| `get_db`, `q_all`, `q_one`, `execute`, `init_db`, `migrate`, `SCHEMA` | `drugshop/db.py`, `schema.sql`, `migrations/` |
| `today_str`, `parse_date`, `normalize_ug_phone` | `drugshop/core/utils.py` |
| `SHOP_DEFAULTS`, `get_setting` | `drugshop/core/settings.py` |
| `current_user`, gate, `ensure_admin` | `drugshop/auth/guards.py` + `service.py` |
| `deduct_fefo`, `expiry_status`, `expiry_report`, `stock_levels` | `drugshop/inventory/service.py` |
| `next_receipt_ref`, `sales_summary` | `drugshop/sales/service.py` |
| `refill_due` | `drugshop/patients/service.py` |
| `upsert_customer` | `drugshop/customers/service.py` |
| `low_stock_items`, `send_sms_via_gateway` | `drugshop/notifications/service.py` |
| `PPDA_REQUIREMENTS`, `extract_pdf_text`, `analyze_tender_text`, `draft_methodology` | `drugshop/tender/service.py` |
| Dashboard/profit/export/backup route logic | `drugshop/reporting/service.py`, `finance/service.py` |

## Appendix B — Endpoint smoke checklist

| # | Check | Expected |
|---|---|---|
| 1 | `GET /api/me` without session | 200 JSON, `{"user": null}` |
| 2 | `POST /api/login` wrong password | 401 JSON |
| 3 | `POST /api/login` admin | 200 + user JSON |
| 4 | `GET /api/dashboard` | 200, counts match pre-refactor |
| 5 | `POST /api/sales/cart` (2 items, CASH) | 201, receipt_ref, stock decremented by FEFO |
| 6 | `GET /api/receipts/<ref>` | 200, lines + total |
| 7 | `POST /api/credit` flow: credit sale then `/pay` overpay | overpay rejected 400 |
| 8 | `POST /api/batches` with past expiry | batch created; appears in `/api/expiry` expired |
| 9 | `POST /api/patients` then `GET /api/reminders` | patient in due/upcoming with `whatsapp_link` |
| 10 | `POST /api/invoices` (multipart) + `/post` | invoice POSTED, batches added |
| 11 | `POST /api/reconciliation` twice same date | second run updates, status computed |
| 12 | `GET /api/alerts/low-stock` + `send-sms` (simulated) | count > 0, sms_log entry SIMULATED |
| 13 | `POST /api/tender/analyze` with text | 201, score, matrix of 14 items |
| 14 | `GET /api/export/sales`, `/api/backup` | CSV / .db download |
| 15 | Pages: `/`, `/login`, `/staff`, `/tender` | all return 200 HTML |

---

# EXECUTION LOG

Branch: `refactor/modularization` | Tag: `pre-modularization` (HEAD before work)
Test command: `.venv\Scripts\python.exe -m pytest -q` | Smoke: `scripts\smoke.ps1`
Entry point: `python run.py` (legacy `app.py` removed in the Phase 5 cut-over);
nothing committed yet.

| Phase | Status | Tests | Notes |
|---|---|---|---|
| 0 — Baseline & safety net | DONE | 57 (56 pass + 1 xfail) | Tag + branch created; pytest/ruff installed; smoke script verified |
| 1 — Config + factory | DONE | 58 (57 pass + 1 xfail) | Templates moved to `drugshop/templates` via `git mv`; added page-render test |
| 2 — DB layer | DONE | 60 (59 pass + 1 xfail) | schema.sql, db.py, migrations runner; 2 new migration tests |
| 3 — Core + guards | DONE | 60 (59 pass + 1 xfail) | Gate now registered in factory; decorators built, not yet applied |
| 4.1 — auth + web blueprints | DONE | 60 (59 pass + 1 xfail) | `app.py` 1356 -> 920 lines; 53 -> 42 routes |
| 4.2-7 — Remaining modules + frontend | DONE | 154 | inventory/sales/patients/customers/credit/finance/notifications/reporting/admin/tender + static JS split |
| 8 — Tests, lint, CI | DONE | 154 | `ruff.toml` gate, GitHub Actions, README run/test docs; smoke 9/9 |

## Findings during execution

1. **CRITICAL — login accepts ANY password.** The allow-list at the old
   `app.py:1087` includes the submitted password (`allowed_passwords =
   [raw_pass, clean_pass, ...]`), so `clean_pass in allowed_passwords` is always
   true — any password logs in and even rewrites the stored hash. Captured as a
   `strict xfail` test (`test_login_wrong_password_401`) so Phase 6 could not
   forget it. **Resolved in Phase 6 (entry #35):** plain
   `check_password_hash`; the xfail is removed and the bypass passwords are
   covered as normal parameterized tests.
2. **Template path bug caught in Phase 1.** Factory-created `template_folder`
   was relative, breaking `send_from_directory` after the folder move. Fixed
   with absolute paths in `create_app`; `tests/test_pages.py` added as guard.
3. **Test fixture bug (Phase 0).** `admin_client` + `staff_client` sharing one
   test client overwrote each other's session; staff now gets its own client.
4. **Phase 0 review fixes (post-completion audit).** Moved `import pytest` to
   the top of `tests/test_auth.py`; refreshed the stale line-number reference in
   the xfail reason; fixed `tests/test_finance.py::test_customer_manual_create`
   whose assertion mixed `and`/`or` precedence (could mask failures or raise
   `IndexError`); hardened `scripts/smoke.ps1` with null-safe 401 checks and an
   explicit anonymous-401 check on `/api/products`.
5. **Phase 1 review fixes (post-completion audit).** Removed dead `BASE_DIR`
   from `app.py` (leftover of the factory rewiring); aligned `app.py` fallback
   runner to `app.run(debug=app.config["DEBUG"])`; removed unused `TestConfig`
   (tests build per-test temp config dynamically); deleted the empty root
   `static/` folder (unreferenced by templates); added `drugshop/static/.gitkeep`
   so the static folder survives checkouts (Phase 7 JS files land there);
   refreshed the package docstring. Verified env overrides work (`DRUGSHOP_DB`,
   `DRUGSHOP_UPLOADS`, `FLASK_DEBUG`).
6. **Phase 2 review fixes (post-completion audit).** `schema.sql` now carries the
   six legacy-added columns directly (`sales`: `receipt_ref`, `customer_name`,
   `created_at`, `customer_phone`; `users`: `display_name`, `phone`) with the
   exact `TEXT DEFAULT ''` defaults of the original ALTERs, so fresh and
   upgraded DBs are identical; probes stay for old DBs. Removed dead
   `db_path()`/`upload_dir()` accessors; `q_all`/`q_one`/`execute` now close the
   connection via `try/finally` (no handle leak on SQL errors); `get_db()`
   raises a clear `RuntimeError` when `init_app()` was never called; corrected
   the migration-runner docstring (files execute first, version row recorded
   after — keep migrations small); moved `users` before `login_events` so the
   schema reads in dependency order.
7. **Phase 3 review fixes (post-completion audit).** Verified verbatim parity
   with the monolith for the gate/`OPEN_API`, `current_user`, `today_str`,
   `parse_date`, `normalize_ug_phone`, `SHOP_DEFAULTS` and `get_setting`.
   Removed the never-used `set_setting` helper + its `execute` import (the
   original inlined the settings UPSERT and still does; nothing imported it).
   Added `tests/test_core_utils.py` — direct unit tests for the helpers
   (previously only exercised indirectly via HTTP). `login_required` /
   `admin_required` stay unused until Phase 4.2+ swaps out inline checks.
8. **Phase 4.1 review fixes (post-completion audit).** Diffed all 8 auth
   routes (`personas`/`login`/`logout`/`me` GET+PUT/`users` GET+POST/delete/
   `change-password`) against the monolith: status codes, response shapes,
   `IntegrityError` handling, `login_events` best-effort insert, and the
   permissive login allow-list are verbatim. Page routes are equivalent
   (`current_app.template_folder` replaces the original `app.template_folder`;
   blueprints cannot bind `app`). No duplicate routes remained in `app.py` and
   no `session` references were left behind; templates are static HTML, so the
   blueprint endpoint renames are collision-safe. Fixed a coverage gap: added
   8 tests for `/api/me` PUT, `/api/users` GET/POST/DELETE (admin gate,
   duplicate username, self-delete guard, unknown user 404) and
   unknown-username login.
9. **Phase 4.2 executed with in-stride review (`inventory` module).** New
   `drugshop/inventory/` with `service.py` (`deduct_fefo`, `expiry_status`,
   `stock_levels`, `expiry_report`) and `routes.py` (9 registrations:
   products GET/POST, product PUT/DELETE, batch delete, batches GET/POST,
   expiry, invoices GET/POST, invoice post, invoice delete, uploads).
   Mechanical diff vs the monolith: all 13 functions verbatim after
   normalizing two intentional substitutions — `@admin_required` replaces the
   inline check on the three fully-admin views (`api_product_one`,
   `api_batch_del`, `api_invoice_del`; mixed-method `api_products` keeps its
   inline POST check), and `UPLOAD_DIR` → `upload_dir()` (module-state
   accessor, re-added to `db.py` — it was removed in the Phase 2 review as
   dead code and now has real consumers; test/real paths behave identically).
   Watch-outs held: `deduct_fefo` stays transactional (takes an open `db`),
   invoice delete still removes the file from disk. `app.py`: 42 → 33 routes,
   `sqlite3` import dropped, `UPLOAD_DIR` global kept (tender upload still
   uses it until 4.11) so no conftest change was needed. Verified: targeted
   30 pass; full suite 77 pass + 1 xfail; smoke 9/9; import check 54 url
   rules.
10. **Phase 4.3 executed with in-stride review (`sales` + `customers` service).**
   New `drugshop/sales/` (`service.py`: `next_receipt_ref`, `sales_summary`;
   `routes.py`: 6 registrations — sales GET/POST, cart, receipt-by-ref,
   receipt-by-sale-id, day-report, sale void) and `drugshop/customers/`
   (`service.py`: `upsert_customer`, moved ahead of 4.5 because the sales
   routes are its only remaining callers besides the still-legacy
   `/api/customers` route, which now imports it from the package). Mechanical
   diff vs the monolith: all 9 functions verbatim after normalizing the single
   intentional substitution (`@admin_required` on the void route; the
   mixed/no-auth views keep their original checks). Documented plan switch:
   dependency edge for `sales` is now `db, core, inventory, customers` (the
   plan's edge list had omitted customers although the code always called
   `upsert_customer` from checkout). Cart total math and receipt ref
   sequencing unchanged. `app.py`: 33 → 27 routes; `deduct_fefo` import
   dropped; `sales_summary` still imported there for dashboard/reconciliation
   until 4.7/4.9 move. New tests: sales list for day, receipt by sale id,
   cart CREDIT requires customer name. Verified: targeted 40 pass; full suite
   80 pass + 1 xfail; smoke 9/9.
11. **Phase 4.4 executed with in-stride review (`patients` module).** New
   `drugshop/patients/` (`service.py`: `refill_due`; `routes.py`: 3
   registrations — patients GET/POST, patient PUT/DELETE/POST, reminders).
   Mechanical diff vs the monolith: all 4 functions byte-identical (no
   substitutions — the mixed-method `api_patient_one` keeps its inline admin
   check in the DELETE branch). Watch-out held: `cycle_days` default 30 and
   the Day-25 remind logic are unchanged, including the in-function
   `urllib.parse.quote` import. `app.py`: 27 → 24 routes; `parse_date` import
   dropped (no other users); `refill_due` still imported there for the
   dashboard until 4.9 moves. New test: patient update (PUT). Verified:
   targeted 29 pass; full suite 81 pass + 1 xfail; smoke 9/9.
12. **Phase 4.5 executed with in-stride review (`customers` routes).** New
   `drugshop/customers/routes.py` (`/api/customers` GET search-with-stats /
   POST manual create + notes). Mechanical diff vs the monolith: byte-identical.
   Watch-out held: phone digit normalization (`normalize_ug_phone`) unchanged,
   as is the `ph[-9:]` sales-matching SQL. `app.py`: 24 → 23 routes;
   `upsert_customer` import dropped (service stays for sales routes). New test:
   POST validation without name/phone → 400. Verified: targeted 19 pass; full
   suite 82 pass + 1 xfail; smoke 9/9.
13. **Phase 4.6 executed with in-stride review (`credit` module).** New
   `drugshop/credit/routes.py` (no service file — the two views had no
   helpers): `/api/credit` ledger, `/api/credit/<sid>/pay`. Mechanical diff vs
   the monolith: byte-identical. Watch-out held: overpayment guard
   (`paid + amt > total + 0.005`) and 404 for non-credit sales unchanged; no
   admin gate (staff may record payments, as before). `app.py`: 23 → 21
   routes. New test: pay validation (−5 → 400, "abc" → 400, unknown sale →
   404). Verified: targeted 21 pass; full suite 83 pass + 1 xfail; smoke 9/9.
14. **Phase 4.7 executed with in-stride review (`finance` module).** New
   `drugshop/finance/routes.py` (no service file — views use
   `sales_summary` from the sales service): reconciliation (calc / upsert /
   delete), expenses (list-or-create / delete), profit. Mechanical diff vs the
   monolith: all 6 functions byte-identical after normalizing the two
   single-method admin views (`api_rec_del`, `api_expense_del`) to
   `@admin_required` — their monolith bodies checked admin at the top for all
   methods, so behavior is unchanged. Watch-out held: `ON CONFLICT(rec_date)
   DO UPDATE` upsert, the `abs(diff) < 0.5` BALANCED threshold, and the profit
   formula unchanged. `app.py`: 21 → 15 routes. New test: expense/reconciliation
   delete staff → 403. Verified: targeted 10 pass; full suite 84 pass + 1
   xfail; smoke 9/9.
15. **Phase 4.8 executed with in-stride review (`notifications` module).** New
   `drugshop/notifications/` (`service.py`: `send_sms_via_gateway`,
   `low_stock_items`; `routes.py`: `/api/alerts/low-stock`, `/api/alerts/send-sms`,
   `/api/alerts/log`). Mechanical diff vs the monolith: all 5 functions
   byte-identical. Watch-out held: SIMULATED/SENT/WHATSAPP_LINK → 201 vs
   FAILED → 502 mapping unchanged. `/api/settings` stays in app.py (moves in
   4.10). `app.py`: 15 → 12 routes; `normalize_ug_phone` import dropped;
   `get_setting`/`stock_levels` kept for settings/dashboard/export. New tests:
   send-sms 400 validation, FAILED → 502 (monkeypatched gateway). Verified:
   targeted 14 pass; full suite 86 pass + 1 xfail; smoke 9/9.
16. **Phase 4.9 executed with in-stride review (`reporting` module).** New
   `drugshop/reporting/routes.py` (no service file — views compose existing
   services): my-sales, staff-activity, dashboard, backup, CSV export.
   Mechanical diff vs the monolith: all 5 functions byte-identical after two
   documented substitutions — `api_staff_activity` → `@admin_required`
   (admin for its only method) and `api_backup` → new `db_path()` accessor in
   `db.py` instead of the legacy `DB_PATH` global (same value; accessor pattern
   like `upload_dir()`; conftest's `init_app(TestPaths)` feeds it, so the temp
   DB patch still works). Watch-out held: dashboard aggregation counts and CSV
   columns unchanged. `app.py`: 12 → 7 routes; dead imports removed
   (`send_file`, `Response`, `current_user`, `today_str`, `expiry_report`,
   `stock_levels`, `refill_due`, `sales_summary`). New test: stock + patients
   CSV exports. Verified: targeted 16 pass; full suite 87 pass + 1 xfail;
   smoke 9/9.
    - Note: `ruff check .` has 25 pre-existing findings (13×BLE001, 6×I001,
      2×S112, 2×S110, SIM102, SIM115) present since the monolith and carried
      through verbatim moves; deferred to Phase 8 (which owns the ruff gate +
      config) rather than churning verbatim code mid-phase.
17. **Phase 4.10 executed with in-stride review (`admin` module).** New
   `drugshop/admin/routes.py` (no service file): `/api/settings` (GET
   allow-listed defaults / POST upsert) and `/api/seed` (demo data). Mechanical
   diff vs the monolith: both functions byte-identical. Watch-out held: seed
   guard returns `"already seeded"` on the second call (new test asserts both
   notes). `app.py`: 7 → 5 routes (all tender — 4.11 removes them and the
   file); dead imports removed (`date`/`timedelta`, `SHOP_DEFAULTS`,
   `get_setting`, `get_db`). Verified: targeted 21 pass; full suite 88 pass +
   1 xfail; smoke 9/9.

18. **Phase 4.11 executed with in-stride review (`tender` module).** New
    `drugshop/tender/` (`service.py`: `PPDA_REQUIREMENTS`, `extract_pdf_text`,
    `analyze_tender_text`, `draft_methodology`; `routes.py`: 5 registrations —
    `/tender`, analyze, list, detail, methodology). Mechanical diff vs the
    monolith: all 3 service functions byte-identical and 3 route bodies
    byte-identical; two documented substitutions in `tender_page` /
    `api_tender_analyze` (`app.template_folder` → `current_app.template_folder`
    and `UPLOAD_DIR` → `upload_dir()`). Watch-out held: PDF limits (80 pages /
    60k chars) and keyword scoring unchanged. Review hardening: uploaded
    filenames are now reduced to a basename before joining the upload dir
    (path-traversal fix; normal names unchanged) and the text-file branch uses
    a context manager (no leaked handle). `app.py`: 5 → 0 routes (shim only,
    still needed for conftest/run.py until Phase 5). New tests: detail 404,
    multipart text upload, multipart PDF branch (extractor monkeypatched),
    filename-traversal guard. Verified: targeted 10 pass; full suite 92 pass +
    1 xfail; route map 54 rules.

19. **Phase 0 review (safety net).** Added the missing FEFO characterization
    test (two batches, later-expiry inserted first, cross-batch sale asserts
    earliest-expiry batch is consumed and recorded as the sale's `batch_id`) —
    the gap the risk register warned about. Tightened `scripts/smoke.ps1`
    check 1 to require `/api/me` anonymous = 200 with `user: null` instead of
    accepting 401; corrected Appendix B #1 to match the real (and intended)
    contract; refreshed stale Phase 4 docstrings in `tests/conftest.py` and
    `run.py`. Verified: `test_sales.py` 12 pass; ruff clean on the touched
    files; full suite 93 pass + 1 xfail after the fix.

20. **Phase 4.1 review (auth + web) + dependency revalidation.** Mechanical
    AST diff vs the monolith: all 8 auth route functions and `current_user`
    byte-identical, `OPEN_API` identical, web page routes differ only by the
    documented `current_app.template_folder` substitution. `ensure_admin` is a
    behavior-preserving loop over the same three users (only console wording
    differs). Reinstalled/validated deps: `pip install -r
    requirements-dev.txt` exit 0, `pip check` clean (Flask 3.1.3, pypdf
    6.20.1, pytest 9.1.1, ruff 0.17.1; the earlier pip traceback was only a
    cp1252 console-encoding crash on the emoji in the project path, fixed by
    forcing UTF-8). Fixed stale docstrings in `guards.py` and
    `drugshop/__init__.py`; added the two missing route tests (non-admin
    `POST /api/users` → 403, too-short password change → 400). The login
    backdoor, boot-time password resets, console-printed credentials, and
    open `/api/seed` + `/api/personas` remain deliberately deferred to
    Phase 6 (deviations 1/3); the strict xfail still guards the backdoor.
    Verified: targeted 20 pass + 1 xfail; full suite 95 pass + 1 xfail.

21. **Phase 4.11 review (tender).** Re-diffed after implementation: all 3
    service functions and 3 of 5 route bodies remain byte-identical to the
    monolith; the other two differ only by the documented
    `current_app.template_folder` / `upload_dir()` substitutions plus the
    earlier filename-basename and context-manager hardening. Found and fixed
    a **stored XSS** in `tender.html`: the history list (`filename`,
    `uploaded_at`), the matrix `snippet` (text extracted from the uploaded
    tender) and the deadline `risk` text were interpolated into `innerHTML`
    unescaped. Added an `esc()` helper and escaped every dynamic value in
    `render()` / `loadHist()`. Added the missing watch-out coverage: PDF page
    cap (80) + char cap (60k) with a fake pypdf reader, empty-text scoring
    (14 rows, score 0), and the corrupt-PDF → 400 branch. Confirmed pypdf
    supports `reader.pages[:80]` on a real generated PDF. Remaining ruff
    findings in the module are the same intentional broad excepts carried
    verbatim from the monolith (Phase 8). Verified: tender+pages 13 pass;
    full suite 98 pass + 1 xfail.

22. **Phase 1 review (config + app factory).** Verified `create_app()` matches
    the monolith: same `SECRET_KEY` default, root `drugshop.db` fallback,
    `instance/uploads` default while the legacy `uploads/` is empty, and dev
    `DEBUG=True`; route map identical (54). Live-booted both `run.py` and
    `app.py` against a temp DB: smoke 9/9. Fixed Phase-1 leftovers: `app.py`
    still exported dead `DB_PATH`/`UPLOAD_DIR` globals (plus a redundant
    `os.makedirs`) that no module reads since 4.11, and `tests/conftest.py`
    still monkeypatched them as no-ops — both removed. Added
    `tests/test_config.py` (3 tests): subprocess-verified env overrides
    (`DRUGSHOP_DB`, `DRUGSHOP_UPLOADS`, `SECRET_KEY`, `FLASK_DEBUG`), default
    parity (DB/upload/Debug), and `create_app(config)` accepting a config
    object (54 routes, all four pages render). Verified: target 3 pass; full
    suite 113 pass + 1 xfail; ruff clean on the touched files; smoke 9/9.

23. **Phase 2 review (db + schema + migrations).** Verified fresh-DB vs the
    live `drugshop.db`: identical table sets and identical `PRAGMA
    table_info` output for every table; fresh init applies
    `001_sale_batches.sql` once and is idempotent. Fixed two real gaps:
    (a) the runner used `executescript` with no transaction, so a failing
    multi-statement migration could leave partial DDL with no version row —
    it now runs each file statement-by-statement inside `BEGIN`/`COMMIT`
    (rollback on `sqlite3.Error`, trigger-safe splitter using
    `sqlite3.complete_statement`) and records the version only on success;
    (b) `init_db`/`_upgrade_legacy_columns` leaked their connection when the
    schema read or an ALTER failed — both now `try/finally`. Migration
    discovery is limited to regular `*.sql` files. New tests: failing
    migration rolls back and stays unrecorded, fresh DB creates the schema +
    records 001 (second run no-op), legacy upgrade preserves the sale row and
    backfills `receipt_ref` (`R-000001`) + admin `display_name`. Verified:
    migrations target 4 pass; full suite 115 pass + 1 xfail; ruff clean on
    touched files; fresh/legacy parity clean; smoke 9/9.

24. **Phase 3 review (core + guards).** Re-diffed `today_str`, `parse_date`,
    `normalize_ug_phone`, `SHOP_DEFAULTS`, `get_setting`, `current_user`,
    `OPEN_API` and the gate against the monolith: byte-identical. Found one
    behavioral drift in the new decorator: `admin_required` returned 401 when
    the session user no longer existed, while every original inline check
    (`if not me or me["role"] != "admin"`) returned `{"error":"admin only"},
    403`; aligned the decorator with the original (the global gate still
    answers anonymous requests with 401). Refreshed the guards docstring
    (`login_required` is intentionally unused — the `/api/` gate covers login
    — and stays for non-`/api/` routes). New tests: staff → 403 on a decorated
    route, stale session uid → 403 matching the monolith, `/api/me`
    `display_name` → username fallback, and `get_setting` falling back to the
    default when the stored value is blank. Verified: auth+core target 41
    pass + 1 xfail; full suite 118 pass + 1 xfail; ruff clean on touched
    files; smoke 9/9.

25. **Phase 4.2 review (inventory).** Re-diffed all route/service functions
    against the monolith: verbatim apart from the documented
    `@admin_required` substitutions (byte-identical 403s after the Phase 3
    fix) and the `safe_upload_name` / `upload_dir()` hardening. Fixed two
    issues: (a) `POST /api/invoices/<id>/post` parsed `items` inside the open
    connection, so a missing/invalid field raised `KeyError`/`ValueError`
    → 500 and leaked the connection — items are now validated up front (400)
    and the connection commits/rolls back in `try/finally`; (b) invoice delete
    re-ran `safe_upload_name` on the stored filename, which would miss legacy
    files containing characters the sanitizer rewrites (e.g. `#`) and leave
    orphans — deletion now uses the exact on-disk basename (still
    traversal-safe) and catches only `OSError`. Added missing coverage:
    invoice delete removes file + row (new and legacy names), malformed
    invoice post → 400 with no batches/status change, `/uploads/<name>`
    serving, staff 403 on product PUT / batch DELETE / invoice DELETE, and
    batch delete blocked when sales exist. Verified: inventory target 17
    pass; full suite 124 pass + 1 xfail; ruff clean on touched files;
    smoke 9/9.

26. **Phase 4.3 review (sales + customers).** Re-diffed the sale/cart/receipt/
    day-report/void routes, `next_receipt_ref`, `sales_summary` and
    `upsert_customer` against the monolith: verbatim apart from the documented
    `@admin_required` substitution and the `sale_batches` allocation logic.
    Fixed one crash: `POST /api/sales` never validated qty, so qty <= 0 made
    `deduct_fefo_allocations` return no rows and `allocations[0][0]` raised
    `IndexError` → 500; the route now returns 400 `qty must be positive`
    (matching the cart) with stock unchanged. Hardened connection handling in
    single sale, cart and void so the connection always closes in `finally`
    (the ValueError path still rolls back; the cart's existing atomic rollback
    was confirmed). Added coverage: non-positive qty → 400, cart with an
    insufficient second line rolls back the first line (stock and sale rows
    untouched), receipt refs increment within the day, and a sale auto-registers
    the customer by normalized phone via `upsert_customer`. Noted a
    pre-existing quirk: legacy/seeded sales with an empty `receipt_ref` count
    as one distinct value in `next_receipt_ref`, so the first new ref is
    `0002`; left as-is per the "sequence must not change" watch-out. Verified:
    sales target 17 pass; full suite 128 pass + 1 xfail; ruff on the module
    reports only the two intentional broad int-parse excepts carried verbatim
    from the monolith (Phase 8); smoke 9/9.

27. **Phase 4.4 review (patients + reminders).** Re-diffed the three patient
    routes and `refill_due` against the monolith: byte-identical (no
    substitutions — the mixed-method DELETE keeps its inline admin check and
    the in-function `urllib.parse.quote` import stays). Watch-out held:
    `cycle_days` defaults to 30 and the Day-25 reminder math is unchanged.
    Fixed one crash: `cycle_days: null` or a non-numeric value reached
    `int(...)` and raised `TypeError`/`ValueError` → 500 on both patient create
    and update; a small `_cycle_days` normalizer now maps a missing/null value
    to 30 and returns 400 `cycle_days must be a number` otherwise (valid
    numeric values, including 0, are unchanged). Added coverage for that
    (create + update + null default) plus a reminder-state boundary matrix
    (31/30/25/24/20/19 days since refill → OVERDUE/DUE_SOON/DUE_SOON/UPCOMING/
    UPCOMING/OK), WhatsApp `07…` → `256…` normalization, and unparseable
    `last_refill_date` rows being skipped by `/api/reminders`. Verified:
    patients target 9 pass; full suite 131 pass + 1 xfail; ruff clean on
    routes/tests (the service keeps its intentional broad date-parse skip,
    Phase 8); smoke 9/9.

28. **Phase 4.5 review (customers).** Re-diffed `/api/customers` against the
    monolith: byte-identical, and `upsert_customer` was already reviewed in
    4.3. Watch-out held: `normalize_ug_phone` and the `ph[-9:]` sales-matching
    SQL are unchanged. Fixed one stats bug: the owed query used
    `s.customer_name=? OR s.customer_phone=?`, so for a customer with no phone
    the empty-string phone comparison counted every phone-less CREDIT sale,
    regardless of buyer. Both sides are now guarded with `?<>''`, so name-only
    and phone-only customers only see their own credit lines. Added a test:
    a phone-less customer owes 0 despite another phone-less credit buyer, then
    equals their own credit total once they have a credit sale. Verified:
    finance target 12 pass; full suite 132 pass + 1 xfail; ruff clean on
    touched files; smoke 9/9.

29. **Phase 4.6 review (credit).** Re-diffed `/api/credit` and
    `/api/credit/<sid>/pay` against the monolith: byte-identical. Watch-out
    held: the `paid + amt > total + 0.005` overpayment guard and the
    "credit sale not found" 404 are unchanged. Fixed a non-finite amount hole:
    `float("nan")` passed both checks (NaN comparisons are false) and SQLite
    bound it as NULL, recording a null payment and returning `balance: NaN`;
    `inf`/`-inf` were already caught. `math.isfinite` now rejects it with 400
    `valid amount required` before any write. Added a test covering nan/inf
    strings and float NaN, plus an assertion that the ledger is untouched.
    Verified: finance target 13 pass; full suite 133 pass + 1 xfail; ruff
    clean except the intentional pre-existing broad float-parse except
    (Phase 8); smoke 9/9.

30. **Phase 4.7 review (finance).** Re-diffed the reconciliation, expenses and
    profit views: unchanged apart from the existing counted-amount 400
    validation and the two `@admin_required` deletes (403 parity verified in
    Phase 3). Watch-outs held: the `ON CONFLICT(rec_date)` upsert, the
    `abs(diff) < 0.5` BALANCED threshold and the profit formula. Fixed the
    same non-finite hole as 4.6: NaN/inf counted amounts and expense amounts
    slipped past the `<= 0` checks (NaN comparisons are false; inf is
    positive), NaN bound as NULL, and inf would poison SUM/profit.
    `math.isfinite` now returns the existing 400 responses before any write,
    and the reconciliation upsert is wrapped in `try/finally` so the
    connection always closes. Added tests: nan/inf strings + float NaN
    rejected for reconciliation (no row saved) and expenses (no row saved).
    Verified: finance target 14 pass; full suite 134 pass + 1 xfail; ruff
    clean except the intentional broad expense-parse except (Phase 8);
    smoke 9/9.

31. **Phase 4.8 review (notifications).** Re-diffed the three alert routes
    and `send_sms_via_gateway` / `low_stock_items`: byte-identical. Watch-out
    held: SIMULATED/SENT/WHATSAPP_LINK → 201, FAILED → 502, and the sms_log
    write are unchanged. Fixed two malformed-input 500s on
    `POST /api/alerts/send-sms`: a numeric `to` crashed `normalize_ug_phone`
    (non-iterable) and a numeric `message` crashed `.strip()`. Both are now
    type-checked and return the existing 400 before any gateway call or log
    write. Added tests: non-string to/message → 400 with an empty log, and the
    omitted-`to` path falls back to the saved `manager_phone` (07… → 256…
    normalization). Verified: reporting target 18 pass; full suite 136 pass +
    1 xfail; ruff clean on route/tests (the service keeps the intentional
    in-function urllib imports and broad gateway except, Phase 8); smoke 9/9.

32. **Phase 4.9 review (reporting).** Re-diffed my-sales, staff-activity,
    dashboard, backup and export against the monolith: verbatim apart from the
    documented `@admin_required` and `db_path()` substitutions (both
    re-verified; the backup test now asserts the downloaded bytes equal the
    configured DB). Watch-out held: dashboard aggregate counts and CSV columns
    are unchanged. Fixed the dashboard credit total drifting from
    `/api/credit`: it summed raw per-sale balances (float artifacts after cent
    payments, and a small negative could appear within the 0.005 overpayment
    tolerance) while the ledger filters balances > 0.005 and rounds. The
    dashboard now uses the same per-sale filter plus `round`, so both endpoints
    agree. Also compute `stock_levels()` and `refill_due()` once each, making
    the stock/refill aggregates internally consistent (previously stock was
    fetched 3× and refill 2×). Added a test: partial cent payment → dashboard
    == ledger, full payment → 0. Verified: reporting target 19 pass; full suite
    137 pass + 1 xfail; ruff clean except the intentional in-function
    `csv, io` import (I001, Phase 8); smoke 9/9.

33. **Phase 4.10 review (admin).** Re-diffed `/api/settings` and `/api/seed`
    against the monolith: byte-identical; the seed guard ("already seeded")
    is preserved. Fixed three issues: (a) a truthy non-object JSON body
    (e.g. `[1]`) crashed `d.items()` → 500; it now returns 400, and the
    settings writes close the connection in `finally`; (b) seed hardcoded the
    demo batch ids `1`/`2` for its sales rows and stock decrements, so
    re-seeding a wiped DB (AUTOINCREMENT keeps the sequence) failed the FK
    check / decremented nothing — it now captures the inserted batch ids
    (PC-889, BX-221) and uses them; (c) seed wrote in two separate
    transactions (demo rows, then stock), so a failure between them left sales
    without the stock deduction, which the guard then prevented repairing —
    both steps now commit as one transaction (same values on success). Added
    tests: re-seed after deleting all data succeeds and lands at 86/190 stock;
    non-object settings body → 400 with settings unchanged. Verified:
    reporting target 21 pass; full suite 139 pass + 1 xfail; ruff clean;
    smoke 9/9.

34. **Phase 5 cut-over executed + review.** Deleted the legacy root `app.py`;
    `run.py` now builds the app via `create_app()` (still exposing `app` so
    `flask --app run` keeps working) and is the single entry point.
    `tests/conftest.py` creates a fresh app per test through the factory, then
    re-points `db.init_app(TestPaths)` at the temp DB — same isolation, and
    the `client` / `admin_client` / `staff_client` interface is unchanged.
    Moved `diag.py` and `fix_drug_classes.py` to `scripts/`; the latter now
    resolves `drugshop/templates/index.html` from the project root instead of
    the removed `templates/` path. Dropped the stale tracked
    `__pycache__/app.cpython-314.pyc`. `import drugshop` is cycle-free and the
    factory still maps 54 routes; README is business content with no run
    instructions, so no command updates were needed. Verified: full suite 139
    pass + 1 xfail; `python run.py` + smoke 9/9; ruff clean on the changed
    entry-point/fixture/docstring files (moved `scripts/diag.py` keeps its
    pre-existing I001/BLE001, Phase 8).

35. **Phase 6 security hardening executed + review.** Login now does a plain
    `check_password_hash` (the legacy allow-list/backdoor is gone); failed
    logins return the same generic 401 for unknown user and wrong password (no
    default-credential hints, no account enumeration), and a failed attempt
    can no longer rewrite the stored hash. `ensure_admin` now bootstraps the
    default users only when the users table is empty and never updates
    existing passwords, so a restart cannot reset changed credentials.
    Config: `SECRET_KEY` is mandatory for `ProdConfig` (factory raises fast
    when absent), debug defaults off (`FLASK_DEBUG=1` opts in), and session
    cookies are forced HttpOnly + SameSite=Lax (HTTPS-only deployment
    documented in `config.py`). Authorization: `/api/seed` is admin-only
    (removed from `OPEN_API`) and `/api/settings` writes are admin-only while
    signed-in staff can still read them; `/api/personas` stays public for the
    login page but never exposes password material. Login page: removed the
    hardcoded default passwords, prefilled credentials, quick-login buttons
    and password hints; profile cards now only fill the username. Also fixed
    the login route's non-object JSON 500 (now 400). Optional Phase 6 items
    (rate limiting, CSRF tokens) were not needed: SameSite=Lax mitigates
    cross-site POSTs and the app is single-origin; noted for Phase 8 review.
    Verified: full suite 153 pass (the former strict xfail is now a normal
    pass; no xfails left); `python run.py` + smoke 9/9; ruff clean on all
    touched Python files (moved `scripts/diag.py` still carries its
    pre-existing I001/BLE001 for Phase 8).

> **PHASE 6 COMPLETE.** The full security pass is done: the login backdoor is
> removed, startup no longer resets passwords, prod requires `SECRET_KEY`,
> debug defaults off, session cookies are HttpOnly + SameSite=Lax, and
> seed/settings writes are admin-only. The login page no longer ships
> hardcoded default credentials. Nothing committed yet — all work is
> uncommitted on `refactor/modularization`; the `pre-modularization` tag still
> points at the last commit (see risk note below). Next: Phase 7 frontend
> split on your call.

36. **Phase 7 frontend split executed + review.** Extracted the inline
    `index.html` script (76 functions, ~36.6 KB) into 15 plain-JS files:
    `core/api.js` (`$`, `api`, logout/switch), `core/format.js` (formatters),
    `core/ui.js` (`ME`/`TITLES`, tabs/sidebar/profile), `boot.js` (wiring +
    startup), and feature modules dashboard/pos/stock/patients/finance/
    credit/customers/team/settings/alerts/manage. `index.html` now has zero
    inline scripts and 15 `/static/js/...` tags; plain paths are required
    because the page is served by `send_from_directory`, not Jinja. Bare
    global names were kept because inline `onclick=` handlers depend on them;
    `BASKET` remains `var`. Added
    `tests/test_pages.py::test_frontend_modules_are_served` (all assets 200,
    tags present, no inline scripts). Verified: `node --check` all 15 files;
    function set matches the original 76 (plus the new `$`/`today` wrappers);
    all 120 literal `$('id')` targets and all inline handler roots resolve;
    string literals unchanged; no U+FFFD; headless Chrome login + all 10
    sidebar tabs on empty and seeded DBs, basket add/clear, zero JS console
    errors (only a favicon 404); full suite 154 pass; smoke 9/9. `staff.html`
    and `tender.html` inline scripts stay (25/12 lines, under the ~50-line
    limit).

> **PHASE 7 COMPLETE.** All inline app JavaScript now lives under
> `drugshop/static/js/`; `index.html` is markup + external script tags and
> every tab was exercised in headless Chrome against empty and seeded data.
> Nothing committed yet - all work is uncommitted on
> `refactor/modularization`; the `pre-modularization` tag still points at the
> last commit. Next: Phase 8 (ruff gate, CI, final verification).

37. **Phase 8 tests/lint/CI completed + review.** Added `ruff.toml` with an
    explicit `E4/E7/E9/F/I/BLE/S` selection (test-only `S101/S105/S106/S608`
    ignored) and fixed all findings the stricter gate surfaced (22 core
    E/F/I/BLE plus 3 Bandit): import ordering/local imports (`notifications`,
    `reporting`, `scripts/diag`), semicolon statements (`admin`, `reporting`,
    `sales`), non-dict/invalid numeric request handling narrowed in
    `credit`/`finance`/`sales`, date-parsing catches narrowed in
    `inventory`/`patients`, `try/except/continue` restructured in
    `patients`/`tender`, and intentional boundary catches (SMS gateway, PDF
    reader, diagnostic probe) annotated with targeted `# noqa` codes instead
    of disabling a rule globally. All behavior is
    unchanged, including pypdf page-skip output and the 400/502 responses.
    Per-module coverage already spans the Section 4.1 modules plus core/config/
    migrations/pages; no additional test files were needed. Added
    `.github/workflows/ci.yml` (Python 3.12: install, `ruff check .`,
    `pytest -q`) and README local-run/lint/test/smoke instructions. Verified:
    `ruff check .` -> "All checks passed!"; full suite **154 passed** (final
    run 207.34s); fresh-temp-DB `python run.py` + `scripts/smoke.ps1` -> **9/9**;
    largest Python file 237 lines. CI workflow has not been run on GitHub yet.
    Nothing committed; `drugshop.db` remains the pre-existing dirty live file.

> **PHASE 8 COMPLETE.** Phase 8 adds the reproducible lint gate, CI workflow,
> and run/test documentation; every acceptance command is green. Nothing
> committed yet - all work is uncommitted on `refactor/modularization`; the
> `pre-modularization` tag still points at the last commit.

## Deviations from the plan (behavior-preserving, agreed during execution)

1. **Resolved in Phase 6:** the login backdoor was removed as planned; the
   former strict xfail is now a normal passing test. Phase 4.1 had moved the
   auth routes verbatim so the characterization suite could prove equivalence
   before the change.
2. **No `001_initial.sql`.** `schema.sql` is already idempotent
   (`CREATE TABLE IF NOT EXISTS`); the legacy `ALTER TABLE` probes remain in
   `db.py::_upgrade_legacy_columns` because SQLite has no
   `ADD COLUMN IF NOT EXISTS`. Future changes ship as `NNN_*.sql` files.
3. **`ensure_admin` moved to `drugshop/auth/service.py` in Phase 2** (one phase
   early) so the factory/bootstrap flow could be tested immediately. Resolved
   in Phase 6: it only bootstraps an empty users table and never updates
   existing passwords.
4. **Resolved in Phase 5:** `run.py` now builds the app with `create_app()`;
   the legacy root `app.py` was deleted (the `pre-modularization` tag keeps
   the old monolith).
5. **Resolved in Phase 5:** `tests/conftest.py` builds a fresh app through the
   factory, then patches the temp DB via `db.init_app`; the `client` /
   `admin_client` / `staff_client` interface is unchanged.
6. **Africa's Talking credentials remain env reads in
   `notifications/service.py`, not `config.py`.** The gateway stays callable
   outside an app/request context, so `AT_USERNAME` / `AT_API_KEY` /
   `AT_SENDER` are read per call; behavior is unchanged when unset.
   (`SECRET_KEY`, DB path, upload dir and debug do live in config.)

## Repo hygiene notes for Phase 5/8

- `__pycache__/app.cpython-314.pyc` (tracked before this work) was deleted in
  Phase 5; `.gitignore` covers `__pycache__/`.
- `drugshop.db` was already dirty before this work (live data); left untouched.
- `diag.py` / `fix_drug_classes.py` moved to `scripts/` in Phase 5.

## Remaining

None. The phase-by-phase review series
(Phases 0, 1, 2, 3, 4.1–4.10 and 4.11), the Phase 5 cut-over, the Phase 6
security hardening, the Phase 7 frontend split, and Phase 8 verification are
complete.
