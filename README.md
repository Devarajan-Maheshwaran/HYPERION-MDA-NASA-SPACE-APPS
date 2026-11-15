# HYPERION-MDA — Deep-Space Crew Health Monitoring

HYPERION-MDA is an offline-first crew-health research web app for exploring astronaut health monitoring across six organ systems and four simulated space habitats. It demonstrates queued alerts for deep-space communication delays of up to 20 minutes, using a clearly labelled 12-second demo timer.

## The Problem & How HYPERION-MDA Solves It

| Problem in Space | What HYPERION-MDA Does |
|---|---|
| **Exercise false alarms** | Gate 2 uses a personal activity scale and simulated cabin CO₂ context to filter workout heart-rate alarms. Displayed ENMO is a labelled simulation, not a calibrated gate input. |
| **Microgravity baseline shifts** | Compares heart rate with the person's own resting Z-score. Other organ checks use visible demo rules, not claimed clinical cutoffs. |
| **Old manual checks & blackouts** | Tracks freshness with $\tau = e^{-\lambda \Delta t}$, uses an **S2 Hold** to request a crew check, and queues escalation packets for the demo flight surgeon. |

## Quick Start (Run Locally)

Verified here on Linux with Python 3.11 and Node.js 22. Run these commands from the repository root:

```bash
python3 -m venv .venv-api
.venv-api/bin/python -m pip install -r requirements-api.txt
cd web
npm ci
npm run build
cd ..
HOST=127.0.0.1 .venv-api/bin/python backend_api.py
```

Open **http://127.0.0.1:8000**. The API and built UI share one port. The default live case is labelled **Simulated Scenario Fallback**. No dataset download is needed to start it.

After the first setup, this command reuses the local environment and build without contacting package registries:

```bash
HOST=127.0.0.1 bash run_workstation.sh --offline
```

Optional hot-reload mode: keep the backend running, then use a second terminal:

```bash
cd web
npm run dev
```

Open http://127.0.0.1:5173; Vite proxies API requests to port 8000. On Windows, use `.venv-api\Scripts\python.exe` instead of `.venv-api/bin/python`.

## Key Features (As Built)

- **Three light-theme views:** Crew Workstation at `/`, Overview at `/overview`, and ML Architecture & Docs at `/docs`.
- **Six-organ body map and four habitats:** Head & Eyes (SANS), Heart & Vessels, Chest & Immune, Metabolic & Gut, Bones & Muscles, and Brain & Sleep; Station, Transit, Lunar Base, and Rover.
- **Three crew tools:** a mouse reaction timer (PVT, ms), an ocular ultrasound caliper (ONSD, mm), and a keyboard vitals logger.
- **Three safety gates and an S0–S4 workflow:** sensor quality, exercise filtering, and freshness holds; exams and surgeon acknowledgement move the case forward.
- **Live local state:** a backend-owned 1 Hz clock, server-sent events, pause/step/reset controls, SQLite persistence, and a blackout-aware alert outbox.
- **SHA-256 audit chain:** linked 32-byte digests make changes detectable without storing raw medical measurements. It is a local chain, not a blockchain.

> Research prototype only: not a medical device, not clinically validated, and not connected to live astronaut wearables. Role headers are for the demo, not secure authentication. Do not expose it publicly with real patient data.

## Why Each Technical Component Is Used

| Component | Tool Used | Why We Used It |
|---|---|---|
| ML models | **NumPy + SciPy:** ridge regression and multinomial logistic regression | Small CPU baselines with participant-separated LOPO splits. scikit-learn Random Forest and the PyTorch LayerNorm MLP are specifications only, not implemented models. |
| Federated learning & privacy | **NumPy FedAvg / DP-SGD + exact RDP accounting + cosine-median filter** | Four participant-group silos in one process exchange weight updates, not raw waveforms. The benchmark reports window-level privacy only; Flower, Opacus, real habitat clients, and secure aggregation are not used. |
| Audit log | **Python `hashlib` SHA-256 + SQLite**; `HealthAudit.sol` as a reference | A local flight-recorder-style chain with no mining and no raw measurements in audit payloads. The contract is not deployed; no EVM transaction exists. |
| Backend & UI | **FastAPI + React + TypeScript + Tailwind CSS + Vite** | One local port serves the API and built UI. Fonts are bundled locally; the core demo does not need a CDN or external telemetry service. |

## Data Sources & Provenance

