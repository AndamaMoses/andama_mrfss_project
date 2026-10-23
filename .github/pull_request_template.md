## Summary

<!-- What changed and why? Keep it to a few sentences. -->

## Scope

- [ ] Pharmacy workspace
- [ ] Tender Copilot
- [ ] Entitlements / plans
- [ ] Data model or migration
- [ ] Documentation or tooling only

## Verification

- [ ] `python -m pytest -q` passes
- [ ] `python -m ruff check .` passes
- [ ] Smoke check run for the affected plan (routing, auth, or entitlements)
- [ ] Manually checked the affected screen on desktop and mobile

## Data safety

- [ ] No database, upload, backup, log, or `.env` file is included
- [ ] Migration is additive and safe on a populated database
- [ ] No real patient, customer, or staff data appears in tests or screenshots

## Notes for the reviewer

<!-- Rollback considerations, follow-up work, or deployment notes. -->
