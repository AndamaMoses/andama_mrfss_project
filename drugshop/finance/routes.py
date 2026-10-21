"""Finance routes: reconciliation, expenses, profit.

Route bodies carried over verbatim from app.py (Phase 4.7); the admin-only
single-method views (``api_rec_del``, ``api_expense_del``) use the
``admin_required`` decorator — their monolith bodies checked admin at the top
for all methods, so behavior is unchanged. The ``ON CONFLICT(rec_date) DO
UPDATE`` upsert is preserved.
"""
import math

from flask import Blueprint, jsonify, request

from drugshop.auth.guards import admin_required
from drugshop.core.utils import today_str
from drugshop.db import execute, get_db, q_all, q_one
from drugshop.sales.service import sales_summary

bp = Blueprint("finance", __name__)


# reconciliation
@bp.route("/api/reconciliation/<rec_date>", methods=["DELETE"])
@admin_required
def api_rec_del(rec_date):
    execute("DELETE FROM reconciliations WHERE rec_date=?", (rec_date,))
    return jsonify({"ok": True})


@bp.route("/api/reconciliation/calculate")
def api_rec_calc():
    day = request.args.get("date", today_str())
    s = sales_summary(day)
    saved = q_one("SELECT * FROM reconciliations WHERE rec_date=?", (day,))
    return jsonify({
        "date": day,
        "expected_cash": s["by_method"]["CASH"],
        "expected_mtn": s["by_method"]["MTN_MOMO"],
        "expected_airtel": s["by_method"]["AIRTEL_MOMO"],
        "expected_credit": s["by_method"]["CREDIT"],
        "saved": saved,
    })


@bp.route("/api/reconciliation", methods=["GET", "POST"])
def api_rec():
    if request.method == "GET":
        return jsonify(q_all("SELECT * FROM reconciliations ORDER BY rec_date DESC LIMIT 60"))
    d = request.json or {}
    day = d.get("rec_date") or today_str()
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
def api_profit():
    day = request.args.get("date", today_str())
    rev = q_one("SELECT COALESCE(SUM(total),0) t FROM sales WHERE sale_date=? AND payment_method!='CREDIT'", (day,))["t"]
    credit = q_one("SELECT COALESCE(SUM(total),0) t FROM sales WHERE sale_date=? AND payment_method='CREDIT'", (day,))["t"]
    cogs = q_one("""SELECT COALESCE(SUM(s.qty * p.price_buy),0) t FROM sales s
                    JOIN products p ON p.id=s.product_id WHERE s.sale_date=?""", (day,))["t"]
    exp = q_one("SELECT COALESCE(SUM(amount),0) t FROM expenses WHERE exp_date=?", (day,))["t"]
    return jsonify({"date": day, "revenue_cash_momo": rev, "credit_given": credit,
                    "cogs_approx": cogs, "expenses": exp, "profit_approx": round(rev - cogs - exp, 2)})
