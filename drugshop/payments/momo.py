"""MTN Mobile Money (MoMo) Collections client.

MTN's developer portal (https://momodeveloper.mtn.com) issues one
``Ocp-Apim-Subscription-Key`` per product subscription. The key alone cannot
move money: MTN also requires an API user + API key created *in the target
environment* (sandbox or a country production environment), which is exchanged
for a short-lived bearer token.

Typical setup::

    # .env already holds MOMO_SUBSCRIPTION_KEY
    flask --app run momo provision --save
    flask --app run momo status --check

The client uses only the standard library so no new runtime dependency (and
no extra supply-chain surface) is added for payments.

Hosts
-----
* Sandbox:    https://sandbox.momodeveloper.mtn.com
* Production: https://proxy.momoapi.mtn.com

Both are configurable through ``MOMO_BASE_URL`` because MTN occasionally moves
gateways per country.
"""

from __future__ import annotations

import base64
import http.client
import json
import math
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from urllib import error as urlerror
from urllib import request as urlrequest

SANDBOX_BASE_URL = "https://sandbox.momodeveloper.mtn.com"
PRODUCTION_BASE_URL = "https://proxy.momoapi.mtn.com"

TOKEN_PATH = "/collection/token/"  # noqa: S105 - endpoint path, not a secret
REQUEST_TO_PAY_PATH = "/collection/v1_0/requesttopay"
ACCOUNT_BALANCE_PATH = "/collection/v1_0/account/balance"
API_USER_PATH = "/v1_0/apiuser"

DEFAULT_TIMEOUT = 20.0


