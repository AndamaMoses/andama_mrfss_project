"""Production WSGI entry point for gunicorn (Render, containers, VMs).

Gunicorn imports ``wsgi:app``. The start command uses ``--preload`` so the
idempotent bootstrap below runs once in the master process before workers fork;
this also avoids two workers racing to create the SQLite schema on first boot.
"""
import os

from config import ProdConfig
from drugshop import create_app
from drugshop.apps.service import ensure_entitlements
from drugshop.auth.service import ensure_admin
from drugshop.db import init_db

app = create_app(ProdConfig)


def _enabled(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def bootstrap():
    """Create the schema, bootstrap accounts, plan, and optional demo data."""
    init_db()
    ensure_admin()
    plan = ensure_entitlements(app.config["DEFAULT_BUNDLE"])
    if plan["seeded"]:
        print(f"Plan seeded: {plan['label']} ({', '.join(plan['apps'])})")
    if _enabled("DEMO_SEED"):
        from drugshop.demo import seed_demo

        demo = seed_demo()
        if demo["seeded"]:
            print(
                f"Demo data seeded: {demo['products']} products, "
                f"{demo['sales']} sales, {demo['patients']} patients"
            )


bootstrap()
