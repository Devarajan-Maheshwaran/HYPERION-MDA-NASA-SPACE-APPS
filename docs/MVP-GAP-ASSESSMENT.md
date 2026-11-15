# End-to-end MVP gap assessment vs the PPT reference

**Assessed:** 2026-11-14 · commit `f223da3` · branch `arena/da7479f7-hyperion-mda-nasa-space-apps`

## Source note

The original `.pptx`/`.ppt`/`.pdf` binary is not available in this checkout. This assessment uses the
repository's saved slide text in `docs/HYPERION-MDA-CONCEPT-AS-PROVIDED.txt` (10 slides)
and the existing PPT mapping in `docs/REQUIREMENTS-TRACEABILITY.md` Part A (6-slide
template). If the attached deck is a newer revision, re-upload it for exact slide-number
reconciliation. The functional gaps below are checked against current code, not only docs.

## Status update — 2026-11-14 (live cockpit wave)

The P0 runtime loop is now implemented and verified end-to-end over HTTP:

- **P0-1 live clock/transport:** backend-owned 1 Hz mission clock, SSE `frame` + `state`,
  pause/play/step/reset; cockpit boots directly into the live case at `/`.
- **P0-2 persistence:** SQLite case store (`HYPERION_STATE_DB`, default `var/hyperion-state.db`).
  A real process kill/restart preserved `t_s`, stage, running flag, packets, packet state,
  history length, audit entry count and audit head; the chain still verifies.
- **P0-3 closed workflow:** persisted S0–S4 FSM; S2 eye exam resolves to S3 or escalates to
  S4; surgeon acknowledgement returns a hashed receipt and moves to `S4_SURGEON_ACKNOWLEDGED`.
- **P0-4 honest lanes:** OSD-575 drawer, recorded-non-astronaut M6 replay selector, GOES pfu
  cache-age/not-dose panel; real mode still never invents frames.
- **P0-5 outbox:** habitat delay, rover blackout queue/release, DELIVERED-only ack,
  explicit demo flight-surgeon role switch in the UI, restart-durable packets.
- **P0-6 packaging:** `run_workstation.sh --offline` verified against an existing venv +
  `web/dist`; Dockerfile + compose + healthcheck added (Docker daemon unavailable here, so
  the image was not built in this sandbox). Reset endpoint verified.
- **P1 benchmark:** measured FL/DP artifact rendered in Docs from
  `artifacts/fl_dp_benchmark_results.json`; `--verify` reproduces it byte-for-byte.

Still open: real-browser Playwright E2E (no browser binary in this sandbox), hosted
authentication/authorization beyond demo `X-Role`, CI workflow, and the P1/P2 research or
external-data gates. Verification now: `tests_api` **152 passed + 79 subtests**; full
`PYTHONPATH=src pytest -q` **324 passed / 41 skipped / 207 subtests**; web **48 tests / 10
files**, typecheck and production build clean; HTTP smoke **58/58**; FL/DP `--verify` OK.

---

## Bottom line

**The UI and API demo shell are working; the full end-to-end MVP is not complete.**

Working today:

- Three-view light-theme React UI: Overview, Crew Workstation, ML Architecture & Docs.
- FastAPI single-port launch; 29 API paths plus the SPA catch-all in OpenAPI.
- Deterministic 3-stage gate truth table with safety bypasses, hard ceiling and hold timeout.
- Five labelled simulated scenarios; six-organ demo rule table; staleness decay.
- Three crew tools: demo PVT, manual ONSD caliper/sample upload, keyboard vitals.
- Explicit provenance and real-vs-simulated mode separation.
- Local SHA-256 audit chain with verification; optional JSONL persistence.
- Verified NASA OSD-575 descriptive lab lane; committed, independently verified M6 offline results.

Not complete today:

- The unified workstation does **not** continuously advance telemetry. Scenarios seed a finite
  history; the new UI polls `/api/state` every 15 s. Legacy `/api/stream/step` + SSE exist but
  are not wired into the new three-view UI.
- Case state is process-local. Checks, calibrations, alerts and holds are lost on restart;
  only the audit chain can optionally persist.
- The workflow does not close through a surgeon review/acknowledgement/sync loop in the new UI.
- No trained neural inference, MC-dropout, Flower-based FL comparison, Opacus DP experiment,
  or deployed EVM ledger is in the live path.
- No live astronaut wearable, validated clinical protocol, or clinical/flight qualification exists.

Current live read-only snapshot during this assessment: real-source mode was selected,
`telemetry_mode=NOT_AVAILABLE`, history empty; OSD-575 available; GOES and PhysioNet caches
unavailable in the runtime. This is honest unavailable behaviour, not a crash.

Current verification re-run:

