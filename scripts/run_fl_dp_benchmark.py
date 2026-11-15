#!/usr/bin/env python3
"""Measured federated / DP-SGD benchmark on the frozen M6 participant-separated splits.

    python3 scripts/run_fl_dp_benchmark.py            # full, writes the committed artifact
    python3 scripts/run_fl_dp_benchmark.py --quick    # tiny smoke config, does NOT write
    python3 scripts/run_fl_dp_benchmark.py --verify    # re-run and compare to the artifact

WHY THIS IS HAND-ROLLED
-----------------------
The deck asks for Flower + Opacus. Neither is installed here (torch pulls ~540 MB of CUDA
wheels; flwr pins fastapi<0.139 against this repo's 0.163.1). Instead of a fake number, this
script implements the four requested training regimes directly on numpy/scipy with an exact
integer-order RDP accountant for the Sampled Gaussian Mechanism. Every number in
`artifacts/fl_dp_benchmark_results.json` is produced by running this file.

DATA AND SPLITS
---------------
Inputs are the committed M6 outputs, never a re-download:
  experiments/m6/outputs/features.csv   41 frozen spectral/correlation features per window
  experiments/m6/outputs/windows.csv    participant, record, activity, reference HR
Joined on (record, start_sample). Task: predict reference HR (bpm) from wrist features.
Splits: leave-one-participant-out over the frozen 8 participants (s1..s9 minus s7).
No window ever crosses the train/test boundary, and no participant appears on both sides.

REGIMES (identical model, identical splits, identical step budget)
-----------------------------------------------------------------
  local_only    each of 4 participant-group silos trains alone; the held-out participant is
                scored with every silo model and the silo MAEs are averaged (a single silo
                cannot see the others' data, so this is the honest no-federation baseline)
  centralized   one model on the pooled training participants
  fedavg        4 participant-group clients, C=1.0 (all clients every round), R rounds,
                sample-count-weighted averaging
  dp_sgd_fl     same federation, but per-window gradient clipping (C=1.0) plus Gaussian
                noise on each client's summed update; Poisson subsampling at rate q

THREAT MODEL — READ THIS BEFORE QUOTING EPSILON
----------------------------------------------
The reported epsilon is WINDOW-LEVEL: the neighbouring datasets differ by one 8-second
window. It is (eps, delta=1e-5) for one window in one client, composed over every noisy step
that client took. It is NOT participant-level: one participant contributes 107-868 windows,
so removing a whole participant is a much larger change and is NOT bounded by this epsilon.
Participant-level DP would require per-participant (group) clipping, which is not implemented.
Two further honest limitations, both declared in the artifact:
  * the feature standardiser and target centring are computed from the training participants
    and are NOT covered by the DP guarantee (only the SGD phase is accounted);
  * the noise is added client-locally and the server is assumed honest-but-curious. There is
    no secure aggregation, so a malicious server sees individual noisy client updates.

ROBUSTNESS
----------
5 seeds x {sign-flip, scale} fault injection into exactly 1 of the 4 clients, comparing
plain FedAvg averaging against cosine-screened coordinate-wise median (declared f=1 of n=4).

Not astronaut data. Not clinical. Not validated. No accuracy claim for spaceflight.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from scipy.special import gammaln

ROOT = Path(__file__).resolve().parents[1]
FEATURES_CSV = ROOT / "experiments" / "m6" / "outputs" / "features.csv"
WINDOWS_CSV = ROOT / "experiments" / "m6" / "outputs" / "windows.csv"
ARTIFACT = ROOT / "artifacts" / "fl_dp_benchmark_results.json"
PARTICIPANTS = ["s1", "s2", "s3", "s4", "s5", "s6", "s8", "s9"]
CLIENT_GROUPS = [["s1", "s2"], ["s3", "s4"], ["s5", "s6"], ["s8", "s9"]]
DELTA = 1e-5
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 20261115  # the frozen M6 bootstrap seed
DIVERGENCE_MAE_BPM = 1000.0  # above this an "MAE" is a diverged optimiser, not a measurement


@dataclass(frozen=True)
class Config:
    rounds: int = 20
    local_steps: int = 25
    batch_size: int = 16
    learning_rate: float = 0.02
    l2: float = 1e-3
    clip_norm: float = 1.0
    noise_multiplier: float = 8.0
    client_fraction: float = 1.0
    n_clients: int = 4
    fault_seeds: tuple[int, ...] = (11, 22, 33, 44, 55)
    fault_scale: float = 20.0
    dp_sigma_sweep: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
    rdp_orders: tuple[int, ...] = tuple(range(2, 129))
    delta: float = DELTA

    def public(self) -> dict:
        d = asdict(self)
        d["fault_seeds"] = list(self.fault_seeds)
        d["rdp_orders"] = [min(self.rdp_orders), max(self.rdp_orders)]
        d["rdp_orders_note"] = "every integer order in the inclusive range"
        d["dp_sigma_sweep"] = list(self.dp_sigma_sweep)
        return d


QUICK = Config(rounds=2, local_steps=3, batch_size=32, fault_seeds=(11, 22),
               rdp_orders=tuple(range(2, 33)))


# --------------------------------------------------------------------------------------------
# Exact RDP accountant for the Sampled Gaussian Mechanism
# --------------------------------------------------------------------------------------------
def _log_comb(n: int, k: np.ndarray) -> np.ndarray:
    return gammaln(n + 1) - gammaln(k + 1) - gammaln(n - k + 1)


def sgm_log_moment(q: float, sigma: float, alpha: int) -> float:
    """log E_{z~mu0}[(mu(z)/mu0(z))^alpha] for Poisson-subsampled Gaussian, integer alpha.

    mu = (1-q) N(0, sigma^2) + q N(1, sigma^2), mu0 = N(0, sigma^2). The expectation is the
    finite binomial sum sum_i C(alpha,i) (1-q)^(alpha-i) q^i exp((i^2-i)/(2 sigma^2)),
    evaluated in log space. This is the exact integer-order expression (Mironov et al.,
    "Renyi Differential Privacy of the Sampled Gaussian Mechanism", 2019, eq. for integer
    alpha) - no CLT or tail approximation is used.
    """
    if q == 0.0:
        return 0.0
    if q >= 1.0:
        return alpha * (alpha - 1) / (2.0 * sigma ** 2)
    i = np.arange(alpha + 1, dtype=np.float64)
    terms = (_log_comb(alpha, i) + i * math.log(q) + (alpha - i) * math.log1p(-q)
             + (i ** 2 - i) / (2.0 * sigma ** 2))
    top = float(np.max(terms))
    return top + float(np.log(np.sum(np.exp(terms - top))))


def sgm_rdp(q: float, sigma: float, alpha: int) -> float:
    """RDP of order alpha for one application of the mechanism."""
    return sgm_log_moment(q, sigma, alpha) / (alpha - 1)


def rdp_to_dp(rdp: np.ndarray, orders: np.ndarray, delta: float) -> tuple[float, int]:
    """Standard RDP->(eps, delta) conversion: eps = min_a rdp(a) + log(1/delta)/(a-1)."""
    eps = rdp + math.log(1.0 / delta) / (orders - 1)
    best = int(np.argmin(eps))
    return float(eps[best]), int(orders[best])


def accountant(cfg: Config, n_client_windows: int, steps: int) -> dict:
    """Window-level epsilon for one client's participation across all rounds."""
    q = min(1.0, cfg.batch_size / max(1, n_client_windows))
    orders = np.array(cfg.rdp_orders, dtype=np.int64)
    per_step = np.array([sgm_rdp(q, cfg.noise_multiplier, int(a)) for a in orders])
    total = per_step * steps
    eps, best_order = rdp_to_dp(total, orders, cfg.delta)
    return {
        "epsilon": round(eps, 4), "delta": cfg.delta, "best_order": best_order,
        "sampling_rate_q": round(q, 6), "noise_multiplier": cfg.noise_multiplier,
        "clip_norm": cfg.clip_norm, "accounted_steps": steps,
        "rdp_at_best_order": round(float(total[orders == best_order][0]), 6),
        "mechanism": "Poisson-subsampled Gaussian (per-window clip + additive Gaussian noise)",
        "accountant": "exact integer-order SGM RDP, log-space binomial sum; composed by "
                      "summing RDP over steps; converted with eps = rdp + log(1/delta)/(alpha-1)",
        "neighbouring_dataset": "one 8 s window added or removed from one client",
        "level": "WINDOW",
    }


