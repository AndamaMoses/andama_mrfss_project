# Revenue Strategy — Onzima Dawa & Tender Copilot

**Status:** v1 commercial model approved 2026-11-05; validate with the first five buyers  
**Date:** 2026-11-05  
**Owner:** Andama Moses  
**Scope:** Commercial model for the current build (packaging Phases 0–5 complete; Phase 6 pilot runs through 2026-11-09)

> This document describes commercial intent. The current build does **not**
> contain a price book, checkout, billing, or a licence server. The prices below
> were approved for v1 on 2026-11-05 (see the
> [implementation plan](revenue-strategy-implementation-plan.md) Appendix A) and
> should still be validated with the first five buyers.
>
> **Build plan:** see
> [`revenue-strategy-implementation-plan.md`](revenue-strategy-implementation-plan.md)
> for the phased implementation, test gates, rollback points, and review
> checkpoints.

---

## 1. Thesis

Onzima Dawa is sold as **B2B software for one installation at a time**, not as a
payments platform or a marketplace.

The revenue engine is:

1. a **one-time setup and catalog-ingestion fee**;
2. a **recurring monthly subscription** for the chosen bundle;
3. a **Growth add-on** for proactive alerts;
4. a separate **Tender Copilot** subscription for consultancies.

The product does **not** take a commission on MTN MoMo, Airtel Money, cash, or
credit transactions. Those rails move the pharmacy's own customer money. Revenue
comes from software access and onboarding services.

Strategic principles:

- **Land with Core, expand with proof.** Start with POS and inventory, then sell
  Finance, Refill Care, and alerts after the shop trusts the system.
- **Sell outcomes, not features.** Stock-loss prevention, faster reconciliation,
  and refill retention are the buying reasons.
- **Protect recurring revenue.** Discount setup if a deal needs movement; do not
  discount the monthly fee.
- **Stay sales-assisted.** At 20 customers, manual activation is cheaper and
  safer than self-service billing.
- **Keep one codebase, several SKUs.** Packaging and entitlements create the
  commercial options without forking the product.
- **Treat Tender Copilot as a separate vertical.** It shares code, auth, and
  deployment, but has its own brand and buyer.

---

## 2. What we sell

### 2.1 Revenue streams

| Stream | What the customer buys | Billing | Status |
|---|---|---|---|
| **Setup & catalog ingestion** | Installation, database setup, catalog import, first-run configuration, handover | One-time | Sold manually; onboarding runbook exists |
| **Core subscription** | POS, inventory, batches, expiry, purchases, customers, dashboard | Monthly | Built and gated |
| **Pro subscription** | Core + Refill Care, Finance (credit, reconciliation, expenses, profit), staff activity | Monthly | Built and gated |
| **Growth add-on** | Stock Alerts, SMS/WhatsApp reminders and log; requires Pro | Monthly add-on | Built and gated |
| **Tender Copilot** | Tender workspace, PPDA/UNRA analysis, compliance matrix, methodology drafting | Setup + monthly | Built and gated; standalone brand |
| **Combined installation** | Pro + Tender Copilot | Setup + monthly | Technically supported; price not defined |

### 2.2 Explicit non-streams

The current build does **not** monetise through:

- transaction fees or revenue share on customer payments;
- per-user or per-seat pricing;
- self-service upgrades or in-app card checkout;
- advertising, data resale, or marketplace commissions;
- hardware sales.

Users are not metered. Entitlements are installation-wide; roles still control
what each user can do.

---

## 3. Product packaging

| App | Bundle | Customer outcome |
|---|---|---|
| Dashboard | Always-on | Today at a glance |
| Point of Sale | Core | Sell, take payment, print receipts, close the day |
| Inventory & Purchases | Core | Batch stock, expiry control, supplier invoices |
| Refill Care | Pro | Chronic-patient register and Day-25 refill reminders |
| Finance | Pro | Credit ledger, cash/MoMo reconciliation, expenses, profit |
| Stock Alerts | Growth | Low-stock and expiry alerts |
| Tender Copilot | Tender | Tender analysis and methodology drafting |

### 3.1 Bundle map

