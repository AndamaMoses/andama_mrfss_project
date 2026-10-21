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
