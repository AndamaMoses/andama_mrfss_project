"""Airtel Money OpenAPI collections client (Uganda).

The client mirrors :mod:`drugshop.payments.momo`:

* standard library only (``urllib``) so payments add no runtime dependency;
* an injectable transport, so tests never touch Airtel's servers;
* a cached OAuth2 bearer token, refreshed once on HTTP 401;
* collection requests written against ``/merchant/v1/payments/`` and status
  lookups against ``/standard/v1/payments/{transaction_id}``.

Airtel expects the subscriber MSISDN in national format *without* the country
code or leading zero (``0701234567`` becomes ``701234567``). MTN uses the
international ``256...`` form; the two helpers are intentionally separate.

Status codes are normalised to the same vocabulary as MTN so the ledger and sale
guard can stay provider-agnostic:

======  ===========
Airtel  Ledger
======  ===========
TS      SUCCESSFUL
TF/TIN  FAILED
TIP     PENDING
TA      UNKNOWN
TE      TIMEOUT
======  ===========
"""

from __future__ import annotations

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

DEFAULT_BASE_URL = "https://openapiuat.airtel.africa"
PRODUCTION_BASE_URL = "https://openapi.airtel.africa"

TOKEN_PATH = "/auth/oauth2/token"  # noqa: S105 - endpoint path, not a secret
COLLECTION_PATH = "/merchant/v1/payments/"
STATUS_PATH = "/standard/v1/payments"

DEFAULT_TIMEOUT = 20.0

STATUS_MAP = {
    "TS": "SUCCESSFUL",
    "SUCCESS": "SUCCESSFUL",
    "SUCCESSFUL": "SUCCESSFUL",
    "TF": "FAILED",
    "TIN": "FAILED",
    "FAILED": "FAILED",
    "REJECTED": "FAILED",
    "TIP": "PENDING",
    "PENDING": "PENDING",
    "TA": "UNKNOWN",
    "UNKNOWN": "UNKNOWN",
    "TE": "TIMEOUT",
    "EXPIRED": "TIMEOUT",
}

# Currencies whose smallest unit is the whole unit. Sending decimals for these
# is rejected by the gateway or, worse, collects a different amount.
ZERO_DECIMAL_CURRENCIES = frozenset(
    {"UGX", "RWF", "BIF", "DJF", "GNF", "KMF", "XAF", "XOF", "JPY", "KRW", "VND"}
)