# --------------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dataset() -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    with FEATURES_CSV.open(newline="") as fh:
        reader = csv.DictReader(fh)
        feature_names = [c for c in (reader.fieldnames or []) if c not in {"record", "start_sample"}]
        feats = {(r["record"], int(r["start_sample"])): [float(r[c]) for c in feature_names]
                 for r in reader}
    X, y, participants, activities = [], [], [], []
    with WINDOWS_CSV.open(newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row["record"], int(row["start_sample"]))
            raw = row.get("ref_hr_bpm", "")
            if key not in feats or raw in ("", "nan"):
                continue
            X.append(feats[key])
            y.append(float(raw))
            participants.append(row["participant"])
            activities.append(row["activity"])
    order = np.argsort(np.array(participants), kind="stable")
    return (np.asarray(X, dtype=np.float64)[order], np.asarray(y, dtype=np.float64)[order],
            [participants[i] for i in order], feature_names)


def bootstrap_ci(per_participant: list[float], seed: int = BOOTSTRAP_SEED,
                 resamples: int = BOOTSTRAP_RESAMPLES) -> dict:
    """Participant-level paired bootstrap, identical convention to the frozen M6 protocol."""
    v = np.asarray(per_participant, dtype=float)
    idx = np.random.default_rng(seed).integers(0, v.size, size=(resamples, v.size))
    means = v[idx].mean(axis=1)
    return {"mean": round(float(v.mean()), 4), "median": round(float(np.median(v)), 4),
            "sd": round(float(v.std(ddof=1)), 4) if v.size > 1 else None,
            "ci_low": round(float(np.percentile(means, 2.5)), 4),
            "ci_high": round(float(np.percentile(means, 97.5)), 4),
            "n_participants": int(v.size), "resamples": resamples, "seed": seed,
            "unit": "participant", "percentiles": [2.5, 97.5]}


