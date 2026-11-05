"""Airtel Money client, unified routes, and sale guard - fully offline.

Every Airtel client test injects a fake transport; every route/service test
monkeypatches the client constructor. No test can reach Airtel or move money.
"""

import json

import pytest

from drugshop.payments import airtel, providers

AIRTEL_REF = "22222222-2222-4222-8222-222222222222"
MTN_REF = "11111111-1111-4111-8111-111111111111"


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
        "AIRTEL_CLIENT_ID": "client-id",
        "AIRTEL_CLIENT_SECRET": "client-secret",
        "AIRTEL_BASE_URL": "https://openapiuat.airtel.africa",
        "AIRTEL_CURRENCY": "UGX",
        "AIRTEL_COUNTRY": "UG",
        "AIRTEL_TIMEOUT": "20",
    }
    values.update(overrides)
    return airtel.AirtelSettings.from_mapping(values)


def _client(responses, **overrides):
    transport = FakeTransport(responses)
    return airtel.AirtelClient(_settings(**overrides), transport=transport), transport


def _token_response(value="token-1"):
    return (200, {"access_token": value, "expires_in": 3600})


def _status_payload(status="TS", amount="5000", currency="UGX", txn="AM-1"):
    transaction = {"status": status, "airtel_money_id": txn}
    if amount is not None:
        transaction["amount"] = amount
    if currency is not None:
        transaction["currency"] = currency
    return (200, {"data": {"transaction": transaction}})


# -- provider detection ----------------------------------------------------
@pytest.mark.parametrize(
    "phone,method",
    [
        ("0772123456", "MTN_MOMO"),
        ("+256 772 123 456", "MTN_MOMO"),
        ("256781234567", "MTN_MOMO"),
        ("0392123456", "MTN_MOMO"),
        ("0701234567", "AIRTEL_MOMO"),
        ("0741234567", "AIRTEL_MOMO"),
        ("0751234567", "AIRTEL_MOMO"),
        ("0201234567", "AIRTEL_MOMO"),
        ("+256 701 234 567", "AIRTEL_MOMO"),
        ("256701234567", "AIRTEL_MOMO"),
        ("2560701234567", "AIRTEL_MOMO"),
        ("0711234567", "UNKNOWN"),
        ("0791234567", "UNKNOWN"),
        ("", "UNKNOWN"),
        ("not-a-phone", "UNKNOWN"),
    ],
)
def test_ugandan_telco_detection(phone, method):
    assert providers.detect_telco(phone) == method
    expected = {"MTN_MOMO": "MTN", "AIRTEL_MOMO": "AIRTEL"}.get(method, "UNKNOWN")
    assert providers.detect_provider(phone) == expected


def test_provider_aliases_and_methods():
    assert providers.normalize_provider("mtn") == "MTN"
    assert providers.normalize_provider("AIRTEL_MONEY") == "AIRTEL"
    assert providers.normalize_provider("", default="AIRTEL_MOMO") == "AIRTEL"
    with pytest.raises(ValueError, match="unsupported"):
        providers.normalize_provider("TELECOM")
    assert providers.provider_for_method("AIRTEL_MOMO") == "AIRTEL"
    assert providers.method_for_provider("MTN") == "MTN_MOMO"
    assert providers.is_momo_method("AIRTEL_MOMO") is True
    assert providers.is_momo_method("CASH") is False


# -- Airtel client ---------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0701234567", "701234567"),
        ("+256701234567", "701234567"),
        ("256701234567", "701234567"),
        ("00256701234567", "701234567"),
        ("2560701234567", "701234567"),
        ("701234567", "701234567"),
    ],
)
def test_airtel_msisdn_is_national_digits(raw, expected):
    assert airtel.normalize_msisdn(raw) == expected


@pytest.mark.parametrize("raw", ["", "07123", "0701234567890123456", "12345"])
def test_airtel_msisdn_rejects_bad_numbers(raw):
    with pytest.raises(ValueError):
        airtel.normalize_msisdn(raw)


