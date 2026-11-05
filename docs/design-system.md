# Dawa Ledger

**The Onzima Dawa design system**  
Version 1.0 · Proposed for review · October 2026  
Owner: Product & Engineering, Communion Engineering Services Ltd

> Dawa Ledger is a working system for a pharmacy counter, a stockroom, and a tender desk.
> It is built from the artifacts of the trade — the label, the ledger, the seal, the stock
> card — rather than from a generic component library.

---

## 0. At a glance

| | |
|---|---|
| **Product** | Onzima Dawa (pharmacy operations) and Tender Copilot (procurement intelligence) |
| **Design idea** | A well-kept dispensary: precise records, warm materials, visible accountability |
| **Reference implementation** | [`docs/design/ui-kit.html`](design/ui-kit.html) |
| **Token source** | [`docs/design/ui-kit.css`](design/ui-kit.css) · [`components.css`](design/components.css) · [`patterns.css`](design/patterns.css) |
| **Status** | Visual language for approval; not yet applied to production templates |
| **Non-negotiables** | Evidence over decoration · Labels always legible · No emoji in chrome · No glass, mesh, or floating cards |

### What this system replaces

The current interface has a recognizable palette and a good apothecary seed, but it relies on
conventions that make it feel assembled rather than designed:

- rounded white cards with drop shadows and coloured top borders
- glassmorphic sidebar panels and gradient buttons
- generic SaaS pills and badge chips
- mixed radii, inconsistent icon weights, and emoji used as interface icons
- display type used decoratively instead of to establish hierarchy

Dawa Ledger keeps the pine/brass brand equity, then gives it a stricter grammar.

---

## 1. Brand and identity

### 1.1 The idea

A pharmacy runs on records: batch numbers, expiry dates, signatures, cash counts, refill
dates. The interface should feel like those records are being handled with care. The visual
metaphor is **the ledger and the label**: warm paper, dark ink, brass rules, monospaced
metadata, and a seal that marks the work as belonging to Onzima Dawa.

This is not a nostalgic paper pastiche. It is a precise operational instrument that borrows
the *confidence* of the ledger: ruled alignment, tabular figures, explicit labels, and a
clear record of who did what.

### 1.2 Brand attributes

| Attribute | Means | Does not mean |
|---|---|---|
| **Precise** | Numbers align, labels are explicit, states are unambiguous | Cold, clinical, or cramped |
| **Warm** | Paper tones, brass, human language, generous writing space | Cute, hand-drawn, or decorative |
| **Accountable** | Every record shows an owner, a time, and a status | Surveillance or clutter |
| **Local** | Ugandan context, UGX, Kireka and Jinja, real names | Folkloric or touristic |
| **Unhurried** | Calm hierarchy and quiet motion at the counter | Slow, wasteful, or over-animated |

### 1.3 Design principles

1. **The record comes first.** A screen exists to help someone find, change, or trust a record.
   Decoration that does not help that job is removed.
2. **Label it like a pharmacist.** Say “Expires in 5 days”, not “Attention required”. Use plain,
   specific words and put the number where the eye lands first.
3. **Structure with rules, not boxes.** Hairlines, alignment, and spacing create groups. A border
   is a last resort, not the default container.
4. **Brass marks importance, never decoration.** Brass is a seal, an active marker, a focus ring,
   a single underline. If everything is brass, nothing is.
5. **Density is a service.** Counter staff need many rows on screen. Use 40–44 px controls and
   compact tables, then relax on mobile rather than shrinking everything.
6. **No false affordances.** If it looks like a button it is a button. If it is a status it is a
   stamp, not a pill that invites a tap.

### 1.4 Logo

The mark is an **octagonal brass seal** containing a mortar and pestle. The octagon is the
system’s corner language; the mortar is the pharmacy; the brass is the standard of care.

| Element | Rule |
|---|---|
| **Seal** | Brass gradient octagon, 1 px inner keyline, mortar/pestle in deep pine. Never outline-only on light backgrounds. |
| **Wordmark** | “Onzima” in Fraunces SemiBold, “Dawa” in Fraunces Italic. On dark grounds, “Onzima” is paper and “Dawa” is brass. On light grounds, both are pine with “Dawa” in brass-700. |
| **Descriptor** | `APOTHECARY · KIREKA` in IBM Plex Mono, 10 px, 0.16em tracking, uppercase. One line only. |
| **Lockup** | Seal left, wordmark and descriptor right, baseline-aligned. Gap = 40% of seal width. |
| **Clear space** | Minimum 1× seal width on all sides. |
| **Minimum size** | Digital lockup 120 px wide; seal alone 24 px; favicon 16 px. |
| **Misuse** | No rotation, no drop shadow, no recolouring outside the palette, no seal as a decorative watermark inside content, no wordmark over a photograph. |

