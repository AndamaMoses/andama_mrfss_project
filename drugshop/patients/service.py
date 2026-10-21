"""Patients services: Day-25 refill reminder states and WhatsApp links."""
from datetime import date, timedelta

from drugshop.core.utils import parse_date
from drugshop.db import q_all


def refill_due():
    pats = q_all("SELECT pt.*, p.name as drug_name FROM patients pt LEFT JOIN products p ON p.id=pt.product_id ORDER BY pt.last_refill_date")
    due, upcoming, ok = [], [], []
    for p in pats:
        try:
            last = parse_date(p["last_refill_date"])
        except (TypeError, ValueError):
            last = None
        if last is None:
            continue
        cycle = p.get("cycle_days") or 30
        next_due = last + timedelta(days=cycle)
        remind = last + timedelta(days=cycle - 5)  # Day 25 of 30
        days_left = (next_due - date.today()).days
        p["next_due"] = next_due.isoformat()
        p["remind_from"] = remind.isoformat()
        p["days_left"] = days_left
        # WhatsApp click-to-chat link (no API cost)
        phone = "".join(c for c in (p["phone"] or "") if c.isdigit())
        if phone.startswith("0"):
            phone = "256" + phone[1:]
        msg = f"Hello {p['name']}, this is Onzima Charles Drug Shop (Kireka). Your {p.get('drug_name') or 'medication'} refill is due on {next_due.isoformat()} ({days_left} days left). Reply to confirm pickup. Thank you!"
        from urllib.parse import quote
        p["whatsapp_link"] = f"https://wa.me/{phone}?text={quote(msg)}" if phone else ""
        if days_left < 0:
            p["state"] = "OVERDUE"
            due.append(p)
        elif date.today() >= remind:
            p["state"] = "DUE_SOON"
            due.append(p)
        elif days_left <= 10:
            p["state"] = "UPCOMING"
            upcoming.append(p)
        else:
            p["state"] = "OK"
            ok.append(p)
    return {"due": due, "upcoming": upcoming, "ok": ok}