def test_airtel_settings_status_payload_hides_secrets():
    settings = _settings()
    assert settings.configured is True
    assert settings.environment == "sandbox"
    payload = settings.status_payload
    assert payload["configured"] is True
    assert payload["has_client_secret"] is True
    assert "client-secret" not in json.dumps(payload)


def test_airtel_collection_payload_and_token_reuse():
    client, transport = _client(
        [
            _token_response("token-1"),
            (200, {"status": {"code": "200", "success": True}}),
            _status_payload("TS", "5000.00", "UGX"),
        ]
    )

    created = client.request_to_pay(
        5000,
        "0701234567",
        external_id="POS-42",
        reference_id=AIRTEL_REF,
    )

    assert created["reference_id"] == AIRTEL_REF
    assert created["status"] == "PENDING"
    assert created["phone"] == "701234567"
    assert transport.calls[0]["url"].endswith("/auth/oauth2/token")
    assert transport.calls[0]["body"] == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "grant_type": "client_credentials",
    }
    collect = transport.calls[1]
    assert collect["method"] == "POST"
    assert collect["url"].endswith("/merchant/v1/payments/")
    assert collect["headers"]["Authorization"] == "Bearer token-1"
    assert collect["headers"]["X-Country"] == "UG"
    assert collect["headers"]["X-Currency"] == "UGX"
    assert collect["body"] == {
        "reference": "POS-42",
        "subscriber": {"country": "UG", "currency": "UGX", "msisdn": "701234567"},
        "transaction": {
            "amount": 5000,
            "country": "UG",
            "currency": "UGX",
            "id": AIRTEL_REF,
        },
    }

    status = client.request_status(AIRTEL_REF)
    assert status["status"] == "SUCCESSFUL"
    assert status["amount"] == "5000.00"
    assert status["currency"] == "UGX"
    assert status["financialTransactionId"] == "AM-1"
    assert transport.calls[2]["headers"]["Authorization"] == "Bearer token-1"
    # One token exchange only: the cached bearer is reused for the status call.
    assert [c["url"] for c in transport.calls].count(
        "https://openapiuat.airtel.africa/auth/oauth2/token"
    ) == 1


def test_airtel_refreshes_token_once_after_401():
    client, transport = _client(
        [
            _token_response("old-token"),
            (401, {"status": {"code": "401", "message": "expired"}}),
            _token_response("new-token"),
            _status_payload(),
        ]
    )

    result = client.request_status(AIRTEL_REF)

    assert result["status"] == "SUCCESSFUL"
    assert [call["method"] for call in transport.calls] == [
        "POST",
        "GET",
        "POST",
        "GET",
    ]
    assert transport.calls[1]["headers"]["Authorization"] == "Bearer old-token"
    assert transport.calls[3]["headers"]["Authorization"] == "Bearer new-token"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("TS", "SUCCESSFUL"),
        ("TF", "FAILED"),
        ("TIN", "FAILED"),
        ("TIP", "PENDING"),
        ("TA", "UNKNOWN"),
        ("TE", "TIMEOUT"),
        ("something-else", "UNKNOWN"),
    ],
)
def test_airtel_status_mapping(raw, expected):
    client, _ = _client([_token_response(), _status_payload(raw)])
    assert client.request_status(AIRTEL_REF)["status"] == expected


def test_airtel_status_accepts_top_level_transaction_fallback():
    client, _ = _client(
        [
            _token_response(),
            (
                200,
                {
                    "transaction": {
                        "status": "TS",
                        "amount": 2500,
                        "currency": "UGX",
                        "airtel_money_id": "AM-TOP",
                    }
                },
            ),
        ]
    )
    result = client.request_status(AIRTEL_REF)
    assert result["status"] == "SUCCESSFUL"
    assert result["amount"] == 2500
    assert result["financialTransactionId"] == "AM-TOP"


