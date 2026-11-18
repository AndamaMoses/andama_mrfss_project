-- Phase 2: commercial subscription record and audit trail.
--
-- One row per installation (id = 1): the customer's agreed bundle, fees,
-- status, and current billing period. Entitlements remain the source of truth
-- for access; this table is the source of truth for money and commercial terms.
--
-- billing_events keeps every activation, renewal, and status change with the
-- operator and reason, so a later invoice or report can be explained.

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    customer_name         TEXT NOT NULL DEFAULT '',
    contact_name          TEXT NOT NULL DEFAULT '',
    contact_phone         TEXT NOT NULL DEFAULT '',
    bundle                TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN
                            ('pending','active','past_due','cancelled',
                             'expired','grandfathered')),
    currency              TEXT NOT NULL DEFAULT 'UGX',
    setup_fee             REAL NOT NULL DEFAULT 0 CHECK (setup_fee >= 0),
    monthly_fee           REAL NOT NULL DEFAULT 0 CHECK (monthly_fee >= 0),
    started_on            TEXT NOT NULL,
    current_period_start  TEXT,
    current_period_end    TEXT,
    price_book_version    TEXT NOT NULL DEFAULT '',
    notes                 TEXT NOT NULL DEFAULT '',
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS billing_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id  INTEGER REFERENCES billing_subscriptions(id),
    action           TEXT NOT NULL,
    actor            TEXT NOT NULL DEFAULT '',
    detail           TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_status
    ON billing_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_billing_events_subscription
    ON billing_events(subscription_id, created_at);