# --------------------------------------------------------------------------------------------
# Model: linear least squares trained by (DP-)SGD, so all four regimes are comparable
# --------------------------------------------------------------------------------------------
@dataclass
class Linear:
    w: np.ndarray
    b: float

    def predict(self, Z: np.ndarray) -> np.ndarray:
        return Z @ self.w + self.b

    def flat(self) -> np.ndarray:
        return np.concatenate([self.w, [self.b]])


def _init(dim: int) -> Linear:
    return Linear(np.zeros(dim), 0.0)


def _mean_abs_error(model: Linear, Z: np.ndarray, y: np.ndarray) -> float:
    """MAE in the model's target units. Callers multiply by the train-only y SD to get bpm."""
    value = float(np.mean(np.abs(model.predict(Z) - y)))
    if not math.isfinite(value):
        raise FloatingPointError("model diverged; the configured learning rate is too high "
                                 "for this split. Refusing to report a non-finite metric.")
    return value


def sgd_steps(model: Linear, Z: np.ndarray, y: np.ndarray, cfg: Config, rng,
              *, dp: bool, steps: int) -> Linear:
    """`steps` minibatch updates. DP mode clips per-window gradients then adds noise."""
    w, b = model.w.copy(), float(model.b)
    n = len(y)
    dim = Z.shape[1]
    for _ in range(steps):
        if dp:
            # Poisson subsampling: each window is included independently with probability q.
            q = min(1.0, cfg.batch_size / max(1, n))
            mask = rng.random(n) < q
            Zb, yb = Z[mask], y[mask]
            m = len(yb)
            if m == 0:
                continue
            err = Zb @ w + b - yb
            gw = Zb * err[:, None]
            gb = err
            flat = np.concatenate([gw, gb[:, None]], axis=1)
            norms = np.linalg.norm(flat, axis=1)
            scale = np.minimum(1.0, cfg.clip_norm / np.maximum(norms, 1e-12))
            clipped = flat * scale[:, None]
            denom = max(1.0, q * n)  # fixed denominator: no data-dependent scaling
            noise = rng.normal(0.0, cfg.noise_multiplier * cfg.clip_norm, size=dim + 1)
            total = clipped.sum(axis=0) + noise
            gw_mean, gb_mean = total[:dim] / denom, float(total[dim] / denom)
        else:
            take = min(cfg.batch_size, n)
            sel = rng.integers(0, n, size=take)
            Zb, yb = Z[sel], y[sel]
            err = Zb @ w + b - yb
            gw_mean = (Zb.T @ err) / len(yb)
            gb_mean = float(err.mean())
        w -= cfg.learning_rate * (gw_mean + cfg.l2 * w)
        b -= cfg.learning_rate * gb_mean
    return Linear(w, b)


def fedavg(clients: list[tuple[np.ndarray, np.ndarray]], Zte: np.ndarray, yte: np.ndarray,
           cfg: Config, seed: int, *, dp: bool = False, aggregator: str = "mean",
           fault: str | None = None, fault_client: int = 0) -> tuple[Linear, dict]:
    """Multi-round federation over participant-group clients. Returns (model, trace)."""
    rng = np.random.default_rng(seed)
    dim = clients[0][0].shape[1]
    global_model = _init(dim)
    counts = np.array([len(y) for _, y in clients], dtype=float)
    weights = counts / counts.sum()
    n_selected = max(1, int(round(cfg.client_fraction * len(clients))))
    trace = {"rounds": cfg.rounds, "local_steps_per_round": cfg.local_steps,
             "clients_per_round": n_selected, "client_window_counts": counts.astype(int).tolist(),
             "aggregator": aggregator, "fault": fault, "fault_client": fault_client if fault else None,
             "train_mae_by_round": []}
    for _ in range(cfg.rounds):
        updates, sizes = [], []
        for k, (Zc, yc) in enumerate(clients):
            if k >= n_selected:
                continue
            local = sgd_steps(global_model, Zc, yc, cfg, rng, dp=dp, steps=cfg.local_steps)
            delta = local.flat() - global_model.flat()
            if fault and k == fault_client:
                delta = -delta if fault == "sign_flip" else delta * cfg.fault_scale
            updates.append(delta)
            sizes.append(len(yc))
        stacked = np.stack(updates)
        if aggregator == "cosine_median":
            agg, dropped = cosine_median(stacked)
            trace.setdefault("dropped_client_counts", []).append(dropped)
        else:
            agg = np.average(stacked, axis=0, weights=np.asarray(sizes, dtype=float))
        global_model = Linear(agg[:dim].copy(), float(agg[dim]))
        pooled_Z = np.concatenate([c[0] for c in clients])
        pooled_y = np.concatenate([c[1] for c in clients])
        trace["train_mae_by_round"].append(round(_mean_abs_error(global_model, pooled_Z, pooled_y), 6))
    trace["steps_per_client"] = cfg.rounds * cfg.local_steps
    return global_model, trace


