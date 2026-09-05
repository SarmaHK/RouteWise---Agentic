# DESIGN_SYSTEM.md — RouteWise Agentic

> Source of truth #3. **Non-negotiable.** Every visual value in the product comes from
> here. The Markdown explains the rules; **`frontend/src/styles/tokens.css` implements
> them as CSS custom properties.** If the two ever disagree, fix both in the same change.
>
> **Never** hard-code a color, font size, spacing, radius, shadow, or duration in a
> component. Reference a token. If a token does not exist, **add it here first**, then use it.

---

## 0. Design principles

The interface must feel:

- **Intelligent** — it visibly *thinks*; the agent's reasoning is legible.
- **Reliable** — calm, high-contrast, no visual noise; data you can trust at a glance.
- **Modern** — contemporary dark "operations / mission-control" aesthetic.
- **Travel-focused** — routes, legs, fares, times and status are the heroes.
- **Technically sophisticated** — precise spacing, mono for data, clear hierarchy.
- **Clear** — usability first; every state (loading/error/empty/success) is designed.

**Avoid:** neon, glassmorphism, random gradients, decorative 3D objects, unnecessary
animation, and generic "chatbot" styling. Accent glow is allowed **sparingly** to signal
live agent activity only.

**Theme:** dark-first. Light theme is out of scope for the MVP; tokens are structured so a
light theme can be added later by overriding the token values only.

---

## 1. Color system

All colors are CSS custom properties defined in `tokens.css`. Use `var(--token)`.

### 1.1 Brand

| Token | Value | Use |
|-------|-------|-----|
| `--color-primary` | `#12A594` | Brand teal. Primary actions, active agent states, links, focus, key highlights. |
| `--color-primary-hover` | `#0E8B7D` | Hover on primary fills. |
| `--color-primary-active` | `#0B7165` | Pressed on primary fills. |
| `--color-primary-subtle` | `rgba(18,165,148,0.12)` | Tinted backgrounds (selected rows, active chips). |
| `--color-on-primary` | `#04211D` | Text/icon **on** a solid primary fill (passes AA). |
| `--color-secondary` | `#E9B44C` | Warm gold. Sri-Lanka warmth; secondary emphasis, "evaluating" state, premium accents. |
| `--color-secondary-hover` | `#D89F35` | Hover on secondary fills. |
| `--color-secondary-subtle` | `rgba(233,180,76,0.14)` | Tinted gold backgrounds. |
| `--color-on-secondary` | `#2A1E02` | Text/icon on a solid secondary fill. |

**Rationale:** teal = ocean / transit / calm trust; gold = sun / tea-country / warmth.
Together they read as *travel* and *Sri Lanka* without being clichéd.

### 1.2 Neutrals (surfaces & structure)

| Token | Value | Use |
|-------|-------|-----|
| `--color-bg` | `#0A0F1C` | App background (deepest layer). |
| `--color-bg-alt` | `#0D1424` | Alternate page sections (no gradients — flat). |
| `--color-surface` | `#121A2B` | Cards, panels, inputs resting surface. |
| `--color-surface-elevated` | `#1A2438` | Modals, popovers, dropdowns, raised cards. |
| `--color-surface-sunken` | `#0C1322` | Insets, wells, code/log blocks, input backgrounds. |
| `--color-border` | `#26314A` | Default 1px borders & dividers. |
| `--color-border-strong` | `#35425F` | Emphasized borders (focused/active containers). |

### 1.3 Text

| Token | Value | Use |
|-------|-------|-----|
| `--color-text-primary` | `#EAF0FA` | Headings, body, primary content. |
| `--color-text-secondary` | `#AAB6CE` | Supporting text, descriptions, secondary labels. |
| `--color-text-muted` | `#6F7C97` | Placeholders, hints, timestamps, disabled, "IDLE". |
| `--color-text-inverse` | `#0A0F1C` | Dark text on light fills (rare in dark theme). |

> All body text tokens meet **WCAG AA** contrast on `--color-surface`. Do not place
> `--color-text-muted` on `--color-bg` for small text (use secondary there).

### 1.4 Semantic (status)

Base colors are chosen to pass AA as **text on `--color-surface`**, and each has a subtle
background for chips/badges.

