"""Payment-reference ledger and anti-replay claim.

The sales table alone cannot safely answer "has this MoMo payment been used?":
a basket writes several sale rows with the same reference, a void deletes the
row, and two concurrent checkouts can both pass a ``SELECT`` before either
``INSERT``. This module keeps one durable row per payment reference and makes
the sale claim a conditional ``UPDATE`` inside the sale transaction.

Statuses
--------
``PENDING``     request accepted by MTN (or awaiting a final status)
``SUCCESSFUL``  MTN reports the customer paid
``FAILED``      MTN rejected the request, or verification failed
``REJECTED``    customer declined
``TIMEOUT``     customer did not approve in time
``UNKNOWN``     network/5xx outcome; MTN may or may not have accepted it
``CONSUMED``    a sale has claimed this payment
``VOIDED``      reserved for an explicit admin release (not used automatically)

A consumed or voided reference is never freed by deleting a sale.
"""
from __future__ import annotations

import sqlite3
import uuid

from drugshop.db import get_db
from drugshop.payments import providers
from drugshop.payments.errors import PaymentError

MTN_STATUSES = frozenset(
    {"PENDING", "SUCCESSFUL", "FAILED", "REJECTED", "TIMEOUT", "UNKNOWN"}
)
PAYMENT_STATUSES = MTN_STATUSES  # provider-neutral alias
TERMINAL_BAD_STATUSES = frozenset({"FAILED", "REJECTED", "TIMEOUT"})
CLAIMABLE_STATUSES = frozenset({"PENDING", "SUCCESSFUL", "UNKNOWN"})


def canonical_reference(value):
    """Return the stable form used for ledger lookups.

    MTN reference ids are UUIDs; canonicalising them prevents the same payment
    being recorded again with different case, braces, or whitespace. Manual
    till/SMS references are upper-cased and matched case-insensitively.
    """
    text = str(value or "").strip()
    if not text:
        raise ValueError("MoMo reference is required")
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError, AttributeError):
        return text.upper()


def is_uuid(value):
    try:
        uuid.UUID(str(value or "").strip())
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def _as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _row_dict(row):
    return dict(row) if row is not None else None


def _provider_or_none(value):
    if value is None or not str(value).strip():
        return None
    return providers.normalize_provider(value)


def _check_provider(row, provider):
    """Reject using a reference through the wrong carrier's rail."""
    if row is None or not provider:
        return
    row_provider = str(row["provider"] or providers.MTN).upper()
    if row_provider == provider:
        return
    row_label = providers.PROVIDER_LABELS.get(row_provider, row_provider)
    wanted_label = providers.PROVIDER_LABELS.get(provider, provider)
    raise PaymentError(
        f"This mobile-money reference belongs to {row_label}, not {wanted_label}",
        status=409,
    )


def get_collection(reference, db=None):
    """Return the ledger row for ``reference``, or ``None``."""
    reference = canonical_reference(reference)
    own = db is None
    db = db or get_db()
    try:
        row = db.execute(
            "SELECT * FROM momo_collections WHERE reference=? COLLATE NOCASE",
            (reference,),
        ).fetchone()
        return _row_dict(row)
    finally:
        if own:
            db.close()


def get_by_idempotency(key, db=None):
    """Return the ledger row created for an idempotency key, or ``None``."""
    text = str(key or "").strip()
    if not text:
        return None
    own = db is None
    db = db or get_db()
    try:
        row = db.execute(
            "SELECT * FROM momo_collections WHERE idempotency_key=? COLLATE NOCASE",
            (text,),
        ).fetchone()
        return _row_dict(row)
    finally:
        if own:
            db.close()


def get_by_external_id(external_id, provider=None, db=None):
    """Return the most recent ledger row for a provider ``external_id``.

    External ids are chosen by the POS and are not globally unique across
    carriers, so callers should pass ``provider`` when they know it.
    """
    text = str(external_id or "").strip()
    if not text:
        return None
    wanted = _provider_or_none(provider)
    own = db is None
    db = db or get_db()
    try:
        if wanted:
            row = db.execute(
                """SELECT * FROM momo_collections
                   WHERE external_id=? AND provider=?
                   ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (text, wanted),
            ).fetchone()
        else:
            row = db.execute(
                """SELECT * FROM momo_collections
                   WHERE external_id=?
                   ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (text,),
            ).fetchone()
        return _row_dict(row)
    finally:
        if own:
            db.close()


