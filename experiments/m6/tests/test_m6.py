"""M6 tests: leakage, ECG exclusion, model and metric correctness, reproducibility.

Run from the project root:
    .venv\\Scripts\\python -m unittest discover -s experiments/m6/tests -v
Real-data tests skip with a stated reason if the PhysioNet cache is absent.
Software verification only; no clinical or astronaut validation.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from scipy.optimize import check_grad

M6 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(M6))

import m6_data  # noqa: E402
import m6_features  # noqa: E402
from m6_metrics import aggregate, bootstrap_indices, classification_summary, confusion, hr_stats  # noqa: E402
from m6_models import (LogisticClassifier, MajorityClassifier, MeanRegressor, RidgeRegressor,  # noqa: E402
                       Standardizer, lopo_folds, lopo_predict)

CFG = m6_data.load_config()
FS = 256.0
WIN = int(CFG["windows"]["window_s"] * FS)


def cache_available() -> bool:
    try:
        m6_data.verified_record("s9_walk")
        return True
    except Exception:
        return False


REAL = cache_available()
SKIP_REAL = "PhysioNet cache not present (run hyperion_mda.physionet_fetch)"


class FeatureTests(unittest.TestCase):
    def test_spectral_peak_recovers_known_frequency(self):
        t = np.arange(WIN) / FS
        for hz in (0.9, 1.5, 2.6):
            sig = np.sin(2 * np.pi * hz * t) + 0.05 * np.random.default_rng(1).standard_normal(WIN)
            feats, dom, degenerate = m6_features.ppg_window_features(sig, FS, CFG)
            self.assertFalse(degenerate)
            self.assertLessEqual(abs(dom - hz), CFG["spectrum"]["resolution_hz"])
            self.assertAlmostEqual(float(feats[:-1].sum()), 1.0, places=9)

    def test_m5_peak_method_recovers_known_rate(self):
        t = np.arange(WIN) / FS
        sig = m6_features.m5_filtered_ppg(np.sin(2 * np.pi * 1.25 * t) ** 21, FS)  # sharp pulses, 75 / min
        self.assertAlmostEqual(m6_features.a1_estimate(sig, FS), 75.0, delta=1.0)

    def test_flat_window_is_degenerate_not_nan(self):
        feats, dom, degenerate = m6_features.ppg_window_features(np.zeros(WIN), FS, CFG)
        self.assertTrue(degenerate)
        self.assertTrue(np.all(np.isfinite(feats)))

    def test_accel_features_have_no_raw_amplitude(self):
        acc = np.random.default_rng(2).standard_normal((WIN, 3)) + [0, 0, 9.8]
        a, _ = m6_features.accel_window_features(acc, FS, CFG)
        b, _ = m6_features.accel_window_features(7.3 * acc, FS, CFG)
        np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-12)
        self.assertEqual(a.size, len(m6_features.ACCEL_FEATURE_NAMES))

    def test_ppg_features_are_scale_invariant(self):
        x = np.random.default_rng(3).standard_normal(WIN)
        a = m6_features.ppg_window_features(x, FS, CFG)[0]
        np.testing.assert_allclose(a, m6_features.ppg_window_features(1e4 * x, FS, CFG)[0], rtol=1e-9)
        self.assertEqual(a.size, len(m6_features.PPG_FEATURE_NAMES))


class EcgExclusionTests(unittest.TestCase):
    def test_inputs_type_has_no_ecg_or_reference_field(self):
        names = {f.name for f in dataclasses.fields(m6_data.RecordInputs)}
        self.assertEqual(names, {"record", "participant", "activity", "header_comment", "fs", "n_samples", "ppg", "accel"})

    def test_feature_extractor_takes_no_reference(self):
        self.assertEqual(list(inspect.signature(m6_features.record_features).parameters), ["inputs", "starts", "cfg"])

    def test_reference_loader_never_reads_signals(self):
        with mock.patch.object(m6_data, "read_signals", side_effect=AssertionError("signal file read")):
            if REAL:
                self.assertGreater(m6_data.load_reference("s9_walk").size, 0)

    @unittest.skipUnless(REAL, SKIP_REAL)
    def test_features_unchanged_when_ecg_waveform_is_replaced_by_noise(self):
        real_read = m6_data.read_signals
        verified = m6_data.verified_record("s9_walk")
        header = m6_data.read_header(verified.header)
        ecg_index = next(s.index for s in header.signals if s.description == m6_data.ECG_SIGNAL)

        def noisy(h, path):
            raw = real_read(h, path)
            raw[ecg_index] = type(raw[ecg_index])(raw[ecg_index].typecode,
                                                   np.random.default_rng(4).integers(-30000, 30000, len(raw[ecg_index])).tolist())
            return raw

        starts = m6_data.window_starts(header.n_samples, FS, 8.0, 2.0)
        clean = m6_features.record_features(m6_data.load_inputs("s9_walk"), starts, CFG)
        with mock.patch.object(m6_data, "read_signals", noisy):
            perturbed = m6_features.record_features(m6_data.load_inputs("s9_walk"), starts, CFG)
        for key in ("ppg", "accel", "a1", "a2"):
            np.testing.assert_array_equal(clean[key], perturbed[key])


class FoldTests(unittest.TestCase):
    PARTICIPANTS = ["s1", "s2", "s3", "s4", "s5", "s6", "s8", "s9"]

    def test_eight_disjoint_folds_cover_everyone_once(self):
        folds = lopo_folds(self.PARTICIPANTS[::-1] * 3)
        self.assertEqual([t for t, _ in folds], self.PARTICIPANTS)
        for test, train in folds:
            self.assertNotIn(test, train)
            self.assertEqual(sorted(train + [test]), self.PARTICIPANTS)

    def test_fit_never_sees_test_participant_and_each_row_predicted_once(self):
        rng = np.random.default_rng(5)
        groups = np.repeat(self.PARTICIPANTS, 20)
        X = np.column_stack([np.arange(groups.size), rng.standard_normal(groups.size)])
        seen = {}

        class Spy:
            def fit(self, X, y):
                self.rows = set(X[:, 0].astype(int))
                return self

            def predict(self, X):
                seen[tuple(X[:, 0].astype(int))] = self.rows
                return X[:, 0]

        pred, folds = lopo_predict(X, np.zeros(groups.size), groups, Spy)
        np.testing.assert_array_equal(pred, X[:, 0])  # every row predicted exactly once, in place
        for test_rows, train_rows in seen.items():
            self.assertTrue(set(test_rows).isdisjoint(train_rows))
            self.assertEqual(len({groups[i] for i in test_rows}), 1)
            self.assertNotIn(groups[test_rows[0]], {groups[i] for i in train_rows})

    def test_overlapping_windows_stay_inside_their_record_and_fold(self):
        starts = m6_data.window_starts(100 * 256, FS, 8.0, 2.0)
        self.assertEqual(int(starts[-1]) + WIN, 100 * 256 - (100 * 256 - WIN) % 512)
        self.assertTrue(np.all(starts + WIN <= 100 * 256))
        # windows overlapping in time share a record, hence a participant, hence a test fold
        groups = np.array(["s1"] * starts.size + ["s2"] * starts.size)
        for test, train in lopo_folds(list(groups)):
            idx = np.where(groups == test)[0]
            self.assertEqual(idx.size, starts.size)

    def test_scaler_and_model_fitted_on_training_rows_only(self):
        rng = np.random.default_rng(6)
        groups = np.repeat(self.PARTICIPANTS, 30)
        X = rng.standard_normal((groups.size, 4))
        y = X @ [1.0, -2.0, 0.5, 0.0] + rng.standard_normal(groups.size)
        _, folds_a = lopo_predict(X, y, groups, lambda: RidgeRegressor(1.0))
        X2 = X.copy()
        X2[groups == "s4"] *= 1e6  # corrupt one participant
        _, folds_b = lopo_predict(X2, y, groups, lambda: RidgeRegressor(1.0))
        fa, fb = folds_a[3], folds_b[3]
        self.assertEqual(fa.test_participant, "s4")
        np.testing.assert_array_equal(fa.model.coef_, fb.model.coef_)
        np.testing.assert_array_equal(fa.model.scaler_.mean_, X[groups != "s4"].mean(axis=0))

    def test_no_random_split_anywhere(self):
        for mod in (m6_data, m6_features, sys.modules["m6_models"]):
            src = inspect.getsource(mod)
            self.assertNotIn("shuffle", src)
            self.assertNotIn("permutation", src)


class ModelTests(unittest.TestCase):
    def test_ridge_matches_closed_form_reference(self):
        rng = np.random.default_rng(7)
        X = rng.standard_normal((50, 3))
        y = rng.standard_normal(50)
        m = RidgeRegressor(2.0).fit(X, y)
        Z = Standardizer().fit(X).transform(X)
        A = np.vstack([Z, np.sqrt(2.0) * np.eye(3)])
        b = np.concatenate([y - y.mean(), np.zeros(3)])
        np.testing.assert_allclose(m.coef_, np.linalg.lstsq(A, b, rcond=None)[0], rtol=1e-10)

    def test_logistic_gradient_and_separable_fit(self):
        rng = np.random.default_rng(8)
        X = np.vstack([rng.normal(-3, 1, (40, 2)), rng.normal(3, 1, (40, 2)), rng.normal([3, -3], 1, (40, 2))])
        y = np.repeat([0, 1, 2], 40)
        clf = LogisticClassifier(3, 1.0, 10000, 1e-5)
        Z = Standardizer().fit(X).transform(X)
        Y = np.eye(3)[y]
        theta = rng.standard_normal(2 * 3 + 3)
        err = check_grad(lambda t: clf._objective(t, Z, Y)[0], lambda t: clf._objective(t, Z, Y)[1], theta)
        self.assertLess(err, 1e-4)
        clf.fit(X, y)
        self.assertTrue(clf.converged_)
        self.assertGreater(np.mean(clf.predict(X) == y), 0.95)

    def test_trivial_baselines(self):
        self.assertEqual(MajorityClassifier(3).fit(None, np.array([2, 2, 1, 0])).predict(np.zeros(2)).tolist(), [2, 2])
        self.assertEqual(MajorityClassifier(3).fit(None, np.array([1, 0])).label_, 0)  # tie -> label-set order
        self.assertEqual(MeanRegressor().fit(None, np.array([60.0, 80.0])).predict(np.zeros(3)).tolist(), [70.0] * 3)


class MetricTests(unittest.TestCase):
    def test_hr_stats(self):
        s = hr_stats([3.0, -4.0])
        self.assertAlmostEqual(s["mae"], 3.5)
        self.assertAlmostEqual(s["rmse"], np.sqrt(12.5))
        self.assertAlmostEqual(s["bias"], -0.5)
        self.assertEqual(hr_stats([])["mae"], None)

    def test_single_class_fold_macro_f1_is_na(self):
        s = classification_summary(confusion([0, 0, 0], [0, 1, 0], 3), ["walk", "run", "cycle"])
        self.assertIsNone(s["macro_f1"])
        self.assertEqual(s["macro_f1_note"], "n/a: single-class test fold")
        self.assertAlmostEqual(s["accuracy"], 2 / 3)

    def test_macro_f1_hand_example(self):
        cm = np.array([[2, 1], [0, 1]])
        s = classification_summary(cm, ["a", "b"])
        f_a, f_b = 2 * 1 * (2 / 3) / (1 + 2 / 3), 2 * 0.5 * 1 / 1.5
        self.assertAlmostEqual(s["macro_f1"], (f_a + f_b) / 2)

    def test_bootstrap_is_seeded_and_over_participants(self):
        a = bootstrap_indices(8, 100, 1)
        np.testing.assert_array_equal(a, bootstrap_indices(8, 100, 1))
        self.assertEqual(a.shape, (100, 8))
        agg = aggregate([1.0] * 8, a)
        self.assertEqual((agg["ci_low"], agg["ci_high"]), (1.0, 1.0))


@unittest.skipUnless(REAL, SKIP_REAL)
class RealDataPipelineTests(unittest.TestCase):
    """Runs the complete frozen pipeline into a temporary directory."""

    @classmethod
    def setUpClass(cls):
        import run_m6
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.results = run_m6.run(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_dataset_matches_audit(self):
        dc = self.results["dataset_check"]
        self.assertEqual(dc["participants"], CFG["dataset"]["expected_participants"])
        self.assertEqual(dc["n_records"], 19)
        self.assertEqual(sum(v["beats"] for v in dc["per_record"].values()), 11388)
        self.assertEqual(dc["records_per_participant"]["s4"], ["s4_run"])
        self.assertEqual(dc["records_per_participant"]["s9"], ["s9_walk"])

    def test_a1_is_the_frozen_m5_method(self):
        self.assertTrue(self.results["dataset_check"]["a1_matches_m5_dsp_hr"]["all_identical"])
        self.assertEqual(self.results["dataset_check"]["a1_matches_m5_dsp_hr"]["records_checked"], 19)

    def test_single_class_folds_reported_na(self):
        for ls in ("primary_3class", "secondary_4class"):
            for m in ("B0", "B1", "B2"):
                for p in ("s4", "s9"):
                    self.assertIsNone(self.results["activity"][ls]["models"][m]["per_fold"][p]["macro_f1"])

    def test_config_hash_recorded(self):
        import hashlib
        self.assertEqual(self.results["provenance"]["config_sha256"],
                         hashlib.sha256(m6_data.CONFIG_PATH.read_bytes()).hexdigest())

    def test_reported_metrics_match_raw_outputs(self):
        import verify_m6
        checker = verify_m6.verify(self.out)
        self.assertEqual(checker.failures, [])
        self.assertGreater(checker.passed, 1000)

    def test_deterministic_and_matches_committed_outputs(self):
        committed = M6 / "outputs"
        if not (committed / "results.json").exists():
            self.skipTest("experiments/m6/outputs not generated yet")
        names = sorted(p.name for p in committed.iterdir() if p.is_file())
        self.assertEqual(names, sorted(p.name for p in self.out.iterdir() if p.is_file()))
        for name in names:
            self.assertEqual(_without_provenance(name, (committed / name).read_bytes()),
                             _without_provenance(name, (self.out / name).read_bytes()), name)

    def test_provenance_still_recorded(self):
        prov = json.loads((self.out / "results.json").read_text(encoding="utf-8"))["provenance"]
        for key in ("git_head", "config_sha256", "dataset_manifest_sha256", "source_sha256", "python"):
            self.assertIn(key, prov)


def _without_provenance(name: str, data: bytes) -> bytes:
    """Drop only environment provenance, which cannot be byte-stable across commits and machines
    (git HEAD, platform, Python version, file hashes that depend on checkout line endings).
    Every metric and every CSV is still compared byte for byte."""
    if name == "results.json":
        obj = json.loads(data.decode("utf-8"))
        obj.pop("provenance")
        return json.dumps(obj, indent=1, sort_keys=True).encode("utf-8")
    if name == "report.md":
        text = data.decode("utf-8")
        start = text.index("## 1. Reproducibility")
        end = text.index("\n## ", start)
        return (text[:start] + text[end:]).encode("utf-8")
    return data


if __name__ == "__main__":
    unittest.main()
