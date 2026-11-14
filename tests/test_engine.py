"""Software verification checks for the CSV demo engine (synthetic inputs only)."""

from __future__ import annotations

import itertools
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hyperion_mda.engine import (  # noqa: E402
    DEMO_FLAG_ABS_Z, DEMO_FLAG_LABEL, SUPPORTED_SIGNAL_UNITS, CsvLoadError, read_records,
)

HEADER = "timestamp,subject_id,signal,value,unit,context,source,quality,record_type\n"
# Synthetic fixture, kept only in tests (never loaded by the app at run time).
SAMPLE = Path(__file__).resolve().parent / "fixtures" / "simulated_telemetry.csv"


_default_second = itertools.count()


def _default_ts(record_type: str) -> str:
    """Distinct default instants: baselines from 08:00Z, observations from 09:00Z.

    Each call gets a new second so default rows never collide as duplicates (R1),
    and every default baseline stays earlier than every default observation.
    """
    second = next(_default_second) % 3000
    hour = 9 if record_type == "observation" else 8
    return f"2026-01-01T{hour:02d}:{second // 60:02d}:{second % 60:02d}Z"


def row(ts=None, value="70", quality="good", record_type="baseline",
        subject="S1", signal="heart_rate", unit="bpm") -> str:
    if ts is None:
        ts = _default_ts(record_type)
    return f"{ts},{subject},{signal},{value},{unit},rest,test,{quality},{record_type}\n"


class CsvTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)

    def write(self, content: str | bytes, name: str = "t.csv") -> Path:
        path = Path(self._dir.name) / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def load(self, content: str | bytes):
        return read_records(self.write(content))

    @staticmethod
    def pick(records, value):
        return next(r for r in records if r.value == value)

    @staticmethod
    def observations(records):
        return [r for r in records if r.record_type == "observation"]


class BaselineSeparationTests(CsvTestCase):
    def test_observation_not_included_in_baseline(self):
        records, _ = self.load(HEADER + row(value="68") + row(value="72")
                               + row(value="1000", record_type="observation"))
        (obs,) = self.observations(records)
        # Baseline mean 70, SD sqrt(8) — the observation itself is excluded.
        self.assertAlmostEqual(obs.z_score, (1000 - 70) / math.sqrt(8))

    def test_other_observations_do_not_shift_baseline(self):
        base = HEADER + row(value="68") + row(value="72")
        one, _ = self.load(base + row(value="75", record_type="observation"))
        many, _ = self.load(base + row(value="75", record_type="observation")
                            + row(value="500", record_type="observation"))
        z_one = self.observations(one)[0].z_score
        z_many = [r.z_score for r in self.observations(many) if r.value == 75][0]
        self.assertAlmostEqual(z_one, z_many)

    def test_baselines_are_per_subject_signal_unit(self):
        records, _ = self.load(HEADER + row(value="68") + row(value="72")
                               + row(value="10", subject="S2") + row(value="20", subject="S2")
                               + row(value="1", unit="other") + row(value="2", unit="other")
                               + row(value="70", record_type="observation"))
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    def test_low_quality_baselines_excluded(self):
        records, _ = self.load(HEADER + row(value="68") + row(value="72")
                               + row(value="999", quality="poor")
                               + row(value="70", record_type="observation"))
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    def test_low_quality_observation_not_scored(self):
        records, _ = self.load(HEADER + row(value="68") + row(value="72")
                               + row(value="70", record_type="observation", quality="artifact"))
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("quality", obs.score_note)

    def test_baseline_rows_have_no_score(self):
        records, _ = self.load(HEADER + row(value="68") + row(value="72"))
        self.assertTrue(all(r.z_score is None for r in records))

    def test_invalid_record_type_skipped(self):
        records, issues = self.load(HEADER + row(record_type="baselin"))
        self.assertEqual(records, [])
        self.assertTrue(any("record_type" in i for i in issues))

    def test_demo_flag_uses_single_constant(self):
        records, _ = self.load(HEADER + row(value="68") + row(value="72")
                               + row(value="1000", record_type="observation"))
        obs = self.observations(records)[0]
        self.assertGreaterEqual(abs(obs.z_score), DEMO_FLAG_ABS_Z)
        self.assertIn(DEMO_FLAG_LABEL, obs.flags)
        self.assertIn("demo only", DEMO_FLAG_LABEL)

    def test_bundled_sample(self):
        records, issues = read_records(SAMPLE)
        self.assertEqual(issues, [])
        (obs,) = self.observations(records)
        self.assertEqual(obs.value, 91)
        self.assertIsNotNone(obs.z_score)


