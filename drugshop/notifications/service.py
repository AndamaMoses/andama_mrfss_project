"""Notifications services: SMS gateway and low-stock alert payloads."""
import os
import urllib.parse
import urllib.request

from drugshop.core.settings import get_setting
from drugshop.inventory.service import stock_levels


def send_sms_via_gateway(to_phone, message):
    """Try Africa's Talking SMS API if env creds exist, else simulate.
    Set env: AT_USERNAME, AT_API_KEY, AT_SENDER(optional). Returns (status, response)."""
    user = os.environ.get("AT_USERNAME", "")
    key = os.environ.get("AT_API_KEY", "")
    sender = os.environ.get("AT_SENDER", "") or get_setting("sms_sender")
    if not (user and key and to_phone):
        return ("SIMULATED", "No AT_API_KEY configured — logged only. Set AT_USERNAME/AT_API_KEY env to send real SMS.")
    try:
        data = urllib.parse.urlencode({"username": user, "to": "+" + to_phone, "message": message, **({"from": sender} if sender else {})}).encode()
        req = urllib.request.Request("https://api.africastalking.com/version1/messaging", data=data, headers={"apiKey": key, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
            return ("SENT", r.read().decode()[:500])
    except Exception as e:  # noqa: BLE001
        return ("FAILED", str(e)[:500])


def low_stock_items():
    items = [s for s in stock_levels() if s["low_stock"]]
    for it in items:
        it["suggested_order"] = max((it["reorder_level"] or 10) * 2 - it["stock_on_hand"], 0)
        it["sms_text"] = (f"LOW STOCK: {it['name']} — {it['stock_on_hand']} {it['unit']} left "
                          f"(reorder {it['reorder_level']}). Suggest order {it['suggested_order']}. - {get_setting('shop_name')}")
    return items
