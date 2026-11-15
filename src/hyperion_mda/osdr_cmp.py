"""Schema-checked adapter for the NASA OSDR OSD-575 serum CMP file (long format).

Mapping (nothing inferred or converted):
    ANALYTE    -> signal, exactly as written
    UNITS      -> unit, exactly as written (no conversion)
    SUBJECT_ID -> subject
    VALUE      -> value; "NA" is kept as a visible missing value and never imputed
    timepoint  -> mission-relative order only: "L-n" (n days before launch) is a
                  pre-flight baseline, "R+n" (n days after return) is a post-flight
                  observation. No calendar date is created.
Not used: SEX (demographic, not needed), RANGE_MIN/RANGE_MAX (the laboratory's
reference ranges are not used as thresholds). TEST_TYPE must be "CMP": any other
value is an explicit scoring rejection, so the row is kept visible with its source
line but is never a baseline and never scored.

Scoring for this source: each post-flight value is compared descriptively with the
same subject's pre-flight values for the same analyte and unit. The illustrative
|z| flag is disabled. There are no thresholds, alerts, diagnoses or recommendations.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from .engine import (ScoringProfile, TelemetryRecord, add_baseline_scores, flag_duplicates)
from .osdr_source import VerifiedFile

EXPECTED_COLUMNS = ("ANALYTE", "VALUE", "RANGE_MIN", "RANGE_MAX", "UNITS",
                    "TEST_TYPE", "SUBJECT_ID", "SEX", "timepoint")
EXPECTED_TEST_TYPE = "CMP"
# Explicit rejection reason carried on the record and shown in the score-basis column.
WRONG_ASSAY_REJECTION = "wrong assay type"
MISSING_TOKEN = "NA"
SOURCE_LABEL = "NASA OSDR OSD-575 (serum CMP)"
QUALITY_NOT_PROVIDED = "not provided by source"
UNCLASSIFIED = "unclassified"
_TIMEPOINT = re.compile(r"^(L-|R\+)(\d+)$")

# Exact analyte/unit spellings found in the verified file (copied verbatim, not derived
# at run time). A data-format allow-list, not a clinical range. No unit conversion.
OSDR_CMP_PAIRS: frozenset[tuple[str, str]] = frozenset({
    ("ALBUMIN", "g/dL"),
    ("ALBUMIN/GLOBULIN RATIO", "(calc)"),
    ("ALKALINE PHOSPHATASE", "U/L"),
    ("ALT", "U/L"),
    ("AST", "U/L"),
    ("BILIRUBIN; TOTAL", "mg/dL"),
    ("BUN/CREATININE RATIO", "(calc)"),
    ("CALCIUM", "mg/dL"),
    ("CARBON DIOXIDE", "mmol/L"),
    ("CHLORIDE", "mmol/L"),
    ("CREATININE", "mg/dL"),
    ("GLOBULIN", "g/dL"),
    ("GLUCOSE", "mg/dL"),
    ("POTASSIUM", "mmol/L"),
    ("PROTEIN; TOTAL", "g/dL"),
    ("SODIUM", "mmol/L"),
    ("UREA NITROGEN (BUN)", "mg/dL"),
    ("eGFR AFRICAN AMERICAN", "mL/min/1.73m2"),
    ("eGFR NON-AFR. AMERICAN", "mL/min/1.73m2"),
})

OSDR_CMP_PROFILE = ScoringProfile(
    name="osdr-osd575-cmp",
    supported_pairs=OSDR_CMP_PAIRS,
    require_quality_label=False,  # the source has no quality column; nothing is invented
    demo_flag_enabled=False,      # z is shown only as a descriptive, unvalidated comparison
    baseline_word="pre-flight baseline",
    note_suffix="; descriptive comparison only, unvalidated",
)


class OsdrSchemaError(Exception):
    """The file's columns are not the expected OSD-575 CMP schema."""


@dataclass(frozen=True)
class MissionTime:
    label: str
    phase: str  # "L" (before launch) or "R" (after return)
    days: int

    @property
    def order_key(self) -> tuple[int, int]:
        # L-92 < L-44 < L-3 < R+1 < R+45 < R+82 < R+194. Days before launch and days
        # after return are different reference points, so no spacing is implied.
        return (0, -self.days) if self.phase == "L" else (1, self.days)


def parse_timepoint(label: str) -> MissionTime | None:
    match = _TIMEPOINT.match(label)
    if not match:
        return None
    return MissionTime(label=label, phase=match.group(1)[0], days=int(match.group(2)))


@dataclass
class ImportReport:
    file_name: str
    sha256: str = ""
    data_rows: int = 0
    missing_value_lines: list[int] = field(default_factory=list)
    unparseable_value_lines: list[int] = field(default_factory=list)
    invalid_timepoint_lines: list[int] = field(default_factory=list)
    wrong_test_type_lines: list[int] = field(default_factory=list)
    unsupported_pair_lines: list[int] = field(default_factory=list)
    absent_combinations: list[tuple[str, str, str]] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    analytes: int = 0
    timepoints: list[str] = field(default_factory=list)
    scored_observations: int = 0

    def summary_lines(self) -> list[str]:
        def lines(xs):
            return ", ".join(str(x) for x in xs) if xs else "none"
        absent = "; ".join(f"{s} {a} {t}" for s, a, t in self.absent_combinations) or "none"
        return [
            f"Source file: {self.file_name}" + (f" (SHA-256 {self.sha256[:16]}… verified)" if self.sha256 else ""),
            f"{self.data_rows} data rows · {len(self.subjects)} subjects · {self.analytes} analytes · "
            f"timepoints {', '.join(self.timepoints)}",
            f"Missing values (NA, kept visible, not scored): {len(self.missing_value_lines)} at lines "
            f"{lines(self.missing_value_lines)}",
            f"Rows absent from the file: {absent}",
            f"Unparseable values: {lines(self.unparseable_value_lines)} · invalid timepoints: "
            f"{lines(self.invalid_timepoint_lines)} · non-CMP rows: {lines(self.wrong_test_type_lines)} · "
            f"unsupported analyte/unit pairs: {lines(self.unsupported_pair_lines)}",
            f"Post-flight values with a descriptive comparison: {self.scored_observations}",
        ]


