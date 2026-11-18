"""Phase 5 revenue report tests."""
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from drugshop.billing import report, service
from drugshop.billing.catalog import CURRENCY
from drugshop.db import db_path, execute, get_db


def _activate(**overrides):
    kwargs = {
        "bundle": "pro",
        "customer_name": "Example Pharmacy",
        "contact_name": "Dr. A",
        "contact_phone": "+256700000000",
        "start": "2026-11-05",
        "period_end": "2027-11-05",
        "actor": "Andama",
        "notes": "signed Pro, one year",
    }
    kwargs.update(overrides)
    return service.activate(**kwargs)


def _report(**kwargs):
    db = get_db()
    try:
        return report.build_report(db, **kwargs)
    finally:
        db.close()


def test_report_before_billing_tables_reports_entitlements(app_under_test):
    execute("DROP TABLE billing_payments")
    execute("DROP TABLE billing_invoices")
    execute("DROP TABLE billing_subscriptions")

    data = _report(as_of="2026-11-18")

    assert data["billing_status"] == "uninitialized"
    assert data["plan"]["bundle"] == "pro"
    assert data["mrr"] == 0
    assert data["invoice_count"] == 0
    assert data["excluded"][0]["reason"] == "billing tables not initialized"


def test_pro_report_reconciles_to_invoices_and_payments(app_under_test):
    _activate()
    setup = service.create_setup_invoice()
    service.create_monthly_invoice(
        "2026-11-05", "2026-12-05", issue_date="2026-11-12"
    )
    service.record_payment(setup["invoice_no"], 100_000, "cash")

    data = _report(as_of="2026-11-18")

    assert data["customer_name"] == "Example Pharmacy"
    assert data["currency"] == CURRENCY
    assert data["plan"]["label"] == "Pro"
    assert data["plan"]["status"] == "active"
    assert data["mrr"] == 180_000
    assert data["setup_invoiced"] == 600_000
    assert data["monthly_invoiced"] == 180_000
    assert data["total_invoiced"] == 780_000
    assert data["setup_collected"] == 100_000
    assert data["payments_collected"] == 100_000
    assert data["payments_by_method"] == {"cash": 100_000}
    assert data["outstanding_balance"] == 680_000
    assert data["invoice_count"] == 2
    assert data["invoices_by_status"] == {"partial": 1, "unpaid": 1}
    assert data["invoices_by_kind"] == {"monthly": 1, "setup": 1}
    assert data["renewal_due_count"] == 0
    assert data["plan_mix"] == [
        {"bundle": "pro", "label": "Pro", "installations": 1, "mrr": 180_000}
    ]


def test_grandfathered_legacy_is_not_mrr(app_under_test):
    service.activate(
        bundle="legacy",
        customer_name="Onzima Pharmacy",
        grandfathered=True,
        actor="Andama",
    )

    data = _report(as_of="2026-11-18")

    assert data["billing_status"] == "grandfathered"
    assert data["mrr"] == 0
    assert data["plan"]["label"] == "Legacy (grandfathered)"
    assert data["grandfathered"][0]["reason"] == (
        "legacy grandfathered subscription"
    )
    assert data["excluded"] == []


def test_cancelled_subscription_is_excluded_from_mrr(app_under_test):
    _activate()
    service.set_status("cancelled", actor="Andama", notes="shop closed")

    data = _report(as_of="2026-11-18")

    assert data["mrr"] == 0
    assert data["plan"]["status"] == "cancelled"
    assert data["excluded"][0]["status"] == "cancelled"
    assert data["excluded"][0]["reason"] == "status cancelled"


def test_past_due_subscription_still_counts_in_mrr(app_under_test):
    _activate()
    service.set_status("past_due", actor="Andama", notes="invoice unpaid")

    data = _report(as_of="2026-11-18")

    assert data["mrr"] == 180_000
    assert data["excluded"] == []


