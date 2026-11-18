"""Phase 2-3 migration tests for the billing ledger tables."""
import sqlite3

import pytest

from drugshop.migrations import run


def _paths(tmp_path):
    db_file = str(tmp_path / "billing.db")

    class TestPaths:
        DATABASE = db_file
        UPLOAD_DIR = str(tmp_path / "uploads")

    return db_file, TestPaths


def test_fresh_database_creates_billing_tables(tmp_path):
    from drugshop import db as dbm

    db_file, paths = _paths(tmp_path)
    dbm.init_app(paths)
    applied = dbm.init_db()

    assert "007_billing_subscriptions.sql" in applied
    assert "008_billing_invoices.sql" in applied
    assert dbm.init_db() == []

    conn = sqlite3.connect(db_file)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    columns = {
        table: {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for table in (
            "billing_subscriptions",
            "billing_events",
            "billing_invoices",
            "billing_payments",
        )
    }
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name IN ('billing_subscriptions','billing_events',"
            "'billing_invoices','billing_payments')"
        )
    }
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    assert {
        "billing_subscriptions",
        "billing_events",
        "billing_invoices",
        "billing_payments",
    } <= tables
    assert columns["billing_subscriptions"] == {
        "id",
        "customer_name",
        "contact_name",
        "contact_phone",
        "bundle",
        "status",
        "currency",
        "setup_fee",
        "monthly_fee",
        "started_on",
        "current_period_start",
        "current_period_end",
        "price_book_version",
        "notes",
        "created_at",
        "updated_at",
    }
    assert columns["billing_events"] == {
        "id",
        "subscription_id",
        "action",
        "actor",
        "detail",
        "created_at",
    }
    assert columns["billing_invoices"] == {
        "id",
        "invoice_no",
        "kind",
        "issue_date",
        "due_date",
        "period_start",
        "period_end",
        "amount",
        "currency",
        "status",
        "notes",
        "created_at",
    }
    assert columns["billing_payments"] == {
        "id",
        "invoice_id",
        "paid_on",
        "amount",
        "currency",
        "method",
        "reference",
        "received_by",
        "notes",
        "created_at",
    }
    assert {
        "idx_billing_subscriptions_status",
        "idx_billing_events_subscription",
        "idx_billing_invoices_status_due",
        "idx_billing_invoices_kind_period",
        "idx_billing_payments_invoice",
        "idx_billing_invoices_setup_unique",
        "idx_billing_invoices_monthly_period_unique",
    } <= indexes
    assert "007_billing_subscriptions.sql" in versions
    assert "008_billing_invoices.sql" in versions
    assert integrity == "ok"


def test_single_subscription_and_status_constraints(tmp_path):
    from drugshop import db as dbm

    db_file, paths = _paths(tmp_path)
    dbm.init_app(paths)
    dbm.init_db()

    conn = sqlite3.connect(db_file)
    conn.execute(
        "INSERT INTO billing_subscriptions(id, bundle, status, started_on) "
        "VALUES (1, 'pro', 'active', '2026-11-05')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_subscriptions(id, bundle, status, started_on) "
            "VALUES (2, 'pro', 'active', '2026-11-05')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE billing_subscriptions SET status='bogus' WHERE id=1"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE billing_subscriptions SET monthly_fee=-1 WHERE id=1"
        )
    conn.rollback()
    conn.close()


