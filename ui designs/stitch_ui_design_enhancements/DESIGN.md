---
name: Clinical Apothecary Modern
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#414845'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#717974'
  outline-variant: '#c1c8c3'
  surface-tint: '#3e6657'
  primary: '#002217'
  on-primary: '#ffffff'
  primary-container: '#0e382b'
  on-primary-container: '#79a291'
  inverse-primary: '#a5d0bd'
  secondary: '#904d00'
  on-secondary: '#ffffff'
  secondary-container: '#fe932c'
  on-secondary-container: '#663500'
  tertiary: '#002114'
  on-tertiary: '#ffffff'
  tertiary-container: '#003925'
  on-tertiary-container: '#00ae79'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c0ecd9'
  primary-fixed-dim: '#a5d0bd'
  on-primary-fixed: '#002117'
  on-primary-fixed-variant: '#264e40'
  secondary-fixed: '#ffdcc3'
  secondary-fixed-dim: '#ffb77d'
  on-secondary-fixed: '#2f1500'
  on-secondary-fixed-variant: '#6e3900'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 2.25rem
    fontWeight: '700'
    lineHeight: 2.75rem
    letterSpacing: -0.025em
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.375rem
    fontWeight: '600'
    lineHeight: 1.875rem
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: 1.625rem
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.25rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1rem
  data-mono:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: -0.01em
  label-lg:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.02em
  label-caps:
    fontFamily: Inter
    fontSize: 0.6875rem
    fontWeight: '700'
    lineHeight: 0.875rem
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
  space-3xl: 3rem
---

## Brand & Style

This design system blends deep-rooted apothecary heritage with precision clinical ergonomics. Built for high-frequency retail dispensary counters, clinical verification workflows, and strict pharmaceutical stock management, the visual voice prioritizes unassailable trust, rapid scannability, and operational calm under pressure.

The aesthetic fuses **Tactile Modernism** with **Clinical Minimalism**:
- Grounded, authoritative deep forest tones provide an anchoring institutional presence.
- Crisp, sterile white and cool-slate surfaces ensure absolute visual hygiene for medication dosage, batch tracing, and prescription validation.
- Warm amber accents recall classic medicinal compounding and historical glass vials, while functioning as high-visibility operational triggers.
- Tight data density and deliberate information architecture reduce cognitive fatigue during extended shifts, supporting dual-input ergonomic environments (lightning-fast physical barcode/keyboard entry and broad touch-target POS terminals).

## Colors

The palette balances institutional clinical trust with distinct chromatic signals for life-critical inventory states.

### Core Roles
- **Primary (`#0E382B`)**: Deep Forest Green. Forms the foundational command layer—navigation sidebars, top headers, primary transactional confirmations, and prominent system identifiers. Deep variant `#09261D` anchors active navigation states and high-contrast terminal headers.
- **Secondary (`#D97706`) / Accent Gold (`#F59E0B`)**: Warm Apothecary Amber. Reserved for transactional highlights, dispense-action commitments, controlled drug notifications, and attention-required prescription states.
- **Tertiary / Success (`#10B981`)**: Emerald Clinical Green. Dedicated to verified prescriptions, inventory reconciled states, active dispensing channels, and positive batch tallies.
- **Watchdog / Critical (`#EF4444`)**: Urgent Crimson. Strictly isolated for batch expiry alerts, out-of-stock lockouts, dangerous drug-drug interactions, and discrepancy audits.
- **Neutral Dark (`#0F172A`)**: Deep Slate. Used for primary typography, dosage measurements, and table data points requiring maximum legibility.
- **Neutral Light Surfaces (`#FFFFFF`, `#F8FAFC`, `#F1F5F9`)**: Clean, anti-glare clinical backgrounds. Subdued border definitions rely on `#E2E8F0` for structural segmentation without visual noise.

## Typography

The typographic hierarchy eliminates decorative serifs in favor of high-legibility geometric and neo-grotesque structures, guaranteeing zero misinterpretation of milligram dosages, drug names, and numerical stock figures.

- **Plus Jakarta Sans** governs page titles, KPI metrics, modal headers, and point-of-sale total summaries, projecting modern authority.
- **Inter** handles all operational data tables, dosage regimens, batch IDs, barcode readouts, and form inputs.
- All numerical figures within tables, receipt summaries, and inventory counters must enforce tabular lining figures (`font-variant-numeric: tabular-nums`) to preserve vertical columnar alignment across fluctuating price and inventory quantities.
- Critical warnings, regulatory categories, and stock condition statuses use `label-caps` with subtle uppercase tracking to ensure immediate peripheral identification.

## Layout & Spacing

The interface utilizes a dense, highly structured layout system built for multi-window pharmacy operations, split-screen dispensing queues, and hardware-integrated POS lanes.

### Grid & Canvas Structure
- **Persistent Command Rail**: A fixed vertical navigation bar on desktop (260px wide, collapsing to 72px icon-rail) draped in `#09261D`.
- **Dual-Pane POS Terminal**: A split screen architecture pairing an active drug lookup & catalog table (fluid 60–65% width) alongside a sticky transaction and dispense cart ledger (35–40% width).
- **Responsive Adaptations**:
  - *Desktop (>1280px)*: 12-column layout with 24px margins and gutters. Multi-tier data tables display full metadata: SKU, Batch, Expiry, Strength, Pack Size, and Stock on Hand.
  - *Tablet / Touch POS (768px - 1279px)*: Collapsed navigation rail; cart shifts to a slide-over drawer or toggleable bottom sheet. Minimum touch targets expand to 44px height across active keys.
  - *Mobile / Handheld Auditing (<768px)*: Single-column stacked cards for stocktaking, barcode-driven batch auditing, and fast reconciliation.

