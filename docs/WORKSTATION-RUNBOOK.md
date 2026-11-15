# Workstation runbook (API + React frontend)

**What this is:** a runnable research prototype of the crew-health workstation from
`HYPERION_MDA.pdf`, built as React 18 + TypeScript strict + Vite + Tailwind + Radix
Popover + Motion + Recharts over a FastAPI composition layer. The UI follows
[docs/FRONTEND-DESIGN.md](FRONTEND-DESIGN.md): a Swiss Clinical Minimalist light theme
with three views — **Crew Workstation (`/`, the boot route)**, Overview (`/overview`) and
ML Architecture & Docs (`/docs`). All three stay in the header navigation.

**The workstation is live by default.** Booting `/` seeds the labelled
`SIMULATED_FALLBACK · nominal-orbital` case and starts a 1 Hz mission clock that drives the
organ panels, the freshness decay, the S0–S4 lifecycle and the communications outbox.

**What it is not:** a medical device. No clinical validation, no NASA approval, no flight
readiness. Demo thresholds throughout. Read `docs/SAFETY_ISSUES.md` before presenting it.

---

## 1. Install & run (pick one)

### A. One command (bootstrap + build + launch)

```bash
bash run_workstation.sh
# open http://localhost:8000
```

Creates `.venv-api`, installs `requirements-api.txt`, runs `npm ci` + `npm run build` in
`web/`, then serves everything from one process on `0.0.0.0:8000`.

### B. Offline rerun (no package index, no CDN)

After one successful run of A, everything needed is on disk:

```bash
bash run_workstation.sh --offline
```

This refuses to touch the network: it reuses `.venv-api` and `web/dist`, verifies the API
dependencies import, and launches. Fonts are bundled locally via `@fontsource`, so the
cockpit renders with no external requests.

### C. Docker

```bash
docker compose up --build          # open http://localhost:8000
docker compose restart workstation # clock, stage, exams, outbox and audit survive
docker compose down                # state survives in the named volume
docker compose down -v             # state deliberately destroyed
```

Multi-stage build (`node:22` -> `python:3.11-slim`), runs as an unprivileged user, exposes
only port 8000, and ships a `HEALTHCHECK` against `/api/health`. The `hyperion-state` named
volume holds `/app/var/hyperion-state.db`, which is what makes restart persistence real.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | bind address |
| `PORT` | `8000` | port |
| `HYPERION_STATE_DB` | `var/hyperion-state.db` | durable SQLite case store |
| `HYPERION_MDA_DATA_DIR` | unset | optional cache root for OSD-575 / PhysioNet / GOES lanes |
| `HYPERION_AUDIT_LOG` | `<state dir>/audit.jsonl` | durable audit JSONL |

Absent external data is reported as `NOT_AVAILABLE` with an explanation; nothing is
downloaded at startup and no value is invented.

## 2. Serving

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

The audit chain is durable in SQLite by default. `HYPERION_AUDIT_LOG` adds an optional
JSONL mirror; it is no longer required for restart persistence:

```bash
HYPERION_AUDIT_LOG=/tmp/hyperion-audit.jsonl .venv-api/bin/python backend_api.py
```

Optional real-data cache:

```bash
HYPERION_MDA_DATA_DIR=/path/to/cache .venv-api/bin/python backend_api.py
```

## 3. Navigation & cockpit layout

- The app lands on **Crew Workstation** (`/`). `/workstation` redirects there. Overview is
  `/overview` and Docs is `/docs`; the header shows `01. Crew Workstation`, `02. Overview`,
  `03. ML Architecture & Docs`.
- **Control strip** (always at the top): `LIVE 1.0 Hz` + `T+…` mission clock, Pause/Play,
  **Step +10 s**, **Reset Case**, five simulated scenario buttons plus a **Recorded human**
  replay selector, habitat/comms selector, **Rover blackout** toggle and an SSE health badge
  (`SSE live` / `SSE connecting` / `polling` / `offline`).
- **Main workspace** is a 3 / 5 / 4 grid on `xl`:
  - **left (3)** — six-node body map, organ summary grid, organ detail panel;
  - **centre (5)** — `LifecycleBanner` (S0–S4, pulsing amber `ACTION REQUIRED TO RESOLVE S2
    HOLD`), the live three-gate strip, `InstrumentBay` (always-visible PVT / Eye ONSD /
    Vitals tabs that auto-focus the requested exam), `TriagePlan`, `ActiveSensingList`, and
    exactly one raw-HR/residual chart;
  - **right (4)** — `CommsOutbox` (packet lifecycle + SBAR drawer + inline *Act as Flight
    Surgeon* acknowledgement) and `ProvenancePanel` (OSD-575 drawer, replay lane, GOES pfu).
- Below the fold: the full `GatePipeline` + residual chart, readiness, countermeasures and
  overlays — all fed by the same live state.
- **Docs** contains model specs, the requested-benchmark matrix, the **measured FL/DP
  benchmark rendered from the committed artifact**, measured M6 rows, demo thresholds,
  official NASA/CSA links and the local SHA-256 audit ledger.

### Streaming and the clock

