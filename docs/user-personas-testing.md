# User Personas & Product Experience Testing

**Project:** andama_mrfss_project (Onzima Charles Drug Shop + Tender Copilot)  
**Date:** 2026-10-26  
**Primary reader:** building/reviewing agent and human QA  
**Purpose:** test the product as each persona experiences it, and collect the
evidence needed for product-market-fit conversations.

**Executable assets:**

| Asset | Purpose |
|---|---|
| [`qa/personas.json`](../qa/personas.json) | Machine-readable persona cards and PMF hypotheses |
| [`qa/scenarios/P2-sarah.json`](../qa/scenarios/P2-sarah.json) | P2 journeys that the runner executes today |
| [`qa/seeds.py`](../qa/seeds.py) | Synthetic seed profiles (`fresh`, `pharmacy_day`, `edge`, `tender`) |
| [`scripts/qa_seed.py`](../scripts/qa_seed.py) | Build a scratch database for manual or browser review |
| [`scripts/qa_run.py`](../scripts/qa_run.py) | Run persona scenarios and write a JSON/Markdown report |
| [`qa/report-template.md`](../qa/report-template.md) | Report template for the browser/manual layer |

**Companion documents:**

- [`docs/pilot-runbook.md`](pilot-runbook.md) — live pilot operation and exit criteria
- [`docs/pilot-tracker.md`](pilot-tracker.md) — real usage, support, and owner feedback
- [`docs/packaging-plan.md`](packaging-plan.md) — entitlements and the phased delivery record
- [`docs/business-context.md`](business-context.md) — commercial and operational background

---

## 0. How an agent uses this guide

An agent can verify that a persona can complete a job, that the UI and API agree,
and that role/plan boundaries hold. An agent **cannot** measure willingness to
pay, retention, or trust built over weeks. Keep those distinctions explicit.

### 0.1 Three review modes

| Mode | When | What the agent does | Output |
|---|---|---|---|
| **Regression review** | During development, per pull request | Run the affected persona journeys and security invariants on a scratch DB | Pass/fail plus regressions |
| **Experience audit** | Before a release or demo | Run all persona shifts, including the browser layer, and score friction | PMF readiness report with evidence |
| **PMF review** | After a pilot period | Combine the audit evidence with real login, sales, support, and owner feedback data | Persist / fix / pivot recommendation |

A green regression run is not a PMF result. It is one input.

### 0.2 Agent contract

Before the run:

- Read the persona card and the selected scenario first. Do not start from the
  route map; the experience audit must be black-box.
- Create a fresh scratch database. Never open `drugshop.db`,
  `instance/drugshop.db`, or the live pilot database.
- Record the commit, plan, seed profile, viewport, browser, and scenario version.
- Use synthetic data only. Do not paste real patient or customer data into a run.

During the run:

- Do not edit application code, tests, scenarios, or this document. A reviewer
  that can change the test can accidentally make the test pass.
- Verify the user-visible outcome **and** the database state. HTTP 200 alone is
  not success.
- Capture console errors, unexpected 4xx/5xx responses, screenshots for UI
  steps, and the time/action budget.
- Stop at the scenario budget and record the dead end. Do not improvise a
  workaround and call the journey successful.
- Use the persona's constraints: one hand, interruptions, no training, patchy
  connectivity, shared device.

After the run:

- Score every journey `pass`, `partial`, or `fail`.
- Write findings with severity, evidence, and persona impact.
- Produce a **PMF readiness** assessment. Do not declare product-market fit.
- Leave the scratch database and report in place as evidence.

### 0.3 Commands

Automated API-level run:

```powershell
# P2 golden path plus boundary checks
.\.venv\Scripts\python.exe scripts\qa_run.py --persona P2 --all

# One journey only
.\.venv\Scripts\python.exe scripts\qa_run.py --persona P2 --scenario P2-J1

# List personas and available scenarios
.\.venv\Scripts\python.exe scripts\qa_run.py --list
```

Manual/browser setup:

