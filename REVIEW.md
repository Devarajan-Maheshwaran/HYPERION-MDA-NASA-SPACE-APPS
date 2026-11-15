# HYPERION-MDA repository review

> **Historical snapshot.** This review predates the live web workstation and the later R1–R6 fixes. Use `README.md`, `docs/WORKSTATION-RUNBOOK.md` and `docs/IMPLEMENTATION-STATUS.md` for the current build. R3 below is retained as a finding and marked resolved.

**Reviewed commit:** `0c06fbf9d813db6f15a4fa968efc55154c99312c`  
**Branch:** `arena/da7479f7-hyperion-mda-nasa-space-apps` (branched from `150b1f84b173e601b90b2cf7c5fea88c69bb1b64`)  
**Review date:** 2026-11-14 UTC (session date). Several repository artifacts carry 2026-11-15 timestamps; those are repository-reported dates, not independently verified event times.

## Scope and evidence rules

This is a read-only review of the tracked application, experiment, tests, configuration, documentation and evidence pack. The only intended repository addition is this `REVIEW.md`; no application or experiment code was changed. Before this file was written, `git status --short --ignored` was empty. Temporary environments, caches, probe outputs and installer artifacts were kept outside the repository or removed.

Evidence is distinguished as follows:

- **Observed here:** a command or probe executed in this review environment.
- **Code-inspected:** behavior established from the current source and synthetic tests.
- **Repository-reported:** a result or external-source fact recorded in the repository, but not independently reproduced here.
- **Not verified / proposed:** no sufficient execution or external evidence in this review.

The environment was Linux with Python 3.11.2, initially without Tkinter, NumPy, SciPy or pytest. A temporary virtual environment outside the repository supplied NumPy 2.4.6 and SciPy 1.17.1. Docker was unavailable. NASA OSDR and PhysioNet requests failed at the sandbox network boundary; PyPI was reachable. The historical evidence pack instead reports Windows 11, Python 3.14.2, NumPy 2.5.4 and SciPy 1.18.1 (`demo-evidence/README.md:1–6`; `experiments/m6/outputs/results.json:24–28`).

## Executive verdict

**This is a substantially implemented local research/data-visualization prototype, not the full clinical system described in the original concept.** Its strongest work is explicit data provenance, lane separation, conservative labeling, participant-separated M6 evaluation, and unusually candid reporting of negative results. It is not a medical device, not clinically validated, not flight-ready, and not a deployed web service.

The main conclusions are:

1. **One confirmed data-integrity defect:** a NASA-row with the wrong `TEST_TYPE` is flagged but can still enter a personal baseline. This should be fixed before relying on the schema-validation claim. It is a conditional input-validation bug, not evidence that the currently pinned OSD-575 file contains such rows.
2. **The local core and M6 arithmetic checks run here, with important skips.** The main suite reports `OK (skipped=30)`; M6 reports `OK (skipped=8)`; the committed-output verifier reports `1187 checks passed, 0 failed`.
3. **The GUI and real-data end-to-end paths were not reproduced here.** Tkinter is absent and both dataset downloads fail with TLS EOF. Historical screenshots and an eight-workflow acceptance log exist, but are not a substitute for a portable rerun.
4. **M6 is credible as a small offline methods experiment, not as a validated heart-rate or astronaut-health model.** No HR method demonstrated improvement over the no-signal baseline. Activity classification improved over majority prediction on this terrestrial dataset, with substantial participant-specific failures.
5. **There is no HTTP backend, browser frontend, container deployment, CI workflow, production audit log, differential privacy, Flower integration, clinical FSM or agency/device integration.** These are scope gaps, not bugs in the explicitly local prototype.
6. **Documentation is mostly careful but needs reconciliation:** stale channel/test counts, an absent referenced ZIP, a then-non-portable acceptance script (R3, now resolved), and inconsistent wording about redistribution of derived PhysioNet outputs.

No Critical finding was established. That is not a safety approval.

## Priority findings

| ID | Priority | Classification | Finding and evidence | Recommended action |
|---|---|---|---|---|
| R1 | High | Confirmed defect | Wrong-`TEST_TYPE` rows are flagged at `src/hyperion_mda/osdr_cmp.py:172–174`, but baseline eligibility does not check that rejection condition (`src/hyperion_mda/engine.py:301–304`). A synthetic CBC baseline was used in a CMP z-score. | Add an explicit eligibility/rejection reason; exclude wrong-type baselines and observations; add regression tests for both roles. |
| R2 | Medium | Reproducibility gap | Core packaging declares no dependencies (`pyproject.toml:5–13`), while HR/M6 require manually installed, unpinned NumPy/SciPy (`README.md:68–81`). No lockfile or CI matrix is tracked. Provenance hashes raw checkout bytes, making the manifest hash line-ending-sensitive. | Declare an optional numeric extra with tested bounds, lock the experiment environment, document the OS-level Tk requirement, and define canonical provenance hashing. |
| R3 | Medium | Evidence portability — **resolved** | The reviewed harness hardcoded a Windows source path. The current `demo-evidence/live_acceptance_script.py` derives `REPO_ROOT` from `__file__` and exits 2 with setup hints when Tk/display/caches are missing. The GUI still could not run in this Linux environment. | Rerun on a Tk-capable machine with both verified caches. |
| R4 | Medium | Data-governance inconsistency | Derived per-participant/window features and predictions are tracked under `experiments/m6/outputs/` (`experiments/m6/run_m6.py:302–315`), while several docs say the project does not redistribute PhysioNet data. The output location was an approved deviation (`docs/M6-LOPO-PROTOCOL.md:15–25`). | Explicitly distinguish raw recordings from derived open-data artifacts; confirm attribution/license handling and update the blanket wording. This is not an established astronaut-data leak. |
| R5 | Medium | UI responsiveness | The HR check runs synchronously on the Tk callback thread (`src/hyperion_mda/recorded_view.py:86–105`). The historical acceptance log measured a 3.02 s event-loop gap (`demo-evidence/06-live-acceptance.txt:48–50`). | Move computation to a worker with cancellation/progress and marshal UI updates back to Tk. Keep this labeled as a methods check, not monitoring. |
| R6 | Low | Documentation drift | Status still says 41 channels in one row; actual registry has 49. M6 now has 28 tests, not 27. Several guides reference an absent `dist/HYPERION-MDA-Prototype.zip`. | Generate counts from source or update them together; remove/qualify unavailable archive references; mark historical sections clearly. |

