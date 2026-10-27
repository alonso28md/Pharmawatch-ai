---
version: 1
name: PharmaWatch Clinical
description: Design system for the PharmaWatch AI decision-support interface (medical device vigilance).
colors:
  light:
    canvas: "#F6F5F2"
    surface: "#FFFFFF"
    surface-raised: "#FBFAF8"
    surface-sunken: "#EFEDE8"
    border: "#DFDCD5"
    border-strong: "#C9C5BC"
    text: "#1B1F23"
    text-muted: "#565C63"
    text-subtle: "#6B7178"
    accent: "#0E5C70"
    accent-hover: "#0A4757"
    accent-contrast: "#FFFFFF"
    focus: "#0E5C70"
    ok: { fg: "#22603A", bg: "#E5F1E8", border: "#B8D7C1" }
    serious: { fg: "#7A4F00", bg: "#FBF0D8", border: "#E9CC8B" }
    critical: { fg: "#9E2227", bg: "#FBE7E6", border: "#EDB9B6" }
    escalation: { fg: "#39437D", bg: "#E8EAF5", border: "#BCC1E2" }
    info: { fg: "#2C4F66", bg: "#E6EEF3", border: "#BACFDC" }
  dark:
    canvas: "#111315"
    surface: "#181B1E"
    surface-raised: "#1E2125"
    surface-sunken: "#0C0E10"
    border: "#2C3136"
    border-strong: "#3B4148"
    text: "#E9E7E2"
    text-muted: "#A6AAAF"
    text-subtle: "#8E9398"
    accent: "#5DB4C8"
    accent-hover: "#7CC4D5"
    accent-contrast: "#0B1416"
    focus: "#7CC4D5"
    ok: { fg: "#8FD0A2", bg: "#14261A", border: "#2C4A35" }
    serious: { fg: "#E9C276", bg: "#2A2111", border: "#4D3C1C" }
    critical: { fg: "#F0A19D", bg: "#2C1514", border: "#552927" }
    escalation: { fg: "#AEB6EC", bg: "#1A1D33", border: "#353C66" }
    info: { fg: "#9EC3DA", bg: "#14212A", border: "#2A4152" }
typography:
  sans: "Public Sans Variable"
  mono: "JetBrains Mono Variable"
  scale: { caption: "12/16", small: "13/18", body: "15/22", body-lg: "16/24", title-sm: "18/24", title: "22/28", display: "30/36" }
rounded: { sm: 4, md: 6, lg: 10, full: 9999 }
spacing: { base: 4, steps: [0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64] }
motion:
  duration: { instant: 80, fast: 140, base: 200, route: 220, slow: 360, counter: 700 }
  easing: { standard: "cubic-bezier(0.2, 0, 0, 1)", exit: "cubic-bezier(0.4, 0, 1, 1)", enter: "cubic-bezier(0, 0, 0, 1)" }
---

# PharmaWatch Clinical — design system

Interface for vigilance staff and hospital device safety officers who triage medical
device incidents under MDR 2017/745. People use it while deciding whether and when to
notify an authority, so the system optimises for **legibility, calm and unambiguous
state** over decoration.

Method adapted from the IBM/Carbon DESIGN.md in VoltAgent/awesome-design-md (tokens
named by role, scales, states as named variants, density rules). Colours, type and
voice are our own. App-screen rules follow the `taste` skill (references/app-screens);
interaction and accessibility rules follow Vercel's Web Interface Guidelines.

## 1. Principles

1. **One question per screen.** The largest element answers it (triage: *what must be
   reported, to whom, by when — or why a human must decide*).
2. **Colour belongs to data and state**, not chrome. Chrome is neutral; the single
   accent marks the primary action, links and focus.
3. **State is never colour alone.** Every status carries an icon *and* a text label.
4. **Nothing invented.** Every figure comes from the backend or a stored evaluation
   file. Unknown data shows a dash; loading shows flat placeholders of real size.
5. **Calm, not alarming.** Serious incidents read as firm and clear, never flashing.

## 2. Colour

Roles, not hues. Light and dark themes share role names (`--pw-<role>`).

| Role | Usage |
|---|---|
| `canvas` | App background (behind the dynamic field) |
| `surface` | Panels, cards, form fields |
| `surface-raised` / `surface-sunken` | One tone step above/below a surface; separates regions without shadows |
| `border` / `border-strong` | 1px structure; `border-strong` for inputs |
| `text` / `text-muted` / `text-subtle` | Running text ≥ 4.5:1; muted for secondary; subtle only ≥ 14px |
| `accent` | Primary action, links, focus ring, the one highlighted series in a chart |

**Semantic roles** (each has `fg`, `bg`, `border`; text on `bg` ≥ 4.5:1):

| Role | Meaning | Icon | Example label |
|---|---|---|---|
| `ok` | Non-serious / not reportable / healthy | check-circle | "Not reportable" |
| `serious` | Serious incident with a reporting deadline | alert-triangle | "Serious · 15 days" |
| `critical` | Death, public health threat, 5xx errors | octagon-alert | "Death · 10 days" |
| `escalation` | Decision withheld for a human (blocking) | hand | "Human decision required" |
| `escalation` outline | Determination kept, flagged for review (advisory) | info | "Review advised" |
| `info` | Neutral notices, provenance | info | "Extracted from text" |

