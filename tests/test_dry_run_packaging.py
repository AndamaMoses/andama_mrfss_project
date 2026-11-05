"""Regression tests for the packaging dry-run row-count comparison."""
import importlib.util
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "dry_run_packaging.py"
)
_spec = importlib.util.spec_from_file_location("dry_run_packaging", SCRIPT)
dry_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dry_run)


def _snap(counts):
    return {"counts": counts}


def test_business_counts_drops_infrastructure_tables():
    snap = _snap({
        "products": 8,
        "sales": 12,
        "schema_migrations": 5,
        "app_entitlements": 6,
        "entitlement_events": 6,
    })

    assert dry_run.business_counts(snap) == {"products": 8, "sales": 12}


def test_new_migration_table_does_not_look_like_business_change():
    before = _snap({"products": 8, "sales": 12})
    after = _snap({
        "products": 8,
        "sales": 12,
        "payment_reconciliations": 0,
    })

    assert dry_run.business_counts(after) != dry_run.business_counts(before)
    assert dry_run.business_counts(after, before) == dry_run.business_counts(before)


def test_changed_existing_business_table_is_detected():
    before = _snap({"products": 8, "sales": 12})
    after = _snap({"products": 9, "sales": 12})

    assert dry_run.business_counts(after, before) != dry_run.business_counts(before)


def test_missing_baseline_table_is_detected():
    before = _snap({"products": 8, "sales": 12})
    after = _snap({"products": 8})

    assert dry_run.business_counts(after, before) != dry_run.business_counts(before)
