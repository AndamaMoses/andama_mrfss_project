"""Patients routes: CRUD and refill reminders.

Route bodies carried over verbatim from app.py (Phase 4.4); the DELETE branch
of ``api_patient_one`` keeps its inline admin check because the view is a
mixed-method one (PUT/POST/DELETE, like ``api_products``).
"""
from flask import Blueprint, jsonify, request

from drugshop.auth.guards import current_user
from drugshop.core.utils import today_str
from drugshop.db import execute, q_all
from drugshop.patients.service import refill_due

bp = Blueprint("patients", __name__)


def _cycle_days(d):
    raw = d.get("cycle_days", 30)
    if raw is None:
        return 30
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


# patients
@bp.route("/api/patients", methods=["GET", "POST"])
def api_patients():
    if request.method == "GET":
        rows = q_all("SELECT pt.*, p.name as drug_name FROM patients pt LEFT JOIN products p ON p.id=pt.product_id ORDER BY pt.name")
        return jsonify(rows)
    d = request.json or {}
    if not d.get("name") or not d.get("phone") or not d.get("last_refill_date"):
        return jsonify({"error": "name, phone, last_refill_date required"}), 400
    cycle = _cycle_days(d)
    if cycle is None:
        return jsonify({"error": "cycle_days must be a number"}), 400
    lid = execute("INSERT INTO patients(name,phone,product_id,last_refill_date,cycle_days,notes) VALUES(?,?,?,?,?,?)",
        (d["name"].strip(), d["phone"].strip(), d.get("product_id"), d["last_refill_date"], cycle, d.get("notes", "")))
    return jsonify({"id": lid}), 201


@bp.route("/api/patients/<int:pid>", methods=["PUT", "DELETE", "POST"])
def api_patient_one(pid):
    if request.method == "DELETE":
        me = current_user()
        if not me or me["role"] != "admin":
            return jsonify({"error": "admin only"}), 403
        execute("DELETE FROM patients WHERE id=?", (pid,))
        return jsonify({"ok": True})
    d = request.json or {}
    if request.method == "POST":  # refill action: set last_refill=today
        execute("UPDATE patients SET last_refill_date=? WHERE id=?", (today_str(), pid))
        return jsonify({"ok": True, "last_refill_date": today_str()})
    cycle = _cycle_days(d)
    if cycle is None:
        return jsonify({"error": "cycle_days must be a number"}), 400
    execute("UPDATE patients SET name=?,phone=?,product_id=?,last_refill_date=?,cycle_days=?,notes=? WHERE id=?",
        (d.get("name"), d.get("phone"), d.get("product_id"), d.get("last_refill_date"), cycle, d.get("notes", ""), pid))
    return jsonify({"ok": True})


@bp.route("/api/reminders")
def api_reminders():
    return jsonify(refill_due())
