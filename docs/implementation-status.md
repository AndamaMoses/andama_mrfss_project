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
| Packaging and entitlements | **Done through Phase 5** | Registry, entitlements, server-side gate, launcher, Tender packaging, dry run, and runbooks are complete | Finish Phase 6 pilot observation |
| Phase 6 pilot | **In progress** | Re-baselined 2026-10-26; observation ends 2026-11-09 | Owner walkthrough, upgrade demo, final exit review |
| Owner-only security guards | **Done** | `/api/profit` and `/api/backup` require admin; regression tests added | Extend the same guard pattern if new owner-only endpoints appear |
| Persona QA harness | **P2 done; P1/P3/P4/P5 planned** | P2 golden path 16/16; P2 boundary audit 8/8; seed profiles and report template complete | Implement P1, P3, P4, and P5 scenarios |
| Browser/manual QA layer | **Not started** | Manual report template exists; Playwright is not built | Build the browser layer after the API-level scenarios stabilize |
| QA CI integration | **Not wired** | Runner is manual | Add a CI job for the automated persona suites |
| Known product gaps | **Open decisions** | Four gaps documented in the persona guide | Fix or explicitly accept each gap before a wider release |

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
| 6 — Pilot | **In progress** | Re-baselined 2026-10-26; ends 2026-11-09 |

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
| Release under observation | `v2.5.0` / `eaeb2f8` |
| Observation window | 2026-10-26 to 2026-11-09 |
| Live plan | Legacy (grandfathered) |
| Fresh 403 denials | 0 since the 2026-10-26 re-baseline |
| Live DB integrity | `ok` |
| Logins at re-baseline | 91 cumulative |
| Support tickets | 0 recorded |
| Owner walkthrough | **Pending** |
| Upgrade demo | **Pending** |
| Final exit decision | **Pending** |

**Open pilot checks:**

- Confirm that removal of the historical `andama` account was intentional.
- Complete the owner walkthrough and record the answers.
- Run the upgrade conversation on the staging install, never by changing
  Onzima’s live plan.
- Complete the 14-day observation and record the final scorecard.

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