def test_airtel_collection_business_failure_is_an_error():
    client, _ = _client(
        [
            _token_response(),
            (
                200,
                {
                    "status": {
                        "code": "400",
                        "success": False,
                        "message": "Invalid subscriber",
                    }
                },
            ),
        ]
    )
    with pytest.raises(airtel.AirtelError, match="Invalid subscriber") as exc:
        client.request_to_pay(1000, "0701234567")
    assert exc.value.status == 400


def test_airtel_collection_rejects_bad_amounts_and_ids():
    client, _ = _client([])
    with pytest.raises(ValueError, match="greater than zero"):
        client.request_to_pay(0, "0701234567")
    with pytest.raises(ValueError, match="whole numbers"):
        client.request_to_pay(1000.5, "0701234567", currency="UGX")
    with pytest.raises(ValueError, match="UUID"):
        client.request_to_pay(1000, "0701234567", reference_id="not-a-uuid")
    with pytest.raises(ValueError, match="three-letter"):
        client.request_to_pay(1000, "0701234567", currency="UG")


def test_airtel_token_failure_is_clear():
    client, _ = _client([(401, {"status": {"code": "401", "message": "bad creds"}})])
    with pytest.raises(airtel.AirtelError, match="bad creds") as exc:
        client.access_token()
    assert exc.value.status == 401


# -- unified routes --------------------------------------------------------
def _airtel_config(app, verify=False):
    app.config.update(
        AIRTEL_CLIENT_ID="client-id",
        AIRTEL_CLIENT_SECRET="client-secret",
        AIRTEL_BASE_URL="https://openapiuat.airtel.africa",
        AIRTEL_CURRENCY="UGX",
        AIRTEL_COUNTRY="UG",
        AIRTEL_TIMEOUT=20,
        AIRTEL_VERIFY_SALES=verify,
    )


class FakeAirtel:
    def __init__(self):
        self.collect_calls = []
        self.status_calls = []
        self.status = {
            "status": "SUCCESSFUL",
            "amount": "5000",
            "currency": "UGX",
            "financialTransactionId": "AM-1",
        }

    def request_to_pay(self, **kwargs):
        self.collect_calls.append(kwargs)
        return {
            "reference_id": kwargs["reference_id"],
            "status": "PENDING",
            "amount": kwargs["amount"],
            "currency": "UGX",
        }

    def request_status(self, reference):
        self.status_calls.append(reference)
        return dict(self.status)


def _install_airtel(monkeypatch, fake=None):
    import drugshop.payments.routes as routes

    fake = fake or FakeAirtel()
    monkeypatch.setattr(routes, "_airtel_client", lambda: fake)
    return fake


def _airtel_pending(admin_client, monkeypatch, amount=5000, key="airtel-key"):
    fake = _install_airtel(monkeypatch)
    response = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": amount,
            "phone": "0701234567",
            "provider": "AIRTEL",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 202, response.get_json()
    return response.get_json()["reference_id"], fake