### 1.5 Product family

Onzima Dawa and Tender Copilot share one system and one seal geometry.

- **Onzima Dawa** — pine and brass. Descriptor: `APOTHECARY · KIREKA`.
- **Tender Copilot** — pine and **clay**. Descriptor: `PROCUREMENT · JINJA`. The clay accent
  appears only in the product tag, the active section marker, and tender-specific stamps.
  It never replaces brass in the pharmacy workspace.

When both appear in one installation, the seal stays brass; the product tag changes to
clay. This keeps the family recognizable while making the workspace legible.

### 1.6 Voice

Write like a senior colleague at the next counter: direct, specific, calm.

| Do | Don't |
|---|---|
| “Batch OM-55 expires in 5 days.” | “Uh oh! Something needs your attention!” |
| “Record a sale” | “Let’s get selling ✨” |
| “Saved. Stock is now 190 units.” | “Success!! Your changes have been saved.” |
| “Only the shop owner can download backups.” | “You are not authorized to perform this action.” |
| “No refills due today.” | “Nothing to see here!” |

- Use sentence case for buttons, labels, and headings.
- Use the imperative for actions: *Record payment*, *Print receipt*, *Add batch*.
- Use the past tense for confirmations: *Payment recorded*, *Batch added*.
- Name the thing, then the state: *Stock — low*, *Invoice — unpaid*.
- Never use emoji as an interface icon. Never use exclamation marks in system messages.

---

## 2. Colour

### 2.1 Palette

Colour is named after materials, not abstractions. This keeps conversations concrete
(“use paper-200 here”, not “use the light grey”).

#### Paper — the ground

| Token | Hex | Use |
|---|---|---|
| `--ds-paper-50` | `#FCF9F1` | Surfaces, sheets, input fields |
| `--ds-paper-100` | `#F6F1E4` | App canvas |
| `--ds-paper-200` | `#ECE5D3` | Sunken wells, table headers, hover rows |
| `--ds-paper-300` | `#DCD1B8` | Disabled fills, rules on paper |

#### Ink and pine — the record

| Token | Hex | Use |
|---|---|---|
| `--ds-ink-900` | `#111C17` | Primary text |
| `--ds-ink-700` | `#2B4037` | Secondary text, strong labels |
| `--ds-ink-500` | `#56695F` | Muted text, captions |
| `--ds-ink-300` | `#89988F` | Disabled text, placeholders |
| `--ds-pine-950` | `#061A15` | Sidebar, inverse ground |
| `--ds-pine-900` | `#0A241D` | Deep panels, hover on inverse |
| `--ds-pine-800` | `#103328` | Primary action |
| `--ds-pine-700` | `#174838` | Primary hover, info text |
| `--ds-pine-500` | `#2C6B55` | Charts, links on paper |
| `--ds-pine-100` | `#DCE9E1` | Info background, selected row |

#### Brass — the seal

| Token | Hex | Use |
|---|---|---|
| `--ds-brass-700` | `#6E5511` | Brass text on paper (AA) |
| `--ds-brass-600` | `#8A6B16` | Focus ring, icon accent on paper |
| `--ds-brass-500` | `#B08A2E` | Rules, seals, active markers, chart highlight |
| `--ds-brass-300` | `#D8C07C` | Brass on dark grounds |
| `--ds-brass-100` | `#F2E8C9` | Highlight wash, selected nav tint |

#### Signal — the exception

| Token | Hex | Use |
|---|---|---|
| `--ds-moss-700` | `#2E5C3D` | Success text |
| `--ds-moss-500` | `#4B7B57` | Success marks, charts |
| `--ds-moss-100` | `#E1ECDF` | Success background |
| `--ds-ochre-700` | `#78560F` | Warning text |
| `--ds-ochre-100` | `#F5E9CD` | Warning background |
| `--ds-clay-700` | `#8C3D23` | Danger text, Tender accent |
| `--ds-clay-500` | `#B65A35` | Danger marks, Tender active marker |
| `--ds-clay-100` | `#F6E2D8` | Danger background |

