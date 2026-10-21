# Pilot tracker — Onzima Charles Drug Shop

Fill this in during the two-week Phase 6 pilot. Keep it in the repo or in the
customer folder; do not put passwords in it.

## Pilot header

| Field | Value |
|---|---|
| Status | Ready to start |
| Start date | 2026-10-21 |
| End date | 2026-11-04 |
| Release | `phase-5-hardening` / commit `1f436bc` |
| Plan | Legacy (Pro + Alerts + Tender), grandfathered |
| Owner | Charles Onzima |
| Operator | Andama |
| Live database | `drugshop.db` at the project root |
| Pre-pilot backup | `instance/backups/drugshop-pre-pilot-<stamp>.db` |
| Backup SHA256 | _fill in after backup_ |
| Server log | `instance/pilot/server.log` |
| Support WhatsApp | _fill in from config_ |

## Baseline before deployment

Measured with `python scripts\pilot_metrics.py --json` before the migration:

| Table | Rows |
|---|---:|
| users | 3 |
| products | 8 |
| batches | 7 |
| sales | 5 |
| patients | 3 |
| tender_docs | 2 |
| login_events | 57 |

Plan at baseline: `unseeded` (migration `001` only). No `app_entitlements`
table yet.

## Day 0 deployment

| Check | Result | Time / note |
|---|---|---|
| Pre-pilot backup integrity `ok` | pending | |
| Uploads copied | pending | |
| Server booted | pending | |
| `plan show` = Legacy | pending | |
| Smoke `-Plan legacy` all green | pending | |
| `/api/apps` reports Legacy + 6 gate apps | pending | |
| Launcher shows all apps | pending | |
| Business row counts unchanged | pending | |
| Activation event recorded | pending | |
| Core staging install created | pending | |
| Core smoke green | pending | |
| Staging downgrade/upgrade rehearsal | pending | |

## Daily log

| Date | Logins | 403 denials | Support tickets | Owner feedback / notes | Action |
|---|---:|---:|---:|---|---|
| 2026-10-21 |  |  |  | Day 0 deployment | |
| 2026-10-22 |  |  |  |  | |
| 2026-10-23 |  |  |  |  | |
| 2026-10-24 |  |  |  |  | |
| 2026-10-25 |  |  |  |  | |
| 2026-10-26 |  |  |  |  | |
| 2026-10-27 |  |  |  |  | |
| 2026-10-28 |  |  |  |  | |
| 2026-10-29 |  |  |  |  | |
| 2026-10-30 |  |  |  |  | |
| 2026-10-31 |  |  |  |  | |
| 2026-11-01 |  |  |  |  | |
| 2026-11-02 |  |  |  |  | |
| 2026-11-03 |  |  |  |  | |
| 2026-11-04 |  |  |  | Exit review | |

Run `python scripts\pilot_metrics.py --log instance\pilot\server.log` and copy
the totals into the day's row. Record cumulative 403s; the daily delta is the
difference from the previous row.

## 403 denial log

| Date | Endpoint | App | User/session | Context | Resolved |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

A 403 during normal Legacy use is a regression. Expected 403s come only from
direct calls to an unentitled app, or from a staging Core/Tender install.

## Support tickets

| ID | Date | Reported by | Issue | Severity | Time spent | Resolution |
|---|---|---|---:|---:|---:|---|
|  |  |  |  |  |  |  |

Target: at most 2 support hours for the pilot period.

## Owner walkthrough — 15 minutes

| Question | Owner answer | Follow-up |
|---|---|---|
| Is anything missing or locked? |  |  |
| Does the POS flow match the counter? |  |  |
| Which inventory or patient screen matters most? |  |  |
| Is the Tender Copilot output clear? |  |  |
| Who else needs a login? |  |  |
| What should we fix before day 14? |  |  |

## Upgrade conversation

Use the staging Core install; never change Onzima's live plan during the pilot.

| Date | Path shown | Customer reaction | Next step | Outcome |
|---|---|---|---|---|
|  | Core → Pro / Growth / Tender |  |  |  |

## Final scorecard

| Metric | Target | Actual | Pass |
|---|---|---:|---|
| Activation time per customer | < 15 minutes |  |  |
| Unentitled 403s during normal Legacy use | 0 |  |  |
| Downgrade/upgrade data loss | 0 rows |  |  |
| Support hours for the pilot | ≤ 2 hours |  |  |
| Upgrade demo completed | ≥ 1 |  |  |
| Time to quote a bundle | < 5 minutes |  |  |
| Two weeks without regressions | yes |  |  |

## Exit decision

- [ ] Pilot passed; keep Onzima on Legacy and begin the next customer.
- [ ] Pilot passed with follow-ups; list them below.
- [ ] Pilot failed; rollback/extend and record why.

Notes:

```

```

Signed off by: ____________________  Date: __________
