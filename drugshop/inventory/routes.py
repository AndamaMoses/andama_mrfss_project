"""Inventory routes: products, batches, expiry, supplier invoices, uploads.

Route bodies carried over verbatim from app.py (Phase 4.2); fully admin-only
views now use the ``admin_required`` decorator, mixed-method views keep their
inline checks. The invoice delete route still removes the uploaded file from
disk, and ``deduct_fefo`` (in ``service``) stays transactional for callers.
"""
import os
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory

from drugshop.auth.guards import admin_required, current_user
from drugshop.core.utils import safe_upload_name, today_str
from drugshop.db import execute, get_db, q_all, q_one, upload_dir
from drugshop.inventory.service import expiry_report, expiry_status, stock_levels

bp = Blueprint("inventory", __name__)


def _stored_upload_name(name):
    """Exact on-disk filename for a name stored in the DB (no sanitizing).

    New uploads are already sanitized by ``safe_upload_name``; legacy rows may
    contain characters it would rewrite, so only strip directories here.
    """
    return os.path.basename((name or "").replace("\\", "/"))


# products — Drug Catalogue (add/edit: admin only; read: all)
@bp.route("/api/products", methods=["GET", "POST"])
def api_products():
    if request.method == "GET":
        return jsonify(stock_levels())
    # POST — admin only
    me = current_user()
    if not me or me["role"] != "admin":
        return jsonify({"error": "Only the shop owner/admin can add drugs"}), 403
    d = request.json or {}
    if not d.get("name"):
        return jsonify({"error": "name required"}), 400
    try:
        lid = execute("INSERT INTO products(name,category,unit,reorder_level,price_buy,price_sell) VALUES(?,?,?,?,?,?)",
            (d["name"].strip(), d.get("category", "General"), d.get("unit", "tabs"),
             int(d.get("reorder_level", 10)), float(d.get("price_buy", 0)), float(d.get("price_sell", 0))))
    except sqlite3.IntegrityError:
        return jsonify({"error": "Product already exists"}), 400
    return jsonify({"id": lid}), 201


@bp.route("/api/products/<int:pid>", methods=["PUT", "DELETE"])
@admin_required
def api_product_one(pid):
    if request.method == "DELETE":
        if q_one("SELECT id FROM batches WHERE product_id=? LIMIT 1", (pid,)) or \
           q_one("SELECT id FROM sales WHERE product_id=? LIMIT 1", (pid,)):
            return jsonify({"error": "Cannot delete: stock batches or sales exist for this product. Void sales first."}), 400
        execute("DELETE FROM products WHERE id=?", (pid,))
        return jsonify({"ok": True})
    d = request.json or {}
    execute("UPDATE products SET name=?,category=?,unit=?,reorder_level=?,price_buy=?,price_sell=? WHERE id=?",
        (d.get("name"), d.get("category"), d.get("unit"), int(d.get("reorder_level", 10)),
         float(d.get("price_buy", 0)), float(d.get("price_sell", 0)), pid))
    return jsonify({"ok": True})


@bp.route("/api/batches/<int:bid>", methods=["DELETE"])
@admin_required
def api_batch_del(bid):
    if q_one("SELECT id FROM sales WHERE batch_id=? LIMIT 1", (bid,)):
        return jsonify({"error": "Cannot delete: sales were made from this batch. Void those sales first."}), 400
    execute("DELETE FROM batches WHERE id=?", (bid,))
    return jsonify({"ok": True})


ADJUSTMENT_REASONS = ("DAMAGED", "EXPIRED", "COUNT_CORRECTION", "OTHER")


