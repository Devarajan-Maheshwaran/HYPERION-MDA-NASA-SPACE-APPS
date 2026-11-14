# CSV schema (demo)

UTF-8 text (a byte-order mark is allowed), comma-separated, with a header row. All columns below are required; extra columns are ignored. This schema applies to CSVs opened with **Open CSV…**. The NASA OSDR OSD-575 file uses its own schema (see `docs/OSDR-OSD575-DATA.md`). The synthetic example CSV is a test fixture (`tests/fixtures/simulated_telemetry.csv`); the app does not ship or load it on its own. Results have no clinical meaning.

| Column | Meaning | Validation |
|---|---|---|
| `timestamp` | ISO 8601 date-time **with a UTC offset**, e.g. `2026-01-01T08:00:00Z` or `2026-01-01T10:00:00+02:00` | Unparseable, blank, or offset-less values are kept, given a row warning, and listed after the ordered rows. No time zone is assumed. |
| `subject_id` | Pseudonymous subject label | Blank → row warning; row is not used for baselines or scored |
| `signal` | Signal name, e.g. `heart_rate` | Blank → as above. Must form a supported signal–unit pair to be scored (see below). |
| `value` | Numeric measurement | Blank, non-numeric, NaN, or infinite → row skipped with a load note |
| `unit` | Unit as recorded; never converted | Blank → as above. Different units are never pooled. Must form a supported signal–unit pair to be scored. |
| `context` | Free-text activity/context note | Displayed only |
| `source` | Data source/provenance label | Blank → row warning |
| `quality` | Source quality label | Only `good`, `ok`, `valid` (case-insensitive) are used for scoring. Blank → "Missing quality metadata" warning; other values → "Source quality marked" warning. |
| `record_type` | `baseline` or `observation` | Any other value → row skipped with a load note |

Rows with the wrong number of fields are skipped with a load note. Malformed quoting, non-UTF-8 bytes, and unreadable files stop the load and show an error dialog.

## Supported signal–unit pairs

Only these exact, case-sensitive pairs are scored (`SUPPORTED_SIGNAL_UNITS` in `src/hyperion_mda/engine.py`). They are the pairs that appear in the synthetic test fixture.

| `signal` | `unit` |
|---|---|
| `heart_rate` | `bpm` |
| `respiratory_rate` | `breaths/min` |

Any other pair (for example `heart_rate` with `BPM`, `beats/min` or `Hz`) is **kept visible**, flagged "Unsupported signal-unit pair … not scored, unit not converted", and **excluded from scoring**: it is never used in a baseline, and an observation with such a pair is not scored. Units are never normalised, mapped or converted. This is a data-format allow-list, not a clinical range. Adding a pair is a code change that should come with tests.

## Duplicate readings

Rows with the same `subject_id` and `signal` at the same **absolute instant** are duplicates. Timestamps are compared as timezone-aware times, so `10:30:00Z`, `12:30:00+02:00` and `05:30:00-05:00` all match. `unit` is **not** part of the key: one moment recorded in two units is still a duplicate.

- Every row in a duplicate group stays visible, and each one is flagged with the other rows' line numbers.
- **No row in a duplicate group is used for scoring.** Duplicate baselines are excluded, and duplicate observations are not scored. The app does not pick one of them as correct.
- Rows without a valid, offset-bearing timestamp, subject or signal can't be compared, so they are never marked as duplicates. They are already excluded from scoring for their own reasons.
- A baseline at the same instant as an observation (same subject and signal) is a duplicate pair, so neither is scored.

## Demo scoring

- Each `observation` is compared only with **eligible** `baseline` rows. A baseline row is eligible for a given observation only if all of these hold:
  - same `subject_id`, `signal`, and `unit`, and that signal–unit pair is supported;
  - not part of a duplicate group;
  - accepted `quality` (`good`, `ok`, `valid`);
  - a valid ISO 8601 timestamp **with a UTC offset**;
  - recorded **strictly before** the observation. Baselines at the same instant or later are not used. (A same-instant baseline for the same subject and signal is also a duplicate, see above.) Timestamps are compared as absolute instants, so `14:00+02:00` and `12:00Z` count as the same time.
- Observations never contribute to a baseline.
- Rows with invalid or offset-less timestamps stay visible with a warning, but they are never used in a baseline. Such an observation is not scored either.
- z = (value − baseline mean) / baseline sample SD (n − 1).
- No z-score is shown, and the reason is displayed, when fewer than 2 eligible baseline readings were recorded before the observation, the baseline SD is zero, or the observation itself has unaccepted quality, missing identifying fields, an unsupported signal–unit pair, or is part of a duplicate group.
- `DEMO_FLAG_ABS_Z = 2.5` in `src/hyperion_mda/engine.py` is an arbitrary, illustrative display setting. It is not a clinical threshold, and a flag is not a diagnosis.
- Eligibility is decided separately for each observation, so different observations of the same signal can have different baselines.
- These rules are tested on synthetic data only. That checks the software's behaviour; it does not validate clinical performance and does not imply NASA approval or flight readiness.
