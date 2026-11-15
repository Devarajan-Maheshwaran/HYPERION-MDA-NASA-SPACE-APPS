# Implementation status

Updated 2026-11-14 (live crew cockpit wave): backend-owned 1 Hz mission clock + SSE,
SQLite case persistence with verified restart resume, persisted S0–S4 workflow, store-and-
forward surgeon outbox with blackout/delay/hashed receipts, recorded-non-astronaut replay,
OSD-575/GOES provenance panels, measured FL/DP benchmark artifact + Docs rendering,
Dockerfile/compose/healthcheck and `run_workstation.sh --offline`. Verification: tests_api
152 passed + 79 subtests; full pytest 324 passed / 41 skipped / 207 subtests; web 48 tests /
10 files + typecheck + build; HTTP smoke 58/58; FL/DP `--verify` byte-for-byte. Docker image
not built here (no daemon); real-browser Playwright still unavailable.

Prior: OSD-575 candidate + M2 channel panel + demo lanes + M5 PhysioNet recorded lane + M6 LOPO baselines experiment, with the review R1 assay-rejection fix and the R3/R6 documentation reconciliation applied afterwards.

> **Archive note:** earlier versions of this file referenced `dist/HYPERION-MDA-Prototype.zip`. That archive is **not present in this repository** (`dist/` is git-ignored) and no builder for it is included. Nothing in the current build depends on it.
>
> **Counts:** channel and test counts in this file are computed by `python scripts/report_counts.py`. Collected tests ≠ executed tests; class-level skips (no Tkinter, no dataset cache) lower the "Ran N" figure.

