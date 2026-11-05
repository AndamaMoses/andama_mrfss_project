CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT DEFAULT 'General',
    unit TEXT DEFAULT 'tabs',
    reorder_level INTEGER DEFAULT 10,
    price_buy REAL DEFAULT 0,
    price_sell REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    batch_no TEXT DEFAULT '',
    qty_received INTEGER DEFAULT 0,
    qty_remaining INTEGER DEFAULT 0,
    expiry_date TEXT NOT NULL,
    supplier TEXT DEFAULT '',
    invoice_no TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_date TEXT NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    batch_id INTEGER REFERENCES batches(id),
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total REAL NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('CASH','MTN_MOMO','AIRTEL_MOMO','CREDIT')),
    served_by TEXT DEFAULT '',
    receipt_ref TEXT DEFAULT '',
    customer_name TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    customer_phone TEXT DEFAULT '',
    momo_ref TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sale_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    qty INTEGER NOT NULL DEFAULT 0
);
-- One row per mobile-money reference. The ledger is the anti-replay source of
-- truth: a sale claim is a conditional UPDATE, so two concurrent checkouts
-- cannot both consume the same payment. Rows are never deleted on void.
CREATE TABLE IF NOT EXISTS momo_collections (
    reference TEXT COLLATE NOCASE PRIMARY KEY,
    idempotency_key TEXT COLLATE NOCASE NOT NULL UNIQUE,
    external_id TEXT DEFAULT '',
    amount REAL NOT NULL DEFAULT 0,
    currency TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','SUCCESSFUL','FAILED','REJECTED','TIMEOUT','UNKNOWN','CONSUMED','VOIDED')),
    source TEXT NOT NULL DEFAULT 'API'
        CHECK (source IN ('API','MANUAL','LEGACY')),
    provider TEXT NOT NULL DEFAULT 'MTN'
        CHECK (provider IN ('MTN','AIRTEL')),
    mtn_status TEXT DEFAULT '',
    mtn_amount REAL,
    mtn_currency TEXT DEFAULT '',
    financial_txn_id TEXT DEFAULT '',
    sale_id INTEGER,
    sale_receipt_ref TEXT DEFAULT '',
    last_error TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    checked_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_momo_collections_status ON momo_collections(status, created_at);
CREATE INDEX IF NOT EXISTS idx_momo_collections_receipt ON momo_collections(sale_receipt_ref);
-- idx_momo_collections_provider_status is created by migration 005 (and by
-- db._ensure_momo_provider_column) so schema.sql can still run against a
-- Phase 1 table that has no provider column yet.
CREATE TABLE IF NOT EXISTS momo_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT DEFAULT '',
    event TEXT NOT NULL,
    actor TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_momo_events_reference ON momo_events(reference, created_at);
CREATE TABLE IF NOT EXISTS stock_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT 'OTHER',
    note TEXT DEFAULT '',
    adjusted_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    product_id INTEGER REFERENCES products(id),
    last_refill_date TEXT NOT NULL,
    cycle_days INTEGER DEFAULT 30,
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_date TEXT NOT NULL UNIQUE,
    expected_cash REAL DEFAULT 0,
    counted_cash REAL DEFAULT 0,
    expected_mtn REAL DEFAULT 0,
    counted_mtn REAL DEFAULT 0,
    expected_airtel REAL DEFAULT 0,
    counted_airtel REAL DEFAULT 0,
    notes TEXT DEFAULT '',
    status TEXT DEFAULT 'OPEN',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
-- Phase 3: one persisted payment-variance snapshot per provider and day. The
-- live view is computed from sales + momo_collections; this table keeps what
-- the books said when the shift was closed.
CREATE TABLE IF NOT EXISTS payment_reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_date TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('MTN','AIRTEL')),
    expected_amount REAL NOT NULL DEFAULT 0,
    consumed_amount REAL NOT NULL DEFAULT 0,
    successful_amount REAL NOT NULL DEFAULT 0,
    pending_amount REAL NOT NULL DEFAULT 0,
    unknown_amount REAL NOT NULL DEFAULT 0,
    orphaned_amount REAL NOT NULL DEFAULT 0,
    unresolved_count INTEGER NOT NULL DEFAULT 0,
    orphaned_count INTEGER NOT NULL DEFAULT 0,
    variance REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'OPEN',
    snapshot TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(rec_date, provider)
);
CREATE INDEX IF NOT EXISTS idx_payment_reconciliations_date
    ON payment_reconciliations(rec_date);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT DEFAULT '',
    supplier TEXT DEFAULT '',
    inv_date TEXT DEFAULT '',
    image_name TEXT DEFAULT '',
    ocr_text TEXT DEFAULT '',
    status TEXT DEFAULT 'PENDING',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS sms_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    to_phone TEXT DEFAULT '',
    channel TEXT DEFAULT 'SMS',
    message TEXT DEFAULT '',
    status TEXT DEFAULT 'SIMULATED',
    response TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tender_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT DEFAULT '',
    uploaded_at TEXT DEFAULT (datetime('now','localtime')),
    text_len INTEGER DEFAULT 0,
    text_excerpt TEXT DEFAULT '',
    compliance_json TEXT DEFAULT '[]',
    risks_json TEXT DEFAULT '[]',
    score REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    pass_hash TEXT NOT NULL,
    role TEXT DEFAULT 'attendant' CHECK (role IN ('admin','attendant')),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    display_name TEXT DEFAULT '',
    phone TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS login_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    username TEXT DEFAULT '',
    login_at TEXT DEFAULT (datetime('now','localtime')),
    ip TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    phone_digits TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS credit_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    amount REAL NOT NULL,
    pay_date TEXT NOT NULL,
    method TEXT DEFAULT 'CASH',
    notes TEXT DEFAULT '',
    received_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exp_date TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    description TEXT DEFAULT '',
    amount REAL NOT NULL,
    paid_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS app_entitlements (
    app_id TEXT PRIMARY KEY,
    bundle TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    activated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS entitlement_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_entitlement_events_created ON entitlement_events(created_at);