| Check | Result |
|---|---|
| `pytest tests_api -q` | **70 passed** |
| `web npm run test` | **27 passed / 8 files** |
| Prior full Python suite at this commit | 234 passed / 49 skipped / 128 subtests |
| Prior HTTP smoke at this commit | 42/42 |
| Real-browser Playwright run | **Not available / not run** |

## Existing PPT-traceability acceptance: M1–M7

Part A of `REQUIREMENTS-TRACEABILITY.md` defines a narrower MVP than the full ten-slide
concept. Its M1–M7 IDs are **requirements**, not the similarly numbered build milestones:

| Requirement | Current status | What remains / limitation |
|---|---|---|
| **M1 — verified NASA lane** | **Met** | OSD-575 checksum-gated loading and descriptive pre/post comparison exist. Surfacing the rows in the rebuilt web UI is an integration improvement (P0-4), not a failure of the original load criterion. |
| **M2 — registry + reduced channel panel** | **Met, reduced** | The 49-channel registry and display-only channel panel exist in the original desktop/API path. The rebuilt web six-organ view is a separate, explicitly simulated rule demo—not evidence of a validated physiological twin. |
| **M3 — WESAD provenance/terms gate** | **Blocked** | WESAD remains NO-GO; no download or training. Terms, labels, formats, units and exclusions need confirmation and a team use decision. |
| **M4 — reproducible LOPO baselines** | **Met in reduced substitute form** | Build milestone M6 used PhysioNet, not WESAD: n=8, leakage checks, per-class metrics and participant-bootstrap intervals. No HR method beat the training-mean predictor; activity classification improved over majority class. This is not clinical or astronaut validation. |
| **M5 — Flower vs centralised vs local** | **Not implemented** | Identical participant splits, reproducible runs and measured comparison are missing. The toy FedAvg demonstration does not satisfy this requirement. |
| **M6 — separate DP experiment** | **Not implemented** | Threat model, DP training, actual accountant ε/δ, sampling method and `secure_mode` report are missing. This is unrelated to the measured PhysioNet build milestone also called M6. |
| **M7 — claims hygiene** | **Maintained in the rebuilt UI** | Keep simulation, demo-threshold, unavailable-data and no-chain labels; reconcile the source deck/docs before reusing their claims. This does not establish compliance or validation. |

These statuses should not be converted into a percentage complete: the original acceptance
list is narrower than the full concept, and the end-to-end runtime gaps below still matter.

## Implemented code that is only a demo stand-in

| Capability | What actually runs | What it must not be presented as |
|---|---|---|
| Mission telemetry / habitats | Five deterministic scenario formulas and four habitat labels | Live sensors, real habitat data or independent sites |
| Activity / residualization | Per-person activity normalization plus a fixed saturating context model | Calibrated ENMO in g or a fitted physiological residualizer |
| Uncertainty | Split-conformal quantile on simulated residuals, currently α=0.10; epistemic σ is null | Guaranteed coverage, MC-dropout or a validated uncertainty model |
| Organs / triage | Manual measurements, demo cutoffs, staleness decay and deterministic gates | Six trained risk heads, organ coupling or approved clinical protocols |
| Exam selection | Risk-weight × staleness ÷ cost heuristic | The deck's expected-uncertainty-reduction resolver U(m) |
| FL / robustness | One-process toy FedAvg and a simulated cosine-median bit-flip example | Flower, independent data owners, DP or measured Byzantine resilience |
| Audit | Local SHA-256 chain, optional JSONL; Solidity file is reference-only | A deployed EVM ledger, transaction receipts or tamper-proof storage |
| Crew instruments | Demo PVT, synthetic/manual ONSD measurement and keyboard vitals | Validated cognitive testing, automated ultrasound diagnosis or device integration |

## Recommended MVP definition

For a credible hackathon/research MVP, target a **single-machine, explicitly labelled
research demonstrator**, not a flight or clinical product:

> Recorded/simulated telemetry advances continuously → personal baseline and residual gates
> update → stale/uncertain evidence requests a crew exam → the crew completes a tool →
> triage transitions → an alert packet is queued and acknowledged by a demo flight-surgeon
> role → the audit chain survives restart → the browser E2E path passes offline.

Real astronaut sensors, clinical countermeasures, multi-agency FL and formal privacy/flight
claims are outside that MVP unless the external gates below are met.

## Slide-by-slide comparison

