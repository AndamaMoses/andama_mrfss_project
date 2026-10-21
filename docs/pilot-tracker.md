# Pilot tracker — Onzima Charles Drug Shop

Fill this in during the two-week Phase 6 pilot. Keep it in the repo or in the
customer folder; do not put passwords in it.

## Pilot header

| Field | Value |
|---|---|
| Status | In progress — Day 0 complete; 14-day observation running |
| Start date | 2026-10-21 |
| End date | 2026-11-04 |
| Release | `phase-6-pilot-start` (code commit `66f6ca7`) |
| Plan | Legacy (Pro + Alerts + Tender), grandfathered |
| Owner | Charles Onzima |
| Operator | Andama |
| Live database | `drugshop.db` at the project root |
| Pre-pilot backup | `instance/backups/drugshop-pre-pilot-20261021-192335.db` |
| Backup SHA256 | `E2AEED56CF6C7ACF1D8F5C2E4838A4DACEDFF75230859638324CEB7B3A14542C` |
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

After deployment: migration `002` applied, six Legacy entitlement rows, all
business counts unchanged, live DB SHA256
`3B2564F1A065FC090552C28AA7F206EFD5A443A792F0FF9E635521BB1CF6569B`.

## Day 0 deployment

| Check | Result | Time / note |
|---|---|---|
| Pre-pilot backup integrity `ok` | PASS | `drugshop-pre-pilot-20261021-192335.db`, SHA256 matches source |
| Uploads copied | PASS | `instance/backups/uploads-pre-pilot-20261021-192335` |
| Server booted | PASS | `instance/pilot/server.log`; port 5000 |
| `plan show` = Legacy | PASS | six apps; no expiry |
| Smoke `-Plan legacy` all green | PASS | 15/15 checks, including backup and Tender |
| `/api/apps` reports Legacy + 6 gate apps | PASS | detected plan `legacy` |
| Launcher shows all apps | PASS | `/` and `/staff` render 200 |
| Business row counts unchanged | PASS | users 3, products 8, batches 7, sales 5, patients 3, tender_docs 2 |
| Activation event recorded | PASS | `2026-10-21 19:24:13` |
| Core staging install created | PASS | `instance/staging-core`, port 5001 |
| Core smoke green | PASS | 15/15 |
| Staging downgrade/upgrade rehearsal | PASS | Core -> Pro -> Core; smoke green each time; row counts unchanged |

## Daily log

| Date | Logins | 403 denials | Support tickets | Owner feedback / notes | Action |
|---|---:|---:|---:|---|---|
| 2026-10-21 | 59 | 0 | 0 | Day 0: Legacy seeded 19:24:13; live smoke 15/15; staging Core/Pro/Core smoke green; business rows unchanged | Monitor |
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
| Activation time per customer | < 15 minutes | ~1 minute (backup 19:23:35 to smoke complete 19:24:37) | PASS (Day 0) |
| Unentitled 403s during normal Legacy use | 0 | 0 so far | PASS (Day 0) |
| Downgrade/upgrade data loss | 0 rows | 0 on staging Core/Pro/Core | PASS (rehearsal) |
| Support hours for the pilot | ≤ 2 hours | 0 so far | pending |
| Upgrade demo completed | ≥ 1 | 0 | pending |
| Time to quote a bundle | < 5 minutes | not measured | pending |
| Two weeks without regressions | yes | day 0 of 14 | pending |

## Exit decision

- [ ] Pilot passed; keep Onzima on Legacy and begin the next customer.
- [ ] Pilot passed with follow-ups; list them below.
- [ ] Pilot failed; rollback/extend and record why.

Notes:

```

```

Signed off by: ____________________  Date: __________
