"""Entitlement service: plan reads, plan changes, seeding, and audit events.

Phase 1 of ``IMPLEMENTATION_PLAN_2.md``. Entitlements are stored per
installation (one deployment serves one shop); they gate access but never
install or delete code or business data. Removing an app only revokes access —
rows in the shop's tables are untouched.

Safety rule: an empty ``app_entitlements`` table means "not configured yet" and
is treated as *all apps entitled* (fail-open). Upgrading a live shop must never
lock it out of its own data. ``ensure_entitlements`` still seeds the configured
default bundle on first boot; fail-open only covers the window before that.
"""
import sqlite3
from datetime import date

from drugshop.apps.registry import (
    APPS,
    BUNDLES,
    app_ids,
    bundle_apps,
    bundle_label,
    detect_bundle,
    requires_of,
)
from drugshop.db import get_db, q_all

BOOTSTRAP_NOTE = "default bundle"


# ---------- reads ----------
def entitlement_rows():
    """Raw entitlement rows, ordered by app id (for the CLI plan view)."""
    return q_all("SELECT * FROM app_entitlements ORDER BY app_id")


def events(limit=20):
    """Most recent entitlement changes, newest first."""
    return q_all("SELECT * FROM entitlement_events ORDER BY id DESC LIMIT ?", (int(limit),))


def _active_ids(rows):
    return {r["app_id"] for r in rows if r["status"] == "active"}


def entitled_app_ids():
    """Active app ids for this installation.

    An empty table is fail-open (see module docstring) and returns every known
    app id so the Phase 2 gate cannot strand an unconfigured deployment.
    """
    rows = entitlement_rows()
    if not rows:
        return set(APPS)
    return _active_ids(rows)


def entitled_app_ids_or_all():
    """Fail-open app ids for page rendering before the migration has run.

    The request gate already fails open on a missing schema; pages that need
    plan metadata to choose a brand follow the same rule instead of returning
    a 500 on a fresh, not-yet-initialized deployment.
    """
    try:
        return entitled_app_ids()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc).lower():
            raise
        return set(APPS)


def is_entitled(app_id):
    app = APPS.get(app_id)
    if app and app["always_on"]:
        return True
    if app is None:
        return False
    return app_id in entitled_app_ids()


def current_plan():
    """Summary used by the CLI and, in Phase 2, by ``GET /api/apps``."""
    rows = entitlement_rows()
    bootstrap = not rows
    active = set(APPS) if bootstrap else _active_ids(rows)
    active = {a for a in active if a in APPS}
    bundle_id = "unseeded" if bootstrap else detect_bundle(active)
    expiries = sorted(
        r["expires_at"] for r in rows if r["status"] == "active" and r["expires_at"]
    )
    if bootstrap:
        label = "Unseeded"
    elif bundle_id in BUNDLES:
        label = bundle_label(bundle_id)
    else:
        label = bundle_id.title()
    return {
        "bundle": bundle_id,
        "label": label,
        "status": "active" if active else "inactive",
        "expires_at": expiries[-1] if expiries else None,
        "apps": sorted(active, key=lambda a: APPS[a]["order"]),
        "bootstrap": bootstrap,
    }


# ---------- validation ----------
def _validate_bundle(bundle_id):
    if bundle_id not in BUNDLES:
        raise ValueError(
            f"unknown bundle '{bundle_id}' (choose: {', '.join(BUNDLES)})"
        )


def _validate_app(app_id):
    if app_id not in APPS:
        raise ValueError(f"unknown app '{app_id}' (choose: {', '.join(app_ids())})")
    if APPS[app_id]["always_on"]:
        raise ValueError(f"'{app_id}' is always available and cannot be changed")


def _normalize_expires(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError("expires must be an ISO date (YYYY-MM-DD)") from exc


def _log(db, app_id, action, actor="", detail=""):
    db.execute(
        "INSERT INTO entitlement_events(app_id,action,actor,detail) VALUES(?,?,?,?)",
        (app_id, action, actor or "", detail or ""),
    )


def _note(notes, fallback):
    return notes.strip() if isinstance(notes, str) and notes.strip() else fallback


# ---------- writes ----------
def set_bundle(bundle_id, expires_at=None, actor="", notes="", source="cli"):
    """Replace the entitlement set with a bundle's apps.

    Apps already active with the same expiry are left untouched; missing apps
    are activated; apps outside the bundle are revoked (never deleted).
    """
    _validate_bundle(bundle_id)
    expires = _normalize_expires(expires_at)
    desired = set(bundle_apps(bundle_id))
    detail = f"bundle={bundle_id}"
    if notes:
        detail = f"{detail} - {notes}"

    db = get_db()
    added, changed, removed = [], [], []
    try:
        current = {r["app_id"]: dict(r) for r in db.execute(
            "SELECT * FROM app_entitlements").fetchall()}
        for app_id in sorted(desired, key=lambda a: APPS[a]["order"]):
            row = current.get(app_id)
            if row and row["status"] == "active" and (row["expires_at"] or None) == expires:
                continue
            if row:
                db.execute(
                    "UPDATE app_entitlements SET bundle=?, status='active',"
                    " expires_at=?, source=?, notes=? WHERE app_id=?",
                    (bundle_id, expires, source, _note(notes, ""), app_id),
                )
                changed.append(app_id)
                _log(db, app_id, "change", actor, detail)
            else:
                db.execute(
                    "INSERT INTO app_entitlements(app_id,bundle,status,expires_at,"
                    "source,notes) VALUES(?,?,'active',?,?,?)",
                    (app_id, bundle_id, expires, source, _note(notes, "")),
                )
                added.append(app_id)
                _log(db, app_id, "add", actor, detail)
        for app_id in sorted(current):
            row = current[app_id]
            if app_id not in desired and row["status"] == "active":
                db.execute(
                    "UPDATE app_entitlements SET status='revoked' WHERE app_id=?",
                    (app_id,),
                )
                removed.append(app_id)
                _log(db, app_id, "remove", actor, detail)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "ok": True,
        "bundle": bundle_id,
        "label": bundle_label(bundle_id),
        "added": added,
        "changed": changed,
        "removed": removed,
        "active": bundle_apps(bundle_id),
    }


