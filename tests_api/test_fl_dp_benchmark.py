"""P1: the FL/DP benchmark artifact must be measured, reproducible and honestly labelled.

The accountant is checked against an independent numerical integration, not against itself.
The artifact is checked for internal consistency and for the presence of every honesty
control (mean baseline, window-vs-participant threat model, divergence reporting).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api import benchmark as benchmark_api  # noqa: E402

SCRIPT = ROOT / "scripts" / "run_fl_dp_benchmark.py"
ARTIFACT = ROOT / "artifacts" / "fl_dp_benchmark_results.json"


def load_module():
    spec = importlib.util.spec_from_file_location("fl_dp_bench", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fl_dp_bench"] = module
    spec.loader.exec_module(module)
    return module


bench = load_module()


class AccountantTests(unittest.TestCase):
    def test_no_subsampling_reduces_to_the_gaussian_mechanism(self):
        for alpha in (2, 5, 16, 64, 128):
            for sigma in (0.5, 1.0, 2.0, 8.0):
                with self.subTest(alpha=alpha, sigma=sigma):
                    self.assertAlmostEqual(bench.sgm_rdp(1.0, sigma, alpha),
                                           alpha / (2 * sigma ** 2), places=9)

    def test_zero_sampling_rate_costs_nothing(self):
        self.assertEqual(bench.sgm_rdp(0.0, 1.0, 16), 0.0)

    def test_closed_form_matches_independent_numerical_integration(self):
        """Integrate E_mu0[(mu/mu0)^alpha] directly; do not reuse the binomial identity."""
        from scipy.integrate import quad

        def numeric(q, sigma, alpha):
            def integrand(z):
                ratio = (1 - q) + q * np.exp((2 * z - 1) / (2 * sigma ** 2))
                return (np.exp(-z * z / (2 * sigma ** 2)) / (np.sqrt(2 * np.pi) * sigma)
                        * ratio ** alpha)
            value, _ = quad(integrand, -40 * sigma, 40 * sigma, limit=400)
            return math.log(value)

        for q, sigma, alpha in [(0.01, 1.0, 4), (0.05, 1.5, 8), (0.1495, 8.0, 16),
                                (0.25, 1.1, 2), (0.1, 2.0, 16), (0.3, 4.0, 6)]:
            with self.subTest(q=q, sigma=sigma, alpha=alpha):
                self.assertAlmostEqual(bench.sgm_log_moment(q, sigma, alpha),
                                       numeric(q, sigma, alpha), places=9)

    def test_privacy_loss_is_monotone_in_noise_and_sampling(self):
        self.assertLess(bench.sgm_rdp(0.01, 2.0, 16), bench.sgm_rdp(0.01, 1.0, 16))
        self.assertLess(bench.sgm_rdp(0.01, 1.0, 16), bench.sgm_rdp(0.1, 1.0, 16))

    def test_epsilon_grows_with_steps_and_shrinks_with_noise(self):
        cfg = bench.Config()
        small = bench.accountant(cfg, 300, 100)["epsilon"]
        large = bench.accountant(cfg, 300, 1000)["epsilon"]
        self.assertLess(small, large)
        from dataclasses import replace
        quiet = bench.accountant(replace(cfg, noise_multiplier=2.0), 300, 500)["epsilon"]
        loud = bench.accountant(replace(cfg, noise_multiplier=16.0), 300, 500)["epsilon"]
        self.assertGreater(quiet, loud)

    def test_accountant_declares_the_window_level_neighbour(self):
        report = bench.accountant(bench.Config(), 300, 500)
        self.assertEqual(report["level"], "WINDOW")
        self.assertIn("one 8 s window", report["neighbouring_dataset"])
        self.assertEqual(report["delta"], 1e-5)
        self.assertEqual(report["clip_norm"], 1.0)


class AggregatorTests(unittest.TestCase):
    def test_cosine_median_rejects_a_single_sign_flipped_client(self):
        honest = np.array([[1.0, 0.9, 1.1], [1.0, 1.0, 1.0], [0.9, 1.1, 1.0]])
        faulty = np.array([[-1.0, -1.0, -1.0]])
        updates = np.concatenate([faulty, honest])
        agg, dropped = bench.cosine_median(updates, f=1)
        self.assertEqual(dropped, 1)
        np.testing.assert_allclose(agg, np.median(honest, axis=0))

    def test_cosine_median_rejects_a_single_scaled_client(self):
        honest = np.array([[1.0, 1.0], [1.1, 0.9], [0.9, 1.1]])
        updates = np.concatenate([np.array([[500.0, 500.0]]), honest])
        agg, dropped = bench.cosine_median(updates, f=1)
        self.assertEqual(dropped, 1)
        self.assertLess(float(np.linalg.norm(agg)), 2.0)

    def test_plain_mean_is_corrupted_by_a_scaled_client(self):
        honest = np.array([[1.0, 1.0], [1.1, 0.9], [0.9, 1.1]])
        updates = np.concatenate([np.array([[500.0, 500.0]]), honest])
        self.assertGreater(float(np.linalg.norm(updates.mean(axis=0))), 100.0)


class DatasetTests(unittest.TestCase):
    def test_join_keeps_every_window_and_the_frozen_eight(self):
        X, y, participants, names = bench.load_dataset()
        self.assertEqual(len(y), 3332)
        self.assertEqual(X.shape, (3332, 41))
        self.assertEqual(len(names), 41)
        self.assertEqual(sorted(set(participants)), bench.PARTICIPANTS)

    def test_no_participant_is_split_across_clients(self):
        seen = [p for group in bench.CLIENT_GROUPS for p in group]
        self.assertEqual(sorted(seen), bench.PARTICIPANTS)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(bench.CLIENT_GROUPS), 4)

    def test_held_out_participant_is_in_no_client(self):
        X, y, participants, _ = bench.load_dataset()
        parr = np.asarray(participants)
        for held_out in bench.PARTICIPANTS:
            mask = parr != held_out
            Xtr, ytr = X[mask], y[mask]
            ptr = [p for p, keep in zip(participants, mask) if keep]
            mean, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
            clients = bench.make_clients(Xtr, ytr, ptr, held_out, mean,
                                         np.where(sd > 0, sd, 1.0), float(ytr.mean()),
                                         float(ytr.std()))
            with self.subTest(held_out=held_out):
                self.assertNotIn(held_out, ptr)
                self.assertEqual(sum(len(cy) for _, cy in clients), int(mask.sum()))


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ARTIFACT.is_file():
            raise unittest.SkipTest("artifact not generated yet")
        cls.data = json.loads(ARTIFACT.read_text())

    def test_api_loader_reports_the_artifact_and_its_digest(self):
        loaded = benchmark_api.load()
        self.assertTrue(loaded["available"])
        self.assertEqual(len(loaded["sha256"]), 64)
        self.assertEqual(loaded["results"]["title"], self.data["title"])

    def test_provenance_hashes_match_the_files_on_disk(self):
        prov = self.data["provenance"]
        for key, path in (("features_sha256", prov["features_csv"]),
                          ("windows_sha256", prov["windows_csv"]),
                          ("script_sha256", prov["script"])):
            with self.subTest(file=path):
                self.assertEqual(prov[key], bench.sha256_file(ROOT / path))

    def test_mean_baseline_reproduces_the_frozen_m6_a0(self):
        check = self.data["accuracy"]["frozen_m6_cross_check"]
        self.assertTrue(check["matches"], check)
        self.assertAlmostEqual(check["measured_mae_bpm"], 24.177234, places=4)

    def test_all_four_requested_regimes_plus_the_baseline_are_present(self):
        regimes = {row["regime"] for row in self.data["accuracy"]["table"]}
        self.assertEqual(regimes, {"mean_baseline", "local_only", "centralized",
                                   "fedavg", "dp_sgd_fl"})

    def test_every_row_carries_a_participant_bootstrap_ci(self):
        for row in self.data["accuracy"]["table"]:
            mae = row["mae_bpm"]
            with self.subTest(regime=row["regime"]):
                self.assertEqual(mae["unit"], "participant")
                self.assertEqual(mae["n_participants"], 8)
                self.assertEqual(mae["resamples"], 10000)
                self.assertEqual(mae["seed"], 20261115)
                self.assertLessEqual(mae["ci_low"], mae["mean"])
                self.assertGreaterEqual(mae["ci_high"], mae["mean"])

    def test_fold_maes_average_to_the_reported_table(self):
        per = self.data["accuracy"]["per_participant_mae_bpm"]
        for row in self.data["accuracy"]["table"]:
            with self.subTest(regime=row["regime"]):
                values = per[row["regime"]]
                self.assertEqual(len(values), 8)
                self.assertAlmostEqual(float(np.mean(values)), row["mae_bpm"]["mean"], places=3)

    def test_threat_model_separates_window_from_participant_level(self):
        tm = self.data["threat_model"]
        self.assertEqual(tm["level"], "WINDOW")
        self.assertEqual(tm["delta"], 1e-5)
        joined = " ".join(tm["not_covered"]).lower()
        self.assertIn("participant-level", joined)
        self.assertIn("not implemented", joined)
        self.assertIn("standardiser", joined)
        self.assertIn("secure aggregation", joined)

    def test_dp_row_reports_epsilon_and_the_sweep_brackets_it(self):
        dp = next(r for r in self.data["accuracy"]["table"] if r["regime"] == "dp_sgd_fl")
        eps = dp["window_level_epsilon"]
        self.assertEqual(eps["delta"], 1e-5)
        self.assertGreater(eps["max_over_folds"], 0)
        sweep = self.data["dp_privacy_utility"]["sweep"]
        self.assertGreaterEqual(len(sweep), 4)
        epsilons = [r["window_level_epsilon_worst_case"] for r in sweep]
        self.assertEqual(epsilons, sorted(epsilons, reverse=True))  # more noise, less epsilon
        self.assertTrue(any(r["is_default_operating_point"] for r in sweep))

    def test_robustness_covers_both_faults_both_aggregators_and_five_seeds(self):
        runs = self.data["robustness"]["runs"]
        self.assertEqual({(r["fault"], r["aggregator"]) for r in runs},
                         {(f, a) for f in ("sign_flip", "scale")
                          for a in ("mean", "cosine_median")})
        for run in runs:
            with self.subTest(fault=run["fault"], aggregator=run["aggregator"]):
                self.assertEqual(run["n_seeds"], 5)
                self.assertEqual(len(run["per_seed_mae_bpm"]), 5)
                self.assertEqual(run["fault_client_index"], 0)

    def test_divergence_is_reported_as_divergence_not_a_giant_mae(self):
        scale_mean = next(r for r in self.data["robustness"]["runs"]
                          if r["fault"] == "scale" and r["aggregator"] == "mean")
        if scale_mean["diverged_seeds"]:
            self.assertIn(scale_mean["outcome"], {"DIVERGED", "PARTIALLY_DIVERGED"})
            for value in scale_mean["per_seed_mae_bpm"]:
                self.assertTrue(value is None or value <= scale_mean["divergence_threshold_bpm"])
        robust = next(r for r in self.data["robustness"]["runs"]
                      if r["fault"] == "scale" and r["aggregator"] == "cosine_median")
        self.assertEqual(robust["diverged_seeds"], 0)
        self.assertLess(robust["mae_bpm_mean_over_seeds"], 1000.0)

    def test_robustness_findings_are_not_cherry_picked(self):
        for row in self.data["robustness"]["comparison"]:
            with self.subTest(fault=row["fault"]):
                self.assertTrue(row["finding"])
                if (row["fedavg_mae_bpm"] is not None
                        and row["cosine_median_mae_bpm"] is not None
                        and row["cosine_median_mae_bpm"] > row["fedavg_mae_bpm"]):
                    self.assertIn("NOT better", row["finding"])

    def test_limitations_state_that_dp_looking_free_is_an_artifact(self):
        joined = " ".join(self.data["limitations"]).lower()
        self.assertIn("not evidence that strong", joined)
        self.assertIn("flower", joined)
        self.assertIn("opacus", joined)
        self.assertIn("not astronaut data", self.data["scope"].lower())

    def test_no_non_finite_or_absurd_number_reaches_the_artifact(self):
        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")
            elif isinstance(node, float):
                self.assertTrue(math.isfinite(node), f"non-finite at {path}")
                if "mae" in path.lower() and "raw" not in path.lower():
                    self.assertLess(node, 1000.0, f"absurd MAE at {path}: {node}")
        walk(self.data)


if __name__ == "__main__":
    unittest.main()
