"""Create a scratch QA database with a named seed profile.

Examples:
    python scripts/qa_seed.py --profile pharmacy_day --plan pro
    python scripts/qa_seed.py --profile fresh --plan core --db instance/qa/first-run/drugshop.db

Never point this at the live pilot database. The harness refuses the two known
live paths and any directory outside ``instance/qa`` or the system temp dir.
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from drugshop.apps.service import current_plan  # noqa: E402
from qa.harness import assert_scratch_path, build_scratch_app  # noqa: E402
from qa.seeds import PROFILES, summary_counts  # noqa: E402


def _reset_database(db_path):
    for suffix in ("", "-journal", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="pharmacy_day")
    parser.add_argument("--plan", default="pro", choices=("core", "pro", "growth", "tender", "legacy"))
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "instance" / "qa" / "manual" / "drugshop.db"),
        help="scratch database path (default: instance/qa/manual/drugshop.db)",
    )
    parser.add_argument("--uploads", default=None, help="scratch upload directory")
    parser.add_argument("--force", action="store_true", help="delete the existing scratch database first")
    args = parser.parse_args(argv)

    db_path = assert_scratch_path(args.db)
    if args.force:
        _reset_database(db_path)
    elif db_path.exists():
        print(f"Reusing existing scratch database: {db_path}")
        print("Pass --force for a clean seed.")

    upload_dir = Path(args.uploads) if args.uploads else db_path.parent / "uploads"
    app = build_scratch_app(db_path, upload_dir, plan=args.plan, profile=args.profile)
    with app.app_context():
        plan = current_plan()
        counts = summary_counts()

    print(f"Scratch database: {db_path}")
    print(f"Plan: {plan['label']} ({plan['bundle']})")
    print(f"Profile: {args.profile}")
    print("Rows: " + ", ".join(f"{table}={count}" for table, count in counts.items()))
    print("Login: admin / qa-admin-pass (scratch only) or grace / qa-staff-pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
