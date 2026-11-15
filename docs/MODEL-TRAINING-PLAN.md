# Phased model-training plan (MVP)

**Status: the WESAD plan below is still a plan only.** No WESAD model has been trained, and the WESAD gate is NO-GO. The numbers below are design parameters to fix *before* looking at test results, not findings.

> **Update 2026-11-15.** The LOPO evaluation pattern of this plan has been carried out on a *different* dataset: PhysioNet Wrist PPG During Exercise, as build milestone **M6**.
> - **Models:** linear models only (ridge regression and logistic regression), with fixed hyperparameters, under leave-one-participant-out evaluation.
> - **Tasks:** heart-rate estimation and walk / run / cycle activity labels. It is not a stress task.
> - **Where:** [M6-LOPO-PROTOCOL.md](M6-LOPO-PROTOCOL.md) and [M6-RESULTS-SUMMARY.md](M6-RESULTS-SUMMARY.md).
>
> No Flower or DP experiment has been run.

## 0. Scope decision: which data can support a model?

| Dataset | Labels suitable for supervised learning? | Decision |
|---|---|---|
| **NASA OSDR OSD-575 CMP** (4 crew, 7 sparse timepoints, serum chemistry) | **No.** There are no outcome labels; there are 4 people; it is not a wearable signal. | **No model.** Descriptive pre/post comparison only (already built). |
| Other Inspiration4 OSDR studies (omics, microbiome, CBC) | No labels for any wearable task; not wearable signals | No model |
| Any astronaut wearable or vital-sign time series | **No public source found** (inventory §1–§2, Q3) | No astronaut wearable model |
| **WESAD** (15 participants, terrestrial lab study, chest + wrist sensors) | **Yes:** the protocol-condition labels (neutral/baseline, stress, amusement; exact codes to be verified from the readme, Q2) | **One methods-demonstration task**, clearly labelled *non-astronaut, lab study* |

**The single task:** *binary classification of the WESAD protocol condition, stress vs non-stress (baseline + amusement), from short windows of **wrist** (Empatica E4) signals.*
- **Why wrist signals:** they are the closest analogue to a consumer wearable, with lower data volume than the 700 Hz chest device.
- **What the label means:** it is the *study-protocol phase*, not a physiological ground truth and not a health state. The report must say so.
- **What it can't show:** the task demonstrates the **method** (ingestion → features → participant-separated evaluation → FL simulation → DP experiment). It says **nothing** about astronauts, spaceflight stress, or clinical usefulness.
- **The three-class variant** (baseline / stress / amusement) is an optional secondary analysis. It is decided before seeing results, and it is reported with per-class metrics.

## 1. Phases and gates

Each phase ends at a gate. **Do not start the next phase until its gate passes.**

### Phase 1: data-access and provenance gate (WESAD)

- Confirm WESAD's current terms of use from the dataset owner (the owner page has moved; inventory Q1). Record the exact wording and date in a manifest. **Track neither raw nor derived WESAD data in git**; fetch it on demand, as with OSDR. (Nothing WESAD is currently downloaded or tracked; the gate is NO-GO.)
- Download into a local cache **outside the repository**, and record the source URL, retrieval time, file sizes and SHA-256 in `wesad.provenance.json`.
- Inspect read-only: verify the participant IDs present, the label codes, the sampling rates and the file formats against the official readme (Q2). Prefer the raw device files to the `.pkl` pickles; if pickles are unavoidable, load them only in an isolated subprocess after the checksum check.
- **Gate 1:** terms confirmed in writing; checksums recorded; readme facts verified, with any discrepancy written up; no data in git or in any ZIP.

### Phase 2: reproducible preprocessing

