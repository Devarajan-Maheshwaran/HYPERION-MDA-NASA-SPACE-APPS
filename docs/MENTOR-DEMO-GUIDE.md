# HYPERION-MDA mentor demonstration guide

Prepared 2026-11-15 for the hackathon mentor review.
- **Platform checked:** Windows 11, Python 3.14.2, project `.venv` (numpy 2.5.4, scipy 1.18.1).
- **Where the expected outputs come from:** every quoted on-screen string was captured by driving the real app classes on this machine. Every number comes from the verified M5/M6 outputs.

> **What you are demonstrating:** a tested, local software prototype with **four separate data lanes** that never share data, plus an offline research experiment (M6).
>
> **What it is not:** a medical device, a diagnostic or risk tool, a validated algorithm, or a flight system. It has no NASA approval, no clinical validation and no standards compliance.

## 0. Framing: say this first (30 seconds)

The request for this demo listed six capabilities. Here is what exists for each, so nobody is surprised during the review:

| Requested | What actually exists | Where |
|---|---|---|
| Simulated astronaut health measurements | **Simulated wearable signals.** They are **not astronaut data** and have no health meaning; their banner says so. The only astronaut data is **real**: NASA OSDR OSD-575 serum lab values from the 4 Inspiration4 crew. | *Simulated wearable…* and the NASA lane |
| Recorded PhysioNet wearable data | Real recorded data from **8 non-astronaut adults** in a lab exercise study, replayed through the adapter boundary | *Recorded wearable (PhysioNet)…* |
| Data validation | SHA-256 verification of every file, schema checks, WFDB header checksums, and sample validation at the adapter boundary | All lanes |
| Heart-rate analysis | The M5 HR methods check (in the app) and the M6 LOPO baselines (offline) | Recorded window; `experiments/m6` |
| Activity classification | **Offline only (M6).** It is not in the desktop app. | `experiments/m6/outputs/report.md` §5 |
| Health visualization | **Data visualization without health meaning:** a channel/status panel, mission-timepoint charts and signal playback. There are no health scores, risk levels or cutoffs. | Channel panel, main chart, playback |

**Lane separation:** the NASA lane never shows PhysioNet or simulated values. Each recorded or simulated window has its own banner and title, and the tests check that the lanes import nothing from one another.

---

## 1. Before the session (needs internet once; about 10 minutes)

Run all commands in a terminal in the repository root unless the step says otherwise. The captured session used Windows; on Linux/macOS use `.venv/bin/python` (or `.venv-api/bin/python`) and forward slashes.

**1. Check the environment** (no installs; numpy and scipy are already in `.venv`):

```bash
.venv\Scripts\python -c "import numpy, scipy, tkinter; print(numpy.__version__, scipy.__version__)"
```

Expected: `2.5.4 1.18.1`

**2. Make sure both datasets are cached and verified.** Skip this if they already are; the tests in step 3 will tell you. Run from `src/`:

```bash
cd src
```

```bash
..\.venv\Scripts\python -m hyperion_mda.osdr_fetch
```

```bash
..\.venv\Scripts\python -m hyperion_mda.physionet_fetch
```

```bash
cd ..
```

Each command verifies every file by SHA-256 and saves nothing if any check fails. **If either prints a failure, do not present that lane.** No other data is substituted.

**3. Run all tests** (about 1 minute in total):

```bash
.venv\Scripts\python -m unittest discover -s tests
```

```bash
.venv\Scripts\python -m unittest discover -s experiments/m6/tests
```

Expected: `OK` for both, with no failures or errors. The suites collect **185** tests in `tests/` and **28** in `experiments/m6/tests/` (recompute with `python scripts/report_counts.py`). With the `.venv`, Tkinter and both caches present on the development machine, the historical Windows run reported `Ran 173 … OK` / `Ran 27 … OK`; those logs predate the R1 assay-rejection tests and one added M6 provenance test, so today's totals are higher. **Quote the number your own run prints.** If the real-data tests skip, the reason is printed; go back to step 2.

The main suite also prints `OSDR download FAILED: boom` and `PhysioNet download FAILED: boom`. **These are expected.** They come from tests that inject a download failure on purpose, to check that nothing is saved when a download fails. Mention this if the terminal is on screen.

**4. Rehearse the M6 commands once** (section 3). Re-running M6 rewrites `experiments/m6/outputs/` with byte-identical files.

**5. Screen setup:** maximise each window, set display scaling to 125% or less if possible, and close notification pop-ups.

---

## 2. Live demonstration sequence (about 15 minutes)

### Step 1: Launch the desktop app (30 s)

```bash
.venv\Scripts\python run.py
```

Use the `.venv` interpreter. The plain system Python opens the app, but **Run HR methods check** will then show a "needs numpy and scipy" dialog.