```powershell
# Build a clean scratch database
.\.venv\Scripts\python.exe scripts\qa_seed.py `
    --profile pharmacy_day --plan pro `
    --db instance\qa\manual-p2\drugshop.db --force

# Point the app at the scratch database (never the live one)
$env:DRUGSHOP_DB = "instance\qa\manual-p2\drugshop.db"
$env:DRUGSHOP_UPLOADS = "instance\qa\manual-p2\uploads"
$env:DRUGSHOP_BUNDLE = "pro"
.\.venv\Scripts\python.exe run.py
```

Scratch logins are `admin` / `qa-admin-pass` and `grace` / `qa-staff-pass`.
They exist only in the scratch database. Do not reuse them anywhere else.

### 0.4 Evidence and report

`scripts/qa_run.py` writes:

```text
instance/qa/run-YYYYMMDD-HHMMSS/
├── drugshop.db       # disposable scratch database
├── uploads/          # scratch uploads
├── report.json       # machine-readable steps, timings, statuses, findings
└── summary.md        # human-readable result and next actions
```

The runner exits:

- `0` — every selected check passed.
- `1` — product or contract findings; read `summary.md`.
- `2` — harness or scenario error; fix the runner or spec before trusting the run.

For the browser/manual layer, copy [`qa/report-template.md`](../qa/report-template.md)
and add screenshots, console logs, network logs, and the reviewer's friction notes.

---

## 1. Product thesis and PMF hypotheses

The product has two customers with different jobs. Do not average them into a
single "user."

| Persona | Core job | PMF hypothesis | Agent-testable proxy |
|---|---|---|---|
| **P1 Charles** | Reconcile the day and know the margin | Owner can trust the numbers enough to keep using the system | Login → saved reconciliation in under 5 minutes |
| **P2 Sarah** | Serve a customer fast and correctly | Ten sales in a row without help means the counter workflow is viable | Two-item cash sale in under 45 seconds, ≤ 8 actions |
| **P3 Kato** | Start selling on a Core plan | First-run activation under 15 minutes can convert a starter customer | First login → first completed sale in under 15 minutes |
| **P4 Brenda** | Act on refills, credit, and stock risk | A clear daily worklist makes Growth worth retaining | Due-refill list → contact → partial credit payment in under 5 minutes |
| **P5 David** | Decide whether a tender is worth bidding | A defensible bid/no-bid decision in 15 minutes makes Tender Copilot sellable | Upload → qualification summary → decision in under 15 minutes |

**What the agent can conclude:** whether the product delivers the job in a
controlled, realistic simulation, and where friction blocks adoption.

**What the agent cannot conclude:** whether customers will pay, renew, recommend
the product, or change their habits. Those come from the pilot tracker and real
owner conversations.

---

## 2. Persona cards

The machine-readable source is [`qa/personas.json`](../qa/personas.json). The
cards below are the narrative version an agent should use for role-play.

### Persona matrix

| Persona | Name | Role | Plan | Surface | Primary interface |
|---|---|---|---|---|---|
| **P1** | Charles Onzima | `admin` | `legacy` / `pro` | Desktop | `/` |
| **P2** | Sarah Achen | `attendant` | Same install (`pro` in tests) | Counter tablet | `/staff` or `/` |
| **P3** | Kato Ronald | `admin` | `core` | Desktop | `/` |
| **P4** | Dr. Brenda Akello | `admin` | `growth` | Desktop + tablet | `/` |
| **P5** | Eng. David Mukasa | `admin` | `tender` | Standalone | `/tender` |

Plan and role are different axes. Test the intersection: an admin on Core still
gets `403` for Patients; an attendant on Pro still gets `403` for owner controls.

### P1 — Charles Onzima, owner and administrator

- **Context:** Owns Onzima Charles Drug Shop in Kireka. Buys stock in Nakasero,
  extends credit to trusted local families, reconciles cash at 8:30 PM, and
  watches daily gross margin.
- **Job to be done:** When the day ends, I want to reconcile the drawer and know
  my margin without a spreadsheet, so I can trust the business and decide what
  to restock.
- **Constraints:** Back-office laptop or counter desktop; the system total must
  match the physical drawer; a backup that cannot be restored is not a backup.
