# Pilot tracker — Onzima Charles Drug Shop

Fill this in during the two-week Phase 6 pilot. Keep it in the repo or in the
customer folder; do not put passwords in it.

## Pilot header

| Field | Value |
|---|---|
| Status | Re-baselined on `a622894` (2026-11-06); new observation window 2026-11-06 to 2026-11-20. Day 0 tests and staging rehearsal PASS; live smoke and fresh log pending; owner walkthrough answers pending; upgrade demo not completed; support time not tracked |
| Initial Day 0 | 2026-10-21 |
| Initial window | 2026-10-21 to 2026-11-04 (superseded by the v2.5 re-baseline) |
| Current observation | 2026-11-06 to 2026-11-20 (re-baselined on `a622894`; the `eaeb2f8` window is superseded) |
| Release | `a622894` / 2026-11-06 (previous pilot build `eaeb2f8` superseded) |
| Plan | Legacy (Pro + Alerts + Tender), grandfathered |
| Owner | Charles Onzima |
| Operator | Andama |
| Live database | `drugshop.db` at the project root |
| Pre-pilot backup | `instance/backups/drugshop-pre-pilot-20261021-192335.db` |
| Backup SHA256 | `E2AEED56CF6C7ACF1D8F5C2E4838A4DACEDFF75230859638324CEB7B3A14542C` |
| Re-baseline backup | `instance/backups/drugshop-pre-restart-20261026-113319.db` |
| Re-baseline SHA256 | `576235A8569C554F27C86579563148F696489D6C6CA068F77EB9FB949A6A286E` |
| Uploads backup | `instance/backups/uploads-pre-rebaseline-20261026-113155` |
| Server log | `instance/pilot/server.log` (fresh 2026-10-26 11:33–11:42; stale afterward) |
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
| Owner walkthrough | Pending at re-baseline; completed 2026-11-09 (answers pending) |
| Upgrade demo | Pending at re-baseline; not completed as of 2026-11-09 |

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

## Final metrics — 2026-11-09

Measured read-only with `python scripts\pilot_metrics.py --log instance\pilot\server.log`
and `--since 2026-10-26`; JSON snapshot saved to
`instance/pilot/final-metrics-20261109.json`.

| Metric | Value |
|---|---:|
| Logins (cumulative) | 131 |
| Login events since 2026-10-26 | 42 (40 after the 11:33 re-baseline snapshot) |
| Distinct logged usernames (cumulative) | 3 (`admin`, `grace`, historical `andama`) |
| Active users | 2 (`admin`, `grace`) |
| Last login | 2026-11-06 10:23:27 |
| Products | 8 |
| Batches | 7 |
| Sales | 12 (was 5 at re-baseline; +7) |
| Patients | 3 |
| Tender documents | 11 (was 5 at re-baseline; +6) |
| Live DB integrity | `ok` |
| Final backup | `instance/backups/drugshop-post-pilot-20261109-014340.db` |
| Final backup SHA256 | `43375B60EE2E60541EA38C9F8A2FF36F7258E2B04AAA049A220F13C544520B70` |
| Final backup integrity | `ok`; business counts match the live DB |

The fresh `eaeb2f8` server log ends at 2026-10-26 11:42:33. It captured zero
403s in its nine-minute window, but it is stale for the rest of that window
(2026-10-27 through 2026-11-09). The 403 count for the `eaeb2f8` pilot is
therefore **not evidenced** from the local log; a Render/remote access log or a
fresh server log is required to close that criterion.

## Build change — confirmed 2026-11-09

The operator confirmed that the live app was updated from `eaeb2f8` to
`a622894` on 2026-11-06. Per the runbook, the `eaeb2f8` observation window is
superseded: do not carry its 403 counts, smoke evidence, or acceptance clock
into the new build. The new observation window is **2026-11-06 to 2026-11-20**.
Re-run the Day 0 smoke/rehearsal evidence on `a622894` and start a fresh server
log for the new window.

## Re-baseline evidence on a622894 — 2026-11-09

The exact `a622894` build was checked in a clean git worktree (without the
uncommitted payment-hardening changes):

| Check | Result |
|---|---|
| Test suite | PASS — 499 passed |
| Ruff | PASS — clean |
| JavaScript syntax | PASS — all 17 modules under `drugshop/static/js/` |
| Staging Core smoke | PASS — 15/15 |
| Staging Core → Pro | PASS — 15/15 |
| Staging Pro → Core | PASS — 15/15 |
| Business rows before/after | PASS — users 2, products 8, batches 7, sales 2, patients 3, tender_docs 0; no data loss |
| Staging DB integrity | PASS — `ok` |
| Evidence | `instance/pilot/rebaseline-a622894/` |

Still pending for the new window: live smoke on the deployed app, `/api/apps`
Legacy confirmation, launcher check, and a fresh 403/server log.

