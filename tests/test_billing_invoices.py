"""Phase 3 invoice service and CLI tests."""
import json

import pytest

from drugshop.billing import service
from drugshop.billing.catalog import quote
from drugshop.db import execute, q_one


def _activate(bundle="pro", **overrides):
    kwargs = {
        "bundle": bundle,
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


def _setup_invoice(**overrides):
    kwargs = {
        "due_date": "2026-11-12",
        "issue_date": "2026-11-12",
        "actor": "Andama",
    }
    kwargs.update(overrides)
    return service.create_setup_invoice(**kwargs)


def test_setup_invoice_defaults_to_agreed_setup_fee(app_under_test):
    _activate()

    invoice = _setup_invoice(notes="setup before activation")

    assert invoice["invoice_no"] == "INV-202611-0001"
    assert invoice["kind"] == "setup"
    assert invoice["issue_date"] == "2026-11-12"
    assert invoice["due_date"] == "2026-11-12"
    assert invoice["amount"] == 600_000
    assert invoice["currency"] == "UGX"
    assert invoice["status"] == "unpaid"
    assert invoice["paid"] == 0
    assert invoice["balance"] == 600_000
    assert invoice["payment_count"] == 0
    assert invoice["notes"] == "setup before activation"
    assert invoice["payments"] == []
    assert q_one("SELECT COUNT(*) AS n FROM billing_invoices")["n"] == 1

    event = service.subscription_events(1)[0]
    assert event["action"] == "invoice"
    assert event["actor"] == "Andama"
    assert "invoice=INV-202611-0001" in event["detail"]
    assert "kind=setup" in event["detail"]
    assert "amount=600,000" in event["detail"]


def test_monthly_invoice_defaults_to_agreed_monthly_fee(app_under_test):
    _activate()

    invoice = service.create_monthly_invoice(
        "2026-11-05",
        "2026-12-05",
        issue_date="2026-11-05",
        actor="Andama",
    )

    assert invoice["invoice_no"] == "INV-202611-0001"
    assert invoice["kind"] == "monthly"
    assert invoice["period_start"] == "2026-11-05"
    assert invoice["period_end"] == "2026-12-05"
    assert invoice["due_date"] == "2026-11-05"
    assert invoice["amount"] == 180_000
    assert invoice["status"] == "unpaid"
    assert invoice["balance"] == 180_000


def test_invoice_amounts_reconcile_to_the_price_book_quote(app_under_test):
    expected = quote("pro")
    _activate()

    setup = _setup_invoice()
    monthly = service.create_monthly_invoice(
        "2026-11-05",
        "2026-12-05",
        issue_date="2026-11-12",
    )

    assert expected.setup_total == 600_000
    assert expected.monthly_total == 180_000
    assert setup["amount"] == expected.setup_total
    assert monthly["amount"] == expected.monthly_total
    assert setup["currency"] == expected.currency == "UGX"
    assert setup["amount"] + monthly["amount"] == 780_000


def test_invoices_bill_the_agreed_fee_not_the_list_price(app_under_test):
    _activate(
        setup_fee=500_000,
        override_reason="founder-approved launch discount",
    )

    setup = _setup_invoice()

    assert quote("pro").setup_total == 600_000
    assert setup["amount"] == 500_000
    assert setup["balance"] == 500_000


def test_invoice_numbers_are_unique_and_sequential_per_month(app_under_test):
    _activate()

    first = _setup_invoice(issue_date="2026-11-12")
    second = service.create_monthly_invoice(
        "2026-11-05",
        "2026-12-05",
        issue_date="2026-11-12",
    )
    third = service.create_monthly_invoice(
        "2026-12-05",
        "2027-01-05",
        issue_date="2026-12-12",
    )

    assert first["invoice_no"] == "INV-202611-0001"
    assert second["invoice_no"] == "INV-202611-0002"
    assert third["invoice_no"] == "INV-202612-0001"

    rows = service.invoices()
    assert [row["invoice_no"] for row in rows] == [
        "INV-202612-0001",
        "INV-202611-0002",
        "INV-202611-0001",
    ]


def test_duplicate_monthly_period_is_refused_until_voided(app_under_test):
    _activate()
    first = service.create_monthly_invoice(
        "2026-11-05",
        "2026-12-05",
        issue_date="2026-11-05",
    )

    with pytest.raises(service.BillingError, match="already exists"):
        service.create_monthly_invoice(
            "2026-11-05",
            "2026-12-05",
            issue_date="2026-11-06",
        )

    execute("UPDATE billing_invoices SET status='void' WHERE invoice_no=?", (first["invoice_no"],))
    second = service.create_monthly_invoice(
        "2026-11-05",
        "2026-12-05",
        issue_date="2026-11-07",
    )
    assert second["invoice_no"] == "INV-202611-0002"


def test_second_setup_invoice_is_refused_until_the_first_is_voided(app_under_test):
    _activate()
    first = _setup_invoice()

    with pytest.raises(service.BillingError, match="setup invoice already exists"):
        _setup_invoice(issue_date="2026-11-13")

    assert q_one("SELECT COUNT(*) AS n FROM billing_invoices")["n"] == 1

    service.void_invoice(first["invoice_no"], actor="Andama", reason="duplicate")
    second = _setup_invoice(issue_date="2026-11-13")

    assert second["invoice_no"] == "INV-202611-0002"
    assert second["status"] == "unpaid"
    assert q_one("SELECT COUNT(*) AS n FROM billing_invoices")["n"] == 2


def test_overlapping_monthly_invoice_is_refused(app_under_test):
    _activate()
    first = service.create_monthly_invoice(
        "2026-11-05",
        "2026-12-05",
        issue_date="2026-11-05",
    )

    with pytest.raises(service.BillingError, match="overlaps"):
        service.create_monthly_invoice(
            "2026-11-20",
            "2026-12-20",
            issue_date="2026-11-20",
        )

    adjacent = service.create_monthly_invoice(
        "2026-12-05",
        "2027-01-05",
        issue_date="2026-12-05",
    )

    assert first["invoice_no"] == "INV-202611-0001"
    assert adjacent["invoice_no"] == "INV-202612-0001"


def test_void_invoice_keeps_the_row_and_blocks_payments(app_under_test):
    _activate()
    invoice = _setup_invoice()

    voided = service.void_invoice(
        invoice["invoice_no"].lower(),
        actor="Andama",
        reason="wrong amount",
    )

    assert voided["status"] == "void"
    assert voided["amount"] == 600_000
    assert voided["balance"] == 0
    assert voided["payment_count"] == 0
    assert service.invoices()[0]["balance"] == 0

    event = service.subscription_events(1)[0]
    assert event["action"] == "void"
    assert event["actor"] == "Andama"
    assert f"invoice={invoice['invoice_no']}" in event["detail"]
    assert "reason=wrong amount" in event["detail"]

    with pytest.raises(service.BillingError, match="void and cannot accept payments"):
        service.record_payment(
            invoice["invoice_no"],
            100_000,
            "cash",
            received_by="Andama",
        )
    with pytest.raises(service.BillingError, match="already void"):
        service.void_invoice(invoice["invoice_no"])


def test_invoice_with_recorded_payments_cannot_be_voided(app_under_test):
    _activate()
    invoice = _setup_invoice()
    service.record_payment(
        invoice["invoice_no"],
        100_000,
        "cash",
        received_by="Andama",
    )

    with pytest.raises(service.BillingError, match="100,000 UGX has been recorded"):
        service.void_invoice(invoice["invoice_no"], actor="Andama")

    detail = service.invoice_detail(invoice["invoice_no"])
    assert detail["status"] == "partial"
    assert detail["paid"] == 100_000


def test_invoice_list_shows_paid_and_balance_totals(app_under_test):
    _activate()
    invoice = _setup_invoice()
    service.record_payment(
        invoice["invoice_no"],
        300_000,
        "bank",
        paid_on="2026-11-12",
        received_by="Andama",
    )

    rows = service.invoices()

    assert len(rows) == 1
    row = rows[0]
    assert row["invoice_no"] == invoice["invoice_no"]
    assert row["amount"] == 600_000
    assert row["paid"] == 300_000
    assert row["balance"] == 300_000
    assert row["payment_count"] == 1
    assert row["status"] == "partial"

    detail = service.invoice_detail(invoice["invoice_no"])
    assert detail["payments"][0]["amount"] == 300_000
    assert detail["payments"][0]["method"] == "bank"


def test_zero_fee_subscription_cannot_be_invoiced(app_under_test):
    service.activate(
        "legacy",
        customer_name="Onzima",
        grandfathered=True,
        actor="Andama",
    )

    with pytest.raises(service.BillingError, match="setup fee must be greater than zero"):
        service.create_setup_invoice()
    with pytest.raises(service.BillingError, match="monthly fee must be greater than zero"):
        service.create_monthly_invoice("2026-11-05", "2026-12-05")


def test_invoice_validation_errors(app_under_test):
    with pytest.raises(service.BillingError, match="no subscription recorded"):
        service.create_setup_invoice()

    _activate()

    with pytest.raises(service.BillingError, match="issue-date must be an ISO date"):
        service.create_setup_invoice(issue_date="not-a-date")
    with pytest.raises(service.BillingError, match="due must be an ISO date"):
        service.create_setup_invoice(due_date="not-a-date")
    with pytest.raises(service.BillingError, match="period-start is required"):
        service.create_monthly_invoice(None, "2026-12-05")
    with pytest.raises(service.BillingError, match="period-end is required"):
        service.create_monthly_invoice("2026-11-05", None)
    with pytest.raises(service.BillingError, match="period-end must be after"):
        service.create_monthly_invoice("2026-12-05", "2026-11-05")


def test_invoice_cli_creates_lists_and_emits_json(app_under_test):
    _activate()
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=[
            "revenue",
            "invoice",
            "setup",
            "--issue-date",
            "2026-11-12",
            "--due",
            "2026-11-12",
            "--actor",
            "Andama",
            "--json",
        ]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["invoice_no"] == "INV-202611-0001"
    assert payload["kind"] == "setup"
    assert payload["amount"] == 600_000
    assert payload["balance"] == 600_000

    result = runner.invoke(
        args=[
            "revenue",
            "invoice",
            "monthly",
            "--period-start",
            "2026-11-05",
            "--period-end",
            "2026-12-05",
            "--issue-date",
            "2026-11-12",
        ]
    )
    assert result.exit_code == 0, result.output
    assert "Invoice created." in result.output
    assert "Amount:      180,000 UGX" in result.output

    result = runner.invoke(args=["revenue", "invoice", "list", "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert [row["invoice_no"] for row in rows] == [
        "INV-202611-0002",
        "INV-202611-0001",
    ]

    result = runner.invoke(args=["revenue", "invoice", "list"])
    assert result.exit_code == 0, result.output
    assert "INV-202611-0001" in result.output
    assert "balance 600,000 UGX" in result.output


def test_invoice_cli_errors_are_clean(app_under_test):
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(args=["revenue", "invoice", "setup"])
    assert result.exit_code != 0
    assert "no subscription recorded" in result.output
    assert "Traceback" not in result.output

    _activate()
    result = runner.invoke(
        args=[
            "revenue",
            "invoice",
            "monthly",
            "--period-start",
            "2026-12-05",
            "--period-end",
            "2026-11-05",
        ]
    )
    assert result.exit_code != 0
    assert "period-end must be after" in result.output
    assert "Traceback" not in result.output


def test_invoice_cli_show_prints_the_payment_ledger(app_under_test):
    _activate()
    invoice = _setup_invoice()
    service.record_payment(
        invoice["invoice_no"],
        300_000,
        "bank",
        paid_on="2026-11-12",
        reference="FT-123",
        received_by="Andama",
    )
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=["revenue", "invoice", "show", invoice["invoice_no"].lower()]
    )
    assert result.exit_code == 0, result.output
    assert "Status:      partial" in result.output
    assert "Balance:     300,000 UGX" in result.output
    assert "Payments:" in result.output
    assert "2026-11-12  300,000 UGX  bank  ref FT-123  by Andama" in result.output

    result = runner.invoke(
        args=["revenue", "invoice", "show", invoice["invoice_no"], "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["paid"] == 300_000
    assert payload["payments"][0]["reference"] == "FT-123"


def test_invoice_cli_voids_and_refuses_a_second_void(app_under_test):
    _activate()
    invoice = _setup_invoice()
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=[
            "revenue",
            "invoice",
            "void",
            invoice["invoice_no"],
            "--actor",
            "Andama",
            "--reason",
            "wrong due date",
        ]
    )
    assert result.exit_code == 0, result.output
    assert "Invoice voided." in result.output
    assert "Status:      void" in result.output
    assert "Balance:     0 UGX" in result.output

    result = runner.invoke(
        args=["revenue", "invoice", "void", invoice["invoice_no"]]
    )
    assert result.exit_code != 0
    assert "already void" in result.output
    assert "Traceback" not in result.output
