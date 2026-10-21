"""Customer directory routes: search with stats, manual create.

Route body carried over verbatim from app.py (Phase 4.5); phone digit
normalization (``normalize_ug_phone``) and the stats aggregation
(visits/total_spent/owed/wa_link) are unchanged.
"""
from flask import Blueprint, jsonify, request

from drugshop.core.utils import normalize_ug_phone
from drugshop.customers.service import upsert_customer
from drugshop.db import execute, q_all, q_one

bp = Blueprint("customers", __name__)


# ---------- customers directory ----------
@bp.route("/api/customers", methods=["GET", "POST"])
def api_customers():
    if request.method == "POST":
        d = request.json or {}
        if not (d.get("name") or "").strip() and not (d.get("phone") or "").strip():
            return jsonify({"error": "name or phone required"}), 400
        upsert_customer(d.get("name", ""), d.get("phone", ""))
        if d.get("notes"):
            ph = normalize_ug_phone(d.get("phone", ""))
            if ph:
                execute("UPDATE customers SET notes=? WHERE phone_digits=?", (d["notes"], ph))
            else:
                execute("UPDATE customers SET notes=? WHERE name=?", (d["notes"], d["name"].strip()))
        return jsonify({"ok": True}), 201
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"
    rows = q_all("""SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? OR phone_digits LIKE ?
                    ORDER BY name LIMIT 200""", (like, like, like))
    for r in rows:
        nm = r.get("name") or ""
        ph = r.get("phone_digits") or ""
        spent = q_one("""SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM sales
                         WHERE customer_name=? OR (customer_phone<>'' AND REPLACE(REPLACE(customer_phone,' ',''),'+','') LIKE ?)""",
                      (nm, f"%{ph[-9:]}" if len(ph) >= 9 else ph or "zzz-no-match")) if (nm or ph) else {"t": 0, "n": 0}
        r["total_spent"] = spent["t"]
        r["visits"] = spent["n"]
        phone = r.get("phone") or ""
        owed = q_all("""SELECT s.total - COALESCE((SELECT SUM(amount) FROM credit_payments WHERE sale_id=s.id),0) as bal
                        FROM sales s WHERE s.payment_method='CREDIT'
                        AND ((?<>'' AND s.customer_name=?) OR (?<>'' AND s.customer_phone=?))""",
                     (nm, nm, phone, phone))
        r["owed"] = round(sum(x["bal"] for x in owed if x["bal"] > 0.005), 2)
        digits = ph or normalize_ug_phone(r.get("phone") or "")
        r["wa_link"] = f"https://wa.me/{digits}" if digits else ""
    return jsonify(rows)
