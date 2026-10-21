"""Sales routes: POS sales, cart checkout, receipts, day-report.

Route bodies carried over from app.py (Phase 4.3); the fully admin-only void
view uses ``admin_required``. Receipt ref sequencing and cart total math are
unchanged. Sales record every FEFO allocation in ``sale_batches`` so a void
restores each touched batch, not just the first; ``deduct_fefo_allocations``
keeps all DB writes inside a single transaction per request.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from drugshop.auth.guards import admin_required
from drugshop.core.settings import get_setting
from drugshop.core.utils import today_str
from drugshop.customers.service import upsert_customer
from drugshop.db import get_db, q_all, q_one
from drugshop.inventory.service import deduct_fefo_allocations
from drugshop.sales.service import next_receipt_ref, sales_summary

bp = Blueprint("sales", __name__)


@bp.route("/api/sales/<int:sid>", methods=["DELETE"])
@admin_required
def api_sale_void(sid):
    """Void a sale: restore every FEFO allocation, drop credit payments. Admin only."""
    s = q_one("SELECT * FROM sales WHERE id=?", (sid,))
    if not s:
        return jsonify({"error": "sale not found"}), 404
    db = get_db()
    try:
        allocations = db.execute("SELECT batch_id, qty FROM sale_batches WHERE sale_id=?", (sid,)).fetchall()
        if allocations:
            for batch_id, qty in allocations:
                db.execute("UPDATE batches SET qty_remaining=qty_remaining+? WHERE id=?", (qty, batch_id))
        elif s.get("batch_id"):
            # Pre-allocation sales only recorded the first batch; keep old behavior.
            db.execute("UPDATE batches SET qty_remaining=qty_remaining+? WHERE id=?", (s["qty"], s["batch_id"]))
        db.execute("DELETE FROM sale_batches WHERE sale_id=?", (sid,))
        db.execute("DELETE FROM credit_payments WHERE sale_id=?", (sid,))
        db.execute("DELETE FROM sales WHERE id=?", (sid,))
        db.commit()
    finally:
        db.close()
    return jsonify({"ok": True, "restored": s["qty"]})


# sales / POS
@bp.route("/api/sales", methods=["GET", "POST"])
def api_sales():
    if request.method == "GET":
        day = request.args.get("date", today_str())
        rows = q_all("""SELECT s.*, p.name as product_name FROM sales s
                        JOIN products p ON p.id=s.product_id WHERE sale_date=? ORDER BY s.id DESC""", (day,))
        return jsonify(rows)
    d = request.json or {}
    try:
        pid = int(d["product_id"])
        qty = int(d["qty"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return jsonify({"error": "product_id and qty required"}), 400
    if qty <= 0:
        return jsonify({"error": "qty must be positive"}), 400
    method = d.get("payment_method", "CASH")
    if method not in ("CASH", "MTN_MOMO", "AIRTEL_MOMO", "CREDIT"):
        return jsonify({"error": "bad payment_method"}), 400
    prod = q_one("SELECT * FROM products WHERE id=?", (pid,))
    if not prod:
        return jsonify({"error": "product not found"}), 404
    unit_price = float(d.get("unit_price") or prod["price_sell"] or 0)
    sale_date = d.get("sale_date") or today_str()
    db = get_db()
    try:
        allocations = deduct_fefo_allocations(db, pid, qty)
        first_batch = allocations[0][0]
        ref = next_receipt_ref(sale_date)
        cur = db.execute("INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,payment_method,served_by,receipt_ref,customer_name,customer_phone) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sale_date, pid, first_batch, qty, unit_price, unit_price * qty, method, d.get("served_by", ""), ref, d.get("customer_name", ""), d.get("customer_phone", "")))
        for batch_id, taken in allocations:
            db.execute("INSERT INTO sale_batches(sale_id,batch_id,qty) VALUES(?,?,?)", (cur.lastrowid, batch_id, taken))
        db.commit()
        lid = cur.lastrowid
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    upsert_customer(d.get("customer_name", ""), d.get("customer_phone", ""))
    return jsonify({"id": lid, "receipt_ref": ref, "total": unit_price * qty}), 201


@bp.route("/api/sales/cart", methods=["POST"])
def api_cart():
    """Multi-item basket -> one receipt. Body: {items:[{product_id,qty,unit_price?}], payment_method, served_by, sale_date, customer_name}"""
    d = request.json or {}
    items = d.get("items", [])
    if not items:
        return jsonify({"error": "basket is empty"}), 400
    method = d.get("payment_method", "CASH")
    if method not in ("CASH", "MTN_MOMO", "AIRTEL_MOMO", "CREDIT"):
        return jsonify({"error": "bad payment_method"}), 400
    if method == "CREDIT" and not (d.get("customer_name") or "").strip():
        return jsonify({"error": "customer name required for CREDIT sales"}), 400
    sale_date = d.get("sale_date") or today_str()
    lines = []
    for it in items:
        try:
            pid, qty = int(it["product_id"]), int(it["qty"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return jsonify({"error": "each item needs product_id and qty"}), 400
        if qty <= 0:
            return jsonify({"error": "qty must be positive"}), 400
        prod = q_one("SELECT * FROM products WHERE id=?", (pid,))
        if not prod:
            return jsonify({"error": f"product {pid} not found"}), 404
        unit = float(it.get("unit_price") or prod["price_sell"] or 0)
        lines.append({"prod": prod, "qty": qty, "unit": unit})
    db = get_db()
    try:
        ref = next_receipt_ref(sale_date)
        total = 0
        for ln in lines:
            allocations = deduct_fefo_allocations(db, ln["prod"]["id"], ln["qty"])
            first = allocations[0][0]
            t = ln["unit"] * ln["qty"]
            total += t
            cur = db.execute("INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,payment_method,served_by,receipt_ref,customer_name,customer_phone) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sale_date, ln["prod"]["id"], first, ln["qty"], ln["unit"], t, method, d.get("served_by", ""), ref, d.get("customer_name", ""), d.get("customer_phone", "")))
            for batch_id, taken in allocations:
                db.execute("INSERT INTO sale_batches(sale_id,batch_id,qty) VALUES(?,?,?)", (cur.lastrowid, batch_id, taken))
        db.commit()
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    upsert_customer(d.get("customer_name", ""), d.get("customer_phone", ""))
    return jsonify({"receipt_ref": ref, "total": total, "lines": len(lines)}), 201


@bp.route("/api/receipts/<ref>")
def api_receipt_ref(ref):
    rows = q_all("""SELECT s.*, p.name as product_name, p.unit FROM sales s
                    JOIN products p ON p.id=s.product_id WHERE s.receipt_ref=? ORDER BY s.id""", (ref,))
    if not rows:
        return jsonify({"error": "receipt not found"}), 404
    return jsonify({
        "shop_name": get_setting("shop_name"),
        "shop_branch": get_setting("shop_branch"),
        "shop_phone": get_setting("shop_phone"),
        "receipt_no": ref,
        "footer": get_setting("receipt_footer"),
        "sale_date": rows[0]["sale_date"],
        "payment_method": rows[0]["payment_method"],
        "served_by": rows[0].get("served_by", ""),
        "customer_name": rows[0].get("customer_name", ""),
        "customer_phone": rows[0].get("customer_phone", ""),
        "lines": rows,
        "total": sum(r["total"] for r in rows),
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


# ---------- receipts ----------
@bp.route("/api/sales/<int:sid>/receipt")
def api_receipt(sid):
    s = q_one("""SELECT s.*, p.name as product_name, p.unit FROM sales s
                 JOIN products p ON p.id=s.product_id WHERE s.id=?""", (sid,))
    if not s:
        return jsonify({"error": "sale not found"}), 404
    return jsonify({
        "shop_name": get_setting("shop_name"),
        "shop_branch": get_setting("shop_branch"),
        "shop_phone": get_setting("shop_phone"),
        "receipt_no": f"R-{sid:06d}",
        "footer": get_setting("receipt_footer"),
        "sale": s,
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


@bp.route("/api/sales/day-report")
def api_day_report():
    day = request.args.get("date", today_str())
    rows = q_all("""SELECT s.*, p.name as product_name FROM sales s
                    JOIN products p ON p.id=s.product_id WHERE sale_date=? ORDER BY s.id""", (day,))
    return jsonify({"date": day, "shop_name": get_setting("shop_name"),
                    "summary": sales_summary(day), "rows": rows})
