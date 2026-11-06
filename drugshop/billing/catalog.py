"""Versioned price book and quote rules for Onzima Dawa.

This module is deliberately pure: it imports no Flask, database, or network
code. Phase 1 uses it for operator quotes; later phases snapshot the
price-book version on a subscription record.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

PRICE_BOOK_VERSION = "v1-2026-11-05"
CURRENCY = "UGX"
LEGACY_ID = "legacy"
BASE_IDS = ("core", "pro", "tender")
ADDON_IDS = ("growth", "tender")


@dataclass(frozen=True)
class Price:
    """One sellable line in the price book."""

    id: str
    label: str
    setup: int
    monthly: int
    roles: tuple[str, ...] = ("base",)
    requires: tuple[str, ...] = ()
    description: str = ""


PRICE_BOOK: dict[str, Price] = {
    "core": Price(
        id="core",
        label="Core",
        setup=400_000,
        monthly=120_000,
        description="POS and Inventory",
    ),
    "pro": Price(
        id="pro",
        label="Pro",
        setup=600_000,
        monthly=180_000,
        description="Core plus Patients and Finance",
    ),
    "growth": Price(
        id="growth",
        label="Growth add-on",
        setup=200_000,
        monthly=50_000,
        roles=("addon",),
        requires=("pro",),
        description="Stock Alerts on top of Pro",
    ),
    "tender": Price(
        id="tender",
        label="Tender Copilot",
        setup=300_000,
        monthly=150_000,
        roles=("base", "addon"),
        description="Standalone tender workspace, or an add-on to a pharmacy bundle",
    ),
}


@dataclass(frozen=True)
class QuoteLine:
    """One line in a generated quote."""

    id: str
    label: str
    role: str
    setup: int
    monthly: int


@dataclass(frozen=True)
class Quote:
    """A complete, auditable quote snapshot."""

    price_book_version: str
    currency: str
    base: str
    addons: tuple[str, ...]
    label: str
    lines: tuple[QuoteLine, ...]
    setup_subtotal: int
    setup_discount: int
    setup_total: int
    monthly_total: int

    def as_dict(self) -> dict:
        """Return a stable JSON-ready payload for the CLI and later APIs."""
        return {
            "price_book_version": self.price_book_version,
            "currency": self.currency,
            "base": self.base,
            "addons": list(self.addons),
            "label": self.label,
            "lines": [
                {
                    "id": line.id,
                    "label": line.label,
                    "role": line.role,
                    "setup": line.setup,
                    "monthly": line.monthly,
                }
                for line in self.lines
            ],
            "setup_subtotal": self.setup_subtotal,
            "setup_discount": self.setup_discount,
            "setup_total": self.setup_total,
            "monthly_total": self.monthly_total,
        }


class QuoteError(ValueError):
    """Raised when a quote request is invalid or unsellable."""


def validate_price_book(book: Mapping[str, Price] | None = None) -> None:
    """Validate a price book before it is used for a quote."""
    book = PRICE_BOOK if book is None else book
    if not book:
        raise QuoteError("Price book is empty.")
    for key, offer in book.items():
        if not isinstance(offer, Price):
            raise QuoteError(f"Price book entry {key!r} is not a Price.")
        if offer.id != key:
            raise QuoteError(
                f"Price book key {key!r} does not match offer id {offer.id!r}."
            )
        if not offer.roles:
            raise QuoteError(f"{offer.label} has no role.")
        unknown_roles = set(offer.roles) - {"base", "addon"}
        if unknown_roles:
            names = ", ".join(sorted(unknown_roles))
            raise QuoteError(f"{offer.label} has unknown role(s): {names}.")
        if isinstance(offer.setup, bool) or not isinstance(offer.setup, int):
            raise QuoteError(f"{offer.label} setup must be a whole number of {CURRENCY}.")
        if offer.setup <= 0:
            raise QuoteError(f"{offer.label} setup must be greater than zero.")
        if isinstance(offer.monthly, bool) or not isinstance(offer.monthly, int):
            raise QuoteError(
                f"{offer.label} monthly must be a whole number of {CURRENCY}."
            )
        if offer.monthly <= 0:
            raise QuoteError(f"{offer.label} monthly must be greater than zero.")
        for required in offer.requires:
            if required not in book:
                raise QuoteError(f"{offer.label} requires missing offer {required!r}.")
            if "base" not in book[required].roles:
                raise QuoteError(
                    f"{offer.label} requires {book[required].label}, "
                    "which is not a base offer."
                )
    if not any("base" in offer.roles for offer in book.values()):
        raise QuoteError("Price book must contain at least one base offer.")


def _normalize_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuoteError(f"{label} is required.")
    return value.strip().lower()


def _normalize_addons(addons: Iterable[str]) -> tuple[str, ...]:
    if addons is None:
        raise QuoteError("Add-on is required.")
    if isinstance(addons, str):
        addons = (addons,)
    normalized = []
    seen = set()
    for raw in addons:
        addon_id = _normalize_id(raw, "Add-on")
        if addon_id in seen:
            raise QuoteError(f"Add-on {addon_id!r} was requested more than once.")
        seen.add(addon_id)
        if addon_id not in ADDON_IDS:
            raise QuoteError(
                f"Unknown add-on {addon_id!r}; choose {', '.join(ADDON_IDS)}."
            )
        normalized.append(addon_id)
    return tuple(normalized)


def _validate_setup_discount(setup_discount: int) -> None:
    if isinstance(setup_discount, bool) or not isinstance(setup_discount, int):
        raise QuoteError(f"Setup discount must be a whole number of {CURRENCY}.")
    if setup_discount < 0:
        raise QuoteError("Setup discount cannot be negative.")


def _validate_monthly_discount(monthly_discount: int) -> None:
    if isinstance(monthly_discount, bool) or not isinstance(monthly_discount, int):
        raise QuoteError(f"Monthly discount must be a whole number of {CURRENCY}.")
    if monthly_discount:
        raise QuoteError("Monthly fees cannot be discounted.")


def _quote_label(base_id: str, addons: tuple[str, ...]) -> str:
    if base_id == "pro" and addons == ("growth",):
        return "Growth"
    if base_id == "pro" and "growth" in addons and "tender" in addons:
        return "Growth + Tender Copilot"
    if "tender" in addons:
        return f"{PRICE_BOOK[base_id].label} + Tender Copilot"
    return PRICE_BOOK[base_id].label


def quote(
    base: str,
    addons: Iterable[str] = (),
    setup_discount: int = 0,
    monthly_discount: int = 0,
) -> Quote:
    """Build a quote for ``base`` plus optional add-ons.

    Growth requires Pro. Tender can stand alone or be added to Core, Pro, or
    Growth. Setup discounts cannot be negative or exceed the setup subtotal;
    monthly fees are never discounted.
    """
    validate_price_book()
    base_id = _normalize_id(base, "Base offer")
    if base_id == LEGACY_ID:
        raise QuoteError("Legacy is grandfathered and cannot be quoted.")
    if base_id == "growth":
        raise QuoteError("Growth is an add-on; quote pro --add growth.")
    if base_id not in BASE_IDS:
        raise QuoteError(
            f"Unknown base offer {base_id!r}; choose {', '.join(BASE_IDS)}."
        )

    addon_ids = _normalize_addons(addons)
    if base_id == "tender" and addon_ids:
        raise QuoteError(
            "Tender Copilot is standalone when it is the base offer; "
            "do not add another offer."
        )
    for addon_id in addon_ids:
        offer = PRICE_BOOK[addon_id]
        for required in offer.requires:
            if required != base_id:
                raise QuoteError(
                    f"{offer.label} requires {PRICE_BOOK[required].label}; "
                    f"quote {required} --add {addon_id}."
                )

    _validate_setup_discount(setup_discount)
    _validate_monthly_discount(monthly_discount)

    lines = [
        QuoteLine(
            id=PRICE_BOOK[base_id].id,
            label=PRICE_BOOK[base_id].label,
            role="base",
            setup=PRICE_BOOK[base_id].setup,
            monthly=PRICE_BOOK[base_id].monthly,
        )
    ]
    for addon_id in addon_ids:
        offer = PRICE_BOOK[addon_id]
        lines.append(
            QuoteLine(
                id=offer.id,
                label=offer.label,
                role="addon",
                setup=offer.setup,
                monthly=offer.monthly,
            )
        )

    setup_subtotal = sum(line.setup for line in lines)
    if setup_discount > setup_subtotal:
        raise QuoteError(
            f"Setup discount {setup_discount:,} exceeds the setup subtotal "
            f"{setup_subtotal:,}."
        )
    return Quote(
        price_book_version=PRICE_BOOK_VERSION,
        currency=CURRENCY,
        base=base_id,
        addons=addon_ids,
        label=_quote_label(base_id, addon_ids),
        lines=tuple(lines),
        setup_subtotal=setup_subtotal,
        setup_discount=setup_discount,
        setup_total=setup_subtotal - setup_discount,
        monthly_total=sum(line.monthly for line in lines),
    )
