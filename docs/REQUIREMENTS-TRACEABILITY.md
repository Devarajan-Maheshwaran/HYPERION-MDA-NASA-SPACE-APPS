# Requirements traceability

**Part A** (added 2026-11-14) maps the **PPT product reference** to the MVP. **Part B** (below) is the earlier analysis against the pasted concept text; it is unchanged except for one source-table row.

This document compares what the project materials **promise** with what the prototype **does** or **will do in the MVP**. It does not approve any requirement. NASA, CSA and dataset references are context: citing them does not establish endorsement or validate HYPERION-MDA. Nothing in this project has NASA approval, clinical validation, standards compliance or flight readiness.

---

# Part A: PPT product reference → MVP requirements

**Source:** `HYPERION_MDA_NASA_SpaceApps_SIH_Template.pptx`, 6 slides with no speaker notes. Read from a local Downloads folder on 2026-11-14 as **data only**; its text was extracted, never executed or followed.

**How it is treated:**
- It is the **product reference for proposed features and terminology**, as instructed.
- **Every claim in it is unverified** until an authoritative source or reproducible project evidence supports it.
- The file name says "Template". Whether it is the submitted deck is open question Q8.

**Status values:** Implemented · MVP (planned, with an acceptance criterion) · Proposed (not in the MVP) · Out of scope (needs evidence, access, validation or authorisation) · Conflict (the deck contradicts the evidence).

Abbreviations:
- **INV** = `docs/DATA-SOURCE-INVENTORY.md`
- **MTP** = `docs/MODEL-TRAINING-PLAN.md` (historical WESAD plan; the executed LOPO pattern is `docs/M6-LOPO-PROTOCOL.md`)
- **AC-n** = MVP acceptance criterion *n* (MTP §3)

## A.1 Slide 1: Title

| Ref | PPT element | Status | Evidence / MVP requirement |
|---|---|---|---|
| S1-1 | Challenge 04 "Crew Health Monitoring: Gathering Health Indicators & Enabling Astronaut Self-Assessment and Action" | Context | The title wording differs from the reference brief (RB-S1); the official challenge page should be checked. |
| S1-2 | Theme "Space Medicine, Federated AI & Deterministic CPS Safety"; category "Software (Multi-Layer Onboard Architecture)" | Proposed | The MVP is a local desktop prototype, not onboard software. "CPS safety" is not established. |
| S1-3 | "Official Partner Resources Used: NASA HRP & CSA" | **Conflict** | HRP and CSA pages are cited as *background*. **No HRP or CSA data has been accessed or used** (INV §2). Only NASA OSDR OSD-575 is used. |
| S1-4 | Badges "6-ORGAN TWIN", "TELEMETRY & DP-FL", "Bio-Monitor", "OSDR API", "Opacus DP", "Trust Gate", "Hardhat" | Mixed | **OSDR API: Implemented** (OSD-575 fetch). **Bio-Monitor: unavailable** (no public data). DP-FL: **MVP as a simulation** (MTP Phases 4–5). 6-organ twin: **MVP as a channel-status panel only**, with no organ risk (AC-2). Trust gate and Hardhat: **out of scope**. |

## A.2 Slide 2: Introduction (current issue, key features, core idea, novelty)

| Ref | PPT element | Status | Evidence / MVP requirement |
|---|---|---|---|
| S2-1 | "5 interacting hazards", "20-min communication blackouts", "One-Way Mars Comms Delay 20 MIN" | Context; **Conflict** | The 5 hazards are NASA HRP's *framework* (BIB 1). The delay figure is inconsistent: the deck says **20 min**, the concept text **14 min**. Neither is sourced in the project. **Not a requirement.** |
| S2-2 | "Multi-Modal Fusion: wearables, BP, glucose, temp, sleep, mood & ultrasound" | Partial / Proposed | **Implemented:** the sparse serum CMP values (glucose and others) from OSD-575, as lab samples. **MVP:** WESAD wrist signals, *recorded non-astronaut*, in a separate lane. BP, temperature, sleep, mood and ultrasound: **unavailable**. |
| S2-3 | "Individual Baselines: per-astronaut rolling Z-scores relative to NASA Standard Measures" | Partial; **Conflict** | **Implemented:** per-person *pre-flight* baselines on OSD-575 (descriptive z, unvalidated). **No Standard Measures data** has been accessed (INV §2). "Rolling" doesn't apply to 3 sparse pre-flight points. |
| S2-4 | "Exertion Residualizer (ENMO & cabin CO₂)" | Out of scope | There is no astronaut accelerometer or cabin CO₂ data (INV Q4). |
| S2-5 | "6-Organ Clickable Twin mapping indicators to NASA HRP & CSA physiological risks" | **MVP, reduced** | **AC-2:** a body-region panel of *channels* with status badges (MEASURED-LAB-SAMPLE / RECORDED-NON-ASTRONAUT / SIMULATED / UNAVAILABLE). **No organ risk, scores or thresholds**, and a "not a validated physiological twin" notice. |
| S2-6 | "3-Stage Trust Gate (SQI, activity, uncertainty)" | Out of scope | There's no SQI-labelled astronaut data and no validated uncertainty model. |
| S2-7 | "Guided Self-Exams", "Gamified Routine (Organ Protection Shields & Sol streaks)" | Proposed | They need protocol content from a qualified source (CLIN-1). They aren't in the MVP. |
| S2-8 | "Surgeon Triage Sync: NASA-STD-3001 action packets & SHA-256 audit hashes" | Out of scope / Proposed | Action packets: out of scope (no clinical authority). A local SHA-256 load log is feasible later (Part B, R2); SHA-256 *file verification* already exists. |
| S2-9 | Core idea "Fuses continuous CSA Bio-Monitor streams, NASA OSDR environmental telemetry & episodic self-exams" | **Conflict** | There is no public Bio-Monitor stream (INV §2) and no OSDR environmental telemetry identified. The only real NASA data is a sparse serum lab panel. |
| S2-10 | Workstation view "ENV: [Station 0g] [Spacecraft] [Lunar Base] [Rover]" | Out of scope | No environment-specific data exists. These labels must not be used for simulated FL clients (MTP Phase 4). |
| S2-11 | Novelty 1 "Privacy-Preserving Multi-Habitat FL … without sharing raw crew medical records" | **MVP as a simulation**; **Conflict** | **AC-6:** a Flower simulation on WESAD participants, not habitats and not crew. FL alone gives **no formal privacy guarantee** (MTP Phase 5). |
| S2-12 | Novelty 2 "Exogenous Residualization & Active Exams" | Out of scope | As S2-4, and the exam-ranking formula is unvalidated. |
| S2-13 | Novelty 3 "Zero-Hallucination Deterministic Triage … LangGraph … Hardhat" | Out of scope | No triage protocols, no LLM component and no ledger in the MVP. "Zero-hallucination" is an unverifiable claim. |

## A.3 Slide 3: Technical approach

