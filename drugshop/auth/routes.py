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
from drugshop.db import execute, get_db, q_all, q_one

bp = Blueprint("auth", __name__)


@bp.route("/api/personas")
def api_personas():
    rows = q_all("SELECT id, username, role, display_name FROM users ORDER BY id")
    return jsonify(rows)


def _login_candidates(raw_user):
    """Rank the users a typed identifier could mean, best match first.

    Shop staff sign in with whatever they remember: their username, their full
    profile name, or just a first/last name ("Sarah"). Ambiguous names are fine
    because the password still has to pick the right account.
    """
    needle = raw_user.casefold()
    ranked = []
    for u in q_all("SELECT * FROM users"):
        username = (u.get("username") or "").casefold()
        display = (u.get("display_name") or "").casefold()
        if needle == username:
            rank = 0
        elif needle == display:
            rank = 1
        elif needle in display.split():
            rank = 2
        else:
            continue
        ranked.append((rank, u["id"], u))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [u for _, _, u in ranked]


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

    u = next(
        (row for row in _login_candidates(raw_user)
         if check_password_hash(row["pass_hash"], raw_pass)),
        None,
    )
    if not u:
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
    # Keep the sign-in audit trail but detach it from the deleted account;
    # login_events.user_id is a foreign key, so the row cannot stay linked.
    db = get_db()
    try:
        db.execute("UPDATE login_events SET user_id=NULL WHERE user_id=?", (uid,))
        db.execute("DELETE FROM users WHERE id=?", (uid,))
        db.commit()
    except sqlite3.DatabaseError:
        db.rollback()
        raise
    finally:
        db.close()
    return jsonify({"ok": True})


@bp.route("/api/users/<int:uid>/reset-password", methods=["POST"])
def api_user_reset_pw(uid):
    """Admin lockout recovery: set a new password for a staff account."""
    me = current_user()
    if not me or me["role"] != "admin":
        return jsonify({"error": "admin only"}), 403
    u = q_one("SELECT id, username FROM users WHERE id=?", (uid,))
    if not u:
        return jsonify({"error": "staff not found"}), 404
    d = request.json or {}
    new = d.get("password") or ""
    if len(new) < 6:
        return jsonify({"error": "new password must be 6+ characters"}), 400
    execute("UPDATE users SET pass_hash=? WHERE id=?", (generate_password_hash(new), uid))
    return jsonify({"ok": True, "username": u["username"]})


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
