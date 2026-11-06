"""Sales routes: POS sales, cart checkout, receipts, day-report.

Route bodies carried over from app.py (Phase 4.3); the fully admin-only void
view uses ``admin_required``. Receipt ref sequencing and cart total math are
unchanged. Sales record every FEFO allocation in ``sale_batches`` so a void
restores each touched batch, not just the first; ``deduct_fefo_allocations``
keeps all DB writes inside a single transaction per request.
"""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from drugshop.apps.service import is_entitled
from drugshop.auth.guards import admin_required, current_user
from drugshop.core.settings import get_setting
from drugshop.core.utils import today_str
from drugshop.customers.service import upsert_customer
from drugshop.db import get_db, q_all, q_one
from drugshop.inventory.service import deduct_fefo_allocations
from drugshop.payments import ledger, providers
from drugshop.payments.airtel import AirtelSettings
from drugshop.payments.errors import PaymentError
from drugshop.payments.momo import MomoSettings
from drugshop.payments.service import verify_reference, verify_sales_enabled
from drugshop.sales.service import next_receipt_ref, sales_summary

bp = Blueprint("sales", __name__)


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _sale_currency(provider):
    """Currency used for automated amount checks and the ledger row."""
    if provider == providers.AIRTEL:
        return AirtelSettings.from_mapping(current_app.config).currency
    return MomoSettings.from_mapping(current_app.config).currency


def _manual_currency(provider):
    """Currency for a manual till/SMS reference.

    MTN's sandbox defaults to EUR, but a manual payment is still a shop payment
    in the local currency. An explicit provider currency wins; otherwise UGX is
    the safe default for this Ugandan deployment.
    """
    if provider == providers.AIRTEL:
        return str(current_app.config.get("AIRTEL_CURRENCY") or "UGX").strip().upper()
    return str(current_app.config.get("MOMO_CURRENCY") or "UGX").strip().upper()