**Design parameters**, fixed in a versioned config before evaluation (stated as choices, not results):
- **Signals:** wrist BVP (64 Hz), EDA (4 Hz), temperature (4 Hz) and 3-axis accelerometer (32 Hz), as listed by UCI. Verify against the files.
- **Windows:** 60 s, with a 30 s step. Each window takes the majority label inside it, and **windows that span a label change are dropped**. Transient or undefined label codes are dropped (exact codes per the readme).
- **Features:** simple, documented and deterministic. For example:
  - EDA: mean, SD, slope
  - temperature: mean, slope
  - accelerometer magnitude: mean, SD
  - BVP: amplitude statistics, plus pulse rate **if** peak detection is validated on visible traces first

  The `scipy.signal` functions used, and their parameters, are recorded in the config.
- **No resampling across gaps and no imputation.** Windows with missing samples are dropped and counted.
- **Leakage controls:**
  - Scalers, feature selection and any normalisation are **fitted on training participants only**, inside each fold.
  - No per-participant normalisation that uses the test participant's labels.
  - The same participant never appears in more than one of train, validation or test within a fold.
- **Reproducibility:** fixed seeds, a config hash and a feature-file hash are written alongside every result. Running the same config twice must produce byte-identical features.
- **Gate 2:** unit tests prove there's no participant overlap between folds, that the scaler is fitted on training data only, that windows crossing a label change are dropped, and that features are deterministic. Window counts per participant and class are reported.

### Phase 3: participant-separated baselines (centralised)

- **Splits: leave-one-participant-out (LOPO).** There is one fold per participant (about 15, depending on Q2). Hyperparameters are tuned only by **nested** participant-separated validation inside the training participants, or not tuned at all (fixed defaults). Which of the two is decided before running.
- **Models, all CPU-only with scikit-learn:**
  1. **Majority-class baseline.** This is the floor every other model must be compared against.
  2. **Logistic regression** (L2, class-balanced weights). This is the **simple baseline**.
  3. Optionally, a small random forest (the PPT names one). It is reported only alongside 1 and 2.
- **Metrics, for each fold and pooled:**
  - per-class precision, recall and F1
  - macro-F1 and balanced accuracy
  - the confusion matrix
  - AUROC, if probabilities are calibrated enough to be meaningful
  - the class prevalence of each test participant
- **Uncertainty:**
  - the per-fold distribution (median and range)
  - **participant-level bootstrap** 95% confidence intervals: resample participants, not windows, because windows from one person are correlated
- **What gets reported:** every number goes with its fold count and participant count. Failures and participants with poor results are reported too. **No claim of "better"** unless the participant-level CI of the paired difference excludes 0, and even then it applies only to *this lab dataset*.
- **Gate 3:** the evaluation report is generated end to end by one script from the hashed features. The majority baseline is present. The leakage tests from Gate 2 pass.

### Phase 4: Flower federated learning (simulation only)

- **Framing:** this is a **Flower Simulation Runtime** experiment (`flwr run`, Ray backend). It does **not** represent multiple habitats, agencies or devices.
  - Each simulated client is a **set of WESAD training participants**, for example one participant per client.
  - The report must say: *"simulated clients on one machine; no independent data owners."*
  - The PPT's silo names (Station, Spacecraft, Base, Rover) **are not used.**
- **Identical splits:**
  - For every LOPO fold, the held-out participant is excluded from **all** clients.
  - The centralised model in that fold is trained on the **union of exactly the same training participants**.
  - A test asserts that the client partitions' union equals the centralised training set.