| State | Base token | Value | Subtle token | Subtle value |
|-------|-----------|-------|--------------|--------------|
| Success | `--color-success` | `#34C97E` | `--color-success-subtle` | `rgba(52,201,126,0.14)` |
| Warning | `--color-warning` | `#E08A2E` | `--color-warning-subtle` | `rgba(224,138,46,0.14)` |
| Error | `--color-error` | `#F05252` | `--color-error-subtle` | `rgba(240,82,82,0.14)` |
| Info | `--color-info` | `#4C9AFF` | `--color-info-subtle` | `rgba(76,154,255,0.14)` |

Solid destructive fills use `--color-error-strong` `#D64545` with `--color-on-error`
(`#FFFFFF`) text (AA at bold/large weight).

### 1.5 Focus

| Token | Value | Use |
|-------|-------|-----|
| `--color-focus-ring` | `rgba(18,165,148,0.55)` | Keyboard focus ring (2px, offset 2px). |

---

## 2. Typography

### 2.1 Font families

| Token | Value |
|-------|-------|
| `--font-sans` | `'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif` |
| `--font-mono` | `'JetBrains Mono', 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace` |

- **Sans** for all UI text. **Mono** for *data*: fares, times, distances, IDs, booking
  refs, agent logs, tool-call traces. Mono signals "this is a precise machine value".
- Web fonts (Inter / JetBrains Mono) are **not loaded yet** — the stack falls back to
  system fonts so nothing breaks. Font loading is a later frontend phase; do not add a
  font dependency during foundation.

### 2.2 Type scale

Base font size = **16px** (`1rem`). Sizes in rem with px reference.

| Token | rem | px | Weight | Line-height | Letter-spacing | Use |
|-------|-----|----|--------|-------------|----------------|-----|
| `--text-display` | 2.5 | 40 | 700 | 1.10 | -0.02em | Hero / landing headline |
| `--text-h1` | 2.0 | 32 | 700 | 1.20 | -0.015em | Page title |
| `--text-h2` | 1.5 | 24 | 600 | 1.25 | -0.01em | Section title |
| `--text-h3` | 1.25 | 20 | 600 | 1.35 | 0 | Card / panel title |
| `--text-h4` | 1.125 | 18 | 600 | 1.40 | 0 | Sub-section, emphasized label |
| `--text-body-lg` | 1.0625 | 17 | 400 | 1.60 | 0 | Lead paragraph |
| `--text-body` | 1.0 | 16 | 400 | 1.60 | 0 | Default body text |
| `--text-body-sm` | 0.875 | 14 | 400 | 1.50 | 0 | Secondary text, table cells, buttons |
| `--text-label` | 0.75 | 12 | 600 | 1.40 | +0.04em | Field labels, badges, meta (often uppercase) |
| `--text-mono` | 0.875 | 14 | 500 | 1.50 | 0 | Numeric/data values (with `--font-mono`) |

### 2.3 Font weights

| Token | Value |
|-------|-------|
| `--font-regular` | 400 |
| `--font-medium` | 500 |
| `--font-semibold` | 600 |
| `--font-bold` | 700 |

### 2.4 Line heights

| Token | Value |
|-------|-------|
| `--leading-none` | 1.0 |
| `--leading-tight` | 1.15 |
| `--leading-snug` | 1.35 |
| `--leading-normal` | 1.6 |
| `--leading-relaxed` | 1.75 |

### 2.5 Letter spacing

| Token | Value |
|-------|-------|
| `--tracking-tight` | -0.02em |
| `--tracking-normal` | 0 |
| `--tracking-wide` | 0.04em |

---

## 3. Spacing

**4px base grid.** Use only these tokens for margin, padding, and gap. No arbitrary values.

| Token | rem | px |
|-------|-----|----|
| `--space-0` | 0 | 0 |
| `--space-1` | 0.25 | 4 |
| `--space-2` | 0.5 | 8 |
| `--space-3` | 0.75 | 12 |
| `--space-4` | 1.0 | 16 |
| `--space-5` | 1.25 | 20 |
| `--space-6` | 1.5 | 24 |
| `--space-7` | 1.75 | 28 |
| `--space-8` | 2.0 | 32 |
| `--space-10` | 2.5 | 40 |
| `--space-12` | 3.0 | 48 |
| `--space-16` | 4.0 | 64 |
| `--space-20` | 5.0 | 80 |
| `--space-24` | 6.0 | 96 |

**Common patterns:** card padding `--space-5`→`--space-6`; section gap `--space-8`;
stacked text `--space-2`; icon↔label gap `--space-2`; page gutter `--container-padding`.

---

## 4. Border radius

