# Unified workstation API contract

Base URL: `http://localhost:8000` (single origin; SPA + API). Every JSON response carries
`lane`, `provenance`, `generated_at`, `disclaimer`. Roles are demo-grade `X-Role` headers,
not authentication.

## Dual-mode state

### `GET /api/state`
Returns the full cockpit snapshot:
- `data_source_mode`: `REAL_EMPIRICAL` | `SIMULATED_FALLBACK`
- `telemetry_mode`: `REAL_EMPIRICAL` | `SIMULATED_FALLBACK` | `NOT_AVAILABLE`
- `provenance_banner`: explicit non-flight simulation banner in fallback; real-mode banner
  states which sources are available / NOT AVAILABLE.
- `habitat`, `habitat_label`, `habitat_options` (station / transit / lunar / rover)
- `sources.lab` (OSD-575 SHA-256 verified or unavailable), `sources.goes` (cached/live NOAA
  integral protons; flux pfu, **dose_mgy_day=null**), `sources.wearable` (WESAD NO-GO /
  PhysioNet verified-or-absent; feature values null unless a live extraction path exists)
- `organs[6]`: multi-signal demo rules, `staleness_tau`, optional `z_score`, allowed action
- `frame`, `history[]` (raw HR / residual / ENMO* / CO₂* / conformal upper), `gates[3]`
- `conformal`: demo split-conformal quantile; `sigma_epistemic=null`
- `active_sensing`: ranked crew checks; `triage`: tier / why / steps / allowed actions
- `overlays`, `countermeasure_flags`, `readiness` (τ̄, streak, badges)
- `ml_benchmark`: measured M6 rows + `requested_benchmarks` statuses + toy FedAvg +
  cosine-median bit-flip demo; unimplemented models are labelled, never invented
- `audit`: local SHA-256 chain verification + entries; **not on-chain**

### `POST /api/scenario`
Body: `{ "scenario_id"?: string, "habitat"?: "station|transit|lunar|rover", "mode"?: "REAL_EMPIRICAL|SIMULATED_FALLBACK" }`
- `scenario_id` ∈ `nominal-orbital`, `eva-ared-exercise`, `sans-stale-eye`, `spe-radiation`,
  `glycemic-circadian`. Seeds a labelled SIMULATED fallback state and returns `/api/state`.
- `mode=REAL_EMPIRICAL` stops the stream, clears simulated frames/overlays and never invents
  telemetry. Returns `/api/state`.
- Roles: crew / ops / flight-surgeon.

## Exams (crew / flight-surgeon)

### `POST /api/exams/pvt`
`{ "reaction_ms": [..1–5 finite values in (0,10000]..], "subject_id"?: string }`
Stores median PVT, resets τ_PVT≈1, re-evaluates gates, audits count only. Returns state.

### `POST /api/exams/ultrasound`
Either `{ "sample": "nominal" | "sans" }` (known 4.6 / 6.1 mm sample frames) or
`{ "px_per_mm": >0, "x1","y1","x2","y2" }` manual retrobulbar caliper (3 mm behind globe).
An uploaded image without a pixel scale is rejected. Returns state + `caliper`.

### `POST /api/exams/vitals`
Any of: `bp_sys`+`bp_dia` (together), `glucose_mgdl`, `temp_c`, `sleep_hrs`, `water_ml`,
`ared_min`, `mood_score`. Finite range-checked values; stores INJECTED crew checks /
countermeasure log, re-evaluates gates, audits kinds only (no raw values). Returns state.

## Data / ML / audit

- `POST /api/goes/refresh` (ops/researcher/flight-surgeon): attempts live NOAA SWPC fetch,
  best-effort caches JSON, returns availability. Never converts pfu → mGy/day.
- `GET /api/ml/benchmark`: same honesty panel as `/api/state.ml_benchmark`.
- Existing endpoints remain: `/api/health`, `/api/session`, `/api/lanes`, `/api/registry`,
  `/api/lab/osd575`, `/api/research/m6`, calibration, manual, organs, scenarios/stream/SSE,
  alerts, `/api/audit`, `/api/audit/verify`.

## Safety invariants
- Unknown/stale/missing never renders green.
- Gate 2 cannot suppress non-rate findings, hard-ceiling rates, or holds past timeout.
- Actions are exactly the four-string allow-list; no treatment advice.
- Audit stores no raw measurement values; acknowledgement notes are hashed.
- `contracts/HealthAudit.sol` is reference only; no EVM transaction exists.