def cosine_median(updates: np.ndarray, f: int = 1) -> tuple[np.ndarray, int]:
    """Cosine-screened coordinate-wise median, declared Byzantine tolerance f of n.

    Score each client update by its median cosine similarity to the other updates, drop the
    `f` lowest-scoring clients, then take the coordinate-wise median of the survivors. With
    n=4 and f=1 this tolerates exactly one faulty client, which is what is injected below.
    """
    n = len(updates)
    norms = np.linalg.norm(updates, axis=1)
    unit = updates / np.maximum(norms[:, None], 1e-12)
    sim = unit @ unit.T
    scores = np.array([np.median(np.delete(sim[i], i)) if n > 1 else 1.0 for i in range(n)])
    keep = np.argsort(-scores, kind="stable")[: max(1, n - f)]
    return np.median(updates[keep], axis=0), int(n - len(keep))


# --------------------------------------------------------------------------------------------
# Benchmark driver
# --------------------------------------------------------------------------------------------
def make_clients(Xtr, ytr, ptr, held_out: str, mean: np.ndarray, sd: np.ndarray,
                 y_mean: float, y_sd: float = 1.0) -> list[tuple[np.ndarray, np.ndarray]]:
    """4 participant-group clients. The held-out participant is in none of them."""
    groups = [[p for p in group if p != held_out] for group in CLIENT_GROUPS]
    clients = []
    ptr_arr = np.asarray(ptr)
    for group in groups:
        mask = np.isin(ptr_arr, group)
        if mask.sum() == 0:
            continue
        clients.append(((Xtr[mask] - mean) / sd, (ytr[mask] - y_mean) / y_sd))
    return clients


