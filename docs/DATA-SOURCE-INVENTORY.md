# Data-source inventory

First written 2026-11-14. **Gate re-check: 2026-11-14** (§3 and §6). Each entry records what the source actually is, how it is accessed, and whether the MVP may use it.

**Rules for data:**
- NASA astronaut laboratory data and non-astronaut wearable data are kept **separate** in code, storage and UI.
- Molecular and sparse sample data are **never** described as continuous wearable telemetry.
- OSD-575 is **not** used as model-training data.
- Nothing in this file is a result.

**Status key:**
- **USED**: in the code today, verified.
- **GATED**: planned, but blocked until its gate passes.
- **CANDIDATE**: worth inspecting; not yet checked.
- **NOT USABLE**: wrong data type.
- **NOT PUBLIC**: the data exists, but no open access was found.
- **NOT FOUND**: not found by the searches listed. This is **not** a claim that the data doesn't exist.

## 1. NASA OSDR: Inspiration4 (SpaceX, 3-day private LEO mission, Sept 2021, 4 crew)

| Source | What it actually contains (verified from the official OSDR APIs) | Access | Status | Use in the MVP |
|---|---|---|---|---|
| **OSD-575**, serum CMP: [metadata](https://osdr.nasa.gov/osdr/data/osd/meta/575) · [files](https://osdr.nasa.gov/osdr/data/osd/files/575) | Clinical chemistry: 19 analytes, 4 subjects, 7 sparse timepoints (L-92 … R+194); 531 rows, 22 `NA`. SHA-256 `dab247eb…a0c`. | Listing shows `restricted: false`. **No licence stated** in the record. [OSDR terms](https://science.nasa.gov/reference/osdr-help-terms-and-conditions): "provided under NASA's open access policy". | **USED** | Descriptive pre- vs post-flight comparison, and the *Measured · lab sample* channels in the M2 panel. **Not wearable data. Never used for training** (no labels; n = 4). |
| OSD-575, cytokine panels (Eve HD71, HDCVD9; Alamar NULISA) | Multiplex immunoassays. The Eve panels were *"normalized by average of pre-flight values from all crew"* (record protocol text). | Public (same study) | CANDIDATE | Not in the MVP. |
| **OSD-569**, whole blood | *"Whole Blood Measurements from the SpaceX Inspiration4 Mission (RNA-seq, epitranscriptome, WGS, clonal hematopoiesis, CBC)"* | Public metadata; files **not inspected** | CANDIDATE | A possible second sparse lab panel (CBC), after inspection. |
| **OSD-570** PBMC; OSD-571 plasma; OSD-572/573/574/630/687 | Single-cell sequencing, proteomics/metabolomics, microbiome, spatial transcriptomics, histone profiling | Public metadata | **NOT USABLE** | Molecular data, **not telemetry**. (The PPT cites OSD-570 as cabin CO₂/radiation data; that conflicts with the record.) |

## 2. Search for public human wearable or continuous astronaut vital-sign data

**Result: NOT FOUND in the searches below.** That is not a finding that such data doesn't exist; §2.2 shows that some astronaut wearable data **does exist but is not publicly released**.

### 2.1 Searches performed (2026-11-14)

| Where | Query | Result |
|---|---|---|
| OSDR search API (`https://osdr.nasa.gov/osdr/data/search?term=…&type=cgene`) | `actigraphy`, `electrocardiogram`, `sleep`, `Astroskin`, `vital signs`, `wearable`, `Bio-Monitor`, `heart rate variability` | Totals 0–3 per term. The only *Homo sapiens* hits were OSD-195 (bed-rest skeletal-muscle gene expression; ground study) and OSD-127 (stem-cell-derived cardiac progenitors; ground study). **No wearable or vital-sign time series.** |
| OSDR search API (earlier the same day) | `heart rate`, `Inspiration4` | Cell, rodent and fly studies; Inspiration4 omics, microbiome, CBC and serum studies. Those result lists were truncated in the tool output. **No wearable data seen.** |
| CSA web / Government of Canada open data | Bio-Monitor astronaut data | No open dataset found (see 2.2). |

### 2.2 Wearable astronaut data that exists but is not public

| Source | Evidence | Access | Status |
|---|---|---|---|
| **CSA Bio-Monitor** recordings | The [CSA Bio-Monitor page](https://www.asc-csa.gc.ca/eng/sciences/bio-monitor.asp) lists its signals (heart electrical activity/pulse, blood pressure, breathing rate and volume, skin temperature, SpO₂, activity) and describes data sent to ground scientists, with **no public download or access process**. A [Government of Canada grant record](https://search.open.canada.ca/grants/record/csa-asc,003-2025-2026-Q2-00080,current) (CSA, Jul 2025 – Dec 2026) funds analysis of *"pre-existing data collected by the Bio-Monitor biometric shirt in nine astronauts (two women)"*, with 48-hour recordings. **No data release or access statement.** | Not public. Any access would be through CSA, with terms unknown. | **NOT PUBLIC** |
| **NASA Life Sciences Data Archive (LSDA)** human research data | NASA's [2024 HRP/OSDR presentation](https://ntrs.nasa.gov/api/citations/20240001562/downloads/hrp%20iws%202024%20osdr%2020240202_fin.pdf) describes **mediated access**: a request package with a Data Use Agreement, a review board, and secure transfer; IRB conditions can apply. The [LSDA portal page](https://nlsp.nasa.gov/explore/lsdahome) rendered no readable text for this check. | Request-based, not a public download. Whether it holds suitable wearable data was **not checked**. | **NOT PUBLIC** (request route) |
| ISS cabin ppCO₂ / radiation dose-rate time series | No OSDR study identified | — | **NOT FOUND** |
| B-mode ocular ultrasound / ONSD images | No dataset identified | — | **NOT FOUND** |

**MVP consequence:** there is **no astronaut wearable track**. All such channels remain *Unavailable* in the M2 panel.

## 3. WESAD: non-astronaut wearable data for a methods demonstration only

### 3.1 Authoritative sources checked

| Source | Link | Owner-provided? |
|---|---|---|
| **Owner dataset page** (authors: P. Schmidt, A. Reiss, R. Duerichen, C. Marberger, K. Van Laerhoven), hosted at the University of Siegen | <https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html> | **Yes** |
| Original page URL given in the paper | `https://ubicomp.eti.uni-siegen.de/home/datasets/icmi18/`. This now redirects (301) to `https://ubi29.informatik.uni-siegen.de/home/datasets/icmi18/`, which returns **404**. | Dead link |
| **Authors' paper**, owner-hosted PDF | <https://ubi29.informatik.uni-siegen.de/usi/pdf/ubi_icmi2018.pdf>. Schmidt et al., *Introducing WESAD…*, ICMI 2018, doi:[10.1145/3242969.3242985](https://doi.org/10.1145/3242969.3242985) | **Yes** (authors) |
| **Official download location**, linked from the owner page | <https://uni-siegen.sciebo.de/s/HGdUkoNlW1Ub0Gx>: "ICMI'18 dataset (2.5 GB zipped)". The share page shows a single `WESAD.zip`, **with no separate readme or licence file**. | Yes (link) |
| Repository mirror | [UCI ML Repository #465](https://archive.ics.uci.edu/dataset/465/wesad+wearable+stress+and+affect+detection), DOI 10.24432/C57K5T. Licence: *"See linked dataset for licensing information"*; *"please follow the acknowledgment policy on the original dataset website."* | Repository; defers to the owners |
| Not used as evidence | Kaggle and GitHub mirrors and third-party summaries. One Kaggle mirror labels the data CC BY 4.0, which **conflicts** with the owner terms. | No |

### 3.2 Gate checklist (owner and repository evidence only)

| Gate item | Evidence (verbatim where quoted) | Status |
|---|---|---|
| **Permitted use** | Owner page: *"You may use this data for scientific, non-commercial purposes"* | **VERIFIED** |
| **Attribution** | Owner page: *"provided that you give credit to the owners when publishing any work based on this data"*, citing Schmidt et al., ICMI 2018 | **VERIFIED** |
| **Redistribution** | Owner page: **not stated**. UCI defers to the owners. Third-party pages claim it's prohibited, but those aren't evidence here. | **NOT VERIFIED.** The project policy for WESAD is to track **neither raw nor derived** WESAD data: fetch on demand, keep it out of the repo and any archive. Nothing WESAD is downloaded or tracked today (§3c). |
| Does this project's use qualify as "scientific, non-commercial"? | A hackathon methods demonstration with no commercial use is *plausibly* within scope. That is a judgement, not owner confirmation. | **NEEDS TEAM DECISION** (or owner confirmation) |
| **Official download and archive** | Owner-linked sciebo share; one `WESAD.zip` of about 2.5 GB | **VERIFIED** (location). No checksum is published by the owners. |
| **File formats** | Not stated on the owner page or in the paper. Expected to be in the readme inside the archive. | **NOT VERIFIED** |
| **Subjects and exclusions** | Paper §3.1: *"In total, 17 subjects participated in our study. Due to sensor malfunction, the data of two participants had to be discarded. The remaining 15 subjects…"* Which two IDs were discarded is **not stated** in the owner sources checked. | **PARTLY VERIFIED** (count yes, IDs no) |
| **Conditions and labels** | Paper §3.3/§5.2: baseline (20 min), amusement, stress (TSST), two meditations; *"three different affective states (neutral, stress, amusement)"*; binary task *"combining the states baseline and amusement to a non-stress class"*. Self-reports: PANAS, STAI, SAM, SSSQ. The **integer label codes** in the files are **not stated** in these sources. | **PARTLY VERIFIED** (definitions yes, file codes no) |
| **Channels and sampling rates** | Paper §3.2: chest RespiBAN (ECG, EDA, EMG, TEMP, plus ACC and RESP): *"All signals were sampled at 700 Hz."* Wrist E4: *"BVP (64 Hz), EDA (4 Hz), TEMP (4 Hz), and ACC (32 Hz)."* | **VERIFIED** |
| **Units** | Not stated in the owner page or paper | **NOT VERIFIED** |
| **Evaluation precedent** | Paper §4: *"All models were evaluated using the leave-one-subject-out (LOSO) cross-validation"* | VERIFIED (consistent with the plan) |
| **Checksums** | None published. They can only be computed after download. | **NOT AVAILABLE** before download |

### 3.3 WESAD gate decision: **NO-GO (BLOCKED)**

The terms are **partly** verified: permitted use and attribution are confirmed from the owners. The **data documentation** the gate requires is **not**:
1. **Integer label codes**, and which samples are transient or undefined.
2. **File formats**: raw device files vs Python pickles. Loading an untrusted pickle can execute code.
3. **Signal units.**
4. **The IDs of the two discarded participants.**
5. **An explicit redistribution clause.**

Owner sources indicate that items 1–4 are in the readme **inside** the 2.5 GB archive, which isn't separately downloadable. Per the instruction, WESAD is **not downloaded, not redistributed and not used for training**, and the M2 panel keeps all 10 WESAD channels *Unavailable*.

**Evidence that would unblock the gate.** Either option suffices:
- **(A) Team-authorised documentation-only inspection.** Download `WESAD.zip` into an isolated cache outside the repository, then record its SHA-256 and size and read **only** the readme. No pickle loading and no training. Then verify items 1–4 and record them here. This is a download, so it needs explicit approval.
- **(B) Ask the owners** (contact via the owner page or paper) for the readme, or for written confirmation of items 1–5 and of whether this use counts as scientific, non-commercial.

The team must also decide whether this hackathon use falls within "scientific, non-commercial".

## 3b. PhysioNet "Wrist PPG During Exercise" v1.0.0: gate **GO** (M5, 2026-11-14)

| Item | Evidence | Status |
|---|---|---|
| Terms | [Owner page](https://physionet.org/content/wrist/1.0.0/): *Open Data Commons Attribution License v1.0*; open access. Cite Jarchi & Casson, *Data* 2017 (doi:10.3390/data2010001) and PhysioNet. | **VERIFIED.** Raw recordings are never bundled; **derived M6 outputs are tracked** — see §3c. |
| Documentation | Owner page: 8 participants; chest ECG (Actiwave) and wrist PPG plus IMU (Shimmer 3 GSR+), all at 256 Hz; walk, run, low- and high-resistance cycling; hand-marked reference ECG R-peaks; WFDB format. | **VERIFIED** |
| Files and checksums | 59 files in `SHA256SUMS.txt` (19 records; participants s1–s6, s8, s9; no s7). All downloaded and verified. The hash of the sums file is pinned in `wrist-1.0.0.provenance.json`. | **VERIFIED** |
| Format and units | WFDB format 16. Units from the headers: ECG and PPG "mV", accelerometer m/s² (`ms^-2`), gyroscope °/s, magnetometer Ga. The reader is checked against the header checksums and cross-checked against the official `wfdb` package (identical). | **VERIFIED.** Amplitudes are not calibrated (ECG values in the hundreds to thousands of "mV" are implausible as physical values). |
| Labels | Reference ECG beats (code 1, "N"). Each `.atr` starts with header pseudo-annotations; s9_walk has one NOTE. Activity from header comments (some speeds and levels "unknown"). **No stress or outcome labels.** | Suitable for HR-from-PPG methods checks and activity context only |
| Known data issue | The wrist timestamp channel is a 60 s rollover clock with whole-second jumps; its unwrapped span differs from the row count by 5–30 s per record. Not explained in the sources checked. | **The uniform 256 Hz index is used; the clock is not reinterpreted** |
| Use | **RECORDED-NON-ASTRONAUT methods lane only.** Never astronaut data, never merged with NASA records, no clinical meaning. | **GO** (non-astronaut methods demo) |

**PhysioNet "Wearable Exam Stress" v1.0.0** ([page](https://physionet.org/content/wearable-exam-stress/1.0.0/)) is open (ODC-By 1.0), but its outcomes are **exam grades, not stress labels**. It is not used for stress tasks.

## 3c. What is actually tracked in this repository

Earlier wording said this project "never redistributes" data. That was imprecise: it is true of the **raw recordings**, but not of **derived results**. The exact position, checked against `git ls-files`:

| Artifact | Tracked in git? | Notes |
|---|---|---|
| Raw PhysioNet `.hea` / `.dat` / `.atr` files (59 files) | **No** | Fetched on demand into a cache outside the repository (`~/.hyperion_mda/`, or `HYPERION_MDA_DATA_DIR`). |
| Raw NASA OSD-575 CMP CSV | **No** | No licence is stated in the study record, so it is not bundled; fetched on demand and SHA-256-verified. |
| Any WESAD file | **No** | The gate is NO-GO; nothing was downloaded. |
| Provenance manifests (URLs, sizes, SHA-256, licence text, citations) | **Yes** | `src/hyperion_mda/data/osdr/OSD-575.provenance.json`, `src/hyperion_mda/data/physionet/wrist-1.0.0.provenance.json`. Metadata only, no measurements. |
| **Derived M6 outputs** (14 files: per-window features, per-window predictions, per-participant/per-record metrics, `results.json`, `report.md`) | **Yes** | `experiments/m6/outputs/`. These contain participant IDs (s1–s9), record names, window positions, reference HR and model predictions **derived from the PhysioNet recordings**. They are not raw signal samples. |
| Synthetic test fixture | **Yes** | `tests/fixtures/simulated_telemetry.csv`; generated for tests, not measured. |

Why this is permitted for PhysioNet and not assumed elsewhere: the dataset is released under **ODC-By 1.0**, which allows redistribution with attribution. The required citations (Jarchi & Casson 2017; the standard PhysioNet citation) and the licence string are recorded in `src/hyperion_mda/data/physionet/wrist-1.0.0.provenance.json` and in this inventory (§3b), so they travel with the repository alongside the derived files. Storing derived outputs in the repo was an **approved deviation** from the frozen protocol's "outside the repository" default (`docs/M6-LOPO-PROTOCOL.md`, §7.2 row of the deviations table, approved decision 4). It is a team decision about open, non-astronaut data — **not** a precedent for crew data.

**Known gap (not fixed here):** the generated `experiments/m6/outputs/report.md` and `results.json` do **not** themselves carry the citation or licence text — they name the dataset but cite no authors. Attribution therefore depends on the manifest elsewhere in the repo. If those output files are ever extracted or shared on their own, the citation must be added to the report generator first. That is a change to M6 code and is out of scope for this documentation pass.

**Rule going forward:** raw third-party recordings stay out of git; derived artifacts are tracked only when the source licence permits it and the attribution travels with them. No astronaut-derived per-window data may be committed without a separate, explicit decision.

## 4. Synthetic data

| Source | Status | Rule |
|---|---|---|
| `tests/fixtures/simulated_telemetry.csv`, and CSVs written inside tests | Tests only | Never loaded by the app on its own; never presented as measured or recorded. |
| SIMULATED channels in the M2 panel | None defined | If ever added: labelled SIMULATED, off by default, never mixed with OSDR or WESAD values. |

## 5. Open data and access questions

| # | Question | Status after 2026-11-14 gate re-check |
|---|---|---|
| Q1 | WESAD terms | **Partly resolved.** Permitted use and attribution are verified from the owner page. Redistribution isn't stated (we track no WESAD data, raw or derived, anyway). The team must decide whether hackathon use counts as scientific, non-commercial. |
| Q2 | WESAD label codes, file formats, units, discarded IDs, checksums | **Open. Blocks the gate.** These are only in the archive's readme (§3.3 A or B). |
| Q3 | Public astronaut wearable or vital-sign data | **Not found in public sources searched** (§2.1). Bio-Monitor data exists but is not public; LSDA is request-based with a DUA and review. Who could request it, and under what authorisation, is open. |
| Q4 | Public ISS cabin ppCO₂ / radiation time series | Not found |
| Q5 | OSD-575 redistribution (no licence stated) | Open. The current practice (download on demand, never bundle) continues. |
| Q6 | OSD-569 CBC files, flags and checksums | Open (CANDIDATE) |
| Q7 | Python 3.14 support for `flwr`/Ray, `torch` and `opacus` | Open. Not needed until after the WESAD gate. |
| Q8 | Is the PPT "template" the submitted deck? (An unopened `HYPERION_MDA_NASA_SpaceApps_2026.pdf` also exists in Downloads.) | Open |

## 6. Gate status summary

| Gate | Status | Blocking evidence |
|---|---|---|
| OSD-575 (NASA laboratory data) | **GO, for descriptive display only.** Not for training. | — |
| **PhysioNet Wrist PPG (non-astronaut methods demonstration)** | **GO** (M5) | — |
| **WESAD (non-astronaut methods demonstration)** | **NO-GO (BLOCKED)** | Readme-level documentation (label codes, file formats, units, discarded IDs), a redistribution clause, and a team decision on "scientific, non-commercial" (§3.3) |
| Astronaut wearable data (any source) | **NO-GO** | No public source found; Bio-Monitor and LSDA would need a formal request and authorisation |
