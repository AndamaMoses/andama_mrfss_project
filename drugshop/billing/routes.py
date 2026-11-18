"""Read-only subscription API for the Plan & Apps card.

The customer sees what they own, when it renews, and (admins only) the invoice
ledger. There are no write endpoints here: activation, invoicing, and payment
recording remain operator CLI actions.

The payload deliberately excludes commercial internals — setup fees, price-book
version, invoice notes, payment notes, and row ids never leave the server.
"""
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from drugshop import db as dbm
from drugshop.apps import service as apps_service
from drugshop.apps.registry import bundle_label
from drugshop.auth.guards import admin_required
from drugshop.billing import report as report_service
from drugshop.billing import service
from drugshop.billing.catalog import (
    CURRENCY,
    PRICE_BOOK,
    PRICE_BOOK_VERSION,
    SETUP_DISCOUNT_CAP,
)

bp = Blueprint("billing", __name__)


def _money(value):
    amount = float(value or 0)
    return int(amount) if amount.is_integer() else amount


def _support():
    return {"whatsapp": current_app.config.get("SUPPORT_WHATSAPP") or ""}


def _plan_payload(subscription):
    """Commercial plan summary, or the entitlement plan before a billing row."""
    if subscription is None:
        try:
            plan = apps_service.current_plan()
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            plan = {
                "bundle": "unseeded",
                "label": "Unseeded",
                "status": "active",
                "expires_at": None,
            }
        # A Legacy entitlement install with no billing row is the grandfathered
        # pilot state: show it as such rather than as a fresh paid plan.
        status = "grandfathered" if plan["bundle"] == "legacy" else plan["status"]
        return {
            "bundle": plan["bundle"],
            "label": plan["label"],
            "status": status,
            "started_on": None,
            "current_period_end": plan["expires_at"],
            "monthly_fee": 0,
            "currency": CURRENCY,
        }
    return {
        "bundle": subscription["bundle"],
        "label": bundle_label(subscription["bundle"]),
        "status": subscription["status"],
        "started_on": subscription["started_on"],
        "current_period_end": subscription["current_period_end"],
        "monthly_fee": _money(subscription["monthly_fee"]),
        "currency": subscription["currency"] or CURRENCY,
    }


def _invoice_payload(invoice):
    """Invoice fields safe for the customer-facing ledger."""
    return {
        "invoice_no": invoice["invoice_no"],
        "kind": invoice["kind"],
        "issue_date": invoice["issue_date"],
        "due_date": invoice["due_date"],
        "period_start": invoice["period_start"],
        "period_end": invoice["period_end"],
        "amount": _money(invoice["amount"]),
        "currency": invoice["currency"],
        "status": invoice["status"],
        "paid": _money(invoice["paid"]),
        "balance": _money(invoice["balance"]),
        "payment_count": invoice["payment_count"],
    }


def _payment_payload(payment):
    """Payment fields safe for the customer-facing ledger."""
    return {
        "paid_on": payment["paid_on"],
        "amount": _money(payment["amount"]),
        "currency": payment["currency"],
        "method": payment["method"],
        "reference": payment["reference"],
        "received_by": payment["received_by"],
    }


def _billing_reads():
    """Read the commercial rows, failing open before the 008 migration.

    A freshly deployed app always runs ``init_db()`` first, but the apps API
    already fails open on a missing schema and this read-only panel should not
    be the one screen that returns a 500 during an upgrade window.
    """
    try:
        subscription = service.current_subscription()
        invoices = service.invoices()
        renewal_due = bool(service.renewals())
        return subscription, invoices, renewal_due
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        current_app.logger.warning(
            "billing unavailable (%s); reporting entitlement plan only", exc
        )
        return None, [], False


@bp.route("/api/subscription")
def api_subscription():
    """Limited plan, balance, renewal, and support summary for any signed-in user."""
    subscription, invoices, renewal_due = _billing_reads()
    balance = sum(float(row["balance"] or 0) for row in invoices)
    return jsonify({
        "plan": _plan_payload(subscription),
        "balance": _money(balance),
        "renewal_due": renewal_due,
        "support": _support(),
    })