- **PMF hypothesis:** If Charles can reconcile the day and explain any variance
  in under five minutes, the owner workflow is viable for a paid plan.
- **Success metrics:** Login to saved reconciliation under 5 minutes; discrepancy
  explained, not just displayed; backup downloads and opens; zero unexpected
  403s during normal Legacy use.
- **Abandonment triggers:** System total does not match counted cash and the
  cause is unclear; stock intake is slower than the paper book; backup is
  missing; a staff mistake needs the developer.
- **Shift script:** morning stock intake → midday spot check → evening
  reconciliation and expenses → backup and close.

### P2 — Sarah Achen, frontline counter attendant

- **Context:** Serves 80+ customers a day on a shared counter tablet. Needs fast
  search, correct stock, receipt printing, and no access to owner-only controls.
- **Job to be done:** When a customer asks for a drug, I want to find it, confirm
  price and stock, take payment, and hand over a receipt in under 30 seconds, so
  the queue keeps moving.
- **Constraints:** One hand, interruptions, patchy connectivity, no training.
  Cannot see cost, profit, user management, or delete records.
- **PMF hypothesis:** If Sarah can complete ten sales in a row without help and
  never encounters an owner-only surface, the counter workflow is viable for a
  pilot.
- **Success metrics:** First sale within 30 seconds of login; two-item cash sale
  in 45 seconds and at most 8 user actions; correct receipt; stock reduced by the
  sold quantity; zero unexpected 403s; no owner-only endpoint reachable.
- **Abandonment triggers:** Search over 3 seconds; ambiguous stock or price;
  unclear payment step; error with no next action; an admin screen appears or an
  owner-only action succeeds.
- **Shift script:** sign in → serve a rush of mixed cash/mobile-money sales →
  answer stock queries → reprint a receipt and check "My Sales" → sign out
  without exposing owner data.

### P3 — Kato Ronald, single-counter owner on Core

- **Context:** Bought the starter Core plan: POS and inventory. Did not buy
  Refill Care, Finance, Alerts, or Tender. Expects a clean first-run setup and a
  clear upgrade path, not a broken or empty shell.
- **Job to be done:** When I buy the starter plan, I want to be selling within
  fifteen minutes without training, so I do not lose a day setting up.
- **Constraints:** Empty database on first login; no paid modules; cannot pay for
  an upgrade until the value is clear.
- **PMF hypothesis:** If Kato can add stock and complete a first sale within
  fifteen minutes, and can explain what an upgrade unlocks, Core can convert.
- **Success metrics:** First login to first sale under 15 minutes; locked apps
  explain what they do and which plan includes them; no crashes, console 403s,
  or dead ends; upgrade prompt names the correct bundle and support contact.
- **Abandonment triggers:** Empty dashboard with no next step; locked tile does
  nothing; product setup needs developer help; upgrade path is unclear or pushes
  an irrelevant add-on.
- **Shift script:** first login on empty Core → add product and batch → first
  sale → hit a locked feature → understand and demonstrate the upgrade.

### P4 — Dr. Brenda Akello, growing clinic pharmacy

- **Context:** Runs a high-volume dispensary with three staff, 150 chronic
  refill patients, credit lines, and stock alerts.
- **Job to be done:** When refills and credit are due, I want one list that tells
  me who to contact and what they owe, so I do not lose repeat customers.
- **Constraints:** Three staff on one install; refill/credit work competes with
  counter service; alerts must be actionable, not noisy.
- **PMF hypothesis:** If Brenda can clear the due-refill list and reconcile a
  credit payment in under five minutes, Growth provides enough recurring value
  to retain.
- **Success metrics:** Due and overdue refills visible with contact action;
  credit balance correct after a partial payment; low-stock and expiry alerts
  specific and logged; no patient data leaks to unentitled plans or roles.
- **Abandonment triggers:** Refill list is wrong or misses a patient; credit
  balance is wrong after a payment; alert log is empty or not actionable;
  patient data appears in a Core install or to an attendant.
- **Shift script:** review refill due list → contact a due patient → credit sale
  and partial payment → review low-stock/expiry alerts → verify the alert log.