### 2.2 Semantic tokens

Components must consume semantic tokens, never raw palette values.

```css
--ds-canvas: var(--ds-paper-100);
--ds-surface: var(--ds-paper-50);
--ds-sunken: var(--ds-paper-200);
--ds-inverse: var(--ds-pine-950);

--ds-text: var(--ds-ink-900);
--ds-text-muted: var(--ds-ink-500);
--ds-text-faint: var(--ds-ink-300);
--ds-text-inverse: var(--ds-paper-50);
--ds-text-accent: var(--ds-brass-700);

--ds-line: rgba(17, 28, 23, 0.14);
--ds-line-strong: rgba(17, 28, 23, 0.28);
--ds-line-inverse: rgba(252, 249, 241, 0.14);

--ds-action: var(--ds-pine-800);
--ds-action-hover: var(--ds-pine-700);
--ds-accent: var(--ds-brass-500);
--ds-focus: var(--ds-brass-600);

--ds-success: var(--ds-moss-700);
--ds-success-bg: var(--ds-moss-100);
--ds-warning: var(--ds-ochre-700);
--ds-warning-bg: var(--ds-ochre-100);
--ds-danger: var(--ds-clay-700);
--ds-danger-bg: var(--ds-clay-100);
--ds-info: var(--ds-pine-700);
--ds-info-bg: var(--ds-pine-100);
```

### 2.3 Contrast

All approved text pairs meet WCAG 2.2 AA (4.5:1 for body, 3:1 for large text and UI marks).

| Pair | Ratio |
|---|---:|
| ink-900 on paper-100 | 15.5:1 |
| ink-700 on paper-100 | 9.9:1 |
| ink-500 on paper-100 | 5.2:1 |
| paper-50 on pine-900 | 15.6:1 |
| paper-50 on pine-800 | 13.1:1 |
| brass-700 on paper-100 | 6.3:1 |
| brass-500 on pine-950 | 5.6:1 |
| moss-700 on moss-100 | 6.4:1 |
| clay-700 on clay-100 | 6.0:1 |
| ochre-700 on ochre-100 | 5.6:1 |

Rules:

- Never place brass-500 text on paper. Use brass-700.
- Never use ink-300 for text. It is for disabled labels and placeholder glyphs only.
- Colour never carries meaning alone. Status stamps include a word and a mark.
- Do not use pure black or pure white. The warm ground is part of the identity.

### 2.4 Colour composition

Use the **70 / 25 / 5** rule:

- **70%** paper and ink — the working surface and its record.
- **25%** pine — navigation, primary actions, inverse panels.
- **5%** brass and signal — seals, active markers, focus, status, chart emphasis.

If a screen feels “branded” rather than readable, there is too much brass.

---

## 3. Typography

### 3.1 Families

| Role | Family | Why |
|---|---|---|
| **Display** | Fraunces (variable, optical size) | A contemporary serif with a craftsman’s warmth. Carries the apothecary character without nostalgia. |
| **Interface** | Archivo | Neutral, sturdy grotesque with excellent small-size clarity. Does the work. |
| **Data and labels** | IBM Plex Mono | Batch codes, timestamps, quantities, labels, and eyebrow text. Makes records feel recorded. |

Fallbacks: `Iowan Old Style, Palatino Linotype, Georgia, serif`; `system-ui, Segoe UI, sans-serif`;
`SFMono-Regular, Consolas, monospace`.

### 3.2 Scale

| Token | Size / line | Family | Weight | Tracking | Use |
|---|---|---|---|---|---|
| `display-xl` | 64 / 0.98 | Fraunces | 500 | −0.035em | Cover statements only |
| `display-l` | 48 / 1.02 | Fraunces | 500 | −0.03em | Page titles |
| `display-m` | 36 / 1.08 | Fraunces | 500 | −0.025em | Section titles |
| `title-l` | 28 / 1.15 | Fraunces | 500 | −0.02em | Panel titles |
| `title-m` | 22 / 1.25 | Fraunces | 500 | −0.015em | Sub-panels, dialogs |
| `title-s` | 17 / 1.35 | Archivo | 600 | −0.01em | Card headings, list titles |
| `body-l` | 17 / 1.55 | Archivo | 400 | 0 | Lede paragraphs |
| `body` | 15 / 1.6 | Archivo | 400 | 0 | Default body |
| `small` | 13 / 1.5 | Archivo | 400 | 0.005em | Helper text, metadata |
| `label` | 10.5 / 1.2 | Plex Mono | 600 | 0.12em | Field labels, table heads |
| `micro` | 9.5 / 1.2 | Plex Mono | 500 | 0.14em | Eyebrows, counts, timestamps |

