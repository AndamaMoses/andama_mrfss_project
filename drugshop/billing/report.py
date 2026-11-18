"""Revenue reports for one installation or a read-only portfolio rollup.

This module is deliberately connection-oriented so the same calculations back
the operator CLI and ``scripts/revenue_rollup.py``. The rollup opens customer
databases read-only and never imports the Flask app or the writable data layer.

Definitions (v1):

* ``mrr`` — monthly fee of an ``active`` or ``past_due`` subscription. Legacy
  grandfathered, pending, cancelled, and expired subscriptions contribute 0.
* ``setup_invoiced`` / ``monthly_invoiced`` / ``total_invoiced`` — non-void
  invoice amounts. A void invoice stays visible in the counts but is not owed.
* ``setup_collected`` — payments recorded against non-void setup invoices.
* ``payments_collected`` — every manual payment recorded on the installation.
* ``outstanding_balance`` — unpaid balance of non-void invoices.
* ``renewals_due`` — subscriptions inside the renewal window, including
  overdue and expired rows, matching ``billing.service.renewals``.
"""
import sqlite3
from collections import Counter
from datetime import date, datetime

from drugshop.apps import registry
from drugshop.billing.catalog import CURRENCY

REPORT_VERSION = 1
PAYING_STATUSES = ("active", "past_due")
RENEWAL_EXCLUDED_STATUSES = ("pending", "grandfathered", "cancelled")


def _money(value):
    amount = float(value or 0)
    return int(amount) if amount.is_integer() else amount


