# M7 proposal: motion-artifact-resistant heart-rate estimation (PhysioNet Wrist PPG)

**Status: PROPOSAL ONLY.**
- Nothing is implemented, trained or run, and no M7 result exists.
- Drafted 2026-11-15. Implementation needs explicit approval of a frozen M7 config (stage 0, §9).

**Scope:** RECORDED-NON-ASTRONAUT methods demonstration on the same verified dataset as M5/M6 (8 adults, terrestrial lab exercise). It makes no astronaut, clinical, device or validation claim, and it would not be shown in the desktop app.

## 1. Motivation (measured in M6)

M6 values are mean per-participant MAE in bpm [95% participant bootstrap]; source: `experiments/m6/outputs/report.md`.

- **No wrist method beat a predictor that ignores the signal.**
  - A0 (training mean): 24.18 [12.00, 41.17]
  - A1 (frozen M5 peak method): 23.67 [13.84, 37.83]; A1 − A0 = −0.51 [−4.85, 3.50]
- **The plain PPG spectral peak (A2) was worse than no signal:** A2 − A0 = 22.14 [4.17, 41.84].
  - During running, only 14.2% of its windows were within ±10% of the reference.
  - 28.0% were near half the reference, and 13.4% near double.
  - This is a post-hoc descriptive diagnostic.
- **Interpretation (a hypothesis, not a result):** the PPG spectrum's dominant peak often tracks motion rather than the pulse.
- **Gap this points to:** M6 tested no method that *uses the accelerometer to remove motion from the PPG*. M6's ridge models only placed accelerometer features alongside the PPG features.

## 2. Research questions and pre-registered hypotheses

**Primary question.** Under M6's exact LOPO design, does a pre-declared motion-artifact-resistant method (M7-ST, §3) achieve lower per-participant MAE than the no-signal baseline A0?

**Hypotheses.** Each uses M6's pre-declared reading rule: a paired participant-bootstrap 95% interval entirely below 0 counts as evidence; an interval containing 0 means "no evidence either way at n = 8".

| ID | Hypothesis | Comparison | Status |
|---|---|---|---|
| H1 (primary) | M7-ST has lower MAE than A0 | M7-ST − A0 | Confirmatory; the single primary test |
| H2 | M7-ST has lower MAE than the frozen M5 method | M7-ST − A1 | Secondary |
| H3 | Accelerometer-referenced suppression reduces the spectral-peak error | M7-S − A2 | Secondary |
| H4 | Temporal tracking reduces gross errors | Fraction of windows outside ±10%, M7-ST vs M7-S | Descriptive |

**Multiplicity.** Only H1 is confirmatory. H2 to H4 are reported as secondary and descriptive, with no correction-free "significance" language.

**Power caveat (stated in advance).**
- M6's A1 − A0 interval was about 8 bpm wide. At n = 8, only differences of several bpm are likely to be resolved.
- An inconclusive result is a legitimate outcome and will be reported as such.

## 3. Candidate methods

All candidate methods are untrained signal processing with fixed parameters. There are no learned models.

| ID | Method | Inputs | Idea |
|---|---|---|---|
| M7-S | **Accelerometer-referenced spectral suppression** | PPG + accel | Attenuate PPG spectral bins within ±Δ Hz of the top-*k* accelerometer peaks (each axis and the magnitude) and their 2nd harmonics, then take the remaining in-band maximum |
| M7-N | **Adaptive noise cancellation (NLMS)** | PPG + accel | An NLMS filter of length *L* and step *μ*, with the three accelerometer axes as noise references; the spectral peak of the residual |
| M7-T | **Temporal tracking** | PPG | Choose among the top spectral candidates per window by dynamic programming (Viterbi) within a record, penalising heart-rate jumps between consecutive windows |
| **M7-ST** (primary) | M7-S followed by M7-T | PPG + accel | Suppression, then tracking |
| M7-ST-causal | M7-ST with forward-only tracking | PPG + accel | Shows what is achievable without future windows; reported alongside |

**Parameters** (Δ, *k*, *L*, *μ*, number of candidates, transition penalty, maximum heart-rate step):
- They will be set at stage 0 from the method definitions and conventional defaults, with each value's rationale written down. They are **not** chosen by inspecting M6 per-record results.
- No parameter is tuned on this dataset. If tuning ever becomes necessary, it requires a new approval and **nested LOPO** inside the training participants.
- **Literature basis:** these method families appear in the published wrist-PPG literature. For example, the TROIKA framework (Zhang, Pi & Liu, *IEEE Trans. Biomed. Eng.* 2015) combines signal decomposition, sparse spectrum reconstruction and spectral peak tracking. **No citation has been verified in this project yet.** Each must be checked against the original paper at stage 0 before it is cited in any M7 document, and no published result is assumed to transfer to this dataset.

**Explicitly excluded from M7:**
- learned or deep models (CNNs, LSTMs)
- any learned correction stage
- extra dependencies

A learned stage would be a separate milestone with its own approval.

## 4. Experimental design (identical to M6 unless stated)