@bp.route("/api/stock/adjustments", methods=["POST"])
@admin_required
def api_stock_adjustment():
    """Remove damaged/expired stock from a batch and keep an audit row."""
    d = request.json or {}
    try:
        batch_id = int(d["batch_id"])
        qty = int(d["qty"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return jsonify({"error": "batch_id and qty required"}), 400
    if qty <= 0:
        return jsonify({"error": "qty must be positive"}), 400
    reason = (d.get("reason") or "OTHER").upper()
    if reason not in ADJUSTMENT_REASONS:
        return jsonify({"error": f"reason must be one of {', '.join(ADJUSTMENT_REASONS)}"}), 400

    batch = q_one("SELECT * FROM batches WHERE id=?", (batch_id,))
    if not batch:
        return jsonify({"error": "batch not found"}), 404

    me = current_user() or {}
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE batches SET qty_remaining=qty_remaining-? "
            "WHERE id=? AND qty_remaining>=?",
            (qty, batch_id, qty),
        )
        if cur.rowcount != 1:
            db.rollback()
            return jsonify({"error": "qty exceeds the batch's remaining stock"}), 400
        db.execute(
            "INSERT INTO stock_adjustments(batch_id,product_id,qty,reason,note,adjusted_by)"
            " VALUES(?,?,?,?,?,?)",
            (batch_id, batch["product_id"], qty, reason,
             (d.get("note") or "").strip(), me.get("display_name") or me.get("username", "")),
        )
        db.commit()
        remaining = q_one("SELECT qty_remaining FROM batches WHERE id=?", (batch_id,))["qty_remaining"]
    finally:
        db.close()
    return jsonify({"ok": True, "batch_id": batch_id, "qty": qty, "remaining": remaining})


@bp.route("/api/invoices/<int:iid>", methods=["DELETE"])
@admin_required
def api_invoice_del(iid):
    inv = q_one("SELECT * FROM invoices WHERE id=?", (iid,))
    if inv and inv.get("image_name"):
        try:
            os.remove(os.path.join(upload_dir(), _stored_upload_name(inv["image_name"])))
        except OSError:
            pass
    execute("DELETE FROM invoices WHERE id=?", (iid,))
    return jsonify({"ok": True})


# batches
@bp.route("/api/batches", methods=["GET", "POST"])
def api_batches():
    if request.method == "GET":
        rows = q_all("SELECT b.*, p.name as product_name FROM batches b JOIN products p ON p.id=b.product_id ORDER BY b.expiry_date")
        for b in rows:
            b["status"] = expiry_status(b["expiry_date"])
        return jsonify(rows)
    d = request.json or {}
    for f in ("product_id", "expiry_date", "qty_received"):
        if d.get(f) in (None, ""):
            return jsonify({"error": f"{f} required"}), 400
    qty = int(d["qty_received"])
    lid = execute("INSERT INTO batches(product_id,batch_no,qty_received,qty_remaining,expiry_date,supplier,invoice_no) VALUES(?,?,?,?,?,?,?)",
        (int(d["product_id"]), d.get("batch_no", ""), qty, qty, d["expiry_date"], d.get("supplier", ""), d.get("invoice_no", "")))
    return jsonify({"id": lid}), 201


@bp.route("/api/expiry")
def api_expiry():
    return jsonify(expiry_report())


# invoices (photo + OCR-text hook for future AI)
@bp.route("/api/invoices", methods=["GET", "POST"])
def api_invoices():
    if request.method == "GET":
        return jsonify(q_all("SELECT * FROM invoices ORDER BY id DESC LIMIT 100"))
    # multipart (photo) or JSON
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("photo")
        fname = ""
        if f and f.filename:
            fname = datetime.now().strftime("%Y%m%d_%H%M%S_") + safe_upload_name(f.filename)
            f.save(os.path.join(upload_dir(), fname))
        lid = execute("INSERT INTO invoices(invoice_no,supplier,inv_date,image_name,ocr_text,status) VALUES(?,?,?,?,?,?)",
            (request.form.get("invoice_no", ""), request.form.get("supplier", ""), request.form.get("inv_date", today_str()), fname, request.form.get("ocr_text", ""), "PENDING"))
        return jsonify({"id": lid, "image": fname}), 201
    d = request.json or {}
    lid = execute("INSERT INTO invoices(invoice_no,supplier,inv_date,ocr_text,status) VALUES(?,?,?,?,?)",
        (d.get("invoice_no", ""), d.get("supplier", ""), d.get("inv_date", today_str()), d.get("ocr_text", ""), "PENDING"))
    return jsonify({"id": lid}), 201


@bp.route("/api/invoices/<int:iid>/post", methods=["POST"])
def api_invoice_post(iid):
    """Convert an invoice into batch stock lines. Body: items=[{product_id,qty_received,expiry_date,batch_no}]"""
    d = request.json or {}
    items = d.get("items", [])
    if not items:
        return jsonify({"error": "items required"}), 400
    try:
        lines = [
            (int(it["product_id"]), it.get("batch_no", ""), int(it["qty_received"]), it["expiry_date"])
            for it in items
        ]
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "items need product_id, qty_received and expiry_date"}), 400
    inv = q_one("SELECT * FROM invoices WHERE id=?", (iid,))
    db = get_db()
    try:
        for product_id, batch_no, qty, expiry_date in lines:
            db.execute("INSERT INTO batches(product_id,batch_no,qty_received,qty_remaining,expiry_date,supplier,invoice_no) VALUES(?,?,?,?,?,?,?)",
                (product_id, batch_no, qty, qty, expiry_date, (inv or {}).get("supplier", ""), (inv or {}).get("invoice_no", "")))
        db.execute("UPDATE invoices SET status='POSTED' WHERE id=?", (iid,))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()
    return jsonify({"ok": True, "posted": len(items)})


@bp.route("/uploads/<path:name>")
def uploads(name):
    return send_from_directory(upload_dir(), name)
