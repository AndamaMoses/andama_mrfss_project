"""Mobile-money endpoints used by the Sell/POS counter and operations checks.

MTN keeps its original ``/api/momo/*`` endpoints for compatibility. Phase 2
adds provider-aware ``/api/payments/*`` endpoints that dispatch to MTN or Airtel
through the same durable ledger and idempotency rules.

These routes never move money by themselves beyond asking the carrier to push a
collection prompt to the customer's phone; the customer still approves on their
handset. The final state is read from the status endpoint and recorded against
the sale by the operator.

The ledger in :mod:`drugshop.payments.ledger` is written *before* the gateway is
called. If the HTTP response is lost, the reference still exists and can be
polled or reconciled instead of becoming an orphaned customer charge.
"""

import hmac
import math
import sqlite3
import threading
import time
import uuid
from collections import deque

from flask import Blueprint, current_app, jsonify, request

from drugshop.auth.guards import current_user, login_required
from drugshop.payments import ledger, providers, service
from drugshop.payments.airtel import (
    AirtelClient,
    AirtelError,
    AirtelSettings,
)
from drugshop.payments.airtel import (
    normalize_msisdn as normalize_airtel_msisdn,
)
from drugshop.payments.errors import PaymentError
from drugshop.payments.momo import (
    MomoClient,
    MomoError,
    MomoSettings,
    normalize_msisdn,
)

bp = Blueprint("payments", __name__)
# MTN cannot send a session cookie. Keep the callback on its own always-on
# blueprint so it still works when the POS entitlement is absent.
callback_bp = Blueprint("payments_callback", __name__)

# One client per distinct configuration so the bearer token is reused across
# polls. The POS polls every few seconds; creating a client per request would
# fetch a fresh token every time and waste the carrier's rate limit.
_CLIENTS = {}
_AIRTEL_CLIENTS = {}
_CLIENTS_LOCK = threading.Lock()

# Simple per-user request throttle. This is deliberately in-process: the app is
# a single-instance desktop deployment, and the goal is to stop a double-click
# or stuck key from firing a burst of prompts, not to replace the carrier's own
# limits.
_RATE_LIMIT = {}
_RATE_LIMIT_LOCK = threading.Lock()
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 60.0

# Statuses that mean the request will not succeed without a new reference.
DEFINITIVE_FAILURE_STATUSES = frozenset({400, 401, 403, 404, 409, 422, 429})


def _settings():
    return MomoSettings.from_mapping(current_app.config)


def _airtel_settings():
    return AirtelSettings.from_mapping(current_app.config)


def _settings_for(provider):
    return _settings() if provider == providers.MTN else _airtel_settings()


def _client():
    settings = _settings()
    key = (
        settings.resolved_base_url,
        settings.subscription_key,
        settings.api_user,
        settings.api_key,
        settings.environment,
        settings.currency,
        settings.callback_url,
        settings.timeout,
    )
    with _CLIENTS_LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            client = MomoClient(settings)
            _CLIENTS[key] = client
    return client


def _airtel_client():
    settings = _airtel_settings()
    key = (
        settings.resolved_base_url,
        settings.client_id,
        settings.client_secret,
        settings.currency,
        settings.country,
        settings.timeout,
    )
    with _CLIENTS_LOCK:
        client = _AIRTEL_CLIENTS.get(key)
        if client is None:
            client = AirtelClient(settings)
            _AIRTEL_CLIENTS[key] = client
    return client


def _client_for(provider):
    return _client() if provider == providers.MTN else _airtel_client()


def _upstream_status(exc):
    """Map a carrier 4xx to the same client status; hide auth/server errors as 502."""
    return exc.status if exc.status in {400, 404, 409, 422, 429} else 502


def reset_rate_limits():
    """Clear the in-process throttle. Tests call this between cases."""
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT.clear()


def _rate_limited(user_id):
    now = time.monotonic()
    key = str(user_id or "anonymous")
    with _RATE_LIMIT_LOCK:
        hits = deque(
            stamp
            for stamp in _RATE_LIMIT.get(key, ())
            if now - stamp < RATE_LIMIT_WINDOW
        )
        if len(hits) >= RATE_LIMIT_MAX:
            _RATE_LIMIT[key] = hits
            return True
        hits.append(now)
        _RATE_LIMIT[key] = hits
    return False