def create_pending(
    reference,
    idempotency_key,
    amount,
    currency,
    phone="",
    external_id="",
    actor="",
    provider=providers.MTN,
):
    """Insert a pending collection before asking the gateway to push a prompt.

    Writing first is deliberate: if the provider accepts the request but the
    HTTP response is lost, the reference is still on disk and can be polled or
    reconciled instead of becoming an orphaned customer charge.
    """
    reference = canonical_reference(reference)
    provider = providers.normalize_provider(provider)
    key = str(idempotency_key or "").strip() or reference
    db = get_db()
    try:
        db.execute(
            """INSERT INTO momo_collections(
                   reference, idempotency_key, external_id, amount, currency,
                   phone, status, source, provider, created_at, updated_at)
               VALUES(?,?,?,?,?,?, 'PENDING', 'API', ?,
                      datetime('now','localtime'), datetime('now','localtime'))""",
            (
                reference,
                key,
                str(external_id or "").strip(),
                float(amount),
                str(currency or "").strip().upper(),
                str(phone or "").strip(),
                provider,
            ),
        )
        db.commit()
        return get_collection(reference, db=db)
    except sqlite3.IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()


def apply_status(reference, data, source="STATUS", actor="", provider=None):
    """Record the gateway's latest status without ever un-consuming a payment.

    ``provider`` is optional for backwards compatibility; when supplied, a
    reference owned by the other carrier is rejected with ``409`` instead of
    being updated with the wrong gateway's status.
    """
    reference = canonical_reference(reference)
    requested_provider = _provider_or_none(provider)
    data = data or {}
    status = str(data.get("status") or "").strip().upper()
    if status not in PAYMENT_STATUSES:
        status = ""
    mtn_amount = _as_float(data.get("amount"))
    mtn_currency = str(data.get("currency") or "").strip().upper()
    txn_id = str(
        data.get("financialTransactionId")
        or data.get("financial_transaction_id")
        or ""
    ).strip()

    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM momo_collections WHERE reference=? COLLATE NOCASE",
            (reference,),
        ).fetchone()
        _check_provider(dict(row) if row is not None else None, requested_provider)
        if row is None:
            db.execute(
                """INSERT OR IGNORE INTO momo_collections(
                       reference, idempotency_key, external_id, amount, currency,
                       phone, status, source, provider, mtn_status, mtn_amount,
                       mtn_currency, financial_txn_id, checked_at, created_at,
                       updated_at)
                   VALUES(?,?,?,?,?,?,?, 'LEGACY', ?, ?,?,?,?,
                          datetime('now','localtime'),
                          datetime('now','localtime'),
                          datetime('now','localtime'))""",
                (
                    reference,
                    f"legacy:{reference}",
                    str(data.get("externalId") or "").strip(),
                    mtn_amount if mtn_amount is not None else 0,
                    mtn_currency,
                    "",
                    status or "UNKNOWN",
                    requested_provider or providers.MTN,
                    status,
                    mtn_amount,
                    mtn_currency,
                    txn_id,
                ),
            )
        db.execute(
            """UPDATE momo_collections SET
                   status = CASE
                       WHEN status IN ('CONSUMED','VOIDED') THEN status
                       WHEN status='SUCCESSFUL' AND ? <> 'SUCCESSFUL' THEN status
                       WHEN status IN ('FAILED','REJECTED','TIMEOUT')
                            AND ? <> 'SUCCESSFUL' THEN status
                       WHEN ? <> '' THEN ?
                       ELSE status END,
                   mtn_status = CASE WHEN ? <> '' THEN ? ELSE mtn_status END,
                   mtn_amount = COALESCE(?, mtn_amount),
                   mtn_currency = CASE WHEN ? <> '' THEN ? ELSE mtn_currency END,
                   financial_txn_id = CASE WHEN ? <> '' THEN ? ELSE financial_txn_id END,
                   checked_at = datetime('now','localtime'),
                   updated_at = datetime('now','localtime')
               WHERE reference=? COLLATE NOCASE""",
            (
                status,
                status,
                status,
                status,
                status,
                status,
                mtn_amount,
                mtn_currency,
                mtn_currency,
                txn_id,
                txn_id,
                reference,
            ),
        )
        db.commit()
        return get_collection(reference, db=db)
    finally:
        db.close()


