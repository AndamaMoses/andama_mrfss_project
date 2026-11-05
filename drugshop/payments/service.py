"""Sale-side mobile-money checks for MTN and Airtel.

The fluent flow is: counter requests a collection, the customer approves on
their phone, the counter records the sale with the gateway reference. This
module re-asks the carrier, server-side, that the reference is ``SUCCESSFUL``,
that the amount matches the basket, and that the currency matches the
configured environment.

Manual MoMo takings (customer paid a till/agent directly) skip the gateway call
only when the request explicitly says ``is_manual_entry``. A configured shop
cannot bypass verification by simply omitting the reference.
"""
import threading

from flask import current_app

from drugshop.payments import ledger, providers
from drugshop.payments.airtel import AirtelClient, AirtelError, AirtelSettings
from drugshop.payments.errors import PaymentError
from drugshop.payments.momo import MomoClient, MomoError, MomoSettings

__all__ = ["PaymentError", "enabled", "verify_reference"]

# Sale verification runs on every mobile-money checkout. Reuse one client per
# distinct provider/configuration so a valid bearer token is not re-fetched for
# every sale; the routes module keeps a separate cache for collect/status.
_CLIENTS = {}
_CLIENTS_LOCK = threading.Lock()


def reset_clients():
    """Clear the verification client cache. Tests call this between cases."""
    with _CLIENTS_LOCK:
        _CLIENTS.clear()


def _settings(provider):
    if provider == providers.MTN:
        return MomoSettings.from_mapping(current_app.config)
    return AirtelSettings.from_mapping(current_app.config)


def _client_key(provider, settings):
    if provider == providers.MTN:
        return (
            providers.MTN,
            settings.resolved_base_url,
            settings.subscription_key,
            settings.api_user,
            settings.api_key,
            settings.environment,
            settings.currency,
            settings.callback_url,
            settings.timeout,
        )
    return (
        providers.AIRTEL,
        settings.resolved_base_url,
        settings.client_id,
        settings.client_secret,
        settings.currency,
        settings.country,
        settings.timeout,
    )


def _client(provider, settings):
    key = _client_key(provider, settings)
    with _CLIENTS_LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            if provider == providers.MTN:
                client = MomoClient(settings)
            else:
                client = AirtelClient(settings)
            _CLIENTS[key] = client
    return client


def enabled(provider=providers.MTN):
    """True when the selected provider's credentials are configured."""
    try:
        provider = providers.normalize_provider(provider)
    except ValueError:
        return False
    return _settings(provider).configured


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value if value is not None else "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _verify_flag(provider):
    key = "MOMO_VERIFY_SALES" if provider == providers.MTN else "AIRTEL_VERIFY_SALES"
    return _truthy(current_app.config.get(key, True))


def _provider_label(provider):
    return "MTN" if provider == providers.MTN else "Airtel"


def _amount(value, label, provider):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PaymentError(
            f"{_provider_label(provider)} did not return a valid {label}", status=502
        ) from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise PaymentError(
            f"{_provider_label(provider)} did not return a valid {label}", status=502
        )
    return number


def fetch_status(reference, provider=providers.MTN):
    """Return the carrier's current status for a ledger reference.

    This is the shared read used by callbacks and reconciliation sweeps. Unlike
    :func:`verify_reference`, it does not apply the sale verification switch: a
    shop that records sales manually may still want to check an old prompt.
    Credentials are required, because the status endpoint is authenticated.
    """
    try:
        provider = providers.normalize_provider(provider)
    except ValueError as exc:
        raise PaymentError(str(exc), status=400) from exc
    try:
        reference = ledger.canonical_reference(reference)
    except ValueError as exc:
        raise PaymentError(str(exc), status=400) from exc

    settings = _settings(provider)
    if not settings.configured:
        if provider == providers.MTN:
            raise PaymentError(
                "MoMo is not configured on this terminal; set "
                "MOMO_SUBSCRIPTION_KEY / MOMO_API_USER / MOMO_API_KEY",
                status=503,
            )
        raise PaymentError(
            "Airtel Money is not configured on this terminal; set "
            "AIRTEL_CLIENT_ID / AIRTEL_CLIENT_SECRET",
            status=503,
        )
    try:
        return _client(provider, settings).request_status(reference) or {}
    except ValueError as exc:
        raise PaymentError(
            "MoMo reference must be the UUID returned by the payment request",
            status=400,
        ) from exc
    except (MomoError, AirtelError) as exc:
        raise PaymentError(
            f"Could not check the {_provider_label(provider)} payment: {exc}",
            status=502,
        ) from exc