---

# A. Architecture and technology stack

## A.1 What actually exists

| Component | Current implementation | Evidence |
|---|---|---|
| Desktop entry points | `run.py`, `python -m hyperion_mda`, and installed `hyperion-mda` console script | `pyproject.toml:12–19`; launch probes in H |
| Core UI | Python standard library + Tkinter; table, static chart, details panel and separate windows | `src/hyperion_mda/app.py`; `chart_view.py`; `playback_view.py`; `recorded_view.py`; `fl_view.py`; `twin_view.py` |
| Generic CSV path | Schema/value/time/quality checks, exact signal-unit allow-list, duplicate detection, explicit earlier baselines, descriptive z-score | `src/hyperion_mda/engine.py:156–229,232–337`; `docs/CSV-SCHEMA.md:5–53` |
| NASA lane | Explicit OSDR fetch, pinned size/SHA-256 verification, strict CMP schema adapter, mission-relative ordering, descriptive pre/post comparison | `src/hyperion_mda/osdr_fetch.py`; `osdr_source.py:67–80`; `osdr_cmp.py:131–223` |
| Simulated lane | Three deterministic formula-generated channels through `WearableAdapter` and playback controls | `src/hyperion_mda/sim_wearable.py:26–43`; `adapters.py:93–145` |
| Recorded lane | Explicit PhysioNet fetch, pinned checksums, stdlib WFDB reader, adapter boundary, playback and optional NumPy/SciPy HR check | `src/hyperion_mda/physionet_fetch.py`; `physionet_source.py`; `wfdb_reader.py`; `physionet_adapter.py`; `dsp_hr.py` |
| FL demonstration | In-process FedAvg on generated 2-D toy points; 2–8 clients, 1–30 rounds, fixed seed 7 | `src/hyperion_mda/fl_sim.py:66–140`; `README.md:64` |
| Channel registry | Value-free registry with one status per channel; observed counts: 19 lab, 5 recorded, 3 simulated, 22 unavailable | `src/hyperion_mda/signal_registry.py:167–210`; registry probe in H |
| M6 experiment | Offline config → verified data → label-free features → LOPO linear models → CSV/JSON/report → independent arithmetic verifier | `experiments/m6/run_m6.py`; `m6_data.py`; `m6_features.py`; `m6_models.py`; `m6_report.py`; `verify_m6.py` |

The current architecture is accurately summarized as:

```text
Tk desktop
├── user CSV ───────────────► validation ─► descriptive baseline comparison
├── OSDR fetch ─► SHA-256 ─► CMP adapter ─► mission-relative comparison
├── formula generator ─────► WearableAdapter ─► SIMULATED playback
├── PhysioNet fetch ─► SHA-256/WFDB checks ─► RECORDED playback / HR check
├── toy FedAvg ────────────► FL SIMULATION window
└── value-free registry ───► channel/status panel

experiments/m6 (offline; not imported by the app)
└── frozen config ─► verified inputs/reference ─► features ─► LOPO ─► outputs ► verifier
```

The app is not a streaming telemetry bus. Playback is a local replay over an adapter, not a device connection. The channel panel is explicitly not a validated physiological digital twin (`src/hyperion_mda/twin_view.py:175–204`; `README.md:53–66`).

## A.2 Stack and dependency assessment

- `pyproject.toml:9–10` declares Python ≥3.10 and an empty dependency list. That is consistent with the **core** stdlib/Tk app, but not a complete specification for the optional HR/M6 environment.
- Tkinter is an interpreter/OS capability, not something the empty dependency list installs. Its absence here prevented every GUI launch; this is an environment limitation, not proof of a Tk code defect.
- NumPy/SciPy are imported for the HR check and M6, but installation is a manual README step rather than a declared extra (`README.md:70–81`; `src/hyperion_mda/recorded_view.py:86–93`).
- No tracked `requirements*.txt`, lockfile, `package.json`, Dockerfile, compose file, `.env` template or CI workflow was found. `pyproject.toml` is the only build/runtime manifest.
- The project uses `unittest`, not pytest. No coverage percentage was measured in this review.

**Assessment:** suitable for a controlled local demonstration; not yet a reproducible cross-machine research package or a production service.

# B. Safety, thresholds and clinical logic

## B.1 Implemented safeguards

