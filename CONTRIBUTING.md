# Contributing

This repository is maintained for Communion Engineering Services Ltd and Onzima
Charles Drug Shop. Keep changes small, reviewable, and safe for a live shop.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -r requirements-dev.txt
python run.py
```

Use a scratch database for development:

```powershell
$env:DRUGSHOP_DB = "$PWD\instance\dev.db"
$env:DRUGSHOP_BUNDLE = "core"
python run.py
```

Never point a development server at the live shop database.

## Before opening a pull request

```powershell
python -m pytest -q
python -m ruff check .
```

If you touched routing, entitlements, or authentication, also run the smoke
script against a local instance:

```powershell
$env:SMOKE_PASSWORD = "your-local-password"
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1 -Plan core -Username admin
```

## Code layout

- Add a route to the owning domain blueprint in `drugshop/<domain>/routes.py`.
- Keep business logic in the domain `service.py`, not in templates or routes.
- Read the app catalog from `drugshop/apps/registry.py`; do not hardcode plan
  names or app IDs in JavaScript.
- Gate new business endpoints through the existing entitlement map in
  `drugshop/apps/guards.py` and add a test for both allowed and denied access.
- Do not add a dependency without a clear operational reason. The runtime is
  Flask plus `pypdf` only.

## Database and migrations

- Schema changes require a new forward-only file in `drugshop/migrations/`.
- Migrations must be additive and safe to run on a populated database.
- Never rewrite or delete an existing migration.
- Back up before running a migration on any real installation.
- Add a test in `tests/test_migrations.py` or the owning domain test file.

## Commits and branches

Use a short conventional subject:

```text
feat: add plan-aware refill reminder
fix: keep tender page usable without a pharmacy plan
docs: clarify restore rehearsal
chore: bump pypdf
```

Keep unrelated changes out of the same commit. Do not commit databases, backups,
uploads, logs, `.env` files, or real customer data.

## Reporting

- Security issues: follow [SECURITY.md](SECURITY.md), not a public issue.
- Operational incidents: use the [rollback runbook](docs/rollback-runbook.md).
