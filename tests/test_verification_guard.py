"""Phase 5 verification: the suite must stay offline and credential-free."""
import socket
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_test_app_has_no_live_payment_credentials(app_under_test):
    config = app_under_test.config
    assert config["MOMO_SUBSCRIPTION_KEY"] == ""
    assert config["MOMO_API_USER"] == ""
    assert config["MOMO_API_KEY"] == ""
    assert config["MOMO_BASE_URL"] == ""
    assert config["MOMO_CALLBACK_SECRET"] == ""
    assert config["AIRTEL_CLIENT_ID"] == ""
    assert config["AIRTEL_CLIENT_SECRET"] == ""
    assert config["AIRTEL_BASE_URL"] == ""
    assert config["AIRTEL_CALLBACK_SECRET"] == ""
    assert config["MOMO_VERIFY_SALES"] is False
    assert config["AIRTEL_VERIFY_SALES"] is False


def test_outbound_network_is_blocked():
    sock = socket.socket()
    try:
        with pytest.raises(AssertionError, match="outbound network"):
            sock.connect(("203.0.113.1", 80))
    finally:
        sock.close()


def test_tests_cannot_open_the_live_database(tmp_path):
    from types import SimpleNamespace

    from drugshop import db as dbm

    paths = SimpleNamespace(
        DATABASE=str(PROJECT_ROOT / "drugshop.db"),
        UPLOAD_DIR=str(tmp_path / "uploads"),
    )

    with pytest.raises(AssertionError, match="live database"):
        dbm.init_app(paths)
