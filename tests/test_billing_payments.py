"""Phase 3 manual payment tests."""
import json
import threading

import pytest

from drugshop.billing import service
from drugshop.db import execute, q_one


def _activate_and_invoice():
    service.activate(
        "pro",
        customer_name="Example Pharmacy",
        contact_name="Dr. A",
        contact_phone="+256700000000",
        start="2026-11-05",
        period_end="2027-11-05",
        actor="Andama",
    )
    return service.create_setup_invoice(
        due_date="2026-11-12",
        issue_date="2026-11-12",
        actor="Andama",
    )


def test_partial_payment_sets_partial_status(app_under_test):
    invoice = _activate_and_invoice()

    result = service.record_payment(
        invoice["invoice_no"],
        300_000,
        "bank",
        paid_on="2026-11-12",
        reference="FT-123",
        received_by="Andama",
        notes="first instalment",
    )

    assert result["status"] == "partial"
    assert result["paid"] == 300_000
    assert result["balance"] == 300_000
    assert result["payment_count"] == 1
    payment = result["payments"][0]
    assert payment["amount"] == 300_000
    assert payment["currency"] == "UGX"
    assert payment["method"] == "bank"
    assert payment["reference"] == "FT-123"
    assert payment["received_by"] == "Andama"
    assert payment["notes"] == "first instalment"
    assert payment["paid_on"] == "2026-11-12"

    event = service.subscription_events(1)[0]
    assert event["action"] == "payment"
    assert event["actor"] == "Andama"
    assert f"invoice={invoice['invoice_no']}" in event["detail"]
    assert "amount=300,000" in event["detail"]
    assert "method=bank" in event["detail"]


def test_full_payment_sets_paid_status(app_under_test):
    invoice = _activate_and_invoice()

    result = service.record_payment(
        invoice["invoice_no"],
        600_000,
        "cash",
        paid_on="2026-11-12",
        received_by="Andama",
    )

    assert result["status"] == "paid"
    assert result["paid"] == 600_000
    assert result["balance"] == 0
    assert result["payment_count"] == 1

    with pytest.raises(service.BillingError, match="already paid"):
        service.record_payment(
            invoice["invoice_no"],
            1,
            "cash",
            received_by="Andama",
        )


def test_overpayment_is_rejected_with_remaining_balance(app_under_test):
    invoice = _activate_and_invoice()
    service.record_payment(
        invoice["invoice_no"],
        300_000,
        "bank",
        received_by="Andama",
    )

    with pytest.raises(service.BillingError, match="remaining balance is 300,000 UGX"):
        service.record_payment(
            invoice["invoice_no"],
            300_001,
            "bank",
            received_by="Andama",
        )

    detail = service.invoice_detail(invoice["invoice_no"])
    assert detail["paid"] == 300_000
    assert detail["balance"] == 300_000
    assert detail["payment_count"] == 1


def test_void_invoice_rejects_payment(app_under_test):
    invoice = _activate_and_invoice()
    execute(
        "UPDATE billing_invoices SET status='void' WHERE invoice_no=?",
        (invoice["invoice_no"],),
    )

    with pytest.raises(service.BillingError, match="void"):
        service.record_payment(
            invoice["invoice_no"],
            100_000,
            "cash",
            received_by="Andama",
        )

    assert q_one("SELECT COUNT(*) AS n FROM billing_payments")["n"] == 0


def test_draft_invoice_rejects_payment(app_under_test):
    invoice = _activate_and_invoice()
    execute(
        "UPDATE billing_invoices SET status='draft' WHERE invoice_no=?",
        (invoice["invoice_no"],),
    )

    with pytest.raises(service.BillingError, match="draft"):
        service.record_payment(
            invoice["invoice_no"],
            100_000,
            "cash",
            received_by="Andama",
        )


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        (0, "payment amount must be greater than zero"),
        (-1, "payment amount cannot be negative"),
        (100.5, "payment amount must be a whole number"),
    ],
)
def test_payment_amount_must_be_positive_whole_ugx(app_under_test, amount, message):
    invoice = _activate_and_invoice()

    with pytest.raises(service.BillingError, match=message):
        service.record_payment(
            invoice["invoice_no"],
            amount,
            "cash",
            received_by="Andama",
        )


