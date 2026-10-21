"""Collect pilot metrics without changing the database.

Reads the live SQLite database in read-only mode and optionally parses the
server log for entitlement denials. Use this during the Onzima pilot to fill
in ``docs/pilot-tracker.md``.

Examples:
    python scripts/pilot_metrics.py
    python scripts/pilot_metrics.py --log instance/pilot/server.log
    python scripts/pilot_metrics.py --since 2026-10-21 --json
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSINESS_TABLES = (
    "users",
    "products",
    "batches",
    "sales",
    "patients",
    "tender_docs",
)
DENIAL_RE = re.compile(r"app access denied endpoint=(\S+) app=(\S+)")
HTTP_403_RE = re.compile(
    r'"(?:GET|POST|PUT|PATCH|DELETE) (\S+) HTTP/[^"]+"\s+403\b'
)


def default_source():
    instance = PROJECT_ROOT / "instance" / "drugshop.db"
    legacy = PROJECT_ROOT / "drugshop.db"
    return instance if instance.exists() else legacy


def connect_readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def table_exists(conn, name):
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def parse_denials(text):
    app_counts = Counter()
    endpoint_counts = Counter()
    http_counts = Counter()
    for line in text.splitlines():
        match = DENIAL_RE.search(line)
        if match:
            endpoint, app_id = match.groups()
            app_counts[app_id] += 1
            endpoint_counts[endpoint] += 1
            continue
        match = HTTP_403_RE.search(line)
        if match:
            http_counts[match.group(1)] += 1
    return {
        "app_log_total": sum(app_counts.values()),
        "by_app": dict(app_counts.most_common()),
        "by_endpoint": dict(endpoint_counts.most_common()),
        "http_log_total": sum(http_counts.values()),
        "by_path": dict(http_counts.most_common()),
    }


def collect(db_path, log_path=None, since=None):
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "database": str(db_path),
        "log": str(log_path) if log_path else None,
        "since": since,
    }
    conn = connect_readonly(db_path)
    try:
        if table_exists(conn, "app_entitlements"):
            rows = conn.execute(
                "SELECT app_id, bundle, expires_at, activated_at "
                "FROM app_entitlements WHERE status='active' ORDER BY app_id"
            ).fetchall()
            result["plan"] = {
                "active_apps": [row[0] for row in rows],
                "bundles": sorted({row[1] for row in rows}),
                "expires_at": sorted({row[2] for row in rows if row[2]}),
                "activated_at": min((row[3] for row in rows), default=None),
            }
        else:
            result["plan"] = {
                "active_apps": [],
                "bundles": ["unseeded"],
                "expires_at": [],
                "activated_at": None,
            }

        if table_exists(conn, "entitlement_events"):
            result["first_entitlement_event"] = scalar(
                conn,
                "SELECT MIN(created_at) FROM entitlement_events",
            )
            events_sql = (
                "SELECT created_at, action, app_id, actor, detail "
                "FROM entitlement_events"
            )
            params = ()
            if since:
                events_sql += " WHERE created_at >= ?"
                params = (since,)
            events_sql += " ORDER BY id DESC LIMIT 10"
            result["recent_entitlement_events"] = [
                {
                    "created_at": row[0],
                    "action": row[1],
                    "app_id": row[2],
                    "actor": row[3],
                    "detail": row[4],
                }
                for row in conn.execute(events_sql, params)
            ]
        else:
            result["first_entitlement_event"] = None
            result["recent_entitlement_events"] = []

        if table_exists(conn, "login_events"):
            login_sql = "SELECT COUNT(*), COUNT(DISTINCT username), MAX(login_at) FROM login_events"
            params = ()
            if since:
                login_sql += " WHERE login_at >= ?"
                params = (since,)
            total, users, last = conn.execute(login_sql, params).fetchone()
            result["logins"] = {
                "count": total,
                "distinct_users": users,
                "last_login_at": last,
            }
        else:
            result["logins"] = {"count": 0, "distinct_users": 0, "last_login_at": None}

        result["business_counts"] = {}
        for table in BUSINESS_TABLES:
            if table_exists(conn, table):
                result["business_counts"][table] = scalar(
                    conn,
                    f'SELECT COUNT(*) FROM "{table}"',  # noqa: S608
                )
        result["integrity"] = scalar(conn, "PRAGMA integrity_check")
    finally:
        conn.close()

    if log_path:
        if log_path.is_file():
            result["denials"] = parse_denials(
                log_path.read_text(encoding="utf-8", errors="replace")
            )
        else:
            result["denials"] = {"error": f"log not found: {log_path}"}
    else:
        result["denials"] = None
    return result


def print_report(data):
    plan = data["plan"]
    print(f"Pilot metrics — {data['generated_at']}")
    print(f"Database: {data['database']}")
    print(f"Integrity: {data['integrity']}")
    print(
        "Plan: "
        + (", ".join(plan["bundles"]) if plan["bundles"] else "none")
        + f" ({', '.join(plan['active_apps']) or 'no active apps'})"
    )
    print(f"First entitlement event: {data['first_entitlement_event'] or 'not recorded'}")
    if plan["expires_at"]:
        print(f"Expiry: {', '.join(plan['expires_at'])}")
    logins = data["logins"]
    print(
        "Logins: "
        f"{logins['count']} total, {logins['distinct_users']} distinct user(s), "
        f"last {logins['last_login_at'] or 'never'}"
    )
    counts = ", ".join(f"{key} {value}" for key, value in data["business_counts"].items())
    print(f"Business rows: {counts}")
    print("Entitlement changes (latest 10):")
    events = data["recent_entitlement_events"]
    if not events:
        print("  none")
    for event in events:
        print(
            f"  {event['created_at']}  {event['action']:<6} {event['app_id']:<10} "
            f"{event['actor']} {event['detail']}"
        )
    denials = data["denials"]
    if denials is None:
        print("403 denials: no log supplied (pass --log)")
    elif "error" in denials:
        print(f"403 denials: {denials['error']}")
    elif denials["app_log_total"]:
        print(f"403 denials: {denials['app_log_total']} (app log)")
        for app_id, count in denials["by_app"].items():
            print(f"  app {app_id}: {count}")
        for endpoint, count in denials["by_endpoint"].items():
            print(f"  endpoint {endpoint}: {count}")
    else:
        print(f"403 HTTP responses: {denials['http_log_total']} (request log)")
        for path, count in denials["by_path"].items():
            print(f"  {path}: {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="database path (read-only)")
    parser.add_argument("--log", default=None, help="server log to scan for 403s")
    parser.add_argument("--since", default=None, help="ISO date for DB counts")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    source = Path(args.db).resolve() if args.db else default_source().resolve()
    if not source.is_file():
        print(f"FAIL: database not found: {source}", file=sys.stderr)
        return 1
    since = date.fromisoformat(args.since).isoformat() if args.since else None
    log_path = Path(args.log).resolve() if args.log else None

    data = collect(source, log_path=log_path, since=since)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_report(data)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - CLI reports the failed metrics read
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