| Bundle | Apps included | Sold? |
|---|---|---|
| **Core** | `pos`, `inventory` | Yes |
| **Pro** | Core + `patients`, `finance` | Yes |
| **Growth** | Pro + `alerts` | Yes |
| **Tender** | `tender` | Yes, standalone |
| **Legacy** | All gated apps | No — Onzima only, grandfathered |

A Growth customer keeps every Pro app. Tender can be combined with any pharmacy
bundle by activating both. The server-side gate enforces the bundle on every
request, including for admins.

---

## 4. Pricing

### 4.1 Approved v1 price card

| Offer | Setup (UGX) | Monthly (UGX) | Buyer |
|---|---:|---:|---|
| **Core** | 400,000 | 120,000 | Single-counter shop |
| **Pro** | 600,000 | 180,000 | Established shop with staff and credit |
| **Growth add-on** | 200,000 | +50,000 | Pro customers |
| **Tender Copilot** | 300,000 | 150,000 | Consultancies |

**Billing assumptions (approved for v1):**

- Prices are per installation, in UGX, for one shop, and totals are
  tax-inclusive unless VAT/accounting advice changes this.
- Setup is invoiced once and collected before activation.
- Subscription is invoiced monthly in advance.
- Growth requires Pro and is quoted as an increment, not a separate product.
- Combined Pro + Tender is the sum of the two lines until a package discount is
  approved.
- Setup discounts need founder approval and are capped at UGX 100,000 in v1;
  monthly fees are never discounted.
- Payment methods are cash, bank transfer, MTN MoMo, Airtel Money, or other,
  recorded manually. No gateway charges the shop for its own subscription.
- Hardware, internet, carrier charges, and messaging pass-through costs are not
  included in the price card.

### 4.2 Pricing rules

- **Do not discount the monthly fee.** It sets the renewal anchor and the value
  of the recurring book.
- **Discount setup if a deal needs movement.** The plan explicitly allows this
  lever.
- **Do not grandfather new customers.** Legacy is for the existing Onzima
  installation only.
- **Do not change a live plan to run a demo.** Use the staging Core/Pro installs.
- **Keep the quote simple.** The target is to quote a bundle in under five
  minutes.

### 4.3 Conflict to resolve

The older [`strategy-playbook.md`](strategy-playbook.md) proposes a retail range
of **UGX 400,000–600,000 setup + UGX 80,000–150,000/month** for Onzima. The
packaging plan proposes **120,000 Core / 180,000 Pro** and flags the difference
as an open decision.

Recommendation: use the packaging plan's structure for the first five buyers,
record actual willingness to pay, and only then publish a final card. Do not
publish two competing ranges.

---

## 5. Unit economics

### 5.1 Illustrative 20-customer mix

From the packaging plan's target mix: 11 Core, 9 Pro, 5 Growth add-ons.

| Line | Calculation | UGX |
|---|---|---:|
| Core MRR | 11 × 120,000 | 1,320,000 |
| Pro MRR | 9 × 180,000 | 1,620,000 |
| Growth MRR | 5 × 50,000 | 250,000 |
| **Total MRR** | | **3,190,000** |
| **ARR** | MRR × 12 | **38,280,000** |
| Setup cash (one-time) | 11 × 400,000 + 9 × 600,000 + 5 × 200,000 | **10,800,000** |
| Blended ARPU | 3,190,000 ÷ 20 | **159,500/month** |

At roughly 3,800 UGX/USD, this is about **USD 840 MRR** — a founder-led
business, not a venture-scale platform. Tender Copilot revenue is additive and
is not included in this mix.

### 5.2 What is not yet measured

- Gross margin after support time, hosting, and messaging costs.
- Cost to onboard one customer.
- Churn and renewal rate.
- Setup discount actually granted.
- Tender Copilot sales cycle and close rate.

These become the commercial dashboard once the first paying customers exist.

---

## 6. Ideal customer and positioning

### 6.1 Pharmacy ICP

**Primary:** a single-counter or established drug shop in the Kampala–Jinja
corridor, already using a manual book, spreadsheet, or a basic POS.

Buying triggers:

- repeated stockouts or silent expiry losses;
- daily cash/MoMo reconciliation mismatches;
- lost chronic-medication refills;
- more than one staff member handling sales;
- credit customers tracked informally.

