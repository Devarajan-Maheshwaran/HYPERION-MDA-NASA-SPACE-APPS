# Architecture: current build and MVP target

The PPT (`HYPERION_MDA_NASA_SpaceApps_SIH_Template.pptx`) describes a five-layer onboard system. This document separates **what exists** from **the realistic MVP target** and **what stays out of scope**. Every PPT element is mapped in `docs/REQUIREMENTS-TRACEABILITY.md` Part A.

## 1. Current build (implemented and tested)

**NASA real-data path (OSD-575 candidate):**
1. The official NASA OSDR file listing.
2. An explicit download (`osdr_fetch`, the **only** network code).
3. A size and SHA-256 check against `OSD-575.provenance.json`.
4. The schema-checked adapter (`osdr_cmp.py`): exact analyte and unit names; `NA` kept visible; `SEX` and the reference ranges unused.
5. Mission-relative ordering (`L-n` before `R+n`; no dates created).
6. Pre-flight baselines vs post-flight observations, with a descriptive z (no flag, no thresholds).
7. The desktop table, chart and details panel.

A missing or altered file stops the load; nothing is substituted. See `docs/OSDR-OSD575-DATA.md`.

**User-CSV path (demo format):**
1. A CSV file.
2. Schema, value and timestamp checks.
3. The supported signal–unit pair check and duplicate-instant detection. Problem rows are flagged, kept visible and excluded from scoring.
4. Provenance and quality display.
5. Explicit `baseline` rows (accepted quality only) for each subject, signal and unit.
6. A descriptive z-score for `observation` rows.
7. A chronological desktop table.

The illustrative |z| flag applies **only** to this path and is not a clinical threshold. The synthetic example CSV is a test fixture only.

**M2: signal registry and channel panel (implemented):**
- `signal_registry.py` assigns every displayed channel exactly one status, a lane (`nasa-lab`, `wearable-model`, `unavailable`) and a source description. It holds no values and performs no file or network access.
- `twin_view.py` (the **Channel panel…** button) draws a neutral body outline and a channel table from the registry. OSD-575 values are counted per channel only after the verified load.
- A "not a validated physiological digital twin" notice is always visible, and the panel shows no scores, risk, cutoffs or integration claims.
- WESAD channels are UNAVAILABLE until the WESAD gate.
- Scoring and the main window are unchanged.

**Demo lanes (implemented):** three pipelines that share no data. Import directions are audited by tests.
- *NASA lab data:* `osdr_*`, `engine`. Unchanged.
- *SIMULATED wearable:* `sim_wearable` → `adapters` (the `WearableAdapter` boundary, validation, `PlaybackSession`) → `playback_view`.
- *FL SIMULATION:* `fl_sim` → `fl_view`, using toy data only.
- *RECORDED non-astronaut (M5):* `physionet_fetch` (network, explicit) → `physionet_source` (pinned SHA-256 manifest) → `wfdb_reader` (stdlib; header-checksum verified) → `physionet_adapter` (`WearableAdapter`) → `playback_view` / `recorded_view`. The `dsp_hr` methods check needs numpy and scipy (project `.venv`). Imports nothing from the NASA, FL or simulated modules (tested).

The simulated and FL modules import nothing from the NASA pipeline, and the reverse also holds. Wearable samples are a separate type (`WearableSample`) from NASA `TelemetryRecord`s. No real device adapter exists.

**Stack:** Python standard library and Tkinter for the core app. numpy and scipy only for the M5 HR methods check, in an isolated `.venv`. Network access exists only in the two explicit fetch commands (`osdr_fetch`, `physionet_fetch`). Tests use `unittest`; there are 173 tests.

## 2. MVP target architecture (the signal registry and channel panel exist as of M2; everything else below is planned)

