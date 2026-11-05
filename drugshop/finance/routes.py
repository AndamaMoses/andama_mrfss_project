"""Finance routes: reconciliation, expenses, profit.

Route bodies carried over verbatim from app.py (Phase 4.7); the admin-only
single-method views (``api_rec_del``, ``api_expense_del``) use the
``admin_required`` decorator — their monolith bodies checked admin at the top
for all methods, so behavior is unchanged. The ``ON CONFLICT(rec_date) DO
UPDATE`` upsert is preserved.
"""
import math
from datetime import datetime

from flask import Blueprint, jsonify, request

from drugshop.auth.guards import admin_required, current_user
from drugshop.core.utils import today_str
from drugshop.db import execute, get_db, q_all, q_one
from drugshop.payments import reconciliation
from drugshop.sales.service import sales_summary

bp = Blueprint("finance", __name__)


def _json_object():
    """Return a JSON object, ``{}`` for an empty body, or ``None`` if invalid."""
    data = request.get_json(silent=True)
    if data is None:
        return {}
    return data if isinstance(data, dict) else None


def _valid_day(value):
    """Return a strict ``YYYY-MM-DD`` day, or ``None`` when it is malformed.

    Python's ``strptime`` accepts single-digit months/days, so the round-trip
    check is what keeps ``2026-11-5`` from creating a separate ledger day.
    """
    day = str(value or today_str()).strip()
    try:
        parsed = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return None
    return day if parsed.strftime("%Y-%m-%d") == day else None


# reconciliation
@bp.route("/api/reconciliation/<rec_date>", methods=["DELETE"])
@admin_required
def api_rec_del(rec_date):
    execute("DELETE FROM reconciliations WHERE rec_date=?", (rec_date,))
    return jsonify({"ok": True})


@bp.route("/api/reconciliation/calculate")
def api_rec_calc():
    day = _valid_day(request.args.get("date", today_str()))
    if not day:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    s = sales_summary(day)
    saved = q_one("SELECT * FROM reconciliations WHERE rec_date=?", (day,))
    return jsonify({
        "date": day,
        "expected_cash": s["by_method"]["CASH"],
        "expected_mtn": s["by_method"]["MTN_MOMO"],
        "expected_airtel": s["by_method"]["AIRTEL_MOMO"],
        "expected_credit": s["by_method"]["CREDIT"],
        "saved": saved,
        "payments": reconciliation.payment_summary(day),
    })


@bp.route("/api/reconciliation/daily-summary")
def api_rec_daily_summary():
    """Expected sales by channel plus the live mobile-money variance view."""
    day = _valid_day(request.args.get("date", today_str()))
    if not day:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    s = sales_summary(day)
    saved = q_one("SELECT * FROM reconciliations WHERE rec_date=?", (day,))
    return jsonify({
        "ok": True,
        "date": day,
        "summary": {
            "expected_cash": s["by_method"]["CASH"],
            "expected_mtn": s["by_method"]["MTN_MOMO"],
            "expected_airtel": s["by_method"]["AIRTEL_MOMO"],
            "expected_credit": s["by_method"]["CREDIT"],
            "total_sales_count": s["count"],
            "total": s["total"],
        },
        "existing_reconciliation": saved,
        "payments": reconciliation.payment_summary(day),
    })


@bp.route("/api/reconciliation/payments")
def api_rec_payments():
    """Live payment variance plus any snapshots saved when the shift closed."""
    day = _valid_day(request.args.get("date", today_str()))
    if not day:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    return jsonify(reconciliation.payment_reconciliation_report(day))


