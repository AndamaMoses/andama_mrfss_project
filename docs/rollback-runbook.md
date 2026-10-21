# Rollback runbook

Use the smallest rollback that fixes the problem. Entitlement changes never
delete business data, so an incorrect plan usually needs a CLI change, not a
database restore.

| Problem | Action |
|---|---|
| Wrong plan or missing app | Fix access with `flask --app run plan ...` |
| Launcher or UI regression after a release | Roll back the code tag |
| Migration or database corruption | Restore the verified database backup |
| Lost uploads (Tender PDFs) | Restore the uploads folder alongside the DB |

The live database is whatever `config.py` reports, which may be
`instance\drugshop.db` or the legacy root `drugshop.db`. Check before touching
anything:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -c "import config; print(config.DevConfig.DATABASE); print(config.DevConfig.UPLOAD_DIR)"
```

## 1. Access rollback (fastest, no restore)

This restores the apps without touching rows:

```powershell
flask --app run plan show
flask --app run plan set pro --actor "Andama" --notes "rollback: restore Pro access"
```

For Onzima use `plan set legacy`. For a combined pharmacy plan, restore the base
bundle and re-add Tender:

```powershell
flask --app run plan set pro --actor "Andama" --notes "rollback: restore base plan"
flask --app run plan add tender --actor "Andama" --notes "rollback: restore Tender add-on"
```

Confirm:

```powershell
flask --app run plan show
```

The app does not need a restart for an entitlement change; refresh the browser.

## 2. Code rollback

Stop the app before changing code. Commit or stash local changes first, then
check out the last known-good release tag.

For a full packaging rollback (before the apps/entitlements work):

```powershell
git status
git stash push -u -m "before rollback"
git fetch --tags
git checkout pre-packaging
python run.py
```

`pre-packaging` is the modularized baseline before the packaging phases. The
database may remain migrated: the older code ignores the additive
`app_entitlements` and `entitlement_events` tables, and no business table is
removed.

For rolling back only the latest release while keeping packaging:

```powershell
git checkout phase-4-tender
python run.py
```

Replace `phase-4-tender` with the last release tag that was verified for this
customer. Do not use a random commit from another branch. Record the rollback
tag in the customer sheet.

If the rollback is temporary, return to the release branch after the fix:

```powershell
git checkout feature/packaging
```

## 3. Database restore

Restoring a database discards everything written since that backup. If possible,
take a fresh copy of the current database first.

1. Stop the app.
2. Save the current database and uploads.
3. Restore the verified backup over the configured database path.
4. Restore uploads if they were part of the backup.
5. Verify integrity, then boot.

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -c "import config; print(config.DevConfig.DATABASE); print(config.DevConfig.UPLOAD_DIR)"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dbPath = if ($env:DRUGSHOP_DB) { $env:DRUGSHOP_DB }
          elseif (Test-Path -LiteralPath "instance\drugshop.db") { "instance\drugshop.db" }
          else { "drugshop.db" }
$uploadPath = if ($env:DRUGSHOP_UPLOADS) { $env:DRUGSHOP_UPLOADS }
              elseif ((Test-Path -LiteralPath "uploads") -and
                      (Get-ChildItem -LiteralPath "uploads" -Force | Select-Object -First 1)) { "uploads" }
              else { "instance\uploads" }
Copy-Item -LiteralPath $dbPath "instance\backups\drugshop-before-rollback-$stamp.db"
if (Test-Path -LiteralPath $uploadPath) {
    Copy-Item -LiteralPath $uploadPath "instance\backups\uploads-before-rollback-$stamp" -Recurse -Force
    Remove-Item -LiteralPath $uploadPath -Recurse -Force
}
Copy-Item -LiteralPath "instance\backups\<verified-backup>.db" $dbPath -Force
if (Test-Path -LiteralPath "instance\backups\uploads-<verified-backup>") {
    Copy-Item -LiteralPath "instance\backups\uploads-<verified-backup>" $uploadPath -Recurse -Force
}
python -c "import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute('PRAGMA integrity_check').fetchone()[0]); d.close()" $dbPath
```

> Windows PowerShell 5.1 can mis-decode non-ASCII paths printed by Python.
> The snippet uses the repository-relative defaults; if `config.py` prints a
> different path, use that exact path manually.

The integrity result must be `ok`. Compare the restored file hash with the
backup hash:

```powershell
Get-FileHash -Algorithm SHA256 $dbPath
Get-FileHash -Algorithm SHA256 "instance\backups\<verified-backup>.db"
```

Then boot once:

```powershell
python run.py
```

If the backup predates migration `002_app_entitlements.sql`, the boot will
re-apply the additive migration and seed the configured default bundle. Check:

```powershell
flask --app run plan show
```

Do not restore a backup while the app or another Python process is writing to
the database. Do not run destructive SQL by hand.

## 4. Rehearse the restore before you need it

The Phase 5 rehearsal copies the real database, migrates it, seeds a plan,
checks access, downgrades to Core, re-upgrades, restores the verified backup,
and confirms the source file is unchanged:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python scripts\dry_run_packaging.py --bundle legacy `
    --restore-backup "instance\backups\drugshop-pre-packaging-20261021-161243.db"
```

For the bundle acceptance path, run it again with `--bundle pro`. The script
never writes to `--source` or `--restore-backup`; it works in a temporary
directory and removes it unless `--keep` is passed.

The current Phase 5 verified backup is
`instance\backups\drugshop-pre-packaging-20261021-161243.db` with SHA256
`E2AEED56CF6C7ACF1D8F5C2E4838A4DACEDFF75230859638324CEB7B3A14542C`.
Use the newest backup that has been verified for the customer, not this example.

## 5. Post-rollback checks

1. `flask --app run plan show` matches the intended plan.
2. `GET /api/apps` matches the launcher.
3. Run the smoke script with the customer's plan:

   ```powershell
   $env:SMOKE_PASSWORD = "the-admin-password"
   powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Plan pro -Username admin
   ```

4. Complete one real workflow (sale, patient, or Tender analysis) as the owner.
5. Confirm row counts for the main tables match the backup or the
   pre-rollback snapshot.
6. Record what was rolled back, why, the tag, the backup path, and the time.

## 6. Escalation

If the app still fails after an access rollback and a verified data restore:

- Keep the failed database copy; do not overwrite it.
- Capture `python run.py` output, `plan show`, and `/api/apps`.
- Stop the server and leave the last known-good backup in place.
- Do not attempt a second restore over a running process.

Onboarding steps are in [onboarding-runbook.md](onboarding-runbook.md).
