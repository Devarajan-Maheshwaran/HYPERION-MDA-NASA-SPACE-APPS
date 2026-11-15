# Workstation runbook (API + React frontend)

**What this is:** a runnable research prototype of the crew-health workstation from
`HYPERION_MDA.pdf`, built as React 18 + TypeScript strict + Vite + Tailwind + Radix
Popover + Motion + Recharts over a FastAPI composition layer. The UI follows
[docs/FRONTEND-DESIGN.md](FRONTEND-DESIGN.md): a Swiss Clinical Minimalist light theme
with exactly three views — Overview, Crew Workstation, ML Architecture & Docs.

**What it is not:** a medical device. No clinical validation, no NASA approval, no flight
readiness. Demo thresholds throughout. Read `docs/SAFETY_ISSUES.md` before presenting it.

---

## 1. Install

The desktop app stays standard-library only. The API needs its own virtualenv.

```bash
python -m venv .venv-api
# Windows: .venv-api\Scripts\activate
. .venv-api/bin/activate
pip install -r requirements-api.txt
```

```bash
cd web
npm ci          # reproducible install from package-lock.json
```

## 2. Run

**One command (bootstrap + build + launch):**

```bash
bash run_workstation.sh
# open http://localhost:8000
```

`backend_api.py` is the single-process entrypoint. It serves the built React SPA and the
unified `/api/state`, `/api/scenario`, `/api/exams/*` endpoints on the same origin — no CORS,
no separate frontend server. If `web/dist` is missing it runs `npm ci` / `npm run build` first.

Already installed? Launch directly:

```bash
.venv-api/bin/python backend_api.py
# open http://localhost:8000
```

Development (hot reload, two terminals):

```bash
# terminal 1
.venv-api/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
# terminal 2
cd web && npm run dev          # http://localhost:5173
```

The browser only ever requests relative `/api/...`; Vite proxies those to port 8000. No
browser-facing code addresses `localhost`.

Optional audit persistence (otherwise the chain is in-memory and clears on restart):

```bash
HYPERION_AUDIT_LOG=/tmp/hyperion-audit.jsonl .venv-api/bin/python backend_api.py
```

Optional real-data cache:

```bash
HYPERION_MDA_DATA_DIR=/path/to/cache .venv-api/bin/python backend_api.py
```

## 3. Navigation

- The app lands on **Overview** (`/`): a 15-second mission explanation, three problem→solution
  cards, and a clickable architecture strip. The primary CTA opens the Crew Workstation.
- A persistent 64px sticky header switches between `01. Overview`, `02. Crew Workstation`
  (`/workstation`) and `03. ML Architecture & Docs` (`/docs`).
- The right-hand provenance pill opens a popover with OSD-575 / GOES / WESAD availability
  and switches between Real Empirical Data and explicitly labelled Simulated Scenario Fallback.
- **Crew Workstation** is a 40/60 layout: six-node body map + organ detail on the left;
  Tab A (3-stage gate, one chart, triage) and Tab B (readiness + PVT / ultrasound / vitals)
  on the right. Habitat pills and five scenario buttons sit above the workspace.
- **Docs** contains model specs, requested benchmarks with explicit provenance, measured M6
  rows, demo threshold tables, official NASA/CSA links and the local SHA-256 audit ledger.

## 4. First run — the honest path

1. Open the app. It lands on **Overview**. Click **Launch Live Crew Workstation**. The
   workstation shows the amber **SIMULATED SCENARIO FALLBACK ACTIVE** banner; the seeded
   `nominal-orbital` scenario is an explicitly labelled non-flight simulation.
2. Select **Exercise Bout Blocks False Alarm**. Raw HR rises toward ~148 bpm while the
   residual stays near zero. Gate 2 shows **BLOCK** and the amber false-alarm shield appears.
   Triage is **WATCH / ONBOARD COUNTERMEASURE**, not a surgeon alert.
3. Select **High CO₂ + SANS Eye Risk**. Gate 3 shows **HOLD** and recommends the guided eye
   ultrasound. Click **Open Recommended Crew Check**, use the 6.1 mm sample or a scaled
   upload, and save. The UI returns to Tab A and re-animates the gates.
4. Select **Solar Radiation Spike**. The demo chest/immune rule escalates to the flight
   surgeon. The Docs page shows the cosine-median toy demo catching the simulated silo-2 bit-flip.
5. Select **Blood Sugar & Sleep Drift**. Metabolic goes WATCH and Brain & Sleep goes ALERT.
   Run the reaction test or log vitals from Tab B; saved checks refresh their freshness weights.
6. Open the provenance pill and switch to **Real Empirical Data**. The lab/GOES/WESAD lanes
   show available or NOT AVAILABLE. Without a live astronaut wearable, telemetry is
   `NOT_AVAILABLE` and no simulated frames are shown.