| Token | rem | px | Use |
|-------|-----|----|-----|
| `--radius-none` | 0 | 0 | Flush edges |
| `--radius-xs` | 0.125 | 2 | Tiny chips, table pills |
| `--radius-sm` | 0.25 | 4 | Badges, small tags |
| `--radius-md` | 0.5 | 8 | Buttons, inputs, small cards |
| `--radius-lg` | 0.75 | 12 | Cards, panels, route cards |
| `--radius-xl` | 1.0 | 16 | Modals, large surfaces |
| `--radius-2xl` | 1.5 | 24 | Hero containers, Travel Pass |
| `--radius-full` | 9999 | pill | Avatars, status dots, pill badges |

---

## 5. Shadows

Dark theme: shadows are **deep + soft** (not gray). Used to convey elevation, not decoration.

| Token | Value | Use |
|-------|-------|-----|
| `--shadow-xs` | `0 1px 2px rgba(0,0,0,0.30)` | Subtle lift, badges |
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,0.40), 0 1px 2px rgba(0,0,0,0.30)` | Resting cards |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.45)` | Hovered/interactive cards, dropdowns |
| `--shadow-lg` | `0 12px 32px rgba(0,0,0,0.50)` | Modals, popovers |
| `--shadow-xl` | `0 24px 56px rgba(0,0,0,0.55)` | Full-screen dialogs, floating panels |
| `--shadow-inset` | `inset 0 1px 0 rgba(255,255,255,0.04)` | Top inner highlight on surfaces |
| `--shadow-glow-primary` | `0 0 0 1px rgba(18,165,148,0.40), 0 0 20px rgba(18,165,148,0.15)` | **Sparingly** — live/active agent emphasis only |

---

## 6. Responsive breakpoints

**Source of truth (px).** CSS custom properties **cannot** be used inside `@media`, so
media queries must use these literal values. Keep them in sync with this table.

| Token name | Min-width | Typical target |
|------------|-----------|----------------|
| `sm` | **640px** | Large phone / small tablet |
| `md` | **768px** | Tablet |
| `lg` | **1024px** | Small laptop |
| `xl` | **1280px** | Desktop |
| `2xl` | **1536px** | Large desktop |

Mobile-first: base styles target `< 640px`, then enhance upward with `min-width` queries.

---

## 7. Motion

Purposeful, quick, and calm. Motion communicates **state change**, never decoration.

### 7.1 Duration

| Token | Value | Use |
|-------|-------|-----|
| `--duration-instant` | 80ms | Press feedback, toggles |
| `--duration-fast` | 150ms | Hover, focus, small transitions |
| `--duration-base` | 220ms | Cards, panels, most UI transitions |
| `--duration-slow` | 320ms | Modals, larger reveals |
| `--duration-slower` | 480ms | Route/timeline draw-in, page-level transitions |

### 7.2 Easing

| Token | Value | Use |
|-------|-------|-----|
| `--ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | Default for most transitions |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Elements exiting |
| `--ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Elements entering |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Subtle emphasis (status dot pop) — use rarely |

### 7.3 Rules

- Prefer **opacity + transform** over layout properties (no animating width/height/top).
- **Never** animate purely for attention. Agent "live" pulse is the one allowed exception.
- Honor **`prefers-reduced-motion: reduce`** → disable non-essential animation (see
  `globals.css`).
- Loading uses a **skeleton** or a **subtle indeterminate bar**, not a bouncing spinner.

---

## 8. Z-index scale

| Token | Value | Layer |
|-------|-------|-------|
| `--z-base` | 0 | Normal content |
| `--z-dropdown` | 1000 | Select menus |
| `--z-sticky` | 1100 | Sticky headers |
| `--z-overlay` | 1200 | Modal backdrops |
| `--z-modal` | 1300 | Modals |
| `--z-popover` | 1400 | Popovers |
| `--z-toast` | 1500 | Toasts / notifications |
| `--z-tooltip` | 1600 | Tooltips (always top) |

---

## 9. Layout tokens

| Token | Value | Use |
|-------|-------|-----|
| `--container-max` | `1280px` | Max content width |
| `--container-padding` | `clamp(1rem, 4vw, 2rem)` | Responsive page gutter |
| `--header-height` | `64px` | App top bar |
| `--sidebar-width` | `360px` | Agent activity sidebar (desktop) |
| `--content-max-width` | `72ch` | Readable measure for text blocks |

---

## 10. Borders

| Token | Value |
|-------|-------|
| `--border-width` | `1px` |
| `--border-width-thick` | `2px` |
| `--border-color` | `var(--color-border)` |

---

## 11. Component tokens

