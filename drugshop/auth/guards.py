"""Auth guards: the API session gate, current_user, and decorators.

``admin_required`` replaces the old per-route inline admin checks (applied
across the domain modules in Phase 4). ``login_required`` is available for
routes outside the ``/api/`` gate scope. Phase 6 removed the legacy login
backdoor and made ``/api/seed`` non-public; session-cookie hardening lives in
``config.py``.
"""
from functools import wraps

from flask import jsonify, request, session

from drugshop.db import q_one

# /api/personas stays public so the login page can render profile cards; it
# exposes only id/username/role/display_name (never password material).
OPEN_API = {"/api/login", "/api/logout", "/api/me", "/api/personas"}


def current_user():
    if not session.get("uid"):
        return None
    u = q_one("SELECT id, username, role, display_name, phone FROM users WHERE id=?", (session["uid"],))
    if u and not u.get("display_name"):
        u["display_name"] = u["username"]
    return u


def register_gate(app):
    """Require a logged-in session for every /api/ path outside OPEN_API."""

    @app.before_request
    def gate():
        if request.path.startswith("/api/") and request.path not in OPEN_API and not session.get("uid"):
            return jsonify({"error": "login required"}), 401


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "login required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        me = current_user()
        if not me or me["role"] != "admin":
            return jsonify({"error": "admin only"}), 403
        return fn(*args, **kwargs)

    return wrapper