def test_payments_health_lists_both_providers(app_under_test, admin_client):
    _airtel_config(app_under_test)
    response = admin_client.get("/api/payments/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["providers"]["AIRTEL"]["configured"] is True
    assert body["providers"]["AIRTEL"]["payment_method"] == "AIRTEL_MOMO"
    assert body["providers"]["MTN"]["payment_method"] == "MTN_MOMO"
    assert body["providers"]["MTN"]["configured"] is False


def test_payments_health_check_ignores_intentionally_unconfigured_provider(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.payments.routes as routes

    _airtel_config(app_under_test)

    class Fake:
        def access_token(self, force=False):
            return "token-1"

    monkeypatch.setattr(routes, "_airtel_client", lambda: Fake())
    response = admin_client.get("/api/payments/health?check=1")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["providers"]["AIRTEL"]["reachable"] is True
    assert body["providers"]["MTN"]["reachable"] is False


def test_payments_detect_returns_provider_and_method(admin_client):
    response = admin_client.post(
        "/api/payments/detect", json={"phone": "+256 701 234 567"}
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "provider": "AIRTEL",
        "payment_method": "AIRTEL_MOMO",
        "phone": "0701234567",
    }


def test_payments_collect_airtel_is_idempotent(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    _airtel_config(app_under_test)
    reference, fake = _airtel_pending(admin_client, monkeypatch)

    assert len(fake.collect_calls) == 1
    call = fake.collect_calls[0]
    assert call["phone"] == "701234567"
    assert call["reference_id"] == reference
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["provider"] == "AIRTEL"
    assert row["status"] == "PENDING"
    assert row["currency"] == "UGX"

    retry = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 5000,
            "phone": "0701234567",
            "provider": "AIRTEL",
            "idempotency_key": "airtel-key",
        },
    )
    assert retry.status_code == 202
    assert retry.get_json()["reference_id"] == reference
    assert retry.get_json()["reused"] is True
    assert len(fake.collect_calls) == 1


def test_payments_collect_auto_detects_airtel(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test)
    fake = _install_airtel(monkeypatch)
    response = admin_client.post(
        "/api/payments/collect",
        json={"amount": 1200, "phone": "0701234567", "idempotency_key": "auto-key"},
    )
    assert response.status_code == 202
    assert response.get_json()["provider"] == "AIRTEL"
    assert fake.collect_calls[0]["phone"] == "701234567"


def test_payments_collect_rejects_unknown_carrier(app_under_test, admin_client):
    _airtel_config(app_under_test)
    response = admin_client.post(
        "/api/payments/collect",
        json={"amount": 1200, "phone": "0711234567"},
    )
    assert response.status_code == 400
    assert response.get_json()["provider"] == "UNKNOWN"


def test_payments_status_airtel_and_provider_mismatch(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test)
    reference, fake = _airtel_pending(admin_client, monkeypatch)

    ok = admin_client.get(f"/api/payments/status/AIRTEL/{reference}")
    assert ok.status_code == 200
    body = ok.get_json()
    assert body["status"] == "SUCCESSFUL"
    assert body["provider"] == "AIRTEL"
    assert body["ledger_status"] == "SUCCESSFUL"

    wrong = admin_client.get(f"/api/payments/status/MTN/{reference}")
    assert wrong.status_code == 409
    assert wrong.get_json()["provider"] == "AIRTEL"
    assert fake.status_calls == [reference]


@pytest.mark.parametrize(
    "reported,expected",
    [("TA", "UNKNOWN"), ("TE", "TIMEOUT"), ("TIN", "FAILED")],
)
def test_payments_status_airtel_maps_terminal_statuses(
    app_under_test, admin_client, monkeypatch, reported, expected
):
    from drugshop.db import q_one

    _airtel_config(app_under_test)
    reference, fake = _airtel_pending(admin_client, monkeypatch)
    fake.status = {
        "status": expected,
        "amount": "5000",
        "currency": "UGX",
    }

    response = admin_client.get(f"/api/payments/status/AIRTEL/{reference}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == expected
    assert body["ledger_status"] == expected
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["status"] == expected


def test_unified_idempotency_keys_do_not_collide_across_providers(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.payments.routes as routes
    from drugshop.db import q_one

    _airtel_config(app_under_test)
    app_under_test.config.update(
        MOMO_SUBSCRIPTION_KEY="sub-key",
        MOMO_API_USER="api-user",
        MOMO_API_KEY="api-key",
        MOMO_TARGET_ENVIRONMENT="sandbox",
    )

    class FakeMtn:
        def request_to_pay(self, **kwargs):
            return {
                "reference_id": kwargs["reference_id"],
                "status": "PENDING",
                "amount": kwargs["amount"],
                "currency": "EUR",
            }

    monkeypatch.setattr(routes, "_client", lambda: FakeMtn())
    _install_airtel(monkeypatch)

    mtn = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 5000,
            "phone": "0772123456",
            "provider": "MTN",
            "idempotency_key": "shared-key",
        },
    )
    airtel = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 5000,
            "phone": "0701234567",
            "provider": "AIRTEL",
            "idempotency_key": "shared-key",
        },
    )

    assert mtn.status_code == 202, mtn.get_json()
    assert airtel.status_code == 202, airtel.get_json()
    assert mtn.get_json()["reference_id"] != airtel.get_json()["reference_id"]
    mtn_row = q_one(
        "SELECT * FROM momo_collections WHERE reference=?",
        (mtn.get_json()["reference_id"],),
    )
    airtel_row = q_one(
        "SELECT * FROM momo_collections WHERE reference=?",
        (airtel.get_json()["reference_id"],),
    )
    assert mtn_row["provider"] == "MTN"
    assert airtel_row["provider"] == "AIRTEL"


