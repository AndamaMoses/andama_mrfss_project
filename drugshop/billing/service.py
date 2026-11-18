"""Subscription ledger, invoicing, and activation service (Phases 2-3).

Commercial terms live in ``billing_subscriptions``; access continues to live in
``app_entitlements``. Activation writes both in one operator action, but never
pretends they are the same record:

1. validate the bundle, dates, fees, currency, and operator input;
2. write a ``pending`` subscription plus a ``billing_events`` row;
3. call the entitlement service to set the bundle;
4. mark the subscription ``active`` (or ``grandfathered`` for Legacy).

If step 3 fails the subscription stays ``pending`` so the operator can retry.
If step 4 fails the error says the entitlements changed but the commercial
record did not, rather than rolling back silently.

All writes are operator CLI actions. The customer UI is read-only.
"""
import math
import sqlite3
from datetime import date

from drugshop.apps import service as apps_service
from drugshop.billing.catalog import (
    BASE_IDS,
    CURRENCY,
    PRICE_BOOK_VERSION,
    SETUP_DISCOUNT_CAP,
    quote,
)
from drugshop.db import get_db, q_all, q_one

ACTIVATABLE_BUNDLES = ("core", "pro", "growth", "tender", "legacy")
STATUSES = (
    "pending",
    "active",
    "past_due",
    "cancelled",
    "expired",
    "grandfathered",
)
ALLOWED_TRANSITIONS = {
    "pending": {"cancelled"},
    "active": {"past_due", "cancelled", "expired"},
    "past_due": {"active", "cancelled", "expired"},
    "cancelled": set(),
    "expired": {"cancelled"},
    "grandfathered": {"cancelled"},
}
INVOICE_KINDS = ("setup", "monthly", "addon", "other")
INVOICE_STATUSES = ("draft", "unpaid", "partial", "paid", "void")
PAYMENT_METHODS = ("cash", "bank", "mtn_momo", "airtel_money", "other")


class BillingError(ValueError):
    """Raised when a commercial action is invalid."""


# ---------- reads ----------
def current_subscription():
    """Return the installation's single subscription row, or None."""
    return q_one("SELECT * FROM billing_subscriptions WHERE id = 1")


def subscription_events(limit=20):
    """Most recent commercial events, newest first."""
    return q_all(
        "SELECT * FROM billing_events ORDER BY id DESC LIMIT ?",
        (max(1, int(limit)),),
    )


def reconciliation():
    """Compare the commercial bundle/date with the entitlement plan.

    The two records are deliberately separate. This helper is used by
    ``revenue show`` and by tests/rollout checks to prove they agree.
    """
    subscription = current_subscription()
    plan = apps_service.current_plan()
    expected_expiry = (subscription["current_period_end"] or None) if subscription else None
    agrees = bool(
        subscription
        and plan["bundle"] == subscription["bundle"]
        and (plan["expires_at"] or None) == expected_expiry
    )
    return {"agrees": agrees, "plan": plan, "subscription": subscription}


# ---------- validation ----------
def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _required_text(value, label):
    text = _text(value)
    if not text:
        raise BillingError(f"{label} is required")
    return text


def _normalize_date(value, label):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except (TypeError, ValueError) as exc:
        raise BillingError(f"{label} must be an ISO date (YYYY-MM-DD)") from exc


def _validate_currency(currency):
    value = _text(currency).upper()
    if not value:
        raise BillingError("currency is required")
    if value != CURRENCY:
        raise BillingError(f"v1 subscriptions must use {CURRENCY}")
    return value


def _normalize_bundle(bundle, grandfathered):
    value = _text(bundle).lower()
    if not value:
        raise BillingError("bundle is required")
    if value not in ACTIVATABLE_BUNDLES:
        raise BillingError(
            f"unknown bundle {value!r} (choose: {', '.join(ACTIVATABLE_BUNDLES)})"
        )
    if grandfathered and value != "legacy":
        raise BillingError("--grandfathered is only valid for legacy")
    if value == "legacy" and not grandfathered:
        raise BillingError("legacy activation requires --grandfathered")
    return value