| Ref | PPT element | Status | Evidence / MVP requirement |
|---|---|---|---|
| S3-1 | Stack: PyTorch, scikit-learn, Flower, Opacus, Pandas/NumPy | **MVP (subset)** | scikit-learn/numpy/scipy for baselines (installed). Flower (`[fl]` extra) and PyTorch + Opacus (`[dp]` extra) are **not installed**, and Python 3.14 support is **unverified** (INV Q7). |
| S3-2 | Stack: FastAPI, LangGraph, Hardhat/Solidity, React+TS, Docker | Proposed / Out of scope | The MVP keeps the existing Tkinter desktop app; no service, ledger or LLM layer. |
| S3-3 | "Benchmarks … on NASA OSDR + CSA + WESAD streams" | **Conflict** | There are no CSA streams and no OSDR wearable streams. **The MVP model task uses WESAD only**, labelled non-astronaut (MTP §0). OSD-575 is never used for training (AC-3). |
| S3-4 | Inputs: "Wearable (1Hz): HR, HRV, Resp, Temp, EDA, ENMO(g)" | **MVP (non-astronaut)** | WESAD wrist BVP/EDA/temperature/accelerometer at their native rates (64/4/4/32 Hz per UCI, to verify), shown as RECORDED-NON-ASTRONAUT. No astronaut equivalent exists. |
| S3-5 | Inputs: manual BP, glucose, core temp, sleep, H₂O; click/cam mood, PVT, ultrasound | Unavailable / Out of scope | Glucose exists only as sparse OSD-575 lab values; the rest are unavailable. |
| S3-6 | "NASA & CSA context: 5 RIDGE hazards (u_t): CSA Rad mGy/day, cabin ppCO₂, gravity, isolation, distance; NASA OSDR (OSD-570)" | **Conflict** | **OSD-570 is PBMC single-cell sequencing**, not cabin or radiation telemetry (verified, INV §1). No hazard time series is available. |
| S3-7 | "Adaptive baseline z_{i,t}; staleness mask τ" | Partial | Descriptive z on OSD-575 pre-flight baselines is implemented. A staleness display is possible later (Part B, R3), with **no** decay thresholds. |
| S3-8 | "Exertion residualizer r_t" | Out of scope | As S2-4. |
| S3-9 | "Baselines (scikit-learn): RandomForest & MLP (local vs centralized)" | **MVP** | **AC-5:** the majority-class and logistic-regression baselines (plus an optional RF), local-only vs centralised vs FL-simulation, on **identical leave-one-participant-out splits**. |
| S3-10 | "Proposed (PyTorch): Opacus-safe LayerNorm multi-head residual net; 2D-CNN ONSD" | Proposed / Out of scope | The MVP uses a tiny model for the DP experiment only. No ONSD (no images). |
| S3-11 | "6 organ risk heads ŷ ∈ [0,1]⁶" | Out of scope | No labels, data or clinical validation. |
| S3-12 | Stage-2 gate "Raw HR > 125 bpm AND ENMO > 0.22g" | Out of scope; **thresholds unverified** | No source in the project. |
| S3-13 | Stage-3 "split conformal + MC-dropout; τ < 0.5; U(m)" | Out of scope | Unvalidated thresholds and formula. |
| S3-14 | FL: "4 non-IID silos (Station, Mars transit, base, rover); Opacus DP-SGD clip C=1.0; Rényi accountant; cosine-median filter" | **MVP reduced**; **Conflict** | Simulated clients are WESAD participant groups; **no silos and no habitat claims** (AC-6). DP is a separate experiment that reports the accountant actually used (Opacus defaults to `prv`, with `rdp` available) and ε at a stated δ (AC-7). C and σ are design parameters, not results. The cosine-median filter is not in the MVP. |
| S3-15 | "Zero Raw Biometric Sharing: Complies with U.S. Privacy Act & international agency medical confidentiality" | **Conflict / unsupported** | No legal or compliance assessment exists. It **must not be claimed.** |
| S3-16 | Backend "FastAPI 1Hz streams", "LangGraph NASA-STD-3001 router", "HealthAudit.sol" | Out of scope | — |
| S3-17 | GUI "clickable 6-system body SVG, 3 instruments, gamified tracker" | MVP reduced / Out of scope | See S2-5; the instruments are out of scope. |
| S3-18 | "Tiers 1–3 … NASA-STD-3001 protocol"; "evaluate_all.py benchmarks … EVA false-alarm reduction" | Out of scope / **MVP reduced** | There are no triage tiers. One evaluation script is planned (AC-5), with **no** EVA false-alarm claim (no such data). |

## A.4 Slide 4: Feasibility and viability

| Ref | PPT element | Status | Evidence / MVP requirement |
|---|---|---|---|
| S4-1 | "PyTorch LayerNorm MLP ~4.2k params"; "inference & trust gate in milliseconds on crew tablets" | Unverified | No model or measurement exists. **Not to be claimed.** |
| S4-2 | "Aligned directly with NASA Spaceflight Standard Measures & CIPHER" | **Conflict** | There is no access to Standard Measures or CIPHER data (INV §2). |
| S4-3 | "Offline batch FL respects … 20-min Mars comms delays" | Out of scope | FL is a single-machine simulation only. |
| S4-4 | "100% reproducible pipeline using public NASA OSDR records (OSD-570 / ISS cabin CO₂ & rad), CSA dosimetry/vascular science, and de-identified WESAD" | **Conflict** | OSD-570 is not telemetry; there is no CSA data access. **The MVP reproducibility claim is limited to:** OSD-575 (SHA-pinned) plus WESAD (SHA-pinned after the terms gate) (AC-4, AC-5). |
| S4-5 | "Opacus bounds privacy loss (ε, δ); Hardhat logs only SHA-256" | **MVP reduced** | Opacus bounds **record-level** loss only under its assumptions; it is not participant-level, and FL alone gives nothing (MTP Phase 5). No Hardhat. |
| S4-6 | "Baseline-first engineering; every module unit-tested" | **MVP** | AC-5: majority and logistic-regression baselines come first; leakage tests are required (MTP Gate 2). |
| S4-7 | Challenges: EVA false alarms, guided exams, small crews (DP-FL), radiation glitches / LLM hallucination | Out of scope / MVP reduced | Only the small-cohort concern is touched, and only as a WESAD simulation. |
| S4-8 | Mission relevance: ISS/Gateway, Mars transit, Artemis bases; Earth spinoff (Arctic clinics, ICU) | Context | These are goals, not demonstrated outcomes. |
| S4-9 | Phase 1 "OSDR + CSA + WESAD ingestion → sklearn → Flower/Opacus DP-FL → trust gate → 6-organ UI" | **MVP reduced** | MTP Phases 1–6: OSDR (OSD-575) + WESAD → baselines → FL simulation → separate DP experiment → twin channel panel. **No CSA data and no trust gate.** |
| S4-10 | Phase 2 "HERA / CHAPEA & CSA polar testbeds, live Bluetooth Bio-Monitor & handheld ultrasound" | Out of scope | Needs authorisation, hardware and ethics approval. |
| S4-11 | Phase 3 "HL7 FHIR packets & NASA ION-DTN" | Out of scope | — |

## A.5 Slide 5: Impacts and benefits

| Ref | PPT element | Status | Evidence / MVP requirement |
|---|---|---|---|
| S5-1 | "Enables astronauts to gather and evaluate multi-modal indicators … across all 5 RIDGE hazards" | Unsupported | The MVP shows sparse lab values and data availability; it does not evaluate health. |
| S5-2 | "Prevents alarm fatigue …"; "explains why an exam is needed" | Unsupported / Out of scope | No alarm system or exam guidance exists. |
| S5-3 | "Improve shared diagnostic models via FL while keeping raw records local" | **MVP reduced** | A simulation only; no diagnostic model; FL's privacy is not assumed. |
| S5-4 | "Tamper-evident SHA-256 audit receipts for Flight Surgeons" | Out of scope | File-integrity SHA-256 exists; there are no audit receipts. |
| S5-5 | Impact/effort quadrants (trust gate, 6-organ twin, DP-FL, Hardhat) | Mixed | See S2-5, S2-6, S2-11 and S2-13. |
| S5-6 | Capabilities "5 RIDGE · 6 ORGANS · 4 SILOS · 3 GATES · 0 RAW PII · 24×7" | **Conflict / unsupported** | None is demonstrated. "0 RAW PII" and "24×7" are unverifiable claims. |
| S5-7 | Alignment: NASA HRP/ExMC, CSA deep-space healthcare ("integrates CSA radiation dosimetry, Bio-Monitor … Vascular/Insulin Resistance science"), UN SDGs | **Conflict** | Nothing from CSA is integrated. Alignment statements are context, not endorsement. |
| S5-8 | Goal "evaluate their own health indicators accurately … act early to prevent critical medical events" | Unsupported | No accuracy or clinical outcome has been measured. |