The code does several important things correctly:

- Keeps units exact and refuses unsupported signal-unit pairs rather than guessing conversions (`src/hyperion_mda/engine.py:293–314`; `docs/CSV-SCHEMA.md:19–28`).
- Keeps missing values visible and does not impute them (`src/hyperion_mda/osdr_cmp.py:159–171`; `engine.py:309–310`).
- Requires at least two eligible earlier baselines and nonzero sample spread before computing z (`src/hyperion_mda/engine.py:322–331`).
- Excludes duplicate groups from scoring rather than selecting a purportedly correct row (`src/hyperion_mda/engine.py:267–290,315–317`).
- Disables the illustrative absolute-z flag for NASA data (`src/hyperion_mda/osdr_cmp.py:63–70`).
- Does not use OSD-575 `SEX` or laboratory reference ranges as clinical interpretation (`docs/OSDR-OSD575-DATA.md:44–63`).
- Labels the NASA comparison descriptive and unvalidated, with no diagnosis, alert or recommendation (`README.md:40–51`).

These are software/data-handling safeguards, not clinical validation.

## B.2 Confirmed defect: flagged wrong-type row remains baseline-eligible

`osdr_cmp._to_record()` adds a flag and report entry when `TEST_TYPE != "CMP"` (`src/hyperion_mda/osdr_cmp.py:172–174`). However, `_baseline_usable()` checks role, value, quality policy, grouping key, time, supported pair and duplicate status—not that flag or a dedicated validity field (`src/hyperion_mda/engine.py:301–304`). The existing wrong-type test checks only that a flag/report entry exists (`tests/test_osdr.py:174–177`).

A fresh synthetic-only reproduction in this review produced:

```text
wrong_test_type_lines [2]
L-92 flags= ("TEST_TYPE is 'CBC', expected 'CMP'",) z= None note= Baseline reading (eligible for later observations)
R+1 flags= () z= 9.0 note= vs 3 earlier pre-flight baseline readings (mean 82, SD 2); descriptive comparison only, unvalidated
```

The input had baselines 80 (wrong type), 82 and 84, then observation 100. The wrong-type value contributed to the mean and SD. The same eligibility path also does not reject a wrong-type observation merely because of that flag.

**Impact:** a malformed or mixed-assay input can produce a descriptive score despite the schema warning. The repository-reported pinned OSD-575 file has `TEST_TYPE` always `CMP` (`docs/OSDR-OSD575-DATA.md:30–35`), so this is not a demonstrated corruption of the current real-data results. It nevertheless undermines the stated validation boundary.

**Acceptance test for the fix:** wrong-type baselines must not contribute to any later score; wrong-type observations must remain visible with an explicit no-score reason; valid rows must be unchanged; test both roles and the import summary. Prefer an explicit validity/rejection reason over treating every display flag as a blanket rejection.

## B.3 Threshold and action inventory

| Item | Where it appears | Implemented? | Review conclusion |
|---|---|---:|---|
| `DEMO_FLAG_ABS_Z = 2.5` | `src/hyperion_mda/engine.py:48`; `docs/CSV-SCHEMA.md:51` | Yes, generic CSV display only | Arbitrary illustrative setting; disabled for NASA data; not a clinical cutoff. |
| Minimum two baselines | `src/hyperion_mda/engine.py:36,324–327` | Yes | Statistical/software eligibility rule, not clinical validation. |
| M6 RR screen 0.25–1.5 s | `experiments/m6/m6-lopo-config.json:92`; `docs/M6-LOPO-PROTOCOL.md:160–162` | Yes, sensitivity analysis | Annotation-quality screen, not a patient threshold. |
| ENMO > 0.22 g | `docs/HYPERION-MDA-CONCEPT-AS-PROVIDED.txt:262–267` | No | Concept-only exertion gate; no residualizer or ENMO implementation. |
| Staleness τ < 0.5 / ≥ 0.8 | Concept text `:268–329` | No | No staleness resolver or clinical state transitions. |
| ONSD ≥ 5.8 mm; PVT > 350 ms | Concept text `:345–362`; `docs/REQUIREMENTS-TRACEABILITY.md:360–363` | No | No ultrasound/PVT instrument or validated interpretation. |
| Glucose and BP bands | `docs/REQUIREMENTS-TRACEABILITY.md:108–113` | No | Explicitly unverified attribution; no action mapping. |
| ε = 2.5, δ = 10⁻⁴ | Concept text `:389–403` | No | Design parameters, not an accountant result or privacy guarantee. |
| ENMO 0.31, HR 115/125 action rule, 38 °C rule, kurtosis gate, radiation shelter trigger | Targeted source/concept searches | No | No implemented rule found. HR >125 appears in proposed/unverified traceability text, not runtime logic. |

The concept's F1, false-alarm, coverage and Byzantine-resilience benchmarks are also unsupported as product results (`docs/HYPERION-MDA-CONCEPT-AS-PROVIDED.txt:414–437`; `docs/REQUIREMENTS-TRACEABILITY.md:354–358`). The retained validation reference explicitly forbids recycling those reported numbers as measured outcomes (`reference-material/02-Architecture-and-Validation.md`, claims table).

**Safety verdict:** no clinical FSM, triage, diagnosis, treatment recommendation, countermeasure trigger, conformal safety gate, exertion alarm suppression or flight-surgeon workflow exists. The correct claim is a non-clinical research prototype.