### Spacing Philosophy
Rhythm follows an exact 4px/8px modular scale. Spacing within tabular clinical rows is compact (`space-xs` to `space-sm`) to maximize visible inventory without scrolling, while transactional triggers use generous surrounding pads (`space-lg` to `space-xl`) to prevent mis-clicks during rapid checkout.

## Elevation & Depth

This design system avoids excessive shadows, relying instead on clean surface segregation, subtle borders, and targeted ambient elevation.

- **Level 0 (Base Canvas)**: Background canvas (`#F8FAFC`) with no elevation.
- **Level 1 (Card & Module Layer)**: Resting panels, medication item cards, and catalog tables set on pure white (`#FFFFFF`) framed with a 1px border (`#E2E8F0`). Flat depth keeps screen glare low in sterile overhead lighting.
- **Level 2 (Interactive & Hover Cards)**: Soft ambient shadow for highlighted cart items and hover-state inventory lines: `0 2px 4px -1px rgba(14, 56, 43, 0.04), 0 4px 6px -1px rgba(14, 56, 43, 0.06)`.
- **Level 3 (Flyouts, Menus & Autocomplete)**: Floating search results, dosage calculators, and dropdown pickers: `0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)` with a crisp `#CBD5E1` containment border.
- **Level 4 (Clinical Modals & Overrides)**: Controlled substance approvals, lethal interaction warnings, and final payment dialogs: `0 20px 25px -5px rgba(15, 23, 42, 0.12), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`, anchored behind a 40% deep slate backdrop overlay.

## Shapes

The interface embraces a disciplined, compact shape language (`roundedness: 1` — base border radius of `0.25rem` / 4px, `rounded-md` at `0.375rem` / 6px, and `rounded-lg` capped at `0.5rem` / 8px).

- **Data Tables & Inventory Cells**: Strict square corners (0px) to soft edges (4px) to preserve maximum spatial alignment and avoid clipping long text or drug formulation names.
- **Input Fields & Transaction Buttons**: 6px (`0.375rem`) border-radius offers an ergonomic, modern look while preserving the structured authority expected of pharmaceutical software.
- **Status Pills & Micro-Badges**: Exemption to the rule—status indicators for batch expiry, prescription categories, and stock availability employ fully rounded pill structures (`9999px`) to create immediate geometric contrast against boxy tabular data.

## Components

### Buttons
- **Primary Transactional (POS Confirm / Dispense)**: Forest green (`#0E382B`) fill, pure white label, `0.375rem` radius, hover state shifts to `#09261D`. Focus ring uses a 2px offset in `#10B981`.
- **Accent Action (Add to Cart / Tender Payment)**: Apothecary amber (`#D97706`) background, white text, transitioning to `#B45309` on hover.
- **Destructive Action (Void Line / Discard Batch)**: Soft crimson tint background (`#FEF2F2`), border in `#FCA5A5`, text `#DC2626`. Hover state fills solid `#EF4444` with white text.
- **Secondary / Ghost**: White background, 1px border in `#CBD5E1`, text in `#0F172A`. Hover brings `#F1F5F9`.

### Input Fields & Search Bars
- Standard height of 40px (expanding to 48px on POS touch layouts).
- Background: `#FFFFFF`, border: 1px solid `#CBD5E1`, inset font: Inter 14px.
- Focus state: Border transitions to `#0E382B` accompanied by a 3px ring of `#0E382B` at 15% opacity.
- Drug lookup input includes persistent left-aligned barcode/search iconography and right-aligned keyboard shortcut badges (`[F2]` or `[Ctrl+K]`).

### Status Badges & Expiry Watchdogs
- **Watchdog Alert (Expired / Critical Recall)**: Background `#FEF2F2`, border 1px solid `#F87171`, text `#991B1B`. Accompanied by a pulsing crimson dot indicator.
- **Expiring Soon (<30–60 Days)**: Background `#FFFBEB`, border 1px solid `#FCD34D`, text `#92400E`.
- **In Stock / Verified Dispense**: Background `#ECFDF5`, border 1px solid `#6EE7B7`, text `#065F46`.
- **Controlled Substance (Schedule)**: Background `#F5F3FF`, border 1px solid `#C4B5FD`, text `#5B21B6`.

### Cards & Ledger Panels
- Structured with a distinct header region separated by a 1px `#E2E8F0` divider.
- Cart and checkout totals anchor firmly to the bottom of the POS drawer with prominent, oversized typography for the balance due (`Plus Jakarta Sans Bold`, 28px).

### Data Tables (Prescription & Stock Audit)
- Alternating row zebra striping is rejected in favor of high-contrast white rows separated by 1px `#F1F5F9` rules.
- Row hover triggers an immediate soft tint of `#F0FDF4` (50% opacity green-50) to assist lateral tracking across wide drug specification columns.
- Quantity adjustment components within rows feature linked segmented buttons `[-] [Qty] [+]` with physical haptic-style visual down-states.