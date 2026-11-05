"""Core vs Pro boundaries that are easy to leak through shared endpoints."""
from drugshop.apps import service


def seed(client):
    assert client.post("/api/seed").status_code == 200


def test_core_dashboard_does_not_compute_pro_data(admin_client):
    seed(admin_client)
    service.set_bundle("core")

    d = admin_client.get("/api/dashboard").get_json()

    # Refill Care and Finance are not in Core: same response shape, no data.
    assert d["refill"] == {"due_count": 0, "due": []}
    assert d["credit_owed_total"] == 0


def test_core_patient_export_is_forbidden(admin_client):
    service.set_bundle("core")

    assert admin_client.get("/api/export/patients").status_code == 403
    assert admin_client.get("/api/export/sales").status_code == 200
    assert admin_client.get("/api/export/stock").status_code == 200


def test_core_rejects_credit_sales(admin_client):
    seed(admin_client)
    service.set_bundle("core")
    prod = admin_client.get("/api/products").get_json()[0]

    single = admin_client.post("/api/sales", json={
        "product_id": prod["id"], "qty": 1, "payment_method": "CREDIT",
        "customer_name": "Should Not Matter",
    })
    cart = admin_client.post("/api/sales/cart", json={
        "items": [{"product_id": prod["id"], "qty": 1}],
        "payment_method": "CREDIT", "customer_name": "Should Not Matter",
    })

    assert single.status_code == 403
    assert single.get_json()["app"] == "finance"
    assert cart.status_code == 403


def test_pro_still_allows_credit_and_patient_export(admin_client):
    seed(admin_client)
    prod = admin_client.get("/api/products").get_json()[0]

    r = admin_client.post("/api/sales", json={
        "product_id": prod["id"], "qty": 1, "payment_method": "CREDIT",
        "customer_name": "Credit Customer",
    })
    assert r.status_code == 201
    assert admin_client.get("/api/export/patients").status_code == 200


def test_staff_page_follows_the_plan(admin_client):
    service.set_bundle("core")
    core_html = admin_client.get("/staff").get_data(as_text=True)

    assert "api('/api/reminders')" not in core_html
    assert "CREDIT (owe)" not in core_html
    assert 'id="refN"' not in core_html

    service.set_bundle("pro")
    pro_html = admin_client.get("/staff").get_data(as_text=True)

    assert "api('/api/reminders')" in pro_html
    assert "CREDIT (owe)" in pro_html
    assert 'id="refN"' in pro_html