# C. Data sources, provenance and licensing

## C.1 Source inventory

| Source/lane | What the repository establishes | What was verified here | Important limits |
|---|---|---|---|
| NASA OSD-575 CMP | Real public Inspiration4 serum lab data; 4 people, 19 analytes, 7 timepoints; repository-reported 531 rows/22 NA; pinned size/SHA-256 | Verification/import code and synthetic tests inspected/run; real fetch failed | Sparse lab samples, not wearable telemetry; no stated study license; CSV not bundled (`docs/OSDR-OSD575-DATA.md:9–35,65–70`). |
| PhysioNet Wrist PPG v1.0.0 | Repository-reported 8 non-astronaut adults, 19 records, 59 files, 256 Hz, 11,388 reference beats; ODC-By 1.0 | Manifest/code inspected; committed M6 outputs verified; real fetch failed | Terrestrial exercise; clock anomalies and uncalibrated amplitudes; no clinical/stress labels (`docs/DATA-SOURCE-INVENTORY.md:98–108`). |
| WESAD | Gate is NO-GO; documentation/terms questions remain | No WESAD data or training path found | Not downloaded, not used, channels unavailable (`docs/DATA-SOURCE-INVENTORY.md:81–96,132–139`). |
| Simulated wearable | Fixed formulas, e.g. HR-like `70 + 5 sin(...) + ...`, scripted movement at 120–165 s | Formula and headless adapter logic inspected/run | Not measured, not a physiological simulation validated against crew data (`src/hyperion_mda/sim_wearable.py:33–43`). |
| FL toy data | Seeded generated 2-D points and in-process FedAvg | Headless run completed | Not real clients, habitats, agencies or privacy protection (`src/hyperion_mda/fl_sim.py:66–140`). |
| OSD-570/571, CIPHER, Bio-Monitor, radiation/cabin feeds | Discussed as sources/context or unavailable | No live integration or usable telemetry pipeline found | OSD-570/571 are not wearable telemetry; access/authorization cannot be inferred from names (`docs/IMPLEMENTATION-STATUS.md:48–56`; `docs/RESEARCH-BIBLIOGRAPHY.md:13–17`). |

External owner pages, licenses and dataset metadata were **not independently re-fetched** because the sandbox blocked those hosts. The repository's recorded license/provenance statements are useful evidence, but this review does not certify current upstream terms or legal compliance.

## C.2 Integrity mechanisms

- OSDR: size and SHA-256 checked against the pinned manifest before load (`src/hyperion_mda/osdr_source.py:67–80`).
- PhysioNet: the owner-provided `SHA256SUMS.txt` is itself pinned; individual files are checked; WFDB signal header checksums are also checked (`src/hyperion_mda/physionet_fetch.py:42–61`; `physionet_source.py:59–77`; `wfdb_reader.py:110–115`).
- Missing/altered inputs raise errors rather than silently substituting another lane. Synthetic failure-injection tests exercise this behavior.

A hash check establishes consistency with a recorded digest. It does not by itself establish upstream authenticity, clinical correctness, access control or tamper-proof storage.

## C.3 M6 manifest-hash discrepancy resolved

The committed results record:

```text
recorded dataset_manifest_sha256:
327be90a503a74a028d0e4dbfc1ab214a97b73bbca7e733d0e5a0ecfcf1edbc0
```

(`experiments/m6/outputs/results.json:4–10`.)

The current LF checkout of `src/hyperion_mda/data/physionet/wrist-1.0.0.provenance.json` hashes to:

```text
732ae914ddfbeec34eb99a39df5c786d69a1859b8466c38c91ae9e483f78454c
```

This initially looked like stale provenance. A byte-level probe showed that converting the same manifest from LF to CRLF produces **exactly** the recorded `327be90a…` digest. The parent commit `f1add93` also contains the same LF bytes as the current checkout. There is no manifest content diff between that parent and HEAD. The parent added output-only LF checkout attributes; HEAD changes the M6 portability test, forces LF when writing JSON/Markdown outputs, and refreshes provenance fields without changing metrics.

**Conclusion:** the mismatch is explained by checkout line endings, not demonstrated stale results. Do not report it as fabricated or invalid output. The underlying weakness is hashing checkout-dependent bytes (`experiments/m6/run_m6.py:59–60,368–374`). Use a documented canonical representation or pinned LF bytes for future provenance manifests, and record the convention alongside the hash. Do not silently rewrite historical results to make the old digest match.

The config hash and all 11 recorded source-file hashes matched the current checkout in this review. The recorded `git_head` is the historical `f1add93…`, with a note that M6 files were then uncommitted; it is not expected to equal the later review HEAD.

# D. Machine learning, evaluation and scientific claims

## D.1 M6 methodology

M6 is a real offline experiment on the recorded non-astronaut lane, not a neural clinical model:

- 8 participant folds; every window of the held-out participant stays together. `lopo_predict()` asserts disjoint participant sets, one prediction per row and complete coverage (`experiments/m6/m6_models.py:106–129`).
- Standardization/model fitting uses training rows only; tests cover the fit/transform boundary (`experiments/m6/tests/test_m6.py:120–178`).
- ECG is a reference, not an input; input/reference loading is separated and ECG-exclusion tests exist (`experiments/m6/tests/test_m6.py:83–115`; `docs/M6-LOPO-PROTOCOL.md:262–265`).
- Fixed ridge α=1.0 and logistic C=1.0; no test-fold tuning (`experiments/m6/m6-lopo-config.json:61–71`).
- Participant-level paired bootstrap, 10,000 resamples, seed 20261115 (`experiments/m6/m6_metrics.py:22–32`; config `:85`).
- 8 s windows with 2 s step; overlap stays within participant/record boundaries. Filtering is explicitly non-causal/offline (`docs/M6-LOPO-PROTOCOL.md:245–258`).