| Data Lane | Source | How It Is Used in the Repo |
|---|---|---|
| NASA lab data | **NASA OSDR OSD-575**, Inspiration4 serum CMP | Checksum-verified, sparse pre/post-flight lab comparisons and a web lab drawer. The CSV is fetched separately, not bundled or used for model training. |
| Recorded non-astronaut data | **PhysioNet Wrist PPG During Exercise v1.0.0**, n=8 | Raw waveforms are checksum-verified when fetched. Committed derived windows/features support replay, LOPO baselines, and the FL/DP benchmark. These are terrestrial exercise recordings, not astronaut data. |
| Space-weather context | **NOAA/NASA GOES** integral proton flux | Optional cached/live flux in **pfu**, with availability and cache age shown. It is satellite environmental data, not cabin radiation or absorbed crew dose. |
| Simulated scenarios | **Five labelled deterministic scenarios** and crew-entered demo values | Drive the default workstation and safety-gate tests. They are never presented as measured astronaut telemetry or merged into the real-data lanes. |

Measured outputs: [PhysioNet LOPO report](experiments/m6/outputs/report.md) · [FL/DP benchmark](artifacts/fl_dp_benchmark_results.json) · [recorded desktop demo evidence](demo-evidence/README.md).

## Repository Structure

```text
api/                         FastAPI routes, safety gates, workflow, persistence, and data lanes
src/hyperion_mda/             Shared data adapters, desktop prototype, and provenance manifests
web/                         React UI, frontend tests, and build configuration
scripts/                     HTTP smoke test, FL/DP benchmark, and source-count report
tests/                       Core data, engine, packaging, and desktop tests
tests_api/                   API, gate, lifecycle, privacy-label, and benchmark tests
experiments/m6/              Frozen LOPO protocol, code, tests, and measured outputs
artifacts/                   Reproducible FL/DP benchmark result
contracts/                   Reference-only HealthAudit.sol
docs/                        Runbooks, API contract, safety notes, and verification reports
demo-evidence/               Recorded desktop screenshots, logs, and acceptance harness
reference-material/          Retained project brief and research references
backend_api.py               Single-port web/API entrypoint
run_workstation.sh           Setup/build launcher and offline rerun
Dockerfile, docker-compose.yml  Container configuration; not built in the verification environment
```

## Running Tests

From the repository root, with the Quick Start dependencies installed:

```bash
export PYTHONPATH=src
.venv-api/bin/python -m pytest tests_api -q
.venv-api/bin/python -m pytest -q
(cd web && npm run test)
.venv-api/bin/python experiments/m6/verify_m6.py
.venv-api/bin/python scripts/run_fl_dp_benchmark.py --verify
```

With the local server running, check the HTTP workflow:

```bash
.venv-api/bin/python scripts/smoke_workstation.py --base http://127.0.0.1:8000
```

| Check | Verified result |
|---|---|
| API pytest suite | **152 passed**, 79 subtests passed |
| Full Python pytest suite | **316 passed**, 49 skipped, 207 subtests passed |
| Frontend Vitest suite | **48 passed** in 10 files |
| M6 output verifier | **1,187 checks passed**, 0 failed |
| FL/DP artifact verifier | Reproduced; only the moving `git_head` metadata is excluded |
| HTTP smoke test | **58 passed**, 0 failed |
| Frontend production build | Passed |

Skips are explicit: this verification environment lacks Tkinter and the optional raw OSD-575/PhysioNet caches. Committed derived PhysioNet outputs still support the M6 and FL/DP verifiers. Docker and a real-browser E2E run were not available; frontend tests use jsdom.

## NASA & Space Agency References

These are research context, not endorsement or proof of compliance:

- NASA HRP: [Five Hazards](https://www.nasa.gov/hrp/hazards/) · [Risks](https://www.nasa.gov/hrp/risks/) · [Ongoing research](https://www.nasa.gov/hrp/)
- NASA OSDR: [OSD-575 study record](https://osdr.nasa.gov/osdr/data/osd/meta/575)
- CSA: [science experiments in space](https://www.asc-csa.gc.ca/eng/sciences/) · [Bio-Monitor](https://www.asc-csa.gc.ca/eng/sciences/bio-monitor.asp) · [Vascular research](https://www.asc-csa.gc.ca/eng/sciences/vascular.asp)
- CSA radiation monitoring is a concept reference only; no CSA dose feed is integrated.
- NOAA GOES: [SWPC](https://www.swpc.noaa.gov/) · [integral proton flux feed used by the app](https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json)
- PhysioNet: [Wrist PPG During Exercise v1.0.0](https://physionet.org/content/wrist/1.0.0/), ODC-By 1.0; cite Jarchi & Casson (2017), doi:10.3390/data2010001.
