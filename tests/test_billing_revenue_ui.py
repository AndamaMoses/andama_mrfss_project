"""Read-only Revenue tab: price book, report, payments, and renewals."""
import hashlib
from datetime import date, timedelta
from pathlib import Path

from drugshop import db as dbm
from drugshop.billing import service

ENDPOINTS = (
    "/api/subscription/pricebook",
    "/api/subscription/report",
    "/api/subscription/payments",
    "/api/subscription/renewals",
)


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


def _section(html):
    start = html.index('id="tab-revenue"')
    end = html.index("</section>", start)
    return html[start:end]


def test_revenue_endpoints_require_login(client):
    for path in ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json() == {"error": "login required"}


def test_revenue_endpoints_are_admin_only(staff_client):
    for path in ENDPOINTS:
        response = staff_client.get(path)
        assert response.status_code == 403, path
        assert response.get_json() == {"error": "admin only"}


def test_price_book_payload(admin_client):
    response = admin_client.get("/api/subscription/pricebook")
    assert response.status_code == 200
    data = response.get_json()

    assert data["version"] == "v1-2026-11-05"
    assert data["currency"] == "UGX"
    assert data["setup_discount_cap"] == 100_000
    offers = {offer["id"]: offer for offer in data["offers"]}
    assert set(offers) == {"core", "pro", "growth", "tender"}
    assert offers["core"]["setup"] == 400_000
    assert offers["core"]["monthly"] == 120_000
    assert offers["pro"]["monthly"] == 180_000
    assert offers["growth"]["requires"] == [{"id": "pro", "label": "Pro"}]
    assert offers["tender"]["roles"] == ["base", "addon"]


def test_report_payload_matches_the_ledger(admin_client):
    _activate()
    setup = service.create_setup_invoice()
    service.record_payment(setup["invoice_no"], 600_000, "mtn_momo")
    service.create_monthly_invoice("2026-11-05", "2026-12-04")

    response = admin_client.get("/api/subscription/report")
    assert response.status_code == 200
    data = response.get_json()

    assert data["customer_name"] == "Example Pharmacy"
    assert data["mrr"] == 180_000
    assert data["setup_invoiced"] == 600_000
    assert data["monthly_invoiced"] == 180_000
    assert data["total_invoiced"] == 780_000
    assert data["payments_collected"] == 600_000
    assert data["outstanding_balance"] == 180_000
    assert data["invoice_count"] == 2
    assert data["invoices_by_status"] == {"paid": 1, "unpaid": 1}
    assert data["payments_by_method"] == {"mtn_momo": 600_000}
    assert data["as_of"] == date.today().isoformat()
    assert "source" in data and data["source"] is None


def test_report_endpoint_does_not_write_the_database(admin_client):
    _activate()
    path = Path(dbm.db_path())
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    response = admin_client.get("/api/subscription/report")
    assert response.status_code == 200

    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before


def test_payments_endpoint_lists_the_ledger(admin_client):
    _activate()
    setup = service.create_setup_invoice()
    service.record_payment(
        setup["invoice_no"],
        600_000,
        "bank",
        reference="FT-001",
        received_by="Andama",
    )

    response = admin_client.get("/api/subscription/payments")
    assert response.status_code == 200
    rows = response.get_json()
    assert len(rows) == 1
    assert rows[0]["invoice_no"] == setup["invoice_no"]
    assert rows[0]["invoice_kind"] == "setup"
    assert rows[0]["amount"] == 600_000
    assert rows[0]["method"] == "bank"
    assert rows[0]["reference"] == "FT-001"
    assert rows[0]["received_by"] == "Andama"
    assert "notes" not in rows[0]


def test_renewals_endpoint_and_window_validation(admin_client):
    end = (date.today() + timedelta(days=7)).isoformat()
    _activate(period_end=end)

    response = admin_client.get("/api/subscription/renewals?days=14")
    assert response.status_code == 200
    rows = response.get_json()
    assert len(rows) == 1
    assert rows[0]["days_until"] == 7
    assert rows[0]["monthly_fee"] == 180_000
    assert rows[0]["overdue"] is False

    outside = admin_client.get("/api/subscription/renewals?days=3")
    assert outside.status_code == 200
    assert outside.get_json() == []

    for bad in ("?days=-1", "?days=99999"):
        rejected = admin_client.get("/api/subscription/renewals" + bad)
        assert rejected.status_code == 400, bad
        assert "days must be" in rejected.get_json()["error"]

    bad_as_of = admin_client.get("/api/subscription/renewals?as_of=not-a-date")
    assert bad_as_of.status_code == 400


def test_revenue_tab_is_read_only(admin_client):
    html = admin_client.get("/").get_data(as_text=True)
    section = _section(html)

    for marker in (
        'data-tab="revenue"',
        "/static/js/revenue.js",
        'id="revAsOf"',
        'id="revMrr"',
        'id="revBookRows"',
        'id="revInvoiceRows"',
        'id="revPaymentRows"',
        'id="revRenewalRows"',
        "Revenue snapshot",
        "Price book",
        "Renewals",
    ):
        assert marker in html, marker

    for forbidden in ("<form", "<button", 'method="post"', 'method="POST"'):
        assert forbidden not in section, forbidden
