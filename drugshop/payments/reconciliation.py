"""Payment reconciliation: stale-prompt sweeps and the daily variance ledger.

Two related jobs live here:

* A stale ``PENDING``/``UNKNOWN`` collection is one where the customer may
  still approve a prompt, or where the carrier accepted a request but the
  response was lost. The sweep re-asks the carrier and updates the ledger. It
  never creates a new prompt and never frees a consumed reference.
* The daily summary compares the mobile-money sales recorded by the POS with
  the ledger rows the carriers confirmed. It also surfaces unresolved prompts
  and successful payments that were never attached to a sale, because those are
  the two cases a cashier must resolve before closing the day.

No function in this module moves money. Every carrier call is a status read.
"""
from __future__ import annotations

import json
from datetime import date

from drugshop.db import get_db
from drugshop.payments import ledger, providers, service
from drugshop.payments.errors import PaymentError

DEFAULT_STALE_MINUTES = 15
MAX_SWEEP_LIMIT = 200
ATTENTION_LIMIT = 100

TERMINAL_BAD_STATUSES = ledger.TERMINAL_BAD_STATUSES


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value, default, minimum=0, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if number < minimum:
        number = minimum
    if maximum is not None and number > maximum:
        number = maximum
    return number


def _provider_or_none(value):
    """Normalise a provider filter, treating blank/ALL/AUTO as no filter."""
    text = str(value or "").strip().upper()
    if text in {"", "ALL", "AUTO", "ANY"}:
        return None
    return providers.normalize_provider(text)


def stale_collections(
    provider=None,
    older_than_minutes=DEFAULT_STALE_MINUTES,
    limit=50,
    db=None,
    preferred_providers=None,
):
    """Return unresolved ledger rows that have not been checked recently.

    Rows are selected by ``updated_at`` so a sweep that still sees ``PENDING``
    does not hit the carrier again on every run. Consumed, voided, and terminal
    rows are never selected.

    ``preferred_providers`` only affects an unfiltered (ALL) sweep: rows owned
    by a configured carrier sort ahead of rows from an unconfigured one. Without
    that priority, 50 old rows from a carrier with no credentials could fill the
    limit on every run and starve the configured carrier forever.
    """
    wanted = _provider_or_none(provider)
    minutes = _as_int(older_than_minutes, DEFAULT_STALE_MINUTES)
    capped_limit = _as_int(limit, 50, minimum=1, maximum=MAX_SWEEP_LIMIT)
    modifier = f"-{minutes} minutes"

    priority = ""
    priority_params = []
    if wanted is None and preferred_providers:
        preferred = [p for p in preferred_providers if p]
        if preferred:
            placeholders = ",".join("?" for _ in preferred)
            priority = (
                "CASE WHEN provider IN (" + placeholders + ") THEN 0 ELSE 1 END, "
            )
            priority_params = preferred

    own = db is None
    db = db or get_db()
    try:
        sql = """
            SELECT * FROM momo_collections
            WHERE UPPER(status) IN ('PENDING','UNKNOWN')
              AND TRIM(COALESCE(sale_receipt_ref,'')) = ''
              AND datetime(COALESCE(NULLIF(updated_at,''), created_at))
                  <= datetime('now','localtime', ?)
        """
        params = [modifier]
        if wanted:
            sql += " AND provider = ?"
            params.append(wanted)
        sql += (
            " ORDER BY "
            + priority
            + "datetime(COALESCE(NULLIF(updated_at,''), created_at)) ASC, "
            + "rowid ASC LIMIT ?"
        )
        params.extend(priority_params)
        params.append(capped_limit)
        return [dict(row) for row in db.execute(sql, params).fetchall()]
    finally:
        if own:
            db.close()