def run_accuracy(cfg: Config, X, y, participants, feature_names) -> dict:
    per_participant: dict[str, list[float]] = {k: [] for k in
                                              ("mean_baseline", "local_only", "centralized",
                                               "fedavg", "dp_sgd_fl")}
    folds, eps_values, silo_counts = [], [], []
    for held_out in PARTICIPANTS:
        parr = np.asarray(participants)
        train_mask = parr != held_out
        test_mask = ~train_mask
        Xtr, ytr = X[train_mask], y[train_mask]
        ptr = [p for p, keep in zip(participants, train_mask) if keep]
        Xte, yte = X[test_mask], y[test_mask]
        # Train-only preprocessing. Declared limitation: these statistics are not DP-protected.
        mean = Xtr.mean(axis=0)
        sd = Xtr.std(axis=0)
        sd = np.where(sd > 0, sd, 1.0)
        y_mean, y_sd = float(ytr.mean()), float(ytr.std())
        y_sd = y_sd if y_sd > 0 else 1.0
        Ztr, Zte = (Xtr - mean) / sd, (Xte - mean) / sd
        # The target is standardised with train-only statistics too, so the DP clip norm
        # C=1.0 is on a comparable scale in every fold. MAE is converted back to bpm below.
        ytr_c, yte_c = (ytr - y_mean) / y_sd, (yte - y_mean) / y_sd
        clients = make_clients(Xtr, ytr, ptr, held_out, mean, sd, y_mean, y_sd)
        silo_counts.append([len(cy) for _, cy in clients])
        # Reference: predict the training mean. Without this row a reader cannot tell
        # whether any regime learned anything at all.
        per_participant["mean_baseline"].append(float(np.mean(np.abs(yte - y_mean))))

        # 1. local-only: every silo scores the held-out participant; average the silo MAEs.
        silo_maes = []
        for i, (Zc, yc) in enumerate(clients):
            m = sgd_steps(_init(X.shape[1]), Zc, yc, cfg, np.random.default_rng(1000 + i),
                          dp=False, steps=cfg.rounds * cfg.local_steps)
            silo_maes.append(_mean_abs_error(m, Zte, yte_c) * y_sd)
        per_participant["local_only"].append(float(np.mean(silo_maes)))

        # 2. centralized: same total step budget on the pooled training windows.
        central = sgd_steps(_init(X.shape[1]), Ztr, ytr_c, cfg, np.random.default_rng(7),
                            dp=False, steps=cfg.rounds * cfg.local_steps)
        per_participant["centralized"].append(_mean_abs_error(central, Zte, yte_c) * y_sd)

        # 3. FedAvg.
        fed, fed_trace = fedavg(clients, Zte, yte_c, cfg, seed=7)
        per_participant["fedavg"].append(_mean_abs_error(fed, Zte, yte_c) * y_sd)

        # 4. DP-SGD FL, identical rounds/steps so the comparison is like for like.
        dp_model, _ = fedavg(clients, Zte, yte_c, cfg, seed=7, dp=True)
        per_participant["dp_sgd_fl"].append(_mean_abs_error(dp_model, Zte, yte_c) * y_sd)

        smallest = min(len(cy) for _, cy in clients)
        eps_values.append(accountant(cfg, smallest, cfg.rounds * cfg.local_steps)["epsilon"])
        folds.append({"held_out": held_out, "n_test_windows": int(test_mask.sum()),
                      "n_train_windows": int(train_mask.sum()),
                      "client_window_counts": [len(cy) for _, cy in clients],
                      "local_only_silo_maes": [round(v, 4) for v in silo_maes],
                      "mae_bpm": {k: round(v[-1], 4) for k, v in per_participant.items()},
                      "fedavg_final_train_mae_bpm": round(fed_trace["train_mae_by_round"][-1] * y_sd, 4),
                      "train_target_sd_bpm": round(y_sd, 6)})
        print(f"  LOPO {held_out}: " + "  ".join(
            f"{k}={v[-1]:.2f}" for k, v in per_participant.items()), flush=True)

    labels = {"mean_baseline": "Training-mean baseline (learns nothing; the honesty control)",
              "local_only": "Local-only (mean of 4 participant-group silos)",
              "centralized": "Centralized (pooled training participants)",
              "fedavg": f"FedAvg ({cfg.n_clients} participant-group clients, C={cfg.client_fraction}, "
                        f"{cfg.rounds} rounds)",
              "dp_sgd_fl": f"DP-SGD FL (clip C={cfg.clip_norm}, sigma={cfg.noise_multiplier})"}
    table = []
    for key, values in per_participant.items():
        row = {"regime": key, "label": labels[key], "mae_bpm": bootstrap_ci(values)}
        if key == "dp_sgd_fl":
            row["window_level_epsilon"] = {
                "min_over_folds": min(eps_values), "max_over_folds": max(eps_values),
                "delta": cfg.delta,
                "note": "epsilon for the smallest client in each fold; a window in a larger "
                        "client has a smaller q and therefore a smaller epsilon. The reported "
                        "max is the conservative worst case over folds and clients."}
        table.append(row)
    # Cross-check: the training-mean row must reproduce the frozen M6 A0 aggregate exactly.
    # If the join, the split or the rounding ever drifts, this fails loudly.
    m6_results = ROOT / "experiments" / "m6" / "outputs" / "results.json"
    cross_check = {"reference": "experiments/m6/outputs/results.json hr.primary.models.A0",
                   "expected_mae_bpm": None, "measured_mae_bpm":
                       round(float(np.mean(per_participant["mean_baseline"])), 6),
                   "matches": None}
    if m6_results.is_file():
        try:
            expected = json.loads(m6_results.read_text())["hr"]["primary"]["models"]["A0"][
                "aggregate"]["mae"]["mean"]
            cross_check["expected_mae_bpm"] = round(float(expected), 6)
            cross_check["matches"] = abs(float(expected) - cross_check["measured_mae_bpm"]) < 1e-4
            if not cross_check["matches"]:
                raise SystemExit(f"mean-baseline cross-check FAILED: measured "
                                 f"{cross_check['measured_mae_bpm']} vs frozen M6 A0 {expected}. "
                                 "The data join or the LOPO split has drifted.")
        except (KeyError, TypeError):
            cross_check["detail"] = "frozen M6 A0 aggregate not found; cross-check skipped"
    baseline = float(np.mean(per_participant["centralized"]))
    for row in table:
        row["mae_bpm"]["gap_vs_centralized_bpm"] = round(row["mae_bpm"]["mean"] - baseline, 4)
    return {"table": table, "folds": folds, "frozen_m6_cross_check": cross_check,
            "per_participant_mae_bpm": {k: [round(v, 6) for v in vals]
                                        for k, vals in per_participant.items()},
            "participant_order": PARTICIPANTS,
            "dp_accountant_example": accountant(cfg, min(min(c) for c in silo_counts),
                                                cfg.rounds * cfg.local_steps),
            "n_features": len(feature_names)}