### P5 — Eng. David Mukasa, tender specialist

- **Context:** Lead engineer at Communion Engineering Services in Jinja. Uses
  Tender Copilot to decide whether PPDA/UNRA tenders are worth bidding.
- **Job to be done:** When a tender lands, I want to know if we qualify and what
  to fix before the deadline, so I do not waste bid effort.
- **Constraints:** No pharmacy inventory or POS; deadlines are short; output must
  be defensible to a client or bid committee.
- **PMF hypothesis:** If David can reach a defensible bid/no-bid decision in under
  fifteen minutes, Tender Copilot can be sold as a standalone workspace.
- **Success metrics:** Upload to qualification summary under 15 minutes;
  compliance gaps and risks specific and readable; methodology export usable in
  a bid; no pharmacy navigation or branding in the standalone workspace.
- **Abandonment triggers:** Analysis is generic or unsupported; no clear bid/no-bid
  recommendation; pharmacy clutter appears; upload or analysis is too slow.
- **Shift script:** receive tender → upload and analyze → review compliance and
  risks → make bid/no-bid decision → export methodology.

---

## 3. Shift simulations and journey specs

Test a believable **shift**, not an isolated feature. A feature can return 200
while the persona still cannot finish their day.

### 3.1 Scenario catalog

| ID | Persona | Scenario | Status | Budget |
|---|---|---|---|---|
| `P1-J1` | P1 | Morning stock intake and batch entry | Planned | 3 min |
| `P1-J2` | P1 | Evening reconciliation and discrepancy explanation | Planned | 5 min |
| `P1-N1` | P1 | Last-admin protection and backup integrity | Planned | 2 min |
| `P2-J1` | P2 | Rush-hour two-item cash sale with receipt | **Implemented** | 45 sec |
| `P2-N1` | P2 | Attendant cannot reach owner-only controls | **Implemented** | 20 sec |
| `P3-J1` | P3 | First-run Core: product → batch → first sale | Planned | 15 min |
| `P3-N1` | P3 | Core entitlement boundary and upgrade prompt | Planned | 3 min |
| `P4-J1` | P4 | Refill due list, credit sale, partial payment | Planned | 5 min |
| `P4-N1` | P4 | Patient-data boundary across role and plan | Planned | 3 min |
| `P5-J1` | P5 | Tender upload → qualification → bid/no-bid | Planned | 15 min |
| `P5-N1` | P5 | Tender-only branding and pharmacy isolation | Planned | 3 min |

Executable scenarios live in [`qa/scenarios/`](../qa/scenarios). Add one JSON file
per persona, using the schema in Appendix B.

### 3.2 P2-J1 — Two-item cash sale

**Preconditions:** Plan `pro`, seed `pharmacy_day`, user `grace`, counter tablet.

**User-level steps:**

1. Sign in as Sarah.
2. Search "Paracetamol" and add two units.
3. Search "ORS" and add one sachet.
4. Choose Cash and complete the sale.
5. Open the receipt.

**Expected outcome:**

- Sale returns `201` with a receipt reference.
- Receipt total is UGX 1,400 and itemizes two lines.
- Receipt carries the shop name and `served_by=grace`.
- Paracetamol stock falls by exactly two units.
- Sarah can see her own sales without seeing shop-wide reports.
- Budget: 45 seconds, at most 8 user actions.

**Automated check:**

```powershell
.\.venv\Scripts\python.exe scripts\qa_run.py --persona P2 --scenario P2-J1
```

**Evidence:** `report.json` step excerpts, receipt total, DB before/after stock.

### 3.3 P2-N1 — Attendant boundary

**Expected:**

| Request | Expected |
|---|---|
| `GET /api/settings` | `200` (read-only settings needed by the counter) |
| `GET /api/users` | `403` |
| `POST /api/users` | `403` |
| `POST /api/settings` | `403` |
| `GET /api/staff-activity` | `403` |
| `GET /api/profit` | `403` |
| `GET /api/backup` | `403` |

