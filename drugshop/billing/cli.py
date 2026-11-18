"""Operator CLI for revenue quotes, subscriptions, invoices, and payments.

Quote commands are pure price-book calculations. Subscription, invoice, and
payment commands touch the installation database and remain operator-only.

    flask --app run revenue pricebook
    flask --app run revenue quote core
    flask --app run revenue quote pro --add growth
    flask --app run revenue quote pro --add tender
    flask --app run revenue quote pro --setup-discount 100000 --json
    flask --app run revenue show
    flask --app run revenue report --format json
    flask --app run revenue report --format csv
    flask --app run revenue activate pro --customer "Example Pharmacy" ...
    flask --app run revenue renew --period-end 2027-11-05 --actor "Andama"
    flask --app run revenue status past_due --notes "November invoice unpaid"
    flask --app run revenue invoice setup --due 2026-11-12
    flask --app run revenue invoice monthly \
        --period-start 2026-11-05 --period-end 2026-12-05
    flask --app run revenue invoice list --json
    flask --app run revenue invoice show INV-202611-0001
    flask --app run revenue invoice void INV-202611-0001 --reason "wrong period"
    flask --app run revenue payment record INV-202611-0001 \
        --amount 600000 --method bank --reference "FT-..."
    flask --app run revenue renewals --days 14
"""
import csv
import io
import json
import sqlite3

import click

