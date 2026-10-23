"""Auth domain services.

Phase 6 security hardening: ``ensure_admin`` bootstraps the default users only
when the users table is empty. It never updates an existing user's password, so
restarting the server cannot resurrect default credentials.
"""
from werkzeug.security import generate_password_hash

from drugshop.db import execute, q_one

DEFAULT_USERS = (
    # username, password, role, display_name
    ("admin", "admin123", "admin", "Charles Onzima"),
    ("grace", "grace123", "attendant", "Sarah Achen"),
)


def ensure_admin():
    if q_one("SELECT id FROM users LIMIT 1"):
        return
    for username, password, role, display_name in DEFAULT_USERS:
        execute(
            "INSERT INTO users(username,pass_hash,role,display_name) VALUES(?,?,?,?)",
            (username, generate_password_hash(password), role, display_name),
        )
        print(f"** Bootstrap login created: {username} / {password} (change it immediately) **")
