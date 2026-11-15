# M6 results summary: LOPO baselines on PhysioNet Wrist PPG (measured 2026-11-15)

> **RECORDED-NON-ASTRONAUT METHODS DEMONSTRATION. NOT VALIDATED.**
>
> - **Data:** 8 adults doing terrestrial laboratory exercise.
> - **What this is:** measurements of simple baselines on this one dataset.
> - **What it isn't:** no astronaut, spaceflight, clinical or device-performance claim. Not shown in the desktop app.

**Source of truth.**
- Protocol: [M6-LOPO-PROTOCOL.md](M6-LOPO-PROTOCOL.md).
- Full generated report, with every table: [experiments/m6/outputs/report.md](../experiments/m6/outputs/report.md).

All numbers below are copied from that report. They are checked against `results.json` and the raw prediction CSVs; see Verification.

## Setup (as frozen in `experiments/m6/m6-lopo-config.json`)

- **Data:** 19 records, 8 participants (s1–s6, s8, s9), 3332 windows (8 s window, 2 s step). All 3332 windows have at least 3 reference beats.
- **Folds:** leave-one-participant-out, 8 folds. All windows of a participant are in one test fold, so overlapping windows never cross folds.
- **Fitting:** standardisation is fitted on the training participants only.
- **Hyperparameters:** fixed (ridge α = 1.0, logistic C = 1.0); no tuning.
- **Dependencies:** numpy and scipy only.
- **ECG:** reference only. Heart rate is 60 / median RR of the hand-marked R peaks. The ECG waveform is never loaded as an input; this is tested by replacing it with noise and checking the features are unchanged.
- **Aggregates:** the unweighted mean over the 8 participants, with a 95% participant-bootstrap interval in brackets (10,000 resamples, seed 20261115).
- **Frozen M5 method (A1):** its per-window errors are identical to M5 `dsp_hr.check_record` on all 19 records.

## Heart rate (Task A): estimate vs ECG reference, bpm

| ID | Model | MAE | RMSE | MAE without s4 (S3) |
|---|---|---|---|---|
| A0 | Training-mean predictor (no signal) | 24.18 [12.00, 41.17] | 25.72 [13.51, 42.45] | 16.69 |
| A1 | M5 peak-interval method (frozen) | 23.67 [13.84, 37.83] | 28.73 [18.01, 43.53] | 17.46 |
| A2 | PPG spectral peak (untrained) | 46.32 [29.63, 64.82] | 55.80 [41.32, 72.41] | 44.63 |
| A3 | Ridge, PPG features | 30.90 [17.62, 49.00] | 33.94 [20.58, 51.61] | 22.89 |
| A4 | Ridge, PPG + accelerometer | 32.22 [21.29, 46.18] | 35.27 [24.70, 49.17] | 26.33 |
| A5 | Ridge, accelerometer only (ablation) | 30.06 [21.57, 38.75] | 33.76 [24.67, 42.70] | 28.05 |

**Per-participant MAE, bpm:**

| Model | s1 | s2 | s3 | s4 | s5 | s6 | s8 | s9 |
|---|---|---|---|---|---|---|---|---|
| A0 | 28.82 | 14.55 | 12.41 | 76.61 | 25.40 | 9.86 | 23.59 | 2.19 |
| A1 | 18.45 | 20.15 | 9.42 | 67.15 | 25.38 | 16.00 | 26.71 | 6.10 |
| A2 | 23.84 | 56.82 | 40.35 | 58.12 | 54.58 | 24.52 | 99.32 | 13.01 |
| A3 | 33.53 | 33.04 | 22.12 | 87.00 | 31.58 | 12.56 | 20.20 | 7.20 |
| A4 | 31.87 | 30.09 | 15.65 | 73.44 | 40.82 | 14.50 | 35.16 | 16.20 |
| A5 | 30.36 | 32.86 | 21.99 | 44.15 | 51.82 | 12.98 | 31.07 | 15.27 |

**What was measured:**
- **No method beat the no-signal baseline.**
  - A1 vs A0: −0.51 [−4.85, 3.50] bpm.
  - Every learned ridge model had higher MAE than A0.
  - On this dataset, these simple wrist-PPG methods did not estimate heart rate better than predicting the training participants' mean.
- **The spectral-peak baseline (A2) was the worst:** A2 − A0 = 22.14 [4.17, 41.84] bpm.
  - A post-hoc descriptive check found that only 14–35% of A2 windows fall within ±10% of the reference.
  - During running, 28.0% of windows sit near half the reference rate. That is consistent with the peak locking onto motion rather than the pulse; it is not proven.
- **s4 dominates the error.** s4 ran at 10 km/h with a reference median of 175 bpm, and is the worst participant for A0, A1, A3 and A4. Without s4 every MAE falls (S3 column above), but the ranking of A0 vs the others does not change.
- **The S2 reference-quality screen** (RR < 0.25 s or > 1.5 s; 31 windows removed: 28 from s4_run, 3 from s9_walk) changed no conclusion. A0 is 24.18 and A1 is 23.33.

## Does PPG add information beyond motion? (Stage 4)

