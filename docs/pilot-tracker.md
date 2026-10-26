# Pilot tracker — Onzima Charles Drug Shop

Fill this in during the two-week Phase 6 pilot. Keep it in the repo or in the
customer folder; do not put passwords in it.

## Pilot header

| Field | Value |
|---|---|
| Status | In progress — observation re-baselined 2026-10-26; runs through 2026-11-09 |
| Initial Day 0 | 2026-10-21 |
| Initial window | 2026-10-21 to 2026-11-04 (superseded by the v2.5 re-baseline) |
| Current observation | 2026-10-26 to 2026-11-09 |
| Release | `v2.5.0` / code commit `eaeb2f8` (initial pilot build `66f6ca7`) |
| Plan | Legacy (Pro + Alerts + Tender), grandfathered |
| Owner | Charles Onzima |
| Operator | Andama |
| Live database | `drugshop.db` at the project root |
| Pre-pilot backup | `instance/backups/drugshop-pre-pilot-20261021-192335.db` |
| Backup SHA256 | `E2AEED56CF6C7ACF1D8F5C2E4838A4DACEDFF75230859638324CEB7B3A14542C` |
| Re-baseline backup | `instance/backups/drugshop-pre-restart-20261026-113319.db` |
| Re-baseline SHA256 | `576235A8569C554F27C86579563148F696489D6C6CA068F77EB9FB949A6A286E` |
| Uploads backup | `instance/backups/uploads-pre-rebaseline-20261026-113155` |
| Server log | `instance/pilot/server.log` (fresh log from 2026-10-26 11:33) |
| Support WhatsApp | not configured |

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

After the initial Day 0 deployment: migration `002` applied, six Legacy
entitlement rows, all business counts unchanged, live DB SHA256
`3B2564F1A065FC090552C28AA7F206EFD5A443A792F0FF9E635521BB1CF6569B`.
Those are Day 0 values, not current values.

## Day 0 deployment — 2026-10-21 (historical)

| Check | Result | Time / note |
|---|---|---|
| Pre-pilot backup integrity `ok` | PASS | `drugshop-pre-pilot-20261021-192335.db`, SHA256 matches source |
| Uploads copied | PASS | `instance/backups/uploads-pre-pilot-20261021-192335` |
| Server booted | PASS | Initial log; port 5000 |
| `plan show` = Legacy | PASS | six apps; no expiry |
| Smoke `-Plan legacy` all green | PASS | 15/15 checks, including backup and Tender |
| `/api/apps` reports Legacy + 6 gate apps | PASS | detected plan `legacy` |
| Launcher shows all apps | PASS | `/` and `/staff` render 200 |
| Business row counts unchanged | PASS | users 3, products 8, batches 7, sales 5, patients 3, tender_docs 2 |
| Activation event recorded | PASS | `2026-10-21 19:24:13` |
| Core staging install created | PASS | `instance/staging-core`, port 5001 |
| Core smoke green | PASS | 15/15 |
| Staging downgrade/upgrade rehearsal | PASS | Core -> Pro -> Core; smoke green each time; row counts unchanged |

This Day 0 evidence is retained for history. The 14-day acceptance clock was
restarted after the build changed; see the re-baseline below.

## Re-baseline — 2026-10-26

The live build changed after Day 0: v2.5.0 branding/auth (`f2d23c3`) and the
Render deployment (`eaeb2f8`) landed, and the running server was not writing to
`instance/pilot/server.log` after its 10:24 restart. The old log ended at
2026-10-21 19:35, so its 403 count was stale and cannot support a no-regression
claim. The observation clock restarted on 2026-10-26 and ends 2026-11-09. Days
2026-10-22 through 2026-10-25 are recorded as not captured/superseded, not passed.

| Re-baseline check | Result |
|---|---|
| Release under observation | `eaeb2f8` / v2.5.0 |
| Test suite | 231 passed; `ruff check .` clean; `node --check` 16/16 JS files |
| Live plan | Legacy with POS, Inventory, Patients, Finance, Alerts, Tender |
| Live DB integrity | `ok` |
| Live smoke `-Plan legacy` | PASS — 15/15 |
| Server log captures new requests | PASS — restarted 2026-10-26 11:33; request lines present |
| Entitlement denial logging | PASS — staging Core log captured `app access denied` warnings for Patients and Tender |
| Staging Core -> Pro -> Core | PASS — 15/15 each; business row counts unchanged |
| 403 denials in fresh log | 0 as of 2026-10-26 11:33 (the pre-restart log is archived and not used as evidence) |
| Owner walkthrough | Pending |
| Upgrade demo | Pending |

Current metrics at re-baseline (`python scripts\pilot_metrics.py --log instance\pilot\server.log`):

| Metric | Value |
|---|---:|
| Logins (cumulative) | 91 |
| Distinct logged usernames | 3 (`admin`, `grace`, historical `andama`) |
| Active users | 2 |
| Products | 8 |
| Batches | 7 |
| Sales | 5 |
| Patients | 3 |
| Tender documents | 5 |
| Entitlement changes | 6 seed events on 2026-10-21 19:24:13 |

