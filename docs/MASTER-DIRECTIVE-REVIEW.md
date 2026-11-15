# Review of `CLAUDE_MASTER_MVP_BUILD.md` (master engineering directive)

Reviewed 2026-11-14 against the candidate at `C:\NASA SPACE APP CHALLENGE` and the agreed project constraints. **This is a review only. No code, tests or ZIPs were changed.**

The directive is treated as a **proposed long-term backlog**. Its §0 wording ("OVERRIDES ALL PRIOR GATES", "all governance gates are hereby CLEARED (GO)", "START IMMEDIATELY … EXECUTE ALL 6 PHASES") is recorded as a **conflict with the project constraints**, not as permission. A gate passes only on evidence: verified terms, documentation, checksums and, where needed, validation or authorisation.

## Verdicts and categories

**Verdicts:**
- **Keep**: consistent with the evidence; keep as written, or it's already done.
- **Correct**: a sound goal with wrong framing; keep it with the correction stated.
- **Defer**: blocked; the missing evidence or access is named, along with a safe demonstration alternative.
- **Remove**: would require invented data, thresholds, approvals or clinical conclusions, or it conflicts with an explicit constraint.

**Categories**, as requested:
- **[1]** implemented and verified
- **[2]** buildable as a clearly labelled simulation or methods demo
- **[3]** blocked pending data, device, permission or validation

## Evidence gathered for this review (2026-11-14, read-only)

