# Project Overview & Mobile Money Architecture: Onzima Dawa

> **Target Audience:** Developers and AI Agents working on payment integrations, mobile money gateways (MTN MoMo, Airtel Money, or aggregators), and financial reconciliation for this repository.

---

## 1. Executive Summary & Business Context

**Onzima Dawa** is a modular pharmacy management and point-of-sale (POS) web application paired with a **Tender Copilot** workspace. It is actively built for and piloted at **Onzima Charles Drug Shop** in Kireka, Uganda, with tender capabilities for **Communion Engineering Services Ltd** in Jinja.

- **Primary Currency:** Ugandan Shillings (`UGX`).
- **Country Context:** Uganda (East Africa) — where over 80% of digital retail transactions occur via **Mobile Money** (primarily **MTN Mobile Money** and **Airtel Money**).
- **Core Operations:**
  - Fast counter Point of Sale (POS) supporting single-item sales and multi-item baskets.
  - Expiry watchdog and FEFO (First-Expired, First-Out) stock allocation.
  - Chronic-patient refill tracking and automated WhatsApp/SMS reminders.
  - End-of-day cash and mobile money drawer reconciliation (Z-report).
  - Credit ledger for trustworthy customers.

---

## 2. Technology Stack & Repository Structure

### Backend
- **Framework:** Python 3.12+ / 3.14 with **Flask 3.x**.
- **Architecture:** Flask Application Factory pattern (`drugshop/__init__.py`) with modular Blueprints.
- **Database:** **SQLite 3** (`drugshop.db` at root or `instance/drugshop.db`).
  - Single-file database accessed via custom helpers in `drugshop/db.py` (`get_db()`, `q_all()`, `q_one()`).
  - Transactions are handled per request; no heavy ORM like SQLAlchemy is used (raw parameter-bound SQL queries for speed, simplicity, and zero migration locks).
- **Configuration:** `config.py` reads from environment variables (`.env`).

### Frontend
- **Structure:** Server-rendered HTML shells via Jinja2 (`drugshop/templates/`) with modern Vanilla JavaScript modules (`drugshop/static/js/`).
- **Design System:** Vanilla CSS (`drugshop/static/css/`) with dark mode, high-contrast typography, and a dedicated **Mobile Shift View** for counter staff using smartphones.
- **Client API:** Unified fetch wrapper in `drugshop/static/js/core/api.js`.

### Key Directory Layout
```text
andama_mrfss_project/
├── config.py                 # App settings, environment resolution, and defaults
├── run.py                    # Server entrypoint (Flask runner)
├── drugshop.db               # Primary SQLite database file
├── drugshop/
│   ├── __init__.py           # Application factory (create_app), blueprint registrations
│   ├── db.py                 # SQLite helper functions (get_db, q_all, q_one, init_db)
│   ├── schema.sql            # Table definitions (sales, products, reconciliations, etc.)
│   ├── sales/                # POS counter, basket checkout, FEFO allocation, voiding
│   │   ├── routes.py         # /api/sales, /api/sales/cart
│   │   └── service.py        # Receipt generation, daily totals
│   ├── payments/             # Existing MTN MoMo Collections implementation
│   │   ├── momo.py           # Pure-Python MTN MoMo Open API client (stdlib urllib)
│   │   ├── service.py        # Server-side MoMo verification & security checks
│   │   ├── routes.py         # /api/momo/collect, /api/momo/health, status checks
│   │   └── cli.py            # CLI commands: flask --app run momo provision/status
│   ├── finance/              # Cash drawer & mobile money reconciliation, expenses
│   │   └── routes.py         # /api/reconciliation, /api/profit
│   ├── inventory/            # Product catalog, batches, invoices, stock adjustments
│   ├── credit/               # Debt tracking and partial credit repayment
│   ├── notifications/        # SMS and WhatsApp alerts (simulated or gateway)
│   └── static/
│       └── js/
│           ├── pos.js        # POS checkout logic and basket state
│           ├── momo.js       # Frontend MTN MoMo USSD push and polling handler
│           └── finance.js    # Reconciliation form and daily register
```

---

## 3. Current Payment Architecture

