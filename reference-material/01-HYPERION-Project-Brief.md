# HYPERION — Project Brief and Six-Slide Content

**Use:** Primary narrative source for a six-slide NASA Space Apps Challenge 2026 presentation.
**Project status:** Proposed student prototype. No flight validation, NASA approval, or measured performance results are supplied in the source material.

## Slide 1 — Title

**HYPERION: Personalized Astronaut Health Monitoring and Medical Decision Support**

NASA Space Apps Challenge 2026 · Challenge: Create Health Monitoring Software for Astronauts on Space Missions

Present HYPERION as a proposed offline-first desktop workstation that organizes available crew health measurements, compares them with an individual's own history, considers mission/activity context, and supports structured follow-up. Team name and member details should be supplied by the team.

## Slide 2 — Introduction

### A. Current Issue
NASA groups human-spaceflight hazards as radiation, isolation and confinement, distance from Earth, gravity fields, and hostile or closed environments. These hazards can affect physiology, behavior, and mission performance. Remote care and resupply become more difficult as distance from Earth increases. A monitoring tool must therefore handle multiple data types, changing context, imperfect sensors, and local operation. Do not claim every astronaut experiences a particular condition or that software alone mitigates these hazards.

### B. Key Features (proposed)
- Local collection/import of supported physiological and contextual measurements.
- Data-quality checks, timestamps, source/provenance, missing/stale-data visibility.
- Personal baseline and trend display.
- Activity-aware anomaly flagging as an experimental feature.
- Optional sleep, self-reported mood, and cognitive-task records; not diagnoses.
- Deterministic, documented follow-up workflow; no autonomous prescribing.
- Local records and operation without continuous internet; deferred sync only if implemented.

### C. Core Idea
**Collect → validate → contextualize → compare → explain → record.** Help the crew see what was measured, whether it is trustworthy, how it compares with that person's history, and what protocol-based next measurement may be appropriate. A statistical deviation is not a diagnosis.

### D. Novelty / Innovation (research hypothesis)
The project proposes combining personal baselines, activity context, data-quality awareness, and explainable follow-up in one local workstation. Its testable question is whether context and individual history improve anomaly-flag behavior over a fixed-threshold baseline in a specified dataset or controlled simulation. No improvement is established until evaluated. Avoid calling the combination unique or clinically superior without a documented comparison.

## Slide 3 — Technical Approach

### A. System Architecture
Proposed modular desktop application: device/manual/file adapters → ingestion and unit/time validation → quality/provenance checks → feature and context assembly → baseline/trend and experimental anomaly analysis → deterministic decision-support workflow → user interface, local database, audit/event log. Core computation is local. External sensors and spacecraft integration are future interfaces unless actually demonstrated. See `02-Architecture-and-Validation.md`.

### B. Technical Method
Start with transparent descriptive statistics and rules. Establish baselines only from identified, quality-checked data and guard against abnormal values silently redefining “normal.” Compare fixed-threshold, personal-baseline, and context-aware variants using the same split and evaluation protocol. Report data source, cohort, missingness, label limits, metrics, confidence intervals where appropriate, and failure cases. Do not invent thresholds or target accuracy.

## Slide 4 — Feasibility & Viability

### A. Feasibility
A desktop demonstrator can be scoped around recorded/sample data, visible provenance, quality checks, trend views, and a small rule-based workflow. Real astronaut sensor integration, clinical validation, spacecraft qualification, cyber accreditation, and flight deployment are outside what the supplied material establishes.

### B. Challenges
Limited representative labeled astronaut data; non-equivalent terrestrial datasets; device interoperability and units; sensor artifacts and missingness; privacy/security; clinical protocol authority; small sample sizes; and the distinction between anomaly detection and diagnosis.

### C. Risk Mitigation
Label simulated/imported/manual data clearly; preserve provenance; surface uncertainty and stale data; use approved source protocols only; require human judgment; test failure paths; keep claims bounded to the prototype. Treat NASA/CSA documents as references, not endorsements.

### D. Timeline
Use a team-confirmed timeline only. Suggested work packages (not dates or completed milestones): requirements and source review; data adapter and quality checks; baseline/trend interface; rule-based workflow; evaluation and failure analysis; presentation/demo. Do not imply these are complete.

## Slide 5 — Impacts & Benefits

### A. Expected Benefits (intended, not measured)
Potentially clearer longitudinal visibility, easier review of measurement context, earlier recognition of changes requiring follow-up, and support for Earth-independent workflows. These are goals, not demonstrated outcomes.

### B. Impact vs Effort
High-priority demonstrator work: data provenance/quality, local trend view, transparent personal baseline, and scripted scenarios. Higher effort and not established: real device integration, clinical utility, mission deployment, and validated prediction. Do not use fabricated impact scores.

### C. Social / Mission Relevance
The concept responds to NASA’s documented human-spaceflight hazards and the operational challenge of distance from Earth. It is a research prototype concept, not operational medical equipment.

## Slide 6 — Research & References

### A. Primary Research
NASA Human Research Program hazards/risks; NASA Exploration Medical Capability decision-support use cases; NASA-STD-3001 human-system standards; CSA Bio-Monitor; NASA Open Science Data Repository and Spaceflight Standard Measures. Consult `03-Research-Bibliography.md` for links, scope, and caveats.

### B. Existing Systems / Related Work
CSA describes Bio-Monitor as an astronaut wearable system and tablet application measuring multiple physiological signals. NASA ExMC publishes decision-support use cases. These are related research/operational references; HYPERION must not imply it integrates with or replaces them.

### C. Differentiation
State as a proposed integration and evaluation focus: transparent personal trends + mission/activity context + data-quality flags + protocol-linked follow-up in a local desktop demonstrator. Do not claim novelty as a fact absent a literature review.

### D. Market / Costs
No market sizing or cost evidence is supplied. Omit TAM/SAM/SOM, customer counts, revenue, or deployment forecasts. If needed, describe only potential stakeholder categories (space agencies, research groups) as possibilities, not validated customers.

## Presentation-wide wording rules
- Separate **established research**, **proposed design**, and **unvalidated hypothesis** (see technical source).
- Never say NASA approved/certified/endorsed HYPERION or that it is flight-ready.
- Never present prototype plans as implemented features.
- Never invent results, clinical cutoffs, sample sizes, accuracy, savings, market size, or sensor compatibility.
- Keep slide text concise; place detail and caveats in speaker notes.