def _fee(value, label, default):
    if value is None:
        return int(default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BillingError(f"{label} must be a whole number of {CURRENCY}")
    if not math.isfinite(float(value)):
        raise BillingError(f"{label} must be a whole number of {CURRENCY}")
    if float(value) != int(value):
        raise BillingError(f"{label} must be a whole number of {CURRENCY}")
    amount = int(value)
    if amount < 0:
        raise BillingError(f"{label} cannot be negative")
    return amount


def _default_fees(bundle):
    if bundle == "legacy":
        return 0, 0
    if bundle == "growth":
        result = quote("pro", addons=("growth",))
    elif bundle in BASE_IDS:
        result = quote(bundle)
    else:
        raise BillingError(f"bundle {bundle!r} has no price-book fees")
    return result.setup_total, result.monthly_total


def _resolve_fees(bundle, setup_fee, monthly_fee, override_reason):
    default_setup, default_monthly = _default_fees(bundle)
    setup = _fee(setup_fee, "setup fee", default_setup)
    monthly = _fee(monthly_fee, "monthly fee", default_monthly)
    reason = _text(override_reason)

    if bundle == "legacy":
        if monthly != 0:
            raise BillingError("legacy grandfathered subscriptions must have monthly fee 0")
        if setup != default_setup and not reason:
            raise BillingError("fee override requires --override-reason")
        return setup, 0

    minimum_setup = default_setup - SETUP_DISCOUNT_CAP
    if setup < minimum_setup:
        raise BillingError(
            f"setup fee {setup:,} is below the allowed minimum {minimum_setup:,} "
            f"({SETUP_DISCOUNT_CAP:,} {CURRENCY} setup-discount cap)"
        )
    if monthly < default_monthly:
        raise BillingError(
            f"monthly fee {monthly:,} cannot be below the price-book fee "
            f"{default_monthly:,} {CURRENCY}"
        )
    if (setup != default_setup or monthly != default_monthly) and not reason:
        raise BillingError("fee override requires --override-reason")
    return setup, monthly


def _terms(
    bundle,
    customer_name,
    contact_name,
    contact_phone,
    currency,
    setup_fee,
    monthly_fee,
    start_date,
    period_start,
    period_end,
    price_book_version,
    notes,
):
    return {
        "customer_name": customer_name,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "bundle": bundle,
        "status": "grandfathered" if bundle == "legacy" else "active",
        "currency": currency,
        "setup_fee": setup_fee,
        "monthly_fee": monthly_fee,
        "started_on": start_date,
        "current_period_start": period_start,
        "current_period_end": period_end,
        "price_book_version": price_book_version,
        "notes": notes,
    }


def _terms_detail(terms, override_reason="", extra=""):
    parts = [
        f"bundle={terms['bundle']}",
        f"customer={terms['customer_name']}",
        f"setup={terms['setup_fee']:,}",
        f"monthly={terms['monthly_fee']:,}",
        "period="
        f"{terms['current_period_start'] or '-'}..{terms['current_period_end'] or '-'}",
        f"price_book={terms['price_book_version']}",
    ]
    if override_reason:
        parts.append(f"override={override_reason}")
    if terms["notes"]:
        parts.append(f"notes={terms['notes']}")
    if extra:
        parts.append(extra)
    return "; ".join(parts)


def _same_terms(row, terms):
    for key in (
        "customer_name",
        "contact_name",
        "contact_phone",
        "bundle",
        "status",
        "currency",
        "started_on",
        "current_period_start",
        "current_period_end",
        "price_book_version",
        "notes",
    ):
        if (row[key] or "") != (terms[key] or ""):
            return False
    return (
        float(row["setup_fee"] or 0) == float(terms["setup_fee"] or 0)
        and float(row["monthly_fee"] or 0) == float(terms["monthly_fee"] or 0)
    )


# ---------- write helpers ----------
def _log(db, action, actor, detail):
    db.execute(
        "INSERT INTO billing_events(subscription_id, action, actor, detail) "
        "VALUES(1,?,?,?)",
        (action, _text(actor), detail),
    )


def _log_failure(action, actor, detail):
    """Best-effort audit row for a failed entitlement/DB step."""
    db = get_db()
    try:
        _log(db, action, actor, detail)
        db.commit()
    except sqlite3.Error:
        db.rollback()
    finally:
        db.close()


def _insert_subscription(db, terms, status):
    db.execute(
        "INSERT INTO billing_subscriptions("
        "id, customer_name, contact_name, contact_phone, bundle, status, currency,"
        " setup_fee, monthly_fee, started_on, current_period_start,"
        " current_period_end, price_book_version, notes"
        ") VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            terms["customer_name"],
            terms["contact_name"],
            terms["contact_phone"],
            terms["bundle"],
            status,
            terms["currency"],
            terms["setup_fee"],
            terms["monthly_fee"],
            terms["started_on"],
            terms["current_period_start"],
            terms["current_period_end"],
            terms["price_book_version"],
            terms["notes"],
        ),
    )