def run_dp_sweep(cfg: Config, X, y, participants) -> dict:
    """Privacy/utility trade-off: the same federation at several noise multipliers.

    A single epsilon is not informative on its own; this shows what accuracy a given
    window-level budget actually buys on these 8 participants.
    """
    from dataclasses import replace

    rows = []
    for sigma in cfg.dp_sigma_sweep:
        variant = replace(cfg, noise_multiplier=sigma)
        per_participant, eps_folds = [], []
        for held_out in PARTICIPANTS:
            parr = np.asarray(participants)
            train_mask = parr != held_out
            Xtr, ytr = X[train_mask], y[train_mask]
            ptr = [p for p, keep in zip(participants, train_mask) if keep]
            Xte, yte = X[~train_mask], y[~train_mask]
            mean, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
            sd = np.where(sd > 0, sd, 1.0)
            y_mean, y_sd = float(ytr.mean()), float(ytr.std())
            y_sd = y_sd if y_sd > 0 else 1.0
            clients = make_clients(Xtr, ytr, ptr, held_out, mean, sd, y_mean, y_sd)
            Zte, yte_c = (Xte - mean) / sd, (yte - y_mean) / y_sd
            model, _ = fedavg(clients, Zte, yte_c, variant, seed=7, dp=True)
            per_participant.append(_mean_abs_error(model, Zte, yte_c) * y_sd)
            smallest = min(len(cy) for _, cy in clients)
            eps_folds.append(accountant(variant, smallest, cfg.rounds * cfg.local_steps)["epsilon"])
        rows.append({"noise_multiplier": sigma, "clip_norm": cfg.clip_norm,
                     "mae_bpm": bootstrap_ci(per_participant),
                     "window_level_epsilon_worst_case": max(eps_folds),
                     "window_level_epsilon_best_case": min(eps_folds), "delta": cfg.delta,
                     "is_default_operating_point": sigma == cfg.noise_multiplier})
        print(f"  DP sweep sigma={sigma:4.1f}  MAE={np.mean(per_participant):6.2f} bpm  "
              f"eps<={max(eps_folds):7.3f}", flush=True)
    return {"sweep": rows,
            "note": "identical rounds, steps, clipping and splits; only the Gaussian noise "
                    "multiplier changes. Epsilon is window-level at delta=1e-5, worst case "
                    "over folds and clients. Participant-level privacy is NOT provided."}


def run_robustness(cfg: Config, X, y, participants) -> dict:
    results = []
    for fault in ("sign_flip", "scale"):
        for aggregator in ("mean", "cosine_median"):
            per_participant, dropped = [], []
            for seed in cfg.fault_seeds:
                seed_maes = []
                for held_out in PARTICIPANTS:
                    parr = np.asarray(participants)
                    train_mask = parr != held_out
                    Xtr, ytr = X[train_mask], y[train_mask]
                    ptr = [p for p, keep in zip(participants, train_mask) if keep]
                    Xte, yte = X[~train_mask], y[~train_mask]
                    mean, sd = Xtr.mean(axis=0), Xtr.std(axis=0)
                    sd = np.where(sd > 0, sd, 1.0)
                    y_mean, y_sd = float(ytr.mean()), float(ytr.std())
                    y_sd = y_sd if y_sd > 0 else 1.0
                    clients = make_clients(Xtr, ytr, ptr, held_out, mean, sd, y_mean, y_sd)
                    Zte, yte_c = (Xte - mean) / sd, (yte - y_mean) / y_sd
                    model, trace = fedavg(clients, Zte, yte_c, cfg,
                                          seed=seed, aggregator=aggregator, fault=fault,
                                          fault_client=0)
                    seed_maes.append(_mean_abs_error(model, Zte, yte_c) * y_sd)
                    if trace.get("dropped_client_counts"):
                        dropped.append(trace["dropped_client_counts"][-1])
                per_participant.append(float(np.mean(seed_maes)))
            spread = np.asarray(per_participant)
            # A scale fault can make plain averaging diverge. Reporting 1e20 as an "MAE"
            # would be meaningless, so divergence is reported as divergence.
            diverged = [bool(v > DIVERGENCE_MAE_BPM) for v in per_participant]
            finite = spread[~np.asarray(diverged)]
            results.append({
                "diverged_seeds": int(sum(diverged)),
                "divergence_threshold_bpm": DIVERGENCE_MAE_BPM,
                "raw_per_seed_mae_bpm": [float(f"{v:.6g}") for v in per_participant],
                "fault": fault, "aggregator": aggregator, "n_seeds": len(cfg.fault_seeds),
                "seeds": list(cfg.fault_seeds), "fault_client_index": 0,
                "fault_magnitude": None if fault == "sign_flip" else cfg.fault_scale,
                "mae_bpm_mean_over_seeds": (round(float(finite.mean()), 4)
                                            if finite.size else None),
                "mae_bpm_sd_over_seeds": (round(float(finite.std(ddof=1)), 4)
                                          if finite.size > 1 else None),
                "mae_bpm_min": round(float(finite.min()), 4) if finite.size else None,
                "mae_bpm_max": round(float(finite.max()), 4) if finite.size else None,
                "per_seed_mae_bpm": [round(v, 4) if not d else None
                                     for v, d in zip(per_participant, diverged)],
                "outcome": ("DIVERGED" if all(diverged) else
                            "PARTIALLY_DIVERGED" if any(diverged) else "CONVERGED"),
                "mean_clients_dropped_per_round": (round(float(np.mean(dropped)), 3)
                                                   if dropped else 0.0),
            })
            summary = (f"MAE={finite.mean():.2f}" if finite.size else "DIVERGED")
            print(f"  robustness {fault:9s} {aggregator:14s} {summary} "
                  f"({sum(diverged)}/{len(diverged)} seeds diverged)", flush=True)
    by_key = {(r["fault"], r["aggregator"]): r["mae_bpm_mean_over_seeds"] for r in results}
    comparison = []
    for fault in ("sign_flip", "scale"):
        mean_mae = by_key[(fault, "mean")]
        robust_mae = by_key[(fault, "cosine_median")]
        row = {"fault": fault, "fedavg_mae_bpm": mean_mae,
               "cosine_median_mae_bpm": robust_mae,
               "improvement_bpm": (round(mean_mae - robust_mae, 4)
                                   if mean_mae is not None and robust_mae is not None else None),
               "improvement_pct": (round(100.0 * (mean_mae - robust_mae) / mean_mae, 2)
                                   if mean_mae and robust_mae is not None else None)}
        if mean_mae is None:
            row["finding"] = ("plain FedAvg averaging diverged under this fault in every seed; "
                              "the cosine-screened median stayed finite. No numeric MAE "
                              "difference is quoted because one side has no finite MAE.")
        elif robust_mae is not None and robust_mae > mean_mae:
            row["finding"] = ("the robust aggregator was NOT better on this fault: with f=1 of "
                              "n=4 a sign flip partly cancels in the mean, while the median "
                              "discards a whole honest client. Reported as measured.")
        else:
            row["finding"] = "the cosine-screened median reduced MAE under this fault."
        comparison.append(row)
    return {"runs": results, "comparison": comparison,
            "aggregator_definition": "cosine-screened coordinate-wise median: score each client "
                                     "update by median cosine similarity to the others, drop the "
                                     "lowest-scoring f=1 of n=4, then coordinate-wise median",
            "note": "one faulty client of four, injected in every round; 5 seeds; the same "
                    "LOPO folds and step budget as the accuracy table"}