7. Open **ML Architecture & Docs**. Unimplemented benchmarks show dashes / `NOT_IMPLEMENTED`;
   the audit ledger shows local SHA-256 blocks and explicitly says there is no EVM transaction.

The underlying API still exposes the older safety scenarios (`uncalibrated`, `hard-ceiling`,
`hold-timeout`, `sensor-artifact`, `exercise-with-arrhythmia`, etc.) and role-gated endpoints;
they remain covered by `tests_api` and `scripts/smoke_workstation.py`.

### Scenarios worth showing

| Scenario | What it proves |
|---|---|
| `uncalibrated` | All gates UNKNOWN. Nothing green. No default threshold ships. |
| `exercise-false-alarm` | Gate 2 blocks the deck's core false alarm. |
| `exercise-with-arrhythmia` | Suppression never hides a non-rate finding. |
| `hard-ceiling` | Above 180 bpm, movement never explains the rate. |
| `hold-timeout` | Suppression latches off after 120 s and escalates. |
| `sensor-artifact` | Gate 1 quarantines the window → "Check sensor". |
| `stale-manual` | Gate 3 holds the ground alarm and asks for a crew check. |

## 5. Roles

The role selector is **demo-grade and not authentication**. Anyone can pick any role.

| Role | Can |
|---|---|
| Crew | Workstation, manual checks, PVT/ultrasound/vitals exams, run scenarios |
| Flight surgeon | Everything above + acknowledge alerts, read audit and lab data |
| Ops | Calibrate, run scenarios, refresh GOES, read lanes and audit |
| Researcher | Read-only state/docs, M6 results, registry, provenance, audit; cannot run scenarios or acknowledge |

The rebuilt UI defaults to the crew role and does not expose a role switcher; roles remain
demo-grade `X-Role` headers on the unchanged API, not authentication.

## 6. Tests

```bash
# existing suites, unchanged
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python -m unittest discover -s experiments/m6/tests
python experiments/m6/verify_m6.py

# API suite (70 tests, pytest)
.venv-api/bin/python -m pytest tests_api -q

# full Python suite (core + API + M6)
PYTHONPATH=src .venv-api/bin/python -m pytest tests tests_api experiments/m6/tests -q

# web: strict typecheck, 27 unit/DOM tests, production build
cd web && npm run typecheck && npm test && npm run build

# end-to-end against a RUNNING server (42 checks)
python scripts/smoke_workstation.py --base http://127.0.0.1:8000
```

## 7. Real data lanes

Both real lanes report **Not available** until their cache exists. Nothing is substituted.

```bash
PYTHONPATH=src python -m hyperion_mda.osdr_fetch        # NASA OSD-575, SHA-256 verified
PYTHONPATH=src python -m hyperion_mda.physionet_fetch   # PhysioNet, 59 files verified
```

Set `HYPERION_MDA_DATA_DIR` to point at an existing cache. The header provenance popover
shows OSD-575 / GOES / WESAD availability; **ML Architecture & Docs** shows the committed,
independently verified M6 offline results. The unchanged `/api/lab/osd575` endpoint still
returns the verified rows.

## 8. Known limits

- No browser binary was available in the build environment, so the UI was verified with
  jsdom component renders, a strict typecheck, a production build and HTTP smoke checks —
  **not** with a real-browser screenshot or Playwright run.
- Frontend state is process-local on the server; restarting the API clears calibrations,
  checks and alerts unless `HYPERION_AUDIT_LOG` is set (which persists only the audit chain).
- The rebuilt UI polls `/api/state` every 15 seconds and re-evaluates immediately after a
  scenario or exam POST. The legacy `/api/stream/step` / SSE endpoints remain available and
  tested, but the new three-view UI does not drive a background server-side worker.
- Implemented in the unified cockpit: dual-mode state engine, five labelled demo scenarios,
  `/api/state`, `/api/scenario`, `/api/exams/{pvt,ultrasound,vitals}`, GOES cached/live loader
  (`/api/goes/refresh`), manual ONSD caliper with pixel→mm math, multi-signal demo organ rules,
  split-conformal demo quantile, cosine-median bit-flip demo, and `contracts/HealthAudit.sol`
  as a **reference only** contract.
- Still not implemented / not claimed: neural risk heads, MC-dropout σ_epistemic, conformal
  coverage guarantees, sklearn LR/RF baselines, PyTorch HyperionCoreNet, real Flower FL,
  Opacus DP-SGD (ε,δ), WESAD (gate NO-GO), automated ultrasound diagnosis, flux→dose
  conversion, and a deployed EVM ledger. The ML panel lists these as `NOT_IMPLEMENTED`.
  `docs/REQUIREMENTS-TRACEABILITY.md` tracks each one.
