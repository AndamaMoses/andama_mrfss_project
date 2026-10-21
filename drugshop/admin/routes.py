"""Admin routes: shop settings and demo-data seeding.

Route bodies carried over from app.py (Phase 4.10); no service file - no
reusable helpers here. Phase 6 hardening: settings writes and demo seeding are
admin-only (settings reads remain available to any signed-in user); the seed
guard (second POST -> ``"already seeded"`` note) and the settings allow-list
(only ``SHOP_DEFAULTS`` keys are persisted) are unchanged.
"""
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from drugshop.auth.guards import admin_required, current_user
from drugshop.core.settings import SHOP_DEFAULTS, get_setting
from drugshop.db import get_db

bp = Blueprint("admin", __name__)


# ---------- settings ----------
@bp.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify({k: get_setting(k) for k in SHOP_DEFAULTS})
    me = current_user()
    if not me or me["role"] != "admin":
        return jsonify({"error": "admin only"}), 403
    d = request.json or {}
    if not isinstance(d, dict):
        return jsonify({"error": "settings object required"}), 400
    db = get_db()
    try:
        for k, v in d.items():
            if k in SHOP_DEFAULTS:
                db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
        db.commit()
    finally:
        db.close()
    return jsonify({"ok": True})


# seed
@bp.route("/api/seed", methods=["POST"])
@admin_required
def api_seed():
    db = get_db()
    if db.execute("SELECT COUNT(*) c FROM products").fetchone()[0] > 0:
        db.close()
        return jsonify({"ok": True, "note": "already seeded"})
    prods = [
        ("Amoxicillin 500mg", "Antibiotics", "caps", 20, 300, 500),
        ("Paracetamol 500mg", "Analgesics", "tabs", 50, 100, 200),
        ("Metformin 500mg", "Chronic-Diabetes", "tabs", 30, 250, 400),
        ("Amlodipine 5mg", "Chronic-BP", "tabs", 30, 300, 500),
        ("Artemether-Lumefantrine 20/120", "Antimalarial", "dose", 20, 2500, 4000),
        ("Omeprazole 20mg", "GIT", "caps", 20, 200, 400),
        ("ORS Sachet", "Rehydration", "sachet", 40, 800, 1500),
        ("Cetirizine 10mg", "Allergy", "tabs", 20, 150, 300),
    ]
    pmap = {}
    for p in prods:
        cur = db.execute("INSERT INTO products(name,category,unit,reorder_level,price_buy,price_sell) VALUES(?,?,?,?,?,?)", p)
        pmap[p[0]] = cur.lastrowid
    t = date.today()
    def iso(d): return d.isoformat()
    batches = [
        (pmap["Amoxicillin 500mg"], "BX-221", 100, iso(t + timedelta(days=400)), "Abacus Pharma", "INV-101"),
        (pmap["Paracetamol 500mg"], "PC-889", 200, iso(t + timedelta(days=25)), "Kampala Pharma", "INV-102"),
        (pmap["Metformin 500mg"], "MF-331", 120, iso(t + timedelta(days=300)), "Abacus Pharma", "INV-103"),
        (pmap["Amlodipine 5mg"], "AM-110", 5, iso(t + timedelta(days=500)), "Kampala Pharma", "INV-103"),
        (pmap["Artemether-Lumefantrine 20/120"], "AL-77", 60, iso(t + timedelta(days=20)), "Quality Chem", "INV-104"),
        (pmap["Omeprazole 20mg"], "OM-55", 80, iso(t - timedelta(days=5)), "Quality Chem", "INV-100"),
        (pmap["ORS Sachet"], "ORS-9", 100, iso(t + timedelta(days=200)), "Abacus Pharma", "INV-105"),
    ]
    batch_ids = {}
    for pid, bn, q, exp, sup, inv in batches:
        cur = db.execute("INSERT INTO batches(product_id,batch_no,qty_received,qty_remaining,expiry_date,supplier,invoice_no) VALUES(?,?,?,?,?,?,?)",
                         (pid, bn, q, q, exp, sup, inv))
        batch_ids[bn] = cur.lastrowid
    pats = [
        ("Nakato Grace", "0774123456", pmap["Metformin 500mg"], iso(t - timedelta(days=26)), 30, "Diabetes - monthly"),
        ("Ssemakula John", "0755987654", pmap["Amlodipine 5mg"], iso(t - timedelta(days=10)), 30, "Hypertension"),
        ("Amina Namono", "0701456789", pmap["Metformin 500mg"], iso(t - timedelta(days=32)), 30, "Overdue refill"),
    ]
    for n, ph, pid, last, cyc, notes in pats:
        db.execute("INSERT INTO patients(name,phone,product_id,last_refill_date,cycle_days,notes) VALUES(?,?,?,?,?,?)", (n, ph, pid, last, cyc, notes))
    db.execute("INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,payment_method,served_by) VALUES(?,?,?,?,?,?,?,?)",
               (iso(t), pmap["Paracetamol 500mg"], batch_ids["PC-889"], 10, 200, 2000, "CASH", "Charles"))
    db.execute("INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,payment_method,served_by) VALUES(?,?,?,?,?,?,?,?)",
               (iso(t), pmap["Amoxicillin 500mg"], batch_ids["BX-221"], 14, 500, 7000, "MTN_MOMO", "Charles"))
    db.execute("UPDATE batches SET qty_remaining=qty_remaining-10 WHERE id=?", (batch_ids["PC-889"],))
    db.execute("UPDATE batches SET qty_remaining=qty_remaining-14 WHERE id=?", (batch_ids["BX-221"],))
    db.commit()
    db.close()
    return jsonify({"ok": True, "note": "demo data loaded"})
