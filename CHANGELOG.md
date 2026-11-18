# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions track the
product release shown on the sign-in screen.

## [Unreleased]

### Added

- Production `wsgi.py` entry point with an idempotent schema, account, plan, and
  demo-data bootstrap for Gunicorn.
- Render Blueprint (`render.yaml`), `requirements-prod.txt`, and a deployment
  guide for a free public demo with synthetic data.
- `ADMIN_PASSWORD` / `STAFF_PASSWORD` first-boot overrides so hosted installs
  never start with the documented development passwords.
- Operator billing ledger: subscription activation, setup and monthly invoices,
  manual payments with balances, a payment ledger view and invoice voiding, and
  a 14-day renewal queue under `flask --app run revenue ...`. Invoice
  numbering and payment checks take a SQLite writer lock, and partial unique
  indexes block duplicate setup invoices and duplicate monthly periods.
- Read-only Plan & Apps subscription card with plan, renewal, monthly fee,
  balance, and an admin-only invoice ledger, backed by `/api/subscription`.
  There are no write, payment, or self-service upgrade endpoints; the support
  CTA is configuration-driven and stays hidden when `SUPPORT_WHATSAPP` is blank.
- Monthly revenue report (`flask --app run revenue report --format
  text|json|csv`) with MRR, setup and monthly invoiced amounts, collections,
  outstanding balance, plan mix, renewals, and grandfathered/excluded rows.
  The report opens the database read-only, records the `as_of` date, and is
  verified byte-identical before and after a run.
- Read-only portfolio rollup (`scripts/revenue_rollup.py`) across database paths
  or a directory; every source is opened read-only in one snapshot and
  hash-checked before and after the read. A mixed-currency portfolio is
  rejected instead of summed.
- Monthly-close and renewal-reminder checklists, plus onboarding and rollback
  runbook updates for the billing CLI.
- `SUPPORT_WHATSAPP` pilot destination configured; the number is supplied
  through the environment and is never committed.

### Security

- `ProdConfig` marks session cookies `Secure`; bootstrap logs no longer print
  account passwords.

## [2.5.0] — 2026-10-21

Sign-in recovery and the pine/brass palette.

### Added

- Admin password reset from **Team → Reset password**, plus
  `flask --app run reset-password <username>` for lockout recovery without a
  running server.
- Sign-in accepts usernames, full profile names, and first/last names; the form
  now warns when Caps Lock is on and includes a short troubleshooting panel.

### Changed

- Refreshed the product palette from plum/gold to deep pine and muted brass
  across the workspace, sign-in, mobile shift view, Tender Copilot, favicon,
  manifest, and banner.
- Unified typography (Plus Jakarta Sans + Playfair Display) across all pages.
- Removed the extra `andama` bootstrap Shop Owner; fresh installs now seed only
  Charles Onzima (owner) and Sarah Achen (sales).

### Fixed

- Staff who remembered only their profile name could not sign in; matching is
  now case-insensitive, whitespace-tolerant, and name-aware.
- Deleting a staff account with sign-in history now detaches those audit rows
  instead of failing on the `login_events.user_id` foreign key.

## [2.4.0] — 2026-10-21

Packaging, entitlements, and the Phase 6 pilot.

### Added

- Static app registry, bundles, and installation-level entitlements.
- Server-side entitlement gate with plan-aware `403` responses and `/api/apps`.
- Odoo-style app launcher, plan UI, upgrade prompts, and a Legacy all-apps
  bundle for Onzima.
- Standalone Tender Copilot branding and shared sign-in settings.
- Packaging dry run that copies the database, migrates, seeds, downgrades,
  re-upgrades, and rehearses a restore without touching the source.
- Pilot metrics script, pilot runbook, tracker, and smoke checklist.
- Brand assets, web manifest, and a responsive mobile shift view.
- Project documentation: README, security policy, contributing guide, and
  consolidated runbooks.

### Changed

- Documentation moved under `docs/` (packaging plan and strategy playbook).
- Sign-in and workspace pages now carry favicon, theme, and description
  metadata.

### Security

- Debug is off by default; `ProdConfig` refuses to start without `SECRET_KEY`.
- Session cookies are `HttpOnly` and `SameSite=Lax`.
- Bootstrap passwords are only created on an empty user table and are never
  reset on restart.
- Baseline response headers deny framing, MIME sniffing, and search indexing.
- Default bundle for new installations is Core; Onzima keeps Legacy.

## Earlier

- Modular monolith cut-over: application factory, 14 domain packages, one
  migration stream, and the initial pytest and Ruff CI gates.
- Pharmacy POS, batch and expiry inventory, refill care, credit and expense
  tracking, reconciliation, SMS/WhatsApp alerts, and reporting.
- Tender Copilot analysis, compliance checks, and methodology drafting.
