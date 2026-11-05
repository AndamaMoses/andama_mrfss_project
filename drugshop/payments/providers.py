"""Mobile-money provider constants, method mapping, and telco detection.

The rest of the payment code uses two related names:

* ``provider`` is the ledger/gateway family: ``MTN`` or ``AIRTEL``.
* ``payment_method`` is the value stored on a sale: ``MTN_MOMO`` or
  ``AIRTEL_MOMO``.

Keeping the mapping in one module avoids scattering string comparisons across
the ledger, sale guard, routes, and POS. Ugandan prefixes are deliberately
limited to the ranges currently assigned to the two carriers; an unknown
prefix is never guessed.
"""
from __future__ import annotations

import re

MTN = "MTN"
AIRTEL = "AIRTEL"
PROVIDERS = (MTN, AIRTEL)

PROVIDER_LABELS = {
    MTN: "MTN MoMo",
    AIRTEL: "Airtel Money",
}

METHOD_TO_PROVIDER = {
    "MTN_MOMO": MTN,
    "AIRTEL_MOMO": AIRTEL,
}
PROVIDER_TO_METHOD = {provider: method for method, provider in METHOD_TO_PROVIDER.items()}
MOMO_METHODS = frozenset(METHOD_TO_PROVIDER)

# Ugandan national prefixes, with the leading zero (e.g. 077, 070).
MTN_PREFIXES = frozenset({"077", "078", "076", "039"})
AIRTEL_PREFIXES = frozenset({"070", "074", "075", "020"})

_ALIASES = {
    "MTN": MTN,
    "MTN_MOMO": MTN,
    "MTN_MONEY": MTN,
    "MOMO": MTN,
    "AIRTEL": AIRTEL,
    "AIRTEL_MOMO": AIRTEL,
    "AIRTEL_MONEY": AIRTEL,
}


def normalize_provider(value, default=None):
    """Return ``MTN`` or ``AIRTEL`` from a provider or payment-method value.

    ``default`` is returned only for an empty value. An unknown non-empty value
    raises ``ValueError`` so a typo cannot silently select the wrong gateway.
    """
    text = str(value or "").strip().upper()
    if not text:
        if default is not None:
            return normalize_provider(default)
        raise ValueError("provider is required (MTN or AIRTEL)")
    try:
        return _ALIASES[text]
    except KeyError as exc:
        raise ValueError(f"unsupported payment provider: {value}") from exc


def provider_for_method(method):
    """Return the provider for a sale payment method, or ``None``."""
    return METHOD_TO_PROVIDER.get(str(method or "").strip().upper())


def method_for_provider(provider):
    """Return the sale payment method for a provider."""
    return PROVIDER_TO_METHOD[normalize_provider(provider)]


def is_momo_method(method):
    """True for a supported mobile-money sale method."""
    return str(method or "").strip().upper() in METHOD_TO_PROVIDER


def ugandan_national_number(phone):
    """Return a Ugandan number as ``0XXXXXXXXX`` for prefix detection.

    Accepts local, international (``+256``/``256``), ``00256`` and the common
    ``2560...`` handset form. Returns the digits unchanged when they are not a
    recognisable Ugandan number; callers decide whether that is an error.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("2560"):
        digits = "0" + digits[4:]
    elif digits.startswith("256"):
        digits = "0" + digits[3:]
    elif len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    return digits


def detect_telco(phone):
    """Classify a Ugandan number as ``MTN_MOMO``, ``AIRTEL_MOMO``, or ``UNKNOWN``."""
    national = ugandan_national_number(phone)
    if len(national) != 10 or not national.startswith("0"):
        return "UNKNOWN"
    prefix = national[:3]
    if prefix in MTN_PREFIXES:
        return "MTN_MOMO"
    if prefix in AIRTEL_PREFIXES:
        return "AIRTEL_MOMO"
    return "UNKNOWN"


def detect_provider(phone):
    """Return ``MTN``, ``AIRTEL``, or ``UNKNOWN`` for a Ugandan number."""
    method = detect_telco(phone)
    return METHOD_TO_PROVIDER.get(method, "UNKNOWN")
