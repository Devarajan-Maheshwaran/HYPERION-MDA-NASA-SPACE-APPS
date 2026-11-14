"""M5 tests: PhysioNet Wrist PPG During Exercise (RECORDED, NON-ASTRONAUT) lane.

Synthetic WFDB fixtures written here are test-only. Real-file tests use the locally
verified PhysioNet cache and skip with a stated reason if it was never downloaded.
Software and methods checks only; no clinical or astronaut meaning.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
if os.environ.get("HYPERION_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(PROJECT / "src"))

from hyperion_mda import physionet_fetch  # noqa: E402
from hyperion_mda.adapters import AdapterError, WearableAdapter, WearableSample, validate_samples  # noqa: E402
from hyperion_mda.engine import TelemetryRecord  # noqa: E402
from hyperion_mda.physionet_source import (CACHE_ENV_VAR, PROVENANCE, PhysioNetChecksumError,  # noqa: E402
                                           PhysioNetMissingError, PhysioNetSourceError, load_manifest,
                                           verify_file, verified_record)
from hyperion_mda.wfdb_reader import (WfdbFormatError, beat_samples, read_annotations,  # noqa: E402
                                      read_header, read_signals, to_physical)

PKG = PROJECT / "src" / "hyperion_mda"


def real_cache_or_skip():
    try:
        verified_record(load_manifest()["records"][0])
    except PhysioNetMissingError as exc:
        raise unittest.SkipTest(f"PhysioNet files not downloaded ({exc}). Run: python -m hyperion_mda.physionet_fetch")


# --------------------------------------------------------------------------- manifest and gate
class ManifestTests(unittest.TestCase):
    def test_manifest_records_terms_and_pins(self):
        m = load_manifest()
        self.assertEqual((m["dataset"], m["version"]), ("Wrist PPG During Exercise", "1.0.0"))
        self.assertEqual(m["license"], "Open Data Commons Attribution License v1.0")
        self.assertEqual(len(m["files"]), 59)
        self.assertEqual(len(m["records"]), 19)
        self.assertRegex(m["sha256sums_file_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(all(len(h) == 64 for h in m["files"].values()))
        self.assertIn("NOT astronaut data", m["scope_note"])
        self.assertIn("Never bundled or redistributed", m["redistribution_policy_of_this_project"])
        for rec in m["records"]:
            for ext in (".hea", ".dat", ".atr"):
                self.assertIn(rec + ext, m["files"])

    def test_no_physionet_data_ships_in_package(self):
        from importlib import resources
        folder = resources.files("hyperion_mda").joinpath("data", "physionet")
        self.assertEqual(sorted(p.name for p in folder.iterdir() if p.is_file()), ["wrist-1.0.0.provenance.json"])


class GateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_missing_and_mismatched_files(self):
        m = load_manifest()
        with self.assertRaises(PhysioNetMissingError):
            verify_file(self.dir, "s1_walk.hea", m)
        (self.dir / "s1_walk.hea").write_bytes(b"tampered")
        with self.assertRaises(PhysioNetChecksumError):
            verify_file(self.dir, "s1_walk.hea", m)
        with self.assertRaises(PhysioNetSourceError):
            verify_file(self.dir, "not_listed.dat", m)

    def _fake_source(self, files: dict[str, bytes]):
        src = self.dir / "src"
        src.mkdir()
        for name, data in files.items():
            (src / name).write_bytes(data)
        sums = "".join(f"{hashlib.sha256(d).hexdigest()} {n}\n" for n, d in files.items()).encode()
        (src / "SHA256SUMS.txt").write_bytes(sums)
        manifest = {"dataset": "x", "version": "1", "license": "x", "records": ["r"], "files_base_url": "x",
                    "files": {n: hashlib.sha256(d).hexdigest() for n, d in files.items()},
                    "sha256sums_file_sha256": hashlib.sha256(sums).hexdigest()}
        return src, manifest

    def test_fetch_verifies_every_file(self):
        src, manifest = self._fake_source({"a.hea": b"header", "a.dat": b"\x00\x01"})
        with mock.patch.object(physionet_fetch, "load_manifest", return_value=manifest):
            out = physionet_fetch.fetch(self.dir / "cache", base_url=src.as_uri() + "/", progress=None)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["a.dat", "a.hea"])

    def test_fetch_rejects_changed_sums_file_before_downloading(self):
        src, manifest = self._fake_source({"a.hea": b"header"})
        manifest["sha256sums_file_sha256"] = "0" * 64
        with mock.patch.object(physionet_fetch, "load_manifest", return_value=manifest):
            with self.assertRaises(PhysioNetChecksumError):
                physionet_fetch.fetch(self.dir / "cache", base_url=src.as_uri() + "/", progress=None)
        self.assertEqual([p for p in (self.dir / "cache").iterdir()], [])

    def test_fetch_rejects_tampered_file_and_leaves_nothing(self):
        src, manifest = self._fake_source({"a.hea": b"header"})
        (src / "a.hea").write_bytes(b"HEADER")                         # served bytes differ from pinned hash
        with mock.patch.object(physionet_fetch, "load_manifest", return_value=manifest):
            with self.assertRaises(PhysioNetChecksumError):
                physionet_fetch.fetch(self.dir / "cache", base_url=src.as_uri() + "/", progress=None)
        self.assertEqual([p for p in (self.dir / "cache").iterdir()], [])

    def test_cli_reports_failure(self):
        with mock.patch.object(physionet_fetch, "fetch", side_effect=PhysioNetChecksumError("boom")):
            self.assertEqual(physionet_fetch.main(["--cache-dir", str(self.dir)]), 1)


# --------------------------------------------------------------------------- WFDB reader (synthetic)
def _signed16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def write_record(folder: Path, signals: list[list[int]], fmt: int = 16, bad_checksum: bool = False) -> tuple[Path, Path]:
    n = len(signals[0])
    lines = [f"rec {len(signals)} 256 {n}"]
    for i, sig in enumerate(signals):
        cs = _signed16(sum(sig)) + (1 if bad_checksum and i == 0 else 0)
        lines.append(f"rec.dat {fmt} 2.0(10)/mV 0 0 {sig[0]} {cs} 0 sig_{i}")
    lines.append("#Synthetic test record")
    hea = folder / "rec.hea"
    hea.write_text("\n".join(lines) + "\n", encoding="ascii")
    dat = folder / "rec.dat"
    dat.write_bytes(b"".join(struct.pack("<h", signals[c][k]) for k in range(n) for c in range(len(signals))))
    return hea, dat


def ann_bytes(words: list[tuple[int, int]], extra: bytes = b"") -> bytes:
    return b"".join(struct.pack("<H", (code << 10) | value) for code, value in words) + extra


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_reads_and_verifies_checksums(self):
        sigs = [[10, -3, 7, 32000], [-5, 0, 1, 2]]
        hea, dat = write_record(self.dir, sigs)
        h = read_header(hea)
        self.assertEqual((h.n_signals, h.fs_hz, h.n_samples), (2, 256.0, 4))
        self.assertEqual(h.comments, ("Synthetic test record",))
        ch = read_signals(h, dat)
        self.assertEqual([list(c) for c in ch], sigs)
        self.assertEqual(to_physical(h.signals[0], ch[0])[:2], [0.0, -6.5])     # (raw - 10) / 2.0

    def test_checksum_mismatch_rejected(self):
        hea, dat = write_record(self.dir, [[1, 2, 3]], bad_checksum=True)
        with self.assertRaises(WfdbFormatError):
            read_signals(read_header(hea), dat)

    def test_size_mismatch_and_unsupported_format(self):
        hea, dat = write_record(self.dir, [[1, 2, 3]])
        dat.write_bytes(dat.read_bytes()[:-2])
        with self.assertRaises(WfdbFormatError):
            read_signals(read_header(hea), dat)
        hea, _ = write_record(self.dir, [[1, 2, 3]], fmt=212)
        with self.assertRaises(WfdbFormatError):
            read_header(hea)

    def test_annotations_metadata_skip_notes_and_beats(self):
        aux = b"## time resolution: 256"
        data = (ann_bytes([(22, 0), (63, len(aux))]) + aux + b"\x00"          # NOTE + AUX (padded)
                + ann_bytes([(59, 0)]) + struct.pack("<HH", 0xFFFF, 0xFFFF)   # SKIP -1
                + ann_bytes([(0, 1), (1, 199), (62, 1), (1, 211), (22, 50), (1, 30), (0, 0)]))
        path = self.dir / "a.atr"
        path.write_bytes(data)
        anns = read_annotations(path)
        self.assertEqual([(a.sample, a.code) for a in anns], [(0, 22), (0, 0), (199, 1), (410, 1), (460, 22), (490, 1)])
        self.assertEqual(beat_samples(anns), [199, 410, 490])           # metadata and notes excluded


# --------------------------------------------------------------------------- real verified files
class RealFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        real_cache_or_skip()

    def test_all_records_verify_and_match_header_checksums(self):
        total_beats = 0
        for rec in load_manifest()["records"]:
            v = verified_record(rec)
            h = read_header(v.header)
            self.assertEqual((h.n_signals, h.fs_hz), (15, 256.0))
            read_signals(h, v.signals)                                      # raises on any checksum mismatch
            total_beats += len(beat_samples(read_annotations(v.annotations)))
        # Equal to the official wfdb package's 'N' annotations (cross-checked in a scratch env, 2026-11-14).
        self.assertEqual(total_beats, 11388)

    def test_units_preserved_from_header(self):
        h = read_header(verified_record("s1_walk").header)
        units = {s.description: s.units for s in h.signals}
        self.assertEqual(units["chest_ecg"], "mV")
        self.assertEqual(units["wrist_low_noise_accelerometer_x"], "ms^-2")
        self.assertEqual(units["sample_times_for_all_signals_apart_from_ecg"], "s")


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        real_cache_or_skip()
        from hyperion_mda.physionet_adapter import RecordedPhysioNetAdapter
        cls.Adapter = RecordedPhysioNetAdapter
        cls.adapter = RecordedPhysioNetAdapter("s3_run")

    def test_labels_provenance_and_interface(self):
        a = self.adapter
        self.assertIsInstance(a, WearableAdapter)
        self.assertFalse(a.is_real_device)
        self.assertEqual(a.provenance, PROVENANCE)
        self.assertIn("non-astronaut", a.name)
        for spec in a.channels():
            self.assertTrue(spec.label.startswith("RECORDED non-astronaut"))
            self.assertIn(spec.unit, ("mV", "ms^-2"))

    def test_read_uses_uniform_sample_index_and_validates(self):
        samples = self.adapter.read(10.0, 11.0)
        self.assertEqual(len(samples), 256 * 5)
        ecg = [s for s in samples if s.channel_id == "physionet:chest_ecg"]
        self.assertEqual([s.t_s for s in ecg[:3]], [10.0, 10.0 + 1 / 256, 10.0 + 2 / 256])
        self.assertEqual(validate_samples(samples, self.adapter), samples)
        self.assertIsInstance(samples[0], WearableSample)
        self.assertNotIsInstance(samples[0], TelemetryRecord)

    def test_missing_cache_raises_adapter_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AdapterError):
                self.Adapter("s3_run", Path(tmp))
        with self.assertRaises(AdapterError):
            self.Adapter("s7_walk")                                         # not a record in this dataset


class LaneSeparationTests(unittest.TestCase):
    def test_recorded_lane_imports_no_nasa_fl_or_simulated_modules(self):
        banned = {"engine", "osdr_cmp", "osdr_source", "osdr_fetch", "fl_sim", "fl_view", "sim_wearable"}
        for name in ("physionet_source", "physionet_fetch", "physionet_adapter", "wfdb_reader", "dsp_hr",
                     "recorded_view"):
            tree = ast.parse((PKG / f"{name}.py").read_text(encoding="utf-8"))
            found = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    found.add((node.module or "").split(".")[-1])
                    found |= {a.name for a in node.names}
            self.assertFalse(found & banned, (name, found & banned))

    def test_core_app_does_not_import_numpy_or_scipy_at_module_level(self):
        for name in ("app", "recorded_view", "physionet_adapter", "wfdb_reader", "physionet_source"):
            tree = ast.parse((PKG / f"{name}.py").read_text(encoding="utf-8"))
            top = {(n.module or "").split(".")[0] for n in tree.body if isinstance(n, ast.ImportFrom)}
            top |= {a.name.split(".")[0] for n in tree.body if isinstance(n, ast.Import) for a in n.names}
            self.assertFalse(top & {"numpy", "scipy"}, name)


class HRCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        real_cache_or_skip()
        try:
            from hyperion_mda import dsp_hr
        except ImportError as exc:
            raise unittest.SkipTest(f"numpy/scipy unavailable: {exc}")
        cls.dsp = dsp_hr

    def test_parameters_fixed(self):
        self.assertEqual((self.dsp.WINDOW_S, self.dsp.STEP_S, self.dsp.BAND_HZ), (8.0, 2.0, (0.5, 4.0)))

    def test_deterministic_and_finite(self):
        a, b = self.dsp.check_record("s9_walk"), self.dsp.check_record("s9_walk")
        self.assertEqual(a.errors_bpm, b.errors_bpm)
        self.assertEqual(a.compared + a.no_ppg_estimate + a.no_reference, a.windows)
        self.assertTrue(all(math.isfinite(e) for e in a.errors_bpm))

    def test_reference_rate_matches_independent_calculation(self):
        import statistics
        from hyperion_mda.physionet_adapter import RecordedPhysioNetAdapter
        beats = RecordedPhysioNetAdapter("s9_walk").beats
        win = [b for b in beats if 0 <= b < 8 * 256]
        expected = 60 / statistics.median([(y - x) / 256 for x, y in zip(win, win[1:])])
        import numpy as np
        self.assertAlmostEqual(self.dsp._rate_from_intervals(np.asarray(win), 256.0), expected)


class GuiTests(unittest.TestCase):
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

    def test_recorded_window_labels_and_failure_without_data(self):
        self.window.open_recorded()
        rw = self.window.recorded_window
        rw.update()
        self.assertIn("NON-ASTRONAUT", rw.banner.cget("text"))
        self.assertIn("not astronaut data", rw.banner.cget("text"))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {CACHE_ENV_VAR: tmp}):
            rw.play()
        self.assertTrue(any("No other data was substituted" in str(d) for d in self.dialogs))
        self.assertIsNone(rw.player)

    def test_play_and_check_leave_nasa_records_untouched(self):
        real_cache_or_skip()
        w = self.window
        try:
            from hyperion_mda.osdr_source import verified_cmp_file
            verified_cmp_file()
            w.load_osdr()
        except Exception:
            pass
        before = [(r.row_number, r.value, r.z_score) for r in w.records]
        w.open_recorded()
        rw = w.recorded_window
        rw.record.set("s3_run")
        rw.play()
        rw.player.start(); rw.player._tick(); rw.player.pause()
        self.assertIn("RECORDED-NON-ASTRONAUT", rw.player.position_text.get())
        try:
            import numpy, scipy  # noqa: F401
            rw.run_check()
            self.assertEqual(len(rw.table.get_children()), 19)
            self.assertIn("Parameters:", rw.note.get())
        except ImportError:
            pass
        self.assertEqual(before, [(r.row_number, r.value, r.z_score) for r in w.records])
        self.assertEqual(self.dialogs, [])


if __name__ == "__main__":
    unittest.main()