from drugshop.apps.registry import bundle_label
from drugshop.billing.catalog import (
    CURRENCY,
    PRICE_BOOK,
    PRICE_BOOK_VERSION,
    SETUP_DISCOUNT_CAP,
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
    yield f"       Setup discounts are capped at {SETUP_DISCOUNT_CAP:,} {CURRENCY}."
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


def _format_money(value):
    amount = float(value or 0)
    if amount.is_integer():
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


def _error_message(exc):
    if isinstance(exc, sqlite3.Error) and "no such table" in str(exc).lower():
        return "database not initialized - run `python run.py` once, then retry"
    return str(exc)


def _period_text(subscription):
    if subscription["current_period_end"] is None:
        return "no expiry"
    return (
        f"{subscription['current_period_start'] or '-'} -> "
        f"{subscription['current_period_end']}"
    )


def _print_subscription(subscription, apps=None):
    click.echo(f"Plan:        {bundle_label(subscription['bundle'])}")
    click.echo(f"Status:      {subscription['status']}")
    click.echo(f"Customer:    {subscription['customer_name']}")
    contact = " ".join(
        part
        for part in (
            subscription["contact_name"] or "",
            subscription["contact_phone"] or "",
        )
        if part
    )
    if contact:
        click.echo(f"Contact:     {contact}")
    click.echo(f"Started:     {subscription['started_on']}")
    click.echo(f"Period:      {_period_text(subscription)}")
    click.echo(
        f"Setup:       {_format_money(subscription['setup_fee'])} "
        f"{subscription['currency']}"
    )
    click.echo(
        f"Monthly:     {_format_money(subscription['monthly_fee'])} "
        f"{subscription['currency']}"
    )
    click.echo(f"Price book:  {subscription['price_book_version']}")
    if subscription["notes"]:
        click.echo(f"Notes:       {subscription['notes']}")
    if apps:
        click.echo(f"Apps:        {', '.join(apps)}")


def _print_invoice(invoice):
    click.echo(f"Invoice:     {invoice['invoice_no']}")
    click.echo(f"Kind:        {invoice['kind']}")
    click.echo(f"Issued:      {invoice['issue_date']}")
    click.echo(f"Due:         {invoice['due_date']}")
    if invoice["period_start"] or invoice["period_end"]:
        click.echo(
            f"Period:      {invoice['period_start'] or '-'} -> "
            f"{invoice['period_end'] or '-'}"
        )
    click.echo(
        f"Amount:      {_format_money(invoice['amount'])} {invoice['currency']}"
    )
    click.echo(f"Paid:        {_format_money(invoice['paid'])} {invoice['currency']}")
    click.echo(
        f"Balance:     {_format_money(invoice['balance'])} {invoice['currency']}"
    )
    click.echo(f"Status:      {invoice['status']}")
    if invoice["notes"]:
        click.echo(f"Notes:       {invoice['notes']}")


def _invoice_line(invoice):
    return (
        f"{invoice['invoice_no']}  {invoice['kind']:<8} "
        f"{invoice['status']:<8} due {invoice['due_date']}  "
        f"amount {_format_money(invoice['amount'])}  "
        f"paid {_format_money(invoice['paid'])}  "
        f"balance {_format_money(invoice['balance'])} {invoice['currency']}"
    )


def _report_lines(data):
    plan = data["plan"]
    currency = data["currency"]
    yield f"Revenue report - {data['generated_at']}"
    yield f"As of:                {data['as_of']}"
    if data.get("source"):
        yield f"Source:               {data['source']}"
    yield f"Customer:             {data['customer_name'] or '(not recorded)'}"
    yield f"Plan:                 {plan['label']} ({plan['status']})"
    yield f"Billing:              {data['billing_status']}"
    yield f"Currency:             {currency}"
    yield ""
    yield f"MRR:                  {_format_money(data['mrr'])} {currency}"
    yield f"Setup invoiced:       {_format_money(data['setup_invoiced'])} {currency}"
    yield f"Monthly invoiced:     {_format_money(data['monthly_invoiced'])} {currency}"
    yield f"Total invoiced:       {_format_money(data['total_invoiced'])} {currency}"
    yield f"Setup collected:      {_format_money(data['setup_collected'])} {currency}"
    yield (
        f"Payments collected:   "
        f"{_format_money(data['payments_collected'])} {currency}"
    )
    yield (
        f"Outstanding balance:  "
        f"{_format_money(data['outstanding_balance'])} {currency}"
    )
    statuses = ", ".join(
        f"{status} {count}"
        for status, count in data["invoices_by_status"].items()
    )
    yield f"Invoices:             {data['invoice_count']}" + (
        f" ({statuses})" if statuses else ""
    )
    if data["renewals_due"]:
        yield "Renewals due:"
        for row in data["renewals_due"]:
            state = (
                f"overdue by {-row['days_until']} days"
                if row["overdue"]
                else f"due in {row['days_until']} days"
            )
            yield (
                f"  {row['customer_name'] or '(not recorded)'}  "
                f"{bundle_label(row['bundle'])}  ends {row['current_period_end']}  "
                f"{state}"
            )
    else:
        yield "Renewals due:         none"
    if data["grandfathered"]:
        yield "Grandfathered:"
        for row in data["grandfathered"]:
            yield (
                f"  {row['customer_name'] or '(not recorded)'}  "
                f"{row['label']}  {row['reason']}"
            )
    else:
        yield "Grandfathered:        none"
    if data["excluded"]:
        yield "Excluded from MRR:"
        for row in data["excluded"]:
            yield (
                f"  {row['customer_name'] or '(not recorded)'}  "
                f"{row['label']}  {row['reason']}"
            )
    else:
        yield "Excluded from MRR:    none"


def _payment_line(payment):
    parts = [
        payment["paid_on"],
        f"{_format_money(payment['amount'])} {payment['currency']}",
        payment["method"],
    ]
    if payment["reference"]:
        parts.append(f"ref {payment['reference']}")
    if payment["received_by"]:
        parts.append(f"by {payment['received_by']}")
    if payment["notes"]:
        parts.append(payment["notes"])
    return "  ".join(parts)


@click.group("revenue")
def revenue_group():
    """Show the price book, quote, or manage this installation's subscription."""


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
    help=(
        f"{CURRENCY} off setup (max {SETUP_DISCOUNT_CAP:,} in v1); "
        "monthly fees are never discounted."
    ),
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


@revenue_group.command("show")
def show_command():
    """Show the subscription, entitlement match, and recent events."""
    from drugshop.billing import service

    try:
        check = service.reconciliation()
        events = service.subscription_events(10)
    except sqlite3.Error as exc:
        raise click.ClickException(_error_message(exc)) from exc
    subscription = check["subscription"]
    if subscription is None:
        click.echo("No subscription recorded.")
        click.echo(
            "Run `flask --app run revenue activate <bundle> ...` after payment."
        )
        return
    _print_subscription(subscription)
    plan = check["plan"]
    state = "OK" if check["agrees"] else "MISMATCH"
    click.echo(
        f"Entitled:    {plan['label']} "
        f"(expires {plan['expires_at'] or 'no expiry'}) [{state}]"
    )
    if check["agrees"] is False:
        click.echo(
            "Warning:     subscription and entitlements disagree; review before invoicing."
        )
    if events:
        click.echo("Recent events:")
        for event in events:
            click.echo(
                f"  {event['created_at']}  {event['action']:<18} "
                f"{event['actor'] or '-':<10} {event['detail']}"
            )


@revenue_group.command("report")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "csv"]),
    default="text",
    show_default=True,
)
@click.option(
    "--days",
    "renewal_days",
    type=int,
    default=14,
    show_default=True,
    help="renewal window in days",
)
@click.option(
    "--as-of",
    default=None,
    help="ISO date used to evaluate renewals (default: today)",
)
def report_command(output_format, renewal_days, as_of):
    """Report MRR, collections, balances, plan mix, and renewals."""
    from pathlib import Path

    from drugshop.billing import report as report_service
    from drugshop.db import db_path

    path = Path(db_path())
    if not path.is_file():
        raise click.ClickException(f"database not found: {path}")

    db = None
    try:
        # Reporting is read-only: never open the customer database writable.
        db = report_service.connect_readonly(path)
        data = report_service.build_report(
            db,
            source=str(path),
            renewal_days=renewal_days,
            as_of=as_of,
        )
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    finally:
        if db is not None:
            db.close()

    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
        return
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(
            buffer,
            fieldnames=report_service.CSV_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(report_service.csv_rows([data]))
        click.echo(buffer.getvalue(), nl=False)
        return
    for line in _report_lines(data):
        click.echo(line)


@revenue_group.command("activate")
@click.argument("bundle")
@click.option("--customer", required=True, help="customer / shop name")
@click.option("--contact", "contact_phone", default="", help="contact phone or WhatsApp")
@click.option("--contact-name", default="", help="contact person")
@click.option("--start", default=None, help="ISO start date (default: today)")
@click.option(
    "--period-end",
    default=None,
    help="ISO period end; required for paid bundles",
)
@click.option("--actor", default="", help="who made the change")
@click.option("--notes", default="", help="free-text note stored with the event")
@click.option(
    "--setup-fee",
    type=int,
    default=None,
    help="override setup fee; requires --override-reason",
)
@click.option(
    "--monthly-fee",
    type=int,
    default=None,
    help="override monthly fee; requires --override-reason",
)
@click.option(
    "--override-reason",
    default="",
    help="why the price-book fee was overridden",
)
@click.option(
    "--grandfathered",
    is_flag=True,
    help="required for legacy; monthly fee is forced to 0",
)
@click.option("--currency", default=CURRENCY, show_default=True)
def activate_command(
    bundle,
    customer,
    contact_phone,
    contact_name,
    start,
    period_end,
    actor,
    notes,
    setup_fee,
    monthly_fee,
    override_reason,
    grandfathered,
    currency,
):
    """Record the agreement and activate BUNDLE (core|pro|growth|tender|legacy)."""
    from drugshop.billing import service

    try:
        result = service.activate(
            bundle,
            customer_name=customer,
            contact_name=contact_name,
            contact_phone=contact_phone,
            start=start,
            period_end=period_end,
            actor=actor,
            notes=notes,
            setup_fee=setup_fee,
            monthly_fee=monthly_fee,
            override_reason=override_reason,
            grandfathered=grandfathered,
            currency=currency,
        )
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    subscription = result["subscription"]
    click.echo(f"{result['note'].capitalize()}: {bundle_label(subscription['bundle'])}")
    _print_subscription(subscription, result.get("apps"))


@revenue_group.command("renew")
@click.option("--period-end", required=True, help="new ISO period end")
@click.option("--actor", default="", help="who made the change")
@click.option("--notes", default="", help="free-text note stored with the event")
def renew_command(period_end, actor, notes):
    """Extend the current billing period and refresh entitlement expiry."""
    from drugshop.billing import service

    try:
        result = service.renew(period_end, actor=actor, notes=notes)
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    subscription = result["subscription"]
    click.echo(
        f"Renewed: {bundle_label(subscription['bundle'])} until "
        f"{subscription['current_period_end']}"
    )
    _print_subscription(subscription, result.get("apps"))


@revenue_group.command("status")
@click.argument("status")
@click.option("--actor", default="", help="who made the change")
@click.option("--notes", default="", help="free-text note stored with the event")
def status_command(status, actor, notes):
    """Set STATUS (active | past_due | cancelled | expired)."""
    from drugshop.billing import service

    try:
        result = service.set_status(status, actor=actor, notes=notes)
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    subscription = result["subscription"]
    if result["note"] == "unchanged":
        click.echo(f"Status unchanged: {subscription['status']}")
        return
    click.echo(f"Status: {subscription['status']}")
    click.echo(f"Customer: {subscription['customer_name']}")


@revenue_group.group("invoice")
def invoice_group():
    """Create and list invoices for this installation."""


@invoice_group.command("setup")
@click.option(
    "--due",
    "due_date",
    default=None,
    help="ISO due date (default: issue date)",
)
@click.option(
    "--issue-date",
    default=None,
    help="ISO issue date (default: today)",
)
@click.option("--actor", default="", help="who issued the invoice")
@click.option("--notes", default="", help="free-text note stored on the invoice")
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def invoice_setup_command(due_date, issue_date, actor, notes, as_json):
    """Create a setup invoice for the agreed setup fee."""
    from drugshop.billing import service

    try:
        invoice = service.create_setup_invoice(
            due_date=due_date,
            issue_date=issue_date,
            actor=actor,
            notes=notes,
        )
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(invoice, indent=2))
        return
    click.echo("Invoice created.")
    _print_invoice(invoice)


