# M6 protocol: leave-one-participant-out (LOPO) baselines on PhysioNet Wrist PPG

**Status (updated 2026-11-15): APPROVED, IMPLEMENTED AND RUN.**
- Results: [M6-RESULTS-SUMMARY.md](M6-RESULTS-SUMMARY.md), the generated `experiments/m6/outputs/report.md`, and the review document [M6-TECHNICAL-REVIEW.md](M6-TECHNICAL-REVIEW.md).
- The protocol text below is preserved exactly as frozen before any run. That includes its original status line ("PROPOSED PROTOCOL. Not implemented…") and the closing STOP line, both of which are now historical.

**Approved decisions (stage 0):**
1. Fixed, pre-declared hyperparameters (option 1).
2. numpy and scipy only.
3. No desktop UI view.
4. Outputs stored under `experiments/m6/`.
5. A results summary added to `docs/`.
6. S1 kept only if the documentation supports an onset time.

**Deviations from the text below**, each made before the runs unless marked *post hoc*:

| Protocol section | As written | As implemented | Why |
|---|---|---|---|
| §10 files | New modules in `src/hyperion_mda/`; tests in `tests/` | All M6 code in `experiments/m6/` (`m6_data`, `m6_features`, `m6_models`, `m6_metrics`, `run_m6`, `m6_report`, `verify_m6`); tests in `experiments/m6/tests/` | Instruction to keep M6 inside `experiments/m6/`. No `src/` file was changed. |
| §7.2 results location | `~/.hyperion_mda/results/m6/` | `experiments/m6/outputs/` | Approved decision 4 |
| §3.5 S1 | Exclude the first 60 s, or the documented onset | **Omitted** | The PhysioNet page says subjects started "from rest" but gives no onset time; the MDPI paper page returned HTTP 403. Approved decision 6. |
| §5.1 Bland–Altman | Per-participant plot | Bias ± 1.96 SD table only | No plotting dependency is installed, and none was added |
| §7.4 UI view | Optional | Not built | Approved decision 3 |
| §4 B3 random forest | Optional, needs scikit-learn | Not run | Approved decision 2 |
| §7.5 reproducibility | Byte-identical apart from a timestamp | Outputs contain no timestamp; all 14 output files are byte-identical across runs (tested) | Stricter than planned |
| §5.3 failure cases | As listed | As listed, **plus a post-hoc A2 / reference ratio diagnostic** | *Post hoc*, added after viewing the results. Descriptive only; no model or parameter changed. |

---

**Original status at drafting:** "PROPOSED PROTOCOL. Not implemented. No model has been trained and no M6 result exists." Drafted 2026-11-15. Implementation needs explicit approval (§9).

**Scope.** This is a methods demonstration on **non-astronaut** data from a terrestrial laboratory exercise study.
- It makes **no** astronaut-health, clinical, diagnostic or flight-readiness claim.
- Nothing produced under this protocol is shown in, or fed into, the NASA lab-data lane.
- It does not estimate stress. The dataset has **no stress, clinical or outcome labels**.

**Dataset.** PhysioNet *Wrist PPG During Exercise* v1.0.0.
- doi:10.13026/C2PQ1X, licence ODC-By 1.0. Cite Jarchi & Casson, *Data* 2017, doi:10.3390/data2010001.
- Already gated, SHA-256-verified and cached by M5 (`physionet_source`, `wfdb_reader`). Nothing is redistributed.

---

## 1. Dataset and label audit (measured 2026-11-15, read-only)

The audit was run with the M5 verified reader on all 19 records. Beats are the annotation code-1 (`N`) marks on the chest-ECG channel. Instantaneous HR is 60 / RR.