def _update_subscription(db, terms, status):
    db.execute(
        "UPDATE billing_subscriptions SET"
        " customer_name=?, contact_name=?, contact_phone=?, bundle=?, status=?,"
        " currency=?, setup_fee=?, monthly_fee=?, started_on=?,"
        " current_period_start=?, current_period_end=?, price_book_version=?,"
        " notes=?, updated_at=datetime('now','localtime')"
        " WHERE id=1",
        (
            terms["customer_name"],
            terms["contact_name"],
            terms["contact_phone"],
            terms["bundle"],
            status,
            terms["currency"],
            terms["setup_fee"],
            terms["monthly_fee"],
            terms["started_on"],
            terms["current_period_start"],
            terms["current_period_end"],
            terms["price_book_version"],
            terms["notes"],
        ),
    )


# ---------- activation ----------
def activate(
    bundle,
    customer_name,
    contact_name="",
    contact_phone="",
    start=None,
    period_end=None,
    actor="",
    notes="",
    setup_fee=None,
    monthly_fee=None,
    override_reason="",
    grandfathered=False,
    currency=CURRENCY,
):
    """Create or update the installation's subscription and entitlements.

    The same call is idempotent: if every term already matches an active (or
    grandfathered) row, the entitlement set is reconciled and no event is
    written. A different call is an auditable plan change.
    """
    bundle = _normalize_bundle(bundle, grandfathered)
    customer = _required_text(customer_name, "customer")
    contact_name = _text(contact_name)
    contact_phone = _text(contact_phone)
    currency = _validate_currency(currency)
    start_date = _normalize_date(start, "start") or date.today().isoformat()
    end_date = _normalize_date(period_end, "period-end")
    override_reason = _text(override_reason)
    notes = _text(notes)

    if bundle == "legacy":
        if end_date is not None:
            raise BillingError(
                "legacy grandfathered subscriptions do not use --period-end"
            )
        period_start = None
        price_book_version = "legacy"
    else:
        if end_date is None:
            raise BillingError("--period-end is required for paid bundles")
        if end_date <= start_date:
            raise BillingError("period-end must be after start")
        period_start = start_date
        price_book_version = PRICE_BOOK_VERSION

    setup, monthly = _resolve_fees(
        bundle, setup_fee, monthly_fee, override_reason
    )
    terms = _terms(
        bundle=bundle,
        customer_name=customer,
        contact_name=contact_name,
        contact_phone=contact_phone,
        currency=currency,
        setup_fee=setup,
        monthly_fee=monthly,
        start_date=start_date,
        period_start=period_start,
        period_end=end_date,
        price_book_version=price_book_version,
        notes=notes,
    )
    existing = current_subscription()
    detail = _terms_detail(terms, override_reason)

    if existing and _same_terms(existing, terms):
        try:
            result = apps_service.set_bundle(
                bundle, expires_at=end_date, actor=actor, notes=notes
            )
        except (ValueError, sqlite3.Error) as exc:
            _log_failure(
                "reconcile_failed", actor, f"bundle={bundle}; error={exc}"
            )
            raise BillingError(
                "subscription is already "
                f"{terms['status']} but entitlements could not be confirmed: {exc}"
            ) from exc
        return {
            "ok": True,
            "note": f"already {terms['status']}",
            "subscription": current_subscription(),
            "apps": result["active"],
        }

    if existing is None or existing["status"] == "pending":
        db = get_db()
        try:
            if existing is None:
                _insert_subscription(db, terms, "pending")
            else:
                _update_subscription(db, terms, "pending")
            _log(db, "activate", actor, detail)
            db.commit()
        except sqlite3.Error:
            db.rollback()
            raise
        finally:
            db.close()

        try:
            result = apps_service.set_bundle(
                bundle, expires_at=end_date, actor=actor, notes=notes
            )
        except (ValueError, sqlite3.Error) as exc:
            _log_failure(
                "activate_failed", actor, f"bundle={bundle}; error={exc}"
            )
            raise BillingError(
                "entitlement step failed; subscription remains pending: "
                f"{exc}"
            ) from exc

        db = get_db()
        try:
            _update_subscription(db, terms, terms["status"])
            db.commit()
        except sqlite3.Error as exc:
            db.rollback()
            _log_failure(
                "activate_update_failed",
                actor,
                f"bundle={bundle}; error={exc}",
            )
            raise BillingError(
                "entitlements were changed but the subscription could not be "
                "marked active; run `flask --app run revenue show` and retry"
            ) from exc
        finally:
            db.close()
        return {
            "ok": True,
            "note": "activated",
            "subscription": current_subscription(),
            "apps": result["active"],
        }

    # An existing live row changes terms only after entitlements succeed, so a
    # failure leaves the old commercial agreement intact.
    try:
        result = apps_service.set_bundle(
            bundle, expires_at=end_date, actor=actor, notes=notes
        )
    except (ValueError, sqlite3.Error) as exc:
        _log_failure("change_failed", actor, f"bundle={bundle}; error={exc}")
        raise BillingError(
            f"entitlement change failed; subscription remains "
            f"{existing['status']}: {exc}"
        ) from exc

    db = get_db()
    try:
        _update_subscription(db, terms, terms["status"])
        _log(db, "change", actor, detail)
        db.commit()
    except sqlite3.Error as exc:
        db.rollback()
        _log_failure(
            "change_update_failed", actor, f"bundle={bundle}; error={exc}"
        )
        raise BillingError(
            "entitlements were changed but the subscription record could not "
            "be updated; run `flask --app run revenue show` and retry"
        ) from exc
    finally:
        db.close()
    return {
        "ok": True,
        "note": "changed",
        "subscription": current_subscription(),
        "apps": result["active"],
    }


