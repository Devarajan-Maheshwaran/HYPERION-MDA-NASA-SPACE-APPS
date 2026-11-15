# HYPERION-MDA technical review: M5 recorded lane and M6 LOPO baselines

Prepared 2026-11-15 for mentor review.

> **Scope.** Everything here is a **methods demonstration on non-astronaut data**: PhysioNet *Wrist PPG During Exercise* v1.0.0, 8 adults, terrestrial laboratory treadmill and exercise-bike sessions.
>
> - Nothing here is validated.
> - Nothing makes an astronaut-health, clinical, diagnostic, device-performance or flight-readiness claim.
> - No M6 result is shown in the desktop app or mixed with the NASA OSD-575 lane.
>
> **Number sources:**
> - Every M6 number is copied from `experiments/m6/outputs/report.md`, which is rendered from `results.json`.
> - M5 numbers come from re-running `hyperion_mda.dsp_hr.run_check()`.
> - Both sets were cross-checked mechanically (§10).

## Contents
1. [M5 achievements](#1-m5-achievements)
2. [M6 architecture](#2-m6-architecture)
3. [Methodology and LOPO design](#3-methodology-and-lopo-design)
4. [Heart-rate results](#4-heart-rate-results-task-a)
5. [Heart-rate estimation: limitations and interpretation](#5-heart-rate-estimation-limitations-and-interpretation)
6. [Activity-classification findings](#6-activity-classification-findings-task-b)
7. [PPG vs accelerometer](#7-ppg-versus-accelerometer)
8. [Leakage prevention](#8-leakage-prevention)
9. [Independent verification](#9-independent-verification-and-reproducibility)
10. [How this document was checked](#10-how-this-document-was-checked)
11. [Limitations](#11-limitations)
12. [Next research questions](#12-next-research-questions)

---

## 1. M5 achievements

M5 added a **RECORDED-NON-ASTRONAUT** lane alongside the NASA lab-data lane and the SIMULATED and FL-SIMULATION lanes.

**Data gate (GO):**
- The licence (ODC-By 1.0) and documentation were verified on the owner's page.
- All 59 files are SHA-256-verified against the owner's `SHA256SUMS.txt`, whose own hash is pinned in `src/hyperion_mda/data/physionet/wrist-1.0.0.provenance.json`.
- The **raw recordings** are cached outside the repository and are not bundled. **Derived M6 outputs are tracked** in `experiments/m6/outputs/` (14 files: features, predictions, metrics, `results.json`, `report.md`), which ODC-By 1.0 permits with attribution. The exact tracked/not-tracked split is in `docs/DATA-SOURCE-INVENTORY.md` §3c.

**Standard-library WFDB reader** (`wfdb_reader.py`, format 16 plus MIT annotations):
- Every signal is checked against its header checksum.
- It was cross-checked against the official `wfdb` package in a scratch environment: identical raw samples and physical values for all 19 records × 15 signals, and all 11,388 beat annotations identical.

**Adapter:** `RecordedPhysioNetAdapter` sits behind the existing `WearableAdapter` boundary, with 5 RECORDED-NON-ASTRONAUT registry channels and the playback window.

**HR methods check** (`dsp_hr.py`): a PPG peak-interval estimate, its parameters fixed before results, compared with the hand-marked ECG beats.
- Every one of the 3332 windows was compared.
- The per-record median absolute error ranged from **2.24 bpm** (s3_low_resistance_bike) to **84.19 bpm** (s4_run).
- The worst records were s4_run (84.19), s1_walk (40.44), s8_run (26.58) and s5_run (25.51).

**Documented data anomalies:**
- The wrist clock rolls over every 60 s and jumps by whole seconds, so the uniform 256 Hz index is used.
- Amplitudes are uncalibrated.
- s9_walk has one RR interval of 2.36 s.

**What M5 did not establish:** whether any wrist method generalises across people. That question needed a participant-separated evaluation with baselines, which is M6.

## 2. M6 architecture

M6 is an **offline experiment**. It lives entirely in `experiments/m6/`. It imports the audited M5 modules read-only, and nothing in `src/` imports it.

```text
m6-lopo-config.json  (frozen; SHA-256 recorded in every output)
        │
m6_data.py ──── load_inputs(record)    → PPG + accelerometer only (ECG dropped on read)
        │  └─── load_reference(record) → beat indices from the .atr file only (never reads signals)
        │
m6_features.py  label-free per-window features; frozen M5 method reused as A1
        │
m6_models.py    Standardizer, ridge (closed form), multinomial logistic (L-BFGS),
        │       majority / mean baselines, lopo_predict() with leakage assertions
        │
run_m6.py ───── metrics (m6_metrics.py) → outputs/*.csv, results.json
        │                                 → report.md (m6_report.py, from results.json only)
        │
verify_m6.py    independent standard-library recomputation from the raw CSVs
experiments/m6/tests/test_m6.py  28 tests (scripts/report_counts.py)
```

**Dependencies:** numpy 2.5.4 and scipy 1.18.1 in the project `.venv`. Nothing was installed.

## 3. Methodology and LOPO design

| Element | Specification |
|---|---|
| Windows | 8 s, 2 s step (75% overlap), within one record only; 3332 windows over 19 records |
| HR reference | 60 / median RR of hand-marked chest-ECG R peaks in the window (≥ 3 beats); all 3332 windows eligible |
| Model inputs | Wrist PPG and wrist low-noise accelerometer only. ECG, its annotations and the wrist clock are never inputs. |
| PPG features (15) | M5 band-pass (0.5–4 Hz); per-window z-score; Hann; 8192-point spectrum; 14 relative band powers + dominant frequency |
| Accelerometer features (26) | Magnitude spectrum, 19 relative band powers (0.25–5 Hz) + dominant frequency; 3 axis correlations; 3 log SD shares. **No raw-amplitude features**, because amplitudes are uncalibrated. |
| HR models | **A0** training mean · **A1** frozen M5 · **A2** PPG spectral peak · **A3** ridge on PPG · **A4** ridge on PPG + accel · **A5** ridge on accel only (ablation) |
| Activity models | **B0** majority · **B1** logistic on accel · **B2** logistic on accel + PPG |
| Activity labels | Primary: walk / run / cycle (both bike levels merged). Secondary: 4 classes. Per-record protocol labels. |
| Folds | 8 folds, one per participant, all of that participant's windows held out; no random splitting at any level |
| Hyperparameters | Fixed before any run: ridge α = 1.0, logistic C = 1.0. No tuning. |
| Aggregation | Unweighted mean of per-participant metrics. s1 contributes 26% of the recording time, so pooled-window figures are secondary. |
| Uncertainty | 95% participant bootstrap: 10,000 resamples, seed 20261115, the same indices for every model (paired) |
| Sensitivity | **S1** onset exclusion: *omitted* (no documented onset time). **S2** RR-screened windows removed (31 windows). **S3** aggregates without s4. |
| Reading rule (fixed in advance) | A difference whose interval lies entirely below 0 is evidence; an interval containing 0 is "no evidence either way at n = 8" |

## 4. Heart-rate results (Task A)

All values are bpm, as mean over participants [95% participant-bootstrap interval].

| ID | Model | MAE | RMSE | Mean bias | MAE without s4 |
|---|---|---|---|---|---|
| A0 | Training-mean predictor | 24.18 [12.00, 41.17] | 25.72 [13.51, 42.45] | -8.44 | 16.69 |
| A1 | M5 peak-interval (frozen) | 23.67 [13.84, 37.83] | 28.73 [18.01, 43.53] | -6.09 | 17.46 |
| A2 | PPG spectral peak | 46.32 [29.63, 64.82] | 55.80 [41.32, 72.41] | -3.44 | 44.63 |
| A3 | Ridge, PPG | 30.90 [17.62, 49.00] | 33.94 [20.58, 51.61] | -11.34 | 22.89 |
| A4 | Ridge, PPG + accel | 32.22 [21.29, 46.18] | 35.27 [24.70, 49.17] | -12.62 | 26.33 |
| A5 | Ridge, accel only | 30.06 [21.57, 38.75] | 33.76 [24.67, 42.70] | -13.09 | 28.05 |

**Per-participant MAE:**

| Model | s1 | s2 | s3 | s4 | s5 | s6 | s8 | s9 |
|---|---|---|---|---|---|---|---|---|
| A0 | 28.82 | 14.55 | 12.41 | 76.61 | 25.40 | 9.86 | 23.59 | 2.19 |
| A1 | 18.45 | 20.15 | 9.42 | 67.15 | 25.38 | 16.00 | 26.71 | 6.10 |
| A2 | 23.84 | 56.82 | 40.35 | 58.12 | 54.58 | 24.52 | 99.32 | 13.01 |
| A3 | 33.53 | 33.04 | 22.12 | 87.00 | 31.58 | 12.56 | 20.20 | 7.20 |
| A4 | 31.87 | 30.09 | 15.65 | 73.44 | 40.82 | 14.50 | 35.16 | 16.20 |
| A5 | 30.36 | 32.86 | 21.99 | 44.15 | 51.82 | 12.98 | 31.07 | 15.27 |

**Paired comparisons** (MAE difference, first − second; negative = first model better):

| Difference | Mean [95% CI] | Participants first lower |
|---|---|---|
| A1 − A0 (frozen M5 vs no signal) | -0.51 [-4.85, 3.50] | 4 / 8 |
| A2 − A0 (spectral peak vs no signal) | 22.14 [4.17, 41.84] | 2 / 8 |
| A2 − A1 | 22.65 [7.25, 40.11] | 1 / 8 |
| A3 − A2 | -15.42 [-37.21, 3.33] | 6 / 8 |

**Robustness:**
- **S2 reference-quality screen:** 31 windows removed (28 from s4_run, 3 from s9_walk). A0 24.18, A1 23.33, A2 45.99. No conclusion changed.
- **S3 (without s4):** every MAE drops, but A0 remains the lowest.
- **Frozen-method identity:** A1's per-window errors equal M5 `dsp_hr` exactly on all 19 records.

## 5. Heart-rate estimation: limitations and interpretation

**Measured facts:**
1. **No method is better than ignoring the signal.** The frozen M5 method is level with the training-mean predictor (difference −0.51 [−4.85, 3.50]). All three learned ridge models have higher MAE than A0.
2. **The spectral-peak estimator is clearly worse than A0** (+22.14 [4.17, 41.84]).
   - A post-hoc descriptive check (added after viewing results; no model changed) found that only 14.2% (run) to 35.4% (low-resistance bike) of its windows fall within ±10% of the reference.
   - During running, 28.0% of windows sit near half the reference, and 13.4% near double.
3. **Errors concentrate in a few records:**
   - s4_run is the worst record for A0, A1, A3 and A4.
   - A2's worst records are s8_walk (113.99) and s8_run.
   - The four M5 failure records (s4_run, s1_walk, s8_run, s5_run) are exactly A1's four worst records (ranks 1–4 of 19).
4. **The largest errors sit at the extremes of the reference HR.** The top 10% windows by error have a median reference HR of 57.5 for A0, against 99.1 for all windows; for A1 it is 115.9, and for A3 to A5 it is 120.9–123.9.

**Interpretation** (hypotheses, *not* results):
- *Between-participant HR level dominates.* The audited instantaneous-HR medians run from 57.3 bpm (s1_walk) to 174.5 bpm (s4_run); see `M6-LOPO-PROTOCOL.md` §1. When a method can't read the pulse reliably, the training mean is a hard baseline. This would explain why the ridge models, which learn from only 7 participants, generalise worse than the mean.
- *Motion corrupts the PPG spectrum.* The half-rate and double-rate clusters during running are consistent with the dominant spectral peak tracking wrist or step motion rather than the pulse. This dataset has no motion-free reference PPG to confirm it.
- *The released data mixes preprocessing.* Cycling PPG was low-pass filtered (15 Hz) before release, while walk/run PPG is raw. Any per-activity difference in PPG quality is confounded with that release preprocessing.

**What this does not show:**
- It does not show that wrist PPG cannot estimate HR.
- It does not show that the M5 method is "as good as" anything in an absolute sense.
- It does not show that any result would hold in other people, devices or settings.

## 6. Activity-classification findings (Task B)

**Primary: 3 classes.** Labels are per record; 3332 windows.

| ID | Model | Pooled accuracy | Balanced accuracy | Macro-F1 | Record-level accuracy (19) |
|---|---|---|---|---|---|
| B0 | Majority class | 0.451 | 0.333 | 0.207 | 0.421 |
| B1 | Logistic, accel | 0.733 | 0.720 | 0.731 | 0.842 |
| B2 | Logistic, accel + PPG | 0.715 | 0.707 | 0.708 | 0.895 |

**B1 pooled confusion matrix** (rows = true, columns = predicted):

| | walk | run | cycle |
|---|---|---|---|
| walk | 712 | 7 | 378 |
| run | 10 | 512 | 210 |
| cycle | 117 | 167 | 1219 |

**Per fold, B1** (accuracy / macro-F1; n/a = single-class test fold):

| s1 | s2 | s3 | s4 | s5 | s6 | s8 | s9 |
|---|---|---|---|---|---|---|---|
| 0.540 / 0.492 | 0.887 / 0.866 | 0.968 / 0.968 | 0.000 / n/a | 0.705 / 0.774 | 0.724 / 0.725 | 0.834 / 0.915 | 1.000 / n/a |

**Findings:**
- **There is a real, if modest, signal.** B1 − B0 fold accuracy is 0.384 [0.144, 0.649], higher in 6 of 8 participants.
- **The dominant error is "cycle" absorbing the other classes:** 378 walk windows and 210 run windows were predicted cycle.
- **s4, the only participant running at 10 km/h, is entirely misclassified:** 136 of 143 windows predicted cycle, 7 walk. No other participant has a recorded running speed above 5.5 km/h (s6's speed is unknown). One plausible, untested explanation is that s4's runs lie outside the training distribution.
- **Bike resistance level is not separable** in the secondary 4-class analysis. B1 macro-F1 is 0.528, and high-bike F1 is 0.085.
- **Optimisation:** all 16 logistic fits (B1 and B2 × 8 folds) converged.
- **Caveat:** activity is confounded with participant and self-selected speed, and labels are per record. The classifier may partly learn the person or the intensity rather than the activity.

## 7. PPG versus accelerometer

| Question | Comparison | Mean [95% CI] | Participants |
|---|---|---|---|
| Does adding PPG to accel help HR? | A4 − A5 MAE | 2.15 [-4.33, 11.05] | A4 lower in 3 / 8 |
| Does PPG alone beat accel alone for HR? | A3 − A5 MAE | 0.84 [-9.49, 14.44] | A3 lower in 4 / 8 |
| Does adding accel to PPG help HR? | A4 − A3 MAE | 1.31 [-4.68, 7.59] | A4 lower in 4 / 8 |
| Does adding PPG help activity? | B2 − B1 fold accuracy | -0.007 [-0.046, 0.041] | B2 higher in 3 / 8 |

**Conclusion under the pre-declared reading rule:** every interval includes 0. There is **no evidence at n = 8 that the PPG features contribute information beyond the accelerometer features**, for either task.

Two cautions:
1. This is absence of evidence, not evidence of absence. The intervals are wide (A3 − A5 spans more than 20 bpm).
2. The accelerometer features are amplitude-free (cadence and spectral shape), so "beyond motion" here does not mean "beyond calibrated exercise intensity".

## 8. Leakage prevention

| Risk | Control | Evidence |
|---|---|---|
| Participant leakage | Folds by participant ID; `lopo_predict` asserts disjoint train/test participants and that each row is predicted exactly once | A spy-model test confirms the fit never sees a test-participant row |
| Overlapping windows | Windows never cross a record; records never cross a participant, so any overlapping neighbour is always in the same fold | Fold and window tests |
| Preprocessing leakage | The standardiser is fitted inside each model on training rows only. Per-window normalisation uses only that window. No test-participant normalisation. | Corrupting one participant's features by ×10⁶ leaves that fold's fitted coefficients unchanged, and the scaler mean equals the training-row mean |
| ECG / reference leakage | `RecordInputs` has no ECG field; the feature extractor's signature takes no reference; the reference loader never reads the signal file | Replacing the ECG waveform with random noise leaves every feature and estimate byte-identical (real data) |
| Researcher degrees of freedom | The config (features, models, hyperparameters, sensitivity analyses, seed) was frozen and hashed before any run; A1 frozen as committed | The config SHA-256 is recorded in `results.json`; A1 matches M5 exactly. The one post-hoc addition (the A2 ratio diagnostic) is labelled post hoc and changes no model. |
| Random splitting | None anywhere | A source scan test (no `shuffle` / `permutation`) |

## 9. Independent verification and reproducibility

- **`verify_m6.py`** recomputes the metrics from the raw per-window CSVs using only the standard library (`csv`, `math`), with no shared metric code. **1187 checks passed, 0 failed.** It checks:
  - per-participant, per-record, pooled and aggregate MAE / RMSE / bias for all 6 HR models, in both analyses
  - every paired difference
  - the window-level and record-level confusion matrices
  - accuracy and macro-F1, including the n/a folds
  - that the summary CSVs mirror `results.json`
  - that `report.md` is exactly the rendering of `results.json`
- **Tests:** 27 M6 tests at the time of this run, including a full pipeline run into a temporary directory whose 14 output files are **byte-identical** to `experiments/m6/outputs/`. The 173 existing app tests passed unchanged. *(Historical counts. The suites now collect 28 M6 tests and 185 app tests; recompute with `python scripts/report_counts.py`.)*
- **Provenance in `results.json`:**
  - config SHA-256, dataset-manifest SHA-256, git HEAD, and SHA-256 of every M6 and reused M5 source file
  - Python 3.14.2, numpy 2.5.4, scipy 1.18.1
  - the bootstrap seed

**Reproduce:**

```bash
.venv\Scripts\python experiments\m6\run_m6.py
```

```bash
.venv\Scripts\python experiments\m6\verify_m6.py
```

```bash
.venv\Scripts\python -m unittest discover -s experiments/m6/tests -v
```

## 10. How this document was checked

Every decimal number in this document was extracted mechanically and matched against:
- `experiments/m6/outputs/report.md`
- the frozen config
- a fresh run of the M5 `dsp_hr.run_check()`
- the stated version strings

Each number that matched none of these was examined and listed in the validation report for this revision.

## 11. Limitations

**Sample and population:**
- **n = 8 participants.** The participant-bootstrap intervals are coarse and unstable, and a single participant (s4) moves several means substantially.
- **Non-astronaut population**, terrestrial 1 g, short laboratory sessions. Nothing transfers to astronauts, microgravity, fluid shifts or spaceflight.

**Labels:**
- No stress, clinical, fatigue or outcome labels exist; no such task was attempted.
- Activity labels are per record. Exercise onset is not marked, so S1 was omitted.
- High-bike data comes from only 3 participants.
- Activity is confounded with participant and self-selected speed (2–10 km/h; s6 unknown).

**Signal quality:**
- Release preprocessing differs by activity (cycling PPG low-pass filtered before release).
- Amplitudes are uncalibrated, so no amplitude features were used.
- The wrist clock is unusable, so the uniform sample index is assumed.
- PPG motion artifacts are severe in running and walking.

**Method:**
- Bland–Altman limits are descriptive only, because windows are autocorrelated. No plots were produced.
- Hyperparameters are fixed defaults, not tuned. That is deliberate (no tuning on n = 8), so the learned models are not optimised.
- The paper (MDPI) could not be retrieved, so the protocol facts rest on the PhysioNet project page only.

## 12. Next research questions

1. **Can motion-artifact-aware methods beat the no-signal baseline?** Under the same LOPO design, can a method that uses the accelerometer to suppress motion components in the PPG spectrum beat A0, not just A1? This remains a proposed follow-up question; no M7 implementation or result exists.
2. **Does temporal tracking help?** HR changes slowly between consecutive 2 s steps; does a continuity constraint fix the half-rate and double-rate errors seen in running?
3. **Is the activity "signal" really activity?** How much of B1's accuracy survives speed-matched or participant-balanced analysis? That needs data with more participants per activity.
4. **Do the findings replicate?** Would they hold on a second, independently collected wrist-PPG exercise dataset? Any such dataset must pass the same terms-and-documentation gate as PhysioNet and WESAD; none has been verified yet.
5. **What would an astronaut-relevant evaluation require?** It would need access to astronaut wearable data (none public; NASA LSDA is request-only) and is out of scope until that access exists.