| Record | Header comment (verbatim) | Duration (s) | Beats | First beat (s) | Inst. HR p5 / p50 / p95 (bpm) | Max RR (s) |
|---|---|---|---|---|---|---|
| s1_high_resistance_bike | High resistance biking_level 6 | 589 | 1040 | 0.78 | 85.3 / 108.2 / 129.1 | 0.82 |
| s1_low_resistance_bike | low_resistance biking_level 4 | 579 | 796 | 0.57 | 73.8 / 83.9 / 89.8 | 1.46 |
| s1_walk | Walking_2 km/h | 588 | 563 | 0.03 | 50.2 / 57.3 / 65.6 | 1.46 |
| s2_high_resistance_bike | High resistance biking_level 7 | 414 | 805 | 0.34 | 97.2 / 120.0 / 128.0 | 1.00 |
| s2_low_resistance_bike | low_resistance biking_level 4 | 341 | 611 | 0.56 | 94.2 / 109.7 / 117.3 | 1.13 |
| s2_walk | Walking_2.5 km/h | 399 | 566 | 0.54 | 77.2 / 84.4 / 94.0 | 0.92 |
| s3_high_resistance_bike | High resistance biking_level 8 | 281 | 593 | 0.27 | 114.6 / 128.0 / 136.5 | 0.71 |
| s3_low_resistance_bike | low_resistance biking_level 4 | 294 | 523 | 0.13 | 99.8 / 108.2 / 113.8 | 1.32 |
| s3_run | Running_5.5 km/h | 307 | 565 | 0.04 | 103.8 / 110.5 / 116.4 | 0.62 |
| s3_walk | Walking_2.5 km/h | 287 | 458 | **6.06** | 90.9 / 97.8 / 103.9 | 0.73 |
| s4_run | Running_10 km/h | 292 | 839 | 0.86 | **143.6 / 174.5 / 216.3** | 1.01 |
| s5_low_resistance_bike | low_resistance biking_level 4 | 280 | 576 | 0.51 | 112.9 / 124.9 / 131.3 | 0.61 |
| s5_run | Running_5.5 km/h | 308 | 640 | 0.29 | 118.2 / 124.9 / 132.4 | 0.99 |
| s6_low_resistance_bike | low_resistance biking_level **unknown** | 280 | 536 | 0.07 | 98.7 / 117.3 / 123.9 | 0.70 |
| s6_run | Running_**unknown** km/h | 302 | 478 | 0.53 | 84.9 / 94.8 / 105.9 | 0.84 |
| s6_walk | Walking_**unknown** km/h | 336 | 513 | 0.61 | 86.8 / 91.4 / 98.5 | 0.77 |
| s8_run | Running_5.2 km/h | 287 | 417 | 0.65 | 72.6 / 87.3 / 118.4 | 1.25 |
| s8_walk | Walking_2.7 km/h | 402 | 498 | 1.57 | 66.2 / 74.2 / 83.6 | 1.21 |
| s9_walk | Walking_3 km/h | 220 | 371 | 0.11 | 97.2 / 103.1 / 108.2 | **2.36** |

**Totals:** 19 records, 8 participants (s1–s6, s8, s9; there is no s7), 6786 s, 11,388 beats.

**Participants × activity** (protocol labels taken from the record name):

| Participant | Activities | Recorded time (s) |
|---|---|---|
| s1 | high bike, low bike, walk | 1756 |
| s2 | high bike, low bike, walk | 1154 |
| s3 | high bike, low bike, run, walk | 1169 |
| s4 | run | 292 |
| s5 | low bike, run | 588 |
| s6 | low bike, run, walk | 918 |
| s8 | run, walk | 689 |
| s9 | walk | 220 |

**By activity:**

| Activity | Participants | Records | Time (s) |
|---|---|---|---|
| walk | 6 | 6 | 2232 |
| run | 5 | 5 | 1496 |
| low-resistance bike | 5 | 5 | 1645 |
| high-resistance bike | 3 (s1, s2, s3) | 3 | 1284 |
| cycle (both bike levels) | 5 | 8 | 3058 |

**What labels exist:**