## A.6 Slide 6: Research and references

| Ref | PPT element | Status | Evidence / MVP requirement |
|---|---|---|---|
| S6-1 | HRP findings: "cabin CO₂ (>2.5–4.0 mmHg) drives SANS … ONSD ≥ 5.8 mm; bone 1–1.5%/mo …" | **Unverified** | These need specific cited sources. **Not requirements**; no thresholds are implemented. |
| S6-2 | "CSA ISS Vascular & Metabolic Findings (Hughson et al.) … fasting glucose 100–125+ mg/dL" | **Unverified** | The citation has not been checked in this project. |
| S6-3 | "CSA Bio-Monitor defines non-invasive continuous ECG, PPG, Resp, Temp & Accel tracking" | Partially consistent | CSA's page lists heart activity, blood pressure, breathing, skin temperature, SpO₂ and activity, and no public data (INV §2). |
| S6-4 | Existing systems table (CMO-DA, ATOMS, ALISSE: "static Earth cutoffs", "generative text risk") | **Unverified** | No sources in the project; don't present as fact. |
| S6-5 | References 1–5 (NASA HRP hazards/risks/ongoing research; two CSA URLs) and "6. NASA OSDR (OSD-570 / ISS Env API), NASA-STD-3001 & WESAD" | Partial; **Conflict** | HRP pages are cited in BIB. The two CSA URLs (including "Feb 2026") are **not checked**. The "OSD-570 / ISS Env API" attribution conflicts with the record. |
| S6-6 | **"Grounded NASA-STD-3001 & CSA Indicator Cutoffs"**: glucose 70–99 / 100–125 / ≥126 mg/dL; ONSD <5.0 / 5.0–5.7 / ≥5.8 mm; cabin ppCO₂ <2.5 / 2.5–3.9 / ≥4.0 mmHg; BP <125/80 / ≥140/90 | **Out of scope; unverified attribution** | These values have **not** been traced to NASA-STD-3001 or CSA documents in this project, and they must not be described as "grounded" in them. **No clinical cutoff is implemented, and none will be in the MVP** (AC-8). The OSD-575 lab's own reference ranges are also deliberately unused. |
| S6-7 | Formulas (residualizer, staleness, exam priority, DP-SGD aggregation) | Proposed | Only standard DP-SGD (via Opacus) appears in the MVP, as a separate experiment. |
| S6-8 | Prior-art list (Hughson 2016, Lee 2020, ExMC CMO-DA, ATOMS, ALISSE, Brahms, Ax-4 TESH) | **Unverified** | Not checked in this project. |
| S6-9 | Next steps "benchmark validation → HERA/CSA analog → ExMC HL7-FHIR & ION-DTN" | Out of scope | Needs authorisation. |

## A.7 Conflicts summary: deck vs current evidence

1. **OSD-570** is cited as cabin CO₂ / radiation / environment data (S3-6, S4-4, S6-5). It is **PBMC single-cell sequencing** (verified).
2. **CSA Bio-Monitor streams and CSA dosimetry/vascular data** are described as used or integrated (S1-3, S2-9, S4-4, S5-7). There's **no public access**, and nothing is integrated.
3. **NASA Standard Measures / CIPHER** "alignment" (S2-3, S4-2): **no data access.**
4. **Clinical cutoffs** described as "grounded" in NASA-STD-3001/CSA (S6-6): **untraced; not implemented.**
5. **Privacy:** "Complies with U.S. Privacy Act", "0 RAW PII", FL as privacy-preserving (S3-15, S5-6, S2-11). There is **no assessment**; FL alone offers no formal guarantee, and Opacus DP is record-level under its assumptions.
6. **Multi-habitat FL with 4 silos** (S2-11, S3-14, S5-6): **simulation only**; there are no independent data owners.
7. **Comms delay:** 20 min (deck) vs 14 min (concept text); neither is sourced (S2-1).
8. **Performance and size claims** (~4.2k params, millisecond inference, EVA false-alarm reduction; S4-1, S3-18): **no evidence.**

## A.8 MVP requirement list, traced to the PPT

| MVP req | Traces to | Acceptance |
|---|---|---|
| M1 NASA lane: OSD-575 verified load and descriptive pre/post comparison | S2-2, S2-3, S3-7, S4-4 (reduced) | AC-1 (**met**) |
| M2 Signal registry and wearable-style twin channel panel (4 statuses; no risk) | S1-4, S2-5, S3-17 | AC-2, AC-3 |
| M3 WESAD provenance and terms gate | S3-3, S3-4, S4-4 | AC-4 |
| M4 Reproducible preprocessing and LOPO baselines with per-class metrics and CIs | S3-9, S4-6, S3-18 (reduced) | AC-5 |
| M5 Flower simulation vs centralised vs local on identical splits | S2-11, S3-14, S5-3 (reduced) | AC-6 |
| M6 Separate DP experiment with threat model and accountant report | S3-14, S4-5 (reduced) | AC-7 |
| M7 Claims hygiene across UI and docs | S3-15, S5-6, S6-6 and all conflicts | AC-8 |

> **Numbering note (2026-11-15).** The "MVP req" IDs M1–M7 in this table are PPT-traceability requirements. They are **not** the build milestones named elsewhere in the docs: M2 channel panel, M5 PhysioNet recorded lane, M6 PhysioNet LOPO baselines.
>
> **Status by requirement:**
> - **M4 (LOPO baselines with per-class metrics and CIs):** satisfied in reduced form by build milestone M6. It used **PhysioNet Wrist PPG**, not WESAD (WESAD gate NO-GO), with participant-bootstrap intervals; see `docs/M6-RESULTS-SUMMARY.md`.
> - **M3:** blocked (WESAD NO-GO).
> - **M5 and M6** (Flower vs centralised; DP): not implemented.

---

# Part B: earlier analysis against the pasted concept text (Concept Sections 1–10)

Prepared 2026-11-14 against the code in `src/hyperion_mda/` and the tests in `tests/` as they were on that date. Revised the same day so that it references **Concept Sections 1–10** instead of slide numbers.

This document compares what the project materials **promise** with what the prototype **does**. It is an assessment of project material. It does not approve any requirement. Listing a capability here does not mean the team has decided to build it. NASA, CSA and other references are context: citing them does not establish endorsement and does not validate HYPERION-MDA. Nothing in this project has NASA approval, clinical validation, or flight readiness.

> **Revision, 2026-11-14 (OSD-575 candidate):**
> - The DATA-1 gate is now met for **one** dataset only: NASA OSDR **OSD-575** serum CMP. Its metadata was inspected, its licence status recorded (none stated, so **neither the raw CSV nor any derived OSD-575 measurements are tracked in git** — only the provenance manifest), and the file pinned by SHA-256. It is used for a descriptive pre-flight vs post-flight comparison; see `docs/OSDR-OSD575-DATA.md`. The tracked derived outputs under `experiments/m6/outputs/` come from the openly licensed PhysioNet dataset, not from OSDR (`docs/DATA-SOURCE-INVENTORY.md` §3c).
> - OSD-570 and OSD-571 were checked and are **not** telemetry. WESAD is terrestrial lab data and is not used.
> - Everything else under DATA-1, CLIN-1, HW-1, INT-1, SEC-1 and QUAL-1 (federated learning, ledger, clinical workflows, ultrasound, sensors) remains **not implemented**.

## 1. Sources assessed