def _rows(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _one(conn, sql, params=()):
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


def _table_exists(conn, name):
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _entitlement_plan(conn):
    """Fallback plan for an installation without a commercial row."""
    if not _table_exists(conn, "app_entitlements"):
        return {
            "bundle": "unseeded",
            "label": "Unseeded",
            "status": "inactive",
            "expires_at": None,
        }
    rows = _rows(conn, "SELECT app_id, status, expires_at FROM app_entitlements")
    active = {row["app_id"] for row in rows if row["status"] == "active"}
    bundle = "unseeded" if not rows else registry.detect_bundle(active)
    expiries = sorted(
        row["expires_at"]
        for row in rows
        if row["status"] == "active" and row["expires_at"]
    )
    return {
        "bundle": bundle,
        "label": "Unseeded" if bundle == "unseeded" else registry.bundle_label(bundle),
        "status": "active" if active else "inactive",
        "expires_at": expiries[-1] if expiries else None,
    }


def _invoice_totals(conn):
    """Invoice and payment totals, tolerating pre-migration databases."""
    totals = {
        "invoice_count": 0,
        "invoices_by_status": {},
        "invoices_by_kind": {},
        "setup_invoiced": 0,
        "monthly_invoiced": 0,
        "total_invoiced": 0,
        "setup_collected": 0,
        "payments_collected": 0,
        "payments_by_method": {},
        "outstanding_balance": 0,
    }
    if not _table_exists(conn, "billing_invoices"):
        return totals

    has_payments = _table_exists(conn, "billing_payments")
    if has_payments:
        rows = _rows(
            conn,
            "SELECT i.*, COALESCE(SUM(p.amount), 0) AS paid, "
            "COUNT(p.id) AS payment_count "
            "FROM billing_invoices i "
            "LEFT JOIN billing_payments p ON p.invoice_id = i.id "
            "GROUP BY i.id ORDER BY i.id DESC",
        )
    else:
        rows = _rows(
            conn,
            "SELECT i.*, 0 AS paid, 0 AS payment_count "
            "FROM billing_invoices i ORDER BY i.id DESC",
        )

    status_counts = Counter()
    kind_counts = Counter()
    outstanding = 0.0
    for row in rows:
        amount = float(row["amount"] or 0)
        paid = float(row["paid"] or 0)
        status = row["status"]
        balance = 0.0 if status == "void" else max(0.0, amount - paid)
        outstanding += balance
        status_counts[status] += 1
        kind_counts[row["kind"]] += 1
        if status == "void":
            continue
        if row["kind"] == "setup":
            totals["setup_invoiced"] += amount
        elif row["kind"] == "monthly":
            totals["monthly_invoiced"] += amount
        totals["total_invoiced"] += amount

    totals["invoice_count"] = len(rows)
    totals["invoices_by_status"] = dict(sorted(status_counts.items()))
    totals["invoices_by_kind"] = dict(sorted(kind_counts.items()))
    totals["setup_invoiced"] = _money(totals["setup_invoiced"])
    totals["monthly_invoiced"] = _money(totals["monthly_invoiced"])
    totals["total_invoiced"] = _money(totals["total_invoiced"])
    totals["outstanding_balance"] = _money(outstanding)

    if has_payments:
        payments = _rows(
            conn,
            "SELECT COALESCE(SUM(amount), 0) AS paid FROM billing_payments",
        )
        totals["payments_collected"] = _money(payments[0]["paid"])
        methods = _rows(
            conn,
            "SELECT method, COALESCE(SUM(amount), 0) AS paid "
            "FROM billing_payments GROUP BY method ORDER BY method",
        )
        totals["payments_by_method"] = {
            row["method"]: _money(row["paid"]) for row in methods
        }
        if totals["payments_by_method"]:
            setup = _rows(
                conn,
                "SELECT COALESCE(SUM(p.amount), 0) AS paid "
                "FROM billing_payments p "
                "JOIN billing_invoices i ON i.id = p.invoice_id "
                "WHERE i.kind = 'setup' AND i.status != 'void'",
            )
            totals["setup_collected"] = _money(setup[0]["paid"])
    return totals


def _renewal_rows(subscription, renewal_days, as_of):
    if subscription is None:
        return []
    if subscription["status"] in RENEWAL_EXCLUDED_STATUSES:
        return []
    end = subscription["current_period_end"]
    if not end:
        return []
    try:
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise ValueError(
            f"subscription period end {end!r} is not an ISO date"
        ) from exc
    days_until = (end_date - as_of).days
    if days_until > renewal_days:
        return []
    return [
        {
            "customer_name": subscription["customer_name"],
            "bundle": subscription["bundle"],
            "status": subscription["status"],
            "currency": subscription["currency"],
            "monthly_fee": _money(subscription["monthly_fee"]),
            "current_period_end": end,
            "days_until": days_until,
            "overdue": days_until < 0,
        }
    ]


def _plan_payload(subscription, entitlement_plan):
    if subscription is None:
        status = (
            "grandfathered"
            if entitlement_plan["bundle"] == "legacy"
            else entitlement_plan["status"]
        )
        return {
            "bundle": entitlement_plan["bundle"],
            "label": entitlement_plan["label"],
            "status": status,
            "monthly_fee": 0,
            "setup_fee": 0,
            "started_on": None,
            "current_period_start": None,
            "current_period_end": entitlement_plan["expires_at"],
        }
    return {
        "bundle": subscription["bundle"],
        "label": registry.bundle_label(subscription["bundle"]),
        "status": subscription["status"],
        "monthly_fee": _money(subscription["monthly_fee"]),
        "setup_fee": _money(subscription["setup_fee"]),
        "started_on": subscription["started_on"],
        "current_period_start": subscription["current_period_start"],
        "current_period_end": subscription["current_period_end"],
    }


def _grandfathered_entry(subscription, customer_name, plan, reason):
    return {
        "customer_name": customer_name,
        "bundle": plan["bundle"],
        "label": plan["label"],
        "status": plan["status"],
        "started_on": plan["started_on"],
        "current_period_end": plan["current_period_end"],
        "monthly_fee": 0,
        "currency": subscription["currency"] if subscription else CURRENCY,
        "reason": reason,
    }


def _excluded_entry(subscription, customer_name, plan, reason):
    return {
        "customer_name": customer_name,
        "bundle": plan["bundle"],
        "label": plan["label"],
        "status": plan["status"],
        "monthly_fee": plan["monthly_fee"],
        "currency": subscription["currency"] if subscription else CURRENCY,
        "reason": reason,
    }


def build_report(conn, source=None, renewal_days=14, as_of=None):
    """Build one installation's revenue report from an open connection."""
    if isinstance(renewal_days, bool) or not isinstance(renewal_days, int):
        raise ValueError("renewal days must be a whole number")
    if renewal_days < 0:
        raise ValueError("renewal days cannot be negative")
    if as_of is None:
        as_of_date = date.today()
    else:
        try:
            as_of_date = date.fromisoformat(str(as_of))
        except ValueError as exc:
            raise ValueError("as-of must be an ISO date (YYYY-MM-DD)") from exc

    has_subscriptions = _table_exists(conn, "billing_subscriptions")
    subscription = (
        _one(conn, "SELECT * FROM billing_subscriptions WHERE id = 1")
        if has_subscriptions
        else None
    )
    entitlement_plan = _entitlement_plan(conn)
    plan = _plan_payload(subscription, entitlement_plan)

    customer_name = subscription["customer_name"] if subscription else ""
    currency = (
        (subscription["currency"] if subscription else None) or CURRENCY
    )
    grandfathered = []
    excluded = []
    mrr = 0
    if subscription is None:
        billing_status = (
            "uninitialized" if not has_subscriptions else "no_billing_row"
        )
        reason = (
            "billing tables not initialized"
            if billing_status == "uninitialized"
            else "no billing subscription"
        )
        if entitlement_plan["bundle"] == "legacy":
            grandfathered.append(
                _grandfathered_entry(
                    None,
                    "",
                    plan,
                    "legacy entitlements without a billing row",
                )
            )
        else:
            excluded.append(_excluded_entry(None, "", plan, reason))
    else:
        billing_status = subscription["status"]
        if subscription["status"] == "grandfathered" or (
            subscription["bundle"] == "legacy"
            and subscription["status"] not in PAYING_STATUSES
        ):
            grandfathered.append(
                _grandfathered_entry(
                    subscription,
                    customer_name,
                    plan,
                    "legacy grandfathered subscription",
                )
            )
        elif subscription["status"] in PAYING_STATUSES:
            mrr = _money(subscription["monthly_fee"])
        else:
            excluded.append(
                _excluded_entry(
                    subscription,
                    customer_name,
                    plan,
                    f"status {subscription['status']}",
                )
            )

    totals = _invoice_totals(conn)
    renewals_due = _renewal_rows(subscription, renewal_days, as_of_date)

    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of": as_of_date.isoformat(),
        "source": str(source) if source else None,
        "customer_name": customer_name,
        "currency": currency,
        "billing_status": billing_status,
        "plan": plan,
        "mrr": mrr,
        "plan_mix": [
            {
                "bundle": plan["bundle"],
                "label": plan["label"],
                "installations": 1,
                "mrr": mrr,
            }
        ],
        "renewal_days": renewal_days,
        "renewals_due": renewals_due,
        "renewal_due_count": len(renewals_due),
        "grandfathered": grandfathered,
        "excluded": excluded,
        **totals,
    }


