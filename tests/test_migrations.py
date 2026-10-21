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
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()

    assert {
        "products", "batches", "sales", "sale_batches", "patients", "settings",
        "users", "login_events", "customers", "credit_payments", "expenses",
    } <= tables
    assert {"receipt_ref", "customer_name", "created_at", "customer_phone"} <= scols
    assert "001_sale_batches.sql" in versions


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
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    sale = conn.execute("SELECT total, receipt_ref FROM sales WHERE id=1").fetchone()
    display_name = conn.execute(
        "SELECT display_name FROM users WHERE username='admin'"
    ).fetchone()[0]
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    conn.close()

    assert {"receipt_ref", "customer_name", "created_at", "customer_phone"} <= scols
    assert {"display_name", "phone"} <= ucols
    assert {"products", "batches", "patients", "settings", "expenses", "sale_batches"} <= tables
    assert sale == (200.0, "R-000001")
    assert display_name == "Charles Onzima"
    assert "001_sale_batches.sql" in versions