The reading rule was fixed before any result was computed. An interval entirely below 0 is evidence for PPG; an interval that includes 0 is *no evidence either way at n = 8*.

| Difference (MAE, bpm) | Mean [95% CI] | Participants where first is lower |
|---|---|---|
| A4 (PPG + accel) − A5 (accel only) | 2.15 [−4.33, 11.05] | 3 / 8 |
| A3 (PPG only) − A5 (accel only) | 0.84 [−9.49, 14.44] | 4 / 8 |
| Activity: B2 (accel + PPG) − B1 (accel) fold accuracy | −0.007 [−0.046, 0.041] | 3 / 8 higher |

**Answer: no evidence that the PPG features contribute information beyond the accelerometer features**, for heart rate or for activity, in this dataset at n = 8. Two cautions about what this means:
- This is not evidence that PPG carries no pulse information.
- The accelerometer features used here are amplitude-free (cadence and spectral shape), so "motion" here does not mean calibrated exercise intensity.

## Activity classification (Task B)

The primary label set has 3 classes (walk / run / cycle, bike levels merged). Labels are per record, not per window.

| ID | Model | Pooled accuracy | Balanced accuracy | Macro-F1 | Record-level accuracy (19) |
|---|---|---|---|---|---|
| B0 | Majority class | 0.451 | 0.333 | 0.207 | 0.421 |
| B1 | Logistic, accelerometer | 0.733 | 0.720 | 0.731 | 0.842 |
| B2 | Logistic, accelerometer + PPG | 0.715 | 0.707 | 0.708 | 0.895 |

B1 pooled confusion matrix (rows = true, columns = predicted):

| | walk | run | cycle |
|---|---|---|---|
| walk | 712 | 7 | 378 |
| run | 10 | 512 | 210 |
| cycle | 117 | 167 | 1219 |

**Per-fold results.** The cells show B1 accuracy / macro-F1. s4 (run only) and s9 (walk only) are single-class folds, so their macro-F1 is n/a.

| s1 | s2 | s3 | s4 | s5 | s6 | s8 | s9 |
|---|---|---|---|---|---|---|---|
| 0.540 / 0.492 | 0.887 / 0.866 | 0.968 / 0.968 | 0.000 / n/a | 0.705 / 0.774 | 0.724 / 0.725 | 0.834 / 0.915 | 1.000 / n/a |

**What was measured:**
- **B1 beats the majority baseline:** B1 − B0 fold accuracy is 0.384 [0.144, 0.649], higher in 6 of 8 participants.
- **The failures are participant-specific.**
  - All 143 of s4's run windows were misclassified; B1 called 136 of them cycle.
  - s1 scored 0.540.
- **4-class secondary analysis:** B1 macro-F1 is 0.528. The high-bike F1 is only 0.085, since just 3 participants can supply high-bike data. Bike resistance level was not separable with these features.
- All 16 logistic fits converged.

## Limitations (details in the report, §7)

- **n = 8.** The intervals are coarse and unstable.
- **Population:** non-astronaut, terrestrial, 1 g.
- **Labels:** per-record activity labels, and exercise onset is not marked.
  - Subjects started from rest, but no onset time is documented, so **sensitivity analysis S1 was omitted** as approved.
  - The MDPI paper page returned HTTP 403 and could not be checked.
- **Confounding:** activity is confounded with participant and self-selected speed (2–10 km/h; s6 unknown).
- **Release preprocessing differs by activity.** The dataset documentation states the cycling PPG was low-pass filtered (15 Hz) before release, while walk/run PPG is raw. The PPG features here are restricted to 0.5–4 Hz.
- **Signal issues:**
  - the wrist clock is not used
  - amplitudes are uncalibrated, so no raw-amplitude features are used
  - PPG motion artifacts are severe
- **No stress, clinical or outcome labels**, so no such task was attempted.
- **Bland–Altman values are descriptive only.** No plot was made, because no plotting dependency is installed.

## Verification

- **Independent verifier:** `verify_m6.py` (standard library only) recomputes metrics from the raw per-window CSVs. 1187 checks passed and 0 failed. It also confirms `report.md` is exactly the rendering of `results.json`.
- **Tests:** 27 M6 tests in `experiments/m6/tests/` covered leakage, the ECG guard, model and metric correctness, the frozen-A1 identity and byte-identical reproducibility, and the 173 existing app tests passed unchanged. *(Counts as at the M6 run on 2026-11-15. The suites now collect 28 M6 tests and 185 app tests — one M6 provenance test and the R1 assay-rejection tests were added since. Recompute with `python scripts/report_counts.py`.)*

## Reproduce

```bash
.venv\Scripts\python experiments\m6\run_m6.py
```

```bash
.venv\Scripts\python experiments\m6\verify_m6.py
```

```bash
.venv\Scripts\python -m unittest discover -s experiments/m6/tests -v
```

Requirements:
- The verified PhysioNet cache from M5 (`python -m hyperion_mda.physionet_fetch`).
- The project `.venv` with numpy and scipy.

Outputs are written to `experiments/m6/outputs/`.