**Core** fits the shop that mainly needs to sell and control stock. **Pro** fits
the shop with staff, credit, and a reconciliation problem. **Growth** fits a Pro
shop that wants alerts without adding staff.

### 6.2 Tender ICP

Consultancies and engineering firms bidding for PPDA/UNRA work, starting with
Communion Engineering Services in Jinja. The pain is document volume and
compliance risk, not pharmacy operations.

### 6.3 Positioning

> **Odoo-grade polish, pharmacy-grade focus, WhatsApp-native workflows.**

Do not position on price against Odoo or generic POS tools. Position on
time-to-value and stock-loss prevention. For Tender Copilot, position on hours
saved per tender and compliance coverage.

---

## 7. Sales and expansion motion

| Stage | Action | Evidence / tool |
|---|---|---|
| 1. Target | Build a list of shops in the corridor; qualify counter count, staff, credit, and current system | Founder pipeline sheet |
| 2. Discover | 15-minute call or visit; identify the cost of stockouts, expiry, and reconciliation | Discovery notes |
| 3. Demo | Show POS, expiry control, and the reconciliation view on staging | Core or Pro staging install |
| 4. Quote | Choose Core, Pro, Growth, or Tender; give setup + monthly in under 5 minutes | Price card |
| 5. Close | Collect setup and first month; agree start date | Invoice / receipt |
| 6. Activate | Back up, deploy, set the bundle by CLI, run smoke checks, show the plan panel | [`onboarding-runbook.md`](onboarding-runbook.md) |
| 7. Adopt | 30-day check-in; confirm one real workflow works end to end | Support log |
| 8. Expand | Demo the next bundle using real usage, not a generic pitch | Staging upgrade demo |
| 9. Renew | Remind 14 days before expiry; confirm continuation | Renewal calendar |

### 7.1 Sales rules

- **One live plan change per customer, after payment.** The CLI is the activation
  mechanism; there is no self-service purchase.
- **Never demo an upgrade by changing Onzima's live plan.** Use staging.
- **No bundle announcement during the pilot.** The pilot explicitly forbids
  price sheets and feature removal until the observation window closes.
- **Log every quote.** Bundle, setup, monthly, discount, decision, and reason.
- **Do not promise unbuilt features.** AI invoice OCR, expiry prediction, and
  automated MoMo reconciliation are outside the current build.

### 7.2 Expansion paths

1. **Core → Pro:** Finance and Refill Care after the shop has clean sales and
   stock data.
2. **Pro → Growth:** alerts after the shop has experienced a stockout or expiry
   that an alert would have prevented.
3. **Pharmacy → Combined:** Tender Copilot for an owner who also bids for
   institutional supply or construction work.
4. **Tender standalone:** consultancies that do not need the pharmacy workspace.

---

## 8. Activation and lifecycle in the current build

The commercial lifecycle is deliberately manual:

1. Payment is collected outside the app.
2. The operator runs `flask --app run plan set <bundle> --expires <date> --actor "<name>"`.
3. The customer sees the read-only **Plan & Apps** panel and the upgrade CTA.
4. Entitlements gate the API and the UI; removing an app revokes access without
   deleting business data.
5. Expiry is **soft**: `expires_at` is shown but does not block access in v1.

Implications:

- **Collections discipline is the control.** The build will not chase a renewal
  or suspend a non-paying customer automatically.
- **The upgrade CTA needs a destination.** `SUPPORT_WHATSAPP` is blank by
  default; when blank, the upgrade link is hidden. Set it before any sales demo.
- **Onzima stays on Legacy.** The reference installation keeps every app during
  and after the pilot. Legacy is not a price anchor for new buyers.

---

## 9. Current build readiness

| Capability | Status | Commercial implication |
|---|---|---|
| Bundle catalog and app registry | Built | Can sell Core, Pro, Growth, Tender |
| Server-side entitlement gate | Built | Hiding UI is not the only control |
| Launcher, locked tiles, upgrade modal | Built | In-product expansion prompt exists |
| Read-only plan panel | Built | Customer can see what they own |
| Operator CLI activation | Built | Manual fulfilment after payment |
| Pricing in the UI | Not built | Quotes are manual; no price list in app |
| Checkout / billing / invoicing | Not built | Collect payment outside the platform |
| Licence server / hard expiry | Not built | Renewal is commercial, not enforced |
| Transaction commission | Not built | No take rate on customer payments |
| Combined Pro + Tender price | Not defined | Treat as a custom quote |
| Tender standalone brand and auth | Built | Separate go-to-market is possible |
| `SUPPORT_WHATSAPP` configuration | Not set in pilot | Upgrade CTA may be hidden |

