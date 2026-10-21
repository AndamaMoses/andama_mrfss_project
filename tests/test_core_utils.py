"""Direct unit tests for the Phase 3 core helpers (dates, phones, settings)."""
from datetime import date

import pytest

from drugshop.core.settings import SHOP_DEFAULTS, get_setting
from drugshop.core.utils import (
    normalize_ug_phone,
    parse_date,
    safe_upload_name,
    today_str,
)


def test_today_str_is_iso_date():
    assert today_str() == date.today().isoformat()


def test_parse_date_roundtrip_and_rejects_bad_input():
    assert parse_date("2026-10-19") == date(2026, 10, 19)
    with pytest.raises(ValueError):
        parse_date("19/10/2026")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0774123456", "256774123456"),
        ("+256 774 123456", "256774123456"),
        ("256774123456", "256774123456"),
        ("077-412-3456", "256774123456"),
        ("12345", "12345"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_ug_phone(raw, expected):
    assert normalize_ug_phone(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("invoice.jpg", "invoice.jpg"),
        ("notice copy.pdf", "notice_copy.pdf"),
        ("../../evil.jpg", "evil.jpg"),
        (r"C:\temp\evil.jpg", "evil.jpg"),
        ('x"<img>.jpg', "x__img_.jpg"),
        ("合同.pdf", "__.pdf"),
        ("..", "upload"),
        ("", "upload"),
        (None, "upload"),
    ],
)
def test_safe_upload_name(raw, expected):
    assert safe_upload_name(raw) == expected


def test_get_setting_defaults_and_overrides(tmp_path):
    from drugshop import db as dbm

    class TestPaths:
        DATABASE = str(tmp_path / "settings.db")
        UPLOAD_DIR = str(tmp_path / "up")

    dbm.init_app(TestPaths)
    dbm.init_db()

    assert get_setting("shop_name") == SHOP_DEFAULTS["shop_name"]
    assert get_setting("no_such_key") == ""

    dbm.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("shop_name", "Test Shop"))
    assert get_setting("shop_name") == "Test Shop"

    dbm.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("shop_branch", ""))
    assert get_setting("shop_branch") == SHOP_DEFAULTS["shop_branch"]