class MomoError(RuntimeError):
    """A MoMo API call failed (configuration, network, or HTTP error)."""

    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class MomoSettings:
    """MoMo credentials and environment, resolved from app config or env."""

    subscription_key: str = ""
    api_user: str = ""
    api_key: str = ""
    environment: str = "sandbox"
    base_url: str = ""
    currency: str = "UGX"
    callback_url: str = ""
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_mapping(cls, values):
        def get(key, default=""):
            return values.get(key, default) or default

        try:
            timeout = float(get("MOMO_TIMEOUT", DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        if not math.isfinite(timeout) or timeout <= 0:
            timeout = DEFAULT_TIMEOUT

        environment = str(get("MOMO_TARGET_ENVIRONMENT", "sandbox")).strip()
        environment = environment or "sandbox"
        # MTN's sandbox accepts EUR only; production environments use their
        # local currency (UGX for mtnuganda).
        currency = str(get("MOMO_CURRENCY")).strip().upper()
        currency = currency or ("EUR" if environment.lower() == "sandbox" else "UGX")
        return cls(
            subscription_key=str(get("MOMO_SUBSCRIPTION_KEY")).strip(),
            api_user=str(get("MOMO_API_USER")).strip(),
            api_key=str(get("MOMO_API_KEY")).strip(),
            environment=environment,
            base_url=str(get("MOMO_BASE_URL")).strip(),
            currency=currency,
            callback_url=str(get("MOMO_CALLBACK_URL")).strip(),
            timeout=timeout,
        )

    @classmethod
    def from_env(cls):
        return cls.from_mapping(os.environ)

    @property
    def resolved_base_url(self):
        if self.base_url:
            return self.base_url.rstrip("/")
        if self.environment.lower() == "sandbox":
            return SANDBOX_BASE_URL
        return PRODUCTION_BASE_URL

    @property
    def configured(self):
        """True when the three credentials needed for Collections are present."""
        return bool(self.subscription_key and self.api_user and self.api_key)

    @property
    def status_payload(self):
        """Credential-free summary safe to log or return from an API."""
        return {
            "configured": self.configured,
            "environment": self.environment,
            "base_url": self.resolved_base_url,
            "currency": self.currency,
            "has_subscription_key": bool(self.subscription_key),
            "has_api_user": bool(self.api_user),
            "has_api_key": bool(self.api_key),
        }


def normalize_msisdn(phone, country_code="256"):
    """Return an MSISDN in international digits, e.g. ``0772...`` -> ``256772...``.

    Accepts local (``0772 123 456``), international (``+256 772...``), and
    already-normalised (``256772...``) forms. Raises ``ValueError`` for input
    without digits.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        raise ValueError("phone number is required")
    if digits.startswith(country_code + "0"):
        # Common handset form: 2560772123456 -> 256772123456.
        digits = country_code + digits[len(country_code) + 1:]
    if digits.startswith(country_code):
        normalized = digits
    elif digits.startswith("0"):
        normalized = country_code + digits[1:]
    elif len(digits) == 9:
        normalized = country_code + digits
    else:
        normalized = digits
    if country_code == "256" and not (
        len(normalized) == 12 and normalized.startswith("256")
    ):
        raise ValueError(
            "phone number must be a Ugandan MSISDN, e.g. 0772123456 or +256772123456"
        )
    if not normalized.startswith(country_code):
        raise ValueError(f"phone number must use country code {country_code}")
    if not (10 <= len(normalized) <= 15):
        raise ValueError("phone number is invalid")
    return normalized


def _validate_amount(amount):
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("amount must be a number") from exc
    if not math.isfinite(value):
        raise ValueError("amount must be a finite number")
    if value <= 0:
        raise ValueError("amount must be greater than zero")
    return value


# Currencies whose smallest unit is the whole unit. Sending decimals for these
# makes MTN reject the request, or worse, creates a mismatch with the sale total.
ZERO_DECIMAL_CURRENCIES = frozenset(
    {"UGX", "RWF", "BIF", "DJF", "GNF", "KMF", "XAF", "XOF", "JPY", "KRW", "VND"}
)


def _format_amount(value, currency):
    """Format an amount the way MTN expects for ``currency``.

    ``UGX`` and other zero-decimal currencies must be whole numbers. A
    fractional UGX total is a data error, not something to round silently:
    rounding could collect a different amount than the receipt says.
    """
    code = str(currency or "").upper()
    if code in ZERO_DECIMAL_CURRENCIES:
        if not float(value).is_integer():
            raise ValueError(f"{code} amounts must be whole numbers")
        return str(int(value))
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    if text in {"", "0", "-0"}:
        raise ValueError("amount is too small for the selected currency")
    return text


def _urllib_transport(method, url, headers, body, timeout):
    """Default transport: return ``(status, headers, text)`` without raising on 4xx/5xx."""
    try:
        req = urlrequest.Request(  # noqa: S310
            url, data=body, headers=headers, method=method
        )
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed MTN hosts
            return (
                resp.status,
                {k.lower(): v for k, v in resp.headers.items()},
                resp.read().decode("utf-8", "replace"),
            )
    except urlerror.HTTPError as exc:
        return (
            exc.code,
            {k.lower(): v for k, v in exc.headers.items()},
            exc.read().decode("utf-8", "replace"),
        )
    except (urlerror.URLError, OSError, http.client.HTTPException) as exc:
        reason = getattr(exc, "reason", exc)
        raise MomoError(f"cannot reach MTN MoMo at {url}: {reason}") from exc
    except ValueError as exc:
        # urlopen raises ValueError for an unsupported scheme or a malformed
        # URL (for example MOMO_BASE_URL=foo). Surface it as a config error,
        # not an unhandled traceback in the health endpoint or CLI.
        raise MomoError(f"invalid MTN MoMo URL {url}: {exc}") from exc


def _decode(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return {"raw": text}


def _http_error(action, status, payload):
    detail = ""
    if isinstance(payload, dict):
        detail = (
            payload.get("message") or payload.get("error") or payload.get("raw") or ""
        )
    suffix = f" - {detail}" if detail else ""
    return MomoError(
        f"{action} failed (HTTP {status}){suffix}", status=status, payload=payload
    )


class MomoClient:
    """Minimal Collections client: token, request-to-pay, status, balance.

    ``transport`` is injectable so tests never touch the network. It must have
    the signature ``(method, url, headers, body, timeout) -> (status, headers, text)``.
    """

    def __init__(self, settings=None, transport=None):
        self.settings = settings or MomoSettings.from_env()
        self._transport = transport or _urllib_transport
        self._token = ""
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    # -- low level ---------------------------------------------------------
    def _headers(self, extra=None, authorized=False):
        if not self.settings.subscription_key:
            raise MomoError(
                "MOMO_SUBSCRIPTION_KEY is not set - add it to .env (see .env.example)"
            )
        headers = {
            "Ocp-Apim-Subscription-Key": self.settings.subscription_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if authorized:
            headers["Authorization"] = f"Bearer {self.access_token()}"
        if extra:
            headers.update(extra)
        return headers

    def _send(self, method, path, body=None, headers=None):
        url = self.settings.resolved_base_url + path
        payload = None if body is None else json.dumps(body).encode("utf-8")
        status, _resp_headers, text = self._transport(
            method, url, headers or {}, payload, self.settings.timeout
        )
        data = _decode(text)
        if status >= 400:
            raise _http_error(f"MoMo {method} {path}", status, data)
        return status, data

    def _send_authorized(self, method, path, body=None, extra=None):
        """Send with a bearer token, refreshing it once if MTN returns 401.

        Tokens are cached for an hour, but a rotated API key or an early
        revocation would otherwise fail every poll until the process restarts.
        """
        extra = dict(extra or {})
        for attempt in (0, 1):
            headers = self._headers(extra, authorized=True)
            try:
                return self._send(method, path, body=body, headers=headers)
            except MomoError as exc:
                if exc.status == 401 and attempt == 0:
                    self.access_token(force=True)
                    continue
                raise
        raise AssertionError("unreachable")  # pragma: no cover

    # -- auth --------------------------------------------------------------
    def access_token(self, force=False):
        """Return a cached Collections bearer token, refreshing 60s before expiry."""
        if not force and self._token and time.monotonic() < self._token_expires_at:
            return self._token
        # Serialize the fetch so concurrent POS polls do not all hit the token
        # endpoint when the cache is cold or just expired.
        with self._token_lock:
            if not force and self._token and time.monotonic() < self._token_expires_at:
                return self._token
            return self._fetch_token()

    def _fetch_token(self):
        if not (self.settings.api_user and self.settings.api_key):
            raise MomoError(
                "MOMO_API_USER / MOMO_API_KEY are not set - run "
                "`flask --app run momo provision --save` first"
            )
        basic = base64.b64encode(
            f"{self.settings.api_user}:{self.settings.api_key}".encode("utf-8")
        ).decode("ascii")
        headers = self._headers({"Authorization": f"Basic {basic}"})
        _status, data = self._send("POST", TOKEN_PATH, headers=headers)
        token = (data or {}).get("access_token", "")
        if not token:
            raise MomoError("MoMo token response did not include an access_token")
        try:
            expires_in = int((data or {}).get("expires_in", 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        if expires_in <= 0:
            expires_in = 3600
        self._token = token
        self._token_expires_at = time.monotonic() + max(60, expires_in - 60)
        return token

    # -- collections -------------------------------------------------------
    def request_to_pay(
        self,
        amount,
        phone,
        external_id,
        reference_id=None,
        payer_message="",
        payee_note="",
        currency=None,
    ):
        """Ask a customer to approve a collection on their phone (USSD push).

        Returns the reference id and the submitted body. The payment is
        asynchronous: poll :meth:`request_status` until ``SUCCESSFUL``,
        ``FAILED``, or ``REJECTED``.
        """
        value = _validate_amount(amount)
        if reference_id is None:
            reference_id = str(uuid.uuid4())
        else:
            try:
                # MTN requires a UUID in X-Reference-Id; fail fast with a 400
                # instead of forwarding a malformed id and returning a 502.
                reference_id = str(uuid.UUID(str(reference_id)))
            except (TypeError, ValueError) as exc:
                raise ValueError("reference_id must be a valid UUID") from exc
        # MTN requires a non-empty externalId. Callers that only have a
        # reference id (for example a retried request) can omit it safely.
        external_id = str(external_id or "").strip() or reference_id
        code = str(currency or self.settings.currency or "").strip().upper()
        if len(code) != 3:
            raise ValueError("currency must be a three-letter ISO code")
        body = {
            "amount": _format_amount(value, code),
            "currency": code,
            "externalId": external_id,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": normalize_msisdn(phone),
            },
            "payerMessage": str(payer_message or "")[:160],
            "payeeNote": str(payee_note or "")[:160],
        }
        extra_headers = {
            "X-Reference-Id": reference_id,
            "X-Target-Environment": self.settings.environment,
        }
        if self.settings.callback_url:
            extra_headers["X-Callback-Url"] = self.settings.callback_url
        try:
            self._send_authorized(
                "POST", REQUEST_TO_PAY_PATH, body=body, extra=extra_headers
            )
        except MomoError as exc:
            if "currency not supported" in str(exc).lower():
                raise MomoError(
                    f"{exc}. MTN's sandbox accepts EUR only; set MOMO_CURRENCY=EUR "
                    "for sandbox demos (production environments use their own "
                    "currency, e.g. UGX for mtnuganda).",
                    status=exc.status,
                    payload=exc.payload,
                ) from exc
            raise
        return {"reference_id": reference_id, **body}

    def request_status(self, reference_id):
        if not reference_id:
            raise ValueError("reference_id is required")
        try:
            reference_id = str(uuid.UUID(str(reference_id)))
        except (TypeError, ValueError) as exc:
            raise ValueError("reference_id must be a valid UUID") from exc
        _status, data = self._send_authorized(
            "GET",
            f"{REQUEST_TO_PAY_PATH}/{reference_id}",
            extra={"X-Target-Environment": self.settings.environment},
        )
        return data or {}

    def account_balance(self):
        _status, data = self._send_authorized(
            "GET",
            ACCOUNT_BALANCE_PATH,
            extra={"X-Target-Environment": self.settings.environment},
        )
        return data or {}


def _api_user_body(callback_host):
    host = str(callback_host or "localhost").strip()
    host = re.sub(r"^https?://", "", host).split("/")[0]
    return {"providerCallbackHost": host or "localhost"}


def create_api_user(settings, transport=None, callback_host="localhost"):
    """Create an API user in the configured environment and return its UUID.

    Sandbox: ``POST /v1_0/apiuser`` with the subscription key and an
    ``X-Reference-Id`` that becomes the API user id.
    """
    if not settings.subscription_key:
        raise MomoError("MOMO_SUBSCRIPTION_KEY is not set - add it to .env")
    send = transport or _urllib_transport
    api_user = str(uuid.uuid4())
    headers = {
        "Ocp-Apim-Subscription-Key": settings.subscription_key,
        "X-Reference-Id": api_user,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = json.dumps(_api_user_body(callback_host)).encode("utf-8")
    url = settings.resolved_base_url + API_USER_PATH
    status, _headers, text = send("POST", url, headers, body, settings.timeout)
    if status not in (200, 201):
        raise _http_error("MoMo create API user", status, _decode(text))
    return api_user


def create_api_key(settings, api_user, transport=None):
    """Create (or rotate) the API key for ``api_user`` and return it."""
    if not settings.subscription_key:
        raise MomoError("MOMO_SUBSCRIPTION_KEY is not set - add it to .env")
    if not api_user:
        raise MomoError("API user id is required")
    try:
        api_user = str(uuid.UUID(str(api_user)))
    except (TypeError, ValueError) as exc:
        raise MomoError("API user id must be a valid UUID") from exc
    send = transport or _urllib_transport
    headers = {
        "Ocp-Apim-Subscription-Key": settings.subscription_key,
        "Accept": "application/json",
    }
    url = f"{settings.resolved_base_url}{API_USER_PATH}/{api_user}/apikey"
    status, _headers, text = send("POST", url, headers, None, settings.timeout)
    data = _decode(text) or {}
    if status not in (200, 201):
        raise _http_error("MoMo create API key", status, data)
    api_key = data.get("apiKey", "")
    if not api_key:
        raise MomoError("MoMo API key response did not include apiKey")
    return api_key


def provision(settings, transport=None, callback_host="localhost"):
    """Create an API user + key and return ``(api_user, api_key)``."""
    api_user = create_api_user(
        settings, transport=transport, callback_host=callback_host
    )
    api_key = create_api_key(settings, api_user, transport=transport)
    return api_user, api_key
