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
    customer_phone TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sale_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    qty INTEGER NOT NULL DEFAULT 0
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
