-- Phase 2: record which mobile-money provider owns a ledger reference.
--
-- schema.sql already creates the provider column on a fresh database, while a
-- Phase 1 database has no column yet. SQLite has no "ADD COLUMN IF NOT EXISTS",
-- so the table is rebuilt once. Existing rows predate Airtel support and are
-- correctly MTN. No other table references momo_collections, so the rebuild is
-- safe; indexes are recreated below.

-- A previous interrupted run may have left the temporary table behind.
DROP TABLE IF EXISTS momo_collections_new;

CREATE TABLE IF NOT EXISTS momo_collections_new (
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

INSERT INTO momo_collections_new(
    reference, idempotency_key, external_id, amount, currency, phone, status,
    source, provider, mtn_status, mtn_amount, mtn_currency, financial_txn_id,
    sale_id, sale_receipt_ref, last_error, created_at, updated_at, checked_at)
SELECT
    reference, idempotency_key, external_id, amount, currency, phone, status,
    source, 'MTN', mtn_status, mtn_amount, mtn_currency, financial_txn_id,
    sale_id, sale_receipt_ref, last_error, created_at, updated_at, checked_at
FROM momo_collections;

DROP TABLE momo_collections;
ALTER TABLE momo_collections_new RENAME TO momo_collections;

CREATE INDEX IF NOT EXISTS idx_momo_collections_status
    ON momo_collections(status, created_at);
CREATE INDEX IF NOT EXISTS idx_momo_collections_receipt
    ON momo_collections(sale_receipt_ref);
CREATE INDEX IF NOT EXISTS idx_momo_collections_provider_status
    ON momo_collections(provider, status, created_at);
