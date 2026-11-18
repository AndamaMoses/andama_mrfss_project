"""Phase 5 read-only portfolio rollup tests."""
import csv
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from drugshop.billing import report

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "revenue_rollup.py"

SCHEMA = """
CREATE TABLE billing_subscriptions (
    id INTEGER PRIMARY KEY,
    customer_name TEXT,
    bundle TEXT,
    status TEXT,
    currency TEXT,
    setup_fee REAL,
    monthly_fee REAL,
    started_on TEXT,
    current_period_start TEXT,
    current_period_end TEXT
);
CREATE TABLE billing_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    kind TEXT,
    issue_date TEXT,
    due_date TEXT,
    period_start TEXT,
    period_end TEXT,
    amount REAL,
    currency TEXT,
    status TEXT
);
CREATE TABLE billing_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER,
    paid_on TEXT,
    amount REAL,
    currency TEXT,
    method TEXT,
    reference TEXT,
    received_by TEXT
);
"""


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_db(
    path,
    *,
    customer,
    bundle,
    status,
    monthly_fee,
    period_end,
    invoices=(),
    currency="UGX",
):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO billing_subscriptions("
            "id, customer_name, bundle, status, currency, setup_fee, "
            "monthly_fee, started_on, current_period_start, current_period_end"
            ") VALUES (1, ?, ?, ?, ?, 600000, ?, '2026-11-05', ?, ?)",
            (customer, bundle, status, currency, monthly_fee, period_end, period_end),
        )
        for invoice in invoices:
            cursor = conn.execute(
                "INSERT INTO billing_invoices("
                "invoice_no, kind, issue_date, due_date, period_start, "
                "period_end, amount, currency, status"
                ") VALUES (?, ?, '2026-11-12', '2026-11-12', NULL, NULL, ?, "
                "?, ?)",
                (
                    invoice["invoice_no"],
                    invoice["kind"],
                    invoice["amount"],
                    currency,
                    invoice["status"],
                ),
            )
            for payment in invoice.get("payments", ()):
                conn.execute(
                    "INSERT INTO billing_payments("
                    "invoice_id, paid_on, amount, currency, method, reference, "
                    "received_by"
                    ") VALUES (?, '2026-11-12', ?, ?, ?, ?, 'Andama')",
                    (
                        cursor.lastrowid,
                        payment["amount"],
                        currency,
                        payment["method"],
                        payment.get("reference", ""),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def _run(args):
    return subprocess.run(  # noqa: S603 - fixed script with test-generated paths
        [sys.executable, str(SCRIPT), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture()
def two_databases(tmp_path):
    pro = tmp_path / "pro-shop.db"
    legacy = tmp_path / "legacy-shop.db"
    _make_db(
        pro,
        customer="Pro Pharmacy",
        bundle="pro",
        status="active",
        monthly_fee=180_000,
        period_end="2026-11-21",
        invoices=(
            {
                "invoice_no": "INV-202611-0001",
                "kind": "setup",
                "amount": 600_000,
                "status": "partial",
                "payments": (
                    {"amount": 100_000, "method": "cash", "reference": "RC-1"},
                ),
            },
        ),
    )
    _make_db(
        legacy,
        customer="Onzima Pharmacy",
        bundle="legacy",
        status="grandfathered",
        monthly_fee=0,
        period_end=None,
    )
    return pro, legacy


def test_rollup_totals_equal_the_sum_of_installations(two_databases):
    pro, legacy = two_databases
    hashes = {pro: sha256(pro), legacy: sha256(legacy)}

    result = _run(
        [
            str(pro),
            str(legacy),
            "--format",
            "json",
            "--as-of",
            "2026-11-18",
        ]
    )

    assert result.returncode == 0, result.stderr
    portfolio = json.loads(result.stdout)
    totals = portfolio["totals"]
    assert portfolio["as_of"] == "2026-11-18"
    assert portfolio["currency"] == "UGX"
    assert totals["installations"] == 2
    assert totals["paying_installations"] == 1
    assert totals["mrr"] == 180_000
    assert totals["setup_invoiced"] == 600_000
    assert totals["monthly_invoiced"] == 0
    assert totals["total_invoiced"] == 600_000
    assert totals["setup_collected"] == 100_000
    assert totals["payments_collected"] == 100_000
    assert totals["outstanding_balance"] == 500_000
    assert totals["invoice_count"] == 1
    assert totals["renewal_due_count"] == 1
    assert totals["grandfathered_count"] == 1
    assert totals["excluded_count"] == 0

    installations = portfolio["installations"]
    for key in (
        "mrr",
        "setup_invoiced",
        "monthly_invoiced",
        "total_invoiced",
        "setup_collected",
        "payments_collected",
        "outstanding_balance",
        "invoice_count",
        "renewal_due_count",
    ):
        assert sum(item[key] for item in installations) == totals[key], key

    assert {item["plan"]["bundle"] for item in installations} == {"pro", "legacy"}
    assert {item["bundle"] for item in portfolio["plan_mix"]} == {"pro", "legacy"}
    assert portfolio["renewals_due"][0]["source"] == str(pro)
    assert portfolio["grandfathered"][0]["source"] == str(legacy)
    assert hashes == {pro: sha256(pro), legacy: sha256(legacy)}


def test_rollup_scans_a_directory_and_emits_csv(two_databases, tmp_path):
    pro, legacy = two_databases
    folder = tmp_path / "portfolio"
    folder.mkdir()
    pro.rename(folder / pro.name)
    legacy.rename(folder / legacy.name)
    (folder / "notes.txt").write_text("not a database", encoding="utf-8")

    result = _run(
        [str(folder), "--format", "csv", "--as-of", "2026-11-18"]
    )

    assert result.returncode == 0, result.stderr
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert rows[0] == list(report.CSV_COLUMNS)
    assert len(rows) == 3
    by_customer = {row[1]: row for row in rows[1:]}
    assert by_customer["Pro Pharmacy"][7] == "180000"
    assert by_customer["Onzima Pharmacy"][7] == "0"
    assert by_customer["Pro Pharmacy"][13] == "500000"


def test_rollup_handles_a_database_without_billing_tables(tmp_path):
    empty = tmp_path / "pre-billing.db"
    sqlite3.connect(empty).close()

    result = _run([str(empty), "--format", "json", "--as-of", "2026-11-18"])

    assert result.returncode == 0, result.stderr
    portfolio = json.loads(result.stdout)
    assert portfolio["totals"]["installations"] == 1
    assert portfolio["totals"]["mrr"] == 0
    assert portfolio["totals"]["excluded_count"] == 1
    assert portfolio["excluded"][0]["reason"] == "billing tables not initialized"


def test_rollup_rejects_a_missing_source(tmp_path):
    result = _run([str(tmp_path / "missing.db")])

    assert result.returncode == 1
    assert "source not found" in result.stderr


def test_rollup_refuses_to_sum_mixed_currencies(tmp_path):
    ugx = tmp_path / "ugx.db"
    usd = tmp_path / "usd.db"
    _make_db(
        ugx,
        customer="UGX Pharmacy",
        bundle="pro",
        status="active",
        monthly_fee=180_000,
        period_end="2026-11-21",
    )
    _make_db(
        usd,
        customer="USD Pharmacy",
        bundle="pro",
        status="active",
        monthly_fee=50,
        period_end="2026-11-21",
        currency="USD",
    )

    result = _run([str(ugx), str(usd), "--format", "json"])

    assert result.returncode == 1
    assert "mixes currencies" in result.stderr


def test_rollup_fails_cleanly_on_a_non_database(tmp_path):
    bad = tmp_path / "not-a-database.db"
    bad.write_text("not sqlite", encoding="utf-8")

    result = _run([str(bad), "--format", "json"])

    assert result.returncode == 1
    assert "FAIL:" in result.stderr


def test_readonly_connection_refuses_writes(tmp_path):
    path = tmp_path / "readonly.db"
    _make_db(
        path,
        customer="Example",
        bundle="pro",
        status="active",
        monthly_fee=180_000,
        period_end="2027-11-05",
    )

    conn = report.connect_readonly(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM billing_invoices")
    finally:
        conn.close()