### A. Supported Payment Methods
The database and POS currently recognize four payment methods defined in `drugshop/schema.sql`:
1. `CASH`: Physical banknotes handed to the cashier.
2. `MTN_MOMO`: MTN Mobile Money (Uganda prefix `077`, `078`, `076`).
3. `AIRTEL_MOMO`: Airtel Money (Uganda prefix `070`, `075`, `074`).
4. `CREDIT`: Customer debt (requires customer name; restricted to the Pro plan).

### B. Current MTN MoMo Implementation
An end-to-end integration for **MTN MoMo Collections** already exists in `drugshop/payments/`:
- **Client (`drugshop/payments/momo.py`):**
  - Built using Python's standard library (`urllib.request`) to avoid external dependencies.
  - Implements the official MTN Open API specification:
    - Token generation (`POST /collection/token/`).
    - USSD Push Request to Pay (`POST /collection/v1_0/requesttopay`).
    - Transaction polling (`GET /collection/v1_0/requesttopay/{referenceId}`).
    - Sandbox auto-provisioning (`POST /v1_0/apiuser` & API key generation).
- **Verification Service (`drugshop/payments/service.py`):**
  - Provides `verify_reference(reference, amount)`: ensures that before a sale is committed, the MTN reference is `SUCCESSFUL`, matches the exact basket total, and uses the correct currency.
- **Frontend Interaction (`drugshop/static/js/momo.js` & `pos.js`):**
  - When the cashier selects `MTN_MOMO`, an inline prompt box appears.
  - The cashier enters the customer's phone number and clicks "Complete Sale" or "Sell".
  - The browser requests a payment push via `POST /api/momo/collect`.
  - The frontend polls `GET /api/momo/collect/<ref>` every 2 seconds until the customer enters their PIN.
  - Once successful, the sale payload is sent to `POST /api/sales` with `momo_ref`.
  - Cashiers can also uncheck "Request MoMo on customer phone" to record a manual reference if the customer already sent money to the pharmacy merchant code/till directly.

### C. Current Airtel Money Status
- **Schema support:** The `sales` table allows `payment_method = 'AIRTEL_MOMO'`.
- **Reconciliation support:** The `reconciliations` table tracks `expected_airtel` and `counted_airtel`.
- **API Status:** Currently **manual only**. Cashiers select `AIRTEL_MOMO` in the POS, and the sale is recorded without an automated USSD prompt or server-side API verification.

---

## 4. Key Database Tables & Schemas

### `sales` Table
Stores each product line or receipt in a transaction:
```sql
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date TEXT NOT NULL,                -- 'YYYY-MM-DD'
    product_id INTEGER NOT NULL REFERENCES products(id),
    batch_id INTEGER REFERENCES batches(id),
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total REAL NOT NULL,                    -- Line total (UGX)
    payment_method TEXT NOT NULL CHECK (payment_method IN ('CASH','MTN_MOMO','AIRTEL_MOMO','CREDIT')),
    served_by TEXT DEFAULT '',              -- Staff username or display name
    receipt_ref TEXT DEFAULT '',            -- Formatted receipt code, e.g. R-20261102-0001
    customer_name TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    customer_phone TEXT DEFAULT '',
    momo_ref TEXT DEFAULT ''                -- External Telco / Gateway Transaction Reference ID
);
```

### `reconciliations` Table
Stores end-of-day reconciliation between POS records and actual drawer/statements:
```sql
CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_date TEXT NOT NULL UNIQUE,          -- 'YYYY-MM-DD'
    expected_cash REAL DEFAULT 0,
    counted_cash REAL DEFAULT 0,
    expected_mtn REAL DEFAULT 0,            -- Calculated from sales WHERE payment_method='MTN_MOMO'
    counted_mtn REAL DEFAULT 0,             -- Cashier's counted MTN till balance
    expected_airtel REAL DEFAULT 0,         -- Calculated from sales WHERE payment_method='AIRTEL_MOMO'
    counted_airtel REAL DEFAULT 0,          -- Cashier's counted Airtel till balance
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'OPEN',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

### `credit_payments` Table
Tracks repayments of customer debt:
```sql
CREATE TABLE IF NOT EXISTS credit_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    amount REAL NOT NULL,
    pay_date TEXT NOT NULL,
    method TEXT DEFAULT 'CASH',             -- Can be CASH, MTN_MOMO, or AIRTEL_MOMO
    notes TEXT DEFAULT '',
    received_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 5. Sales & Payment Transaction Flow

