"""Credit ledger routes: outstanding balances and payments.

Route bodies carried over verbatim from app.py (Phase 4.6); the overpayment
guard (``paid + amt > total + 0.005``) and the "credit sale not found" 404
are unchanged.
"""
import math

from flask import Blueprint, jsonify, request

from drugshop.auth.guards import current_user
from drugshop.core.utils import today_str
from drugshop.db import execute, q_all, q_one

bp = Blueprint("credit", __name__)


# ---------- credit ledger ----------
@bp.route("/api/credit")
def api_credit():
    rows = q_all("""SELECT s.*, p.name as product_name,
                    COALESCE((SELECT SUM(amount) FROM credit_payments WHERE sale_id=s.id),0) as paid
                    FROM sales s JOIN products p ON p.id=s.product_id
                    WHERE s.payment_method='CREDIT' ORDER BY s.sale_date DESC, s.id DESC""")
    out = []
    for r in rows:
        r["balance"] = round(r["total"] - r["paid"], 2)
        if r["balance"] > 0.005:
            out.append(r)
    return jsonify({"count": len(out), "total_owed": round(sum(r["balance"] for r in out), 2), "rows": out})


@bp.route("/api/credit/<int:sid>/pay", methods=["POST"])
def api_credit_pay(sid):
    s = q_one("SELECT * FROM sales WHERE id=? AND payment_method='CREDIT'", (sid,))
    if not s:
        return jsonify({"error": "credit sale not found"}), 404
    d = request.json or {}
    try:
        amt = float(d.get("amount", 0))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return jsonify({"error": "valid amount required"}), 400
    if not math.isfinite(amt):
        return jsonify({"error": "valid amount required"}), 400
    if amt <= 0:
        return jsonify({"error": "amount must be positive"}), 400
    paid = q_one("SELECT COALESCE(SUM(amount),0) p FROM credit_payments WHERE sale_id=?", (sid,))["p"]
    if paid + amt > s["total"] + 0.005:
        return jsonify({"error": f"overpayment. Balance is UGX {s['total']-paid:,.0f}"}), 400
    me = current_user()
    execute("INSERT INTO credit_payments(sale_id,amount,pay_date,method,notes,received_by) VALUES(?,?,?,?,?,?)",
            (sid, amt, d.get("pay_date") or today_str(), d.get("method", "CASH"), d.get("notes", ""), me["username"] if me else ""))
    return jsonify({"ok": True, "balance": round(s["total"] - paid - amt, 2)}), 201