| Label | Exists? | Granularity | Use in M6 |
|---|---|---|---|
| ECG beat annotations (code 1) | Yes | Per beat | **HR reference only.** Never a model input. |
| Activity (walk / run / bike level) | Yes, implied by the record name and header comment | **Per record**, not per window | Classification target (Task B) |
| Speed (km/h) / resistance level | Partly; s6 has "unknown" | Per record | **Not a target.** Reported descriptively only. |
| Stress, affect, clinical state, fatigue, exertion rating | **No** | — | Not used. None may be invented. |
| Exercise onset/offset times within a record | **Not marked in the files** | — | See the sensitivity analysis in §3.5 |

**Audit observations carried into the risks (§8):**
- s3_walk's first annotated beat is at 6.06 s. Windows before it have no reference.
- s9_walk has one RR of 2.36 s. That could be a missed annotation or a genuine pause; it is unresolved and is not "corrected".
- s4_run reaches a p95 of 216 bpm, far above every other record. It is to be inspected, not excluded silently.
- Speeds and levels differ across participants. For example, "run" ranges from 5.2 to 10 km/h. Activity labels are therefore not intensity-matched.

## 2. Supported research tasks

Only tasks the labels in §1 can support are proposed.

**Task A: wrist-PPG heart-rate estimation (regression). Primary task.**
- *Input:* a wrist PPG window, optionally with the wrist low-noise accelerometer x/y/z from the same window.
- *Target:* the reference HR for that window, 60 / median RR of the code-1 ECG beats within it. This is identical to M5's `dsp_hr` reference definition.
- *Window:* 8 s with a 2 s step, i.e. M5's `WINDOW_S = 8` and `STEP_S = 2`, kept for comparability.
- *Eligibility:* a window needs at least `MIN_BEATS = 3` reference beats (the M5 rule).

**Task B: activity classification from wrist signals. Secondary task.**
- *Primary label set: 3 classes, `walk` / `run` / `cycle`.* Both bike levels are merged because high-resistance bike has only 3 participants. This merge is decided **before** any results.
- *Secondary label set: 4 classes, splitting `cycle` into low and high resistance.* Reported with an explicit caveat that only 3 participants can ever supply high-bike test data.
- *Input:* wrist accelerometer, optionally with PPG. ECG is never an input.
- **Label caveat:** labels are **per record**. Every window inherits its record's label, and no per-window activity truth exists. Window accuracy therefore measures agreement with the protocol label, not verified moment-by-moment activity.
- *Also reported:* a record-level result, the majority vote of a record's windows. There are only 19 records.

**Not supported, so not proposed:** stress or affect classification, any clinical or fatigue state, speed regression (s6 is unknown and there are only 19 records), and anything presented as astronaut-relevant performance.

## 3. LOPO methodology

### 3.1 Outer loop
- 8 folds, one per participant. In each fold, **all** records of one participant form the test set and the remaining 7 participants form the training set.
- The fold order is the sorted participant IDs. It is deterministic and there is no shuffling.
- Every number reported is computed only from outer-fold test predictions.

### 3.2 Hyperparameters
Two options. **Option 1 is recommended** for its simplicity and auditability at n = 8.
1. **Fixed hyperparameters, declared in the frozen config before any run.** The values are ridge α = 1.0 and logistic-regression L2 C = 1.0 on standardised features. They are conventional defaults and are **not** tuned on this data.
2. **Nested inner LOPO.** For each outer fold, a 7-fold inner LOPO over the training participants picks α or C from a pre-declared grid {0.01, 0.1, 1, 10, 100}. The test participant is never seen during selection. Each outer fold reports the selected value.

### 3.3 Fitting boundaries (per outer fold)
1. Feature extraction is deterministic and label-free, and it runs per window (§6.3).
2. Feature standardisation (mean and SD) is fitted on **training-participant windows only**, then applied unchanged to the test participant.
3. The model is fitted on the training participants only.
4. The model predicts on the test participant, and those predictions are stored.

There is no per-test-participant calibration, adaptation or normalisation that uses the test participant's data (no transductive steps).