Visual rules per component family. Components **must** consume these (see the
**Component Registry** §13 and **UI Application Guidelines** §12 below).

### 11.1 Buttons

| Property | Value |
|----------|-------|
| Heights | sm `32px` · md `40px` · lg `48px` (`--btn-height-*`) |
| Padding-x | sm `--space-3` · md `--space-4` · lg `--space-5` |
| Radius | `--radius-md` |
| Font | `--text-body-sm` @ `--font-semibold` (md/sm); `--text-body` @ `--font-semibold` (lg) |
| Border | `--border-width` |
| Transition | `background/border/color/box-shadow` `--duration-fast` `--ease-standard` |

Variants:

| Variant | Background | Text | Border | Hover |
|---------|-----------|------|--------|-------|
| **Primary** | `--color-primary` | `--color-on-primary` | none | `--color-primary-hover` |
| **Secondary** | transparent | `--color-text-primary` | `--color-border-strong` | bg `--color-surface-elevated` |
| **Ghost** | transparent | `--color-text-secondary` | none | bg `--color-surface-elevated`, text primary |
| **Danger** | `--color-error-strong` | `--color-on-error` | none | darken |

Focus: `box-shadow: 0 0 0 2px var(--color-bg), 0 0 0 4px var(--color-focus-ring)`.
Disabled: opacity `0.5`, `cursor: not-allowed`, no hover.

### 11.2 Inputs / Select

| Property | Value |
|----------|-------|
| Height | md `40px` (sm `32`, lg `48`) |
| Radius | `--radius-md` |
| Background | `--color-surface-sunken` |
| Border | `--border-width` `--color-border` |
| Padding | `--space-2` `--space-3` |
| Text | `--text-body-sm`, `--color-text-primary` |
| Placeholder | `--color-text-muted` |
| Focus border | `--color-primary` + `--shadow-glow-primary` (subtle) |
| Error border | `--color-error` |

### 11.3 Cards

| Property | Value |
|----------|-------|
| Background | `--color-surface` |
| Border | `--border-width` `--color-border` |
| Radius | `--radius-lg` |
| Padding | `--space-5` (compact) / `--space-6` (default) |
| Shadow | `--shadow-sm` resting; `--shadow-md` if interactive/hover |

### 11.4 Badges / Pills

| Property | Value |
|----------|-------|
| Radius | `--radius-sm` (tag) or `--radius-full` (pill) |
| Padding | `--space-1` `--space-2` |
| Font | `--text-label` (12px, 600, +0.04em; uppercase optional) |
| Style | subtle bg + matching base color text + optional 1px tinted border |

### 11.5 Status indicators & Agent-state colors

Status dot: `8px` (`--space-2`) circle, `--radius-full`. Active/live states may pulse
(`--duration-slower`, infinite, subtle opacity) — respect reduced-motion.

Canonical **Agent state → color** mapping (states defined in [`AGENT_SPEC.md`](AGENT_SPEC.md)):

| Agent state | Token | Color |
|-------------|-------|-------|
| IDLE | `--state-idle` | `--color-text-muted` |
| UNDERSTANDING | `--state-understanding` | `--color-info` |
| PLANNING | `--state-planning` | `--color-info` |
| SEARCHING | `--state-searching` | `--color-primary` |
| EVALUATING | `--state-evaluating` | `--color-secondary` |
| EXECUTING | `--state-executing` | `--color-primary` |
| REPLANNING | `--state-replanning` | `--color-warning` |
| COMPLETED | `--state-completed` | `--color-success` |
| ERROR | `--state-error` | `--color-error` |

### 11.6 Route cards

- Base = Card tokens, plus a **left accent bar** `3px` in the recommendation's status color
  (recommended → `--color-primary`; alternative → `--color-border-strong`).
- Fare/time/distance in **mono** (`--text-mono`).
- Contains a **RouteTimeline** with **TransportLeg** rows (icons per mode).

### 11.7 Agent activity

- Vertical **timeline**: node `12px` circle, connector line `2px` `--color-border`.
- Each step colored by its Agent state token (§11.5).
- Tool-call traces and IDs in **mono**, `--color-text-secondary`, on `--color-surface-sunken`.
- The active step may use `--shadow-glow-primary` (sparingly).

### 11.8 Maps

- Container: `--radius-lg`, `--border-width` `--color-border`, min-height `240px` (mobile) /
  `400px` (desktop).
- **Dark map style** required (matches theme). Route line = `--color-primary`
  (`3px`); alternative = `--color-border-strong` dashed. Markers: origin/destination =
  `--color-secondary`; intermediate = `--color-primary`.