---

## 10. Metrics and targets

### 10.1 Commercial dashboard

| Metric | Definition | Target |
|---|---|---|
| MRR | Sum of active monthly subscriptions | UGX 3.2M by month 12 |
| ARR | MRR × 12 | UGX 38M by month 12 |
| Setup cash collected | One-time fees in the period | UGX 10.8M across first 20 |
| Active pharmacies | Paying installations | 20 in 12 months |
| Core → Pro conversion | Pro customers ÷ Core + Pro customers | ≥ 40% |
| Growth attach rate | Growth add-ons ÷ Pro customers | ≥ 50% |
| Tender pipeline | Qualified consultancies in discussion | ≥ 3 in the first year |
| Renewal rate | Renewed ÷ due for renewal | ≥ 90% |
| Setup discount | Discount ÷ list setup price | Track; founder approval |
| Support load | Hours per customer per month | ≤ 2 |
| Activation time | Backup start to smoke complete | < 15 minutes |
| Quote turnaround | Enquiry to written quote | < 5 minutes |

### 10.2 Pilot scorecard

From [`pilot-tracker.md`](pilot-tracker.md) and
[`packaging-plan.md`](packaging-plan.md):

- zero unentitled `403`s during normal Legacy use;
- zero data loss on downgrade/upgrade;
- support hours for the pilot ≤ 2;
- at least one upgrade demo completed;
- two weeks without regressions, ending 2026-11-09.

The pilot is an operational acceptance test, not proof of product-market fit.
Commercial evidence starts with the first paying customer.

---

## 11. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Prices are too low for 20-customer economics | Cannot fund support | Validate with first five buyers; protect monthly fee; review after five |
| Soft expiry allows unpaid use | Revenue leakage | Manual renewal calendar; 14-day reminder; decide hard expiry after first renewal cycle |
| No billing integration | Slow collections, admin load | Standard invoice, setup before activation, monthly in advance |
| Manual activation does not scale | Founder bottleneck | Keep manual until ~20 customers; document the CLI runbook |
| Carrier credentials delay MoMo setup | Weaker demo | Sell Core without MoMo dependence; use manual reference fallback |
| Support load exceeds 2 hours/customer | Margin erosion | Scope setup, onboarding checklist, FAQ, in-product plan panel |
| Tender brand confuses pharmacy buyers | Weaker demos | Separate link, separate script, never bundle by default |
| Onzima's Legacy plan sets expectations | Discount pressure | Keep Legacy non-sellable; explain it is grandfathered |
| Pricing quoted inconsistently | Trust and margin loss | One price card, one discount rule, one owner |
| Combined Pro + Tender is unpriced | Deal friction | Quote as custom until a repeatable package emerges |

---

## 12. Open decisions

The v1 prices, discount rule, combined quote rule, collection methods, and
tax-inclusive treatment were approved on 2026-11-05. The rows below remain open
only where later validation or accountant review is still required.

| # | Decision | Why it matters | Owner | Target |
|---:|---|---|---|---|
| 1 | Final Core and Pro prices | Validates 120k/180k against the 80–150k playbook range | Founder | Before the second paying customer |
| 2 | Growth add-on pricing and whether future AI features are included | Protects the add-on's value | Founder | Before the first Growth sale |
| 3 | Combined Pro + Tender price | Avoids ad-hoc discounting | Founder | Before the first combined quote |
| 4 | Tender Copilot standalone price and pilot terms | Separate buyer, separate willingness to pay | Founder | Before the first Tender pilot |
| 5 | How subscription payments are collected | No billing exists in the app | Founder | Before the first invoice |
| 6 | Hard expiry policy | Soft expiry is a deliberate v1 choice | Founder | After the first renewal cycle |
| 7 | Setup scope boundary | Prevents unpaid catalog and data work | Founder | Before the next onboarding |
| 8 | Tax treatment and invoice format | Required for a clean commercial record | Founder / accountant | Before the first paid setup |
| 9 | `SUPPORT_WHATSAPP` destination | The upgrade CTA depends on it | Operator | Before the next demo |
| 10 | Messaging and hosting pass-through costs | Gross margin is currently unmeasured | Founder | With the first five customers |

