# Frontend design system — Swiss Clinical Minimalist

The web workstation is a light-theme clinical product UI, not a sci-fi HUD. It has three
top-level views behind a persistent 64px sticky header:

1. `01. Crew Workstation` — **`/`, the boot route**: a live astronaut-in-seat cockpit.
   `/workstation` redirects here.
2. `02. Overview` — `/overview`, explaining the mission problem in about 15 seconds.
3. `03. ML Architecture & Docs` — `/docs`, specifications, measured benchmarks, thresholds
   and audit ledger.

The browser uses relative `/api/...` URLs only. The cockpit is SSE-first (`state` channel at
1 Hz) with a 2 s polling fallback and 20 s live resync; the backend owns the mission clock.

## Tokens

| Token | Value | Use |
|---|---|---|
| page | `#F8FAFC` | app background |
| card | `#FFFFFF` | panels, `1px solid #E2E8F0`, shadow `0 1px 3px rgba(15,23,42,0.04)` |
| ink | `#0F172A` | headings |
| ink-body | `#475569` | body copy |
| ink-label | `#94A3B8` | uppercase micro labels |
| primary | `#0F172A` / `#1E293B` | primary actions |
| primary-blue | `#2563EB` | links / focus only |
| nominal | `#10B981`, bg `#ECFDF5`, text `#065F46` | semantic nominal state |
| watch | `#F59E0B`, bg `#FFFBEB`, text `#92400E` | semantic watch / simulated fallback |
| critical | `#EF4444`, bg `#FEF2F2`, text `#991B1B` | semantic alert state |
| neutral | `#94A3B8`, bg `#F1F5F9`, text `#475569` | unknown / not available |

Typography: **Inter** for UI/headings/body; **JetBrains Mono** only for numbers, units,
formulas and SHA-256 hashes (`.num`, tabular numerals). Both are self-hosted via
`@fontsource`, Latin subset only. No CDN fonts. The palette is roughly 90% monochrome;
colour is reserved for semantic clinical states and primary actions.

## Layout

- **Header:** 64px sticky. Left: `HYPERION-MDA` + `NASA Space Apps · Crew Health` pill.
  Center: segmented `01 / 02 / 03` navigation. Right: provenance pill with a Radix popover
  that lists OSD-575 / GOES / WESAD availability and switches real vs simulated mode.
- **Overview:** eyebrow, 36px headline, 680px subtitle, two CTAs, three problem→solution
  cards, and a clickable four-step architecture strip with two-sentence summaries.
- **Crew Workstation:** a control strip (LIVE 1.0 Hz clock, Pause/Play, Step +10 s, Reset
  Case, five sim lanes + recorded replay selector, habitat/comms, rover blackout, SSE health)
  above an explicit amber simulation banner. The workspace is a 3/5/4 grid on `xl`:
  left = body map + organ detail + provenance panel; centre = S0–S4 lifecycle banner, live
  gate strip, one telemetry chart, gate/triage tabs; right = always-visible instrument bay
  (PVT / Eye ONSD / Vitals, auto-focused on an S2 hold) + store-and-forward comms outbox
  with SBAR drawer and explicit demo flight-surgeon acknowledgement.
- **Docs:** four spec cards, requested benchmark matrix, the measured FL/DP panel rendered
  from `artifacts/fl_dp_benchmark_results.json` (regimes, CIs, σ sweep, Byzantine faults,
  window-level threat model), measured M6 rows, six-organ demo threshold table, five
  official NASA/CSA links, and the local SHA-256 audit ledger. No chart is rendered here.

## Components

- Bespoke `Card`, `Button`, `Badge`, `StatusDot`, `Gauge`, `Tabs`, `MetricTile`,
  `ErrorNotice`, `EmptyState` and `PageSkeleton` primitives in `components/ui.tsx`.
- Radix Popover supplies accessible provenance-popover behaviour. Motion supplies only
  the view transition; `MotionConfig reducedMotion="user"` remains enabled.
- Icons: `lucide-react`, thin clinical stroke.
- Charts: exactly one Recharts `ComposedChart` on screen at a time (Tab A only): raw HR
  slate line, residual emerald line, shaded demo residual band, four context metric pills.
  The chart is mounted only after its container has a measured width, avoiding zero-size
  console warnings.

## Motion

- View transitions: opacity + `translateY(6px)`, 280ms, `cubic-bezier(0.16,1,0.3,1)`.
- Selected organ: SVG pulse ring.
- Gate steps: sequential 450ms pulse on scenario change / crew check (`revision` key).
- Freshness / readiness bars: `width 500ms ease`.
- `prefers-reduced-motion` collapses animations and transitions.

## Data honesty preserved

- Unknown / stale / missing never render green and never become `0`; they render `—`,
  `UNKNOWN` or `NOT_AVAILABLE`.
- Simulated fallback is unmistakably labelled in the header pill and amber workstation banner.
- Real mode never invents telemetry; without a live wearable it shows `NOT_AVAILABLE`.
- Gate 2 uses per-person normalized activity, not raw ENMO grams; the UI says so.
- Demo thresholds are labelled as demo rules, not NASA-STD-3001 compliance.
- Unimplemented ML/DP benchmarks show `NOT_IMPLEMENTED` / dashes, never invented metrics.
- The audit ledger is a local SHA-256 hash chain: no EVM transaction, no deployed contract,
  no raw measurements.

## Dependencies

React 18.3, React Router 7.18, Vite 7.3, Vitest 4.1, Tailwind 3.4, Recharts 2.15,
Motion 14, Radix Popover, Lucide, clsx + tailwind-merge, `@fontsource/inter` and
`@fontsource/jetbrains-mono`. The old rail / command palette / dialog / tabs / cmdk
dependencies were removed. `npm ci` is reproducible; `npm audit` reported 0 vulnerabilities.

## Verification

| Check | Result |
|---|---|
| `tsc --noEmit` | exit 0 |
| `vitest run` | 27 passed (8 files), including zero-console-error assertions |
| `vite build` | OK, code-split JS/CSS + self-hosted fonts |
| `tests_api` | 70 passed |
| full Python suite | 234 passed / 49 skipped / 128 subtests |
| M6 verifier | 1187 checks passed |
| HTTP smoke | 42/42 against the running single-port server |

No browser binary was available, so interaction coverage uses jsdom + React Testing
Library and HTTP smoke checks — not a real-browser screenshot or Playwright run.