def mark_failed(reference, error, actor="", provider=None):
    """Record a definitive failure (the gateway rejected the request)."""
    reference = canonical_reference(reference)
    requested_provider = _provider_or_none(provider)
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM momo_collections WHERE reference=? COLLATE NOCASE",
            (reference,),
        ).fetchone()
        _check_provider(dict(row) if row is not None else None, requested_provider)
        db.execute(
            """UPDATE momo_collections SET
                   status = CASE WHEN status IN ('CONSUMED','VOIDED','SUCCESSFUL')
                                 THEN status ELSE 'FAILED' END,
                   last_error = ?,
                   checked_at = datetime('now','localtime'),
                   updated_at = datetime('now','localtime')
               WHERE reference=? COLLATE NOCASE""",
            (str(error or "")[:500], reference),
        )
        db.commit()
        record_event(db, reference, "FAILED", actor=actor, detail=str(error or "")[:500])
        db.commit()
        return get_collection(reference, db=db)
    finally:
        db.close()


def mark_unknown(reference, error, actor="", provider=None):
    """Record an ambiguous outcome: the gateway may still have accepted it."""
    reference = canonical_reference(reference)
    requested_provider = _provider_or_none(provider)
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM momo_collections WHERE reference=? COLLATE NOCASE",
            (reference,),
        ).fetchone()
        _check_provider(dict(row) if row is not None else None, requested_provider)
        db.execute(
            """UPDATE momo_collections SET
                   status = CASE WHEN status IN ('CONSUMED','VOIDED','SUCCESSFUL')
                                 THEN status ELSE 'UNKNOWN' END,
                   last_error = ?,
                   updated_at = datetime('now','localtime')
               WHERE reference=? COLLATE NOCASE""",
            (str(error or "")[:500], reference),
        )
        db.commit()
        record_event(
            db, reference, "UNKNOWN", actor=actor, detail=str(error or "")[:500]
        )
        db.commit()
        return get_collection(reference, db=db)
    finally:
        db.close()


