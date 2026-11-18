# Operational Scripts

This folder contains active utility, verification, and smoke-testing scripts for `andama_mrfss_project`.

---

## Active Scripts

### 1. `smoke.ps1`
PowerShell smoke test verifying the app boots, responds on core routes, rejects unentitled requests, and handles auth gates.
```powershell
.\scripts\smoke.ps1
```

### 2. `dry_run_packaging.py`
Simulates packaging and entitlement dry runs against a database copy. Validates migration cleanly, seeds target bundles (Pro/Legacy/Core), tests downgrade/upgrade cycles, and checks row-count integrity.
```powershell
.\.venv\Scripts\python.exe scripts\dry_run_packaging.py --bundle pro
```

### 3. `pilot_metrics.py`
Extracts pilot metrics and logs for the Onzima Charles Drug Shop rollout, summarizing 403 entitlement denials, daily activity, and operational baseline.
```powershell
.\.venv\Scripts\python.exe scripts\pilot_metrics.py
```

### 4. `revenue_rollup.py`
Builds a read-only revenue rollup across one or more installation databases. Accepts database paths or a directory of `*.db` files, opens every source with `mode=ro` and `PRAGMA query_only` inside one read snapshot, and fails if a source hash changes or the portfolio mixes currencies.
```powershell
python scripts\revenue_rollup.py instance --format json
python scripts\revenue_rollup.py instance --format csv
python scripts\revenue_rollup.py a.db b.db --format json --days 14
```
Use this for the monthly close and the renewal queue; totals equal the sum of each installation's `flask --app run revenue report`.

Portfolio layout: keep customer databases as flat files in one directory, e.g.
`instance/customers/<slug>.db` with uploads at `instance/customers/<slug>-uploads/`.
A directory scan reads only direct `*.db` files, so nested per-customer folders
are invisible to the rollup. Example close:

```powershell
python scripts\revenue_rollup.py instance\customers --format csv |
    Set-Content -Encoding utf8 instance\reports\portfolio-2026-11.csv
```

---

> [!NOTE]
> One-off migration patches and obsolete probes have been retired to [`archive/scripts/`](../archive/scripts/).