**Current result:** all eight checks pass. The first audit found that
`GET /api/profit` and `GET /api/backup` returned `200` for an attendant. Both
routes now require an admin role and are covered by regression tests in
`tests/test_finance.py` and `tests/test_reporting.py`.

**Automated check:**

```powershell
.\.venv\Scripts\python.exe scripts\qa_run.py --persona P2 --scenario P2-N1
```

### 3.4 P3-J1 — First-run activation

Start on an empty Core database. Do not read the code or the setup docs; use the
persona's knowledge only. Measure from first login to first completed sale.

Expected: a visible next step on the empty dashboard; add product and batch
without developer language; first sale succeeds; locked tiles explain the plan
needed; upgrade prompt names the correct bundle and a support contact. Target:
under 15 minutes. This is the activation metric already used in the pilot
tracker.

### 3.5 P1-J2 — Evening reconciliation

Use the seeded day's sales and expenses. Count the drawer, calculate the
discrepancy, save the reconciliation, and explain the result in one sentence.
Target: under 5 minutes. A mismatch that the owner cannot explain is a P1
finding even if the arithmetic is correct.

### 3.6 P4-J1 — Refill and credit loop

Register or open a chronic patient, make a credit sale, record a partial cash
payment, and confirm the remaining balance. Then open the refill due list and
identify who needs contact today. Target: under 5 minutes. A wrong balance or a
missed patient is a P1 finding.

### 3.7 P5-J1 — Tender bid/no-bid

Use the `tender` seed profile. Upload the sample UNRA document, review the
compliance matrix and risk flags, make a bid/no-bid decision, and draft the
methodology. Target: under 15 minutes. Generic output or a missing gap that the
document clearly states is a P1 finding.

---

## 4. PMF proxy scorecard

Score each dimension `0`, `1`, or `2`:

- `2` — persona completed the job without help or friction.
- `1` — completed with friction, workaround, or hesitation.
- `0` — blocked or gave up.

| Dimension | Evidence | Target |
|---|---|---|
| **Time to first value** | Login → first completed job | P2 < 30 sec; P3 < 15 min; P1/P4 < 5 min; P5 < 15 min |
| **Core task completion** | Journey pass/fail | Every P1 journey passes |
| **Friction events** | Dead ends, ambiguous labels, extra steps | 0 critical; ≤ 2 minor per shift |
| **Mistake recovery** | Wrong quantity, void, partial payment | Persona can recover without an admin |
| **Data trust** | Stock, sale, receipt, credit agree everywhere | No stale or contradictory values |
| **Plan clarity** | Persona can explain current plan and upgrade | Yes, without help |
| **Mobile viability** | Key actions at 390×844 | No horizontal scroll; tap targets usable |
| **Support dependence** | Did the reviewer need code/docs to finish? | No |

Use the result to write a **PMF readiness** statement:

- **READY** — the persona can do the core job and the value is clear.
- **CLOSE** — the job completes, but friction or a data-trust issue would block
  adoption.
- **NOT READY** — the persona cannot complete the core job or cannot understand
  what to do next.

The pilot tracker remains the source for actual PMF evidence: logins, sales,
support hours, upgrade conversations, and owner feedback.

---

## 5. Security and entitlement invariants

These checks are separate from the experience audit. They must pass before a
release is considered safe.

### 5.1 Expected status matrix

| Test case | Actor | Action | Expected status |
|---|---|---|---|
| Unauthenticated API | Anonymous | `GET /api/products` | `401` |
| Public whitelist | Anonymous | `GET /api/personas` | `200` (public profile cards) |
| Login | Anonymous | `POST /api/login` | `200` or `401` on invalid password |
| Staff reads settings | `grace` | `GET /api/settings` | `200` |
| Staff writes settings | `grace` | `POST /api/settings` | `403` |
| Staff lists users | `grace` | `GET /api/users` | `403` |
| Staff creates user | `grace` | `POST /api/users` | `403` |
| Staff views staff activity | `grace` | `GET /api/staff-activity` | `403` |
| Staff views profit | `grace` | `GET /api/profit` | `403` |
| Staff downloads backup | `grace` | `GET /api/backup` | `403` |
| Core accesses Patients | `admin` (`core`) | `GET /api/patients` | `403 app not entitled` |
| Core accesses Profit | `admin` (`core`) | `GET /api/profit` | `403 app not entitled` |
| Pro accesses Alerts | `admin` (`pro`) | `GET /api/alerts/low-stock` | `403 app not entitled` |
| Growth accesses Alerts | `admin` (`growth`) | `GET /api/alerts/low-stock` | `200` |
| Tender-only accesses POS | `admin` (`tender`) | `GET /api/sales` | `403 app not entitled` |
| Core exports patients | `admin` (`core`) | `GET /api/export/patients` | `403 app not entitled` — **currently 200; see 5.3** |