### 3.3 Typesetting rules

- **Display type is structural, not decorative.** Use it for the page title and one section
  opening. Never set a whole paragraph in Fraunces.
- **Sentence case for nearly everything.** Uppercase is reserved for mono labels and stamps.
- **Tabular numerals always.** Money, quantities, dates, and counts use
  `font-variant-numeric: tabular-nums`.
- **Numbers lead.** In operational messages, put the figure before the noun:
  “3 batches expire this week”, not “This week, three batches are expiring”.
- **Currency** is `UGX 12,500` — code, non-breaking space, thousands separators, no decimals.
- **Dates** are `16 Oct 2026` in prose and `2026-10-16` in data tables.
- **Time** is 24-hour: `18:42`.
- **Line length** is 60–75 characters for prose, 45–60 for narrow panels.
- **No text shadows, no letter-spaced body copy, no centred paragraphs longer than two lines.**

### 3.4 Type specimens

```
Fraunces / Display / 48
Records, not guesses.

Archivo / Body / 15
Every sale, batch, and refill is written to one ledger, so the counter
and the back office work from the same truth.

IBM Plex Mono / Label / 10.5
BATCH  OM-55   ·   EXPIRES  2026-10-16   ·   QTY  190
```

---

## 4. Space, layout, and shape

### 4.1 Spacing

A 4 px base with a named scale. Components use the scale; arbitrary pixel values are a review
failure.

| Token | Value | Typical use |
|---|---:|---|
| `space-1` | 4 | Icon-to-text micro gap |
| `space-2` | 8 | Tight stacks, badge padding |
| `space-3` | 12 | Field inner gap, table cell inline |
| `space-4` | 16 | Default stack |
| `space-5` | 20 | Panel inner padding (compact) |
| `space-6` | 24 | Panel inner padding |
| `space-7` | 32 | Section gap |
| `space-8` | 40 | Page gutter |
| `space-9` | 48 | Section padding |
| `space-10` | 64 | Major section separation |
| `space-11` | 80 | Editorial breathing room |
| `space-12` | 96 | Cover spacing |

### 4.2 Grid

- **App shell:** 272 px sidebar, 64 px top bar, fluid content, maximum 1440 px.
- **Content grid:** 12 columns, 24 px gutters, 32–40 px page gutters.
- **Panel grid:** 2, 3, or 4 equal columns; never nest more than two panel levels.
- **Reading measure:** 65ch maximum for prose; 100% for tables.
- **Asymmetry is allowed** where it carries hierarchy: a 2/1 split for chart + notes, a wide
  ledger table beside a narrow summary rail. Avoid symmetrical card walls.

### 4.3 Breakpoints

| Name | Min width | Behaviour |
|---|---:|---|
| `compact` | 0 | Single column, 16 px gutters, bottom navigation, 44 px targets |
| `medium` | 640 | Two-column panels, sidebar becomes a drawer |
| `wide` | 960 | Persistent sidebar, three-column stat strips |
| `full` | 1280 | Maximum density, optional summary rail |

### 4.4 Shape and elevation

| Token | Value | Use |
|---|---|---|
| `radius-xs` | 2 px | Buttons, inputs, panels, stamps |
| `radius-sm` | 3 px | Menu surfaces, larger sheets |
| `radius-round` | 999 px | Avatars and status dots only |
| `border` | 1 px solid `--ds-line` | Default separation |
| `border-strong` | 1 px solid `--ds-line-strong` | Inputs, focused containers |
| `shadow-overlay` | `0 24px 64px -24px rgba(6,26,21,.45)` | Dialogs, drawers, menus only |

- **No shadow on in-page content.** Use rules and background shifts.
- **Corner ticks:** major panels may carry a 10 px brass L-mark at the top-left and bottom-right.
  This is the signature frame. Use it once per composition, not on every box.