### 3.4 Uncertainty
- Each participant's metric is computed per participant.
- The aggregate is the **unweighted mean over the 8 participants**, plus the median and range.
- A **95% bootstrap interval** resamples **participants** (not windows) with replacement: 10,000 resamples, seed fixed in the config. With n = 8 this interval is coarse and unstable, and it is reported as such.
- Window-level intervals are **not** reported. Windows overlap and are autocorrelated within a participant, so treating them as independent would overstate precision.

### 3.5 Pre-specified sensitivity analyses
The primary analysis is unchanged by these; they are reported alongside it.
- **S1 (record start):** the files do not mark exercise onset, so early windows may not match the activity label. Task B is re-run excluding each record's first 60 s.
  - 60 s is an arbitrary, pre-declared analysis parameter, not a physiological constant.
  - At stage 0 the dataset paper's description of the recording procedure is checked. If it states an onset, that value replaces 60 s, and the change is recorded **before** any run.
- **S2 (reference quality):** Task A is re-run excluding windows that contain any reference RR > 1.5 s or < 0.25 s.
  - These bounds are pre-declared data-quality screens on the annotations, not clinical thresholds.
  - The primary analysis keeps all eligible windows. The number of windows excluded is reported per record.
- **S3 (s4 influence):** aggregates are reported with and without participant s4, whose reference HR distribution is the outlier noted in §1. s4 is **never** dropped from the primary analysis.

## 4. Baseline models

Every model is a deliberately simple baseline. No neural network, deep model or ensemble is proposed for M6.

**Task A (HR).** Models are in order of complexity.

| ID | Model | Trained? | Inputs | Purpose |
|---|---|---|---|---|
| A0 | Training-mean predictor: the mean reference HR of the training participants' windows | Yes (one number) | none | Floor: what "no signal" achieves |
| A1 | **M5 untuned peak-interval method**, `dsp_hr` exactly as committed (band 0.5–4 Hz, Butterworth order 3, `sosfiltfilt`, min peak distance 0.33 s, prominence 0.5 × SD, ≥ 3 peaks) | No | PPG | Continuity with M5. **Frozen**: its parameters may not be changed now that M5 per-record results have been seen (§6.5). |
| A2 | Spectral peak: the dominant frequency of the band-passed PPG (Hann window, 0.5–4 Hz), × 60 | No | PPG | Standard non-learned estimator |
| A3 | Ridge regression on PPG spectral features | Yes | PPG | Learned, PPG only |
| A4 | Ridge regression on PPG and accelerometer spectral features | Yes | PPG + accel | Learned, with motion context |
| A5 | Ridge regression on accelerometer features only | Yes | accel | **Ablation.** Measures how much HR is predictable from motion intensity alone, without any PPG. |

A5 is essential for honest interpretation. If A4 beats A3 but A5 alone is close to A4, the "improvement" is the model learning activity intensity, not reading the pulse from the PPG.

**Task B (activity).**

| ID | Model | Trained? | Inputs |
|---|---|---|---|
| B0 | Majority class of the training fold's windows | Yes | none |
| B1 | Multinomial logistic regression (L2) | Yes | accel features |
| B2 | Multinomial logistic regression (L2) | Yes | accel + PPG features |
| (B3) | Random forest | Optional; **not proposed** unless approved, because it needs scikit-learn (see the dependency note) | accel |

**Dependency note.** The project `.venv` contains only numpy 2.5.4 and scipy 1.18.1. scikit-learn exists in the global Python but **not** in `.venv`, and the global install is not to be used.
- **Recommended:** implement ridge in closed form (numpy) and multinomial logistic regression with `scipy.optimize.minimize` (L-BFGS). This needs **no new dependency**.
- **Alternative:** add `scikit-learn` to `.venv`, only with separate approval. It would also unlock B3.

## 5. Evaluation metrics

### 5.1 Task A (HR, bpm)
**Per participant and per record:**
- MAE
- RMSE
- bias (mean signed error, estimate − reference)
- SD of the error
- median absolute error, kept for continuity with M5
- **coverage**: the fraction of eligible windows for which the method produced an estimate. A1 can decline windows with fewer than 3 peaks.