def add_app(app_id, expires_at=None, actor="", notes="", source="manual"):
    """Activate a single app (an add-on). Refuses on an unseeded table so an
    operator cannot accidentally switch a fail-open installation to a
    one-app plan."""
    _validate_app(app_id)
    expires = _normalize_expires(expires_at)

    db = get_db()
    try:
        rows = [dict(r) for r in db.execute("SELECT * FROM app_entitlements").fetchall()]
        if not rows:
            raise ValueError("entitlements are not initialized; run `python run.py` once")
        active = _active_ids(rows)
        missing = [r for r in requires_of(app_id) if r not in active]
        if missing:
            raise ValueError(
                f"'{app_id}' requires {', '.join(missing)}; activate a bundle that "
                "includes them first"
            )
        row = next((r for r in rows if r["app_id"] == app_id), None)
        if row and row["status"] == "active" and (row["expires_at"] or None) == expires:
            return {"ok": True, "app": app_id, "note": "already active"}
        if row:
            db.execute(
                "UPDATE app_entitlements SET status='active', expires_at=?, source=?,"
                " notes=? WHERE app_id=?",
                (expires, source, _note(notes, ""), app_id),
            )
            action = "change"
        else:
            db.execute(
                "INSERT INTO app_entitlements(app_id,bundle,status,expires_at,source,"
                "notes) VALUES(?,?,'active',?,?,?)",
                (app_id, APPS[app_id]["bundle"], expires, source, _note(notes, "")),
            )
            action = "add"
        _log(db, app_id, action, actor, _note(notes, "manual add"))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()
    return {"ok": True, "app": app_id, "note": "activated"}


def remove_app(app_id, actor="", notes=""):
    """Revoke a single app. Refuses while another active app depends on it."""
    _validate_app(app_id)

    db = get_db()
    try:
        rows = [dict(r) for r in db.execute("SELECT * FROM app_entitlements").fetchall()]
        if not rows:
            raise ValueError("entitlements are not initialized; run `python run.py` once")
        active = _active_ids(rows)
        if app_id not in active:
            return {"ok": True, "app": app_id, "note": "not active"}
        dependents = sorted(
            (a for a in active if a != app_id and app_id in requires_of(a)),
            key=lambda a: APPS[a]["order"],
        )
        if dependents:
            raise ValueError(
                f"cannot remove '{app_id}': {', '.join(dependents)} depends on it"
            )
        db.execute("UPDATE app_entitlements SET status='revoked' WHERE app_id=?", (app_id,))
        _log(db, app_id, "remove", actor, _note(notes, "manual remove"))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()
    return {"ok": True, "app": app_id, "note": "revoked"}


def ensure_entitlements(default_bundle="pro"):
    """Seed the default bundle once, when the entitlement table is empty.

    Returns ``{"seeded": True, ...}`` after seeding and
    ``{"seeded": False, "count": N}`` when entitlements already exist.
    """
    bundle_id = default_bundle if default_bundle in BUNDLES else "pro"

    db = get_db()
    try:
        count = db.execute("SELECT COUNT(*) FROM app_entitlements").fetchone()[0]
        if count:
            return {"seeded": False, "count": count, "bundle": None, "apps": []}
        for app_id in sorted(bundle_apps(bundle_id), key=lambda a: APPS[a]["order"]):
            db.execute(
                "INSERT INTO app_entitlements(app_id,bundle,status,source,notes)"
                " VALUES(?,?,'active','bootstrap',?)",
                (app_id, bundle_id, BOOTSTRAP_NOTE),
            )
            _log(db, app_id, "seed", "system", f"bundle={bundle_id}")
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    finally:
        db.close()
    return {
        "seeded": True,
        "bundle": bundle_id,
        "label": bundle_label(bundle_id),
        "apps": bundle_apps(bundle_id),
    }