class AirtelError(RuntimeError):
    """An Airtel Money API call failed (configuration, network, or HTTP error)."""

    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class AirtelSettings:
    """Airtel credentials and environment, resolved from app config or env."""

    client_id: str = ""
    client_secret: str = ""
    base_url: str = DEFAULT_BASE_URL
    currency: str = "UGX"
    country: str = "UG"
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_mapping(cls, values):
        def get(key, default=""):
            return values.get(key, default) or default

        try:
            timeout = float(get("AIRTEL_TIMEOUT", DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        if not math.isfinite(timeout) or timeout <= 0:
            timeout = DEFAULT_TIMEOUT

        base_url = str(get("AIRTEL_BASE_URL", DEFAULT_BASE_URL)).strip()
        currency = str(get("AIRTEL_CURRENCY", "UGX")).strip().upper() or "UGX"
        country = str(get("AIRTEL_COUNTRY", "UG")).strip().upper() or "UG"
        return cls(
            client_id=str(get("AIRTEL_CLIENT_ID")).strip(),
            client_secret=str(get("AIRTEL_CLIENT_SECRET")).strip(),
            base_url=base_url or DEFAULT_BASE_URL,
            currency=currency,
            country=country,
            timeout=timeout,
        )

    @classmethod
    def from_env(cls):
        return cls.from_mapping(os.environ)

    @property
    def resolved_base_url(self):
        return (self.base_url or DEFAULT_BASE_URL).rstrip("/")

    @property
    def environment(self):
        """Human-readable environment derived from the configured host."""
        return "sandbox" if "uat" in self.resolved_base_url.lower() else "production"

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    @property
    def status_payload(self):
        """Credential-free summary safe to log or return from an API."""
        return {
            "configured": self.configured,
            "environment": self.environment,
            "base_url": self.resolved_base_url,
            "currency": self.currency,
            "country": self.country,
            "has_client_id": bool(self.client_id),
            "has_client_secret": bool(self.client_secret),
        }


def normalize_msisdn(phone, country_code="256"):
    """Return Airtel's national MSISDN form, e.g. ``0701234567`` -> ``701234567``.

    Airtel rejects the international ``256...`` form used by MTN. Accepts local,
    international, ``00256`` and the common ``2560...`` handset form.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        raise ValueError("phone number is required")
    if digits.startswith(country_code + "0"):
        digits = digits[len(country_code) + 1:]
    elif digits.startswith(country_code):
        digits = digits[len(country_code):]
    elif digits.startswith("0"):
        digits = digits[1:]
    if country_code == "256" and not re.fullmatch(r"[27]\d{8}", digits):
        raise ValueError(
            "phone number must be a Ugandan mobile number, e.g. 0701234567 "
            "or +256701234567"
        )
    if not (7 <= len(digits) <= 15):
        raise ValueError("phone number is invalid")
    return digits


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


def _format_amount(value, currency):
    """Return a JSON number Airtel accepts for ``currency``."""
    code = str(currency or "").upper()
    if code in ZERO_DECIMAL_CURRENCIES:
        if not float(value).is_integer():
            raise ValueError(f"{code} amounts must be whole numbers")
        return int(value)
    return round(float(value), 2)


def _urllib_transport(method, url, headers, body, timeout):
    """Default transport: return ``(status, headers, text)`` without raising on 4xx/5xx."""
    try:
        req = urlrequest.Request(  # noqa: S310
            url, data=body, headers=headers, method=method
        )
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed Airtel hosts
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
        raise AirtelError(f"cannot reach Airtel Money at {url}: {reason}") from exc
    except ValueError as exc:
        raise AirtelError(f"invalid Airtel Money URL {url}: {exc}") from exc


def _decode(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return {"raw": text}


def _error_detail(payload):
    if not isinstance(payload, dict):
        return ""
    status = payload.get("status")
    if isinstance(status, dict):
        detail = status.get("message") or status.get("code")
        if detail:
            return str(detail)
    return str(
        payload.get("message") or payload.get("error") or payload.get("raw") or ""
    )


def _http_error(action, status, payload):
    detail = _error_detail(payload)
    suffix = f" - {detail}" if detail else ""
    return AirtelError(
        f"{action} failed (HTTP {status}){suffix}", status=status, payload=payload
    )


def _business_status(payload):
    """Map an Airtel business status code to an HTTP-like error status."""
    status = payload.get("status") if isinstance(payload, dict) else None
    code = ""
    if isinstance(status, dict):
        code = str(status.get("code") or "").strip()
    try:
        number = int(code)
    except (TypeError, ValueError):
        number = 0
    if 400 <= number < 500:
        return number
    if number >= 500:
        return 502
    return 400


class AirtelClient:
    """Minimal Airtel Money collections client.

    ``transport`` is injectable so tests never touch the network. It must have
    the signature ``(method, url, headers, body, timeout) -> (status, headers, text)``.
    """

    def __init__(self, settings=None, transport=None):
        self.settings = settings or AirtelSettings.from_env()
        self._transport = transport or _urllib_transport
        self._token = ""
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    # -- low level ---------------------------------------------------------
    def _headers(self, extra=None, authorized=False):
        if authorized and not self.settings.configured:
            raise AirtelError(
                "AIRTEL_CLIENT_ID / AIRTEL_CLIENT_SECRET are not set - add them "
                "to .env (see .env.example)"
            )
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
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
            raise _http_error(f"Airtel {method} {path}", status, data)
        return status, data

    def _send_authorized(self, method, path, body=None, extra=None):
        """Send with a bearer token, refreshing it once if Airtel returns 401."""
        extra = dict(extra or {})
        for attempt in (0, 1):
            headers = self._headers(extra, authorized=True)
            try:
                return self._send(method, path, body=body, headers=headers)
            except AirtelError as exc:
                if exc.status == 401 and attempt == 0:
                    self.access_token(force=True)
                    continue
                raise
        raise AssertionError("unreachable")  # pragma: no cover

    # -- auth --------------------------------------------------------------
    def access_token(self, force=False):
        """Return a cached bearer token, refreshing 60s before expiry."""
        if not force and self._token and time.monotonic() < self._token_expires_at:
            return self._token
        with self._token_lock:
            if not force and self._token and time.monotonic() < self._token_expires_at:
                return self._token
            return self._fetch_token()

    def _fetch_token(self):
        if not self.settings.configured:
            raise AirtelError(
                "AIRTEL_CLIENT_ID / AIRTEL_CLIENT_SECRET are not set - add them "
                "to .env (see .env.example)"
            )
        body = {
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "grant_type": "client_credentials",
        }
        _status, data = self._send(
            "POST",
            TOKEN_PATH,
            body=body,
            headers={"Accept": "*/*", "Content-Type": "application/json"},
        )
        token = (data or {}).get("access_token", "")
        if not token:
            raise AirtelError("Airtel token response did not include an access_token")
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
        external_id="",
        reference_id=None,
        payer_message="",
        payee_note="",
        currency=None,
    ):
        """Ask a customer to approve an Airtel collection on their phone.

        ``reference_id`` is the transaction id used by the status endpoint. It
        is generated here when omitted and must be a UUID, matching the ledger's
        canonical reference format. ``external_id`` is sent as Airtel's merchant
        ``reference``; it is not the status lookup key.
        """
        value = _validate_amount(amount)
        if reference_id is None:
            reference_id = str(uuid.uuid4())
        else:
            try:
                reference_id = str(uuid.UUID(str(reference_id)))
            except (TypeError, ValueError) as exc:
                raise ValueError("reference_id must be a valid UUID") from exc

        code = str(currency or self.settings.currency or "").strip().upper()
        if len(code) != 3:
            raise ValueError("currency must be a three-letter ISO code")
        country = str(self.settings.country or "UG").strip().upper()
        if len(country) != 2:
            raise ValueError("country must be a two-letter ISO code")

        merchant_reference = str(external_id or "").strip() or reference_id
        body = {
            "reference": merchant_reference[:128],
            "subscriber": {
                "country": country,
                "currency": code,
                "msisdn": normalize_msisdn(phone),
            },
            "transaction": {
                "amount": _format_amount(value, code),
                "country": country,
                "currency": code,
                "id": reference_id,
            },
        }
        extra_headers = {"X-Country": country, "X-Currency": code}
        _status, data = self._send_authorized(
            "POST", COLLECTION_PATH, body=body, extra=extra_headers
        )

        data = data or {}
        info = data.get("status") if isinstance(data.get("status"), dict) else {}
        success = info.get("success")
        code_text = str(info.get("code") or "").strip()
        if success is False or (code_text and code_text not in {"200", "201", "0"}):
            detail = _error_detail(data) or "Airtel rejected the collection request"
            raise AirtelError(
                f"Airtel collection failed - {detail}",
                status=_business_status(data),
                payload=data,
            )
        return {
            "reference_id": reference_id,
            "status": "PENDING",
            "amount": value,
            "currency": code,
            "phone": body["subscriber"]["msisdn"],
            "external_id": merchant_reference,
        }

    def request_status(self, reference_id):
        if not reference_id:
            raise ValueError("reference_id is required")
        try:
            reference_id = str(uuid.UUID(str(reference_id)))
        except (TypeError, ValueError) as exc:
            raise ValueError("reference_id must be a valid UUID") from exc

        _status, data = self._send_authorized(
            "GET",
            f"{STATUS_PATH}/{reference_id}",
            extra={
                "X-Country": self.settings.country,
                "X-Currency": self.settings.currency,
            },
        )
        data = data or {}
        data_obj = data.get("data") if isinstance(data.get("data"), dict) else {}
        transaction = (
            data_obj.get("transaction")
            if isinstance(data_obj.get("transaction"), dict)
            else {}
        )
        if not transaction and isinstance(data.get("transaction"), dict):
            transaction = data["transaction"]

        raw_status = str(transaction.get("status") or "").strip().upper()
        if not raw_status and isinstance(data.get("status"), str):
            raw_status = str(data.get("status") or "").strip().upper()
        status = STATUS_MAP.get(raw_status, "UNKNOWN")

        amount = transaction.get("amount")
        if amount is None:
            amount = data_obj.get("amount")
        if amount is None:
            amount = data.get("amount")

        currency = (
            transaction.get("currency")
            or data_obj.get("currency")
            or data.get("currency")
        )
        if not currency:
            subscriber = data_obj.get("subscriber") or data.get("subscriber") or {}
            if isinstance(subscriber, dict):
                currency = subscriber.get("currency")

        financial_txn_id = (
            transaction.get("airtel_money_id")
            or transaction.get("airtel_money_id".replace("_", ""))
            or data_obj.get("airtel_money_id")
            or ""
        )
        return {
            "status": status,
            "amount": amount,
            "currency": currency,
            "financialTransactionId": financial_txn_id,
            "raw_status": raw_status,
            "raw": data,
        }
