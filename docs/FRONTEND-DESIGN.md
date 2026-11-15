# Frontend design system — HYPERION-MDA workstation

The workstation UI is a bespoke, instrument-grade SaaS dashboard. It is deliberately
**not** a generic admin template: no purple/indigo gradients, neon glows, floating blobs,
equal-width stat-card rows or thick drop shadows. The reference feel is Linear / Raycast /
Swiss instrumentation.

## Tokens

| Token | Value | Use |
|---|---|---|
| `base` | `#0B0C0E` | app background |
| `surface` | `#13151A` | panels |
| `surface-2 / surface-3` | `#181B21 / #1E222A` | elevated inputs, hover |
| `hairline` | `rgba(255,255,255,0.07)` | all 1px borders |
| `accent` | `#F59E0B` (Signal Amber) | primary actions and active states only |
| `ink / secondary / muted / faint` | `#E7E9EC / #9CA3AC / #6B7280 / #4B5158` | text hierarchy |
| `state.ok / watch / alert / unknown / info` | `#3FB950 / #DB6D28 / #F85149 / #6E7681 / #58A6FF` | semantic status, distinct from the accent |

Typography: **Plus Jakarta Sans** for UI/headings, **JetBrains Mono** with
`font-variant-numeric: tabular-nums` for every number, timestamp, status badge and table
cell (`.tnum`). Both fonts are self-hosted via `@fontsource`, Latin subset only — no CDN.
No Inter / Roboto / Arial / Open Sans.

## Layout

- **Rail:** 220px expanded, 64px collapsed, animated width. Workspace block, active pill
  (`layoutId`), `G D` / `G C` / `G H` / `G A` / `G O` / `G R` chord indicators, active
  subject readout. Collapse state persists in `localStorage`. Hidden below `md`; a compact
  mobile nav replaces it.
- **Command topbar:** 52px. Breadcrumb, ⌘K trigger, date-range `Segmented`
  (`30s / 2m / 5m / All`), habitat + demo-role selectors, live/offline dot, one primary CTA.
- **Overview bento:** asymmetric grid, telemetry canvas ≈65% and live activity feed ≈35%
  on `xl`, stacking cleanly on tablet/mobile. Metrics live inline in the chart header, not
  in floating boxes. Full-width gate-verdict table below with sticky headers, row-hover
  quick actions and a row-click slide-over drawer.
- **Honesty strip + footer:** lane provenance is always visible; the footer carries
  “Demo thresholds, not clinically validated. Not a medical device.”

## Components

Radix UI supplies the accessible behaviour; Motion supplies only the visual transition.

- `DialogShell` (Radix Dialog) backs `Dialog`, `Drawer` and the command palette: focus
  trap, focus restore, Escape, outside-click, `aria-hidden` on the rest of the app.
- `Tabs` (Radix Tabs) gives roving focus + arrow keys and a Motion shared underline.
- `CommandPalette` uses `cmdk` for fuzzy command/scenario/subject/role search.
- `Button` is a `motion.button` with `scale(0.98)` press state and `type="button"` by
  default so it never submits a form accidentally.
- `Segmented`, `Badge`, `StatusDot`, `Table/Th/Td`, `InlineMetric`, `Skeleton`,
  `AlertBanner`, `EmptyState` are bespoke hairline primitives. Semantic tone is exposed as
  `data-tone` so tests assert meaning, not colour classes.
- Icons: `lucide-react` at stroke width **1.75**.
- Charts: Recharts with hairline gridlines, a custom crosshair tooltip and
  `accessibilityLayer` for keyboard traversal.

## Motion

One physics contract in `lib/motion.ts`: springs `stiffness: 400, damping: 32`, crisp ease
`cubic-bezier(0.16, 1, 0.3, 1)`, 40ms staggered mount with 6px translate + fade,
`layoutId` shared indicators, smooth accordion height, dimension-matched skeleton shimmer.
`MotionConfig reducedMotion="user"` plus a CSS `prefers-reduced-motion` block disable
animation for users who ask for it. Nothing bouncy or sluggish.

## Data honesty preserved

- Unknown / stale / failed / unavailable never render green and never become `0`; they
  render as text (`Not available`, `—`, `UNKNOWN`).
- Lane badge and provenance explanation are persistent.
- Non-rate findings are never suppressed; the UI states this explicitly.
- Action text is restricted to the four non-treatment strings.
- Roles are a demo-grade switcher, not authentication; the UI says so.

## Dependencies & security

React 18.3, React Router 7.18, Vite 7.3, Vitest 4.1, Tailwind 3.4, Recharts 2.15,
Motion 14, Radix Dialog/Tabs, cmdk, Lucide. `npm ci` is reproducible and `npm audit`
reported **0 vulnerabilities** at the time of the redesign. Recharts 2.x is pinned
deliberately (3.x is a breaking migration); npm’s deprecation notice is expected.

## Verification

| Check | Result |
|---|---|
| `tsc --noEmit` | exit 0 |
| `vitest run` | 34 passed (5 files) |
| `vite build` | OK, 4 JS/CSS chunks + self-hosted fonts |
| `tests_api` | 57 OK |
| `tests/` (core, unchanged) | 170 OK, 30 skipped |
| smoke on :5173 and :8000 | 26/26 each |
| `npm audit` | 0 vulnerabilities |

No browser binary was available, so this was verified with jsdom component renders,
strict typecheck, production build and HTTP smoke checks — **not** a real-browser
screenshot or Playwright run.