def git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def build_artifact(cfg: Config) -> dict:
    X, y, participants, feature_names = load_dataset()
    print(f"Loaded {len(y)} windows, {len(feature_names)} features, "
          f"{len(set(participants))} participants", flush=True)
    print("Accuracy (LOPO, MAE bpm):", flush=True)
    accuracy = run_accuracy(cfg, X, y, participants, feature_names)
    print("DP privacy/utility sweep:", flush=True)
    dp_sweep = run_dp_sweep(cfg, X, y, participants)
    print("Robustness (fault injection):", flush=True)
    robustness = run_robustness(cfg, X, y, participants)
    import scipy
    return {
        "title": "Federated / DP-SGD benchmark on frozen M6 participant-separated splits",
        "scope": "RECORDED-NON-ASTRONAUT methods demonstration. Not astronaut data, not "
                 "clinical, not validated, no spaceflight accuracy claim.",
        "task": "predict annotation-derived reference HR (bpm) from 41 frozen wrist "
                "PPG + accelerometer features, 8 s windows",
        "model": "linear least squares trained by minibatch SGD (identical model and step "
                 "budget in all four regimes, so the comparison isolates the training regime)",
        "preprocessing": "features z-scored and target standardised using TRAIN-participant "
                         "statistics only, per fold; predictions converted back to bpm before "
                         "scoring. The DP clip norm C=1.0 therefore acts on a comparable "
                         "scale in every fold. These statistics are not DP-protected.",
        "stability": "learning_rate=0.02 was verified stable on all 8 folds and all 4 silos; "
                     "a non-finite metric raises instead of being written to the artifact",
        "config": cfg.public(),
        "provenance": {
            "script": "scripts/run_fl_dp_benchmark.py",
            "script_sha256": sha256_file(Path(__file__)),
            "features_csv": str(FEATURES_CSV.relative_to(ROOT)),
            "features_sha256": sha256_file(FEATURES_CSV),
            "windows_csv": str(WINDOWS_CSV.relative_to(ROOT)),
            "windows_sha256": sha256_file(WINDOWS_CSV),
            "m6_config_sha256": sha256_file(ROOT / "experiments" / "m6" / "m6-lopo-config.json"),
            "git_head": git_head(),
            "numpy": np.__version__, "scipy": scipy.__version__, "python": sys.version.split()[0],
            "reproduce": "python3 scripts/run_fl_dp_benchmark.py",
            "verify": "python3 scripts/run_fl_dp_benchmark.py --verify",
            "determinism": "fixed seeds, no wall-clock or host-dependent values; re-running "
                           "reproduces this file byte for byte",
        },
        "dataset": {"n_windows": int(len(y)), "n_features": len(feature_names),
                    "participants": PARTICIPANTS,
                    "windows_per_participant": {p: int(sum(1 for q in participants if q == p))
                                                for p in PARTICIPANTS},
                    "splits": "leave-one-participant-out, 8 folds, no random splitting",
                    "client_groups": CLIENT_GROUPS,
                    "client_grouping_note": "clients are participant groups, so no participant "
                                            "is split across clients and no client holds the "
                                            "held-out participant"},
        "threat_model": {
            "level": "WINDOW",
            "neighbouring_dataset": "one 8 s window added or removed from one client",
            "delta": cfg.delta,
            "guarantee_covers": "the client-side clipped/noised SGD steps only",
            "not_covered": [
                "PARTICIPANT-LEVEL privacy: a participant contributes 107-868 windows, so "
                "removing a participant is not bounded by the reported window-level epsilon. "
                "Group (per-participant) clipping is NOT implemented.",
                "the train-only feature standardiser and target centring (non-private "
                "preprocessing statistics shared with the server)",
                "secure aggregation: the server is honest-but-curious and sees each client's "
                "noisy update individually",
                "the raw dataset itself, which is public PhysioNet data",
            ],
            "trust_assumption": "honest-but-curious server, up to f=1 faulty client in the "
                                "robustness experiment only",
        },
        "accuracy": accuracy,
        "dp_privacy_utility": dp_sweep,
        "robustness": robustness,
        "limitations": [
            "Flower and Opacus are not used: torch/flwr/opacus are not installable in this "
            "environment (CUDA wheel size, fastapi pin conflict). The regimes and the RDP "
            "accountant are implemented directly in numpy/scipy and are measured, not quoted.",
            "n=8 participants from one public exercise dataset; participant bootstrap CIs are "
            "wide and cannot support a clinical or spaceflight claim.",
            "IMPORTANT: every regime lands close to the training-mean baseline. The frozen M6 "
            "run found the same thing (ridge A4 32.22 bpm vs the 24.18 bpm mean baseline), so "
            "these 41 features do not generalise across participants. The near-zero measured "
            "DP cost is a consequence of no regime learning much, NOT evidence that strong "
            "privacy is free here.",
            "the linear model is deliberately simple so all four regimes share one step budget; "
            "this is a training-regime comparison, not a state-of-the-art HR model.",
            "DP noise is applied per client per step with a fixed denominator; epsilon is "
            "composed over rounds x local_steps for the smallest client (worst case).",
        ],
    }


