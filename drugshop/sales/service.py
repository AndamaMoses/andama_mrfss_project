"""Sales services: receipt reference sequence and daily summary."""
from drugshop.db import q_all, q_one


def next_receipt_ref(day):
    n = q_one("SELECT COUNT(DISTINCT receipt_ref) c FROM sales WHERE sale_date=?", (day,))
    seq = (n["c"] if n else 0) + 1
    return f"R-{day.replace('-', '')}-{seq:04d}"


def sales_summary(day):
    rows = q_all("SELECT payment_method, COALESCE(SUM(total),0) as total, COUNT(*) as n FROM sales WHERE sale_date=? GROUP BY payment_method", (day,))
    m = {"CASH": 0, "MTN_MOMO": 0, "AIRTEL_MOMO": 0, "CREDIT": 0}
    for r in rows:
        m[r["payment_method"]] = r["total"]
    tot = q_one("SELECT COALESCE(SUM(total),0) as t, COUNT(*) as n FROM sales WHERE sale_date=?", (day,))
    return {"by_method": m, "total": tot["t"] if tot else 0, "count": tot["n"] if tot else 0}
