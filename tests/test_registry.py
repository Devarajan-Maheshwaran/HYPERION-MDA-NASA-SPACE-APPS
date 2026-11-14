"""M2 tests: signal registry and the channel panel (display only; software checks).

Covers registry coverage, exactly one status per channel, no stored values, no
clinical/risk/integration wording, separation of NASA lab data from wearable-model
data, and the persistent "not a validated physiological digital twin" notice.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if os.environ.get("HYPERION_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(PROJECT / "src"))

from hyperion_mda import signal_registry as reg  # noqa: E402
from hyperion_mda.osdr_cmp import OSDR_CMP_PAIRS, load_osd575_cmp  # noqa: E402
from hyperion_mda.osdr_source import SourceFileMissingError, verified_cmp_file  # noqa: E402

# Words that would imply assessment, clinical meaning or integration. Checked in registry
# text and in every panel row. (The panel's limitation notice is checked separately: it
# deliberately says what the panel does NOT show.)
BANNED = ("risk", "diagnos", "treat", "cutoff", "threshold", "abnormal", "elevated", "healthy",
          "normal range", "alert", "integrat", "approved", "flight-ready", "validated twin")
ORGAN_WORDS = ("kidney", "renal", "liver", "hepatic", "heart", "cardi", "bone", "organ", "metabolic risk")
REQUIRED_UNAVAILABLE = ("unavail:biomonitor-ecg", "unavail:biomonitor-breathing", "unavail:biomonitor-skin-temp",
                        "unavail:biomonitor-spo2", "unavail:biomonitor-activity", "unavail:cuff-bp", "unavail:sleep",
                        "unavail:pvt", "unavail:onsd", "unavail:cabin-ppco2", "unavail:cabin-radiation",
                        "unavail:cabin-pressure")


def text_of(channel: reg.Channel) -> str:
    return " ".join(str(v) for v in dataclasses.asdict(channel).values()).lower()


class RegistryCoverageTests(unittest.TestCase):
    def test_registry_is_consistent(self):
        self.assertEqual(reg.validate_registry(), [])

    def test_every_osd575_pair_has_exactly_one_lab_channel(self):
        for analyte, unit in OSDR_CMP_PAIRS:
            with self.subTest(pair=(analyte, unit)):
                matches = [c for c in reg.CHANNELS if c.lane == reg.LANE_NASA_LAB
                           and (c.label, c.unit) == (analyte, unit)]
                self.assertEqual(len(matches), 1)
        self.assertEqual(sum(c.lane == reg.LANE_NASA_LAB for c in reg.CHANNELS), len(OSDR_CMP_PAIRS))

    def test_required_unavailable_channels_present(self):
        ids = {c.channel_id: c for c in reg.CHANNELS}
        for cid in REQUIRED_UNAVAILABLE:
            with self.subTest(channel=cid):
                self.assertIn(cid, ids)
                self.assertEqual(ids[cid].status, reg.UNAVAILABLE)
                self.assertEqual(ids[cid].unit, "")
                self.assertEqual(ids[cid].sampling, "none")

    def test_wesad_channels_unavailable_pending_gate(self):
        wesad = [c for c in reg.CHANNELS if c.lane == reg.LANE_WEARABLE_MODEL]
        self.assertEqual(len(wesad), 10)
        for c in wesad:
            self.assertEqual(c.status, reg.UNAVAILABLE)
            self.assertIn("not astronaut data", c.source)
            for word in ("terms of use", "label codes", "file format", "checksums", "not downloaded",
                         "not redistributed", "not used for training"):
                self.assertIn(word, c.note.lower())


class StatusTests(unittest.TestCase):
    def test_exactly_one_valid_status_per_channel(self):
        for c in reg.CHANNELS:
            with self.subTest(channel=c.channel_id):
                self.assertIsInstance(c.status, str)
                self.assertIn(c.status, reg.STATUSES)
        self.assertEqual(sum(reg.status_counts().values()), len(reg.CHANNELS))

    def test_channel_ids_unique(self):
        ids = [c.channel_id for c in reg.CHANNELS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_channel_has_a_source_description(self):
        for c in reg.CHANNELS:
            self.assertGreater(len(c.source.strip()), 20, c.channel_id)

    def test_simulated_and_recorded_channels_each_in_their_own_lane(self):
        counts = reg.status_counts()
        self.assertEqual(counts[reg.SIMULATED], 3)
        self.assertEqual(counts[reg.RECORDED_NON_ASTRONAUT], 5)
        for c in reg.CHANNELS:
            self.assertEqual(c.status == reg.SIMULATED, c.lane == reg.LANE_SIMULATED, c.channel_id)
            self.assertEqual(c.status == reg.RECORDED_NON_ASTRONAUT, c.lane == reg.LANE_RECORDED, c.channel_id)
            if c.status == reg.RECORDED_NON_ASTRONAUT:
                self.assertTrue(c.label.startswith("RECORDED non-astronaut"))
                self.assertIn("not astronaut data", c.source)
            if c.status == reg.SIMULATED:
                self.assertTrue(c.label.startswith("SIMULATED"))
                self.assertIn("not astronaut data", c.source)

    def test_registry_holds_no_values(self):
        # Every field is descriptive text; there is no numeric field that could hold a sample value.
        for f in dataclasses.fields(reg.Channel):
            self.assertEqual(f.type, "str", f.name)


class WordingTests(unittest.TestCase):
    def test_no_clinical_risk_or_integration_wording(self):
        for c in reg.CHANNELS:
            text = text_of(c)
            for word in BANNED:
                self.assertNotIn(word, text, (c.channel_id, word))

    def test_lab_analytes_grouped_by_sample_not_organ(self):
        for c in reg.CHANNELS:
            if c.lane == reg.LANE_NASA_LAB:
                self.assertEqual(c.region, reg.REGION_BLOOD)
                self.assertIn("Sparse blood draws", c.sampling)
                self.assertIn("no clock times", c.sampling)
                self.assertNotIn("continuous", c.sampling.lower())
                for word in ORGAN_WORDS:
                    self.assertNotIn(word, c.region.lower())


class LaneSeparationTests(unittest.TestCase):
    def test_lanes_are_disjoint(self):
        lanes = {}
        for c in reg.CHANNELS:
            lanes.setdefault(c.lane, set()).add(c.label)
        self.assertFalse(lanes[reg.LANE_NASA_LAB] & lanes[reg.LANE_WEARABLE_MODEL])
        self.assertTrue(all(c.status != reg.MEASURED_LAB_SAMPLE for c in reg.CHANNELS
                            if c.lane != reg.LANE_NASA_LAB))

    def test_registry_and_panel_do_no_io_and_no_training(self):
        banned_imports = {"urllib", "socket", "pickle", "sklearn", "torch", "flwr", "opacus", "csv"}
        for name in ("signal_registry.py", "twin_view.py"):
            tree = ast.parse((PROJECT / "src" / "hyperion_mda" / name).read_text(encoding="utf-8"))
            imported = {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            imported |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            self.assertFalse(imported & banned_imports, (name, imported & banned_imports))
            self.assertNotIn("open(", (PROJECT / "src" / "hyperion_mda" / name).read_text(encoding="utf-8"))

    def test_no_wesad_or_real_data_training_module_exists(self):
        names = {p.name for p in (PROJECT / "src" / "hyperion_mda").glob("*.py")}
        self.assertFalse({n for n in names if "wesad" in n or "train" in n}, names)
        # The only learning code is the toy FL simulation, which may not import any data pipeline.
        self.assertEqual({n for n in names if n.startswith("fl_")}, {"fl_sim.py", "fl_view.py"})

    def test_osd575_records_map_only_to_nasa_lab_channels(self):
        try:
            verified = verified_cmp_file()
        except SourceFileMissingError as exc:
            self.skipTest(f"Real OSDR file not downloaded ({exc})")
        records, _ = load_osd575_cmp(verified)
        for r in records:
            channel = reg.nasa_lab_channel_for(r.signal, r.unit)
            self.assertIsNotNone(channel, (r.signal, r.unit))
            self.assertEqual(channel.lane, reg.LANE_NASA_LAB)
        wearable_labels = {c.label for c in reg.CHANNELS if c.lane == reg.LANE_WEARABLE_MODEL}
        self.assertFalse({r.signal for r in records} & wearable_labels)


class PanelTests(unittest.TestCase):
    def setUp(self):
        try:
            from hyperion_mda import app, twin_view
            self.twin_view, self.app_module, self.window = twin_view, app, app.HyperionApp()
        except Exception as exc:  # no display / Tk unavailable
            raise unittest.SkipTest(f"Tk GUI unavailable: {exc}")
        self.window.geometry("1180x760")
        self.window.update()
        mb = self.app_module.messagebox
        self._orig = (mb.showerror, mb.showwarning)
        mb.showerror = mb.showwarning = lambda *_a: None

    def tearDown(self):
        mb = self.app_module.messagebox
        mb.showerror, mb.showwarning = self._orig
        self.window.destroy()

    def open_panel(self):
        self.window.open_channel_panel()
        panel = self.window.twin_panel
        panel.update()
        return panel

    COLS = ("channel", "status", "unit", "session", "region", "sampling")

    def rows(self, panel):
        return {iid: {col: panel.table.set(iid, col) for col in self.COLS} for iid in panel.table.get_children()}

    def assert_notice_visible(self, panel):
        self.assertTrue(panel.notice.winfo_ismapped())
        self.assertIn("NOT A VALIDATED PHYSIOLOGICAL DIGITAL TWIN", panel.notice.cget("text"))

    def test_notice_stays_visible_through_filtering_and_selection(self):
        panel = self.open_panel()
        self.assert_notice_visible(panel)
        for region in reg.REGIONS:
            panel.set_filter(region)
            panel.update()
            self.assert_notice_visible(panel)
        panel.set_filter(None)
        first = panel.table.get_children()[0]
        panel.table.selection_set(first)
        panel._show_channel()
        panel.update()
        self.assert_notice_visible(panel)

    def test_every_channel_shown_once_with_its_badge(self):
        panel = self.open_panel()
        rows = self.rows(panel)
        self.assertEqual(set(rows), {c.channel_id for c in reg.CHANNELS})
        for c in reg.CHANNELS:
            self.assertEqual(rows[c.channel_id]["status"], self.twin_view.badge(c.status))
            self.assertIn(c.status, panel.table.item(c.channel_id)["tags"])

    def test_rows_contain_no_assessment_wording_or_values_for_unavailable(self):
        panel = self.open_panel()
        for iid, values in self.rows(panel).items():
            text = " ".join(str(v) for v in values.values()).lower()
            for word in BANNED:
                self.assertNotIn(word, text, (iid, word))
            channel = next(c for c in reg.CHANNELS if c.channel_id == iid)
            if channel.status == reg.UNAVAILABLE:
                self.assertEqual(values["unit"], "—")      # no unit
                self.assertEqual(values["session"], "—")   # nothing loaded or generated

    def test_layout_legend_session_column_and_labels_readable(self):
        panel = self.open_panel()
        panel.geometry("1180x700")
        panel.update()
        bottom = panel.winfo_rooty() + panel.winfo_height()
        legend_labels = [w for w in self._descendants(panel)
                         if w.winfo_class() == "Label" and any(w.cget("text") == self.twin_view.badge(s)
                                                               for s in reg.STATUSES)]
        self.assertEqual(len(legend_labels), 4)
        for w in legend_labels:   # all four statuses, including Unavailable, inside the window
            self.assertTrue(w.winfo_ismapped())
            self.assertLessEqual(w.winfo_rooty() + w.winfo_height(), bottom, w.cget("text"))
        first = panel.table.get_children()[0]
        self.assertTrue(panel.table.bbox(first, "session"))   # visible without horizontal scrolling
        labels = [panel.canvas.bbox(i) for i in panel.canvas.find_withtag("region_label")]
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                overlap = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                self.assertFalse(overlap, (a, b))

    @staticmethod
    def _descendants(widget):
        stack, found = [widget], []
        while stack:
            w = stack.pop()
            found.append(w)
            stack.extend(w.winfo_children())
        return found

    def test_badge_colours_are_not_risk_colours(self):
        for colour in self.twin_view.BADGE_FG.values():
            r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
            self.assertFalse(r > g + 60 and r > b + 60, colour)   # not red / amber
            self.assertFalse(g > r + 60 and g > b + 60, colour)   # not green

    def test_lab_channels_show_session_counts_only_after_verified_load(self):
        panel = self.open_panel()
        lab_ids = [c.channel_id for c in reg.CHANNELS if c.lane == reg.LANE_NASA_LAB]
        self.assertTrue(all(self.rows(panel)[cid]["session"] == "not loaded" for cid in lab_ids))
        try:
            verified_cmp_file()
        except SourceFileMissingError as exc:
            self.skipTest(f"Real OSDR file not downloaded ({exc})")
        self.window.load_osdr()
        panel.update()
        rows = self.rows(panel)
        for analyte, unit in OSDR_CMP_PAIRS:
            recs = [r for r in self.window.records if (r.signal, r.unit) == (analyte, unit)]
            values = sum(r.has_value for r in recs)
            missing = len(recs) - values
            expected = f"{values} values loaded" + (f", {missing} NA" if missing else "")
            self.assertEqual(rows[f"osd575:{analyte}"]["session"], expected)
        # Wearable-model and unavailable channels never receive loaded values.
        for c in reg.CHANNELS:
            if c.lane != reg.LANE_NASA_LAB:
                self.assertEqual(rows[c.channel_id]["session"], "—")

    def test_main_window_scoring_unchanged_by_panel(self):
        try:
            verified_cmp_file()
        except SourceFileMissingError as exc:
            self.skipTest(f"Real OSDR file not downloaded ({exc})")
        self.window.load_osdr()
        before = [(r.row_number, r.z_score, r.score_note) for r in self.window.records]
        self.open_panel()
        self.window.twin_panel.set_filter(reg.REGION_BLOOD)
        self.window.update()
        after = [(r.row_number, r.z_score, r.score_note) for r in self.window.records]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