class InsufficientBaselineTests(CsvTestCase):
    def test_no_baseline(self):
        records, _ = self.load(HEADER + row(record_type="observation"))
        obs = records[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("0 eligible baseline", obs.score_note)

    def test_single_baseline(self):
        records, _ = self.load(HEADER + row() + row(value="80", record_type="observation"))
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("1 eligible baseline", obs.score_note)

    def test_zero_spread_baseline(self):
        records, _ = self.load(HEADER + row() + row() + row()
                               + row(value="80", record_type="observation"))
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("spread is zero", obs.score_note)
        self.assertNotIn(DEMO_FLAG_LABEL, obs.flags)


class TemporalEligibilityTests(CsvTestCase):
    """Baselines must be validly timestamped and strictly earlier than the observation."""

    OBS = "2026-01-01T12:00:00Z"

    def obs_row(self, value="80", ts=None):
        return row(ts=ts or self.OBS, value=value, record_type="observation")

    def test_future_baseline_excluded(self):
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T10:00:00Z", value="68")
                               + row(ts="2026-01-01T11:00:00Z", value="72")
                               + row(ts="2026-01-01T13:00:00Z", value="999")
                               + self.obs_row(value="70"))
        # Only the two earlier baselines (mean 70) count; the future 999 is ignored.
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    # Since R1, a baseline at the observation's own instant (same subject and signal) is a
    # duplicate reading, so neither row is scored. The strictly-earlier rule still applies
    # but the duplicate check is reached first for this case.
    def test_same_timestamp_baseline_excluded(self):
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T10:00:00Z", value="68")
                               + row(ts="2026-01-01T11:00:00Z", value="72")
                               + row(ts=self.OBS, value="999")
                               + self.obs_row(value="70"))
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("duplicate reading", obs.score_note)
        same_instant = self.pick(records, 999)
        self.assertIn("excluded (duplicate reading)", same_instant.score_note)

    def test_same_instant_different_offset_excluded(self):
        # 14:00+02:00 is the same instant as 12:00Z, so it is not strictly earlier.
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T10:00:00Z", value="68")
                               + row(ts="2026-01-01T14:00:00+02:00", value="72")
                               + self.obs_row())
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("duplicate reading", obs.score_note)
        self.assertTrue(self.pick(records, 72).is_duplicate)

    def test_fewer_than_two_earlier_baselines(self):
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T10:00:00Z", value="68")
                               + row(ts="2026-01-01T13:00:00Z", value="72")
                               + row(ts="2026-01-01T14:00:00Z", value="74")
                               + self.obs_row())
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("1 eligible baseline reading(s) recorded before", obs.score_note)
        self.assertNotIn(DEMO_FLAG_LABEL, obs.flags)

    def test_different_offsets_compared_as_instants(self):
        # 13:30+03:00 = 10:30Z (earlier, eligible); 07:00-06:00 = 13:00Z (later, excluded).
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T13:30:00+03:00", value="68")
                               + row(ts="2026-01-01T05:00:00-05:00", value="72")
                               + row(ts="2026-01-01T07:00:00-06:00", value="999")
                               + self.obs_row(value="70"))
        obs = self.observations(records)[0]
        self.assertAlmostEqual(obs.z_score, 0.0)
        self.assertIn("vs 2 earlier baseline", obs.score_note)

    def test_invalid_timestamp_baseline_visible_but_unused(self):
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T10:00:00Z", value="68")
                               + row(ts="2026-01-01T11:00:00Z", value="72")
                               + row(ts="not-a-time", value="999")
                               + row(ts="2026-01-01T11:30:00", value="999")
                               + self.obs_row(value="70"))
        self.assertEqual(len(records), 5)
        excluded = [r for r in records if r.value == 999]
        for r in excluded:
            self.assertIn("timestamp", r.score_note)
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    def test_invalid_timestamp_observation_not_scored(self):
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T10:00:00Z", value="68")
                               + row(ts="2026-01-01T11:00:00Z", value="72")
                               + self.obs_row(ts="2026-01-01 noon"))
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("timestamp", obs.score_note)


class RowValidationTests(CsvTestCase):
    def test_invalid_values_skipped_with_issue(self):
        for bad in ("", "abc", "nan", "NaN", "inf", "-inf"):
            with self.subTest(value=bad):
                records, issues = self.load(HEADER + row(value=bad))
                self.assertEqual(records, [])
                self.assertTrue(any("not a finite number" in i for i in issues))

    def test_missing_columns(self):
        records, issues = self.load("timestamp,subject_id,signal,value\n2026-01-01T08:00:00Z,S1,hr,70\n")
        self.assertEqual(records, [])
        self.assertIn("record_type", issues[0])
        self.assertIn("quality", issues[0])

    def test_blank_quality_flagged_and_not_used(self):
        records, _ = self.load(HEADER + row(quality="") + row(value="72") + row(value="74")
                               + row(value="73", record_type="observation"))
        blank = [r for r in records if r.quality == ""][0]
        self.assertIn("Missing quality metadata", blank.flags)
        self.assertIn("excluded", blank.score_note)
        # Baseline from the two good rows only: mean 73.
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    def test_wrong_field_count_skipped(self):
        records, issues = self.load(HEADER + "2026-01-01T08:00:00Z,S1,hr,70\n")
        self.assertEqual(records, [])
        self.assertTrue(any("wrong number of fields" in i for i in issues))


