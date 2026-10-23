"""Synthetic demo data for public preview deployments.

Enable with ``DEMO_SEED=1`` (see ``wsgi.py``). The seeder is a no-op when the
products table already has rows, so it cannot overwrite a real shop database by
accident. Every name, phone number, and amount here is invented for the demo.
"""
from datetime import date, timedelta

from drugshop.core.utils import normalize_ug_phone
from drugshop.db import get_db

# name, category, unit, reorder_level, price_buy, price_sell, batch, qty,
# expiry in days from today, supplier
DEMO_PRODUCTS = (
    ("Paracetamol 500mg", "Analgesics", "tabs", 50, 100, 200, "DM-1001", 400, 420, "Demo Wholesale Ltd"),
    ("Amoxicillin 250mg", "Antibiotics", "caps", 40, 250, 500, "DM-1002", 180, 25, "Demo Wholesale Ltd"),
    ("Metformin 500mg", "Diabetes care", "tabs", 30, 150, 300, "DM-1003", 220, 365, "Demo Wholesale Ltd"),
    ("Omeprazole 20mg", "Gastrointestinal", "caps", 30, 300, 600, "DM-1004", 80, -5, "Demo Wholesale Ltd"),
    ("Artemether-Lumefantrine 20/120", "Antimalarial", "tabs", 20, 1500, 2500, "DM-1005", 90, 20, "Demo Wholesale Ltd"),
    ("Cetirizine 10mg", "Antihistamine", "tabs", 25, 80, 200, "DM-1006", 12, 500, "Demo Wholesale Ltd"),
    ("ORS Sachets", "Rehydration", "sachets", 40, 500, 1000, "DM-1007", 60, 300, "Demo Wholesale Ltd"),
    ("Ibuprofen 400mg", "Analgesics", "tabs", 30, 120, 300, "DM-1008", 8, 18, "Demo Wholesale Ltd"),
    ("Amlodipine 5mg", "Hypertension", "tabs", 30, 200, 400, "DM-1009", 140, 240, "Demo Wholesale Ltd"),
    ("Vitamin C 100mg", "Supplements", "tabs", 20, 50, 150, "DM-1010", 200, 600, "Demo Wholesale Ltd"),
)

# name, phone, notes
DEMO_CUSTOMERS = (
    ("Demo Customer", "+256700000010", "Synthetic account for the public demo"),
    ("Demo Walk-in", "+256700000011", "Synthetic account for the public demo"),
)

# name, phone, product, days since last refill, cycle days, notes
DEMO_PATIENTS = (
    ("Demo Patient A", "+256700000001", "Metformin 500mg", 26, 30, "Synthetic refill record"),
    ("Demo Patient B", "+256700000002", "Amlodipine 5mg", 28, 30, "Synthetic refill record"),
    ("Demo Patient C", "+256700000003", "Omeprazole 20mg", 6, 30, "Synthetic refill record"),
)

# days ago, payment method, served by, customer name, customer phone, lines
DEMO_SALES = (
    (0, "CASH", "admin", "", "", (("Paracetamol 500mg", 2), ("ORS Sachets", 1))),
    (0, "MTN_MOMO", "grace", "", "", (("Artemether-Lumefantrine 20/120", 1), ("Amoxicillin 250mg", 2))),
    (0, "CREDIT", "admin", "Demo Customer", "+256700000010", (("Metformin 500mg", 3), ("Amlodipine 5mg", 1))),
    (1, "AIRTEL_MOMO", "grace", "", "", (("Cetirizine 10mg", 1), ("Vitamin C 100mg", 2))),
    (1, "CASH", "admin", "", "", (("Ibuprofen 400mg", 2),)),
)

# days ago, category, description, amount, paid by
DEMO_EXPENSES = (
    (0, "Transport", "Demo delivery run", 3000, "admin"),
    (1, "Utilities", "Demo water bill", 8000, "admin"),
)


def seed_demo():
    """Insert synthetic demo data once; return a summary of what happened."""
    db = get_db()
    try:
        if db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
            return {"seeded": False, "reason": "products already exist"}

        today = date.today()
        product_ids = {}
        batch_ids = {}
        prices = {}
        for row in DEMO_PRODUCTS:
            (name, category, unit, reorder, buy, sell, batch_no, qty, expiry_days, supplier) = row
            cur = db.execute(
                "INSERT INTO products(name,category,unit,reorder_level,price_buy,price_sell)"
                " VALUES(?,?,?,?,?,?)",
                (name, category, unit, reorder, buy, sell),
            )
            product_ids[name] = cur.lastrowid
            prices[name] = sell
            expiry = (today + timedelta(days=expiry_days)).isoformat()
            cur = db.execute(
                "INSERT INTO batches(product_id,batch_no,qty_received,qty_remaining,"
                "expiry_date,supplier,invoice_no) VALUES(?,?,?,?,?,?,?)",
                (cur.lastrowid, batch_no, qty, qty, expiry, supplier, "DEMO-INV"),
            )
            batch_ids[name] = cur.lastrowid

        for name, phone, notes in DEMO_CUSTOMERS:
            db.execute(
                "INSERT INTO customers(name,phone,phone_digits,notes) VALUES(?,?,?,?)",
                (name, phone, normalize_ug_phone(phone), notes),
            )

        for name, phone, product, days_ago, cycle, notes in DEMO_PATIENTS:
            last_refill = (today - timedelta(days=days_ago)).isoformat()
            db.execute(
                "INSERT INTO patients(name,phone,product_id,last_refill_date,cycle_days,notes)"
                " VALUES(?,?,?,?,?,?)",
                (name, phone, product_ids[product], last_refill, cycle, notes),
            )

        sequences = {}
        sales = 0
        for days_ago, method, served_by, customer, phone, lines in DEMO_SALES:
            day = (today - timedelta(days=days_ago)).isoformat()
            sequences[day] = sequences.get(day, 0) + 1
            ref = f"R-{day.replace('-', '')}-{sequences[day]:04d}"
            for product, qty in lines:
                batch_id = batch_ids[product]
                price = prices[product]
                taken = db.execute(
                    "UPDATE batches SET qty_remaining=qty_remaining-?"
                    " WHERE id=? AND qty_remaining>=?",
                    (qty, batch_id, qty),
                )
                if taken.rowcount != 1:
                    raise RuntimeError(f"demo stock too low for {product}")
                cur = db.execute(
                    "INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,"
                    "payment_method,served_by,receipt_ref,customer_name,created_at,"
                    "customer_phone) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (day, product_ids[product], batch_id, qty, price, price * qty,
                     method, served_by, ref, customer, f"{day} 10:00:00", phone),
                )
                db.execute(
                    "INSERT INTO sale_batches(sale_id,batch_id,qty) VALUES(?,?,?)",
                    (cur.lastrowid, batch_id, qty),
                )
                sales += 1

        for days_ago, category, description, amount, paid_by in DEMO_EXPENSES:
            exp_date = (today - timedelta(days=days_ago)).isoformat()
            db.execute(
                "INSERT INTO expenses(exp_date,category,description,amount,paid_by)"
                " VALUES(?,?,?,?,?)",
                (exp_date, category, description, amount, paid_by),
            )

        db.commit()
        return {
            "seeded": True,
            "products": len(DEMO_PRODUCTS),
            "sales": sales,
            "patients": len(DEMO_PATIENTS),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