def _momo_guard(method, momo_ref, total, manual_entry=False):
    """Validate a mobile-money reference before stock is deducted.

    Returns ``(error_response, claim)``. ``claim`` is the metadata the sale
    transaction needs to perform the atomic anti-replay claim; verification is
    deliberately done here, outside the transaction, because it is a network
    call. The conditional ledger update later is what actually prevents two
    concurrent checkouts from using the same payment.
    """
    raw = str(momo_ref or "").strip()
    provider = providers.provider_for_method(method)
    if provider is None:
        if raw:
            return (
                jsonify(
                    {
                        "error": "momo_ref is only valid for MTN_MOMO or "
                        "AIRTEL_MOMO sales"
                    }
                ),
                400,
            ), None
        return None, None

    verify = verify_sales_enabled(provider)
    if not raw:
        if verify:
            return (
                jsonify(
                    {
                        "error": "A mobile-money reference is required when "
                        "verification is enabled"
                    }
                ),
                400,
            ), None
        # Rollout path: a monitored shop may record a mobile-money sale without
        # the gateway reference, exactly as it did before Phase 1.
        return None, None

    try:
        reference = ledger.canonical_reference(raw)
    except ValueError as exc:
        return (jsonify({"error": str(exc)}), 400), None

    row = ledger.get_collection(reference)
    if row:
        row_provider = str(row.get("provider") or providers.MTN).upper()
        if row_provider != provider:
            return (
                jsonify(
                    {
                        "error": "This mobile-money reference belongs to "
                        f"{providers.PROVIDER_LABELS.get(row_provider, row_provider)}, "
                        f"not {providers.PROVIDER_LABELS.get(provider, provider)}",
                        "provider": row_provider,
                    }
                ),
                409,
            ), None
        status = str(row["status"] or "").upper()
        if str(row["sale_receipt_ref"] or "").strip() or status in {
            "CONSUMED",
            "VOIDED",
        }:
            return (
                jsonify(
                    {
                        "error": "This MoMo reference is already on another sale",
                        "sale_id": row.get("sale_id"),
                        "receipt_ref": row.get("sale_receipt_ref", ""),
                        "momo_ref": row.get("reference", reference),
                    }
                ),
                409,
            ), None
        if status in ledger.TERMINAL_BAD_STATUSES:
            return (
                jsonify(
                    {
                        "error": f"MoMo payment is {status}; the sale was not "
                        "recorded"
                    }
                ),
                402,
            ), None
        if (
            manual_entry
            and str(row["source"] or "").upper() in {"API", "LEGACY"}
            and status != "SUCCESSFUL"
        ):
            return (
                jsonify(
                    {
                        "error": "This MoMo payment has not been confirmed; "
                        "request the prompt or use the verified reference path"
                    }
                ),
                402,
            ), None
    else:
        # A pre-ledger sale may already carry this reference. The transaction
        # claim repeats this check, but failing before stock work is cheaper.
        existing = q_one(
            """SELECT id, receipt_ref FROM sales
               WHERE TRIM(COALESCE(momo_ref,'')) <> ''
                 AND momo_ref=? COLLATE NOCASE LIMIT 1""",
            (reference,),
        )
        if existing:
            return (
                jsonify(
                    {
                        "error": "This MoMo reference is already on another sale",
                        "sale_id": existing["id"],
                        "receipt_ref": existing.get("receipt_ref", ""),
                        "momo_ref": reference,
                    }
                ),
                409,
            ), None

    if not manual_entry and verify:
        try:
            # Verify the reference the operator typed; the ledger canonicalises
            # it for lookup, but the gateway call should echo the original.
            # The MTN call keeps its historical two-argument shape so existing
            # fakes and integrations continue to work; Airtel names the rail.
            if provider == providers.AIRTEL:
                verify_reference(raw, total, provider=providers.PROVIDER_TO_METHOD[provider])
            else:
                verify_reference(raw, total)
        except PaymentError as exc:
            body = {"error": str(exc), "momo_ref": raw}
            if exc.paid_amount is not None:
                body["paid_amount"] = exc.paid_amount
                body["paid_currency"] = exc.paid_currency
            return (jsonify(body), exc.status), None

    if manual_entry:
        # If the counter is recording an existing API payment, keep that row's
        # currency so the claim can match it. A brand-new manual reference uses
        # the shop currency, not the provider's sandbox default.
        row_currency = str(row["currency"] or "").strip().upper() if row else ""
        claim_currency = row_currency or _manual_currency(provider)
    else:
        claim_currency = _sale_currency(provider)

    return None, {
        "reference": reference,
        "source": "MANUAL" if manual_entry else "API",
        "provider": provider,
        # With verification off, the payment may still be PENDING; the
        # monitored rollout path is allowed to consume it. Manual claims never
        # consume a pending API payment (enforced in claim_collection).
        "allow_pending": not verify,
        "currency": claim_currency,
    }


def _claim_momo(db, claim, receipt_ref, total, actor, phone):
    """Claim the reference inside the sale transaction and link the sale id."""
    if not claim:
        return None
    return ledger.claim_collection(
        db,
        claim["reference"],
        total,
        claim["currency"],
        receipt_ref,
        source=claim["source"],
        allow_pending=claim["allow_pending"],
        actor=actor,
        phone=phone,
        provider=claim.get("provider"),
    )


