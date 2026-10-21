"""Shared pytest fixtures.

Characterization tests run against a fresh temp SQLite DB per test. All routes
live in the ``drugshop/`` package and are exercised through the application
factory (the legacy root ``app.py`` was removed in the Phase 5 cut-over). The
``client`` / ``admin_client`` / ``staff_client`` fixture interface stays stable.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def app_under_test(tmp_path):
    from drugshop import create_app
    from drugshop import db as dbm
    from drugshop.apps import service as apps_service
    from drugshop.auth import service as auth_service

    db_file = str(tmp_path / "test.db")
    uploads = tmp_path / "uploads"
    uploads.mkdir()

    class TestPaths:
        DATABASE = db_file
        UPLOAD_DIR = str(uploads)

    app = create_app()
    dbm.init_app(TestPaths)
    dbm.init_db()
    auth_service.ensure_admin()
    apps_service.ensure_entitlements("pro")
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return app


@pytest.fixture()
def client(app_under_test):
    return app_under_test.test_client()


def _login(client, username, password):
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_json()
    return client


@pytest.fixture()
def admin_client(client):
    return _login(client, "admin", "admin123")


@pytest.fixture()
def staff_client(app_under_test):
    # Separate test client: a staff and an admin session must not share cookies.
    return _login(app_under_test.test_client(), "grace", "grace123")
