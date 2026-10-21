"""SQLite data access layer.

The database path and upload directory are configured once via ``init_app()``
from the application factory. Paths are held module-level so services stay
callable without needing a Flask request or app context (single-instance,
desktop-style app; per-request connections, no pooling).
"""
import os
import sqlite3

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_PACKAGE_DIR, "schema.sql")
_MIGRATIONS_DIR = os.path.join(_PACKAGE_DIR, "migrations")

_db_path = None
_upload_dir = None


def _read_config(app, key):
    config = getattr(app, "config", None)
    if config is not None:
        return config[key]
    return getattr(app, key)


def init_app(app):
    """Point the layer at paths from a Flask app or a plain config object."""
    global _db_path, _upload_dir
    _db_path = _read_config(app, "DATABASE")
    _upload_dir = _read_config(app, "UPLOAD_DIR")
    parent = os.path.dirname(_db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    os.makedirs(_upload_dir, exist_ok=True)


def get_db():
    if _db_path is None:
        raise RuntimeError("db.init_app() has not been called")
    db = sqlite3.connect(_db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def upload_dir():
    return _upload_dir


def db_path():
    return _db_path


def q_all(sql, args=()):
    db = get_db()
    try:
        rows = db.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def q_one(sql, args=()):
    db = get_db()
    try:
        r = db.execute(sql, args).fetchone()
        return dict(r) if r else None
    finally:
        db.close()


def execute(sql, args=()):
    db = get_db()
    try:
        cur = db.execute(sql, args)
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def init_db():
    """Create schema (idempotent) and run pending migrations."""
    db = get_db()
    try:
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            db.executescript(f.read())
        db.commit()
    finally:
        db.close()
    _upgrade_legacy_columns()
    from drugshop.migrations import run as run_migrations

    return run_migrations(_db_path, _MIGRATIONS_DIR)


def _upgrade_legacy_columns():
    """Additive column upgrades for DBs created by older versions.

    Kept as PRAGMA probes (SQLite has no ADD COLUMN IF NOT EXISTS) so existing
    databases keep working. Future schema changes should ship as files in
    drugshop/migrations/ instead.
    """
    db = get_db()
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(sales)").fetchall()]
        if "receipt_ref" not in cols:
            db.execute("ALTER TABLE sales ADD COLUMN receipt_ref TEXT DEFAULT ''")
        if "customer_name" not in cols:
            db.execute("ALTER TABLE sales ADD COLUMN customer_name TEXT DEFAULT ''")
        if "created_at" not in cols:
            db.execute("ALTER TABLE sales ADD COLUMN created_at TEXT DEFAULT ''")
        if "customer_phone" not in cols:
            db.execute("ALTER TABLE sales ADD COLUMN customer_phone TEXT DEFAULT ''")
        db.commit()
        db.execute("UPDATE sales SET receipt_ref=('R-' || substr('000000' || id, -6, 6)) "
                   "WHERE receipt_ref IS NULL OR receipt_ref=''")
        db.commit()
        ucols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
        if "display_name" not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
        if "phone" not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
        db.execute("UPDATE users SET display_name='Charles Onzima' "
                   "WHERE username='admin' AND (display_name IS NULL OR display_name='')")
        db.commit()
    finally:
        db.close()
