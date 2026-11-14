"""Checks for time-series chart data preparation (display only; synthetic inputs)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if os.environ.get("HYPERION_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(PROJECT / "src"))

from hyperion_mda.chart import MIN_PLOT_POINTS, nice_ticks, padded_range, prepare_series  # noqa: E402
from hyperion_mda.engine import read_records  # noqa: E402

HEADER = "timestamp,subject_id,signal,value,unit,context,source,quality,record_type\n"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "simulated_telemetry.csv"  # synthetic, tests only


def row(ts, value, record_type="baseline", subject="S1", signal="hr", unit="bpm", quality="good"):
    return f"{ts},{subject},{signal},{value},{unit},rest,test,{quality},{record_type}\n"


class ChartDataTests(unittest.TestCase):
    def load(self, body: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            path.write_text(HEADER + body, encoding="utf-8")
            records, _ = read_records(path)
        return records

    @staticmethod
    def pick(records, value):
        return next(r for r in records if r.value == value)

    def test_chronological_order_across_offsets(self):
        records = self.load(row("2026-01-01T12:00:00Z", 3)
                            + row("2026-01-01T13:30:00+03:00", 1)   # 10:30Z
                            + row("2026-01-01T06:00:00-05:00", 2))  # 11:00Z
        series = prepare_series(records, self.pick(records, 3))
        self.assertEqual([p.value for p in series.points], [1, 2, 3])
        self.assertTrue(all(p.time_utc.tzinfo == timezone.utc for p in series.points))

    def test_grouped_by_subject_signal_and_unit_only(self):
        records = self.load(row("2026-01-01T08:00:00Z", 1)
                            + row("2026-01-01T09:00:00Z", 2)
                            + row("2026-01-01T08:30:00Z", 50, subject="S2")
                            + row("2026-01-01T08:30:00Z", 60, signal="rr")
                            + row("2026-01-01T08:30:00Z", 70, unit="other"))
        series = prepare_series(records, self.pick(records, 1))
        self.assertEqual([p.value for p in series.points], [1, 2])
        self.assertEqual((series.subject_id, series.signal, series.unit), ("S1", "hr", "bpm"))

    def test_record_types_and_selected_point(self):
        records = self.load(row("2026-01-01T08:00:00Z", 1)
                            + row("2026-01-01T09:00:00Z", 2)
                            + row("2026-01-01T10:00:00Z", 99, record_type="observation"))
        series = prepare_series(records, self.pick(records, 99))
        self.assertEqual([p.record_type for p in series.points], ["baseline", "baseline", "observation"])
        self.assertEqual([p.selected for p in series.points], [False, False, True])
        self.assertEqual(series.selected_point.value, 99)

    def test_low_quality_rows_still_plotted_as_imported(self):
        # The chart shows imported data; quality affects scoring, not display.
        records = self.load(row("2026-01-01T08:00:00Z", 1)
                            + row("2026-01-01T09:00:00Z", 2, quality="poor"))
        self.assertEqual(len(prepare_series(records, self.pick(records, 1)).points), 2)

    def test_invalid_timestamps_listed_not_plotted(self):
        records = self.load(row("2026-01-01T08:00:00Z", 1)
                            + row("not-a-time", 2)
                            + row("2026-01-01T09:00:00", 3)      # no offset
                            + row("2026-01-01T10:00:00Z", 4))
        series = prepare_series(records, self.pick(records, 1))
        self.assertEqual([p.value for p in series.points], [1, 4])
        self.assertEqual(series.unplotted_rows, (3, 4))  # physical CSV line numbers
        self.assertTrue(series.plottable)

    def test_selected_row_with_invalid_timestamp_has_no_point(self):
        records = self.load(row("2026-01-01T08:00:00Z", 1)
                            + row("2026-01-01T09:00:00Z", 2)
                            + row("bad", 3, record_type="observation"))
        series = prepare_series(records, self.pick(records, 3))
        self.assertTrue(series.plottable)
        self.assertIsNone(series.selected_point)

    def test_too_few_valid_timestamps_explained(self):
        records = self.load(row("2026-01-01T08:00:00Z", 1) + row("bad", 2) + row("", 3))
        series = prepare_series(records, self.pick(records, 1))
        self.assertFalse(series.plottable)
        self.assertIn("Too few valid timestamps", series.message)
        self.assertIn(f"1 of 3", series.message)
        self.assertIn(str(MIN_PLOT_POINTS), series.message)

    def test_missing_group_key_explained(self):
        records = self.load(row("2026-01-01T08:00:00Z", 1, unit="")
                            + row("2026-01-01T09:00:00Z", 2, unit=""))
        series = prepare_series(records, records[0])
        self.assertFalse(series.plottable)
        self.assertIn("missing", series.message)

    def test_equal_timestamps_keep_file_order(self):
        records = self.load(row("2026-01-01T08:00:00Z", 5) + row("2026-01-01T08:00:00Z", 6))
        self.assertEqual([p.value for p in prepare_series(records, records[0]).points], [5, 6])

    def test_padded_range_handles_flat_and_reversed(self):
        self.assertEqual(padded_range(5, 5), (4.75, 5.25))
        self.assertEqual(padded_range(0, 0), (-1.0, 1.0))
        low, high = padded_range(10, 0)
        self.assertLess(low, 0)
        self.assertGreater(high, 10)


    def test_nice_ticks_are_round_and_in_range(self):
        ticks = nice_ticks(66.16, 92.84, 5)
        self.assertEqual(ticks, [70, 80, 90])  # step 26.68/4 ≈ 6.7 rounds up to 10
        self.assertLessEqual(len(ticks), 5)
        self.assertTrue(all(66.16 <= t <= 92.84 for t in ticks))
        self.assertEqual(nice_ticks(13.84, 16.16, 3), [14, 16])  # step 1.16 rounds up to 2
        self.assertEqual(nice_ticks(13.84, 16.16, 5), [14, 15, 16])
        self.assertEqual(nice_ticks(5, 5), [5])


class ChartWidgetTests(unittest.TestCase):
    """Smoke-checks the drawn canvas; visual quality is inspected manually."""

    def setUp(self):
        try:
            from hyperion_mda import app
            self.app_module, self.window = app, app.HyperionApp()
        except Exception as exc:
            raise unittest.SkipTest(f"Tk GUI unavailable: {exc}")
        mb = app.messagebox
        self._orig = (mb.showerror, mb.showwarning)
        mb.showerror = mb.showwarning = lambda *_a: None
        self.window.geometry("1180x860")
        self.window.update()

    def tearDown(self):
        mb = self.app_module.messagebox
        mb.showerror, mb.showwarning = self._orig
        self.window.destroy()

    def select_value(self, value):
        index = next(i for i, r in enumerate(self.window.records) if r.value == value)
        self.window.table.selection_set(self.window.table.get_children()[index])
        self.window._show_selected()
        self.window.update()

    def test_bundled_example_draws_markers(self):
        self.window.load_path(FIXTURE)
        self.select_value(91)
        chart = self.window.chart
        self.assertEqual(len(chart.find_withtag("baseline")), 5)
        self.assertEqual(len(chart.find_withtag("observation")), 1)
        self.assertTrue(chart.find_withtag("selected"))
        self.assertEqual(chart.find_withtag("line_series"), ())  # nothing joins the points
        self.assertIn("Score basis", self.window.details.get())

    def test_message_shown_when_unplottable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            path.write_text(HEADER + row("bad", 1) + row("2026-01-01T08:00:00Z", 2), encoding="utf-8")
            self.window.load_path(path)
        self.select_value(1)
        chart = self.window.chart
        self.assertEqual(chart.find_withtag("point"), ())
        text = chart.itemcget(chart.find_withtag("message")[0], "text")
        self.assertIn("Too few valid timestamps", text)
        self.assertEqual(len(self.window.table.get_children()), 2)  # rows stay visible

    def test_redraws_after_resize(self):
        self.window.load_path(FIXTURE)
        self.select_value(91)
        self.window.geometry("900x740")  # the window minsize
        self.window.update()
        self.assertEqual(len(self.window.chart.find_withtag("point")), 6)


if __name__ == "__main__":
    unittest.main()
