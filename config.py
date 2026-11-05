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
import math
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")
_LEGACY_DB = os.path.join(PROJECT_ROOT, "drugshop.db")
_INSTANCE_DB = os.path.join(INSTANCE_DIR, "drugshop.db")
_LEGACY_UPLOADS = os.path.join(PROJECT_ROOT, "uploads")
_INSTANCE_UPLOADS = os.path.join(INSTANCE_DIR, "uploads")


def _load_dotenv(path=os.path.join(PROJECT_ROOT, ".env")):
    """Load ``KEY=VALUE`` lines from ``.env`` into the process environment.

    Values already exported in the real environment always win, so production
    secret stores are never overridden by a stray file. Lines may be blank,
    comments (``#``), or prefixed with ``export``. Quoted values are unquoted.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].lstrip()
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


_load_dotenv()


def _env_float(name, default):
    """Read a positive float from the environment, falling back safely.

    A blank or malformed value (for example ``MOMO_TIMEOUT=``) must not stop
    the app from starting: operators edit ``.env`` by hand, so a bad value is
    treated as "use the default" rather than a fatal configuration error.
    """
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return float(default)
    if not math.isfinite(value) or value <= 0:
        return float(default)
    return value


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
    # Optional: set to ".example.com" when Tender Copilot is served from a
    # subdomain of the pharmacy install so one sign-in works on both hosts.
    # Leave unset for the default single-origin deployment.
    SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN") or None
    # Packaging (Phase 1): bundle to seed when the installation has no plan
    # yet. "legacy" grandfathers the existing Onzima shop (Pro + Alerts +
    # Tender); new deployments set DRUGSHOP_BUNDLE=core. SUPPORT_WHATSAPP is
    # shown on upgrade prompts.
    DEFAULT_BUNDLE = os.environ.get("DRUGSHOP_BUNDLE", "legacy")
    SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "")
    # Show the synthetic-data banner on the public Render preview. Kept
    # separate from the seeder so a shop can label a demo database without
    # re-running the seed.
    DEMO_MODE = os.environ.get("DEMO_SEED", "").strip().lower() in {"1", "true", "yes", "on"}
    # MTN MoMo Collections (https://momodeveloper.mtn.com). The subscription
    # key is issued per product subscription; the API user/key are created in
    # the target environment once with `flask --app run momo provision`.
    # Leave the key blank to keep MoMo disabled; the POS still records manual
    # MTN_MOMO takings.
    MOMO_SUBSCRIPTION_KEY = os.environ.get("MOMO_SUBSCRIPTION_KEY", "").strip()
    MOMO_API_USER = os.environ.get("MOMO_API_USER", "").strip()
    MOMO_API_KEY = os.environ.get("MOMO_API_KEY", "").strip()
    MOMO_TARGET_ENVIRONMENT = os.environ.get("MOMO_TARGET_ENVIRONMENT", "sandbox").strip()
    MOMO_BASE_URL = os.environ.get("MOMO_BASE_URL", "").strip()
    # Blank means: EUR on the MTN sandbox (its only supported currency) and
    # UGX on production environments. Set it explicitly for other markets.
    MOMO_CURRENCY = os.environ.get("MOMO_CURRENCY", "").strip().upper()
    MOMO_CALLBACK_URL = os.environ.get("MOMO_CALLBACK_URL", "").strip()
    # MTN cannot send a session cookie, so the callback is authenticated with a
    # shared secret carried in the URL (or X-Callback-Token). Blank disables
    # the callback route; polling still works.
    MOMO_CALLBACK_SECRET = os.environ.get("MOMO_CALLBACK_SECRET", "").strip()
    MOMO_TIMEOUT = _env_float("MOMO_TIMEOUT", 20)
    # Re-check the MTN reference when a sale is recorded (default on). Set
    # MOMO_VERIFY_SALES=0 only for a monitored rollout that records manually.
    MOMO_VERIFY_SALES = os.environ.get("MOMO_VERIFY_SALES", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    # Airtel Money OpenAPI (https://developers.airtel.africa). The client uses
    # OAuth2 client credentials and the Uganda collection/status endpoints.
    # Leave the client id/secret blank to keep Airtel disabled; the POS still
    # records manual AIRTEL_MOMO takings.
    AIRTEL_BASE_URL = os.environ.get(
        "AIRTEL_BASE_URL", "https://openapiuat.airtel.africa"
    ).strip()
    AIRTEL_CLIENT_ID = os.environ.get("AIRTEL_CLIENT_ID", "").strip()
    AIRTEL_CLIENT_SECRET = os.environ.get("AIRTEL_CLIENT_SECRET", "").strip()
    AIRTEL_CURRENCY = os.environ.get("AIRTEL_CURRENCY", "UGX").strip().upper() or "UGX"
    AIRTEL_COUNTRY = os.environ.get("AIRTEL_COUNTRY", "UG").strip().upper() or "UG"
    AIRTEL_TIMEOUT = _env_float("AIRTEL_TIMEOUT", 20)
    # Re-check an Airtel reference when a sale is recorded (default on). Set
    # AIRTEL_VERIFY_SALES=0 only for a monitored rollout that records manually.
    AIRTEL_VERIFY_SALES = os.environ.get(
        "AIRTEL_VERIFY_SALES", "1"
    ).strip().lower() not in {"0", "false", "no", "off"}
    # Airtel cannot send a session cookie, so the callback is authenticated
    # with a shared secret carried in the URL, X-Callback-Token, or
    # Authorization header. Blank disables the callback route; polling and the
    # reconciliation sweep still work.
    AIRTEL_CALLBACK_URL = os.environ.get("AIRTEL_CALLBACK_URL", "").strip()
    AIRTEL_CALLBACK_SECRET = os.environ.get("AIRTEL_CALLBACK_SECRET", "").strip()


class DevConfig(BaseConfig):
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"


class ProdConfig(BaseConfig):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    REQUIRE_SECRET_KEY = True
    # Hosted deployments terminate TLS at the proxy; never send the session
    # cookie over plain HTTP. Local development uses DevConfig instead.
    SESSION_COOKIE_SECURE = True