# ---------- renewal and status ----------
def renew(period_end, actor="", notes=""):
    """Extend the current period and refresh the entitlement expiry."""
    end_date = _normalize_date(period_end, "period-end")
    if end_date is None:
        raise BillingError("--period-end is required")
    subscription = current_subscription()
    if subscription is None:
        raise BillingError(
            "no subscription recorded; run `flask --app run revenue activate` first"
        )
    status = subscription["status"]
    if status == "grandfathered":
        raise BillingError("grandfathered subscriptions do not renew")
    if status == "cancelled":
        raise BillingError("cancelled subscriptions must be reactivated before renewal")
    if status not in ("active", "past_due", "expired"):
        raise BillingError(f"cannot renew a {status} subscription")

    old_start = subscription["current_period_start"] or subscription["started_on"]
    old_end = subscription["current_period_end"] or subscription["started_on"]
    if end_date <= old_end:
        raise BillingError(f"new period end must be after {old_end}")

    try:
        result = apps_service.set_bundle(
            subscription["bundle"],
            expires_at=end_date,
            actor=actor,
            notes=_text(notes),
        )
    except (ValueError, sqlite3.Error) as exc:
        _log_failure(
            "renew_failed",
            actor,
            f"bundle={subscription['bundle']}; error={exc}",
        )
        raise BillingError(
            f"renewal failed; subscription remains {status}: {exc}"
        ) from exc

    terms = dict(subscription)
    terms.update(
        {
            "current_period_start": old_end,
            "current_period_end": end_date,
        }
    )
    detail = f"period {old_start}..{old_end} -> {old_end}..{end_date}"
    if _text(notes):
        detail = f"{detail}; notes={_text(notes)}"
    db = get_db()
    try:
        _update_subscription(db, terms, "active")
        _log(db, "renew", actor, detail)
        db.commit()
    except sqlite3.Error as exc:
        db.rollback()
        _log_failure(
            "renew_update_failed",
            actor,
            f"bundle={subscription['bundle']}; error={exc}",
        )
        raise BillingError(
            "entitlements were renewed but the subscription record could not "
            "be updated; run `flask --app run revenue show` and retry"
        ) from exc
    finally:
        db.close()
    return {
        "ok": True,
        "subscription": current_subscription(),
        "apps": result["active"],
    }