def test_payments_collect_unknown_outcome_keeps_reference(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    _airtel_config(app_under_test)

    class Failing(FakeAirtel):
        def request_to_pay(self, **kwargs):
            raise airtel.AirtelError("connection reset", status=None)

    fake = _install_airtel(monkeypatch, Failing())
    response = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 5000,
            "phone": "0701234567",
            "provider": "AIRTEL",
            "idempotency_key": "unknown-airtel",
        },
    )
    assert response.status_code == 502
    body = response.get_json()
    assert body["status"] == "UNKNOWN"
    assert body["provider"] == "AIRTEL"
    row = q_one(
        "SELECT * FROM momo_collections WHERE reference=?", (body["reference_id"],)
    )
    assert row["status"] == "UNKNOWN"
    assert row["provider"] == "AIRTEL"
    assert fake.collect_calls == []


def test_payments_collect_definitive_failure_marks_failed(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    _airtel_config(app_under_test)

    class Rejected(FakeAirtel):
        def request_to_pay(self, **kwargs):
            raise airtel.AirtelError("invalid subscriber", status=400)

    _install_airtel(monkeypatch, Rejected())
    response = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 5000,
            "phone": "0701234567",
            "provider": "AIRTEL",
            "idempotency_key": "rejected-airtel",
        },
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "FAILED"
    row = q_one(
        "SELECT * FROM momo_collections WHERE reference=?", (body["reference_id"],)
    )
    assert row["status"] == "FAILED"
    assert row["provider"] == "AIRTEL"


# -- sale guard ------------------------------------------------------------
def _stocked_product(client, name="Airtel Drug", price=5000, qty=20):
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
            "batch_no": "A1",
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        },
    )
    return pid


def _stock(client, pid):
    return next(p for p in client.get("/api/products").get_json() if p["id"] == pid)[
        "stock_on_hand"
    ]


def _install_verifier(monkeypatch, **overrides):
    import drugshop.payments.service as svc

    svc.reset_clients()
    data = {
        "status": "SUCCESSFUL",
        "amount": "5000",
        "currency": "UGX",
        "financialTransactionId": "AM-1",
    }
    data.update(overrides)
    built = []

    class FakeClient:
        def __init__(self, settings):
            built.append(settings)

        def request_status(self, reference):
            return dict(data)

    monkeypatch.setattr(svc, "AirtelClient", FakeClient)
    return built