@invoice_group.command("monthly")
@click.option("--period-start", required=True, help="ISO first day of the period")
@click.option("--period-end", required=True, help="ISO last day of the period")
@click.option(
    "--due",
    "due_date",
    default=None,
    help="ISO due date (default: period start)",
)
@click.option(
    "--issue-date",
    default=None,
    help="ISO issue date (default: today)",
)
@click.option("--actor", default="", help="who issued the invoice")
@click.option("--notes", default="", help="free-text note stored on the invoice")
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def invoice_monthly_command(
    period_start,
    period_end,
    due_date,
    issue_date,
    actor,
    notes,
    as_json,
):
    """Create a monthly invoice for the agreed monthly fee and period."""
    from drugshop.billing import service

    try:
        invoice = service.create_monthly_invoice(
            period_start,
            period_end,
            due_date=due_date,
            issue_date=issue_date,
            actor=actor,
            notes=notes,
        )
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(invoice, indent=2))
        return
    click.echo("Invoice created.")
    _print_invoice(invoice)


@invoice_group.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def invoice_list_command(as_json):
    """List every invoice with amount, paid, and balance."""
    from drugshop.billing import service

    try:
        rows = service.invoices()
    except sqlite3.Error as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("No invoices recorded.")
        return
    for invoice in rows:
        click.echo(_invoice_line(invoice))


