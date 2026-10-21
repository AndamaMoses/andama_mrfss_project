"""Notifications routes: low-stock alerts, SMS sending, SMS log.

Route bodies carried over verbatim from app.py (Phase 4.8); the
SIMULATED/SENT/WHATSAPP_LINK → 201 vs FAILED → 502 status mapping is
unchanged.
"""
from flask import Blueprint, jsonify, request

from drugshop.core.settings import get_setting
from drugshop.core.utils import normalize_ug_phone
from drugshop.db import execute, q_all
from drugshop.notifications.service import low_stock_items, send_sms_via_gateway

bp = Blueprint("notifications", __name__)


@bp.route("/api/alerts/low-stock")
def api_low_stock():
    items = low_stock_items()
    return jsonify({"count": len(items), "manager_phone": get_setting("manager_phone"), "items": items})


@bp.route("/api/alerts/send-sms", methods=["POST"])
def api_send_sms():
    d = request.json or {}
    raw_to = d.get("to") or get_setting("manager_phone")
    raw_msg = d.get("message")
    if not isinstance(raw_to, str) or not isinstance(raw_msg, str):
        return jsonify({"error": "to and message required"}), 400
    to = normalize_ug_phone(raw_to)
    msg = raw_msg.strip()
    channel = d.get("channel", "SMS")
    if not to or not msg:
        return jsonify({"error": "to and message required"}), 400
    status, resp = send_sms_via_gateway(to, msg) if channel == "SMS" else ("WHATSAPP_LINK", f"https://wa.me/{to}")
    execute("INSERT INTO sms_log(to_phone,channel,message,status,response) VALUES(?,?,?,?,?)", (to, channel, msg, status, resp))
    code = 201 if status in ("SENT", "SIMULATED", "WHATSAPP_LINK") else 502
    return jsonify({"status": status, "detail": resp}), code


@bp.route("/api/alerts/log")
def api_sms_log():
    return jsonify(q_all("SELECT * FROM sms_log ORDER BY id DESC LIMIT 100"))
