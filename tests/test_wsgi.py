"""End-to-end check of the production WSGI bootstrap used by Render."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_wsgi_bootstraps_a_demo_database(tmp_path):
    db_file = tmp_path / "deploy.db"
    env = os.environ.copy()
    env.update(
        {
            "SECRET_KEY": "deploy-test-secret",
            "DRUGSHOP_DB": str(db_file),
            "DRUGSHOP_UPLOADS": str(tmp_path / "uploads"),
            "DRUGSHOP_BUNDLE": "core",
            "DEMO_SEED": "1",
            "ADMIN_PASSWORD": "deploy-admin-pass",
            "STAFF_PASSWORD": "deploy-staff-pass",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", "import wsgi; print('ok')"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout

    with sqlite3.connect(db_file) as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 10
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 9
        assert conn.execute(
            "SELECT COUNT(DISTINCT bundle) FROM app_entitlements"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT bundle FROM app_entitlements LIMIT 1"
        ).fetchone()[0] == "core"
