# Workstation runbook (API + React frontend)

**What this is:** a runnable research prototype of the crew-health workstation from
`HYPERION_MDA.pdf`, built as spec B (React 18 + TypeScript strict + Vite + Tailwind +
Radix UI / cmdk / Motion primitives + Recharts) over a FastAPI composition layer.
The UI follows [docs/FRONTEND-DESIGN.md](FRONTEND-DESIGN.md): an instrument-grade
dashboard with a collapsible rail, ⌘K command palette, asymmetric telemetry bento and
slide-over detail drawers.

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

- The app lands on **Live workstation** (`/workstation`): the 3-column avionics layout from
  the directive — body twin + inspector, gate pipeline + charts + triage, diagnostics tabs +
  readiness shield, ML benchmark and audit panels.
- **⌘K / Ctrl-K** opens the command palette: navigate, run/stop scenarios, switch subject,
  switch demo role, refresh session.
- **G then W / D / C / H / A / O / R** jumps to Live workstation, Overview, Crew console,
  Crew checks, Alert queue, Operations, Research. The rail shows the chord indicators.
- The rail collapses to 64px; the state persists. Below `md` a compact mobile nav replaces it.
- The topbar date-range control (`30s / 2m / 5m / All`) filters the telemetry canvas and
  gate-verdict log. On mobile the same control appears in the chart header.
- Clicking a table row opens a slide-over drawer with the full gate evidence for that frame.

## 4. First run — the honest path

1. Open the app. It lands on **Live workstation**. Until a scenario is selected the banner
   reads **SIMULATED MISSION TELEMETRY FALLBACK … Explicitly Labeled Non-Flight Simulation**
   and there is no telemetry; every organ is **NOT_AVAILABLE**. Nothing is invented to fill
   the screen. Use the five scenario buttons for labelled demo states, or switch to REAL mode
   to see verified lab/GOES availability (`telemetry_mode=NOT_AVAILABLE` without a live wearable).
2. Switch the role selector to **Ops**.
3. Go to **Operations** (`G O`). In **Per-person calibration**, press **Calibrate** for
   `demo-crew-1`. The note says this is a DEMO calibration built from a SIMULATED resting window.
4. In **Scenario runner**, run **Exercise false alarm** (or press ⌘K and search for it).
5. Return to **Live workstation** (`G W`) or **Overview** (`G D`). Watch raw HR climb toward
   ~148 bpm while the residual stays near zero. Gate 2 shows **BLOCK** and the false-alarm
   banner appears. State: **CONTEXT COMPENSATED**.
6. Run **Exercise + irregular rhythm** instead. The same movement is present, but the
   non-rate finding escalates to **SURGEON ALERT**. It is never suppressed.
7. Switch to **Flight surgeon** and acknowledge the alert with a note.
8. Switch to **Ops** and check the **Audit chain** badge reads "Chain intact".

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
| Crew | Console, manual checks, PVT, run scenarios |
| Flight surgeon | Everything above + acknowledge alerts, read audit and lab data |
| Ops | Calibrate, run scenarios, read lanes and audit |
| Researcher | Read-only overview/telemetry, M6 results, registry, provenance, audit; cannot run scenarios or acknowledge |

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

# web: strict typecheck, 34 unit/DOM tests, production build
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

Set `HYPERION_MDA_DATA_DIR` to point at an existing cache. The **Research → NASA lab lane**
tab shows the verified rows; **Research → M6** shows the committed, independently verified
offline results.

## 8. Known limits

- No browser binary was available in the build environment, so the UI was verified with
  jsdom component renders, a strict typecheck, a production build and HTTP smoke checks —
  **not** with a real-browser screenshot or Playwright run.
- Frontend state is process-local on the server; restarting the API clears calibrations,
  checks and alerts unless `HYPERION_AUDIT_LOG` is set (which persists only the audit chain).
- The stream advances while a browser tab is driving it (`/api/stream/step` once a second).
  There is no background server-side worker.
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