def claim_collection(
    db,
    reference,
    amount,
    currency,
    receipt_ref,
    source="API",
    allow_pending=False,
    actor="",
    phone="",
    provider=None,
):
    """Atomically claim a reference for one receipt inside the sale transaction.

    The conditional ``UPDATE`` is the anti-replay lock: concurrent checkouts may
    both verify with the gateway, but only one can move the ledger row to
    ``CONSUMED``. ``source`` is ``API`` for a gateway-verified payment or
    ``MANUAL`` for a till/SMS reference entered by the counter.
    """
    reference = canonical_reference(reference)
    amount_value = float(amount)
    currency = str(currency or "").strip().upper()
    source = "MANUAL" if str(source).upper() == "MANUAL" else "API"
    requested_provider = _provider_or_none(provider)

    row = db.execute(
        "SELECT * FROM momo_collections WHERE reference=? COLLATE NOCASE",
        (reference,),
    ).fetchone()
    _check_provider(dict(row) if row is not None else None, requested_provider)
    if row is None:
        # A reference that predates the ledger, or a manual SMS reference.
        # The sales fallback catches an un-backfilled legacy row.
        legacy = db.execute(
            """SELECT id FROM sales
               WHERE TRIM(COALESCE(momo_ref,'')) <> ''
                 AND momo_ref=? COLLATE NOCASE LIMIT 1""",
            (reference,),
        ).fetchone()
        if legacy:
            raise PaymentError(
                "This MoMo reference is already on another sale", status=409
            )
        row_source = "MANUAL" if source == "MANUAL" else "LEGACY"
        key_prefix = "manual" if source == "MANUAL" else "legacy"
        try:
            db.execute(
                """INSERT INTO momo_collections(
                       reference, idempotency_key, external_id, amount, currency,
                       phone, status, source, provider, sale_receipt_ref,
                       created_at, updated_at)
                   VALUES(?,?,?,?,?,?, 'CONSUMED', ?, ?, ?,
                          datetime('now','localtime'),
                          datetime('now','localtime'))""",
                (
                    reference,
                    f"{key_prefix}:{reference}",
                    "",
                    amount_value,
                    currency,
                    str(phone or "").strip(),
                    row_source,
                    requested_provider or providers.MTN,
                    str(receipt_ref or "").strip(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise PaymentError(
                "This MoMo reference is already on another sale", status=409
            ) from exc
        record_event(
            db,
            reference,
            "SALE_CONSUMED",
            actor=actor,
            detail=f"receipt={receipt_ref} source={row_source} amount={amount_value}",
        )
        return get_collection(reference, db=db)

    status = str(row["status"] or "").upper()
    if str(row["sale_receipt_ref"] or "").strip() or status in {
        "CONSUMED",
        "VOIDED",
    }:
        raise PaymentError(
            "This MoMo reference is already on another sale", status=409
        )
    if status in TERMINAL_BAD_STATUSES:
        raise PaymentError(
            f"MoMo payment is {status}; the sale was not recorded", status=402
        )
    if source == "MANUAL" and str(row["source"] or "").upper() in {"API", "LEGACY"}:
        if status != "SUCCESSFUL":
            raise PaymentError(
                "This MoMo payment has not been confirmed; request the prompt "
                "or use the verified reference path",
                status=402,
            )
    if status not in CLAIMABLE_STATUSES:
        raise PaymentError(
            f"MoMo payment is {status or 'not confirmed'}; the sale was not recorded",
            status=402,
        )
    if status in {"PENDING", "UNKNOWN"} and not allow_pending:
        raise PaymentError(
            f"MoMo payment is {status}; the sale was not recorded", status=402
        )

    # A callback can confirm a payment without the counter ever polling it.
    # When the carrier reported an amount/currency, use that for the claim
    # check instead of trusting the amount originally requested. This catches
    # a partial payment or a callback for a different amount.
    reported_currency = (
        str(row["mtn_currency"] or "").strip().upper()
        if status == "SUCCESSFUL"
        else ""
    )
    reported_amount = _as_float(row["mtn_amount"])
    if status == "SUCCESSFUL" and reported_amount is not None:
        if reported_amount <= 0:
            raise PaymentError(
                "The carrier reported an invalid successful amount", status=402
            )
        paid_amount = reported_amount
    else:
        paid_amount = _as_float(row["amount"])
    if paid_amount is None or paid_amount <= 0:
        raise PaymentError("MoMo payment amount is not confirmed", status=402)
    if abs(paid_amount - amount_value) > 0.01:
        label = (
            reported_currency
            or str(row["currency"] or "").strip().upper()
            or currency
        )
        raise PaymentError(
            f"MoMo reference was for {label} {paid_amount:,.2f} but the sale "
            f"totals {currency} {amount_value:,.2f}",
            status=402,
            paid_amount=paid_amount,
            paid_currency=label,
        )
    row_currency = reported_currency or str(row["currency"] or "").strip().upper()
    if row_currency and currency and row_currency != currency:
        raise PaymentError(
            f"MoMo reference is in {row_currency}, not {currency}", status=402
        )

    cur = db.execute(
        """UPDATE momo_collections SET
               status='CONSUMED',
               sale_receipt_ref=?,
               amount = CASE WHEN amount <= 0 THEN ? ELSE amount END,
               currency = CASE WHEN TRIM(COALESCE(currency,''))='' THEN ? ELSE currency END,
               phone = CASE WHEN TRIM(COALESCE(phone,''))='' THEN ? ELSE phone END,
               updated_at = datetime('now','localtime')
           WHERE reference=? COLLATE NOCASE
             AND TRIM(COALESCE(sale_receipt_ref,''))=''
             AND status IN ('PENDING','SUCCESSFUL','UNKNOWN')""",
        (
            str(receipt_ref or "").strip(),
            amount_value,
            currency,
            str(phone or "").strip(),
            reference,
        ),
    )
    if cur.rowcount != 1:
        raise PaymentError(
            "This MoMo reference is already on another sale", status=409
        )
    record_event(
        db,
        reference,
        "SALE_CONSUMED",
        actor=actor,
        detail=f"receipt={receipt_ref} source={source} amount={amount_value}",
    )
    return get_collection(reference, db=db)


def attach_sale_id(db, reference, sale_id):
    """Link the claimed ledger row to the first sale row on the receipt."""
    try:
        reference = canonical_reference(reference)
    except ValueError:
        return
    db.execute(
        "UPDATE momo_collections SET sale_id=? WHERE reference=? COLLATE NOCASE",
        (sale_id, reference),
    )


def record_event(db, reference, event, actor="", detail=""):
    """Append an audit event, reusing the caller's transaction when supplied."""
    try:
        reference = canonical_reference(reference) if reference else ""
    except ValueError:
        reference = str(reference or "")[:128]
    own = db is None
    db = db or get_db()
    try:
        db.execute(
            """INSERT INTO momo_events(reference, event, actor, detail)
               VALUES(?,?,?,?)""",
            (reference, str(event or "")[:40], str(actor or "")[:80], str(detail or "")[:500]),
        )
        if own:
            db.commit()
    finally:
        if own:
            db.close()
