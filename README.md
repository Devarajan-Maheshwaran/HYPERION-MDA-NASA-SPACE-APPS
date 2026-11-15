# HYPERION-MDA — OSD-575 real-data candidate

A local desktop prototype that loads **real, public NASA OSDR data** (study OSD-575), verifies the file against a recorded SHA-256, imports it with a schema check, and shows a **descriptive** comparison of each person's post-flight serum values against their own pre-flight values.

This is a tested software prototype. It is **not** a medical device or diagnostic system. It has **no** clinical validation, NASA approval, standards compliance or flight readiness, and it makes no claims about model performance.

**Presenting the demo?** Follow [docs/DEMO-RUNBOOK.md](docs/DEMO-RUNBOOK.md). Data source details are in [docs/OSDR-OSD575-DATA.md](docs/OSDR-OSD575-DATA.md).

> This is a **candidate** build. Earlier write-ups referenced a frozen synthetic-data demo at `dist/HYPERION-MDA-Prototype.zip`. **That archive is not in this repository** (`dist/` is git-ignored) and no builder for it is included, so nothing here depends on it. Run the current build from source as described below.

## What the data is, and is not

- **Source:** NASA Open Science Data Repository, **OSD-575**: *SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays*. The file used is the serum **Comprehensive Metabolic Panel (CMP)**, `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`.
- **Scope:** 4 people (the private Inspiration4 crew, a 3-day low-Earth-orbit mission in September 2021). 19 analytes at 7 sparse timepoints: pre-flight L-92, L-44, L-3; post-flight R+1, R+45, R+82, R+194.
- **It is not:** continuous wearable telemetry, ISS or long-duration data, or a representative astronaut population.
- **Licence:** none is stated in the OSD-575 record, so redistribution rights are not confirmed. The CSV is therefore **not bundled**, and no derived OSD-575 measurements are tracked in git either — only the provenance manifest (URL, size, SHA-256). You download it from OSDR yourself, and the app verifies it. The one place this repository *does* track derived data is the M6 experiment, built from the openly licensed (ODC-By 1.0) PhysioNet recordings; see [docs/DATA-SOURCE-INVENTORY.md](docs/DATA-SOURCE-INVENTORY.md) §3c for the exact tracked/not-tracked split.

## Run it

Requires Python 3.10+ with Tkinter. Uses the standard library only; there are no third-party packages.

**1. Download and verify the OSDR file (needs internet, once):**

```bash
python -m hyperion_mda.osdr_fetch
```

Run this from `src/`, or after installing the package. It reads the official OSDR file listing, downloads the one public file, and checks its name, size, restriction flag and SHA-256 against `src/hyperion_mda/data/osdr/OSD-575.provenance.json`. The file is saved to `~/.hyperion_mda/osdr/OSD-575/` (set `HYPERION_MDA_DATA_DIR` to change the location). If any check fails, nothing is saved and the command exits with an error. **No other data is substituted.**

**2. Launch the app:**

```bash
python run.py
```

Then click **Load NASA OSDR OSD-575 CMP (verified)**. The app re-checks the SHA-256 every time it loads the file. If the file is missing or altered, it shows an error and loads nothing.

**Installed package:** `python -m venv .venv`, then `.venv\Scripts\python -m pip install .`, then `.venv\Scripts\python -m hyperion_mda.osdr_fetch`, then `.venv\Scripts\hyperion-mda`. On macOS/Linux use `.venv/bin/`.

## What the app does with the OSDR file

