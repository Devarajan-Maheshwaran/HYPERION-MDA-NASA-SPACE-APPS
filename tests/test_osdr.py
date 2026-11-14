"""Tests for the NASA OSDR OSD-575 CMP path: source verification, schema, ordering,
units, missing values, pre-flight baselines, and an end-to-end check on the real file.

Small CSVs written inside these tests are SYNTHETIC fixtures for schema and rule
checks only. The end-to-end tests use the real, checksum-verified OSDR file.
These are software checks; they say nothing about clinical validity.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
if os.environ.get("HYPERION_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(PROJECT / "src"))

from hyperion_mda import osdr_fetch  # noqa: E402
from hyperion_mda.engine import DEMO_FLAG_LABEL  # noqa: E402
from hyperion_mda.osdr_cmp import (EXPECTED_COLUMNS, OSDR_CMP_PAIRS, OsdrSchemaError, analyse,  # noqa: E402
                                   load_osd575_cmp, parse_cmp_rows, parse_timepoint)
from hyperion_mda.osdr_source import (CACHE_ENV_VAR, ChecksumMismatchError, OsdrSourceError,  # noqa: E402
                                      SourceFileMissingError, default_cache_dir, load_manifest,
                                      verified_cmp_file, verify_file)

HEADER = ",".join(EXPECTED_COLUMNS) + "\n"


def cmp_row(analyte="GLUCOSE", value="80", units="mg/dL", subject="S1", timepoint="L-92",
            test_type="CMP", sex="X", rmin="65", rmax="99") -> str:
    return f"{analyte},{value},{rmin},{rmax},{units},{test_type},{subject},{sex},{timepoint}\n"


def series(values_by_tp: dict[str, str], **kw) -> str:
    return "".join(cmp_row(value=v, timepoint=tp, **kw) for tp, v in values_by_tp.items())


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, text: str, name: str = "cmp.csv") -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8", newline="")
        return path

    def load(self, text: str):
        records, report = parse_cmp_rows(self.write(text))
        return analyse(records, report), report

    @staticmethod
    def find(records, subject="S1", analyte="GLUCOSE", timepoint="R+1"):
        return next(r for r in records if (r.subject_id, r.signal, r.timestamp) == (subject, analyte, timepoint))


# --------------------------------------------------------------------------- source verification
class SourceVerificationTests(TempDirCase):
    def fake_manifest(self, path: Path) -> dict:
        data = path.read_bytes()
        return {"study_id": "OSD-575", "file_name": path.name, "download_url": "x", "retrieved_utc": "x",
                "file_size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def test_matching_file_verifies(self):
        path = self.write(HEADER + cmp_row())
        verified = verify_file(path, self.fake_manifest(path))
        self.assertEqual(verified.sha256, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_file_is_reported_not_substituted(self):
        manifest = self.fake_manifest(self.write(HEADER))
        with self.assertRaises(SourceFileMissingError) as ctx:
            verify_file(self.dir / "absent.csv", manifest)
        self.assertIn("osdr_fetch", str(ctx.exception))

    def test_checksum_mismatch_same_size(self):
        path = self.write(HEADER + cmp_row(value="80"))
        manifest = self.fake_manifest(path)
        path.write_text(HEADER + cmp_row(value="81"), encoding="utf-8", newline="")  # same length
        self.assertEqual(path.stat().st_size, manifest["file_size_bytes"])
        with self.assertRaises(ChecksumMismatchError):
            verify_file(path, manifest)

    def test_size_mismatch(self):
        path = self.write(HEADER + cmp_row())
        manifest = self.fake_manifest(path)
        path.write_text(HEADER + cmp_row() + cmp_row(), encoding="utf-8", newline="")
        with self.assertRaises(ChecksumMismatchError):
            verify_file(path, manifest)

    def test_cache_dir_override(self):
        with mock.patch.dict(os.environ, {CACHE_ENV_VAR: str(self.dir)}):
            self.assertEqual(default_cache_dir(), self.dir / "osdr" / "OSD-575")


class FetchTests(TempDirCase):
    """Exercise the downloader with local file:// URLs (no network)."""

    def setUp(self):
        super().setUp()
        self.payload = self.write(HEADER + cmp_row(), "LSDS-8_test.csv")
        data = self.payload.read_bytes()
        self.manifest = {"study_id": "OSD-575", "file_name": "LSDS-8_test.csv", "retrieved_utc": "x",
                         "download_url": self.payload.as_uri(), "file_size_bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest(), "osdr_files_api": ""}
        self.cache = self.dir / "cache"
        patcher = mock.patch.object(osdr_fetch, "load_manifest", return_value=self.manifest)
        patcher.start()
        self.addCleanup(patcher.stop)

    def listing(self, **entry_overrides) -> str:
        entry = {"file_name": "LSDS-8_test.csv", "file_size": self.manifest["file_size_bytes"], "restricted": False}
        entry.update(entry_overrides)
        path = self.dir / "listing.json"
        path.write_text(json.dumps({"studies": {"OSD-575": {"study_files": [entry]}}}), encoding="utf-8")
        return path.as_uri()

    def test_successful_fetch_is_verified(self):
        target = osdr_fetch.fetch(self.cache, listing_url=self.listing())
        self.assertEqual(target.read_bytes(), self.payload.read_bytes())
        self.assertEqual([p.name for p in self.cache.iterdir()], ["LSDS-8_test.csv"])

    def test_checksum_failure_leaves_nothing_in_cache(self):
        bad = self.write(HEADER + cmp_row(value="81"), "tampered.csv")  # same size, different bytes
        with self.assertRaises(ChecksumMismatchError):
            osdr_fetch.fetch(self.cache, listing_url=self.listing(), download_url=bad.as_uri())
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_restricted_listing_refused(self):
        with self.assertRaises(OsdrSourceError):
            osdr_fetch.fetch(self.cache, listing_url=self.listing(restricted=True))

    def test_listing_size_change_refused(self):
        with self.assertRaises(ChecksumMismatchError):
            osdr_fetch.fetch(self.cache, listing_url=self.listing(file_size=1))

    def test_file_absent_from_listing_refused(self):
        with self.assertRaises(OsdrSourceError):
            osdr_fetch.fetch(self.cache, listing_url=self.listing(file_name="other.csv"))

    def test_cli_reports_failure_with_nonzero_exit(self):
        with mock.patch.object(osdr_fetch, "fetch", side_effect=ChecksumMismatchError("boom")):
            self.assertEqual(osdr_fetch.main(["--cache-dir", str(self.cache)]), 1)


# --------------------------------------------------------------------------- schema
class SchemaTests(TempDirCase):
    def test_exact_header_required(self):
        bad_headers = [
            HEADER.replace("timepoint", "TIMEPOINT"),                     # renamed
            HEADER.replace(",SEX", ""),                                   # missing column
            HEADER.replace("\n", ",EXTRA\n"),                             # extra column
            ",".join(reversed(EXPECTED_COLUMNS)) + "\n",                  # reordered
        ]
        for header in bad_headers:
            with self.subTest(header=header.strip()):
                with self.assertRaises(OsdrSchemaError):
                    parse_cmp_rows(self.write(header + cmp_row()))

    def test_wrong_field_count_rejected(self):
        with self.assertRaises(OsdrSchemaError):
            parse_cmp_rows(self.write(HEADER + "GLUCOSE,80,65,99,mg/dL,CMP,S1,X\n"))

    def test_non_cmp_rows_flagged(self):
        records, report = self.load(HEADER + cmp_row(test_type="CBC"))
        self.assertEqual(report.wrong_test_type_lines, [2])
        self.assertTrue(any("expected 'CMP'" in f for f in records[0].flags))

    def test_demographics_and_reference_ranges_not_used(self):
        base = {"L-92": "80", "L-44": "84", "L-3": "88", "R+1": "120"}
        a, _ = self.load(HEADER + series(base))
        b, _ = self.load(HEADER + series(base, sex="Y", rmin="0", rmax="1"))  # changed SEX and ranges
        strip = lambda rs: [(r.timestamp, r.value, r.unit, r.z_score, r.score_note, r.flags) for r in rs]
        self.assertEqual(strip(a), strip(b))
        record = a[0]
        for text in (str(record.__dict__),):
            self.assertNotIn("RANGE", text)
            self.assertNotIn("'X'", text)  # the SEX value is not carried into records


# --------------------------------------------------------------------------- ordering
class MissionOrderingTests(TempDirCase):
    def test_parse_timepoint(self):
        self.assertEqual(parse_timepoint("L-92").order_key, (0, -92))
        self.assertEqual(parse_timepoint("R+194").order_key, (1, 194))
        for bad in ("L92", "R-1", "l-3", "L+3", "", "R+", "Day 3", "2021-09-16"):
            with self.subTest(label=bad):
                self.assertIsNone(parse_timepoint(bad))

    def test_label_order(self):
        labels = ["R+194", "L-3", "R+1", "L-92", "R+82", "L-44", "R+45"]
        ordered = sorted(labels, key=lambda t: parse_timepoint(t).order_key)
        self.assertEqual(ordered, ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"])

    def test_no_calendar_dates_created(self):
        records, _ = self.load(HEADER + series({"R+45": "1", "L-3": "2", "L-92": "3"}))
        self.assertEqual([r.timestamp for r in records], ["L-92", "L-3", "R+45"])  # sorted, labels kept
        self.assertTrue(all(r.parsed_time is None for r in records))

    def test_invalid_label_kept_visible_and_unscored(self):
        records, report = self.load(HEADER + series({"L-92": "1", "L-44": "2"}) + cmp_row(timepoint="Day 5"))
        bad = next(r for r in records if r.timestamp == "Day 5")
        self.assertIsNone(bad.z_score)
        self.assertIn("unrecognised timepoint", bad.score_note)
        self.assertEqual(report.invalid_timepoint_lines, [4])


# --------------------------------------------------------------------------- units and values
class UnitAndValueTests(TempDirCase):
    def test_units_and_analyte_names_preserved_exactly(self):
        for analyte, unit in sorted(OSDR_CMP_PAIRS):
            with self.subTest(pair=(analyte, unit)):
                name = f'"{analyte}"' if "," in analyte else analyte
                records, _ = self.load(HEADER + cmp_row(analyte=name, units=unit))
                self.assertEqual((records[0].signal, records[0].unit), (analyte, unit))

    def test_unsupported_unit_flagged_not_converted(self):
        text = HEADER + series({"L-92": "4.4", "L-44": "4.6", "L-3": "4.5", "R+1": "5.0"}, units="mmol/L")
        records, report = self.load(text)
        obs = self.find(records)
        self.assertEqual((obs.value, obs.unit), (5.0, "mmol/L"))   # no mg/dL conversion
        self.assertIsNone(obs.z_score)
        self.assertIn("unsupported", obs.score_note)
        self.assertEqual(len(report.unsupported_pair_lines), 4)

    def test_na_is_visible_reported_and_not_imputed(self):
        text = HEADER + series({"L-92": "80", "L-44": "NA", "L-3": "84", "R+1": "NA", "R+45": "90"})
        records, report = self.load(text)
        self.assertEqual(len(records), 5)                            # nothing dropped
        self.assertEqual(report.missing_value_lines, [3, 5])
        na_obs = self.find(records, timepoint="R+1")
        self.assertTrue(math.isnan(na_obs.value))
        self.assertIsNone(na_obs.z_score)
        self.assertIn("missing in source", na_obs.score_note)
        scored = self.find(records, timepoint="R+45")
        self.assertIn("vs 2 earlier pre-flight baseline", scored.score_note)  # NA baseline not counted

    def test_unparseable_value_reported(self):
        records, report = self.load(HEADER + cmp_row(value="<5"))
        self.assertEqual(report.unparseable_value_lines, [2])
        self.assertFalse(records[0].has_value)


# --------------------------------------------------------------------------- baselines
class PreflightBaselineTests(TempDirCase):
    def test_only_preflight_rows_are_baselines(self):
        records, _ = self.load(HEADER + series({"L-92": "80", "L-44": "84", "L-3": "88",
                                                "R+1": "500", "R+45": "84"}))
        self.assertEqual({r.timestamp for r in records if r.record_type == "baseline"}, {"L-92", "L-44", "L-3"})
        later = self.find(records, timepoint="R+45")
        # R+1 (500) must not join the baseline: z for 84 vs mean 84 stays 0.
        self.assertAlmostEqual(later.z_score, 0.0)
        self.assertIn("vs 3 earlier pre-flight baseline readings", later.score_note)

    def test_baseline_count_and_descriptive_label(self):
        records, _ = self.load(HEADER + series({"L-92": "80", "L-44": "84", "L-3": "88", "R+1": "100"}))
        obs = self.find(records)
        expected = (100 - 84) / statistics.stdev([80, 84, 88])
        self.assertAlmostEqual(obs.z_score, expected)
        self.assertIn("descriptive comparison only, unvalidated", obs.score_note)

    def test_no_illustrative_flag_even_for_large_z(self):
        records, _ = self.load(HEADER + series({"L-92": "80", "L-44": "81", "L-3": "80", "R+1": "400"}))
        obs = self.find(records)
        self.assertGreater(abs(obs.z_score), 100)
        self.assertNotIn(DEMO_FLAG_LABEL, obs.flags)
        self.assertFalse(any("Illustrative" in f for f in obs.flags))

    def test_fewer_than_two_preflight_values(self):
        records, _ = self.load(HEADER + series({"L-92": "80", "L-44": "NA", "R+1": "90"}))
        obs = self.find(records)
        self.assertIsNone(obs.z_score)
        self.assertIn("1 eligible pre-flight baseline reading(s)", obs.score_note)

    def test_series_kept_per_subject_and_analyte(self):
        text = (HEADER + series({"L-92": "80", "L-44": "84", "R+1": "82"})
                + series({"L-92": "1", "L-44": "2"}, subject="S2"))
        records, _ = self.load(text)
        self.assertAlmostEqual(self.find(records).z_score, 0.0)


# --------------------------------------------------------------------------- real file, end to end
def _real_file_or_skip():
    try:
        return verified_cmp_file()
    except SourceFileMissingError as exc:
        raise unittest.SkipTest(f"Real OSDR file not downloaded ({exc}). Run: python -m hyperion_mda.osdr_fetch")


class RealOsdrEndToEndTests(unittest.TestCase):
    """Verified OSDR file -> adapter -> engine -> UI data model, checked against an
    independent calculation made directly from the raw CSV with the csv module."""

    @classmethod
    def setUpClass(cls):
        cls.verified = _real_file_or_skip()
        cls.records, cls.report = load_osd575_cmp(cls.verified)
        with cls.verified.path.open(encoding="utf-8", newline="") as handle:
            cls.raw = list(csv.DictReader(handle))

    def test_file_matches_manifest(self):
        manifest = load_manifest()
        self.assertEqual(self.verified.sha256, manifest["sha256"])
        self.assertEqual(self.verified.size, manifest["file_size_bytes"])

    def test_every_row_kept_with_source_reference(self):
        self.assertEqual(len(self.records), len(self.raw) == 531 and 531)
        self.assertEqual(sorted(r.row_number for r in self.records), list(range(2, 533)))
        self.assertTrue(all(r.source_ref.startswith(f"line {r.row_number} of LSDS-8_") for r in self.records))

    def test_missing_values_reported_exactly(self):
        expected = [i + 2 for i, row in enumerate(self.raw) if row["VALUE"] == "NA"]
        self.assertEqual(self.report.missing_value_lines, expected)
        self.assertEqual(len(expected), 22)
        self.assertEqual(self.report.absent_combinations, [("C002", "BUN/CREATININE RATIO", "R+82")])

    def test_units_and_names_preserved_from_raw(self):
        raw_by_line = {i + 2: row for i, row in enumerate(self.raw)}
        for r in self.records:
            raw = raw_by_line[r.row_number]
            self.assertEqual((r.signal, r.unit, r.subject_id, r.timestamp),
                             (raw["ANALYTE"], raw["UNITS"], raw["SUBJECT_ID"], raw["timepoint"]))
            if raw["VALUE"] != "NA":
                self.assertEqual(r.value, float(raw["VALUE"]))

    def test_z_scores_match_independent_calculation(self):
        pre: dict[tuple, list[float]] = {}
        for row in self.raw:
            if row["timepoint"].startswith("L-") and row["VALUE"] != "NA":
                pre.setdefault((row["SUBJECT_ID"], row["ANALYTE"], row["UNITS"]), []).append(float(row["VALUE"]))
        expected = {}
        for i, row in enumerate(self.raw):
            key = (row["SUBJECT_ID"], row["ANALYTE"], row["UNITS"])
            if row["timepoint"].startswith("R+") and row["VALUE"] != "NA" and len(pre.get(key, [])) >= 2:
                sd = statistics.stdev(pre[key])
                if sd > 0:
                    expected[i + 2] = (float(row["VALUE"]) - statistics.mean(pre[key])) / sd
        got = {r.row_number: r.z_score for r in self.records if r.z_score is not None}
        self.assertEqual(set(got), set(expected))
        for line, z in expected.items():
            self.assertAlmostEqual(got[line], z, places=9)
        self.assertEqual(self.report.scored_observations, len(expected))

    def test_no_flags_alerts_or_baselines_from_postflight(self):
        self.assertFalse(any("Illustrative" in f for r in self.records for f in r.flags))
        self.assertTrue(all(r.record_type == "observation" for r in self.records if r.timestamp.startswith("R+")))
        self.assertTrue(all(r.record_type == "baseline" for r in self.records if r.timestamp.startswith("L-")))


class RealOsdrGuiTests(unittest.TestCase):
    """The verified file through the desktop app's data model and widgets."""

    def setUp(self):
        self.verified = _real_file_or_skip()
        try:
            from hyperion_mda import app
            self.app_module, self.window = app, app.HyperionApp()
        except Exception as exc:
            raise unittest.SkipTest(f"Tk GUI unavailable: {exc}")
        self.window.geometry("1180x760")  # shown (not withdrawn) so the chart canvas has a real size
        self.window.update()
        self.dialogs = []
        mb = self.app_module.messagebox
        self._orig = (mb.showerror, mb.showwarning)
        mb.showerror = lambda t, m: self.dialogs.append(("error", t, m))
        mb.showwarning = lambda t, m: self.dialogs.append(("warning", t, m))

    def tearDown(self):
        mb = self.app_module.messagebox
        mb.showerror, mb.showwarning = self._orig
        self.window.destroy()

    def test_load_select_and_chart(self):
        w = self.window
        w.load_osdr()
        w.update()
        self.assertEqual(self.dialogs, [])
        rows = [w.table.item(i)["values"] for i in w.table.get_children()]
        self.assertEqual(len(rows), 531)
        self.assertEqual(sum(1 for r in rows if r[4] == "NA"), 22)
        self.assertIn("OSD-575", w.banner_text.get())
        self.assertIn("not wearable telemetry", w.banner_text.get())
        self.assertIn("531 rows · 22 NA", w.status.get())
        self.assertIn("SHA-256", w.import_summary)
        self.assertEqual(w.table.heading("z")["text"], "z (descriptive)")
        for r in rows:  # no alert or interpretation text anywhere in the rows
            text = " ".join(str(x) for x in r).lower()
            for word in ("diagnos", "risk", "recommend", "abnormal", "alert", "illustrative"):
                self.assertNotIn(word, text)
        index = next(i for i, r in enumerate(w.records)
                     if (r.subject_id, r.signal, r.timestamp) == ("C001", "CREATININE", "R+1"))
        w.table.selection_set(w.table.get_children()[index])
        w._show_selected()
        w.update()
        details = w.details.get()
        self.assertIn("vs 3 earlier pre-flight baseline readings", details)
        self.assertIn("Descriptive z (unvalidated)", details)
        self.assertIn("line 61 of LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv", details)
        self.assertNotIn("SEX", details)
        chart = w.chart
        ticks = [chart.itemcget(t, "text") for t in chart.find_withtag("xtick")]
        self.assertEqual(ticks, ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"])
        self.assertEqual((len(chart.find_withtag("baseline")), len(chart.find_withtag("observation"))), (3, 4))
        self.assertTrue(chart.find_withtag("flight_marker"))

    def select(self, subject, analyte, timepoint):
        w = self.window
        index = next(i for i, r in enumerate(w.records)
                     if (r.subject_id, r.signal, r.timestamp) == (subject, analyte, timepoint))
        w.table.selection_set(w.table.get_children()[index])
        w._show_selected()
        w.update()

    def test_na_timepoint_keeps_its_axis_slot(self):
        self.window.load_osdr()
        self.select("C001", "BILIRUBIN; TOTAL", "R+45")          # this value is NA in the source
        chart = self.window.chart
        ticks = [chart.itemcget(t, "text") for t in chart.find_withtag("xtick")]
        self.assertIn("R+45", ticks)                              # visible gap, not a vanished timepoint
        self.assertEqual(len(chart.find_withtag("point")), 6)     # 7 timepoints, 1 NA not plotted
        self.assertIn("line 93", self.window.details.get())

    def test_axis_title_and_note_do_not_overlap_at_minimum_size(self):
        self.window.geometry("900x740")
        self.window.load_osdr()
        self.select("C001", "BUN/CREATININE RATIO", "R+194")     # series with several NA rows
        chart = self.window.chart
        title = chart.bbox(chart.find_withtag("axis_title")[0])
        note = chart.bbox(chart.find_withtag("note")[0])
        self.assertLessEqual(title[3], note[1], (title, note))    # title bottom above note top
        self.assertLessEqual(note[3], chart.winfo_height(), (note, chart.winfo_height()))

    def test_missing_file_shows_failure_and_loads_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {CACHE_ENV_VAR: tmp}):
            self.window.load_path(PROJECT / "tests" / "fixtures" / "simulated_telemetry.csv")
            self.window.load_osdr()
        self.assertEqual(self.dialogs[-1][1], "OSDR data not loaded")
        self.assertIn("No other data was substituted", self.dialogs[-1][2])
        self.assertEqual(self.window.table.get_children(), ())      # earlier CSV cleared, nothing substituted
        self.assertIn("NO DATA LOADED", self.window.banner_text.get())
        self.assertIn("OSDR load failed", self.window.status.get())

    def test_tampered_file_rejected_in_gui(self):
        manifest = load_manifest()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {CACHE_ENV_VAR: tmp}):
            folder = Path(tmp) / "osdr" / "OSD-575"
            folder.mkdir(parents=True)
            data = bytearray(self.verified.path.read_bytes())
            data[-3] = ord("9") if data[-3] != ord("9") else ord("8")   # one changed byte, same size
            (folder / manifest["file_name"]).write_bytes(bytes(data))
            self.window.load_osdr()
        self.assertIn("does not match the provenance manifest", self.dialogs[-1][2])
        self.assertEqual(self.window.table.get_children(), ())


if __name__ == "__main__":
    unittest.main()
