# Renewal reminder checklist

Start this **14 days before** `current_period_end`. Expiry is soft in v1, so the
reminder is a commercial control, not an automatic lockout.

## 1. Find who is due

Per installation:

```powershell
flask --app run revenue renewals --days 14
flask --app run revenue report
```

Portfolio:

```powershell
python scripts/revenue_rollup.py instance --format csv --days 14
python scripts/revenue_rollup.py instance --format json --days 14
```

The report includes overdue rows so nothing drops out of the queue. Confirm the
customer name, bundle, monthly fee, period end, and whether the row is overdue.

## 2. Contact the customer

Use the recorded contact and the configured support channel. Confirm:

1. the customer wants to continue;
2. the bundle and monthly fee are unchanged (or the approved change);
3. the next period start and end dates;
4. the payment method and reference.

Log the contact date and the customer's answer in the customer sheet.

## 3. Invoice and collect before renewing

```powershell
# Next period, monthly in advance.
flask --app run revenue invoice monthly `
    --period-start 2026-12-18 --period-end 2027-01-18 `
    --actor "Andama"

# Record the payment when it lands.
flask --app run revenue payment record INV-202611-0003 `
    --amount 180000 --method bank --reference "FT-..." `
    --received-by "Andama"

# Extend the period only after the commercial step is agreed.
flask --app run revenue renew --period-end 2027-01-18 `
    --actor "Andama" --notes "renewed after December payment"
```

If payment has not arrived by the period end, set the status and keep chasing:

```powershell
flask --app run revenue status past_due --actor "Andama" --notes "renewal unpaid"
```

Do not suspend access automatically. The founder decides whether to keep the
soft-expiry grace period or stop service; use `plan set core` only as an
explicit access decision.

## 4. Verify

```powershell
flask --app run revenue show
flask --app run plan show
flask --app run revenue report
```

- Subscription and entitlements agree (or the combined-plan custom mix is
  understood).
- The new invoice appears with the correct period and balance.
- The payment is recorded once.
- MRR and outstanding balance match the close worksheet.

## 5. Record the renewal

| Field | Value |
|---|---|
| Customer | |
| Previous period end | |
| New period end | |
| Invoice no. / amount | |
| Payment date / reference | |
| Status after renewal | |
| Customer confirmation | |
| Operator | |
| Date | |

If the customer declines, record the reason, set `cancelled` when appropriate,
and preserve the data. Do not delete invoices or payments.