**Show:** the window title `HYPERION-MDA · Local Data Demo` and the banner **`RESEARCH PROTOTYPE · NO DATA LOADED · NOT FOR MEDICAL DECISIONS`**. Maximise the window.

**Say:** nothing loads automatically, and there is no built-in sample data in the main table.

### Step 2: NASA lane, real astronaut lab data (3 min)

**Click:** **Load NASA OSDR OSD-575 CMP (verified)**.

**Expected:**
- Status: `NASA lab data · 531 rows · 22 NA · OSD-575 CMP · SHA-256 verified`
- Banner: `NASA LAB DATA · OSDR OSD-575 · sparse laboratory measurements — not wearable telemetry · serum metabolic panel (CMP) from the 4 Inspiration4 crew · NOT FOR MEDICAL DECISIONS`
- The table has 531 rows.

**Click** the first post-flight row (`R+1 · C001 · ALBUMIN · 4.9 g/dL`). The details panel shows:
- `Descriptive z (unvalidated): -1.15`
- `Score basis: vs 3 earlier pre-flight baseline readings (mean 4.96667, SD 0.0577); descriptive comparison only, unvalidated`
- `Source: line 71 of LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`

The chart shows that person's values across L-92 … R+194, with a "flight" marker. The spacing is not to scale.

**Say:**
- Each post-flight value is compared only with the same person's pre-flight values. There is no threshold, no flag and no reference range.
- `NA` values stay visible and are never imputed.

### Step 3: Channel panel (1.5 min)

**Click:** **Channel panel…**

**Expected:**
- Title: `HYPERION-MDA · Channel panel (not a validated digital twin)`
- Notice: `NOT A VALIDATED PHYSIOLOGICAL DIGITAL TWIN · …`
- Heading: `49 channels · all regions`

**Click** the **Wrist** region. The *Recorded · non-astronaut*, *Simulated* and *Unavailable* (WESAD) channels appear side by side.

**Say:** every channel has exactly one status. The counts are 19 measured lab-sample, 5 recorded non-astronaut, 3 simulated and 22 unavailable. Channels with no public source stay *Unavailable* and have no values.

### Step 4: Simulated lane (1.5 min)

**Click:** **Simulated wearable…**, then **Start**, **Pause**, drag the time slider, then **Reset**.

**Expected:**
- Title: `HYPERION-MDA · SIMULATED wearable playback`
- Banner: `SIMULATED WEARABLE PLAYBACK · every value is generated by a fixed formula · not measured, not from a device, not astronaut data · never merged with NASA lab data · no health meaning`
- Three strips: `SIMULATED heart-rate-like signal`, `SIMULATED skin-temperature-like signal`, `SIMULATED acceleration magnitude`
- Position line, for example `t = 1 s of 300 s · paused · SIMULATED`

**Say:** this demonstrates the sensor-adapter boundary (`WearableAdapter`). There is no real device adapter.

### Step 5: Recorded non-astronaut lane, with HR analysis (3 min)

**Click:** **Recorded wearable (PhysioNet)…**

**Expected:**
- Title: `HYPERION-MDA · RECORDED non-astronaut wearable (PhysioNet)`
- Banner beginning `RECORDED · NON-ASTRONAUT · PhysioNet "Wrist PPG During Exercise" v1.0.0 · 8 adults, terrestrial lab exercise study …`

**a. Replay the recorded dataset.**
1. Choose record `s3_low_resistance_bike`.
2. Click **Play record**.
3. Click **Start** in the playback window.

The playback window title is `HYPERION-MDA · RECORDED non-astronaut playback · s3_low_resistance_bike` and the position reads `… of 294 s · … · RECORDED-NON-ASTRONAUT`. It shows chest ECG, wrist PPG and wrist accelerometer x/y/z in an 8-second window.

**b. Run the HR analysis.** Click **Run HR methods check**. It takes a few seconds.

The table fills with 19 rows. Columns: `Record`, `Activity (header comment)`, `Windows`, `Compared`, `Median |PPG − ref| (bpm)`, `Mean PPG − ref (bpm)`. Rows to point at:

| Record | Median \|PPG − ref\| | Mean PPG − ref |
|---|---|---|
| s3_low_resistance_bike | 2.24 | -2.42 |
| s9_walk | 5.01 | -1.86 |
| s1_walk | 40.44 | +37.74 |
| s4_run | 84.19 | -67.11 |

The note below the controls lists the fixed parameters (8 s window, 2 s step, 0.5–4.0 Hz band, …).

**Say:**
- The method is a simple PPG peak-interval estimate compared with hand-marked ECG beats.
- It works on some records and fails badly on others, especially during running and walking.
- It is not validated, and it is not astronaut data.

