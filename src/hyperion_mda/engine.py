"""Transparent CSV validation and descriptive baseline calculations.

The calculations here are for software demonstration only. They are not
validated for medical interpretation and must not guide care.

Scoring model (demo only):
    Each ``observation`` row is compared with the explicitly labelled
    ``baseline`` rows that share its subject, signal, and unit and were
    recorded strictly before it (valid, offset-bearing timestamps only).
    Observations never contribute to any baseline. Only rows whose quality is one of
    ``ACCEPTED_QUALITY`` are used, and missing or invalid data is reported
    rather than guessed.

Data-integrity exclusions (R1 in docs/REQUIREMENTS-TRACEABILITY.md):
    * Only signal-unit pairs listed in ``SUPPORTED_SIGNAL_UNITS`` are scored.
      Other pairs are flagged and kept visible; units are never converted.
    * Readings with the same subject and signal at the same instant (offsets
      compared as absolute times) are all flagged as duplicates and none of
      them is used for scoring.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

REQUIRED_COLUMNS = {
    "timestamp", "subject_id", "signal", "value", "unit",
    "context", "source", "quality", "record_type",
}
RECORD_TYPES = {"baseline", "observation"}
ACCEPTED_QUALITY = {"good", "ok", "valid"}
MIN_BASELINE_READINGS = 2

# Exact (case-sensitive) signal-unit spellings accepted for scoring. Only the pairs that
# appear in the bundled synthetic sample are listed. This is a data-format allow-list,
# not a clinical range; no unit conversion is performed for any pair.
SUPPORTED_SIGNAL_UNITS: frozenset[tuple[str, str]] = frozenset({
    ("heart_rate", "bpm"),
    ("respiratory_rate", "breaths/min"),
})

# Arbitrary display setting for the demo. NOT a clinical threshold.
# Defined once here so the calculation and the UI text cannot disagree.
DEMO_FLAG_ABS_Z = 2.5
DEMO_FLAG_LABEL = f"Illustrative |z| ≥ {DEMO_FLAG_ABS_Z:g} flag (demo only, not clinical)"


@dataclass(frozen=True)
class ScoringProfile:
    """How a data source is scored. Explicit per source; nothing is inferred."""
    name: str
    supported_pairs: frozenset[tuple[str, str]]
    require_quality_label: bool   # False only when the source has no quality field at all
    demo_flag_enabled: bool       # the illustrative |z| flag; disabled for real-data sources
    baseline_word: str = "baseline"
    note_suffix: str = ""


DEMO_PROFILE = ScoringProfile(
    name="csv-demo",
    supported_pairs=SUPPORTED_SIGNAL_UNITS,
    require_quality_label=True,
    demo_flag_enabled=True,
)


class CsvLoadError(Exception):
    """The file could not be read or parsed as a CSV."""


@dataclass(frozen=True)
class TelemetryRecord:
    row_number: int
    timestamp: str
    parsed_time: datetime | None
    subject_id: str
    signal: str
    value: float
    unit: str
    context: str
    source: str
    quality: str
    record_type: str
    flags: tuple[str, ...] = ()
    z_score: float | None = None
    score_note: str = ""
    duplicate_rows: tuple[int, ...] = ()  # other rows sharing subject, signal and instant
    # Mission-relative ordering for sources without calendar timestamps (e.g. OSDR
    # "L-92"/"R+1" labels). Never converted to dates. None for timestamped CSV rows.
    order_key: tuple[int, int] | None = None
    source_ref: str = ""  # e.g. "line 7 of <file>"; shown in the details panel

    @property
    def when(self):
        """Ordering value: the parsed timestamp, or the mission-relative key."""
        return self.parsed_time if self.parsed_time is not None else self.order_key

    @property
    def has_value(self) -> bool:
        """False for a value the source marked as missing (stored as NaN, never imputed)."""
        return math.isfinite(self.value)

    @property
    def pair_supported(self) -> bool:
        return (self.signal, self.unit) in SUPPORTED_SIGNAL_UNITS

    @property
    def is_duplicate(self) -> bool:
        return bool(self.duplicate_rows)

    @property
    def quality_accepted(self) -> bool:
        return self.quality.strip().lower() in ACCEPTED_QUALITY

    @property
    def group_key(self) -> tuple[str, str, str]:
        return (self.subject_id, self.signal, self.unit)

    @property
    def has_group_key(self) -> bool:
        return all(self.group_key)


def parse_timestamp(text: str) -> datetime | None:
    """Parse an ISO 8601 timestamp with an explicit UTC offset; None otherwise.

    A trailing ``Z`` is accepted as UTC. Timestamps without an offset are not
    given an assumed time zone.
    """
    text = text.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def read_records(path: str | Path) -> tuple[list[TelemetryRecord], list[str]]:
    """Read rows and report schema/row issues without silently repairing data.

    Raises ``CsvLoadError`` for file access, decoding, or CSV syntax errors.
    Returned records are in chronological order; rows whose timestamp could
    not be parsed follow in file order, each with a row warning.
    """
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
            records, issues = _parse(csv.DictReader(handle, strict=True))
    except UnicodeDecodeError as exc:
        raise CsvLoadError(f"File is not valid UTF-8 text ({exc.reason} at byte {exc.start}).") from exc
    except csv.Error as exc:
        raise CsvLoadError(f"Malformed CSV: {exc}") from exc
    except OSError as exc:
        raise CsvLoadError(f"Could not read file: {exc}") from exc
    if records is None:
        return [], issues
    if not records:
        issues.append("No usable rows found.")
    return sort_chronologically(add_baseline_scores(flag_duplicates(records))), issues


def _parse(reader: csv.DictReader) -> tuple[list[TelemetryRecord] | None, list[str]]:
    records: list[TelemetryRecord] = []
    issues: list[str] = []
    columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        return None, ["Missing required columns: " + ", ".join(sorted(missing))]
    for row in reader:
        row_number = reader.line_num
        if None in row or any(v is None for v in row.values()):
            issues.append(f"Row {row_number}: wrong number of fields; skipped.")
            continue
        text = {key: (row.get(key) or "").strip() for key in REQUIRED_COLUMNS}
        try:
            value = float(text["value"])
            if not math.isfinite(value):
                raise ValueError("value is not finite")
        except ValueError:
            issues.append(f"Row {row_number}: value is missing or not a finite number; skipped.")
            continue
        record_type = text["record_type"].lower()
        if record_type not in RECORD_TYPES:
            issues.append(
                f"Row {row_number}: record_type must be 'baseline' or 'observation' "
                f"(got {text['record_type']!r}); skipped.")
            continue

        flags: list[str] = []
        for key in ("subject_id", "signal", "unit", "source"):
            if not text[key]:
                flags.append(f"Missing {key}")
        parsed_time = parse_timestamp(text["timestamp"])
        if not text["timestamp"]:
            flags.append("Missing timestamp; not ordered")
        elif parsed_time is None:
            flags.append("Unparseable or offset-less timestamp; not ordered")
        if text["signal"] and text["unit"] and (text["signal"], text["unit"]) not in SUPPORTED_SIGNAL_UNITS:
            flags.append(f"Unsupported signal-unit pair ({text['signal']!r}, {text['unit']!r}); "
                         "not scored, unit not converted")
        if not text["quality"]:
            flags.append("Missing quality metadata")
        elif text["quality"].lower() not in ACCEPTED_QUALITY:
            flags.append("Source quality marked: " + text["quality"])

        records.append(TelemetryRecord(
            row_number=row_number,
            timestamp=text["timestamp"],
            parsed_time=parsed_time,
            subject_id=text["subject_id"],
            signal=text["signal"],
            value=value,
            unit=text["unit"],
            context=text["context"],
            source=text["source"],
            quality=text["quality"],
            record_type=record_type,
            flags=tuple(flags),
        ))
    return records, issues


def add_baseline_scores(records: list[TelemetryRecord],
                        profile: ScoringProfile = DEMO_PROFILE) -> list[TelemetryRecord]:
    """Score observations against explicit, earlier baselines; descriptive only.

    A baseline is eligible for an observation only if it has a value, the same
    subject/signal/unit, a supported signal-unit pair, accepted quality (when the
    profile requires a quality label), a valid time (timestamp or mission-relative
    label), is not a duplicate, and was recorded strictly before the observation.
    """
    baselines: dict[tuple[str, str, str], list[tuple[object, float]]] = {}
    for record in records:
        if _baseline_usable(record, profile):
            baselines.setdefault(record.group_key, []).append((record.when, record.value))

    result: list[TelemetryRecord] = []
    for record in records:
        if record.record_type == "baseline":
            if _baseline_usable(record, profile):
                note = "Baseline reading (eligible for later observations)"
            elif not record.has_value:
                note = "Baseline reading excluded (value missing in source; not imputed)"
            elif record.has_group_key and not _pair_ok(record, profile):
                note = "Baseline reading excluded (unsupported signal-unit pair)"
            elif record.is_duplicate:
                note = "Baseline reading excluded (duplicate reading)"
            elif record.when is None:
                note = "Baseline reading excluded (invalid or offset-less timestamp)"
            else:
                note = "Baseline reading excluded (quality or missing fields)"
            result.append(replace(record, score_note=note))
            continue
        result.append(_score_observation(record, baselines.get(record.group_key, []), profile))
    return result


def flag_duplicates(records: list[TelemetryRecord]) -> list[TelemetryRecord]:
    """Flag every row in each group sharing subject, signal and the same instant.

    Instants are compared as timezone-aware datetimes, so ``12:00Z`` and
    ``14:00+02:00`` match; mission-relative labels compare by their exact label
    position. Unit is not part of the key: the same moment recorded in two units
    is also a duplicate. Rows without a valid time, subject or signal cannot be
    compared and are left as they are. No row is removed.
    """
    groups: dict[tuple[str, str, object], list[int]] = {}
    for index, record in enumerate(records):
        if record.when is not None and record.subject_id and record.signal:
            groups.setdefault((record.subject_id, record.signal, record.when), []).append(index)
    result = list(records)
    for indices in groups.values():
        if len(indices) < 2:
            continue
        for index in indices:
            record = records[index]
            others = tuple(sorted(records[i].row_number for i in indices if i != index))
            flag = ("Duplicate reading: same subject, signal and instant as row(s) "
                    + ", ".join(str(r) for r in others) + "; not scored")
            result[index] = replace(record, duplicate_rows=others, flags=record.flags + (flag,))
    return result


def _pair_ok(record: TelemetryRecord, profile: ScoringProfile) -> bool:
    return (record.signal, record.unit) in profile.supported_pairs


def _quality_ok(record: TelemetryRecord, profile: ScoringProfile) -> bool:
    return record.quality_accepted or not profile.require_quality_label


def _baseline_usable(record: TelemetryRecord, profile: ScoringProfile = DEMO_PROFILE) -> bool:
    return (record.record_type == "baseline" and record.has_value and _quality_ok(record, profile)
            and record.has_group_key and record.when is not None
            and _pair_ok(record, profile) and not record.is_duplicate)


def _score_observation(record: TelemetryRecord, candidates: list[tuple[object, float]],
                       profile: ScoringProfile = DEMO_PROFILE) -> TelemetryRecord:
    if not record.has_value:
        return replace(record, score_note="No score: value missing in source (NA); not imputed")
    if not record.has_group_key:
        return replace(record, score_note="No score: subject, signal, or unit missing")
    if not _pair_ok(record, profile):
        return replace(record, score_note="No score: unsupported signal-unit pair (unit not converted)")
    if record.is_duplicate:
        rows = ", ".join(str(r) for r in record.duplicate_rows)
        return replace(record, score_note=f"No score: duplicate reading (also rows {rows})")
    if not _quality_ok(record, profile):
        return replace(record, score_note="No score: observation quality not good/ok/valid")
    if record.when is None:
        return replace(record, score_note="No score: observation timestamp invalid or lacks a UTC offset")
    values = [value for when, value in candidates if when < record.when]
    n = len(values)
    if n < MIN_BASELINE_READINGS:
        return replace(record, score_note=(
            f"No score: {n} eligible {profile.baseline_word} reading(s) recorded before this observation; "
            f"need {MIN_BASELINE_READINGS}"))
    mean = sum(values) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))
    if sd == 0:
        return replace(record, score_note=f"No score: baseline spread is zero (n={n})")
    z = (record.value - mean) / sd
    flagged = profile.demo_flag_enabled and abs(z) >= DEMO_FLAG_ABS_Z
    flags = record.flags + ((DEMO_FLAG_LABEL,) if flagged else ())
    return replace(record, z_score=z, flags=flags,
                   score_note=(f"vs {n} earlier {profile.baseline_word} readings (mean {mean:g}, SD {sd:.3g})"
                               f"{profile.note_suffix}"))


def sort_chronologically(records: list[TelemetryRecord]) -> list[TelemetryRecord]:
    """Rows with a valid time in order (stable), then unordered rows in file order."""
    timed = sorted((r for r in records if r.when is not None), key=lambda r: r.when)
    untimed = sorted((r for r in records if r.when is None), key=lambda r: r.row_number)
    return timed + untimed