def test_void_invoice_is_visible_but_not_owed(app_under_test):
    _activate()
    setup = service.create_setup_invoice()
    service.void_invoice(setup["invoice_no"], actor="Andama", reason="duplicate")

    data = _report(as_of="2026-11-18")

    assert data["invoice_count"] == 1
    assert data["invoices_by_status"] == {"void": 1}
    assert data["invoices_by_kind"] == {"setup": 1}
    assert data["setup_invoiced"] == 0
    assert data["total_invoiced"] == 0
    assert data["outstanding_balance"] == 0


def test_renewal_window_is_inclusive_and_overdue_is_visible(app_under_test):
    _activate(
        start="2026-10-19",
        period_end="2026-11-21",
    )

    due = _report(as_of="2026-11-18", renewal_days=3)
    outside = _report(as_of="2026-11-18", renewal_days=2)

    assert due["renewal_due_count"] == 1
    assert due["renewals_due"][0]["days_until"] == 3
    assert due["renewals_due"][0]["overdue"] is False
    assert outside["renewal_due_count"] == 0


def test_report_renewals_match_the_service_queue(app_under_test):
    _activate(start="2026-10-19", period_end="2026-11-21")

    data = _report(as_of="2026-11-18", renewal_days=3)
    queue = service.renewals(days=3, as_of="2026-11-18")

    assert data["renewals_due"] == queue


def test_report_records_the_as_of_date(app_under_test):
    _activate()

    data = _report(as_of="2026-11-18")

    assert data["as_of"] == "2026-11-18"


def test_aggregate_rejects_mixed_currencies(app_under_test):
    _activate()
    first = _report(as_of="2026-11-18")
    second = {**first, "currency": "USD", "source": "other.db"}

    with pytest.raises(ValueError, match="mixes currencies"):
        report.aggregate([first, second])


def test_report_rejects_bad_inputs(app_under_test):
    with pytest.raises(ValueError, match="whole number"):
        _report(renewal_days=True)
    with pytest.raises(ValueError, match="cannot be negative"):
        _report(renewal_days=-1)
    with pytest.raises(ValueError, match="ISO date"):
        _report(as_of="18/11/2026")


def test_report_cli_json_csv_and_text(app_under_test):
    _activate()
    setup = service.create_setup_invoice()
    service.record_payment(setup["invoice_no"], 100_000, "cash")
    runner = app_under_test.test_cli_runner()

    as_json = runner.invoke(
        args=["revenue", "report", "--format", "json", "--as-of", "2026-11-18"]
    )
    assert as_json.exit_code == 0, as_json.output
    data = json.loads(as_json.output)
    assert data["mrr"] == 180_000
    assert data["outstanding_balance"] == 500_000

    as_csv = runner.invoke(
        args=["revenue", "report", "--format", "csv", "--as-of", "2026-11-18"]
    )
    assert as_csv.exit_code == 0, as_csv.output
    rows = list(csv.reader(io.StringIO(as_csv.output)))
    assert rows[0] == list(report.CSV_COLUMNS)
    assert rows[1][0].endswith(".db")
    assert rows[1][7] == "180000"  # mrr
    assert rows[1][13] == "500000"  # outstanding_balance
    assert rows[1][18] == "2026-11-18"  # as_of

    text = runner.invoke(
        args=["revenue", "report", "--as-of", "2026-11-18"]
    )
    assert text.exit_code == 0, text.output
    assert "Revenue report -" in text.output
    assert "As of:                2026-11-18" in text.output
    assert "MRR:" in text.output
    assert "Excluded from MRR:    none" in text.output


def test_report_cli_never_writes_the_database(app_under_test):
    _activate()
    service.create_setup_invoice()
    path = Path(db_path())
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    runner = app_under_test.test_cli_runner()
    result = runner.invoke(
        args=["revenue", "report", "--format", "json", "--as-of", "2026-11-18"]
    )

    assert result.exit_code == 0, result.output
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_report_cli_returns_clean_errors(app_under_test):
    runner = app_under_test.test_cli_runner()

    bad_as_of = runner.invoke(args=["revenue", "report", "--as-of", "nope"])
    assert bad_as_of.exit_code == 1
    assert "ISO date" in bad_as_of.output

    bad_days = runner.invoke(args=["revenue", "report", "--days", "-1"])
    assert bad_days.exit_code == 1
    assert "cannot be negative" in bad_days.output
