"""Shared pytest fixtures.

Characterization tests run against a fresh temp SQLite DB per test. All routes
live in the ``drugshop/`` package and are exercised through the application
factory (the legacy root ``app.py`` was removed in the Phase 5 cut-over). The
``client`` / ``admin_client`` / ``staff_client`` fixture interface stays stable.
"""
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """Keep the suite fast without weakening production hashing.

    Bootstrap and user-management tests exercise real hash/verify paths, but
    the default scrypt work factor makes a 200-test suite take minutes. The
    stored hash carries its own method, so verification stays real.
    """
    from drugshop.auth import routes as auth_routes
    from drugshop.auth import service as auth_service

    def fast_hash(value):
        return generate_password_hash(value, method="pbkdf2:sha256:1000")

    monkeypatch.setattr(auth_service, "generate_password_hash", fast_hash)
    monkeypatch.setattr(auth_routes, "generate_password_hash", fast_hash)


@pytest.fixture()
def app_under_test(tmp_path, fast_password_hashing):
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
    # Never inherit live MoMo credentials from the developer's .env: a test
    # that forgets to stub the client must fail offline, not move real money.
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        MOMO_SUBSCRIPTION_KEY="",
        MOMO_API_USER="",
        MOMO_API_KEY="",
        MOMO_BASE_URL="",
        MOMO_TARGET_ENVIRONMENT="sandbox",
        MOMO_CURRENCY="",
        MOMO_CALLBACK_URL="",
        MOMO_CALLBACK_SECRET="",
        MOMO_TIMEOUT=20,
        MOMO_VERIFY_SALES=False,
        AIRTEL_CLIENT_ID="",
        AIRTEL_CLIENT_SECRET="",
        AIRTEL_BASE_URL="",
        AIRTEL_CURRENCY="",
        AIRTEL_COUNTRY="UG",
        AIRTEL_TIMEOUT=20,
        AIRTEL_VERIFY_SALES=False,
        AIRTEL_CALLBACK_URL="",
        AIRTEL_CALLBACK_SECRET="",
    )
    from drugshop.payments import routes as payment_routes
    from drugshop.payments import service as payment_service

    payment_routes._CLIENTS.clear()
    payment_routes._AIRTEL_CLIENTS.clear()
    payment_routes.reset_rate_limits()
    payment_service.reset_clients()
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
