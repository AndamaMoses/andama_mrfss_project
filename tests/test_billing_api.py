"""Phase 4 read-only subscription API tests."""
from datetime import date, timedelta

import pytest

from drugshop.apps import service as apps_service
from drugshop.billing import service
from drugshop.db import execute

PLAN_KEYS = {
    "bundle",
    "label",
    "status",
    "started_on",
    "current_period_end",
    "monthly_fee",
    "currency",
}
INVOICE_KEYS = {
    "invoice_no",
    "kind",
    "issue_date",
    "due_date",
    "period_start",
    "period_end",
    "amount",
    "currency",
    "status",
    "paid",
    "balance",
    "payment_count",
}
PAYMENT_KEYS = {
    "paid_on",
    "amount",
    "currency",
    "method",
    "reference",
    "received_by",
}


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


def test_subscription_endpoints_require_login(client):
    for path in (
        "/api/subscription",
        "/api/subscription/invoices",
        "/api/subscription/invoices/INV-202611-0001",
    ):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json() == {"error": "login required"}


def test_staff_can_read_summary_but_not_invoices(staff_client):
    summary = staff_client.get("/api/subscription")
    assert summary.status_code == 200
    data = summary.get_json()
    assert set(data) == {"plan", "balance", "renewal_due", "support"}
    assert set(data["plan"]) == PLAN_KEYS
    assert data["plan"]["bundle"] == "pro"
    assert data["balance"] == 0

    for path in (
        "/api/subscription/invoices",
        "/api/subscription/invoices/INV-202611-0001",
    ):
        response = staff_client.get(path)
        assert response.status_code == 403, path
        assert response.get_json() == {"error": "admin only"}


def test_summary_matches_the_plan_contract(app_under_test, admin_client):
    app_under_test.config["SUPPORT_WHATSAPP"] = "+256700000000"
    _activate()

    response = admin_client.get("/api/subscription")
    assert response.status_code == 200
    data = response.get_json()

    assert set(data) == {"plan", "balance", "renewal_due", "support"}
    assert data["plan"] == {
        "bundle": "pro",
        "label": "Pro",
        "status": "active",
        "started_on": "2026-11-05",
        "current_period_end": "2027-11-05",
        "monthly_fee": 180_000,
        "currency": "UGX",
    }
    assert data["balance"] == 0
    assert data["renewal_due"] is False
    assert data["support"] == {"whatsapp": "+256700000000"}


def test_summary_and_invoices_hide_internal_commercial_fields(
    app_under_test, admin_client
):
    _activate()
    setup = service.create_setup_invoice(notes="internal setup commentary")
    service.record_payment(
        setup["invoice_no"],
        100_000,
        "cash",
        reference="RC-1",
        received_by="Andama",
        notes="internal payment commentary",
    )

    summary_text = admin_client.get("/api/subscription").get_data(as_text=True)
    for hidden in (
        "setup_fee",
        "price_book_version",
        "contact_phone",
        "customer_name",
        "internal setup commentary",
    ):
        assert hidden not in summary_text, hidden

    rows = admin_client.get("/api/subscription/invoices").get_json()
    assert len(rows) == 1
    assert set(rows[0]) == INVOICE_KEYS
    assert "id" not in rows[0]
    assert "notes" not in rows[0]
    assert "created_at" not in rows[0]

    detail_text = admin_client.get(
        f"/api/subscription/invoices/{setup['invoice_no']}"
    ).get_data(as_text=True)
    assert "internal setup commentary" not in detail_text
    assert "internal payment commentary" not in detail_text
    assert '"notes"' not in detail_text
    assert '"id"' not in detail_text


def test_legacy_install_without_a_billing_row_is_grandfathered(admin_client):
    apps_service.set_bundle("legacy")

    data = admin_client.get("/api/subscription").get_json()

    assert data["plan"] == {
        "bundle": "legacy",
        "label": "Legacy (grandfathered)",
        "status": "grandfathered",
        "started_on": None,
        "current_period_end": None,
        "monthly_fee": 0,
        "currency": "UGX",
    }
    assert data["balance"] == 0
    assert data["renewal_due"] is False