def set_status(status, actor="", notes=""):
    """Move the subscription to a valid status without changing access."""
    target = _text(status).lower()
    if target not in STATUSES:
        raise BillingError(
            f"unknown status {target!r} (choose: {', '.join(STATUSES)})"
        )
    subscription = current_subscription()
    if subscription is None:
        raise BillingError(
            "no subscription recorded; run `flask --app run revenue activate` first"
        )
    current = subscription["status"]
    if target == current:
        return {
            "ok": True,
            "note": "unchanged",
            "subscription": subscription,
        }
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        if target == "grandfathered":
            raise BillingError(
                "use `revenue activate legacy --grandfathered` to create a "
                "grandfathered subscription"
            )
        if current == "pending":
            raise BillingError(
                "pending subscriptions become active through activation; "
                "re-run `revenue activate`"
            )
        if current == "cancelled":
            raise BillingError(
                "cancelled subscriptions must be reactivated with "
                "`revenue activate`"
            )
        raise BillingError(
            f"cannot change status from {current} to {target}"
        )

    detail = f"from {current} to {target}"
    if _text(notes):
        detail = f"{detail} - {_text(notes)}"
    db = get_db()
    try:
        db.execute(
            "UPDATE billing_subscriptions SET status=?,"
            " updated_at=datetime('now','localtime') WHERE id=1",
            (target,),
        )
        _log(db, "status", actor, detail)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()
    return {
        "ok": True,
        "note": target,
        "subscription": current_subscription(),
    }


# ---------- invoices and payments ----------
def _money_value(value):
    amount = float(value or 0)
    return int(amount) if amount.is_integer() else amount


def _positive_money(value, label):
    amount = _fee(value, label, 0)
    if amount <= 0:
        raise BillingError(f"{label} must be greater than zero")
    return amount


def _require_subscription():
    subscription = current_subscription()
    if subscription is None:
        raise BillingError(
            "no subscription recorded; run `flask --app run revenue activate` first"
        )
    return subscription


def _normalize_kind(kind):
    value = _text(kind).lower()
    if value not in INVOICE_KINDS:
        raise BillingError(
            f"unknown invoice kind {value!r} (choose: {', '.join(INVOICE_KINDS)})"
        )
    return value


def _normalize_method(method):
    value = _text(method).lower()
    if not value:
        raise BillingError(
            "payment method is required "
            f"(choose: {', '.join(PAYMENT_METHODS)})"
        )
    if value not in PAYMENT_METHODS:
        raise BillingError(
            f"unknown payment method {value!r} "
            f"(choose: {', '.join(PAYMENT_METHODS)})"
        )
    return value


def _invoice_number(value):
    """Normalize operator input to the stored form: ``INV-YYYYMM-####``."""
    return _required_text(value, "invoice number").upper()


def _begin_immediate(db):
    """Take SQLite's writer lock before reading a balance or numbering a row.

    Without it, two operator processes could both read the same remaining
    balance (or the same highest invoice number) and then both write.
    """
    db.isolation_level = None
    try:
        db.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise BillingError(
                "database is busy; close the shop screen or retry in a moment"
            ) from exc
        raise