class TimestampTests(CsvTestCase):
    def test_chronological_order_and_invalid_kept(self):
        records, _ = self.load(HEADER
                               + row(ts="2026-01-01T09:00:00Z", value="1")
                               + row(ts="not-a-time", value="2")
                               + row(ts="2026-01-01T08:00:00+00:00", value="3")
                               + row(ts="2026-01-01T08:30:00", value="4"))
        self.assertEqual([r.value for r in records], [3, 1, 2, 4])
        for r in records[2:]:
            self.assertIsNone(r.parsed_time)
            self.assertTrue(any("timestamp" in f for f in r.flags))

    def test_offsets_compared_correctly(self):
        records, _ = self.load(HEADER + row(ts="2026-01-01T08:00:00Z", value="1")
                               + row(ts="2026-01-01T09:30:00+02:00", value="2"))
        self.assertEqual([r.value for r in records], [2, 1])


class SupportedPairTests(CsvTestCase):
    """R1: only listed signal-unit pairs are scored; units are never converted."""

    def test_allow_list_matches_bundled_sample_exactly(self):
        records, _ = read_records(SAMPLE)
        self.assertEqual({(r.signal, r.unit) for r in records}, set(SUPPORTED_SIGNAL_UNITS))

    def test_supported_pairs_are_scored(self):
        for signal, unit in sorted(SUPPORTED_SIGNAL_UNITS):
            with self.subTest(pair=(signal, unit)):
                records, _ = self.load(HEADER
                                       + row(value="10", signal=signal, unit=unit)
                                       + row(value="20", signal=signal, unit=unit)
                                       + row(value="15", signal=signal, unit=unit, record_type="observation"))
                obs = self.observations(records)[0]
                self.assertAlmostEqual(obs.z_score, 0.0)
                self.assertFalse(any("Unsupported" in f for f in obs.flags))

    def test_unsupported_pairs_flagged_visible_and_not_scored(self):
        cases = [("heart_rate", "BPM"),          # case differs: not normalised
                 ("heart_rate", "beats/min"),    # synonym: not mapped
                 ("heart_rate", "Hz"),           # convertible in principle: not converted
                 ("hr", "bpm"),                  # unknown signal name
                 ("respiratory_rate", "bpm")]    # known names, wrong pairing
        for signal, unit in cases:
            with self.subTest(pair=(signal, unit)):
                records, _ = self.load(HEADER
                                       + row(value="1", signal=signal, unit=unit)
                                       + row(value="3", signal=signal, unit=unit)
                                       + row(value="2", signal=signal, unit=unit, record_type="observation"))
                self.assertEqual(len(records), 3)  # nothing dropped
                for r in records:
                    self.assertTrue(any("Unsupported signal-unit pair" in f for f in r.flags), r.flags)
                    self.assertIsNone(r.z_score)
                obs = self.observations(records)[0]
                self.assertIn("unsupported signal-unit pair", obs.score_note)
                base = self.pick(records, 1)
                self.assertIn("excluded (unsupported signal-unit pair)", base.score_note)

    def test_no_unit_conversion(self):
        # Hz readings keep their value and unit, and never join a bpm baseline.
        records, _ = self.load(HEADER
                               + row(value="1.2", unit="Hz")
                               + row(value="1.25", unit="Hz")
                               + row(value="68") + row(value="72")
                               + row(value="70", record_type="observation"))
        hz = [r for r in records if r.unit == "Hz"]
        self.assertEqual(sorted(r.value for r in hz), [1.2, 1.25])
        obs = self.observations(records)[0]
        self.assertEqual((obs.value, obs.unit), (70, "bpm"))
        self.assertIn("vs 2 earlier baseline", obs.score_note)  # only the two bpm rows
        self.assertAlmostEqual(obs.z_score, 0.0)

    def test_bpm_observation_with_only_unsupported_unit_baselines(self):
        records, _ = self.load(HEADER
                               + row(value="70", unit="beats/min") + row(value="72", unit="beats/min")
                               + row(value="71", record_type="observation"))
        obs = self.observations(records)[0]
        self.assertIsNone(obs.z_score)
        self.assertIn("0 eligible baseline", obs.score_note)


