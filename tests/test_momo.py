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
    assert settings.currency == "UGX"


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
        "currency": "UGX",
        "externalId": "SALE-12",
        "payer": {"partyIdType": "MSISDN", "partyId": "256772123456"},
        "payerMessage": "Dawa",
        "payeeNote": "Counter",
    }


def test_request_status_reads_by_reference():
    transport = FakeTransport(
        [
            (200, {"access_token": "tok"}),
            (200, {"status": "SUCCESSFUL", "amount": "5000"}),
        ]
    )
    client = momo.MomoClient(_settings(), transport=transport)

    assert client.request_status("ref-1")["status"] == "SUCCESSFUL"
    assert transport.calls[1]["url"].endswith("/collection/v1_0/requesttopay/ref-1")


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
def test_momo_endpoints_require_admin(app_under_test, staff_client, client):
    assert client.get("/api/momo/health").status_code == 401
    assert staff_client.get("/api/momo/health").status_code == 403
    assert staff_client.post("/api/momo/collect", json={}).status_code == 403


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
        def access_token(self):
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
    import drugshop.payments.routes as routes

    class Fake:
        def request_to_pay(self, **kwargs):
            return {"reference_id": "ref-1", "amount": "5000"}

    monkeypatch.setattr(routes, "_client", lambda: Fake())
    response = admin_client.post(
        "/api/momo/collect", json={"amount": 5000, "phone": "0772123456"}
    )
    assert response.status_code == 202
    assert response.get_json()["reference_id"] == "ref-1"