- **Data and windows:** the same 19 verified records and the same 3332 windows (8 s, 2 s step).
- **Reference:** 60 / median RR of the hand-marked ECG beats; at least 3 beats per window.
- **Inputs:** wrist PPG and the low-noise accelerometer only. ECG is never an input.
- **Folds and aggregation:** the same 8 participant folds.
  - Untrained methods need no fitting. Folds still define the per-participant aggregation, the paired comparison with A0, and the A0 values, which are reused byte-for-byte from M6 `hr_predictions_primary.csv`.
- **Uncertainty:** the same bootstrap (seed 20261115, 10,000 resamples, paired indices).
- **Sensitivity analyses:** the same S2 (RR screen) and S3 (without s4). S1 stays omitted unless a documented onset is found.
- **Breakdowns:** per activity and per record, reported as secondary. The released cycling PPG was low-pass filtered (15 Hz) and walk/run PPG is raw, so per-activity comparisons are confounded with release preprocessing.
- **Comparators:** A0, A1 and A2 from M6, unchanged and not re-tuned.

## 5. Leakage and integrity controls

- **ECG:** reuse the M6 data layer unchanged. `RecordInputs` has no ECG field, the ECG-noise invariance test is repeated, and the reference loader never reads signals.
- **Temporal tracking:** operates within one record only and uses no reference information. The non-causal variant uses future windows of the same record, is labelled offline, and is reported next to the causal variant.
- **Freezing:** the config is frozen and hashed before any run. Every post-hoc analysis is labelled post hoc and cannot change a method.
- **Researcher degrees of freedom:** M6 results have already been seen. That is why only one primary method and hypothesis is declared, and why parameters come from method definitions rather than this data.

## 6. Validation plan

**Synthetic tests**, in fixtures only:
- a sinusoidal "pulse" plus a stronger sinusoidal "motion" component at a known different frequency, present in both the PPG and the accelerometer
- M7-S and M7-N must recover the pulse frequency where A2 picks the motion frequency
- the tracker must follow a slowly changing synthetic rate and reject an isolated wrong-frequency window

**Other checks:**
- **Real-data checks:** same windows as M6; the M6 A0, A1 and A2 values are reproduced exactly.
- **Independent verifier:** extend the `verify_m6.py` pattern, recomputing every reported metric from the raw prediction CSVs with the standard library only.
- **Reproducibility:** a full run is byte-identical across two runs.
- **Regression:** all 173 `tests/` and 27 M6 tests stay passing, and M6 outputs stay byte-identical.

## 7. Expected outputs

These are artifacts, not results.
- `experiments/m7/m7-config.json` (frozen)
- `experiments/m7/outputs/`: per-window predictions, per-participant and per-record tables, aggregates with intervals, paired comparisons, gross-error fractions, `results.json`, and a generated `report.md`
- `docs/M7-RESULTS-SUMMARY.md` after verification

**No expected values are stated. The outcome is unknown.**

## 8. Risks and limitations

| Risk | Consequence | Mitigation |
|---|---|---|
| n = 8 | Low power; H1 may be inconclusive even with a real effect | Pre-stated; report the per-participant results first |
| Default parameters unsuited to this device | Methods may underperform | Report as measured. Any tuning is a new, approved, nested-LOPO milestone. |
| Tracker locks onto a wrong track | Errors persist across whole records | Causal and non-causal variants; per-record error tables; the H4 gross-error fraction |
| Accelerometer and pulse frequencies coincide (cadence ≈ HR) | Suppression removes the pulse | Report the fraction of windows where they overlap within Δ; descriptive |
| Release preprocessing differs by activity | Per-activity effects are confounded | Stated; not interpreted as physiology |
| Non-astronaut, terrestrial population | No transfer to spaceflight | Lane separation; banners; no app integration |
| Single dataset | No external replication | Optional M7b, below |

**Optional M7b (external replication)** needs its own approval and gate. Candidate public wrist-PPG exercise datasets exist, for example the IEEE Signal Processing Cup 2015 data and PPG-DaLiA. Neither has been gated in this project: their terms, documentation and file formats are unverified. Each would need the same terms-and-documentation gate that PhysioNet passed and WESAD failed. Nothing would be downloaded before that.

## 9. Stages (each needs approval)

| Stage | Work | Stop for approval |
|---|---|---|
| 0 | Verify the cited method sources; fix and hash `m7-config.json` (parameters with rationale) | **Yes** |
| 1 | Implement M7-S, M7-N, M7-T and M7-ST in `experiments/m7/`; synthetic tests | No |
| 2 | Real-data run; verifier; reproducibility; regression | **Yes**: results reviewed as measured |
| 3 | `docs/M7-RESULTS-SUMMARY.md`; update the status docs | **Yes**: before any commit |

**Files (all new, none modified):**
- `experiments/m7/m7_methods.py`, `experiments/m7/run_m7.py`, `experiments/m7/verify_m7.py`
- `experiments/m7/m7-config.json`
- `experiments/m7/tests/test_m7.py`

M7 would import the M6 data and feature layer read-only.

## 10. Out of scope

- Diagnosis, clinical thresholds or alerts.
- Any astronaut or spaceflight claim.
- Desktop UI integration.
- Learned or deep models.
- WESAD (gate NO-GO).
- Any change to the frozen M5 method, to M6 code or outputs, or to the three ZIP packages.
