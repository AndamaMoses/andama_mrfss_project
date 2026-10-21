MODULES = (
    "core/api.js", "core/format.js", "core/ui.js",
    "dashboard.js", "pos.js", "stock.js", "patients.js", "finance.js",
    "credit.js", "customers.js", "team.js", "settings.js", "alerts.js",
    "manage.js", "boot.js",
)


def test_all_pages_render(client):
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