@invoice_group.command("show")
@click.argument("invoice_no")
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def invoice_show_command(invoice_no, as_json):
    """Show one invoice and its payment ledger."""
    from drugshop.billing import service

    try:
        invoice = service.invoice_detail(invoice_no)
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(invoice, indent=2))
        return
    _print_invoice(invoice)
    payments = invoice["payments"]
    if not payments:
        click.echo("Payments:    none")
        return
    click.echo("Payments:")
    for payment in payments:
        click.echo(f"  {_payment_line(payment)}")


@invoice_group.command("void")
@click.argument("invoice_no")
@click.option("--actor", default="", help="who voided the invoice")
@click.option("--reason", default="", help="why the invoice was voided")
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def invoice_void_command(invoice_no, actor, reason, as_json):
    """Void an invoice; an invoice with recorded payments cannot be voided."""
    from drugshop.billing import service

    try:
        invoice = service.void_invoice(
            invoice_no,
            actor=actor,
            reason=reason,
        )
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(invoice, indent=2))
        return
    click.echo("Invoice voided.")
    _print_invoice(invoice)


@revenue_group.group("payment")
def payment_group():
    """Record manual payments against an invoice."""


@payment_group.command("record")
@click.argument("invoice_no")
@click.option("--amount", type=int, required=True, help="amount received in UGX")
@click.option(
    "--method",
    required=True,
    help="cash | bank | mtn_momo | airtel_money | other",
)
@click.option(
    "--paid-on",
    default=None,
    help="ISO payment date (default: today)",
)
@click.option("--reference", default="", help="bank or mobile-money reference")
@click.option("--received-by", default="", help="who received the payment")
@click.option("--notes", default="", help="free-text note stored with the payment")
@click.option("--actor", default="", help="who recorded the payment")
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def payment_record_command(
    invoice_no,
    amount,
    method,
    paid_on,
    reference,
    received_by,
    notes,
    actor,
    as_json,
):
    """Record a manual payment; no gateway or carrier call is made."""
    from drugshop.billing import service

    try:
        invoice = service.record_payment(
            invoice_no,
            amount,
            method,
            paid_on=paid_on,
            reference=reference,
            received_by=received_by,
            notes=notes,
            actor=actor,
        )
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(invoice, indent=2))
        return
    click.echo("Payment recorded.")
    _print_invoice(invoice)


@revenue_group.command("renewals")
@click.option("--days", type=int, default=14, show_default=True)
@click.option(
    "--as-of",
    default=None,
    help="ISO date used to evaluate the window (default: today)",
)
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
def renewals_command(days, as_of, as_json):
    """List renewals due within DAYS, including overdue subscriptions."""
    from drugshop.billing import service

    try:
        rows = service.renewals(days=days, as_of=as_of)
    except (ValueError, sqlite3.Error) as exc:
        raise click.ClickException(_error_message(exc)) from exc
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo(f"No renewals due in the next {days} days.")
        return
    for row in rows:
        if row["overdue"]:
            state = f"overdue by {-row['days_until']} days"
        else:
            state = f"due in {row['days_until']} days"
        click.echo(
            f"{row['customer_name']}  {bundle_label(row['bundle'])}  "
            f"ends {row['current_period_end']}  {state}  "
            f"{_format_money(row['monthly_fee'])} {row['currency']}/month"
        )


def register_cli(app):
    app.cli.add_command(revenue_group)
