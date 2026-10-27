# Project Archive

This directory stores legacy scripts, historical design plans, and temporary tools that are no longer actively used in day-to-day development or production operations, but are preserved for audit, historical reference, and rollback context.

---

## Directory Structure

```
archive/
├── modularization/
│   ├── IMPLEMENTATION_PLAN.md    # The original 8-phase monolith-to-modules refactor plan (Completed)
│   └── README.md                 # Context on the modular monolith migration
└── scripts/
    ├── diag.py                   # Legacy password hash probe (used during Phase 4 auth migration)
    └── fix_drug_classes.py       # One-off string replacement patch for template CSS classes
```

---

## Inventory of Archived Files

### 1. `archive/modularization/IMPLEMENTATION_PLAN.md`
- **Purpose:** Documented the migration of the original 1,356-line monolithic `app.py` into the modular `drugshop/` package (Phases 0 through 8).
- **Status:** **Completed & Closed** (2026-10-19).
- **Superseded By:** Active development is now governed by [`docs/packaging-plan.md`](../docs/packaging-plan.md) (Implementation Plan 2: Packaging, Entitlements & App Launcher).

### 2. `archive/scripts/diag.py`
- **Purpose:** Ad-hoc diagnostic script used to probe SQLite user password hashes when replacing the legacy hardcoded password allowlist with Werkzeug password hashing.
- **Status:** **Retired**. Replaced by standard CLI management (`flask --app run users`) and unit tests in `tests/test_auth.py`.

### 3. `archive/scripts/fix_drug_classes.py`
- **Purpose:** One-time text patcher for updating button and pill badge CSS class names in `index.html` during the frontend refactor.
- **Status:** **Retired**. Template classes are now standard and maintained directly in `drugshop/templates/index.html`.