```text
 ┌──────────────── LANE A: NASA astronaut data (real, sparse lab samples) ───────────────┐
 │ OSDR listing → fetch + SHA-256 manifest → schema adapter → mission-relative order →   │
 │ descriptive pre/post comparison (no thresholds)            [EXISTS: OSD-575 CMP]      │
 └──────────────────────────────────────────────┬────────────────────────────────────────┘
                                                │ "measured lab sample" channels only
 ┌──────────────── LANE B: non-astronaut wearable (WESAD, lab study) ────────────────────┐
 │ owner-terms gate → fetch + SHA-256 manifest → raw-file reader (no untrusted pickle) → │
 │ windowing + feature extraction (deterministic, versioned) → participant-separated     │
 │ evaluation: majority / logistic-regression baselines → centralized model →            │
 │ Flower SIMULATION (same folds) → separate DP experiment (Opacus accountant report)    │
 │ OUTPUT: an evaluation report (metrics + uncertainty) — never fed into Lane A or the   │
 │ astronaut view                                                                         │
 └──────────────────────────────────────────────┬────────────────────────────────────────┘
                                                │ "recorded, non-astronaut" channels, clearly separated
 ┌──────────────── Signal registry (single source of truth for channel status) ──────────┐
 │ every channel → {MEASURED-LAB-SAMPLE | RECORDED-NON-ASTRONAUT | SIMULATED |           │
 │ UNAVAILABLE}, with source, units, sampling (or "sparse timepoints"), provenance link   │
 └──────────────────────────────────────────────┬────────────────────────────────────────┘
                                                ▼
 ┌──────────────── Desktop UI (Tkinter, existing app) ────────────────────────────────────┐
 │ Wearable-style twin panel: body-region layout of CHANNELS + status badges only        │
 │ (no organ risk, no scores on the figure) · existing table / chart / details           │
 │ · a separate "Methods demo (WESAD)" tab showing the evaluation report, never mixed    │
 │   with astronaut data                                                                  │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

**Lane boundaries (enforced in code and tests once built):**
- **A and B never share a table, chart or record type.** WESAD values never appear in the astronaut view. OSD-575 values are never used for training (they have no labels, and n = 4).
- **Simulated signals:**
  - They exist only if a demo mode is explicitly turned on.
  - Every simulated channel carries a **SIMULATED** badge and a watermark.
  - They are never combined with measured or recorded values.
  - They are **off by default**.

**Planned modules** (names are proposals):

| Module | Lane | Purpose |
|---|---|---|
| `signal_registry.py` | — | **Implemented (M2).** Channel definitions and status; the only place a status is assigned |
| `twin_view.py` | UI | **Implemented (M2).** Body-region channel panel with badges; no scoring. The "Methods demo (WESAD)" tab is **not** built. |
| `wesad_source.py` / `wesad_fetch.py` | B | Manifest, verification and download (mirrors the OSDR pattern) |
| `wesad_features.py` | B | Deterministic windowing and features; the feature set and window sizes are versioned config |
| `evaluation.py` | B | Participant-separated folds, baselines, per-class metrics, bootstrap intervals |
| `fl_sim/` (optional extra `[fl]`) | B | Flower `ServerApp` and `ClientApp`, run with the Simulation Runtime (`flwr run`) |
| `dp_experiment/` (optional extra `[dp]`) | B | Opacus `PrivacyEngine` experiment and accountant report |

**Dependency policy:** the core app stays standard-library only.
- **Lane B** adds `numpy`/`scipy`/`scikit-learn`, which are already present on the development machine.
- **The `[fl]` extra** adds `flwr[simulation]`, which pulls in Ray.
- **The `[dp]` extra** adds `torch` and `opacus`.

These are large, optional installs. Python 3.14 compatibility is **unverified** (inventory Q7). A separate Python 3.11/3.12 environment may be required.

## 3. Out of scope (from the PPT; not built and not planned without evidence or authorisation)

- **Clinical decision-making:** clinical thresholds and "indicator cutoffs", diagnoses, treatment or "action plans", NASA-STD-3001 "action packets", triage tiers.
- **Physiological modelling:** the six-organ risk heads and organ risk scores, the "6-organ twin" as a physiological model, the exertion residualizer on astronaut data, the 3-stage trust gate, conformal and MC-dropout risk gating.
- **Instruments:** ultrasound/ONSD, the PVT instrument, point-of-care device integration.
- **Integrations:** CSA Bio-Monitor, dosimetry, the ISS environment, NASA/CSA systems, HL7-FHIR/DTN, analog-habitat deployment.
- **Deployment claims:** multi-habitat deployment, a Hardhat/Solidity ledger, the LangGraph protocol router.
- **Claims that can't be made:** flight readiness, NASA approval, Privacy Act compliance, any performance improvement.

## 4. Design rules (unchanged, plus additions)

- Do not silently guess units, repair timestamps, or impute missing observations.
- Keep source and transformation provenance with every value; pin every external file by SHA-256.
- Do not let flagged values silently redefine an individual's baseline.
- Present observed values separately from computed indicators.
- **New:**
  - Keep astronaut and non-astronaut data in separate lanes.
  - Every displayed channel carries one status from the signal registry.
- **New:** model evaluation uses participant-separated splits only. Preprocessing is fitted on training participants only.
- **New:** federated learning is labelled a **simulation**, and differential privacy is reported only as the accountant's actual output under a stated threat model.
- "Offline" describes no-network behaviour; it does not imply secure, flight-ready or validated operation.
