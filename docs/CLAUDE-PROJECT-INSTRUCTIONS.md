# Instructions for Claude Desktop

Use this folder as the project context for building HYPERION-MDA. Start with `README.md`, `docs/PROJECT-BRIEF.md`, `docs/ARCHITECTURE.md`, and `docs/IMPLEMENTATION-STATUS.md`.

## Working rules
- Make small, reviewable changes and explain which files changed.
- Keep simulated data conspicuously labeled; never present it as astronaut or NASA data.
- Update implementation status when features are added.
- Keep established research, proposed design, and unvalidated hypotheses separate.
- Do not invent dataset access, results, thresholds, hardware integration, standards compliance, NASA approval, or clinical recommendations.
- Do not add network transmission of health data.
- Before adding medical interpretation, require a named authoritative protocol source, scope, version, and appropriate expert review.
- Prefer transparent, testable behavior over speculative complexity.
- When evaluating algorithms, request real data provenance and an evaluation plan before reporting performance.

## First useful development milestones
1. Improve CSV error handling and schema documentation.
2. Add explicit per-subject baseline configuration without silently learning from flagged data.
3. Add a time-series view with provenance and missingness.
4. Write software verification checks before relying on the calculation.
5. Select one suitable, licensed dataset only after inspecting its metadata.

Do not implement all advanced ideas from the concept document at once. Build only what can be demonstrated and evaluated.
