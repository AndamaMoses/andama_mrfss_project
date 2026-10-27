"""Build a disposable Flask app on a scratch database.

The harness is the only place that wires persona runs to the application. It
refuses the known live database paths; callers must point at ``instance/qa``
or a temporary directory. Passwords are fixed for the scratch database so a
run is repeatable even if the developer shell has production credentials set.
"""
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from drugshop import create_app
from drugshop import db as dbm
from drugshop.apps import service as apps_service
from drugshop.auth import service as auth_service
from drugshop.db import execute, q_one
from qa.seeds import apply_seed

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QA_ADMIN_PASSWORD = "qa-admin-pass"
QA_STAFF_PASSWORD = "qa-staff-pass"
LIVE_PATHS = {
    (PROJECT_ROOT / "drugshop.db").resolve(),
    (PROJECT_ROOT / "instance" / "drugshop.db").resolve(),
}


def assert_scratch_path(db_path):
    """Refuse to touch the live pilot database or an arbitrary directory."""
    resolved = Path(db_path).expanduser().resolve()
    if resolved in LIVE_PATHS:
        raise ValueError(
            f"refusing to use the live database at {resolved}; "
            "pass a path under instance/qa or a temporary directory"
        )
    temp_root = Path(tempfile.gettempdir()).resolve()
    under_temp = temp_root in resolved.parents or resolved == temp_root
    parts = resolved.parts
    under_qa = "instance" in parts and "qa" in parts
    if not (under_temp or under_qa):
        raise ValueError(
            f"refusing to use {resolved}; QA databases must live under "
            "instance/qa or the system temporary directory"
        )
    return resolved


def build_scratch_app(db_path, upload_dir, plan="pro", profile="pharmacy_day"):
    """Create, seed, and return an isolated app for one persona run."""
    db_path = assert_scratch_path(db_path)
    upload_dir = Path(upload_dir).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # A fresh config class per call avoids leaking DATABASE/UPLOAD_DIR/plan
    # between runs. Passwords are forced below, after bootstrap, so inherited
    # ADMIN_PASSWORD/STAFF_PASSWORD values can never become scratch logins.
    scratch_config = type(
        "ScratchConfig",
        (),
        {
            "TESTING": True,
            "SECRET_KEY": "qa-scratch-secret",
            "SUPPORT_WHATSAPP": "+256700000000",
            "DATABASE": str(db_path),
            "UPLOAD_DIR": str(upload_dir),
            "DEFAULT_BUNDLE": plan,
        },
    )

    app = create_app(scratch_config)
    dbm.init_db()
    auth_service.ensure_admin()
    _ensure_qa_passwords()

    seeded = apps_service.ensure_entitlements(plan)
    if not seeded.get("seeded"):
        apps_service.set_bundle(plan, actor="qa-harness", notes="scratch QA run")

    apply_seed(profile)
    app.config.update(TESTING=True, SECRET_KEY="qa-scratch-secret")
    return app


def _ensure_qa_passwords():
    """Keep scratch logins stable even when a scratch DB is reused."""
    for username, password in (
        ("admin", QA_ADMIN_PASSWORD),
        ("grace", QA_STAFF_PASSWORD),
    ):
        if q_one("SELECT id FROM users WHERE username=?", (username,)):
            execute(
                "UPDATE users SET pass_hash=? WHERE username=?",
                (auth_service.generate_password_hash(password), username),
            )


def password_for(persona):
    return QA_ADMIN_PASSWORD if persona["role"] == "admin" else QA_STAFF_PASSWORD


def db_sha256(db_path):
    digest = hashlib.sha256()
    with open(db_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit():
    git = shutil.which("git")
    if not git:
        return "unknown"
    try:
        result = subprocess.run(  # noqa: S603 - trusted git executable, fixed arguments
            [git, "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return result.stdout.strip() or "unknown"
