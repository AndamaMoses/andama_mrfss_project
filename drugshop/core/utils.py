"""Shared utilities: dates, phone normalization, upload filenames."""
import os
import re
from datetime import date, datetime


def today_str():
    return date.today().isoformat()


def safe_upload_name(name):
    """Return a flat, filesystem-safe filename (no path separators or markup).

    The extension is preserved so ``.pdf`` detection still works. Callers
    prefix a timestamp when saving, which also neutralizes reserved names.
    """
    base = os.path.basename((name or "").replace("\\", "/")).replace(" ", "_")
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return base if base not in ("", ".", "..") else "upload"


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def normalize_ug_phone(p):
    digits = "".join(c for c in (p or "") if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "256" + digits[1:]
    elif digits.startswith("256") and len(digits) == 12:
        pass
    return digits
