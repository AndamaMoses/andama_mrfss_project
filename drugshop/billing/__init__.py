"""Billing price book, quote engine, and subscription ledger.

The package exports the pure price-book API only. ``service.py`` adds the
database-backed subscription, invoice, and payment ledger and is imported
lazily by the operator CLI, so quote commands stay pure. The read-only customer
view arrives in Phase 4.
"""
from drugshop.billing.catalog import (
    ADDON_IDS,
    BASE_IDS,
    CURRENCY,
    LEGACY_ID,
    PRICE_BOOK,
    PRICE_BOOK_VERSION,
    SETUP_DISCOUNT_CAP,
    Price,
    Quote,
    QuoteError,
    QuoteLine,
    quote,
    validate_price_book,
)

__all__ = [
    "ADDON_IDS",
    "BASE_IDS",
    "CURRENCY",
    "LEGACY_ID",
    "PRICE_BOOK",
    "PRICE_BOOK_VERSION",
    "SETUP_DISCOUNT_CAP",
    "Price",
    "Quote",
    "QuoteError",
    "QuoteLine",
    "quote",
    "validate_price_book",
]
