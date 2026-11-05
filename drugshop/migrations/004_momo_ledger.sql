-- Phase 1: durable mobile-money reference ledger.
-- The ledger is the anti-replay source of truth; sale rows may be deleted on
-- void, but a consumed reference must remain claimed.

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

CREATE TABLE IF NOT EXISTS momo_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT DEFAULT '',
    event TEXT NOT NULL,
    actor TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_momo_events_reference ON momo_events(reference, created_at);

-- Backfill references already recorded on sales. A basket writes several rows
-- with the same reference, so group by the case-insensitive reference and sum
-- the receipt total. These rows are consumed and can never be claimed again.
INSERT OR IGNORE INTO momo_collections(
    reference, idempotency_key, external_id, amount, currency, phone, status,
    source, sale_id, sale_receipt_ref, created_at, updated_at)
SELECT
    MIN(TRIM(momo_ref)),
    'legacy:' || LOWER(TRIM(MIN(momo_ref))),
    '',
    COALESCE(SUM(total), 0),
    '',
    '',
    'CONSUMED',
    'LEGACY',
    MIN(id),
    COALESCE(NULLIF(MIN(receipt_ref), ''), 'R-' || printf('%06d', MIN(id))),
    COALESCE(NULLIF(MIN(created_at), ''), datetime('now','localtime')),
    datetime('now','localtime')
FROM sales
WHERE TRIM(COALESCE(momo_ref, '')) <> ''
GROUP BY LOWER(TRIM(momo_ref));