### 5.2 How to read a denial

The entitlement gate returns:

```json
{
  "error": "app not entitled",
  "app": "patients",
  "message": "Refill Care is not included in your plan.",
  "upgrade": {"bundle": "pro"}
}
```

The role guard returns:

```json
{"error": "admin only"}
```

The auth gate returns:

```json
{"error": "login required"}
```

A `403` alone is not enough evidence. Record which guard produced it and whether
the payload matches the persona's plan and role.

### 5.3 Known gaps and product decisions

The remaining known gaps and decisions are below. The profit and backup gaps
found by the first P2-N1 run are fixed and covered by
`tests/test_finance.py` and `tests/test_reporting.py`.

| Gap | Current behavior | Risk | Decision |
|---|---|---|---|
| Core patient export | `/api/export/patients` is always-on | Core install can export patient data without the Patients app | Gate the export by the `patients` app |
| Core dashboard refills | `/api/dashboard` includes due refill rows on every plan | Patient names/details appear on Core | Gate the refill block by `patients` |
| Tender-only `/` | `/` renders the pharmacy SPA | A tender-only user can see an irrelevant shell | Keep JS branding or add a server redirect; document the real behavior |
| Staff `/staff` | Page route is not role-restricted | An admin can open the staff view | Acceptable unless the view exposes owner data; define the policy |

The automated matrix is in [`tests/test_app_gate.py`](../tests/test_app_gate.py),
[`tests/test_auth.py`](../tests/test_auth.py), and
[`tests/test_reporting.py`](../tests/test_reporting.py). Extend those tests when a
gap is fixed; do not only update this document.

---

## 6. Test environments and data

### 6.1 Scratch database rule

Every persona run gets its own database. The plan is installation-scoped; two
personas with different plans cannot share one database at the same time.

```text
instance/qa/
├── manual-p1/
├── manual-p2/
├── manual-p3/
└── run-YYYYMMDD-HHMMSS/
```

`scripts/qa_run.py` refuses the known live paths. `scripts/qa_seed.py` also
refuses paths outside `instance/qa` or the system temp directory. If a command
fails with a refusal, do not bypass it; create a scratch directory instead.

### 6.2 Seed profiles

| Profile | Contents | Use for |
|---|---|---|
| `fresh` | Empty business tables, default users, plan only | First-run, activation, empty-state quality |
| `pharmacy_day` | 10 products, batches, 3 patients, 9 demo sales, expenses | P1/P2 normal-day journeys |
| `edge` | `pharmacy_day` + overdue refill, zero stock, near-expiry stock, second FEFO batch, credit customer | Error recovery, expiry, FEFO, long names |
| `tender` | One sample UNRA tender document, no pharmacy data | P5 standalone journeys |

Commands:

```powershell
.\.venv\Scripts\python.exe scripts\qa_seed.py --profile fresh --plan core
.\.venv\Scripts\python.exe scripts\qa_seed.py --profile pharmacy_day --plan pro
.\.venv\Scripts\python.exe scripts\qa_seed.py --profile edge --plan growth
.\.venv\Scripts\python.exe scripts\qa_seed.py --profile tender --plan tender
```

### 6.3 Plan and role matrix

| Plan | Apps | Persona | Notes |
|---|---|---|---|
| `core` | POS, Inventory | P3 | Dashboard is always on |
| `pro` | Core + Patients, Finance | P1, P2 | Use for normal pharmacy journeys |
| `growth` | Pro + Alerts | P4 | Alerts require Patients and Finance |
| `tender` | Tender only | P5 | No pharmacy apps |
| `legacy` | Everything | P1 | Grandfathered Onzima install only |
| Empty table | Fail-open all apps | Edge | Do not use for sales demos |

