"""Auth routes: personas, login/logout, profile, user management.

Phase 6 security hardening: login now uses a plain ``check_password_hash``
check (the legacy allow-list backdoor is gone), and failed logins return a
generic error without leaking default credentials.
"""
import contextlib
import sqlite3

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from drugshop.auth.guards import current_user
from drugshop.db import execute, q_all, q_one

bp = Blueprint("auth", __name__)


@bp.route("/api/personas")
def api_personas():
    rows = q_all("SELECT id, username, role, display_name FROM users ORDER BY id")
    return jsonify(rows)


@bp.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        d = request.form.to_dict()
    raw_user = (d.get("username") or "").strip()
    raw_pass = d.get("password") or ""

    if not raw_user:
        return jsonify({"error": "Please enter a username or click a profile card."}), 400
    if not raw_pass:
        return jsonify({"error": "Please enter a password."}), 400

    # Case-insensitive query matching username or display_name
    u = q_one("SELECT * FROM users WHERE LOWER(username)=LOWER(?) OR LOWER(display_name)=LOWER(?)",
              (raw_user, raw_user))
    if not u or not check_password_hash(u["pass_hash"], raw_pass):
        return jsonify({"error": "Invalid username or password."}), 401

    session.clear()
    session["uid"] = u["id"]
    with contextlib.suppress(sqlite3.Error):
        execute("INSERT INTO login_events(user_id,username,ip) VALUES(?,?,?)",
                (u["id"], u["username"], request.remote_addr or ""))
    return jsonify({"id": u["id"], "username": u["username"], "role": u["role"],
                    "display_name": u.get("display_name") or u["username"]})


@bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@bp.route("/api/me")
def api_me():
    u = current_user()
    return jsonify(u or {"user": None})


@bp.route("/api/me", methods=["PUT"])
def api_me_update():
    me = current_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    d = request.json or {}
    execute("UPDATE users SET display_name=?, phone=? WHERE id=?",
            ((d.get("display_name") or me["username"]).strip(), (d.get("phone") or "").strip(), me["id"]))
    return jsonify(current_user())


@bp.route("/api/users", methods=["GET", "POST"])
def api_users():
    me = current_user()
    if not me or me["role"] != "admin":
        return jsonify({"error": "admin only"}), 403
    if request.method == "GET":
        return jsonify(q_all("SELECT id, username, role, display_name, phone, created_at FROM users ORDER BY id"))
    d = request.json or {}
    if not d.get("username") or not d.get("password"):
        return jsonify({"error": "username and password required"}), 400
    try:
        lid = execute("INSERT INTO users(username,pass_hash,role,display_name) VALUES(?,?,?,?)",
                      (d["username"].strip(), generate_password_hash(d["password"]), d.get("role", "attendant"), d.get("display_name", d["username"]).strip()))
    except sqlite3.IntegrityError:
        return jsonify({"error": "username exists"}), 400
    return jsonify({"id": lid}), 201


@bp.route("/api/users/<int:uid>", methods=["DELETE"])
def api_user_del(uid):
    me = current_user()
    if not me or me["role"] != "admin":
        return jsonify({"error": "admin only"}), 403
    if uid == me["id"]:
        return jsonify({"error": "You cannot delete your own account"}), 400
    u = q_one("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        return jsonify({"error": "staff not found"}), 404
    if u["role"] == "admin" and q_one("SELECT COUNT(*) c FROM users WHERE role='admin'")["c"] <= 1:
        return jsonify({"error": "Cannot delete the last Shop Owner"}), 400
    execute("DELETE FROM users WHERE id=?", (uid,))
    return jsonify({"ok": True})


@bp.route("/api/change-password", methods=["POST"])
def api_change_pw():
    me = current_user()
    if not me:
        return jsonify({"error": "login required"}), 401
    d = request.json or {}
    u = q_one("SELECT * FROM users WHERE id=?", (me["id"],))
    if not check_password_hash(u["pass_hash"], d.get("old") or ""):
        return jsonify({"error": "old password is wrong"}), 400
    if len(d.get("new") or "") < 6:
        return jsonify({"error": "new password must be 6+ characters"}), 400
    execute("UPDATE users SET pass_hash=? WHERE id=?", (generate_password_hash(d["new"]), me["id"]))
    return jsonify({"ok": True})