`GET /api/stream/events` emits both `frame` (chart tick) and `state` (full cockpit snapshot)
events at 1 Hz. The provider consumes `state`, falls back to a 2 s `GET /api/state` poll if
SSE drops, and resyncs every 20 s while live so out-of-band packet transitions are never
missed. The mission clock lives in the backend; `Step +10 s` advances it by exactly ten
mission seconds, and freshness `tau` uses **60 mission seconds = 1 demo hour** (an explicit
time-compression convention, surfaced in the clock tooltip).

### Case lifecycle and comms

`S0_NOMINAL -> S1_EXERTION_COMPENSATED -> S2_ACTIVE_SENSING_HOLD ->
S3_CREW_COUNTERMEASURE -> S4_SURGEON_ESCALATED -> S4_SURGEON_ACKNOWLEDGED`.
The banner states that this is a **DEMO routing table, not clinically validated**. Escalation
builds an SBAR packet with a hashed payload; comms delay is habitat-dependent (station
0.2 s, lunar 1.3 s, transit 12 s, rover 5 s), a blackout parks packets in `QUEUED_BLACKOUT`,
and only a `flight-surgeon` role may acknowledge a `DELIVERED` packet. Acknowledgement
returns a SHA-256 receipt — **no blockchain exists**.

`POST /api/case/reset` returns the case to `S0_NOMINAL` with zero packets while preserving
the audit chain and adding two `CASE_RESET_*` blocks.

### Reproducing the measured benchmark

```bash
python3 scripts/run_fl_dp_benchmark.py --quick    # smoke config, writes nothing
python3 scripts/run_fl_dp_benchmark.py            # full run, writes artifacts/
python3 scripts/run_fl_dp_benchmark.py --verify   # recompute; compare all but git_head
```

Reads only committed M6 CSVs, needs no network, and the UI renders the JSON through
`GET /api/benchmark/fl-dp`. The accounting is **window-level, not participant-level**; the
Docs page states this on screen next to the numbers.

## 4. First run — the honest path

1. Open the app. It lands **directly on the Crew Workstation** with the clock already
   running. The amber **SIMULATED SCENARIO FALLBACK ACTIVE** banner is visible; the seeded
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

The cockpit defaults to the crew role. The outbox exposes one explicit, labelled
**Act as Flight Surgeon (demo role)** checkbox for acknowledgement; it sends `X-Role:
flight-surgeon` only for that request. Roles remain demo-grade headers, not authentication.
Do not host this with real PHI.

## 6. Tests

```bash
# existing suites, unchanged
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src .venv-api/bin/python -m unittest discover -s experiments/m6/tests
python experiments/m6/verify_m6.py

# API suite (152 tests + subtests, pytest)
.venv-api/bin/python -m pytest tests_api -q

# full Python suite (core + API + M6)
PYTHONPATH=src .venv-api/bin/python -m pytest -q

# web: strict typecheck, 48 unit/DOM tests, production build
cd web && npm run typecheck && npm test && npm run build

# end-to-end against a RUNNING server (58 checks)
python scripts/smoke_workstation.py --base http://127.0.0.1:8000

# measured FL/DP artifact: reproduce and verify (git_head metadata excluded)
python scripts/run_fl_dp_benchmark.py --verify
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
- Case state is durable in SQLite (`HYPERION_STATE_DB`, default `var/hyperion-state.db`).
  Restarting the process resumes the same mission clock, lifecycle stage, exams,
  calibrations, alerts, outbox and audit chain. `:memory:` opts out deliberately.
- The cockpit is SSE-first: `GET /api/stream/events` carries `frame` + `state` at 1 Hz.
  If SSE drops, the provider falls back to a 2 s `/api/state` poll and retries SSE after
  2 s; while live it resyncs every 20 s. The backend owns the clock.
- Implemented in the unified cockpit: dual-mode state engine, five labelled demo scenarios,
  `/api/state`, `/api/scenario`, `/api/exams/{pvt,ultrasound,vitals}`, GOES cached/live loader
  (`/api/goes/refresh`), manual ONSD caliper with pixel→mm math, multi-signal demo organ rules,
  split-conformal demo quantile, cosine-median bit-flip demo, and `contracts/HealthAudit.sol`
  as a **reference only** contract.
- Measured offline FL/DP benchmark exists (`scripts/run_fl_dp_benchmark.py`,
  `artifacts/fl_dp_benchmark_results.json`, `/api/benchmark/fl-dp`, Docs panel). It is a
  numpy DP-SGD + exact RDP experiment on committed non-astronaut M6 windows, with a
  **window-level** threat model. It is not Flower, not Opacus, not participant-level DP,
  and not a clinical or astronaut result.
- Still not implemented / not claimed: neural risk heads, MC-dropout σ_epistemic, conformal
  coverage guarantees, sklearn LR/RF baselines, PyTorch HyperionCoreNet, real Flower FL,
  Opacus DP-SGD, WESAD (gate NO-GO), automated ultrasound diagnosis, flux→dose
  conversion, and a deployed EVM ledger. The ML panel lists these as `NOT_IMPLEMENTED`.
  `docs/REQUIREMENTS-TRACEABILITY.md` tracks each one.
- Dockerfile/compose are provided but were not built in this sandbox (no Docker daemon).
  The offline launcher, SPA build, API suites and HTTP smoke were executed directly.