This is a sound baseline-evaluation pattern for the stated dataset. It does not establish prospective, causal, clinical or astronaut performance.

## D.2 Measured results and correct interpretation

The independent verifier passed against the committed prediction CSVs here. The following values are therefore **arithmetically verified committed results**, with raw-data regeneration still repository-reported rather than reproduced in this sandbox.

| HR model | Mean participant MAE (bpm) | Interpretation |
|---|---:|---|
| A0 training mean, no signal | 24.18 | Reference floor |
| A1 frozen M5 peak interval | 23.67 | Difference vs A0 −0.51 [−4.85, 3.50]; no demonstrated improvement |
| A2 PPG spectral peak | 46.32 | Worse than A0 |
| A3 ridge, PPG | 30.90 | Worse than A0 |
| A4 ridge, PPG + accelerometer | 32.22 | Worse than A0 |
| A5 ridge, accelerometer only | 30.06 | Worse than A0; important motion-only ablation |

Source: `docs/M6-RESULTS-SUMMARY.md:26–57`.

| Activity model | Pooled accuracy | Macro-F1 |
|---|---:|---:|
| B0 majority | 0.451 | 0.207 |
| B1 logistic, accelerometer | 0.733 | 0.731 |
| B2 logistic, accelerometer + PPG | 0.715 | 0.708 |

Source: `docs/M6-RESULTS-SUMMARY.md:73–103`.

Correct conclusions:

- **No HR method beat the no-signal baseline** under the repository's predeclared reading rule.
- **B1 improved over majority activity prediction on this dataset**, but all 143 windows from participant s4's run were misclassified; labels are per record and intensity/person are confounded.
- **No evidence that PPG added value beyond accelerometer features at n=8.** That is not proof that PPG contains no pulse information (`docs/M6-RESULTS-SUMMARY.md:59–71`).
- s4 strongly influences aggregate error; the with/without-s4 sensitivity analysis is reported rather than silently dropping the participant.
- The planned onset sensitivity S1 was omitted because no onset time was documented; this is an explicit limitation, not a completed analysis (`docs/M6-LOPO-PROTOCOL.md:15–26`; `docs/M6-RESULTS-SUMMARY.md:105–113`).

## D.3 What the verifier does—and does not—prove

`experiments/m6/verify_m6.py:1–9` recomputes metrics from committed per-window prediction CSVs using independent standard-library metric code, then checks JSON/CSV/report consistency. Its `1187` passing checks are meaningful arithmetic/report-integrity evidence.

It does **not** re-read the raw PhysioNet recordings and re-derive every prediction. That end-to-end path belongs to `RealDataPipelineTests`, which skipped here because the verified cache was absent (`experiments/m6/tests/test_m6.py:239–249`). The historical log reports a full run and 14/14 byte-identical outputs, but this review could not independently repeat that raw-data run.

The current portability test removes provenance before comparing regenerated and committed outputs, while retaining metric/CSV comparison (`experiments/m6/tests/test_m6.py:283–312`). That is a reasonable response to environment-dependent metadata, but the new `test_provenance_still_recorded` checks presence, not semantic correctness. Keep separate checks for config/source identity and canonical dataset-manifest identity.

## D.4 Missing ML/privacy capabilities

Not implemented: neural risk heads, Kalman adaptation, exertion residualization, split conformal prediction, MC-dropout uncertainty, ONSD CNN, Flower, Opacus/DP-SGD, secure aggregation, cosine-median Byzantine filtering or radiation fault injection. The status and architecture documents explicitly list these gaps (`docs/IMPLEMENTATION-STATUS.md:41–57`; `docs/ARCHITECTURE.md:111–118`).

The toy FedAvg code is useful pedagogically, but it has no network clients, privacy accountant, malicious-client model or resilience experiment (`src/hyperion_mda/fl_sim.py:87–140`). FedAvg alone is not a privacy guarantee.

# E. User interface and lane separation

## E.1 Implemented experience

The desktop app exposes the NASA table/chart, channel panel, simulated playback, recorded playback/HR check, FL simulation and generic CSV import. Playback has Start/Pause/Reset and seeking (`src/hyperion_mda/playback_view.py:50–101`). The registry has structural checks for unique IDs, valid status/lane combinations and no values in unavailable channels (`src/hyperion_mda/signal_registry.py:184–210`).

Lane separation is more than a banner: simulated/FL/NASA import-direction tests and distinct sample/record types exist (`tests/test_demo_lanes.py:47–65`), and the historical acceptance session reports that other lanes left the NASA table/status unchanged (`demo-evidence/06-live-acceptance.txt:35–45`). M6 is outside the app and does not feed the NASA lane (`docs/ARCHITECTURE.md:44–50`).

## E.2 Limits and UI risks