| Code used below | Source | Availability and notes |
|---|---|---|
| — | Submitted HYPERION PowerPoint | Part B was written when **no deck was available**; its slide-free mapping is kept as it was. The PPT product reference (`HYPERION_MDA_NASA_SpaceApps_SIH_Template.pptx`) is mapped in **Part A** above. Whether that file is the submitted deck is open (INV Q8). |
| — | `reference-material/Original-Reference-Slides.pdf` | Present, but it is **not** the HYPERION deck. Its embedded title is "AI - Based Cyber Threats detection in Unidirection IP Traffic.pptx" (Canva export, 6 pages). `reference-material/01-HYPERION-Project-Brief.md` supplies the six-slide narrative format. No HYPERION claims are taken from it. Its page images could not be rendered here, so this identification relies on the file's metadata. |
| **Concept §1 … Concept §10** | **Concept Sections 1–10.** Two inputs: (a) the section summary the team supplied on 2026-11-14, which defines the section structure; (b) `docs/HYPERION-MDA-CONCEPT-AS-PROVIDED.txt`, the full pasted concept text, organised into the same 10 parts. Section *n* of the summary corresponds to part *n* of the text. | The section summary gives the scope of each section. The concept text supplies the specific wording, numbers and thresholds quoted below. Where the two differ in emphasis, the difference is recorded in §3.0, not resolved by assumption. |
| **RB-S1…RB-S6** | `reference-material/01-HYPERION-Project-Brief.md` | The bounded six-slide narrative, with wording rules. |
| **RA** | `reference-material/02-Architecture-and-Validation.md` | Evidence labels, proposed architecture, hypotheses and the claims table. |
| **PB / AR / VP / BIB** | `reference-material/01-HYPERION-Project-Brief.md`, `docs/ARCHITECTURE.md`, `reference-material/02-Architecture-and-Validation.md` (validation plan), `docs/RESEARCH-BIBLIOGRAPHY.md` | Retained narrative, architecture and validation references. |
| **Code** | `src/hyperion_mda/`, `tests/`, `docs/CSV-SCHEMA.md`, `docs/IMPLEMENTATION-STATUS.md` | What the prototype actually does. |

**Notation:** "Concept §n" always means Concept Section *n*. A bare "§n" refers to a section of *this* document. "RA §4" refers to section 4 of `02-Architecture-and-Validation.md`.

## 2. Status definitions

- **Implemented**: present in the code and covered by tests in `tests/`. This means software verification on synthetic data only.
- **Partially implemented**: part of the capability exists. The gap is stated.
- **Proposed**: a design intent with no code. It could be built and checked as software.
- **Unsupported by evidence**: a claim, number or reference that the project does not support with reproducible evidence (data, code, method, results).
- **Outside current prototype**: needs external data, hardware, clinical authority, or formal qualification that a desktop CSV demo cannot provide.

An item can be both *Unsupported* and *Outside*. Where that applies, the table shows both.

**Acceptance checks** describe how *software behaviour* would be verified if the team decides to build an item. Passing one is never clinical validation. For items that are *Outside*, the check is replaced by a **gate**: the evidence that must exist before the item could even become a requirement.

Two further distinctions are kept throughout:
- **Demonstrated feature vs proposed capability.** *Demonstrated* means only the items marked Implemented (or the implemented part of a Partially implemented item). Everything the concept describes beyond that is *proposed* at most.
- **Reported result vs reproducible evidence.** The concept *reports* results (§4 below). The project holds no data, code, configuration or logs that could reproduce any of them. Only the prototype's own software tests (`tests/`) count as reproducible evidence, and they verify software behaviour on synthetic inputs, nothing more.

---

## 3. Traceability by area

### 3.0 Concept section map and recorded contradictions

| Concept section | Main content | Traced items | What is demonstrated today | Contradictions or tensions recorded |
|---|---|---|---|---|
| **§1 System overview** | An event-driven onboard telemetry bus, personalised analysis, a five-state workflow, and a federated habitat network. | TEL-1, BAS-1/2, WF-1, PRV-1, REF-2 | CSV import, explicit personal baselines, and a descriptive score. **No bus, no workflow, no federation.** | (a) The section summary calls the federated network *proposed*, but the concept text presents the system as already "enabling astronauts to self-assess, perform guided diagnostics, and act on health risks". That is a capability claim with no demonstration behind it. (b) The concept's challenge name ("Challenge 4: Crew Health Monitoring") differs from the reference brief's ("Create Health Monitoring Software for Astronauts on Space Missions"); see REF-2. |
| **§2 Operational gaps** | Changing physiology; mission workload and environmental context; continuous vs occasional measurements; small, privacy-sensitive cohorts. | BAS-1, CTX-1/2, TEL-1/5, PRV-4, WF-4, IMP-3, §4 physiology figures | The gaps are presented as *motivations*. The prototype addresses part of the first (personal baselines) and the third (mixed-rate CSV rows). | The concept states physiology figures (~15% plasma loss, 1.5%/month bone loss) and says static Earth cut-offs "cause high false-positive rates", without any source in the project (IMP-3, §4). `reference-material/01-HYPERION-Project-Brief.md` treats such numbers as claims needing independent evidence. |
| **§3 Research grounding** | NASA HRP hazards and risks, Standard Measures and CIPHER; CSA Bio-Monitor, radiation, vascular and metabolic research; NASA OSDR; WESAD. | REF-1, DATA-1, INT-1, BAS-3, CTX-3 | **None of these sources is used by the code.** The CSV sample is synthetic. | (a) The concept calls the design "100% grounded", but BIB and RA treat these as context only, with no data access or integration (REF-1). (b) It encodes the HRP hazards as a numeric vector, but BIB describes them as a framework with no measurable components defined (CTX-3). (c) WESAD is a terrestrial dataset and is not astronaut data (DATA-1). |
| **§4 Six-layer architecture** | Workstation UI; deterministic workflow; conformal/uncertainty layer; multimodal inference; privacy-preserving federated learning; asynchronous telemetry with personal baselines. | INS-5, WF-1, UNC-3/4/5, PRV-1/2, AUD-1, TEL-1/2/3/4, BAS-1/2/4 | Only a desktop UI (table, static chart, details panel), CSV ingestion and explicit baselines. **Layers 2 to 5 have no code.** | (a) The concept calls the workflow *deterministic* but names LangGraph, which is generally an agent-orchestration framework. The concept itself (§2) warns about LLM-assistant risk. Determinism would have to be shown in a design (WF-1). (b) Its baseline is an *adaptive Kalman tracker*; the code uses *explicitly labelled baseline rows*, so they are not the same mechanism (BAS-1 vs BAS-2). (c) It describes "real-time 1 Hz oscilloscopes"; the code shows a static view of imported data (INS-5). |
| **§5 Analysis engine** | Context-adjusted residuals, split conformal calibration, MC-dropout uncertainty. | CTX-2, CTX-4, UNC-1/2/3/4 | A descriptive z-score against explicit baselines, with a demo-only \|z\| ≥ 2.5 flag. | The concept's residualizer and conformal gate are not implemented. The prototype's z-score is **not** a stand-in for them and must not be presented as one. |
| **§6 Five-state workflow** | Nominal monitoring, sensor-quality issue, context-compensated reading, further measurement needed, protocol-based review. | WF-1/2/3, TEL-6, CTX-4 | **None.** Sensor quality is handled only through the CSV `quality` label, which excludes rows from baselines. | The section summary calls the last state "protocol-based review". The concept text names it `VERIFIED_CLINICAL_PROTOCOL` and says it "triggers NASA-STD-3001 countermeasure", which is a clinical action rather than a review. This document treats only a *non-clinical* review workflow as buildable (WF-1). The rest is gated on clinical review (WF-3). |
| **§7 Diagnostic instruments** | Ocular ultrasound, psychomotor vigilance testing, point-of-care metabolic/hemodynamic measurements. | INS-1/2/3/4 | **None.** | The README excludes "ultrasound analysis" and "validated cognitive testing". The concept presents both as embedded instruments, with thresholds (ONSD ≥ 5.8 mm, PVT > 350 ms) that are unverified (§4). |
| **§8 Privacy and audit** | Federated learning across four environments, differential privacy, Byzantine filtering, a cryptographic ledger. | PRV-1/2/3/4, AUD-1/2/3 | No network code (OFF-1). No privacy or audit mechanism is implemented. | The on-chain ledger conflicts with the project rule against network transmission of health data (AUD-1). A stated (ε, δ) is not a privacy guarantee without reviewed accounting (PRV-1). |
| **§9 Reported benchmarks** | F1 scores, false-alarm rates, conformal coverage, uncertainty reduction, resilience figures. | §4 table | **None reproducible.** | Every figure is a *reported result* with no reproducible evidence in the project. "+24%" is ambiguous: 0.63 → 0.87 is +0.24 absolute, about +38% relative (§4). |
| **§10 Intended impact** | Deep-space crew support and possible Earth applications. | IMP-1/2, PRV-3, OFF-2 | **None.** | The concept says crews "execute verified … countermeasures", but nothing has been verified (IMP-1). It mentions HIPAA/GDPR suitability with no compliance assessment (PRV-3). The reference brief (RB-S5A) says impacts are "goals, not demonstrated outcomes". |

