"""Customer directory services: auto-registration from sales."""
from drugshop.core.utils import normalize_ug_phone
from drugshop.db import execute, q_one


def upsert_customer(name, phone):
    """Auto-register a customer from a sale. Dedupes by phone digits, else by name."""
    name = (name or "").strip()
    phone = (phone or "").strip()
    if not name and not phone:
        return
    digits = normalize_ug_phone(phone) if phone else ""
    if digits:
        ex = q_one("SELECT * FROM customers WHERE phone_digits=?", (digits,))
        if ex:
            if name and not (ex.get("name") or ""):
                execute("UPDATE customers SET name=? WHERE id=?", (name, ex["id"]))
            elif phone and not (ex.get("phone") or ""):
                execute("UPDATE customers SET phone=? WHERE id=?", (phone, ex["id"]))
            return
        execute("INSERT INTO customers(name,phone,phone_digits) VALUES(?,?,?)", (name or phone, phone, digits))
    elif name:
        if not q_one("SELECT id FROM customers WHERE name=?", (name,)):
            execute("INSERT INTO customers(name) VALUES(?)", (name,))
