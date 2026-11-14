"""Packaging and GUI-source checks (software behaviour only; not clinical validation).

By default these tests import ``hyperion_mda`` from ``src/``. To check an installed
copy, set ``HYPERION_TEST_INSTALLED=1`` and run from a directory outside the project.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from importlib import resources
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "simulated_telemetry.csv"  # synthetic, tests only
if os.environ.get("HYPERION_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(PROJECT / "src"))

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

from hyperion_mda.osdr_source import load_manifest  # noqa: E402


class PackagedFilesTests(unittest.TestCase):
    def test_provenance_manifest_is_packaged_and_complete(self):
        manifest = load_manifest()
        self.assertEqual(manifest["study_id"], "OSD-575")
        self.assertEqual(manifest["file_name"], "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv")
        self.assertRegex(manifest["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(manifest["file_size_bytes"], 25275)
        self.assertTrue(manifest["download_url"].startswith("https://osdr.nasa.gov/"))
        self.assertIsNone(manifest["license"])  # no licence is stated in the official record
        self.assertIn("not confirmed", manifest["license_status"])

    def test_no_data_files_ship_in_the_package(self):
        # The OSDR CSV is downloaded on demand (redistribution not confirmed) and the
        # synthetic sample lives only in tests/fixtures.
        data = resources.files("hyperion_mda").joinpath("data")
        shipped = [p.name for p in data.iterdir() if p.is_file()]
        shipped += [p.name for p in data.joinpath("osdr").iterdir() if p.is_file()]
        shipped += [p.name for p in data.joinpath("physionet").iterdir() if p.is_file()]
        self.assertEqual(sorted(shipped), ["OSD-575.provenance.json", "wrist-1.0.0.provenance.json"])


@unittest.skipIf(os.environ.get("HYPERION_TEST_INSTALLED") == "1", "source-tree check only")
class SourceTreeTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_package_data_declares_manifest_only(self):
        config = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["setuptools"]["package-data"]["hyperion_mda"],
                         ["data/osdr/*.json", "data/physionet/*.json"])

    def test_synthetic_sample_isolated_to_tests(self):
        copies = [p.relative_to(PROJECT).as_posix() for p in PROJECT.rglob("simulated_telemetry.csv")
                  if not any(part in {"build", ".venv", "dist"} or part.endswith(".egg-info") for part in p.parts)]
        self.assertEqual(copies, ["tests/fixtures/simulated_telemetry.csv"])
        source = "".join(p.read_text(encoding="utf-8") for p in (PROJECT / "src").rglob("*.py"))
        self.assertNotIn("simulated_telemetry", source)

    def test_manifest_json_is_valid(self):
        json.loads((PROJECT / "src/hyperion_mda/data/osdr/OSD-575.provenance.json").read_text(encoding="utf-8"))


class GuiSourceModeTests(unittest.TestCase):
    def setUp(self):
        try:
            from hyperion_mda import app
            self.app_module, self.window = app, app.HyperionApp()
        except Exception as exc:  # no display / Tk unavailable
            raise unittest.SkipTest(f"Tk GUI unavailable: {exc}")
        self.window.withdraw()
        self.dialogs: list[tuple[str, str]] = []
        mb = self.app_module.messagebox
        self._orig = (mb.showerror, mb.showwarning)
        mb.showerror = lambda t, m: self.dialogs.append((t, m))
        mb.showwarning = lambda t, m: self.dialogs.append((t, m))

    def tearDown(self):
        mb = self.app_module.messagebox
        mb.showerror, mb.showwarning = self._orig
        self.window.destroy()

    def buttons(self):
        found, stack = [], [self.window]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if w.winfo_class() == "TButton":
                found.append(w.cget("text"))
        return found

    def test_no_synthetic_runtime_button(self):
        self.assertEqual(sorted(self.buttons()),
                         ["Channel panel…", "FL simulation…", "Load NASA OSDR OSD-575 CMP (verified)",
                          "Open CSV…", "Recorded wearable (PhysioNet)…", "Simulated wearable…"])
        self.assertFalse(hasattr(self.window, "load_example"))  # no synthetic data path into the main table

    def test_initial_state_shows_no_data(self):
        self.assertIn("NO DATA LOADED", self.window.banner_text.get())
        self.assertEqual(self.window.table.get_children(), ())

    def test_user_csv_gets_unverified_banner_and_demo_rules(self):
        self.window.load_path(FIXTURE)
        self.assertIn("provenance not verified", self.window.banner_text.get())
        self.assertIn("illustrative display setting", self.window.footer_text.get())
        self.assertEqual(len(self.window.table.get_children()), 10)

    def test_horizontal_scroll_available(self):
        self.assertTrue(str(self.window.table.cget("xscrollcommand")))


if __name__ == "__main__":
    unittest.main()