def aggregate(reports):
    """Aggregate installation reports into one portfolio view.

    Totals are only meaningful in one currency, so a mixed-currency portfolio
    is rejected instead of silently adding unlike amounts.
    """
    currencies = {report.get("currency") or CURRENCY for report in reports}
    if len(currencies) > 1:
        raise ValueError(
            "portfolio mixes currencies "
            f"({', '.join(sorted(currencies))}); report each currency separately"
        )
    totals = {
        "installations": len(reports),
        "paying_installations": 0,
        "mrr": 0,
        "setup_invoiced": 0,
        "monthly_invoiced": 0,
        "total_invoiced": 0,
        "setup_collected": 0,
        "payments_collected": 0,
        "outstanding_balance": 0,
        "invoice_count": 0,
        "renewal_due_count": 0,
        "grandfathered_count": 0,
        "excluded_count": 0,
    }
    plan_mix = {}
    renewals_due = []
    grandfathered = []
    excluded = []
    for report in reports:
        source = report.get("source")
        for key in (
            "mrr",
            "setup_invoiced",
            "monthly_invoiced",
            "total_invoiced",
            "setup_collected",
            "payments_collected",
            "outstanding_balance",
            "invoice_count",
            "renewal_due_count",
        ):
            totals[key] += report[key]
        if report["mrr"] > 0:
            totals["paying_installations"] += 1
        for entry in report["plan_mix"]:
            bucket = plan_mix.setdefault(
                entry["bundle"],
                {
                    "bundle": entry["bundle"],
                    "label": entry["label"],
                    "installations": 0,
                    "mrr": 0,
                },
            )
            bucket["installations"] += entry["installations"]
            bucket["mrr"] += entry["mrr"]
        for entry in report["renewals_due"]:
            renewals_due.append({**entry, "source": source})
        for entry in report["grandfathered"]:
            grandfathered.append({**entry, "source": source})
        for entry in report["excluded"]:
            excluded.append({**entry, "source": source})

    totals["grandfathered_count"] = len(grandfathered)
    totals["excluded_count"] = len(excluded)
    for key in (
        "mrr",
        "setup_invoiced",
        "monthly_invoiced",
        "total_invoiced",
        "setup_collected",
        "payments_collected",
        "outstanding_balance",
    ):
        totals[key] = _money(totals[key])
    for bucket in plan_mix.values():
        bucket["mrr"] = _money(bucket["mrr"])

    return {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of": reports[0].get("as_of") if reports else None,
        "currency": currencies.pop() if currencies else CURRENCY,
        "totals": totals,
        "plan_mix": sorted(
            plan_mix.values(), key=lambda item: (-item["mrr"], item["bundle"])
        ),
        "renewals_due": renewals_due,
        "grandfathered": grandfathered,
        "excluded": excluded,
        "installations": reports,
    }