### 6.4 Devices and network

| Surface | Viewport | What to check |
|---|---|---|
| Desktop | 1440×900 | Full workspace, tables, keyboard use |
| Counter tablet | 1024×768 | Touch targets, landscape, sidebar collapse |
| Phone | 390×844 | Bottom navigation, one-handed sale, receipt readability |
| Network | Normal and throttled 3G | Search time, loading state, retry behavior |

The API runner does not measure browser layout or network time. Use the manual
template for that layer.

### 6.5 Synthetic data rules

- Use invented names, phone numbers, and amounts from `qa/seeds.py` or the demo
  seed. Never copy live patient or customer data into a report.
- Keep the scratch DB and uploads under `instance/qa` so they remain gitignored.
- Record the seed profile and DB SHA256 in the report.
- If a run needs a new state, add a seed profile or a scenario; do not hand-edit
  the live database.

---

## 7. Reporting, severity, triage

### 7.1 Severity

| Severity | Meaning | Examples |
|---|---|---|
| **P0** | Data loss, security exposure, unusable install | Backup exposes the database; a sale loses stock; restore fails |
| **P1** | Blocks the persona's core job or a paid boundary | Sarah cannot complete a sale; owner-only data is reachable; reconciliation is wrong |
| **P2** | Friction, ambiguity, slow path | Search is slow; receipt summary is unclear; upgrade copy confuses |
| **P3** | Polish | Spacing, copy, non-blocking visual issue |

A P0 or P1 blocks a release. P2s need an owner and a date. P3s can ship with a
ticket.

### 7.2 Required report fields

Every review needs:

- Commit, plan, seed, persona, viewport, browser, and scenario version.
- Journey result and the user-visible evidence.
- API status, DB state, and console/network evidence where relevant.
- Friction log with persona impact.
- PMF readiness score, not a PMF claim.
- Recommended actions with severity and owner.

### 7.3 Triage flow

1. Is the expected behavior written in the registry, route guard, or this guide?
2. If the code is wrong, fix the code and add a regression test.
3. If the guide is wrong, fix the guide and record why.
4. If the behavior is intentional, record it as an accepted risk with an owner
   and review date.
5. Add or update a scenario so the issue cannot disappear silently.

Do not let the reviewer both change the product and declare the review passed.

### 7.4 Current P2 evidence

The P2 evidence now shows:

- `P2-J1` — pass, 16/16 checks; sale, receipt, attribution, stock delta, and
  "My Sales" all correct.
- `P2-N1` — pass, 8/8 checks; owner-only profit and backup access is denied to
  an attendant.

The first P2-N1 audit found that `GET /api/profit` and `GET /api/backup`
returned `200` for an attendant. Both routes now require an admin role, and the
regression tests keep the boundary closed.

---

## 8. Feedback loop and maintenance

### 8.1 During development

- Every change names the personas it affects.
- Run the affected scenario on a scratch database.
- Attach the report to the pull request.
- A P0/P1 regression blocks merge.
- Every bug found in a persona journey gets a regression check or a scenario.

### 8.2 Before a release

- Run all implemented persona scenarios.
- Run the browser/manual checklist for the UI-only claims.
- Run the security invariant tests and the deployment smoke script.
- Attach the evidence pack: reports, screenshots, console/network logs, DB hash.
- Do not call the release PMF-validated; call it ready for the next pilot
  evidence cycle.

### 8.3 After the pilot

Use [`docs/pilot-tracker.md`](pilot-tracker.md) and
[`scripts/pilot_metrics.py`](../scripts/pilot_metrics.py) for real evidence:

- Logins and distinct active users.
- Sales, stock changes, refills, and credit activity.
- 403 denials during normal use.
- Support tickets and time spent.
- Owner walkthrough answers and the upgrade conversation.