class DuplicateReadingTests(CsvTestCase):
    """R1: same subject + signal + absolute instant -> every row flagged, none scored."""

    def base(self):
        return (row(ts="2026-01-01T10:00:00Z", value="68")
                + row(ts="2026-01-01T11:00:00Z", value="72"))

    def obs(self, value="70"):
        return row(ts="2026-01-01T12:00:00Z", value=value, record_type="observation")

    def test_duplicates_flagged_kept_and_excluded(self):
        records, _ = self.load(HEADER + self.base()
                               + row(ts="2026-01-01T10:30:00Z", value="500")
                               + row(ts="2026-01-01T10:30:00Z", value="600")
                               + self.obs())
        self.assertEqual(len(records), 5)
        dupes = [r for r in records if r.value in (500, 600)]
        self.assertEqual(len(dupes), 2)
        for r in dupes:
            self.assertTrue(r.is_duplicate)
            self.assertTrue(any(f.startswith("Duplicate reading") for f in r.flags))
            self.assertIn("excluded (duplicate reading)", r.score_note)
        self.assertEqual(self.pick(records, 500).duplicate_rows, (self.pick(records, 600).row_number,))
        # Baseline is 68 and 72 only (mean 70), so the observation scores 0.
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    def test_every_row_in_larger_group_flagged(self):
        records, _ = self.load(HEADER + self.base()
                               + "".join(row(ts="2026-01-01T10:30:00Z", value=str(v)) for v in (1, 2, 3)))
        group = [r for r in records if r.value in (1, 2, 3)]
        self.assertEqual(len(group), 3)
        for r in group:
            self.assertEqual(len(r.duplicate_rows), 2)
            self.assertNotIn(r.row_number, r.duplicate_rows)

    def test_equal_instant_different_offsets_is_duplicate(self):
        records, _ = self.load(HEADER + self.base()
                               + row(ts="2026-01-01T10:30:00Z", value="500")
                               + row(ts="2026-01-01T12:30:00+02:00", value="600")
                               + row(ts="2026-01-01T05:30:00-05:00", value="700")
                               + self.obs())
        for v in (500, 600, 700):
            self.assertEqual(len(self.pick(records, v).duplicate_rows), 2)
        self.assertAlmostEqual(self.observations(records)[0].z_score, 0.0)

    def test_same_instant_different_unit_is_duplicate(self):
        # Unit is not part of the key: one moment recorded in two units is still a duplicate.
        records, _ = self.load(HEADER + row(ts="2026-01-01T10:30:00Z", value="70")
                               + row(ts="2026-01-01T10:30:00Z", value="1.17", unit="Hz"))
        self.assertTrue(all(r.is_duplicate for r in records))

    def test_duplicate_observations_both_unscored(self):
        records, _ = self.load(HEADER + self.base() + self.obs("70") + self.obs("90"))
        for obs in self.observations(records):
            self.assertIsNone(obs.z_score)
            self.assertIn("duplicate reading", obs.score_note)

    def test_non_duplicates(self):
        cases = {
            "different subject": row(ts="2026-01-01T10:30:00Z", value="500", subject="S2"),
            "different signal": row(ts="2026-01-01T10:30:00Z", value="500",
                                    signal="respiratory_rate", unit="breaths/min"),
            "one second later": row(ts="2026-01-01T10:30:01Z", value="500"),
            "offset makes it a different instant": row(ts="2026-01-01T10:30:00+01:00", value="500"),
        }
        for label, other in cases.items():
            with self.subTest(case=label):
                records, _ = self.load(HEADER + row(ts="2026-01-01T10:30:00Z", value="400") + other)
                self.assertFalse(any(r.is_duplicate for r in records), label)

    def test_invalid_timestamps_never_matched_as_duplicates(self):
        records, _ = self.load(HEADER + row(ts="bad", value="1") + row(ts="bad", value="2")
                               + row(ts="2026-01-01T10:30:00", value="3")   # offset-less
                               + row(ts="2026-01-01T10:30:00", value="4"))
        self.assertFalse(any(r.is_duplicate for r in records))

class FileErrorTests(CsvTestCase):
    def test_malformed_csv(self):
        path = self.write(HEADER + '2026-01-01T08:00:00Z,S1,"hr"x,70,bpm,rest,test,good,baseline\n')
        with self.assertRaises(CsvLoadError) as ctx:
            read_records(path)
        self.assertIn("Malformed CSV", str(ctx.exception))

    def test_non_utf8_input(self):
        content = (HEADER + row(subject="café")).encode("latin-1")
        with self.assertRaises(CsvLoadError) as ctx:
            read_records(self.write(content))
        self.assertIn("UTF-8", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(CsvLoadError) as ctx:
            read_records(Path(self._dir.name) / "absent.csv")
        self.assertIn("Could not read file", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