### 11.9 Travel information / Travel Pass

- Distinct "pass" surface: `--color-surface-elevated`, `--radius-2xl`, `--shadow-lg`.
- **Dashed divider** (`--border-width` dashed `--color-border-strong`) between stub and body.
- IDs, times, seat/booking refs in **mono**.
- Reserved QR/offline area: `--color-surface-sunken` box, square, `--radius-md`.
- (Travel Pass **implementation** is Workstream C — this is the *visual contract* only.)

---

## 12. UI Application Guidelines

How to **apply** the tokens above to real screens. (Merged from the former `UI_GUIDELINES.md`.)
The interface must feel **intelligent, reliable, modern, travel-focused, technically
sophisticated, and clear**, and must **communicate the agent's actions**.

### 12.1 Layout & app shell

```
┌───────────────────────────────────────────────────────────┐
│  Header (--header-height): logo · primary action · status    │
├───────────────────────────────────┬───────────────────────┤
│   Main content (fluid, centered)    │  Agent activity rail  │
│   max-width --container-max         │  (--sidebar-width)    │
│   padding --container-padding       │  desktop lg+ only     │
└───────────────────────────────────┴───────────────────────┘
```

- **Desktop (≥ `lg` 1024px):** two-column — main content + persistent **Agent activity rail**.
- **Tablet (≥ `md`):** single column; agent activity collapsible / bottom sheet.
- **Mobile (< `md`):** single column; agent activity in a bottom sheet / expandable card.
- Content **centered** at `max-width: var(--container-max)`, gutters `var(--container-padding)`.
- Header is **sticky** (`--z-sticky`) with a `--color-border` bottom edge. Sections use **flat**
  backgrounds (`--color-bg` / `--color-bg-alt`) — **no gradients**. Cards sit on `--color-surface`
  with `--shadow-sm`.

### 12.2 Grid & spacing

- **12-column** conceptual grid (desktop) → 6 (tablet) → 4 (mobile).
- Gutter `--space-4` (mobile) → `--space-6` (desktop). Use **token gaps** (`--space-*`), never
  fixed pixel gaps.
- Route cards: 1-up (mobile) → 2-up (tablet) → 2–3-up (desktop), or a list in the main rail.

### 12.3 Responsive behavior

- **Mobile-first**: base styles for `< 640px`, enhance at the breakpoints in §6.
- Break the two-column shell at `< lg`; **stack**, don't shrink below readable widths.
- Cap paragraph/explanation measure at `--content-max-width` (`72ch`).

### 12.4 Navigation

- **Header**: RouteWise mark (left), agent state / phase indicator, main CTA (right).
- The MVP is a **single flow** (Landing → Request → Results) — navigation is minimal (logo/home +
  contextual actions); **no deep nav tree**, no breadcrumbs required.
- Active/selected items: `--color-primary-subtle` bg + `--color-primary` text. Full keyboard
  navigation with visible `--color-focus-ring` and logical DOM order.

### 12.5 Forms (travel request)

- **Labels above inputs** (`--text-label`, `--color-text-secondary`) — never placeholder-only.
- Input styling per §11.2 (sunken bg, `--radius-md`, focus → primary border + subtle glow).
- Group related fields in a Card with `--space-5` gaps.
- The **natural-language request field is the hero**: larger (`--text-body-lg`), multiline, with an
  example hint in `--color-text-muted`. Structured refinements (budget, luggage, walking pref,
  times) sit **below** as optional.
- Inline **validation** on blur; error text `--text-body-sm` `--color-error` + error border.
- **Submit** = Primary button, full-width on mobile, right-aligned on desktop.

### 12.6 Buttons & cards (usage)

- **One Primary action per view**; everything else Secondary/Ghost. Sizes: `lg` main submit, `md`
  default, `sm` dense/inline. Loading button keeps width, shows subtle spinner + label, disables.
  Destructive/irreversible actions use **Danger** + explicit confirmation.
- Cards are the primary container (routes, agent steps, summary, pass). **Interactive** cards:
  hover `--shadow-md` + `--color-border-strong`; **selected**: `--color-primary` border +
  `--color-primary-subtle` tint. Title `--text-h3`; support `--text-body-sm`
  `--color-text-secondary`. Don't nest cards more than one level.

### 12.7 Typography hierarchy

Use at most **3–4** levels per screen:
`Display/H1` (screen/hero) → `H2` (section) → `H3` (card title) → `Body/Body-sm` (content) →
`Label` (fields/meta/badges) → `Mono` (fares, times, distances, IDs, logs). Emphasize with
**weight and color**, not extra sizes; never skip levels for effect.