The transaction lifecycle in the POS is designed to prevent stock leakage and double-charging:

```
[Cashier selects Products in POS]
                │
                ▼
      [Select Payment Method]
     ┌──────────┴──────────┐
     ▼                     ▼
   [CASH]        [MTN_MOMO / AIRTEL_MOMO]
     │                     │
     │            Is automated push enabled?
     │             ├── Yes ──► [Initiate Collection API: USSD prompt pushed to customer phone]
     │             │                    │
     │             │                    ▼
     │             │           [Customer enters Mobile Money PIN]
     │             │                    │
     │             │                    ▼
     │             │           [API returns SUCCESSFUL + Reference ID]
     │             └── No (Manual entry of MoMo Reference / Merchant code transfer)
     │                     │
     └──────────┬──────────┘
                ▼
[POST /api/sales/cart (with momo_ref)]
                │
                ▼
[_momo_guard server-side check]
  ├── Check: Has this momo_ref already been used? (Prevents replay attacks)
  └── Check: Call Telco API to verify reference amount & SUCCESSFUL status
                │
                ▼
[Begin SQLite Transaction]
  ├── Allocate stock using FEFO (First-Expired, First-Out)
  ├── Deduct batch quantities from `batches` table
  ├── Record allocations in `sale_batches` table
  ├── Insert rows into `sales` table with receipt_ref and momo_ref
[Commit SQLite Transaction]
                │
                ▼
[Return Receipt JSON & Print Receipt]
```

---

## 6. Guidelines for Integrating Mobile Money

When implementing **Airtel Money** or an **Aggregator Gateway** (e.g. Relworx, Flutterwave, Beyonic, PayTota, Pegasus):

### 1. Maintain Modular Packaging
- Keep payment gateway drivers isolated in `drugshop/payments/` (e.g., `drugshop/payments/airtel.py` or `drugshop/payments/aggregator.py`).
- Abstract common payment actions into `drugshop/payments/service.py`:
  - `initiate_collection(phone, amount, provider, external_id)`
  - `check_payment_status(reference_id, provider)`
  - `verify_reference(reference, amount, provider)`

### 2. Environment Variables in `.env`
Add new settings with safe development defaults to `.env.example` and read them in `config.py`:
- For MTN: `MOMO_SUBSCRIPTION_KEY`, `MOMO_API_USER`, `MOMO_API_KEY`, `MOMO_TARGET_ENVIRONMENT`, `MOMO_BASE_URL`.
- For Airtel / Aggregators:
  - `AIRTEL_CLIENT_ID`, `AIRTEL_CLIENT_SECRET`, `AIRTEL_ENV` (or aggregator API keys).
  - Webhook secret tokens if asynchronous callbacks are supported.

### 3. Handle Local Network Realities in Uganda
- **Timeouts & USSD Delays:** USSD push prompts in Uganda can take 5 to 30 seconds for the network to deliver to the user's handset. Ensure frontend polling timeouts are generous (60–90 seconds) with an explicit "Cancel" or "Verify Later" option.
- **Fail-safe Manual Fallback:** Pharmacies must never stop selling if the internet or telco gateway is slow. Always allow counter attendants to toggle manual reference entry or proceed without a live API push when offline.
- **Strict Currency Checks:** MTN and Airtel production collections must always be in `UGX`. MTN sandbox only accepts `EUR`.

### 4. Replay & Amount Protection
In `drugshop/sales/routes.py`:
- Never accept a payment reference without verifying that `SELECT id FROM sales WHERE momo_ref=?` returns no results.
- Verify that `paid_amount >= basket_total`.

### 5. Day-End Reconciliation
Any new mobile money channel or aggregator account should automatically flow into `drugshop/finance/routes.py` so the daily Z-report matches the till statements.

---

## 7. Useful Local Commands

- **Run Dev Server:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  python run.py
  ```
- **Check MoMo CLI Status:**
  ```powershell
  python -m flask --app run momo status
  python -m flask --app run momo status --check
  ```
- **Provision Sandbox MTN Credentials:**
  ```powershell
  python -m flask --app run momo provision --save
  ```
- **Run Test Suite:**
  ```powershell
  pytest
  ```