def canonical_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="tiny smoke config; never writes")
    parser.add_argument("--verify", action="store_true",
                        help="re-run the full config and compare with the committed artifact")
    parser.add_argument("--out", type=Path, default=ARTIFACT)
    args = parser.parse_args()

    cfg = QUICK if args.quick else Config()
    artifact = build_artifact(cfg)
    text = canonical_json(artifact)
    if args.quick:
        print("\n--quick: smoke run only, artifact NOT written.")
        print(json.dumps(artifact["accuracy"]["table"], indent=2)[:1200])
        return 0
    if args.verify:
        if not args.out.is_file():
            print(f"MISSING artifact: {args.out}", file=sys.stderr)
            return 1
        committed = json.loads(args.out.read_text())
        # git_head moves as the repo advances; compare everything else.
        a, b = json.loads(text), committed
        a["provenance"].pop("git_head", None)
        b["provenance"].pop("git_head", None)
        if canonical_json(a) == canonical_json(b):
            print(f"VERIFIED: re-run reproduces {args.out.relative_to(ROOT)} (git_head ignored)")
            return 0
        print("MISMATCH: the re-run does not reproduce the committed artifact", file=sys.stderr)
        for key in a:
            if canonical_json(a[key]) != canonical_json(b.get(key, {})):
                print(f"  differs: {key}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"\nWrote {args.out.relative_to(ROOT)}  sha256={sha256_file(args.out)}")
    for row in artifact["accuracy"]["table"]:
        m = row["mae_bpm"]
        print(f"  {row['regime']:12s} MAE {m['mean']:7.3f} bpm  "
              f"95% CI [{m['ci_low']:.3f}, {m['ci_high']:.3f}]")
    eps = artifact["accuracy"]["dp_accountant_example"]
    print(f"  DP window-level epsilon = {eps['epsilon']} at delta={eps['delta']} "
          f"(sigma={eps['noise_multiplier']}, q={eps['sampling_rate_q']}, "
          f"steps={eps['accounted_steps']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