def verify_reference(reference, amount, provider=providers.MTN, currency=None):
    """Raise :class:`PaymentError` unless the carrier reports a successful payment.

    Verification is fail-closed: when the provider's verify switch is on but its
    credentials are missing, the sale is rejected instead of silently trusting
    the counter. ``MOMO_VERIFY_SALES=0`` / ``AIRTEL_VERIFY_SALES=0`` is the
    explicit, monitored rollout switch that skips the gateway call.
    """
    try:
        provider = providers.normalize_provider(provider)
    except ValueError as exc:
        raise PaymentError(str(exc), status=400) from exc
    try:
        reference = ledger.canonical_reference(reference)
    except ValueError as exc:
        raise PaymentError(str(exc), status=400) from exc

    settings = _settings(provider)
    if not _verify_flag(provider):
        return None
    if not settings.configured:
        if provider == providers.MTN:
            raise PaymentError(
                "MoMo verification is enabled but MOMO_SUBSCRIPTION_KEY / "
                "MOMO_API_USER / MOMO_API_KEY are incomplete; set "
                "MOMO_VERIFY_SALES=0 only for a monitored manual rollout",
                status=503,
            )
        raise PaymentError(
            "Airtel verification is enabled but AIRTEL_CLIENT_ID / "
            "AIRTEL_CLIENT_SECRET are incomplete; set AIRTEL_VERIFY_SALES=0 "
            "only for a monitored manual rollout",
            status=503,
        )

    data = fetch_status(reference, provider)

    status = str(data.get("status", "")).upper()
    if status != "SUCCESSFUL":
        raise PaymentError(
            f"MoMo payment is {status or 'not confirmed'}; the sale was not recorded"
        )

    paid_amount_raw = data.get("amount")
    paid_currency = str(data.get("currency") or "").strip().upper()
    if provider == providers.AIRTEL and (paid_amount_raw is None or not paid_currency):
        # Airtel's status response may omit amount/currency. Fall back to the
        # amount/currency the merchant asked Airtel to collect; that row was
        # written before the request and the sale still has to match it
        # exactly. With no ledger row there is no basis for the amount, so the
        # check stays fail-closed.
        row = ledger.get_collection(reference)
        if row and str(row.get("provider") or providers.MTN).upper() == providers.AIRTEL:
            if paid_amount_raw is None:
                paid_amount_raw = row.get("amount")
            if not paid_currency:
                paid_currency = str(row.get("currency") or "").strip().upper()

    expected_currency = str(currency or settings.currency or "").strip().upper()

    paid_value = _amount(paid_amount_raw, "amount", provider)
    if paid_value <= 0:
        raise PaymentError(
            f"{_provider_label(provider)} reported a zero MoMo amount", status=502
        )

    expected = _amount(amount, "sale total", provider)
    if abs(paid_value - expected) > 0.01:
        label = paid_currency or expected_currency
        raise PaymentError(
            f"{_provider_label(provider)} MoMo paid {label} {paid_value:,.2f} "
            f"but the sale totals {expected_currency} {expected:,.2f}",
            paid_amount=paid_value,
            paid_currency=paid_currency or expected_currency,
        )

    if not paid_currency:
        raise PaymentError(
            f"{_provider_label(provider)} did not return a currency for the "
            "successful payment",
            status=502,
        )
    if paid_currency != expected_currency:
        raise PaymentError(
            f"MoMo currency {paid_currency} does not match {expected_currency}"
        )

    # Keep the ledger in step with the verification result. A later sale claim
    # still checks the amount and performs the atomic CONSUMED update.
    ledger.apply_status(reference, data, source="VERIFY", provider=provider)
    return data
