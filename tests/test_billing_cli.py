"""Tests for the `revenue` operator CLI (Phases 1-2)."""
import json

import pytest
from click.testing import CliRunner

from drugshop.apps import service as apps_service
from drugshop.billing import service as billing_service
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
    assert "Setup discounts are capped at 100,000 UGX." in result.output
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
        (
            ("quote", "core", "--setup-discount", "100001"),
            "exceeds the approved v1 cap",
        ),
        (
            ("quote", "core", "--setup-discount", "400000"),
            "exceeds the approved v1 cap",
        ),
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


def _run(app, *args):
    return app.test_cli_runner().invoke(args=list(args))


def _activate_cli(app, bundle="pro", **extra):
    args = [
        "revenue",
        "activate",
        bundle,
        "--customer",
        "Example Pharmacy",
        "--contact",
        "+256700000000",
        "--contact-name",
        "Dr. A",
        "--start",
        "2026-11-05",
        "--period-end",
        "2027-11-05",
        "--actor",
        "Andama",
        "--notes",
        "signed Pro, one year",
    ]
    for key, value in extra.items():
        args.extend([f"--{key.replace('_', '-')}", str(value)])
    return _run(app, *args)


def test_show_without_subscription(app_under_test):
    result = _run(app_under_test, "revenue", "show")

    assert result.exit_code == 0, result.output
    assert "No subscription recorded." in result.output


def test_activate_cli(app_under_test):
    result = _activate_cli(app_under_test)

    assert result.exit_code == 0, result.output
    assert "Activated: Pro" in result.output
    assert "Customer:    Example Pharmacy" in result.output
    assert "Contact:     Dr. A +256700000000" in result.output
    assert "Status:      active" in result.output
    assert "Setup:       600,000 UGX" in result.output
    assert "Monthly:     180,000 UGX" in result.output
    assert "2027-11-05" in result.output
    assert "Apps:        pos, inventory, patients, finance" in result.output

    subscription = billing_service.current_subscription()
    assert subscription["status"] == "active"
    assert subscription["bundle"] == "pro"
    assert apps_service.current_plan()["bundle"] == "pro"


def test_activate_cli_is_idempotent(app_under_test):
    first = _activate_cli(app_under_test)
    assert first.exit_code == 0, first.output
    events_before = len(billing_service.subscription_events(20))

    second = _activate_cli(app_under_test)

    assert second.exit_code == 0, second.output
    assert "Already active: Pro" in second.output
    assert len(billing_service.subscription_events(20)) == events_before


def test_activate_legacy_requires_grandfathered(app_under_test):
    result = _run(
        app_under_test,
        "revenue",
        "activate",
        "legacy",
        "--customer",
        "Onzima",
    )

    assert result.exit_code != 0
    assert "requires --grandfathered" in result.output


def test_activate_legacy_grandfathered(app_under_test):
    result = _run(
        app_under_test,
        "revenue",
        "activate",
        "legacy",
        "--customer",
        "Onzima",
        "--grandfathered",
        "--actor",
        "Andama",
        "--notes",
        "existing shop",
    )

    assert result.exit_code == 0, result.output
    assert "Status:      grandfathered" in result.output
    assert "Monthly:     0 UGX" in result.output
    subscription = billing_service.current_subscription()
    assert subscription["status"] == "grandfathered"
    assert subscription["monthly_fee"] == 0
    assert apps_service.current_plan()["bundle"] == "legacy"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("revenue", "activate", "platinum", "--customer", "X"),
            "unknown bundle",
        ),
        (
            (
                "revenue",
                "activate",
                "pro",
                "--customer",
                "X",
                "--period-end",
                "2027-11-05",
                "--start",
                "not-a-date",
            ),
            "start must be an ISO date",
        ),
        (
            (
                "revenue",
                "activate",
                "pro",
                "--customer",
                "X",
                "--start",
                "2026-11-05",
            ),
            "--period-end is required",
        ),
        (
            (
                "revenue",
                "activate",
                "pro",
                "--customer",
                "X",
                "--start",
                "2026-11-05",
                "--period-end",
                "2027-11-05",
                "--setup-fee=-1",
            ),
            "setup fee cannot be negative",
        ),
        (
            (
                "revenue",
                "activate",
                "pro",
                "--customer",
                "X",
                "--start",
                "2026-11-05",
                "--period-end",
                "2027-11-05",
                "--monthly-fee=-1",
            ),
            "monthly fee cannot be negative",
        ),
        (
            (
                "revenue",
                "activate",
                "pro",
                "--customer",
                "X",
                "--start",
                "2026-11-05",
                "--period-end",
                "2027-11-05",
                "--setup-fee",
                "500000",
            ),
            "requires --override-reason",
        ),
        (
            (
                "revenue",
                "activate",
                "pro",
                "--customer",
                "X",
                "--start",
                "2026-11-05",
                "--period-end",
                "2027-11-05",
                "--currency",
                "USD",
            ),
            "must use UGX",
        ),
    ],
)
def test_activate_cli_errors(app_under_test, args, message):
    result = _run(app_under_test, *args)

    assert result.exit_code != 0
    assert message in result.output
    assert "Traceback" not in result.output


