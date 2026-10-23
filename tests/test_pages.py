from drugshop.apps import service

MODULES = (
    "core/api.js", "core/format.js", "core/ui.js",
    "dashboard.js", "pos.js", "stock.js", "patients.js", "finance.js",
    "credit.js", "customers.js", "team.js", "settings.js", "alerts.js",
    "manage.js", "core/apps.js", "boot.js",
)


def test_brand_assets_and_metadata_are_served(client):
    html = client.get("/").get_data(as_text=True)
    assert 'rel="icon"' in html
    assert "/static/img/favicon.svg" in html
    assert "/static/site.webmanifest" in html

    favicon = client.get("/static/img/favicon.svg")
    assert favicon.status_code == 200
    assert favicon.mimetype == "image/svg+xml"

    manifest = client.get("/static/site.webmanifest")
    assert manifest.status_code == 200
    assert b'"short_name": "Onzima Dawa"' in manifest.data


def test_security_headers_are_set(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_all_pages_render(client):
    # Tender is a standalone app; enable it so this stays a render test rather
    # than an entitlement test (the redirect is covered in test_app_gate.py).
    service.add_app("tender")
    for page in ("/", "/login", "/staff", "/tender"):
        r = client.get(page)
        assert r.status_code == 200, page
        assert b"<html" in r.data.lower() or b"<!doctype" in r.data.lower(), page


def test_frontend_modules_are_served(client):
    html = client.get("/").get_data(as_text=True)
    for module in MODULES:
        r = client.get(f"/static/js/{module}")
        assert r.status_code == 200, module
        assert "javascript" in r.mimetype, module
        assert f'src="/static/js/{module}"' in html, module
    assert html.count("<script") == len(MODULES)


def test_launcher_markup_and_hooks_are_present(client):
    html = client.get("/").get_data(as_text=True)
    for marker in (
        'id="tab-apps"',
        'id="appsGrid"',
        'id="upgradeModal"',
        'id="planCard"',
        'data-app="patients"',
        'data-app="tender"',
        'data-section-apps="finance,patients"',
        'data-section-apps="tender"',
        'id="i-apps"',
        'id="i-lock"',
    ):
        assert marker in html, marker

    js = client.get("/static/js/core/apps.js").get_data(as_text=True)
    for hook in (
        "function applyApps",
        "function renderLauncher",
        "function launcherApps",
        "var PHARMACY_APP_IDS",
        "function openUpgrade",
        "function closeUpgrade",
        "function handleUpgradeParam",
        "function canOpenTab",
    ):
        assert hook in js, hook
    assert "app.id !== 'tender'" in js
