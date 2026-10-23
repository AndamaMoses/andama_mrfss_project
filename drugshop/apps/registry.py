"""Static catalog of sellable apps and bundles.

Phase 1 of ``docs/packaging-plan.md``. This module is the single source of
truth for what the product can offer, which bundle contains which apps, and
which blueprints/endpoints belong to which app. Runtime enforcement (the
request gate and the ``/api/apps`` payload) arrives in Phase 2; the entitlement
service in ``service.py`` reads this catalog.
"""

# App ids are stable identifiers stored in the database. Never rename one
# without a migration; only its display metadata may change.
APPS = {
    "dashboard": {
        "id": "dashboard",
        "name": "Dashboard",
        "description": "Today at a glance: sales, stock, expiries, refills",
        "icon": "i-dash",
        "tabs": ["dash"],
        "href": "",
        "bundle": "",
        "requires": [],
        "always_on": True,
        "order": 10,
    },
    "pos": {
        "id": "pos",
        "name": "Point of Sale",
        "description": "Sell, take payment, print receipts, close the day",
        "icon": "i-pos",
        "tabs": ["pos"],
        "href": "",
        "bundle": "core",
        "requires": [],
        "always_on": False,
        "order": 20,
    },
    "inventory": {
        "id": "inventory",
        "name": "Inventory & Purchases",
        "description": "Stock, batches, expiries, supplier invoices",
        "icon": "i-stock",
        "tabs": ["stock", "inv", "drugs"],
        "href": "",
        "bundle": "core",
        "requires": [],
        "always_on": False,
        "order": 30,
    },
    "patients": {
        "id": "patients",
        "name": "Refill Care",
        "description": "Chronic patients and Day-25 refill reminders",
        "icon": "i-heart",
        "tabs": ["pat"],
        "href": "",
        "bundle": "pro",
        "requires": [],
        "always_on": False,
        "order": 40,
    },
    "finance": {
        "id": "finance",
        "name": "Finance",
        "description": "Credit ledger, reconciliation, expenses, profit",
        "icon": "i-coins",
        "tabs": ["rec", "fin"],
        "href": "",
        "bundle": "pro",
        "requires": [],
        "always_on": False,
        "order": 50,
    },
    "alerts": {
        "id": "alerts",
        "name": "Stock Alerts",
        "description": "Low-stock SMS and WhatsApp alerts",
        "icon": "i-bell",
        "tabs": ["alerts"],
        "href": "",
        "bundle": "growth",
        "requires": ["patients", "finance"],
        "always_on": False,
        "order": 60,
    },
    "tender": {
        "id": "tender",
        "name": "Tender Copilot",
        "description": "PPDA/UNRA tender analysis and methodology drafting",
        "icon": "i-hat",
        "tabs": [],
        "href": "/tender",
        "bundle": "tender",
        "requires": [],
        "always_on": False,
        "order": 70,
    },
}

# A bundle is a named set of apps. "growth" is the Pro set plus the alerts
# add-on, so a customer on Growth keeps everything Pro included.
BUNDLES = {
    "core": {
        "id": "core",
        "label": "Core",
        "apps": ["pos", "inventory"],
        "order": 10,
    },
    "pro": {
        "id": "pro",
        "label": "Pro",
        "apps": ["pos", "inventory", "patients", "finance"],
        "order": 20,
    },
    "growth": {
        "id": "growth",
        "label": "Growth",
        "apps": ["pos", "inventory", "patients", "finance", "alerts"],
        "order": 30,
    },
    "tender": {
        "id": "tender",
        "label": "Tender Copilot",
        "apps": ["tender"],
        "order": 40,
    },
    # Not sold: the existing Onzima installation keeps every app it had before
    # packaging. New deployments set DRUGSHOP_BUNDLE=core and buy upwards.
    "legacy": {
        "id": "legacy",
        "label": "Legacy (grandfathered)",
        "apps": ["pos", "inventory", "patients", "finance", "alerts", "tender"],
        "order": 50,
    },
}

# Apps that make an installation an operational pharmacy workspace. Tender
# Copilot uses this boundary to decide whether the pharmacy brand/link belongs
# on its page, and the launcher uses it to keep the two products from being
# cross-sold inside each other's demos.
PHARMACY_APP_IDS = ("pos", "inventory", "patients", "finance", "alerts")

# Phase 2 gate inputs. Blueprint -> app for the default case; endpoint
# overrides win over the blueprint default; ALWAYS_ON_BLUEPRINTS are never
# gated. Kept here so the whole ownership map is visible in one place.
BLUEPRINT_APPS = {
    "sales": "pos",
    "inventory": "inventory",
    "patients": "patients",
    "credit": "finance",
    "finance": "finance",
    "notifications": "alerts",
    "tender": "tender",
}
ENDPOINT_APPS = {
    "reporting.api_staff_activity": "finance",
}
ALWAYS_ON_BLUEPRINTS = frozenset(
    {"auth", "web", "admin", "customers", "reporting", "apps"}
)


def app_ids():
    """All app ids in display order."""
    return [a for a in sorted(APPS, key=lambda x: APPS[x]["order"])]


def gated_app_ids():
    """App ids that can be granted or revoked (always-on apps excluded)."""
    return [a for a in app_ids() if not APPS[a]["always_on"]]


def ordered_app_ids(ids):
    """Sort any iterable of app ids into display order."""
    return [a for a in app_ids() if a in set(ids)]


def get_app(app_id):
    return APPS.get(app_id)


def bundle_apps(bundle_id):
    """Apps contained in a bundle, or [] for an unknown bundle."""
    bundle = BUNDLES.get(bundle_id)
    return list(bundle["apps"]) if bundle else []


def bundle_label(bundle_id):
    bundle = BUNDLES.get(bundle_id)
    return bundle["label"] if bundle else "Custom"


def requires_of(app_id):
    """App ids that must be active before this app can be added."""
    return list(APPS.get(app_id, {}).get("requires", []))


def detect_bundle(active_ids):
    """Best-known bundle label for an active app set.

    Returns the largest bundle fully contained in ``active_ids`` (legacy wins
    for the grandfathered all-apps set, then growth over pro over core),
    ``"tender"`` for a Tender-only installation, ``"custom"`` for a partial
    mix, and ``"none"`` for an empty set.
    """
    active = set(active_ids)
    for bundle_id in ("legacy", "growth", "pro", "core", "tender"):
        if set(bundle_apps(bundle_id)) <= active:
            return bundle_id
    return "custom" if active else "none"