- No browser frontend exists; Tkinter is the UI.
- No real device adapter, live 1 Hz oscilloscope, clinical workflow, organ-risk visualization or in-app activity classifier exists.
- The channel panel is a status/provenance view, not a validated digital twin.
- The HR check blocks the Tk event loop while computing. The historical 3.02 s gap is documented, but responsiveness on slower machines is unverified.
- GUI behavior could not be observed here because Tkinter is unavailable. The eight-workflow PASS log and screenshots are historical evidence, not a live result from this review.

# F. API, backend, frontend and deployment

## F.1 Current state

**No HTTP API or server was found.** There are no routes, FastAPI/Flask/Django app, websocket service, browser package, Dockerfile, compose stack, environment template or deployment CI workflow. The supported delivery path is a local Python/Tk installation, not a hosted application.

Packaging was exercised with:

```bash
pip install --target /tmp/hyperion-review-install --no-deps .
```

The wheel built successfully (61,572 bytes), and the installed copy was launched from outside the source tree. It failed at `import tkinter`, confirming both that the packaged entry point resolves and that this environment lacks the OS-level GUI dependency. No live web preview was started because there is no web server to preview.

This absence is consistent with the repository's local-only scope. It becomes a delivery gap only if a browser-accessible or multi-user demonstration is required.

## F.2 If a browser demo is requested later

The following is a **proposal**, not existing functionality:

1. Preserve the existing lane-aware core and verification boundaries; add a thin typed API rather than mixing data lanes in a new database.
2. Provide read-only dataset/status/report endpoints and explicit import jobs. Run HR/M6 work off the request/UI thread, with job IDs, progress, cancellation and bounded caches.
3. Keep provenance, units, missingness and lane labels in every response. Do not expose a clinical-risk endpoint without the separate clinical/data gates.
4. Add authentication/authorization, local-storage threat modeling and an append-only application audit trail before handling sensitive crew data.
5. Build a separate browser client that consumes relative API URLs. In a hosted preview, bind the server to `0.0.0.0`, allow the preview origin as appropriate, and proxy API calls through the dev server; browser code must not call sandbox `localhost`.
6. Containerize the API/experiment workers separately from the Tk desktop. A headless API container should not pretend to provide the desktop GUI.
7. Add contract tests, lane-isolation tests, failure-injection tests, a locked environment and a clean-machine deployment smoke test before claiming deployability.

No framework choice should be presented as already implemented, and no blockchain is needed for the first local audit trail.

# G. Privacy, security and auditability

## G.1 What exists

- Network code is confined to explicit dataset fetch commands; the runtime does not upload health records to a service (`docs/ARCHITECTURE.md:36–42`; fetch modules).
- Samples carry provenance, and adapter validation rejects mismatched provenance/units/channels and malformed values/times (`src/hyperion_mda/adapters.py:93–113`).
- SHA-256 checks protect against accidental alteration relative to a pinned manifest.
- Data lanes use separate types/windows and are covered by import-direction tests.

## G.2 What does not exist

- No encryption at rest, authentication, authorization or access-control layer is established.
- No production audit/event log, append-only load history, review-state persistence or cryptographic receipt exists. The requirements document explicitly marks the local audit log as proposed (`docs/REQUIREMENTS-TRACEABILITY.md:288–294`).
- No differential privacy, secure aggregation, privacy accountant, membership-inference evaluation or formal threat model is implemented.
- No blockchain/Solidity ledger exists.
- No HIPAA/GDPR suitability, NASA standards compliance or security certification is established (`docs/IMPLEMENTATION-STATUS.md:54–57`; `docs/REQUIREMENTS-TRACEABILITY.md:370–378`).

The local caches and M6 outputs should not be described as secure storage merely because they are local or hashed.

## G.3 Derived-data governance finding

M6 writes participant IDs, record names, window positions, reference HR, features and predictions into tracked output files (`experiments/m6/run_m6.py:302–315,414–417`). These are derived from the open PhysioNet dataset, not astronaut records. The repository records ODC-By 1.0 and required citations, so this is **not an established license violation or private-data leak**.

However, the original protocol preferred derived per-window outputs outside the repository (`docs/M6-LOPO-PROTOCOL.md:279–285`), while the approved deviation put outputs inside `experiments/m6/` (`:15–25`). Other docs use blanket language such as “never redistributes.” Reconcile that wording with the actual tracked derived artifacts, and record the team's redistribution/attribution decision explicitly. Apply a much stricter gate before any real crew-derived windows are committed.

## G.4 Minimum audit design before sensitive persistence

A proportionate first step is a local JSONL event stream containing UTC time, app/config version, lane, file identifier, content digest, row/issue counts and review transitions—without raw health values. Test that a second event leaves existing bytes unchanged and that the recorded digest matches the loaded file. Document filesystem permissions and backup behavior. This provides traceability, **not** tamper resistance; stronger guarantees require a separate threat model and security review.

# H. Execution, tests and reproducibility

## H.1 Commands executed here

All commands below were run from the repository root unless a different working directory is stated. Temporary paths are outside the repository.

