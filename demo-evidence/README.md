# Demo evidence and fallback pack (captured 2026-11-15, 14:58)

Use this folder if the live demonstration can't run. Every file here was produced by actually running the project on the development machine: Windows 11, Python 3.14.2, project `.venv`, display 1920×1080.

- **Screenshots:** captured while the real app ran under its normal event loop, driven through each workflow in `docs/MENTOR-DEMO-GUIDE.md`. No error dialog appeared in any workflow.
- **Text logs:** the unedited console output of each command.

## Screenshots (`screenshots/`)

| File | Shows | Lane |
|---|---|---|
| `01-launch-no-data.png` | Main window at launch: `RESEARCH PROTOTYPE · NO DATA LOADED · NOT FOR MEDICAL DECISIONS` | — |
| `02-nasa-lane-loaded.png` | `NASA lab data · 531 rows · 22 NA · OSD-575 CMP · SHA-256 verified` | NASA lab data (real astronaut serum lab values) |
| `03-nasa-row-details-chart.png` | R+1 · C001 · ALBUMIN selected, with the descriptive z (−1.15, unvalidated), score basis and mission-timepoint chart | NASA lab data |
| `04-channel-panel-wrist.png` | Channel panel filtered to Wrist (10 channels): 4 Recorded · non-astronaut, 2 Simulated, 4 Unavailable (WESAD) | Registry, no values |
| `05-simulated-playback.png` | SIMULATED playback running (t = 14 s of 300 s); banner says "not astronaut data · no health meaning" | SIMULATED |
| `06-recorded-playback.png` | Recorded `s3_low_resistance_bike` playing (chest ECG, wrist PPG, accelerometer x/y/z) | RECORDED-NON-ASTRONAUT |
| `07-recorded-hr-check.png` | HR methods check: all 19 records plus the fixed parameters | RECORDED-NON-ASTRONAUT |
| `08-fl-simulation.png` | FL SIMULATION: 3 clients, 5 rounds, seed 7, toy data | FL SIMULATION |

## Command logs

| File | Command | Result |
|---|---|---|
| `01-m6-run.txt` | `.venv\Scripts\python experiments\m6\run_m6.py` | `M6 run complete: 3332 windows; A1 identical to M5: True` |
| `02-m6-verify.txt` | `.venv\Scripts\python experiments\m6\verify_m6.py` | `1187 checks passed, 0 failed` |
| `03-tests-173.txt` | `.venv\Scripts\python -m unittest discover -s tests -v` | `Ran 173 tests … OK` |
| `04-tests-m6-27.txt` | `.venv\Scripts\python -m unittest discover -s experiments/m6/tests -v` | `Ran 27 tests … OK` |
| `05-m6-reproducibility.txt` | A second, independent M6 run compared file by file (SHA-256) | 14 of 14 output files identical |
| `06-live-acceptance.txt` | `.venv\Scripts\python demo-evidence\live_acceptance_script.py`: final release-freeze run of all 8 workflows in one continuous session under the real Tk mainloop, including workflow switching with 4 windows open at once | All 8 workflows PASS; 0 Tk callback exceptions; 0 dialogs |

The lines `OSDR download FAILED: boom` and `PhysioNet download FAILED: boom` in `03-tests-173.txt` are **expected**. They come from tests that inject a download failure on purpose.

## Research fallback

- `experiments/m6/outputs/report.md`, the full generated M6 report:
  - §3.1 heart-rate table
  - §4 PPG vs accelerometer
  - §5.1 activity classification (offline only; not in the app)
- `docs/M6-RESULTS-SUMMARY.md` and `docs/M6-TECHNICAL-REVIEW.md`

**What this evidence does not show:**
- Activity classification in the app: it does not exist there.
- Any astronaut wearable data: none is public.
- Any health assessment.

The simulated signals are not astronaut data. The recorded data comes from 8 non-astronaut adults.