---

## 13. Roadmap

### Now — through 2026-11-09

- Finish the Phase 6 pilot without announcing bundles or changing Onzima's plan.
- Complete the owner walkthrough and record answers in the pilot tracker.
- Run the upgrade demo on the staging Core install.
- Set `SUPPORT_WHATSAPP` so the upgrade path has a destination.
- Keep the first price card internal until the pilot closes.

### Next 90 days — validation

- Quote the approved v1 card to the first five buyers and record objections.
- Produce a one-page price sheet and a standard setup scope.
- Agree the subscription collection method and invoice template.
- Onboard the first two paying Core customers using the onboarding runbook.
- Run one Pro upgrade conversation grounded in real usage.
- Start a Tender Copilot conversation with Communion Engineering.
- Review support hours and setup effort after each onboarding.

### Months 4–12 — repeatability

- Reach 20 paying pharmacies in the corridor.
- Target 9 Pro customers and 5 Growth add-ons within that base.
- Convert at least one Tender Copilot engagement.
- Decide whether soft expiry is sufficient after the first renewal cycle.
- Review the v1 card after five buyers and publish the next revision.
- Review whether the 20-customer model supports a second operator.

### Longer term — only with evidence

Revisit self-service billing, a licence server, or a multi-tenant SaaS model only
when the triggers in [`packaging-plan.md`](packaging-plan.md) §13 are met:
50+ customers across 3+ verticals, reseller demand, per-module procurement, a
dedicated platform engineer, or offline module changes.

---

## 14. Operating cadence

| Cadence | Review |
|---|---|
| Weekly | Pipeline, demos, quotes, activations, support hours |
| Monthly | MRR, setup cash, renewals due, discount log, churn reasons |
| Quarterly | Price card, bundle mix, Tender pipeline, support economics |
| Per customer | Activation checklist, 30-day check-in, renewal reminder 14 days before expiry |

---

## Appendix A — App-to-bundle map

| App ID | Name | Bundle | Requires |
|---|---|---|---|
| `dashboard` | Dashboard | Always-on | — |
| `pos` | Point of Sale | Core | — |
| `inventory` | Inventory & Purchases | Core | — |
| `patients` | Refill Care | Pro | — |
| `finance` | Finance | Pro | — |
| `alerts` | Stock Alerts | Growth | `patients`, `finance` |
| `tender` | Tender Copilot | Tender | — |

---

## Appendix B — Activation commands

```bash
# Show the current plan and recent entitlement changes
flask --app run plan show

# Activate a bundle after payment
flask --app run plan set core --expires 2027-11-05 --actor "Andama"
flask --app run plan set pro  --expires 2027-11-05 --actor "Andama"

# Add or remove an app
flask --app run plan add alerts --actor "Andama"
flask --app run plan remove alerts --actor "Andama"
```

Expiry is informational in the current build. A `plan set` replaces the bundle
entitlement set and writes an audit event for each change.

---

## Appendix C — Source documents

- [`packaging-plan.md`](packaging-plan.md) — bundles, prices, entitlements, pilot
  plan, risk register, and open decisions.
- [`strategy-playbook.md`](strategy-playbook.md) — corridor outreach and the
  original retail pricing range.
- [`business-context.md`](business-context.md) — customer research for both
  verticals.
- [`implementation-status.md`](implementation-status.md) — what is built and what
  remains open.
- [`pilot-tracker.md`](pilot-tracker.md) — live pilot evidence and exit criteria.
- [`onboarding-runbook.md`](onboarding-runbook.md) — activation and handover.
- [`drugshop/apps/registry.py`](../drugshop/apps/registry.py) — the source of
  truth for apps and bundles.
- [`drugshop/apps/cli.py`](../drugshop/apps/cli.py) — operator plan activation.