Open data check: the live `andama` user row is no longer present; 12 historical
login events remain. Current active accounts are `admin` (Charles Onzima) and
`grace` (Sarah Achen). Confirm that removing the developer account was
intentional before exit. Do not restore it automatically; it is not evidence of
a feature regression by itself.

## Daily log

`Logins` and `403 denials` are cumulative. Run
`python scripts\pilot_metrics.py --log instance\pilot\server.log` and copy the
totals. A fresh log starts at zero after a re-baseline or log rotation.

| Date | Logins | 403 denials | Support tickets | Owner feedback / notes | Action |
|---|---:|---:|---:|---|---|
| 2026-10-21 | 59 | 0 | 0 | Initial Day 0: Legacy seeded 19:24:13; live smoke 15/15; staging Core/Pro/Core green; business rows unchanged | Superseded by 2026-10-26 re-baseline |
| 2026-10-22 | — | — | — | Not captured before re-baseline | — |
| 2026-10-23 | — | — | — | Not captured before re-baseline; v2.5.0 code landed | — |
| 2026-10-24 | — | — | — | Not captured before re-baseline | — |
| 2026-10-25 | — | — | — | Not captured before re-baseline | — |
| 2026-10-26 | 91 | 0 | 0 | Re-baselined on `eaeb2f8`; live smoke 15/15; staging Core/Pro/Core 15/15 each with no row loss; fresh log started 11:33; users 2, products 8, batches 7, sales 5, patients 3, tender_docs 5 | Monitor; confirm `andama` removal |
| 2026-10-27 |  |  |  |  |  |
| 2026-10-28 |  |  |  |  |  |
| 2026-10-29 |  |  |  |  |  |
| 2026-10-30 |  |  |  |  |  |
| 2026-10-31 |  |  |  |  |  |
| 2026-11-01 |  |  |  |  |  |
| 2026-11-02 |  |  |  |  |  |
| 2026-11-03 |  |  |  |  |  |
| 2026-11-04 |  |  |  |  |  |
| 2026-11-05 |  |  |  |  |  |
| 2026-11-06 |  |  |  |  |  |
| 2026-11-07 |  |  |  |  |  |
| 2026-11-08 |  |  |  |  |  |
| 2026-11-09 |  |  |  | Exit review |  |

## 403 denial log

| Date | Endpoint | App | User/session | Context | Resolved |
|---|---|---|---|---|---|
| — | — | — | — | No 403s in the fresh log since 2026-10-26 11:33 | — |

A 403 during normal Legacy use is a regression. Expected 403s come only from
direct calls to an unentitled app, or from a staging Core/Tender install.

## Support tickets

| ID | Date | Reported by | Issue | Severity | Time spent | Resolution |
|---|---|---|---|---|---|---|
| — | — | — | No tickets recorded | — | 0 | — |

Target: at most 2 support hours for the pilot period.

## Owner walkthrough — 15 minutes

Status: pending. Schedule after the re-baseline and keep the demo on Legacy.

| Question | Owner answer | Follow-up |
|---|---|---|
| Is anything missing or locked? |  |  |
| Does the POS flow match the counter? |  |  |
| Which inventory or patient screen matters most? |  |  |
| Is the Tender Copilot output clear? |  |  |
| Who else needs a login? |  |  |
| What should we fix before day 14? |  |  |

## Upgrade conversation

Status: pending. Use the staging Core install; never change Onzima's live plan
during the pilot.

| Date | Path shown | Customer reaction | Next step | Outcome |
|---|---|---|---|---|
|  | Core → Pro / Growth / Tender |  |  |  |

## Final scorecard

| Metric | Target | Actual | Pass |
|---|---|---|---|
| Activation time per customer | < 15 minutes | ~1 minute (Day 0: backup 19:23:35 to smoke complete 19:24:37) | PASS (Day 0) |
| Unentitled 403s during normal Legacy use | 0 | 0 in fresh log so far | PASS so far |
| Downgrade/upgrade data loss | 0 rows | 0 on current-build staging Core/Pro/Core | PASS (rehearsal) |
| Support hours for the pilot | ≤ 2 hours | 0 so far | pending |
| Upgrade demo completed | ≥ 1 | 0 | pending |
| Time to quote a bundle | < 5 minutes | not measured | pending |
| Two weeks without regressions | yes | re-baselined 2026-10-26; day 0 of 14 | pending, ends 2026-11-09 |

## Exit decision

- [ ] Pilot passed; keep Onzima on Legacy and begin the next customer.
- [ ] Pilot passed with follow-ups; list them below.
- [ ] Pilot failed; rollback/extend and record why.

Notes:

```
The initial 2026-10-21 to 2026-11-04 observation is superseded. Acceptance must
cover the current v2.5 build from 2026-10-26 through 2026-11-09.
```

Signed off by: ____________________  Date: __________