1. **Verify:** checks the file size and SHA-256 against the provenance manifest.
2. **Import with a schema check:** the header must be exactly `ANALYTE,VALUE,RANGE_MIN,RANGE_MAX,UNITS,TEST_TYPE,SUBJECT_ID,SEX,timepoint`.
   - Analyte names and units are kept **exactly** as written, with no conversion.
   - Each row keeps its source line number.
   - `NA` values stay visible as `NA`, are listed in the import summary, and are never imputed.
   - The one subject/analyte/timepoint row missing from the file is reported.
   - **Not used:** `SEX` (a demographic) and `RANGE_MIN`/`RANGE_MAX` (the laboratory's reference ranges, which are never used as thresholds).
3. **Order by mission timepoint:** `L-n` (days before launch) comes before `R+n` (days after return). **No calendar dates are created.** The chart spaces timepoints evenly and marks the flight between them; it is not to scale.
4. **Compare:** every pre-flight (`L-`) value is a baseline, and every post-flight (`R+`) value is an observation. Each observation is compared with the same person's pre-flight values for the same analyte and unit. The details panel shows how many baseline values were used. With fewer than 2 numeric baselines, or zero spread, no comparison is shown and the reason is given.
5. **Display:** the z-score is labelled **descriptive and unvalidated**. There is **no flag, threshold, risk alert, diagnosis or recommendation** for this dataset; the illustrative `|z| ≥ 2.5` demo flag is disabled.

## Channel panel (M2)

**Channel panel…** opens a body/channel view built from the signal registry. Every channel shows exactly one status: *Measured · lab sample* (the 19 OSD-575 analytes, which are sparse blood draws, not continuous sensing), *Unavailable* (WESAD until its terms and data are verified; Bio-Monitor, BP, sleep, PVT, ONSD and cabin telemetry, which have no public source), *Recorded · non-astronaut* (the 5 PhysioNet playback channels, added in M5) and *Simulated* (the 3 demo-playback channels). It is **not a validated physiological digital twin**. It shows no scores, risk levels, cutoffs or diagnoses, and it is not connected to any NASA or CSA system.

## Demo lanes (three separate pipelines, each with its own label)

| Label in the UI | Window / button | What it is | What it is not |
|---|---|---|---|
| **NASA lab data** | Main window → **Load NASA OSDR OSD-575 CMP (verified)** | Real, SHA-256-verified OSD-575 serum CMP: 4 Inspiration4 crew, 7 sparse timepoints. The banner reads *"sparse laboratory measurements — not wearable telemetry"*. | Not wearable data; never used for training. |
| **SIMULATED** | **Simulated wearable…** | A deterministic playback (fixed formulas, no randomness) of three demo signals, with **Start / Pause / Reset** and a time slider. It runs through the documented sensor-adapter boundary (`adapters.py`: the `WearableAdapter` interface and `SimulatedPlaybackAdapter`). Malformed samples (non-finite value, unknown channel, wrong unit, non-increasing time, wrong provenance) are rejected with a readable error. | **Not measured, not from a device, not astronaut data.** Never merged into the NASA records. **No real device adapter exists.** |
| **RECORDED non-astronaut** | **Recorded wearable (PhysioNet)…** | PhysioNet *Wrist PPG During Exercise* v1.0.0: 8 adults, terrestrial lab exercise (walk, run, cycling), chest ECG and wrist PPG/accelerometer at 256 Hz. **Every file is SHA-256-verified** against the owner's checksums, and **every signal is checked against its WFDB header checksum.** *Play record* replays it through the same adapter boundary. *Run HR methods check* compares a simple PPG heart-rate estimate with the dataset's hand-marked reference ECG beats. The parameters were fixed beforehand, and the results are shown exactly as measured. | **Not astronaut data**, not a stress dataset, not a device connection. Amplitudes are as declared in the header and not calibrated. The HR check is **not validated** and has no clinical meaning (n = 8). |
| **FL SIMULATION** | **FL simulation…** | A framework-free FedAvg on generated toy 2-D data: 2–8 simulated clients, 1–30 rounds, fixed seed 7. It shows the client sizes, the per-round local update sizes, the global weights, and a client → server flow diagram. The server step receives only (weights, n). | **One computer.** Not habitats, sites or devices; not Flower (not installed); **no privacy protection** (no differential privacy, and FedAvg alone is not privacy); no accuracy or performance claims; no clinical meaning. |

The **Channel panel…** lists all 49 channels, each with exactly one status: 19 *Measured · lab sample*, 5 *Recorded · non-astronaut*, 3 *Simulated*, and 22 *Unavailable*, including the WESAD channels (that gate is NO-GO) and the Bio-Monitor, BP, sleep, PVT, ONSD and cabin channels. Its "not a validated physiological digital twin" notice is always visible.

### Recorded non-astronaut lane: setup (once, needs internet)

```bash
python -m venv .venv
.venv\Scripts\python -m pip install numpy scipy
cd src
..\.venv\Scripts\python -m hyperion_mda.physionet_fetch
```

This downloads the 59 files (about 50 MB) into `~/.hyperion_mda/physionet/wrist-1.0.0/` (or under `HYPERION_MDA_DATA_DIR`). Every file is checked against the owner-provided `SHA256SUMS.txt`, whose own hash is pinned in `src/hyperion_mda/data/physionet/wrist-1.0.0.provenance.json`. Nothing is bundled or redistributed.

- **Licence:** Open Data Commons Attribution v1.0.
- **Cite:** Jarchi & Casson, *Data* 2017, doi:10.3390/data2010001, and PhysioNet (doi:10.13026/C2PQ1X).
- **Dependencies:** the core app needs only the standard library. Only the HR methods check needs numpy and scipy; run it with `.venv\Scripts\python run.py`.

### Demo steps
1. `python run.py`, then **Load NASA OSDR OSD-575 CMP (verified)**. The status reads *"NASA lab data · 531 rows · 22 NA · … SHA-256 verified"*. Select a post-flight row to see its descriptive comparison and the mission-timepoint chart.
2. **Simulated wearable…**: press **Start**, **Pause**, drag the time slider, then **Reset**. Every title and the banner say SIMULATED.
3. **FL simulation…**: choose clients and rounds, then **Run FL simulation**. Read the flow diagram and the per-round table.
4. **Recorded wearable (PhysioNet)…**: pick a record and click **Play record** (8-second window, RECORDED-NON-ASTRONAUT). Then click **Run HR methods check** to see per-record PPG-vs-reference differences, with the parameters and caveats shown.
5. **Channel panel…**: click **Wrist** to see the *Recorded*, *Simulated* and *Unavailable* (WESAD) channels side by side.

## M6 research experiment (offline; not shown in the app)

`experiments/m6/` holds a leave-one-participant-out (LOPO) evaluation of simple baselines on the PhysioNet Wrist PPG data. It covers **8 adults doing terrestrial lab exercise**; these are not astronaut data and no validated algorithm comes out of it.
- **Setup:** the frozen config and fixed hyperparameters are in `experiments/m6/m6-lopo-config.json`. Only numpy and scipy are used.
- **Design rules:** the ECG is used as the reference only. Folds are separated by participant, and standardisation is fitted on the training participants.

**Measured results:**

| Measure | Result |
|---|---|
| Heart rate, mean absolute error | **No method beat a predictor that ignores the signal:** 24.18 bpm for it, against 23.67 for the frozen M5 method and 30.06–32.22 for the ridge models |
| Activity (walk / run / cycle), accelerometer logistic regression | 0.733 accuracy and 0.731 macro-F1, against 0.451 and 0.207 for the majority class |
| Does PPG add information beyond the accelerometer? | No evidence at n = 8, for either task |

Details: [docs/M6-RESULTS-SUMMARY.md](docs/M6-RESULTS-SUMMARY.md), [docs/M6-TECHNICAL-REVIEW.md](docs/M6-TECHNICAL-REVIEW.md), and the generated `experiments/m6/outputs/report.md`. The next step, M7, is a **proposal only**: [docs/M7-PROPOSAL.md](docs/M7-PROPOSAL.md).

```bash
.venv\Scripts\python experiments\m6\run_m6.py
```

```bash
.venv\Scripts\python experiments\m6\verify_m6.py
```

## Your own CSV files

**Open CSV…** loads a CSV in the original demo format, described in [docs/CSV-SCHEMA.md](docs/CSV-SCHEMA.md). Those files get the "provenance not verified" banner and the original demo rules, including the illustrative flag. The synthetic example CSV now lives only in `tests/fixtures/`; the app never loads it on its own.

## Tests

```bash
python -m unittest discover -s tests -v
```

The M6 experiment has 28 further tests, which need the `.venv` and the PhysioNet cache (run from the repository root with `src` importable, for example `PYTHONPATH=src` on Linux/macOS):

```bash
.venv\Scripts\python -m unittest discover -s experiments/m6/tests -v
```

The main suite has 185 tests. Both counts, and the channel counts quoted below, are computed from the code — regenerate them with:

```bash
python scripts/report_counts.py
```

Collected tests are not the same as executed tests: without Tkinter or a dataset cache, whole test classes skip and `unittest` reports a lower "Ran N" figure. Quote the command output when reporting a run.

The main suite covers:
- **Engine, chart and packaging tests**, using synthetic fixtures that are kept inside the tests.
- **OSDR tests:** checksum mismatch, schema validation, the fetch logic (using local `file://` URLs, so no network is needed), mission-relative ordering, unit preservation, `NA` handling and pre-flight-only baselines.
- **An end-to-end check on the real verified file**, through to the UI data model, which compares every z-score with an independent calculation from the raw CSV. These real-file tests **skip with a stated reason** if you haven't run the fetch command.

All of these are software checks only. They do not validate anything clinically.

## Not implemented

A validated heart-rate algorithm (the M6 baselines did not beat a no-signal predictor), federated learning beyond the toy simulation, differential privacy, a blockchain or ledger, clinical state machines or protocols, ultrasound or ONSD analysis, PVT or other instruments, sensor or wearable integration, live streaming, and any NASA/CSA system integration. See [docs/IMPLEMENTATION-STATUS.md](docs/IMPLEMENTATION-STATUS.md) and [docs/REQUIREMENTS-TRACEABILITY.md](docs/REQUIREMENTS-TRACEABILITY.md).

Acknowledgment suggested by OSDR: *Data are courtesy of the NASA Open Science Data Repository.* For the dataset citation, use the "Citation" panel on the OSDR study page. Related publication: Overbey et al., *Collection of Biospecimens from the Inspiration4 Mission Establishes the Standards for the Space Omics and Medical Atlas (SOMA)*, doi:10.1038/s41467-024-48806-z.