Then update the persona cards with what was actually observed. If the owner
describes a workaround, add it to the shift script. If a support ticket repeats,
add a scenario. Personas are hypotheses until real users confirm them.

### 8.4 Drift control

- Keep persona and scenario IDs stable. Add new IDs; do not renumber silently.
- `qa/personas.json` is the machine-readable headcount; this document is the
  narrative. If they disagree, the JSON and tests win, and the document is fixed.
- Add a docs-contract test when the scenario count grows: every persona and
  scenario ID referenced here must exist in the JSON specs.
- Review the persona set after each pilot or pricing change.

---

## Appendix A — CLI cheat sheet

```powershell
# List personas and scenarios
.\.venv\Scripts\python.exe scripts\qa_run.py --list

# P2 golden path and boundary audit
.\.venv\Scripts\python.exe scripts\qa_run.py --persona P2 --all

# Build a scratch database for browser review
.\.venv\Scripts\python.exe scripts\qa_seed.py --profile pharmacy_day --plan pro `
    --db instance\qa\manual-p2\drugshop.db --force

# Inspect the current plan (scratch DB only)
$env:DRUGSHOP_DB = "instance\qa\manual-p2\drugshop.db"
.\.venv\Scripts\python.exe -m flask --app run plan show

# Run the automated suite
.\.venv\Scripts\pytest -q

# Deployment smoke (against a running server, not the scratch DB)
$env:SMOKE_PASSWORD = "the-admin-password"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Plan pro -Username admin
```

---

## Appendix B — Scenario schema

`qa/scenarios/<persona>-<slug>.json`:

```json
{
  "persona": "P2",
  "version": 1,
  "scenarios": [
    {
      "id": "P2-J1",
      "name": "Two-item cash sale",
      "seed": "pharmacy_day",
      "plan": "pro",
      "budget_seconds": 45,
      "ux_actions": 7,
      "budget_actions": 8,
      "continue_on_failure": false,
      "steps": [
        {"action": "login", "label": "Sign in as Sarah"},
        {"action": "lookup_product", "name": "Paracetamol 500mg"},
        {"action": "sell", "items": [{"product_name": "Paracetamol 500mg", "qty": 2}],
         "payment_method": "CASH", "save": {"receipt_ref": "receipt_ref"}},
        {"action": "http", "method": "GET", "path": "/api/receipts/{receipt_ref}",
         "expect_status": 200},
        {"action": "assert_json", "path": "total", "equals": 400}
      ]
    }
  ]
}
```

Supported actions:

| Action | Purpose |
|---|---|
| `login` | Sign in as the persona using the scratch password |
| `lookup_product` | Read `/api/products`, find a product, and save it in context |
| `sell` | Post a cart to `/api/sales/cart` with product names resolved to IDs |
| `http` | Call any route with a method, JSON body, expected status, and optional save map |
| `assert_json` | Assert a path in the last JSON response (`equals`, `contains`, `length`, `length_gte`, `gte`, `lte`, `in`) |
| `assert_context` | Assert a saved context value |
| `db` | Run a read-only SQL check and optionally save the scalar result |
| `assert_delta` | Compare two saved numeric context values |
| `note` | Add a reviewer note to the step trace |

Use `continue_on_failure: true` for independent boundary checks. Leave it false
for a golden path so a broken sale does not produce a cascade of receipt errors.

---

## Appendix C — Implementation status

| Area | Status |
|---|---|
| Persona cards for P1–P5 | Complete in `qa/personas.json` and this document |
| P2 automated golden path | Complete; 16/16 checks pass |
| P2 automated boundary audit | Complete; 8/8 checks pass after the profit/backup guards |
| P1/P3/P4/P5 automated scenarios | Planned; cards and journey specs exist |
| Seed profiles | Complete: `fresh`, `pharmacy_day`, `edge`, `tender` |
| Browser/manual report | Template complete; Playwright layer not built |
| CI integration | Not yet wired; run `qa_run.py` manually or add a job |
| Docs-contract test | Planned when scenario count grows |

Until the remaining scenarios exist, an agent should use the persona cards and
journey specs to run the browser/manual checklist. Do not claim that a persona is
covered merely because the card exists.
