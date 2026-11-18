# Implementation Status

**Status snapshot:** 2026-10-27  
**Branch:** `feature/packaging`  
**Baseline commit:** `e286d7a`  
**Last verification:** `python -m pytest -q` → **234 passed**; `ruff check .` → **clean**

This is the consolidated index for current implementation work. It summarizes
status and points to the detailed records; it does not replace them.

- Detailed packaging plan: [`packaging-plan.md`](packaging-plan.md)
- Live pilot evidence: [`pilot-tracker.md`](pilot-tracker.md)
- Persona QA protocol and PMF rubric: [`user-personas-testing.md`](user-personas-testing.md)
- Historical modularization record: [`archive/modularization/IMPLEMENTATION_PLAN.md`](../archive/modularization/IMPLEMENTATION_PLAN.md)

> Do not claim product-market fit from synthetic QA alone. Pilot usage, owner
> feedback, support load, and commercial evidence remain the source for PMF
> decisions.

---

## 1. At a glance

| Workstream | Status | Current position | Next action |
|---|---|---|---|
| Modularization foundation | **Done and archived** | 14-domain package, app factory, DB/migrations, auth guards, frontend split, tests/lint/CI | No active work; preserve as the platform baseline |
| Packaging and entitlements | **Done through Phase 5** | Registry, entitlements, server-side gate, launcher, Tender packaging, dry run, and runbooks are complete | Complete the re-baselined Phase 6 observation on `a622894` |
| Phase 6 pilot | **Re-baselined — observation running** | `a622894` (2026-11-06); new window 2026-11-06 to 2026-11-20; 499 tests and staging Core/Pro/Core 15/15 each PASS | Run the live Day 0 smoke, start a fresh log, record the walkthrough answers, complete the upgrade demo, and track 403/support evidence |
| Owner-only security guards | **Done** | `/api/profit` and `/api/backup` require admin; regression tests added | Extend the same guard pattern if new owner-only endpoints appear |
| Persona QA harness | **P2 done; P1/P3/P4/P5 planned** | P2 golden path 16/16; P2 boundary audit 8/8; seed profiles and report template complete | Implement P1, P3, P4, and P5 scenarios |
| Browser/manual QA layer | **Not started** | Manual report template exists; Playwright is not built | Build the browser layer after the API-level scenarios stabilize |
| QA CI integration | **Not wired** | Runner is manual | Add a CI job for the automated persona suites |
| Known product gaps | **Open decisions** | Four gaps documented in the persona guide | Fix or explicitly accept each gap before a wider release |

### Completed foundation: modularization

Modularization is complete and archived. The original 1,356-line `app.py` was
split into 14 domain packages under `drugshop/`, with a Flask application
factory, SQLite database layer, versioned migrations, auth guards, a service
layer, and a separate frontend module set.

Phases 0–8 completed with a 154-test suite at the time, clean Ruff, 9/9 smoke,
15 frontend JS modules, and the largest Python file at 237 lines. The work was
later committed as the packaging baseline `3b085a9`; it is no longer active.
The current suite has grown to 234 tests.

The archived plan’s top status line says the work was uncommitted at the time of
writing. That is historical: the archive record marks it completed on
2026-10-19, and packaging is the active follow-up.

- Archived plan: [`archive/modularization/IMPLEMENTATION_PLAN.md`](../archive/modularization/IMPLEMENTATION_PLAN.md)
- Archive closure: [`archive/modularization/README.md`](../archive/modularization/README.md)

---

## 2. Packaging and entitlements

The phased record is in [`packaging-plan.md`](packaging-plan.md). Phase test
counts below are historical evidence from that plan; the current suite is 234
tests.

