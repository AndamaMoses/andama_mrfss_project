"""Phase 3 renewal queue tests."""
import json

import pytest

from drugshop.billing import service
from drugshop.db import execute


def _activate(period_end="2026-11-26", status=None):
    service.activate(
        "pro",
        customer_name="Example Pharmacy",
        start="2025-11-26",
        period_end=period_end,
        actor="Andama",
    )
    if status:
        service.set_status(status, actor="Andama")


def test_renewal_window_is_inclusive_and_excludes_later_dates(app_under_test):
    _activate(period_end="2026-11-26")

    due = service.renewals(days=14, as_of="2026-11-12")
    assert len(due) == 1
    assert due[0]["current_period_end"] == "2026-11-26"
    assert due[0]["days_until"] == 14
    assert due[0]["overdue"] is False
    assert due[0]["bundle"] == "pro"
    assert due[0]["monthly_fee"] == 180_000
    assert due[0]["currency"] == "UGX"

    assert service.renewals(days=13, as_of="2026-11-12") == []


def test_renewal_window_excludes_dates_after_the_window(app_under_test):
    _activate(period_end="2026-11-27")

    assert service.renewals(days=14, as_of="2026-11-12") == []


def test_overdue_subscription_is_included(app_under_test):
    _activate(period_end="2026-11-01")

    due = service.renewals(days=14, as_of="2026-11-12")

    assert len(due) == 1
    assert due[0]["days_until"] == -11
    assert due[0]["overdue"] is True


def test_renewals_exclude_non_renewing_statuses(app_under_test):
    _activate(period_end="2026-11-26", status="cancelled")
    assert service.renewals(days=14, as_of="2026-11-12") == []

    execute("UPDATE billing_subscriptions SET status='pending' WHERE id=1")
    assert service.renewals(days=14, as_of="2026-11-12") == []


def test_grandfathered_subscription_has_no_renewal(app_under_test):
    service.activate(
        "legacy",
        customer_name="Onzima",
        grandfathered=True,
        actor="Andama",
    )

    assert service.renewals(days=14, as_of="2026-11-12") == []


def test_no_subscription_returns_empty_queue(app_under_test):
    assert service.renewals(days=14, as_of="2026-11-12") == []


@pytest.mark.parametrize("days", [-1, 1.5, "14", True])
def test_renewal_days_must_be_a_non_negative_whole_number(app_under_test, days):
    with pytest.raises(service.BillingError, match="days"):
        service.renewals(days=days, as_of="2026-11-12")


def test_invalid_period_end_is_reported(app_under_test):
    _activate(period_end="2026-11-26")
    execute("UPDATE billing_subscriptions SET current_period_end='not-a-date' WHERE id=1")

    with pytest.raises(service.BillingError, match="not an ISO date"):
        service.renewals(days=14, as_of="2026-11-12")


def test_renewals_cli_text_and_json(app_under_test):
    _activate(period_end="2026-11-26")
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=["revenue", "renewals", "--days", "14", "--as-of", "2026-11-12"]
    )
    assert result.exit_code == 0, result.output
    assert "Example Pharmacy" in result.output
    assert "Pro" in result.output
    assert "ends 2026-11-26" in result.output
    assert "due in 14 days" in result.output
    assert "180,000 UGX/month" in result.output

    result = runner.invoke(
        args=[
            "revenue",
            "renewals",
            "--days",
            "14",
            "--as-of",
            "2026-11-12",
            "--json",
        ]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["customer_name"] == "Example Pharmacy"
    assert payload[0]["bundle"] == "pro"
    assert payload[0]["current_period_end"] == "2026-11-26"
    assert payload[0]["days_until"] == 14
    assert payload[0]["overdue"] is False


def test_renewals_cli_reports_empty_queue(app_under_test):
    _activate(period_end="2027-11-26")
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=["revenue", "renewals", "--days", "14", "--as-of", "2026-11-12"]
    )

    assert result.exit_code == 0, result.output
    assert "No renewals due in the next 14 days." in result.output
