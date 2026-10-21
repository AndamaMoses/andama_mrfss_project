"""Versioned SQL migration runner.

Files named ``NNN_description.sql`` in this directory are applied once, in
filename order. Each file runs inside one transaction together with its
``schema_migrations`` row, so a failure rolls the whole file back and nothing
is recorded. Migration files must therefore not contain their own
``BEGIN``/``COMMIT``. ``schema.sql`` holds the full current schema for fresh
databases — new changes should also ship as numbered files here.
"""
import os
import sqlite3


def _statements(script):
    """Split a SQL script into complete statements (handles trigger bodies)."""
    buf = ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            text = buf.strip()
            if text:
                yield text
            buf = ""
    if buf.strip():
        yield buf.strip()


def run(db_path, migrations_dir=None):
    if migrations_dir is None:
        migrations_dir = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(db_path)
    conn.isolation_level = None
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY,"
            " applied_at TEXT DEFAULT (datetime('now','localtime')))"
        )
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        pending = sorted(
            f
            for f in os.listdir(migrations_dir)
            if f.endswith(".sql") and os.path.isfile(os.path.join(migrations_dir, f))
        )
        applied_now = []
        for fname in pending:
            if fname in applied:
                continue
            with open(os.path.join(migrations_dir, fname), encoding="utf-8") as f:
                script = f.read()
            conn.execute("BEGIN")
            try:
                for statement in _statements(script):
                    conn.execute(statement)
                conn.execute("INSERT INTO schema_migrations(version) VALUES(?)", (fname,))
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
            applied_now.append(fname)
        return applied_now
    finally:
        conn.close()
