# HYPERION-MDA showcase rehearsal guide

Prepared 2026-11-15 for the live showcase.

**Sources:**
- [MENTOR-DEMO-GUIDE.md](MENTOR-DEMO-GUIDE.md)
- [IMPLEMENTATION-STATUS.md](IMPLEMENTATION-STATUS.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- The live acceptance log, [../demo-evidence/06-live-acceptance.txt](../demo-evidence/06-live-acceptance.txt)

**Pitch in one sentence:** *"HYPERION-MDA is a tested, local research prototype. It keeps four kinds of data in strictly separate lanes: real NASA astronaut lab data, simulated wearable signals, recorded non-astronaut wearable data, and a federated-learning simulation. Every claim it makes is backed by verified data or measured results."*

---

## 1. Live demonstration sequence (about 13 minutes)

**Before you start:**
- Open a terminal in `C:\NASA SPACE APP CHALLENGE`.
- Close notification pop-ups and hide the taskbar if you can.
- Keep `demo-evidence\README.md` open in a background window as the fallback.

| # | Time | Do this | You should see |
|---|---|---|---|
| 0 | 0:00–1:00 | Talk only (framing, see §2) | — |
| 1 | 1:00–1:30 | Run `.venv\Scripts\python run.py`, then maximise (Win + ↑) | Banner `RESEARCH PROTOTYPE · NO DATA LOADED · NOT FOR MEDICAL DECISIONS` |
| 2 | 1:30–4:30 | Click **Load NASA OSDR OSD-575 CMP (verified)**, then the first `R+1 · C001 · ALBUMIN` row | `NASA lab data · 531 rows · 22 NA · OSD-575 CMP · SHA-256 verified`. Details: `Descriptive z (unvalidated): -1.15`, the score basis "vs 3 earlier pre-flight baseline readings", and the timepoint chart L-92 … R+194 |
| 3 | 4:30–6:00 | **Channel panel…**, then click the **Wrist** region | `49 channels · all regions`, then `10 channels · Wrist` (4 Recorded · non-astronaut, 2 Simulated, 4 Unavailable), and the "NOT A VALIDATED PHYSIOLOGICAL DIGITAL TWIN" notice |
| 4 | 6:00–7:15 | Close the panel. **Simulated wearable…**, then **Start**; wait about 3 s; **Pause**; drag the slider; **Reset**. Close. | `t = … s of 300 s · playing · SIMULATED` advancing; banner "not measured, not from a device, not astronaut data … no health meaning" |
| 5a | 7:15–8:30 | **Recorded wearable (PhysioNet)…**, choose `s3_low_resistance_bike`, **Play record**, **Start**. Close the player afterwards. | `… of 294 s · playing · RECORDED-NON-ASTRONAUT`; chest ECG, wrist PPG, accelerometer x/y/z |
| 5b | 8:30–10:00 | In the recorded window, click **Run HR methods check** **once** and talk for 3 s while it runs | 19 rows. Point at: s3_low_resistance_bike 2.24 / −2.42; s9_walk 5.01 / −1.86; s1_walk 40.44 / +37.74; s4_run 84.19 / −67.11 |
| 6 | 10:00–11:00 | **FL simulation…**, then **Run FL simulation** with the defaults | `FL SIMULATION complete: 3 simulated clients (120 generated toy points in total), 5 rounds, seed 7` and 15 rows |
| 7 | 11:00–12:30 | In the terminal, run `.venv\Scripts\python experiments\m6\verify_m6.py`, then open `experiments\m6\outputs\report.md` at §3.1 and §5.1 | `1187 checks passed, 0 failed` |
| 8 | 12:30–13:30 | Close with findings and limitations (§2, step 8) | — |

**Tips:**
- **Step 5b freezes the window for about 3 seconds.** The HR check runs on the UI thread. It always finishes (19 rows in 3.1 s in the acceptance run). Don't click again and don't drag the window. Just keep talking.
- **Step 7:** run the verifier live; it's quick and harmless. Only run `run_m6.py` (about 11 s) if you have spare time. It rewrites the outputs, though they come out byte-identical.
- **If you're short on time:** skip step 6 (FL) and shorten step 7 to showing `report.md`.

---

## 2. What to say at each step

**0. Framing**
> "This is a research prototype, not a medical device. It makes no diagnosis, has no thresholds and has no NASA approval. There's one rule I'll keep coming back to: astronaut data, non-astronaut data and simulated data never mix. Each window tells you which lane it belongs to."

**1. Launch**
> "Nothing loads by itself, and there's no hidden sample data. The banner tells you the state before you do anything."

**2. NASA lane**
> "This is real NASA Open Science Data Repository data: OSD-575, the serum metabolic panel from the four Inspiration4 crew members. The file is downloaded once and its SHA-256 hash is checked against a pinned manifest every time it loads. If the file is missing or altered, you get an empty table, never substitute data."
>
> "Each post-flight value is compared only with the same person's own pre-flight values. This albumin reading is 1.15 standard deviations below that person's three pre-flight readings. The label says 'descriptive, unvalidated': there's no flag and no reference range. Lab reference ranges are deliberately not used. The 22 NA values stay visible and are never filled in."
>
> "These are sparse laboratory samples, seven timepoints, not wearable telemetry. The chart is spaced by timepoint, not to scale."

**3. Channel panel**
> "This is a channel registry, not a digital twin; the notice says so permanently. Every channel has exactly one status: measured lab sample, recorded non-astronaut, simulated, or unavailable. There are 49 channels: 19 measured, 5 recorded, 3 simulated and 22 unavailable. Unavailable channels show no values at all. We don't pretend to have data we don't have."

**4. Simulated lane**
> "These signals come from a fixed formula, and the banner says that in every way it can. The point of this lane is the software boundary: every sample passes through a `WearableAdapter` interface that rejects non-finite values, wrong units, unknown channels and time going backwards. A real device would plug in here. No real device adapter exists today."

**5a. Recorded lane**
> "This is real recorded data, but not astronaut data. It's PhysioNet's *Wrist PPG During Exercise*: eight adults in a terrestrial lab, open ODC-By licence. The raw recordings are cached locally and aren't in the repo; the derived experiment results are, which that licence allows with attribution. I wrote the WFDB file reader myself using only the standard library. It was cross-checked against the official `wfdb` package: all 19 records and all 11,388 beat annotations are identical."

**5b. HR check**
> "Now the honest part. This is a simple heart-rate estimate from the wrist PPG, compared with heart beats hand-marked on the chest ECG. Its parameters were fixed before we looked at results. On low-resistance cycling, the median error is about 2 bpm. On running it's 84 bpm. Motion destroys the wrist signal. We show that rather than hide it."

**6. FL**
> "This shows how federated averaging works: three simulated clients, five rounds, a fixed seed, generated toy data, all in one process on one computer. It is not multi-site, it is not Flower, and it gives no privacy guarantee. It explains the mechanism and nothing more."

**7. M6**
> "M6 is our offline research experiment on the same PhysioNet data, using leave-one-participant-out evaluation, so no person is ever in both training and testing. Everything was fixed in advance in a frozen config. An independent verifier recomputes every metric from the raw outputs: 1187 checks, zero failures. A rerun produces byte-identical files."

**8. Close**
> "There are three findings. First, no wrist heart-rate method beat a predictor that ignores the signal entirely: about 24 bpm mean error for both. Second, accelerometer-based activity classification works offline: 0.73 accuracy against 0.45 for always guessing the majority class. Third, with eight people, we found no evidence that PPG adds anything beyond the accelerometer. That is absence of evidence, not evidence of absence. Our next proposal, M7, targets motion-artifact-resistant heart rate. It is a proposal only, and we don't claim it will improve anything until it's measured."

---

## 3. Simple architecture

```text
            ┌──────── Desktop app (Python standard library + Tkinter, runs offline) ─────────┐
            │                                                                                 │
 NASA OSDR ─┼─► osdr_fetch ─► SHA-256 check ─► schema adapter ─► pre/post descriptive z ─► table + chart
 (explicit) │                                                                                 │
            │   sim_wearable (formula) ─► WearableAdapter boundary ─► playback window [SIMULATED]
            │                                                                                 │
 PhysioNet ─┼─► physionet_fetch ─► SHA-256 manifest ─► WFDB reader ─► WearableAdapter ─► playback
 (explicit) │                                                    └─► dsp_hr HR check (numpy/scipy, .venv)
            │                                                                                 │
            │   fl_sim (toy FedAvg, one process) ─► FL window [FL SIMULATION]                 │
            │                                                                                 │
            │   signal_registry (49 channels, one status each, holds no values) ─► channel panel
            └─────────────────────────────────────────────────────────────────────────────────┘

 experiments/m6/ (offline, NOT in the app): frozen config → data → features → LOPO models
                 → outputs (CSV/JSON/report) → independent verifier
```

The design points worth naming:
- **Network access:** only the two explicit fetch commands use the network. They send no health data.
- **Lane separation:** the lanes import nothing from one another, and tests check this. Wearable samples are a different data type from NASA records.
- **M6 isolation:** M6 reads the app's modules but never writes to them, and nothing in the app imports M6.
- **Tests:** 173 in the app suite plus 27 in M6 passed on 2026-11-15 (the captured evidence logs). The suites now collect **185** and **28**; recompute with `python scripts/report_counts.py` and quote your own run's output.

---

## 4. Implemented vs experimental vs proposed

| Category | What it covers |
|---|---|
| **Implemented in the app (verified live 2026-11-15)** | NASA OSD-575 lane: verified fetch, SHA-256 check on every load, schema adapter, mission-relative order, NA kept visible, descriptive z with no flag · Channel registry and panel (49 channels) · Simulated playback via the `WearableAdapter` boundary · PhysioNet recorded lane: verified fetch, stdlib WFDB reader, playback · M5 HR methods check · FL simulation (toy FedAvg) · User CSV import with an "unverified provenance" banner |
| **Experimental (offline, measured, not in the app)** | M6 LOPO baselines: HR (A0–A5) and activity (B0–B2), with participant bootstrap intervals, an independent verifier and byte-identical reproducibility |
| **Proposed only (not implemented)** | M7 motion-artifact-resistant HR (accelerometer-referenced spectral suppression plus tracking) · a WESAD methods demonstration (the WESAD data gate is **NO-GO**) · Flower FL, differential privacy · real device adapters |
| **Out of scope (never claim)** | Diagnosis, thresholds, risk scores, treatment, a digital twin, flight readiness, NASA/CSA integration or approval, clinical validation, privacy guarantees, activity classification in the app |

---

## 5. Ten likely questions

**1. Why not use astronaut wearable data?**
None is publicly available. NASA's LSDA (Life Sciences Data Archive) is request-only, and CSA Bio-Monitor data is not public. The only public astronaut data we use is OSD-575 serum chemistry, and we label it as sparse lab samples, not telemetry.

**2. What exactly is the z-score?**
It is the post-flight value minus the mean of the same person's pre-flight readings, divided by their standard deviation. It is labelled descriptive and unvalidated. There is no threshold or flag on NASA data, and lab reference ranges are not used. With only three baseline readings and a tiny standard deviation, a z-score can look large without meaning anything clinically.

**3. How do you know the data hasn't been tampered with or misread?**
- Every file is pinned by SHA-256 and checked on every load. A failed check means no data is shown, and nothing is substituted.
- The OSDR file must have an exact header and pass a `CMP` test-type check.
- The PhysioNet files are checked against the owner's `SHA256SUMS.txt` and each record's WFDB header checksums.
- Our reader was cross-checked against the official `wfdb` package with zero differences.

**4. How is lane separation enforced, not just labelled?**
- Wearable samples use a separate data type from NASA records.
- Tests check the import direction between lanes in both directions.
- Each window has its own banner and title.
- The NASA table and status stayed unchanged in the live acceptance test while the other lanes were running.

**5. What is LOPO and why use it?**
Leave-one-participant-out: train on 7 people, test on the 8th, and repeat 8 times. Windows from the same person are highly correlated, so mixing them across training and testing would inflate the scores. The standardisers are fitted on the training participants only, and the code asserts that no participant leaks across the split.

**6. Why does the HR estimate fail on running?**
Wrist motion corrupts the PPG signal.
- **Measured:** the heart-rate errors are largest on running and walking, and the spectral-peak method often locks onto roughly half or double the true rate (28.0% of running windows near 0.5×, 13.4% near 2×; this was a labelled post-hoc diagnostic).
- **Hypothesis, untested:** that s4 specifically fails because of their running cadence.

**7. Does the app classify activity?**
No. Activity classification exists only in the offline M6 experiment. There, accelerometer logistic regression scored 0.733 accuracy and 0.731 macro-F1, against 0.451 and 0.207 for majority class. Labels are per record, and all 143 of participant s4's running windows were misclassified.

**8. Why linear models and no deep learning?**
- With n = 8 participants, a baseline has to come first.
- The hyperparameters were fixed in advance, so nothing was tuned on the test data.
- We used numpy and scipy only, with no new dependencies.
- The baselines showed that the signal problem (motion) has to be solved before model complexity can help.

**9. Can someone reproduce your results?**
Yes.
- The M6 config is frozen and the bootstrap seed is fixed (20261115).
- Rerunning produces 14 of 14 output files byte-identical, and a test checks this automatically.
- An independent standard-library verifier recomputes the metrics: 1187 checks pass.

**10. What would you do next?**
M7: motion-artifact-resistant heart rate using accelerometer-referenced spectral suppression and rate tracking, evaluated with the same LOPO protocol against the same baselines. It is a proposal only. We make no claim that it will improve anything, and its literature basis still needs verification.

---

## 6. Five difficult questions

**1. Research limitations: "Eight people, and nothing beat the mean. Isn't this a negative result?"**
> "Yes, and we report it as one. The training-mean predictor scored 24.18 bpm MAE, and the M5 method 23.67. The difference is −0.51 with a 95% interval of [−4.85, 3.50], so there's no evidence either is better. With n = 8 the intervals are wide, and one participant, s4, moves several of the means: without s4, the mean predictor scores 16.69 and M5 scores 17.46. What this shows is that the problem is motion artifact, and that's exactly what M7 is designed to address."

**2. NASA data: "Four crew and sparse lab draws. What can you actually conclude?"**
> "Nothing clinical, and we don't try. OSD-575 has four people, seven timepoints, serum chemistry and no labels. We cannot train on it, and we don't. What we demonstrate is a correct pipeline on real NASA data: verified provenance, exact units, NA kept visible, and comparison only against the same person's pre-flight values. We never combine it with the wearable lanes."

**3. PPG accuracy: "84 bpm error on running. Why show something that bad?"**
> "Because it's the measured result, and the parameters were fixed before we saw it. Hiding the failures would make the good records, like 2.24 bpm on low-resistance cycling, meaningless. One more caveat: the cycling PPG was low-pass filtered before the dataset was released, so cycling is easier than it looks. No heart-rate algorithm here is validated."

**4. Federated learning: "Is this privacy-preserving?"**
> "No. It's federated averaging on generated toy data in one process. There's no network, no Flower, no secure aggregation and no differential privacy. And federated learning alone isn't a privacy guarantee anyway, because model updates can leak information. A real privacy claim would need a stated threat model and an accountant's output from a differential-privacy experiment, and we haven't built that."

**5. Medical safety: "Could a flight surgeon use this?"**
> "No. It's not a medical device and makes no diagnosis or recommendation. It has no thresholds, no clinical validation, no standards compliance, no flight qualification and no NASA approval. We even disabled the illustrative |z| flag for NASA data so nothing on screen could be read as an alert. Every banner says 'NOT FOR MEDICAL DECISIONS'."

---

## 7. Recovery if something fails live

| Symptom | What to do on the spot |
|---|---|
| The window seems frozen after **Run HR methods check** | Expected; it takes about 3 s. Wait. Don't click again. |
| A "needs numpy and scipy" dialog | It was launched with the system Python. Close it and run `.venv\Scripts\python run.py`. |
| Playback stuck at `t = 0 s` | Click **Start** in the playback window itself; use **Reset** if the slider is at the end. |
| "OSDR load failed" or a checksum dialog | Say: "This is the integrity check working: altered or missing data gives an empty table, never a substitute." Then skip the lane, or show screenshots 02–03. |
| "Recorded data not loaded" | Skip the lane and show screenshots 06–07. Re-fetching needs internet and about 50 MB, so don't do it live. |
| Status line hidden behind the taskbar | Win + ↑ to maximise. |
| The verifier reports failures | Don't present M6 numbers live. Show `demo-evidence/02-m6-verify.txt` and `report.md` instead. |
| `download FAILED: boom` appears in test output | Expected; those are failure-injection tests. |
| The app won't start at all | Open `demo-evidence/README.md`, show screenshots 01–08 in order, then `06-live-acceptance.txt` (the full live run, all 8 workflows PASS) and `report.md`. Say: "Here is the evidence captured from the real app." |

**Golden rule under pressure:** if a lane fails, say why and skip it. Never use one lane's data to stand in for another.

---

**Document notes:**
- **IMPLEMENTATION-STATUS.md**, the M2 row: previously said "41 channels" and "no SIMULATED or RECORDED channels". **Corrected** — it now states 49 channels (19 measured, 5 recorded, 3 simulated, 22 unavailable), computed from `signal_registry.CHANNELS` by `python scripts/report_counts.py`, matching the live panel.
- **DEMO-RUNBOOK.md** is superseded by the mentor guide. It already carries a note saying so, and its stale "102 tests" line is now annotated with the current counts.