- **No pill-shaped buttons.** No floating cards. No glass blur. No gradient meshes.

### 4.5 The signature frame

A panel is a sheet of paper, not a floating card:

```
┌──────────────────────────────┐   ← 1px line, 2px radius, paper-50
│ SECTION LABEL            07  │   ← mono label + index
│ ──────────────────────────── │   ← hairline
│ Content                      │
└──────────────────────────────┘
```

The brass corner mark is drawn with pseudo-elements (see `.ds-frame`). It marks the primary
panel in a region. Secondary panels use a plain hairline.

---

## 5. Marks and iconography

### 5.1 The seal

The seal is the only ornamental mark in the system. It appears:

- in the sidebar header and on the sign-in panel
- as the favicon and app icon
- on printed receipts, once, at 16 px
- on the empty state, at 40 px, in brass-500 at 20% opacity

It never appears as a repeated background pattern or inside body copy.

### 5.2 Icons

- **Grid:** 24 × 24, 1.6 px stroke, rounded caps and joins, no fills.
- **Sizes:** 16, 20, 24. Never scale a 24 px icon below 16 px.
- **Colour:** inherits current text colour. Status icons may take a signal colour.
- **Meaning:** one icon, one meaning. Do not use an icon without a label in primary navigation.
- **Ban:** emoji, multicolour illustrations, filled icon sets, and mixed stroke weights.

The reference set is drawn specifically for this system: bowl-and-pestle, pill, receipt,
stock box, batch tag, ledger, scale, refill heart, alert bell, shield, truck, calendar, clock,
search, filter, download, print, external, menu, chevrons, plus, minus, check, close, more.

---

## 6. Components

Every component below is implemented in the kit. The class names are the contract.

### 6.1 Buttons

**Anatomy:** label, optional leading icon, optional trailing icon. Primary buttons carry a 3 px
brass bottom inset — the “seal edge” — instead of a gradient or glow.

| Variant | Use | Rule |
|---|---|---|
| `ds-btn--primary` | The single most likely action on a screen | One per region |
| `ds-btn--secondary` | Alternative actions | Bordered, transparent |
| `ds-btn--quiet` | Tertiary and toolbar actions | No border until hover |
| `ds-btn--danger` | Destructive confirmation only | Never the default |
| `ds-btn--link` | Inline navigation | Underline on hover, not a button |

**Sizes:** `sm` 32 px, `md` 40 px, `lg` 48 px. Minimum target 40 px desktop, 44 px touch.

**States:** default, hover, active (`translateY(1px)`), focus-visible (2 px brass outline,
2 px offset), disabled (paper-300, ink-300, no shadow), loading (label replaced by three
pulsing dots; width is preserved).

### 6.2 Fields

- Labels are mono, uppercase, above the field. Never use placeholder text as a label.
- Inputs are 42 px high, paper-50, 1 px strong line, 2 px radius.
- Focus: pine border plus a 1 px pine inset. The global focus ring remains for keyboard users.
- Error: clay border, clay label, a specific message below, and an icon. Never colour alone.
- Help text sits below the field at 13 px, ink-500.
- Required fields are marked with the word `Required` in the label row, not an asterisk alone.
- Selects use a custom chevron; no native arrow inconsistency.
- Search fields use the mono `/` hint on desktop and no hint on touch.
- Checkboxes and radios are 18 px, pine when checked. Switches are rectangular, not pills.
- Quantity steppers are a joined group: minus, value, plus — 40 px each.
- File drop zones use a dashed line and a mono instruction, not a large illustration.

### 6.3 Navigation

- **Sidebar:** 272 px, pine-950. Numbered groups (`01`, `02`…) in mono. The active item is a
  paper label with an inset brass rail — a physical tag on a dark shelf.
- **Top bar:** 64 px, paper-50, hairline base. Breadcrumb in mono; search and utilities on the right.
- **Tabs:** underline tabs, 2 px brass indicator, no filled pills.
- **Breadcrumbs:** `Workspace / Stock / Batch OM-55`, mono, slash separators.
- **Pagination:** rectangular page buttons, current page pine, neighbours quiet.
- **Mobile:** bottom navigation with four items maximum, 56 px high, labels always visible.

### 6.4 Data display

