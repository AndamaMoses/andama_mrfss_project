"""Shop settings: defaults plus the DB-backed key/value store."""
from drugshop.db import q_one

SHOP_DEFAULTS = {
    "shop_name": "Onzima Charles Drug Shop",
    "shop_branch": "Kireka",
    "shop_phone": "+256 700 000000",
    "receipt_footer": "Thank you for shopping with us! No return of drugs without receipt.",
    "sms_sender": "",  # Africa's Talking sender ID / short code
    "manager_phone": "",  # where low-stock alerts go, e.g. 077xxxxxxx
}


def get_setting(key):
    row = q_one("SELECT value FROM settings WHERE key=?", (key,))
    if row and row.get("value"):
        return row["value"]
    return SHOP_DEFAULTS.get(key, "")
