"""App catalog API used by the launcher, navigation, and plan panel.

``GET /api/apps`` is authenticated by the global auth gate and always-on in the
entitlement map: the launcher must work even for a Core-only installation.
The payload exposes catalog metadata and entitlement booleans only; it never
includes notes, sources, or event history.
"""
import sqlite3

from flask import Blueprint, current_app, jsonify

from drugshop.apps import registry
from drugshop.apps.service import current_plan

bp = Blueprint("apps", __name__)


@bp.route("/api/apps")
def api_apps():
    try:
        plan = current_plan()
        entitled = set(plan["apps"])
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        # Fail open, matching the request gate: a pre-migration deployment
        # should still render its launcher rather than crash.
        current_app.logger.warning(
            "entitlements unavailable (%s); reporting fail-open plan", exc
        )
        plan = {
            "bundle": "unseeded",
            "label": "Unseeded",
            "status": "active",
            "expires_at": None,
        }
        entitled = set(registry.APPS)

    apps = [
        {
            "id": meta["id"],
            "name": meta["name"],
            "description": meta["description"],
            "icon": meta["icon"],
            "tabs": list(meta["tabs"]),
            "href": meta.get("href", ""),
            "bundle": meta["bundle"],
            "entitled": bool(meta["always_on"] or meta["id"] in entitled),
            "always_on": bool(meta["always_on"]),
        }
        for meta in (registry.APPS[app_id] for app_id in registry.app_ids())
    ]
    return jsonify({
        "plan": {
            "bundle": plan["bundle"],
            "label": plan["label"],
            "status": plan["status"],
            "expires_at": plan["expires_at"],
        },
        "apps": apps,
        "support": {
            "whatsapp": current_app.config.get("SUPPORT_WHATSAPP") or "",
            "message": "Upgrade your plan",
        },
    })