**Contradictions between the concept and the current code or docs, in brief:** the baseline mechanism differs (Kalman vs explicit labelled rows); the display differs (live 1 Hz vs static); the concept's onboard instruments and its validated cognitive testing are excluded by the README; the ledger conflicts with the no-network rule; the concept's "verified" and "grounded" language conflicts with VP's claims gate and BIB's caveats. In each case this document records the code's actual behaviour as the demonstrated state and the concept's version as proposed or unsupported.

### 3.1 Telemetry ingestion and data quality

| ID | Source | Requirement / claim (plain language) | Status | Acceptance check (if built) | Dependencies |
|---|---|---|---|---|---|
| TEL-1 | Concept §4 (Layer 1), Concept §2 | An asynchronous bus that takes continuous wearable streams (~1 Hz) and occasional measurements (glucose, BP, ultrasound, PVT) at different rates. | **Partially implemented.** CSV *file* import accepts rows at any rate or time spacing, but there is no live bus, streaming or device input. | Import one synthetic CSV that mixes a 1 Hz series with occasional rows. Every row is kept and sorted by UTC; there is no resampling or filling-in; a per-series count and time span is shown. | Live input needs device APIs and an interface specification (see INT-1). |
| TEL-2 | RB-S2B, RA (data and safety design), AR (design rules) | Each record carries value, unit, timestamp, source and quality. Malformed data is reported, never silently repaired. | **Implemented** for the CSV schema: required columns, numeric values must be finite, timestamps need a UTC offset, `record_type`, quality labels, readable file errors (`docs/CSV-SCHEMA.md`, `tests/test_engine.py`). | *Already met:* the existing test classes `RowValidationTests`, `FileErrorTests`, `TimestampTests`. | None for synthetic data. |
| TEL-3 | RA (data and safety design): "Convert units explicitly; reject or quarantine… unknown units" | Units are checked, and never guessed or converted silently. | **Implemented (R1).** An exact, case-sensitive allow-list of signal–unit pairs (`SUPPORTED_SIGNAL_UNITS`), limited to the pairs in the synthetic sample. Other pairs are flagged, kept visible and excluded from scoring. No conversion exists. | *Met by* `SupportedPairTests` in `tests/test_engine.py`: supported pairs scored; `BPM`, `beats/min`, `Hz`, unknown signal and wrong pairing all flagged and unscored; values and units unchanged. | Adding pairs, or any conversion table, needs a team decision and a cited source for factors. |
| TEL-4 | RA ("missing/stale/duplicate") | Duplicate readings are detected. | **Implemented (R1).** Key: subject + signal + absolute instant (offset-aware; unit **not** in the key). Every row in a group is flagged, kept visible and excluded from scoring. | *Met by* `DuplicateReadingTests`: pairs and larger groups, equal instants with different offsets, same instant in different units, duplicate observations, non-duplicates (different subject, signal or instant), invalid timestamps never matched. | None. |
| TEL-5 | RB-S2B, RA ("Show missingness and stale values") | Missing or stale data is made visible. | **Partially implemented.** Invalid timestamps are flagged; the chart lists rows it can't plot; rows that fail validation are reported. But there is no indicator of time since the last reading. | For each series, show how long ago the last valid reading was, relative to a reference time the user chooses. No imputation. Tested with a fixed reference time. | Any "stale" threshold must be a user setting labelled as non-clinical. |
| TEL-6 | Concept §6 (S1 `SENSOR_SEU_ISOLATED`), Concept §3 (radiation filtering of single-event upsets, SEUs) | ECG motion artifacts and radiation bit-flips are detected and blocked from corrupting baselines. | **Unsupported by evidence / Outside.** No artifact detector exists. Only the source `quality` label stops a row from entering a baseline. | **Gate:** labelled artifact data, sensor specifications, and an evaluated detector. Until then, the existing quality-label exclusion is the only mechanism. | Artifact-labelled data; CSA dosimetry data access (unverified); review. |

### 3.2 Personal baselines

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| BAS-1 | AR ("Do not let flagged values silently redefine an individual's baseline"), RB-S3B | Each person has their own baseline, and observations or flagged values never change it. | **Implemented.** A baseline uses only explicitly labelled `baseline` rows with accepted quality, the same subject, signal and unit, and a valid timestamp **strictly before** the observation. It needs at least 2 readings and a non-zero spread; observations are never added (`engine.py`, `tests/test_engine.py`). | *Already met:* `BaselineSeparationTests`, `TemporalEligibilityTests`, `InsufficientBaselineTests`. | None. |
| BAS-2 | Concept §4 (Layer 1) | An adaptive per-astronaut Kalman tracker for the baseline mean and covariance. | **Proposed** method. Not implemented, and no evidence of benefit. | If built as an experimental option: on a synthetic series with a known drift, the output is reproducible with documented parameters; flagged or observation rows never update the state; the existing explicit baseline stays available beside it for comparison. | A method review is needed. Tuning on real longitudinal data is Outside (DATA-1). |
| BAS-3 | Concept §3 (CIPHER, Spaceflight Standard Measures) | Uses CIPHER longitudinal baselines and the Standard Measures. | **Unsupported by evidence / Outside.** The project only names them; no data access is established. | **Gate:** specific study records, data-use terms and variable definitions confirmed (VP stage 2). | Data access and licensing. |
| BAS-4 | Earlier review note | An optional maximum age for baseline readings. | **Proposed.** Currently any earlier reading qualifies, however old. | A configurable maximum age, **off by default**, labelled as a demo setting. Tests cover readings just inside and just outside the limit. | The default value is a team decision and must not be presented as clinical. |

### 3.3 Mission context

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| CTX-1 | RB-S2B ("activity-aware"), RA | Activity and mission context is recorded with each reading. | **Partially implemented.** A free-text `context` column is shown in the table, but it is not used in scoring or charting. | Optionally, a fixed list of context values. Unknown values are shown exactly as written. The chart can mark points by context, and scores are unchanged unless a separate decision is made. Tested. | The context vocabulary is a team decision. |
| CTX-2 | Concept §5 (Step 1), Concept §2 | "Exogenous load residualization": subtract the heart-rate and breathing effects of exertion (ENMO), cabin ppCO₂ and gravity before judging anything. | **Unsupported by evidence.** As a method it is **Proposed**. | Experimental, synthetic data only: on a series built with a known added load term, the residualizer recovers that term within a tolerance stated beforehand, on held-out synthetic data with a fixed seed. Raw and residual values are always shown side by side and labelled experimental. | Real ENMO and ppCO₂ data, a validated load model, and physiological review (DATA-1, CLIN-1). |
| CTX-3 | Concept §3 | NASA's five HRP hazards encoded as a 5-number vector [Radiation, Isolation, Distance, Gravity, Environment]. | **Unsupported by evidence.** BIB 1 describes the hazards as a *framework*. No measurable quantity or data source is defined for terms such as "Isolation" or "Distance". | **Gate:** a documented definition, units and source for each component. Without that, it is not buildable as a requirement. | Definitions and data sources. |
| CTX-4 | Concept §6 (S2) | Exertion is recognised when ENMO > 0.22 g, which suppresses cardiac alarms. | **Unsupported by evidence** (threshold, see §4). Alarm suppression is **Outside**. | **Gate:** cited derivation or evaluation of the threshold, plus clinical review of suppression logic. | CLIN-1, DATA-1. |