def _sweep_row(row, actor="", dry_run=False):
    """Check one stale row and return a result dictionary."""
    reference = row.get("reference", "")
    row_provider = str(row.get("provider") or providers.MTN).upper()
    result = {
        "reference": reference,
        "provider": row_provider,
        "old_status": str(row.get("status") or "").upper(),
        "amount": row.get("amount"),
        "currency": row.get("currency", ""),
        "phone": row.get("phone", ""),
    }
    if not ledger.is_uuid(reference):
        result.update(outcome="skipped", reason="reference is not a UUID")
        return result
    if dry_run:
        result.update(outcome="would_check")
        return result
    if not service.enabled(row_provider):
        result.update(outcome="skipped", reason="provider is not configured")
        return result

    try:
        data = service.fetch_status(reference, row_provider)
        updated = ledger.apply_status(
            reference,
            data,
            source="RECONCILE",
            actor=actor,
            provider=row_provider,
        )
    except PaymentError as exc:
        result.update(outcome="error", error=str(exc), error_status=exc.status)
        ledger.record_event(
            None,
            reference,
            "RECONCILE_ERROR",
            actor=actor,
            detail=str(exc)[:500],
        )
        return result

    new_status = str((updated or {}).get("status") or "").upper()
    outcome = "updated" if new_status != result["old_status"] else "unchanged"
    result.update(
        outcome=outcome,
        new_status=new_status,
        gateway_status=str(data.get("status") or "").upper(),
        amount=data.get("amount", row.get("amount")),
        currency=data.get("currency", row.get("currency", "")),
    )
    ledger.record_event(
        None,
        reference,
        "RECONCILE",
        actor=actor,
        detail=(
            f"old={result['old_status']} gateway={result['gateway_status']} "
            f"new={new_status}"
        ),
    )
    return result


def sweep_stale(
    provider=None,
    older_than_minutes=DEFAULT_STALE_MINUTES,
    limit=50,
    actor="",
    dry_run=False,
):
    """Poll carriers for stale unresolved collections and update the ledger.

    The sweep is deliberately bounded and safe to run repeatedly. A carrier
    error leaves the row unresolved; the next run retries it. A row whose
    provider is not configured is reported as skipped instead of being marked
    failed, because the shop may add credentials later.
    """
    try:
        wanted = _provider_or_none(provider)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    configured = [p for p in providers.PROVIDERS if service.enabled(p)]
    rows = stale_collections(
        provider=wanted,
        older_than_minutes=older_than_minutes,
        limit=limit,
        preferred_providers=configured,
    )
    counts = {
        "checked": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": 0,
        "skipped": 0,
        "would_check": 0,
    }
    results = []
    for row in rows:
        result = _sweep_row(row, actor=actor, dry_run=dry_run)
        results.append(result)
        outcome = result["outcome"]
        if outcome == "updated":
            counts["checked"] += 1
            counts["updated"] += 1
        elif outcome == "unchanged":
            counts["checked"] += 1
            counts["unchanged"] += 1
        elif outcome == "error":
            counts["checked"] += 1
            counts["errors"] += 1
        elif outcome == "would_check":
            counts["would_check"] += 1
        else:
            counts["skipped"] += 1

    return {
        "provider": wanted or "ALL",
        "older_than_minutes": _as_int(older_than_minutes, DEFAULT_STALE_MINUTES),
        "limit": _as_int(limit, 50, minimum=1, maximum=MAX_SWEEP_LIMIT),
        "dry_run": bool(dry_run),
        **counts,
        "results": results,
    }


