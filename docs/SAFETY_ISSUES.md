# Safety issues and deliberate deviations from the concept deck

This file records every place where `HYPERION_MDA.pdf` asks for something that would be unsafe or
unevidenced to ship, and what this build does instead. **Gates are never tuned to make a scenario
pass.** If a scenario produces an inconvenient verdict, the scenario or the documentation changes —
not the threshold.

---

## S1 — Gate 1 ships with no default threshold

**Deck:** "If Kurtosis < 2.5 → quarantine the window."

**Problem:** A fixed kurtosis cutoff is sensor-, placement- and population-specific. The PhysioNet
wrist records are explicitly uncalibrated (ECG amplitudes in the hundreds–thousands of "mV" are not
physically plausible). Shipping `2.5` would be an invented constant presented as a safety gate.

**This build:** Gate 1 returns `UNKNOWN` with reason `"not calibrated"` until a per-subject
calibration exists. `UNKNOWN` is never displayed green and never permits a rate alarm to be
suppressed downstream. The kurtosis and slew values are still computed and shown as evidence.

**To change:** supply a calibration procedure with a stated reference population and error rate.

## S2 — Activity is per-person scale-normalised, not ENMO in g

**Deck:** "ENMO = 0.31 g (Exercise)"; "ENMO > 0.22 g".

**Problem:** ENMO in g requires a calibrated accelerometer in known units. `docs/DATA-SOURCE-INVENTORY.md`
records that the wrist accelerometer amplitudes are **not calibrated**. A `0.22 g` cutoff on this data
would be meaningless, and exercise detection would silently depend on device gain.

**This build:** activity is `(magnitude − rest_median) / rest_scale` for the **same person**, using
their own resting window: a dimensionless, per-person z-like quantity. The API field is
`activity_norm` and the unit is `"per-person rest scale (dimensionless)"`. No g-based constant exists
in the gate code. The cockpit may *display* a labelled SIMULATED ENMO g reference channel, but it never
feeds the gate.

## S3 — Exercise suppression can never hide a non-rate alarm

**Deck:** Gate 2 "BLOCKS FALSE ALARM" when movement explains the heart rate.

**Problem:** A blanket exercise filter would also suppress arrhythmia, irregular rhythm, apnoea or
any non-rate finding that happens to occur during exercise.

**This build:** `non_rate_flags` are evaluated **before** and **independently of** Gate 2. Any
non-rate flag forces escalation regardless of activity, residual, or calibration state. Covered by
`tests_api/test_gates.py::test_non_rate_flags_are_never_suppressed`.

## S4 — Hard HR ceiling and hold timeout

**Problem:** An exercise filter with no upper bound would suppress a genuinely dangerous rate, and
an unbounded suppression would hide a sustained problem indefinitely.

**This build:** two independent limits, both declared constants in `api/gates.py`:
- `HARD_HR_CEILING_BPM = 180` — above this, alert regardless of activity or residual.
- `MAX_SUPPRESSION_HOLD_S = 120` — continuous suppression longer than this escalates to a surgeon
  alert with reason `"suppression hold timeout"`.

These are **demo limits, not clinical thresholds**, and are labelled as such in the UI.

## S5 — No treatment advice

**Deck slide 5** recommends: "Fluid Load (500 mL) + Salt", "Drink 600 mL Water + Potassium Citrate",
"Low-Glycemic Ration", "480 nm Blue LED Light Therapy", "LBNP", "Check CO2 Scrubber".

**Problem:** These are treatment instructions. This prototype has no clinical validation and must
not issue them.

**This build:** the action allow-list is exactly four strings (storm-shelter / fluid / ration / light
therapy prompts from the deck are **not** emitted as actions):
1. `Repeat measurement`
2. `Rest and recheck`
3. `Check sensor`
4. `Contact flight surgeon`

Enforced in code (`api/actions.py`) and asserted by a test that scans every action string returned by
the API. Nothing else can reach the UI.

## S6 — Organ status is a demo rule table

**Deck:** six organ systems with NASA-STD-3001 / CSA thresholds (ONSD ≥ 5.8 mm, BP ≥ 140/90,
Temp ≥ 38 °C, glucose 100–125, PVT > 350 ms …).

**Problem:** `docs/REQUIREMENTS-TRACEABILITY.md` already classifies these figures as **unverified**
against the cited standards. Presenting them as validated compliance would be a false claim.