def _payment_error_response(exc, claim, momo_ref, db):
    """Return a payment error, including the existing receipt on a replay.

    A lost HTTP response can leave the counter thinking a sale was not saved
    when it actually committed. The duplicate response carries the original
    sale id/receipt so the client can stop retrying and print that receipt.
    """
    body = {
        "error": str(exc),
        "momo_ref": claim["reference"] if claim else momo_ref,
    }
    if exc.paid_amount is not None:
        body["paid_amount"] = exc.paid_amount
        body["paid_currency"] = exc.paid_currency
    if exc.status == 409 and claim:
        row = ledger.get_collection(claim["reference"], db=db)
        if row:
            body["momo_ref"] = row.get("reference", body["momo_ref"])
            body["sale_id"] = row.get("sale_id")
            body["receipt_ref"] = row.get("sale_receipt_ref", "")
        else:
            sale = db.execute(
                """SELECT id, receipt_ref FROM sales
                   WHERE TRIM(COALESCE(momo_ref,'')) <> ''
                     AND momo_ref=? COLLATE NOCASE LIMIT 1""",
                (claim["reference"],),
            ).fetchone()
            if sale:
                body["sale_id"] = sale["id"]
                body["receipt_ref"] = sale["receipt_ref"]
    return jsonify(body), exc.status


@bp.route("/api/sales/<int:sid>", methods=["DELETE"])
@admin_required
def api_sale_void(sid):
    """Void a sale: restore every FEFO allocation, drop credit payments. Admin only."""
    s = q_one("SELECT * FROM sales WHERE id=?", (sid,))
    if not s:
        return jsonify({"error": "sale not found"}), 404
    db = get_db()
    try:
        allocations = db.execute("SELECT batch_id, qty FROM sale_batches WHERE sale_id=?", (sid,)).fetchall()
        if allocations:
            for batch_id, qty in allocations:
                db.execute("UPDATE batches SET qty_remaining=qty_remaining+? WHERE id=?", (qty, batch_id))
        elif s.get("batch_id"):
            # Pre-allocation sales only recorded the first batch; keep old behavior.
            db.execute("UPDATE batches SET qty_remaining=qty_remaining+? WHERE id=?", (s["qty"], s["batch_id"]))
        db.execute("DELETE FROM sale_batches WHERE sale_id=?", (sid,))
        db.execute("DELETE FROM credit_payments WHERE sale_id=?", (sid,))
        db.execute("DELETE FROM sales WHERE id=?", (sid,))
        # The ledger row stays CONSUMED. A void restores stock, but it must
        # never free a payment reference for a second sale.
        if s.get("momo_ref"):
            me = current_user() or {}
            ledger.record_event(
                db,
                s["momo_ref"],
                "SALE_VOIDED",
                actor=me.get("username", ""),
                detail=f"sale={sid} receipt={s.get('receipt_ref', '')}",
            )
        db.commit()
    finally:
        db.close()
    return jsonify({"ok": True, "restored": s["qty"]})