### 3.4 Uncertainty and anomaly analysis

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| UNC-1 | AR (current prototype) | A transparent statistic comparing each observation with its baseline. | **Implemented** as a descriptive z-score, for demonstration only. The illustrative flag is \|z\| ≥ 2.5, defined once as `DEMO_FLAG_ABS_Z`. **The 2.5 is not a clinical threshold.** | *Already met:* engine tests, plus the flag constant shared by the calculation and the UI. | None. |
| UNC-2 | RB-S2B ("surface uncertainty"), RA | Uncertainty is made visible. | **Partially implemented.** The score basis shows the baseline count, mean and SD, and says why a score is absent. There are no intervals. | The baseline count and SD are shown in the details panel (already met). Any interval added later must state its method and assumptions in the UI. | None. |
| UNC-3 | Concept §4 (Layer 4), Concept §5 (Step 2) | Split conformal prediction with α ≤ 0.05 (95% coverage). | **Proposed** method. Coverage is **Unsupported** (see §4). | Experimental, on synthetic exchangeable data: a fixed-seed calibration/test split, empirical coverage reported with its uncertainty, and the method and assumptions documented. No coverage claim is made for real crew data. | A model to wrap; real calibration data is Outside (DATA-1). |
| UNC-4 | Concept §4, Concept §5 | Monte-Carlo dropout with M = 15 passes for an epistemic uncertainty bound. | **Outside.** It needs a trained neural model and data. | **Gate:** a trained model, data provenance and an evaluation plan (VP stage 3). | DATA-1, ML-1. |
| UNC-5 | Concept §3, Concept §4 (Layer 3) | A PyTorch multi-head network with 6 coupled physiological "risk heads" (SANS, cardiovascular, immune/radiation, metabolic, musculoskeletal/renal, behavioural/circadian). | **Outside / Unsupported by evidence.** There is no model, no labels and no training data. | **Gate:** labelled outcome data for each head, a leakage-safe split (by subject and time), and expert review of label definitions. | DATA-1, CLIN-1. |
| UNC-6 | RA (hypotheses 1–3) | Compare fixed-threshold, personal-baseline and context-aware flagging on the same data. | **Proposed** research harness. **No result exists.** | A harness runs all variants on the same synthetic scenarios and reports flag counts per scenario, labelled as simulation. It has no sensitivity, specificity or F1 unless real labels exist. | Real comparison needs DATA-1. |

