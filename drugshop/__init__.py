"""Drug Shop + Tender Copilot application package.

Modularization status (see modularization/IMPLEMENTATION_PLAN.md):
  Phase 1 - application factory + configuration (this file).
  Phase 4 - all route modules now live in this package as blueprints.
  Phase 5 - cut-over complete: ``run.py`` is the single entry point and the
  legacy root ``app.py`` has been removed.
"""
import os

from flask import Flask

from config import DevConfig

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app(config=None):
    """Create the Flask app and point the db layer at the configured paths.

    Database initialization is explicit — call ``drugshop.db.init_db()`` and
    ``drugshop.auth.service.ensure_admin()`` — so importing/creating an app
    has no data side effects (tests use their own temp databases).
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(PACKAGE_DIR, "templates"),
        static_folder=os.path.join(PACKAGE_DIR, "static"),
    )
    app.config.from_object(config or DevConfig)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    if not app.config.get("SESSION_COOKIE_SAMESITE"):
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if app.config.pop("REQUIRE_SECRET_KEY", False) and not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set when using ProdConfig")
    from drugshop import db as dbm
    from drugshop.admin.routes import bp as admin_bp
    from drugshop.apps import guards as app_guards
    from drugshop.apps.cli import register_cli
    from drugshop.apps.routes import bp as apps_bp
    from drugshop.auth import guards
    from drugshop.auth.routes import bp as auth_bp
    from drugshop.credit.routes import bp as credit_bp
    from drugshop.customers.routes import bp as customers_bp
    from drugshop.finance.routes import bp as finance_bp
    from drugshop.inventory.routes import bp as inventory_bp
    from drugshop.notifications.routes import bp as notifications_bp
    from drugshop.patients.routes import bp as patients_bp
    from drugshop.reporting.routes import bp as reporting_bp
    from drugshop.sales.routes import bp as sales_bp
    from drugshop.tender.routes import bp as tender_bp
    from drugshop.web.routes import bp as web_bp

    dbm.init_app(app)
    guards.register_gate(app)
    app.register_blueprint(web_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(credit_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reporting_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tender_bp)
    app.register_blueprint(apps_bp)
    # Registered last: the entitlement gate builds its endpoint map from the
    # complete URL map. The auth gate above stays first, so anonymous API
    # requests still receive 401 before entitlement checks.
    app_guards.register_gate(app)
    register_cli(app)
    return app
