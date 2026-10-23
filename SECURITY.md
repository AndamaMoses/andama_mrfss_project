# Security policy

## Supported versions

Security fixes are applied to the current release line on `main`. Onzima's
production installation is the reference deployment; older branches are not
maintained.

## Reporting a vulnerability

**Do not open a public GitHub issue for a suspected vulnerability.**

Email **andamamoses42@gmail.com** with:

- a short description of the issue;
- the affected route, component, or version;
- steps to reproduce (use synthetic data, never patient or customer records);
- any suggested remediation.

You will receive an acknowledgement within three working days. Please allow
time for a fix and a coordinated disclosure before publishing details.

## Data handling

This application processes pharmacy sales, patient refill records, staff
accounts, supplier invoices, and tender documents. Treat every installation as
production data, even during a pilot.

- Never attach a real database, upload, backup, or server log to an issue,
  pull request, or chat message.
- Reproduce with the test fixtures in `tests/` or a temporary database.
- Do not commit `.db`, `.env`, backup, or upload files. They are ignored by
  default, but tracked files must still be reviewed before a push.
- Redact names and phone numbers from screenshots and diagnostics.

## Production checklist

Before exposing an installation beyond localhost:

- [ ] Set a strong, random `SECRET_KEY` from a secret store.
- [ ] Serve the app behind HTTPS and leave `FLASK_DEBUG` unset.
- [ ] Change every bootstrap password and remove accounts that are not in use.
- [ ] Put `instance/` (database, uploads, backups, logs) outside version control.
- [ ] Take a backup before every migration and rehearse the restore.
- [ ] Confirm the entitlement gate with `scripts\smoke.ps1` for the sold plan.
- [ ] Review the [onboarding](docs/onboarding-runbook.md) and
      [rollback](docs/rollback-runbook.md) runbooks with the operator.
- [ ] Keep the SQLite file on local disk with restricted filesystem permissions.

## Known constraints

- SQLite is single-writer. Do not run multiple app processes against one file;
  use the documented maintenance window for migrations and backups.
- Authentication is session-based with no external identity provider. Protect
  the host and the network path to it.
- Uploaded documents are stored on disk. Include them in the backup and restore
  rehearsal, not just the database.