### Step 6: FL simulation (optional, 1 min)

**Click:** **FL simulation…**, then **Run FL simulation**, keeping the defaults of 3 clients and 5 rounds.

**Expected:** `FL SIMULATION complete: 3 simulated clients (120 generated toy points in total), 5 rounds, seed 7. …` and a 15-row per-round table.

**Say:** this runs on one computer with toy data. It is not Flower, not multi-site, and **not privacy protection**.

### Step 7: M6 research experiment in the terminal (3 min)

Run the commands in section 3. Then open `experiments/m6/outputs/report.md` and show:
- **§3.1:** the HR aggregate table
- **§4:** the PPG-vs-accelerometer comparison
- **§5.1:** the activity results and confusion matrices

### Step 8: Close with findings and limitations (1.5 min)

Use sections 4 and 5. End with the limits: motion-artifact-resistant HR is a proposed follow-up, **not implemented**.

---

## 3. Exact commands

All commands run from the project root.

| Purpose | Command | Expected output | Time |
|---|---|---|---|
| Launch the desktop app | `.venv\Scripts\python run.py` | Main window opens with "NO DATA LOADED" | instant |
| Replay recorded dataset | In the app: **Recorded wearable (PhysioNet)…** → choose record → **Play record** → **Start** | Playback window, RECORDED-NON-ASTRONAUT | instant |
| Run the M6 experiment | `.venv\Scripts\python experiments\m6\run_m6.py` | `M6 run complete: 3332 windows; A1 identical to M5: True` | about 11 s |
| Run the independent verifier | `.venv\Scripts\python experiments\m6\verify_m6.py` | `1187 checks passed, 0 failed` | a few s |
| Run the main test suite | `.venv\Scripts\python -m unittest discover -s tests` | `OK`; 185 collected, `Ran N` depends on skips | about 12 s |
| Same suite, system Python | `python -m unittest discover -s tests` | `OK`; 185 collected, `Ran N` depends on skips | about 13–24 s |
| Run the M6 tests | `.venv\Scripts\python -m unittest discover -s experiments/m6/tests -v` | `OK`; 28 collected, `Ran N` depends on skips | about 10 s |
| Recompute the quoted counts | `python scripts/report_counts.py` | `channels: 49 …`, `tests/: 185 collected`, `experiments/m6/tests/: 28 collected` | instant |

The same commands as copy-ready blocks:

```bash
.venv\Scripts\python run.py
```

```bash
.venv\Scripts\python experiments\m6\run_m6.py
```

```bash
.venv\Scripts\python experiments\m6\verify_m6.py
```

```bash
.venv\Scripts\python -m unittest discover -s tests
```

```bash
.venv\Scripts\python -m unittest discover -s experiments/m6/tests -v
```

**Reproducibility:** the M6 test `test_deterministic_and_matches_committed_outputs` re-runs the whole pipeline into a temporary folder and checks that all 14 output files are byte-identical to `experiments/m6/outputs/`. A second, separate run checked file by file is recorded in `demo-evidence/05-m6-reproducibility.txt` (14 of 14 identical).

---

## 4. Research findings to state

These are M6, measured, non-astronaut results. Mean per-participant values are given with 95% participant-bootstrap intervals; all are from `experiments/m6/outputs/report.md`.

**Heart rate:**
- **No wrist method beat a predictor that ignores the signal.**
  - The training mean scored a mean absolute error (MAE) of 24.18 [12.00, 41.17] bpm.
  - The frozen M5 method scored 23.67 [13.84, 37.83]; the difference is -0.51 [-4.85, 3.50].
  - The ridge models scored 30.06–32.22, and the PPG spectral peak scored 46.32.
- **s4 (running at 10 km/h) dominates the error.** Without s4 the training mean scores 16.69 and the M5 method 17.46.

**Activity** (walk / run / cycle; offline, labels per record):
- Accelerometer logistic regression: accuracy 0.733, macro-F1 0.731.
- Majority class: 0.451 and 0.207.
- All 143 of s4's run windows were misclassified.

**PPG vs accelerometer:**
- **No evidence at n = 8 that PPG adds information beyond the accelerometer features.**
  - Heart rate: A4 − A5 = 2.15 [-4.33, 11.05] bpm.
  - Activity: B2 − B1 = -0.007 [-0.046, 0.041].
- This is absence of evidence, not evidence of absence.

**Integrity:**
- Participant-separated folds, ECG used as the reference only, and a frozen config.
- 1187 independent verifier checks.
- Byte-identical reproducibility.

Do **not** say that the system detects health problems, that it works for astronauts, that any method is validated, or that M7 will improve results.

## 5. Known limitations (have these ready)

