"""Inventory services: FEFO stock deduction, stock levels, expiry watch."""
from datetime import date

from drugshop.core.utils import parse_date
from drugshop.db import q_all


def _deduct_fefo(db, product_id, qty):
    """Deduct qty FEFO inside an open transaction; return [(batch_id, taken)]."""
    batches = [dict(r) for r in db.execute("SELECT * FROM batches WHERE product_id=? AND qty_remaining>0 ORDER BY expiry_date ASC", (product_id,)).fetchall()]
    avail = sum(b["qty_remaining"] for b in batches)
    if avail < qty:
        raise ValueError(f"Insufficient stock. Available={avail}")
    allocations = []
    remaining = qty
    for b in batches:
        if remaining <= 0:
            break
        take = min(remaining, b["qty_remaining"])
        db.execute("UPDATE batches SET qty_remaining=qty_remaining-? WHERE id=?", (take, b["id"]))
        allocations.append((b["id"], take))
        remaining -= take
    return allocations


def deduct_fefo(db, product_id, qty):
    """Deduct qty FEFO inside an open transaction. Returns first batch id. Raises ValueError if short."""
    allocations = _deduct_fefo(db, product_id, qty)
    return allocations[0][0] if allocations else None


def deduct_fefo_allocations(db, product_id, qty):
    """Deduct qty FEFO and return every (batch_id, qty_taken) pair."""
    return _deduct_fefo(db, product_id, qty)


def expiry_status(expiry_date):
    try:
        d = parse_date(expiry_date)
    except (TypeError, ValueError):
        return "UNKNOWN"
    delta = (d - date.today()).days
    if delta < 0:
        return "EXPIRED"
    if delta <= 30:
        return "CRITICAL_30"
    if delta <= 60:
        return "WARNING_60"
    return "OK"


def stock_levels():
    rows = q_all("""
        SELECT p.*, COALESCE(SUM(b.qty_remaining),0) as stock_on_hand
        FROM products p LEFT JOIN batches b ON b.product_id=p.id
        GROUP BY p.id ORDER BY p.name
    """)
    for r in rows:
        r["low_stock"] = r["stock_on_hand"] <= (r["reorder_level"] or 10)
    return rows


def expiry_report():
    rows = q_all("""
        SELECT b.*, p.name as product_name, p.unit
        FROM batches b JOIN products p ON p.id=b.product_id
        WHERE b.qty_remaining > 0
        ORDER BY b.expiry_date ASC
    """)
    out = {"expired": [], "critical_30": [], "warning_60": [], "ok": []}
    for b in rows:
        st = expiry_status(b["expiry_date"])
        try:
            b["days_to_expiry"] = (parse_date(b["expiry_date"]) - date.today()).days
        except (TypeError, ValueError):
            b["days_to_expiry"] = None
        if st == "EXPIRED":
            out["expired"].append(b)
        elif st == "CRITICAL_30":
            out["critical_30"].append(b)
        elif st == "WARNING_60":
            out["warning_60"].append(b)
        else:
            out["ok"].append(b)
    return out