Open data check: the live `andama` user row is no longer present; 12 historical
login events remain. Current active accounts are `admin` (Charles Onzima) and
`grace` (Sarah Achen). The operator confirmed on 2026-11-09 that removing the
developer account was intentional; no action required. Do not restore it
automatically; it is not evidence of a feature regression by itself.

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
| 2026-10-26 | 92 | 0 | 0 | Re-baselined on `eaeb2f8`; live smoke 15/15; staging Core/Pro/Core 15/15 each with no row loss; fresh log started 11:33; 91 logins at the snapshot, 92 by end of day; users 2, products 8, batches 7, sales 5, patients 3, tender_docs 5 | Monitor; confirm `andama` removal |
| 2026-10-27 | 92 | — | — | No login activity recorded; server log stale | 403 not captured |
| 2026-10-28 | 92 | — | — | No login activity recorded; server log stale | 403 not captured |
| 2026-10-29 | 93 | — | — | 1 login; 2 sales (UGX 104,000) | 403 not captured |
| 2026-10-30 | 96 | — | — | 3 logins | 403 not captured |
| 2026-10-31 | 97 | — | — | 1 login | 403 not captured |
| 2026-11-01 | 97 | — | — | 1 sale (UGX 2,000) | 403 not captured |
| 2026-11-02 | 126 | — | — | 29 logins; 3 sales (UGX 1,500) | 403 not captured; unusually high login count |
| 2026-11-03 | 128 | — | — | 2 logins | 403 not captured |
| 2026-11-04 | 129 | — | — | 1 login; 1 sale (UGX 1,500) | 403 not captured |
| 2026-11-05 | 129 | — | — | No login activity recorded | 403 not captured |
| 2026-11-06 | 131 | — | — | 2 logins; 6 tender documents uploaded (5 → 11); live build changed to `a622894`; new observation window starts | 403 not captured; new Day 0 evidence required |
| 2026-11-07 | 131 | — | — | No login activity recorded | 403 not captured |
| 2026-11-08 | 131 | — | — | No login activity recorded | 403 not captured |
| 2026-11-09 | 131 | — | — | Exit review; final metrics and backup captured; live build confirmed as `a622894` (2026-11-06); re-baseline evidence: 499 tests, staging Core/Pro/Core 15/15 each, no data loss; owner walkthrough completed (answers pending); upgrade demo not completed; support time not tracked | New window 2026-11-06 to 2026-11-20; live smoke and fresh log pending; exit decision: wait |

## 403 denial log

| Date | Endpoint | App | User/session | Context | Resolved |
|---|---|---|---|---|---|
| 2026-10-26 | — | — | — | 0 403s in the fresh log window 11:33–11:42 | — |
| 2026-10-27 to 2026-11-09 | — | — | — | No fresh server log after 2026-10-26 11:42; 403 count not captured | Open evidence gap |

A 403 during normal Legacy use is a regression. Expected 403s come only from
direct calls to an unentitled app, or from a staging Core/Tender install.

## Support tickets

| ID | Date | Reported by | Issue | Severity | Time spent | Resolution |
|---|---|---|---|---|---|---|
| — | — | — | No tickets recorded | — | 0 | — |

Target: at most 2 support hours for the pilot period. Support time was **not
tracked** during this window, so the target cannot be verified.

## Owner walkthrough — 15 minutes

Status: completed 2026-11-09 — answers pending transcription into the table
below. Keep the demo on Legacy for the walkthrough.

| Question | Owner answer | Follow-up |
|---|---|---|
| Is anything missing or locked? |  |  |
| Does the POS flow match the counter? |  |  |
| Which inventory or patient screen matters most? |  |  |
| Is the Tender Copilot output clear? |  |  |
| Who else needs a login? |  |  |
| What should we fix before day 14? |  |  |

## Upgrade conversation

Status: not completed. Use the staging Core install; never change Onzima's live
plan during the pilot.

| Date | Path shown | Customer reaction | Next step | Outcome |
|---|---|---|---|---|
|  | Core → Pro / Growth / Tender |  |  |  |

## Final scorecard

| Metric | Target | Actual | Pass |
|---|---|---|---|
| Activation time per customer | < 15 minutes | ~1 minute (Day 0: backup 19:23:35 to smoke complete 19:24:37) | PASS (Day 0); re-verify on the new build |
| Unentitled 403s during normal Legacy use | 0 | 0 in the captured 2026-10-26 window; not captured after 11:42 | PARTIAL — log gap |
| Downgrade/upgrade data loss | 0 rows | 0 on the `eaeb2f8` staging Core/Pro/Core; the new build has not been rehearsed | PARTIAL — re-run on the new build |
| Support hours for the pilot | ≤ 2 hours | Not tracked | cannot verify |
| Upgrade demo completed | ≥ 1 | 0 | pending — not completed |
| Time to quote a bundle | < 5 minutes | not measured | pending |
| Owner walkthrough captured | yes | Completed 2026-11-09; answers pending transcription | PARTIAL |
| Two weeks without regressions | yes | New window on `a622894` is 2026-11-06 to 2026-11-20; Day 0 tests and staging rehearsal PASS; live smoke and fresh log pending | pending |

## Exit decision

- [ ] Pilot passed; keep Onzima on Legacy and begin the next customer.
- [ ] Pilot passed with follow-ups; list them below.
- [ ] Pilot failed; rollback/extend and record why.
- [x] Wait for missing items — re-baseline on the new build and complete the
  owner walkthrough transcription, upgrade demo, and 403 evidence.

Notes:

```
The initial 2026-10-21 to 2026-11-04 observation is superseded. The v2.5
observation (2026-10-26 to 2026-11-09) is also superseded because the live build
changed after `eaeb2f8`; acceptance must cover the new build once its window is
set.

Exit review 2026-11-09: machine evidence is DB integrity ok, continued use
through 2026-11-06, sales 5 -> 12, tender docs 5 -> 11, no data loss, and a
verified final backup (SHA256 43375B60...520B70). Open items before a pass:
owner walkthrough answers, one upgrade demo, and 403 evidence for 2026-10-27
onward (the local server log is stale).

Operator answers 2026-11-09: the live build changed to `a622894` on 2026-11-06;
the new observation window is 2026-11-06 to 2026-11-20. Removing the historical
`andama` account was intentional; the owner walkthrough was completed (answers
pending); the upgrade demo was not completed; support time was not tracked;
exit decision = wait for the new window and missing evidence.
```

Signed off by: ____________________  Date: __________