- **Model:** the same logistic-regression model (parameters exchanged as numpy arrays) with FedAvg. Fixed rounds, local epochs and seeds are recorded.
- **Comparison:** federated vs centralised vs local-only (each client's own model, evaluated on the same held-out participant). All three use the Phase 3 metrics and participant-level bootstrap CIs.
- **Not in the MVP:** non-IID "habitat" partitioning claims, the Byzantine/cosine-median filter, and radiation fault-injection claims.
- **Gate 4:** the identical-split test passes; the run is reproducible from config and seed; the report is labelled "simulation".

### Phase 5: differential privacy, as a separate experiment

**Threat model:**
- **Asset:** a training participant's window-level records.
- **Adversary:** anyone who obtains the trained model parameters, for example to attempt membership inference.
- **Out of scope:** a malicious server or clients, network attackers, and side channels.

**What the guarantee covers:**
- DP-SGD (Opacus) gives **record-level (window-level)** (ε, δ) under its assumptions: Poisson sampling, and per-sample gradient clipping computed by the wrapped model.
- Windows from the same person are correlated, so **record-level DP is not participant-level DP.**
- Participant-level guarantees would need user-level or client-level DP. With about 13–15 participants that would be very noisy; it is optional and reported only if run.

**Federated learning alone provides no formal privacy guarantee.** This is stated in every report.

**The experiment:**
- A small PyTorch model (logistic regression, or a tiny MLP with no BatchNorm), trained centralised with `opacus.PrivacyEngine` on the same LOPO folds.
- δ is set below 1/(number of training windows).
- A sweep over the noise multiplier, **or** over a target ε (`make_private_with_epsilon`).
- Report the **accountant's actual output** (`get_epsilon(delta)`), naming the accountant used (Opacus default `prv`, or `rdp`), alongside the Phase 3 metrics and CIs.
- `secure_mode` is recorded (True requires `torchcsprng`). If False, the report states that the noise source is not cryptographically secure.

**Optional, and only after the centralised DP experiment works:** DP inside the Flower simulation, with the same reporting rules.

**Gate 5:** the threat-model document exists; ε, δ, the accountant, the sampling method and `secure_mode` are reported for every run; no sentence claims that the system "guarantees privacy" outside those stated conditions.

### Phase 6: integration and reporting

- The UI's "Methods demo (WESAD)" tab shows the **static evaluation report**: metrics, CIs, fold counts and limitations. It does **not** show live predictions on astronaut data, and it is never placed in the astronaut twin.
- Docs updated: the traceability document, the inventory, the status document, the runbook.
- **Gate 6:** the MVP acceptance criteria (§3) all pass; the candidate ZIP is rebuilt; the frozen ZIPs are unchanged.

## 2. Explicitly not planned

- Training on OSD-575 or any astronaut data.
- Clinical thresholds, diagnosis or treatment output.
- Six-organ risk heads.
- Exertion residualization on astronaut data.
- Conformal or MC-dropout risk gating.
- Ultrasound CNNs.
- PVT instruments.
- Multi-habitat deployment.
- Blockchain.
- LangGraph.
- Performance-improvement claims beyond the stated lab-data comparison.

## 3. MVP acceptance criteria

1. **Lane A (NASA):** OSD-575 loads only after SHA-256 verification, and a mismatch loads nothing. Provenance, licence status (none stated) and limitations are visible in-app and in the docs. *(Already met; it must stay green.)*
2. **Twin panel:**
   - Every displayed channel carries exactly one status: MEASURED-LAB-SAMPLE, RECORDED-NON-ASTRONAUT, SIMULATED or UNAVAILABLE.
   - The status comes from the signal registry, and there is a test for every channel.
   - The figure contains no organ risk, score or threshold.
   - The "not a validated physiological twin" notice is always visible.
3. **Lane separation:** tests prove that no WESAD value is reachable from the astronaut view or the OSD-575 records, and that OSD-575 data is never passed to training code.
4. **WESAD provenance:** terms recorded; checksums pinned and verified on load; no WESAD data in the repository or ZIPs.
5. **Evaluation:**
   - LOPO with participant-overlap tests; the majority and logistic-regression baselines.
   - Per-class metrics, macro-F1, balanced accuracy and confusion matrices.
   - Participant-level bootstrap CIs.
   - The full report regenerates from config and seed, with identical numbers.
6. **FL:** a Flower simulation vs centralised vs local-only comparison on **identical** participant splits (with a test), labelled "simulation".
7. **DP:** a separate experiment with the threat model; ε, δ, the accountant, the sampling method and `secure_mode` reported from the accountant; no privacy claims for FL alone.
8. **Claims hygiene:** no clinical thresholds, diagnoses, treatment text, organ-risk output, NASA/CSA integration, flight-readiness or performance-improvement claims anywhere in the UI or docs (the docs scan is checked against a list of banned phrases).
