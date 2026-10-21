# Onboarding runbook

Use this checklist for every new customer and for Onzima's packaging rollout.
It assumes the app is installed in this repository and the virtual environment
is active. Run PowerShell from the repository root.

The database is **not always** at `instance\drugshop.db`. `config.py` uses
`instance\drugshop.db` when it exists, otherwise the legacy root
`drugshop.db`. Always ask the app for the real paths before copying anything:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -c "import config; print(config.DevConfig.DATABASE); print(config.DevConfig.UPLOAD_DIR)"
```

## 1. Confirm the commercial details

| Bundle | Apps | Typical customer |
|---|---|---|
| Core | POS, Inventory | New pharmacy, starter |
| Pro | Core + Patients, Finance | Established pharmacy |
| Growth | Pro + Alerts | Pharmacy that wants stock alerts |
| Tender Copilot | Tender only | Consultancy, standalone workspace |
| Combined | Pro + Tender (add-on) | Pharmacy that also bids |
| Legacy | All apps | **Onzima only**, grandfathered, not sellable |

Record the bundle, expiry date, owner name, support number, and activation date
in the customer sheet before touching the server. Expiry is informational in
v1: there is no automatic lockout.

## 2. Back up the database and uploads

Stop the app first. SQLite copies are only safe when no process is writing.

```powershell
$env:PYTHONIOENCODING = "utf-8"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dbPath = (python -c "import config; print(config.DevConfig.DATABASE)").Trim()
$uploadPath = (python -c "import config; print(config.DevConfig.UPLOAD_DIR)").Trim()
New-Item -ItemType Directory -Force instance\backups | Out-Null
Copy-Item -LiteralPath $dbPath "instance\backups\drugshop-pre-onboarding-$stamp.db"
if (Test-Path -LiteralPath $uploadPath) {
    Copy-Item -LiteralPath $uploadPath "instance\backups\uploads-pre-onboarding-$stamp" -Recurse
}
Get-FileHash -Algorithm SHA256 "instance\backups\drugshop-pre-onboarding-$stamp.db"
```

Verify the database copy before continuing:

```powershell
python -c "import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute('PRAGMA integrity_check').fetchone()[0]); d.close()" "instance\backups\drugshop-pre-onboarding-$stamp.db"
```

The result must be `ok`. Write the backup path and SHA256 hash in the customer
sheet.

## 3. Deploy and migrate

Deploy the current release, then boot once:

```powershell
python run.py
```

The boot applies any pending additive migration and seeds the configured
default bundle. New installations should set the default before first boot:

```powershell
$env:DRUGSHOP_BUNDLE = "core"
python run.py
```

Do **not** set `DRUGSHOP_BUNDLE=core` for Onzima. This installation defaults to
`legacy`, which preserves every current feature plus Tender.

Check the result:

```powershell
flask --app run plan show
```

`plan show` must display the expected bundle and app list. If it says
`unseeded`, the boot did not create the entitlement rows; fix that before
onboarding the customer.

## 4. Activate or change the plan

The app may stay running; plan changes are read on the next request. Refresh
the browser after a change.

```powershell
flask --app run plan set core   --expires 2027-10-21 --actor "Andama"
flask --app run plan set pro    --expires 2027-10-21 --actor "Andama"
flask --app run plan set growth --expires 2027-10-21 --actor "Andama"
flask --app run plan set tender --expires 2027-10-21 --actor "Andama"
```

For a pharmacy that also buys Tender, set the base bundle first and add the
add-on:

```powershell
flask --app run plan set pro --expires 2027-10-21 --actor "Andama"
flask --app run plan add tender --actor "Andama"
```

Other useful commands:

```powershell
flask --app run plan add alerts --actor "Andama"
flask --app run plan remove alerts --actor "Andama"
flask --app run plan show
```

Use `--notes "customer signed Pro, 12 months"` on the first activation so the
audit trail explains the commercial decision. Onzima is the only installation
that may use `plan set legacy`.

If you operate more than one database from the same shell, set `DRUGSHOP_DB`
to the customer's database path for **both** `python run.py` and every
`flask --app run ...` command. A mismatch is the usual cause of "I changed the
plan but the browser still shows the old one".

## 5. Verify the plan

Log in as the owner or admin and check:

1. The Apps launcher shows only entitled apps; locked tiles show the upgrade
   path.
2. The Plan & Apps card shows the bundle, active apps, expiry, and support
   link.
3. `/api/apps` returns the same plan and app flags as the launcher.
4. A normal session does not produce unexpected 403s or 500s.

Run the smoke script against the running install:

```powershell
$env:SMOKE_PASSWORD = "the-admin-password"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Plan core -Username admin
```

Use the matching plan flag for the customer:

| Plan | Smoke flag | Expected key result |
|---|---|---|
| Core | `-Plan core` | `/api/patients` 403, `/tender` redirect |
| Pro | `-Plan pro` | `/api/patients` 200, `/tender` redirect |
| Growth | `-Plan growth` | Pro access, alerts active |
| Tender only | `-Plan tender` | POS/Patients 403, `/tender` 200 |
| Legacy | `-Plan legacy` | all apps 200 |
| Combined Pro + Tender | `-Plan pro` (or omit) | patients 200, tender 200 |

With no `-Plan`, the script detects the plan from `/api/apps` and checks the
matching expectations. `SMOKE_PASSWORD` keeps the password out of shell
history; if it is unset the script uses the fresh-install bootstrap password
`admin123`. Pass `-Username` when the customer's admin username is not `admin`.

## 6. Verify one real workflow per plan

| Plan | Workflow |
|---|---|
| Core | Make a cash sale, confirm stock decreases, check the receipt |
| Pro | Add a patient, attach a sale, record an expense |
| Growth | Make the low-stock/alerts check run and open the alert list |
| Tender | Upload or open a sample tender and run an analysis |
| Legacy | One sale plus one Tender analysis; confirm both brands render |

Do not demonstrate a bundle the customer has not bought. New pharmacy demos
start on Core, not Legacy. Tender-only demos must not show pharmacy upsells.

## 7. Handover and follow-up

1. Show the owner the read-only Plan & Apps card and the support WhatsApp link.
2. Confirm the owner can log in and can see the apps they paid for.
3. Record activation time, bundle, expiry, backup path, and support contact.
4. Schedule a 30-day check-in and a renewal reminder 14 days before expiry.
5. Leave the verified backup in `instance\backups` (or the customer's own
   backup location).

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| `plan show` says unseeded | Boot once with `python run.py`; confirm migration `002` ran |
| Plan changed but UI unchanged | `flask` and the server may be using different DB paths; compare `config.DevConfig.DATABASE` in both shells |
| App returns 403 | Check `/api/apps` and `plan show`; 403 is correct for an unentitled app |
| Tender redirects to `/?upgrade=tender` | Tender is not active; use `plan add tender` for a combined plan or `plan set tender` for standalone |
| Backup integrity check fails | Stop and restore the last known-good backup; do not migrate over it |
| Smoke login fails | Use `-Username` and `SMOKE_PASSWORD` for this install; do not reuse bootstrap credentials on a live shop |

Never edit `app_entitlements` by hand. Use the CLI so the audit event is written.

For data or code rollback, use [rollback-runbook.md](rollback-runbook.md).