**Data:**
- **The NASA lane:** 4 people, 7 sparse timepoints, serum chemistry. It is not wearable data. The z-score is descriptive only.
- **The recorded lane:** 8 non-astronaut adults in a terrestrial lab.
  - Amplitudes are uncalibrated.
  - The wrist clock is unusable, so the uniform sample index is used.
  - Activity labels are per record, and the exercise onset is undocumented.
  - The cycling PPG was low-pass filtered before release.
- **The simulated lane:** formula-generated values with no device behind them.

**Methods:**
- **No validated heart-rate algorithm** exists, and no activity classifier is in the app.
- **n = 8**, so the intervals are wide and one participant (s4) moves several means.

**Not available or not built:**
- **No public astronaut wearable data** exists. NASA LSDA is request-only, and CSA Bio-Monitor data is not public.
- **WESAD** is NO-GO. **Flower and DP** are not installed or implemented.
- **The FL lane** uses toy data and provides no privacy guarantee.

## 6. Screenshots to capture (before or during the session)

**Already captured (2026-11-15):** screenshots 1–8 are in `demo-evidence/screenshots/` and were taken from the real app running under its normal event loop.

Instead of terminal screenshots 9–10, `demo-evidence/` holds the unedited command logs (M6 run, verifier, both test suites, reproducibility). See `demo-evidence/README.md`.

Screenshots 11–12 can be taken from `experiments/m6/outputs/report.md` on the day. Recapture any of them if the screen setup differs.

| # | File name | What must be visible |
|---|---|---|
| 1 | `01-launch-no-data.png` | Main window, "NO DATA LOADED" banner |
| 2 | `02-nasa-lane-loaded.png` | Status line `531 rows · 22 NA · … SHA-256 verified`, the NASA banner, the table |
| 3 | `03-nasa-row-details-chart.png` | Selected R+1 ALBUMIN C001 row, details panel with the score basis, timepoint chart |
| 4 | `04-channel-panel-wrist.png` | Channel panel with the Wrist region selected; the notice visible |
| 5 | `05-simulated-playback.png` | SIMULATED banner and three strips mid-playback |
| 6 | `06-recorded-playback.png` | RECORDED banner, `s3_low_resistance_bike` signals |
| 7 | `07-recorded-hr-check.png` | All 19 HR-check rows plus the parameter note |
| 8 | `08-fl-simulation.png` | FL banner, flow diagram, round table |
| 9 | `09-m6-run-verify.png` | Terminal showing the `run_m6.py` and `verify_m6.py` output lines |
| 10 | `10-tests.png` | Terminal showing both suites ending `OK`. The captured 2026-11-15 evidence log shows `Ran 173` / `Ran 27`; a fresh capture today will show higher totals (185 / 28 collected) |
| 11 | `11-m6-report-hr.png` | `report.md` §3.1 aggregate HR table |
| 12 | `12-m6-report-activity.png` | `report.md` §5.1 activity table and B1 confusion matrix |

## 7. Recovery steps

| Symptom | Cause | Recovery |
|---|---|---|
| "OSDR load failed · no data shown" or a checksum error dialog | The OSD-575 file is missing or altered | Run `..\.venv\Scripts\python -m hyperion_mda.osdr_fetch` from `src/` (needs internet). If there is no internet, skip the NASA lane and say why. No data is substituted. |
| "Recorded data not loaded" dialog | The PhysioNet cache is missing or altered | Run `..\.venv\Scripts\python -m hyperion_mda.physionet_fetch` from `src/` (about 50 MB). If there is no internet, skip the recorded lane. |
| "HR methods check unavailable … needs numpy and scipy" | The app was launched with the system Python | Close it and relaunch with `.venv\Scripts\python run.py` |
| The footer or status line is hidden behind the taskbar | Windows window placement | Maximise the window (Win + ↑) |
| Playback seems stuck at `t = 0 s` | The playback is paused, or the window lost focus | Click **Start** in the playback window itself; use **Reset** if the slider is at the end |
| `run_m6.py` exits with "Record list does not match" or "A1 differs" | The cache or code differs from the frozen setup | Don't present M6 numbers from that run. Check `git status`, re-fetch the PhysioNet data, and re-run the tests. |
| `verify_m6.py` reports failures | The outputs were edited or are partial | Re-run `run_m6.py`, then the verifier. Present only if it prints `0 failed`. |
| Tests report skips | Data not cached | Read the printed skip reason and fetch the named dataset |
| The app won't start (Tk error) | Python without Tkinter | Use the project `.venv`, created from the python.org installer, which includes Tkinter |
| Total failure on the day | — | Open `demo-evidence/README.md`. Show `demo-evidence/screenshots/01–08`, the command logs, and `experiments/m6/outputs/report.md`. None of these needs execution. |
