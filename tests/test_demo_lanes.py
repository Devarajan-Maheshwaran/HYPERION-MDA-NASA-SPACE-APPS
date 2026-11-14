"""Demo-lane tests: NASA lab data vs SIMULATED wearable playback vs FL SIMULATION.

Software checks only. The simulated and toy values are generated and have no
physiological, clinical or astronaut meaning.
"""

from __future__ import annotations

import ast
import math
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if os.environ.get("HYPERION_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(PROJECT / "src"))

from hyperion_mda import fl_sim, sim_wearable  # noqa: E402
from hyperion_mda import signal_registry as reg  # noqa: E402
from hyperion_mda.adapters import (AdapterError, PlaybackSession, SimulatedPlaybackAdapter,  # noqa: E402
                                   WearableAdapter, WearableSample, validate_samples)
from hyperion_mda.engine import TelemetryRecord  # noqa: E402
from hyperion_mda.osdr_source import SourceFileMissingError, verified_cmp_file  # noqa: E402

PKG = PROJECT / "src" / "hyperion_mda"
NASA_MODULES = {"engine", "osdr_cmp", "osdr_source", "osdr_fetch"}
SIM_MODULES = {"sim_wearable", "adapters", "playback_view"}
FL_MODULES = {"fl_sim", "fl_view"}


def imported_modules(name: str) -> set[str]:
    tree = ast.parse((PKG / f"{name}.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[-1])
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            found |= {a.name.split(".")[-1] for a in node.names}
    return found


class LaneSeparationTests(unittest.TestCase):
    def test_simulated_lane_does_not_import_nasa_or_fl(self):
        for name in SIM_MODULES:
            self.assertFalse(imported_modules(name) & (NASA_MODULES | FL_MODULES), name)

    def test_fl_lane_does_not_import_nasa_or_wearable(self):
        for name in FL_MODULES:
            self.assertFalse(imported_modules(name) & (NASA_MODULES | SIM_MODULES | {"signal_registry"}), name)

    def test_nasa_lane_does_not_import_demo_lanes(self):
        for name in NASA_MODULES:
            self.assertFalse(imported_modules(name) & (SIM_MODULES | FL_MODULES), name)

    def test_wearable_samples_are_a_different_type_from_nasa_records(self):
        sample = SimulatedPlaybackAdapter().read(0, 1)[0]
        self.assertIsInstance(sample, WearableSample)
        self.assertNotIsInstance(sample, TelemetryRecord)

    def test_toy_fl_data_is_generated_and_unrelated_to_nasa_analytes(self):
        clients = fl_sim.make_toy_clients(3)
        self.assertTrue(all(isinstance(p, tuple) and len(p) == 2 for c in clients for p in c.points))
        self.assertTrue(all(c.client_id.startswith("client-") for c in clients))


class SimulatedLabellingTests(unittest.TestCase):
    def test_every_sample_and_channel_is_labelled_simulated(self):
        adapter = SimulatedPlaybackAdapter()
        self.assertFalse(adapter.is_real_device)
        self.assertEqual(adapter.provenance, "SIMULATED")
        for spec in adapter.channels():
            self.assertTrue(spec.label.startswith("SIMULATED"))
            self.assertIn("(simulated)", spec.unit)
        samples = adapter.read(0, adapter.duration_s())
        self.assertTrue(samples)
        self.assertTrue(all(s.provenance == "SIMULATED" for s in samples))

    def test_registry_lists_simulated_channels_with_simulated_status(self):
        sim = [c for c in reg.CHANNELS if c.lane == reg.LANE_SIMULATED]
        self.assertEqual({c.channel_id for c in sim}, {c.channel_id for c in sim_wearable.CHANNELS})
        self.assertTrue(all(c.status == reg.SIMULATED for c in sim))


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.adapter = SimulatedPlaybackAdapter()
        self.session = PlaybackSession(self.adapter, window_s=60, step_s=1)

    def test_start_tick_pause_reset(self):
        s = self.session
        self.assertFalse(s.tick())                      # not running: no movement
        s.start()
        for _ in range(5):
            self.assertTrue(s.tick())
        self.assertEqual(s.position_s, 5)
        s.pause()
        self.assertFalse(s.tick())
        self.assertEqual(s.position_s, 5)
        s.reset()
        self.assertEqual((s.position_s, s.running), (0.0, False))

    def test_seek_clamps_and_rejects_bad_input(self):
        s = self.session
        s.seek(42)
        self.assertEqual(s.position_s, 42)
        s.seek(-5)
        self.assertEqual(s.position_s, 0)
        s.seek(10_000)
        self.assertEqual(s.position_s, self.adapter.duration_s())
        for bad in ("abc", None, float("nan"), float("inf")):
            with self.assertRaises(AdapterError):
                s.seek(bad)

    def test_stops_at_end_and_restarts_from_zero(self):
        s = self.session
        s.seek(self.adapter.duration_s() - 2)
        s.start()
        s.tick(); s.tick()
        self.assertTrue(s.finished)
        self.assertFalse(s.running)
        s.start()                                        # restarting after the end resets
        self.assertEqual(s.position_s, 0)

    def test_window_is_deterministic_and_bounded(self):
        s = self.session
        s.seek(100)
        first = s.visible()
        self.assertEqual(first, s.visible())
        self.assertTrue(all(40 <= x.t_s < 100 for x in first))

    def test_sample_rates_match_channel_specs(self):
        samples = self.adapter.read(0, 10)
        counts = {c.channel_id: sum(s.channel_id == c.channel_id for s in samples) for c in self.adapter.channels()}
        self.assertEqual(counts, {"sim:hr-like": 10, "sim:skin-temp-like": 5, "sim:accel-like": 20})

    def test_session_requires_an_adapter(self):
        with self.assertRaises(AdapterError):
            PlaybackSession(object())
        self.assertIsInstance(self.adapter, WearableAdapter)


class AdapterValidationTests(unittest.TestCase):
    def setUp(self):
        self.adapter = SimulatedPlaybackAdapter()
        self.good = self.adapter.read(0, 3)

    def check_rejected(self, samples, fragment):
        with self.assertRaises(AdapterError) as ctx:
            validate_samples(samples, self.adapter)
        self.assertIn(fragment, str(ctx.exception))

    def test_good_samples_pass(self):
        self.assertEqual(validate_samples(self.good, self.adapter), self.good)

    def test_malformed_inputs_rejected_with_messages(self):
        g = self.good[0]
        self.check_rejected([replace(g, value=math.nan)], "Non-finite")
        self.check_rejected([replace(g, channel_id="sim:unknown")], "Unknown channel")
        self.check_rejected([replace(g, unit="bpm")], "does not match")
        self.check_rejected([g, replace(g, t_s=g.t_s)], "not increasing")
        self.check_rejected([replace(g, provenance="MEASURED")], "provenance")
        self.check_rejected([replace(g, t_s=-1.0)], "Invalid time")
        self.check_rejected(["not a sample"], "Unexpected sample type")

    def test_invalid_read_window(self):
        for a, b in ((-1, 5), (5, 1), (0, math.inf)):
            with self.assertRaises(AdapterError):
                self.adapter.read(a, b)


class FLSimulationTests(unittest.TestCase):
    def test_reproducible(self):
        a, b = fl_sim.run_fedavg(4, 3), fl_sim.run_fedavg(4, 3)
        self.assertEqual([l.global_weights for l in a.logs], [l.global_weights for l in b.logs])

    def test_structure_counts(self):
        run = fl_sim.run_fedavg(5, 4)
        self.assertEqual(len(run.logs), 4)
        self.assertTrue(all(len(l.updates) == 5 for l in run.logs))
        self.assertEqual(len(run.client_sizes), 5)

    def test_fedavg_is_sample_weighted_average(self):
        updates = [((1.0, 0.0, 2.0), 10), ((3.0, 4.0, 0.0), 30)]
        self.assertEqual(fl_sim.fedavg(updates), (2.5, 3.0, 0.5))
        with self.assertRaises(ValueError):
            fl_sim.fedavg([((1.0, 1.0, 1.0), 0)])

    def test_each_round_global_equals_fedavg_of_client_updates(self):
        run = fl_sim.run_fedavg(3, 3)
        for log in run.logs:
            expected = fl_sim.fedavg([(u.weights, u.n) for u in log.updates])
            self.assertEqual(log.global_weights, expected)

    def test_server_step_receives_only_weights_and_counts(self):
        import inspect
        self.assertEqual(list(inspect.signature(fl_sim.fedavg).parameters), ["updates"])

    def test_invalid_parameters_rejected(self):
        for bad in ((1, 3), (9, 3), (3, 0), (3, 31), ("x", 3), (3, "2.5"), (None, 3)):
            with self.assertRaises(ValueError):
                fl_sim.validate_params(*bad)


class GuiDemoFlowTests(unittest.TestCase):
    def setUp(self):
        try:
            from hyperion_mda import app
            self.app_module, self.window = app, app.HyperionApp()
        except Exception as exc:
            raise unittest.SkipTest(f"Tk GUI unavailable: {exc}")
        self.window.geometry("1180x760")
        self.window.update()
        self.dialogs = []
        import tkinter.messagebox as mb
        self.mb = mb
        self._orig = (mb.showerror, mb.showwarning)
        mb.showerror = lambda *a, **k: self.dialogs.append(a)
        mb.showwarning = lambda *a, **k: self.dialogs.append(a)

    def tearDown(self):
        self.mb.showerror, self.mb.showwarning = self._orig
        self.window.destroy()

    def test_full_flow_keeps_nasa_records_untouched(self):
        w = self.window
        try:
            verified_cmp_file()
            w.load_osdr()
            self.assertIn("NASA LAB DATA", w.banner_text.get())
            self.assertIn("sparse laboratory measurements", w.banner_text.get())
            self.assertIn("NASA lab data", w.status.get())
        except SourceFileMissingError:
            pass  # the separation checks below still apply to an empty main table
        before = [(r.row_number, r.value, r.z_score, r.score_note) for r in w.records]
        rows_before = len(w.table.get_children())
        w.open_playback()
        pw = w.playback_window
        pw.start()
        for _ in range(12):
            pw._tick()
        pw.pause()
        w.open_fl()
        w.fl_window.clients.set("4")
        w.fl_window.rounds.set("3")
        w.fl_window.run_simulation()
        w.update()
        self.assertEqual(before, [(r.row_number, r.value, r.z_score, r.score_note) for r in w.records])
        self.assertEqual(rows_before, len(w.table.get_children()))
        self.assertEqual(self.dialogs, [])

    def test_playback_window_labels_and_controls(self):
        self.window.open_playback()
        pw = self.window.playback_window
        pw.update()
        self.assertTrue(pw.banner.winfo_ismapped())
        self.assertIn("SIMULATED", pw.banner.cget("text"))
        titles = [pw.canvas.itemcget(i, "text") for i in pw.canvas.find_withtag("strip_title")]
        self.assertEqual(len(titles), 3)
        self.assertTrue(all(t.startswith("SIMULATED") for t in titles))
        pw.start(); pw._tick(); pw._tick(); pw.pause()
        self.assertIn("t = 2 s", pw.position_text.get())
        self.assertIn("SIMULATED", pw.position_text.get())
        pw.seek("not-a-time")
        self.assertTrue(self.dialogs)                           # readable error, no crash
        pw.reset()
        self.assertIn("t = 0 s", pw.position_text.get())

    def test_playback_reports_malformed_adapter_data(self):
        from hyperion_mda.playback_view import PlaybackWindow

        class BrokenAdapter(SimulatedPlaybackAdapter):
            name = "broken test adapter"

            def read(self, t_start, t_end):
                return [replace(s, value=math.nan) for s in super().read(t_start, t_end)]

        pw = PlaybackWindow(self.window, BrokenAdapter())
        pw.seek(10)
        pw.update()
        self.assertTrue(any("Non-finite" in str(d) for d in self.dialogs))
        self.assertFalse(pw.session.running)
        pw.destroy()

    def test_fl_window_runs_and_validates(self):
        self.window.open_fl()
        fw = self.window.fl_window
        fw.update()
        self.assertIn("FL SIMULATION", fw.banner.cget("text"))
        self.assertIn("not Flower", fw.banner.cget("text"))
        self.assertIn("no privacy protection", fw.banner.cget("text"))
        fw.clients.set("4"); fw.rounds.set("3")
        fw.run_simulation()
        fw.update()
        self.assertEqual(len(fw.table.get_children()), 12)
        self.assertEqual(len(fw.flow.find_withtag("client")), 4)
        self.assertTrue(fw.flow.find_withtag("server"))
        summary = fw.summary.get().lower()
        for word in ("accuracy", "performance", "improve", "astronaut data", "habitat"):
            self.assertNotIn(word, summary.replace("no clinical or astronaut meaning", ""))
        fw.clients.set("1")
        fw.run_simulation()
        self.assertTrue(any("Clients must be between" in str(d) for d in self.dialogs))
        self.assertEqual(len(fw.table.get_children()), 12)      # previous run kept; nothing faked


if __name__ == "__main__":
    unittest.main()
