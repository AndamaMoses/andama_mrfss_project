-- Phase 3: invoices and manual payments.
--
-- Invoices snapshot what was billed; payments record what was collected. Both
-- are operator-only commercial records. Access still lives in app_entitlements.
-- No gateway or carrier integration is involved.

CREATE TABLE IF NOT EXISTS billing_invoices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no    TEXT NOT NULL UNIQUE,
    kind          TEXT NOT NULL
                  CHECK (kind IN ('setup','monthly','addon','other')),
    issue_date    TEXT NOT NULL,
    due_date      TEXT NOT NULL,
    period_start  TEXT,
    period_end    TEXT,
    amount        REAL NOT NULL CHECK (amount > 0),
    currency      TEXT NOT NULL DEFAULT 'UGX',
    status        TEXT NOT NULL DEFAULT 'unpaid'
                  CHECK (status IN ('draft','unpaid','partial','paid','void')),
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS billing_payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    INTEGER NOT NULL REFERENCES billing_invoices(id)
                  ON DELETE RESTRICT,
    paid_on       TEXT NOT NULL,
    amount        REAL NOT NULL CHECK (amount > 0),
    currency      TEXT NOT NULL DEFAULT 'UGX',
    method        TEXT NOT NULL DEFAULT 'other'
                  CHECK (method IN
                    ('cash','bank','mtn_momo','airtel_money','other')),
    reference     TEXT NOT NULL DEFAULT '',
    received_by   TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_billing_invoices_status_due
    ON billing_invoices(status, due_date);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_kind_period
    ON billing_invoices(kind, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_billing_payments_invoice
    ON billing_payments(invoice_id);

-- Money guards enforced by the database, not only by the service:
--   * at most one non-void setup invoice per installation;
--   * at most one non-void monthly invoice per billing period.
-- Voiding is the supported correction path, so a voided row stops guarding.
CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_invoices_setup_unique
    ON billing_invoices(kind)
    WHERE kind = 'setup' AND status != 'void';
CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_invoices_monthly_period_unique
    ON billing_invoices(kind, period_start, period_end)
    WHERE kind = 'monthly' AND status != 'void';
