import sqlite3

import pytest


def test_migrations_apply_once_and_in_order(tmp_path):
    from drugshop.migrations import run

    mdir = tmp_path / "migrations"
    mdir.mkdir()
    (mdir / "001_create_widgets.sql").write_text(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT);", encoding="utf-8"
    )
    (mdir / "002_add_color.sql").write_text(
        "ALTER TABLE widgets ADD COLUMN color TEXT DEFAULT 'red';", encoding="utf-8"
    )
    (mdir / "010_insert_widget.sql").write_text(
        "INSERT INTO widgets(id, name) VALUES (1, 'bolt');", encoding="utf-8"
    )
    db_file = str(tmp_path / "m.db")

    applied = run(db_file, str(mdir))
    assert applied == [
        "001_create_widgets.sql",
        "002_add_color.sql",
        "010_insert_widget.sql",
    ]
    assert run(db_file, str(mdir)) == []

    conn = sqlite3.connect(db_file)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(widgets)").fetchall()]
    rows = conn.execute("SELECT id, name, color FROM widgets").fetchall()
    conn.close()
    assert "color" in cols
    assert rows == [(1, "bolt", "red")]


def test_failed_migration_rolls_back_and_is_not_recorded(tmp_path):
    from drugshop.migrations import run

    mdir = tmp_path / "migrations"
    mdir.mkdir()
    (mdir / "001_ok.sql").write_text(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY);", encoding="utf-8"
    )
    (mdir / "002_broken.sql").write_text(
        "CREATE TABLE good (id INTEGER);\nTHIS IS NOT SQL;", encoding="utf-8"
    )
    db_file = str(tmp_path / "m.db")

    with pytest.raises(sqlite3.Error):
        run(db_file, str(mdir))

    conn = sqlite3.connect(db_file)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()
    assert "widgets" in tables
    assert "good" not in tables
    assert versions == {"001_ok.sql"}


def test_init_db_creates_fresh_schema_and_records_migrations(tmp_path):
    from drugshop import db as dbm

    db_file = str(tmp_path / "fresh.db")

    class TestPaths:
        DATABASE = db_file
        UPLOAD_DIR = str(tmp_path / "up")

    dbm.init_app(TestPaths)
    assert "001_sale_batches.sql" in dbm.init_db()
    assert dbm.init_db() == []

    conn = sqlite3.connect(db_file)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    scols = {r[1] for r in conn.execute("PRAGMA table_info(sales)").fetchall()}
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(momo_collections)").fetchall()}
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='momo_collections'"
        )
    }
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()

    assert {
        "products", "batches", "sales", "sale_batches", "patients", "settings",
        "users", "login_events", "customers", "credit_payments", "expenses",
        "app_entitlements", "entitlement_events", "stock_adjustments",
        "momo_collections", "momo_events", "payment_reconciliations",
    } <= tables
    assert {"receipt_ref", "customer_name", "created_at", "customer_phone", "momo_ref"} <= scols
    assert "provider" in mcols
    assert "001_sale_batches.sql" in versions
    assert "002_app_entitlements.sql" in versions
    assert "003_stock_adjustments.sql" in versions
    assert "004_momo_ledger.sql" in versions
    assert "005_momo_provider.sql" in versions
    assert "006_payment_reconciliation.sql" in versions
    assert "idx_momo_collections_provider_status" in indexes


