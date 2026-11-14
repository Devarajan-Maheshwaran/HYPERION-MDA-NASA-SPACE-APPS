# HYPERION-MDA demo runbook (OSD-575 real-data candidate)

How to present the **candidate** build. Everything below describes behaviour in the current code, checked on 2026-11-14 (Windows 11, Python 3.14.2, 125% display scaling).

> **What this is:** a tested local software prototype that downloads one **real, public** NASA OSDR file (OSD-575 serum Comprehensive Metabolic Panel), verifies it by SHA-256, imports it with a schema check, and shows each person's post-flight values **descriptively** against their own pre-flight values.
> **What this is not:** a medical device, a diagnosis or risk tool, wearable telemetry, or a representative astronaut dataset. There is **no** clinical validation, **no** NASA approval or standards compliance, and **no** flight readiness. The data is **sparse serum lab data from the 4 Inspiration4 crew**: a 3-day private mission, with 7 timepoints.

This runbook is not matched to any presentation deck; none is in the project. The earlier synthetic-data demo is preserved, with its own runbook, inside `dist/HYPERION-MDA-Prototype.zip`.

---

## 1. Before you start (do this before the session, with internet)

1. Use Python 3.10+ with Tkinter. No other packages are needed.
2. In the project folder, run the tests:
   ```bash
   python -m unittest discover -s tests
   ```
   Until step 3 is done, the real-file tests **skip** with the reason "Real OSDR file not downloaded".
3. Download and verify the OSDR file:
   ```bash
   cd src
   python -m hyperion_mda.osdr_fetch
   ```
   Expected output: `Verified LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv (25275 bytes, SHA-256 dab247eb…a0c) -> …\.hyperion_mda\osdr\OSD-575\…`.
   **If it prints `OSDR download FAILED`, stop.** Don't present real-data results. The app will not substitute other data.
4. Rerun the tests. Expect `Ran 102 tests … OK`, with nothing skipped.
5. Once the file is cached, the demo itself needs no internet.

## 2. Live walkthrough

### Step 1: Launch
```bash
python run.py
```
- The window opens with the banner **"RESEARCH PROTOTYPE · NO DATA LOADED · NOT FOR MEDICAL DECISIONS"**.
- **Maximise the window** (□ button or Win + ↑). On some laptops, Windows places the window low enough that the footer sits behind the taskbar; maximising fixes this.

### Step 2: Load the verified OSDR data
Click **Load NASA OSDR OSD-575 CMP (verified)**.
- **Status (top right):** `531 rows · 22 NA · OSD-575 CMP · SHA-256 verified`.
- **Banner:** "REAL PUBLIC DATA · NASA OSDR OSD-575 · sparse serum metabolic panel (CMP) from the 4 Inspiration4 crew · not wearable telemetry · NOT FOR MEDICAL DECISIONS".
- **The details panel shows the import summary:**
  - the study title
  - the retrieval date and verified SHA-256
  - 531 rows · 4 subjects · 19 analytes · timepoints L-92 … R+194
  - **22 missing values (NA)**, with their line numbers
  - the one absent row (C002 BUN/CREATININE RATIO R+82)
  - 287 post-flight values with a descriptive comparison
- **Say:** "This is the real file from NASA's Open Science Data Repository, checked byte-for-byte against the hash we recorded. Missing values are shown and listed, not filled in."

### Step 3: Show one comparison (C001, creatinine, R+1)
In the table, select **row 74**: `R+1 · observation · C001 · CREATININE · 1.12 · mg/dL`. Rows are sorted by subject, then analyte, then timepoint.

The details panel shows:
```
C001 · CREATININE · R+1 (post-flight observation)
Value: 1.12 mg/dL
Descriptive z (unvalidated): -0.86
Score basis: vs 3 earlier pre-flight baseline readings (mean 1.23667, SD 0.135); descriptive comparison only, unvalidated
Warnings: none
Source: line 61 of LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv
```
**Explain:**
- The baseline is **only this person's pre-flight values** for this analyte and unit: L-92 = 1.24, L-44 = 1.10, L-3 = 1.37 mg/dL. That gives mean 1.237 and SD 0.135, so z = (1.12 − 1.237) / 0.135 ≈ −0.86.
- **"3 baseline readings"** is shown because 3 points is very little data. The number is a description, not a judgement.
- There is **no flag or threshold.** The lab's own reference ranges are in the file but are deliberately not used.
- **"Source: line 61"** lets anyone check the value against the raw CSV.

