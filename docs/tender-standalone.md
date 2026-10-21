# Tender Copilot — standalone deployment notes

Tender Copilot is the same repository, Flask application, SQLite database, and
migration stream as the pharmacy suite. It is a separate product and brand, not
a separate service. These notes cover the Phase 4 packaging rules and the
supported ways to expose Tender Copilot on its own.

## 1. What “standalone” means

- One repository, one Flask app, one database per installation.
- Shared auth: `/login`, `/api/login`, `/api/logout`, `/api/me`, and the
  `users` table.
- The app catalog still contains pharmacy apps, but entitlement gating hides
  them in the UI and returns `403 app not entitled` at the API.
- A Tender-only install is seeded with `DRUGSHOP_BUNDLE=tender`. Always-on
  surfaces such as login, user management, settings, and backup remain
  available because they are product infrastructure, not pharmacy features.
- The Tender page and the login page detect a Tender-only entitlement set and
  render the Tender Copilot brand. Combined installs keep the Onzima link.

## 2. Demo hygiene — no cross-sell leakage

| Demo | Seed | Expected |
|---|---|---|
| Pharmacy Core/Pro/Growth | `DRUGSHOP_BUNDLE=core` / `pro` / `growth` | No Tender sidebar link; no Tender launcher tile; `/tender` redirects to `/?upgrade=tender` |
| Tender Copilot only | `DRUGSHOP_BUNDLE=tender` | Tender page works; pharmacy API is blocked; launcher shows only Tender + always-on tiles; login defaults back to `/tender` |
| Combined pharmacy + Tender | pharmacy seed, then `flask --app run plan add tender` | Both surfaces work; the Tender sidebar link and backlink appear |

Tender Copilot is never part of a new-install default seed. The grandfathered
Onzima `legacy` plan is the only all-apps seed.

## 3. Same origin (default)

Serve both surfaces from one host:

- `https://app.example.com/` — pharmacy suite
- `https://app.example.com/tender` — Tender Copilot

No extra configuration is needed. Session cookies are host-only and shared, and
the Flask `SECRET_KEY` is the same process.

## 4. Optional separate domain or subdomain

You can point a second DNS name at the **same** installation. Do not clone the
repository, run a second Python process against the same SQLite file, or fork
templates.

Example `nginx` vhost for `tender.example.com`:

```nginx
server {
    server_name tender.example.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Keep the pharmacy hostname pointed at the same `127.0.0.1:5000`.

### Shared sign-in across hosts

Browsers only share cookies across hosts when the cookie domain covers both.
For one sign-in on `app.example.com` and `tender.example.com`:

```powershell
$env:SESSION_COOKIE_DOMAIN = ".example.com"
$env:SECRET_KEY = "<same value on every host>"
```

Both hostnames must use HTTPS. `SESSION_COOKIE_DOMAIN` will not share cookies
between unrelated registrable domains (for example `pharmacy.example` and
`tender.example`); users sign in once per domain against the same `users`
table. The database and `SECRET_KEY` must stay identical either way.

### Tender-only hostname

A deployment that only sells Tender Copilot is the same code with a different
seed:

```powershell
$env:DRUGSHOP_BUNDLE = "tender"
python run.py
flask --app run plan show
```

The login page defaults to `/tender` after sign-in, and `/tender` shows the
standalone brand with a sign-out control. Pharmacy endpoints remain blocked.

## 5. Rollback

1. Restore the database backup (entitlements live in the same file).
2. Point the hostname back at the pharmacy install.
3. `flask --app run plan set core` (or `pro`, `growth`; `legacy` only for
   Onzima).
4. Verify `/api/apps`, `/tender`, and `/` with the smoke script.

## 6. Do not

- Do not split the codebase into a second app or repository.
- Do not run two processes against one SQLite database.
- Do not put pharmacy upgrade copy on the Tender page; Tender has its own
  go-to-market.
- Do not seed new pharmacy demos with `legacy`.
- Do not remove the server-side entitlement gate and rely on hidden UI.