### 12.8 Interface states (always design all four)

- **Loading:** prefer **skeletons** matching final layout (subtle shimmer, `--duration-slower`) —
  **no bouncing spinners**. During agent work the **activity rail is the loading state**; don't
  also show a full-screen spinner.
- **Error:** `--color-error-subtle` bg, `--color-error` border/text, icon, short human message,
  **Retry** (Secondary). Distinguish agent/tool errors (activity rail, `ERROR`), form errors
  (inline), and network errors (banner/toast). No raw stack traces (put detail in a collapsible
  mono block).
- **Empty:** headline (`--text-h3`) + one-line explanation (`--color-text-secondary`) + primary
  action if applicable (e.g., "No routes match your budget yet").
- **Success:** `--color-success` with a **label + icon** (never color alone).

### 12.9 Agent activity visualization (core to this product)

- Render as a **vertical timeline** of **AgentStep** items, each mapped to a canonical Agent state
  ([`AGENT_SPEC.md`](AGENT_SPEC.md)) with its color (§11.5).
- Each step: state icon + label, a short human phrase, and an expandable **mono** tool-call trace
  (`search_routes(...)`).
- **Current** step emphasized (primary glow, subtle pulse); **completed** steps dim to
  `--color-text-secondary` with a check; **failed** steps turn `--color-error`. Auto-scroll to newest.
- End with a **ReasoningSummary** explaining *why* the route won, referencing the user's constraints.
- **Honesty:** only show a step done when it happened; tag mock/simulated data — never present mock
  as real-time (see [`AGENT_SPEC.md` §15–16](AGENT_SPEC.md)).
- Accessibility: region `aria-live="polite"`; current state `role="status"`.

### 12.10 Route presentation

- **Recommended route first**, visually distinct: `--color-primary` left accent bar + "Recommended"
  badge + a one-line **why**. **Alternatives** below as equal-weight cards, each with its trade-off.
- Each **RouteCard** shows total time, total fare (**mono**, LKR), transfers, walking estimate, and
  a **RouteTimeline** of **TransportLeg**s (walk/tuk/bus/train) with per-mode icon + per-leg
  time/fare.
