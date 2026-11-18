# Monthly close checklist

Run this on the last working day of each month, per installation, after the
month's invoices and payments are recorded. The report is read-only; corrections
are made with `revenue invoice void` and a reissue, never by editing SQLite.

## 1. Confirm the database and take a backup

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -c "import config; print(config.DevConfig.DATABASE); print(config.DevConfig.UPLOAD_DIR)"
```

Stop the app, copy the database (see
[onboarding-runbook.md](onboarding-runbook.md) section 2), verify
`PRAGMA integrity_check` returns `ok`, and record the SHA256 hash.

## 2. Produce the report

```powershell
New-Item -ItemType Directory -Force instance\reports | Out-Null
flask --app run revenue report --format json |
    Set-Content -Encoding utf8 instance\reports\revenue-2026-11.json
flask --app run revenue report
```

For a portfolio, run the read-only rollup and keep both files:

```powershell
python scripts/revenue_rollup.py instance --format csv |
    Set-Content -Encoding utf8 instance\reports\portfolio-2026-11.csv
python scripts/revenue_rollup.py instance --format json |
    Set-Content -Encoding utf8 instance\reports\portfolio-2026-11.json
```

The rollup opens each database read-only, holds one read snapshot per source,
and fails if a source hash changes. Stop the shop app, or report against a
copy, when you need a guaranteed point-in-time file.

## 3. Reconcile

The report is a **cumulative snapshot**, not a period filter. To get the
month's movement, subtract the previous close from the current report and keep
both files.

| Check | Expected | Actual | OK |
|---|---|---|---|
| Report as-of / generated at | Matches the close date | | |
| MRR | Sum of `active` + `past_due` monthly fees | | |
| Setup invoiced | Lifetime non-void setup invoices (month = current − last close) | | |
| Setup collected | Lifetime payments against non-void setup invoices | | |
| Payments collected | Lifetime bank + cash + MoMo + Airtel + other (month = current − last close) | | |
| Outstanding balance | Snapshot of non-void invoice balances | | |
| Void invoices | Visible, zero balance, no payment | | |
| Grandfathered | Legacy subscriptions with MRR 0 | | |
| Excluded | Pending/cancelled/expired subscriptions | | |
| Renewals due | Report list matches `revenue renewals --days 14` | | |

Rules:

- One payment is recorded once; do not double-enter a bank or MoMo reference.
- Overpayment is blocked by the service. If a customer pays early, record it
  against the correct invoice.
- A wrong invoice is voided and reissued; a payment cannot be deleted.
- A voided invoice cannot have payments; the service refuses to void a paid or
  partly paid invoice, so collected totals stay reconcilable.
- A portfolio that mixes currencies is rejected; report each currency
  separately.
- If the report does not reconcile, stop and fix the source record before
  reporting the month.

## 4. Check renewals and expiries

```powershell
flask --app run revenue renewals --days 14
```

Compare with the report's `renewals_due` list. Start the
[renewal reminder](renewal-reminder-checklist.md) for any customer in the
window, and record overdue customers as `past_due` when the founder agrees.

## 5. Record the close

| Field | Value |
|---|---|
| Month | |
| Database | |
| Backup path + SHA256 | |
| Report path | |
| Report as-of / generated at | |
| MRR | |
| Setup collected | |
| Payments collected | |
| Outstanding balance | |
| Renewals due | |
| Corrections made (invoice no. / reason) | |
| Closed by | |
| Founder review | |
| Date | |

File the report and backup together. The next month starts from the closing
report, not from a hand-made spreadsheet: monthly movement is the current
cumulative report minus this close.