- **Stat strip:** a single ruled band, not four cards. Label, large tabular figure, note.
  Dividers are hairlines; one figure may take brass emphasis.
- **Panel:** paper sheet, 1 px line, header with mono label and optional index. No shadow.
- **Ledger table:** row numbers in mono, uppercase mono headers, hairline rows, right-aligned
  numbers, hover wash. The table is the primary data component.
- **Status stamp:** rectangular, 1 px border, 10 px mono uppercase, a 5 px square mark.
  Variants: live, success, warning, danger, neutral.
- **Count badge:** rectangular, mono, pine ground; max two digits before widening.
- **Avatar:** circular, 32/40 px, initials in Fraunces. No photo required. Groups sit
  side by side with a 4 px gap and end in a mono `+n` count; discs never overlap.
- **Meter:** 4 px track, pine fill, brass threshold marker. Always paired with a number.
- **Timeline:** vertical hairline, 7 px square nodes, mono timestamp, actor in Archivo.
- **Charts:** 1.5 px lines, hairline grid, no gradients or 3D. One brass series maximum.
  Label axes in mono at 9.5 px. Always provide a text summary.

### 6.5 Feedback

- **Inline banner:** left 3 px signal rule, tinted background, title + one sentence, optional action.
- **Toast:** pine-950 block, brass left rule, paper text, mono label, 6 s maximum, bottom-right.
  Never use a toast for an error that needs a decision.
- **Empty state:** seal watermark, a direct sentence, one action. No illustration.
- **Skeleton:** paper-200 blocks, no shimmer. Use only for content that is genuinely loading.
- **Tooltip:** pine-950, 12 px Archivo, 4 px radius, 200 ms delay, keyboard accessible.

### 6.6 Overlays

- **Dialog:** paper sheet, 2 px brass top rule, 560 px max width, title in Fraunces 22,
  actions right-aligned. Backdrop is ink at 60%, no blur.
- **Drawer:** 400 px sheet from the right, same top rule, for contextual detail and filters.
- **Menu:** paper surface, 1 px line, 3 px radius, 6 px vertical padding, 32 px items.
- **Confirmation:** destructive copy names the record and the consequence. The destructive
  action is on the right and never the default focus.

---

## 7. Patterns

### 7.1 Operations overview

A page header with title, date, and primary action. A single stat strip. Then an asymmetric
2/1 layout: the ledger table or expiry watchdog occupies the wide column; refills, notes, or
a chart occupy the narrow rail. The eye should move **title → numbers → exceptions → detail**.

### 7.2 Counter sale

The POS screen is a two-pane instrument: product search and basket on the left, payment and
totals on the right. Totals use display type and tabular numerals. The primary action is
`Complete sale` with the amount visible in the button on wide screens. Never hide the total.

### 7.3 Receipt

A narrow paper sheet, mono throughout, seal at the top, dashed tear line, total in Fraunces.
The receipt is the one place where centred text is allowed.

### 7.4 Sign-in

A split sheet: pine panel with seal, wordmark, and a one-line promise; paper panel with the
form. Profile cards are rows, not tiles. The password reveal is a text button inside the field.
Caps-lock warning sits directly under the password field.

### 7.5 Tender Copilot

The same shell with a clay product tag. The compliance matrix is the hero: requirement,
status stamp, evidence link, owner. Risk flags use clay. Never use brass for a risk state.

### 7.6 Plan gate

An overlay sheet that states what the current plan includes, what the requested feature does,
and the next step. No lock illustrations. One primary action (`Ask about upgrading`) and one
quiet action (`Not now`).

---

## 8. Motion

Motion confirms a change; it does not perform personality.

| Token | Duration | Use |
|---|---:|---|
| `dur-fast` | 120 ms | Hover, focus, small state changes |
| `dur-base` | 180 ms | Menus, tabs, toggles |
| `dur-slow` | 280 ms | Drawers, dialogs, page transitions |
| `ease` | `cubic-bezier(.2,.7,.2,1)` | All standard motion |

- No bounce, spring, parallax, or looping decoration.
- Never animate layout properties when transform/opacity will do.
- The live-status dot may pulse at 2 s; it stops under `prefers-reduced-motion`.
- Respect reduced motion by removing transforms and shortening durations to 1 ms.

---

## 9. Accessibility