### Step 4: Explain the chart
- **Title:** `CREATININE (mg/dL) · subject C001`.
- **Markers:** 3 blue circles (pre-flight baselines) and 4 orange diamonds (post-flight observations). The selected point has a black ring.
- **The x-axis is the mission timepoint labels**, L-92, L-44, L-3, then a dashed **"flight"** marker, then R+1, R+45, R+82, R+194. The axis note says *"not to scale"*. **No calendar dates were invented**, because days before launch and days after return don't share a reference point.
- **No lines, bands or thresholds** are drawn.

### Step 5: Show the honesty features (optional)
- **A missing value:** select **row 40**, `R+45 · C001 · BILIRUBIN; TOTAL · NA`. The details read *"No score: value missing in source (NA); not imputed"*, with *"Source: line 93"*. The chart keeps an **empty R+45 slot**, and a red note says *"Not plotted (NA or no valid time; still in table): lines 93"*.
- **Too few baselines:** select **row 49**, `R+194 · C001 · BUN/CREATININE RATIO · 22`. Two of the three pre-flight values are NA, so the details read *"No score: 1 eligible pre-flight baseline reading(s) recorded before this observation; need 2"*.
- **Verification failure (only if you have time):** temporarily point the app at an empty folder, or alter a copy of the file. "Load NASA OSDR…" then shows **"OSDR data not loaded"** with *"No other data was substituted"*, and the table stays empty.

## 3. What to say

> "HYPERION-MDA now runs end to end on real public data. It downloads one file from NASA's Open Science Data Repository, OSD-575, the serum metabolic panel from the four-person Inspiration4 mission. It verifies the file by SHA-256, imports it with a strict schema check, keeps every unit and every missing value exactly as published, and compares each person's post-flight values with their own pre-flight values. The comparison is descriptive and unvalidated: it uses no thresholds or reference ranges and gives no alerts or diagnoses. This is sparse lab data from four people, not wearable telemetry, and not representative of astronauts generally. There is no clinical validation and no NASA approval."

## 4. Likely judge questions

| Question | Answer |
|---|---|
| Is this real astronaut data? | Yes. It's real public data from NASA OSDR study OSD-575: serum lab panels from the 4 private Inspiration4 crew, verified by SHA-256. It is **not** wearable telemetry, it's only 4 people, and it's not representative of astronauts in general. |
| Why not heart-rate or wearable data? | We found no openly downloadable astronaut wearable time series. OSD-570/571/575 are blood assays, and WESAD is a terrestrial lab dataset. |
| Is the z-score clinically meaningful? | No. It's a descriptive comparison with only 2–3 pre-flight points, labelled unvalidated. There are no thresholds, alerts or diagnoses. |
| Why not flag values outside the lab's reference ranges? | Those are the performing lab's ranges. Using them as alerts would be clinical interpretation, which needs qualified review. They're deliberately unused. |
| Why is there an R+194 when OSDR's description lists R+1/45/82? | The file contains R+194 rows. We show the data as given and document the discrepancy. |
| How do you know the data wasn't altered? | The SHA-256 and size are recorded in a provenance manifest and re-checked every time the file loads. A mismatched file is refused (this is tested). |
| Can you redistribute the file? | The OSD-575 record states no licence, so we don't bundle it. Users download it from OSDR themselves. |
| Is anything synthetic? | Only small test fixtures inside `tests/`. The app has no synthetic fallback. |
| What about federated learning, blockchain, ultrasound, clinical workflows? | **Not implemented.** No suitable data, authority or justification exists in this project. |
| NASA approval? Flight ready? | No and no. NASA material is cited as a data source only. |

## 5. If something goes wrong

| Symptom | What to do |
|---|---|
| "OSDR data not loaded … was not found" | The file isn't cached. Run `python -m hyperion_mda.osdr_fetch` from `src/` (needs internet). |
| "… does not match the provenance manifest" | The cached file is altered or corrupted. Delete it and fetch again. If OSDR itself has changed the file, the fetch will refuse it; don't present results from it. |
| `OSDR download FAILED` | Network problem, or the OSDR listing changed. Present the honesty features using the failure dialog instead; don't substitute other data. |
| Footer hidden | Maximise the window. |
| `ModuleNotFoundError: tkinter` | Use a Python build that includes Tkinter. |
