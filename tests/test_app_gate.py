"""Integration tests for the server-side entitlement gate (Phase 2)."""
import logging

from drugshop.apps import service
from drugshop.apps.guards import UNMAPPED
from drugshop.db import execute


def test_every_non_static_endpoint_is_mapped_or_always_on(app_under_test):
    mapping = app_under_test.extensions["endpoint_apps"]
    endpoints = {rule.endpoint for rule in app_under_test.url_map.iter_rules()}
    endpoints.discard("static")

    assert endpoints <= set(mapping)
    unmapped = sorted(ep for ep in mapping if mapping[ep] == UNMAPPED)
    assert unmapped == []


def test_gate_map_uses_blueprints_and_endpoint_overrides(app_under_test):
    mapping = app_under_test.extensions["endpoint_apps"]

    assert mapping["sales.api_sales"] == "pos"
    assert mapping["inventory.api_products"] == "inventory"
    assert mapping["patients.api_patients"] == "patients"
    assert mapping["credit.api_credit"] == "finance"
    assert mapping["finance.api_expenses"] == "finance"
    assert mapping["notifications.api_low_stock"] == "alerts"
    assert mapping["tender.api_tender_analyze"] == "tender"
    assert mapping["reporting.api_staff_activity"] == "finance"
    assert mapping["reporting.api_dashboard"] is None
    assert mapping["apps.api_apps"] is None


def test_core_keeps_core_and_always_on_routes(app_under_test, admin_client):
    service.set_bundle("core")

    assert admin_client.get("/api/products").status_code == 200
    assert admin_client.get("/api/sales").status_code == 200
    assert admin_client.get("/api/dashboard").status_code == 200
    assert admin_client.get("/api/customers").status_code == 200


def test_core_blocks_pro_endpoints_even_for_admin(app_under_test, admin_client):
    service.set_bundle("core")

    response = admin_client.get("/api/patients")
    assert response.status_code == 403
    assert response.get_json() == {
        "error": "app not entitled",
        "app": "patients",
        "message": "Refill Care is not included in your plan.",
        "upgrade": {"bundle": "pro"},
    }

    assert admin_client.get("/api/expenses").status_code == 403
    assert admin_client.get("/api/credit").status_code == 403


def test_core_blocks_finance_override_endpoint(app_under_test, admin_client):
    service.set_bundle("core")

    response = admin_client.get("/api/staff-activity")
    assert response.status_code == 403
    assert response.get_json()["app"] == "finance"


def test_core_blocks_alerts_and_tender(app_under_test, admin_client):
    service.set_bundle("core")

    alerts = admin_client.get("/api/alerts/low-stock")
    assert alerts.status_code == 403
    assert alerts.get_json()["upgrade"] == {"bundle": "growth"}

    tender = admin_client.post("/api/tender/analyze", json={"text": "x"})
    assert tender.status_code == 403
    assert tender.get_json()["upgrade"] == {"bundle": "tender"}


def test_pro_reaches_pro_routes(app_under_test, admin_client):
    assert admin_client.get("/api/patients").status_code == 200
    assert admin_client.get("/api/expenses").status_code == 200
    assert admin_client.get("/api/staff-activity").status_code == 200


def test_anonymous_api_gets_401_before_entitlement_check(app_under_test, client):
    service.set_bundle("core")

    response = client.get("/api/patients")
    assert response.status_code == 401
    assert response.get_json()["error"] == "login required"


def test_empty_entitlement_table_fails_open(app_under_test, admin_client, client):
    execute("DELETE FROM app_entitlements")

    assert admin_client.get("/api/patients").status_code == 200
    assert admin_client.get("/api/alerts/low-stock").status_code == 200
    assert client.get("/tender").status_code == 200


def test_unentitled_tender_page_redirects_to_upgrade(app_under_test, client):
    response = client.get("/tender")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/?upgrade=tender")


def test_tender_page_renders_when_entitled(app_under_test, client):
    service.add_app("tender")

    response = client.get("/tender")
    assert response.status_code == 200
    assert b"<html" in response.data.lower() or b"<!doctype" in response.data.lower()


def test_denial_is_logged_at_info(app_under_test, admin_client, caplog):
    service.set_bundle("core")

    with caplog.at_level(logging.INFO, logger="drugshop"):
        assert admin_client.get("/api/patients").status_code == 403

    assert any("app access denied" in r.getMessage() for r in caplog.records)
