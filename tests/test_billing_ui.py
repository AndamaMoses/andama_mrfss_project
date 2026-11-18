"""Phase 4 read-only Plan & Apps card tests."""


def _plan_card(html):
    start = html.index('id="planCard"')
    end = html.index('<div class="panel" data-app="inventory">', start)
    return html[start:end]


def test_plan_card_shows_the_read_only_summary(admin_client):
    card = _plan_card(admin_client.get("/").get_data(as_text=True))

    for marker in (
        'id="planName"',
        'id="planStatus"',
        'id="planExpiry"',
        'id="planStarted"',
        'id="planMonthly"',
        'id="planBalance"',
        'id="planApps"',
        'id="planInvoices"',
        'id="planInvoiceRows"',
        'id="planSupport"',
        "Renews",
        "Started",
        "Monthly fee",
        "Outstanding balance",
        "Invoices",
        "This panel is read-only.",
    ):
        assert marker in card, marker


def test_plan_card_has_no_write_controls(admin_client):
    card = _plan_card(admin_client.get("/").get_data(as_text=True))

    for forbidden in (
        "<form",
        "<input",
        "<button",
        'method="post"',
        "onclick=",
        "Pay now",
        "Upgrade now",
        "Change plan",
    ):
        assert forbidden not in card, forbidden


def test_apps_js_loads_and_renders_the_subscription_summary(admin_client):
    js = admin_client.get("/static/js/core/apps.js").get_data(as_text=True)

    for hook in (
        "var SUBSCRIPTION_DATA",
        "var PLAN_STATUS_LABELS",
        "function planStatusLabel",
        "function planStatusClass",
        "function planMoney",
        "function loadSubscription",
        "function renderSubscription",
        "api('/api/subscription')",
        "loadSubscription();",
        "past_due: 'Past due'",
        "expired: 'Expired'",
        "grandfathered: 'Grandfathered'",
        "active: 'Active'",
        "status === 'active' || status === 'grandfathered'",
        "plan.current_period_end",
        "plan.monthly_fee",
        "data.balance",
        "data.renewal_due",
    ):
        assert hook in js, hook

    for write in (
        "api('/api/subscription', 'POST'",
        "api('/api/subscription', 'PUT'",
    ):
        assert write not in js, write


def test_manage_js_renders_escaped_read_only_invoice_rows(admin_client):
    js = admin_client.get("/static/js/manage.js").get_data(as_text=True)

    for hook in (
        "function loadPlanInvoices",
        "function renderPlanInvoices",
        "api('/api/subscription/invoices')",
        "INVOICE_STATUS_LABELS",
        "No invoices recorded.",
        "escHtml(row.invoice_no)",
        "escHtml(prettyDate(row.due_date)",
        "escHtml(planMoney(row.amount",
        "escHtml(planMoney(row.paid",
        "escHtml(planMoney(row.balance",
        "escHtml(status)",
    ):
        assert hook in js, hook

    start = js.index("function renderPlanInvoices")
    end = js.index("/* Owner manage-data tab. */", start)
    renderer = js[start:end]
    assert "api('/api/subscription/invoices', 'POST'" not in renderer
    assert "<form" not in renderer
    assert "<button" not in renderer
    assert "onclick=" not in renderer


def test_plan_support_link_uses_the_configured_whatsapp(admin_client):
    js = admin_client.get("/static/js/core/apps.js").get_data(as_text=True)

    for hook in (
        "function supportWhatsApp",
        "https://wa.me/",
        "supportLink.href = href || '#'",
        "supportLink.hidden = !href",
    ):
        assert hook in js, hook


def test_invoice_status_labels_cover_the_ledger_states(admin_client):
    js = admin_client.get("/static/js/core/apps.js").get_data(as_text=True)

    for status, label in (
        ("unpaid", "Unpaid"),
        ("partial", "Part paid"),
        ("paid", "Paid"),
        ("void", "Void"),
    ):
        assert f"{status}: '{label}'" in js, status


def test_invoice_table_styles_are_present(admin_client):
    css = admin_client.get("/static/css/app.css").get_data(as_text=True)

    for selector in (
        ".plan-invoices",
        ".plan-invoice-wrap",
        ".plan-invoice-table",
        ".plan-empty",
    ):
        assert selector in css, selector