def test_invoice_and_payment_constraints(tmp_path):
    from drugshop import db as dbm

    db_file, paths = _paths(tmp_path)
    dbm.init_app(paths)
    dbm.init_db()

    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO billing_subscriptions(id, bundle, status, started_on) "
        "VALUES (1, 'pro', 'active', '2026-11-05')"
    )
    conn.execute(
        "INSERT INTO billing_invoices("
        "invoice_no, kind, issue_date, due_date, amount, status"
        ") VALUES ('INV-202611-0001','setup','2026-11-12','2026-11-12',600000,"
        "'unpaid')"
    )
    invoice_id = conn.execute("SELECT id FROM billing_invoices").fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_invoices("
            "invoice_no, kind, issue_date, due_date, amount"
            ") VALUES ('INV-202611-0001','setup','2026-11-12','2026-11-12',1)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_invoices("
            "invoice_no, kind, issue_date, due_date, amount"
            ") VALUES ('INV-202611-0002','bogus','2026-11-12','2026-11-12',1)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_invoices("
            "invoice_no, kind, issue_date, due_date, amount"
            ") VALUES ('INV-202611-0003','other','2026-11-12','2026-11-12',0)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE billing_invoices SET status='bogus' WHERE id=?",
            (invoice_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_payments(invoice_id, paid_on, amount, method) "
            "VALUES (?, '2026-11-12', 0, 'cash')",
            (invoice_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_payments(invoice_id, paid_on, amount, method) "
            "VALUES (?, '2026-11-12', 100, 'cheque')",
            (invoice_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_payments(invoice_id, paid_on, amount, method) "
            "VALUES (999, '2026-11-12', 100, 'cash')"
        )
    conn.rollback()
    conn.close()


def test_database_guards_setup_and_monthly_invoices(tmp_path):
    from drugshop import db as dbm

    db_file, paths = _paths(tmp_path)
    dbm.init_app(paths)
    dbm.init_db()

    conn = sqlite3.connect(db_file)
    conn.execute(
        "INSERT INTO billing_invoices("
        "invoice_no, kind, issue_date, due_date, amount"
        ") VALUES ('INV-202611-0001','setup','2026-11-12','2026-11-12',600000)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_invoices("
            "invoice_no, kind, issue_date, due_date, amount"
            ") VALUES ('INV-202611-0002','setup','2026-11-13','2026-11-13',600000)"
        )

    conn.execute(
        "UPDATE billing_invoices SET status='void' "
        "WHERE invoice_no='INV-202611-0001'"
    )
    conn.execute(
        "INSERT INTO billing_invoices("
        "invoice_no, kind, issue_date, due_date, amount"
        ") VALUES ('INV-202611-0003','setup','2026-11-13','2026-11-13',600000)"
    )

    conn.execute(
        "INSERT INTO billing_invoices("
        "invoice_no, kind, issue_date, due_date, period_start, period_end, amount"
        ") VALUES ('INV-202611-0004','monthly','2026-11-05','2026-11-05',"
        "'2026-11-05','2026-12-05',180000)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO billing_invoices("
            "invoice_no, kind, issue_date, due_date,"
            " period_start, period_end, amount"
            ") VALUES ('INV-202611-0005','monthly','2026-11-06','2026-11-06',"
            "'2026-11-05','2026-12-05',180000)"
        )

    conn.execute(
        "UPDATE billing_invoices SET status='void' "
        "WHERE invoice_no='INV-202611-0004'"
    )
    conn.execute(
        "INSERT INTO billing_invoices("
        "invoice_no, kind, issue_date, due_date, period_start, period_end, amount"
        ") VALUES ('INV-202611-0006','monthly','2026-11-06','2026-11-06',"
        "'2026-11-05','2026-12-05',180000)"
    )
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM billing_invoices"
    ).fetchone()[0] == 4
    conn.close()


def test_existing_database_upgrade_is_additive_and_idempotent(tmp_path):
    db_file = str(tmp_path / "existing.db")
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO schema_migrations(version) VALUES
            ('001_sale_batches.sql'),
            ('002_app_entitlements.sql'),
            ('003_stock_adjustments.sql'),
            ('004_momo_ledger.sql'),
            ('005_momo_provider.sql'),
            ('006_payment_reconciliation.sql');
        CREATE TABLE sales (id INTEGER PRIMARY KEY, total REAL NOT NULL);
        INSERT INTO sales(total) VALUES (1000), (2000);
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
        INSERT INTO users(username) VALUES ('admin');
        """
    )
    conn.commit()
    before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("sales", "users")
    }
    conn.close()

    applied = run(db_file)

    assert applied == [
        "007_billing_subscriptions.sql",
        "008_billing_invoices.sql",
    ]
    assert run(db_file) == []

    conn = sqlite3.connect(db_file)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    after = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("sales", "users")
    }
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    assert {
        "billing_subscriptions",
        "billing_events",
        "billing_invoices",
        "billing_payments",
    } <= tables
    assert "007_billing_subscriptions.sql" in versions
    assert "008_billing_invoices.sql" in versions
    assert after == before
    assert integrity == "ok"


def test_phase2_database_adds_only_invoice_tables(tmp_path):
    db_file = str(tmp_path / "phase2.db")
    conn = sqlite3.connect(db_file)
    conn.execute(
        "CREATE TABLE schema_migrations ("
        " version TEXT PRIMARY KEY,"
        " applied_at TEXT DEFAULT (datetime('now','localtime')))"
    )
    for version in (
        "001_sale_batches.sql",
        "002_app_entitlements.sql",
        "003_stock_adjustments.sql",
        "004_momo_ledger.sql",
        "005_momo_provider.sql",
        "006_payment_reconciliation.sql",
        "007_billing_subscriptions.sql",
    ):
        conn.execute("INSERT INTO schema_migrations(version) VALUES(?)", (version,))
    conn.commit()
    conn.close()

    assert run(db_file) == ["008_billing_invoices.sql"]
    assert run(db_file) == []