### 3.5 Guided workflows

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| WF-1 | Concept §6, Concept §4 (Layer 5) | A 5-state deterministic clinical state machine, S0 Nominal through S4 Verified Clinical Protocol, built with LangGraph. | **Outside** as clinical logic. **Proposed** only as a non-clinical data-review workflow. Note: LangGraph is generally an agent-orchestration framework. The concept's claim that the state machine is "deterministic" would need checking against an actual design. | Non-clinical version: states such as *unreviewed / reviewed / needs re-measurement (user-chosen)*. Transitions are deterministic and fully unit-tested; every transition is written to the audit log (AUD-3); **no medical guidance text**. | Clinical states need CLIN-1 and an approved protocol source (PB pillar 3). |
| WF-2 | Concept §6 (S3) | An "Active Observable Resolver" ranks missing exams by U(m) and launches guided procedures. | **Unsupported by evidence / Outside.** It depends on validated epistemic estimates (UNC-4) and on clinical procedures. | **Gate:** UNC-4 validated, plus procedures from a named authoritative source with version and expert review (`reference-material/02-Architecture-and-Validation.md`, claims gate). | CLIN-1, DATA-1. |
| WF-3 | Concept §6 (S4), Concept §10 | A confirmed anomaly triggers a NASA-STD-3001 countermeasure. | **Outside / Unsupported.** RA and BIB 4 note that NASA-STD-3001 is a standards document, not a treatment cookbook, and that citing it is not compliance. | **Gate:** program authority, an applicable requirement trace, and clinical review. Not a prototype requirement. | CLIN-1, QUAL-1. |
| WF-4 | Concept §2 | Avoid the hallucination risk of unconstrained LLM assistants. | **Implemented by absence.** The prototype contains no LLM or generated guidance. | Check that the package imports no LLM or network client (part of OFF-1's check). | None. |

### 3.6 Diagnostic instruments and the workstation interface

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| INS-1 | Concept §7 (Instrument 1) | B-mode ocular ultrasound guidance plus a 2D-CNN measuring optic nerve sheath diameter (ONSD); ≥ 5.8 mm "flags SANS intracranial pressure". | **Outside** (hardware, imaging, clinical validation). The threshold is **Unsupported** (see §4). | **Gate:** imaging hardware, labelled image data, a validated model, and clinical review of any cutoff. | HW-1, DATA-1, CLIN-1. |
| INS-2 | Concept §7 (Instrument 2) | A millisecond psychomotor vigilance (PVT) reaction-time test, where > 350 ms counts as a lapse. | **Proposed** as a software task. A *validated* cognitive test is **Outside** (the README excludes it). The 350 ms value is **Unsupported**. | If built: measure and document the timing latency of the display and input path on the target machine. Results are stored as records with `source=manual-task` and no interpretation. Any lapse cut-off is a labelled demo setting. | Timing validation; a validated protocol is CLIN-1. |
| INS-3 | Concept §7 (Instrument 3) | A point-of-care analyser for capillary glucose, cuff BP, core temperature and hydration/exercise logs. | **Outside** as a device. A **manual-entry form** for such values is **Proposed**. | Manual entries require a unit and a timestamp with an offset. They pass the same validation as CSV rows, are saved with `source=manual`, and show up in the table and chart. Tested. | Device integration is HW-1. |
| INS-4 | Concept §7 | A 6-system anatomical "digital twin" showing per-organ residuals and coupling between organs (e.g. bone calcium loss → kidney stone risk; CO₂ + 0 g → SANS). | **Unsupported by evidence / Outside.** The coupling statements are physiological assertions with no cited sources in the project. | **Gate:** sourced, reviewed physiology for every displayed relationship. Not a prototype requirement. | CLIN-1. |
| INS-5 | Concept §4 (Layer 6) | Real-time 1 Hz "oscilloscope" displays. | **Partially implemented** as a *static* time-series view of imported data (markers only, UTC axis, no interpolation; `tests/test_chart.py`). There is no live streaming. | Live display needs TEL-1 live input first. It must then show data age and gaps, and must not join points across missing readings. | INT-1. |

### 3.7 Offline operation

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| OFF-1 | RB-S1, RB-S2B, README | Works locally without network access. | **Implemented** in the narrow sense: the package contains no network code, and it is designed as a local desktop app. AR: "offline" does not imply secure, validated or flight-ready. | Add a test confirming the package imports none of `socket`, `urllib`, `http`, `requests` or LLM clients. Also do a manual run with the network disabled. | None. |
| OFF-2 | Concept §8, Concept §10 | Operates through a 14-minute communications delay and blackouts, with deferred sync to Earth flight surgeons. | **Outside.** No sync exists, and the project rules forbid network transmission of health data. | **Gate:** a mission comms interface specification, a security assessment and authorisation. | INT-1, QUAL-1. |
| OFF-3 | RB-S2B ("local records"), RA | Local records persist between sessions. | **Proposed.** The app currently only *reads* CSV files; nothing is saved. | If built: a local store keeps every field and flag exactly as loaded. A reload test shows identical records. The docs state that local storage provides no encryption or access control (AR). | Threat model before any sensitive data (SEC-1). |

### 3.8 Privacy and federated learning

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| PRV-1 | Concept §4 (Layer 2), Concept §8 | Federated training (Flower + Opacus DP-SGD) across 4 habitats with (ε = 2.5, δ = 10⁻⁴) Rényi differential privacy. | **Outside / Unsupported.** There is no implementation, and the privacy parameters are **unverified** (see §4). | **Gate:** multiple real data holders, a threat model, independent review of the privacy accounting, and a justified need (AR: "only if justified by requirements"). | DATA-1, SEC-1, QUAL-1. |
| PRV-2 | Concept §8, Concept §9 (Benchmark 4) | A cosine-median Byzantine filter rejects radiation-corrupted client gradients. | **Outside / Unsupported.** | Same gate as PRV-1. | As PRV-1. |
| PRV-3 | Concept §8, Concept §10 | "Zero raw health data exposed"; HIPAA/GDPR-suitable for Earth use. | **Unsupported by evidence.** No compliance assessment exists. | **Gate:** a formal privacy and legal assessment. Not to be claimed. | QUAL-1. |
| PRV-4 | Project instructions, AR | The prototype handles data cautiously: no transmission, pseudonymous IDs, nothing presented as real crew data. | **Partially implemented.** There is no network code, and the sample is labelled synthetic in the UI and data. There is no encryption, authentication or access control. | Write a threat model document before adding any persistence (OFF-3) or real data. The UI keeps its synthetic and no-medical-use banners; the existing GUI tests already check that the sample loads. | SEC-1. |

### 3.9 Audit records

| ID | Source | Requirement / claim | Status | Acceptance check | Dependencies |
|---|---|---|---|---|---|
| AUD-1 | Concept §4 (Layer 3), Concept §8 | A Hardhat Solidity contract (`HyperionMDAState.sol`) records training rounds, weight hashes, privacy budget spent and S4 alert hashes "on-chain". | **Outside / Unsupported.** There is no contract or chain. It conflicts with the no-network rule, and AR allows a ledger "only if justified". | **Gate:** a documented requirement that a simpler local log cannot meet, plus a security review. | SEC-1, QUAL-1. |
| AUD-2 | Concept §6 (S4) | A "cryptographic receipt" for Earth flight surgeons. | **Outside.** | Same gate as AUD-1, plus OFF-2. | As above. |
| AUD-3 | RA ("audit/event history"), AR | A local, append-only record of what was loaded and reviewed. | **Proposed** (feasible). | Each file load writes one JSON line: UTC time, file name, SHA-256 of the file, row and issue counts, app version. A test checks the hash against the file and that existing lines are unchanged after a second load. The docs state this gives traceability, **not** tamper-proofing or security. | None for the prototype. Tamper resistance needs SEC-1. |

### 3.10 Data sources, integrations and references

| ID | Source | Requirement / claim | Status | Acceptance check / gate | Dependencies |
|---|---|---|---|---|---|
| REF-1 | Concept §1 (badges), Concept §3 ("100% Grounded in Official Challenge Documentation") | The design is "100% grounded" in NASA HRP, CSA and OSDR resources. | **Unsupported by evidence.** BIB and RA treat these as *context*; nothing establishes that any of them is implemented. | Present them only as background references, with BIB caveats. | — |
| DATA-1 | Concept §1, Concept §3 | Uses NASA OSDR OSD-570 / RADLab, CSA dosimetry, CSA experiments (Vascular, MARROW, Bio-Monitor) and WESAD to seed "4 multi-habitat digital twin telemetry stores". | **Unsupported by evidence / Outside.** No dataset is in the project and no access is established. BIB: "Do not infer access or licensing from a program name." WESAD is a terrestrial wearable dataset and cannot stand in for astronaut data without justification (VP stage 2). | **Gate (VP stage 2):** for each dataset, record study ID, population, context, variables, units, sample rate, missingness, labels, access terms and limitations **before** any use. | Licences, data-use agreements. |
| INT-1 | Concept §3, Concept §4 | Integration with CSA Bio-Monitor channels, radiation dose-rate feeds, solar-particle-event alerts, and spacecraft or avionics systems. | **Outside.** BIB 9 notes that Bio-Monitor's existence "does not establish available API or HYPERION compatibility". | **Gate:** an authorised interface specification and test access. Not to be claimed (RA claims table). | Agency authorisation. |
| REF-2 | Concept §1 | "NASA Space Apps 2026 – Challenge 4: Crew Health Monitoring". | **Needs verification.** RB-S1 names the challenge "Create Health Monitoring Software for Astronauts on Space Missions". The two names should be checked against the official challenge page. | Use the exact official title and number. | — |

### 3.11 Impact claims

| ID | Source | Requirement / claim | Status | Gate |
|---|---|---|---|---|
| IMP-1 | Concept §10 | Lets Artemis, Gateway and Mars crews self-monitor and carry out verified countermeasures during blackouts. | **Unsupported by evidence / Outside.** | Rephrase as an intended goal (RB-S5A: "goals, not demonstrated outcomes"). |
| IMP-2 | Concept §10 | Transferable to rural telemedicine, polar stations and federated ICU monitoring under HIPAA/GDPR. | **Unsupported by evidence.** | Same as above; do not claim compliance (PRV-3). |
| IMP-3 | Concept §2 | Static Earth cutoffs (as in ATOMS and basic monitors) cause high false-positive rates. | **Unsupported by evidence.** No source is cited in the project. | Cite a specific source or remove the claim. |

---

## 4. Reported numbers and thresholds: all **unverified**

The project contains **no** datasets, training code, experiment logs, seeds or evaluation scripts behind any figure below. VP's "claims gate" already forbids using them as project results. They are listed so that none of them slips into a requirement, the UI or a slide as if it were established.

| Source | Figure as written in the concept | Kind | Status | Note |
|---|---|---|---|---|
| Concept §9 B1 | Macro-F1: local-only 0.63, centralised 0.89, DP-federated 0.87, "+24% over local-only" | Performance | **Unverified** | 0.87 − 0.63 is a 0.24 *absolute* gain, which is about 38% *relative*. The "+24%" label is ambiguous. No dataset, labels or split are described. |
| Concept §9 B2 | False-alarm rate falls from 48% to 2.9% ("93.9% reduction") during EVA/ARED | Performance | **Unverified** | The arithmetic is consistent ((48 − 2.9) / 48 ≈ 0.94), but nothing describes the alarm definition or the data. |
| Concept §9 B3 | Conformal coverage 95.6% against a 95.0% target; top exam "collapses" epistemic variance by 68% | Performance | **Unverified** | No calibration set and no checks of the method's assumptions. |
| Concept §9 B4 | Under simulated SEU corruption: FedAvg 0.52 F1 vs cosine-median 0.85 F1 | Performance | **Unverified** | The simulation setup is not described. |
| Concept §4, Concept §8 | ε = 2.5, δ = 10⁻⁴ (Rényi DP) | Privacy parameter | **Unverified** | A stated budget is not a privacy guarantee unless the accounting is reviewed. |
| Concept §4, Concept §5 | α ≤ 0.05; M = 15 MC-dropout passes | Method setting | **Unverified** | These are design choices, not results. |
| Concept §6 | ENMO > 0.22 g (exertion); τ < 0.5 (stale); τ ≥ 0.8 (confirmed) | Decision thresholds | **Unverified** | Not to be used as clinical or operational cut-offs. |
| Concept §7 | ONSD ≥ 5.8 mm flags SANS intracranial pressure | Clinical threshold | **Unverified** | Needs a clinical source and review (CLIN-1). |
| Concept §7 | PVT lapse > 350 ms | Cognitive threshold | **Unverified** | Needs a protocol source. |
| Concept §2 | ~15% plasma loss; 1.5%/month bone loss; insulin resistance; arterial stiffening | Physiology claims | **Unverified in this project** | Each figure needs a specific cited source with its scope before it is quoted. |
| Concept §3 | "100% grounded" | Rhetorical claim | **Unsupported** | See REF-1. |
| Prototype | \|z\| ≥ 2.5 demo flag | Display setting | **Implemented as an arbitrary demo value** | Explicitly **not** a clinical threshold (`engine.py`, README, UI footer). |

---

## 5. Five highest-priority requirements for a local demonstrator

These five were chosen because each one (a) addresses a gap named in Concept §2 or a mechanism proposed in §4, §6 or §8, using only local software; (b) can be shown working on synthetic files; (c) adds no clinical threshold or interpretation; and (d) leaves the current scoring rules unchanged. Every acceptance check is a software test on synthetic data, and passing one is **not** clinical validation. Each check should also be exercised by a small synthetic scenario file (VP stage 1, RA §4), so the demonstration can be repeated.

| # | Requirement | Traces to | Acceptance check (software, synthetic data) |
|---|---|---|---|
| **R1** | **Unit and duplicate quality checks.** Each signal has an allowed list of unit spellings (configuration, not clinical values). Rows with unrecognised units are flagged and left out of baselines, and never converted. Readings with the same subject and signal at the same absolute instant are flagged as duplicates (unit is not part of the key, so one instant recorded in two units also counts). **Status: implemented**; see TEL-3 and TEL-4. | TEL-3, TEL-4; Concept §2 (continuous vs occasional data), §4 (telemetry layer) | Tests: (1) a known unit is accepted; (2) an unsupported signal–unit pair gives an "Unsupported signal-unit pair" warning, the row stays visible, and it is absent from scoring; (3) two rows at the same instant (including the same instant written with different offsets) are both flagged and both shown; (4) all existing engine tests still pass unchanged. |
| **R2** | **Local append-only load log.** Each file load appends one JSON line: UTC time, file name, SHA-256 of the file, row and issue counts, app version. | AUD-3; Concept §8 (audit concept, as a *local* substitute for the ledger) | Tests: (1) the logged hash equals the file's SHA-256; (2) after a second load, the earlier lines are byte-for-byte unchanged and one line has been added; (3) a failed load is also logged with its error. The docs state that this gives traceability, **not** tamper-proofing or security. |
| **R3** | **Data-age (staleness) display.** For the selected series, show how long it has been since the last valid reading, relative to a reference time the user chooses. Nothing is imputed. | TEL-5; Concept §2 (occasional measurements), §5 (the concept's staleness idea, without its τ thresholds) | Tests with a fixed reference time: (1) the age is computed from the latest *valid* timestamp, with invalid ones ignored; (2) a series with no valid timestamp says so rather than showing a number; (3) no "stale" judgement is shown unless the user sets a cut-off, which is labelled as a demo setting. |
| **R4** | **Structured context, display only.** An optional fixed list of context values (for example `rest`, `exercise`) can mark points in the table and chart. Unknown values are shown exactly as written. Scores are unchanged. | CTX-1; Concept §2 (workload and environmental context), §5 (context, *without* residualization) | Tests: (1) known and unknown context values both appear exactly as written; (2) the chart can tell points apart by context; (3) z-scores are identical with and without context values present (no residualization). |
| **R5** | **Non-clinical review workflow.** Each observation can be marked *unreviewed → reviewed* or *needs re-measurement (user's choice)*. Transitions are deterministic, and each one is written to the R2 log. No medical guidance text appears. | WF-1 (non-clinical part); Concept §6 (five-state workflow; the *clinical* states stay gated) | Tests: (1) only the allowed transitions are possible, and invalid ones are rejected with a message; (2) each transition appends a log entry with the previous state, the new state and the UTC time; (3) the UI text contains no diagnosis, threshold or treatment wording. |

**After these five,** in order: a manual-entry form using the same validation (INS-3, software part); a written threat model, then local saving (SEC-1, OFF-3); a test confirming there are no network or LLM imports (OFF-1); and a comparison harness that runs only on synthetic data and reports flag counts as simulation, never as performance (UNC-6). BAS-2, CTX-2 and UNC-3 could follow as **experimental, synthetic-only** options, but only if the team asks for them, and with no performance claims.

## 6. Work that requires external evidence or formal review

None of the following can be demonstrated by the local prototype. None should be presented as a property of HYPERION-MDA until its gate is met. Items appear under every dependency that applies.

**External data (DATA-1: a specific licensed dataset, with metadata inspected per VP stage 2)**
- Concept §2 physiology figures, and the claim that static cut-offs cause false positives (IMP-3)
- Concept §3 dataset attributions: NASA OSDR (OSD-570 / RADLab), CIPHER and the Standard Measures, CSA radiation / Vascular / MARROW / Bio-Monitor data, WESAD (DATA-1, BAS-3)
- Concept §4/§5 methods applied to real signals: the Kalman tracker (BAS-2), context residualization (CTX-2), conformal calibration (UNC-3), MC-dropout (UNC-4), the multi-head network (UNC-5), artifact and SEU detection (TEL-6)
- **Every Concept §9 benchmark**: F1 0.63/0.89/0.87; false alarms 48% → 2.9%; coverage 95.6%; 68% variance reduction; FedAvg 0.52 vs cosine-median 0.85

**Clinical or expert review (CLIN-1: a named authoritative source, its scope and version, and qualified review)**
- The clinical states of the Concept §6 workflow, exam ranking by U(m), and NASA-STD-3001 countermeasures (WF-1 clinical part, WF-2, WF-3)
- Every threshold: ENMO > 0.22 g, τ < 0.5 / ≥ 0.8, ONSD ≥ 5.8 mm, PVT > 350 ms (§4), and any future "stale" or flag cut-off presented as clinical
- Exertion-based alarm suppression (CTX-4), the organ-coupling content of the digital twin (INS-4), and interpretation of PVT or ONSD values (INS-1, INS-2)

**Hardware or agency integration (HW-1, INT-1)**
- Concept §7 instruments: the ocular ultrasound with its CNN (INS-1), point-of-care glucose, BP and temperature devices (INS-3, device part), and a validated PVT timing platform (INS-2)
- Live 1 Hz streaming and oscilloscope displays (TEL-1, INS-5); Bio-Monitor, dosimetry and solar-particle-event feeds; spacecraft or avionics interfaces (INT-1)
- Communications-delay operation and Earth sync (OFF-2)

**Security, privacy or legal review (SEC-1)**
- Encryption, authentication and access control before any persistence of real data (OFF-3, PRV-4)
- Concept §8 federated learning, (ε = 2.5, δ = 10⁻⁴) differential privacy, and the Byzantine filter (PRV-1, PRV-2): privacy accounting needs independent review
- Tamper resistance beyond the R2 local log (AUD-3)

**Formal qualification or compliance (QUAL-1)**
- The on-chain ledger and cryptographic receipts (AUD-1, AUD-2)
- Applicability of NASA-STD-3001 and NASA-STD-8739.8; HIPAA/GDPR suitability (PRV-3, IMP-2)
- Any claim of flight readiness, operational crew use (IMP-1), NASA or CSA endorsement, or "100% grounded" traceability (REF-1)

## 7. Dependency key

| Key | Meaning |
|---|---|
| DATA-1 | A specific, licensed dataset whose metadata has been inspected (VP stage 2) |
| CLIN-1 | A named authoritative clinical source, its scope and version, and qualified expert review |
| ML-1 | A trained model with a leakage-safe evaluation plan |
| HW-1 | Physical device or hardware access and a specification |
| INT-1 | An authorised interface specification for an agency or spacecraft system |
| SEC-1 | A written threat model and security design |
| QUAL-1 | Formal assurance, compliance or qualification by the relevant authority |

*Update this document, and `docs/IMPLEMENTATION-STATUS.md`, whenever an item's status changes. A design note or TODO is not evidence of implementation.*
