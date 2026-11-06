"""Tests for the Phase 1 `revenue` operator CLI."""
import json

import pytest
from click.testing import CliRunner

from drugshop.billing.cli import revenue_group


def _invoke(*args):
    return CliRunner().invoke(revenue_group, list(args))


def test_pricebook_command():
    result = _invoke("pricebook")

    assert result.exit_code == 0, result.output
    assert "Price book: v1-2026-11-05" in result.output
    assert "Currency:   UGX" in result.output
    assert "Core" in result.output
    assert "400,000" in result.output
    assert "120,000" in result.output
    assert "Growth add-on" in result.output
    assert "requires Pro" in result.output
    assert "Tender Copilot" in result.output
    assert "Monthly fees are never discounted." in result.output


def test_quote_core_text():
    result = _invoke("quote", "core")

    assert result.exit_code == 0, result.output
    assert "Quote:      Core" in result.output
    assert "Price book: v1-2026-11-05" in result.output
    assert "400,000" in result.output
    assert "120,000" in result.output
    assert "Total" in result.output


def test_quote_growth_text():
    result = _invoke("quote", "pro", "--add", "growth")

    assert result.exit_code == 0, result.output
    assert "Quote:      Growth" in result.output
    assert "Pro" in result.output
    assert "Growth add-on" in result.output
    assert "800,000" in result.output
    assert "230,000" in result.output


def test_quote_tender_standalone_text():
    result = _invoke("quote", "tender")

    assert result.exit_code == 0, result.output
    assert "Quote:      Tender Copilot" in result.output
    assert "300,000" in result.output
    assert "150,000" in result.output


def test_quote_pro_plus_tender_text():
    result = _invoke("quote", "pro", "--add", "tender")

    assert result.exit_code == 0, result.output
    assert "Quote:      Pro + Tender Copilot" in result.output
    assert "900,000" in result.output
    assert "330,000" in result.output


def test_quote_discount_text():
    result = _invoke("quote", "pro", "--setup-discount", "100000")

    assert result.exit_code == 0, result.output
    assert "Setup subtotal" in result.output
    assert "Setup discount" in result.output
    assert "500,000" in result.output
    assert "180,000" in result.output


def test_quote_json_is_stable():
    result = _invoke("quote", "pro", "--add", "growth", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert list(payload) == [
        "price_book_version",
        "currency",
        "base",
        "addons",
        "label",
        "lines",
        "setup_subtotal",
        "setup_discount",
        "setup_total",
        "monthly_total",
    ]
    assert payload["price_book_version"] == "v1-2026-11-05"
    assert payload["base"] == "pro"
    assert payload["addons"] == ["growth"]
    assert payload["label"] == "Growth"
    assert payload["setup_total"] == 800_000
    assert payload["monthly_total"] == 230_000
    assert payload["lines"][0]["id"] == "pro"
    assert payload["lines"][1]["id"] == "growth"


def test_quote_json_discount():
    result = _invoke("quote", "pro", "--setup-discount", "100000", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["setup_subtotal"] == 600_000
    assert payload["setup_discount"] == 100_000
    assert payload["setup_total"] == 500_000
    assert payload["monthly_total"] == 180_000


def test_quote_cli_runs_without_database():
    # The group is invoked directly, with no Flask app or database fixture.
    result = CliRunner().invoke(revenue_group, ["quote", "core"])

    assert result.exit_code == 0, result.output
    assert "400,000" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("quote", "legacy"), "Legacy is grandfathered"),
        (("quote", "growth"), "Growth is an add-on"),
        (("quote", "core", "--add", "growth"), "Growth add-on requires Pro"),
        (("quote", "platinum"), "Unknown base offer"),
        (("quote", "pro", "--add", "alerts"), "Unknown add-on"),
        (("quote", "core", "--setup-discount=-1"), "cannot be negative"),
        (("quote", "core", "--setup-discount", "400001"), "exceeds the setup subtotal"),
        (("quote", "tender", "--add", "tender"), "standalone"),
    ],
)
def test_quote_errors_are_clean(args, message):
    result = _invoke(*args)

    assert result.exit_code != 0
    assert message in result.output
    assert "Traceback" not in result.output


def test_revenue_group_is_registered(app_under_test):
    result = app_under_test.test_cli_runner().invoke(args=["revenue", "quote", "core"])

    assert result.exit_code == 0, result.output
    assert "400,000" in result.output