**Aggregate:** the unweighted mean over participants with its participant-bootstrap 95% interval, plus the median and range across participants. Pooled window-level MAE and RMSE are reported as secondary figures, labelled as dominated by long-recording participants: s1 contributes 26% of the time.

**Common-window comparison:** each method is scored on its own covered windows and also on the intersection of windows covered by every method. This stops a method from looking better simply by declining hard windows.

**Bland–Altman:** a per-participant plot of the difference against the mean, with bias ± 1.96 SD. This is **descriptive only**; because windows are autocorrelated, these limits are not valid agreement limits.

### 5.2 Task B (activity)
**Pooled over all 8 outer test folds:**
- confusion matrix
- accuracy
- balanced accuracy
- macro-F1
- per-class precision, recall and F1

**Per fold:**
- accuracy
- the test classes present
- macro-F1 **only over the classes present** in that fold, flagged as such

The s4 fold (run only) and the s9 fold (walk only) are single-class, so their per-fold macro-F1 is reported as "n/a: single-class test fold".

**Record level:** the majority-vote label per record (19 records), as a confusion matrix.

### 5.3 Variability and failure cases
- **Variability:** the per-participant metric table for every model, the across-participant SD, and the participant-bootstrap interval (§3.4).
- **Failure-case analysis** (descriptive, no new thresholds):
  - the worst-MAE participant and the worst-MAE record for each model
  - the top 10% of windows by absolute error, described by activity, accelerometer magnitude and reference HR
  - whether the M5 failure records (s4_run, s1_walk, s8_run, s5_run) remain the worst under A2 to A4
- Results are reported **as measured**, including when a learned model does no better than A0, A1 or A2.

**No expected values are stated anywhere in this protocol. The outcomes are unknown until run.**

## 6. Leakage prevention

### 6.1 Participant leakage
- Folds are defined by participant ID. A unit test asserts that the sets of training and test participant IDs are disjoint in every outer **and** inner fold.
- A unit test also asserts that every window carries its participant ID and that no window appears in two folds' test sets.

### 6.2 Overlapping-window leakage
- 8 s windows with a 2 s step overlap by 75%, so adjacent windows share 6 s of samples.
- Windows never cross a record boundary, and records never cross a participant, so any overlap is entirely **within a participant**. LOPO therefore puts every overlapping neighbour on the same side of the split.
- Any inner split must also be by participant. A random-window split or k-fold split is **prohibited** at every level, and a test checks that no fold builder can split windows randomly.

### 6.3 Preprocessing and normalisation boundaries

