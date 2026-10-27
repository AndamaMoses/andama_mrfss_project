"""Reporting routes: dashboard, my-sales, staff-activity, backup, export.

Route bodies carried over verbatim from app.py (Phase 4.9). Two intentional
substitutions, both behavior-preserving: ``api_staff_activity`` used the
``admin_required`` decorator (its monolith body checked admin at the top for
its only method), and ``api_backup`` reads the DB path via the ``db_path()``
accessor instead of the legacy ``DB_PATH`` global (same value — both come from
``app.config["DATABASE"]``). Dashboard aggregations and CSV columns are
unchanged.
"""
import csv
import io

from flask import Blueprint, Response, jsonify, request, send_file

from drugshop.auth.guards import admin_required, current_user
from drugshop.core.utils import today_str
from drugshop.db import db_path, q_all, q_one
from drugshop.inventory.service import expiry_report, stock_levels
from drugshop.patients.service import refill_due
from drugshop.sales.service import sales_summary

bp = Blueprint("reporting", __name__)


@bp.route("/api/my-sales")
def api_my_sales():
    me = current_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    day = request.args.get("date", today_str())
    rows = q_all("""SELECT s.*, p.name as product_name FROM sales s
                    JOIN products p ON p.id=s.product_id
                    WHERE s.sale_date=? AND (s.served_by=? OR s.served_by=?)
                    ORDER BY s.id DESC""", (day, me.get("display_name") or "", me["username"]))
    return jsonify({"date": day, "count": len(rows),
                    "total": sum(r["total"] for r in rows), "rows": rows})


@bp.route("/api/staff-activity")
@admin_required
def api_staff_activity():
    day = request.args.get("date", today_str())
    sales = q_all("""SELECT COALESCE(NULLIF(served_by,''),'(unrecorded)') as staff,
                     COUNT(*) as sales, COALESCE(SUM(total),0) as revenue
                     FROM sales WHERE sale_date=? GROUP BY staff ORDER BY revenue DESC""", (day,))
    logins = q_all("""SELECT l.username, COALESCE(u.display_name,l.username) as name, l.login_at, l.ip
                      FROM login_events l LEFT JOIN users u ON u.id=l.user_id
                      ORDER BY l.id DESC LIMIT 20""")
    return jsonify({"date": day, "sales_by_staff": sales, "recent_logins": logins})


@bp.route("/api/dashboard")
def api_dashboard():
    day = request.args.get("date", today_str())
    exp = expiry_report()
    stock = stock_levels()
    refill = refill_due()
    owed = q_one("""SELECT COALESCE(SUM(CASE WHEN bal > 0.005 THEN bal ELSE 0 END),0) t FROM (
                      SELECT s.total - COALESCE((SELECT SUM(amount) FROM credit_payments WHERE sale_id=s.id),0) as bal
                      FROM sales s WHERE s.payment_method='CREDIT'
                    )""")["t"]
    return jsonify({
        "date": day,
        "sales_today": sales_summary(day),
        "credit_owed_total": round(owed, 2),
        "stock": stock,
        "low_stock_count": sum(1 for s in stock if s["low_stock"]),
        "expiry_counts": {k: len(v) for k, v in exp.items()},
        "expiry_critical": exp["expired"] + exp["critical_30"],
        "refill": {"due_count": len(refill["due"]), "due": refill["due"][:10]},
        "stock_value": sum(s["stock_on_hand"] * (s["price_buy"] or 0) for s in stock),
    })


# ---------- backup + CSV export ----------
@bp.route("/api/backup")
@admin_required
def api_backup():
    return send_file(db_path(), as_attachment=True, download_name=f"drugshop-backup-{today_str()}.db")


@bp.route("/api/export/<which>")
def api_export(which):
    buf = io.StringIO()
    if which == "sales":
        rows = q_all("SELECT s.id, s.sale_date, p.name as product_name, s.qty, s.unit_price, s.total, s.payment_method, s.receipt_ref, s.customer_name FROM sales s JOIN products p ON p.id=s.product_id ORDER BY s.id")
        w = csv.writer(buf)
        w.writerow(["id", "date", "product", "qty", "unit_price", "total", "method", "receipt", "customer"])
        for r in rows:
            w.writerow([r["id"], r["sale_date"], r["product_name"], r["qty"], r["unit_price"], r["total"], r["payment_method"], r.get("receipt_ref", ""), r.get("customer_name", "")])
    elif which == "stock":
        w = csv.writer(buf)
        w.writerow(["product", "on_hand", "reorder", "buy", "sell"])
        for r in stock_levels():
            w.writerow([r["name"], r["stock_on_hand"], r["reorder_level"], r["price_buy"], r["price_sell"]])
    elif which == "patients":
        rows = q_all("SELECT * FROM patients ORDER BY name")
        w = csv.writer(buf)
        w.writerow(["name", "phone", "last_refill", "cycle_days", "notes"])
        for r in rows:
            w.writerow([r["name"], r["phone"], r["last_refill_date"], r["cycle_days"], r["notes"]])
    else:
        return jsonify({"error": "unknown export (sales|stock|patients)"}), 404
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={which}-{today_str()}.csv"})