| PPT area | Current implementation | Remaining gap |
|---|---|---|
| 1. System overview | FastAPI + React + deterministic gates + local audit | Event-driven continuous bus, trained conformal engine, closed 5-state workflow and federated network are partial or absent |
| 2. Problem framing | Static simulated personal calibration; demo exertion residualizer; manual episodic checks | Adaptive Kalman baseline; real ENMO/CO₂/gravity context; live multi-rate wearable ingestion; real small-cohort FL |
| 3. NASA/CSA/OSDR grounding | OSD-575 verified lab lane; GOES loader; PhysioNet offline lane; WESAD blocked | Correct OSD-570 attribution; no CSA Bio-Monitor/dosimetry data access; no Standard Measures/CIPHER data; GOES flux is not dose |
| 4. Six-layer architecture | Layers 5/6 partly implemented; local audit; toy FL | Layer 1 live bus/Kalman; Layer 2 Flower/Opacus; Layer 3 PyTorch/CNN/EVM; Layer 4 MC-dropout/validated conformal |
| 5. Residualization + conformal | Saturating demo context model; demo split-conformal quantile at α=0.10 | Fitted ENMO/CO₂/respiratory model; α≤0.05 calibration; M=15 MC-dropout; epistemic bound |
| 6. Five-state FSM + resolver | Gate states map to demo triage; heuristic exam ranking | Explicit persisted S0–S4 transitions; post-exam resolution; surgeon sync; uncertainty-reduction resolver; approved protocols |
| 7. Workstation + instruments | Six-node body map; PVT; manual ONSD caliper; vitals form | 1 Hz live display; validated PVT timing; ultrasound probe guidance + 2D-CNN; device adapters; inter-organ coupling model; z-scores beyond heart |
| 8. FL + audit ledger | Four habitat labels; one-process toy FedAvg; cosine-median bit-flip demo; local hash chain | Independent simulated silos; Flower; Opacus accounting; Byzantine evaluation; Hardhat deployment/tests; weights/ε/alert hashes |
| 9. Benchmarks | Measured M6 PhysioNet LOPO results; requested benchmarks labelled NOT_IMPLEMENTED | Reproducible harness for the deck's tasks/splits/metrics or removal of unsupported numbers; no evidence for 0.63/0.89/0.87, 48%→2.9%, 95.6%, 68%, 0.52/0.85 |
| 10. Impact | Clear research prototype and Earth-use narrative | No demonstrated clinical outcome, HIPAA/GDPR compliance, NASA/CSA endorsement or flight readiness |

## P0 — required for a credible end-to-end demo MVP

| ID | Pending work | Why it blocks the loop | Acceptance criterion |
|---|---|---|---|
| P0-1 | **Unified live replay clock + transport** | `running=True` currently does not advance the unified scenario; the chart is a seeded snapshot | Start/pause/reset controls; `t_s` and history advance at 1 Hz without manual `/stream/step`; SSE/reconnect updates gates/chart; gaps and data age remain visible |
| P0-2 | **Persistent case/session state** | Restart loses checks, calibration, alerts and holds; global store is not multi-user isolated | SQLite or equivalent stores subjects/checks/calibrations/alerts/outbox/audit; restart restores the same case; two demo sessions do not overwrite each other; audit verifies after restart |
| P0-3 | **Close the clinical-demo workflow** | Exam results re-run gates, but there is no persisted S0–S4 case lifecycle or surgeon ack/sync UI | Exercise→compensated; stale-eye→exam→freshness restored, with escalation if the simulated CO₂/ONSD finding persists; SPE→surgeon queue→acknowledged receipt; every transition audited; plain Python FSM is sufficient, LangGraph is not required |
| P0-4 | **Connect the honest data lanes to the demo** | OSD-575 is availability-only in the new UI; PhysioNet features are not wired live; GOES is uncached here | Docs/provenance shows verified lab rows; a labelled RECORDED-NON-ASTRONAUT replay can drive the bus; GOES cache/refresh status is visible; real mode never invents frames; lanes never merge |
| P0-5 | **Surgeon outbox / delayed-sync demonstration** | Habitat delay is display-only; no blackout queue or receipt | Store-and-forward outbox survives restart; simulated delay/blackout releases packets later; demo surgeon acknowledgement returns a receipt; no real mission network claim |
| P0-6 | **Deterministic demo reset + packaging** | `run_workstation.sh` exists, but there is no full case-reset endpoint, Dockerfile or CI workflow | Verify the launcher from a clean checkout; reset returns nominal state; pinned dependencies; container/compose healthcheck; offline run after cache/install works |
| P0-7 | **Real-browser E2E and failure-path tests** | Current UI coverage is jsdom + HTTP smoke only | Playwright covers all 3 pages, 5 scenarios, 6 organs, 3 tools, ack/restart/reconnect/API-down/bad upload; zero console errors; CI runs it |
| P0-8 | **Presentation/deck reconciliation + claims guard** | The rebuilt UI is labelled, but the source deck and older status docs contain conflicting or obsolete claims | Presentation uses only measured results or explicitly proposed targets; OSD-570 attribution corrected; demo thresholds not called NASA-STD-3001 limits; no privacy/compliance/endorsement claims; add a regression scan |
| P0-9 | **Minimum access boundary if hosted** | `X-Role` is spoofable and CORS is permissive | Local-only mode is explicit; shared preview requires authentication/authorization, restricted origins and no real PHI; unauthorized role changes fail |