- **DelayBadge** on affected legs (warning = risk, error = major). Show budget fit clearly (under →
  success; over → error + excluded/explained). Surface how constraints are met ("Minimal walking ·
  0.3 km total").

### 12.11 Visual do / don't

| ✅ Do | ❌ Don't |
|-------|---------|
| Use tokens for every value | Hard-code `#hex`, `px`, `rgba` in components |
| Flat surfaces, clear borders | Glassmorphism, blur-heavy panels |
| One primary accent per view | Neon everywhere, rainbow gradients |
| Mono for data | Proportional font for fares/times/IDs |
| Skeletons + live agent rail | Full-screen spinners over content |
| Calm, purposeful motion | Bouncy/decorative animation |
| Real, informative copy | Lorem ipsum, "AI magic ✨" filler |
| Distinct travel product UI | Generic chatbot bubbles as the whole UI |

### 12.12 Copy & tone

Confident, plain, helpful; short sentences; no hype or emoji spam. Speak in the traveler's terms
(budget, time, comfort, luggage, walking). Agent messages are neutral/first-person-plural
("Comparing 3 routes…"). Always **explain decisions** referencing the user's stated constraints and
**state uncertainty honestly** ("Fares are estimates") — never fabricate precision.

---

## 13. Component Registry

The **registry** of shared components. (Merged from the former `COMPONENTS.md`.) This is a *plan
and a rulebook* — **not** a command to build every component now (most are built in phase **A8**).
**Before creating ANY component, check this registry.** If one exists or is planned to satisfy the
need, **reuse it** — do not create a near-duplicate.

### 13.1 Anti-duplication rule

Never create `FancyButton`, `Button2`, `NewButton`, `RouteCardV2`, `MyCard`, `ButtonFinal` if a
registered component already fits. Process:

1. Search this registry. 2. Exists → **use it**; needs a new look → **add a variant/prop**, don't
fork. 3. Planned but unbuilt → build it **here**, in the registered location/name. 4. Genuinely new
& reusable → **add a row here first**, then build. 5. One-off → keep it local to the feature; don't
add generic look-alikes to `components/ui`.

All shared components consume **tokens only** (§1–§11). No magic values.

### 13.2 Directory convention

Shared components live under `frontend/src/components/`, grouped by domain; feature composition
lives in `frontend/src/features/` (see [`ARCHITECTURE.md` §3](ARCHITECTURE.md)).

```
components/
├── ui/      Button 🟩 · Badge 🟩 · Card 🟩 · StatusIndicator 🟩 · Alert 🟩 · Input · Select · Modal · Tooltip
├── agent/   AgentActivity 🟩 · AgentStep 🟩 · AgentStatus 🟩 · ReasoningSummary 🟩
└── travel/  TripForm 🟩 · RouteCard 🟩 · RouteTimeline 🟩 · TransportLeg 🟩 · FareDisplay 🟩 ·
             DelayBadge 🟩 · ModeIcon 🟩 · TravelRequestSummary 🟩 · TravelPass 🟥 (Workstream C)
```

**A8 realization.** Components ship as **flat files inside their domain group** (`ui/`, `agent/`,
`travel/`) — not one subfolder each: `ComponentName.tsx` + `ComponentName.css` (tokens only), with a
single `index.ts` **barrel** per group. **PascalCase** components; presentational components hold
**no** business logic. Per-component `ComponentName.test.tsx` is **deferred**: A8 added **no** test
runner (kept dependency-light per [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) rule 9 and the A8
"no new dependencies" constraint), so the UI behaviors are verified by `tsc --noEmit` (strict) + the
production build + the backend suite + manual DOM checks; a runner (Vitest + RTL) lands only when
the team chooses to add that dependency.

### 13.3 Registry

Status: 🟥 **Planned** (not built) · 🟩 **Built** · 🟨 **Partial**. All were 🟥 during **A1**; **A8
built the agent-experience set** (🟩 below) and left the not-yet-needed primitives (Input, Select,
Modal, Tooltip) plus the Workstream-C `TravelPass` 🟥. `Alert`, `ModeIcon` and
`TravelRequestSummary` were **added to this registry in A8** (§13.5) before being built.

**`ui/` — primitives**

| Component | Purpose | Key props (conceptual) | Notes |
|-----------|---------|------------------------|-------|
| 🟩 **Button** | All actions | `variant`, `size`, `loading`, `disabled`, `fullWidth` | One primary per view (§11.1). |
| 🟥 **Input** | Text/number fields | `label`, `value`, `onChange`, `error`, `hint`, `type`, `required` | Label above; never placeholder-only. A8 `TripForm` uses a styled multiline `<textarea>` directly (the §12.5 hero NL field), so a single-line `Input` was not needed yet. |
| 🟥 **Select** | Enumerated choices | `label`, `options`, `value`, `onChange`, `error` | Native `<select>` styled or a11y listbox. |
| 🟩 **Card** | Primary container | `as`, `title`, `titleId`, `lead`, `actions` | §11.3; renders `.panel`, wired with `aria-labelledby` via `useId`. |
| 🟩 **Badge** | Status/label pills | `tone`, `mono` | Subtle bg + colored text + label; spreads native props (e.g. `title`). |
| 🟩 **Alert** | Inline state banner | `tone`, `title`, `hint`, `icon`, `role` | **New in A8** (§13.5): the §12.8 error / clarification / offline banner — icon + label, never color-only. |
| 🟥 **Modal** | Dialogs/confirmations | `open`, `onClose`, `title`, `footer` | `--z-modal`, focus trap, ESC. |
| 🟥 **Tooltip** | Contextual hints | `content`, `placement` | `--z-tooltip`; keyboard friendly. |
| 🟩 **StatusIndicator** | Colored dot + label | `state`, `label`, `pulse` | Shared primitive behind agent/connection status; `data-state` + `data-pulse`; never color-only. |

**`agent/` — agent visualization**

| Component | Purpose | Key props (conceptual) | Notes |
|-----------|---------|------------------------|-------|
| 🟩 **AgentActivity** | Activity rail/timeline container | `actions[]`, `busy` | §12.9 timeline of `AgentStep`s + a progress **stepper** derived from real visited states; skeleton while `busy`. |
| 🟩 **AgentStep** | One timeline step | `action` | One `agent_actions[]` entry: state color + label, human phrase, expandable **mono** tool trace with ✓/✗ from real `status`. |
| 🟩 **AgentStatus** | Compact current-state chip | `state`, `busy` | Maps state → color/label; honest indeterminate **"Working…"** while `busy` (single-shot API — no faked stage, §12.8). |
| 🟩 **ReasoningSummary** | Human decision explanation | `summary` | Shown at COMPLETED; "In short: …". |

**`travel/` — domain components**

| Component | Purpose | Key props (conceptual) | Notes |
|-----------|---------|------------------------|-------|
| 🟩 **TripForm** | Capture the request (§12.5 hero NL field) | `onSubmit`, `initialValue`, `submitting`, `disabled`, `error` | Multiline hero `<textarea>` + example hint + Primary submit; inline empty/error validation. |
| 🟩 **RouteCard** | Present one route | `route`, `recommended`, `legs` | Left accent bar (recommended); metrics grid + `RouteTimeline` + reasons / strengths / trade-offs / structured violations. One component for recommended **and** alternative. |
| 🟩 **RouteTimeline** | Ordered legs | `legs[]` | Renders `TransportLeg`s as an `<ol>`. |
| 🟩 **TransportLeg** | One leg | `leg` | Per-mode `ModeIcon`; mono duration/fare/walk; per-leg `DelayBadge`. |
| 🟩 **FareDisplay** | Fare/budget figure | `amount`, `currency`, `budgetStatus` | **Mono**; color by budget fit (within → success, over → error). |
| 🟩 **DelayBadge** | Delay risk | `level`, `minutes` | Thin `Badge` wrapper: warning/error/success tones + text; hidden when `none`. |
| 🟩 **ModeIcon** | Transport-mode glyph (§13.4 icon set) | `mode` | **New in A8**: the §13.4 walk/tuk/bus/train/taxi/ferry set as inline stroke SVGs + a direction-arrow fallback; `aria-hidden`. |
| 🟩 **TravelRequestSummary** | Parsed-request recap | `request` | **New in A8** (§13.5): read-only `<dl>` of the understood `TravelRequest` (origin/destination/budget/luggage/walking/times) + any `assumptions`. |
| 🟥 **TravelPass** | Offline pass (**visual contract only**) | `pass`, `legs[]`, `refs` | Workstream **C** implements generation — **not** built in A8. |

### 13.4 Shared building blocks (behind the components)

- **Transport-mode icons** — one set for `walk, tuk, bus, train, taxi, ferry`; reused by
  `TransportLeg`, maps, timeline. **A8:** realized as `components/travel/ModeIcon` (inline stroke
  SVGs + a fallback glyph).
- **Agent-state → color/label map** — single source (§11.5 + [`AGENT_SPEC.md`](AGENT_SPEC.md));
  consumed by `StatusIndicator`, `AgentStep`, `AgentStatus`. **A8:** labels + canonical order live in
  `services/agentState.ts` (`STATE_LABELS`, `PROGRESS_STAGES`, `visitedStates`); colors are applied in
  CSS via `data-state` + the `--state-*` tokens (never chosen in TS).
- **Formatters** — LKR currency, durations (`3h 20m`), times, distances (km). Live in frontend
  **services/utils**, not inside components. **A8:** implemented in `services/format.ts`
  (`formatMoney`, `formatLkr`, `formatMinutes`, `formatKm`, `describeError`).

### 13.5 Adding to this registry

1. Confirm no existing/planned component fits (§13.1). 2. Propose name, group (`ui`/`agent`/
`travel`), purpose, key props. 3. Add a row in §13.3 (status 🟥). 4. Build in the registered
location using **tokens only**. 5. Add tests; flip to 🟩 when shipped. 6. Update this file in the
**same change** — the registry must never drift from reality.

> **Rule:** if a component isn't in this registry, it doesn't exist as a shared component.

---

## 14. Accessibility

- Text contrast ≥ **4.5:1** (AA) for body, ≥ **3:1** for large text and UI components.
- Non-text status (color) is **always** paired with a label or icon — never color alone.
- Visible keyboard focus on every interactive element (`--color-focus-ring`).
- **Semantic HTML**: `<button>` for actions, `<nav>`/`<main>`, headings in order, `label` for inputs.
- **ARIA for dynamic agent activity**: region `aria-live="polite"`; current state `role="status"`.
- Touch targets ≥ **44×44px** on mobile (buttons sm are `32px` — desktop-only).
- Motion honors `prefers-reduced-motion`.

---

## 15. Golden rules

1. **No magic values.** If it's not a token, it doesn't ship.
2. **Add tokens here first**, then in `tokens.css`, then use them.
3. **One accent for live agent activity** (primary glow). Everything else stays calm.
4. **Data is mono.** Fares, times, distances, IDs, logs.
5. **Color is never the only signal** — pair with text/icon.
6. **Keep this doc and `tokens.css` in sync** in the same commit.
