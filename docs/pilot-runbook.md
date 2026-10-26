# Pilot runbook — Onzima + Tender Copilot

Phase 6 is a two-week observation, not a feature release. Onzima stays on the
non-sellable **Legacy** plan (Pro + Alerts + Tender) for the whole pilot. Do not
announce bundles, show a price sheet, or remove any feature during this period.

- Pilot window: Day 0 + 14 days
- Initial Day 0: 2026-10-21
- Current observation: 2026-10-26 to 2026-11-09 (re-baselined after v2.5.0)
- Owner: Charles Onzima
- Operator: Andama
- Release: `v2.5.0` / code commit `eaeb2f8`
- Rollback: [rollback-runbook.md](rollback-runbook.md)

Record every step in [pilot-tracker.md](pilot-tracker.md).

If the deployed code changes during the pilot, restart the observation clock,
archive the old log, update the release and dates above, and update the tracker.
Do not carry 403 counts or smoke evidence across builds.

## 1. Day 0 pre-flight

Confirm the release and paths:

```powershell
git log --oneline -1
$env:PYTHONIOENCODING = "utf-8"
python -c "import config; print(config.DevConfig.DATABASE); print(config.DevConfig.UPLOAD_DIR)"
```

The live database is usually the legacy root `drugshop.db`, but always use the
path printed by `config.py`. Stop the app before copying SQLite.

Create a fresh pre-pilot backup and verify it:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dbPath = if ($env:DRUGSHOP_DB) { $env:DRUGSHOP_DB }
          elseif (Test-Path -LiteralPath "instance\drugshop.db") { "instance\drugshop.db" }
          else { "drugshop.db" }
$uploadPath = if ($env:DRUGSHOP_UPLOADS) { $env:DRUGSHOP_UPLOADS }
              elseif ((Test-Path -LiteralPath "uploads") -and
                      (Get-ChildItem -LiteralPath "uploads" -Force | Select-Object -First 1)) { "uploads" }
              else { "instance\uploads" }
New-Item -ItemType Directory -Force instance\backups,instance\pilot | Out-Null
Copy-Item -LiteralPath $dbPath "instance\backups\drugshop-pre-pilot-$stamp.db"
if (Test-Path -LiteralPath $uploadPath) {
    Copy-Item -LiteralPath $uploadPath "instance\backups\uploads-pre-pilot-$stamp" -Recurse
}
Get-FileHash -Algorithm SHA256 "instance\backups\drugshop-pre-pilot-$stamp.db"
python -c "import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute('PRAGMA integrity_check').fetchone()[0]); d.close()" "instance\backups\drugshop-pre-pilot-$stamp.db"
```

> Windows PowerShell 5.1 can mis-decode non-ASCII paths printed by Python.
> Use the repository-relative defaults above, or type the printed path manually.

Save the baseline metrics before the migration:

```powershell
python scripts\pilot_metrics.py --json | Out-File -Encoding utf8 instance\pilot\baseline.json
python scripts\pilot_metrics.py
```

## 2. Deploy the pilot

Onzima must seed as **Legacy**. The default is already `legacy`; set it
explicitly so the intent is clear.

```powershell
$env:DRUGSHOP_BUNDLE = "legacy"
python run.py *>> instance\pilot\server.log
```

Keep that terminal open: `run.py` is the server. If the server is restarted in
the background, redirect both standard output and standard error to the pilot
log, then prove the log is fresh by loading `/login` and checking that a new
request line appears:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/login | Out-Null
Get-Content instance\pilot\server.log -Tail 5
```

A log whose last request predates the current server process is stale and must
not be used for 403 evidence.

In a second terminal, verify:

```powershell
flask --app run plan show
$env:SMOKE_PASSWORD = "the-admin-password"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Plan legacy -Username admin
python scripts\pilot_metrics.py --log instance\pilot\server.log
```

Expected:
- `plan show` reports Legacy with POS, Inventory, Patients, Finance, Alerts,
  and Tender.
- Smoke reports every check `[OK]`.
- The launcher shows all apps, including Tender.
- Business row counts match the pre-pilot metrics.
- `/api/apps` reports `bundle: "legacy"` and all app flags true.

If `plan show` reports `unseeded`, stop and check the server log. Do not continue
until the plan is seeded.

