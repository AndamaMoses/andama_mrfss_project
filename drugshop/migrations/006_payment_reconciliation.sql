-- Phase 3: persist the per-provider payment variance snapshot for a closed day.
--
-- The live reconciliation view is computed from sales + momo_collections. This
-- table keeps what those books said when the shift was closed, so a later
-- backfill or carrier correction cannot silently rewrite history.
--
-- schema.sql already creates the table on a fresh database; this migration
-- covers an existing installation. IF NOT EXISTS makes the migration harmless
-- when schema.sql ran first.

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