def _invoice_payload(row):
    amount = float(row["amount"] or 0)
    paid = float(row.get("paid") or 0)
    # A void invoice stays in the ledger for audit, but nothing is owed on it.
    balance = 0.0 if row["status"] == "void" else max(0.0, amount - paid)
    return {
        "id": row["id"],
        "invoice_no": row["invoice_no"],
        "kind": row["kind"],
        "issue_date": row["issue_date"],
        "due_date": row["due_date"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "amount": _money_value(amount),
        "currency": row["currency"],
        "status": row["status"],
        "paid": _money_value(paid),
        "balance": _money_value(balance),
        "payment_count": int(row.get("payment_count") or 0),
        "notes": row["notes"],
        "created_at": row["created_at"],
    }


def invoices():
    """Return every invoice, newest first, with paid and balance totals."""
    rows = q_all(
        "SELECT i.*, COALESCE(SUM(p.amount), 0) AS paid, "
        "COUNT(p.id) AS payment_count "
        "FROM billing_invoices i "
        "LEFT JOIN billing_payments p ON p.invoice_id = i.id "
        "GROUP BY i.id ORDER BY i.id DESC"
    )
    return [_invoice_payload(row) for row in rows]


def invoice_detail(invoice_no):
    """Return one invoice with its payment ledger and remaining balance."""
    number = _invoice_number(invoice_no)
    row = q_one("SELECT * FROM billing_invoices WHERE invoice_no = ?", (number,))
    if row is None:
        raise BillingError(f"invoice {number!r} not found")
    totals = q_one(
        "SELECT COALESCE(SUM(amount), 0) AS paid, COUNT(*) AS payment_count "
        "FROM billing_payments WHERE invoice_id = ?",
        (row["id"],),
    )
    row.update(totals)
    payload = _invoice_payload(row)
    payments = q_all(
        "SELECT id, paid_on, amount, currency, method, reference, received_by, "
        "notes, created_at FROM billing_payments "
        "WHERE invoice_id = ? ORDER BY id",
        (row["id"],),
    )
    for payment in payments:
        payment["amount"] = _money_value(payment["amount"])
    payload["payments"] = payments
    return payload


def _next_invoice_no(db, issue_date):
    """Next number in the issue month: INV-YYYYMM-####.

    The sequence is per installation and resets each month; the month prefix
    keeps the full number unique across the installation.
    """
    prefix = f"INV-{issue_date[0:4]}{issue_date[5:7]}-"
    rows = db.execute(
        "SELECT invoice_no FROM billing_invoices WHERE invoice_no LIKE ?",
        (prefix + "%",),
    ).fetchall()
    highest = 0
    for row in rows:
        suffix = str(row[0]).rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:04d}"


def _invoice_event_text(
    invoice_no,
    kind,
    amount,
    due_date,
    period_start=None,
    period_end=None,
    notes="",
):
    parts = [
        f"invoice={invoice_no}",
        f"kind={kind}",
        f"amount={amount:,}",
        f"due={due_date}",
    ]
    if period_start or period_end:
        parts.append(f"period={period_start or '-'}..{period_end or '-'}")
    if notes:
        parts.append(f"notes={notes}")
    return "; ".join(parts)