| Command | Observed result | Exit |
|---|---|---:|
| `python -m unittest discover -s tests -v` | `Ran 159 tests … OK (skipped=30)` | 0 |
| `PYTHONPATH=src /tmp/hyperion-review-venv/bin/python -m unittest discover -s experiments/m6/tests -v` | `Ran 28 tests … OK (skipped=8)` | 0 |
| `/tmp/hyperion-review-venv/bin/python experiments/m6/verify_m6.py` | `1187 checks passed, 0 failed` | 0 |
| `python run.py` | `ModuleNotFoundError: No module named 'tkinter'` | 1 |
| `python -m hyperion_mda` (from `src/`) | Same Tkinter import failure | 1 |
| Installed-copy `hyperion-mda` console entry point | Same Tkinter import failure from the installed package | 1 |
| `python experiments/m6/run_m6.py` (system Python) | NumPy import failure | 1 |
| `HYPERION_MDA_DATA_DIR=/tmp/hyperion-review-cache PYTHONPATH=src /tmp/hyperion-review-venv/bin/python experiments/m6/run_m6.py /tmp/hyperion-review-m6-outputs` | `PhysioNetMissingError` / `AdapterError`: `s1_high_resistance_bike.hea was not found…` | 1 |
| `PYTHONPATH=src HYPERION_MDA_DATA_DIR=/tmp/hyperion-review-cache /tmp/hyperion-review-venv/bin/python -c 'from hyperion_mda import dsp_hr; dsp_hr.run_check()'` | Same missing verified PhysioNet header, surfaced as `AdapterError` | 1 |
| `python demo-evidence/live_acceptance_script.py` | Tkinter import failure; the reviewed script also contained a hardcoded Windows path (now repository-relative) | 1 |

The explicit M6 output argument was used to avoid overwriting tracked outputs. The run failed on missing input before writing results.

### Exact fetch failures

```bash
PYTHONPATH=src python -m hyperion_mda.osdr_fetch \
  --cache-dir /tmp/hyperion-review-cache/osdr/OSD-575
```

```text
OSDR download FAILED: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)>
exit 1
```

```bash
PYTHONPATH=src python -m hyperion_mda.physionet_fetch \
  --cache-dir /tmp/hyperion-review-cache/physionet/wrist-1.0.0
```

```text
PhysioNet download FAILED: <urlopen error TLS/SSL connection has been closed (EOF) (_ssl.c:992)>
exit 1
```

These are sandbox connectivity failures, not evidence that the upstream datasets are unavailable generally.

### Test-count accounting

A custom `unittest` result-accounting probe reported:

```text
main: collected 173; runner testsRun 159; failures 0; errors 0;
      skip records 30; non-skipped runner records 129
M6:   collected 28; loader errors []
```

Do **not** describe the main result as “159 passing tests.” The runner count includes skip records, and 173 collected items did not all execute as individual test bodies in this dependency/data-limited environment. The historical `Ran 173 … OK` log was produced with Tkinter and verified caches present. Similarly, the historical M6 count was 27 before the current portability commit added a test; the current suite has 28 definitions, of which 8 skipped here.

The expected stderr lines `OSDR download FAILED: boom` and `PhysioNet download FAILED: boom` also appeared during the main suite. They come from deliberate failure-injection tests, not unexpected network failures (`docs/MENTOR-DEMO-GUIDE.md:70–72`).

## H.2 Headless probes

Registry probe:

```text
49 channels: 19 MEASURED-LAB-SAMPLE, 5 RECORDED-NON-ASTRONAUT,
3 SIMULATED, 22 UNAVAILABLE
```

Toy FedAvg probe (`run_fedavg(4, 5, 7)`):

```text
clients 4 rounds 5 seed 7 sizes {'client-1': 30, 'client-2': 40, 'client-3': 50, 'client-4': 30}
final_weights (0.9327564802936943, 1.0207541343468947, -0.033688540970288124)
exit 0
```

Wrong-`TEST_TYPE` probe:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from test_osdr import HEADER, cmp_row
from hyperion_mda.osdr_cmp import parse_cmp_rows, analyse
with TemporaryDirectory(prefix='hyperion-review-') as d:
    p = Path(d) / 'synthetic.csv'
    p.write_text(HEADER
        + cmp_row(value='80', timepoint='L-92', test_type='CBC')
        + cmp_row(value='82', timepoint='L-44')
        + cmp_row(value='84', timepoint='L-3')
        + cmp_row(value='100', timepoint='R+1'), encoding='utf-8')
    rows, report = parse_cmp_rows(p)
    scored = analyse(rows, report)
    print('wrong_test_type_lines', report.wrong_test_type_lines)
    for r in scored:
        if r.timestamp in ('L-92', 'R+1'):
            print(r.timestamp, 'flags=', r.flags, 'z=', r.z_score, 'note=', r.score_note)