def test_airtel_sale_verification_claims_ledger(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch)
    pid = _stocked_product(admin_client, price=5000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 201, response.get_json()
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["provider"] == "AIRTEL"
    assert row["status"] == "CONSUMED"
    assert row["source"] == "API"
    assert row["sale_receipt_ref"]


def test_airtel_sale_rejects_amount_mismatch(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch, amount="4000")
    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 402
    body = response.get_json()
    assert "Airtel" in body["error"]
    assert body["paid_amount"] == 4000
    assert body["paid_currency"] == "UGX"
    assert _stock(admin_client, pid) == before


def test_airtel_sale_rejects_currency_mismatch(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch, currency="EUR")
    pid = _stocked_product(admin_client, price=5000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 402
    assert "EUR" in response.get_json()["error"]


def test_airtel_sale_uses_ledger_currency_when_status_omits_it(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch, currency=None)
    pid = _stocked_product(admin_client, price=5000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 201, response.get_json()
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["status"] == "CONSUMED"
    assert row["currency"] == "UGX"


def test_airtel_sale_rejects_mtn_reference(app_under_test, admin_client):
    from drugshop.payments import ledger

    _airtel_config(app_under_test, verify=False)
    with app_under_test.app_context():
        ledger.create_pending(
            MTN_REF, "mtn-key", 5000, "UGX", provider=providers.MTN
        )
    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": MTN_REF,
        },
    )

    assert response.status_code == 409
    assert response.get_json()["provider"] == "MTN"
    assert _stock(admin_client, pid) == before


def test_airtel_manual_entry_requires_reference(
    app_under_test, admin_client
):
    _airtel_config(app_under_test, verify=True)
    pid = _stocked_product(admin_client)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 400
    assert "reference" in response.get_json()["error"].lower()


def test_airtel_manual_entry_records_without_gateway(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.sales.routes as sales_routes
    from drugshop.db import q_one

    _airtel_config(app_under_test, verify=True)

    def fail(*args, **kwargs):
        raise AssertionError("manual Airtel entry must not call the gateway")

    monkeypatch.setattr(sales_routes, "verify_reference", fail)
    pid = _stocked_product(admin_client)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": "airtel-manual-1",
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 201
    row = q_one("SELECT * FROM momo_collections WHERE reference='AIRTEL-MANUAL-1'")
    assert row["provider"] == "AIRTEL"
    assert row["source"] == "MANUAL"
    assert row["status"] == "CONSUMED"
    assert row["currency"] == "UGX"


def test_airtel_manual_entry_cannot_consume_pending_api_payment(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    pid = _stocked_product(admin_client, price=5000)
    before = _stock(admin_client, pid)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 402
    assert _stock(admin_client, pid) == before


def test_airtel_manual_entry_reports_paid_amount_on_mismatch(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test, verify=True)
    reference, fake = _airtel_pending(admin_client, monkeypatch)
    fake.status = {"status": "SUCCESSFUL", "amount": "5000", "currency": "UGX"}
    confirmed = admin_client.get(f"/api/payments/status/AIRTEL/{reference}")
    assert confirmed.status_code == 200
    pid = _stocked_product(admin_client, price=4000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
            "is_manual_entry": True,
        },
    )

    assert response.status_code == 402
    body = response.get_json()
    assert body["paid_amount"] == 5000
    assert body["paid_currency"] == "UGX"


def test_airtel_service_fails_closed_without_credentials(app_under_test):
    import drugshop.payments.service as svc

    app_under_test.config.update(
        AIRTEL_CLIENT_ID="",
        AIRTEL_CLIENT_SECRET="",
        AIRTEL_VERIFY_SALES=True,
    )
    with app_under_test.app_context():
        with pytest.raises(svc.PaymentError) as exc:
            svc.verify_reference(AIRTEL_REF, 5000, provider="AIRTEL_MOMO")
    assert exc.value.status == 503
    assert "AIRTEL_CLIENT_ID" in str(exc.value)


def test_airtel_service_reuses_client_and_accepts_string_amounts(
    app_under_test, monkeypatch
):
    import drugshop.payments.service as svc

    _airtel_config(app_under_test, verify=True)
    built = _install_verifier(monkeypatch, amount="5000.00")
    with app_under_test.app_context():
        svc.verify_reference(AIRTEL_REF, 5000, provider="AIRTEL")
        svc.verify_reference(AIRTEL_REF, 5000, provider="AIRTEL_MOMO")
    assert len(built) == 1


def test_airtel_service_uses_ledger_amount_when_status_omits_it(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.payments.service as svc

    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch, amount=None, currency=None)
    with app_under_test.app_context():
        result = svc.verify_reference(reference, 5000, provider="AIRTEL")
    assert result["status"] == "SUCCESSFUL"


def test_airtel_service_checks_sale_total_when_status_omits_amount(
    app_under_test, admin_client, monkeypatch
):
    import drugshop.payments.service as svc

    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch, amount=None, currency=None)
    with app_under_test.app_context():
        with pytest.raises(svc.PaymentError, match="totals"):
            svc.verify_reference(reference, 4000, provider="AIRTEL")


def test_airtel_service_fails_closed_without_status_or_ledger_amount(
    app_under_test, monkeypatch
):
    import drugshop.payments.service as svc

    _airtel_config(app_under_test, verify=True)
    _install_verifier(monkeypatch, amount=None, currency=None)
    with app_under_test.app_context():
        with pytest.raises(svc.PaymentError, match="valid amount"):
            svc.verify_reference(AIRTEL_REF, 5000, provider="AIRTEL")


def test_airtel_service_rejects_zero_reported_amount(
    app_under_test, monkeypatch
):
    import drugshop.payments.service as svc

    _airtel_config(app_under_test, verify=True)
    _install_verifier(monkeypatch, amount="0")
    with app_under_test.app_context():
        with pytest.raises(svc.PaymentError, match="zero"):
            svc.verify_reference(AIRTEL_REF, 5000, provider="AIRTEL")


def test_airtel_verification_can_be_disabled_for_rollout(
    app_under_test, admin_client, monkeypatch
):
    from drugshop.db import q_one

    _airtel_config(app_under_test, verify=False)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    pid = _stocked_product(admin_client, price=5000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
            "momo_ref": reference,
        },
    )

    assert response.status_code == 201
    row = q_one("SELECT * FROM momo_collections WHERE reference=?", (reference,))
    assert row["status"] == "CONSUMED"


