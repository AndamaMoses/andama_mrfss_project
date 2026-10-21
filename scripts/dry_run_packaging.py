"""Phase 5 packaging dry run.

Copies the real database to a temporary directory, applies the additive
migration, seeds a bundle, exercises the entitlement gate, downgrades to Core,
re-upgrades, and then rehearses a restore from the verified backup. The source
database and backup are never modified.

Usage:
    python scripts/dry_run_packaging.py --bundle legacy \
        --restore-backup instance/backups/drugshop-pre-packaging-20261021-161243.db

Stop the app before running this against a live database file. The script also
works against a copy, which is the safer option on a busy install.
"""
import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ("core", "pro", "growth", "tender", "legacy")
IGNORED_TABLES = {"schema_migrations", "app_entitlements", "entitlement_events"}


def default_source():
    instance = PROJECT_ROOT / "instance" / "drugshop.db"
    legacy = PROJECT_ROOT / "drugshop.db"
    return instance if instance.exists() else legacy


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_database(source, destination):
    """Make a consistent snapshot, including any WAL contents."""
    source_conn = sqlite3.connect(source)
    destination_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()


def snapshot(path):
    """Return integrity, row counts, and migration versions for one DB file."""
    conn = sqlite3.connect(path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {}
        for table in tables:
            counts[table] = conn.execute(
                f'SELECT COUNT(*) FROM "{table}"'  # noqa: S608
            ).fetchone()[0]
        versions = ()
        if "schema_migrations" in counts:
            versions = tuple(
                row[0]
                for row in conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            )
        return {"integrity": integrity, "counts": counts, "versions": versions}
    finally:
        conn.close()


def business_counts(snap):
    return {key: value for key, value in snap["counts"].items() if key not in IGNORED_TABLES}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def ok(message):
    print(f"[OK]   {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=None,
        help="database to copy (default: instance/drugshop.db if present, else drugshop.db)",
    )
    parser.add_argument(
        "--restore-backup",
        default=None,
        help="verified backup used for the restore rehearsal (default: --source)",
    )
    parser.add_argument(
        "--bundle",
        choices=BUNDLES,
        default="legacy",
        help="bundle to seed for this installation (default: legacy for Onzima)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the temporary working directory for inspection",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve() if args.source else default_source().resolve()
    restore = Path(args.restore_backup).resolve() if args.restore_backup else source
    require(source.is_file(), f"source database not found: {source}")
    require(restore.is_file(), f"restore backup not found: {restore}")

    source_hash = sha256(source)
    source_snap = snapshot(source)
    restore_snap = snapshot(restore)
    require(source_snap["integrity"] == "ok", f"source integrity failed: {source_snap['integrity']}")
    require(restore_snap["integrity"] == "ok", f"backup integrity failed: {restore_snap['integrity']}")
    ok(f"source opens cleanly: {source}")
    ok(f"restore backup opens cleanly: {restore}")
    if source_hash == sha256(restore):
        ok("restore backup is byte-identical to the source")
    else:
        print("[INFO] restore backup differs from the source; restore counts will be used")

    workdir = Path(tempfile.mkdtemp(prefix="drugshop-packaging-dryrun-"))
    work_db = workdir / "dryrun.db"
    work_uploads = workdir / "uploads"
    work_uploads.mkdir()
    copy_database(source, work_db)
    ok(f"copied source to {work_db}")

    # config.py reads these before the app package is imported.
    os.environ["DRUGSHOP_DB"] = str(work_db)
    os.environ["DRUGSHOP_UPLOADS"] = str(work_uploads)
    os.environ["DRUGSHOP_BUNDLE"] = args.bundle

    sys.path.insert(0, str(PROJECT_ROOT))
    from drugshop import create_app
    from drugshop import db as dbm
    from drugshop.apps import registry, service
    from drugshop.db import q_one

    app = create_app()
    applied = dbm.init_db()
    ok(f"init_db applied: {', '.join(applied) if applied else 'nothing (already current)'}")

    migrated = snapshot(work_db)
    require(migrated["integrity"] == "ok", f"migrated integrity failed: {migrated['integrity']}")
    require(
        business_counts(migrated) == business_counts(source_snap),
        "business table row counts changed during migration",
    )
    require("app_entitlements" in migrated["counts"], "app_entitlements table is missing")
    require("entitlement_events" in migrated["counts"], "entitlement_events table is missing")
    require(
        "002_app_entitlements.sql" in migrated["versions"],
        "002_app_entitlements.sql was not recorded",
    )
    ok(f"migration preserved {len(business_counts(source_snap))} existing table row counts")

    seeded = service.ensure_entitlements(args.bundle)
    if not seeded["seeded"]:
        service.set_bundle(args.bundle, actor="dry-run", notes="dry run seed")
    plan = service.current_plan()
    require(
        plan["bundle"] == args.bundle,
        f"seeded plan is {plan['bundle']}, expected {args.bundle}",
    )
    ok(f"seeded plan: {plan['label']} ({', '.join(plan['apps'])})")
    require(
        business_counts(snapshot(work_db)) == business_counts(source_snap),
        "business table row counts changed during entitlement seeding",
    )

    admin = q_one(
        "SELECT id, username FROM users WHERE role='admin' ORDER BY id LIMIT 1"
    ) or q_one("SELECT id, username FROM users WHERE username='admin'")
    require(admin is not None, "no admin user found in the copied database")

    client = app.test_client()

    def api_status(path):
        return client.get(path).status_code

    def check_matrix(label, bundle_id):
        active = set(registry.bundle_apps(bundle_id))
        require(api_status("/api/apps") == 200, f"{label}: /api/apps failed")
        payload = client.get("/api/apps").get_json()
        require(
            payload["plan"]["bundle"] == bundle_id,
            f"{label}: /api/apps reports {payload['plan']['bundle']}",
        )
        require(
            api_status("/api/products") == (200 if "inventory" in active else 403),
            f"{label}: /api/products access mismatch",
        )
        require(
            api_status("/api/patients") == (200 if "patients" in active else 403),
            f"{label}: /api/patients access mismatch",
        )
        tender_response = client.get("/tender")
        if "tender" in active:
            require(tender_response.status_code == 200, f"{label}: /tender did not render")
        else:
            require(tender_response.status_code == 302, f"{label}: /tender did not redirect")
            require(
                "upgrade=tender" in tender_response.headers.get("Location", ""),
                f"{label}: /tender redirect lost the upgrade target",
            )
        ok(f"{label}: access matrix matches {bundle_id}")

    with client.session_transaction() as session:
        session["uid"] = admin["id"]

    check_matrix(f"{args.bundle} seed", args.bundle)

    service.set_bundle("core", actor="dry-run", notes="downgrade rehearsal")
    require(
        business_counts(snapshot(work_db)) == business_counts(source_snap),
        "business table row counts changed during Core downgrade",
    )
    check_matrix("Core downgrade", "core")

    service.set_bundle(args.bundle, actor="dry-run", notes="upgrade rehearsal")
    require(
        business_counts(snapshot(work_db)) == business_counts(source_snap),
        "business table row counts changed during re-upgrade",
    )
    check_matrix("re-upgrade", args.bundle)

    # Restore rehearsal: stop using the app, replace the working copy with the
    # backup, and verify the pre-migration state is back exactly.
    shutil.copy2(restore, work_db)
    restored = snapshot(work_db)
    require(restored["integrity"] == "ok", f"restored integrity failed: {restored['integrity']}")
    require(
        restored["counts"] == restore_snap["counts"],
        "restored table row counts do not match the backup",
    )
    require(
        restored["versions"] == restore_snap["versions"],
        "restored migration versions do not match the backup",
    )
    if "app_entitlements" not in restore_snap["counts"]:
        require(
            "app_entitlements" not in restored["counts"],
            "backup restore left the new entitlement table behind",
        )
    ok("backup restore rehearsal matched the saved row counts and schema")

    require(sha256(source) == source_hash, "source database changed during the dry run")
    ok("source database hash unchanged")

    if args.keep:
        print(f"[INFO] temporary working directory kept: {workdir}")
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    print("PASS: packaging dry run clean")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - CLI reports the failed rehearsal step
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
