"""Operator CLI for the revenue price book and quotes (Phase 1).

No database access: quotes are pure price-book calculations.

    flask --app run revenue pricebook
    flask --app run revenue quote core
    flask --app run revenue quote pro --add growth
    flask --app run revenue quote pro --add tender
    flask --app run revenue quote pro --setup-discount 100000 --json
"""
import json

import click

from drugshop.billing.catalog import (
    CURRENCY,
    PRICE_BOOK,
    PRICE_BOOK_VERSION,
    QuoteError,
    quote,
)


def _pricebook_lines():
    yield f"Price book: {PRICE_BOOK_VERSION}"
    yield f"Currency:   {CURRENCY}"
    yield "Offers:"
    for offer in PRICE_BOOK.values():
        roles = " / ".join(offer.roles)
        requires = ""
        if offer.requires:
            required = ", ".join(PRICE_BOOK[item].label for item in offer.requires)
            requires = f" (requires {required})"
        yield (
            f"  {offer.label:<20} setup {offer.setup:>9,}   "
            f"monthly {offer.monthly:>7,}   {roles}{requires}"
        )
    yield ""
    yield "Rules: Growth requires Pro; Tender can stand alone or be added."
    yield "       Monthly fees are never discounted."


def _quote_lines(result):
    yield f"Quote:      {result.label}"
    yield f"Price book: {result.price_book_version}"
    yield f"Currency:   {result.currency}"
    yield ""
    for line in result.lines:
        yield (
            f"  {line.label:<20} setup {line.setup:>9,}   "
            f"monthly {line.monthly:>7,}"
        )
    if result.setup_discount:
        yield f"  {'Setup subtotal':<20} setup {result.setup_subtotal:>9,}"
        yield f"  {'Setup discount':<20} setup {-result.setup_discount:>9,}"
    yield "  " + "-" * 56
    yield (
        f"  {'Total':<20} setup {result.setup_total:>9,}   "
        f"monthly {result.monthly_total:>7,}"
    )


@click.group("revenue")
def revenue_group():
    """Show the price book or build an operator quote."""


@revenue_group.command("pricebook")
def pricebook_command():
    """Show the versioned price book."""
    for line in _pricebook_lines():
        click.echo(line)


@revenue_group.command("quote")
@click.argument("base")
@click.option(
    "--add",
    "addons",
    multiple=True,
    help="Add growth or tender; repeat for both.",
)
@click.option(
    "--setup-discount",
    type=int,
    default=0,
    show_default=True,
    help=f"{CURRENCY} off setup; monthly fees are never discounted.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def quote_command(base, addons, setup_discount, as_json):
    """Quote BASE (core | pro | tender) with optional add-ons."""
    try:
        result = quote(base, addons=addons, setup_discount=setup_discount)
    except QuoteError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(json.dumps(result.as_dict(), indent=2))
        return
    for line in _quote_lines(result):
        click.echo(line)


def register_cli(app):
    app.cli.add_command(revenue_group)