def _positive_amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("amount is required and must be a number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError("amount must be greater than zero")
    return number


def _phone(value, provider=providers.MTN):
    try:
        if provider == providers.MTN:
            return normalize_msisdn(value)
        return normalize_airtel_msisdn(value)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _idempotency_key(data, external_id):
    key = str(data.get("idempotency_key") or "").strip()
    if not key:
        key = str(external_id or "").strip()
    if not key:
        key = f"POS-{uuid.uuid4().hex}"
    return key[:128]


def _provider_label(provider):
    return providers.PROVIDER_LABELS.get(provider, provider)


def _row_provider(row):
    return str((row or {}).get("provider") or providers.MTN).upper()


def _provider_mismatch_response(row, provider):
    row_provider = _row_provider(row)
    if row is None or row_provider == provider:
        return None
    return (
        jsonify(
            {
                "error": "This mobile-money reference belongs to "
                f"{_provider_label(row_provider)}, not {_provider_label(provider)}",
                "provider": row_provider,
            }
        ),
        409,
    )


def _existing_payload(row, provider=None):
    """Return the same reference for a retried request, or explain why not."""
    status = str(row.get("status") or "").upper()
    row_provider = _row_provider(row)
    payload = {
        "reference_id": row.get("reference", ""),
        "status": status,
        "amount": row.get("amount"),
        "currency": row.get("currency", ""),
        "phone": row.get("phone", ""),
        "external_id": row.get("external_id", ""),
        "idempotency_key": row.get("idempotency_key", ""),
        "provider": row_provider,
        "payment_method": providers.PROVIDER_TO_METHOD.get(row_provider, ""),
        "reused": True,
    }
    mismatch = _provider_mismatch_response(row, provider) if provider else None
    if mismatch:
        return mismatch
    if status in {"CONSUMED", "VOIDED"}:
        return jsonify(
            {
                **payload,
                "sale_id": row.get("sale_id"),
                "receipt_ref": row.get("sale_receipt_ref", ""),
                "error": "This mobile-money reference is already on a sale",
            }
        ), 409
    if status in {"FAILED", "REJECTED", "TIMEOUT"}:
        return jsonify(
            {
                **payload,
                "error": f"Payment request is {status}; start a new request",
            }
        ), 409
    return jsonify(payload), 202


def _collect(provider, data, me, key_prefix=""):
    """Shared collection flow for MTN and Airtel."""
    provider = providers.normalize_provider(provider)
    data = data or {}
    try:
        amount = _positive_amount(data.get("amount"))
        phone = _phone(data.get("phone") or data.get("payer"), provider)
    except ValueError as exc:
        return jsonify({"error": str(exc), "provider": provider}), 400

    settings = _settings_for(provider)
    if not settings.configured:
        return jsonify(
            {
                "error": f"{_provider_label(provider)} is not configured on this terminal",
                "provider": provider,
            }
        ), 503

    external_id = str(data.get("external_id") or data.get("sale_id") or "").strip()
    if not external_id:
        external_id = f"POS-{uuid.uuid4().hex[:12]}"
    key = _idempotency_key(data, external_id)
    if key_prefix:
        key = f"{key_prefix}{key}"[:128]

    # A retried request must return the original reference, not send a second
    # prompt. Match the idempotency key first, then the external id so a client
    # that only remembers its sale id still converges.
    existing = ledger.get_by_idempotency(key) or ledger.get_by_external_id(
        external_id, provider=provider
    )
    if existing:
        return _existing_payload(existing, provider)

    reference = str(data.get("reference_id") or "").strip() or str(uuid.uuid4())
    try:
        reference = ledger.canonical_reference(reference)
    except ValueError as exc:
        return jsonify({"error": str(exc), "provider": provider}), 400
    if not ledger.is_uuid(reference):
        return jsonify(
            {
                "error": "reference_id must be the UUID returned by the payment request",
                "provider": provider,
            }
        ), 400
    existing = ledger.get_collection(reference)
    if existing:
        return _existing_payload(existing, provider)

    try:
        ledger.create_pending(
            reference,
            key,
            amount,
            settings.currency,
            phone=phone,
            external_id=external_id,
            actor=me.get("username", ""),
            provider=provider,
        )
    except sqlite3.IntegrityError:
        # Two clicks raced past the lookup. Return the winner's reference.
        existing = ledger.get_by_idempotency(key) or ledger.get_by_external_id(
            external_id, provider=provider
        )
        if existing:
            return _existing_payload(existing, provider)
        return jsonify(
            {
                "error": "This mobile-money reference already exists",
                "provider": provider,
            }
        ), 409

    ledger.record_event(
        None,
        reference,
        "REQUEST",
        actor=me.get("username", ""),
        detail=(
            f"provider={provider} amount={amount} "
            f"currency={settings.currency} phone={phone}"
        ),
    )

    try:
        client = _client_for(provider)
        result = client.request_to_pay(
            amount=amount,
            phone=phone,
            external_id=external_id,
            reference_id=reference,
            payer_message=data.get("payer_message") or "",
            payee_note=data.get("payee_note") or "",
        )
    except ValueError as exc:
        ledger.mark_failed(
            reference, str(exc), actor=me.get("username", ""), provider=provider
        )
        return jsonify(
            {"error": str(exc), "reference_id": reference, "provider": provider}
        ), 400
    except (MomoError, AirtelError) as exc:
        if exc.status in DEFINITIVE_FAILURE_STATUSES:
            ledger.mark_failed(
                reference, str(exc), actor=me.get("username", ""), provider=provider
            )
            return jsonify(
                {
                    "error": str(exc),
                    "momo_status": exc.status,
                    "reference_id": reference,
                    "status": "FAILED",
                    "provider": provider,
                }
            ), _upstream_status(exc)
        # Network/5xx: the carrier may have accepted the prompt. Keep the
        # reference pollable and tell the client the outcome is not known yet.
        ledger.mark_unknown(
            reference, str(exc), actor=me.get("username", ""), provider=provider
        )
        return jsonify(
            {
                "error": str(exc),
                "momo_status": exc.status,
                "reference_id": reference,
                "status": "UNKNOWN",
                "provider": provider,
            }
        ), _upstream_status(exc)

    result = dict(result or {})
    result["reference_id"] = reference
    result["status"] = "PENDING"
    result["idempotency_key"] = key
    result["provider"] = provider
    # create_pending already stored PENDING/amount/currency. Do not re-apply a
    # PENDING status here: a very fast callback could have set SUCCESSFUL
    # between the carrier response and this line.
    return jsonify(result), 202


def _status(provider, reference_id):
    """Shared status flow for MTN and Airtel."""
    provider = providers.normalize_provider(provider)
    try:
        reference = ledger.canonical_reference(reference_id)
    except ValueError as exc:
        return jsonify({"error": str(exc), "provider": provider}), 400
    if not ledger.is_uuid(reference):
        return jsonify(
            {
                "error": "reference must be the UUID returned by the payment request",
                "provider": provider,
            }
        ), 400

    row = ledger.get_collection(reference)
    mismatch = _provider_mismatch_response(row, provider)
    if mismatch:
        return mismatch

    settings = _settings_for(provider)
    if not settings.configured:
        return jsonify(
            {
                "error": f"{_provider_label(provider)} is not configured on this terminal",
                "provider": provider,
            }
        ), 503

    try:
        data = _client_for(provider).request_status(reference) or {}
    except ValueError as exc:
        return jsonify({"error": str(exc), "provider": provider}), 400
    except (MomoError, AirtelError) as exc:
        return jsonify(
            {
                "error": str(exc),
                "momo_status": exc.status,
                "provider": provider,
            }
        ), _upstream_status(exc)

    row = ledger.apply_status(reference, data, source="STATUS", provider=provider)
    payload = dict(data)
    payload["reference_id"] = reference
    payload["provider"] = provider
    payload["ledger_status"] = row.get("status", "") if row else ""
    return jsonify(payload)


@bp.route("/api/momo/health")
@login_required
def momo_health():
    """Credential summary; ``?check=1`` also proves the token exchange works."""
    settings = _settings()
    payload = settings.status_payload
    payload["provider"] = providers.MTN
    payload["verify_sales"] = service.verify_sales_enabled(providers.MTN)
    if request.args.get("check") in {"1", "true", "yes", "on"}:
        try:
            # Force a real exchange: a cached token would not prove MTN is up.
            _client().access_token(force=True)
            payload["reachable"] = True
        except MomoError as exc:
            payload["reachable"] = False
            payload["error"] = str(exc)
            return jsonify(payload), 503
    return jsonify(payload)


@bp.route("/api/momo/collect", methods=["POST"])
@login_required
def momo_collect():
    me = current_user() or {}
    if _rate_limited(me.get("id")):
        return jsonify(
            {"error": "Too many payment requests; wait a minute and try again"}
        ), 429
    return _collect(providers.MTN, request.get_json(silent=True) or {}, me)


@bp.route("/api/momo/collect/<reference_id>")
@login_required
def momo_request_status(reference_id):
    return _status(providers.MTN, reference_id)


@callback_bp.route("/api/momo/callback", methods=["POST"])
def momo_callback():
    """Receive MTN's asynchronous status callback.

    The route is public (MTN cannot send a session cookie) but requires the
    shared ``MOMO_CALLBACK_SECRET``. It only updates a ledger row that already
    exists; a callback can never create a payment out of thin air.
    """
    secret = str(current_app.config.get("MOMO_CALLBACK_SECRET") or "").strip()
    if not secret:
        return jsonify({"error": "callback disabled"}), 404

    supplied = request.args.get("token") or request.headers.get("X-Callback-Token") or ""
    if not hmac.compare_digest(str(supplied), secret):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    raw_reference = str(
        data.get("referenceId") or data.get("reference_id") or ""
    ).strip()
    if not raw_reference:
        return jsonify({"error": "referenceId is required"}), 400
    try:
        reference = ledger.canonical_reference(raw_reference)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    row = ledger.get_collection(reference)
    if row is None:
        return jsonify({"error": "unknown reference"}), 404
    mismatch = _provider_mismatch_response(row, providers.MTN)
    if mismatch:
        return mismatch

    status = str(data.get("status") or "").strip().upper()
    if not status:
        return jsonify({"error": "status is required"}), 400
    if status not in ledger.PAYMENT_STATUSES:
        return jsonify({"error": f"unsupported status {status}"}), 400

    try:
        ledger.apply_status(reference, data, source="CALLBACK", provider=providers.MTN)
    except PaymentError as exc:
        return jsonify({"error": str(exc)}), exc.status
    ledger.record_event(
        None,
        reference,
        "CALLBACK",
        detail=f"status={status}",
    )
    return jsonify({"ok": True, "reference_id": reference, "status": status})


def _callback_supplied_token():
    """Read the shared callback secret from the query, header, or bearer auth."""
    supplied = request.args.get("token") or request.headers.get("X-Callback-Token") or ""
    if not supplied:
        authorization = str(request.headers.get("Authorization") or "").strip()
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        elif authorization:
            supplied = authorization
    return str(supplied or "")


@callback_bp.route("/api/payments/airtel/callback", methods=["POST"])
def airtel_callback():
    """Receive Airtel's asynchronous status callback.

    The route is public (Airtel cannot send a session cookie) but requires the
    shared ``AIRTEL_CALLBACK_SECRET``. The callback body is **never** trusted:
    Airtel's status endpoint is re-queried and only that answer updates the
    ledger. A callback can never create a payment out of thin air.
    """
    secret = str(current_app.config.get("AIRTEL_CALLBACK_SECRET") or "").strip()
    if not secret:
        return jsonify({"error": "callback disabled"}), 404

    supplied = _callback_supplied_token()
    if not hmac.compare_digest(supplied, secret):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
    raw_reference = str(
        transaction.get("id")
        or transaction.get("transaction_id")
        or data.get("reference_id")
        or data.get("referenceId")
        or data.get("id")
        or ""
    ).strip()
    if not raw_reference:
        return jsonify({"error": "transaction.id is required"}), 400
    try:
        reference = ledger.canonical_reference(raw_reference)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ledger.is_uuid(reference):
        return jsonify(
            {
                "error": "transaction.id must be the UUID returned by the "
                "payment request"
            }
        ), 400

    row = ledger.get_collection(reference)
    if row is None:
        return jsonify({"error": "unknown reference"}), 404
    mismatch = _provider_mismatch_response(row, providers.AIRTEL)
    if mismatch:
        return mismatch

    # Record what the callback claimed for the audit trail, but never apply it.
    # A forged body must not be able to mark a payment successful or failed.
    reported = (
        transaction.get("status_code")
        or transaction.get("status")
        or data.get("status")
        or ""
    )
    reported = str(reported).strip().upper() if isinstance(reported, str) else ""

    try:
        status_data = service.fetch_status(reference, providers.AIRTEL)
        updated = ledger.apply_status(
            reference,
            status_data,
            source="CALLBACK",
            provider=providers.AIRTEL,
        )
    except PaymentError as exc:
        ledger.record_event(
            None,
            reference,
            "CALLBACK_ERROR",
            actor="airtel",
            detail=str(exc)[:500],
        )
        return jsonify(
            {
                "error": str(exc),
                "reference_id": reference,
                "provider": providers.AIRTEL,
            }
        ), exc.status

    gateway_status = str((status_data or {}).get("status") or "").upper()
    ledger_status = str((updated or {}).get("status") or "").upper()
    ledger.record_event(
        None,
        reference,
        "CALLBACK",
        actor="airtel",
        detail=(
            f"reported={reported or '-'} gateway={gateway_status or '-'} "
            f"ledger={ledger_status or '-'}"
        ),
    )
    return jsonify(
        {
            "ok": True,
            "reference_id": reference,
            "provider": providers.AIRTEL,
            "status": ledger_status,
            "gateway_status": gateway_status,
        }
    )


# -- provider-aware endpoints (Phase 2) -------------------------------------
@bp.route("/api/payments/health")
@login_required
def payments_health():
    """Summarise both carriers; ``?check=1`` forces a token exchange per provider."""
    check = request.args.get("check") in {"1", "true", "yes", "on"}
    result = {}
    configured_any = False
    failed = False
    for provider in providers.PROVIDERS:
        settings = _settings_for(provider)
        payload = settings.status_payload
        payload["provider"] = provider
        payload["payment_method"] = providers.PROVIDER_TO_METHOD[provider]
        payload["verify_sales"] = service.verify_sales_enabled(provider)
        if check:
            if not settings.configured:
                # A shop may intentionally use only one carrier. Report it as
                # unreachable but do not fail the health check for the other.
                payload["reachable"] = False
            else:
                configured_any = True
                try:
                    _client_for(provider).access_token(force=True)
                    payload["reachable"] = True
                except (MomoError, AirtelError) as exc:
                    payload["reachable"] = False
                    payload["error"] = str(exc)
                    failed = True
        result[provider] = payload
    ok = not failed and (configured_any or not check)
    body = {"ok": ok, "providers": result}
    return jsonify(body), 503 if check and not ok else 200


@bp.route("/api/payments/detect", methods=["POST"])
@login_required
def payments_detect():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone") or data.get("payer") or "").strip()
    method = providers.detect_telco(phone)
    provider = providers.METHOD_TO_PROVIDER.get(method, "UNKNOWN")
    return jsonify(
        {
            "ok": True,
            "provider": provider,
            "payment_method": method,
            "phone": providers.ugandan_national_number(phone),
        }
    )


@bp.route("/api/payments/collect", methods=["POST"])
@login_required
def payments_collect():
    me = current_user() or {}
    if _rate_limited(me.get("id")):
        return jsonify(
            {"error": "Too many payment requests; wait a minute and try again"}
        ), 429

    data = request.get_json(silent=True) or {}
    raw_provider = str(data.get("provider") or "").strip()
    if not raw_provider or raw_provider.upper() in {"AUTO", "DETECT"}:
        method = providers.detect_telco(data.get("phone") or data.get("payer"))
        if method == "UNKNOWN":
            return jsonify(
                {
                    "error": "Could not identify the carrier from this phone "
                    "number; select MTN or Airtel explicitly",
                    "provider": "UNKNOWN",
                }
            ), 400
        provider = providers.METHOD_TO_PROVIDER[method]
    else:
        try:
            provider = providers.normalize_provider(raw_provider)
        except ValueError as exc:
            return jsonify({"error": str(exc), "provider": "UNKNOWN"}), 400
    # Prefix the idempotency key so the same POS key cannot collide across
    # carriers (the ledger's unique index is global).
    return _collect(provider, data, me, key_prefix=f"{provider}:")


@bp.route("/api/payments/status/<provider>/<reference_id>")
@login_required
def payments_status(provider, reference_id):
    try:
        normalized = providers.normalize_provider(provider)
    except ValueError as exc:
        return jsonify({"error": str(exc), "provider": "UNKNOWN"}), 400
    return _status(normalized, reference_id)