def test_airtel_rollout_allows_sale_without_reference(app_under_test, admin_client):
    _airtel_config(app_under_test, verify=False)
    pid = _stocked_product(admin_client, price=5000)

    response = admin_client.post(
        "/api/sales",
        json={
            "product_id": pid,
            "qty": 1,
            "payment_method": "AIRTEL_MOMO",
        },
    )

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["momo_ref"] == ""


def test_airtel_replay_returns_original_receipt(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test, verify=True)
    reference, _ = _airtel_pending(admin_client, monkeypatch)
    _install_verifier(monkeypatch)
    pid = _stocked_product(admin_client, price=5000)
    payload = {
        "product_id": pid,
        "qty": 1,
        "payment_method": "AIRTEL_MOMO",
        "momo_ref": reference,
    }

    first = admin_client.post("/api/sales", json=payload)
    assert first.status_code == 201, first.get_json()
    receipt = first.get_json()["receipt_ref"]
    sale_id = first.get_json()["id"]

    replay = admin_client.post("/api/sales", json=payload)

    assert replay.status_code == 409
    body = replay.get_json()
    assert body["receipt_ref"] == receipt
    assert body["sale_id"] == sale_id


def test_airtel_status_uuid_is_required(app_under_test, admin_client):
    _airtel_config(app_under_test)
    response = admin_client.get("/api/payments/status/AIRTEL/not-a-uuid")
    assert response.status_code == 400


def test_airtel_collect_reference_is_always_uuid(
    app_under_test, admin_client, monkeypatch
):
    _airtel_config(app_under_test)
    _install_airtel(monkeypatch)
    response = admin_client.post(
        "/api/payments/collect",
        json={
            "amount": 1000,
            "phone": "0701234567",
            "provider": "AIRTEL",
            "reference_id": "manual-text",
        },
    )
    assert response.status_code == 400
    assert "UUID" in response.get_json()["error"]
