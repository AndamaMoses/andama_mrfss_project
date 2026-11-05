"""Phase 3 payment reconciliation, stale sweeps, and Airtel callbacks."""
import uuid
from datetime import date

import pytest

from drugshop.db import execute, get_db, q_all, q_one

DAY = date.today().isoformat()


def _seed(client):
    assert client.post("/api/seed").status_code == 200
    products = client.get("/api/products").get_json()
    assert products
    return products[0]["id"]


def _clear_sales():
    execute("DELETE FROM sales")


def _add_sale(day, product_id, method, total, receipt_ref):
    execute(
        """INSERT INTO sales(sale_date, product_id, qty, unit_price, total,
                             payment_method, receipt_ref, created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (day, product_id, 1, total, total, method, receipt_ref, day),
    )


def _pending(provider="MTN", amount=5000, key=None):
    from drugshop.payments import ledger

    reference = str(uuid.uuid4())
    ledger.create_pending(
        reference,
        key or f"key-{reference}",
        amount,
        "UGX",
        phone="256700000000" if provider == "MTN" else "700000000",
        provider=provider,
    )
    return reference


def _age(reference, minutes=30):
    execute(
        "UPDATE momo_collections SET updated_at=datetime('now','localtime',?) "
        "WHERE reference=?",
        (f"-{minutes} minutes", reference),
    )


def _airtel_config(app, callback_secret="cb-secret"):  # noqa: S107 - test token
    app.config.update(
        AIRTEL_CLIENT_ID="client-id",
        AIRTEL_CLIENT_SECRET="client-secret",
        AIRTEL_BASE_URL="https://openapiuat.airtel.africa",
        AIRTEL_CURRENCY="UGX",
        AIRTEL_COUNTRY="UG",
        AIRTEL_TIMEOUT=20,
        AIRTEL_VERIFY_SALES=False,
        AIRTEL_CALLBACK_SECRET=callback_secret,
    )


# -- payment summary -------------------------------------------------------
def test_payment_summary_reports_variance_orphans_and_unresolved(
    app_under_test, admin_client
):
    from drugshop.payments import ledger, reconciliation

    pid = _seed(admin_client)
    _clear_sales()
    _add_sale(DAY, pid, "MTN_MOMO", 7000, "R-TEST-1")
    _add_sale(DAY, pid, "AIRTEL_MOMO", 2000, "R-TEST-2")

    consumed = _pending("MTN", 7000, key="consumed")
    ledger.apply_status(
        consumed,
        {"status": "SUCCESSFUL", "amount": "7000", "currency": "UGX"},
        provider="MTN",
    )
    db = get_db()
    try:
        ledger.claim_collection(
            db,
            consumed,
            7000,
            "UGX",
            "R-TEST-1",
            source="API",
            provider="MTN",
        )
        db.commit()
    finally:
        db.close()

    orphan = _pending("AIRTEL", 500, key="orphan")
    ledger.apply_status(
        orphan,
        {"status": "SUCCESSFUL", "amount": "500", "currency": "UGX"},
        provider="AIRTEL",
    )
    _pending("MTN", 300, key="unresolved")

    summary = reconciliation.payment_summary(DAY)

    mtn = summary["providers"]["MTN"]
    assert mtn["expected"] == 7000
    assert mtn["consumed"] == 7000
    assert mtn["variance"] == 0
    assert mtn["orphaned_count"] == 0
    assert mtn["unresolved_count"] == 1
    assert mtn["unresolved_amount"] == 300

    airtel = summary["providers"]["AIRTEL"]
    assert airtel["expected"] == 2000
    assert airtel["consumed"] == 0
    assert airtel["variance"] == -2000
    assert airtel["orphaned_count"] == 1
    assert airtel["orphaned"] == 500

    assert summary["totals"]["orphaned_count"] == 1
    assert summary["totals"]["unresolved_count"] == 1
    assert summary["totals"]["status"] == "ATTENTION"
    assert [row["reference"] for row in summary["unresolved"]] == [
        q_one(
            "SELECT reference FROM momo_collections WHERE status='PENDING'"
        )["reference"]
    ]


def test_payment_summary_is_balanced_when_ledger_matches_sales(
    app_under_test, admin_client
):
    from drugshop.payments import ledger, reconciliation

    pid = _seed(admin_client)
    _clear_sales()
    _add_sale(DAY, pid, "MTN_MOMO", 7000, "R-TEST-BAL")

    consumed = _pending("MTN", 7000, key="balanced")
    ledger.apply_status(
        consumed,
        {"status": "SUCCESSFUL", "amount": "7000", "currency": "UGX"},
        provider="MTN",
    )
    db = get_db()
    try:
        ledger.claim_collection(
            db, consumed, 7000, "UGX", "R-TEST-BAL", source="API", provider="MTN"
        )
        db.commit()
    finally:
        db.close()

    summary = reconciliation.payment_summary(DAY)
    assert summary["providers"]["MTN"]["variance"] == 0
    assert summary["totals"]["variance"] == 0
    assert summary["totals"]["status"] == "BALANCED"


def test_payment_summary_does_not_count_unconfirmed_consumed_as_successful(
    app_under_test, admin_client
):
    """A verification-off claim is consumed but not carrier-confirmed."""
    from drugshop.payments import ledger, reconciliation

    pid = _seed(admin_client)
    _clear_sales()
    _add_sale(DAY, pid, "MTN_MOMO", 5000, "R-TEST-PENDING")
    reference = _pending("MTN", 5000, key="pending-consume")

    db = get_db()
    try:
        ledger.claim_collection(
            db,
            reference,
            5000,
            "UGX",
            "R-TEST-PENDING",
            source="API",
            allow_pending=True,
            provider="MTN",
        )
        db.commit()
    finally:
        db.close()

    summary = reconciliation.payment_summary(DAY)
    mtn = summary["providers"]["MTN"]
    assert mtn["consumed"] == 5000
    assert mtn["successful"] == 0
    assert mtn["variance"] == 0
    assert mtn["orphaned_count"] == 0


def test_payment_summary_flags_consumed_payment_when_sale_is_voided(
    app_under_test, admin_client
):
    """A void leaves the ledger CONSUMED; the money must not vanish."""
    from drugshop.payments import ledger, reconciliation

    pid = _seed(admin_client)
    _clear_sales()
    _add_sale(DAY, pid, "MTN_MOMO", 7000, "R-TEST-VOID")
    reference = _pending("MTN", 7000, key="voided")
    ledger.apply_status(
        reference,
        {"status": "SUCCESSFUL", "amount": "7000", "currency": "UGX"},
        provider="MTN",
    )

    db = get_db()
    try:
        ledger.claim_collection(
            db,
            reference,
            7000,
            "UGX",
            "R-TEST-VOID",
            source="API",
            provider="MTN",
        )
        db.commit()
    finally:
        db.close()

    # Mirrors the sale-void path: the sale row is gone, the ledger is not freed.
    execute("DELETE FROM sales WHERE receipt_ref=?", ("R-TEST-VOID",))

    summary = reconciliation.payment_summary(DAY)
    mtn = summary["providers"]["MTN"]
    assert mtn["expected"] == 0
    assert mtn["consumed"] == 0
    assert mtn["orphaned_count"] == 1
    assert mtn["orphaned"] == 7000
    assert mtn["variance"] == 0
    assert mtn["status"] == "ATTENTION"
    assert [row["reference"] for row in summary["orphaned"]] == [reference]


# -- stale sweep -----------------------------------------------------------
def test_sweep_updates_only_old_unresolved_rows(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.payments import service

    _airtel_config(app_under_test)
    stale = _pending("AIRTEL", 5000, key="stale")
    _age(stale, 30)
    fresh = _pending("AIRTEL", 6000, key="fresh")
    calls = []

    def fake_fetch(reference, provider):
        calls.append((reference, provider))
        return {"status": "SUCCESSFUL", "amount": "5000", "currency": "UGX"}

    monkeypatch.setattr(service, "fetch_status", fake_fetch)

    response = admin_client.post(
        "/api/reconciliation/sweep",
        json={"provider": "AIRTEL", "older_than_minutes": 15},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["checked"] == 1
    assert body["updated"] == 1
    assert calls == [(stale, "AIRTEL")]
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (stale,)
    )["status"] == "SUCCESSFUL"
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (fresh,)
    )["status"] == "PENDING"
    events = q_all(
        "SELECT event FROM momo_events WHERE reference=? ORDER BY id", (stale,)
    )
    assert [row["event"] for row in events] == ["RECONCILE"]

    again = admin_client.post(
        "/api/reconciliation/sweep",
        json={"provider": "AIRTEL", "older_than_minutes": 15},
    ).get_json()
    assert again["checked"] == 0
    assert again["would_check"] == 0


def test_sweep_dry_run_does_not_call_the_carrier(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.payments import service

    reference = _pending("AIRTEL", 5000, key="dry")
    _age(reference, 30)
    called = []

    def fail_if_called(*args):
        called.append(args)
        raise AssertionError("dry run must not call the carrier")

    monkeypatch.setattr(service, "fetch_status", fail_if_called)

    body = admin_client.post(
        "/api/reconciliation/sweep",
        json={"provider": "AIRTEL", "dry_run": True},
    ).get_json()

    assert body["dry_run"] is True
    assert body["would_check"] == 1
    assert body["checked"] == 0
    assert called == []
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (reference,)
    )["status"] == "PENDING"


def test_sweep_skips_unconfigured_provider(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.payments import service

    reference = _pending("AIRTEL", 5000, key="unconfigured")
    _age(reference, 30)
    called = []
    monkeypatch.setattr(service, "fetch_status", lambda *a: called.append(a))

    body = admin_client.post(
        "/api/reconciliation/sweep", json={"provider": "AIRTEL"}
    ).get_json()

    assert body["skipped"] == 1
    assert body["checked"] == 0
    assert called == []
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (reference,)
    )["status"] == "PENDING"


def test_sweep_rejects_unknown_provider(admin_client):
    response = admin_client.post(
        "/api/reconciliation/sweep", json={"provider": "VODAFONE"}
    )
    assert response.status_code == 400
    assert "provider" in response.get_json()["error"].lower()


def test_sweep_prioritizes_configured_provider_over_older_skipped_rows(
    app_under_test, admin_client, monkeypatch
):
    """An unconfigured carrier must not consume the whole ALL-sweep limit."""
    from drugshop.payments import service

    _airtel_config(app_under_test)
    for i in range(3):
        stale_mtn = _pending("MTN", 1000, key=f"starve-mtn-{i}")
        _age(stale_mtn, 90 + i)
    airtel = _pending("AIRTEL", 5000, key="starve-airtel")
    _age(airtel, 20)
    calls = []

    def fake_fetch(reference, provider):
        calls.append((reference, provider))
        return {"status": "SUCCESSFUL", "amount": "5000", "currency": "UGX"}

    monkeypatch.setattr(service, "fetch_status", fake_fetch)

    body = admin_client.post(
        "/api/reconciliation/sweep", json={"limit": 2}
    ).get_json()

    # The newer Airtel row must sort ahead of the older MTN rows because only
    # Airtel is configured. One MTN row fills the remaining slot and is skipped.
    assert body["updated"] == 1
    assert body["skipped"] == 1
    assert calls == [(airtel, "AIRTEL")]
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (airtel,)
    )["status"] == "SUCCESSFUL"


# -- Airtel callback -------------------------------------------------------
def test_airtel_callback_requeries_and_ignores_forged_body(
    app_under_test, monkeypatch
):
    from drugshop.payments import service

    _airtel_config(app_under_test)
    reference = _pending("AIRTEL", 5000, key="callback-forged")
    seen = []

    def fake_fetch(ref, provider):
        seen.append((ref, provider))
        return {"status": "SUCCESSFUL", "amount": "5000", "currency": "UGX"}

    monkeypatch.setattr(service, "fetch_status", fake_fetch)

    response = app_under_test.test_client().post(
        "/api/payments/airtel/callback?token=cb-secret",
        json={
            "transaction": {
                "id": reference,
                "status_code": "TF",
                "message": "forged failure",
            }
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "SUCCESSFUL"
    assert body["gateway_status"] == "SUCCESSFUL"
    assert seen == [(reference, "AIRTEL")]
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (reference,)
    )["status"] == "SUCCESSFUL"
    event = q_one(
        "SELECT detail FROM momo_events WHERE reference=? AND event='CALLBACK'",
        (reference,),
    )
    assert "reported=TF" in event["detail"]
    assert "gateway=SUCCESSFUL" in event["detail"]


def test_airtel_callback_cannot_force_success_from_body(
    app_under_test, monkeypatch
):
    from drugshop.payments import service

    _airtel_config(app_under_test)
    reference = _pending("AIRTEL", 5000, key="callback-failed")
    monkeypatch.setattr(
        service,
        "fetch_status",
        lambda ref, provider: {
            "status": "FAILED",
            "amount": "5000",
            "currency": "UGX",
        },
    )

    response = app_under_test.test_client().post(
        "/api/payments/airtel/callback?token=cb-secret",
        json={"transaction": {"id": reference, "status_code": "TS"}},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "FAILED"
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (reference,)
    )["status"] == "FAILED"


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Callback-Token": "cb-secret"},
        {"Authorization": "Bearer cb-secret"},
    ],
)
def test_airtel_callback_accepts_header_tokens(
    app_under_test, monkeypatch, headers
):
    from drugshop.payments import service

    _airtel_config(app_under_test)
    reference = _pending("AIRTEL", 5000, key=f"header-{uuid.uuid4().hex}")
    monkeypatch.setattr(
        service,
        "fetch_status",
        lambda ref, provider: {
            "status": "SUCCESSFUL",
            "amount": "5000",
            "currency": "UGX",
        },
    )

    response = app_under_test.test_client().post(
        "/api/payments/airtel/callback",
        json={"transaction": {"id": reference}},
        headers=headers,
    )
    assert response.status_code == 200


def test_airtel_callback_rejects_bad_or_disabled_secret(app_under_test):
    reference = _pending("AIRTEL", 5000, key="auth")
    payload = {"transaction": {"id": reference}}

    disabled = app_under_test.test_client().post(
        "/api/payments/airtel/callback", json=payload
    )
    assert disabled.status_code == 404

    _airtel_config(app_under_test)
    wrong = app_under_test.test_client().post(
        "/api/payments/airtel/callback?token=wrong", json=payload
    )
    assert wrong.status_code == 403


def test_airtel_callback_rejects_unknown_or_wrong_provider(
    app_under_test,
):
    _airtel_config(app_under_test)
    client = app_under_test.test_client()

    unknown = client.post(
        "/api/payments/airtel/callback?token=cb-secret",
        json={"transaction": {"id": str(uuid.uuid4())}},
    )
    assert unknown.status_code == 404

    mtn_reference = _pending("MTN", 5000, key="callback-mtn")
    mismatch = client.post(
        "/api/payments/airtel/callback?token=cb-secret",
        json={"transaction": {"id": mtn_reference}},
    )
    assert mismatch.status_code == 409
    assert mismatch.get_json()["provider"] == "MTN"


def test_airtel_callback_keeps_row_pending_when_status_check_fails(
    app_under_test, monkeypatch
):
    from drugshop.payments import service
    from drugshop.payments.errors import PaymentError

    _airtel_config(app_under_test)
    reference = _pending("AIRTEL", 5000, key="callback-error")

    def fail(ref, provider):
        raise PaymentError("Airtel is down", status=502)

    monkeypatch.setattr(service, "fetch_status", fail)

    response = app_under_test.test_client().post(
        "/api/payments/airtel/callback?token=cb-secret",
        json={"transaction": {"id": reference, "status_code": "TS"}},
    )

    assert response.status_code == 502
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (reference,)
    )["status"] == "PENDING"
    event = q_one(
        "SELECT event FROM momo_events WHERE reference=? AND event='CALLBACK_ERROR'",
        (reference,),
    )
    assert event is not None


# -- finance endpoints -----------------------------------------------------
def test_reconciliation_calculate_and_daily_summary_include_payments(admin_client):
    _seed(admin_client)

    calc = admin_client.get("/api/reconciliation/calculate").get_json()
    assert calc["expected_cash"] == 2000
    assert calc["expected_mtn"] == 7000
    assert calc["payments"]["date"] == calc["date"]

    summary = admin_client.get("/api/reconciliation/daily-summary").get_json()
    assert summary["ok"] is True
    assert summary["summary"]["expected_cash"] == 2000
    assert summary["summary"]["expected_mtn"] == 7000
    assert summary["summary"]["expected_airtel"] == 0
    assert summary["summary"]["total_sales_count"] > 0
    assert summary["existing_reconciliation"] is None
    assert summary["payments"]["totals"]["expected"] == 7000

    report = admin_client.get("/api/reconciliation/payments").get_json()
    assert report["live"]["date"] == summary["date"]
    assert report["saved"] == []


def test_close_shift_records_closed_status_and_payment_snapshots(admin_client):
    _seed(admin_client)
    response = admin_client.post(
        "/api/reconciliation/close-shift",
        json={
            "date": DAY,
            "counted_cash": 1900,
            "counted_mtn": 7000,
            "counted_airtel": 0,
            "notes": "evening close",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "CLOSED"
    assert body["variances"] == {"cash": -100.0, "mtn": 0.0, "airtel": 0.0}
    assert body["difference"] == -100.0
    assert body["payments"]["providers"]["MTN"]["expected"] == 7000

    saved = q_one("SELECT * FROM reconciliations WHERE rec_date=?", (DAY,))
    assert saved["status"] == "CLOSED"
    assert saved["notes"] == "evening close"

    snapshots = q_all(
        "SELECT * FROM payment_reconciliations WHERE rec_date=? ORDER BY provider",
        (DAY,),
    )
    assert len(snapshots) == 2
    assert {row["provider"] for row in snapshots} == {"MTN", "AIRTEL"}

    report = admin_client.get(f"/api/reconciliation/payments?date={DAY}").get_json()
    assert len(report["saved"]) == 2


def test_close_shift_rejects_non_numeric_counted_amounts(admin_client):
    for value in ("abc", None, "nan", "inf"):
        response = admin_client.post(
            "/api/reconciliation/close-shift", json={"counted_cash": value}
        )
        assert response.status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/api/reconciliation/calculate?date=2026-11-5",
        "/api/reconciliation/daily-summary?date=2026-02-30",
        "/api/reconciliation/payments?date=not-a-day",
    ],
)
def test_reconciliation_rejects_malformed_dates(admin_client, path):
    response = admin_client.get(path)
    assert response.status_code == 400
    assert "date" in response.get_json()["error"]


@pytest.mark.parametrize(
    "url,payload",
    [
        ("/api/reconciliation/close-shift", {"date": "2026-11-5"}),
        ("/api/reconciliation", {"rec_date": "2026-11-5"}),
    ],
)
def test_reconciliation_writes_reject_malformed_dates(
    admin_client, url, payload
):
    response = admin_client.post(url, json=payload)
    assert response.status_code == 400
    assert "date" in response.get_json()["error"]


@pytest.mark.parametrize(
    "url",
    [
        "/api/reconciliation/sweep",
        "/api/reconciliation/close-shift",
        "/api/reconciliation",
    ],
)
def test_reconciliation_posts_require_a_json_object(admin_client, url):
    response = admin_client.post(url, json=["not", "an", "object"])
    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


# -- CLI -------------------------------------------------------------------
def test_momo_reconcile_cli_dry_run(app_under_test):
    reference = _pending("AIRTEL", 5000, key="cli-dry")
    _age(reference, 30)
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(
        args=["momo", "reconcile", "--provider", "AIRTEL", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert "would_check          1" in result.output
    assert reference in result.output


def test_momo_reconcile_cli_updates_configured_provider(
    app_under_test, monkeypatch
):
    from drugshop.payments import service

    _airtel_config(app_under_test)
    reference = _pending("AIRTEL", 5000, key="cli-update")
    _age(reference, 30)
    monkeypatch.setattr(
        service,
        "fetch_status",
        lambda ref, provider: {
            "status": "SUCCESSFUL",
            "amount": "5000",
            "currency": "UGX",
        },
    )
    runner = app_under_test.test_cli_runner()

    result = runner.invoke(args=["momo", "reconcile", "--provider", "AIRTEL"])

    assert result.exit_code == 0, result.output
    assert "updated              1" in result.output
    assert q_one(
        "SELECT status FROM momo_collections WHERE reference=?", (reference,)
    )["status"] == "SUCCESSFUL"