| Capability | Status |
|---|---|
| **NASA OSDR OSD-575 serum CMP: real-data path** | **Implemented (candidate).** Official source, verified local file, schema-checked import, pre-flight vs post-flight descriptive comparison, desktop UI. See `docs/OSDR-OSD575-DATA.md`. |
| Provenance manifest (source URLs, file, size, SHA-256, retrieval date, licence status, discrepancies) | Implemented: `src/hyperion_mda/data/osdr/OSD-575.provenance.json`. The SHA-256 was computed from the downloaded file. |
| On-demand download with verification (`python -m hyperion_mda.osdr_fetch`) | Implemented. Checks the official listing (name, size, `restricted: false`), downloads, verifies size and SHA-256, and leaves no file if any check fails. **This is the only code that uses the network**; it sends no health data. |
| Checksum check on every load; no fallback | Implemented. A missing or altered file gives an error dialog and an empty table, and nothing is substituted (tested). |
| Schema-checked OSDR adapter | Implemented: exact header required; `TEST_TYPE` = `CMP` checked — a row with any other assay sets an explicit `rejection_reason` and is **never a baseline and never scored** (R1), while staying visible with its flags; analyte names and units preserved exactly; source line kept per row; `SEX` and the lab reference ranges not used. `rejection_reason` (blocks scoring) and `flags` (display warnings only) are distinct — see `docs/OSDR-OSD575-DATA.md`. |
| Mission-relative ordering (`L-n` before `R+n`) | Implemented. No calendar dates are created; the chart shows timepoints evenly spaced with a "flight" marker, not to scale. |
| Missing (`NA`) values and absent rows | Implemented: kept visible as `NA`, listed by line number in the import summary, never imputed or scored. The absent C002/BUN-CREATININE/R+82 row is reported. |
| Pre-flight-only baselines; baseline count shown | Implemented: only `L-` rows are baselines; the score basis states the number of baseline readings used. |
| Illustrative `\|z\| ≥ 2.5` flag | **Disabled for OSDR data.** Still present only for user-opened demo-format CSVs. |
| Descriptive z-score | Implemented and labelled "descriptive, unvalidated". No thresholds, alerts, diagnoses or recommendations. |
| Synthetic example data | **Moved to `tests/fixtures/` only.** No longer shipped, and there is no runtime button or fallback. |
| User-opened CSV (demo format) | Implemented, with an "unverified provenance" banner; see `docs/CSV-SCHEMA.md`. |
| CSV validation, timestamp ordering, earlier-only baselines, unit allow-list, duplicates (R1) | Implemented (unchanged), for the user-CSV path. |
| Time-series chart | Implemented: UTC axis for CSV data, mission-relative axis for OSDR data. Markers are not joined; timepoints with `NA` keep a visible empty slot. |
| Tests | **213 `unittest` tests collected in total:** 185 in `tests/` and 28 in `experiments/m6/tests/` (`python scripts/report_counts.py`). The M6 tests cover participant-leakage, ECG-exclusion, standardiser-boundary, model, metric and real-data pipeline checks, plus reproducibility. The `tests/` suite covers engine, chart, packaging, OSDR source/schema/ordering/units/NA/baselines, assay-type rejection (R1), fetch logic using `file://` URLs, the demo lanes, the signal registry, the M5 PhysioNet lane (gate/checksums, WFDB reader, real records, adapter, lane separation, HR check, GUI), and an end-to-end check on the real verified file through the UI data model against an independent calculation. **Collected ≠ executed:** without Tkinter or the dataset caches, whole classes skip. Software verification only. |
| Visual inspection | Done on Windows 11 (125% scaling) at the 900×740 minimum and maximised, with the real OSDR data. |
| Window sized to fit the screen | Implemented. Maximise if Windows places the window low on the screen (see the runbook). |
| **M2: signal registry** (`signal_registry.py`) | **Implemented.** **49 channels** — 19 MEASURED-LAB-SAMPLE, 5 RECORDED-NON-ASTRONAUT, 3 SIMULATED, 22 UNAVAILABLE (computed from `signal_registry.CHANNELS` by `python scripts/report_counts.py`). Each channel has exactly one status, a lane, and a source/provenance description. The registry holds **no values**. The 19 OSD-575 analytes are MEASURED-LAB-SAMPLE, grouped under "Blood serum (laboratory sample)", with their sparse collection labels (L-92 … R+194; no clock times). The 10 WESAD channels are UNAVAILABLE pending the WESAD gate (not downloaded, not tracked in the repo, not trained on). Bio-Monitor signals, cuff BP, sleep, PVT, ONSD and cabin ppCO2/radiation/pressure are UNAVAILABLE with no values. The 5 RECORDED channels were added in M5 and the 3 SIMULATED channels with the demo playback lane; both carry their own lane and never merge with NASA records. `validate_registry()` enforces the lane and status rules. |
| **M2: channel panel** (`twin_view.py`, opened with **Channel panel…**) | **Implemented, display only.** A neutral body outline with clickable regions, a status legend, a channel table (status badge, unit, "This session" counts of loaded OSD-575 values and NAs, region, sampling) and a details box with the full source. A **persistent "NOT A VALIDATED PHYSIOLOGICAL DIGITAL TWIN" notice** is always visible. It shows no clinical scores, risk colours, cutoffs, diagnoses, treatment text or NASA/CSA integration claims, and scoring is unchanged. Covered by 22 tests in `tests/test_registry.py`; visually inspected on Windows 11 (125% scaling). |
| **SIMULATED wearable playback** (`sim_wearable.py`, `playback_view.py`) | **Implemented (demo only).** Three deterministic fixed-formula signals, with Start/Pause/Reset and a time slider. Labelled SIMULATED on the banner, titles, units, provenance and registry channels. Never merged with NASA records (tested). |
| **Sensor-adapter boundary** (`adapters.py`) | **Implemented as an interface.** `WearableAdapter` protocol, sample validation (rejects non-finite values, unknown channels, unit mismatches, non-increasing time, wrong provenance) and `PlaybackSession`. **The only implementation is `SimulatedPlaybackAdapter`; no real device adapter exists or is connected.** |
| **FL SIMULATION** (`fl_sim.py`, `fl_view.py`) | **Implemented (concept demo only).** A framework-free, reproducible FedAvg on generated toy data in one process: 2–8 simulated clients, 1–30 rounds, seed 7. It shows clients, rounds, update sizes, global weights and the aggregation flow. **Not Flower** (not installed; Python 3.14 support unverified), **not multi-site**, **no differential privacy**, no performance claims. |
| **M5: PhysioNet Wrist PPG lane (RECORDED, non-astronaut)** | **Implemented and verified.**
- **Data gate passed:** terms (ODC-By 1.0) and documentation were verified on the owner page. All 59 files are SHA-256-verified against the owner `SHA256SUMS.txt`, whose own hash is pinned. The **raw recordings** are cached outside the repo and are not bundled. **Derived M6 outputs are tracked** in `experiments/m6/outputs/` (14 files), which ODC-By 1.0 permits with attribution; see `docs/DATA-SOURCE-INVENTORY.md` §3c for exactly what is and is not in git.
- **Standard-library WFDB reader** (format 16 + MIT annotations): checked against each record's own header checksums, and **cross-checked against the official `wfdb` package in a scratch environment**. All 19 records, all 15 signals: identical raw samples, zero physical difference, and all 11,388 beat annotations identical.
- **`RecordedPhysioNetAdapter`** sits behind `WearableAdapter`, with 5 RECORDED-NON-ASTRONAUT registry channels and the playback window.
- **HR methods check** (`dsp_hr.py`, numpy/scipy in `.venv` only): PPG peak-interval rate vs the reference ECG beats. The parameters were fixed before results; the output is measured and deterministic, and shown as-is.
- **Known limitations:** the wrist timestamp channel (60 s rollover with whole-second jumps) isn't used, so the time base is the uniform 256 Hz index. Amplitudes are header-declared, not calibrated. n = 8. |
| **M6: LOPO baselines on PhysioNet Wrist PPG (offline experiment)** | **Implemented, run and verified (2026-11-15).** This is not in the desktop app. Code, frozen config and outputs are in `experiments/m6/`; protocol in `docs/M6-LOPO-PROTOCOL.md`; results in `docs/M6-RESULTS-SUMMARY.md` and `docs/M6-TECHNICAL-REVIEW.md`.
- **Design:** 8-fold leave-one-participant-out; fixed hyperparameters; numpy/scipy linear models; ECG used as the reference only.
- **Measured, heart rate:** no method beat a no-signal training-mean predictor. MAE 24.18 bpm for that predictor vs 23.67 for the frozen M5 method; the ridge models were 30.06–32.22.
- **Measured, activity (walk / run / cycle):** accelerometer logistic regression scored 0.733 accuracy and 0.731 macro-F1, vs 0.451 / 0.207 for the majority class.
- **PPG vs accelerometer:** no evidence at n = 8 that PPG adds information beyond the accelerometer features.
- **Verification:** an independent verifier recomputed the metrics from the raw CSVs (1187 checks passed). |
| **Blocked / not implemented** | **WESAD gate: NO-GO** (`docs/DATA-SOURCE-INVENTORY.md` §3.3); no WESAD download or training. No astronaut wearable data (none public). **No validated heart-rate algorithm:** the M6 baselines did not beat a no-signal predictor. M7 (motion-artifact-resistant HR) is a **proposal only** (`docs/M7-PROPOSAL.md`). **Not implemented:**
- real device adapters
- Flower, or real multi-site FL
- differential privacy
- training beyond the M6 linear baselines
- clinical functionality
- NASA/CSA integration |
| Wearable / continuous telemetry ingestion | **Not implemented.** No open astronaut wearable dataset was identified. WESAD (terrestrial lab study) is planned for a methods demonstration only, gated on confirming its current terms. |
| WESAD or other terrestrial datasets | Not implemented. |
| OSD-570 / OSD-571 data | Not used. They are sequencing and proteomics/metabolomics data, not telemetry. |
| Kalman baselines, exertion residualizer, conformal / MC-dropout uncertainty, neural models | Not implemented. |
| Clinical state machine or protocols (NASA-STD-3001, CSA) | Not implemented. |
| Ultrasound / ONSD, PVT, point-of-care instruments, digital twin | Not implemented. |
| Federated learning / differential privacy | Not implemented. |
| Blockchain or cryptographic ledger | Not implemented. |
| Sensor, spacecraft or NASA/CSA system integration | Not implemented. |
| Encryption, authentication, standards compliance, clinical validation, flight qualification | Not implemented or established. |

Keep this file current. A design note or TODO is not evidence of implementation.