def test_summary_reports_balance_and_renewal_due(admin_client):
    today = date.today()
    _activate(
        start=(today - timedelta(days=30)).isoformat(),
        period_end=(today + timedelta(days=5)).isoformat(),
    )
    setup = service.create_setup_invoice()
    monthly = service.create_monthly_invoice(
        (today - timedelta(days=30)).isoformat(),
        (today + timedelta(days=5)).isoformat(),
    )
    service.record_payment(setup["invoice_no"], 100_000, "cash")

    data = admin_client.get("/api/subscription").get_json()

    assert monthly["amount"] == 180_000
    assert data["renewal_due"] is True
    assert data["balance"] == 680_000  # 500,000 setup + 180,000 monthly


def test_void_invoices_carry_no_balance(admin_client):
    _activate()
    setup = service.create_setup_invoice()
    service.void_invoice(setup["invoice_no"], actor="Andama", reason="raised twice")

    assert admin_client.get("/api/subscription").get_json()["balance"] == 0
    rows = admin_client.get("/api/subscription/invoices").get_json()
    assert rows[0]["status"] == "void"
    assert rows[0]["balance"] == 0


def test_admin_invoice_list_and_detail_are_read_only_and_scoped(admin_client):
    _activate()
    setup = service.create_setup_invoice()
    monthly = service.create_monthly_invoice(
        "2026-11-05", "2026-12-05", issue_date="2026-11-12"
    )
    service.record_payment(
        setup["invoice_no"],
        100_000,
        "cash",
        reference="RC-1",
        received_by="Andama",
    )

    rows = admin_client.get("/api/subscription/invoices").get_json()
    assert [row["invoice_no"] for row in rows] == [
        monthly["invoice_no"],
        setup["invoice_no"],
    ]
    assert all(set(row) == INVOICE_KEYS for row in rows)
    assert rows[1]["paid"] == 100_000
    assert rows[1]["balance"] == 500_000
    assert rows[1]["status"] == "partial"

    detail = admin_client.get(
        f"/api/subscription/invoices/{setup['invoice_no'].lower()}"
    )
    assert detail.status_code == 200
    data = detail.get_json()
    assert set(data) == INVOICE_KEYS | {"payments"}
    assert data["invoice_no"] == setup["invoice_no"]
    assert data["payments"] and set(data["payments"][0]) == PAYMENT_KEYS
    assert data["payments"][0]["reference"] == "RC-1"


def test_unknown_invoice_returns_404(admin_client):
    _activate()

    response = admin_client.get("/api/subscription/invoices/INV-209901-0001")

    assert response.status_code == 404
    assert response.get_json() == {"error": "invoice not found"}


def test_admin_invoice_list_is_empty_before_any_invoice(admin_client):
    assert admin_client.get("/api/subscription/invoices").get_json() == []


@pytest.mark.parametrize("bundle", ["core", "pro", "growth", "tender", "legacy"])
def test_summary_is_available_on_every_plan(admin_client, bundle):
    apps_service.set_bundle(bundle)

    response = admin_client.get("/api/subscription")

    assert response.status_code == 200
    assert response.get_json()["plan"]["bundle"] == bundle


def test_reads_fail_open_before_the_billing_migration(admin_client):
    execute("DROP TABLE billing_payments")
    execute("DROP TABLE billing_invoices")
    execute("DROP TABLE billing_subscriptions")

    summary = admin_client.get("/api/subscription")
    assert summary.status_code == 200
    data = summary.get_json()
    assert data["plan"]["bundle"] == "pro"
    assert data["balance"] == 0
    assert data["renewal_due"] is False

    assert admin_client.get("/api/subscription/invoices").get_json() == []
    missing = admin_client.get("/api/subscription/invoices/INV-202611-0001")
    assert missing.status_code == 404