## P1 — reference-deck research parity, after P0

These are buildable as **labelled research/simulation modules**, but are not required to
prove the basic end-to-end crew loop:

1. **Adaptive personal baseline:** Kalman or another reviewed tracker, compared against the
   current static calibration on held-out data; flagged rows never update it silently.
2. **Fitted exertion residualizer:** calibrated ENMO, CO₂ and gravity context; respiratory
   output if supported by data; participant-separated evaluation; no scenario-tuned constants.
3. **HyperionCoreNet + six risk heads:** versioned PyTorch artifact, serving path, input
   schema, latency report and leakage-safe evaluation. Requires defensible labels/data first.
4. **Validated uncertainty stack:** split conformal at the declared α, MC-dropout passes,
   epistemic uncertainty and expected-uncertainty-reduction exam ranking; coverage report.
5. **Flower + Opacus experiment:** simulated participant-group clients, identical LOPO splits,
   local/centralized/federated comparison, actual accountant ε/δ and `secure_mode`; no
   habitat/agency claim unless independent data owners exist.
6. **Cosine-median robustness evaluation:** fault injection across multiple seeds/splits with
   measured metrics, not only the current single bit-flip demonstration.
7. **Ultrasound CNN and probe guidance:** labelled ONSD images, calibration, held-out image
   evaluation and clinical review. Manual caliper remains the honest fallback.
8. **Local Hardhat/EVM audit demo:** contract tests, local deployment, anchoring of round ID,
   weights hash, ε spent and S4 alert hash; clearly local, not a production chain.
9. **Benchmark harness:** one reproducible command producing the requested tables with dataset,
   task, splits, CIs and provenance. Report measured values even if they miss deck targets.
10. **Interop prototypes:** HL7 FHIR packet export and delay-tolerant sync simulation only if
    needed for the demo; real NASA ION-DTN integration is external.

## P2 — external dependencies / not achievable by coding alone

| Gate | What is needed | Current blocker |
|---|---|---|
| Astronaut wearable data | Authorized Bio-Monitor/LSDA or equivalent access, DUA, ethics/IRB conditions | No public continuous astronaut vital-sign source found |
| WESAD | Owner/readme confirmation of labels, formats, units, discarded IDs, terms; team use decision | Gate is NO-GO; nothing downloaded/trained |
| Cabin/radiation context | Verified ppCO₂ and dosimetry time series; validated flux→dose method if dose is claimed | GOES provides pfu, not mGy/day; OSD-570 is not telemetry |
| Clinical protocols | Named authoritative protocol source, version, qualified review, applicable NASA-STD-3001 trace | Current thresholds/actions are demo rules, not treatment guidance |
| Ultrasound/PVT/devices | Hardware, labelled data, timing/image validation, human review | Current tools are manual/demo software only |
| Production multi-site FL / privacy guarantees | Independent data owners, threat model, secure aggregation/accounting review | Current FL is one process on toy data; a separate local DP methods experiment remains possible without agency integration |
| Security/privacy/legal | AuthN/AuthZ, encryption, threat model, privacy/legal assessment | Demo-grade role header; no compliance established |
| Flight/clinical qualification | Formal assurance, verification, validation and authority approval | No qualification evidence in the repository; outside the hackathon MVP |

## Suggested implementation order

1. **P0-1 + P0-2 + P0-3:** live replay, persistence, closed workflow. This turns the demo from
   a snapshot into an end-to-end case.
2. **P0-5 + P0-4:** delayed surgeon sync and honest recorded/lab/context lanes.
3. **P0-6 + P0-7 + P0-8 (+ P0-9 if hosted):** reproducible packaging, browser E2E, claims and
   access boundary.
4. **Choose one P1 research differentiator** — preferably the reproducible FL/DP benchmark or
   the uncertainty stack — rather than partially adding all of them.

## What should not be claimed at MVP

- Real astronaut wearable monitoring or CSA Bio-Monitor integration.
- NASA-STD-3001 compliance, validated clinical cutoffs, diagnosis or treatment advice.
- The deck's F1, false-alarm, coverage, variance-reduction or Byzantine-resilience numbers.
- Differential privacy from FedAvg alone, or any ε/δ without an accountant report.
- On-chain audit while only a local hash chain exists.
- HIPAA/GDPR compliance, NASA/CSA endorsement, clinical validation or flight readiness.