def _create_invoice(
    kind,
    amount,
    due_date=None,
    issue_date=None,
    period_start=None,
    period_end=None,
    actor="",
    notes="",
):
    subscription = _require_subscription()
    kind = _normalize_kind(kind)
    issued = _normalize_date(issue_date, "issue-date") or date.today().isoformat()
    period_start = _normalize_date(period_start, "period-start")
    period_end = _normalize_date(period_end, "period-end")

    if kind == "monthly":
        if period_start is None:
            raise BillingError("--period-start is required for a monthly invoice")
        if period_end is None:
            raise BillingError("--period-end is required for a monthly invoice")
        if period_end <= period_start:
            raise BillingError("period-end must be after period-start")
    else:
        period_start = None
        period_end = None

    due = _normalize_date(due_date, "due") or (
        period_start if kind == "monthly" else issued
    )
    amount = _positive_money(amount, "invoice amount")
    currency = subscription["currency"] or CURRENCY
    notes = _text(notes)
    actor = _text(actor)
    invoice_no = None

    db = get_db()
    try:
        _begin_immediate(db)
        if kind == "setup":
            existing = db.execute(
                "SELECT invoice_no FROM billing_invoices "
                "WHERE kind='setup' AND status != 'void' LIMIT 1"
            ).fetchone()
            if existing is not None:
                raise BillingError(
                    f"a setup invoice already exists: {existing[0]} "
                    "(void it before issuing another)"
                )
        if kind == "monthly":
            existing = db.execute(
                "SELECT invoice_no, period_start, period_end "
                "FROM billing_invoices "
                "WHERE kind='monthly' AND status != 'void' "
                "AND period_start < ? AND period_end > ? LIMIT 1",
                (period_end, period_start),
            ).fetchone()
            if existing is not None:
                if existing["period_start"] == period_start and (
                    existing["period_end"] == period_end
                ):
                    raise BillingError(
                        "a monthly invoice already exists for "
                        f"{period_start}..{period_end}: {existing['invoice_no']}"
                    )
                raise BillingError(
                    f"monthly invoice {period_start}..{period_end} overlaps "
                    f"{existing['invoice_no']} "
                    f"({existing['period_start']}..{existing['period_end']})"
                )
        invoice_no = _next_invoice_no(db, issued)
        db.execute(
            "INSERT INTO billing_invoices("
            "invoice_no, kind, issue_date, due_date, period_start, period_end,"
            " amount, currency, status, notes"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                invoice_no,
                kind,
                issued,
                due,
                period_start,
                period_end,
                amount,
                currency,
                "unpaid",
                notes,
            ),
        )
        _log(
            db,
            "invoice",
            actor,
            _invoice_event_text(
                invoice_no,
                kind,
                amount,
                due,
                period_start,
                period_end,
                notes,
            ),
        )
        db.commit()
    except BillingError:
        db.rollback()
        raise
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise BillingError(
            f"invoice could not be created because it conflicts with an "
            f"existing record: {exc}"
        ) from exc
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()

    return invoice_detail(invoice_no)


def create_setup_invoice(due_date=None, issue_date=None, actor="", notes=""):
    """Create a setup invoice for the agreed setup fee."""
    subscription = _require_subscription()
    amount = _positive_money(subscription["setup_fee"], "setup fee")
    return _create_invoice(
        "setup",
        amount,
        due_date=due_date,
        issue_date=issue_date,
        actor=actor,
        notes=notes,
    )


def create_monthly_invoice(
    period_start,
    period_end,
    due_date=None,
    issue_date=None,
    actor="",
    notes="",
):
    """Create a monthly invoice for the agreed monthly fee and period."""
    subscription = _require_subscription()
    amount = _positive_money(subscription["monthly_fee"], "monthly fee")
    return _create_invoice(
        "monthly",
        amount,
        due_date=due_date,
        issue_date=issue_date,
        period_start=period_start,
        period_end=period_end,
        actor=actor,
        notes=notes,
    )


def _refresh_invoice_status(db, invoice_id):
    """Derive invoice status from the payment ledger; void stays void."""
    row = db.execute(
        "SELECT amount, status FROM billing_invoices WHERE id = ?",
        (invoice_id,),
    ).fetchone()
    if row is None or row["status"] == "void":
        return
    paid = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS paid "
        "FROM billing_payments WHERE invoice_id = ?",
        (invoice_id,),
    ).fetchone()["paid"]
    if float(paid) >= float(row["amount"]):
        status = "paid"
    elif float(paid) > 0:
        status = "partial"
    else:
        status = "unpaid"
    db.execute(
        "UPDATE billing_invoices SET status = ? WHERE id = ?",
        (status, invoice_id),
    )