| Phase | Status | Evidence / note |
|---|---|---|
| 0 — Baseline and safety | **Done** | Commit `3b085a9`; tag `pre-packaging`; verified backup |
| 1 — Registry, schema, seed, CLI | **Done** | App registry, `002_app_entitlements.sql`, plan CLI, Pro seed |
| 2 — Enforcement and API | **Done** | Server-side endpoint map and gate; `GET /api/apps`; route-coverage test |
| 2a — Onzima grandfathering | **Done** | Non-sellable `legacy` bundle: Pro + Alerts + Tender |
| 3 — Launcher, navigation, loaders | **Done** | Apps launcher, locked tiles, upgrade modal, plan card, grouped loaders |
| 4 — Tender packaging | **Done** | Tender-only brand and auth; no pharmacy upsell leakage |
| 5 — Hardening, docs, dry run | **Done** | Dry run passed; onboarding and rollback runbooks added |
| 6 — Pilot | **Blocked — re-baseline required** | Live build changed after `eaeb2f8`; the `eaeb2f8` window is superseded. Owner walkthrough completed (answers pending); upgrade demo, support-time evidence, and 403 evidence missing |

**Definition-of-done status:** all engineering items are checked except the
two-week pilot without regressions. The pilot remains the only open item in the
packaging plan’s definition of done.

---

## 3. Access control and security

**Completed:**

- `/api/profit` is admin-only, with attendant-denial and admin-success coverage.
- `/api/backup` is admin-only, with attendant-denial and admin-success coverage.
- Existing entitlement checks still block Core installs from Patients, Finance,
  and Alerts at the API and in the UI.
- Admin is not exempt from entitlement checks.
- Route-coverage tests fail when a new non-static endpoint is neither mapped nor
  explicitly always-on.

**Evidence:**

- [`drugshop/finance/routes.py`](../drugshop/finance/routes.py)
- [`drugshop/reporting/routes.py`](../drugshop/reporting/routes.py)
- [`tests/test_finance.py`](../tests/test_finance.py)
- [`tests/test_reporting.py`](../tests/test_reporting.py)
- [`tests/test_app_gate.py`](../tests/test_app_gate.py)

The security matrix and expected `403` behavior are documented in
[`user-personas-testing.md`](user-personas-testing.md) §5.

---

## 4. Persona QA

Persona definitions are machine-readable in [`qa/personas.json`](../qa/personas.json).
The P2 executable journeys are in
[`qa/scenarios/P2-sarah.json`](../qa/scenarios/P2-sarah.json).

| Persona | Role | Plan | Journey specs | Automated status |
|---|---|---|---|---|
| **P1** — Charles Onzima | Owner / admin | Legacy | P1-J1, P1-J2, P1-N1 | **Planned** |
| **P2** — Sarah Achen | Counter attendant | Pro | P2-J1, P2-N1 | **Complete** — 16/16 golden path; 8/8 boundary |
| **P3** — Kato Ronald | Owner / admin | Core | P3-J1, P3-N1 | **Planned** |
| **P4** — Dr. Brenda Akello | Owner / admin | Growth | P4-J1, P4-N1 | **Planned** |
| **P5** — Eng. David Mukasa | Tender specialist | Tender | P5-J1, P5-N1 | **Planned** |

**P2 evidence:** [`instance/qa/run-20261026-161653/summary.md`](../instance/qa/run-20261026-161653/summary.md)
(local, Git-ignored). The run completed with 0 findings.

**Completed infrastructure:**

- Scratch database builder and live-path refusal.
- Seed profiles: `fresh`, `pharmacy_day`, `edge`, `tender`.
- Scenario runner with assertions, evidence capture, and findings.
- CLI entry points: [`scripts/qa_run.py`](../scripts/qa_run.py) and
  [`scripts/qa_seed.py`](../scripts/qa_seed.py).
- P2 smoke test: [`tests/test_qa_personas.py`](../tests/test_qa_personas.py).
- Human-readable report template: [`qa/report-template.md`](../qa/report-template.md).

**Still open:**

- P1, P3, P4, and P5 automated scenarios.
- Browser/manual execution layer.
- CI wiring for persona runs.
- A docs-contract test once the scenario catalog grows.

---

## 5. Phase 6 pilot

The pilot is tracked operationally in [`pilot-tracker.md`](pilot-tracker.md).