## 3. Rehearse a Core demo install

This is separate from the live shop. Use a fresh staging database and a second
port. Open a new terminal and set the staging paths:

```powershell
$stage = Join-Path (Get-Location) "instance\staging-core"
New-Item -ItemType Directory -Force "$stage\uploads" | Out-Null
$env:DRUGSHOP_DB = "$stage\drugshop.db"
$env:DRUGSHOP_UPLOADS = "$stage\uploads"
$env:DRUGSHOP_BUNDLE = "core"
python -c "from run import app; from drugshop.db import init_db; from drugshop.auth.service import ensure_admin; from drugshop.apps.service import ensure_entitlements; init_db(); ensure_admin(); print(ensure_entitlements(app.config['DEFAULT_BUNDLE']))"
flask --app run run --port 5001
```

In another terminal, run the Core smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Base http://127.0.0.1:5001 -Plan core
```

Then rehearse the plan changes **against the staging database only**:

```powershell
$stage = Join-Path (Get-Location) "instance\staging-core"
$env:DRUGSHOP_DB = "$stage\drugshop.db"
$env:DRUGSHOP_UPLOADS = "$stage\uploads"
flask --app run plan set pro --actor "Andama" --notes "pilot staging upgrade rehearsal"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Base http://127.0.0.1:5001 -Plan pro
flask --app run plan set core --actor "Andama" --notes "pilot staging downgrade rehearsal"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Base http://127.0.0.1:5001 -Plan core
```

Confirm the staging row counts are unchanged after both changes. Load demo data
once through `POST /api/seed` (admin only) if the Core demo needs sample
products for the owner walkthrough.

Run this rehearsal on the same release as the live pilot. Repeat it after a
build change and record the new release in the tracker. Never treat a rehearsal
from an older build as evidence for the current build.

Stop the staging server when finished. Never point `DRUGSHOP_DB` at the
production database while rehearsing a downgrade.

## 4. Fifteen-minute owner walkthrough

Keep the demo on the plan the owner already has. Do not open the upgrade modal.

| Time | Focus | Ask |
|---|---|---|
| 0:00–0:03 | Login, launcher, Plan & Apps card | Is anything missing or confusing? |
| 0:03–0:08 | POS sale, receipt, stock deduction | Is this how your counter works? |
| 0:08–0:11 | Inventory, expiries, patients/refills | Which screen would staff use most? |
| 0:11–0:14 | Tender Copilot: open a sample analysis | Is the brand and output clear? |
| 0:14–0:15 | Support link and questions | What should we fix before day 14? |

Capture the answers verbatim in the tracker. Do not promise a feature or a
discount during the walkthrough.

## 5. Daily observation

Once a day (or every second day), run:

```powershell
python scripts\pilot_metrics.py --log instance\pilot\server.log
```

Record in the daily log:
- total logins and distinct users;
- 403 denials, especially `app access denied` lines;
- support tickets and time spent;
- one owner comment or observation;
- any browser console error, failed sale, or missing screen.

A 403 on an unentitled endpoint is expected only when someone calls it directly.
A 403 during normal Legacy use is a regression; capture the endpoint and send it
through the rollback/access path.

## 6. Upgrade conversation

At the end of the pilot, demonstrate one upgrade path on the **staging** install,
not on Onzima's live plan:

1. Core → Pro: patients and finance appear, data remains.
2. Pro → Growth: alerts appear.
3. Tender standalone: the pharmacy shell is hidden and the Tender brand remains.

Record the customer's reaction and next step in the tracker. One completed
upgrade demo is a Phase 6 acceptance item; a closed sale is not required in the
first two weeks.

## 7. Exit criteria

The pilot passes when all are true:

- 14 days without a regression in POS, Inventory, Patients, Finance, Alerts, or
  Tender.
- Zero unentitled 403s during normal Legacy use.
- No data loss after the staging downgrade/upgrade rehearsal.
- Support time is at most 2 hours for the pilot period.
- The owner walkthrough questions are captured and triaged.
- One upgrade demo is completed and recorded.
- A final backup is verified and the tracker is closed.

If a criterion fails, use the [rollback runbook](rollback-runbook.md) and extend
the observation window rather than declaring the pilot complete.
