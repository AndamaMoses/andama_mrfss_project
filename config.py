"""Application configuration.

All values are environment-overridable. The DB defaults to
``instance/drugshop.db`` when that file exists, otherwise the legacy root
``drugshop.db``. Uploads default to ``instance/uploads`` unless the legacy
root ``uploads`` directory already holds files. No file is moved automatically.

Security defaults (Phase 6): debug is off unless ``FLASK_DEBUG=1``, session
cookies are HttpOnly + SameSite=Lax, and ``ProdConfig`` refuses to start
without ``SECRET_KEY``. Deploy behind HTTPS so cookies are not sent in clear
text; set ``SECRET_KEY`` from a secret store in production.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")
_LEGACY_DB = os.path.join(PROJECT_ROOT, "drugshop.db")
_INSTANCE_DB = os.path.join(INSTANCE_DIR, "drugshop.db")
_LEGACY_UPLOADS = os.path.join(PROJECT_ROOT, "uploads")
_INSTANCE_UPLOADS = os.path.join(INSTANCE_DIR, "uploads")


def _legacy_uploads_present():
    try:
        with os.scandir(_LEGACY_UPLOADS) as entries:
            return any(True for _ in entries)
    except FileNotFoundError:
        return False


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "drugshop-local-dev-key")
    DATABASE = os.environ.get(
        "DRUGSHOP_DB", _INSTANCE_DB if os.path.exists(_INSTANCE_DB) else _LEGACY_DB
    )
    UPLOAD_DIR = os.environ.get(
        "DRUGSHOP_UPLOADS", _LEGACY_UPLOADS if _legacy_uploads_present() else _INSTANCE_UPLOADS
    )
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Packaging (Phase 1): bundle to seed when the installation has no plan
    # yet. "pro" grandfathers the existing shop; new deployments set
    # DRUGSHOP_BUNDLE=core. SUPPORT_WHATSAPP is shown on upgrade prompts.
    DEFAULT_BUNDLE = os.environ.get("DRUGSHOP_BUNDLE", "pro")
    SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "")


class DevConfig(BaseConfig):
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"


class ProdConfig(BaseConfig):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    REQUIRE_SECRET_KEY = True
