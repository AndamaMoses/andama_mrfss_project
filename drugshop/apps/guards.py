"""Server-side entitlement gate.

Registered after the auth gate in ``create_app()``, so anonymous ``/api/``
requests still get 401 before any entitlement work. The endpoint→app map is
built once, after every blueprint is registered, from the Flask URL map plus
the ownership tables in ``registry.py``.

Safety rule: if the entitlement schema is missing (for example a brand-new
deployment that has not run ``init_db()`` yet), this gate fails open and logs a
warning. An empty entitlement table is already fail-open inside the service.
"""
import sqlite3

from flask import current_app, g, jsonify, redirect, request, url_for

from drugshop.apps import registry
from drugshop.apps.service import entitled_app_ids

UNMAPPED = "__unmapped__"


def build_endpoint_map(app):
    """Map every non-static endpoint to an app id, None (always on), or UNMAPPED.

    Explicit endpoint overrides win over blueprint defaults. Unknown
    blueprints are marked UNMAPPED; the coverage test fails CI so a new route
    cannot silently become free.
    """
    mapping = {}
    for rule in app.url_map.iter_rules():
        endpoint = rule.endpoint
        if endpoint == "static":
            continue
        if endpoint in registry.ENDPOINT_APPS:
            mapping[endpoint] = registry.ENDPOINT_APPS[endpoint]
            continue
        blueprint = endpoint.split(".", 1)[0] if "." in endpoint else ""
        if blueprint in registry.ALWAYS_ON_BLUEPRINTS:
            mapping[endpoint] = None
        elif blueprint in registry.BLUEPRINT_APPS:
            mapping[endpoint] = registry.BLUEPRINT_APPS[blueprint]
        else:
            mapping[endpoint] = UNMAPPED
    return mapping


def _request_entitlements():
    """Entitlement ids for this request, cached on ``flask.g``."""
    cached = getattr(g, "entitled_apps", None)
    if cached is not None:
        return cached
    try:
        cached = entitled_app_ids()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        current_app.logger.warning(
            "entitlements unavailable (%s); failing open for this request", exc
        )
        cached = set(registry.APPS)
    g.entitled_apps = cached
    return cached


def _denial_payload(app_id):
    app = registry.APPS.get(app_id, {})
    return {
        "error": "app not entitled",
        "app": app_id,
        "message": f"{app.get('name', app_id)} is not included in your plan.",
        "upgrade": {"bundle": app.get("bundle") or None},
    }


def register_gate(app):
    """Install the entitlement ``before_request`` hook for this app."""
    endpoint_apps = build_endpoint_map(app)
    app.extensions["endpoint_apps"] = endpoint_apps

    @app.before_request
    def app_gate():
        endpoint = request.endpoint
        if not endpoint:
            return None
        app_id = endpoint_apps.get(endpoint)
        if app_id is None:
            return None
        if app_id == UNMAPPED:
            current_app.logger.warning(
                "endpoint %s is not in the app ownership map; allowing", endpoint
            )
            return None
        meta = registry.APPS.get(app_id)
        if meta and meta["always_on"]:
            return None
        if app_id in _request_entitlements():
            return None

        current_app.logger.info(
            "app access denied endpoint=%s app=%s", endpoint, app_id
        )
        payload = _denial_payload(app_id)
        if request.path.startswith("/api/"):
            return jsonify(payload), 403
        return redirect(url_for("web.index", upgrade=app_id))