def _provider_summary(db, provider, day):
    method = providers.PROVIDER_TO_METHOD[provider]
    expected_row = db.execute(
        """SELECT COALESCE(SUM(total),0) AS amount,
                  COUNT(DISTINCT CASE
                      WHEN TRIM(COALESCE(receipt_ref,'')) = '' THEN 'sale-' || id
                      ELSE receipt_ref END) AS receipts
           FROM sales WHERE sale_date=? AND payment_method=?""",
        (day, method),
    ).fetchone()
    expected = _as_float(expected_row["amount"])
    receipts = int(expected_row["receipts"] or 0)

    consumed_row = db.execute(
        """SELECT COALESCE(SUM(m.amount),0) AS amount, COUNT(*) AS receipts
           FROM momo_collections m
           WHERE m.provider=?
             AND TRIM(COALESCE(m.sale_receipt_ref,'')) <> ''
             AND m.sale_receipt_ref IN (
                 SELECT DISTINCT s.receipt_ref FROM sales s
                 WHERE s.sale_date=? AND TRIM(COALESCE(s.receipt_ref,'')) <> ''
             )""",
        (provider, day),
    ).fetchone()
    consumed = _as_float(consumed_row["amount"])

    status_rows = db.execute(
        """SELECT UPPER(status) AS status, COUNT(*) AS n,
                  COALESCE(SUM(amount),0) AS amount
           FROM momo_collections
           WHERE provider=? AND date(created_at)=?
           GROUP BY UPPER(status)""",
        (provider, day),
    ).fetchall()
    by_status = {
        str(row["status"] or ""): {
            "count": int(row["n"] or 0),
            "amount": _as_float(row["amount"]),
        }
        for row in status_rows
    }

    # ``successful`` means the carrier confirmed the payment, not merely that a
    # sale claimed it. A pending prompt consumed during a verification-off
    # rollout (or a manual reference) is CONSUMED without a carrier status, and
    # must not inflate the confirmed total.
    successful_row = db.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS amount
           FROM momo_collections
           WHERE provider=? AND date(created_at)=?
             AND (UPPER(status)='SUCCESSFUL'
                  OR (UPPER(status)='CONSUMED'
                      AND UPPER(COALESCE(mtn_status,''))='SUCCESSFUL'))""",
        (provider, day),
    ).fetchone()
    successful = _as_float(successful_row["amount"])

    pending = by_status.get("PENDING", {"count": 0, "amount": 0.0})
    unknown = by_status.get("UNKNOWN", {"count": 0, "amount": 0.0})
    failed = sum(
        by_status.get(status, {"amount": 0.0})["amount"]
        for status in TERMINAL_BAD_STATUSES
    )

    unresolved_row = db.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS amount
           FROM momo_collections
           WHERE provider=? AND UPPER(status) IN ('PENDING','UNKNOWN')
             AND TRIM(COALESCE(sale_receipt_ref,'')) = ''""",
        (provider,),
    ).fetchone()
    unresolved_count = int(unresolved_row["n"] or 0)
    unresolved_amount = _as_float(unresolved_row["amount"])

    # A consumed row normally points at an existing receipt. If that sale was
    # voided, the receipt is gone but the ledger deliberately stays CONSUMED
    # (a void never frees a payment). Without this branch the customer's money
    # would disappear from both the variance and the attention list.
    orphaned_row = db.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(m.amount),0) AS amount
           FROM momo_collections m
           WHERE m.provider=? AND UPPER(m.status) IN ('SUCCESSFUL','CONSUMED')
             AND (
                 TRIM(COALESCE(m.sale_receipt_ref,'')) = ''
                 OR NOT EXISTS (
                     SELECT 1 FROM sales s
                     WHERE s.receipt_ref = m.sale_receipt_ref
                 )
             )""",
        (provider,),
    ).fetchone()
    orphaned_count = int(orphaned_row["n"] or 0)
    orphaned_amount = _as_float(orphaned_row["amount"])

    variance = round(consumed - expected, 2)
    status = (
        "BALANCED"
        if abs(variance) < 0.01
        and orphaned_count == 0
        and unresolved_count == 0
        else "ATTENTION"
    )
    return {
        "payment_method": method,
        "sales_receipts": receipts,
        "expected": expected,
        "consumed": consumed,
        "successful": successful,
        "pending": _as_float(pending["amount"]),
        "unknown": _as_float(unknown["amount"]),
        "failed": failed,
        "orphaned": orphaned_amount,
        "unresolved_amount": unresolved_amount,
        "unresolved_count": unresolved_count,
        "orphaned_count": orphaned_count,
        "variance": variance,
        "status": status,
        "status_counts": by_status,
    }


def payment_summary(day=None):
    """Return the live mobile-money reconciliation view for one day."""
    day = str(day or date.today().isoformat())
    db = get_db()
    try:
        result = {
            "date": day,
            "providers": {},
            "totals": {
                "expected": 0.0,
                "consumed": 0.0,
                "successful": 0.0,
                "pending": 0.0,
                "unknown": 0.0,
                "failed": 0.0,
                "orphaned": 0.0,
                "unresolved_amount": 0.0,
                "unresolved_count": 0,
                "orphaned_count": 0,
                "variance": 0.0,
            },
            "unresolved": [],
            "orphaned": [],
        }
        for provider in providers.PROVIDERS:
            summary = _provider_summary(db, provider, day)
            result["providers"][provider] = summary
            for key in result["totals"]:
                result["totals"][key] += summary[key]

        for key in ("expected", "consumed", "successful", "pending", "unknown",
                    "failed", "orphaned", "unresolved_amount", "variance"):
            result["totals"][key] = round(result["totals"][key], 2)

        unresolved = db.execute(
            """SELECT reference, provider, amount, currency, phone, external_id,
                      status, mtn_status, last_error, created_at, updated_at
               FROM momo_collections
               WHERE UPPER(status) IN ('PENDING','UNKNOWN')
                 AND TRIM(COALESCE(sale_receipt_ref,'')) = ''
               ORDER BY datetime(COALESCE(NULLIF(updated_at,''), created_at)) ASC,
                        rowid ASC
               LIMIT ?""",
            (ATTENTION_LIMIT,),
        ).fetchall()
        orphaned = db.execute(
            """SELECT m.reference, m.provider, m.amount, m.currency, m.phone,
                      m.external_id, m.status, m.mtn_status, m.last_error,
                      m.created_at, m.updated_at
               FROM momo_collections m
               WHERE UPPER(m.status) IN ('SUCCESSFUL','CONSUMED')
                 AND (
                     TRIM(COALESCE(m.sale_receipt_ref,'')) = ''
                     OR NOT EXISTS (
                         SELECT 1 FROM sales s
                         WHERE s.receipt_ref = m.sale_receipt_ref
                     )
                 )
               ORDER BY datetime(COALESCE(NULLIF(m.updated_at,''), m.created_at)) ASC,
                        m.rowid ASC
               LIMIT ?""",
            (ATTENTION_LIMIT,),
        ).fetchall()
        result["unresolved"] = [dict(row) for row in unresolved]
        result["orphaned"] = [dict(row) for row in orphaned]
        result["unresolved_truncated"] = len(result["unresolved"]) >= ATTENTION_LIMIT
        result["orphaned_truncated"] = len(result["orphaned"]) >= ATTENTION_LIMIT
        result["totals"]["status"] = (
            "BALANCED"
            if abs(result["totals"]["variance"]) < 0.01
            and result["totals"]["orphaned_count"] == 0
            and result["totals"]["unresolved_count"] == 0
            else "ATTENTION"
        )
        return result
    finally:
        db.close()


def snapshot_payment_reconciliation(day=None, actor=""):
    """Persist one provider-level payment variance snapshot per day.

    The snapshot is an audit record of what the ledger and the sales table said
    when the shift was closed. It never changes a payment status or a sale.
    """
    day = str(day or date.today().isoformat())
    summary = payment_summary(day)
    db = get_db()
    try:
        for provider, values in summary["providers"].items():
            snapshot_data = {
                key: values[key]
                for key in (
                    "payment_method",
                    "sales_receipts",
                    "expected",
                    "consumed",
                    "successful",
                    "pending",
                    "unknown",
                    "failed",
                    "orphaned",
                    "unresolved_amount",
                    "unresolved_count",
                    "orphaned_count",
                    "variance",
                    "status",
                )
            }
            snapshot_data["snapshot_actor"] = str(actor or "")
            snapshot = json.dumps(snapshot_data, sort_keys=True)
            db.execute(
                """INSERT INTO payment_reconciliations(
                       rec_date, provider, expected_amount, consumed_amount,
                       successful_amount, pending_amount, unknown_amount,
                       orphaned_amount, unresolved_count, orphaned_count,
                       variance, status, snapshot, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,
                          datetime('now','localtime'),
                          datetime('now','localtime'))
                   ON CONFLICT(rec_date, provider) DO UPDATE SET
                       expected_amount=excluded.expected_amount,
                       consumed_amount=excluded.consumed_amount,
                       successful_amount=excluded.successful_amount,
                       pending_amount=excluded.pending_amount,
                       unknown_amount=excluded.unknown_amount,
                       orphaned_amount=excluded.orphaned_amount,
                       unresolved_count=excluded.unresolved_count,
                       orphaned_count=excluded.orphaned_count,
                       variance=excluded.variance,
                       status=excluded.status,
                       snapshot=excluded.snapshot,
                       updated_at=excluded.updated_at""",
                (
                    day,
                    provider,
                    values["expected"],
                    values["consumed"],
                    values["successful"],
                    values["pending"],
                    values["unknown"],
                    values["orphaned"],
                    values["unresolved_count"],
                    values["orphaned_count"],
                    values["variance"],
                    values["status"],
                    snapshot,
                ),
            )
        db.commit()
    finally:
        db.close()
    return summary


def saved_payment_reconciliations(day=None):
    """Return the persisted provider snapshots for a day."""
    day = str(day or date.today().isoformat())
    db = get_db()
    try:
        rows = db.execute(
            """SELECT * FROM payment_reconciliations
               WHERE rec_date=? ORDER BY provider""",
            (day,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def payment_reconciliation_report(day=None):
    """Return the live view plus any snapshots already saved for the day."""
    day = str(day or date.today().isoformat())
    return {
        "date": day,
        "live": payment_summary(day),
        "saved": saved_payment_reconciliations(day),
    }