CSV_COLUMNS = (
    "source",
    "customer_name",
    "bundle",
    "plan_label",
    "status",
    "billing_status",
    "currency",
    "mrr",
    "setup_invoiced",
    "monthly_invoiced",
    "total_invoiced",
    "setup_collected",
    "payments_collected",
    "outstanding_balance",
    "invoice_count",
    "renewal_due_count",
    "grandfathered_count",
    "excluded_count",
    "as_of",
)


def csv_rows(reports):
    """Yield flat, stable rows for CSV output."""
    for report in reports:
        yield {
            "source": report.get("source") or "",
            "customer_name": report["customer_name"],
            "bundle": report["plan"]["bundle"],
            "plan_label": report["plan"]["label"],
            "status": report["plan"]["status"],
            "billing_status": report["billing_status"],
            "currency": report["currency"],
            "mrr": report["mrr"],
            "setup_invoiced": report["setup_invoiced"],
            "monthly_invoiced": report["monthly_invoiced"],
            "total_invoiced": report["total_invoiced"],
            "setup_collected": report["setup_collected"],
            "payments_collected": report["payments_collected"],
            "outstanding_balance": report["outstanding_balance"],
            "invoice_count": report["invoice_count"],
            "renewal_due_count": report["renewal_due_count"],
            "grandfathered_count": len(report["grandfathered"]),
            "excluded_count": len(report["excluded"]),
            "as_of": report["as_of"],
        }


def connect_readonly(path):
    """Open an existing SQLite file without any write capability.

    ``mode=ro`` plus ``PRAGMA query_only`` makes writes impossible, and
    ``BEGIN`` holds one read snapshot for every query on the connection so a
    report cannot mix rows from two committed states. Close the connection to
    release the snapshot; an uncommitted read transaction is rolled back.
    """
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("BEGIN")
    return conn