| Item | Current state |
|---|---|
| Release under observation | `a622894` / 2026-11-06 (the `eaeb2f8` window is superseded) |
| Observation window | 2026-11-06 to 2026-11-20 (re-baselined) |
| Live plan | Legacy (grandfathered) |
| Fresh 403 denials | Not captured for the new window; start a fresh log |
| Live DB integrity | `ok` |
| Day 0 evidence on `a622894` | 499 tests; staging Core/Pro/Core 15/15 each; business rows unchanged; live smoke pending |
| Logins | 131 at the `eaeb2f8` close; new-window count starts fresh |
| Support tickets | Not tracked |
| Owner walkthrough | Completed 2026-11-09; answers pending transcription |
| Upgrade demo | **Not completed** |
| Final exit decision | **Wait for the new window and missing evidence** |

**Open pilot checks:**

- ~~Confirm that removal of the historical `andama` account was intentional.~~
  Confirmed intentional on 2026-11-09.
- Record the completed owner walkthrough answers.
- Run the upgrade conversation on the staging install, never by changing
  Onzima’s live plan.
- Complete the live Day 0 smoke on `a622894` and start a fresh server log for
  the 2026-11-06 to 2026-11-20 window; the 499-test and staging
  Core/Pro/Core rehearsal evidence is recorded.
- Close the 403 evidence gap for the new window (the old local server log is
  stale).
- Track support time so the ≤ 2 hour target can be verified.

---

## 6. Known product gaps and decisions

These are documented in [`user-personas-testing.md`](user-personas-testing.md)
§5.3. They are not all release blockers, but each needs an explicit decision.

| Gap | Current behavior | Risk | Decision needed |
|---|---|---|---|
| Core patient export | `/api/export/patients` is always-on | Core install can export patient data without the Patients app | Gate the export by the `patients` app |
| Core dashboard refills | `/api/dashboard` includes due refill rows on every plan | Patient names/details appear on Core | Gate the refill block by `patients` |
| Tender-only `/` | `/` renders the pharmacy SPA | A Tender-only user sees an irrelevant shell | Keep JS branding or add a server redirect |
| Staff `/staff` | Page route is not role-restricted | An admin can open the staff view | Define whether this is acceptable or add a policy guard |

The profit and backup gaps found by the first P2 boundary run are **fixed** and
covered by regression tests.

---

## 7. Implementation job log

Recent implementation jobs on `feature/packaging`:

| Commit | Job |
|---|---|
| `6be82ee` | Archive the completed modularization plan and retire one-off scripts |
| `ce93579` | Restrict `/api/profit` and `/api/backup` to admins |
| `1a91000` | Add the persona QA harness, P2 scenarios, seed profiles, CLI, and tests |
| `e286d7a` | Index the persona QA guide and archived plan; update lint exclusions |

Full history, including packaging phases 0–5, is available with `git log`.

---

## 8. Verification and evidence

Run from the repository root:

```powershell
# Full test suite
python -m pytest -q

# Lint
.\.venv\Scripts\python.exe -m ruff check .

# P2 golden path and boundary audit
python scripts\qa_run.py --persona P2 --all

# Build a scratch database for manual/browser review
python scripts\qa_seed.py --profile pharmacy_day
```

**Current baseline:**

- `pytest -q`: **234 passed** on 2026-10-27.
- `ruff check .`: **clean**.
- P2: **16/16** golden path, **8/8** boundary, **0 findings**.
- Latest evidence pack: `instance/qa/run-20261026-161653/`.

QA evidence lives under `instance/qa/run-*` and is intentionally excluded from
Git by the `instance/` ignore rule. The scratch databases contain synthetic data
only. Never point the harness at `drugshop.db` or another live database.

---

## 9. Update protocol

Update this file when a workstream changes state:

1. Change the status in the relevant table.
2. Add the verification command, result, and date.
3. Add the commit hash for implementation changes.
4. Link the evidence; do not paste secrets or live customer data.
5. Keep detailed procedures in the canonical documents instead of duplicating
   them here.
6. Do not mark a persona as covered until an automated scenario or documented
   manual run exists.
7. Do not describe synthetic QA as PMF validation.
