from drugshop.apps import service

MODULES = (
    "core/api.js", "core/format.js", "core/ui.js",
    "dashboard.js", "momo.js", "pos.js", "stock.js", "patients.js", "finance.js",
    "credit.js", "customers.js", "team.js", "settings.js", "alerts.js",
    "manage.js", "core/apps.js", "boot.js",
)


def test_brand_assets_and_metadata_are_served(admin_client):
    html = admin_client.get("/").get_data(as_text=True)
    assert 'rel="icon"' in html
    assert "/static/img/favicon.svg" in html
    assert "/static/site.webmanifest" in html

    favicon = admin_client.get("/static/img/favicon.svg")
    assert favicon.status_code == 200
    assert favicon.mimetype == "image/svg+xml"

    manifest = admin_client.get("/static/site.webmanifest")
    assert manifest.status_code == 200
    assert b'"short_name": "Onzima Dawa"' in manifest.data


def test_root_sends_anonymous_visitors_to_login(app_under_test, admin_client):
    anon = app_under_test.test_client().get("/")
    assert anon.status_code == 302
    assert "/login" in anon.headers["Location"]
    assert admin_client.get("/").status_code == 200


def test_demo_mode_labels_synthetic_data(app_under_test, admin_client):
    assert "synthetic" not in admin_client.get("/").get_data(as_text=True)

    app_under_test.config["DEMO_MODE"] = True
    html = admin_client.get("/").get_data(as_text=True)
    assert "synthetic" in html


def test_shop_branch_can_be_saved(admin_client):
    assert admin_client.post("/api/settings", json={"shop_branch": "Jinja"}).status_code == 200
    assert admin_client.get("/api/settings").get_json()["shop_branch"] == "Jinja"


def test_security_headers_are_set(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_all_pages_render(admin_client):
    # Tender is a standalone app; enable it so this stays a render test rather
    # than an entitlement test (the redirect is covered in test_app_gate.py).
    service.add_app("tender")
    for page in ("/", "/login", "/staff", "/tender"):
        r = admin_client.get(page)
        assert r.status_code == 200, page
        assert b"<html" in r.data.lower() or b"<!doctype" in r.data.lower(), page


def test_frontend_modules_are_served(admin_client):
    html = admin_client.get("/").get_data(as_text=True)
    for module in MODULES:
        r = admin_client.get(f"/static/js/{module}")
        assert r.status_code == 200, module
        assert "javascript" in r.mimetype, module
        assert f'src="/static/js/{module}"' in html, module
    assert html.count("<script") == len(MODULES)


def test_reconciliation_controls_and_hooks_are_present(admin_client):
    html = admin_client.get("/").get_data(as_text=True)
    for marker in (
        'id="recPendingBtn"',
        'id="recCloseBtn"',
        'id="recAttention"',
        'onclick="closeShift()"',
    ):
        assert marker in html, marker

    js = admin_client.get("/static/js/finance.js").get_data(as_text=True)
    for hook in (
        "function closeShift",
        "function renderRecAttention",
        "/api/reconciliation/close-shift",
    ):
        assert hook in js, hook


def test_pos_checkout_guards_and_escaping_hooks_are_present(admin_client):
    html = admin_client.get("/").get_data(as_text=True)
    for marker in ('id="saleBtn"', 'id="basketBtn"', 'id="momoManualRef"'):
        assert marker in html, marker

    pos = admin_client.get("/static/js/pos.js").get_data(as_text=True)
    for hook in (
        "var SALE_BUSY = false",
        "function setSaleBusy",
        "SALE_BUSY || MOMO.busy",
        "momoManualReferenceError(momoProvider)",
        "function posSafeRef",
        "escHtml(l.product_name)",
        "escHtml(r.momo_ref)",
        "escHtml(r.shop_name)",
    ):
        assert hook in pos, hook

    momo = admin_client.get("/static/js/momo.js").get_data(as_text=True)
    for hook in (
        "function momoPhoneKey",
        "function momoManualReferenceError",
        "momoPhoneKey(MOMO_PENDING.phone) === phoneKey",
    ):
        assert hook in momo, hook

    staff = admin_client.get("/staff").get_data(as_text=True)
    for hook in (
        'id="staffCheckoutBtn"',
        "BASKET=[],BUSY=false",
        "async function checkout()",
        "if(BUSY)return",
        "e.status===409&&receipt",
        "const esc=",
    ):
        assert hook in staff, hook

    shared = admin_client.get("/static/js/core/format.js").get_data(as_text=True)
    assert "function escHtml" in shared
    apps = admin_client.get("/static/js/core/apps.js").get_data(as_text=True)
    assert "function escHtml" not in apps


def test_launcher_markup_and_hooks_are_present(admin_client):
    html = admin_client.get("/").get_data(as_text=True)
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

    js = admin_client.get("/static/js/core/apps.js").get_data(as_text=True)
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