PY
```

Output is recorded in B.2. This probe used synthetic rows only and wrote only to a temporary directory.

## H.3 Historical evidence pack

| Artifact | Repository-reported result | Review status |
|---|---|---|
| `demo-evidence/01-m6-run.txt` | 3332 windows; A1 identical to M5; exit 0 | Not raw-data-reproduced here |
| `demo-evidence/02-m6-verify.txt` | 1187 checks, 0 failures | Independently repeated here |
| `demo-evidence/03-tests-173.txt` | 173 tests, OK, exit 0 | Different environment; current run has skips |
| `demo-evidence/04-tests-m6-27.txt` | 27 tests, OK, exit 0 | Historical count; current suite has 28 |
| `demo-evidence/05-m6-reproducibility.txt` | 14/14 files byte-identical | Historical; raw rerun blocked here |
| `demo-evidence/06-live-acceptance.txt` | 8/8 workflows PASS; 0 Tk callback exceptions; 0 dialogs; clean mainloop exit | Historical; GUI not runnable here |
| `demo-evidence/screenshots/` | Eight documented workflow screenshots | Inspected as repository evidence, not live capture here |

The evidence pack is useful and internally consistent with its stated environment. Its authenticity cannot be independently established from text logs alone. The reviewed hardcoded acceptance-script path limited reproducibility; the current harness is repository-relative.

## H.4 Coverage gaps

The tests cover many validation, ordering, checksum, adapter, registry, lane-separation, model and metric cases. Not established here: a cross-platform GUI run, real-data fetch/import, raw-data M6 regeneration, numeric-version compatibility matrix, coverage percentage, security testing, load testing, deployment smoke test or clinical validation. No CI workflow enforces these checks automatically.

# I. Documentation, claim hygiene and next steps

## I.1 Claims that are supportable

- “A local research prototype with separate NASA lab, simulated, recorded non-astronaut and FL-simulation lanes.”
- “The NASA path verifies a pinned public lab file and displays descriptive, unvalidated pre/post comparisons.”
- “M6 uses participant-separated linear baselines on terrestrial exercise data and reports negative HR findings.”
- “The committed M6 metrics pass an independent arithmetic verifier.”
- “The channel panel is a provenance/status view, not a validated physiological twin.”

## I.2 Claims that are not supportable

- Clinical diagnosis, risk stratification, treatment/countermeasure guidance or flight-surgeon readiness.
- Validated astronaut HR, stress, activity or organ-risk inference.
- Live NASA/CSA/device integration or continuous astronaut wearable ingestion.
- Privacy-preserving federated learning, DP guarantees, Byzantine/radiation resilience or a cryptographic audit ledger.
- The concept's reported performance improvements as results of this code.
- A hosted web app or production deployment.
- “All 173/27 tests passed here” or “the GUI was verified here.” Those are historical/environment-specific statements, not this review's result.

## I.3 Specific documentation corrections

1. `README.md:9` and `docs/IMPLEMENTATION-STATUS.md:3` reference `dist/HYPERION-MDA-Prototype.zip`; that file is absent from this checkout. `dist/` is ignored (`.gitignore:6`). Remove the claim or provide an authorized, checksum-identified artifact location.
2. `docs/IMPLEMENTATION-STATUS.md:24` still describes 41 channels/no simulated or recorded channels. The actual count is 49; `README.md:66` and the registry agree. The current README and registry agree on 49 channels.
3. M6 references to 27 tests are historical; current code has 28 (`experiments/m6/tests/test_m6.py:293–296` adds the portability-era provenance-presence test). Update guides or label the old count as pre-commit evidence.
4. The superseded desktop demo runbook was removed during cleanup; use `docs/MENTOR-DEMO-GUIDE.md` for the desktop lane and `docs/WORKSTATION-RUNBOOK.md` for the web workstation.
5. Older traceability sections describe a synthetic-only/no-network state (for example `docs/REQUIREMENTS-TRACEABILITY.md:201–206,283–286`). Current code has real NASA/PhysioNet lanes and explicit fetches. Mark Part B as historical or reconcile it with Part A/current status.
6. Reconcile “never redistributes” wording with the tracked derived M6 outputs, as discussed in G.3.
7. Resolved: the acceptance harness now uses a repository-relative path and documents a cross-platform invocation.

## I.4 Prioritized remediation plan

### P0 — before relying on the validation claim

- Fix R1 with explicit wrong-type exclusion and regression tests for baseline and observation roles.
- Add a test that a flagged invalid assay cannot change any valid observation's mean, SD or z-score.
- Keep the current no-clinical-use banners and NASA flag disablement unchanged.

### P1 — before a mentor/judge rerun on another machine

- Provide a tested numeric extra/lockfile and OS-level Tk setup instructions; record exact versions used for the demo.
- Make the acceptance harness portable and rerun all eight workflows with both verified caches on a Tk-capable machine.
- Add CI for the headless core/synthetic tests and a separate, explicitly gated real-data job; report skips rather than hiding them.
- Define canonical provenance hashing and retain separate checks for source/config identity versus environment metadata.
- Correct the stale counts, archive references and historical/current documentation boundaries.

### P2 — before broader data handling or a browser demo

- Resolve derived-data redistribution wording and write a storage/threat model.
- Add the minimum local audit trail if load/review history is actually required.
- Move expensive UI computations off the Tk thread.
- If a web UI is requested, implement the thin lane-aware API/client proposal in F.2 with contract and deployment tests; do not relabel the Tk app as a web app.

### P3 — research expansion, only after gates

- Treat M7 as a proposal, not a result. Freeze its protocol/config before evaluating it against the same baselines and participant splits.
- Obtain suitable data and documented labels before adding residualization, artifact detection, conformal calibration or clinical workflows.
- Add Flower/DP only with a justified multi-owner use case, threat model, accountant output and independent privacy review.
- Require qualified clinical review and formal qualification before any diagnostic, treatment, countermeasure or flight-readiness claim.

## Final assessment

**Promising engineering evidence; limited and clearly non-clinical scientific scope; one concrete validation defect to fix; not production or flight ready.** The repository's best feature is its willingness to show missing data, negative results and unsupported claims honestly. Preserving that discipline while fixing eligibility, reproducibility and documentation drift is more valuable than adding impressive but unvalidated clinical or privacy features.