**This build:** a transparent rule table, each row visibly labelled `DEMO THRESHOLD`, with the
deck's number shown as *the deck's claim*, not as a validated limit. A stale input yields `UNKNOWN`,
never `NOMINAL`. No neural risk head exists. The unified cockpit extends the table with the deck's
multi-signal OR rules (CO₂/proton/water/ARED/HR); every added reference channel is labelled
SIMULATED or crew-log in the evidence string.

## S7 — Staleness never turns a signal green

**Deck:** `τ_m = exp(-λ·Δt_hours)`; stale exams raise uncertainty.

**This build:** τ is computed and displayed. A check older than its declared validity window is
`STALE` and its organ status becomes `UNKNOWN`. Missing data is `NOT_AVAILABLE`. A failed read is
`FAILED`. None of these render green. Gate 3 may `HOLD` a ground alarm and request the fastest crew
check, which is the deck's intended active-sensing behaviour, minus any risk model. In the unified
cockpit, elevated SIMULATED cabin CO₂ plus a stale ONSD τ specifically requests guided eye ultrasound.

## S8 — No neural network or LLM in the decision path

**Deck:** PyTorch `HyperionCoreNet`, MC-dropout, conformal bands from a neural predictor.

**This build:** no neural model is trained or loaded in the decision path. The unified workstation
adds `api/conformal.py`, a finite-sample split-conformal quantile on **SIMULATED** resting residuals,
labelled `demo split-conformal quantile … no coverage guarantee`. `sigma_epistemic` is `null` because
MC-dropout / HyperionCoreNet do not exist. The M6 ridge/logistic results are shown read-only as
measured offline evidence. The ML panel lists requested sklearn/PyTorch/Flower/Opacus benchmarks as
`NOT_IMPLEMENTED` rather than inventing metrics; the FL panel is the existing toy FedAvg simulation.

## S9 — Audit is a hash chain, not a blockchain

**Deck:** `HealthAudit.sol`, Solidity + web3.py, EVM on-chain.

**This build:** an append-only local JSONL log where each entry includes the previous entry's
SHA-256. `GET /api/audit/verify` recomputes the chain and reports the first broken link. This gives
tamper-*evidence*, not tamper-*proofing*, and is described that way in the UI. No raw measurement is
written to the audit log — only event type, subject, role, verdict and digest. Acknowledgement notes
are hashed (`note_sha256`) before anchoring; PVT/calibration audit entries store counts, not values.
`contracts/HealthAudit.sol` is a reference contract only and is **not deployed**.

## S10 — Demo-grade authentication

Role switching is a header, not an identity. Anyone can select any role. This is stated in the UI
banner and in `README-API.md`. It must not be deployed as an access-control boundary.

## S11 — Lanes never merge

The NASA lab lane, the SIMULATED/INJECTED scenario lane and the RECORDED non-astronaut lane are
separate. Every frame, alert and chart carries its lane badge. Scenario data can never be written
into the NASA lane, and the existing lane-separation tests still pass unchanged.

## S12 — Saturating demo context model, not fitted physiology

**Deck:** `r_HR = HR − f(ENMO, CO₂)` with an implied linear personal response.

**Problem:** an unbounded linear context model can "explain away" arbitrarily high heart rates, and
fitting it to the demo scenarios would tune the gate to pass.

**This build:** `api/gates.py` uses declared demo constants:
`expected = rest_median + 80·(1 − e^(−activity_norm/6)) + co2_hr_drive`, where the CO₂ term is a
labelled scenario-engine constant (`api/context.py`), not a measured physiological coefficient.
Residuals are one-sided; suppression still obeys the hard ceiling, hold timeout and non-rate bypass.
Gate constants are never changed to make a scenario pass.

## S13 — Dual-mode engine never silently substitutes real data

**Deck:** a single "REAL_EMPIRICAL_DATA" stream mixing OSD-575, GOES and WESAD/PhysioNet.

**Problem:** those sources have different populations, units and availability. GOES integral proton
flux is pfu, not mGy/day; WESAD is gate NO-GO; PhysioNet is non-astronaut and uncached here.

**This build:** `GET /api/state` reports each source independently (`sources.lab`, `sources.goes`,
`sources.wearable`). `REAL_EMPIRICAL` mode shows verified lab/GOES data when present and
`telemetry_mode=NOT_AVAILABLE` when no live wearable exists — it does **not** display simulated frames.
Selecting a scenario switches to `SIMULATED_FALLBACK` with the explicit non-flight banner. No
flux→dose conversion is performed.
