# Validation plan (proposed)

No clinical, algorithmic-performance, privacy, or flight validation results are included in this starter.

## Stage 1 — Software behavior
- Verify required CSV columns, finite numeric values, missing metadata, and visible row-level issues.
- Confirm data is grouped only by subject, signal, and unit for descriptive calculations.
- Check that the UI labels the example as synthetic and the threshold as demo-only.

## Stage 2 — Data suitability
For each dataset, record study identifier, population, collection context, measures, units, sample rate, missingness, labels, access terms, and limitations. Do not assume terrestrial wearable data establishes astronaut performance.

## Stage 3 — Research experiment
Define an intended use and hypothesis before analysis. Compare simple transparent baselines using subject/time-separated evaluation to avoid leakage. Report dataset and cohort, label definitions, metric rationale, uncertainty, failures, and limits. If reliable labels are unavailable, do not report classification metrics.

## Stage 4 — Human factors and safety
Assess whether users can distinguish measured, simulated, and derived values; understand missing/stale data; and interpret an anomaly as a prompt for review rather than a diagnosis. Any clinical workflow needs qualified medical review and traceable authority.

## Claims gate
Do not use the pasted MDA concept's reported F1 scores, false-alarm percentages, conformal coverage, variance reduction, privacy epsilon/delta guarantee, or instrument thresholds as project results unless the team supplies reproducible methods, data provenance, validation evidence, and appropriate expert review.