Blocking vs advisory escalation must be distinguishable without colour: blocking uses a
filled tint with a left bar and the *hand* icon; advisory uses an outline and the *info*
icon. Red is reserved for death / public health threat and system errors; amber for
other serious incidents. Avoid violet/indigo anywhere else.

## 3. Typography

- **Public Sans Variable** for everything (UI, body, figures with `tabular-nums`).
- **JetBrains Mono Variable** only for identifiers and code: incident IDs, citation
  labels `[C3]`, chunk IDs, API keys.
- Scale (size/line-height px): caption 12/16 · small 13/18 · body 15/22 · body-lg 16/24 ·
  title-sm 18/24 · title 22/28 · display 30/36. At most five sizes per screen.
- Sentence case for headings and labels. No letter-spaced uppercase eyebrows.
- Numbers that update or compare use `tabular-nums`; ellipsis `…`; curly quotes.

## 4. Layout and spacing

- 4px base; steps 4·8·12·16·20·24·32·40·48·64.
- Shell: labelled sidebar 232px (collapses to a top bar < 960px), content column max
  1200px, side padding 24px desktop / 16px phone. Equal gutters both ways.
- Every block has a header and shows its first rows at 1440×900.
- Density: medium (rows 44–52px, padding 16–20px). Tables: right-aligned tabular
  numbers, grey sentence-case headers, rules not stripes, dash for missing values.
- Breakpoints: phone < 640 · tablet 640–1023 · desktop ≥ 1024.

## 5. Shape and elevation

| Token | Value | Use |
|---|---|---|
| `rounded.sm` | 4px | Badges, chips |
| `rounded.md` | 6px | Buttons, inputs (default) |
| `rounded.lg` | 10px | Panels, sheets |
| `rounded.full` | — | Deadline ring, avatars only |

Elevation levels: **0 flat** (canvas) · **1 border** (panels) · **2 tone step**
(raised/sunken) · **3 overlay** (dialogs, sheets, toasts: the only shadowed elements).

## 6. Motion

| Token | ms | Use |
|---|---|---|
| `instant` | 80 | Press feedback |
| `fast` | 140 | Hover, focus, toggles |
| `base` | 200 | Panels, toasts, layout changes |
| `route` | 220 | Page transitions (≤ 250) |
| `slow` | 360 | Deadline ring, result reveal |
| `counter` | 700 | Animated figures (once, on first reveal) |

Easing: `standard` for movement, `enter` for appearing, `exit` for leaving. Animate only
`transform` and `opacity` (and canvas drawing). All motion is interruptible.
**Reduced motion** (OS setting or app setting): durations 0, no counters, background
static, route changes cross-fade only.

## 7. Dynamic background ("pulse field")

A low-contrast canvas behind content: a soft two-tone field plus one faint ECG-like
trace. It reflects **real application state** (request lifecycle and results), never a
timer.

| State | Trigger | Tint | Trace |
|---|---|---|---|
| `idle` | default | teal-green, very low | slow (≈ 48 per minute) |
| `processing` | a request in flight | teal | faster, flowing (≈ 90) |
| `ok` | non-serious / answered | green glow fading in 1.2s | settles to idle |
| `serious` | serious determination | soft amber | steady, firm (≈ 70) |
| `escalated` | blocking escalation | muted indigo | slow, steady |
| `error` | request failed | grey, small red accent | flat with a single blip |

Rules: opacity ≤ 0.10 behind text (contrast unaffected, AA 4.5:1 verified on
surfaces), ≤ 60 fps, paused when the tab is hidden, static under reduced motion.

## 8. Components

`AppShell` · `SideNav` · `TopBar` · `DisclaimerBar` · `PageHeader` · `Panel`
(header, body, empty/loading/error variants) · `Button` (primary, secondary, ghost,
danger; sizes sm/md; states hover/pressed/focus/loading/disabled) · `IconButton` ·
`Input` · `Textarea` (counter, inline error) · `Select` · `Switch` · `Tabs` ·
`Tooltip` · `Sheet` (side panel) · `Toast` · `Badge` (semantic variants) ·
`SeverityBadge` · `EscalationNotice` (blocking/advisory) · `ProvenanceTag` ·
`DeadlineRing` · `Stat` (label above value) · `MetricRow` (value vs threshold, min–max) ·
`Skeleton` (flat, real size) · `CitationChip` · `SourcePanel` · `DataTable` ·
`ChartFrame` (title, single series, accessible table fallback).

States are named variants (`Button/primary/loading`), not ad-hoc styles.

## 9. Accessibility

- Contrast: text ≥ 4.5:1, large text and UI boundaries ≥ 3:1 in both themes.
- Visible `:focus-visible` ring (2px accent, 2px offset) on every interactive element.
- Full keyboard path; skip link to main content; headings in order.
- Live results announced with `aria-live="polite"`; errors associated with fields.
- Touch targets ≥ 40px (44px on phone). Never block zoom or paste.
- Charts always have a text/table equivalent.

## 10. Voice

Sober and specific, second person, no marketing. Say what happened and what to do
next ("The model service is unavailable. Try again in a minute."). Always show:
"Decision-support tool. Requires human review. Do not enter patient-identifying data."

## 11. Do / Don't

Do: neutral chrome, one accent, real data, dashes for unknowns, honest weak metrics.
Don't: gradients, glows, glass, neon, emoji, icons in tinted squares, rows of identical
cards, invented figures, fake agent steps, colour-only status, shadows on resting
elements.