def test_init_db_upgrades_legacy_schema(tmp_path):
    from drugshop import db as dbm

    db_file = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            pass_hash TEXT NOT NULL, role TEXT DEFAULT 'attendant',
            created_at TEXT DEFAULT (datetime('now','localtime')));
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sale_date TEXT NOT NULL,
            product_id INTEGER NOT NULL, batch_id INTEGER, qty INTEGER NOT NULL,
            unit_price REAL NOT NULL, total REAL NOT NULL,
            payment_method TEXT NOT NULL, served_by TEXT DEFAULT '');
        INSERT INTO users(username, pass_hash) VALUES ('admin', 'x');
        INSERT INTO sales(sale_date, product_id, qty, unit_price, total, payment_method)
            VALUES ('2026-01-01', 1, 2, 100, 200, 'CASH');
        """
    )
    conn.commit()
    conn.close()

    class TestPaths:
        DATABASE = db_file
        UPLOAD_DIR = str(tmp_path / "up")

    dbm.init_app(TestPaths)
    dbm.init_db()

    conn = sqlite3.connect(db_file)
    scols = {r[1] for r in conn.execute("PRAGMA table_info(sales)").fetchall()}
    ucols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(momo_collections)").fetchall()}
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    sale = conn.execute("SELECT total, receipt_ref FROM sales WHERE id=1").fetchone()
    display_name = conn.execute(
        "SELECT display_name FROM users WHERE username='admin'"
    ).fetchone()[0]
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()

    assert {"receipt_ref", "customer_name", "created_at", "customer_phone", "momo_ref"} <= scols
    assert {"display_name", "phone"} <= ucols
    assert "provider" in mcols
    assert {"products", "batches", "patients", "settings", "expenses", "sale_batches"} <= tables
    assert {
        "app_entitlements",
        "entitlement_events",
        "stock_adjustments",
        "momo_collections",
        "momo_events",
        "payment_reconciliations",
    } <= tables
    assert sale == (200.0, "R-000001")
    assert display_name == "Charles Onzima"
    assert "001_sale_batches.sql" in versions
    assert "002_app_entitlements.sql" in versions
    assert "003_stock_adjustments.sql" in versions
    assert "004_momo_ledger.sql" in versions
    assert "005_momo_provider.sql" in versions
    assert "006_payment_reconciliation.sql" in versions


def test_payment_reconciliation_migration_adds_table_to_existing_db(tmp_path):
    """Migration 006 is self-contained and upgrades a Phase 2 database."""
    from drugshop.migrations import run

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
    ):
        conn.execute("INSERT INTO schema_migrations(version) VALUES(?)", (version,))
    conn.commit()
    conn.close()

    applied = run(db_file)
    assert applied == ["006_payment_reconciliation.sql"]

    conn = sqlite3.connect(db_file)
    tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(payment_reconciliations)").fetchall()
    }
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='payment_reconciliations'"
        )
    }
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()

    assert "payment_reconciliations" in tables
    assert {
        "rec_date",
        "provider",
        "expected_amount",
        "consumed_amount",
        "successful_amount",
        "pending_amount",
        "unknown_amount",
        "orphaned_amount",
        "unresolved_count",
        "orphaned_count",
        "variance",
        "status",
        "snapshot",
    } <= cols
    assert "idx_payment_reconciliations_date" in indexes
    assert "006_payment_reconciliation.sql" in versions


def test_momo_provider_migration_upgrades_phase1_ledger(tmp_path):
    """A Phase 1 ledger table is rebuilt once and existing rows become MTN."""
    from drugshop import db as dbm

    db_file = str(tmp_path / "phase1.db")
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE momo_collections (
            reference TEXT COLLATE NOCASE PRIMARY KEY,
            idempotency_key TEXT COLLATE NOCASE NOT NULL UNIQUE,
            external_id TEXT DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'PENDING',
            source TEXT NOT NULL DEFAULT 'API',
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
        INSERT INTO momo_collections(
            reference, idempotency_key, amount, currency, status, source,
            sale_receipt_ref)
        VALUES ('11111111-1111-4111-8111-111111111111', 'old-key', 5000,
                'UGX', 'CONSUMED', 'API', 'R-000001');
        """
    )
    conn.commit()
    conn.close()

    class TestPaths:
        DATABASE = db_file
        UPLOAD_DIR = str(tmp_path / "up")

    dbm.init_app(TestPaths)
    dbm.init_db()

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM momo_collections").fetchone()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(momo_collections)").fetchall()}
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()

    assert "provider" in cols
    assert row["provider"] == "MTN"
    assert row["status"] == "CONSUMED"
    assert row["sale_receipt_ref"] == "R-000001"
    assert "005_momo_provider.sql" in versions


def test_momo_ledger_migration_backfills_existing_references(tmp_path):
    from drugshop import db as dbm

    db_file = str(tmp_path / "legacy_momo.db")
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            momo_ref TEXT DEFAULT '',
            receipt_ref TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        );
        INSERT INTO sales(sale_date,product_id,qty,unit_price,total,payment_method,momo_ref,receipt_ref)
            VALUES ('2026-01-01',1,1,1000,1000,'MTN_MOMO','abc-123','R-1');
        INSERT INTO sales(sale_date,product_id,qty,unit_price,total,payment_method,momo_ref,receipt_ref)
            VALUES ('2026-01-01',1,2,1000,2000,'MTN_MOMO','ABC-123','R-1');
        """
    )
    conn.commit()
    conn.close()

    class TestPaths:
        DATABASE = db_file
        UPLOAD_DIR = str(tmp_path / "up")

    dbm.init_app(TestPaths)
    dbm.init_db()

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM momo_collections").fetchall()
    conn.close()

    assert len(rows) == 1
    row = rows[0]
    assert row["reference"].upper() == "ABC-123"
    assert row["status"] == "CONSUMED"
    assert row["source"] == "LEGACY"
    assert row["provider"] == "MTN"
    assert row["amount"] == 3000
    assert row["sale_receipt_ref"] == "R-1"