def test_payment_method_and_invoice_are_validated(app_under_test):
    invoice = _activate_and_invoice()

    with pytest.raises(service.BillingError, match="unknown payment method"):
        service.record_payment(
            invoice["invoice_no"],
            100_000,
            "cheque",
            received_by="Andama",
        )

    with pytest.raises(service.BillingError, match="not found"):
        service.record_payment(
            "INV-202611-9999",
            100_000,
            "cash",
            received_by="Andama",
        )


def test_concurrent_payments_cannot_overpay(app_under_test):
    invoice = _activate_and_invoice()
    results = []
    errors = []

    def pay():
        try:
            results.append(
                service.record_payment(
                    invoice["invoice_no"],
                    600_000,
                    "cash",
                    received_by="Andama",
                )
            )
        except service.BillingError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=pay) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert len(results) == 1
    assert len(errors) == 1
    assert "overpayment" in errors[0] or "already paid" in errors[0]

    detail = service.invoice_detail(invoice["invoice_no"])
    assert detail["paid"] == 600_000
    assert detail["balance"] == 0
    assert detail["status"] == "paid"
    assert q_one("SELECT COUNT(*) AS n FROM billing_payments")["n"] == 1


def test_recording_a_payment_makes_no_network_call(app_under_test, monkeypatch):
    invoice = _activate_and_invoice()

    def fail(*args, **kwargs):
        raise AssertionError("payment recording must not call the network")

    monkeypatch.setattr("socket.create_connection", fail)
    monkeypatch.setattr("urllib.request.urlopen", fail)

    result = service.record_payment(
        invoice["invoice_no"],
        600_000,
        "mtn_momo",
        reference="MOMO-1",
        received_by="Andama",
    )

    assert result["status"] == "paid"


def test_payment_cli_records_and_reports_balance(app_under_test):
    invoice = _activate_and_invoice()
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=[
            "revenue",
            "payment",
            "record",
            invoice["invoice_no"],
            "--amount",
            "300000",
            "--method",
            "bank",
            "--paid-on",
            "2026-11-12",
            "--reference",
            "FT-123",
            "--received-by",
            "Andama",
            "--json",
        ]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "partial"
    assert payload["paid"] == 300_000
    assert payload["balance"] == 300_000
    assert payload["payments"][0]["reference"] == "FT-123"

    result = runner.invoke(
        args=[
            "revenue",
            "payment",
            "record",
            invoice["invoice_no"],
            "--amount",
            "300000",
            "--method",
            "cash",
            "--paid-on",
            "2026-11-13",
            "--received-by",
            "Andama",
        ]
    )
    assert result.exit_code == 0, result.output
    assert "Payment recorded." in result.output
    assert "Status:      paid" in result.output
    assert "Balance:     0 UGX" in result.output


def test_payment_cli_errors_are_clean(app_under_test):
    invoice = _activate_and_invoice()
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=[
            "revenue",
            "payment",
            "record",
            invoice["invoice_no"],
            "--amount",
            "600001",
            "--method",
            "cash",
            "--received-by",
            "Andama",
        ]
    )
    assert result.exit_code != 0
    assert "remaining balance is 600,000 UGX" in result.output
    assert "Traceback" not in result.output

    result = runner.invoke(
        args=[
            "revenue",
            "payment",
            "record",
            invoice["invoice_no"],
            "--amount",
            "0",
            "--method",
            "cash",
            "--received-by",
            "Andama",
        ]
    )
    assert result.exit_code != 0
    assert "must be greater than zero" in result.output
    assert "Traceback" not in result.output
