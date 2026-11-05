"""MTN MoMo client and endpoints: no test touches the real MTN API."""

import json
import os

import pytest

import config
from drugshop.payments import momo


class FakeTransport:
    """Queue of ``(status, payload)`` responses; records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": json.loads(body) if body else None,
                "timeout": timeout,
            }
        )
        status, payload = self.responses.pop(0)
        return status, {}, "" if payload is None else json.dumps(payload)


def _settings(**overrides):
    values = {
        "MOMO_SUBSCRIPTION_KEY": "sub-key",
        "MOMO_API_USER": "api-user",
        "MOMO_API_KEY": "api-key",
        "MOMO_TARGET_ENVIRONMENT": "sandbox",
    }
    values.update(overrides)
    return momo.MomoSettings.from_mapping(values)


# -- configuration ---------------------------------------------------------
def test_settings_defaults_to_sandbox_host():
    settings = _settings()
    assert settings.resolved_base_url == momo.SANDBOX_BASE_URL
    assert settings.configured is True
    # MTN's sandbox accepts EUR only.
    assert settings.currency == "EUR"


def test_currency_defaults_follow_the_environment():
    assert _settings(MOMO_TARGET_ENVIRONMENT="mtnuganda").currency == "UGX"
    assert _settings(MOMO_CURRENCY="ugx").currency == "UGX"
    assert _settings(MOMO_CURRENCY="GHS").currency == "GHS"


@pytest.mark.parametrize("bad", ["", "not-a-number", "0", "-5", "nan", "inf"])
def test_settings_fall_back_to_default_timeout(bad):
    # A hand-edited .env must not stop the app or the CLI from starting.
    assert _settings(MOMO_TIMEOUT=bad).timeout == momo.DEFAULT_TIMEOUT


def test_settings_production_and_override():
    assert (
        _settings(MOMO_TARGET_ENVIRONMENT="mtnuganda").resolved_base_url
        == momo.PRODUCTION_BASE_URL
    )
    assert (
        _settings(MOMO_BASE_URL="https://example.test/").resolved_base_url
        == "https://example.test"
    )
    assert _settings(MOMO_API_KEY="").configured is False


def test_status_payload_hides_secrets():
    payload = _settings().status_payload
    assert payload["configured"] is True
    assert "api-key" not in json.dumps(payload)
    assert "sub-key" not in json.dumps(payload)


def test_dotenv_loads_without_overriding_real_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "export MOMO_TEST_A=from-file\n"
        "MOMO_TEST_B='quoted value'\n"
        "# comment\n"
        "MOMO_TEST_C=a=b\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MOMO_TEST_A", raising=False)
    monkeypatch.setenv("MOMO_TEST_B", "from-env")
    monkeypatch.delenv("MOMO_TEST_C", raising=False)

    config._load_dotenv(str(env_file))

    assert os.environ["MOMO_TEST_A"] == "from-file"
    assert os.environ["MOMO_TEST_B"] == "from-env"
    assert os.environ["MOMO_TEST_C"] == "a=b"


# -- helpers ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0772123456", "256772123456"),
        ("+256 772 123 456", "256772123456"),
        ("256772123456", "256772123456"),
        ("772123456", "256772123456"),
        ("00256772123456", "256772123456"),
    ],
)
def test_normalize_msisdn(raw, expected):
    assert momo.normalize_msisdn(raw) == expected


def test_normalize_msisdn_requires_digits():
    with pytest.raises(ValueError):
        momo.normalize_msisdn("")


@pytest.mark.parametrize(
    "raw", ["12345", "077212345", "25677212345", "255772123456"]
)
def test_normalize_msisdn_rejects_invalid_numbers(raw):
    with pytest.raises(ValueError, match="Ugandan MSISDN"):
        momo.normalize_msisdn(raw)


def test_normalize_msisdn_repairs_country_code_with_leading_zero():
    assert momo.normalize_msisdn("2560772123456") == "256772123456"


def test_amount_formatting_respects_zero_decimal_currencies():
    assert momo._format_amount(5000, "UGX") == "5000"
    assert momo._format_amount(5000.5, "EUR") == "5000.5"
    with pytest.raises(ValueError, match="whole numbers"):
        momo._format_amount(5000.5, "UGX")


# -- client ----------------------------------------------------------------
def test_access_token_is_cached():
    transport = FakeTransport([(200, {"access_token": "tok", "expires_in": 3600})])
    client = momo.MomoClient(_settings(), transport=transport)

    assert client.access_token() == "tok"
    assert client.access_token() == "tok"
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == momo.SANDBOX_BASE_URL + "/collection/token/"
    assert call["headers"]["Ocp-Apim-Subscription-Key"] == "sub-key"
    assert call["headers"]["Authorization"].startswith("Basic ")


def test_request_to_pay_builds_mtn_payload():
    transport = FakeTransport(
        [
            (200, {"access_token": "tok"}),
            (202, None),
        ]
    )
    client = momo.MomoClient(_settings(), transport=transport)

    result = client.request_to_pay(
        5000, "0772 123 456", "SALE-12", payer_message="Dawa", payee_note="Counter"
    )

    assert result["reference_id"]
    call = transport.calls[1]
    assert call["url"].endswith("/collection/v1_0/requesttopay")
    assert call["headers"]["Authorization"] == "Bearer tok"
    assert call["headers"]["X-Target-Environment"] == "sandbox"
    assert call["headers"]["X-Reference-Id"] == result["reference_id"]
    assert call["body"] == {
        "amount": "5000",
        "currency": "EUR",
        "externalId": "SALE-12",
        "payer": {"partyIdType": "MSISDN", "partyId": "256772123456"},
        "payerMessage": "Dawa",
        "payeeNote": "Counter",
    }


def test_request_to_pay_coerces_optional_messages():
    transport = FakeTransport([(200, {"access_token": "tok"}), (202, None)])
    client = momo.MomoClient(_settings(), transport=transport)

    client.request_to_pay(5000, "0772123456", "SALE-16", payer_message=None)

    assert transport.calls[1]["body"]["payerMessage"] == ""
    assert transport.calls[1]["body"]["payeeNote"] == ""


def test_request_to_pay_refreshes_token_once_on_401():
    transport = FakeTransport(
        [
            (200, {"access_token": "tok-1"}),
            (401, {"message": "token expired"}),
            (200, {"access_token": "tok-2"}),
            (202, None),
        ]
    )
    client = momo.MomoClient(_settings(), transport=transport)

    result = client.request_to_pay(5000, "0772123456", "SALE-17")

    assert result["reference_id"]
    assert transport.calls[0]["url"].endswith("/collection/token/")
    assert transport.calls[1]["url"].endswith("/collection/v1_0/requesttopay")
    assert transport.calls[2]["url"].endswith("/collection/token/")
    assert transport.calls[3]["url"].endswith("/collection/v1_0/requesttopay")


def test_request_status_rejects_invalid_reference_id():
    client = momo.MomoClient(_settings(), transport=FakeTransport([]))
    with pytest.raises(ValueError, match="UUID"):
        client.request_status("not-a-uuid")


def test_invalid_base_url_is_wrapped_as_momo_error():
    client = momo.MomoClient(_settings(MOMO_BASE_URL="not-a-url"))
    with pytest.raises(momo.MomoError, match="invalid MTN MoMo URL"):
        client.access_token()


def test_request_to_pay_fills_missing_external_id():
    transport = FakeTransport(
        [
            (200, {"access_token": "tok"}),
            (202, None),
        ]
    )
    client = momo.MomoClient(_settings(), transport=transport)

    result = client.request_to_pay(5000, "0772123456", "")

    assert transport.calls[1]["body"]["externalId"] == result["reference_id"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_request_to_pay_rejects_non_finite_amounts(bad):
    client = momo.MomoClient(_settings(), transport=FakeTransport([]))
    with pytest.raises(ValueError, match="finite"):
        client.request_to_pay(bad, "0772123456", "SALE-14")


def test_request_to_pay_rejects_invalid_reference_id():
    client = momo.MomoClient(_settings(), transport=FakeTransport([]))
    with pytest.raises(ValueError, match="UUID"):
        client.request_to_pay(
            5000, "0772123456", "SALE-15", reference_id="not-a-uuid"
        )


def test_request_to_pay_explains_sandbox_currency_rejection():
    transport = FakeTransport(
        [
            (200, {"access_token": "tok"}),
            (500, {"message": "Currency not supported."}),
        ]
    )
    client = momo.MomoClient(_settings(MOMO_CURRENCY="UGX"), transport=transport)

    with pytest.raises(momo.MomoError, match="sandbox accepts EUR only"):
        client.request_to_pay(5000, "0772123456", "SALE-13")


def test_request_status_reads_by_reference():
    transport = FakeTransport(
        [
            (200, {"access_token": "tok"}),
            (200, {"status": "SUCCESSFUL", "amount": "5000"}),
        ]
    )
    client = momo.MomoClient(_settings(), transport=transport)
    ref = "11111111-1111-4111-8111-111111111111"

    assert client.request_status(ref)["status"] == "SUCCESSFUL"
    assert transport.calls[1]["url"].endswith(
        f"/collection/v1_0/requesttopay/{ref}"
    )


def test_http_error_is_wrapped():
    transport = FakeTransport(
        [(401, {"message": "Access denied due to invalid subscription key"})]
    )
    client = momo.MomoClient(_settings(), transport=transport)

    with pytest.raises(momo.MomoError) as exc:
        client.access_token()
    assert exc.value.status == 401
    assert "invalid subscription key" in str(exc.value)


def test_missing_api_user_is_explained():
    client = momo.MomoClient(_settings(MOMO_API_USER=""), transport=FakeTransport([]))
    with pytest.raises(momo.MomoError, match="momo provision"):
        client.access_token()


def test_provision_creates_user_then_key():
    transport = FakeTransport(
        [
            (201, None),
            (201, {"apiKey": "generated-key"}),
        ]
    )
    api_user, api_key = momo.provision(_settings(), transport=transport)

    assert api_key == "generated-key"
    first, second = transport.calls
    assert first["url"] == momo.SANDBOX_BASE_URL + "/v1_0/apiuser"
    assert first["headers"]["X-Reference-Id"] == api_user
    assert first["body"] == {"providerCallbackHost": "localhost"}
    assert second["url"].endswith(f"/v1_0/apiuser/{api_user}/apikey")


# -- HTTP endpoints --------------------------------------------------------
def test_momo_endpoints_require_login(app_under_test, staff_client, client):
    assert client.get("/api/momo/health").status_code == 401
    assert client.post("/api/momo/collect", json={}).status_code == 401
    # Counter staff take MoMo payments at the POS, so they may use the rail.
    assert staff_client.get("/api/momo/health").status_code == 200
    assert staff_client.post("/api/momo/collect", json={}).status_code == 400


def test_momo_health_summarizes_configuration(app_under_test, admin_client):
    app_under_test.config.update(
        MOMO_SUBSCRIPTION_KEY="sub-key",
        MOMO_API_USER="api-user",
        MOMO_API_KEY="api-key",
        MOMO_TARGET_ENVIRONMENT="sandbox",
        MOMO_BASE_URL="",
    )
    body = admin_client.get("/api/momo/health").get_json()
    assert body["configured"] is True
    assert body["environment"] == "sandbox"
    assert body["base_url"] == momo.SANDBOX_BASE_URL


def test_momo_health_check_reports_unreachable(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.payments.routes as routes

    class Broken:
        def access_token(self, force=False):
            raise momo.MomoError("cannot reach MTN MoMo", status=503)

    monkeypatch.setattr(routes, "_client", lambda: Broken())
    response = admin_client.get("/api/momo/health?check=1")
    assert response.status_code == 503
    assert response.get_json()["reachable"] is False


def test_momo_collect_validates_input(admin_client):
    response = admin_client.post(
        "/api/momo/collect", json={"amount": 0, "phone": "0772123456"}
    )
    assert response.status_code == 400
    assert "amount" in response.get_json()["error"]

    response = admin_client.post(
        "/api/momo/collect", json={"amount": 5000, "phone": ""}
    )
    assert response.status_code == 400
    assert "phone" in response.get_json()["error"]


def test_momo_collect_accepts_request(admin_client, monkeypatch):
    import uuid

    import drugshop.payments.routes as routes

    _momo_config(admin_client.application, True)
    seen = {}

    class Fake:
        def request_to_pay(self, **kwargs):
            seen.update(kwargs)
            return {"reference_id": "ref-1", "amount": "5000"}

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect", json={"amount": 5000, "phone": "0772123456"}
    )
    assert response.status_code == 202
    body = response.get_json()
    # The route generates the UUID MTN needs and ignores the fake's echo.
    reference = body["reference_id"]
    assert str(uuid.UUID(reference)) == reference
    assert seen["reference_id"] == reference
    # MTN rejects an empty externalId, so the route always supplies one.
    assert seen["external_id"].startswith("POS-")


# -- POS sale integration --------------------------------------------------
def _stocked_product(client, name="MoMo Drug", price=5000, qty=20):
    from datetime import date, timedelta

    pid = client.post(
        "/api/products",
        json={"name": name, "price_buy": 100, "price_sell": price},
    ).get_json()["id"]
    client.post(
        "/api/batches",
        json={
            "product_id": pid,
            "qty_received": qty,
            "batch_no": "M1",
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        },
    )
    return pid


def _momo_config(app, verify):
    app.config.update(
        MOMO_SUBSCRIPTION_KEY="sub-key",
        MOMO_API_USER="api-user",
        MOMO_API_KEY="api-key",
        MOMO_TARGET_ENVIRONMENT="sandbox",
        MOMO_VERIFY_SALES=verify,
    )


def _stock(client, pid):
    return next(p for p in client.get("/api/products").get_json() if p["id"] == pid)[
        "stock_on_hand"
    ]


def test_sale_stores_momo_reference(app_under_test, admin_client):
    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client)

    r = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 2,
            "payment_method": "MTN_MOMO",
            "momo_ref": "ref-123",
        },
    )
    assert r.status_code == 201
    assert r.get_json()["momo_ref"] == "ref-123"
    row = next(
        s
        for s in admin_client.get("/api/sales").get_json()
        if s["id"] == r.get_json()["id"]
    )
    assert row["momo_ref"] == "ref-123"

    receipt = admin_client.get(
        f"/api/receipts/{r.get_json()['receipt_ref']}"
    ).get_json()
    assert receipt["momo_ref"] == "ref-123"


def test_momo_reference_cannot_be_reused(app_under_test, admin_client):
    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client)
    payload = {
        "product_id": pid,
        "qty": 1,
        "payment_method": "MTN_MOMO",
        "momo_ref": "ref-dup",
    }
    assert admin_client.post("/api/sales", json=payload).status_code == 201
    before = _stock(admin_client, pid)

    second = admin_client.post("/api/sales", json=payload)
    assert second.status_code == 409
    assert "already" in second.get_json()["error"]
    assert _stock(admin_client, pid) == before


def test_momo_reference_requires_momo_method(app_under_test, admin_client):
    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client)
    r = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "CASH",
            "momo_ref": "ref-cash",
        },
    )
    assert r.status_code == 400
    assert "MTN_MOMO" in r.get_json()["error"]


def test_sale_verifies_reference_amount(app_under_test, admin_client, monkeypatch):
    import drugshop.sales.routes as sales_routes

    _momo_config(app_under_test, True)
    seen = {}

    def fake_verify(reference, amount):
        seen["reference"] = reference
        seen["amount"] = amount
        return {"status": "SUCCESSFUL"}

    monkeypatch.setattr(sales_routes, "verify_reference", fake_verify)
    pid = _stocked_product(admin_client, price=2500)

    r = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 3,
            "payment_method": "MTN_MOMO",
            "momo_ref": "ref-ok",
        },
    )
    assert r.status_code == 201
    assert seen == {"reference": "ref-ok", "amount": 7500}


def test_sale_rejects_unconfirmed_payment(app_under_test, admin_client, monkeypatch):
    import drugshop.sales.routes as sales_routes
    from drugshop.payments.service import PaymentError

    _momo_config(app_under_test, True)

    def pending(reference, amount):
        raise PaymentError("MoMo payment is PENDING; the sale was not recorded")

    monkeypatch.setattr(sales_routes, "verify_reference", pending)
    pid = _stocked_product(admin_client)
    before = _stock(admin_client, pid)

    r = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 2,
            "payment_method": "MTN_MOMO",
            "momo_ref": "ref-pending",
        },
    )
    assert r.status_code == 402
    assert "PENDING" in r.get_json()["error"]
    assert _stock(admin_client, pid) == before


def test_momo_route_client_is_cached(app_under_test):
    import drugshop.payments.routes as routes

    routes._CLIENTS.clear()
    app_under_test.config.update(
        MOMO_SUBSCRIPTION_KEY="sub-key",
        MOMO_API_USER="api-user",
        MOMO_API_KEY="api-key",
    )
    with app_under_test.app_context():
        assert routes._client() is routes._client()
    routes._CLIENTS.clear()


def test_momo_collect_maps_mtn_4xx(admin_client, monkeypatch):
    import drugshop.payments.routes as routes

    _momo_config(admin_client.application, True)

    class Fake:
        def request_to_pay(self, **kwargs):
            raise momo.MomoError("bad phone", status=400)

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect", json={"amount": 5000, "phone": "0772123456"}
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["momo_status"] == 400
    assert body["status"] == "FAILED"
    from drugshop.db import q_one

    row = q_one(
        "SELECT status FROM momo_collections WHERE reference=?",
        (body["reference_id"],),
    )
    assert row["status"] == "FAILED"


def test_momo_collect_hides_mtn_5xx_as_502(admin_client, monkeypatch):
    import drugshop.payments.routes as routes

    _momo_config(admin_client.application, True)

    class Fake:
        def request_to_pay(self, **kwargs):
            raise momo.MomoError("MTN is down", status=503)

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect", json={"amount": 5000, "phone": "0772123456"}
    )
    assert response.status_code == 502
    body = response.get_json()
    assert body["status"] == "UNKNOWN"
    # The reference survives an ambiguous failure so the counter can poll it.
    assert body["reference_id"]


def test_unified_payments_dispatch_mtn(app_under_test, admin_client, monkeypatch):
    import drugshop.payments.routes as routes
    from drugshop.db import q_one

    _momo_config(app_under_test, True)

    class Fake:
        def request_to_pay(self, **kwargs):
            return {
                "reference_id": kwargs["reference_id"],
                "status": "PENDING",
                "amount": kwargs["amount"],
                "currency": "EUR",
            }

        def request_status(self, reference):
            return {
                "status": "SUCCESSFUL",
                "amount": "5000",
                "currency": "EUR",
                "financialTransactionId": "MTN-1",
            }

    monkeypatch.setattr(routes, "_client", lambda: Fake())

    created = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 5000,
            "phone": "0772123456",
            "provider": "MTN",
            "idempotency_key": "unified-mtn-1",
        },
    )
    assert created.status_code == 202, created.get_json()
    body = created.get_json()
    assert body["provider"] == "MTN"
    assert body["status"] == "PENDING"
    reference = body["reference_id"]
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["provider"] == "MTN"

    status = admin_client.get(f"/api/payments/status/MTN/{reference}")
    assert status.status_code == 200
    status_body = status.get_json()
    assert status_body["provider"] == "MTN"
    assert status_body["status"] == "SUCCESSFUL"
    assert status_body["ledger_status"] == "SUCCESSFUL"


def test_unified_payments_collect_auto_detects_mtn(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.payments.routes as routes

    _momo_config(app_under_test, True)
    calls = []

    class Fake:
        def request_to_pay(self, **kwargs):
            calls.append(kwargs)
            return {
                "reference_id": kwargs["reference_id"],
                "status": "PENDING",
                "amount": kwargs["amount"],
                "currency": "EUR",
            }

    monkeypatch.setattr(routes, "_client", lambda: Fake())

    response = admin_client.post(
        "/api/payments/collect",
        json={"amount": 1000, "phone": "0772123456", "idempotency_key": "auto-mtn"},
    )

    assert response.status_code == 202, response.get_json()
    assert response.get_json()["provider"] == "MTN"
    assert calls[0]["phone"].startswith("256")


def test_momo_health_check_wraps_invalid_base_url(app_under_test, admin_client):
    app_under_test.config.update(
        MOMO_SUBSCRIPTION_KEY="sub-key",
        MOMO_API_USER="api-user",
        MOMO_API_KEY="api-key",
        MOMO_BASE_URL="not-a-url",
    )
    response = admin_client.get("/api/momo/health?check=1")
    assert response.status_code == 503
    assert "invalid MTN MoMo URL" in response.get_json()["error"]


def test_cart_momo_verifies_basket_total(app_under_test, admin_client, monkeypatch):
    import drugshop.sales.routes as sales_routes

    _momo_config(app_under_test, True)
    amounts = []
    monkeypatch.setattr(
        sales_routes,
        "verify_reference",
        lambda reference, amount: amounts.append(amount) or {"status": "SUCCESSFUL"},
    )
    p1 = _stocked_product(admin_client, name="Cart A", price=1000)
    p2 = _stocked_product(admin_client, name="Cart B", price=2500)

    r = admin_client.post(
        "/api/sales/cart",
        json={
            "items": [{"product_id": p1, "qty": 2}, {"product_id": p2, "qty": 2}],
            "payment_method": "MTN_MOMO",
            "momo_ref": "ref-cart",
        },
    )
    assert r.status_code == 201
    assert amounts == [7000]
    assert r.get_json()["momo_ref"] == "ref-cart"


def test_momo_service_checks_status_and_amount(app_under_test, monkeypatch):
    import drugshop.payments.service as svc

    _momo_config(app_under_test, True)

    class FakeClient:
        def __init__(self, settings):
            self.settings = settings

        def request_status(self, reference):
            return {"status": "SUCCESSFUL", "amount": "4000", "currency": "UGX"}

    monkeypatch.setattr(svc, "MomoClient", FakeClient)
    with app_under_test.app_context():
        with pytest.raises(svc.PaymentError, match="MoMo paid"):
            svc.verify_reference("ref", 5000)

        monkeypatch.setattr(
            FakeClient,
            "request_status",
            lambda self, reference: {"status": "PENDING"},
        )
        with pytest.raises(svc.PaymentError, match="PENDING"):
            svc.verify_reference("ref", 5000)


def test_momo_service_fails_closed_without_credentials(app_under_test):
    import drugshop.payments.service as svc

    app_under_test.config.update(
        MOMO_SUBSCRIPTION_KEY="",
        MOMO_API_USER="",
        MOMO_API_KEY="",
        MOMO_VERIFY_SALES=True,
    )
    with app_under_test.app_context():
        with pytest.raises(svc.PaymentError) as exc:
            svc.verify_reference("anything", 100)
    assert exc.value.status == 503
    assert "incomplete" in str(exc.value)


# -- Phase 1 ledger, anti-replay, and callback ------------------------------
def _pending_reference(admin_client, monkeypatch, key="callback-key", verify=True):
    """Create one pending API collection and return its reference."""
    import drugshop.payments.routes as routes

    _momo_config(admin_client.application, verify)

    class Fake:
        def request_to_pay(self, **kwargs):
            return {"reference_id": kwargs["reference_id"]}

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect",
        json={
            "amount": 5000,
            "phone": "0772123456",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202, response.get_json()
    return response.get_json()["reference_id"]


def test_momo_collect_writes_pending_ledger_before_calling_mtn(
    admin_client, monkeypatch
):
    import drugshop.payments.routes as routes
    from drugshop.db import q_one

    _momo_config(admin_client.application, True)
    seen = {}

    class Fake:
        def request_to_pay(self, **kwargs):
            seen["row"] = q_one(
                "SELECT * FROM momo_collections WHERE reference=?",
                (kwargs["reference_id"],),
            )
            return {"reference_id": kwargs["reference_id"]}

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect",
        json={
            "amount": 5000,
            "phone": "0772123456",
            "external_id": "SALE-1",
            "idempotency_key": "key-1",
        },
    )

    assert response.status_code == 202
    row = seen["row"]
    assert row is not None
    assert row["status"] == "PENDING"
    assert row["source"] == "API"
    assert row["amount"] == 5000
    assert row["currency"] == "EUR"
    assert row["external_id"] == "SALE-1"
    assert row["idempotency_key"] == "key-1"


def test_momo_collect_reuses_idempotency_key(admin_client, monkeypatch):
    import drugshop.payments.routes as routes

    _momo_config(admin_client.application, True)
    calls = []

    class Fake:
        def request_to_pay(self, **kwargs):
            calls.append(kwargs["reference_id"])
            return {"reference_id": kwargs["reference_id"]}

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    payload = {
        "amount": 5000,
        "phone": "0772123456",
        "idempotency_key": "same-key",
        "external_id": "SALE-2",
    }

    first = admin_client.post("/api/momo/collect", json=payload)
    second = admin_client.post("/api/momo/collect", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.get_json()["reference_id"] == second.get_json()["reference_id"]
    assert second.get_json()["reused"] is True
    assert len(calls) == 1


def test_momo_collect_keeps_reference_on_ambiguous_failure(
    admin_client, monkeypatch
):
    import drugshop.payments.routes as routes
    from drugshop.db import q_one

    _momo_config(admin_client.application, True)

    class Fake:
        def request_to_pay(self, **kwargs):
            raise momo.MomoError("connection reset", status=None)

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect",
        json={
            "amount": 5000,
            "phone": "0772123456",
            "idempotency_key": "unknown-key",
        },
    )

    assert response.status_code == 502
    body = response.get_json()
    assert body["status"] == "UNKNOWN"
    assert body["reference_id"]
    row = q_one(
        "SELECT * FROM momo_collections WHERE reference=?",
        (body["reference_id"],),
    )
    assert row["status"] == "UNKNOWN"
    assert row["last_error"] == "connection reset"


def test_momo_status_updates_ledger(admin_client, monkeypatch):
    import drugshop.payments.routes as routes
    from drugshop.db import q_one

    _momo_config(admin_client.application, True)

    class Fake:
        def request_to_pay(self, **kwargs):
            return {"reference_id": kwargs["reference_id"]}

        def request_status(self, reference):
            return {
                "status": "SUCCESSFUL",
                "amount": "5000",
                "currency": "EUR",
                "financialTransactionId": "TXN-1",
            }

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    created = admin_client.post(
        "/api/momo/collect",
        json={"amount": 5000, "phone": "0772123456"},
    )
    reference = created.get_json()["reference_id"]

    response = admin_client.get(f"/api/momo/collect/{reference}")

    assert response.status_code == 200
    assert response.get_json()["status"] == "SUCCESSFUL"
    assert response.get_json()["ledger_status"] == "SUCCESSFUL"
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["status"] == "SUCCESSFUL"
    assert row["mtn_status"] == "SUCCESSFUL"
    assert row["mtn_amount"] == 5000
    assert row["financial_txn_id"] == "TXN-1"


def test_momo_status_rejects_non_uuid(admin_client):
    response = admin_client.get("/api/momo/collect/not-a-uuid")

    assert response.status_code == 400
    assert "UUID" in response.get_json()["error"]


def test_momo_callback_disabled_without_secret(client):
    response = client.post(
        "/api/momo/callback?token=anything",
        json={
            "referenceId": "11111111-1111-4111-8111-111111111111",
            "status": "SUCCESSFUL",
        },
    )

    assert response.status_code == 404


def test_momo_callback_requires_secret_and_updates_existing(
    app_under_test, admin_client, client, monkeypatch
):
    from drugshop.db import q_one

    reference = _pending_reference(admin_client, monkeypatch)
    app_under_test.config.update(MOMO_CALLBACK_SECRET="cb-secret")

    wrong = client.post(
        "/api/momo/callback?token=wrong",
        json={"referenceId": reference, "status": "SUCCESSFUL"},
    )
    assert wrong.status_code == 403

    ok = client.post(
        "/api/momo/callback",
        headers={"X-Callback-Token": "cb-secret"},
        json={
            "referenceId": reference,
            "status": "SUCCESSFUL",
            "amount": "5000",
            "currency": "EUR",
            "financialTransactionId": "TXN-CB",
        },
    )
    assert ok.status_code == 200
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["status"] == "SUCCESSFUL"
    assert row["financial_txn_id"] == "TXN-CB"
    event = q_one(
        "SELECT * FROM momo_events WHERE reference=? AND event='CALLBACK'",
        (reference,),
    )
    assert event is not None

    bad_status = client.post(
        "/api/momo/callback?token=cb-secret",
        json={"referenceId": reference, "status": "PAID"},
    )
    assert bad_status.status_code == 400

    unknown_ref = "22222222-2222-4222-8222-222222222222"
    unknown = client.post(
        "/api/momo/callback?token=cb-secret",
        json={"referenceId": unknown_ref, "status": "SUCCESSFUL"},
    )
    assert unknown.status_code == 404
    assert (
        q_one(
            "SELECT * FROM momo_collections WHERE reference=?", (unknown_ref,)
        )
        is None
    )


def test_void_keeps_momo_reference_consumed(app_under_test, admin_client):
    from drugshop.db import q_one

    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client)
    payload = {
        "product_id": pid,
        "qty": 1,
        "payment_method": "MTN_MOMO",
        "momo_ref": "ref-void",
    }

    created = admin_client.post("/api/sales", json=payload)
    assert created.status_code == 201
    sale_id = created.get_json()["id"]
    assert admin_client.delete(f"/api/sales/{sale_id}").status_code == 200

    row = q_one("SELECT * FROM momo_collections WHERE reference='REF-VOID'")
    assert row["status"] == "CONSUMED"
    event = q_one(
        "SELECT * FROM momo_events WHERE reference='REF-VOID' "
        "AND event='SALE_VOIDED'"
    )
    assert event is not None

    replay = admin_client.post("/api/sales", json=payload)
    assert replay.status_code == 409


def test_manual_entry_requires_reference_when_verification_enabled(
    app_under_test, admin_client
):
    _momo_config(app_under_test, True)
    pid = _stocked_product(admin_client)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 400
    assert "reference" in response.get_json()["error"].lower()


def test_manual_entry_records_reference_without_gateway_call(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.sales.routes as sales_routes
    from drugshop.db import q_one

    _momo_config(app_under_test, True)

    def fail(*args, **kwargs):
        raise AssertionError("manual entry must not call the gateway verifier")

    monkeypatch.setattr(sales_routes, "verify_reference", fail)
    pid = _stocked_product(admin_client)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": "manual-1",
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 201
    row = q_one("SELECT * FROM momo_collections WHERE reference='MANUAL-1'")
    assert row["status"] == "CONSUMED"
    assert row["source"] == "MANUAL"
    # Manual till references are local-currency payments, not MTN sandbox EUR.
    assert row["currency"] == "UGX"


def test_manual_entry_allows_no_reference_when_verification_off(
    app_under_test, admin_client
):
    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 201
    assert response.get_json()["momo_ref"] == ""


def test_manual_entry_cannot_consume_pending_api_payment(
    app_under_test, admin_client, monkeypatch
):
    _momo_config(app_under_test, True)
    reference = _pending_reference(admin_client, monkeypatch, key="pending-manual")
    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": reference,
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 402
    assert _stock(admin_client, pid) == before


def test_manual_entry_cannot_consume_pending_legacy_payment(
    app_under_test, admin_client
):
    from drugshop.db import q_one
    from drugshop.payments import ledger

    _momo_config(app_under_test, False)
    with app_under_test.app_context():
        ledger.apply_status(
            "LEGACY-PENDING-1",
            {"status": "PENDING", "amount": 5000, "currency": "UGX"},
            provider="MTN",
        )
    row = q_one("SELECT * FROM momo_collections WHERE reference='LEGACY-PENDING-1'")
    assert row["source"] == "LEGACY"
    assert row["status"] == "PENDING"
    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": "LEGACY-PENDING-1",
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 402
    assert "not been confirmed" in response.get_json()["error"]
    assert _stock(admin_client, pid) == before


def test_rollout_path_can_claim_pending_api_payment(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    reference = _pending_reference(
        admin_client, monkeypatch, key="rollout", verify=False
    )
    pid = _stocked_product(admin_client, price=5000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 201
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["status"] == "CONSUMED"


def test_sale_fails_closed_when_verification_enabled_without_credentials(
    app_under_test, admin_client
):
    app_under_test.config.update(
        MOMO_SUBSCRIPTION_KEY="",
        MOMO_API_USER="",
        MOMO_API_KEY="",
        MOMO_VERIFY_SALES=True,
    )
    pid = _stocked_product(admin_client)
    before = _stock(admin_client, pid)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": "some-ref",
        },
    )

    assert response.status_code == 503
    assert _stock(admin_client, pid) == before


def test_momo_service_requires_amount_and_currency(app_under_test, monkeypatch):
    import drugshop.payments.service as svc

    _momo_config(app_under_test, True)

    class FakeClient:
        payload = {}

        def __init__(self, settings):
            pass

        def request_status(self, reference):
            return dict(self.payload)

    monkeypatch.setattr(svc, "MomoClient", FakeClient)
    with app_under_test.app_context():
        FakeClient.payload = {
            "status": "SUCCESSFUL",
            "amount": "5000",
            "currency": "GHS",
        }
        with pytest.raises(svc.PaymentError, match="currency"):
            svc.verify_reference("ref", 5000)

        FakeClient.payload = {"status": "SUCCESSFUL", "currency": "EUR"}
        with pytest.raises(svc.PaymentError, match="amount"):
            svc.verify_reference("ref", 5000)

        FakeClient.payload = {"status": "SUCCESSFUL", "amount": "5000"}
        with pytest.raises(svc.PaymentError, match="currency"):
            svc.verify_reference("ref", 5000)


def test_replayed_sale_returns_existing_receipt(app_under_test, admin_client):
    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client)
    payload = {
        "product_id": pid,
        "qty": 1,
        "payment_method": "MTN_MOMO",
        "momo_ref": "ref-replay-receipt",
    }

    first = admin_client.post("/api/sales", json=payload)
    assert first.status_code == 201
    receipt = first.get_json()["receipt_ref"]
    sale_id = first.get_json()["id"]

    second = admin_client.post("/api/sales", json=payload)
    assert second.status_code == 409
    body = second.get_json()
    assert body["receipt_ref"] == receipt
    assert body["sale_id"] == sale_id


def test_cart_replay_returns_existing_receipt(app_under_test, admin_client):
    _momo_config(app_under_test, False)
    pid = _stocked_product(admin_client, price=1000)
    payload = {
        "items": [{"product_id": pid, "qty": 2}],
        "payment_method": "MTN_MOMO",
        "momo_ref": "ref-cart-replay",
    }

    first = admin_client.post("/api/sales/cart", json=payload)
    assert first.status_code == 201
    receipt = first.get_json()["receipt_ref"]

    second = admin_client.post("/api/sales/cart", json=payload)
    assert second.status_code == 409
    assert second.get_json()["receipt_ref"] == receipt


def test_callback_amount_mismatch_blocks_sale(
    app_under_test, admin_client, client, monkeypatch
):
    reference = _pending_reference(
        admin_client, monkeypatch, key="cb-amount", verify=False
    )
    app_under_test.config.update(MOMO_CALLBACK_SECRET="cb-secret")
    callback = client.post(
        "/api/momo/callback?token=cb-secret",
        json={
            "referenceId": reference,
            "status": "SUCCESSFUL",
            "amount": "4000",
            "currency": "EUR",
        },
    )
    assert callback.status_code == 200

    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)
    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 402
    assert _stock(admin_client, pid) == before


def test_callback_currency_mismatch_blocks_sale(
    app_under_test, admin_client, client, monkeypatch
):
    reference = _pending_reference(
        admin_client, monkeypatch, key="cb-currency", verify=False
    )
    app_under_test.config.update(MOMO_CALLBACK_SECRET="cb-secret")
    callback = client.post(
        "/api/momo/callback?token=cb-secret",
        json={
            "referenceId": reference,
            "status": "SUCCESSFUL",
            "amount": "5000",
            "currency": "GHS",
        },
    )
    assert callback.status_code == 200

    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)
    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "MTN_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 402
    assert _stock(admin_client, pid) == before


def test_momo_service_reuses_client(app_under_test, monkeypatch):
    import drugshop.payments.service as svc

    _momo_config(app_under_test, True)
    built = []

    class FakeClient:
        def __init__(self, settings):
            built.append(settings)

        def request_status(self, reference):
            return {"status": "SUCCESSFUL", "amount": "5000", "currency": "EUR"}

    monkeypatch.setattr(svc, "MomoClient", FakeClient)
    reference = "11111111-1111-4111-8111-111111111111"
    with app_under_test.app_context():
        svc.verify_reference(reference, 5000)
        svc.verify_reference(reference, 5000)

    assert len(built) == 1