| Step | Uses data from | Allowed? |
|---|---|---|
| Band-pass filter (`sosfiltfilt`, zero-phase) applied per record | That record only, no labels | Yes: deterministic and label-free. Zero-phase filtering looks ahead within the record; this is acceptable for an offline methods study and is stated as non-causal. |
| Per-window PPG z-normalisation (that window's own mean and SD) | That window only | Yes: no information from other windows or participants |
| Feature standardiser (mean and SD) | **Training participants only** | Yes, refitted every fold |
| Per-participant normalisation using the test participant's whole recording | Test participant | **No**, prohibited in the primary analysis |
| Feature selection or engineering decisions | — | Fixed in the config before any run, never chosen from outer-fold results |
| Class list and label encoding | A priori (§2) | Yes, fixed globally; this carries no data information |
| Hyperparameters | Config (option 1) or the inner folds (option 2) | Never chosen from the outer test fold |

### 6.4 Reference and target leakage
- **ECG is never an input.** The feature extractor receives only the PPG and accelerometer arrays, and a unit test asserts that the ECG channel index is never read by `wrist_features`.
- Reference HR and beat positions are computed separately and joined only at scoring time.
- The wrist timestamp channel (channel 15) is not used. It has the M5-documented rollover and jumps.

### 6.5 Researcher-degrees-of-freedom leakage
- **M5 per-record HR results have already been seen.** Changing the A1 method's parameters, or picking A2 to A4 features to fix the M5 failure records, would amount to tuning on all 8 participants.
- Therefore A1 is frozen as committed, and every A2 to A5 / B1 to B2 feature and parameter is written in the frozen config at stage 0 (§9), **before** any LOPO run.
- The config's SHA-256 is recorded in every result file. Any later change creates a new, separately labelled config version, and both are reported.

## 7. Expected outputs (artifacts, not results)

1. **Frozen config** (`experiments/m6/m6-lopo-config.json`) holding:
   - the window and step, filters and features for each model
   - the hyperparameters (or the inner grid)
   - the sensitivity parameters and bootstrap seed and count
   - the dataset manifest hash
2. **Per-run result file** (JSON) holding:
   - the config SHA-256, the git commit, the dataset manifest SHA-256 and the Python and numpy/scipy versions
   - the per-window predictions (participant, record, window start, reference, estimate per model)
   - the per-participant metrics and the aggregate metrics with intervals
   - the window exclusion counts

   It is written **outside the repository**, under `~/.hyperion_mda/results/m6/` (or `HYPERION_MDA_DATA_DIR`), because it holds derived per-window data. Whether aggregate tables may be copied into `docs/` is decided after review.
3. **Markdown report** generated from the result file, holding:
   - the per-participant tables, aggregate tables and confusion matrices
   - the sensitivity analyses
   - the failure-case list
   - the caveats in §8

   Every number in it is copied programmatically from the result file.
4. **Optional read-only UI view** in the recorded lane showing the report, with a **RECORDED-NON-ASTRONAUT · METHODS DEMO · NOT VALIDATED** banner. It is never shown in the NASA lane.
5. **Reproducibility check:** two runs from a clean cache must produce byte-identical result files, apart from the timestamp field.

## 8. Risks and limitations

| Risk | Consequence | Mitigation / how it is reported |
|---|---|---|
| **Only 8 participants** | Every aggregate rests on n = 8, intervals are wide and unstable, and one participant can swing the mean | Per-participant tables first, participant bootstrap, the S3 with/without-s4 analysis; no "better than" claim without overlapping-interval caveats |
| **Non-astronaut population**, terrestrial lab exercise, 1 g | No transfer to astronauts, microgravity, fluid shifts or spaceflight HR is implied | Lane separation (tested); a banner on every output; nothing feeds the NASA lane |
| **Wrist timestamp anomalies** (60 s rollover, whole-second jumps) | The true sample timing is uncertain | The uniform 256 Hz index is used, as in M5; channel 15 is unused; stated in the report |
| **PPG motion artifacts**, worst during running and walking (M5: s4_run, s1_walk) | Spectral and peak estimators can lock onto cadence instead of pulse | The A5 accelerometer-only ablation, per-activity error breakdown, and the common-window comparison |
| **Uncalibrated amplitudes** (implausible "mV" values) | Absolute amplitude features are meaningless across participants | Only frequency-domain and per-window-normalised features; no raw-amplitude features |
| **No stress, clinical or outcome labels** | No such model can be built | Out of scope (§2); stated in the report |
| **Activity labels are per record**, and onset is unmarked | Window labels may be wrong near record starts | Record-level results and the S1 onset sensitivity analysis |
| **Activity is confounded with participant and intensity** (speeds 2–10 km/h; s6 unknown) | The classifier may learn intensity or person, not activity | LOPO; per-class recall per fold; stated caveat |
| **High-bike class has only 3 participants**; s4 and s9 folds are single-class | The 4-class result is fragile, and per-fold macro-F1 is undefined for 2 folds | 3-class primary label set; pooled confusion matrix; "n/a" reporting |
| **Reference quality** (s9 RR 2.36 s, s4 HR up to 216 bpm) | Reference errors become apparent model errors | The S2 reference-quality analysis; references are listed, never edited |
| Prior exposure to the M5 results | Unconscious tuning | Config frozen and hashed before any run (§6.5) |
| Python 3.14 with recent numpy and scipy | Numerical results may differ slightly across versions | Versions recorded in every result file |

## 9. Implementation stages (each needs approval; **nothing starts until this protocol is approved**)

| Stage | Work | Data touched | Training? | Stop for approval? |
|---|---|---|---|---|
| **0. Freeze** | Resolve the open decisions (below). Check the dataset paper for exercise-onset information. Write and hash `m6-lopo-config.json`. | Documentation only | No | **Yes** |
| **1. Windows and features** | `wrist_features.py`: windowing, deterministic features, ECG-exclusion guard. Unit tests on **synthetic sinusoids of known frequency**, in the test fixtures only. | Synthetic test signals; real records only for shape and count checks | No | No |
| **2. Fold builder and leakage tests** | `lopo.py`: participant folds (outer and optional inner) and the fit/transform boundary. All §6 tests. | Window metadata only | No | **Yes**: review the leakage tests before any model runs |
| **3. Untrained baselines** | Run A0 (a trivial fit), A1, A2 and B0 under LOPO; result file plus report generator (`eval_report.py`). | Real records | A0 and B0 only (trivial) | No |
| **4. Trained baselines** | A3–A5 and B1–B2 (numpy/scipy implementations), plus the sensitivity analyses S1–S3. | Real records | **Yes**, linear models only | **Yes**: results reviewed as measured |
| **5. Reproducibility** | Two clean runs, byte comparison; full test suite (173 existing plus new tests). | — | — | No |
| **6. UI and docs** | Optional read-only report view; documentation updates (§10). | — | — | **Yes**: before any commit |

*Count note (added after the R6 review): "173 existing" in stage 5 is the frozen figure at drafting. The app suite now collects 185 and the M6 suite 28 — `python scripts/report_counts.py`. The frozen protocol text is otherwise unchanged.*

**Open decisions for the user at stage 0:**
1. Hyperparameter option 1 (fixed, recommended) or option 2 (nested).
2. numpy/scipy implementations (recommended, no new dependency) or adding scikit-learn to `.venv`.
3. Whether the optional UI view (stage 6) is wanted.
4. Whether aggregate result tables may be copied into `docs/` after review.

## 10. Files that would change later (nothing is changed now)

**New:**

| File | Purpose |
|---|---|
| `src/hyperion_mda/wrist_features.py` | Windowing and features; ECG-exclusion guard |
| `src/hyperion_mda/lopo.py` | Participant fold builder, fit/transform boundary, baseline models A0–A5 and B0–B2 |
| `src/hyperion_mda/eval_report.py` | Metrics, participant bootstrap, result JSON, Markdown report |
| `experiments/m6/m6-lopo-config.json` | Frozen config, **outside the package** (see note) |
| `tests/test_wrist_features.py` | Synthetic known-frequency tests; ECG never read |
| `tests/test_lopo.py` | Disjoint folds, no window in two test sets, scaler fitted on training data only, no random splits, determinism, lane-separation imports |

**Modified (stage 6, after approval):**

| File | Change |
|---|---|
| `src/hyperion_mda/recorded_view.py` | Optional "LOPO methods report" button; read-only display |
| `tests/test_physionet.py` / `tests/test_demo_lanes.py` | Extend the import-direction and lane-separation audits to the new modules |
| `.gitignore` | Only if any results path is ever placed inside the repository (the default is outside) |
| `README.md`, `docs/IMPLEMENTATION-STATUS.md`, `docs/ARCHITECTURE.md`, the retired WESAD training plan, `docs/REQUIREMENTS-TRACEABILITY.md` | Describe M6 as implemented and add the measured results only after stage 4 review |

**Not modified:**
- `pyproject.toml` package-data
- the main window's buttons
- the NASA lane modules
- the signal registry
- the three ZIPs in `dist/` *(frozen wording; no `dist/` archives are present in this repository — `dist/` is git-ignored and no builder is included)*

**Note on the config location:** `tests/test_packaging.py` asserts the exact list of package-data globs and the exact set of shipped JSON files. A config placed under `src/hyperion_mda/data/` would break those two existing tests. That is why the config lives in `experiments/m6/`.

---
*STOP. This protocol is awaiting approval. No implementation, training or evaluation has been performed.*