def parse_cmp_rows(path: Path, file_label: str | None = None) -> tuple[list[TelemetryRecord], ImportReport]:
    """Read and schema-check a CMP file. Raises OsdrSchemaError on a column mismatch."""
    label = file_label or path.name
    report = ImportReport(file_name=label)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        header = tuple(reader.fieldnames or ())
        if header != EXPECTED_COLUMNS:
            missing = [c for c in EXPECTED_COLUMNS if c not in header]
            extra = [c for c in header if c not in EXPECTED_COLUMNS]
            raise OsdrSchemaError(
                f"{label}: columns do not match the OSD-575 CMP schema "
                f"(missing: {missing or 'none'}; unexpected: {extra or 'none'}; "
                f"expected order: {', '.join(EXPECTED_COLUMNS)}).")
        records: list[TelemetryRecord] = []
        for row in reader:
            line = reader.line_num
            if None in row or any(v is None for v in row.values()):
                raise OsdrSchemaError(f"{label}: line {line} has the wrong number of fields.")
            records.append(_to_record(row, line, label, report))
    report.data_rows = len(records)
    return records, report


def _to_record(row: dict, line: int, label: str, report: ImportReport) -> TelemetryRecord:
    flags: list[str] = []
    rejection_reason = ""
    analyte, unit, subject = row["ANALYTE"], row["UNITS"], row["SUBJECT_ID"]
    raw_value = row["VALUE"]
    if raw_value == MISSING_TOKEN:
        value = math.nan
        flags.append("Missing value in source (NA); not imputed, not scored")
        report.missing_value_lines.append(line)
    else:
        try:
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError
        except ValueError:
            value = math.nan
            flags.append(f"Unparseable value {raw_value!r} in source; not scored")
            report.unparseable_value_lines.append(line)
    if row["TEST_TYPE"] != EXPECTED_TEST_TYPE:
        flags.append(f"TEST_TYPE is {row['TEST_TYPE']!r}, expected 'CMP'")
        report.wrong_test_type_lines.append(line)
        rejection_reason = WRONG_ASSAY_REJECTION
    if not subject:
        flags.append("Missing SUBJECT_ID")
    if (analyte, unit) not in OSDR_CMP_PAIRS:
        flags.append(f"Unsupported analyte/unit pair ({analyte!r}, {unit!r}); not scored, unit not converted")
        report.unsupported_pair_lines.append(line)
    when = parse_timepoint(row["timepoint"])
    if when is None:
        flags.append(f"Unrecognised timepoint label {row['timepoint']!r}; not ordered or scored")
        report.invalid_timepoint_lines.append(line)
        record_type, order_key = UNCLASSIFIED, None
    else:
        record_type = "baseline" if when.phase == "L" else "observation"
        order_key = when.order_key
    return TelemetryRecord(
        row_number=line, timestamp=row["timepoint"], parsed_time=None, subject_id=subject,
        signal=analyte, value=value, unit=unit, context="", source=SOURCE_LABEL,
        quality=QUALITY_NOT_PROVIDED, record_type=record_type, flags=tuple(flags),
        order_key=order_key, source_ref=f"line {line} of {label}",
        rejection_reason=rejection_reason,
    )


def analyse(records: list[TelemetryRecord], report: ImportReport) -> list[TelemetryRecord]:
    """Duplicate check, pre-flight vs post-flight comparison, and stable ordering."""
    scored = add_baseline_scores(flag_duplicates(records), OSDR_CMP_PROFILE)
    final = []
    for r in scored:
        # An explicit source rejection keeps its own note; the unrecognised timepoint
        # stays visible in the row flags either way.
        if r.record_type == UNCLASSIFIED and not r.scoring_rejected:
            r = replace(r, score_note="Not classified: unrecognised timepoint label; not scored")
        final.append(r)
    timed = sorted((r for r in final if r.order_key is not None),
                   key=lambda r: (r.subject_id, r.signal, r.order_key, r.row_number))
    untimed = sorted((r for r in final if r.order_key is None), key=lambda r: r.row_number)
    report.scored_observations = sum(1 for r in final if r.z_score is not None)
    report.subjects = sorted({r.subject_id for r in final if r.subject_id})
    report.analytes = len({r.signal for r in final})
    labels = {r.timestamp: r.order_key for r in final if r.order_key is not None}
    report.timepoints = sorted(labels, key=lambda t: labels[t])
    present = {(r.subject_id, r.signal, r.timestamp) for r in final}
    report.absent_combinations = sorted(
        (s, a, t) for s in report.subjects for a in sorted({r.signal for r in final})
        for t in report.timepoints if (s, a, t) not in present)
    return timed + untimed


def load_osd575_cmp(verified: VerifiedFile) -> tuple[list[TelemetryRecord], ImportReport]:
    """The only runtime entry point: requires a checksum-verified file."""
    records, report = parse_cmp_rows(verified.path, verified.manifest["file_name"])
    report.sha256 = verified.sha256
    return analyse(records, report), report
