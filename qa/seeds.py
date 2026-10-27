"""Synthetic seed profiles for persona QA runs.

The profiles are deliberately explicit so a review is reproducible:

``fresh``         An empty installation, for first-run/activation tests.
``pharmacy_day``  The public demo dataset: products, batches, patients, sales.
``edge``          The demo plus overdue refills, zero stock, and near-expiry stock.
``tender``        A tender-only installation with one sample tender document.

Every profile is additive and idempotent; it never deletes business rows.
"""
import json
from datetime import date, timedelta

from drugshop.core.utils import normalize_ug_phone
from drugshop.db import execute, q_one
from drugshop.demo import seed_demo
from drugshop.tender.service import analyze_tender_text

PROFILES = ("fresh", "pharmacy_day", "edge", "tender")


def apply_seed(profile):
    """Apply a named seed profile and return a small summary."""
    if profile not in PROFILES:
        raise ValueError(f"unknown seed profile '{profile}' (choose: {', '.join(PROFILES)})")

    seeded = {"profile": profile, "demo": None, "extras": []}
    if profile == "fresh":
        return seeded

    if profile in ("pharmacy_day", "edge"):
        seeded["demo"] = seed_demo()

    if profile == "edge":
        seeded["extras"] = _seed_edge_cases()

    if profile == "tender":
        seeded["extras"] = _seed_tender_document()

    return seeded


def summary_counts():
    """Business row counts used in reports and seed output."""
    count_sql = {
        "users": "SELECT COUNT(*) AS n FROM users",
        "products": "SELECT COUNT(*) AS n FROM products",
        "batches": "SELECT COUNT(*) AS n FROM batches",
        "sales": "SELECT COUNT(*) AS n FROM sales",
        "patients": "SELECT COUNT(*) AS n FROM patients",
        "tender_docs": "SELECT COUNT(*) AS n FROM tender_docs",
    }
    counts = {}
    for table, sql in count_sql.items():
        row = q_one(sql)
        counts[table] = row["n"] if row else 0
    return counts


def _product(name, category, unit, reorder, buy, sell):
    existing = q_one("SELECT id FROM products WHERE name=?", (name,))
    if existing:
        return existing["id"]
    return execute(
        "INSERT INTO products(name,category,unit,reorder_level,price_buy,price_sell)"
        " VALUES(?,?,?,?,?,?)",
        (name, category, unit, reorder, buy, sell),
    )


def _batch(product_id, batch_no, qty, expiry_days, supplier="QA Wholesale", invoice_no="QA-INV"):
    existing = q_one(
        "SELECT id FROM batches WHERE product_id=? AND batch_no=?",
        (product_id, batch_no),
    )
    if existing:
        return existing["id"]
    expiry = (date.today() + timedelta(days=expiry_days)).isoformat()
    return execute(
        "INSERT INTO batches(product_id,batch_no,qty_received,qty_remaining,"
        "expiry_date,supplier,invoice_no) VALUES(?,?,?,?,?,?,?)",
        (product_id, batch_no, qty, qty, expiry, supplier, invoice_no),
    )


def _patient(name, phone, product_name, days_since_refill, cycle_days, notes):
    existing = q_one("SELECT id FROM patients WHERE name=? AND phone=?", (name, phone))
    if existing:
        return existing["id"]
    product = q_one("SELECT id FROM products WHERE name=?", (product_name,))
    last_refill = (date.today() - timedelta(days=days_since_refill)).isoformat()
    return execute(
        "INSERT INTO patients(name,phone,product_id,last_refill_date,cycle_days,notes)"
        " VALUES(?,?,?,?,?,?)",
        (name, phone, product["id"] if product else None, last_refill, cycle_days, notes),
    )


def _customer(name, phone, notes):
    existing = q_one("SELECT id FROM customers WHERE name=? AND phone=?", (name, phone))
    if existing:
        return existing["id"]
    return execute(
        "INSERT INTO customers(name,phone,phone_digits,notes) VALUES(?,?,?,?)",
        (name, phone, normalize_ug_phone(phone), notes),
    )


def _seed_edge_cases():
    """Add the messy states a real shop sees after a few weeks."""
    extras = []

    cough = _product(
        "Cough Syrup Extra Strength 200ml (Alcohol-Free)",
        "Respiratory",
        "bottles",
        5,
        12000,
        18500,
    )
    _batch(cough, "EDGE-2001", 3, 10, supplier="Nakasero Wholesale", invoice_no="EDGE-INV-1")
    extras.append("near-expiry cough syrup (3 bottles, 10 days)")

    cotrim = _product("Cotrimoxazole 480mg", "Antibiotics", "tabs", 20, 150, 300)
    _batch(cotrim, "EDGE-2002", 0, 45, supplier="QA Wholesale", invoice_no="EDGE-INV-2")
    extras.append("zero-stock Cotrimoxazole")

    amox = q_one("SELECT id FROM products WHERE name='Amoxicillin 250mg'")
    if amox:
        _batch(amox["id"], "EDGE-2003", 5, 15, supplier="QA Wholesale", invoice_no="EDGE-INV-3")
        extras.append("second Amoxicillin batch for FEFO testing")

    _patient(
        "Nakato Esther Namubiru Kintu",
        "+256772345678",
        "Metformin 500mg",
        40,
        30,
        "Overdue refill; long-name edge case",
    )
    extras.append("overdue refill patient")

    _customer("John Kintu", "+256772345678", "Credit customer for ledger tests")
    extras.append("credit customer")

    return extras


def _seed_tender_document():
    existing = q_one("SELECT id FROM tender_docs LIMIT 1")
    if existing:
        return ["tender document already present"]

    text = (
        "Uganda National Roads Authority (UNRA) — Periodic Maintenance Roadworks, "
        "Jinja District. The Employer invites sealed bids under the PPDA Act. "
        "Requirements: valid PPDA registration certificate, trading licence, "
        "tax clearance certificate from URA, NSSF clearance, bid security of UGX "
        "20,000,000, power of attorney, specific experience with completion "
        "certificates for similar works, equipment schedule with logbooks, key "
        "personnel CVs and engineer registration, audited accounts for three "
        "years, work programme and methodology, site visit certificate, "
        "performance security terms, and a declaration of non-blacklisting. "
        "Submission deadline: 14 November 2026 at 11:00 EAT. "
        "The scope includes gravel re-grading, drainage works, and culvert repairs."
    )
    matrix, risks, score = analyze_tender_text(text)
    execute(
        "INSERT INTO tender_docs(filename,text_len,text_excerpt,compliance_json,"
        "risks_json,score) VALUES(?,?,?,?,?,?)",
        (
            "sample-unra-roadworks.txt",
            len(text),
            text[:800],
            json.dumps(matrix),
            json.dumps(risks),
            score,
        ),
    )
    return [f"sample UNRA tender document (score {score})"]