# sales / POS
@bp.route("/api/sales", methods=["GET", "POST"])
def api_sales():
    if request.method == "GET":
        day = request.args.get("date", today_str())
        rows = q_all("""SELECT s.*, p.name as product_name FROM sales s
                        JOIN products p ON p.id=s.product_id WHERE sale_date=? ORDER BY s.id DESC""", (day,))
        return jsonify(rows)
    d = request.json or {}
    try:
        pid = int(d["product_id"])
        qty = int(d["qty"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return jsonify({"error": "product_id and qty required"}), 400
    if qty <= 0:
        return jsonify({"error": "qty must be positive"}), 400
    method = d.get("payment_method", "CASH")
    if method not in ("CASH", "MTN_MOMO", "AIRTEL_MOMO", "CREDIT"):
        return jsonify({"error": "bad payment_method"}), 400
    if method == "CREDIT" and not is_entitled("finance"):
        return jsonify({
            "error": "app not entitled",
            "app": "finance",
            "message": "Credit sales need the Finance app.",
            "upgrade": {"bundle": "pro"},
        }), 403
    if method == "CREDIT" and not (d.get("customer_name") or "").strip():
        return jsonify({"error": "customer name required for CREDIT sales"}), 400
    prod = q_one("SELECT * FROM products WHERE id=?", (pid,))
    if not prod:
        return jsonify({"error": "product not found"}), 404
    unit_price = float(d.get("unit_price") or prod["price_sell"] or 0)
    sale_date = d.get("sale_date") or today_str()
    total = unit_price * qty
    momo_ref = (d.get("momo_ref") or "").strip()
    manual_entry = _truthy(d.get("is_manual_entry"))
    guard, claim = _momo_guard(
        method, momo_ref, total, manual_entry=manual_entry
    )
    if guard:
        return guard
    actor = (current_user() or {}).get("username", "")
    phone = d.get("customer_phone", "")
    db = get_db()
    try:
        allocations = deduct_fefo_allocations(db, pid, qty)
        first_batch = allocations[0][0]
        ref = next_receipt_ref(sale_date)
        # Claim before inserting the sale: claim_collection's legacy fallback
        # must not see the row this transaction is about to create. A stock or
        # insert failure rolls the claim back with everything else.
        _claim_momo(db, claim, ref, total, actor, phone)
        cur = db.execute("INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,payment_method,served_by,receipt_ref,customer_name,customer_phone,momo_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (sale_date, pid, first_batch, qty, unit_price, total, method, d.get("served_by", ""), ref, d.get("customer_name", ""), phone, momo_ref))
        lid = cur.lastrowid
        for batch_id, taken in allocations:
            db.execute("INSERT INTO sale_batches(sale_id,batch_id,qty) VALUES(?,?,?)", (lid, batch_id, taken))
        if claim:
            ledger.attach_sale_id(db, claim["reference"], lid)
        db.commit()
    except PaymentError as e:
        db.rollback()
        return _payment_error_response(e, claim, momo_ref, db)
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    upsert_customer(d.get("customer_name", ""), d.get("customer_phone", ""))
    return jsonify({"id": lid, "receipt_ref": ref, "total": total, "momo_ref": momo_ref}), 201


@bp.route("/api/sales/cart", methods=["POST"])
def api_cart():
    """Multi-item basket -> one receipt. Body: {items:[{product_id,qty,unit_price?}], payment_method, served_by, sale_date, customer_name}"""
    d = request.json or {}
    items = d.get("items", [])
    if not items:
        return jsonify({"error": "basket is empty"}), 400
    method = d.get("payment_method", "CASH")
    if method not in ("CASH", "MTN_MOMO", "AIRTEL_MOMO", "CREDIT"):
        return jsonify({"error": "bad payment_method"}), 400
    if method == "CREDIT" and not is_entitled("finance"):
        return jsonify({
            "error": "app not entitled",
            "app": "finance",
            "message": "Credit sales need the Finance app.",
            "upgrade": {"bundle": "pro"},
        }), 403
    if method == "CREDIT" and not (d.get("customer_name") or "").strip():
        return jsonify({"error": "customer name required for CREDIT sales"}), 400
    sale_date = d.get("sale_date") or today_str()
    lines = []
    for it in items:
        try:
            pid, qty = int(it["product_id"]), int(it["qty"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return jsonify({"error": "each item needs product_id and qty"}), 400
        if qty <= 0:
            return jsonify({"error": "qty must be positive"}), 400
        prod = q_one("SELECT * FROM products WHERE id=?", (pid,))
        if not prod:
            return jsonify({"error": f"product {pid} not found"}), 404
        unit = float(it.get("unit_price") or prod["price_sell"] or 0)
        lines.append({"prod": prod, "qty": qty, "unit": unit})
    total = sum(ln["unit"] * ln["qty"] for ln in lines)
    momo_ref = (d.get("momo_ref") or "").strip()
    manual_entry = _truthy(d.get("is_manual_entry"))
    guard, claim = _momo_guard(
        method, momo_ref, total, manual_entry=manual_entry
    )
    if guard:
        return guard
    actor = (current_user() or {}).get("username", "")
    phone = d.get("customer_phone", "")
    db = get_db()
    try:
        ref = next_receipt_ref(sale_date)
        # Allocate every line first: the stock writes take SQLite's write lock
        # before the claim's read-check-update, so two concurrent carts
        # serialise instead of deadlocking on a read-then-write upgrade. A
        # stock failure rolls back before the reference is touched.
        planned = []
        for ln in lines:
            allocations = deduct_fefo_allocations(db, ln["prod"]["id"], ln["qty"])
            planned.append((ln, allocations))
        # Claim before inserting any sale row; claim_collection's legacy
        # fallback must not see the rows this transaction is about to create.
        _claim_momo(db, claim, ref, total, actor, phone)
        first_sale_id = None
        for ln, allocations in planned:
            first = allocations[0][0]
            t = ln["unit"] * ln["qty"]
            cur = db.execute("INSERT INTO sales(sale_date,product_id,batch_id,qty,unit_price,total,payment_method,served_by,receipt_ref,customer_name,customer_phone,momo_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (sale_date, ln["prod"]["id"], first, ln["qty"], ln["unit"], t, method, d.get("served_by", ""), ref, d.get("customer_name", ""), phone, momo_ref))
            if first_sale_id is None:
                first_sale_id = cur.lastrowid
            for batch_id, taken in allocations:
                db.execute("INSERT INTO sale_batches(sale_id,batch_id,qty) VALUES(?,?,?)", (cur.lastrowid, batch_id, taken))
        if claim:
            ledger.attach_sale_id(db, claim["reference"], first_sale_id)
        db.commit()
    except PaymentError as e:
        db.rollback()
        return _payment_error_response(e, claim, momo_ref, db)
    except ValueError as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    upsert_customer(d.get("customer_name", ""), d.get("customer_phone", ""))
    return jsonify({"receipt_ref": ref, "total": total, "lines": len(lines), "momo_ref": momo_ref}), 201


@bp.route("/api/receipts/<ref>")
def api_receipt_ref(ref):
    rows = q_all("""SELECT s.*, p.name as product_name, p.unit FROM sales s
                    JOIN products p ON p.id=s.product_id WHERE s.receipt_ref=? ORDER BY s.id""", (ref,))
    if not rows:
        return jsonify({"error": "receipt not found"}), 404
    return jsonify({
        "shop_name": get_setting("shop_name"),
        "shop_branch": get_setting("shop_branch"),
        "shop_phone": get_setting("shop_phone"),
        "receipt_no": ref,
        "footer": get_setting("receipt_footer"),
        "sale_date": rows[0]["sale_date"],
        "payment_method": rows[0]["payment_method"],
        "served_by": rows[0].get("served_by", ""),
        "customer_name": rows[0].get("customer_name", ""),
        "customer_phone": rows[0].get("customer_phone", ""),
        "momo_ref": rows[0].get("momo_ref", ""),
        "lines": rows,
        "total": sum(r["total"] for r in rows),
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


# ---------- receipts ----------
@bp.route("/api/sales/<int:sid>/receipt")
def api_receipt(sid):
    s = q_one("""SELECT s.*, p.name as product_name, p.unit FROM sales s
                 JOIN products p ON p.id=s.product_id WHERE s.id=?""", (sid,))
    if not s:
        return jsonify({"error": "sale not found"}), 404
    return jsonify({
        "shop_name": get_setting("shop_name"),
        "shop_branch": get_setting("shop_branch"),
        "shop_phone": get_setting("shop_phone"),
        "receipt_no": f"R-{sid:06d}",
        "footer": get_setting("receipt_footer"),
        "sale": s,
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


@bp.route("/api/sales/day-report")
def api_day_report():
    day = request.args.get("date", today_str())
    rows = q_all("""SELECT s.*, p.name as product_name FROM sales s
                    JOIN products p ON p.id=s.product_id WHERE sale_date=? ORDER BY s.id""", (day,))
    return jsonify({"date": day, "shop_name": get_setting("shop_name"),
                    "summary": sales_summary(day), "rows": rows})