@bp.route("/api/subscription/invoices")
@admin_required
def api_subscription_invoices():
    """Admin-only invoice list; payments and notes stay in the detail route."""
    try:
        invoices = service.invoices()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        invoices = []
    return jsonify([_invoice_payload(row) for row in invoices])


@bp.route("/api/subscription/invoices/<invoice_no>")
@admin_required
def api_subscription_invoice(invoice_no):
    """Admin-only invoice detail with its payment ledger."""
    try:
        invoice = service.invoice_detail(invoice_no)
    except service.BillingError:
        return jsonify({"error": "invoice not found"}), 404
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        return jsonify({"error": "invoice not found"}), 404

    payload = _invoice_payload(invoice)
    payload["payments"] = [
        _payment_payload(payment) for payment in invoice["payments"]
    ]
    return jsonify(payload)


def _payment_row_payload(payment):
    """Payment ledger row for the admin Revenue tab."""
    return {
        "invoice_no": payment["invoice_no"],
        "invoice_kind": payment["invoice_kind"],
        "paid_on": payment["paid_on"],
        "amount": _money(payment["amount"]),
        "currency": payment["currency"],
        "method": payment["method"],
        "reference": payment["reference"],
        "received_by": payment["received_by"],
    }


def _window_args():
    """Parse the renewal window, returning (days, as_of, error_response)."""
    days = request.args.get("days", default=14, type=int)
    if days is None or days < 0 or days > 3650:
        return None, None, (jsonify({"error": "days must be 0-3650"}), 400)
    as_of = (request.args.get("as_of") or "").strip() or None
    return days, as_of, None


@bp.route("/api/subscription/pricebook")
@admin_required
def api_subscription_pricebook():
    """Admin-only price book: what is sold, at what setup and monthly fee."""
    return jsonify({
        "version": PRICE_BOOK_VERSION,
        "currency": CURRENCY,
        "setup_discount_cap": _money(SETUP_DISCOUNT_CAP),
        "offers": [
            {
                "id": offer.id,
                "label": offer.label,
                "setup": _money(offer.setup),
                "monthly": _money(offer.monthly),
                "roles": list(offer.roles),
                "requires": [
                    {"id": required, "label": PRICE_BOOK[required].label}
                    for required in offer.requires
                ],
                "description": offer.description,
            }
            for offer in PRICE_BOOK.values()
        ],
    })


@bp.route("/api/subscription/report")
@admin_required
def api_subscription_report():
    """Admin-only revenue report, read through a read-only connection.

    Unlike the other endpoints this opens the database file directly with
    ``mode=ro`` so the report cannot write even by accident. The filesystem
    path is never returned to the browser.
    """
    days, as_of, error = _window_args()
    if error is not None:
        return error

    try:
        conn = report_service.connect_readonly(Path(dbm.db_path()))
    except (sqlite3.Error, OSError) as exc:
        current_app.logger.warning("report unavailable (%s)", exc)
        return jsonify({"error": "report unavailable"}), 503

    try:
        payload = report_service.build_report(
            conn, source=None, renewal_days=days, as_of=as_of
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except sqlite3.Error as exc:
        current_app.logger.warning("report failed (%s)", exc)
        return jsonify({"error": "report unavailable"}), 503
    finally:
        conn.close()

    return jsonify(payload)


@bp.route("/api/subscription/payments")
@admin_required
def api_subscription_payments():
    """Admin-only payment ledger across every invoice."""
    try:
        rows = service.payments()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        rows = []
    return jsonify([_payment_row_payload(row) for row in rows])


@bp.route("/api/subscription/renewals")
@admin_required
def api_subscription_renewals():
    """Admin-only renewal queue for the next DAYS days, overdue included."""
    days, as_of, error = _window_args()
    if error is not None:
        return error
    try:
        rows = service.renewals(days=days, as_of=as_of)
    except service.BillingError as exc:
        return jsonify({"error": str(exc)}), 400
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        rows = []
    return jsonify(rows)
