"""Read-only revenue rollup across one or more installation databases.

Examples:
    python scripts/revenue_rollup.py instance/drugshop.db --format json
    python scripts/revenue_rollup.py instance --format csv
    python scripts/revenue_rollup.py a.db b.db --format json --days 14

Directories are scanned for direct ``*.db`` files only, so a backups folder is
not counted twice unless it is passed explicitly. Every source is opened with
SQLite ``mode=ro`` and ``PRAGMA query_only`` inside one read transaction, so a
report sees a single consistent snapshot. The script hashes each file before
and after the read and fails if a byte changed. For a guaranteed point-in-time
file, stop the shop app or report against a copied database.
"""
import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from drugshop.billing import report as report_service  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover(arguments):
    """Expand files and directories into a de-duplicated list of databases."""
    paths = []
    seen = set()
    for raw in arguments:
        path = Path(raw).resolve()
        if path.is_dir():
            found = sorted(item for item in path.glob("*.db") if item.is_file())
            if not found:
                raise ValueError(f"no .db files found in directory: {path}")
        elif path.is_file():
            found = [path]
        else:
            raise ValueError(f"source not found: {path}")
        for item in found:
            if item not in seen:
                seen.add(item)
                paths.append(item)
    return paths


def load_report(path, renewal_days, as_of):
    before = sha256(path)
    conn = report_service.connect_readonly(path)
    try:
        data = report_service.build_report(
            conn,
            source=str(path),
            renewal_days=renewal_days,
            as_of=as_of,
        )
    finally:
        conn.close()
    after = sha256(path)
    if before != after:
        raise RuntimeError(f"source database changed during read: {path}")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        nargs="+",
        help="one or more database paths, or a directory of *.db files",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="output format (default: json)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="renewal window in days (default: 14)",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="ISO date used to evaluate renewals (default: today)",
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    paths = discover(args.sources)
    reports = [
        load_report(path, args.days, args.as_of) for path in paths
    ]

    if args.format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(
            buffer,
            fieldnames=report_service.CSV_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(report_service.csv_rows(reports))
        sys.stdout.write(buffer.getvalue())
        return 0

    portfolio = report_service.aggregate(reports)
    print(json.dumps(portfolio, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - CLI reports the failed report read
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
