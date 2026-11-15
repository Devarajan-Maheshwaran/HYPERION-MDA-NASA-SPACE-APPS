# NASA OSDR OSD-575 serum CMP: data source record

Retrieved and verified 2026-11-14. The machine-readable record is `src/hyperion_mda/data/osdr/OSD-575.provenance.json`, and the app checks the file against it every time it loads the file.

## Source (from the official OSDR APIs)

| Field | Value |
|---|---|
| Study | **OSD-575**: *SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays (Comprehensive Metabolic Panel and Multiplex)* |
| Mission | SpaceX Inspiration4. OSDR record: Mission Start 09/16/2021, Mission End 09/18/2021. *"a 3-day mission with four private astronauts to low Earth orbit"* |
| Principal investigator | Christopher Mason (Weill Cornell Medicine), per the OSDR record |
| OSDR dates | submitted 05-Dec-2022; public release 14-May-2024 |
| Metadata API | `https://osdr.nasa.gov/osdr/data/osd/meta/575` |
| Files API | `https://osdr.nasa.gov/osdr/data/osd/files/575` (lists 9 files; this one is `restricted: false`, `visible: true`) |
| File | `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv` (category "Comprehensive Metabolic Panel / Tabular Results Files / Original Submitted") |
| Download URL | `https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv` (redirects to OSDR's storage host `genelab-alsda-repo-prod.s3.amazonaws.com`) |
| Size | 25,275 bytes, matching the OSDR listing |
| **SHA-256** | `dab247eb794edab59aaaa683c85fd1f2dbf4ae3684872739338e10ead4192a0c`, computed from the downloaded file. Two independent retrievals (curl, then Python urllib) were byte-identical, and the fetch command verified a third. |
| Retrieved | 2026-11-14T07:40:15Z |
| Related publications | Overbey et al., doi:10.1038/s41467-024-48806-z; Overbey et al., *The Space Omics and Medical Atlas (SOMA) and international astronaut biobank*, doi:10.1038/s41586-024-07639-y |
| Dataset DOI | **Not present.** The DOI fields in the study metadata were empty. Use the OSDR study page's "Citation" panel. |

## Licence and redistribution

- The OSD-575 study metadata **states no licence**.
- The OSDR terms page says *"These data are provided under NASA's open access policy"* and *"Users are responsible for knowing their rights to distribute information."*
- NASA's science-data licence page applies CC0 to *"NASA-led mission data"*. Inspiration4 was a private mission, and for other data that page says *"the data are provided as is."*
- **Conclusion:** redistribution rights are not confirmed. This project **does not bundle the CSV**, and tracks **no derived OSD-575 measurements** either. What *is* in git is `src/hyperion_mda/data/osdr/OSD-575.provenance.json` — URL, size, SHA-256, licence status and citation, i.e. metadata, not values. Users download the CSV from OSDR with `python -m hyperion_mda.osdr_fetch`. (The tracked derived outputs under `experiments/m6/outputs/` come from the openly licensed PhysioNet dataset, not from OSDR; see `docs/DATA-SOURCE-INVENTORY.md` §3c.)

## File contents (as verified)

- **Columns:** `ANALYTE, VALUE, RANGE_MIN, RANGE_MAX, UNITS, TEST_TYPE, SUBJECT_ID, SEX, timepoint` (CRLF line endings, ASCII, no BOM).
- **Size of the data:** 531 data rows; subjects C001–C004; 19 analytes, each with one unit spelling; `TEST_TYPE` is always `CMP`.
- **Timepoints:** L-92, L-44, L-3 (pre-flight) and R+1, R+45, R+82, R+194 (post-flight).
- **Missing values:** 22 `NA` values, at CSV lines 7, 26, 64, 83, 93, 102, 140, 159, 178, 197, 216, 253, 272, 291, 310, 348, 367, 405, 424, 462, 481 and 519.
- **Absent row:** one subject/analyte/timepoint combination is missing entirely: C002, BUN/CREATININE RATIO, R+82.
- **Exact analyte/unit pairs** (the allow-list `OSDR_CMP_PAIRS` in `osdr_cmp.py`, copied verbatim): `ALBUMIN` g/dL · `ALBUMIN/GLOBULIN RATIO` (calc) · `ALKALINE PHOSPHATASE` U/L · `ALT` U/L · `AST` U/L · `BILIRUBIN; TOTAL` mg/dL · `BUN/CREATININE RATIO` (calc) · `CALCIUM` mg/dL · `CARBON DIOXIDE` mmol/L · `CHLORIDE` mmol/L · `CREATININE` mg/dL · `GLOBULIN` g/dL · `GLUCOSE` mg/dL · `POTASSIUM` mmol/L · `PROTEIN; TOTAL` g/dL · `SODIUM` mmol/L · `UREA NITROGEN (BUN)` mg/dL · `eGFR AFRICAN AMERICAN` mL/min/1.73m2 · `eGFR NON-AFR. AMERICAN` mL/min/1.73m2.

## Known discrepancies (reported, not resolved)

1. The OSDR study description lists post-flight samples at R+1, R+45 and R+82, but the CMP file also contains **R+194** (76 rows). The app shows R+194 exactly as given.
2. One expected row is absent (C002 / BUN/CREATININE RATIO / R+82). The import summary reports it.

## How the app uses it

| Column | Use |
|---|---|
| `ANALYTE` | Signal name, kept exactly as written |
| `UNITS` | Unit, kept exactly as written; never converted |
| `SUBJECT_ID` | Subject |
| `VALUE` | Numeric value. `NA` is kept as a visible missing value; it is never imputed and never scored. |
| `timepoint` | Mission-relative order only. `L-n` = pre-flight baseline; `R+n` = post-flight observation. No dates are created. |
| `TEST_TYPE` | Checked to equal `CMP`; any other value is flagged **and excluded from scoring** (see below) |
| `SEX` | **Not used** and not displayed |
| `RANGE_MIN`, `RANGE_MAX` | **Not used.** The laboratory's reference ranges are not used as thresholds and are not shown. |

**`rejection_reason` vs `flags` (R1).** These are two different things. `flags` is a list of **display warnings** shown in the row's "Row warnings" column — a missing `NA`, an unsupported analyte/unit pair, an unexpected `TEST_TYPE`. A flag on its own never removes a row from scoring. `rejection_reason` is a separate, **source-assigned** field: the adapter sets it only when it cannot vouch for the row at all (today, `TEST_TYPE` ≠ `CMP`, reason `"wrong assay type"`). A row with a `rejection_reason` is **never a baseline and never a scored observation**, its z-score is left empty, and the reason appears in the score-basis note ("Baseline reading excluded; not scored: wrong assay type" / "Row kept visible; not scored: wrong assay type"). The row itself stays visible — nothing is dropped or hidden. The engine reads `rejection_reason` directly; it never infers rejection from the flag text, so rewording a warning cannot change what gets scored. In the real OSD-575 file every row is `CMP`, so no row is rejected and no result changes; the rule matters if a different panel (for example the OSD-569 CBC candidate) or an edited file is ever loaded through this adapter.

**The comparison.** Each post-flight value is compared with the same subject's pre-flight values for the same analyte and unit: z = (value − pre-flight mean) / pre-flight sample SD. It needs at least 2 numeric pre-flight values and a non-zero SD.

**How to read the result:**
- The result is labelled a **descriptive, unvalidated comparison**.
- With only 2–3 baseline points, it is statistically fragile.
- It is **not** a measure of clinical significance.
- No flag, threshold, alert, diagnosis or recommendation is produced.

## Limitations

- **Small and sparse:** 4 people from one short private mission, with 7 timepoints. These results don't generalise to astronauts or to long-duration spaceflight.
- **No quality field:** the source has none, so no quality filtering is possible; values are used as reported.
- **Race-based analyte names:** two of the analytes are race-based eGFR variants. The names are preserved exactly as published. The app does not interpret them, and their presence is not an endorsement of race-based equations.
- **Time spacing:** days before launch and days after return use different reference points, so the chart shows order only, not true spacing.