@bp.route("/api/reconciliation/sweep", methods=["POST"])
def api_rec_sweep():
    """Re-query stale pending/unknown prompts; bounded and dry-run capable."""
    d = _json_object()
    if d is None:
        return jsonify({"error": "JSON object required"}), 400
    dry_run = str(d.get("dry_run", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        result = reconciliation.sweep_stale(
            provider=d.get("provider"),
            older_than_minutes=d.get(
                "older_than_minutes", reconciliation.DEFAULT_STALE_MINUTES
            ),
            limit=d.get("limit", 50),
            actor=(current_user() or {}).get("username", ""),
            dry_run=dry_run,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@bp.route("/api/reconciliation/close-shift", methods=["POST"])
def api_rec_close_shift():
    """Record counted balances, close the day, and snapshot payment variance."""
    d = _json_object()
    if d is None:
        return jsonify({"error": "JSON object required"}), 400
    day = _valid_day(d.get("date") or d.get("rec_date") or today_str())
    if not day:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    s = sales_summary(day)
    ec, em, ea = (
        s["by_method"]["CASH"],
        s["by_method"]["MTN_MOMO"],
        s["by_method"]["AIRTEL_MOMO"],
    )
    try:
        cc = float(d.get("counted_cash", 0))
        cm = float(d.get("counted_mtn", 0))
        ca = float(d.get("counted_airtel", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "counted amounts must be numbers"}), 400
    if not all(math.isfinite(x) for x in (cc, cm, ca)):
        return jsonify({"error": "counted amounts must be numbers"}), 400

    variances = {
        "cash": round(cc - ec, 2),
        "mtn": round(cm - em, 2),
        "airtel": round(ca - ea, 2),
    }
    db = get_db()
    try:
        db.execute(
            """INSERT INTO reconciliations(
                   rec_date, expected_cash, counted_cash, expected_mtn,
                   counted_mtn, expected_airtel, counted_airtel, notes, status)
               VALUES(?,?,?,?,?,?,?,?,'CLOSED')
               ON CONFLICT(rec_date) DO UPDATE SET
                   expected_cash=excluded.expected_cash,
                   counted_cash=excluded.counted_cash,
                   expected_mtn=excluded.expected_mtn,
                   counted_mtn=excluded.counted_mtn,
                   expected_airtel=excluded.expected_airtel,
                   counted_airtel=excluded.counted_airtel,
                   notes=excluded.notes,
                   status='CLOSED'""",
            (
                day,
                ec,
                cc,
                em,
                cm,
                ea,
                ca,
                d.get("notes", ""),
            ),
        )
        db.commit()
    finally:
        db.close()

    payments = reconciliation.snapshot_payment_reconciliation(
        day, actor=(current_user() or {}).get("username", "")
    )
    return jsonify({
        "ok": True,
        "date": day,
        "status": "CLOSED",
        "difference": round(sum(variances.values()), 2),
        "variances": variances,
        "payments": payments,
    }), 201


@bp.route("/api/reconciliation", methods=["GET", "POST"])
def api_rec():
    if request.method == "GET":
        return jsonify(q_all("SELECT * FROM reconciliations ORDER BY rec_date DESC LIMIT 60"))
    d = _json_object()
    if d is None:
        return jsonify({"error": "JSON object required"}), 400
    day = _valid_day(d.get("rec_date") or today_str())
    if not day:
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    s = sales_summary(day)
    ec, em, ea = s["by_method"]["CASH"], s["by_method"]["MTN_MOMO"], s["by_method"]["AIRTEL_MOMO"]
    try:
        cc, cm, ca = float(d.get("counted_cash", 0)), float(d.get("counted_mtn", 0)), float(d.get("counted_airtel", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "counted amounts must be numbers"}), 400
    if not all(math.isfinite(x) for x in (cc, cm, ca)):
        return jsonify({"error": "counted amounts must be numbers"}), 400
    diff = (cc - ec) + (cm - em) + (ca - ea)
    status = "BALANCED" if abs(diff) < 0.5 else ("SHORTAGE" if diff < 0 else "OVERAGE")
    db = get_db()
    try:
        db.execute("""INSERT INTO reconciliations(rec_date,expected_cash,counted_cash,expected_mtn,counted_mtn,expected_airtel,counted_airtel,notes,status)
                      VALUES(?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(rec_date) DO UPDATE SET expected_cash=excluded.expected_cash, counted_cash=excluded.counted_cash,
                      expected_mtn=excluded.expected_mtn, counted_mtn=excluded.counted_mtn, expected_airtel=excluded.expected_airtel,
                      counted_airtel=excluded.counted_airtel, notes=excluded.notes, status=excluded.status""",
            (day, ec, cc, em, cm, ea, ca, d.get("notes", ""), status))
        db.commit()
    finally:
        db.close()
    return jsonify({"date": day, "status": status, "difference": diff}), 201


# ---------- expenses + profit ----------
@bp.route("/api/expenses", methods=["GET", "POST"])
def api_expenses():
    if request.method == "GET":
        month = request.args.get("month", today_str()[:7])
        return jsonify(q_all("SELECT * FROM expenses WHERE substr(exp_date,1,7)=? ORDER BY exp_date DESC", (month,)))
    d = request.json or {}
    try:
        amt = float(d.get("amount", 0))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return jsonify({"error": "valid amount required"}), 400
    if not math.isfinite(amt) or amt <= 0 or not d.get("description"):
        return jsonify({"error": "description and positive amount required"}), 400
    lid = execute("INSERT INTO expenses(exp_date,category,description,amount,paid_by) VALUES(?,?,?,?,?)",
                  (d.get("exp_date") or today_str(), d.get("category", "General"), d["description"], amt, d.get("paid_by", "")))
    return jsonify({"id": lid}), 201


@bp.route("/api/expenses/<int:eid>", methods=["DELETE"])
@admin_required
def api_expense_del(eid):
    execute("DELETE FROM expenses WHERE id=?", (eid,))
    return jsonify({"ok": True})


@bp.route("/api/profit")
@admin_required
def api_profit():
    day = request.args.get("date", today_str())
    rev = q_one("SELECT COALESCE(SUM(total),0) t FROM sales WHERE sale_date=? AND payment_method!='CREDIT'", (day,))["t"]
    credit = q_one("SELECT COALESCE(SUM(total),0) t FROM sales WHERE sale_date=? AND payment_method='CREDIT'", (day,))["t"]
    cogs = q_one("""SELECT COALESCE(SUM(s.qty * p.price_buy),0) t FROM sales s
                    JOIN products p ON p.id=s.product_id WHERE s.sale_date=?""", (day,))["t"]
    exp = q_one("SELECT COALESCE(SUM(amount),0) t FROM expenses WHERE exp_date=?", (day,))["t"]
    return jsonify({"date": day, "revenue_cash_momo": rev, "credit_given": credit,
                    "cogs_approx": cogs, "expenses": exp, "profit_approx": round(rev - cogs - exp, 2)})
