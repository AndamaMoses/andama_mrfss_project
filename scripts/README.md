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

---

> [!NOTE]
> One-off migration patches and obsolete probes have been retired to [`archive/scripts/`](../archive/scripts/).