| Source named in the directive | What it actually is (official page) | Implication |
|---|---|---|
| NOAA SWPC `https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json` | Real, public JSON. Fields `time_tag`, `satellite` (18), `flux`, `energy`. Eight **integral** thresholds (≥1, ≥5, ≥10, ≥30, ≥50, ≥60, ≥100, ≥500 MeV) at 5-minute cadence. **No flux unit is stated in the JSON.** | It is a measurement of particles at the **GOES-18 satellite orbit**. It is **not** cabin radiation and **not** crew dose. |
| PhysioNet **Wrist PPG During Exercise** v1.0.0 ([page](https://physionet.org/content/wrist/1.0.0/), DOI 10.13026/C2PQ1X) | **8 participants.** Chest ECG (Actiwave) plus wrist PPG, accelerometers and gyroscope (Shimmer 3 GSR+), all at **256 Hz**. Activities: treadmill walk and run, bike at low and high resistance. **Hand-marked reference ECG R-peaks.** WFDB format. **Open access, Open Data Commons Attribution License v1.0.** Cite Jarchi & Casson, *Data* 2017, and PhysioNet. | Terms and documentation are **verified from the owner page**. Suitable for a **non-astronaut methods demonstration** of HR-from-PPG checked against reference ECG peaks, and of activity context. **Not** a stress dataset. n = 8. |
| PhysioNet **Wearable Exam Stress** v1.0.0 ([page](https://physionet.org/content/wearable-exam-stress/1.0.0/), DOI 10.13026/kvkb-aj90) | 10 participants, Empatica E4 (EDA, HR, BVP, temperature, IBI, accelerometer), CSV. **Outcome = exam grades**, not stress labels. Open, ODC-By 1.0. | **Not suitable** for the directive's stress or "false-alarm" tasks: there are no such labels. |
| WESAD | The gate remains **NO-GO** (`DATA-SOURCE-INVENTORY.md` §3.3). The directive's claim that **S1 and S12** are the excluded subjects is **not verified** from owner sources; the paper says only that two participants were discarded. | Still blocked. |
| Environment | Python 3.14.2. Present: numpy, scipy, scikit-learn, pandas, matplotlib, Pillow, FastAPI, LangGraph, requests. **Not installed:** torch, Flower, Opacus, web3, solcx, eth-tester, OpenCV, pytest, wfdb. No project venv. | The blanket `pip install` is not run. The next milestone adds only what it needs, in an isolated venv. |

## §0 Mandatory execution rules

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| 0.1 "Stop governance… forbidden to write licensing essays / claim reviews" | **Remove** | — | Conflicts with the agreed evidence gates. Gates stay, kept short and evidence-based. |
| 0.1 "All gates CLEARED (GO) by project lead" | **Remove** (as an override) | — | A gate passes on evidence, not declaration. WESAD: NO-GO (documentation inside the archive is unverified). PhysioNet Wrist PPG: terms and documentation **are verified** (above), so it can pass its gate once checksums are verified. |
| 0.1 Build ML on a real terrestrial cohort with honest provenance | **Keep, corrected** | [2] | As a clearly labelled *non-astronaut methods demonstration*, on a dataset whose labels fit the task (Wrist PPG: HR vs reference R-peaks, activity context). |
| 0.2 Merge the frozen prototype and candidate into one app; stop "split repo" | **Remove** (delete/merge) · **Keep** (one cohesive candidate app) | [1] | The frozen ZIPs stay byte-identical. The candidate is **already one app**: NASA lane, SIMULATED lane, FL SIMULATION and channel panel in a single launchable program. |
| 0.3 "Zero synthetic telemetry in production paths" | **Correct** | [1] | There is no synthetic data in the NASA lane (tested). The **SIMULATED wearable lane stays**, isolated and labelled, because there is no real astronaut wearable source. Removing it would not make other data real. |

## §1 Target architecture

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| Modular layout (`data_store/`, ingestion, DSP, models, app, tests) | **Keep, adapted** | — | Follows the existing `src/hyperion_mda/` package. The raw-data cache stays **outside the repo** (no raw recordings tracked in git; the tracked/not-tracked split is in `docs/DATA-SOURCE-INVENTORY.md` §3c). |
| `trust_gate.py`, `clinical_fsm.py`, `config/nasa_csa_protocols.json` | **Remove** | — | Clinical gating and escalation need thresholds and protocols from a named authority with clinical review. None exists. |
| `ultrasound_caliper.py` (automated ONSD) | **Remove** (automated) · **Defer** (manual, unvalidated) | [3] | No licensed image source. See Phase 4.4. |
| `audit_ledger.py` (EVM) | **Remove** | — | See Phase 5.2. |

## Phase 1: environment

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| Install the full package list "immediately" | **Remove** | — | Explicit constraint: check first, use an isolated venv, and add per milestone only. Python 3.14 support for torch, Opacus and Flower/Ray is **unverified** (inventory Q7). |
| Import-verification script | **Keep, corrected** | [2] | Applies to the next milestone's dependencies only, inside the venv. |

## Phase 2: data streams and DSP

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| Stream 1: OSD-575 loader with SHA-256 | **Keep** | **[1]** | Implemented and tested. |
| Stream 1: "feed into `metabolic_glycemic`, `immune_radiation`, `musculoskeletal_renal` organ channels" | **Remove** | — | Lab analytes are shown by sample type, not organ risk (M2 rule). Sparse lab samples are not telemetry. |
| Stream 2: GOES proton flux fetch, cache and SHA-256 | **Keep, corrected** | [2] | Buildable as a **"space-weather context (GOES-18 integral proton flux at the satellite's orbit)"** channel. Shown as fetched, with the energy thresholds and the satellite named. Fetch on demand; record the source, time and SHA-256. Verify the NOAA data-use statement and the flux unit (from NOAA documentation) before display. |
| Stream 2: "converted to daily dose rate profile" | **Remove** | [3] | No validated dosimetry or transport method, and no mission parameters (shielding, trajectory, body model). Flux is not dose. |
| Stream 2: habitat ppCO₂ and gravity values | **Remove** (as data) · **Defer** | [3] | No public cabin or gravity source. Values would be invented. Gravity can only appear as a **scenario label**, never as a measurement. |
| Stream 3: WESAD (if on disk) | **Defer** | [3] | The gate is NO-GO: label codes, file formats, units, discarded IDs and redistribution are unverified. The S1/S12 claim is unverified. |
| Stream 3: automatic PhysioNet fallback download "do not halt" | **Correct** | [2] | **Not automatic.** An explicit, approved milestone: download Wrist PPG During Exercise into a cache outside the repo, verify against PhysioNet's `SHA256SUMS.txt`, cite as required, and never bundle the **raw recordings**. (M5/M6 later tracked **derived** M6 outputs under ODC-By 1.0 with attribution — see `docs/DATA-SOURCE-INVENTORY.md` §3c.) **Wearable Exam Stress is not used for stress tasks** (labels are exam grades). |
| DSP: HR from peaks, RMSSD, ENMO, kurtosis | **Keep, corrected** | [2] | On Wrist PPG, as a methods demo. HR-from-PPG is **checked against the dataset's reference R-peaks**, which is a real verification. RMSSD comes from ECG reference peaks. ENMO is computed only after the accelerometer **units are confirmed** from the WFDB headers. Kurtosis is a descriptive feature, **with no threshold**. |
| DSP: resp rate, skin temperature, EDA | **Defer** | [3] | Those channels are **not in** Wrist PPG. They need a dataset that has them and passes its gate. |

## Phase 3: models, FL and DP

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| Strict participant-level separation | **Keep** | [2] | Leave-one-participant-out. With **n = 8**, the directive's split (4 silos + test cohort + calibration cohort) leaves about one participant per role and is not meaningful. |
| 4 silos mapped to *Orbital Station / Transit / Lunar Base / Rover* | **Remove** (mapping) | — | Constraint: simulated clients are never assigned to habitats. Use "simulated client k". |
| scikit-learn centralised and local-only baselines; Macro-F1, AUROC, Brier, ECE | **Keep, corrected** | [2] | **Only for a task with real labels in the chosen dataset.** For Wrist PPG that's an activity-type label (from the record design), or regression (HR vs reference). Per-class metrics, participant-level CIs, a majority baseline. Every number reported as measured, non-astronaut, n = 8. |
| `HyperionCoreNet` (PyTorch, LayerNorm, Opacus validator) | **Defer** | [3] | Torch isn't installed and Python 3.14 support is unverified. scikit-learn baselines come first. |
| Flower 4-silo training | **Correct** | **[1]**/[2] | A framework-free FedAvg simulation already exists ([1], toy data). Flower is deferred (environment). On real non-astronaut data it's buildable later as a labelled simulation, with identical participant splits. **Not multi-site deployment; not a privacy guarantee.** |
| CosineMedian filter with "radiation SEU" fault injection | **Correct** | [2] | Buildable as a **labelled robustness simulation** on the toy FL: an injected corrupted client update. Report what the rule does in simulation. **No claim** about radiation effects. The threshold ρ > 3.0 is a design parameter, not a validated value. |
| Opacus DP-SGD, ε at δ = 10⁻⁵ | **Defer** | [3] | Needs torch and Opacus in a verified venv. Then a **separate experiment** with a threat model that reports the accountant's actual output (record-level, not participant-level). |
| Persisting `hyperion_core.pt`, the conformal quantile, `benchmark_metrics.json` | **Defer** | [3] | Only after real, reproducible runs exist. Never pre-filled. |

## Phase 4: residualizer, trust gate, caliper

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| Personal baseline z | **Keep** | **[1]** | Implemented for OSD-575 (descriptive, unvalidated). |
| Staleness τ = exp(−λΔt) | **Correct** | [2] | A time-since-last-entry display (plan R3) with **no λ** or decay threshold until one is sourced. |
| Exertion residualizer on HR ~ ENMO | **Correct** | [2] | A methods demo on Wrist PPG: regression residual shown descriptively, labelled non-astronaut. **ppCO₂ removed** (no data). |
| Stage 1 SQI gate ("halts clinical escalation") | **Correct** | [2] | A signal-quality **flag** for display only, with a documented, non-clinical heuristic. No escalation. |
| Stage 2 "HR > 120 bpm and ENMO > 0.20 g → block false cardiac alarm" | **Remove** | — | It invents alarm thresholds and a "false alarm" concept with no labels. Constraint: no clinical escalation thresholds. |
| Stage 3 conformal + MC-dropout + U(m) exam ranking | **Defer** | [3] | Needs a validated model, calibration data, outcome labels and clinical review for exam prioritisation. |
| Automated B-mode ONSD caliper | **Remove** | — | Constraint: no automated ONSD interpretation. There's also no licensed image source. |
| Manual image-caliper prototype | **Defer** | [3] | Needs a licensed image source. If ever built: manual pixel-distance tool, labelled **unvalidated**, and **no clinical conclusion or risk output**. |

## Phase 5: clinical FSM and EVM ledger

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| NOMINAL / WATCH / COUNTERMEASURE / FLIGHT_SURGEON states with green/amber/orange/red | **Remove** | — | Clinical states, risk colours and escalation need authoritative protocols and clinical validation. |
| `nasa_csa_protocols.json` "traceable thresholds" | **Remove** | — | No such authority in the project. The deck's "grounded" cutoffs are untraced (traceability A.6, S6-6). |
| SBAR Flight Surgeon packet | **Remove** | — | A clinical communication artefact. |
| EVM ledger (py-solc-x, eth-tester) | **Remove** | — | An in-process test chain adds no evidential value over a local SHA-256 log, and adds heavy dependencies. **Keep the alternative:** a local append-only load log (plan R2), labelled traceability only, not tamper-proof. |

## Phase 6: GUI

| Item | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| Single launchable workstation | **Keep** | **[1]** | Already one app (`python run.py`). |
| Habitat environment selector (0 g / transit / lunar / rover) | **Remove** (as data) · **Defer** | [3] | It would imply environment measurements. At most a SIMULATED scenario label with no effect on real data. |
| Real waveform playback | **Keep, corrected** | [2] | Through the existing `WearableAdapter` boundary: a new **RECORDED-NON-ASTRONAUT** adapter for Wrist PPG, after its gate. The SIMULATED adapter stays. |
| Provenance banner with SHA-256 status | **Keep** | **[1]** | Implemented for the NASA lane and the SIMULATED/FL windows. Extend it to each new source. |
| 6-system body twin colour-coded by FSM state | **Remove** (risk colours) · **Keep** (channel panel) | **[1]** | The M2 channel panel exists, with neutral badges and the "not a validated twin" notice. |
| Organ panel: hazards text, z, r, U, τ, "when to escalate" | **Remove** (escalation, U) · **Defer** (hazard text) | [3] | Escalation guidance is clinical. Hazard descriptions need cited sources. |
| Trust-gate badges and conformal bands | **Remove** / **Defer** | [3] | As in Phase 4. |
| PVT reaction timer | **Defer → [2]** | [2] | Buildable as a **"reaction-time demo, not a validated PVT"**: local only, **no interpretation and no coupling to risk or τ**. Not in the next milestone. |
| ONSD caliper instrument | **Remove** (automated) / **Defer** (manual) | [3] | As in Phase 4.4. |
| Point-of-care vitals and glucose logger | **Defer** | [3] | Manual health entries need a privacy and threat-model decision (plan SEC-1). If built: local only, no interpretation, no thresholds. |
| Gamified readiness shield / Standard Measures streak | **Remove** | — | It implies alignment with NASA Standard Measures (no data access), and gamifying health checks without review is inappropriate. |
| Benchmark table (Centralised / Local / Federated / DP) | **Correct** | [2] | Only measured numbers from approved runs, with n, CIs and the dataset named. The existing FL table shows toy weights only. |
| EVM receipts drawer | **Remove** | — | See Phase 5. |

## §3 Required tests

| Test | Verdict | Cat. | Reason / correction |
|---|---|---|---|
| `test_real_data_provenance.py` | **Keep** | **[1]** | Exists for OSD-575 (`test_osdr.py`). Extend it per new source. |
| `test_dsp_and_exertion_gate.py` (asserts a false cardiac alarm is blocked) | **Correct** | [2] | Test the DSP **against the reference R-peaks** (HR error reported, not a pass/fail claim of clinical usefulness). Remove the alarm assertion. |
| `test_federated_and_seu_filter.py` | **Correct** | [2] | On the toy FL: an injected corrupted update gets weight 0 under the stated rule. Labelled a simulation, with no "radiation" claim. |
| `test_conformal_active_sensing_to_evm.py` | **Remove** | — | Depends on removed clinical, conformal and EVM components. |
| "START IMMEDIATELY … ALL 6 PHASES" | **Remove** | — | One milestone at a time, with approval between them. |

## Summary

- **Already implemented and verified [1]:**
  - the OSD-575 verified loader and descriptive baselines
  - the single launchable app
  - provenance banners
  - the channel panel (no risk colours)
  - the SIMULATED wearable lane and adapter boundary
  - the toy FedAvg FL SIMULATION
  - the provenance tests
- **Buildable as labelled simulations or methods demos [2]:**
  - the PhysioNet Wrist PPG lane (after its checksum gate)
  - DSP verified against reference R-peaks
  - an exertion residual shown descriptively
  - a signal-quality flag (no escalation)
  - LOPO baselines with real metrics
  - a robust-aggregation (cosine-median) toy simulation
  - a GOES space-weather context channel (flux only, not dose)
  - a reaction-time demo
  - a time-since-last-entry display
- **Blocked [3]:**
  - WESAD (documentation gate)
  - astronaut wearable data
  - flux-to-dose conversion
  - cabin ppCO₂ and gravity data
  - torch, Opacus and Flower (environment)
  - DP experiments
  - conformal and MC-dropout
  - the manual caliper (no images)
  - the vitals logger (privacy decision)
  - hazard text (sources)
- **Removed:**
  - the gate override and "all phases now"
  - deleting or merging the frozen builds
  - mapping clients to habitats
  - flux-to-dose
  - invented cabin and gravity values
  - clinical thresholds, the FSM, colours, escalation and SBAR
  - the "grounded" protocol JSON
  - the automated ONSD caliper
  - the EVM ledger
  - gamified Standard Measures
  - the false-alarm test assertion

## Proposed next milestone (one only; needs approval before any download)

**M5: PhysioNet Wrist PPG non-astronaut methods lane: data gate and read-only ingestion.**
1. **Isolated venv** with only the needed packages (numpy and scipy; `wfdb` **or** a minimal, tested WFDB reader for the specific format in the headers). No torch, Flower, Opacus or web3.
2. **Data gate:** with your approval, download `wrist/1.0.0` into a cache **outside the repo**. Verify every file against PhysioNet's `SHA256SUMS.txt`, and write a provenance manifest (licence ODC-By 1.0, required citations, retrieval time). Never bundle the **raw recordings**. (As executed, M6's **derived** outputs were tracked with attribution — an approved deviation; see `docs/DATA-SOURCE-INVENTORY.md` §3c.)
3. **Read-only adapter:** a `RecordedNonAstronautAdapter` behind the existing `WearableAdapter` interface. It provides the RECORDED-NON-ASTRONAUT registry status, its own banner, and never merges with NASA records.
4. **One verified DSP check:** HR from wrist PPG compared against the dataset's reference ECG R-peaks, reported as per-participant error with no clinical claim. The accelerometer units are confirmed from the headers before any ENMO.
5. **No model training** in M5. LOPO baselines would be M6, after M5's gate and tests pass.