def record_payment(
    invoice_no,
    amount,
    method,
    paid_on=None,
    reference="",
    received_by="",
    notes="",
    actor="",
):
    """Record a manual payment against an invoice; no gateway is called.

    The invoice row and its paid total are re-read under the writer lock, so a
    stale balance can never be paid twice by two concurrent operator runs.
    """
    number = _invoice_number(invoice_no)
    payment_amount = _positive_money(amount, "payment amount")
    method = _normalize_method(method)
    paid = _normalize_date(paid_on, "paid-on") or date.today().isoformat()
    reference = _text(reference)
    received_by = _text(received_by)
    notes = _text(notes)
    actor = _text(actor) or received_by

    db = get_db()
    try:
        _begin_immediate(db)
        invoice = db.execute(
            "SELECT * FROM billing_invoices WHERE invoice_no = ?", (number,)
        ).fetchone()
        if invoice is None:
            raise BillingError(f"invoice {number!r} not found")
        if invoice["status"] == "void":
            raise BillingError(f"invoice {number} is void and cannot accept payments")
        if invoice["status"] == "paid":
            raise BillingError(f"invoice {number} is already paid")
        if invoice["status"] == "draft":
            raise BillingError(f"invoice {number} is a draft and cannot accept payments")

        paid_total = float(
            db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM billing_payments "
                "WHERE invoice_id = ?",
                (invoice["id"],),
            ).fetchone()[0]
        )
        remaining = float(invoice["amount"]) - paid_total
        if payment_amount > remaining:
            raise BillingError(
                "overpayment: remaining balance is "
                f"{_money_value(remaining):,} {invoice['currency']}"
            )

        db.execute(
            "INSERT INTO billing_payments("
            "invoice_id, paid_on, amount, currency, method, reference,"
            " received_by, notes"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (
                invoice["id"],
                paid,
                payment_amount,
                invoice["currency"],
                method,
                reference,
                received_by,
                notes,
            ),
        )
        _refresh_invoice_status(db, invoice["id"])
        _log(
            db,
            "payment",
            actor,
            f"invoice={number}; amount={payment_amount:,}; method={method}; "
            f"reference={reference or '-'}; received_by={received_by or '-'}",
        )
        db.commit()
    except BillingError:
        db.rollback()
        raise
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()

    return invoice_detail(number)


def void_invoice(invoice_no, actor="", reason=""):
    """Void an invoice that has no recorded payments.

    Voiding is the correction path for a wrong amount or period: the row stays
    visible for audit, stops accepting payments, and no longer blocks a
    replacement invoice. A paid or partly paid invoice cannot be voided here;
    money already received must be handled by the operator first.
    """
    number = _invoice_number(invoice_no)
    actor = _text(actor)
    reason = _text(reason)

    db = get_db()
    try:
        _begin_immediate(db)
        invoice = db.execute(
            "SELECT * FROM billing_invoices WHERE invoice_no = ?", (number,)
        ).fetchone()
        if invoice is None:
            raise BillingError(f"invoice {number!r} not found")
        if invoice["status"] == "void":
            raise BillingError(f"invoice {number} is already void")

        paid_total = float(
            db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM billing_payments "
                "WHERE invoice_id = ?",
                (invoice["id"],),
            ).fetchone()[0]
        )
        if paid_total > 0:
            raise BillingError(
                f"cannot void {number}: {_money_value(paid_total):,} "
                f"{invoice['currency']} has been recorded against it"
            )

        db.execute(
            "UPDATE billing_invoices SET status='void' WHERE id = ?",
            (invoice["id"],),
        )
        detail = f"invoice={number}; from {invoice['status']} to void"
        if reason:
            detail = f"{detail}; reason={reason}"
        _log(db, "void", actor, detail)
        db.commit()
    except BillingError:
        db.rollback()
        raise
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()

    return invoice_detail(number)


def renewals(days=14, as_of=None):
    """Return the subscription when its period ends inside the renewal window.

    Overdue subscriptions are included so the operator can chase them. The
    window is inclusive: an end date exactly ``days`` from ``as_of`` is due.
    """
    if isinstance(days, bool) or not isinstance(days, int):
        raise BillingError("days must be a whole number")
    if days < 0:
        raise BillingError("days cannot be negative")

    today = _normalize_date(as_of, "as-of") or date.today().isoformat()
    today_date = date.fromisoformat(today)
    subscription = current_subscription()
    if subscription is None:
        return []
    if subscription["status"] in ("pending", "grandfathered", "cancelled"):
        return []
    end = subscription["current_period_end"]
    if not end:
        return []
    try:
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise BillingError(
            f"subscription period end {end!r} is not an ISO date"
        ) from exc

    days_until = (end_date - today_date).days
    if days_until > days:
        return []
    return [
        {
            "customer_name": subscription["customer_name"],
            "bundle": subscription["bundle"],
            "status": subscription["status"],
            "currency": subscription["currency"],
            "monthly_fee": _money_value(subscription["monthly_fee"]),
            "current_period_end": end,
            "days_until": days_until,
            "overdue": days_until < 0,
        }
    ]
