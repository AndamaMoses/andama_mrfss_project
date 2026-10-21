"""Tests for GET /api/apps, the launcher/plan payload (Phase 2)."""
from drugshop.apps import registry, service

PLAN_KEYS = {"bundle", "label", "status", "expires_at"}
APP_KEYS = {
    "id", "name", "description", "icon", "tabs", "href", "bundle",
    "entitled", "always_on",
}


def _payload(client):
    response = client.get("/api/apps")
    assert response.status_code == 200
    return response.get_json()


def _by_id(payload):
    return {app["id"]: app for app in payload["apps"]}


def test_apps_api_requires_login(client):
    response = client.get("/api/apps")
    assert response.status_code == 401
    assert response.get_json()["error"] == "login required"


def test_apps_api_shape_for_pro(admin_client):
    data = _payload(admin_client)

    assert set(data) == {"plan", "apps", "support"}
    assert set(data["plan"]) == PLAN_KEYS
    assert data["plan"] == {
        "bundle": "pro",
        "label": "Pro",
        "status": "active",
        "expires_at": None,
    }

    assert [app["id"] for app in data["apps"]] == registry.app_ids()
    for app in data["apps"]:
        assert set(app) == APP_KEYS

    apps = _by_id(data)
    for app_id in ("pos", "inventory", "patients", "finance"):
        assert apps[app_id]["entitled"] is True
    for app_id in ("alerts", "tender"):
        assert apps[app_id]["entitled"] is False
    assert apps["dashboard"]["entitled"] is True
    assert apps["dashboard"]["always_on"] is True
    assert apps["tender"]["href"] == "/tender"
    assert apps["patients"]["tabs"] == ["pat"]


def test_apps_api_for_core(admin_client):
    service.set_bundle("core")
    data = _payload(admin_client)
    apps = _by_id(data)

    assert data["plan"]["bundle"] == "core"
    assert data["plan"]["label"] == "Core"
    assert apps["pos"]["entitled"] is True
    assert apps["inventory"]["entitled"] is True
    for app_id in ("patients", "finance", "alerts", "tender"):
        assert apps[app_id]["entitled"] is False
    assert apps["dashboard"]["entitled"] is True


def test_apps_api_for_growth(admin_client):
    service.add_app("alerts")
    data = _payload(admin_client)
    apps = _by_id(data)

    assert data["plan"]["bundle"] == "growth"
    assert data["plan"]["label"] == "Growth"
    assert apps["alerts"]["entitled"] is True
    assert apps["tender"]["entitled"] is False


def test_apps_api_for_tender_standalone(admin_client):
    service.set_bundle("tender")
    data = _payload(admin_client)
    apps = _by_id(data)

    assert data["plan"]["bundle"] == "tender"
    assert apps["tender"]["entitled"] is True
    for app_id in ("pos", "inventory", "patients", "finance", "alerts"):
        assert apps[app_id]["entitled"] is False
    assert apps["dashboard"]["entitled"] is True


def test_apps_api_for_combined_pharmacy_and_tender(admin_client):
    service.add_app("tender")

    data = _payload(admin_client)
    apps = _by_id(data)
    assert data["plan"]["bundle"] == "pro"
    assert apps["tender"]["entitled"] is True
    assert apps["patients"]["entitled"] is True


def test_apps_api_for_legacy_grandfathered_install(admin_client):
    service.set_bundle("legacy")
    data = _payload(admin_client)
    apps = _by_id(data)

    assert data["plan"]["bundle"] == "legacy"
    assert data["plan"]["label"] == "Legacy (grandfathered)"
    for app_id in ("pos", "inventory", "patients", "finance", "alerts", "tender"):
        assert apps[app_id]["entitled"] is True
    assert apps["dashboard"]["entitled"] is True


def test_apps_api_support_and_expiry(app_under_test, admin_client):
    app_under_test.config["SUPPORT_WHATSAPP"] = "+256700000000"
    service.set_bundle("pro", expires_at="2027-10-21")

    data = _payload(admin_client)
    assert data["support"] == {
        "whatsapp": "+256700000000",
        "message": "Upgrade your plan",
    }
    assert data["plan"]["expires_at"] == "2027-10-21"


def test_apps_api_hides_entitlement_internals(admin_client):
    data = _payload(admin_client)

    assert "events" not in data
    assert "notes" not in data
    for app in data["apps"]:
        assert "requires" not in app
        assert "source" not in app