- WCAG 2.2 AA is the floor, not the goal.
- Visible focus on every interactive element: 2 px brass-600 outline, 2 px offset.
- Keyboard order follows visual order. Dialogs trap focus and restore it on close.
- Target size: 40 × 40 px desktop minimum; 44 × 44 px on touch.
- Every input has a persistent visible label. Placeholders are examples, not labels.
- Errors are announced (`role="alert"`), described, and tied to the field with `aria-describedby`.
- Tables use `<caption>`, `<th scope>`, and a text summary for charts.
- Status is never colour alone: word + mark + colour.
- Zoom to 200% must not clip content or hide actions.
- Test with a keyboard, a screen reader, and at 320 px width before release.

---

## 10. Content rules for data

| Case | Format | Example |
|---|---|---|
| Currency | `UGX` + thin space + grouped number | `UGX 12,500` |
| Quantity | number + unit, no space for common units | `190 units`, `60 tabs` |
| Batch | product name, then mono batch code | `Omeprazole 20mg · OM-55` |
| Expiry | relative first, exact second | `Expires in 5 days · 16 Oct 2026` |
| Date in table | ISO | `2026-10-16` |
| Stock state | `In stock`, `Low`, `Out`, `Expired` | never “OK” |
| Payment | method + amount | `MTN MoMo · UGX 7,000` |
| Person | name, then role | `Sarah Achen · Sales agent` |
| Empty | sentence + action | `No batches recorded. Add the first batch.` |

Truncation: never truncate money, quantities, dates, or status. Truncate long product names
with an ellipsis and expose the full name in a tooltip or detail view.

---

## 11. Implementation

### 11.1 File map

```
docs/
├── design-system.md          ← this document
└── design/
    ├── ui-kit.html           ← review specimen, sections 00–14
    ├── ui-kit.css            ← tokens, reset, shell, foundations
    ├── components.css        ← buttons, forms, stamps, tables, overlays
    ├── patterns.css          ← app shell, POS, receipt, plan gate, mobile
    └── ui-kit.js             ← demo interactions only
```

The kit is dependency-free: one HTML file, three CSS layers, one small JS file, and
Google Fonts. It is a review artifact, not a production bundle.

### 11.2 Naming

- Tokens: `--ds-<group>-<step>` (`--ds-pine-800`, `--ds-space-6`).
- Classes: `ds-<block>`, `ds-<block>__<element>`, `ds-<block>--<variant>`.
- States: `is-active`, `is-error`, `is-loading`, `is-disabled`.
- No utility-class soup. Layout classes are explicit and few.
- No inline styles except dynamic widths in charts.

### 11.3 Adoption path

1. **Approve the language.** Review the kit at 320, 768, 1280, and 1440 px.
2. **Extract tokens.** Move section 2 and 3 into `drugshop/static/css/tokens.css`.
3. **Build the shell.** Sidebar, top bar, page header, and stat strip first. These set the tone.
4. **Replace the ledger surfaces.** Tables, panels, stamps, and forms.
5. **Retire the old layer.** Remove inline `<style>` blocks from templates one screen at a time.
   Never run the old and new visual languages side by side in the same viewport.
6. **Regression pass.** Run the persona journeys, keyboard checks, and the screenshot suite.

### 11.4 Definition of done for a screen

- [ ] Uses semantic tokens only; no raw hex in component CSS.
- [ ] One primary action; hierarchy is obvious at arm’s length.
- [ ] Numbers are tabular and aligned; currency and dates follow section 10.
- [ ] Empty, loading, error, and permission-denied states are designed.
- [ ] Keyboard focus is visible and in visual order.
- [ ] Works at 320 px and at 200% zoom.
- [ ] No emoji, glass, gradient mesh, floating card, or pill button.
- [ ] Copy reviewed against section 1.6.

---

## 12. Governance

- **Owner:** Product & Engineering.
- **Changes:** propose in a pull request that updates this document, the kit, and the token
  source together. A component without a documented state is not approved.
- **Review cadence:** after each pilot cycle and before any new workspace ships.
- **Deprecation:** mark a component `deprecated` in this document for one release, then remove it
  from the kit and the application together.

### Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-30 | Initial system: identity, palette, type, space, components, patterns, adoption path |

---

<sub>Dawa Ledger · Onzima Dawa · Communion Engineering Services Ltd · Kireka & Jinja, Uganda</sub>