def test_activate_cli_override_reason_is_logged(app_under_test):
    result = _activate_cli(
        app_under_test,
        setup_fee=500_000,
        override_reason="founder approved setup discount",
    )

    assert result.exit_code == 0, result.output
    assert billing_service.current_subscription()["setup_fee"] == 500_000
    event = billing_service.subscription_events(1)[0]
    assert "founder approved setup discount" in event["detail"]


def test_status_cli(app_under_test):
    assert _activate_cli(app_under_test).exit_code == 0

    result = _run(
        app_under_test,
        "revenue",
        "status",
        "past_due",
        "--actor",
        "Andama",
        "--notes",
        "November invoice unpaid",
    )
    assert result.exit_code == 0, result.output
    assert "Status: past_due" in result.output
    assert billing_service.current_subscription()["status"] == "past_due"
    assert "November invoice unpaid" in billing_service.subscription_events(1)[0]["detail"]

    result = _run(app_under_test, "revenue", "status", "active", "--actor", "Andama")
    assert result.exit_code == 0, result.output
    assert billing_service.current_subscription()["status"] == "active"

    result = _run(app_under_test, "revenue", "status", "cancelled", "--actor", "Andama")
    assert result.exit_code == 0, result.output
    assert billing_service.current_subscription()["status"] == "cancelled"

    result = _run(app_under_test, "revenue", "status", "active")
    assert result.exit_code != 0
    assert "reactivated" in result.output

    result = _run(app_under_test, "revenue", "status", "bogus")
    assert result.exit_code != 0
    assert "unknown status" in result.output


def test_renew_cli(app_under_test):
    assert _activate_cli(app_under_test).exit_code == 0

    result = _run(
        app_under_test,
        "revenue",
        "renew",
        "--period-end",
        "2028-11-05",
        "--actor",
        "Andama",
        "--notes",
        "annual renewal",
    )

    assert result.exit_code == 0, result.output
    assert "Renewed: Pro until 2028-11-05" in result.output
    subscription = billing_service.current_subscription()
    assert subscription["current_period_start"] == "2027-11-05"
    assert subscription["current_period_end"] == "2028-11-05"
    assert subscription["status"] == "active"
    assert apps_service.current_plan()["expires_at"] == "2028-11-05"

    result = _run(
        app_under_test,
        "revenue",
        "renew",
        "--period-end",
        "2028-11-05",
    )
    assert result.exit_code != 0
    assert "must be after 2028-11-05" in result.output


def test_show_cli_displays_reconciliation_and_events(app_under_test):
    assert _activate_cli(app_under_test).exit_code == 0

    result = _run(app_under_test, "revenue", "show")

    assert result.exit_code == 0, result.output
    assert "Entitled:    Pro (expires 2027-11-05) [OK]" in result.output
    assert "Recent events:" in result.output
    assert "activate" in result.output


def test_show_cli_flags_entitlement_drift(app_under_test):
    assert _activate_cli(app_under_test).exit_code == 0
    apps_service.set_bundle("core")

    result = _run(app_under_test, "revenue", "show")

    assert result.exit_code == 0, result.output
    assert "[MISMATCH]" in result.output
    assert "disagree" in result.output
