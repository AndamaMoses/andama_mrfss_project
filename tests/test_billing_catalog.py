"""Tests for the pure Phase 1 price book and quote rules."""
from dataclasses import replace

import pytest

from drugshop.billing.catalog import (
    CURRENCY,
    PRICE_BOOK,
    PRICE_BOOK_VERSION,
    Price,
    QuoteError,
    QuoteLine,
    quote,
    validate_price_book,
)

SCENARIOS = [
    ("core", (), 400_000, 120_000, "Core"),
    ("pro", (), 600_000, 180_000, "Pro"),
    ("pro", ("growth",), 800_000, 230_000, "Growth"),
    ("tender", (), 300_000, 150_000, "Tender Copilot"),
    ("pro", ("tender",), 900_000, 330_000, "Pro + Tender Copilot"),
    ("core", ("tender",), 700_000, 270_000, "Core + Tender Copilot"),
    (
        "pro",
        ("growth", "tender"),
        1_100_000,
        380_000,
        "Growth + Tender Copilot",
    ),
]


@pytest.mark.parametrize(
    ("base", "addons", "setup", "monthly", "label"),
    SCENARIOS,
)
def test_quote_totals(base, addons, setup, monthly, label):
    result = quote(base, addons)

    assert result.label == label
    assert result.setup_subtotal == setup
    assert result.setup_total == setup
    assert result.monthly_total == monthly


def test_quote_includes_price_book_version_and_currency():
    result = quote("core")

    assert result.price_book_version == PRICE_BOOK_VERSION
    assert result.price_book_version == "v1-2026-11-05"
    assert result.currency == CURRENCY == "UGX"


def test_growth_quote_has_pro_and_growth_lines():
    result = quote("pro", ("growth",))

    assert result.base == "pro"
    assert result.addons == ("growth",)
    assert result.lines == (
        QuoteLine(
            id="pro",
            label="Pro",
            role="base",
            setup=600_000,
            monthly=180_000,
        ),
        QuoteLine(
            id="growth",
            label="Growth add-on",
            role="addon",
            setup=200_000,
            monthly=50_000,
        ),
    )


def test_setup_discount_only_reduces_setup():
    result = quote("pro", setup_discount=100_000)

    assert result.setup_subtotal == 600_000
    assert result.setup_discount == 100_000
    assert result.setup_total == 500_000
    assert result.monthly_total == 180_000


def test_zero_setup_discount_is_allowed():
    result = quote("core", setup_discount=0)

    assert result.setup_total == 400_000


def test_setup_discount_equal_to_subtotal_is_allowed():
    result = quote("core", setup_discount=400_000)

    assert result.setup_total == 0


def test_negative_setup_discount_is_rejected():
    with pytest.raises(QuoteError, match="cannot be negative"):
        quote("core", setup_discount=-1)


def test_setup_discount_above_subtotal_is_rejected():
    with pytest.raises(QuoteError, match="exceeds the setup subtotal"):
        quote("core", setup_discount=400_001)


def test_non_integer_setup_discount_is_rejected():
    with pytest.raises(QuoteError, match="whole number"):
        quote("core", setup_discount=1000.5)


def test_monthly_discount_is_rejected():
    with pytest.raises(QuoteError, match="Monthly fees cannot be discounted"):
        quote("pro", monthly_discount=1)


def test_negative_monthly_discount_is_rejected():
    with pytest.raises(QuoteError, match="Monthly fees cannot be discounted"):
        quote("pro", monthly_discount=-1)


def test_growth_with_core_is_rejected():
    with pytest.raises(QuoteError, match="Growth add-on requires Pro"):
        quote("core", ("growth",))


def test_growth_as_base_is_rejected_with_helpful_message():
    with pytest.raises(QuoteError, match="Growth is an add-on"):
        quote("growth")


def test_tender_standalone_rejects_another_offer():
    with pytest.raises(QuoteError, match="standalone"):
        quote("tender", ("growth",))


def test_duplicate_addon_is_rejected():
    with pytest.raises(QuoteError, match="more than once"):
        quote("pro", ("growth", "growth"))


def test_unknown_base_is_rejected():
    with pytest.raises(QuoteError, match="Unknown base offer"):
        quote("platinum")


def test_unknown_addon_is_rejected():
    with pytest.raises(QuoteError, match="Unknown add-on"):
        quote("pro", ("alerts",))


def test_legacy_cannot_be_quoted():
    with pytest.raises(QuoteError, match="Legacy is grandfathered"):
        quote("legacy")


def test_addons_accepts_a_single_string():
    result = quote("pro", "growth")

    assert result.addons == ("growth",)
    assert result.label == "Growth"


def test_as_dict_is_stable_and_includes_line_items():
    payload = quote("pro", ("growth",), setup_discount=100_000).as_dict()

    assert list(payload) == [
        "price_book_version",
        "currency",
        "base",
        "addons",
        "label",
        "lines",
        "setup_subtotal",
        "setup_discount",
        "setup_total",
        "monthly_total",
    ]
    assert payload["price_book_version"] == PRICE_BOOK_VERSION
    assert payload["currency"] == "UGX"
    assert payload["base"] == "pro"
    assert payload["addons"] == ["growth"]
    assert payload["label"] == "Growth"
    assert payload["lines"] == [
        {
            "id": "pro",
            "label": "Pro",
            "role": "base",
            "setup": 600_000,
            "monthly": 180_000,
        },
        {
            "id": "growth",
            "label": "Growth add-on",
            "role": "addon",
            "setup": 200_000,
            "monthly": 50_000,
        },
    ]
    assert payload["setup_subtotal"] == 800_000
    assert payload["setup_discount"] == 100_000
    assert payload["setup_total"] == 700_000
    assert payload["monthly_total"] == 230_000


def test_default_price_book_is_valid():
    validate_price_book()


@pytest.mark.parametrize("field", ["setup", "monthly"])
@pytest.mark.parametrize("value", [0, -1])
def test_price_book_rejects_non_positive_amounts(field, value):
    book = dict(PRICE_BOOK)
    book["core"] = replace(PRICE_BOOK["core"], **{field: value})

    with pytest.raises(QuoteError, match=f"{field} must be greater than zero"):
        validate_price_book(book)


@pytest.mark.parametrize("field", ["setup", "monthly"])
def test_price_book_rejects_non_integer_amounts(field):
    book = dict(PRICE_BOOK)
    book["core"] = replace(PRICE_BOOK["core"], **{field: 1.5})

    with pytest.raises(QuoteError, match=f"{field} must be a whole number"):
        validate_price_book(book)


def test_price_book_rejects_missing_dependency():
    book = {"growth": PRICE_BOOK["growth"]}

    with pytest.raises(QuoteError, match="missing offer 'pro'"):
        validate_price_book(book)


def test_price_book_rejects_key_mismatch():
    book = {"core": Price(id="pro", label="Pro", setup=1, monthly=1)}

    with pytest.raises(QuoteError, match="does not match offer id"):
        validate_price_book(book)
