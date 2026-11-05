"""Sales services: receipt reference sequence and daily summary."""
from drugshop.db import q_all, q_one


def next_receipt_ref(day):
    n = q_one("SELECT COUNT(DISTINCT receipt_ref) c FROM sales WHERE sale_date=?", (day,))
    seq = (n["c"] if n else 0) + 1
    return f"R-{day.replace('-', '')}-{seq:04d}"


def sales_summary(day):
    """Daily totals. ``count`` is receipts, not line items.

    A multi-item basket writes one row per product but shares a single
    ``receipt_ref``. Counting rows made a 2-line basket look like two sales on
    the dashboard and the Z-report. Legacy rows without a receipt ref fall back
    to their own id so they are still counted once.
    """
    rows = q_all("SELECT payment_method, COALESCE(SUM(total),0) as total, COUNT(*) as n FROM sales WHERE sale_date=? GROUP BY payment_method", (day,))
    m = {"CASH": 0, "MTN_MOMO": 0, "AIRTEL_MOMO": 0, "CREDIT": 0}
    for r in rows:
        m[r["payment_method"]] = r["total"]
    tot = q_one(
        """SELECT COALESCE(SUM(total),0) as t,
                  COUNT(*) as line_count,
                  COUNT(DISTINCT CASE
                      WHEN receipt_ref IS NULL OR receipt_ref='' THEN 'sale-' || id
                      ELSE receipt_ref END) as receipts
           FROM sales WHERE sale_date=?""",
        (day,),
    )
    return {
        "by_method": m,
        "total": tot["t"] if tot else 0,
        "count": tot["receipts"] if tot else 0,
        "line_count": tot["line_count"] if tot else 0,
    }
